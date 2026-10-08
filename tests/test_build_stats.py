"""Tests for scripts/build_stats.py. Run: python -m unittest discover -s tests"""

import re
import shutil
import sys
import tempfile
import textwrap
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_stats as bs  # noqa: E402


class FormattingTests(unittest.TestCase):
    def test_round_half_up_not_bankers(self):
        self.assertEqual(bs.round_half_up(Fraction(4025, 100)), 40.3)   # 40.25 -> 40.3
        self.assertEqual(bs.round_half_up(Fraction(41, 2)), 20.5)
        self.assertEqual(bs.fmt_decimal(Fraction(1, 20)), "0.1")         # 0.05 -> 0.1

    def test_ppg_and_ft_pct(self):
        self.assertEqual(bs.fmt_decimal(bs.ppg(141, 7)), "20.1")
        self.assertEqual(bs.fmt_decimal(bs.ppg(96, 6)), "16.0")
        self.assertEqual(bs.fmt_decimal(bs.ft_pct(22, 27)), "81.5")
        self.assertEqual(bs.fmt_decimal(bs.ft_pct(30, 41)), "73.2")
        self.assertIsNone(bs.ppg(0, 0))
        self.assertIsNone(bs.ft_pct(0, 0))

    def test_win_pct_style(self):
        self.assertEqual(bs.fmt_pct3(6, 1), ".857")
        self.assertEqual(bs.fmt_pct3(2, 4), ".333")
        self.assertEqual(bs.fmt_pct3(0, 6), ".000")
        self.assertEqual(bs.fmt_pct3(3, 0), "1.000")
        self.assertEqual(bs.fmt_pct3(0, 0), ".000")

    def test_games_behind(self):
        self.assertEqual(bs.fmt_gb(bs.games_behind(6, 1, 6, 1)), "—")
        self.assertEqual(bs.fmt_gb(bs.games_behind(6, 1, 5, 2)), "1")
        self.assertEqual(bs.fmt_gb(bs.games_behind(6, 1, 3, 3)), "2.5")
        self.assertEqual(bs.fmt_gb(bs.games_behind(6, 1, 0, 6)), "5.5")

    def test_signed_and_dates(self):
        self.assertEqual(bs.fmt_signed(61), "+61")
        self.assertEqual(bs.fmt_signed(-31), "−31")
        self.assertEqual(bs.fmt_signed(0), "0")
        import datetime as dt
        self.assertEqual(bs.fmt_date(dt.date(2026, 12, 3)), "Thu Dec 3")
        self.assertEqual(bs.fmt_time("19:00"), "7:00 PM")
        self.assertEqual(bs.fmt_time("20:15"), "8:15 PM")
        self.assertEqual(bs.fmt_time("12:05"), "12:05 PM")

    def test_display_names(self):
        self.assertTrue(bs._valid_display("Dave M."))
        self.assertTrue(bs._valid_display("Jean-Luc B."))
        self.assertFalse(bs._valid_display("Dave Mitchell"))
        self.assertFalse(bs._valid_display("Dave M"))
        self.assertFalse(bs._valid_display("Dave"))


