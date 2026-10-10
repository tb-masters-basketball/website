#!/usr/bin/env python3
"""Generate the fake sample seasons: data/sample-2026-27/ (the stand-in for the
current season) and data/sample-2025-26/ (a short past season for the archive).

The numbers shown in docs/mockups/ are fixed here (standings, the top seven
scorers, Rob K.'s points by week, the free-throw leaders and the week 8 and 9
games). Everything else is filled in at random, with a fixed seed so the output
is the same every run, and kept below those numbers so the leaderboards match
the mockups.

Delete data/sample-2026-27/ and data/sample-2025-26/ (and their entries in
data/seasons.yml) once real games exist.

Usage: python scripts/make_sample_season.py
"""

import datetime as dt
import math
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_stats  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SEASON = "sample-2026-27"
OUT = ROOT / "data" / SEASON
PAST_SEASON = "sample-2025-26"
PAST_OUT = ROOT / "data" / PAST_SEASON

# id, name, short, colour slot (--mb-team-N), light hex, dark hex (from brand.css)
TEAMS = [
    ("pa", "Port Arthur", "PA", 1, "#C8102E", "#E8394F"),
    ("cr", "Current River", "CR", 2, "#1F6FB5", "#4D8FE0"),
    ("wf", "Westfort", "WF", 3, "#2E8B57", "#3FB27F"),
    ("lh", "Lakehead", "LH", 4, "#F2A900", "#F2B630"),
    ("fw", "Fort William", "FW", 5, "#6B3FA0", "#9B6FD6"),
]

# Nine regulars and one sub per team (the sub is last). 50 players in all,
# matching "Showing 7 of 50" on the Stats mockup.
ROSTERS = {
    "pa": ["Dave M.", "Greg T.", "Kevin H.", "Doug W.", "Terry N.", "Brian O.", "Gord F.", "Marc L.", "Wayne D.", "Ian C."],
    "cr": ["Rob K.", "Chris B.", "Scott A.", "Jason P.", "Tom G.", "Darren V.", "Pete S.", "Luc B.", "Randy J.", "Neil F."],
    "wf": ["Steve P.", "Jeff S.", "Mark D.", "Rick L.", "Jamie C.", "Trevor M.", "Al K.", "Derek H.", "Shawn T.", "Matt W."],
    "lh": ["Mike R.", "Dan H.", "Brad E.", "Craig S.", "Todd B.", "Pat O.", "Andre G.", "Lorne K.", "Sean M.", "Jon V."],
    "fw": ["Paul L.", "Bill C.", "Tim R.", "Glen A.", "Barry S.", "Ken W.", "Joe P.", "Ray D.", "Nick T.", "Carl M."],
}

# Mockup standings: W-L, PF, PA.
STANDINGS = {
    "pa": (6, 1, 482, 421),
    "cr": (5, 2, 470, 440),
    "wf": (3, 3, 401, 398),
    "lh": (2, 4, 389, 420),
    "fw": (0, 6, 342, 405),
}

# Pairings in a 5-team rotation, keyed by the team with the bye.
PAIRS_BY_BYE = {
    "wf": [("pa", "lh"), ("cr", "fw")],
    "cr": [("wf", "pa"), ("lh", "fw")],
    "pa": [("fw", "wf"), ("cr", "lh")],
    "fw": [("cr", "pa"), ("lh", "wf")],
    "lh": [("wf", "cr"), ("pa", "fw")],
}
# Byes per five-week cycle. Weeks 1-8 give the mockup's games played (PA and CR
# one bye, the rest two), CR's week 4 bye (Rob K.'s bars skip W4), WF's week 8
# bye and CR's week 9 bye.
BYE_CYCLES = [
    ["lh", "fw", "pa", "cr", "wf"],   # weeks 1-5
    ["fw", "lh", "wf", "cr", "pa"],   # weeks 6-10
    ["pa", "wf", "lh", "fw", "cr"],   # weeks 11-15
    ["cr", "lh", "wf", "pa", "fw"],   # weeks 16-20
]
FIRST_NIGHT = dt.date(2026, 10, 15)          # week 8 is Thu Dec 3
SKIP_DATES = {dt.date(2026, 12, 24), dt.date(2026, 12, 31)}
TIMES = ["19:00", "20:15"]
GYM = ""                       # blank: the season's gym (St. Pat's) is used
WEEKS_PLAYED = 8

