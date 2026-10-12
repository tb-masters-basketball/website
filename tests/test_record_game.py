"""/record-game's measuring helper (scripts/record_game.py): the box map, and
one made-up photo of a practice game read back. The handwriting itself is
read by Claude (see .claude/skills/record-game/SKILL.md); this checks the
part a script can: finding the page, the game, and the pen in each box."""
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "scoresheet"))
import record_game as rg  # noqa: E402
import record_game_eval as ev  # noqa: E402
import scoresheet as ss  # noqa: E402

GAME = "2027-01-07-g1"            # the flagrant and technical practice game
ANSWER = ROOT / "tests" / "fixtures" / "record-game" / GAME / "answer.yml"


class GeometryTests(unittest.TestCase):
    def test_every_layout_maps_every_box(self):
        geo = ss.geometry_json()
        spec = ss.spec_json()
        for layout, g in geo["layouts"].items():
            W, H = g["page_size"]
            p1, p2 = g["pages"]
            self.assertEqual(len(p1["corners"]), 4)
            for side in ("home", "away"):
                self.assertEqual(len(p1[side]["rows"]), ss.ROSTER_ROWS)
                row = p1[side]["rows"][0]
                self.assertEqual(len(row["ft"]), ss.FT_CIRCLES)
                self.assertEqual(len(row["fouls"]), ss.PF_BOXES)
                self.assertEqual(set(p1[side]["score"]), {b["key"] for b in ss.SPEC["score_boxes"]})
            want = spec["layouts"][layout]
            self.assertEqual(sorted(map(int, p1["running"])), list(range(1, want["page1"]["last"] + 1)))
            self.assertEqual(sorted(map(int, p2["running"])),
                             list(range(want["page2"]["first"], want["page2"]["last"] + 1)))
            for x, y, w, h in p1["corners"]:
                self.assertTrue(0 <= x and x + w <= W and 0 <= y and y + h <= H)


class PhotoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(3)
        page = ev.filled_page(ANSWER, "landscape-letter", 2.2)
        img, _ = ev.photograph(page, rng)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        img.rotate(90, expand=True).save(cls.out / "photo.jpg", quality=85)   # taken sideways
        subprocess.run([sys.executable, str(ROOT / "scripts" / "record_game.py"), "prepare",
                        str(cls.out / "photo.jpg"), "--season", "sample-2026-27", "--out", str(cls.out / "work")],
                       check=True, capture_output=True)
        cls.marks = json.loads((cls.out / "work" / "marks.json").read_text())
        cls.start = yaml.safe_load((cls.out / "work" / "start.yml").read_text())
        cls.answer = yaml.safe_load(ANSWER.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_layout_page_and_game_are_found(self):
        self.assertEqual(self.marks["layout"], "landscape-letter")
        self.assertEqual(sorted(self.marks["pages"]), ["1"])
        self.assertEqual(self.marks["game"], GAME)
        self.assertEqual((self.start["home"], self.start["away"]), (self.answer["home"], self.answer["away"]))

    def test_ticks_circles_fouls_and_lines_come_from_the_ink(self):
        for tid, team in self.answer["teams"].items():
            got = self.start["teams"][tid]["players"]
            for want, row in zip(team["players"], got):
                with self.subTest(team=tid, player=want["player"]):
                    self.assertEqual(row["player"], want["player"])
                    self.assertEqual(row["here"], want["here"])
                    self.assertEqual(row.get("ft", ""), want.get("ft", ""))
                    self.assertEqual(row.get("fouls", 0), want.get("fouls", 0))
                    self.assertEqual(row.get("tech", 0), want.get("tech", 0))
            self.assertEqual(self.start["lines"][tid], self.answer["lines"][tid])

    def test_every_running_score_box_with_writing_is_found(self):
        for tid in self.answer["teams"]:
            self.assertEqual(sorted(self.start["running"][tid]), sorted(self.answer["running"][tid]))
            self.assertTrue(all(v == "?" for v in self.start["running"][tid].values()))

    def test_the_answer_key_reads_back_clean(self):
        game, problems, *_ = rg.check_file(ANSWER)
        self.assertEqual(problems, [])
        self.assertEqual(game["final"], {self.answer["home"]: 63, self.answer["away"]: 54})

    def test_zoom_names_a_box(self):
        page, box = rg.box_for(self.marks, f"running.{self.answer['home']}.27")
        self.assertEqual(page, 1)
        self.assertEqual(len(box), 4)


if __name__ == "__main__":
    unittest.main()
