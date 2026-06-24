#!/usr/bin/env python3
"""Create verified current-D2 stat overrides from manual rows or source URLs.

This script is intentionally small-batch. Put the players you care about in
data/current_d2_verification_input.csv, add source URLs or manual stat columns,
then run this script. It will write data/current_d2_verified_stats.csv, which
the dashboard builder uses automatically.
"""

from __future__ import annotations

import argparse
import html
import re
import ssl
import time
import urllib.error
import urllib.request
from io import StringIO
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path("data/current_d2_verification_input.csv")
DEFAULT_OUTPUT = Path("data/current_d2_verified_stats.csv")
DEFAULT_MISSING = Path("data/current_d2_verified_stats_missing.csv")
DEFAULT_CACHE_DIR = Path("data/cache/current_d2_verified_stats")

STAT_COLUMNS = [
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
    "TOPG",
    "SPG",
    "BPG",
]


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def cache_name(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")[:180] + ".html"


def fetch_url(url: str, cache_dir: Path, sleep: float, refresh: bool = False) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_name(url)
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8", errors="replace")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 current-d2-verify"})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=45, context=context) as response:
        text = response.read().decode("utf-8", errors="replace")
    cache_path.write_text(text, encoding="utf-8")
    if sleep:
        time.sleep(sleep)
    return text


def number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.startswith("."):
        text = f"0{text}"
    try:
        return float(text)
    except ValueError:
        return None


def split_made_attempted(value: object) -> tuple[float | None, float | None]:
    text = str(value or "").strip()
    if "-" not in text:
        return None, None
    left, right = text.split("-", 1)
    return number(left), number(right)


def flatten_columns(columns: object) -> list[str]:
    out: list[str] = []
    for column in columns:
        if isinstance(column, tuple):
            pieces = [str(piece) for piece in column if str(piece) and not str(piece).startswith("Unnamed")]
            out.append(" ".join(pieces).strip())
        else:
            out.append(str(column).strip())
    return out


def table_rows(html_text: str) -> list[pd.DataFrame]:
    try:
        tables = pd.read_html(StringIO(html_text))
    except (ImportError, ValueError):
        return []
    cleaned: list[pd.DataFrame] = []
    for table in tables:
        table = table.copy()
        table.columns = flatten_columns(table.columns)
        cleaned.append(table)
    return cleaned


def find_matching_row(tables: list[pd.DataFrame], player_name: str) -> tuple[pd.Series, pd.DataFrame] | None:
    target = normalize(player_name)
    pieces = target.split()
    if len(pieces) >= 2:
        last_first = normalize(f"{pieces[-1]} {' '.join(pieces[:-1])}")
    else:
        last_first = target
    for table in tables:
        for _, row in table.iterrows():
            row_text = normalize(" ".join(str(value) for value in row.tolist()))
            if target in row_text or last_first in row_text:
                return row, table
    return None


def get_by_alias(row: pd.Series, aliases: list[str]) -> object:
    def alias_key(value: object) -> str:
        text = str(value or "").lower().replace("%", " pct ")
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    normalized_columns = {alias_key(column): column for column in row.index}
    for alias in aliases:
        alias_norm = alias_key(alias)
        if alias_norm in normalized_columns:
            return row[normalized_columns[alias_norm]]
    for column_norm, column in normalized_columns.items():
        column_tokens = set(column_norm.split())
        for alias in aliases:
            alias_norm = alias_key(alias)
            if not alias_norm:
                continue
            # Short labels such as TO, FG, FT, GP should match full tokens only.
            # Otherwise TO incorrectly matches "Totals" or "Minutes Total".
            if len(alias_norm) <= 3:
                if alias_norm == "to":
                    if column_norm in {"to", "to to", "t o", "tov", "turnovers", "turnover"}:
                        return row[column]
                    continue
                if alias_norm in column_tokens:
                    return row[column]
            elif alias_norm in column_norm:
                return row[column]
    return None


def parse_realgm_row(row: pd.Series) -> dict[str, object]:
    out: dict[str, object] = {}
    out["GP"] = number(get_by_alias(row, ["GP"]))
    out["MPG"] = number(get_by_alias(row, ["MIN"]))
    out["PPG"] = number(get_by_alias(row, ["PTS"]))
    out["RPG"] = number(get_by_alias(row, ["REB"]))
    out["APG"] = number(get_by_alias(row, ["AST"]))
    out["SPG"] = number(get_by_alias(row, ["STL"]))
    out["BPG"] = number(get_by_alias(row, ["BLK"]))
    out["TOPG"] = number(get_by_alias(row, ["TOV", "TO"]))
    out["FG%"] = number(get_by_alias(row, ["FG%"]))
    out["3PT%"] = number(get_by_alias(row, ["3P%", "3PT%"]))
    out["FT%"] = number(get_by_alias(row, ["FT%"]))
    if out.get("GP") and out.get("MPG"):
        out["MIN"] = out["GP"] * out["MPG"]
    return out


