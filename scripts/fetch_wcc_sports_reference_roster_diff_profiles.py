#!/usr/bin/env python3
"""Fetch Sports Reference player profiles needed by the WCC roster-diff audit."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd


AUDIT_PATH = Path("data/wcc_sports_reference_roster_diff_audit.csv")
CACHE_DIR = Path("data/cache/sports_reference_roster_diff_profiles")
USER_AGENT = "Mozilla/5.0 wcc-roster-diff-audit"


def cache_path(url: str) -> Path:
    stem = Path(url).stem
    return CACHE_DIR / f"{stem}.html"


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--sleep", type=float, default=3.5)
    parser.add_argument("--urls-csv", type=Path, default=None)
    parser.add_argument("--url-column", default="sports_reference_player_url")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not AUDIT_PATH.exists():
        raise SystemExit(f"Missing {AUDIT_PATH}; run build_wcc_sports_reference_roster_diff_audit.py first")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if args.urls_csv:
        source = pd.read_csv(args.urls_csv)
        urls = list(dict.fromkeys(source[args.url_column].dropna().astype(str).tolist()))
    else:
        audit = pd.read_csv(AUDIT_PATH)
        needed = audit[
            audit["audit_status"].eq("new_roster_player_needs_profile_check")
            & audit["sports_reference_player_url"].fillna("").ne("")
        ].copy()
        urls = list(dict.fromkeys(needed["sports_reference_player_url"].tolist()))

    fetched = 0
    skipped = 0
    failed = []
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
            continue
        except (urllib.error.URLError, TimeoutError) as error:
            failed.append({"url": url, "status": str(error)})
            continue
        path.write_text(page_html, encoding="utf-8")
        path.with_suffix(".json").write_text(json.dumps({"url": url}, indent=2), encoding="utf-8")
        fetched += 1
        time.sleep(args.sleep)

    print(f"Fetched {fetched} profile pages into {CACHE_DIR}")
    print(f"Skipped {skipped} already-cached profile pages")
    if failed:
        print(f"Failed {len(failed)} profile pages")
        for row in failed[:10]:
            print(f"{row['status']}: {row['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
