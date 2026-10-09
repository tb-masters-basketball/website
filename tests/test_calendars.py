"""Tests for scripts/calendars.py (the .ics files)."""

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import calendars as cal  # noqa: E402

TEAMS = {
    "bb": {"id": "bb", "name": "Bay City Bears", "short": "BB", "colour_slot": 1},
    "nw": {"id": "nw", "name": "Nor'Westers", "short": "NW", "colour_slot": 5},
    "hu": {"id": "hu", "name": "Hustle", "short": "HU", "colour_slot": 4},
}
SEASON = {"id": "2026-27", "label": "2026-27", "gym": "St. Pat's",
          "gym_address": "621 Selkirk St S, Thunder Bay, ON P7E 1T9"}
NOW = dt.datetime(2026, 10, 8, 12, 0, tzinfo=dt.timezone.utc)


def game(gid, date, time, home, away, **extra):
    known = home in TEAMS and away in TEAMS
    g = {"game_id": gid, "type": "regular", "date": date, "time": time, "gym": "St. Pat's",
         "home": home, "away": away, "home_name": TEAMS.get(home, {}).get("name", home),
         "away_name": TEAMS.get(away, {}).get("name", away), "round": None, "teams_known": known,
         "played": False, "cancelled": False}
    g.update(extra)
    return g


SCHEDULE = {"weeks": [
    {"week": 0, "games": [game("2026-10-03-g1", "2026-10-03", "09:45", "bb", "nw", cancelled=True)]},
    {"week": 1, "games": [game("2026-10-17-g1", "2026-10-17", "09:45", "bb", "hu", played=True,
                               final={"bb": 62, "hu": 54}),
                          game("2026-10-17-g2", "2026-10-17", "11:00", "hu", "nw")]},
    {"week": 2, "games": [game("2027-01-09-g1", "2027-01-09", "11:15", "nw", "bb")]},
    {"week": 21, "games": [game("2027-04-24-g1", "2027-04-24", "09:45", "2nd", "3rd",
                                type="playoff", round="Semifinal (G42)")]},
]}


def events(text):
    """Unfold the lines and split the VEVENTs into dicts of property -> value."""
    lines = text.replace("\r\n ", "").split("\r\n")
    out, current = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            out.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key] = value
    return out


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.files = cal.build_calendars(SEASON, SCHEDULE, TEAMS, "https://mastersbasketball.ca/", now=NOW)

    def test_one_file_per_team_and_the_league(self):
        self.assertEqual(sorted(self.files), ["bb.ics", "hu.ics", "league.ics", "nw.ics"])
        self.assertEqual(len(events(self.files["league.ics"])), 5)
        self.assertEqual(len(events(self.files["bb.ics"])), 3)     # only Bay City Bears' games
        self.assertEqual(len(events(self.files["hu.ics"])), 2)

    def test_event_times_names_and_uid(self):
        ev = events(self.files["nw.ics"])[-1]
        self.assertEqual(ev["UID"], "2027-01-09-g1@mastersbasketball.ca")
        self.assertEqual(ev["DTSTART;TZID=America/Toronto"], "20270109T111500")
        self.assertEqual(ev["DTEND;TZID=America/Toronto"], "20270109T124500")   # 90 minutes
        self.assertEqual(ev["SUMMARY"], "Nor'Westers vs Bay City Bears")
        self.assertEqual(ev["LOCATION"], "St. Pat's\\, 621 Selkirk St S\\, Thunder Bay\\, ON P7E 1T9")
        self.assertEqual(ev["DTSTAMP"], "20261008T120000Z")
        self.assertIn("BEGIN:VTIMEZONE\r\nTZID:America/Toronto", self.files["nw.ics"])

    def test_playoff_game_with_unknown_teams_is_in_the_league_calendar_only(self):
        league = events(self.files["league.ics"])[-1]
        self.assertEqual(league["SUMMARY"], "Playoffs\\, Semifinal (G42): 2nd vs 3rd")
        for team in ("bb.ics", "hu.ics", "nw.ics"):
            self.assertNotIn("2027-04-24-g1", self.files[team])

    def test_cancelled_game_stays_in_the_feed_marked_cancelled(self):
        ev = events(self.files["bb.ics"])[0]
        self.assertEqual(ev["STATUS"], "CANCELLED")
        self.assertTrue(ev["SUMMARY"].startswith("Cancelled: "))

    def test_played_game_has_the_final_score(self):
        ev = events(self.files["hu.ics"])[0]
        self.assertEqual(ev["STATUS"], "CONFIRMED")
        self.assertIn("Final: Bay City Bears 62\\, Hustle 54.", ev["DESCRIPTION"])
        self.assertIn("https://mastersbasketball.ca/games/2026-10-17-g1/", ev["DESCRIPTION"])

    def test_lines_use_crlf_and_are_folded_at_75_bytes(self):
        for text in self.files.values():
            self.assertTrue(text.endswith("END:VCALENDAR\r\n"))
            self.assertNotIn("\n", text.replace("\r\n", ""))
            for line in text.split("\r\n"):
                self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_another_gym_has_no_address(self):
        other = dict(SCHEDULE["weeks"][2]["games"][0], gym="Other Gym")
        self.assertEqual(cal.location(other, SEASON), "Other Gym")
        self.assertEqual(cal.location(other, {"id": "x", "label": "x", "gym": "Other Gym"}), "Other Gym")

    def test_escape_and_fold(self):
        self.assertEqual(cal.escape("a,b;c\\d\ne"), "a\\,b\;c\\\\d\\ne")
        long = "DESCRIPTION:" + "é" * 80
        folded = cal.fold(long)
        self.assertEqual(folded.replace("\r\n ", ""), long)        # nothing lost, no character split
        self.assertTrue(all(len(p.encode("utf-8")) <= 75 for p in folded.split("\r\n")))


if __name__ == "__main__":
    unittest.main()
