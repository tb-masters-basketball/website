#!/usr/bin/env python3
"""Testing /record-game on made-up photos, scored against answer keys.

    python scripts/record_game_eval.py photos [--out DIR] [--seed N]
    python scripts/record_game_eval.py score DRAFT.yml ANSWER.yml [--json]
    python scripts/record_game_eval.py summary RESULTS_DIR

photos: draws each practice game (tests/fixtures/record-game/<game_id>/answer.yml)
onto each of the five layouts with `scoresheet.py --fill`, renders page 1, and
"photographs" it: turned a few degrees, seen at an angle, on a table, with a
shadow, a little blur and noise, saved as a JPEG. 16 photos, the same every run
for a given --seed. They go in tests/fixtures/record-game/synthetic/ (not
committed) with photos.json listing each photo's game, layout and answer key.
--hard makes a tougher set in synthetic-hard/: untidy handwriting in several
pens and letter shapes, half-filled circles, and smaller, blurrier photos.

score: compares a /record-game draft with its answer key, section by section.
Every box is one of
    right        the draft has what the answer key has
    flagged      wrong (or "?"), but a review item points at it: a person will look
    wrong        wrong, and nothing points at it: the failure that matters
summary: adds up the score_*.json files in a folder (one per photo).
"""
import argparse
import io
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "scoresheet"))
import record_game as rg  # noqa: E402
import scoresheet as ss  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "record-game"
SEASON = ROOT / "data" / "sample-2026-27"


# ---------------------------------------------------------------- photos
def filled_page(answer, layout, scale, messy=False):
    """Page 1 of the game drawn onto the sheet, as an RGB image."""
    sheet = yaml.safe_load(answer.read_text(encoding="utf-8"))
    g, names = ss.game_from_file(str(SEASON), sheet)
    orient, size = layout.split("-")
    buf = io.BytesIO()
    ss.build(buf, [g], size, orient, back=False, fill=sheet, names=names, messy=messy)
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(buf.getvalue())
    doc.init_forms()
    return doc[0].render(scale=scale, may_draw_forms=True).to_pil().convert("RGB")


def photograph(page, rng, hard=False):
    """The page as a phone would see it. Returns (image, what was done)."""
    W, H = page.size
    # paper colour
    tint = np.array([rng.uniform(0.95, 1.0), rng.uniform(0.94, 0.99), rng.uniform(0.88, 0.97)])
    paper = Image.fromarray(np.clip(np.asarray(page, np.float32) * tint, 0, 255).astype(np.uint8))
    # where the page lands: centred, turned, its corners pulled about (perspective)
    angle = math.radians(rng.uniform(-7, 7))
    pull = rng.uniform(0.0, 0.05)
    dst = []
    for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
        x, y = x - W / 2, y - H / 2
        x, y = x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)
        dst.append((x + rng.uniform(-pull, pull) * W, y + rng.uniform(-pull, pull) * W))
    # the whole page in the frame, with some table round it
    margin = rng.uniform(0.03, 0.12) * W
    x0, y0 = min(x for x, _ in dst) - margin, min(y for _, y in dst) - margin
    dst = [(x - x0, y - y0) for x, y in dst]
    cw, ch = int(max(x for x, _ in dst) + margin), int(max(y for _, y in dst) + margin)
    coeffs = rg.homography(dst, [(0, 0), (W, 0), (W, H), (0, H)])
    warped = paper.transform((cw, ch), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)
    mask = Image.new("L", (W, H), 255).transform((cw, ch), Image.Transform.PERSPECTIVE, coeffs,
                                                 Image.Resampling.BILINEAR)
    table = np.ones((ch, cw, 3), np.float32) * np.array([rng.uniform(60, 150), rng.uniform(50, 120),
                                                         rng.uniform(40, 110)])
    table += np.random.default_rng(rng.randrange(1 << 30)).normal(0, 8, (ch, cw, 1))
    bg = Image.fromarray(np.clip(table, 0, 255).astype(np.uint8))
    bg.paste(warped, (0, 0), mask)
    img = np.asarray(bg, np.float32)
    # light: brighter on one side, and a soft shadow (a hand or a phone) across part of it
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    ga = rng.uniform(0, 2 * math.pi)
    grad = (np.cos(ga) * (xx / cw - 0.5) + np.sin(ga) * (yy / ch - 0.5))
    light = rng.uniform(0.8, 0.95) + rng.uniform(0.05, 0.25) * grad
    shadow = Image.new("L", (cw, ch), 0)
    d = ImageDraw.Draw(shadow)
    sx, sy = rng.uniform(0, cw), rng.uniform(0, ch)
    r = rng.uniform(0.25, 0.5) * max(cw, ch)
    d.ellipse([sx - r, sy - r * 0.6, sx + r, sy + r * 0.6], fill=255)
    shadow = np.asarray(shadow.filter(ImageFilter.GaussianBlur(max(cw, ch) * 0.06)), np.float32) / 255
    depth = rng.uniform(0.3, 0.6) if hard else rng.uniform(0.15, 0.45)
    img = img * (light * (1 - depth * shadow))[..., None]
    img = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    blur = rng.uniform(1.0, 2.2) if hard else rng.uniform(0.3, 1.6)
    img = img.filter(ImageFilter.GaussianBlur(blur))
    noise = rng.uniform(2, 6)
    arr = np.asarray(img, np.float32) + np.random.default_rng(rng.randrange(1 << 30)).normal(0, noise, (ch, cw, 1))
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    turn = rng.choice([0, 0, 0, 90, 270, 180])
    if turn:
        img = img.rotate(turn, expand=True)
    return img, {"angle": round(math.degrees(angle), 1), "perspective": round(pull, 3), "shadow": round(depth, 2),
                 "blur": round(blur, 2), "noise": round(noise, 1), "turned": turn}


