# League data

Everything the site shows comes from these files. One folder per season, named
like `2026-27`. `scripts/build_stats.py` turns them into `_data/computed/`.

## Files
```
data/seasons.yml              list of seasons, newest first; marks the current one
data/2026-27/
  teams.yml                   id, name, short (2 letters), colour_light, colour_dark
  players.yml                 id, display (First L.), team, sub (true/false)
  schedule.csv                game_id,date,time,court,home,away,type,week
  games/2026-12-03-g1.yml     one file per played game (format below)
  sheets/2026-12-03-g1.jpg    photo of the paper score sheet, kept for checking
```

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
  use head-to-head, then point differential, and say so on the standings page.
- **Playoffs:** stored with `type: playoff`, shown separately, never counted in
  regular-season stats or standings.

## Sample data
Until real games exist, generate a believable fake season: the 5 sample teams
from the mockups, about 10 players each, 8 weeks played, and the numbers that
appear in the mockups (Port Arthur 6–1, Dave M. 20.1 PPG, and so on). Put it in
`data/sample-2026-27/` so it is easy to delete.
