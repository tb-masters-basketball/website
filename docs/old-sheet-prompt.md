# Prompt: the older league score sheet

Some games are still kept on the older league sheet ("Feuille de pointage"),
not on our MBL-SS6. That sheet has no running score: each player's marks per
quarter, and the team's points per quarter. `/record-game` can't read it, so
send this prompt to Claude Code with the photo (or photos) attached, one game
per sheet.

What it gets right that a plain reading doesn't:
- **Each player's marks come from their own printed row.** Handwriting drifts
  up toward the row above; matching marks to the Total column instead is what
  shifted rows in the first two games (Oct 17).
- **It shows you a table per team first** (each player's points and marks by
  quarter, free throws and fouls) and waits until you say they're right before
  it writes or pushes anything. Answer with fixes such as "Ed K. is zeros
  across, move Ed K. to Corey B. down one row".
- **A filled dot is a made free throw worth 2**, and a 1 is a 1-point free throw.

The sheet doesn't say who scored at each total, so the draft's running score is
rebuilt in roster order, with a review note saying so. Points, free throws,
fouls, the quarter boxes and the final are from the paper. Check the draft on
the entry page and save it as final, as usual
([stats-workflow.md](stats-workflow.md#enter-or-check-a-game-on-the-entry-page)).

Copy everything in the box:

```text
Read the attached photo(s) of the older league score sheet (the "Feuille de pointage" sheet, not our MBL-SS6) into a draft game file, one per sheet.

The sheet
- Header: game number (1 = 9:45 game, 2 = 11:15 game), place, date. Use the game id from data/2026-27/schedule.csv for that date and game number. Keep home/away as the schedule has them, even if the sheet says otherwise, and note it.
- Two team blocks (visitor on top, home below). Each player row has: name, No., a ✓ if they played, fouls (printed 1 2 3 4 5; circled = fouls), then four quarter columns P1-P4, then a Total column.
- In each quarter cell, the scorekeeper writes every attempt in order:
  2 or 3 = a basket worth that much
  filled dot = a made free throw, worth 2 (league rule: a free throw is worth the shot)
  1 = a made 1-point free throw (after a made basket)
  0 = a missed free throw
  The circled number in the cell is that player's points for the quarter.
- On each team's line under its roster: the boxed numbers are the team's points per quarter, then the final (F); a circled number with an H is the halftime total.
- Crossed-out names didn't play: leave them out.

How to read it
1. Read each player's marks from the printed row their name is on. Use the printed 1 2 3 4 5 in the fouls column as the anchor for each row. Handwriting often drifts up toward the row above, so don't place marks by the Total column or by "what adds up".
2. Check each row: its marks add up to the circled number in each quarter, and the quarters add up to the Total column.
3. Check each team: players' points in each quarter add up to that quarter's boxed number, and the quarters add up to the final.
4. Before writing or pushing anything, show me one table per team in the chat, in roster order, so I can check it against the paper. Like this (three rows of the Bears from Oct 17; yours has every player):

   | # | Player | Q1 | Q2 | Q3 | Q4 | Points | FT made / tried | Fouls |
   |---|---|---|---|---|---|---|---|---|
   | 8 | Colin O. | 2 | 4 (2 2) | – | 6 (2 0 2 2) | **12** | 0 / 1 | 0 |
   | 9 | Derek O. | 4 (• 2) | – | 0 (0) | – | **4** | 1 / 2 | 1 |
   | 5 | Tom M. | – | – | – | – | **0** | – | 0 |
   | … | | | | | | | | |
   | | **Total** | **10** | **11** | **11** | **10** | **42** | | |

   - Each quarter cell: the points, then the marks in brackets as written (• = made free throw, 0 = missed, 1 = 1-point free throw). A dash for nothing.
   - Every player on the sheet, including those with no points. Mark anyone who scored but isn't ticked, e.g. "Ryan T. (not ticked Here)". List those who didn't play under the table.
   - The Total row: each quarter's points and the final, matching the team's boxes.
   - Under the tables: the rows you're unsure of and why (e.g. "Mike Z.'s Q3 0 is written on the BEARS line above his name").
   - Then stop and wait. I'll answer with fixes like "Ed K. is zeros across, move Ed K. to Corey B. down one row". Apply them, show the corrected tables again, and wait until I say they're right.

Then, once I've said the tables are right
- Write data/2026-27/drafts/<game_id>.yml in the usual format. Rebuild each quarter's running score in roster order (the sheet doesn't say who scored at each total), and add a review note saying so.
- Players: match names and numbers to data/2026-27/players.yml. Add anyone new as "First L." with their number, and tell me so I can mark subs. Fill in jersey numbers the roster doesn't have yet. Flag any number that disagrees with the roster.
- Flag: a scorer without a ✓, unclear marks or numbers, and anything that doesn't add up (copy the paper, don't correct it).
- Run `python scripts/record_game.py check` on the draft, save the photo to data/2026-27/sheets/<game_id>.jpg (at most 3000 px, no EXIF), and push to main.
- End with the score, the top scorers, the flags, and the entry-page link for each game.
```
