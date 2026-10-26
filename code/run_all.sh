#!/bin/sh
# Rebuild everything from the raw inputs.
# Usage (from the repository root): sh code/run_all.sh <inputs dir> <work dir> [osnames_gb.tsv]
set -e
IN=$(cd "${1:-/mnt/user-data/uploads/Downloads}" && pwd)
mkdir -p "${2:-work}"; WORK=$(cd "${2:-work}" && pwd)
GAZ=${3:-}
cd "$(dirname "$0")"
python3 parse_wrecks.py "$IN/hist_wrecks_wikitext.json" "$WORK" ../data
python3 build_lighthouses.py "$IN/hist_lighthouse_lists.json" "$IN/hist_lighthouses.json" "$WORK"
python3 count_sites.py "$WORK" ../data
if [ -n "$GAZ" ]; then python3 alias_audit.py "$GAZ" ../data > /dev/null; fi
python3 analysis.py ../data
python3 export_page_data.py ../data
