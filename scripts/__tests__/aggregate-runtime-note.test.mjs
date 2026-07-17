import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { promisify } from 'node:util'
import test from 'node:test'

import { buildRuntimeNoteData, extractWorkflowPolicy } from '../aggregate-runtime-note.mjs'

const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')
const execFileAsync = promisify(execFile)

test('runtime note data is derived from workflow and incident sources', async () => {
  const [workflow, incidents] = await Promise.all([
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('data/notes/runtime-incidents.yaml'),
  ])
  const data = buildRuntimeNoteData(workflow, incidents)

  assert.deepEqual(data.current_policy, {
    scope: 'condition_a',
    watchdog_minutes: 290,
    step_timeout_minutes: 350,
    job_timeout_minutes: 360,
    relay_handoff_margin_minutes: 60,
  })
  assert.deepEqual(data.incident, {
    experiment_id: 'exp025',
    condition: 'condition_a',
    action_run_id: '26018603400',
    approx_minute: 330,
    event: 'SIGKILL',
    started_at: '2026-05-18T07:02:37Z',
    completed_at: '2026-05-18T12:36:00Z',
    workflow_commit: '36b0e5bed5e9be2622e505f68d3746eec1b6cc12',
    policy: {
      scope: 'condition_a',
      step_timeout_minutes: 330,
      job_timeout_minutes: 360,
      resume_watchdog_enabled: false,
    },
    source_record_commit: '6e0001503ad4f3760c007dc1981d3bdc53dd785d',
    fix: {
      commit: '62471a4a682b2f2439bba81a7eb24335a8f4931f',
      applied_at: '2026-05-20',
      step_timeout_before_minutes: 330,
      step_timeout_after_minutes: 350,
      resume_watchdog_enabled: true,
    },
  })
})

test('runtime note data rejects unsafe boundary ordering', () => {
  const workflow = `
on:
  workflow_dispatch:
    inputs:
      wall_timeout: { default: 290 }
jobs:
  batch-run:
    timeout-minutes: 360
    steps:
      - name: "Step 2a: Run inference (condition_a)"
        timeout-minutes: 350
        run: bash step2_run_inference.sh condition_a --wall-timeout "$WALL_TIMEOUT"
      - name: "Step 2b: Run inference (condition_b)"
        timeout-minutes: 350
        run: bash step2_run_inference.sh condition_b
`
  const incidents = `
incidents:
  exp025_resume_sigkill:
    experiment_id: exp025
    condition: condition_a
    action_run_id: "26018603400"
    approx_minute: 355
    event: SIGKILL
    started_at: "2026-05-18T07:02:37Z"
    completed_at: "2026-05-18T12:36:00Z"
    workflow_commit: 36b0e5bed5e9be2622e505f68d3746eec1b6cc12
    incident_policy:
      scope: condition_a
      step_timeout_minutes: 330
      job_timeout_minutes: 360
      resume_watchdog_enabled: false
    source_record_commit: 6e0001503ad4f3760c007dc1981d3bdc53dd785d
    fix:
      commit: 62471a4a682b2f2439bba81a7eb24335a8f4931f
      applied_at: "2026-05-20"
      step_timeout_before_minutes: 330
      step_timeout_after_minutes: 350
      resume_watchdog_enabled: true
`

  assert.throws(() => buildRuntimeNoteData(workflow, incidents), /incident minute must match/)
})

test('runtime note data rejects duplicate inference steps', async () => {
  const [workflow, incidents] = await Promise.all([
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('data/notes/runtime-incidents.yaml'),
  ])
  const duplicate = workflow.replace(
    "      - name: 'Step 2b: Run inference (condition_b)'",
    "      - name: 'Step 2a: Run inference (condition_a)'\n        timeout-minutes: 350\n      - name: 'Step 2b: Run inference (condition_b)'",
  )

  assert.throws(() => buildRuntimeNoteData(duplicate, incidents), /must appear exactly once/)
})

