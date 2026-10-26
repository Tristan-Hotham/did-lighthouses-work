"""Print random parsed entries next to their source wikitext, and lighthouse years next to the
list rows, for checking by eye.

Usage: python code/spot_check.py <wikitext.json> <lists.json> <workdir> [seed]
"""
import json
import re
import sys

import pandas as pd


def main(wt, lists, work, seed=11):
    pages = json.load(open(wt, encoding="utf-8"))
    e = pd.read_csv(f"{work}/wreck_entries_all.csv")
    e = e[e.year.between(1750, 1913)]
    for _, r in e.sample(20, random_state=int(seed)).iterrows():
        t = pages[r.page]
        name = re.sub(r"^(SS|PS|HMS|SV|MV|RMS) ", "", str(r.ship)).split(" ")[0]
        i = t.find(f"|desc={str(r.desc)[:12]}")
        if i < 0:
            i = t.find(name)
        heads = [m for m in re.finditer(r"\|\s*date\s*=([^|}]*)|^=+\s*(.*?)\s*=+\s*$", t[:max(i, 0)], flags=re.M)]
        print("=" * 100)
        print(f"PARSED  {r.year}-{r.month}-{r.day} | {r.ship} | {r.flag}\n        {r.desc}")
        print(f"SOURCE  page={r.page} last heading/date={heads[-1].group(0).strip() if heads else None}")
        print("        " + t[max(0, i - 150):i + 450].replace("\n", " ")[:600])
    lh = pd.read_csv(f"{work}/lighthouses_clean.csv")
    L = json.load(open(lists, encoding="utf-8"))
    print("#" * 100)
    for _, r in lh[lh.year_source.str.startswith("Wikipedia list")].sample(10, random_state=int(seed)).iterrows():
        t = L["List of lighthouses in " + r.list]
        key = r["name"].split(" (")[0].split(",")[0]
        i = t.find(key)
        print(f"{r['name']} -> {r.year_first_lit} [{r.year_source}]  cell='{r.list_year_cell}'")
        print("        " + t[i:i + 700].replace("\n", " ")[:700])


if __name__ == "__main__":
    main(*sys.argv[1:])
