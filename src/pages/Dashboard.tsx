import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FlaskConical, TrendingUp, CheckCircle, Filter } from 'lucide-react'
import Header from '../components/Header'
import StatsCard from '../components/StatsCard'
import ExperimentCard from '../components/ExperimentCard'
import GradesSummary from '../components/GradesSummary'
import { useExperiments } from '../hooks/useExperiments'
import { useGrades } from '../hooks/useGrades'

const CATEGORIES = ['All', 'Finance', 'Legal', 'Healthcare', 'Software Engineering'] as const
type Category = (typeof CATEGORIES)[number]

const CATEGORY_STYLE: Record<string, { active: string; inactive: string }> = {
  All: { active: 'bg-primary text-primary-foreground', inactive: 'bg-muted text-muted-foreground hover:bg-muted/80' },
  Finance: { active: 'bg-blue-500 text-white', inactive: 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20' },
  Legal: { active: 'bg-purple-500 text-white', inactive: 'bg-purple-500/10 text-purple-500 hover:bg-purple-500/20' },
  Healthcare: { active: 'bg-emerald-500 text-white', inactive: 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20' },
  'Software Engineering': { active: 'bg-orange-500 text-white', inactive: 'bg-orange-500/10 text-orange-500 hover:bg-orange-500/20' },
}

function Dashboard() {
  const { experiments, loading, error } = useExperiments()
  const { grades } = useGrades()
  const [selectedCategory, setSelectedCategory] = useState<Category>('All')

  // Calculate stats based on filter
  const isFiltered = selectedCategory !== 'All'
  const totalExperiments = experiments.length

  const avgDelta = isFiltered
    ? (
        experiments.reduce((sum, exp) => sum + (exp.industry_breakdown[selectedCategory] || 0), 0) /
        experiments.length
      ).toFixed(1)
    : (experiments.reduce((sum, exp) => sum + exp.delta, 0) / experiments.length).toFixed(1)

  const totalTasks = isFiltered ? `${selectedCategory}` : '220'

  return (
    <motion.div
      className="min-h-screen bg-background"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Header />

      {loading && (
        <div className="container mx-auto px-4 py-8 text-center text-muted-foreground">Loading experiments...</div>
      )}
      {error && (
        <div className="container mx-auto px-4 py-8 text-center text-red-500">Error: {error}</div>
      )}

      {!loading && !error && <div className="container mx-auto px-4 py-8">
        {/* Category Filter */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="mb-6"
        >
          <div className="flex items-center gap-2 mb-3">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium text-muted-foreground">Filter by Category</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => {
              const isActive = selectedCategory === cat
              const style = CATEGORY_STYLE[cat]
              return (
                <motion.button
                  key={cat}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                    isActive ? style.active : style.inactive
                  }`}
                >
                  {cat === 'All' ? 'All (220 tasks)' : cat}
                </motion.button>
              )
            })}
          </div>
        </motion.div>

        {/* Stats Cards */}
        <AnimatePresence mode="wait">
          <motion.div
            key={selectedCategory}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
          >
            <StatsCard
              title="Total Experiments"
              value={totalExperiments}
              icon={FlaskConical}
              description="Benchmark comparisons"
              delay={0}
            />
            <StatsCard
              title={isFiltered ? `Avg Δ (${selectedCategory})` : 'Average Δ Win Rate'}
              value={`+${avgDelta}%p`}
              icon={TrendingUp}
              description={isFiltered ? `${selectedCategory} category only` : 'Across all experiments'}
              delay={0.1}
            />
            <StatsCard
              title="Scope"
              value={totalTasks}
              icon={CheckCircle}
              description={isFiltered ? 'Filtered category' : 'GDPVal benchmark (all tasks)'}
              delay={0.2}
            />
          </motion.div>
        </AnimatePresence>

        {/* Experiments List */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground mb-4">
            Experiments
            {isFiltered && (
              <span className="text-base font-normal text-muted-foreground ml-2">
                — {selectedCategory} results
              </span>
            )}
          </h2>
          {experiments.map((experiment, index) => (
            <ExperimentCard
              key={experiment.id}
              experiment={experiment}
              index={index}
              highlightCategory={isFiltered ? selectedCategory : undefined}
            />
          ))}
        </div>

        {/* Grading Results */}
        {grades.length > 0 && (
          <div className="mt-10">
            <GradesSummary grades={grades} />
          </div>
        )}
      </div>}
    </motion.div>
  )
}

export default Dashboard
