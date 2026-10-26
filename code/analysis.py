"""Before-and-after and stacked event-study estimates of wreck mentions around first lighting.

Inputs : data/sites.csv, data/site_year_counts.csv, data/coverage_by_year.csv
Output : data/results.json  (every number quoted on the page comes from here)

Design
  Treated sites : lighthouse sites first lit 1760 to 1900 that are not excluded in aliases.py.
  Clean controls: for a treated site lit in year G with window W, every site that was never lit
                  (group "control") or was first lit after G + W (not yet treated), and is not excluded.
  Stacked model : one stack per treated site, years G - W to G + W within 1750 to 1913.
                  Poisson (PPML) with stack-by-site and stack-by-year fixed effects, standard errors
                  clustered by site. Year effects absorb changes in how many wrecks the record holds.
  Event study   : 5-year bins of years relative to G; reference bin is 5 to 1 years before.

Usage: python code/analysis.py <datadir>
"""
import json
import sys

import numpy as np
import pandas as pd

from ppml import fit

Y0, Y1 = 1750, 1913
BINS = [(-20, -16), (-15, -11), (-10, -6), (-5, -1), (0, 4), (5, 9), (10, 14), (15, 20)]
REF = (-5, -1)


def load(datadir):
    sites = pd.read_csv(f"{datadir}/sites.csv")
    sites["exclude"] = sites["exclude"].fillna("")
    c = pd.read_csv(f"{datadir}/site_year_counts.csv")
    return sites, c


def treated_set(sites, lo=1760, hi=1900, drop_override=False, kinds=None):
    t = sites[(sites.group == "light") & (sites.exclude == "") & sites.first_lit.between(lo, hi)]
    if drop_override:
        t = t[t.year_source != "hand override"]
    if kinds:
        t = t[t.kind.isin(kinds)]
    return t


def control_pool(sites, which="both", drop_override=False):
    ok = sites[(sites.exclude == "")]
    if drop_override:
        ok = ok[ok.year_source != "hand override"]
    never = ok[ok.group == "control"]
    later = ok[(ok.group == "light")]
    if which == "never":
        return never, later.iloc[0:0]
    if which == "later":
        return never.iloc[0:0], later
    return never, later


def build_stacks(sites, c, treated, W=20, which="both", drop_override=False, fake_shift=0,
                 dates=None, ylo=Y0, yhi=Y1, min_side=5):
    never, later = control_pool(sites, which, drop_override)
    M = c.pivot(index="site", columns="year", values="mentions")
    parts = []
    used = []
    for k, (_, t) in enumerate(treated.iterrows()):
        G = int(dates[t.site] if dates is not None else t.first_lit) + fake_shift
        lo, hi = max(ylo, G - W), min(yhi, G + W)
        if G - lo < min_side or hi - G < min_side:
            continue
        if fake_shift < 0:          # placebo: use only years before the real lighting
            hi = min(hi, int(t.first_lit) - 1)
            if hi - G < min_side:
                continue
        ctrl = list(never.site) + list(later[later.first_lit > hi].site)
        ctrl = [s for s in ctrl if s != t.site]
        used.append(t.site)
        sub = M.loc[[t.site] + ctrl, lo:hi].stack().rename("y").reset_index()
        sub["stack"] = k
        sub["treated"] = sub.site == t.site
        sub["rel"] = sub.year - G
        parts.append(sub)
    df = pd.concat(parts, ignore_index=True)[["stack", "site", "year", "y", "treated", "rel"]]
    return df, used


def did(df):
    X = (df.treated & (df.rel >= 0)).astype(float).values
    r = fit(df.y.values, X, df["stack"].astype(str) + "|" + df.site, df["stack"].astype(str) + "|" + df.year.astype(str), df.site)
    return r


def did_donut(df):
    """Post-lighting years and the 5-year run-up each get a term; the reference is 6 to 20 years before."""
    X = np.column_stack([(df.treated & df.rel.between(-5, -1)).astype(float).values,
                         (df.treated & (df.rel >= 0)).astype(float).values])
    return fit(df.y.values, X, df["stack"].astype(str) + "|" + df.site, df["stack"].astype(str) + "|" + df.year.astype(str), df.site)