class SeasonFixture(unittest.TestCase):
    """A tiny three-team season written to a temp folder for each test."""

    TEAMS = """\
        - {id: aa, name: Alpha, short: AL, colour_slot: 1}
        - {id: bb, name: Bravo, short: BR, colour_slot: 2}
        - {id: cc, name: Charlie, short: CH, colour_slot: 3}
        """
    PLAYERS = """\
        - {id: al-a, display: Al A., team: aa, sub: false}
        - {id: amy-b, display: Amy B., team: aa, sub: false}
        - {id: bo-c, display: Bo C., team: bb, sub: false}
        - {id: cy-d, display: Cy D., team: cc, sub: false}
        - {id: sam-e, display: Sam E., team: bb, sub: true}
        """
    SCHEDULE = """\
        game_id,date,time,gym,home,away,type,week
        2026-10-01-g1,2026-10-01,19:00,1,aa,bb,regular,1
        2026-10-08-g1,2026-10-08,19:00,1,bb,cc,regular,2
        2026-10-15-g1,2026-10-15,19:00,1,cc,aa,regular,3
        2026-10-22-g1,2026-10-22,19:00,1,aa,bb,regular,4
        2027-04-01-g1,2027-04-01,19:00,1,aa,bb,playoff,20
        """
    GAMES = {
        "2026-10-01-g1": """\
            game_id: 2026-10-01-g1
            date: 2026-10-01
            home: aa
            away: bb
            type: regular
            final: {aa: 30, bb: 20}
            lines:
              - {player: al-a, team: aa, pts: 20, ftm: 4, fta: 5}
              - {player: amy-b, team: aa, pts: 10, ftm: 0, fta: 2}
              - {player: bo-c, team: bb, pts: 14, ftm: 6, fta: 6}
              - {player: sam-e, team: bb, pts: 6, ftm: 2, fta: 4}
            """,
        "2026-10-08-g1": """\
            game_id: 2026-10-08-g1
            date: 2026-10-08
            home: bb
            away: cc
            type: regular
            final: {bb: 25, cc: 22}
            lines:
              - {player: bo-c, team: bb, pts: 25, ftm: 5, fta: 5}
              - {player: cy-d, team: cc, pts: 22, ftm: 2, fta: 3}
            """,
        "2026-10-15-g1": """\
            game_id: 2026-10-15-g1
            date: 2026-10-15
            home: cc
            away: aa
            type: regular
            final: {cc: 40, aa: 21}
            lines:
              - {player: cy-d, team: cc, pts: 40, ftm: 10, fta: 12}
              - {player: al-a, team: aa, pts: 21, ftm: 3, fta: 3}
            """,
        "2027-04-01-g1": """\
            game_id: 2027-04-01-g1
            date: 2027-04-01
            home: aa
            away: bb
            type: playoff
            final: {aa: 50, bb: 10}
            lines:
              - {player: al-a, team: aa, pts: 50, ftm: 0, fta: 0}
              - {player: bo-c, team: bb, pts: 10, ftm: 0, fta: 0}
            """,
    }

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.season = self.data / "test"
        (self.season / "games").mkdir(parents=True)
        self.write("seasons.yml", "- {id: test, label: Test, current: true}\n", base=self.data)
        self.write("teams.yml", self.TEAMS)
        self.write("players.yml", self.PLAYERS)
        self.write("schedule.csv", self.SCHEDULE)
        for gid, body in self.GAMES.items():
            self.write(f"games/{gid}.yml", body)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, text, base=None):
        path = (base or self.season) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")

    def edit_game(self, gid, old, new):
        path = self.season / "games" / f"{gid}.yml"
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new))

    def compute(self):
        return bs.compute_season(bs.load_season(self.data, "test"))

    def assertProblem(self, fragment):
        with self.assertRaises(bs.DataError) as ctx:
            bs.load_season(self.data, "test")
        joined = "\n".join(ctx.exception.problems)
        self.assertIn(fragment, joined)


