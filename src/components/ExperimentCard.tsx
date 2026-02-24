import { motion } from 'framer-motion'
import { Card, CardContent } from './ui/card'
import { ArrowRight, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  'Finance and Insurance': { bg: 'bg-blue-500/10', text: 'text-blue-500' },
  'Government': { bg: 'bg-purple-500/10', text: 'text-purple-500' },
  'Health Care and Social Assistance': { bg: 'bg-emerald-500/10', text: 'text-emerald-500' },
  'Information': { bg: 'bg-orange-500/10', text: 'text-orange-500' },
  'Manufacturing': { bg: 'bg-yellow-500/10', text: 'text-yellow-500' },
  'Professional, Scientific, and Technical Services': { bg: 'bg-cyan-500/10', text: 'text-cyan-500' },
  'Real Estate and Rental and Leasing': { bg: 'bg-pink-500/10', text: 'text-pink-500' },
  'Retail Trade': { bg: 'bg-indigo-500/10', text: 'text-indigo-500' },
  'Wholesale Trade': { bg: 'bg-teal-500/10', text: 'text-teal-500' },
}

interface Experiment {
  id: string
  is_dummy?: boolean
  name: string
  model: string
  tasks: number
  condition_a: {
    name: string
    win_rate: number
  }
  condition_b: {
    name: string
    win_rate: number
  }
  delta: number
  industry_breakdown: Record<string, number>
}

interface ExperimentCardProps {
  experiment: Experiment
  index: number
  highlightCategory?: string
}

function ExperimentCard({ experiment, index, highlightCategory }: ExperimentCardProps) {
  const navigate = useNavigate()
  const categories = Object.keys(experiment.industry_breakdown || {})

  // When a category is selected, use that category's delta
  const displayDelta = highlightCategory
    ? experiment.industry_breakdown[highlightCategory] ?? experiment.delta
    : experiment.delta
  const isPositive = displayDelta > 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      whileHover={{
        scale: 1.01,
        boxShadow: isPositive
          ? '0 0 30px rgba(34, 197, 94, 0.2)'
          : '0 0 30px rgba(239, 68, 68, 0.2)',
      }}
      onClick={() => navigate(`/experiments/${experiment.id}`)}
      className="cursor-pointer"
    >
      <Card className="bg-card/50 backdrop-blur border-border hover:border-primary/50 transition-all duration-300 relative overflow-hidden">
        {experiment.is_dummy && (
          <div className="flex items-center gap-1.5 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[11px] font-medium px-3 py-1.5 border-b border-amber-500/20">
            <AlertTriangle className="h-3 w-3 flex-shrink-0" />
            ⏳ We're still waiting for experiment & grading results. This takes a while.
          </div>
        )}
        <CardContent className="p-4 md:p-6">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-base md:text-lg font-semibold text-foreground">{experiment.name}</h3>
                <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              </div>

              <div className="flex items-center gap-2 md:gap-4 text-xs md:text-sm text-muted-foreground mb-3">
                <span className="font-medium text-primary">{experiment.model}</span>
                <span>•</span>
                <span>{experiment.tasks} tasks</span>
              </div>

              {/* Category Tags */}
              {categories.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {categories.map((cat) => {
                    const color = CATEGORY_COLORS[cat] || { bg: 'bg-gray-500/10', text: 'text-gray-500' }
                    const delta = experiment.industry_breakdown[cat]
                    const isHighlighted = highlightCategory === cat
                    return (
                      <span
                        key={cat}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium transition-all duration-200 ${
                          isHighlighted
                            ? `${color.text} ring-2 ring-current ${color.bg} scale-105`
                            : highlightCategory
                            ? `${color.bg} ${color.text} opacity-40`
                            : `${color.bg} ${color.text}`
                        }`}
                      >
                        {cat}
                        <span className="font-mono font-semibold">
                          {delta > 0 ? '+' : ''}{delta}%p
                        </span>
                      </span>
                    )
                  })}
                </div>
              )}

              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                <div className="text-xs md:text-sm">
                  <span className="text-muted-foreground">Win Rate: </span>
                  <span className="font-mono font-medium text-foreground">
                    {experiment.condition_a.win_rate}%
                  </span>
                  <span className="text-muted-foreground mx-2">→</span>
                  <span className="font-mono font-medium text-foreground">
                    {experiment.condition_b.win_rate}%
                  </span>
                </div>

                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md font-mono text-xs md:text-sm font-semibold w-fit ${
                    isPositive
                      ? 'bg-green-500/10 text-green-500'
                      : 'bg-red-500/10 text-red-500'
                  }`}
                >
                  {isPositive ? (
                    <TrendingUp className="h-3 w-3 md:h-4 md:w-4" />
                  ) : (
                    <TrendingDown className="h-3 w-3 md:h-4 md:w-4" />
                  )}
                  {isPositive ? '+' : ''}
                  {displayDelta}%p
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default ExperimentCard
