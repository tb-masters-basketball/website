#!/usr/bin/env python3
"""The measuring half of /record-game (.claude/skills/record-game/SKILL.md):
turn a photo of a score sheet into a straight page, a crop of each section and
a measure of the pen ink in every box, so that whoever reads the sheet (Claude,
or a person) only has to read the handwriting, and knows where it is.

    python scripts/record_game.py prepare PHOTO [PHOTO2] --out DIR [--season ID] [--game GAME_ID] [--layout L]
    python scripts/record_game.py zoom DIR PATH...      # a close-up of boxes by path (running.lh.27 ...)
    python scripts/record_game.py compare DRAFT SECOND  # two readings of the running score: where they differ
    python scripts/record_game.py check FILE.yml        # the rules on one game file (draft or final)
    python scripts/record_game.py save DRAFT PHOTO...   # the draft into drafts/, the photo into sheets/

prepare, for each photo (page 1, and page 2 if there is one):
  1. finds the four black corner squares and straightens the page with them;
     works out the layout (portrait/landscape, Letter/Legal) and the page by
     matching the straightened photo against each blank sheet
  2. finds the game: --game, else the scheduled game whose pre-printed sheet
     (game id, team names, rosters) matches the photo best
  3. measures the ink in every box against that game's pre-printed sheet, so
     the printed names, numbers and lines don't count, only pen
  4. writes into DIR:
       page1.jpg, page2.jpg  the straightened pages
       crops/*.png           one image per section, to read from
       marks.json            the ink in every box (0 = clean, 1 = solid)
       report.md             what the ink says, box by box, and what to read
       start.yml             a draft to finish: the printed rows, ticks,
                             circles, fouls and lines from the ink, and "?" in
                             every running-score box that has writing

Box positions come from scoresheet.py (--geometry); the rules from
sheet_rules.py. Needs numpy, Pillow and pypdfium2 (in requirements.txt).
"""
import argparse
import io
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "scoresheet"))
import build_stats  # noqa: E402
import scoresheet as ss  # noqa: E402
import sheet_rules  # noqa: E402

PX = 4            # pixels per point on the straightened page (288 dpi)
LOW = 1           # pixels per point when matching layouts
GAME_PX = 1.5     # pixels per point when matching games
DARK = 0.72       # after evening out the light, paper is 1.0; darker than this is ink
FAINT = 0.80      # ... and darker than this is faint ink (thin strokes in a blurred photo)
LAYOUTS = [f"{o}-{s}" for o, s in ss.LAYOUTS]

# How much ink (the share of a box's area) means what. Tuned on the practice
# photos (scripts/record_game_eval.py); between two levels is "unsure".
HERE_TICK = (0.02, 0.04)        # below: empty; above: ticked
SLASH = (0.02, 0.045)           # T boxes: below empty, above slashed
FOUL = (0.008, 0.03)            # foul boxes, faint ink counted (their printed digit hides part of a slash)
CIRCLE_MARK = (0.04, 0.08)      # free-throw circle: below empty, above marked
CIRCLE_FILLED = 0.93            # marked circle: this much of its middle inked, and round (under 1.4), is filled
CIRCLE_SLASH = 1.6              # marked circle: a mark this long and thin is a slash (missed)
WRITTEN = (0.008, 0.018)        # digit box, number or name box: below empty, above written
RUN_WRITTEN = (0.014, 0.03)     # running score box, faint ink counted
CORRECTION = (0.04, 0.08)       # pen in the number or name box of a printed row (a blurred photo leaves some)
SOFT_DPI = 150                  # a photo with fewer pixels per inch of paper than this is soft
LINE = (0.45, 0.65)             # the end-of-quarter line under a running box


# ---------------------------------------------------------------- the sheet
_GEO = None


def geometry():
    global _GEO
    if _GEO is None:
        _GEO = ss.geometry_json()
    return _GEO


def page_geo(layout, page):
    return geometry()["layouts"][layout]["pages"][page - 1]


def sheet_pdf(layout, games, back=True):
    """The score sheet PDF for these games (blank when games is [{}])."""
    orient, size = layout.split("-")
    buf = io.BytesIO()
    ss.build(buf, games, size, orient, back=back)
    return buf.getvalue()


