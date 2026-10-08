#!/usr/bin/env python3
"""Compute league stats from data/<season>/ into _data/computed/<season>/.

Reads the hand-edited source files described in data/CLAUDE.md, checks them,
and writes JSON that the Jekyll templates read:

  _data/computed/seasons.json
  _data/computed/<season>/teams.json       team names, short codes and colour slots, keyed by id
  _data/computed/<season>/standings.json   regular-season table
  _data/computed/<season>/players.json     per-player season totals, keyed by id
  _data/computed/<season>/leaders.json     ranked PPG, points and FT% lists
  _data/computed/<season>/games.json       box scores, keyed by game_id
  _data/computed/<season>/game_logs.json   each player's games, keyed by id
  _data/computed/<season>/schedule.json    weeks, byes, latest and next week
  _data/computed/<season>/playoffs.json    playoff games and totals (kept apart)

If any check fails, every problem is printed and nothing is written.

Usage:
  python scripts/build_stats.py              # check and write
  python scripts/build_stats.py --check      # check only
"""

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

FT_MIN_ATTEMPTS = 10
SCHEDULE_COLUMNS = ["game_id", "date", "time", "court", "home", "away", "type", "week"]
GAME_TYPES = ("regular", "playoff")
SHEET_EXTENSIONS = (".jpg", ".jpeg", ".png", ".heic", ".pdf")
TEAM_ID_RE = re.compile(r"^[a-z]{2}$")
PLAYER_ID_RE = re.compile(r"^[a-z]+(?:-[a-z]+)*-[a-z][0-9]*$")
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
MINUS = "−"
DASH = "—"
TIEBREAK_NOTE = (
    "[placeholder] The league hasn't set tiebreakers yet. "
    "Ties are broken by head-to-head record, then point differential."
)


class DataError(Exception):
    """Raised with a list of problems found in the source data."""

    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


# ---------------------------------------------------------------- formatting

def round_half_up(value, places=1):
    """Round a number (int, Fraction, Decimal) half-up, returning a float."""
    if isinstance(value, Fraction):
        value = Decimal(value.numerator) / Decimal(value.denominator)
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP))


def fmt_decimal(value, places=1):
    return f"{round_half_up(value, places):.{places}f}"


def ppg(pts, gp):
    """Exact points per game, or None with no games."""
    return Fraction(pts, gp) if gp else None


def ft_pct(ftm, fta):
    """Exact free-throw percentage (0-100), or None with no attempts."""
    return Fraction(100 * ftm, fta) if fta else None


def fmt_pct3(wins, losses):
    """Win percentage in '.857' style; '1.000' for unbeaten, '.000' with no games."""
    games = wins + losses
    if not games:
        return ".000"
    text = f"{round_half_up(Fraction(wins, games), 3):.3f}"
    return text[1:] if text.startswith("0") else text


def games_behind(leader_w, leader_l, w, l):
    return Fraction((leader_w - w) + (l - leader_l), 2)


def fmt_gb(gb):
    if gb == 0:
        return DASH
    return str(int(gb)) if gb.denominator == 1 else f"{float(gb):.1f}"


def fmt_signed(n):
    if n > 0:
        return f"+{n}"
    if n < 0:
        return f"{MINUS}{-n}"
    return "0"


def fmt_date(d):
    """'Thu Dec 3'."""
    return f"{d:%a} {d:%b} {d.day}"


def fmt_time(t):
    """'19:00' -> '7:00 PM'."""
    hour, minute = (int(x) for x in t.split(":"))
    suffix = "AM" if hour < 12 else "PM"
    return f"{(hour % 12) or 12}:{minute:02d} {suffix}"


# ------------------------------------------------------------------- loading

def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _read_yaml(path, problems):
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        problems.append(f"{path}: file is missing")
    except yaml.YAMLError as exc:
        problems.append(f"{path}: not valid YAML ({exc})")
    return None


def _valid_display(display):
    """'First L.' — a first name, a space, one capital letter and a full stop."""
    if not isinstance(display, str) or " " not in display:
        return False
    first, last = display.rsplit(" ", 1)
    return (
        bool(first.strip())
        and all(c.isalpha() or c in " '’-." for c in first)
        and len(last) == 2
        and last[0].isalpha()
        and last[0].isupper()
        and last[1] == "."
    )


