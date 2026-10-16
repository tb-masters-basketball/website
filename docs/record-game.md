# `/record-game`: reading a score sheet photo

`/record-game <photo> [game_id]` is a Claude Code command
([`.claude/skills/record-game/SKILL.md`](../.claude/skills/record-game/SKILL.md))
that turns a photo of a score sheet (form MBL-SS6) into a draft game file:
`data/<season>/drafts/<game_id>.yml`, with every box it isn't sure of
flagged for review, plus the photo in `data/<season>/sheets/`. It pushes
both to `main` and ends with the score, the top scorers, the number of flags
and a link that opens the draft on the entry page. A person checks the draft
against the paper there and saves it as final; a draft never reaches the
site by itself.

How a volunteer uses it, with or without Claude Code:
[stats-workflow.md](stats-workflow.md#read-a-photo-into-a-draft-record-game).
The free version (a prompt for claude.ai or any assistant):
[record-game-prompt.md](record-game-prompt.md).

## How it works

The sheet was built for this: four black corner squares, a fixed layout,
and the game id, teams and rosters printed before the game. So most of the
work is done by a script, and Claude only reads handwriting.

1. **Measure** (`scripts/record_game.py prepare`, no AI). It finds the four
   corner squares (in a photo taken at any angle, sideways or upside down;
   with one square hidden it works out the fourth), straightens the page,
   and works out the paper (portrait or landscape, Letter or Legal, or landscape
   Tabloid) and the
   page by matching each blank layout. It finds the game by matching every
   scheduled game's pre-printed sheet. Then it subtracts that pre-printed
   sheet from the photo, so only pen is left, and measures the pen in every
   box, using the box map `scoresheet.py --geometry` exports:
   - **Here ticks, foul and T boxes**: how much of the box is inked.
   - **Free-throw circles**: how much is inked, how much of the middle, and
     the mark's shape. A slash is long and thin, a filled circle round with
     a solid middle, so it tells made from missed even when a circle is only
     half filled.
   - **Quarter lines**: ink under a box deeper than under the rest of its
     column.
   - **Running score**: which boxes have writing, against this photo's own
     noise level (a blurred photo gets a higher bar).

   It writes a crop of each section, a report, and a draft to start from
   (`start.yml`): rows, ticks, circles, fouls and lines filled in, a `"?"`
   in every running-score box with writing, a review item wherever the ink
   was in between. It also reports the photo's sharpness (dpi) and the
   look-alike numbers on each roster (46/48, 5/55).
2. **Read** (Claude). The scorer numbers, the score boxes, the scorekeeper,
   Notes and any player written in by hand, section by section, checking each
   number against the team's roster, and checking the ink's ticks and circles
   against the crops.
3. **Read the running score twice.** A subagent (Sonnet) reads the running
   score independently while the main reading goes on;
   `record_game.py compare` lists every box where the two differ, and each is
   looked at again. This is for the one mistake the rules can't catch: a box
   read as another number on the same roster.
4. **Check** (`record_game.py check`, the site's rules). Every error gets a
   review item at the box most likely wrong. Copy the paper, never correct
   it: a wrong Final box is written as is, and flagged.
5. **Save**: the draft into `drafts/`, the photo into `sheets/` (at most 3000
   pixels, the phone's location data removed), commit, push.

## How well it works

It was first tested on made-up photos only: the four practice games
(`tests/fixtures/record-game/`) drawn onto the four layouts there were then
(Tabloid came later; see below) with
`scoresheet.py --fill`, then "photographed" by
`scripts/record_game_eval.py photos`: turned up to 7°, seen at an angle, on
a table, under a shadow, blurred, grainy, saved as JPEG, some sideways or
upside down. Two sets of 16 (the eval now makes 20, with Tabloid, so the same
`--seed` gives different photos from these):

- **Normal**: 145-245 dpi of paper, the handwriting drawn in a font with a
  little wobble.
- **Hard** (`--hard`): 100-160 dpi and blurrier, heavier shadows, and untidy
  writing: digits in six letter shapes, tilted and resized, four pen colours,
  circles half filled, slashes at odd angles.

Each draft was scored box by box against the answer key
(`record_game_eval.py score`). A box is **right**, **flagged** (wrong or
unsure, but a review item points at it, so the checker looks) or **wrong**
(wrong and not flagged: the one that matters).

**The measuring step** (script only, all 32 photos): it found the layout,
the page and the game on every photo, and every running-score box with
writing. The Here ticks, free throws, fouls, T boxes and quarter lines:

| Set | Boxes | Right | Flagged | Wrong |
|---|---|---|---|---|
| Normal | 1,512 | 100% | 0 | 0 |
| Hard | 1,512 | 99.0% | 15 | 0 |

**Reading** (the whole draft, every box), by model, one reader:

| Set | Model | Photos | Boxes | Wrong | Flagged | Tokens and time per photo |
|---|---|---|---|---|---|---|
| Normal | Sonnet | 4 | 752 | 0 | 0 | about 70k, 40 s |
| Normal | Opus | 4 | 752 | 0 | 0 | about 78k, 1 min |
| Normal | Haiku | 4 | 752 | 0 | 0 | about 100k, 2 min |
| Hard | Sonnet | 6 | 1,133 | 1 (a faint foul slash) | 5 | 73-98k, 1-2.5 min |
| Hard | Opus | 4 | 752 | 3 | 0 | 84-119k, 1-4 min |
| Hard | Haiku | 6 | 1,133 | 4 | 12 | 100-140k, 2-5 min |

The faint foul slash (on the blurriest photo, every reader trusted the ink's
"2 fouls") led to a lower foul threshold: the ink now flags that box, and
the measuring step makes no silent mistakes on either set. The other wrong
boxes were all one kind: on the blurriest photo
(about 120 dpi) Opus and Haiku swapped two Fort William numbers, 46 and 48,
in neighbouring boxes; both are on the roster and both players were ticked
Here, so no rule can catch it. Sonnet read them right. That led to the
second reading, the look-alike list and the sharpness check in the report.

**The whole skill** (second reading, look-alikes, the final instructions), on
the four hardest photos, with Opus and with Haiku as the main reader:

| Main reader | Photos | Boxes | Wrong | Flagged | Running score: wrong / flagged |
|---|---|---|---|---|---|
| Opus | 4 | 751 | 1 (the faint foul, since fixed) | 7 | 0 / 6 |
| Haiku | 4 | 751 | 2 (the faint foul; one running-score box) | 11 | 1 / 7 |

The 46/48 boxes that went wrong before are now flagged. Haiku's one miss
came from copying the second reading into boxes it couldn't read itself
without flagging them; the skill now says every box settled by anything but
the handwriting gets a flag. On the blurriest photo (about 120 dpi) both
readers raised 20-40 flags, which is right for that photo but a lot to
check: a closer photo is the real fix, and the report says so.

Costs: the measuring step takes 15-20 seconds and no tokens; the second
reading about 57k tokens and 20 seconds (in parallel with the main reading).

**What it means.** On clean photos every box came out right. On poor
photos nearly everything is still right, and what isn't is mostly flagged;
the checker's job shrinks from copying 190 boxes to looking at a handful.
Sonnet is the most accurate reader and the cheapest, so the second reading
uses it; the main reading uses whatever model the session runs.

**The first real photo** (the practice game `2026-12-17-g2`, copied by hand
onto a grayscale print and photographed on a table with a phone) needed four
fixes to the measuring step: a corner square right at the photo's edge, a
dark table edge mistaken for a corner, a grayscale print that sits a few
pixels off the template (each small box is now measured as placed and with a
few pixels' give, and flagged when the two disagree), and handwriting
crossing cell borders read as quarter lines (stricter line level). After
those, on that sheet: every tick, free throw, foul and T box right or
flagged; the running score 65 of 66 boxes right and the 66th flagged with
the right answer suggested; the second reading agreed box for box. The rest
of what differed from the answer key was the copy itself (no quarter lines
drawn, an OT box of 83, an empty Final, a foul short), each copied as
written and flagged. The made-up sets still come out with no silent
mistakes on ticks, circles, fouls and T boxes.

**Landscape Tabloid** (October 2026), the measuring step only, on the four
practice games drawn on Tabloid and "photographed" like the others: it found
the layout, the page and the game on all eight photos. Normal set: every
tick, circle, foul, T box and quarter line right. Hard set: 378 boxes, 31
flagged, 6 wrong without a flag, all on one photo at 105 dpi of paper (the
blurriest of the set). The other layouts on the same hard photos: 0 to 2
wrong each. A whole 11 x 17 sheet in one phone photo gets fewer pixels per
box than a Letter sheet, so for Tabloid a closer photo matters more; the
report's sharpness check flags anything under 150 dpi.

**13 roster rows** (October 2026, for a 13-player roster): the measuring step
again on 40 made-up photos (4 games x 5 layouts, normal and hard). Normal:
1,890 boxes, all right. Hard: 1,890 boxes, 143 flagged, 12 wrong without a
flag (0-2 per layout, 7 on Tabloid, mostly its blurriest photo): about the
same as with 12 rows.

**What it hasn't seen yet**: more real handwriting. The test writing is drawn
with fonts: messy, but not a tired scorekeeper's 4 that looks like a 9,
crossed-out numbers, arrows, or a box written between two rows. The ink
levels were tuned on these photos and may need retuning for real pens
(the levels are at the top of `scripts/record_game.py`). The practice
sheets copied by hand and photographed have since been tested (October
2026), with the fixes above. Next come real games' sheets: retune the ink
levels if real pens read differently.

## Testing it again

```sh
python scripts/record_game_eval.py photos           # 16 photos into tests/fixtures/record-game/synthetic/
python scripts/record_game_eval.py photos --hard    # the hard set, into synthetic-hard/
python scripts/record_game.py prepare <photo> --season sample-2026-27 --out .record-game/test
python scripts/record_game_eval.py score <draft.yml> tests/fixtures/record-game/<game_id>/answer.yml
python scripts/record_game_eval.py summary <folder of score_*.json>
```

`photos.json` beside the photos says which game and layout each one is
(the file names don't, so a reader can't tell). `tests/test_record_game.py`
runs the measuring step on one made-up photo in CI.
