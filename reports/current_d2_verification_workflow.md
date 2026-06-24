# Current D2 Verification Workflow

Use this when a current D2 player has suspicious or important stats that need to be verified before using the dashboard projection.

## Files

- Input template: `data/current_d2_verification_input.csv`
- Verified overrides: `data/current_d2_verified_stats.csv`
- Missing/unparsed rows: `data/current_d2_verified_stats_missing.csv`
- Dashboard data: `data/projection_dashboard_data.json`

## Step 1: Fill The Input

Open:

`data/current_d2_verification_input.csv`

For each player, either:

- paste a `source_url`, or
- manually fill verified stat columns such as `GP`, `MIN`, `PTS`, `PPG`, `AST`, `TO`, `STL`, `BLK`.

Manual columns are preferred when a school page is hard to parse. You do not need every column; the script will use whatever verified fields are present.

## Step 2: Create Verified Overrides

```bash
.venv/bin/python scripts/fetch_current_d2_verified_stats.py \
  --input data/current_d2_verification_input.csv \
  --sleep 4
```

This writes:

```bash
data/current_d2_verified_stats.csv
data/current_d2_verified_stats_missing.csv
```

If a row appears in the missing file, either add a better URL or manually fill stat columns in the input CSV.

## Step 3: Rebuild Dashboard Data

```bash
.venv/bin/python scripts/build_projection_dashboard_data.py
```

The builder automatically applies `data/current_d2_verified_stats.csv` before scoring players.

## Step 4: Refresh The Website

If the static server is already running, hard-refresh the browser.

If not:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

## Optional QA

Run the validator after adding overrides:

```bash
.venv/bin/python scripts/validate_current_d2_stats.py
```

Note: this validator checks the base `d2_data_cleaned.csv`, not the verified dashboard overlay. It is still useful for finding more players to review.
