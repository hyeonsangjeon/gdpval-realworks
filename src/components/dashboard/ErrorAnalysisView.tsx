import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { AlertCircle, Brain, FileWarning, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import type { ExperimentEntry, ReportData } from '../../types/report'
import { useTheme } from '../../contexts/ThemeContext'
import { useIsMobile } from '../../hooks/useIsMobile'
import { parseTraceback } from '../../utils/tracebackParser'

/* ─── props ─── */
interface ErrorAnalysisViewProps {
  experiments: ExperimentEntry[]
  reports: ReportData[]
}

/* ─── constants ─── */
const EXP_COLORS: Record<string, string> = {
  exp003: '#3b82f6', exp004: '#f59e0b', exp005: '#ef4444',
  exp006: '#10b981', exp007: '#8b5cf6', exp008: '#ec4899',
  exp009: '#14b8a6', exp010: '#f97316',
}

function expColor(id: string) { return EXP_COLORS[id] || '#999' }

/* ─── COMPONENT ─── */
export default function ErrorAnalysisView({ experiments, reports }: ErrorAnalysisViewProps) {
  const { isDark } = useTheme()
  const isMobile = useIsMobile()
  const [expandedError, setExpandedError] = useState<string | null>(null)

  const chartTooltip = {
    contentStyle: {
      background: isDark ? '#1a1a2e' : '#ffffff',
      border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid #e5e7eb',
      borderRadius: 8, fontSize: 12, color: isDark ? '#e5e7eb' : '#374151',
    },
  }
  const gridStroke = isDark ? 'rgba(255,255,255,0.06)' : '#e5e7eb'
  const tickStyle = { fill: isDark ? '#666' : '#9ca3af', fontSize: 11 }

  const sortedExps = useMemo(
    () => [...experiments].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()),
    [experiments],
  )

  /* ─── derived: exception type chart data (cross-experiment stacked bar) ─── */
  const exceptionChartData = useMemo(() => {
    const allTypes = new Set<string>()
    const perExp: Record<string, Record<string, number>> = {}
    for (const r of reports) {
      perExp[r.short_id] = {}
      for (const et of (r.error_tasks || [])) {
        const { type } = parseTraceback(et.error)
        perExp[r.short_id][type] = (perExp[r.short_id][type] || 0) + 1
        allTypes.add(type)
      }
    }
    return Array.from(allTypes)
      .map((type) => {
        const row: Record<string, string | number> = { name: type }
        for (const exp of sortedExps) row[exp.short_id] = perExp[exp.short_id]?.[type] || 0
        return row
      })
      .sort((a, b) => {
        const sumA = sortedExps.reduce((s, e) => s + ((a[e.short_id] as number) || 0), 0)
        const sumB = sortedExps.reduce((s, e) => s + ((b[e.short_id] as number) || 0), 0)
        return sumB - sumA
      })
  }, [reports, sortedExps])

  /* ─── derived: sector error map ─── */
  const sectorErrors = useMemo(() => {
    const map: Record<string, Record<string, number>> = {}
    for (const r of reports) {
      for (const et of (r.error_tasks || [])) {
        if (!map[et.sector]) map[et.sector] = {}
        map[et.sector][r.short_id] = (map[et.sector][r.short_id] || 0) + 1
      }
    }
    return Object.entries(map)
      .map(([sector, counts]) => ({
        sector,
        total: Object.values(counts).reduce((a, b) => a + b, 0),
        ...counts,
      }))
      .sort((a, b) => b.total - a.total)
  }, [reports])

  /* ─── derived: all error tasks with parsed type ─── */
  const allErrorTasks = useMemo(() => {
    const tasks: { expId: string; taskId: string; sector: string; occupation: string; exceptionType: string; error: string }[] = []
    for (const r of reports) {
      for (const et of (r.error_tasks || [])) {
        const { type } = parseTraceback(et.error)
        tasks.push({ expId: r.short_id, taskId: et.task_id, sector: et.sector, occupation: et.occupation, exceptionType: type, error: et.error })
      }
    }
    return tasks
  }, [reports])

  const hasErrors = reports.some((r) => (r.error_tasks?.length || 0) > 0)
  const hasNarrative = reports.some((r) => r.narrative && typeof r.narrative === 'object' && r.narrative.failure_patterns)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* ─── 0. Summary Stats ─── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {sortedExps.map((exp) => {
          const r = reports.find((rr) => rr.short_id === exp.short_id)
          const errCount = r?.error_tasks?.length || r?.summary?.error_count || 0
          const retriedCount = r?.summary?.retried_count || 0
          const round1 = r?.recovery_stats?.resume_rounds?.per_round?.['1']
          const recoveredPct = round1 ? Math.round((round1.recovered / round1.attempted) * 100) : null
          return (
            <motion.div key={exp.short_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              className="rounded-xl bg-dash-card border border-dash-border p-3"
            >
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: expColor(exp.short_id) }} />
                <span className="text-[11px] font-semibold text-dash-text">{exp.short_id}</span>
                <span className="text-[9px] text-dash-text-faint font-mono ml-auto">{exp.model}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-lg font-bold font-mono text-red-400">{errCount}</div>
                  <div className="text-[9px] text-dash-text-muted">Errors</div>
                </div>
                <div>
                  <div className="text-lg font-bold font-mono text-amber-400">{retriedCount}</div>
                  <div className="text-[9px] text-dash-text-muted">Retried</div>
                </div>
                <div>
                  <div className="text-lg font-bold font-mono text-emerald-400">
                    {recoveredPct !== null ? `${recoveredPct}%` : '—'}
                  </div>
                  <div className="text-[9px] text-dash-text-muted">Recovered</div>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* ─── 1. AI Insights ─── */}
      {hasNarrative && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-dash-text">AI Failure Insights</h3>
          </div>
          <div className="space-y-4">
            {reports.map((r) => {
              const n = r.narrative
              if (!n || typeof n !== 'object') return null
              return (
                <div key={r.short_id} className="text-xs space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: expColor(r.short_id) }} />
                    <span className="font-semibold text-dash-text">{r.short_id}</span>
                  </div>
                  {n.failure_patterns && (
                    <div className="pl-4">
                      <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">Failure Patterns</div>
                      <p className="text-dash-text-secondary leading-relaxed">{n.failure_patterns}</p>
                    </div>
                  )}
                  {n.recommendations && (
                    <div className="pl-4">
                      <div className="text-[10px] text-dash-text-muted uppercase mb-0.5">💡 Recommendations</div>
                      <p className="text-dash-text-secondary leading-relaxed whitespace-pre-line">{n.recommendations}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ─── 2. Exception Type Distribution ─── */}
      {hasErrors && exceptionChartData.length > 0 && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-3 md:p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-4">Exception Type Distribution</h3>
          <ResponsiveContainer width="100%" height={Math.max(200, exceptionChartData.length * 36)}>
            <BarChart data={exceptionChartData} layout="vertical" margin={{ top: 5, right: isMobile ? 10 : 30, left: isMobile ? 5 : 120, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis type="number" tick={tickStyle} allowDecimals={false} />
              <YAxis dataKey="name" type="category" tick={{ ...tickStyle, fontSize: isMobile ? 9 : 11 }} width={isMobile ? 80 : 110} />
              <Tooltip {...chartTooltip} />
              {sortedExps.map((exp) => (
                <Bar key={exp.short_id} dataKey={exp.short_id} stackId="a" fill={expColor(exp.short_id)} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── 3. Sector Error Map ─── */}
      {sectorErrors.length > 0 && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-3 md:p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-4">Errors by Sector</h3>
          <ResponsiveContainer width="100%" height={Math.max(180, sectorErrors.length * (isMobile ? 44 : 36))}>
            <BarChart data={sectorErrors} layout="vertical" margin={{ top: 5, right: isMobile ? 10 : 30, left: isMobile ? 5 : 160, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis type="number" tick={tickStyle} allowDecimals={false} />
              <YAxis dataKey="sector" type="category" tick={{ ...tickStyle, fontSize: isMobile ? 9 : 11 }} width={isMobile ? 100 : 150} />
              <Tooltip {...chartTooltip} />
              {sortedExps.map((exp) => (
                <Bar key={exp.short_id} dataKey={exp.short_id} stackId="a" fill={expColor(exp.short_id)} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── 4. Recovery Funnels (real data) ─── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {sortedExps.map((exp) => {
          const r = reports.find((rr) => rr.short_id === exp.short_id)
          const round1 = r?.recovery_stats?.resume_rounds?.per_round?.['1']
          if (!round1) {
            return (
              <motion.div key={exp.short_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className="rounded-xl bg-dash-card border border-dash-border p-4"
              >
                <ExpBadge id={exp.short_id} />
                <h4 className="text-xs font-semibold text-dash-text mb-3">Recovery Funnel</h4>
                <p className="text-[11px] text-dash-text-muted italic">No recovery data available</p>
              </motion.div>
            )
          }
          const { attempted, recovered, still_failed } = round1
          const recoveredPct = attempted > 0 ? ((recovered / attempted) * 100).toFixed(1) : '0'
          const failedPct = attempted > 0 ? ((still_failed / attempted) * 100).toFixed(1) : '0'
          return (
            <motion.div key={exp.short_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="rounded-xl bg-dash-card border border-dash-border p-4"
            >
              <ExpBadge id={exp.short_id} />
              <h4 className="text-xs font-semibold text-dash-text mb-3">Recovery Funnel</h4>
              <div className="space-y-2.5 text-xs">
                <FunnelRow label="Attempted (Retry)" value={attempted} color="text-amber-400" />
                <div className="w-full h-1.5 rounded-full bg-dash-card-hover overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${recoveredPct}%`, backgroundColor: expColor(exp.short_id) }} />
                </div>
                <FunnelRow label="Recovered" value={`${recovered} (${recoveredPct}%)`} color="text-emerald-400" />
                <div className="w-full h-1.5 rounded-full bg-dash-card-hover overflow-hidden">
                  <div className="h-full rounded-full bg-red-500/50 transition-all duration-500" style={{ width: `${failedPct}%` }} />
                </div>
                <FunnelRow label="Still Failed" value={`${still_failed} (${failedPct}%)`} color="text-red-400" />
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* ─── 5. File Generation Risk ─── */}
      {reports.some((r) => r.file_generation) && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <div className="flex items-center gap-2 mb-4">
            <FileWarning className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-dash-text">File Generation Risk</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {sortedExps.map((exp) => {
              const r = reports.find((rr) => rr.short_id === exp.short_id)
              const fg = r?.file_generation
              if (!fg) return null
              const failRate = fg.needs_files_total > 0
                ? ((fg.files_failed / fg.needs_files_total) * 100).toFixed(1)
                : '0'
              return (
                <div key={exp.short_id} className="space-y-2">
                  <ExpBadge id={exp.short_id} />
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <div className="text-[10px] text-dash-text-muted">Needed</div>
                      <div className="font-mono font-semibold text-dash-text">{fg.needs_files_total}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-dash-text-muted">Succeeded</div>
                      <div className="font-mono font-semibold text-emerald-400">{fg.files_succeeded}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-dash-text-muted">Failed</div>
                      <div className="font-mono font-semibold text-red-400">{fg.files_failed}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-dash-text-muted">Dummy Created</div>
                      <div className="font-mono font-semibold text-amber-400">{fg.dummy_files_created}</div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span className="text-dash-text-muted">Failure Rate</span>
                      <span className="font-mono font-semibold text-red-400">{failRate}%</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-dash-card-hover overflow-hidden">
                      <div className="h-full rounded-full bg-red-500/60 transition-all duration-500" style={{ width: `${failRate}%` }} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ─── 6. Error Tasks Detail Table ─── */}
      {allErrorTasks.length > 0 && (
        <div className="rounded-xl bg-dash-card border border-dash-border overflow-hidden">
          <div className="p-4 border-b border-dash-border">
            <h3 className="text-sm font-semibold text-dash-text">
              Error Tasks Detail
              <span className="text-[10px] text-dash-text-muted bg-dash-card-hover px-2 py-0.5 rounded-full ml-2">
                {allErrorTasks.length} tasks
              </span>
            </h3>
          </div>
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-dash-sticky z-10">
                <tr className="text-[10px] text-dash-text-muted uppercase tracking-wider border-b border-dash-border">
                  <th className="px-4 py-2 text-left">Exp</th>
                  <th className="px-3 py-2 text-left">Task ID</th>
                  <th className="px-3 py-2 text-left">Sector</th>
                  <th className="px-3 py-2 text-left">Occupation</th>
                  <th className="px-3 py-2 text-left">Exception</th>
                  <th className="px-3 py-2 text-center w-8"></th>
                </tr>
              </thead>
              <tbody>
                {allErrorTasks.map((t) => {
                  const isExpanded = expandedError === `${t.expId}-${t.taskId}`
                  return (
                    <>
                      <tr key={`row-${t.expId}-${t.taskId}`}
                        className="border-b border-dash-border-subtle hover:bg-dash-card-hover cursor-pointer"
                        onClick={() => setExpandedError(isExpanded ? null : `${t.expId}-${t.taskId}`)}
                      >
                        <td className="px-4 py-2">
                          <span className="font-semibold" style={{ color: expColor(t.expId) }}>{t.expId}</span>
                        </td>
                        <td className="px-3 py-2 font-mono text-dash-text-secondary text-[10px]">{t.taskId}</td>
                        <td className="px-3 py-2 text-dash-text-secondary max-w-[140px] truncate">{t.sector}</td>
                        <td className="px-3 py-2 text-dash-text max-w-[140px] truncate">{t.occupation}</td>
                        <td className="px-3 py-2">
                          <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-red-500/15 text-red-400">
                            {t.exceptionType}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center text-dash-text-muted">
                          {isExpanded ? <ChevronUp className="w-3 h-3 mx-auto" /> : <ChevronDown className="w-3 h-3 mx-auto" />}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`detail-${t.expId}-${t.taskId}`}>
                          <td colSpan={6} className="bg-red-500/[0.04] px-5 py-3">
                            <div className="text-[10px] text-red-400 uppercase font-semibold mb-1.5 flex items-center gap-1.5">
                              <AlertCircle className="w-3 h-3" /> Traceback
                            </div>
                            <pre className="text-[11px] text-dash-text-secondary font-mono whitespace-pre-wrap break-all leading-relaxed max-h-[200px] overflow-y-auto">
                              {t.error}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Empty state ─── */}
      {!hasErrors && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-8 text-center">
          <RefreshCw className="w-8 h-8 text-dash-text-faint mx-auto mb-3" />
          <p className="text-sm text-dash-text-muted">No error data available for the selected experiments.</p>
        </div>
      )}
    </motion.div>
  )
}

/* ─── small helpers ─── */
function ExpBadge({ id }: { id: string }) {
  return (
    <div className="mb-3">
      <div className="inline-block px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider"
        style={{ backgroundColor: expColor(id) + '20', color: expColor(id) }}
      >
        {id}
      </div>
    </div>
  )
}

function FunnelRow({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-dash-text-muted">{label}</span>
      <span className={`font-mono font-semibold ${color}`}>{value}</span>
    </div>
  )
}
