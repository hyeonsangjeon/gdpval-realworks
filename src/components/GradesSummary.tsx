import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Card, CardContent } from './ui/card'
import { AlertTriangle, Award, Target, XCircle, BarChart3, AlertCircle, HelpCircle } from 'lucide-react'
import { GradeResult } from '../hooks/useGrades'

const STAT_TOOLTIPS: Record<string, string> = {
  Graded: 'Tasks that received a score — excludes any that errored out.',
  'Perfect (100%)': 'Score = 100% — all rubric criteria were fully satisfied.',
  Partial: 'Score between 0–100% — some rubric criteria were met.',
  'Zero (0%)': 'Score = 0% — no rubric criteria were satisfied.',
  Disagreement: 'Multiple graders scored the same task differently — indicates ambiguous rubric or borderline output.',
  Errors: 'Tasks that could not be evaluated due to API failures, timeouts, or parsing issues.',
}

function StatTooltip({ label }: { label: string }) {
  const def = STAT_TOOLTIPS[label]
  if (!def) return <p className="text-xs text-muted-foreground">{label}</p>
  return (
    <span className="relative inline-flex items-center gap-0.5 group cursor-help text-xs text-muted-foreground">
      <span>{label}</span>
      <HelpCircle className="h-3 w-3 text-muted-foreground flex-shrink-0" />
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-52 rounded-md bg-popover border border-border text-xs text-popover-foreground px-2.5 py-2 opacity-0 group-hover:opacity-100 transition-opacity shadow-md text-center leading-relaxed whitespace-normal font-normal">
        {def}
      </span>
    </span>
  )
}

interface GradesSummaryProps {
  grades: GradeResult[]
}

function ScoreBar({ perfect, partial, zero, total }: { perfect: number; partial: number; zero: number; total: number }) {
  const pPct = (perfect / total) * 100
  const partPct = (partial / total) * 100
  const zPct = (zero / total) * 100

  return (
    <div className="space-y-2">
      <div className="flex h-4 w-full rounded-full overflow-hidden bg-muted">
        {pPct > 0 && (
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pPct}%` }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
            className="bg-emerald-500 h-full"
            title={`Perfect: ${perfect}`}
          />
        )}
        {partPct > 0 && (
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${partPct}%` }}
            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 }}
            className="bg-amber-500 h-full"
            title={`Partial: ${partial}`}
          />
        )}
        {zPct > 0 && (
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${zPct}%` }}
            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
            className="bg-red-500 h-full"
            title={`Zero: ${zero}`}
          />
        )}
      </div>
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <div className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500" />
          <span>Perfect {perfect}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-500" />
          <span>Partial {partial}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-500" />
          <span>Zero {zero}</span>
        </div>
      </div>
    </div>
  )
}

function StatMini({ icon: Icon, label, value, color }: { icon: typeof Award; label: string; value: string | number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`rounded-md p-1.5 ${color}`}>
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div>
        <StatTooltip label={label} />
        <p className="text-sm font-semibold text-foreground">{value}</p>
      </div>
    </div>
  )
}

function GradeCard({ grade, index }: { grade: GradeResult; index: number }) {
  const s = grade.summary

  return (
    <Link to={`/grades/${grade.id}`} className="block">
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
    >
      <Card className="bg-card/50 backdrop-blur border-border relative overflow-hidden hover:border-primary/50 transition-all duration-300 cursor-pointer">
        {/* Dummy banner */}
        {grade.is_dummy && (
          <div className="absolute top-0 left-0 right-0 bg-amber-500/90 text-amber-950 text-center text-[11px] font-bold py-1 tracking-wider uppercase">
            ⏳ We're still waiting for grading results. This takes a while.
          </div>
        )}

        <CardContent className={`p-6 ${grade.is_dummy ? 'pt-10' : ''}`}>
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-foreground">{grade.label}</h3>
              <p className="text-sm text-muted-foreground">{grade.model}</p>
              {grade.dataset_url && (
                <a
                  href={grade.dataset_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline"
                >
                  HuggingFace Dataset ↗
                </a>
              )}
            </div>
            <div className="text-right">
              <motion.p
                className="text-3xl font-bold text-foreground"
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.3 }}
              >
                {s.avg_score_pct}%
              </motion.p>
              {s.ci_pct && (
                <p className="text-xs text-muted-foreground">± {s.ci_pct}% (95% CI)</p>
              )}
              <p className="text-xs text-muted-foreground">Average Score</p>
            </div>
          </div>

          {/* Score Distribution Bar */}
          <div className="mb-5">
            <ScoreBar
              perfect={s.perfect_score}
              partial={s.partial_score}
              zero={s.zero_score}
              total={s.total_tasks}
            />
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatMini
              icon={Target}
              label="Graded"
              value={`${s.graded_tasks}/${s.total_tasks}`}
              color="bg-blue-500/10 text-blue-500"
            />
            <StatMini
              icon={Award}
              label="Perfect (100%)"
              value={s.perfect_score}
              color="bg-emerald-500/10 text-emerald-500"
            />
            <StatMini
              icon={BarChart3}
              label="Partial"
              value={s.partial_score}
              color="bg-amber-500/10 text-amber-500"
            />
            <StatMini
              icon={XCircle}
              label="Zero (0%)"
              value={s.zero_score}
              color="bg-red-500/10 text-red-500"
            />
            <StatMini
              icon={AlertCircle}
              label="Disagreement"
              value={s.inconsistent_grades}
              color="bg-purple-500/10 text-purple-500"
            />
            <StatMini
              icon={AlertTriangle}
              label="Errors"
              value={s.error_tasks}
              color="bg-orange-500/10 text-orange-500"
            />
          </div>
        </CardContent>
      </Card>
    </motion.div>
    </Link>
  )
}

function GradesSummary({ grades }: GradesSummaryProps) {
  if (grades.length === 0) return null

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground mb-4">
        Grading Results
        {grades.some(g => g.is_dummy) && (
          <span className="ml-2 text-sm font-normal text-amber-500">
            (includes dummy data)
          </span>
        )}
      </h2>
      {grades.map((grade, index) => (
        <GradeCard key={grade.id} grade={grade} index={index} />
      ))}
    </div>
  )
}

export default GradesSummary
