#!/usr/bin/env python3
"""Build a prioritized queue for remaining Big West transfer source stats."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from build_big_west_transfer_source_stats import (
    cached_player_pages,
    cached_source_school_page,
    choose_school_player_row,
    choose_source_row,
    page_matches_player,
    parse_table_rows,
    previous_season,
)

TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
SOURCE_STATS_PATH = Path("data/big_west_transfer_source_stats.csv")
SOURCE_MISSING_PATH = Path("data/big_west_transfer_source_stats_missing.csv")
SPORTS_REFERENCE_OUTCOMES_PATH = Path("data/big_west_transfer_d1_outcomes.csv")
SCHOOL_OUTCOMES_PATH = Path("data/big_west_transfer_school_outcomes.csv")
OUTPUT_PATH = Path("data/big_west_source_stats_work_queue.csv")
SUPPORTED_SOURCE_LEVELS = {"D1", "D2", "JUCO", "NAIA"}

OUTPUT_COLUMNS = [
    "priority",
    "player_name",
    "player_slug",
    "source_school",
    "source_school_slug",
    "source_level",
    "destination_school",
    "destination_school_slug",
    "first_big_west_season",
    "expected_source_season",
    "has_big_west_outcome",
    "model_training_window",
    "local_cache_status",
    "recommended_next_step",
    "current_missing_reason",
    "source_url",
]


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["player_slug"], row["destination_school_slug"], row["first_big_west_season"])


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def source_cache_status(transfer: dict[str, str]) -> str:
    if transfer["source_level"] != "D1":
        return ""

    expected_season = previous_season(transfer["first_big_west_season"])
    school_page = cached_source_school_page(transfer["source_school_slug"], expected_season)
    if school_page:
        path, _source_url = school_page
        page_html = path.read_text(encoding="utf-8")
        per_game_rows = parse_table_rows(page_html, "players_per_game")
        if choose_school_player_row(per_game_rows, transfer["player_name"]):
            return "parseable_local_source_school_page"
        return "source_school_page_cached_no_player_row"

    matched_page = False
    for path, _source_url in cached_player_pages():
        if not page_matches_player(path, _source_url, transfer):
            continue
        matched_page = True
        page_html = path.read_text(encoding="utf-8")
        per_game_rows = parse_table_rows(page_html, "players_per_game")
        if choose_source_row(per_game_rows, expected_season, transfer["source_school"]):
            return "parseable_local_player_page"
    return "local_page_no_matching_source_row" if matched_page else "no_local_player_page"


def recommended_next_step(source_level: str, cache_status: str, has_outcome: bool) -> str:
    if cache_status in {"parseable_local_player_page", "parseable_local_source_school_page"}:
        return "rerun_source_builder"
    if cache_status == "source_school_page_cached_no_player_row":
        return "review_transfer_timing_or_no_source_stats"
    if source_level == "D1":
        return "fetch_sports_reference_later_or_use_source_school_page"
    if source_level == "JUCO":
        return "manual_juco_or_official_school_page"
    if source_level == "D2":
        return "manual_d2_school_page_or_confirm_no_stat_row"
    if source_level == "NAIA":
        return "manual_naia_or_official_school_page"
    return "review_source_level"


def priority(row: dict[str, str], has_outcome: bool) -> int:
    if row.get("model_training_window") != "TRUE":
        return 5
    if has_outcome and row["source_level"] == "D1":
        return 1
    if has_outcome:
        return 2
    if row["source_level"] == "D1":
        return 3
    return 4


def main() -> int:
    transfers = {row_key(row): row for row in load_rows(TRANSFERS_PATH)}
    existing_source_keys = {row_key(row) for row in load_rows(SOURCE_STATS_PATH)}
    missing_source = [row for row in load_rows(SOURCE_MISSING_PATH) if row_key(row) not in existing_source_keys]

    outcome_keys = {
        row_key(row)
        for path in [SPORTS_REFERENCE_OUTCOMES_PATH, SCHOOL_OUTCOMES_PATH]
        for row in load_rows(path)
    }

    rows: list[dict[str, str | int]] = []
    for missing in missing_source:
        transfer = transfers[row_key(missing)]
        if transfer["source_level"] not in SUPPORTED_SOURCE_LEVELS:
            continue
        has_outcome = row_key(missing) in outcome_keys
        cache_status = source_cache_status(transfer)
        rows.append(
            {
                "priority": priority(transfer, has_outcome),
                "player_name": transfer["player_name"],
                "player_slug": transfer["player_slug"],
                "source_school": transfer["source_school"],
                "source_school_slug": transfer["source_school_slug"],
                "source_level": transfer["source_level"],
                "destination_school": transfer["destination_school"],
                "destination_school_slug": transfer["destination_school_slug"],
                "first_big_west_season": transfer["first_big_west_season"],
                "expected_source_season": missing["expected_source_season"],
                "has_big_west_outcome": "TRUE" if has_outcome else "FALSE",
                "model_training_window": transfer["model_training_window"],
                "local_cache_status": cache_status,
                "recommended_next_step": recommended_next_step(transfer["source_level"], cache_status, has_outcome),
                "current_missing_reason": missing["reason"],
                "source_url": transfer["source_url"],
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["priority"]),
            row["source_level"],
            row["first_big_west_season"],
            row["destination_school"],
            row["player_name"],
        )
    )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
