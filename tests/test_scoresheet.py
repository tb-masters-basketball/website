"""Tests for how scripts/scoresheet/scoresheet.py reads a season (not the
drawing: the sheet layout is fixed, see scripts/scoresheet/README.md)."""

import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "scoresheet"))

try:
    import scoresheet  # noqa: E402  (needs reportlab)
except ImportError:      # pragma: no cover
    scoresheet = None


@unittest.skipIf(scoresheet is None, "reportlab isn't installed")
class LoadGamesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.write("teams.yml", """\
            - {id: aa, name: Alpha, short: AL, colour_slot: 1}
            - {id: bb, name: Bravo, short: BR, colour_slot: 2}
            """)
        self.write("players.yml", """\
            - {id: al-a, display: Al A., team: aa, sub: false, number: 12}
            - {id: amy-b, display: Amy B., team: aa, sub: false, number: 4}
            - {id: sam-e, display: Sam E., team: aa, sub: true}
            """)
        self.write("schedule.csv", """\
            game_id,date,time,gym,home,away,type,week,status,round
            2026-10-17-g1,2026-10-17,09:45,,aa,bb,regular,1,,
            2026-10-17-g2,2026-10-17,11:15,,bb,aa,regular,1,cancelled,
            2027-04-24-g1,2027-04-24,09:45,,2nd,3rd,playoff,21,,Semifinal (G42)
            """)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, text):
        (self.tmp / name).write_text(textwrap.dedent(text), encoding="utf-8")

    def test_cancelled_and_placeholder_games_are_skipped(self):
        games = scoresheet.load_games(str(self.tmp))
        self.assertEqual([g["game_id"] for g in games], ["2026-10-17-g1"])
        g = games[0]
        self.assertEqual((g["date"], g["time"], g["home"]["name"], g["away"]["name"]),
                         ("Sat Oct 17", "9:45 AM", "Alpha", "Bravo"))

    def test_regulars_are_printed_in_number_order_and_subs_left_off(self):
        home = scoresheet.load_games(str(self.tmp))[0]["home"]["players"]
        self.assertEqual(home, [{"num": "4", "name": "Amy B."}, {"num": "12", "name": "Al A."}])

    def test_number_zero_is_printed(self):
        self.write("players.yml", "- {id: al-a, display: Al A., team: aa, sub: false, number: 0}\n")
        home = scoresheet.load_games(str(self.tmp))[0]["home"]["players"]
        self.assertEqual(home, [{"num": "0", "name": "Al A."}])

    def test_an_empty_roster_still_makes_a_sheet(self):
        self.write("players.yml", "# no rosters yet\n[]\n")
        g = scoresheet.load_games(str(self.tmp))[0]
        self.assertEqual((g["home"]["name"], g["home"]["players"], g["away"]["players"]), ("Alpha", [], []))
        out = self.tmp / "out"
        subprocess.run([sys.executable, str(ROOT / "scripts/scoresheet/scoresheet.py"), "--data", str(self.tmp),
                        "--out", str(out)], check=True, capture_output=True)
        self.assertTrue((out / "score-sheets-2026-10-17.pdf").exists())

    def test_allow_empty_makes_nothing_without_failing(self):
        cmd = [sys.executable, str(ROOT / "scripts/scoresheet/scoresheet.py"), "--data", str(self.tmp),
               "--date", "2030-01-01", "--out", str(self.tmp / "out")]
        self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(cmd + ["--allow-empty"], capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
