import { ShieldAlert } from 'lucide-react'
import WowCard from './WowCard'
import type { WowSummary } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'

interface Props {
  wow: WowSummary
  delay?: number
}

export default function CriticalItemCard({ wow, delay = 0 }: Props) {
  const pct = (wow.critical_item_pass_rate * 100).toFixed(1)
  return (
    <WowCard
      title="Critical Items (weight ≥ 3)"
      value={`${pct}%`}
      sub='Pass rate for high-weight rubric items — the "must-have" requirements.'
      tooltip={tooltipTexts.wow.criticalItems}
      icon={<ShieldAlert className="w-4 h-4 text-amber-400" />}
      delay={delay}
    />
  )
}
