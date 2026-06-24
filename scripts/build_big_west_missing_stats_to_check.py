#!/usr/bin/env python3
"""Build a focused checklist of D1/D2 model candidates still missing stats."""

from __future__ import annotations

import csv
import html
import re
import sys
import unicodedata
from pathlib import Path

from scrape_phase1_d1_outcomes import parse_table_rows


TRANSFER_MISSING_PATH = Path("data/big_west_transfer_modeling_dataset_missing.csv")
MODELING_DATASET_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
LAGGED_OUTCOME_PATH = Path("data/big_west_first_playable_outcome_audit.csv")
EXCLUSIONS_PATH = Path("data/big_west_first_model_exclusions.csv")
ROSTER_DIFF_PATH = Path("data/big_west_roster_diff_possible_missing_transfers.csv")
ROSTER_DIFF_D1_SOURCE_PATH = Path("data/big_west_roster_diff_d1_source_stats_found.csv")
BIG_WEST_SCHOOL_CACHE = Path("data/cache/sports_reference_big_west_schools")
SOURCE_WORK_QUEUE_PATH = Path("data/big_west_source_stats_work_queue.csv")
OUTPUT_PATH = Path("data/big_west_model_missing_stats_to_check_now.csv")
RAW_OUTPUT_PATH = Path("data/big_west_model_players_missing_before_or_after_stats.csv")

OUTPUT_COLUMNS = [
    "bucket",
    "player_name",
    "player_slug",
    "source_school_or_label",
    "source_level",
    "destination_school",
    "destination_school_slug",
    "listed_first_big_west_season",
    "first_playable_big_west_season_found",
    "missing_before_source_stats",
    "missing_after_big_west_stats",
    "missing_summary",
    "known_later_games",
    "known_later_mpg",
    "known_later_ppg",
    "recommended_action",
    "lookup_notes",
    "source_url",
    "evidence_or_cache",
]


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", html.unescape(str(value))).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def season_end_year(season: str) -> int:
    return int(season.split("-", 1)[0]) + 1


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["player_slug"], row["destination_school"], row["first_big_west_season"])


def finding_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (normalize(row["player_name"]), normalize(row["destination_school"]), row["first_big_west_season"])


def exclusion_keys() -> set[tuple[str, str, str]]:
    keys = set()
    for row in load_rows(EXCLUSIONS_PATH):
        if row.get("next_action", "").startswith("exclude"):
            keys.add(finding_key(row))
    return keys


def source_work_queue_lookup() -> dict[tuple[str, str, str], dict[str, str]]:
    lookup = {}
    for row in load_rows(SOURCE_WORK_QUEUE_PATH):
        lookup[(normalize(row["player_name"]), normalize(row["destination_school"]), row["first_big_west_season"])] = row
    return lookup


def modeled_transfer_keys() -> set[tuple[str, str, str]]:
    return {
        (normalize(row["player_name"]), normalize(row["destination_school"]), row["first_big_west_season"])
        for row in load_rows(MODELING_DATASET_PATH)
    }


def sports_reference_big_west_stat(player_name: str, destination_slug: str, season: str) -> tuple[bool, str, str]:
    if not destination_slug:
        return False, "", ""
    cache_path = BIG_WEST_SCHOOL_CACHE / f"{destination_slug}_{season_end_year(season)}.html"
    if not cache_path.exists():
        return False, "", ""
    rows = parse_table_rows(cache_path.read_text(encoding="utf-8"), "players_per_game")
    wanted = normalize(player_name)
    for row in rows:
        if normalize(row.get("name_display", "")) != wanted:
            continue
        try:
            games = int(float(row.get("games", "") or "0"))
        except ValueError:
            games = 0
        if games > 0:
            return True, str(games), str(cache_path)
    return False, "", str(cache_path)


def action(missing_before: bool, missing_after: str, later_outcome: bool) -> str:
    if missing_before and missing_after == "TRUE":
        return "find source stats and Big West outcome stats"
    if missing_before and later_outcome:
        return "find source stats; later Big West outcome already found"
    if missing_before and missing_after == "NOT_ACTIONABLE_FUTURE_SEASON":
        return "find source stats now; Big West outcome unavailable until 2026-27 season is played"
    if missing_before:
        return "find source stats"
    if missing_after == "TRUE":
        return "find Big West outcome stats or confirm DNP/injury/no stats"
    return "review row"


