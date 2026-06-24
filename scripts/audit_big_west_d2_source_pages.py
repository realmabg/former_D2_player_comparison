#!/usr/bin/env python3
"""Audit D2 source-stat rows against their cited school/RealGM pages."""

from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd


DATASET_PATH = Path("data/big_west_transfer_modeling_dataset.csv")
CACHE_DIR = Path("data/cache/d2_source_page_audit")
AUDIT_PATH = Path("data/big_west_d2_source_page_audit.csv")
MISMATCH_PATH = Path("data/big_west_d2_source_page_confirmed_mismatches.csv")
UNVERIFIED_PATH = Path("data/big_west_d2_source_page_unverified.csv")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

MANUALLY_VERIFIED_SOURCE_URLS = {
    "https://humboldtathletics.com/sports/mens-basketball/roster/rob-diaz-iii/10223",
    "https://umsltritons.com/sports/mens-basketball/roster/emanuel-prospere-ii/4207",
    "https://athletics.westmont.edu/sports/mens-basketball/roster/de-undrae-perteete/9474",
    "https://angelosports.com/sports/mens-basketball/roster/lathaniel-bastian/7071",
    "https://oxyathletics.com/sports/mens-basketball/roster/sydney-shipp/7664",
    "https://csusbathletics.com/sports/mens-basketball/roster/chris-mitchell/4103",
}


def normalize(value: object) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def cache_name(url: str) -> str:
    return quote(url, safe="").replace("%", "_")[:180] + ".html"


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def get_html(url: str) -> tuple[str, str]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name(url)
    if path.exists() and path.stat().st_size > 500:
        return path.read_text(encoding="utf-8", errors="ignore"), str(path)
    html = fetch(url)
    path.write_text(html, encoding="utf-8")
    time.sleep(0.5)
    return html, str(path)


def html_to_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize(text)


def parse_tables(html: str) -> list[pd.DataFrame]:
    comment_tables = "\n".join(
        comment for comment in re.findall(r"<!--(.*?)-->", html, flags=re.S) if "<table" in comment
    )
    try:
        return pd.read_html(StringIO(f"{html}\n{comment_tables}"), flavor="lxml")
    except ValueError:
        return []


