import { Settings, Database, Brain, Activity, Github } from 'lucide-react'
import { Card } from '../ui.jsx'

const STACK = [
  { icon: Database, label: 'Data', text: 'PostgreSQL · 9 tournaments · 4 sources cleaned with SQL (entity resolution, dedup, idempotent upserts, analytical views).' },
  { icon: Brain, label: 'ML', text: 'Leakage-free multinomial logistic regression (Elo + form). Temporal hold-out, Brier 0.62, +7 pts over a FIFA-rank baseline.' },
  { icon: Activity, label: 'Simulation', text: '10,000-run Monte Carlo bracket (Poisson scorelines from Elo strength) → advancement probabilities + the predicted tree.' },
]

export default function SettingsTab() {
  return (
    <div className="space-y-5">
      <Card title="About this platform" subtitle="World Cup 2026 Predictive Analyzer" icon={Settings}>
        <p className="text-sm leading-relaxed text-turf-800">
          An end-to-end analytics platform: a cleaned multi-tournament database, a leakage-free
          match-prediction model, and a Monte Carlo bracket simulator — surfaced through this React
          dashboard. The numbers shown mirror the real model output; wiring the live backend is a
          one-file change (<code className="rounded bg-turf-100 px-1">src/data/api.js</code>).
        </p>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {STACK.map((s) => (
          <Card key={s.label} title={s.label} icon={s.icon}>
            <p className="text-sm leading-relaxed text-turf-700">{s.text}</p>
          </Card>
        ))}
      </div>

      <Card title="Live data status" icon={Activity} accent="gold">
        <p className="text-sm leading-relaxed text-turf-800">
          The app is built to auto-update as matches finish. The free open-data feeds
          (openfootball, football-data.org) currently publish <b>0 finished WC 2026 matches</b> —
          there are no live results to show <i>yet</i>. The moment those feeds populate, the
          standings, scorers, and bracket update on their own.
        </p>
      </Card>

      <div className="flex items-center gap-2 text-xs text-turf-600/70">
        <Github className="h-4 w-4" /> Built by Vivek Patel · Class of 2028 · open data (StatsBomb, openfootball, Fjelstul)
      </div>
    </div>
  )
}
