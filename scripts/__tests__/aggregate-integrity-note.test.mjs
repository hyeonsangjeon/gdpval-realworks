import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { promisify } from 'node:util'
import test from 'node:test'

import { buildIntegrityNoteData } from '../aggregate-integrity-note.mjs'

const execFileAsync = promisify(execFile)
const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')
const cwd = new URL('../..', import.meta.url)

async function loadSources() {
  const [source, beforeConfig, afterConfig] = await Promise.all([
    readRepoFile('data/notes/integrity-incidents.yaml'),
    readRepoFile('batch-runner/experiments/exp013_GPT54_reasoning_high.yaml'),
    readRepoFile('batch-runner/experiments/exp025_GPT54_high_postfix.yaml'),
  ])
  return { source, beforeConfig, afterConfig }
}

test('integrity note validates equal checked-in experiment settings and non-causal interpretation', async () => {
  const { source, beforeConfig, afterConfig } = await loadSources()
  const data = buildIntegrityNoteData(source, beforeConfig, afterConfig)

  assert.equal(data.comparison.checked_in_config_equal, true)
  assert.deepEqual(data.comparison.compared_fields, ['data.filter', 'condition_a', 'execution'])
  assert.equal(data.comparison.before.short_id, 'exp013')
  assert.equal(data.comparison.after.short_id, 'exp025')
  assert.equal(data.interpretation.causal_attribution, false)
  assert.deepEqual(data.interpretation.missing_execution_identities, [
    'execution_git_sha',
    'input_dataset_revision',
    'azure_model_revision',
    'runner_environment_identity',
  ])
})

test('integrity note rejects config drift and causal overclaim', async () => {
  const { source, beforeConfig, afterConfig } = await loadSources()
  assert.throws(
    () => buildIntegrityNoteData(source, beforeConfig, afterConfig.replace('timeout: 720', 'timeout: 721')),
    /configs differ/,
  )
  assert.throws(
    () => buildIntegrityNoteData(source.replace('causal_attribution: false', 'causal_attribution: true'), beforeConfig, afterConfig),
    /causal attribution must remain disabled/,
  )
  assert.throws(
    () => buildIntegrityNoteData(source.replace('execution_git_sha', 'unrelated_identity'), beforeConfig, afterConfig),
    /exact contract/,
  )
})

test('pinned history proves available-files persistence and qa-failed classification changed', async () => {
  const { source, beforeConfig, afterConfig } = await loadSources()
  const data = buildIntegrityNoteData(source, beforeConfig, afterConfig)
  const subprocessPath = data.history.fixes.available_files.path
  const inferencePath = data.history.fixes.qa_failed.path
  const [beforeSubprocess, afterSubprocess, beforeInference, afterInference] = await Promise.all([
    execFileAsync('git', ['show', `${data.history.parent_commit}:${subprocessPath}`], { cwd }).then((result) => result.stdout),
    execFileAsync('git', ['show', `${data.history.core_fix_commit}:${subprocessPath}`], { cwd }).then((result) => result.stdout),
    execFileAsync('git', ['show', `${data.history.parent_commit}:${inferencePath}`], { cwd }).then((result) => result.stdout),
    execFileAsync('git', ['show', `${data.history.core_fix_commit}:${inferencePath}`], { cwd }).then((result) => result.stdout),
  ])

  const headerNeedle = 'code = files_header + code'
  const beforeHeader = beforeSubprocess.indexOf(headerNeedle)
  const afterHeader = afterSubprocess.indexOf(headerNeedle)
  assert.ok(beforeHeader > 0 && afterHeader > 0)
  assert.equal(beforeSubprocess.indexOf('code_path.write_text(code', beforeHeader), -1)
  assert.ok(afterSubprocess.indexOf('code_path.write_text(code', afterHeader) > afterHeader)
  assert.equal(beforeInference.includes('best_result["status"] = "qa_failed"'), false)
  assert.equal(afterInference.includes('best_result["status"] = "qa_failed"'), true)
})

test('pinned history commit dates and merge ancestry match the source record', async () => {
  const { source, beforeConfig, afterConfig } = await loadSources()
  const data = buildIntegrityNoteData(source, beforeConfig, afterConfig)
  const commits = [data.history.core_fix_commit, data.history.followup_commit, data.history.merge_commit]
  const dates = await Promise.all(commits.map((commit) => execFileAsync('git', ['show', '-s', '--format=%cs', commit], { cwd }).then((result) => result.stdout.trim())))
  assert.deepEqual(dates, ['2026-05-17', '2026-05-17', '2026-05-17'])
  await execFileAsync('git', ['merge-base', '--is-ancestor', data.history.core_fix_commit, data.history.merge_commit], { cwd })
  await execFileAsync('git', ['merge-base', '--is-ancestor', data.history.followup_commit, data.history.merge_commit], { cwd })
})
