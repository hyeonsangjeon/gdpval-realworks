import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Sparkles } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'

interface WowCardProps {
  title: string
  value: string
  sub?: string
  tooltip?: string
  icon?: ReactNode
  children?: ReactNode
  delay?: number
}

export default function WowCard({
  title,
  value,
  sub,
  tooltip,
  icon,
  children,
  delay = 0,
}: WowCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
    >
      <Card className="bg-card/50 backdrop-blur border-border h-full relative overflow-hidden">
        <CardContent className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              {icon}
              <span className="text-xs font-semibold tracking-wide text-foreground">
                {title}
              </span>
              {tooltip && <InfoTooltip content={tooltip} position="top" />}
            </div>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-gradient-to-r from-fuchsia-500/15 to-violet-500/15 border border-fuchsia-400/30 text-[10px] font-bold uppercase tracking-wider text-fuchsia-400">
              <Sparkles className="w-2.5 h-2.5" />
              WOW
            </span>
          </div>
          <p className="text-3xl font-bold text-foreground leading-none">
            {value}
          </p>
          {sub && (
            <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
              {sub}
            </p>
          )}
          {children && <div className="mt-4">{children}</div>}
        </CardContent>
      </Card>
    </motion.div>
  )
}

export function WowEmptyState({ title, tooltip }: { title: string; tooltip?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <Card className="bg-card/30 backdrop-blur border-border border-dashed h-full">
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-semibold tracking-wide text-muted-foreground">
              {title}
            </span>
            {tooltip && <InfoTooltip content={tooltip} position="top" />}
          </div>
          <p className="text-sm text-muted-foreground italic">
            Data not available
          </p>
          <p className="text-[11px] text-muted-foreground/70 mt-1">
            Populates after a full-scale grading run.
          </p>
        </CardContent>
      </Card>
    </motion.div>
  )
}
