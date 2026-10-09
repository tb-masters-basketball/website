#!/usr/bin/env bash
# Score sheet PDFs for the season the site shows (the sample season while
# sample_data is on), into score-sheets/ so Jekyll publishes them at
# /score-sheets/. Run after scripts/build_stats.py and before `jekyll build`;
# the Schedule page only links a sheet that exists.
#   score-sheets-<date>-<orient>-<size>.pdf   every game day from today on, all four layouts
#   score-sheet-blank-<orient>-<size>.pdf     blank sheets, all four layouts
# "Today" is Thunder Bay's date. See scripts/scoresheet/README.md.
set -euo pipefail
cd "$(dirname "$0")/.."

season=$(python3 -c 'import json; print(json.load(open("_data/computed/active.json"))["season"])')
rm -rf score-sheets
TZ=America/Toronto python3 scripts/scoresheet/scoresheet.py --data "data/$season" \
  --from-today --all-layouts --allow-empty --out score-sheets
python3 scripts/scoresheet/scoresheet.py --blank --all-layouts --out score-sheets
echo "Score sheets for $season: $(ls score-sheets | wc -l) PDFs in score-sheets/"
