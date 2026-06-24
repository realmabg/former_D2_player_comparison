#!/usr/bin/env python3
"""Clean copied Massey team ratings into model-ready rows."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path("Massey Ratings 20-26 Uncleaned - Team.csv")
OUTPUT_PATH = Path("data/massey_team_ratings.csv")
SUMMARY_PATH = Path("data/massey_team_ratings_summary.csv")

LEVEL_SUFFIXES = [
    "NCAA D1",
    "NCAA D2",
    "NCAA D3",
    "NCCAA II",
    "NCCAA I",
    "NCCAA",
    "USCAA-1",
    "USCAA-2",
    "USCAA",
    "NAIA",
]

CONFERENCE_SUFFIXES_2021 = [
    "American Athletic",
    "America East",
    "Atlantic Coast",
    "Atlantic 10",
    "Atlantic Sun",
    "Big East",
    "Big Sky",
    "Big South",
    "Big 10",
    "Big 12",
    "Big West",
    "Colonial",
    "Coastal",
    "Conference USA",
    "Horizon",
    "Ivy League",
    "Metro Atlantic",
    "Mid-American",
    "Mid-Eastern AC",
    "Missouri Valley",
    "Missouri Val",
    "Mountain West",
    "Northeast",
    "Ohio Valley",
    "OH Valley",
    "Pac 12",
    "Patriot League",
    "Southland",
    "Southeastern",
    "Southern",
    "Southwestern AC",
    "Summit League",
    "Summit Lg",
    "Sun Belt",
    "West Coast",
    "Western Athletic",
]


def normalize_season(value: object) -> str:
    text = str(value).strip()
    if re.match(r"^\d{2}-\d{2}$", text):
        return f"20{text}"
    return text


def slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def parse_team_level(value: object, season: str) -> tuple[str, str, str]:
    text = str(value).strip()
    for suffix in sorted(LEVEL_SUFFIXES, key=len, reverse=True):
        if text.endswith(suffix):
            return text[: -len(suffix)].strip(), suffix, ""
    if season == "2020-21":
        for suffix in sorted(CONFERENCE_SUFFIXES_2021, key=len, reverse=True):
            if text.endswith(suffix):
                return text[: -len(suffix)].strip(), "NCAA D1", suffix
    return text, "", ""


def parse_rec(value: object) -> tuple[float, float, float]:
    text = str(value).strip()
    match = re.match(r"^(\d+)-(\d+)(0\.\d+)$", text)
    if not match:
        return np.nan, np.nan, np.nan
    return float(match.group(1)), float(match.group(2)), float(match.group(3))


def parse_rank_value(value: object, min_value: float = -80, max_value: float = 140) -> tuple[float, float]:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return np.nan, np.nan
    # Massey copy/paste combines rank and value, e.g. "355.49" = rank 3, value 55.49.
    for digits in range(1, min(5, len(text)) + 1):
        rank_text = text[:digits]
        remainder = text[digits:]
        if not rank_text.isdigit() or not remainder:
            continue
        try:
            rank = float(rank_text)
            parsed = float(remainder)
        except ValueError:
            continue
        if 1 <= rank <= 1200 and min_value <= parsed <= max_value:
            return rank, parsed
    try:
        return np.nan, float(text)
    except ValueError:
        return np.nan, np.nan


def parse_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except ValueError:
        return np.nan


def main() -> int:
    raw = pd.read_csv(INPUT_PATH, dtype=str)
    rows: list[dict[str, object]] = []
    for index, row in raw.iterrows():
        season = normalize_season(row["Year"])
        team, level, conference = parse_team_level(row["Team"], season)
        wins, losses, win_pct = parse_rec(row["Rec"])
        rat_rank, rating = parse_rank_value(row["Rat"], min_value=-20, max_value=40)
        pwr_rank, power = parse_rank_value(row["Pwr"], min_value=-40, max_value=80)
        off_rank, offense = parse_rank_value(row["Off"], min_value=40, max_value=130)
        def_rank, defense = parse_rank_value(row["Def"], min_value=-30, max_value=60)
        sos_rank, sos = parse_rank_value(row["SoS"], min_value=-80, max_value=80)
        rows.append(
            {
                "season": season,
                "team": team,
                "team_key": slug(team),
                "level": level,
                "conference_2020_21": conference,
                "wins": wins,
                "losses": losses,
                "win_pct": win_pct,
                "delta": parse_float(row.get("Delta", "")),
                "rating_rank": rat_rank,
                "rating": rating,
                "power_rank": pwr_rank,
                "power": power,
                "offense_rank": off_rank,
                "offense": offense,
                "defense_rank": def_rank,
                "defense": defense,
                "hfa": parse_float(row["HFA"]),
                "sos_rank": sos_rank,
                "sos": sos,
                "source_row": index + 2,
            }
        )

    cleaned = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(OUTPUT_PATH, index=False)
    summary = (
        cleaned.groupby(["season", "level"], dropna=False)
        .agg(rows=("team", "size"), teams=("team_key", "nunique"), power_missing=("power", lambda s: int(s.isna().sum())))
        .reset_index()
        .sort_values(["season", "level"])
    )
    summary.to_csv(SUMMARY_PATH, index=False)
    print(f"Wrote {len(cleaned)} rows to {OUTPUT_PATH}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
