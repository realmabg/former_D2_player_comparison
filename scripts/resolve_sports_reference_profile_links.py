#!/usr/bin/env python3
"""Resolve Sports Reference player profile URLs from cached roster pages.

This is a local-only audit/helper. It does not fetch web pages. It reads rows
with player/source-season/source-url metadata, opens the cached Sports Reference
team roster page for that source season, and extracts the actual player href
from the roster table links.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd


DEFAULT_INPUT = Path("data/modeling/training/source_class_backfill_needs_review.csv")
DEFAULT_OUTPUT = Path("data/modeling/training/source_class_profile_link_resolution.csv")
DEFAULT_OVERRIDES = Path("data/modeling/training/source_class_profile_url_overrides.csv")
BASE_URL = "https://www.sports-reference.com"
CACHE_ROOT = Path("data/cache")
SOURCE_SCHOOL_CACHE_DIRS = [
    Path("data/cache/sports_reference_source_schools"),
    Path("data/cache/sports_reference_big_west_schools"),
    Path("data/cache/sports_reference_wcc_schools"),
    Path("data/cache/sports_reference_mwc_schools"),
    Path("data/cache/sports_reference_a10_schools"),
    Path("data/cache/sports_reference_aac_schools"),
    Path("data/cache/sports_reference_mvc_schools"),
]
SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_anchor = False
        self._href = ""
        self._text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        self._in_anchor = True
        self._href = attr_map.get("href") or ""
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._in_anchor:
            return
        text = " ".join("".join(self._text_parts).split())
        if text and self._href:
            self.links.append((text, self._href))
        self._in_anchor = False
        self._href = ""
        self._text_parts = []


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def name_tokens(value: object, drop_suffixes: bool = True) -> list[str]:
    tokens = normalize_text(value).split()
    if drop_suffixes:
        tokens = [token for token in tokens if token not in SUFFIX_TOKENS]
    return tokens


def name_key(value: object) -> str:
    return " ".join(name_tokens(value))


def school_cache_path_from_url(url: object) -> Path | None:
    parsed = urlparse(str(url))
    match = re.search(r"/cbb/schools/([^/]+)/men/(\d{4})\.html", parsed.path)
    if not match:
        return None
    filename = f"{match.group(1)}_{match.group(2)}.html"
    for cache_dir in SOURCE_SCHOOL_CACHE_DIRS:
        path = cache_dir / filename
        if path.exists():
            return path
    for path in CACHE_ROOT.glob(f"sports_reference*_schools/{filename}"):
        if path.exists():
            return path
    return SOURCE_SCHOOL_CACHE_DIRS[0] / filename


def player_links_from_cached_roster(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    parser = LinkParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for text, href in parser.links:
        if not re.search(r"/cbb/players/[^/]+\.html$", href):
            continue
        url = urljoin(BASE_URL, href)
        key = (name_key(text), url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"roster_player_name": text, "sports_reference_player_url": url})
    return rows


def first_initial(token: str) -> str:
    return token[:1] if token else ""


def similar_enough(left: str, right: str, threshold: float = 0.86) -> bool:
    if not left or not right:
        return False
    return SequenceMatcher(None, left, right).ratio() >= threshold


def score_candidate(wanted_name: object, roster_name: object) -> tuple[int, str]:
    wanted = name_tokens(wanted_name)
    roster = name_tokens(roster_name)
    if not wanted or not roster:
        return (0, "no_match")
    if wanted == roster:
        return (100, "exact_normalized")
    if " ".join(wanted) == " ".join(roster):
        return (100, "exact_key")
    if wanted[-1] != roster[-1]:
        if len(wanted) >= 2 and len(roster) >= 2 and first_initial(wanted[0]) == first_initial(roster[0]):
            if similar_enough(wanted[-1], roster[-1]):
                return (78, "same_first_initial_similar_last")
        return (0, "no_match")
    if len(wanted) >= 2 and len(roster) >= 2:
        if wanted[0] == roster[0] and similar_enough(wanted[-1], roster[-1]):
            return (88, "same_first_similar_last")
        if wanted[0] in roster[0] or roster[0] in wanted[0]:
            return (76, "same_last_first_name_substring")
    if first_initial(wanted[0]) == first_initial(roster[0]):
        if len(set(wanted) & set(roster)) >= 1:
            return (80, "same_last_first_initial")
        return (70, "same_last_first_initial_only")
    if set(wanted).issubset(set(roster)) or set(roster).issubset(set(wanted)):
        return (65, "token_subset")
    return (0, "no_match")


def override_for_row(row: pd.Series, overrides: pd.DataFrame | None) -> dict[str, object] | None:
    if overrides is None or overrides.empty:
        return None
    required = {"player_name", "source_school", "source_season", "resolved_sports_reference_profile_url"}
    if not required.issubset(set(overrides.columns)):
        return None
    matches = overrides[
        overrides["player_name"].map(name_key).eq(name_key(row.get("player_name", "")))
        & overrides["source_school"].map(normalize_text).eq(normalize_text(row.get("source_school", "")))
        & overrides["source_season"].astype(str).eq(str(row.get("source_season", "")))
    ]
    if matches.empty:
        return None
    match = matches.iloc[0]
    return {
        **row.to_dict(),
        "resolution_status": "resolved_from_manual_override",
        "resolved_sports_reference_profile_url": match["resolved_sports_reference_profile_url"],
        "resolved_roster_player_name": row.get("player_name", ""),
        "match_score": 100,
        "match_method": "manual_override",
        "override_reason": match.get("override_reason", ""),
        "guessed_url_matches_resolved": str(row.get("likely_sports_reference_profile_url", "") or "")
        == str(match["resolved_sports_reference_profile_url"]),
    }


def resolve_row(row: pd.Series, overrides: pd.DataFrame | None = None) -> dict[str, object]:
    override = override_for_row(row, overrides)
    if override is not None:
        return override
    cache_path = school_cache_path_from_url(row.get("source_url", ""))
    base = row.to_dict()
    if cache_path is None:
        return {**base, "resolution_status": "no_sports_reference_source_url"}
    links = player_links_from_cached_roster(cache_path)
    if not cache_path.exists():
        return {
            **base,
            "resolution_status": "source_roster_cache_missing",
            "source_roster_cache_file": str(cache_path),
            "roster_link_count": 0,
        }
    if not links:
        return {
            **base,
            "resolution_status": "no_player_links_in_cached_roster",
            "source_roster_cache_file": str(cache_path),
            "roster_link_count": 0,
        }

    scored = []
    for link in links:
        score, method = score_candidate(row.get("player_name", ""), link["roster_player_name"])
        if score > 0:
            scored.append({**link, "match_score": score, "match_method": method})
    if not scored:
        return {
            **base,
            "resolution_status": "no_name_match_in_cached_roster",
            "source_roster_cache_file": str(cache_path),
            "roster_link_count": len(links),
            "roster_player_names": "; ".join(link["roster_player_name"] for link in links),
        }

    scored = sorted(scored, key=lambda item: item["match_score"], reverse=True)
    best = scored[0]
    guessed_url = str(row.get("likely_sports_reference_profile_url", "") or "")
    resolved_url = best["sports_reference_player_url"]
    return {
        **base,
        "resolution_status": "resolved_from_cached_roster",
        "source_roster_cache_file": str(cache_path),
        "roster_link_count": len(links),
        "resolved_sports_reference_profile_url": resolved_url,
        "resolved_roster_player_name": best["roster_player_name"],
        "match_score": best["match_score"],
        "match_method": best["match_method"],
        "guessed_url_matches_resolved": guessed_url == resolved_url,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overrides-csv", type=Path, default=DEFAULT_OVERRIDES)
    args = parser.parse_args()

    source = pd.read_csv(args.input_csv)
    overrides = pd.read_csv(args.overrides_csv) if args.overrides_csv.exists() else None
    rows = [resolve_row(row, overrides) for _, row in source.iterrows()]
    out = pd.DataFrame(rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_csv, index=False)

    print(f"Read {len(source)} rows: {args.input_csv}")
    print(f"Wrote link resolution: {args.output_csv}")
    if "resolution_status" in out.columns:
        print(out["resolution_status"].value_counts(dropna=False).to_string())
    if "guessed_url_matches_resolved" in out.columns:
        resolved = out[out["resolution_status"].eq("resolved_from_cached_roster")]
        if not resolved.empty:
            print("Resolved URLs where current guess differs:")
            cols = [
                "player_name",
                "source_school",
                "source_season",
                "likely_sports_reference_profile_url",
                "resolved_sports_reference_profile_url",
                "resolved_roster_player_name",
                "match_method",
            ]
            matches_guess = resolved["guessed_url_matches_resolved"].fillna(False).astype(bool)
            diff = resolved[~matches_guess]
            print(diff[[c for c in cols if c in diff.columns]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
