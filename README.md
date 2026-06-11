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

## Tech Stack

- **Frontend:** Streamlit + Plotly
- **Database:** PostgreSQL + SQLAlchemy
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

### 6. Run the dashboard
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
- **[StatsBomb Open Data](https://github.com/statsbomb/open-data)** — Event-level data (shots, passes, pressures) for WC 2018 and 2022
- **[openfootball/worldcup.json](https://github.com/openfootball/worldcup.json)** — All 104 WC 2026 fixtures, groups, and venues; public domain (CC0), no API key. Fallback/bootstrap source (`python -c` via `data/ingest/openfootball_loader.py`)
- **[Fjelstul World Cup Database](https://github.com/jfjelstul/worldcup)** — Full 1930–2022 match history for team-strength priors and historical EDA (`python scripts/fetch_external_data.py`). © Joshua C. Fjelstul, Ph.D., CC-BY-SA 4.0

## Resume Bullet Points

> Built a real-time analytics platform tracking 64 World Cup 2026 matches across 48 teams. Designed a normalized PostgreSQL schema ingesting dual data sources (live API + historical event data), built interactive Streamlit dashboards for team/player analysis, and trained a logistic regression match outcome model achieving [X]% accuracy on held-out 2022 WC data.
