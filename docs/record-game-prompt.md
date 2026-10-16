# Reading a score sheet with any chat assistant (the free version of `/record-game`)

`/record-game` (`.claude/skills/record-game/SKILL.md`) needs Claude Code and
this repository: a helper straightens the photo and measures the ink in every
box before Claude reads it. This page is the version anyone can use with the
free claude.ai, or another assistant that reads images: copy the prompt below,
attach the photo, and save the file it writes as a file the entry page opens.

It's less sure-footed than `/record-game`. Nothing measures the ink, so the
assistant has to see every tick and circle itself, and you should expect more
boxes to check. So the prompt makes it work one section at a time, show you
where it found each section, and flag everything it isn't sure of. The entry
page's checks catch most mistakes, and the paper catches the rest.

## How to use it

The entry page (`/enter/`) has a **Copy the prompt** button ("Read a photo
with an AI chat"), so you don't need this page to get it. The deploy copies
the prompt from this page into `enter/data/record-game-prompt.txt`
(`build_stats.py`), so editing it here is enough.

It works best with **ChatGPT** and **Claude** (claude.ai). Gemini, tried so
far, doesn't read the sheet well.

1. **Photograph the sheet.** Lay it flat and take the whole page, with all four
   black corner squares in view and no shadow across it. Then take close-ups of
   the two rosters and the running score (the numbered columns). A close-up
   reads far better than a corner of one big photo.
2. **Let the assistant run code if it can.** On claude.ai, turn on code
   execution (in Settings, under the features or capabilities section;
   the name changes now and then). ChatGPT does this by itself. With code,
   the assistant straightens the photo, enlarges each section before reading
   it, and draws the check picture (step 3 of the prompt). Without code it
   still works, but it reads from the raw photo and describes where it found
   each section in words.
3. **Send it.** Open a new chat, attach the photos, paste the prompt (the
   button on the entry page, or copy it from below) and send it.
4. **Look at the check picture first.** It shows a green box round everything
   it read as HOME, orange round AWAY, blue round the header and Notes, and red
   round every box it isn't sure of. A green box on the away roster, or a column
   left out, means the reading is wrong from the start. Tell it what it got
   wrong ("the green box is on the away roster") and ask it to start again.
5. **Copy the file.** The answer ends with a game file in a code block. Copy
   the code block (or the whole answer: the page finds the block).
6. **Open it on the entry page.** Go to `https://mastersbasketball.ca/enter/`,
   paste it into the box on "Load a score sheet YML" and press **Open the
   pasted file**. (Or save it as a plain-text file named after the game, such
   as `2026-12-03-g1.yml`, and drop it on the same card.) The page turns team names
   into the site's team ids and matches each player's name and number to the
   player list (`players.yml`); check the matches it reports. Go through every
   flagged box with the paper (the red boxes on the check picture are the same
   ones), fix what the checks show, and save it as a draft or final, as in
   [stats-workflow.md](stats-workflow.md).

The prompt doesn't change between games or seasons: team names, player names
and the game id are all read off the sheet.

## The prompt

Copy everything between the lines.

---

You are typing up a basketball score sheet (Masters Basketball League, form
MBL-SS6) from the attached photo(s) into a YAML game file. The numbers go on
the league's website as players' points and free throws.

**Errors are not okay.** A wrong number that looks right goes on the website
and nobody catches it. A flagged box costs the checker a glance at the paper.
So:
- Never guess silently. If you are not sure of a box, write your best reading
  **and** flag it in `review` with a short, specific note ("4 or 9? Looks like
  4"). Flag every box you settled by reasoning (the roster, the arithmetic)
  rather than by seeing the handwriting clearly.
- Never fill a box from what "should" be there. Copy what is written, even when
  the scorekeeper made a mistake (a Final box that doesn't match), and flag the
  mistake instead of fixing it.
- Never skip a section because it looks empty. Look, and say it's empty.
- If the photo is too blurry, dark or cut off to read a section, say so and
  flag it rather than reading what you can't see.

Work through the steps below **in order, one section at a time**. Finish each
step before starting the next, and don't let what you read in one section
change what you read in another (the cross-checks come at the end).

### Step 1. Find the page and turn it the right way up

The sheet has a **black square in each of its four corners**. Find all four.
Turn the page in your mind (or in code) so the title "MASTERS BASKETBALL
LEAGUE" with the round logo is at the **top left**, reading normally.

Then say which layout it is (it's printed under the title, such as "Form
MBL-SS6 · Portrait Letter"):
- **Portrait** (taller than wide) or **Landscape** (wider than tall).
- **Letter**, **Legal** (longer) or **Tabloid** (11 x 17, landscape only, the
  biggest: its running score on page 1 goes to 150, and it has a short "How to
  mark" box under the rosters).
- **Page 1** has the rosters. **Page 2** (the back, "How to mark" in large
  type) has the running score from 101 (from 151 on Tabloid) and free-throw
  circles 11 to 20. Page 2 matters only in a game where a team scored over 100
  (150 on Tabloid) or a player took more than 10 free throws.

If a corner square is out of the photo, or the paper is folded or curled,
say so: positions below may be off.

### Step 2. Make it easier to read (only if you can run code)

If you can run code (Python with Pillow, OpenCV or similar), do this before
reading. If you can't, skip to step 3 and read from the photo.

1. **Straighten.** Find the four black corner squares and warp the page so the
   outer corners of the squares become the corners of a flat rectangle, with
   this width-to-height ratio: Portrait Letter 0.763, Portrait Legal 0.594,
   Landscape Letter 1.310, Landscape Legal 1.683, Landscape Tabloid 1.568.
2. **Crop each section** from the straightened page using the positions in the
   table below (percent of the rectangle's width across, and of its height
   down). Add a margin of 1-2% all round.
3. **Enlarge each crop 2-3 times** (Lanczos or bicubic), turn it to grayscale
   and stretch the contrast (autocontrast). A light sharpen is fine.
4. **Don't threshold to pure black and white, and don't denoise heavily:**
   that erases faint pencil and turns smudges into marks.
5. **Read from the crops** if you can look at images your code makes. Cut the
   running score into pieces of about 10 rows so each piece is big. If you can't
   see your own output, read from the photo and use the crops only for the
   check picture.

| Section (page 1) | Portrait Letter | Portrait Legal | Landscape Letter | Landscape Legal | Landscape Tabloid |
|---|---|---|---|---|---|
| Header (Date ... Scorekeeper) | 57-97 across, 1-9 down | 57-97, 1-7 | 67-98, 2-11 | 74-98, 2-11 | 79-99, 1-9 |
| HOME roster | 3-49, 9-47 | 3-49, 7-43 | 2-40, 12-54 | 2-33, 12-54 | 1-27, 9-42 |
| HOME score boxes | 3-49, 43-47 | 3-49, 39-43 | 2-40, 49-54 | 2-33, 49-54 | 1-27, 37-42 |
| AWAY roster | 51-97, 9-47 | 51-97, 7-43 | 2-40, 55-97 | 2-33, 55-97 | 1-27, 42-74 |
| AWAY score boxes | 51-97, 43-47 | 51-97, 39-43 | 2-40, 92-97 | 2-33, 92-97 | 1-27, 70-74 |
| Notes | 3-97, 47-55 | 3-97, 43-49 | 41-98, 88-97 | 34-98, 88-97 | 28-99, 91-98 |
| Running score (all columns) | 3-97, 55-98 | 3-97, 49-99 | 41-98, 12-88 | 34-98, 12-88 | 28-99, 9-91 |
| Running score columns, across | 3-21, 22-40, 41-59, 60-78, 79-97 | 3-26, 27-50, 50-73, 74-97 | 41-55, 55-70, 70-84, 84-98 | 34-50, 50-66, 66-82, 82-98 | 28-40, 39-52, 51-63, 63-75, 75-87, 87-99 |

(Each roster's score boxes are its bottom strip. In portrait the two rosters
sit side by side; in landscape HOME is above AWAY, both on the left, with the
running score on the right. On Tabloid the box under the two rosters is "How
to mark": instructions, not part of the game.)

### Step 3. Map the sections and draw the check picture

Before reading anything, find every section and box it in its colour:

| Colour | Sections |
|---|---|
| **Green** | HOME roster, HOME score boxes, and the HOME # strip of every running-score column |
| **Orange** | AWAY roster, AWAY score boxes, and the AWAY # strip of every running-score column |
| **Blue** | The header, and Notes |
| **Red** | Added as you go: a small box round every single box you flag in `review` |

How to tell them apart: each roster starts with a dark bar with **HOME** or
**AWAY** in large white letters at its left end and the team name in the TEAM
box. In the running score, every column has a dark bar on top reading
**HOME # | PTS | AWAY #**: the left strip is home, the right strip is away.

- **If you can run code:** draw the boxes on the straightened page (lines 3-4
  pixels thick, a letter label at each box's corner: H, A, Header, Notes) and
  show the picture at the start of your answer. After reading, add the red
  boxes and show it again at the end.
- **If you can't:** write one line per section saying where it is in the photo
  ("HOME roster: top left, about the top half of the left side"), and in the
  end list every flagged box by section, row and column.

### Step 4. Header (blue)

Five boxes at the top right: **Date**, **Start time**, **Court**, **Game ID**
(like `2026-12-03-g1`: the date and the game number) and **Scorekeeper**.
Most are printed; some may be handwritten.

- Copy the Game ID exactly. If it's blank or unreadable, flag `game_id`.
- The scorekeeper as "First L." (first name and last initial only). If the
  sheet has a full surname, shorten it and flag `scorekeeper` with what was
  written. Blank: leave it out and flag it.

### Step 5. HOME roster (green)

**Find it:** the block that starts with the dark **HOME** bar (top left in
both layouts). Write down the team name from its TEAM box: that is `home:`.
Ignore the TIMEOUTS circles in the bar.

**The columns, left to right:**

| `#` | `HERE` | `PLAYER` | `FREE THROWS` | `FOULS · T` |
|---|---|---|---|---|
| jersey number | a small square tick box | "First L." | 10 small circles, in two groups of 5 | 5 small boxes with tiny faint printed digits 1-5, then 2 **red** boxes marked T |

Up to 12 rows. Below them are a **TEAM FOULS** row (ignore it) and the score
boxes (step 7).

**Read one row at a time, top to bottom.** Finish a row (all its columns)
before moving on. For each row:
- `num`: the jersey number. `name`: as printed or handwritten, "First L."
  (never more than the last initial). A row written in by hand is a sub: read
  it the same way.
- `here`: `true` if the Here box has a tick, cross or any mark; else `false`.
- `ft`: the circles from the left, one letter each. **Filled in** (or a
  heavy dot in the middle) = `M` (made). **Slashed or crossed through**
  (a line across, the middle mostly white) = `X` (missed). Stop at the first
  empty circle (they're used left to right). Leave `ft` out if none is
  marked. The two groups of 5 are one string: circle 6 follows circle 5.
- `fouls`: how many of the 5 foul boxes have a slash or cross (0-5). The tiny
  printed digits are not marks: look for pen.
- `tech`: how many of the 2 red T boxes have a slash or cross (0-2).
- Leave out `fouls`/`tech` when 0. Keep printed rows of players who didn't
  play (`here: false`). Leave out rows with nothing in them at all.
- Half-filled circle, faint slash, a mark between two boxes, a crossed-out
  number: write your best reading and flag that box.

### Step 6. AWAY roster (orange)

**Find it:** the block that starts with the dark **AWAY** bar (top right in
portrait, lower left in landscape). The team name in its TEAM box is `away:`.
Read it exactly as step 5, as a fresh section. Don't carry anything over from
the home roster: same-looking rows on the two rosters are different players.

### Step 7. HOME score boxes (green)

**Find them:** the bottom strip of the HOME roster, labelled **SCORE AT END
OF**, under the TEAM FOULS row (the team fouls row has rows of small
empty-looking squares in groups of 5; that is not the score).

Six boxes: **Q1, Q2, Q3** (two digit cells each), **Q4, OT, Final** (three
digit cells each, since a score can pass 99). One digit per cell; read the
cells of a box together as one number ("6", "3" = 63). An empty first cell
means nothing ("", "5", "4" = 54).

- They are the team's **running total** at the end of each quarter, not the
  points in the quarter, so they go up: Q1 ≤ Q2 ≤ Q3 ≤ Q4.
- `ot` is the total after overtime; `null` if empty (no overtime).
- `final` as written; flag it if empty.
- Copy what's written even if it can't be right, and flag it.

### Step 8. AWAY score boxes (orange)

The bottom strip of the AWAY roster. Read exactly as step 7.

### Step 9. Notes (blue)

**Find it:** the wide box headed **NOTES · FLAGRANT FOULS: TEAM, PLAYER #,
QUARTER, WHAT HAPPENED** (under the rosters in portrait; bottom right in
landscape). Often empty: look anyway and say so.

Each entry: `team` (`home` or `away`), `num` (jersey), `q` (1-4, or `OT`),
`kind: flagrant` for a flagrant foul (else `kind: note`) and `text`, short,
as written. Flag anything you can't read.

### Step 10. The running score

**What it is.** Every time a team scores, the scorekeeper finds that team's
new total and writes the **scorer's jersey number** next to it, on that team's
side. It is the only record of who scored, so every box matters.

**How it looks.** Several tall columns side by side (5 columns of 20 rows on
Portrait Letter; 6 columns of 25 rows on Landscape Tabloid; 4 columns of 25
rows on the other layouts). Each column has a
dark bar on top reading **HOME # | PTS | AWAY #** and is three strips wide:

```
 HOME # |  PTS  | AWAY #
--------+-------+--------
        |   1   |
   23   |   2   |          <- home went to 2: #23 scored 2 points
        |   3   |   7      <- away went to 3: #7 scored 3 points
   11   |   4   |          <- home went to 4: #11 scored 2 points
        |   5   |
   23   |   6   |   12     <- home to 6 (#23, 2 points); away to 6 (#12, 3 points)
```

- **PTS** (middle, shaded): **printed** numbers, 1, 2, 3 ... 100 (150 on
  Tabloid), going down
  the first column, then on down the second, and so on. They are not
  handwriting and not jersey numbers; they are the totals.
- **HOME #** (left strip): the home scorer's number, beside the home team's
  new total.
- **AWAY #** (right strip): the away scorer's number, beside the away team's
  new total.
- Each side is its own sequence. A row can have a number on the left, the
  right, both, or neither. Most boxes are empty: a 2-point basket skips one
  total, a 3-pointer skips two. The points for a box are its total minus the
  team's previous total with a number (1, 2 or 3).
- **Quarter lines:** at the end of each quarter the scorekeeper draws a line
  under that team's last number (just across that team's strip, or across
  the row). Four per team, Q1 to Q4; none for overtime.

**10a. HOME pass (green).** Read **only the HOME # strips**: column 1 top to
bottom, then column 2 top to bottom, and so on, until two empty columns or the
end. For every box with writing, write `total: number` (the printed total
beside it, then the number in the box). Look at every box on its own; don't
carry a number down from the box above. Then note the totals with a quarter
line under them.

**10b. AWAY pass (orange).** Start again from the top of column 1 and read
**only the AWAY # strips**, the same way. Then its quarter lines.

**For each number you write down, check it:**
- **Is it on that team's roster** (step 5 or 6)? If not, look again: written
  digits are easy to mix up (1/7, 3/8, 4/9, 5/6, 0/6/8, 2/7, 3/5, 1/4, a
  digit doubled: 3/33). If one roster number fits what you see, use it and
  flag the box ("looks like 9; 4 is on the roster: 4?"). If two fit, use the
  likelier and flag it ("46 or 48? Looks like 46").
- **Is the jump 1, 2 or 3** from the team's previous number? A jump of 4 or
  more means you missed a box: look in between, in that team's strip.
- **Is it in the right strip?** A number written on the line between two
  rows, or across the PTS strip, gets flagged with what it seems to be.
- **Crossed out** with another number beside it: use the new one and flag it.
- A number you settled by any of these checks rather than by seeing it is
  flagged, with the clue in the note.

Before step 11, write the running score as a table: one line per total that
has a number on either side, `total | home # | away #`, in order. The checker
reads it against the paper.

### Step 11. Page 2 (only if attached)

The running score carries on from 101, or 151 on Tabloid (read it the same way, home pass then
away pass). Circles 11 to 20 for each player continue that player's `ft`
string (circle 11 follows circle 10).

### Step 12. Check everything, then flag

Now compare sections. **Don't change a reading to make a check pass:** if a
check fails, look at the boxes involved again. If the handwriting really says
it, keep it and flag the box most likely wrong, with what you found.
- Each team's last running total equals its Final box (and its OT box if
  there was overtime; its Q4 box if not).
- Each Q1-Q4 box equals the total its quarter line is under.
- Every running-score number is on that team's roster, and that player is
  ticked Here.
- A player's made free throws (`M`) are no more than the boxes they have in the
  running score. Most 1-point jumps are free throws, so a 1-point box usually
  belongs to someone with an `M`.
- Every flagged box has a red box on the check picture (or a line in your
  list).

### Your answer

In this order:
1. The check picture with the section boxes (or the one-line section map).
2. Anything about the photo that limits the reading (blur, a cut-off corner,
   glare).
3. The running-score table from step 10.
4. **Unsure:** every flagged box, one line each, the same as `review`.
5. The check picture again with the red boxes added (if you can draw it).
6. **The game file**, in one code block, exactly in this shape (an example; use
   what's on your sheet). Use `home` and `away` as the team keys everywhere,
   and the team names as printed for `home:` and `away:` at the top.

```yaml
game_id: 2026-12-03-g1
form: MBL-SS6
status: draft
home: Lakehead
away: Current River
scorekeeper: Pat S.
teams:
  home:
    players:
      - {name: Andre G., num: 4, here: true, ft: XX, fouls: 1}
      - {name: Dan H., num: 21, here: true, ft: MM, fouls: 3}
      - {name: Pat O., num: 25, here: true, ft: MM, fouls: 1, tech: 1}
      - {name: Lorne K., num: 36, here: false}
  away:
    players:
      - {name: Scott A., num: 3, here: true, ft: XM, fouls: 2}
      - {name: Tom G., num: 6, here: true, fouls: 2}
      - {name: Carl M., num: 34, here: true, ft: MMX, fouls: 2}
running:
  home: {2: 25, 4: 4, 5: 21, 7: 21, 10: 25, 13: 4}
  away: {3: 34, 5: 6, 7: 3, 9: 34, 12: 6, 14: 3, 16: 34}
lines:
  home: [13, 27, 42, 63]
  away: [16, 27, 41, 54]
boxes:
  home: {q1: 13, q2: 27, q3: 42, q4: 63, ot: null, final: 63}
  away: {q1: 16, q2: 27, q3: 41, q4: 54, ot: null, final: 54}
notes:
  - {team: away, num: 6, q: 4, kind: flagrant, text: elbow to the face on a rebound}
review:
  - {at: running.home.27, note: "4 or 9? Looks like 4"}
  - {at: teams.away.players.2.ft.1, note: "filled or slashed?"}
  - {at: boxes.away.final, note: "Final says 54 but the running score ends at 52"}
```

`review` paths name one box: `running.home.27` (home's box at total 27),
`teams.away.players.2` (the third away row; add `.here`, `.fouls`, `.tech`,
`.num`, `.name` or `.ft.1` for the second circle), `lines.home.1` (home's Q2
line), `boxes.home.q4`, `notes.0`, `scorekeeper`, `game_id`. Rows and circles
count from 0. `lines` lists, for each team, the total each quarter line is
under, Q1 to Q4 (fewer if lines are missing; flag it). Leave out `notes` or
`review` if there are none.

---

## Why it's built this way

- **One section at a time.** Generic assistants made most of their mistakes by
  mixing sections up: the away roster read as home, the team fouls row read as
  the score, the printed PTS totals read as jersey numbers. Each step says
  where its section is, what it looks like, and what isn't part of it.
- **The check picture.** If the green box is round the wrong roster, every
  number after it is wrong; the picture shows that in a second, before anyone
  checks a box. The red boxes are the flags, where the checker looks first.
- **Home and away running score as separate passes.** Reading one strip at a
  time stops a number drifting to the other team's side, and the table in
  step 10 lets the checker compare it with the paper line by line.
- **Image processing, only with code, and gently.** Straightening and
  enlarging each section helps most (a small number in a big photo is a few
  pixels). The positions in step 2 come from the sheet's own box map
  (`scoresheet.py --geometry`), as percentages between the corner squares.
  Hard thresholding is ruled out: it erases faint pencil and invents marks.
- **Names, not ids.** The assistant can't see the site's player list, so it
  writes what's on the sheet. The entry page matches each name and number to
  `players.yml` when the file is opened (same team and number first, then a sub
  from any team) and says how many it matched; a row it can't match keeps its
  name, and the checks ask for a player id before it can be final.
- **`home` and `away`, not team ids.** Same reason: the entry page turns them
  into ids using the game id's schedule row (or the team names).
- **The same checks.** Once it's open on the entry page, the file gets exactly
  the checks a typed-up or `/record-game` draft gets
  ([game-file-format.md](game-file-format.md)).
- **Copied from this page.** The Copy button reads exactly what is between
  the two `---` lines under "The prompt"; the build fails if they go missing.
- **If the layout changes** (`SPEC` in `scripts/scoresheet/scoresheet.py`),
  redo the table in step 2 from `scoresheet.py --geometry` and the
  description of each section.