# Winners of the games played each week.
WINNERS = {
    1: ["cr", "pa"], 2: ["cr", "wf"], 3: ["wf", "cr"], 4: ["lh", "pa"],
    5: ["pa", "cr"], 6: ["pa", "lh"], 7: ["wf", "pa"], 8: ["pa", "cr"],
}
FIXED_SCORES = {(8, 0): {"pa": 71, "lh": 64}, (8, 1): {"cr": 66, "fw": 52}}

# Season points for the mockup's top seven; they play every game their team plays.
FIXED_POINTS = {
    "dave-m": 141, "rob-k": 128, "steve-p": 104, "mike-r": 96,
    "greg-t": 99, "paul-l": 82, "chris-b": 88,
}
ROB_K_BY_WEEK = {1: 16, 2: 21, 3: 14, 5: 22, 6: 17, 7: 19, 8: 19}
# Lines fixed in single games: the data/CLAUDE.md example and the week 8 tops.
FIXED_LINES = {
    (8, "dave-m"): (24, 6, 7),
    (8, "greg-t"): (12, 2, 2),
}
# Free throws (made, attempted) for the mockup's FT leaders and Rob K.
FIXED_FT = {"steve-p": (18, 20), "jeff-s": (11, 13), "dave-m": (22, 27), "rob-k": (30, 41)}
ALWAYS_PLAYS = set(FIXED_POINTS) | set(FIXED_FT)

OTHER_PPG_CAP = 12.0          # keeps everyone else below Chris B.'s 12.6
OTHER_FT_CAP = 0.80           # keeps everyone else below Dave M.'s 81.5%


class Retry(Exception):
    pass


def winner_of(week, game):
    return next(t for t in WINNERS[week] if t in (game["home"], game["away"]))


def pid_for(display):
    first, last = display.split(" ")
    return f"{first.lower()}-{last[0].lower()}"


def build_schedule():
    weeks, date = [], FIRST_NIGHT
    for cycle, byes in enumerate(BYE_CYCLES):
        for bye in byes:
            while date in SKIP_DATES:
                date += dt.timedelta(days=7)
            pairs = PAIRS_BY_BYE[bye]
            if cycle % 2 == 0:               # alternate home and away by cycle
                pairs = [(b, a) for a, b in reversed(pairs)]
            week = len(weeks) + 1
            games = [
                {"game_id": f"{date.isoformat()}-g{i + 1}", "date": date, "time": TIMES[i],
                 "home": h, "away": a, "week": week}
                for i, (h, a) in enumerate(pairs)
            ]
            weeks.append(games)
            date += dt.timedelta(days=7)
    return weeks


def solve_scores(rng, played):
    """Pick scores for every played game that hit each team's PF and PA."""
    scores = {}
    for key, game in played.items():
        if key in FIXED_SCORES:
            scores[key] = dict(FIXED_SCORES[key])
            continue
        win = winner_of(key[0], game)
        lose = game["away"] if win == game["home"] else game["home"]
        w = rng.randint(58, 74)
        scores[key] = {win: w, lose: w - rng.randint(2, 14)}

    pf = {t: 0 for t in STANDINGS}
    pa = {t: 0 for t in STANDINGS}
    for s in scores.values():
        (a, sa), (b, sb) = s.items()
        pf[a] += sa; pa[a] += sb; pf[b] += sb; pa[b] += sa

    def term(t):
        return abs(pf[t] - STANDINGS[t][2]) + abs(pa[t] - STANDINGS[t][3])

    # Simulated annealing: nudge one score at a time, sometimes accepting a
    # worse total so the search doesn't get stuck.
    free = [k for k in scores if k not in FIXED_SCORES]
    current = sum(term(t) for t in STANDINGS)
    steps = 60000
    for i in range(steps):
        if current == 0:
            return scores
        temp = max(0.05, 3.0 * (1 - i / steps))
        key = rng.choice(free)
        team, opp = rng.sample(list(scores[key]), 2)
        step = rng.choice([-2, -1, 1, 2])
        win = winner_of(key[0], played[key])
        lose = opp if team == win else team
        scores[key][team] += step
        if not (42 <= scores[key][team] <= 84 and scores[key][win] > scores[key][lose]):
            scores[key][team] -= step
            continue
        before = term(team) + term(opp)
        pf[team] += step
        pa[opp] += step
        delta = term(team) + term(opp) - before
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            current += delta
        else:
            scores[key][team] -= step
            pf[team] -= step
            pa[opp] -= step
    raise Retry("scores")


