"""Build index.html from code/page_template.html, data/results.json and the CSV outputs.

Two things happen here:
  1. A compact JSON object (D) with everything the charts and the map need is embedded.
  2. Tokens in the template of the form {{path.to.value|format}} are replaced with numbers
     from results.json, so every number in the text comes from the analysis output.
     Formats: int, pct0, pct1, x2 (two decimals), abs_pct0 (percentage without sign), f1.

Usage: python code/export_page_data.py <datadir>
"""
import json
import os
import re
import sys

import pandas as pd

Y0, Y1 = 1750, 1913


def get(R, path):
    if path.startswith("site:"):
        name, _, field = path[5:].rpartition(".")
        return next(x for x in R["sites"] if x["site"] == name)[field]
    v = R
    for p in path.split("."):
        v = v[int(p)] if isinstance(v, list) else v[p]
    return v


def fmt(v, f):
    out = _fmt(v, f)
    return out.replace("-", "\u2212", 1) if out.startswith("-") else out


def _fmt(v, f):
    if f == "spct0":
        return ("+" if v > 0 else "") + f"{v * 100:.0f}%"
    if f == "year":
        return str(int(v))
    if f == "int":
        return f"{int(round(v)):,}"
    if f == "pct0":
        return f"{v * 100:.0f}%"
    if f == "pct1":
        return f"{v * 100:.1f}%"
    if f == "abs_pct0":
        return f"{abs(v) * 100:.0f}%"
    if f == "x2":
        return f"{v:.2f}"
    if f == "f1":
        return f"{v:.1f}"
    if f == "p3":
        return f"{v:.3f}" if v >= 0.001 else "< 0.001"
    if f == "p2":
        return f"{v:.2f}"
    return str(v)


def main(datadir):
    R = json.load(open(f"{datadir}/results.json"))
    R["spot"] = json.load(open(f"{datadir}/spot_checks.json"))
    cov = pd.read_csv(f"{datadir}/coverage_by_year.csv")
    c = pd.read_csv(f"{datadir}/site_year_counts.csv")
    lh = pd.read_csv(f"{datadir}/lighthouses.csv")
    home = c.drop_duplicates("year").set_index("year")["entries_home"]
    D = {}
    D["cov"] = dict(y0=int(cov.year.min()), all=cov.entries.astype(int).tolist(),
                    home0=Y0, home=[int(home.get(y, 0)) for y in range(Y0, Y1 + 1)])
    # every light with a position, dated by its site's first light where it belongs to a site
    L = []
    for _, r in lh.iterrows():
        if pd.isna(r.lat):
            continue
        y = r.site_first_lit if isinstance(r.site, str) and r.site and not pd.isna(r.site_first_lit) else r.year_first_lit
        if pd.isna(y) or y < 1:
            continue
        L.append([round(r.lat, 3), round(r.lon, 3), int(y), r["name"], r.site if isinstance(r.site, str) else ""])
    D["lights"] = L
    M = c.pivot(index="site", columns="year", values="mentions")
    S = []
    for s in R["sites"]:
        if s["lat"] is None:
            continue
        ser = M.loc[s["site"]].astype(int).tolist() if s["site"] in M.index else []
        S.append(dict(n=s["site"], la=s["lat"], lo=s["lon"], y=s["first_lit"], g=s["group"], k=s["kind"],
                      t=s["treated"], x=s["exclude"], src=s["year_source"], tot=s["total"],
                      b=s.get("before10"), a=s.get("after10"), rb=s.get("rate_before10"), ra=s.get("rate_after10"),
                      note=s["note"], al=s["aliases"], s=ser))
    D["sites"] = S
    D["controls"] = [dict(n=s["site"], tot=s["total"], s=M.loc[s["site"]].astype(int).tolist())
                     for s in R["sites"] if s["group"] == "control"]
    D["event"] = R["event"]
    D["raw"] = R["raw_profile"]
    D["perm"] = R["permutation"]
    D["permd"] = R["permutation_donut"]
    D["rob"] = R["robustness"] | {"main_w20": R["did_w20"], "donut": R["did_donut"]["post"],
                                  "placebo_early": R["placebo_early"], "placebo_early_norunup": R["placebo_early_norunup"]}
    D["Y0"], D["Y1"] = Y0, Y1
    tpl = open(os.path.join(os.path.dirname(__file__), "page_template.html"), encoding="utf-8").read()
    tpl = tpl.replace("/*__DATA__*/", "const D = " + json.dumps(D, separators=(",", ":"), ensure_ascii=False) + ";")

    def rep(m):
        path, _, f = m.group(1).partition("|")
        return fmt(get(R, path.strip()), f.strip())
    out = re.sub(r"\{\{([^{}]+)\}\}", rep, tpl)
    left = re.findall(r"\{\{[^{}]*\}\}", out)
    if left:
        raise SystemExit(f"unreplaced tokens: {left[:5]}")
    open(os.path.join(datadir, "..", "index.html"), "w", encoding="utf-8").write(out)
    print("index.html", len(out.encode()) // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1])
