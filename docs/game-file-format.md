# The game file: a digital copy of the score sheet

Every game is one YAML file that mirrors the paper score sheet (form
**MBL-SS6**) box for box. Whoever types it up copies what's on the paper; the
site works out every number from it. The same file is what the score sheet
entry page (`/enter/`) reads and writes, so it is kept small enough to fit in
a link: under 3 KB for a typical game, and under 6 KB even for 100 points a side.

- **Finished games:** `data/<season>/games/<game_id>.yml`, `status: final`.
  The build reads these, and any error stops it.
- **Drafts:** `data/<season>/drafts/<game_id>.yml`, `status: draft`. The build
  never reads them; they're checked by the entry page and `/record-game`.
- **Photos:** `data/<season>/sheets/<game_id>.jpg`, kept in the repo, never on
  the site.

The rules live in one place, `scripts/sheet_rules.py` (ported line for line to
`assets/js/sheet-rules.js` for the entry page; change the Python first); the sheet's structure
(rows, circles, boxes, running-score pages) in `scripts/scoresheet/spec.json`,
written by `scoresheet.py --spec`.

## An example

This is `tests/fixtures/sheets/clean/sheet.yml`:

```yaml
game_id: 2026-10-17-g1
form: MBL-SS6
status: final            # draft | final
home: aa                 # team ids, as on the schedule
away: bb
scorekeeper: Pat S.      # the Scorekeeper box (optional)
teams:
  aa:
    players:             # the roster rows, top to bottom (players.0 is row 1)
      - {player: al-a, num: 4, here: true, ft: MXM, fouls: 2}
      - {player: amy-b, num: 10, here: true, ft: X}
      - {player: ann-c, num: 22, here: true, ft: M, fouls: 1}
      - {player: ari-d, num: 7, here: false}
  bb:
    players:
      - {player: bo-c, num: 5, here: true, ft: M, fouls: 3, tech: 1}
      - {player: bev-d, num: 11, here: true, ft: XM}
      - {player: bud-e, num: 30, here: true, ft: MX}
running:                 # the running score: total -> the scorer's jersey number
  aa: {2: 4, 4: 10, 5: 4, 7: 22, 10: 4, 12: 10, 13: 22, 15: 4, 17: 22, 19: 10, 20: 4, 22: 22}
  bb: {3: 5, 5: 11, 6: 30, 8: 5, 10: 11, 11: 5, 14: 30, 16: 11, 17: 11, 19: 5}
lines:                   # where each end-of-quarter line was drawn: [Q1, Q2, Q3, Q4]
  aa: [5, 12, 17, 22]
  bb: [5, 10, 16, 19]
boxes:                   # the score boxes under each roster, as written
  aa: {q1: 5, q2: 12, q3: 17, q4: 22, ot: null, final: 22}
  bb: {q1: 5, q2: 10, q3: 16, q4: 19, ot: null, final: 19}
notes:                   # the Notes box (page 1); flagrant fouls go here
  - {team: bb, num: 5, q: 3, kind: flagrant, text: elbow on a rebound}
review:                  # drafts only: boxes someone still has to check
  - {at: running.bb.14, note: "30 or 38?"}
checked_by: Lee M.       # who checked it against the paper (required when final)
```

