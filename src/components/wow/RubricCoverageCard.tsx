import { Layers } from 'lucide-react'
import WowCard from './WowCard'
import type { WowSummary } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'
import { RUBRIC_ITEMS_DESCRIBED, readWowRate } from './rateReading'

interface Props {
  wow: WowSummary
  totalItems?: number
  delay?: number
}

export default function RubricCoverageCard({ wow, totalItems, delay = 0 }: Props) {
  // `totalItems` is counted off the task rows and is not this rate's
  // denominator — the producer leaves `score_excluded` items out of the
  // average — which is why the prose says `~`. `item_counts.rubric_items` is
  // the denominator, and without it a headline of `0.0%` is indistinguishable
  // from a run that averaged over nothing.
  const reading = readWowRate(
    wow.rubric_item_coverage_avg,
    wow.item_counts?.rubric_items,
    RUBRIC_ITEMS_DESCRIBED,
  )
  const itemsLabel = totalItems && totalItems > 0
    ? ` across ~${totalItems.toLocaleString()} items`
    : ''
  const claim = "OpenAI's task-level binary captures only {0, 33, 67, 100}%."
  const sub = reading.fraction === null
    ? `${claim} We score every rubric item. ${reading.caveat}`
    : reading.caveat
      ? `${claim} We score every rubric item — averaging ${reading.value}${itemsLabel}. ${reading.caveat}`
      : `${claim} We score every rubric item — averaging ${reading.value}${itemsLabel}.`
  return (
    <WowCard
      title="Rubric Item Coverage"
      value={reading.value}
      sub={sub}
      tooltip={tooltipTexts.wow.rubricCoverage}
      icon={<Layers className="w-4 h-4 text-fuchsia-400" />}
      delay={delay}
    />
  )
}
