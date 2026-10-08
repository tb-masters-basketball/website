# Start here: Masters Basketball site handoff

This folder is everything Claude Code needs to build the league website. Unzip
it into the root of the new GitHub repo and commit it as the first commit.

## What's inside
| Path | What it is |
|---|---|
| `CLAUDE.md` | Project instructions Claude Code reads every session: stack, layout, rules |
| `data/CLAUDE.md` | Data file formats, IDs and stat rules |
| `docs/design-brief.md` | The design spec: approved look, components, and every page to build |
| `docs/mockups/` | Approved mockups as HTML pages you can open in a browser, plus PNG screenshots |
| `docs/open-questions.md` | League decisions still needed; the site uses placeholders until then |
| `brand/` | Logos, icons, favicon, colours (`css/brand.css`), Sleeping Giant scenes, social card, `BRAND.md` |

## Steps
1. **Create the GitHub organization** `tb-masters-basketball`, then
   an empty repo in it called `website`. Add a second admin.
2. **Unzip this folder** into the repo and push it.
3. **Open Claude Code on the repo** (web, desktop or phone) and build in this order,
   one session per step, reviewing the screenshots at each step:
   1. "Read CLAUDE.md and docs/design-brief.md. Scaffold the Jekyll site, the
      GitHub Actions deploy workflow and the build_stats script, and generate
      the sample season described in data/CLAUDE.md."
   2. "Build the header, footer, theme toggle and the Home page to match
      docs/mockups. Show me screenshots at 390 and 1440 px in both themes."
   3. "Build the Stats page and its full table view."
   4. "Build Schedule, Teams, Team, Player, Box score, Archive and 404 pages
      from the design brief."
   5. "Check every page at 360, 390 and 1440 px in both themes for overflow,
      contrast and anything that doesn't match the mockups. Fix what you find."
4. **Turn on GitHub Pages** (Settings → Pages → Source: GitHub Actions). The site
   goes live at `https://tb-masters-basketball.github.io/website/`.
5. **Domain:** once it's bought, ask Claude Code to "move the site to
   [domain]". It changes `baseurl`, adds the `CNAME` file and fills in the
   share tags, and gives you the DNS records. You add those records at the
   registrar, enter the domain under Settings → Pages, and tick "Enforce HTTPS"
   once the certificate is issued.

After the site works, the next stage is the `/record-game` skill that turns a
photo of the score sheet into a game file. That needs a sample score sheet first.

## Where the design lives
The full design canvas (all six directions, logo work, brand kit) is in Claude
at the canvas link from the planning chat. This folder is a snapshot of the
approved parts.
