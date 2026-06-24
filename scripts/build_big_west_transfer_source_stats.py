#!/usr/bin/env python3
"""Build pre-transfer source-season stat rows for Big West inbound transfers."""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

from scrape_phase1_d1_outcomes import merge_row, parse_table_rows

TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
PHASE1_SCHOOL_STATS_PATH = Path("data/phase1_school_stats.csv")
SUPPLEMENTAL_D2_STATS_PATH = Path("data/big_west_missing_d2_source_stats.csv")
OUTPUT_PATH = Path("data/big_west_transfer_source_stats.csv")
MISSING_PATH = Path("data/big_west_transfer_source_stats_missing.csv")
SUPPORTED_SOURCE_LEVELS = {"D1", "D2", "JUCO", "NAIA"}

SPORTS_REFERENCE_CACHES = [
    Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/cache/sports_reference"),
    Path("data/cache/sports_reference_review"),
]
SPORTS_REFERENCE_SOURCE_SCHOOL_CACHE = Path("data/cache/sports_reference_source_schools")

SCHOOL_ALIASES = {
    "gcu": {"grand canyon"},
}

PLAYER_ALIASES = {
    "aleks szymczyk": {"aleksander szymczyk"},
    "ben griscti": {"benjamin griscti"},
    "carl daughtery": {"carl daugherty"},
    "dre bullock": {"quandre bullock"},
    "isa silva": {"isael silva"},
    "john square": {"john mikey square"},
    "josh o garro": {"joshua o garro"},
    "kjay bradley": {"kevin bradley"},
    "kieves turner": {"deuce turner"},
    "ronald jessamy": {"ron jessamy"},
    "shay johnson": {"demarshay johnson"},
}

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
    "source_stat_level",
    "source_stat_source",
    "class",
    "position",
    "games",
    "games_started",
    "mpg",
    "minutes",
    "minutes_share",
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
    "ts_pct",
    "three_rate",
    "ft_rate",
    "per",
    "ts_pct_advanced",
    "usg_pct",
    "ows",
    "dws",
    "ws",
    "ws_per_40",
    "bpm",
    "source_url",
]

MISSING_COLUMNS = [
    "player_name",
    "player_slug",
    "source_school",
    "source_school_slug",
    "source_level",
    "destination_school",
    "destination_school_slug",
    "first_big_west_season",
    "expected_source_season",
    "reason",
]


def normalize(value: str) -> str:
    value = str(value).replace("\u2013", "-").replace("\u2014", "-")
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = value.lower()
    value = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def safe_slug(value: str) -> str:
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def school_matches(source_school: str, row_school: str) -> bool:
    source = normalize(source_school)
    row = normalize(row_school)
    return row == source or row in SCHOOL_ALIASES.get(source, set())


def choose_source_row(rows: list[dict[str, str]], season: str, school: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("year_id") == season and school_matches(school, row.get("team_name_abbr", "")):
            return row
    return None


def previous_season(season: str) -> str:
    start = int(season.split("-", 1)[0])
    return f"{start - 1}-{str(start)[-2:]}"


def source_season_candidates(first_big_west_season: str, max_lookback: int = 3) -> list[str]:
    seasons = []
    season = previous_season(first_big_west_season)
    for _ in range(max_lookback):
        seasons.append(season)
        season = previous_season(season)
    return seasons


def zero_advanced() -> dict[str, str]:
    return {
        "per": "",
        "ts_pct_advanced": "",
        "usg_pct": "",
        "ows": "",
        "dws": "",
        "ws": "",
        "ws_per_40": "",
        "bpm": "",
    }


def numeric(value: str) -> float:
    if value == "":
        return 0.0
    if value.startswith("."):
        value = f"0{value}"
    return float(value)


def phase1_rows() -> dict[tuple[str, str, str, str], dict[str, str]]:
    rows = {}
    for path in [PHASE1_SCHOOL_STATS_PATH, SUPPLEMENTAL_D2_STATS_PATH]:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                key = (
                    normalize(row["Player Name"]),
                    normalize(row["Team"]),
                    normalize(row["d1_school"]),
                    row["Season"],
                )
                rows[key] = row
    return rows


def phase1_fallback_row(
    rows: dict[tuple[str, str, str, str], dict[str, str]],
    transfer: dict[str, str],
    expected_season: str,
) -> dict[str, str] | None:
    candidates = [
        row
        for (player_name, team, destination, _season), row in rows.items()
        if player_name == normalize(transfer["player_name"])
        and team == normalize(transfer["source_school"])
        and destination == normalize(transfer["destination_school"])
        and row["Season"] <= expected_season
    ]
    return max(candidates, key=lambda row: row["Season"]) if candidates else None


def d2_output_row(transfer: dict[str, str], stats: dict[str, str]) -> dict[str, object]:
    games = numeric(stats["GP"])
    mpg = numeric(stats["MPG"])
    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "source_school": transfer["source_school"],
        "source_school_slug": transfer["source_school_slug"],
        "source_conference": transfer["source_conference"],
        "source_level": transfer["source_level"],
        "destination_school": transfer["destination_school"],
        "destination_school_slug": transfer["destination_school_slug"],
        "first_big_west_season": transfer["first_big_west_season"],
        "source_season": stats["Season"],
        "source_stat_level": transfer["source_level"],
        "source_stat_source": "phase1_school_stats",
        "class": stats["Year"],
        "position": stats["Position"],
        "games": int(games),
        "games_started": "",
        "mpg": mpg,
        "minutes": numeric(stats["MIN"]),
        "minutes_share": mpg / 40 if mpg else 0,
        "ppg": numeric(stats["PPG"]),
        "rpg": numeric(stats["RPG"]),
        "apg": numeric(stats["APG"]),
        "spg": numeric(stats["SPG"]),
        "bpg": numeric(stats["BPG"]),
        "topg": numeric(stats["TOPG"]),
        "fg_pct": numeric(stats["FG%"]),
        "fg3_pct": numeric(stats["3PT%"]),
        "ft_pct": numeric(stats["FT%"]),
        "efg_pct": numeric(stats["eFG"]),
        "ts_pct": numeric(stats["TS_pct"]),
        "three_rate": numeric(stats["three_share"]),
        "ft_rate": numeric(stats["FTR"]),
        **zero_advanced(),
        "source_url": stats["source_url"],
    }


