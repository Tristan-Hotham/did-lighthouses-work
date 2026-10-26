"""Match wreck descriptions to sites and count mentions per site and year.

Inputs : work/wreck_entries_all.csv, work/lighthouses_clean.csv, aliases.py
Outputs: data/lighthouses.csv        clean lighthouse table, with the site each light belongs to
         data/sites.csv              one row per analysis site (first-lit year, source, group)
         data/wreck_entries.csv      parsed entries 1750 to 1913 that name a site
         data/site_year_counts.csv   mentions per site and year, plus yearly totals
         work/matches_sample.csv     random matched entries for checking

Usage: python code/count_sites.py <workdir> <datadir>
"""
import re
import sys

import pandas as pd

from aliases import SITES, LIGHTVESSEL_SITES, HOME_WORDS

Y0, Y1 = 1750, 1913   # study years: wreck record exists from 1750; 1914 on is wartime

# Sentences that describe a voyage, a port of refuge or later salvage, not the wreck place.
DROP_SENT = re.compile(r"\b(voyage|bound for|bound from|departed|sailed from|sailing from|arrived|"
                       r"taken in(to)?|towed|put in(to)?|was refloated|were refloated|refloated and|"
                       r"brought in(to)?|landed at|rescued by .* and landed|condemned)\b", re.I)


# Other ships named in a description are followed by their flag in brackets,
# e.g. "rescued by the steamship Sanda (United Kingdom)". Remove those names.
OTHER_SHIP = re.compile(r"(?:\b(?:SS|PS|HMS|HMY|RMS|SV|MV|HMT|TSS|HMCS|USS)\s+)?[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,4}\s+\([^()]*\)")
# A distance of more than 10 miles before the place name means the ship was lost at sea,
# with the place used only as a reference point ("abandoned 40 nmi off Flamborough Head").
FAR = re.compile(r"(\d[\d,.]*)\s*(nmi|nautical miles?|miles?|mi|km|kilometres?|leagues?)\b[^.]{0,40}$")


def location_text(desc):
    """Keep only the sentences that say where and how the ship was lost."""
    sents = re.split(r"(?<=[.;])\s+", str(desc))
    keep = [s for s in sents if not DROP_SENT.search(s)]
    return OTHER_SHIP.sub(" ", " ".join(keep))


def near_match(pat, text):
    """True if pat matches somewhere not preceded by a distance over 10 miles."""
    for m in pat.finditer(text):
        f = FAR.search(text[max(0, m.start() - 60):m.start()])
        if f:
            try:
                v = float(f.group(1).replace(",", ""))
            except ValueError:
                v = 0
            if "league" in f.group(2) or v > 10:
                continue
        return True
    return False


