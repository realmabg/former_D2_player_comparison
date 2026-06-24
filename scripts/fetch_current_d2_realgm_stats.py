#!/usr/bin/env python3
"""Fetch current D2 stat overrides from RealGM.

This is meant to be run locally and slowly. By default it only tries rows that
the validator already flagged as suspicious. Use --mode all if you want to try
the full current-D2 file.
"""

from __future__ import annotations

import argparse
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from fetch_current_d2_verified_stats import derive_extra_stats, normalize, number, parse_realgm_row, table_rows


DEFAULT_CURRENT_D2 = Path("d2_data_cleaned.csv")
DEFAULT_SUSPICIOUS = Path("data/current_d2_suspicious_event_stats.csv")
DEFAULT_OUTPUT = Path("data/current_d2_realgm_verified_stats.csv")
DEFAULT_MISSING = Path("data/current_d2_realgm_missing.csv")
DEFAULT_CACHE_DIR = Path("data/cache/current_d2_realgm")
DEFAULT_CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
REALGM_SEARCH_URL = "https://basketball.realgm.com/search"


OUTPUT_COLUMNS = [
    "Player Name",
    "Team",
    "Conference",
    "source_url",
    "source_method",
    "realgm_season",
    "realgm_school",
    "realgm_class",
    "match_score",
    "GP",
    "MIN",
    "MPG",
    "FG%",
    "3PT%",
    "FT%",
    "PPG",
    "RPG",
    "APG",
    "TOPG",
    "SPG",
    "BPG",
    "pts_per_40",
    "reb_per_40",
    "ast_per_40",
    "stl_per_40",
    "blk_per_40",
    "tov_per_40",
]


def cache_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_")[:180] + ".html"


def display_name(value: object) -> str:
    raw = str(value or "").strip()
    parts = [part.strip() for part in raw.split(",", 1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        return f"{parts[1]} {parts[0]}".strip()
    return raw


def fetch_url_urllib(url: str, cache_path: Path, sleep: float, refresh: bool) -> str:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not refresh:
        print(f"    cache hit: {cache_path}", flush=True)
        return cache_path.read_text(encoding="utf-8", errors="replace")
    print(f"    urllib fetch: {url}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 current-d2-realgm"})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=45, context=context) as response:
        text = response.read().decode("utf-8", errors="replace")
    cache_path.write_text(text, encoding="utf-8")
    if sleep:
        time.sleep(sleep)
    return text


def fetch_url_chrome(
    url: str,
    cache_path: Path,
    sleep: float,
    refresh: bool,
    chrome_path: Path,
    chrome_user_data_dir: Path,
    virtual_time_budget: int,
    timeout: int,
    allow_open_profile: bool,
    headless_mode: str,
) -> str:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    chrome_user_data_dir.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not refresh:
        print(f"    cache hit: {cache_path}", flush=True)
        return cache_path.read_text(encoding="utf-8", errors="replace")
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome not found at {chrome_path}")
    if not allow_open_profile and chrome_profile_in_use(chrome_user_data_dir):
        raise RuntimeError(
            "Chrome profile is already open. Fully quit the visible RealGM Chrome window with Cmd+Q, "
            "then rerun. If you intentionally want to risk using an open profile, pass --allow-open-chrome-profile."
        )
    command = [
        str(chrome_path),
        f"--headless={headless_mode}",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-crash-reporter",
        "--disable-breakpad",
        "--disable-features=TrustStoreMac,OptimizationHints,MediaRouter",
        "--ignore-certificate-errors",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        f"--user-data-dir={chrome_user_data_dir}",
        f"--virtual-time-budget={virtual_time_budget}",
        "--dump-dom",
        url,
    ]
    print(f"    chrome fetch start: {url}", flush=True)
    print(f"    chrome path: {chrome_path}", flush=True)
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise TimeoutError(f"Chrome timed out after {timeout}s while fetching {url}") from error
    html_text = result.stdout or ""
    print(
        f"    chrome fetch done: return={result.returncode} chars={len(html_text)} stderr_chars={len(result.stderr or '')}",
        flush=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "Chrome failed").strip()
        if result.returncode == -6 or "NSCGSTransaction" in stderr:
            raise RuntimeError(
                "Chrome crashed while dumping the page. This usually happens on macOS when the same "
                f"--chrome-user-data-dir is still open in a visible Chrome window: {chrome_user_data_dir}. "
                "Quit that Chrome window with Cmd+Q and rerun. Raw Chrome error: "
                f"{stderr}"
            )
        raise RuntimeError(stderr)
    if "Request unsuccessful" in html_text or "403 Forbidden" in html_text:
        raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)
    cache_path.write_text(html_text, encoding="utf-8")
    if sleep:
        time.sleep(sleep)
    return html_text


