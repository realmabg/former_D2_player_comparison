#!/usr/bin/env python3
"""Fetch Sports Reference roster pages for configured target conferences."""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path

from target_conference_configs import TEAMS_BY_CONFERENCE_SEASON, season_end_year


USER_AGENT = "Mozilla/5.0 target-conference-roster-transfer-audit"


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conference", choices=sorted(TEAMS_BY_CONFERENCE_SEASON), required=True)
    parser.add_argument("--sleep", type=float, default=4.0)
    parser.add_argument("--max-pages", type=int, default=999)
    parser.add_argument("--season", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cache_dir = Path(f"data/cache/sports_reference_{args.conference}_schools")
    cache_dir.mkdir(parents=True, exist_ok=True)
    teams_by_season = TEAMS_BY_CONFERENCE_SEASON[args.conference]
    seasons = [args.season] if args.season else sorted(teams_by_season)

    fetched = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    for season in seasons:
        year = season_end_year(season)
        for school_slug in teams_by_season[season]:
            path = cache_dir / f"{school_slug}_{year}.html"
            if not args.force and path.exists() and path.stat().st_size > 1000:
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

    print(f"Fetched {fetched} roster pages into {cache_dir}")
    print(f"Skipped {skipped} already cached pages")
    if failed:
        print(f"Failed {len(failed)} pages")
        for row in failed[:20]:
            print(f"{row['status']}: {row['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
