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
    allow_origins=["*"],
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
        SELECT player, team, goals, COALESCE(assists, 0) AS assists,
               ROUND(xg, 1) AS xg
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


# ════════════════════════════════════════════════════════════════════════════
# Tournament Overview — match results (standings/fixtures/top-scorers above)
# ════════════════════════════════════════════════════════════════════════════
@app.get("/api/results")
def results(tournament: str = "WC 2026", limit: int = 24):
    """Finished match results for a tournament, most recent first."""
    return _rows("""
        SELECT fifa_match_num,
               to_char(kickoff_utc, 'Mon DD') AS date,
               stage, group_name, home_team, away_team, home_score, away_score
        FROM v_match_results
        WHERE tournament_label = :t
        ORDER BY kickoff_utc DESC
        LIMIT :lim
    """, {"t": tournament, "lim": limit})


# ════════════════════════════════════════════════════════════════════════════
# Team Analysis — per-match event-level stats across tournaments
# ════════════════════════════════════════════════════════════════════════════
@app.get("/api/ta/tournaments")
def ta_tournaments():
    return [r["tournament_label"] for r in _rows("""
        SELECT tournament_label, MIN(kickoff_utc) AS k
        FROM v_team_match_stats GROUP BY tournament_label ORDER BY k DESC
    """)]


@app.get("/api/ta/teams")
def ta_teams(tournament: str):
    return [r["team"] for r in _rows("""
        SELECT DISTINCT team FROM v_team_match_stats
        WHERE tournament_label = :t ORDER BY team
    """, {"t": tournament})]


@app.get("/api/ta")
def team_analysis(tournament: str, team: str):
    """Match-by-match event stats for one team in one tournament."""
    return _rows("""
        SELECT to_char(kickoff_utc, 'Mon DD') AS date, stage, opponent,
               goals_scored, goals_conceded, team_xg AS xg,
               shots, passes, pressures
        FROM v_team_match_stats
        WHERE tournament_label = :t AND team = :team
        ORDER BY kickoff_utc
    """, {"t": tournament, "team": team})


# ════════════════════════════════════════════════════════════════════════════
# Player Stats — per-90 leaderboards
# ════════════════════════════════════════════════════════════════════════════
@app.get("/api/ps/tournaments")
def ps_tournaments():
    return [r["tournament_label"] for r in _rows("""
        SELECT tournament_label, MIN(tournament_year) AS y
        FROM v_player_stats WHERE minutes > 0
        GROUP BY tournament_label ORDER BY y DESC
    """)]


@app.get("/api/ps")
def player_stats(tournament: str, min_minutes: int = 180, position: str = "All"):
    rows = _rows("""
        SELECT player, position, team, matches_played, minutes,
               goals, assists, xg, shots, key_passes, pressures, tackles,
               goals_p90, assists_p90, xg_p90, shots_p90,
               key_passes_p90, pressures_p90
        FROM v_player_stats
        WHERE tournament_label = :t AND minutes >= :mm
    """, {"t": tournament, "mm": min_minutes})
    if position and position != "All":
        rows = [r for r in rows if r.get("position") == position]
    return rows


