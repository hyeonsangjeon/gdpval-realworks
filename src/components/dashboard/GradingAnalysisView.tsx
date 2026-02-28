import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Award, Target, XCircle, BarChart3, AlertCircle, AlertTriangle, ExternalLink, Clock,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { useGrades, GradeResult } from '../../hooks/useGrades'
import { useTheme } from '../../contexts/ThemeContext'

/* ─── palette ─── */
const SCORE_COLORS = {
  perfect: '#10b981',
  partial: '#f59e0b',
  zero: '#ef4444',
  error: '#f97316',
  inconsistent: '#8b5cf6',
}

const GRADE_EXP_COLORS = [
  '#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
]

/* ─── component ─── */
export default function GradingAnalysisView() {
  const navigate = useNavigate()
  const { isDark } = useTheme()
  const { grades, loading, error } = useGrades()

  const chartTooltip = {
    contentStyle: {
      background: isDark ? '#1a1a2e' : '#ffffff',
      border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid #e5e7eb',
      borderRadius: 8, fontSize: 12, color: isDark ? '#e5e7eb' : '#374151',
    },
  }
  const gridStroke = isDark ? 'rgba(255,255,255,0.06)' : '#e5e7eb'
  const tickStyle = { fill: isDark ? '#666' : '#9ca3af', fontSize: 11 }

  /* ─── derived: cross-experiment distribution bar chart ─── */
  const distributionData = useMemo(() => {
    return grades.map((g, i) => ({
      name: g.label.length > 22 ? g.label.slice(0, 20) + '…' : g.label,
      fullLabel: g.label,
      perfect: g.summary.perfect_score,
      partial: g.summary.partial_score,
      zero: g.summary.zero_score,
      error: g.summary.error_tasks,
      color: GRADE_EXP_COLORS[i % GRADE_EXP_COLORS.length],
    }))
  }, [grades])

  /* ─── derived: aggregate pie ─── */
  const aggregatePie = useMemo(() => {
    const agg = { perfect: 0, partial: 0, zero: 0, error: 0 }
    for (const g of grades) {
      agg.perfect += g.summary.perfect_score
      agg.partial += g.summary.partial_score
      agg.zero += g.summary.zero_score
      agg.error += g.summary.error_tasks
    }
    return [
      { name: 'Perfect (100%)', value: agg.perfect, color: SCORE_COLORS.perfect },
      { name: 'Partial', value: agg.partial, color: SCORE_COLORS.partial },
      { name: 'Zero (0%)', value: agg.zero, color: SCORE_COLORS.zero },
      { name: 'Errors', value: agg.error, color: SCORE_COLORS.error },
    ].filter((d) => d.value > 0)
  }, [grades])

  /* ─── derived: disagreement comparison ─── */
  const disagreementData = useMemo(() => {
    return grades.map((g, i) => ({
      name: g.label.length > 18 ? g.label.slice(0, 16) + '…' : g.label,
      inconsistent: g.summary.inconsistent_grades,
      total: g.summary.graded_tasks,
      rate: g.summary.graded_tasks > 0
        ? +((g.summary.inconsistent_grades / g.summary.graded_tasks) * 100).toFixed(1)
        : 0,
      color: GRADE_EXP_COLORS[i % GRADE_EXP_COLORS.length],
    }))
  }, [grades])

  /* ─── loading / error states ─── */
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="inline-block w-6 h-6 border-2 border-dash-text-faint border-t-dash-heading rounded-full animate-spin mb-3" />
          <p className="text-sm text-dash-text-muted">Loading grading data…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl bg-dash-card border border-red-500/30 p-8 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
        <p className="text-sm text-red-400">{error}</p>
      </div>
    )
  }

  if (grades.length === 0) {
    return (
      <div className="rounded-xl bg-dash-card border border-dash-border p-10 text-center">
        <Award className="w-10 h-10 text-dash-text-faint mx-auto mb-4" />
        <h3 className="text-base font-semibold text-dash-text mb-2">No Grading Data Yet</h3>
        <p className="text-sm text-dash-text-muted max-w-md mx-auto">
          Grading results will appear here after the external evaluation pipeline completes.
          This is separate from the self-assessed QA scores shown in other tabs.
        </p>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* ─── Dummy data banner ─── */}
      {grades.some((g) => g.is_dummy) && (
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4"
        >
          <div className="flex items-start gap-3">
            <Clock className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-amber-300 mb-1">Grading In Progress</h3>
              <p className="text-xs text-amber-300/80">
                Some entries are placeholder data while we wait for the external grading pipeline to finish.
                Results marked as dummy will be replaced with real scores.
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* ─── 0. Summary Cards per experiment ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {grades.map((g, i) => (
          <GradeOverviewCard key={g.id} grade={g} color={GRADE_EXP_COLORS[i % GRADE_EXP_COLORS.length]} onNavigate={() => navigate(`/grades/${g.id}`)} />
        ))}
      </div>

      {/* ─── 1. Score Distribution (stacked bar — cross-experiment) ─── */}
      {distributionData.length > 1 && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-4">Score Distribution Comparison</h3>
          <ResponsiveContainer width="100%" height={Math.max(180, distributionData.length * 50)}>
            <BarChart data={distributionData} layout="vertical" margin={{ top: 5, right: 30, left: 140, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis type="number" tick={tickStyle} allowDecimals={false} />
              <YAxis dataKey="name" type="category" tick={tickStyle} width={130} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="perfect" stackId="a" fill={SCORE_COLORS.perfect} name="Perfect (100%)" />
              <Bar dataKey="partial" stackId="a" fill={SCORE_COLORS.partial} name="Partial" />
              <Bar dataKey="zero" stackId="a" fill={SCORE_COLORS.zero} name="Zero (0%)" />
              <Bar dataKey="error" stackId="a" fill={SCORE_COLORS.error} name="Error" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ─── 2. Aggregate Pie ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-4">Overall Score Breakdown</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={aggregatePie}
                cx="50%" cy="50%"
                innerRadius={55} outerRadius={90}
                paddingAngle={3}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {aggregatePie.map((d, i) => (
                  <Cell key={i} fill={d.color} />
                ))}
              </Pie>
              <Tooltip {...chartTooltip} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* ─── 3. Grader Disagreement ─── */}
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <div className="flex items-center gap-2 mb-4">
            <AlertCircle className="w-4 h-4 text-purple-400" />
            <h3 className="text-sm font-semibold text-dash-text">Grader Disagreement</h3>
          </div>
          {disagreementData.length > 0 ? (
            <div className="space-y-4">
              {disagreementData.map((d, i) => (
                <div key={i}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-dash-text-secondary">{d.name}</span>
                    <span className="font-mono font-semibold text-purple-400">{d.inconsistent} / {d.total} ({d.rate}%)</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-dash-card-hover overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(d.rate, 100)}%` }}
                      transition={{ duration: 0.8, delay: i * 0.1 }}
                      className="h-full rounded-full"
                      style={{ backgroundColor: d.color + 'aa' }}
                    />
                  </div>
                </div>
              ))}
              <p className="text-[10px] text-dash-text-faint leading-relaxed mt-2">
                Disagreement = multiple graders scored the same task differently.
                High rates may indicate ambiguous rubric criteria or borderline outputs.
              </p>
            </div>
          ) : (
            <p className="text-xs text-dash-text-muted italic">No disagreement data available.</p>
          )}
        </div>
      </div>

      {/* ─── 4. Error Tasks in Grading ─── */}
      {grades.some((g) => g.summary.error_tasks > 0) && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-4">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-orange-400" />
            <h3 className="text-sm font-semibold text-dash-text">Grading Errors</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {grades.map((g, i) => {
              const errorTasks = g.tasks.filter((t) => t.error)
              if (errorTasks.length === 0) return null
              return (
                <div key={g.id} className="space-y-2">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: GRADE_EXP_COLORS[i % GRADE_EXP_COLORS.length] }} />
                    <span className="text-xs font-semibold text-dash-text">{g.label}</span>
                    <span className="text-[10px] text-red-400 font-mono ml-auto">{errorTasks.length} errors</span>
                  </div>
                  <div className="max-h-[160px] overflow-y-auto space-y-1.5">
                    {errorTasks.slice(0, 10).map((t) => (
                      <div key={t.task_id} className="text-[11px] rounded-lg bg-red-500/[0.06] border border-red-500/10 px-2.5 py-1.5">
                        <span className="font-mono text-dash-text-secondary">{t.task_id}</span>
                        {t.error_messages.length > 0 && (
                          <p className="text-red-400/80 text-[10px] mt-0.5 truncate">{t.error_messages[0]}</p>
                        )}
                      </div>
                    ))}
                    {errorTasks.length > 10 && (
                      <p className="text-[10px] text-dash-text-faint text-center">
                        +{errorTasks.length - 10} more
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ─── 5. Quick links to detail pages ─── */}
      <div className="rounded-xl bg-dash-card border border-dash-border p-4">
        <h3 className="text-sm font-semibold text-dash-text mb-3">Detailed Grade Reports</h3>
        <div className="flex flex-wrap gap-2">
          {grades.map((g, i) => (
            <button
              key={g.id}
              onClick={() => navigate(`/grades/${g.id}`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-all text-xs"
            >
              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: GRADE_EXP_COLORS[i % GRADE_EXP_COLORS.length] }} />
              {g.label}
              {g.is_dummy && <span className="text-[9px] text-amber-400 ml-0.5">(dummy)</span>}
              <ExternalLink className="w-3 h-3 ml-1" />
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

/* ─── GradeOverviewCard ─── */
function GradeOverviewCard({ grade, color, onNavigate }: { grade: GradeResult; color: string; onNavigate: () => void }) {
  const s = grade.summary
  const stats = [
    { icon: Target, label: 'Graded', value: `${s.graded_tasks}/${s.total_tasks}`, color: 'text-blue-400 bg-blue-500/10' },
    { icon: Award, label: 'Perfect', value: s.perfect_score, color: 'text-emerald-400 bg-emerald-500/10' },
    { icon: BarChart3, label: 'Partial', value: s.partial_score, color: 'text-amber-400 bg-amber-500/10' },
    { icon: XCircle, label: 'Zero', value: s.zero_score, color: 'text-red-400 bg-red-500/10' },
    { icon: AlertCircle, label: 'Disagree', value: s.inconsistent_grades, color: 'text-purple-400 bg-purple-500/10' },
    { icon: AlertTriangle, label: 'Error', value: s.error_tasks, color: 'text-orange-400 bg-orange-500/10' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl bg-dash-card border border-dash-border p-4 hover:border-dash-border-active transition-all cursor-pointer relative overflow-hidden"
      onClick={onNavigate}
    >
      {grade.is_dummy && (
        <div className="absolute top-0 left-0 right-0 bg-amber-500/80 text-amber-950 text-center text-[9px] font-bold py-0.5 tracking-wider uppercase">
          ⏳ Awaiting real grading
        </div>
      )}
      <div className={grade.is_dummy ? 'pt-3' : ''}>
        {/* header */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              <h4 className="text-sm font-semibold text-dash-text">{grade.label}</h4>
            </div>
            <p className="text-[10px] text-dash-text-faint font-mono">{grade.model}</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-dash-heading font-mono">{s.avg_score_pct}%</p>
            {s.ci_pct && <p className="text-[10px] text-dash-text-faint">± {s.ci_pct}% CI</p>}
          </div>
        </div>

        {/* Score bar */}
        <div className="mb-3">
          <div className="flex h-2.5 w-full rounded-full overflow-hidden bg-dash-card-hover">
            {s.perfect_score > 0 && (
              <motion.div initial={{ width: 0 }} animate={{ width: `${(s.perfect_score / s.total_tasks) * 100}%` }}
                transition={{ duration: 0.8 }} className="h-full bg-emerald-500" />
            )}
            {s.partial_score > 0 && (
              <motion.div initial={{ width: 0 }} animate={{ width: `${(s.partial_score / s.total_tasks) * 100}%` }}
                transition={{ duration: 0.8, delay: 0.1 }} className="h-full bg-amber-500" />
            )}
            {s.zero_score > 0 && (
              <motion.div initial={{ width: 0 }} animate={{ width: `${(s.zero_score / s.total_tasks) * 100}%` }}
                transition={{ duration: 0.8, delay: 0.2 }} className="h-full bg-red-500" />
            )}
          </div>
          <div className="flex justify-between text-[9px] text-dash-text-faint mt-1">
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-sm bg-emerald-500 inline-block" /> Perfect {s.perfect_score}</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-sm bg-amber-500 inline-block" /> Partial {s.partial_score}</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-sm bg-red-500 inline-block" /> Zero {s.zero_score}</span>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-2">
          {stats.map(({ icon: Icon, label, value, color: clr }) => (
            <div key={label} className="flex items-center gap-1.5">
              <div className={`rounded p-1 ${clr}`}><Icon className="w-2.5 h-2.5" /></div>
              <div>
                <div className="text-[9px] text-dash-text-faint leading-none">{label}</div>
                <div className="text-[11px] font-semibold text-dash-text font-mono">{value}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
