# League data

Everything the site shows comes from these files. One folder per season, named
like `2026-27`. `scripts/build_stats.py` turns them into `_data/computed/`.

## Files
```
data/seasons.yml              list of seasons, newest first; marks the current one
data/2026-27/
  teams.yml                   id, name, short (2 letters), colour_slot, colour_light, colour_dark
  players.yml                 id, display (First L.), team, sub (true/false)
  schedule.csv                game_id,date,time,court,home,away,type,week (court blank: St. Pats has one court)
  games/2026-12-03-g1.yml     one file per played game (format below)
  sheets/2026-12-03-g1.jpg    photo of the paper score sheet, kept for checking
```

### seasons.yml
```yaml
- id: 2026-27          # folder name under data/
  label: "2026-27"     # what the site shows
  current: true        # exactly one season is current: the real one
  gym: "St. Pats"
- id: sample-2026-27
  label: "2026-27"
  sample: true         # fake data; never `current`, at most one
  gym: "St. Pats"
```
`sample_data: true` in `_config.yml` makes every page read the `sample` season
and show a "Preview with sample data" banner. With it off, pages read the
`current` season and the banner goes. The build script processes every season
listed here and must not fail on one with no games yet.

### The real season before the first game
`data/2026-27/` holds `[placeholder]` rows: five teams (`[Team A]`...), one
`[placeholder]` player per team, a `schedule.csv` with only its header row (no
dates are invented), an empty `games/` and `sheets/`. A player `display` of
exactly `[placeholder]` passes the "First L." check for this reason. Replace
the rows with real ones as the league decides.

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
