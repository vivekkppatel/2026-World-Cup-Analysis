/**
 * data/api.js — the single data layer for the dashboard.
 *
 * Each function fetches from the FastAPI backend (api/main.py) which serves
 * the REAL model output from PostgreSQL. If the API is unreachable (e.g. you
 * open the static build with no backend running), it falls back to baked-in
 * mock data that mirrors the same shapes, so the UI never breaks.
 *
 * Point VITE_API_BASE at your deployed API in production (.env).
 */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function get(path, fallback, timeout = 4000) {
  try {
    const r = await fetch(`${API_BASE}${path}`, { signal: AbortSignal.timeout(timeout) })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  } catch (e) {
    console.warn(`[api] ${path} → fallback (${e.message})`)
    return fallback
  }
}

// ── Mock fallbacks (mirror the live shapes) ─────────────────────────────────
const MOCK_ODDS = [
  { team: 'France', odds: 11.9, reachedSf: 29.3 },
  { team: 'Netherlands', odds: 9.8, reachedSf: 26.9 },
  { team: 'England', odds: 9.3, reachedSf: 27.6 },
  { team: 'Germany', odds: 8.9, reachedSf: 24.9 },
  { team: 'United States', odds: 8.4, reachedSf: 26.0 },
  { team: 'Argentina', odds: 7.4, reachedSf: 25.7 },
  { team: 'Brazil', odds: 7.2, reachedSf: 22.0 },
  { team: 'Spain', odds: 7.2, reachedSf: 24.0 },
]

export const getChampionOdds = () => get('/api/champion-odds?limit=10', MOCK_ODDS)

export const getModelCall = () =>
  get('/api/model-call', { champion: 'France', championOdds: 11.9, usaOdds: 8.4, usaCeiling: 'Semifinals' })

export const getScorecard = () =>
  get('/api/scorecard', { predictionsScored: 0, hitRate: null, brier: 0.62, baselineEdge: 7.1 })

export const getPulse = () =>
  get('/api/pulse', { played: 0, total: 104, goals: 0, nextMatch: 'Mexico vs South Africa', kickoff: 'Jun 11 · 19:00 UTC' })

export const getTeamStats = () =>
  get('/api/team-stats', [
    { team: 'France', fifaRank: 1, strength: 1839, titleOdds: 11.9 },
    { team: 'Netherlands', fifaRank: 7, strength: 1831, titleOdds: 9.8 },
    { team: 'England', fifaRank: 4, strength: 1808, titleOdds: 9.3 },
    { team: 'United States', fifaRank: 16, strength: 1801, titleOdds: 8.4 },
    { team: 'Spain', fifaRank: 2, strength: 1786, titleOdds: 7.2 },
  ])

export const getTopScorers = () =>
  get('/api/top-scorers?tournament=WC%202022&limit=5', [
    { player: 'Kylian Mbappé', team: 'France', goals: 8, xg: 4.2 },
    { player: 'Lionel Messi', team: 'Argentina', goals: 7, xg: 6.0 },
    { player: 'Julián Álvarez', team: 'Argentina', goals: 4, xg: 1.9 },
  ])

export const getTeams = () =>
  get('/api/teams', ['Argentina', 'Brazil', 'England', 'France', 'Germany', 'Netherlands', 'Portugal', 'Senegal', 'Spain', 'United States'])

export const getMatchPredict = (home, away, knockout = false) =>
  get(`/api/match-predict?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&knockout=${knockout}`, {
    home, away, exp_home_goals: 1.5, exp_away_goals: 1.1,
    home_win: 0.5, draw: 0.25, away_win: 0.25,
    top_scorelines: [{ score: '1-1', prob: 0.09 }, { score: '1-0', prob: 0.08 }, { score: '2-1', prob: 0.07 }],
    grid: [[0.06, 0.05, 0.02], [0.08, 0.09, 0.04], [0.05, 0.06, 0.03]],
    components: { poisson: { home: 0.46, draw: 0.25, away: 0.29 }, logreg: { home: 0.55, draw: 0.25, away: 0.20 } },
  })

