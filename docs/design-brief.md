# Design brief: final

**Status:** the look is approved: option 6 ("Recommended") with the round
badge, in light and dark. Home and Stats are fully designed for phone, and
Home for desktop. Every other page is built from the same parts, as described
below. When a page isn't mocked up, follow these notes and the existing parts
rather than inventing new styles.

## What to look at
| File | Shows |
|---|---|
| `docs/mockups/home-mobile-light.html` / `-dark` | Phone Home, 390 px |
| `docs/mockups/stats-mobile-light.html` / `-dark` | Phone Stats, 390 px, one player row open |
| `docs/mockups/home-desktop-light.html` / `-dark` | Desktop Home, 1440 px |
| `docs/mockups/screens/*.png` | Screenshots of all of the above |
| `brand/BRAND.md` | Logo use, colours, type |
| `brand/css/brand.css` | All colour variables, light and dark |

The mockup HTML is for reference only: inline styles and sample numbers. Rebuild
it as clean templates and CSS classes; don't copy it as is.

## Global layout
- **Widths:** content max 1200 px, 16 px side padding on phones, 32 px from 900 px up.
- **Breakpoint:** one column below 900 px. From 900 px, Home uses a main column
  (about 2/3) and a side column (about 1/3), as in the desktop mockup.
- **Radius:** 10 px for cards, 12 px for large panels. Borders are 1 px `--mb-line`.
- **Type scale:** page title is Barlow Condensed 700, 30 px on phone and 34 px on
  desktop, uppercase. Section titles are 24 px and 28 px. Body text is Barlow
  15–17 px. Big stat numbers are Barlow Condensed 700, 40–56 px.

### Header (every page)
- Background is the `--mb-sky` gradient, with the Sleeping Giant scene
  (`brand/scenes/giant-sunrise.svg` light, `giant-moonset.svg` dark) at the
  bottom edge.
- On phone: badge (58 px), "MASTERS BASKETBALL", a red rule with "THUNDER BAY ·
  season", the sun/moon button, then the nav row underneath.
- On desktop: everything sits on one row, with a bigger badge (84 px) and the
  scene stretched full width. See the desktop mockup.
- **Nav:** Home · Schedule · Stats · Teams · Archive. The active tab has a 3 px
  coral underline. There's no hamburger menu; on phone the nav row wraps if it
  has to.
- The sun/moon button is a real `<button>` with an `aria-label` and a 44 px
  target. It flips `data-theme` and saves the choice.

### Footer (every page)
The Giant silhouette in `--mb-footer` colour, then the footer band: wordmark B
(`masters-wordmark-type-dark.svg`), links (Teams, Past seasons, Contact the
league) and "Masters Basketball League · Thunder Bay, Ontario".

### Components (all in the mockups)
- **Result card:** both teams with colour chips and scores, with the winner in
  bold. Below a divider: "Top: [player] [pts]" and a "Box score ›" link.
- **Next game panel:** `--mb-panel` background, date, gym, and one row per game
  with its time, plus a bye line.
- **Standings table:** rank, team colour chip and name, then W, L, PCT, GB, plus
  PF, PA, DIFF, all on every screen size. On phones the table scrolls sideways
  inside its card and the team column stays fixed. There is no separate
  standings page: Home always shows the full table, with every team and no
  link to another page.
- **Leader card:** small uppercase label, big number in `--mb-accent`, player,
  team. The PPG card has a `--mb-hot` top edge; the FT% card has `--mb-accent`.
