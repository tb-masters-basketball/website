# Full-site QA report (step 5)

Checked on 8 October 2026 against `CLAUDE.md`, `docs/design-brief.md`, `docs/open-questions.md`
and the mockups in `docs/mockups/`. The site was built the way the Actions workflow builds it:
`build_stats.py`, then `JEKYLL_ENV=production jekyll build` with the `/website` baseurl, then
`check_links.sh`.

- **Pages:** Home, Stats (list and table), Schedule, Teams, a team, a player, a box score,
  Archive, the past sample season and 404.
- **Widths and themes:** 360, 390 and 1440 px, light and dark.
- **Data:** sample mode on, and sample mode off (the empty real season).

Screenshots: `docs/qa/before/` and `docs/qa/after/`, laid out as `<mode>/<width>/<page>-<theme>.png`.
Each folder has one contact sheet per width (`contact-360.png`, `contact-390.png`, `contact-1440.png`)
and the script's `checks.json`.

To capture them again: `python scripts/screenshot_all.py --out docs/qa/after --contact-sheets`
(it needs `pip install playwright`).

**Result:** I found 9 issues and fixed 9. 6 differences from the mockups stay as they are, because
they are decisions you already made or follow from your data. Nothing that would change the approved
design was changed.

## Issues found

| # | Page | Width | Theme | What was wrong | Status |
|---|---|---|---|---|---|
| 1 | Every page | all | both | No "Skip to content" link. A keyboard user had to tab through the logo, 5 tabs and the theme button on every page before reaching the content. | **Fixed.** The link is the first tab stop. It stays off screen until it has focus. |
| 2 | Short pages. Sample mode off: 404, Archive, Schedule and the player page. Sample mode on: 404, and Archive at phone widths. (17 page/width cases, found by checking the bottom pixel row of every screenshot.) | all | both | The dark footer ended part-way down the window, with page background showing below it. | **Fixed.** The page is now a column and the footer sits at the bottom of the window. Long pages are unchanged. |
| 3 | 86 of 90 pages (every box score, player, team, season and 404 page) | n/a | n/a | They all had the same meta description, the site default. | **Fixed.** `build_stats.py` writes a description into each stub page, e.g. "Dave M., Port Arthur: points, points per game and free throws, game by game, for the 2026-27 season." The 404 page has its own. All 90 are now different. |
| 4 | Box scores | n/a | n/a | 14 pages shared 7 titles, because the same two teams meet more than once a season (e.g. "Port Arthur vs Fort William" twice). | **Fixed.** Titles now include the date: "Port Arthur vs Fort William, Thu Nov 26, 2026". A new unit test checks that every stub page's title and description are unique. |
| 5 | Every page | n/a | n/a | `og:description` was the same fixed sentence on every page. | **Fixed.** It now uses the page's description. |
| 6 | Every page | n/a | n/a | No `twitter:title`, `twitter:description` or `twitter:image`. Only `twitter:card` was set. | **Fixed.** All three are added; the image uses `absolute_url` and the social card. Image alt text is added for both Open Graph and Twitter. |
| 7 | Home | n/a | n/a | The tab title was "Home · Masters Basketball · Thunder Bay". | **Fixed.** It is now just "Masters Basketball · Thunder Bay". |
| 8 | Stats (table view) | all | both | Following a link to `#stats-table` from the Stats page itself (no reload) didn't switch to the table. A fresh load always worked. | **Fixed** in `assets/js/stats.js` (a `hashchange` listener). |
| 9 | Team and player pages (sample mode off) | all | both | The real rosters show `[placeholder]`, but they weren't listed in `docs/open-questions.md`. | **Fixed.** Added a row for the real 2026-27 rosters. |

**Not a site problem.** My first screenshot pass saved 256-colour PNGs to keep them small. That
turned small coloured dots (the Westfort and Fort William chips) grey or red in the images. The
script now saves full-colour PNGs, and the before set was captured again with no site changes in
between.

### Differences from the mockups that stay

Compared Home and Stats at 390 px and Home at 1440 px, in both themes, with `docs/mockups/screens/`.
The header, nav underline, Giant scene, cards, type sizes, spacing and footer match. These are the
differences:

