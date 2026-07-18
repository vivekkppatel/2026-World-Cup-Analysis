"""
models/match_predictor.py
──────────────────────────
Leakage-free Logistic Regression model for match outcomes
(HOME_WIN / DRAW / AWAY_WIN).

Features (all pre-match — see models/features.py for why this matters):
    elo_diff, fifa_rank_gap, form_goals_diff, form_xg_diff,
    rest_days_diff, is_knockout

This replaces an earlier version that leaked the match's own goals/xG into
its features (fake 96.9% accuracy). Real football outcome models top out
around 55–60% accuracy; the honest metrics here — log loss, Brier score,
calibration — are the interview-defensible numbers, not raw accuracy.

Interpretability is deliberate: a multinomial logistic regression lets you
explain every coefficient ("+100 Elo shifts home-win odds by X"), which beats
a black box for an analyst portfolio.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.features import FEATURE_COLUMNS, LABEL_MAP

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "match_predictor.pkl"
LABELS = ["HOME_WIN", "DRAW", "AWAY_WIN"]
MODEL_VERSION = "logreg-v2"


class MatchPredictor:
    """Multinomial logistic regression over leakage-free pre-match features."""

    def __init__(self):
        self.pipeline: Optional[Pipeline] = None
        self.feature_names: list[str] = list(FEATURE_COLUMNS)
        self.is_trained: bool = False

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self, X: pd.DataFrame, y: pd.Series) -> dict:
        """Fit the model. Returns in-sample metrics (use evaluate() for honest ones)."""
        X = X[self.feature_names].fillna(0.0)
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            # No class_weight balancing: draws are a genuine ~20% minority, and
            # up-weighting them to parity makes the model over-predict draws and
            # hurts both accuracy and calibration. Let the base rates stand.
            ("clf", LogisticRegression(
                solver="lbfgs", max_iter=2000, C=1.0, random_state=42,
            )),
        ])
        self.pipeline.fit(X, y)
        self.is_trained = True

        preds = self.pipeline.predict(X)
        train_acc = accuracy_score(y, preds)
        logger.info(f"Trained on {len(X)} matches | in-sample acc={train_acc:.3f}")
        return {"train_accuracy": train_acc, "n_samples": len(X)}

    # ── Evaluation ────────────────────────────────────────────────────────────

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict:
        """
        Honest held-out metrics. Accuracy is reported but the probabilistic
        metrics matter more for a forecasting model:
          • log_loss — penalises confident wrong calls (lower = better)
          • brier    — mean squared error of the probability vector
          • calibration — are 70%-confidence calls right ~70% of the time?
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained.")
        X = X[self.feature_names].fillna(0.0)
        proba = self.pipeline.predict_proba(X)
        preds = proba.argmax(axis=1)

        classes = list(self.pipeline.named_steps["clf"].classes_)
        ll = log_loss(y, proba, labels=classes)
        # Multiclass Brier = mean squared error vs one-hot truth
        onehot = np.zeros_like(proba)
        for i, label in enumerate(y):
            onehot[i, classes.index(label)] = 1.0
        brier = float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))

        return {
            "accuracy": accuracy_score(y, preds),
            "log_loss": ll,
            "brier": brier,
            "n_samples": len(X),
            "calibration": self._calibration_bins(proba, y, classes),
        }

    @staticmethod
    def _calibration_bins(proba: np.ndarray, y: pd.Series,
                          classes: list[int], n_bins: int = 5) -> list[dict]:
        """
        Reliability of the top predicted probability, bucketed. Each bin reports
        mean confidence vs observed hit rate — a perfectly calibrated model has
        them equal.
        """
        top_conf = proba.max(axis=1)
        top_pred = proba.argmax(axis=1)
        y_arr = np.asarray([classes.index(v) for v in y])
        hit = (top_pred == y_arr).astype(float)

        bins = np.linspace(0.0, 1.0, n_bins + 1)
        out = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            mask = (top_conf >= lo) & (top_conf < hi if hi < 1.0 else top_conf <= hi)
            if mask.sum() == 0:
                continue
            out.append({
                "bin": f"{lo:.0%}–{hi:.0%}",
                "n": int(mask.sum()),
                "mean_confidence": round(float(top_conf[mask].mean()), 3),
                "hit_rate": round(float(hit[mask].mean()), 3),
            })
        return out

    # ── Baseline for comparison ───────────────────────────────────────────────

    @staticmethod
    def baseline_accuracy(X: pd.DataFrame, y: pd.Series) -> float:
        """
        "Pick the higher-FIFA-ranked team" baseline. Positive fifa_rank_gap
        means home is better-ranked → predict HOME_WIN; negative → AWAY_WIN.
        The model has to beat this to have earned its keep.
        """
        gap = X["fifa_rank_gap"].values
        pred = np.where(gap > 0, LABEL_MAP["HOME"], LABEL_MAP["AWAY"])
        return accuracy_score(y, pred)

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_one(self, features: dict) -> dict[str, float]:
        """Predict {HOME_WIN, DRAW, AWAY_WIN} for one pre-built feature dict.

        Missing keys AND present-but-NaN/None values both fall back to 0.0 — the
        same neutral value features.py uses when a team has no history (e.g. a
        WC 2026 side with no event data yet). Without this, a NaN would make
        LogisticRegression reject the whole input.
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Run .train() or .load() first.")
        X = pd.DataFrame([{c: features.get(c, 0.0) for c in self.feature_names}])
        X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        proba = self.pipeline.predict_proba(X)[0]
        classes = list(self.pipeline.named_steps["clf"].classes_)
        # Map model class index → label name via LABEL_MAP ordering
        idx_to_label = {0: "HOME_WIN", 1: "DRAW", 2: "AWAY_WIN"}
        return {idx_to_label[c]: round(float(p), 4) for c, p in zip(classes, proba)}

    def coefficients(self) -> pd.DataFrame:
        """Standardised coefficients per class — the interpretability payoff."""
        if not self.is_trained:
            raise RuntimeError("Model not trained.")
        clf = self.pipeline.named_steps["clf"]
        idx_to_label = {0: "HOME_WIN", 1: "DRAW", 2: "AWAY_WIN"}
        return pd.DataFrame(
            clf.coef_, columns=self.feature_names,
            index=[idx_to_label[c] for c in clf.classes_],
        )

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: Path = MODEL_PATH):
        if not self.is_trained:
            raise RuntimeError("Cannot save: model not trained.")
        with open(path, "wb") as f:
            pickle.dump({"pipeline": self.pipeline, "features": self.feature_names,
                         "version": MODEL_VERSION}, f)
        logger.info(f"Model saved to {path}")

    def load(self, path: Path = MODEL_PATH):
        if not path.exists():
            raise FileNotFoundError(f"No model at {path}. Run scripts/train_model.py.")
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.pipeline = state["pipeline"]
        self.feature_names = state["features"]
        self.is_trained = True
        logger.info(f"Model loaded from {path}")

    @classmethod
    def from_disk(cls, path: Path = MODEL_PATH) -> "MatchPredictor":
        instance = cls()
        instance.load(path)
        return instance
