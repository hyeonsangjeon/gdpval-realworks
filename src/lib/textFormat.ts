import { TASK_TOTAL_PLACEHOLDER } from '../data/tooltipTexts'

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const PLACEHOLDER_PATTERN = new RegExp(escapeRegExp(TASK_TOTAL_PLACEHOLDER), 'g')

export function substituteTaskTotal(text: string, total: number): string {
  return text.replace(PLACEHOLDER_PATTERN, String(total))
}