def load_seasons(data_dir, problems):
    path = data_dir / "seasons.yml"
    seasons = _read_yaml(path, problems)
    if seasons is None:
        return []
    if not isinstance(seasons, list) or not seasons:
        problems.append(f"{path}: should be a list of seasons")
        return []
    seen = set()
    for i, season in enumerate(seasons):
        where = f"{path}: season #{i + 1}"
        if not isinstance(season, dict) or not isinstance(season.get("id"), str):
            problems.append(f"{where}: needs an 'id' (the folder name)")
            continue
        if season["id"] in seen:
            problems.append(f"{where}: id '{season['id']}' is listed twice")
        seen.add(season["id"])
        if not (data_dir / season["id"]).is_dir():
            problems.append(f"{where}: folder data/{season['id']}/ does not exist")
        season.setdefault("label", season["id"])
        season["current"] = bool(season.get("current", False))
    current = [s for s in seasons if isinstance(s, dict) and s.get("current")]
    if len(current) != 1:
        problems.append(f"{path}: exactly one season must have 'current: true' (found {len(current)})")
    return [s for s in seasons if isinstance(s, dict) and isinstance(s.get("id"), str)]


def load_teams(season_dir, problems):
    path = season_dir / "teams.yml"
    raw = _read_yaml(path, problems) or []
    teams = {}
    for i, team in enumerate(raw):
        where = f"{path}: team #{i + 1}"
        if not isinstance(team, dict):
            problems.append(f"{where}: should be a mapping")
            continue
        tid = team.get("id")
        if not isinstance(tid, str) or not TEAM_ID_RE.match(tid):
            problems.append(f"{where}: id {tid!r} should be two lowercase letters")
            continue
        if tid in teams:
            problems.append(f"{where}: team id '{tid}' is listed twice")
        for key in ("name", "short"):
            if not isinstance(team.get(key), str) or not team.get(key):
                problems.append(f"{where} ({tid}): missing '{key}'")
        slot = team.get("colour_slot")
        if not (isinstance(slot, int) and 1 <= slot <= 5):
            problems.append(f"{where} ({tid}): colour_slot should be 1-5 (maps to --mb-team-N)")
        teams[tid] = team
    if not teams:
        problems.append(f"{path}: no teams found")
    return teams


def load_players(season_dir, teams, problems):
    path = season_dir / "players.yml"
    raw = _read_yaml(path, problems) or []
    players = {}
    for i, player in enumerate(raw):
        where = f"{path}: player #{i + 1}"
        if not isinstance(player, dict):
            problems.append(f"{where}: should be a mapping")
            continue
        pid = player.get("id")
        if not isinstance(pid, str) or not PLAYER_ID_RE.match(pid):
            problems.append(f"{where}: id {pid!r} should look like 'dave-m' or 'mike-r2'")
            continue
        if pid in players:
            problems.append(f"{where}: player id '{pid}' is listed twice")
        if not _valid_display(player.get("display")):
            problems.append(
                f"{where} ({pid}): display {player.get('display')!r} should be 'First L.' "
                "(never a full name)"
            )
        if player.get("team") not in teams:
            problems.append(f"{where} ({pid}): team {player.get('team')!r} is not in teams.yml")
        player["sub"] = bool(player.get("sub", False))
        players[pid] = player
    return players


