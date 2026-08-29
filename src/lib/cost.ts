/**
 * cost — how a per-task cost receipt turns into something on screen.
 *
 * There are four things a cost cell can mean, and collapsing any two of them
 * would misreport the run:
 *
 * - `기록 없음`  no receipt exists. The run predates cost instrumentation, so
 *                nobody knows what it cost. This is NOT $0.
 * - `미확정`     a receipt exists but something went unpriced. Any amount shown
 *                is a floor (`≥`), never a total.
 * - `미채점`     the work never happened — the task was never graded, or never
 *                run. There is nothing to price.
 * - `$0.0000`   a real, recorded zero. Priced, complete, and free.
 *
 * Every amount this module produces is derived from recorded usage against a
 * pinned price table. None of it is an Azure invoice figure, which is why
 * `COST_ESTIMATE_NOTE` rides along with each one.
 */

import type {
  CostComponent,
  CostField,
  CostReceipt,
  CostStatus,
  CostSummary,
} from '../types/cost'

/** Shown beside every amount, hover or visible. Goal: no amount reads as billed. */
export const COST_ESTIMATE_NOTE = '사용량 기준 예상 비용이며 Azure 청구서 금액이 아님'

export const COST_FIELD_LABELS: Record<CostField, string> = {
  problem_solving_cost: '문제 풀이 비용',
  grading_cost: '채점 비용',
}

/**
 * What a cell is actually saying.
 *
 * `recorded` covers a genuine zero; the amount carries it. `floor` is a
 * partial receipt, whose amount is a lower bound. `unpriced` is a receipt that
 * could price nothing at all. `absent` is no receipt. `never_ran` is work that
 * did not happen.
 */
export type CostCellState =
  | 'recorded'
  | 'floor'
  | 'unpriced'
  | 'absent'
  | 'never_ran'

export interface CostCell {
  state: CostCellState
  /** What to render: an amount, or one of the four Korean state labels. */
  text: string
  /** Long-form explanation for `title=`; always carries the estimate note. */
  title: string
  /** True when `text` is money rather than a state word. */
  isAmount: boolean
}

/**
 * `not_run` reads differently per field: grading that never happened is
 * 미채점, generation that never happened is 미실행. Both are the same state.
 */
const NEVER_RAN_LABELS: Record<CostField, string> = {
  problem_solving_cost: '미실행',
  grading_cost: '미채점',
}

/**
 * The closed vocabulary the producer publishes for `components[].name`: the
 * five stages plus `retry`. No aliases — the names are fixed at the producer
 * and a synonym listed here would only hide the day one stopped matching.
 *
 * There is deliberately no `runtime` entry. Runtime fees are not model calls;
 * they arrive as `runtime_cost_usd` and are shown once, beside the components,
 * not as a row inside them.
 */
const COMPONENT_LABELS: Record<string, string> = {
  preprocessing: '전처리',
  generation: '생성',
  self_qa: 'Self-QA',
  grading: '주 채점',
  perception: '판독',
  retry: '재시도',
}

/** Human label for a component slug; unknown slugs degrade to spaced words. */
export function componentLabel(name: string): string {
  return COMPONENT_LABELS[name] ?? name.split('_').join(' ')
}

/**
 * Why a line had to be repeated. `none` never reaches a label — a first
 * attempt is shown under its own stage, not as a retry.
 */
const RETRY_KIND_LABELS: Record<string, string> = {
  semantic: '품질 재시도',
  infrastructure: '오류 재시도',
  resume: '재개',
  internal_recovery: '내부 복구',
}

/**
 * What a component row is, in full: which stage it belongs to and, when it was
 * not a first attempt, why it happened again. Two stages that each had to
 * retry are two rows both labelled 재시도, and this is what tells them apart.
 */
export function componentDetail(component: CostComponent): string {
  const stage = componentLabel(component.stage)
  if (component.retry_kind === 'none') return stage
  const reason = RETRY_KIND_LABELS[component.retry_kind] ?? component.retry_kind
  return `${stage} · ${reason}`
}

/**
 * A row is identified by its stage and retry kind, not by its label, because
 * two stages that each had to retry both display as 재시도.
 */
export function componentKey(component: CostComponent): string {
  return `${component.stage}:${component.retry_kind}`
}

/** Four decimal places, matching the existing conservative-cost readouts. */
export function formatCostUsd(value: number): string {
  return `$${value.toFixed(4)}`
}

