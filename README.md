# Did Lighthouses Work?

When a lighthouse was first lit on a dangerous stretch of the British and Irish coast, did the wrecks recorded at that spot fall afterwards?

**Interactive version:** https://tristan-hotham.github.io/did-lighthouses-work/

This repository holds the interactive page, the derived wreck and lighthouse data, and the analysis code for the data study *Did Lighthouses Work?* by Dr Tristan Hotham (Independent researcher). It compares wreck mentions at each lighthouse site before and after its first lighting, using Wikipedia's lists of shipwrecks as the wreck record, with never-lit hazards and not-yet-lit lights as comparisons (a stacked Poisson event study).

## Files

- `index.html`: the interactive page (map with year slider, event study, site picker, record coverage, checks). Built by `code/export_page_data.py` from `code/page_template.html`; every number in its text is filled from `data/results.json`.
- `header.png`: social card.
- `data/lighthouses.csv`: the cleaned lighthouse table (Wikipedia lists plus Wikidata), with location, first-lit year, where that year came from (`year_source`), the site each light belongs to, and the site's first-lit year after hand corrections.
- `data/sites.csv`: one row per analysis site: group (light or never-lit comparison), kind, first-lit year and source, exclusion reason, notes and the name patterns used.
- `data/wreck_entries.csv`: every parsed wreck entry for 1750 to 1913 that names one of the sites: entry id, date (year, month and day where the page gives them), ship, flag, plain-text description and the site(s) matched. Unmatched entries enter the analysis only through the yearly totals in `site_year_counts.csv`; `code/run_all.sh` regenerates the full parsed table (about 35 MB) from the wikitext. Full text and sources are on Wikipedia.
- `data/site_year_counts.csv`: wreck mentions per site and year, with the year's total entries and home-waters entries.
- `data/coverage_by_year.csv`: entries parsed per year, 1700 to 1945.
- `data/alias_audit.csv`: each British alias checked against the OS Open Names gazetteer for same-named places elsewhere.
- `data/results.json`: all estimates (simple before and after, stacked difference-in-differences, event study, robustness checks, placebos, permutation test, per-site figures).
- `data/spot_checks.json`: results of the manual spot checks of parsing and lighthouse dates.
- `code/`: Python scripts. `aliases.py` is the hand-written list of sites and name patterns and is the place to audit the study. `run_all.sh` rebuilds everything from the raw inputs.

## How to rebuild

The raw inputs (not included, as they are large and available from their sources) are the wikitext of the "List of shipwrecks in ..." pages for 1700 to 1945, the wikitext of the six Wikipedia lists of lighthouses, and a Wikidata SPARQL export of lighthouses in the UK, Ireland, the Isle of Man, Jersey and Guernsey.

```
sh code/run_all.sh <folder with the raw inputs> <work folder> [osnames_gb.tsv]
```

Python 3 with pandas and numpy. The Poisson model with two sets of fixed effects is implemented in `code/ppml.py` and was checked against statsmodels.

## Main choices

- Study years 1750 to 1913. Test sites are lights first lit 1760 to 1900, excluding sites where an older light stood before the record begins or before the date in the sources.
- A wreck counts for a site when its description names the site (patterns in `aliases.py`), after removing sentences about voyages, towing and refloating, other ships named in the description, and places used only as a reference point more than 10 miles away.
- Each year has its own baseline in the models, to absorb changes in how many wrecks the record holds.
- The main estimate measures the years after lighting against years 6 to 20 before, because wreck mentions rise in the five years before a light is lit.

## Sources and licence

- Wreck records: Wikipedia contributors, "List of shipwrecks" pages, CC BY-SA 4.0. Largely compiled by Wikipedia editors from Lloyd's List and contemporary newspapers.
- Lighthouse lists: Wikipedia contributors, "List of lighthouses in ..." pages, CC BY-SA 4.0. Lighthouse data: Wikidata, CC0.
- Alias audit: OS Open Names, Ordnance Survey, Open Government Licence v3.0. Contains OS data © Crown copyright and database right 2026. The gazetteer itself is not redistributed.
- Base map on the page: tiles © Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community.

Because the wreck data are derived from Wikipedia, the derived data and the text of the page are released under CC BY-SA 4.0. Code is MIT (see `LICENSE`).

I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped prepare the analysis code. I reviewed and checked all text and results.