def load_schedule(season_dir, teams, problems):
    path = season_dir / "schedule.csv"
    schedule = {}
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != SCHEDULE_COLUMNS:
                problems.append(f"{path}: header should be {','.join(SCHEDULE_COLUMNS)}")
                return schedule
            rows = list(reader)
    except FileNotFoundError:
        problems.append(f"{path}: file is missing")
        return schedule

    team_dates = {}
    for line_no, row in enumerate(rows, start=2):
        where = f"{path}: line {line_no}"
        gid = row["game_id"].strip()
        if not gid:
            problems.append(f"{where}: game_id is empty")
            continue
        if gid in schedule:
            problems.append(f"{where}: game_id '{gid}' appears twice")
        try:
            date = dt.date.fromisoformat(row["date"].strip())
        except ValueError:
            problems.append(f"{where} ({gid}): date {row['date']!r} should be YYYY-MM-DD")
            continue
        time = row["time"].strip()
        if not TIME_RE.match(time):
            problems.append(f"{where} ({gid}): time {time!r} should be 24-hour HH:MM")
        home, away = row["home"].strip(), row["away"].strip()
        for side, tid in (("home", home), ("away", away)):
            if tid not in teams:
                problems.append(f"{where} ({gid}): {side} team {tid!r} is not in teams.yml")
        if home == away:
            problems.append(f"{where} ({gid}): a team can't play itself")
        gtype = row["type"].strip()
        if gtype not in GAME_TYPES:
            problems.append(f"{where} ({gid}): type {gtype!r} should be regular or playoff")
        try:
            week = int(row["week"])
        except ValueError:
            problems.append(f"{where} ({gid}): week {row['week']!r} should be a number")
            continue
        for tid in (home, away):
            key = (tid, date)
            if key in team_dates and gtype == "regular":
                problems.append(f"{where} ({gid}): {tid} already plays on {date} ({team_dates[key]})")
            team_dates[key] = gid
        schedule[gid] = {
            "game_id": gid,
            "date": date,
            "time": time,
            "court": row["court"].strip() or None,   # blank when the gym has one court
            "home": home,
            "away": away,
            "type": gtype,
            "week": week,
        }
    return schedule


def load_games(season_dir, teams, players, schedule, problems):
    games = {}
    games_dir = season_dir / "games"
    paths = sorted(games_dir.glob("*.yml")) + sorted(games_dir.glob("*.yaml"))
    for path in paths:
        game = _read_yaml(path, problems)
        if game is None:
            continue
        if not isinstance(game, dict):
            problems.append(f"{path}: should be a mapping")
            continue
        before = len(problems)
        _check_game(path, game, teams, players, schedule, problems)
        if len(problems) == before:
            games[game["game_id"]] = game
    return games


def _check_game(path, game, teams, players, schedule, problems):
    gid = game.get("game_id")
    where = f"{path}"
    if gid != path.stem:
        problems.append(f"{where}: game_id {gid!r} doesn't match the file name '{path.stem}'")
        return
    row = schedule.get(gid)
    if row is None:
        problems.append(f"{where}: game_id '{gid}' has no row in schedule.csv")
        return

    date = game.get("date")
    if isinstance(date, dt.datetime):
        date = date.date()
    if not isinstance(date, dt.date):
        try:
            date = dt.date.fromisoformat(str(date))
        except ValueError:
            problems.append(f"{where}: date {game.get('date')!r} should be YYYY-MM-DD")
            date = None
    if date is not None and date != row["date"]:
        problems.append(f"{where}: date {date} doesn't match schedule.csv ({row['date']})")

    home, away = game.get("home"), game.get("away")
    for side, tid in (("home", home), ("away", away)):
        if tid not in teams:
            problems.append(f"{where}: {side} team {tid!r} is not in teams.yml")
    if (home, away) != (row["home"], row["away"]):
        problems.append(
            f"{where}: home/away {home}/{away} doesn't match schedule.csv "
            f"({row['home']}/{row['away']})"
        )
    if game.get("type") != row["type"]:
        problems.append(f"{where}: type {game.get('type')!r} doesn't match schedule.csv ({row['type']})")

    final = game.get("final")
    if not isinstance(final, dict) or set(final) != {home, away}:
        problems.append(f"{where}: final should list exactly the two teams, like {{{home}: 71, {away}: 64}}")
        return
    for tid, score in final.items():
        if not _is_count(score):
            problems.append(f"{where}: final score for {tid} should be a whole number, 0 or more")
            return
    if final[home] == final[away]:
        problems.append(f"{where}: final score is tied {final[home]}-{final[away]}")

    lines = game.get("lines")
    if not isinstance(lines, list) or not lines:
        problems.append(f"{where}: 'lines' should list each player on the sheet")
        return
    sums = {home: 0, away: 0}
    seen = set()
    for i, line in enumerate(lines, start=1):
        lw = f"{where}: line {i}"
        if not isinstance(line, dict):
            problems.append(f"{lw}: should look like {{player: dave-m, team: pa, pts: 24, ftm: 6, fta: 7}}")
            continue
        pid, tid = line.get("player"), line.get("team")
        lw = f"{lw} ({pid})"
        if pid not in players:
            problems.append(f"{lw}: player {pid!r} is not in players.yml")
        if pid in seen:
            problems.append(f"{lw}: player is listed twice in this game")
        seen.add(pid)
        if tid not in teams:
            problems.append(f"{lw}: team {tid!r} is not in teams.yml")
        elif tid not in (home, away):
            problems.append(f"{lw}: team '{tid}' isn't playing in this game")
        nums = {k: line.get(k) for k in ("pts", "ftm", "fta")}
        bad = [k for k, v in nums.items() if not _is_count(v)]
        if bad:
            problems.append(f"{lw}: {', '.join(bad)} should be whole numbers, 0 or more")
            continue
        if nums["ftm"] > nums["fta"]:
            problems.append(f"{lw}: ftm {nums['ftm']} is more than fta {nums['fta']}")
        if nums["ftm"] > nums["pts"]:
            problems.append(f"{lw}: ftm {nums['ftm']} is more than pts {nums['pts']}")
        elif nums["pts"] - nums["ftm"] == 1:
            problems.append(
                f"{lw}: pts {nums['pts']} with ftm {nums['ftm']} leaves 1 point from field goals"
            )
        if tid in sums:
            sums[tid] += nums["pts"]
    for tid in (home, away):
        if tid in final and sums[tid] != final[tid]:
            problems.append(
                f"{where}: {tid} player points add up to {sums[tid]}, but the final score is {final[tid]}"
            )


