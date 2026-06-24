import { useEffect, useState } from 'react'
import { Globe, Crosshair, ListChecks, CalendarDays } from 'lucide-react'
import { Card, StatCard, Flag } from '../ui.jsx'
import { HBars, PALETTE } from '../charts.jsx'
import { getPulse, getStandings, getOverviewScorers, getResults, getFixtures } from '../../data/api.js'

const titleStage = (s) =>
  String(s || '').toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

function GroupTable({ group, rows }) {
  return (
    <div className="rounded-xl bg-white p-3 shadow-card ring-1 ring-turf-800/10">
      <div className="mb-2 text-xs font-bold uppercase tracking-wide text-wc-purple">Group {group}</div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wide text-turf-600/70">
            <th className="pb-1 font-semibold">Team</th>
            <th className="pb-1 text-center font-semibold">P</th>
            <th className="pb-1 text-center font-semibold">W</th>
            <th className="pb-1 text-center font-semibold">D</th>
            <th className="pb-1 text-center font-semibold">L</th>
            <th className="pb-1 text-center font-semibold">GD</th>
            <th className="pb-1 text-right font-semibold">Pts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.team} className={`border-t border-turf-100 ${r.position <= 2 ? 'bg-turf-50/70' : ''}`}>
              <td className="py-1.5">
                <span className="flex items-center gap-1.5">
                  <Flag team={r.team} w={16} />
                  <span className="truncate font-medium text-turf-900">{r.team}</span>
                </span>
              </td>
              <td className="py-1.5 text-center tabular-nums">{r.played}</td>
              <td className="py-1.5 text-center tabular-nums">{r.won}</td>
              <td className="py-1.5 text-center tabular-nums">{r.drawn}</td>
              <td className="py-1.5 text-center tabular-nums">{r.lost}</td>
              <td className="py-1.5 text-center tabular-nums">{r.goals_for - r.goals_against}</td>
              <td className="py-1.5 text-right font-bold tabular-nums text-turf-900">{r.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Overview() {
  const [pulse, setPulse] = useState(null)
  const [standings, setStandings] = useState([])
  const [scorers, setScorers] = useState([])
  const [results, setResults] = useState([])
  const [fixtures, setFixtures] = useState([])

  useEffect(() => {
    getPulse().then(setPulse)
    getStandings().then(setStandings)
    getOverviewScorers('WC 2026').then(setScorers)
    getResults('WC 2026').then(setResults)
    getFixtures().then(setFixtures)
  }, [])

  const played = pulse?.played ?? 0
  const total = pulse?.total ?? 104
  const goals = pulse?.goals ?? 0

  const groups = [...new Set(standings.map((r) => r.group_name).filter(Boolean))].sort()
  const byGroup = (g) => standings.filter((r) => r.group_name === g).sort((a, b) => a.position - b.position)

  const scorerRows = scorers.slice(0, 10).map((s) => ({ label: s.player, value: s.goals }))

  return (
    <div className="space-y-5">
      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Matches Played" value={played} sub={`of ${total}`} accent="purple" />
        <StatCard label="Remaining" value={Math.max(0, total - played)} sub="fixtures to play" accent="turf" />
        <StatCard label="Goals Scored" value={goals} sub="across the tournament" accent="red" />
        <StatCard label="Goals / Match" value={(goals / Math.max(played, 1)).toFixed(2)} sub="scoring rate" accent="gold" />
      </div>

      {/* Group standings */}
      <Card title="Group Standings" subtitle="Computed live from results · top two highlighted" icon={Globe}>
        {groups.length ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {groups.map((g) => <GroupTable key={g} group={g} rows={byGroup(g)} />)}
          </div>
        ) : (
          <p className="text-sm text-turf-600">⚽ Standings fill in automatically as group-stage matches finish.</p>
        )}
      </Card>

      {/* Scorers + recent results */}
      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2" title="Top Scorers" subtitle="WC 2026 · goals" icon={Crosshair}>
          {scorerRows.length ? (
            <HBars data={scorerRows} color={PALETTE[0]} valueFmt={(v) => `${v}`} />
          ) : (
            <p className="text-sm text-turf-600">The scorer board fills in as goals are scored.</p>
          )}
        </Card>

        <Card className="lg:col-span-3" title="Recent Results" subtitle="Most recent first" icon={ListChecks}>
          {results.length ? (
            <div className="space-y-1.5">
              {results.slice(0, 9).map((m) => (
                <div key={m.fifa_match_num} className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm hover:bg-turf-50">
                  <span className="flex items-center gap-2">
                    <Flag team={m.home_team} w={18} />
                    <span className="font-medium text-turf-900">{m.home_team}</span>
                    <span className="font-display tabular-nums text-turf-800">{m.home_score}–{m.away_score}</span>
                    <span className="font-medium text-turf-900">{m.away_team}</span>
                    <Flag team={m.away_team} w={18} />
                  </span>
                  <span className="text-xs text-turf-600/80">{m.date} · {titleStage(m.stage)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-turf-600">Results appear here as matches finish.</p>
          )}
        </Card>
      </div>

      {/* Upcoming fixtures */}
      <Card title="Upcoming Fixtures" subtitle="Next 12 kickoffs" icon={CalendarDays}>
        {fixtures.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                <th className="pb-2 font-semibold">Kickoff</th>
                <th className="pb-2 font-semibold">Match</th>
                <th className="pb-2 font-semibold">Venue</th>
                <th className="pb-2 text-right font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {fixtures.slice(0, 12).map((f) => (
                <tr key={f.fifa_match_num} className="border-t border-turf-100">
                  <td className="py-2 text-xs text-turf-600">{f.kickoff}</td>
                  <td className="py-2">
                    <span className="flex items-center gap-1.5">
                      <Flag team={f.home_team} w={16} />
                      <span className="font-medium text-turf-900">{f.home_team}</span>
                      <span className="text-turf-400">vs</span>
                      <span className="font-medium text-turf-900">{f.away_team}</span>
                      <Flag team={f.away_team} w={16} />
                    </span>
                  </td>
                  <td className="py-2 text-xs text-turf-600/80">{f.venue}</td>
                  <td className="py-2 text-right text-xs font-semibold text-turf-700">{f.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-turf-600">No upcoming fixtures found.</p>
        )}
      </Card>
    </div>
  )
}
