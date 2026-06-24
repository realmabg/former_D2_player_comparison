#!/usr/bin/env python3
"""Build first-D1-season outcome rows from Sports Reference player pages."""

from __future__ import annotations

import csv
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote_plus

PHASE1_PATH = Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/phase1_transfers.csv")
SPORTS_REFERENCE_CACHE = Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/cache/sports_reference")
OUTPUT_PATH = Path("data/phase1_d1_outcomes.csv")
MISSING_PATH = Path("data/phase1_d1_outcomes_missing.csv")

SPORTS_REFERENCE_SEARCH = "https://www.sports-reference.com/cbb/search/search.fcgi?search={query}"
USER_AGENT = "Mozilla/5.0 phase1-d1-outcomes"

OUTPUT_COLUMNS = [
    "player_name",
    "d2_school",
    "d1_school",
    "first_d1_season",
    "sr_season",
    "sr_team",
    "sr_conf",
    "class",
    "position",
    "games",
    "games_started",
    "mpg",
    "minutes",
    "minutes_share",
    "ppg",
    "rpg",
    "apg",
    "spg",
    "bpg",
    "topg",
    "fg_pct",
    "fg3_pct",
    "ft_pct",
    "efg_pct",
    "ts_pct",
    "three_rate",
    "ft_rate",
    "per",
    "ts_pct_advanced",
    "usg_pct",
    "ows",
    "dws",
    "ws",
    "ws_per_40",
    "bpm",
    "source_url",
]

MISSING_COLUMNS = [
    "player_name",
    "d1_school",
    "first_d1_season",
    "sports_reference_url",
    "reason",
]

SPORTS_REFERENCE_SCHOOL_FALLBACKS = {
    "Max Jones": {
        "url": "https://www.sports-reference.com/cbb/schools/cal-state-fullerton/men/2023.html",
        "player_names": ["Max Jones"],
    },
    "Joshua Ward": {
        "url": "https://www.sports-reference.com/cbb/schools/cal-state-fullerton/men/2026.html",
        "player_names": ["Joshua Ward", "Josh Ward"],
    },
    "Rob Diaz III": {
        "url": "https://www.sports-reference.com/cbb/schools/long-beach-state/men/2026.html",
        "player_names": ["Rob Diaz III", "Rob Diaz"],
    },
    "De'Undrae Perteete, Jr.": {
        "url": "https://www.sports-reference.com/cbb/schools/california-riverside/men/2026.html",
        "player_names": ["De'Undrae Perteete Jr.", "De'Undrae Perteete"],
    },
    "Emanuel Prospere II": {
        "url": "https://www.sports-reference.com/cbb/schools/california-san-diego/men/2026.html",
        "player_names": ["Emanuel Prospere II"],
    },
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(value).lower()).strip()


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(fragment).strip()


def parse_stat_cells(row_html: str) -> dict[str, str]:
    cells: dict[str, str] = {}
    pattern = re.compile(
        r"<(?:th|td)\b(?P<attrs>[^>]*)data-stat=\"(?P<stat>[^\"]+)\"(?P<attrs2>[^>]*)>(?P<body>.*?)</(?:th|td)>",
        re.S,
    )
    for match in pattern.finditer(row_html):
        attrs = f"{match.group('attrs')} {match.group('attrs2')}"
        csk_match = re.search(r"csk=\"([^\"]*)\"", attrs)
        text = strip_tags(match.group("body"))
        if match.group("stat") == "team_name_abbr" and csk_match:
            text = html.unescape(csk_match.group(1)).strip()
        cells[match.group("stat")] = text
    return cells


def parse_table_rows(page_html: str, table_id: str) -> list[dict[str, str]]:
    table_match = re.search(rf"<table[^>]+id=\"{re.escape(table_id)}\".*?</table>", page_html, re.S)
    if not table_match:
        return []
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", table_match.group(0), re.S)
    if not tbody_match:
        return []
    rows: list[dict[str, str]] = []
    for row_html in re.findall(r"<tr\b[^>]*>.*?</tr>", tbody_match.group(1), re.S):
        cells = parse_stat_cells(row_html)
        if cells.get("year_id") and cells.get("team_name_abbr"):
            rows.append(cells)
        elif cells.get("name_display"):
            rows.append(cells)
    return rows


