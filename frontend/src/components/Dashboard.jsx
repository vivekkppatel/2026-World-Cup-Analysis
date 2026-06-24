import { useState } from 'react'
import { motion } from 'framer-motion'
import SideNav from './SideNav.jsx'
import { Flag } from './ui.jsx'
import Predictions from './tabs/Predictions.jsx'
import Overview from './tabs/Overview.jsx'
import MatchPredictor from './tabs/MatchPredictor.jsx'
import TeamStats from './tabs/TeamStats.jsx'
import TeamAnalysis from './tabs/TeamAnalysis.jsx'
import PlayerStats from './tabs/PlayerStats.jsx'
import PlayerValuation from './tabs/PlayerValuation.jsx'
import BracketSim from './tabs/BracketSim.jsx'
import MonteCarlo from './tabs/MonteCarlo.jsx'
import Regression from './tabs/Regression.jsx'
import SettingsTab from './tabs/SettingsTab.jsx'

const TAB_COMPONENTS = {
  predictions: Predictions,
  overview: Overview,
  match: MatchPredictor,
  teams: TeamStats,
  teamAnalysis: TeamAnalysis,
  players: PlayerStats,
  valuation: PlayerValuation,
  bracket: BracketSim,
  montecarlo: MonteCarlo,
  regression: Regression,
  settings: SettingsTab,
}

const TAB_TITLES = {
  predictions: 'Predictions & Simulation',
  overview: 'Tournament Overview',
  match: 'Match Predictor',
  teams: 'Team Statistics',
  teamAnalysis: 'Team Analysis',
  players: 'Player Statistics',
  valuation: 'Player Valuation · CPCS',
  bracket: 'Bracket Simulator',
  montecarlo: 'Monte Carlo Simulation',
  regression: 'Regression Analysis',
  settings: 'Platform Info',
}

export default function Dashboard() {
  const [active, setActive] = useState('predictions')
  const ActiveTab = TAB_COMPONENTS[active]

  return (
    <div className="min-h-screen w-full">
      {/* Header */}
      <header className="mx-auto max-w-6xl px-6 pt-8 pr-24">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-turf-800 text-2xl shadow-card">⚽</span>
          <div>
            <h1 className="font-display text-2xl leading-none text-turf-900">
              WORLD CUP <span className="text-wc-purple">26</span>
            </h1>
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-widest text-turf-600">
              Predictive Analyzer ·
              <Flag team="United States" w={18} />
              <Flag team="Canada" w={18} />
              <Flag team="Mexico" w={18} />
            </p>
          </div>
        </div>
      </header>

      {/* Content — crossfades between tabs */}
      <main className="mx-auto max-w-6xl px-6 pb-16 pr-24 pt-6">
        <h2 className="mb-4 text-sm font-bold uppercase tracking-widest text-turf-600/70">
          {TAB_TITLES[active]}
        </h2>
        {/* Keyed remount crossfade — changing `active` swaps the key, so the
            new tab mounts and fades in. (Avoids the AnimatePresence mode="wait"
            + StrictMode bug where the exit never resolves and content sticks.) */}
        <motion.div
          key={active}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <ActiveTab />
        </motion.div>
      </main>

      <SideNav active={active} onChange={setActive} />
    </div>
  )
}
