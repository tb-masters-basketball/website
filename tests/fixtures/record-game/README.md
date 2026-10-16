# Practice games for `/record-game`

Four made-up games from the sample season (`data/sample-2026-27/`), for
testing the command that reads a photo of a score sheet. Made by
`python scripts/make_practice_games.py` (same output every run; it rewrites
its own files and leaves anything else, such as photos, alone).

Each game's folder has:

| File | What it is |
|---|---|
| `answer.yml` | The game file: exactly what a perfect transcription gives (status `final`, passes every check) |
| `filled-<layout>.pdf` | The score sheet filled in "by hand" from `answer.yml` (blue pen), page 1 and the blank page 2 |
| `empty-<layout>.pdf` | The same sheet before the game: game id, date, time and the printed rosters, nothing written in |

To make test photos: print the filled sheet and the empty one, have someone
copy the filled sheet onto the empty one by hand (real handwriting, real
pens), then photograph the copy flat with all four corner squares in view. Save it
in the game's folder as `photo.jpg` (`photo-2.jpg` for page 2, if used).
Then run `/record-game` on the photo. These games are in the sample season,
so it stops before saving anything (no draft, no push) and scores its draft
against `answer.yml`:

    python scripts/record_game_eval.py score .record-game/<work>/draft.yml tests/fixtures/record-game/<game_id>/answer.yml

Every box comes out **right**, **flagged** (wrong or unsure, with a review
item pointing at it: fine, a person looks) or **wrong** (wrong and not
flagged: the failure that matters).

Made-up photos, without printing anything: `python scripts/record_game_eval.py
photos` draws each game on all five layouts and "photographs" it (turned, seen
at an angle, shadowed, blurred) into `synthetic/`; `--hard` makes a tougher set
in `synthetic-hard/` (untidy writing in several pens, half-filled circles,
smaller and blurrier photos). Both are git-ignored and the same every run.
[docs/record-game.md](../../../docs/record-game.md) has the results.

| Game | Layout | Teams (home first) | Final | What it tests |
|---|---|---|---|---|
| `2026-12-17-g1` | portrait Letter | Fort William vs Westfort | 50-70 | An ordinary game: a player not ticked Here (#54 Paul L.), an and-one |
| `2026-12-17-g2` | portrait Letter | Current River vs Lakehead | 63-58 OT | Overtime: tied 54-54 after Q4, OT boxes filled in |
| `2027-01-07-g1` | landscape Letter | Lakehead vs Current River | 63-54 | A flagrant foul in Notes (Away #6, Q4) and a technical (Home #25) |
| `2027-01-07-g2` | landscape Letter | Westfort vs Fort William | 47-64 | A sub written in by hand on a blank row (#34 Carl M., a sub in `players.yml`) who scores |

Team fouls on the filled sheets are made up (the game file doesn't record
them). These games are not in `data/`, so they never reach the site.
`tests/test_sheet_rules.py` checks that every `answer.yml` still passes.
