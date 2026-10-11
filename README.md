# Masters Basketball League · Thunder Bay

The league's website: standings, schedule, team pages, player stats and past
seasons. Live at **https://mastersbasketball.ca/**.

It is a static site. Volunteers copy each paper score sheet into a small text
file in `data/`, box for box, usually on the site's entry page (`/enter/`),
which checks it as they type. A Python script checks the files again and works
out every number. Jekyll turns
the numbers into pages, and GitHub Actions publishes them to GitHub Pages
whenever `main` changes.

- **Keeping the stats up to date** (for volunteers, no coding needed):
  [`docs/stats-workflow.md`](docs/stats-workflow.md)
- **Rules for anyone changing the code**, including Claude Code: [`CLAUDE.md`](CLAUDE.md)

---

## To do

### 1. Open questions

The full list, with answers so far, is in
[`docs/open-questions.md`](docs/open-questions.md). Still open:

**League decisions:**
- [ ] **Rosters for 2026-27.** Every player as "First L.", their team, and who
      is a sub. `data/2026-27/players.yml` is empty until then, so team pages
      say "No players listed yet".
- [ ] **Jersey numbers for 2026-27.** They go in `players.yml` as `number:`,
      show as "#23 Dave M." wherever a player is named, and print in the score
      sheets' # box (blank until then). Two players on one team with the same
      "First L." must both have one, or the build stops.
- [ ] **League rules.** `rules/index.md` (the League rules page, linked in the
      footer) has every section with a `[placeholder]` to replace.
- [ ] **Technical foul rules.** What happens after two in a game, or a number
      in a season? The site counts technicals (playoffs included) but flags
      nothing until this is decided.
- [ ] **Standings tiebreakers**, including three-way ties, for teams level on
      points. Until then the site uses head-to-head, then point differential,
      and says so under the standings.
- [ ] **Tied quarters and overtime (to confirm).** Standings points are 1 per
      quarter won and 3 per win. The site assumes a tied quarter gives neither
      team a point, and that overtime isn't a quarter.
- [ ] **Playoff matchups.** The play-in (G41, Wed Apr 21) is "TBD vs TBD" in
      `schedule.csv`. Fill in each playoff row as the standings decide it.
- [ ] **Free throws worth 2 or 3.** Confirmed that a free throw can be worth
      1, 2 or 3 points (so the site takes FTM and FTA only from the circles);
      the League rules page still needs the rule for when.
- [ ] **League contact for the footer.** Set `contact_url` in `_config.yml`
      (an email `mailto:` link or a form). The footer shows no contact link
      while it's blank. A form (e.g. a Google Form) keeps the address away
      from spam bots, which read email links straight from the page.

### 2. Record a game from a photo of the score sheet (`/record-game`)