def main(work, datadir):
    e = pd.read_csv(f"{work}/wreck_entries_all.csv", dtype={"month": "Int64", "day": "Int64"})
    e["desc"] = e["desc"].fillna("")
    e["loc_text"] = e["desc"].map(location_text)
    home = re.compile(HOME_WORDS)
    e["home"] = e["desc"].map(lambda s: bool(home.search(s)))

    # --- site table -----------------------------------------------------------
    lh = pd.read_csv(f"{work}/lighthouses_clean.csv")
    lh["site"] = ""
    rows = []
    for s in SITES:
        group = s.get("group", "light")
        yrs, ids, used = [], [], []
        for nm in s["lights"]:
            m = lh[(lh["name"] == nm)]
            if s.get("light_list"):
                m = m[m["list"] == s["light_list"]]
            if nm == "Start Point Lighthouse" and not s.get("light_list"):
                m = m[m["list"] == "England"]
            if m.empty:
                raise SystemExit(f"light not found: {nm} ({s['site']})")
            r = m.iloc[0]
            lh.loc[m.index[0], "site"] = s["site"]
            ids.append(r["light_id"])
            if pd.notna(r["year_first_lit"]):
                yrs.append((int(r["year_first_lit"]), r["year_source"], nm))
        first, src = None, ""
        if s.get("first_lit"):
            first, src = s["first_lit"], "hand override"
        elif yrs:
            first, src, _ = min(yrs)
        lat = lon = None
        if ids:
            sub = lh[lh["light_id"].isin(ids)]
            lat, lon = sub["lat"].mean(), sub["lon"].mean()
        if s.get("coord"):
            lat, lon = s["coord"]
        excl = s.get("exclude", "")
        if group == "light" and not excl and first is not None and first < 1760:
            excl = "first lit before 1760"
        rows.append(dict(site=s["site"], group=group, kind=s["kind"], first_lit=first, year_source=src,
                         light_ids=";".join(ids), lights=";".join(s["lights"]), lat=lat, lon=lon,
                         exclude=excl, note=s.get("note", "") or s.get("coord_from", ""), aliases=" | ".join(s["aliases"])))
    sites = pd.DataFrame(rows)
    sites.to_csv(f"{datadir}/sites.csv", index=False)
    lh_out = lh.copy()
    ov = sites[sites.year_source == "hand override"]
    lh_out["site_first_lit"] = lh_out["site"].map(dict(zip(sites.site, sites.first_lit)))
    lh_out["site_year_source"] = lh_out["site"].map(dict(zip(sites.site, sites.year_source)))
    lh_out.to_csv(f"{datadir}/lighthouses.csv", index=False)

    # --- matching -------------------------------------------------------------
    pats = [(s["site"], re.compile("|".join(f"(?:{a})" for a in s["aliases"]))) for s in SITES]
    pats += [(s["site"], re.compile("|".join(f"(?:{a})" for a in s["aliases"]))) for s in LIGHTVESSEL_SITES]
    study = e[(e.year >= Y0) & (e.year <= Y1)].copy()
    matched = []
    for t in study["loc_text"]:
        hits = [name for name, p in pats if near_match(p, t)]
        matched.append(";".join(hits))
    study["sites"] = matched

    # --- outputs --------------------------------------------------------------
    out = study[["entry_id", "year", "month", "day", "ship", "flag", "desc", "home", "sites"]].rename(
        columns={"desc": "description", "home": "home_waters", "sites": "matched_sites"})
    # The full parsed table stays in the work folder (about 35 MB). The release keeps the
    # entries matched to a site; unmatched entries enter only as yearly totals.
    out.to_csv(f"{work}/wreck_entries_study_years.csv", index=False)
    out[out.matched_sites != ""].drop(columns=["home_waters"]).to_csv(f"{datadir}/wreck_entries.csv", index=False)

    long = study[study.sites != ""][["entry_id", "year", "sites"]].copy()
    long["site"] = long["sites"].str.split(";")
    long = long.explode("site")
    cnt = long.groupby(["site", "year"]).size().rename("mentions").reset_index()
    allsites = [s["site"] for s in SITES] + [s["site"] for s in LIGHTVESSEL_SITES]
    grid = pd.MultiIndex.from_product([allsites, range(Y0, Y1 + 1)], names=["site", "year"]).to_frame(index=False)
    grid = grid.merge(cnt, how="left").fillna({"mentions": 0})
    tot = study.groupby("year").size().rename("entries_all")
    homet = study[study.home].groupby("year").size().rename("entries_home")
    grid = grid.merge(tot, on="year", how="left").merge(homet, on="year", how="left").fillna(0)
    grid["mentions"] = grid["mentions"].astype(int)
    grid.to_csv(f"{datadir}/site_year_counts.csv", index=False)

    smp = long.merge(study[["entry_id", "loc_text", "desc"]], on="entry_id").sample(60, random_state=7)
    smp.to_csv(f"{work}/matches_sample.csv", index=False)
    print("entries in study years", len(study), "home waters", int(study.home.sum()),
          "entries matched to any site", int((study.sites != "").sum()))
    print(grid.groupby("site").mentions.sum().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:3])
