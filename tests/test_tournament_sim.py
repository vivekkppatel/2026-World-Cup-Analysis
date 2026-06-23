"""
tests/test_tournament_sim.py
─────────────────────────────
The Monte Carlo simulator: deterministic-with-seed reproducibility, match
outcome sanity, and knockout-placeholder resolution.
"""
import numpy as np
import pytest

from models.tournament_sim import (
    BracketStructure, GroupTeam, TournamentSimulator, simulate_match,
)

pytestmark = pytest.mark.unit


class TestSimulateMatch:
    def test_stronger_team_scores_more_on_average(self):
        rng = np.random.default_rng(0)
        strong_goals = 0
        for _ in range(400):
            ga, gb = simulate_match(1900, 1400, rng)
            strong_goals += ga - gb
        assert strong_goals > 0  # the 1900 side outscores over many trials

    def test_knockout_never_returns_a_draw(self):
        rng = np.random.default_rng(1)
        for _ in range(200):
            ga, gb = simulate_match(1500, 1500, rng, allow_draw=False)
            assert ga != gb

    def test_group_match_can_draw(self):
        rng = np.random.default_rng(2)
        draws = sum(1 for _ in range(200)
                    if (lambda r: r[0] == r[1])(simulate_match(1500, 1500, rng)))
        assert draws > 0


def _two_group_structure() -> tuple[dict, BracketStructure]:
    """Two 2-team groups feeding a single final (winner A vs winner B)."""
    groups = {
        "A": [GroupTeam("A1", 1800), GroupTeam("A2", 1500)],
        "B": [GroupTeam("B1", 1700), GroupTeam("B2", 1400)],
    }
    structure = BracketStructure(
        matches={99: ("FINAL", "1A", "1B")}, group_letters=["A", "B"])
    return groups, structure


class TestDeterminism:
    def test_same_seed_same_result(self):
        groups, structure = _two_group_structure()
        r1 = TournamentSimulator(groups, structure).run(200, seed=42)
        r2 = TournamentSimulator(groups, structure).run(200, seed=42)
        assert r1.advancement_table() == r2.advancement_table()

    def test_different_seed_can_differ(self):
        groups, structure = _two_group_structure()
        r1 = TournamentSimulator(groups, structure).run(200, seed=1)
        r2 = TournamentSimulator(groups, structure).run(200, seed=2)
        # Champion probabilities shouldn't be byte-identical across seeds.
        champ1 = {r["team"]: r["won_cup"] for r in r1.advancement_table()}
        champ2 = {r["team"]: r["won_cup"] for r in r2.advancement_table()}
        assert champ1 != champ2


class TestBracketResolution:
    def test_group_winner_reaches_final(self):
        groups, structure = _two_group_structure()
        result = TournamentSimulator(groups, structure).run(300, seed=7)
        table = {r["team"]: r for r in result.advancement_table()}
        # The strongest team (A1) should win the cup most often.
        champ = max(table.values(), key=lambda r: r["won_cup"])
        assert champ["team"] == "A1"

    def test_advancement_probabilities_are_valid(self):
        groups, structure = _two_group_structure()
        result = TournamentSimulator(groups, structure).run(200, seed=3)
        for row in result.advancement_table():
            assert 0.0 <= row["won_cup"] <= 1.0
            # Reaching the final is at least as likely as winning it.
            assert row["reached_final"] >= row["won_cup"]

    def test_champion_probabilities_sum_to_one(self):
        groups, structure = _two_group_structure()
        result = TournamentSimulator(groups, structure).run(300, seed=5)
        total = sum(r["won_cup"] for r in result.advancement_table())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_handles_null_placeholder(self):
        groups = {
            "A": [GroupTeam("A1", 1800), GroupTeam("A2", 1500), GroupTeam("A3", 1450)],
            "B": [GroupTeam("B1", 1700), GroupTeam("B2", 1400), GroupTeam("B3", 1350)],
        }
        structure = BracketStructure(
            matches={
                73: ("LAST_32", None, "1A"),
                74: ("LAST_32", "1A", "1B"),
                75: ("LAST_32", "1A", None),
                76: ("LAST_32", None, None),
                104: ("FINAL", "W74", "1B"),
            },
            group_letters=["A", "B"],
        )
        sim = TournamentSimulator(groups, structure)
        one_run = sim.run_once(np.random.default_rng(7))
        assert 73 not in one_run["slots"]
        assert 75 not in one_run["slots"]
        assert 76 not in one_run["slots"]
        assert 74 in one_run["slots"]

        result = sim.run(10, seed=7)
        table = result.advancement_table()
        assert isinstance(table, list)
        assert table
        assert {"A1", "A2", "A3", "B1", "B2", "B3"}.issubset({r["team"] for r in table})
