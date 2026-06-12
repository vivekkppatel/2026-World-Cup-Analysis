# Connecting Tableau & Power BI

The PostgreSQL database exposes **BI views** (defined in [`database/views.sql`](../database/views.sql)) — connect your BI tool to these, never to the raw tables. The views are the stable contract; raw tables can change underneath without breaking your dashboards.

## The views

| View | What it answers | Has data today? |
|---|---|---|
| `v_group_standings` | Live group tables, computed from match results | ✅ all 48 teams (0 pts until matches finish) |
| `v_match_results` | Every finished match, all tournaments | ✅ 9 tournaments, 2010→2024 |
| `v_upcoming_fixtures` | Schedule with venues, `2A`-style knockout slots | ✅ all 104 WC 2026 fixtures |
| `v_player_stats` | Per-player tournament totals + per-90 rates | ✅ 8 tournaments (WC 2010/14 = goals only) |
| `v_top_scorers` | Golden Boot race per tournament | ✅ 8 tournaments |
| `v_team_match_stats` | Team xG / shots / passes per match | ✅ 6 event-level tournaments |
| `v_player_form_2026` | Pre-tournament form for ~1,200 squad players | ✅ Kaggle "Road to 2026" snapshot |
| `v_predictions_vs_results` | Model accuracy tracking | ⬜ empty until predictions are stored |

Every view carries `tournament_label` (`WC 2022`, `EURO 2024`, `COPA 2024`, `AFCON 2023`…) — use it as the slicer/filter dimension in Tableau and Power BI. Note: WC 2010/2014 predate public event data, so their xG/passes/pressures are NULL by design (goals only, from the Fjelstul database).

Keep data fresh by re-running:

```powershell
python scripts/refresh_live.py
```

## Connection details (both tools)

| Field | Value |
|---|---|
| Server / Host | `localhost` |
| Port | `5432` |
| Database | `worldcup2026` |
| Username | `postgres` |
| Password | your Postgres password |

> ⚠️ Never publish a dashboard with embedded credentials, and remember **Tableau Public makes your data public** — fine for this project (all sources are open data), but form the habit of checking.

## Tableau

1. **Connect → To a Server → PostgreSQL** (first time: Tableau prompts you to install the PostgreSQL driver — accept).
2. Enter the connection details above → **Sign In**.
3. Drag views from the left panel onto the canvas (start with `v_group_standings`).
4. **Live vs Extract:** choose **Live** — the dataset is tiny and you'll see new results the moment `refresh_live.py` runs.

**Starter dashboard ideas** (in increasing order of interview value):
- Group-stage heat map: `v_group_standings` — groups × teams, color by points.
- Golden Boot tracker: `v_top_scorers` — bar chart, filter by `tournament_year`.
- **xG vs actual goals scatter** from `v_player_stats` (x = `xg`, y = `goals`, one dot per player, diagonal reference line). Players above the line are finishing above expectation — this is the chart to walk through in an interview, because it shows you understand *over/under-performance vs a model baseline*, the same idea as alpha vs benchmark in finance.

## Power BI

1. **Get Data → Database → PostgreSQL database**.
2. Server: `localhost`, Database: `worldcup2026` → **OK** → Database tab → enter username/password.
3. If you get a driver error, install [Npgsql](https://github.com/npgsql/npgsql/releases) (choose "GAC installation") and restart Power BI.
4. Select the `v_*` views in the Navigator → **Load**.
5. **Import vs DirectQuery:** choose **Import** (fast, full DAX support). Refresh with the ribbon's Refresh button after running `refresh_live.py`.

**Starter ideas:** group standings matrix with conditional formatting; a tournament-year slicer comparing 2018 vs 2022 player stats; a KPI card row (total goals, avg goals/match, top scorer) over `v_match_results`.

## Raw SQL practice

These views are also your SQL playground (see `docs/LEARNING_PATH.md`, Module 5). Connect with:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d worldcup2026
```

Two queries worth understanding — both use patterns interviewers ask about:

```sql
-- Window function: each team's rank within its group (this is how
-- v_group_standings works internally)
SELECT group_name, team, points,
       RANK() OVER (PARTITION BY group_name ORDER BY points DESC) AS pos
FROM v_group_standings;

-- Self-comparison: players who outscored their xG by the most (2022)
SELECT player, team, goals, xg, ROUND(goals - xg, 2) AS overperformance
FROM v_player_stats
WHERE tournament_year = 2022 AND minutes >= 270
ORDER BY overperformance DESC
LIMIT 10;
```

## Also worth importing into BI directly

The Fjelstul historical CSVs (`python scripts/fetch_external_data.py` → `data/external/fjelstul/`) cover **every World Cup 1930–2022**. Tableau and Power BI both read CSVs natively — `matches.csv` (1,248 matches) makes a great "92 years of World Cup history" dashboard without touching the database.
