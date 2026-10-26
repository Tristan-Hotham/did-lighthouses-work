"""Parse Wikipedia "List of shipwrecks in ..." wikitext into one row per entry.

Input : hist_wrecks_wikitext.json  {page title: wikitext}
Output: work/wreck_entries_all.csv (all parsed entries, used by later steps)
        data/coverage_by_year.csv   (entries parsed per year, pages per year)

Usage: python code/parse_wrecks.py <wikitext.json> <workdir> <datadir>
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict

from wikitext import plain, split_params, extract_templates, country

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
MON_RE = "|".join(MONTHS)


def parse_date(s, year):
    """Return (month, day) from strings like '1 January 1800', 'January 1800', 'Unknown date 1850'."""
    s = plain(s)
    m = re.search(r"(\d{1,2})\s+(%s)" % MON_RE, s)
    if m:
        return MONTHS.index(m.group(2)) + 1, int(m.group(1))
    m = re.search(r"(%s)\s+(\d{1,2})\b(?!\d)" % MON_RE, s)
    if m:
        return MONTHS.index(m.group(1)) + 1, int(m.group(2))
    m = re.search(r"(%s)" % MON_RE, s)
    if m:
        return MONTHS.index(m.group(1)) + 1, None
    return None, None


def parse_page(title, text):
    tm = re.search(r"List of shipwrecks in (?:(%s) )?(\d{4})" % MON_RE, title)
    if not tm:
        return []
    page_month = MONTHS.index(tm.group(1)) + 1 if tm.group(1) else None
    year = int(tm.group(2))
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # positions of headings and list-begin dates, to date each entry
    marks = []
    for m in re.finditer(r"^(={2,4})\s*(.*?)\s*\1\s*$", text, flags=re.M):
        marks.append((m.start(), "h", m.group(2)))
    for i, j, body in extract_templates(text, r"\{\{\s*shipwreck list begin"):
        d = re.search(r"\|\s*date\s*=([^|]*)", body)
        if d:
            marks.append((i, "b", d.group(1)))
    marks.sort()
    rows = []
    for i, j, body in extract_templates(text, r"\{\{\s*shipwreck list item"):
        params = {}
        for p in split_params(body)[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.strip().lower()] = v
        # most recent date mark before this entry
        month, day, src = page_month, None, "page"
        for pos, kind, val in reversed([mk for mk in marks if mk[0] < i]):
            mo, dy = parse_date(val, year)
            if mo is None and re.search(r"unknown", val, re.I):
                break  # an "Unknown date" section: keep page month only
            if mo is not None:
                month, day, src = mo, dy, kind
                break
        ship = plain(params.get("ship", ""))
        flag_raw = params.get("flag", "")
        flag = plain(flag_raw)
        fm = re.search(r"\{\{\s*flag(?:country|icon|u)?\s*\|([^|}]*)", flag_raw, re.I)
        if fm:
            flag = country(fm.group(1)) + ((" " + flag) if flag and country(fm.group(1)) not in flag else "")
        desc = plain(params.get("desc", ""))
        if not (ship or desc):
            continue
        rows.append({"page": title, "year": year, "month": month or "", "day": day or "",
                     "ship": ship, "flag": flag.strip(), "desc": desc})
    return rows


def main(src, work, datadir):
    pages = json.load(open(src, encoding="utf-8"))
    out, pages_by_year, redirects = [], Counter(), 0
    for title, text in pages.items():
        if text.lstrip().upper().startswith("#REDIRECT"):
            redirects += 1
            continue
        rows = parse_page(title, text)
        if rows:
            pages_by_year[rows[0]["year"]] += 1
        out.extend(rows)
    for k, r in enumerate(out):
        r["entry_id"] = k + 1
    cols = ["entry_id", "year", "month", "day", "ship", "flag", "desc", "page"]
    with open(f"{work}/wreck_entries_all.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    by_year = Counter(r["year"] for r in out)
    dated = Counter(r["year"] for r in out if r["day"] != "")
    with open(f"{datadir}/coverage_by_year.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "entries", "entries_with_day", "pages_with_entries"])
        for y in range(1700, 1946):
            w.writerow([y, by_year.get(y, 0), dated.get(y, 0), pages_by_year.get(y, 0)])
    print(f"pages {len(pages)}, redirects skipped {redirects}, entries {len(out)}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
