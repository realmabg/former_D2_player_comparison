#!/usr/bin/env python3
"""Build Massey conference power input from saved Massey pages or CSV exports.

Massey currently protects pages with Cloudflare/Turnstile in some environments.
This script supports both live fetch attempts and saved-page imports so the model
pipeline does not depend on repeated browser access.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

NEEDED_PATH = Path("data/massey_conference_power_needed.csv")
OUTPUT_PATH = Path("data/massey_conference_power.csv")
MISSING_PATH = Path("data/massey_conference_power_missing.csv")
CACHE_DIR = Path("data/cache/massey_conference_power")

USER_AGENT = "Mozilla/5.0 massey-conference-power"

CONFERENCE_ALIASES = {
    "a 10": "Atlantic 10",
    "aac": "American",
    "acc": "ACC",
    "american athletic": "American",
    "ameast": "America East",
    "america east": "America East",
    "atlantic coast": "ACC",
    "atlantic 10": "Atlantic 10",
    "atlantic sun": "ASUN",
    "big 10": "Big Ten",
    "big 12": "Big XII",
    "big east": "Big East",
    "big sky": "Big Sky",
    "big south": "Big South",
    "big ten": "Big Ten",
    "big west": "Big West",
    "big xii": "Big XII",
    "c usa": "C-USA",
    "caa": "Colonial",
    "california caa": "CCAA",
    "ccaa": "CCAA",
    "colonial": "Colonial",
    "coastal": "Colonial",
    "conference usa": "C-USA",
    "cusa": "C-USA",
    "gac": "GAC",
    "glvc": "GLVC",
    "gnac": "GNAC",
    "great american": "GAC",
    "great lakes iac": "GLIAC",
    "great lakes valley": "GLVC",
    "great lakes val": "GLVC",
    "great northwest": "GNAC",
    "gsc": "GSC",
    "gulf south": "GSC",
    "horizon": "Horizon",
    "ivy": "Ivy",
    "ivy league": "Ivy",
    "lone star": "LSC",
    "lsc": "LSC",
    "maac": "MAAC",
    "mac": "MAC",
    "meac": "MEAC",
    "metro atlantic": "MAAC",
    "mid eastern ac": "MEAC",
    "miaa": "MIAA",
    "mid america iaa": "MIAA",
    "mid american": "MAC",
    "missouri valley": "Missouri Valley",
    "missouri val": "Missouri Valley",
    "mvc": "Missouri Valley",
    "mountain west": "Mountain West",
    "mwc": "Mountain West",
    "nec": "Northeast",
    "northeast": "Northeast",
    "oh valley": "Ohio Valley",
    "ohio valley": "Ohio Valley",
    "ovc": "Ohio Valley",
    "pac 12": "PAC 12",
    "pacific west": "PacWest",
    "pacwest": "PacWest",
    "patriot": "Patriot League",
    "patriot league": "Patriot League",
    "rmac": "RMAC",
    "rocky mountain": "RMAC",
    "rocky mtn ac": "RMAC",
    "sec": "SEC",
    "southeastern": "SEC",
    "sciac": "Southern Cal IAC",
    "siac": "SIAC",
    "southern iac": "SIAC",
    "southern": "Southern",
    "southland": "Southland",
    "ssc": "SSC",
    "sunshine state": "SSC",
    "southwestern ac": "SWAC",
    "summit": "Summit League",
    "summit lg": "Summit League",
    "summit league": "Summit League",
    "sun belt": "Sun Belt",
    "swac": "SWAC",
    "wac": "WAC",
    "west coast": "West Coast",
    "wcc": "West Coast",
    "western athletic": "WAC",
}

CONFERENCE_COLUMNS = [
    "conference",
    "conf",
    "league",
    "name",
    "team",
]
POWER_COLUMNS = [
    "power",
    "pwr",
    "conference_power",
    "rating",
    "rat",
    "rate",
    "massey_power",
    "massey_rating",
    "mean",
    "avg",
]

COPIED_TEXT_COLUMNS = [
    "season",
    "conference",
    "level",
    "rec",
    "win_pct",
    "tms",
    "rat_rank",
    "rat",
    "pwr_rank",
    "pwr",
    "off_rank",
    "off",
    "def_rank",
    "def",
    "hfa",
    "sos_rank",
    "sos",
    "source_file",
]


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def canonical_conference(value: object) -> str:
    clean = normalize(value)
    return CONFERENCE_ALIASES.get(clean, str(value).strip())


def season_end_year(season: str) -> int:
    return int(season.split("-", 1)[0]) + 1


def normalize_season(value: object, fallback: str = "") -> str:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return fallback
    if re.match(r"^\d{4}-\d{2}$", text):
        return text
    if re.match(r"^\d{2}-\d{2}$", text):
        start = int(text.split("-", 1)[0])
        century = 2000 if start < 80 else 1900
        return f"{century + start}-{text.split('-', 1)[1]}"
    if re.match(r"^\d{4}$", text):
        start = int(text)
        return f"{start}-{str(start + 1)[-2:]}"
    return text


def default_url(season: str, level: str) -> str:
    level_slug = "ncaa-d1" if level == "D1" else "ncaa-d2"
    return f"https://masseyratings.com/cb{season_end_year(season)}/{level_slug}/ratings"


def read_needed(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    deduped = {}
    for row in rows:
        deduped[(row["season"], canonical_conference(row["conference"]), row["level"])] = {
            "season": row["season"],
            "conference": canonical_conference(row["conference"]),
            "level": row["level"],
        }
    return list(deduped.values())


def fetch_url(url: str, cache_path: Path) -> str:
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        text = response.read().decode("utf-8", errors="replace")
    cache_path.write_text(text, encoding="utf-8")
    time.sleep(2.5)
    return text


def looks_blocked(text: str) -> bool:
    lowered = text.lower()
    return (
        "just a moment" in lowered
        and "cloudflare" in lowered
        or "security verification" in lowered
        or "cf-turnstile-response" in lowered
    )


def select_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {normalize(column): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for column in columns:
        clean = normalize(column)
        if any(candidate in clean.split() for candidate in candidates):
            return column
    return None


def parse_numeric(value: object) -> float | None:
    text = str(value).strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def split_record_win_pct(value: str) -> tuple[str, float | None]:
    match = re.match(r"^\s*(\d+)-(\d+)(0\.\d+)\s*$", value)
    if not match:
        return value.strip(), None
    wins, losses, win_pct = match.groups()
    return f"{wins}-{losses}", float(win_pct)


def split_rank_value(value: str, min_value: float, max_value: float) -> tuple[int | None, float | None]:
    text = value.strip().replace(",", "")
    signed_match = re.match(r"^(\d+)([-+]\d+(?:\.\d+)?)$", text)
    if signed_match:
        rank_text, value_text = signed_match.groups()
        numeric_value = float(value_text)
        if min_value <= numeric_value <= max_value:
            return int(rank_text), numeric_value
    if re.match(r"^\d+\.\d+$", text):
        whole, decimal = text.split(".", 1)
        for split_at in range(1, len(whole) + 1):
            rank_text = whole[:split_at]
            value_text = f"{whole[split_at:] or '0'}.{decimal}"
            numeric_value = float(value_text)
            if min_value <= numeric_value <= max_value:
                return int(rank_text), numeric_value
        return None, float(text)
    if re.match(r"^\d+$", text):
        for split_at in range(1, len(text)):
            rank_text = text[:split_at]
            value_text = text[split_at:]
            numeric_value = float(value_text)
            if min_value <= numeric_value <= max_value:
                return int(rank_text), numeric_value
    return None, parse_numeric(text)


def copied_conference_name(value: str) -> str:
    markdown_match = re.search(r"\[([^\]]+)\]\([^)]+\)", value)
    if markdown_match:
        return markdown_match.group(1).strip()
    return value.strip()


def parse_copied_line(line: str, season: str, level: str, source_file: str) -> dict[str, object] | None:
    cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
    if len(cells) < 9:
        return None
    conference = canonical_conference(copied_conference_name(cells[0]))
    if not conference or conference.lower() in {"team", "conference"}:
        return None

    rec, win_pct = split_record_win_pct(cells[1])
    rat_rank, rat = split_rank_value(cells[3], 0.0, 20.0)
    pwr_rank, pwr = split_rank_value(cells[4], -60.0, 80.0)
    off_rank, off = split_rank_value(cells[5], 40.0, 130.0)
    def_rank, defensive = split_rank_value(cells[6], -30.0, 40.0)
    sos_rank, sos = split_rank_value(cells[8], -60.0, 80.0)
    return {
        "season": season,
        "conference": conference,
        "level": level,
        "rec": rec,
        "win_pct": win_pct,
        "tms": parse_numeric(cells[2]),
        "rat_rank": rat_rank,
        "rat": rat,
        "pwr_rank": pwr_rank,
        "pwr": pwr,
        "off_rank": off_rank,
        "off": off,
        "def_rank": def_rank,
        "def": defensive,
        "hfa": parse_numeric(cells[7]),
        "sos_rank": sos_rank,
        "sos": sos,
        "source_file": source_file,
    }


def parse_copied_text_file(path: Path, season: str, level: str) -> list[dict[str, object]]:
    if not season:
        raise ValueError("--season is required for copied Massey text/markdown inputs")
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = []
    for line in text.splitlines():
        parsed = parse_copied_line(line, season, level, str(path))
        if parsed:
            rows.append(parsed)
    return rows


def rows_from_frame(
    frame: pd.DataFrame,
    *,
    season: str,
    level: str,
    source_file: str,
    source_url: str,
) -> list[dict[str, object]]:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    conf_column = select_column(list(frame.columns), CONFERENCE_COLUMNS)
    power_column = select_column(list(frame.columns), POWER_COLUMNS)
    if not conf_column or not power_column:
        return []

    rows = []
    for _index, row in frame.iterrows():
        conference = canonical_conference(row.get(conf_column, ""))
        if normalize(power_column) in {"pwr", "power", "conference power", "massey power"}:
            _rank, power = split_rank_value(str(row.get(power_column, "")), -80.0, 100.0)
        else:
            power = parse_numeric(row.get(power_column, ""))
        if not conference or power is None:
            continue
        row_season = normalize_season(
            row.get("season", row.get("Season", row.get("year", row.get("Year", "")))),
            fallback=season,
        )
        row_level = str(row.get("level", row.get("Level", level))).strip() or level
        rows.append(
            {
                "season": row_season,
                "conference": conference,
                "level": row_level,
                "power": power,
                "source_file": source_file,
                "source_url": source_url,
                "source_column": power_column,
            }
        )
    return rows


def parse_csv_text(
    text: str,
    *,
    season: str,
    level: str,
    source_file: str,
    source_url: str,
) -> list[dict[str, object]]:
    frame = pd.read_csv(io.StringIO(text))
    return rows_from_frame(frame, season=season, level=level, source_file=source_file, source_url=source_url)


def parse_html_text(
    text: str,
    *,
    season: str,
    level: str,
    source_file: str,
    source_url: str,
) -> list[dict[str, object]]:
    rows = []
    for frame in pd.read_html(io.StringIO(text)):
        rows.extend(
            rows_from_frame(
                frame,
                season=season,
                level=level,
                source_file=source_file,
                source_url=source_url,
            )
        )
    return rows


def parse_input_file(path: Path, season: str, level: str) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    source_file = str(path)
    if looks_blocked(text):
        return []
    if path.suffix.lower() in {".txt", ".md"}:
        copied_rows = parse_copied_text_file(path, season, level)
        return [
            {
                "season": row["season"],
                "conference": row["conference"],
                "level": row["level"],
                "power": row["pwr"],
                "source_file": row["source_file"],
                "source_url": "",
                "source_column": "pwr",
            }
            for row in copied_rows
            if row.get("pwr") is not None
        ]
    if path.suffix.lower() in {".csv", ".tsv"}:
        return parse_csv_text(text, season=season, level=level, source_file=source_file, source_url="")
    return parse_html_text(text, season=season, level=level, source_file=source_file, source_url="")


def parse_fetched_page(season: str, level: str) -> tuple[list[dict[str, object]], str]:
    url = default_url(season, level)
    cache_path = CACHE_DIR / f"{season}_{level}.html"
    text = fetch_url(url, cache_path)
    if looks_blocked(text):
        return [], url
    return parse_html_text(text, season=season, level=level, source_file=str(cache_path), source_url=url), url


def write_rows(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--needed", type=Path, default=NEEDED_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--missing-output", type=Path, default=MISSING_PATH)
    parser.add_argument(
        "--input",
        action="append",
        type=Path,
        default=[],
        help="Saved Massey HTML/CSV file. Repeatable. Use --season/--level if the file lacks those columns.",
    )
    parser.add_argument("--season", default="", help="Season for --input files, e.g. 2024-25.")
    parser.add_argument(
        "--level",
        choices=["AUTO", "D1", "D2"],
        default="AUTO",
        help="Level for --input files. AUTO matches rows against the needed conference-season list.",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Try live Massey URL templates for every needed season/level not supplied by --input.",
    )
    parser.add_argument(
        "--allow-empty-output",
        action="store_true",
        help="Overwrite the output file even when no Massey rows are parsed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    needed = read_needed(args.needed)
    needed_keys = {(row["season"], row["conference"], row["level"]) for row in needed}
    parsed_rows: list[dict[str, object]] = []
    fetch_failures: list[dict[str, str]] = []

    for input_path in args.input:
        if not args.season and input_path.suffix.lower() not in {".csv", ".tsv"}:
            raise ValueError("--season is required for saved HTML inputs")
        parsed_rows.extend(parse_input_file(input_path, args.season, args.level))

    if args.fetch:
        for season, level in sorted({(row["season"], row["level"]) for row in needed}):
            try:
                rows, url = parse_fetched_page(season, level)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                fetch_failures.append({"season": season, "level": level, "url": default_url(season, level), "reason": str(error)})
                continue
            if not rows:
                fetch_failures.append({"season": season, "level": level, "url": url, "reason": "blocked_or_no_parseable_table"})
                continue
            parsed_rows.extend(rows)

    needed_by_season_conference: dict[tuple[str, str], list[str]] = {}
    for season, conference, level in needed_keys:
        needed_by_season_conference.setdefault((season, conference), []).append(level)

    latest_by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in parsed_rows:
        season = normalize_season(row["season"])
        conference = canonical_conference(row["conference"])
        level = str(row.get("level", "")).strip()
        candidate_keys = [(season, conference, level)]
        if (season, conference) in needed_by_season_conference:
            candidate_keys.extend(
                (season, conference, needed_level)
                for needed_level in needed_by_season_conference[(season, conference)]
            )
        for key in candidate_keys:
            if key not in needed_keys:
                continue
            matched = row.copy()
            matched["season"] = key[0]
            matched["conference"] = key[1]
            matched["level"] = key[2]
            latest_by_key[key] = matched

    output_rows = [latest_by_key[key] for key in sorted(latest_by_key)]
    missing_rows = [
        {
            "season": season,
            "conference": conference,
            "level": level,
            "reason": "not_found_in_parsed_massey_data",
        }
        for season, conference, level in sorted(needed_keys - set(latest_by_key))
    ]
    missing_rows.extend(fetch_failures)

    output_columns = ["season", "conference", "level", "power", "source_file", "source_url", "source_column"]
    if output_rows or args.allow_empty_output or not args.output.exists():
        write_rows(args.output, output_rows, output_columns)
    else:
        print(f"Kept existing {args.output} because no Massey rows were parsed.")
    write_rows(args.missing_output, missing_rows, ["season", "conference", "level", "reason", "url"])

    print(f"Wrote {len(output_rows)} Massey conference power rows to {args.output}")
    print(f"Wrote {len(missing_rows)} missing rows to {args.missing_output}")
    if fetch_failures:
        print("Live Massey fetch was blocked or unparseable for at least one season/level.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