def find_sheet(season_dir, gid):
    for ext in SHEET_EXTENSIONS:
        path = season_dir / "sheets" / f"{gid}{ext}"
        if path.exists():
            return path.relative_to(season_dir.parent.parent).as_posix()
    return None


def load_season(data_dir, season_id):
    """Load and check one season. Raises DataError listing every problem."""
    problems = []
    season_dir = data_dir / season_id
    teams = load_teams(season_dir, problems)
    players = load_players(season_dir, teams, problems)
    schedule = load_schedule(season_dir, teams, problems)
    games = load_games(season_dir, teams, players, schedule, problems)
    if problems:
        raise DataError(problems)
    for gid, game in games.items():
        game["sheet"] = find_sheet(season_dir, gid)
    return {"id": season_id, "teams": teams, "players": players, "schedule": schedule, "games": games}


# --------------------------------------------------------------- computation

def team_records(team_ids, games):
    """W, L, PF, PA per team, plus head-to-head wins, from finished games."""
    rec = {t: {"w": 0, "l": 0, "pf": 0, "pa": 0, "h2h": {}} for t in team_ids}
    for game in games:
        home, away = game["home"], game["away"]
        hs, as_ = game["final"][home], game["final"][away]
        for tid, opp, own, other in ((home, away, hs, as_), (away, home, as_, hs)):
            r = rec[tid]
            r["pf"] += own
            r["pa"] += other
            won = own > other
            r["w" if won else "l"] += 1
            h = r["h2h"].setdefault(opp, [0, 0])
            h[0 if won else 1] += 1
    return rec


def _win_frac(w, l):
    return Fraction(w, w + l) if w + l else Fraction(0)


def sort_standings(rec, names):
    """Order teams by win %, then head-to-head among tied teams, then point
    differential, then name. Head-to-head is skipped when a tied team hasn't
    played any of the others yet. Returns [(team_id, tiebreak_used_or_None)]."""
    groups = {}
    for tid, r in rec.items():
        groups.setdefault(_win_frac(r["w"], r["l"]), []).append(tid)
    order = []
    for pct in sorted(groups, reverse=True):
        tied = groups[pct]
        if len(tied) == 1:
            order.append((tied[0], None))
            continue

        def h2h(tid):
            w = sum(rec[tid]["h2h"].get(o, [0, 0])[0] for o in tied if o != tid)
            l = sum(rec[tid]["h2h"].get(o, [0, 0])[1] for o in tied if o != tid)
            return _win_frac(w, l)

        def diff(tid):
            return rec[tid]["pf"] - rec[tid]["pa"]

        # Head-to-head only counts if every tied team has played the others.
        use_h2h = all(any(o in rec[t]["h2h"] for o in tied if o != t) for t in tied)
        h2h_key = h2h if use_h2h else (lambda t: Fraction(0))
        ranked = sorted(tied, key=lambda t: (-h2h_key(t), -diff(t), names[t]))
        for tid in ranked:
            same_h2h = [t for t in tied if h2h_key(t) == h2h_key(tid)]
            if len(same_h2h) == 1:
                used = "head-to-head"
            elif len([t for t in same_h2h if diff(t) == diff(tid)]) == 1:
                used = "point differential"
            else:
                used = "name"
            order.append((tid, used))
    return order