def cache_name(player_slug: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", player_slug)
    return f"{safe}.html"


def canonical_player_url(page_html: str) -> str:
    match = re.search(r'<link rel="canonical" href="([^"]+/cbb/players/[^"]+)"', page_html)
    return html.unescape(match.group(1)).strip() if match else ""


def fetch_page(player_name: str, player_slug: str) -> tuple[str, str]:
    SPORTS_REFERENCE_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = SPORTS_REFERENCE_CACHE / cache_name(player_slug)
    meta_path = SPORTS_REFERENCE_CACHE / f"{cache_path.stem}.json"
    if cache_path.exists():
        source_url = ""
        if meta_path.exists():
            source_url = json.loads(meta_path.read_text(encoding="utf-8")).get("url", "")
        return cache_path.read_text(encoding="utf-8"), source_url

    url = SPORTS_REFERENCE_SEARCH.format(query=quote_plus(player_name))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        page_html = response.read().decode("utf-8", errors="replace")
        final_url = response.geturl()
    source_url = canonical_player_url(page_html) or final_url
    cache_path.write_text(page_html, encoding="utf-8")
    meta_path.write_text(json.dumps({"url": source_url, "final_url": final_url}, indent=2), encoding="utf-8")
    time.sleep(3.5)
    return page_html, source_url


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def numeric(value: str) -> float:
    if not value:
        return 0.0
    if value.startswith("."):
        value = f"0{value}"
    if value.startswith("-."):
        value = value.replace("-.", "-0.", 1)
    return float(value)


def choose_row(rows: list[dict[str, str]], season: str, school: str) -> dict[str, str] | None:
    target_school = normalize(school)
    for row in rows:
        if row.get("year_id") == season and normalize(row.get("team_name_abbr", "")) == target_school:
            return row
    return None


def choose_school_player_row(
    rows: list[dict[str, str]],
    player_names: list[str],
    transfer: dict[str, str],
) -> dict[str, str] | None:
    targets = {normalize(name) for name in player_names}
    for row in rows:
        if normalize(row.get("name_display", "")) in targets:
            row = row.copy()
            row["year_id"] = transfer["first_d1_season"]
            row["team_name_abbr"] = transfer["d1_school"]
            row["conf_abbr"] = transfer["d1_conference"]
            return row
    return None


def merge_row(transfer: dict[str, str], per_game: dict[str, str], advanced: dict[str, str], source_url: str) -> dict[str, object]:
    games = numeric(per_game.get("games", ""))
    mpg = numeric(per_game.get("mp_per_g", ""))
    fga = numeric(per_game.get("fga_per_g", ""))
    fg3a = numeric(per_game.get("fg3a_per_g", ""))
    fta = numeric(per_game.get("fta_per_g", ""))
    pts = numeric(per_game.get("pts_per_g", ""))
    denominator = 2 * (fga + 0.44 * fta)

    return {
        "player_name": transfer["player_name"],
        "d2_school": transfer["d2_school"],
        "d1_school": transfer["d1_school"],
        "first_d1_season": transfer["first_d1_season"],
        "sr_season": per_game.get("year_id", ""),
        "sr_team": per_game.get("team_name_abbr", ""),
        "sr_conf": per_game.get("conf_abbr", ""),
        "class": per_game.get("class", ""),
        "position": per_game.get("pos", ""),
        "games": int(games),
        "games_started": int(numeric(per_game.get("games_started", ""))),
        "mpg": mpg,
        "minutes": games * mpg,
        "minutes_share": mpg / 40 if mpg else 0,
        "ppg": pts,
        "rpg": numeric(per_game.get("trb_per_g", "")),
        "apg": numeric(per_game.get("ast_per_g", "")),
        "spg": numeric(per_game.get("stl_per_g", "")),
        "bpg": numeric(per_game.get("blk_per_g", "")),
        "topg": numeric(per_game.get("tov_per_g", "")),
        "fg_pct": numeric(per_game.get("fg_pct", "")),
        "fg3_pct": numeric(per_game.get("fg3_pct", "")),
        "ft_pct": numeric(per_game.get("ft_pct", "")),
        "efg_pct": numeric(per_game.get("efg_pct", "")),
        "ts_pct": pts / denominator if denominator else 0,
        "three_rate": fg3a / fga if fga else 0,
        "ft_rate": fta / fga if fga else 0,
        "per": numeric(advanced.get("per", "")),
        "ts_pct_advanced": numeric(advanced.get("ts_pct", "")),
        "usg_pct": numeric(advanced.get("usg_pct", "")),
        "ows": numeric(advanced.get("ows", "")),
        "dws": numeric(advanced.get("dws", "")),
        "ws": numeric(advanced.get("ws", "")),
        "ws_per_40": numeric(advanced.get("ws_per_40", "")),
        "bpm": numeric(advanced.get("bpm", "")),
        "source_url": source_url,
    }




def main() -> int:
    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []

    with PHASE1_PATH.open(newline="") as file:
        transfers = [
            row for row in csv.DictReader(file) if row["model_training_eligible"] == "TRUE"
        ]

    for transfer in transfers:
        try:
            page_html, source_url = fetch_page(transfer["player_name"], transfer["player_slug"])
            per_game_rows = parse_table_rows(page_html, "players_per_game")
            advanced_rows = parse_table_rows(page_html, "players_advanced")
            per_game = choose_row(per_game_rows, transfer["first_d1_season"], transfer["d1_school"])
            advanced = choose_row(advanced_rows, transfer["first_d1_season"], transfer["d1_school"]) or {}
            if not per_game:
                fallback = SPORTS_REFERENCE_SCHOOL_FALLBACKS.get(transfer["player_name"])
                if not fallback:
                    raise ValueError("Sports Reference first-D1-season row not found")
                school_html = fetch_url(str(fallback["url"]))
                school_per_game_rows = parse_table_rows(school_html, "players_per_game")
                school_advanced_rows = parse_table_rows(school_html, "players_advanced")
                per_game = choose_school_player_row(
                    school_per_game_rows,
                    list(fallback["player_names"]),
                    transfer,
                )
                advanced = choose_school_player_row(
                    school_advanced_rows,
                    list(fallback["player_names"]),
                    transfer,
                ) or {}
                if not per_game:
                    raise ValueError("Sports Reference school-season player row not found")
                rows.append(merge_row(transfer, per_game, advanced, str(fallback["url"])))
                print(f"OK {transfer['player_name']} {transfer['first_d1_season']} [SR school page]")
                continue
            rows.append(merge_row(transfer, per_game, advanced, source_url))
            print(f"OK {transfer['player_name']} {transfer['first_d1_season']}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            print(f"MISS {transfer['player_name']}: {error}")
            missing.append(
                {
                    "player_name": transfer["player_name"],
                    "d1_school": transfer["d1_school"],
                    "first_d1_season": transfer["first_d1_season"],
                    "sports_reference_url": transfer["sports_reference_url"],
                    "reason": str(error),
                }
            )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with OUTPUT_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with MISSING_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MISSING_COLUMNS)
        writer.writeheader()
        writer.writerows(missing)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} missing rows to {MISSING_PATH}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
