# League data

Everything the site shows comes from these files. One folder per season, named
like `2026-27`. `scripts/build_stats.py` turns them into `_data/computed/`.

## Files
```
data/seasons.yml              list of seasons, newest first; marks the current one
data/2026-27/
  teams.yml                   id, name, short (2 letters), colour_slot, colour_light, colour_dark
  players.yml                 id, display (First L.), team, sub (true/false), number (optional jersey #)
  schedule.csv                game_id,date,time,gym,home,away,type,week,status,round (gym blank: the
                              season's gym; no courts; status blank or `cancelled`; round names a
                              playoff round; status and round may be left out from the end)
  games/2026-12-03-g1.yml     one file per played game: the score sheet, box for box (format below)
  drafts/2026-12-03-g1.yml    a game still being entered or checked (status: draft; not read by the build)
  sheets/2026-12-03-g1.jpg    photo of the paper score sheet, kept for checking
```

### seasons.yml
```yaml
- id: 2026-27          # folder name under data/
  label: "2026-27"     # what the site shows
  current: true        # exactly one season is current: the real one
  gym: "St. Pat's"
  gym_address: "621 Selkirk St S, Thunder Bay, ON P7E 1T9"   # optional, for calendars
  ppg_min_games: 3     # games to be ranked for PPG, capped at the team's games so far
  ft_min_attempts: 10  # free throws attempted to be ranked for FT %
- id: sample-2026-27
  label: "2026-27"
  sample: true         # fake data; never `current`
  stands_in_for: 2026-27   # shown instead of 2026-27 while sample_data is on
  gym: "St. Pat's"
- id: sample-2025-26
  label: "2025-26"
  sample: true         # a fake past season: in the Archive in sample mode only
  gym: "St. Pat's"
```
`sample_data: true` in `_config.yml` makes every page read the sample season
that `stands_in_for` the current one, and show a "Preview with sample data"
banner. With it off, pages read the `current` season and the banner goes.
`build_stats.py` makes that choice once and writes it to
`_data/computed/active.json` (the active season, and the seasons the Archive
lists); the templates only read that file. At most one sample season may stand
in for a given season.

`preview_site: true` in `_config.yml` builds a second copy of the site on every
deploy, from the sample season, at `/preview/` (`scripts/build_preview.sh`).
It runs `build_stats.py` again with `sample_data: true`, so the sample seasons
must always pass every check, `quarters` included.

### Pages made from the data
`build_stats.py` also writes a tiny stub page for each game, player, team and
archive season into `_games/`, `_players/`, `_teams/` and `_archive/` (git-ignored,
rewritten every run). A stub is only front matter (season, id, title); the
layouts read everything else from `_data/computed`. Games and archive pages
exist for every season the Archive lists (game ids start with their date, so
they must be unique across those seasons: the script checks); players and teams
only for the active season, because ids like `dave-m` repeat across seasons.
Past seasons therefore show names without links to player or team pages.

### Gym
A game's gym is the `gym` cell in `schedule.csv`; a blank cell means the
season's `gym` from `seasons.yml` (St. Pat's). There are no courts. Pages show
the gym in the week heading and the next-game panel.

### Calendars
`build_stats.py` also writes `calendar/<team id>.ics` and `calendar/league.ics`
(git-ignored, rewritten every run, published at `/calendar/...`) through
`scripts/calendars.py`. They always hold the **current** season, even in sample
mode, so nobody subscribes to made-up games. One event per game (UID from the
`game_id`, so subscribed calendars update in place), 90 minutes long (the gap
between the printed start times), at the game's gym, Eastern time. Cancelled
games stay in the feed as cancelled; played games carry the final score. A
playoff game with placeholder teams is only in `league.ics` until its row names
the teams; then it joins those two teams' calendars. The
Schedule page lists every team's calendar and the league's; a team page shows
its own (with a Calendar button beside the team name) when that team is in the
current season. Each calendar has three links: webcal:// (Apple Calendar and
Outlook subscribe), Google Calendar's `render?cid=` add-by-URL screen (Google
subscribes too, and refreshes on its own schedule, usually within a day), and
the plain .ics download (a one-time copy).

### Cancelled games
A row with `status` `cancelled` stays on the Schedule with a "Cancelled" badge,
and the team pages leave it out of their upcoming games. It never counts in any
stat, and the next game day skips it. A game file for it fails the check. A game
day whose games are all cancelled is headed by its date and the badge, with no
week number, and moves to Results. A make-up game is a new row; a moved game
keeps its row with a new date, time and `game_id`.

### Score sheet photos
`score_sheet_links: true` in `_config.yml` makes the build copy the photos in
`sheets/` to the published site and shows a "Score sheet photo" link on the box
score. It stays **off**: the league keeps the photos in the repo (which is
public on GitHub) but not on the site. The build script processes every season
listed here and must not fail on one with no games yet.

