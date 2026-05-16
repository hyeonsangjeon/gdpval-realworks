import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { ExperimentEntry, SectorMatrix } from '../../types/report'
import { useTheme } from '../../contexts/ThemeContext'
import InfoTooltip from '../common/InfoTooltip'
import SectionHint from '../common/SectionHint'
import { tooltipTexts, sectionHintTexts } from '../../data/tooltipTexts'
import { substituteTaskTotal } from '../../lib/textFormat'

interface LeaderboardViewProps {
  experiments: ExperimentEntry[]
  sectorMatrix: SectorMatrix
  onSelectExperiment: (shortId: string) => void
  totalTasks?: number
}

const EXPERIMENT_COLORS: Record<string, string> = {
  exp003: '#3b82f6',
  exp004: '#f59e0b',
  exp005: '#ef4444',
  exp006: '#10b981',
  exp007: '#8b5cf6',
  exp008: '#ec4899',
  exp009: '#14b8a6',
  exp010: '#f97316',
}

const MODE_BADGES: Record<string, { label: string; icon: string }> = {
  code_interpreter: { label: 'CI', icon: '☁️' },
  subprocess: { label: 'Sub', icon: '🖥️' },
  json_renderer: { label: 'JSON', icon: '📄' },
}

const ITEMS_PER_PAGE = 10

function getRateColor(rate: number): string {
  if (rate >= 96) return 'text-emerald-400'
  if (rate >= 90) return 'text-amber-400'
  return 'text-red-400'
}

function getQAColor(score: number): string {
  if (score >= 7) return 'text-emerald-400'
  if (score >= 5) return 'text-amber-400'
  return 'text-red-400'
}

function getExpColor(shortId: string): string {
  return EXPERIMENT_COLORS[shortId] || '#999'
}

function getModeBadge(mode: string) {
  const badge = MODE_BADGES[mode] || { label: mode, icon: '⚙️' }
  return badge
}

/** Continuous heatmap color: red → amber → emerald  (70 → 100%) */
function getHeatmapColor(rate: number, isDark: boolean): { bg: string; text: string } {
  const clamped = Math.max(70, Math.min(100, rate))
  const t = (clamped - 70) / 30 // 0..1

  // Color stops: red(0) → amber(0.5) → emerald(1)
  let r: number, g: number, b: number
  if (t < 0.5) {
    const p = t / 0.5
    // red → amber
    r = Math.round(220 + (245 - 220) * p)
    g = Math.round(38 + (158 - 38) * p)
    b = Math.round(38 + (11 - 38) * p)
  } else {
    const p = (t - 0.5) / 0.5
    // amber → emerald
    r = Math.round(245 + (16 - 245) * p)
    g = Math.round(158 + (185 - 158) * p)
    b = Math.round(11 + (129 - 11) * p)
  }

  const alpha = isDark ? 0.35 : 0.25
  const bg = `rgba(${r},${g},${b},${alpha})`
  const text = isDark
    ? `rgb(${Math.min(r + 60, 255)},${Math.min(g + 60, 255)},${Math.min(b + 60, 255)})`
    : `rgb(${Math.max(r - 80, 0)},${Math.max(g - 80, 0)},${Math.max(b - 40, 0)})`
  return { bg, text }
}

/** Continuous heatmap color for QA score: red → amber → emerald (0 → 10) */
function getQAHeatmapColor(score: number, isDark: boolean): { bg: string; text: string } {
  const clamped = Math.max(0, Math.min(10, score))
  const t = clamped / 10 // 0..1

  let r: number, g: number, b: number
  if (t < 0.5) {
    const p = t / 0.5
    r = Math.round(220 + (245 - 220) * p)
    g = Math.round(38 + (158 - 38) * p)
    b = Math.round(38 + (11 - 38) * p)
  } else {
    const p = (t - 0.5) / 0.5
    r = Math.round(245 + (16 - 245) * p)
    g = Math.round(158 + (185 - 158) * p)
    b = Math.round(11 + (129 - 11) * p)
  }

  const alpha = isDark ? 0.35 : 0.25
  const bg = `rgba(${r},${g},${b},${alpha})`
  const text = isDark
    ? `rgb(${Math.min(r + 60, 255)},${Math.min(g + 60, 255)},${Math.min(b + 60, 255)})`
    : `rgb(${Math.max(r - 80, 0)},${Math.max(g - 80, 0)},${Math.max(b - 40, 0)})`
  return { bg, text }
}