class StatsTests(SeasonFixture):
    def test_player_totals(self):
        p = self.compute()["players.json"]
        self.assertEqual((p["al-a"]["gp"], p["al-a"]["pts"]), (2, 41))   # playoff excluded
        self.assertEqual(p["al-a"]["ppg_display"], "20.5")
        self.assertEqual(p["al-a"]["season_high"], 21)
        self.assertEqual(p["sam-e"]["pts"], 6)                           # subs count as players
        self.assertEqual(p["bo-c"]["ft_pct_display"], "100.0")

    def test_teams_lookup(self):
        teams = self.compute()["teams.json"]
        self.assertEqual(teams["aa"], {"id": "aa", "name": "Alpha", "short": "AL", "colour_slot": 1})
        self.assertEqual(set(teams), {"aa", "bb", "cc"})

    def test_rankings_rows(self):
        rows = self.compute()["rankings.json"]
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(set(by_id), {"al-a", "amy-b", "bo-c", "cy-d", "sam-e"})
        # played, in points-per-game order: Cy 31.0, Al 20.5, Bo 19.5, Amy 10.0, Sam 6.0
        self.assertEqual([r["id"] for r in rows], ["cy-d", "al-a", "bo-c", "amy-b", "sam-e"])
        al = by_id["al-a"]
        self.assertEqual((al["rank_ppg"], al["order_ppg"], al["rank_pts"]), (2, 1, 2))
        self.assertEqual((al["gp"], al["pts"], al["ppg_display"], al["season_high"]), (2, 41, "20.5", 21))
        # only Cy (15 FTA) and Bo (11 FTA) clear the 10-attempt minimum
        self.assertEqual([r["id"] for r in rows if r["qualifies_ft"]], ["cy-d", "bo-c"])  # PPG order
        self.assertEqual((by_id["bo-c"]["rank_ft"], by_id["bo-c"]["order_ft"]), (1, 0))
        self.assertIsNone(al["rank_ft"])
        self.assertIsNone(al["order_ft"])

    def test_rankings_game_days_are_regular_season_only(self):
        al = next(r for r in self.compute()["rankings.json"] if r["id"] == "al-a")
        # the 50-point playoff game (week 20) is not a game day here
        self.assertEqual([(g["week"], g["pts"]) for g in al["games"]], [(1, 20), (3, 21)])
        self.assertTrue(al["games"][-1]["latest"])
        self.assertNotIn("latest", al["games"][0])

    def test_standings_exclude_playoffs(self):
        teams = self.compute()["standings.json"]["teams"]
        alpha = next(t for t in teams if t["team"] == "aa")
        self.assertEqual((alpha["w"], alpha["l"], alpha["pf"], alpha["pa"]), (1, 1, 51, 60))

    def test_three_way_tie(self):
        # All three teams are 1-1 and 1-1 against each other, so point
        # differential decides: CC +16, BB -7, AA -9.
        teams = self.compute()["standings.json"]["teams"]
        self.assertEqual([t["team"] for t in teams], ["cc", "bb", "aa"])
        self.assertEqual({t["tiebreak"] for t in teams}, {"point differential"})
        self.assertTrue(all(t["gb_display"] == "—" for t in teams))

    def test_head_to_head_two_teams(self):
        names = {"aa": "A", "bb": "B", "cc": "C"}
        rec = {
            "aa": {"w": 2, "l": 1, "pf": 90, "pa": 70, "h2h": {"bb": [0, 1]}},
            "bb": {"w": 2, "l": 1, "pf": 70, "pa": 80, "h2h": {"aa": [1, 0]}},
            "cc": {"w": 0, "l": 3, "pf": 60, "pa": 70, "h2h": {}},
        }
        order = bs.sort_standings(rec, names)
        self.assertEqual(order, [("bb", "head-to-head"), ("aa", "head-to-head"), ("cc", None)])

    def test_head_to_head_skipped_if_tied_teams_have_not_met(self):
        names = {"aa": "A", "bb": "B"}
        rec = {
            "aa": {"w": 1, "l": 0, "pf": 50, "pa": 40, "h2h": {"cc": [1, 0]}},
            "bb": {"w": 1, "l": 0, "pf": 70, "pa": 40, "h2h": {"dd": [1, 0]}},
        }
        self.assertEqual(bs.sort_standings(rec, names), [("bb", "point differential"), ("aa", "point differential")])

    def test_ft_leaders_need_ten_attempts(self):
        ft = self.compute()["leaders.json"]["ft_pct"]
        self.assertEqual([e["id"] for e in ft], ["bo-c", "cy-d"])   # 11 and 15 FTA
        self.assertEqual(ft[0]["value_display"], "100.0")

    def test_ppg_leaders_and_ties_share_rank(self):
        ppg = self.compute()["leaders.json"]["ppg"]
        self.assertEqual(ppg[0]["id"], "cy-d")          # 62 / 2 = 31.0
        self.assertEqual(ppg[0]["value_display"], "31.0")
        self.write("games/2026-10-15-g1.yml", self.GAMES["2026-10-15-g1"].replace(
            "{cc: 40, aa: 21}", "{cc: 19, aa: 21}").replace("pts: 40, ftm: 10, fta: 12", "pts: 19, ftm: 1, fta: 2"))
        ppg = self.compute()["leaders.json"]["ppg"]
        top = [(e["id"], e["rank"]) for e in ppg[:3]]
        # Al A. 41/2 and Cy D. 41/2 tie at 20.5 and share rank 1; Bo C. 39/2 is 3rd.
        self.assertEqual(top, [("al-a", 1), ("cy-d", 1), ("bo-c", 3)])

    def test_game_summary_and_logs(self):
        out = self.compute()
        g = out["games.json"]["2026-10-01-g1"]
        self.assertEqual(g["winner"], "aa")
        self.assertEqual(g["top"], [{"player": "al-a", "display": "Al A.", "team": "aa", "pts": 20}])
        self.assertEqual(g["home_team"]["totals"], {"pts": 30, "ftm": 4, "fta": 7})
        log = out["game_logs.json"]["al-a"]
        self.assertEqual([(e["week"], e["result"], e["pts"]) for e in log],
                         [(1, "W", 20), (3, "L", 21), (20, "W", 50)])
        self.assertEqual(log[1]["score"], "21–40")

    def test_schedule_byes_and_next_week(self):
        sched = self.compute()["schedule.json"]
        self.assertEqual(sched["latest_week"], 20)
        self.assertEqual(sched["next_week"], 4)
        self.assertEqual(sched["weeks"][0]["byes"], ["cc"])
        self.assertEqual(sched["weeks"][-1]["byes"], [])          # playoff weeks have no byes
        self.assertEqual(sched["weeks"][0]["games"][0]["gym"], "1")
        self.assertEqual(sched["weeks"][0]["gyms"], ["1"])

    def test_blank_gym_uses_the_season_gym(self):
        self.write("schedule.csv", self.SCHEDULE.replace(",19:00,1,", ",19:00,,", 1))
        out = bs.compute_season(bs.load_season(self.data, "test", gym="St. Pats"))
        first = out["schedule.json"]["weeks"][0]
        self.assertEqual(first["games"][0]["gym"], "St. Pats")
        self.assertEqual(first["gyms"], ["St. Pats"])
        self.assertEqual(out["games.json"]["2026-10-01-g1"]["gym"], "St. Pats")
        # a different gym on another day is kept as written
        self.assertEqual(out["schedule.json"]["weeks"][1]["games"][0]["gym"], "1")
        # no season gym and a blank cell: no gym
        out = self.compute()
        self.assertIsNone(out["schedule.json"]["weeks"][0]["games"][0]["gym"])
        self.assertEqual(out["schedule.json"]["weeks"][0]["gyms"], [])


