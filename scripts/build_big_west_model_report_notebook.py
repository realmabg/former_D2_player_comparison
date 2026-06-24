"""Build a lightweight notebook report for the Big West model comparison."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
NOTEBOOK_PATH = REPORTS / "big_west_model_summary.ipynb"
MARKDOWN_PATH = REPORTS / "big_west_model_summary.md"


RUN_SUMMARY = DATA / "big_west_model_run_summary.csv"

LEADERBOARDS = {
    ("impact_score", "random_kfold"): DATA / "big_west_model_leaderboard.csv",
    ("impact_score", "season_holdout"): DATA / "big_west_model_leaderboard_season_holdout.csv",
    ("bpm", "random_kfold"): DATA / "big_west_model_leaderboard_bpm.csv",
    ("bpm", "season_holdout"): DATA / "big_west_model_leaderboard_bpm_season_holdout.csv",
    ("porpag", "random_kfold"): DATA / "big_west_model_leaderboard_porpag.csv",
    ("porpag", "season_holdout"): DATA / "big_west_model_leaderboard_porpag_season_holdout.csv",
}

IMPORTANCES = {
    ("impact_score", "random_kfold"): DATA / "big_west_model_feature_importance.csv",
    ("impact_score", "season_holdout"): DATA / "big_west_model_feature_importance_season_holdout.csv",
    ("bpm", "random_kfold"): DATA / "big_west_model_feature_importance_bpm.csv",
    ("bpm", "season_holdout"): DATA / "big_west_model_feature_importance_bpm_season_holdout.csv",
    ("porpag", "random_kfold"): DATA / "big_west_model_feature_importance_porpag.csv",
    ("porpag", "season_holdout"): DATA / "big_west_model_feature_importance_porpag_season_holdout.csv",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def fmt(value: object, digits: int = 3) -> str:
    if value is None:
        return ""
    text = str(value)
    if text == "":
        return ""
    try:
        return f"{float(text):.{digits}f}"
    except ValueError:
        return text


def markdown_table(rows: list[dict[str, object]], columns: list[str], labels: dict[str, str] | None = None) -> str:
    labels = labels or {}
    if not rows:
        return "_No rows found._"

    header = [labels.get(col, col) for col in columns]
    out = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        cells = [str(row.get(col, "")) for col in columns]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def run_summary_section() -> tuple[str, list[dict[str, str]]]:
    rows = read_csv(RUN_SUMMARY)
    display_rows = []
    for row in rows:
        display_rows.append(
            {
                "target": row["target"],
                "validation": row["validation"],
                "feature_set": row.get("feature_set", "all"),
                "rows_used": row["rows_used"],
                "best_model": row["best_model"],
                "cv_mae": fmt(row["cv_mae"]),
                "baseline_mae": fmt(row["baseline_mae"]),
                "mae_improvement_vs_baseline": fmt(row["mae_improvement_vs_baseline"]),
                "cv_rmse": fmt(row["cv_rmse"]),
                "baseline_rmse": fmt(row.get("baseline_rmse")),
                "cv_r2": fmt(row["cv_r2"]),
                "baseline_r2": fmt(row.get("baseline_r2")),
                "cv_corr": fmt(row["cv_corr"]),
                "baseline_corr": fmt(row.get("baseline_corr")),
            }
        )

    md = "## Overall Run Summary\n\n"
    md += markdown_table(
        display_rows,
        [
            "target",
            "validation",
            "feature_set",
            "rows_used",
            "best_model",
            "cv_mae",
            "baseline_mae",
            "mae_improvement_vs_baseline",
            "cv_rmse",
            "baseline_rmse",
            "cv_r2",
            "baseline_r2",
            "cv_corr",
            "baseline_corr",
        ],
        {
            "feature_set": "Features",
            "cv_mae": "MAE",
            "baseline_mae": "Baseline MAE",
            "mae_improvement_vs_baseline": "MAE Gain",
            "cv_rmse": "RMSE",
            "baseline_rmse": "Baseline RMSE",
            "cv_r2": "R2",
            "baseline_r2": "Baseline R2",
            "cv_corr": "Corr",
            "baseline_corr": "Baseline Corr",
        },
    )
    return md, rows


def takeaways(rows: list[dict[str, str]]) -> str:
    by_key = {(row["target"], row["validation"], row.get("feature_set", "all")): row for row in rows}
    impact = by_key.get(("impact_score", "season_holdout", "common_box")) or by_key.get(
        ("impact_score", "season_holdout", "all"), {}
    )
    bpm = by_key.get(("bpm", "season_holdout", "common_box")) or by_key.get(("bpm", "season_holdout", "all"), {})
    porpag = by_key.get(("porpag", "season_holdout", "common_box")) or by_key.get(
        ("porpag", "season_holdout", "all"), {}
    )

    row_count = max((int(row["rows_used"]) for row in rows if str(row.get("rows_used", "")).isdigit()), default=0)

    return f"""## Main Takeaways

- The most useful first-model target is still `impact_score`, especially under season-holdout validation.
- `impact_score` season holdout uses {impact.get("rows_used", "n/a")} rows, picks `{impact.get("best_model", "n/a")}`, and improves MAE by about {fmt(impact.get("mae_improvement_vs_baseline"))} over the fold-mean baseline.
- `BPM` and `PORPAG` are now fully wired as alternate targets, but their validation correlations remain low in the current {row_count}-row dataset.
- `PORPAG` coverage is complete after the Josh Ward manual BartTorvik PRPG row; the season-holdout PORPAG run improves MAE by about {fmt(porpag.get("mae_improvement_vs_baseline"))}.
- `BPM` season holdout improves MAE by about {fmt(bpm.get("mae_improvement_vs_baseline"))}, but its R2 is still slightly negative, so it should be treated as exploratory.

