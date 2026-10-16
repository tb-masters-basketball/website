---
name: record-game
description: Read a photo of a Masters Basketball League score sheet (form MBL-SS6) into a draft game file for the entry page (/enter/), then save the draft and the photo and push them to main. Use for "/record-game <photo> [game_id]", or whenever someone hands over a score sheet photo to record.
argument-hint: <photo> [page-2 photo] [game_id]
---

# /record-game: a score sheet photo into a draft

The goal is `data/<season>/drafts/<game_id>.yml` (`status: draft`), a copy of the
paper sheet box for box, with a `review:` item on every box you are not sure
of, plus the photo at `data/<season>/sheets/<game_id>.jpg`, both pushed to main.
A person then opens the draft on the entry page, checks it against the paper
and saves it as final. So:

- **Never guess silently.** A flagged box costs the checker a glance; a wrong
  box that looks right goes on the site.
- **Copy the paper, don't correct it.** If the scorekeeper made a mistake
  (the Final box disagrees with the running score, say), write what is on the
  paper and flag the box that is most likely wrong.

The format and every check are in `docs/game-file-format.md` (its example
and "The fields" are what you need here). Team fouls and timeouts are on the
sheet but not in the file: ignore them.

## 0. What you're given

`$ARGUMENTS`: the photo, an optional second photo (page 2, only used when a
team passes 100 points or a player takes more than 10 free throws) and an
optional game id like `2026-12-03-g1`. A photo attached in the chat is a file
on disk (for example under `~/.claude/uploads/`): use that path. No photo:
ask for one.

**A practice sheet** (a game in a sample season, `data/sample-*`, such as the
practice games in `tests/fixtures/record-game/`): do steps 1 to 5 only, never
save or push, and score the draft instead:
`python scripts/record_game_eval.py score .record-game/WORK/draft.yml tests/fixtures/record-game/<game_id>/answer.yml`.

The helper needs numpy, Pillow and pypdfium2. If `prepare` fails to import
them: `pip install -r requirements.txt`.

## 1. Measure the photo

```
python scripts/record_game.py prepare PHOTO [PHOTO2] --out .record-game/WORK [--game GAME_ID]
```

WORK is the game id if you have it, else the date and time. The helper finds
the four black corner squares, straightens the page, works out the paper
(portrait or landscape, Letter or Legal, or landscape Tabloid), the page, and the game (from the
printed game id, teams and rosters), then measures the pen ink in every box
against that game's pre-printed sheet. It writes into `.record-game/WORK/`
(git-ignored):

| File | What it is |
|---|---|
| `report.md` | What the ink says box by box, the roster numbers, look-alike numbers, the photo's sharpness. **Read all of it.** |
| `start.yml` | The draft so far: the printed rows with player ids; Here, free throws, fouls, T and the quarter lines from the ink; `"?"` in every running-score box with writing; score boxes `null` (to read); a few review items |
| `crops/*.png` | One straightened image per section: header, each roster (and its two halves), each team's score boxes, Notes, the running score in pieces of 10-13 rows |
| `page1.jpg` | The whole straightened page, light evened out |

If it can't find the corner squares, or the report says the page matched
badly (under 0.5), look at the photo. A corner cut off, a curled or folded
sheet, a heavy shadow or a badly blurred photo: ask for a new one (the whole
sheet, flat, all four squares in view, no shadow across it, taken close
enough to fill the frame) rather than read a bad one.

The ink measures are dependable for **whether** a box has pen in it, and for
ticks, circles, foul boxes and lines (on test photos they were right on all
but about 1 box in 300, and flagged the rest); they don't read handwriting.

**Zoom**, by the box's path (the same paths the checks use, with the
game's team ids from `start.yml`):

```
python scripts/record_game.py zoom .record-game/WORK running.<team>.27 teams.<team>.players.3.ft.2 boxes.<team>.q4 notes header.scorekeeper
```

Each writes `crops/zoom-<path>.png`: a running-score box with the rows above
and below it (both teams), a circle with its neighbours, one score box with
its label. A zoom is larger, not sharper: if a box is still unclear after one
zoom, give your best reading and flag it; don't keep trying.

## 2. Confirm the game

View `crops/p1-header.png`. The printed Game ID must be the game in the
report, character for character, and the printed date must agree; the team
names are in the roster crops' Home and Away bars. The report's match scores
only rank the candidates: the printed Game ID decides. If it differs, or the
sheet is a blank one with the game written in by hand, find the game in
`data/<season>/schedule.csv` (date, home, away) and run `prepare` again with
`--game`. If you can't tell which game it is, ask; don't guess.

Read the Scorekeeper box ("First L."). If you can't read it, leave
`scorekeeper` out and add a review item at `scorekeeper`.

## 3. Read the sheet

