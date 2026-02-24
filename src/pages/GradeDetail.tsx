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
  AlertTriangle,
  Filter,
  ExternalLink,
  HelpCircle,
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
import { useGrades, TaskGrade } from '../hooks/useGrades'

type TaskFilter = 'all' | 'perfect' | 'partial' | 'zero' | 'error' | 'inconsistent'

const TERM_DEFINITIONS: Record<string, string> = {
  graded: 'Tasks that received a score — excludes any that errored out.',
  perfect: 'Score = 100% — all rubric criteria were fully satisfied.',
  partial: 'Score between 0–100% — some rubric criteria were met.',
  zero: 'Score = 0% — no rubric criteria were satisfied.',
  error: 'Tasks that could not be evaluated due to API failures, timeouts, or parsing issues.',
  errors: 'Tasks that could not be evaluated due to API failures, timeouts, or parsing issues.',
  inconsistent: 'Multiple graders scored the same task differently.',
  disagreement: 'Multiple graders scored the same task differently — indicates ambiguous rubric or borderline output.',
}

const FILTER_LABELS: Record<Exclude<TaskFilter, 'all'>, string> = {
  perfect: 'Perfect',
  partial: 'Partial',
  zero: 'Zero',
  error: 'Error',
  inconsistent: 'Inconsistent',
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
      { label: '0%', count: buckets['0%'], color: 'hsl(0, 84%, 60%)' },
      { label: '~33%', count: buckets['33%'], color: 'hsl(25, 95%, 53%)' },
      { label: '~67%', count: buckets['67%'], color: 'hsl(45, 93%, 47%)' },
      { label: '100%', count: buckets['100%'], color: 'hsl(142, 71%, 45%)' },
    ]
  }, [grade])

  // Pie chart data
  const pieData = useMemo(() => {
    if (!grade) return []
    const s = grade.summary
    return [
      { name: 'Perfect', value: s.perfect_score, fill: '#22c55e' },
      { name: 'Partial', value: s.partial_score, fill: '#f59e0b' },
      { name: 'Zero', value: s.zero_score, fill: '#ef4444' },
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
        exit={{ opacity: 0 }}
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
        exit={{ opacity: 0 }}
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
          {grade.is_dummy && (
            <div className="mb-3 inline-flex items-center gap-2 bg-amber-500/10 text-amber-600 dark:text-amber-400 px-3 py-1.5 rounded-md text-sm font-medium">
              <AlertTriangle className="h-4 w-4" />
              ⏳ We're still waiting for grading results. This takes a while.
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
          <div className="flex flex-wrap items-center gap-3 text-sm md:text-base text-muted-foreground">
            <span>{grade.model}</span>
            <span>•</span>
            <span>{s.total_tasks} tasks</span>
            {grade.dataset_url && (
              <>
                <span>•</span>
                <a
                  href={grade.dataset_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline inline-flex items-center gap-1"
                >
                  HuggingFace <ExternalLink className="h-3 w-3" />
                </a>
              </>
            )}
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
              value={`${s.avg_score_pct}%`}
              sub={s.ci_pct ? `± ${s.ci_pct}%` : undefined}
              color="text-blue-500"
              bg="bg-blue-500/10"
            />
            <OverviewStat
              icon={Award}
              label="Perfect (100%)"
              tooltip={TERM_DEFINITIONS.perfect}
              value={String(s.perfect_score)}
              sub={`${((s.perfect_score / s.total_tasks) * 100).toFixed(1)}%`}
              color="text-emerald-500"
              bg="bg-emerald-500/10"
            />
            <OverviewStat
              icon={XCircle}
              label="Zero (0%)"
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
                <strong className="text-emerald-500">{s.perfect_score}</strong> scored full marks,{' '}
                <strong className="text-amber-500">{s.partial_score}</strong> received partial credit,
                and <strong className="text-red-500">{s.zero_score}</strong> got zero.
                {s.error_tasks > 0 && (
                  <> <strong className="text-orange-500">{s.error_tasks}</strong> task{s.error_tasks > 1 ? 's' : ''} could not be evaluated.</>
                )}
                {' '}The average score was <strong>{s.avg_score_pct}%</strong>
                {s.ci_pct && <> (±{s.ci_pct}% at 95% confidence)</>}.
                {s.inconsistent_grades > 0 && (
                  <> Graders disagreed on <strong className="text-purple-500">{s.inconsistent_grades}</strong> task{s.inconsistent_grades > 1 ? 's' : ''}.</>
                )}
              </p>
            </CardContent>
          </Card>
        </motion.div>

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
                  {(['all', 'perfect', 'partial', 'zero', 'error', 'inconsistent'] as TaskFilter[]).map((f) => (
                    <button
                      key={f}
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

function TaskRow({ task, index }: { task: TaskGrade; index: number }) {
  const getStatusBadge = () => {
    if (task.error) {
      return <span className="px-2 py-0.5 rounded-full text-xs bg-orange-500/10 text-orange-500">Error</span>
    }
    if (task.avg_score === 1) {
      return <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-500">Perfect</span>
    }
    if (task.avg_score === 0) {
      return <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-500">Zero</span>
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
        {task.avg_score !== null ? `${(task.avg_score * 100).toFixed(0)}%` : '—'}
      </td>
      <td className="py-2 px-3 text-center">{getStatusBadge()}</td>
    </tr>
  )
}

export default GradeDetail