(The example's `notes` and `review` are for illustration; the fixture has
neither, and a final file can't have `review`.)

## The fields

| Field | What it is |
|---|---|
| `game_id` | The schedule's id; must equal the file name and have a row in `schedule.csv` (which gives the date, type and teams) |
| `form` | The sheet's form, `MBL-SS6` |
| `status` | `final` (in `games/`) or `draft` (in `drafts/`) |
| `home`, `away` | Team ids, matching the schedule row |
| `scorekeeper` | Optional, as written |
| `teams.<team>.players` | The roster rows, in order (up to 12). See below |
| `running.<team>` | Every filled running-score box: `total: jersey number`. Page 2 just continues the totals (101 and up) |
| `lines.<team>` | The running total each end-of-quarter line was drawn under, Q1 to Q4 (0 if a team hadn't scored) |
| `boxes.<team>` | The score boxes: `q1`-`q4` (running totals at the end of each quarter), `ot` (the total after overtime, or `null`), `final` |
| `notes` | The Notes box: `{team, num, q, kind, text}`; `kind` is `flagrant` or `note`; `q` is 1-4 or `OT` |
| `review` | Drafts only: `{at, note}` for each box still in doubt |
| `checked_by` | Who checked the file against the paper; required when `final` |

**A roster row** is `{player, num, here, ft, fouls, tech}`:

| Key | What it is |
|---|---|
| `player` | The player id from `players.yml`. A sub written in by hand has `name: "Jim K."` instead until they're added (allowed in a draft only) |
| `num` | The jersey number in the # box (`"00"` in quotes). Two rows on a team can't share one |
| `here` | The Here tick: `true` or `false` |
| `ft` | The free-throw circles in order: `M` filled (made), `X` slashed (missed), e.g. `MMXM`. Circles 11-20 on page 2 carry on the same string. Leave it out for none |
| `fouls` | Slashed personal-foul boxes, 0-5 (flagrant fouls included). Leave out for 0 |
| `tech` | Slashed T boxes, 0-2. Leave out for 0 |

## How the numbers come from it

| Number | From |
|---|---|
| Points | The running score: the jump from a team's previous total to each box (1, 2 or 3) goes to the jersey number in it |
| FTM, FTA | The circles: FTM = `M`s, FTA = `M`s + `X`s. Never the running score: under league rules a free throw can be worth 1, 2 or 3, so any jump might be one |
| GP | `here: true` (rows not ticked get no line) |
| PF, techs | `fouls`, `tech` |
| Flagrant fouls | Notes entries with `kind: flagrant`, per team and number |
| Quarter scores | `boxes` q1-q4 (running totals); overtime when the final is above a tied Q4 |
| Final score | The last running total (the Final box must agree) |

## The checks

`scripts/sheet_rules.check(sheet, ctx)` returns `(game, problems)`. Each
problem is `{level, at, message}`; `at` is a dotted path to exactly one box,
the same path the entry page highlights:

| Path | The box |
|---|---|
| `running.lh.27` | Lakehead's running-score box at 27 |
| `teams.pa.players.3` | Port Arthur's row 4 (`.num`, `.player`, `.here`, `.fouls`, `.tech` for its parts) |
| `teams.pa.players.3.ft.2` | That row's third free-throw circle |
| `lines.pa.1` | Port Arthur's end-of-Q2 line |
| `boxes.lh.final` | Lakehead's Final box (`q1`-`q4`, `ot` likewise) |
| `notes.0` | The first entry in Notes |
| `game_id`, `status`, `checked_by`... | Header fields |

**Errors** (the build stops on any in `games/`):
- the header: `form`, `status` (and its folder), `game_id` (file name, schedule
  row, not cancelled, teams known), `home`/`away` against the schedule
- rows: a jersey number on two rows, an unknown or repeated player id, no
  player id in a final file, `here` not true/false, `ft` not `M`/`X` or more
  than 20 circles, `fouls` over 5, `tech` over 2, nobody ticked Here
- running score: a jump that isn't 1, 2 or 3, a total off the sheet (1-175),
  a number that's on no row of that team, a scorer not ticked Here
- quarters: a line under a total with no box, lines or boxes that go down, a
  Q box that disagrees with its line, the Final box not equal to the last
  running total, Q4 above the final, an OT box when there was no overtime (or
  none when there was), overtime without a tied Q4, a tied final
- notes: a flagrant for a number on no row; more flagrants than slashed foul
  boxes (a flagrant is also a personal foul)
- final files: `review` left in, no `checked_by`

**Warnings** (shown, never stop the build):
- more free throws made (filled circles) than the player has scores in the
  running score: possible, but worth a look
- a row with no player id yet (drafts)
- each `review` entry (drafts)

## A sub written in by hand

On paper a sub is a name and number on a blank row. In the file the row keeps
what's written, `{num: 31, name: "Jim K.", here: true, ...}`, with no `player`
id. A draft can stay that way (a warning). To finish it, either match the row
to an existing id, or add the player to `players.yml` first: id first name and
last initial (`jim-k`, or `jim-k2` if that's taken), `sub: true`, the team they
played for, and the number from the sheet. Then the row gets `player: jim-k`.

## Testing

`tests/fixtures/sheets/` holds one folder per case (`sheet.yml` and an
`expected.json` with the computed lines and every problem): a clean game, a
bad final, a free-throw mismatch, an and-one, an unknown jersey number, an
overtime game, a game that runs onto page 2, and a draft with a sub. The entry
page's JavaScript rules must give exactly the same results. Run
`python -m pytest` and `node --test "tests/js/*.test.mjs"` (both run in CI).

## The entry page

`/enter/` is an unlisted page (not in the nav, `noindex`) with a working copy of
the sheet. It draws everything from `enter/sheet-spec.json` (the deploy writes
it with `scoresheet.py --spec`) and the season from `enter/data/` (written by
`build_stats.py`: teams, players, schedule, and copies of the game files and
drafts). It lists drafts and published games from GitHub's API, or from those
copies when GitHub doesn't answer. Checks run as you type; every problem is
marked on its box and listed beside it. Saving as final sets `status: final`,
removes `review` and asks for `checked_by`; it's blocked while there are errors
or unchecked review flags, but a draft can always be saved. The file is
downloaded, copied, or opened in GitHub's new-file page with the contents filled
in (the link for a 100-point game is about 6,300 characters; past 8,000 the page
copies the file and opens an empty new file instead). Correcting a file that's
already on GitHub can't be prefilled, so the page lists the steps: copy, open
the editor, paste, commit. Work in progress stays in the browser
(`localStorage`, `mb-enter:<game_id>`); a photo opened beside the sheet is never
uploaded.
