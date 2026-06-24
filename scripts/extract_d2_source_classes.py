#!/usr/bin/env python3
"""Try to extract source class/year for D2 rows from official school pages.

This script is intentionally small and review-oriented. It fetches or reads the
official source pages listed in ``source_class_profile_unresolved.csv``, looks
for the player's official roster/profile link, fetches that bio page, and writes
class candidates for manual review. It does not modify the training data
directly.
"""

from __future__ import annotations

import argparse
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd


INPUT_PATH = Path("data/modeling/training/source_class_profile_unresolved.csv")
OUT_PATH = Path("data/modeling/training/d2_source_class_candidates.csv")
CACHE_DIR = Path("data/cache/d2_source_class_pages")
BIO_CACHE_DIR = Path("data/cache/d2_source_class_bios")
USER_AGENT = "Mozilla/5.0 d2-source-class-review"
CLASS_ALIASES = {
    "fr": "FR",
    "freshman": "FR",
    "r fr": "FR",
    "redshirt freshman": "FR",
    "so": "SO",
    "sophomore": "SO",
    "r so": "SO",
    "redshirt sophomore": "SO",
    "jr": "JR",
    "junior": "JR",
    "r jr": "JR",
    "redshirt junior": "JR",
    "sr": "SR",
    "senior": "SR",
    "r sr": "SR",
    "redshirt senior": "SR",
    "gr": "GR",
    "grad": "GR",
    "graduate": "GR",
    "graduate student": "GR",
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_anchor = False
        self.href = ""
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self.in_anchor = True
        self.href = dict(attrs).get("href") or ""
        self.text_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_anchor:
            self.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self.in_anchor:
            return
        text = " ".join("".join(self.text_parts).split())
        if self.href:
            self.links.append((text, self.href))
        self.in_anchor = False
        self.href = ""
        self.text_parts = []


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def cache_path(url: str) -> Path:
    encoded = urllib.parse.quote(url, safe="")
    return CACHE_DIR / f"{encoded}.html"


def cache_path_for(url: str, cache_dir: Path) -> Path:
    encoded = urllib.parse.quote(url, safe="")
    return cache_dir / f"{encoded}.html"


def fetch_or_read(url: str, sleep: float, force: bool = False, cache_dir: Path = CACHE_DIR) -> tuple[str, Path, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path_for(url, cache_dir)
    if path.exists() and path.stat().st_size > 1000 and not force:
        return path.read_text(encoding="utf-8", errors="replace"), path, "cached"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        html = response.read().decode("utf-8", errors="replace")
    path.write_text(html, encoding="utf-8")
    time.sleep(sleep)
    return html, path, "fetched"


def html_to_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return " ".join(parser.parts)


def name_variants(player_name: str) -> list[str]:
    normalized = normalize_text(player_name)
    parts = normalized.split()
    variants = {normalized}
    if len(parts) >= 2:
        variants.add(f"{parts[-1]} {' '.join(parts[:-1])}")
        variants.add(f"{parts[-1]} {' '.join(parts[:-1]).replace(' ', '')}")
    return sorted(variants, key=len, reverse=True)


def player_slug_tokens(player_name: str) -> set[str]:
    tokens = set(normalize_text(player_name).split())
    return {token for token in tokens if token not in {"jr", "sr", "ii", "iii", "iv", "v"}}


def roster_bio_links(html: str, source_url: str) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html)
    links: list[str] = []
    for _text, href in parser.links:
        if "/sports/mens-basketball/roster/" not in href:
            continue
        url = urljoin(source_url, href)
        if url not in links:
            links.append(url)
    return links


def bio_url_for_player(html: str, source_url: str, player_name: str) -> str:
    wanted = player_slug_tokens(player_name)
    scored: list[tuple[int, str]] = []
    for url in roster_bio_links(html, source_url):
        parts = [part for part in urlparse(url).path.split("/") if part]
        slug = parts[-2] if parts and parts[-1].isdigit() and len(parts) >= 2 else parts[-1]
        slug_tokens = set(normalize_text(slug).split())
        score = len(wanted & slug_tokens)
        if score:
            scored.append((score, url))
    if not scored:
        raise ValueError("Could not find matching roster bio link on stats page")
    scored.sort(reverse=True)
    return scored[0][1]


def class_from_bio_text(text: str) -> list[dict[str, str]]:
    normalized = re.sub(r"\s+", " ", text)
    patterns = [
        r"\bClass\s+(?P<class>Freshman|Sophomore|Junior|Senior|Graduate Student|Graduate|Fr\.?|So\.?|Jr\.?|Sr\.?|Gr\.?)\b",
        r"\bYr\.?\s+(?P<class>Freshman|Sophomore|Junior|Senior|Graduate Student|Graduate|Fr\.?|So\.?|Jr\.?|Sr\.?|Gr\.?)\b",
        r"\bYear\s+(?P<class>Freshman|Sophomore|Junior|Senior|Graduate Student|Graduate|Fr\.?|So\.?|Jr\.?|Sr\.?|Gr\.?)\b",
        r"\bAcademic Year\s+(?P<class>Freshman|Sophomore|Junior|Senior|Graduate Student|Graduate|Fr\.?|So\.?|Jr\.?|Sr\.?|Gr\.?)\b",
    ]
    candidates: list[dict[str, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            raw = match.group("class").replace(".", "").lower()
            source_class = CLASS_ALIASES.get(raw, CLASS_ALIASES.get(raw[:2], ""))
            if not source_class:
                continue
            start = max(0, match.start() - 100)
            end = min(len(normalized), match.end() + 140)
            candidates.append(
                {
                    "source_class_candidate": source_class,
                    "matched_class_text": match.group("class"),
                    "context": normalized[start:end],
                }
            )
    if candidates:
        return candidates
    # Fallback for compact SIDEARM bio headers where "Senior" appears as a field
    # value without a visible "Class" label nearby.
    for raw, source_class in CLASS_ALIASES.items():
        if raw in {"fr", "so", "jr", "sr", "gr"}:
            continue
        match = re.search(rf"\b{re.escape(raw)}\b", normalized, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - 100)
            end = min(len(normalized), match.end() + 140)
            return [
                {
                    "source_class_candidate": source_class,
                    "matched_class_text": match.group(0),
                    "context": normalized[start:end],
                }
            ]
    return []


def class_candidates_near_name(text: str, player_name: str) -> list[dict[str, str]]:
    norm = normalize_text(text)
    candidates: list[dict[str, str]] = []
    for variant in name_variants(player_name):
        start = norm.find(variant)
        if start < 0:
            continue
        window = norm[max(0, start - 160) : start + len(variant) + 260]
        for raw, source_class in CLASS_ALIASES.items():
            pattern = rf"\b{re.escape(raw)}\b"
            if re.search(pattern, window):
                candidates.append(
                    {
                        "source_class_candidate": source_class,
                        "matched_name_variant": variant,
                        "matched_class_text": raw,
                        "context": window,
                    }
                )
        if candidates:
            break
    # Preserve order but dedupe repeated aliases.
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in candidates:
        key = (row["source_class_candidate"], row["matched_class_text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=INPUT_PATH)
    parser.add_argument("--output-csv", type=Path, default=OUT_PATH)
    parser.add_argument("--sleep", type=float, default=4.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = pd.read_csv(args.input_csv)
    d2 = source[source["source_level"].astype(str).eq("D2")].copy()
    rows: list[dict[str, object]] = []
    for _, row in d2.iterrows():
        url = str(row["source_url"])
        if args.dry_run:
            print(f"{row['player_name']}: {url}")
            continue
        try:
            html, path, fetch_status = fetch_or_read(url, args.sleep, force=args.force)
            text = html_to_text(html)
            candidates = class_candidates_near_name(text, str(row["player_name"]))
            bio_url = ""
            bio_path = ""
            bio_fetch_status = ""
            if not candidates:
                bio_url = bio_url_for_player(html, url, str(row["player_name"]))
                bio_html, bio_cache_path, bio_fetch_status = fetch_or_read(
                    bio_url,
                    args.sleep,
                    force=args.force,
                    cache_dir=BIO_CACHE_DIR,
                )
                bio_path = str(bio_cache_path)
                candidates = class_from_bio_text(html_to_text(bio_html))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
            rows.append({**row.to_dict(), "candidate_status": type(error).__name__, "error": str(error)})
            continue
        except ValueError as error:
            rows.append({**row.to_dict(), "candidate_status": "parse_error", "error": str(error)})
            continue

        if not candidates:
            rows.append(
                {
                    **row.to_dict(),
                    "candidate_status": "no_class_candidate_found_near_name",
                    "cache_file": str(path),
                    "fetch_status": fetch_status,
                    "bio_url": bio_url,
                    "bio_cache_file": bio_path,
                    "bio_fetch_status": bio_fetch_status,
                }
            )
            continue
        for candidate in candidates:
            rows.append(
                {
                    **row.to_dict(),
                    "candidate_status": "candidate_found",
                    "cache_file": str(path),
                    "fetch_status": fetch_status,
                    "bio_url": bio_url,
                    "bio_cache_file": bio_path,
                    "bio_fetch_status": bio_fetch_status,
                    **candidate,
                }
            )

    if args.dry_run:
        return 0
    out = pd.DataFrame(rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_csv, index=False)
    print(f"Wrote D2 source class candidates: {args.output_csv} ({len(out)} rows)")
    if not out.empty:
        print(out["candidate_status"].value_counts(dropna=False).to_string())
        cols = [
            "player_name",
            "source_school",
            "source_season",
            "candidate_status",
            "source_class_candidate",
            "matched_class_text",
        ]
        print(out[[c for c in cols if c in out.columns]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