export const getBracket = () =>
  get('/api/bracket', {
    left: {
      r16: [{ home: 'France', away: 'Senegal', winner: 'France' }, { home: 'Netherlands', away: 'Japan', winner: 'Netherlands' }, { home: 'United States', away: 'Croatia', winner: 'United States' }, { home: 'Brazil', away: 'Morocco', winner: 'Brazil' }],
      qf: [{ home: 'France', away: 'Netherlands', winner: 'France' }, { home: 'United States', away: 'Brazil', winner: 'United States' }],
      sf: [{ home: 'France', away: 'United States', winner: 'France' }],
    },
    right: {
      r16: [{ home: 'England', away: 'Senegal', winner: 'England' }, { home: 'Germany', away: 'Mexico', winner: 'Germany' }, { home: 'Argentina', away: 'Switzerland', winner: 'Argentina' }, { home: 'Portugal', away: 'Uruguay', winner: 'Portugal' }],
      qf: [{ home: 'England', away: 'Germany', winner: 'England' }, { home: 'Argentina', away: 'Portugal', winner: 'Argentina' }],
      sf: [{ home: 'England', away: 'Argentina', winner: 'England' }],
    },
    final: { home: 'France', away: 'England', winner: 'France' },
  })

// ── Tournament Overview ─────────────────────────────────────────────────────
export const getStandings = () =>
  get('/api/standings', [
    { group_name: 'A', position: 1, team: 'Mexico', played: 1, won: 1, drawn: 0, lost: 0, goals_for: 2, goals_against: 0, points: 3 },
    { group_name: 'A', position: 2, team: 'South Africa', played: 1, won: 0, drawn: 0, lost: 1, goals_for: 0, goals_against: 2, points: 0 },
    { group_name: 'B', position: 1, team: 'Argentina', played: 1, won: 1, drawn: 0, lost: 0, goals_for: 3, goals_against: 0, points: 3 },
    { group_name: 'B', position: 2, team: 'Algeria', played: 1, won: 0, drawn: 0, lost: 1, goals_for: 0, goals_against: 3, points: 0 },
  ])

export const getResults = (tournament = 'WC 2026') =>
  get(`/api/results?tournament=${encodeURIComponent(tournament)}&limit=24`, [
    { fifa_match_num: 2, date: 'Jun 17', stage: 'GROUP_STAGE', group_name: 'B', home_team: 'Argentina', away_team: 'Algeria', home_score: 3, away_score: 0 },
    { fifa_match_num: 5, date: 'Jun 17', stage: 'GROUP_STAGE', group_name: 'E', home_team: 'England', away_team: 'Croatia', home_score: 4, away_score: 2 },
    { fifa_match_num: 7, date: 'Jun 16', stage: 'GROUP_STAGE', group_name: 'C', home_team: 'Colombia', away_team: 'Uzbekistan', home_score: 3, away_score: 1 },
  ])

export const getFixtures = () =>
  get('/api/fixtures?limit=12', [
    { fifa_match_num: 12, home_team: 'Brazil', away_team: 'Morocco', venue: 'MetLife Stadium', status: 'TIMED', kickoff: 'Jun 24 · 19:00 UTC' },
    { fifa_match_num: 13, home_team: 'Spain', away_team: 'Japan', venue: 'SoFi Stadium', status: 'TIMED', kickoff: 'Jun 24 · 22:00 UTC' },
  ])

export const getOverviewScorers = (tournament = 'WC 2026') =>
  get(`/api/top-scorers?tournament=${encodeURIComponent(tournament)}&limit=10`, [
    { player: 'Lautaro Martínez', team: 'Argentina', goals: 3, assists: 0, xg: 2.1 },
    { player: 'Harry Kane', team: 'England', goals: 2, assists: 1, xg: 1.8 },
  ])

// ── Team Analysis ───────────────────────────────────────────────────────────
export const getTATournaments = () =>
  get('/api/ta/tournaments', ['WC 2022', 'EURO 2024', 'COPA 2024', 'AFCON 2023', 'EURO 2020', 'WC 2018'])

export const getTATeams = (tournament) =>
  get(`/api/ta/teams?tournament=${encodeURIComponent(tournament)}`,
    ['Argentina', 'Brazil', 'England', 'France', 'Morocco', 'Netherlands', 'Portugal', 'Spain'])

