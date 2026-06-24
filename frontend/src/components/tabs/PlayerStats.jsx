import { useEffect, useMemo, useState } from 'react'
import { Users, Target } from 'lucide-react'
import { Card, Flag } from '../ui.jsx'
import { Radar, PALETTE } from '../charts.jsx'
import { getPSTournaments, getPlayerStats } from '../../data/api.js'

const METRICS = {
  'xG / 90': 'xg_p90', 'Goals / 90': 'goals_p90', 'Assists / 90': 'assists_p90',
  'Shots / 90': 'shots_p90', 'Key Passes / 90': 'key_passes_p90', 'Pressures / 90': 'pressures_p90',
}
const RADAR_KEYS = ['goals_p90', 'assists_p90', 'xg_p90', 'shots_p90', 'key_passes_p90', 'pressures_p90']
const RADAR_LABELS = ['Goals/90', 'Assists/90', 'xG/90', 'Shots/90', 'Key Passes/90', 'Pressures/90']

function Select({ label, value, options, onChange }) {
  return (
    <label className="flex-1">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-turf-600/80">{label}</span>
      <div className="rounded-xl bg-white px-3 py-2.5 shadow-card ring-1 ring-turf-800/10">
        <select value={value} onChange={(e) => onChange(e.target.value)}
          className="w-full bg-transparent text-sm font-semibold text-turf-900 focus:outline-none">
          {options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    </label>
  )
}

const pctRank = (pool, key, val) => {
  if (pool.length < 2) return Number(val) || 0
  const below = pool.filter((p) => (Number(p[key]) || 0) < (Number(val) || 0)).length
  return Math.round((below / pool.length) * 100)
}

export default function PlayerStats() {
  const [tournaments, setTournaments] = useState([])
  const [tournament, setTournament] = useState('')
  const [minMinutes, setMinMinutes] = useState(180)
  const [position, setPosition] = useState('All')
  const [metric, setMetric] = useState('xG / 90')
  const [players, setPlayers] = useState([])
  const [pA, setPA] = useState('')
  const [pB, setPB] = useState('')

  useEffect(() => {
    getPSTournaments().then((ts) => {
      setTournaments(ts)
      setTournament(ts.includes('WC 2022') ? 'WC 2022' : ts[0] || '')
    })
  }, [])

  useEffect(() => {
    if (!tournament) return
    getPlayerStats(tournament, minMinutes, position).then(setPlayers)
  }, [tournament, minMinutes, position])

  const positions = useMemo(
    () => ['All', ...[...new Set(players.map((p) => p.position).filter(Boolean))].sort()],
    [players])

  const metricKey = METRICS[metric]
  const ranked = useMemo(
    () => [...players].sort((a, b) => (Number(b[metricKey]) || 0) - (Number(a[metricKey]) || 0)),
    [players, metricKey])
  const top20 = ranked.slice(0, 20)
  const metricMax = Math.max(...top20.map((p) => Number(p[metricKey]) || 0), 0.0001)

  const names = ranked.map((p) => p.player)
  useEffect(() => {
    if (names.length) {
      setPA((cur) => (names.includes(cur) ? cur : names[0]))
      setPB((cur) => (names.includes(cur) ? cur : names[1] || names[0]))
    }
  }, [tournament, players]) // eslint-disable-line

  const radarFor = (name) => {
    const row = players.find((p) => p.player === name)
    if (!row) return null
    return { row, values: RADAR_KEYS.map((k) => pctRank(players, k, row[k])) }
  }
  const rA = radarFor(pA), rB = radarFor(pB)

  return (
    <div className="space-y-5">
      <Card title="Player Stats" subtitle="Per-90 leaderboards · percentile radars" icon={Users}>
        <div className="flex flex-col gap-3 md:flex-row">
          <Select label="Tournament" value={tournament} options={tournaments} onChange={setTournament} />
          <Select label="Position" value={position} options={positions} onChange={setPosition} />
          <Select label="Rank by" value={metric} options={Object.keys(METRICS)} onChange={setMetric} />
          <label className="flex-1">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-turf-600/80">Min minutes · {minMinutes}</span>
            <input type="range" min="45" max="690" step="45" value={minMinutes}
              onChange={(e) => setMinMinutes(Number(e.target.value))}
              className="mt-3 w-full accent-turf-600" />
          </label>
        </div>
      </Card>

      <Card title={`Top 20 — ${metric}`} subtitle={`${tournament} · ≥ ${minMinutes} minutes`} icon={Target}>
        {top20.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                <th className="pb-2 font-semibold">Player</th>
                <th className="pb-2 font-semibold">Team</th>
                <th className="pb-2 text-center font-semibold">Mins</th>
                <th className="pb-2 font-semibold">{metric}</th>
                <th className="pb-2 text-right font-semibold">G/90</th>
                <th className="pb-2 text-right font-semibold">A/90</th>
                <th className="pb-2 text-right font-semibold">xG/90</th>
              </tr>
            </thead>
            <tbody>
              {top20.map((p) => (
                <tr key={p.player + p.team} className="border-t border-turf-100">
                  <td className="py-1.5">
                    <span className="flex items-center gap-1.5">
                      <Flag team={p.team} w={16} />
                      <span className="font-medium text-turf-900">{p.player}</span>
                    </span>
                  </td>
                  <td className="py-1.5 text-xs text-turf-600">{p.team}</td>
                  <td className="py-1.5 text-center tabular-nums text-turf-700">{p.minutes}</td>
                  <td className="py-1.5">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-20 overflow-hidden rounded-full bg-turf-100">
                        <div className="h-full rounded-full bg-gradient-to-r from-turf-500 to-wc-lime"
                          style={{ width: `${((Number(p[metricKey]) || 0) / metricMax) * 100}%` }} />
                      </div>
                      <span className="font-bold tabular-nums text-turf-900">{(Number(p[metricKey]) || 0).toFixed(2)}</span>
                    </div>
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{(Number(p.goals_p90) || 0).toFixed(2)}</td>
                  <td className="py-1.5 text-right tabular-nums">{(Number(p.assists_p90) || 0).toFixed(2)}</td>
                  <td className="py-1.5 text-right tabular-nums text-turf-600">{(Number(p.xg_p90) || 0).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-turf-600">No players match these filters — lower the minutes threshold.</p>
        )}
      </Card>

      <Card title="Player Radar Comparison" subtitle="Each axis is the percentile rank within the current filter" icon={Users}>
        {names.length >= 2 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {[{ sel: pA, set: setPA, r: rA }, { sel: pB, set: setPB, r: rB }].map((side, i) => (
              <div key={i} className="rounded-xl bg-turf-50/60 p-3">
                <select value={side.sel} onChange={(e) => side.set(e.target.value)}
                  className="mb-2 w-full rounded-lg bg-white px-2 py-1.5 text-sm font-semibold text-turf-900 shadow-card ring-1 ring-turf-800/10 focus:outline-none">
                  {names.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
                {side.r && (
                  <>
                    <Radar axes={RADAR_LABELS} series={[{ name: side.sel, color: PALETTE[i === 0 ? 0 : 1], values: side.r.values }]} />
                    <p className="text-center text-xs text-turf-600">
                      <Flag team={side.r.row.team} w={14} /> {side.r.row.team} · {side.r.row.position} · {side.r.row.minutes} mins
                    </p>
                  </>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-turf-600">Need at least two players in the pool to compare.</p>
        )}
      </Card>
    </div>
  )
}
