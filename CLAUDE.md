# Masters Basketball League · Thunder Bay website

Static site for a 5-team masters basketball league (October to April, playoffs in
April). It shows standings, schedule, team pages, player stats (points, PPG,
FTM, FTA, FT%) and an archive of past seasons. Visitors are mostly on phones.

Hosted on GitHub Pages from the `tb-masters-basketball` organization, repo
`website`. Until a domain is bought it lives at
`https://tb-masters-basketball.github.io/website/`; later it moves to `[DOMAIN]`.

**Paths:** `_config.yml` sets `baseurl: "/website"` for now. Every internal
link, image, stylesheet, icon and manifest path must go through
`relative_url` (or `absolute_url` for share tags), e.g.
`{{ '/brand/logo/masters-badge.svg' | relative_url }}`. Never hard-code a
leading `/`. Moving to the custom domain is then: set `baseurl: ""` and `url`
to the domain, add a `CNAME` file. (`site.webmanifest` uses relative paths, so
it needs no change.)

## Stack
- **Jekyll** builds the site. Deploys run through a GitHub Actions workflow, not
  the default Pages build, because a Python step runs first.
- **`scripts/build_stats.py`** (Python 3, standard library plus PyYAML) reads
  every season in `data/seasons.yml` and writes `_data/computed/<season>/*.json`:
  standings, player totals, leaders, per-player rankings and per-game logs.
- **Sample data switch:** pages never name a season. They get `season` and
  `stats` from `_includes/active-season.html`, which reads the sample season
  while `sample_data: true` in `_config.yml`, else the `current` one. Don't
  hard-code a season id in a template.
- **No JavaScript framework.** Use small vanilla JS only for the theme toggle,
  stat-table sorting and expanding player rows (`assets/js/site.js`, and
  `assets/js/stats.js` on the Stats page). Every page must make sense
  with JS off.

## Layout
```
data/<season>/          source of truth, edited by hand or by /record-game (see data/CLAUDE.md)
                        data/2026-27/ is the real season; data/sample-2026-27/ is fake data
_config.yml             `sample_data: true` makes every page read the sample season (+ banner)
scripts/build_stats.py  computes _data/computed/ (git-ignored) — never edit those files by hand
scripts/make_sample_season.py  regenerates data/sample-2026-27/ (fake data)
tests/                  unit tests for build_stats.py
_layouts/ _includes/    templates
assets/css/site.css     page styles, built on brand/css/brand.css variables
brand/                  logos, icons, colours, scenes (from the brand kit; don't edit)
docs/design-brief.md    the design spec: read this before touching any page
docs/stats-workflow.md  how score sheets become site numbers, for the volunteer (keep it true)
docs/mockups/           approved mockups (open in a browser) and screenshots
.github/workflows/      build stats → build Jekyll → deploy to Pages
```

## Commands
```
python -m unittest discover -s tests     # unit tests
python scripts/build_stats.py            # check data and recompute stats
bundle exec jekyll serve --livereload    # preview at http://localhost:4000/website/
```
Always run the stats script before previewing data changes.

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
- Players are always shown as "First L." (e.g. "Mike R."). Never full names,
  contact details or photos of players.

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
- Don't invent league facts (tiebreakers, playoff format, gym, team colours).
  Leave a visible `[placeholder]` and list it in `docs/open-questions.md`.
