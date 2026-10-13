"""Phone screenshots of the /preview/ copy of the site, for a blog post.
Throwaway: lives only on the tmp/blog-screenshots branch.
Serves _site/ locally, captures each page at phone size in light and dark,
both the first screen ("screen") and the full page ("full")."""
import functools, http.server, re, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE = Path("_site").resolve()
OUT = Path("blog-shots/out")
OUT.mkdir(parents=True, exist_ok=True)
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}/preview/"
DRAFT = sorted(Path("data/sample-2026-27/drafts").glob("*.yml"))[0]

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()

def first_link(page, path, pattern, which="first"):
    page.goto(BASE + path, wait_until="networkidle")
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    hits = [h for h in hrefs if re.search(pattern, h)]
    if not hits:
        return None
    h = hits[0] if which == "first" else hits[-1]
    return h.split("/preview/", 1)[-1] if "/preview/" in h else h.lstrip("/")

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                                  is_mobile=True, has_touch=True, color_scheme=theme)
        page = ctx.new_page()
        pages = [("home", ""), ("stats", "stats/"), ("schedule", "schedule/"), ("teams", "teams/"),
                 ("archive", "archive/")]
        for name, path, pat, which in [("team", "teams/", r"/teams/[^/]+/$", "first"),
                                       ("player", "stats/", r"/players/[^/]+/$", "first"),
                                       ("box-score", "schedule/", r"/games/[^/]+/$", "first"),
                                       ("past-season", "archive/", r"/archive/[^/]+/$", "last")]:
            found = first_link(page, path, pat, which)
            if found is not None:
                pages.append((name, found))
        for name, path in pages:
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / f"{name}-{theme}-screen.png"))
            page.screenshot(path=str(OUT / f"{name}-{theme}-full.png"), full_page=True)
            print(theme, name, path, flush=True)
        # Stats with the first player row opened
        page.goto(BASE + "stats/", wait_until="networkidle")
        btn = page.query_selector("[aria-expanded='false']")
        if btn:
            btn.click(); page.wait_for_timeout(400)
            btn.scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, -120)")
            page.screenshot(path=str(OUT / f"stats-open-{theme}-screen.png"))
        # Entry page: start panel, then the sample draft loaded from a file
        page.goto(BASE + "enter/", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / f"enter-start-{theme}-screen.png"))
        page.set_input_files("#enter-file", str(DRAFT))
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / f"enter-sheet-{theme}-screen.png"))
        page.screenshot(path=str(OUT / f"enter-sheet-{theme}-full.png"), full_page=True)
        flag = page.query_selector(".is-flag") or page.query_selector(".is-error") or page.query_selector(".is-warning")
        if flag:
            flag.scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, -260)")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / f"enter-flag-{theme}-screen.png"))
        for sel, name in (("#enter-checks-title", "enter-checks"), ("#enter-save-title", "enter-save")):
            el = page.query_selector(sel)
            if el:
                el.scroll_into_view_if_needed(); page.evaluate("window.scrollBy(0, -80)")
                page.wait_for_timeout(300)
                page.screenshot(path=str(OUT / f"{name}-{theme}-screen.png"))
        print(theme, "enter done", flush=True)
        ctx.close()
    browser.close()
srv.shutdown()
