"""The score sheet rules: read a game file (a digital copy of the paper sheet,
form MBL-SS6), check it, and work out each player's numbers.

This is the one place the rules live. build_stats.py uses it for every file in
data/<season>/games/; the entry page (/enter/) and /record-game use the same
paths to point at boxes. The entry page runs a line-for-line JavaScript port,
assets/js/sheet-rules.js: change this file first, then that one, and keep the
messages identical (tests/js runs it on the same fixtures). The format is described in data/CLAUDE.md ("Game file").

    check(sheet, ctx) -> (game, problems)

`problems` is a list of {"level": "error" | "warning", "at": path, "message": str}.
`at` names exactly one box on the sheet, as a dotted path into the file:

    running.lh.27              the running-score box for Lakehead's total 27
    teams.pa.players.3.ft.2    row 4 of Port Arthur's roster, its 3rd free-throw circle
    teams.pa.players.3.fouls   that row's personal-foul boxes
    lines.pa.1                 the line drawn at the end of Q2 for Port Arthur
    boxes.lh.final             Lakehead's Final box
    notes.0                    the first entry in Notes

Rows and free-throw circles count from 0, like list positions in the file:
players.0 is the top row, ft.0 the first circle.

`game` (None when there are errors) is the game as the rest of build_stats.py
expects it: home, away, type, date, final, quarters, ot, and one line per
player ticked Here with pts, ftm, fta, pf, tech and flagrant.

How the numbers come from the sheet:
- Points: the running score. Each box holds the scorer's jersey number beside
  the team's new total; the jump from the previous total (1, 2 or 3) is what
  that player scored.
- FTM and FTA: the free-throw circles, never the running score. A free throw
  can be worth 1, 2 or 3 points under league rules, so any jump might be one.
- GP: the Here tick.
- Fouls: the foul boxes (`fouls`, flagrants included) and T boxes (`tech`).
  Flagrant fouls are counted from Notes.
- Quarters: the Q1-Q4 boxes (running totals at the end of each quarter).
"""
import json
import re
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parent / "scoresheet" / "spec.json"
SPEC = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

FORM = SPEC["form"]
ROSTER_ROWS = SPEC["roster_rows"]
FT_CIRCLES = SPEC["ft_circles_per_page"] * 2          # 1-10 on page 1, 11-20 on page 2
MAX_FOULS = SPEC["personal_foul_boxes"]
MAX_TECH = SPEC["technical_boxes"]
MAX_TOTAL = SPEC["max_running_total"]                  # the most any layout's running score holds
QUARTER_BOXES = [b["key"] for b in SPEC["score_boxes"] if b["key"].startswith("q")]   # q1-q4
STATUSES = ("draft", "final")
NOTE_KINDS = ("flagrant", "note")
FT_RE = re.compile(r"^[MX]*$")
JERSEY_RE = re.compile(r"^\d{1,2}$")
FIELDS = {"game_id", "form", "status", "home", "away", "scorekeeper", "teams", "running", "lines",
          "boxes", "notes", "review", "checked_by"}
ROW_FIELDS = {"player", "name", "num", "here", "ft", "fouls", "tech"}


def problem(level, at, message):
    return {"level": level, "at": at, "message": message}


def _count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def jersey(num):
    """A jersey number as text ("4", "00"), or None if it isn't one."""
    if isinstance(num, bool):
        return None
    if isinstance(num, int):
        num = str(num)
    if isinstance(num, str) and JERSEY_RE.match(num.strip()):
        return num.strip()
    return None


