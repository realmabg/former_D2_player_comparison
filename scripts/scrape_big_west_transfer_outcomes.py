#!/usr/bin/env python3
"""Build first-Big-West-season outcome rows from Sports Reference school pages."""

from __future__ import annotations

import csv
import html
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

from scrape_phase1_d1_outcomes import merge_row, parse_table_rows

TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
PHASE1_OUTCOMES_PATH = Path("data/phase1_d1_outcomes.csv")
CACHE_DIR = Path("data/cache/sports_reference_big_west_schools")
OUTPUT_PATH = Path("data/big_west_transfer_d1_outcomes.csv")
MISSING_PATH = Path("data/big_west_transfer_d1_outcomes_missing.csv")

USER_AGENT = "Mozilla/5.0 big-west-transfer-outcomes"

SCHOOL_SLUGS = {
    "cal-poly": "cal-poly",
    "cal-state-bakersfield": "cal-state-bakersfield",
    "cal-state-fullerton": "cal-state-fullerton",
    "cal-state-northridge": "cal-state-northridge",
    "hawaii": "hawaii",
    "long-beach-state": "long-beach-state",
    "uc-davis": "california-davis",
    "uc-irvine": "california-irvine",
    "uc-riverside": "california-riverside",
    "uc-san-diego": "california-san-diego",
    "uc-santa-barbara": "california-santa-barbara",
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
    "pathway_type",
    "sr_season",
    "sr_team",
    "sr_conf",
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
    "destination_school",
    "destination_school_slug",
    "first_big_west_season",
    "pathway_type",
    "sports_reference_url",
    "reason",
]


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", html.unescape(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\b(jr|jr\.|sr|sr\.|ii|iii|iv|v)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


PLAYER_ALIASES = {
    "kieves turner": {"deuce turner"},
}


def season_end_year(season: str) -> int:
    start = int(season.split("-", 1)[0])
    return start + 1


def school_url(destination_school_slug: str, season: str) -> str:
    school_slug = SCHOOL_SLUGS[destination_school_slug]
    return f"https://www.sports-reference.com/cbb/schools/{school_slug}/men/{season_end_year(season)}.html"


def cache_path(destination_school_slug: str, season: str) -> Path:
    return CACHE_DIR / f"{destination_school_slug}_{season_end_year(season)}.html"


def fetch_school_page(destination_school_slug: str, season: str) -> tuple[str, str]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(destination_school_slug, season)
    url = school_url(destination_school_slug, season)
    if path.exists():
        return path.read_text(encoding="utf-8"), url

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        page_html = response.read().decode("utf-8", errors="replace")
    path.write_text(page_html, encoding="utf-8")
    time.sleep(3.5)
    return page_html, url


def choose_player_row(rows: list[dict[str, str]], player_name: str) -> dict[str, str] | None:
    target = normalize(player_name)
    targets = {target, *PLAYER_ALIASES.get(target, set())}
    for row in rows:
        if normalize(row.get("name_display", "")) in targets:
            return row

    compact_targets = {candidate.replace(" ", "") for candidate in targets}
    for row in rows:
        if normalize(row.get("name_display", "")).replace(" ", "") in compact_targets:
            return row
    return None


def transfer_for_merge(transfer: dict[str, str]) -> dict[str, str]:
    return {
        "player_name": transfer["player_name"],
        "d2_school": transfer["source_school"],
        "d1_school": transfer["destination_school"],
        "d1_conference": transfer["destination_conference"],
        "first_d1_season": transfer["first_big_west_season"],
    }


def outcome_row(
    transfer: dict[str, str],
    per_game: dict[str, str],
    advanced: dict[str, str],
    source_url: str,
) -> dict[str, object]:
    merged = merge_row(transfer_for_merge(transfer), per_game, advanced, source_url)
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
        "pathway_type": transfer["pathway_type"],
        **{column: merged[column] for column in OUTPUT_COLUMNS if column in merged},
    }