def cached_player_pages() -> list[tuple[Path, str]]:
    pages = []
    for cache_dir in SPORTS_REFERENCE_CACHES:
        if not cache_dir.exists():
            continue
        for path in sorted(cache_dir.glob("*.html")):
            meta_path = path.with_suffix(".json")
            source_url = ""
            if meta_path.exists():
                source_url = json.loads(meta_path.read_text(encoding="utf-8")).get("url", "")
            pages.append((path, source_url))
    return pages


def cached_source_school_page(source_school_slug: str, season: str) -> tuple[Path, str] | None:
    end_year = int(season.split("-", 1)[0]) + 1
    path = SPORTS_REFERENCE_SOURCE_SCHOOL_CACHE / f"{safe_slug(source_school_slug)}_{end_year}.html"
    if not path.exists():
        return None
    meta_path = path.with_suffix(".json")
    source_url = ""
    if meta_path.exists():
        source_url = json.loads(meta_path.read_text(encoding="utf-8")).get("url", "")
    return path, source_url


def sr_slug(value: str) -> str:
    value = value.rsplit("/", 1)[-1].replace(".html", "")
    value = re.sub(r"-\d+$", "", value)
    return normalize(value)


def page_matches_player(path: Path, source_url: str, transfer: dict[str, str]) -> bool:
    candidates = {
        normalize(transfer["player_name"]),
        normalize(transfer["player_slug"]),
    }
    candidates.update(PLAYER_ALIASES.get(normalize(transfer["player_name"]), set()))
    page_keys = {normalize(path.stem)}
    if source_url:
        page_keys.add(sr_slug(source_url))
    return bool(candidates & page_keys)


def name_matches(player_name: str, row_name: str) -> bool:
    target = normalize(player_name)
    targets = {target, *PLAYER_ALIASES.get(target, set())}
    row = normalize(row_name)
    compact_row = row.replace(" ", "")
    return any(row == candidate or compact_row == candidate.replace(" ", "") for candidate in targets)


def choose_school_player_row(rows: list[dict[str, str]], player_name: str) -> dict[str, str] | None:
    for row in rows:
        if name_matches(player_name, row.get("name_display", "")):
            return row
    return None


def source_school_cache_row(transfer: dict[str, str], expected_season: str) -> dict[str, object] | None:
    cached_page = cached_source_school_page(transfer["source_school_slug"], expected_season)
    if not cached_page:
        return None

    path, source_url = cached_page
    page_html = path.read_text(encoding="utf-8")
    per_game = choose_school_player_row(parse_table_rows(page_html, "players_per_game"), transfer["player_name"])
    if not per_game:
        return None
    advanced = choose_school_player_row(parse_table_rows(page_html, "players_advanced"), transfer["player_name"]) or {}

    per_game = per_game.copy()
    advanced = advanced.copy()
    per_game["year_id"] = expected_season
    per_game["team_name_abbr"] = transfer["source_school"]
    per_game["conf_abbr"] = transfer["source_conference"]
    advanced["year_id"] = expected_season
    advanced["team_name_abbr"] = transfer["source_school"]
    advanced["conf_abbr"] = transfer["source_conference"]
    row = sr_transfer_row(transfer, per_game, advanced, source_url)
    row["source_stat_source"] = "sports_reference_source_school_cache"
    return row


