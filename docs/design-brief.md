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
  PF, PA, DIFF on desktop and on the full standings page.
- **Leader card:** small uppercase label, big number in `--mb-accent`, player,
  team. The PPG card has a `--mb-hot` top edge; the FT% card has `--mb-accent`.
- **Ranked player row:** rank, name, a line with team · pts · GP, the number,
  and a chevron. Tapping opens the expanded row (FTM-FTA, FT%, season high,
  points-by-game-night bars with the latest game in `--mb-hot`, and a "Full
  player page" link).
- **Segmented control:** PPG / Points / FT % on the Stats page.
- **Team filter chips:** All plus one per team, with colour dots.

## Pages
Built from the parts above, in this order.

1. **Home** (`/`): as mocked up, phone and desktop.
2. **Stats** (`/stats/`): as mocked up. Add a full sortable table view behind
   "See all as a table", with columns GP, PTS, PPG, FTM, FTA, FT%, a sticky
   name column, and sort by any column. The team chips filter both views.
3. **Schedule** (`/schedule/`): weeks newest first, with a sticky week heading
   ("Week 8 · Thu Dec 3"). Played games use result cards; upcoming games use
   rows like the next-game panel's (teams, time, court). Byes are listed under
   the week. The next game night is highlighted.
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
- The current season is the default everywhere. A season switcher only lives in
  the Archive.
- All dates in Eastern time, written "Thu Dec 10", with times like "7:00 PM".
- Sorting and expanding rows are progressive enhancements: with JS off, the
  ranked list is just a list, and each player links to their player page.

## Open questions (use placeholders until answered)
- League domain and GitHub organization name
- ~~Gym name and courts~~ (answered: St. Pats, one court)
- Real team names and colours (the five in the mockups are samples)
- Tiebreaker rules and playoff format
- Score sheet layout (affects the `/record-game` skill, not the site)
