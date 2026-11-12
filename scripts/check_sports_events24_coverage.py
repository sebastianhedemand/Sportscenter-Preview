#!/usr/bin/env python3
"""Read-only, quota-conscious SportsEvents24 league and event coverage check."""
from __future__ import annotations

import json
import re
import sys
import time
import email.utils
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://sportsevents24.com/api/v1"
TIMEOUT = 25
MAX_PAGES_PER_SELECTION = 5
MAX_EVENT_CHECKS = 13
REQUEST_SPACING_SECONDS = 7.0

# Match exact top-flight/second-tier competition names, not similarly named youth,
# regional, cup, futsal or women's competitions unless explicitly requested.
TARGETS = [
    {"sport": "football", "sport_id": 1, "country": "DK", "league": "Superligaen",
     "patterns": [r"3f\s*superliga"], "season": "2026/27"},
    {"sport": "football", "sport_id": 1, "country": "DK", "league": "1. Division",
     "patterns": [r"betinia\s*liga"], "season": "2026/27"},
    {"sport": "football", "sport_id": 1, "country": "GB", "league": "Premier League",
     "patterns": [r"premier\s*league"], "season": "2026/27"},
    {"sport": "football", "sport_id": 1, "country": "GB", "league": "Championship",
     "patterns": [r"championship"], "season": "2026/27"},
    {"sport": "football", "sport_id": 1, "country": "GB", "league": "League One",
     "patterns": [r"league\s*one"], "season": "2026/27"},
    {"sport": "football", "sport_id": 1, "country": "DE", "league": "Bundesliga",
     "patterns": [r"bundesliga"], "season": "2026/27"},
    {"sport": "football", "sport_id": 1, "country": "IT", "league": "Serie A",
     "patterns": [r"serie\s*a\s*2026"], "season": "2026/27"},
    {"sport": "football", "sport_id": 1, "country": "ES", "league": "La Liga",
     "patterns": [r"primera\s*divisi[oó]n", r"laliga", r"la\s*liga"], "season": "2026/27"},
    {"sport": "handball", "sport_id": 6, "country": "DK", "league": "Herreligaen",
     "patterns": [r"herreliga"], "season": "2026/27"},
    {"sport": "handball", "sport_id": 6, "country": "DK", "league": "Kvindeligaen",
     "patterns": [r"kvindeliga"], "season": "2026/27"},
    {"sport": "handball", "sport_id": 6, "country": "DK", "league": "1. Division herrer",
     "patterns": [r"1\.\s*division\s*herrer", r"1\.\s*division\s*m[aæ]nd"], "season": "2026/27"},
    {"sport": "handball", "sport_id": 6, "country": "DK", "league": "1. Division damer",
     "patterns": [r"1\.\s*division\s*damer", r"1\.\s*division\s*kvinder"], "season": "2026/27"},
    {"sport": "handball", "sport_id": 6, "country": "DE", "league": "Tysk Handball-Bundesliga",
     "patterns": [r"1\.\s*bundesliga\s*m[aä]nner", r"handball-bundesliga"], "season": "2026/27"},
]


def get_json(path: str, params: dict[str, str]) -> dict:
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Sportscenter-preview-coverage-check/3.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After", "60")
            raise RuntimeError(f"HTTP 429 rate limited; Retry-After={retry_after}") from exc
        raise
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected JSON response shape")
    return payload

