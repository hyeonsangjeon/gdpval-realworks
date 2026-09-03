import { useState, useMemo } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, CheckCircle2, XCircle, RefreshCw,
  X, Search, Sun, Moon, Code2, ChevronDown, ChevronRight,
  Timer, BookOpen, ArrowRight, Receipt,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { useReport, HF_BASE } from '../hooks/useReports'
import { useIsMobile } from '../hooks/useIsMobile'
import { useTheme } from '../contexts/ThemeContext'
import ScopeBadge from '../components/ScopeBadge'
import { useExperimentPrompt } from '../hooks/useExperimentPrompt'
import { useGrades, GradeResult } from '../hooks/useGrades'
import PromptArchitectureView from '../components/dashboard/PromptArchitectureView'
import type { TaskResult } from '../types/report'
import type { ReportMeta } from '../types/report'
import type { CostReceipt, CostSummary } from '../types/cost'
import {
  COST_ESTIMATE_NOTE,
  COST_FIELD_LABELS,
  combinedTaskCost,
  componentAmountText,
  componentDetail,
  componentKey,
  componentLabel,
  costCell,
  costCellClass,
  failedTaskCostCell,
  formatCostUsd,
  missingReasonText,
  perDeliverableCell,
  receiptAmount,
  receiptComponents,
  runtimeLineAmount,
  summaryStatCell,
  summaryStatusLabel,
  summaryTotalCell,
} from '../lib/cost'
import { fmtScore } from '../lib/format'
import { getJournalLinksForExperiment, lensLabels } from '../data/journalLinks'

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