Interpretation: the custom impact blend is currently more stable than raw BPM/PORPAG because the sample is small and the Big West role/outcome signal is noisy. The next real improvement probably comes from more historical rows, not from changing model families.
"""


def leaderboard_section(target: str, validation: str, path: Path) -> str:
    rows = read_csv(path)
    rows = sorted(rows, key=lambda row: float(row["cv_mae"]) if row.get("cv_mae") else 999999)[:8]
    display_rows = [
        {
            "model_name": row["model_name"],
            "status": row["status"],
            "cv_mae": fmt(row["cv_mae"]),
            "cv_rmse": fmt(row["cv_rmse"]),
            "cv_r2": fmt(row["cv_r2"]),
            "cv_corr": fmt(row["cv_corr"]),
            "train_mae": fmt(row["train_mae"]),
        }
        for row in rows
    ]
    return (
        f"## Leaderboard: `{target}` / `{validation}`\n\n"
        + markdown_table(
            display_rows,
            ["model_name", "status", "cv_mae", "cv_rmse", "cv_r2", "cv_corr", "train_mae"],
            {
                "model_name": "Model",
                "cv_mae": "MAE",
                "cv_rmse": "RMSE",
                "cv_r2": "R2",
                "cv_corr": "Corr",
                "train_mae": "Train MAE",
            },
        )
    )


def feature_importance_section(target: str, validation: str, path: Path) -> str:
    rows = read_csv(path)
    if not rows:
        return f"## Feature Importance: `{target}` / `{validation}`\n\n_No feature-importance file found._"
    rows = sorted(rows, key=lambda row: float(row.get("importance") or 0), reverse=True)[:12]
    display_rows = [
        {
            "feature": row["feature"],
            "importance": fmt(row.get("importance")),
            "direction": row.get("direction", ""),
            "permutation_importance_mean": fmt(row.get("permutation_importance_mean")),
            "model_feature_importance": fmt(row.get("model_feature_importance")),
        }
        for row in rows
    ]
    return (
        f"## Top Features: `{target}` / `{validation}`\n\n"
        + markdown_table(
            display_rows,
            [
                "feature",
                "importance",
                "direction",
                "permutation_importance_mean",
                "model_feature_importance",
            ],
            {
                "permutation_importance_mean": "Permutation",
                "model_feature_importance": "Model Importance",
            },
        )
    )


def code_cell(source: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def markdown_cell(source: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def build() -> None:
    REPORTS.mkdir(exist_ok=True)

    summary_md, rows = run_summary_section()
    row_count = max((int(row["rows_used"]) for row in rows if str(row.get("rows_used", "")).isdigit()), default=0)
    sections = [
        f"# Big West Transfer Model Summary\n\nGenerated on {date.today().isoformat()} from the current files in `data/`.\n",
        f"## Scope\n\nThis report covers the first Big West model experiments using the current {row_count} model-ready D1/D2 transfer rows. JUCO rows are still excluded from this first model unless they later get matching source stats and Massey conference power.\n",
        summary_md,
        takeaways(rows),
    ]

    for key, path in LEADERBOARDS.items():
        sections.append(leaderboard_section(key[0], key[1], path))

    sections.append("## Feature Importance Notes\n\nThese are model-specific and should be read as directional, not causal. With only 125 rows, stable validation performance matters more than any single feature rank.\n")
    for key, path in IMPORTANCES.items():
        sections.append(feature_importance_section(key[0], key[1], path))

    sections.append(
        """## How To Refresh

Run the model scripts, summarize the metrics, then rebuild this notebook:

```bash
.venv/bin/python scripts/build_big_west_first_model.py --target impact_score
.venv/bin/python scripts/build_big_west_first_model.py --target impact_score --validation season_holdout
.venv/bin/python scripts/build_big_west_first_model.py --target bpm
.venv/bin/python scripts/build_big_west_first_model.py --target bpm --validation season_holdout
.venv/bin/python scripts/build_big_west_first_model.py --target porpag
.venv/bin/python scripts/build_big_west_first_model.py --target porpag --validation season_holdout
.venv/bin/python scripts/summarize_big_west_model_runs.py
.venv/bin/python scripts/build_big_west_model_report_notebook.py
```
"""
    )

    markdown_report = "\n\n".join(sections)
    MARKDOWN_PATH.write_text(markdown_report + "\n")

    notebook = {
        "cells": [
            *[markdown_cell(section) for section in sections],
            code_cell(
                """import pandas as pd

summary = pd.read_csv("../data/big_west_model_run_summary.csv")
summary
"""
            ),
            code_cell(
                """from pathlib import Path
import pandas as pd

leaderboard_files = sorted(Path("../data").glob("big_west_model_leaderboard*.csv"))
for path in leaderboard_files:
    print("\\n", path.name)
    display(pd.read_csv(path).sort_values("cv_mae").head(8))
"""
            ),
            code_cell(
                """from pathlib import Path
import pandas as pd

importance_files = sorted(Path("../data").glob("big_west_model_feature_importance*.csv"))
for path in importance_files:
    print("\\n", path.name)
    display(pd.read_csv(path).sort_values("importance", ascending=False).head(12))
"""
            ),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2) + "\n")
    print(f"Wrote {NOTEBOOK_PATH.relative_to(ROOT)}")
    print(f"Wrote {MARKDOWN_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
