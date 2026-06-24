#!/usr/bin/env python3
"""Proof of concept for pulling D2 stat rows from school cumulative-stat pages.

This intentionally starts with a small, known-good set of Sidearm pages. The
next version should replace PLAYERS with rows from phase1_transfers.csv plus a
school-domain resolver.
"""

from __future__ import annotations

import csv
import html
import re
import ssl
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


PLAYERS = [
    {
        "player_name": "Aniwaniwa Tait-Jones",
        "team": "Hawaii Hilo",
        "conference": "PacWest",
        "position": "F",
        "height": 78,
        "year": "Jr.",
        "season": "2022-23",
        "url": "https://hiloathletics.com/sports/mens-basketball/stats/2022-23",
        "row_name": "Tait-Jones, Aniwaniwa",
    },
    {
        "player_name": "Hayden Gray",
        "team": "Azusa Pacific",
        "conference": "PacWest",
        "position": "G",
        "height": 76,
        "year": "So.",
        "season": "2022-23",
        "url": "https://athletics.apu.edu/sports/mens-basketball/stats/2022-23",
        "row_name": "Gray , Hayden",
    },
    {
        "player_name": "Tyler McGhie",
        "team": "Southern Nazarene",
        "conference": "GAC",
        "position": "G/W",
        "height": 77,
        "year": "So.",
        "season": "2022-23",
        "url": "https://snuathletics.com/sports/mens-basketball/stats/2022-23",
        "row_name": "McGhie, Tyler",
    },
    {
        "player_name": "Nordin Kapic",
        "team": "Lynn",
        "conference": "Sunshine State",
        "position": "F",
        "height": 80,
        "year": "Fr.",
        "season": "2023-24",
        "url": "https://lynnfightingknights.com/sports/mens-basketball/stats/2023-24",
        "row_name": "Kapic, Nordin",
    },
]


OUTPUT_COLUMNS = [
    "Player Name",
    "Team",
    "Conference",
    "Position",
    "Height",
    "Year",
    "Season",
    "GP",
    "MIN",
    "MPG",
    "FGM",
    "FGA",
    "FG%",
    "3PTM",
    "3PTA",
    "3PT%",
    "FTM",
    "FTA",
    "FT%",
    "PTS",
    "PPG",
    "ORB",
    "DRB",
    "TOT RB",
    "RPG",
    "PF",
    "AST",
    "TO",
    "STL",
    "BLK",
    "APG",
    "SPG",
    "DRBPG",
    "ORBPG",
    "BPG",
    "TOPG",
    "eFG",
    "three_share",
    "AST_TOV",
    "FTR",
    "TS_pct",
    "usg",
    "pts_per_40",
    "reb_per_40",
    "ast_per_40",
    "stl_per_40",
    "blk_per_40",
    "tov_per_40",
    "source_url",
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = html.unescape(data).strip()
        if text:
            self.parts.append(text)


def page_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 school-stats-poc"},
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        parser = TextExtractor()
        parser.feed(response.read().decode("utf-8", errors="replace"))
    return " ".join(parser.parts)


def number(value: str) -> float:
    if value.startswith("."):
        value = f"0{value}"
    return float(value)


def find_player_tokens(text: str, row_name: str) -> list[str]:
    pattern = re.compile(
        rf"\b\d{{1,2}}\s+{re.escape(row_name)}\s+\d{{1,2}}\s+{re.escape(row_name)}\s+"
        r"(?P<stats>.+?)(?:View Bio|Total|Opponents)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Could not find stats row for {row_name}")
    return match.group("stats").split()


def player_row(player: dict[str, object]) -> dict[str, object]:
    tokens = find_player_tokens(page_text(str(player["url"])), str(player["row_name"]))
    if len(tokens) < 24:
        raise ValueError(f"Unexpected row shape for {player['player_name']}: {tokens}")

    gp = int(tokens[0])
    minutes = int(tokens[2])
    fgm = int(tokens[4])
    fga = int(tokens[5])
    fg_pct = number(tokens[6])
    three_m = int(tokens[7])
    three_a = int(tokens[8])
    three_pct = number(tokens[9])
    ftm = int(tokens[10])
    fta = int(tokens[11])
    ft_pct = number(tokens[12])
    pts = int(tokens[13])
    orb = int(tokens[15])
    drb = int(tokens[16])
    reb = int(tokens[17])
    pf = int(tokens[19])
    ast = int(tokens[20])
    tov = int(tokens[21])
    stl = int(tokens[22])
    blk = int(tokens[23])

    possessions_proxy = max(1, fga + 0.44 * fta + tov)
    row = {
        "Player Name": player["player_name"],
        "Team": player["team"],
        "Conference": player["conference"],
        "Position": player["position"],
        "Height": player["height"],
        "Year": player["year"],
        "Season": player["season"],
        "GP": gp,
        "MIN": minutes,
        "MPG": minutes / gp,
        "FGM": fgm,
        "FGA": fga,
        "FG%": fg_pct,
        "3PTM": three_m,
        "3PTA": three_a,
        "3PT%": three_pct,
        "FTM": ftm,
        "FTA": fta,
        "FT%": ft_pct,
        "PTS": pts,
        "PPG": pts / gp,
        "ORB": orb,
        "DRB": drb,
        "TOT RB": reb,
        "RPG": reb / gp,
        "PF": pf,
        "AST": ast,
        "TO": tov,
        "STL": stl,
        "BLK": blk,
        "APG": ast / gp,
        "SPG": stl / gp,
        "DRBPG": drb / gp,
        "ORBPG": orb / gp,
        "BPG": blk / gp,
        "TOPG": tov / gp,
        "eFG": (fgm + 0.5 * three_m) / fga if fga else 0,
        "three_share": three_a / fga if fga else 0,
        "AST_TOV": ast / tov if tov else ast,
        "FTR": fta / fga if fga else 0,
        "TS_pct": pts / (2 * (fga + 0.44 * fta)) if fga or fta else 0,
        "usg": possessions_proxy / minutes if minutes else 0,
        "pts_per_40": pts * 40 / minutes if minutes else 0,
        "reb_per_40": reb * 40 / minutes if minutes else 0,
        "ast_per_40": ast * 40 / minutes if minutes else 0,
        "stl_per_40": stl * 40 / minutes if minutes else 0,
        "blk_per_40": blk * 40 / minutes if minutes else 0,
        "tov_per_40": tov * 40 / minutes if minutes else 0,
        "source_url": player["url"],
    }
    return row


def main() -> int:
    rows = [player_row(player) for player in PLAYERS]
    output_path = Path("data/school_stats_poc.csv")
    output_path.parent.mkdir(exist_ok=True)
    with output_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
