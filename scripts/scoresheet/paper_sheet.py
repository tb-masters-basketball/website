#!/usr/bin/env python3
"""The league's own paper score sheet (form MBL-PS1), in the league's look.

A second form alongside MBL-SS6 (scoresheet.py), not a change to it: the sheet
the league has always used (one row per player with the points scored in each
period written in P1-P4, a 1-5 foul count, team fouls, timeouts and a running
score), English only, with the running score carried on to 130 (101-130 is one
more line than the original's 1-100). Letter portrait, one page per game.

Everything structural is in SPEC (PDF points; origin top-left, y down). The
drawing code reads only SPEC; `--spec` writes it as JSON and `--geometry`
writes where every box is, for a reader later on (none exists yet).

Usage
-----
Sheets for every game in the schedule (one PDF per game day):
  python paper_sheet.py --data data/2026-27 --out dist/paper-sheets
Only one day, or one game, or from today on:
  python paper_sheet.py --data data/2026-27 --date 2026-10-31 --out ...
  python paper_sheet.py --data data/2026-27 --game 2026-10-31-g1 --out ...
  python paper_sheet.py --data data/2026-27 --from-today --out ...
(--allow-empty: no matching games is fine; the deploy uses it with --from-today.)
A blank sheet (every field empty but fillable):
  python paper_sheet.py --blank --out dist/paper-sheets
The structure, and every box's position:
  python paper_sheet.py --spec scripts/scoresheet/paper-spec.json
  python paper_sheet.py --geometry OUT.json

Pre-filled (each an editable PDF field): Game No. (the game of the day, from
the game id), Competition ("Masters"), Place (the game's gym, or the season's
from seasons.yml), Date, each team's name (visitor = schedule.csv away), and
each team's regular players as "First L." with their numbers, in number order;
the remaining rows are left blank for subs.

Needs: reportlab, PyYAML. Shares fonts, colours and the header with
scoresheet.py through branding.py.
"""
import argparse, csv, datetime as dt, io, json, os, random, sys
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from branding import NAVY, BLUE, RULE, TINT, draw_text, draw_header  # noqa: E402

FORM = "MBL-PS1"

SPEC = {
    "page": {"w": 612, "h": 792, "size": "letter", "orientation": "portrait"},
    # black corner squares for straightening a photo, as on MBL-SS6 (12 pt here,
    # so the bottom-right one clears the footer's last rule)
    "corners": {"size": 12, "inset": 16},
    "fonts": {"label": "CondSemi", "number": "Cond"},   # Barlow Condensed 600 / 700 (branding.py)
    "lines": {"grid": 0.6, "frame": 1.0},
    "header": {
        "logo_slot": {"x": 34, "y": 18, "w": 250, "h": 36,
                      "note": "league header: badge + wordmark, styled like MBL-SS6"},
        "subtitle": "Score Sheet  ·  Thunder Bay",
        # the game's details, in two rows in the top-right corner (clear of its corner square)
        "game_line": {"size": 9.5, "field_rule": "underline from 3pt after the label to field_end",
                      "rows": [{"baseline": 36, "items": [{"label": "Game No.", "x": 300, "field_end": 380},
                                                          {"label": "Competition", "x": 388, "field_end": 584}]},
                               {"baseline": 56, "items": [{"label": "Place", "x": 300, "field_end": 470},
                                                          {"label": "Date", "x": 478, "field_end": 584}]}]},
    },
    "table": {"x0": 22, "x1": 590},
    "columns": [{"key": "name", "x": 22},
                {"key": "colour", "x": 132, "row_divider": False},
                {"key": "no", "x": 182, "label": "No."},
                {"key": "here", "x": 211, "label": "✓"},
                {"key": "fouls", "x": 231, "label": "Fouls", "per_row": "1 2 3 4 5"},
                {"key": "p1", "x": 300, "sub": "P1"},
                {"key": "p2", "x": 365, "sub": "P2"},
                {"key": "p3", "x": 425, "sub": "P3"},
                {"key": "p4", "x": 490, "sub": "P4"},
                {"key": "total", "x": 553, "label": "Total"}],
    "team_fouls_groups": [{"from": "p1", "to": "p2", "label": "Team fouls"},
                          {"from": "p3", "to": "p4", "label": "Team fouls"}],
    "block": {"header_h": 26, "header_split": 13, "rows": 16, "row_h": 15.5, "bottom_rows": [13, 13, 12.5, 12.5],
              "time_out_label_rows": [2, 3], "bottom_left_x1": 160,
              "timeouts": ["1", "2", "3", "4", "5", "OT"],
              "running": [[1, 36], [37, 69], [70, 100], [101, 130]], "running_x": [165, 588]},
    "blocks": [{"top": 62, "label": "Visitor", "team_field": "visitor_team"},
               {"top": 387, "label": "Home", "team_field": "home_team"}],
    "team_cell": {"x0": 22, "x1": 132, "split": 13,
                  "note": "top half: printed block label; bottom half: fillable team name (PDF text field), "
                          "pre-filled by the script"},
    "footer": {"size": 9.5, "lines": [
        {"baseline": 728, "items": [{"label": "Scorer", "x": 30, "field_end": 178},
                                    {"label": "Timer", "x": 184, "field_end": 342},
                                    {"label": "30” Timer", "x": 350, "field_end": 560}]},
        {"baseline": 744, "items": [{"label": "Referee", "x": 30, "field_end": 178},
                                    {"label": "Umpire", "x": 184, "field_end": 342},
                                    {"label": "Time: Start", "x": 350, "field_end": 494},
                                    {"label": "Finish", "x": 500, "field_end": 584}]},
        {"baseline": 760, "items": [{"label": "Home Coach", "x": 30, "field_end": 290},
                                    {"label": "Visitor Coach", "x": 350, "field_end": 584}]}]},
}