def split_total(rng, total, slots, low, high):
    """Random whole numbers in [low, high] for each slot, summing to total."""
    if not slots:
        if total:
            raise Retry("split")
        return {}
    mean = total / len(slots)
    vals = {s: max(low, min(high, round(mean + rng.gauss(0, mean * 0.25)))) for s in slots}
    for _ in range(10000):
        gap = total - sum(vals.values())
        if gap == 0:
            return vals
        s = rng.choice(slots)
        nv = vals[s] + (1 if gap > 0 else -1)
        if low <= nv <= high:
            vals[s] = nv
    raise Retry("split")


def generate(seed):
    rng = random.Random(seed)
    weeks = build_schedule()
    played = {}
    for week in range(1, WEEKS_PLAYED + 1):
        for i, g in enumerate(weeks[week - 1]):
            played[(week, i)] = g
    scores = solve_scores(rng, played)

    players = {}
    for tid, names in ROSTERS.items():
        for i, display in enumerate(names):
            players[pid_for(display)] = {"display": display, "team": tid, "sub": i == len(names) - 1}

    # Which games each team played, and who turned up.
    team_games = {t: [k for k, g in played.items() if t in (g["home"], g["away"])] for t in STANDINGS}
    present = {}
    for tid, keys in team_games.items():
        roster = [pid_for(d) for d in ROSTERS[tid]]
        regulars, sub = roster[:-1], roster[-1]
        sub_games = set(rng.sample(keys, rng.randint(1, 2)))
        for key in keys:
            here = [p for p in regulars if p in ALWAYS_PLAYS or rng.random() < 0.85]
            if key in sub_games:
                here.append(sub)
            present[(key, tid)] = here
        for p in regulars:      # every regular plays at least once
            if not any(p in present[(k, tid)] for k in keys):
                present[(rng.choice(keys), tid)].append(p)

    # Points for the fixed players, game by game.
    pts = {}
    for pid, total in FIXED_POINTS.items():
        keys = team_games[players[pid]["team"]]
        if pid == "rob-k":
            for key in keys:
                pts[(key, pid)] = ROB_K_BY_WEEK[key[0]]
            continue
        fixed = {k: FIXED_LINES[(k[0], pid)][0] for k in keys if (k[0], pid) in FIXED_LINES}
        rest = [k for k in keys if k not in fixed]
        mean = (total - sum(fixed.values())) / len(rest)
        split = split_total(rng, total - sum(fixed.values()), rest, max(4, int(mean - 9)), int(mean + 9))
        pts.update({(k, pid): v for k, v in {**fixed, **split}.items()})

    # Everyone else shares what's left of each team score, weighted by skill.
    skill = {p: (0.5 if players[p]["sub"] else rng.uniform(0.6, 2.2)) for p in players}
    for (key, tid), here in present.items():
        fixed_sum = sum(pts.get((key, p), 0) for p in here if p in FIXED_POINTS)
        left = scores[key][tid] - fixed_sum
        others = [p for p in here if p not in FIXED_POINTS]
        if left < 8 or not others:
            raise Retry("not enough points left for the bench")
        share = {p: 0 for p in others}
        while left > 0:
            chunk = min(left, rng.choice([2, 2, 2, 3, 1]))
            p = rng.choices(others, weights=[skill[o] for o in others])[0]
            share[p] += chunk
            left -= chunk
        for p, v in share.items():
            pts[(key, p)] = v

    # Free throws.
    ft = {}
    for pid, (made, att) in FIXED_FT.items():
        keys = [k for k in team_games[players[pid]["team"]]]
        fixed = {k: FIXED_LINES[(k[0], pid)][1:] for k in keys if (k[0], pid) in FIXED_LINES}
        rest = [k for k in keys if k not in fixed]
        att_left = att - sum(a for _, a in fixed.values())
        made_left = made - sum(m for m, _ in fixed.values())
        atts = split_total(rng, att_left, rest, 0, 12)
        misses = split_total(rng, att_left - made_left, rest, 0, 4)
        for k in rest:
            if misses[k] > atts[k]:
                raise Retry("ft misses")
            ft[(k, pid)] = (atts[k] - misses[k], atts[k])
        ft.update({(k, pid): v for k, v in fixed.items()})
    for (key, tid), here in present.items():
        for p in here:
            if (key[0], p) in FIXED_LINES:
                ft[(key, p)] = FIXED_LINES[(key[0], p)][1:]
            if (key, p) in ft:
                continue
            fta = rng.choice([0, 0, 0, 1, 2, 2, 2, 3, 4]) if pts[(key, p)] else 0
            ftm = sum(rng.random() < 0.62 for _ in range(fta))
            ft[(key, p)] = (ftm, fta)
    for (key, p), (ftm, fta) in list(ft.items()):     # make every line possible
        points = pts[(key, p)]
        if ftm > points or points - ftm == 1:
            if p in FIXED_FT:
                raise Retry("fixed ft line impossible")
            if points == 1:
                ftm = 1
            elif ftm > points:
                ftm = points
            else:
                ftm -= 1
            ft[(key, p)] = (ftm, max(fta, ftm))
    # Nobody else may sneak onto the FT leaderboard top three.
    for p in players:
        if p in FIXED_FT:
            continue
        lines = [k for k in ft if k[1] == p]
        while True:
            m = sum(ft[k][0] for k in lines)
            a = sum(ft[k][1] for k in lines)
            if a < build_stats.FT_MIN_ATTEMPTS or m / a < OTHER_FT_CAP:
                break
            k = rng.choice(lines)
            ft[k] = (ft[k][0], ft[k][1] + 1)

    return weeks, played, scores, players, present, pts, ft


