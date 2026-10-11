# Masters Basketball League · Thunder Bay website

Static site for a 5-team masters basketball league (October to April, playoffs in
April). It shows standings, schedule, team pages, player stats (points, PPG,
FTM, FTA, FT%) and an archive of past seasons. Visitors are mostly on phones.

Hosted on GitHub Pages from the `tb-masters-basketball` organization, repo
`website`, at the custom domain `https://mastersbasketball.ca/` (registered at
Porkbun; DNS records are listed in `docs/domain.md`).

**Paths:** `_config.yml` sets `url: "https://mastersbasketball.ca"` and an empty
`baseurl`; the `CNAME` file names the domain. Every internal link, image,
stylesheet, icon and manifest path must still go through `relative_url` (or
`absolute_url` for share tags), e.g.
`{{ '/brand/logo/masters-badge.svg' | relative_url }}`. Never hard-code a
leading `/`: then a new domain or a baseurl only means changing `_config.yml`
and `CNAME`. (`site.webmanifest` uses relative paths, so it needs no change.)

## Stack
- **Jekyll** builds the site. Deploys run through a GitHub Actions workflow, not
  the default Pages build, because a Python step runs first.
- **`scripts/build_stats.py`** (Python 3, standard library plus PyYAML) reads
  every season in `data/seasons.yml` and writes `_data/computed/<season>/*.json`:
  standings, player totals, leaders, per-player rankings and per-game logs.
  Game files are digital copies of the score sheet (docs/game-file-format.md);
  `scripts/sheet_rules.py` is the one place the sheet rules live: it checks a
  file, returns problems as {level, at: path to one box, message}, and works out
  each player's points (running score), FTM/FTA (circles), GP (Here), fouls,
  techs and flagrants (Notes). Technical and flagrant fouls count the whole
  season, playoffs included; personal fouls aren't shown. Standings are by
  points: 1 per quarter won (from the quarter boxes), 3 per win.
- **Sample data switch:** pages never name a season. `build_stats.py` picks the
  active season (the sample stand-in while `sample_data: true` in `_config.yml`,
  else the `current` one) and writes `_data/computed/active.json`;
  `_includes/active-season.html` reads it and gives templates `season` and
  `stats`. Don't hard-code a season id in a template.
- **One page per game, player, team and archive season** comes from stub files
  that `build_stats.py` writes into `_games/`, `_players/`, `_teams/` and
  `_archive/` (git-ignored, rewritten every run). Jekyll collections and
  `defaults` in `_config.yml` give them a layout and an address. No Ruby plugin.
- **No JavaScript framework.** Use small vanilla JS only for the theme toggle,
  stat-table sorting and expanding player rows (`assets/js/site.js`, and
  `assets/js/stats.js` on the Stats page). Every page must make sense
  with JS off.
  **Exception:** the unlisted score sheet entry page (`/enter/`) is a tool and needs JavaScript (it says so with JS off).

## Score sheets
The printable score sheet (form MBL-SS6) comes from
`scripts/scoresheet/scoresheet.py`; read `scripts/scoresheet/README.md` first.
`scripts/make_score_sheets.sh` runs it on every deploy, after `build_stats.py`
and before Jekyll, for the season the site shows. It writes `score-sheets/`
(git-ignored): each game day from today on in all four layouts, plus the blank
sheets. The Schedule page links only the PDFs that exist.
Every structural number (rows, circles, foul boxes, score boxes, running-score
pages) is in its `SPEC` dict; `scoresheet.py --spec scripts/scoresheet/spec.json`
writes it out for `sheet_rules.py` (a test keeps the two in step).
**Don't change the sheet's layout or `FORM` without updating `sheet_rules.py`
(and its JS port), the game file format and, once it exists, `/record-game`**, which read sheets by that exact
layout. The entry page (`/enter/`) draws its sheet from the spec, so it follows on its own. Changes to how it reads the data (which games, which players) are fine.

