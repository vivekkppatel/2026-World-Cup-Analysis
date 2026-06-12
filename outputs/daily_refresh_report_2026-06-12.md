# FIFA World Cup Analytics — Daily Data Refresh Check
**Date:** 2026-06-12  
**Task:** `fifa-daily-data-refresh-check`  
**Mode:** Read-only inspection (no code changes made)

---

## Summary

| Area | Status | One-line finding |
|------|--------|-----------------|
| 1. New match data | 🔴 CRITICAL | `outputs/` is empty — no processed data exists |
| 2. Schema integrity | ⚠️ WARNING | Kaggle sources missing 4 required fields; no source CSV contains `xG` or `player_id` |
| 3. xG anomaly detection | ⚠️ BLOCKED | Cannot run — no `xG` data accessible (outputs empty, StatsBomb not yet fetched) |
| 4. Pipeline status | ⚠️ WARNING | Scripts ran this morning (05:15–06:05) but produced no output to `outputs/` |

---

## Area 1 — New Match Data Availability 🔴

**Finding:** The `outputs/` directory is completely empty. No processed match data, predictions, or reports exist.

**Raw source file activity (all Jun 11, not today):**
- `data/external/fjelstul/matches.csv` — Jun 11 19:09 (299KB, 300 historical WC matches)
- `data/external/fjelstul/team_appearances.csv` — Jun 11 19:09 (558KB)
- `data/external/kaggle/wc_complete/wc_all_matches.csv` — Jun 11 23:48
- `data/external/kaggle/road_to_2026/fifa_world_cup_2026_golden_dataset.csv` — Jun 11 23:48

**No new data ingested today.** Raw sources unchanged since yesterday evening.

**Fix required:** Pipeline scripts (`scripts/train_model.py`, `scripts/predict_wc2026.py`, `scripts/run_bracket_sim.py`) appear to run but do not write results to `outputs/`. Investigate output path configuration in those scripts — they may be writing to a local working directory, a database, or no persistent destination at all.

---

## Area 2 — Schema Integrity ⚠️

Required fields monitored: `match_id`, `team_id`, `xG`, `timestamp`, `player_id`

### Fjelstul Dataset (authoritative historical source)

**`data/external/fjelstul/matches.csv`**
| Field | Status | Notes |
|-------|--------|-------|
| `match_id` | ✅ Present | Column: `match_id` |
| `team_id` | ✅ Present | Via `home_team_id` / `away_team_id` |
| `timestamp` | ✅ Present | Via `match_date` + `match_time` |
| `xG` | ⚠️ Absent | Not in this file — expected, lives in StatsBomb |
| `player_id` | ⚠️ Absent | Not in this file — match-level only |

**`data/external/fjelstul/team_appearances.csv`**
| Field | Status | Notes |
|-------|--------|-------|
| `match_id` | ✅ Present | |
| `team_id` | ✅ Present | |
| `timestamp` | ✅ Present | Via `match_date` + `match_time` |
| `xG` | ⚠️ Absent | Expected — this is historical goals data, not xG |
| `player_id` | ⚠️ Absent | Team-level file, not player-level |

### Kaggle Dataset — `wc_all_matches.csv`

Header: `year,stage,team1,score1,score2,team2,venue,city,country,date,notes`

| Field | Status | Issue |
|-------|--------|-------|
| `match_id` | 🔴 MISSING | No identifier — only implicitly keyed by year+team1+team2 |
| `team_id` | 🔴 MISSING | Uses team name strings (`team1`, `team2`) — no foreign key |
| `timestamp` | ✅ Present | Via `date` column |
| `xG` | ⚠️ Absent | Expected |
| `player_id` | ⚠️ Absent | Match-level file |

**Risk:** This file cannot be reliably joined to the rest of the pipeline without `match_id` / `team_id`. Any feature engineering that uses it will depend on fuzzy name matching.

### Kaggle Dataset — `fifa_world_cup_2026_golden_dataset.csv`

Header: `name,team_name,group,appearances,goals,assists,minutes,total_contributions,contributions_per_90,efficiency_score`

| Field | Status | Issue |
|-------|--------|-------|
| `match_id` | 🔴 MISSING | Aggregated player stats, no per-match identifier |
| `team_id` | 🔴 MISSING | Uses `team_name` string only |
| `timestamp` | 🔴 MISSING | No date/time column |
| `xG` | 🔴 MISSING | No xG column — only goals/assists/minutes |
| `player_id` | 🔴 MISSING | Player identified by `name` string only |

**Risk:** This file lacks every required schema field. It is a summarized "golden dataset" intended as reference material, not a pipeline input. Do not use it as an authoritative player stats source without cross-referencing a source that has `player_id`.