def render(pdf, scale):
    """Every page of a PDF as greyscale arrays, 0 (black) to 1 (white)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    doc.init_forms()             # the pre-printed text is in form fields
    out = []
    for i in range(len(doc)):
        im = doc[i].render(scale=scale, may_draw_forms=True).to_pil().convert("L")
        out.append(np.asarray(im, np.float32) / 255)
    return out


# ---------------------------------------------------------------- the season
def season_dir(season_id=None):
    if season_id:
        p = Path(season_id)
        return p if p.is_dir() else ROOT / "data" / season_id
    seasons = yaml.safe_load((ROOT / "data" / "seasons.yml").read_text(encoding="utf-8"))
    return ROOT / "data" / next(s["id"] for s in seasons if s.get("current"))


def find_season(gid):
    """The season folder whose schedule has this game (the current season first)."""
    seasons = yaml.safe_load((ROOT / "data" / "seasons.yml").read_text(encoding="utf-8"))
    for s in sorted(seasons, key=lambda s: not s.get("current")):
        path = ROOT / "data" / s["id"] / "schedule.csv"
        if path.exists() and any(line.split(",")[0].strip() == gid for line in path.read_text().splitlines()):
            return ROOT / "data" / s["id"]
    return None


def load_season(sdir):
    problems = []
    teams = build_stats.load_teams(sdir, problems)
    players = build_stats.load_players(sdir, teams, problems)
    schedule = build_stats.load_schedule(sdir, teams, problems)
    return teams, players, schedule, problems


def printed_games(sdir):
    """Every game with a pre-printed sheet, as scoresheet.py prints it."""
    return ss.load_games(str(sdir))


def printed_ids(game, tid, players):
    """The player id on each printed roster row of one team."""
    out = []
    for row in game["home" if game["_home"] == tid else "away"]["players"]:
        pid = next((pid for pid, p in players.items() if p.get("team") == tid and not p.get("sub")
                    and p.get("display") == row["name"] and str(p.get("number") or "") == row["num"]), None)
        out.append({"player": pid, "num": row["num"], "name": row["name"]})
    return out


# ---------------------------------------------------------------- images
def background(gray):
    """The light falling on the paper (a PIL L image): the brightest nearby
    paper, smoothed. Dividing by it evens out shadows and dim corners."""
    w, h = gray.size
    k = max(1, round(max(w, h) / 220))
    small = gray.resize((max(1, w // k), max(1, h // k)), Image.Resampling.BOX)
    small = small.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MaxFilter(5))
    small = small.filter(ImageFilter.GaussianBlur(2))
    return small.resize((w, h), Image.Resampling.BILINEAR)


def flatten(gray):
    g = np.asarray(gray, np.float32)
    bg = np.maximum(np.asarray(background(gray), np.float32), 24)
    return np.clip(g / bg, 0, 1), bg


def boxsum(ii, s):
    return ii[s:, s:] - ii[:-s, s:] - ii[s:, :-s] + ii[:-s, :-s]


def find_corners(photo):
    """The centres of the four corner squares in the photo (pixels), in the
    order top-left, top-right, bottom-right, bottom-left as the photo shows them."""
    gray = photo.convert("L")
    f = min(1.0, 1000 / max(gray.size))
    small = gray.resize((round(gray.width * f), round(gray.height * f)), Image.Resampling.BOX) if f < 1 else gray
    flat, _ = flatten(small)
    big = max(flat.shape)
    # a square right at the photo's edge: count what's past the edge as white paper
    E = int(big * 0.05)
    d = np.pad(1 - flat, E)
    ii = np.pad(d.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    found = []
    for s in range(max(5, int(big * 0.006)), int(big * 0.05) + 1):
        m = max(2, round(s * 0.5))
        S = s + 2 * m
        if S >= min(d.shape):
            break
        outer = boxsum(ii, S)
        inner = boxsum(ii, s)[m:m + outer.shape[0], m:m + outer.shape[1]]
        score = inner / (s * s) - (outer - inner) / (S * S - s * s)
        for _ in range(10):
            i = int(np.argmax(score))
            y, x = divmod(i, score.shape[1])
            v = score[y, x]
            if v < 0.45:
                break
            found.append((float(v), x + m + s / 2 - E, y + m + s / 2 - E, s))
            r = int(1.5 * s)
            score[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = -1
    found.sort(reverse=True)
    kept = []
    for c in found:
        if all(math.hypot(c[1] - k[1], c[2] - k[2]) > 1.5 * max(c[3], k[3]) for k in kept):
            kept.append(c)
        if len(kept) >= 14:
            break
    best = None
    for quad in itertools.combinations(kept, 4):
        sizes = [q[3] for q in quad]
        if max(sizes) > 1.7 * min(sizes):
            continue
        pts = order([(q[1], q[2]) for q in quad])
        if not page_shaped(pts):
            continue
        # the four squares are printed the same size: a quad of matched sizes
        # beats a slightly bigger one that takes in a dark patch of the table
        val = polygon_area(pts) * min(q[0] for q in quad) * (min(sizes) / max(sizes)) ** 2
        if best is None or val > best[0]:
            best = (val, quad)
    if best is None:
        # one square hidden (cut off, in shadow, under a thumb): the other three
        # and the page's shape give it
        for tri in itertools.combinations(kept, 3):
            sizes = [q[3] for q in tri]
            if max(sizes) > 1.7 * min(sizes):
                continue
            for k in range(3):
                a, b, c = tri[k], tri[(k + 1) % 3], tri[(k + 2) % 3]   # b..: a is the corner between
                fourth = (b[1] + c[1] - a[1], b[2] + c[2] - a[2], a[3])
                pts = order([(a[1], a[2]), (b[1], b[2]), (c[1], c[2]), fourth[:2]])
                if not page_shaped(pts):
                    continue
                val = polygon_area(pts) * min(q[0] for q in tri) * 0.5
                if best is None or val > best[0]:
                    best = (val, (a, b, c, (0.0, *fourth)))
    if best is None:
        raise SystemExit("couldn't find the corner squares: photograph the whole sheet, flat, "
                         "with all four black squares in view")
    # refine each centre on the full photo: the middle of the dark pixels around it
    g = np.asarray(gray, np.float32)
    out = []
    for v, cx, cy, s in best[1]:
        cx, cy, half = cx / f, cy / f, max(4, int(s / f))
        if v == 0:                       # worked out from the other three, not seen
            out.append((cx, cy))
            continue
        x0, y0 = max(0, int(cx - half)), max(0, int(cy - half))
        win = g[y0:int(cy + half) + 1, x0:int(cx + half) + 1]
        dark = win < (win.min() + win.max()) / 2
        ys, xs = np.nonzero(dark)
        out.append((x0 + xs.mean(), y0 + ys.mean()) if len(xs) else (cx, cy))
    return order(out)


def order(pts):
    """Clockwise as the photo shows them (y points down), from the one up and to the left."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def polygon_area(p):
    return abs(sum(p[i][0] * p[(i + 1) % 4][1] - p[(i + 1) % 4][0] * p[i][1] for i in range(4))) / 2


def page_shaped(p):
    """Could these four points (in order) be a sheet's corners seen by a phone:
    convex, opposite sides about equal, corners about square?"""
    if not convex(p):
        return False
    side = [math.dist(p[i], p[(i + 1) % 4]) for i in range(4)]
    if min(side) < 1:
        return False
    for i in range(2):
        if not 0.7 < side[i] / side[i + 2] < 1.43:
            return False
    for i in range(4):
        a, b, c = p[i - 1], p[i], p[(i + 1) % 4]
        v1, v2 = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
        cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))
        if abs(cos) > 0.42:              # within about 25 degrees of square
            return False
    return True


def convex(p):
    signs = []
    for i in range(4):
        a, b, c = p[i], p[(i + 1) % 4], p[(i + 2) % 4]
        signs.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) > 0)
    return all(signs) or not any(signs)


def homography(src, dst):
    """The 8 coefficients mapping src points to dst points (Pillow's PERSPECTIVE order)."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return tuple(np.linalg.solve(np.array(a, float), np.array(b, float)))


def page_corners(layout):
    """Centres of the corner squares on the page, in points: TL, TR, BR, BL."""
    c = [(x + w / 2, y + h / 2) for x, y, w, h in page_geo(layout, 1)["corners"]]
    return [min(c, key=lambda p: p[0] + p[1]), max(c, key=lambda p: p[0] - p[1]),
            max(c, key=lambda p: p[0] + p[1]), max(c, key=lambda p: p[1] - p[0])]


def warp(img, corners, layout, turn, scale):
    """The page straightened: `scale` pixels per point. `turn` (0-3) says which
    photo corner is the page's top-left."""
    W, H = geometry()["layouts"][layout]["page_size"]
    src = [(x * scale, y * scale) for x, y in page_corners(layout)]
    dst = [corners[(i + turn) % 4] for i in range(4)]
    coeffs = homography(src, dst)
    return img.transform((round(W * scale), round(H * scale)), Image.Transform.PERSPECTIVE, coeffs,
                         Image.Resampling.BICUBIC, fillcolor=(255, 255, 255) if img.mode == "RGB" else 255)


def ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / (math.sqrt((a * a).sum() * (b * b).sum()) + 1e-9))


_BLANKS = {}


def blank(layout, scale):
    if (layout, scale) not in _BLANKS:
        _BLANKS[(layout, scale)] = render(sheet_pdf(layout, [{}]), scale)
    return _BLANKS[(layout, scale)]


def identify_page(photo, corners, layouts):
    """(score, layout, page, turn) of the best match among the blank sheets."""
    gray = photo.convert("L")
    f = min(1.0, 1400 / max(gray.size))
    small = gray.resize((round(gray.width * f), round(gray.height * f)), Image.Resampling.BOX)
    sc = [(x * f, y * f) for x, y in corners]
    best = None
    for layout in layouts:
        pages = blank(layout, LOW)
        for turn in range(4):
            w = warp(small, sc, layout, turn, LOW)
            flat, _ = flatten(w)
            for p, tmpl in enumerate(pages):
                m = 40
                score = ncc(1 - flat[m:-m, m:-m], 1 - tmpl[m:-m, m:-m])
                if best is None or score > best[0]:
                    best = (score, layout, p + 1, turn)
    return best


