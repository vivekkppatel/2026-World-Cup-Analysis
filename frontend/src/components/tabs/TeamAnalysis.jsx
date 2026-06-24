import { useEffect, useState } from 'react'
import { Activity, LineChart, Gauge, Swords } from 'lucide-react'
import { Card, StatCard, Flag } from '../ui.jsx'
import { VBars, GroupedHBars, Legend, PALETTE } from '../charts.jsx'
import { getTATournaments, getTATeams, getTeamAnalysis } from '../../data/api.js'

function Select({ label, value, options, onChange, exclude }) {
  return (
    <label className="flex-1">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-turf-600/80">{label}</span>
      <div className="flex items-center gap-2 rounded-xl bg-white px-3 py-2.5 shadow-card ring-1 ring-turf-800/10">
        <select value={value} onChange={(e) => onChange(e.target.value)}
          className="w-full bg-transparent text-sm font-semibold text-turf-900 focus:outline-none">
          {options.map((o) => <option key={o} value={o} disabled={o === exclude}>{o}</option>)}
        </select>
      </div>
    </label>
  )
}

const avg = (arr, key) => (arr.length ? arr.reduce((s, r) => s + (Number(r[key]) || 0), 0) / arr.length : 0)
const resultOf = (m) => (m.goals_scored > m.goals_conceded ? 'W' : m.goals_scored === m.goals_conceded ? 'D' : 'L')

export default function TeamAnalysis() {
  const [tournaments, setTournaments] = useState([])
  const [tournament, setTournament] = useState('')
  const [teams, setTeams] = useState([])
  const [team, setTeam] = useState('')
  const [opponent, setOpponent] = useState('')
  const [matches, setMatches] = useState([])
  const [oppMatches, setOppMatches] = useState([])

  useEffect(() => {
    getTATournaments().then((ts) => {
      setTournaments(ts)
      setTournament(ts.includes('WC 2022') ? 'WC 2022' : ts[0] || '')
    })
  }, [])

  useEffect(() => {
    if (!tournament) return
    getTATeams(tournament).then((ts) => {
      setTeams(ts)
      setTeam(ts[0] || '')
      setOpponent(ts[1] || ts[0] || '')
    })
  }, [tournament])

  useEffect(() => {
    if (!tournament || !team) return
    getTeamAnalysis(tournament, team).then(setMatches)
  }, [tournament, team])

  useEffect(() => {
    if (!tournament || !opponent) return
    getTeamAnalysis(tournament, opponent).then(setOppMatches)
  }, [tournament, opponent])

  const wins = matches.filter((m) => resultOf(m) === 'W').length
  const draws = matches.filter((m) => resultOf(m) === 'D').length
  const losses = matches.filter((m) => resultOf(m) === 'L').length
  const goals = matches.reduce((s, m) => s + (m.goals_scored || 0), 0)

  const cats = matches.map((m, i) => m.opponent || m.date || `M${i + 1}`)
  const xgSeries = [
    { name: 'xG', color: PALETTE[0], values: matches.map((m) => Number(m.xg) || 0) },
    { name: 'Goals', color: PALETTE[2], values: matches.map((m) => Number(m.goals_scored) || 0) },
  ]

  const h2hMetrics = [
    { label: 'Avg xG', a: avg(matches, 'xg'), b: avg(oppMatches, 'xg') },
    { label: 'Avg Shots', a: avg(matches, 'shots'), b: avg(oppMatches, 'shots') },
    { label: 'Avg Passes', a: avg(matches, 'passes'), b: avg(oppMatches, 'passes') },
    { label: 'Avg Pressures', a: avg(matches, 'pressures'), b: avg(oppMatches, 'pressures') },
    { label: 'Goals/Match', a: avg(matches, 'goals_scored'), b: avg(oppMatches, 'goals_scored') },
  ]

  return (
    <div className="space-y-5">
      <Card title="Team Analysis" subtitle="Event-level performance across six tournaments" icon={Activity}>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Select label="Tournament" value={tournament} options={tournaments} onChange={setTournament} />
          <Select label="Team" value={team} options={teams} onChange={setTeam} exclude={opponent} />
          <Select label="Compare vs" value={opponent} options={teams} onChange={setOpponent} exclude={team} />
        </div>
      </Card>

      {matches.length === 0 ? (
        <Card><p className="text-sm text-turf-600">No event data for this selection.</p></Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <StatCard label="Played" value={matches.length} accent="purple" flag={team} />
            <StatCard label="W / D / L" value={`${wins}/${draws}/${losses}`} accent="turf" />
            <StatCard label="Goals" value={goals} accent="red" />
            <StatCard label="Avg xG" value={avg(matches, 'xg').toFixed(2)} accent="gold" />
            <StatCard label="Avg Shots" value={avg(matches, 'shots').toFixed(1)} accent="turf" />
          </div>

          <Card title="xG by Match" subtitle="Expected goals vs goals actually scored" icon={LineChart}>
            <VBars categories={cats} series={xgSeries} yFmt={(v) => v.toFixed(1)} height={260} />
            <div className="mt-2"><Legend items={[{ label: 'xG', color: PALETTE[0] }, { label: 'Goals', color: PALETTE[2] }]} /></div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Passing Volume" subtitle="Total passes per match" icon={Gauge}>
              <VBars categories={cats} series={[{ name: 'Passes', color: PALETTE[4], values: matches.map((m) => Number(m.passes) || 0) }]} height={240} />
            </Card>
            <Card title="Press Intensity" subtitle="Pressures applied per match" icon={Gauge}>
              <VBars categories={cats} series={[{ name: 'Pressures', color: PALETTE[1], values: matches.map((m) => Number(m.pressures) || 0) }]} height={240} />
            </Card>
          </div>

          <Card title="Head-to-Head" subtitle={`${team} vs ${opponent} · tournament averages`} icon={Swords}>
            <GroupedHBars
              categories={h2hMetrics.map((m) => m.label)}
              series={[
                { name: team, color: PALETTE[0], values: h2hMetrics.map((m) => m.a) },
                { name: opponent, color: PALETTE[2], values: h2hMetrics.map((m) => m.b) },
              ]}
              valueFmt={(v) => v.toFixed(1)}
              height={210}
            />
            <div className="mt-2"><Legend items={[{ label: team, color: PALETTE[0] }, { label: opponent, color: PALETTE[2] }]} /></div>
          </Card>
        </>
      )}
    </div>
  )
}
