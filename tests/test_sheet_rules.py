"""Tests for scripts/sheet_rules.py, driven by the shared fixtures in
tests/fixtures/sheets/. Each case is a folder with a sheet.yml (a game file, as
the paper sheet was filled in) and an expected.json: the game it computes (or
null when it has errors) and every problem, with the path of its box.

The fixtures are shared on purpose: the entry page's JavaScript rules are tested
against the same files (tests/js/). Run: python -m pytest
"""
import json
import random
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_stats  # noqa: E402
import sheet_rules  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "sheets"
CASES = sorted(p.name for p in FIXTURES.iterdir() if (p / "sheet.yml").exists())


@pytest.fixture(scope="module")
def season():
    problems = []
    teams = build_stats.load_teams(FIXTURES / "season", problems)
    players = build_stats.load_players(FIXTURES / "season", teams, problems)
    schedule = build_stats.load_schedule(FIXTURES / "season", teams, problems)
    assert problems == []
    return {"teams": teams, "players": players, "schedule": schedule}


def run(case, season):
    sheet = yaml.safe_load((FIXTURES / case / "sheet.yml").read_text())
    expected = json.loads((FIXTURES / case / "expected.json").read_text())
    # Every fixture is game 2026-10-17-g1; its folder name stands in for the file name.
    ctx = {**season, "stem": sheet["game_id"], "folder": expected.get("folder", "games")}
    return sheet, expected, sheet_rules.check(sheet, ctx)


def test_the_required_cases_are_all_there():
    for case in ("clean", "bad-final", "ft-mismatch", "and-one", "unknown-jersey", "overtime", "page-two"):
        assert case in CASES


@pytest.mark.parametrize("case", CASES)
def test_fixture(case, season):
    _, expected, (game, problems) = run(case, season)
    assert problems == expected["problems"]
    if expected["game"] is None:
        assert game is None
    else:
        assert game is not None
        for key in ("final", "quarters", "ot", "lines"):
            assert game[key] == expected["game"][key], key


@pytest.mark.parametrize("case", CASES)
def test_every_path_names_a_box_in_the_file(case, season):
    """`at` paths must lead to something in the sheet (or, for a missing field,
    to the place it belongs), so the page can highlight it."""
    sheet, _, (_, problems) = run(case, season)
    for p in problems:
        node = sheet
        parts = p["at"].split(".")
        for part in parts[:-1]:
            node = node[int(part)] if isinstance(node, list) else node.get(int(part) if part.isdigit() and int(part) in node else part)
        last = parts[-1]
        assert node is not None, p                      # the box's row, team or section exists
        if isinstance(node, list):
            assert int(last) <= len(node), p
        elif last.isdigit():
            assert int(last) in node, p                 # a running-score box
        # a named field may be missing (e.g. a sub's `player`): the path is where it belongs


def test_points_come_from_the_running_score_and_free_throws_from_the_circles(season):
    _, _, (game, _) = run("and-one", season)
    ann = next(l for l in game["lines"] if l["player"] == "ann-c")
    # 2 to 7, 1 to 13, 2 to 17, 1 to 18 (the and-one); her two filled circles are the FTs
    assert (ann["pts"], ann["ftm"], ann["fta"]) == (6, 2, 2)


def test_a_player_not_ticked_here_has_no_line(season):
    _, _, (game, _) = run("clean", season)
    assert "ari-d" not in {l["player"] for l in game["lines"]}


def test_jumps_are_1_2_or_3(season):
    sheet, _, _ = run("clean", season)
    del sheet["running"]["aa"][20]                      # 19 -> 22 is a jump of 3: fine
    del sheet["running"]["aa"][19]                      # 17 -> 22 is a jump of 5
    _, problems = sheet_rules.check(sheet, {**season, "stem": sheet["game_id"], "folder": "games"})
    assert {"level": "error", "at": "running.aa.22",
            "message": "aa goes from 17 to 22, a jump of 5; a score is 1, 2 or 3"} in problems


def test_a_scorer_must_be_ticked_here(season):
    sheet, _, _ = run("clean", season)
    sheet["running"]["aa"][2] = 7                       # Ari D. (#7) didn't play
    _, problems = sheet_rules.check(sheet, {**season, "stem": sheet["game_id"], "folder": "games"})
    assert any(p["at"] == "running.aa.2" and "isn't ticked Here" in p["message"] for p in problems)


def test_a_final_sheet_needs_ids_checked_by_and_no_review(season):
    sheet, _, _ = run("draft-with-sub", season)
    sheet["status"] = "final"
    _, problems = sheet_rules.check(sheet, {**season, "stem": sheet["game_id"], "folder": "games"})
    errors = {p["at"] for p in problems if p["level"] == "error"}
    assert {"teams.bb.players.3.player", "review", "checked_by"} <= errors


def test_status_must_match_the_folder(season):
    sheet, _, _ = run("clean", season)
    _, problems = sheet_rules.check(sheet, {**season, "stem": sheet["game_id"], "folder": "drafts"})
    assert any(p["at"] == "status" for p in problems)


def test_the_game_must_be_on_the_schedule(season):
    sheet, _, _ = run("clean", season)
    sheet["game_id"] = "2026-10-24-g1"
    _, problems = sheet_rules.check(sheet, {**season, "stem": "2026-10-24-g1", "folder": "games"})
    assert {"level": "error", "at": "game_id", "message": "game_id '2026-10-24-g1' has no row in schedule.csv"} in problems


def test_a_100_point_game_fits_in_a_url():
    """The whole file must fit in a link later: under 6 KB for a 100-point game."""
    players = {"aa": [{"player": f"pa{i}", "num": i, "pts": 10, "ftm": 4, "fta": 6, "pf": 2} for i in range(1, 11)],
               "bb": [{"player": f"pb{i}", "num": i, "pts": 12, "ftm": 4, "fta": 6, "pf": 2} for i in range(1, 9)]}
    sheet = sheet_rules.build_sheet("2026-10-17-g1", "aa", "bb", {"aa": [25, 50, 75, 100], "bb": [24, 49, 70, 96]},
                                    players, random.Random(3))
    assert len(sheet_rules.dump(sheet).encode()) < 6000


def test_the_spec_json_matches_the_generator():
    """scripts/scoresheet/spec.json is written by `scoresheet.py --spec`; keep them in step."""
    pytest.importorskip("reportlab")
    sys.path.insert(0, str(ROOT / "scripts" / "scoresheet"))
    import scoresheet
    assert json.loads(sheet_rules.SPEC_PATH.read_text()) == json.loads(json.dumps(scoresheet.spec_json()))


PRACTICE = ROOT / "tests" / "fixtures" / "record-game"


@pytest.mark.parametrize("game", sorted(p.name for p in PRACTICE.iterdir() if (p / "answer.yml").exists())
                         if PRACTICE.exists() else [])
def test_the_practice_answer_keys_pass(game):
    """The /record-game practice games (scripts/make_practice_games.py) are valid
    final game files for the sample season."""
    season_dir = ROOT / "data" / "sample-2026-27"
    problems = []
    teams = build_stats.load_teams(season_dir, problems)
    players = build_stats.load_players(season_dir, teams, problems)
    schedule = build_stats.load_schedule(season_dir, teams, problems)
    sheet = yaml.safe_load((PRACTICE / game / "answer.yml").read_text())
    result, found = sheet_rules.check(sheet, {"stem": game, "folder": "games", "teams": teams,
                                              "players": players, "schedule": schedule})
    assert found == [] and result is not None