PEN = HexColor("#1F3FB8")   # example handwriting only (--example)
LABEL_TRACK = 0.4          # letter spacing of the (upper-case) labels, as on MBL-SS6
FIELD_FONT = "Helvetica"   # PDF form fields can only use the standard fonts


class PaperSheet:
    """One PDF; add_page() once per game, then save(). Coordinates follow SPEC
    (top-left, y down); y() turns them into PDF coordinates."""

    def __init__(self, out, spec=SPEC):
        self.S = spec
        self.W, self.H = spec["page"]["w"], spec["page"]["h"]
        self.c = canvas.Canvas(out, pagesize=(self.W, self.H))
        self.c.setTitle("Masters Basketball League score sheet (paper form)")
        self.c.setAuthor("Masters Basketball League")
        self.pages, self.prefix, self.maps, self.multi = 0, "", [], False
        self.label_font, self.number_font = spec["fonts"]["label"], spec["fonts"]["number"]
        self.grid, self.frame = spec["lines"]["grid"], spec["lines"]["frame"]

    def y(self, top_y):
        return self.H - top_y

    # ---- helpers --------------------------------------------------------
    def width(self, s, size, font=None, upper=True):
        font = font or self.label_font
        s = s.upper() if upper else s
        return pdfmetrics.stringWidth(s, font, size) + LABEL_TRACK * max(len(s) - 1, 0)

    def fit(self, s, size, room, font=None, upper=True):
        """The largest size up to `size` at which s fits in `room` points."""
        w = self.width(s, size, font, upper)
        return size if w <= room else size * room / w

    def label(self, x, base, s, size, anchor="l", color=NAVY, room=None):
        if room: size = self.fit(s, size, room)
        return draw_text(self.c, x, self.y(base), s.upper(), self.label_font, size, color, anchor, LABEL_TRACK)

    def number(self, x, base, s, size, anchor="c", color=NAVY):
        return draw_text(self.c, x, self.y(base), s, self.number_font, size, color, anchor)

    def line(self, x0, y0, x1, y1, lw=None, color=NAVY):
        c = self.c
        c.setLineWidth(lw or self.grid); c.setStrokeColor(color)
        c.line(x0, self.y(y0), x1, self.y(y1))

    def fill(self, x, top, w, h, color):
        self.c.setFillColor(color)
        self.c.rect(x, self.y(top + h), w, h, stroke=0, fill=1)

    def field(self, name, x, top, w, h, value="", size=9.5, maxlen=None):
        """A fillable text field; a long value gets a smaller font so it fits."""
        value = str(value or "")
        if value:
            size = max(5.0, min(size, (w - 4) / max(1e-6, pdfmetrics.stringWidth(value, FIELD_FONT, 1))))
        kw = dict(name=self.prefix + name, x=x, y=self.y(top + h), width=w, height=h, value=value,
                  fontName=FIELD_FONT, fontSize=round(size, 1), borderWidth=0, fillColor=None,
                  borderColor=None, textColor=black, forceBorder=False, tooltip=name.replace("_", " "))
        if maxlen: kw["maxlen"] = maxlen
        self.c.acroForm.textfield(**kw)
        self.map["fields"][name] = box(x, top, w, h)

    def tick(self, cx, cy, s=3.4):
        """A check mark (Barlow has no ✓), centred on (cx, cy)."""
        c = self.c
        c.setLineWidth(1.1); c.setStrokeColor(NAVY); c.setLineCap(1); c.setLineJoin(1)
        p = c.beginPath()
        p.moveTo(cx - s, self.y(cy)); p.lineTo(cx - s * 0.3, self.y(cy + s * 0.75)); p.lineTo(cx + s, self.y(cy - s))
        c.drawPath(p, stroke=1, fill=0)
        c.setLineCap(0); c.setLineJoin(0)

    # ---- page parts -----------------------------------------------------
    def header(self, g):
        H = self.S["header"]
        slot = H["logo_slot"]
        draw_header(self.c, slot["x"], self.y(slot["y"]), H["subtitle"].upper(), f"Form {FORM} · Letter",
                    badge=slot["h"])
        self.map["header"] = {"logo_slot": box(slot["x"], slot["y"], slot["w"], slot["h"])}
        gl = H["game_line"]
        values = {"Game No.": "game_no", "Competition": "competition", "Place": "place", "Date": "date"}
        for row in gl["rows"]:
            self.underlined(row["items"], row["baseline"], gl["size"], BLUE,
                            lambda lab: (values[lab], g.get(values[lab], "")))

    def underlined(self, items, base, size, color, field_for=None):
        """Labels, each followed by a rule (from 3 pt after the label to field_end);
        field_for(label) -> (name, value) adds a fillable field on the rule."""
        for it in items:
            w = self.label(it["x"], base, it["label"], size, color=color)
            x0, x1 = it["x"] + w + 3, it["field_end"]
            self.line(x0, base + 1.5, x1, base + 1.5, color=RULE)
            if field_for:
                name, value = field_for(it["label"])
                self.field(name, x0, base - 10, x1 - x0, 12, value, size=10)
            else:
                key = it["label"].lower().replace("”", "").replace(":", "").replace(" ", "_").strip("_")
                self.map["footer"][key] = box(x0, base - 10, x1 - x0, 12)

    def block(self, B, team):
        S, blk, tc = self.S, self.S["block"], self.S["team_cell"]
        x0, x1 = S["table"]["x0"], S["table"]["x1"]
        cols = {c["key"]: c for c in S["columns"]}
        edges = [c["x"] for c in S["columns"]] + [x1]
        span = {c["key"]: (c["x"], edges[i + 1]) for i, c in enumerate(S["columns"])}
        T, hh, hs, rh = B["top"], blk["header_h"], blk["header_split"], blk["row_h"]
        rows_top = T + hh
        bottom_top = rows_top + blk["rows"] * rh
        bottom = bottom_top + sum(blk["bottom_rows"])
        side = B["team_field"].split("_")[0]
        m = self.map["blocks"][side] = {"frame": box(x0, T, x1 - x0, bottom - T)}

        # tinted header, white where people write (team name, colour)
        self.fill(x0, T, x1 - x0, hh, TINT)
        self.fill(tc["x0"], T + tc["split"], tc["x1"] - tc["x0"], hh - tc["split"], white)
        cx0, cx1 = span["colour"]
        self.fill(cx0, T, cx1 - cx0, hh, white)
        tl = blk["time_out_label_rows"]
        lx1 = blk["bottom_left_x1"]
        to_top = bottom_top + sum(blk["bottom_rows"][:tl[0]])
        self.fill(x0, to_top, lx1 - x0, bottom - to_top, TINT)

        # header lines
        self.line(x0, rows_top, x1, rows_top)
        self.line(tc["x0"], T + tc["split"], tc["x1"], T + tc["split"])
        self.line(cx0, T, cx0, rows_top)                       # name | colour: header only
        for g in S["team_fouls_groups"]:
            gx0, gx1 = span[g["from"]][0], span[g["to"]][1]
            self.line(gx0, T + hs, gx1, T + hs)
            self.line(span[g["to"]][0], T + hs, span[g["to"]][0], bottom_top)   # P2 / P4 from below the split
            self.label((gx0 + gx1) / 2, T + hs - 4, g["label"], 7.6, anchor="c", room=gx1 - gx0 - 6)
        for k in ("no", "here", "fouls", "p1", "p3", "total"):
            self.line(cols[k]["x"], T, cols[k]["x"], bottom_top)
        # header text
        self.label(tc["x0"] + 4, T + tc["split"] - 3.8, B["label"], 8, room=tc["x1"] - tc["x0"] - 8)
        self.field(B["team_field"], tc["x0"] + 2, T + tc["split"] + 0.5, tc["x1"] - tc["x0"] - 4,
                   hh - tc["split"] - 1, team.get("name", ""), size=9)
        m["team_label"] = box(tc["x0"], T, tc["x1"] - tc["x0"], tc["split"])
        m["team_name"] = box(tc["x0"], T + tc["split"], tc["x1"] - tc["x0"], hh - tc["split"])
        m["colour"] = box(cx0, T, cx1 - cx0, hh)
        self.label(cx1 - 3, T + 7, "Colour", 5.6, anchor="r", color=RULE)
        for k in ("no", "fouls", "total"):
            a, b = span[k]
            self.label((a + b) / 2, T + hh / 2 + 3, cols[k]["label"], 8, anchor="c", room=b - a - 4)
        a, b = span["here"]
        self.tick((a + b) / 2, T + hh / 2)
        for k in ("p1", "p2", "p3", "p4"):
            a, b = span[k]
            # "P1-" then the team-foul digits 1-5, spaced so each can be circled or struck
            sub, size = cols[k]["sub"], 7
            sw = self.width(sub, size)
            dp = min(7.5, (b - a - 6 - sw - 2) / 5)
            sx = (a + b) / 2 - (sw + 2 + 5 * dp) / 2
            self.label(sx, T + hh - 3.6, sub, size)
            m.setdefault("team_foul_digits", {})[k] = []
            for i in range(5):
                self.number(sx + sw + 2 + (i + 0.5) * dp, T + hh - 3.6, str(i + 1), size)
                m["team_foul_digits"][k].append(box(sx + sw + 2 + i * dp, T + hs, dp, hh - hs))
        m["header"] = {k: box(span[k][0], T, span[k][1] - span[k][0], hh) for k in ("no", "here", "fouls", "total")}
        m["team_fouls"] = {k: box(span[k][0], T + hs, span[k][1] - span[k][0], hh - hs) for k in ("p1", "p2", "p3", "p4")}

        # player rows
        players = team.get("players", [])
        fx0, fx1 = span["fouls"]
        pitch = (fx1 - fx0 - 8) / 5
        m["rows"] = []
        for r in range(blk["rows"]):
            top = rows_top + r * rh
            if r:
                self.line(x0, top, x1, top, color=RULE)
            for i in range(5):
                self.number(fx0 + 4 + (i + 0.5) * pitch, top + rh / 2 + 3, str(i + 1), 8.2)
            pl = players[r] if r < len(players) else {}
            n = f"{side}_p{r + 1:02d}"
            self.field(n + "_name", x0 + 2, top + 1, span["no"][0] - x0 - 4, rh - 2, pl.get("name", ""), size=9.5)
            self.field(n + "_no", span["no"][0] + 1, top + 1, span["no"][1] - span["no"][0] - 2, rh - 2,
                       pl.get("num", ""), size=9.5, maxlen=3)
            row = {"row": box(x0, top, x1 - x0, rh), "name": box(x0, top, span["no"][0] - x0, rh)}
            for k in ("no", "here", "fouls", "p1", "p2", "p3", "p4", "total"):
                row[k] = box(span[k][0], top, span[k][1] - span[k][0], rh)
            row["foul_marks"] = [box(fx0 + 4 + i * pitch, top, pitch, rh) for i in range(5)]
            m["rows"].append(row)
        self.line(x0, bottom_top, x1, bottom_top)

        # bottom rows: coach, timeouts, Time Out | running score
        ys = [bottom_top]
        for h in blk["bottom_rows"]: ys.append(ys[-1] + h)
        self.line(lx1, bottom_top, lx1, bottom)
        for i in range(1, len(blk["bottom_rows"])):
            if i > tl[0]:                      # no line between the Time Out rows on the left
                self.line(lx1, ys[i], x1, ys[i])
            else:
                self.line(x0, ys[i], x1, ys[i])
        self.label(x0 + 4, ys[1] - 3, "Coach:", 7, color=NAVY)
        m["coach"] = box(x0, ys[0], lx1 - x0, ys[1] - ys[0])
        tos = blk["timeouts"]
        tw = (lx1 - x0) / len(tos)
        m["timeouts"] = {}
        for i, t in enumerate(tos):
            bx = x0 + i * tw
            if i: self.line(bx, ys[1], bx, ys[2])
            self.number(bx + tw / 2, ys[2] - 3.6, t, 8.5)
            m["timeouts"][t] = box(bx, ys[1], tw, ys[2] - ys[1])
        self.label(x0 + 4, (to_top + bottom) / 2 + 3, "Time Out", 9, color=NAVY)
        m["time_out_label"] = box(x0, to_top, lx1 - x0, bottom - to_top)
        rx0, rx1 = blk["running_x"]
        size = running_size(self.S, self.number_font)
        m["running"] = {}
        for li, (a, b) in enumerate(blk["running"]):
            n = b - a + 1
            p = (rx1 - rx0) / n
            top, h = ys[li], ys[li + 1] - ys[li]
            for i in range(n):
                self.number(rx0 + (i + 0.5) * p, top + h / 2 + size * 0.36, str(a + i), size)
                m["running"][str(a + i)] = box(rx0 + i * p, top, p, h)
        # frame last, over the fills' edges
        self.c.setLineWidth(self.frame); self.c.setStrokeColor(NAVY)
        self.c.rect(x0, self.y(bottom), x1 - x0, bottom - T, stroke=1, fill=0)

    def corners(self):
        k = self.S["corners"]
        z, i = k["size"], k["inset"]
        self.c.setFillColor(black)
        self.map["corners"] = []
        for x in (i, self.W - i - z):
            for y in (i, self.H - i - z):
                self.c.rect(x, self.y(y + z), z, z, stroke=0, fill=1)
                self.map["corners"].append(box(x, y, z, z))

    def footer(self):
        F = self.S["footer"]
        for ln in F["lines"]:
            self.underlined(ln["items"], ln["baseline"], F["size"], BLUE)

    def add_page(self, g=None, example=False):
        g = g or {}
        self.pages += 1
        self.prefix = f"g{self.pages}_" if self.multi else ""
        self.map = {"fields": {}, "header": {}, "blocks": {}, "footer": {}}
        self.header(g)
        teams = {"visitor": g.get("away", {}), "home": g.get("home", {})}
        for B in self.S["blocks"]:
            self.block(B, teams[B["team_field"].split("_")[0]])
        self.footer()
        self.corners()
        if example:
            self.example_marks(g)
        self.maps.append(self.map)
        self.c.showPage()

    def save(self):
        self.c.save()

    # ---- example handwriting (previews only) ----------------------------
    def pen(self, x, base, s, size=9.5, anchor="c"):
        draw_text(self.c, x, self.y(base), s, "CondSemi", size, PEN, anchor)

    def ptick(self, cx, cy, s=3.2):
        c = self.c
        c.setStrokeColor(PEN); c.setLineWidth(1.2); c.setLineCap(1)
        p = c.beginPath()
        p.moveTo(cx - s, self.y(cy)); p.lineTo(cx - s * 0.2, self.y(cy + s * 0.8)); p.lineTo(cx + s * 1.1, self.y(cy - s * 1.1))
        c.drawPath(p, stroke=1, fill=0); c.setLineCap(0)

    def ring(self, x, y, w, h):
        self.c.setStrokeColor(PEN); self.c.setLineWidth(0.9)
        self.c.ellipse(x, self.y(y + h), x + w, self.y(y), stroke=1, fill=0)

    def stroke(self, x0, y0, x1, y1, lw=1.0):
        self.c.setStrokeColor(PEN); self.c.setLineWidth(lw)
        self.c.line(x0, self.y(y0), x1, self.y(y1))

    def example_marks(self, g):
        """A made-up game written onto the sheet the way the league's old sheet
        is marked (an open question for this form): in each period cell every
        attempt in order (2 or 3 a basket, a dot a made free throw worth 2,
        1 a 1-point free throw after a basket, 0 a miss) and the period's points
        circled; Total; fouls circled; team fouls struck through; each team's
        points per period boxed under its last player, the final boxed under
        Total; each running total reached struck through."""
        rnd = random.Random(g.get("game_id", "example"))
        periods = ("p1", "p2", "p3", "p4")
        for side, key in (("visitor", "away"), ("home", "home")):
            m = self.map["blocks"][side]
            players = [p for p in g.get(key, {}).get("players", []) if p.get("name")]
            played = [i for i in range(len(players)) if rnd.random() < 0.85][:10]
            shooters = played[:]
            rnd.shuffle(shooters)
            weights = {i: w for i, w in zip(shooters, [9, 7, 6, 4, 3, 3, 2, 2, 1, 1])}
            marks = {i: {p: [] for p in periods} for i in played}
            timeline = []                      # (period, points) in the order scored
            fouls = {i: 0 for i in played}
            team_fouls = {p: 0 for p in periods}
            for p in periods:
                pts = 0
                while pts < rnd.randint(10, 16):
                    i = rnd.choices(played, [weights[j] for j in played])[0]
                    r = rnd.random()
                    if r < 0.58: ev = [("2", 2)]
                    elif r < 0.72: ev = [("3", 3)]
                    elif r < 0.82: ev = [("•", 2)]
                    elif r < 0.88: ev = [("2", 2), ("1", 1)]
                    else: ev = [("0", 0)]
                    for mark, v in ev:
                        marks[i][p].append((mark, v))
                        if v: timeline.append(v)
                        pts += v
                    if rnd.random() < 0.25:
                        f = rnd.choice(played)
                        if fouls[f] < 4: fouls[f] += 1
                        team_fouls[p] = min(5, team_fouls[p] + 1)
            totals = {p: 0 for p in periods}
            for i in played:
                row = m["rows"][i]
                x, y, w, h = row["here"]
                self.ptick(x + w / 2, y + h / 2)
                fx = row["foul_marks"]
                for k in range(fouls[i]):
                    bx, by, bw, bh = fx[k]
                    self.ring(bx + bw / 2 - 4, by + 2, 8, bh - 4)
                tot = 0
                for p in periods:
                    ms = marks[i][p]
                    if not ms:
                        continue
                    x, y, w, h = row[p]
                    cx = x + 4
                    for mark, _ in ms:
                        if mark == "•":
                            self.c.setFillColor(PEN); self.c.circle(cx + 2.2, self.y(y + h / 2), 2.2, stroke=0, fill=1)
                            cx += 6.5
                        else:
                            draw_text(self.c, cx, self.y(y + h - 3.2), mark, "CondSemi", 9.5, PEN)
                            cx += 6.5
                    v = sum(v for _, v in ms)
                    tot += v; totals[p] += v
                    self.pen(x + w - 9, y + h - 3.2, str(v), 9)
                    self.ring(x + w - 16, y + 0.8, 14, h - 1.6)
                x, y, w, h = row["total"]
                self.pen(x + w / 2, y + h - 3.2, str(tot), 10)
            # the period totals boxed in the first empty row, the final under Total
            spare = m["rows"][min(len(players), len(m["rows"]) - 1)]
            run = 0
            for p in periods:
                run += totals[p]
                x, y, w, h = spare[p]
                self.pen(x + w - 12, y + h - 3.2, str(run), 9.5)
                self.c.setStrokeColor(PEN); self.c.setLineWidth(0.9)
                self.c.rect(x + w - 22, self.y(y + h - 0.8), 20, h - 1.6, stroke=1, fill=0)
            x, y, w, h = spare["total"]
            self.pen(x + w / 2, y + h - 3.2, str(run), 10)
            self.c.rect(x + 4, self.y(y + h - 0.8), w - 8, h - 1.6, stroke=1, fill=0)
            for p in periods:
                for k in range(team_fouls[p]):
                    bx, by, bw, bh = m["team_foul_digits"][p][k]
                    self.stroke(bx + 0.5, by + bh - 2.5, bx + bw - 0.5, by + 2.5, 0.9)
            for t in rnd.sample(["1", "2", "3", "4"], 2):
                bx, by, bw, bh = m["timeouts"][t]
                self.stroke(bx + 5, by + bh - 3, bx + bw - 5, by + 3, 1.1)
            score = 0
            for v in timeline:
                score += v
                if str(score) in m["running"]:
                    bx, by, bw, bh = m["running"][str(score)]
                    self.stroke(bx + bw * 0.25, by + bh - 1.5, bx + bw * 0.75, by + 1.5, 0.9)
        for key, s in (("scorer", "Dana P."), ("timer", "Chris W."), ("30_timer", "Lee M."),
                       ("referee", "Sam T."), ("umpire", "Jo B."), ("time_start", "9:45"), ("finish", "11:05")):
            x, y, w, h = self.map["footer"][key]
            self.pen(x + 6, y + h - 3, s, 10, anchor="l")