def compute_standings(season, regular_games):
    teams = season["teams"]
    names = {t: teams[t]["name"] for t in teams}
    rec = team_records(teams, regular_games)
    order = sort_standings(rec, names)
    leader = rec[order[0][0]] if order else None
    rows = []
    for rank, (tid, tiebreak) in enumerate(order, start=1):
        r = rec[tid]
        gb = games_behind(leader["w"], leader["l"], r["w"], r["l"])
        diff = r["pf"] - r["pa"]
        rows.append({
            "rank": rank,
            "team": tid,
            "name": teams[tid]["name"],
            "short": teams[tid]["short"],
            "colour_slot": teams[tid]["colour_slot"],
            "gp": r["w"] + r["l"],
            "w": r["w"],
            "l": r["l"],
            "pct": fmt_pct3(r["w"], r["l"]),
            "pct_value": round_half_up(_win_frac(r["w"], r["l"]), 3),
            "gb": float(gb),
            "gb_display": fmt_gb(gb),
            "pf": r["pf"],
            "pa": r["pa"],
            "diff": diff,
            "diff_display": fmt_signed(diff),
            "tiebreak": tiebreak,
        })
    return {"tiebreak_note": TIEBREAK_NOTE, "teams": rows}


def player_totals(players, teams, games):
    """Season totals per player id from a list of games."""
    totals = {}
    for pid, p in players.items():
        totals[pid] = {
            "id": pid,
            "display": p["display"],
            "team": p["team"],
            "team_name": teams[p["team"]]["name"],
            "sub": p["sub"],
            "gp": 0, "pts": 0, "ftm": 0, "fta": 0, "season_high": None,
        }
    for game in games:
        for line in game["lines"]:
            t = totals[line["player"]]
            t["gp"] += 1
            t["pts"] += line["pts"]
            t["ftm"] += line["ftm"]
            t["fta"] += line["fta"]
            t["season_high"] = max(t["season_high"] or 0, line["pts"])
    for t in totals.values():
        exact_ppg = ppg(t["pts"], t["gp"])
        exact_ft = ft_pct(t["ftm"], t["fta"])
        t["ppg"] = round_half_up(exact_ppg) if exact_ppg is not None else None
        t["ppg_display"] = fmt_decimal(exact_ppg) if exact_ppg is not None else DASH
        t["ft_pct"] = round_half_up(exact_ft) if exact_ft is not None else None
        t["ft_pct_display"] = fmt_decimal(exact_ft) if exact_ft is not None else DASH
    return totals


def _ranked(entries, value_key, exact):
    """Sort by exact value (high first) and give tied values the same rank."""
    entries = sorted(entries, key=lambda e: (-exact(e), -e["pts"], e["display"], e["id"]))
    out, prev, rank = [], None, 0
    for i, e in enumerate(entries, start=1):
        v = exact(e)
        if v != prev:
            rank, prev = i, v
        out.append({**e, "rank": rank, "value": e[value_key]})
    return out


def compute_leaders(totals):
    played = [t for t in totals.values() if t["gp"] > 0]
    shooters = [t for t in played if t["fta"] >= FT_MIN_ATTEMPTS]
    by_ppg = _ranked(played, "ppg", lambda e: ppg(e["pts"], e["gp"]))
    by_pts = _ranked(played, "pts", lambda e: Fraction(e["pts"]))
    by_ft = _ranked(shooters, "ft_pct", lambda e: ft_pct(e["ftm"], e["fta"]))
    for e in by_ppg:
        e["value_display"] = e["ppg_display"]
    for e in by_pts:
        e["value_display"] = str(e["pts"])
    for e in by_ft:
        e["value_display"] = e["ft_pct_display"]
    return {
        "ft_min_attempts": FT_MIN_ATTEMPTS,
        "players_with_games": len(played),
        "ppg": by_ppg,
        "points": by_pts,
        "ft_pct": by_ft,
    }


