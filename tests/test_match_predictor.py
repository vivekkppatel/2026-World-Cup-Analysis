"""
tests/test_match_predictor.py
──────────────────────────────
The match model's mechanics: train/evaluate/predict/persist round-trip and
the honest-metrics surface. Uses synthetic separable data so behaviour is
predictable without the database.
"""
import numpy as np
import pandas as pd
import pytest

from models.features import FEATURE_COLUMNS
from models.match_predictor import MatchPredictor

pytestmark = pytest.mark.unit


def _separable_data(n: int = 180):
    """
    Synthetic matches where a positive elo_diff strongly implies a home win —
    enough signal for the model to learn something testable.
    """
    rng = np.random.default_rng(0)
    elo = rng.normal(0, 200, n)
    rows, labels = [], []
    for e in elo:
        rows.append({
            "elo_diff": e,
            "fifa_rank_gap": e / 10,
            "form_goals_diff": rng.normal(e / 200, 1),
            "form_xg_diff": rng.normal(e / 300, 1),
            "rest_days_diff": rng.integers(-2, 3),
            "is_knockout": rng.integers(0, 2),
        })
        # Strong edge → decisive; otherwise a draw-ish middle.
        labels.append(0 if e > 80 else (2 if e < -80 else 1))
    return pd.DataFrame(rows)[FEATURE_COLUMNS], pd.Series(labels)


class TestTrainPredict:
    def test_train_sets_flag(self):
        X, y = _separable_data()
        m = MatchPredictor()
        m.train(X, y)
        assert m.is_trained

    def test_predict_one_returns_normalised_probs(self):
        X, y = _separable_data()
        m = MatchPredictor()
        m.train(X, y)
        probs = m.predict_one({"elo_diff": 300, "fifa_rank_gap": 30})
        assert set(probs) == {"HOME_WIN", "DRAW", "AWAY_WIN"}
        assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)

    def test_strong_home_edge_favours_home(self):
        X, y = _separable_data()
        m = MatchPredictor()
        m.train(X, y)
        probs = m.predict_one({"elo_diff": 400, "fifa_rank_gap": 40,
                               "form_goals_diff": 2})
        assert probs["HOME_WIN"] == max(probs.values())

    def test_predict_before_train_raises(self):
        with pytest.raises(RuntimeError):
            MatchPredictor().predict_one({"elo_diff": 0})


class TestEvaluate:
    def test_metrics_present_and_bounded(self):
        X, y = _separable_data()
        m = MatchPredictor()
        m.train(X, y)
        metrics = m.evaluate(X, y)
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert metrics["log_loss"] > 0
        assert 0.0 <= metrics["brier"] <= 2.0  # multiclass Brier upper bound
        assert isinstance(metrics["calibration"], list)

    def test_baseline_is_a_probability(self):
        X, y = _separable_data()
        assert 0.0 <= MatchPredictor.baseline_accuracy(X, y) <= 1.0

    def test_coefficients_shape(self):
        X, y = _separable_data()
        m = MatchPredictor()
        m.train(X, y)
        coefs = m.coefficients()
        assert list(coefs.columns) == FEATURE_COLUMNS


class TestPersistence:
    def test_save_load_round_trip(self, tmp_path):
        X, y = _separable_data()
        m = MatchPredictor()
        m.train(X, y)
        path = tmp_path / "model.pkl"
        m.save(path)

        loaded = MatchPredictor.from_disk(path)
        f = {"elo_diff": 250, "fifa_rank_gap": 25}
        assert loaded.predict_one(f) == m.predict_one(f)

    def test_save_untrained_raises(self, tmp_path):
        with pytest.raises(RuntimeError):
            MatchPredictor().save(tmp_path / "x.pkl")

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            MatchPredictor().load(tmp_path / "nope.pkl")
