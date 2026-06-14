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

async function get(path, fallback) {
  try {
    const r = await fetch(`${API_BASE}${path}`, { signal: AbortSignal.timeout(4000) })
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