def event(df):
    cols = []
    for a, b in BINS:
        if (a, b) == REF:
            continue
        cols.append((df.treated & df.rel.between(a, b)).astype(float).values)
    X = np.column_stack(cols)
    r = fit(df.y.values, X, df["stack"].astype(str) + "|" + df.site, df["stack"].astype(str) + "|" + df.year.astype(str), df.site)
    return r


def summarise(r, j=0):
    b, se = float(r["b"][j]), float(r["se"][j])
    return dict(coef=b, se=se, irr=float(np.exp(b)), lo=float(np.exp(b - 1.96 * se)), hi=float(np.exp(b + 1.96 * se)),
                pct=float(np.exp(b) - 1), pct_lo=float(np.exp(b - 1.96 * se) - 1), pct_hi=float(np.exp(b + 1.96 * se) - 1),
                n_obs=r["n"], n_clusters=r["clusters"], mentions=r["events"])


def simple_before_after(sites, c, treated, N=10, denom="entries_home"):
    """Share of the year's wreck entries naming the site, N years before vs N years after (lighting year left out)."""
    out = []
    for _, t in treated.iterrows():
        G = int(t.first_lit)
        s = c[c.site == t.site]
        b = s[s.year.between(G - N, G - 1) & (s.year >= Y0)]
        a = s[s.year.between(G + 1, G + N) & (s.year <= Y1)]
        if len(b) < N // 2 or len(a) < N // 2:
            continue
        out.append(dict(site=t.site, G=G, before=int(b.mentions.sum()), after=int(a.mentions.sum()),
                        den_before=float(b[denom].sum()), den_after=float(a[denom].sum())))
    d = pd.DataFrame(out)
    d["rate_before"] = d.before / d.den_before * 1000
    d["rate_after"] = d.after / d.den_after * 1000
    pooled = (d.after.sum() / d.den_after.sum()) / (d.before.sum() / d.den_before.sum())
    both = d[(d.before + d.after) > 0]
    fell = int((both.rate_after < both.rate_before).sum())
    rose = int((both.rate_after > both.rate_before).sum())
    return d, dict(n_lights=len(d), n_with_mentions=len(both), pooled_ratio=float(pooled),
                   fell=fell, rose=rose, same=int(len(both) - fell - rose),
                   before=int(d.before.sum()), after=int(d.after.sum()))