class CancelledGameTests(SeasonFixture):
    """schedule.csv may have a status column: blank, or cancelled."""

    def schedule_with_status(self, statuses):
        lines = textwrap.dedent(self.SCHEDULE).splitlines()
        out = [lines[0] + ",status"]
        for line in lines[1:]:
            out.append(line + "," + statuses.get(line.split(",")[0], ""))
        self.write("schedule.csv", "\n".join(out) + "\n")

    def test_header_without_status_still_works(self):
        self.assertEqual(self.compute()["schedule.json"]["next_week"], 4)

    def test_cancelled_game_is_skipped_as_next_and_moves_to_results(self):
        self.schedule_with_status({"2026-10-22-g1": "cancelled"})
        out = self.compute()
        sched = out["schedule.json"]
        week4 = next(w for w in sched["weeks"] if w["week"] == 4)
        self.assertTrue(week4["cancelled"])
        self.assertTrue(week4["played"])                 # done: shown under Results
        self.assertTrue(week4["games"][0]["cancelled"])
        self.assertFalse(week4["games"][0]["played"])
        self.assertIsNone(sched["next_week"])            # the only open game was cancelled
        self.assertEqual(sched["latest_week"], 20)
        self.assertEqual(out["players.json"]["al-a"]["gp"], 2)   # stats don't change

    def test_partly_cancelled_week_stays_upcoming(self):
        self.schedule_with_status({"2026-10-22-g1": "cancelled"})
        self.write("schedule.csv", (self.season / "schedule.csv").read_text()
                   + "2026-10-22-g2,2026-10-22,20:15,1,bb,cc,regular,4,\n")
        sched = self.compute()["schedule.json"]
        week4 = next(w for w in sched["weeks"] if w["week"] == 4)
        self.assertFalse(week4["cancelled"])
        self.assertFalse(week4["played"])
        self.assertEqual(sched["next_week"], 4)

    def test_a_game_file_for_a_cancelled_game_fails(self):
        self.schedule_with_status({"2026-10-08-g1": "cancelled"})
        self.assertProblem("game '2026-10-08-g1' is marked cancelled in schedule.csv")

    def test_unknown_status_fails(self):
        self.schedule_with_status({"2026-10-22-g1": "postponed"})
        self.assertProblem("status 'postponed' should be blank or cancelled")

    def test_make_up_on_the_day_of_a_cancelled_game_is_allowed(self):
        self.schedule_with_status({"2026-10-22-g1": "cancelled"})
        self.write("schedule.csv", (self.season / "schedule.csv").read_text()
                   + "2026-10-22-g2,2026-10-22,20:15,1,aa,bb,regular,4,\n")
        self.assertEqual(self.compute()["schedule.json"]["next_week"], 4)


