import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Github, Eye, EyeOff, BarChart3, TrendingUp, AlertTriangle, Award, Sun, Moon } from 'lucide-react'
import ScopeBadge from '../components/ScopeBadge'
import LeaderboardView from '../components/dashboard/LeaderboardView'
import TrendView from '../components/dashboard/TrendView'
import ErrorAnalysisView from '../components/dashboard/ErrorAnalysisView'
import GradingAnalysisView from '../components/dashboard/GradingAnalysisView'
import { useReports } from '../hooks/useReports'
import { useTheme } from '../contexts/ThemeContext'

type TabKey = 'leaderboard' | 'trend' | 'errors' | 'grading'

const TABS: { id: TabKey; label: string; icon: React.ReactNode }[] = [
  { id: 'leaderboard', label: 'Leaderboard', icon: <BarChart3 className="w-4 h-4" /> },
  { id: 'trend', label: 'Trends', icon: <TrendingUp className="w-4 h-4" /> },
  { id: 'errors', label: 'Execution Errors', icon: <AlertTriangle className="w-4 h-4" /> },
  { id: 'grading', label: 'Grading Analysis', icon: <Award className="w-4 h-4" /> },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const { reports, experiments, sectorMatrix, generated, loading, error } = useReports()
  const { isDark, toggle: toggleTheme } = useTheme()
  const [activeTab, setActiveTab] = useState<TabKey>('leaderboard')
  const [demoMode, setDemoMode] = useState(false)

  const displayReports = demoMode ? reports.filter((r) => r.meta.report_scope === 'self_assessed_pre_grading') : reports
  const displayExperiments = demoMode
    ? experiments.filter((e) => e.report_scope === 'self_assessed_pre_grading')
    : experiments

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
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-dash-heading">GDPVal RealWorks</h1>
            {displayReports.length > 0 && <ScopeBadge scope={displayReports[0].meta.report_scope} />}
          </div>
          <div className="flex items-center gap-3">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-all hover:scale-105"
              title={isDark ? '라이트 모드' : '다크 모드'}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setDemoMode(!demoMode)}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-sm text-dash-text-secondary transition-colors"
            >
              {demoMode ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              <span className="text-xs">{demoMode ? 'Demo' : 'Full'}</span>
            </button>
            <a
              href="https://github.com/hyeonsangjeon/gdpval-realworks"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-colors"
            >
              <Github className="w-4 h-4" />
              <span className="text-xs">GitHub</span>
            </a>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <div className="max-w-[1400px] mx-auto px-6 py-8">
        {/* Hero KPIs */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8"
        >
          {[
            {
              label: 'Best Success Rate',
              value: `${bestRate.toFixed(1)}%`,
              unit: 'of 220 tasks',
            },
            {
              label: 'Experiments',
              value: displayExperiments.length,
              unit: 'total',
            },
            {
              label: 'Tasks Evaluated',
              value: displayExperiments.length > 0 ? displayExperiments[0].total_tasks : 0,
              unit: 'per experiment',
            },
            {
              label: 'Best QA Score',
              value: bestQA.toFixed(2),
              unit: 'out of 10',
            },
          ].map((kpi, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="rounded-xl bg-dash-card border border-dash-border p-5"
            >
              <p className="text-xs font-semibold text-dash-text-muted uppercase tracking-wider mb-2">{kpi.label}</p>
              <p className="text-2xl font-semibold text-dash-heading font-mono mb-1">
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
          <div className="flex gap-2 border-b border-dash-border pb-4">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${
                  activeTab === tab.id
                    ? 'border-dash-border bg-dash-card-active text-dash-heading'
                    : 'border-transparent text-dash-text-muted hover:text-dash-text'
                }`}
              >
                {tab.icon}
                <span className="text-sm font-medium">{tab.label}</span>
              </button>
            ))}
          </div>
        </motion.div>

        {/* Tab Content */}
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

      {/* Footer */}
      <motion.footer
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="border-t border-dash-border bg-dash-card/50 mt-16"
      >
        <div className="max-w-[1400px] mx-auto px-6 py-6 flex items-center justify-between text-xs text-dash-text-faint">
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
    </motion.div>
  )
}
