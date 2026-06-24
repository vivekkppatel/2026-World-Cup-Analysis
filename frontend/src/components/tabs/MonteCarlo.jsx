import { useEffect, useState } from 'react'
import { Dices, Trophy, TrendingUp, Gauge } from 'lucide-react'
import { Card, StatCard, Flag } from '../ui.jsx'
import { HBars, Heatmap, Scatter } from '../charts.jsx'
import { getMonteCarlo } from '../../data/api.js'

export default function MonteCarlo() {
  const [mc, setMc] = useState(null)
  const [topN, setTopN] = useState(16)

  useEffect(() => { getMonteCarlo().then(setMc) }, [])
  if (!mc) return null

  const adv = mc.advancement || []
  const sc = mc.scorecard || { scored: 0 }
  const champ = adv[0]
  const strongest = adv.reduce((a, b) => (b.strength > (a?.strength ?? -1) ? b : a), null)
  const show = adv.slice(0, topN)

  const oddsRows = show.map((t) => ({
    label: t.team, value: t.champion,
    color: t.team === mc.champion ? 'linear-gradient(90deg,#6D28D9,#9BE800)' : undefined,
  }))
  const funnelCols = ['R32', 'R16', 'QF', 'SF', 'Final', 'Champion']
  const funnelMatrix = show.map((t) => [t.r32, t.r16, t.qf, t.sf, t.final, t.champion])
  const scatterPts = adv.map((t) => ({ x: t.strength, y: t.champion, label: t.team }))

  return (
    <div className="space-y-5">
      <Card accent="purple" title={`Monte Carlo — ${mc.nSims?.toLocaleString?.() || mc.nSims} simulations`} icon={Dices}>
        <p className="text-lg leading-snug text-turf-900">
          {champ && <><Flag team={champ.team} w={26} /> <b className="font-display text-wc-purple">{champ.team}</b> are the simulated champions
          <span className="font-bold text-turf-600"> ({champ.champion}%)</span>.</>}
          {' '}These are advancement <b>distributions</b> across {mc.nSims?.toLocaleString?.() || mc.nSims} simulated
          tournaments — the way you'd price a path-dependent option, not a single guessed bracket.
        </p>
      </Card>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Predicted Champion" value={champ?.team || '—'} flag={champ?.team} sub={`${champ?.champion ?? '—'}% to win`} accent="purple" />
        <StatCard label="Champion Odds" value={`${champ?.champion ?? '—'}%`} sub="most likely winner" accent="gold" />
        <StatCard label="Strength Leader" value={`${strongest?.strength ?? '—'}`} flag={strongest?.team} sub={`${strongest?.team || ''} · Elo`} accent="turf" />
        <StatCard label="Predictions Scored" value={sc.scored || 0} sub={sc.hitRate != null ? `${sc.hitRate}% hit rate` : 'awaiting knockouts'} accent="red" />
      </div>

      <Card title="Simulation depth" subtitle={`Show top ${topN} teams`} icon={Gauge}>
        <input type="range" min="8" max="48" step="4" value={topN}
          onChange={(e) => setTopN(Number(e.target.value))} className="w-full accent-wc-purple" />
      </Card>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2" title="Title Odds" subtitle="P(win the cup)" icon={Trophy}>
          <HBars data={oddsRows} valueFmt={(v) => `${v}%`} />
        </Card>
        <Card className="lg:col-span-3" title="Advancement Funnel" subtitle="P(reach each round) — survival decays each step" icon={TrendingUp}>
          <Heatmap rows={show.map((t) => t.team)} cols={funnelCols} matrix={funnelMatrix}
            scale="seq" fmt={(v) => `${Math.round(v)}`} />
        </Card>
      </div>

      <Card title="Strength vs Title Odds" subtitle="Team strength (Elo) against champion probability" icon={TrendingUp}>
        <Scatter points={scatterPts} xLabel="Team strength (Elo)" yLabel="Champion %" height={360} color="#6D28D9" />
      </Card>

      <Card title="Model Scorecard" subtitle="Updates as knockout matches finish · lower Brier = better" icon={Gauge}>
        {sc.scored > 0 ? (
          <>
            <div className="mb-3 grid grid-cols-3 gap-4">
              <StatCard label="Hit Rate" value={`${sc.hitRate}%`} accent="turf" />
              <StatCard label="Brier Score" value={sc.brier} sub="lower is better" accent="gold" />
              <StatCard label="Avg Confidence" value={`${sc.avgConf}%`} accent="purple" />
            </div>
            {sc.byStage?.length > 0 && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                    <th className="pb-2 font-semibold">Round</th>
                    <th className="pb-2 text-center font-semibold">Matches</th>
                    <th className="pb-2 text-right font-semibold">Hit %</th>
                    <th className="pb-2 text-right font-semibold">Brier</th>
                  </tr>
                </thead>
                <tbody>
                  {sc.byStage.map((r) => (
                    <tr key={r.round} className="border-t border-turf-100">
                      <td className="py-1.5 font-medium text-turf-900">{r.round}</td>
                      <td className="py-1.5 text-center tabular-nums">{r.matches}</td>
                      <td className="py-1.5 text-right tabular-nums">{r.hitRate}%</td>
                      <td className="py-1.5 text-right tabular-nums text-turf-600">{r.brier}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        ) : (
          <p className="text-sm text-turf-600">
            No knockout matches have finished yet — the scorecard fills in from the Round of 32 onward. The group stage runs first.
          </p>
        )}
      </Card>
    </div>
  )
}
