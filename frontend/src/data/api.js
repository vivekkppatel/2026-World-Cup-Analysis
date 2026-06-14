/**
 * data/api.js — the single data layer for the dashboard.
 *
 * Right now every function returns MOCK data that mirrors the real model's
 * actual output (France champion, USA out in the semis, etc.). To go live,
 * replace each function body with a `fetch()` to a thin API over the Python /
 * PostgreSQL backend — the component code never changes because the shapes
 * stay identical. Example of the swap:
 *
 *   export async function getChampionOdds() {
 *     const r = await fetch(`${API_BASE}/champion-odds`)
 *     return r.json()
 *   }
 *
 * The corresponding SQL already exists as the `v_bracket_predictions`,
 * `v_top_scorers`, `v_model_scorecard` views (see docs/BI_SETUP.md).
 */

export const API_BASE = import.meta.env.VITE_API_BASE || '' // set when wiring live

// ── Champion / advancement odds (from v_bracket_predictions) ────────────────
export async function getChampionOdds() {
  return [
    { team: 'France', odds: 11.8, reachedSf: 29.3 },
    { team: 'Netherlands', odds: 9.8, reachedSf: 26.9 },
    { team: 'England', odds: 9.3, reachedSf: 27.6 },
    { team: 'Germany', odds: 8.9, reachedSf: 24.9 },
    { team: 'United States', odds: 8.4, reachedSf: 26.0 },
    { team: 'Argentina', odds: 7.4, reachedSf: 25.7 },
    { team: 'Brazil', odds: 7.2, reachedSf: 22.0 },
    { team: 'Spain', odds: 7.2, reachedSf: 24.0 },
    { team: 'Portugal', odds: 4.7, reachedSf: 19.7 },
    { team: 'Senegal', odds: 3.8, reachedSf: 16.4 },
  ]
}

// The headline model call (USA explicitly not winning)
export const MODEL_CALL = {
  champion: 'France',
  championOdds: 11.8,
  usaOdds: 8.4,
  usaCeiling: 'Semifinals',
}

// ── Model scorecard KPIs (from v_model_scorecard) ───────────────────────────
export async function getScorecard() {
  return {
    predictionsScored: 0, // fills in as knockout matches finish
    hitRate: null,
    brier: 0.62, // strict temporal hold-out (WC 2022)
    baselineEdge: 7.1, // LOTO-CV edge over the FIFA-rank baseline (pts)
    accuracyByRound: [
      { round: 'R32', hit: null },
      { round: 'R16', hit: null },
      { round: 'QF', hit: null },
      { round: 'SF', hit: null },
      { round: 'Final', hit: null },
    ],
  }
}

// ── Live tournament pulse (from the matches table) ──────────────────────────
export async function getPulse() {
  // 0 finished because the free open-data feeds have no published WC 2026
  // results yet. When the live feed populates, these numbers move on their own.
  return { played: 0, total: 104, goals: 0, nextMatch: 'Mexico vs South Africa', kickoff: 'Jun 11 · 19:00 UTC' }
}

// ── Team stats (from v_player_stats / v_team_match_stats, historical) ────────
export async function getTeamStats() {
  return [
    { team: 'France', fifaRank: 1, strength: 1835, recentForm: 'W W D W', titleOdds: 11.8 },
    { team: 'Spain', fifaRank: 2, strength: 1786, recentForm: 'W W W D', titleOdds: 7.2 },
    { team: 'Argentina', fifaRank: 3, strength: 1796, recentForm: 'W D W W', titleOdds: 7.4 },
    { team: 'England', fifaRank: 4, strength: 1809, recentForm: 'W W W L', titleOdds: 9.3 },
    { team: 'Portugal', fifaRank: 5, strength: 1768, recentForm: 'W L W W', titleOdds: 4.7 },
    { team: 'Netherlands', fifaRank: 7, strength: 1818, recentForm: 'W W D W', titleOdds: 9.8 },
    { team: 'Brazil', fifaRank: 6, strength: 1791, recentForm: 'D W W W', titleOdds: 7.2 },
    { team: 'Germany', fifaRank: 10, strength: 1785, recentForm: 'W D W W', titleOdds: 8.9 },
    { team: 'United States', fifaRank: 16, strength: 1801, recentForm: 'W W L D', titleOdds: 8.4 },
  ]
}

// Top historical scorers (from v_top_scorers, WC 2022)
export async function getTopScorers() {
  return [
    { player: 'Kylian Mbappé', team: 'France', goals: 8, xg: 4.2 },
    { player: 'Lionel Messi', team: 'Argentina', goals: 7, xg: 6.0 },
    { player: 'Julián Álvarez', team: 'Argentina', goals: 4, xg: 1.9 },
    { player: 'Olivier Giroud', team: 'France', goals: 4, xg: 3.1 },
    { player: 'Cody Gakpo', team: 'Netherlands', goals: 3, xg: 0.6 },
  ]
}

// ── Predicted knockout bracket (coherent chalk bracket, France champion) ─────
export async function getBracket() {
  // Final-eight view (R16 → QF → SF → Final), winner of each match marked.
  return {
    left: {
      r16: [
        { home: 'France', away: 'Senegal', winner: 'France' },
        { home: 'Netherlands', away: 'Japan', winner: 'Netherlands' },
        { home: 'United States', away: 'Croatia', winner: 'United States' },
        { home: 'Brazil', away: 'Morocco', winner: 'Brazil' },
      ],
      qf: [
        { home: 'France', away: 'Netherlands', winner: 'France' },
        { home: 'United States', away: 'Brazil', winner: 'United States' },
      ],
      sf: [{ home: 'France', away: 'United States', winner: 'France' }],
    },
    right: {
      r16: [
        { home: 'England', away: 'Senegal', winner: 'England' },
        { home: 'Germany', away: 'Mexico', winner: 'Germany' },
        { home: 'Argentina', away: 'Switzerland', winner: 'Argentina' },
        { home: 'Portugal', away: 'Uruguay', winner: 'Portugal' },
      ],
      qf: [
        { home: 'England', away: 'Germany', winner: 'England' },
        { home: 'Argentina', away: 'Portugal', winner: 'Argentina' },
      ],
      sf: [{ home: 'England', away: 'Argentina', winner: 'England' }],
    },
    final: { home: 'France', away: 'England', winner: 'France' },
  }
}
