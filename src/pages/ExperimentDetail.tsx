import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, CheckCircle2, XCircle, RefreshCw,
  X, Search, Sun, Moon,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts'
import { useReport } from '../hooks/useReports'
import { useIsMobile } from '../hooks/useIsMobile'
import { useTheme } from '../contexts/ThemeContext'
import ScopeBadge from '../components/ScopeBadge'
import type { TaskResult } from '../types/report'

// ── Color helpers ──
function rateColor(rate: number) {
  if (rate >= 96) return '#10b981'
  if (rate >= 90) return '#f59e0b'
  return '#ef4444'
}

function qaColor(score: number | null) {
  if (score === null) return '#6b7280'
  if (score >= 7) return '#10b981'
  if (score >= 5) return '#f59e0b'
  return '#ef4444'
}

type SortKey = 'task_id' | 'sector' | 'occupation' | 'status' | 'qa_score' | 'latency_ms'
type SortDir = 'asc' | 'desc'

function ExperimentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { report, loading, error } = useReport(id)
  const { isDark, toggle: toggleTheme } = useTheme()
  const isMobile = useIsMobile()

  const chartTooltipStyle = {
    background: isDark ? '#1a1a2e' : '#ffffff',
    border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid #e5e7eb',
    borderRadius: 8,
    fontSize: 12,
    color: isDark ? '#e5e7eb' : '#374151',
  }
  const gridStroke = isDark ? 'rgba(255,255,255,0.06)' : '#e5e7eb'
  const tickStyle = { fill: isDark ? '#666' : '#9ca3af', fontSize: 11 }

  // ── State ──
  const [selectedTask, setSelectedTask] = useState<TaskResult | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sectorFilter, setSectorFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortKey, setSortKey] = useState<SortKey>('sector')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  // ── Derived data ──
  const meta = report?.meta
  const summary = report?.summary
  const sectors = useMemo(
    () => [...new Set(report?.task_results?.map((t) => t.sector) || [])].sort(),
    [report]
  )

  const filteredTasks = useMemo(() => {
    let tasks = report?.task_results || []
    if (searchTerm) {
      const q = searchTerm.toLowerCase()
      tasks = tasks.filter(
        (t) =>
          t.task_id.toLowerCase().includes(q) ||
          t.occupation.toLowerCase().includes(q) ||
          t.sector.toLowerCase().includes(q)
      )
    }
    if (sectorFilter !== 'all') tasks = tasks.filter((t) => t.sector === sectorFilter)
    if (statusFilter !== 'all') tasks = tasks.filter((t) => t.status === statusFilter)
    tasks = [...tasks].sort((a, b) => {
      const av =
        sortKey === 'qa_score'
          ? a.qa_score ?? -1
          : sortKey === 'latency_ms'
            ? a.latency_ms
            : (a as any)[sortKey]
      const bv =
        sortKey === 'qa_score'
          ? b.qa_score ?? -1
          : sortKey === 'latency_ms'
            ? b.latency_ms
            : (b as any)[sortKey]
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
    return tasks
  }, [report, searchTerm, sectorFilter, statusFilter, sortKey, sortDir])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-dash-page flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-2 border-dash-text-faint border-t-dash-heading rounded-full animate-spin mb-4" />
          <p className="text-dash-text-secondary">Loading experiment...</p>
        </div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-dash-page flex items-center justify-center">
        <div className="text-center text-red-400">
          <p className="font-semibold mb-2">Error loading experiment</p>
          <p className="text-sm text-red-300">{error}</p>
        </div>
      </div>
    )
  }

  const sectorChartData = report.sector_breakdown.map((s) => ({
    name: s.sector,
    success_rate: s.success_rate_pct,
    qa_score: s.avg_qa_score,
  }))

  return (
    <motion.div
      className="min-h-screen bg-dash-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <header className="border-b border-dash-border bg-dash-page/90 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-3 flex items-center gap-2 md:gap-4">
          <button
            onClick={() => navigate('/')}
            className="text-dash-text-muted hover:text-dash-heading transition p-1 rounded hover:bg-dash-card-hover"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold text-dash-heading">{report.short_id}</h1>
              <span className="text-xs font-mono bg-dash-card-hover px-2 py-0.5 rounded text-dash-text">
                {meta?.model}
              </span>
              <span className="text-[10px] bg-dash-card-hover px-2 py-0.5 rounded text-dash-text-secondary" title={meta?.execution_mode}>
                {meta?.execution_mode === 'code_interpreter' ? '☁️ CI' :
                 meta?.execution_mode === 'subprocess' ? '🖥️ Sub' :
                 meta?.execution_mode === 'json_renderer' ? '📄 JSON' :
                 meta?.execution_mode}
              </span>
              {meta?.report_scope && <ScopeBadge scope={meta.report_scope} />}
            </div>
            <p className="text-xs text-dash-text-muted mt-0.5 truncate max-w-[150px] md:max-w-none">{meta?.experiment_name}</p>
          </div>
          <button
            onClick={toggleTheme}
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-all"
            title={isDark ? '라이트 모드' : '다크 모드'}
          >
            {isDark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>
          <div className="text-right text-xs text-dash-text-muted hidden md:block">
            <div>{meta?.date}</div>
            <div>{meta?.duration}</div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-4 md:py-8">
        {/* Quick Stats (6 cards) */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 md:gap-3 mb-6 md:mb-8"
        >
          {[
            {
              label: 'Success Rate',
              value: `${summary?.success_rate_pct.toFixed(1)}%`,
              color: rateColor(summary?.success_rate_pct ?? 0),
            },
            { label: 'Errors', value: summary?.error_count, color: '#ef4444' },
            { label: 'Retried', value: summary?.retried_count, color: '#f59e0b' },
            { label: 'Avg QA', value: summary?.avg_qa_score?.toFixed(1), color: '#6366f1' },
            {
              label: 'Avg Latency',
              value: `${((summary?.avg_latency_ms ?? 0) / 1000).toFixed(1)}s`,
              color: '#8b5cf6',
            },
            {
              label: 'Exec Mode',
              value: meta?.execution_mode === 'code_interpreter' ? '☁️ CI'
                : meta?.execution_mode === 'subprocess' ? '🖥️ Sub'
                : meta?.execution_mode === 'json_renderer' ? '📄 JSON'
                : meta?.execution_mode ?? '—',
              color: '#6b7280',
            },
          ].map((s, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="bg-dash-card border border-dash-border rounded-lg p-3 text-center"
            >
              <div className="text-[10px] text-dash-text-muted mb-1 uppercase tracking-wider">{s.label}</div>
              <div className="text-xl font-semibold font-mono" style={{ color: s.color }}>
                {s.value}
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* Charts */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8"
        >
          {/* Sector Bar Chart */}
          <div className="rounded-xl bg-dash-card border border-dash-border p-3 md:p-4">
            <h3 className="text-sm font-semibold text-dash-text mb-3">Success Rate by Sector</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={sectorChartData} layout="vertical" margin={{ top: 5, right: isMobile ? 10 : 30, left: isMobile ? 5 : 150, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                <XAxis type="number" tick={tickStyle} />
                <YAxis dataKey="name" type="category" tick={{ ...tickStyle, fontSize: isMobile ? 9 : 11 }} width={isMobile ? 100 : 140} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="success_rate" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* QA Score Radar */}
          <div className="rounded-xl bg-dash-card border border-dash-border p-4">
            <h3 className="text-sm font-semibold text-dash-text mb-3">QA Score by Sector</h3>
            <ResponsiveContainer width="100%" height={250}>
              <RadarChart data={sectorChartData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                <PolarGrid stroke={isDark ? 'rgba(255,255,255,0.1)' : '#e5e7eb'} />
                <PolarAngleAxis dataKey="name" tick={{ fill: isDark ? '#999' : '#6b7280', fontSize: 10 }} />
                <PolarRadiusAxis tick={tickStyle} />
                <Radar dataKey="qa_score" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.3} />
                <Tooltip contentStyle={chartTooltipStyle} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Task Table */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="bg-dash-card border border-dash-border rounded-xl overflow-hidden"
        >
          {/* Filter bar */}
          <div className="px-5 py-3 border-b border-dash-border">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold text-dash-text">
                Task Results{' '}
                <span className="text-[10px] text-dash-text-muted bg-dash-card-hover px-2 py-0.5 rounded-full ml-2">
                  {filteredTasks.length} tasks
                </span>
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-dash-text-muted" />
                <input
                  type="text"
                  placeholder="Search task ID, occupation..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="bg-dash-card-hover border border-dash-border rounded-lg pl-7 pr-3 py-1.5 text-xs text-dash-text placeholder-dash-text-faint w-full md:w-56 focus:outline-none"
                />
              </div>
              {/* Sector filter */}
              <select
                value={sectorFilter}
                onChange={(e) => setSectorFilter(e.target.value)}
                className="bg-dash-card-hover border border-dash-border rounded-lg px-2 py-1.5 text-xs text-dash-text"
              >
                <option value="all">All Sectors</option>
                {sectors.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              {/* Status filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-dash-card-hover border border-dash-border rounded-lg px-2 py-1.5 text-xs text-dash-text"
              >
                <option value="all">All Status</option>
                <option value="success">Success</option>
                <option value="error">Error</option>
              </select>
            </div>
          </div>

          {/* Scrollable table */}
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-dash-sticky z-10">
                <tr className="text-[10px] text-dash-text-muted uppercase tracking-wider border-b border-dash-border">
                  <th className="px-4 py-2 text-left w-8">#</th>
                  <th className="px-3 py-2 text-left cursor-pointer" onClick={() => handleSort('status')}>
                    Status
                  </th>
                  <th className="px-3 py-2 text-left cursor-pointer" onClick={() => handleSort('task_id')}>
                    Task ID
                  </th>
                  <th className="px-3 py-2 text-left cursor-pointer" onClick={() => handleSort('sector')}>
                    Sector
                  </th>
                  <th className="px-3 py-2 text-left cursor-pointer" onClick={() => handleSort('occupation')}>
                    Occupation
                  </th>
                  <th className="px-3 py-2 text-center">Retry</th>
                  <th className="px-3 py-2 text-center">Files</th>
                  <th className="px-3 py-2 text-right cursor-pointer" onClick={() => handleSort('qa_score')}>
                    Self-QA
                  </th>
                  <th className="px-3 py-2 text-right">Grade</th>
                  <th className="px-3 py-2 text-right cursor-pointer" onClick={() => handleSort('latency_ms')}>
                    Latency
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredTasks.map((task, i) => (
                  <tr
                    key={task.task_id}
                    className="border-b border-dash-border-subtle hover:bg-dash-card-hover cursor-pointer transition"
                    onClick={() => setSelectedTask(task)}
                  >
                    <td className="px-4 py-2 text-dash-text-faint font-mono">{i + 1}</td>
                    <td className="px-3 py-2">
                      {task.status === 'success' ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-red-400" />
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-dash-text-secondary text-[10px]">{task.task_id}</td>
                    <td className="px-3 py-2 text-dash-text-secondary max-w-[180px] truncate">{task.sector}</td>
                    <td className="px-3 py-2 text-dash-text max-w-[180px] truncate">{task.occupation}</td>
                    <td className="px-3 py-2 text-center">
                      {task.retried && <RefreshCw className="h-3 w-3 text-amber-400 mx-auto" />}
                    </td>
                    <td className="px-3 py-2 text-center text-dash-text-secondary font-mono">{task.files_count}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {task.qa_score != null ? (
                        <span style={{ color: qaColor(task.qa_score) }}>{task.qa_score}/10</span>
                      ) : (
                        <span className="text-dash-text-faint">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span className="text-[10px] text-dash-text-faint bg-dash-card-hover px-1.5 py-0.5 rounded">
                        pending
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-dash-text-muted">
                      {task.latency_ms ? `${(task.latency_ms / 1000).toFixed(1)}s` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Task Detail Modal */}
        <AnimatePresence>
          {selectedTask && <TaskDetailModal task={selectedTask} onClose={() => setSelectedTask(null)} />}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

function TaskDetailModal({ task, onClose }: { task: TaskResult; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.97 }}
        className="relative bg-dash-modal border border-dash-border rounded-2xl w-full max-w-xl max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="sticky top-0 bg-dash-modal border-b border-dash-border px-5 py-3 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            {task.status === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            ) : (
              <XCircle className="h-4 w-4 text-red-400" />
            )}
            <span className="text-sm font-semibold text-dash-heading font-mono break-all">{task.task_id}</span>
          </div>
          <button onClick={onClose} className="text-dash-text-muted hover:text-dash-heading p-1 rounded hover:bg-dash-card-hover">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Meta grid: Sector, Occupation, Files, Latency */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">Sector</div>
              <div className="text-dash-text">{task.sector}</div>
            </div>
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">Occupation</div>
              <div className="text-dash-text">{task.occupation}</div>
            </div>
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">Files Created</div>
              <div className="text-dash-text font-mono">{task.files_count}</div>
            </div>
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">Latency</div>
              <div className="text-dash-text font-mono">{task.latency_ms ? `${(task.latency_ms / 1000).toFixed(1)}s` : '—'}</div>
            </div>
          </div>

          {/* ★ Error Message (for error tasks) ★ */}
          {task.status === 'error' && task.error && (
            <div className="bg-red-500/[0.08] border border-red-500/20 rounded-lg p-3">
              <div className="text-[10px] text-red-400 uppercase font-semibold mb-1.5 flex items-center gap-1.5">
                <XCircle className="h-3 w-3" /> Execution Error
              </div>
              <pre className="text-[11px] text-red-300/90 dark:text-red-300/90 text-red-700 font-mono whitespace-pre-wrap break-all leading-relaxed max-h-[200px] overflow-y-auto">{task.error}</pre>
            </div>
          )}

          {/* ★ Two Score Cards Side by Side ★ */}
          <div className="grid grid-cols-2 gap-3">
            {/* Self-QA */}
            <div className="bg-dash-card-hover border border-dash-border rounded-lg p-3 text-center">
              <div className="text-[10px] text-dash-text-muted uppercase mb-1">Self-QA Score</div>
              <div className="text-2xl font-bold font-mono" style={{ color: qaColor(task.qa_score) }}>
                {task.qa_score != null ? `${task.qa_score}/10` : '—'}
              </div>
            </div>
            {/* External Grade — shows "Awaiting Grade" when null */}
            <div className="bg-dash-card-hover border border-dash-border rounded-lg p-3 text-center">
              <div className="text-[10px] text-dash-text-muted uppercase mb-1">External Grade</div>
              <div className="text-2xl font-bold text-dash-text-faint">—</div>
              <div className="text-[10px] text-amber-400/60 mt-0.5">⏳ Awaiting Grade</div>
            </div>
          </div>

          {/* QA Issues List */}
          {task.qa_issues && task.qa_issues.length > 0 && (
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-2">QA Issues Found</div>
              <ul className="space-y-1.5">
                {task.qa_issues.map((issue, i) => (
                  <li key={i} className="text-xs text-dash-text-secondary flex items-start gap-2">
                    <span className="text-red-400/60 mt-0.5">•</span>
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* QA Suggestion */}
          {task.qa_suggestion && (
            <div className="bg-blue-500/[0.06] border border-blue-500/10 rounded-lg p-3">
              <div className="text-[10px] text-blue-400/60 uppercase mb-1">💡 Suggestion</div>
              <p className="text-xs text-blue-300/70 dark:text-blue-300/70 text-blue-700">{task.qa_suggestion}</p>
            </div>
          )}

          {/* Deliverable Summary */}
          {task.deliverable_summary && (
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-1">Deliverable Summary</div>
              <p className="text-xs text-dash-text-secondary">{task.deliverable_summary}</p>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default ExperimentDetail