def parse_school_row(row: pd.Series) -> dict[str, object]:
    out: dict[str, object] = {}
    normalized_index = {str(column).strip().lower(): column for column in row.index}

    def raw(column: str) -> object:
        return row[normalized_index[column]] if column in normalized_index else None

    # Presto lineup tables often split a player's stat line across separate
    # category rows: shooting has fg/g, 3pt/g, ft/g, ppg; ball control has
    # ast/g, to/g, etc. Parse those exact labels first so generic aliases do
    # not treat made-attempted fields or pct.1/pct.2 columns incorrectly.
    gp_value = number(raw("gp"))
    if gp_value is not None:
        out["GP"] = gp_value
    gs_value = number(raw("gs"))
    if gs_value is not None:
        out["GS"] = gs_value
    mpg_value = number(raw("min/g")) or number(raw("mpg"))
    if mpg_value is not None:
        out["MPG"] = mpg_value

    for source, made_col, attempted_col in [
        ("fg", "FGM", "FGA"),
        ("fg/g", "FGM", "FGA"),
        ("3pt", "3PTM", "3PTA"),
        ("3pt/g", "3PTM", "3PTA"),
        ("ft", "FTM", "FTA"),
        ("ft/g", "FTM", "FTA"),
    ]:
        made, attempted = split_made_attempted(raw(source))
        if made is not None and attempted is not None:
            if source.endswith("/g") and gp_value:
                made *= gp_value
                attempted *= gp_value
            out[made_col] = made
            out[attempted_col] = attempted

    pct_value = number(raw("pct"))
    if pct_value is not None and "FGM" in out:
        out["FG%"] = pct_value
    pct_1_value = number(raw("pct.1"))
    if pct_1_value is not None and "3PTM" in out:
        out["3PT%"] = pct_1_value
    pct_2_value = number(raw("pct.2"))
    if pct_2_value is not None and "FTM" in out:
        out["FT%"] = pct_2_value

    ppg_value = number(raw("ppg"))
    if ppg_value is not None:
        out["PPG"] = ppg_value
        if gp_value:
            out["PTS"] = ppg_value * gp_value
    pts_value = number(raw("pts"))
    if pts_value is not None:
        out["PTS"] = pts_value
        if gp_value:
            out["PPG"] = pts_value / gp_value

    for source, total_col, per_col in [
        ("off", "ORB", None),
        ("off/g", "ORB", None),
        ("def", "DRB", None),
        ("def/g", "DRB", None),
        ("reb", "TOT RB", "RPG"),
        ("reb/g", "TOT RB", "RPG"),
        ("pf", "PF", None),
        ("pf/g", "PF", None),
        ("ast", "AST", "APG"),
        ("ast/g", "AST", "APG"),
        ("to", "TO", "TOPG"),
        ("to/g", "TO", "TOPG"),
        ("stl", "STL", "SPG"),
        ("stl/g", "STL", "SPG"),
        ("blk", "BLK", "BPG"),
        ("blk/g", "BLK", "BPG"),
    ]:
        value = number(raw(source))
        if value is None:
            continue
        if source.endswith("/g"):
            if per_col:
                out[per_col] = value
            if gp_value:
                out[total_col] = value * gp_value
        else:
            out[total_col] = value
            if per_col and gp_value:
                out[per_col] = value / gp_value

    min_value = number(raw("min"))
    if min_value is not None:
        out["MIN"] = min_value
        if gp_value:
            out["MPG"] = min_value / gp_value

    aliases = {
        "GP": ["GP", "G", "Games"],
        "GS": ["GS"],
        "MIN": ["MIN", "Minutes MIN", "Minutes TOT"],
        "MPG": ["MPG", "AVG", "Minutes AVG"],
        "FGM": ["FG FGM", "Totals FG", "FGM", "FG"],
        "FGA": ["FG FGA", "Totals FGA", "FGA"],
        "FG%": ["FG FG%", "FG PCT", "Totals PCT", "FG%"],
        "3PTM": ["3PT 3PT", "3-Point FG", "3PT", "3PM", "3FG"],
        "3PTA": ["3PT 3PTA", "3-Point FGA", "3PA", "3PTA"],
        "3PT%": ["3PT 3PT%", "3-Point PCT", "3P%", "3PT%"],
        "FTM": ["FT FTM", "Free-Throws FT", "FTM", "FT"],
        "FTA": ["FT FTA", "Free-Throws FTA", "FTA"],
        "FT%": ["FT FT%", "Free-Throws PCT", "FT%"],
        "ORB": ["Rebounds OFF", "OFF", "OREB", "Offensive"],
        "DRB": ["Rebounds DEF", "DEF", "DREB", "Defensive"],
        "TOT RB": ["Rebounds TOT", "TOT", "REB"],
        "RPG": ["Rebounds AVG", "RPG"],
        "PF": ["PF"],
        "AST": ["AST"],
        "APG": ["AST/G"],
        "TO": ["T/O", "TO", "TOV"],
        "BLK": ["BLK"],
        "STL": ["STL"],
        "PTS": ["Scoring PTS", "PTS"],
        "PPG": ["Scoring AVG", "Points AVG", "PPG"],
    }
    for column, column_aliases in aliases.items():
        if column in out:
            continue
        value = get_by_alias(row, column_aliases)
        parsed = number(value)
        if parsed is not None:
            out[column] = parsed

    # Some school tables include made-attempted columns such as "107-207".
    for source, made_col, attempted_col in [
        ("2P", "2PM", "2PA"),
        ("3P", "3PTM", "3PTA"),
        ("FT", "FTM", "FTA"),
    ]:
        value = get_by_alias(row, [source])
        made, attempted = split_made_attempted(value)
        if made is not None and attempted is not None:
            if made_col not in out:
                out[made_col] = made
            if attempted_col not in out:
                out[attempted_col] = attempted

    if "GP" in out:
        for total_col, per_col in [
            ("PTS", "PPG"),
            ("TOT RB", "RPG"),
            ("AST", "APG"),
            ("STL", "SPG"),
            ("BLK", "BPG"),
            ("TO", "TOPG"),
        ]:
            if per_col not in out and total_col in out and out["GP"]:
                out[per_col] = out[total_col] / out["GP"]
    if "MIN" not in out and out.get("GP") and out.get("MPG"):
        out["MIN"] = out["GP"] * out["MPG"]
    if "MPG" not in out and out.get("GP") and out.get("MIN"):
        out["MPG"] = out["MIN"] / out["GP"]
    return out


