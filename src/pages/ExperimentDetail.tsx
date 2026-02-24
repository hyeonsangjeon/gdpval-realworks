import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import Header from '../components/Header'
import ComparisonView from '../components/ComparisonView'
import IndustryBreakdown from '../components/IndustryBreakdown'
import AnalysisCard from '../components/AnalysisCard'
import { useExperiments } from '../hooks/useExperiments'

function ExperimentDetail() {
  const { id } = useParams()
  const { experiments, loading, error } = useExperiments()
  const experiment = experiments.find((exp) => exp.id === id)

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

  if (error) {
    return (
      <motion.div
        className="min-h-screen bg-background"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Header />
        <div className="container mx-auto px-4 py-8 text-center text-red-500">Error: {error}</div>
      </motion.div>
    )
  }

  if (!experiment) {
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
          <Link to="/experiments" className="text-primary hover:underline inline-flex items-center gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
          <p className="mt-8 text-muted-foreground">Experiment not found</p>
        </div>
      </motion.div>
    )
  }

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
            to="/experiments"
            className="text-primary hover:underline inline-flex items-center gap-2 mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
        </motion.div>

        {/* Title */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="mb-6 md:mb-8"
        >
          <h1 className="text-2xl md:text-4xl font-bold text-foreground">{experiment.name}</h1>
          <p className="mt-2 text-sm md:text-base text-muted-foreground">
            {experiment.model} • {experiment.tasks} tasks
          </p>
        </motion.div>

        {/* Controlled Variables */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="mb-8"
        >
          <Card className="bg-card/50 backdrop-blur border-border">
            <CardHeader>
              <CardTitle>Controlled Variables</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-muted-foreground">
                    Fixed: <span className="text-foreground">Model ({experiment.model}), Tasks ({experiment.tasks})</span>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-red-500" />
                  <span className="text-sm text-muted-foreground">
                    Changed: <span className="text-foreground">{experiment.changed_variable || 'Prompt Strategy'}</span>
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Comparison View */}
        <div className="mb-8 relative">
          <ComparisonView
            conditionA={experiment.condition_a}
            conditionB={experiment.condition_b}
            delta={experiment.delta}
          />
        </div>

        {/* Industry Breakdown */}
        <div className="mb-8">
          <IndustryBreakdown breakdown={experiment.industry_breakdown} />
        </div>

        {/* AI Analysis */}
        <div className="mb-8">
          <AnalysisCard analysis={experiment.analysis} />
        </div>
      </div>
    </motion.div>
  )
}

export default ExperimentDetail