def main(datadir):
    sites, c = load(datadir)
    cov = pd.read_csv(f"{datadir}/coverage_by_year.csv")
    R = {}
    T = treated_set(sites)
    R["sample"] = dict(n_sites_total=int(len(sites)), n_light_sites=int((sites.group == "light").sum()),
                       n_controls_never=int(((sites.group == "control")).sum()),
                       n_excluded=int((sites.exclude != "").sum()),
                       n_treated=int(len(T)), treated_first=int(T.first_lit.min()), treated_last=int(T.first_lit.max()),
                       n_later_lit=int(((sites.group == "light") & (sites.exclude == "") & (sites.first_lit > 1900)).sum()),
                       n_overrides=int((sites.year_source == "hand override").sum()))
    # ---- coverage
    st = c.drop_duplicates("year")[["year", "entries_all", "entries_home"]]
    R["coverage"] = dict(
        total_entries=int(cov.entries.sum()),
        study_entries=int(st.entries_all.sum()), study_home=int(st.entries_home.sum()),
        mean_1760s=float(cov[cov.year.between(1760, 1769)].entries.mean()),
        mean_1800s=float(cov[cov.year.between(1800, 1809)].entries.mean()),
        mean_1850s=float(cov[cov.year.between(1850, 1859)].entries.mean()),
        mean_1880s=float(cov[cov.year.between(1880, 1889)].entries.mean()),
        mean_1895_1913=float(cov[cov.year.between(1895, 1913)].entries.mean()),
        peak_year=int(cov.loc[cov[cov.year <= 1913].entries.idxmax(), "year"]),
        peak_entries=int(cov[cov.year <= 1913].entries.max()),
        first_year=int(cov[cov.entries > 0].year.min()),
        site_mentions=int(c[c.site.isin(sites.site)].mentions.sum()),
        pre1750_entries=int(cov[cov.year < 1750].entries.sum()),
    )
    # ---- simple before/after
    d10, s10 = simple_before_after(sites, c, T, 10)
    d20, s20 = simple_before_after(sites, c, T, 20)
    _, s10all = simple_before_after(sites, c, T, 10, denom="entries_all")
    R["simple"] = dict(w10=s10, w20=s20, w10_alldenom=s10all)
    # same simple measure for never-lit controls with each treated light's date (a reference)
    ctrl_sites = sites[sites.group == "control"]
    ref = []
    for _, t in T.iterrows():
        for _, k in ctrl_sites.iterrows():
            ref.append(dict(site=k.site, first_lit=float(t.first_lit)))
    _, sref = simple_before_after(sites, c, pd.DataFrame(ref), 10)
    R["simple"]["controls_same_dates_w10"] = sref
    # ---- stacked DiD and event study
    main_df, used = build_stacks(sites, c, T, W=20)
    R["did_w20"] = summarise(did(main_df)) | dict(n_stacks=len(used))
    dn = did_donut(main_df)
    R["did_donut"] = dict(runup=summarise(dn, 0), post=summarise(dn, 1), n_stacks=len(used))
    df10, used10 = build_stacks(sites, c, T, W=10)
    R["did_w10"] = summarise(did(df10)) | dict(n_stacks=len(used10))
    ev = event(main_df)
    evrows, j = [], 0
    for a, b in BINS:
        if (a, b) == REF:
            evrows.append(dict(bin=f"{a} to {b}", mid=(a + b) / 2, irr=1.0, lo=1.0, hi=1.0, ref=True))
            continue
        s = summarise(ev, j); j += 1
        evrows.append(dict(bin=f"{a} to {b}", mid=(a + b) / 2, irr=s["irr"], lo=s["lo"], hi=s["hi"], ref=False))
    R["event"] = evrows
    # raw event-time profile: treated mentions relative to the year's home entries
    rows = []
    for _, t in T.iterrows():
        s = c[c.site == t.site]
        for _, r in s.iterrows():
            rel = int(r.year - t.first_lit)
            if -20 <= rel <= 20:
                rows.append((rel, r.mentions, r.entries_home))
    rp = pd.DataFrame(rows, columns=["rel", "m", "home"]).groupby("rel").sum()
    R["raw_profile"] = [dict(rel=int(k), mentions=int(v.m), per1000=float(v.m / v.home * 1000) if v.home else None)
                        for k, v in rp.iterrows()]
    # ---- robustness
    rob = {}
    def run(name, **kw):
        tr = kw.pop("treated", T)
        dfr, u = build_stacks(sites, c, tr, **kw)
        rob[name] = summarise(did(dfr)) | dict(n_stacks=len(u))
        dn = did_donut(dfr)
        rob[name]["donut"] = summarise(dn, 1)
        rob[name]["runup"] = summarise(dn, 0)
    run("never_lit_controls_only", W=20, which="never")
    run("later_lit_controls_only", W=20, which="later")
    run("drop_hand_overrides", W=20, drop_override=True, treated=treated_set(sites, drop_override=True))
    run("rocks_and_islands", W=20, treated=treated_set(sites, kinds=["rock", "island"]))
    run("headlands_and_sands", W=20, treated=treated_set(sites, kinds=["headland", "sands"]))
    run("lit_1760_1840", W=20, treated=treated_set(sites, 1760, 1840))
    run("lit_1841_1900", W=20, treated=treated_set(sites, 1841, 1900))
    run("years_to_1890_only", W=20, yhi=1890)
    # leave out the three sites with most mentions in their own stack
    tops = main_df[main_df.treated].groupby("site").y.sum().sort_values(ascending=False)
    R["top_treated"] = [dict(site=s, mentions=int(v)) for s, v in tops.head(8).items()]
    run("drop_top3_treated", W=20, treated=T[~T.site.isin(tops.index[:3])])
    run("window_10", W=10)
    loo = []
    for s in tops[tops > 0].index:
        dfr, _ = build_stacks(sites, c, T[T.site != s], W=20)
        loo.append(dict(site=s, irr=float(np.exp(did(dfr)["b"][0])), irr_donut=float(np.exp(did_donut(dfr)["b"][1]))))
    R["leave_one_out"] = dict(min=min(x["irr"] for x in loo), max=max(x["irr"] for x in loo),
                              min_site=min(loo, key=lambda x: x["irr"])["site"], max_site=max(loo, key=lambda x: x["irr"])["site"],
                              donut_min=min(x["irr_donut"] for x in loo), donut_max=max(x["irr_donut"] for x in loo),
                              donut_min_site=min(loo, key=lambda x: x["irr_donut"])["site"], donut_max_site=max(loo, key=lambda x: x["irr_donut"])["site"])
    R["robustness"] = rob
    # ---- placebo 1: fake lighting 10 years early, using only pre-lighting years
    pdf, pu = build_stacks(sites, c, T, W=10, fake_shift=-10)
    R["placebo_early"] = summarise(did(pdf)) | dict(n_stacks=len(pu))
    # placebo with the run-up removed: fake date 15 years early, using only years up to 6 before the real date
    pdf2, pu2 = build_stacks(sites, c, T, W=10, fake_shift=-15, yhi=Y1)
    pdf2 = pdf2[pdf2.rel <= 9]
    R["placebo_early_norunup"] = summarise(did(pdf2)) | dict(n_stacks=int(pdf2[pdf2.treated].site.nunique()))
    # ---- placebo 2: permutation of lighting years across treated sites
    rng = np.random.default_rng(2026)
    obs = R["did_w20"]["coef"]
    perm, perm_d = [], []
    yrs = T.first_lit.values.copy()
    for i in range(200):
        if i % 20 == 0:
            print("permutation", i, flush=True)
        p = rng.permutation(yrs)
        dates = dict(zip(T.site, p))
        dfp, _ = build_stacks(sites, c, T, W=20, dates=dates)
        perm.append(float(did(dfp)["b"][0]))
        perm_d.append(float(did_donut(dfp)["b"][1]))
    perm = np.array(perm)
    perm_d = np.array(perm_d)
    obs_d = R["did_donut"]["post"]["coef"]
    R["permutation_donut"] = dict(n=len(perm_d), observed=obs_d,
                                  p_two_sided=float((np.sum(np.abs(perm_d - np.median(perm_d)) >= abs(obs_d - np.median(perm_d))) + 1) / (len(perm_d) + 1)),
                                  perm_irr_median=float(np.exp(np.median(perm_d))),
                                  perm_irr_p05=float(np.exp(np.percentile(perm_d, 5))), perm_irr_p95=float(np.exp(np.percentile(perm_d, 95))),
                                  share_below=float(np.mean(perm_d <= obs_d)),
                                  hist=np.histogram(np.exp(perm_d), bins=24, range=(0, 3))[0].tolist())
    R["permutation"] = dict(n=len(perm), observed=obs, p_two_sided=float((np.sum(np.abs(perm) >= abs(obs)) + 1) / (len(perm) + 1)),
                            p_one_sided_lower=float((np.sum(perm <= obs) + 1) / (len(perm) + 1)),
                            perm_irr_p05=float(np.exp(np.percentile(perm, 5))), perm_irr_p95=float(np.exp(np.percentile(perm, 95))),
                            perm_irr_median=float(np.exp(np.median(perm))),
                            share_below=float(np.mean(perm <= obs)),
                            hist=np.histogram(np.exp(perm), bins=24, range=(0, 3))[0].tolist())
    # ---- per-site table for the page
    per = []
    d10i = d10.set_index("site")
    for _, s in sites.iterrows():
        row = dict(site=s.site, group=s.group, kind=s.kind, first_lit=None if pd.isna(s.first_lit) else int(s.first_lit),
                   year_source=s.year_source if isinstance(s.year_source, str) else "", exclude=s.exclude,
                   lat=None if pd.isna(s.lat) else round(float(s.lat), 4), lon=None if pd.isna(s.lon) else round(float(s.lon), 4),
                   treated=bool(s.site in set(T.site)), total=int(c[c.site == s.site].mentions.sum()),
                   note=s.note if isinstance(s.note, str) else "", aliases=s.aliases)
        if s.site in d10i.index:
            r = d10i.loc[s.site]
            row.update(before10=int(r.before), after10=int(r.after), rate_before10=float(r.rate_before), rate_after10=float(r.rate_after))
        per.append(row)
    R["sites"] = per
    json.dump(R, open(f"{datadir}/results.json", "w"), indent=1, default=float)
    print(json.dumps({k: R[k] for k in ["did_donut", "sample", "simple", "did_w20", "did_w10", "robustness", "placebo_early", "leave_one_out"]}, indent=1, default=float))
    print(json.dumps(R["event"], indent=0))
    print({k: v for k, v in R["permutation"].items() if k != "hist"})


if __name__ == "__main__":
    main(sys.argv[1])