function formatDuration(ms: number | null | undefined) {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const totalSeconds = Math.round(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}m ${seconds}s`
}

/**
 * "N.Ns", or an em dash when nothing was ever timed.
 *
 * Deliberately not formatDuration above, which switches units below a second.
 * These summary rows have always rendered plain seconds, so keeping the same
 * expression means a run that did measure prints exactly what it printed
 * before and only the absent case changes.
 */
function secondsOrDash(ms: number | null | undefined, digits: number) {
  if (ms == null) return '—'
  return `${(ms / 1000).toFixed(digits)}s`
}

// Grade-derived scope wins over the meta-recorded scope when a grade row
// exists for this experiment (match by exact experiment_id, never startsWith).
function resolveScope(
  meta: ReportMeta | undefined,
  grades: GradeResult[],
): 'self_assessed_pre_grading' | 'graded' | 'graded_v1' | 'legacy_demo' {
  if (!meta) return 'self_assessed_pre_grading'
  const match = grades.find((g) => g.experiment_id === meta.experiment_id)
  if (match?.grade_status === 'graded_v1') return 'graded_v1'
  if (match?.grade_status === 'legacy_dummy') return 'legacy_demo'
  if (meta.report_scope === 'graded') return 'graded'
  return 'self_assessed_pre_grading'
}

type SortKey =
  | 'task_id' | 'sector' | 'occupation' | 'status' | 'qa_score' | 'latency_ms'
  | 'task_wall_time_ms' | 'problem_solving_cost' | 'grading_cost'
type SortDir = 'asc' | 'desc'

/**
 * Sort key for a cost column. Rows with no recorded amount sink to the bottom
 * rather than being sorted as if they were free.
 */
function costSortValue(receipt: CostReceipt | null | undefined): number {
  if (!receipt) return -1
  return receiptAmount(receipt) ?? -1
}

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
  const [showPromptArch, setShowPromptArch] = useState(false)
  const [qaScoreFilter, setQaScoreFilter] = useState<number | 'all'>('all')
  const { prompt: promptArch, description: expDescription } = useExperimentPrompt(id)
  const { grades } = useGrades()

  // ── Derived data ──
  const meta = report?.meta
  const summary = report?.summary
  const relatedJournalArticles = getJournalLinksForExperiment(id)
  const resolvedScope = useMemo(() => resolveScope(meta, grades), [meta, grades])
  const sectors = useMemo(
    () => [...new Set(report?.task_results?.map((t) => t.sector) || [])].sort(),
    [report]
  )

  // ── Cost receipts ──
  // Problem-solving cost rides on the report's own task rows; grading cost
  // lives on the grade row for the same experiment and is joined by task_id.
  const gradeRow = useMemo(
    () => grades.find((g) => g.experiment_id === meta?.experiment_id),
    [grades, meta],
  )
  const gradingCosts = useMemo(() => {
    const receipts = new Map<string, CostReceipt>()
    // Which tasks a judge actually looked at. A task missing from this set was
    // never graded (미채점); a task in it with no receipt was graded without a
    // cost record (기록 없음). Collapsing the two would misreport both.
    const attempted = new Set<string>()
    for (const task of gradeRow?.tasks ?? []) {
      attempted.add(task.task_id)
      if (task.grading_cost) receipts.set(task.task_id, task.grading_cost)
    }
    return { receipts, attempted }
  }, [gradeRow])
  const problemSolvingSummary = report?.cost_summary?.problem_solving_cost ?? null
  const gradingSummary = gradeRow?.cost_summary?.grading_cost ?? null

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
    if (qaScoreFilter !== 'all') {
      tasks = tasks.filter((t) => t.qa_score != null && t.qa_score <= qaScoreFilter)
    }
    tasks = [...tasks].sort((a, b) => {
      const av =
        sortKey === 'qa_score'
          ? a.qa_score ?? -1
          : sortKey === 'latency_ms'
            ? a.latency_ms
            : sortKey === 'task_wall_time_ms'
              ? a.observability?.execution_metrics?.task_wall_time_ms ?? -1
            : sortKey === 'problem_solving_cost'
              ? costSortValue(a.problem_solving_cost)
            : sortKey === 'grading_cost'
              ? costSortValue(gradingCosts.receipts.get(a.task_id))
            : (a as any)[sortKey]
      const bv =
        sortKey === 'qa_score'
          ? b.qa_score ?? -1
          : sortKey === 'latency_ms'
            ? b.latency_ms
            : sortKey === 'task_wall_time_ms'
              ? b.observability?.execution_metrics?.task_wall_time_ms ?? -1
            : sortKey === 'problem_solving_cost'
              ? costSortValue(b.problem_solving_cost)
            : sortKey === 'grading_cost'
              ? costSortValue(gradingCosts.receipts.get(b.task_id))
            : (b as any)[sortKey]
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
    return tasks
  }, [report, searchTerm, sectorFilter, statusFilter, qaScoreFilter, sortKey, sortDir, gradingCosts])

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
                 meta?.execution_mode === 'agentic_sandbox' ? 'Agent' :
                 meta?.execution_mode === 'json_renderer' ? '📄 JSON' :
                 meta?.execution_mode}
              </span>
              {meta?.report_scope && <ScopeBadge scope={resolvedScope} />}
            </div>
            <p className="text-xs text-dash-text-muted mt-0.5 truncate max-w-[150px] md:max-w-none">{meta?.experiment_name}</p>
            {expDescription && (
              <p className="text-[11px] text-dash-text-faint mt-0.5 max-w-[600px] leading-relaxed hidden md:block">{expDescription}</p>
            )}
          </div>
          {meta?.experiment_id && (
            <a
              href={`${HF_BASE}/${meta.experiment_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-[10px] text-dash-text-muted hover:text-dash-heading bg-dash-card-hover border border-dash-border rounded-lg px-2.5 py-1.5 transition-all hover:border-dash-text-muted hidden md:inline-flex"
              title="View experiment dataset on HuggingFace"
            >
              🤗 HF Dataset
            </a>
          )}
          <button
            onClick={() => navigate('/notes')}
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-all"
            title="RealWorks Field Notes"
          >
            <BookOpen className="w-3.5 h-3.5" />
          </button>
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
            {
              label: 'Avg QA',
              value: summary?.avg_qa_score == null ? '—' : summary.avg_qa_score.toFixed(1),
              color: '#6366f1',
            },
            {
              label: 'Avg Latency',
              // `?? 0` here used to print "0.0s" for a run that never timed
              // anything, which reads as a run that finished instantly.
              value: summary?.avg_latency_ms == null
                ? '—'
                : `${(summary.avg_latency_ms / 1000).toFixed(1)}s`,
              color: '#8b5cf6',
            },
            {
              label: 'Exec Mode',
              value: meta?.execution_mode === 'code_interpreter' ? '☁️ CI'
                : meta?.execution_mode === 'subprocess' ? '🖥️ Sub'
                : meta?.execution_mode === 'agentic_sandbox' ? 'Agent'
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

        {/* ── Execution Summary ── */}
        {report.narrative?.overview && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.05 }}
            className="bg-dash-card border border-dash-border rounded-xl p-4 md:p-5 mb-6"
          >
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-sm font-semibold text-dash-heading">Execution Summary</h3>
              <ScopeBadge scope={resolvedScope} />
            </div>
            <p className="text-xs text-dash-text-secondary leading-relaxed whitespace-pre-line">
              {report.narrative.overview}
            </p>
          </motion.div>
        )}

        {relatedJournalArticles.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.07 }}
            className="bg-dash-card border border-dash-border rounded-xl overflow-hidden mb-6"
          >
            <div className="px-4 py-3 border-b border-dash-border flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-emerald-500" />
                <h3 className="text-sm font-semibold text-dash-heading">Related Notes</h3>
              </div>
              <Link to="/notes" className="inline-flex items-center gap-1 text-[10px] text-dash-text-muted hover:text-emerald-500 transition-colors">
                모든 기록 <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="grid md:grid-cols-2">
              {relatedJournalArticles.map((article, index) => (
                <Link
                  key={article.slug}
                  to={`/notes/${article.slug}`}
                  className={`group px-4 py-4 hover:bg-dash-card-hover transition-colors ${index % 2 === 0 ? 'md:border-r md:border-dash-border' : ''} ${index >= 2 ? 'border-t border-dash-border' : index === 1 ? 'border-t md:border-t-0 border-dash-border' : ''}`}
                >
                  <div className="text-[10px] text-dash-text-muted mb-1.5">{lensLabels[article.lens]}</div>
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-xs font-medium text-dash-heading leading-relaxed group-hover:text-emerald-500 transition-colors">{article.title}</h4>
                    <ArrowRight className="w-3 h-3 text-dash-text-faint flex-shrink-0 mt-0.5" />
                  </div>
                </Link>
              ))}
            </div>
          </motion.section>
        )}

        {/* ── Key Metrics (Extended) ── */}
        {summary && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.08 }}
            className="bg-dash-card border border-dash-border rounded-xl overflow-hidden mb-6"
          >
            <div className="px-4 py-3 border-b border-dash-border">
              <h3 className="text-sm font-semibold text-dash-heading">Key Metrics</h3>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                {[
                  { label: 'Total Tasks', value: summary.total_tasks },
                  { label: 'Success', value: `${summary.success_count} (${summary.success_rate_pct}%)` },
                  { label: 'Errors', value: summary.error_count },
                  { label: 'Retried Tasks', value: summary.retried_count },
                  { label: 'Avg QA Score', value: fmtScore(summary.avg_qa_score) },
                  { label: 'Min QA Score', value: fmtScore(summary.min_qa_score) },
                  { label: 'Max QA Score', value: fmtScore(summary.max_qa_score) },
                  { label: 'Avg Latency', value: secondsOrDash(summary.avg_latency_ms, 1) },
                  { label: 'Max Latency', value: secondsOrDash(summary.max_latency_ms, 1) },
                  { label: 'Total LLM Time', value: secondsOrDash(summary.total_latency_ms, 0) },
                ].map((m, i) => (
                  <div key={i}>
                    <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">{m.label}</div>
                    <div className="text-dash-text font-mono font-semibold">{m.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {report.execution_metrics && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.09 }}
            className="bg-dash-card border border-dash-border rounded-xl overflow-hidden mb-6"
          >
            <div className="px-4 py-3 border-b border-dash-border flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-dash-heading flex items-center gap-2">
                <Timer className="h-4 w-4 text-emerald-500" />
                Job Performance
              </h3>
              <span className="text-[10px] text-dash-text-muted font-mono">
                {report.execution_metrics.measured_tasks}/{report.execution_metrics.total_tasks} measured
              </span>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-x-5 gap-y-4 text-xs">
                {[
                  { label: 'Avg Job Time', value: formatDuration(report.execution_metrics.avg_task_wall_time_ms) },
                  { label: 'P50 Job Time', value: formatDuration(report.execution_metrics.p50_task_wall_time_ms) },
                  { label: 'P95 Job Time', value: formatDuration(report.execution_metrics.p95_task_wall_time_ms) },
                  { label: 'Time to Valid File', value: formatDuration(report.execution_metrics.avg_time_to_valid_artifact_ms) },
                  { label: 'Successful Job Avg', value: formatDuration(report.execution_metrics.avg_successful_task_wall_time_ms) },
                  { label: 'Failed Job Avg', value: formatDuration(report.execution_metrics.avg_failed_task_wall_time_ms) },
                ].map((metric) => (
                  <div key={metric.label}>
                    <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">{metric.label}</div>
                    <div className="text-dash-text font-mono font-semibold">{metric.value}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-4 border-t border-dash-border-subtle grid grid-cols-2 md:grid-cols-5 gap-x-5 gap-y-3 text-xs">
                {[
                  { label: 'Model', value: formatDuration(report.execution_metrics.total_model_time_ms) },
                  { label: 'Tools', value: formatDuration(report.execution_metrics.total_tool_time_ms) },
                  { label: 'Verification', value: formatDuration(report.execution_metrics.total_verification_time_ms) },
                  { label: 'Dependencies', value: formatDuration(report.execution_metrics.total_dependency_time_ms) },
                  { label: 'Self-QA', value: formatDuration(report.execution_metrics.total_self_qa_time_ms) },
                  { label: 'Orchestration', value: formatDuration(report.execution_metrics.total_orchestration_time_ms) },
                  { label: 'Execution Attempts', value: report.execution_metrics.total_execution_attempts },
                  { label: 'Sandbox Attempts', value: report.execution_metrics.total_sandbox_attempts },
                  { label: 'Tool Calls', value: report.execution_metrics.total_tool_calls },
                  { label: 'Self-QA Calls', value: report.execution_metrics.total_self_qa_calls },
                  { label: 'Coverage', value: `${report.execution_metrics.coverage_pct.toFixed(1)}%` },
                ].map((metric) => (
                  <div key={metric.label} className="flex justify-between md:block gap-2">
                    <span className="text-dash-text-muted">{metric.label}</span>
                    <span className="text-dash-text font-mono md:block md:mt-0.5">{metric.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {report.agentic_metrics && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="bg-dash-card border border-dash-border rounded-xl overflow-hidden mb-6"
          >
            <div className="px-4 py-3 border-b border-dash-border flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-dash-heading flex items-center gap-2">
                <Code2 className="h-4 w-4 text-emerald-500" />
                Agentic Tool Loop
              </h3>
              <span className="text-[10px] text-dash-text-muted font-mono">
                {report.agentic_metrics.measured_tasks}/{report.agentic_metrics.total_tasks} measured
              </span>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-x-5 gap-y-4 text-xs">
                {[
                  { label: 'API Calls', value: report.agentic_metrics.total_model_api_calls },
                  { label: 'Model Iterations', value: report.agentic_metrics.total_model_iterations },
                  { label: 'Tool Calls', value: report.agentic_metrics.total_tool_calls },
                  { label: 'Tool Error Rate', value: `${report.agentic_metrics.tool_error_rate_pct.toFixed(1)}%` },
                  { label: 'Recovery Rate', value: `${report.agentic_metrics.recovery_rate_pct.toFixed(1)}%` },
                  { label: 'Finalize Attempts', value: report.agentic_metrics.total_finalize_attempts },
                  { label: 'P50 Tool Time', value: formatDuration(report.agentic_metrics.p50_tool_time_ms) },
                  { label: 'P95 Tool Time', value: formatDuration(report.agentic_metrics.p95_tool_time_ms) },
                  { label: 'Usage Coverage', value: `${report.agentic_metrics.usage_coverage_pct.toFixed(1)}%` },
                  { label: 'Cached Tokens', value: report.agentic_metrics.total_cached_tokens.toLocaleString() },
                  { label: 'Capability Misses', value: report.agentic_metrics.total_capability_misses },
                  { label: 'Conservative Cost', value: `$${report.agentic_metrics.conservative_cost_usd.toFixed(4)}` },
                ].map((metric) => (
                  <div key={metric.label}>
                    <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">{metric.label}</div>
                    <div className="text-dash-text font-mono font-semibold">{metric.value}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-4 border-t border-dash-border-subtle grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-x-5 gap-y-3 text-xs">
                {Object.entries(report.agentic_metrics.tool_calls_by_name).map(([name, count]) => (
                  <div key={name} className="flex justify-between md:block gap-2">
                    <span className="text-dash-text-muted">{name.split('_').join(' ')}</span>
                    <span className="text-dash-text font-mono md:block md:mt-0.5">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── Cost: problem-solving and grading, side by side ── */}
        <CostSummaryCard
          problemSolving={problemSolvingSummary}
          grading={gradingSummary}
          gradeLedger={gradeRow?.cost_ledger ?? null}
          reportLedger={report.cost_ledger ?? null}
        />

        {/* ── File Generation & Resume Rounds ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {report.file_generation && report.file_generation.needs_files_total != null && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.1 }}
              className="bg-dash-card border border-dash-border rounded-xl p-4"
            >
              <h3 className="text-sm font-semibold text-dash-heading mb-3">File Generation</h3>
              <div className="space-y-2 text-xs">
                {[
                  { label: 'Tasks requiring files', value: report.file_generation.needs_files_total },
                  { label: 'Successfully generated', value: `${report.file_generation.files_succeeded} (${report.file_generation.needs_files_total > 0 ? ((report.file_generation.files_succeeded / report.file_generation.needs_files_total) * 100).toFixed(1) : 0}%)` },
                  { label: 'Failed → dummy created', value: report.file_generation.files_failed },
                  // Only when there are any. A report written before step5
                  // counted them carries no number here, and no number is not
                  // the same claim as none.
                  ...((report.file_generation.files_absent ?? 0) > 0
                    ? [{ label: 'Absent from submission (never checked)', value: report.file_generation.files_absent as number }]
                    : []),
                ].map((row, i) => (
                  <div key={i} className="flex justify-between py-1 border-b border-dash-border-subtle last:border-0">
                    <span className="text-dash-text-secondary">{row.label}</span>
                    <span className="text-dash-text font-mono font-semibold">{row.value}</span>
                  </div>
                ))}
              </div>
              {(report.file_generation.files_absent ?? 0) > 0 && (
                <p className="mt-2 text-[10px] leading-snug text-amber-400/90">
                  {report.file_generation.files_absent} of these tasks have no row in the
                  submission, so nothing was read for them. The percentage above is out of a
                  denominator that includes them.
                </p>
              )}
            </motion.div>
          )}
          {report.recovery_stats?.resume_rounds?.per_round &&
            Object.keys(report.recovery_stats.resume_rounds.per_round).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.12 }}
              className="bg-dash-card border border-dash-border rounded-xl p-4"
            >
              <h3 className="text-sm font-semibold text-dash-heading mb-3">Resume Rounds</h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[10px] text-dash-text-muted uppercase border-b border-dash-border">
                    <th className="py-1.5 text-left">Round</th>
                    <th className="py-1.5 text-right">Attempted</th>
                    <th className="py-1.5 text-right">Recovered</th>
                    <th className="py-1.5 text-right">Still Failed</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.recovery_stats.resume_rounds.per_round).map(([round, data]) => (
                    <tr key={round} className="border-b border-dash-border-subtle last:border-0">
                      <td className="py-1.5 text-dash-text font-mono">{round}</td>
                      <td className="py-1.5 text-right text-dash-text-secondary font-mono">{data.attempted}</td>
                      <td className="py-1.5 text-right font-mono text-emerald-400">{data.recovered}</td>
                      <td className="py-1.5 text-right font-mono text-red-400">{data.still_failed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </motion.div>
          )}
        </div>

        {/* ── v2: Policy Comparison & Confidence Distribution ── */}
        {(summary?.policy_counts || summary?.confidence_distribution) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* Policy Comparison */}
            {summary?.policy_counts && Object.keys(summary.policy_counts).length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.13 }}
                className="bg-dash-card border border-dash-border rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-dash-heading">Policy Comparison</h3>
                  {summary.active_policy && (
                    <span
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-dash-card-hover text-dash-text-secondary"
                      title="Currently active policy"
                    >
                      active: <span className="text-emerald-400">{summary.active_policy}</span>
                    </span>
                  )}
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart
                    data={Object.entries(summary.policy_counts).map(([policy, count]) => ({
                      policy,
                      count: count ?? 0,
                      isActive: policy === summary.active_policy,
                    }))}
                    margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                    <XAxis dataKey="policy" tick={{ ...tickStyle, fontSize: 10 }} />
                    <YAxis tick={tickStyle} allowDecimals={false} />
                    <Tooltip contentStyle={chartTooltipStyle} />
                    <Bar dataKey="count" name="needs_files">
                      {Object.entries(summary.policy_counts).map(([policy], i) => (
                        <Cell
                          key={i}
                          fill={policy === summary.active_policy ? '#10b981' : '#6366f1'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <table className="w-full text-xs mt-2">
                  <thead>
                    <tr className="text-[10px] text-dash-text-muted uppercase border-b border-dash-border">
                      <th className="py-1.5 text-left">Policy</th>
                      <th className="py-1.5 text-right">needs_files</th>
                      <th className="py-1.5 text-right">Δ vs active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(summary.policy_counts).map(([policy, count]) => {
                      const active = summary.active_policy
                      const activeCount = active && summary.policy_counts ? summary.policy_counts[active] ?? null : null
                      const delta = activeCount != null && count != null ? count - activeCount : null
                      const isActive = policy === active
                      return (
                        <tr key={policy} className="border-b border-dash-border-subtle last:border-0">
                          <td className="py-1.5 text-dash-text font-mono">
                            {policy}
                            {isActive && (
                              <span className="ml-1.5 text-[9px] text-emerald-400">●</span>
                            )}
                          </td>
                          <td className="py-1.5 text-right text-dash-text-secondary font-mono">{count ?? 0}</td>
                          <td className="py-1.5 text-right font-mono text-dash-text-muted">
                            {delta == null || isActive ? '—' : delta > 0 ? `+${delta}` : `${delta}`}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </motion.div>
            )}

            {/* Confidence Distribution */}
            {summary?.confidence_distribution && Object.keys(summary.confidence_distribution).length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.14 }}
                className="bg-dash-card border border-dash-border rounded-xl p-4"
              >
                <h3 className="text-sm font-semibold text-dash-heading mb-3">Confidence Distribution</h3>
                {(() => {
                  const CONFIDENCE_COLORS: Record<string, string> = {
                    explicit: '#10b981',
                    inferred: '#6366f1',
                    ambiguous: '#f59e0b',
                    text_only: '#6b7280',
                  }
                  const entries = Object.entries(summary.confidence_distribution!).map(([k, v]) => ({
                    name: k,
                    value: v ?? 0,
                  }))
                  const total = entries.reduce((s, e) => s + (e.value || 0), 0)
                  return (
                    <>
                      <ResponsiveContainer width="100%" height={200}>
                        <PieChart>
                          <Pie
                            data={entries}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            outerRadius={70}
                            innerRadius={40}
                            paddingAngle={2}
                            label={(entry: { value?: number }) => (entry.value ? String(entry.value) : '')}
                          >
                            {entries.map((entry, i) => (
                              <Cell key={i} fill={CONFIDENCE_COLORS[entry.name] ?? '#9ca3af'} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={chartTooltipStyle} />
                          <Legend
                            verticalAlign="bottom"
                            iconSize={8}
                            wrapperStyle={{ fontSize: 10, color: isDark ? '#e5e7eb' : '#374151' }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                        {entries.map((e) => {
                          const pct = total > 0 ? ((e.value / total) * 100).toFixed(1) : '0.0'
                          return (
                            <div key={e.name} className="flex items-center justify-between py-1 border-b border-dash-border-subtle last:border-0">
                              <span className="flex items-center gap-1.5 text-dash-text-secondary">
                                <span
                                  className="inline-block w-2 h-2 rounded-full"
                                  style={{ background: CONFIDENCE_COLORS[e.name] ?? '#9ca3af' }}
                                />
                                <span className="font-mono">{e.name}</span>
                              </span>
                              <span className="font-mono text-dash-text">
                                {e.value} <span className="text-dash-text-muted">({pct}%)</span>
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </>
                  )
                })()}
              </motion.div>
            )}
          </div>
        )}

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

        {/* ── Sector Breakdown Table ── */}
        {report.sector_breakdown && report.sector_breakdown.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.15 }}
            className="bg-dash-card border border-dash-border rounded-xl overflow-hidden mb-6"
          >
            <div className="px-4 py-3 border-b border-dash-border">
              <h3 className="text-sm font-semibold text-dash-heading">Sector Breakdown</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[10px] text-dash-text-muted uppercase border-b border-dash-border">
                    <th className="px-4 py-2 text-left">Sector</th>
                    <th className="px-3 py-2 text-right">Tasks</th>
                    <th className="px-3 py-2 text-right">Success</th>
                    <th className="px-3 py-2 text-right">Success%</th>
                    <th className="px-3 py-2 text-right">Avg QA</th>
                    <th className="px-3 py-2 text-right">Avg Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {report.sector_breakdown.map((s) => (
                    <tr key={s.sector} className="border-b border-dash-border-subtle last:border-0 hover:bg-dash-card-hover transition">
                      <td className="px-4 py-2 text-dash-text">{s.sector}</td>
                      <td className="px-3 py-2 text-right font-mono text-dash-text-secondary">{s.total}</td>
                      <td className="px-3 py-2 text-right font-mono text-dash-text-secondary">{s.success}</td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: rateColor(s.success_rate_pct) }}>
                        {s.success_rate_pct.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: qaColor(s.avg_qa_score) }}>
                        {fmtScore(s.avg_qa_score, 1)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-dash-text-muted">
                        {secondsOrDash(s.avg_latency_ms, 1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}

        {/* ── Analysis Narratives ── */}
        {(report.narrative?.quality_analysis || report.narrative?.failure_patterns || report.narrative?.recommendations) && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.18 }}
            className="space-y-4 mb-8"
          >
            {report.narrative.quality_analysis && (
              <div className="bg-dash-card border border-dash-border rounded-xl p-4">
                <h3 className="text-sm font-semibold text-dash-heading mb-2">Quality Analysis</h3>
                <p className="text-xs text-dash-text-secondary leading-relaxed whitespace-pre-line">
                  {report.narrative.quality_analysis}
                </p>
              </div>
            )}
            {report.narrative.failure_patterns && (
              <div className="bg-dash-card border border-dash-border rounded-xl p-4">
                <h3 className="text-sm font-semibold text-dash-heading mb-2">Failure Patterns</h3>
                <p className="text-xs text-dash-text-secondary leading-relaxed whitespace-pre-line">
                  {report.narrative.failure_patterns}
                </p>
              </div>
            )}
            {report.narrative.recommendations && (
              <div className="bg-dash-card border border-dash-border rounded-xl p-4">
                <h3 className="text-sm font-semibold text-dash-heading mb-2">Recommendations</h3>
                <p className="text-xs text-dash-text-secondary leading-relaxed whitespace-pre-line">
                  {report.narrative.recommendations}
                </p>
              </div>
            )}
          </motion.div>
        )}

        {/* ── Prompt Architecture ── */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.19 }}
          className="mb-8"
        >
          <button
            onClick={() => setShowPromptArch(!showPromptArch)}
            className="w-full flex items-center gap-3 px-5 py-4 text-sm font-bold rounded-xl border transition-all duration-200 mb-4 cursor-pointer group
              bg-gradient-to-r from-blue-500/10 via-indigo-500/5 to-transparent
              dark:border-blue-500/25 dark:hover:border-blue-400/40 border-blue-300 hover:border-blue-400
              dark:text-blue-200 dark:hover:text-blue-100 text-blue-700 hover:text-blue-800
              dark:shadow-[0_0_15px_rgba(59,130,246,0.08)] dark:hover:shadow-[0_0_20px_rgba(59,130,246,0.15)]
              shadow-sm hover:shadow-md"
          >
            <div className="flex items-center justify-center w-8 h-8 rounded-lg dark:bg-blue-500/15 dark:group-hover:bg-blue-500/25 bg-blue-100 group-hover:bg-blue-200 transition">
              <Code2 className="w-4 h-4" />
            </div>
            <div className="flex-1 text-left">
              <span>{showPromptArch ? 'Hide' : 'View'} Prompt Architecture</span>
              <span className="block text-[11px] font-normal dark:text-blue-400/50 text-blue-500/70">System · User Prompt · QA · Execution Config</span>
            </div>
            {showPromptArch ? <ChevronDown className="w-5 h-5 dark:text-blue-400/60 text-blue-500" /> : <ChevronRight className="w-5 h-5 dark:text-blue-400/60 text-blue-500" />}
          </button>
          <AnimatePresence>
            {showPromptArch && promptArch && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="overflow-hidden"
              >
                <div className="bg-dash-card border border-dash-border rounded-xl p-4">
                  <PromptArchitectureView prompt={promptArch} shortId={id ?? ''} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
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
              {/* QA Score filter */}
              <select
                value={qaScoreFilter}
                onChange={(e) => setQaScoreFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                className="bg-dash-card-hover border border-dash-border rounded-lg px-2 py-1.5 text-xs text-dash-text"
              >
                <option value="all">All QA Scores</option>
                <option value="3">QA ≤ 3 (Critical)</option>
                <option value="5">QA ≤ 5 (Below Pass)</option>
                <option value="7">QA ≤ 7 (Needs Work)</option>
                <option value="10">QA ≤ 10 (All Scored)</option>
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
                  <th
                    className="px-3 py-2 text-right cursor-pointer whitespace-nowrap"
                    onClick={() => handleSort('problem_solving_cost')}
                    title={COST_ESTIMATE_NOTE}
                  >
                    문제 풀이 비용
                  </th>
                  <th
                    className="px-3 py-2 text-right cursor-pointer whitespace-nowrap"
                    onClick={() => handleSort('grading_cost')}
                    title={COST_ESTIMATE_NOTE}
                  >
                    채점 비용
                  </th>
                  {report.execution_metrics && (
                    <th className="px-3 py-2 text-right cursor-pointer" onClick={() => handleSort('task_wall_time_ms')}>
                      Job Time
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredTasks.map((task, i) => {
                  const problemCost = costCell(task.problem_solving_cost, 'problem_solving_cost')
                  const gradeCost = costCell(
                    gradingCosts.receipts.get(task.task_id),
                    'grading_cost',
                    { ran: gradingCosts.attempted.has(task.task_id) },
                  )
                  return (
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
                    <td
                      className={`px-3 py-2 text-right font-mono whitespace-nowrap ${costCellClass(problemCost)}`}
                      title={problemCost.title}
                      data-cost-field="problem_solving_cost"
                      data-cost-state={problemCost.state}
                    >
                      {problemCost.text}
                    </td>
                    <td
                      className={`px-3 py-2 text-right font-mono whitespace-nowrap ${costCellClass(gradeCost)}`}
                      title={gradeCost.title}
                      data-cost-field="grading_cost"
                      data-cost-state={gradeCost.state}
                    >
                      {gradeCost.text}
                    </td>
                    {report.execution_metrics && (
                      <td className="px-3 py-2 text-right font-mono text-dash-text-muted">
                        {formatDuration(task.observability?.execution_metrics?.task_wall_time_ms)}
                      </td>
                    )}
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Task Detail Modal */}
        <AnimatePresence>
          {selectedTask && (
            <TaskDetailModal
              task={selectedTask}
              experimentId={meta?.experiment_id}
              gradingCost={gradingCosts.receipts.get(selectedTask.task_id) ?? null}
              gradingRan={gradingCosts.attempted.has(selectedTask.task_id)}
              onClose={() => setSelectedTask(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

/**
 * Run-level cost, both fields side by side.
 *
 * Always rendered, including for the runs that predate cost instrumentation:
 * an experiment that recorded nothing has to say 기록 없음 out loud, because a
 * hidden card and a $0 card are equally easy to misread as "this was free".
 */
function CostSummaryCard({
  problemSolving,
  grading,
  gradeLedger,
  reportLedger,
}: {
  problemSolving: CostSummary | null
  grading: CostSummary | null
  gradeLedger: { path: string; sha256: string } | null
  reportLedger: { path: string; sha256: string } | null
}) {
  const columns = [
    { field: 'problem_solving_cost' as const, summary: problemSolving, ledger: reportLedger },
    { field: 'grading_cost' as const, summary: grading, ledger: gradeLedger },
  ]
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 }}
      className="bg-dash-card border border-dash-border rounded-xl overflow-hidden mb-6"
      data-testid="cost-summary"
    >
      <div className="px-4 py-3 border-b border-dash-border flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-dash-heading flex items-center gap-2">
          <Receipt className="h-4 w-4 text-sky-500" />
          비용
        </h3>
        <span className="text-[10px] text-dash-text-muted" data-testid="cost-estimate-note">
          {COST_ESTIMATE_NOTE}
        </span>
      </div>
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
        {columns.map(({ field, summary, ledger }) => (
          <div key={field} data-cost-summary-field={field}>
            <div className="flex items-baseline justify-between gap-2 mb-2">
              <h4 className="text-xs font-semibold text-dash-heading">{COST_FIELD_LABELS[field]}</h4>
              {summary && (
                <span className="text-[10px] text-dash-text-muted">
                  {summaryStatusLabel(summary.status)}
                </span>
              )}
            </div>
            {!summary ? (
              <p
                className="text-xs text-dash-text-faint leading-relaxed"
                data-cost-state="absent"
              >
                기록 없음 — 이 실행에는 비용 기록이 없습니다. $0이 아니라, 얼마가 들었는지
                알 수 없다는 뜻입니다.
              </p>
            ) : (
              <div className="space-y-1 text-xs">
                {[
                  { label: '총액', cell: summaryTotalCell(summary, field) },
                  { label: '평균', cell: summaryStatCell(summary.avg_cost_usd) },
                  { label: '중앙값', cell: summaryStatCell(summary.median_cost_usd) },
                  { label: 'P95', cell: summaryStatCell(summary.p95_cost_usd) },
                  { label: '최대', cell: summaryStatCell(summary.max_cost_usd) },
                  ...(field === 'problem_solving_cost'
                    ? [{ label: '성공 결과물 1건당', cell: perDeliverableCell(summary) }]
                    : []),
                ].map(({ label, cell }) => (
                  <div
                    key={label}
                    className="flex justify-between gap-2 border-b border-dash-border-subtle py-1 last:border-0"
                  >
                    <span className="text-dash-text-muted">{label}</span>
                    <span
                      className={`font-mono ${costCellClass(cell)}`}
                      title={cell.title}
                      data-cost-stat={label}
                      data-cost-state={cell.state}
                    >
                      {cell.text}
                    </span>
                  </div>
                ))}
                {/* Failed work costs money. It sits beside the total, not inside it. */}
                {(() => {
                  const failedCell = failedTaskCostCell(summary)
                  return (
                    <div className="flex justify-between gap-2 py-1">
                      <span className="text-dash-text-muted">실패 작업 비용</span>
                      <span
                        className="font-mono text-amber-400"
                        title={`${COST_FIELD_LABELS[field]}: 실패한 작업에도 비용이 들었습니다. 총액에서 빼지 않았습니다. · ${failedCell.title}`}
                        data-cost-stat="실패 작업 비용"
                        data-cost-state={failedCell.state}
                      >
                        {summary.failed_task_count}건 · {failedCell.text}
                      </span>
                    </div>
                  )
                })()}
                <div className="flex justify-between gap-2 py-1 text-[11px]">
                  <span className="text-dash-text-muted">기록 범위</span>
                  <span className="font-mono text-dash-text-secondary">
                    {summary.receipt_tasks} / {summary.total_tasks}건 ({summary.coverage_pct}%)
                  </span>
                </div>
                {(() => {
                  // Gated on the text, not on `missing_reasons.length`: the
                  // reader already guards the list, and a second raw `.length`
                  // beside it would be the one place still able to throw.
                  const reasons = missingReasonText(summary.missing_reasons)
                  if (!reasons) return null
                  return (
                    <p className="text-[11px] text-amber-400/80 pt-1">미가격 사유: {reasons}</p>
                  )
                })()}
                {ledger && (
                  <p className="text-[10px] text-dash-text-faint font-mono pt-1 break-all">
                    🧾 {ledger.path} · sha256 {ledger.sha256.slice(0, 12)}…
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </motion.div>
  )
}

function TaskDetailModal({
  task,
  experimentId,
  gradingCost,
  gradingRan,
  onClose,
}: {
  task: TaskResult
  experimentId?: string
  gradingCost: CostReceipt | null
  gradingRan: boolean
  onClose: () => void
}) {
  const [showPrompt, setShowPrompt] = useState(false)
  const executionMetrics = task.observability?.execution_metrics
  const agenticMetrics = task.observability?.agentic_metrics
  const combinedCost = combinedTaskCost(task.problem_solving_cost, gradingCost)
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

          {executionMetrics && (
            <div className="border border-dash-border rounded-lg p-3">
              <div className="text-[10px] text-dash-text-muted uppercase mb-2 flex items-center gap-1.5">
                <Timer className="h-3 w-3" /> Job Performance
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                {[
                  { label: 'Job Time', value: formatDuration(executionMetrics.task_wall_time_ms) },
                  { label: 'Time to Valid File', value: formatDuration(executionMetrics.time_to_valid_artifact_ms) },
                  { label: 'Model', value: formatDuration(executionMetrics.model_time_ms) },
                  { label: 'Tools', value: formatDuration(executionMetrics.tool_time_ms) },
                  { label: 'Verification', value: formatDuration(executionMetrics.verification_time_ms) },
                  { label: 'Self-QA', value: formatDuration(executionMetrics.self_qa_time_ms) },
                  { label: 'Orchestration', value: formatDuration(executionMetrics.orchestration_time_ms) },
                  { label: 'Execution Attempts', value: executionMetrics.execution_attempt_count },
                  { label: 'Tool Calls', value: executionMetrics.tool_call_count },
                ].map((metric) => (
                  <div key={metric.label} className="flex justify-between gap-2 border-b border-dash-border-subtle py-1 last:border-0">
                    <span className="text-dash-text-muted">{metric.label}</span>
                    <span className="text-dash-text font-mono">{metric.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {agenticMetrics && (
            <div className="border border-dash-border rounded-lg p-3">
              <div className="text-[10px] text-dash-text-muted uppercase mb-2 flex items-center gap-1.5">
                <Code2 className="h-3 w-3" /> Agentic Tool Loop
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                {[
                  { label: 'API Calls', value: agenticMetrics.model_api_calls },
                  { label: 'Iterations', value: agenticMetrics.model_iterations },
                  { label: 'Tool Calls', value: agenticMetrics.tool_calls },
                  { label: 'Tool Errors', value: agenticMetrics.tool_errors },
                  { label: 'Finalize Attempts', value: agenticMetrics.finalize_attempts },
                  { label: 'Finalize Corrections', value: agenticMetrics.finalize_required_corrections },
                  { label: 'Input Tokens', value: agenticMetrics.input_tokens.toLocaleString() },
                  { label: 'Output Tokens', value: agenticMetrics.output_tokens.toLocaleString() },
                  { label: 'Cached Tokens', value: agenticMetrics.cached_tokens.toLocaleString() },
                  { label: 'Conservative Cost', value: `$${agenticMetrics.conservative_cost_usd.toFixed(4)}` },
                  { label: 'Usage Complete', value: agenticMetrics.usage_complete ? 'Yes' : 'No' },
                  { label: 'Terminal Category', value: agenticMetrics.terminal_error_category || 'none' },
                ].map((metric) => (
                  <div key={metric.label} className="flex justify-between gap-2 border-b border-dash-border-subtle py-1 last:border-0">
                    <span className="text-dash-text-muted">{metric.label}</span>
                    <span className="text-dash-text font-mono text-right break-all">{metric.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── What this one task cost: to solve, and to grade ── */}
          <div className="border border-dash-border rounded-lg p-3" data-testid="task-cost">
            <div className="text-[10px] text-dash-text-muted uppercase mb-2 flex items-center gap-1.5">
              <Receipt className="h-3 w-3" /> 비용
            </div>
            <div className="space-y-2 text-xs">
              {([
                {
                  field: 'problem_solving_cost' as const,
                  receipt: task.problem_solving_cost ?? null,
                  // The task itself ran; whether it was priced is the receipt's business.
                  ran: true,
                },
                { field: 'grading_cost' as const, receipt: gradingCost, ran: gradingRan },
              ]).map(({ field, receipt, ran }) => {
                const cell = costCell(receipt, field, { ran })
                // Runtime is not a model call, so it is not one of the component
                // lines. It gets its own, and only when something was charged.
                const runtime = receipt ? runtimeLineAmount(receipt) : null
                // `components` is read through the accessor, not off the object.
                // It arrives on an unvalidated fetch, and a `components` that is
                // not an array made `.length` undefined and `.map` a TypeError,
                // which the error boundary in App.tsx turned into a blank page.
                const components = receipt ? receiptComponents(receipt) : []
                return (
                  <div key={field}>
                    <div className="flex justify-between gap-2 border-b border-dash-border-subtle py-1">
                      <span className="text-dash-text-secondary">{COST_FIELD_LABELS[field]}</span>
                      <span
                        className={`font-mono ${costCellClass(cell)}`}
                        title={cell.title}
                        data-cost-field={field}
                        data-cost-state={cell.state}
                      >
                        {cell.text}
                      </span>
                    </div>
                    {receipt && (components.length > 0 || runtime !== null) && (
                      // Keyed by field: the same stage can legitimately appear
                      // under both, e.g. a perception read the solver made and
                      // one the judge made, and they must not read as one line.
                      <div className="pl-3 pt-1 space-y-0.5" data-cost-components={field}>
                        {components.map((component) => {
                          const text = componentAmountText(component)
                          return (
                            <div
                              // Two stages that each had to retry are two rows
                              // both labelled 재시도. The stage and retry kind
                              // are what tell them apart, so they are the key.
                              key={componentKey(component)}
                              className="flex justify-between gap-2 text-[11px]"
                              data-cost-component={component.name}
                              data-cost-component-key={componentKey(component)}
                            >
                              <span
                                className="text-dash-text-muted"
                                title={componentDetail(component)}
                              >
                                · {componentLabel(component.name)}
                              </span>
                              <span
                                className="font-mono text-dash-text-secondary"
                                title={COST_ESTIMATE_NOTE}
                              >
                                {text}
                              </span>
                            </div>
                          )
                        })}
                        {runtime !== null && (
                          // Runtime is not a model call, so it is not one of the
                          // lines above. It is shown once here so the lines and
                          // the total agree without being added twice.
                          <div
                            className="flex justify-between gap-2 text-[11px]"
                            data-cost-runtime={field}
                          >
                            <span className="text-dash-text-muted">· 실행 환경</span>
                            <span
                              className="font-mono text-dash-text-secondary"
                              title={COST_ESTIMATE_NOTE}
                            >
                              {formatCostUsd(runtime)}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
              {combinedCost && (
                <div className="flex justify-between gap-2 border-t border-dash-border pt-2 mt-1">
                  <span className="text-dash-text font-semibold">합계</span>
                  <span
                    className={`font-mono font-semibold ${costCellClass(combinedCost)}`}
                    title={combinedCost.title}
                    data-cost-field="combined"
                    data-cost-state={combinedCost.state}
                  >
                    {combinedCost.text}
                  </span>
                </div>
              )}
            </div>
            <p className="text-[10px] text-dash-text-faint mt-2">{COST_ESTIMATE_NOTE}</p>
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

          {/* Task Prompt (Collapsible) */}
          {task.instruction && (
            <div>
              <button
                onClick={() => setShowPrompt(!showPrompt)}
                className="text-[10px] text-dash-text-muted uppercase flex items-center gap-1 hover:text-dash-text-secondary transition"
              >
                {showPrompt ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Task Prompt
              </button>
              {showPrompt && (
                <div className="mt-1.5 max-h-48 overflow-y-auto bg-dash-card-hover rounded-lg p-3">
                  <p className="text-xs text-dash-text-secondary whitespace-pre-wrap leading-relaxed">
                    {task.instruction}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Reference Files */}
          {task.reference_file_urls && task.reference_file_urls.length > 0 && (
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-1.5">
                📎 Reference Files ({task.reference_file_urls.length})
              </div>
              <div className="space-y-1">
                {task.reference_file_urls.map((url, i) => (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between text-xs text-blue-400 hover:text-blue-300 bg-dash-card-hover rounded px-2 py-1.5 transition"
                  >
                    <span className="truncate">{decodeURIComponent(url.split('/').pop() || '')}</span>
                    <span className="text-[10px] ml-2 shrink-0">↗ Open</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Deliverable Files */}
          {task.deliverable_files && task.deliverable_files.length > 0 && experimentId && (
            <div>
              <div className="text-[10px] text-dash-text-muted uppercase mb-1.5">
                📦 Deliverable Files ({task.deliverable_files.length})
              </div>
              <div className="space-y-1">
                {task.deliverable_files.map((relPath, i) => {
                  const hfUrl = `${HF_BASE}/${experimentId}/resolve/main/${relPath}`
                  const filename = relPath.split('/').pop() || relPath
                  return (
                    <a
                      key={i}
                      href={hfUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between text-xs text-emerald-400 hover:text-emerald-300 bg-dash-card-hover rounded px-2 py-1.5 transition"
                    >
                      <span className="truncate">{filename}</span>
                      <span className="text-[10px] ml-2 shrink-0">↓ Open</span>
                    </a>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default ExperimentDetail