def identify_game(flat, layout, page, games):
    """Rank the games by how well their pre-printed sheet matches the photo:
    the header boxes and the roster's number and name columns."""
    if not games:
        return []
    scale = GAME_PX
    small = np.asarray(Image.fromarray((flat * 255).astype(np.uint8)).resize(
        (round(flat.shape[1] * scale / PX), round(flat.shape[0] * scale / PX)), Image.Resampling.BOX), np.float32) / 255
    pg = page_geo(layout, page)
    header = [pg["header"][k] for k in ("date", "time", "game_id")]
    teams = []
    for side in ("home", "away"):
        teams.append(pg[side]["bar"])
        for r in pg[side]["rows"]:
            teams += [r["num"], r["name"]]
    pdf = sheet_pdf(layout, games, back=True)
    pages = render(pdf, scale)

    def part(tmpl, rects):
        a, b = [], []
        for x, y, w, h in rects:
            x0, y0, x1, y1 = (int(round(v * scale)) for v in (x, y, x + w, y + h))
            a.append((1 - small[y0:y1, x0:x1]).ravel())
            b.append((1 - tmpl[y0:y1, x0:x1]).ravel())
        return ncc(np.concatenate(a), np.concatenate(b))

    ranked = []
    for i, g in enumerate(games):
        tmpl = pages[2 * i + page - 1]
        ranked.append(((part(tmpl, header) + part(tmpl, teams)) / 2, g["game_id"]))
    ranked.sort(reverse=True)
    return ranked


