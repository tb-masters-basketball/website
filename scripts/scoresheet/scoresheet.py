#!/usr/bin/env python3
"""Masters Basketball League score sheets (form MBL-SS5).

Makes printable, fillable PDF score sheets in four layouts:
portrait or landscape, Letter or Legal.

Each sheet has two rosters (jersey #, here tick, name, 10 free-throw circles,
5 personal fouls + 2 technicals) and a running score from 1 to 120, with a
continuation page (121-240, free throws 11-20) printed on the back: totals in
the middle, home scorer's number on the left, away scorer's on the right.

Usage
-----
Sheets for every game in the schedule (one PDF per game night):
  python scoresheet.py --data data/2026-27 --out dist/score-sheets

Only one night, or one game:
  python scoresheet.py --data data/2026-27 --date 2026-12-03 --out dist/score-sheets
  python scoresheet.py --data data/2026-27 --game 2026-12-03-g1 --out dist/score-sheets

Pick a layout (default portrait letter), or make all four:
  python scoresheet.py --data data/2026-27 --orient landscape --size legal --out ...
  python scoresheet.py --data data/2026-27 --all-layouts --out ...

Blank sheets (names and numbers left as fillable fields):
  python scoresheet.py --blank --all-layouts --out dist/score-sheets

Data it reads (see data/CLAUDE.md in the website repo):
  teams.yml     list of {id, name, ...}
  players.yml   list of {id, display, team, sub, number}   (number optional)
  schedule.csv  game_id,date,time,court,home,away,type,week[,status,...]
                (rows whose status is "cancelled" are skipped)
Regular players (sub: false) are pre-printed, sorted by jersey number; the
remaining rows are left blank for subs. Every field stays editable in the PDF.

Needs: reportlab, PyYAML (pypdf only for --check).
"""
import argparse, csv, datetime as dt, json, os, random, sys
from reportlab.lib.pagesizes import letter, legal
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
for _name, _file in [("Cond", "barlow-condensed-700"), ("CondSemi", "barlow-condensed-600"),
                     ("Body", "barlow-400"), ("BodySemi", "barlow-600")]:
    pdfmetrics.registerFont(TTFont(_name, os.path.join(ASSETS, "fonts", _file + ".ttf")))
BADGE = os.path.join(ASSETS, "masters-badge.png")

NAVY = HexColor("#0B1B3F")
BLUE = HexColor("#032F98")
RED = HexColor("#CB0E1D")
RULE = HexColor("#8C96AE")
TINT = HexColor("#E7ECF7")
SHADE = HexColor("#F1F3F9")
PEN = HexColor("#1F3FB8")      # example handwriting only

FORM = "MBL-SS5"
ROSTER_ROWS = 12
FT_CIRCLES = 10
MAX_POINTS = 120          # per page; the back page continues 121-240
PAD = 36
FID, FID_IN = 14, 16
SIZES = {"letter": letter, "legal": legal}


