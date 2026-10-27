import json, os
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Polygon as MPoly
from matplotlib.collections import PatchCollection
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely import prepared

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', 'data')
F = '/tmp/claude-0/-home-claude/c232619d-81e0-53f3-9de6-41e973630753/scratchpad/fonts/'
for f in ['FrauncesVar.ttf', 'IBMPlexMono-Regular.ttf', 'IBMPlexMono-Medium.ttf', 'SourceSerif4-Regular.ttf', 'SourceSerif4-Semibold.ttf', 'SourceSerif4-It.ttf']:
    fm.fontManager.addfont(F + f)
DISP = fm.FontProperties(fname=F + 'FrauncesVar.ttf', weight=900)
SER = 'Source Serif 4'; MONO = 'IBM Plex Mono'

BG = '#06101F'; SEA2 = '#0B1A30'; LAND = '#16233A'; EDGE = '#2A3B58'
FG = '#F2EAD8'; MUT = '#8C98AE'; GOLD = '#FFC857'; CORAL = '#FF7A59'; SPARK = '#9FC3FF'

R = json.load(open(os.path.join(D, 'results.json')))
S = pd.DataFrame(R['sites'])
W = pd.read_csv(os.path.join(D, 'wreck_entries.csv'))
C = pd.read_csv(os.path.join(D, 'coverage_by_year.csv'))
Y = pd.read_csv(os.path.join(D, 'site_year_counts.csv'))
LH = pd.read_csv(os.path.join(D, 'lighthouses.csv'))

K = np.cos(np.radians(55.0))
def P(lon, lat):
    return np.asarray(lon) * K, np.asarray(lat)

geo = json.load(open(os.path.join(HERE, '..', 'release', 'build', 'ne10m_land_british_isles.json')))
polys = []
for g in geo:
    gg = shape(g)
    polys.append(gg)
land_ll = unary_union(polys)
from shapely.affinity import scale as sscale
land = sscale(land_ll, xfact=K, yfact=1.0, origin=(0, 0))
pl = prepared.prep(land)

def seaward(x, y):
    """Direction (radians) pointing most to open sea from (x,y), projected degrees."""
    angs = np.radians(np.arange(0, 360, 5))
    score = np.zeros(len(angs))
    for i, a in enumerate(angs):
        for r in (0.08, 0.18, 0.3, 0.45):
            if not pl.contains(Point(x + r * np.cos(a), y + r * np.sin(a))):
                score[i] += 1
    sm = np.convolve(np.r_[score[-6:], score, score[:6]], np.ones(13) / 13, 'same')[6:-6]
    return angs[np.argmax(sm)]


def stack_blocks(fig, x, ytop, ybot, blocks, size, inner=0.007):
    """Place big-number blocks top to bottom with equal measured gaps between ytop and ybot."""
    r = fig.canvas.get_renderer(); H = fig.bbox.height
    items = []
    for big, c, small in blocks:
        tb = fig.text(x, 0.5, big, fontproperties=DISP, fontsize=size, color=c, va='top')
        ts = fig.text(x, 0.5, small, family=SER, fontsize=12, color=FG, va='top', linespacing=1.3)
        items.append((tb, ts, tb.get_window_extent(r).height / H, ts.get_window_extent(r).height / H))
    total = sum(hb + inner + hs for _, _, hb, hs in items)
    gap = (ytop - ybot - total) / (len(items) - 1)
    y = ytop
    for tb, ts, hb, hs in items:
        tb.set_y(y); ts.set_y(y - hb - inner); y -= hb + inner + hs + gap
    return gap

CLEAR = 40 / 3000  # at least 40 px between the subtitle block and the right column

fig = plt.figure(figsize=(12, 15), dpi=200, facecolor=BG)

# ---------------- title
fig.text(0.04, 0.968, 'Did lighthouses stop the wrecks?', fontproperties=DISP, fontsize=46, color=FG, va='top')
dek = fig.text(0.04, 0.917, 'Britain and Ireland were ringed with new lights from 1776 to 1900. I counted the wrecks\n'
         'named at each rock, headland and sandbank in 193,562 shipwreck records, 1750 to 1913.',
         family=SER, fontsize=15, color=FG, va='top', linespacing=1.4)
DEKB = dek.get_window_extent(fig.canvas.get_renderer()).y0 / fig.bbox.height
HDR = DEKB - CLEAR