| Where | Mockup | Site | Why it stays |
|---|---|---|---|
| Every page, sample mode | No banner | "Preview with sample data" banner under the header | Required. It shows only in sample mode, and is gone with `sample_data: false` (checked). |
| Home: Next game | "[Gym name]" | "St. Pats" | Your answer (the gym is read from `schedule.csv`). |
| Home: Standings | 5 columns and a "Full table" link | All 8 columns (scrolls sideways on phones, team column pinned), no link | Your decision in step 2. |
| Footer | "Contact the league" link | No link | `contact_url` is blank. The link appears when it's set (your rule). |
| Home at 1440: the Giant scene | Fills the width | About 20% narrower, keeping the brand file's proportions | Recorded in step 2. `brand/` can't be edited. |
| Stats at 390 | First row shown open; no "How stats are counted" | All rows closed; "How stats are counted" at the end | The mockup shows one row opened as an example. The definitions section was added in step 3. |

Pages without a mockup use only the shared components (result card, rank row, tiles, game row,
team card, season card, surface card), with the same section spacing. I found no one-off styles.

## What was checked, and the results

### Sideways scroll (overflow)

`screenshot_all.py` compares `document.documentElement.scrollWidth` with the viewport width on every
capture: 126 captures (11 pages × 3 widths × 2 themes in sample mode, and 10 × 3 × 2 in real mode,
which has no box score).

- No page scrolls sideways, before or after the fixes.
- Every wide table (Home standings, Stats table, game log, box score, season standings) scrolls in its
  own box at 360 px.
- The first column is `position: sticky`, with an opaque background in both themes:
  - `#FFFFFF` in light and `#131B34` in dark.
  - On the box score, the top scorer's row uses the highlight colours on purpose: `#F4F6FB` in light
    and `#0A1022` in dark.
- I checked the sticky column by scrolling each table fully to the right.

### Contrast (WCAG AA)

Every visible text element on every page was measured in both themes, at 360, 390 and 1440 px, with
sample mode on and off: 10,970 text elements.

- The text colour is compared with the actual background behind it, with alpha blended in.
- Where text sits on the header gradient or the scene, the background is sampled from the pixels
  around the text.
- AA needs 4.5:1, or 3:1 for large text.
- **0 text elements are below AA.**