def check(sheet, ctx):
    """Check one game file and compute its lines.

    ctx: {"stem": file name without .yml, "folder": "games" | "drafts",
          "teams": {id: team}, "players": {id: player}, "schedule": {game_id: row}}
    Schedule rows are build_stats.load_schedule rows (date, home, away, type,
    teams_known, cancelled)."""
    out = []
    err = lambda at, msg: out.append(problem("error", at, msg))
    warn = lambda at, msg: out.append(problem("warning", at, msg))

    if not isinstance(sheet, dict):
        err("", "the file should be a game sheet (game_id, status, home, away, teams, running, ...)")
        return None, out
    for key in sorted(set(sheet) - FIELDS):
        err(key, f"'{key}' isn't part of a game sheet")

    # ---- the header ------------------------------------------------------
    status = sheet.get("status")
    final_file = ctx.get("folder") == "games"
    if status not in STATUSES:
        err("status", f"status should be draft or final, not {status!r}")
    elif final_file and status != "final":
        err("status", "a file in games/ must be status: final (drafts go in drafts/)")
    elif not final_file and status != "draft":
        err("status", "a file in drafts/ must be status: draft (finished games go in games/)")
    is_final = status == "final"

    if sheet.get("form") != FORM:
        err("form", f"form {sheet.get('form')!r} isn't {FORM}, the sheet this format describes")

    gid = sheet.get("game_id")
    row = None
    if gid != ctx.get("stem"):
        err("game_id", f"game_id {gid!r} doesn't match the file name '{ctx.get('stem')}'")
    else:
        row = ctx["schedule"].get(gid)
        if row is None:
            err("game_id", f"game_id '{gid}' has no row in schedule.csv")
        elif not row["teams_known"]:
            err("game_id", f"schedule.csv still lists this game as {row['home']} vs {row['away']}. "
                           "Put the two teams' ids in its home and away cells first")
            row = None
        elif row["cancelled"]:
            err("game_id", f"game '{gid}' is marked cancelled in schedule.csv. "
                           "Delete this file, or clear the status if the game was played")
            row = None

    home, away = sheet.get("home"), sheet.get("away")
    for side, tid in (("home", home), ("away", away)):
        if tid not in ctx["teams"]:
            err(side, f"{side} team {tid!r} is not in teams.yml")
    if row is not None and (home, away) != (row["home"], row["away"]):
        err("home", f"home/away {home}/{away} doesn't match schedule.csv ({row['home']}/{row['away']})")
    if home == away or home not in ctx["teams"] or away not in ctx["teams"]:
        return None, out
    sides = (home, away)

    # ---- rosters ------------------------------------------------------------
    teams = sheet.get("teams")
    if not isinstance(teams, dict) or set(teams) != set(sides):
        err("teams", f"teams should list exactly {home} and {away}")
        return None, out
    rows = {}                 # team -> list of (index, row) that are well formed
    by_num = {}               # team -> jersey -> index
    seen_players = {}
    for tid in sides:
        base = f"teams.{tid}.players"
        listed = (teams[tid] or {}).get("players") if isinstance(teams[tid], dict) else None
        if not isinstance(listed, list) or not listed:
            err(base, f"list {tid}'s players, one per roster row")
            listed = []
        if len(listed) > ROSTER_ROWS:
            err(base, f"{tid} has {len(listed)} rows; the sheet has {ROSTER_ROWS}")
        rows[tid], by_num[tid] = [], {}
        for i, r in enumerate(listed):
            at = f"{base}.{i}"
            if not isinstance(r, dict):
                err(at, "a row looks like {player: dave-m, num: 4, here: true, ft: MMX, fouls: 2}")
                continue
            for key in sorted(set(r) - ROW_FIELDS):
                err(f"{at}.{key}", f"'{key}' isn't part of a roster row")
            num = jersey(r.get("num"))
            if num is None:
                err(f"{at}.num", f"jersey number {r.get('num')!r} should be 0 to 99 (or \"00\")")
            elif num in by_num[tid]:
                err(f"{at}.num", f"#{num} is on two {tid} rows (rows {by_num[tid][num] + 1} and {i + 1}); "
                                 "the running score can't tell them apart")
            else:
                by_num[tid][num] = i
            pid = r.get("player")
            if pid is None:
                who = r.get("name") or f"#{num}"
                msg = (f"{who} isn't matched to a player id yet. Pick one from players.yml, or add them "
                       "there (a sub: sub: true, with this team and number)")
                (err if is_final else warn)(f"{at}.player", msg)
            elif pid not in ctx["players"]:
                err(f"{at}.player", f"player {pid!r} is not in players.yml")
            elif pid in seen_players:
                err(f"{at}.player", f"{pid} is listed twice in this game ({seen_players[pid]})")
            else:
                seen_players[pid] = at
            if not isinstance(r.get("here"), bool):
                err(f"{at}.here", "here should be true (ticked) or false")
            ft = r.get("ft", "")
            if not isinstance(ft, str) or not FT_RE.match(ft):
                err(f"{at}.ft", f"ft {ft!r} should be the circles in order: M for made (filled), "
                                "X for missed (slashed), e.g. MMXM")
                ft = ""
            elif len(ft) > FT_CIRCLES:
                err(f"{at}.ft.{FT_CIRCLES}", f"{len(ft)} free throws; the sheet has {FT_CIRCLES} circles")
            for key, most in (("fouls", MAX_FOULS), ("tech", MAX_TECH)):
                v = r.get(key, 0)
                if not _count(v) or v > most:
                    err(f"{at}.{key}", f"{key} {v!r} should be a whole number from 0 to {most}")
            rows[tid].append((i, {**r, "_num": num, "_ft": ft}))
        if ROSTER_ROWS and not any(rr.get("here") is True for _, rr in rows[tid]):
            err(base, f"nobody on {tid} is ticked Here")

    # ---- running score ------------------------------------------------------
    running = sheet.get("running")
    if not isinstance(running, dict) or set(running) != set(sides):
        err("running", f"running should list both teams' boxes: {{{home}: {{2: 4, ...}}, {away}: {{...}}}}")
        return None, out
    pts = {tid: {} for tid in sides}          # team -> row index -> points
    jumps = {tid: {} for tid in sides}        # team -> row index -> scoring jumps
    last = {}
    totals_seen = {}
    for tid in sides:
        boxes = running[tid] or {}
        if not isinstance(boxes, dict):
            err(f"running.{tid}", "the running score is total: jersey number, e.g. {2: 4, 5: 10}")
            boxes = {}
        prev = 0
        totals = []
        for total in sorted(boxes, key=lambda t: (not isinstance(t, int), t if isinstance(t, int) else 0)):
            at = f"running.{tid}.{total}"
            if not isinstance(total, int) or isinstance(total, bool) or not 1 <= total <= MAX_TOTAL:
                err(at, f"{total!r} isn't a running-score box (1 to {MAX_TOTAL})")
                continue
            jump = total - prev
            if not 1 <= jump <= 3:
                err(at, f"{tid} goes from {prev} to {total}, a jump of {jump}; a score is 1, 2 or 3")
            num = jersey(boxes[total])
            if num is None:
                err(at, f"{boxes[total]!r} isn't a jersey number")
            elif num not in by_num[tid]:
                err(at, f"#{num} scored for {tid}, but no {tid} row has #{num}")
            else:
                i = by_num[tid][num]
                r = dict(rows[tid])[i]
                if r.get("here") is not True:
                    err(at, f"#{num} scored, but row {i + 1} ({r.get('player') or r.get('name') or '#' + num}) "
                            "isn't ticked Here")
                if 1 <= jump <= 3:
                    pts[tid][i] = pts[tid].get(i, 0) + jump
                    jumps[tid][i] = jumps[tid].get(i, 0) + 1
            totals.append(total)
            prev = total
        last[tid] = prev
        totals_seen[tid] = set(totals) | {0}

    # free throws: made circles can't outnumber the player's scores
    for tid in sides:
        for i, r in rows[tid]:
            made = r["_ft"].count("M")
            if made > jumps[tid].get(i, 0):
                warn(f"teams.{tid}.players.{i}.ft",
                     f"{made} free throws made, but the running score has {jumps[tid].get(i, 0)} "
                     f"score{'s' if jumps[tid].get(i, 0) != 1 else ''} for #{r['_num']}")

    # ---- quarter lines and score boxes ----------------------------------------
    lines = sheet.get("lines") or {}
    boxes = sheet.get("boxes")
    ends = {}
    if not isinstance(boxes, dict) or set(boxes) != set(sides):
        err("boxes", f"boxes should list both teams' score boxes: {{{home}: {{q1: .., q2: .., q3: .., "
                     f"q4: .., ot: null, final: ..}}, {away}: {{...}}}}")
        return None, out
    for tid in sides:
        b = boxes[tid] if isinstance(boxes[tid], dict) else {}
        tl = lines.get(tid) if isinstance(lines, dict) else None
        if tl is None:
            (err if is_final else warn)(f"lines.{tid}", f"where were {tid}'s end-of-quarter lines drawn? "
                                                        "Give the running total at each: [Q1, Q2, Q3, Q4]")
            tl = []
        elif not isinstance(tl, list) or len(tl) != len(QUARTER_BOXES) or not all(_count(x) for x in tl):
            err(f"lines.{tid}", f"lines for {tid} should be {len(QUARTER_BOXES)} running totals, one per quarter")
            tl = []
        for q, x in enumerate(tl):
            if x not in totals_seen[tid]:
                err(f"lines.{tid}.{q}", f"the Q{q + 1} line is under {x}, but {tid} has no box with that total")
            if q and x < tl[q - 1]:
                err(f"lines.{tid}.{q}", f"the Q{q + 1} line ({x}) is above the Q{q} line ({tl[q - 1]})")
        qs = []
        for q, key in enumerate(QUARTER_BOXES):
            v = b.get(key)
            if not _count(v):
                err(f"boxes.{tid}.{key}", f"the {key.upper()} box should hold {tid}'s running total at the end "
                                          f"of that quarter, not {v!r}")
                qs.append(None)
                continue
            qs.append(v)
            if q < len(tl) and v != tl[q]:
                err(f"boxes.{tid}.{key}", f"the {key.upper()} box says {v}, but the Q{q + 1} line is under {tl[q]}")
            if q and qs[q - 1] is not None and v < qs[q - 1]:
                err(f"boxes.{tid}.{key}", f"the {key.upper()} box ({v}) is less than "
                                          f"{QUARTER_BOXES[q - 1].upper()} ({qs[q - 1]})")
        final = b.get("final")
        if not _count(final):
            err(f"boxes.{tid}.final", f"the Final box should hold {tid}'s final score, not {final!r}")
        elif final != last[tid]:
            err(f"boxes.{tid}.final", f"the Final box says {final}, but the running score ends at {last[tid]}")
        # From here on the running score is the final: a wrong Final box is one problem, not several
        ends[tid] = {"q": qs, "ot": b.get("ot"), "final": last[tid]}

    if any(v is None for tid in sides for v in ends[tid]["q"]):
        return None, out
    q4 = {tid: ends[tid]["q"][-1] for tid in sides}
    final = {tid: ends[tid]["final"] for tid in sides}
    went_ot = any(q4[t] != final[t] for t in sides)
    for tid in sides:
        if q4[tid] > final[tid]:
            err(f"boxes.{tid}.q4", f"the Q4 box ({q4[tid]}) is more than the Final box ({final[tid]})")
        ot = ends[tid]["ot"]
        if went_ot:
            if ot != final[tid]:
                err(f"boxes.{tid}.ot", f"after overtime the OT box should hold {tid}'s total, {final[tid]}")
        elif ot is not None:
            err(f"boxes.{tid}.ot", "the OT box is filled in, but Q4 already equals the final score")
    if went_ot and q4[home] != q4[away]:
        err(f"boxes.{home}.q4", f"Q4 ({home} {q4[home]}, {away} {q4[away]}) isn't tied, so there was no "
                                f"overtime: Q4 should equal the final score")
    if final[home] == final[away]:
        err(f"boxes.{home}.final", f"the final score is tied {final[home]}-{final[away]}")

    # ---- notes: flagrant fouls ------------------------------------------------
    flagrants = {tid: {} for tid in sides}
    notes = sheet.get("notes") or []
    if not isinstance(notes, list):
        err("notes", "notes should be a list, e.g. - {team: lh, num: 11, q: 3, kind: flagrant, text: ...}")
        notes = []
    for n, note in enumerate(notes):
        at = f"notes.{n}"
        if not isinstance(note, dict):
            err(at, "a note looks like {team: lh, num: 11, q: 3, kind: flagrant, text: ...}")
            continue
        kind = note.get("kind", "note")
        if kind not in NOTE_KINDS:
            err(f"{at}.kind", f"kind should be flagrant or note, not {kind!r}")
        if kind != "flagrant":
            continue
        tid, num = note.get("team"), jersey(note.get("num"))
        if tid not in sides:
            err(f"{at}.team", f"team {tid!r} isn't playing in this game")
        elif num not in by_num[tid]:
            err(f"{at}.num", f"no {tid} row has #{note.get('num')}")
        else:
            i = by_num[tid][num]
            flagrants[tid][i] = flagrants[tid].get(i, 0) + 1
        if note.get("q") not in (1, 2, 3, 4, "OT"):
            err(f"{at}.q", f"q should be the quarter, 1 to 4 (or OT), not {note.get('q')!r}")
    for tid in sides:
        for i, r in rows[tid]:
            f = flagrants[tid].get(i, 0)
            if f and _count(r.get("fouls", 0)) and f > r.get("fouls", 0):
                err(f"teams.{tid}.players.{i}.fouls", f"{f} flagrant foul{'s' if f > 1 else ''} in Notes, but only "
                    f"{r.get('fouls', 0)} foul box{'es' if r.get('fouls', 0) != 1 else ''} slashed; a flagrant "
                    "is also a personal foul")

    # ---- review and sign-off --------------------------------------------------
    review = sheet.get("review") or []
    if review and is_final:
        err("review", "a final sheet can't have review notes left; settle them, then remove the list")
    for item in review if isinstance(review, list) else []:
        if isinstance(item, dict):
            warn(str(item.get("at", "review")), f"to review: {item.get('note', '')}")
    if is_final and not sheet.get("checked_by"):
        err("checked_by", "a final sheet needs checked_by: who checked it against the paper (\"First L.\")")

    if any(p["level"] == "error" for p in out):
        return None, out

    # ---- the game, for build_stats ---------------------------------------------
    game_lines = []
    for tid in sides:
        for i, r in rows[tid]:
            if r.get("here") is not True or not r.get("player"):
                continue
            ft = r["_ft"]
            game_lines.append({
                "player": r["player"], "team": tid, "num": r["_num"],
                "pts": pts[tid].get(i, 0), "ftm": ft.count("M"), "fta": len(ft),
                "pf": r.get("fouls", 0), "tech": r.get("tech", 0), "flagrant": flagrants[tid].get(i, 0),
            })
    game = {
        "game_id": gid,
        "date": row["date"] if row else None,
        "type": row["type"] if row else None,
        "home": home, "away": away,
        "final": final,
        "quarters": {tid: list(ends[tid]["q"]) for tid in sides},
        "ot": went_ot,
        "lines": game_lines,
        "scorekeeper": sheet.get("scorekeeper"),
        "checked_by": sheet.get("checked_by"),
    }
    return game, out


