"""
scripts/train_model.py
───────────────────────
Train the leakage-free match-outcome model with a STRICT TEMPORAL split:

    train  →  WC 2018 + EURO 2020   (everything before WC 2022)
    test   →  WC 2022               (genuinely out-of-sample in time)

This is the honest setup: the model is evaluated on a tournament whose matches
it never saw, the way it would face WC 2026. Reports log loss, Brier score,
calibration, and accuracy vs. a FIFA-rank baseline — not a single inflated
number.

Run (DB must be loaded — see README steps 6):
    python scripts/train_model.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

import pandas as pd
from sqlalchemy import text

from database.db import engine, health_check
from data.transform.team_aliases import canonicalize
from models.elo import build_from_history
from models.features import build_match_features
from models.match_predictor import MatchPredictor, MODEL_PATH

FJELSTUL_MATCHES = Path(__file__).parent.parent / "data" / "external" / "fjelstul" / "matches.csv"
TRAIN_TOURNAMENTS = ["WC 2018", "EURO 2020"]
TEST_TOURNAMENTS = ["WC 2022"]
# All event-level tournaments, for the leave-one-tournament-out robustness check.
ALL_TOURNAMENTS = ["WC 2018", "EURO 2020", "WC 2022",
                   "AFCON 2023", "COPA 2024", "EURO 2024"]

# Pull finished matches with per-side xG (summed from player_match_stats).
_MATCH_SQL = """
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


def load_matches(labels: list[str]) -> pd.DataFrame:
    return pd.read_sql(_MATCH_SQL, engine, params={"labels": labels})


def load_fifa_ranks() -> dict[str, int]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT name, fifa_ranking FROM teams WHERE fifa_ranking IS NOT NULL"
        )).fetchall()
    return {name: rank for name, rank in rows}


def main() -> None:
    logger.info("═══════════════════════════════════════")
    logger.info("  WC Match Predictor — Temporal Training")
    logger.info("═══════════════════════════════════════")

    if not health_check():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)
    if not FJELSTUL_MATCHES.exists():
        logger.error("Fjelstul matches.csv missing. Run scripts/fetch_external_data.py")
        sys.exit(1)

    # ── Elo backbone (as-of-date, leakage-free) ──
    history = pd.read_csv(FJELSTUL_MATCHES)
    history["home_team_name"] = history["home_team_name"].map(canonicalize)
    history["away_team_name"] = history["away_team_name"].map(canonicalize)
    elo = build_from_history(history)
    fifa_ranks = load_fifa_ranks()

    # ── Featurise ALL tournaments once (rolling form carries across them) ──
    all_raw = load_matches(ALL_TOURNAMENTS)
    if all_raw.empty:
        logger.error("No matches found. Run scripts/load_statsbomb_history.py first.")
        sys.exit(1)
    X_all, y_all, meta = build_match_features(all_raw, elo, fifa_ranks)
    tour = meta["tournament_label"]

    # ── Primary: strict temporal split (train pre-2022 → test WC 2022) ──
    train_mask = tour.isin(TRAIN_TOURNAMENTS)
    test_mask = tour.isin(TEST_TOURNAMENTS)
    X_train, y_train = X_all[train_mask], y_all[train_mask]
    X_test, y_test = X_all[test_mask], y_all[test_mask]
    logger.info(f"Train: {len(X_train)} matches ({', '.join(TRAIN_TOURNAMENTS)})")
    logger.info(f"Test:  {len(X_test)} matches ({', '.join(TEST_TOURNAMENTS)})")

    model = MatchPredictor()
    model.train(X_train, y_train)
    metrics = model.evaluate(X_test, y_test)
    baseline = MatchPredictor.baseline_accuracy(X_test, y_test)

    logger.info("── Held-out WC 2022 performance (primary, temporal) ──")
    logger.info(f"  Accuracy        : {metrics['accuracy']*100:5.1f}%")
    logger.info(f"  FIFA baseline   : {baseline*100:5.1f}%   "
                f"(edge: {(metrics['accuracy']-baseline)*100:+.1f} pts)")
    logger.info(f"  Log loss        : {metrics['log_loss']:.3f}   (lower better)")
    logger.info(f"  Brier score     : {metrics['brier']:.3f}   (lower better)")
    logger.info("  Calibration (top-confidence reliability):")
    for b in metrics["calibration"]:
        logger.info(f"    {b['bin']:>9} | n={b['n']:<3} conf={b['mean_confidence']:.2f} "
                    f"hit={b['hit_rate']:.2f}")

    logger.info("── Standardised coefficients (home-win class) ──")
    coefs = model.coefficients()
    if "HOME_WIN" in coefs.index:
        for feat, val in coefs.loc["HOME_WIN"].sort_values(key=abs, ascending=False).items():
            logger.info(f"    {feat:<16} {val:+.3f}")

    # ── Robustness: leave-one-tournament-out CV ──
    # WC 2022 alone is a small, unusually chaotic test set. Rotating each of the
    # six tournaments out as the test fold gives a stabler read on the model's
    # real edge over the baseline.
    logger.info("── Leave-one-tournament-out CV (robustness) ──")
    loto_acc, loto_base = [], []
    for held in ALL_TOURNAMENTS:
        te = tour == held
        tr = ~te
        if te.sum() == 0 or tr.sum() == 0:
            continue
        m = MatchPredictor()
        m.train(X_all[tr], y_all[tr])
        acc = m.evaluate(X_all[te], y_all[te])["accuracy"]
        base = MatchPredictor.baseline_accuracy(X_all[te], y_all[te])
        loto_acc.append(acc); loto_base.append(base)
        logger.info(f"    {held:<11} acc={acc*100:4.1f}%  baseline={base*100:4.1f}%  "
                    f"edge={ (acc-base)*100:+4.1f}")
    if loto_acc:
        mean_acc = sum(loto_acc) / len(loto_acc)
        mean_base = sum(loto_base) / len(loto_base)
        logger.info(f"    {'MEAN':<11} acc={mean_acc*100:4.1f}%  baseline={mean_base*100:4.1f}%  "
                    f"edge={(mean_acc-mean_base)*100:+4.1f}")

    # Refit on every available match so the saved model uses all data for WC 2026.
    model.train(X_all, y_all)
    model.save(MODEL_PATH)

    logger.info(f"✅ Model saved to {MODEL_PATH}")
    if loto_acc:
        edge = (mean_acc - mean_base) * 100
        logger.info(
            f"Resume bullet: 'Calibrated multinomial logistic match model "
            f"(Elo + form features); {mean_acc*100:.0f}% accuracy across 6 international "
            f"tournaments, +{edge:.0f} pts over a FIFA-rank baseline, Brier "
            f"{metrics['brier']:.2f} on a strict temporal hold-out.'")


if __name__ == "__main__":
    main()
