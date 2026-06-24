#!/usr/bin/env python3
"""Backfill source classes from cached roster/profile pages."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import numpy as np
import pandas as pd


MISSING_PATH = Path("data/modeling/training/source_class_missing_rows.csv")
BACKFILL_INPUT_PATH = Path("data/modeling/training/source_class_backfill_input_rows.csv")
OUT_PATH = Path("data/modeling/training/source_class_backfill_found.csv")
NEEDS_REVIEW_PATH = Path("data/modeling/training/source_class_backfill_needs_review.csv")
PROFILE_LINK_RESOLUTION_PATH = Path("data/modeling/training/source_class_profile_link_resolution.csv")
SOURCE_SCHOOL_CACHE = Path("data/cache/sports_reference_source_schools")
PROFILE_CACHE = Path("data/cache/sports_reference_roster_diff_profiles")

CLASS_ORDER = {"FR": 1.0, "SO": 2.0, "JR": 3.0, "SR": 4.0, "GR": 5.0}
SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def player_key(value: object, drop_suffixes: bool = True) -> str:
    tokens = normalize_text(value).split()
    if drop_suffixes:
        tokens = [token for token in tokens if token not in SUFFIX_TOKENS]
    return " ".join(tokens)


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


def class_to_seasons(source_class: str) -> float:
    return CLASS_ORDER.get(source_class, np.nan)


def season_start_year(value: object) -> float:
    match = re.match(r"(\d{4})-\d{2}", str(value))
    return float(match.group(1)) if match else np.nan


def sports_reference_school_cache_path(url: object) -> Path | None:
    parsed = urlparse(str(url))
    match = re.search(r"/cbb/schools/([^/]+)/men/(\d{4})\.html", parsed.path)
    if not match:
        return None
    return SOURCE_SCHOOL_CACHE / f"{match.group(1)}_{match.group(2)}.html"


def read_tables(path: Path) -> list[pd.DataFrame]:
    if not path.exists():
        return []
    try:
        return pd.read_html(path)
    except (ValueError, ImportError):
        return []


def class_from_school_roster(row: pd.Series) -> dict[str, object] | None:
    cache_path = sports_reference_school_cache_path(row.get("source_url"))
    if cache_path is None or not cache_path.exists():
        return None
    wanted = player_key(row["player_name"])
    wanted_full = player_key(row["player_name"], drop_suffixes=False)
    for table_index, table in enumerate(read_tables(cache_path)):
        if "Player" not in table.columns or "Class" not in table.columns:
            continue
        roster = table[["Player", "Class"]].dropna(subset=["Player"]).copy()
        roster["match_key"] = roster["Player"].map(player_key)
        roster["match_key_full"] = roster["Player"].map(lambda value: player_key(value, drop_suffixes=False))
        matched = roster[(roster["match_key"] == wanted) | (roster["match_key_full"] == wanted_full)]
        if matched.empty:
            continue
        source_class = normalize_class(matched.iloc[0]["Class"])
        if source_class == "unknown":
            continue
        return {
            "source_class": source_class,
            "seasons_played_before_transfer": class_to_seasons(source_class),
            "class_backfill_source": "cached_sports_reference_school_roster",
            "class_backfill_file": str(cache_path),
            "class_backfill_table": table_index,
            "class_backfill_matched_name": matched.iloc[0]["Player"],
        }
    return None


def profile_candidate_paths(player_name: object) -> list[Path]:
    base = "-".join(player_key(player_name).split())
    if not base:
        return []
    candidates: list[Path] = []
    for extension in ("html",):
        candidates.extend(sorted(PROFILE_CACHE.glob(f"{base}-*.{extension}")))
    return candidates


def profile_resolution_paths(row: pd.Series) -> list[Path]:
    if not PROFILE_LINK_RESOLUTION_PATH.exists():
        return []
    try:
        resolved = pd.read_csv(PROFILE_LINK_RESOLUTION_PATH)
    except (OSError, ValueError):
        return []
    required = {"player_name", "source_school", "source_season", "resolved_sports_reference_profile_url"}
    if not required.issubset(set(resolved.columns)):
        return []
    matches = resolved[
        resolved["player_name"].map(player_key).eq(player_key(row["player_name"]))
        & resolved["source_school"].map(normalize_text).eq(normalize_text(row["source_school"]))
        & resolved["source_season"].astype(str).eq(str(row["source_season"]))
    ]
    paths: list[Path] = []
    for url in matches["resolved_sports_reference_profile_url"].dropna().astype(str):
        if not url:
            continue
        path = PROFILE_CACHE / f"{Path(url).stem}.html"
        if path.exists():
            paths.append(path)
    return paths


def sports_reference_search_url(player_name: object) -> str:
    return f"https://www.sports-reference.com/cbb/search/search.fcgi?search={quote_plus(str(player_name))}"


def likely_profile_url(player_name: object) -> str:
    base = "-".join(player_key(player_name).split())
    if not base:
        return ""
    return f"https://www.sports-reference.com/cbb/players/{base}-1.html"


def class_from_profile(row: pd.Series) -> dict[str, object] | None:
    source_season = str(row["source_season"])
    source_school = normalize_text(row["source_school"])
    source_start = season_start_year(source_season)
    candidate_paths = list(dict.fromkeys(profile_resolution_paths(row) + profile_candidate_paths(row["player_name"])))
    for path in candidate_paths:
        for table_index, table in enumerate(read_tables(path)):
            required = {"Season", "Team", "Class"}
            if not required.issubset(set(table.columns)):
                continue
            season_rows = table[table["Season"].astype(str).eq(source_season)].copy()
            if season_rows.empty:
                continue
            season_rows["team_key"] = season_rows["Team"].map(normalize_text)
            playable = season_rows[~season_rows["Team"].astype(str).str.contains("Did not play|Career", case=False, na=False)]
            if not playable.empty:
                matched = playable[playable["team_key"].eq(source_school)]
                if matched.empty:
                    matched = playable
            else:
                matched = season_rows
            source_class = normalize_class(matched.iloc[0]["Class"])
            if source_class == "unknown":
                # Sports Reference labels D2/JUCO seasons as "Did not play -
                # non-major team" and does not attach the class to that row.
                # The next playable D1 row often has the player's listed class;
                # use it as the transfer-time eligibility proxy.
                profile_rows = table.copy()
                profile_rows["season_start"] = profile_rows["Season"].map(season_start_year)
                profile_rows = profile_rows[profile_rows["season_start"].notna()]
                profile_rows = profile_rows[profile_rows["season_start"] >= source_start]
                profile_rows = profile_rows[
                    ~profile_rows["Team"].astype(str).str.contains("Did not play|Career", case=False, na=False)
                ]
                profile_rows["normalized_class"] = profile_rows["Class"].map(normalize_class)
                profile_rows = profile_rows[profile_rows["normalized_class"].ne("unknown")]
                if profile_rows.empty:
                    continue
                matched = profile_rows.sort_values("season_start").iloc[[0]]
                source_class = str(matched.iloc[0]["normalized_class"])
            return {
                "source_class": source_class,
                "seasons_played_before_transfer": class_to_seasons(source_class),
                "class_backfill_source": "cached_sports_reference_player_profile"
                if normalize_class(season_rows.iloc[0]["Class"]) != "unknown"
                else "cached_sports_reference_player_profile_next_playable_class",
                "class_backfill_file": str(path),
                "class_backfill_table": table_index,
                "class_backfill_matched_name": row["player_name"],
            }
    return None


def main() -> int:
    input_path = BACKFILL_INPUT_PATH if BACKFILL_INPUT_PATH.exists() else MISSING_PATH
    missing = pd.read_csv(input_path)
    found_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []

    for _idx, row in missing.iterrows():
        backfill = class_from_school_roster(row)
        if backfill is None:
            backfill = class_from_profile(row)
        base = row.to_dict()
        if backfill is None:
            profile_candidates = [str(path) for path in profile_candidate_paths(row["player_name"])]
            review_rows.append(
                {
                    **base,
                    "review_reason": "no_cached_roster_or_profile_class_match",
                    "profile_candidates": ";".join(profile_candidates),
                    "sports_reference_search_url": sports_reference_search_url(row["player_name"]),
                    "likely_sports_reference_profile_url": likely_profile_url(row["player_name"]),
                }
            )
        else:
            found_rows.append({**base, **backfill})

    found = pd.DataFrame(found_rows)
    review = pd.DataFrame(review_rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    found.to_csv(OUT_PATH, index=False)
    review.to_csv(NEEDS_REVIEW_PATH, index=False)

    print(f"Read class backfill input: {input_path}")
    print(f"Found class backfills: {len(found)}/{len(missing)} -> {OUT_PATH}")
    if not found.empty:
        print(found["source_class"].value_counts().to_string())
        print(found["class_backfill_source"].value_counts().to_string())
    print(f"Still needs review: {len(review)} -> {NEEDS_REVIEW_PATH}")
    if not review.empty:
        print(review.groupby(["target_conference", "source_level"], dropna=False).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
