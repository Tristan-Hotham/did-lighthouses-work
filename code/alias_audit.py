"""Audit the hand-written aliases against the OS Open Names gazetteer (Great Britain only).

For each alias of a site in Great Britain, list the coastal features and settlements in the
gazetteer whose names the alias pattern matches, and their distance from the light.
  near_km : distance to the nearest matching feature (should be small: the alias is local)
  far_n   : matching features more than 25 km away (possible ambiguity)
Ireland, the Isle of Man and the Channel Islands are not in the gazetteer and are not audited.

Gazetteer: OS Open Names, Ordnance Survey, Open Government Licence v3.0.
Contains OS data (c) Crown copyright and database right 2026. The gazetteer itself is not
redistributed; only the audit table is.

Usage: python code/alias_audit.py <osnames_gb.tsv> <datadir>
"""
import re
import sys

import numpy as np
import pandas as pd

from aliases import SITES

TYPES = {"Other Coastal Landform", "Coastal Headland", "Bay", "Island", "Group Of Islands", "Tidal Water",
         "Channel", "Estuary", "Sea", "Beach", "Cliff Or Slope", "Town", "Village", "Hamlet", "City",
         "Other Settlement", "Suburban Area"}


def main(path, datadir):
    g = pd.read_csv(path, sep="\t", usecols=["name1", "name2", "local_type", "lat", "lon", "county"],
                    dtype=str, quoting=3)
    g = g[g.local_type.isin(TYPES)].copy()
    g["lat"] = g.lat.astype(float)
    g["lon"] = g.lon.astype(float)
    g["names"] = g.name1.fillna("") + " / " + g.name2.fillna("")
    sites = pd.read_csv(f"{datadir}/sites.csv")
    pos = dict(zip(sites.site, zip(sites.lat, sites.lon)))
    rows = []
    for s in SITES:
        la, lo = pos.get(s["site"], (np.nan, np.nan))
        if pd.isna(la) or la < 49.8 or (lo < -5.5 and la < 55.0 and la > 51.3):  # skip Ireland / no coords
            continue
        if s["site"] in ("Calf of Man", "Chicken Rock", "Point of Ayre (Man)", "Langness", "Douglas Head",
                         "Maughold Head", "Les Hanois", "Sark", "Casquets", "St John's Point (Down)",
                         "South Rock", "Maidens", "Rathlin Island"):
            continue
        for a in s["aliases"]:
            p = re.compile(a)
            m = g[g.names.map(lambda n: bool(p.search(n)))]
            if m.empty:
                rows.append(dict(site=s["site"], alias=a, gazetteer_matches=0, near_km=None, far_n=0, far_examples=""))
                continue
            d = 6371 * 2 * np.arcsin(np.sqrt(np.sin(np.radians(m.lat - la) / 2) ** 2 + np.cos(np.radians(la)) *
                                             np.cos(np.radians(m.lat)) * np.sin(np.radians(m.lon - lo) / 2) ** 2))
            far = m[d > 25]
            rows.append(dict(site=s["site"], alias=a, gazetteer_matches=len(m), near_km=round(float(d.min()), 1),
                             far_n=len(far), far_examples="; ".join((far.name1 + " (" + far.county.fillna("") + ")").head(4))))
    out = pd.DataFrame(rows)
    out.to_csv(f"{datadir}/alias_audit.csv", index=False)
    print(out.to_string(max_colwidth=60))


if __name__ == "__main__":
    main(*sys.argv[1:3])