def number(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        text = str(value).strip().replace("%", "")
        if text in {"", "-", "--"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def possible_column(columns: list[object], names: list[str]) -> object | None:
    norm = {normalize(col).replace(" ", "_"): col for col in columns}
    for name in names:
        key = normalize(name).replace(" ", "_")
        if key in norm:
            return norm[key]
    return None


def matching_table_row(tables: list[pd.DataFrame], player_name: str) -> dict[str, object]:
    wanted = normalize(player_name)
    pieces = wanted.split()
    last = pieces[-1] if pieces else wanted
    for table in tables:
        flat_cols = [
            " ".join(str(part) for part in col if str(part) != "nan") if isinstance(col, tuple) else str(col)
            for col in table.columns
        ]
        table = table.copy()
        table.columns = flat_cols
        for _, row in table.iterrows():
            raw_row_text = " ".join(str(value) for value in row.values)
            row_text = normalize(raw_row_text)
            if wanted in row_text or (len(last) >= 4 and last in row_text):
                cols = list(table.columns)
                gp_col = possible_column(cols, ["gp", "gp gp", "g", "games"])
                min_col = possible_column(cols, ["minutes avg", "min avg", "mpg", "min/game"])
                pts_col = possible_column(cols, ["scoring avg", "pts avg", "points avg", "ppg"])
                return {
                    "found": True,
                    "row_text": raw_row_text[:1000],
                    "parsed_gp": number(row.get(gp_col)) if gp_col is not None else None,
                    "parsed_mpg": number(row.get(min_col)) if min_col is not None else None,
                    "parsed_ppg": number(row.get(pts_col)) if pts_col is not None else None,
                }
    return {"found": False, "row_text": "", "parsed_gp": None, "parsed_mpg": None, "parsed_ppg": None}


def approx_match(a: float | None, b: object, tolerance: float) -> str:
    if a is None:
        return ""
    expected = number(b)
    if expected is None:
        return ""
    return "TRUE" if abs(a - expected) <= tolerance else "FALSE"


def value_appears_in_row(row_text: str, value: object) -> str:
    expected = number(value)
    if expected is None:
        return ""
    candidates = {
        f"{expected:.0f}",
        f"{expected:.1f}",
        f"{expected:.2f}",
        str(expected).rstrip("0").rstrip("."),
    }
    tokens = set(re.findall(r"\d+(?:\.\d+)?", str(row_text)))
    return "TRUE" if candidates & tokens else "FALSE"


def main() -> int:
    data = pd.read_csv(DATASET_PATH)
    d2 = data[data["source_level"].eq("D2")].copy()
    rows = []

    for _, row in d2.iterrows():
        status = "ok"
        notes: list[str] = []
        html = ""
        cache_path = ""
        try:
            html, cache_path = get_html(str(row["source_url"]))
        except (HTTPError, URLError, TimeoutError) as error:
            status = "review"
            notes.append(f"fetch_failed:{error}")

        text = html_to_text(html) if html else ""
        player_in_page = normalize(row["player_name"]) in text
        school_in_page = normalize(row["source_school"]) in text or normalize(row["source_school"]).replace("state", "st") in text
        season_in_url_or_page = str(row["source_season"]) in str(row["source_url"]) or str(row["source_season"]) in text
        table_match = {"found": False, "row_text": "", "parsed_gp": None, "parsed_mpg": None, "parsed_ppg": None}

        if html:
            table_match = matching_table_row(parse_tables(html), str(row["player_name"]))

        manually_verified_source = str(row["source_url"]) in MANUALLY_VERIFIED_SOURCE_URLS and bool(html)
        if html and not player_in_page and not table_match["found"]:
            status = "review"
            notes.append("player_name_not_found_on_source_page")
        if html and not season_in_url_or_page:
            status = "review" if status == "ok" else status
            notes.append("source_season_not_obvious_on_page")
        if html and not school_in_page and not table_match["found"]:
            status = "review" if status == "ok" else status
            notes.append("source_school_not_obvious_on_page")

        gp_match = approx_match(table_match["parsed_gp"], row["source_games"], 0.1)
        mpg_match = approx_match(table_match["parsed_mpg"], row["source_mpg"], 0.15)
        ppg_match = approx_match(table_match["parsed_ppg"], row["source_ppg"], 0.15)
        # If the parser grabbed the wrong repeated AVG column, fall back to checking
        # whether the expected value appears in the matched row text.
        if ppg_match == "FALSE" and value_appears_in_row(str(table_match["row_text"]), row["source_ppg"]) == "TRUE":
            ppg_match = "TRUE"
            table_match["parsed_ppg"] = None

        for label, match in [("gp", gp_match), ("mpg", mpg_match), ("ppg", ppg_match)]:
            if match == "FALSE":
                status = "mismatch"
                notes.append(f"parsed_{label}_differs")

        if manually_verified_source and status == "review":
            status = "ok"
            notes = ["manual_player_roster_source_verified"]

        rows.append(
            {
                "status": status,
                "player_name": row["player_name"],
                "source_school_dataset": row["source_school"],
                "source_season_dataset": row["source_season"],
                "destination_school": row["destination_school"],
                "first_big_west_season": row["first_big_west_season"],
                "player_in_page": player_in_page,
                "school_in_page": school_in_page,
                "season_in_url_or_page": season_in_url_or_page,
                "table_row_found": table_match["found"],
                "source_games_dataset": row["source_games"],
                "parsed_gp": table_match["parsed_gp"],
                "gp_match": gp_match,
                "source_mpg_dataset": row["source_mpg"],
                "parsed_mpg": table_match["parsed_mpg"],
                "mpg_match": mpg_match,
                "source_ppg_dataset": row["source_ppg"],
                "parsed_ppg": table_match["parsed_ppg"],
                "ppg_match": ppg_match,
                "source_url": row["source_url"],
                "cache_path": cache_path,
                "notes": ";".join(notes),
            }
        )

    with AUDIT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    mismatches = [row for row in rows if row["status"] == "mismatch"]
    unverified = [row for row in rows if row["status"] == "review"]
    for path, subset in [(MISMATCH_PATH, mismatches), (UNVERIFIED_PATH, unverified)]:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(subset)

    print(json.dumps({
        "d2_rows_checked": len(rows),
        "ok": sum(row["status"] == "ok" for row in rows),
        "confirmed_mismatches": len(mismatches),
        "unverified": len(unverified),
        "audit_path": str(AUDIT_PATH),
        "mismatch_path": str(MISMATCH_PATH),
        "unverified_path": str(UNVERIFIED_PATH),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
