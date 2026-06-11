import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Award, Target, XCircle, BarChart3, AlertCircle, AlertTriangle, ExternalLink, BookOpen, Info,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { useGrades, GradeResult } from '../../hooks/useGrades'
import { useTheme } from '../../contexts/ThemeContext'
import { useIsMobile } from '../../hooks/useIsMobile'
import InfoTooltip from '../common/InfoTooltip'
import SectionHint from '../common/SectionHint'
import { tooltipTexts, sectionHintTexts } from '../../data/tooltipTexts'
import { fmtPct } from '../../lib/format'
import { isHiddenGrade, isOfficialGrade } from '../../lib/officialFilter'

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
export default function GradingAnalysisView({ debug = false }: { debug?: boolean }) {
  const navigate = useNavigate()
  const { isDark } = useTheme()
  const isMobile = useIsMobile()
  const { grades: allGrades, loading, error } = useGrades()

  // Phase 1: hide legacy demo + smoke grade cards from the default view.
  // `?debug=1` (passed from Dashboard) restores them. Display filter only —
  // the grades-index JSON is untouched. exp003 grades never match.
  const grades = useMemo(
    () => (debug ? allGrades : allGrades.filter((g) => !isHiddenGrade(g))),
    [allGrades, debug],
  )

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

  /* ─── derived: status counts (002 D2) ─── */
  const statusCounts = useMemo(() => ({
    graded_v1: grades.filter((g) => g.grade_status === 'graded_v1').length,
    legacy_dummy: grades.filter((g) => g.grade_status === 'legacy_dummy').length,
  }), [grades])

  type BannerKind = 'none' | 'legacy_only' | 'mixed'
  const bannerKind: BannerKind =
    statusCounts.legacy_dummy === 0 ? 'none'
    : statusCounts.graded_v1 === 0  ? 'legacy_only'
    :                                 'mixed'

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
  const hasDisagreement = disagreementData.some((d) => d.inconsistent > 0)

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
          Grading results will appear here after running the LLM-judge via <code className="text-dash-text-secondary">grade-run.yml</code>.
          This is separate from the self-assessed QA scores shown in other tabs.
        </p>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* ─── Status-aware banner (002 D2) ─── */}
      {bannerKind === 'legacy_only' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
          className="rounded-xl border border-zinc-500/20 bg-zinc-500/10 p-4"
        >
          <div className="flex items-start gap-3">
            <BookOpen className="w-5 h-5 text-zinc-300 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-zinc-300 mb-1">Legacy demo grades</h3>
              <p className="text-xs text-zinc-300/80">
                Showing legacy demo grades. Run <code className="text-zinc-200">grade-run.yml</code> to get real LLM-judge scores.
              </p>
            </div>
          </div>
        </motion.div>
      )}
      {bannerKind === 'mixed' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
          className="rounded-xl border border-sky-500/20 bg-sky-500/10 p-4"
        >
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-sky-300 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-sky-300 mb-1">Mixed grade sources</h3>
              <p className="text-xs text-sky-300/80">
                Some experiments still show legacy demo grades alongside fresh LLM-judge results.
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* ─── Section Hint ─── */}
      <SectionHint tabId="grading">{sectionHintTexts.grading}</SectionHint>

      {/* ─── 0. Summary Cards per experiment ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {grades.map((g, i) => (
          <GradeOverviewCard key={g.id} grade={g} color={GRADE_EXP_COLORS[i % GRADE_EXP_COLORS.length]} onNavigate={() => navigate(`/grades/${g.id}`)} />
        ))}
      </div>

      {/* ─── 1. Score Distribution (stacked bar — cross-experiment) ─── */}
      {distributionData.length > 1 && (
        <div className="rounded-xl bg-dash-card border border-dash-border p-3 md:p-4">
          <h3 className="text-sm font-semibold text-dash-text mb-4">Score Distribution Comparison</h3>
          <ResponsiveContainer width="100%" height={Math.max(180, distributionData.length * 50)}>
            <BarChart data={distributionData} layout="vertical" margin={{ top: 5, right: isMobile ? 10 : 30, left: isMobile ? 5 : 140, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
              <XAxis type="number" tick={tickStyle} allowDecimals={false} />
              <YAxis dataKey="name" type="category" tick={{ ...tickStyle, fontSize: isMobile ? 9 : 11 }} width={isMobile ? 80 : 130} />
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
      <div className={`grid grid-cols-1 ${hasDisagreement ? 'md:grid-cols-2' : ''} gap-4`}>
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

        {/* ─── 3. Grader Disagreement (multi-judge only; hidden when all zero) ─── */}
        {hasDisagreement && (
          <div className="rounded-xl bg-dash-card border border-dash-border p-4">
            <div className="flex items-center gap-2 mb-4">
              <AlertCircle className="w-4 h-4 text-purple-400" />
              <h3 className="text-sm font-semibold text-dash-text flex items-center gap-1">Grader Disagreement <InfoTooltip content={tooltipTexts.grading.graderDisagreement} position="bottom" /></h3>
            </div>
            <div className="space-y-4">
              {disagreementData.filter((d) => d.inconsistent > 0).map((d, i) => (
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
                Visible only in multi-judge mode (Phase B). Single-judge runs always show 0.
              </p>
            </div>
          </div>
        )}
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
              {g.grade_status === 'legacy_dummy' && <span className="text-[9px] text-zinc-400 ml-0.5">(demo)</span>}
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
  const isLegacyDummy = grade.grade_status === 'legacy_dummy'
  const isOfficial = isOfficialGrade(grade)
  const wow = grade.summary_v1?.wow
  const stats = [
    { icon: Target, label: 'Graded', value: `${s.graded_tasks}/${s.total_tasks}`, color: 'text-blue-400 bg-blue-500/10' },
    { icon: Award, label: 'Perfect', value: s.perfect_score, color: 'text-emerald-400 bg-emerald-500/10' },
    { icon: BarChart3, label: 'Partial', value: s.partial_score, color: 'text-amber-400 bg-amber-500/10' },
    { icon: XCircle, label: 'Zero', value: s.zero_score, color: 'text-red-400 bg-red-500/10' },
    ...(s.inconsistent_grades > 0
      ? [{ icon: AlertCircle, label: 'Disagree', value: s.inconsistent_grades as number | string, color: 'text-purple-400 bg-purple-500/10' }]
      : []),
    { icon: AlertTriangle, label: 'Error', value: s.error_tasks, color: 'text-orange-400 bg-orange-500/10' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className={
        'rounded-xl p-4 hover:border-dash-border-active transition-all cursor-pointer relative overflow-hidden ' +
        (isLegacyDummy
          ? 'bg-dash-card/60 border border-dashed border-dash-border'
          : 'bg-dash-card border border-dash-border')
      }
      onClick={onNavigate}
    >
      <div>
        {/* header */}
        <div className="flex items-start justify-between mb-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
              <h4 className="text-sm font-semibold text-dash-text">{grade.label}</h4>
              {isOfficial && (
                <span
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-[9px] font-bold uppercase tracking-wider text-emerald-400"
                  title="Curated official baseline run"
                >
                  <Award className="w-2.5 h-2.5" />
                  OFFICIAL
                </span>
              )}
              {isLegacyDummy && (
                <span
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-zinc-500/10 border border-zinc-500/30 text-[9px] font-bold uppercase tracking-wider text-zinc-400"
                  title="Legacy demonstration data — not a real graded run"
                >
                  <BookOpen className="w-2.5 h-2.5" />
                  DEMO
                </span>
              )}
            </div>
            <div className="text-[10px] text-dash-text-faint space-y-0.5">
              <div className="flex items-center gap-1">
                <span className="uppercase tracking-wider opacity-70">Inference</span>
                {grade.inference_model
                  ? <span className="font-mono text-dash-text">{grade.inference_model}</span>
                  : <span className="italic">unknown</span>}
              </div>
              <div className="flex items-center gap-1">
                <span className="uppercase tracking-wider opacity-70">Judge</span>
                {grade.judge_model
                  ? <span className="font-mono text-fuchsia-300/80">{grade.judge_model}</span>
                  : <span className="italic">—</span>}
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-dash-heading font-mono">{s.avg_score_pct}%</p>
            {s.ci_pct && <p className="text-[10px] text-dash-text-faint flex items-center gap-0.5 justify-end">± {s.ci_pct}% CI <InfoTooltip content={tooltipTexts.grading.ci} position="left" /></p>}
          </div>
        </div>

        {/* Mini-health pills (graded_v1 only) */}
        {grade.grade_status === 'graded_v1' && wow && (
          <div className="flex items-center gap-2 text-[10px] mt-1 mb-3 font-mono">
            <span
              className={(wow.judge_error_rate ?? 0) > 0.05
                ? 'text-red-400 font-semibold'
                : 'text-emerald-400'}
              title={tooltipTexts.health.judgeErrorRate}
            >
              err {fmtPct(wow.judge_error_rate)}
            </span>
            <span className="text-dash-text-muted" title={tooltipTexts.health.judgePassRate}>
              judge {fmtPct(wow.judge_pass_rate)}
            </span>
            <span className="text-dash-text-muted" title={tooltipTexts.health.precheckPassRate}>
              precheck {fmtPct(wow.precheck_pass_rate)}
            </span>
          </div>
        )}

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
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-sm bg-emerald-500 inline-block" /> Perfect {s.perfect_score} <InfoTooltip content={tooltipTexts.grading.perfect} position="bottom" /></span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-sm bg-amber-500 inline-block" /> Partial {s.partial_score} <InfoTooltip content={tooltipTexts.grading.partial} position="bottom" /></span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-sm bg-red-500 inline-block" /> Zero {s.zero_score} <InfoTooltip content={tooltipTexts.grading.zero} position="bottom" /></span>
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
