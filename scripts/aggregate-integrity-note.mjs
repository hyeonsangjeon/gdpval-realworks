#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import YAML from 'yaml'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SOURCE_PATH = join(ROOT, 'data', 'notes', 'integrity-incidents.yaml')
const BEFORE_CONFIG_PATH = join(ROOT, 'batch-runner', 'experiments', 'exp013_GPT54_reasoning_high.yaml')
const AFTER_CONFIG_PATH = join(ROOT, 'batch-runner', 'experiments', 'exp025_GPT54_high_postfix.yaml')
const OUTPUT_PATH = join(ROOT, 'public', 'generated', 'integrity-note.json')
const COMPARED_FIELDS = ['data.filter', 'condition_a', 'execution']
const MISSING_EXECUTION_IDENTITIES = [
  'execution_git_sha',
  'input_dataset_revision',
  'azure_model_revision',
  'runner_environment_identity',
]

const requireString = (value, label, pattern) => {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} must be a non-empty string`)
  if (pattern && !pattern.test(value)) throw new Error(`${label} has an invalid format`)
  return value
}

const requireDate = (value, label) => {
  const date = requireString(value, label, /^\d{4}-\d{2}-\d{2}$/)
  const timestamp = `${date}T00:00:00.000Z`
  const milliseconds = Date.parse(timestamp)
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).toISOString() !== timestamp) {
    throw new Error(`${label} must be a valid date`)
  }
  return date
}

const requireSha = (value, label) => requireString(value, label, /^[0-9a-f]{40}$/)
const stableJson = (value) => JSON.stringify(value, Object.keys(value ?? {}).sort())
const deepEqual = (left, right) => JSON.stringify(left) === JSON.stringify(right)

const comparableConfig = (config) => ({
  data_filter: config?.data?.filter,
  condition_a: config?.condition_a,
  execution: config?.execution,
})

export function buildIntegrityNoteData(sourceText, beforeConfigText, afterConfigText) {
  const source = YAML.parse(sourceText)
  const beforeConfig = YAML.parse(beforeConfigText)
  const afterConfig = YAML.parse(afterConfigText)
  const comparison = source?.comparison
  const history = source?.history
  const interpretation = source?.interpretation

  if (!comparison || !history || !interpretation) throw new Error('integrity source is incomplete')
  const beforeId = requireString(comparison.before?.experiment_id, 'before experiment ID', /^exp\d+_/)
  const afterId = requireString(comparison.after?.experiment_id, 'after experiment ID', /^exp\d+_/)
  if (beforeConfig?.experiment?.id !== beforeId || afterConfig?.experiment?.id !== afterId) {
    throw new Error('comparison experiment IDs must match the config files')
  }

  const beforeComparable = comparableConfig(beforeConfig)
  const afterComparable = comparableConfig(afterConfig)
  if (!deepEqual(beforeComparable, afterComparable)) {
    throw new Error(`checked-in experiment configs differ: ${stableJson({ before: beforeComparable, after: afterComparable })}`)
  }

  const condition = beforeConfig?.condition_a
  if (condition?.name !== comparison.expected_condition) throw new Error('condition name changed')
  if (condition?.model?.deployment !== comparison.expected_model) throw new Error('model deployment changed')
  if (condition?.model?.provider !== 'azure') throw new Error('comparison must remain Azure-only')
  if (beforeConfig?.execution?.mode !== comparison.expected_mode) throw new Error('execution mode changed')
  if (comparison.expected_task_count !== 220 || comparison.expected_report_scope !== 'self_assessed_pre_grading') {
    throw new Error('comparison scope contract changed')
  }

  if (interpretation.causal_attribution !== false) throw new Error('causal attribution must remain disabled')
  if (!deepEqual(interpretation.missing_execution_identities, MISSING_EXECUTION_IDENTITIES)) {
    throw new Error('missing execution identities must match the exact contract')
  }
  if (history.fixes?.anthropic_content?.applicable_to_comparison !== false) {
    throw new Error('Anthropic parsing fix is not applicable to Azure runs')
  }
  if (history.fixes?.qa_failed?.undetermined_remains_success !== true) {
    throw new Error('QA-undetermined exception must remain explicit')
  }

  return {
    comparison: {
      before: {
        short_id: requireString(comparison.before?.short_id, 'before short ID', /^exp\d+$/),
        experiment_id: beforeId,
        report_date: requireDate(comparison.before?.report_date, 'before report date'),
      },
      after: {
        short_id: requireString(comparison.after?.short_id, 'after short ID', /^exp\d+$/),
        experiment_id: afterId,
        report_date: requireDate(comparison.after?.report_date, 'after report date'),
      },
      expected_condition: requireString(comparison.expected_condition, 'expected condition'),
      expected_model: requireString(comparison.expected_model, 'expected model'),
      expected_mode: requireString(comparison.expected_mode, 'expected mode'),
      expected_task_count: 220,
      expected_report_scope: 'self_assessed_pre_grading',
      checked_in_config_equal: true,
      compared_fields: COMPARED_FIELDS,
    },
    history: {
      parent_commit: requireSha(history.parent_commit, 'parent commit'),
      core_fix_commit: requireSha(history.core_fix_commit, 'core fix commit'),
      followup_commit: requireSha(history.followup_commit, 'follow-up commit'),
      merge_commit: requireSha(history.merge_commit, 'merge commit'),
      applied_at: requireDate(history.applied_at, 'fix date'),
      fixes: history.fixes,
    },
    interpretation: {
      causal_attribution: false,
      observed_claim: requireString(interpretation.observed_claim, 'observed claim'),
      measurement_claim: requireString(interpretation.measurement_claim, 'measurement claim'),
      missing_execution_identities: MISSING_EXECUTION_IDENTITIES,
      report_snapshot: requireString(interpretation.report_snapshot, 'report snapshot caveat'),
    },
    sources: {
      integrity: 'data/notes/integrity-incidents.yaml',
      before_config: 'batch-runner/experiments/exp013_GPT54_reasoning_high.yaml',
      after_config: 'batch-runner/experiments/exp025_GPT54_high_postfix.yaml',
    },
  }
}

export async function aggregateIntegrityNote() {
  const [sourceText, beforeConfigText, afterConfigText] = await Promise.all([
    readFile(SOURCE_PATH, 'utf8'),
    readFile(BEFORE_CONFIG_PATH, 'utf8'),
    readFile(AFTER_CONFIG_PATH, 'utf8'),
  ])
  const data = {
    ...buildIntegrityNoteData(sourceText, beforeConfigText, afterConfigText),
    _generated: new Date().toISOString(),
  }
  await mkdir(dirname(OUTPUT_PATH), { recursive: true })
  await writeFile(OUTPUT_PATH, `${JSON.stringify(data, null, 2)}\n`)
  console.log(`✅ ${OUTPUT_PATH}`)
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  aggregateIntegrityNote().catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
}