def data_rows(payload: dict) -> list[dict]:
    data = payload.get("data", [])
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("tournaments", "events", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def tournament_name(row: dict) -> str:
    for key in ("name", "tournament_name", "title"):
        if row.get(key):
            return str(row[key])
    return ""


def tournament_id(row: dict):
    for key in ("tournament_id", "id"):
        if row.get(key) is not None:
            return row[key]
    return None


def matches_target(name: str, target: dict) -> bool:
    text = name.casefold()
    return any(re.search(pattern, text, re.I) for pattern in target["patterns"])


def main() -> int:
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "SportsEvents24",
        "mode": "read-only; no Sportscenter app data is changed",
        "targets": [],
        "limits": {
            "max_pages_per_country_sport": MAX_PAGES_PER_SELECTION,
            "max_event_checks": MAX_EVENT_CHECKS,
            "documented_free_beta": "100 requests/day/IP; 5,000 returned records/month/IP; 100 records/response"
        },
        "notes": [
            "Pagination follows nextCursor with identical filters as documented by the provider.",
            "A tournament name is not proof of complete season coverage.",
            "Event checks explicitly request the previous 7 UTC days through today to inspect finished-match scores.",
            "The API permits event dates only within the last 7 and next 30 days; this does not establish deep historical availability.",
            "No odds endpoint is documented in the public API overview.",
            "Commercial redistribution rights must be confirmed with the provider before paid use."
        ],
        "selection_runs": []
    }

    groups = {}
    for target in TARGETS:
        groups.setdefault((target["sport_id"], target["country"]), []).append(target)

    found_by_key = {}
    for (sport_id, country), targets in groups.items():
        cursor = None
        pages = 0
        all_rows = []
        error = None
        while pages < MAX_PAGES_PER_SELECTION:
            params = {"sport_id": str(sport_id), "country": country, "limit": "100"}
            if cursor:
                params["cursor"] = cursor
            try:
                payload = get_json("tournaments", params)
                pages += 1
                batch = data_rows(payload)
                all_rows.extend(batch)
                cursor = payload.get("nextCursor")
                if not cursor:
                    break
                # Stop early only when every target in this country/sport group is located.
                names = [tournament_name(r) for r in all_rows]
                if all(any(matches_target(n, t) for n in names) for t in targets):
                    break
                time.sleep(REQUEST_SPACING_SECONDS)  # remain below 10 requests/minute
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                error = str(exc)
                break

        report["selection_runs"].append({
            "sport_id": sport_id, "country": country, "pages_read": pages,
            "rows_read": len(all_rows), "more_pages_available": bool(cursor),
            "error": error
        })
        for target in targets:
            matches = [r for r in all_rows if matches_target(tournament_name(r), target)]
            # Prefer exact season/year matches, but retain all matching names for review.
            season_matches = [r for r in matches if target["season"] in tournament_name(r)]
            chosen = season_matches or matches
            found_by_key[(target["sport"], target["country"], target["league"])] = {
                "target": target, "matches": chosen, "all_matches": matches,
                "pages_read": pages, "error": error,
                "more_pages_available": bool(cursor)
            }

    event_checks = 0
    for target in TARGETS:
        key = (target["sport"], target["country"], target["league"])
        entry = found_by_key[key]
        match_rows = entry["matches"]
        result = {
            "sport": target["sport"], "country": target["country"],
            "requested_league": target["league"], "expected_season": target["season"],
            "status": "not_found" if not match_rows else "tournament_found",
            "tournament_matches": [
                {"name": tournament_name(r), "tournament_id": tournament_id(r)}
                for r in entry["all_matches"][:20]
            ],
            "pagination_incomplete": entry["more_pages_available"],
            "discovery_error": entry["error"],
            "event_check": "not_run"
        }
        usable = next((r for r in match_rows if tournament_id(r) is not None), None)
        if usable and event_checks < MAX_EVENT_CHECKS:
            try:
                from_date = (datetime.now(timezone.utc).date() - __import__("datetime").timedelta(days=7)).isoformat()
                to_date = (datetime.now(timezone.utc).date() + __import__("datetime").timedelta(days=1)).isoformat()
                payload = get_json("events", {"tournament_id": str(tournament_id(usable)), "from": from_date, "to": to_date, "limit": "100"})
                events = data_rows(payload)
                event_checks += 1
                scored = [e for e in events if e.get("result") or e.get("home_score") is not None or e.get("score") is not None]
                finished = [e for e in events if str(e.get("category", "")).casefold() in ("finished", "completed", "result") or e.get("result")]
                result["event_check"] = "ok"
                result["event_window_utc"] = {"from": from_date, "to_exclusive": to_date}
                result["events_in_previous_7_days"] = len(events)
                result["finished_events_detected"] = len(finished)
                result["events_with_score_fields"] = len(scored)
                result["event_sample"] = events[:5]
                result["event_usage"] = payload.get("usage")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                result["event_check"] = "error"
                result["event_error"] = str(exc)
            time.sleep(6.2)
        elif usable:
            result["event_check"] = "skipped_quota_guard"
        report["targets"].append(result)

    Path("sports-events24-coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# SportsEvents24 – resultat- og dækningskontrol", "",
        f"- Kontrolleret (UTC): {report['checked_at_utc']}",
        "- Metode: pagineret, skrivebeskyttet turneringsopslag samt scorekontrol for de seneste 7 UTC-dage.",
        "",
        "| Sport | Land | Liga | Turneringsfund | Kampdata-test | Flere sider uafklaret |",
        "|---|---|---|---|---|---|"
    ]
    for item in report["targets"]:
        lines.append(
            f"| {item['sport']} | {item['country']} | {item['requested_league']} | "
            f"{item['status']} | {item['event_check']} | {'Ja' if item['pagination_incomplete'] else 'Nej'} |"
        )
    lines += ["", "## Detaljer", ""]
    for item in report["targets"]:
        lines += [f"### {item['sport'].title()} – {item['requested_league']} ({item['country']})", ""]
        if item["tournament_matches"]:
            for t in item["tournament_matches"]:
                lines.append(f"- {t['name']} (turnerings-ID: {t['tournament_id']})")
        else:
            lines.append("Ingen matchende turnering fundet i de gennemgåede sider.")
        if item["event_check"] == "ok":
            lines.append(f"- Kampe i seneste 7 dage: {item['events_in_previous_7_days']}")
            lines.append(f"- Afsluttede kampe identificeret: {item['finished_events_detected']}")
            lines.append(f"- Kampe med scorefelter: {item['events_with_score_fields']}")
        else:
            lines.append(f"- Kampdata-test: {item['event_check']}")
        if item["discovery_error"]:
            lines.append(f"- Fejl ved turneringsopslag: {item['discovery_error']}")
        lines.append("")
    lines += ["## Begrænsninger", ""] + [f"- {note}" for note in report["notes"]]
    markdown = "\n".join(lines) + "\n"
    Path("sports-events24-coverage.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0 if any(x["status"] != "not_found" for x in report["targets"]) else 1


if __name__ == "__main__":
    sys.exit(main())
