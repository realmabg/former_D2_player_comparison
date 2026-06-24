#!/usr/bin/env python3
"""Adapt combined target-conference rows to the existing Big West model schema."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


INPUT_PATH = Path("data/target_conference_transfer_modeling_dataset.csv")
OUTPUT_PATH = Path("data/target_conference_transfer_modeling_big_west_schema.csv")
MASSEY_POWER_PATH = Path("data/massey_conference_power.csv")


OUTPUT_COLUMNS = [
    "target_conference",
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
    "source_conf_power_method",
    "destination_conf_power",
    "destination_conf_power_method",
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


def number(value: object, fallback: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def normalize(value: object) -> str:
    import re

    text = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    return CONFERENCE_ALIASES.get(text, text)


CONFERENCE_ALIASES = {
    "a 10": "atlantic 10",
    "a sun": "asun",
    "aac": "american",
    "acc": "atlantic coast",
    "ameast": "america east",
    "america east": "america east",
    "american": "american",
    "big 12": "big xii",
    "big ten": "big 10",
    "big 10": "big ten",
    "big xii": "big xii",
    "bw": "big west",
    "c usa": "c usa",
    "caa": "colonial",
    "colonial athletic": "colonial",
    "cusa": "c usa",
    "lsc": "lone star",
    "maac": "metro atlantic",
    "meac": "mid eastern ac",
    "mec": "mountain east",
    "missouri val": "missouri valley",
    "mvc": "missouri valley",
    "mwc": "mountain west",
    "nec": "northeast",
    "ovc": "ohio valley",
    "pac 12": "pac 12",
    "pacwest": "pacific west",
    "patriot": "patriot league",
    "rmac": "rocky mtn ac",
    "sciac": "southern cal iac",
    "sec": "southeastern",
    "summit": "summit league",
    "wcc": "west coast",
}

MASSEY_CONFERENCE_ALIASES = {
    "america east": "america east",
    "c usa": "c usa",
    "mountain east": "mountain east",
    "northwest": "northwest",
    "united east": "united east",
    "wcc": "west coast",
}


TARGET_CONFERENCE_TO_MASSEY = {
    "American": "American",
    "Atlantic 10": "Atlantic 10",
    "Big West": "Big West",
    "Missouri Valley": "Missouri Valley",
    "Mountain West": "Mountain West",
    "WCC": "West Coast",
}


def load_massey_power() -> dict[tuple[str, str], float]:
    if not MASSEY_POWER_PATH.exists():
        return {}
    power: dict[tuple[str, str], float] = {}
    with MASSEY_POWER_PATH.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            season = str(row.get("season", "")).strip()
            conference = normalize(row.get("conference", ""))
            value = row.get("power", "")
            if season and conference and value != "":
                power[(season, conference)] = number(value)
    return power


def season_start_year(season: str) -> int | None:
    try:
        return int(str(season).split("-", 1)[0])
    except (TypeError, ValueError):
        return None


def conference_power(
    power: dict[tuple[str, str], float],
    season: str,
    conference: str,
) -> tuple[float | str, str]:
    if not power:
        return "", "missing_no_massey_file"
    normalized_conference = normalize(conference)
    exact = power.get((season, normalized_conference), "")
    if exact != "":
        return exact, "exact"

    target_year = season_start_year(season)
    if target_year is None:
        return "", "missing_bad_season"

    candidates: list[tuple[int, float, str]] = []
    for (candidate_season, candidate_conference), value in power.items():
        if candidate_conference != normalized_conference:
            continue
        candidate_year = season_start_year(candidate_season)
        if candidate_year is None:
            continue
        candidates.append((candidate_year, value, candidate_season))
    if not candidates:
        return "", "missing_no_same_conference"

    before = sorted((item for item in candidates if item[0] < target_year), reverse=True)
    after = sorted(item for item in candidates if item[0] > target_year)
    if before and after:
        before_year, before_value, before_season = before[0]
        after_year, after_value, after_season = after[0]
        span = after_year - before_year
        if span > 0:
            weight = (target_year - before_year) / span
            interpolated = before_value + (after_value - before_value) * weight
            return round(interpolated, 3), f"interpolated_{before_season}_{after_season}"

    nearest_year, nearest_value, nearest_season = min(
        candidates,
        key=lambda item: (abs(item[0] - target_year), item[0]),
    )
    return nearest_value, f"nearest_{nearest_season}"


def percentile_values(rows: list[dict[str, object]], column: str) -> dict[int, float]:
    values = [(index, number(row[column])) for index, row in enumerate(rows)]
    values.sort(key=lambda item: item[1])
    if len(values) <= 1:
        return {index: 50.0 for index, _value in values}
    out: dict[int, float] = {}
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[end + 1][1] == values[start][1]:
            end += 1
        avg_index = (start + end) / 2
        pct = avg_index / (len(values) - 1) * 100
        for offset in range(start, end + 1):
            out[values[offset][0]] = pct
        start = end + 1
    return out


def outcome_tier(score: float) -> str:
    if score >= 80:
        return "Target-conference impact starter"
    if score >= 65:
        return "Target-conference starter/plus rotation"
    if score >= 45:
        return "Target-conference rotation"
    return "Limited target-conference role"


def source_conference_override(row: dict[str, str]) -> str:
    player = str(row.get("player_name", "")).strip().lower()
    school = str(row.get("source_school", "")).strip().lower()
    season = str(row.get("source_season", "")).strip()
    if player == "jahsean corbett" and school == "chicago state" and season == "2023-24":
        return "Northeast"
    return row.get("source_conference", "")


def adapt(row: dict[str, str], massey_power: dict[tuple[str, str], float]) -> dict[str, object]:
    ppg = number(row["target_ppg"])
    rpg = number(row["target_rpg"])
    apg = number(row["target_apg"])
    spg = number(row["target_spg"])
    bpg = number(row["target_bpg"])
    topg = number(row["target_topg"])
    production_score = ppg + 0.7 * rpg + 0.7 * apg + 0.7 * spg + 0.7 * bpg - 0.5 * topg
    source_conference = source_conference_override(row)
    source_conf_power, source_conf_power_method = conference_power(
        massey_power,
        row["source_season"],
        source_conference,
    )
    destination_conf_power, destination_conf_power_method = conference_power(
        massey_power,
        row["first_target_season"],
        TARGET_CONFERENCE_TO_MASSEY.get(row["target_conference"], row["target_conference"]),
    )
    if source_conf_power != "" and destination_conf_power != "":
        conf_power_delta: float | str = number(destination_conf_power) - number(source_conf_power)
    else:
        conf_power_delta = ""
    return {
        "target_conference": row["target_conference"],
        "player_name": row["player_name"],
        "player_slug": row["player_key"],
        "source_school": row["source_school"],
        "source_school_slug": slug(row["source_school"]),
        "source_conference": source_conference,
        "source_level": row["source_level"],
        "destination_school": row["destination_school"],
        "destination_school_slug": slug(row["destination_school"]),
        "first_big_west_season": row["first_target_season"],
        "source_season": row["source_season"],
        "source_stat_source": "target_conference_common_box",
        "position": row["position"],
        "height_in": row["height"],
        "weight_lbs": row["weight"],
        "source_conf_power": source_conf_power,
        "source_conf_power_method": source_conf_power_method,
        "destination_conf_power": destination_conf_power,
        "destination_conf_power_method": destination_conf_power_method,
        "conf_power_delta": conf_power_delta,
        "source_games": row["source_games"],
        "source_mpg": row["source_mpg"],
        "source_minutes_share": row["source_minutes_share"],
        "source_ppg": row["source_ppg"],
        "source_rpg": row["source_rpg"],
        "source_apg": row["source_apg"],
        "source_spg": row["source_spg"],
        "source_bpg": row["source_bpg"],
        "source_topg": row["source_topg"],
        "source_fg_pct": row["source_fg_pct"],
        "source_fg3_pct": row["source_fg3_pct"],
        "source_ft_pct": row["source_ft_pct"],
        "source_efg_pct": row["source_efg_pct"],
        "source_ts_pct": "",
        "source_three_rate": "",
        "source_ft_rate": "",
        "source_per": "",
        "source_usg_pct": "",
        "source_ws": "",
        "source_bpm": "",
        "source_pts_per_40": row["source_pts_per_40"],
        "source_reb_per_40": row["source_reb_per_40"],
        "source_ast_per_40": row["source_ast_per_40"],
        "source_stl_per_40": row["source_stl_per_40"],
        "source_blk_per_40": row["source_blk_per_40"],
        "source_tov_per_40": row["source_tov_per_40"],
        "big_west_games": row["target_games"],
        "big_west_games_started": row["target_games_started"],
        "big_west_mpg": row["target_mpg"],
        "big_west_minutes": row["target_minutes"],
        "big_west_minutes_share": row["target_minutes_share"],
        "big_west_ppg": row["target_ppg"],
        "big_west_rpg": row["target_rpg"],
        "big_west_apg": row["target_apg"],
        "big_west_spg": row["target_spg"],
        "big_west_bpg": row["target_bpg"],
        "big_west_topg": row["target_topg"],
        "big_west_ts_pct": row["target_ts_pct"],
        "big_west_per": row["target_per"],
        "big_west_usg_pct": row["target_usg_pct"],
        "big_west_ws": row["target_ws"],
        "big_west_ws_per_40": row["target_ws_per_40"],
        "big_west_bpm": row["target_bpm"],
        "big_west_porpag": "",
        "production_score": production_score,
        "impact_score": 0.0,
        "outcome_tier": "",
        "source_url": row["source_url"],
        "outcome_url": row["outcome_url"],
    }


def main() -> int:
    massey_power = load_massey_power()
    with INPUT_PATH.open(newline="", encoding="utf-8") as file:
        rows = [adapt(row, massey_power) for row in csv.DictReader(file)]

    production_pct = percentile_values(rows, "production_score")
    minutes_pct = percentile_values(rows, "big_west_minutes_share")
    bpm_pct = percentile_values(rows, "big_west_bpm")
    ws_pct = percentile_values(rows, "big_west_ws")
    for index, row in enumerate(rows):
        impact = (
            0.35 * minutes_pct[index]
            + 0.25 * bpm_pct[index]
            + 0.20 * ws_pct[index]
            + 0.20 * production_pct[index]
        )
        row["impact_score"] = impact
        row["outcome_tier"] = outcome_tier(impact)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