class NoGamesYetTests(SeasonFixture):
    """The real season starts with teams, placeholder players and no games."""

    def setUp(self):
        super().setUp()
        for path in (self.season / "games").glob("*.yml"):
            path.unlink()
        self.write("schedule.csv", "game_id,date,time,gym,home,away,type,week\n")

    def test_builds_with_no_games_and_no_schedule(self):
        out = self.compute()
        self.assertEqual(out["rankings.json"], [])
        self.assertEqual(out["leaders.json"]["ppg"], [])
        self.assertEqual(out["leaders.json"]["ft_pct"], [])
        self.assertIsNone(out["standings.json"]["through_week"])
        self.assertEqual(out["schedule.json"], {"latest_week": None, "next_week": None, "weeks": []})
        self.assertEqual(out["games.json"], {})
        teams = out["standings.json"]["teams"]
        self.assertEqual(len(teams), 3)
        self.assertTrue(all((t["w"], t["l"], t["pct"], t["gb_display"]) == (0, 0, ".000", "\u2014") for t in teams))

    def test_placeholder_rows_are_accepted(self):
        self.write("players.yml", "- {id: placeholder-a, display: \"[placeholder]\", team: aa, sub: false}\n")
        self.assertEqual(self.compute()["rankings.json"], [])

    def test_main_writes_every_file(self):
        out = self.tmp / "computed"
        argv = ["--data", str(self.data), "--out", str(out), "--root", str(self.tmp / "site"),
                "--config", str(self.tmp / "none.yml")]
        self.assertEqual(bs.main(argv), 0)
        names = sorted(p.name for p in (out / "test").iterdir())
        self.assertIn("rankings.json", names)
        self.assertEqual(len(names), 9)
        self.assertTrue((out / "active.json").exists())


class SeasonListTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for sid in ("real", "fake"):
            (self.tmp / sid).mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def load(self, text):
        (self.tmp / "seasons.yml").write_text(textwrap.dedent(text))
        problems = []
        seasons = bs.load_seasons(self.tmp, problems)
        return seasons, problems

    def test_real_current_and_sample_flagged(self):
        seasons, problems = self.load("""\
            - {id: real, current: true}
            - {id: fake, sample: true}
            """)
        self.assertEqual(problems, [])
        self.assertEqual([(s["id"], s["current"], s["sample"]) for s in seasons],
                         [("real", True, False), ("fake", False, True)])

    def test_sample_cannot_be_current(self):
        _, problems = self.load("""\
            - {id: real}
            - {id: fake, sample: true, current: true}
            """)
        self.assertTrue(any("both current and sample" in p for p in problems), problems)

    def test_exactly_one_current(self):
        _, problems = self.load("""\
            - {id: real}
            - {id: fake, sample: true}
            """)
        self.assertTrue(any("exactly one season must have 'current: true'" in p for p in problems), problems)

    def test_a_past_sample_season_is_allowed(self):
        (self.tmp / "fake2").mkdir()
        seasons, problems = self.load("""\
            - {id: real, current: true}
            - {id: fake, sample: true, stands_in_for: real}
            - {id: fake2, sample: true}
            """)
        self.assertEqual(problems, [])
        self.assertEqual([s["sample"] for s in seasons], [False, True, True])

    def test_only_one_stand_in_per_season(self):
        (self.tmp / "fake2").mkdir()
        _, problems = self.load("""\
            - {id: real, current: true}
            - {id: fake, sample: true, stands_in_for: real}
            - {id: fake2, sample: true, stands_in_for: real}
            """)
        self.assertTrue(any("both 'fake' and 'fake2' stand in for 'real'" in p for p in problems), problems)


