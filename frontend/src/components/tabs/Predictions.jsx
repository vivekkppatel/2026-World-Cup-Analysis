import { useEffect, useState } from 'react'
import { Trophy, TrendingUp, Crosshair } from 'lucide-react'
import { Card, StatCard, BarList, Flag } from '../ui.jsx'
import { getChampionOdds, getScorecard, getTopScorers, getModelCall } from '../../data/api.js'

const FALLBACK_CALL = { champion: 'France', championOdds: 11.9, usaOdds: 8.4, usaCeiling: 'Semifinals' }

export default function Predictions() {
  const [odds, setOdds] = useState([])
  const [scorecard, setScorecard] = useState(null)
  const [scorers, setScorers] = useState([])
  const [call, setCall] = useState(FALLBACK_CALL)

  useEffect(() => {
    getChampionOdds().then(setOdds)
    getScorecard().then(setScorecard)
    getTopScorers().then(setScorers)
    getModelCall().then((c) => setCall(c || FALLBACK_CALL))
  }, [])

  const oddsRows = odds.map((o) => ({
    label: o.team,
    value: o.odds,
    display: `${o.odds}%`,
    color:
      o.team === 'France' ? 'linear-gradient(90deg,#6D28D9,#9BE800)'
      : o.team === 'United States' ? 'linear-gradient(90deg,#E0003C,#E0003C)'
      : 'linear-gradient(90deg,#4CAF50,#9BE800)',
  }))

  return (
    <div className="space-y-5">
      {/* Headline model call — the prediction explicitly revolves around this */}
      <Card accent="purple" title="Model Call" icon={Trophy}>
        <p className="text-lg leading-snug text-turf-900">
          <Flag team={call.champion} w={26} />{' '}
          <b className="font-display text-wc-purple">{call.champion}</b> are the predicted
          champions <span className="font-bold text-turf-600">({call.championOdds}%)</span>.
          {' '}The host <Flag team="United States" w={22} />{' '}
          <b>United States</b> is <b className="text-wc-red">not winning this</b> — a{' '}
          <b>{call.usaOdds}%</b> title shot with a ceiling at the{' '}
          <b>{call.usaCeiling}</b>, eliminated before the final.
        </p>
      </Card>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Predicted Champion" value={call.champion} flag={call.champion} sub={`${call.championOdds}% to win`} accent="purple" />
        <StatCard label="Host (USA)" value={`${call.usaOdds}%`} flag="United States" sub="ceiling: semifinals" accent="red" />
        <StatCard label="Brier Score" value={scorecard?.brier ?? '—'} sub="held-out WC 2022 (lower = better)" accent="turf" />
        <StatCard label="Edge vs Baseline" value={`+${scorecard?.baselineEdge ?? '—'}`} sub="pts over FIFA-rank (LOTO-CV)" accent="gold" />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        {/* Title odds "chart" */}
        <Card className="lg:col-span-3" title="Title Odds" subtitle="Monte Carlo, 10,000 simulations" icon={TrendingUp}>
          <BarList rows={oddsRows} render={(r) => (
            <span className="flex items-center gap-2"><Flag team={r.label} w={20} /><span className="truncate">{r.label}</span></span>
          )} />
        </Card>

        {/* Top scorers table */}
        <Card className="lg:col-span-2" title="Top Scorers" subtitle="WC 2022 · goals vs xG" icon={Crosshair}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                <th className="pb-2 font-semibold">Player</th>
                <th className="pb-2 text-right font-semibold">G</th>
                <th className="pb-2 text-right font-semibold">xG</th>
                <th className="pb-2 text-right font-semibold">+/−</th>
              </tr>
            </thead>
            <tbody>
              {scorers.map((s) => {
                const diff = (s.goals - s.xg).toFixed(1)
                return (
                  <tr key={s.player} className="border-t border-turf-100">
                    <td className="py-2">
                      <span className="flex items-center gap-2">
                        <Flag team={s.team} w={18} />
                        <span className="font-medium text-turf-900">{s.player}</span>
                      </span>
                    </td>
                    <td className="py-2 text-right font-bold tabular-nums">{s.goals}</td>
                    <td className="py-2 text-right tabular-nums text-turf-600">{s.xg}</td>
                    <td className={`py-2 text-right font-semibold tabular-nums ${diff >= 0 ? 'text-turf-600' : 'text-wc-red'}`}>
                      {diff >= 0 ? '+' : ''}{diff}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  )
}
