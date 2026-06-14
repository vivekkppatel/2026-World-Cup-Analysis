"""
models/recent_form.py
──────────────────────
Competition-weighted, recency-decayed recent-form scoring — the distinctive
feature from the reference notebooks, as pure (testable, API-free) logic.

Idea: not all matches carry equal signal. A World Cup win means more than a
friendly; last month means more than three years ago. So each recent match
gets a weight = competition_importance × time_decay, and the team's form is
the weighted average of its results. That form is then converted to an Elo
point adjustment that nudges the expected goals in the match predictor.

The raw recent matches come from API-Football (see apifootball_loader); this
module just does the math, so it's unit-tested without any network.
"""
from __future__ import annotations

from datetime import date

# Competition importance — matched against the league NAME (case-insensitive
# substring), since API-Football returns league names, not short codes.
# ORDER MATTERS: more specific patterns first, so "World Cup Qualification"
# matches 'qualif' (1.5), not 'world cup' (3.0).
_COMP_WEIGHTS = [
    ("qualif", 1.5),      # WC / Euro qualifiers — check before 'world cup'/'euro'
    ("nations league", 1.8),
    ("world cup", 3.0),
    ("euro", 2.5),
    ("africa", 2.5),      # AFCON
    ("copa", 2.5),        # Copa América
    ("friendl", 0.6),
]
_DEFAULT_COMP_WEIGHT = 1.0
_HALF_LIFE_DAYS = 365     # a result one year old counts half

# Strength-adjustment scaling: weighted goal-difference-per-game → Elo points.
_GD_TO_ELO = 28.0
_FORM_CAP = 55.0          # never let recent form swing strength by more than this


def competition_weight(league_name: str | None) -> float:
    name = (league_name or "").lower()
    for needle, w in _COMP_WEIGHTS:
        if needle in name:
            return w
    return _DEFAULT_COMP_WEIGHT


def _time_weight(match_date: date, ref: date) -> float:
    days = max((ref - match_date).days, 0)
    return 2 ** (-days / _HALF_LIFE_DAYS)


def compute_form(matches: list[dict], ref: date) -> dict:
    """
    Aggregate a list of recent matches into weighted form stats.

    Each match dict needs: gf, ga (ints), league (name str), date (datetime.date).
    Returns weighted win_rate / gf_pg / ga_pg / gd_pg / pts_pg, the effective
    sample size, and the n of matches used. Empty input → neutral zeros.
    """
    if not matches:
        return {"win_rate": 0.5, "gf_pg": 1.3, "ga_pg": 1.3, "gd_pg": 0.0,
                "pts_pg": 1.3, "n": 0, "eff_n": 0.0}

    wsum = gf = ga = gd = pts = wins = 0.0
    for m in matches:
        w = competition_weight(m.get("league")) * _time_weight(m["date"], ref)
        g_for, g_ag = int(m["gf"]), int(m["ga"])
        win = g_for > g_ag
        result_pts = 3 if win else (1 if g_for == g_ag else 0)
        wsum += w
        gf += w * g_for
        ga += w * g_ag
        gd += w * (g_for - g_ag)
        pts += w * result_pts
        wins += w * (1 if win else 0)

    wsum = wsum or 1e-9
    return {
        "win_rate": round(wins / wsum, 4),
        "gf_pg": round(gf / wsum, 3),
        "ga_pg": round(ga / wsum, 3),
        "gd_pg": round(gd / wsum, 3),
        "pts_pg": round(pts / wsum, 3),
        "n": len(matches),
        "eff_n": round(wsum, 2),
    }


def form_to_elo_delta(form: dict) -> float:
    """
    Convert weighted form into an Elo-point adjustment (capped). Driven mainly
    by weighted goal difference per game — a side averaging +1.5 GD recently is
    in strong form and gets a positive nudge; a struggling side gets a negative
    one. Thin samples (eff_n < 2) are shrunk toward zero to avoid overreacting.
    """
    if form.get("n", 0) == 0:
        return 0.0
    delta = form["gd_pg"] * _GD_TO_ELO
    shrink = min(form.get("eff_n", 0.0) / 4.0, 1.0)   # ramp in with sample size
    return max(-_FORM_CAP, min(_FORM_CAP, delta * shrink))