### StatsBomb Loader (xG source)
`data/ingest/statsbomb_loader.py` correctly implements xG collection:
- Player-level: `shot_statsbomb_xg` → `xg` column, keyed by `player_id` + `match_id`
- Team-level: per-match `xg` totals, keyed by `team_id` + `match_id`

**But no StatsBomb data has been fetched/materialized to disk.** The loader requires a live StatsBomb API/SDK call; no cached results were found anywhere in the repo.

---

## Area 3 — xG Anomaly Detection ⚠️ BLOCKED

**Status:** Cannot execute. No `xG` column exists in any inspected CSV file. StatsBomb is the only configured xG source (`data/ingest/statsbomb_loader.py`), but no StatsBomb data has been materialized to `outputs/` or any cache directory.

**Anomaly thresholds that would be checked once data is available:**
- 🔴 Team xG > 4.0 per match (extreme outlier — suspect data quality)
- 🔴 Player xG exactly 0.000 (may indicate shot data not loaded rather than genuine 0)
- 🔴 Any negative xG value (data corruption)

**Fix required:**
1. Run `StatsBombLoader.get_player_tournament_stats()` and `get_team_match_stats()` and persist outputs to `outputs/statsbomb_player_stats.csv` and `outputs/statsbomb_team_stats.csv`.
2. Once those files exist, this check can run automatically tomorrow.

---

## Area 4 — Pipeline Status ⚠️

**File modification times (Jun 12 = today):**

| File | Last Modified | Notes |
|------|--------------|-------|
| `models/player_rating.py` | 06:05 today | Most recent activity in repo |
| `scripts/predict_wc2026.py` | 05:18 today | Ran this morning |
| `scripts/run_bracket_sim.py` | 05:18 today | Ran this morning |
| `scripts/train_model.py` | 05:15 today | Ran this morning |
| `models/match_predictor.pkl` | 05:15 today | ⚠️ Only 1.7KB — suspiciously small |
| `models/features.py` | 05:15 today | |
| `models/match_predictor.py` | 05:13 today | |
| `models/elo.py` | 05:11 today | |
| `models/tournament_sim.py` | 04:58 today | |
| All raw CSVs | Jun 11 | No new ingestion today |

**Critical discrepancy:** Pipeline scripts ran successfully this morning (05:15–05:18) but `outputs/` remains empty. One of the following is happening:

1. **Output path misconfiguration** — scripts write to a relative path that resolves outside `outputs/` when run in context (e.g., from `scripts/` working directory)
2. **Database-only output** — scripts write to the SQLite/PostgreSQL DB in `database/` rather than CSVs (check `database/db.py`)
3. **Silent failure** — scripts complete without error but an upstream data-loading failure (e.g., no StatsBomb credentials) results in empty DataFrames that are never written
4. **Stub model** — `models/match_predictor.pkl` at 1.7KB is far too small for a trained sklearn model (typical: 50KB–5MB). The model may be a placeholder, meaning predictions are not meaningful.

**Recommended fix sequence:**
1. Check `scripts/predict_wc2026.py` for the output file path — run `grep -n "to_csv\|outputs\|write\|save" scripts/predict_wc2026.py`
2. Check `database/db.py` for SQLite path — outputs may be going to DB not filesystem
3. Re-run `scripts/train_model.py` with logging enabled and verify `match_predictor.pkl` grows to expected size (>50KB after training on 1930–2022 WC data)
4. Add explicit `outputs/` path assertions to all pipeline scripts

---

## Action Items (Priority Order)

| Priority | Action | Owner area |
|----------|--------|-----------|
| 🔴 P0 | Diagnose why `outputs/` is empty after pipeline run — check output paths in `scripts/predict_wc2026.py` and `run_bracket_sim.py` | Pipeline |
| 🔴 P0 | Investigate `models/match_predictor.pkl` at 1.7KB — retrain on actual data and validate size | Models |
| ⚠️ P1 | Materialize StatsBomb xG data to disk — call `StatsBombLoader.get_team_match_stats()` and persist to `outputs/statsbomb_team_stats.csv` | Data ingestion |
| ⚠️ P1 | Add `match_id` and `team_id` mappings for `kaggle/wc_all_matches.csv` — or exclude it from pipeline joins | Schema |
| ⚠️ P2 | Add `player_id` to `kaggle/golden_dataset` by joining on `name` + `team_name` against a StatsBomb player roster | Schema |
| ℹ️ P3 | Once StatsBomb data is materialized, rerun xG anomaly check (thresholds: >4.0 team, exact 0.000 player, negative) | Monitoring |

---

*Report generated by automated scheduled task `fifa-daily-data-refresh-check` · 2026-06-12 · Read-only inspection, no changes made*
