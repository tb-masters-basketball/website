#!/usr/bin/env python3
"""Screenshot every page of the site, and check each one for problems.

Builds the site the way the Actions workflow does (stats script, then a
production Jekyll build with the /website baseurl), once with sample data on
and once with it off, serves each build locally and captures:

  pages   Home, Stats (list and table view), Schedule, Teams, one team,
          one player, one box score, Archive, the past sample season, 404
  widths  360, 390 and 1440 px
  themes  light and dark (the system setting; nothing saved in localStorage)

Each screenshot is a full-page PNG at <out>/<mode>/<width>/<page>-<theme>.png.
While capturing, every page is also checked for:

  - sideways page scroll (document scrollWidth wider than the viewport)
  - console errors and uncaught script errors
  - any request that fails or returns 400 or above (CSS, fonts, images, ...)

The results go to <out>/checks.json, and the script exits with 1 if any
check failed. --contact-sheets also writes one contact sheet per width
(<out>/contact-<width>.png): every page, light and dark, sample and real.

Usage:
  python scripts/screenshot_all.py --out docs/qa/after --contact-sheets
  python scripts/screenshot_all.py --out /tmp/shots --modes sample --widths 390
  python scripts/screenshot_all.py --out /tmp/shots --no-build \\
      --base-url http://localhost:4000/website/      # use a site you serve

Needs: pip install playwright pillow pyyaml, and Chromium. If Playwright's own
browser isn't installed, set PLAYWRIGHT_CHROMIUM to a Chromium binary (the
script also tries /opt/pw-browsers/chromium).

The repo's _data/computed/ and stub folders are rebuilt for the normal
_config.yml when the script finishes.
"""

import argparse
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WIDTHS = [360, 390, 1440]
THEMES = ["light", "dark"]
MODES = {"sample": True, "real": False}  # mode name: value of sample_data
HEIGHT = 800  # viewport height; screenshots are full page anyway

# (name, how to find the address). A fixed path, or (pages to look on, link pattern, which
# match): the first page with a matching link wins. "@team" is the team page found above.
PAGES = [
    ("home", "/"),
    ("stats-list", "/stats/"),
    ("stats-table", "/stats/#stats-table"),
    ("schedule", "/schedule/"),
    ("teams", "/teams/"),
    ("team", ("/teams/", r"/teams/[^/]+/$", "first")),
    ("player", (["/stats/", "@team"], r"/players/[^/]+/$", "first")),
    ("box-score", ("/schedule/", r"/games/[^/]+/$", "first")),
    ("archive", "/archive/"),
    ("past-season", ("/archive/", r"/archive/[^/]+/$", "last")),
    ("404", "/404.html"),
]


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def build_site(sample, dest):
    """Stats + Jekyll build with sample_data set; the site lands in dest/<baseurl>/."""
    config = yaml.safe_load((ROOT / "_config.yml").read_text(encoding="utf-8"))
    baseurl = (config.get("baseurl") or "").strip("/")
    override = Path(tempfile.mkdtemp()) / "qa-config.yml"
    merged = dict(config, sample_data=sample)
    override.write_text(yaml.safe_dump(merged), encoding="utf-8")
    run([sys.executable, "scripts/build_stats.py", "--config", override])
    site = dest / baseurl if baseurl else dest
    env = dict(os.environ, JEKYLL_ENV="production")
    run(["bundle", "exec", "jekyll", "build", "--quiet", "--config", f"_config.yml,{override}", "-d", site], env=env)
    return baseurl


def serve(directory):
    """Serve a folder on a free local port in a background thread; returns the server."""
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def launch(playwright):
    try:
        return playwright.chromium.launch()
    except Exception:
        for exe in (os.environ.get("PLAYWRIGHT_CHROMIUM"), "/opt/pw-browsers/chromium"):
            if exe and Path(exe).exists():
                return playwright.chromium.launch(executable_path=exe)
        raise


def resolve_pages(browser, base):
    """Turn PAGES into {name: url}, following links for the pages picked from a list."""
    found = {}
    page = browser.new_page()
    for name, where in PAGES:
        if isinstance(where, str):
            found[name] = base + where.lstrip("/")
            continue
        indexes, pattern, which = where
        found[name] = None
        for index in [indexes] if isinstance(indexes, str) else indexes:
            url = found.get(index[1:]) if index.startswith("@") else base + index.lstrip("/")
            if not url:
                continue
            page.goto(url)
            hrefs = page.eval_on_selector_all("main a[href]", "els => els.map(e => e.href)")
            matches = [h for h in hrefs if re.search(pattern, h.split("#")[0])]
            if matches:
                found[name] = matches[0] if which == "first" else matches[-1]
                break
    page.close()
    return found


