"""Calendar files (iCalendar, .ics) for the real season's schedule.

build_stats.py calls write_calendars() after the stats are computed. It writes
one file per team and one for the whole league into <root>/calendar/, which
Jekyll publishes at /calendar/<team id>.ics and /calendar/league.ics.

Calendars always come from the `current` season in data/seasons.yml, even
while sample mode is on: the schedule is real, and anyone who subscribes now
should never see the sample season's made-up games.

Each game is one event, with a UID made from its game_id, so a calendar app
that has subscribed updates the event in place when the schedule changes:
- a cancelled game stays in the feed, marked STATUS:CANCELLED
- a played game gets the final score in its description
Times are Eastern (America/Toronto, which is Thunder Bay's time zone).
"""

import datetime as dt

# The printed schedule starts games 75 minutes apart (9:45 and 11:00), so an
# event lasts 75 minutes. The league hasn't said how long a game is.
GAME_MINUTES = 75
TZID = "America/Toronto"
PRODID = "-//Masters Basketball League Thunder Bay//Schedule//EN"

VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    f"TZID:{TZID}",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:-0500",
    "TZOFFSETTO:-0400",
    "TZNAME:EDT",
    "DTSTART:19700308T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:-0400",
    "TZOFFSETTO:-0500",
    "TZNAME:EST",
    "DTSTART:19701101T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def escape(text):
    """Escape a TEXT value (RFC 5545 section 3.3.11)."""
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """Split a content line into pieces of at most 75 bytes (RFC 5545 section 3.1)."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    pieces, start, limit = [], 0, 75
    while start < len(data):
        end = min(start + limit, len(data))
        while end < len(data) and (data[end] & 0xC0) == 0x80:   # don't cut a UTF-8 character
            end -= 1
        pieces.append(data[start:end].decode("utf-8"))
        start, limit = end, 74                                   # later lines start with a space
    return "\r\n ".join(pieces)


def game_event(game, teams, site_url, domain, stamp):
    """The VEVENT lines for one game from schedule.json."""
    home, away = teams[game["home"]]["name"], teams[game["away"]]["name"]
    start = dt.datetime.fromisoformat(f"{game['date']}T{game['time']}")
    end = start + dt.timedelta(minutes=GAME_MINUTES)
    title = f"{home} vs {away}"
    if game["type"] == "playoff":
        title = f"Playoffs: {title}"
    notes = [f"Masters Basketball League, {game['label']}."]
    if game["cancelled"]:
        title = f"Cancelled: {title}"
        notes.append("This game was cancelled.")
    elif game["played"]:
        final = game["final"]
        notes.append(f"Final: {home} {final[game['home']]}, {away} {final[game['away']]}.")
        notes.append(f"Box score: {site_url}/games/{game['game_id']}/")
    notes.append(f"Schedule and standings: {site_url}/schedule/")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{game['game_id']}@{domain}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;TZID={TZID}:{start:%Y%m%dT%H%M%S}",
        f"DTEND;TZID={TZID}:{end:%Y%m%dT%H%M%S}",
        f"SUMMARY:{escape(title)}",
        f"DESCRIPTION:{escape(' '.join(notes))}",
        f"URL:{site_url}/schedule/",
        "STATUS:CANCELLED" if game["cancelled"] else "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
    ]
    if game.get("gym"):
        lines.append(f"LOCATION:{escape(game['gym'])}")
    lines.append("END:VEVENT")
    return lines


def calendar(name, events):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(name)}",
        f"X-WR-TIMEZONE:{TZID}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
        *VTIMEZONE,
    ]
    for event in events:
        lines.extend(event)
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)


def build_calendars(season, schedule, teams, site_url, now=None):
    """{file name: .ics text} for every team and the whole league."""
    site_url = site_url.rstrip("/")
    domain = site_url.split("://", 1)[-1].split("/", 1)[0] or "localhost"
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    games = [dict(g, label=season["label"] + " season") for week in schedule["weeks"] for g in week["games"]]
    events = {g["game_id"]: game_event(g, teams, site_url, domain, stamp) for g in games}
    files = {"league.ics": calendar(f"Masters Basketball {season['label']}",
                                    [events[g["game_id"]] for g in games])}
    for tid, team in teams.items():
        mine = [events[g["game_id"]] for g in games if tid in (g["home"], g["away"])]
        files[f"{tid}.ics"] = calendar(f"{team['name']} · Masters Basketball {season['label']}", mine)
    return files


def write_calendars(root, season, schedule, teams, site_url, now=None):
    """Write <root>/calendar/*.ics (the folder is replaced each run). Returns the
    list the templates read: which team has which file."""
    folder = root / "calendar"
    if folder.exists():
        for old in folder.glob("*.ics"):
            old.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    files = build_calendars(season, schedule, teams, site_url, now)
    for name, text in files.items():
        with open(folder / name, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return {
        "season": season["id"],
        "label": season["label"],
        "league": "league.ics",
        "teams": [{"team": tid, "name": t["name"], "colour_slot": t["colour_slot"], "file": f"{tid}.ics"}
                  for tid, t in sorted(teams.items(), key=lambda kv: kv[1]["name"])],
    }