# ---------------- hero map
ax = fig.add_axes([0.0, 0.34, 0.60, 0.525], facecolor=BG)
ax.set_aspect('equal'); ax.axis('off')
x0, x1 = -10.9 * K, 2.3 * K; y0, y1 = 49.75, 60.95
ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
# faint sea vignette
ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, color=BG, zorder=0))
geoms = land.geoms if hasattr(land, 'geoms') else [land]
for gm in geoms:
    xs, ys = gm.exterior.xy
    if gm.area < 0.0004 or gm.bounds[1] < 49.5 * 1.0 and gm.bounds[2] > 3.0 * K:
        continue
    ax.fill(xs, ys, color=LAND, lw=0, zorder=1)
    ax.plot(xs, ys, color=EDGE, lw=0.5, zorder=2)

site_xy = {r.site: P(r.lon, r.lat) for r in S.itertuples()}
rng = np.random.default_rng(7)
dirs = {s: seaward(*xy) for s, xy in site_xy.items()}

# wreck sparks: one per entry, scattered seaward of the site it names
sx, sy = [], []
for ms in W.matched_sites.dropna():
    for s in ms.split(';'):
        if s not in site_xy:
            continue
        x, y = site_xy[s]; a = dirs[s] + rng.normal(0, 0.55); r = abs(rng.normal(0.05, 0.06)) + 0.02
        sx.append(x + r * np.cos(a)); sy.append(y + r * np.sin(a))
ax.scatter(sx, sy, s=0.9, c=SPARK, alpha=0.35, lw=0, zorder=3, rasterized=True)

# all other lighthouses: small dim points
ox, oy = P(LH.lon.values, LH.lat.values)
ax.scatter(ox, oy, s=3, c='#C9B27A', alpha=0.45, lw=0, zorder=4)

# beams for the 128 test lights
T = S[S.treated == True].copy()
T['chg'] = np.where((T.before10 + T.after10) == 0, 'none', np.where(T.rate_after10 < T.rate_before10, 'fell', 'rose'))
patches, cols = [], []
for r in T.itertuples():
    x, y = site_xy[r.site]; a = dirs[r.site]
    for L, w, al in ((0.6, 0.16, 0.06), (0.45, 0.10, 0.09), (0.32, 0.05, 0.13)):
        pts = [(x, y), (x + L * np.cos(a - w), y + L * np.sin(a - w)), (x + L * np.cos(a + w), y + L * np.sin(a + w))]
        ax.add_patch(MPoly(pts, closed=True, color='#FFE3A0', alpha=al, lw=0, zorder=5))
# glowing halos
for kind, col in (('none', '#B9A57A'), ('fell', GOLD), ('rose', CORAL)):
    q = T[T.chg == kind]; qx, qy = P(q.lon.values, q.lat.values)
    big = 1.0 if kind != 'none' else 0.55
    for s_, al in ((420, 0.05), (200, 0.09), (80, 0.18), (26, 0.5)):
        ax.scatter(qx, qy, s=s_ * big, c=col, alpha=al, lw=0, zorder=6)
    ax.scatter(qx, qy, s=7 * big, c='#FFF8E8', lw=0, zorder=7)
# never-lit hazards
q = S[S.group == 'control']; qx, qy = P(q.lon.values, q.lat.values)
ax.scatter(qx, qy, s=60, facecolors='none', edgecolors='#7FD1C2', lw=1.1, linestyle=(0, (2, 1.5)), zorder=7)

# labels for three story sites
def lab(site, txt, lon, lat, ha='left'):
    x, y = site_xy[site]
    ax.annotate(txt, xy=(x, y), xytext=(lon * K, lat), annotation_clip=False, family=MONO, fontsize=10, color=FG, ha=ha, va='center',
                arrowprops=dict(arrowstyle='-', color=MUT, lw=0.7), zorder=9)
lab('Gunfleet', 'Gunfleet, lit 1850\n171 before, 55 after', 0.75, 50.6)
lab('Souter (Whitburn)', 'Souter, lit 1871\n59 before, 32 after', 0.0, 55.75)
lab('Happisburgh', 'Happisburgh, lit 1791\n6 before, 19 after', 0.3, 53.95)