def capture(browser, url, width, theme, path):
    """One screenshot plus its checks. Returns a dict of what was found."""
    context = browser.new_context(viewport={"width": width, "height": HEIGHT}, color_scheme=theme)
    page = context.new_page()
    problems = []
    page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"script error: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"request failed: {r.url} ({r.failure})"))

    def on_response(response):
        if response.status >= 400 and not (response.url.endswith("/404.html") and response.status == 404):
            problems.append(f"HTTP {response.status}: {response.url}")

    page.on("response", on_response)
    page.goto(url, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    sizes = page.evaluate(
        "({scroll: document.documentElement.scrollWidth, viewport: window.innerWidth,"
        " theme: getComputedStyle(document.documentElement).colorScheme, title: document.title})"
    )
    if sizes["scroll"] > sizes["viewport"]:
        problems.append(f"sideways scroll: page is {sizes['scroll']} px wide in a {sizes['viewport']} px viewport")
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    context.close()
    return {"url": url, "width": width, "theme": theme, "title": sizes["title"],
            "scroll_width": sizes["scroll"], "problems": problems}


def contact_sheets(out, widths, modes):
    """One PNG per width: a row per page, a column per mode and theme (top of each page)."""
    from PIL import Image, ImageDraw, ImageFont

    def font(size):
        for f in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
        return ImageFont.load_default()

    label_font, head_font = font(15), font(17)
    columns = [(m, t) for m in modes for t in THEMES]
    for width in widths:
        scale = 0.5 if width < 1000 else 0.3
        crop = 1500 if width < 1000 else 1100  # source pixels kept from the top of each page
        cell_w, cell_h = int(width * scale), int(crop * scale)
        gap, left, top = 16, 130, 40
        sheet = Image.new("RGB", (left + len(columns) * (cell_w + gap), top + len(PAGES) * (cell_h + gap)), "white")
        draw = ImageDraw.Draw(sheet)
        for c, (mode, theme) in enumerate(columns):
            draw.text((left + c * (cell_w + gap), 10), f"{mode} · {theme}", fill="black", font=head_font)
        for r, (name, _) in enumerate(PAGES):
            y = top + r * (cell_h + gap)
            draw.text((8, y + 4), name, fill="black", font=label_font)
            for c, (mode, theme) in enumerate(columns):
                x = left + c * (cell_w + gap)
                shot = out / mode / str(width) / f"{name}-{theme}.png"
                if not shot.exists():
                    draw.rectangle([x, y, x + cell_w, y + cell_h], outline="#999")
                    draw.text((x + 8, y + 8), "not on this site", fill="#666", font=label_font)
                    continue
                with Image.open(shot) as im:
                    im = im.convert("RGB").crop((0, 0, im.width, min(im.height, crop)))
                    im = im.resize((cell_w, int(im.height * scale)), Image.LANCZOS)
                    sheet.paste(im, (x, y))
                    draw.rectangle([x - 1, y - 1, x + cell_w, y + im.height], outline="#bbb")
        dest = out / f"contact-{width}.png"
        sheet.save(dest, optimize=True)
        print("wrote", dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="folder for the screenshots and checks.json")
    parser.add_argument("--modes", nargs="+", choices=list(MODES), default=list(MODES))
    parser.add_argument("--widths", nargs="+", type=int, default=WIDTHS)
    parser.add_argument("--themes", nargs="+", choices=THEMES, default=THEMES)
    parser.add_argument("--no-build", action="store_true", help="use --base-url instead of building (one mode only)")
    parser.add_argument("--base-url", help="with --no-build: the site's address, e.g. http://localhost:4000/website/")
    parser.add_argument("--contact-sheets", action="store_true", help="also write one contact sheet per width")
    args = parser.parse_args()
    if args.no_build and (not args.base_url or len(args.modes) != 1):
        parser.error("--no-build needs --base-url and exactly one --modes value")

    from playwright.sync_api import sync_playwright

    out = args.out.resolve()
    for mode in args.modes:
        shutil.rmtree(out / mode, ignore_errors=True)
    results, failed = [], 0
    work = Path(tempfile.mkdtemp(prefix="mb-qa-"))
    try:
        with sync_playwright() as p:
            browser = launch(p)
            for mode in args.modes:
                server = None
                if args.no_build:
                    base = args.base_url.rstrip("/") + "/"
                else:
                    baseurl = build_site(MODES[mode], work / mode)
                    server = serve(work / mode)
                    base = f"http://127.0.0.1:{server.server_address[1]}/" + (baseurl + "/" if baseurl else "")
                urls = resolve_pages(browser, base)
                for name, url in urls.items():
                    if url is None:
                        print(f"  {mode:6} {name:12} not on this site")
                        results.append({"mode": mode, "page": name, "url": None, "problems": []})
                        continue
                    for width in args.widths:
                        for theme in args.themes:
                            shot = out / mode / str(width) / f"{name}-{theme}.png"
                            result = capture(browser, url, width, theme, shot)
                            result.update(mode=mode, page=name)
                            results.append(result)
                            failed += bool(result["problems"])
                            mark = "FAIL" if result["problems"] else "ok"
                            print(f"  {mode:6} {name:12} {width:5} {theme:5} {mark}")
                            for problem in result["problems"]:
                                print("        ", problem)
                if server:
                    server.shutdown()
            browser.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if not args.no_build:
            run([sys.executable, "scripts/build_stats.py"])  # back to the normal _config.yml

    out.mkdir(parents=True, exist_ok=True)
    (out / "checks.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    if args.contact_sheets:
        contact_sheets(out, args.widths, args.modes)
    shots = sum(1 for r in results if r.get("url"))
    print(f"{shots} screenshots, {failed} with problems; details in {out / 'checks.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
