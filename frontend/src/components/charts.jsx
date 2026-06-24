/**
 * charts.jsx — dependency-free SVG chart primitives.
 *
 * These mirror the Plotly visuals from the Streamlit analytics app without
 * adding a charting dependency, matching the dashboard's hand-built style
 * (see ui.jsx / MatchPredictor.jsx). All are themed for LIGHT surfaces
 * (white cards, dark text). SVGs are responsive via viewBox + width:100%.
 *
 * Exports: HBars, GroupedHBars, VBars, Scatter, Radar, Heatmap, Legend, PALETTE
 */
import { motion } from 'framer-motion'

const INK = '#1f2937'
const MUTED = '#64748b'
const GRID = '#e5e7eb'

// Series palette — chosen to read clearly on white (bright lime is reserved
// for accents/highlights, not large fills where contrast suffers).
export const PALETTE = ['#2E7D32', '#6D28D9', '#C99A06', '#E0003C', '#2563eb', '#0891b2']

const fmtNum = (v, d = 2) => (v == null || Number.isNaN(v) ? '—' : Number(v).toFixed(d))

// ── tiny colour helpers (for heatmap scales) ────────────────────────────────
function lerp(a, b, t) {
  return Math.round(a + (b - a) * t)
}
function rgb(c) {
  const h = c.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}
function mix(c1, c2, t) {
  const a = rgb(c1), b = rgb(c2)
  return `rgb(${lerp(a[0], b[0], t)},${lerp(a[1], b[1], t)},${lerp(a[2], b[2], t)})`
}

/** Sequential white→lime fill for 0..1 intensity. */
export const seqColor = (t) => mix('#f1f5f9', '#65a30d', Math.max(0, Math.min(1, t)))
/** Diverging purple(-1)→white(0)→green(+1) for correlations. */
export const divColor = (v) => (v >= 0 ? mix('#ffffff', '#2E7D32', v) : mix('#ffffff', '#6D28D9', -v))

// ── Legend ──────────────────────────────────────────────────────────────────
export function Legend({ items }) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs font-semibold text-turf-700">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  )
}

/**
 * HBars — single-series horizontal bars with a value axis.
 * data: [{ label, value, color? }]
 */
