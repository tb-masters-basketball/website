# Score sheets

`scoresheet.py` makes the printable league score sheet (form MBL-SS5) as a
fillable PDF. It comes in four layouts: portrait or landscape, Letter or Legal.
The scorekeeper can pick whichever they like. All four have the same parts, so
`/record-game` reads them the same way.

## What's on the sheet
- **Game details:** date, start time, court, game ID, scorekeeper.
- **Two team rosters** with 12 rows each. Each row has:
  - jersey number
  - a **Here** tick, which gives games played
  - name ("First L.")
  - 10 **free throw circles**: filled means made, slashed means missed
  - 5 **personal foul** boxes and 2 red **T** boxes for technicals
- **Under each roster:** team fouls for each half, timeouts, and the score by half and the final score.
- **Running score from 1 to 100:** the totals run down the middle, with the home scorer's number on the left and the away scorer's on the right.
- **Page 2, for printing on the back:** carries on in case it's needed, with the running score from 101 to 200 and free throws 11 to 20 for each player. Leave it out with `--front-only`.
- **Corner squares** so a photo can be straightened.

## How stats come from a sheet
| Stat | Source |
|---|---|
| Player points | Running score. The jump from the team's previous total to the next one is that basket's value: 1, 2 or 3. |
| FTM | Filled circles in the player's row. The running score's 1-point jumps must agree. |
| FTA | Filled circles plus slashed circles. |
| GP | **Here** ticks. |
| PF | Slashed foul boxes in the player's row (0 to 5). The website keeps them but doesn't show them. |
| Techs | Slashed red **T** boxes in the player's row (0 to 2). The website counts them for the whole season, playoffs included. |
| Checks | The last running total equals the Final box. Halftime totals equal the half boxes. Player points add up to the team score. |

## Commands
```
pip install reportlab pyyaml

# every game night in a season, one PDF per night (two pages per game, for double-sided printing)
python scripts/scoresheet/scoresheet.py --data data/2026-27 --out dist/score-sheets

# one night or one game
python scripts/scoresheet/scoresheet.py --data data/2026-27 --date 2026-12-03 --out dist/score-sheets
python scripts/scoresheet/scoresheet.py --data data/2026-27 --game 2026-12-03-g1 --out dist/score-sheets

# layout (default portrait letter), or all four at once
python scripts/scoresheet/scoresheet.py --data data/2026-27 --orient landscape --size legal --out ...
python scripts/scoresheet/scoresheet.py --data data/2026-27 --all-layouts --out ...

# blank sheets
python scripts/scoresheet/scoresheet.py --blank --all-layouts --out dist/score-sheets
```
Other options:
- `--from-today`: skips games dated before today.
- `--allow-empty`: if no games match (say, `--from-today` after the last game
  night), make nothing and exit without an error. The website's deploy uses it.
- `--front-only`: leaves out the page 2 continuation.
- `--per-game`: makes one file per game instead of one per night.
- `--include-subs`: also pre-prints subs.
- `--example`: adds sample handwriting, for previews only.

## Data it needs
It reads `teams.yml`, `players.yml` and `schedule.csv` from the season folder.
- **Jersey numbers:** players need a `number` field in `players.yml`.
  Without one, the # box prints empty and stays fillable.
- **Rosters:** regular players (`sub: false`) are pre-printed in jersey number
  order. Rows left over are blank for subs.
- **Schedule rows** without two real teams, such as byes or TBD playoff slots,
  are skipped, and so are rows whose `status` is `cancelled`.
- **No roster yet:** with an empty `players.yml`, the team names are still
  filled in and all 12 rows stay blank and fillable.
- **Court:** filled from a `court` column if the schedule has one. The league
  schedule has none (one gym, no courts), so the box prints empty.
- **Editing:** every name, number and detail stays an editable PDF field, so
  last-minute changes can be typed in before printing.

## Files
```
scoresheet.py           the generator
assets/fonts/*.ttf      Barlow and Barlow Condensed (SIL Open Font License 1.1)
assets/fonts/OFL.txt    the licence text, which must stay with the fonts
assets/masters-badge.png
example-data/           a small fake season and one sample game, for testing
```
