# League data

Everything the site shows comes from these files. One folder per season, named
like `2026-27`. `scripts/build_stats.py` turns them into `_data/computed/`.

## Files
```
data/seasons.yml              list of seasons, newest first; marks the current one
data/2026-27/
  teams.yml                   id, name, short (2 letters), colour_slot, colour_light, colour_dark
  players.yml                 id, display (First L.), team, sub (true/false)
  schedule.csv                game_id,date,time,gym,home,away,type,week,status (gym blank: the season's gym; no courts;
                              status blank, or `cancelled`; the status column may be left out)
  games/2026-12-03-g1.yml     one file per played game (format below)
  sheets/2026-12-03-g1.jpg    photo of the paper score sheet, kept for checking
```

### seasons.yml
```yaml
- id: 2026-27          # folder name under data/
  label: "2026-27"     # what the site shows
  current: true        # exactly one season is current: the real one
  gym: "St. Pat's"
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
`game_id`, so subscribed calendars update in place), 75 minutes long (the gap
between the printed start times), at the game's gym, Eastern time. Cancelled
games stay in the feed as cancelled; played games carry the final score. The
Schedule page lists every team's calendar and the league's; a team page lists
its own when that team is in the current season.

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
score. It is **off** until the league has checked that the sheets are fine to
publish (they may show full names, and players are only ever "First L."). The build script processes every season
listed here and must not fail on one with no games yet.

### The real season before the first game
`data/2026-27/` has the real teams and the full regular-season schedule, both
from the league's printed schedule (`Masters_League_Print_Schedule_2026-27.pdf`):
- **Teams:** Bay City Bears (`bb`, BB), Dam Nation (`dn`, DN), Floor Generals
  (`fg`, FG), Hustle (`hu`, HU) and Nor'Westers (`nw`, NW). The codes were made
  for the site and approved. Colour slots go in alphabetical order (approved; a
  slot can be swapped any time in `teams.yml`).
- **Schedule:** 20 Saturdays, Oct 3 to Apr 3, at St. Pat's. Two games each
  morning, at 9:45 AM (`-g1`) and 11:00 AM (`-g2`), and one team has the bye.
  Oct 3 was cancelled (`status: cancelled`, week `0`), so Oct 17 is Week 1 and
  Apr 3 is Week 19. Weeks with no games on the printed schedule (Thanksgiving,
  the holidays, Feb 13, March break) are simply skipped.
- **Home and away:** the printed schedule has none. The team listed first is in
  the `home` column, but the site never says "home" or "away": the player game
  log always says "vs".
- **Playoffs:** April 10, 17 and 24, 2027. They aren't in `schedule.csv` yet,
  because the playoff format and matchups aren't known.

Still placeholders: one `[placeholder]` player per team (a `display` of exactly
`[placeholder]` passes the "First L." check for this reason). `games/` and
`sheets/` are empty.

### Team colours
`colour_slot` (1-5) picks `--mb-team-N` in `brand/css/brand.css`, which holds
the light and dark versions. Templates only use the variable. `colour_light`
and `colour_dark` are kept as a record of the hex values and should match
`brand.css`.

### Game file
```yaml
game_id: 2026-12-03-g1
date: 2026-12-03
home: pa            # team ids
away: lh
type: regular       # regular | playoff
final: {pa: 71, lh: 64}
lines:              # one per player listed on the sheet
  - {player: dave-m, team: pa, pts: 24, ftm: 6, fta: 7}
  - {player: greg-t, team: pa, pts: 12, ftm: 2, fta: 2}
```
Checks the build script must enforce (and fail loudly on):
- each team's player points add up to its final score
- `ftm <= fta`, and all numbers are 0 or more
- every player and team id exists
- `game_id` matches the file name and a row in `schedule.csv`

It also checks: the date, home, away and type match `schedule.csv`; the final
score isn't tied; no player is listed twice in a game; `ftm` isn't more than
`pts` and `pts - ftm` isn't 1 (field goals can't add up to 1 point); display
names are "First L."; ids are unique. It reports every problem at once and
writes nothing until all of them are fixed.

## IDs
- Team ids: two letters (`pa`, `cr`, `wf`, `lh`, `fw`). Player ids: first name
  plus last initial, lowercase (`dave-m`); add a number if two clash (`mike-r2`).
- A sub gets a player id the first time they appear, with `sub: true`. Their
  points count for them as a player. A sub's points still count toward the team
  score in that game.

## Stat rules
- **GP:** games where the player is listed on the sheet.
- **PPG:** points ÷ GP, one decimal.
- **FT%:** FTM ÷ FTA, one decimal. FT% leaderboards need 10 or more FTA.
- **Standings:** sorted by win %. Show W, L, PCT (`.857` style), GB, PF, PA, DIFF.
- **Tiebreakers:** `[placeholder]`, not yet decided by the league. Until then
  use head-to-head, then point differential, and say so under the standings on
  Home (shown when a tie was broken this way).
  Head-to-head is win % in games among all the tied teams, and is skipped if
  any tied team hasn't played the others yet. Ties left after that go by name.
- **Rounding:** PPG, FT% and PCT round half up (20.15 → 20.2). Rankings use the
  exact values, and players with exactly equal values share a rank.
- **Playoffs:** stored with `type: playoff`, shown separately, never counted in
  regular-season stats or standings.

## Sample data
Until real games exist, generate a believable fake season: the 5 sample teams
from the mockups, about 10 players each, 8 weeks played, and the numbers that
appear in the mockups (Port Arthur 6–1, Dave M. 20.1 PPG, and so on). Put it in
`data/sample-2026-27/` so it is easy to delete.

`scripts/make_sample_season.py` writes it (5 teams, 9 players and a sub each,
16 games over 8 weeks, an upcoming night, and enough free throws that 16
players clear the 10-FTA minimum and 34 don't), with a fixed seed so the files are
the same every run, and checks the result against the mockup numbers. To
remove it: delete the folder and its entry in `seasons.yml`.
