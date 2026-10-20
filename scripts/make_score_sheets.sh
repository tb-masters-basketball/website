#!/usr/bin/env bash
# Score sheet PDFs for the season the site shows (the sample season while
# sample_data is on), into score-sheets/ so Jekyll publishes them at
# /score-sheets/. Run after scripts/build_stats.py and before `jekyll build`;
# the Schedule page only links a sheet that exists.
#   paper-sheets-<date>.pdf                   the league's paper sheet (MBL-PS1), every game day from today on
#   paper-sheet-blank.pdf                     the blank paper sheet
#   score-sheets-<date>-<orient>-<size>.pdf   MBL-SS6, every game day from today on, all five layouts
#   score-sheet-blank-<orient>-<size>.pdf     blank MBL-SS6 sheets, all five layouts
# The paper sheet is the Schedule page's main link; MBL-SS6 is under "Other layouts".
# "Today" is Thunder Bay's date. See scripts/scoresheet/README.md.
set -euo pipefail
cd "$(dirname "$0")/.."

season=$(python3 -c 'import json; print(json.load(open("_data/computed/active.json"))["season"])')
rm -rf score-sheets
TZ=America/Toronto python3 scripts/scoresheet/scoresheet.py --data "data/$season" \
  --from-today --all-layouts --allow-empty --out score-sheets
python3 scripts/scoresheet/scoresheet.py --blank --all-layouts --out score-sheets
TZ=America/Toronto python3 scripts/scoresheet/paper_sheet.py --data "data/$season" \
  --from-today --allow-empty --out score-sheets
python3 scripts/scoresheet/paper_sheet.py --blank --out score-sheets
echo "Score sheets for $season: $(ls score-sheets | wc -l) PDFs in score-sheets/"
