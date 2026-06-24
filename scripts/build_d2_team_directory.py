#!/usr/bin/env python3
"""Build a D2 team directory from current-player and historical-transfer data."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from scrape_phase1_school_stats import SCHOOL_DOMAINS

CURRENT_D2_PATH = Path("d2_data_cleaned copy.csv")
PHASE1_D2_PATH = Path("data/phase1_school_stats.csv")
OUTPUT_PATH = Path("data/d2_team_directory.csv")

SEASONS = ["2023-24", "2024-25", "2025-26"]

SCHEDULE_URL_OVERRIDES = {
    "Tampa": {
        season: f"https://www.tampaspartans.com/sports/mbkb/{season}/schedule"
        for season in SEASONS
    },
}

CONFERENCE_ALIASES = {
    "California Collegiate": "CCAA",
    "Central Athletic": "CACC",
    "Central Intercollegiate Athletic": "CIAA",
    "Conference Carolinas": "Conference Carolinas",
    "Division II Independent": "DII Independent",
    "East Coast": "ECC",
    "Great American": "GAC",
    "Great Lakes Intercollegiate": "GLIAC",
    "Great Lakes Valley": "GLVC",
    "Great Midwest Athletic": "G-MAC",
    "Great Northwest": "GNAC",
    "Gulf South": "GSC",
    "Lone Star": "LSC",
    "Mid-America Intercollegiate": "MIAA",
    "Mountain East": "MEC",
    "Northeast 10": "NE10",
    "Northern Sun Intercollegiate": "NSIC",
    "PacWest": "PacWest",
    "Peach Belt": "PBC",
    "Pennsylvania State Athletic": "PSAC",
    "Rocky Mountain": "RMAC",
    "South Atlantic": "SAC",
    "Southern Intercollegiate Athletic": "SIAC",
    "Sunshine": "SSC",
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(value)).strip("-")


def canonical_team(value: str) -> str:
    replacements = {
        "Cal Poly Humboldt": "Humboldt",
        "Cal State East Bay": "East Bay",
        "Cal State San Bernardino": "San Bernardino",
        "Chico State": "Chico",
        "Concordia Irvine": "Concordia",
        "Hawaii-Hilo": "Hawaii–Hilo",
        "Missouri-St. Louis": "Missouri–St. Louis",
        "West Texas A&M": "West Texas AM",
    }
    return replacements.get(value, value)


def schedule_url(domain: str, season: str) -> str:
    return f"https://{domain}/sports/mens-basketball/schedule/{season}"


def main() -> int:
    teams: dict[str, dict[str, object]] = {}

    with CURRENT_D2_PATH.open(newline="") as file:
        for row in csv.DictReader(file):
            team = row["Team"].strip()
            key = normalize(team)
            entry = teams.setdefault(
                key,
                {
                    "team_name": team,
                    "conference": row["Conference"].strip(),
                    "current_player_count": 0,
                    "phase1_player_count": 0,
                },
            )
            entry["current_player_count"] = int(entry["current_player_count"]) + 1

    with PHASE1_D2_PATH.open(newline="") as file:
        for row in csv.DictReader(file):
            team = canonical_team(row["Team"].strip())
            key = normalize(team)
            entry = teams.setdefault(
                key,
                {
                    "team_name": team,
                    "conference": row["Conference"].strip(),
                    "current_player_count": 0,
                    "phase1_player_count": 0,
                },
            )
            entry["phase1_player_count"] = int(entry["phase1_player_count"]) + 1
            if not entry.get("conference"):
                entry["conference"] = row["Conference"].strip()

    domain_by_key = {normalize(canonical_team(team)): domain for team, domain in SCHOOL_DOMAINS.items()}

    rows = []
    for key, entry in sorted(teams.items(), key=lambda item: str(item[1]["team_name"])):
        team_name = str(entry["team_name"])
        conference = str(entry["conference"])
        domain = domain_by_key.get(normalize(canonical_team(team_name)), "")
        row = {
            "team_id": slugify(team_name),
            "team_name": team_name,
            "conference": conference,
            "conference_code": CONFERENCE_ALIASES.get(conference, conference),
            "current_player_count": entry["current_player_count"],
            "phase1_player_count": entry["phase1_player_count"],
            "school_domain": domain,
            "has_schedule_domain": "TRUE" if domain else "FALSE",
        }
        for season in SEASONS:
            row[f"schedule_url_{season}"] = SCHEDULE_URL_OVERRIDES.get(team_name, {}).get(
                season,
                schedule_url(domain, season) if domain else "",
            )
        rows.append(row)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    fieldnames = [
        "team_id",
        "team_name",
        "conference",
        "conference_code",
        "current_player_count",
        "phase1_player_count",
        "school_domain",
        "has_schedule_domain",
        *[f"schedule_url_{season}" for season in SEASONS],
    ]
    with OUTPUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} teams to {OUTPUT_PATH}")
    print(f"Teams with known schedule domains: {sum(1 for row in rows if row['school_domain'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
