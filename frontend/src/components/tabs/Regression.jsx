import { useEffect, useState } from 'react'
import { Sigma, BarChart3, Target, Activity, GitCompare, Grid3x3, Info } from 'lucide-react'
import { Card, StatCard } from '../ui.jsx'
import { GroupedHBars, HBars, VBars, Scatter, Heatmap, Legend, PALETTE } from '../charts.jsx'
import { getRegression } from '../../data/api.js'

const classColor = (lbl) => (lbl === 'HOME_WIN' ? PALETTE[0] : lbl === 'DRAW' ? '#94a3b8' : PALETTE[1])

function binDistribution(distribution, nClasses, bins = 10) {
  const counts = Array.from({ length: nClasses }, () => Array(bins).fill(0))
  distribution.forEach((row) => row.forEach((p, ci) => {
    if (ci < nClasses) counts[ci][Math.min(bins - 1, Math.max(0, Math.floor(p * bins)))]++
  }))
  return counts
}

export default function Regression() {
  const [r, setR] = useState(null)
  useEffect(() => { getRegression().then(setR) }, [])
  if (!r) return null

  if (r.available === false) {
    return (
      <Card title="Regression report unavailable" icon={Sigma}>
        <p className="text-sm text-turf-600">
          The model report could not be computed{r.error ? `: ${r.error}` : '.'} It builds from the
          historical match database — check back once the data pipeline has run.
        </p>
      </Card>
    )
  }

  const m = r.metrics || {}
  const features = r.features || []
  const classes = r.classes || []
  const legendItems = classes.map((c) => ({ label: c, color: classColor(c) }))

  const coefSeries = classes.map((c, ci) => ({ name: c, color: classColor(c), values: r.coefficients[ci] }))
  const orSeries = classes.map((c, ci) => ({ name: c, color: classColor(c), values: r.oddsRatios[ci] }))
  const importanceRows = (r.importance || []).map((d) => ({ label: d.feature, value: d.value }))
  const calPts = (r.calibration || []).map((c) => ({ x: c.conf, y: c.hit, r: 4 + Math.min(8, c.n / 4) }))

  const distCounts = binDistribution(r.distribution || [], classes.length)
  const distCats = Array.from({ length: 10 }, (_, i) => (i / 10).toFixed(1))
  const distSeries = classes.map((c, ci) => ({ name: c, color: classColor(c), values: distCounts[ci] }))

  const loto = r.loto || []
  const lotoSeries = [
    { name: 'Model', color: PALETTE[0], values: loto.map((l) => l.accuracy * 100) },
    { name: 'FIFA baseline', color: '#94a3b8', values: loto.map((l) => l.baseline * 100) },
  ]

  return (
    <div className="space-y-5">
      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard label="Accuracy (WC 2022)" value={`${(m.accuracy * 100).toFixed(1)}%`}
          sub={`+${((m.accuracy - m.baseline) * 100).toFixed(1)} pts vs baseline`} accent="purple" />
        <StatCard label="Log Loss" value={m.logLoss} sub="lower is better" accent="turf" />
        <StatCard label="Brier Score" value={m.brier} sub="lower is better" accent="gold" />
        <StatCard label="Train Set" value={`${m.nTrain}`} sub={(m.trainTournaments || []).join(', ')} accent="turf" />
        <StatCard label="Test Set" value={`${m.nTest}`} sub={(m.testTournaments || []).join(', ')} accent="red" />
      </div>

      {/* Coefficients */}
      <Card title="Regression Coefficients" subtitle="Standardised β per outcome class · positive raises that outcome's log-odds" icon={BarChart3}>
        <GroupedHBars categories={features} series={coefSeries} valueFmt={(v) => v.toFixed(2)} height={features.length * 38 + 30} />
        <div className="mt-2"><Legend items={legendItems} /></div>
      </Card>

      {/* Odds ratios */}
      <Card title="Odds Ratios — exp(β)" subtitle="How the odds multiply per 1 SD of the feature · dashed line = neutral (1.0)" icon={GitCompare}>
        <GroupedHBars categories={features} series={orSeries} valueFmt={(v) => v.toFixed(2)} refLine={1} height={features.length * 38 + 30} />
        <div className="mt-2"><Legend items={legendItems} /></div>
      </Card>

      {/* Importance */}
      <Card title="Feature Importance" subtitle="Mean |β| across the three outcome classes" icon={BarChart3}>
        <HBars data={importanceRows} color={PALETTE[1]} valueFmt={(v) => v.toFixed(3)} />
      </Card>

      {/* Confusion + report */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Confusion Matrix" subtitle="WC 2022 hold-out · rows = actual, cols = predicted" icon={Grid3x3}>
          <Heatmap rows={r.confusion.labels} cols={r.confusion.labels} matrix={r.confusion.matrix}
            scale="seq" fmt={(v) => `${v}`} xLabel="Predicted" />
        </Card>
        <Card title="Classification Report" subtitle="Per-class precision / recall / F1" icon={Target}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                <th className="pb-2 font-semibold">Class</th>
                <th className="pb-2 text-right font-semibold">Precision</th>
                <th className="pb-2 text-right font-semibold">Recall</th>
                <th className="pb-2 text-right font-semibold">F1</th>
                <th className="pb-2 text-right font-semibold">Support</th>
              </tr>
            </thead>
            <tbody>
              {(r.classReport || []).map((c) => (
                <tr key={c.label} className="border-t border-turf-100">
                  <td className="py-2 font-medium" style={{ color: classColor(c.label) }}>{c.label}</td>
                  <td className="py-2 text-right tabular-nums">{c.precision.toFixed(2)}</td>
                  <td className="py-2 text-right tabular-nums">{c.recall.toFixed(2)}</td>
                  <td className="py-2 text-right tabular-nums">{c.f1.toFixed(2)}</td>
                  <td className="py-2 text-right tabular-nums text-turf-600">{c.support}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Calibration */}
      <Card title="Calibration Curve" subtitle="A calibrated model's confidence matches its hit rate · points on the diagonal = perfect" icon={Activity}>
        <Scatter points={calPts} connect diagonal xDomain={[0, 1]} yDomain={[0, 1]}
          xLabel="Mean predicted confidence" yLabel="Observed hit rate" color={PALETTE[0]} height={360} />
      </Card>

      {/* Distribution */}
      <Card title="Predicted Probability Distribution" subtitle="How confidence spreads across held-out matches (WC 2022)" icon={BarChart3}>
        <VBars categories={distCats} series={distSeries} yFmt={(v) => `${Math.round(v)}`} height={260} />
        <div className="mt-2"><Legend items={legendItems} /></div>
      </Card>

      {/* LOTO CV */}
      <Card title="Leave-One-Tournament-Out CV" subtitle="Each tournament held out in turn · model vs FIFA-rank baseline" icon={GitCompare}>
        {loto.length > 0 && (
          <>
            <VBars categories={loto.map((l) => l.tournament)} series={lotoSeries} yFmt={(v) => `${Math.round(v)}`} height={260} yMax={100} />
            <div className="mt-2 mb-3"><Legend items={[{ label: 'Model', color: PALETTE[0] }, { label: 'FIFA baseline', color: '#94a3b8' }]} /></div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-turf-600/70">
                  <th className="pb-2 font-semibold">Tournament</th>
                  <th className="pb-2 text-center font-semibold">Matches</th>
                  <th className="pb-2 text-right font-semibold">Acc %</th>
                  <th className="pb-2 text-right font-semibold">Base %</th>
                  <th className="pb-2 text-right font-semibold">Edge</th>
                  <th className="pb-2 text-right font-semibold">Log Loss</th>
                  <th className="pb-2 text-right font-semibold">Brier</th>
                </tr>
              </thead>
              <tbody>
                {loto.map((l) => (
                  <tr key={l.tournament} className="border-t border-turf-100">
                    <td className="py-1.5 font-medium text-turf-900">{l.tournament}</td>
                    <td className="py-1.5 text-center tabular-nums">{l.matches}</td>
                    <td className="py-1.5 text-right tabular-nums">{(l.accuracy * 100).toFixed(1)}</td>
                    <td className="py-1.5 text-right tabular-nums text-turf-600">{(l.baseline * 100).toFixed(1)}</td>
                    <td className={`py-1.5 text-right font-semibold tabular-nums ${l.edge >= 0 ? 'text-turf-700' : 'text-wc-red'}`}>{l.edge >= 0 ? '+' : ''}{(l.edge * 100).toFixed(1)}</td>
                    <td className="py-1.5 text-right tabular-nums text-turf-600">{l.logLoss}</td>
                    <td className="py-1.5 text-right tabular-nums text-turf-600">{l.brier}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>

      {/* Correlation */}
      <Card title="Feature Correlation Matrix" subtitle="Pearson correlations · high values flag multicollinearity" icon={Grid3x3}>
        <Heatmap rows={r.correlation.features} cols={r.correlation.features} matrix={r.correlation.matrix}
          scale="div" fmt={(v) => v.toFixed(2)} />
      </Card>

      {/* Methodology */}
      <Card title="Methodology" icon={Info}>
        <details className="text-sm text-turf-700">
          <summary className="cursor-pointer font-semibold text-turf-800">How to read this analysis</summary>
          <div className="mt-2 space-y-2 leading-relaxed">
            <p><b>Model:</b> multinomial logistic regression (Home / Draw / Away) with a StandardScaler, model <code>{r.modelVersion}</code>.</p>
            <p><b>Leakage-free features:</b> elo_diff, fifa_rank_gap, form_goals_diff, form_xg_diff, rest_days_diff, is_knockout — each knowable before kickoff.</p>
            <p><b>Validation:</b> strict temporal split (train WC 2018 + EURO 2020, test WC 2022) plus leave-one-tournament-out CV across six tournaments.</p>
            <p><b>Metrics:</b> log loss penalises confident wrong calls; Brier is the MSE of the probability vector (0.25 = coin flip); calibration asks whether 70% confidence comes true ~70% of the time. The edge over the FIFA-rank baseline is the model's alpha.</p>
          </div>
        </details>
      </Card>
    </div>
  )
}