# legend
legend_items = [(GOLD, 'o', 'lit 1776 to 1900, fewer wrecks after (44)'),
                (CORAL, 'o', 'lit 1776 to 1900, more wrecks after (43)'),
                ('#7FD1C2', 'c', 'named hazard never lit (13)'),
                ('#C9B27A', '.', 'every other lighthouse'),
                (SPARK, '.', 'a wreck entry naming a site')]
lg = fig.add_axes([0.04, 0.285, 0.94, 0.05]); lg.axis('off'); lg.set_xlim(0, 1); lg.set_ylim(0, 1)
for i, (c_, m, t) in enumerate(legend_items):
    yy = 0.85 - (i % 3) * 0.35
    xo = 0.0 if i < 3 else 0.36
    lg.text(xo + 0.03, yy, t, family=MONO, fontsize=10.5, color=FG, va='center')
    if m == 'o':
        for s_, al in ((160, 0.1), (60, 0.25), (16, 0.8)):
            lg.scatter([xo + 0.01], [yy], s=s_, c=c_, alpha=al, lw=0)
    elif m == 'c':
        lg.scatter([xo + 0.01], [yy], s=60, facecolors='none', edgecolors=c_, lw=1.1, linestyle=(0, (2, 1.5)))
    else:
        lg.scatter([xo + 0.01], [yy], s=10, c=c_, lw=0)

# ---------------- event study inset (hero)
ev = pd.DataFrame(R['event'])
ea = fig.add_axes([0.665, HDR - 0.242, 0.305, 0.18], facecolor=BG)
for sp in ea.spines.values():
    sp.set_visible(False)
ea.axvspan(-5.5, -0.5, color=CORAL, alpha=0.10, lw=0)
ea.axvline(-0.5, color=GOLD, lw=1.2, ls=(0, (3, 2)))
ea.text(-0.1, 0.40, 'light\nlit', family=MONO, fontsize=10, color=GOLD, va='bottom')
ea.fill_between(ev.mid, ev.lo, ev.hi, color=GOLD, alpha=0.16, lw=0)
for lw_, al in ((11, 0.06), (6, 0.12), (2.6, 1)):
    ea.plot(ev.mid, ev.irr, color=GOLD, lw=lw_, alpha=al, solid_capstyle='round')
ea.scatter(ev.mid, ev.irr, s=34, c='#FFF8E8', zorder=5, lw=0)
ea.set_yscale('log'); ea.set_ylim(0.38, 1.75)
ea.set_yticks([0.5, 0.75, 1.0, 1.5]); ea.set_yticklabels(['0.5', '0.75', '1', '1.5'])
ea.minorticks_off()
ea.set_xticks([-18, -13, -8, -3, 2, 7, 12, 17.5]); ea.set_xticklabels(['-18', '-13', '-8', '-3', '2', '7', '12', '18'])
ea.tick_params(colors=MUT, labelsize=10, length=0)
for t in ea.get_xticklabels() + ea.get_yticklabels():
    t.set_family(MONO)
ea.grid(axis='y', color='#24324A', lw=0.6)
ea.set_xlabel('years from first lighting (5-year bins)', family=MONO, fontsize=10, color=MUT)
ea.text(-3, 1.1, 'the run-up', family=MONO, fontsize=10, color=CORAL, ha='center', va='bottom')
fig.text(0.655, HDR, 'THE WRECKS CAME FIRST', family=MONO, fontsize=11, color=GOLD, va='top')
fig.text(0.655, HDR - 0.017, 'Wrecks named at a site, relative to the five\nyears before its light (= 1), 95% intervals',
         family=SER, fontsize=11, color=FG, va='top', linespacing=1.3)

# ---------------- headline numbers
dn = R['did_donut']
nums = [('+37%', CORAL, 'wrecks named in the five years before a light,\nagainst the 15 years before that (95%: %d%% to %d%%).'
         .replace('%d%%', '{}%').format(round(dn['runup']['pct_lo'] * 100), round(dn['runup']['pct_hi'] * 100))),
        ('%d%%' % round(dn['post']['pct'] * 100), GOLD, 'after the light, against those quieter years.\n95% interval {}% to +{}%: not clearly\ndifferent from no change.'.format(
         round(dn['post']['pct_lo'] * 100), round(dn['post']['pct_hi'] * 100))),
        ('44 v 43', FG, 'test sites named less often after their\nlight, against those named more often.')]
stack_blocks(fig, 0.655, HDR - 0.242 - 0.05, 0.29, nums, 28, inner=0.006)

