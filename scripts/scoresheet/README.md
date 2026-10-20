# Score sheets

`scoresheet.py` makes the printable league score sheet (form MBL-SS6) as a
fillable PDF. It comes in five layouts: portrait or landscape, Letter or Legal,
and landscape Tabloid (11 x 17).
The scorekeeper can pick whichever they like. All five have the same parts (Tabloid
adds a short How to mark under the rosters), so
a game file (and the entry page, `/enter/`, and `/record-game`)
reads them the same way.

## What's on the sheet
- **Game details:** date, start time, court, game ID, scorekeeper.
- **Two team rosters** with 13 rows each. Each row has:
  - jersey number
  - a **Here** tick, which gives games played
  - name ("First L.")
  - 10 **free throw circles**: filled means made, slashed means missed
  - 5 **personal foul** boxes and 2 red **T** boxes for technicals
- **Beside each team name:** 3 timeout circles.
- **Under each roster:** team fouls for each quarter (Q1 to Q4, 5 boxes each), then the score at the end of each quarter (the running total at that point), after overtime (OT), and the final score.
- **Notes** (page 1): for flagrant fouls (team, player number, quarter, what happened) and anything else worth knowing.
- **Running score from 1 to 100** (1 to 150 on Tabloid)**:** the totals run down the middle, with the home scorer's number on the left and the away scorer's on the right. A line under each team's last number marks the end of each quarter.
- **Page 2, for printing on the back:**
  - **How to mark**, the scorekeeper's instructions, in large type.
  - The running score carries on with one column fewer than page 1: 101-180 on portrait Letter, 151-275 on Tabloid, 101-175 on the others.
  - Free throws 11 to 20 for each player.
  - Leave the page out with `--front-only`.
- **Corner squares** so a photo can be straightened.

## How stats come from a sheet
| Stat | Source |
|---|---|
| Player points | Running score. The jump from the team's previous total to the next one is that score's value: 1, 2 or 3 (a basket or a free throw). |
| FTM | Filled circles in the player's row. Never the running score: a free throw can be worth 1, 2 or 3 points under league rules. More made free throws than the player's scores is flagged as a warning. |
| FTA | Filled circles plus slashed circles. |
| GP | **Here** ticks. |
| PF | Slashed foul boxes in the player's row (0 to 5). The website keeps them but doesn't show them. |
| Techs | Slashed red **T** boxes in the player's row (0 to 2). The website counts them for the whole season, playoffs included. |
| Quarter scores | The **Q1 to Q4** boxes: each team's running total at the end of each quarter (and **OT** after overtime). A quarter's points are the difference from the quarter before. |
| Flagrant fouls | **Notes** on page 1: team, player number and quarter for each one. A flagrant also counts as a personal foul, so it is in that player's foul boxes (and PF) too. |
| Checks | Every jump is 1, 2 or 3. Every scorer's number is on that team's roster and ticked Here. The last running total equals the Final box. Each quarter box equals the running total at that quarter's line. (Player points always add up to the team score, since both come from the running score.) The full list is in [`docs/game-file-format.md`](../../docs/game-file-format.md#the-checks). |

Team fouls and timeouts are for the game itself and aren't recorded on the
website. The timeout circles follow league rule 9: two for the first half
(H1), two for the second (H2) and one for overtime (OT), in `SPEC["timeouts"]`.

Form **MBL-SS6** (October 2026) replaced MBL-SS5, which had halves instead of
quarters and the instructions on page 1.

## Commands
```
pip install reportlab pyyaml

# every game day in a season, one PDF per day (two pages per game, for double-sided printing)
python scripts/scoresheet/scoresheet.py --data data/2026-27 --out dist/score-sheets

# one day or one game
python scripts/scoresheet/scoresheet.py --data data/2026-27 --date 2026-12-03 --out dist/score-sheets
python scripts/scoresheet/scoresheet.py --data data/2026-27 --game 2026-12-03-g1 --out dist/score-sheets

# layout (default portrait letter; tabloid is landscape only: --orient landscape --size tabloid), or all five at once
python scripts/scoresheet/scoresheet.py --data data/2026-27 --orient landscape --size legal --out ...
python scripts/scoresheet/scoresheet.py --data data/2026-27 --all-layouts --out ...

# blank sheets
python scripts/scoresheet/scoresheet.py --blank --all-layouts --out dist/score-sheets
```
Other options:
- `--from-today`: skips games dated before today.
- `--allow-empty`: if no games match (say, `--from-today` after the last game
  day), make nothing and exit without an error. The website's deploy uses it.
- `--front-only`: leaves out the page 2 continuation.
- `--per-game`: makes one file per game instead of one per day.
- `--include-subs`: also pre-prints subs.
- `--example`: adds made-up sample handwriting, for previews only.
- `--fill GAME.yml` (with `--data`): writes a game file onto its sheet as
  handwriting: Here ticks, circles, foul and T boxes, the running score, the
  quarter lines, the score boxes, Notes, and any sub written in on a blank
  row. Page 1 only (up to 100 points, 150 on Tabloid, and 10 free throws a player). It makes
  the practice sheets for `/record-game` (`scripts/make_practice_games.py`,
  into `tests/fixtures/record-game/`).
- `--prefill GAME.json`: one game's header and rosters from a JSON file instead
  of `--data`.
