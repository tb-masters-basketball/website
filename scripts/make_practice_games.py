#!/usr/bin/env python3
"""Practice score sheets for testing /record-game: four made-up games from the
sample season, each as

    answer.yml         the game file: what a perfect transcription gives
    filled-<layout>.pdf  the score sheet, filled in "by hand" from answer.yml
    empty-<layout>.pdf   the same sheet before the game: rosters and game id
                         printed, nothing written in

People copy each filled sheet onto its empty one by hand; photos of those are
what /record-game is tested on, and its draft is compared with answer.yml.
Everything is fake (the sample season's teams and players) and written into
tests/fixtures/record-game/<game_id>/. Same output every run; anything else
in those folders (photos of the hand-copied sheets) is left alone.

    python scripts/make_practice_games.py

Each game tests something different:
    2026-12-17-g1  portrait Letter   an ordinary game, a player not ticked Here, an and-one
    2026-12-17-g2  portrait Letter   overtime (tied after Q4)
    2027-01-07-g1  landscape Letter  a flagrant foul in Notes and a technical
    2027-01-07-g2  landscape Letter  a sub written in by hand who scores
"""
import random
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "scoresheet"))
import build_stats  # noqa: E402
import sheet_rules  # noqa: E402

SEASON = ROOT / "data" / "sample-2026-27"
OUT = ROOT / "tests" / "fixtures" / "record-game"
HEADER = "# Practice game from scripts/make_practice_games.py. Made up; the answer key for /record-game.\n"

# game_id, orientation, what it tests
GAMES = [
    ("2026-12-17-g1", "portrait", "plain"),
    ("2026-12-17-g2", "portrait", "overtime"),
    ("2027-01-07-g1", "landscape", "flagrant"),
    ("2027-01-07-g2", "landscape", "sub"),
]
SCOREKEEPERS = ["Pat S.", "Lee M.", "Sam P.", "Chris D."]


def season():
    problems = []
    teams = build_stats.load_teams(SEASON, problems)
    players = build_stats.load_players(SEASON, teams, problems)
    schedule = build_stats.load_schedule(SEASON, teams, problems)
    assert not problems, problems
    return teams, players, schedule


def jersey(p):
    """A player's number as a game file holds it: 23, or "00" kept as text."""
    n = p.get("number")
    if n is None:
        return None
    n = str(n)
    return int(n) if n.isdigit() and (n == "0" or not n.startswith("0")) else n


def printed_roster(players, tid):
    """The regular players in the order the score sheet prints them: by jersey number."""
    regs = [p for pid, p in players.items() if p["team"] == tid and not p["sub"]]
    return sorted(regs, key=lambda p: (p.get("number") is None, int(p["number"]) if p.get("number") is not None else 0,
                                       p["display"]))


def split(rng, total, n=4):
    """Running totals at the end of each of n quarters, roughly even."""
    weights = [rng.uniform(0.8, 1.2) for _ in range(n)]
    per = [int(total * w / sum(weights)) for w in weights]
    per[-1] += total - sum(per)
    return [sum(per[:i + 1]) for i in range(n)]


def lines_for(rng, roster, absent):
    out = []
    for p in roster:
        if p["id"] in absent:
            continue
        fta = rng.choice([0, 0, 1, 2, 2, 3, 4])
        ftm = rng.randint(0, fta)
        pts = ftm + rng.choice([0, 2, 4, 5, 6, 7, 8, 9, 10, 12])
        out.append({"player": p["id"], "num": jersey(p), "pts": pts, "ftm": ftm, "fta": fta,
                    "pf": rng.choice([0, 1, 1, 2, 2, 3])})
    return out


