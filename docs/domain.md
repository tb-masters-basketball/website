# Domain: mastersbasketball.ca

The site is served by GitHub Pages at **https://mastersbasketball.ca/**. The
domain is registered at Porkbun. `www.mastersbasketball.ca` redirects to it, and
the old address `https://tb-masters-basketball.github.io/website/` redirects too.

In the repo, the domain appears in `_config.yml` (`url`) and in the `CNAME` file.
Every page path goes through `relative_url`, so nothing else names it.

## DNS records at Porkbun

Porkbun → Account → Domain Management → mastersbasketball.ca → **DNS**.

First delete Porkbun's default parking records: an `ALIAS` or `A` record on the
bare domain, and a `CNAME` for `*` or `www` pointing at `pixie.porkbun.com` or
`uixie.porkbun.com`. Leave any `MX` or `TXT` records for email alone.

Then add these. Leave **Host** blank for the bare domain, and keep TTL at 600.

| Type | Host | Answer |
|---|---|---|
| A | (blank) | 185.199.108.153 |
| A | (blank) | 185.199.109.153 |
| A | (blank) | 185.199.110.153 |
| A | (blank) | 185.199.111.153 |
| AAAA | (blank) | 2606:50c0:8000::153 |
| AAAA | (blank) | 2606:50c0:8001::153 |
| AAAA | (blank) | 2606:50c0:8002::153 |
| AAAA | (blank) | 2606:50c0:8003::153 |
| CNAME | www | tb-masters-basketball.github.io |
| TXT | `_github-pages-challenge-tb-masters-basketball` | the code GitHub shows you (step 1 below) |

These are GitHub's published Pages addresses. The CNAME points at the
organization's Pages host and never includes `/website`.

## Steps, in order

1. **Verify the domain with GitHub.** This stops anyone else's repo from claiming it.
   - Go to GitHub → the `tb-masters-basketball` organization → **Settings** → **Pages**
     → **Add a domain**, and enter `mastersbasketball.ca`.
   - GitHub shows a TXT record. Add it at Porkbun (the last row above).
   - Click **Verify**. It can take a few minutes, sometimes up to a day.
2. **Add the A, AAAA and www CNAME records** above at Porkbun.
3. **Set the custom domain on the repo.**
   - Go to repo `website` → **Settings** → **Pages** → **Custom domain**.
   - Enter `mastersbasketball.ca` and click **Save**. Wait for "DNS check successful".
   - Because the site deploys through GitHub Actions, this setting is what counts.
     The `CNAME` file in the repo is a record of it.
4. **Merge the pull request** that sets `url` and `baseurl` in `_config.yml`. Do
   this right after step 3, because the two go together:
   - Until both are done, the site's links point at the wrong place and pages
     show without styles for a few minutes.
5. **Turn on HTTPS.**
   - Once GitHub has issued the certificate, tick **Enforce HTTPS** on the same
     Settings → Pages screen.
   - This usually takes 15 minutes to an hour after the DNS check passes.

## Checking it works

- `https://mastersbasketball.ca/` loads, with a padlock in the address bar.
- `https://www.mastersbasketball.ca/` and `http://mastersbasketball.ca/` both end up at
  `https://mastersbasketball.ca/`.
- `https://tb-masters-basketball.github.io/website/` redirects to the domain.
- On the page, open developer tools (F12) → **Network**, tick "Disable cache" and
  reload. Nothing should show 404, and the Console should have no red errors.
- The "Build and deploy" run in the Actions tab is green. Its link check fails the
  deploy if any page, image, stylesheet or script is missing.

From a terminal you can also check the records:

```
dig +short mastersbasketball.ca A          # the four 185.199.x.153 addresses
dig +short www.mastersbasketball.ca CNAME  # tb-masters-basketball.github.io.
```

## If something goes wrong

- **"Domain's DNS record could not be retrieved" or "improperly configured"** in
  Settings → Pages: the records haven't spread yet, or a Porkbun parking record is
  still there. Wait 10–30 minutes and click **Check again**.
- **Pages load without styles:** the custom domain is set but the `_config.yml`
  change isn't merged yet, or the other way round. Make sure both are done.
- **Enforce HTTPS is greyed out:** the certificate isn't ready. Remove the custom
  domain, save, add it again, and wait.
