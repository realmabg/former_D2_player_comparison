#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-.venv/bin/python}"

echo "Rebuilding modeling artifacts..."
"$PYTHON" scripts/build_modeling_artifacts.py

echo
echo "Writing current missing-data reports..."
"$PYTHON" scripts/write_current_missing_reports.py

echo
echo "Running tuned model comparison on all rows..."
"$PYTHON" scripts/run_d2_available_model_comparison.py \
  --out-dir reports/d2_available_model_comparison

echo
echo "Running tuned model comparison with minimum target MPG >= 10..."
"$PYTHON" scripts/run_d2_available_model_comparison.py \
  --min-target-mpg 10 \
  --out-dir reports/d2_available_model_comparison_min_mpg_10

echo
echo "Done."
echo "Main reports:"
echo "  reports/d2_available_model_comparison/model_comparison_report.md"
echo "  reports/d2_available_model_comparison_min_mpg_10/model_comparison_report.md"
echo
echo "Best-model summaries:"
echo "  reports/d2_available_model_comparison/best_models_summary.csv"
echo "  reports/d2_available_model_comparison_min_mpg_10/best_models_summary.csv"