def sr_transfer_row(transfer: dict[str, str], per_game: dict[str, str], advanced: dict[str, str], source_url: str) -> dict[str, object]:
    proxy = {
        "player_name": transfer["player_name"],
        "d2_school": transfer["source_school"],
        "d1_school": transfer["source_school"],
        "d1_conference": transfer["source_conference"],
        "first_d1_season": per_game["year_id"],
    }
    merged = merge_row(proxy, per_game, advanced, source_url)
    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "source_school": transfer["source_school"],
        "source_school_slug": transfer["source_school_slug"],
        "source_conference": transfer["source_conference"],
        "source_level": transfer["source_level"],
        "destination_school": transfer["destination_school"],
        "destination_school_slug": transfer["destination_school_slug"],
        "first_big_west_season": transfer["first_big_west_season"],
        "source_season": per_game["year_id"],
        "source_stat_level": transfer["source_level"],
        "source_stat_source": "sports_reference_cache",
        "class": merged["class"],
        "position": merged["position"],
        "games": merged["games"],
        "games_started": merged["games_started"],
        "mpg": merged["mpg"],
        "minutes": merged["minutes"],
        "minutes_share": merged["minutes_share"],
        "ppg": merged["ppg"],
        "rpg": merged["rpg"],
        "apg": merged["apg"],
        "spg": merged["spg"],
        "bpg": merged["bpg"],
        "topg": merged["topg"],
        "fg_pct": merged["fg_pct"],
        "fg3_pct": merged["fg3_pct"],
        "ft_pct": merged["ft_pct"],
        "efg_pct": merged["efg_pct"],
        "ts_pct": merged["ts_pct"],
        "three_rate": merged["three_rate"],
        "ft_rate": merged["ft_rate"],
        "per": merged["per"],
        "ts_pct_advanced": merged["ts_pct_advanced"],
        "usg_pct": merged["usg_pct"],
        "ows": merged["ows"],
        "dws": merged["dws"],
        "ws": merged["ws"],
        "ws_per_40": merged["ws_per_40"],
        "bpm": merged["bpm"],
        "source_url": source_url,
    }


def missing_row(transfer: dict[str, str], expected_source_season: str, reason: str) -> dict[str, str]:
    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "source_school": transfer["source_school"],
        "source_school_slug": transfer["source_school_slug"],
        "source_level": transfer["source_level"],
        "destination_school": transfer["destination_school"],
        "destination_school_slug": transfer["destination_school_slug"],
        "first_big_west_season": transfer["first_big_west_season"],
        "expected_source_season": expected_source_season,
        "reason": reason,
    }


def main() -> int:
    transfers = list(csv.DictReader(TRANSFERS_PATH.open(newline="", encoding="utf-8")))
    d2_by_key = phase1_rows()
    pages = cached_player_pages()
    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []

    for transfer in transfers:
        if transfer["source_level"] not in SUPPORTED_SOURCE_LEVELS:
            continue

        expected_season = previous_season(transfer["first_big_west_season"])
        if transfer["source_level"] == "D2":
            key = (
                normalize(transfer["player_name"]),
                normalize(transfer["source_school"]),
                normalize(transfer["destination_school"]),
                expected_season,
            )
            stats = d2_by_key.get(key) or phase1_fallback_row(d2_by_key, transfer, expected_season)
            if stats:
                rows.append(d2_output_row(transfer, stats))
                continue

        if transfer["source_level"] == "D1":
            found_source = False
            for candidate_season in source_season_candidates(transfer["first_big_west_season"]):
                source_school_row = source_school_cache_row(transfer, candidate_season)
                if source_school_row:
                    rows.append(source_school_row)
                    found_source = True
                    break
            if not found_source:
                found = False
                for path, source_url in pages:
                    if not page_matches_player(path, source_url, transfer):
                        continue
                    page_html = path.read_text(encoding="utf-8")
                    per_game_rows = parse_table_rows(page_html, "players_per_game")
                    advanced_rows = parse_table_rows(page_html, "players_advanced")
                    for candidate_season in source_season_candidates(transfer["first_big_west_season"]):
                        per_game = choose_source_row(per_game_rows, candidate_season, transfer["source_school"])
                        if per_game:
                            advanced = choose_source_row(advanced_rows, candidate_season, transfer["source_school"]) or {}
                            rows.append(sr_transfer_row(transfer, per_game, advanced, source_url))
                            found = True
                            break
                    if found:
                        break
                if not found:
                    pass
                else:
                    continue
            if found_source:
                continue

        if transfer["source_level"] in {"JUCO", "NAIA"}:
            reason = "source_level_not_yet_supported"
        elif transfer["source_level"] == "D1":
            reason = "sports_reference_source_row_not_in_local_cache"
        elif transfer["source_level"] == "D2":
            reason = "d2_source_row_not_in_phase1_school_stats"
        else:
            reason = "unknown_source_level"
        missing.append(missing_row(transfer, expected_season, reason))

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
