# Open questions

The site shows a visible `[placeholder]` for each of these until it's answered.

| Question | Where it shows | Answer |
|---|---|---|
| Domain name | `_config.yml` (`url`), `CNAME`, share tags | `mastersbasketball.ca` (Porkbun). DNS steps in `docs/domain.md` |
| GitHub organization name | repo, Pages address | `tb-masters-basketball`, repo `website` |
| Gym name and courts | Next game panel, Schedule | St. Pat's (spelled as on the league's printed schedule), no courts. A game's gym is read from `schedule.csv` (blank = season gym) |
| Real team names, short codes and colours | Everywhere; the five in the mockups are samples | From the printed schedule: Bay City Bears, Dam Nation, Floor Generals, Hustle, Nor'Westers. Codes BB, DN, FG, HU, NW. Colours: the five site colour slots in alphabetical order (can be swapped later in `teams.yml`) |
| The real 2026-27 rosters: every player as "First L." with their team, and which players are subs (`data/2026-27/players.yml` has one `[placeholder]` row per team until then) | Team pages, player pages | |
| The real 2026-27 schedule: first game day and every game day's games and times | Home, Schedule | In `data/2026-27/schedule.csv`, from the printed schedule: 20 Saturdays, Oct 3 to Apr 3, games at 9:45 AM and 11:00 AM. Oct 3 was cancelled; the first game day is Oct 17 |
| Standings tiebreakers (including three-way ties) | Standings note | |
| Minimum games to appear on the PPG leaderboard (none for now, so a sub with one big game could lead) | Home, Stats | |
| Playoff format (teams, single game or series) | Schedule, Archive | Dates known: April 10, 17 and 24, 2027 (printed schedule). Format and matchups still open |
| League contact for the footer's "Contact the league" link (an email address or a form). Set `contact_url` in `_config.yml`; with it blank the footer shows no contact link | Footer | |
| Can score sheet photos be published on the box score pages? (They may show full names; players are only ever "First L.") | Box score | Not for now: `score_sheet_links: false`. Revisit after seeing a real sheet |
| Do subs' points count only for the player? (assumed yes) | Stats | |
| Score sheet layout (photo of a filled-in sheet) | `/record-game` skill | |
| How long is a game? Calendar events last 75 minutes for now, the gap between the 9:45 and 11:00 starts | Team calendars | |
| Gym address (calendar events only say "St. Pat's") | Team calendars | |
| Badge colourway for jerseys/merch (navy, blue or light) | Not on the site | |

## Site decisions waiting on you

These aren't league facts, so nothing on the site shows a placeholder for them.
They came out of the full-site QA (`docs/qa/report.md`).

| Question | Current state | Answer |
|---|---|---|
| Keep the QA screenshot sets in the repo? | `docs/qa/before/` and `after/` hold about 41 MB of PNGs. They could be cut down to the six contact sheets; `scripts/screenshot_all.py` recreates the rest | |
| "Game night" wording | Games are Saturday mornings | Changed to "game day" everywhere |
| Home and away | The printed schedule has no home team | The site always says "vs"; the first-listed team is in the `home` column |
| Theme toggle for screen readers | The label changes ("Switch to dark theme" / "Switch to light theme") instead of a fixed label with `aria-pressed`. Both are valid; using both at once contradicts itself | |