- `--spec OUT.json`: writes the spec (below) and stops.
- `--geometry OUT.json`: writes where every box is on each layout's two pages
  (points from the page's top-left corner: corner squares, header boxes, each
  roster row's number, Here, name, circles, foul and T boxes, the score boxes,
  Notes, every running-score box) and stops. `/record-game`'s helper
  (`scripts/record_game.py`) reads photos by it; it doesn't change the PDFs.

## Data it needs
It reads `teams.yml`, `players.yml` and `schedule.csv` from the season folder.
- **Jersey numbers:** players need a `number` field in `players.yml`.
  Without one, the # box prints empty and stays fillable.
- **Rosters:** regular players (`sub: false`) are pre-printed in jersey number
  order. Rows left over are blank for subs.
- **Schedule rows** without two real teams, such as byes or TBD playoff slots,
  are skipped, and so are rows whose `status` is `cancelled`.
- **No roster yet:** with an empty `players.yml`, the team names are still
  filled in and all 13 rows stay blank and fillable.
- **Court:** filled from a `court` column if the schedule has one. The league
  schedule has none (one gym, no courts), so the box prints empty.
- **Editing:** every name, number and detail stays an editable PDF field, so
  last-minute changes can be typed in before printing.

## The spec
Every structural number on the sheet lives in the `SPEC` dict at the top of
`scoresheet.py`, and the drawing code reads only that: the form id, roster
rows, free-throw circles per page, personal-foul and technical boxes,
timeouts, quarters and team-foul boxes, the score boxes (Q1-Q4, OT, Final),
points per page, running-score columns per layout and the page 2
continuation.

```
python scripts/scoresheet/scoresheet.py --spec scripts/scoresheet/spec.json
```
writes it as JSON, with each layout's running-score ranges added (page 1:
1-100, or 1-150 on Tabloid; page 2: 101-180 portrait Letter, 151-275 Tabloid, 101-175 the others).
`scripts/sheet_rules.py` reads `spec.json`, and a test fails if it's out of
date. The deploy also writes it to `enter/sheet-spec.json`, which the score
sheet entry page (`/enter/`) draws its whole sheet from, so the page follows a
change here with no edits. Change the printed sheet in `SPEC`, bump `form`,
regenerate `spec.json`, and update the game file format
(`docs/game-file-format.md`) and the rules (`sheet_rules.py`, then its JS port
`assets/js/sheet-rules.js`) if what they check changed.

## The league's paper sheet (MBL-PS1)

`paper_sheet.py` makes a second form, alongside MBL-SS6 and separate from it:
the league's own paper score sheet ("Feuille de pointage"), English only, with
one more running-score line (101-130) for each team. Letter portrait, one page
per game, one PDF per game day. It isn't linked from the site and isn't made by
the deploy.

Each team block: the team cell (the printed "Visitor" or "Home Team" over a
fillable team name), Colour, 16 player rows (name, No., a tick for played,
fouls 1-5, P1-P4, Total) with team fouls over P1+P2 and P3+P4, then Coach,
timeouts 1-5 and OT, Time Out, and the running score 1-36, 37-69, 70-100 and
101-130. The footer has the officials, the start and finish times and the coaches.
Black squares in the four corners (12 pt, 16 pt in from the edges, as on MBL-SS6)
let a reader straighten a photo of it.

```
python scripts/scoresheet/paper_sheet.py --data data/2026-27 --out dist/paper-sheets    # every game day
python scripts/scoresheet/paper_sheet.py --data data/2026-27 --date 2026-10-31 --out ...   # or --game, --from-today
python scripts/scoresheet/paper_sheet.py --blank --out dist/paper-sheets               # a blank fillable sheet
python scripts/scoresheet/paper_sheet.py --data data/2026-27 --game 2026-10-31-g1 --example --out ...   # a made-up game written on it (previews only)
python scripts/scoresheet/paper_sheet.py --spec scripts/scoresheet/paper-spec.json    # the spec (a test keeps it in step)
python scripts/scoresheet/paper_sheet.py --geometry OUT.json                          # where every box is
```

Pre-filled, each as an editable field: Game No. (the game of the day, from the
game id), Competition ("Masters"), Place (the game's gym, else the season's from
`seasons.yml`), Date, both team names (Visitor is the schedule's away team) and
each team's regular players ("First L." and number, in number order; the other
rows stay blank for subs). A long team name gets a smaller font. Its `SPEC` is
in PDF points with the origin at the top-left; the geometry uses the same
coordinates. Nothing reads these sheets yet: how the P1-P4 cells are marked is
still an open question (`docs/open-questions.md`). `--example` writes them the
way the old sheet is marked: every attempt in order (2 or 3 a basket, a dot a
made free throw worth 2, 1 a 1-point free throw, 0 a miss), the period's points
circled, each team's running total boxed after each period, and each total
reached struck through in the running score.

Both forms share `branding.py`: the fonts, the brand colours and the header.

## Files
```
scoresheet.py           the generator (MBL-SS6)
spec.json               SPEC as JSON (from --spec), read by scripts/sheet_rules.py
paper_sheet.py          the league's paper sheet (MBL-PS1)
paper-spec.json         its SPEC as JSON (from --spec)
branding.py             fonts, brand colours and the header, shared by both
assets/fonts/*.ttf      Barlow and Barlow Condensed (SIL Open Font License 1.1)
assets/fonts/OFL.txt    the licence text, which must stay with the fonts
assets/masters-badge.png
example-data/           a small fake season and one sample game, for testing
```