/**
 * The amount a receipt is willing to stand behind, or null.
 *
 * Status-gated on purpose. A receipt that recorded nothing still carries a
 * zero in its money fields, and returning it here would put `$0.0000` on
 * screen for a run nobody measured.
 */
export function receiptAmount(receipt: CostReceipt): number | null {
  if (receipt.status !== 'complete' && receipt.status !== 'partial') return null
  return receipt.estimated_cost_usd ?? receipt.known_cost_usd
}

/**
 * The runtime fee, when there was one.
 *
 * The producer sums runtime rows into a `Decimal` that starts at zero, so
 * every receipt carries `runtime_cost_usd` — a task that never opened a
 * sandbox reports `0`, not absence. A line gated on presence alone would
 * therefore appear on every task in the dashboard reading `실행 환경 $0.0000`.
 *
 * It is gated on "was anything charged" instead, which is the same rule the
 * producer applies to component lines: a stage that made no call gets no line.
 * Nothing is hidden by this. A zero runtime is still inside the task total,
 * and with the line absent the component lines add up to that total exactly —
 * which is the only reason the line exists.
 */
export function runtimeLineAmount(receipt: CostReceipt): number | null {
  const amount = receipt.runtime_cost_usd
  if (amount === null || amount === 0) return null
  return amount
}

function withNote(text: string): string {
  return `${text} · ${COST_ESTIMATE_NOTE}`
}

function unpricedTitle(reasons: string[]): string {
  return reasons.length ? `미가격 사유: ${reasons.join(', ')}` : '가격을 계산할 수 없음'
}

/**
 * Turn one receipt into a cell.
 *
 * `graded` exists for the grading-cost column: a task in an experiment that
 * was never graded has no receipt, but that is 미채점, not 기록 없음. Pass
 * `false` to say the work never happened; the default assumes it did.
 */
export function costCell(
  receipt: CostReceipt | null | undefined,
  field: CostField,
  { ran = true }: { ran?: boolean } = {},
): CostCell {
  const label = COST_FIELD_LABELS[field]

  if (!receipt) {
    if (!ran) {
      return {
        state: 'never_ran',
        text: NEVER_RAN_LABELS[field],
        title: `${label}: 해당 작업이 수행되지 않아 비용이 없습니다.`,
        isAmount: false,
      }
    }
    return {
      state: 'absent',
      text: '기록 없음',
      title:
        `${label}: 이 실행에는 비용 기록이 없습니다. ` +
        '$0이 아니라, 얼마가 들었는지 알 수 없다는 뜻입니다.',
      isAmount: false,
    }
  }

  if (receipt.status === 'not_run') {
    return {
      state: 'never_ran',
      text: NEVER_RAN_LABELS[field],
      title: `${label}: 해당 작업이 수행되지 않아 비용이 없습니다.`,
      isAmount: false,
    }
  }

  const amount = receiptAmount(receipt)

  if (receipt.status === 'complete' && amount !== null) {
    return {
      state: 'recorded',
      text: formatCostUsd(amount),
      title: withNote(`${label}: ${formatCostUsd(amount)}`),
      isAmount: true,
    }
  }

  // partial / unavailable — anything shown from here down is a lower bound.
  if (amount !== null) {
    return {
      state: 'floor',
      text: `≥ ${formatCostUsd(amount)}`,
      title: withNote(
        `${label}: 미확정. 일부만 가격이 계산되어 최소 ${formatCostUsd(amount)}입니다. ` +
          unpricedTitle(receipt.missing_reasons),
      ),
      isAmount: true,
    }
  }

  return {
    state: 'unpriced',
    text: '미확정',
    title: `${label}: 미확정. ${unpricedTitle(receipt.missing_reasons)}`,
    isAmount: false,
  }
}

/**
 * The task-level 조건부 합계.
 *
 * Conditional in two ways: it does not exist unless at least one receipt does,
 * and it is only a total when both fields carry a complete receipt. A missing
 * grading receipt makes the pair a floor, because the unrecorded half is
 * unknown rather than free.
 */