def photos(a):
    out = Path(a.out or FIXTURES / ("synthetic-hard" if a.hard else "synthetic"))
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    made = []
    for folder in sorted(p for p in FIXTURES.iterdir() if (p / "answer.yml").exists()):
        for layout in rg.LAYOUTS:
            # 144-245 dpi of paper (a 2-4k phone photo); hard: 100-160 dpi, a far-off or cropped shot
            scale = rng.uniform(1.4, 2.2) if a.hard else rng.uniform(2.0, 3.4)
            page = filled_page(folder / "answer.yml", layout, scale, messy=a.hard)
            img, how = photograph(page, rng, hard=a.hard)
            quality = rng.randint(50, 75) if a.hard else rng.randint(65, 92)
            name = f"photo-{len(made) + 1:02d}.jpg"     # a name that doesn't give the game away
            img.save(out / name, quality=quality)
            how.update(photo=name, game_id=folder.name, layout=layout, answer=str((folder / "answer.yml").relative_to(ROOT)),
                       size=list(img.size), jpeg=quality, dpi=round(72 * scale))
            made.append(how)
            print(name, how)
    (out / "photos.json").write_text(json.dumps(made, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- scoring
SECTIONS = ["game", "players", "here", "free throws", "fouls", "tech", "running score", "lines", "score boxes",
            "notes", "scorekeeper"]


def flagged(review, path):
    """Is there a review item at this box (or the row or part it's in, or inside it)?"""
    for r in review:
        at = str(r.get("at", ""))
        if at == path or path.startswith(at + ".") or at.startswith(path + "."):
            return True
    return False


def score(draft, answer):
    review = draft.get("review") or []
    res = {s: {"right": 0, "flagged": 0, "wrong": 0} for s in SECTIONS}
    wrong = []

    def tick(section, path, ok, got=None, want=None):
        if ok:
            res[section]["right"] += 1
        elif flagged(review, path):
            res[section]["flagged"] += 1
        else:
            res[section]["wrong"] += 1
            wrong.append({"section": section, "at": path, "got": got, "want": want})

    tick("game", "game_id", draft.get("game_id") == answer["game_id"], draft.get("game_id"), answer["game_id"])
    tick("scorekeeper", "scorekeeper", str(draft.get("scorekeeper", "")).strip() == str(answer.get("scorekeeper", "")).strip(),
         draft.get("scorekeeper"), answer.get("scorekeeper"))
    for tid, t in answer["teams"].items():
        drows = ((draft.get("teams") or {}).get(tid) or {}).get("players") or []
        for i, want in enumerate(t["players"]):
            at = f"teams.{tid}.players.{i}"
            got = next((r for r in drows if want.get("player") and r.get("player") == want["player"]), None)
            if got is None:
                got = next((r for r in drows if str(r.get("num")) == str(want.get("num"))), None)
            if got is None:
                got = drows[i] if i < len(drows) else {}
            j = drows.index(got) if got in drows else i
            dat = f"teams.{tid}.players.{j}"
            ok = (got.get("player") == want.get("player") and str(got.get("num")) == str(want.get("num")))
            tick("players", dat, ok, f"{got.get('player') or got.get('name')} #{got.get('num')}",
                 f"{want.get('player')} #{want.get('num')}")
            tick("here", f"{dat}.here", bool(got.get("here")) == bool(want.get("here")), got.get("here"), want.get("here"))
            gft, wft = str(got.get("ft", "") or ""), str(want.get("ft", "") or "")
            for k in range(max(len(gft), len(wft))):
                g_, w_ = gft[k:k + 1], wft[k:k + 1]
                tick("free throws", f"{dat}.ft.{k}", g_ == w_, g_ or "-", w_ or "-")
            tick("fouls", f"{dat}.fouls", (got.get("fouls") or 0) == (want.get("fouls") or 0), got.get("fouls"),
                 want.get("fouls"))
            tick("tech", f"{dat}.tech", (got.get("tech") or 0) == (want.get("tech") or 0), got.get("tech"), want.get("tech"))
    for tid in answer["teams"]:
        want = {int(k): v for k, v in (answer.get("running") or {}).get(tid, {}).items()}
        got = {int(k): v for k, v in ((draft.get("running") or {}).get(tid) or {}).items()}
        for total in sorted(set(want) | set(got)):
            tick("running score", f"running.{tid}.{total}", str(got.get(total)) == str(want.get(total)),
                 got.get(total), want.get(total))
        wl, gl = (answer.get("lines") or {}).get(tid, []), ((draft.get("lines") or {}).get(tid) or [])
        for k in range(max(len(wl), len(gl))):
            tick("lines", f"lines.{tid}.{k}", k < len(wl) and k < len(gl) and wl[k] == gl[k],
                 gl[k] if k < len(gl) else None, wl[k] if k < len(wl) else None)
        wb, gb = (answer.get("boxes") or {}).get(tid, {}), ((draft.get("boxes") or {}).get(tid) or {})
        for k in ("q1", "q2", "q3", "q4", "ot", "final"):
            tick("score boxes", f"boxes.{tid}.{k}", gb.get(k) == wb.get(k), gb.get(k), wb.get(k))
    wn = [(n.get("team"), str(n.get("num")), str(n.get("q")), n.get("kind")) for n in answer.get("notes") or []]
    gn = [(n.get("team"), str(n.get("num")), str(n.get("q")), n.get("kind")) for n in draft.get("notes") or []]
    for k, n in enumerate(wn):
        tick("notes", f"notes.{k}", n in gn, None, n)
    for k, n in enumerate(gn):
        if n not in wn:
            tick("notes", f"notes.{k}", False, n, None)
    return res, wrong


def score_cmd(a):
    draft = yaml.safe_load(Path(a.draft).read_text(encoding="utf-8"))
    answer = yaml.safe_load(Path(a.answer).read_text(encoding="utf-8"))
    res, wrong = score(draft, answer)
    if a.json:
        Path(a.json).write_text(json.dumps({"draft": a.draft, "answer": a.answer, "sections": res, "wrong": wrong},
                                           indent=1) + "\n", encoding="utf-8")
    print_table({a.draft: res})
    for w in wrong:
        print(f"  WRONG {w['at']}: got {w['got']!r}, want {w['want']!r}")


def print_table(results):
    tot = {s: {"right": 0, "flagged": 0, "wrong": 0} for s in SECTIONS}
    for res in results.values():
        for s, v in res.items():
            for k in v:
                tot[s][k] += v[k]
    print(f"{'section':15} {'boxes':>6} {'right':>7} {'flagged':>8} {'wrong':>6}")
    for s, v in tot.items():
        n = sum(v.values())
        if not n:
            continue
        print(f"{s:15} {n:6} {v['right'] / n:7.1%} {v['flagged']:8} {v['wrong']:6}")
    return tot


def summary(a):
    results = {}
    for f in sorted(Path(a.folder).glob("score_*.json")):
        d = json.loads(f.read_text())
        results[f.name] = d["sections"]
    print(f"{len(results)} photos")
    print_table(results)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("photos")
    p.add_argument("--out", help="default: tests/fixtures/record-game/synthetic (or synthetic-hard)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--hard", action="store_true", help="untidy handwriting, half-filled circles, blurrier "
                   "and smaller photos")
    s = sub.add_parser("score")
    s.add_argument("draft")
    s.add_argument("answer")
    s.add_argument("--json", help="also write the result here")
    m = sub.add_parser("summary")
    m.add_argument("folder")
    a = ap.parse_args(argv)
    return {"photos": photos, "score": score_cmd, "summary": summary}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
