#!/usr/bin/env python3
"""Join D2 inputs to first-year D1 outcomes and derive first-pass weights."""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

D2_PATH = Path("data/phase1_school_stats.csv")
D1_PATH = Path("data/phase1_d1_outcomes.csv")
OUTPUT_PATH = Path("data/phase1_modeling_dataset.csv")
IMPORTANCE_PATH = Path("data/phase1_feature_importance.csv")
WEIGHTS_JSON_PATH = Path("data/phase1_learned_weights.json")
WEIGHTS_JS_PATH = Path("src/learnedWeights.js")

CLASS_AGE = {
    "Fr.": 18.8,
    "So.": 19.8,
    "Jr.": 20.8,
    "Sr.": 21.8,
    "Gr.": 22.8,
}

FEATURES = [
    ("heightIn", "D2 height"),
    ("age", "D2 class age proxy"),
    ("minutesPct", "D2 minutes share"),
    ("usagePct", "D2 usage proxy"),
    ("ptsPer40", "D2 scoring per 40"),
    ("tsPct", "D2 true shooting"),
    ("astPer40", "D2 assists per 40"),
    ("tovPer40", "D2 turnovers per 40"),
    ("rebPer40", "D2 rebounds per 40"),
    ("stlPer40", "D2 steals per 40"),
    ("blkPer40", "D2 blocks per 40"),
    ("threePaRate", "D2 3PA/FGA"),
    ("threePct", "D2 3P%"),
    ("ftRate", "D2 FTA/FGA"),
]

OUTPUT_COLUMNS = [
    "player_name",
    "d2_school",
    "d2_conference",
    "d2_season",
    "d1_school",
    "first_d1_season",
    "position",
    "heightIn",
    "age",
    "minutesPct",
    "usagePct",
    "ptsPer40",
    "tsPct",
    "astPer40",
    "tovPer40",
    "rebPer40",
    "stlPer40",
    "blkPer40",
    "threePaRate",
    "threePct",
    "ftRate",
    "d1_games",
    "d1_games_started",
    "d1_mpg",
    "d1_minutes",
    "d1_minutes_share",
    "d1_ppg",
    "d1_rpg",
    "d1_apg",
    "d1_spg",
    "d1_bpg",
    "d1_topg",
    "d1_ts_pct",
    "d1_per",
    "d1_usg_pct",
    "d1_ws",
    "d1_ws_per_40",
    "d1_bpm",
    "production_score",
    "impact_score",
    "outcome_tier",
    "d2_source_url",
    "d1_source_url",
]


