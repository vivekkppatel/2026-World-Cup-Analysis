import { useEffect, useMemo, useState } from 'react'
import { Shield, Search } from 'lucide-react'
import { Card, Flag } from '../ui.jsx'
import { getTeamStats } from '../../data/api.js'

export default function TeamStats() {
  const [teams, setTeams] = useState([])
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState('titleOdds')

  useEffect(() => { getTeamStats().then(setTeams) }, [])

  const rows = useMemo(() => {
    const filtered = teams.filter((t) => t.team.toLowerCase().includes(query.toLowerCase()))
    return [...filtered].sort((a, b) =>
      sortKey === 'fifaRank' ? a.fifaRank - b.fifaRank : b[sortKey] - a[sortKey])
  }, [teams, query, sortKey])

  const cols = [
    { key: 'fifaRank', label: 'FIFA Rank' },
    { key: 'strength', label: 'Model Strength' },
    { key: 'titleOdds', label: 'Title Odds %' },
  ]

  return (
    <div className="space-y-5">
      <Card title="Team Explorer" subtitle="Historical strength & current form" icon={Shield}>
        {/* Filter bar */}
        <div className="mb-4 flex items-center gap-2 rounded-xl bg-turf-50 px-3 py-2 ring-1 ring-turf-800/10">
          <Search className="h-4 w-4 text-turf-600" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter teams…"
            className="w-full bg-transparent text-sm text-turf-900 placeholder:text-turf-600/50 focus:outline-none"
          />
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
              <th className="pb-2 font-semibold">Team</th>
              {cols.map((c) => (
                <th
                  key={c.key}
                  onClick={() => setSortKey(c.key)}
                  className={`cursor-pointer pb-2 text-right font-semibold transition hover:text-turf-800
                    ${sortKey === c.key ? 'text-turf-800' : ''}`}
                >
                  {c.label}{sortKey === c.key ? ' ↓' : ''}
                </th>
              ))}
              <th className="pb-2 text-right font-semibold">Recent</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.team} className="border-t border-turf-100 transition hover:bg-turf-50/60">
                <td className="py-2.5">
                  <span className="flex items-center gap-2">
                    <Flag team={t.team} w={22} />
                    <span className="font-semibold text-turf-900">{t.team}</span>
                  </span>
                </td>
                <td className="py-2.5 text-right tabular-nums text-turf-700">#{t.fifaRank}</td>
                <td className="py-2.5 text-right tabular-nums text-turf-700">{t.strength}</td>
                <td className="py-2.5 text-right font-bold tabular-nums text-wc-purple">{t.titleOdds}%</td>
                <td className="py-2.5 text-right">
                  <span className="inline-flex gap-1">
                    {(t.recentForm ? t.recentForm.split(' ') : []).map((r, i) => (
                      <span
                        key={i}
                        className={`grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold text-white
                          ${r === 'W' ? 'bg-turf-400' : r === 'D' ? 'bg-turf-200 text-turf-800' : 'bg-wc-red'}`}
                      >
                        {r}
                      </span>
                    ))}
                    {!t.recentForm && <span className="text-xs text-turf-600/60">—</span>}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-turf-600/70">
          Click a column header to sort. <b>Model Strength</b> blends World-Cup Elo, current FIFA
          rank, and recent-tournament form — why Spain (Euro 2024 winners) rate as contenders and
          the host USA doesn't top the table.
        </p>
      </Card>
    </div>
  )
}