## Layout
```
data/<season>/          source of truth, edited on the entry page (/enter/) or by hand (see data/CLAUDE.md);
                        games/ = finished score sheets, drafts/ = not yet (never built)
                        data/2026-27/ is the real season; data/sample-2026-27/ is fake data
_config.yml             `sample_data: true` makes every page read the sample season (+ banner);
                        `preview_site: true` also builds a sample copy at /preview/ on every deploy;
                        `score_sheet_links` (off) publishes score sheet photos; collections for the stubs
scripts/build_stats.py  computes _data/computed/ (git-ignored) — never edit those files by hand
scripts/sheet_rules.py  the score sheet rules: game file checks (with box paths) and per-player lines
assets/js/sheet-rules.js  the same rules ported to JS for /enter/ (change the Python first, then this;
                        tests/js keeps them in step)
enter/index.html        the score sheet entry page (unlisted, noindex): built from enter/sheet-spec.json
                        (the deploy writes it with `scoresheet.py --spec`) and enter/data/ (build_stats.py);
                        UI in assets/js/enter.js, js-yaml vendored in assets/js/lib/
scripts/calendars.py    writes calendar/<team>.ics and league.ics (git-ignored) from the real season;
                        called by build_stats.py, linked from Schedule and team pages
scripts/make_sample_season.py  regenerates data/sample-2026-27/ and sample-2025-26/ (fake data)
scripts/build_preview.sh  after the main build: the sample-season copy into _site/preview/ (runs in CI)
scripts/check_links.sh  fails on broken links/images in _site/ (html-proofer; runs in CI)
scripts/scoresheet/     the score sheet generator (README, fonts, badge, example data)
scripts/make_score_sheets.sh  score-sheets/*.pdf (git-ignored) for the season shown; runs in CI
scripts/make_practice_games.py  practice sheets for /record-game into tests/fixtures/record-game/
                        (answer key + filled + empty sheet; uses `scoresheet.py --fill`)
scripts/screenshot_all.py  builds sample + real mode, screenshots the main pages (360/390/1440, light/dark),
                        checks sideways scroll, console errors and failed requests
tests/                  pytest: build_stats, calendars, score sheets, sheet rules
tests/js/               node --test: the JS sheet rules against the same fixtures (runs in CI)
tests/fixtures/sheets/  test game files + expected results (run by both the Python and the JS rules)
tests/fixtures/record-game/  four practice games for the planned /record-game (see its README)
_layouts/ _includes/    templates (_layouts/text.html: Markdown pages such as rules/index.md)
rules/index.md          the League rules page (Markdown, [placeholder] sections; linked from the footer)
assets/css/site.css     page styles, built on brand/css/brand.css variables
brand/                  logos, icons, colours, scenes (from the brand kit; don't edit)
docs/design-brief.md    the design spec: read this before touching any page
docs/stats-workflow.md  how score sheets become site numbers, for the volunteer (keep it true)
docs/game-file-format.md  the game file format, its checks and problem paths
docs/mockups/           approved mockups (open in a browser) and screenshots
docs/qa/report.md       the full-site QA report (screenshots: run screenshot_all.py)
.github/workflows/      build stats → build Jekyll → deploy to Pages
```

## Commands
```
python -m pytest                         # every test (runs in CI before the build)
node --test "tests/js/*.test.mjs"        # the JS sheet rules against the same fixtures (Node 22)
python scripts/scoresheet/scoresheet.py --spec enter/sheet-spec.json   # the sheet layout /enter/ reads
python scripts/build_stats.py            # check data, recompute stats, write the stub pages
scripts/make_score_sheets.sh             # score sheet PDFs into score-sheets/ (needs reportlab)
bundle exec jekyll serve --livereload    # preview at http://localhost:4000/
bundle exec jekyll build && scripts/build_preview.sh && scripts/check_links.sh   # build both copies, check links
python scripts/screenshot_all.py --out /tmp/shots --contact-sheets   # every page, both modes (needs Playwright)
```
Always run the stats script before previewing data changes (and after changing
`sample_data`): it also writes the stub pages and the active season.

## Design rules (details in docs/design-brief.md)
- Match `docs/mockups/` for look and spacing. Mobile mockups are 390 px wide;
  the desktop mockup is 1440 px.
- Colours only through the `--mb-*` variables in `brand/css/brand.css`. No raw
  hex values in page CSS.
- Light and dark themes. Follow `prefers-color-scheme`; the sun/moon button sets
  `data-theme` on `<html>` and saves it to `localStorage` (`mb-theme`). The head
  snippet in `brand/head-snippet.html` applies it before paint.
- Fonts: Barlow Condensed (headings, numbers) and Barlow (text) from Google Fonts.
  Use `font-variant-numeric: tabular-nums` in tables.
- Logo: `brand/logo/masters-badge.svg` in the header (works on light, dark and
  the blue header). Footer uses `masters-wordmark-type-dark.svg`. Favicon and
  app icons are in `brand/icons/`.
- Players are always shown as "First L." (e.g. "Mike R."), with their jersey
  number first when `players.yml` has one ("#23 Mike R.", via
  `_includes/player-name.html`). Never full names,
  contact details or photos of players. Score sheet photos stay in the repo
  and off the site (`score_sheet_links: false`, the league's decision).
- Reuse the includes and classes already in `_includes/` and `assets/css/site.css`
  (result card, standings table, rank row, tiles, bars, game row, team card...).
  If a page needs something new, add it as a reusable component, not a one-off.

## Quality bar
- Every page works at 360 px wide with no sideways page scroll. Wide tables
  scroll inside their own box with a sticky first column.
- Text contrast passes WCAG AA in both themes. Touch targets are at least 44 px.
  Use real `<button>`, `<a>` and `<table>` elements.
- Before calling a page done, screenshot it at 390 px and 1440 px in both
  themes, and compare against the mockups.

## Don't
- Don't edit `_data/computed/` or anything in `brand/` by hand (except the
  domain and path fixes in `head-snippet.html` and `site.webmanifest`).
- Don't add analytics, ads, trackers or cookie banners.
- Don't add a sitemap or anything that invites search engines: the league
  doesn't want the site on Google (`search_engines: false` puts a `noindex`
  tag on every page).
- Don't invent league facts (tiebreakers, playoff format, gym, team colours).
  Leave a visible `[placeholder]` and list it in `docs/open-questions.md`.
