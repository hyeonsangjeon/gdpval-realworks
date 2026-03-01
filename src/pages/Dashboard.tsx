import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Github, Eye, EyeOff, BarChart3, TrendingUp, AlertTriangle, Award, Sun, Moon, HelpCircle } from 'lucide-react'
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

type TabKey = 'leaderboard' | 'trend' | 'errors' | 'grading'

const TABS: { id: TabKey; label: string; icon: React.ReactNode; color: string }[] = [
  { id: 'leaderboard', label: 'Leaderboard', icon: <BarChart3 className="w-4 h-4" />, color: '#10b981' },
  { id: 'trend', label: 'Trends', icon: <TrendingUp className="w-4 h-4" />, color: '#3b82f6' },
  { id: 'errors', label: 'Execution Errors', icon: <AlertTriangle className="w-4 h-4" />, color: '#ef4444' },
  { id: 'grading', label: 'Grading Analysis', icon: <Award className="w-4 h-4" />, color: '#f59e0b' },
]

export default function Dashboard() {
  const navigate = useNavigate()
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

  const displayReports = demoMode ? reports.filter((r) => r.meta.report_scope === 'self_assessed_pre_grading') : reports

  // Parse "138m 37s" → seconds for sorting
  const parseDuration = (d: string) => {
    const m = d.match(/(\d+)m/)
    const s = d.match(/(\d+)s/)
    return (m ? parseInt(m[1]) * 60 : 0) + (s ? parseInt(s[1]) : 0)
  }

  // Sort: date desc → duration desc
  const displayExperiments = useMemo(() => {
    const list = demoMode
      ? experiments.filter((e) => e.report_scope === 'self_assessed_pre_grading')
      : [...experiments]
    return list.sort((a, b) => {
      const dateDiff = new Date(b.date).getTime() - new Date(a.date).getTime()
      if (dateDiff !== 0) return dateDiff
      return parseDuration(b.duration) - parseDuration(a.duration)
    })
  }, [experiments, demoMode])

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
  const bestQA = displayExperiments.length > 0 ? Math.max(...displayExperiments.map((e) => e.avg_qa_score)) : 0

  const handleSelectExperiment = (shortId: string) => {
    navigate(`/experiments/${shortId}`)
  }

  return (
    <motion.div
      className="min-h-screen bg-dash-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
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
              label: 'Best Success Rate',
              value: `${bestRate.toFixed(1)}%`,
              unit: 'of 220 tasks',
              tooltip: tooltipTexts.kpi.bestSuccessRate,
              valueColor: 'text-emerald-400',
              accentColor: '#10b981',
              tooltipDir: 'right' as const,
            },
            {
              label: 'Experiments',
              value: displayExperiments.length,
              unit: 'total',
              tooltip: tooltipTexts.kpi.experiments,
              valueColor: 'text-dash-heading',
              accentColor: '#3b82f6',
              tooltipDir: 'right' as const,
            },
            {
              label: 'Tasks Evaluated',
              value: displayExperiments.length > 0 ? displayExperiments[0].total_tasks : 0,
              unit: 'per experiment',
              tooltip: tooltipTexts.kpi.tasksEvaluated,
              valueColor: 'text-dash-heading',
              accentColor: '#8b5cf6',
              tooltipDir: 'right' as const,
            },
            {
              label: 'Best QA Score',
              value: bestQA.toFixed(2),
              unit: 'out of 10',
              tooltip: tooltipTexts.kpi.bestQaScore,
              valueColor: 'text-amber-400',
              accentColor: '#f59e0b',
              tooltipDir: 'left' as const,
            },
          ].map((kpi, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ y: -2 }}
              transition={{ delay: idx * 0.05, type: 'spring', stiffness: 400, damping: 25 }}
              className="relative rounded-xl bg-dash-card border border-dash-border p-3 md:p-5 overflow-hidden transition-shadow duration-200"
              style={{
                boxShadow: isDark
                  ? '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)'
                  : '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.04)',
              }}
            >
              {/* Accent bar */}
              <div
                className="absolute right-0 top-0 bottom-0 w-1"
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
          <AnimatePresence mode="wait">
            <div key={activeTab}>
              {activeTab === 'leaderboard' && (
                <LeaderboardView
                  experiments={displayExperiments}
                  sectorMatrix={sectorMatrix}
                  onSelectExperiment={handleSelectExperiment}
                />
              )}
              {activeTab === 'trend' && <TrendView experiments={displayExperiments} />}
              {activeTab === 'errors' && <ErrorAnalysisView experiments={displayExperiments} reports={displayReports} />}
              {activeTab === 'grading' && <GradingAnalysisView />}
            </div>
          </AnimatePresence>
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
          <div>
            {generated && (
              <p>Generated {new Date(generated).toLocaleString()}</p>
            )}
          </div>
          <a href="https://github.com/hyeonsangjeon/gdpval-realworks" className="hover:text-dash-text-secondary transition-colors">
            GDPVal RealWorks • v0.2.0
          </a>
        </div>
      </motion.footer>

      {/* About Modal */}
      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </motion.div>
  )
}
