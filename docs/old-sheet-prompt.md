# Prompt: reading the league's paper score sheet

Games kept on the league's own paper sheet (the new English form MBL-PS1 from
`scripts/scoresheet/paper_sheet.py`, or the older bilingual "Feuille de
pointage") are typed up on the paper sheet page, `/enter/paper/`. That sheet
has no running score: each player's points per period, free throws and fouls.
The page builds the game file, running score included, from those.

This prompt has an AI chat read a photo of the sheet into a **paper sheet
file** the page opens. It doesn't make the game file or the running score
itself, and it doesn't save anything.

## How to use it

1. On `/enter/paper/`, press **Copy the prompt** ("Read a photo with an AI
   chat"). The deploy copies the prompt from this page into
   `enter/data/old-sheet-prompt.txt` (`build_stats.py`), so editing it here is
   enough.
2. Paste it into a new chat in Claude (claude.ai, or Claude Code) or ChatGPT,
   with a photo of the whole sheet, flat and in focus (and close-ups of the two
   team blocks if you can).
3. **Check its tables against the paper.** It first shows a table per team,
   each player's marks and points by period, free throws and fouls, and waits.
   Answer with fixes ("Ed K. is zeros across; move Ed K. to Corey B. down one
   row") until the tables are right, then say so.
4. It writes the file. Paste it (the code block, or the whole answer) into
   "Load a score sheet YML" on `/enter/paper/` and press **Open the pasted
   file**. The page matches the names to the season's players, checks every
   number, and saves the game file.

What it gets right that a plain reading doesn't:
- **Each player's marks come from their own printed row.** Handwriting drifts
  up toward the row above; matching marks to the Total column instead shifted
  rows in the first two games (Oct 17, 2026).
- **It shows you the tables first** and waits until you say they're right.
- **The free-throw marks:** a filled dot is a made free throw worth 2, a filled
  triangle one worth 3, a 1 one worth 1, a 0 a miss. (How the scorekeeper marks
  these may change; edit the prompt below if it does.)

## The prompt

---
You're reading a photo of a basketball score sheet from the Masters Basketball League (Thunder Bay) into a paper sheet file that I'll paste into the league's entry page. Copy the paper exactly: don't correct anything, and tell me about anything that doesn't add up. Work through the steps in order.

THE SHEET
It's the league's paper sheet: the English one ("Score Sheet", form MBL-PS1, running score to 130) or the older bilingual one ("Feuille de pointage", to 100). Both have:
- At the top: Game No. (1 = the first game that day, 2 = the second), Competition, Place and Date.
- Two team blocks. The top block is the visitors, the bottom block the home team ("Home" or "Home Team / Équipe"). Each block has the team name, then one row per player: name, No. (jersey number), a ✓ if they played, Fouls (the printed digits 1 2 3 4 5; circled digits are fouls), then one cell for each period (P1, P2, P3, P4) and Total.
- In each period cell the scorekeeper writes every attempt in order:
  2 or 3 = a basket worth that much
  a filled dot = a made free throw worth 2
  a filled triangle = a made free throw worth 3
  1 = a made free throw worth 1 (after a basket, or a bonus free throw)
  0 = a missed free throw
  The circled number at the right of the cell is that player's points in that period.
- Under the players, the team's score so far is boxed under each period (P1 to P4), and the final under Total (sometimes with an F). A circled number with an H is the halftime score. Overtime, if any, is written after P4: tell me where you found it.
- Crossed-out names didn't play: leave them out. Team fouls, timeouts and the running score numbers at the bottom aren't needed.

STEP 1: FIND THE PARTS
Say where you found the game details, each team block (its name, how many player rows have writing), the period boxes and the final for each team. If the photo is too blurry or cut off to read a part, say so and stop.

STEP 2: READ EACH TEAM, ONE ROW AT A TIME
Read each player's marks from the printed row their name is on. Use the printed 1 2 3 4 5 in the Fouls column as the anchor for each row. Handwriting often drifts up toward the row above, so never place marks by the Total column or by what adds up.
For each player:
- the marks in each period cell, as written, and the circled points;
- free throws made = dots + triangles + 1s; tried = made + 0s;
- fouls = how many Fouls digits are circled;
- played = the ✓.

STEP 3: CHECK THE SUMS (but don't change anything)
- Each player's marks add up to the circled number in each period, and the periods add up to their Total.
- Each period's points by the players add up to the team's points that period (that period's box minus the one before).
- The last box equals the final.
Note every mismatch.

STEP 4: SHOW ME, THEN WAIT
Show one table per team, in the sheet's row order:

| # | Player | P1 | P2 | P3 | P4 | Points | FT made / tried | Fouls |
|---|---|---|---|---|---|---|---|---|
| 8 | Colin O. | 2 | 4 (2 2) | – | 6 (2 0 2 2) | **12** | 0 / 1 | 0 |
| 9 | Derek O. | 4 (• 2) | – | 0 (0) | – | **4** | 1 / 2 | 1 |
| | **Total** | **10** | **11** | **11** | **10** | **42** | | |

- Each period cell: the points, then the marks in brackets as written (• a dot, ▲ a triangle). A dash for an empty cell.
- Every player row with writing, including those with no points. Mark anyone who scored but has no ✓. List the players who didn't play under the table.
- The Total row: the players' points each period and in all, then the team's boxes.
- Under the tables: every mismatch from step 3, and each mark or number you're unsure of and why.
Then stop and wait. I'll answer with fixes (for example "Ed K. is zeros across; move Ed K. to Corey B. down one row"). Apply them, show the tables again, and wait until I say they're right.

STEP 5: WRITE THE FILE
Only when I've said the tables are right, write the file in one ```yaml code block, exactly in this shape:

```yaml
game_id: 2026-10-17-g2
form: MBL-PS1
status: draft
home: Floor Generals
away: Nor'Westers
scorekeeper: Dennis P.
teams:
  home:
    players:
      - {name: Adam A., num: "00", here: true, pts: [2, 0, 3, 0], ftm: 1, fta: 2, fouls: 1}
      - {name: Dan K., num: 7, here: false}
  away:
    players:
      - {name: Ryan S., num: 4, here: true, pts: [2, 4, 0, 2], ftm: 1, fta: 1, fouls: 2}
boxes:
  home: {q1: 18, q2: 29, q3: 43, q4: 66, ot: null, final: 66}
  away: {q1: 18, q2: 31, q3: 40, q4: 53, ot: null, final: 53}
review:
  - {at: teams.home.players.0.pts.1, note: "2 or 3?"}
```

- game_id: the sheet's date as YYYY-MM-DD, then -g and the Game No. (2026-10-17-g2 is the second game on October 17, 2026).
- home is the bottom block's team, away the top block's, by the names written on the sheet. scorekeeper: the Scorer line, if filled in.
- Players: each written as first name and last initial ("Adam A."), never the full name. num: the jersey number; put "00" or "0" in quotes.
- pts: the circled points for P1, P2, P3, P4, with 0 for an empty cell. Add a fifth number only if there was overtime.
- ftm, fta and fouls: leave each out when it's 0. A player who didn't play is just {name, num, here: false}.
- boxes: the team's boxed score after each period (q1-q4), after overtime (ot, or null), and the final.
- review: one entry for each box you're still unsure of, with at naming it: teams.home.players.<row, from 0>.pts.<period, from 0> (or .num, .here, .ftm, .fta, .fouls), or boxes.home.q1 (q2, q3, q4, ot, final). Leave review out if there's nothing.
- Nothing else: no running score, no other fields.
---
