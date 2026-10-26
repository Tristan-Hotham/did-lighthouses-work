"""Render header.png (1200 x 630 social card) with Playwright and Chromium.

Usage: python code/make_header.py <datadir> <out.png> [fonts dir]
The fonts dir, if given, holds Fraunces, Source Serif 4 and IBM Plex Mono TTFs (Google Fonts,
OFL). Without it the card loads them from Google Fonts.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright


def pct(v):
    s = f"{abs(v) * 100:.0f}%"
    return ("+" if v >= 0 else "−") + s


def html(R):
    run, post = R["did_donut"]["runup"]["pct"], R["did_donut"]["post"]["pct"]
    lo, hi = R["did_donut"]["post"]["pct_lo"], R["did_donut"]["post"]["pct_hi"]
    n = R["sample"]["n_treated"]
    entries = f'{R["coverage"]["study_entries"]:,}'
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,900&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400&display=swap">
<style>
body{{margin:0;width:1200px;height:630px;background:#F3EEE2;color:#1D1A15;font-family:"Source Serif 4",Georgia,serif;overflow:hidden}}
.c{{position:absolute;inset:0;padding:54px 64px;display:grid;grid-template-columns:1fr 330px;gap:20px}}
.k{{font:500 17px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:#6B6457;display:flex;gap:14px;align-items:center}}
.k b{{background:#D9480F;color:#fff;padding:7px 10px;font-weight:500}}
h1{{font:900 112px/.88 "Fraunces",Georgia,serif;letter-spacing:-.02em;margin:26px 0 0}} h1 em{{font-style:normal;color:#D9480F}}
.d{{font-size:27px;line-height:1.35;margin:26px 0 0;max-width:30ch}}
.s{{position:absolute;left:64px;right:64px;bottom:46px;border-top:6px double #1D1A15;padding-top:18px;display:flex;gap:44px;font:400 17px/1.3 "IBM Plex Mono",monospace;color:#6B6457}}
.s b{{display:block;font:900 44px/1 "Fraunces",Georgia,serif;color:#1D1A15;margin-bottom:6px}} .s b.h{{color:#D9480F}}
svg{{width:330px;height:330px;margin-top:6px}}
</style></head><body><div class="c"><div>
<div class="k"><b>Data study</b><span>History × data</span><span>Britain and Ireland</span></div>
<h1>Did <em>lighthouses</em> work?</h1>
<p class="d">{entries} recorded wrecks, 1750 to 1913, and what changed at {n} spots once the light came on.</p></div>
<svg viewBox="-100 -100 200 200"><g transform="translate(0,-52)"><path d="M0 0 L96 -24 L96 24 Z" fill="#A87400" opacity=".38" transform="rotate(-12)"/><path d="M0 0 L-96 -22 L-96 22 Z" fill="#A87400" opacity=".2" transform="rotate(-12)"/></g>
<path d="M-70 92 Q-40 60 0 66 Q40 60 70 92 Z" fill="#1D1A15" opacity=".85"/><path d="M-20 70 L-13 -40 L13 -40 L20 70 Z" fill="#FBF8F1" stroke="#1D1A15" stroke-width="3"/>
<path d="M-18 40 L18 30 L19 42 L-19 52 Z" fill="#D9480F"/><path d="M-16 8 L16 -2 L17 10 L-17 20 Z" fill="#D9480F"/>
<rect x="-17" y="-62" width="34" height="22" fill="#1D1A15"/><circle cx="0" cy="-52" r="8" fill="#A87400"/><path d="M-20 -62 L0 -80 L20 -62 Z" fill="#D9480F"/>
<path d="M-86 92 Q-60 82 -34 92 T18 92 T70 92 T96 92" fill="none" stroke="#2763A8" stroke-width="3" opacity=".7"/></svg>
</div>
<div class="s"><div><b class="h">{pct(run)}</b>wrecks named at a site in the<br>5 years before its first light</div>
<div><b>{pct(post)}</b>after the light, against earlier years<br>(95% interval {pct(lo)} to {pct(hi)})</div>
<div style="margin-left:auto;align-self:end;text-align:right">Dr Tristan Hotham<br>Independent researcher</div></div>
</body></html>"""


def main(datadir, out, fonts=None):
    R = json.load(open(f"{datadir}/results.json"))
    page = pathlib.Path(out).with_suffix(".card.html")
    page.write_text(html(R), encoding="utf-8")
    F = {"fraunces": "Fraunces[SOFT,WONK,opsz,wght].ttf", "ss4": "SourceSerif4[opsz,wght].ttf",
         "pm4": "IBMPlexMono-Regular.ttf", "pm5": "IBMPlexMono-Medium.ttf"}
    css = ('@font-face{font-family:"Fraunces";src:url(https://fonts.gstatic.com/x/fraunces);font-weight:100 900}'
           '@font-face{font-family:"Source Serif 4";src:url(https://fonts.gstatic.com/x/ss4);font-weight:200 900}'
           '@font-face{font-family:"IBM Plex Mono";src:url(https://fonts.gstatic.com/x/pm4);font-weight:400}'
           '@font-face{font-family:"IBM Plex Mono";src:url(https://fonts.gstatic.com/x/pm5);font-weight:500}')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        if fonts:
            def route(r):
                u = r.request.url
                if "fonts.googleapis.com" in u:
                    return r.fulfill(body=css, content_type="text/css")
                if "fonts.gstatic.com/x/" in u:
                    return r.fulfill(body=(pathlib.Path(fonts) / F[u.rsplit("/", 1)[1]]).read_bytes(), content_type="font/ttf")
                return r.continue_()
            pg.route("**/*", route)
        pg.goto(page.resolve().as_uri())
        pg.wait_for_timeout(800)
        pg.screenshot(path=out)
        b.close()
    page.unlink()


if __name__ == "__main__":
    main(*sys.argv[1:])
