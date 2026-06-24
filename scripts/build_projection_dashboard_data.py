#!/usr/bin/env python3
"""Build static JSON data for the BPR projection dashboard."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


CURRENT_D2_PATH = Path("d2_data_cleaned.csv")
TRAINING_PATH = Path("data/modeling/training/d2_available_training.csv")
MASSEY_PATH = Path("data/massey_conference_power.csv")
TEAM_RATINGS_PATH = Path("data/massey_team_ratings.csv")
MODEL_SUMMARY_PATH = Path("reports/d2_available_model_comparison_min_mpg_10/best_models_summary.csv")
FEATURE_MANIFEST_PATH = Path("data/modeling/training/d2_available_feature_manifest.json")
OUTPUT_PATH = Path("data/projection_dashboard_data.json")
SUSPICIOUS_CURRENT_STATS_PATH = Path("data/current_d2_suspicious_event_stats.csv")
VERIFIED_CURRENT_STATS_PATH = Path("data/current_d2_verified_stats.csv")
SCHOOL_VERIFIED_CURRENT_STATS_PATH = Path("data/current_d2_school_verified_stats.csv")
REALGM_VERIFIED_CURRENT_STATS_PATH = Path("data/current_d2_realgm_verified_stats.csv")

TARGET_CONFERENCES = [
    "Big West",
    "WCC",
    "Mountain West",
    "Atlantic 10",
    "American",
    "Missouri Valley",
]

TARGET_CONFERENCE_TO_MASSEY = {
    "Big West": "Big West",
    "WCC": "West Coast",
    "Mountain West": "Mountain West",
    "Atlantic 10": "Atlantic 10",
    "American": "American",
    "Missouri Valley": "Missouri Valley",
}

CONFERENCE_ALIASES = {
    "a sun": "asun",
    "c usa": "c usa",
    "ccaa": "california caa",
    "central": "central iaa",
    "glvc": "great lakes val",
    "gliac": "great lakes iac",
    "gnac": "great northwest",
    "gmac": "great midwest",
    "gulf south": "gulf south",
    "lone star": "lone star",
    "lsc": "lone star",
    "mec": "mountain east",
    "mid america": "mid america iaa",
    "mountain east": "mountain east",
    "northeast 10": "northeast 10",
    "pacwest": "pacific west",
    "peach belt": "peach belt",
    "psac": "psac west",
    "rmac": "rocky mtn ac",
    "sac": "south atlantic",
    "sciac": "southern cal iac",
    "ssc": "sunshine state",
    "sunshine": "sunshine state",
}

CLASS_ORDER = {"Fr.": 1, "So.": 2, "Jr.": 3, "Sr.": 4, "Gr.": 5}
NEXT_CLASS = {
    "FR": "SO",
    "SO": "JR",
    "JR": "SR",
    "SR": "GR",
    "GR": "GR",
    "UNKNOWN": "unknown",
}


def normalize(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    return CONFERENCE_ALIASES.get(text, text)


def normalize_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def slugify(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def number(value: object, fallback: float = np.nan) -> float:
    try:
        if value == "" or pd.isna(value):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def display_name(value: object) -> str:
    raw = str(value or "").strip()
    parts = [part.strip() for part in raw.split(",", 1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        last_tokens = parts[0].split()
        suffixes = {"Jr.", "Sr.", "II", "III", "IV", "V"}
        if len(last_tokens) > 1 and last_tokens[-1] in suffixes:
            return f"{parts[1]} {' '.join(last_tokens[:-1])} {last_tokens[-1]}"
        return f"{parts[1]} {parts[0]}"
    return raw


def height_label(inches: float) -> str:
    if not math.isfinite(inches):
        return ""
    return f"{int(inches // 12)}'{int(inches % 12)}\""


def event_stat_quality(row: dict[str, object]) -> dict[str, bool]:
    apg = number(row.get("APG"), 0.0)
    topg = number(row.get("TOPG"), 0.0)
    spg = number(row.get("SPG"), 0.0)
    bpg = number(row.get("BPG"), 0.0)
    ast_per_40 = number(row.get("ast_per_40"), 0.0)
    tov_per_40 = number(row.get("tov_per_40"), 0.0)
    stl_per_40 = number(row.get("stl_per_40"), 0.0)
    blk_per_40 = number(row.get("blk_per_40"), 0.0)
    return {
        "assist_stats_suspicious": apg > 8 or ast_per_40 > 12,
        "turnover_stats_suspicious": topg > 8 or tov_per_40 > 12,
        "steal_stats_suspicious": spg > 5 or stl_per_40 > 8,
        "block_stats_suspicious": bpg > 5 or blk_per_40 > 8,
    }


def stat_or_missing(value: object, suspicious: bool, fallback: float = np.nan) -> float:
    return np.nan if suspicious else number(value, fallback)


def verified_key(name: object, team: object) -> tuple[str, str]:
    return normalize_key(display_name(name)), normalize_key(team)


def load_verified_current_stats() -> dict[tuple[str, str], dict[str, object]]:
    rows: dict[tuple[str, str], dict[str, object]] = {}
    for path in [REALGM_VERIFIED_CURRENT_STATS_PATH, SCHOOL_VERIFIED_CURRENT_STATS_PATH, VERIFIED_CURRENT_STATS_PATH]:
        if not path.exists():
            continue
        verified = pd.read_csv(path)
        if verified.empty:
            continue
        for row in verified.to_dict("records"):
            name = row.get("Player Name", row.get("player_name", ""))
            team = row.get("Team", row.get("team", ""))
            if not name or not team:
                continue
            rows[verified_key(name, team)] = row
    return rows


def apply_verified_row(row: dict[str, object], verified: dict[tuple[str, str], dict[str, object]]) -> dict[str, object]:
    override = verified.get(verified_key(row.get("Player Name", ""), row.get("Team", "")))
    if not override:
        return row
    updated = dict(row)
    aliases = {
        "player_name": "Player Name",
        "team": "Team",
        "conference": "Conference",
        "position": "Position",
        "height": "Height",
        "year": "Year",
        "gp": "GP",
        "min": "MIN",
        "minutes": "MIN",
        "mpg": "MPG",
        "fgm": "FGM",
        "fga": "FGA",
        "fg_pct": "FG%",
        "fg%": "FG%",
        "3ptm": "3PTM",
        "3pm": "3PTM",
        "3pta": "3PTA",
        "3pa": "3PTA",
        "3pt_pct": "3PT%",
        "3p_pct": "3PT%",
        "3pt%": "3PT%",
        "ftm": "FTM",
        "fta": "FTA",
        "ft_pct": "FT%",
        "ft%": "FT%",
        "pts": "PTS",
        "ppg": "PPG",
        "orb": "ORB",
        "drb": "DRB",
        "tot rb": "TOT RB",
        "reb": "TOT RB",
        "rpg": "RPG",
        "pf": "PF",
        "ast": "AST",
        "to": "TO",
        "tov": "TO",
        "stl": "STL",
        "blk": "BLK",
        "apg": "APG",
        "spg": "SPG",
        "bpg": "BPG",
        "topg": "TOPG",
        "tovpg": "TOPG",
    }
    for source_column, target_column in aliases.items():
        if source_column in override and math.isfinite(number(override[source_column])):
            updated[target_column] = number(override[source_column])
        if target_column in override and math.isfinite(number(override[target_column])):
            updated[target_column] = number(override[target_column])

    gp = number(updated.get("GP"), 0.0)
    minutes = number(updated.get("MIN"), 0.0)
    mpg = number(updated.get("MPG"), minutes / gp if gp else np.nan)
    if gp and minutes and not math.isfinite(number(updated.get("MPG"))):
        updated["MPG"] = minutes / gp
    for total_column, per_game_column in [
        ("PTS", "PPG"),
        ("TOT RB", "RPG"),
        ("AST", "APG"),
        ("STL", "SPG"),
        ("BLK", "BPG"),
        ("TO", "TOPG"),
    ]:
        total = number(updated.get(total_column))
        per_game = number(updated.get(per_game_column))
        if gp and math.isfinite(total):
            updated[per_game_column] = total / gp
        elif math.isfinite(per_game):
            updated[per_game_column] = per_game

    for per_game_column, per_40_column in [
        ("PPG", "pts_per_40"),
        ("RPG", "reb_per_40"),
        ("APG", "ast_per_40"),
        ("SPG", "stl_per_40"),
        ("BPG", "blk_per_40"),
        ("TOPG", "tov_per_40"),
    ]:
        per_game = number(updated.get(per_game_column))
        if mpg and math.isfinite(per_game):
            updated[per_40_column] = per_game * 40 / mpg

    fgm = number(updated.get("FGM"))
    fga = number(updated.get("FGA"))
    three_m = number(updated.get("3PTM"))
    three_a = number(updated.get("3PTA"))
    ftm = number(updated.get("FTM"))
    fta = number(updated.get("FTA"))
    points = number(updated.get("PTS"))
    if math.isfinite(fgm) and math.isfinite(fga) and fga:
        updated["FG%"] = fgm / fga
        updated["eFG"] = (fgm + 0.5 * (three_m if math.isfinite(three_m) else 0.0)) / fga
        updated["three_share"] = (three_a if math.isfinite(three_a) else 0.0) / fga
        updated["FTR"] = (fta if math.isfinite(fta) else 0.0) / fga
    if math.isfinite(three_m) and math.isfinite(three_a) and three_a:
        updated["3PT%"] = three_m / three_a
    if math.isfinite(ftm) and math.isfinite(fta) and fta:
        updated["FT%"] = ftm / fta
    if math.isfinite(points) and math.isfinite(fga) and math.isfinite(fta) and (fga or fta):
        updated["TS_pct"] = points / (2 * (fga + 0.44 * fta))
    updated["verified_current_stats"] = True
    updated["verified_source_url"] = override.get("source_url", override.get("verified_source_url", ""))
    return updated


def load_power() -> dict[tuple[str, str], float]:
    power: dict[tuple[str, str], float] = {}
    df = pd.read_csv(MASSEY_PATH)
    for row in df.to_dict("records"):
        power[(str(row["season"]), normalize(row["conference"]))] = number(row["power"])
    return power


def load_team_power(season: str = "2025-26") -> dict[str, float]:
    if not TEAM_RATINGS_PATH.exists():
        return {}
    df = pd.read_csv(TEAM_RATINGS_PATH)
    df = df[df["season"].astype(str).eq(season)].copy()
    return {
        normalize_key(row["team"]): number(row["power"])
        for row in df.to_dict("records")
        if math.isfinite(number(row.get("power")))
    }


def latest_power(power: dict[tuple[str, str], float], conference: str, season: str = "2025-26") -> float:
    key = (season, normalize(conference))
    if key in power:
        return power[key]
    matches = [(season_key, value) for (season_key, conf_key), value in power.items() if conf_key == normalize(conference)]
    if not matches:
        return np.nan
    return sorted(matches)[-1][1]


def normalize_class(value: object) -> str:
    text = str(value or "").strip().upper().replace(".", "")
    aliases = {
        "FR": "FR",
        "FRESHMAN": "FR",
        "SO": "SO",
        "SOPHOMORE": "SO",
        "JR": "JR",
        "JUNIOR": "JR",
        "SR": "SR",
        "SENIOR": "SR",
        "GR": "GR",
        "GRAD": "GR",
        "GRADUATE": "GR",
    }
    return aliases.get(text, "unknown")


def position_bucket(position: object) -> str:
    text = str(position or "").upper()
    if "C" in text:
        return "center"
    if "G" in text and "F" in text:
        return "wing"
    if "G" in text:
        return "guard"
    if "F" in text:
        return "forward"
    return "unknown"


def height_bucket(inches: float) -> str:
    if not math.isfinite(inches):
        return "unknown"
    if inches <= 74:
        return "small_guard"
    if inches <= 78:
        return "wing_guard"
    if inches <= 81:
        return "forward"
    if inches <= 84:
        return "big_forward"
    return "center"


def role_bucket(mpg: float) -> str:
    if mpg < 10:
        return "bench"
    if mpg < 20:
        return "rotation"
    if mpg < 30:
        return "starter"
    return "high_usage_role"


def fit_model(training: pd.DataFrame) -> tuple[Pipeline, list[str], list[str], dict[str, float], dict[str, object]]:
    manifest = json.loads(FEATURE_MANIFEST_PATH.read_text(encoding="utf-8"))
    numeric_features = list(manifest["numeric_features"])
    categorical_features = list(manifest["categorical_features"])
    target = "big_west_bpr"
    included = training[
        pd.to_numeric(training[target], errors="coerce").notna()
        & (pd.to_numeric(training["big_west_mpg"], errors="coerce").fillna(0) >= 10)
    ].copy()
    medians: dict[str, float] = {}
    for column in numeric_features:
        values = pd.to_numeric(included[column], errors="coerce")
        median = float(values.median()) if values.notna().any() else 0.0
        medians[column] = median
        included[column] = values.fillna(median)
    for column in categorical_features:
        included[column] = included[column].fillna("").astype(str)
    pipeline = Pipeline(
        steps=[
            (
                "preprocess",
                ColumnTransformer(
                    transformers=[
                        ("num", StandardScaler(), numeric_features),
                        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
                    ]
                ),
            ),
            (
                "model",
                GradientBoostingRegressor(
                    n_estimators=180,
                    learning_rate=0.06,
                    max_depth=1,
                    min_samples_leaf=10,
                    subsample=0.8,
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(included[numeric_features + categorical_features], included[target])
    summary = pd.read_csv(MODEL_SUMMARY_PATH)
    bpr = summary[summary["target"].eq("bpr")].iloc[0].to_dict()
    return pipeline, numeric_features, categorical_features, medians, bpr


def current_source_row(row: dict[str, object], source_power: float, source_team_power: float) -> dict[str, object]:
    mpg = number(row.get("MPG"), 0.0)
    fga = number(row.get("FGA"), 0.0)
    three_attempts = number(row.get("3PTA"), 0.0)
    height = number(row.get("Height"))
    source_class = normalize_class(row.get("Year", ""))
    entering_class = NEXT_CLASS.get(source_class, "unknown")
    quality = event_stat_quality(row)
    return {
        "height_in": height,
        "weight_lbs": np.nan,
        "source_games": number(row.get("GP"), 0.0),
        "source_mpg": mpg,
        "source_minutes_share": mpg / 40 if mpg else 0.0,
        "source_ppg": number(row.get("PPG"), 0.0),
        "source_rpg": number(row.get("RPG"), 0.0),
        "source_apg": stat_or_missing(row.get("APG"), quality["assist_stats_suspicious"]),
        "source_spg": stat_or_missing(row.get("SPG"), quality["steal_stats_suspicious"]),
        "source_bpg": stat_or_missing(row.get("BPG"), quality["block_stats_suspicious"]),
        "source_topg": stat_or_missing(row.get("TOPG"), quality["turnover_stats_suspicious"]),
        "source_fg_pct": number(row.get("FG%")),
        "source_fg3_pct": number(row.get("3PT%")),
        "source_ft_pct": number(row.get("FT%")),
        "source_efg_pct": number(row.get("eFG")),
        "source_ts_pct": number(row.get("TS_pct")),
        "source_three_rate": three_attempts / fga if fga else number(row.get("three_share")),
        "source_ft_rate": number(row.get("FTR")),
        "source_pts_per_40": number(row.get("pts_per_40"), 0.0),
        "source_reb_per_40": number(row.get("reb_per_40"), 0.0),
        "source_ast_per_40": stat_or_missing(row.get("ast_per_40"), quality["assist_stats_suspicious"]),
        "source_stl_per_40": stat_or_missing(row.get("stl_per_40"), quality["steal_stats_suspicious"]),
        "source_blk_per_40": stat_or_missing(row.get("blk_per_40"), quality["block_stats_suspicious"]),
        "source_tov_per_40": stat_or_missing(row.get("tov_per_40"), quality["turnover_stats_suspicious"]),
        "source_conf_power": source_power,
        "source_team_power": source_team_power,
        "source_low_minutes_flag": int(mpg < 10),
        "source_low_games_flag": int(number(row.get("GP"), 0.0) < 10),
        "position": row.get("Position", ""),
        "position_bucket": position_bucket(row.get("Position", "")),
        "height_bucket": height_bucket(height),
        "source_role_bucket": role_bucket(mpg),
        "class_entering_destination": entering_class,
        "source_level": "D2",
        "source_conference": row.get("Conference", ""),
        **quality,
    }


def tier(value: float) -> str:
    if value >= 4.0:
        return "impact starter"
    if value >= 2.0:
        return "plus rotation"
    if value >= 0.0:
        return "rotation"
    return "depth risk"


def main() -> int:
    training = pd.read_csv(TRAINING_PATH)
    current = pd.read_csv(CURRENT_D2_PATH)
    verified_current_stats = load_verified_current_stats()
    power = load_power()
    team_power = load_team_power()
    model, numeric_features, categorical_features, medians, bpr_summary = fit_model(training)

    suspicious_rows: list[dict[str, object]] = []

    conference_power = {
        conference: latest_power(power, TARGET_CONFERENCE_TO_MASSEY[conference])
        for conference in TARGET_CONFERENCES
    }
    destination_team_power = (
        training.groupby("target_conference")["destination_team_power"]
        .median()
        .reindex(TARGET_CONFERENCES)
        .to_dict()
    )

    base_rows: list[dict[str, object]] = []
    player_records: list[dict[str, object]] = []
    for index, row in enumerate(current.to_dict("records")):
        row = apply_verified_row(row, verified_current_stats)
        name = display_name(row.get("Player Name", ""))
        if not name:
            continue
        source_power = latest_power(power, str(row.get("Conference", "")))
        source_team_power = team_power.get(normalize_key(row.get("Team", "")), np.nan)
        if not math.isfinite(source_team_power):
            source_team_power = source_power
        base = current_source_row(row, source_power, source_team_power)
        quality = event_stat_quality(row)
        if any(quality.values()):
            suspicious_rows.append(
                {
                    "player_name": name,
                    "team": row.get("Team", ""),
                    "conference": row.get("Conference", ""),
                    "gp": row.get("GP", ""),
                    "min": row.get("MIN", ""),
                    "mpg": row.get("MPG", ""),
                    "ppg": row.get("PPG", ""),
                    "rpg": row.get("RPG", ""),
                    "raw_apg": row.get("APG", ""),
                    "raw_topg": row.get("TOPG", ""),
                    "raw_spg": row.get("SPG", ""),
                    "raw_bpg": row.get("BPG", ""),
                    "raw_ast_per_40": row.get("ast_per_40", ""),
                    "raw_tov_per_40": row.get("tov_per_40", ""),
                    "raw_stl_per_40": row.get("stl_per_40", ""),
                    "raw_blk_per_40": row.get("blk_per_40", ""),
                    **quality,
                }
            )
        base_rows.append(base)
        player_records.append(
            {
                "id": f"{slugify(name)}-{slugify(row.get('Team', ''))}-{index}",
                "name": name,
                "team": row.get("Team", ""),
                "conference": row.get("Conference", ""),
                "position": row.get("Position", ""),
                "height": int(number(row.get("Height"), 0) or 0),
                "heightLabel": height_label(number(row.get("Height"), np.nan)),
                "classYear": row.get("Year", ""),
                "games": round(number(row.get("GP"), 0), 0),
                "mpg": round(number(row.get("MPG"), 0), 1),
                "ppg": round(number(row.get("PPG"), 0), 1),
                "rpg": round(number(row.get("RPG"), 0), 1),
                "apg": None if not math.isfinite(base["source_apg"]) else round(base["source_apg"], 1),
                "spg": None if not math.isfinite(base["source_spg"]) else round(base["source_spg"], 1),
                "bpg": None if not math.isfinite(base["source_bpg"]) else round(base["source_bpg"], 1),
                "topg": None if not math.isfinite(base["source_topg"]) else round(base["source_topg"], 1),
                "fgPct": round(number(row.get("FG%"), 0), 3),
                "threePct": round(number(row.get("3PT%"), 0), 3),
                "ftPct": round(number(row.get("FT%"), 0), 3),
                "efgPct": round(number(row.get("eFG"), 0), 3),
                "tsPct": round(number(row.get("TS_pct"), 0), 3),
                "threeRate": round(base["source_three_rate"] if math.isfinite(base["source_three_rate"]) else 0, 3),
                "ftRate": round(number(row.get("FTR"), 0), 3),
                "ptsPer40": round(number(row.get("pts_per_40"), 0), 1),
                "rebPer40": round(number(row.get("reb_per_40"), 0), 1),
                "astPer40": None if not math.isfinite(base["source_ast_per_40"]) else round(base["source_ast_per_40"], 1),
                "stlPer40": None if not math.isfinite(base["source_stl_per_40"]) else round(base["source_stl_per_40"], 1),
                "blkPer40": None if not math.isfinite(base["source_blk_per_40"]) else round(base["source_blk_per_40"], 1),
                "tovPer40": None if not math.isfinite(base["source_tov_per_40"]) else round(base["source_tov_per_40"], 1),
                "sourceConfPower": None if not math.isfinite(source_power) else round(source_power, 2),
                "sourceTeamPower": None if not math.isfinite(source_team_power) else round(source_team_power, 2),
                "eventStatsFlagged": any(quality.values()),
                "verifiedCurrentStats": bool(row.get("verified_current_stats", False)),
                "verifiedSourceUrl": row.get("verified_source_url", ""),
                "bestConference": "",
                "bestBpr": 0.0,
                "projections": {},
                "classOrder": CLASS_ORDER.get(row.get("Year", ""), 0),
            }
        )

    base_frame = pd.DataFrame(base_rows)
    source_powers = pd.to_numeric(base_frame["source_conf_power"], errors="coerce")
    for conference in TARGET_CONFERENCES:
        frame = base_frame.copy()
        destination_power = conference_power[conference]
        destination_team = number(destination_team_power.get(conference), destination_power)
        frame["destination_conf_power"] = destination_power
        frame["conf_power_delta"] = destination_power - source_powers
        frame["destination_team_power"] = destination_team
        frame["team_power_delta"] = destination_team - pd.to_numeric(frame["source_team_power"], errors="coerce")
        for column in numeric_features:
            values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            frame[column] = values.fillna(medians[column])
        for column in categorical_features:
            frame[column] = frame[column].fillna("").astype(str)
        predictions = model.predict(frame[numeric_features + categorical_features])
        for player, predicted in zip(player_records, predictions):
            predicted = float(predicted)
            player["projections"][conference] = {
                "bpr": round(predicted, 2),
                "tier": tier(predicted),
                "destinationPower": None if not math.isfinite(destination_power) else round(destination_power, 2),
                "destinationTeamPower": None if not math.isfinite(destination_team) else round(destination_team, 2),
            }

    for player in player_records:
        best_conference = max(player["projections"], key=lambda conf: player["projections"][conf]["bpr"])
        player["bestConference"] = best_conference
        player["bestBpr"] = player["projections"][best_conference]["bpr"]

    pd.DataFrame(suspicious_rows).to_csv(SUSPICIOUS_CURRENT_STATS_PATH, index=False)

    payload = {
        "meta": {
            "model": "gradient_boosting_bpr_min_mpg_10",
            "target": "EvanMiya BPR",
            "rowsUsed": int(bpr_summary["rows_used"]),
            "cvMae": round(float(bpr_summary["cv_mae"]), 3),
            "cvR2": round(float(bpr_summary["cv_r2"]), 3),
            "cvCorr": round(float(bpr_summary["cv_pearson"]), 3),
            "conferences": TARGET_CONFERENCES,
            "conferencePower": {key: round(value, 2) for key, value in conference_power.items()},
            "modelParams": json.loads(bpr_summary["params_json"]),
            "note": "Current D2 players are scored only with features available for D2 players: box/per-40 stats, position, height, D2 conference power, destination conference power, and conference power jump.",
        },
        "players": player_records,
    }
    OUTPUT_PATH.write_text(
        json.dumps(json_safe(payload), separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(player_records)} players to {OUTPUT_PATH}")
    print(f"Wrote {len(suspicious_rows)} suspicious current D2 stat rows to {SUSPICIOUS_CURRENT_STATS_PATH}")
    print(f"Target conferences: {', '.join(TARGET_CONFERENCES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