# --------------------------------------------------------------------------
# Writing a sheet from known totals (the sample seasons and the tests)

def build_sheet(game_id, home, away, quarters, players, rng, checked_by="Sam P.", status="final", final=None):
    """A believable, valid sheet for a game whose numbers are already known.

    quarters: {team: [Q1, Q2, Q3, Q4 running totals]}
    final:    {team: final score}; leave it out when Q4 is the final. A final
              above a tied Q4 is an overtime game.
    players:  {team: [{player, num, pts, ftm, fta, pf, tech, flagrant}]}, everyone ticked Here
    Free throws are 1-point scores; the rest of each player's points are 2s and
    3s. The scores are shuffled into quarters so each quarter ends exactly on
    its total. rng: a random.Random, so the same inputs give the same sheet."""
    teams, running, lines, boxes, notes = {}, {}, {}, {}, []
    for tid in (home, away):
        rows, fts, baskets = [], {}, {}
        for p in players[tid]:
            ft = "M" * p["ftm"] + "X" * (p["fta"] - p["ftm"])
            ft = "".join(rng.sample(ft, len(ft)))
            row = {"player": p["player"], "num": p["num"], "here": True}
            if ft:
                row["ft"] = ft
            if p.get("pf"):
                row["fouls"] = p["pf"]
            if p.get("tech"):
                row["tech"] = p["tech"]
            rows.append(row)
            fts[p["num"]] = p["ftm"]                      # made free throws: 1-point scores here
            baskets[p["num"]] = p["pts"] - p["ftm"]       # the rest in 2s and 3s
            for _ in range(p.get("flagrant", 0)):
                notes.append({"team": tid, "num": p["num"], "q": rng.randint(1, 4), "kind": "flagrant",
                              "text": "flagrant foul"})
        teams[tid] = {"players": rows}
        q = list(quarters[tid])
        end = (final or {}).get(tid, q[-1])
        running[tid] = _fill_quarters(fts, baskets, q + ([end] if end != q[-1] else []), rng)
        lines[tid] = q
        boxes[tid] = {"q1": q[0], "q2": q[1], "q3": q[2], "q4": q[3], "ot": None, "final": end}
    if final and any(final[t] != quarters[t][-1] for t in (home, away)):
        for tid in (home, away):
            boxes[tid]["ot"] = final[tid]
    sheet = {"game_id": game_id, "form": FORM, "status": status, "home": home, "away": away,
             "teams": teams, "running": running, "lines": lines, "boxes": boxes}
    if notes:
        sheet["notes"] = notes
    sheet["checked_by"] = checked_by
    return sheet


