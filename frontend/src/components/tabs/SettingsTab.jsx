import { Database, Brain, Activity, Github } from 'lucide-react'
import { Card } from '../ui.jsx'

const STACK = [
  { icon: Database, label: 'Data', text: 'PostgreSQL · 9 tournaments · 4 sources cleaned with SQL (entity resolution, dedup, idempotent upserts, analytical views).' },
  { icon: Brain, label: 'ML', text: 'Leakage-free multinomial logistic regression (Elo + form). Temporal hold-out, Brier 0.62, +7 pts over a FIFA-rank baseline.' },
  { icon: Activity, label: 'Simulation', text: '10,000-run Monte Carlo bracket (Poisson scorelines from Elo strength) → advancement probabilities + the predicted tree.' },
]

export default function SettingsTab() {
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        {STACK.map((s) => (
          <Card key={s.label} title={s.label} icon={s.icon}>
            <p className="text-sm leading-relaxed text-turf-700">{s.text}</p>
          </Card>
        ))}
      </div>

      <Card title="Live data status" icon={Activity} accent="gold">
        <div className="space-y-2 text-sm leading-relaxed text-turf-800">
          <p>
            <span className="inline-flex items-center gap-1.5 font-semibold text-green-700">
              <span className="h-2 w-2 rounded-full bg-green-500 inline-block" /> ML pipeline live
            </span>
            {' '}— logistic regression predictions &amp; 10,000-run Monte Carlo bracket simulation
            run automatically every day via GitHub Actions and write fresh results to the database.
          </p>
          <p>
            <span className="font-semibold text-turf-900">Group stage is underway.</span>{' '}
            Results in as of June 17: Argentina 3–0 Algeria, Austria 3–1 Jordan, Colombia 3–1 Uzbekistan,
            England 4–2 Croatia, Ghana 1–0 Panama, Portugal 1–1 DR Congo, and more.
            Standings, scorers, and the bracket scorecard update automatically as the open-data feeds
            (openfootball, football-data.org) publish each result.
          </p>
        </div>
      </Card>

      <div className="flex items-center gap-2 text-xs text-turf-600/70">
        <Github className="h-4 w-4" /> Built by Vivek Patel · Class of 2028 · open data (StatsBomb, openfootball, Fjelstul)
      </div>
    </div>
  )
}
