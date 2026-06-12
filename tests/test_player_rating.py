"""
tests/test_player_rating.py
────────────────────────────
Position classification (regression test for the StatsBomb-string bug) and
the CPCS computation.
"""
import pandas as pd
import pytest

from models.player_rating import _get_position_group, compute_player_ratings

pytestmark = pytest.mark.unit


class TestPositionGroup:
    @pytest.mark.parametrize("position,expected", [
        # The real StatsBomb strings that the old exact-set match missed.
        ("Center Back", "DEF"),
        ("Left Center Back", "DEF"),
        ("Right Center Back", "DEF"),
        ("Left Back", "DEF"),
        ("Left Wing Back", "DEF"),     # 'back' must win over 'wing'
        ("Right Wing Back", "DEF"),
        ("Center Midfield", "MID"),
        ("Center Defensive Midfield", "MID"),
        ("Center Attacking Midfield", "MID"),
        ("Left Midfield", "MID"),
        ("Center Forward", "FWD"),
        ("Left Center Forward", "FWD"),
        ("Left Wing", "FWD"),
        ("Right Wing", "FWD"),
        ("Secondary Striker", "FWD"),
        ("Goalkeeper", "GK"),
    ])
    def test_statsbomb_strings(self, position, expected):
        assert _get_position_group(position) == expected

    @pytest.mark.parametrize("abbrev,expected", [
        ("GK", "GK"), ("CB", "DEF"), ("LWB", "DEF"),
        ("CM", "MID"), ("CDM", "MID"), ("ST", "FWD"), ("RW", "FWD"),
    ])
    def test_abbreviations(self, abbrev, expected):
        assert _get_position_group(abbrev) == expected

    def test_unknown_defaults_to_mid_not_fwd(self):
        # The old default was FWD, which inflated unclassified players with
        # goal-heavy weights. MID is the neutral choice.
        assert _get_position_group("Substitute") == "MID"
        assert _get_position_group("") == "MID"
        assert _get_position_group(None) == "MID"

    def test_case_insensitive(self):
        assert _get_position_group("center back") == "DEF"
        assert _get_position_group("CENTER FORWARD") == "FWD"


class TestComputePlayerRatings:
    def _players(self) -> pd.DataFrame:
        return pd.DataFrame({
            "player_name": ["Striker", "Defender", "Mid", "Keeper"],
            "team_name": ["X"] * 4,
            "position": ["Center Forward", "Center Back",
                         "Center Midfield", "Goalkeeper"],
            "minutes_played": [450, 480, 500, 540],
            "goals_p90": [0.8, 0.05, 0.2, 0.0],
            "assists_p90": [0.3, 0.05, 0.3, 0.0],
            "xg_p90": [0.7, 0.05, 0.15, 0.0],
            "xa_p90": [0.2, 0.0, 0.2, 0.0],
            "key_passes_p90": [1.2, 0.4, 1.5, 0.1],
            "pressures_p90": [12, 16, 20, 2],
            "progressive_carries_p90": [0, 0, 0, 0],
            "progressive_passes_p90": [0, 0, 0, 0],
            "shots_p90": [3, 0.5, 1, 0],
            "tackles": [2, 9, 10, 1],
        })

    def test_assigns_diverse_position_groups(self):
        rated = compute_player_ratings(self._players(), min_minutes=90)
        assert set(rated["position_group"]) == {"FWD", "DEF", "MID", "GK"}

    def test_cpcs_scaled_0_to_100(self):
        rated = compute_player_ratings(self._players(), min_minutes=90)
        assert rated["cpcs"].max() == pytest.approx(100.0)
        assert (rated["cpcs"] >= 0).all()

    def test_min_minutes_filter(self):
        rated = compute_player_ratings(self._players(), min_minutes=490)
        assert len(rated) == 2  # only the 500 and 540 minute players

    def test_empty_after_filter_returns_empty(self):
        rated = compute_player_ratings(self._players(), min_minutes=9999)
        assert rated.empty