export function combinedTaskCost(
  problem: CostReceipt | null | undefined,
  grading: CostReceipt | null | undefined,
): CostCell | null {
  const receipts = [problem, grading].filter(Boolean) as CostReceipt[]
  if (!receipts.length) return null

  const amounts = receipts
    .map(receiptAmount)
    .filter((amount): amount is number => amount !== null)

  // Work that never ran is not a hole in the sum; it contributed nothing.
  const accounted = receipts.filter((r) => r.status !== 'not_run')
  const exact =
    accounted.every((r) => r.status === 'complete') &&
    [problem, grading].every((r) => r == null || r.status !== 'partial') &&
    [problem, grading].filter(Boolean).length === 2

  if (!amounts.length) {
    return {
      state: 'unpriced',
      text: '미확정',
      title: `합계: 가격이 계산된 항목이 없습니다.`,
      isAmount: false,
    }
  }

  const total = Number(amounts.reduce((sum, value) => sum + value, 0).toFixed(6))

  if (exact) {
    return {
      state: 'recorded',
      text: formatCostUsd(total),
      title: withNote(`합계: ${formatCostUsd(total)}`),
      isAmount: true,
    }
  }

  return {
    state: 'floor',
    text: `≥ ${formatCostUsd(total)}`,
    title: withNote(
      `합계: 기록된 항목만 더한 최소값입니다. 기록이 없는 항목은 $0으로 세지 않았습니다.`,
    ),
    isAmount: true,
  }
}

const SUMMARY_STATUS_LABELS: Record<CostStatus, string> = {
  complete: '전체 기록됨',
  partial: '일부 기록됨',
  unavailable: '가격 미계산',
  not_run: '미수행',
}

export function summaryStatusLabel(status: CostStatus): string {
  return SUMMARY_STATUS_LABELS[status]
}

/**
 * A run total, honestly labelled. `complete` gives a total; anything else
 * gives the floor of what was recorded, marked `≥`.
 */
export function summaryTotalCell(summary: CostSummary, field: CostField): CostCell {
  const label = COST_FIELD_LABELS[field]
  if (summary.estimated_cost_usd !== null) {
    return {
      state: 'recorded',
      text: formatCostUsd(summary.estimated_cost_usd),
      title: withNote(`${label} 총액: ${formatCostUsd(summary.estimated_cost_usd)}`),
      isAmount: true,
    }
  }
  if (summary.measured_tasks > 0) {
    return {
      state: 'floor',
      text: `≥ ${formatCostUsd(summary.known_cost_usd)}`,
      title: withNote(
        `${label}: ${summary.total_tasks}건 중 ${summary.measured_tasks}건만 가격이 ` +
          '계산되어 총액이 아니라 최소값입니다.',
      ),
      isAmount: true,
    }
  }
  return {
    state: 'unpriced',
    text: '미확정',
    title: `${label}: ${unpricedTitle(summary.missing_reasons)}`,
    isAmount: false,
  }
}

/** A single statistic inside the summary card; `null` renders as 기록 없음. */
export function summaryStatCell(value: number | null): CostCell {
  if (value === null) {
    return {
      state: 'absent',
      text: '기록 없음',
      title: '가격이 계산된 작업이 없어 계산할 수 없습니다.',
      isAmount: false,
    }
  }
  return {
    state: 'recorded',
    text: formatCostUsd(value),
    title: withNote(formatCostUsd(value)),
    isAmount: true,
  }
}

/**
 * Problem-solving cost per successful deliverable.
 *
 * Null has two causes worth telling apart: the run is not fully priced, so no
 * per-unit figure can be honest (미확정), or the run produced no successful
 * deliverable to divide by (기록 없음).
 */
export function perDeliverableCell(summary: CostSummary): CostCell {
  const value = summary.cost_per_successful_deliverable_usd
  if (value !== null) {
    return {
      state: 'recorded',
      text: formatCostUsd(value),
      title: withNote(`성공 결과물 1건당: ${formatCostUsd(value)}`),
      isAmount: true,
    }
  }
  if (summary.status !== 'complete') {
    return {
      state: 'unpriced',
      text: '미확정',
      title: '일부 작업의 비용이 확정되지 않아 1건당 비용을 계산할 수 없습니다.',
      isAmount: false,
    }
  }
  return {
    state: 'absent',
    text: '기록 없음',
    title: '성공한 결과물이 없어 1건당 비용을 계산할 수 없습니다.',
    isAmount: false,
  }
}

/** Muted for state words, normal for money — a state word is not a number. */
export function costCellClass(cell: CostCell): string {
  switch (cell.state) {
    case 'recorded':
      return 'text-dash-text'
    case 'floor':
      return 'text-amber-400'
    case 'unpriced':
      return 'text-amber-400/70'
    default:
      return 'text-dash-text-faint'
  }
}