class ActiveSeasonTests(unittest.TestCase):
    SEASONS = [
        {"id": "real", "current": True, "sample": False},
        {"id": "fake", "current": False, "sample": True, "stands_in_for": "real"},
        {"id": "old-fake", "current": False, "sample": True},
        {"id": "old-real", "current": False, "sample": False},
    ]

    def ids(self, seasons):
        return [s["id"] for s in seasons]

    def test_real_mode(self):
        active = bs.choose_active(self.SEASONS, sample_mode=False)
        self.assertEqual(active["id"], "real")
        # the real current season and the real past season, no sample seasons
        self.assertEqual(self.ids(bs.archive_seasons(self.SEASONS, active, False)), ["real", "old-real"])

    def test_sample_mode(self):
        active = bs.choose_active(self.SEASONS, sample_mode=True)
        self.assertEqual(active["id"], "fake")
        # the stand-in replaces the real season; sample past seasons now show
        self.assertEqual(self.ids(bs.archive_seasons(self.SEASONS, active, True)), ["fake", "old-fake", "old-real"])

    def test_sample_mode_without_a_stand_in_falls_back_to_real(self):
        seasons = [s for s in self.SEASONS if s["id"] != "fake"]
        self.assertEqual(bs.choose_active(seasons, True)["id"], "real")


