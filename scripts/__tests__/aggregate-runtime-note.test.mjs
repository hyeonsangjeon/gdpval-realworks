import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { promisify } from 'node:util'
import test from 'node:test'
import { parse } from 'yaml'

import { buildRuntimeNoteData, extractWorkflowPolicy } from '../aggregate-runtime-note.mjs'

const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')
const execFileAsync = promisify(execFile)

const compilePythonHeredocs = async (script) => {
  const lines = script.split('\n')
  let count = 0
  for (let index = 0; index < lines.length; index += 1) {
    if (!/^python3(?:\s+-)?\s+<<'PY'$/.test(lines[index].trim())) continue
    const body = []
    index += 1
    while (index < lines.length && lines[index].trim() !== 'PY') {
      body.push(lines[index])
      index += 1
    }
    assert.ok(index < lines.length, 'Python heredoc terminator is missing')
    const indents = body
      .filter((line) => line.trim())
      .map((line) => line.length - line.trimStart().length)
    const indent = indents.length ? Math.min(...indents) : 0
    const source = body.map((line) => line.slice(indent)).join('\n')
    await execFileAsync('python3', ['-c', `compile(${JSON.stringify(source)}, '<workflow>', 'exec')`])
    count += 1
  }
  return count
}

const compileRubyHeredocs = async (script) => {
  const lines = script.split('\n')
  let count = 0
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].trim() !== "ruby <<'RUBY'") continue
    const body = []
    index += 1
    while (index < lines.length && lines[index].trim() !== 'RUBY') {
      body.push(lines[index])
      index += 1
    }
    assert.ok(index < lines.length, 'Ruby heredoc terminator is missing')
    const indents = body
      .filter((line) => line.trim())
      .map((line) => line.length - line.trimStart().length)
    const indent = indents.length ? Math.min(...indents) : 0
    const source = body.map((line) => line.slice(indent)).join('\n')
    await execFileAsync('ruby', ['-c', '-e', source])
    count += 1
  }
  return count
}

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

