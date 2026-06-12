# World Cup 2026 Analytics Platform

A real-time player performance and match analytics dashboard built during the 2026 FIFA World Cup. Combines live match data with historical StatsBomb event data to surface insights on team tactics, player contribution, and match predictions.

## Features

| Page | Description |
|---|---|
| 🌍 Tournament Overview | Live group standings, top scorers, recent results |
| 🔵 Team Analysis | Passing networks, xG timelines, formation stats |
| 👤 Player Stats | Per-90 leaderboards, radar comparisons |
| 🔮 Match Predictor | Win probability model trained on WC 2014–2022 |
| 💰 Player Valuation | Contribution scoring — finding undervalued players |
| 🏆 Bracket | Predicted (Elo + Monte Carlo) vs. reality, with model KPIs |

## Tech Stack

- **Frontend:** Streamlit + Plotly
- **Database:** PostgreSQL + SQLAlchemy
- **BI:** SQL analytical views consumed by Tableau & Power BI — see [docs/BI_SETUP.md](docs/BI_SETUP.md)
- **Data Sources:** football-data.org API (live), StatsBomb Open Data (historical)
- **ML:** scikit-learn (Logistic Regression)

## Setup

### 1. Prerequisites
- Python 3.11+
- PostgreSQL running locally (or set `DATABASE_URL` to a hosted instance)

### 2. Install dependencies
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env — add your football-data.org API key and DATABASE_URL
```

Get a free API key at https://www.football-data.org/client/register

### 4. Initialize the database
```bash
python scripts/seed_db.py
```

This creates all tables and seeds historical StatsBomb World Cup data (2018 + 2022).

### 5. Train the prediction model
```bash
python scripts/train_model.py
```

Trains a logistic regression model on historical WC data and saves to `models/match_predictor.pkl`.

### 6. Load data & create BI views
```bash
python scripts/refresh_live.py            # WC 2026 fixtures + live results → DB
python scripts/load_statsbomb_history.py  # WC 2018/2022 player stats → DB (slow first run)
python scripts/apply_views.py             # analytical views for Tableau / Power BI
```

Re-run `refresh_live.py` any time to pull the latest scores. Connect Tableau or Power BI to the `v_*` views — guide in [docs/BI_SETUP.md](docs/BI_SETUP.md).

### 7. Simulate the bracket
```bash
python scripts/run_bracket_sim.py --sims 10000
```

Builds team strength from 92 years of World Cup Elo blended with current FIFA ranks, then runs a 10,000-tournament Monte Carlo to produce advancement probabilities and a predicted bracket. Results feed the 🏆 Bracket page and the `v_bracket_predictions` / `v_model_scorecard` views — the scorecard (Brier score, hit rate) grades the model against reality as matches finish.

### 8. Run the dashboard
```bash
streamlit run app/main.py
```

## Project Structure

```
worldcup2026/
├── app/
│   ├── main.py                     # Home page
│   ├── pages/
│   │   ├── 1_Tournament_Overview.py
│   │   ├── 2_Team_Analysis.py
│   │   ├── 3_Player_Stats.py
│   │   ├── 4_Match_Predictor.py
│   │   └── 5_Player_Valuation.py
│   └── utils/
│       └── charts.py               # Reusable Plotly chart builders
├── data/
│   ├── ingest/
│   │   ├── football_data_api.py    # Live WC2026 data
│   │   └── statsbomb_loader.py     # Historical event data
│   └── transform/
│       └── processors.py           # Cleaning & metric derivation
├── database/
│   ├── schema.sql                  # Full PostgreSQL schema
│   └── db.py                       # SQLAlchemy engine + session
├── models/
│   ├── match_predictor.py          # Win probability model
│   └── player_rating.py            # Composite contribution score
├── scripts/
│   ├── seed_db.py                  # Initialize & seed database
│   └── train_model.py              # Train & persist ML model
└── requirements.txt
```

## Data Sources

- **[football-data.org](https://www.football-data.org/)** — Live match results, standings, scorers for WC 2026 (free tier, 10 req/min)
- **[StatsBomb Open Data](https://github.com/statsbomb/open-data)** — Event-level data (shots, passes, pressures) for **WC 2018/2022, Euro 2020/2024, Copa América 2024, AFCON 2023** (`python scripts/load_statsbomb_history.py`)
- **[openfootball/worldcup.json](https://github.com/openfootball/worldcup.json)** — All 104 WC 2026 fixtures, groups, and venues; public domain (CC0), no API key. Fallback/bootstrap source (`scripts/refresh_live.py` via `data/ingest/openfootball_loader.py`)
- **[Fjelstul World Cup Database](https://github.com/jfjelstul/worldcup)** — Full 1930–2022 match history; WC 2010 + 2014 are loaded into the DB at match/goal level (`python scripts/fetch_external_data.py`, then `python scripts/load_fjelstul_history.py`). © Joshua C. Fjelstul, Ph.D., CC-BY-SA 4.0
- **[Kaggle: FIFA World Cup Complete Dataset 1930–2026](https://www.kaggle.com/datasets/kulkarniparth09/fifa-world-cup-complete-dataset-19302026)** — 2026 team metadata (FIFA ranks, confederations, coaches) and a 1930–2026 tournament-edition summary. Its match data is a small curated subset — Fjelstul remains the historical match source of record
- **[Kaggle: Road to 2026 Squad Prediction](https://www.kaggle.com/datasets/ardaciftci/road-to-2026-world-cup-squad-prediction)** — Pre-tournament form snapshot for ~1,200 national-team players (appearances, goals, assists, minutes, contribution metrics). Loaded into `player_form_2026` / exposed as `v_player_form_2026` (`python scripts/fetch_kaggle_data.py`, then `python scripts/load_kaggle_data.py`)

**Tournament coverage in PostgreSQL:** WC 2010 · WC 2014 · WC 2018 · WC 2022 · WC 2026 (live) · EURO 2020 · EURO 2024 · COPA 2024 · AFCON 2023 — sliceable via the `tournament_label` column in every BI view.

## Resume Bullet Points

> Built a real-time analytics platform tracking 64 World Cup 2026 matches across 48 teams. Designed a normalized PostgreSQL schema ingesting dual data sources (live API + historical event data), built interactive Streamlit dashboards for team/player analysis, and trained a logistic regression match outcome model achieving [X]% accuracy on held-out 2022 WC data.
