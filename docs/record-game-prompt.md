# Reading a score sheet with any chat assistant (the free version of `/record-game`)

`/record-game` (`.claude/skills/record-game/SKILL.md`) needs Claude Code and
this repository: a helper straightens the photo and measures the ink in every
box before Claude reads it. This page is the version anyone can use with the
free claude.ai, or another assistant that reads images: copy the prompt below,
attach the photo, and save what comes back as a file the entry page opens.

It's less sure-footed than `/record-game` (nothing measures the ink, so the
assistant has to see every tick and circle itself), so expect more boxes to
check. The entry page's checks catch most mistakes; the paper catches the rest.

## How to use it

1. Photograph the sheet flat, the whole page, all four black corner squares
   in view, no shadow across it. Then take two close-ups: the running score
   (the numbered columns) and the two rosters. A close-up reads far better than
   a corner of one big photo.
2. Open a new chat at claude.ai (or another assistant), attach the photos,
   paste the prompt below, and send.
3. It answers with a game file in a code block. Copy it into a plain-text file
   named after the game, such as `2026-12-03-g1.yml` (in Notepad or TextEdit,
   save as plain text).
4. Open the entry page, `https://mastersbasketball.ca/enter/`, and drop the file
   on "A file on this computer". The page turns team names into the site's team
   ids and matches each player's name and number to the player list
   (`players.yml`); check the matches it reports. Then go through every flagged
   box with the paper, fix what the checks show, and save it as a draft or
   final, as in [stats-workflow.md](stats-workflow.md).

The prompt doesn't change between games or seasons: team names, player
names and the game id are all read off the sheet.

## The prompt

Copy everything between the lines.

---

You are typing up a basketball score sheet (Masters Basketball League, form
MBL-SS6) from the attached photo(s) into a YAML game file. Accuracy matters more
than speed: **never guess silently**. Any box you're not sure of goes in
`review` with a short, specific note ("4 or 9?"). A flagged box costs the
checker a glance; a wrong box that looks right goes on the website.
Copy what's written, even if the scorekeeper made a mistake; flag it instead
of fixing it.

**The sheet.** At the top: Date, Start time, Court, Game ID (like
`2026-12-03-g1`) and Scorekeeper. Then two roster blocks, HOME and AWAY, each
with the team name, timeouts, and up to 12 rows. Each row: `#` (jersey number),
`Here` (a tick box), `Player` (printed "First L." or written in by hand),
10 free-throw circles, 5 foul boxes and 2 `T` boxes. Under each roster: a team
fouls row (ignore it) and the score boxes `Q1 Q2 Q3 Q4 OT Final`. Then a Notes
box. Then the running score: columns of rows numbered 1 to 100, each row with a
Home # box on the left of the printed number and an Away # box on the right.
A page 2, if there is one, continues free throws 11-20 and the running score
from 101. Ignore timeouts and team fouls.

**What to read, and how:**

1. **Game ID, date, scorekeeper** from the header. The team names from the HOME
   and AWAY bars.
2. **Each roster row, top to bottom, in order**, including printed rows of
   players who didn't play:
   - `num`: the jersey number. `name`: as printed or written, "First L."
     (first name and last initial only; never more of the surname).
   - `here`: `true` if the Here box has a tick or any mark, else `false`.
   - `ft`: the free-throw circles from the left, one letter each: a **filled**
     circle is `M` (made), a **slashed or crossed** circle is `X` (missed).
     Stop at the first empty circle. Leave `ft` out if none are marked.
   - `fouls`: how many foul boxes are slashed (0-5); `tech`: how many T boxes
     (0-2). Leave them out when 0.
   - Leave out rows that are completely empty (no number, no name, no marks).
3. **The running score.** Each time a team scores, the scorekeeper writes the
   scorer's jersey number in that team's box beside the team's new total.
   Go down every column, row by row, and record each box with a number in it
   as `total: number`, separately for home and away. Most rows have a number on
   one side only; many have none.
   - Every number must be a jersey number on that team's roster. If what you
     read isn't, look again: handwritten 1/7, 3/8, 4/9, 5/6, 0/6/8 and 2/7 are
     easy to mix up. If one roster number fits, use it; if two could, use the
     likelier and flag it.
   - A team's totals go up by 1, 2 or 3 at a time. A bigger jump means you
     missed a box: look again.
   - Read every box on its own; don't carry a number down a column.
4. **Quarter lines.** A line drawn under a team's last number at the end of
   each quarter. `lines` lists, for each team, the total each line is under:
   four numbers, Q1 to Q4. (Overtime has no line.)
5. **Score boxes** under each roster, as written: running totals at the end of
   Q1-Q4, the total after overtime (`ot`, `null` if empty), and `final`.
6. **Notes.** Each entry: which team (`home` or `away`), the player's number,
   the quarter (1-4 or `OT`), `kind: flagrant` for a flagrant foul (else
   `kind: note`), and the text as written, kept short.

**Before you answer, check your own work** and flag anything that fails:
- each team's last running total equals its Final box;
- each Q box equals the total its quarter line is under;
- every running-score number is on that team's roster, and that player is
  ticked Here;
- a player's made free throws (`M`) are no more than the number of times they
  appear in the running score.

**Answer with only the file, in one code block**, exactly in this shape (an
example; use what's on your sheet). Use `home` and `away` as the team keys
everywhere, and the team names as printed for `home:` and `away:` at the top.

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
`teams.away.players.2` (the third away row; add `.here`, `.fouls`, `.tech` or
`.ft.1` for the second circle), `lines.home.1` (home's Q2 line),
`boxes.home.q4`, `notes.0`, `scorekeeper`. Rows and circles count from 0.
Leave out `notes` or `review` if there are none.

---

## Why it's built this way

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
