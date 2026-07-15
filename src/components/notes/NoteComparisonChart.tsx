import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useReducedMotion } from 'framer-motion'
import type { JournalComparisonChart, JournalChartSeries } from '../../data/journal'

const tickStyle = { fill: 'hsl(var(--dash-text-secondary))', fontSize: 11 }
const tooltipStyle = {
  background: 'hsl(var(--dash-modal))',
  border: '1px solid hsl(var(--dash-border))',
  borderRadius: '6px',
  color: 'hsl(var(--dash-text))',
  fontSize: '12px',
}

const formatTick = (series: JournalChartSeries) => (value: number) => `${value}${series.unit.trim()}`

export default function NoteComparisonChart({ chart }: { chart: JournalComparisonChart }) {
  const reduceMotion = useReducedMotion()
  const ariaLabel = `${chart.title}. ${chart.data.map((datum) => {
    const values = [`${chart.primary.label} ${datum.primary}${chart.primary.unit}`]
    if (chart.secondary && datum.secondary != null) values.push(`${chart.secondary.label} ${datum.secondary}${chart.secondary.unit}`)
    return `${datum.label}: ${values.join(', ')}`
  }).join('. ')}`

  const commonAxis = (
    <>
      <CartesianGrid stroke="hsl(var(--dash-border))" strokeDasharray="3 5" vertical={false} />
      <XAxis
        dataKey="label"
        interval={chart.kind === 'dual' ? 0 : undefined}
        tick={tickStyle}
        tickLine={false}
        axisLine={{ stroke: 'hsl(var(--dash-border))' }}
      />
      <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'hsl(var(--dash-card-hover))', opacity: 0.5 }} />
      <Legend
        wrapperStyle={{ fontSize: '11px', paddingTop: '12px' }}
        formatter={(value) => <span style={{ color: 'hsl(var(--dash-text-secondary))' }}>{value}</span>}
      />
    </>
  )

  return (
    <figure className="mb-16 md:mb-20 border-y border-dash-border py-7 md:py-9" aria-label={ariaLabel}>
      <div className="mb-6">
        <div className="font-mono text-[10px] text-emerald-700 dark:text-emerald-400 mb-2">COMPARISON</div>
        <h2 className="font-journal-serif text-[22px] md:text-[26px] leading-[1.4] text-dash-heading mb-3">{chart.title}</h2>
        <p className="text-[13px]/[1.75] text-pretty break-keep text-dash-text-secondary">{chart.description}</p>
      </div>
      <div className="h-[280px] w-full" role="img" aria-label={ariaLabel}>
        <ResponsiveContainer width="100%" height="100%">
          {chart.kind === 'dual' && chart.secondary ? (
            <ComposedChart data={chart.data} margin={{ top: 16, right: 8, left: -8, bottom: 4 }}>
              {commonAxis}
              <YAxis
                yAxisId="primary"
                domain={chart.primary.domain ?? [0, 'auto']}
                tick={tickStyle}
                tickFormatter={formatTick(chart.primary)}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                yAxisId="secondary"
                orientation="right"
                domain={chart.secondary.domain ?? [0, 'auto']}
                tick={tickStyle}
                tickFormatter={formatTick(chart.secondary)}
                tickLine={false}
                axisLine={false}
              />
              <Bar yAxisId="primary" dataKey="primary" name={chart.primary.label} unit={chart.primary.unit} fill={chart.primary.color} radius={[4, 4, 0, 0]} maxBarSize={84} isAnimationActive={!reduceMotion} />
              <Line yAxisId="secondary" dataKey="secondary" name={chart.secondary.label} unit={chart.secondary.unit} stroke={chart.secondary.color} strokeWidth={3} dot={{ r: 5 }} activeDot={{ r: 7 }} isAnimationActive={!reduceMotion} />
            </ComposedChart>
          ) : (
            <BarChart data={chart.data} margin={{ top: 16, right: 8, left: -8, bottom: 4 }}>
              {commonAxis}
              <YAxis
                domain={chart.primary.domain ?? [0, 'auto']}
                tick={tickStyle}
                tickFormatter={formatTick(chart.primary)}
                tickLine={false}
                axisLine={false}
              />
              <Bar
                dataKey="primary"
                name={chart.primary.label}
                unit={chart.primary.unit}
                stackId={chart.kind === 'stacked' ? 'total' : undefined}
                fill={chart.primary.color}
                radius={chart.kind === 'stacked' ? [0, 0, 0, 0] : [4, 4, 0, 0]}
                maxBarSize={84}
                isAnimationActive={!reduceMotion}
              />
              {chart.kind === 'stacked' && chart.secondary && (
                <Bar
                  dataKey="secondary"
                  name={chart.secondary.label}
                  unit={chart.secondary.unit}
                  stackId="total"
                  fill={chart.secondary.color}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={84}
                  isAnimationActive={!reduceMotion}
                />
              )}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <div className="sr-only">
        {chart.data.map((datum) => (
          <p key={datum.label}>
            {datum.label}: {chart.primary.label} {datum.primary}{chart.primary.unit}
            {chart.secondary && datum.secondary != null ? `, ${chart.secondary.label} ${datum.secondary}${chart.secondary.unit}` : ''}
          </p>
        ))}
      </div>
      {chart.caveat && <figcaption className="mt-4 text-xs/[1.7] text-pretty break-keep text-dash-text-secondary">{chart.caveat}</figcaption>}
    </figure>
  )
}