#!/usr/bin/env python3
"""Fetch only the Sports Reference profiles needed for source-class review.

This intentionally works from the small review CSV created by
``scripts/backfill_source_classes.py``. Run it with a conservative sleep so the
next backfill pass can use cached profile pages instead of repeatedly touching
Sports Reference.
"""

from __future__ import annotations

import argparse
import http.client
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd


REVIEW_PATH = Path("data/modeling/training/source_class_backfill_needs_review.csv")
CACHE_DIR = Path("data/cache/sports_reference_roster_diff_profiles")
STATUS_PATH = Path("data/modeling/training/source_class_profile_fetch_status.csv")
URL_COLUMN = "likely_sports_reference_profile_url"
USER_AGENT = "Mozilla/5.0 source-class-review-profile-fetch"


def cache_path(url: str) -> Path:
    return CACHE_DIR / f"{Path(url).stem}.html"


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=REVIEW_PATH)
    parser.add_argument("--url-column", default=URL_COLUMN)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--status-csv", type=Path, default=STATUS_PATH)
    parser.add_argument("--max-pages", type=int, default=29)
    parser.add_argument("--sleep", type=float, default=8.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    review = pd.read_csv(args.review_csv)
    if args.url_column not in review.columns:
        raise ValueError(f"Missing URL column in {args.review_csv}: {args.url_column}")

    urls = (
        review[args.url_column]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda series: series.ne("")]
        .tolist()
    )
    urls = list(dict.fromkeys(urls))

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    fetched = 0
    skipped = 0

    print(f"Review rows: {len(review)}")
    print(f"Unique profile URLs: {len(urls)}")
    print(f"Cache dir: {args.cache_dir}")
    if args.dry_run:
        for url in urls[: args.max_pages]:
            print(url)
        return 0

    for url in urls:
        path = args.cache_dir / f"{Path(url).stem}.html"
        if not args.force and path.exists() and path.stat().st_size > 1000:
            skipped += 1
            rows.append({"url": url, "status": "cached", "cache_file": str(path)})
            continue
        if fetched >= args.max_pages:
            rows.append({"url": url, "status": "not_attempted_max_pages", "cache_file": str(path)})
            continue

        try:
            page_html = fetch_url(url)
        except urllib.error.HTTPError as error:
            status = f"http_{error.code}"
            rows.append({"url": url, "status": status, "cache_file": str(path)})
            print(f"{status}: {url}")
            if error.code == 429:
                break
            time.sleep(args.sleep)
            continue
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as error:
            status = type(error).__name__
            rows.append({"url": url, "status": status, "cache_file": str(path)})
            print(f"{status}: {url}")
            time.sleep(args.sleep)
            continue

        path.write_text(page_html, encoding="utf-8")
        path.with_suffix(".json").write_text(json.dumps({"url": url}, indent=2), encoding="utf-8")
        rows.append({"url": url, "status": "fetched", "cache_file": str(path)})
        fetched += 1
        print(f"fetched: {url}")
        time.sleep(args.sleep)

    status = pd.DataFrame(rows)
    args.status_csv.parent.mkdir(parents=True, exist_ok=True)
    status.to_csv(args.status_csv, index=False)

    print(f"Fetched {fetched} profile pages")
    print(f"Skipped {skipped} already-cached pages")
    print(f"Wrote status: {args.status_csv}")
    print("Next: run scripts/backfill_source_classes.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