# ---------------- bottom row: coverage + three site stories
fig.text(0.04, 0.258, 'A RECORD THAT GROWS AND SHRINKS: WRECK ENTRIES PER YEAR', family=MONO, fontsize=11, color=MUT)
ca = fig.add_axes([0.065, 0.11, 0.42, 0.13], facecolor=BG)
cc = C[C.year.between(1750, 1913)]
ca.bar(cc.year, cc.entries, width=1, color='#3A5A8C', lw=0)
lit = T.first_lit.values
ca.scatter(lit, np.full(len(lit), -260) + rng.uniform(-90, 90, len(lit)), s=9, c=GOLD, lw=0, alpha=0.9, clip_on=False)
ca.set_ylim(-420, 4100); ca.set_xlim(1748, 1915)
for sp in ca.spines.values():
    sp.set_visible(False)
ca.tick_params(colors=MUT, labelsize=10, length=0)
ca.set_yticks([0, 2000, 4000]); ca.set_yticklabels(['0', '2,000', '4,000'])
ca.set_xticks([1750, 1800, 1850, 1900])
for t in ca.get_xticklabels() + ca.get_yticklabels():
    t.set_family(MONO)
ca.grid(axis='y', color='#24324A', lw=0.6); ca.set_axisbelow(True)
pk = R['coverage']['peak_year']; pv = R['coverage']['peak_entries']
ca.annotate('%d entries in %d' % (pv, pk), xy=(pk, pv), xytext=(1786, 3500), family=MONO, fontsize=10, color=FG,
            arrowprops=dict(arrowstyle='-', color=MUT, lw=0.7))
ca.text(1893, 1500, '1891: one\npage a year', family=MONO, fontsize=10, color=FG, ha='left')
ca.text(1752, -330, 'gold: a test light lit', family=MONO, fontsize=10, color=GOLD, va='center', ha='left', alpha=0)

fig.text(0.545, 0.258, 'THREE SITES, TEN YEARS EITHER SIDE', family=MONO, fontsize=11, color=MUT)
for i, (site, nm) in enumerate([('Gunfleet', 'Gunfleet'), ('Souter (Whitburn)', 'Souter'), ('Happisburgh', 'Happisburgh')]):
    a = fig.add_axes([0.545 + i * 0.148, 0.11, 0.13, 0.08], facecolor=BG)
    fy = int(S.set_index('site').loc[site, 'first_lit'])
    q = Y[(Y.site == site) & Y.year.between(fy - 10, fy + 10)]
    cl = np.where(q.year < fy, CORAL, np.where(q.year > fy, GOLD, FG))
    a.bar(q.year, q.mentions, width=0.8, color=cl, lw=0)
    a.axvline(fy, color=FG, lw=0.8, ls=(0, (2, 2)))
    b_ = q[q.year < fy].mentions.sum(); a_ = q[q.year > fy].mentions.sum()
    a.set_title('%s, %d\n%d before\n%d after' % (nm, fy, b_, a_), family=MONO, fontsize=10.5, color=FG, pad=4)
    for sp in a.spines.values():
        sp.set_visible(False)
    a.set_yticks([]); a.set_xticks([fy - 10, fy + 10]); a.set_xticklabels(['-10', '+10'])
    a.tick_params(colors=MUT, labelsize=10, length=0)
    for t in a.get_xticklabels():
        t.set_family(MONO)

# ---------------- footer
fig.text(0.04, 0.012,
         'Data: Wikipedia contributors, Lists of shipwrecks 1750 to 1913 (CC BY-SA 4.0), largely from Lloyd\'s List and newspapers;\n'
         'lists of lighthouses (CC BY-SA 4.0) and Wikidata (CC0); OS Open Names (OGL v3, contains OS data © Crown copyright 2026);\n'
         'coastline Natural Earth. Stacked Poisson event study, 128 test lights. Sparks sit near the site an entry names,\n'
         'not at the true wreck spot. Gold ticks under the bars: first lighting years. Counts wrecks, not voyages.\n'
         'Analysis and chart: Tristan Hotham, with Python and matplotlib.',
         family=MONO, fontsize=9, color=MUT, linespacing=1.45, va='bottom')

fig.savefig(os.path.join(HERE, 'did_lighthouses_work.png'), facecolor=BG, dpi=200)
print('ok')
