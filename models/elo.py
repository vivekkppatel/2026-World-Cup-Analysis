"""
models/elo.py
──────────────
Team-strength engine for the World Cup 2026 bracket simulator.

Elo ratings computed from 92 years of World Cup history (Fjelstul, 1930–2022)
give a single interpretable strength number per team. For the 48 WC 2026
qualifiers — many with thin or no WC history — Elo is blended with each
team's current FIFA ranking so first-timers aren't stuck at the 1500 default.

Quant-finance analog: Elo is a recency-weighted, self-correcting rating much
like a credit score or a momentum factor — each result updates the prior in
proportion to how surprising it was (the (actual − expected) error term),
and the K-factor is the learning rate.

Pipeline role: produces the pre-match team-strength feature the bracket
Monte Carlo consumes, and ultimately the leakage-free input for the LogReg
match model. Strength here is known BEFORE a match — no leakage.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

# ── Elo hyperparameters ───────────────────────────────────────────────────────
BASE_RATING = 1500.0      # every team's prior before any matches
K_FACTOR = 40.0           # update step; 40 is standard for international football
HOME_ADVANTAGE = 65.0     # Elo points added to the home/designated side
GOAL_DIFF_SCALING = True  # amplify K by margin of victory (blowouts move more)

# Elo→probability uses a 400-point logistic: a 400-point edge ≈ 10:1 odds.
_ELO_DIVISOR = 400.0


@dataclass
class EloModel:
    """
    Incremental Elo rating store. Feed it matches in chronological order;
    read `ratings` for the current strength of every team seen so far.
    """
    ratings: dict[str, float] = field(default_factory=dict)
    games_played: dict[str, int] = field(default_factory=dict)

    def rating(self, team: str) -> float:
        return self.ratings.get(team, BASE_RATING)

    # ── Probability model ─────────────────────────────────────────────────────

    @staticmethod
    def expected_score(rating_a: float, rating_b: float) -> float:
        """P(A beats B) on the logistic Elo curve, draws counted as half."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / _ELO_DIVISOR))

    # ── Update step ───────────────────────────────────────────────────────────

    def update(self, home: str, away: str, home_goals: int, away_goals: int,
               neutral: bool = False) -> None:
        """Apply one match result, mutating ratings in place."""
        r_home = self.rating(home)
        r_away = self.rating(away)

        adv = 0.0 if neutral else HOME_ADVANTAGE
        exp_home = self.expected_score(r_home + adv, r_away)
        exp_away = 1.0 - exp_home

        if home_goals > away_goals:
            score_home, score_away = 1.0, 0.0
        elif home_goals < away_goals:
            score_home, score_away = 0.0, 1.0
        else:
            score_home = score_away = 0.5

        k = self._effective_k(home_goals, away_goals)
        self.ratings[home] = r_home + k * (score_home - exp_home)
        self.ratings[away] = r_away + k * (score_away - exp_away)
        self.games_played[home] = self.games_played.get(home, 0) + 1
        self.games_played[away] = self.games_played.get(away, 0) + 1

    @staticmethod
    def _effective_k(home_goals: int, away_goals: int) -> float:
        """
        Scale K by goal margin (FiveThirtyEight-style): a 3-goal win shifts
        the rating more than a 1-goal win. Caps growth logarithmically so a
        7–0 doesn't dominate.
        """
        if not GOAL_DIFF_SCALING:
            return K_FACTOR
        margin = abs(home_goals - away_goals)
        return K_FACTOR * (1.0 + math.log1p(max(margin - 1, 0)))


# ── Building the model from history ───────────────────────────────────────────

def build_from_history(matches: pd.DataFrame) -> EloModel:
    """
    Build an EloModel from Fjelstul match rows (chronological).
    All World Cup matches are at neutral venues except for the host, which we
    don't special-case here — host advantage is folded into the team's
    accumulated rating over time.

    Required columns: match_date, home_team_name, away_team_name,
                      home_team_score, away_team_score.
    """
    model = EloModel()
    ordered = matches.sort_values("match_date")
    for _, m in ordered.iterrows():
        try:
            model.update(
                home=m["home_team_name"],
                away=m["away_team_name"],
                home_goals=int(m["home_team_score"]),
                away_goals=int(m["away_team_score"]),
                neutral=True,   # WC matches: treat as neutral, rating absorbs form
            )
        except (ValueError, TypeError):
            continue  # skip rows with missing scores
    logger.info(f"Elo built from {len(ordered)} matches, {len(model.ratings)} teams.")
    return model


# ── Blending Elo with FIFA ranking ────────────────────────────────────────────

# A FIFA ranking maps to an approximate Elo via a linear scale calibrated to
# the empirical WC Elo range (~1450–1850 across the 48 qualifiers): rank 1 ≈
# 1850, falling ~5.5 Elo per place so rank 35 ≈ 1660 and rank 48 ≈ 1590. The
# earlier 2050/-7 scale over-inflated mid-table teams above their real level.
_FIFA_TOP_ELO = 1850.0
_FIFA_ELO_PER_RANK = 5.5

# WC-only Elo never regresses between tournaments, so teams with deep but dated
# history (e.g. Sweden, USA) carry stale, inflated ratings. Capping the Elo
# weight keeps a permanent floor of trust in the *current* FIFA rank, which
# counters that staleness no matter how many WC games a team has played.
_MAX_ELO_WEIGHT = 0.75


def fifa_rank_to_elo(rank: int) -> float:
    """Convert a FIFA world ranking into an approximate Elo-scale strength."""
    return _FIFA_TOP_ELO - _FIFA_ELO_PER_RANK * (rank - 1)


def blended_strength(
    team: str,
    model: EloModel,
    fifa_rank: int | None,
    history_weight_full_at: int = 20,
) -> float:
    """
    Combine historical WC Elo with the current FIFA rank.

    Teams with lots of WC history lean on their Elo; teams with little or no
    history lean on FIFA rank (their only current-strength signal). The Elo
    weight ramps with games played, reaching its cap (`_MAX_ELO_WEIGHT`) at
    `history_weight_full_at` matches — never 100%, so current form always has
    a say and faded powers don't coast on old Elo.

    A team with zero WC history and no FIFA rank falls back to BASE_RATING.
    """
    elo = model.rating(team)
    games = model.games_played.get(team, 0)

    if fifa_rank is None:
        return elo  # no FIFA signal — trust whatever Elo we have

    fifa_elo = fifa_rank_to_elo(fifa_rank)
    w_elo = _MAX_ELO_WEIGHT * min(games / history_weight_full_at, 1.0)
    return w_elo * elo + (1.0 - w_elo) * fifa_elo