Today a game is typed up on the entry page (`/enter/`), box by box, with the
photo beside it ([how](docs/stats-workflow.md#enter-or-check-a-game-on-the-entry-page)).
The goal is a Claude Code command, `/record-game`, that reads the photo and
does the typing: it writes a **draft** with every box it isn't sure of flagged,
and a person checks the draft on the entry page and saves it as final. The
command never publishes a game by itself.

**Already in place** (what the command builds on):
- **The sheet:** form MBL-SS6 from `scripts/scoresheet/scoresheet.py`
  ([README](scripts/scoresheet/README.md)), with corner squares for
  straightening a photo. Game ID, date, time and the regular players (in
  jersey order) are printed on it, so most of the header and the rosters are
  known before the photo is read. Its structure (rows, circles, boxes,
  running-score pages per layout) is in `scripts/scoresheet/spec.json`.
- **The file it writes:** the game file, box for box
  ([`docs/game-file-format.md`](docs/game-file-format.md)), as a draft:
  `status: draft` in `data/<season>/drafts/<game_id>.yml`, with a `review`
  entry (`{at: running.lh.27, note: "23 or 28?"}`) for every doubtful box.
- **The checks:** `scripts/sheet_rules.py` gives every problem with the path of
  its box. The entry page runs the same rules (ported to JavaScript), lists
  drafts with their flag count, shows the photo beside the sheet, and has
  **Mark as checked** and **Save as final**.
- **Test material:** `tests/fixtures/sheets/` (eight small cases with expected
  results) and `tests/fixtures/record-game/`: four practice games, each with
  an answer key (`answer.yml`), a sheet filled in from it and an empty sheet
  ([README](tests/fixtures/record-game/README.md)).

**Still needed before building it:**
- [ ] **Photos to test on.** Print the four practice games' filled and empty
      sheets, have people copy each filled sheet onto its empty one by hand,
      and photograph the copies (flat, all four corner squares in view). Save
      them as `tests/fixtures/record-game/<game_id>/photo.jpg`. A photo of a
      real game's sheet will help too.
- [ ] **A way to check one file from the command line.** `build_stats.py
      --check` never reads drafts. Add `scripts/check_game.py <file>`: runs
      `sheet_rules.check` on one game file (draft or final) against its
      season and prints each problem with its box path. The command uses it,
      and so can anyone editing a file by hand.
- [ ] **A way to score a transcription.** `scripts/compare_game.py <draft>
      <answer.yml>`: lists every box that differs, and whether each was
      flagged for review. The goal: no wrong box that isn't flagged.

**What `/record-game` does:**
1. **Takes the photo(s)** of page 1 (and page 2 if the game used it) and
   finds the game: the printed Game ID, checked against `schedule.csv` (date
   and teams). It asks if they disagree.
2. **Reads every box** into the game file (field names as in the format doc):
   - each roster row: `num`, the **Here** tick (`here`), the circles in order
     (`ft`: `M` filled, `X` slashed), slashed foul boxes (`fouls`) and red T
     boxes (`tech`)
   - the running score: every filled box as `total: jersey number`, for both
     teams (page 2 carries on from 101)
   - `lines`: the running total each end-of-quarter line is drawn under, Q1 to
     Q4 (needed for a final file)
   - `boxes`: what's written in Q1 to Q4, OT and Final
   - `notes`: each Notes entry (team, number, quarter, `kind: flagrant` or
     `note`, the text), and the scorekeeper
3. **Matches rows to players** in `players.yml`. A printed row is a regular
   player (team, number and "First L." all on the sheet). A row written in by
   hand is a sub: match by team, "First L." and number; if there's no match,
   keep `name: "Jim K."` without a `player` id (a draft may) and say so. Never
   write a full name.
4. **Flags rather than guesses.** Every box it can't read with confidence gets
   a `review` entry with a short note. It doesn't change what's written to make
   the checks pass: a Final box that disagrees with the running score is
   copied as written, and the check says so.
5. **Runs the checks** (`scripts/check_game.py`) and reports them with the
   flags.
6. **Writes** the draft and the photo (`data/<season>/sheets/<game_id>.jpg`)
   and opens a pull request with both. Merging it publishes nothing: drafts
   are never built.
7. **A person finishes it on the entry page:** opens the draft (it's listed
   with its flag count), checks each flagged box against the photo, presses
   **Mark as checked**, fixes any errors, and saves it as final. That's a
   second pull request, the one that publishes the game. Then they delete the
   draft (the save dialog links to it).

It would live in `.claude/skills/record-game/SKILL.md` (or
`.claude/commands/record-game.md`). Test it on the practice photos with
`compare_game.py` before using it on real games. `docs/stats-workflow.md`
then gains a "Record a game from a photo" section, and its workflow diagram
loses the word "planned".

### 3. Build `players.yml` from the team rosters (`/build-roster`)

Rosters will arrive one team at a time, probably as a spreadsheet or CSV per
team, maybe as a photo or PDF. The goal is a Claude Code command,
`/build-roster`, like `/record-game`: give it a set of rosters and it updates
`data/<season>/players.yml` and opens a pull request. `players.yml` stays the
one source of truth for ids, display names and numbers.

1. **Read each roster:** first name, last name, jersey number, team, and
   whether the player is a sub. Ask about anything it can't read or any team
   it can't match to `teams.yml`.
2. **Match each row to an existing player** on the same team by "First L.",
   and if two share it, by number.
   - **Add only players who are new by name.** Existing ids are never
     rewritten, because every game file points at them.
   - **New ids** follow the usual rule: `dave-m`, then `dave-m2` for a second
     "Dave M." in the league. `dave-mo` style ids are also accepted.
   - **Update numbers** from the rosters (two regular players on a team
     can't share one; a sub can wear any). A number lives only in
     `players.yml`, so a change shows everywhere at once, past box scores
     included.
   - **Players missing from a roster** are listed for the volunteer to
     decide on, never deleted: their games still point at them.
3. **Keep only "First L."** in `players.yml`. Full last names are read for
   matching and never written to the repo (nor are the roster files).
4. **Run the checks** (`python scripts/build_stats.py --check`). They fail on a
   duplicate id, a number used twice on one team, and two players on one team
   with the same "First L." and no numbers to tell them apart.
5. **Show a summary to confirm** (added, number changes, not on a roster),
   then open a pull request. Merging it publishes the rosters.

It would live in `.claude/skills/build-roster/SKILL.md` (or
`.claude/commands/build-roster.md`). If the matching rules prove fiddly, a
small helper (`scripts/build_roster.py`, with tests) can do the matching and
id assignment so the command only reads the rosters and confirms.
`docs/stats-workflow.md` would gain an "Add the rosters" section.

### 4. Smaller follow-ups

- [ ] **Try "Save to GitHub" on a real game.** The entry page sends the whole
      file in the link to GitHub's new-file page. A 100-point game makes a
      link of about 6,300 characters; it couldn't be tested against GitHub
      itself. Past 8,000 the page copies the file and opens an empty new
      file instead (`MAX_URL` in `assets/js/sheet-rules.js`). If GitHub
      refuses a long link, lower that number.
- [ ] **Saving the photo is a separate step.** The entry page never uploads
      the photo, so it goes into `data/<season>/sheets/<game_id>.jpg` by hand
      (GitHub: *Add file → Upload files*). `/record-game` will add it with the
      draft.

---

## How the site works

### The big picture

```mermaid
flowchart LR
    A["data/<br/>seasons, teams, players,<br/>schedule, game files"] --> B["scripts/build_stats.py<br/>checks + calculates"]
    C["_config.yml<br/>switches"] --> B
    B --> D["_data/computed/<br/>JSON numbers"]
    B --> E["_games/ _players/<br/>_teams/ _archive/<br/>stub pages"]
    B --> F["calendar/*.ics"]
    B --> EN["enter/data/<br/>for the entry page"]
    EN --> G
    B --> S["scripts/make_score_sheets.sh<br/>score-sheets/*.pdf"]
    D --> G["Jekyll<br/>layouts + includes"]
    E --> G
    F --> G
    S --> G
    G --> H["_site/"]
    G --> PV["_site/preview/<br/>same pages, sample season"]
    PV --> I
    H --> I["link check"]
    I --> J["GitHub Pages<br/>mastersbasketball.ca"]
```

1. **People edit `data/`.** These files are the only source of truth: game
   results, players, the schedule.
2. **`scripts/build_stats.py` checks and calculates.** It reads every season,
   checks every rule, and stops with a list of every problem if anything is
   wrong. Otherwise it writes:
   - the numbers as JSON
   - one tiny "stub" page per game, player, team and archived season
   - the calendar files
3. **Jekyll builds the pages.** Templates read the JSON and the stubs and
   produce plain HTML in `_site/`. No number is typed into a template. A second
   build makes the hidden preview copy from the sample season in
   `_site/preview/` (`scripts/build_preview.sh`).
4. **A link check** (`scripts/check_links.sh`) fails the build if any page,
   image, stylesheet or script is missing.
5. **GitHub Actions publishes `_site/`** to GitHub Pages, but only from `main`
   and only when every step passed.

Everything in steps 2–3 is regenerated from scratch on every build. Nothing
generated is committed: `_data/computed/`, the stub folders, `calendar/`,
`score-sheets/`, `enter/data/`, `enter/sheet-spec.json` and `_site/` are all
git-ignored.

### Where the data lives

| File | What it holds | Edited by |
|---|---|---|
| `data/seasons.yml` | Every season, newest first. Marks which is `current`, which are sample (fake) data, the gym and its address, and the ranking minimums (`ppg_min_games`, `ft_min_attempts`) | hand, once a season |
| `data/<season>/teams.yml` | Team id (2 letters), name, 2-letter code, colour slot (1–5) | hand, once a season |
| `data/<season>/players.yml` | Player id (`mike-r`), display name ("Mike R."), team, `sub`, jersey `number` (the roster: the only place numbers live) | hand (later `/build-roster` and `/record-game`, both planned) |
| `data/<season>/schedule.csv` | One row per game: id, date, time, gym, home, away, `regular`/`playoff`, week, optional `status` (`cancelled`) and `round` (playoff round name) | hand |
| `data/<season>/games/<game_id>.yml` | One file per played game: a digital copy of the score sheet, box for box (roster rows with Here, free-throw circles and fouls; the running score; quarter lines and score boxes; Notes). Format: [`docs/game-file-format.md`](docs/game-file-format.md) | the entry page (`/enter/`) or hand (later `/record-game`, planned) |
| `data/<season>/drafts/<game_id>.yml` | A game still being entered or checked (`status: draft`, with `review` flags on boxes still in doubt); never read by the build, not even `--check`; checked on the entry page | the entry page (later `/record-game`, planned) |
| `data/<season>/sheets/<game_id>.jpg` | Photo of the paper sheet, kept for checking (not published) | hand (later `/record-game`, planned) |
| `_config.yml` | `sample_data` (show the fake season), `score_sheet_links` (publish photos), `preview_site` (the sample copy at `/preview/`), `contact_url`, `search_engines` (off: pages ask not to be listed by Google), the domain | hand, rarely |

The file formats, id rules and stat rules (GP, PPG, FT%, standings points,
rounding, tiebreakers) are in [`data/CLAUDE.md`](data/CLAUDE.md). The seasons are:
- **`2026-27`:** the real, current season.
- **`sample-2026-27` and `sample-2025-26`:** made-up data from
  `scripts/make_sample_season.py`. They're only shown when `sample_data: true`.

### What `build_stats.py` does

**Checks.** Every problem is reported at once, and nothing is written until
there are none:
- Every game file (a copy of the score sheet) passes the sheet rules in
  `scripts/sheet_rules.py` ([all of them](docs/game-file-format.md#the-checks)):
  running-score jumps of 1, 2 or 3 by numbers on that team's roster and ticked
  Here; the Final box equals the last running total; quarter boxes match their
  lines; overtime only after a tied Q4; fouls 0–5, techs 0–2, and no more
  flagrants than foul boxes; the game is on the schedule with the same teams.
  Each problem names the box (`running.bb.14`, `boxes.aa.final`); warnings are
  listed but don't stop the build. Drafts (`drafts/`) are never read.
- Every player, team and game id exists and is unique.
- No game file for a cancelled game, or for a playoff game whose teams are
  still `TBD`/`2nd`/`Winner G41`.
- Names are "First L.", times are 24-hour, dates are real, and a team doesn't
  play two regular-season games in one day.

**Calculates**, for every season in `seasons.yml`, written to
`_data/computed/<season>/`:

| File | Contents |
|---|---|
| `teams.json` | name, code, colour slot per team |
| `standings.json` | PTS (standings points), W, L, QW (quarters won), PCT, PF, PA, DIFF, rank; tiebreak notes; "through week N" |
| `players.json` | each player's totals: GP, PTS, PPG, FTM, FTA, FT%, season high; PF (kept, not shown); technical and flagrant fouls for the whole season, playoffs included |
| `leaders.json` | PPG, points and FT% leaders (the minimums `ppg_min_games` and `ft_min_attempts` come from `seasons.yml`); everyone with a technical foul; everyone with a flagrant foul |
| `rankings.json` | every player with their rank in each stat, for the Stats page |
| `games.json` | every played game's box score, with the points in each quarter, quarters won and the standings points earned |
| `game_logs.json` | each player's game-by-game lines |
| `schedule.json` | game days (weeks) with their games, byes, played/cancelled state, and which week is latest and next |
| `playoffs.json` | playoff games and totals, kept apart from the regular season |

Playoff games never count toward regular-season stats or standings. Standings
points are 1 per quarter won and 3 per win (`POINTS_PER_QUARTER` and
`POINTS_PER_WIN` in `build_stats.py`).

**Chooses the active season** and writes `_data/computed/active.json`: the
`current` season, or its sample stand-in while `sample_data: true`. It also
writes which seasons the Archive lists. Templates never name a season; they
read this file.

**Writes stub pages.** These are a few lines of front matter each, such as
`_games/2026-10-17-g1.md` with `season:` and `game_id:` (plus title and
description):
- one per game, for every season the Archive lists
- one per player and team, for the active season only (player ids repeat
  across seasons)
- one per archived season

**Writes the calendars** through `scripts/calendars.py`:
`calendar/<team id>.ics` and `calendar/league.ics`, from the `current` season
always.
- One event per game, Eastern time, 90 minutes, at St. Pat's with its address.
- Cancelled games are marked cancelled, and played games carry the score.
- Subscribers' calendars update on the next publish.

### How a page gets its data

Jekyll loads every JSON file in `_data/computed/` as `site.data.computed`.
Two small includes turn that into the variables every template uses:

- **`_includes/active-season.html`** (fixed pages): reads `active.json` and
  sets `season` (from `seasons.json`) and `stats` (that season's JSON files).
- **`_includes/page-season.html`** (generated pages): does the same for the
  season named in the stub's front matter (`page.season`), so an archived
  game's box score reads its own season.

**Fixed pages**, one file each:

| URL | File | Shows |
|---|---|---|
| `/` | `index.html` | latest results, standings (by points), next game day, leaders |
| `/schedule/` | `schedule/index.html` | upcoming game days (each with its score sheet PDF), then results; cancelled games; calendar links; blank score sheets |
| `/stats/` | `stats/index.html` | ranked list (PPG / Points / FT %, by team); full table at `#stats-table`; technical and flagrant foul lists at the bottom |
| `/teams/` | `teams/index.html` | a card per team |
| `/archive/` | `archive/index.html` | a card per season |
| `/rules/` | `rules/index.md` (layout `text`) | the league rules, written in Markdown; linked from the footer |
| `/enter/` | `enter/index.html` | the score sheet entry page (unlisted, needs JavaScript): type up or check a game against the photo, then save the file to GitHub. Reads `enter/sheet-spec.json` and `enter/data/`; script `assets/js/enter.js` |
| `/404.html` | `404.html` | page not found |

**Generated pages:** a stub plus a layout. `_config.yml` declares four
collections; their `defaults` give each stub a layout and a nav tab.

| URL | Stub folder | Layout | Shows |
|---|---|---|---|
| `/games/<game_id>/` | `_games/` | `_layouts/game.html` | box score: score by quarter, both teams, every player, top scorer |
| `/players/<id>/` | `_players/` | `_layouts/player.html` | totals, techs and flagrant fouls, points-by-game-day bars, game log |
| `/teams/<id>/` | `_teams/` | `_layouts/team.html` | record, points, rank, roster, results, upcoming games, calendar |
| `/archive/<season>/` | `_archive/` | `_layouts/archive-season.html` | final standings, playoffs, leaders |

For example, the box score at `/games/2026-10-17-g1/`:
1. `build_stats.py` writes `_games/2026-10-17-g1.md` (`season: 2026-27`,
   `game_id: 2026-10-17-g1`).
2. Jekyll gives it `layout: game` (from `defaults`).
3. `game.html` includes `page-season.html`, looks up
   `stats.games["2026-10-17-g1"]` and draws it with `result-card.html`,
   `line-score.html` and `box-score-table.html`.

Every page uses `_layouts/default.html`:
- `head.html`
- `header.html`
- `sample-banner.html` (only in sample mode)
- the page
- `footer.html`

**Components** (`_includes/`), reused across pages:

| Include | What it draws |
|---|---|
| `head.html` | title, description, share tags, icons, fonts, CSS, the no-flash theme script |
| `header.html` / `footer.html` | badge, nav, theme button and the Sleeping Giant scene / wordmark and links (Teams, Past seasons, Score sheets, League rules, Contact when set) |
| `sample-banner.html` | "Preview with sample data" (sample mode and the `/preview/` copy, which also links to the live site) |
| `player-name.html` | a player as "#23 Dave M." (number from `players.yml`, when known) |
| `result-card.html` | a played game's score card |
| `standings-table.html` / `standings-points-note.html` | the standings table, ranked by points: PTS, W, L, QW, PCT, PF, PA, DIFF (scrolls sideways on phones, team column pinned) / the one-line note on how points work |
| `line-score.html` | a box score's "Score by quarter" table: Q1–Q4, OT, final, standings points |
| `next-game.html` | the blue "Next game day" panel |
| `leader-card.html` / `rank-row.html` | a leader's big number / a ranked player row |
| `stats-row.html` / `game-bars.html` | a Stats list row that expands / points-by-game-day bars |
| `schedule-week.html` / `game-row.html` / `bye-line.html` | a game day on the Schedule / one upcoming or cancelled game / who has the bye |
| `box-score-table.html` | one team's half of a box score |
| `team-card.html` / `season-card.html` | the cards on Teams and Archive |
| `calendar-links.html` / `calendar-help.html` | Subscribe / Download rows for the calendars / how to add one on each kind of device |
| `score-sheet-links.html` | a game day's score sheet PDF link, with "Other layouts" |

### Look and behaviour

- **`brand/`** is the brand kit: logos, icons, the `--mb-*` colour variables
  for light and dark (`css/brand.css`), and the Sleeping Giant scenes.
  Don't edit it.
- **`assets/css/site.css`** holds all page styles, built only from the brand
  variables (no raw colours). Light and dark follow the phone's setting.
- **`assets/js/site.js`** runs the sun/moon button, which saves the choice in
  `localStorage`. A small script in `head.html` applies it before the page
  paints.
- **`assets/js/stats.js`** runs the Stats page: the PPG/Points/FT % switch,
  team filters, expanding rows and table sorting.
- **`assets/js/enter.js`** runs the score sheet entry page (`/enter/`), with
  `assets/js/sheet-rules.js` (the Python rules, ported) and js-yaml
  (`assets/js/lib/`, MIT).
- **No framework.** Every page works with JavaScript off: Stats then shows
  plain lists and a readable table. The one exception is the unlisted entry
  page, a tool that needs it (and says so).
- The approved design is [`docs/design-brief.md`](docs/design-brief.md) and
  [`docs/mockups/`](docs/mockups/). Pages are checked at 360, 390 and 1440 px
  in both themes.

### Publishing

`.github/workflows/deploy.yml` runs on every push and pull request, and every
night at about 4 AM Thunder Bay time (08:17 UTC):

1. Install Python packages (`requirements.txt`: PyYAML, reportlab, pytest).
2. Run every test with pytest (`tests/`, including the score sheet rules against
   the shared fixtures in `tests/fixtures/sheets/`).
3. Run the JavaScript tests with Node 22 (`node --test "tests/js/*.test.mjs"`):
   the entry page's copy of the rules against the same fixtures.
4. `python scripts/build_stats.py`: check the data and write the JSON, stubs,
   calendars and the entry page's data (`enter/data/`).
5. `scripts/make_score_sheets.sh`: score sheet PDFs for the season the site
   shows, into `score-sheets/`. That's every game day from today (Thunder Bay
   time) in all four layouts, plus blank sheets. The Schedule page links only
   the files that exist.
6. `scoresheet.py --spec enter/sheet-spec.json`: the sheet's structure, which
   the entry page draws its sheet from.
7. `bundle exec jekyll build` (production).
8. `scripts/build_preview.sh`: the hidden preview copy, the same site built
   from the sample season into `_site/preview/` (published at `/preview/`, with
   the sample banner). Off with `preview_site: false` in `_config.yml`.
9. `scripts/check_links.sh`: html-proofer over `_site/` (both copies), including
   the PDF links.
10. **On `main` only:** upload `_site/` and deploy it to GitHub Pages.

A pull request runs steps 1–9, so a red cross means "don't merge yet". The
nightly run rebuilds `main` with nothing changed, so the parts that depend on
today's date stay current: the score sheets (from today on), the "next game
day" panel and the calendar files. GitHub pauses scheduled runs after 60 days
without a push to the repo; re-enable it under Actions → Build and deploy. The
domain is set in the repo's Settings → Pages and in `_config.yml` (`url`) and
`CNAME`; DNS is at Porkbun ([`docs/domain.md`](docs/domain.md)).

### Running it on your computer

```sh
pip install -r requirements.txt        # Python 3.12, PyYAML, reportlab, pytest
bundle install                         # Ruby and Jekyll 4.4

python -m pytest                       # every test (unit tests + score sheet fixtures)
node --test "tests/js/*.test.mjs"      # the entry page's rules on the same fixtures (Node 22)
python scripts/build_stats.py          # check data; write JSON, stubs, calendars, enter/data/
python scripts/scoresheet/scoresheet.py --spec enter/sheet-spec.json   # needed for /enter/
scripts/make_score_sheets.sh           # score sheet PDFs (optional locally)
bundle exec jekyll serve --livereload  # http://localhost:4000/
bundle exec jekyll build && scripts/build_preview.sh && scripts/check_links.sh   # both copies

# every page at 360/390/1440 px, light and dark, sample and real data
# (needs: pip install playwright pillow)
python scripts/screenshot_all.py --out /tmp/shots --contact-sheets
```

Run `build_stats.py` again after changing anything in `data/` or the
`sample_data` switch.

### Common changes

| I want to… | Do this |
|---|---|
| Add a game result | type it up on `/enter/` ([guide](docs/stats-workflow.md#enter-or-check-a-game-on-the-entry-page)), or add `data/2026-27/games/<game_id>.yml` by hand ([guide](docs/stats-workflow.md#add-a-game-by-hand)) |
| Check a draft against the paper | open it on `/enter/`, with the photo beside it |
| Fix a number | edit the game file (or reopen the game on `/enter/`); everything is recalculated |
| Add a player or sub | one line in `data/2026-27/players.yml` |
| Edit the league rules | `rules/index.md` ([guide](docs/stats-workflow.md#edit-the-league-rules)) |
| Cancel, move or make up a game | edit its row in `schedule.csv` ([guide](docs/stats-workflow.md#cancel-or-move-a-game)) |
| Set a playoff matchup | replace `TBD` / `2nd` / `Winner G41` with team ids in `schedule.csv` |
| Change a team's colour | its `colour_slot` (1–5) in `teams.yml` |
| See a change with fake numbers | open `/preview/` after it's merged (the sample-season copy), or set `sample_data: true` in `_config.yml` locally |
| Change a ranking minimum | `ppg_min_games` / `ft_min_attempts` in `data/seasons.yml` ([guide](docs/stats-workflow.md#change-a-ranking-minimum)) |
| Start a new season | add `data/<new season>/` (teams, players, schedule, empty `games/`, `drafts/` and `sheets/`), add it to the top of `seasons.yml` with `current: true`, and remove `current` from the old one. The old season moves to the Archive, keeping its standings, leaders and box scores, but no player or team pages. |

### Repository map

```
data/                    league data: the only thing edited week to week
  seasons.yml
  2026-27/               the real season: teams, players, schedule, games/, drafts/, sheets/
  sample-2026-27/        made-up data (sample mode only)
  sample-2025-26/
scripts/
  build_stats.py         checks the data; writes JSON, stub pages, calendars
  sheet_rules.py         the score sheet rules: checks a game file, works out each player's numbers
  calendars.py           the .ics files
  scoresheet/            the score sheet generator (form MBL-SS6): README, fonts, example data
  make_score_sheets.sh   score sheet PDFs for the season shown (CI)
  make_sample_season.py  regenerates the sample seasons (and their two drafts)
  make_practice_games.py the practice sheets for /record-game (tests/fixtures/record-game/)
  build_preview.sh       the sample-season copy at /preview/ (CI)
  check_links.sh         link check (CI)
  screenshot_all.py      screenshots + page checks for QA
tests/                   unit tests (build_stats, calendars, score sheets) and the sheet rules tests
  fixtures/sheets/       test game files with their expected results (Python and JS rules both run them)
  fixtures/record-game/  four practice games: answer key, filled sheet, empty sheet (see its README)
  js/                    the entry page's JavaScript rules on the same fixtures (node --test)
_config.yml              site settings, switches, collections
_layouts/  _includes/    templates and components
index.html  schedule/  stats/  teams/  archive/  rules/  404.html   fixed pages
enter/                   the score sheet entry page (unlisted); sheet-spec.json and data/ are written by the build
assets/css/site.css      page styles
assets/js/               theme button, Stats page, entry page (+ sheet rules, lib/js-yaml)
brand/                   brand kit (don't edit)
docs/
  stats-workflow.md      the volunteer's guide
  game-file-format.md    the game file: a digital copy of the score sheet
  open-questions.md      league decisions still needed
  design-brief.md        the design spec and decisions
  mockups/               approved mockups
  domain.md              domain and DNS
  qa/                    full-site QA report (screenshots: run screenshot_all.py)
  screenshots/           screenshots from the build steps
.github/workflows/deploy.yml   build, check and publish
CNAME                    the domain, for GitHub Pages
```

Generated on every build and never committed: `_data/computed/`, `_games/`,
`_players/`, `_teams/`, `_archive/`, `calendar/`, `score-sheets/`,
`enter/data/`, `enter/sheet-spec.json`, `sheets/` (only when photos are
published) and `_site/`.