### 3a. Start the second reading of the running score

The running score is most of the sheet, and the rules can't tell two of a
team's own numbers apart (46 written where 48 belongs passes every check).
So it is read twice, independently, like double entry. If you can start a
subagent (the Agent tool), start one now, in the background, with the model
`sonnet` (the most accurate reader in testing, and quick), and this prompt
(fill in WORK, and both team ids, names and roster numbers from the report):

> Read the running score of a basketball score sheet from images. In
> `.record-game/WORK/crops/` the files `p1-running-*.png` (and `p2-running-*`
> if any) are pieces of the running score: each row is one total (the
> printed number in the shaded middle column); the box left of it holds the
> HOME scorer's jersey number, the box right of it the AWAY scorer's, or is
> empty. Home is `<home id>` (<home name>), numbers <home roster numbers>;
> away is `<away id>` (<away name>), numbers <away roster numbers>. View every
> crop and read every box on its own. Write `.record-game/WORK/second.yml` as
> `running:` with `<home id>: {total: number, ...}` and `<away id>: {...}`,
> one line per team, only boxes with a number in them. Don't open any other
> file. Reply "done".

Then read everything yourself (3b-3e) without looking at `second.yml`. If you
can't start a subagent, skip it; step 5 says what to do instead.

### 3b. Rosters: `crops/p1-home-roster.png`, `crops/p1-away-roster.png`

`start.yml` already has each printed row's player id and number, and Here,
`ft`, `fouls` and `tech` from the ink. Check every row against the crop; the
full roster crop is usually enough (the `rows-01-06` and `rows-07-12` crops
are the same rows split in two).

- **Here**: a tick (or any mark) in the box.
- **Free throws**, in order from the left: a circle with ink in its middle
  (filled, or a heavy dot) is `M` (made); a circle slashed or crossed through
  is `X` (missed). An empty circle ends the string. Replace every `?` with `M`
  or `X`, or drop it if the circle is empty. Circles 11-20 are on page 2 and
  carry on the same string.
- **Fouls**: slashed foul boxes, 0-5. **T**: slashed T boxes, 0-2. If you
  count a different number from `start.yml`, look again; flag it if you
  still differ.
- **A row written in by hand** (`name: "?"`, `num: "?"`): read the number and
  the name. If they match a sub the report lists (or anyone in
  `data/<season>/players.yml`), use `player: <id>`, drop `name` and the row's
  review item. If not, keep `name: "First L."` (first name and initial only,
  never more) and change the item's note to "not in players.yml: add them,
  then give the id".
- **A review item for pen in the # or name box of a printed row**: a
  correction (a number crossed out and another written beside it). Use what
  is written now and keep the flag; if there's no correction, drop the item.

### 3c. Running score: `crops/p1-running-*.png` (and `p2-running-*` for page 2: 101 up, or 151 up on Tabloid)

Each row is one total: the home scorer's number on the left of the printed
total, the away scorer's on the right. Each team's column is its own
sequence (a row can have a number on both sides, one side, or neither: at
some point each team's score passed that total). `start.yml` has a `"?"` in every box
the ink says has writing. Replace each with the number you read. View every
crop up to the one holding the higher team's last total, and the one after.

- **Every number is a jersey number on that team's roster** (listed in the
  report). If what you read isn't one, zoom. Handwritten look-alikes: 1/7,
  3/8, 4/9, 5/6, 0/6/8, 2/7, 3/5, 1/4, and a digit doubled (3/33). If exactly
  one roster number fits what you see, use it. If two could, take the likelier
  and flag the box: `{at: running.<team>.27, note: "46 or 48? Looks like 46"}`.
- **Look-alike pairs.** The report lists pairs on each roster that are easy to
  mix up (46/48). Look twice at every box you read as one of them. If the
  report says the photo is soft (under 150 dpi), a look-alike box whose
  digits aren't plainly clear counts as unsure.
- **Free throws help.** Most 1-point jumps are free throws (league rules let
  a free throw be worth more, so not all), so a 1-point box usually belongs to
  a player with a filled circle; a player's made free throws can't outnumber
  their boxes. Use this to choose between two readings of a 1-point box.
- **When to flag:** a box is settled only when the handwriting itself shows
  it. If you chose by a clue instead (the free throws, the 1-2-3 jump rule,
  "only one roster number fits"), flag it and put the clue in the note: the
  checker can confirm it in a second with the paper.
- **Go row by row.** Don't carry a number down a column: each box is its own
  read.
- A box marked `"?"` that is empty when you look (blur, a smudge, a quarter
  line from the box above): remove it from `running`, with no flag. A box with
  writing that has no `"?"`: add it and flag it.
- Totals go up by 1, 2 or 3 at a time. A jump of 4 or more means a box was
  missed: look again around it.
