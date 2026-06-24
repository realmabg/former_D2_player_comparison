#!/usr/bin/env python3
"""Scrape D2-side stat rows for phase1 D2->D1 transfers from school pages."""

from __future__ import annotations

import csv
import html
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

PHASE1_PATH = Path("/Users/adriankong/Desktop/D2_to_D1_pathway/data/phase1_transfers.csv")
OUTPUT_PATH = Path("data/phase1_school_stats.csv")
MISSING_PATH = Path("data/phase1_school_stats_missing.csv")

SCHOOL_DOMAINS = {
    "Azusa Pacific": "athletics.apu.edu",
    "Biola": "athletics.biola.edu",
    "Cal Poly Humboldt": "humboldtathletics.com",
    "Cal State East Bay": "eastbaypioneers.com",
    "Cal State San Bernardino": "csusbathletics.com",
    "Chico State": "chicowildcats.com",
    "Colorado Mesa": "cmumavericks.com",
    "Concordia Irvine": "cuigoldeneagles.com",
    "Hawaii–Hilo": "hiloathletics.com",
    "Lynn": "lynnfightingknights.com",
    "McKendree": "mckbearcats.com",
    "Menlo": "menloathletics.com",
    "Missouri–St. Louis": "umsltritons.com",
    "Palm Beach Atlantic": "pbasailfish.com",
    "Quincy": "quhawks.com",
    "San Francisco State": "sfstategators.com",
    "Southeastern Oklahoma State": "gosoutheastern.com",
    "Southern Nazarene": "snuathletics.com",
    "Spring Hill": "shcbadgers.com",
    "Tampa": "tampaspartans.com",
    "West Texas A&M": "gobuffsgo.com",
    "Westmont": "athletics.westmont.edu",
}

