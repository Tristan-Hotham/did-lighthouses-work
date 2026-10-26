"""Build a clean lighthouse table from Wikipedia lists and Wikidata.

Inputs : hist_lighthouse_lists.json (wikitext of six Wikipedia lists)
         hist_lighthouses.json      (Wikidata SPARQL results)
Output : work/lighthouses_clean.csv (every light kept after cleaning)

Year rules (the column year_source records which applied):
  1. list year: the list's "First lit" column (England inactive table), otherwise the first
     year in its "Year built" cell (Irish and Manx lists often give "1850/1965", first light
     then current tower, so the first year is used).
  2. For list rows that are drawn from Wikidata (Scotland, Wales, Channel Islands), and for
     Wikidata items not in any list: Wikidata service entry (P729), then inception (P571).
  3. Hand overrides for the first light at a site, in aliases.py (FIRST_LIGHT_OVERRIDES),
     applied later in build_sites.py, never here.

Usage: python code/build_lighthouses.py <lists.json> <wikidata.json> <workdir>
"""
import csv
import json
import math
import re
import sys

from wikitext import plain, split_params

SKIP_WORDS = re.compile(r"keeper|cottage|house(?!.*lighthouse)|houses|store|engine|fog ?signal|"
                        r"boundary wall|bothy|stables|gate ?piers|walled garden|steading|"
                        r"\bbarn\b|offices|boundary|outbuilding|dwelling|toilet|hut\b|walls",
                        re.I)


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(d))


def years(s):
    return [int(y) for y in re.findall(r"(?<!\d)(1[5-9]\d\d|20[0-2]\d)(?!\d)", s)]


def coord_from(cell):
    m = re.search(r'latitude="([-\d.]+)"\s+longitude="([-\d.]+)"', cell)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"\{\{\s*[cC]oord\s*\|([^}]*)\}\}", cell)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split("|")]
    nums, dirs = [], []
    for p in parts:
        if re.fullmatch(r"-?\d+(\.\d+)?", p):
            nums.append(float(p))
        elif p in ("N", "S", "E", "W"):
            dirs.append((p, len(nums)))
        elif "=" in p or ":" in p:
            break
    if not dirs and len(nums) >= 2:
        return nums[0], nums[1]
    if len(dirs) == 2:
        (d1, i1), (d2, i2) = dirs
        lat = nums[:i1]; lon = nums[i1:i2]
        f = lambda v: sum(x / 60 ** k for k, x in enumerate(v))
        la, lo = f(lat), f(lon)
        return (-la if d1 == "S" else la), (-lo if d2 == "W" else lo)
    return None


def parse_classic_tables(title, text):
    """Rows of hand-written wikitables (England, Ireland, Isle of Man)."""
    rows = []
    for tm in re.finditer(r"\{\|[^\n]*wikitable.*?\n\|\}", text, flags=re.S):
        tbl = tm.group(0)
        sec = re.findall(r"\n==\s*([^=\n]+?)\s*==", text[:tm.start()])
        section = sec[-1] if sec else ""
        hdr = [plain(h.lstrip("!").split("|")[-1]) for h in re.findall(r"^!(?!scope)[^\n]*", tbl, flags=re.M)]
        year_col = next((i for i, h in enumerate(hdr) if re.search(r"first lit|year built|^built", h, re.I)), None)
        dec_col = next((i for i, h in enumerate(hdr) if re.search(r"decom|inactive", h, re.I)), None)
        for chunk in re.split(r"\n\|-+[^\n]*", tbl)[1:]:
            chunk = chunk.strip()
            if not chunk or chunk.startswith("|}") or chunk.startswith("!") and "scope" not in chunk:
                continue
            lines = [ln for ln in chunk.split("\n") if ln.startswith(("|", "!")) and not ln.startswith("|}")]
            cells = []
            for ln in lines:
                body = ln[1:]
                for c in re.split(r"\|\||!!", body):
                    cells.append(c)
            # drop attribute prefixes such as style="..."| or scope='row' |
            clean = []
            for c in cells:
                ps = split_params(c)
                if len(ps) > 1 and re.search(r"(style|scope|align|bgcolor|width)\s*=", ps[0]):
                    c = "|".join(ps[1:])
                clean.append(c.strip())
            if len(clean) < 4:
                continue
            name_raw = clean[0]
            name = plain(name_raw)
            if not name or name.lower() in ("name",):
                continue
            loc_cell = clean[2] if len(clean) > 2 else ""
            location = plain(re.sub(r"<span.*", "", re.sub(r"\{\{\s*[cC]oord[^}]*\}\}", "", loc_cell), flags=re.S))
            cd = coord_from(loc_cell) or coord_from(chunk)
            yr_cell = clean[year_col] if year_col is not None and year_col < len(clean) else ""
            ys = years(plain(re.sub(r"<ref.*?(</ref>|/>)", "", yr_cell, flags=re.S)))
            dec = None
            if dec_col is not None and dec_col < len(clean):
                dy = years(plain(clean[dec_col]))
                dec = dy[0] if dy else None
            notes = plain(" ".join(re.findall(r"\{\{efn\|([^{}]*)\}\}", chunk)))
            rows.append({"name": name, "location": location, "lat": cd[0] if cd else None,
                         "lon": cd[1] if cd else None, "list": title.replace("List of lighthouses in ", ""),
                         "section": section, "list_year": ys[0] if ys else None,
                         "list_year_cell": plain(yr_cell)[:40], "list_years_all": "/".join(map(str, ys)),
                         "decommissioned": dec, "notes": notes, "qid": ""})
    return rows