def game_summary(game, sched_row, season):
    teams, players = season["teams"], season["players"]
    home, away = game["home"], game["away"]
    final = game["final"]
    by_team = {}
    for tid in (home, away):
        lines = [
            {
                "player": l["player"],
                "display": players[l["player"]]["display"],
                "sub": players[l["player"]]["sub"],
                "pts": l["pts"], "ftm": l["ftm"], "fta": l["fta"],
            }
            for l in game["lines"] if l["team"] == tid
        ]
        lines.sort(key=lambda l: (-l["pts"], l["display"]))
        by_team[tid] = {
            "team": tid,
            "name": teams[tid]["name"],
            "short": teams[tid]["short"],
            "colour_slot": teams[tid]["colour_slot"],
            "score": final[tid],
            "won": final[tid] > final[home if tid == away else away],
            "lines": lines,
            "totals": {
                "pts": sum(l["pts"] for l in lines),
                "ftm": sum(l["ftm"] for l in lines),
                "fta": sum(l["fta"] for l in lines),
            },
        }
    all_lines = [
        {**l, "team": tid} for tid in (home, away) for l in by_team[tid]["lines"]
    ]
    top_pts = max(l["pts"] for l in all_lines)
    return {
        "game_id": game["game_id"],
        "type": game["type"],
        "week": sched_row["week"],
        "date": sched_row["date"].isoformat(),
        "date_display": fmt_date(sched_row["date"]),
        "time": sched_row["time"],
        "time_display": fmt_time(sched_row["time"]),
        "court": sched_row["court"],
        "home": home,
        "away": away,
        "winner": home if final[home] > final[away] else away,
        "home_team": by_team[home],
        "away_team": by_team[away],
        "top": [
            {"player": l["player"], "display": l["display"], "team": l["team"], "pts": l["pts"]}
            for l in all_lines if l["pts"] == top_pts
        ],
        "sheet": game.get("sheet"),
    }


def compute_game_logs(season, summaries):
    logs = {pid: [] for pid in season["players"]}
    for s in sorted(summaries.values(), key=lambda s: (s["date"], s["time"], s["game_id"])):
        for side, other in (("home_team", "away_team"), ("away_team", "home_team")):
            mine, theirs = s[side], s[other]
            for line in mine["lines"]:
                logs[line["player"]].append({
                    "game_id": s["game_id"],
                    "type": s["type"],
                    "week": s["week"],
                    "date": s["date"],
                    "date_display": s["date_display"],
                    "team": mine["team"],
                    "opponent": theirs["team"],
                    "opponent_name": theirs["name"],
                    "home": side == "home_team",
                    "result": "W" if mine["won"] else "L",
                    "score": f"{mine['score']}–{theirs['score']}",
                    "pts": line["pts"],
                    "ftm": line["ftm"],
                    "fta": line["fta"],
                })
    return logs


def compute_schedule(season, summaries):
    teams = season["teams"]
    weeks = {}
    for row in season["schedule"].values():
        weeks.setdefault(row["week"], []).append(row)
    out = []
    for week in sorted(weeks):
        rows = sorted(weeks[week], key=lambda r: (r["date"], r["time"], r["game_id"]))
        games = []
        for r in rows:
            played = r["game_id"] in summaries
            entry = {
                "game_id": r["game_id"],
                "type": r["type"],
                "date": r["date"].isoformat(),
                "date_display": fmt_date(r["date"]),
                "time": r["time"],
                "time_display": fmt_time(r["time"]),
                "court": r["court"],
                "home": r["home"],
                "away": r["away"],
                "played": played,
            }
            if played:
                s = summaries[r["game_id"]]
                entry["final"] = {r["home"]: s["home_team"]["score"], r["away"]: s["away_team"]["score"]}
                entry["winner"] = s["winner"]
            games.append(entry)
        playing = {g["home"] for g in games} | {g["away"] for g in games}
        regular = all(g["type"] == "regular" for g in games)
        out.append({
            "week": week,
            "type": "regular" if regular else "playoff",
            "date": rows[0]["date"].isoformat(),
            "date_display": fmt_date(rows[0]["date"]),
            "played": all(g["played"] for g in games),
            "games": games,
            "byes": sorted((t for t in teams if t not in playing), key=lambda t: teams[t]["name"]) if regular else [],
        })
    played_weeks = [w["week"] for w in out if any(g["played"] for g in w["games"])]
    upcoming = [w["week"] for w in out if not all(g["played"] for g in w["games"])]
    return {
        "latest_week": max(played_weeks) if played_weeks else None,
        "next_week": min(upcoming) if upcoming else None,
        "weeks": out,
    }


