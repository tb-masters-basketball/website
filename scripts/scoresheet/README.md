# Score sheets

`scoresheet.py` makes the printable league score sheet (form MBL-SS6) as a
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
- **Beside each team name:** 3 timeout circles.
- **Under each roster:** team fouls for each quarter (Q1 to Q4, 5 boxes each), then the score at the end of each quarter (the running total at that point), after overtime (OT), and the final score.
- **Notes** (page 1): for flagrant fouls (team, player number, quarter, what happened) and anything else worth knowing.
- **Running score from 1 to 100:** the totals run down the middle, with the home scorer's number on the left and the away scorer's on the right. A line under each team's last number marks the end of each quarter.
- **Page 2, for printing on the back:**
  - **How to mark**, the scorekeeper's instructions, in large type.
  - The running score carries on from 101 with one column fewer than page 1: to 180 on portrait Letter, to 175 on the other layouts.
  - Free throws 11 to 20 for each player.
  - Leave the page out with `--front-only`.
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
| Quarter scores | The **Q1 to Q4** boxes: each team's running total at the end of each quarter (and **OT** after overtime). A quarter's points are the difference from the quarter before. |
| Flagrant fouls | **Notes** on page 1: team, player number and quarter for each one. A flagrant also counts as a personal foul, so it is in that player's foul boxes (and PF) too. |
| Checks | The last running total equals the Final box. Each quarter box equals the running total at that quarter's line. Player points add up to the team score. |

Team fouls and timeouts are for the game itself and aren't recorded on the website.

Form **MBL-SS6** (October 2026) replaced MBL-SS5, which had halves instead of
quarters and the instructions on page 1.

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
