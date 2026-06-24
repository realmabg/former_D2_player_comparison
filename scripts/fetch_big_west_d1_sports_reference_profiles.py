#!/usr/bin/env python3
"""Fetch missing Sports Reference player profile pages for the D1 audit."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd


AUDIT_PATH = Path("data/big_west_d1_sports_reference_profile_audit.csv")
UNVERIFIED_PATH = Path("data/big_west_d1_sports_reference_profile_unverified.csv")
CACHE_DIR = Path("data/cache/sports_reference_d1_profile_audit")
EXTRA_CACHE_DIRS = [
    Path("data/cache/sports_reference_review"),
    Path("data/cache/sports_reference_roster_diff_profiles"),
]
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def slug_from_url(url: str) -> str:
    return Path(url).name.removesuffix(".html")


def profile_cached_anywhere(url: str) -> bool:
    stem = slug_from_url(url)
    candidates = [CACHE_DIR / f"{stem}.html"]
    for cache_dir in EXTRA_CACHE_DIRS:
        candidates.append(cache_dir / f"{stem}.html")
        if stem.endswith("-1"):
            candidates.append(cache_dir / f"{stem[:-2]}.html")
    return any(path.exists() and path.stat().st_size > 1000 for path in candidates)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--max-pages", type=int, default=999)
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    audit = pd.read_csv(UNVERIFIED_PATH if UNVERIFIED_PATH.exists() else AUDIT_PATH)
    urls = sorted(
        {
            str(url)
            for url in audit["profile_url"].dropna()
            if "/cbb/players/" in str(url)
        }
    )

    fetched = 0
    skipped = 0
    failed = []
    for index, url in enumerate(urls, start=1):
        path = CACHE_DIR / f"{slug_from_url(url)}.html"
        if profile_cached_anywhere(url):
            skipped += 1
            continue
        if fetched >= args.max_pages:
            break
        try:
            html = fetch(url)
            path.write_text(html, encoding="utf-8")
            fetched += 1
            print(f"[{index}/{len(urls)}] fetched {url}")
            time.sleep(args.sleep)
        except HTTPError as error:
            failed.append({"url": url, "error": str(error)})
            print(f"[{index}/{len(urls)}] failed {url}: {error}")
            if error.code == 429:
                break
            time.sleep(2.0)
        except (URLError, TimeoutError) as error:
            failed.append({"url": url, "error": str(error)})
            print(f"[{index}/{len(urls)}] failed {url}: {error}")
            time.sleep(args.sleep)

    if failed:
        pd.DataFrame(failed).to_csv(CACHE_DIR / "fetch_failures.csv", index=False)
    print(f"Fetched {fetched}; skipped {skipped}; failed {len(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
