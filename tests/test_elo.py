"""
tests/test_elo.py
──────────────────
Elo rating engine: probability model, update direction, and the as-of-date
lookup that underpins leakage-free features.
"""
import pandas as pd
import pytest

from models.elo import (
    BASE_RATING, EloModel, build_from_history, blended_strength,
    fifa_rank_to_elo,
)

pytestmark = pytest.mark.unit


class TestExpectedScore:
    def test_equal_ratings_gives_even_odds(self):
        assert EloModel.expected_score(1500, 1500) == pytest.approx(0.5)

    def test_higher_rating_favoured(self):
        assert EloModel.expected_score(1700, 1500) > 0.5

    def test_probabilities_are_complementary(self):
        a = EloModel.expected_score(1650, 1480)
        b = EloModel.expected_score(1480, 1650)
        assert a + b == pytest.approx(1.0)

    def test_400_point_gap_is_about_ten_to_one(self):
        # The canonical Elo property: +400 ≈ 10:1 odds (~0.909).
        assert EloModel.expected_score(1900, 1500) == pytest.approx(0.909, abs=0.005)


class TestUpdate:
    def test_winner_gains_loser_loses(self):
        m = EloModel()
        m.update("A", "B", 2, 0, neutral=True)
        assert m.rating("A") > BASE_RATING
        assert m.rating("B") < BASE_RATING

    def test_update_is_zero_sum_on_neutral_ground(self):
        m = EloModel()
        m.update("A", "B", 1, 0, neutral=True)
        # Points one team gains, the other loses (equal priors, neutral venue).
        assert (m.rating("A") - BASE_RATING) == pytest.approx(BASE_RATING - m.rating("B"))

    def test_bigger_margin_moves_rating_more(self):
        narrow, blowout = EloModel(), EloModel()
        narrow.update("A", "B", 1, 0, neutral=True)
        blowout.update("A", "B", 5, 0, neutral=True)
        assert blowout.rating("A") > narrow.rating("A")

    def test_games_played_tracked(self):
        m = EloModel()
        m.update("A", "B", 1, 1, neutral=True)
        assert m.games_played["A"] == 1
        assert m.games_played["B"] == 1


class TestRatingAsOf:
    """The leakage-critical method: it must never see a match's own result."""

    def _model(self):
        m = EloModel()
        m.update("A", "B", 3, 0, neutral=True, date="2018-06-01")
        m.update("A", "C", 2, 1, neutral=True, date="2022-06-01")
        return m

    def test_no_history_returns_base(self):
        assert self._model().rating_as_of("Z", "2020-01-01") == BASE_RATING

    def test_date_before_first_match_returns_base(self):
        # A's rating going into its first-ever match must be the prior.
        assert self._model().rating_as_of("A", "2018-05-31") == BASE_RATING

    def test_returns_rating_strictly_before_date(self):
        m = self._model()
        # On the day of the 2022 match, A's known strength is post-2018 only.
        post_2018 = m.rating_as_of("A", "2018-06-02")
        as_of_2022 = m.rating_as_of("A", "2022-06-01")
        assert as_of_2022 == pytest.approx(post_2018)

    def test_later_date_reflects_more_history(self):
        m = self._model()
        after_all = m.rating_as_of("A", "2023-01-01")
        assert after_all > m.rating_as_of("A", "2022-06-01")


class TestBuildFromHistory:
    def test_builds_and_records_dates(self):
        df = pd.DataFrame({
            "match_date": ["2018-06-14", "2018-06-15"],
            "home_team_name": ["A", "C"], "away_team_name": ["B", "A"],
            "home_team_score": [2, 0], "away_team_score": [1, 0],
        })
        m = build_from_history(df)
        assert "A" in m.ratings
        assert m.history["A"]  # checkpoints recorded for as-of lookups

    def test_skips_rows_with_missing_scores(self):
        df = pd.DataFrame({
            "match_date": ["2018-06-14"], "home_team_name": ["A"],
            "away_team_name": ["B"], "home_team_score": [None],
            "away_team_score": [1],
        })
        m = build_from_history(df)
        assert m.ratings == {}


class TestFifaBlend:
    def test_rank_one_maps_high(self):
        assert fifa_rank_to_elo(1) > fifa_rank_to_elo(48)

    def test_blend_uses_fifa_when_no_history(self):
        m = EloModel()
        # No WC history → strength is driven entirely by FIFA rank.
        assert blended_strength("New", m, fifa_rank=1) == pytest.approx(fifa_rank_to_elo(1))

    def test_blend_caps_elo_weight(self):
        # Even with deep history, current FIFA rank keeps a permanent say.
        m = EloModel()
        for i in range(40):
            m.update("Vet", "Foe", 5, 0, neutral=True, date=f"19{50+i:02d}-01-01")
        pure_elo = m.rating("Vet")
        blended = blended_strength("Vet", m, fifa_rank=48)  # weak current rank
        assert blended < pure_elo  # rank pulls it down; not 100% Elo
