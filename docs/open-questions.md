# Open questions

The site shows a visible `[placeholder]` for each of these until it's answered.

| Question | Where it shows | Answer |
|---|---|---|
| Domain name | `_config.yml` (`url`), `CNAME`, share tags | `mastersbasketball.ca` (Porkbun). DNS steps in `docs/domain.md` |
| GitHub organization name | repo, Pages address | `tb-masters-basketball`, repo `website` |
| Gym name and courts | Next game panel, Schedule | St. Pat's (spelled as on the league's printed schedule), no courts. A game's gym is read from `schedule.csv` (blank = season gym) |
| Real team names, short codes and colours | Everywhere; the five in the mockups are samples | From the printed schedule: Bay City Bears, Dam Nation, Floor Generals, Hustle, Nor'Westers. Codes BB, DN, FG, HU, NW. Colours from the league: Bears red, Dam Nation blue, Floor Generals green, Hustle black, Nor'Westers orange. Each uses the nearest site colour: Hustle shows purple and Nor'Westers gold. Decided to leave it that way (October 2026) |
| The real 2026-27 rosters: every player as "First L." with their team, and which players are subs (`data/2026-27/players.yml` is empty until then; team pages say "No players listed yet") | Team pages, player pages | In (October 2026): 58 players from the league's team list, all regulars (no subs listed). Jersey numbers still missing for Dam Nation and Bay City Bears |
| The real 2026-27 schedule: first game day and every game day's games and times | Home, Schedule | In `data/2026-27/schedule.csv`, from the updated printed schedule: 20 Saturdays, Oct 17 to Apr 17, games at 9:45 AM and 11:15 AM |
| Standings tiebreakers (including three-way ties) for teams level on points | Standings note, League rules | |
| A tied quarter: does either team get a standings point? | Standings, League rules | Zero for both for now (the site's rule); still open for the league |
| Overtime: does it count as a quarter for standings points? | Standings, League rules | Assumed: no, it only decides who wins the game (to confirm) |
| Minimum games to appear on the PPG leaderboard | Home, Stats, player pages | 3 games (`ppg_min_games: 3` in `data/seasons.yml`), or all of the team's games while it has played fewer than 3 |
| Playoff format (teams, single game or series) | Schedule, Archive | From the updated schedule: play-in (G41) Wed Apr 21 7:30 PM, matchup TBD; semifinals Sat Apr 24 (2nd vs 3rd at 9:45, 1st vs Winner G41 at 11:15); championship Wed Apr 28 7:30 PM. Single games. The play-in matchup stays TBD; it goes into `schedule.csv` when it's known |
| League contact for the footer's "Contact the league" link (an email address or a form). Set `contact_url` in `_config.yml`; with it blank the footer shows no contact link | Footer | mastersbasketballthunderbay@gmail.com (October 2026), as a `mailto:` link |
| Can score sheet photos be published on the box score pages? (They may show full names; players are only ever "First L.") | Box score | Keep them in the repo (`data/<season>/sheets/`), not on the site: `score_sheet_links` stays `false`. The sheets print "First L." names, so they're fine to keep. The repo is public, so the photos can be seen on GitHub |
| Do subs' points count only for the player? (assumed yes) | Stats | Yes: a sub's points count for them and toward their team's score that day. Subs are expected to be rare (new players join the roster instead) |
| Score sheet layout | Schedule page, the entry page, `/record-game` | The league's form MBL-SS6 (quarters; it replaced MBL-SS5, which had halves), made by `scripts/scoresheet/scoresheet.py` (see its README). `/record-game` was tested on the four practice games in `tests/fixtures/record-game/`, copied out by hand and photographed (October 2026). Photos of real games' sheets will still help |
| What is a free throw worth? | Score sheet "How to mark", game file checks | 1, 2 or 3 points under league rules (confirmed October 2026). So the site never takes free throws from the running score: FTM and FTA come only from the circles. Rule 12: one free throw for a shooting foul, worth what the shot would have been; after a made basket, and for bonus and penalty free throws, one point |
| Player jersey numbers (`number:` in `data/2026-27/players.yml`) | Score sheets' # box; "#23 Dave M." wherever a player is named | Not yet. Until then the # boxes print empty and are filled in by hand |
| What happens after technical fouls: two in one game (ejection?), and a number in a season (suspension?) | League rules page, player page, Stats | Code of conduct 4: T1 sits the player for the rest of the quarter; T2 in a game is an ejection; 2 in a season a one-game suspension, 3 and 4 add playoff games, 5 ends the season. The site counts technicals (playoffs included) but flags nothing yet |
| The league rules themselves | League rules page (`rules/index.md`) | The league's draft playing rules and player code of conduct (October 2026). Not yet marked approved (`updated:` blank) |
| A regular-season game still tied after one overtime (rule 4: "may be recorded as a tie") | Standings, box score, game file checks | Ties are allowed: quarters give their points, overtime none, no win points. The standings have a T column; PCT counts a tie as half a win (October 2026) |
| Forfeits (rule 24: recorded as Q1-Q4 1-0) | Standings, Schedule | A nearly blank game file, `forfeit: <team>`, counted as 1-0 each quarter: 7 points and a win to the other team, no player stats (October 2026) |
| Timeouts (rule 9: two per half, one per overtime) | Score sheet | The sheet prints them that way: H1 two circles, H2 two, OT one (October 2026) |
| Reseeding after 6 games (rule 31) | Schedule | Probably no longer done; to confirm |
| How long is a game? | Team calendars | 90 minutes (calendar events last 90 minutes) |
| Gym address | Team calendars | 621 Selkirk St S, Thunder Bay, ON P7E 1T9 (`gym_address` in `data/seasons.yml`) |

## Site decisions waiting on you

These aren't league facts, so nothing on the site shows a placeholder for them.
They came out of the full-site QA (`docs/qa/report.md`).

| Question | Current state | Answer |
|---|---|---|
| Keep the QA screenshot sets in the repo? | `docs/qa/before/` and `after/` hold about 41 MB of PNGs. They could be cut down to the six contact sheets; `scripts/screenshot_all.py` recreates the rest | Removed (October 2026). `docs/qa/report.md` stays; the screenshots are in git history, and `screenshot_all.py` makes a fresh set |
| "Game night" wording | Games are Saturday mornings | Changed to "game day" everywhere |
| Home and away | The printed schedule has no home team | The site always says "vs"; the first-listed team is in the `home` column |
| Two players with the same first name and last initial | Ids can't clash (`mike-r`, `mike-r2`), and both display as "Mike R." | Jersey numbers: the site shows "#23 Mike R.", and the build stops if two players on one team share a "First L." without numbers. `/record-game` and the entry page tell them apart by jersey number |
| Theme toggle for screen readers | The label changes ("Switch to dark theme" / "Switch to light theme") instead of a fixed label with `aria-pressed`. Both are valid; using both at once contradicts itself | Keep it as it is: the changing label |