class MultiSeasonTests(SeasonFixture):
    """A real season (no games), its sample stand-in, and a sample past season."""

    def setUp(self):
        super().setUp()
        base = self.season
        for name in ("real", "fake", "oldfake"):
            shutil.copytree(base, self.data / name)
        shutil.rmtree(base)
        for gid in list(self.GAMES):                     # the real season has no games yet
            (self.data / "real" / "games" / f"{gid}.yml").unlink()
        (self.data / "real" / "schedule.csv").write_text("game_id,date,time,gym,home,away,type,week\n")
        # the fake past season gets its own game ids, a year earlier
        old = self.data / "oldfake"
        for gid in list(self.GAMES):
            new_id = gid.replace("2026", "2025").replace("2027", "2026")
            text = (old / "games" / f"{gid}.yml").read_text().replace(gid, new_id).replace(gid[:10], new_id[:10])
            (old / "games" / f"{gid}.yml").unlink()
            (old / "games" / f"{new_id}.yml").write_text(text)
        sched = (old / "schedule.csv").read_text().replace("2026-", "2025-").replace("2027-", "2026-")
        (old / "schedule.csv").write_text(sched)
        (self.data / "seasons.yml").write_text(textwrap.dedent("""\
            - {id: real, current: true, gym: Gym A}
            - {id: fake, sample: true, stands_in_for: real, gym: Gym A}
            - {id: oldfake, sample: true, gym: Gym A}
            """))
        self.site = self.tmp / "site"
        self.out = self.tmp / "computed"

    def build(self, **config):
        return bs.build(self.data, self.out, config=config, root=self.site)

    def stubs(self, folder):
        d = self.site / folder
        return sorted(p.stem for p in d.glob("*.md")) if d.exists() else []

    def test_real_mode_stubs(self):
        self.build(sample_data=False)
        active = (self.out / "active.json").read_text()
        self.assertIn('"season": "real"', active)
        self.assertIn('"sample_mode": false', active)
        self.assertEqual(self.stubs("_games"), [])                       # no games yet
        self.assertEqual(self.stubs("_archive"), ["real"])
        self.assertEqual(self.stubs("_teams"), ["aa", "bb", "cc"])       # teams exist before games do
        self.assertEqual(self.stubs("_players"), ["al-a", "amy-b", "bo-c", "cy-d", "sam-e"])

    def test_sample_mode_stubs(self):
        self.build(sample_data=True)
        self.assertIn('"season": "fake"', (self.out / "active.json").read_text())
        self.assertEqual(self.stubs("_archive"), ["fake", "oldfake"])
        # games from every listed season; players and teams from the active one only
        self.assertEqual(self.stubs("_games"), ["2025-10-01-g1", "2025-10-08-g1", "2025-10-15-g1", "2026-04-01-g1",
                                                 "2026-10-01-g1", "2026-10-08-g1", "2026-10-15-g1", "2027-04-01-g1"])
        game = (self.site / "_games" / "2026-10-01-g1.md").read_text()
        self.assertEqual(game, '---\nseason: "fake"\ngame_id: "2026-10-01-g1"\ntitle: "Alpha vs Bravo, Thu Oct 1, 2026"\n'
                               'description: "Box score: Alpha 30, Bravo 20 on Thu Oct 1, 2026 (Week 1). '
                               'Points and free throws for every player."\n---\n')
        self.assertEqual(self.stubs("_teams"), ["aa", "bb", "cc"])
        self.assertIn('title: "Al A."', (self.site / "_players" / "al-a.md").read_text())

    def test_every_stub_has_its_own_title_and_description(self):
        self.build(sample_data=True)
        for folder in ("_games", "_players", "_teams", "_archive"):
            pages = [p.read_text() for p in (self.site / folder).glob("*.md")]
            titles = [re.search(r'^title: (.*)$', p, re.M).group(1) for p in pages]
            descriptions = [re.search(r'^description: (.*)$', p, re.M).group(1) for p in pages]
            self.assertEqual(len(set(titles)), len(pages), folder)
            self.assertEqual(len(set(descriptions)), len(pages), folder)

    def test_calendars_come_from_the_real_season_even_in_sample_mode(self):
        self.build(sample_data=True, url="https://example.ca")
        self.assertEqual(sorted(p.name for p in (self.site / "calendar").glob("*.ics")),
                         ["aa.ics", "bb.ics", "cc.ics", "league.ics"])
        info = (self.out / "calendars.json").read_text()
        self.assertIn('"season": "real"', info)
        self.assertIn('"games": 0', info)                                 # the fake season's games aren't in it
        self.assertNotIn("BEGIN:VEVENT", (self.site / "calendar" / "league.ics").read_text())

    def test_stubs_are_rewritten_not_accumulated(self):
        self.build(sample_data=True)
        (self.site / "_games" / "stale.md").write_text("---\n---\n")
        self.build(sample_data=True)
        self.assertNotIn("stale", self.stubs("_games"))

    def test_check_mode_writes_nothing(self):
        argv = ["--data", str(self.data), "--out", str(self.out), "--root", str(self.site),
                "--config", str(self.tmp / "none.yml"), "--check"]
        self.assertEqual(bs.main(argv), 0)
        self.assertFalse(self.out.exists())
        self.assertFalse(self.site.exists())

    def test_game_ids_must_be_unique_across_listed_seasons(self):
        shutil.copy(self.data / "fake" / "games" / "2026-10-01-g1.yml", self.data / "oldfake" / "games" / "2026-10-01-g1.yml")
        sched = self.data / "oldfake" / "schedule.csv"
        sched.write_text(sched.read_text() + "2026-10-01-g1,2026-10-01,19:00,,aa,bb,regular,1\n")
        with self.assertRaises(bs.DataError) as ctx:
            self.build(sample_data=True)
        self.assertIn("'2026-10-01-g1' is used in both 'fake' and 'oldfake'", "\n".join(ctx.exception.problems))
        # in real mode neither sample season is listed, so the clash doesn't matter
        self.build(sample_data=False)

    def test_score_sheets_only_copied_when_switched_on(self):
        photo = self.data / "fake" / "sheets"
        photo.mkdir(exist_ok=True)
        (photo / "2026-10-01-g1.jpg").write_bytes(b"jpeg")
        self.build(sample_data=True)
        self.assertFalse((self.site / "sheets").exists())
        self.assertIn('"sheet": null', (self.out / "fake" / "games.json").read_text())
        self.build(sample_data=True, score_sheet_links=True)
        self.assertEqual((self.site / "sheets" / "2026-10-01-g1.jpg").read_bytes(), b"jpeg")
        self.assertIn('"sheet": "sheets/2026-10-01-g1.jpg"', (self.out / "fake" / "games.json").read_text())
        self.build(sample_data=True)                          # switched off again: the copy is removed
        self.assertFalse((self.site / "sheets").exists())