def compute_season(season):
    """All computed outputs for one loaded season, as {filename: data}."""
    schedule = season["schedule"]
    games = season["games"]
    summaries = {gid: game_summary(g, schedule[gid], season) for gid, g in games.items()}
    regular = [g for g in games.values() if g["type"] == "regular"]
    playoff = [g for g in games.values() if g["type"] == "playoff"]

    totals = player_totals(season["players"], season["teams"], regular)
    through_week = max((schedule[g["game_id"]]["week"] for g in regular), default=None)
    standings = compute_standings(season, regular)
    standings["through_week"] = through_week

    playoff_totals = player_totals(season["players"], season["teams"], playoff)
    playoffs = {
        "games": sorted((g["game_id"] for g in playoff), key=lambda gid: (summaries[gid]["date"], summaries[gid]["time"])),
        "players": {pid: t for pid, t in playoff_totals.items() if t["gp"] > 0},
    }
    leaders = compute_leaders(totals)
    leaders["through_week"] = through_week
    team_info = {
        tid: {"id": tid, "name": t["name"], "short": t["short"], "colour_slot": t["colour_slot"]}
        for tid, t in season["teams"].items()
    }
    return {
        "teams.json": team_info,
        "standings.json": standings,
        "players.json": totals,
        "leaders.json": leaders,
        "games.json": summaries,
        "game_logs.json": compute_game_logs(season, summaries),
        "schedule.json": compute_schedule(season, summaries),
        "playoffs.json": playoffs,
    }


# ---------------------------------------------------------------------- main

def build(data_dir, out_dir, write=True):
    """Check every season, then (if all pass) replace out_dir with fresh JSON."""
    problems = []
    seasons = load_seasons(data_dir, problems)
    if problems:
        raise DataError(problems)

    outputs, summary = {}, []
    for s in seasons:
        try:
            loaded = load_season(data_dir, s["id"])
        except DataError as exc:
            problems.extend(exc.problems)
            continue
        outputs[s["id"]] = compute_season(loaded)
        played = len(loaded["games"])
        week = outputs[s["id"]]["standings.json"]["through_week"]
        summary.append(f"{s['id']}: {len(loaded['teams'])} teams, {len(loaded['players'])} players, "
                       f"{played} games played, through week {week}")
    if problems:
        raise DataError(problems)

    if write:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".computed-", dir=out_dir.parent))
        try:
            _write_json(tmp / "seasons.json", [
                {k: v for k, v in s.items()} for s in seasons
            ])
            for sid, files in outputs.items():
                for name, data in files.items():
                    _write_json(tmp / sid / name, data)
            if out_dir.exists():
                shutil.rmtree(out_dir)
            tmp.rename(out_dir)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp)
    return summary


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
        fh.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="source data folder")
    parser.add_argument("--out", type=Path, default=ROOT / "_data" / "computed", help="output folder")
    parser.add_argument("--check", action="store_true", help="check the data without writing anything")
    args = parser.parse_args(argv)
    try:
        summary = build(args.data, args.out, write=not args.check)
    except DataError as exc:
        print(f"Data check failed: {len(exc.problems)} problem(s). Nothing was written.\n", file=sys.stderr)
        for p in exc.problems:
            print(f"  - {p.replace(str(ROOT) + '/', '')}", file=sys.stderr)
        return 1
    for line in summary:
        print(line)
    print("Checks passed." if args.check else f"Wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