test('pinned incident and fix commits preserve the before-after workflow history', async () => {
  const incidents = await readRepoFile('data/notes/runtime-incidents.yaml')
  const currentWorkflow = await readRepoFile('.github/workflows/batch-run.yml')
  const data = buildRuntimeNoteData(currentWorkflow, incidents)
  const path = '.github/workflows/batch-run.yml'
  const [{ stdout: incidentWorkflow }, { stdout: fixedWorkflow }] = await Promise.all([
    execFileAsync('git', ['show', `${data.incident.workflow_commit}:${path}`], { cwd: new URL('../..', import.meta.url) }),
    execFileAsync('git', ['show', `${data.incident.fix.commit}:${path}`], { cwd: new URL('../..', import.meta.url) }),
  ])

  assert.deepEqual(extractWorkflowPolicy(incidentWorkflow), {
    scope: 'condition_a',
    watchdog_minutes: 290,
    step_timeout_minutes: 330,
    job_timeout_minutes: 360,
    relay_handoff_margin_minutes: 40,
  })
  assert.deepEqual(extractWorkflowPolicy(fixedWorkflow), {
    scope: 'condition_a',
    watchdog_minutes: 290,
    step_timeout_minutes: 350,
    job_timeout_minutes: 360,
    relay_handoff_margin_minutes: 60,
  })
})

test('pinned runner history proves Resume Round watchdog was added by the fix', async () => {
  const incidents = await readRepoFile('data/notes/runtime-incidents.yaml')
  const currentWorkflow = await readRepoFile('.github/workflows/batch-run.yml')
  const data = buildRuntimeNoteData(currentWorkflow, incidents)
  const runnerPath = 'batch-runner/step2_run_inference.py'
  const [{ stdout: beforeRunner }, { stdout: afterRunner }] = await Promise.all([
    execFileAsync('git', ['show', `${data.incident.workflow_commit}:${runnerPath}`], { cwd: new URL('../..', import.meta.url) }),
    execFileAsync('git', ['show', `${data.incident.fix.commit}:${runnerPath}`], { cwd: new URL('../..', import.meta.url) }),
  ])
  const extractResumeBlock = (source) => source.slice(
    source.indexOf('# 7. Resume rounds:'),
    source.indexOf('# 8. Final summary & save'),
  )
  const before = extractResumeBlock(beforeRunner)
  const after = extractResumeBlock(afterRunner)
  assert.ok(before.length > 0)
  assert.ok(after.length > 0)

  for (const marker of [
    'Watchdog: wall-clock timeout check (resume round)',
    'if wall_deadline and time.time() >= wall_deadline:',
    'r["status"] = "pending"',
    'sys.exit(EXIT_CHECKPOINT)',
  ]) {
    assert.equal(before.includes(marker), false, `before unexpectedly contains ${marker}`)
    assert.equal(after.includes(marker), true, `after is missing ${marker}`)
  }
  assert.match(after, /_save_progress\([\s\S]*?progress_path/)
})

test('runtime note data rejects impossible and reversed incident timestamps', async () => {
  const [workflow, incidents] = await Promise.all([
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('data/notes/runtime-incidents.yaml'),
  ])
  assert.throws(
    () => buildRuntimeNoteData(workflow, incidents.replace('2026-05-18T07:02:37Z', '2026-02-30T07:02:37Z')),
    /valid UTC timestamp/,
  )
  assert.throws(
    () => buildRuntimeNoteData(workflow, incidents.replace('2026-05-18T07:02:37Z', '2026-05-18T13:02:37Z')),
    /start must precede completion/,
  )
})

test('runtime source changes trigger serialized Pages deployment', async () => {
  const deploy = await readRepoFile('.github/workflows/deploy.yml')

  assert.match(deploy, /- '\.github\/workflows\/batch-run\.yml'/)
  assert.match(deploy, /- 'data\/notes\/runtime-incidents\.yaml'/)
  assert.match(deploy, /concurrency:\s+group: pages\s+cancel-in-progress: false/)
  assert.match(deploy, /runs-on: ubuntu-24\.04/)
  assert.match(deploy, /fetch-depth: 0/)
  assert.match(deploy, /Verify aggregate contracts and pinned history[\s\S]*npm run test:aggregate/)
  assert.match(deploy, /playwright install --with-deps --only-shell chromium/)
  assert.match(deploy, /npm run test:runtime-browser:dist/)
})
