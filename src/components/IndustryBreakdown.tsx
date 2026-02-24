import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const SHORT_LABELS: Record<string, string> = {
  'Finance and Insurance': 'Finance & Insurance',
  'Government': 'Government',
  'Health Care and Social Assistance': 'Health Care',
  'Information': 'Information',
  'Manufacturing': 'Manufacturing',
  'Professional, Scientific, and Technical Services': 'Prof. & Tech. Services',
  'Real Estate and Rental and Leasing': 'Real Estate',
  'Retail Trade': 'Retail Trade',
  'Wholesale Trade': 'Wholesale Trade',
}

interface IndustryBreakdownProps {
  breakdown: {
    [key: string]: number
  }
}

function IndustryBreakdown({ breakdown }: IndustryBreakdownProps) {
  // Transform data for Recharts
  const data = Object.entries(breakdown).map(([industry, delta]) => ({
    industry,
    shortLabel: SHORT_LABELS[industry] ?? industry,
    delta,
    isPositive: delta >= 0,
  }))

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.3 }}
    >
      <Card className="bg-card/50 backdrop-blur border-border">
        <CardHeader>
          <CardTitle>Industry Breakdown</CardTitle>
          <p className="text-sm text-muted-foreground">Win rate change by industry</p>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={Math.max(300, data.length * 44)}>
            <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                type="number"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: 'hsl(var(--muted-foreground))' }}
                label={{ value: 'Δ Win Rate (%p)', position: 'insideBottom', offset: -10, fill: 'hsl(var(--muted-foreground))' }}
              />
              <YAxis
                type="category"
                dataKey="shortLabel"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fill: 'hsl(var(--foreground))', fontSize: 12 }}
                width={170}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'hsl(var(--foreground))' }}
                formatter={(value: number) => [`${value > 0 ? '+' : ''}${value}%p`, 'Δ Win Rate']}
                labelFormatter={(label) => {
                  const entry = data.find(d => d.shortLabel === label)
                  return entry?.industry ?? label
                }}
                cursor={{ fill: 'hsl(var(--muted))' }}
              />
              <Bar dataKey="delta" radius={[0, 8, 8, 0]}>
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.isPositive ? 'hsl(142, 71%, 45%)' : 'hsl(0, 84%, 60%)'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="mt-4 flex items-center justify-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-green-500" />
              <span className="text-muted-foreground">Positive Δ</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-red-500" />
              <span className="text-muted-foreground">Negative Δ</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default IndustryBreakdown
