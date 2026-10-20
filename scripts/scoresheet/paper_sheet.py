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
import argparse, csv, datetime as dt, io, json, os, sys
from reportlab.lib.colors import white, black
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from branding import NAVY, BLUE, RULE, TINT, draw_text, draw_header  # noqa: E402

FORM = "MBL-PS1"

SPEC = {
    "page": {"w": 612, "h": 792, "size": "letter", "orientation": "portrait"},
    "fonts": {"label": "CondSemi", "number": "Cond"},   # Barlow Condensed 600 / 700 (branding.py)
    "lines": {"grid": 0.6, "frame": 1.0},
    "header": {
        "logo_slot": {"x": 34, "y": 26, "w": 250, "h": 36,
                      "note": "league header: badge + wordmark, styled like MBL-SS6"},
        "title": {"text": "Score Sheet", "x_right": 590, "baseline": 62, "size": 9.5},
        "game_line": {"baseline": 78, "size": 10.5, "field_rule": "underline from 3pt after the label to field_end",
                      "items": [{"label": "Game No.", "x": 40, "field_end": 204},
                                {"label": "Competition", "x": 208, "field_end": 384},
                                {"label": "Place", "x": 388, "field_end": 478},
                                {"label": "Date", "x": 482, "field_end": 584}]},
    },
    "table": {"x0": 22, "x1": 590},
    "columns": [{"key": "name", "x": 22},
                {"key": "colour", "x": 110, "row_divider": False},
                {"key": "no", "x": 182, "label": "No."},
                {"key": "here", "x": 211, "label": "✓"},
                {"key": "fouls", "x": 231, "label": "Fouls", "per_row": "1 2 3 4 5"},
                {"key": "p1", "x": 300, "sub": "P1-"},
                {"key": "p2", "x": 365, "sub": "P2-"},
                {"key": "p3", "x": 425, "sub": "P3-"},
                {"key": "p4", "x": 490, "sub": "P4-"},
                {"key": "total", "x": 553, "label": "Total"}],
    "team_fouls_groups": [{"from": "p1", "to": "p2", "label": "Team fouls"},
                          {"from": "p3", "to": "p4", "label": "Team fouls"}],
    "block": {"header_h": 26, "header_split": 13, "rows": 16, "row_h": 14, "bottom_rows": [12, 14, 13, 13],
              "time_out_label_rows": [2, 3], "bottom_left_x1": 182,
              "timeouts": ["1", "2", "3", "4", "5", "OT"],
              "running": [[1, 36], [37, 69], [70, 100], [101, 130]], "running_x": [188, 588]},
    "blocks": [{"top": 84, "label": "Visitor", "team_field": "visitor_team"},
               {"top": 386, "label": "Home Team", "team_field": "home_team"}],
    "team_cell": {"x0": 22, "x1": 110, "split": 13,
                  "note": "top half: printed block label; bottom half: fillable team name (PDF text field), "
                          "pre-filled by the script"},
    "footer": {"size": 9.5, "lines": [
        {"baseline": 714, "items": [{"label": "Scorer", "x": 30, "field_end": 178},
                                    {"label": "Timer", "x": 184, "field_end": 342},
                                    {"label": "30” Timer", "x": 350, "field_end": 560}]},
        {"baseline": 737, "items": [{"label": "Referee", "x": 30, "field_end": 178},
                                    {"label": "Umpire", "x": 184, "field_end": 342},
                                    {"label": "Time: Start", "x": 350, "field_end": 494},
                                    {"label": "Finish", "x": 500, "field_end": 584}]},
        {"baseline": 760, "items": [{"label": "Home Coach", "x": 30, "field_end": 290},
                                    {"label": "Visitor Coach", "x": 350, "field_end": 584}]}]},
}

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
        draw_header(self.c, slot["x"], self.y(slot["y"]), "THUNDER BAY", f"Form {FORM} · Letter", badge=slot["h"])
        self.map["header"] = {"logo_slot": box(slot["x"], slot["y"], slot["w"], slot["h"])}
        t = H["title"]
        self.label(t["x_right"], t["baseline"], t["text"], t["size"], anchor="r", color=NAVY)
        gl = H["game_line"]
        values = {"Game No.": "game_no", "Competition": "competition", "Place": "place", "Date": "date"}
        self.underlined(gl["items"], gl["baseline"], gl["size"], BLUE,
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
        self.label((tc["x0"] + tc["x1"]) / 2, T + tc["split"] - 3.8, B["label"], 8,
                   anchor="c", room=tc["x1"] - tc["x0"] - 6)
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
            for i in range(5):
                self.number(sx + sw + 2 + (i + 0.5) * dp, T + hh - 3.6, str(i + 1), size)
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

    def footer(self):
        F = self.S["footer"]
        for ln in F["lines"]:
            self.underlined(ln["items"], ln["baseline"], F["size"], BLUE)

    def add_page(self, g=None):
        g = g or {}
        self.pages += 1
        self.prefix = f"g{self.pages}_" if self.multi else ""
        self.map = {"fields": {}, "header": {}, "blocks": {}, "footer": {}}
        self.header(g)
        teams = {"visitor": g.get("away", {}), "home": g.get("home", {})}
        for B in self.S["blocks"]:
            self.block(B, teams[B["team_field"].split("_")[0]])
        self.footer()
        self.maps.append(self.map)
        self.c.showPage()

    def save(self):
        self.c.save()


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


def build(path, games):
    s = PaperSheet(path)
    s.multi = len(games) > 1
    for g in games:
        s.add_page(g)
    s.save()


def main():
    ap = argparse.ArgumentParser(description="Make the league's paper score sheet (form MBL-PS1).")
    ap.add_argument("--data", help="season folder, e.g. data/2026-27")
    ap.add_argument("--date", help="only games on this date (YYYY-MM-DD)")
    ap.add_argument("--game", help="only this game_id")
    ap.add_argument("--from-today", action="store_true", help="skip games before today")
    ap.add_argument("--blank", action="store_true", help="a blank fillable sheet")
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
            sys.exit("no games matched")
        days = {}
        for g in games:
            days.setdefault(g["iso_date"], []).append(g)
        for day, gs in sorted(days.items()):
            p = os.path.join(a.out, f"paper-sheets-{day}.pdf")
            build(p, gs); made.append(p)
    for p in made:
        print(p)


if __name__ == "__main__":
    main()