export const getTeamAnalysis = (tournament, team) =>
  get(`/api/ta?tournament=${encodeURIComponent(tournament)}&team=${encodeURIComponent(team)}`, [
    { date: 'Nov 22', stage: 'GROUP_STAGE', opponent: 'Saudi Arabia', goals_scored: 1, goals_conceded: 2, xg: 2.3, shots: 15, passes: 640, pressures: 130 },
    { date: 'Nov 26', stage: 'GROUP_STAGE', opponent: 'Mexico', goals_scored: 2, goals_conceded: 0, xg: 1.4, shots: 12, passes: 580, pressures: 145 },
    { date: 'Nov 30', stage: 'GROUP_STAGE', opponent: 'Poland', goals_scored: 2, goals_conceded: 0, xg: 2.7, shots: 23, passes: 700, pressures: 120 },
    { date: 'Dec 03', stage: 'LAST_16', opponent: 'Australia', goals_scored: 2, goals_conceded: 1, xg: 2.6, shots: 21, passes: 660, pressures: 110 },
    { date: 'Dec 09', stage: 'QUARTER_FINALS', opponent: 'Netherlands', goals_scored: 2, goals_conceded: 2, xg: 2.1, shots: 13, passes: 540, pressures: 150 },
  ])

// ── Player Stats ────────────────────────────────────────────────────────────
export const getPSTournaments = () =>
  get('/api/ps/tournaments', ['WC 2022', 'EURO 2024', 'COPA 2024', 'AFCON 2023', 'EURO 2020', 'WC 2018'])

export const getPlayerStats = (tournament, minMinutes = 180, position = 'All') =>
  get(`/api/ps?tournament=${encodeURIComponent(tournament)}&min_minutes=${minMinutes}&position=${encodeURIComponent(position)}`, [
    { player: 'Lionel Messi', position: 'Right Wing', team: 'Argentina', matches_played: 7, minutes: 690, goals: 7, assists: 3, xg: 6.0, shots: 34, key_passes: 21, pressures: 95, tackles: 9, goals_p90: 0.91, assists_p90: 0.39, xg_p90: 0.78, shots_p90: 4.4, key_passes_p90: 2.7, pressures_p90: 12.4 },
    { player: 'Kylian Mbappé', position: 'Center Forward', team: 'France', matches_played: 7, minutes: 644, goals: 8, assists: 2, xg: 4.2, shots: 30, key_passes: 12, pressures: 70, tackles: 4, goals_p90: 1.12, assists_p90: 0.28, xg_p90: 0.59, shots_p90: 4.2, key_passes_p90: 1.7, pressures_p90: 9.8 },
  ])

// ── Player Valuation (CPCS) ─────────────────────────────────────────────────
export const getPVTournaments = () => getPSTournaments()

export const getPlayerValuation = (tournament, minMinutes = 90) =>
  get(`/api/pv?tournament=${encodeURIComponent(tournament)}&min_minutes=${minMinutes}`, {
    leaderboard: [
      { player: 'Lionel Messi', team: 'Argentina', positionGroup: 'FWD', minutes: 690, cpcs: 100, goals_p90: 0.91, assists_p90: 0.39, xg_p90: 0.78, shots_p90: 4.4, key_passes_p90: 2.7, pressures_p90: 12.4 },
      { player: 'Antoine Griezmann', team: 'France', positionGroup: 'MID', minutes: 615, cpcs: 84.2, goals_p90: 0.0, assists_p90: 0.44, xg_p90: 0.3, shots_p90: 2.1, key_passes_p90: 3.4, pressures_p90: 18.2 },
    ],
    undervalued: [
      { player: 'Cody Gakpo', team: 'Netherlands', positionGroup: 'FWD', minutes: 270, cpcs: 71.0, goals_p90: 1.0, assists_p90: 0.0, xg_p90: 0.6, shots_p90: 2.3, key_passes_p90: 1.1, pressures_p90: 8.0, efficiency: 23.7 },
    ],
  }, 12000)

