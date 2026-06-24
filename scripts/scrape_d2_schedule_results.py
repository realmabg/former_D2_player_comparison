#!/usr/bin/env python3
"""Scrape D2 schedule results for teams with known athletics domains."""

from __future__ import annotations

import csv
import html
import re
import ssl
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

TEAM_DIRECTORY_PATH = Path("data/d2_team_directory.csv")
OUTPUT_PATH = Path("data/d2_schedule_results.csv")
MISSING_PATH = Path("data/d2_schedule_results_missing.csv")
CACHE_DIR = Path("data/cache/schedules")

SEASONS = ["2023-24", "2024-25", "2025-26"]
USER_AGENT = "Mozilla/5.0 d2-schedule-results"

OUTPUT_COLUMNS = [
    "team_id",
    "team_name",
    "conference",
    "season",
    "date",
    "opponent",
    "site",
    "is_conference_game",
    "is_exhibition",
    "result",
    "team_score",
    "opponent_score",
    "margin",
    "source_url",
]

MISSING_COLUMNS = [
    "team_id",
    "team_name",
    "conference",
    "season",
    "source_url",
    "reason",
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = html.unescape(data).strip()
        if text:
            self.parts.append(text)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def cache_name(url: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", url)
    return f"{safe}.txt"


def fetch_text(url: str) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / cache_name(url)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        parser = TextExtractor()
        parser.feed(response.read().decode("utf-8", errors="replace"))
    text = normalize_space(" ".join(parser.parts))
    cache_path.write_text(text, encoding="utf-8")
    time.sleep(0.25)
    return text


def clean_opponent(value: str) -> str:
    value = re.sub(r"\s+\*", "", value)
    value = re.sub(r"\s+(Exhibition|Championship)$", "", value, flags=re.IGNORECASE)
    return normalize_space(value)


def parse_schedule_text(
    text: str,
    team: dict[str, str],
    season: str,
    source_url: str,
) -> list[dict[str, object]]:
    body_match = re.search(r"Scheduled Games (?P<body>.*?)(?:Footer|Related Videos|Social Media|Sponsors|$)", text)
    body = body_match.group("body") if body_match else text

    pattern = re.compile(
        r"(?P<chunk>.*?)(?:Hide/Show Additional Information For\s+"
        r"(?P<opponent>.+?)\s+-\s+"
        r"(?P<date>[A-Z][a-z]+\s+\d{1,2},\s+\d{4}))",
        re.IGNORECASE,
    )

    rows: list[dict[str, object]] = []
    for match in pattern.finditer(body):
        chunk = normalize_space(match.group("chunk"))
        result_match = re.search(
            r"\b(?P<result>[WL]),\s+"
            r"(?P<team_score>\d{1,3})-"
            r"(?P<opponent_score>\d{1,3})",
            chunk,
        )
        if not result_match:
            continue

        opponent = clean_opponent(match.group("opponent"))
        lower_chunk = chunk.lower()
        site = "neutral"
        if re.search(r"\bat\s+" + re.escape(opponent), chunk, flags=re.IGNORECASE):
            site = "away"
        elif re.search(r"\bvs\s+" + re.escape(opponent), chunk, flags=re.IGNORECASE):
            site = "home"
        elif " at " in lower_chunk and " vs " not in lower_chunk:
            site = "away"
        elif " vs " in lower_chunk:
            site = "home"

        team_score = int(result_match.group("team_score"))
        opponent_score = int(result_match.group("opponent_score"))
        rows.append(
            {
                "team_id": team["team_id"],
                "team_name": team["team_name"],
                "conference": team["conference"],
                "season": season,
                "date": match.group("date"),
                "opponent": opponent,
                "site": site,
                "is_conference_game": "TRUE" if "*" in chunk else "FALSE",
                "is_exhibition": "TRUE" if "exhibition" in lower_chunk else "FALSE",
                "result": result_match.group("result").upper(),
                "team_score": team_score,
                "opponent_score": opponent_score,
                "margin": team_score - opponent_score,
                "source_url": source_url,
            }
        )
    return rows


def parse_tampa_schedule_text(
    text: str,
    team: dict[str, str],
    season: str,
    source_url: str,
) -> list[dict[str, object]]:
    month_names = (
        "November",
        "December",
        "January",
        "February",
        "March",
        "April",
    )
    month_pattern = re.compile(r"\b(" + "|".join(month_names) + r")\s+\d+\s+events\b")
    rows: list[dict[str, object]] = []
    season_start = int(season[:4])

    matches = list(month_pattern.finditer(text))
    for index, month_match in enumerate(matches):
        month = month_match.group(1)
        section_start = month_match.end()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[section_start:section_end]
        year = season_start if month in {"November", "December"} else season_start + 1

        pattern = re.compile(
            r"\b(?P<site>vs|at)\s+"
            r"(?P<opponent>.+?)\s+"
            r"(?P<conference>\*\s+Conference\s+)?"
            r"(?:~\s+Region\s+)?"
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.\s+"
            r"(?P<day>\d{1,2})\s+Final(?:\s+-\s+\S+)?\s+"
            r".*?\b(?P<result>[WL])\s+,\s+"
            r"(?P<team_score>\d{1,3})-"
            r"(?P<opponent_score>\d{1,3})\s+"
            r".*?(?:Box Score|Recap)",
            re.IGNORECASE,
        )

        for game in pattern.finditer(section):
            opponent = clean_opponent(game.group("opponent"))
            team_score = int(game.group("team_score"))
            opponent_score = int(game.group("opponent_score"))
            rows.append(
                {
                    "team_id": team["team_id"],
                    "team_name": team["team_name"],
                    "conference": team["conference"],
                    "season": season,
                    "date": f"{month} {int(game.group('day'))}, {year}",
                    "opponent": opponent,
                    "site": "away" if game.group("site").lower() == "at" else "home",
                    "is_conference_game": "TRUE" if game.group("conference") else "FALSE",
                    "is_exhibition": "FALSE",
                    "result": game.group("result").upper(),
                    "team_score": team_score,
                    "opponent_score": opponent_score,
                    "margin": team_score - opponent_score,
                    "source_url": source_url,
                }
            )
    return rows


def main() -> int:
    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []

    with TEAM_DIRECTORY_PATH.open(newline="") as file:
        teams = [row for row in csv.DictReader(file) if row["has_schedule_domain"] == "TRUE"]

    for team in teams:
        for season in SEASONS:
            source_url = team[f"schedule_url_{season}"]
            try:
                text = fetch_text(source_url)
                if "tampaspartans.com" in source_url:
                    parsed = parse_tampa_schedule_text(text, team, season, source_url)
                else:
                    parsed = parse_schedule_text(text, team, season, source_url)
                if not parsed:
                    raise ValueError("No completed schedule results parsed")
                rows.extend(parsed)
                print(f"OK {team['team_name']} {season}: {len(parsed)} games")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                print(f"MISS {team['team_name']} {season}: {error}")
                missing.append(
                    {
                        "team_id": team["team_id"],
                        "team_name": team["team_name"],
                        "conference": team["conference"],
                        "season": season,
                        "source_url": source_url,
                        "reason": str(error),
                    }
                )

    with OUTPUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with MISSING_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MISSING_COLUMNS)
        writer.writeheader()
        writer.writerows(missing)

    print(f"Wrote {len(rows)} games to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} misses to {MISSING_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