def fetch_url(url: str, cache_path: Path, args: argparse.Namespace) -> str:
    if args.fetcher == "chrome":
        return fetch_url_chrome(
            url,
            cache_path,
            sleep=args.sleep,
            refresh=args.refresh_cache,
            chrome_path=args.chrome_path,
            chrome_user_data_dir=args.chrome_user_data_dir,
            virtual_time_budget=args.virtual_time_budget,
            timeout=args.chrome_timeout,
            allow_open_profile=args.allow_open_chrome_profile,
            headless_mode=args.chrome_headless,
        )
    return fetch_url_urllib(url, cache_path, sleep=args.sleep, refresh=args.refresh_cache)


def chrome_profile_in_use(chrome_user_data_dir: Path) -> bool:
    """Best-effort check for a visible/headless Chrome process using the profile."""
    try:
        result = subprocess.run(
            ["ps", "-axo", "command"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    profile_arg = f"--user-data-dir={chrome_user_data_dir}"
    current_pid = str(os.getpid())
    for line in result.stdout.splitlines():
        if profile_arg in line and current_pid not in line:
            return True
    return False


def search_url(player_name: str) -> str:
    return f"{REALGM_SEARCH_URL}?q={urllib.parse.quote_plus(display_name(player_name))}"


def extract_search_player_links(html_text: str) -> list[tuple[str, str]]:
    """Return (label, absolute_url) pairs from a RealGM search page."""
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r'<a[^>]+href="(?P<href>/player/[^"]+/Summary/\d+)"[^>]*>(?P<label>.*?)</a>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href = match.group("href")
        label = re.sub(r"<[^>]+>", " ", match.group("label"))
        label = re.sub(r"\s+", " ", label).strip()
        url = urllib.parse.urljoin("https://basketball.realgm.com", href)
        if url not in seen:
            links.append((label, url))
            seen.add(url)
    return links


def text_similarity(a: object, b: object) -> float:
    left = normalize(a)
    right = normalize(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.92
    return SequenceMatcher(None, left, right).ratio()


def get_by_alias(row: pd.Series, aliases: list[str]) -> object:
    normalized_columns = {normalize(column): column for column in row.index}
    for alias in aliases:
        alias_norm = normalize(alias)
        if alias_norm in normalized_columns:
            return row[normalized_columns[alias_norm]]
    for column_norm, column in normalized_columns.items():
        column_tokens = set(column_norm.split())
        for alias in aliases:
            alias_norm = normalize(alias)
            if not alias_norm:
                continue
            if len(alias_norm) <= 3:
                if alias_norm in column_tokens:
                    return row[column]
            elif alias_norm in column_norm:
                return row[column]
    return None


def realgm_stat_tables(html_text: str) -> list[pd.DataFrame]:
    out: list[pd.DataFrame] = []
    for table in table_rows(html_text):
        normalized = {normalize(column) for column in table.columns}
        has_school = any(column in normalized for column in ["school", "team"])
        has_gp = "gp" in normalized
        has_season = "season" in normalized
        if has_school and has_gp and has_season:
            out.append(table)
    return out


def player_page_name_score(html_text: str, player_name: str, search_label: str) -> float:
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.IGNORECASE | re.DOTALL)
    h1 = re.sub(r"<[^>]+>", " ", h1_match.group(1)).strip() if h1_match else ""
    return max(text_similarity(player_name, h1), text_similarity(player_name, search_label))


def choose_realgm_row(
    html_text: str,
    player_name: str,
    team: str,
    search_label: str,
) -> tuple[dict[str, object], dict[str, object]] | None:
    name_score = player_page_name_score(html_text, player_name, search_label)
    if name_score < 0.72:
        return None

    best: tuple[float, pd.Series] | None = None
    for table in realgm_stat_tables(html_text):
        for _, row in table.iterrows():
            school = get_by_alias(row, ["School", "Team"])
            gp = number(get_by_alias(row, ["GP"]))
            if not school or not gp:
                continue
            school_score = text_similarity(team, school)
            score = (name_score * 0.55) + (school_score * 0.45)
            if best is None or score > best[0]:
                best = (score, row)

    if best is None or best[0] < 0.70:
        return None

    score, row = best
    stats = derive_extra_stats(parse_realgm_row(row))
    meta = {
        "realgm_season": get_by_alias(row, ["Season"]),
        "realgm_school": get_by_alias(row, ["School", "Team"]),
        "realgm_class": get_by_alias(row, ["Class"]),
        "match_score": round(score, 4),
    }
    return stats, meta


def load_candidates(args: argparse.Namespace) -> pd.DataFrame:
    current = pd.read_csv(args.input)
    if args.mode == "all":
        candidates = current.copy()
    else:
        if not args.suspicious_input.exists():
            raise FileNotFoundError(
                f"{args.suspicious_input} does not exist. Run scripts/validate_current_d2_stats.py first."
            )
        suspicious = pd.read_csv(args.suspicious_input)
        keys = suspicious[["Player Name", "Team"]].drop_duplicates()
        candidates = current.merge(keys, on=["Player Name", "Team"], how="inner")

    if args.names:
        wanted = {normalize(display_name(name)) for name in args.names}
        candidates = candidates[candidates["Player Name"].map(lambda value: normalize(display_name(value))).isin(wanted)]
    candidates = candidates.drop_duplicates(subset=["Player Name", "Team"], keep="first")
    if args.limit:
        candidates = candidates.head(args.limit)
    return candidates.reset_index(drop=True)


def existing_verified(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_CURRENT_D2)
    parser.add_argument("--suspicious-input", type=Path, default=DEFAULT_SUSPICIOUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--mode", choices=["suspicious", "all"], default="suspicious")
    parser.add_argument("--fetcher", choices=["urllib", "chrome"], default="chrome")
    parser.add_argument("--chrome-path", type=Path, default=DEFAULT_CHROME_PATH)
    parser.add_argument("--chrome-user-data-dir", type=Path, default=Path("/tmp/current-d2-realgm-chrome"))
    parser.add_argument("--chrome-headless", choices=["new", "old"], default="old")
    parser.add_argument("--virtual-time-budget", type=int, default=20000)
    parser.add_argument("--chrome-timeout", type=int, default=75)
    parser.add_argument("--allow-open-chrome-profile", action="store_true")
    parser.add_argument("--sleep", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-profiles-per-player", type=int, default=4)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--names", nargs="*", default=[])
    args = parser.parse_args()

    candidates = load_candidates(args)
    verified_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    for idx, row in candidates.iterrows():
        player_name = str(row.get("Player Name", "")).strip()
        team = str(row.get("Team", "")).strip()
        conference = str(row.get("Conference", "")).strip()
        print(f"[{idx + 1}/{len(candidates)}] {player_name} - {team}", flush=True)

        try:
            url = search_url(player_name)
            print(f"  search url: {url}", flush=True)
            search_html = fetch_url(url, args.cache_dir / "search" / cache_name(url), args)
            links = extract_search_player_links(search_html)
            print(f"  RealGM links found: {len(links)}", flush=True)
            if not links:
                raise ValueError("no RealGM player links found from search")

            chosen: tuple[str, dict[str, object], dict[str, object]] | None = None
            for label, profile_url in links[: args.max_profiles_per_player]:
                print(f"  profile candidate: {label} -> {profile_url}", flush=True)
                profile_html = fetch_url(profile_url, args.cache_dir / "profiles" / cache_name(profile_url), args)
                parsed = choose_realgm_row(profile_html, player_name, team, label)
                if parsed is None:
                    print("    no player+school stat-row match", flush=True)
                    continue
                stats, meta = parsed
                print(
                    f"    matched {meta.get('realgm_school')} {meta.get('realgm_season')} score={meta.get('match_score')}",
                    flush=True,
                )
                if chosen is None or float(meta.get("match_score", 0)) > float(chosen[2].get("match_score", 0)):
                    chosen = (profile_url, stats, meta)

            if chosen is None:
                raise ValueError("searched RealGM but could not match a profile row to player+school")

            profile_url, stats, meta = chosen
            verified_rows.append(
                {
                    "Player Name": player_name,
                    "Team": team,
                    "Conference": conference,
                    "source_url": profile_url,
                    "source_method": "realgm_search_profile",
                    **meta,
                    **stats,
                }
            )
            print(f"  OK {meta.get('realgm_school')} {meta.get('realgm_season')} score={meta.get('match_score')}", flush=True)
        except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError, FileNotFoundError) as error:
            missing_rows.append(
                {
                    "Player Name": player_name,
                    "Team": team,
                    "Conference": conference,
                    "reason": str(error),
                    "search_url": search_url(player_name),
                }
            )
            print(f"  MISS {error}", flush=True)

    output = pd.DataFrame(verified_rows)
    if args.append and args.output.exists():
        output = pd.concat([existing_verified(args.output), output], ignore_index=True)
        output = output.drop_duplicates(subset=["Player Name", "Team"], keep="last")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if output.empty:
        pd.DataFrame(columns=OUTPUT_COLUMNS).to_csv(args.output, index=False)
    else:
        for column in OUTPUT_COLUMNS:
            if column not in output.columns:
                output[column] = pd.NA
        output[OUTPUT_COLUMNS].to_csv(args.output, index=False)

    pd.DataFrame(missing_rows).to_csv(args.missing_output, index=False)
    print(f"Wrote {len(output)} RealGM verified rows to {args.output}")
    print(f"Wrote {len(missing_rows)} missing rows to {args.missing_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