// ── Monte Carlo ─────────────────────────────────────────────────────────────
export const getMonteCarlo = () =>
  get('/api/monte-carlo', {
    nSims: 10000, modelVersion: 'elo-mc-v1', champion: 'France',
    advancement: [
      { team: 'France', group: 'D', fifaRank: 1, strength: 1839, r32: 92.1, r16: 71.0, qf: 49.3, sf: 29.3, final: 18.5, champion: 11.9 },
      { team: 'Netherlands', group: 'F', fifaRank: 7, strength: 1831, r32: 90.4, r16: 68.2, qf: 45.1, sf: 26.9, final: 16.2, champion: 9.8 },
      { team: 'England', group: 'E', fifaRank: 4, strength: 1808, r32: 91.0, r16: 69.5, qf: 46.8, sf: 27.6, final: 16.9, champion: 9.3 },
      { team: 'United States', group: 'A', fifaRank: 16, strength: 1801, r32: 88.0, r16: 64.0, qf: 42.0, sf: 26.0, final: 14.0, champion: 8.4 },
    ],
    scorecard: { scored: 0, hitRate: null, brier: null, avgConf: null, byStage: [] },
  })

// ── Regression Analysis ─────────────────────────────────────────────────────
export const getRegression = () =>
  get('/api/regression', {
    available: true, modelVersion: 'logreg-v2',
    features: ['elo_diff', 'fifa_rank_gap', 'form_goals_diff', 'form_xg_diff', 'rest_days_diff', 'is_knockout'],
    classes: ['HOME_WIN', 'DRAW', 'AWAY_WIN'],
    coefficients: [[0.82, 0.31, 0.18, 0.22, 0.05, -0.12], [-0.10, -0.05, -0.08, -0.06, 0.02, 0.04], [-0.72, -0.26, -0.10, -0.16, -0.07, 0.08]],
    oddsRatios: [[2.27, 1.36, 1.20, 1.25, 1.05, 0.89], [0.90, 0.95, 0.92, 0.94, 1.02, 1.04], [0.49, 0.77, 0.90, 0.85, 0.93, 1.08]],
    importance: [{ feature: 'elo_diff', value: 0.55 }, { feature: 'fifa_rank_gap', value: 0.21 }, { feature: 'form_xg_diff', value: 0.15 }, { feature: 'form_goals_diff', value: 0.12 }, { feature: 'is_knockout', value: 0.08 }, { feature: 'rest_days_diff', value: 0.05 }],
    confusion: { labels: ['HOME_WIN', 'DRAW', 'AWAY_WIN'], matrix: [[18, 4, 3], [6, 5, 5], [4, 4, 15]] },
    classReport: [{ label: 'HOME_WIN', precision: 0.64, recall: 0.72, f1: 0.68, support: 25 }, { label: 'DRAW', precision: 0.38, recall: 0.31, f1: 0.34, support: 16 }, { label: 'AWAY_WIN', precision: 0.65, recall: 0.65, f1: 0.65, support: 23 }],
    calibration: [{ conf: 0.42, hit: 0.40, n: 12 }, { conf: 0.55, hit: 0.58, n: 22 }, { conf: 0.68, hit: 0.71, n: 18 }, { conf: 0.82, hit: 0.85, n: 12 }],
    distribution: [[0.55, 0.25, 0.20], [0.33, 0.30, 0.37], [0.20, 0.25, 0.55]],
    loto: [
      { tournament: 'WC 2018', matches: 64, accuracy: 0.55, baseline: 0.48, edge: 0.07, logLoss: 0.98, brier: 0.61 },
      { tournament: 'WC 2022', matches: 64, accuracy: 0.59, baseline: 0.50, edge: 0.09, logLoss: 0.95, brier: 0.60 },
      { tournament: 'EURO 2024', matches: 51, accuracy: 0.53, baseline: 0.47, edge: 0.06, logLoss: 1.0, brier: 0.62 },
    ],
    correlation: { features: ['elo_diff', 'fifa_rank_gap', 'form_goals_diff', 'form_xg_diff', 'rest_days_diff', 'is_knockout'], matrix: [[1, 0.62, 0.21, 0.25, 0.02, 0.0], [0.62, 1, 0.18, 0.2, 0.01, 0.0], [0.21, 0.18, 1, 0.55, 0.03, -0.04], [0.25, 0.2, 0.55, 1, 0.02, -0.03], [0.02, 0.01, 0.03, 0.02, 1, 0.08], [0.0, 0.0, -0.04, -0.03, 0.08, 1]] },
    metrics: { accuracy: 0.594, logLoss: 0.95, brier: 0.6, baseline: 0.50, nTrain: 115, nTest: 64, trainTournaments: ['WC 2018', 'EURO 2020'], testTournaments: ['WC 2022'] },
  }, 20000)
