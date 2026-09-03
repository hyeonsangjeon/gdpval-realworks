import { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  Award,
  Target,
  XCircle,
  BarChart3,
  AlertCircle,
  Filter,
  ExternalLink,
  HelpCircle,
  BookOpen,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  ShieldAlert,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from 'recharts'
import Header from '../components/Header'
import ZeroReasonBreakdown from '../components/ZeroReasonBreakdown'
import { useGrades, TaskGrade } from '../hooks/useGrades'
import type { GradeSummaryV1, TaskGradeV1, SelectionOutcome } from '../types/grade'
import {
  RubricCoverageCard,
  CriticalItemCard,
  StructureVsReasoning,
  SectorHeatmap,
  ScoreDensityHistogram,
  RubricSeverityCurve,
  HealthStrip,
} from '../components/wow'
import InfoTooltip from '../components/common/InfoTooltip'
import { tooltipTexts } from '../data/tooltipTexts'
import {
  NEAR_PERFECT_DEF,
  NEAR_PERFECT_LABEL,
  NEAR_PERFECT_MIN_PCT,
  NEAR_PERFECT_SHORT,
  NEAR_ZERO_DEF,
  NEAR_ZERO_LABEL,
  NEAR_ZERO_MAX_PCT,
  NEAR_ZERO_SHORT,
  PARTIAL_DEF,
  formatTaskScorePct,
} from '../data/scoreBands'
import {
  hasUnverifiedRouteProvenance,
  UNVERIFIED_PROVENANCE_DESCRIPTION,
} from '../lib/gradeProvenance.js'

type TaskFilter =
  | 'all'
  | 'perfect'
  | 'partial'
  | 'zero'
  | 'error'
  | 'inconsistent'
  | 'calibrated'
  | 'overconfident'
  | 'underconfident'

const TERM_DEFINITIONS: Record<string, string> = {
  graded: 'Tasks that received a score — excludes any that errored out.',
  perfect: NEAR_PERFECT_DEF,
  partial: PARTIAL_DEF,
  zero: NEAR_ZERO_DEF,
  error: 'Tasks that could not be evaluated due to API failures, timeouts, or parsing issues.',
  errors: 'Tasks that could not be evaluated due to API failures, timeouts, or parsing issues.',
  inconsistent: 'Multiple graders scored the same task differently.',
  disagreement: 'Multiple graders scored the same task differently — indicates ambiguous rubric or borderline output.',
  calibrated: 'Tasks where |Rubric − Self-QA| ≤ 10pp. Model self-assessment matches external rubric.',
  overconfident: 'Tasks where Rubric − Self-QA < −10pp. Model rated itself higher than rubric. Risk signal.',
  underconfident: 'Tasks where Rubric − Self-QA > +10pp. Model underestimated its own work.',
}

const FILTER_LABELS: Record<Exclude<TaskFilter, 'all'>, string> = {
  perfect: NEAR_PERFECT_SHORT,
  partial: 'Partial',
  zero: NEAR_ZERO_SHORT,
  error: 'Error',
  inconsistent: 'Inconsistent',
  calibrated: 'Calibrated',
  overconfident: 'Overconfident',
  underconfident: 'Underconfident',
}

// Compute Δ = Rubric% − SelfQA%. Returns null if any input is missing.
function computeDelta(qa_score: number | null | undefined, avg_score: number | null | undefined): number | null {
  if (qa_score == null || avg_score == null) return null
  return (avg_score * 100) - (qa_score * 10)
}

function gapStyle(delta: number | null): { className: string; severe: boolean } {
  if (delta == null) return { className: 'text-muted-foreground', severe: false }
  const abs = Math.abs(delta)
  if (abs <= 10) return { className: 'text-muted-foreground bg-muted/30', severe: false }
  if (abs <= 30) return { className: 'text-amber-500 bg-amber-500/10', severe: false }
  return { className: 'text-red-500 bg-red-500/10', severe: true }
}

function calibStatus(delta: number | null): {
  icon: typeof Target | null
  label: string
  className: string
} {
  if (delta == null) return { icon: null, label: '—', className: 'text-muted-foreground' }
  if (Math.abs(delta) <= 10) return { icon: Target, label: 'Aligned', className: 'text-muted-foreground' }
  if (delta < -10) return { icon: TrendingDown, label: 'Over', className: 'text-red-500' }
  return { icon: TrendingUp, label: 'Under', className: 'text-amber-500' }
}

function TermTooltip({ term, definition, className }: { term: string; definition?: string; className?: string }) {
  const def = definition ?? TERM_DEFINITIONS[term.toLowerCase()] ?? ''
  return (
    <span className={`relative inline-flex items-center gap-0.5 group cursor-help ${className ?? 'text-xs text-muted-foreground'}`}>
      <span>{term}</span>
      <HelpCircle className="h-3 w-3 text-muted-foreground flex-shrink-0" />
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-56 rounded-md bg-popover border border-border text-xs text-popover-foreground px-2.5 py-2 opacity-0 group-hover:opacity-100 transition-opacity shadow-md text-center leading-relaxed whitespace-normal font-normal">
        {def}
      </span>
    </span>
  )
}

function GradeDetail() {
  const { gradeId } = useParams()
  const { grades, loading } = useGrades()
  const grade = grades.find((g) => g.id === gradeId)
  const [taskFilter, setTaskFilter] = useState<TaskFilter>('all')

  // Score distribution data for bar chart
  const scoreDistribution = useMemo(() => {
    if (!grade) return []
    // Bucket keys stay the four OpenAI score levels; only the labels below say
    // what the two end buckets actually hold. `avg_score` is snapped at the
    // band boundaries, so `pct === 0` is every task at or under NEAR_ZERO_MAX_PCT
    // and `pct === 100` is every task at or over NEAR_PERFECT_MIN_PCT — neither
    // end is the exact figure its old label claimed.
    const buckets: Record<string, number> = {
      '0%': 0,
      '33%': 0,
      '67%': 0,
      '100%': 0,
    }
    grade.tasks.forEach((t) => {
      if (t.error || t.avg_score === null) return
      const pct = t.avg_score * 100
      if (pct === 0) buckets['0%']++
      else if (pct <= 40) buckets['33%']++
      else if (pct < 100) buckets['67%']++
      else buckets['100%']++
    })
    return [
      { label: `≤${NEAR_ZERO_MAX_PCT}%`, count: buckets['0%'], color: 'hsl(0, 84%, 60%)' },
      { label: '~33%', count: buckets['33%'], color: 'hsl(25, 95%, 53%)' },
      { label: '~67%', count: buckets['67%'], color: 'hsl(45, 93%, 47%)' },
      { label: `≥${NEAR_PERFECT_MIN_PCT}%`, count: buckets['100%'], color: 'hsl(142, 71%, 45%)' },
    ]
  }, [grade])

  // Pie chart data
  const pieData = useMemo(() => {
    if (!grade) return []
    const s = grade.summary
    return [
      { name: NEAR_PERFECT_SHORT, value: s.perfect_score, fill: '#22c55e' },
      { name: 'Partial', value: s.partial_score, fill: '#f59e0b' },
      { name: NEAR_ZERO_SHORT, value: s.zero_score, fill: '#ef4444' },
      { name: 'Error', value: s.error_tasks, fill: '#f97316' },
    ].filter((d) => d.value > 0)
  }, [grade])

  // Grader consistency data
  const consistencyData = useMemo(() => {
    if (!grade) return { agree: 0, disagree: 0 }
    const graded = grade.tasks.filter((t) => !t.error && t.scores.length > 0)
    const agree = graded.filter((t) => {
      const unique = new Set(t.scores)
      return unique.size === 1
    }).length
    return { agree, disagree: graded.length - agree }
  }, [grade])

  // Filtered tasks
  const filteredTasks = useMemo(() => {
    if (!grade) return []
    return grade.tasks.filter((t: TaskGrade) => {
      switch (taskFilter) {
        case 'perfect':
          return !t.error && t.avg_score === 1
        case 'partial':
          return !t.error && t.avg_score !== null && t.avg_score > 0 && t.avg_score < 1
        case 'zero':
          return !t.error && t.avg_score === 0
        case 'error':
          return t.error
        case 'inconsistent':
          return !t.error && t.scores.length > 1 && new Set(t.scores).size > 1
        case 'calibrated': {
          const delta = computeDelta(t.qa_score, t.avg_score)
          return delta != null && Math.abs(delta) <= 10
        }
        case 'overconfident': {
          const delta = computeDelta(t.qa_score, t.avg_score)
          return delta != null && delta < -10
        }
        case 'underconfident': {
          const delta = computeDelta(t.qa_score, t.avg_score)
          return delta != null && delta > 10
        }
        default:
          return true
      }
    })
  }, [grade, taskFilter])

  if (loading) {
    return (
      <motion.div
        className="min-h-screen bg-background"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <Header />
        <div className="container mx-auto px-4 py-8 text-center text-muted-foreground">Loading...</div>
      </motion.div>
    )
  }

  if (!grade) {
    return (
      <motion.div
        className="min-h-screen bg-background"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <Header />
        <div className="container mx-auto px-4 py-8">
          <Link to="/" className="text-primary hover:underline inline-flex items-center gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
          <p className="mt-8 text-muted-foreground">Grade result not found</p>
        </div>
      </motion.div>
    )
  }

  const s = grade.summary

  return (
    <motion.div
      className="min-h-screen bg-background"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Header />

      <div className="container mx-auto px-4 py-8">
        {/* Back Button */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
        >
          <Link
            to="/"
            className="text-primary hover:underline inline-flex items-center gap-2 mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
        </motion.div>

        {/* Title + Dummy Banner */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="mb-6 md:mb-8"
        >
          {grade.grade_status === 'legacy_dummy' && (
            <div className="mb-3 inline-flex items-center gap-2 bg-zinc-500/10 text-zinc-300 border border-zinc-500/30 px-3 py-1.5 rounded-md text-sm font-medium">
              <BookOpen className="h-4 w-4" />
              Legacy demo grades — this card shows demonstration data, not a real LLM-judge run.
            </div>
          )}
          {hasUnverifiedRouteProvenance(
            grade.source_azure_ai_provenance_status,
          ) && (
            <div className="mb-3 flex items-start gap-2 bg-amber-500/10 text-amber-700 dark:text-amber-200 border border-amber-500/30 px-3 py-1.5 rounded-md text-sm font-medium">
              <ShieldAlert className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{UNVERIFIED_PROVENANCE_DESCRIPTION}</span>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3 mb-1">
            <h1 className="text-2xl md:text-4xl font-bold text-foreground">
              {grade.label}
            </h1>
            {/* A/B vs Single test badge */}
            {grade.experiment_type === 'ab' ? (
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-violet-500/10 text-violet-500 border border-violet-500/20">
                A/B Test
              </span>
            ) : (
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-sky-500/10 text-sky-500 border border-sky-500/20">
                Single Test
              </span>
            )}
          </div>
          <p className="text-base text-muted-foreground mb-2">Grading Results</p>
          <div className="flex flex-col gap-1 text-sm mt-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Inference
              </span>
              {grade.inference_model ? (
                <span className="px-2 py-0.5 rounded bg-foreground/5 border border-border font-mono text-xs text-foreground">
                  {grade.inference_model}
                </span>
              ) : (
                <span className="font-mono text-xs italic text-amber-500/80">unknown</span>
              )}
              <span className="text-muted-foreground">· {s.total_tasks} tasks</span>
              {grade.dataset_url && (
                <a
                  href={grade.dataset_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline inline-flex items-center gap-1"
                >
                  HuggingFace <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Graded by
              </span>
              {grade.judge_model ? (
                <span className="px-2 py-0.5 rounded bg-fuchsia-500/10 border border-fuchsia-400/20 font-mono text-xs text-fuchsia-300">
                  {grade.judge_model}
                </span>
              ) : (
                <span className="font-mono text-xs italic text-muted-foreground">— (legacy)</span>
              )}
              <InfoTooltip content={tooltipTexts.grading.judgeVsInference} />
            </div>
          </div>
        </motion.div>

        {/* Overview Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.15 }}
          className="mb-8"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <OverviewStat
              icon={Target}
              label="Average Score"
              tooltip="Mean score across all graded tasks (excluding errors), expressed as a percentage."
              value={s.avg_score_pct == null ? '—' : `${s.avg_score_pct}%`}
              sub={s.ci_pct ? `± ${s.ci_pct}%` : undefined}
              color="text-blue-500"
              bg="bg-blue-500/10"
            />
            <OverviewStat
              icon={Award}
              label={NEAR_PERFECT_LABEL}
              tooltip={TERM_DEFINITIONS.perfect}
              value={String(s.perfect_score)}
              sub={`${((s.perfect_score / s.total_tasks) * 100).toFixed(1)}%`}
              color="text-emerald-500"
              bg="bg-emerald-500/10"
            />
            <OverviewStat
              icon={XCircle}
              label={NEAR_ZERO_LABEL}
              tooltip={TERM_DEFINITIONS.zero}
              value={String(s.zero_score)}
              sub={`${((s.zero_score / s.total_tasks) * 100).toFixed(1)}%`}
              color="text-red-500"
              bg="bg-red-500/10"
            />
            <OverviewStat
              icon={AlertCircle}
              label="Inconsistent"
              tooltip={TERM_DEFINITIONS.inconsistent}
              value={String(s.inconsistent_grades)}
              sub={`${((s.inconsistent_grades / s.total_tasks) * 100).toFixed(1)}%`}
              color="text-purple-500"
              bg="bg-purple-500/10"
            />
          </div>
        </motion.div>

        {/* ── HealthStrip: item-level judge run-quality diagnostics ── */}
        {grade.schema_version != null && grade.summary_v1 ? (
          <HealthStrip summaryV1={grade.summary_v1} delay={0.2} />
        ) : null}

        {/* ── WOW: Item-level Rubric Insights ── */}
        {grade.schema_version != null && grade.summary_v1 ? (
          <WowSection summary={grade.summary_v1} tasksV1={grade.tasks_v1 ?? []} />
        ) : null}

        {/* Score Distribution + Pie — side by side */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Score Distribution Bar Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Card className="bg-card/50 backdrop-blur border-border h-full">
              <CardHeader>
                <CardTitle className="text-lg">Score Distribution</CardTitle>
                <p className="text-sm text-muted-foreground">Tasks grouped by average score</p>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={scoreDistribution} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="label"
                      stroke="hsl(var(--muted-foreground))"
                      tick={{ fill: 'hsl(var(--foreground))' }}
                    />
                    <YAxis
                      stroke="hsl(var(--muted-foreground))"
                      tick={{ fill: 'hsl(var(--muted-foreground))' }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                      }}
                      labelStyle={{ color: 'hsl(var(--foreground))' }}
                      cursor={{ fill: 'hsl(var(--muted))' }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {scoreDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </motion.div>

          {/* Grader Consistency — VS style */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.25 }}
          >
            <Card className="bg-card/50 backdrop-blur border-border h-full">
              <CardHeader>
                <CardTitle className="text-lg">Grader Consistency</CardTitle>
                <p className="text-sm text-muted-foreground">Agreement across multiple graders</p>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center gap-4 md:gap-8">
                  {/* Agree side */}
                  <div className="text-center flex-1">
                    <motion.p
                      className="text-4xl font-bold text-emerald-500"
                      initial={{ opacity: 0, scale: 0.5 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.5, delay: 0.3 }}
                    >
                      {consistencyData.agree}
                    </motion.p>
                    <p className="text-sm text-muted-foreground mt-1">Agree</p>
                    <p className="text-xs text-muted-foreground">
                      ({((consistencyData.agree / (consistencyData.agree + consistencyData.disagree || 1)) * 100).toFixed(1)}%)
                    </p>
                  </div>

                  {/* VS badge */}
                  <motion.div
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.3, delay: 0.35 }}
                    className="bg-primary text-primary-foreground rounded-full w-10 h-10 flex items-center justify-center font-bold text-xs shadow-lg flex-shrink-0"
                  >
                    VS
                  </motion.div>

                  {/* Disagree side */}
                  <div className="text-center flex-1">
                    <motion.p
                      className="text-4xl font-bold text-amber-500"
                      initial={{ opacity: 0, scale: 0.5 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.5, delay: 0.4 }}
                    >
                      {consistencyData.disagree}
                    </motion.p>
                    <p className="text-sm text-muted-foreground mt-1">Disagree</p>
                    <p className="text-xs text-muted-foreground">
                      ({((consistencyData.disagree / (consistencyData.agree + consistencyData.disagree || 1)) * 100).toFixed(1)}%)
                    </p>
                  </div>
                </div>

                {/* Consistency bar */}
                <div className="mt-6">
                  <div className="flex h-3 w-full rounded-full overflow-hidden bg-muted">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{
                        width: `${(consistencyData.agree / (consistencyData.agree + consistencyData.disagree || 1)) * 100}%`,
                      }}
                      transition={{ duration: 0.8, ease: 'easeOut', delay: 0.3 }}
                      className="bg-emerald-500 h-full"
                    />
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{
                        width: `${(consistencyData.disagree / (consistencyData.agree + consistencyData.disagree || 1)) * 100}%`,
                      }}
                      transition={{ duration: 0.8, ease: 'easeOut', delay: 0.4 }}
                      className="bg-amber-500 h-full"
                    />
                  </div>
                </div>

                {/* Pie chart */}
                <div className="mt-6 flex justify-center">
                  <ResponsiveContainer width={160} height={160}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        dataKey="value"
                        cx="50%"
                        cy="50%"
                        innerRadius={40}
                        outerRadius={70}
                        paddingAngle={2}
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`pie-${index}`} fill={entry.fill} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex items-center justify-center gap-4 text-xs text-muted-foreground mt-2">
                  {pieData.map((d) => (
                    <div key={d.name} className="flex items-center gap-1">
                      <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: d.fill }} />
                      <span>{d.name} {d.value}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Analysis placeholder */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="mb-8"
        >
          <Card className="bg-gradient-to-br from-card/50 to-card/30 backdrop-blur border-border">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-foreground leading-relaxed">
                Out of <strong>{s.graded_tasks}</strong> evaluated tasks,{' '}
                <strong className="text-emerald-500">{s.perfect_score}</strong> scored {NEAR_PERFECT_MIN_PCT}% or above,{' '}
                <strong className="text-amber-500">{s.partial_score}</strong> received partial credit,
                and <strong className="text-red-500">{s.zero_score}</strong> scored {NEAR_ZERO_MAX_PCT}% or below.
                {s.error_tasks > 0 && (
                  <> <strong className="text-orange-500">{s.error_tasks}</strong> task{s.error_tasks > 1 ? 's' : ''} could not be evaluated
                    {/* "could not be evaluated" reads as a model failure unless
                        the cause is named. When the selector recorded one, say it. */}
                    {grade.summary_v1?.selection?.covered
                      && (grade.summary_v1.selection.outcomes?.not_selected ?? 0) > 0
                      ? <> &mdash; the deliverables exist, but the selector could not choose a primary one without guessing, so {s.error_tasks > 1 ? 'they are' : 'it is'} excluded from the average rather than scored zero.</>
                      : <>.</>}
                  </>
                )}
                {s.avg_score_pct == null
                  ? <> No headline score is available.</>
                  : <> The average score was <strong>{s.avg_score_pct}%</strong>
                    {s.ci_pct && <> (±{s.ci_pct}% at 95% confidence)</>}.</>}
                {s.inconsistent_grades > 0 && (
                  <> Graders disagreed on <strong className="text-purple-500">{s.inconsistent_grades}</strong> task{s.inconsistent_grades > 1 ? 's' : ''}.</>
                )}
              </p>
              {/*
                The same caveat the task table carries, said once for the run.
                The banner under the table is per-task and shows fifty rows at
                most; nothing until now told a reader what the *headline* — the
                one number an experiment is remembered by — owed to rubric its
                judge never read. Absent on a run that read everything, so this
                appears only where it is true.

                Both percentages printed here are means over the task rows, and
                that is deliberate. Neither is the published headline above:
                pairing a full-denominator mean with the published figure would
                add a second, unrelated defect into this one and can flip the
                sign of the answer on real files. When the headline and its own
                rows disagree, the sentence after says so rather than leaving a
                reader to reconcile three numbers alone.
              */}
              {(() => {
                const lift = s.score_exclusion_lift
                if (!lift) return null
                const support = s.headline_support
                // Kept as the number rather than a flag: a boolean would need a
                // non-null assertion at the point of use, and asserting a value
                // is present is exactly the habit that puts a stray "0.00
                // points" on screen when it is not.
                const headlineDelta = support?.supported === false
                  && typeof support.delta_pct === 'number'
                  ? support.delta_pct
                  : null
                return (
                  <p className="text-sm text-muted-foreground leading-relaxed mt-3">
                    <strong className="text-foreground">Part of that average is rubric nobody read.</strong>{' '}
                    The judge failed to read <strong>{lift.excluded_items}</strong> rubric
                    item{lift.excluded_items > 1 ? 's' : ''} across{' '}
                    <strong>{lift.tasks_affected}</strong> of the{' '}
                    {lift.tasks_counted} scored task{lift.tasks_counted > 1 ? 's' : ''},
                    worth {lift.excluded_max} points of rubric, and those items left the
                    denominator along with the numerator. Averaging the task rows as
                    published gives <strong>{lift.avg_score_pct_from_rows}%</strong>;
                    scoring the same tasks out of their whole rubrics gives{' '}
                    <strong>{lift.avg_score_pct_full_denominator}%</strong>. The
                    difference — <strong className="text-amber-500">{lift.lift_pct.toFixed(2)} points</strong>{' '}
                    — is what unread rubric adds to this run&apos;s average, and the
                    truth is between the two.
                    {headlineDelta !== null && (
                      <> Neither figure is the headline above: this run publishes an
                        average {Math.abs(headlineDelta).toFixed(2)} points{' '}
                        {headlineDelta < 0 ? 'below' : 'above'} the mean of its own
                        rows, which is a separate problem pulling the other way. The two
                        gaps are reported apart because adding them would describe
                        neither.</>
                    )}
                  </p>
                )
              })()}
            </CardContent>
          </Card>
        </motion.div>

        {/* What the zeros were actually made of. Renders only when the grade
            carries selector metadata, so older experiments are untouched. */}
        <ZeroReasonBreakdown selection={grade.summary_v1?.selection} delay={0.32} />

        {/* Task Details Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.35 }}
        >
          <Card className="bg-card/50 backdrop-blur border-border">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <CardTitle>Task Details</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    Showing {filteredTasks.length} of {grade.tasks.length} tasks
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  {(['all', 'perfect', 'partial', 'zero', 'error', 'inconsistent', 'calibrated', 'overconfident', 'underconfident'] as TaskFilter[]).map((f, idx) => (
                    <span key={f} className="inline-flex items-center">
                      {idx === 6 && (
                        <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
                      )}
                      <button
                        onClick={() => setTaskFilter(f)}
                        className={`relative group px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                          taskFilter === f
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        }`}
                      >
                        {f === 'all' ? 'All' : FILTER_LABELS[f]}
                        {f !== 'all' && (
                          <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-52 rounded-md bg-popover border border-border text-xs text-popover-foreground px-2.5 py-2 opacity-0 group-hover:opacity-100 transition-opacity shadow-md text-center leading-relaxed whitespace-normal font-normal">
                            {TERM_DEFINITIONS[f]}
                          </span>
                        )}
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">#</th>
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Task ID</th>
                      <th className="text-center py-2 px-3 text-muted-foreground font-medium">Scores</th>
                      <th className="text-center py-2 px-3 text-muted-foreground font-medium">Avg</th>
                      <th className="text-center py-2 px-3 text-muted-foreground font-medium">
                        <span title={tooltipTexts.calibration.selfQa}>Self-QA</span>
                      </th>
                      <th className="text-center py-2 px-3 text-muted-foreground font-medium">
                        <span title={tooltipTexts.calibration.gap}>Δ Gap</span>
                      </th>
                      <th className="text-center py-2 px-3 text-muted-foreground font-medium">
                        <span title={tooltipTexts.calibration.status}>Calib.</span>
                      </th>
                      <th className="text-center py-2 px-3 text-muted-foreground font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTasks.slice(0, 50).map((task, i) => (
                      <TaskRow key={task.task_id} task={task} index={i} />
                    ))}
                  </tbody>
                </table>
                {filteredTasks.length > 50 && (
                  <p className="text-center text-xs text-muted-foreground mt-3 py-2">
                    … and {filteredTasks.length - 50} more tasks (showing first 50 only)
                  </p>
                )}
                {/*
                  Only appears when a task in this run actually shows two
                  numbers, so a run whose grading read every rubric item is not
                  told about a problem it does not have.
                */}
                {(() => {
                  const affected = grade.tasks.filter((t: TaskGrade) => t.score_exclusion)
                  if (affected.length === 0) return null
                  const worst = affected.reduce((acc: number, t: TaskGrade) => {
                    const ex = t.score_exclusion
                    if (!ex) return acc
                    return Math.max(acc, ex.pct_published - ex.pct_full_denominator)
                  }, 0)
                  return (
                    <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
                      <strong className="text-foreground">Two numbers in Avg</strong>{' '}
                      ({affected.length} of {grade.tasks.length} tasks): the judge
                      failed to read some rubric items, and those items left the
                      denominator along with the numerator. The left figure is the
                      score out of what was read — the one this run publishes. The
                      right figure is the same points out of the whole rubric. The
                      real score is between them. The widest gap here is{' '}
                      {worst.toFixed(1)} points.
                    </p>
                  )
                })()}
                {(() => {
                  const counts = s.calibration_counts
                  if (!counts) return null
                  const total = s.total_tasks ?? grade.tasks.length
                  const errorCount = s.error_tasks ?? 0
                  const evaluable = total - errorCount
                  const matched = evaluable - counts.unmatched
                  return (
                    <p className="text-xs text-muted-foreground mt-2 text-center">
                      Self-QA matched: {matched}/{evaluable} tasks{counts.unmatched > 0 && ` (${counts.unmatched} unmatched)`}
                    </p>
                  )
                })()}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  )
}

function OverviewStat({
  icon: Icon,
  label,
  tooltip,
  value,
  sub,
  color,
  bg,
}: {
  icon: typeof Target
  label: string
  tooltip?: string
  value: string
  sub?: string
  color: string
  bg: string
}) {
  return (
    <Card className="bg-card/50 backdrop-blur border-border">
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className={`rounded-lg p-2.5 ${bg}`}>
            <Icon className={`h-5 w-5 ${color}`} />
          </div>
          <div>
            {tooltip ? (
              <TermTooltip term={label} definition={tooltip} />
            ) : (
              <p className="text-xs text-muted-foreground">{label}</p>
            )}
            <p className="text-xl font-bold text-foreground">{value}</p>
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// A zero row and a never-graded row used to carry the same badge, which made
// "the model scored nothing" indistinguishable from "nothing reached a judge".
// The badge now names the reason, and the full sentence rides along as the
// title so the table stays narrow.
const OUTCOME_BADGES: Partial<Record<SelectionOutcome, { text: string; className: string }>> = {
  content_zero: { text: 'Zero', className: 'bg-red-500/10 text-red-500' },
  format_unmet: { text: 'Format unmet', className: 'bg-amber-500/10 text-amber-500' },
  inference_failed: { text: 'No output', className: 'bg-orange-500/10 text-orange-500' },
  no_deliverable: { text: 'No deliverable', className: 'bg-orange-400/10 text-orange-400' },
  not_selected: { text: 'Not scored', className: 'bg-violet-400/10 text-violet-400' },
  grading_error: { text: 'Error', className: 'bg-orange-500/10 text-orange-500' },
}

/**
 * The task's score, with both ends shown when a judge failure moved the
 * denominator.
 *
 * A rubric item the judge could not read leaves the numerator and the
 * denominator together, so the task is scored out of less than its rubric is
 * worth. The left number is what the run publishes, out of what was read. The
 * right number is the same points out of the whole rubric. Neither is wrong;
 * the true score is between them, and printing only the left one reads as
 * certainty the grading never had.
 *
 * Both stay visible rather than hiding behind a hover, because the reader who
 * most needs the second number is the one who was not going to look for it.
 */
function ScoreCell({ task }: { task: TaskGrade }) {
  if (task.avg_score === null) return <>—</>
  const exclusion = task.score_exclusion
  if (!exclusion) return <>{formatTaskScorePct(task)}</>

  // `avg_score` is snapped to a flat 1.0/0.0 at the band boundaries so the
  // Status badge can be taken from it by equality, which leaves it unable to
  // state the score it came from. `pct_exact` is present on exactly the rows
  // the snap moved, so prefer it: a 99.77 stays 99.77 here instead of becoming
  // the 100 it never was.
  const publishedPct = task.pct_exact ?? task.avg_score * 100

  // Two numbers that render as the same number are not a range, they read as
  // a bug. Some affected rows differ by less than half a point, so the pair
  // gains decimals rather than one of the ends dropping off the screen. Two
  // is enough and is not a guess: both ends carry two decimals, and the
  // aggregator withholds the key entirely when they are equal there. A row the
  // snap moved takes one decimal even when the pair does not collide, for the
  // same reason the figure is preferred at all.
  const collides = publishedPct.toFixed(0)
    === exclusion.pct_full_denominator.toFixed(0)
  const digits = collides ? 2 : (task.pct_exact === undefined ? 0 : 1)
  const published = `${publishedPct.toFixed(digits)}%`
  const full = `${exclusion.pct_full_denominator.toFixed(digits)}%`

  // The tooltip spells out the left figure from the same number the cell
  // renders, not from the aggregator's `pct_published`, so the cell and its own
  // explanation cannot disagree. A cell that contradicts its tooltip teaches a
  // reader to trust neither.
  const publishedExact = publishedPct.toFixed(2)

  return (
    <span
      className="inline-flex items-baseline gap-1 whitespace-nowrap"
      title={
        `${exclusion.items} rubric item${exclusion.items === 1 ? '' : 's'} `
        + `worth ${exclusion.excluded_max} point${exclusion.excluded_max === 1 ? '' : 's'} `
        + 'could not be graded, so they left the denominator. '
        + `${publishedExact}% is out of the ${exclusion.read_max} points `
        + `that were read; ${exclusion.pct_full_denominator.toFixed(2)}% is out of `
        + 'the whole rubric. The task’s real score is somewhere between the two.'
      }
    >
      <span>{published}</span>
      <span className="text-muted-foreground">~</span>
      <span className="text-muted-foreground">{full}</span>
    </span>
  )
}

function TaskRow({ task, index }: { task: TaskGrade; index: number }) {
  const getStatusBadge = () => {
    const badge = task.outcome ? OUTCOME_BADGES[task.outcome] : undefined
    if (badge) {
      return (
        <span
          className={`px-2 py-0.5 rounded-full text-xs ${badge.className}`}
          title={task.outcome_detail || undefined}
        >
          {badge.text}
        </span>
      )
    }
    if (task.error) {
      return <span className="px-2 py-0.5 rounded-full text-xs bg-orange-500/10 text-orange-500">Error</span>
    }
    if (task.avg_score === 1) {
      return <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-500">{NEAR_PERFECT_SHORT}</span>
    }
    if (task.avg_score === 0) {
      return <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-500">{NEAR_ZERO_SHORT}</span>
    }
    return <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500/10 text-amber-500">Partial</span>
  }

  const isInconsistent = !task.error && task.scores.length > 1 && new Set(task.scores).size > 1

  return (
    <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors">
      <td className="py-2 px-3 text-muted-foreground">{index + 1}</td>
      <td className="py-2 px-3 font-mono text-xs text-foreground">{task.task_id.slice(0, 8)}…</td>
      <td className="py-2 px-3 text-center">
        <div className="flex items-center justify-center gap-1">
          {task.scores.map((score, si) => (
            <span
              key={si}
              className={`inline-block w-6 h-6 rounded text-xs font-medium flex items-center justify-center ${
                score === 1
                  ? 'bg-emerald-500/10 text-emerald-500'
                  : score === 0
                  ? 'bg-red-500/10 text-red-500'
                  : 'bg-amber-500/10 text-amber-500'
              }`}
            >
              {score}
            </span>
          ))}
          {isInconsistent && (
            <AlertCircle className="h-3.5 w-3.5 text-purple-500 ml-1" />
          )}
        </div>
      </td>
      <td className="py-2 px-3 text-center font-mono text-sm">
        <ScoreCell task={task} />
      </td>
      {/* Self-QA */}
      <td className="py-2 px-3 text-center">
        {task.qa_score != null ? (
          <div className="flex flex-col items-center leading-tight">
            <span className="font-semibold">{Math.round(task.qa_score * 10)}%</span>
            <span className="text-xs text-muted-foreground">{task.qa_score.toFixed(1)}/10</span>
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      {/* Δ Gap */}
      <td className="py-2 px-3 text-center">
        {(() => {
          const delta = computeDelta(task.qa_score, task.avg_score)
          if (delta == null) return <span className="text-muted-foreground">—</span>
          const { className, severe } = gapStyle(delta)
          const sign = delta > 0 ? '▲' : delta < 0 ? '▼' : '─'
          const num = delta > 0 ? `+${Math.round(delta)}` : `${Math.round(delta)}`
          return (
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ${className}`}>
              <span>{sign}</span>
              <span>{num}</span>
              {severe && <AlertTriangle className="h-3 w-3" />}
            </span>
          )
        })()}
      </td>
      {/* Calibration status */}
      <td className="py-2 px-3 text-center">
        {(() => {
          const delta = computeDelta(task.qa_score, task.avg_score)
          const { icon: Icon, label, className } = calibStatus(delta)
          return (
            <span className={`inline-flex items-center gap-1 text-xs ${className}`}>
              {Icon && <Icon className="h-3.5 w-3.5" />}
              <span>{label}</span>
            </span>
          )
        })()}
      </td>
      <td className="py-2 px-3 text-center">{getStatusBadge()}</td>
    </tr>
  )
}

export default GradeDetail

function WowSection({ summary, tasksV1 }: { summary: GradeSummaryV1; tasksV1: TaskGradeV1[] }) {
  const wow = summary.wow
  const totalItems = tasksV1.reduce((acc, t) => acc + (Array.isArray(t.items) ? t.items.length : 0), 0)
  const fallbackPcts = tasksV1
    .filter((t) => !t.error && typeof t.pct === 'number')
    .map((t) => t.pct)
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.18 }}
      className="mb-8"
    >
      <div className="flex items-end justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-xl md:text-2xl font-bold text-foreground">
          WOW — Item-level Rubric Insights
        </h2>
        <p className="text-xs text-muted-foreground max-w-xl">
          Item-level partial credit grading powered by our LLM-judge against
          open-sourced GDPval rubrics — richer than the legacy task-level binary.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
        <RubricCoverageCard wow={wow} totalItems={totalItems} delay={0.0} />
        <CriticalItemCard wow={wow} delay={0.05} />
        <StructureVsReasoning wow={wow} delay={0.1} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ScoreDensityHistogram wow={wow} fallbackPcts={fallbackPcts} delay={0.15} />
        <RubricSeverityCurve wow={wow} delay={0.2} />
      </div>
      <div className="mt-4">
        <SectorHeatmap wow={wow} delay={0.25} />
      </div>
    </motion.section>
  )
}