# --------------------------------------------------------------------------
class ScoreSheet:
    """One PDF; call add_page() once per game, then save()."""

    def __init__(self, path, size="letter", orient="portrait"):
        w, h = SIZES[size]
        if orient == "landscape":
            w, h = h, w
        self.W, self.H, self.size, self.orient = w, h, size, orient
        self.c = canvas.Canvas(path, pagesize=(w, h))
        self.c.setTitle("Masters Basketball League score sheet")
        self.c.setAuthor("Masters Basketball League")
        self.form = self.c.acroForm
        self.x0, self.cw = PAD, w - 2 * PAD
        self.pages = 0

    # ---- drawing helpers ------------------------------------------------
    def text(self, x, y, s, font="Body", size=8, color=NAVY, anchor="l", tracking=0):
        c = self.c
        c.setFillColor(color)
        w = pdfmetrics.stringWidth(s, font, size) + tracking * max(len(s) - 1, 0)
        if anchor == "c": x -= w / 2
        elif anchor == "r": x -= w
        t = c.beginText()
        t.setFont(font, size); t.setCharSpace(tracking); t.setTextOrigin(x, y)
        t.textOut(s); t.setCharSpace(0)
        c.drawText(t)
        return w

    def label(self, x, y, s, anchor="l", size=6.4, color=BLUE):
        return self.text(x, y, s.upper(), "CondSemi", size, color, anchor, tracking=0.6)

    def lwidth(self, s, size=6.4):
        return pdfmetrics.stringWidth(s.upper(), "CondSemi", size) + 0.6 * (len(s) - 1)

    def box(self, x, y, w, h, stroke=NAVY, lw=0.8, fill=None):
        c = self.c
        c.setLineWidth(lw); c.setStrokeColor(stroke)
        if fill is not None: c.setFillColor(fill)
        c.rect(x, y, w, h, stroke=1, fill=1 if fill is not None else 0)

    def circle(self, x, y, r, lw=0.75):
        c = self.c
        c.setStrokeColor(NAVY); c.setFillColor(white); c.setLineWidth(lw)
        c.circle(x, y, r, stroke=1, fill=1)

    def field(self, name, x, y, w, h, value="", size=9, maxlen=None):
        kw = dict(name=self.prefix + name, x=x, y=y, width=w, height=h, value=str(value or ""),
                  fontName="Helvetica", fontSize=size, borderWidth=0, fillColor=None,
                  borderColor=None, textColor=black, forceBorder=False,
                  tooltip=name.replace("_", " "))
        if maxlen: kw["maxlen"] = maxlen
        self.form.textfield(**kw)

    def digits(self, x, y, n, w=10.5, h=14, gap=1.5, lw=0.9):
        for i in range(n):
            self.box(x + i * (w + gap), y, w, h, lw=lw, fill=white)
        return n * w + (n - 1) * gap

    def wrap(self, s, width, font="Body", size=6.9):
        lines, cur = [], ""
        for word in s.split():
            t = (cur + " " + word).strip()
            if pdfmetrics.stringWidth(t, font, size) > width and cur:
                lines.append(cur); cur = word
            else:
                cur = t
        return lines + [cur] if cur else lines

    # ---- page parts --------------------------------------------------------
    def fiducials(self):
        self.c.setFillColor(black)
        for x in (FID_IN, self.W - FID_IN - FID):
            for y in (FID_IN, self.H - FID_IN - FID):
                self.c.rect(x, y, FID, FID, stroke=0, fill=1)

    def header(self, top, g, subtitle="SCORE SHEET  ·  THUNDER BAY"):
        c, x0, cw = self.c, self.x0, self.cw
        bh = 44
        if os.path.exists(BADGE):
            c.drawImage(BADGE, x0, top - bh, bh, bh, mask="auto")
        tx = x0 + bh + 9
        self.text(tx, top - 17, "MASTERS BASKETBALL LEAGUE", "Cond", 17.5, NAVY, tracking=0.4)
        c.setFillColor(RED); c.rect(tx, top - 25, 30, 2, stroke=0, fill=1)
        self.text(tx + 36, top - 26.3, subtitle, "CondSemi", 8.6, BLUE, tracking=0.9)
        self.text(tx, top - 39, f"Form {FORM} · {self.orient.title()} {self.size.title()}", "Body", 6.8, RULE)
        rows = [[("Date", "date", 80), ("Start time", "time", 56), ("Court", "court", 76)],
                [("Game ID", "game_id", 96), ("Scorekeeper", "scorekeeper", 122)]]
        right = x0 + cw
        for ri, row in enumerate(rows):
            y = top - 21 - ri * 24
            x = right - (sum(w for *_, w in row) + 6 * (len(row) - 1))
            for lab, key, w in row:
                self.label(x, y + 17, lab)
                self.box(x, y, w, 15, lw=0.8, fill=white)
                self.field(key, x + 2, y + 1, w - 4, 13, g.get(key, ""), size=8.5)
                x += w + 6
        return top - 50

    def roster(self, x, top, w, rh, side, key, team, back=False):
        """Team roster block. Returns (bottom_y, geometry for example marks).
        back=True: continuation roster (#, player, free throws 11-20 only)."""
        c = self.c
        ft_pitch = 9.2
        ft_w = FT_CIRCLES * ft_pitch + 4 + 8
        foul_w = 5 * 9 + 4 + 2 * 9 + 1.5 + 6
        if back:
            cols = [("#", 20), ("Player", w - 20 - ft_w - 8), ("Free throws 11-20", ft_w + 8)]
        else:
            cols = [("#", 20), ("Here", 18), ("Player", w - 20 - 18 - ft_w - foul_w),
                    ("Free throws", ft_w), ("Fouls  ·  T", foul_w)]
        xs = [x]
        for _, cwid in cols: xs.append(xs[-1] + cwid)
        # team bar
        bar = 20
        by = top - bar
        c.setFillColor(NAVY); c.rect(x, by, 48, bar, stroke=0, fill=1)
        self.text(x + 24, by + 6.5, side.upper(), "Cond", 11.5, white, anchor="c", tracking=1)
        self.box(x, by, w, bar, lw=1.2)
        self.label(x + 54, by + 7.4, "Team")
        self.box(x + 76, by + 3, w - 80, bar - 6, lw=0.6, fill=white)
        self.field(f"{key}_team", x + 78, by + 4, w - 84, bar - 8, team.get("name", ""), size=9.5)
        # column header
        hh = 15
        hy = by - hh
        self.box(x, hy, w, hh, lw=0.8, fill=TINT)
        for (name, cwid), cx in zip(cols, xs):
            self.label(cx + cwid / 2, hy + 4.8, name, anchor="c", size=6.6, color=NAVY)
        # player rows
        players = team.get("players", [])
        r_ft = min(3.8, rh / 2 - 2.6)
        bs = min(9, rh - 5)
        rows = []
        y = hy
        for r in range(ROSTER_ROWS):
            y -= rh
            self.box(x, y, w, rh, stroke=RULE, lw=0.5, fill=white)
            pl = players[r] if r < len(players) else {}
            fs = 9 if rh >= 16 else 8.5
            self.field(f"{key}_p{r+1:02d}_num", xs[0] + 2, y + 1.5, 16, rh - 3, pl.get("num", ""), size=fs, maxlen=3)
            if back:
                self.field(f"{key}_p{r+1:02d}_name", xs[1] + 3, y + 1.5, cols[1][1] - 6, rh - 3, pl.get("name", ""), size=fs)
                ft0 = xs[2] + 10
                for i in range(FT_CIRCLES):
                    self.circle(ft0 + r_ft + i * ft_pitch + (4 if i >= 5 else 0), y + rh / 2, r_ft)
                continue
            self.field(f"{key}_p{r+1:02d}_name", xs[2] + 3, y + 1.5, cols[2][1] - 6, rh - 3, pl.get("name", ""), size=fs)
            self.box(xs[1] + (18 - bs) / 2, y + (rh - bs) / 2, bs, bs, lw=0.8, fill=white)
            # free throws
            ft0 = xs[3] + 6
            centers = []
            for i in range(FT_CIRCLES):
                cx = ft0 + r_ft + i * ft_pitch + (4 if i >= 5 else 0)
                self.circle(cx, y + rh / 2, r_ft)
                centers.append(cx)
            # fouls 1-5 + T
            f0 = xs[4] + 3
            fboxes = []
            for i in range(5):
                bx = f0 + i * 9
                self.box(bx, y + (rh - bs) / 2, 8, bs, stroke=RULE, lw=0.6, fill=white)
                self.text(bx + 4, y + (rh - bs) / 2 + 2.3, str(i + 1), "Body", 4.4, RULE, anchor="c")
                fboxes.append(bx)
            techs = []
            for k in range(2):
                tx = f0 + 5 * 9 + 4 + k * 10.5
                self.box(tx, y + (rh - bs) / 2, 9, bs, stroke=RED, lw=0.9, fill=white)
                self.text(tx + 4.5, y + (rh - bs) / 2 + 2.2, "T", "CondSemi", 5.2, RED, anchor="c")
                techs.append(tx)
            rows.append(dict(y=y, xs=xs, ft=centers, r=r_ft, fouls=fboxes, tech=techs, bs=bs))
        # dividers
        c.setStrokeColor(RULE); c.setLineWidth(0.5)
        for cx in xs[1:-1]:
            c.line(cx, y, cx, hy + hh)
        if back:
            self.box(x, y, w, top - y, lw=1.2)
            return y, None
        # team fouls + timeouts
        ty = y - 17
        self.box(x, ty, w, 17, lw=0.8, fill=SHADE)
        self.label(x + 6, ty + 6, "Team fouls")
        bx = x + 52
        for half in ("1st", "2nd"):
            self.label(bx, ty + 6, half, color=NAVY)
            for i in range(5):
                self.box(bx + 13 + i * 9.5, ty + 4, 8, 9, lw=0.6, fill=white)
            bx += 13 + 5 * 9.5 + 8
        self.label(bx + 4, ty + 6, "Timeouts")
        for i in range(3):
            self.circle(bx + 46 + i * 10, ty + 8.5, 3.6, lw=0.7)
        # score by half
        sy = ty - 22
        self.box(x, sy, w, 22, lw=1.2, fill=white)
        self.label(x + 6, sy + 8, "Score")
        sx = x + 34
        score_boxes = []
        for lab, n in (("1st half", 2), ("2nd half", 2), ("OT", 2), ("Final", 3)):
            self.label(sx, sy + 8, lab, color=NAVY)
            lw_ = self.lwidth(lab) + 4
            dw = self.digits(sx + lw_, sy + 4, n, lw=1.4 if lab == "Final" else 0.9)
            score_boxes.append((sx + lw_, sy + 4, n))
            sx += lw_ + dw + 9
        self.box(x, sy, w, top - sy, lw=1.2)
        return sy, dict(rows=rows, score=score_boxes)

    FRONT_HELP = [
        "Running score: every time a team scores, write the scorer's number in that team's box beside "
        "the new total. Leave skipped totals empty. A jump of 1 is a free throw; 2 or 3 is a basket. "
        "And-one: write the basket, then the free throw.",
        "Player rows: fill a circle for each free throw made, slash one for each miss. Slash a foul box "
        "per personal foul; slash a T box per technical. Tick Here for everyone who plays. "
        "Halftime: draw a line under each team's last number. Past 120, or more than 10 free throws: "
        "carry on over the page.",
    ]
    BACK_HELP = [
        "Continuation. Use this side only if a team passes 120 points or a player takes more than 10 free "
        "throws. Keep marking exactly as on the front; the running score carries on from 121. "
        "Write the final score on the front.",
    ]

    def legend_lines(self, w, paras):
        lines = []
        for para in paras:
            lines += self.wrap(para, w - 16)
        return lines

    def legend_height(self, w, paras):
        return 14 + 8.6 * len(self.legend_lines(w, paras)) + 4

    def legend(self, x, top, w, paras):
        lines = self.legend_lines(w, paras)
        h = self.legend_height(w, paras)
        self.box(x, top - h, w, h, stroke=RULE, lw=0.6, fill=SHADE)
        self.label(x + 8, top - 10, "How to mark" if paras is self.FRONT_HELP else "Page 2", size=6.8)
        for i, s in enumerate(lines):
            self.text(x + 8, top - 19.5 - i * 8.6, s, "Body", 6.9, NAVY)
        return top - h

    def running(self, x, top, w, bottom, sets=4, start=1):
        c = self.c
        per = MAX_POINTS // sets
        gap = 8
        sw = (w - gap * (sets - 1)) / sets
        num_w = min(30, sw * 0.26)
        bw = (sw - num_w) / 2
        hh = 14
        rh = (top - hh - bottom) / per
        cells = {}
        fs = min(10, rh * 0.62)
        for s in range(sets):
            sx = x + s * (sw + gap)
            self.box(sx, top - hh, sw, hh, lw=0.8, fill=NAVY)
            for cx, t in ((sx + bw / 2, "Home #"), (sx + bw + num_w / 2, "Pts"), (sx + bw + num_w + bw / 2, "Away #")):
                self.label(cx, top - hh + 4.6, t, anchor="c", size=6.2, color=white)
            for r in range(per):
                n = start + s * per + r
                y = top - hh - (r + 1) * rh
                self.box(sx, y, bw, rh, stroke=RULE, lw=0.5, fill=white)
                self.box(sx + bw + num_w, y, bw, rh, stroke=RULE, lw=0.5, fill=white)
                self.box(sx + bw, y, num_w, rh, stroke=RULE, lw=0.5,
                         fill=TINT if (n - 1) // 10 % 2 == 0 else SHADE)
                self.text(sx + bw + num_w / 2, y + rh / 2 - fs * 0.35, str(n), "Cond", fs, NAVY, anchor="c")
                cells[n] = dict(home=(sx, y, bw, rh), away=(sx + bw + num_w, y, bw, rh))
            self.box(sx, top - hh - per * rh, sw, per * rh + hh, lw=1.1)
            c.setStrokeColor(NAVY); c.setLineWidth(1.0)
            for lx in (sx + bw, sx + bw + num_w):
                c.line(lx, top - hh - per * rh, lx, top - hh)
        return cells

    def footer(self, page_label=""):
        s = ("Masters Basketball League · Thunder Bay, Ontario  ·  Photograph the whole sheet, flat, "
             "with all four corner squares in view.")
        if page_label:
            s += "  ·  " + page_label
        self.text(self.W / 2, FID_IN + 3, s, "Body", 6.6, RULE, anchor="c")

    # ---- pages ------------------------------------------------------------------
    def score_sets(self):
        # portrait letter is the narrowest grid: 5 columns of 24; the rest 4 of 30
        return 5 if (self.orient, self.size) == ("portrait", "letter") else 4

    def add_page(self, game=None, example=False, back=True):
        """Front page for one game, plus the continuation page unless back=False."""
        g = game or {}
        self.pages += 1
        base = f"g{self.pages}_" if self.pages > 1 or getattr(self, "_multi", False) else ""
        self.prefix = base
        cells, geo = self._page(g, back=False)
        if example:
            self.example_marks(g, geo, cells)
        self.footer("Page 1 of 2" if back else "")
        self.c.showPage()
        if back:
            self.prefix = base + "b_"
            self._page(g, back=True)
            self.footer("Page 2 of 2")
            self.c.showPage()

    def _page(self, g, back):
        self.fiducials()
        sub = "SCORE SHEET  ·  PAGE 2  ·  CONTINUED" if back else "SCORE SHEET  ·  THUNDER BAY"
        top = self.header(self.H - PAD + 4, g, sub)
        bottom = FID_IN + FID + 4
        home, away = g.get("home", {}), g.get("away", {})
        helptext = self.BACK_HELP if back else self.FRONT_HELP
        start = MAX_POINTS + 1 if back else 1
        sets = self.score_sets()
        geo = {}
        fixed = 20 + 15 + (0 if back else 17 + 22)
        if self.orient == "portrait":
            gap = 14
            w = (self.cw - gap) / 2
            rh = 22 if self.size == "legal" else 17.5
            if back:
                rh = 18 if self.size == "legal" else 14
            y, geo["home"] = self.roster(self.x0, top - 6, w, rh, "Home", "home", home, back)
            _, geo["away"] = self.roster(self.x0 + w + gap, top - 6, w, rh, "Away", "away", away, back)
            y = self.legend(self.x0, y - 8, self.cw, helptext)
            cells = self.running(self.x0, y - 6, self.cw, bottom, sets, start)
        else:
            lw = 300 if self.size == "legal" else 284
            gap_v = 8
            avail = (top - 6) - bottom
            rh = (avail - gap_v - 2 * fixed) / (2 * ROSTER_ROWS)
            if back:
                rh = min(rh, 16)
            y, geo["home"] = self.roster(self.x0, top - 6, lw, rh, "Home", "home", home, back)
            _, geo["away"] = self.roster(self.x0, y - gap_v, lw, rh, "Away", "away", away, back)
            rx = self.x0 + lw + 14
            rw = self.cw - lw - 14
            legend_h = self.legend_height(rw, helptext)
            self.legend(rx, bottom + legend_h, rw, helptext)
            cells = self.running(rx, top - 6, rw, bottom + legend_h + 6, sets, start)
        return cells, geo

    def save(self):
        self.c.save()

    # ---- example handwriting (for previews only) --------------------------
    def example_marks(self, g, geo, cells):
        c = self.c
        rnd = random.Random(11)
        nums = {k: [p["num"] for p in g[k]["players"] if p.get("num")] for k in ("home", "away")}
        here = {"home": nums["home"][:9], "away": nums["away"][:8]}
        wts = {"home": [9, 6, 8, 3, 4, 2, 2, 3, 1], "away": [8, 5, 3, 6, 3, 2, 3, 1]}
        score = {"home": 0, "away": 0}
        events, ftseq, fouls, tech, half = [], {"home": {}, "away": {}}, {"home": {}, "away": {}}, ("away", None), None
        for i in range(80):
            t = "home" if rnd.random() < 0.53 else "away"
            n = rnd.choices(here[t], wts[t][:len(here[t])])[0]
            r = rnd.random()
            opp = "away" if t == "home" else "home"
            if r < 0.16:
                for _ in range(2):
                    made = rnd.random() < 0.7
                    ftseq[t].setdefault(n, []).append(made)
                    if made:
                        score[t] += 1; events.append((t, n, score[t]))
                f = rnd.choice(here[opp]); fouls[opp][f] = min(5, fouls[opp].get(f, 0) + 1)
            else:
                score[t] += 3 if r > 0.88 else 2; events.append((t, n, score[t]))
            if i == 34: half = dict(score)
            if max(score.values()) >= 62: break
        tech = ("away", here["away"][3])

        def pen(x, y, s, size):
            self.text(x, y, s, "CondSemi", size, PEN, anchor="c")

        for t, n, total in events:
            bx, by, bw, rh = cells[total][t]
            pen(bx + bw / 2, by + rh / 2 - min(10.5, rh * 0.62) * 0.36, n, min(10.5, rh * 0.62))
        for t in ("home", "away"):
            bx, by, bw, rh = cells[half[t]][t]
            c.setStrokeColor(PEN); c.setLineWidth(1.4); c.line(bx + 2, by + 0.8, bx + bw - 2, by + 0.8)
        for t in ("home", "away"):
            for r, pl in enumerate(g[t]["players"]):
                if pl.get("num") not in here[t]: continue
                row = geo[t]["rows"][r]
                y, rh = row["y"], (geo[t]["rows"][0]["y"] - geo[t]["rows"][1]["y"])
                cx, cy = row["xs"][1] + 9, y + rh / 2
                c.setStrokeColor(PEN); c.setLineWidth(1.3)
                p = c.beginPath(); p.moveTo(cx - 3.2, cy); p.lineTo(cx - 0.8, cy - 3); p.lineTo(cx + 4, cy + 4)
                c.drawPath(p, stroke=1, fill=0)
                for i, made in enumerate(ftseq[t].get(pl["num"], [])[:FT_CIRCLES]):
                    fx, rr = row["ft"][i], row["r"]
                    c.setFillColor(PEN); c.setStrokeColor(PEN)
                    if made: c.circle(fx, cy, rr - 0.7, stroke=0, fill=1)
                    else: c.setLineWidth(1.3); c.line(fx - rr, cy - rr, fx + rr, cy + rr)
                bs = row["bs"]
                for i in range(fouls[t].get(pl["num"], 0)):
                    bx = row["fouls"][i]
                    c.setStrokeColor(PEN); c.setLineWidth(1.1)
                    c.line(bx + 1.5, y + (rh - bs) / 2 + 1.5, bx + 6.5, y + (rh + bs) / 2 - 1.5)
                if tech == (t, pl["num"]):
                    tx = row["tech"][0]
                    c.setStrokeColor(PEN); c.setLineWidth(1.1)
                    c.line(tx + 1.5, y + (rh - bs) / 2 + 1.5, tx + 7.5, y + (rh + bs) / 2 - 1.5)
            final = score[t]
            for (bx, by, n), v in zip(geo[t]["score"], [half[t], final - half[t], None, final]):
                if v is None: continue
                for j, ch in enumerate(str(v).rjust(n)):
                    if ch != " ": pen(bx + j * 12 + 5.25, by + 3.6, ch, 10)


# --------------------------------------------------------------------------
# Data loading
def load_yaml(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def as_list(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        return [dict(id=k, **v) for k, v in obj.items()]
    return obj or []


def nice_date(iso):
    d = dt.date.fromisoformat(str(iso))
    return d.strftime("%a %b ") + str(d.day)


def nice_time(t):
    t = str(t or "").strip()
    try:
        h, m = t.split(":")[:2]
        h, m = int(h), int(m[:2])
        if "pm" in t.lower() and h < 12: h += 12
        return dt.time(h, m).strftime("%I:%M %p").lstrip("0")
    except Exception:
        return t


def load_games(data_dir, include_subs=False):
    teams = {t["id"]: t for t in as_list(load_yaml(os.path.join(data_dir, "teams.yml")), "teams")}
    players = as_list(load_yaml(os.path.join(data_dir, "players.yml")), "players")
    roster = {tid: [] for tid in teams}
    for p in players:
        if p.get("sub") and not include_subs:
            continue
        num = p.get("number")
        roster.setdefault(p["team"], []).append(   # 0 is a real jersey number, so test for None
            {"num": "" if num is None else str(num).strip(), "name": p.get("display", "")})
    for tid in roster:
        roster[tid].sort(key=lambda p: (not p["num"].isdigit(), int(p["num"]) if p["num"].isdigit() else 0, p["name"]))
        if len(roster[tid]) > ROSTER_ROWS:
            print(f"warning: {tid} has {len(roster[tid])} players; only {ROSTER_ROWS} fit", file=sys.stderr)
            roster[tid] = roster[tid][:ROSTER_ROWS]
    games = []
    with open(os.path.join(data_dir, "schedule.csv")) as f:
        for row in csv.DictReader(f):
            h, a = row["home"].strip(), row["away"].strip()
            if h not in teams or a not in teams:
                continue  # bye rows or TBD playoff slots
            if (row.get("status") or "").strip().lower() == "cancelled":
                continue  # a cancelled game needs no sheet
            games.append({
                "game_id": row["game_id"].strip(),
                "iso_date": row["date"].strip(),
                "date": nice_date(row["date"].strip()),
                "time": nice_time(row.get("time")),
                "court": (row.get("court") or "").strip(),
                "home": {"name": teams[h]["name"], "players": roster.get(h, [])},
                "away": {"name": teams[a]["name"], "players": roster.get(a, [])},
            })
    return games


# --------------------------------------------------------------------------
def build(path, games, size, orient, example=False, back=True):
    s = ScoreSheet(path, size, orient)
    s._multi = len(games) > 1
    for g in games:
        s.add_page(g, example=example, back=back)
    s.save()


def main():
    ap = argparse.ArgumentParser(description="Make Masters Basketball League score sheets.")
    ap.add_argument("--data", help="season folder, e.g. data/2026-27")
    ap.add_argument("--date", help="only games on this date (YYYY-MM-DD)")
    ap.add_argument("--game", help="only this game_id")
    ap.add_argument("--from-today", action="store_true", help="skip games before today")
    ap.add_argument("--prefill", help="one game as JSON instead of --data")
    ap.add_argument("--blank", action="store_true", help="blank fillable sheet")
    ap.add_argument("--size", choices=SIZES, default="letter")
    ap.add_argument("--orient", choices=["portrait", "landscape"], default="portrait")
    ap.add_argument("--all-layouts", action="store_true", help="make all four layouts")
    ap.add_argument("--per-game", action="store_true", help="one PDF per game instead of per night")
    ap.add_argument("--include-subs", action="store_true", help="also pre-print subs")
    ap.add_argument("--example", action="store_true", help="add sample handwriting (previews only)")
    ap.add_argument("--front-only", action="store_true", help="leave out the continuation page")
    ap.add_argument("--allow-empty", action="store_true",
                    help="no matching games is fine (e.g. --from-today after the last game night): make nothing, exit 0")
    ap.add_argument("--out", required=True, help="output folder")
    a = ap.parse_args()

    layouts = ([(o, s) for o in ("portrait", "landscape") for s in ("letter", "legal")]
               if a.all_layouts else [(a.orient, a.size)])
    os.makedirs(a.out, exist_ok=True)
    made = []

    if a.blank or a.prefill:
        g = json.load(open(a.prefill)) if a.prefill else {}
        stem = "example" if a.example else ("game" if a.prefill else "blank")
        for o, s in layouts:
            p = os.path.join(a.out, f"score-sheet-{stem}-{o}-{s}.pdf")
            build(p, [g], s, o, example=a.example, back=not a.front_only); made.append(p)
    else:
        if not a.data:
            ap.error("give --data, --prefill or --blank")
        games = load_games(a.data, a.include_subs)
        if a.game: games = [g for g in games if g["game_id"] == a.game]
        if a.date: games = [g for g in games if g["iso_date"] == a.date]
        if a.from_today:
            today = dt.date.today().isoformat()
            games = [g for g in games if g["iso_date"] >= today]
        if not games:
            if a.allow_empty:
                print("no games matched; nothing to make")
                return
            sys.exit("no games matched")
        groups = {}
        for g in games:
            key = g["game_id"] if a.per_game else g["iso_date"]
            groups.setdefault(key, []).append(g)
        for key, gs in sorted(groups.items()):
            for o, s in layouts:
                suffix = "" if not a.all_layouts and (o, s) == ("portrait", "letter") else f"-{o}-{s}"
                p = os.path.join(a.out, f"score-sheets-{key}{suffix}.pdf")
                build(p, gs, s, o, example=a.example, back=not a.front_only); made.append(p)
    for p in made:
        print(p)


if __name__ == "__main__":
    main()