# ---------------------------------------------------------------- measuring ink
class Page:
    """One straightened page and its pre-printed sheet, for measuring ink."""

    def __init__(self, rgb, layout, page, tmpl):
        self.layout, self.page = layout, page
        gray = rgb.convert("L")
        self.flat, bg = flatten(gray)
        rgbf = np.asarray(rgb, np.float32) / np.maximum(bg, 24)[..., None]
        self.rgb = Image.fromarray(np.clip(rgbf * 255, 0, 255).astype(np.uint8))
        self.tmpl = tmpl
        self.ink = self.flat < DARK
        self.faint = self.flat < FAINT
        tdark = Image.fromarray(((tmpl < 0.82) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
        self.printed = np.asarray(tdark) > 0
        self.geo = page_geo(layout, page)
        self.regions = self._regions()

    def _regions(self):
        """Parts of the page, each lined up on its own with the printed sheet
        (a photo of a curled page is a few points off here and there)."""
        g, out = self.geo, []
        out.append(("header", [16, 16, self.flat.shape[1] / PX - 32, 70]))
        for side in ("home", "away"):
            x, y, w, h = g[side]["block"]
            n = max(2, round(h / 50))       # bands of about three rows, left and right halves
            for k in range(n):
                for j in range(2):
                    out.append((f"{side}-{k}{'lr'[j]}", [x + j * w / 2, y + k * h / n, w / 2, h / n]))
        if "notes" in g:
            out.append(("notes", g["notes"]))
        for i, (x, y, w, h) in enumerate(g["running_columns"]):
            n = max(3, round(h / 70))
            for k in range(n):
                out.append((f"run{i}-{k}", [x, y + k * h / n, w, h / n]))
        shifts = []
        for name, rect in out:
            shifts.append((name, rect, self.align(rect)))
        return shifts

    def align(self, rect, reach=7):
        R = int(reach * PX)
        x0, y0, w, h = (int(round(v * PX)) for v in rect)
        T = 1 - self.tmpl[y0:y0 + h, x0:x0 + w]
        H, W = self.flat.shape
        P = np.zeros((h + 2 * R, w + 2 * R), np.float32)
        ys, xs = max(0, y0 - R), max(0, x0 - R)
        ye, xe = min(H, y0 + h + R), min(W, x0 + w + R)
        P[ys - (y0 - R):ye - (y0 - R), xs - (x0 - R):xe - (x0 - R)] = 1 - self.flat[ys:ye, xs:xe]
        T = T - T.mean()
        corr = np.fft.irfft2(np.fft.rfft2(P) * np.conj(np.fft.rfft2(T, s=P.shape)), s=P.shape)
        dy, dx = np.unravel_index(int(np.argmax(corr[:2 * R + 1, :2 * R + 1])), (2 * R + 1, 2 * R + 1))
        return int(dx) - R, int(dy) - R

    def shift(self, box):
        cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
        best = None
        for name, (x, y, w, h), s in self.regions:
            if x <= cx <= x + w and y <= cy <= y + h and (best is None or w * h < best[0]):
                best = (w * h, s)
        return best[1] if best else (0, 0)

    def _cut(self, box, grow=0.0):
        x, y, w, h = box
        x, y, w, h = x - grow, y - grow, w + 2 * grow, h + 2 * grow
        dx, dy = self.shift(box)
        x0, y0 = int(round(x * PX)), int(round(y * PX))
        x1, y1 = int(round((x + w) * PX)), int(round((y + h) * PX))
        return (slice(y0 + dy, y1 + dy), slice(x0 + dx, x1 + dx)), (slice(y0, y1), slice(x0, x1))

    def _extra(self, box, grow=0.0, faint=False, reach=None):
        """Pen in a box: ink in the photo that isn't printed on the sheet. A
        printed sheet sits a few pixels off the template here and there (paper
        feed, dot gain, a curl), so the box is tried a few pixels each way and
        the least ink kept: printed lines then line up and drop out, while pen
        stays pen wherever the box is put."""
        reach = 3 if reach is None else reach
        p, t = self._cut(box, grow)
        ink = self.faint if faint else self.ink
        printed = self.printed[t]
        best = None
        H, W = ink.shape
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                ys, xs = slice(p[0].start + dy, p[0].stop + dy), slice(p[1].start + dx, p[1].stop + dx)
                if ys.start < 0 or xs.start < 0 or ys.stop > H or xs.stop > W:
                    continue
                e = ink[ys, xs] & ~printed
                if e.shape != printed.shape:
                    continue
                n = int(e.sum())
                if best is None or n < best[0]:
                    best = (n, e)
        return best[1] if best else np.zeros((0, 0), bool)

    def ink_in(self, box, grow=0.0, disk=False, faint=False, reach=None):
        """The share of a box covered by pen (printed marks don't count)."""
        extra = self._extra(box, grow, faint, reach)
        if extra.size == 0:
            return 0.0
        if disk:
            h, w = extra.shape
            yy, xx = np.mgrid[0:h, 0:w]
            mask = (yy - (h - 1) / 2) ** 2 + (xx - (w - 1) / 2) ** 2 <= (min(h, w) / 2) ** 2
            return round(float(extra[mask].mean()), 3)
        return round(float(extra.mean()), 3)

    def circle(self, box, reach=None):
        """A free-throw circle: [ink, centre, long] = the share of the circle
        with pen, the share of its middle with pen, and how long and thin
        the pen mark is (about 1 for a filled circle, 2 or more for a slash)."""
        extra = self._extra(box, 0.2, reach=reach)
        if extra.size == 0:
            return [0.0, 0.0, 0.0]
        h, w = extra.shape
        yy, xx = np.mgrid[0:h, 0:w]
        d2 = (yy - (h - 1) / 2) ** 2 + (xx - (w - 1) / 2) ** 2
        r = min(h, w) / 2
        disk, mid = d2 <= r * r, d2 <= (0.45 * r) ** 2
        on = extra & disk
        long = 0.0
        if on.sum() >= 6:
            ev = np.linalg.eigvalsh(np.cov(np.vstack([yy[on], xx[on]]).astype(float)))
            long = float(math.sqrt(max(ev[1], 1e-6) / max(ev[0], 1e-6)))
        return [round(float(on.sum() / disk.sum()), 3), round(float(extra[mid].mean()), 3), round(min(long, 9.0), 2)]

    def band(self, box):
        """Pen and printed ink just under a box: how many pixels deep it is at
        each point across the box's width."""
        x, y, w, h = box
        p, _ = self._cut([x + 1.5, y + h - 2.6, w - 3, 5.2])
        return self.ink[p].sum(0)

    def crop(self, box, path, pad=4):
        x, y, w, h = box
        dx, dy = self.shift(box)
        x0, y0 = max(0, int((x - pad) * PX) + dx), max(0, int((y - pad) * PX) + dy)
        x1, y1 = int((x + w + pad) * PX) + dx, int((y + h + pad) * PX) + dy
        im = self.rgb.crop((x0, y0, x1, y1))
        if max(im.size) > 1500:
            k = 1500 / max(im.size)
            im = im.resize((round(im.width * k), round(im.height * k)), Image.Resampling.LANCZOS)
        im.save(path)
        return path


def level(v, lo_hi):
    lo, hi = lo_hi
    return "yes" if v >= hi else ("no" if v < lo else "unsure")


def both(pg, box, levels, grow=0.0, faint=False):
    """A box measured as placed and with a few pixels' give (see Page._extra).
    The two agree almost always; when they don't (a faint mark, or printing a
    little off), the reading is put in the unsure band, to be looked at."""
    tight = pg.ink_in(box, grow, faint=faint, reach=0)
    loose = pg.ink_in(box, grow, faint=faint)
    if level(tight, levels) == level(loose, levels):
        return loose
    return round((levels[0] + levels[1]) / 2, 3)


def both_circle(pg, box):
    """A circle measured both ways; a fourth value 1 when they disagree."""
    loose = pg.circle(box)
    tight = pg.circle(box, reach=0)
    return loose if circle_mark(loose) == circle_mark(tight) else loose + [1]


def circle_mark(v):
    """'.' empty, 'M' filled, 'X' slashed, '?' can't tell, from [ink, centre, long]
    (and a fourth value 1: the two ways of measuring disagree)."""
    if len(v) > 3 and v[3]:
        return "?"
    ink, mid, long = v[:3]
    if ink < CIRCLE_MARK[0] and mid < 0.15:
        return "."
    if ink < CIRCLE_MARK[1] and mid < 0.3:
        return "?"
    if mid >= CIRCLE_FILLED and long < 1.4:
        return "M"
    if long >= CIRCLE_SLASH and mid < 0.95:
        return "X"
    return "?"


def measure(pg):
    """The ink in every box of one page."""
    g, out = pg.geo, {"rows": {}, "running": {}, "boxes": {}}
    for side in ("home", "away"):
        rows = []
        for r in g[side]["rows"]:
            m = {"num": pg.ink_in(r["num"], -1.5), "name": pg.ink_in(r["name"], -1.5),
                 "ft": [both_circle(pg, c) for c in r["ft"]]}
            if "here" in r:
                hx, hy, hw, hh = r["here"]
                m["here"] = both(pg, [hx - 3, r["row"][1] + 1, hw + 6, r["row"][3] - 2], HERE_TICK)
                m["fouls"] = [both(pg, b, FOUL, -0.6, faint=True) for b in r["fouls"]]
                m["tech"] = [both(pg, b, SLASH, -0.6) for b in r["tech"]]
            rows.append(m)
        out["rows"][side] = rows
    # Most foul and T boxes on a sheet are empty, so the middle reading of each
    # kind is this print's own background (a dark grey or black print of the
    # outlines and the T leaves some); take it off every box of that kind.
    for kind in ("fouls", "tech"):
        vals = [v for side in ("home", "away") for r in out["rows"][side] for v in r.get(kind, [])]
        if vals:
            base = float(np.median(vals))
            out.setdefault("background", {})[kind] = round(base, 3)
            for side in ("home", "away"):
                for r in out["rows"][side]:
                    if kind in r:
                        r[kind] = [round(max(0.0, v - base), 3) for v in r[kind]]
        if "score" in g[side]:
            out["boxes"][side] = {k: [pg.ink_in([x + i * 10.4, y, 9.2, h], -1.0) for i in range(round((w + 1.2) / 10.4))]
                                  for k, (x, y, w, h) in g[side]["score"].items()}
    # The end-of-quarter lines: ink under a box deeper than under the other
    # boxes of its column (printed rules look different in every photo, so
    # each column is its own yardstick; the last row has the column's frame).
    cols = g["running_columns"]
    bands, groups = {}, {}
    for total, cells in g["running"].items():
        for side in ("home", "away"):
            box = cells[side]
            col = next(i for i, (x, y, w, h) in enumerate(cols) if x <= box[0] < x + w)
            last = abs(box[1] + box[3] - (cols[col][1] + cols[col][3])) < 1
            bands[(total, side)] = (pg.band(box), ("last", 0) if last else ("col", col))
            groups.setdefault(bands[(total, side)][1], []).append(float(np.median(bands[(total, side)][0])))
    base = {k: float(np.median(v)) for k, v in groups.items()}
    inks = {(total, side): pg.ink_in(cells[side], -1.0, faint=True)
            for total, cells in g["running"].items() for side in ("home", "away")}
    # Most running-score boxes are empty, so the middle reading is this photo's
    # noise (blur, grain, shadow); a box needs well above it to count as written.
    noise = float(np.median(list(inks.values())))
    out["run_written"] = [round(max(RUN_WRITTEN[0], 1.3 * noise), 3), round(max(RUN_WRITTEN[1], 2.6 * noise), 3)]
    for total, cells in g["running"].items():
        for side in ("home", "away"):
            v = inks[(total, side)]
            depth, grp = bands[(total, side)]
            ln = round(float((depth >= base[grp] + 3).mean()), 3) if depth.size else 0.0
            if v >= out["run_written"][0] / 2 or ln >= LINE[0] / 2:
                out["running"].setdefault(side, {})[int(total)] = {"ink": v, "line": ln}
    if "notes" in g:
        x, y, w, h = g["notes"]
        out["notes"] = [pg.ink_in([x + 6, y + 12 + k * 13, w - 12, 13]) for k in range(int((h - 14) // 13))]
    out["header"] = {k: pg.ink_in(b, -1.0) for k, b in g["header"].items()}
    return out


def make_crops(pg, folder, tag):
    """One image per section, sized to read from."""
    g, made = pg.geo, []
    folder.mkdir(parents=True, exist_ok=True)

    def save(name, box):
        made.append(pg.crop(box, folder / f"{tag}-{name}.png").name)

    hb = g["header"]
    xs = [b[0] for b in hb.values()] + [b[0] + b[2] for b in hb.values()]
    ys = [b[1] for b in hb.values()] + [b[1] + b[3] for b in hb.values()]
    save("header", [min(xs) - 4, min(ys) - 12, max(xs) - min(xs) + 8, max(ys) - min(ys) + 14])
    for side in ("home", "away"):
        rows = g[side]["rows"]
        x, y, w, _ = g[side]["bar"]
        save(f"{side}-roster", [x, y, w, rows[-1]["row"][1] + rows[-1]["row"][3] - y])
        half = len(rows) // 2
        for a, b in ((0, half), (half, len(rows))):
            top, bot = rows[a]["row"], rows[b - 1]["row"]
            save(f"{side}-rows-{a + 1:02d}-{b:02d}", [x, top[1], w, bot[1] + bot[3] - top[1]])
        if "score_strip" in g[side]:
            sx, sy, sw, sh = g[side]["score_strip"]
            save(f"{side}-score", [sx, sy - 17, sw, sh + 17])
    if "notes" in g:
        save("notes", g["notes"])
    run = {int(k): v for k, v in g["running"].items()}
    for col in g["running_columns"]:
        x, y, w, h = col
        totals = sorted(t for t, c in run.items() if x <= c["home"][0] < x + w)
        per = 13 if len(totals) > 20 else 10
        for i in range(0, len(totals), per):
            chunk = totals[i:i + per]
            a, b = run[chunk[0]]["home"], run[chunk[-1]]["home"]
            save(f"running-{chunk[0]:03d}-{chunk[-1]:03d}", [x, a[1] - 3, w, b[1] + b[3] - a[1] + 6])
    return made


# ---------------------------------------------------------------- prepare
def prepare(a):
    out = Path(a.out)
    (out / "crops").mkdir(parents=True, exist_ok=True)
    sdir = season_dir(a.season) if a.season or not a.game else find_season(a.game)
    if sdir is None:
        sys.exit(f"{a.game} isn't on any season's schedule (data/*/schedule.csv)")
    teams, players, schedule, season_problems = load_season(sdir)
    games = printed_games(sdir)
    for g in games:
        row = schedule.get(g["game_id"], {})
        g["_home"], g["_away"] = row.get("home"), row.get("away")
    layouts = [a.layout] if a.layout else LAYOUTS
    pages, report = {}, []
    for photo_path in a.photos:
        photo = ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB")
        corners = find_corners(photo)
        score, layout, page, turn = identify_page(photo, corners, layouts)
        layouts = [layout]                     # page 2 is on the same paper
        rgb = warp(photo, corners, layout, turn, PX)
        pc = page_corners(layout)
        span = sum(math.dist(corners[i], corners[(i + 1) % 4]) for i in range(4))
        dpi = 72 * span / sum(math.dist(pc[i], pc[(i + 1) % 4]) for i in range(4))
        pages[page] = {"photo": str(photo_path), "rgb": rgb, "layout": layout, "match": round(score, 3), "dpi": round(dpi),
                       "turn": turn, "corners": [[round(x), round(y)] for x, y in corners]}
    if 1 not in pages:
        sys.exit("none of the photos is page 1 of the score sheet")
    layout = pages[1]["layout"]
    flat1, _ = flatten(pages[1]["rgb"].convert("L"))
    ranked = identify_game(flat1, layout, 1, games)
    gid = a.game or (ranked[0][1] if ranked else None)
    game = next((g for g in games if g["game_id"] == gid), None)
    if a.game and not game:
        sys.exit(f"{a.game} isn't a scheduled game in {sdir.relative_to(ROOT)}")
    printed = render(sheet_pdf(layout, [game] if game else [{}]), PX)
    marks = {"season": sdir.name, "layout": layout, "game": gid,
             "home": game["_home"] if game else None, "away": game["_away"] if game else None,
             "game_match": [{"game_id": g_, "score": round(s, 3)} for s, g_ in ranked[:3]], "pages": {}}
    crops = {}
    for page, info in sorted(pages.items()):
        pg = Page(info["rgb"], layout, page, printed[page - 1])
        pg.rgb.save(out / f"page{page}.jpg", quality=90)          # light evened out, for zoom
        m = measure(pg)
        m.update({k: info[k] for k in ("photo", "match", "turn", "corners", "dpi")})
        m["regions"] = [[name, [round(v, 2) for v in rect], list(shift)] for name, rect, shift in pg.regions]
        marks["pages"][page] = m
        crops[page] = make_crops(pg, out / "crops", f"p{page}")
    (out / "marks.json").write_text(json.dumps(marks, indent=1) + "\n", encoding="utf-8")
    draft, review = start_draft(marks, game, teams, players)
    (out / "start.yml").write_text(sheet_rules.dump(draft), encoding="utf-8")
    (out / "report.md").write_text(write_report(marks, game, teams, players, draft, crops, season_problems), encoding="utf-8")
    print(f"{out / 'report.md'}")
    print(f"layout {layout}, pages {sorted(pages)}; game {gid}"
          + (f" (match {ranked[0][0]:.2f}; next {ranked[1][1]} {ranked[1][0]:.2f})" if len(ranked) > 1 and not a.game else ""))


LOOK_ALIKE = [set(p) for p in ("17", "38", "49", "56", "06", "08", "68", "27", "35", "14", "23", "59")]


def look_alikes(nums):
    """Pairs of numbers on one roster that handwriting can turn into each other:
    one digit apart by a look-alike pair (46/48, 3/8), or a digit doubled (3/33)."""
    out = []
    nums = sorted({str(n) for n in nums if str(n).isdigit()}, key=lambda n: (len(n), int(n)))
    for i, a in enumerate(nums):
        for b in nums[i + 1:]:
            if len(a) == len(b):
                diff = [(x, y) for x, y in zip(a, b) if x != y]
                if len(diff) == 1 and {diff[0][0], diff[0][1]} in LOOK_ALIKE:
                    out.append((a, b))
            elif len(a) == 1 and b == a * 2:
                out.append((a, b))
    return out


def jersey(n):
    """A jersey number as a game file holds it: 23, or "00" kept as text."""
    n = str(n)
    return int(n) if n.isdigit() and (n == "0" or not n.startswith("0")) else n


def runs(marks_list):
    """A row of marks ('M', 'X', '?', '.') as a free-throw string; where a gap or doubt is."""
    s = "".join(marks_list).rstrip(".")
    return s


def start_draft(marks, game, teams, players):
    """A draft from the ink: everything the ink says for sure, '?' where only
    the handwriting can say (or the ink isn't sure), and a review item each."""
    p1, p2 = marks["pages"][1], marks["pages"].get(2)
    review = []
    if game:
        home, away = game["_home"], game["_away"]
    else:
        home, away = "?", "?"
    sides = {"home": home, "away": away}
    draft = {"game_id": marks["game"] or "?", "form": sheet_rules.FORM, "status": "draft", "home": home,
             "away": away, "scorekeeper": "?", "teams": {}, "running": {}, "lines": {}, "boxes": {}}
    for side, tid in sides.items():
        rows_out = []
        prows = printed_ids(game, tid, players) if game else []
        for r, m in enumerate(p1["rows"][side]):
            at = f"teams.{tid}.players.{r}"
            pr = prows[r] if r < len(prows) else None
            ft_marks = [circle_mark(v) for v in m["ft"]]
            if p2:
                ft_marks += [circle_mark(v) for v in p2["rows"][side][r]["ft"]]
            here = level(m["here"], HERE_TICK)
            fouls = [level(v, FOUL) for v in m["fouls"]]
            tech = [level(v, SLASH) for v in m["tech"]]
            written = level(max(m["num"], m["name"]), CORRECTION if pr else WRITTEN)
            used = here != "no" or any(x != "." for x in ft_marks) or "yes" in fouls + tech
            if not pr and not used and written == "no":
                continue                                   # an empty row
            row = {}
            if pr and pr["player"]:
                row["player"] = pr["player"]
                row["num"] = jersey(pr["num"])
                if written != "no":
                    review.append({"at": f"{at}.num", "note": "pen in the number or name box of a printed row: "
                                   "a correction? Read it"})
            else:
                row["name"] = "?"
                row["num"] = "?"
                review.append({"at": at, "note": "a row written in by hand: read the number and name, "
                               "then give the player id (players.yml) or keep name: First L."})
            row["here"] = here != "no"
            if here == "unsure":
                review.append({"at": f"{at}.here", "note": f"faint mark in Here (ink {m['here']}): ticked or not?"})
            s = runs(ft_marks)
            if "." in s:
                review.append({"at": f"{at}.ft.{s.index('.')}", "note": "an empty circle before a marked one: "
                               "check the circles in order"})
            for i, ch in enumerate(s):
                if ch == "?":
                    page_ft = m["ft"] if i < len(m["ft"]) else p2["rows"][side][r]["ft"]
                    v = page_ft[i % len(m["ft"])]
                    review.append({"at": f"{at}.ft.{i}", "note": f"circle {i + 1}: can't tell from the ink "
                                   f"(ink {v[0]}, middle {v[1]}, shape {v[2]}): filled (M), slashed (X) or empty?"})
            if s:
                row["ft"] = s.replace(".", "?")
            nf = sum(1 for x in fouls if x != "no")
            if nf:
                row["fouls"] = nf
            if "unsure" in fouls or (nf and fouls[:nf].count("no")):
                review.append({"at": f"{at}.fouls", "note": "foul boxes: " + " ".join(
                    f"{i + 1}:{v}" for i, v in enumerate(m["fouls"])) + " (ink); count the slashes"})
            nt = sum(1 for x in tech if x != "no")
            if nt:
                row["tech"] = nt
            if "unsure" in tech:
                review.append({"at": f"{at}.tech", "note": f"T boxes ink {m['tech']}: slashed or not?"})
            rows_out.append(row)
        draft["teams"][tid] = {"players": rows_out}
        run = {}
        lines = []
        for page in (p1, p2):
            if not page:
                continue
            for total, cell in sorted(page["running"].get(side, {}).items(), key=lambda kv: int(kv[0])):
                total = int(total)
                w = level(cell["ink"], page.get("run_written", RUN_WRITTEN))
                if w != "no":
                    run[total] = "?"
                    if w == "unsure":
                        review.append({"at": f"running.{tid}.{total}", "note": f"faint (ink {cell['ink']}): "
                                       "a number, or a smudge?"})
                ln = level(cell["line"], LINE)
                if ln != "no":
                    lines.append(total)
                    if ln == "unsure":
                        review.append({"at": f"running.{tid}.{total}", "note": f"a line under {total}? "
                                       f"(ink across {cell['line']:.0%} of the width)"})
        draft["running"][tid] = dict(sorted(run.items()))
        draft["lines"][tid] = sorted(lines)
        draft["boxes"][tid] = {k: None for k in ("q1", "q2", "q3", "q4", "ot", "final")}
    if any(level(v, WRITTEN) != "no" for v in p1.get("notes", [])):
        review.append({"at": "notes", "note": "Notes has writing: read it (a flagrant foul is "
                       "{team, num, q, kind: flagrant, text})"})
    draft["review"] = review
    return draft, review


def write_report(marks, game, teams, players, draft, crops, season_problems):
    L = []
    gid = marks["game"]
    L.append(f"# Score sheet photo: {gid or 'game not found'}\n")
    L.append(f"Season `{marks['season']}`, layout **{marks['layout']}**, pages "
             f"{', '.join(str(p) for p in sorted(marks['pages']))}.")
    for p, m in sorted(marks["pages"].items()):
        L.append(f"- Page {p}: `{m['photo']}`, matched the blank sheet at {m['match']:.2f}"
                 + (" (low: check page*.jpg is the whole sheet, straight)" if m["match"] < 0.5 else "")
                 + f"; about {m.get('dpi', '?')} dpi"
                 + (" (soft: small or far away; read look-alikes with care, see below)" if m.get("dpi", 999) < SOFT_DPI else "")
                 + ".")
    if marks["game_match"]:
        gm = marks["game_match"]
        L.append(f"- Game by the printed header and rosters: " + ", ".join(
            f"{g['game_id']} ({g['score']:.2f})" for g in gm)
                 + (". **Close: read the Game ID box to be sure.**" if len(gm) > 1 and gm[0]["score"] - gm[1]["score"] < 0.08
                    else ". Confirm with the Game ID box."))
    if game:
        L.append(f"- {teams.get(game['_home'], {}).get('name', '?')} (home, `{game['_home']}`) vs "
                 f"{teams.get(game['_away'], {}).get('name', '?')} (away, `{game['_away']}`).")
    if season_problems:
        L.append(f"- Season data problems (fix separately): {len(season_problems)}")
    L.append("\nInk levels: 0 = clean, 1 = solid. They say *where* there's pen; read every\n"
             "number from the crops, and look at any box marked `?`.\n")
    L.append("## Crops\n")
    for p, files in sorted(crops.items()):
        L.append(f"Page {p}: " + ", ".join(f"`crops/{f}`" for f in files))
    for side in ("home", "away"):
        tid = draft[side]
        L.append(f"\n## {side.title()} roster (`{tid}`)\n")
        L.append("Rows count from 1 here; paths count from 0 (row 1 is `players.0`).\n")
        L.append("| Row | Printed | # / name ink | Here | Free throws (1-10 / 11-20) | Fouls | T |")
        L.append("|---|---|---|---|---|---|---|")
        p1 = marks["pages"][1]["rows"][side]
        p2 = marks["pages"].get(2, {}).get("rows", {}).get(side) if 2 in marks["pages"] else None
        pr = game[side]["players"] if game else []
        for r, m in enumerate(p1):
            printed = f"#{pr[r]['num']} {pr[r]['name']}" if r < len(pr) else ""
            ft = "".join(circle_mark(v) for v in m["ft"])
            if p2:
                ft += " / " + "".join(circle_mark(v) for v in p2[r]["ft"])
            fouls = sum(1 for v in m["fouls"] if level(v, FOUL) != "no")
            tech = sum(1 for v in m["tech"] if level(v, SLASH) != "no")
            here = {"yes": "✓", "no": "", "unsure": "?"}[level(m["here"], HERE_TICK)]
            written = max(m["num"], m["name"])
            if not printed and written < WRITTEN[0] and not here and set(ft) <= {".", " ", "/"}:
                continue
            L.append(f"| {r + 1} | {printed} | {written:.2f} | {here} ({m['here']:.2f}) | `{ft}` | {fouls} | {tech} |")
        nums = [str(r.get("num")) for r in draft["teams"][tid]["players"] if r.get("num") not in (None, "?")]
        L.append(f"\nJersey numbers on this roster (every running-score number must be one of them): "
                 + ", ".join(nums) + (" and the rows written in by hand" if any(r.get("num") == "?" for r in
                                                                               draft["teams"][tid]["players"]) else ""))
        pairs = look_alikes(nums)
        if pairs:
            L.append("Look-alike numbers on this roster (check each box read as one of these against the other): "
                     + ", ".join(f"{a}/{b}" for a, b in pairs))
        subs = sorted((p.get("number") or "", p["display"], pid) for pid, p in players.items()
                      if p.get("team") == tid and p.get("sub"))
        if subs:
            L.append("Subs for this team in players.yml (for a row written in by hand): "
                     + ", ".join(f"#{n} {d} (`{pid}`)" if n else f"{d} (`{pid}`)" for n, d, pid in subs))
        run = marks["pages"][1]["running"].get(side, {})
        if 2 in marks["pages"]:
            run = {**run, **marks["pages"][2]["running"].get(side, {})}
        thr = marks["pages"][1].get("run_written", RUN_WRITTEN)
        written = [int(t) for t, c in run.items() if level(c["ink"], thr) != "no"]
        L.append(f"\nRunning score boxes with writing ({len(written)}): " + ", ".join(map(str, sorted(written))))
        L.append(f"Lines under: {', '.join(map(str, draft['lines'][tid])) or 'none found'}")
        L.append(f"Score boxes: read them from `crops/p1-{side}-score.png`.")
    notes = marks["pages"][1].get("notes", [])
    L.append(f"\n## Notes\n\nLines with writing: "
             + (", ".join(str(i + 1) for i, v in enumerate(notes) if level(v, WRITTEN) != "no") or "none"))
    L.append(f"\n## Still to do\n\n`start.yml` has {len(draft['review'])} review items and a `?` for every "
             "number only the handwriting can give: the running-score numbers, the score boxes, the "
             "scorekeeper, any row written in by hand, and Notes.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- zoom
def box_for(marks, at):
    """(page, box in points) for a path such as running.lh.27, boxes.cr.q4,
    teams.lh.players.3 (or .ft.2, .here, .fouls, .tech), notes, header.game_id."""
    parts = at.split(".")
    side_of = {marks.get("home"): "home", marks.get("away"): "away", "home": "home", "away": "away"}
    layout = marks["layout"]
    if parts[0] == "running":
        total = int(parts[2])
        page = 1 if str(total) in page_geo(layout, 1)["running"] else 2
        c = page_geo(layout, page)["running"][str(total)]
        x, y, w, h = c["home"]              # the whole row, and the rows above and below
        ax, _, aw, _ = c["away"]
        return page, [x, y - h, ax + aw - x, 3 * h]
    if parts[0] == "boxes":
        g = page_geo(layout, 1)[side_of[parts[1]]]
        if len(parts) > 2 and parts[2] in g["score"]:
            x, y, w, h = g["score"][parts[2]]
            return 1, [x - 6, y - 10, w + 12, h + 13]            # the box and its label
        sx, sy, sw, sh = g["score_strip"]
        return 1, [sx, sy - 17, sw, sh + 17]
    if parts[0] == "teams":
        side, r = side_of[parts[1]], int(parts[3])
        page = 2 if len(parts) > 5 and parts[4] == "ft" and int(parts[5]) >= ss.FT_CIRCLES else 1
        row = page_geo(layout, page)[side]["rows"][r]
        part = parts[4] if len(parts) > 4 else None
        boxes = []
        if part == "ft":
            i = int(parts[5]) % ss.FT_CIRCLES if len(parts) > 5 else None
            boxes = row["ft"][max(0, i - 2):i + 3] if i is not None else row["ft"]
        elif part in ("fouls", "tech"):
            boxes = row["fouls"] + row["tech"]
        elif part == "here" and "here" in row:
            boxes = [row["here"]]
        elif part in ("num", "name", "player"):
            boxes = [row["num"], row["name"]]
        if boxes:
            x0, y0 = min(b[0] for b in boxes), row["row"][1]
            x1, y1 = max(b[0] + b[2] for b in boxes), row["row"][1] + row["row"][3]
            return page, [x0 - 4, y0 - 2, x1 - x0 + 8, y1 - y0 + 4]
        return page, row["row"]
    if parts[0] == "notes":
        return 1, page_geo(layout, 1)["notes"]
    if parts[0] == "header":
        return 1, page_geo(layout, 1)["header"][parts[1]]
    raise SystemExit(f"don't know where {at} is")


def zoom(a):
    folder = Path(a.folder)
    marks = json.loads((folder / "marks.json").read_text(encoding="utf-8"))
    for at in a.paths:
        page, (x, y, w, h) = box_for(marks, at)
        im = Image.open(folder / f"page{page}.jpg")
        pad = 3
        cx, cy = x + w / 2, y + h / 2          # line up with the photo, as the measures did
        inside = [(rw * rh, sh) for _, (rx, ry, rw, rh), sh in marks["pages"][str(page)].get("regions", [])
                  if rx <= cx <= rx + rw and ry <= cy <= ry + rh]
        dx, dy = min(inside)[1] if inside else (0, 0)
        box = [int((x - pad) * PX) + dx, int((y - pad) * PX) + dy, int((x + w + pad) * PX) + dx,
               int((y + h + pad) * PX) + dy]
        crop = im.crop(box)
        k = min(3.0, 1400 / max(crop.size))
        crop = crop.resize((round(crop.width * k), round(crop.height * k)), Image.Resampling.LANCZOS)
        out = folder / "crops" / f"zoom-{at}.png"
        crop.save(out)
        print(out)


# ---------------------------------------------------------------- save
def save(a):
    """Put the draft and the photo where they belong: data/<season>/drafts/<game_id>.yml
    and data/<season>/sheets/<game_id>.jpg (page 2: <game_id>-2.jpg)."""
    draft = yaml.safe_load(Path(a.draft).read_text(encoding="utf-8"))
    gid = str(draft.get("game_id"))
    sdir = season_dir(a.season) if a.season else find_season(gid)
    if sdir is None:
        sys.exit(f"{gid} isn't on any season's schedule")
    if sdir.name.startswith("sample-"):
        sys.exit(f"{gid} is in {sdir.name}, made-up data: a practice sheet. Not saved; score it with "
                 "scripts/record_game_eval.py score instead")
    final = sdir / "games" / f"{gid}.yml"
    if final.exists() and not a.force:
        sys.exit(f"{final.relative_to(ROOT)} already exists: this game is recorded. Stopping (--force to save the draft anyway)")
    dest = sdir / "drafts" / f"{gid}.yml"
    if dest.exists() and not a.force:
        sys.exit(f"{dest.relative_to(ROOT)} already exists (--force to replace it)")
    draft["status"] = "draft"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(sheet_rules.dump(draft), encoding="utf-8")
    print(dest.relative_to(ROOT))
    for i, photo in enumerate(a.photos):
        im = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")   # and no EXIF (no location) kept
        if max(im.size) > 3000:
            k = 3000 / max(im.size)
            im = im.resize((round(im.width * k), round(im.height * k)), Image.Resampling.LANCZOS)
        out = sdir / "sheets" / (f"{gid}.jpg" if i == 0 else f"{gid}-{i + 1}.jpg")
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, quality=85)
        print(out.relative_to(ROOT))


# ---------------------------------------------------------------- compare
def compare(a):
    """Two readings of the running score, box by box: every box where they differ."""
    one = yaml.safe_load(Path(a.draft).read_text(encoding="utf-8")) or {}
    two = yaml.safe_load(Path(a.second).read_text(encoding="utf-8")) or {}
    differ = 0
    for tid in sorted(set((one.get("running") or {})) | set((two.get("running") or {}))):
        r1 = {int(k): v for k, v in ((one.get("running") or {}).get(tid) or {}).items()}
        r2 = {int(k): v for k, v in ((two.get("running") or {}).get(tid) or {}).items()}
        for total in sorted(set(r1) | set(r2)):
            v1, v2 = r1.get(total), r2.get(total)
            if str(v1) != str(v2):
                differ += 1
                print(f"running.{tid}.{total}: {'-' if v1 is None else v1} / {'-' if v2 is None else v2}")
    print(f"{differ} box{'es' if differ != 1 else ''} differ" if differ else "The two readings agree.")
    return 0


# ---------------------------------------------------------------- check
def check_file(path, season=None):
    """The rules on one game file, with its season. Returns (game, problems, sheet)."""
    path = Path(path).resolve()
    sheet = yaml.safe_load(path.read_text(encoding="utf-8"))
    if season:
        sdir = season_dir(season)
    elif path.parent.name in ("games", "drafts") and (path.parent.parent / "schedule.csv").exists():
        sdir = path.parent.parent
    else:
        sdir = find_season(str((sheet or {}).get("game_id"))) or season_dir()
    teams, players, schedule, _ = load_season(sdir)
    stem = path.stem if path.parent.name in ("games", "drafts") else str((sheet or {}).get("game_id"))
    folder = path.parent.name if path.parent.name in ("games", "drafts") else (
        "games" if (sheet or {}).get("status") == "final" else "drafts")
    ctx = {"stem": stem, "folder": folder,
           "teams": teams, "players": players, "schedule": schedule}
    game, problems = sheet_rules.check(sheet, ctx)
    return game, problems, sheet, teams, players


def tally(sheet, players):
    """Points by jersey number from the running score (works on a draft with errors)."""
    out = {}
    for tid, run in (sheet.get("running") or {}).items():
        prev, pts = 0, {}
        for total in sorted(int(t) for t in run):
            num = run.get(total, run.get(str(total)))
            pts[str(num)] = pts.get(str(num), 0) + total - prev
            prev = total
        names = {}
        for r in ((sheet.get("teams") or {}).get(tid) or {}).get("players", []):
            p = players.get(r.get("player"), {})
            names[str(r.get("num"))] = p.get("display") or r.get("name") or "?"
        out[tid] = {"final": prev, "top": sorted(((v, k, names.get(k, "?")) for k, v in pts.items()), reverse=True)[:3]}
    return out


def check(a):
    game, problems, sheet, teams, players = check_file(a.file, a.season)
    left = [f"running.{tid}.{t}" for tid, run in (sheet.get("running") or {}).items() for t, v in run.items()
            if str(v).strip() == "?"]
    for at in left:
        print(f"{'error':8} {at:30} still \"?\": read it, or give your best guess and a review item")
    for p in problems:
        print(f"{p['level']:8} {p['at'] or '-':30} {p['message']}")
    warns = sum(1 for p in problems if p["level"] != "error")
    errors = len(problems) - warns + len(left)
    t = tally(sheet, players)
    parts = [f"{teams.get(tid, {}).get('name', tid)} {v['final']}" for tid, v in t.items()]
    print(f"\n{', '.join(parts)}. {errors} error{'s' if errors != 1 else ''}, {warns} warning{'s' if warns != 1 else ''}"
          f" ({len(sheet.get('review') or [])} review items).")
    for tid, v in t.items():
        print(f"  {teams.get(tid, {}).get('name', tid)}: " + ", ".join(f"#{n} {name} {pts}" for pts, n, name in v["top"]))
    return 1 if errors else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="straighten, crop and measure score sheet photos")
    p.add_argument("photos", nargs="+", help="page 1 (and page 2) of one game's score sheet")
    p.add_argument("--out", required=True, help="folder for the pages, crops, marks and start.yml")
    p.add_argument("--season", help="season folder id (default: the current season in data/seasons.yml)")
    p.add_argument("--game", help="the game id, if known (else found from the printed header and rosters)")
    p.add_argument("--layout", choices=LAYOUTS, help="the paper, if known (else found)")
    c = sub.add_parser("check", help="the rules on one game file (draft or final)")
    c.add_argument("file")
    c.add_argument("--season", help="season folder id (default: the one whose schedule has the game)")
    z = sub.add_parser("zoom", help="a close-up of boxes, by path (running.lh.27, teams.cr.players.3, boxes.lh.q4...)")
    z.add_argument("folder", help="the prepare --out folder")
    z.add_argument("paths", nargs="+")
    v = sub.add_parser("save", help="the draft into data/<season>/drafts/ and the photo into sheets/")
    v.add_argument("draft")
    v.add_argument("photos", nargs="+", help="page 1 (and page 2), as taken")
    v.add_argument("--season")
    v.add_argument("--force", action="store_true", help="replace a draft that's already there")
    d = sub.add_parser("compare", help="two readings of the running score: the boxes where they differ")
    d.add_argument("draft")
    d.add_argument("second")
    a = ap.parse_args(argv)
    return {"prepare": prepare, "check": check, "zoom": zoom, "save": save, "compare": compare}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
