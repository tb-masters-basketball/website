# How the stats work

A guide for whoever keeps the league's numbers up to date. You do not need to
be a programmer. Everything below can be done in GitHub's web editor in a
browser, and the site checks your work for you before anything goes live.

**The short version:** after each game day, the paper score sheets are typed
into one small text file per game. The site reads those files, double-checks
them, works out every number (standings, points per game, free-throw %), and
publishes the pages. If something doesn't add up, the check fails with a plain
message and **nothing is published**, so a typo can't put wrong numbers on the
site.

- [The path from score sheet to website](#the-path-from-score-sheet-to-website)
- [The data folders](#the-data-folders)
- [What a game file looks like](#what-a-game-file-looks-like)
- [The checks, and what a failure looks like](#the-checks-and-what-a-failure-looks-like)
- [How each number is calculated](#how-each-number-is-calculated)
- [How to](#how-to) — add a game, fix a number, add a player or sub, change a ranking minimum, the preview copy
- [If something looks wrong](#if-something-looks-wrong)

## The path from score sheet to website

```mermaid
flowchart TD
    A["Paper score sheet"] --> B["Photo of the sheet"]
    B --> C["Game file typed up<br/>data/SEASON/games/DATE-gN.yml"]
    B -. "kept for checking" .-> P["Photo saved in<br/>data/SEASON/sheets/"]
    C --> D{"scripts/build_stats.py<br/>runs the checks"}
    D -- "a check fails" --> E["Clear error message.<br/>Nothing is published."]
    E -- "fix the file and try again" --> C
    D -- "all checks pass" --> F["Calculates standings points,<br/>points per game, free-throw %"]
    F --> G["_data/computed/*.json<br/>and one small stub page per game,<br/>player and team (never edited by hand)"]
    G --> H["Jekyll builds every page:<br/>Home, Stats, Schedule, box scores,<br/>player and team pages, Archive"]
    H --> L{"Link check:<br/>any broken link or image?"}
    L -- "yes" --> E2["Build fails.<br/>Nothing is published."]
    L -- "no" --> I["GitHub Actions publishes<br/>to GitHub Pages"]
    I --> J["The live website"]
```

What each step means in plain words:

| Step | Who or what does it | Where it lives |
|---|---|---|
| Score sheet and photo | A person at the game | Paper, then a photo on someone's phone |
| Game file | **You**, by typing the sheet's numbers | `data/<season>/games/<date>-g1.yml` |
| Checks | `scripts/build_stats.py` (automatic) | Runs on every change; see [the checks](#the-checks-and-what-a-failure-looks-like) |
| Calculations | `scripts/build_stats.py` (automatic) | Writes `_data/computed/`. Never edit those files; they are rewritten every time |
| Pages | Jekyll, the site builder (automatic) | Every page reads `_data/computed/`. The script also writes a tiny stub file for each game, player, team and archive season (folders `_games/`, `_players/`, `_teams/`, `_archive/`, rewritten every time), which is how each one gets its own page |
| Link check | `scripts/check_links.sh` (automatic) | Stops the publish if any link, image or script in the built site is broken |
| Publishing | GitHub Actions (automatic) | `.github/workflows/deploy.yml`. It only publishes when a change is **merged into `main`**, and again every night so the date-based parts stay current. Each publish also updates the [preview copy](#the-preview-copy-sample-data-at-preview) |

You only ever touch the game file (and occasionally the player list). The rest
happens by itself: add a game and its box score page, the players' pages and the
standings all update on their own.

## The score sheet

The league's score sheet is form **MBL-SS6**, made by
`scripts/scoresheet/scoresheet.py` ([its README](../scripts/scoresheet/README.md)).
Every time the site is published:

- **Upcoming game days:** each one on the Schedule gets a **Score sheet (PDF)**
  link (landscape Legal) and **Other layouts** (landscape Letter, portrait
  Letter and Legal). The sheet has both games, two pages each, with the date,
  start time, game ID and team names filled in. Each roster lists the team's
  regular players (not subs) in jersey-number order. Until the rosters are in
  `players.yml`, the 12 rows print blank. Every printed name and number is still
  an editable field, so last-minute changes can be typed in before printing.
- **Blank sheets:** all four layouts are at the bottom of the Schedule page.

Print double-sided. Page 2 has **How to mark** (the scorekeeper's
instructions) and the overflow: the running score past 100 points and free
throws past 10. Page 1 has a **Notes** box for flagrant fouls. Games are played
in quarters: the scorekeeper writes each team's running total at the end of
each quarter in the Q1 to Q4 boxes.

### How stats come from a sheet

| Stat | Source |
|---|---|
| Player points | Running score. The jump from the team's previous total to the next one is that basket's value: 1, 2 or 3. |
| FTM | Filled circles in the player's row. The running score's 1-point jumps must agree. |
| FTA | Filled circles plus slashed circles. |
| GP | **Here** ticks. |
| PF (personal fouls) | Slashed foul boxes in the player's row (0 to 5). Kept, but not shown on the site. |
| Techs (technical fouls) | Slashed red **T** boxes in the player's row (0 to 2). |
| Quarter scores | The **Q1 to Q4** boxes (and **OT**): each team's running total at the end of each quarter. |
| Flagrant fouls | **Notes** on page 1: team, player number and quarter. A flagrant also counts as a personal foul, so it is in the player's foul boxes (and `pf`) too. |
| Checks | The last running total equals the Final box. Each quarter box equals the running total at that quarter's line. Player points add up to the team score. |

Those numbers are what goes into the game file: `pts`, `ftm` and `fta` for every
player ticked **Here** (plus `pf` and `tech` when they're not 0), and each team's
final score. The sheet's team fouls and timeouts aren't on the site. Quarter
scores and flagrant fouls are on the sheet now; the game files and standings
start using them in the next change (standings by points).

## The data folders

```
data/
  seasons.yml          which seasons exist, and which one is current
  2026-27/             the REAL season: real teams and schedule, rosters to come
    teams.yml            the five teams
    players.yml          every player and sub
    schedule.csv         every game day: who plays whom, when
    games/               one file per game that has been played
    sheets/              photos of the paper score sheets
  sample-2026-27/      FAKE sample season, standing in for the real one
  sample-2025-26/      FAKE past season, so the Archive has something to show
```

- **Real season:** `data/2026-27/`. The teams and the schedule are in;
  `players.yml` is empty until the rosters arrive, and `games/` fills up as
  games are played.
- **Sample seasons:** `data/sample-2026-27/` and `data/sample-2025-26/` are
  made-up data (made by `scripts/make_sample_season.py`) so the site looks real
  before the first game. The first stands in for the current season and the
  second is a short past season for the Archive. While sample mode is on, the
  website shows a banner saying so, and the Archive lists both. With it off,
  neither is shown on the main site, but both are on the hidden
  [preview copy](#the-preview-copy-sample-data-at-preview) at `/preview/`. See
  [Sample mode](#sample-mode-now-off) (it is off now).
- **Which season is shown** is decided in one place, `data/seasons.yml`:
  `current: true` marks the real season, and `stands_in_for: 2026-27` marks
  the sample that replaces it while sample mode is on.

## What a game file looks like

This is a real file from the sample season, `data/sample-2026-27/games/2026-12-03-g1.yml`
(shortened):

```yaml
game_id: 2026-12-03-g1      # must match the file name and a row in schedule.csv
date: 2026-12-03
home: pa                    # team ids, two letters (see teams.yml)
away: lh
type: regular               # regular, or playoff
final: {pa: 71, lh: 64}     # the final score from the sheet
quarters: {pa: [19, 36, 53, 71], lh: [15, 31, 49, 64]}   # the sheet's Q1-Q4 boxes
lines:                      # one line per player listed on the sheet
  - {player: dave-m, team: pa, pts: 24, ftm: 6, fta: 7, pf: 3}
  - {player: greg-t, team: pa, pts: 12, ftm: 2, fta: 2, pf: 2, tech: 1, flagrant: 1}
  - {player: mike-r, team: lh, pts: 16, ftm: 1, fta: 2}
  # ...and so on for everyone on the sheet
```

**`quarters`** is copied from the sheet's **Q1 to Q4** boxes under each
roster: each team's running total at the end of each quarter, in order. The
last one is the final score, unless the game went to overtime (then Q4 is tied
and the final is higher). The site works out the points scored in each quarter
from these, and from those who won each quarter.

For each player: **`pts`** = total points, **`ftm`** = free throws made,
**`fta`** = free throws attempted. Two more are optional and can be left out
when they're 0: **`pf`** = personal fouls (0 to 5; kept, not shown on the site)
**`tech`** = technical fouls (0 to 2; shown on the player page and the
Stats page, counting the whole season, playoffs included) and **`flagrant`** =
flagrant fouls (from the sheet's Notes; counted like technicals). A flagrant
is also a personal foul, so count it in `pf` too. A player who was on the sheet but didn't
score still gets a line with zeros, because being on the sheet counts as
playing in the game.

Two things must always be true, and the checks look for both: each team's
player points add up to that team's final score, and `ftm` is never more than
`fta`.

## The checks, and what a failure looks like

Every time the numbers are built, the script runs these checks. If **any**
fail, it lists **all** the problems (with the file and the line) and stops.
Nothing is published until they are fixed.

The real message starts with the full path (for example
`data/2026-27/games/2026-12-03-g1.yml`); it is shortened here to fit.

| What it catches | Example message |
|---|---|
| A team's player points don't add up to the final score | `games/2026-12-03-g1.yml: pa player points add up to 71, but the final score is 73` |
| Free throws made is more than attempted | `games/2026-12-03-g1.yml: line 1 (dave-m): ftm 8 is more than fta 7` |
| A number is negative or isn't a whole number | `games/2026-12-03-g1.yml: line 2 (greg-t): fta should be whole numbers, 0 or more` |
| A player id isn't in `players.yml` (often a typo) | `games/2026-12-03-g1.yml: line 1 (dave-x): player 'dave-x' is not in players.yml` |
| A team id isn't in `teams.yml` | `games/2026-12-03-g1.yml: line 10 (mike-r): team 'zz' is not in teams.yml` |
| The `game_id` doesn't match the file name | `games/2026-12-03-g1.yml: game_id '2026-12-03-g9' doesn't match the file name '2026-12-03-g1'` |
| The game isn't in `schedule.csv` | `games/2026-12-11-g1.yml: game_id '2026-12-11-g1' has no row in schedule.csv` |
| The date, teams or type disagree with `schedule.csv` | `games/2026-12-03-g1.yml: date 2026-12-04 doesn't match schedule.csv (2026-12-03)` |
| A game file exists for a game marked `cancelled` | `games/2026-11-14-g1.yml: game '2026-11-14-g1' is marked cancelled in schedule.csv. Delete this file, or clear the status if the game was played` |
| Too many fouls for the sheet (`pf` above 5, `tech` above 2) | `games/2026-12-03-g1.yml: line 1 (dave-m): tech 3 should be a whole number from 0 to 2` |
| The final score is a tie | `games/2026-12-03-g1.yml: final score is tied 64-64` |
| A player is listed twice in one game | `games/2026-12-03-g1.yml: line 3 (greg-t): player is listed twice in this game` |
| A player name isn't written "First L." | `players.yml: player #1 (dave-m): display 'Dave Mitchell' should be 'First L.' (never a full name)` |
| Two players on one team share a "First L." and one has no number | ``players.yml: mike-r, mike-r2 on team dn are all "Mike R."; give each a jersey `number` ...`` |
| The quarter totals are missing | ``games/2026-12-03-g1.yml: quarters is missing. Add each team's running total at the end of each quarter, from the sheet's Q1-Q4 boxes, e.g. quarters: {...}`` |
| The Q4 totals don't match the final score | `games/2026-12-03-g1.yml: the Q4 totals (pa 70, lh 64) don't match the final score (71-64). They only differ after overtime, which needs the score tied at the end of Q4` |
| A quarter total goes down | `games/2026-12-03-g1.yml: quarters for lh [15, 31, 29, 64] go down; each is the running total at the end of that quarter, so it can only stay level or climb` |
| More flagrant fouls than personal fouls | `games/2026-12-03-g1.yml: line 2 (greg-t): flagrant 1 is more than pf 0 (a flagrant foul is also a personal foul, so count it in pf too)` |
| The file isn't valid (a missing bracket, wrong indent) | `games/2026-12-03-g1.yml: not valid YAML (...)` followed by the line and column |

It also catches: the same `game_id` used in two seasons that are shown on the
site (each game gets a page at `/games/<game_id>/`, so ids must be unique), a
`stands_in_for` that names a season that doesn't exist, two players or teams
sharing an id, a made free throw worth
more than the points scored, a player with exactly 1 point more than their free
throws (a field goal can't be worth 1), a team playing twice on the same day,
and a `seasons.yml` that doesn't have exactly one current season.

**Where you see the message:** on the GitHub pull request, the *Build and
deploy* check turns into a red cross. Click **Details**, then open the step
called **Check data and compute stats**. The messages above are what you will
read there. A failed check never changes the live site.

Often one mistake shows up as two messages. A wrong final score, for example,
also makes the points not add up. Fix the first one and look again.

## How each number is calculated

Everything is worked out from the game files. Here is Dave M. (Port Arthur) in
the sample season, line by line:

| Week | Points | FTM | FTA |
|---|---|---|---|
| 1 | 23 | 2 | 3 |
| 2 | 14 | 4 | 4 |
| 4 | 21 | 2 | 3 |
| 5 | 22 | 1 | 2 |
| 6 | 20 | 4 | 4 |
| 7 | 17 | 3 | 4 |
| 8 | 24 | 6 | 7 |
| **Total** | **141** | **22** | **27** |

(He has no line for week 3, so he didn't play that day.)

| Stat | Rule | Dave M.'s number |
|---|---|---|
| **GP** (games played) | Games where the player is on the sheet | 7 games |
| **PTS** | Add up the points | 141 |
| **PPG** (points per game) | PTS ÷ GP, one decimal | 141 ÷ 7 = 20.14… → **20.1** |
| **FTM-FTA** | Add up made and attempted | 22-27 |
| **FT%** | FTM ÷ FTA, one decimal | 22 ÷ 27 = 81.48…% → **81.5%** |
| **Season high** | His best single game | 24 |

Rounding goes the usual way (.5 rounds up), and the *ranking* uses the exact
number, not the rounded one, so two players only tie when their numbers are
truly equal.

- **Free-throw leaders** only include players with **10 or more** attempts
  (FTA). Dave M.'s 27 is plenty. A player with 1 of 2 is not ranked, however
  good the percentage.
- **Points-per-game leaders** can need a minimum number of games
  (`ppg_min_games`, 3 this season). While a player's team has played fewer
  games than the minimum, playing all of the team's games is enough, so the
  list fills up from the first game day. Players below it still appear in the
  Stats table and on their own page ("Not ranked yet").
- Both minimums are set per season in `data/seasons.yml` (`ppg_min_games` and
  `ft_min_attempts`). See [Change a ranking minimum](#change-a-ranking-minimum).
- **Subs** get their own line and their own stats. A sub's points also count
  toward their team's score that day.
- **Playoffs** (`type: playoff`) are kept separate. They never count in the
  standings or in the Stats page.

**Standings** are by **points**: in each regular-season game a team gets
**1 point for each quarter it wins** and **3 points for winning the game**, so
7 at most. A quarter's winner is the team that scored more in it (from the
`quarters` totals). Two things are assumed until the league confirms them: a
**tied quarter** gives neither team a point, and **overtime** isn't a quarter
(it only decides who wins the game). Port Arthur in the sample season:

| Column | Rule | Port Arthur |
|---|---|---|
| PTS | Quarters won + 3 for each win | 19 + 3 × 6 = **37** |
| W-L | Wins and losses | 6-1 |
| QW | Quarters won | 19 of 28 |
| PCT | W ÷ (W + L), three decimals | 6 ÷ 7 = **.857** |
| PF / PA | Points scored for / against, all games | 482 / 421 |
| DIFF | PF − PA | **+61** |

The order is by PTS. **Tiebreakers have not been decided by the league yet**
(`[placeholder]`). Until then the site orders teams level on points by
head-to-head record, then point differential, and says so under the standings
when it has to. Playoff games give no standings points: they go to the winner.

## How to

All of these work in the GitHub web editor. For every change, use **Commit
changes… → Create a new branch and start a pull request**. The *Build and
deploy* check then runs the checks on your change and shows a green tick or a
red cross. **Merge the pull request** only when it is green. Merging publishes
the site (it takes a minute or two).

### Add a game

1. **Check the game is on the schedule.** Open `data/2026-27/schedule.csv`. The
   game needs a row, for example:
   `2026-10-17-g1,2026-10-17,09:45,,bb,hu,regular,1,,`
   The columns are `game_id, date, time, gym, home, away, type, week, status, round`. The
   date is `YYYY-MM-DD`, the time is 24-hour (`09:45`), and the id is the date
   plus `-g1`, `-g2` for that day's first and second game. Leave `gym` blank
   to use the season's gym (St. Pat's, set in `data/seasons.yml`); fill it in
   only for a game day played somewhere else. There is no court column. Leave
   `status` blank (it is only for [cancelled games](#cancel-or-move-a-game)),
   and `round` blank for a regular-season game.
2. **Create the game file.** In `data/2026-27/games/`, choose **Add file →
   Create new file** and name it exactly like the `game_id`, plus `.yml`:
   `2026-12-03-g1.yml`. The easiest start is to copy the example
   [above](#what-a-game-file-looks-like) and replace the numbers.
3. **Type in the sheet.** The `final:` score, the `quarters:` totals from the
   Q1 to Q4 boxes, and one `lines:` entry for every player on the sheet, with
   their `pts`, `ftm` and `fta` (and `pf`, `tech`, `flagrant` when not 0). The
   `final:` score must equal each team's points added up.
4. **Optional: save the photo** of the sheet as
   `data/2026-27/sheets/2026-12-03-g1.jpg` (same name as the game). It is kept
   for checking. It is **not** shown on the site: the box score's "Score sheet
   photo" link is switched off (`score_sheet_links: false` in `_config.yml`):
   the league keeps the photos in the repo, not on the site. The repo is public,
   so if a name was written out in full by hand, don't save the photo.
5. **Commit as a pull request** and wait for the check. Fix anything it reports
   (see [the checks](#the-checks-and-what-a-failure-looks-like)), then merge.
   When it is published the game has its own box score page
   (`/games/2026-12-03-g1/`), and the Schedule, standings, Stats and every
   player's and team's page update with it.

### Fill in a playoff matchup

The playoff games are already in `schedule.csv`, with placeholders where the
teams will go, as on the printed schedule:

```
2027-04-24-g1,2027-04-24,09:45,,2nd,3rd,playoff,22,,Semifinal (G42)
```

When the standings (or a result) decide who plays, replace the placeholders
with the two team ids, for example `...,09:45,,dn,hu,playoff,22,,Semifinal (G42)`.
Do this **before** adding the game file: the check refuses a game file whose
row still says `2nd`, `TBD` or `Winner G41`. Once a row names both teams, the
game also appears on their team pages and in their team calendars.

### Cancel or move a game

Keep the game's row in `data/2026-27/schedule.csv` and change it:

- **Cancelled, not made up:** type `cancelled` in the `status` column (next to last),
  for example `2026-11-14-g1,2026-11-14,09:45,,hu,nw,regular,4,cancelled,`.
  The game stays on the Schedule with a **Cancelled** badge. It counts for
  nothing, and the site skips it when it shows the next game day. A game file
  for a cancelled game is an error: the check says so.
  - If every game that day is cancelled, the Schedule shows the date with a
    **Cancelled** badge and no week number, so the week number in those rows
    doesn't matter.
- **Moved to another date or time:** change its `date` and `time`, and change
  the `game_id` to match the new date (and its `-g1`/`-g2`). Give it the
  `week` of the day it is now played on.
- **Cancelled now, made up later:** mark the original row `cancelled`, and add a
  new row for the make-up game with its own date and `game_id`.

### Team calendars

Nothing to do. Every time the site is published, the calendar files on the
Schedule page (and each team page) are rebuilt from `schedule.csv` and the game
files. Anyone who added a calendar with **Apple** (Apple Calendar or Outlook)
or **Google** sees moved and cancelled games, and final scores, the next time
their calendar app checks: Apple within a few hours, Google on its own
schedule, usually within a day (it can't be hurried). Anyone who chose
**Download** has a one-time copy and needs to download it again.

### Change a ranking minimum

Open `data/seasons.yml` and change the number on the current season:

```yaml
  ppg_min_games: 3      # games to be ranked for points per game (0 = none)
  ft_min_attempts: 10   # free throws attempted to be ranked for FT %
```

Commit it as a pull request. The Stats page, the home page leaders and the
player pages follow the new numbers when it's merged, and the notes on the
Stats page say what the rule is. Past seasons keep their own numbers.

### Edit the league rules

The League rules page (linked in every page's footer) is one text file,
`rules/index.md`. Open it on GitHub, click the pencil, and replace each
`[placeholder]` with the real rule. Each line starting with `## ` is a section
heading; lines starting with `- ` are bullet points. When you're done, put the
date in `updated:` near the top (for example `updated: "Oct 17, 2026"`); until
then the page says it's a draft. Commit as a pull request and merge it.

### Fix a wrong number

Open the game file, correct the number, and commit it as a pull request. The
checks run again and every stat that depends on it is recalculated from
scratch, so there is nothing else to update. If you are changing a player's
points, change the team's `final:` score too if it is now off, or the check
will tell you. A wrong quarter total is fixed the same way, in `quarters:`;
the standings points follow by themselves.

### Add a new player, or a sub

1. Open `data/2026-27/players.yml` and add one line:
   `- {id: mike-r, display: Mike R., team: dn, sub: false, number: 23}`
   (`number` is the jersey number, optional, 0 to 99; it goes on the score
   sheets)
2. The **id** is first name plus last initial, lowercase (`mike-r`). If two
   players would get the same id, number the second one: `mike-r2` (or use
   more of the last name: `mike-ro`). Never change an id once a game uses it.
   If two players on the **same team** are both "Mike R.", give both a
   `number`: the site shows "#23 Mike R." and "#7 Mike R.", and the build
   stops until they have one.
3. The **display** name is always written **First L.**, never a full name.
4. For a **sub**, add them the first time they play and set `sub: true`. Then
   use their id in that day's game file like any other player. A sub's page
   and box score lines are marked **Sub**.
5. Once they are in `players.yml` they get a player page (`/players/mike-r/`)
   and appear on their team's roster, even before their first game.

### The preview copy (sample data at /preview/)

Every deploy also builds a second copy of the site from the made-up sample
season, at **mastersbasketball.ca/preview/**. It looks exactly like the real
site, with a full season of fake numbers, and a banner that says so and links
back to the live site. Use it to see what a change looks like with data, while
the real site carries on showing the real season.

- Nothing links to it and search engines are asked not to list it, but it is
  not private: anyone with the address can open it.
- It shows what is merged into `main`, a minute or two after the merge. A pull
  request that isn't merged yet doesn't appear there.
- The switch is `preview_site: true` in `_config.yml` (`false` turns it off).

### Sample mode (now off)

Sample mode was switched off in October 2026, once the real teams and schedule
were in: the site shows the real 2026-27 season. The switch is in one file,
`_config.yml`, if you ever want to preview the site with made-up numbers again:

```yaml
sample_data: false    # true shows the made-up sample season
```

- **On (`true`):** every page shows the made-up season, and a banner under the
  header says *"Preview with sample data. Real results start after the first
  game day."*
- **Off (`false`):** every page reads the real season in `data/2026-27/` and
  the banner disappears. The sample past season leaves the Archive too. Until
  the first game is recorded, the pages show empty states such as "No games
  played yet" and "Not scheduled yet", and the Archive lists only the current
  season.

The teams and the schedule are already in, and the rosters can start empty
(`data/2026-27/players.yml` is `[]`; team pages then say "No players listed
yet"). Add players as they're known, at the latest when their first game is
recorded. Nothing else needs to change. The sample data can stay
in the repository (it is never shown while the switch is off), or be deleted
later together with its entry in `data/seasons.yml`.

## If something looks wrong

- **The check failed (red cross).** Read the message. It names the file and the
  line. Fix it, commit again, and the check re-runs by itself.
- **The site still shows an old number.** Changes only go live when the pull
  request is merged, and publishing takes a minute or two. Refresh the page.
- **A player is missing from Stats.** Stats only lists players who have played
  at least one game, so check they have a `lines:` entry in a game file.
- **A player is missing from the free-throw leaders.** They have fewer than 10
  attempts so far (`ft_min_attempts` in `data/seasons.yml`). That is the rule,
  not a mistake.
- **A team's points look wrong.** Points come from the `quarters:` totals: 1
  for each quarter a team scored more in, and 3 for the win. Check the totals
  against the sheet's Q1 to Q4 boxes. A tied quarter gives no one a point.
- **A sub tops the points-per-game list after one big game.** There is no
  minimum number of games for that list unless `ppg_min_games` is set in
  `data/seasons.yml` ([how](#change-a-ranking-minimum)).
- **A player is missing from the points-per-game list.** They have fewer games
  than `ppg_min_games` while their team has played that many. They are still
  in the Stats table and on their own page.
- **You aren't sure what to do.** Don't merge. A pull request that isn't merged
  never changes the live site, so it is always safe to leave it open and ask.

For the technical details (file formats, ids and the exact rules), see
`data/CLAUDE.md`.
