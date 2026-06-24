#!/usr/bin/env python3
"""Join Big West transfer source stats to first-Big-West outcomes."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
SOURCE_STATS_PATH = Path("data/big_west_transfer_source_stats.csv")
OUTCOMES_PATH = Path("data/big_west_transfer_d1_outcomes.csv")
SCHOOL_OUTCOMES_PATH = Path("data/big_west_transfer_school_outcomes.csv")
MASSEY_POWER_PATHS = [
    Path("data/massey_conference_power.csv"),
    Path("data/massey_conference_ratings.csv"),
    Path("data/massey_power.csv"),
]
BARTTORVIK_OUTCOMES_PATH = Path("data/big_west_barttorvik_outcomes.csv")
OUTPUT_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
MISSING_PATH = Path("data/big_west_transfer_modeling_dataset_missing.csv")

OUTPUT_COLUMNS = [
    "player_name",
    "player_slug",
    "source_school",
    "source_school_slug",
    "source_conference",
    "source_level",
    "destination_school",
    "destination_school_slug",
    "first_big_west_season",
    "source_season",
    "source_stat_source",
    "position",
    "height_in",
    "weight_lbs",
    "source_conf_power",
    "destination_conf_power",
    "conf_power_delta",
    "source_games",
    "source_mpg",
    "source_minutes_share",
    "source_ppg",
    "source_rpg",
    "source_apg",
    "source_spg",
    "source_bpg",
    "source_topg",
    "source_fg_pct",
    "source_fg3_pct",
    "source_ft_pct",
    "source_efg_pct",
    "source_ts_pct",
    "source_three_rate",
    "source_ft_rate",
    "source_per",
    "source_usg_pct",
    "source_ws",
    "source_bpm",
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_stl_per_40",
    "source_blk_per_40",
    "source_tov_per_40",
    "big_west_games",
    "big_west_games_started",
    "big_west_mpg",
    "big_west_minutes",
    "big_west_minutes_share",
    "big_west_ppg",
    "big_west_rpg",
    "big_west_apg",
    "big_west_spg",
    "big_west_bpg",
    "big_west_topg",
    "big_west_ts_pct",
    "big_west_per",
    "big_west_usg_pct",
    "big_west_ws",
    "big_west_ws_per_40",
    "big_west_bpm",
    "big_west_porpag",
    "production_score",
    "impact_score",
    "outcome_tier",
    "source_url",
    "outcome_url",
]

MISSING_COLUMNS = [
    "player_name",
    "player_slug",
    "source_school",
    "source_level",
    "destination_school",
    "first_big_west_season",
    "missing_source_stats",
    "missing_outcome_stats",
    "reason",
]


def key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["player_slug"], row["destination_school_slug"], row["first_big_west_season"])


def number(value: str, fallback: float = 0.0) -> float:
    try:
        if value == "":
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def per_40(per_game: str, mpg: str) -> float:
    minutes = number(mpg)
    return number(per_game) * 40 / minutes if minutes else 0.0


def optional_number(value: str) -> float | str:
    return number(value) if value != "" else ""


def normalize(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def possible_columns(row: dict[str, str], names: list[str]) -> str:
    lowered = {normalize(key).replace(" ", "_"): key for key in row}
    for name in names:
        key = lowered.get(normalize(name).replace(" ", "_"))
        if key:
            return row.get(key, "")
    return ""


def load_massey_power() -> dict[tuple[str, str], float]:
    for path in MASSEY_POWER_PATHS:
        if not path.exists():
            continue
        power: dict[tuple[str, str], float] = {}
        with path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                season = possible_columns(row, ["season", "year", "season_start"])
                conference = possible_columns(row, ["conference", "conf", "source_conference"])
                value = possible_columns(row, ["power", "conference_power", "rating", "massey_power"])
                if not season or not conference or value == "":
                    continue
                if len(season) == 4:
                    season = f"{season}-{str(int(season) + 1)[-2:]}"
                power[(season, normalize(conference))] = number(value)
        return power
    return {}


def load_barttorvik_outcomes() -> dict[tuple[str, str, str], dict[str, str]]:
    if not BARTTORVIK_OUTCOMES_PATH.exists():
        return {}
    rows = {}
    with BARTTORVIK_OUTCOMES_PATH.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            player_slug = possible_columns(row, ["player_slug", "slug"])
            destination_slug = possible_columns(row, ["destination_school_slug", "school_slug", "team_slug"])
            season = possible_columns(row, ["first_big_west_season", "season", "year"])
            if player_slug and destination_slug and season:
                rows[(player_slug, destination_slug, season)] = row
    return rows


def conference_power(
    power: dict[tuple[str, str], float],
    season: str,
    conference: str,
) -> float | str:
    if not power:
        return ""
    key = (season, normalize(conference))
    return power.get(key, "")


def percentile_map(rows: list[dict[str, object]], column: str) -> dict[tuple[str, str, str], float]:
    by_value: dict[float, list[dict[str, object]]] = {}
    for row in rows:
        by_value.setdefault(float(row[column]), []).append(row)
    ordered_values = sorted(by_value)
    if len(rows) == 1:
        return {key(rows[0]): 50.0}  # type: ignore[arg-type]

    percentiles: dict[tuple[str, str, str], float] = {}
    start_index = 0
    for value in ordered_values:
        tied_rows = by_value[value]
        end_index = start_index + len(tied_rows) - 1
        average_index = (start_index + end_index) / 2
        percentile = (average_index / (len(rows) - 1)) * 100
        for row in tied_rows:
            percentiles[key(row)] = percentile  # type: ignore[arg-type]
        start_index = end_index + 1
    return percentiles


def outcome_tier(score: float) -> str:
    if score >= 80:
        return "Big West impact starter"
    if score >= 65:
        return "Big West starter/plus rotation"
    if score >= 45:
        return "Big West rotation"
    return "Limited Big West role"


def build_row(
    transfer: dict[str, str],
    source: dict[str, str],
    outcome: dict[str, str],
    massey_power: dict[tuple[str, str], float],
    barttorvik_outcomes: dict[tuple[str, str, str], dict[str, str]],
) -> dict[str, object]:
    bw_ppg = number(outcome["ppg"])
    bw_rpg = number(outcome["rpg"])
    bw_apg = number(outcome["apg"])
    bw_spg = number(outcome["spg"])
    bw_bpg = number(outcome["bpg"])
    bw_topg = number(outcome["topg"])
    production_score = bw_ppg + 0.7 * bw_rpg + 0.7 * bw_apg + 0.7 * bw_spg + 0.7 * bw_bpg - 0.5 * bw_topg
    source_conf_power = conference_power(massey_power, source["source_season"], source["source_conference"])
    destination_conf_power = conference_power(
        massey_power,
        source["first_big_west_season"],
        outcome.get("sr_conf") or transfer.get("destination_conference", ""),
    )
    if source_conf_power != "" and destination_conf_power != "":
        conf_power_delta: float | str = number(str(destination_conf_power)) - number(str(source_conf_power))
    else:
        conf_power_delta = ""
    barttorvik = barttorvik_outcomes.get(key(transfer), {})
    porpag = possible_columns(barttorvik, ["porpag", "big_west_porpag", "prpg", "porp"])

    return {
        "player_name": source["player_name"],
        "player_slug": source["player_slug"],
        "source_school": source["source_school"],
        "source_school_slug": source["source_school_slug"],
        "source_conference": source["source_conference"],
        "source_level": source["source_level"],
        "destination_school": source["destination_school"],
        "destination_school_slug": source["destination_school_slug"],
        "first_big_west_season": source["first_big_west_season"],
        "source_season": source["source_season"],
        "source_stat_source": source["source_stat_source"],
        "position": source["position"] or outcome["position"],
        "height_in": optional_number(transfer.get("height", "")),
        "weight_lbs": optional_number(transfer.get("weight", "")),
        "source_conf_power": source_conf_power,
        "destination_conf_power": destination_conf_power,
        "conf_power_delta": conf_power_delta,
        "source_games": int(number(source["games"])),
        "source_mpg": number(source["mpg"]),
        "source_minutes_share": number(source["minutes_share"]),
        "source_ppg": number(source["ppg"]),
        "source_rpg": number(source["rpg"]),
        "source_apg": number(source["apg"]),
        "source_spg": number(source["spg"]),
        "source_bpg": number(source["bpg"]),
        "source_topg": number(source["topg"]),
        "source_fg_pct": number(source["fg_pct"]),
        "source_fg3_pct": number(source["fg3_pct"]),
        "source_ft_pct": number(source["ft_pct"]),
        "source_efg_pct": number(source["efg_pct"]),
        "source_ts_pct": number(source["ts_pct"]),
        "source_three_rate": number(source["three_rate"]),
        "source_ft_rate": number(source["ft_rate"]),
        "source_per": optional_number(source["per"]),
        "source_usg_pct": optional_number(source["usg_pct"]),
        "source_ws": optional_number(source["ws"]),
        "source_bpm": optional_number(source["bpm"]),
        "source_pts_per_40": per_40(source["ppg"], source["mpg"]),
        "source_reb_per_40": per_40(source["rpg"], source["mpg"]),
        "source_ast_per_40": per_40(source["apg"], source["mpg"]),
        "source_stl_per_40": per_40(source["spg"], source["mpg"]),
        "source_blk_per_40": per_40(source["bpg"], source["mpg"]),
        "source_tov_per_40": per_40(source["topg"], source["mpg"]),
        "big_west_games": int(number(outcome["games"])),
        "big_west_games_started": int(number(outcome["games_started"])),
        "big_west_mpg": number(outcome["mpg"]),
        "big_west_minutes": number(outcome["minutes"]),
        "big_west_minutes_share": number(outcome["minutes_share"]),
        "big_west_ppg": bw_ppg,
        "big_west_rpg": bw_rpg,
        "big_west_apg": bw_apg,
        "big_west_spg": bw_spg,
        "big_west_bpg": bw_bpg,
        "big_west_topg": bw_topg,
        "big_west_ts_pct": number(outcome["ts_pct"]),
        "big_west_per": number(outcome["per"]),
        "big_west_usg_pct": number(outcome["usg_pct"]),
        "big_west_ws": number(outcome["ws"]),
        "big_west_ws_per_40": number(outcome["ws_per_40"]),
        "big_west_bpm": number(outcome["bpm"]),
        "big_west_porpag": optional_number(porpag),
        "production_score": production_score,
        "impact_score": 0.0,
        "outcome_tier": "",
        "source_url": source["source_url"],
        "outcome_url": outcome["source_url"],
    }


def missing_row(transfer: dict[str, str], has_source: bool, has_outcome: bool) -> dict[str, str]:
    reasons = []
    if not has_source:
        reasons.append("missing_source_stats")
    if not has_outcome:
        reasons.append("missing_big_west_outcome")
    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "source_school": transfer["source_school"],
        "source_level": transfer["source_level"],
        "destination_school": transfer["destination_school"],
        "first_big_west_season": transfer["first_big_west_season"],
        "missing_source_stats": "FALSE" if has_source else "TRUE",
        "missing_outcome_stats": "FALSE" if has_outcome else "TRUE",
        "reason": ";".join(reasons),
    }


def main() -> int:
    transfers = list(csv.DictReader(TRANSFERS_PATH.open(newline="", encoding="utf-8")))
    sources = {key(row): row for row in csv.DictReader(SOURCE_STATS_PATH.open(newline="", encoding="utf-8"))}
    outcomes = {key(row): row for row in csv.DictReader(OUTCOMES_PATH.open(newline="", encoding="utf-8"))}
    massey_power = load_massey_power()
    barttorvik_outcomes = load_barttorvik_outcomes()
    if SCHOOL_OUTCOMES_PATH.exists():
        school_outcomes = {
            key(row): row
            for row in csv.DictReader(SCHOOL_OUTCOMES_PATH.open(newline="", encoding="utf-8"))
        }
        outcomes = {**school_outcomes, **outcomes}

    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    for transfer in transfers:
        transfer_key = key(transfer)
        source = sources.get(transfer_key)
        outcome = outcomes.get(transfer_key)
        if source and outcome:
            rows.append(build_row(transfer, source, outcome, massey_power, barttorvik_outcomes))
        else:
            missing.append(missing_row(transfer, bool(source), bool(outcome)))

    if rows:
        production_pct = percentile_map(rows, "production_score")
        minutes_pct = percentile_map(rows, "big_west_minutes_share")
        bpm_pct = percentile_map(rows, "big_west_bpm")
        ws_pct = percentile_map(rows, "big_west_ws")
        for row in rows:
            row_key = key(row)  # type: ignore[arg-type]
            impact = (
                0.35 * minutes_pct[row_key]
                + 0.25 * bpm_pct[row_key]
                + 0.20 * ws_pct[row_key]
                + 0.20 * production_pct[row_key]
            )
            row["impact_score"] = impact
            row["outcome_tier"] = outcome_tier(impact)
        rows.sort(key=lambda row: float(row["impact_score"]), reverse=True)

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