def box(x, y, w, h):
    return [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]


def running_size(spec, font):
    """One size for every running-score number: the largest that fits each
    number's slot (92% of its width) and 70% of its row's height."""
    blk = spec["block"]
    rx0, rx1 = blk["running_x"]
    best = 8.0
    for li, (a, b) in enumerate(blk["running"]):
        p = (rx1 - rx0) / (b - a + 1)
        widest = max(pdfmetrics.stringWidth(str(n), font, 1) for n in range(a, b + 1))
        best = min(best, 0.92 * p / widest, 0.7 * blk["bottom_rows"][li])
    return round(best, 2)


# --------------------------------------------------------------------------
def spec_json():
    return {"form": FORM, **SPEC}


def geometry_json():
    """Where every box is (points; [x, y, width, height] from the page's
    top-left corner). The map is the same for every game."""
    s = PaperSheet(io.BytesIO())
    s.add_page({})
    return {"form": FORM, "units": "points; [x, y, width, height] from the top-left corner of the page",
            "page_size": [s.W, s.H], "pages": s.maps}


# --------------------------------------------------------------------------
# Data (the same files MBL-SS6 reads; see data/CLAUDE.md)
def load_yaml(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def as_list(obj, key):
    if isinstance(obj, dict):
        return obj[key] if key in obj else [dict(id=k, **v) for k, v in obj.items()]
    return obj or []


def nice_date(iso):
    d = dt.date.fromisoformat(str(iso))
    return d.strftime("%a %b ") + str(d.day) + d.strftime(", %Y")


def season_gym(data_dir):
    """The season's gym from data/seasons.yml (used when schedule.csv's gym is blank)."""
    path = os.path.join(os.path.dirname(os.path.abspath(data_dir)), "seasons.yml")
    sid = os.path.basename(os.path.abspath(data_dir))
    if not os.path.exists(path):
        return ""
    for s in load_yaml(path) or []:
        if str(s.get("id")) == sid:
            return s.get("gym") or ""
    return ""


def load_games(data_dir):
    rows = SPEC["block"]["rows"]
    teams = {t["id"]: t for t in as_list(load_yaml(os.path.join(data_dir, "teams.yml")), "teams")}
    roster = {tid: [] for tid in teams}
    for p in as_list(load_yaml(os.path.join(data_dir, "players.yml")), "players"):
        if p.get("sub"):
            continue                              # subs' rows are left blank
        num = p.get("number")
        roster.setdefault(p["team"], []).append(  # 0 is a real jersey number
            {"num": "" if num is None else str(num).strip(), "name": p.get("display", "")})
    for tid, ps in roster.items():
        ps.sort(key=lambda p: (not p["num"].isdigit(), int(p["num"]) if p["num"].isdigit() else 0, p["name"]))
        if len(ps) > rows:
            print(f"warning: {tid} has {len(ps)} players; only {rows} fit", file=sys.stderr)
            del ps[rows:]
    gym = season_gym(data_dir)
    games = []
    with open(os.path.join(data_dir, "schedule.csv")) as f:
        for row in csv.DictReader(f):
            h, a = row["home"].strip(), row["away"].strip()
            if h not in teams or a not in teams:
                continue                          # byes and TBD playoff slots
            if (row.get("status") or "").strip().lower() == "cancelled":
                continue
            gid = row["game_id"].strip()
            games.append({
                "game_id": gid,
                "iso_date": row["date"].strip(),
                "game_no": gid.rsplit("-g", 1)[1] if "-g" in gid else "",
                "competition": "Masters",
                "place": (row.get("gym") or "").strip() or gym,
                "date": nice_date(row["date"].strip()),
                "home": {"name": teams[h]["name"], "players": roster.get(h, [])},
                "away": {"name": teams[a]["name"], "players": roster.get(a, [])},
            })
    return games


def build(path, games, example=False):
    s = PaperSheet(path)
    s.multi = len(games) > 1
    for g in games:
        s.add_page(g, example=example)
    s.save()


def main():
    ap = argparse.ArgumentParser(description="Make the league's paper score sheet (form MBL-PS1).")
    ap.add_argument("--data", help="season folder, e.g. data/2026-27")
    ap.add_argument("--date", help="only games on this date (YYYY-MM-DD)")
    ap.add_argument("--game", help="only this game_id")
    ap.add_argument("--from-today", action="store_true", help="skip games before today")
    ap.add_argument("--blank", action="store_true", help="a blank fillable sheet")
    ap.add_argument("--example", action="store_true",
                    help="write a made-up game on each sheet as handwriting (previews only)")
    ap.add_argument("--allow-empty", action="store_true",
                    help="no matching games is fine (e.g. --from-today after the last game day): make nothing, exit 0")
    ap.add_argument("--out", help="output folder")
    ap.add_argument("--spec", metavar="OUT.json", help="write the sheet spec as JSON and stop")
    ap.add_argument("--geometry", metavar="OUT.json", help="write where every box is and stop")
    a = ap.parse_args()
    if a.spec or a.geometry:
        path, obj, kw = (a.spec, spec_json(), {"indent": 2}) if a.spec else \
            (a.geometry, geometry_json(), {"separators": (",", ":")})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, **kw)
            f.write("\n")
        print(path)
        return
    if not a.out:
        ap.error("give --out (or --spec or --geometry)")
    os.makedirs(a.out, exist_ok=True)
    made = []
    if a.blank:
        p = os.path.join(a.out, "paper-sheet-blank.pdf")
        build(p, [{}]); made.append(p)
    else:
        if not a.data:
            ap.error("give --data or --blank")
        games = load_games(a.data)
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
        days = {}
        for g in games:
            days.setdefault(g["iso_date"], []).append(g)
        for day, gs in sorted(days.items()):
            p = os.path.join(a.out, f"paper-sheet{'-example' if a.example else 's'}-{day}.pdf")
            build(p, gs, a.example); made.append(p)
    for p in made:
        print(p)


if __name__ == "__main__":
    main()
