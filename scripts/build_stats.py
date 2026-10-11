#!/usr/bin/env python3
"""Compute league stats from data/<season>/ into _data/computed/<season>/.

Reads the hand-edited source files described in data/CLAUDE.md, checks them,
and writes JSON that the Jekyll templates read:

  _data/computed/seasons.json
  _data/computed/active.json               which season the site shows, and which are listed in the archive
  _data/computed/<season>/teams.json       team names, short codes and colour slots, keyed by id
  _data/computed/<season>/standings.json   regular-season table
  _data/computed/<season>/players.json     per-player season totals, keyed by id
  _data/computed/<season>/leaders.json     ranked PPG, points and FT% lists
  _data/computed/<season>/rankings.json    one row per player for the Stats page: totals,
                                           every rank, and points by game day
  _data/computed/<season>/games.json       box scores, keyed by game_id
  _data/computed/<season>/game_logs.json   each player's games, keyed by id
  _data/computed/<season>/schedule.json    weeks, byes, latest and next week
  _data/computed/<season>/playoffs.json    playoff games and totals (kept apart)

It also writes small stub pages for Jekyll (see write_stubs): _games/, _players/,
_teams/ and _archive/ (git-ignored, rewritten every run), and, if
`score_sheet_links: true` in _config.yml, copies score sheet photos to sheets/.
It writes the real season's calendar files to calendar/ too (see calendars.py).

If any check fails, every problem is printed and nothing is written.

Usage:
  python scripts/build_stats.py              # check and write
  python scripts/build_stats.py --check      # check only (writes nothing)
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

import calendars
import sheet_rules

ROOT = Path(__file__).resolve().parent.parent

# Ranking minimums, set per season in data/seasons.yml; these are the defaults.
#   ft_min_attempts  free throws attempted to be ranked for FT %
#   ppg_min_games    games played to be ranked for points per game, capped at
#                    the games the player's team has played so far (so early in
#                    the season everyone who has played is ranked)
FT_MIN_ATTEMPTS = 10
PPG_MIN_GAMES = 0
SEASON_MINIMUMS = {"ppg_min_games": PPG_MIN_GAMES, "ft_min_attempts": FT_MIN_ATTEMPTS}
SCHEDULE_COLUMNS = ["game_id", "date", "time", "gym", "home", "away", "type", "week", "status", "round"]
# The last two columns are optional (leave them out, or out from the end):
#   status  blank (the game goes ahead) or "cancelled"
#   round   a playoff round's name as the league writes it, e.g. "Semifinal (G42)"
GAME_STATUSES = ("", "cancelled")
# Optional per-player fouls in a game file, as on the score sheet: 5 personal
# foul boxes and 2 technical (T) boxes. Personal fouls are kept but not shown.
FOUL_LIMITS = {"pf": sheet_rules.MAX_FOULS, "tech": sheet_rules.MAX_TECH}
# Flagrant fouls (from the sheet's Notes) are optional too. A flagrant is also a
# personal foul, so a player's flagrant count can't be more than their pf.
# Like technicals, the site counts them for the whole season, playoffs included.
# Games are played in quarters. `quarters` in a game file holds each team's
# running total at the end of Q1-Q4, as written in the sheet's Q1-Q4 boxes.
QUARTERS = 4
# Standings points (regular season): 1 for each quarter won and 3 for winning
# the game, so 7 at most. A tied quarter gives neither team a point, and
# overtime isn't a quarter: both assumed, to be confirmed by the league.
POINTS_PER_QUARTER = 1
POINTS_PER_WIN = 3
# A playoff game whose teams aren't known yet names them like the printed
# schedule does: TBD, a standings place (1st to 5th), or the winner/loser of a game.
PLACEHOLDER_RE = re.compile(r"^(TBD|[1-9](st|nd|rd|th)|(Winner|Loser) G\d+)$")
GAME_TYPES = ("regular", "playoff")
SHEET_EXTENSIONS = (".jpg", ".jpeg", ".png", ".heic", ".pdf")
TEAM_ID_RE = re.compile(r"^[a-z]{2}$")
# first name, hyphen, last initial (or more of the last name, e.g. kevin-mo, to
# tell two "Kevin M."s apart), then an optional number: dave-m, mike-r2, kevin-mo
PLAYER_ID_RE = re.compile(r"^[a-z]+(?:-[a-z]+)*-[a-z]+[0-9]*$")
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
MINUS = "−"
DASH = "—"
TIEBREAK_NOTE = (
    "[placeholder] The league hasn't set tiebreakers yet. "
    "Teams level on points are ranked by head-to-head record, then point differential."
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


def quarter_points(game):
    """Points each team scored in each quarter, from the running totals in
    `quarters`, plus overtime points (0 when there was no overtime)."""
    out = {}
    for tid, totals in game["quarters"].items():
        prev, per = 0, []
        for total in totals:
            per.append(total - prev)
            prev = total
        out[tid] = {"quarters": per, "ot": game["final"][tid] - totals[-1]}
    return out


def quarters_won(game):
    """{team: quarters won} for one game. A tied quarter counts for neither."""
    qp = quarter_points(game)
    home, away = game["home"], game["away"]
    won = {home: 0, away: 0}
    for h, a in zip(qp[home]["quarters"], qp[away]["quarters"]):
        if h > a:
            won[home] += 1
        elif a > h:
            won[away] += 1
    return won


def standings_points(game):
    """{team: standings points} for one game: 1 per quarter won, 3 for the win."""
    won = quarters_won(game)
    home, away = game["home"], game["away"]
    winner = home if game["final"][home] > game["final"][away] else away
    return {tid: won[tid] * POINTS_PER_QUARTER + (POINTS_PER_WIN if tid == winner else 0) for tid in won}


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


PLACEHOLDER = "[placeholder]"


def _valid_display(display):
    """'First L.' — a first name, a space, one capital letter and a full stop.
    The literal "[placeholder]" is also allowed, for rows waiting to be filled in."""
    if display == PLACEHOLDER:
        return True
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
        season["sample"] = bool(season.get("sample", False))
        for key, default in SEASON_MINIMUMS.items():
            value = season.setdefault(key, default)
            if not _is_count(value):
                problems.append(f"{where} ({season['id']}): {key} should be a whole number, 0 or more")
        if season["current"] and season["sample"]:
            problems.append(f"{where}: '{season['id']}' is both current and sample; "
                            "the sample season should never be the current one")
    valid = [s for s in seasons if isinstance(s, dict)]
    ids = {s.get("id") for s in valid}
    stand_ins = {}
    for s in valid:
        target = s.get("stands_in_for")
        if target is None:
            continue
        if not s.get("sample"):
            problems.append(f"{path}: season '{s.get('id')}' has stands_in_for but is not marked sample: true")
        if target not in ids:
            problems.append(f"{path}: season '{s.get('id')}' stands_in_for '{target}', which is not a season in this file")
        if target in stand_ins:
            problems.append(f"{path}: both '{stand_ins[target]}' and '{s.get('id')}' stand in for '{target}'")
        stand_ins[target] = s.get("id")
    current = [s for s in valid if s.get("current")]
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
    numbers_taken = {}   # (team, number) -> player id, for regular (non-sub) players
    for i, player in enumerate(raw):
        where = f"{path}: player #{i + 1}"
        if not isinstance(player, dict):
            problems.append(f"{where}: should be a mapping")
            continue
        pid = player.get("id")
        if not isinstance(pid, str) or not PLAYER_ID_RE.match(pid):
            problems.append(f"{where}: id {pid!r} should look like 'dave-m', 'mike-r2' or 'kevin-mo'")
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
        number = player.get("number")
        if number is not None:
            # optional jersey number, 0 to 99 ("00" in quotes); printed on the score sheets
            text = str(number).strip()
            if isinstance(number, bool) or not re.fullmatch(r"\d{1,2}", text):
                problems.append(f"{where} ({pid}): number {number!r} should be a jersey number from 0 to 99")
            else:
                player["number"] = text
                if not player["sub"]:
                    key = (player.get("team"), text)
                    if key in numbers_taken:
                        problems.append(f"{where} ({pid}): number {text} is already {numbers_taken[key]}'s on "
                                        f"team {player.get('team')}")
                    numbers_taken[key] = pid
        players[pid] = player
    # Two players on one team with the same "First L." are told apart by jersey
    # number (on the site and on the score sheet), so both need one.
    same = {}
    for pid, p in players.items():
        same.setdefault((p.get("team"), p.get("display")), []).append(pid)
    for (team, display), pids in same.items():
        if len(pids) > 1 and display != PLACEHOLDER:
            missing = [pid for pid in pids if players[pid].get("number") is None]
            if missing:
                problems.append(f"{path}: {', '.join(pids)} on team {team} are all \"{display}\"; give each a "
                                f"jersey `number` so the site and the score sheet can tell them apart "
                                f"(missing: {', '.join(missing)})")
    return players


def load_schedule(season_dir, teams, problems):
    path = season_dir / "schedule.csv"
    schedule = {}
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames not in (SCHEDULE_COLUMNS, SCHEDULE_COLUMNS[:-1], SCHEDULE_COLUMNS[:-2]):
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
        gtype = row["type"].strip()
        if gtype not in GAME_TYPES:
            problems.append(f"{where} ({gid}): type {gtype!r} should be regular or playoff")
        for side, tid in (("home", home), ("away", away)):
            if tid in teams:
                continue
            if gtype == "playoff" and PLACEHOLDER_RE.match(tid):
                continue   # not known yet: TBD, 2nd, Winner G41...
            hint = " (a playoff game may also say TBD, a place like 2nd, or Winner G41)" if gtype == "playoff" else ""
            problems.append(f"{where} ({gid}): {side} team {tid!r} is not in teams.yml{hint}")
        if home == away and home != "TBD":
            problems.append(f"{where} ({gid}): a team can't play itself")
        try:
            week = int(row["week"])
        except ValueError:
            problems.append(f"{where} ({gid}): week {row['week']!r} should be a number")
            continue
        status = (row.get("status") or "").strip().lower()
        if status not in GAME_STATUSES:
            problems.append(f"{where} ({gid}): status {row['status']!r} should be blank or cancelled")
        for tid in (home, away):
            if status == "cancelled":
                break   # a cancelled game doesn't stop a team playing a make-up that day
            if tid not in teams:
                continue
            key = (tid, date)
            if key in team_dates and gtype == "regular":
                problems.append(f"{where} ({gid}): {tid} already plays on {date} ({team_dates[key]})")
            team_dates[key] = gid
        schedule[gid] = {
            "game_id": gid,
            "date": date,
            "time": time,
            "gym": row["gym"].strip() or None,   # blank: use the season's gym
            "home": home,
            "away": away,
            "type": gtype,
            "week": week,
            "cancelled": status == "cancelled",
            "round": (row.get("round") or "").strip() or None,
            "teams_known": home in teams and away in teams,
        }
    return schedule


def load_games(season_dir, teams, players, schedule, problems, warnings=None):
    """Every finished game: data/<season>/games/*.yml, digital copies of the
    paper score sheets (see data/CLAUDE.md). scripts/sheet_rules.py checks each
    one and works out the lines; its errors become problems here, its warnings
    are passed on. Drafts (data/<season>/drafts/) are never read."""
    games = {}
    games_dir = season_dir / "games"
    paths = sorted(games_dir.glob("*.yml")) + sorted(games_dir.glob("*.yaml"))
    ctx = {"folder": "games", "teams": teams, "players": players, "schedule": schedule}
    for path in paths:
        sheet = _read_yaml(path, problems)
        if sheet is None:
            continue
        game, found = sheet_rules.check(sheet, {**ctx, "stem": path.stem})
        for p in found:
            where = f"{path}: {p['at']}" if p["at"] else f"{path}"
            if p["level"] == "error":
                problems.append(f"{where}: {p['message']}")
            elif warnings is not None:
                warnings.append(f"{where}: {p['message']}")
        if game is not None:
            games[game["game_id"]] = game
    return games


def find_sheet(season_dir, gid):
    """The score sheet photo for a game, or None."""
    for ext in SHEET_EXTENSIONS:
        path = season_dir / "sheets" / f"{gid}{ext}"
        if path.exists():
            return path
    return None


def load_season(data_dir, season_id, gym=None, minimums=None):
    """Load and check one season. Raises DataError listing every problem.
    `gym` is the season's default gym (from seasons.yml), used when a
    schedule row leaves its gym blank. `minimums` holds the season's
    ppg_min_games and ft_min_attempts (defaults: SEASON_MINIMUMS)."""
    problems = []
    season_dir = data_dir / season_id
    teams = load_teams(season_dir, problems)
    players = load_players(season_dir, teams, problems)
    schedule = load_schedule(season_dir, teams, problems)
    warnings = []
    games = load_games(season_dir, teams, players, schedule, problems, warnings)
    if problems:
        raise DataError(problems)
    for gid, game in games.items():
        game["sheet_path"] = find_sheet(season_dir, gid)
    return {"id": season_id, "gym": gym, "teams": teams, "players": players, "schedule": schedule,
            "games": games, "publish_sheets": False, "minimums": {**SEASON_MINIMUMS, **(minimums or {})},
            "warnings": warnings}


# --------------------------------------------------------------- computation

def team_records(team_ids, games):
    """W, L, PF, PA, quarters won and standings points per team, plus
    head-to-head wins, from finished games."""
    rec = {t: {"w": 0, "l": 0, "pf": 0, "pa": 0, "qw": 0, "points": 0, "h2h": {}} for t in team_ids}
    for game in games:
        home, away = game["home"], game["away"]
        hs, as_ = game["final"][home], game["final"][away]
        for tid, n in quarters_won(game).items():
            rec[tid]["qw"] += n
        for tid, n in standings_points(game).items():
            rec[tid]["points"] += n
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
    """Order teams by standings points, then head-to-head record among teams
    level on points, then point differential, then name. Head-to-head is
    skipped when a tied team hasn't played any of the others yet.
    Returns [(team_id, tiebreak_used_or_None)]."""
    groups = {}
    for tid, r in rec.items():
        groups.setdefault(r["points"], []).append(tid)
    order = []
    for points in sorted(groups, reverse=True):
        tied = groups[points]
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
    rows = []
    for rank, (tid, tiebreak) in enumerate(order, start=1):
        r = rec[tid]
        diff = r["pf"] - r["pa"]
        rows.append({
            "rank": rank,
            "team": tid,
            "name": teams[tid]["name"],
            "short": teams[tid]["short"],
            "colour_slot": teams[tid]["colour_slot"],
            "gp": r["w"] + r["l"],
            "points": r["points"],
            "w": r["w"],
            "l": r["l"],
            "qw": r["qw"],
            "pct": fmt_pct3(r["w"], r["l"]),
            "pct_value": round_half_up(_win_frac(r["w"], r["l"]), 3),
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
            "number": p.get("number"),   # jersey number from players.yml (the roster is the truth), or None
            "gp": 0, "pts": 0, "ftm": 0, "fta": 0, "pf": 0, "season_high": None,
        }
    for game in games:
        for line in game["lines"]:
            t = totals[line["player"]]
            t["gp"] += 1
            t["pts"] += line["pts"]
            t["ftm"] += line["ftm"]
            t["fta"] += line["fta"]
            t["pf"] += line.get("pf", 0)
            t["season_high"] = max(t["season_high"] or 0, line["pts"])
    for t in totals.values():
        exact_ppg = ppg(t["pts"], t["gp"])
        exact_ft = ft_pct(t["ftm"], t["fta"])
        t["ppg"] = round_half_up(exact_ppg) if exact_ppg is not None else None
        t["ppg_display"] = fmt_decimal(exact_ppg) if exact_ppg is not None else DASH
        t["ft_pct"] = round_half_up(exact_ft) if exact_ft is not None else None
        t["ft_pct_display"] = fmt_decimal(exact_ft) if exact_ft is not None else DASH
    return totals


def add_technicals(totals, regular, playoff):
    """Technical fouls count for the whole season, playoffs included (unlike
    every other stat): adds tech, tech_playoff and tech_games to each player.
    Flagrant fouls count the same way: flagrant, flagrant_playoff, flagrant_games."""
    for t in totals.values():
        t.update(tech=0, tech_playoff=0, tech_games=0, flagrant=0, flagrant_playoff=0, flagrant_games=0)
    for games, playoffs in ((regular, False), (playoff, True)):
        for game in games:
            for line in game["lines"]:
                t = totals[line["player"]]
                for key in ("tech", "flagrant"):
                    n = line.get(key, 0)
                    if n:
                        t[key] += n
                        t[f"{key}_games"] += 1
                        if playoffs:
                            t[f"{key}_playoff"] += n


def technicals_list(totals, key="tech"):
    """Everyone with a technical foul this season (or a flagrant foul, with
    key="flagrant"), most first, then by name."""
    keys = ("id", "display", "number", "team", "team_name", "sub", key, f"{key}_playoff", f"{key}_games")
    rows = [{k: t[k] for k in keys} for t in totals.values() if t[key] > 0]
    return sorted(rows, key=lambda r: (-r[key], r["display"], r["id"]))


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


def ppg_games_needed(totals, team_games, ppg_min_games):
    """Games each player needs to be ranked for PPG: the season's minimum, or
    every game their team has played so far if that is fewer."""
    return {pid: min(ppg_min_games, team_games.get(t["team"], 0)) for pid, t in totals.items()}


def compute_leaders(totals, team_games=None, ppg_min_games=PPG_MIN_GAMES, ft_min_attempts=FT_MIN_ATTEMPTS):
    """team_games: regular-season games played by each team id."""
    played = [t for t in totals.values() if t["gp"] > 0]
    shooters = [t for t in played if t["fta"] >= ft_min_attempts]
    needed = ppg_games_needed(totals, team_games or {}, ppg_min_games)
    qualified = [t for t in played if t["gp"] >= needed[t["id"]]]
    by_ppg = _ranked(qualified, "ppg", lambda e: ppg(e["pts"], e["gp"]))
    by_pts = _ranked(played, "pts", lambda e: Fraction(e["pts"]))
    by_ft = _ranked(shooters, "ft_pct", lambda e: ft_pct(e["ftm"], e["fta"]))
    for e in by_ppg:
        e["value_display"] = e["ppg_display"]
    for e in by_pts:
        e["value_display"] = str(e["pts"])
    for e in by_ft:
        e["value_display"] = e["ft_pct_display"]
    return {
        "ft_min_attempts": ft_min_attempts,
        "ppg_min_games": ppg_min_games,
        "players_with_games": len(played),
        "ppg": by_ppg,
        "points": by_pts,
        "ft_pct": by_ft,
    }


def compute_rankings(season, totals, leaders, logs, needed=None):
    """One row per player who has played, in points-per-game order (players
    not yet ranked for PPG last), with all three ranks, their position in each
    ordering, and their regular-season points by game day. The Stats page
    sorts, filters and expands these. needed: games each player needs to be
    ranked for PPG (ppg_games_needed)."""
    teams = season["teams"]
    pos = {
        "ppg": {e["id"]: (i, e["rank"]) for i, e in enumerate(leaders["ppg"])},
        "pts": {e["id"]: (i, e["rank"]) for i, e in enumerate(leaders["points"])},
        "ft": {e["id"]: (i, e["rank"]) for i, e in enumerate(leaders["ft_pct"])},
    }
    unranked = sorted(
        (t for t in totals.values() if t["gp"] > 0 and t["id"] not in pos["ppg"]),
        key=lambda t: (-ppg(t["pts"], t["gp"]), -t["pts"], t["display"], t["id"]),
    )
    rows = []
    for pid in [e["id"] for e in leaders["ppg"]] + [t["id"] for t in unranked]:
        t = totals[pid]
        team = teams[t["team"]]
        games = [
            {"week": g["week"], "pts": g["pts"], "game_id": g["game_id"]}
            for g in logs[pid] if g["type"] == "regular"
        ]
        if games:
            games[-1]["latest"] = True
        row = {
            "id": pid,
            "display": t["display"],
            "number": t["number"],
            "sub": t["sub"],
            "team": t["team"],
            "team_name": t["team_name"],
            "team_short": team["short"],
            "colour_slot": team["colour_slot"],
            "gp": t["gp"],
            "pts": t["pts"],
            "ppg": t["ppg"],
            "ppg_display": t["ppg_display"],
            "ftm": t["ftm"],
            "fta": t["fta"],
            "ft_pct": t["ft_pct"],
            "ft_pct_display": t["ft_pct_display"],
            "season_high": t["season_high"],
            "qualifies_ft": pid in pos["ft"],
            "qualifies_ppg": pid in pos["ppg"],
            "ppg_games_needed": (needed or {}).get(pid, 0),
            "games": games,
        }
        for key in ("ppg", "pts", "ft"):
            order, rank = pos[key].get(pid, (None, None))
            row[f"order_{key}"] = order
            row[f"rank_{key}"] = rank
        rows.append(row)
    return rows


def game_summary(game, sched_row, season):
    teams, players = season["teams"], season["players"]
    home, away = game["home"], game["away"]
    final = game["final"]
    qp, qwon = quarter_points(game), quarters_won(game)
    spoints = standings_points(game) if game["type"] == "regular" else {home: None, away: None}
    by_team = {}
    for tid in (home, away):
        lines = [
            {
                "player": l["player"],
                "display": players[l["player"]]["display"],
                "sub": players[l["player"]]["sub"],
                "number": players[l["player"]].get("number"),
                "pts": l["pts"], "ftm": l["ftm"], "fta": l["fta"],
                "pf": l.get("pf", 0), "tech": l.get("tech", 0), "flagrant": l.get("flagrant", 0),
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
            "quarters": qp[tid]["quarters"],      # points scored in Q1-Q4
            "ot": qp[tid]["ot"] if game.get("ot") else None,
            "quarters_won": qwon[tid],
            "standings_points": spoints[tid],     # None for playoff games
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
        "gym": sched_row["gym"] or season.get("gym"),
        "home": home,
        "away": away,
        "winner": home if final[home] > final[away] else away,
        "ot": bool(game.get("ot")),
        "home_team": by_team[home],
        "away_team": by_team[away],
        "top": [
            {"player": l["player"], "display": l["display"], "number": l["number"], "team": l["team"], "pts": l["pts"]}
            for l in all_lines if l["pts"] == top_pts
        ],
        # Only set when score sheet links are switched on in _config.yml and the photo exists
        "sheet": f"sheets/{game['sheet_path'].name}" if season.get("publish_sheets") and game.get("sheet_path") else None,
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
                    "pf": line.get("pf", 0),
                    "tech": line.get("tech", 0),
                    "flagrant": line.get("flagrant", 0),
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
                "gym": r["gym"] or season.get("gym"),
                "home": r["home"],
                "away": r["away"],
                # names to show: the team's name, or the placeholder (TBD, 2nd, Winner G41)
                "home_name": teams[r["home"]]["name"] if r["home"] in teams else r["home"],
                "away_name": teams[r["away"]]["name"] if r["away"] in teams else r["away"],
                "round": r["round"],
                "teams_known": r["teams_known"],
                "played": played,
                "cancelled": r["cancelled"],
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
            "cancelled": all(g["cancelled"] for g in games),
            "type": "regular" if regular else "playoff",
            "date": rows[0]["date"].isoformat(),
            "date_display": fmt_date(rows[0]["date"]),
            # done: every game played or cancelled (the week moves to Results)
            "played": all(g["played"] or g["cancelled"] for g in games),
            "gyms": list(dict.fromkeys(g["gym"] for g in games if g["gym"])),
            "games": games,
            "byes": sorted((t for t in teams if t not in playing), key=lambda t: teams[t]["name"]) if regular else [],
        })
    played_weeks = [w["week"] for w in out if any(g["played"] for g in w["games"])]
    upcoming = [w["week"] for w in out if not w["played"]]
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
    add_technicals(totals, regular, playoff)
    team_games = {tid: 0 for tid in season["teams"]}
    for g in regular:
        team_games[g["home"]] += 1
        team_games[g["away"]] += 1
    minimums = season.get("minimums", SEASON_MINIMUMS)
    leaders = compute_leaders(totals, team_games, minimums["ppg_min_games"], minimums["ft_min_attempts"])
    needed = ppg_games_needed(totals, team_games, minimums["ppg_min_games"])
    leaders["through_week"] = through_week
    leaders["technicals"] = technicals_list(totals)
    leaders["flagrants"] = technicals_list(totals, "flagrant")
    team_info = {
        tid: {"id": tid, "name": t["name"], "short": t["short"], "colour_slot": t["colour_slot"]}
        for tid, t in season["teams"].items()
    }
    logs = compute_game_logs(season, summaries)
    return {
        "teams.json": team_info,
        "standings.json": standings,
        "players.json": totals,
        "leaders.json": leaders,
        "rankings.json": compute_rankings(season, totals, leaders, logs, needed),
        "games.json": summaries,
        "game_logs.json": logs,
        "schedule.json": compute_schedule(season, summaries),
        "playoffs.json": playoffs,
    }


# ---------------------------------------------------------------------- main

STUB_DIRS = ("_games", "_players", "_teams", "_archive")


def read_config(path):
    """The two settings this script needs from _config.yml (missing file: defaults)."""
    try:
        with open(path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}
    return config if isinstance(config, dict) else {}


def choose_active(seasons, sample_mode):
    """The season every page shows: the current one, or while sample mode is on
    the sample season that stands in for it."""
    current = next(s for s in seasons if s["current"])
    if sample_mode:
        stand_in = next((s for s in seasons if s.get("stands_in_for") == current["id"]), None)
        if stand_in:
            return stand_in
    return current


def archive_seasons(seasons, active, sample_mode):
    """Seasons the archive lists (newest first, as in seasons.yml): the active
    one, every past season, and other sample seasons only in sample mode. The
    real season and its sample stand-in never both appear."""
    listed = []
    for s in seasons:
        if s["id"] == active["id"]:
            listed.append(s)
        elif s["current"] or s.get("stands_in_for"):
            continue
        elif s["sample"] and not sample_mode:
            continue
        else:
            listed.append(s)
    return listed


def _front_matter(**fields):
    body = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items())
    return f"---\n{body}\n---\n"


def write_stubs(root, active, listed, outputs):
    """Write one tiny Jekyll page per game, player, team and archive season.

    A stub is only front matter (season, id, title, description). The layouts read
    everything else from _data/computed. Games and archive pages exist for
    every listed season (game ids start with their date, so they never clash);
    players and teams only for the active season, because ids like `dave-m`
    repeat across seasons. The folders are git-ignored and wiped each run, so
    a removed game can't leave an orphan page behind."""
    for name in STUB_DIRS:
        shutil.rmtree(root / name, ignore_errors=True)

    def put(folder, name, **fields):
        folder_path = root / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        (folder_path / f"{name}.md").write_text(_front_matter(**fields), encoding="utf-8")

    count = 0
    for season in listed:
        files = outputs[season["id"]]
        label = season["label"]
        for gid, game in files["games.json"].items():
            home, away = game["home_team"], game["away_team"]
            year = game["date"][:4]
            # The date keeps titles unique: the same two teams meet more than once a season.
            title = f"{home['name']} vs {away['name']}, {game['date_display']}, {year}"
            when = "Playoffs" if game["type"] == "playoff" else f"Week {game['week']}"
            description = (f"Box score: {home['name']} {home['score']}, {away['name']} {away['score']} "
                           f"on {game['date_display']}, {year} ({when}). Points and free throws for every player.")
            put("_games", gid, season=season["id"], game_id=gid, title=title, description=description)
            count += 1
        description = f"The {label} season: standings, playoff results and scoring leaders."
        put("_archive", season["id"], season=season["id"], title=f"{label} season", description=description)
        count += 1
    files = outputs[active["id"]]
    label = active["label"]
    for pid, player in files["players.json"].items():
        description = (f"{player['display']}, {player['team_name']}: points, points per game and free throws, "
                       f"game by game, for the {label} season.")
        put("_players", pid, season=active["id"], player_id=pid, title=player["display"], description=description)
        count += 1
    for tid, team in files["teams.json"].items():
        description = f"{team['name']}: record, roster, results and upcoming games for the {label} season."
        put("_teams", tid, season=active["id"], team_id=tid, title=team["name"], description=description)
        count += 1
    return count


def copy_sheets(root, listed, loaded):
    """Copy score sheet photos of listed seasons to <root>/sheets/ so Jekyll
    publishes them. Only called when `score_sheet_links: true`."""
    target = root / "sheets"
    shutil.rmtree(target, ignore_errors=True)
    copied = 0
    for season in listed:
        for game in loaded[season["id"]]["games"].values():
            photo = game.get("sheet_path")
            if photo:
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(photo, target / photo.name)
                copied += 1
    return copied


def build(data_dir, out_dir, write=True, config=None, root=None):
    """Check every season, then (if all pass) replace out_dir with fresh JSON.

    config: the settings from _config.yml (sample_data, score_sheet_links).
    root:   the site folder to write stub pages and sheets into; None writes
            only the JSON."""
    config = config or {}
    sample_mode = bool(config.get("sample_data"))
    publish_sheets = bool(config.get("score_sheet_links"))
    problems = []
    seasons = load_seasons(data_dir, problems)
    if problems:
        raise DataError(problems)

    outputs, loaded_seasons, summary = {}, {}, []
    for s in seasons:
        try:
            loaded = load_season(data_dir, s["id"], gym=s.get("gym"),
                                 minimums={k: s[k] for k in SEASON_MINIMUMS})
        except DataError as exc:
            problems.extend(exc.problems)
            continue
        loaded["publish_sheets"] = publish_sheets
        loaded_seasons[s["id"]] = loaded
        outputs[s["id"]] = compute_season(loaded)
        played = len(loaded["games"])
        week = outputs[s["id"]]["standings.json"]["through_week"]
        progress = f"through week {week}" if week else "no games played yet"
        flag = " (sample data)" if s.get("sample") else ""
        summary.append(f"{s['id']}{flag}: {len(loaded['teams'])} teams, {len(loaded['players'])} players, "
                       f"{played} games played, {progress}")
        summary += [f"  warning: {w.replace(str(ROOT) + '/', '')}" for w in loaded["warnings"]]
    if problems:
        raise DataError(problems)

    active = choose_active(seasons, sample_mode)
    listed = archive_seasons(seasons, active, sample_mode)
    # Game pages live at /games/<game_id>/, so ids must be unique among the listed seasons.
    owner = {}
    for s in listed:
        for gid in outputs[s["id"]]["games.json"]:
            if gid in owner:
                problems.append(f"game_id '{gid}' is used in both '{owner[gid]}' and '{s['id']}'; "
                                "game ids must be unique across seasons shown on the site")
            owner[gid] = s["id"]
    if problems:
        raise DataError(problems)
    # Calendars always carry the real (current) season, even in sample mode.
    current = next(s for s in seasons if s["current"])
    site_url = str(config.get("url") or "").rstrip("/") + str(config.get("baseurl") or "").rstrip("/")
    mode = "sample mode" if active.get("sample") else "real season"
    summary.append(f"Site shows: {active['id']} ({mode}); archive lists {', '.join(s['id'] for s in listed)}")

    if write:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".computed-", dir=out_dir.parent))
        try:
            _write_json(tmp / "seasons.json", [dict(s) for s in seasons])
            _write_json(tmp / "active.json", {
                "season": active["id"],
                "sample_mode": bool(active.get("sample")),
                "archive": [s["id"] for s in listed],
            })
            for sid, files in outputs.items():
                for name, data in files.items():
                    _write_json(tmp / sid / name, data)
            if root is not None:
                cal = calendars.write_calendars(root, current, outputs[current["id"]]["schedule.json"],
                                                outputs[current["id"]]["teams.json"], site_url)
                cal["games"] = sum(len(w["games"]) for w in outputs[current["id"]]["schedule.json"]["weeks"])
                _write_json(tmp / "calendars.json", cal)
            if out_dir.exists():
                shutil.rmtree(out_dir)
            tmp.rename(out_dir)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp)
        if root is not None:
            summary.append(f"Wrote {write_stubs(root, active, listed, outputs)} stub pages")
            summary.append(f"Wrote calendars for {current['id']} ({len(outputs[current['id']]['teams.json'])} teams "
                           "and the league) to calendar/")
            n_games, n_drafts = write_entry_data(root, data_dir, active, loaded_seasons[active["id"]], config)
            summary.append(f"Wrote the entry page's data for {active['id']} ({n_games} games, "
                           f"{n_drafts} drafts) to enter/data/")
            if publish_sheets:
                summary.append(f"Copied {copy_sheets(root, listed, loaded_seasons)} score sheet photos")
            else:
                shutil.rmtree(root / "sheets", ignore_errors=True)
    return summary


def write_entry_data(root, data_dir, season, loaded, config):
    """What the score-sheet entry page (/enter/) needs, for the season the site
    shows, into enter/data/ (git-ignored, rewritten every build):
      season.json  teams, every player (id, "First L.", team, number, sub) and
                   the schedule, plus where the season's files live on GitHub
      index.json   the game ids with a final file, and every draft with its
                   number of review flags
      <season>/games/*.yml, <season>/drafts/*.yml
                   copies of the files, so the page can still load them when
                   GitHub's API is out of reach (they're as of this build)
    Returns (games, drafts) counts."""
    out = root / "enter" / "data"
    shutil.rmtree(out, ignore_errors=True)
    sid = season["id"]
    src = data_dir / sid
    games, drafts = [], []
    for kind, bucket in (("games", games), ("drafts", drafts)):
        folder = src / kind
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.yml")):
            dest = out / sid / kind / path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            if kind == "games":
                bucket.append(path.stem)
            else:
                try:
                    review = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("review") or []
                except (yaml.YAMLError, AttributeError):
                    review = []
                bucket.append({"game_id": path.stem, "flags": len(review) if isinstance(review, list) else 0})
    teams = {tid: {"id": tid, "name": t["name"], "short": t["short"], "slot": t.get("colour_slot")} for tid, t in loaded["teams"].items()}
    players = {pid: {"id": pid, "display": p["display"], "team": p["team"], "sub": p["sub"],
                     "number": p.get("number")} for pid, p in loaded["players"].items()}
    schedule = {gid: {"game_id": gid, "date": r["date"].isoformat(), "date_display": fmt_date(r["date"]),
                      "time": r["time"], "home": r["home"], "away": r["away"], "type": r["type"],
                      "week": r["week"], "cancelled": r["cancelled"], "teams_known": r["teams_known"],
                      "round": r["round"]}
                for gid, r in sorted(loaded["schedule"].items(), key=lambda kv: (kv[1]["date"], kv[0]))}
    _write_json(out / "season.json", {
        "season": sid, "label": season.get("label", sid), "sample": bool(season.get("sample")),
        "repo": config.get("github_repo"), "branch": config.get("github_branch", "main"),
        "teams": teams, "players": players, "schedule": schedule,
    })
    built = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    _write_json(out / "index.json", {"season": sid, "built": built, "games": games, "drafts": drafts})
    return len(games), len(drafts)


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
        fh.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="source data folder")
    parser.add_argument("--out", type=Path, default=ROOT / "_data" / "computed", help="output folder")
    parser.add_argument("--config", type=Path, default=ROOT / "_config.yml", help="the site's _config.yml")
    parser.add_argument("--root", type=Path, default=ROOT, help="site folder that gets the stub pages")
    parser.add_argument("--check", action="store_true", help="check the data without writing anything")
    args = parser.parse_args(argv)
    try:
        summary = build(args.data, args.out, write=not args.check, config=read_config(args.config), root=args.root)
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
