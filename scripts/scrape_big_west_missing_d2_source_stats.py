#!/usr/bin/env python3
"""Scrape missing D2 source rows for Big West inbound transfers."""

from __future__ import annotations

import csv
import sys
import time
import urllib.error
from pathlib import Path

from scrape_phase1_school_stats import (
    MISSING_COLUMNS,
    OUTPUT_COLUMNS,
    build_row,
    find_player_tokens,
    page_text,
)

MISSING_SOURCE_PATH = Path("data/big_west_transfer_source_stats_missing.csv")
OUTPUT_PATH = Path("data/big_west_missing_d2_source_stats.csv")
MISSING_PATH = Path("data/big_west_missing_d2_source_stats_missing.csv")

TARGET_SOURCE_ROWS = [
    {
        "player_name": "Isaiah Moses",
        "source_school": "Alaska Anchorage",
        "destination_school": "UC Riverside",
        "first_big_west_season": "2022-23",
        "expected_source_season": "2021-22",
    },
    {
        "player_name": "Guzmán Vasilić",
        "source_school": "Southeastern Oklahoma State",
        "destination_school": "Cal Poly",
        "first_big_west_season": "2024-25",
        "expected_source_season": "2023-24",
    },
    {
        "player_name": "E.J. Bryson",
        "source_school": "Azusa Pacific",
        "destination_school": "Cal State Bakersfield",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Malcolm Bell",
        "source_school": "Cal Poly Pomona",
        "destination_school": "Cal State Fullerton",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Matthew Willenborg",
        "source_school": "Central Oklahoma",
        "destination_school": "Cal State Fullerton",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Tiernan Stynes",
        "source_school": "Quincy",
        "destination_school": "Cal State Fullerton",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Jaden Matingou",
        "source_school": "Point Loma Nazarene",
        "destination_school": "Hawaii",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Brett Wright",
        "source_school": "Trevecca Nazarene",
        "destination_school": "Long Beach State",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Colin Ruffin",
        "source_school": "Missouri Southern",
        "destination_school": "Long Beach State",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Jaden Tengan",
        "source_school": "Cal State Monterey Bay",
        "destination_school": "Long Beach State",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Aidan Rice",
        "source_school": "Western Washington",
        "destination_school": "UC Riverside",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Easton Reagan",
        "source_school": "Northwest Nazarene",
        "destination_school": "UC Riverside",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
    {
        "player_name": "Tyus Parrish-Tillman",
        "source_school": "Biola",
        "destination_school": "UC Riverside",
        "first_big_west_season": "2026-27",
        "expected_source_season": "2025-26",
    },
]

SCHOOL_DOMAINS = {
    "Alaska Anchorage": "goseawolves.com",
    "Azusa Pacific": "athletics.apu.edu",
    "Cal Poly Pomona": "broncoathletics.com",
    "Central Oklahoma": "bronchosports.com",
    "Quincy": "quhawks.com",
    "Point Loma Nazarene": "plnusealions.com",
    "Trevecca Nazarene": "tnutrojans.com",
    "Missouri Southern": "mssulions.com",
    "Cal State Monterey Bay": "otterathletics.com",
    "Western Washington": "wwuvikings.com",
    "Northwest Nazarene": "nnusports.com",
    "Biola": "athletics.biola.edu",
}

SKIP_PLAYERS = {
    "Guzmán Vasilić": "Redshirt/did not play; no D2 source stat row expected",
    "Isaiah Moses": "2020-21 source season appears cancelled/no playable stat row",
}

MANUAL_PLAYER_ROWS = {
    "Malcolm Bell": {
        "row_name": "Bell, Malcolm",
        "source_url": "https://broncoathletics.com/sports/mens-basketball/stats/2025-26",
        "tokens": [
            "29",
            "29",
            "958",
            "33.0",
            "159",
            "400",
            ".398",
            "74",
            "202",
            ".366",
            "110",
            "125",
            ".880",
            "502",
            "17.3",
            "8",
            "59",
            "67",
            "2.3",
            "55",
            "63",
            "45",
            "29",
            "2",
        ],
    },
    "Jaden Tengan": {
        "row_name": "Tengan, Jaden",
        "source_url": "https://otterathletics.com/sports/mens-basketball/stats/2025-26",
        "tokens": [
            "29",
            "29",
            "912",
            "31.4",
            "149",
            "292",
            ".510",
            "29",
            "81",
            ".358",
            "100",
            "146",
            ".685",
            "427",
            "14.7",
            "46",
            "152",
            "198",
            "6.8",
            "69",
            "51",
            "77",
            "55",
            "9",
        ],
    },
}


def stats_url(school: str, season: str) -> str:
    return f"https://{SCHOOL_DOMAINS[school]}/sports/mens-basketball/stats/{season}"


def transfer_adapter(row: dict[str, str]) -> dict[str, str]:
    return {
        "player_name": row["player_name"],
        "d2_school": row["source_school"],
        "d2_conference": "",
        "position": "",
        "height": "",
        "class": "",
        "first_d1_season": row["first_big_west_season"],
        "d1_school": row["destination_school"],
    }


def main() -> int:
    source_rows = TARGET_SOURCE_ROWS
    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    cache: dict[str, str] = {}

    for source in source_rows:
        player_name = source["player_name"]
        season = source["expected_source_season"]
        source_url = ""
        try:
            manual = MANUAL_PLAYER_ROWS.get(player_name)
            if manual:
                rows.append(
                    build_row(
                        transfer_adapter(source),
                        str(manual["source_url"]),
                        list(manual["tokens"]),
                        season,
                    )
                )
                print(f"OK {player_name} [{manual['row_name']}] [manual]")
                continue
            if player_name in SKIP_PLAYERS:
                raise ValueError(SKIP_PLAYERS[player_name])
            source_url = stats_url(source["source_school"], season)
            if source_url not in cache:
                cache[source_url] = page_text(source_url)
                time.sleep(0.25)
            row_name, tokens = find_player_tokens(cache[source_url], player_name)
            rows.append(build_row(transfer_adapter(source), source_url, tokens, season))
            print(f"OK {player_name} [{row_name}]")
        except (KeyError, urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"MISS {player_name}: {error}")
            missing.append(
                {
                    "player_name": player_name,
                    "d2_school": source["source_school"],
                    "d2_conference": "",
                    "d1_school": source["destination_school"],
                    "first_d1_season": source["first_big_west_season"],
                    "d2_season": season,
                    "source_url": source_url,
                    "reason": str(error),
                }
            )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with MISSING_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MISSING_COLUMNS)
        writer.writeheader()
        writer.writerows(missing)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} missing rows to {MISSING_PATH}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