# ════════════════════════════════════════════════════════════════════════════
# Player Valuation — Composite Player Contribution Score (CPCS)
# ════════════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=16)
def _cpcs_payload(tournament: str, min_minutes: int) -> dict:
    """Compute CPCS leaderboard + undervalued cohort from the v_player_stats
    view (no slow StatsBomb cold-download). Cached per (tournament, minutes)."""
    from models.player_rating import compute_player_ratings, get_undervalued_players

    df = pd.read_sql("""
        SELECT player AS player_name, position, team AS team_name,
               matches_played, minutes AS minutes_played,
               goals, assists, xg, shots, key_passes, pressures, tackles,
               goals_p90, assists_p90, xg_p90, shots_p90,
               key_passes_p90, pressures_p90
        FROM v_player_stats
        WHERE tournament_label = %(t)s AND minutes > 0
    """, engine, params={"t": tournament})
    if df.empty:
        return {"leaderboard": [], "undervalued": []}

    rated = compute_player_ratings(df, min_minutes=min_minutes)
    if rated.empty:
        return {"leaderboard": [], "undervalued": []}

    def _row(r) -> dict:
        return {
            "player": r["player_name"], "team": r["team_name"],
            "positionGroup": r.get("position_group", "MID"),
            "minutes": int(r["minutes_played"]),
            "cpcs": round(float(r["cpcs"]), 1),
            "goals_p90": round(float(r.get("goals_p90") or 0), 2),
            "assists_p90": round(float(r.get("assists_p90") or 0), 2),
            "xg_p90": round(float(r.get("xg_p90") or 0), 2),
            "shots_p90": round(float(r.get("shots_p90") or 0), 2),
            "key_passes_p90": round(float(r.get("key_passes_p90") or 0), 2),
            "pressures_p90": round(float(r.get("pressures_p90") or 0), 2),
        }

    leaderboard = [_row(r) for _, r in rated.head(40).iterrows()]
    uv = get_undervalued_players(rated, top_n=12)
    undervalued = []
    for _, r in uv.iterrows():
        d = _row(r)
        d["efficiency"] = round(float(r.get("efficiency_ratio") or 0), 2)
        undervalued.append(d)
    return {"leaderboard": leaderboard, "undervalued": undervalued}


@app.get("/api/pv/tournaments")
def pv_tournaments():
    return ps_tournaments()


@app.get("/api/pv")
def player_valuation(tournament: str, min_minutes: int = 90):
    return _cpcs_payload(tournament, min_minutes)


# ════════════════════════════════════════════════════════════════════════════
# Monte Carlo — advancement distribution + model scorecard
# ════════════════════════════════════════════════════════════════════════════
_KO_STAGE_ORDER = ["LAST_32", "LAST_16", "QUARTER_FINALS",
                   "SEMI_FINALS", "THIRD_PLACE", "FINAL"]
_STAGE_LABEL = {"LAST_32": "Round of 32", "LAST_16": "Round of 16",
                "QUARTER_FINALS": "Quarter-finals", "SEMI_FINALS": "Semi-finals",
                "THIRD_PLACE": "Third place", "FINAL": "Final"}
_N_SIMS = 10000  # matches scripts/run_bracket_sim.py --sims default


@app.get("/api/monte-carlo")
def monte_carlo():
    """The 10k-run Monte Carlo output: advancement probabilities per team,
    plus the live model scorecard. Read straight from the stored sim tables."""
    adv = _rows("""
        SELECT team, group_name AS "group", fifa_rank AS "fifaRank",
               ROUND(strength)::int AS strength,
               ROUND(reached_r32*100, 1)   AS r32,
               ROUND(reached_r16*100, 1)   AS r16,
               ROUND(reached_qf*100, 1)    AS qf,
               ROUND(reached_sf*100, 1)    AS sf,
               ROUND(reached_final*100, 1) AS final,
               ROUND(won_cup*100, 1)       AS champion,
               model_version AS "modelVersion"
        FROM v_bracket_predictions
        ORDER BY won_cup DESC
    """)

    sc = _rows("""
        SELECT stage, hit, brier, predicted_confidence AS conf
        FROM v_model_scorecard
    """)
    scorecard = {"scored": len(sc), "hitRate": None, "brier": None,
                 "avgConf": None, "byStage": []}
    if sc:
        scorecard["hitRate"] = round(sum(r["hit"] for r in sc) / len(sc) * 100, 1)
        scorecard["brier"] = round(sum(r["brier"] for r in sc) / len(sc), 3)
        scorecard["avgConf"] = round(sum(r["conf"] for r in sc) / len(sc) * 100, 1)
        for stage in _KO_STAGE_ORDER:
            grp = [r for r in sc if r["stage"] == stage]
            if grp:
                scorecard["byStage"].append({
                    "round": _STAGE_LABEL[stage], "matches": len(grp),
                    "hitRate": round(sum(r["hit"] for r in grp) / len(grp) * 100, 1),
                    "brier": round(sum(r["brier"] for r in grp) / len(grp), 3),
                })

    model_version = adv[0]["modelVersion"] if adv else None
    return {"advancement": adv, "scorecard": scorecard,
            "nSims": _N_SIMS, "modelVersion": model_version,
            "champion": adv[0]["team"] if adv else None}


