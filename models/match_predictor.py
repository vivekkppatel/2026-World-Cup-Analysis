"""
models/match_predictor.py
──────────────────────────
Logistic Regression model that predicts match outcomes
(HOME WIN / DRAW / AWAY WIN) trained on WC 2018 + 2022 data.

Features used:
    - FIFA ranking differential (home - away)
    - xG differential from recent matches
    - Goals scored / conceded averages
    - Tournament stage (group vs knockout)
    - Is neutral venue (always true for WC)

This is intentionally a straightforward model. Interpretability
and the ability to explain every coefficient beats a black-box.
That's a key interview talking point for analyst roles.
"""
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "match_predictor.pkl"
LABELS = ["HOME_WIN", "DRAW", "AWAY_WIN"]


class MatchPredictor:
    """
    Logistic Regression match outcome classifier.

    Example:
        predictor = MatchPredictor()
        predictor.train(training_df)
        probs = predictor.predict_proba(home_ranking=5, away_ranking=20,
                                         home_xg_avg=1.8, away_xg_avg=0.9,
                                         stage="GROUP_STAGE")
        # {'HOME_WIN': 0.61, 'DRAW': 0.21, 'AWAY_WIN': 0.18}
    """

    def __init__(self):
        self.pipeline: Optional[Pipeline] = None
        self.feature_names: list[str] = []
        self.is_trained: bool = False

    # ── Training ──────────────────────────────────────────────────────────────

    def build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform a team-match DataFrame (from StatsBombLoader.get_team_match_stats)
        into match-level feature rows suitable for training.

        Input df must have columns: match_id, team, opponent, goals_for,
        goals_against, xg, shots, is_home, stage, result
        """
        # Pivot to get home/away stats side by side
        home = df[df["is_home"]].copy()
        away = df[~df["is_home"]].copy()

        merged = home.merge(
            away,
            on="match_id",
            suffixes=("_home", "_away"),
        )

        features = pd.DataFrame({
            "xg_diff":         merged["xg_home"] - merged["xg_away"],
            "shots_diff":      merged["shots_home"] - merged["shots_away"],
            "passes_diff":     merged["passes_home"] - merged["passes_away"],
            "pressures_diff":  merged["pressures_home"] - merged["pressures_away"],
            "goals_for_home":  merged["goals_for_home"],
            "goals_for_away":  merged["goals_for_away"],
            "goals_ag_home":   merged["goals_against_home"],
            "goals_ag_away":   merged["goals_against_away"],
            # Stage strings differ by source: StatsBomb "Group Stage" vs
            # football-data.org "GROUP_STAGE". Empty/unknown counts as group.
            "is_knockout":     merged["stage_home"].apply(
                lambda s: 0 if (not s or "group" in str(s).lower()) else 1
            ),
        })

        # Target: outcome from home team perspective
        labels = merged["result_home"].map({"W": 0, "D": 1, "L": 2})

        self.feature_names = features.columns.tolist()
        return features, labels

    def train(self, df: pd.DataFrame) -> dict:
        """
        Train the model on historical match data.
        Returns a dict with accuracy and CV scores.
        """
        X, y = self.build_features(df)
        X = X.fillna(0)

        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                solver="lbfgs",
                max_iter=1000,
                C=1.0,
                class_weight="balanced",
                random_state=42,
            )),
        ])

        # 5-fold cross-validation
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(self.pipeline, X, y, cv=cv, scoring="accuracy")

        # Fit on full dataset
        self.pipeline.fit(X, y)
        self.is_trained = True

        train_preds = self.pipeline.predict(X)
        report = classification_report(y, train_preds, target_names=LABELS, output_dict=True)

        results = {
            "train_accuracy": accuracy_score(y, train_preds),
            "cv_mean":        cv_scores.mean(),
            "cv_std":         cv_scores.std(),
            "n_samples":      len(X),
            "classification_report": report,
        }
        logger.info(
            f"Model trained | train_acc={results['train_accuracy']:.3f} "
            f"| cv={results['cv_mean']:.3f} ± {results['cv_std']:.3f}"
        )
        return results

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_proba(
        self,
        xg_diff: float,
        shots_diff: float,
        passes_diff: float = 0.0,
        pressures_diff: float = 0.0,
        goals_for_home: float = 1.5,
        goals_for_away: float = 1.2,
        goals_ag_home: float = 1.0,
        goals_ag_away: float = 1.2,
        is_knockout: int = 0,
    ) -> dict[str, float]:
        """
        Predict win/draw/lose probabilities for a single match.

        xg_diff = expected_home_xg - expected_away_xg
        Returns: {'HOME_WIN': float, 'DRAW': float, 'AWAY_WIN': float}
        """
        if not self.is_trained or self.pipeline is None:
            raise RuntimeError("Model not trained. Run .train() or .load() first.")

        X = pd.DataFrame([{
            "xg_diff":        xg_diff,
            "shots_diff":     shots_diff,
            "passes_diff":    passes_diff,
            "pressures_diff": pressures_diff,
            "goals_for_home": goals_for_home,
            "goals_for_away": goals_for_away,
            "goals_ag_home":  goals_ag_home,
            "goals_ag_away":  goals_ag_away,
            "is_knockout":    is_knockout,
        }])

        probs = self.pipeline.predict_proba(X)[0]
        return {label: round(float(prob), 4) for label, prob in zip(LABELS, probs)}

    def predict_from_team_stats(
        self,
        home_stats: dict,
        away_stats: dict,
        is_knockout: bool = False,
    ) -> dict[str, float]:
        """
        Higher-level prediction from aggregated team stats dicts.
        home_stats / away_stats should contain: avg_xg, avg_shots,
        avg_passes, avg_pressures, avg_goals_for, avg_goals_against
        """
        return self.predict_proba(
            xg_diff=home_stats.get("avg_xg", 1.5) - away_stats.get("avg_xg", 1.2),
            shots_diff=home_stats.get("avg_shots", 12) - away_stats.get("avg_shots", 10),
            passes_diff=home_stats.get("avg_passes", 450) - away_stats.get("avg_passes", 400),
            pressures_diff=home_stats.get("avg_pressures", 180) - away_stats.get("avg_pressures", 160),
            goals_for_home=home_stats.get("avg_goals_for", 1.5),
            goals_for_away=away_stats.get("avg_goals_for", 1.2),
            goals_ag_home=home_stats.get("avg_goals_against", 1.0),
            goals_ag_away=away_stats.get("avg_goals_against", 1.2),
            is_knockout=int(is_knockout),
        )

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: Path = MODEL_PATH):
        """Persist model to disk."""
        if not self.is_trained:
            raise RuntimeError("Cannot save: model not trained.")
        with open(path, "wb") as f:
            pickle.dump({"pipeline": self.pipeline, "features": self.feature_names}, f)
        logger.info(f"Model saved to {path}")

    def load(self, path: Path = MODEL_PATH):
        """Load a persisted model from disk."""
        if not path.exists():
            raise FileNotFoundError(f"No model file at {path}. Run scripts/train_model.py first.")
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.pipeline = state["pipeline"]
        self.feature_names = state["features"]
        self.is_trained = True
        logger.info(f"Model loaded from {path}")

    @classmethod
    def from_disk(cls, path: Path = MODEL_PATH) -> "MatchPredictor":
        """Convenience constructor that loads from disk immediately."""
        instance = cls()
        instance.load(path)
        return instance
