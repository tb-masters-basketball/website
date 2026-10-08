# Open questions

The site shows a visible `[placeholder]` for each of these until it's answered.

| Question | Where it shows | Answer |
|---|---|---|
| Domain name | `_config.yml` (`url`), `CNAME`, share tags | `masterbasketball.ca` (Porkbun). DNS steps in `docs/domain.md` |
| GitHub organization name | repo, Pages address | `tb-masters-basketball`, repo `website` |
| Gym name and courts | Next game panel, Schedule | St. Pats, no courts. A game's gym is read from `schedule.csv` (blank = season gym) |
| Real team names, short codes and colours | Everywhere; the five in the mockups are samples | |
| The real 2026-27 rosters: every player as "First L." with their team, and which players are subs (`data/2026-27/players.yml` has one `[placeholder]` row per team until then) | Team pages, player pages | |
| The real 2026-27 schedule: first game night and every game night's games and times (`data/2026-27/schedule.csv` is empty until then, so Home says "Not scheduled yet") | Home, Schedule | |
| Standings tiebreakers (including three-way ties) | Standings note | |
| Minimum games to appear on the PPG leaderboard (none for now, so a sub with one big game could lead) | Home, Stats | |
| Playoff format (teams, single game or series) | Schedule, Archive | |
| League contact for the footer's "Contact the league" link (an email address or a form). Set `contact_url` in `_config.yml`; with it blank the footer shows no contact link | Footer | |
| Can score sheet photos be published on the box score pages? (They may show full names; players are only ever "First L.") | Box score | Not for now: `score_sheet_links: false`. Revisit after seeing a real sheet |
| Do subs' points count only for the player? (assumed yes) | Stats | |
| Score sheet layout (photo of a filled-in sheet) | `/record-game` skill | |
| Badge colourway for jerseys/merch (navy, blue or light) | Not on the site | |

## Site decisions waiting on you

These aren't league facts, so nothing on the site shows a placeholder for them.
They came out of the full-site QA (`docs/qa/report.md`).

| Question | Current state | Answer |
|---|---|---|
| Keep the QA screenshot sets in the repo? | `docs/qa/before/` and `after/` hold about 41 MB of PNGs. They could be cut down to the six contact sheets; `scripts/screenshot_all.py` recreates the rest | |
| Theme toggle for screen readers | The label changes ("Switch to dark theme" / "Switch to light theme") instead of a fixed label with `aria-pressed`. Both are valid; using both at once contradicts itself | |
