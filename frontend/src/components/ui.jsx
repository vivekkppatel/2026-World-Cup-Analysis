/** Small, reusable presentational components shared across tabs. */
import { motion } from 'framer-motion'
import { FLAG_ISO } from '../data/flags.js'

// Flags come from the bundled `flag-icons` package (local assets, no external
// CDN) — flagcdn.com images failed to load in some environments. Rendered as a
// styled <span> with the `fi fi-<iso>` classes from flag-icons.
export function Flag({ team, w = 22, className = '' }) {
  const iso = FLAG_ISO[team]
  if (!iso) return <span className={`inline-block ${className}`} style={{ width: w }} />
  return (
    <span
      className={`fi fi-${iso} ${className}`}
      title={team}
      style={{
        display: 'inline-block',
        width: `${w}px`,
        height: `${Math.round(w * 0.72)}px`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        borderRadius: '3px',
        boxShadow: 'inset 0 0 0 1px rgba(0,0,0,.1)',
        verticalAlign: '-3px',
      }}
    />
  )
}

export function Card({ title, subtitle, icon: Icon, children, className = '', accent = 'turf' }) {
  const ring = {
    turf: 'before:bg-turf-400',
    purple: 'before:bg-wc-purple',
    red: 'before:bg-wc-red',
    gold: 'before:bg-wc-gold',
  }[accent]
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className={`relative overflow-hidden rounded-2xl bg-white/85 backdrop-blur shadow-card
                  ring-1 ring-turf-800/10 before:absolute before:left-0 before:top-0 before:h-full
                  before:w-1 ${ring} ${className}`}
    >
      <div className="p-5">
        {(title || Icon) && (
          <div className="mb-3 flex items-center gap-2">
            {Icon && <Icon className="h-4 w-4 text-turf-600" />}
            <div>
              {title && <h3 className="text-sm font-bold uppercase tracking-wide text-turf-800">{title}</h3>}
              {subtitle && <p className="text-xs text-turf-600/80">{subtitle}</p>}
            </div>
          </div>
        )}
        {children}
      </div>
    </motion.div>
  )
}

export function StatCard({ label, value, sub, accent = 'turf', flag }) {
  const color = {
    turf: 'text-turf-800', purple: 'text-wc-purple', red: 'text-wc-red', gold: 'text-[#b8950f]',
  }[accent]
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="rounded-2xl bg-white/85 p-4 shadow-card ring-1 ring-turf-800/10"
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-turf-600/80">{label}</div>
      <div className={`mt-1 flex items-center gap-2 font-display text-2xl ${color}`}>
        {flag && <Flag team={flag} w={26} />}
        {value}
      </div>
      {sub && <div className="mt-0.5 text-xs text-turf-600/70">{sub}</div>}
    </motion.div>
  )
}

/** Horizontal bar list (mock "chart" — no chart lib needed). */
export function BarList({ rows, max, render }) {
  const top = max ?? Math.max(...rows.map((r) => r.value))
  return (
    <div className="space-y-2.5">
      {rows.map((r, i) => (
        <div key={r.label} className="flex items-center gap-3">
          <div className="w-32 shrink-0 truncate text-sm font-medium text-turf-800">
            {render ? render(r) : r.label}
          </div>
          <div className="relative h-6 flex-1 overflow-hidden rounded-full bg-turf-100">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(r.value / top) * 100}%` }}
              transition={{ duration: 0.6, delay: i * 0.04, ease: [0.16, 1, 0.3, 1] }}
              className="absolute left-0 top-0 h-full rounded-full"
              style={{ background: r.color || 'linear-gradient(90deg,#4CAF50,#9BE800)' }}
            />
          </div>
          <div className="w-12 shrink-0 text-right text-sm font-bold tabular-nums text-turf-800">
            {r.display ?? r.value}
          </div>
        </div>
      ))}
    </div>
  )
}