| What | Light | Dark |
|---|---|---|
| Muted / secondary text (`--mb-muted`, on page and on cards) | 5.50 | 6.99 |
| Sample banner | 14.40 | 12.30 |
| Links ("All stats", "Box score ›", names, dates) | 10.42 | 7.96 |
| Team chips (selected and not selected) | 11.27 | 8.85 |
| Segmented control (lowest: the options that aren't selected) | 4.84 | 5.33 |
| Active nav tab | 11.27 | 15.68 |
| Other nav tabs (over the gradient) | 8.38 | 8.87 |
| Title and season line over the header gradient | 8.38 | 9.97 |
| Leader card and ranked-list numbers | 11.27 | 7.96 |
| Text on blue panels (next game, No. 1 card) | 7.61 | 8.19 |
| Footer text | 11.41 | 8.74 |
| Table sort headers | 5.95 | 6.99 |
| Skip link (new) | 11.27 | 7.96 |
| **Lowest anywhere on the site** | **4.84** | **5.33** |

### Touch targets and keyboard

I tabbed through all 21 page and mode combinations in both themes. On every stop I recorded:

- the element
- its size
- whether a focus ring shows
- whether it is on screen

Results after the fixes:

- **Focus ring:** shows on every stop in both themes, 0 missing.
- **Target size:** 0 interactive elements are under 44 × 44 px.
- **Tab order:** skip link, logo, nav tabs, theme button, the page's content in reading order, then
  the footer.
- **Scrolling tables:** these are focusable regions with a name (e.g. "Standings table"), so a
  keyboard user can scroll them.

Controls, operated with the keyboard only (25/25 checks pass):

- **Theme toggle:** Enter flips the theme. The label changes between "Switch to dark theme" and
  "Switch to light theme".
  - I used the changing label instead of `aria-pressed`. A button that changes its own name and is
    also `aria-pressed` reads as a contradiction ("Switch to light theme, pressed").
- **Segmented control (PPG / Points / FT %):** Enter and Space both work. `aria-pressed` moves to
  the chosen option.
- **Team chips:** one team at a time. `aria-pressed` follows; "All" resets.
- **Expanding player rows:** Enter and Space toggle `aria-expanded`. `aria-controls` points to the
  panel, which shows and hides.
- **Table sort headers:** Enter sorts. Enter again reverses. `aria-sort` is on the sorted column only
  ("descending", then "ascending").

### JavaScript turned off

Every page was loaded with JavaScript disabled, and the screenshots were reviewed.

- **Stats:** shows the No. 1 card and the top of the ranked list as plain links to player pages, with
  151 links to player pages in total. The full table is readable and sorted by PPG. No buttons that do
  nothing are shown.
- **Theme toggle and Stats controls:** hidden, because they need JavaScript.
- **Theme:** follows the system setting.
- **Other pages:** have no JavaScript to lose.
- **Overall:** nothing is hidden behind JavaScript, and nothing scrolls sideways.

### Theme

All checks pass:

- **System setting:** with nothing saved, the page follows it, in both themes.
- **Toggle:** flips the theme, saves it in `localStorage` (`mb-theme`) and keeps it after a reload
  and on other pages.
- **Browser toolbar colour:** the `theme-color` meta follows the toggle.
- **Header scene:** swaps between `giant-sunrise.svg` and `giant-moonset.svg`.
- **No flash:**
  - The page was loaded on a throttled network (400 ms latency, 50 KB/s), so it took about 6.3 s.
  - The saved theme was the opposite of the system theme.
  - I recorded every painted frame: 9 frames each way, 0 in the wrong theme.

### Paths and links

- **No hard-coded leading `/`:** none in `_layouts/`, `_includes/` or the page files, and no root
  paths in the CSS or JS. Every internal path goes through `relative_url`; share tags use
  `absolute_url`.
- **Browser console and network log:** no errors and no failed or 4xx requests, on all 126 captures.
  This covers CSS, fonts, images, icons and the manifest.
- **`scripts/check_links.sh`** (the Actions step) passes on the built site in sample mode and in real
  mode.
- **Icons and manifest:** the favicon (SVG and ICO), apple-touch icon, `site.webmanifest` and both
  `theme-color` tags load on every page.

### Head tags

All 90 built pages:

- **`<title>`:** every page has its own.
- **Meta description:** every page has its own.
- **Open Graph and Twitter tags:** use the page's title and description, with absolute URLs and the
  1200 × 630 social card.
- **Canonical URL:** set on every page.

### Data spot-check (by hand from the game YAML files)

Computed straight from `data/sample-2026-27/games/*.yml` and `data/sample-2025-26/games/*.yml`
(without `build_stats.py`), then compared with what the built pages show. **44/44 match.**

| Player | GP | PTS | PPG | FTM | FTA | FT% | Season high | Site |
|---|---|---|---|---|---|---|---|---|
| Dave M. (Port Arthur) | 7 | 141 | 20.1 | 22 | 27 | 81.5% | 24 | matches (player page tiles, Stats row, Stats table) |
| Ian C. (Port Arthur, sub) | 2 | 7 | 3.5 | 2 | 2 | 100.0% | 5 | matches |
| Bill C. (Fort William) | 5 | 40 | 8.0 | 9 | 13 | 69.2% | 16 | matches |

| Team | W-L | GB | DIFF | Site |
|---|---|---|---|---|
| Port Arthur | 6-1 | — | +61 | matches |
| Current River | 5-2 | 1 | +30 | matches |
| Westfort | 3-3 | 2.5 | +3 | matches |
| Lakehead | 2-4 | 3.5 | −31 | matches |
| Fort William | 0-6 | 5.5 | −63 | matches |

| Game | Final (by hand) | Points add up to the final | Site |
|---|---|---|---|
| 2026-11-26-g2 | Port Arthur 62, Fort William 54 | yes | matches: "Week 7 · Thu Nov 26 · 8:15 PM · St. Pats" |
| 2026-10-15-g1 | Fort William 61, Port Arthur 68 | yes | matches: "Week 1 · Thu Oct 15 · 7:00 PM · St. Pats" |

Also confirmed:

- **FT% leaderboard leaves out anyone under 10 FTA.**
  - 16 players have 10 or more FTA, and the leaderboard lists exactly those 16.
  - 32 players with 1–9 FTA are left out.
- **Playoff games stay out of regular-season stats.**
  - The 2025-26 final (2026-04-09, Port Arthur 68, Current River 64) is not in the 2025-26
    standings (W-L 4-0, 3-1, 2-2, 1-3, 0-4 by hand and on the site).
  - The final doesn't count toward the 2025-26 PPG leader (15.0, regular season only).
  - It still has its own box score page.
- **Dates and times:** Eastern, as written in `schedule.csv`, in the "Thu Dec 10 · 7:00 PM" format,
  everywhere I looked: result cards, schedule, box scores, game log and next game.

### Empty states (sample mode off)

Every page shows a plain sentence, with no errors, "NaN", "undefined", Liquid errors or empty tables
(I searched every built page):

- "No games played yet."
- "Not scheduled yet."
- "No games scheduled yet."
- "Player stats appear after the first game night."
- "No playoff games yet."
- "Needs 10 attempts"

The standings show all five `[Team A]`–`[Team E]` at 0-0. The sample banner appears only in sample
mode.

### Speed and accessibility (Lighthouse 12, mobile settings)

| Page | Accessibility | Best practices | SEO | Performance (gzip, like GitHub Pages) | Performance (plain local server) |
|---|---|---|---|---|---|
| Home | 100 | 100 | 100 | 92 | 91 |
| Stats | 100 | 100 | 100 | 92 | 83 |
| Box score (2026-11-26-g2) | 100 | 100 | 100 | 91 | 92 |

- **Layout shift (CLS):** 0 on all three.
- **Total blocking time:** 0 ms on all three.
- **Page weight:** 125–141 KB compressed.
- **Why Stats scores 83 without compression:** the plain local server doesn't compress files, and
  Stats has the most HTML. GitHub Pages compresses, so the gzip column is the realistic one.
- **What blocks rendering:** the Google Fonts stylesheet and the two site stylesheets, as expected.
  Fonts use `display=swap`.
- **Images:** every `<img>` has `width` and `height`.
- **axe-core:** 0 violations on every page and mode, in both themes.

### Content rules

- **Player names:** shown only as "First L.", including page titles, share tags and alt text.
  - `build_stats.py` rejects any other format.
  - The only images with alt text are the badge (alt is empty, because the title is next to it) and
    the footer wordmark ("Masters Thunder Bay").
- **No analytics, trackers or cookies:** none in any built page or script.
- **Score sheet photos:** stay unpublished (`score_sheet_links: false`).
- **Unknown league facts:** each shows `[placeholder]` and is listed in `docs/open-questions.md`. I
  added the missing row for the real rosters.

## Left for you to decide

1. **Minimum games for the PPG leaderboard.** It is still open in `docs/open-questions.md`. In the
   2025-26 sample season, a sub with 2 games (Darren V., 15.0) leads PPG. The same could happen with
   real data. Should there be a minimum (for example half the team's games)?
2. **Screenshot size in the repo.** The before and after sets are about 41 MB of full-colour PNGs. If
   you'd rather keep the repo small, I can keep only the contact sheets after you've reviewed this PR
   (`screenshot_all.py` can recreate the rest any time).
3. **Theme toggle semantics.** It uses a changing label ("Switch to dark theme") instead of
   `aria-pressed`, as explained above. Say if you'd prefer a fixed label with `aria-pressed`.
4. The open questions in `docs/open-questions.md` still need answers before launch:
   - real team names and colours
   - rosters
   - the schedule
   - tiebreakers
   - the playoff format
   - the contact link
   - the domain
