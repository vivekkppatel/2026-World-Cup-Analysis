"""
models/player_rating.py
─────────────────────────
Composite Player Contribution Score (CPCS).

A weighted, position-adjusted rating that answers:
"Which players are contributing most relative to their playing time?"

This is the "Player Valuation" page's core model.
The framing for interviews: this is analogous to risk-adjusted return —
normalizing output (goals, assists, pressures) per unit of input (minutes).

Weights are inspired by StatsBomb's publicly documented methodology.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Position classification ───────────────────────────────────────────────────
# StatsBomb's event `position` field uses verbose strings — "Center Back",
# "Left Center Back", "Center Defensive Midfield", "Left Wing Back", … (24
# variants), NOT abbreviations or British spellings. Keyword matching is far
# more robust than exact-set membership: an earlier version matched
# "Centre-Back"/"Central Midfield", so almost every defender and midfielder
# fell through to the FWD default and was scored with forward weights.
_POSITION_ABBREV = {
    "gk": "GK",
    "cb": "DEF", "lb": "DEF", "rb": "DEF", "lwb": "DEF", "rwb": "DEF",
    "cm": "MID", "cdm": "MID", "cam": "MID", "dm": "MID", "am": "MID",
    "lm": "MID", "rm": "MID",
    "st": "FWD", "cf": "FWD", "lw": "FWD", "rw": "FWD", "ss": "FWD",
}


@dataclass
class PositionWeights:
    """
    Feature weights per position group.
    Values sum to ~1.0 (approximate — renormalized in code).
    """
    goals:                float = 0.20
    assists:              float = 0.15
    xg:                   float = 0.15
    xa:                   float = 0.10
    key_passes:           float = 0.08
    progressive_passes:   float = 0.07
    progressive_carries:  float = 0.07
    pressures:            float = 0.08
    shots_on_target:      float = 0.05
    tackles:              float = 0.05


POSITION_WEIGHTS: dict[str, PositionWeights] = {
    "GK": PositionWeights(
        goals=0.01, assists=0.03, xg=0.01, xa=0.03,
        key_passes=0.05, progressive_passes=0.10,
        progressive_carries=0.05, pressures=0.10,
        shots_on_target=0.02, tackles=0.10,
    ),
    "DEF": PositionWeights(
        goals=0.05, assists=0.08, xg=0.05, xa=0.08,
        key_passes=0.07, progressive_passes=0.12,
        progressive_carries=0.08, pressures=0.18,
        shots_on_target=0.04, tackles=0.15,
    ),
    "MID": PositionWeights(
        goals=0.12, assists=0.14, xg=0.12, xa=0.12,
        key_passes=0.12, progressive_passes=0.14,
        progressive_carries=0.10, pressures=0.06,
        shots_on_target=0.04, tackles=0.04,
    ),
    "FWD": PositionWeights(
        goals=0.25, assists=0.15, xg=0.22, xa=0.12,
        key_passes=0.08, progressive_passes=0.05,
        progressive_carries=0.07, pressures=0.03,
        shots_on_target=0.02, tackles=0.01,
    ),
}


def _get_position_group(position: str) -> str:
    """
    Map any StatsBomb position string (or abbreviation) to GK/DEF/MID/FWD.

    Order matters: 'back' is tested before 'wing' so wing-backs ('Left Wing
    Back') resolve to DEF, not FWD. Unknown/ambiguous labels (e.g.
    'Substitute') default to MID — a neutral middle rather than FWD, whose
    goal-heavy weights would inflate the score of anyone unclassified.
    """
    if not position:
        return "MID"
    p = str(position).strip().lower()
    if p in _POSITION_ABBREV:
        return _POSITION_ABBREV[p]
    if "goalkeeper" in p:
        return "GK"
    if "back" in p:        # Center Back, Left Back, Wing Back — all defenders
        return "DEF"
    if "midfield" in p:
        return "MID"
    if "wing" in p or "forward" in p or "striker" in p:
        return "FWD"
    return "MID"


def compute_player_ratings(df: pd.DataFrame, min_minutes: int = 90) -> pd.DataFrame:
    """
    Compute the Composite Player Contribution Score for all players.

    Input: player_tournament_stats DataFrame from StatsBombLoader.
    Output: same DataFrame with an added 'cpcs' column (0–100 scale).

    The CPCS is:
    1. For each feature, take the per-90 rate.
    2. Normalise each feature column to 0–1 within the dataset.
    3. Apply position-adjusted weights.
    4. Scale the final score 0–100.
    """
    df = df[df["minutes_played"] >= min_minutes].copy()

    if df.empty:
        logger.warning("No players met the minimum minutes threshold.")
        return df

    # Per-90 features used for scoring
    p90_features = [
        "goals_p90", "assists_p90", "xg_p90", "xa_p90",
        "key_passes_p90", "progressive_passes_p90",
        "progressive_carries_p90", "pressures_p90",
        "shots_on_target_p90",
    ]

    # Add tackles_p90 if available
    if "tackles" in df.columns:
        p90 = df["minutes_played"] / 90
        df["tackles_p90"] = (df["tackles"] / p90).round(3)
    else:
        df["tackles_p90"] = 0.0

    p90_features.append("tackles_p90")

    # Fill missing columns with 0
    for col in p90_features:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)

    # Normalise each feature to [0, 1] across all players
    normed = df[p90_features].copy()
    for col in p90_features:
        col_max = normed[col].max()
        if col_max > 0:
            normed[col] = normed[col] / col_max

    # Apply position-specific weights
    df["position_group"] = df["position"].apply(_get_position_group)
    scores = []

    feature_map = {
        "goals_p90":               "goals",
        "assists_p90":             "assists",
        "xg_p90":                  "xg",
        "xa_p90":                  "xa",
        "key_passes_p90":          "key_passes",
        "progressive_passes_p90":  "progressive_passes",
        "progressive_carries_p90": "progressive_carries",
        "pressures_p90":           "pressures",
        "shots_on_target_p90":     "shots_on_target",
        "tackles_p90":             "tackles",
    }

    for idx, row in normed.iterrows():
        pos_group = df.loc[idx, "position_group"]
        weights = POSITION_WEIGHTS[pos_group]
        score = 0.0
        for p90_col, weight_attr in feature_map.items():
            score += row[p90_col] * getattr(weights, weight_attr)
        scores.append(score)

    df["cpcs_raw"] = scores
    # Scale to 0–100
    max_score = max(scores) if scores else 1.0
    df["cpcs"] = (df["cpcs_raw"] / max_score * 100).round(1)

    # Rank within position group
    df["position_rank"] = df.groupby("position_group")["cpcs"].rank(
        ascending=False, method="min"
    ).astype(int)

    logger.info(f"Computed CPCS for {len(df)} players. Top score: {df['cpcs'].max():.1f}")
    return df.sort_values("cpcs", ascending=False)


def get_undervalued_players(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    Find players with high CPCS but low minutes — the 'undervalued' cohort.
    These are impactful players who haven't had enough game time.

    For BA/Finance Analyst framing: this is alpha identification —
    high output-per-input with low volume (low minutes exposure).
    """
    if "cpcs" not in df.columns:
        df = compute_player_ratings(df)

    # Low minutes = below 50th percentile, high score = above 60th percentile
    minutes_threshold = df["minutes_played"].quantile(0.50)
    score_threshold   = df["cpcs"].quantile(0.60)

    undervalued = df[
        (df["minutes_played"] < minutes_threshold) &
        (df["cpcs"] >= score_threshold)
    ].copy()

    undervalued["efficiency_ratio"] = (
        undervalued["cpcs"] / (undervalued["minutes_played"] / 90)
    ).round(2)

    return undervalued.sort_values("efficiency_ratio", ascending=False).head(top_n)
