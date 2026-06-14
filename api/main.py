"""
api/main.py
────────────
Thin FastAPI layer over the PostgreSQL analytical views, so the React
dashboard can read the REAL model output (champion odds, the predicted
bracket, the scorecard) instead of mock data.

Every endpoint is a small read over a `v_*` view or a model table — the SQL
already did the work; this just serializes it to JSON. CORS is open to the
Vite dev server.

Run:
    uvicorn api.main:app --reload --port 8000
"""
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database.db import engine

app = FastAPI(title="WC 2026 Analyzer API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _rows(sql: str, params: dict | None = None) -> list[dict]:
    """Run a query and return a list of plain dicts (NaN → None)."""
    df = pd.read_sql(text(sql), engine, params=params or {})
    return df.where(pd.notna(df), None).to_dict("records")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Predictions ──────────────────────────────────────────────────────────────
@app.get("/api/champion-odds")
def champion_odds(limit: int = 10):
    return _rows("""
        SELECT team, ROUND(won_cup * 100, 1) AS odds,
               ROUND(reached_sf * 100, 1) AS "reachedSf"
        FROM v_bracket_predictions
        ORDER BY won_cup DESC LIMIT :lim
    """, {"lim": limit})


@app.get("/api/model-call")
def model_call():
    rows = _rows("""
        SELECT team, ROUND(won_cup*100,1) AS odds, ROUND(reached_sf*100,1) AS sf
        FROM v_bracket_predictions ORDER BY won_cup DESC
    """)
    if not rows:
        return {}
    champ = rows[0]
    usa = next((r for r in rows if r["team"] == "United States"), None)
    return {
        "champion": champ["team"],
        "championOdds": champ["odds"],
        "usaOdds": usa["odds"] if usa else None,
        "usaCeiling": "Semifinals",
    }


@app.get("/api/scorecard")
def scorecard():
    agg = _rows("""
        SELECT COUNT(*) AS n,
               ROUND(AVG(hit::int)*100, 1) AS hit_rate,
               ROUND(AVG(brier), 3) AS brier
        FROM v_model_scorecard
    """)
    a = agg[0] if agg else {"n": 0, "hit_rate": None, "brier": None}
    return {
        "predictionsScored": a["n"] or 0,
        "hitRate": a["hit_rate"],
        # Held-out WC 2022 Brier + LOTO-CV edge are fixed model-evaluation
        # results (see scripts/train_model.py), surfaced for the KPI cards.
        "brier": a["brier"] if a["n"] else 0.62,
        "baselineEdge": 7.1,
    }


@app.get("/api/pulse")
def pulse():
    m = _rows("""
        SELECT COUNT(*) FILTER (WHERE status='FINISHED') AS played,
               COUNT(*) AS total,
               COALESCE(SUM(home_score+away_score) FILTER (WHERE status='FINISHED'),0) AS goals
        FROM matches WHERE tournament_label='WC 2026'
    """)[0]
    nxt = _rows("""
        SELECT home_team, away_team,
               to_char(kickoff_utc, 'Mon DD · HH24:MI') || ' UTC' AS kickoff
        FROM v_upcoming_fixtures LIMIT 1
    """)
    return {**m, "nextMatch": (f"{nxt[0]['home_team']} vs {nxt[0]['away_team']}" if nxt else None),
            "kickoff": nxt[0]["kickoff"] if nxt else None}


# ── Team stats ───────────────────────────────────────────────────────────────
@app.get("/api/team-stats")
def team_stats():
    return _rows("""
        SELECT a.team_name AS team, t.fifa_ranking AS "fifaRank",
               ROUND(a.strength)::int AS strength,
               ROUND(a.won_cup*100, 1) AS "titleOdds"
        FROM team_advancement a
        JOIN teams t ON t.id = a.team_id
        WHERE t.fifa_ranking IS NOT NULL
        ORDER BY a.won_cup DESC LIMIT 16
    """)


@app.get("/api/top-scorers")
def top_scorers(tournament: str = "WC 2022", limit: int = 5):
    return _rows("""
        SELECT player, team, goals, ROUND(xg, 1) AS xg
        FROM v_top_scorers WHERE tournament_label = :t
        ORDER BY goals DESC, xg DESC LIMIT :lim
    """, {"t": tournament, "lim": limit})


# ── Bracket ──────────────────────────────────────────────────────────────────
# Fixed FIFA-2026 knockout topology: which match numbers sit in each half.
_LEFT = {"r16": [89, 90, 93, 94], "qf": [97, 98], "sf": [101]}
_RIGHT = {"r16": [91, 92, 95, 96], "qf": [99, 100], "sf": [102]}


@app.get("/api/bracket")
def bracket():
    rows = {int(r["fifa_match_num"]): r for r in _rows("""
        SELECT fifa_match_num, home_team AS home, away_team AS away, winner
        FROM predicted_bracket
    """)}

    def pick(nums):
        return [{"home": rows[n]["home"], "away": rows[n]["away"], "winner": rows[n]["winner"]}
                for n in nums if n in rows]

    half = lambda h: {"r16": pick(h["r16"]), "qf": pick(h["qf"]), "sf": pick(h["sf"])}
    fin = rows.get(104, {})
    return {
        "left": half(_LEFT),
        "right": half(_RIGHT),
        "final": {"home": fin.get("home"), "away": fin.get("away"), "winner": fin.get("winner")},
    }


# ── Standings & fixtures (for the live tab once results flow) ─────────────────
@app.get("/api/standings")
def standings():
    return _rows("""
        SELECT group_name, position, team, played, won, drawn, lost,
               goals_for, goals_against, points
        FROM v_group_standings ORDER BY group_name, position
    """)


@app.get("/api/fixtures")
def fixtures(limit: int = 12):
    return _rows("""
        SELECT fifa_match_num, home_team, away_team, venue, status,
               to_char(kickoff_utc, 'Mon DD · HH24:MI') || ' UTC' AS kickoff
        FROM v_upcoming_fixtures LIMIT :lim
    """, {"lim": limit})


# ── Single-match predictor (Poisson scoreline ⊕ LogReg blend) ────────────────
@lru_cache(maxsize=1)
def _strengths() -> dict:
    return {r["team_name"]: float(r["strength"])
            for r in _rows("SELECT team_name, strength FROM team_advancement")}


@lru_cache(maxsize=1)
def _logreg_bundle():
    """Trained match model + per-team Elo/rank/form features (cached once)."""
    from models.match_predictor import MatchPredictor, MODEL_PATH
    from scripts.predict_wc2026 import load_team_features
    return MatchPredictor.from_disk(MODEL_PATH), load_team_features()


@app.get("/api/teams")
def teams():
    return [r["name"] for r in _rows(
        "SELECT name FROM teams WHERE group_name IS NOT NULL ORDER BY name")]


def _form_deltas() -> dict:
    """Current-form Elo adjustments per team (from scripts/refresh_form.py)."""
    try:
        return {r["team_name"]: {"delta": float(r["elo_delta"] or 0),
                                 "gd_pg": r["gd_pg"], "win_rate": r["win_rate"],
                                 "matches": r["matches"]}
                for r in _rows("SELECT * FROM team_recent_form")}
    except Exception:
        return {}   # table not created yet (form never refreshed)


@app.get("/api/match-predict")
def match_predict(home: str, away: str, knockout: bool = False):
    from models.match_poisson import predict_match
    from scripts.predict_wc2026 import make_features

    strengths = _strengths()
    forms = _form_deltas()
    # Fold competition-weighted recent form into each team's strength.
    fh, fa = forms.get(home, {}), forms.get(away, {})
    sh = strengths.get(home, 1700.0) + fh.get("delta", 0.0)
    sa = strengths.get(away, 1700.0) + fa.get("delta", 0.0)

    # Optional LogReg probabilities to blend with the Poisson grid.
    logreg = None
    try:
        model, feats = _logreg_bundle()
        h, a = feats.get(home), feats.get(away)
        if h and a:
            p = model.predict_one(make_features(h, a, int(knockout)))
            logreg = {"home": p["HOME_WIN"], "draw": p["DRAW"], "away": p["AWAY_WIN"]}
    except Exception:
        pass  # model not trained / team missing → Poisson stands alone

    pred = predict_match(home, away, sh, sa, logreg_probs=logreg)
    return {**asdict(pred), "form": {
        "home": fh or None, "away": fa or None,
        "applied": bool(forms),  # True once refresh_form has run with a key
    }}
