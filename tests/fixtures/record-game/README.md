# Practice games for `/record-game`

Four made-up games from the sample season (`data/sample-2026-27/`), for
testing the command that reads a photo of a score sheet. Made by
`python scripts/make_practice_games.py` (same output every run; it replaces
this folder, so keep photos and notes elsewhere or re-add them after a rerun).

Each game's folder has:

| File | What it is |
|---|---|
| `answer.yml` | The game file: exactly what a perfect transcription gives (status `final`, passes every check) |
| `filled-<layout>.pdf` | The score sheet filled in "by hand" from `answer.yml` (blue pen), page 1 and the blank page 2 |
| `empty-<layout>.pdf` | The same sheet before the game: game id, date, time and the printed rosters, nothing written in |

To make test photos: print the filled sheet and the empty one, have someone
copy the filled sheet onto the empty one by hand (real handwriting, real
pens), then photograph the copy flat with all four corner squares in view.
Run `/record-game` on the photo and compare its draft with `answer.yml`.

| Game | Layout | Teams (home first) | Final | What it tests |
|---|---|---|---|---|
| `2026-12-17-g1` | portrait Letter | Fort William vs Westfort | 50-70 | An ordinary game: a player not ticked Here (#54 Paul L.), an and-one |
| `2026-12-17-g2` | portrait Letter | Current River vs Lakehead | 63-58 OT | Overtime: tied 54-54 after Q4, OT boxes filled in |
| `2027-01-07-g1` | landscape Letter | Lakehead vs Current River | 63-54 | A flagrant foul in Notes (Away #6, Q4) and a technical (Home #25) |
| `2027-01-07-g2` | landscape Letter | Westfort vs Fort William | 47-64 | A sub written in by hand on a blank row (#34 Carl M., a sub in `players.yml`) who scores |

Team fouls on the filled sheets are made up (the game file doesn't record
them). These games are not in `data/`, so they never reach the site.
`tests/test_sheet_rules.py` checks that every `answer.yml` still passes.