class SeasonStandInTests(unittest.TestCase):
    def test_stands_in_for_must_name_a_season_and_be_sample(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "a").mkdir()
            (tmp / "b").mkdir()
            (tmp / "seasons.yml").write_text("- {id: a, current: true}\n- {id: b, stands_in_for: nope}\n")
            problems = []
            bs.load_seasons(tmp, problems)
            joined = "\n".join(problems)
            self.assertIn("not marked sample: true", joined)
            self.assertIn("stands_in_for 'nope', which is not a season", joined)
        finally:
            shutil.rmtree(tmp)


class CheckTests(SeasonFixture):
    def test_points_must_add_up_to_final(self):
        self.edit_game("2026-10-01-g1", "{aa: 30, bb: 20}", "{aa: 31, bb: 20}")
        self.assertProblem("aa player points add up to 30, but the final score is 31")

    def test_ftm_not_more_than_fta(self):
        self.edit_game("2026-10-01-g1", "ftm: 4, fta: 5", "ftm: 6, fta: 5")
        self.assertProblem("ftm 6 is more than fta 5")

    def test_no_negative_numbers(self):
        self.edit_game("2026-10-01-g1", "amy-b, team: aa, pts: 10, ftm: 0, fta: 2",
                       "amy-b, team: aa, pts: 10, ftm: 0, fta: -2")
        self.assertProblem("fta should be whole numbers, 0 or more")

    def test_unknown_player(self):
        self.edit_game("2026-10-01-g1", "player: amy-b", "player: amy-z")
        self.assertProblem("player 'amy-z' is not in players.yml")

    def test_unknown_team(self):
        self.write("players.yml", self.PLAYERS + "- {id: zed-z, display: Zed Z., team: zz, sub: true}\n")
        self.assertProblem("team 'zz' is not in teams.yml")

    def test_game_id_must_match_file_name(self):
        self.edit_game("2026-10-01-g1", "game_id: 2026-10-01-g1", "game_id: 2026-10-01-g2")
        self.assertProblem("doesn't match the file name")

    def test_game_id_must_be_in_schedule(self):
        body = self.GAMES["2026-10-01-g1"].replace("2026-10-01-g1", "2026-10-02-g1")
        self.write("games/2026-10-02-g1.yml", body)
        self.assertProblem("has no row in schedule.csv")

    def test_full_names_rejected(self):
        self.write("players.yml", self.PLAYERS.replace("Al A.", "Al Anderson"))
        self.assertProblem("should be 'First L.'")

    def test_every_problem_reported_at_once(self):
        self.edit_game("2026-10-01-g1", "ftm: 4, fta: 5", "ftm: 6, fta: 5")
        self.edit_game("2026-10-08-g1", "player: cy-d", "player: nobody-x")
        with self.assertRaises(bs.DataError) as ctx:
            bs.load_season(self.data, "test")
        self.assertGreaterEqual(len(ctx.exception.problems), 2)

    def test_build_writes_nothing_on_failure(self):
        out = self.tmp / "computed"
        bs.build(self.data, out)
        self.assertTrue((out / "test" / "standings.json").exists())
        self.edit_game("2026-10-01-g1", "{aa: 30, bb: 20}", "{aa: 31, bb: 20}")
        (out / "marker").write_text("old")
        self.assertEqual(bs.main(["--data", str(self.data), "--out", str(out), "--root", str(self.tmp / "site")]), 1)
        self.assertTrue((out / "marker").exists())                  # old output left alone


if __name__ == "__main__":
    unittest.main()
