import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Sparkles } from 'lucide-react'

interface AnalysisCardProps {
  analysis: string
}

function AnalysisCard({ analysis }: AnalysisCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.4 }}
      whileHover={{
        boxShadow: '0 0 30px rgba(59, 130, 246, 0.3)',
      }}
    >
      <Card className="bg-gradient-to-br from-card/50 to-card/30 backdrop-blur border-border hover:border-primary/50 transition-all duration-300">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            AI Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <motion.p
            className="text-foreground leading-relaxed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.5 }}
          >
            {analysis}
          </motion.p>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default AnalysisCard
