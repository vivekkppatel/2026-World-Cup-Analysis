"""
models/features.py
───────────────────
Leakage-free feature engineering for the match-outcome model.

Every feature here is knowable BEFORE kickoff. This is the whole point: the
previous model leaked by feeding a match's own goals/xG into its features,
producing a fake 96.9% accuracy. Here, each feature is derived only from data
that existed before the match started:

    elo_diff        as-of-date World Cup Elo (built from matches BEFORE this one)
    fifa_rank_gap   static pre-tournament FIFA ranking
    form_goals_diff rolling goal difference over each team's PRIOR matches
    form_xg_diff    rolling xG difference over each team's PRIOR matches
    rest_days_diff  days since each team's previous match
    is_knockout     known from the fixture list

Quant-finance analog: this is point-in-time correctness. Just as a backtest
must use only the fundamentals that were public on the trade date — never
restated figures — each match feature uses only the strength/form signals
available the morning of the match.
"""
from __future__ import annotations

import logging
from collections import deque

import pandas as pd

from models.elo import EloModel

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "elo_diff", "fifa_rank_gap", "form_goals_diff",
    "form_xg_diff", "rest_days_diff", "is_knockout",
]
LABEL_MAP = {"HOME": 0, "DRAW": 1, "AWAY": 2}   # HOME_WIN / DRAW / AWAY_WIN

_FORM_WINDOW = 5            # rolling window length (matches) for form features
_DEFAULT_REST_DAYS = 7      # assumed rest before a team's first match in the data


def build_match_features(
    matches: pd.DataFrame,
    elo: EloModel,
    fifa_ranks: dict[str, int],
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Build a leakage-free feature matrix + label vector from finished matches.

    `matches` must be chronologically sortable and contain:
        kickoff_utc, home_team, away_team, home_score, away_score,
        stage, winner, team_xg_home, team_xg_away (xG nullable).
        Optional: tournament_label (carried into the returned meta frame).

    `elo` is a model with rating_as_of() (built from history that may overlap
    these matches — as-of-date lookups guarantee no future leak).
    `fifa_ranks` maps team name → current FIFA ranking (static).

    Build features over ALL the matches you intend to use in one call so the
    rolling-form windows carry across tournaments chronologically; split into
    train/test afterwards using the returned meta frame.

    Returns (X, y, meta) where y ∈ {0,1,2} from the home team's perspective and
    meta aligns row-for-row with X (tournament_label, home_team, away_team).
    """
    ordered = matches.sort_values("kickoff_utc").reset_index(drop=True)

    # Rolling state, updated AFTER each match so a match never sees its own data.
    goals_form: dict[str, deque] = {}     # team → recent (gf - ga)
    xg_form: dict[str, deque] = {}        # team → recent (xg_for - xg_against)
    last_played: dict[str, pd.Timestamp] = {}

    rows: list[dict] = []
    labels: list[int] = []
    meta_rows: list[dict] = []

    for _, m in ordered.iterrows():
        home, away = m["home_team"], m["away_team"]
        date = str(pd.to_datetime(m["kickoff_utc"]).date())
        kickoff = pd.to_datetime(m["kickoff_utc"])

        # ── Features (pre-match only) ──
        elo_diff = elo.rating_as_of(home, date) - elo.rating_as_of(away, date)
        rank_gap = _rank_gap(fifa_ranks.get(away), fifa_ranks.get(home))
        form_goals_diff = _mean(goals_form.get(home)) - _mean(goals_form.get(away))
        form_xg_diff = _mean(xg_form.get(home)) - _mean(xg_form.get(away))
        rest_diff = (_rest_days(last_played.get(home), kickoff)
                     - _rest_days(last_played.get(away), kickoff))
        is_knockout = 0 if "group" in str(m["stage"]).lower() else 1

        rows.append({
            "elo_diff": elo_diff,
            "fifa_rank_gap": rank_gap,
            "form_goals_diff": form_goals_diff,
            "form_xg_diff": form_xg_diff,
            "rest_days_diff": rest_diff,
            "is_knockout": is_knockout,
        })
        labels.append(LABEL_MAP[m["winner"]])
        meta_rows.append({
            "tournament_label": m.get("tournament_label"),
            "home_team": home, "away_team": away,
        })

        # ── Update rolling state AFTER recording the row ──
        hs, as_ = int(m["home_score"]), int(m["away_score"])
        _push(goals_form, home, hs - as_)
        _push(goals_form, away, as_ - hs)
        if pd.notna(m.get("team_xg_home")) and pd.notna(m.get("team_xg_away")):
            xh, xa = float(m["team_xg_home"]), float(m["team_xg_away"])
            _push(xg_form, home, xh - xa)
            _push(xg_form, away, xa - xh)
        last_played[home] = kickoff
        last_played[away] = kickoff

    X = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    y = pd.Series(labels, name="outcome")
    meta = pd.DataFrame(meta_rows)
    logger.info(f"Built {len(X)} leakage-free feature rows.")
    return X, y, meta


# ── helpers ───────────────────────────────────────────────────────────────────

def _push(store: dict[str, deque], team: str, value: float) -> None:
    store.setdefault(team, deque(maxlen=_FORM_WINDOW)).append(value)


def _mean(dq: deque | None) -> float:
    """Mean of a rolling window; 0.0 (neutral) when a team has no history yet."""
    return sum(dq) / len(dq) if dq else 0.0


def _rank_gap(away_rank: int | None, home_rank: int | None) -> float:
    """
    Positive when the home side is higher-ranked (lower rank number).
    Missing ranks → 0 (no signal) rather than a wild default.
    """
    if home_rank is None or away_rank is None:
        return 0.0
    return float(away_rank - home_rank)


def _rest_days(prev: pd.Timestamp | None, kickoff: pd.Timestamp) -> float:
    if prev is None:
        return float(_DEFAULT_REST_DAYS)
    return max((kickoff - prev).days, 0)