export default function LeaderboardView({
  experiments,
  sectorMatrix,
  onSelectExperiment,
  totalTasks,
}: LeaderboardViewProps) {
  const [hoveredRow, setHoveredRow] = useState<string | null>(null)
  const [modelFilter, setModelFilter] = useState<string>('all')
  const [modeFilter, setModeFilter] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [hoveredCell, setHoveredCell] = useState<string | null>(null)
  const [heatmapMode, setHeatmapMode] = useState<'qa' | 'rate'>('qa')
  const { isDark } = useTheme()

  const effectiveTotalTasks = totalTasks ?? 220

  // Unique filter options
  const models = useMemo(
    () => [...new Set(experiments.map((e) => e.model))].sort(),
    [experiments]
  )
  const modes = useMemo(
    () => [...new Set(experiments.map((e) => e.execution_mode).filter(Boolean))].sort(),
    [experiments]
  )

  // Filtered (preserve parent sort order: date desc → duration desc)
  const filtered = useMemo(() => {
    let list = [...experiments]
    if (modelFilter !== 'all') list = list.filter((e) => e.model === modelFilter)
    if (modeFilter !== 'all') list = list.filter((e) => e.execution_mode === modeFilter)
    return list
  }, [experiments, modelFilter, modeFilter])

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE))
  const paginated = filtered.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  )

  // Best rate across all (not just filtered)
  const bestRate =
    experiments.length > 0
      ? Math.max(...experiments.map((e) => e.success_rate_pct))
      : 0

  // Sectors for heatmap
  const sectors = Object.keys(sectorMatrix).sort()

  // Reset page on filter change
  const handleFilter = (setter: (v: string) => void) => (v: string) => {
    setter(v)
    setCurrentPage(1)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* ── Section Hint ── */}
      <SectionHint tabId="leaderboard">{substituteTaskTotal(sectionHintTexts.leaderboard, effectiveTotalTasks)}</SectionHint>

      {/* ── Filter Bar ── */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={modelFilter}
          onChange={(e) => handleFilter(setModelFilter)(e.target.value)}
          className="bg-dash-card border border-dash-border rounded-lg px-3 py-1.5 text-xs text-dash-text focus:outline-none focus:border-dash-heading/30"
        >
          <option value="all">All Models</option>
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        <select
          value={modeFilter}
          onChange={(e) => handleFilter(setModeFilter)(e.target.value)}
          className="bg-dash-card border border-dash-border rounded-lg px-3 py-1.5 text-xs text-dash-text focus:outline-none focus:border-dash-heading/30"
        >
          <option value="all">All Modes</option>
          {modes.map((m) => (
            <option key={m} value={m}>
              {getModeBadge(m).icon} {m}
            </option>
          ))}
        </select>

        <span className="text-[10px] text-dash-text-muted ml-auto">
          {filtered.length} experiment{filtered.length !== 1 ? 's' : ''}
          {(modelFilter !== 'all' || modeFilter !== 'all') && (
            <button
              onClick={() => {
                setModelFilter('all')
                setModeFilter('all')
                setCurrentPage(1)
              }}
              className="ml-2 text-dash-text-muted hover:text-dash-heading underline transition"
            >
              Reset
            </button>
          )}
        </span>
      </div>

      {/* ── Ranking Table ── */}
      <div className="rounded-xl bg-dash-card border border-dash-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-dash-border">
                <th className="px-4 py-3 text-left text-dash-text-muted font-semibold">Rank</th>
                <th className="px-4 py-3 text-left text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1">Experiment <InfoTooltip content={substituteTaskTotal(tooltipTexts.leaderboard.experiment, effectiveTotalTasks)} position="bottom" /></span>
                </th>
                <th className="px-4 py-3 text-left text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1">Model <InfoTooltip content={tooltipTexts.leaderboard.model} position="bottom" /></span>
                </th>
                <th className="px-4 py-3 text-left text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1">Strategy <InfoTooltip content={tooltipTexts.leaderboard.strategy} position="bottom" /></span>
                </th>
                <th className="px-4 py-3 text-center text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1 justify-center">Progress <InfoTooltip content={substituteTaskTotal(tooltipTexts.leaderboard.progress, effectiveTotalTasks)} position="bottom" /></span>
                </th>
                <th className="px-4 py-3 text-right text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1 justify-end">Success Rate <InfoTooltip content={tooltipTexts.leaderboard.successRate} position="bottom" /></span>
                </th>
                <th className="px-4 py-3 text-right text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1 justify-end">Δ Best <InfoTooltip content={tooltipTexts.leaderboard.deltaBest} position="bottom" /></span>
                </th>
                <th className="px-4 py-3 text-right text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1 justify-end">QA Score <InfoTooltip content={tooltipTexts.leaderboard.qaScore} position="bottom" /></span>
                </th>
                <th className="px-4 py-3 text-right text-dash-text-muted font-semibold">
                  <span className="inline-flex items-center gap-1 justify-end">Tasks <InfoTooltip content={tooltipTexts.leaderboard.tasks} position="bottom" /></span>
                </th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((exp, idx) => {
                const globalRank = (currentPage - 1) * ITEMS_PER_PAGE + idx + 1
                const badge = getModeBadge(exp.execution_mode)
                return (
                  <tr
                    key={exp.short_id}
                    onMouseEnter={() => setHoveredRow(exp.short_id)}
                    onMouseLeave={() => setHoveredRow(null)}
                    onClick={() => onSelectExperiment(exp.short_id)}
                    className={`border-b border-dash-border-subtle cursor-pointer transition-colors ${
                      hoveredRow === exp.short_id ? 'bg-dash-card-hover' : ''
                    }`}
                  >
                    <td className="px-4 py-3 text-dash-text-secondary font-mono">{globalRank}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: getExpColor(exp.short_id) }}
                        />
                        <span className="text-dash-text font-medium" title={exp.experiment_name || exp.short_id}>{exp.short_id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-block bg-dash-card-hover border border-dash-border rounded px-2 py-0.5 font-mono text-dash-text-secondary">
                        {exp.model}
                      </span>
                      <span
                        className="ml-1.5 inline-block text-[9px] px-1.5 py-0.5 rounded bg-dash-card-hover text-dash-text-muted"
                        title={exp.execution_mode}
                      >
                        {badge.icon} {badge.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-dash-text-muted capitalize">
                      {exp.condition || 'baseline'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="w-full max-w-xs bg-dash-card-hover rounded-full h-2.5">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${exp.success_rate_pct}%`,
                            backgroundColor: getExpColor(exp.short_id),
                            opacity: 0.75,
                          }}
                        />
                      </div>
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-mono font-semibold ${getRateColor(exp.success_rate_pct)}`}
                    >
                      {exp.success_rate_pct.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-dash-text-secondary">
                      {(bestRate - exp.success_rate_pct).toFixed(1)}%
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-mono font-semibold ${getQAColor(exp.avg_qa_score)}`}
                    >
                      {exp.avg_qa_score.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right text-dash-text-secondary font-mono">
                      {exp.success_count}/{exp.total_tasks}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* ── Pagination ── */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-dash-border">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="flex items-center gap-1 text-xs text-dash-text-secondary hover:text-dash-heading disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ChevronLeft className="h-3 w-3" /> Prev
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  className={`w-7 h-7 rounded text-xs font-mono transition ${
                    page === currentPage
                      ? 'bg-dash-card-active text-dash-heading'
                      : 'text-dash-text-muted hover:text-dash-heading hover:bg-dash-card-hover'
                  }`}
                >
                  {page}
                </button>
              ))}
            </div>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="flex items-center gap-1 text-xs text-dash-text-secondary hover:text-dash-heading disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              Next <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>

      {/* ── Sector Heatmap Table ── */}
      <div className="rounded-xl bg-dash-card border border-dash-border overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-dash-border flex items-center justify-between">
          <div className="flex items-center gap-1 rounded-lg bg-dash-card-hover p-0.5">
            <button
              onClick={() => setHeatmapMode('qa')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                heatmapMode === 'qa'
                  ? 'bg-amber-500/15 text-amber-300 shadow-sm'
                  : 'text-dash-text-muted hover:text-dash-text-secondary'
              }`}
            >
              Self-QA Score
            </button>
            <button
              onClick={() => setHeatmapMode('rate')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                heatmapMode === 'rate'
                  ? 'bg-emerald-500/15 text-emerald-300 shadow-sm'
                  : 'text-dash-text-muted hover:text-dash-text-secondary'
              }`}
            >
              Success Rate
            </button>
          </div>
          {/* Legend */}
          <div className="flex items-center gap-2 text-[10px] text-dash-text-muted">
            <span>Low</span>
            <div
              className="h-2.5 w-24 rounded-full overflow-hidden"
              style={{
                background: isDark
                  ? 'linear-gradient(to right, rgba(220,38,38,0.5), rgba(245,158,11,0.5), rgba(16,185,129,0.5))'
                  : 'linear-gradient(to right, rgba(220,38,38,0.35), rgba(245,158,11,0.35), rgba(16,185,129,0.35))',
              }}
            />
            <span>High</span>
            <span className="ml-1">({heatmapMode === 'qa' ? '0–10' : '0–100%'})</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table
            className="w-full text-xs border-separate"
            style={{
              minWidth: `${240 + filtered.length * 120}px`,
              borderSpacing: '2px 2px',
            }}
          >
            <thead>
              <tr>
                <th className="text-left text-dash-text-muted px-4 py-2.5 font-semibold sticky left-0 bg-dash-sticky z-10 min-w-[200px] rounded-tl-lg">
                  Sector
                </th>
                {filtered.map((e) => {
                  const badge = getModeBadge(e.execution_mode)
                  return (
                    <th
                      key={e.short_id}
                      className="text-center px-3 py-2.5 min-w-[110px]"
                      title={e.experiment_name || e.short_id}
                    >
                      <div
                        style={{ color: getExpColor(e.short_id) }}
                        className="font-semibold text-[11px]"
                      >
                        {e.short_id}
                      </div>
                      <div className="text-[9px] text-dash-text-faint font-mono mt-0.5">
                        {e.model}
                      </div>
                      <div className="text-[8px] text-dash-text-faint">
                        {badge.icon} {badge.label}
                      </div>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {sectors.map((sector, sIdx) => (
                <tr key={sector}>
                  <td
                    className={`text-dash-text-secondary px-4 py-2.5 text-[11px] font-medium sticky left-0 bg-dash-sticky z-10 ${
                      sIdx === sectors.length - 1 ? 'rounded-bl-lg' : ''
                    }`}
                  >
                    {sector}
                  </td>
                  {filtered.map((exp) => {
                    const cellData = sectorMatrix[sector]?.[exp.short_id]
                    const value = heatmapMode === 'qa'
                      ? (cellData?.avg_qa_score ?? 0)
                      : (cellData?.success_rate_pct ?? 0)
                    const { bg, text } = heatmapMode === 'qa'
                      ? getQAHeatmapColor(value, isDark)
                      : getHeatmapColor(value, isDark)
                    const displayValue = heatmapMode === 'qa'
                      ? value.toFixed(1)
                      : (value % 1 === 0 ? `${value}%` : `${value.toFixed(1)}%`)
                    const cellKey = `${sector}-${exp.short_id}`
                    const isHovered = hoveredCell === cellKey
                    return (
                      <td
                        key={exp.short_id}
                        className="text-center px-3 py-3 font-mono text-[11px] font-semibold rounded-md transition-all duration-150 cursor-default"
                        style={{
                          backgroundColor: bg,
                          color: text,
                          transform: isHovered ? 'scale(1.05)' : 'scale(1)',
                          boxShadow: isHovered
                            ? `0 0 12px ${bg}, 0 2px 8px rgba(0,0,0,0.15)`
                            : 'none',
                          zIndex: isHovered ? 5 : 'auto',
                          position: 'relative',
                        }}
                        onMouseEnter={() => setHoveredCell(cellKey)}
                        onMouseLeave={() => setHoveredCell(null)}
                      >
                        {displayValue}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  )
}
