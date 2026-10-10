#!/usr/bin/env python3
"""Masters Basketball League score sheets (form MBL-SS6).

Makes printable, fillable PDF score sheets in four layouts:
portrait or landscape, Letter or Legal.

Page 1: two rosters (jersey #, here tick, name, 10 free-throw circles,
5 personal fouls + 2 technicals), timeouts, team fouls per quarter, the score
at the end of each quarter (Q1-Q4, OT) and the final, a Notes box for flagrant
fouls, and a running score from 1 to 100: totals in the middle, home scorer's
number on the left, away scorer's on the right.
Page 2, printed on the back: How to mark (the instructions), the running score
from 101 with one column fewer (to 180 or 175), and free throws 11-20.

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

# Everything structural about the printed sheet, in one place. The drawing code
# reads only this; `--spec OUT.json` writes it (plus each layout's running-score
# ranges) for the game file checks and the entry page. Change the printed sheet
# here, then bump "form" (and update /record-game and scripts/sheet_rules.py).
SPEC = {
    "form": "MBL-SS6",                 # SS6: quarters (was halves), Notes on page 1, how-to on page 2
    "roster_rows": 12,                 # player rows per team (same rows on both pages)
    "ft_circles_per_page": 10,         # free-throw circles per player row: 1-10 on page 1, 11-20 on page 2
    "personal_foul_boxes": 5,
    "technical_boxes": 2,
    "timeouts": 3,                     # circles beside each team name
    "quarters": ["Q1", "Q2", "Q3", "Q4"],
    "team_foul_boxes_per_quarter": 5,
    # The score boxes under each roster: the running total at the end of each
    # quarter, after overtime, and the final ("digits" = boxes printed).
    "score_boxes": [
        {"key": "q1", "label": "Q1", "digits": 2},
        {"key": "q2", "label": "Q2", "digits": 2},
        {"key": "q3", "label": "Q3", "digits": 2},
        {"key": "q4", "label": "Q4", "digits": 3},
        {"key": "ot", "label": "OT", "digits": 3},
        {"key": "final", "label": "Final", "digits": 3},
    ],
    "points_per_page": 100,            # page 1's running score: 1-100
    # Running-score columns on page 1, by layout; each column holds
    # points_per_page / columns totals. Page 2 continues from 101 with
    # page2_columns_fewer columns fewer, the same totals per column.
    "running_columns": {"portrait-letter": 5, "default": 4},
    "page2_columns_fewer": 1,
    "notes_box": True,                 # page 1: flagrant fouls and anything else
}
FORM = SPEC["form"]
ROSTER_ROWS = SPEC["roster_rows"]
FT_CIRCLES = SPEC["ft_circles_per_page"]
MAX_POINTS = SPEC["points_per_page"]
QUARTERS = tuple(SPEC["quarters"])
TEAM_FOUL_BOXES = SPEC["team_foul_boxes_per_quarter"]
PF_BOXES = SPEC["personal_foul_boxes"]
T_BOXES = SPEC["technical_boxes"]
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
        foul_w = PF_BOXES * 9 + 4 + T_BOXES * 9 + 1.5 + 6
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
        name_w = w - 80 if back else w - 80 - 76
        self.box(x + 76, by + 3, name_w, bar - 6, lw=0.6, fill=white)
        self.field(f"{key}_team", x + 78, by + 4, name_w - 4, bar - 8, team.get("name", ""), size=9.5)
        if not back:   # timeouts: one circle per timeout taken
            tx = x + 76 + name_w + 6
            self.label(tx, by + 7.4, "Timeouts")
            for i in range(SPEC["timeouts"]):
                self.circle(tx + self.lwidth("Timeouts") + 8 + i * 9.5, by + bar / 2, 3.4, lw=0.7)
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
            for i in range(PF_BOXES):
                bx = f0 + i * 9
                self.box(bx, y + (rh - bs) / 2, 8, bs, stroke=RULE, lw=0.6, fill=white)
                self.text(bx + 4, y + (rh - bs) / 2 + 2.3, str(i + 1), "Body", 4.4, RULE, anchor="c")
                fboxes.append(bx)
            techs = []
            for k in range(T_BOXES):
                tx = f0 + PF_BOXES * 9 + 4 + k * 10.5
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
        # team fouls, one row of boxes per quarter
        ty = y - 17
        self.box(x, ty, w, 17, lw=0.8, fill=SHADE)
        self.label(x + 6, ty + 6, "Team fouls")
        pitch = 7.9
        slot = (w - 52 - 4) / len(QUARTERS)
        team_fouls = {}
        for qi, q in enumerate(QUARTERS):
            bx = x + 52 + qi * slot
            self.label(bx, ty + 6, q, color=NAVY)
            team_fouls[q] = []
            for i in range(TEAM_FOUL_BOXES):
                fx = bx + 11 + i * pitch
                self.box(fx, ty + 4, 6.0, 9, lw=0.6, fill=white)
                team_fouls[q].append(fx)
        # the score at the end of each quarter (the running total), then OT and final
        sh = 27
        sy = ty - sh
        self.box(x, sy, w, sh, lw=1.2, fill=white)
        self.label(x + 6, sy + 15.5, "Score at")
        self.label(x + 6, sy + 7.5, "end of")
        cells_ = [(b["label"], b["digits"]) for b in SPEC["score_boxes"]]
        dw_, dgap = 9.2, 1.2
        widths = [n * dw_ + (n - 1) * dgap for _, n in cells_]
        sx = x + 40
        gap = (x + w - 6 - sx - sum(widths)) / (len(cells_) - 1)
        score_boxes = []
        for (lab, n), cwid in zip(cells_, widths):
            self.label(sx + cwid / 2, sy + 18.5, lab, anchor="c", color=NAVY if lab != "Final" else BLUE)
            self.digits(sx, sy + 3.5, n, w=dw_, h=13, gap=dgap, lw=1.4 if lab == "Final" else 0.9)
            score_boxes.append((sx, sy + 3.5, n, lab))
            sx += cwid + gap
        self.box(x, sy, w, top - sy, lw=1.2)
        return sy, dict(rows=rows, score=score_boxes, team_fouls=team_fouls, team_fouls_y=ty + 4)

    # How to mark: on page 2, in the space of its last running-score column.
    HOW_TO = [
        ("Running score", "Each time a team scores, write the scorer's number in that team's box "
         "beside the new total. Leave skipped totals empty. A jump of 1 is a free throw; 2 or 3 is a "
         "basket. And-one: write the basket, then the free throw."),
        ("End of each quarter", "Draw a line under each team's last number. Write each team's running "
         "total in its Q1, Q2, Q3 or Q4 box under the roster, the total after overtime in OT, and the "
         "final score in Final."),
        ("Players", "Tick Here for everyone who plays. Fill a circle for each free throw made; slash one "
         "for each miss. Slash a foul box for each personal foul and a T box for each technical."),
        ("Team fouls", "Slash one box in that quarter's row for each team foul."),
        ("Flagrant fouls", "A flagrant foul is also a personal foul: slash a foul box for it as usual. "
         "Then write it in Notes on page 1: the team, the player's number, the quarter and what happened."),
        ("This page", "Use it only if a team passes 100 points or a player takes more than 10 free "
         "throws. Keep marking exactly as on page 1: the running score carries on from 101. Write the "
         "final score on page 1."),
    ]
    NOTES_LABEL = "Notes  ·  flagrant fouls: team, player #, quarter, what happened"
    NOTES_H = 50

    def how_to(self, x, top, w, bottom):
        """The marking instructions, in the biggest type that fits the box."""
        h = top - bottom
        self.box(x, bottom, w, h, stroke=RULE, lw=0.6, fill=SHADE)
        inner = w - 16
        for size in (10.4, 10.0, 9.6, 9.2, 8.8, 8.4, 8.0, 7.6, 7.2, 6.8):
            lead = size * 1.24
            head_size = max(6.8, size * 0.8)
            paras = [(head, self.wrap(body, inner, size=size)) for head, body in self.HOW_TO]
            need = 22 + sum(lead * len(lines) + head_size + 5 + 6 for _, lines in paras)
            if need <= h:
                break
        self.label(x + 8, top - 13, "How to mark", size=7.6)
        y = top - 28
        for head, lines in paras:
            self.label(x + 8, y, head, size=head_size, color=NAVY)
            y -= head_size + 5
            for line in lines:
                self.text(x + 8, y, line, "Body", size, NAVY)
                y -= lead
            y -= 6

    def notes(self, x, top, w, h):
        """Page 1 notes box, for flagrant fouls (and anything else worth knowing)."""
        self.box(x, top - h, w, h, lw=0.9, fill=white)
        self.label(x + 8, top - 10, self.NOTES_LABEL, size=6.6)
        self.text(x + w - 8, top - 10, "How to mark: page 2", "Body", 6.4, RULE, anchor="r")
        self.c.setStrokeColor(RULE); self.c.setLineWidth(0.5)
        for ly in range(int(top - 26), int(top - h + 4), -13):
            self.c.line(x + 8, ly, x + w - 8, ly)
        return top - h

    def running(self, x, top, w, bottom, sets=4, start=1, per=None, col_w=None):
        """Running score: `sets` columns of `per` totals from `start`, each `col_w`
        wide (default: the full width shared out). Returns the cells by total."""
        c = self.c
        per = per or MAX_POINTS // sets
        gap = 8
        sw = col_w or (w - gap * (sets - 1)) / sets
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

    def back_running(self, x, top, w, bottom, sets):
        """Page 2: the running score carries on from 101 with one column fewer than
        page 1 (same totals per column), and How to mark fills the space left."""
        gap = 8
        per = MAX_POINTS // sets
        front_w = (w - gap * (sets - 1)) / sets
        col_w = front_w * 0.85
        cols = sets - SPEC["page2_columns_fewer"]
        used = cols * col_w + (cols - 1) * gap
        self.running(x, top, used, bottom, cols, MAX_POINTS + 1, per, col_w)
        self.how_to(x + used + 10, top, w - used - 10, bottom)
        self.back_last = MAX_POINTS + cols * per   # the last total on page 2
        return self.back_last

    def footer(self, page_label=""):
        s = ("Masters Basketball League · Thunder Bay, Ontario  ·  Photograph the whole sheet, flat, "
             "with all four corner squares in view.")
        if page_label:
            s += "  ·  " + page_label
        self.text(self.W / 2, FID_IN + 3, s, "Body", 6.6, RULE, anchor="c")

    # ---- pages ------------------------------------------------------------------
    def score_sets(self):
        # portrait letter is the narrowest grid: 5 columns of 20; the rest 4 of 25
        return running_columns(self.orient, self.size)

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
        sets = self.score_sets()
        geo, cells = {}, None
        fixed = 20 + 15 + (0 if back else 17 + 27)
        if self.orient == "portrait":
            gap = 14
            w = (self.cw - gap) / 2
            rh = 22 if self.size == "legal" else 17
            if back:
                rh = 18 if self.size == "legal" else 14
            y, geo["home"] = self.roster(self.x0, top - 6, w, rh, "Home", "home", home, back)
            _, geo["away"] = self.roster(self.x0 + w + gap, top - 6, w, rh, "Away", "away", away, back)
            if back:
                self.back_running(self.x0, y - 8, self.cw, bottom, sets)
            else:
                geo["notes"] = (self.x0, y - 8, self.cw, self.NOTES_H)
                y = self.notes(self.x0, y - 8, self.cw, self.NOTES_H)
                cells = self.running(self.x0, y - 6, self.cw, bottom, sets, 1)
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
            if back:
                self.back_running(rx, top - 6, rw, bottom, sets)
            else:
                geo["notes"] = (rx, bottom + self.NOTES_H, rw, self.NOTES_H)
                self.notes(rx, bottom + self.NOTES_H, rw, self.NOTES_H)
                cells = self.running(rx, top - 6, rw, bottom + self.NOTES_H + 6, sets, 1)
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
        events, ftseq, fouls, tech = [], {"home": {}, "away": {}}, {"home": {}, "away": {}}, ("away", None)
        ends, team_fouls, q = [], {"home": [0] * 4, "away": [0] * 4}, 0
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
                team_fouls[opp][q] = min(TEAM_FOUL_BOXES, team_fouls[opp][q] + 1)
            else:
                score[t] += 3 if r > 0.88 else 2; events.append((t, n, score[t]))
            if i in (17, 34, 51): ends.append(dict(score)); q += 1
            if max(score.values()) >= 62: break
        ends.append(dict(score))
        tech = ("away", here["away"][3])

        def pen(x, y, s, size):
            self.text(x, y, s, "CondSemi", size, PEN, anchor="c")

        for t, n, total in events:
            bx, by, bw, rh = cells[total][t]
            pen(bx + bw / 2, by + rh / 2 - min(10.5, rh * 0.62) * 0.36, n, min(10.5, rh * 0.62))
        for end in ends[:-1]:          # a line at the end of each quarter
            for t in ("home", "away"):
                if end[t] in cells:
                    bx, by, bw, rh = cells[end[t]][t]
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
            values = {q_: end[t] for q_, end in zip(QUARTERS, ends)}
            values["Final"] = score[t]
            for bx, by, n, lab in geo[t]["score"]:
                v = values.get(lab)
                if v is None: continue
                for j, ch in enumerate(str(v).rjust(n)):
                    if ch != " ": pen(bx + j * 10.4 + 4.6, by + 3.4, ch, 9.5)
            for qi, q_ in enumerate(QUARTERS):
                for fx in geo[t]["team_fouls"][q_][:team_fouls[t][qi]]:
                    c.setStrokeColor(PEN); c.setLineWidth(1.0)
                    c.line(fx + 1, geo[t]["team_fouls_y"] + 1.5, fx + 5, geo[t]["team_fouls_y"] + 7.5)
        nx, ntop, nw, nh = geo["notes"]
        self.text(nx + 10, ntop - 23, f"Away #{here['away'][1]} flagrant foul, Q3: swung elbow on a rebound",
                  "CondSemi", 9.5, PEN)


# --------------------------------------------------------------------------
# The spec as data
LAYOUTS = [(o, s) for o in ("portrait", "landscape") for s in ("letter", "legal")]


def running_columns(orient, size):
    cols = SPEC["running_columns"]
    return cols.get(f"{orient}-{size}", cols["default"])


def spec_json():
    """SPEC plus, for each layout, the running-score totals printed on each page."""
    out = dict(SPEC)
    layouts = {}
    for orient, size in LAYOUTS:
        cols = running_columns(orient, size)
        per = SPEC["points_per_page"] // cols
        back_cols = cols - SPEC["page2_columns_fewer"]
        layouts[f"{orient}-{size}"] = {
            "page1": {"first": 1, "last": SPEC["points_per_page"], "columns": cols, "per_column": per},
            "page2": {"first": SPEC["points_per_page"] + 1, "last": SPEC["points_per_page"] + back_cols * per,
                      "columns": back_cols, "per_column": per},
        }
    out["layouts"] = layouts
    # Totals any layout can hold; the game file checks use this as the limit.
    out["max_running_total"] = min(l["page2"]["last"] for l in layouts.values())
    out["ft_circles"] = SPEC["ft_circles_per_page"] * 2
    return out


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
    ap.add_argument("--out", help="output folder")
    ap.add_argument("--spec", metavar="OUT.json", help="write the sheet spec as JSON and stop")
    a = ap.parse_args()
    if a.spec:
        with open(a.spec, "w") as f:
            json.dump(spec_json(), f, indent=2)
            f.write("\n")
        print(a.spec)
        return
    if not a.out:
        ap.error("give --out (or --spec)")

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