def phase1_outcome_row(transfer: dict[str, str], outcome: dict[str, str]) -> dict[str, object]:
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
        "pathway_type": transfer["pathway_type"],
        "sr_season": outcome["sr_season"],
        "sr_team": outcome["sr_team"],
        "sr_conf": outcome["sr_conf"],
        "class": outcome["class"],
        "position": outcome["position"],
        "games": outcome["games"],
        "games_started": outcome["games_started"],
        "mpg": outcome["mpg"],
        "minutes": outcome["minutes"],
        "minutes_share": outcome["minutes_share"],
        "ppg": outcome["ppg"],
        "rpg": outcome["rpg"],
        "apg": outcome["apg"],
        "spg": outcome["spg"],
        "bpg": outcome["bpg"],
        "topg": outcome["topg"],
        "fg_pct": outcome["fg_pct"],
        "fg3_pct": outcome["fg3_pct"],
        "ft_pct": outcome["ft_pct"],
        "efg_pct": outcome["efg_pct"],
        "ts_pct": outcome["ts_pct"],
        "three_rate": outcome["three_rate"],
        "ft_rate": outcome["ft_rate"],
        "per": outcome["per"],
        "ts_pct_advanced": outcome["ts_pct_advanced"],
        "usg_pct": outcome["usg_pct"],
        "ows": outcome["ows"],
        "dws": outcome["dws"],
        "ws": outcome["ws"],
        "ws_per_40": outcome["ws_per_40"],
        "bpm": outcome["bpm"],
        "source_url": outcome["source_url"],
    }


def missing_row(transfer: dict[str, str], url: str, reason: str) -> dict[str, str]:
    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "destination_school": transfer["destination_school"],
        "destination_school_slug": transfer["destination_school_slug"],
        "first_big_west_season": transfer["first_big_west_season"],
        "pathway_type": transfer["pathway_type"],
        "sports_reference_url": url,
        "reason": reason,
    }


def main() -> int:
    transfers = list(csv.DictReader(TRANSFERS_PATH.open(newline="", encoding="utf-8")))
    phase1_outcomes = {}
    if PHASE1_OUTCOMES_PATH.exists():
        with PHASE1_OUTCOMES_PATH.open(newline="", encoding="utf-8") as file:
            phase1_outcomes = {
                (row["player_name"], row["d1_school"], row["first_d1_season"]): row
                for row in csv.DictReader(file)
            }

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    rate_limited = False

    for transfer in transfers:
        season = transfer["first_big_west_season"]
        phase_key = (transfer["player_name"], transfer["destination_school"], season)
        if phase_key in phase1_outcomes:
            rows.append(phase1_outcome_row(transfer, phase1_outcomes[phase_key]))
            continue
        if season_end_year(season) > 2026:
            missing.append(missing_row(transfer, "", "season_not_started"))
            continue
        grouped[(transfer["destination_school_slug"], season)].append(transfer)

    for (destination_slug, season), group in sorted(grouped.items()):
        if rate_limited:
            url = school_url(destination_slug, season) if destination_slug in SCHOOL_SLUGS else ""
            for transfer in group:
                missing.append(missing_row(transfer, url, "sports_reference_rate_limited"))
            continue
        try:
            page_html, url = fetch_school_page(destination_slug, season)
            per_game_rows = parse_table_rows(page_html, "players_per_game")
            advanced_rows = parse_table_rows(page_html, "players_advanced")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, KeyError) as error:
            url = school_url(destination_slug, season) if destination_slug in SCHOOL_SLUGS else ""
            if isinstance(error, urllib.error.HTTPError) and error.code == 429:
                rate_limited = True
            for transfer in group:
                missing.append(missing_row(transfer, url, str(error)))
            print(f"MISS {destination_slug} {season}: {error}")
            continue

        for transfer in group:
            per_game = choose_player_row(per_game_rows, transfer["player_name"])
            advanced = choose_player_row(advanced_rows, transfer["player_name"]) or {}
            if not per_game:
                missing.append(missing_row(transfer, url, "Sports Reference school-season player row not found"))
                print(f"MISS {transfer['player_name']} {season}: row not found")
                continue
            rows.append(outcome_row(transfer, per_game, advanced, url))
            print(f"OK {transfer['player_name']} {season}")

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
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
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