def _fill_quarters(fts, baskets, ends, rng):
    """A running score that lands exactly on each quarter end. fts: jersey ->
    made free throws (1 point each); baskets: jersey -> field-goal points, given
    out in 2s and 3s. Random tries until every point is placed.
    Returns {total: jersey number}."""
    for _ in range(5000):
        ft, fg = dict(fts), dict(baskets)
        order, total = [], 0
        for end in ends:
            while total < end:
                options = [(1, n) for n, c in ft.items() if c and total + 1 <= end]
                options += [(v, n) for n, b in fg.items() for v in (2, 2, 3)
                            if v <= b and b - v != 1 and total + v <= end]
                if not options:
                    break
                v, n = rng.choice(options)
                if v == 1:
                    ft[n] -= 1
                else:
                    fg[n] -= v
                total += v
                order.append((total, n))
            if total != end:
                break
        else:
            if not any(ft.values()) and not any(fg.values()):
                return {t: n for t, n in order}
    raise ValueError(f"can't fit the scores into quarters ending {ends}")


def dump(sheet):
    """The sheet as compact YAML, in the documented key order."""
    def scalar(v):
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        s = str(v)
        if re.match(r"^[A-Za-z][\w .'-]*$", s) and s not in ("null", "true", "false", "yes", "no", "on", "off"):
            return s
        return json.dumps(s)

    def flow(d):
        return "{" + ", ".join(f"{k}: {scalar(v)}" for k, v in d.items()) + "}"

    out = []
    for key in ("game_id", "form", "status", "home", "away", "scorekeeper"):
        if key in sheet:
            out.append(f"{key}: {scalar(sheet[key])}")
    out.append("teams:")
    for tid, t in sheet["teams"].items():
        out.append(f"  {tid}:")
        out.append("    players:")
        out += [f"      - {flow(r)}" for r in t["players"]]
    for key in ("running", "lines", "boxes"):
        if key not in sheet:
            continue
        out.append(f"{key}:")
        for tid, v in sheet[key].items():
            if isinstance(v, dict):
                out.append(f"  {tid}: " + flow(v))
            else:
                out.append(f"  {tid}: [" + ", ".join(map(str, v)) + "]")
    for key in ("notes", "review"):
        if sheet.get(key):
            out.append(f"{key}:")
            out += [f"  - {flow(n)}" for n in sheet[key]]
    if "checked_by" in sheet:
        out.append(f"checked_by: {scalar(sheet['checked_by'])}")
    return "\n".join(out) + "\n"
