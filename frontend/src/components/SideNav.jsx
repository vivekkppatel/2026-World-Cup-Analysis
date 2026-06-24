import { motion } from 'framer-motion'
import {
  Trophy, Globe, Swords, Shield, Activity, Users, Gem,
  Network, Dices, Sigma, Settings,
} from 'lucide-react'

export const TABS = [
  { id: 'predictions', label: 'Predictions', icon: Trophy },
  { id: 'overview', label: 'Tournament Overview', icon: Globe },
  { id: 'match', label: 'Match Predictor', icon: Swords },
  { id: 'teams', label: 'Team Stats', icon: Shield },
  { id: 'teamAnalysis', label: 'Team Analysis', icon: Activity },
  { id: 'players', label: 'Player Stats', icon: Users },
  { id: 'valuation', label: 'Player Valuation', icon: Gem },
  { id: 'bracket', label: 'Bracket', icon: Network },
  { id: 'montecarlo', label: 'Monte Carlo', icon: Dices },
  { id: 'regression', label: 'Regression Analysis', icon: Sigma },
  { id: 'settings', label: 'Info', icon: Settings },
]

/** Floating, vertical, pill-shaped navigation fixed to the far right. */
export default function SideNav({ active, onChange }) {
  return (
    <nav className="fixed right-5 top-1/2 z-30 -translate-y-1/2">
      <div className="flex max-h-[92vh] flex-col items-center gap-2 overflow-y-auto rounded-[28px] bg-turf-800/95 p-2 shadow-pill backdrop-blur [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {TABS.map((t) => {
          const Icon = t.icon
          const isActive = active === t.id
          return (
            <button
              key={t.id}
              onClick={() => onChange(t.id)}
              className="group relative grid h-12 w-12 place-items-center rounded-full transition"
              aria-label={t.label}
            >
              {isActive && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-full bg-wc-lime"
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                />
              )}
              <Icon
                className={`relative h-5 w-5 transition ${
                  isActive ? 'text-turf-900' : 'text-turf-100 group-hover:text-wc-lime'
                }`}
              />
              {/* Hover-revealed label (slides out to the left) */}
              <span
                className="pointer-events-none absolute right-14 whitespace-nowrap rounded-lg bg-turf-800 px-3 py-1.5
                           text-xs font-semibold text-white opacity-0 shadow-lg transition
                           group-hover:right-15 group-hover:opacity-100"
              >
                {t.label}
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