def derive_extra_stats(row: dict[str, object]) -> dict[str, object]:
    gp = number(row.get("GP"))
    mpg = number(row.get("MPG"))
    minutes = number(row.get("MIN"))
    if mpg is None and gp and minutes:
        mpg = minutes / gp
        row["MPG"] = mpg
    if minutes is None and gp and mpg:
        minutes = gp * mpg
        row["MIN"] = minutes
    for per_game_col, per_40_col in [
        ("PPG", "pts_per_40"),
        ("RPG", "reb_per_40"),
        ("APG", "ast_per_40"),
        ("SPG", "stl_per_40"),
        ("BPG", "blk_per_40"),
        ("TOPG", "tov_per_40"),
    ]:
        value = number(row.get(per_game_col))
        if value is not None and mpg:
            row[per_40_col] = value * 40 / mpg
    return row


def manual_stats_from_input(row: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for column in STAT_COLUMNS:
        if column in row and number(row[column]) is not None:
            out[column] = number(row[column])
    return derive_extra_stats(out)


def parse_url_stats(player_name: str, url: str, cache_dir: Path, sleep: float, refresh: bool) -> dict[str, object]:
    html_text = fetch_url(url, cache_dir, sleep=sleep, refresh=refresh)
    tables = table_rows(html_text)
    match = find_matching_row(tables, player_name)
    if not match:
        raise ValueError("no matching player row found in parsed HTML tables")
    row, _table = match
    if "realgm.com" in url:
        return derive_extra_stats(parse_realgm_row(row))
    parsed = parse_school_row(row)
    if not parsed:
        parsed = parse_realgm_row(row)
    if not parsed:
        raise ValueError("matching row found, but no stat columns could be parsed")
    return derive_extra_stats(parsed)


def write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "player_name": "Kolby Watson",
            "team": "Emmanuel GA",
            "conference": "Conference Carolinas",
            "season": "2025-26",
            "source_url": "",
            "source_type": "",
            "notes": "",
        },
        {
            "player_name": "Kolby Horace",
            "team": "Delta State",
            "conference": "Gulf South",
            "season": "2025-26",
            "source_url": "",
            "source_type": "",
            "notes": "",
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--sleep", type=float, default=4.0)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--write-template", action="store_true")
    args = parser.parse_args()

    if args.write_template or not args.input.exists():
        write_template(args.input)
        print(f"Wrote template to {args.input}")
        if args.write_template:
            return 0

    inputs = pd.read_csv(args.input).fillna("")
    verified_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []
    for input_row in inputs.to_dict("records"):
        player_name = input_row.get("player_name") or input_row.get("Player Name")
        team = input_row.get("team") or input_row.get("Team")
        conference = input_row.get("conference") or input_row.get("Conference")
        source_url = str(input_row.get("source_url", "")).strip()
        try:
            stats = manual_stats_from_input(input_row)
            source_method = "manual_columns"
            if not stats and source_url:
                stats = parse_url_stats(str(player_name), source_url, args.cache_dir, args.sleep, args.refresh_cache)
                source_method = "parsed_url"
            if not stats:
                raise ValueError("no manual stats and no parseable source_url")
            verified_rows.append(
                {
                    "Player Name": player_name,
                    "Team": team,
                    "Conference": conference,
                    "source_url": source_url,
                    "source_method": source_method,
                    **stats,
                }
            )
            print(f"OK {player_name} ({source_method})")
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            missing_rows.append(
                {
                    "player_name": player_name,
                    "team": team,
                    "conference": conference,
                    "source_url": source_url,
                    "reason": str(error),
                }
            )
            print(f"MISS {player_name}: {error}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(verified_rows).to_csv(args.output, index=False)
    pd.DataFrame(missing_rows).to_csv(args.missing_output, index=False)
    print(f"Wrote {len(verified_rows)} verified rows to {args.output}")
    print(f"Wrote {len(missing_rows)} missing rows to {args.missing_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
