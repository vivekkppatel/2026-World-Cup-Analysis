"""
models/tournament_sim.py
─────────────────────────
Monte Carlo simulator for the World Cup 2026 (48 teams, 104 matches).

Given team strengths (from models.elo), it plays the whole tournament
thousands of times — group stage → standings with tiebreakers → the real
FIFA knockout slotting → final — and aggregates two things:

  1. Advancement probabilities: P(team reaches R32 / R16 / … / wins) — the
     honest output. "Argentina 22% champion" beats a single guessed bracket.
  2. A modal bracket: the single most likely team in each knockout slot,
     for the side-by-side-vs-reality view.

The bracket structure (which group slots feed which R32 match, and the
W##/L## progression) is read from the `matches` table, which already encodes
the official FIFA schedule via openfootball placeholders ('2A', 'W73').

Quant-finance analog: this is a Monte Carlo path simulation. Each tournament
is one price path; advancement probabilities are the distribution of outcomes
across paths — exactly how you'd price a path-dependent option or estimate
VaR rather than trusting a single point forecast.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from models.elo import EloModel, HOME_ADVANTAGE

logger = logging.getLogger(__name__)

# Expected goals per team in an evenly-matched game; Elo gap shifts each side's
# Poisson mean. Calibrated to the ~2.7 goals/game seen across recent WCs.
_BASE_LAMBDA = 1.35
_LAMBDA_ELO_SWING = 0.9   # how strongly Elo edge moves a team's expected goals

ROUND_ORDER = ["GROUP_STAGE", "LAST_32", "LAST_16",
               "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]
# Rounds a team is credited with "reaching" when it wins the prior round.
ADVANCE_LABELS = ["reached_r32", "reached_r16", "reached_qf",
                  "reached_sf", "reached_final", "won_cup"]


@dataclass
class GroupTeam:
    name: str
    strength: float


# ═══════════════════════════════════════════════════════════════════════════════
# Match outcome model
# ═══════════════════════════════════════════════════════════════════════════════

def _lambdas(strength_a: float, strength_b: float,
             home_adv: float = 0.0) -> tuple[float, float]:
    """
    Map an Elo strength gap onto a pair of Poisson goal means. The stronger
    side gets a higher expected-goals rate; the gap is squashed through a
    logistic so it stays in a realistic band.
    """
    diff = (strength_a + home_adv) - strength_b
    swing = _LAMBDA_ELO_SWING * (2.0 / (1.0 + 10 ** (-diff / 400.0)) - 1.0)
    return _BASE_LAMBDA + swing, _BASE_LAMBDA - swing


def simulate_match(strength_a: float, strength_b: float, rng: np.random.Generator,
                   allow_draw: bool = True, home_adv: float = 0.0) -> tuple[int, int]:
    """
    Simulate one match as two independent Poisson goal counts. In knockouts
    (allow_draw=False) a tie is resolved by a coin flip weighted to strength
    — a lightweight stand-in for extra time + penalties.
    """
    lam_a, lam_b = _lambdas(strength_a, strength_b, home_adv)
    ga = int(rng.poisson(max(lam_a, 0.05)))
    gb = int(rng.poisson(max(lam_b, 0.05)))

    if not allow_draw and ga == gb:
        p_a = EloModel.expected_score(strength_a + home_adv, strength_b)
        if rng.random() < p_a:
            ga += 1
        else:
            gb += 1
    return ga, gb


# ═══════════════════════════════════════════════════════════════════════════════
# Group stage
# ═══════════════════════════════════════════════════════════════════════════════

def _simulate_group(teams: list[GroupTeam], fixtures: list[tuple[int, int]],
                    rng: np.random.Generator) -> list[dict]:
    """
    Play a group's round-robin and return its final table (sorted).
    Tiebreakers: points → goal difference → goals for → a deterministic
    coin flip (real FIFA uses head-to-head then fair-play; this is close
    enough for simulation and avoids bias).
    """
    n = len(teams)
    table = [{"name": t.name, "pts": 0, "gf": 0, "ga": 0, "idx": i}
             for i, t in enumerate(teams)]

    for i, j in fixtures:
        ga, gb = simulate_match(teams[i].strength, teams[j].strength, rng)
        table[i]["gf"] += ga; table[i]["ga"] += gb
        table[j]["gf"] += gb; table[j]["ga"] += ga
        if ga > gb:
            table[i]["pts"] += 3
        elif gb > ga:
            table[j]["pts"] += 3
        else:
            table[i]["pts"] += 1; table[j]["pts"] += 1

    for row in table:
        row["gd"] = row["gf"] - row["ga"]
        row["tiebreak"] = rng.random()
    table.sort(key=lambda r: (r["pts"], r["gd"], r["gf"], r["tiebreak"]),
               reverse=True)
    return table


def _round_robin_fixtures(n: int) -> list[tuple[int, int]]:
    """All unique pairings for an n-team group."""
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


# ═══════════════════════════════════════════════════════════════════════════════
# Tournament structure (read from the matches table's placeholder encoding)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BracketStructure:
    """The fixed shape of the knockout stage, parsed once from the DB."""
    # match_num → (stage, home_placeholder, away_placeholder)
    matches: dict[int, tuple[str, str, str]]
    # group letter → list of match (i,j) fixtures by seed index
    group_letters: list[str]


_GROUP_SLOT = re.compile(r"^([123])([A-L])$")          # '1A', '2B'
_THIRD_SLOT = re.compile(r"^3([A-L/]+)$")              # '3A/B/C/D/F'
_WINNER_SLOT = re.compile(r"^W(\d+)$")                  # 'W74'
_LOSER_SLOT = re.compile(r"^L(\d+)$")                   # 'L101'


# ═══════════════════════════════════════════════════════════════════════════════
# Full tournament simulation
# ═══════════════════════════════════════════════════════════════════════════════

class TournamentSimulator:
    """
    Holds the fixed bracket structure + team strengths, and runs N simulations.
    """

    def __init__(self, groups: dict[str, list[GroupTeam]],
                 structure: BracketStructure):
        self.groups = groups
        self.structure = structure

    def run_once(self, rng: np.random.Generator) -> dict:
        """
        Play one full tournament. Returns:
          - 'advance': {team: highest round index reached}
          - 'slots':   {match_num: {'home': team, 'away': team, 'winner': team}}
        """
        strength = {t.name: t.strength
                    for g in self.groups.values() for t in g}

        # ── Group stage ──
        group_tables: dict[str, list[dict]] = {}
        for letter, teams in self.groups.items():
            fixtures = _round_robin_fixtures(len(teams))
            group_tables[letter] = _simulate_group(teams, fixtures, rng)

        # Winners and runners-up by group
        resolved: dict[str, str] = {}
        for letter, tbl in group_tables.items():
            resolved[f"1{letter}"] = tbl[0]["name"]
            resolved[f"2{letter}"] = tbl[1]["name"]

        # Best-third pool: assign qualified thirds to the '3...' slots in order
        thirds_ranked = self._rank_thirds(group_tables, rng)
        third_iter = iter(thirds_ranked)

        advance: dict[str, int] = defaultdict(int)
        for letter, tbl in group_tables.items():
            for name in (tbl[0]["name"], tbl[1]["name"]):
                advance[name] = max(advance[name], 1)  # reached R32
        for name in thirds_ranked:
            advance[name] = max(advance[name], 1)

        # ── Knockouts ──
        slots: dict[int, dict] = {}
        winners: dict[int, str] = {}
        losers: dict[int, str] = {}

        for match_num in sorted(self.structure.matches):
            stage, home_ph, away_ph = self.structure.matches[match_num]
            home = self._resolve(home_ph, resolved, winners, losers, third_iter)
            away = self._resolve(away_ph, resolved, winners, losers, third_iter)
            if home is None or away is None:
                continue

            ga, gb = simulate_match(strength.get(home, 1500),
                                    strength.get(away, 1500),
                                    rng, allow_draw=False)
            winner, loser = (home, away) if ga > gb else (away, home)
            winners[match_num] = winner
            losers[match_num] = loser
            slots[match_num] = {"home": home, "away": away, "winner": winner}

            # The third-place match doesn't advance anyone — both finalists for
            # it already reached the semis. Record the slot, skip the ladder.
            if stage == "THIRD_PLACE":
                continue

            # Winning a match at round_idx promotes you to that milestone
            # (win LAST_32 → reached_r16 … win FINAL → won_cup). The loser
            # stays one rung below — including the final's loser, who reached
            # the final but did not win it.
            round_idx = ROUND_ORDER.index(stage)
            advance[winner] = max(advance[winner], round_idx)
            advance[loser] = max(advance[loser], round_idx - 1)

        return {"advance": dict(advance), "slots": slots}

    def _rank_thirds(self, group_tables: dict[str, list[dict]],
                     rng: np.random.Generator) -> list[str]:
        thirds = [dict(group=g, **tbl[2]) for g, tbl in group_tables.items()
                  if len(tbl) >= 3]
        for t in thirds:
            t["seed"] = rng.random()
        thirds.sort(key=lambda r: (r["pts"], r["gd"], r["gf"], r["seed"]),
                    reverse=True)
        return [t["name"] for t in thirds[:8]]

    @staticmethod
    def _resolve(placeholder: str, resolved: dict[str, str],
                 winners: dict[int, str], losers: dict[int, str],
                 third_iter) -> str | None:
        """Turn a slot placeholder into a concrete team name, if known yet."""
        if placeholder in resolved:
            return resolved[placeholder]
        if _GROUP_SLOT.match(placeholder):
            return resolved.get(placeholder)
        if _THIRD_SLOT.match(placeholder):
            return next(third_iter, None)
        mw = _WINNER_SLOT.match(placeholder)
        if mw:
            return winners.get(int(mw.group(1)))
        ml = _LOSER_SLOT.match(placeholder)
        if ml:
            return losers.get(int(ml.group(1)))
        return None

    def run(self, n_sims: int, seed: int = 2026) -> "SimulationResult":
        """Run N tournaments and aggregate advancement frequencies."""
        rng = np.random.default_rng(seed)
        reach_counts: dict[str, list[int]] = defaultdict(lambda: [0] * len(ROUND_ORDER))
        # modal-bracket tally: match_num → Counter of winners
        slot_winner_tally: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        slot_pair_tally: dict[int, dict[tuple[str, str], int]] = defaultdict(lambda: defaultdict(int))

        for _ in range(n_sims):
            out = self.run_once(rng)
            for team, reached in out["advance"].items():
                for r in range(reached + 1):
                    reach_counts[team][r] += 1
            for mnum, slot in out["slots"].items():
                slot_winner_tally[mnum][slot["winner"]] += 1
                slot_pair_tally[mnum][(slot["home"], slot["away"])] += 1

        return SimulationResult(n_sims, dict(reach_counts),
                                {k: dict(v) for k, v in slot_winner_tally.items()},
                                {k: dict(v) for k, v in slot_pair_tally.items()})


@dataclass
class SimulationResult:
    n_sims: int
    reach_counts: dict[str, list[int]]                       # team → [r32,..,win] counts
    slot_winner_tally: dict[int, dict[str, int]]             # match → {team: wins}
    slot_pair_tally: dict[int, dict[tuple[str, str], int]]   # match → {(h,a): count}

    def advancement_table(self) -> list[dict]:
        """Per-team probability of reaching each round, sorted by title odds."""
        rows = []
        for team, counts in self.reach_counts.items():
            row = {"team": team}
            for label, c in zip(ADVANCE_LABELS, counts):
                row[label] = round(c / self.n_sims, 4)
            rows.append(row)
        rows.sort(key=lambda r: r["won_cup"], reverse=True)
        return rows

    def modal_bracket(self) -> dict[int, dict]:
        """
        Most likely (home, away, winner) for each knockout match. The winner is
        chosen from WITHIN the modal pairing (whichever of the two displayed
        teams won more often), so the bracket never shows a winner who isn't in
        the matchup — the global modal winner can otherwise be a third team,
        since any single pairing is individually unlikely in a 48-team field.
        """
        bracket = {}
        for mnum, pairs in self.slot_pair_tally.items():
            top_pair = max(pairs.items(), key=lambda kv: kv[1])[0]
            winners = self.slot_winner_tally.get(mnum, {})
            home, away = top_pair
            top_winner = (home if winners.get(home, 0) >= winners.get(away, 0)
                          else away)
            bracket[mnum] = {"home": top_pair[0], "away": top_pair[1],
                             "winner": top_winner}
        return bracket
