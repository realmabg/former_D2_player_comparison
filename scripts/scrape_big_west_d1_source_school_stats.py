#!/usr/bin/env python3
"""Cache Sports Reference D1 source-school pages for Big West transfer source stats."""

from __future__ import annotations

import argparse
import csv
import json
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

from build_big_west_transfer_source_stats import choose_school_player_row
from scrape_phase1_d1_outcomes import parse_table_rows

WORK_QUEUE_PATH = Path("data/big_west_source_stats_work_queue.csv")
CACHE_DIR = Path("data/cache/sports_reference_source_schools")
STATUS_PATH = Path("data/big_west_d1_source_school_cache_status.csv")

USER_AGENT = "Mozilla/5.0 big-west-source-school-stats"

SCHOOL_SLUG_OVERRIDES = {
    "alabama-a-m": "alabama-am",
    "byu": "brigham-young",
    "fiu": "florida-international",
    "gcu": "grand-canyon",
    "houston-christian": "houston-baptist",
    "louisiana": "louisiana-lafayette",
    "loyola-chicago": "loyola-il",
    "lsu": "louisiana-state",
    "mcneese": "mcneese-state",
    "north-carolina-a-t": "north-carolina-at",
    "little-rock": "arkansas-little-rock",
    "omaha": "nebraska-omaha",
    "saint-marys": "saint-marys-ca",
    "smu": "southern-methodist",
    "usc": "southern-california",
    "texas-a-m-corpus-christi": "texas-am-corpus-christi",
    "uc-irvine": "california-irvine",
    "uc-davis": "california-davis",
    "uc-san-diego": "california-san-diego",
    "unlv": "nevada-las-vegas",
    "ut-arlington": "texas-arlington",
    "utep": "texas-el-paso",
    "utah-tech": "dixie-state",
    "vcu": "virginia-commonwealth",
}

STATUS_COLUMNS = [
    "source_school",
    "source_school_slug",
    "expected_source_season",
    "sports_reference_url",
    "cache_path",
    "player_count",
    "matched_count",
    "matched_players",
    "missing_players",
    "status",
]


def season_end_year(season: str) -> int:
    return int(season.split("-", 1)[0]) + 1


def sports_reference_slug(source_school_slug: str) -> str:
    source_school_slug = safe_slug(source_school_slug)
    return SCHOOL_SLUG_OVERRIDES.get(source_school_slug, source_school_slug)


def safe_slug(value: str) -> str:
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def school_url(source_school_slug: str, season: str) -> str:
    slug = sports_reference_slug(source_school_slug)
    return f"https://www.sports-reference.com/cbb/schools/{slug}/men/{season_end_year(season)}.html"


def cache_path(source_school_slug: str, season: str) -> Path:
    return CACHE_DIR / f"{safe_slug(source_school_slug)}_{season_end_year(season)}.html"


def fetch_page(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def grouped_priority_rows(priority: str) -> dict[tuple[str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with WORK_QUEUE_PATH.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["source_level"] != "D1":
                continue
            if priority and row["priority"] != priority:
                continue
            groups[(row["source_school_slug"], row["expected_source_season"])].append(row)
    return groups


def status_row(
    source_school_slug: str,
    season: str,
    group: list[dict[str, str]],
    page_html: str,
    url: str,
    path: Path,
    status: str,
) -> dict[str, str | int]:
    rows = parse_table_rows(page_html, "players_per_game")
    matched = []
    missing = []
    for transfer in group:
        if choose_school_player_row(rows, transfer["player_name"]):
            matched.append(transfer["player_name"])
        else:
            missing.append(transfer["player_name"])
    return {
        "source_school": group[0]["source_school"],
        "source_school_slug": source_school_slug,
        "expected_source_season": season,
        "sports_reference_url": url,
        "cache_path": str(path),
        "player_count": len(group),
        "matched_count": len(matched),
        "matched_players": "; ".join(matched),
        "missing_players": "; ".join(missing),
        "status": status,
    }


def missing_status_row(
    source_school_slug: str,
    season: str,
    group: list[dict[str, str]],
    url: str,
    path: Path,
    status: str,
) -> dict[str, str | int]:
    return {
        "source_school": group[0]["source_school"],
        "source_school_slug": source_school_slug,
        "expected_source_season": season,
        "sports_reference_url": url,
        "cache_path": str(path),
        "player_count": len(group),
        "matched_count": 0,
        "matched_players": "",
        "missing_players": "; ".join(row["player_name"] for row in group),
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--priority", default="1", help="Work-queue priority to cache, or empty for all D1 rows")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--sleep", type=float, default=4.0)
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    groups = grouped_priority_rows(args.priority)
    status_rows: list[dict[str, str | int]] = []
    fetched = 0

    for (source_school_slug, season), group in sorted(groups.items()):
        path = cache_path(source_school_slug, season)
        url = school_url(source_school_slug, season)

        if path.exists():
            page_html = path.read_text(encoding="utf-8")
            status_rows.append(status_row(source_school_slug, season, group, page_html, url, path, "cached"))
            continue

        if args.cache_only:
            status_rows.append(missing_status_row(source_school_slug, season, group, url, path, "not_cached"))
            continue

        if fetched >= args.max_pages:
            status_rows.append(missing_status_row(source_school_slug, season, group, url, path, "max_pages_deferred"))
            continue

        try:
            page_html = fetch_page(url)
        except urllib.error.HTTPError as error:
            status_rows.append(missing_status_row(source_school_slug, season, group, url, path, f"http_{error.code}"))
            if error.code == 429:
                break
            continue
        except (urllib.error.URLError, TimeoutError) as error:
            status_rows.append(missing_status_row(source_school_slug, season, group, url, path, str(error)))
            continue

        path.write_text(page_html, encoding="utf-8")
        path.with_suffix(".json").write_text(json.dumps({"url": url}, indent=2), encoding="utf-8")
        fetched += 1
        status_rows.append(status_row(source_school_slug, season, group, page_html, url, path, "fetched"))
        time.sleep(args.sleep)

    with STATUS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=STATUS_COLUMNS)
        writer.writeheader()
        writer.writerows(status_rows)

    print(f"Wrote {len(status_rows)} status rows to {STATUS_PATH}")
    print(f"Fetched {fetched} new pages into {CACHE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
