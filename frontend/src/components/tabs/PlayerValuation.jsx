import { useEffect, useState } from 'react'
import { Gem, Search, Star } from 'lucide-react'
import { Card, Flag } from '../ui.jsx'
import { Scatter, Legend } from '../charts.jsx'
import { getPVTournaments, getPlayerValuation } from '../../data/api.js'

const POS_COLOR = { FWD: '#E0003C', MID: '#2563eb', DEF: '#2E7D32', GK: '#C99A06' }
const median = (a) => {
  if (!a.length) return 0
  const s = [...a].sort((x, y) => x - y)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

function CpcsBar({ value }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-turf-100">
        <div className="h-full rounded-full bg-gradient-to-r from-wc-purple to-wc-lime" style={{ width: `${value}%` }} />
      </div>
      <span className="font-bold tabular-nums text-turf-900">{value.toFixed(1)}</span>
    </div>
  )
}

export default function PlayerValuation() {
  const [tournaments, setTournaments] = useState([])
  const [tournament, setTournament] = useState('')
  const [minMinutes, setMinMinutes] = useState(90)
  const [data, setData] = useState({ leaderboard: [], undervalued: [] })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getPVTournaments().then((ts) => {
      setTournaments(ts)
      setTournament(ts.includes('WC 2022') ? 'WC 2022' : ts[0] || '')
    })
  }, [])

  useEffect(() => {
    if (!tournament) return
    setLoading(true)
    getPlayerValuation(tournament, minMinutes).then((d) => { setData(d || { leaderboard: [], undervalued: [] }); setLoading(false) })
  }, [tournament, minMinutes])

  const lb = data.leaderboard || []
  const uv = data.undervalued || []

  const points = lb.map((p) => ({ x: p.minutes, y: p.cpcs, label: p.player, color: POS_COLOR[p.positionGroup] || '#94a3b8' }))
  const midX = median(lb.map((p) => p.minutes))
  const midY = median(lb.map((p) => p.cpcs))
  const maxCpcs = Math.max(...lb.map((p) => p.cpcs), 1)
  const maxMin = Math.max(...lb.map((p) => p.minutes), 1)

  return (
    <div className="space-y-5">
      <Card title="Player Valuation — CPCS" subtitle="Composite Player Contribution Score · risk-adjusted return per minute" icon={Gem} accent="purple">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-turf-600/80">Tournament</span>
            <div className="rounded-xl bg-white px-3 py-2.5 shadow-card ring-1 ring-turf-800/10">
              <select value={tournament} onChange={(e) => setTournament(e.target.value)}
                className="w-full bg-transparent text-sm font-semibold text-turf-900 focus:outline-none">
                {tournaments.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </label>
          <label className="flex-1">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-turf-600/80">Min minutes · {minMinutes}</span>
            <input type="range" min="45" max="400" step="45" value={minMinutes}
              onChange={(e) => setMinMinutes(Number(e.target.value))} className="mt-3 w-full accent-wc-purple" />
          </label>
        </div>
        <div className="mt-3 grid gap-2 text-xs text-turf-600 sm:grid-cols-3">
          <p><b className="text-turf-800">1. Per-90 rates</b> — normalise output by playing time.</p>
          <p><b className="text-turf-800">2. Scale 0–1</b> — each metric across all players.</p>
          <p><b className="text-turf-800">3. Position weights</b> — then scaled to 0–100.</p>
        </div>
      </Card>

      {loading ? (
        <Card title="Computing CPCS…"><div className="h-24 animate-pulse rounded-xl bg-turf-100" /></Card>
      ) : lb.length === 0 ? (
        <Card><p className="text-sm text-turf-600">No player data available for this selection.</p></Card>
      ) : (
        <>
          <Card title="CPCS Leaderboard" subtitle={`Top ${Math.min(30, lb.length)} · ${tournament}`} icon={Star}>
            <div className="max-h-[28rem] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white/95">
                  <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                    <th className="pb-2 font-semibold">Player</th>
                    <th className="pb-2 font-semibold">Team</th>
                    <th className="pb-2 text-center font-semibold">Pos</th>
                    <th className="pb-2 text-center font-semibold">Mins</th>
                    <th className="pb-2 font-semibold">CPCS</th>
                    <th className="pb-2 text-right font-semibold">xG/90</th>
                  </tr>
                </thead>
                <tbody>
                  {lb.slice(0, 30).map((p) => (
                    <tr key={p.player + p.team} className="border-t border-turf-100">
                      <td className="py-1.5"><span className="flex items-center gap-1.5"><Flag team={p.team} w={16} /><span className="font-medium text-turf-900">{p.player}</span></span></td>
                      <td className="py-1.5 text-xs text-turf-600">{p.team}</td>
                      <td className="py-1.5 text-center">
                        <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: POS_COLOR[p.positionGroup] || '#94a3b8' }}>{p.positionGroup}</span>
                      </td>
                      <td className="py-1.5 text-center tabular-nums text-turf-700">{p.minutes}</td>
                      <td className="py-1.5"><CpcsBar value={p.cpcs} /></td>
                      <td className="py-1.5 text-right tabular-nums text-turf-600">{(p.xg_p90 || 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="CPCS vs Minutes — find undervalued players" subtitle="Top-left = high output, low minutes" icon={Search}>
            <Scatter
              points={points} xLabel="Minutes Played" yLabel="CPCS (0–100)" height={400}
              quadrants={{ midX, midY, labels: [
                { x: midX * 0.5, y: maxCpcs * 0.94, text: '⭐ Undervalued' },
                { x: maxMin * 0.82, y: maxCpcs * 0.94, text: '🌟 Stars' },
              ] }}
            />
            <div className="mt-1">
              <Legend items={[{ label: 'FWD', color: POS_COLOR.FWD }, { label: 'MID', color: POS_COLOR.MID }, { label: 'DEF', color: POS_COLOR.DEF }, { label: 'GK', color: POS_COLOR.GK }]} />
            </div>
          </Card>

          <Card title="Undervalued Players" subtitle="Above-median CPCS, below-median minutes — the hidden gems" icon={Gem} accent="gold">
            {uv.length ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                    <th className="pb-2 font-semibold">Player</th>
                    <th className="pb-2 font-semibold">Team</th>
                    <th className="pb-2 text-center font-semibold">Pos</th>
                    <th className="pb-2 text-center font-semibold">Mins</th>
                    <th className="pb-2 text-right font-semibold">CPCS</th>
                    <th className="pb-2 text-right font-semibold">CPCS/90</th>
                    <th className="pb-2 text-right font-semibold">xG/90</th>
                  </tr>
                </thead>
                <tbody>
                  {uv.map((p) => (
                    <tr key={p.player + p.team} className="border-t border-turf-100">
                      <td className="py-1.5"><span className="flex items-center gap-1.5"><Flag team={p.team} w={16} /><span className="font-medium text-turf-900">{p.player}</span></span></td>
                      <td className="py-1.5 text-xs text-turf-600">{p.team}</td>
                      <td className="py-1.5 text-center"><span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: POS_COLOR[p.positionGroup] || '#94a3b8' }}>{p.positionGroup}</span></td>
                      <td className="py-1.5 text-center tabular-nums text-turf-700">{p.minutes}</td>
                      <td className="py-1.5 text-right font-bold tabular-nums text-turf-900">{p.cpcs.toFixed(1)}</td>
                      <td className="py-1.5 text-right tabular-nums text-wc-purple">{(p.efficiency || 0).toFixed(2)}</td>
                      <td className="py-1.5 text-right tabular-nums text-turf-600">{(p.xg_p90 || 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-turf-600">No undervalued players found with current filters.</p>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
