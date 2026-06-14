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

---

## Build your first dashboard — step by step

Theory is cheap; building one is what teaches you. Here's a complete, click-by-click recipe for **the xG-vs-goals "finishing" dashboard** — the single most impressive thing to show in an interview, because it demonstrates you think about *performance vs. a model baseline*, not raw totals. Pick your tool:

### Tableau (≈15 minutes)

1. **Connect** to PostgreSQL (details above) → drag the **`v_player_stats`** view to the canvas → go to **Sheet 1**.
2. **Filter to a real sample.** Drag `Tournament Label` to **Filters** → pick `WC 2022`. Drag `Minutes` to Filters → set **At least 270** (kills small-sample noise — see the EDA notebook, §5).
3. **Build the scatter:**
   - Drag **`Xg`** to **Columns**, **`Goals`** to **Rows**. Both will aggregate — right-click each pill → **Dimension** isn't right here; instead set each to **AVG** off, use **Measure → (the raw value)**. Simplest: right-click the `Xg`/`Goals` pills → **Measure → Sum**, then drag **`Player`** to **Detail** (this makes one dot per player).
   - You now have a scatter of players: xG on the x-axis, goals on the y.
4. **Add the reference diagonal** (the "as expected" line): right-click the x-axis → **Add Reference Line** → choose a **constant** won't work for a diagonal, so instead create a calculated field **`Expected = [Xg]`** and plot it as a line, *or* (easier) just add a trend line: **Analytics tab → Trend Line → Linear**. Points above the trend = over-performers.
5. **Make it readable:** drag **`Team`** to **Color**, **`Player`** to **Label**. Drag **`Goals`-minus-`Xg`** (make a calculated field `Over = [Goals] - [Xg]`) to **Size** so the biggest over-performers pop.
6. **Title it** "Finishing: who beats their xG?" → **Dashboard → New Dashboard** → drag the sheet in. Publish to **Tableau Public** for a portfolio link (remember: Public makes data public — fine here, all open data).

**What it shows an interviewer:** a calculated field (`Goals - Xg`), a meaningful filter (min minutes), and a point of view (over/under-performance). That's analyst thinking, not just charting.

### Power BI (≈15 minutes)

1. **Get Data → PostgreSQL** → server `localhost`, database `worldcup2026` → **Import** → select **`v_player_stats`** → **Load**.
2. **Add the over-performance measure.** In the **Data** pane right-click the table → **New measure**:
   ```DAX
   Over Performance = SUM(v_player_stats[goals]) - SUM(v_player_stats[xg])
   ```
3. **Scatter chart:** Visualizations → **Scatter chart**. Set **X Axis = `xg`** (Sum), **Y Axis = `goals`** (Sum), **Values/Details = `player`** (one bubble per player), **Size = `Over Performance`**, **Legend = `team`**.
4. **Filter the noise:** drag `tournament_label` to **Filters** → `WC 2022`; drag `minutes` to Filters → **is greater than or equal to 270**.
5. **Add the y = x reference:** select the visual → **Analytics pane (the magnifying-glass icon)** → there's no built-in diagonal, so add a **trend line** instead → bubbles above it are the clinical finishers.
6. **Title** it, add a **card** visual showing the top `Over Performance` player, and you have a one-screen story. **Publish** to Power BI Service for a shareable link.

**KPI dashboard idea (either tool):** a second page with the `v_model_scorecard` view — a **card** for overall hit rate, a **gauge** for Brier score, and a **line chart** of accuracy by round. That's your "model performance" page, the finance-style track record.

> **The habit to build:** every dashboard should answer *one question* and have *one point of view*. "Goals by team" is a report; "who finishes above expectation" is an analysis. Aim for the second.
