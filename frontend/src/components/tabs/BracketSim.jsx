import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Network, Trophy } from 'lucide-react'
import { Flag } from '../ui.jsx'
import { getBracket } from '../../data/api.js'

function Slot({ team, won }) {
  return (
    <div className={`flex items-center gap-2 px-2.5 py-1.5 ${won ? 'bg-wc-lime/90' : ''}`}>
      <Flag team={team} w={18} />
      <span className={`truncate text-xs font-semibold ${won ? 'text-turf-900' : 'text-turf-700'}`}>
        {team}
      </span>
    </div>
  )
}

function Match({ m, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, delay }}
      className="w-36 divide-y divide-turf-100 overflow-hidden rounded-lg bg-white shadow-card ring-1 ring-turf-800/10"
    >
      <Slot team={m.home} won={m.winner === m.home} />
      <Slot team={m.away} won={m.winner === m.away} />
    </motion.div>
  )
}

function Column({ matches, label, delay }) {
  return (
    <div className="flex flex-col items-center justify-around gap-4">
      {label && <div className="text-[10px] font-bold uppercase tracking-widest text-turf-600">{label}</div>}
      {matches.map((m, i) => <Match key={i} m={m} delay={delay + i * 0.05} />)}
    </div>
  )
}

export default function BracketSim() {
  const [b, setB] = useState(null)
  useEffect(() => { getBracket().then(setB) }, [])
  if (!b) return null

  return (
    <div className="space-y-5">
      <div className="rounded-2xl bg-white/85 p-5 shadow-card ring-1 ring-turf-800/10">
        <div className="mb-1 flex items-center gap-2">
          <Network className="h-4 w-4 text-turf-600" />
          <h3 className="text-sm font-bold uppercase tracking-wide text-turf-800">Predicted Bracket</h3>
        </div>
        <p className="mb-5 text-xs text-turf-600/80">
          The model's expected knockout path — favourites advance through a coherent tree. Winners
          highlighted in lime. <b className="text-wc-purple">France</b> lifts the trophy.
        </p>

        <div className="flex items-start justify-between gap-2 overflow-x-auto pb-2">
          {/* Left half */}
          <Column matches={b.left.r16} label="Round of 16" delay={0} />
          <Column matches={b.left.qf} label="Quarters" delay={0.2} />
          <Column matches={b.left.sf} label="Semis" delay={0.4} />

          {/* Final (centre) */}
          <div className="flex min-w-[10rem] flex-col items-center justify-center gap-3 px-2">
            <Trophy className="h-8 w-8 animate-floaty text-wc-gold" />
            <div className="text-[10px] font-bold uppercase tracking-widest text-wc-purple">Final</div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="w-40 divide-y divide-turf-100 overflow-hidden rounded-xl bg-white shadow-pill ring-2 ring-wc-gold"
            >
              <Slot team={b.final.home} won={b.final.winner === b.final.home} />
              <Slot team={b.final.away} won={b.final.winner === b.final.away} />
            </motion.div>
            <div className="flex items-center gap-1.5 rounded-full bg-wc-purple px-3 py-1 text-xs font-bold text-white">
              <Trophy className="h-3 w-3" /> <Flag team={b.final.winner} w={16} /> {b.final.winner}
            </div>
          </div>

          {/* Right half (mirrored) */}
          <Column matches={b.right.sf} label="Semis" delay={0.4} />
          <Column matches={b.right.qf} label="Quarters" delay={0.2} />
          <Column matches={b.right.r16} label="Round of 16" delay={0} />
        </div>
      </div>
    </div>
  )
}