def existing_transfer_rows(include_future_outcome_only: bool) -> list[dict[str, str]]:
    transfers = {row_key(row): row for row in load_rows(TRANSFERS_PATH)}
    lagged = {row_key(row): row for row in load_rows(LAGGED_OUTCOME_PATH)}
    excluded = exclusion_keys()
    work_queue = source_work_queue_lookup()
    rows = []

    for missing in load_rows(TRANSFER_MISSING_PATH):
        if missing["source_level"] not in {"D1", "D2"}:
            continue
        if finding_key(missing) in excluded:
            continue
        transfer = transfers.get(row_key(missing), {})
        lag = lagged.get(row_key(missing), {})
        work = work_queue.get(finding_key(missing), {})
        has_source = missing["missing_source_stats"] == "FALSE"
        has_first_outcome = missing["missing_outcome_stats"] == "FALSE"
        has_later_outcome = bool(lag.get("first_playable_big_west_season"))
        if has_source and (has_first_outcome or has_later_outcome):
            continue

        future = missing["first_big_west_season"] == "2026-27"
        missing_before = not has_source
        missing_after = not has_first_outcome and not has_later_outcome
        if future and missing_after and not missing_before and not include_future_outcome_only:
            continue

        missing_after_value = "TRUE" if missing_after else "FALSE"
        summary_parts = []
        if missing_before:
            summary_parts.append("before_source_stats")
        if missing_after:
            summary_parts.append("after_big_west_outcome_stats")
        if missing_before and has_later_outcome:
            summary_parts.append("before_source_stats_only_later_outcome_found")
        if future and missing_before and missing_after:
            missing_after_value = "NOT_ACTIONABLE_FUTURE_SEASON"
            summary_parts = [part for part in summary_parts if part != "after_big_west_outcome_stats"]

        rows.append(
            {
                "bucket": "existing_transfer_missing_stats",
                "player_name": missing["player_name"],
                "player_slug": missing["player_slug"],
                "source_school_or_label": missing["source_school"],
                "source_level": missing["source_level"],
                "destination_school": missing["destination_school"],
                "destination_school_slug": transfer.get("destination_school_slug", ""),
                "listed_first_big_west_season": missing["first_big_west_season"],
                "first_playable_big_west_season_found": lag.get("first_playable_big_west_season", ""),
                "missing_before_source_stats": "TRUE" if missing_before else "FALSE",
                "missing_after_big_west_stats": missing_after_value,
                "missing_summary": ";".join(dict.fromkeys(summary_parts)),
                "known_later_games": lag.get("games", ""),
                "known_later_mpg": lag.get("mpg", ""),
                "known_later_ppg": lag.get("ppg", ""),
                "recommended_action": action(missing_before, missing_after_value, has_later_outcome),
                "lookup_notes": (
                    f"Sports Reference source-school cache status: {work.get('local_cache_status', '')}; "
                    f"current source reason: {work.get('current_missing_reason', '')}"
                    if missing_before and work
                    else ""
                ),
                "source_url": transfer.get("source_url", ""),
                "evidence_or_cache": lag.get("sports_reference_school_cache", ""),
            }
        )
    return rows


def roster_diff_rows(include_future_outcome_only: bool) -> list[dict[str, str]]:
    d1_source_found = {
        (row["player_name"], row["destination_school"], row["first_big_west_season"])
        for row in load_rows(ROSTER_DIFF_D1_SOURCE_PATH)
    }
    already_modeled = modeled_transfer_keys()
    rows = []
    for row in load_rows(ROSTER_DIFF_PATH):
        key = (normalize(row["player_name"]), normalize(row["destination_school"]), row["first_big_west_season"])
        if key in already_modeled:
            continue
        level = row["profile_prior_level_guess"]
        if level not in {"D1", "D2"}:
            continue
        has_source = (row["player_name"], row["destination_school"], row["first_big_west_season"]) in d1_source_found
        if level == "D2":
            has_source = False
        has_after, games, cache = sports_reference_big_west_stat(
            row["player_name"], row.get("destination_school_slug", ""), row["first_big_west_season"]
        )
        future = row["first_big_west_season"] == "2026-27"
        if has_source and has_after:
            continue
        if future and not has_source and has_after:
            pass
        elif future and not has_source:
            pass
        elif future and not include_future_outcome_only:
            continue

        missing_after_value = "FALSE" if has_after else "TRUE"
        parts = []
        if not has_source:
            parts.append("before_source_stats")
        if not has_after:
            parts.append("after_big_west_outcome_stats")
        if future and not has_source and not has_after:
            missing_after_value = "NOT_ACTIONABLE_FUTURE_SEASON"
            parts = [part for part in parts if part != "after_big_west_outcome_stats"]

        rows.append(
            {
                "bucket": "roster_diff_candidate_missing_stats",
                "player_name": row["player_name"],
                "player_slug": "",
                "source_school_or_label": row["profile_prior_school"],
                "source_level": level,
                "destination_school": row["destination_school"],
                "destination_school_slug": row.get("destination_school_slug", ""),
                "listed_first_big_west_season": row["first_big_west_season"],
                "first_playable_big_west_season_found": "",
                "missing_before_source_stats": "TRUE" if not has_source else "FALSE",
                "missing_after_big_west_stats": missing_after_value,
                "missing_summary": ";".join(parts),
                "known_later_games": games,
                "known_later_mpg": "",
                "known_later_ppg": "",
                "recommended_action": action(not has_source, missing_after_value, False),
                "lookup_notes": (
                    "Sports Reference profile checked: prior row is only 'Did not play - non-major team'; "
                    "direct Verbal Commits lookup was blocked/returned no indexed result"
                    if level == "D2"
                    else ""
                ),
                "source_url": row["sports_reference_player_url"],
                "evidence_or_cache": cache,
            }
        )
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    rows.sort(
        key=lambda row: (
            row["bucket"],
            row["source_level"],
            row["listed_first_big_west_season"],
            row["destination_school"],
            row["player_name"],
        )
    )
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    raw_rows = existing_transfer_rows(include_future_outcome_only=True) + roster_diff_rows(include_future_outcome_only=True)
    check_now_rows = existing_transfer_rows(include_future_outcome_only=False) + roster_diff_rows(include_future_outcome_only=False)
    write_rows(RAW_OUTPUT_PATH, raw_rows)
    write_rows(OUTPUT_PATH, check_now_rows)
    print(f"Wrote {len(raw_rows)} rows to {RAW_OUTPUT_PATH}")
    print(f"Wrote {len(check_now_rows)} rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
