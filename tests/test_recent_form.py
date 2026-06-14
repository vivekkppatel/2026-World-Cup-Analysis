"""
tests/test_recent_form.py
──────────────────────────
Competition-weighting + recency-decay form math (no network).
"""
from datetime import date

import pytest

from models.recent_form import (
    compute_form, competition_weight, form_to_elo_delta,
)

pytestmark = pytest.mark.unit


class TestCompetitionWeight:
    @pytest.mark.parametrize("league,expected", [
        ("FIFA World Cup", 3.0),
        ("UEFA Euro 2024", 2.5),
        ("Africa Cup of Nations", 2.5),
        ("Copa America", 2.5),
        ("UEFA Nations League", 1.8),
        ("World Cup Qualification", 1.5),
        ("International Friendlies", 0.6),
        ("Some Random Cup", 1.0),
    ])
    def test_weights(self, league, expected):
        assert competition_weight(league) == expected

    def test_none_is_default(self):
        assert competition_weight(None) == 1.0


class TestComputeForm:
    def test_empty_is_neutral(self):
        f = compute_form([], date(2026, 6, 1))
        assert f["n"] == 0 and f["win_rate"] == 0.5

    def test_basic_aggregate(self):
        ref = date(2026, 6, 1)
        matches = [
            {"gf": 3, "ga": 0, "league": "FIFA World Cup", "date": date(2026, 5, 1)},
            {"gf": 1, "ga": 1, "league": "Friendlies", "date": date(2026, 5, 15)},
        ]
        f = compute_form(matches, ref)
        assert f["n"] == 2
        # The 3-0 WC win is weighted far more than the friendly draw, so the
        # weighted goal-diff per game should be strongly positive.
        assert f["gd_pg"] > 1.5
        assert 0.5 < f["win_rate"] <= 1.0

    def test_recency_decay_favours_recent(self):
        ref = date(2026, 6, 1)
        old_win = compute_form(
            [{"gf": 5, "ga": 0, "league": "Friendlies", "date": date(2020, 1, 1)}], ref)
        new_win = compute_form(
            [{"gf": 5, "ga": 0, "league": "Friendlies", "date": date(2026, 5, 1)}], ref)
        # Same scoreline; the recent one carries more effective weight.
        assert new_win["eff_n"] > old_win["eff_n"]


class TestEloDelta:
    def test_no_matches_zero(self):
        assert form_to_elo_delta({"n": 0}) == 0.0

    def test_positive_form_positive_delta(self):
        f = {"n": 8, "gd_pg": 1.5, "eff_n": 8.0}
        assert form_to_elo_delta(f) > 0

    def test_negative_form_negative_delta(self):
        f = {"n": 8, "gd_pg": -1.5, "eff_n": 8.0}
        assert form_to_elo_delta(f) < 0

    def test_capped(self):
        f = {"n": 20, "gd_pg": 10.0, "eff_n": 20.0}
        assert form_to_elo_delta(f) <= 55.0

    def test_thin_sample_shrunk(self):
        thin = form_to_elo_delta({"n": 1, "gd_pg": 2.0, "eff_n": 0.5})
        full = form_to_elo_delta({"n": 8, "gd_pg": 2.0, "eff_n": 8.0})
        assert abs(thin) < abs(full)
