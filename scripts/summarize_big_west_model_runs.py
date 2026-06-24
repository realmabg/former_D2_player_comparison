#!/usr/bin/env python3
"""Summarize first-model run metrics across targets and validation modes."""

from __future__ import annotations

import csv
import json
from pathlib import Path

OUTPUT_PATH = Path("data/big_west_model_run_summary.csv")


def read_payload(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    rows = []
    for path in sorted(Path("data").glob("big_west_model_metrics*.json")):
        payload = read_payload(path)
        if not payload:
            continue
        best = payload["best_overall_metrics"]
        baseline = payload["baseline"]
        cv_mae = float(best["cv_mae"])
        baseline_mae = float(baseline["mae"])
        rows.append(
            {
                "target": payload["target"],
                "validation": payload.get("validation", "random_kfold"),
                "feature_set": payload.get("feature_set", "all"),
                "rows_used": payload["rows_used"],
                "best_model": payload["best_overall"],
                "best_status": payload["best_overall_status"],
                "cv_mae": cv_mae,
                "baseline_mae": baseline_mae,
                "mae_improvement_vs_baseline": baseline_mae - cv_mae,
                "cv_rmse": best["cv_rmse"],
                "baseline_rmse": baseline["rmse"],
                "cv_r2": best["cv_r2"],
                "baseline_r2": baseline["r2"],
                "cv_corr": best["cv_corr"],
                "baseline_corr": baseline["corr"],
                "massey_power_source": payload.get("massey_power_source", ""),
            }
        )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
