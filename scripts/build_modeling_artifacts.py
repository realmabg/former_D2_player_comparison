#!/usr/bin/env python3
"""Create separated all-stats and training-ready modeling artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import numpy as np
import pandas as pd


RAW_SCHEMA_PATH = Path("data/target_conference_transfer_modeling_bpr_schema.csv")
BART_OUTCOMES_PATH = Path("data/target_conference_barttorvik_outcomes.csv")
MASSEY_TEAM_RATINGS_PATH = Path("data/massey_team_ratings.csv")
ALL_STATS_PATH = Path("data/modeling/master/target_conference_all_stats.csv")
TRAINING_PATH = Path("data/modeling/training/d2_available_training.csv")
MANIFEST_PATH = Path("data/modeling/training/d2_available_feature_manifest.json")
LEGACY_D2_AVAILABLE_PATH = Path("data/target_conference_transfer_modeling_bpr_schema_d2_available.csv")
PROFILE_CACHE_DIRS = [
    Path("data/cache/sports_reference_roster_diff_profiles"),
    Path("data/cache/sports_reference_d1_profile_audit"),
    Path("data/cache/sports_reference_d2_outcome_audit"),
    Path("data/cache/sports_reference_review"),
]
D2_SOURCE_PAGE_AUDIT_CACHE_DIR = Path("data/cache/d2_source_page_audit")

CLASS_SOURCE_FILES = [
    Path("data/modeling/training/source_class_backfill_found.csv"),
    Path("data/big_west_roster_diff_d1_source_stats_found.csv"),
    Path("data/wcc_roster_diff_d1_source_stats_found.csv"),
    Path("data/mwc_roster_diff_d1_source_stats_found.csv"),
    Path("data/a10_roster_diff_d1_source_stats_found.csv"),
    Path("data/aac_roster_diff_d1_source_stats_found.csv"),
    Path("data/mvc_roster_diff_d1_source_stats_found.csv"),
    Path("data/big_west_transfer_source_stats.csv"),
]
PROFILE_URL_OVERRIDES_PATH = Path("data/modeling/training/source_class_profile_url_overrides.csv")
COLLEGE_STAT_SEASONS_OVERRIDES_PATH = Path("data/modeling/training/college_stat_seasons_manual_overrides.csv")

TEAM_ALIASES = {
    "alcorn state": "alcorn st",
    "american": "american univ",
    "arizona state": "arizona st",
    "ball state": "ball st",
    "black hills state": "black hills st",
    "boise state": "boise st",
    "brigham young": "byu",
    "california baptist": "cal baptist",
    "cal state bakersfield": "cs bakersfield",
    "cal state dominguez hills": "csu dom hills",
    "cal state fullerton": "cs fullerton",
    "cal state northridge": "cs northridge",
    "cal state san bernardino": "cs san bern",
    "cal state east bay": "csu east bay",
    "cal poly humboldt": "humboldt st",
    "central arkansas": "cent arkansas",
    "charleston southern": "charleston so",
    "chicago state": "chicago st",
    "chico state": "cs chico",
    "colorado mesa": "co mesa",
    "colorado state": "colorado st",
    "concordia irvine": "concordia ca",
    "coastal carolina": "coastal car",
    "detroit mercy": "detroit",
    "east tennessee state": "etsu",
    "eastern illinois": "e illinois",
    "eastern kentucky": "e kentucky",
    "eastern washington": "e washington",
    "fairleigh dickinson": "f dickinson",
    "florida atlantic": "fl atlantic",
    "florida gulf coast": "fgcu",
    "florida international": "florida intl",
    "florida state": "florida st",
    "fresno state": "fresno st",
    "george washington": "g washington",
    "georgia southern": "ga southern",
    "georgia state": "georgia st",
    "gcu": "grand canyon",
    "grand canyon university": "grand canyon",
    "green bay": "wi green bay",
    "hawaii hilo": "hawaii hilo",
    "hawaii-hilo": "hawaii hilo",
    "houston christian": "houston chr",
    "illinois state": "illinois st",
    "illinois chicago": "il chicago",
    "illinois–chicago": "il chicago",
    "indiana state": "indiana st",
    "incarnate word": "incarnate word",
    "iowa state": "iowa st",
    "jackson state": "jackson st",
    "kansas city": "missouri kc",
    "little rock": "ark little rock",
    "liu": "liu brooklyn",
    "long beach state": "long beach st",
    "louisiana state": "lsu",
    "loyola marymount": "loy marymount",
    "mcneese": "mcneese st",
    "mcneese state": "mcneese st",
    "angelo state": "angelo st",
    "middle tennessee": "mtsu",
    "milwaukee": "wi milwaukee",
    "mississippi state": "mississippi st",
    "missouri state": "missouri st",
    "missouri st louis": "mo st louis",
    "missouri–st louis": "mo st louis",
    "montana state": "montana st",
    "mount st mary s": "mt st mary s",
    "mount st mary's": "mt st mary s",
    "murray state": "murray st",
    "new mexico state": "new mexico st",
    "norfolk state": "norfolk st",
    "morehead state": "morehead st",
    "north carolina central": "nc central",
    "north dakota state": "n dakota st",
    "northern illinois": "n illinois",
    "ohio state": "ohio st",
    "oklahoma state": "oklahoma st",
    "ole miss": "mississippi",
    "oregon state": "oregon st",
    "palm beach atlantic": "palm beach atl",
    "penn state harrisburg": "psu harrisburg",
    "pennsylvania": "penn",
    "portland state": "portland st",
    "sacramento state": "cs sacramento",
    "saint francis pa": "st francis pa",
    "saint joseph s": "st joseph s pa",
    "saint joseph's": "st joseph s pa",
    "saint louis": "st louis",
    "saint mary s": "st mary s ca",
    "saint mary's": "st mary s ca",
    "saint mary's ca": "st mary s ca",
    "saint marys ca": "st mary s ca",
    "saint peter s": "st peter s",
    "saint peter's": "st peter s",
    "san diego state": "san diego st",
    "san francisco state": "s francisco st",
    "san jose state": "san jose st",
    "south carolina state": "s carolina st",
    "southeastern oklahoma state": "se oklahoma",
    "southern": "southern univ",
    "southern california": "usc",
    "southern illinois": "s illinois",
    "southern mississippi": "southern miss",
    "st john s ny": "st john s",
    "st john's ny": "st john s",
    "stephen f austin": "sf austin",
    "tamu corpus christi": "tam c christi",
    "tarleton state": "tarleton st",
    "tennessee state": "tennessee st",
    "texas state": "texas st",
    "texas a m corpus christi": "tam c christi",
    "texas a m–corpus christi": "tam c christi",
    "texas rio grande valley": "utrgv",
    "texas–rio grande valley": "utrgv",
    "ut rio grande valley": "utrgv",
    "utah state": "utah st",
    "ut martin": "tn martin",
    "utsa": "ut san antonio",
    "washington state": "washington st",
    "weber state": "weber st",
    "west texas a m": "w texas a m",
    "west texas a&m": "w texas a m",
    "west virginia state": "wv state",
    "western kentucky": "wku",
    "western michigan": "w michigan",
    "wichita state": "wichita st",
}

KEY_COLUMNS = [
    "target_conference",
    "player_slug",
    "destination_school_slug",
    "first_big_west_season",
]

META_COLUMNS = [
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
    "source_url",
    "outcome_url",
    "source_class",
    "source_class_context",
    "seasons_played_before_transfer",
    "class_entering_destination",
    "years_in_college_entering_destination",
    "college_stat_seasons_before_transfer",
    "college_stat_seasons_source",
]

NUMERIC_FEATURES = [
    "height_in",
    "weight_lbs",
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
    "source_pts_per_40",
    "source_reb_per_40",
    "source_ast_per_40",
    "source_stl_per_40",
    "source_blk_per_40",
    "source_tov_per_40",
    "source_conf_power",
    "destination_conf_power",
    "conf_power_delta",
    "source_team_power",
    "destination_team_power",
    "team_power_delta",
    "projected_destination_mpg",
    "source_low_minutes_flag",
    "source_low_games_flag",
]

CATEGORICAL_FEATURES = [
    "destination_school",
    "position",
    "position_bucket",
    "height_bucket",
    "source_role_bucket",
    "class_entering_destination",
    "source_level",
    "source_conference",
]

TARGET_COLUMNS = [
    "big_west_games",
    "big_west_games_started",
    "big_west_mpg",
    "big_west_minutes",
    "big_west_minutes_share",
    "big_west_ppg",
    "big_west_rpg",
    "big_west_apg",
    "big_west_bpr",
    "big_west_obpr",
    "big_west_dbpr",
    "big_west_bpr_poss",
    "big_west_bpm",
    "big_west_bpm_percentile",
    "big_west_porpag",
    "target_porpag",
    "target_barttorvik_bpm",
    "target_barttorvik_obpm",
    "target_barttorvik_dbpm",
    "production_score",
    "impact_score",
    "outcome_tier",
]


def ensure_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def merge_bart_outcomes(raw: pd.DataFrame) -> pd.DataFrame:
    if not BART_OUTCOMES_PATH.exists():
        return raw.copy()

    bart = pd.read_csv(BART_OUTCOMES_PATH)
    bart_columns = KEY_COLUMNS + [
        "big_west_porpag",
        "barttorvik_bpm",
        "barttorvik_obpm",
        "barttorvik_dbpm",
        "barttorvik_url",
        "barttorvik_player_name",
        "barttorvik_team",
        "match_status",
    ]
    bart = bart[ensure_columns(bart, bart_columns)].copy()
    bart = bart.rename(
        columns={
            "big_west_porpag": "target_porpag_from_bart",
            "barttorvik_bpm": "target_barttorvik_bpm",
            "barttorvik_obpm": "target_barttorvik_obpm",
            "barttorvik_dbpm": "target_barttorvik_dbpm",
            "barttorvik_url": "target_barttorvik_url",
            "barttorvik_player_name": "target_barttorvik_player_name",
            "barttorvik_team": "target_barttorvik_team",
            "match_status": "target_barttorvik_match_status",
        }
    )

    merged = raw.merge(bart, on=KEY_COLUMNS, how="left")
    if "big_west_porpag" not in merged.columns:
        merged["big_west_porpag"] = pd.NA
    merged["big_west_porpag"] = merged["big_west_porpag"].combine_first(merged["target_porpag_from_bart"])
    merged["target_porpag"] = merged["target_porpag_from_bart"].combine_first(merged["big_west_porpag"])
    merged = merged.drop(columns=["target_porpag_from_bart"], errors="ignore")
    return merged


def parse_height_inches(value: object) -> float:
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if not text:
        return np.nan
    numeric = pd.to_numeric(text, errors="coerce")
    if pd.notna(numeric):
        return float(numeric)
    cleaned = text.replace("’", "'").replace("″", '"').replace("“", '"').replace("”", '"')

    match = re.match(r"^\s*(\d+)\s*[-']\s*(\d+)", cleaned)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        return float(feet * 12 + inches)
    return np.nan


def normalize_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def team_key(value: object) -> str:
    key = normalize_key(value)
    return TEAM_ALIASES.get(key, key)


def normalize_class(value: object) -> str:
    if pd.isna(value):
        return "unknown"
    text = str(value).strip().upper().replace(".", "")
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
        "GS": "GR",
        "GRAD": "GR",
        "GRADUATE": "GR",
        "5TH": "GR",
    }
    return aliases.get(text, "unknown")


def class_to_seasons(value: object) -> float:
    normalized = normalize_class(value)
    return {
        "FR": 1.0,
        "SO": 2.0,
        "JR": 3.0,
        "SR": 4.0,
        "GR": 5.0,
    }.get(normalized, np.nan)


def next_class(value: object) -> str:
    normalized = normalize_class(value)
    return {
        "FR": "SO",
        "SO": "JR",
        "JR": "SR",
        "SR": "GR",
        "GR": "GR",
    }.get(normalized, "unknown")


def season_start_year(value: object) -> float:
    match = re.match(r"(\d{4})-\d{2}", str(value))
    return float(match.group(1)) if match else np.nan


def sports_reference_profile_slug(url: object) -> str:
    parsed = urlparse(str(url))
    if "/cbb/players/" not in parsed.path:
        return ""
    return Path(parsed.path).stem


def profile_cache_paths_for_slug(slug: str) -> list[Path]:
    if not slug:
        return []
    paths: list[Path] = []
    for cache_dir in PROFILE_CACHE_DIRS:
        path = cache_dir / f"{slug}.html"
        if path.exists() and path.stat().st_size > 1000:
            paths.append(path)
    return paths


def likely_profile_slug(player_name: object) -> str:
    key = normalize_key(player_name)
    return "-".join(key.split()) if key else ""


def profile_paths_for_row(row: pd.Series) -> list[Path]:
    slugs: list[str] = []
    override_url = profile_url_override_for_row(row)
    override_slug = sports_reference_profile_slug(override_url)
    if override_slug:
        slugs.append(override_slug)
    for column in ["source_url", "outcome_url"]:
        slug = sports_reference_profile_slug(row.get(column, ""))
        if slug:
            slugs.append(slug)
    guessed = likely_profile_slug(row.get("player_name", ""))
    if guessed:
        for index in range(1, 6):
            slugs.append(f"{guessed}-{index}")
    paths: list[Path] = []
    for slug in dict.fromkeys(slugs):
        paths.extend(profile_cache_paths_for_slug(slug))
    return list(dict.fromkeys(paths))


def profile_url_override_for_row(row: pd.Series) -> str:
    if not PROFILE_URL_OVERRIDES_PATH.exists():
        return ""
    if not hasattr(profile_url_override_for_row, "_lookup"):
        overrides = pd.read_csv(PROFILE_URL_OVERRIDES_PATH)
        lookup: dict[tuple[str, str, str], str] = {}
        for _idx, override in overrides.iterrows():
            key = (
                normalize_key(override.get("player_name")),
                normalize_key(override.get("source_school")),
                str(override.get("source_season", "")).strip(),
            )
            url = str(override.get("resolved_sports_reference_profile_url", "")).strip()
            if key[0] and url:
                lookup[key] = url
        profile_url_override_for_row._lookup = lookup
    lookup = profile_url_override_for_row._lookup
    exact_key = (
        normalize_key(row.get("player_name")),
        normalize_key(row.get("source_school")),
        str(row.get("source_season", "")).strip(),
    )
    if exact_key in lookup:
        return lookup[exact_key]
    loose_matches = [
        url
        for (player, school, _season), url in lookup.items()
        if player == exact_key[0] and school == exact_key[1]
    ]
    return loose_matches[0] if len(loose_matches) == 1 else ""


def count_college_stat_seasons_from_profile(path: Path, first_target_season: object) -> float:
    target_start = season_start_year(first_target_season)
    if np.isnan(target_start):
        return np.nan
    counts: list[int] = []
    try:
        tables = pd.read_html(path)
    except (ValueError, ImportError, OSError):
        return np.nan
    for table in tables:
        if not {"Season", "Team"}.issubset(set(table.columns)):
            continue
        profile = table.copy()
        profile["season_start"] = profile["Season"].map(season_start_year)
        profile = profile[profile["season_start"].notna()]
        profile = profile[profile["season_start"] < target_start]
        team_text = profile["Team"].astype(str)
        non_major_or_juco = team_text.str.contains("non-major team|juco", case=False, na=False)
        explicit_dnp = team_text.str.contains("transfer|redshirt|injur|medical|DNP|did not play", case=False, na=False)
        # Sports Reference uses "Did not play - non-major team/juco" for
        # seasons outside its stat coverage. For this feature, those are real
        # college seasons unless the row is explicitly a transfer/redshirt/etc.
        profile = profile[non_major_or_juco | ~explicit_dnp]
        team_text = profile["Team"].astype(str)
        non_major_or_juco = team_text.str.contains("non-major team|juco", case=False, na=False)
        profile = profile[~team_text.str.contains("Career", case=False, na=False)]
        if "G" in profile.columns:
            games = pd.to_numeric(profile["G"], errors="coerce")
            team_text = profile["Team"].astype(str)
            non_major_or_juco = team_text.str.contains("non-major team|juco", case=False, na=False)
            profile = profile[non_major_or_juco | (games.fillna(0) > 0)]
        if not profile.empty:
            counts.append(int(profile["season_start"].nunique()))
    return float(max(counts)) if counts else np.nan


def d2_source_cache_path(url: object) -> Path:
    return D2_SOURCE_PAGE_AUDIT_CACHE_DIR / (quote(str(url), safe="").replace("%", "_")[:180] + ".html")


def count_college_stat_seasons_from_source_page(row: pd.Series) -> tuple[float, str]:
    if str(row.get("source_level", "")).upper() != "D2":
        return np.nan, ""
    path = d2_source_cache_path(row.get("source_url", ""))
    if not path.exists():
        return np.nan, ""
    target_start = season_start_year(row.get("first_big_west_season"))
    if np.isnan(target_start):
        return np.nan, ""
    counts: list[int] = []
    try:
        tables = pd.read_html(path)
    except (ValueError, ImportError, OSError):
        return np.nan, ""
    for table in tables:
        if table.empty:
            continue
        flattened = table.copy()
        flattened.columns = [
            " ".join(str(part) for part in column if str(part) != "nan").strip()
            if isinstance(column, tuple)
            else str(column)
            for column in flattened.columns
        ]
        season_column = flattened.columns[0]
        season_starts = flattened[season_column].map(season_start_year)
        season_rows = flattened[season_starts.notna()].copy()
        if season_rows.empty:
            continue
        season_rows["season_start"] = season_starts[season_starts.notna()].astype(float)
        season_rows = season_rows[season_rows["season_start"] < target_start]
        if season_rows.empty:
            continue
        gp_columns = [column for column in season_rows.columns if column.lower().strip() in {"gp", "g"}]
        if gp_columns:
            gp = pd.to_numeric(season_rows[gp_columns[0]], errors="coerce")
            season_rows = season_rows[gp.fillna(0) > 0]
        if not season_rows.empty:
            counts.append(int(season_rows["season_start"].nunique()))
    return (float(max(counts)), str(path)) if counts else (np.nan, "")


def college_stat_seasons_override_for_row(row: pd.Series) -> tuple[float, str]:
    if not COLLEGE_STAT_SEASONS_OVERRIDES_PATH.exists():
        return np.nan, ""
    if not hasattr(college_stat_seasons_override_for_row, "_lookup"):
        overrides = pd.read_csv(COLLEGE_STAT_SEASONS_OVERRIDES_PATH)
        lookup: dict[tuple[str, str, str], tuple[float, str]] = {}
        for _idx, override in overrides.iterrows():
            value = pd.to_numeric(
                pd.Series([override.get("manual_college_stat_seasons_before_transfer")]),
                errors="coerce",
            ).iloc[0]
            if pd.isna(value):
                continue
            key = (
                normalize_key(override.get("player_name")),
                normalize_key(override.get("source_school")),
                str(override.get("source_season", "")).strip(),
            )
            evidence = str(override.get("manual_evidence_url", "")).strip()
            summary = str(override.get("manual_prior_seasons_summary", "")).strip()
            source = "manual_college_stat_seasons_override"
            if evidence:
                source += f": {evidence}"
            if summary:
                source += f" ({summary})"
            lookup[key] = (float(value), source)
        college_stat_seasons_override_for_row._lookup = lookup
    lookup = college_stat_seasons_override_for_row._lookup
    key = (
        normalize_key(row.get("player_name")),
        normalize_key(row.get("source_school")),
        str(row.get("source_season", "")).strip(),
    )
    return lookup.get(key, (np.nan, ""))


def add_college_stat_seasons(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    values: list[float] = []
    sources: list[str] = []
    for _idx, row in out.iterrows():
        manual_count, manual_source = college_stat_seasons_override_for_row(row)
        if not np.isnan(manual_count):
            values.append(manual_count)
            sources.append(manual_source)
            continue
        counts: list[float] = []
        used_paths: list[str] = []
        for path in profile_paths_for_row(row):
            count = count_college_stat_seasons_from_profile(path, row.get("first_big_west_season"))
            if not np.isnan(count):
                counts.append(count)
                used_paths.append(str(path))
        if counts:
            values.append(float(max(counts)))
            sources.append(";".join(used_paths))
            continue
        source_count, source_path = count_college_stat_seasons_from_source_page(row)
        if not np.isnan(source_count):
            values.append(source_count)
            sources.append(source_path)
            continue
        source_games = pd.to_numeric(pd.Series([row.get("source_games")]), errors="coerce").iloc[0]
        if pd.notna(source_games) and source_games > 0:
            values.append(1.0)
            sources.append("minimum_from_source_stats")
        else:
            values.append(np.nan)
            sources.append("")
    out["college_stat_seasons_before_transfer"] = values
    out["college_stat_seasons_source"] = sources
    return out


def load_source_class_lookup() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in CLASS_SOURCE_FILES:
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        class_column = "class" if "class" in frame.columns else "source_class" if "source_class" in frame.columns else ""
        if not class_column:
            continue
        first_season_col = "first_target_season"
        if first_season_col not in frame.columns:
            first_season_col = "first_wcc_season" if "first_wcc_season" in frame.columns else "first_big_west_season"
        if first_season_col not in frame.columns:
            continue
        for _idx, row in frame.iterrows():
            source_class = normalize_class(row.get(class_column))
            if source_class == "unknown":
                continue
            rows.append(
                {
                    "player_key_for_class": normalize_key(row.get("player_name")),
                    "source_school_key_for_class": normalize_key(row.get("source_school")),
                    "destination_school_key_for_class": normalize_key(row.get("destination_school")),
                    "source_season": str(row.get("source_season", "")).strip(),
                    "first_big_west_season": str(row.get(first_season_col, "")).strip(),
                    "source_class": source_class,
                    "seasons_played_before_transfer": class_to_seasons(source_class),
                    "source_class_context": str(row.get("class_backfill_source", "source_season_class")).strip()
                    or "source_season_class",
                    "source_class_file": str(path),
                }
            )
    if not rows:
        return pd.DataFrame()
    lookup = pd.DataFrame(rows).drop_duplicates(
        [
            "player_key_for_class",
            "source_school_key_for_class",
            "destination_school_key_for_class",
            "source_season",
            "first_big_west_season",
        ],
        keep="first",
    )
    return lookup


def merge_source_class(frame: pd.DataFrame) -> pd.DataFrame:
    lookup = load_source_class_lookup()
    out = frame.copy()
    if lookup.empty:
        out["source_class"] = "unknown"
        out["seasons_played_before_transfer"] = np.nan
        out["source_class_context"] = ""
        out["source_class_file"] = ""
        return out
    out["player_key_for_class"] = out["player_name"].map(normalize_key)
    out["source_school_key_for_class"] = out["source_school"].map(normalize_key)
    out["destination_school_key_for_class"] = out["destination_school"].map(normalize_key)
    out = out.merge(
        lookup,
        on=[
            "player_key_for_class",
            "source_school_key_for_class",
            "destination_school_key_for_class",
            "source_season",
            "first_big_west_season",
        ],
        how="left",
    )
    out["source_class"] = out["source_class"].fillna("unknown")
    out["source_class_context"] = out.get("source_class_context", "").fillna("")
    out = out.drop(
        columns=[
            "player_key_for_class",
            "source_school_key_for_class",
            "destination_school_key_for_class",
        ],
        errors="ignore",
    )
    return out


def load_team_rating_lookup() -> pd.DataFrame:
    if not MASSEY_TEAM_RATINGS_PATH.exists():
        return pd.DataFrame()
    ratings = pd.read_csv(MASSEY_TEAM_RATINGS_PATH)
    ratings["team_match_key"] = ratings["team_key"].map(team_key)
    columns = [
        "season",
        "team_match_key",
        "team",
        "level",
        "power_rank",
        "power",
        "rating_rank",
        "rating",
        "offense_rank",
        "offense",
        "defense_rank",
        "defense",
        "sos_rank",
        "sos",
    ]
    ratings = ratings[[c for c in columns if c in ratings.columns]].drop_duplicates(["season", "team_match_key"], keep="first")
    return ratings


def merge_team_ratings(frame: pd.DataFrame) -> pd.DataFrame:
    ratings = load_team_rating_lookup()
    out = frame.copy()
    if ratings.empty:
        return out

    source = ratings.add_prefix("source_team_").rename(
        columns={
            "source_team_season": "source_season",
            "source_team_team_match_key": "source_team_match_key",
            "source_team_team": "source_team_massey_name",
            "source_team_power": "source_team_power",
        }
    )
    destination = ratings.add_prefix("destination_team_").rename(
        columns={
            "destination_team_season": "first_big_west_season",
            "destination_team_team_match_key": "destination_team_match_key",
            "destination_team_team": "destination_team_massey_name",
            "destination_team_power": "destination_team_power",
        }
    )

    out["source_team_match_key"] = out["source_school"].map(team_key)
    out["destination_team_match_key"] = out["destination_school"].map(team_key)
    out = out.merge(source, on=["source_season", "source_team_match_key"], how="left")
    out = out.merge(destination, on=["first_big_west_season", "destination_team_match_key"], how="left")
    out["team_power_delta"] = pd.to_numeric(out.get("destination_team_power"), errors="coerce") - pd.to_numeric(
        out.get("source_team_power"), errors="coerce"
    )
    return out


def build_training_frame(all_stats: pd.DataFrame) -> pd.DataFrame:
    all_stats = add_derived_features(all_stats)
    columns = (
        ensure_columns(all_stats, META_COLUMNS)
        + ensure_columns(all_stats, NUMERIC_FEATURES)
        + ensure_columns(all_stats, CATEGORICAL_FEATURES)
        + ensure_columns(all_stats, TARGET_COLUMNS)
    )
    # Preserve order while removing duplicates from columns that are both metadata and features.
    columns = list(dict.fromkeys(columns))
    training = all_stats[columns].copy()

    unavailable_prefixes = ("source_evanmiya_",)
    unavailable_columns = [c for c in training.columns if c.startswith(unavailable_prefixes)]
    training = training.drop(columns=unavailable_columns, errors="ignore")
    return training


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = merge_team_ratings(merge_source_class(frame))
    out = add_college_stat_seasons(out)
    class_context = out.get("source_class_context", pd.Series([""] * len(out))).fillna("").astype(str)
    source_class = out.get("source_class", pd.Series(["unknown"] * len(out))).fillna("unknown")
    already_destination_class = class_context.str.contains("next_playable_class", case=False, na=False)
    out["class_entering_destination"] = np.where(
        already_destination_class,
        source_class.map(normalize_class),
        source_class.map(next_class),
    )
    out["years_in_college_entering_destination"] = out["class_entering_destination"].map(class_to_seasons)
    if "height_in" in out.columns:
        out["height_in"] = out["height_in"].apply(parse_height_inches)
    height = pd.to_numeric(out.get("height_in"), errors="coerce")
    mpg = pd.to_numeric(out.get("source_mpg"), errors="coerce")
    games = pd.to_numeric(out.get("source_games"), errors="coerce")

    out["height_bucket"] = pd.cut(
        height,
        bins=[0, 74, 78, 81, 84, 120],
        labels=["small_guard", "wing_guard", "forward", "big_forward", "center"],
        include_lowest=True,
    ).astype("object")
    out["height_bucket"] = out["height_bucket"].fillna("unknown")

    position = out.get("position", pd.Series([""] * len(out))).fillna("").astype(str).str.upper()
    out["position_bucket"] = np.select(
        [
            position.str.contains("G") & ~position.str.contains("F|C"),
            position.str.contains("F") & ~position.str.contains("G|C"),
            position.str.contains("C"),
            position.str.contains("G") & position.str.contains("F"),
        ],
        ["guard", "forward", "center", "wing"],
        default="unknown",
    )

    out["source_role_bucket"] = pd.cut(
        mpg,
        bins=[-0.01, 10, 20, 30, 80],
        labels=["bench", "rotation", "starter", "high_usage_role"],
        include_lowest=True,
    ).astype("object")
    out["source_role_bucket"] = out["source_role_bucket"].fillna("unknown")
    out["source_low_minutes_flag"] = (mpg < 10).fillna(False).astype(int)
    out["source_low_games_flag"] = (games < 10).fillna(False).astype(int)
    return out


def main() -> None:
    raw = pd.read_csv(RAW_SCHEMA_PATH)
    all_stats = merge_bart_outcomes(raw)
    training = build_training_frame(all_stats)
    training["big_west_bpm_percentile"] = pd.to_numeric(training.get("big_west_bpm"), errors="coerce").rank(pct=True) * 100
    training["projected_destination_mpg"] = pd.to_numeric(training.get("big_west_mpg"), errors="coerce")

    ALL_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRAINING_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_stats.to_csv(ALL_STATS_PATH, index=False)
    training.to_csv(TRAINING_PATH, index=False)
    # Keep the existing path fresh for scripts that have not moved yet.
    training.to_csv(LEGACY_D2_AVAILABLE_PATH, index=False)

    manifest = {
        "all_stats_path": str(ALL_STATS_PATH),
        "training_path": str(TRAINING_PATH),
        "legacy_training_copy": str(LEGACY_D2_AVAILABLE_PATH),
        "rows_all_stats": int(len(all_stats)),
        "rows_training": int(len(training)),
        "numeric_features": ensure_columns(training, NUMERIC_FEATURES),
        "categorical_features": ensure_columns(training, CATEGORICAL_FEATURES),
        "targets": {column: int(training[column].notna().sum()) for column in ensure_columns(training, TARGET_COLUMNS)},
        "excluded_from_training": {
            "source_evanmiya_*": "D1-only source features; not available for current D2 projection candidates.",
            "all other non-selected columns": "Kept in all-stats master file, omitted from training-ready table.",
        },
        "porpag_source": str(BART_OUTCOMES_PATH),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote all-stats artifact: {ALL_STATS_PATH} ({all_stats.shape[0]} rows, {all_stats.shape[1]} cols)")
    print(f"Wrote training artifact: {TRAINING_PATH} ({training.shape[0]} rows, {training.shape[1]} cols)")
    print(f"Wrote manifest: {MANIFEST_PATH}")
    print("Target coverage:")
    for column, count in manifest["targets"].items():
        print(f"  {column}: {count}/{len(training)}")


if __name__ == "__main__":
    main()
