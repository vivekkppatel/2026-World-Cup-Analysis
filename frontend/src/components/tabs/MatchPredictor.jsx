import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Swords, Target, Grid3x3, Layers } from 'lucide-react'
import { Card, Flag } from '../ui.jsx'
import { getTeams, getMatchPredict } from '../../data/api.js'

const TURF = '#2E7D32', LIME = '#9BE800', PURPLE = '#6D28D9', GREY = '#94a3b8'

function TeamSelect({ label, value, teams, onChange, exclude }) {
  return (
    <label className="flex-1">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-turf-600/80">{label}</span>
      <div className="flex items-center gap-2 rounded-xl bg-white px-3 py-2.5 shadow-card ring-1 ring-turf-800/10">
        <Flag team={value} w={24} />
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-transparent text-sm font-semibold text-turf-900 focus:outline-none"
        >
          {teams.map((t) => (
            <option key={t} value={t} disabled={t === exclude}>{t}</option>
          ))}
        </select>
      </div>
    </label>
  )
}

/** Win / Draw / Loss as a single stacked bar. */
function WDLBar({ home, draw, away, homeTeam, awayTeam }) {
  const seg = [
    { p: home, color: TURF, label: homeTeam },
    { p: draw, color: GREY, label: 'Draw' },
    { p: away, color: PURPLE, label: awayTeam },
  ]
  return (
    <div>
      <div className="flex h-10 overflow-hidden rounded-xl ring-1 ring-turf-800/10">
        {seg.map((s, i) => (
          <motion.div
            key={i}
            initial={{ width: 0 }}
            animate={{ width: `${s.p * 100}%` }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="grid place-items-center text-xs font-bold text-white"
            style={{ background: s.color }}
          >
            {s.p > 0.12 ? `${Math.round(s.p * 100)}%` : ''}
          </motion.div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs font-semibold text-turf-700">
        <span className="flex items-center gap-1"><Flag team={homeTeam} w={16} /> {Math.round(home * 100)}%</span>
        <span style={{ color: GREY }}>Draw {Math.round(draw * 100)}%</span>
        <span className="flex items-center gap-1">{Math.round(away * 100)}% <Flag team={awayTeam} w={16} /></span>
      </div>
    </div>
  )
}

/** Poisson scoreline probability heatmap (home goals × away goals). */
function ScorelineHeatmap({ grid, homeTeam, awayTeam }) {
  const max = Math.max(...grid.flat())
  return (
    <div className="inline-block">
      <div className="mb-1 text-center text-[10px] font-bold uppercase tracking-widest text-turf-600">{awayTeam} goals →</div>
      <div className="flex">
        <div className="mr-1 flex flex-col justify-center">
          <span className="rotate-180 text-[10px] font-bold uppercase tracking-widest text-turf-600" style={{ writingMode: 'vertical-rl' }}>
            {homeTeam} goals →
          </span>
        </div>
        <div>
          {grid.map((row, i) => (
            <div key={i} className="flex">
              {row.map((p, j) => {
                const intensity = p / (max || 1)
                return (
                  <div
                    key={j}
                    className="grid h-9 w-9 place-items-center text-[9px] font-semibold"
                    style={{
                      background: `rgba(155, 232, 0, ${0.12 + intensity * 0.85})`,
                      color: intensity > 0.55 ? '#0b3d12' : '#3a5d12',
                      border: '1px solid rgba(27,94,32,0.08)',
                    }}
                    title={`${i}-${j}: ${(p * 100).toFixed(1)}%`}
                  >
                    {(p * 100).toFixed(0)}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function MatchPredictor() {
  const [teams, setTeams] = useState([])
  const [home, setHome] = useState('France')
  const [away, setAway] = useState('Senegal')
  const [knockout, setKnockout] = useState(false)
  const [pred, setPred] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { getTeams().then(setTeams) }, [])

  useEffect(() => {
    if (home === away) return
    setLoading(true)
    getMatchPredict(home, away, knockout).then((p) => { setPred(p); setLoading(false) })
  }, [home, away, knockout])

  return (
    <div className="space-y-5">
      {/* Matchup picker */}
      <Card title="Match Predictor" subtitle="Poisson scoreline model blended with the ML win model" icon={Swords}>
        <div className="flex flex-col items-end gap-3 sm:flex-row">
          <TeamSelect label="Home / Team A" value={home} teams={teams} onChange={setHome} exclude={away} />
          <div className="pb-3 text-sm font-black text-turf-400">VS</div>
          <TeamSelect label="Away / Team B" value={away} teams={teams} onChange={setAway} exclude={home} />
        </div>
        <label className="mt-3 flex items-center gap-2 text-xs text-turf-700">
          <input type="checkbox" checked={knockout} onChange={(e) => setKnockout(e.target.checked)} className="accent-turf-600" />
          Knockout match (no draws on the day)
        </label>
      </Card>

      {pred && !loading && (
        <>
          <div className="grid gap-5 lg:grid-cols-5">
            {/* Outcome + expected goals */}
            <Card className="lg:col-span-3" title="Win / Draw / Loss" icon={Target}>
              <WDLBar home={pred.home_win} draw={pred.draw} away={pred.away_win} homeTeam={home} awayTeam={away} />
              <div className="mt-5 flex items-center justify-center gap-6 rounded-xl bg-turf-50 py-3">
                <div className="text-center">
                  <Flag team={home} w={28} />
                  <div className="font-display text-2xl text-turf-800">{pred.exp_home_goals}</div>
                  <div className="text-[10px] uppercase tracking-wide text-turf-600">exp. goals</div>
                </div>
                <div className="text-sm font-black text-turf-400">—</div>
                <div className="text-center">
                  <Flag team={away} w={28} />
                  <div className="font-display text-2xl text-turf-800">{pred.exp_away_goals}</div>
                  <div className="text-[10px] uppercase tracking-wide text-turf-600">exp. goals</div>
                </div>
              </div>
            </Card>

            {/* Scoreline heatmap */}
            <Card className="lg:col-span-2" title="Scoreline Probability" subtitle="Poisson grid · darker = more likely" icon={Grid3x3}>
              <div className="overflow-x-auto">
                <ScorelineHeatmap grid={pred.grid} homeTeam={home} awayTeam={away} />
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {pred.top_scorelines.slice(0, 5).map((s) => (
                  <span key={s.score} className="rounded-full bg-turf-100 px-2.5 py-1 text-xs font-bold text-turf-800">
                    {s.score} · {(s.prob * 100).toFixed(0)}%
                  </span>
                ))}
              </div>
            </Card>
          </div>

          {/* Model blend breakdown */}
          <Card title="How the prediction is built" subtitle="Poisson scoreline ⊕ logistic-regression, blended 50/50" icon={Layers}>
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { name: 'Poisson scoreline', d: pred.components.poisson, note: 'From Elo-strength → expected goals' },
                { name: 'ML model (LogReg)', d: pred.components.logreg, note: 'Leakage-free, temporally validated' },
                { name: 'Blended (final)', d: { home: pred.home_win, draw: pred.draw, away: pred.away_win }, note: 'What the bars above show', highlight: true },
              ].map((m) => (
                <div key={m.name} className={`rounded-xl p-3 ring-1 ${m.highlight ? 'bg-wc-purple/5 ring-wc-purple/40' : 'bg-white ring-turf-800/10'}`}>
                  <div className="text-xs font-bold uppercase tracking-wide text-turf-800">{m.name}</div>
                  {m.d ? (
                    <div className="mt-2 flex gap-3 text-sm tabular-nums">
                      <span className="font-bold" style={{ color: TURF }}>{Math.round(m.d.home * 100)}%</span>
                      <span style={{ color: GREY }}>{Math.round(m.d.draw * 100)}%</span>
                      <span className="font-bold" style={{ color: PURPLE }}>{Math.round(m.d.away * 100)}%</span>
                    </div>
                  ) : (
                    <div className="mt-2 text-xs text-turf-600/60">not available for these teams</div>
                  )}
                  <div className="mt-1 text-[11px] text-turf-600/70">{m.note}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-turf-600/70">
              Ensembling a scoreline model with a classifier (the approach in the reference notebooks)
              hedges each model's blind spots — Poisson captures goal distributions, the LogReg captures
              learned form patterns.
            </p>
          </Card>
        </>
      )}
      {loading && <Card title="Computing…"><div className="h-24 animate-pulse rounded-xl bg-turf-100" /></Card>}
    </div>
  )
}