test('runtime source changes trigger isolated PR validation and serialized Pages deployment', async () => {
  const [deployText, batchText, step2Text] = await Promise.all([
    readRepoFile('.github/workflows/deploy.yml'),
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('batch-runner/step2_run_inference.py'),
  ])
  const deploy = parse(deployText)
  const batch = parse(batchText)
  const validateJob = deploy.jobs.validate
  const deployJob = deploy.jobs.deploy
  const eventContractStep = validateJob.steps.find(
    (step) => step.name === 'Verify non-PR event contract',
  )
  const uploadStep = validateJob.steps.find((step) => step.name === 'Upload Pages artifact')
  const createPullRequestStep = batch.jobs['batch-run'].steps.find(
    (step) => step.name === 'Create Pull Request with results',
  )
  const dispatchStep = batch.jobs['batch-run'].steps.find(
    (step) => step.name === 'Dispatch exact result PR validation',
  )
  const reportStep = batch.jobs['batch-run'].steps.find(
    (step) => step.name === 'Step 6: Generate experiment report',
  )
  const fallbackStep = batch.jobs['batch-run'].steps.find(
    (step) => step.name === 'Ensure model-free experiment report',
  )
  const verifyPrStep = batch.jobs['batch-run'].steps.find(
    (step) => step.name === 'Verify result PR outputs and contract',
  )
  const uploadHfStep = batch.jobs['batch-run'].steps.find(
    (step) => step.name === 'Step 7: Upload to HuggingFace',
  )
  const batchSteps = batch.jobs['batch-run'].steps
  const validateConfigStep = batch.jobs['batch-run'].steps.find(
    (step) => step.name === 'Validate full experiment config',
  )
  const inspectModeStep = batch.jobs['inspect-mode'].steps.find(
    (step) => step.name === 'Inspect execution mode without credentials',
  )

  assert.deepEqual(deploy.permissions, { contents: 'read' })
  assert.deepEqual(deploy.on.pull_request.branches, ['main'])
  assert.ok(deploy.on.push.paths.includes('.github/workflows/batch-run.yml'))
  assert.ok(deploy.on.push.paths.includes('data/notes/runtime-incidents.yaml'))
  assert.ok(deploy.on.push.paths.includes('vite.config.ts'))
  assert.ok(deploy.on.pull_request.paths.includes('vite.config.ts'))
  assert.equal(deploy.on.workflow_dispatch.inputs.deploy_pages.default, true)
  assert.equal(validateJob['runs-on'], 'ubuntu-24.04')
  assert.equal(validateJob.permissions, undefined)
  assert.equal(validateJob.environment, undefined)
  assert.equal(validateJob.steps.find((step) => step.name === 'Checkout').with['fetch-depth'], 0)
  assert.ok(validateJob.steps.some((step) => step.run === 'npm run test:aggregate'))
  assert.ok(validateJob.steps.some((step) => step.run?.includes('playwright install --with-deps --only-shell chromium')))
  assert.ok(validateJob.steps.some((step) => step.run === 'npm run test:notes-browser:dist'))
  assert.doesNotMatch(eventContractStep.run, /ref_protected/i)
  assert.match(eventContractStep.run, /GITHUB_EVENT_NAME.*push[\s\S]*?GITHUB_REF.*refs\/heads\/main/)
  assert.match(eventContractStep.run, /DEPLOY_PAGES.*true[\s\S]*?GITHUB_REF.*refs\/heads\/main[\s\S]*?-z.*EXPECTED_SHA/)
  assert.match(eventContractStep.run, /GITHUB_REF.*refs\/heads\/experiment\/\*/)
  assert.match(eventContractStep.run, /GITHUB_SHA.*EXPECTED_SHA/)
  assert.match(eventContractStep.run, /WORKFLOW_SHA.*EXPECTED_SHA/)
  assert.match(uploadStep.if, /refs\/heads\/main/)
  assert.doesNotMatch(uploadStep.if, /ref_protected/)
  assert.deepEqual(deployJob.permissions, { pages: 'write', 'id-token': 'write' })
  assert.equal(deployJob.environment.name, 'github-pages')
  assert.match(deployJob.if, /refs\/heads\/main/)
  assert.match(deployJob.if, /inputs\.deploy_pages == true/)
  assert.doesNotMatch(deployJob.if, /ref_protected/)
  assert.equal(createPullRequestStep.id, 'cpr')
  assert.equal(reportStep.id, 'step6')
  assert.match(
    createPullRequestStep.with.body,
    /steps\.step6\.outcome == 'success'/,
  )
  assert.match(createPullRequestStep.with.body, /Model-free fallback report/)
  assert.equal(
    createPullRequestStep.with['add-paths'],
    'batch-runner/results/${{ env.EXPERIMENT_ID }}/report/report.md',
  )
  assert.match(fallbackStep.if, /needs_relay == 'false'/)
  assert.match(fallbackStep.run, /step6_report\.sh --no-narrative/)
  assert.match(fallbackStep.run, /self-report experiment identity mismatch/)
  assert.equal(await compilePythonHeredocs(validateConfigStep.run), 1)
  assert.equal(await compilePythonHeredocs(fallbackStep.run), 1)
  assert.equal(await compilePythonHeredocs(verifyPrStep.run), 1)
  assert.equal(await compileRubyHeredocs(inspectModeStep.run), 1)
  assert.match(verifyPrStep.run, /\$PR_NUMBER.*\^\[1-9\]/s)
  assert.match(verifyPrStep.run, /isCrossRepository,files/)
  assert.match(verifyPrStep.run, /paths == \[expected_path\]/)
  assert.match(dispatchStep.run, /--raw-field deploy_pages=false/)
  assert.match(dispatchStep.run, /--raw-field expected_sha="\$PR_HEAD_SHA"/)
  assert.ok(batchSteps.indexOf(fallbackStep) < batchSteps.indexOf(createPullRequestStep))
  assert.ok(batchSteps.indexOf(createPullRequestStep) < batchSteps.indexOf(verifyPrStep))
  assert.ok(batchSteps.indexOf(verifyPrStep) < batchSteps.indexOf(uploadHfStep))
  assert.ok(batchSteps.indexOf(uploadHfStep) < batchSteps.indexOf(dispatchStep))
  assert.ok(batchText.indexOf('Validate full experiment config') < batchText.indexOf("Step 0: Bootstrap submission repo"))
  assert.match(batchText, /ExperimentConfig\.from_yaml/)
  assert.match(batchText, /config\.validate\(\)/)
  assert.match(batchText, /relay_lineage_id:/)
  assert.match(batchText, /GDPVAL_RELAY_LINEAGE_ID/)
  assert.match(batchText, /LINEAGE_ID="\$\{EXPERIMENT_ID\}:\$\{GITHUB_RUN_ID\}:\$\{GITHUB_RUN_ATTEMPT\}"/)
  assert.match(batchText, /-f relay_lineage_id="\$LINEAGE_ID"/)
  assert.match(step2Text, /step2_inference_progress_\{condition_key\}/)
  assert.match(step2Text, /step2_inference_results_\{condition_key\}/)
  assert.match(batchText, /EXPERIMENT_ID=\{config\.experiment_id\}/)
  assert.match(batchText, /step6_report\.sh --dry-run/)
})