- **Ranked player row:** rank, name, a line with team · pts · GP, the number,
  and a chevron. Tapping opens the expanded row (FTM-FTA, FT%, season high,
  points-by-game-day bars with the latest game in `--mb-hot`, and a "Full
  player page" link).
- **Segmented control:** PPG / Points / FT % on the Stats page.
- **Team filter chips:** All plus one per team, with colour dots.

## Pages
Built from the parts above, in this order.

1. **Home** (`/`): as mocked up, phone and desktop.
2. **Stats** (`/stats/`): as mocked up. Add a full sortable table view behind
   "See all as a table", with columns GP, PTS, PPG, FTM, FTA, FT%, a sticky
   name column, and sort by any column. The team chips filter both views.
   Rank 1 is the card and the list starts at rank 2 ("Showing 7 of 50" counts
   the card). The FT % view only ranks players with the minimum attempts and
   says so. Without JavaScript: the card, the list (each player links to their
   page) and the full table. Desktop isn't mocked: the same single column,
   left-aligned, 760 px wide. Ends with a short "How stats are counted".
3. **Schedule** (`/schedule/`): weeks newest first, with a sticky week heading
   ("Week 8 · Thu Dec 3"). Played games use result cards; upcoming games use
   rows like the next-game panel's (teams, time, court). Byes are listed under
   the week. The next game day is highlighted.
4. **Teams** (`/teams/`): five team cards, each with a colour chip, name, W-L
   and rank. **Team page** (`/teams/<id>/`): team name with a colour bar,
   record, rank, then the roster as ranked player rows (PPG, with FT% in the
   sub-line), then that team's games as result cards and upcoming rows.
5. **Player page** (`/players/<id>/`): name, team, a big PPG number with GP,
   PTS, FTM-FTA and FT% beside it, the points-by-game bars, and a game log table
   (date, opponent, PTS, FTM-FTA) linking to box scores.
6. **Box score** (`/games/<game_id>/`): a header with the final score (result
   card, but larger), then one table per team: player, PTS, FTM, FTA, with a
   team totals row. Add a "Score sheet photo" link if the photo exists.
7. **Archive** (`/archive/`): list of seasons. Each **season page**
   (`/archive/<season>/`) shows final standings, playoff results and the season
   leaders (PPG and FT%), using the same components.
8. **404:** the header, "Page not found", and a link home.

## Behaviour
- While `sample_data: true` in `_config.yml`, every page reads the sample season
  and shows a slim banner under the header: "Preview with sample data. Real
  results start after the first game day."
- The current season is the default everywhere. A season switcher only lives in
  the Archive.
- All dates in Eastern time, written "Thu Dec 10", with times like "7:00 PM".
- Sorting and expanding rows are progressive enhancements: with JS off, the
  ranked list is just a list, and each player links to their player page.

## Open questions (use placeholders until answered)
- League domain and GitHub organization name
- ~~Gym name and courts~~ (answered: St. Pats, no courts; a game's gym is read from `schedule.csv`, blank meaning the season's gym)
- Real team names and colours (the five in the mockups are samples)
- Tiebreaker rules and playoff format
- Score sheet layout (affects the `/record-game` skill, not the site)

## Decisions made while building the remaining pages (step 4)
The brief didn't cover these. They are in the code now; change any of them here
and in the templates together.

**Schedule**
- Upcoming game days come first, soonest first, with the next game day
  highlighted (its games in the blue next-game panel). Results follow, newest
  week first. One newest-first list would have put next March at the top. A
  week that is only partly played sits under Upcoming and shows both kinds of
  game.
- Week headings are sticky inside their own week. The gym is shown once in each
  week heading; there is no court column. Playoff weeks read "Playoffs".

**Box score**
- The header is the result card, larger and not a link; team names, player
  names and top scorers in it link. Top scorers (ties included) get a "Top"
  badge and a tinted row. Every table has a team totals row. Names link only
  for the season the site is showing.
- "Score sheet photo" shows only when `score_sheet_links: true` in
  `_config.yml` and the photo exists. It is off.

**Player page**
- The big card is points per game with the player's rank ("No. 3 of 50
  players"); beside or below it are GP, PTS, FTM-FTA and FT%. The bars are
  regular-season games only. The game log is newest first, includes playoff
  games (badged "Playoff") and shows the result under the opponent's name.
- Subs are marked with a "Sub" badge on their page, in team rosters and in box
  scores.
- A player with no games shows "No games played yet".

**Teams**
- Team cards show the colour as a top bar, the W-L record and the rank, or "No
  games yet". The team page header has the colour as a bar on the left.
- The roster lists everyone on the team in `players.yml`: players with games
  as ranked rows (PPG, with FT% in the sub-line, ranked in order within the
  team), the rest below as "No games yet". Results are result cards, newest
  first; upcoming games are rows with their dates.
- Team names in the Home standings link to team pages. Result cards stay
  whole-card links to the box score, so the names inside them aren't links.

**Archive**
- The Archive lists the season being shown (badged "Current") and every past
  season, newest first, each with who tops the standings. With only the
  current season it says past seasons will appear once a season has finished.
- A season page shows "Standings so far" (current) or "Final standings"
  (past), the playoff games as result cards (no round names or champion, as
  the playoff format isn't decided), and the PPG and FT% leaders.
- Past seasons have box scores (their playoff cards link to them) but no
  player or team pages, so their names don't link.

**Other**
- 404: header, "Page not found" and a "Back to Home" button.
- New reusable parts: badge, button, surface card, tap link (a name that is also
  a 44 px target), game row, week heading, team card, season card, large result
  card.
- A link check (html-proofer) runs after the site is built and fails the
  deploy on a broken link, image, script or anchor. External links aren't
  checked.

## Changes from the full-site QA (step 5)

See `docs/qa/report.md` for the full list. None of these change the approved look:
- A "Skip to content" link is the first thing a keyboard user reaches. It stays
  off screen until it has focus, then shows over the header's top-left corner.
- The page is a column with the footer at the bottom of the window. On a short
  page (an empty schedule, the 404) the footer no longer stops halfway up with
  page background below it.
- Every page has its own `<title>` and meta description. Box score titles
  include the date, because the same two teams meet more than once a season.
  Share tags (Open Graph and Twitter) use the page's description and the
  social card.

## Changes for the real 2026-27 season

- Games are Saturday mornings, so "game night" is now "game day" everywhere
  ("Next game day", "Points by game day"). The mockups still say "night";
  that's the only difference.
- The league has no home team (one gym, "A vs B" on the printed schedule), so
  the player game log always says "vs", never "at".
- Cancelled games (`status: cancelled` in `schedule.csv`) reuse the game row
  and the existing `.badge`: muted names and a "Cancelled" badge where the time
  would be. A game day that is cancelled outright is headed by its date and the
  badge, with no week number and no bye line, and sits under Results.
- Team calendars: an "Add to your calendar" section on each team page and at
  the end of the Schedule page.
  - **Team page:** a **Calendar** pill beside the team name (icon only, in a
    44 px circle, under 480 px wide) jumps to the section. The section is a
    blue panel like Next game day: a one-line promise ("updates by itself"),
    two white buttons (**Apple Calendar**: webcal://, also works in Outlook;
    **Google Calendar**: Google's add-by-URL screen), how-to lines per device,
    and a small "download the file" link (a one-time copy).
  - **Schedule page:** the same panel without buttons, then a game row per
    team plus "Every game" with **Apple**, **Google** and **Download** links
    (under the name on phones).
- Playoff games whose teams aren't decided show as printed: the round in bold,
  then the placeholders ("**Semifinal (G42)** · 2nd vs 3rd"), in the same game
  row and next-game panel. Playoff weeks are headed "Playoffs · Sat Apr 24".
- Score sheets on the Schedule page (reusable include `score-sheet-links.html`):
  - Each game day still to play gets **Score sheet (PDF)** (landscape Legal)
    and a muted **Other layouts** disclosure (a `<details>`, so it works
    without JavaScript) with landscape Letter and portrait Letter and Legal.
    Both are `link-more` text links with 44 px tap areas. A link is only drawn
    when its PDF was generated, so past days and TBD playoff games get none.
  - A **Score sheets** section at the bottom lists the four blank layouts,
    with one line: print double-sided, page 2 is only for overflow.

## League rules, footer links and technical fouls

- **Footer:** Teams · Past seasons · **Score sheets** (to the blank sheets on
  the Schedule page) · **League rules** · Contact (when set). The links wrap on
  phones; each is a 44 px target.
- **League rules page** (`/rules/`): Markdown in `rules/index.md`, drawn by the
  reusable `text` layout. The page title, then "Last updated …" (or "Draft"
  while `updated` is blank), then the text in a readable column (`.prose`,
  68 characters wide) with the site's section-title style for `##` headings.
  It's in the footer only, not the header nav.
- **Technical fouls:**
  - **Player page:** a fifth tile, **Techs**. It's one row of five on phones,
    and beside the points card on desktop. A line under the tiles appears when
    some came in the playoffs. Games with one get a red **Tech** badge (or "2
    techs") in the game log.
  - **Stats page:** a **Technical fouls** list at the very bottom, reusing the
    rank row. It shows number, name, team and games, with the count on the
    right, and "No technical fouls yet." when there are none.
  - **Personal fouls** are recorded but shown nowhere.

## Jersey numbers

- Wherever a player is named, a known jersey number comes first: "#23 Dave M."
  (reusable include `player-name.html`; `stats.js` draws the No. 1 card the
  same way). The `#23` is a `.player-num` span in the muted text colour, with
  tabular figures, so the name stays the stronger of the two. On the blue
  panels it uses the panel's muted colour. A player without a number shows
  just the name.
- Places: result cards ("Top:"), leader cards, the Stats ranked list, No. 1
  card, FT card and table, rank rows (team rosters, technical fouls), box
  scores and the player page heading. Captions, page titles and alt-style
  text keep the plain name.
- Score sheet links on the Schedule page lead with **landscape Legal**.
