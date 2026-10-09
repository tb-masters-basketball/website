# Open questions

The site shows a visible `[placeholder]` for each of these until it's answered.

| Question | Where it shows | Answer |
|---|---|---|
| Domain name | `_config.yml` (`url`), `CNAME`, share tags | `mastersbasketball.ca` (Porkbun). DNS steps in `docs/domain.md` |
| GitHub organization name | repo, Pages address | `tb-masters-basketball`, repo `website` |
| Gym name and courts | Next game panel, Schedule | St. Pat's (spelled as on the league's printed schedule), no courts. A game's gym is read from `schedule.csv` (blank = season gym) |
| Real team names, short codes and colours | Everywhere; the five in the mockups are samples | From the printed schedule: Bay City Bears, Dam Nation, Floor Generals, Hustle, Nor'Westers. Codes BB, DN, FG, HU, NW. Colours from the league: Bears red, Dam Nation blue, Floor Generals green, Hustle black, Nor'Westers orange. Each uses the nearest site colour: Hustle shows purple and Nor'Westers gold until black and orange are added to `brand/css/brand.css` |
| The real 2026-27 rosters: every player as "First L." with their team, and which players are subs (`data/2026-27/players.yml` is empty until then; team pages say "No players listed yet") | Team pages, player pages | Not yet; rosters start empty |
| The real 2026-27 schedule: first game day and every game day's games and times | Home, Schedule | In `data/2026-27/schedule.csv`, from the updated printed schedule: 20 Saturdays, Oct 17 to Apr 17, games at 9:45 AM and 11:15 AM |
| Standings tiebreakers (including three-way ties) | Standings note | |
| Minimum games to appear on the PPG leaderboard (none for now, so a sub with one big game could lead) | Home, Stats | |
| Playoff format (teams, single game or series) | Schedule, Archive | From the updated schedule: play-in (G41) Wed Apr 21 7:30 PM, matchup TBD; semifinals Sat Apr 24 (2nd vs 3rd at 9:45, 1st vs Winner G41 at 11:15); championship Wed Apr 28 7:30 PM. Single games. The play-in matchup stays TBD; it goes into `schedule.csv` when it's known |
| League contact for the footer's "Contact the league" link (an email address or a form). Set `contact_url` in `_config.yml`; with it blank the footer shows no contact link | Footer | |
| Can score sheet photos be published on the box score pages? (They may show full names; players are only ever "First L.") | Box score | Not for now: `score_sheet_links: false`. Revisit after seeing a real sheet |
| Do subs' points count only for the player? (assumed yes) | Stats | |
| Score sheet layout | `/record-game` skill, Schedule page | The league's form MBL-SS5, made by `scripts/scoresheet/scoresheet.py` (see its README). Still useful: a photo of a filled-in sheet, to build and test `/record-game` |
| Player jersey numbers (for the score sheets' # box; `number:` in `data/2026-27/players.yml`) | Score sheets | Not yet. Until then the # boxes print empty and are filled in by hand |
| What happens after technical fouls: two in one game (ejection?), and a number in a season (suspension?) | League rules page, player page, Stats | The site counts each player's technicals (playoffs included) but flags nothing yet |
| The league rules themselves | League rules page (`rules/index.md`) | Sections are in place, each with a `[placeholder]` |
| How long is a game? | Team calendars | 90 minutes (calendar events last 90 minutes) |
| Gym address | Team calendars | 621 Selkirk St S, Thunder Bay, ON P7E 1T9 (`gym_address` in `data/seasons.yml`) |
| Badge colourway for jerseys/merch (navy, blue or light) | Not on the site | |

## Site decisions waiting on you

These aren't league facts, so nothing on the site shows a placeholder for them.
They came out of the full-site QA (`docs/qa/report.md`).

| Question | Current state | Answer |
|---|---|---|
| Keep the QA screenshot sets in the repo? | `docs/qa/before/` and `after/` hold about 41 MB of PNGs. They could be cut down to the six contact sheets; `scripts/screenshot_all.py` recreates the rest | |
| "Game night" wording | Games are Saturday mornings | Changed to "game day" everywhere |
| Home and away | The printed schedule has no home team | The site always says "vs"; the first-listed team is in the `home` column |
| Two players with the same first name and last initial | Ids can't clash (`mike-r`, `mike-r2`), but both display as "Mike R.": fine on different teams, identical on the same team. Options: two letters of the last name ("Mike Ro."), or a jersey number. See the README's to-do | |
| Theme toggle for screen readers | The label changes ("Switch to dark theme" / "Switch to light theme") instead of a fixed label with `aria-pressed`. Both are valid; using both at once contradicts itself | |
