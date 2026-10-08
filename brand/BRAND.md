# Masters Basketball League · Thunder Bay: brand kit

Everything the website needs for its look, in light and dark. All logo files are
built from the league's original vector logo; nothing is redrawn by hand.

## Logo family

| File | What it is | Use it for |
|---|---|---|
| `logo/masters-badge.svg` | Round badge: ball, MASTERS, maple leaf with wings, on a Night Navy field | The main logo, on any background: site header, footer, print, social avatar |
| `logo/masters-badge-alt-blue.svg` | Same badge on a Masters Blue field with a navy ring | Alternative colourway (jerseys, merch) |
| `logo/masters-badge-alt-light.svg` | Same badge on a pale field | Alternative for light-only uses (letterhead, print on white) |
| `logo/masters-wordmark.svg` | Wordmark A: the badge's MASTERS with the leaf and wings, no ball or ring | Wide spaces on light backgrounds: banners, merch |
| `logo/masters-wordmark-dark.svg` | Same, with white wings | Wide spaces on dark backgrounds and photos |
| `logo/masters-wordmark-type.svg` | Wordmark B: MASTERS / THUNDER BAY in the site's typeface, maple leaf on the right | Text-style uses: email signatures, documents, the site footer |
| `logo/masters-wordmark-type-dark.svg` | Same, white and coral | Dark backgrounds |
| `logo/masters-icon.svg` | The badge's "M" inside a red basketball | Favicon, app icon, social avatar |
| `logo/masters-icon-alt-orange.svg` | Same in classic basketball orange | Alternative if the league prefers orange |

PNG copies are in `logo/png/`. Keep the SVGs as the source of truth. Every
file is cut from the league's original vector logo; "Basketball League" and the
ribbon are removed.

### Rules
- **Clear space:** keep empty space around any logo at least the height of the maple leaf.
- **Minimum sizes:** badge 32 px, wordmark 24 px tall, icon 16 px.
- **Backgrounds:** the round badge works on white, navy and the blue header,
  because its white inner ring always separates it from the background.
- **Don't** recolour the ball to match the field, stretch it, add effects, or
  bring back the ribbon text.

## Colours

| Name | Hex | Role |
|---|---|---|
| Masters Blue | `#032F98` | Primary. Header, links, buttons, numbers (light) |
| Maple Red | `#CB0E1D` | Accent only: active tab, No. 1, latest game. Never body text on blue |
| Night Navy | `#0B1B3F` | Text (light), footer, the Sleeping Giant, the badge's field |
| Ice | `#F4F6FB` | Page background (light) |
| White | `#FFFFFF` | Cards (light), text on blue |
| Sky Blue | `#8FB0FF` | Dark-mode version of Masters Blue (links, numbers) |
| Coral Red | `#FF5C66` | Dark-mode version of Maple Red; active-tab underline in both themes |
| Midnight | `#0A1022` | Page background (dark) |

Contrast checks (WCAG): Masters Blue on white 11.3:1, white on Masters Blue
11.3:1, Maple Red on white 5.8:1, Sky Blue on dark cards 8.0:1, muted text 5.5:1
or better in both themes. Red on blue is only 1.9:1, so don't use it for text.

### Light and dark tokens
`css/brand.css` defines every colour the site uses as a `--mb-*` variable. Dark
mode switches on automatically from the device setting
(`prefers-color-scheme`). A visitor's own choice with the sun/moon button sets
`data-theme="light"` or `"dark"` on `<html>` and wins over the device setting.
The choice is saved in `localStorage` (`mb-theme`), and the inline script in
`head-snippet.html` applies it before the page paints.

| Token | Light | Dark |
|---|---|---|
| `--mb-bg` | `#F4F6FB` | `#0A1022` |
| `--mb-surface` | `#FFFFFF` | `#131B34` |
| `--mb-line` | `#E3E8F2` | `#243052` |
| `--mb-text` | `#0B1B3F` | `#EEF2FF` |
| `--mb-muted` | `#5A6478` | `#9AA6C4` |
| `--mb-accent` / `--mb-link` | `#032F98` | `#8FB0FF` |
| `--mb-hot` | `#CB0E1D` | `#FF5C66` |
| `--mb-panel` | `#032F98` | `#1A2B6B` |
| `--mb-sky` | sunrise gradient | twilight gradient |
| `--mb-giant` | `#0B1B3F` | `#03060C` |
| `--mb-footer` | `#0B1B3F` | `#18214D` |
| `--mb-team-1…5` | team colours | lifted team colours |

Team colours are placeholders until the league confirms each team's colour.

## Type
- **Barlow Condensed** 600/700, uppercase with slight tracking, for headings,
  scores and big numbers.
- **Barlow** 400–700 for everything else.

Both are free Google Fonts (SIL Open Font License). Use tabular numbers
(`font-variant-numeric: tabular-nums`) in tables.

## Sleeping Giant header
`scenes/giant-sunrise.svg` (light) and `scenes/giant-moonset.svg` (dark) sit
at the bottom of the header, over the `--mb-sky` gradient. The outline is
traced from a photo of the Giant taken from Thunder Bay.
`scenes/giant-silhouette.svg` uses `currentColor` and goes in the footer.

## Web files
- `icons/`: `favicon.svg`, `favicon.ico` (16/32/48), `favicon-16/32.png`,
  `apple-touch-icon.png` (180), `icon-192/512.png`, `icon-maskable-512.png`
- `site.webmanifest`: lets people add the site to their phone's home screen
- `social/og-image.png`: 1200×630 preview card for links shared in texts and social media
- `head-snippet.html`: paste into the site's `<head>`, and replace `[YOUR DOMAIN]`