export function HBars({ data, color = PALETTE[0], valueFmt = (v) => fmtNum(v, 1), height }) {
  if (!data?.length) return null
  const W = 520, padL = 130, padR = 44, padT = 8, padB = 8
  const rowH = 26, gap = 8
  const innerH = data.length * (rowH + gap) - gap
  const H = height || innerH + padT + padB
  const max = Math.max(...data.map((d) => d.value), 0.0001)
  const x = (v) => padL + (v / max) * (W - padL - padR)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="bar chart">
      {data.map((d, i) => {
        const y = padT + i * (rowH + gap)
        const w = Math.max(2, x(d.value) - padL)
        return (
          <g key={d.label}>
            <text x={padL - 8} y={y + rowH / 2} textAnchor="end" dominantBaseline="central"
              fontSize="11.5" fill={INK} className="font-medium">
              {d.label.length > 18 ? d.label.slice(0, 17) + '…' : d.label}
            </text>
            <rect x={padL} y={y} width={W - padL - padR} height={rowH} rx="5" fill="#f1f5f9" />
            <motion.rect initial={{ width: 0 }} animate={{ width: w }}
              transition={{ duration: 0.5, delay: i * 0.03, ease: [0.16, 1, 0.3, 1] }}
              x={padL} y={y} height={rowH} rx="5" fill={d.color || color} />
            <text x={x(d.value) + 6} y={y + rowH / 2} dominantBaseline="central"
              fontSize="11" fill={INK} className="font-bold tabular-nums">
              {valueFmt(d.value)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/**
 * GroupedHBars — multi-series horizontal bars per category, with a value axis
 * that supports NEGATIVE values (zero-centred). Optional vertical reference line.
 * categories: [string]; series: [{ name, color, values: number[] }]
 */
export function GroupedHBars({ categories, series, valueFmt = (v) => fmtNum(v, 2),
  refLine = null, height }) {
  if (!categories?.length || !series?.length) return null
  const W = 540, padL = 132, padR = 20, padT = 10, padB = 26
  const bandH = 34
  const H = height || categories.length * bandH + padT + padB
  const all = series.flatMap((s) => s.values)
  let lo = Math.min(0, ...all), hi = Math.max(0, ...all)
  if (refLine != null) { lo = Math.min(lo, refLine); hi = Math.max(hi, refLine) }
  const span = (hi - lo) || 1
  const x = (v) => padL + ((v - lo) / span) * (W - padL - padR)
  const zeroX = x(0)
  const subH = (bandH - 8) / series.length

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="grouped bar chart">
      {/* zero / baseline axis */}
      <line x1={zeroX} y1={padT} x2={zeroX} y2={H - padB} stroke={GRID} strokeWidth="1.5" />
      {refLine != null && (
        <line x1={x(refLine)} y1={padT} x2={x(refLine)} y2={H - padB}
          stroke={MUTED} strokeWidth="1" strokeDasharray="4 3" />
      )}
      {categories.map((cat, ci) => {
        const top = padT + ci * bandH
        return (
          <g key={cat}>
            <text x={padL - 8} y={top + bandH / 2} textAnchor="end" dominantBaseline="central"
              fontSize="11" fill={INK} className="font-medium">
              {cat.length > 18 ? cat.slice(0, 17) + '…' : cat}
            </text>
            {series.map((s, si) => {
              const v = s.values[ci]
              const bx = Math.min(zeroX, x(v))
              const bw = Math.max(1.5, Math.abs(x(v) - zeroX))
              const y = top + 4 + si * subH
              return (
                <motion.rect key={s.name} initial={{ width: 0 }} animate={{ width: bw }}
                  transition={{ duration: 0.5, delay: ci * 0.02, ease: [0.16, 1, 0.3, 1] }}
                  x={bx} y={y} height={subH - 2} rx="2.5" fill={s.color}>
                  <title>{`${cat} · ${s.name}: ${valueFmt(v)}`}</title>
                </motion.rect>
              )
            })}
          </g>
        )
      })}
    </svg>
  )
}

/**
 * VBars — vertical bars, optionally grouped (multi-series).
 * categories: [string]; series: [{ name, color, values: number[] }]
 */
export function VBars({ categories, series, yFmt = (v) => fmtNum(v, 0), height = 240, yMax }) {
  if (!categories?.length || !series?.length) return null
  const W = 560, padL = 38, padR = 12, padT = 12, padB = 40
  const H = height
  const max = yMax || Math.max(...series.flatMap((s) => s.values), 0.0001)
  const innerW = W - padL - padR, innerH = H - padT - padB
  const bandW = innerW / categories.length
  const groupW = bandW * 0.72
  const barW = groupW / series.length
  const y = (v) => padT + innerH - (v / max) * innerH

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="column chart">
      {/* y gridlines */}
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={padL} y1={y(max * t)} x2={W - padR} y2={y(max * t)} stroke={GRID} strokeWidth="1" />
          <text x={padL - 6} y={y(max * t)} textAnchor="end" dominantBaseline="central"
            fontSize="9.5" fill={MUTED}>{yFmt(max * t)}</text>
        </g>
      ))}
      {categories.map((cat, ci) => {
        const gx = padL + ci * bandW + (bandW - groupW) / 2
        return (
          <g key={cat}>
            {series.map((s, si) => {
              const v = s.values[ci]
              const bh = Math.max(1, (v / max) * innerH)
              const bx = gx + si * barW
              return (
                <motion.rect key={s.name} initial={{ height: 0, y: padT + innerH }}
                  animate={{ height: bh, y: padT + innerH - bh }}
                  transition={{ duration: 0.5, delay: ci * 0.02, ease: [0.16, 1, 0.3, 1] }}
                  x={bx + 1} width={Math.max(1, barW - 2)} rx="2.5" fill={s.color}>
                  <title>{`${cat} · ${s.name}: ${yFmt(v)}`}</title>
                </motion.rect>
              )
            })}
            <text x={padL + ci * bandW + bandW / 2} y={H - padB + 14} textAnchor="middle"
              fontSize="10" fill={INK}>
              {cat.length > 9 ? cat.slice(0, 8) + '…' : cat}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/**
 * Scatter — x/y points with axes. Optional y=x diagonal, ordered connecting
 * line, and quadrant guide lines/labels.
 * points: [{ x, y, label?, color?, r? }]
 */
export function Scatter({ points, xLabel = '', yLabel = '', diagonal = false, connect = false,
  quadrants = null, xDomain, yDomain, height = 360, color = PALETTE[0] }) {
  if (!points?.length) return null
  const W = 560, padL = 48, padR = 16, padT = 14, padB = 44
  const H = height
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y)
  const [x0, x1] = xDomain || [Math.min(...xs), Math.max(...xs)]
  const [y0, y1] = yDomain || [Math.min(...ys), Math.max(...ys)]
  const xpad = (x1 - x0) * 0.08 || 1, ypad = (y1 - y0) * 0.08 || 1
  const xmin = x0 - xpad, xmax = x1 + xpad, ymin = y0 - ypad, ymax = y1 + ypad
  const innerW = W - padL - padR, innerH = H - padT - padB
  const px = (v) => padL + ((v - xmin) / (xmax - xmin || 1)) * innerW
  const py = (v) => padT + innerH - ((v - ymin) / (ymax - ymin || 1)) * innerH

  const ticks = (a, b) => { const out = []; for (let i = 0; i <= 4; i++) out.push(a + (b - a) * i / 4); return out }
  const ordered = connect ? [...points].sort((a, b) => a.x - b.x) : points

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="scatter plot">
      {ticks(xmin, xmax).map((t, i) => (
        <g key={`x${i}`}>
          <line x1={px(t)} y1={padT} x2={px(t)} y2={padT + innerH} stroke={GRID} strokeWidth="1" />
          <text x={px(t)} y={padT + innerH + 14} textAnchor="middle" fontSize="9.5" fill={MUTED}>{fmtNum(t, 1)}</text>
        </g>
      ))}
      {ticks(ymin, ymax).map((t, i) => (
        <g key={`y${i}`}>
          <line x1={padL} y1={py(t)} x2={padL + innerW} y2={py(t)} stroke={GRID} strokeWidth="1" />
          <text x={padL - 6} y={py(t)} textAnchor="end" dominantBaseline="central" fontSize="9.5" fill={MUTED}>{fmtNum(t, 1)}</text>
        </g>
      ))}
      {quadrants && (
        <>
          <line x1={px(quadrants.midX)} y1={padT} x2={px(quadrants.midX)} y2={padT + innerH} stroke={MUTED} strokeDasharray="4 3" strokeWidth="1" />
          <line x1={padL} y1={py(quadrants.midY)} x2={padL + innerW} y2={py(quadrants.midY)} stroke={MUTED} strokeDasharray="4 3" strokeWidth="1" />
          {quadrants.labels?.map((q) => (
            <text key={q.text} x={px(q.x)} y={py(q.y)} textAnchor="middle" fontSize="10.5"
              fill="#b8950f" className="font-bold">{q.text}</text>
          ))}
        </>
      )}
      {diagonal && (
        <line x1={px(Math.max(xmin, ymin))} y1={py(Math.max(xmin, ymin))}
          x2={px(Math.min(xmax, ymax))} y2={py(Math.min(xmax, ymax))}
          stroke={MUTED} strokeDasharray="5 4" strokeWidth="1.25" />
      )}
      {connect && (
        <polyline fill="none" stroke={color} strokeWidth="2"
          points={ordered.map((p) => `${px(p.x)},${py(p.y)}`).join(' ')} />
      )}
      {points.map((p, i) => (
        <motion.circle key={i} initial={{ opacity: 0, scale: 0 }} animate={{ opacity: 0.85, scale: 1 }}
          transition={{ duration: 0.3, delay: i * 0.01 }}
          cx={px(p.x)} cy={py(p.y)} r={p.r || 5} fill={p.color || color}
          stroke="#fff" strokeWidth="0.75">
          <title>{`${p.label ? p.label + ' · ' : ''}${fmtNum(p.x, 1)}, ${fmtNum(p.y, 2)}`}</title>
        </motion.circle>
      ))}
      <text x={padL + innerW / 2} y={H - 6} textAnchor="middle" fontSize="11" fill={INK} className="font-semibold">{xLabel}</text>
      <text x={14} y={padT + innerH / 2} textAnchor="middle" fontSize="11" fill={INK}
        transform={`rotate(-90 14 ${padT + innerH / 2})`} className="font-semibold">{yLabel}</text>
    </svg>
  )
}

/**
 * Radar — percentile/profile polygon(s) on a polar grid.
 * axes: [string]; series: [{ name, color, values: number[] }]  (values 0..max)
 */
export function Radar({ axes, series, max = 100, size = 300 }) {
  if (!axes?.length || !series?.length) return null
  const cx = size / 2, cy = size / 2 + 6, R = size / 2 - 46
  const n = axes.length
  const angle = (i) => (Math.PI * 2 * i) / n - Math.PI / 2
  const pt = (i, r) => [cx + Math.cos(angle(i)) * R * (r / max), cy + Math.sin(angle(i)) * R * (r / max)]
  const rings = [0.25, 0.5, 0.75, 1]

  return (
    <svg viewBox={`0 0 ${size} ${size + 10}`} width="100%" role="img" aria-label="radar chart">
      {rings.map((rr) => (
        <polygon key={rr} fill="none" stroke={GRID} strokeWidth="1"
          points={axes.map((_, i) => pt(i, max * rr).join(',')).join(' ')} />
      ))}
      {axes.map((a, i) => {
        const [ex, ey] = pt(i, max)
        const [lx, ly] = [cx + Math.cos(angle(i)) * (R + 16), cy + Math.sin(angle(i)) * (R + 16)]
        return (
          <g key={a}>
            <line x1={cx} y1={cy} x2={ex} y2={ey} stroke={GRID} strokeWidth="1" />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="central" fontSize="9.5" fill={MUTED}>
              {a.length > 12 ? a.slice(0, 11) + '…' : a}
            </text>
          </g>
        )
      })}
      {series.map((s) => {
        const pts = s.values.map((v, i) => pt(i, Math.max(0, Math.min(max, v))).join(',')).join(' ')
        return (
          <g key={s.name}>
            <motion.polygon initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}
              points={pts} fill={s.color} fillOpacity="0.28" stroke={s.color} strokeWidth="2" />
            {s.values.map((v, i) => {
              const [dx, dy] = pt(i, Math.max(0, Math.min(max, v)))
              return <circle key={i} cx={dx} cy={dy} r="2.5" fill={s.color}><title>{`${axes[i]}: ${fmtNum(v, 0)}`}</title></circle>
            })}
          </g>
        )
      })}
    </svg>
  )
}

/**
 * Heatmap — labelled grid with a colour scale and per-cell values.
 * rows/cols: [string]; matrix: number[][]; scale: 'seq' | 'div'
 */
export function Heatmap({ rows, cols, matrix, scale = 'seq', fmt = (v) => fmtNum(v, 0),
  xLabel = '', yLabel = '', height }) {
  if (!rows?.length || !cols?.length) return null
  const W = 460, padL = 96, padR = 14, padT = 28, padB = 30
  const cell = (W - padL - padR) / cols.length
  const H = height || padT + padB + cell * rows.length
  const flat = matrix.flat()
  const maxAbs = Math.max(...flat.map((v) => Math.abs(v)), 0.0001)
  const color = (v) => (scale === 'div' ? divColor(v / maxAbs) : seqColor(v / maxAbs))
  const textColor = (v) => (scale === 'seq' && v / maxAbs > 0.55 ? '#1a2e10' : INK)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="heatmap">
      {cols.map((c, j) => (
        <text key={c} x={padL + j * cell + cell / 2} y={padT - 8} textAnchor="middle" fontSize="9.5" fill={MUTED}>
          {c.length > 9 ? c.slice(0, 8) + '…' : c}
        </text>
      ))}
      {rows.map((r, i) => (
        <text key={r} x={padL - 8} y={padT + i * cell + cell / 2} textAnchor="end" dominantBaseline="central" fontSize="9.5" fill={MUTED}>
          {r.length > 13 ? r.slice(0, 12) + '…' : r}
        </text>
      ))}
      {matrix.map((row, i) => row.map((v, j) => (
        <g key={`${i}-${j}`}>
          <rect x={padL + j * cell} y={padT + i * cell} width={cell - 1.5} height={cell - 1.5}
            rx="3" fill={color(v)}><title>{`${rows[i]} × ${cols[j]}: ${fmt(v)}`}</title></rect>
          <text x={padL + j * cell + cell / 2} y={padT + i * cell + cell / 2} textAnchor="middle"
            dominantBaseline="central" fontSize={cell < 44 ? '9.5' : '11.5'} fill={textColor(v)}
            className="font-semibold tabular-nums">{fmt(v)}</text>
        </g>
      )))}
      {xLabel && <text x={padL + (W - padL - padR) / 2} y={H - 6} textAnchor="middle" fontSize="10.5" fill={INK} className="font-semibold">{xLabel}</text>}
    </svg>
  )
}
