#!/usr/bin/env python3
"""Find later Big West seasons for transfers missing first-year outcome stats."""

from __future__ import annotations

import csv
import html
import re
import sys
import unicodedata
from pathlib import Path

from scrape_phase1_d1_outcomes import parse_table_rows


TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
SOURCE_STATS_PATH = Path("data/big_west_transfer_source_stats.csv")
SPORTS_REFERENCE_OUTCOMES_PATH = Path("data/big_west_transfer_d1_outcomes.csv")
SCHOOL_OUTCOMES_PATH = Path("data/big_west_transfer_school_outcomes.csv")
BIG_WEST_CACHE_DIR = Path("data/cache/sports_reference_big_west_schools")
OUTPUT_PATH = Path("data/big_west_first_playable_outcome_audit.csv")

OUTPUT_COLUMNS = [
    "player_name",
    "player_slug",
    "source_school",
    "source_level",
    "destination_school",
    "destination_school_slug",
    "first_big_west_season",
    "has_source_stats",
    "has_first_year_outcome",
    "first_playable_big_west_season",
    "outcome_lag_years",
    "games",
    "games_started",
    "mpg",
    "ppg",
    "rpg",
    "apg",
    "spg",
    "bpg",
    "topg",
    "fg_pct",
    "fg3_pct",
    "ft_pct",
    "efg_pct",
    "sports_reference_school_cache",
    "recommended_action",
]


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", html.unescape(str(value)))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["player_slug"], row["destination_school_slug"], row["first_big_west_season"])


def season_end_year(season: str) -> int:
    start = int(season.split("-", 1)[0])
    return start + 1


def season_from_end_year(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def row_games(row: dict[str, str]) -> int:
    try:
        return int(float(row.get("games", "0") or "0"))
    except ValueError:
        return 0


def load_outcome_keys() -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for path in [SPORTS_REFERENCE_OUTCOMES_PATH, SCHOOL_OUTCOMES_PATH]:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as file:
            keys.update(key(row) for row in csv.DictReader(file))
    return keys


def load_source_keys() -> set[tuple[str, str, str]]:
    if not SOURCE_STATS_PATH.exists():
        return set()
    with SOURCE_STATS_PATH.open(newline="", encoding="utf-8") as file:
        return {key(row) for row in csv.DictReader(file)}


def player_row_for_later_season(transfer: dict[str, str], end_year: int) -> tuple[dict[str, str], Path | None]:
    cache_path = BIG_WEST_CACHE_DIR / f"{transfer['destination_school_slug']}_{end_year}.html"
    if not cache_path.exists():
        return {}, None
    rows = parse_table_rows(cache_path.read_text(encoding="utf-8"), "players_per_game")
    wanted = normalize(transfer["player_name"])
    for row in rows:
        if normalize(row.get("name_display", "")) == wanted and row_games(row) > 0:
            return row, cache_path
    return {}, cache_path


def build_output_row(
    transfer: dict[str, str],
    has_source: bool,
    has_first_outcome: bool,
    stat_row: dict[str, str],
    cache_path: Path | None,
    playable_season: str,
) -> dict[str, str]:
    lag = season_end_year(playable_season) - season_end_year(transfer["first_big_west_season"]) if playable_season else ""
    if has_first_outcome:
        action = "already_has_first_year_outcome"
    elif playable_season and has_source:
        action = "can_use_first_playable_outcome_after_lag_review"
    elif playable_season:
        action = "later_outcome_found_but_source_stats_missing"
    else:
        action = "no_later_big_west_stats_found_in_cached_sports_reference_pages"
    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "source_school": transfer["source_school"],
        "source_level": transfer["source_level"],
        "destination_school": transfer["destination_school"],
        "destination_school_slug": transfer["destination_school_slug"],
        "first_big_west_season": transfer["first_big_west_season"],
        "has_source_stats": "TRUE" if has_source else "FALSE",
        "has_first_year_outcome": "TRUE" if has_first_outcome else "FALSE",
        "first_playable_big_west_season": playable_season,
        "outcome_lag_years": str(lag),
        "games": stat_row.get("games", ""),
        "games_started": stat_row.get("games_started", ""),
        "mpg": stat_row.get("mp_per_g", ""),
        "ppg": stat_row.get("pts_per_g", ""),
        "rpg": stat_row.get("trb_per_g", ""),
        "apg": stat_row.get("ast_per_g", ""),
        "spg": stat_row.get("stl_per_g", ""),
        "bpg": stat_row.get("blk_per_g", ""),
        "topg": stat_row.get("tov_per_g", ""),
        "fg_pct": stat_row.get("fg_pct", ""),
        "fg3_pct": stat_row.get("fg3_pct", ""),
        "ft_pct": stat_row.get("ft_pct", ""),
        "efg_pct": stat_row.get("efg_pct", ""),
        "sports_reference_school_cache": str(cache_path or ""),
        "recommended_action": action,
    }


def main() -> int:
    transfers = list(csv.DictReader(TRANSFERS_PATH.open(newline="", encoding="utf-8")))
    outcome_keys = load_outcome_keys()
    source_keys = load_source_keys()
    rows: list[dict[str, str]] = []

    for transfer in transfers:
        transfer_key = key(transfer)
        has_first_outcome = transfer_key in outcome_keys
        if has_first_outcome:
            continue
        start_end_year = season_end_year(transfer["first_big_west_season"])
        if start_end_year > 2026:
            continue
        found_row: dict[str, str] = {}
        found_cache: Path | None = None
        found_season = ""
        for end_year in range(start_end_year + 1, 2027):
            stat_row, cache_path = player_row_for_later_season(transfer, end_year)
            if stat_row:
                found_row = stat_row
                found_cache = cache_path
                found_season = season_from_end_year(end_year)
                break
            found_cache = cache_path or found_cache
        rows.append(
            build_output_row(
                transfer,
                transfer_key in source_keys,
                has_first_outcome,
                found_row,
                found_cache,
                found_season,
            )
        )

    rows.sort(key=lambda row: (row["recommended_action"], row["first_big_west_season"], row["destination_school"], row["player_name"]))
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} first-playable outcome audit rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
