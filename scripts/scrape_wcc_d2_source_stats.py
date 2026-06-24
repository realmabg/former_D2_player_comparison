#!/usr/bin/env python3
"""Scrape WCC D2/non-major source rows from official school stat pages."""

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


OUTPUT_PATH = Path("data/wcc_d2_source_stats.csv")
MISSING_PATH = Path("data/wcc_d2_source_stats_missing.csv")

TARGET_SOURCE_ROWS = [
    {
        "player_name": "Tredyn Christensen",
        "source_school": "Chaminade",
        "source_conference": "PacWest",
        "destination_school": "BYU",
        "first_wcc_season": "2022-23",
        "expected_source_season": "2021-22",
        "source_url": "https://goswords.com/sports/mens-basketball/stats/2021-22",
    },
    {
        "player_name": "Alex Leiba",
        "source_school": "Penn State Harrisburg",
        "source_conference": "United East",
        "destination_school": "Pepperdine",
        "first_wcc_season": "2024-25",
        "expected_source_season": "2023-24",
        "source_url": "https://psuharrisburgsports.com/sports/mens-basketball/stats/2023-24",
    },
    {
        "player_name": "Noah Jordan",
        "source_school": "West Virginia State",
        "source_conference": "Mountain East",
        "destination_school": "Portland",
        "first_wcc_season": "2023-24",
        "expected_source_season": "2022-23",
        "source_url": "https://wvsuyellowjackets.com/sports/mens-basketball/stats/2022-23",
    },
    {
        "player_name": "Elliyas Delaire",
        "source_school": "Lewis & Clark",
        "source_conference": "Northwest",
        "destination_school": "San Diego",
        "first_wcc_season": "2022-23",
        "expected_source_season": "2021-22",
        "source_url": "https://lcpioneers.com/sports/mens-basketball/stats/2021-22",
    },
    {
        "player_name": "PJ Hayes",
        "source_school": "Black Hills State",
        "source_conference": "RMAC",
        "destination_school": "San Diego",
        "first_wcc_season": "2023-24",
        "expected_source_season": "2022-23",
        "source_url": "https://bhsuathletics.com/sports/mens-basketball/stats/2022-23",
    },
    {
        "player_name": "Kody Clouet",
        "source_school": "Southeastern Oklahoma State",
        "source_conference": "GAC",
        "destination_school": "San Diego",
        "first_wcc_season": "2024-25",
        "expected_source_season": "2023-24",
        "source_url": "https://gosoutheastern.com/sports/mens-basketball/stats/2023-24",
    },
]


def transfer_adapter(row: dict[str, str]) -> dict[str, str]:
    return {
        "player_name": row["player_name"],
        "d2_school": row["source_school"],
        "d2_conference": row["source_conference"],
        "position": "",
        "height": "",
        "class": "",
        "first_d1_season": row["first_wcc_season"],
        "d1_school": row["destination_school"],
    }


def main() -> int:
    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    cache: dict[str, str] = {}

    for source in TARGET_SOURCE_ROWS:
        player_name = source["player_name"]
        source_url = source["source_url"]
        season = source["expected_source_season"]
        try:
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
                    "d2_conference": source["source_conference"],
                    "d1_school": source["destination_school"],
                    "first_d1_season": source["first_wcc_season"],
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
