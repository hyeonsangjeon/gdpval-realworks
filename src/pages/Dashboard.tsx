import { useState, useMemo, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Github, Eye, EyeOff, BarChart3, TrendingUp, AlertTriangle, Award, Sun, Moon, HelpCircle, BookOpen } from 'lucide-react'
import ScopeBadge from '../components/ScopeBadge'
import LeaderboardView from '../components/dashboard/LeaderboardView'
import TrendView from '../components/dashboard/TrendView'
import ErrorAnalysisView from '../components/dashboard/ErrorAnalysisView'
import GradingAnalysisView from '../components/dashboard/GradingAnalysisView'
import InfoTooltip from '../components/common/InfoTooltip'
import AboutModal from '../components/common/AboutModal'
import { useReports } from '../hooks/useReports'
import { useTheme } from '../contexts/ThemeContext'
import { tooltipTexts } from '../data/tooltipTexts'
import { onboarding } from '../utils/onboarding'
import { substituteTaskTotal } from '../lib/textFormat'
import { OFFICIAL_TASK_COUNT } from '../lib/officialFilter'
import { resolveBuildProvenance } from '../lib/buildProvenance'
import {
  getDashboardDisplayData,
} from '../lib/officialExperimentScope.js'

type TabKey = 'leaderboard' | 'trend' | 'errors' | 'grading'

const TABS: { id: TabKey; label: string; icon: React.ReactNode; color: string }[] = [
  { id: 'leaderboard', label: 'Leaderboard', icon: <BarChart3 className="w-4 h-4" />, color: '#10b981' },
  { id: 'trend', label: 'Trends', icon: <TrendingUp className="w-4 h-4" />, color: '#3b82f6' },
  { id: 'errors', label: 'Execution Errors', icon: <AlertTriangle className="w-4 h-4" />, color: '#ef4444' },
  { id: 'grading', label: 'Grading Analysis', icon: <Award className="w-4 h-4" />, color: '#f59e0b' },
]

const BUILD_PROVENANCE = resolveBuildProvenance({
  version: __APP_VERSION__,
  sha: import.meta.env.VITE_BUILD_SHA,
  repository: import.meta.env.VITE_BUILD_REPOSITORY,
})