### The real season before the first game
`data/2026-27/` has the real teams and the full schedule, both from the
league's updated printed schedule (`Masters_Basketball_Schedule_2026-27_UPDATED.pdf`):
- **Teams:** Bay City Bears (`bb`, BB), Dam Nation (`dn`, DN), Floor Generals
  (`fg`, FG), Hustle (`hu`, HU) and Nor'Westers (`nw`, NW). The codes were made
  for the site and approved.
- **Colours** (from the league), each matched to the nearest site colour slot:
  Bay City Bears red (1), Dam Nation blue (2), Floor Generals green (3),
  Nor'Westers orange → gold (4), Hustle black → purple (5). Black and orange
  would need new `--mb-team-N` values in `brand/css/brand.css`.
- **Schedule:** 20 Saturdays, Oct 17 to Apr 17, at St. Pat's (Weeks 1 to 20).
  Two games each morning, at 9:45 AM (`-g1`) and 11:15 AM (`-g2`), and one team
  has the bye. Each team plays 16 games and meets every other team 4 times.
  Weeks with no games on the printed schedule are simply skipped.
- **Home and away:** the printed schedule has none. The team listed first is in
  the `home` column, but the site never says "home" or "away": the player game
  log always says "vs".
- **Playoffs** (`type: playoff`, with the league's game numbers in `round`):
  - Wed Apr 21, 7:30 PM: Play-in (G41), TBD vs TBD (weeks 21 to 23)
  - Sat Apr 24, 9:45 AM: Semifinal (G42), 2nd vs 3rd
  - Sat Apr 24, 11:15 AM: Semifinal (G43), 1st vs Winner G41
  - Wed Apr 28, 7:30 PM: Championship (G44), Winner G42 vs Winner G43

  Until the teams are known, `home` and `away` hold these placeholders (TBD, a
  place like `2nd`, or `Winner G41`/`Loser G41`; only playoff rows may). The
  site shows them as written. Replace them with team ids as the standings and
  results settle; a game file can't be added until its row names both teams.

- **Gym address:** `gym_address` in `seasons.yml` (621 Selkirk St S, Thunder
  Bay, ON P7E 1T9) goes into the calendar events' location.

Still to come: the rosters. `players.yml` is an empty list (`[]`), so team
pages say "No players listed yet" and there are no player pages. (A `display`
of exactly `[placeholder]` still passes the "First L." check, if a placeholder
row is ever useful.) `games/` and `sheets/` are empty.

### Team colours
`colour_slot` (1-5) picks `--mb-team-N` in `brand/css/brand.css`, which holds
the light and dark versions. Templates only use the variable. `colour_light`
and `colour_dark` are kept as a record of the hex values and should match
`brand.css`.

### Game file
A game file is a digital copy of the paper score sheet (form MBL-SS6), box for
box. **The full format, every check and the problem paths are in
[`docs/game-file-format.md`](../docs/game-file-format.md).** In short:

```yaml
game_id: 2026-10-17-g1
form: MBL-SS6
status: final            # final in games/, draft in drafts/
home: aa
away: bb
teams:
  aa:
    players:             # roster rows in order: id, jersey, Here tick, circles, fouls
      - {player: al-a, num: 4, here: true, ft: MXM, fouls: 2}
running:                 # running score: total -> scorer's jersey number
  aa: {2: 4, 4: 10, 5: 4}
lines:                   # the end-of-quarter lines: running total at Q1-Q4
  aa: [5, 12, 17, 22]
boxes:                   # the score boxes as written
  aa: {q1: 5, q2: 12, q3: 17, q4: 22, ot: null, final: 22}
notes:                   # flagrant fouls (and other notes) from the Notes box
  - {team: aa, num: 4, q: 3, kind: flagrant, text: ...}
checked_by: Lee M.
```

- **Where:** finished games in `data/<season>/games/<game_id>.yml`
  (`status: final`); drafts in `data/<season>/drafts/` (never read by the
  build); photos in `data/<season>/sheets/<game_id>.jpg`.
- **Rules:** `scripts/sheet_rules.py`, the one place they live. Points come
  from running-score jumps; FTM/FTA from the circles (`M` made, `X` missed),
  never from the running score, because a free throw can be worth 1, 2 or 3;
  GP from `here`; fouls from `fouls`/`tech`; flagrants from `notes`; quarters
  from `boxes`.
- **Problems** are `{level, at, message}`. `at` is a path to one box
  (`running.bb.14`, `teams.aa.players.0.ft.2`, `boxes.bb.final`). The build
  fails on any error in a `games/` file and lists warnings.
- **The sheet's structure** (rows, circles, boxes, running-score pages) is
  `scripts/scoresheet/spec.json`, from `scoresheet.py --spec`.
- **A sub written in by hand** has `name: "Jim K."` and no `player` until they
  are in `players.yml` (`sub: true`, team, number). Allowed in drafts only.
- **Fixtures:** `tests/fixtures/sheets/` (shared with the entry page's JS rules, `tests/js/`).
- **The entry page** (`/enter/`, unlisted) opens drafts, published games or a
  local file as a copy of the paper sheet, checks it live with the same rules,
  and saves the file (download, copy, or GitHub's new-file page). See
  `docs/game-file-format.md` ("The entry page").

## IDs
- Team ids: two letters (`pa`, `cr`, `wf`, `lh`, `fw`). Player ids: first name
  plus last initial, lowercase (`dave-m`); add a number if two clash (`mike-r2`).
  More of the last name is also accepted (`kevin-mo`), but the display stays
  "First L.". Ids never change once a game uses them.
- A sub gets a player id the first time they appear, with `sub: true`. Their
  points count for them as a player. A sub's points still count toward the team
  score in that game.
- **Jersey number** (optional): `number: 23`, from 0 to 99 (write `"00"` in
  quotes, or YAML reads it as 0). Two regular players on a team can't share a
  number; a sub can wear any. The score sheets print it in the # box and sort
  each roster by it; without one the box is left blank to fill in. The site
  shows it before the name wherever a player appears ("#23 Dave M.";
  `_includes/player-name.html`). `players.yml` is the only place numbers live,
  so a changed number shows everywhere, past box scores included.
- **Same "First L." on one team:** both players must have a `number`, or the
  build stops; the number is what tells them apart on the site and the sheet.
  The sample seasons have made-up numbers; `data/2026-27/` has none until the
  league sends them.

## Stat rules
- **GP:** games where the player is listed on the sheet.
- **PPG:** points ÷ GP, one decimal. PPG leaderboards need `ppg_min_games`
  GP (from `seasons.yml`, 0 = none), capped at the games the player's team has
  played so far: min(ppg_min_games, team GP). Unranked players stay in the
  Stats table (`qualifies_ppg: false`, `ppg_games_needed`).
- **FT%:** FTM ÷ FTA, one decimal. FT% leaderboards need `ft_min_attempts` FTA
  (from `seasons.yml`, default 10).
- **Standings points** (regular season): 1 for each quarter won and 3 for
  winning the game, so 7 at most. A tied quarter gives neither team a point and
  overtime isn't a quarter (both assumed, to be confirmed by the league).
  Constants `POINTS_PER_QUARTER` and `POINTS_PER_WIN` in `build_stats.py`.
- **Standings:** sorted by points. Show PTS, W, L, QW (quarters won), PCT
  (`.857` style), PF, PA, DIFF. No games-behind column.
- **Tiebreakers:** `[placeholder]`, not yet decided by the league. Until then
  teams level on points are ordered by head-to-head, then point differential,
  and the site says so under the standings on Home (shown when a tie was
  broken this way).
  Head-to-head is win % in games among all the tied teams, and is skipped if
  any tied team hasn't played the others yet. Ties left after that go by name.
- **Rounding:** PPG, FT% and PCT round half up (20.15 → 20.2). Rankings use the
  exact values, and players with exactly equal values share a rank.
- **Playoffs:** stored with `type: playoff`, shown separately, never counted in
  regular-season stats or standings. A playoff game is decided by its winner
  alone: no standings points (its box score still shows the score by quarter).
- **Flagrant fouls** count like technicals: the whole season, playoffs included
  (`flagrant`, `flagrant_playoff`, `flagrant_games` in `players.json`; the
  `flagrants` list in `leaders.json`). They show on the player page (a line
  under the tiles, a Flagrant badge in the game log) and in a list at the bottom
  of the Stats page, under the technical fouls.
- **Technical fouls** are the exception: a player's season total counts every
  game, playoffs included (`tech`, `tech_playoff`, `tech_games` in
  `players.json`; the list in `leaders.json` as `technicals`). They show on the
  player page (a Techs tile, and a badge on each game with one) and in a list at
  the very bottom of the Stats page. What happens after a number of technicals
  is an open question; the site only counts them.
- **Personal fouls** (`pf`) are kept in the computed data (regular season, like
  the other stats) but shown nowhere.

## Sample data
Until real games exist, generate a believable fake season: the 5 sample teams
from the mockups, about 10 players each, 8 weeks played, and the numbers that
appear in the mockups (Port Arthur 6–1, Dave M. 20.1 PPG, and so on). Put it in
`data/sample-2026-27/` so it is easy to delete.

`scripts/make_sample_season.py` writes it (5 teams, 9 players and a sub each,
16 games over 8 weeks with quarter totals and a few flagrant fouls, an
upcoming night with two drafts in `drafts/` for trying the entry page (one
with two review flags and a sub written in by hand, one with errors), and enough free throws that 16 players clear the 10-FTA
minimum and 34 don't). The quarter splits are tried until the standings by
points keep the mockup order (Port Arthur, Current River, Westfort, Lakehead,
Fort William), with a fixed seed so the files are
the same every run, and checks the result against the mockup numbers. To
remove it: delete the folder and its entry in `seasons.yml`.