- **Quarter lines**: `lines` come from the ink. Check each: a line under each
  team's last number of Q1, Q2, Q3 and Q4, four per team. Overtime has no line.

### 3d. Score boxes: `crops/p1-home-score.png`, `crops/p1-away-score.png`

Fill all six for each team (they're `null` in `start.yml`). Q1-Q4 are running
totals at the end of each quarter, not points in the quarter. Q4, OT and
Final have three cells (Q1-Q3 two); the digits sit to the right, so an empty
first cell means nothing. OT is the total after overtime, filled only when
the game was tied after Q4; otherwise `null`. If a box disagrees with its
line or the running score, still write what's on the paper and flag it.

### 3e. Notes: `crops/p1-notes.png`

Each entry is `{team: <team id>, num: <jersey>, q: <1-4 or OT>, kind:
flagrant, text: ...}` (`kind: note` for anything that isn't a flagrant foul).
"Home"/"Away" are the two team ids; "Q4" is `q: 4`. Keep the text short, as
written. Check the crop even if the report says Notes is empty.

## 4. Write the draft

Write `.record-game/WORK/draft.yml`: `start.yml` with everything filled in,
in the same layout and key order, `status: draft`. Write the whole file with
the Write tool: rows and maps stay one per line, such as
`<team>: {3: 48, 5: 25, 7: 4}`. Add `notes:` (a list, after `boxes:`) only if
Notes has entries. No `"?"` may be left. Review items go in `review:` at the
end; with none, leave `review` out.

Review notes name the box and the choice: "46 or 48? Looks like 46",
"a tick or a stray mark?", "filled or slashed?", "Final says 54, running
score ends at 52". Flag only what you're unsure of: not a box you read
clearly, and not a faint box you settled by looking. Keep the `start.yml`
items that still apply. Put the items that could change a score or a
player's points first (running score, score boxes, circles), then the rest.

## 5. Compare the two readings, then run the rules

When the subagent from 3a is done:

```
python scripts/record_game.py compare .record-game/WORK/draft.yml .record-game/WORK/second.yml
```

For every box listed, zoom and look again. If you now agree with one reading
for sure, use it; otherwise use the likelier and flag the box with both
readings ("46 or 48? two readings differ"). Taking the second reading's
number for a box you couldn't read yourself is choosing by a clue: flag it. No second reading (no subagent)?
Then go over every running-score crop a second time instead, comparing each
box with what you wrote.

Then the rules:

```
python scripts/record_game.py check .record-game/WORK/draft.yml
```

For every error, look at the box it names and the boxes around it. If your
draft differs from the paper, fix the draft. If the paper itself is wrong or
unclear, keep what's written and flag the box most likely to be wrong, saying
what the check found. Run the check again until every error has a review item
at or next to its box. Each review item also shows as a warning: that's
expected. Look at the other warnings and flag the real ones.

| Error | Where to look first |
|---|---|
| a jump that isn't 1, 2 or 3 | a missed or extra running-score box near that total |
| a number that's on no row | a misread digit: compare with the roster |
| a scorer not ticked Here | a missed tick, or a misread number |
| a Q box that disagrees with its line | the line (under which total?) or the box's digits |
| the Final box isn't the last running total | the last few running-score boxes, then the Final digits |
| more free throws made than scores | a circle read as filled, or a missed running-score box |

## 6. Save, commit and push

First make sure you're on main and up to date. If the working tree has other
changes, ask before touching it.

```
git switch main && git pull --ff-only
python scripts/record_game.py save .record-game/WORK/draft.yml PHOTO [PHOTO2]
```

`save` writes `data/<season>/drafts/<game_id>.yml` and the photo as
`data/<season>/sheets/<game_id>.jpg` (page 2: `<game_id>-2.jpg`), as a JPEG
of at most 3000 pixels with the phone's EXIF data (location) removed. It
stops if the game already has a final file or a draft: ask before using
`--force`. Then:

```
git add data/<season>/drafts/<game_id>.yml data/<season>/sheets/<game_id>*.jpg
git commit -m "Draft <game_id> from the score sheet photo (<n> boxes to check)"
git push origin main
```

If the push to main is refused, push to a branch `record-game/<game_id>`,
open a pull request, and say so. The photo is public once pushed (the repo is
public; the site never shows it).

## 7. Tell them

Short:

- the game: Home 63, Away 54 (OT if so), and the date
- each team's top scorers (`check` prints them)
- how many boxes are flagged, and the few that matter most
- if the report called the photo soft: a closer, sharper photo next time
  means far fewer flags
- the link to check it: `https://mastersbasketball.ca/enter/?game=<game_id>`
  (it opens the draft; compare each flagged box with the paper, fix, then
  "Save as final")