def fouls(game_id, pid):
    """Made-up personal fouls (0-5) and technicals (0-2, rare) for one player in
    one game, from a Random of their own so no other sample number changes."""
    r = random.Random(f"fouls-{game_id}-{pid}")
    pf = r.choices(range(6), weights=[14, 24, 26, 20, 11, 5])[0]
    tech = 1 if r.random() < 0.025 else 0
    flagrant = 1 if pf and r.random() < 0.012 else 0      # a flagrant is also one of the pf
    return f", pf: {pf}" + (f", tech: {tech}" if tech else "") + (f", flagrant: {flagrant}" if flagrant else "")


def quarters_line(game_id, scores, salt=0):
    """`quarters:` for one game: each team's running total at the end of Q1-Q4,
    from its final score split into four quarters of roughly equal size. A
    Random of its own (plus `salt`, so main() can try another split), so no
    other sample number changes. No overtime: Q4 is the final score."""
    r = random.Random(f"quarters-{salt}-{game_id}")
    parts = []
    for tid, total in scores.items():
        weights = [r.uniform(0.75, 1.25) for _ in range(build_stats.QUARTERS)]
        per = [int(total * w / sum(weights)) for w in weights]
        per[r.randrange(len(per))] += total - sum(per)
        running = [sum(per[:i + 1]) for i in range(len(per))]
        parts.append(f"{tid}: [{', '.join(map(str, running))}]")
    return "quarters: {" + ", ".join(parts) + "}\n"


def jersey_numbers(tid, pids):
    """Made-up jersey numbers, unique within the team. A Random of their own, so
    adding them changes none of the sample season's other numbers."""
    picks = random.Random(f"jersey-{tid}").sample(range(0, 56), len(pids))
    return dict(zip(pids, picks))