# ════════════════════════════════════════════════════════════════════════════
# Regression Analysis — coefficients, calibration, cross-validation
# ════════════════════════════════════════════════════════════════════════════
_REG_ALL = ["WC 2018", "EURO 2020", "WC 2022", "AFCON 2023", "COPA 2024", "EURO 2024"]
_REG_TRAIN = ["WC 2018", "EURO 2020"]
_REG_TEST = ["WC 2022"]
_REG_CLASS_LABELS = ["HOME_WIN", "DRAW", "AWAY_WIN"]

_REG_MATCH_SQL = """
    SELECT m.kickoff_utc, m.stage, m.winner, m.tournament_label,
           th.name AS home_team, ta.name AS away_team,
           m.home_score, m.away_score,
           xh.team_xg AS team_xg_home, xa.team_xg AS team_xg_away
    FROM matches m
    JOIN teams th ON th.id = m.home_team_id
    JOIN teams ta ON ta.id = m.away_team_id
    LEFT JOIN (SELECT match_id, team_id, SUM(xg) AS team_xg
               FROM player_match_stats GROUP BY match_id, team_id) xh
           ON xh.match_id = m.id AND xh.team_id = m.home_team_id
    LEFT JOIN (SELECT match_id, team_id, SUM(xg) AS team_xg
               FROM player_match_stats GROUP BY match_id, team_id) xa
           ON xa.match_id = m.id AND xa.team_id = m.away_team_id
    WHERE m.tournament_label = ANY(%(labels)s)
      AND m.status = 'FINISHED' AND m.winner IS NOT NULL
    ORDER BY m.kickoff_utc
"""


