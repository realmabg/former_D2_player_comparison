#!/usr/bin/env python3
"""Scrape first-Big-West outcome rows from official school stat pages."""

from __future__ import annotations

import csv
import html
import io
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

import pandas as pd

from scrape_big_west_transfer_outcomes import OUTPUT_COLUMNS
from scrape_phase1_school_stats import find_player_tokens, number, normalize

TRANSFERS_PATH = Path("data/big_west_inbound_transfers.csv")
SPORTS_REFERENCE_OUTCOMES_PATH = Path("data/big_west_transfer_d1_outcomes.csv")
OUTPUT_PATH = Path("data/big_west_transfer_school_outcomes.csv")
MISSING_PATH = Path("data/big_west_transfer_school_outcomes_missing.csv")

SCHOOL_DOMAINS = {
    "cal-poly": "gopoly.com",
    "cal-state-bakersfield": "gorunners.com",
    "cal-state-fullerton": "fullertontitans.com",
    "cal-state-northridge": "gomatadors.com",
    "hawaii": "hawaiiathletics.com",
    "long-beach-state": "longbeachstate.com",
    "uc-davis": "ucdavisaggies.com",
    "uc-irvine": "ucirvinesports.com",
    "uc-riverside": "gohighlanders.com",
    "uc-san-diego": "ucsdtritons.com",
    "uc-santa-barbara": "ucsbgauchos.com",
}

MISSING_COLUMNS = [
    "player_name",
    "player_slug",
    "destination_school",
    "destination_school_slug",
    "first_big_west_season",
    "pathway_type",
    "source_url",
    "reason",
]


def season_end_year(season: str) -> int:
    return int(season.split("-", 1)[0]) + 1


def stats_url(destination_school_slug: str, season: str) -> str:
    return f"https://{SCHOOL_DOMAINS[destination_school_slug]}/sports/mens-basketball/stats/{season}"


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(fragment).strip()


def page_text(page_html: str) -> str:
    return " ".join(part for part in re.sub(r"<[^>]+>", " ", page_html).split() if part)


def numeric(value: str) -> float:
    if value.startswith("."):
        value = f"0{value}"
    return float(value.replace(",", ""))


def name_keys(name: str) -> set[str]:
    keys = {normalize(name)}
    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
        keys.add(normalize(f"{first} {last}"))
    else:
        parts = [part for part in re.split(r"\s+", name.strip()) if part]
        if len(parts) >= 2:
            keys.add(normalize(f"{parts[-1]}, {' '.join(parts[:-1])}"))
    return {key for key in keys if key}


def fuzzy_tokens(rows: dict[str, list[str]], player_name: str) -> tuple[str, list[str]] | None:
    target_parts = normalize(player_name).split()
    target_parts = [part for part in target_parts if part not in {"jr", "sr", "ii", "iii", "iv"}]
    if len(target_parts) < 2:
        return None
    target_first = target_parts[0]
    target_last = target_parts[-1]
    matches = []
    seen = set()
    for key, tokens in rows.items():
        parts = key.split()
        if target_last not in parts:
            continue
        if target_first in parts or any(
            part.startswith(target_first) or target_first.startswith(part) for part in parts
        ):
            token_key = tuple(tokens)
            if token_key not in seen:
                seen.add(token_key)
                matches.append((key, tokens))
    if not matches:
        return None
    return max(matches, key=lambda item: (numeric(item[1][0]), numeric(item[1][2])))


def add_player_row(rows: dict[str, list[str]], name: str, tokens: list[str]) -> None:
    for key in name_keys(name):
        rows.setdefault(key, tokens)


