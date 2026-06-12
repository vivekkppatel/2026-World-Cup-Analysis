"""
tests/test_features.py
───────────────────────
The leakage-safety contract. These tests encode the property the original
model violated (it fed a match's own goals/xG into its features → fake 96.9%).
If any feature ever starts depending on the match it's describing, a test here
should fail.
"""
import pandas as pd
import pytest

from models.elo import EloModel
from models.features import FEATURE_COLUMNS, LABEL_MAP, build_match_features

pytestmark = pytest.mark.unit


def _matches() -> pd.DataFrame:
    """Three chronological matches for a small team set."""
    return pd.DataFrame({
        "kickoff_utc": ["2022-06-01", "2022-06-05", "2022-06-10"],
        "home_team": ["A", "A", "B"],
        "away_team": ["B", "C", "C"],
        "home_score": [3, 1, 0],
        "away_score": [0, 1, 2],
        "stage": ["Group Stage", "Group Stage", "Round of 16"],
        "winner": ["HOME", "DRAW", "AWAY"],
        "team_xg_home": [2.5, 1.1, 0.4],
        "team_xg_away": [0.6, 1.0, 1.8],
        "tournament_label": ["WC 2022"] * 3,
    })


def _elo() -> EloModel:
    return EloModel()  # empty — isolates the form/label logic from Elo history


class TestShape:
    def test_returns_expected_columns(self):
        X, y, meta = build_match_features(_matches(), _elo(), {})
        assert list(X.columns) == FEATURE_COLUMNS
        assert len(X) == len(y) == len(meta) == 3

    def test_labels_map_correctly(self):
        _, y, _ = build_match_features(_matches(), _elo(), {})
        assert list(y) == [LABEL_MAP["HOME"], LABEL_MAP["DRAW"], LABEL_MAP["AWAY"]]

    def test_meta_carries_tournament_and_teams(self):
        _, _, meta = build_match_features(_matches(), _elo(), {})
        assert set(meta["tournament_label"]) == {"WC 2022"}
        assert meta.iloc[0]["home_team"] == "A"


class TestLeakageSafety:
    def test_first_match_has_zero_form(self):
        # Before any match is played, every team's rolling form is neutral (0).
        X, _, _ = build_match_features(_matches(), _elo(), {})
        assert X.iloc[0]["form_goals_diff"] == 0.0
        assert X.iloc[0]["form_xg_diff"] == 0.0

    def test_form_reflects_only_prior_matches(self):
        # Match 2 (A vs C) is A's second game. A's form should reflect ONLY
        # match 1 (A won 3-0 → +3 goal diff), never match 2's own 1-1 result.
        X, _, _ = build_match_features(_matches(), _elo(), {})
        # A entered match 2 with +3 form; C has no prior games (0).
        assert X.iloc[1]["form_goals_diff"] == pytest.approx(3.0)

    def test_changing_a_matchs_own_score_does_not_change_its_features(self):
        # The definitive leakage test: rewrite a match's scoreline and confirm
        # ITS OWN feature row is unchanged (features must come from the past).
        base = _matches()
        X_before, _, _ = build_match_features(base, _elo(), {})

        tampered = base.copy()
        tampered.loc[1, ["home_score", "away_score", "team_xg_home",
                         "team_xg_away", "winner"]] = [9, 0, 8.0, 0.1, "HOME"]
        X_after, _, _ = build_match_features(tampered, _elo(), {})

        # Row 1's features must be identical — they depend only on match 0.
        pd.testing.assert_series_equal(
            X_before.iloc[1], X_after.iloc[1], check_names=False)

    def test_tampering_later_match_leaves_earlier_features_intact(self):
        base = _matches()
        X_before, _, _ = build_match_features(base, _elo(), {})
        tampered = base.copy()
        tampered.loc[2, "home_score"] = 7  # change the LAST match
        X_after, _, _ = build_match_features(tampered, _elo(), {})
        pd.testing.assert_frame_equal(X_before.iloc[:2], X_after.iloc[:2])


class TestFeatureValues:
    def test_elo_diff_uses_as_of_date(self):
        elo = EloModel()
        elo.update("A", "B", 5, 0, neutral=True, date="2021-01-01")  # A strong pre-tournament
        X, _, _ = build_match_features(_matches(), elo, {})
        assert X.iloc[0]["elo_diff"] > 0  # A favoured over B

    def test_fifa_rank_gap_positive_when_home_higher_ranked(self):
        X, _, _ = build_match_features(_matches(), _elo(), {"A": 5, "B": 30})
        assert X.iloc[0]["fifa_rank_gap"] == pytest.approx(25.0)  # 30 - 5

    def test_knockout_flag_set(self):
        X, _, _ = build_match_features(_matches(), _elo(), {})
        assert X.iloc[0]["is_knockout"] == 0   # Group Stage
        assert X.iloc[2]["is_knockout"] == 1   # Round of 16