OUTPUT_COLUMNS = [
    "Player Name",
    "Team",
    "Conference",
    "Position",
    "Height",
    "Year",
    "Season",
    "first_d1_season",
    "d1_school",
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

MISSING_COLUMNS = [
    "player_name",
    "d2_school",
    "d2_conference",
    "d1_school",
    "first_d1_season",
    "d2_season",
    "source_url",
    "reason",
]

PLAYER_OVERRIDES = {
    "Guzmán Vasilić": {
        "skip": True,
        "reason": "Redshirt/did not play; no D2 stat row to scrape",
    },
    "Max Jones": {
        "season": "2021-22",
        "source_url": "https://www.tampaspartans.com/sports/mbkb/2021-22/players/maxjonesdgr9?view=career",
        "parser": "tampa_player_page",
    },
    "Jailen Daniel-Dalton": {
        "season": "2023-24",
        "source_url": "https://sfstategators.com/sports/mens-basketball/stats/2023-24",
    },
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = html.unescape(data).strip()
        if text:
            self.parts.append(text)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def lastname_first(name: str) -> str:
    suffixes = {"jr", "jr.", "iii", "ii", "iv"}
    parts = [part for part in re.split(r"\s+", name.strip()) if normalize(part) not in suffixes]
    if len(parts) < 2:
        return name
    return f"{parts[-1].rstrip(',')}, {' '.join(parts[:-1])}"


def d2_season(first_d1_season: str, transfer_year: str) -> str:
    start = int(first_d1_season[:4]) if first_d1_season else int(transfer_year)
    return f"{start - 1}-{str(start)[-2:]}"


def stats_url(school: str, season: str) -> str:
    domain = SCHOOL_DOMAINS[school]
    return f"https://{domain}/sports/mens-basketball/stats/{season}"


def page_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        parser = TextExtractor()
        parser.feed(response.read().decode("utf-8", errors="replace"))
    return " ".join(parser.parts)


def number(value: str) -> float:
    if value.startswith("."):
        value = f"0{value}"
    return float(value.replace(",", ""))


def candidate_row_names(player_name: str) -> list[str]:
    clean = player_name.strip()
    suffixes = {"Jr.", "Jr", "II", "III", "IV"}
    parts = [part for part in re.split(r"\s+", clean) if part]
    suffix = parts[-1] if parts and parts[-1].replace(",", "") in suffixes else ""
    no_suffix = " ".join(parts[:-1]) if suffix else clean
    base = lastname_first(clean)
    base_no_suffix = lastname_first(no_suffix)
    variants = {base, base_no_suffix}
    if suffix and len(parts) >= 2:
        last_name = parts[-2].rstrip(",")
        clean_suffix = suffix.replace(",", "")
        variants.add(f"{last_name} {clean_suffix}, {' '.join(parts[:-2])}")
        variants.add(f"{last_name}, {clean_suffix} {' '.join(parts[:-2])}".strip())
        variants.add(f"{last_name}, {' '.join(parts[:-2])}")
    variants.add(base.replace("-", " "))
    variants.add(base.replace("'", ""))
    variants.add(base.replace(".", ""))
    variants.add(base.replace(" ,", " "))
    variants.add(base.replace(", ", " , "))
    variants.add(base.replace(" Jr", ""))
    variants.add(base.replace(" Jr.", ""))
    variants.add(unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode())
    variants.add(unicodedata.normalize("NFKD", base_no_suffix).encode("ascii", "ignore").decode())
    return [variant for variant in variants if variant.strip()]


def find_player_tokens(text: str, player_name: str) -> tuple[str, list[str]]:
    for row_name in candidate_row_names(player_name):
        pattern = re.compile(
            rf"\b\d{{1,2}}\s+{re.escape(row_name)}\s+\d{{1,2}}\s+{re.escape(row_name)}\s+"
            r"(?P<stats>.+?)(?:View Bio|Total|Opponents)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return row_name, match.group("stats").split()

    compact_text = normalize(text)
    for row_name in candidate_row_names(player_name):
        if normalize(row_name) in compact_text:
            raise ValueError(f"Found name text but not parseable stat row: {row_name}")
    raise ValueError("Could not find player row")


def field_value(text: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}\s+(?P<overall>\S+)\s+\S+", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Could not find Tampa player-page field: {label}")
    return match.group("overall")


def split_made_attempted(value: str) -> tuple[str, str]:
    made, attempted = value.split("-", 1)
    return made, attempted


def find_tampa_player_tokens(text: str) -> tuple[str, list[str]]:
    start = text.find("Player Stats Overall Conference")
    end = text.find("Recent Results", start)
    if start == -1 or end == -1:
        raise ValueError("Could not find Tampa player-page stats table")
    stats_text = text[start:end]

    fgm, fga = split_made_attempted(field_value(stats_text, "FG"))
    three_m, three_a = split_made_attempted(field_value(stats_text, "3PT"))
    ftm, fta = split_made_attempted(field_value(stats_text, "FT"))
    return "Max Jones player page", [
        field_value(stats_text, "Games"),
        field_value(stats_text, "Games started"),
        field_value(stats_text, "Minutes"),
        field_value(stats_text, "Minutes per game"),
        fgm,
        fga,
        str(number(field_value(stats_text, "FG Pct")) / 100),
        three_m,
        three_a,
        str(number(field_value(stats_text, "3PT Pct")) / 100),
        ftm,
        fta,
        str(number(field_value(stats_text, "FT Pct")) / 100),
        field_value(stats_text, "Points"),
        field_value(stats_text, "Points per game"),
        field_value(stats_text, "Off rebounds"),
        field_value(stats_text, "Def rebounds"),
        field_value(stats_text, "Total rebounds"),
        field_value(stats_text, "Rebounds per game"),
        field_value(stats_text, "Personal fouls"),
        field_value(stats_text, "Assists"),
        field_value(stats_text, "Turnovers"),
        field_value(stats_text, "Steals"),
        field_value(stats_text, "Blocks"),
    ]


def class_to_year(value: str) -> str:
    mapping = {
        "FR": "Fr.",
        "SO": "So.",
        "JR": "Jr.",
        "SR": "Sr.",
        "COLLEGE_SOPHOMORE": "So.",
        "COLLEGE_JUNIOR": "Jr.",
        "COLLEGE_SENIOR": "Sr.",
        "INELIGIBLE": "Sr.",
    }
    return mapping.get(value, value)


def position_short(value: str) -> str:
    lower = value.lower()
    if "point" in lower:
        return "G"
    if "shooting" in lower:
        return "G"
    if "small" in lower:
        return "W"
    if "power" in lower:
        return "F"
    if "center" in lower:
        return "C"
    return value


def build_row(
    transfer: dict[str, str],
    source_url: str,
    tokens: list[str],
    season: str,
) -> dict[str, object]:
    if len(tokens) < 24:
        raise ValueError(f"Unexpected row shape: {tokens}")

    gp = int(tokens[0])
    minutes = int(number(tokens[2]))
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

    return {
        "Player Name": transfer["player_name"],
        "Team": transfer["d2_school"].replace("–", "-"),
        "Conference": transfer["d2_conference"],
        "Position": position_short(transfer["position"]),
        "Height": transfer["height"],
        "Year": class_to_year(transfer["class"]),
        "Season": season,
        "first_d1_season": transfer["first_d1_season"],
        "d1_school": transfer["d1_school"],
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
        "source_url": source_url,
    }


def main() -> int:
    with PHASE1_PATH.open(newline="") as file:
        transfers = [
            row for row in csv.DictReader(file) if row["model_training_eligible"] == "TRUE"
        ]

    rows: list[dict[str, object]] = []
    missing: list[dict[str, str]] = []
    cache: dict[str, str] = {}

    for transfer in transfers:
        override = PLAYER_OVERRIDES.get(transfer["player_name"], {})
        season = str(
            override.get("season", d2_season(transfer["first_d1_season"], transfer["transfer_year"]))
        )
        source_url = ""
        try:
            if override.get("skip"):
                raise ValueError(str(override["reason"]))

            source_url = str(override.get("source_url", stats_url(transfer["d2_school"], season)))
            if source_url not in cache:
                cache[source_url] = page_text(source_url)
                time.sleep(0.25)
            if override.get("parser") == "tampa_player_page":
                row_name, tokens = find_tampa_player_tokens(cache[source_url])
            else:
                row_name, tokens = find_player_tokens(cache[source_url], transfer["player_name"])
            rows.append(build_row(transfer, source_url, tokens, season))
            print(f"OK {transfer['player_name']} [{row_name}]")
        except (KeyError, urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"MISS {transfer['player_name']}: {error}")
            missing.append(
                {
                    "player_name": transfer["player_name"],
                    "d2_school": transfer["d2_school"],
                    "d2_conference": transfer["d2_conference"],
                    "d1_school": transfer["d1_school"],
                    "first_d1_season": transfer["first_d1_season"],
                    "d2_season": season,
                    "source_url": source_url,
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