def write_teams(out, header):
    with open(out / "teams.yml", "w", encoding="utf-8") as fh:
        fh.write(header)
        fh.write("# colour_slot picks --mb-team-N in brand/css/brand.css; the hex values are a record only.\n")
        for tid, name, short, slot, light, dark in TEAMS:
            fh.write(f"- id: {tid}\n  name: {name}\n  short: {short}\n  colour_slot: {slot}\n"
                     f"  colour_light: \"{light}\"\n  colour_dark: \"{dark}\"\n")


def write_files(weeks, played, scores, players, present, pts, ft, salt=0):
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "games").mkdir(parents=True)
    (OUT / "sheets").mkdir()
    (OUT / "sheets" / ".gitkeep").write_text("")
    header = "# Sample data from scripts/make_sample_season.py. Not real.\n"

    write_teams(OUT, header)

    with open(OUT / "players.yml", "w", encoding="utf-8") as fh:
        fh.write(header)
        for tid, *_ in TEAMS:
            team_ids = [pid for pid, p in players.items() if p["team"] == tid]
            numbers = jersey_numbers(tid, team_ids)
            for pid in team_ids:
                p = players[pid]
                fh.write(f"- {{id: {pid}, display: {p['display']}, team: {tid}, "
                         f"sub: {'true' if p['sub'] else 'false'}, number: {numbers[pid]}}}\n")

    with open(OUT / "schedule.csv", "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(build_stats.SCHEDULE_COLUMNS) + "\n")
        for games in weeks:
            for g in games:
                fh.write(f"{g['game_id']},{g['date']},{g['time']},{GYM},{g['home']},{g['away']},regular,{g['week']},,\n")

    for key, g in played.items():
        s = scores[key]
        lines = []
        for tid in (g["home"], g["away"]):
            here = sorted(present[(key, tid)], key=lambda p: (-pts[(key, p)], p))
            for p in here:
                m, a = ft[(key, p)]
                lines.append(f"  - {{player: {p}, team: {tid}, pts: {pts[(key, p)]}, ftm: {m}, fta: {a}"
                             f"{fouls(g['game_id'], p)}}}\n")
        with open(OUT / "games" / f"{g['game_id']}.yml", "w", encoding="utf-8") as fh:
            fh.write(header)
            fh.write(f"game_id: {g['game_id']}\ndate: {g['date']}\nhome: {g['home']}\naway: {g['away']}\n"
                     f"type: regular\nfinal: {{{g['home']}: {s[g['home']]}, {g['away']}: {s[g['away']]}}}\n")
            fh.write(quarters_line(g["game_id"], {t: s[t] for t in (g["home"], g["away"])}, salt))
            fh.write("lines:\n")
            fh.writelines(lines)


def check_against_mockups(out):
    """Raise Retry unless the computed numbers match docs/mockups/."""
    standings = {r["team"]: r for r in out["standings.json"]["teams"]}
    for tid, (w, l, pf, pa) in STANDINGS.items():
        r = standings[tid]
        if (r["w"], r["l"], r["pf"], r["pa"]) != (w, l, pf, pa):
            raise Retry(f"standings {tid}")
    order = [r["team"] for r in out["standings.json"]["teams"]]
    if order != ["pa", "cr", "wf", "lh", "fw"]:
        raise Retry("standings order")

    leaders = out["leaders.json"]
    top7 = [(e["id"], e["ppg_display"]) for e in leaders["ppg"][:7]]
    expected = [("dave-m", "20.1"), ("rob-k", "18.3"), ("steve-p", "17.3"), ("mike-r", "16.0"),
                ("greg-t", "14.1"), ("paul-l", "13.7"), ("chris-b", "12.6")]
    if top7 != expected or leaders["ppg"][7]["ppg"] > OTHER_PPG_CAP:
        raise Retry("ppg leaders")
    if leaders["players_with_games"] != 50:
        raise Retry("player count")
    ft3 = [(e["id"], e["ft_pct_display"], e["ftm"], e["fta"]) for e in leaders["ft_pct"][:3]]
    if ft3 != [("steve-p", "90.0", 18, 20), ("jeff-s", "84.6", 11, 13), ("dave-m", "81.5", 22, 27)]:
        raise Retry("ft leaders")
    rob = out["players.json"]["rob-k"]
    if (rob["ftm"], rob["fta"], rob["ft_pct_display"], rob["season_high"]) != (30, 41, "73.2", 22):
        raise Retry("rob-k")

    games = out["games.json"]
    tops = {gid: [(t["player"], t["pts"]) for t in g["top"]] for gid, g in games.items()}
    if tops["2026-12-03-g1"] != [("dave-m", 24)] or tops["2026-12-03-g2"] != [("rob-k", 19)]:
        raise Retry("week 8 tops")
    sched = out["schedule.json"]
    if sched["latest_week"] != 8 or sched["next_week"] != 9:
        raise Retry("weeks")
    wk9 = sched["weeks"][8]
    if wk9["date"] != "2026-12-10" or wk9["byes"] != ["cr"] or \
            [(g["home"], g["away"], g["time_display"]) for g in wk9["games"]] != \
            [("wf", "pa", "7:00 PM"), ("lh", "fw", "8:15 PM")]:
        raise Retry("week 9")


# ------------------------------------------------------ the sample past season

PAST_FIRST_NIGHT = dt.date(2025, 10, 16)
PAST_WEEKS = 5                      # five regular-season nights, each team has one bye
PAST_FINAL_DATE = dt.date(2026, 4, 9)
PAST_BYE_ORDER = ["lh", "wf", "fw", "pa", "cr"]
PAST_STRENGTH = {"cr": 3, "wf": 2, "pa": 1, "fw": 0, "lh": -1}     # last year's pecking order


def past_lines(rng, roster, team_points):
    """Split a team's points among the players on the sheet, with free throws."""
    regulars, sub = roster[:-1], roster[-1]
    here = [p for p in regulars if rng.random() < 0.85]
    while len(here) < 6:
        here = [p for p in regulars if rng.random() < 0.9]
    if rng.random() < 0.3:
        here.append(sub)
    skill = {p: rng.uniform(0.5, 2.2) for p in here}
    points = {p: 0 for p in here}
    left = team_points
    while left > 0:
        chunk = min(left, rng.choice([2, 2, 2, 3, 1]))
        points[rng.choices(here, weights=[skill[p] for p in here])[0]] += chunk
        left -= chunk
    lines = []
    for p in sorted(here, key=lambda p: (-points[p], p)):
        fta = rng.choice([0, 0, 1, 2, 2, 3, 4]) if points[p] else 0
        ftm = min(points[p], sum(rng.random() < 0.65 for _ in range(fta)))
        if points[p] - ftm == 1:                  # one point can't come from field goals
            ftm = 1 if points[p] == 1 else ftm - 1
        lines.append((p, points[p], ftm, max(fta, ftm)))
    return lines


def write_past_season():
    """A short, believable past season: 5 regular nights and a playoff final."""
    rng = random.Random(2025)
    if PAST_OUT.exists():
        shutil.rmtree(PAST_OUT)
    (PAST_OUT / "games").mkdir(parents=True)
    (PAST_OUT / "sheets").mkdir()
    (PAST_OUT / "sheets" / ".gitkeep").write_text("")
    header = "# Sample data from scripts/make_sample_season.py. Not real.\n"
    write_teams(PAST_OUT, header)

    rosters = {tid: [pid_for(d) for d in names[:8] + names[-1:]] for tid, names in ROSTERS.items()}
    display = {pid_for(d): d for names in ROSTERS.values() for d in names}
    with open(PAST_OUT / "players.yml", "w", encoding="utf-8") as fh:
        fh.write(header)
        for tid, *_ in TEAMS:
            numbers = jersey_numbers(tid, rosters[tid])
            for i, pid in enumerate(rosters[tid]):
                fh.write(f"- {{id: {pid}, display: {display[pid]}, team: {tid}, "
                         f"sub: {'true' if i == len(rosters[tid]) - 1 else 'false'}, number: {numbers[pid]}}}\n")

    schedule, results = [], []          # results: (game, winner, scores)
    wins = {tid: [0, 0, 0] for tid, *_ in TEAMS}     # wins, losses, point differential
    for week in range(1, PAST_WEEKS + 1):
        date = PAST_FIRST_NIGHT + dt.timedelta(days=7 * (week - 1))
        for i, (home, away) in enumerate(PAIRS_BY_BYE[PAST_BYE_ORDER[week - 1]]):
            game = {"game_id": f"{date.isoformat()}-g{i + 1}", "date": date, "time": TIMES[i],
                    "home": home, "away": away, "week": week, "type": "regular"}
            # Stronger teams usually win, so the final standings aren't all level
            chance = 0.5 + 0.13 * (PAST_STRENGTH[home] - PAST_STRENGTH[away])
            winner = home if rng.random() < chance else away
            loser = away if winner == home else home
            top = rng.randint(58, 76)
            margin = rng.randint(2, 14)
            scores = {winner: top, loser: top - margin}
            wins[winner][0] += 1; wins[loser][1] += 1
            wins[winner][2] += margin; wins[loser][2] -= margin
            schedule.append(game); results.append((game, scores))
    # The two best records meet in the final
    seeds = sorted(wins, key=lambda t: (-wins[t][0], -wins[t][2], t))[:2]
    final = {"game_id": f"{PAST_FINAL_DATE.isoformat()}-g1", "date": PAST_FINAL_DATE, "time": TIMES[0],
             "home": seeds[0], "away": seeds[1], "week": PAST_WEEKS + 1, "type": "playoff"}
    champion = rng.choice(seeds)
    other = seeds[1] if champion == seeds[0] else seeds[0]
    top = rng.randint(60, 74)
    schedule.append(final); results.append((final, {champion: top, other: top - rng.randint(3, 9)}))

    with open(PAST_OUT / "schedule.csv", "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(build_stats.SCHEDULE_COLUMNS) + "\n")
        for g in schedule:
            fh.write(f"{g['game_id']},{g['date']},{g['time']},{GYM},{g['home']},{g['away']},{g['type']},{g['week']},,\n")
    for g, scores in results:
        lines = []
        for tid in (g["home"], g["away"]):
            for pid, pts_, ftm, fta in past_lines(rng, rosters[tid], scores[tid]):
                lines.append(f"  - {{player: {pid}, team: {tid}, pts: {pts_}, ftm: {ftm}, fta: {fta}"
                             f"{fouls(g['game_id'], pid)}}}\n")
        with open(PAST_OUT / "games" / f"{g['game_id']}.yml", "w", encoding="utf-8") as fh:
            fh.write(header)
            fh.write(f"game_id: {g['game_id']}\ndate: {g['date']}\nhome: {g['home']}\naway: {g['away']}\n"
                     f"type: {g['type']}\nfinal: {{{g['home']}: {scores[g['home']]}, {g['away']}: {scores[g['away']]}}}\n")
            fh.write(quarters_line(g["game_id"], {t: scores[t] for t in (g["home"], g["away"])}))
            fh.write("lines:\n")
            fh.writelines(lines)
    build_stats.load_season(ROOT / "data", PAST_SEASON)       # raises if any check fails
    print(f"Wrote {PAST_OUT.relative_to(ROOT)}/ ({len(results)} games, final won by {champion})")


def main():
    for seed in range(1, 500):
        try:
            result = generate(seed)
        except Retry:
            continue
        # Standings are by points (quarters won count), so try a few quarter
        # splits of the same games until the order still matches the mockups.
        for salt in range(60):
            try:
                write_files(*result, salt=salt)
                loaded = build_stats.load_season(ROOT / "data", SEASON)
                check_against_mockups(build_stats.compute_season(loaded))
            except (Retry, build_stats.DataError):
                continue
            print(f"Wrote {OUT.relative_to(ROOT)}/ (seed {seed}, quarter split {salt})")
            write_past_season()
            return 0
    print("No seed produced data matching the mockups.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
