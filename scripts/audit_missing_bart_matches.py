#!/usr/bin/env python3
"""Find local BartTorvik candidates for rows missing PORPAG/BPM outcomes."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


MISSING_PATH = Path("data/modeling/training/current_missing_target_fields.csv")
BART_DIR = Path("Bart data")

BART_COLUMNS = [
    "player_name",
    "team",
    "conf",
    "GP",
    "Min_per",
    "ORtg",
    "usg",
    "eFG",
    "TS_per",
    "ORB_per",
    "DRB_per",
    "AST_per",
    "TO_per",
    "FTM",
    "FTA",
    "FT_per",
    "twoPM",
    "twoPA",
    "twoP_per",
    "TPM",
    "TPA",
    "TP_per",
    "blk_per",
    "stl_per",
    "ftr",
    "yr",
    "ht",
    "num",
    "porpag",
    "adjoe",
    "pfr",
    "year",
    "pid",
    "type",
    "Rec Rank",
    "ast_tov",
    "rimmade",
    "rim_attempts",
    "midmade",
    "mid_attempts",
    "rim_pct",
    "mid_pct",
    "dunksmade",
    "dunks_attempts",
    "dunk_pct",
    "pick",
    "drtg",
    "adrtg",
    "dporpag",
    "stops",
    "bpm",
    "obpm",
    "dbpm",
    "gbpm",
    "mp",
    "ogbpm",
    "dgbpm",
    "oreb",
    "dreb",
    "treb",
    "ast",
    "stl",
    "blk",
    "pts",
    "role",
    "threep100",
    "dob",
]


def norm(value: object) -> str:
    text = str(value).lower().replace("&", "and")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


def bart_year(season: object) -> int:
    return int(str(season).split("-")[0]) + 1


def load_bart(year: int) -> pd.DataFrame:
    path = BART_DIR / f"trank_data_{year}.csv"
    frame = pd.read_csv(path)
    frame.columns = BART_COLUMNS[: len(frame.columns)]
    frame["source_file"] = str(path)
    frame["name_norm"] = frame["player_name"].map(norm)
    frame["team_norm"] = frame["team"].map(norm)
    return frame


def main() -> None:
    missing = pd.read_csv(MISSING_PATH)
    rows = (
        missing[
            missing["missing_column"].isin(
                ["big_west_porpag", "target_porpag", "target_barttorvik_bpm"]
            )
        ]
        .drop_duplicates(
            ["player_name", "target_conference", "destination_school", "first_big_west_season"]
        )
        .copy()
    )
    all_candidates = []
    for _, row in rows.iterrows():
        year = bart_year(row["first_big_west_season"])
        path = BART_DIR / f"trank_data_{year}.csv"
        if not path.exists():
            continue
        bart = load_bart(year)
        player_norm = norm(row["player_name"])
        dest_norm = norm(row["destination_school"])
        candidates = bart[bart["name_norm"].eq(player_norm)].copy()
        if candidates.empty and player_norm:
            last = player_norm.split()[-1]
            candidates = bart[bart["name_norm"].str.contains(last, na=False)].copy()
        if candidates.empty:
            all_candidates.append({**row.to_dict(), "candidate_status": "no_name_candidate"})
            continue
        candidates["team_score"] = candidates["team_norm"].map(
            lambda value: int(value == dest_norm) + int(dest_norm in value or value in dest_norm)
        )
        candidates["candidate_status"] = candidates["team_score"].map(
            lambda score: "team_match_candidate" if score else "name_only_candidate"
        )
        for _, cand in candidates.sort_values(["team_score", "porpag"], ascending=[False, False]).head(5).iterrows():
            all_candidates.append(
                {
                    **row.to_dict(),
                    "candidate_status": cand["candidate_status"],
                    "bart_player_name": cand["player_name"],
                    "bart_team": cand["team"],
                    "bart_conf": cand["conf"],
                    "bart_year": year,
                    "bart_porpag": cand["porpag"],
                    "bart_bpm": cand["bpm"],
                    "bart_obpm": cand["obpm"],
                    "bart_dbpm": cand["dbpm"],
                    "bart_pid": cand["pid"],
                    "source_file": cand["source_file"],
                    "team_score": cand["team_score"],
                }
            )
    out = pd.DataFrame(all_candidates)
    out_path = Path("data/modeling/training/missing_barttorvik_match_candidates.csv")
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} candidate rows)")
    if not out.empty:
        print(
            out[
                [
                    "player_name",
                    "destination_school",
                    "first_big_west_season",
                    "candidate_status",
                    "bart_player_name",
                    "bart_team",
                    "bart_porpag",
                    "bart_bpm",
                    "bart_pid",
                    "team_score",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
