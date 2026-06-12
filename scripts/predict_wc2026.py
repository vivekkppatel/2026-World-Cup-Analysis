"""
scripts/predict_wc2026.py
──────────────────────────
Use the trained match model to predict every WC 2026 match whose teams are
known (all 72 group games now; knockout games as they resolve), and store the
predictions so v_model_scorecard grades the model against reality as results
land.

Re-run alongside scripts/refresh_live.py — it's an upsert keyed on match_id,
so finished matches keep their prediction and newly-resolved knockout fixtures
get predicted once their teams are set.

Run:
    python scripts/predict_wc2026.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

import pandas as pd
from sqlalchemy import text

from database.db import engine, get_session, health_check
from data.transform.team_aliases import canonicalize
from models.elo import build_from_history
from models.match_predictor import MatchPredictor, MODEL_PATH, MODEL_VERSION

FJELSTUL = Path(__file__).parent.parent / "data" / "external" / "fjelstul" / "matches.csv"

# Map the model's HOME/DRAW/AWAY label to the predictions table's winner code.
_PRED_LABEL = {"HOME_WIN": "HOME", "DRAW": "DRAW", "AWAY_WIN": "AWAY"}


def load_team_features() -> dict[str, dict]:
    """Current Elo, FIFA rank, and recent-form proxy per WC 2026 team."""
    df = pd.read_csv(FJELSTUL)
    df["home_team_name"] = df["home_team_name"].map(canonicalize)
    df["away_team_name"] = df["away_team_name"].map(canonicalize)
    elo = build_from_history(df)

    meta = pd.read_sql("""
        SELECT t.name AS team, t.fifa_ranking,
               AVG(s.goals_scored - s.goals_conceded) AS form_goals,
               AVG(s.team_xg) AS avg_xg
        FROM teams t
        LEFT JOIN v_team_match_stats s ON s.team = t.name
        WHERE t.group_name IS NOT NULL
        GROUP BY t.name, t.fifa_ranking
    """, engine)

    out: dict[str, dict] = {}
    for _, r in meta.iterrows():
        out[r["team"]] = {
            "elo": elo.rating(r["team"]),
            "rank": int(r["fifa_ranking"]) if pd.notna(r["fifa_ranking"]) else 50,
            "form_goals": float(r["form_goals"]) if pd.notna(r["form_goals"]) else 0.0,
            "avg_xg": float(r["avg_xg"]) if pd.notna(r["avg_xg"]) else 1.3,
        }
    return out


def make_features(home: dict, away: dict, is_knockout: int) -> dict:
    return {
        "elo_diff": home["elo"] - away["elo"],
        "fifa_rank_gap": float(away["rank"] - home["rank"]),
        "form_goals_diff": home["form_goals"] - away["form_goals"],
        "form_xg_diff": home["avg_xg"] - away["avg_xg"],
        "rest_days_diff": 0.0,
        "is_knockout": is_knockout,
    }


def main() -> None:
    logger.info("═══════════════════════════════════════")
    logger.info("  WC 2026 — Model Predictions")
    logger.info("═══════════════════════════════════════")

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    try:
        model = MatchPredictor.from_disk(MODEL_PATH)
    except FileNotFoundError:
        logger.error("No trained model. Run scripts/train_model.py first.")
        sys.exit(1)

    feats = load_team_features()

    # Matches with both teams known (NULL team_id = unresolved knockout slot).
    fixtures = pd.read_sql("""
        SELECT m.id AS match_id, m.stage,
               th.name AS home_team, ta.name AS away_team
        FROM matches m
        JOIN teams th ON th.id = m.home_team_id
        JOIN teams ta ON ta.id = m.away_team_id
        WHERE m.tournament_label = 'WC 2026'
        ORDER BY m.fifa_match_num
    """, engine)

    written = 0
    with get_session() as session:
        for _, fx in fixtures.iterrows():
            h, a = feats.get(fx["home_team"]), feats.get(fx["away_team"])
            if h is None or a is None:
                continue
            is_ko = 0 if "group" in str(fx["stage"]).lower() else 1
            probs = model.predict_one(make_features(h, a, is_ko))
            pick = max(probs, key=probs.get)
            session.execute(text("""
                INSERT INTO predictions (match_id, home_win_prob, draw_prob,
                                         away_win_prob, predicted_winner, model_version)
                VALUES (:mid, :hw, :dw, :aw, :pw, :mv)
                ON CONFLICT (match_id) DO UPDATE SET
                    home_win_prob = EXCLUDED.home_win_prob,
                    draw_prob     = EXCLUDED.draw_prob,
                    away_win_prob = EXCLUDED.away_win_prob,
                    predicted_winner = EXCLUDED.predicted_winner,
                    model_version = EXCLUDED.model_version,
                    created_at = NOW()
            """), {"mid": int(fx["match_id"]), "hw": probs["HOME_WIN"],
                   "dw": probs["DRAW"], "aw": probs["AWAY_WIN"],
                   "pw": _PRED_LABEL[pick], "mv": MODEL_VERSION})
            written += 1

    logger.info(f"Predicted {written} WC 2026 matches with known teams.")
    logger.info("✅ v_model_scorecard will grade these as results finish.")


if __name__ == "__main__":
    main()
