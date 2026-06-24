#!/usr/bin/env python3
"""Fetch Sports Reference player profile URLs from a CSV into the shared cache."""

from __future__ import annotations

import argparse
import http.client
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd


CACHE_DIR = Path("data/cache/sports_reference_roster_diff_profiles")
USER_AGENT = "Mozilla/5.0 target-conference-profile-fetch"


def cache_path(url: str) -> Path:
    return CACHE_DIR / f"{Path(url).stem}.html"


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls-csv", type=Path, required=True)
    parser.add_argument("--url-column", default="sports_reference_player_url")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep", type=float, default=3.5)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(args.urls_csv)
    urls = list(dict.fromkeys(source[args.url_column].dropna().astype(str).tolist()))

    fetched = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    for url in urls:
        path = cache_path(url)
        if not args.force and path.exists() and path.stat().st_size > 1000:
            skipped += 1
            continue
        if fetched >= args.max_pages:
            break
        try:
            page_html = fetch_url(url)
        except urllib.error.HTTPError as error:
            failed.append({"url": url, "status": f"http_{error.code}"})
            if error.code == 429:
                break
            time.sleep(args.sleep)
            continue
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as error:
            failed.append({"url": url, "status": type(error).__name__})
            time.sleep(args.sleep)
            continue
        path.write_text(page_html, encoding="utf-8")
        path.with_suffix(".json").write_text(json.dumps({"url": url}, indent=2), encoding="utf-8")
        fetched += 1
        time.sleep(args.sleep)

    print(f"Fetched {fetched} profile pages into {CACHE_DIR}")
    print(f"Skipped {skipped} already-cached profile pages")
    if failed:
        print(f"Failed {len(failed)} profile pages")
        for row in failed[:20]:
            print(f"{row['status']}: {row['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
