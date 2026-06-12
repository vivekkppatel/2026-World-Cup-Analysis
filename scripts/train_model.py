"""
scripts/train_model.py
───────────────────────
Train the match outcome predictor on WC 2018 + 2022 StatsBomb data.
Saves the model to models/match_predictor.pkl.

Run after seed_db.py:
    python scripts/train_model.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("═══════════════════════════════════════")
    logger.info("  World Cup 2026 — Model Training")
    logger.info("═══════════════════════════════════════")

    # ── Load training data from both WC editions ─────────────────────────────
    from data.ingest.statsbomb_loader import StatsBombLoader, COMPETITIONS

    all_data: list[pd.DataFrame] = []
    # World Cups only — Euro/Copa/AFCON entries in COMPETITIONS exist for
    # player valuation and would distort a WC-specific outcome model.
    wc_comps = {k: c for k, c in COMPETITIONS.items() if c["competition"] == "WORLD_CUP"}
    for key, comp in wc_comps.items():
        logger.info(f"Loading team stats for {key} …")
        try:
            df = StatsBombLoader.get_team_match_stats(
                competition_id=comp["competition_id"],
                season_id=comp["season_id"],
            )
            if not df.empty:
                df["source"] = key
                all_data.append(df)
                logger.info(f"  → {len(df)} team-match rows loaded.")
        except Exception as e:
            logger.warning(f"  → Skipping {key}: {e}")

    if not all_data:
        logger.error("No training data available. Check StatsBomb connection.")
        sys.exit(1)

    combined = pd.concat(all_data, ignore_index=True)
    logger.info(f"Combined training dataset: {len(combined)} rows from {len(all_data)} tournament(s).")

    # ── Train the model ───────────────────────────────────────────────────────
    from models.match_predictor import MatchPredictor

    predictor = MatchPredictor()
    results = predictor.train(combined)

    logger.info(f"Training complete:")
    logger.info(f"  Train accuracy : {results['train_accuracy']:.3f}")
    logger.info(f"  CV accuracy    : {results['cv_mean']:.3f} ± {results['cv_std']:.3f}")
    logger.info(f"  Samples        : {results['n_samples']}")

    # ── Print classification report ───────────────────────────────────────────
    report = results["classification_report"]
    logger.info("\nClassification Report:")
    for cls, metrics in report.items():
        if isinstance(metrics, dict):
            logger.info(
                f"  {cls:12s} | precision={metrics['precision']:.2f} "
                f"recall={metrics['recall']:.2f} f1={metrics['f1-score']:.2f}"
            )

    # ── Save model ────────────────────────────────────────────────────────────
    from models.match_predictor import MODEL_PATH
    predictor.save(MODEL_PATH)

    logger.info(f"\n✅ Model saved to {MODEL_PATH}")
    logger.info("Next step: streamlit run app/main.py")

    # ── CV accuracy tip for README ────────────────────────────────────────────
    cv_pct = results["cv_mean"] * 100
    logger.info(f"\nAdd to your resume bullet: '…achieving {cv_pct:.1f}% accuracy on 5-fold CV'")


if __name__ == "__main__":
    main()
