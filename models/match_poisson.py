"""
models/match_poisson.py
────────────────────────
Single-match prediction: a Poisson scoreline model blended with the project's
logistic-regression win model — adapted from the approach in the reference
notebooks (Brazil-vs-Morocco style), but driven by our calibrated team
strengths instead of re-fetching raw goal averages.

Pipeline for one matchup:
  1. Expected goals for each side from the Elo-strength gap (same mapping the
     tournament simulator uses, so a single match and the bracket agree).
  2. A Poisson scoreline grid P(i,j) = Pois(i|λ_home)·Pois(j|λ_away).
  3. Aggregate the grid into Win / Draw / Loss + the most likely scorelines.
  4. (Optional) blend 50/50 with the trained LogReg's win probabilities.

Why Poisson: goals are rare, roughly independent events over 90 minutes, so a
Poisson with mean λ models them well (mean ≈ variance — verified in the EDA
notebook). It's the standard scoreline model in football analytics.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson

from models.tournament_sim import _lambdas

MAX_GOALS = 8  # scoreline grid is (MAX_GOALS × MAX_GOALS)


@dataclass
class MatchPrediction:
    home: str
    away: str
    exp_home_goals: float
    exp_away_goals: float
    home_win: float
    draw: float
    away_win: float
    top_scorelines: list[dict]          # [{score: '2-1', prob: 0.08}, ...]
    grid: list[list[float]]             # MAX_GOALS×MAX_GOALS heatmap
    components: dict                    # {'poisson': {...}, 'logreg': {... or None}}


def expected_goals(strength_home: float, strength_away: float,
                   home_adv: float = 0.0) -> tuple[float, float]:
    """Expected goals for each side from the Elo-strength difference."""
    lam_h, lam_a = _lambdas(strength_home, strength_away, home_adv)
    return max(lam_h, 0.15), max(lam_a, 0.15)


def scoreline_grid(lam_home: float, lam_away: float,
                   max_goals: int = MAX_GOALS) -> np.ndarray:
    """Joint probability of every scoreline up to max_goals−1 each."""
    h = poisson.pmf(np.arange(max_goals), lam_home)
    a = poisson.pmf(np.arange(max_goals), lam_away)
    return np.outer(h, a)  # grid[i, j] = P(home i, away j)


def _outcomes(grid: np.ndarray) -> tuple[float, float, float]:
    home_win = float(np.tril(grid, -1).sum())   # i > j
    draw = float(np.trace(grid))                # i == j
    away_win = float(np.triu(grid, 1).sum())    # i < j
    # normalise away the lost tail mass beyond the grid
    total = home_win + draw + away_win
    return home_win / total, draw / total, away_win / total


def _top_scorelines(grid: np.ndarray, n: int = 5) -> list[dict]:
    flat = [(i, j, grid[i, j]) for i in range(grid.shape[0]) for j in range(grid.shape[1])]
    flat.sort(key=lambda t: t[2], reverse=True)
    return [{"score": f"{i}-{j}", "prob": round(float(p), 4)} for i, j, p in flat[:n]]


def predict_match(home: str, away: str, strength_home: float, strength_away: float,
                  logreg_probs: dict | None = None, blend: float = 0.5,
                  home_adv: float = 0.0) -> MatchPrediction:
    """
    Full single-match prediction.

    `logreg_probs`, if given, is {'home': p, 'draw': p, 'away': p} from the
    trained model; the final Win/Draw/Loss is then a `blend`/(1-blend) mix of
    Poisson and LogReg (the notebooks' ensemble trick). Without it, the
    Poisson grid stands alone.
    """
    lam_h, lam_a = expected_goals(strength_home, strength_away, home_adv)
    grid = scoreline_grid(lam_h, lam_a)
    p_home, p_draw, p_away = _outcomes(grid)

    components = {"poisson": {"home": round(p_home, 4), "draw": round(p_draw, 4),
                              "away": round(p_away, 4)}, "logreg": None}

    if logreg_probs:
        lh, ld, la = logreg_probs["home"], logreg_probs["draw"], logreg_probs["away"]
        components["logreg"] = {"home": round(lh, 4), "draw": round(ld, 4), "away": round(la, 4)}
        p_home = blend * p_home + (1 - blend) * lh
        p_draw = blend * p_draw + (1 - blend) * ld
        p_away = blend * p_away + (1 - blend) * la
        s = p_home + p_draw + p_away
        p_home, p_draw, p_away = p_home / s, p_draw / s, p_away / s

    return MatchPrediction(
        home=home, away=away,
        exp_home_goals=round(lam_h, 2), exp_away_goals=round(lam_a, 2),
        home_win=round(p_home, 4), draw=round(p_draw, 4), away_win=round(p_away, 4),
        top_scorelines=_top_scorelines(grid),
        grid=np.round(grid[:6, :6], 4).tolist(),  # 6×6 is enough to display
        components=components,
    )