def cell_values(row_html: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = defaultdict(list)
    for match in re.finditer(
        r"<td\b(?P<attrs>[^>]*)>(?P<body>.*?)</td>",
        row_html,
        re.S | re.I,
    ):
        attrs = match.group("attrs")
        label_match = re.search(r'data-label="([^"]+)"', attrs)
        if not label_match:
            continue
        label = html.unescape(label_match.group(1)).strip().upper()
        values[label].append(strip_tags(match.group("body")))
    return values


def player_name_from_row(row_html: str) -> str:
    for pattern in [
        r'<a\b[^>]*data-player-id="[^"]+"[^>]*>(.*?)</a>',
        r'title="([^"]+) - Roster Bio"',
    ]:
        match = re.search(pattern, row_html, re.S | re.I)
        if match:
            return strip_tags(match.group(1))
    return ""


def tokens_from_cells(cells: dict[str, list[str]]) -> list[str] | None:
    def first(label: str) -> str:
        return cells.get(label, [""])[0]

    def nth(label: str, index: int) -> str:
        values = cells.get(label, [])
        return values[index] if len(values) > index else ""

    gp = first("GP")
    gs = first("GS")
    minutes = first("MIN") or first("MINUTES")
    mpg = first("MIN/G") or nth("AVG", 0)
    fgm = first("FGM") or first("FG")
    fga = first("FGA")
    fg_pct = first("FG%") or first("PCT")
    three_m = first("3PT") or first("3FG")
    three_a = first("3PTA") or first("3FGA")
    three_pct = first("3PT%") or nth("PCT", 1)
    ftm = first("FT") or first("FTM")
    fta = first("FTA")
    ft_pct = first("FT%") or nth("PCT", 2)
    pts = first("PTS")
    ppg = nth("AVG", 1)
    orb = first("OFF REB") or first("OFF")
    drb = first("DEF REB") or first("DEF")
    reb = first("REB") or first("TOT")
    rpg = first("REB/G") or nth("AVG", 2)
    pf = first("PF")
    ast = first("AST")
    tov = first("TO") or first("T/O")
    stl = first("STL")
    blk = first("BLK")
    tokens = [
        gp,
        gs,
        minutes,
        mpg,
        fgm,
        fga,
        fg_pct,
        three_m,
        three_a,
        three_pct,
        ftm,
        fta,
        ft_pct,
        pts,
        ppg,
        orb,
        drb,
        reb,
        rpg,
        pf,
        ast,
        tov,
        stl,
        blk,
    ]
    return tokens if all(value != "" for value in [gp, gs, minutes, fgm, fga, pts, reb, ast, tov, stl, blk]) else None


def html_player_rows(page_html_value: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for row_html in re.findall(r"<tr\b[^>]*>.*?</tr>", page_html_value, re.S | re.I):
        if "data-label" not in row_html:
            continue
        name = player_name_from_row(row_html)
        if not name:
            continue
        tokens = tokens_from_cells(cell_values(row_html))
        if tokens:
            add_player_row(rows, name, tokens)
    return rows


def nuxt_payload(page_html_value: str) -> list[object] | None:
    match = re.search(
        r'<script\b[^>]*data-nuxt-data="nuxt-app"[^>]*>(.*?)</script>',
        page_html_value,
        re.S | re.I,
    )
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, list) else None


def resolved_nuxt_refs(payload: list[object]) -> list[object]:
    wrappers = {"Reactive", "ShallowReactive", "Ref", "ComputedRef", "Set"}
    cache: dict[int, object] = {}

    def resolve(value: object) -> object:
        if isinstance(value, int):
            if value < 0 or value >= len(payload):
                return value
            if value in cache:
                return cache[value]
            cache[value] = None
            cache[value] = resolve(payload[value])
            return cache[value]
        if isinstance(value, list):
            if value and isinstance(value[0], str) and value[0] in wrappers:
                if value[0] == "Set":
                    return [resolve(item) for item in value[1:]]
                return resolve(value[1]) if len(value) > 1 else None
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            return {key: resolve(item) for key, item in value.items()}
        return value

    return [resolve(index) for index in range(len(payload))]


def nuxt_tokens(player: dict[str, object]) -> list[str] | None:
    def field(name: str, default: str = "") -> str:
        value = player.get(name, default)
        return "" if value is None else str(value).strip()

    games = field("gamesPlayed")
    points = field("points")
    rebounds = field("rebounds")
    assists = field("assists")
    turnovers = field("turnovers")
    steals = field("steals")
    blocks = field("blocks")
    minutes = field("minutesPlayed")
    fgm = field("fieldGoals")
    fga = field("fieldGoalsAttempted")
    if not all([games, points, rebounds, assists, turnovers, steals, blocks, minutes, fgm, fga]):
        return None
    return [
        games,
        field("gamesStarted", "0") or "0",
        minutes,
        field("minutesPerGame"),
        fgm,
        fga,
        field("fieldGoalsPercentage"),
        field("threePointFieldGoals"),
        field("threePointFieldGoalsAttempted"),
        field("threePointFieldGoalsPercentage"),
        field("freeThrows"),
        field("freeThrowsAttempted"),
        field("freeThrowsPercentage"),
        points,
        field("pointsPerGame"),
        field("reboundsOffensive"),
        field("reboundsDefensive"),
        rebounds,
        field("reboundsPerGame"),
        field("personalFouls"),
        assists,
        turnovers,
        steals,
        blocks,
    ]


def nuxt_player_rows(page_html_value: str) -> dict[str, list[str]]:
    payload = nuxt_payload(page_html_value)
    if not payload:
        return {}

    rows: dict[str, list[str]] = {}
    for value in resolved_nuxt_refs(payload):
        if not isinstance(value, dict) or "statsSeason" not in value:
            continue
        stats_season = value.get("statsSeason")
        if not isinstance(stats_season, dict):
            continue
        cumulative_stats = stats_season.get("cumulativeStats")
        if not isinstance(cumulative_stats, dict):
            continue
        for season_stats in cumulative_stats.values():
            if not isinstance(season_stats, dict):
                continue
            overall = season_stats.get("overallIndividualStats")
            if not isinstance(overall, dict):
                continue
            individual_stats = overall.get("individualStats")
            if not isinstance(individual_stats, list):
                continue
            for player in individual_stats:
                if not isinstance(player, dict):
                    continue
                name = str(player.get("playerName", "")).strip()
                if not name or normalize(name) in {"total", "opponents"}:
                    continue
                tokens = nuxt_tokens(player)
                if tokens:
                    add_player_row(rows, name, tokens)
    return rows


def flattened_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [
        " ".join(str(part) for part in column if str(part) != "nan").strip()
        if isinstance(column, tuple)
        else str(column)
        for column in frame.columns
    ]
    return frame


def column_value(row: pd.Series, *needles: str) -> str:
    for column, value in row.items():
        raw_column = str(column).lower()
        column_key = normalize(str(column))
        column_parts = set(column_key.split())
        matched = True
        for needle in needles:
            if needle == "%":
                if "%" not in raw_column and "pct" not in column_parts:
                    matched = False
                    break
            elif normalize(needle) not in column_parts:
                matched = False
                break
        if matched:
            if pd.isna(value):
                return ""
            return str(value).strip()
    return ""


def pandas_player_rows(page_html_value: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    try:
        tables = pd.read_html(io.StringIO(page_html_value))
    except ValueError:
        return rows

    for table in tables:
        frame = flattened_columns(table)
        if not any("player" in normalize(str(column)) for column in frame.columns):
            continue
        if not any("gp" in normalize(str(column)) for column in frame.columns):
            continue
        for _index, row in frame.iterrows():
            name = ""
            for column, value in row.items():
                column_key = normalize(str(column))
                if "player name" in column_key or column_key == "player player":
                    name = str(value).strip()
                    break
            if not name or normalize(name) in {"total", "opponents"}:
                continue
            tokens = [
                column_value(row, "gp"),
                column_value(row, "gs"),
                column_value(row, "minutes", "min")
                or column_value(row, "minutes", "tot")
                or column_value(row, "min"),
                column_value(row, "minutes", "avg"),
                column_value(row, "fg", "fgm"),
                column_value(row, "fg", "fga"),
                column_value(row, "fg", "%"),
                column_value(row, "3pt", "3pt"),
                column_value(row, "3pt", "3pta"),
                column_value(row, "3pt", "%"),
                column_value(row, "ft", "ftm"),
                column_value(row, "ft", "fta"),
                column_value(row, "ft", "%"),
                column_value(row, "scoring", "pts"),
                column_value(row, "scoring", "avg"),
                column_value(row, "rebounds", "off"),
                column_value(row, "rebounds", "def"),
                column_value(row, "rebounds", "tot"),
                column_value(row, "rebounds", "avg"),
                column_value(row, "pf"),
                column_value(row, "ast"),
                column_value(row, "to"),
                column_value(row, "stl"),
                column_value(row, "blk"),
            ]
            required = [tokens[index] for index in [0, 1, 2, 4, 5, 13, 17, 20, 21, 22, 23]]
            if all(value != "" for value in required):
                add_player_row(rows, name, tokens)
    return rows


def outcome_row(transfer: dict[str, str], source_url: str, tokens: list[str]) -> dict[str, object]:
    if len(tokens) < 24:
        raise ValueError(f"Unexpected row shape: {tokens}")

    games = int(numeric(tokens[0]))
    games_started = int(numeric(tokens[1]))
    minutes = numeric(tokens[2])
    mpg = numeric(tokens[3]) if tokens[3] else minutes / games
    fgm = numeric(tokens[4])
    fga = numeric(tokens[5])
    fg3m = numeric(tokens[7])
    fg3a = numeric(tokens[8])
    ftm = numeric(tokens[10])
    fta = numeric(tokens[11])
    points = numeric(tokens[13])
    rebounds = numeric(tokens[17])
    assists = numeric(tokens[20])
    turnovers = numeric(tokens[21])
    steals = numeric(tokens[22])
    blocks = numeric(tokens[23])
    denominator = 2 * (fga + 0.44 * fta)

    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "source_school": transfer["source_school"],
        "source_school_slug": transfer["source_school_slug"],
        "source_conference": transfer["source_conference"],
        "source_level": transfer["source_level"],
        "destination_school": transfer["destination_school"],
        "destination_school_slug": transfer["destination_school_slug"],
        "first_big_west_season": transfer["first_big_west_season"],
        "pathway_type": transfer["pathway_type"],
        "sr_season": transfer["first_big_west_season"],
        "sr_team": transfer["destination_school"],
        "sr_conf": "Big West",
        "class": "",
        "position": "",
        "games": games,
        "games_started": games_started,
        "mpg": mpg,
        "minutes": minutes,
        "minutes_share": mpg / 40 if mpg else 0,
        "ppg": points / games if games else 0,
        "rpg": rebounds / games if games else 0,
        "apg": assists / games if games else 0,
        "spg": steals / games if games else 0,
        "bpg": blocks / games if games else 0,
        "topg": turnovers / games if games else 0,
        "fg_pct": numeric(tokens[6]),
        "fg3_pct": numeric(tokens[9]),
        "ft_pct": numeric(tokens[12]),
        "efg_pct": (fgm + 0.5 * fg3m) / fga if fga else 0,
        "ts_pct": points / denominator if denominator else 0,
        "three_rate": fg3a / fga if fga else 0,
        "ft_rate": fta / fga if fga else 0,
        "per": "",
        "ts_pct_advanced": "",
        "usg_pct": "",
        "ows": "",
        "dws": "",
        "ws": "",
        "ws_per_40": "",
        "bpm": "",
        "source_url": source_url,
    }


def missing_row(transfer: dict[str, str], source_url: str, reason: str) -> dict[str, str]:
    return {
        "player_name": transfer["player_name"],
        "player_slug": transfer["player_slug"],
        "destination_school": transfer["destination_school"],
        "destination_school_slug": transfer["destination_school_slug"],
        "first_big_west_season": transfer["first_big_west_season"],
        "pathway_type": transfer["pathway_type"],
        "source_url": source_url,
        "reason": reason,
    }


def main() -> int:
    transfers = list(csv.DictReader(TRANSFERS_PATH.open(newline="", encoding="utf-8")))
    sr_keys = set()
    if SPORTS_REFERENCE_OUTCOMES_PATH.exists():
        with SPORTS_REFERENCE_OUTCOMES_PATH.open(newline="", encoding="utf-8") as file:
            sr_keys = {
                (row["player_slug"], row["destination_school_slug"], row["first_big_west_season"])
                for row in csv.DictReader(file)
            }

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    future_rows: list[dict[str, str]] = []
    for transfer in transfers:
        key = (transfer["player_slug"], transfer["destination_school_slug"], transfer["first_big_west_season"])
        if key in sr_keys:
            continue
        if season_end_year(transfer["first_big_west_season"]) > 2026:
            future_rows.append(transfer)
            continue
        grouped[(transfer["destination_school_slug"], transfer["first_big_west_season"])].append(transfer)

    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = [
        missing_row(transfer, "", "season_not_started") for transfer in future_rows
    ]
    cache: dict[str, str] = {}

    for (destination_slug, season), group in sorted(grouped.items()):
        source_url = ""
        try:
            source_url = stats_url(destination_slug, season)
            if source_url not in cache:
                cache[source_url] = fetch_html(source_url)
                time.sleep(0.25)
            player_rows = html_player_rows(cache[source_url])
            player_rows.update(nuxt_player_rows(cache[source_url]))
            player_rows.update(pandas_player_rows(cache[source_url]))
        except (KeyError, urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"MISS {destination_slug} {season}: {error}")
            for transfer in group:
                missing.append(missing_row(transfer, source_url, str(error)))
            continue

        for transfer in group:
            try:
                row_name = transfer["player_name"]
                tokens = None
                for key in name_keys(transfer["player_name"]):
                    tokens = player_rows.get(key)
                    if tokens:
                        break
                if not tokens:
                    fuzzy = fuzzy_tokens(player_rows, transfer["player_name"])
                    if fuzzy:
                        row_name, tokens = fuzzy
                if not tokens:
                    row_name, tokens = find_player_tokens(page_text(cache[source_url]), transfer["player_name"])
                rows.append(outcome_row(transfer, source_url, tokens))
                print(f"OK {transfer['player_name']} {season} [{row_name}]")
            except ValueError as error:
                print(f"MISS {transfer['player_name']} {season}: {error}")
                missing.append(missing_row(transfer, source_url, str(error)))

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with MISSING_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MISSING_COLUMNS)
        writer.writeheader()
        writer.writerows(missing)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Wrote {len(missing)} missing rows to {MISSING_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
