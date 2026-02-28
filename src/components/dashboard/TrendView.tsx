import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { ExperimentEntry } from '../../types/report'
import { useTheme } from '../../contexts/ThemeContext'

interface TrendViewProps {
  experiments: ExperimentEntry[]
}

/* ─── Custom X-axis tick: clickable + tooltip ─── */
function ClickableAxisTick(props: any) {
  const { x, y, payload, expMap, navigate, isDark } = props
  const exp = expMap?.[payload.value] as ExperimentEntry | undefined
  const [hovered, setHovered] = useState(false)

  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0} y={0} dy={14}
        textAnchor="middle"
        fill={isDark ? '#93a3bf' : '#6b7280'}
        fontSize={11}
        style={{ cursor: 'pointer', textDecoration: hovered ? 'underline' : 'none' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={(e) => { e.stopPropagation(); navigate(`/experiments/${payload.value}`) }}
      >
        {payload.value}
      </text>
      {hovered && exp && (
        <foreignObject x={-100} y={20} width={200} height={60} style={{ overflow: 'visible', pointerEvents: 'none' }}>
          <div
            style={{
              background: isDark ? '#1e1e2e' : '#ffffff',
              border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid #d1d5db',
              borderRadius: 6,
              padding: '4px 8px',
              fontSize: 10,
              color: isDark ? '#e5e7eb' : '#374151',
              textAlign: 'center',
              whiteSpace: 'nowrap',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            }}
          >
            {exp.experiment_name}
          </div>
        </foreignObject>
      )}
    </g>
  )
}

export default function TrendView({ experiments }: TrendViewProps) {
  const { isDark } = useTheme()
  const navigate = useNavigate()

  const chartTooltipStyle = {
    contentStyle: {
      background: isDark ? '#1a1a2e' : '#ffffff',
      border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid #e5e7eb',
      borderRadius: 8,
      fontSize: 12,
      color: isDark ? '#e5e7eb' : '#374151',
    },
  }
  const gridStroke = isDark ? 'rgba(255,255,255,0.06)' : '#e5e7eb'
  const tickStyle = { fill: isDark ? '#666' : '#9ca3af', fontSize: 11 }
  // Sort by date chronologically
  const sortedExps = [...experiments].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  // Build a map for quick lookup by short_id
  const expMap = Object.fromEntries(sortedExps.map((e) => [e.short_id, e]))

  // Prepare data for charts
  const chartData = sortedExps.map((exp) => ({
    name: exp.short_id,
    experiment_name: exp.experiment_name,
    successRate: exp.success_rate_pct,
    qaScore: exp.avg_qa_score,
    errors: exp.total_tasks - exp.success_count,
    retries: exp.retried_count || 0,
  }))

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* 2x2 Chart Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Success Rate Chart */}
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-3">Success Rate Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="name" tick={<ClickableAxisTick expMap={expMap} navigate={navigate} isDark={isDark} />} />
              <YAxis tick={tickStyle} domain={[85, 100]} />
              <Tooltip {...chartTooltipStyle} />
              <Line
                type="monotone"
                dataKey="successRate"
                stroke="#10b981"
                dot={{ fill: '#10b981', r: 4 }}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* QA Score Chart */}
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-3">QA Score Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="name" tick={<ClickableAxisTick expMap={expMap} navigate={navigate} isDark={isDark} />} />
              <YAxis tick={tickStyle} domain={[4, 7]} />
              <Tooltip {...chartTooltipStyle} />
              <Line
                type="monotone"
                dataKey="qaScore"
                stroke="#f59e0b"
                dot={{ fill: '#f59e0b', r: 4 }}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Errors Chart */}
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-3">Error Count</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="name" tick={<ClickableAxisTick expMap={expMap} navigate={navigate} isDark={isDark} />} />
              <YAxis tick={tickStyle} />
              <Tooltip {...chartTooltipStyle} />
              <Bar dataKey="errors" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Retries Chart */}
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-3">Recovery Attempts</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis dataKey="name" tick={<ClickableAxisTick expMap={expMap} navigate={navigate} isDark={isDark} />} />
              <YAxis tick={tickStyle} />
              <Tooltip {...chartTooltipStyle} />
              <Bar dataKey="retries" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Config Comparison Table */}
      <div className="rounded-xl bg-dash-card border border-dash-border overflow-hidden">
        <div className="p-4 border-b border-dash-border">
          <h3 className="text-sm font-semibold text-dash-text">Configuration Comparison</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-dash-border bg-dash-card">
                <th className="px-4 py-2 text-left text-dash-text-muted font-semibold">Experiment</th>
                <th className="px-4 py-2 text-left text-dash-text-muted font-semibold">Model</th>
                <th className="px-4 py-2 text-left text-dash-text-muted font-semibold">Condition</th>
                <th className="px-4 py-2 text-left text-dash-text-muted font-semibold">Date</th>
                <th className="px-4 py-2 text-left text-dash-text-muted font-semibold">Duration</th>
              </tr>
            </thead>
            <tbody>
              {sortedExps.map((exp, idx) => (
                <motion.tr
                  key={exp.short_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.04 }}
                  className="border-b border-dash-border-subtle hover:bg-dash-card-hover"
                >
                  <td className="px-4 py-2">
                    <span
                      className="relative group cursor-pointer text-dash-heading font-semibold hover:underline"
                      onClick={() => navigate(`/experiments/${exp.short_id}`)}
                    >
                      {exp.short_id}
                      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 whitespace-nowrap rounded-md bg-dash-card border border-dash-border text-[10px] text-dash-text-secondary px-2.5 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
                        {exp.experiment_name}
                      </span>
                    </span>
                  </td>
                  <td className="px-4 py-2 text-dash-text-secondary font-mono">{exp.model}</td>
                  <td className="px-4 py-2 text-dash-text-secondary">{exp.condition}</td>
                  <td className="px-4 py-2 text-dash-text-muted">{exp.date}</td>
                  <td className="px-4 py-2 text-dash-text-muted">{exp.duration}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  )
}
