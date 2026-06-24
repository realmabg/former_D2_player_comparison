# Current D2 Stats Audit

## Source Files Checked

- `d2_data_cleaned.csv` and `d2_data_cleaned copy.csv` are byte-for-byte identical.
- `d2_mens_database.csv` is a rawer upstream file, but it already contains the bad event-stat values. It also mixes row shapes under one header: the header includes `GS`, while many rows appear to omit starts and shift values under the wrong labels when read literally.

The dashboard now uses `d2_data_cleaned.csv` as the canonical current-D2 input, with validation/guardrails layered on top.

## What Happened

The dashboard is using `d2_data_cleaned.csv` for current D2 player box-score stats. Some rows in that file already contain impossible event-stat totals before the dashboard/model code reads them.

Example rows:

- Kolby Watson has `AST=62`, `APG=20.67`, and `ast_per_40=49.6` in the source CSV.
- Kolby Horace has `TO=53`, `TOPG=17.67`, and `tov_per_40=36.55` in the source CSV.

The website did not create those values. It was displaying and scoring from them.

## Likely Root Cause

The pattern looks like a D2 stats-page parsing problem. Many school stat tables include extra columns such as `FO` and `AST/G`, and older parser code in this repo used fixed token positions for columns after rebounds/fouls. If a source table includes an extra column or orders `PTS`, `REB`, `PF`, `FO`, `AST`, `AST/G`, `T/O`, `BLK`, and `STL` differently, fixed-position parsing can shift values into the wrong box-score fields.

The current CSV is internally consistent after the bad totals are present: for example, `AST / GP` equals `APG`. That means the bad value likely entered as the raw `AST` total, then downstream derived fields correctly computed nonsense from that bad total.

## Current Guardrail

`scripts/build_projection_dashboard_data.py` now treats impossible current-D2 event stats as missing before model scoring and website display.

Flagged rows are written to:

`data/current_d2_suspicious_event_stats.csv`

## Standalone Validation

Run this before rebuilding the dashboard or scoring current D2 players:

```bash
.venv/bin/python scripts/validate_current_d2_stats.py
```

Use this stricter mode if the build should fail when suspicious rows exist:

```bash
.venv/bin/python scripts/validate_current_d2_stats.py --fail-on-suspicious
```

## Long-Term Fix

The durable fix is to rebuild `d2_data_cleaned copy.csv` from the original raw source using column-name/header-based parsing instead of fixed token positions. Until the raw extraction pipeline is available, the validator and dashboard guardrail prevent obviously corrupted event stats from affecting projections.
