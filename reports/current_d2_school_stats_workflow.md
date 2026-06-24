# Current D2 Official School Stats Workflow

Use this instead of bulk RealGM when validating suspicious current-D2 rows.

## What It Does

`scripts/fetch_current_d2_school_stats.py`:

- starts from `data/current_d2_suspicious_event_stats.csv` by default
- looks up each player's team in `data/d2_team_directory.csv`
- guesses official school stats URLs such as `/sports/mens-basketball/stats/2025-26`
- caches each fetched page in `data/cache/current_d2_school_stats/`
- parses the player row from HTML tables
- writes dashboard-ready overrides to `data/current_d2_school_verified_stats.csv`

The dashboard builder now reads, in priority order:

1. `data/current_d2_realgm_verified_stats.csv`
2. `data/current_d2_school_verified_stats.csv`
3. `data/current_d2_verified_stats.csv`

If the same player/team appears in multiple files, the later file in that list
wins, so manual verified rows still override school/RealGM rows.

## Preview Queue

This does not fetch pages. It only writes the candidate URL queue:

```bash
.venv/bin/python scripts/validate_current_d2_stats.py

.venv/bin/python scripts/fetch_current_d2_school_stats.py \
  --mode suspicious \
  --write-queue-only
```

Review:

```text
data/current_d2_school_stats_queue.csv
```

## Small Test Run

```bash
.venv/bin/python scripts/fetch_current_d2_school_stats.py \
  --mode suspicious \
  --limit 10 \
  --sleep 3
```

## Full Suspicious Batch

```bash
.venv/bin/python scripts/fetch_current_d2_school_stats.py \
  --mode suspicious \
  --sleep 3 \
  --append
```

Then rebuild the dashboard:

```bash
.venv/bin/python scripts/build_projection_dashboard_data.py
```

## URL Overrides

If a school domain is missing or the guessed stats URL is wrong, edit:

```text
data/current_d2_school_stat_url_overrides.csv
```

Columns:

```text
team,season,stats_url,notes
```

Example:

```csv
team,season,stats_url,notes
Tampa,2025-26,https://www.tampaspartans.com/sports/mbkb/2025-26/teams?sort=name,Presto stats page
```

Then rerun the script. The override URL will be tried first.

## Outputs

- `data/current_d2_school_verified_stats.csv`
- `data/current_d2_school_stats_missing.csv`
- `data/current_d2_school_stats_queue.csv`
- cached HTML under `data/cache/current_d2_school_stats/`