def number(value: str, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def percentile_map(rows: list[dict[str, float]], key: str) -> dict[str, float]:
    ordered = sorted(rows, key=lambda row: row[key])
    if len(ordered) == 1:
        return {ordered[0]["player_name"]: 50.0}
    return {
        row["player_name"]: (index / (len(ordered) - 1)) * 100
        for index, row in enumerate(ordered)
    }


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_den = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    y_den = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if not x_den or not y_den:
        return 0.0
    return numerator / (x_den * y_den)


def outcome_tier(score: float) -> str:
    if score >= 80:
        return "D1 impact starter"
    if score >= 65:
        return "D1 starter/plus rotation"
    if score >= 45:
        return "D1 rotation"
    return "Limited D1 role"


def build_model_row(d2: dict[str, str], d1: dict[str, str]) -> dict[str, object]:
    d1_ppg = number(d1["ppg"])
    d1_rpg = number(d1["rpg"])
    d1_apg = number(d1["apg"])
    d1_spg = number(d1["spg"])
    d1_bpg = number(d1["bpg"])
    d1_topg = number(d1["topg"])

    return {
        "player_name": d2["Player Name"],
        "d2_school": d2["Team"],
        "d2_conference": d2["Conference"],
        "d2_season": d2["Season"],
        "d1_school": d1["d1_school"],
        "first_d1_season": d1["first_d1_season"],
        "position": d2["Position"],
        "heightIn": number(d2["Height"]),
        "age": CLASS_AGE.get(d2["Year"], 21.8),
        "minutesPct": min(100, number(d2["MPG"]) / 40 * 100),
        "usagePct": number(d2["usg"]) * 100,
        "ptsPer40": number(d2["pts_per_40"]),
        "tsPct": number(d2["TS_pct"]),
        "astPer40": number(d2["ast_per_40"]),
        "tovPer40": number(d2["tov_per_40"]),
        "rebPer40": number(d2["reb_per_40"]),
        "stlPer40": number(d2["stl_per_40"]),
        "blkPer40": number(d2["blk_per_40"]),
        "threePaRate": number(d2["three_share"]),
        "threePct": number(d2["3PT%"]),
        "ftRate": number(d2["FTR"]),
        "d1_games": int(number(d1["games"])),
        "d1_games_started": int(number(d1["games_started"])),
        "d1_mpg": number(d1["mpg"]),
        "d1_minutes": number(d1["minutes"]),
        "d1_minutes_share": number(d1["minutes_share"]),
        "d1_ppg": d1_ppg,
        "d1_rpg": d1_rpg,
        "d1_apg": d1_apg,
        "d1_spg": d1_spg,
        "d1_bpg": d1_bpg,
        "d1_topg": d1_topg,
        "d1_ts_pct": number(d1["ts_pct"]),
        "d1_per": number(d1["per"]),
        "d1_usg_pct": number(d1["usg_pct"]),
        "d1_ws": number(d1["ws"]),
        "d1_ws_per_40": number(d1["ws_per_40"]),
        "d1_bpm": number(d1["bpm"]),
        "production_score": d1_ppg + 0.7 * d1_rpg + 0.7 * d1_apg + 0.7 * d1_spg + 0.7 * d1_bpg - 0.5 * d1_topg,
        "impact_score": 0,
        "outcome_tier": "",
        "d2_source_url": d2["source_url"],
        "d1_source_url": d1["source_url"],
    }


def main() -> int:
    with D2_PATH.open(newline="") as file:
        d2_rows = list(csv.DictReader(file))
    with D1_PATH.open(newline="") as file:
        d1_rows = list(csv.DictReader(file))

    d1_by_name = {normalize_name(row["player_name"]): row for row in d1_rows}
    rows = [
        build_model_row(d2, d1_by_name[normalize_name(d2["Player Name"])])
        for d2 in d2_rows
        if normalize_name(d2["Player Name"]) in d1_by_name
    ]

    production_pct = percentile_map(rows, "production_score")
    minutes_pct = percentile_map(rows, "d1_minutes_share")
    bpm_pct = percentile_map(rows, "d1_bpm")
    ws_pct = percentile_map(rows, "d1_ws")

    for row in rows:
        name = str(row["player_name"])
        impact = (
            0.35 * minutes_pct[name]
            + 0.25 * bpm_pct[name]
            + 0.20 * ws_pct[name]
            + 0.20 * production_pct[name]
        )
        row["impact_score"] = impact
        row["outcome_tier"] = outcome_tier(impact)

    importance_rows = []
    for key, label in FEATURES:
        xs = [float(row[key]) for row in rows]
        impact_corr = pearson(xs, [float(row["impact_score"]) for row in rows])
        bpm_corr = pearson(xs, [float(row["d1_bpm"]) for row in rows])
        minutes_corr = pearson(xs, [float(row["d1_minutes_share"]) for row in rows])
        ws_corr = pearson(xs, [float(row["d1_ws"]) for row in rows])
        blended = (
            0.55 * abs(impact_corr)
            + 0.20 * abs(bpm_corr)
            + 0.15 * abs(minutes_corr)
            + 0.10 * abs(ws_corr)
        )
        importance_rows.append(
            {
                "feature": key,
                "label": label,
                "corr_impact": impact_corr,
                "corr_bpm": bpm_corr,
                "corr_minutes": minutes_corr,
                "corr_ws": ws_corr,
                "importance": blended,
                "direction": "positive" if impact_corr >= 0 else "negative",
            }
        )

    max_importance = max(row["importance"] for row in importance_rows) or 1
    learned_weights = {
        row["feature"]: round(0.25 + 1.5 * (row["importance"] / max_importance), 2)
        for row in importance_rows
    }

    rows.sort(key=lambda row: float(row["impact_score"]), reverse=True)
    importance_rows.sort(key=lambda row: float(row["importance"]), reverse=True)

    with OUTPUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with IMPORTANCE_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "feature",
                "label",
                "corr_impact",
                "corr_bpm",
                "corr_minutes",
                "corr_ws",
                "importance",
                "direction",
            ],
        )
        writer.writeheader()
        writer.writerows(importance_rows)

    WEIGHTS_JSON_PATH.write_text(json.dumps(learned_weights, indent=2) + "\n", encoding="utf-8")
    WEIGHTS_JS_PATH.write_text(
        "export const LEARNED_WEIGHTS = "
        + json.dumps(learned_weights, indent=2)
        + ";\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote feature importance to {IMPORTANCE_PATH}")
    print(f"Wrote learned weights to {WEIGHTS_JSON_PATH} and {WEIGHTS_JS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
