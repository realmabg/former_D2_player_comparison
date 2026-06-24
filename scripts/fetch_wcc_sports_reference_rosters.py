#!/usr/bin/env python3
"""Fetch Sports Reference roster pages for WCC transfer discovery."""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path


CACHE_DIR = Path("data/cache/sports_reference_wcc_schools")
USER_AGENT = "Mozilla/5.0 wcc-roster-transfer-audit"

BASE_WCC = [
    "gonzaga",
    "loyola-marymount",
    "pacific",
    "pepperdine",
    "portland",
    "saint-marys-ca",
    "san-diego",
    "san-francisco",
    "santa-clara",
]

TEAMS_BY_SEASON = {
    "2021-22": BASE_WCC + ["brigham-young"],
    "2022-23": BASE_WCC + ["brigham-young"],
    "2023-24": BASE_WCC,
    "2024-25": BASE_WCC + ["oregon-state", "washington-state"],
    "2025-26": BASE_WCC + ["oregon-state", "seattle", "washington-state"],
}


def season_end_year(season: str) -> int:
    return int(season.split("-", 1)[0]) + 1


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sleep", type=float, default=4.0)
    parser.add_argument("--max-pages", type=int, default=999)
    parser.add_argument("--season", choices=sorted(TEAMS_BY_SEASON), default=None)
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetched = 0
    skipped = 0
    failed = []
    seasons = [args.season] if args.season else sorted(TEAMS_BY_SEASON)
    for season in seasons:
        year = season_end_year(season)
        for school_slug in TEAMS_BY_SEASON[season]:
            path = CACHE_DIR / f"{school_slug}_{year}.html"
            if path.exists() and path.stat().st_size > 1000:
                skipped += 1
                continue
            if fetched >= args.max_pages:
                break
            url = f"https://www.sports-reference.com/cbb/schools/{school_slug}/men/{year}.html"
            try:
                html = fetch_url(url)
            except urllib.error.HTTPError as error:
                failed.append({"url": url, "status": f"http_{error.code}"})
                if error.code == 429:
                    break
                continue
            except (urllib.error.URLError, TimeoutError) as error:
                failed.append({"url": url, "status": str(error)})
                continue
            path.write_text(html, encoding="utf-8")
            fetched += 1
            print(f"fetched {url}")
            time.sleep(args.sleep)

    print(f"Fetched {fetched} WCC roster pages into {CACHE_DIR}")
    print(f"Skipped {skipped} already cached pages")
    if failed:
        print(f"Failed {len(failed)} pages")
        for row in failed[:20]:
            print(f"{row['status']}: {row['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
