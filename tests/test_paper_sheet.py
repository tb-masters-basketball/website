"""Tests for the league's paper score sheet (scripts/scoresheet/paper_sheet.py,
form MBL-PS1): it builds, its spec round-trips, and it has every row, every
running-score number and both team-name fields."""

import json
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "scoresheet" / "paper_sheet.py"
sys.path.insert(0, str(ROOT / "scripts" / "scoresheet"))

try:
    import paper_sheet  # noqa: E402  (needs reportlab)
except ImportError:      # pragma: no cover
    paper_sheet = None
try:
    import pypdfium2 as pdfium
except ImportError:      # pragma: no cover
    pdfium = None


def fields(pdf):
    """{field name: value} from a PDF's form fields."""
    out = {}
    for obj in pdf.read_bytes().split(b"endobj"):
        t = re.search(rb"/T \(((?:[^()\\]|\\.)*)\)", obj)
        v = re.search(rb"/V \(((?:[^()\\]|\\.)*)\)", obj)
        if t and v and b"/Widget" in obj:
            out[t.group(1).decode("latin-1")] = v.group(1).decode("latin-1")
    return out


def page_texts(pdf):
    doc = pdfium.PdfDocument(str(pdf))
    try:
        return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    finally:
        doc.close()


@unittest.skipIf(paper_sheet is None, "reportlab isn't installed")
class PaperSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        season = self.tmp / "data" / "2026-27"
        season.mkdir(parents=True)
        (self.tmp / "data" / "seasons.yml").write_text(textwrap.dedent("""\
            - {id: 2026-27, label: "2026-27", current: true, gym: "Test Gym"}
            """))
        for name, text in {
            "teams.yml": """\
                - {id: aa, name: Alpha, short: AL, colour_slot: 1}
                - {id: bb, name: The Very Long Team Name Of Bravo, short: BR, colour_slot: 2}
                """,
            "players.yml": """\
                - {id: al-a, display: Al A., team: aa, sub: false, number: 12}
                - {id: amy-b, display: Amy B., team: aa, sub: false, number: 4}
                - {id: sam-e, display: Sam E., team: aa, sub: true}
                - {id: bo-c, display: Bo C., team: bb, sub: false}
                """,
            "schedule.csv": """\
                game_id,date,time,gym,home,away,type,week,status,round
                2026-10-17-g1,2026-10-17,09:45,,aa,bb,regular,1,,
                2026-10-17-g2,2026-10-17,11:15,Other Gym,bb,aa,regular,1,,
                2026-10-31-g1,2026-10-31,09:45,,aa,bb,regular,2,cancelled,
                """,
        }.items():
            (season / name).write_text(textwrap.dedent(text))
        self.season = season

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], check=True,
                              capture_output=True, text=True).stdout.split()

    def test_a_game_day_builds_one_pdf_with_a_page_per_game(self):
        out = self.tmp / "out"
        made = self.run_script("--data", str(self.season), "--out", str(out))
        self.assertEqual(made, [str(out / "paper-sheets-2026-10-17.pdf")])   # the cancelled game: no sheet
        if pdfium:
            self.assertEqual(len(page_texts(out / "paper-sheets-2026-10-17.pdf")), 2)

    def test_the_prefilled_fields(self):
        out = self.tmp / "out"
        self.run_script("--data", str(self.season), "--game", "2026-10-17-g1", "--out", str(out))
        f = fields(out / "paper-sheets-2026-10-17.pdf")
        self.assertEqual(f["visitor_team"], "The Very Long Team Name Of Bravo")   # away = visitor
        self.assertEqual(f["home_team"], "Alpha")
        self.assertEqual((f["game_no"], f["competition"], f["place"]), ("1", "Masters", "Test Gym"))
        self.assertEqual(f["date"], "Sat Oct 17, 2026")
        # regular players in number order; subs' rows left blank
        self.assertEqual([(f[f"home_p0{i}_no"], f[f"home_p0{i}_name"]) for i in (1, 2, 3)],
                         [("4", "Amy B."), ("12", "Al A."), ("", "")])
        self.assertEqual((f["visitor_p01_no"], f["visitor_p01_name"]), ("", "Bo C."))
        self.assertEqual(sum(1 for k in f if k.startswith("home_p") and k.endswith("_name")), 16)

    def test_a_game_gym_beats_the_season_gym(self):
        g = {x["game_id"]: x for x in paper_sheet.load_games(str(self.season))}
        self.assertEqual(g["2026-10-17-g2"]["place"], "Other Gym")
        self.assertEqual(g["2026-10-17-g2"]["game_no"], "2")

    def test_a_blank_sheet_has_every_field_empty(self):
        out = self.tmp / "out"
        self.run_script("--blank", "--out", str(out))
        f = fields(out / "paper-sheet-blank.pdf")
        for name in ("visitor_team", "home_team", "game_no", "date", "visitor_p16_name", "home_p16_no"):
            self.assertIn(name, f)
        self.assertEqual({v for v in f.values()}, {""})

    def test_a_long_team_name_gets_a_smaller_font(self):
        out = self.tmp / "out"
        self.run_script("--data", str(self.season), "--game", "2026-10-17-g1", "--out", str(out))
        raw = (out / "paper-sheets-2026-10-17.pdf").read_bytes()
        sizes = {m.group(2).decode(): float(m.group(1)) for m in
                 re.finditer(rb"/DA \(/Helv ([\d.]+) Tf[^)]*\)[^>]*?/T \((\w+_team)\)", raw)}
        self.assertLess(sizes["visitor_team"], sizes["home_team"])

    @unittest.skipIf(pdfium is None, "pypdfium2 isn't installed")
    def test_every_row_and_running_number_is_printed(self):
        out = self.tmp / "out"
        self.run_script("--blank", "--out", str(out))
        pdf = out / "paper-sheet-blank.pdf"
        text = page_texts(pdf)[0]
        # "1 2 3 4 5" in the Fouls cell of all 16 rows of each team
        page = paper_sheet.geometry_json()["pages"][0]
        doc = pdfium.PdfDocument(str(pdf))
        tp, H = doc[0].get_textpage(), 792
        for side in ("visitor", "home"):
            rows = page["blocks"][side]["rows"]
            self.assertEqual(len(rows), 16)
            for r in rows:
                x, y, w, h = r["fouls"]
                cell = tp.get_text_bounded(left=x, bottom=H - y - h, right=x + w, top=H - y)
                self.assertEqual(cell.split(), ["1", "2", "3", "4", "5"])
        doc.close()
        numbers = [int(n) for n in re.findall(r"\b\d+\b", text)]
        for n in range(1, 131):
            self.assertGreaterEqual(numbers.count(n), 2, n)         # the running score, both teams
        for s in ("VISITOR", "HOME TEAM", "TIME OUT", "SCORE SHEET"):
            self.assertIn(s, text)

    def test_the_geometry_has_both_blocks(self):
        geo = paper_sheet.geometry_json()
        page = geo["pages"][0]
        for side in ("visitor", "home"):
            b = page["blocks"][side]
            self.assertEqual(len(b["rows"]), 16)
            self.assertEqual(sorted(map(int, b["running"])), list(range(1, 131)))
            self.assertEqual(list(b["timeouts"]), ["1", "2", "3", "4", "5", "OT"])
            self.assertIn(f"{side}_team", page["fields"])
        # rows sit inside their block's frame, below its header
        fr, rows = page["blocks"]["home"]["frame"], page["blocks"]["home"]["rows"]
        self.assertEqual(rows[0]["row"][1], fr[1] + 26)
        self.assertLess(rows[-1]["row"][1] + 14, fr[1] + fr[3])

    def test_the_spec_round_trips(self):
        """paper-spec.json is `paper_sheet.py --spec`; a sheet drawn from it is the same sheet."""
        path = ROOT / "scripts" / "scoresheet" / "paper-spec.json"
        spec = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(spec, json.loads(json.dumps(paper_sheet.spec_json())))
        self.assertEqual(spec.pop("form"), paper_sheet.FORM)
        import io
        a, b = paper_sheet.PaperSheet(io.BytesIO()), paper_sheet.PaperSheet(io.BytesIO(), spec)
        a.add_page({}); b.add_page({})
        self.assertEqual(a.maps, b.maps)


if __name__ == "__main__":
    unittest.main()