def make_game(gid, kind, keeper, teams, players, schedule):
    rng = random.Random(f"practice-{gid}")
    row = schedule[gid]
    home, away = row["home"], row["away"]
    rosters = {tid: printed_roster(players, tid) for tid in (home, away)}
    absent = {rosters[home][-1]["id"]} if kind == "plain" else set()
    lines = {tid: lines_for(rng, rosters[tid], absent) for tid in (home, away)}
    sub = None
    if kind == "sub":
        sub = next(p for pid, p in players.items() if p["team"] == away and p["sub"])
        lines[away].append({"player": sub["id"], "num": jersey(sub), "pts": 6, "ftm": 2, "fta": 3, "pf": 2})
    if kind == "flagrant":
        lines[away][1].update(pf=max(2, lines[away][1]["pf"]), flagrant=1)
        lines[home][2]["tech"] = 1
    totals = {tid: sum(x["pts"] for x in lines[tid]) for tid in (home, away)}
    if totals[home] == totals[away]:
        lines[home][0]["pts"] += 2
        totals[home] += 2
    final = None
    if kind == "overtime":
        tied = min(totals.values()) - rng.randint(3, 6)
        quarters = {tid: split(rng, tied) for tid in (home, away)}
        final = dict(totals)
    else:
        quarters = {tid: split(rng, totals[tid]) for tid in (home, away)}
    # the plain game must have an and-one: try running-score orders until one does
    for salt in range(200):
        sheet = sheet_rules.build_sheet(gid, home, away, quarters, lines, random.Random(f"practice-sheet-{gid}-{salt}"),
                                        checked_by="Lee M.", final=final)
        if kind != "plain" or has_and_one(sheet["running"][home]):
            break
    else:
        raise SystemExit(f"{gid}: no running score with an and-one")
    # The rows as on the paper: the printed roster in order (absent players
    # not ticked), then any sub written in on the next blank row.
    for tid in (home, away):
        by_id = {r["player"]: r for r in sheet["teams"][tid]["players"]}
        rows = [by_id.get(p["id"], {"player": p["id"], "num": jersey(p), "here": False}) for p in rosters[tid]]
        if sub and tid == away:
            rows.append(by_id[sub["id"]])
        sheet["teams"][tid]["players"] = rows
    for n in sheet.get("notes", []):
        n["text"] = "elbow to the face on a rebound"
    ordered = {"game_id": gid, "form": sheet["form"], "status": "final", "home": home, "away": away,
               "scorekeeper": keeper}
    ordered.update({k: v for k, v in sheet.items() if k not in ordered})
    return ordered


def has_and_one(run):
    """A basket then a free throw by the same player straight after: a jump of 2
    then a jump of 1, both beside the same number."""
    totals = [0] + sorted(run)
    return any(b - a == 2 and c - b == 1 and run[b] == run[c] for a, b, c in zip(totals, totals[1:], totals[2:]))


def check(sheet, teams, players, schedule):
    game, problems = sheet_rules.check(sheet, {"stem": sheet["game_id"], "folder": "games", "teams": teams,
                                               "players": players, "schedule": schedule})
    assert game is not None and not problems, problems
    return game


def main():
    teams, players, schedule = season()
    for (gid, orient, kind), keeper in zip(GAMES, SCOREKEEPERS):
        sheet = make_game(gid, kind, keeper, teams, players, schedule)
        game = check(sheet, teams, players, schedule)
        folder = OUT / gid
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.pdf"):                # only what this script makes: photos stay
            old.unlink()
        (folder / "answer.yml").write_text(HEADER + sheet_rules.dump(sheet), encoding="utf-8")
        layout = f"{orient}-letter"
        tmp = folder / "tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        common = [sys.executable, str(ROOT / "scripts" / "scoresheet" / "scoresheet.py"), "--data", str(SEASON),
                  "--orient", orient, "--size", "letter", "--out", str(tmp)]
        subprocess.run(common + ["--fill", str(folder / "answer.yml")], check=True, capture_output=True)
        subprocess.run(common + ["--game", gid, "--per-game"], check=True, capture_output=True)
        made = sorted(tmp.glob("*.pdf"))
        for pdf in made:
            name = f"filled-{layout}.pdf" if "filled" in pdf.name else f"empty-{layout}.pdf"
            pdf.rename(folder / name)
        tmp.rmdir()
        t = {tid: teams[tid]["name"] for tid in (sheet["home"], sheet["away"])}
        print(f"{gid} ({layout}, {kind}): {t[sheet['home']]} {game['final'][sheet['home']]}, "
              f"{t[sheet['away']]} {game['final'][sheet['away']]}{' (OT)' if game['ot'] else ''}")
    print(f"Wrote {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    sys.exit(main())
