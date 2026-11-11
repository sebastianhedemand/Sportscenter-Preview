#!/usr/bin/env python3
"""Read-only coverage probe for SportsEvents24. Makes a small, quota-conscious set of requests."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://sportsevents24.com/api/v1"
# SportsEvents24 country + sport filters; this is discovery, not proof of complete coverage.
SELECTIONS = [
    ("football", 1, "DK", ["Superliga", "1. Division"]),
    ("football", 1, "GB", ["Premier League", "Championship", "League One"]),
    ("football", 1, "DE", ["Bundesliga"]),
    ("football", 1, "IT", ["Serie A"]),
    ("football", 1, "ES", ["La Liga", "Primera División"]),
    ("handball", 6, "DK", ["Herreliga", "Kvindeliga", "1. Division"]),
    ("handball", 6, "DE", ["1. Bundesliga Männer", "Handball-Bundesliga"]),
]
TIMEOUT = 25


def get_json(path: str, params: dict[str, str]) -> dict:
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Sportscenter-preview-coverage-check/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected JSON response shape")
        return payload


def rows(payload: dict) -> list[dict]:
    data = payload.get("data", [])
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("tournaments", "events", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def main() -> int:
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "SportsEvents24",
        "mode": "read-only discovery; no app data is changed",
        "selections": [],
        "notes": [
            "A tournament appearing in discovery does not prove that all seasons, fixtures or results are complete.",
            "The provider documents a free beta quota of 100 data requests/day/IP and 5,000 returned records/month/IP.",
            "Commercial redistribution rights must be confirmed with the provider before a paid launch."
        ],
    }

    for sport, sport_id, country, expected in SELECTIONS:
        item = {"sport": sport, "country": country, "expected_competitions": expected}
        try:
            payload = get_json("tournaments", {"sport_id": str(sport_id), "country": country, "limit": "100"})
            found = rows(payload)
            names = []
            for row in found:
                name = row.get("name") or row.get("tournament_name") or row.get("title")
                if name:
                    names.append(str(name))
            item.update({
                "status": "ok",
                "tournament_rows": len(found),
                "tournament_names": names[:100],
                "usage": payload.get("usage"),
                "next_cursor_available": bool(payload.get("nextCursor")),
            })
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            item.update({"status": "error", "error": str(exc)})
        report["selections"].append(item)

    Path("sports-events24-coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# SportsEvents24 – dækningskontrol",
        "",
        f"- Kontrolleret (UTC): {report['checked_at_utc']}",
        "- Metode: skrivebeskyttet opslag af turneringsoversigter; ingen ændringer i Sportscenter-appen.",
        "",
        "| Sport | Land | Status | Turneringsrækker | Forventede ligaer |",
        "|---|---|---:|---:|---|",
    ]
    for item in report["selections"]:
        lines.append(
            f"| {item['sport']} | {item['country']} | {item['status']} | "
            f"{item.get('tournament_rows', '—')} | {', '.join(item['expected_competitions'])} |"
        )
    lines += ["", "## Fundne turneringsnavne", ""]
    for item in report["selections"]:
        lines += [f"### {item['sport'].title()} – {item['country']}", ""]
        if item.get("tournament_names"):
            lines += [f"- {name}" for name in item["tournament_names"]]
        elif item["status"] == "error":
            lines.append(f"Fejl: {item['error']}")
        else:
            lines.append("Ingen turneringsnavne kunne udtrækkes fra svaret; kontrollér JSON-rapporten.")
        lines.append("")
    lines += ["## Begrænsninger", ""] + [f"- {note}" for note in report["notes"]]
    Path("sports-events24-coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if any(x["status"] == "ok" for x in report["selections"]) else 1


if __name__ == "__main__":
    sys.exit(main())