def parse_wd_rows(title, text):
    rows = []
    for m in re.finditer(r"\{\{Wdtable row/[^|]*\|qid=(Q\d+)([^\n]*)\}\}", text):
        notes = plain(" ".join(re.findall(r"\{\{efn\|([^{}]*)\}\}", m.group(2))))
        sec = re.findall(r"\n==\s*([^=\n]+?)\s*==", text[:m.start()])
        rows.append({"qid": m.group(1), "list": title.replace("List of lighthouses in ", ""),
                     "section": sec[-1] if sec else "", "notes": notes})
    return rows


def norm(n):
    n = n.lower()
    n = re.sub(r"\b(lighthouse|light|lighthouses|tower|the|old|new)\b", " ", n)
    return re.sub(r"[^a-z]+", " ", n).strip()


def main(lists_path, wd_path, work):
    lists = json.load(open(lists_path, encoding="utf-8"))
    wd = json.load(open(wd_path, encoding="utf-8"))["results"]["bindings"]
    items = {}
    for r in wd:
        q = r["l"]["value"].rsplit("/", 1)[-1]
        v = {k: x["value"] for k, x in r.items()}
        m = re.search(r"Point\(([-\d.]+) ([-\d.]+)\)", v.get("coord", ""))
        it = items.setdefault(q, {"qid": q, "label": v.get("lLabel", q), "lat": None, "lon": None,
                                   "inception": None, "service": None, "end": None})
        if m and it["lat"] is None:
            it["lon"], it["lat"] = float(m.group(1)), float(m.group(2))
        for k in ("inception", "service", "end"):
            if v.get(k):
                y = int(v[k][:5].lstrip("+")[:4]) if re.match(r"[+-]?\d{4}", v[k]) else None
                if y and (it[k] is None or y < it[k]):
                    it[k] = y
    out = []
    used_q = set()
    for title, text in lists.items():
        for r in parse_classic_tables(title, text):
            r.update({"wd_inception": None, "wd_service": None, "wd_end": None})
            out.append(r)
        for r in parse_wd_rows(title, text):
            it = items.get(r["qid"])
            if not it:
                continue
            used_q.add(r["qid"])
            out.append({"name": it["label"], "location": "", "lat": it["lat"], "lon": it["lon"],
                        "list": r["list"], "section": r["section"], "list_year": None,
                        "list_year_cell": "", "list_years_all": "", "decommissioned": it["end"],
                        "notes": r["notes"], "qid": r["qid"], "wd_inception": it["inception"],
                        "wd_service": it["service"], "wd_end": it["end"]})
    # attach Wikidata items to classic list rows by name and distance
    for r in out:
        if r["qid"] or r["lat"] is None:
            continue
        best = None
        for q, it in items.items():
            if it["lat"] is None or SKIP_WORDS.search(it["label"]):
                continue
            d = km((r["lat"], r["lon"]), (it["lat"], it["lon"]))
            same = norm(it["label"]) and (norm(it["label"]) in norm(r["name"]) or norm(r["name"]) in norm(it["label"]))
            if d < 1.0 and same or d < 0.15:
                if best is None or d < best[0]:
                    best = (d, q)
        if best:
            it = items[best[1]]
            r.update({"qid": best[1], "wd_inception": it["inception"], "wd_service": it["service"], "wd_end": it["end"]})
            used_q.add(best[1])
    # Wikidata items not in any list (skip keepers' houses and other buildings)
    for q, it in items.items():
        if q in used_q or it["lat"] is None or SKIP_WORDS.search(it["label"]):
            continue
        if not re.search(r"light|beacon|tower|pharos", it["label"], re.I):
            continue
        out.append({"name": it["label"], "location": "", "lat": it["lat"], "lon": it["lon"],
                    "list": "Wikidata only", "section": "", "list_year": None, "list_year_cell": "",
                    "list_years_all": "", "decommissioned": it["end"], "notes": "", "qid": q,
                    "wd_inception": it["inception"], "wd_service": it["service"], "wd_end": it["end"]})
    # year first lit and its source
    for r in out:
        if r["list_year"]:
            r["year_first_lit"], r["year_source"] = r["list_year"], "Wikipedia list"
        elif r["wd_service"]:
            r["year_first_lit"], r["year_source"] = r["wd_service"], "Wikidata service entry (P729)"
        elif r["wd_inception"]:
            r["year_first_lit"], r["year_source"] = r["wd_inception"], "Wikidata inception (P571)"
        else:
            r["year_first_lit"], r["year_source"] = None, "none"
        m = re.search(r"not lit till (\d{4})", r["notes"])
        if m:
            r["year_first_lit"], r["year_source"] = int(m.group(1)), "Wikipedia list note"
    # remove exact duplicates (same qid or same name within 200 m)
    seen, clean = [], []
    for r in out:
        dup = False
        for s in seen:
            if r["qid"] and r["qid"] == s["qid"]:
                dup = True
            elif r["lat"] is not None and s["lat"] is not None and norm(r["name"]) == norm(s["name"]) \
                    and km((r["lat"], r["lon"]), (s["lat"], s["lon"])) < 0.2:
                dup = True
            if dup:
                break
        if not dup:
            seen.append(r)
            clean.append(r)
    for i, r in enumerate(clean):
        r["light_id"] = f"L{i + 1:03d}"
    cols = ["light_id", "name", "location", "lat", "lon", "list", "section", "year_first_lit", "year_source",
            "list_years_all", "list_year_cell", "wd_service", "wd_inception", "wd_end", "decommissioned", "qid", "notes"]
    with open(f"{work}/lighthouses_clean.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(clean)
    print(f"list+wikidata rows {len(out)}, clean {len(clean)}, wikidata items {len(items)}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