@lru_cache(maxsize=1)
def _regression_payload() -> dict:
    """Train the leakage-free LogReg with a strict temporal split and return a
    full statistical report (coefficients, odds ratios, calibration, LOTO-CV,
    confusion matrix, feature correlations). Cached once per process."""
    import numpy as np
    from pathlib import Path as _Path
    from sklearn.metrics import confusion_matrix, classification_report
    from data.transform.team_aliases import canonicalize
    from models.elo import build_from_history
    from models.features import build_match_features, FEATURE_COLUMNS
    from models.match_predictor import MatchPredictor, MODEL_VERSION

    fjelstul = _Path(__file__).parent.parent / "data" / "external" / "fjelstul" / "matches.csv"
    matches = pd.read_sql(_REG_MATCH_SQL, engine, params={"labels": _REG_ALL})
    if matches.empty:
        return {"available": False}

    with engine.connect() as conn:
        fifa_ranks = {n: r for n, r in conn.execute(text(
            "SELECT name, fifa_ranking FROM teams WHERE fifa_ranking IS NOT NULL"
        )).fetchall()}

    history = pd.read_csv(fjelstul)
    history["home_team_name"] = history["home_team_name"].map(canonicalize)
    history["away_team_name"] = history["away_team_name"].map(canonicalize)
    elo = build_from_history(history)

    X_all, y_all, meta = build_match_features(matches, elo, fifa_ranks)
    tour = meta["tournament_label"]
    tr, te = tour.isin(_REG_TRAIN), tour.isin(_REG_TEST)
    X_train, y_train, X_test, y_test = X_all[tr], y_all[tr], X_all[te], y_all[te]

    model = MatchPredictor()
    model.train(X_train, y_train)
    metrics = model.evaluate(X_test, y_test)
    baseline = MatchPredictor.baseline_accuracy(X_test, y_test)

    clf = model.pipeline.named_steps["clf"]
    idx_to_label = {0: "HOME_WIN", 1: "DRAW", 2: "AWAY_WIN"}
    classes = [idx_to_label[c] for c in clf.classes_]
    coef = clf.coef_.tolist()
    odds = np.exp(clf.coef_).round(4).tolist()
    importance = np.abs(clf.coef_).mean(axis=0)
    importance_rows = sorted(
        [{"feature": f, "value": round(float(v), 4)}
         for f, v in zip(FEATURE_COLUMNS, importance)],
        key=lambda d: d["value"], reverse=True)

    X_test_f = X_test[FEATURE_COLUMNS].fillna(0.0)
    proba = model.pipeline.predict_proba(X_test_f)
    y_pred = model.pipeline.predict(X_test_f)
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2]).tolist()
    report = classification_report(y_test, y_pred, target_names=_REG_CLASS_LABELS,
                                   output_dict=True, zero_division=0)
    class_report = [{
        "label": lbl, "precision": round(report[lbl]["precision"], 2),
        "recall": round(report[lbl]["recall"], 2),
        "f1": round(report[lbl]["f1-score"], 2),
        "support": int(report[lbl]["support"]),
    } for lbl in _REG_CLASS_LABELS]

    # Calibration (top-prediction confidence vs hit rate)
    top_conf = proba.max(axis=1)
    top_pred = proba.argmax(axis=1)
    y_arr = np.asarray(y_test)
    hits = (top_pred == y_arr).astype(float)
    calibration = []
    edges = np.linspace(0.0, 1.0, 9)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (top_conf >= lo) & (top_conf < (hi if hi < 1.0 else hi + 0.01))
        if mask.sum():
            calibration.append({"conf": round(float(top_conf[mask].mean()), 3),
                                "hit": round(float(hits[mask].mean()), 3),
                                "n": int(mask.sum())})

    # Leave-one-tournament-out CV
    loto = []
    for held in _REG_ALL:
        te_m = tour == held
        tr_m = ~te_m
        if te_m.sum() == 0 or tr_m.sum() == 0:
            continue
        m = MatchPredictor()
        m.train(X_all[tr_m], y_all[tr_m])
        ev = m.evaluate(X_all[te_m], y_all[te_m])
        base = MatchPredictor.baseline_accuracy(X_all[te_m], y_all[te_m])
        loto.append({"tournament": held, "matches": int(te_m.sum()),
                     "accuracy": round(ev["accuracy"], 4),
                     "baseline": round(base, 4),
                     "edge": round(ev["accuracy"] - base, 4),
                     "logLoss": round(ev["log_loss"], 3),
                     "brier": round(ev["brier"], 3)})

    corr = X_all[FEATURE_COLUMNS].corr().round(3).values.tolist()

    return {
        "available": True,
        "modelVersion": MODEL_VERSION,
        "features": list(FEATURE_COLUMNS),
        "classes": classes,
        "coefficients": coef,
        "oddsRatios": odds,
        "importance": importance_rows,
        "confusion": {"labels": _REG_CLASS_LABELS, "matrix": cm},
        "classReport": class_report,
        "calibration": calibration,
        "distribution": [[round(float(p), 4) for p in row] for row in proba.tolist()],
        "loto": loto,
        "correlation": {"features": list(FEATURE_COLUMNS), "matrix": corr},
        "metrics": {
            "accuracy": round(metrics["accuracy"], 4),
            "logLoss": round(metrics["log_loss"], 3),
            "brier": round(metrics["brier"], 3),
            "baseline": round(baseline, 4),
            "nTrain": int(tr.sum()), "nTest": int(te.sum()),
            "trainTournaments": _REG_TRAIN, "testTournaments": _REG_TEST,
        },
    }


@app.get("/api/regression")
def regression():
    try:
        return _regression_payload()
    except Exception as e:
        return {"available": False, "error": str(e)}
