import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'

interface Condition {
  name: string
  prompt: string
  win_rate: number
}

interface ComparisonViewProps {
  conditionA: Condition
  conditionB: Condition
  delta: number
}

function ComparisonView({ conditionA, conditionB, delta }: ComparisonViewProps) {
  const isPositive = delta > 0

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Condition A */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Card className="h-full bg-card/50 backdrop-blur border-border">
          <CardHeader>
            <CardTitle className="text-lg">
              <span className="text-muted-foreground">Condition A: </span>
              {conditionA.name}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-muted-foreground mb-2">Prompt</p>
                <p className="text-sm text-foreground bg-muted/30 p-3 rounded-md border border-border">
                  {conditionA.prompt}
                </p>
              </div>

              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <p className="text-sm text-muted-foreground">Win Rate</p>
                  <p className="text-3xl font-bold font-mono text-foreground">
                    {conditionA.win_rate}%
                  </p>
                </div>
                <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-blue-500 to-blue-600"
                    initial={{ width: 0 }}
                    animate={{ width: `${conditionA.win_rate}%` }}
                    transition={{ duration: 1, delay: 0.2, ease: 'easeOut' }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* VS Divider - Desktop: absolute, Mobile: centered */}
      <div className="flex md:hidden justify-center -my-3 z-10">
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="bg-primary text-primary-foreground rounded-full w-10 h-10 flex items-center justify-center font-bold text-xs shadow-lg"
        >
          VS
        </motion.div>
      </div>
      <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 items-center justify-center z-10">
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="bg-primary text-primary-foreground rounded-full w-12 h-12 flex items-center justify-center font-bold text-sm shadow-lg"
        >
          VS
        </motion.div>
      </div>

      {/* Condition B */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Card className="h-full bg-card/50 backdrop-blur border-border">
          <CardHeader>
            <CardTitle className="text-lg">
              <span className="text-muted-foreground">Condition B: </span>
              {conditionB.name}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-muted-foreground mb-2">Prompt</p>
                <p className="text-sm text-foreground bg-muted/30 p-3 rounded-md border border-border">
                  {conditionB.prompt}
                </p>
              </div>

              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <p className="text-sm text-muted-foreground">Win Rate</p>
                  <div className="flex items-baseline gap-2">
                    <p className="text-3xl font-bold font-mono text-foreground">
                      {conditionB.win_rate}%
                    </p>
                    <span
                      className={`text-sm font-semibold ${
                        isPositive ? 'text-green-500' : 'text-red-500'
                      }`}
                    >
                      ({isPositive ? '+' : ''}{delta}%p)
                    </span>
                  </div>
                </div>
                <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
                  <motion.div
                    className={`h-full ${
                      isPositive
                        ? 'bg-gradient-to-r from-green-500 to-green-600'
                        : 'bg-gradient-to-r from-red-500 to-red-600'
                    }`}
                    initial={{ width: 0 }}
                    animate={{ width: `${conditionB.win_rate}%` }}
                    transition={{ duration: 1, delay: 0.2, ease: 'easeOut' }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}

export default ComparisonView