export default function Dashboard() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // `?debug=1` reveals demo/smoke/subset entries hidden in the default view.
  // Display toggle only (not access control) — these reports are not sensitive.
  const debug = searchParams.get('debug') === '1'
  const { reports, experiments, sectorMatrix, generated, loading, error } = useReports()
  const { isDark, toggle: toggleTheme } = useTheme()
  const [activeTab, setActiveTab] = useState<TabKey>('leaderboard')
  const [demoMode, setDemoMode] = useState(false)
  const [aboutOpen, setAboutOpen] = useState(false)

  // Auto-open AboutModal on first visit
  useEffect(() => {
    if (!onboarding.isAboutSeen()) {
      setAboutOpen(true)
    }
  }, [])

  // Parse "138m 37s" → seconds for sorting
  const parseDuration = (d: string) => {
    const m = d.match(/(\d+)m/)
    const s = d.match(/(\d+)s/)
    return (m ? parseInt(m[1]) * 60 : 0) + (s ? parseInt(s[1]) : 0)
  }

  // Scope experiments and report narratives/errors together, then sort.
  const displayData = useMemo(() => {
    const scoped = getDashboardDisplayData(
      experiments,
      reports,
      { debug, demoMode },
    )
    scoped.experiments.sort((a, b) => {
      const dateDiff = new Date(b.date).getTime() - new Date(a.date).getTime()
      if (dateDiff !== 0) return dateDiff
      return parseDuration(b.duration) - parseDuration(a.duration)
    })
    return scoped
  }, [experiments, reports, demoMode, debug])
  const displayExperiments = displayData.experiments
  const displayReports = displayData.reports

  if (loading) {
    return (
      <div className="min-h-screen bg-dash-page flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-2 border-dash-text-faint border-t-dash-heading rounded-full animate-spin mb-4" />
          <p className="text-dash-text-secondary">Loading experiments...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-dash-page flex items-center justify-center">
        <div className="text-center text-red-400">
          <p className="font-semibold mb-2">Error loading reports</p>
          <p className="text-sm text-red-300">{error}</p>
        </div>
      </div>
    )
  }

  // Calculate KPIs
  const bestRate = displayExperiments.length > 0 ? Math.max(...displayExperiments.map((e) => e.success_rate_pct)) : 0
  // "Best" over the runs that measured a score. A run whose tasks all errored
  // carries null, and `Math.max` reads a null as 0 — harmless for the maximum
  // itself, but it means a board with nothing but unmeasured runs would announce
  // a best score of 0.00 rather than admitting it has none. When at least one
  // run measured something this is the same maximum it always was.
  const measuredQaScores = displayExperiments
    .map((e) => e.avg_qa_score)
    .filter((v): v is number => v != null)
  const bestQA = measuredQaScores.length > 0 ? Math.max(...measuredQaScores) : null
  // Keep global benchmark copy stable even when debug mode reveals subsets.
  const totalTasks = OFFICIAL_TASK_COUNT

  const handleSelectExperiment = (shortId: string) => {
    navigate(`/experiments/${shortId}`)
  }

  return (
    <motion.div
      className="min-h-screen bg-dash-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <motion.header
        className="border-b border-dash-border bg-dash-card/80 backdrop-blur-sm sticky top-0 z-40"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-3 md:py-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 md:gap-4 min-w-0">
            <h1 className="text-base md:text-2xl font-bold text-dash-heading truncate">GDPVal RealWorks</h1>
            {displayReports.length > 0 && <ScopeBadge scope={displayReports[0].meta.report_scope} />}
          </div>
          <div className="flex items-center gap-1.5 md:gap-3 flex-shrink-0">
            <button
              onClick={() => navigate('/notes')}
              className="inline-flex items-center justify-center md:justify-start gap-1.5 w-8 h-8 md:w-auto md:h-9 md:px-3 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-colors"
              title="RealWorks Field Notes"
            >
              <BookOpen className="w-4 h-4" />
              <span className="text-xs hidden lg:inline">Notes</span>
            </button>
            {/* About / Help */}
            <button
              onClick={() => setAboutOpen(true)}
              className="inline-flex items-center justify-center w-8 h-8 md:w-9 md:h-9 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-all hover:scale-105"
              title="About this dashboard"
            >
              <HelpCircle className="w-4 h-4" />
            </button>
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="inline-flex items-center justify-center w-8 h-8 md:w-9 md:h-9 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-all hover:scale-105"
              title={isDark ? '라이트 모드' : '다크 모드'}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setDemoMode(!demoMode)}
              className="inline-flex items-center gap-1.5 md:gap-2 px-2 md:px-3 py-1.5 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-sm text-dash-text-secondary transition-colors"
            >
              {demoMode ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              <span className="text-xs hidden sm:inline">{demoMode ? 'Demo' : 'Full'}</span>
            </button>
            <a
              href="https://github.com/hyeonsangjeon/gdpval-realworks"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 md:gap-2 px-2 md:px-3 py-1.5 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-colors"
            >
              <Github className="w-4 h-4" />
              <span className="text-xs hidden sm:inline">GitHub</span>
            </a>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-4 md:py-8">
        {/* Hero KPIs */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-4 mb-6 md:mb-8"
        >
          {[
            {
              label: 'Best Self-QA',
              value: bestQA == null ? '—' : bestQA.toFixed(2),
              unit: 'out of 10',
              tooltip: tooltipTexts.kpi.bestQaScore,
              valueColor: 'text-amber-400',
              accentColor: '#f59e0b',
              tooltipDir: 'right' as const,
            },
            {
              label: 'Best Success Rate',
              value: `${bestRate.toFixed(1)}%`,
              unit: `of ${totalTasks} tasks`,
              tooltip: tooltipTexts.kpi.bestSuccessRate,
              valueColor: 'text-emerald-400',
              accentColor: '#10b981',
              tooltipDir: 'right' as const,
            },
            {
              label: 'Experiments',
              value: displayExperiments.length,
              unit: 'total',
              tooltip: substituteTaskTotal(tooltipTexts.kpi.experiments, totalTasks),
              valueColor: 'text-dash-heading',
              accentColor: '#3b82f6',
              tooltipDir: 'right' as const,
            },
            {
              label: 'Tasks Evaluated',
              value: displayExperiments.length > 0 ? totalTasks : 0,
              unit: 'per experiment',
              tooltip: tooltipTexts.kpi.tasksEvaluated,
              valueColor: 'text-dash-heading',
              accentColor: '#8b5cf6',
              tooltipDir: 'left' as const,
            },
          ].map((kpi, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ y: -2 }}
              transition={{ delay: idx * 0.05, type: 'spring', stiffness: 400, damping: 25 }}
              className="relative rounded-xl bg-dash-card border border-dash-border p-3 md:p-5 transition-shadow duration-200"
              style={{
                boxShadow: isDark
                  ? '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)'
                  : '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.04)',
              }}
            >
              {/* Accent bar */}
              <div
                className="absolute right-0 top-0 bottom-0 w-1 rounded-r-xl"
                style={{ backgroundColor: kpi.accentColor, opacity: 0.6 }}
              />
              <p className="text-[10px] md:text-xs font-semibold text-dash-text-muted uppercase tracking-wider mb-1 md:mb-2 flex items-center gap-1">
                {kpi.label}
                <InfoTooltip content={kpi.tooltip} position={kpi.tooltipDir} />
              </p>
              <p className={`text-lg md:text-2xl font-semibold font-mono mb-1 ${kpi.valueColor}`}>
                {typeof kpi.value === 'number' ? kpi.value : kpi.value}
              </p>
              <p className="text-xs text-dash-text-faint">{kpi.unit}</p>
            </motion.div>
          ))}
        </motion.div>

        {/* Tabs */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="mb-6"
        >
          <div className="flex gap-1.5 md:gap-2 border-b border-dash-border pb-0 overflow-x-auto scrollbar-hide -mx-3 px-3 md:mx-0 md:px-0">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative inline-flex items-center gap-1.5 md:gap-2 px-2.5 md:px-4 py-2 md:py-2.5 rounded-t-lg transition-all whitespace-nowrap flex-shrink-0 ${
                  activeTab === tab.id
                    ? 'text-dash-heading bg-dash-card/50'
                    : 'text-dash-text-muted hover:text-dash-text hover:bg-dash-card/20'
                }`}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{
                    backgroundColor: tab.color,
                    opacity: activeTab === tab.id ? 1 : 0.4,
                  }}
                />
                {tab.icon}
                <span className="text-xs md:text-sm font-medium">{tab.label}</span>
                {activeTab === tab.id && (
                  <motion.div
                    layoutId="tab-accent"
                    className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
                    style={{ backgroundColor: tab.color }}
                    transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                  />
                )}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Tab Content — sunken wrapper for depth */}
        <div
          className="rounded-xl p-3 md:p-4 -mt-1"
          style={{
            background: isDark ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.02)',
            boxShadow: isDark
              ? 'inset 0 2px 6px rgba(0,0,0,0.25)'
              : 'inset 0 1px 4px rgba(0,0,0,0.06)',
          }}
        >
          {activeTab === 'leaderboard' && (
              <LeaderboardView
                experiments={displayExperiments}
                sectorMatrix={sectorMatrix}
                onSelectExperiment={handleSelectExperiment}
                totalTasks={totalTasks}
              />
            )}
            {activeTab === 'trend' && <TrendView experiments={displayExperiments} />}
            {activeTab === 'errors' && <ErrorAnalysisView experiments={displayExperiments} reports={displayReports} />}
            {activeTab === 'grading' && <GradingAnalysisView debug={debug} />}
        </div>
      </div>

      {/* Footer */}
      <motion.footer
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="border-t border-dash-border bg-dash-card/50 mt-16"
      >
        <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-4 md:py-6 flex flex-col md:flex-row items-center justify-between gap-1 text-xs text-dash-text-faint">
          {generated ? (
            <p aria-label="Dashboard data generation time">
              Data generated {new Date(generated).toLocaleString()}
            </p>
          ) : <span />}
          {BUILD_PROVENANCE.kind === 'published' ? (
            <a
              href={BUILD_PROVENANCE.commitUrl}
              aria-label={BUILD_PROVENANCE.accessibleLabel}
              title={BUILD_PROVENANCE.accessibleLabel}
              data-build-provenance="published"
              className="max-w-full rounded-sm text-center font-mono text-[11px] text-dash-text-secondary hover:text-dash-heading transition-colors"
            >
              {BUILD_PROVENANCE.displayLabel}
            </a>
          ) : (
            <span
              aria-label={BUILD_PROVENANCE.accessibleLabel}
              data-build-provenance="local"
              className="max-w-full text-center font-mono text-[11px] text-dash-text-secondary"
            >
              {BUILD_PROVENANCE.displayLabel}
            </span>
          )}
        </div>
      </motion.footer>

      {/* About Modal */}
      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} totalTasks={totalTasks} />
    </motion.div>
  )
}
