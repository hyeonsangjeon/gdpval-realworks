import { Layers } from 'lucide-react'
import WowCard from './WowCard'
import type { WowSummary } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'

interface Props {
  wow: WowSummary
  totalItems?: number
  delay?: number
}

export default function RubricCoverageCard({ wow, totalItems, delay = 0 }: Props) {
  const coverage = wow.rubric_item_coverage_avg
  const pct = (coverage * 100).toFixed(1)
  const itemsLabel = totalItems && totalItems > 0
    ? ` across ~${totalItems.toLocaleString()} items`
    : ''
  return (
    <WowCard
      title="Rubric Item Coverage"
      value={`${pct}%`}
      sub={`OpenAI's task-level binary captures only {0, 33, 67, 100}%. We score every rubric item — averaging ${pct}%${itemsLabel}.`}
      tooltip={tooltipTexts.wow.rubricCoverage}
      icon={<Layers className="w-4 h-4 text-fuchsia-400" />}
      delay={delay}
    />
  )
}
