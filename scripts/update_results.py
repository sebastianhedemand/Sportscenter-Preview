"""Safely reconcile provider results with the legacy embedded match list.

Existing/manual scores are never overwritten. A mismatch is reported for review.
Run with API_FOOTBALL_KEY set in the environment.
"""
import json
import os
import re
import sys
from datetime import date, timedelta
from urllib.request import Request, urlopen

API_KEY = os.environ.get("API_FOOTBALL_KEY")
LEAGUES = {
    "Premier League": 39,
    "Championship": 40,
    "League One": 41,
    "Bundesliga": 78,
    "Serie A": 135,
    "La Liga": 140,
    "Superligaen": 119,
    "1. Division": 121,
}
FINISHED_STATUSES = {"FT", "AET", "PEN"}


def fetch(league_id, season, start, end):
    url = (
        "https://v3.football.api-sports.io/fixtures"
        f"?league={league_id}&season={season}&from={start}&to={end}"
    )
    request = Request(url, headers={"x-apisports-key": API_KEY})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"API-fejl for liga {league_id}: {payload['errors']}")
    fixtures = payload.get("response")
    if not isinstance(fixtures, list):
        raise RuntimeError(f"Ugyldigt API-svar for liga {league_id}: response mangler.")
    return fixtures


def norm(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def result_key(day, home, away):
    """Stable exact-match key; deliberately does not fuzzy-match team names."""
    return (str(day or "")[:10], norm(home), norm(away))


def season_for_date(day):
    """Return the start year used by API-Football for July–June seasons."""
    return day.year if day.month >= 7 else day.year - 1


def result_window(day, days_back=7):
    """Return an inclusive ISO-date window ending on the supplied date."""
    if not isinstance(days_back, int) or days_back < 0:
        raise ValueError("days_back skal være et heltal på 0 eller derover.")
    return (day - timedelta(days=days_back)).isoformat(), day.isoformat()


def apply_verified_result(game, score, source="api-football", verified_at=None):
    """Fill a missing score; never silently replace an existing/manual result."""
    old_home, old_away = game.get("hg"), game.get("ag")
    has_home = old_home not in (None, "")
    has_away = old_away not in (None, "")
    if has_home != has_away:
        return "incomplete"
    if has_home:
        if (str(old_home), str(old_away)) == (str(score[0]), str(score[1])):
            return "already"
        return "conflict"
    game["hg"], game["ag"] = int(score[0]), int(score[1])
    game["result_source"] = source
    if verified_at:
        game["result_verified_at"] = verified_at
    return "filled"


def main():
    if not API_KEY:
        raise RuntimeError("GitHub Secret API_FOOTBALL_KEY mangler.")

    with open("index.html", encoding="utf-8") as handle:
        html = handle.read()
    match = re.search(r"const initialData=(\{.*?\});\nlet data=load\(\)", html, re.S)
    if not match:
        raise RuntimeError("Kunne ikke finde initialData i index.html.")

    data = json.loads(match.group(1))
    matches = data.get("matches", [])
    today = date.today()
    start, end = result_window(today)
    season = season_for_date(today)

    checked = filled = already = conflicts = 0
    for league, league_id in LEAGUES.items():
        finished = {}
        for item in fetch(league_id, season, start, end):
            fixture = item.get("fixture") or {}
            status = (fixture.get("status") or {}).get("short", "")
            goals = item.get("goals") or {}
            home = (item.get("teams") or {}).get("home") or {}
            away = (item.get("teams") or {}).get("away") or {}
            day = (fixture.get("date") or "")[:10]
            if (
                status in FINISHED_STATUSES
                and goals.get("home") is not None
                and goals.get("away") is not None
            ):
                key = result_key(day, home.get("name"), away.get("name"))
                finished[key] = (int(goals["home"]), int(goals["away"]))
        checked += len(finished)

        for game in matches:
            if game.get("league") != league:
                continue
            key = result_key(game.get("date"), game.get("home"), game.get("away"))
            score = finished.get(key)
            if score is None:
                continue
            outcome = apply_verified_result(game, score, verified_at=today.isoformat())
            if outcome == "already":
                already += 1
            elif outcome in ("conflict", "incomplete"):
                conflicts += 1
                print(
                    f"MANUEL KONTROL ({outcome}) – eksisterende score bevares: "
                    f"{league} {key[0]} {game.get('home')}–{game.get('away')} "
                    f"lokal={game.get('hg')}-{game.get('ag')}, provider={score[0]}-{score[1]}"
                )
            elif outcome == "filled":
                filled += 1
    if filled:
        updated_html = (
            html[:match.start(1)]
            + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            + html[match.end(1):]
        )
        with open("index.html", "w", encoding="utf-8") as handle:
            handle.write(updated_html)

    print(
        f"Afsluttede provider-kampe kontrolleret: {checked}; "
        f"tomme resultater udfyldt: {filled}; allerede ens: {already}; "
        f"konflikter til manuel kontrol: {conflicts}."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Automatisk opdatering fejlede: {exc}", file=sys.stderr)
        sys.exit(1)
