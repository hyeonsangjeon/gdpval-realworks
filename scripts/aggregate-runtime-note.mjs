#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import YAML from 'yaml'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const WORKFLOW_PATH = join(ROOT, '.github', 'workflows', 'batch-run.yml')
const INCIDENTS_PATH = join(ROOT, 'data', 'notes', 'runtime-incidents.yaml')
const OUTPUT_PATH = join(ROOT, 'public', 'generated', 'runtime-note.json')

const requirePositiveInteger = (value, label) => {
  if (!Number.isInteger(value) || value <= 0) throw new Error(`${label} must be a positive integer`)
  return value
}

const requireString = (value, label, pattern) => {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} must be a non-empty string`)
  if (pattern && !pattern.test(value)) throw new Error(`${label} has an invalid format`)
  return value
}

const requireUtcSecond = (value, label) => {
  const timestamp = requireString(value, label, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/)
  const milliseconds = Date.parse(timestamp)
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).toISOString() !== timestamp.replace('Z', '.000Z')) {
    throw new Error(`${label} must be a valid UTC timestamp`)
  }
  return timestamp
}

const requireCalendarDate = (value, label) => {
  const date = requireString(value, label, /^\d{4}-\d{2}-\d{2}$/)
  const timestamp = `${date}T00:00:00.000Z`
  const milliseconds = Date.parse(timestamp)
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).toISOString() !== timestamp) throw new Error(`${label} must be a valid date`)
  return date
}

const findExactStep = (steps, name) => {
  const matches = steps.filter((step) => step.name === name)
  if (matches.length !== 1) throw new Error(`${name} must appear exactly once`)
  return matches[0]
}

export function extractWorkflowPolicy(workflowSource) {
  const workflow = YAML.parse(workflowSource)
  const job = workflow?.jobs?.['batch-run']
  const dispatch = workflow?.on?.workflow_dispatch
  const steps = job?.steps ?? []
  const step2a = findExactStep(steps, 'Step 2a: Run inference (condition_a)')
  const step2b = findExactStep(steps, 'Step 2b: Run inference (condition_b)')

  const watchdogMinutes = requirePositiveInteger(dispatch?.inputs?.wall_timeout?.default, 'wall timeout')
  const step2aMinutes = requirePositiveInteger(step2a?.['timeout-minutes'], 'Step 2a timeout')
  const step2bMinutes = requirePositiveInteger(step2b?.['timeout-minutes'], 'Step 2b timeout')
  const jobMinutes = requirePositiveInteger(job?.['timeout-minutes'], 'job timeout')
  const step2aRun = requireString(step2a?.run, 'Step 2a run')
  const step2bRun = requireString(step2b?.run, 'Step 2b run')

  if (step2aMinutes !== step2bMinutes) throw new Error('Step 2a and Step 2b timeouts must match')
  if (!(watchdogMinutes < step2aMinutes && step2aMinutes < jobMinutes)) {
    throw new Error('runtime boundaries must satisfy watchdog < step < job')
  }
  if (!step2aRun.includes('step2_run_inference.sh condition_a --wall-timeout "$WALL_TIMEOUT"')) {
    throw new Error('Step 2a must forward the wall timeout')
  }
  if (step2bRun.includes('--wall-timeout') || !step2bRun.includes('step2_run_inference.sh condition_b')) {
    throw new Error('Step 2b watchdog wiring changed; update the runtime policy scope')
  }

  return {
    scope: 'condition_a',
    watchdog_minutes: watchdogMinutes,
    step_timeout_minutes: step2aMinutes,
    job_timeout_minutes: jobMinutes,
    relay_handoff_margin_minutes: step2aMinutes - watchdogMinutes,
  }
}

export function buildRuntimeNoteData(workflowSource, incidentsSource) {
  const incidents = YAML.parse(incidentsSource)
  const currentPolicy = extractWorkflowPolicy(workflowSource)

  const incident = incidents?.incidents?.exp025_resume_sigkill
  const approxMinute = requirePositiveInteger(incident?.approx_minute, 'incident minute')
  const incidentStepMinutes = requirePositiveInteger(incident?.incident_policy?.step_timeout_minutes, 'incident step timeout')
  const incidentJobMinutes = requirePositiveInteger(incident?.incident_policy?.job_timeout_minutes, 'incident job timeout')
  const fixBeforeMinutes = requirePositiveInteger(incident?.fix?.step_timeout_before_minutes, 'fix previous step timeout')
  const fixAfterMinutes = requirePositiveInteger(incident?.fix?.step_timeout_after_minutes, 'fix next step timeout')

  if (approxMinute !== incidentStepMinutes) throw new Error('incident minute must match the historical step timeout')
  if (incidentJobMinutes !== currentPolicy.job_timeout_minutes) throw new Error('incident and current job timeouts must match')
  if (fixBeforeMinutes !== incidentStepMinutes || fixAfterMinutes !== currentPolicy.step_timeout_minutes) {
    throw new Error('fix timeout transition must match historical and current policies')
  }
  if (incident?.incident_policy?.resume_watchdog_enabled !== false || incident?.fix?.resume_watchdog_enabled !== true) {
    throw new Error('fix must enable the Resume Round watchdog')
  }
  if (incident?.condition !== 'condition_a' || incident?.incident_policy?.scope !== 'condition_a') {
    throw new Error('incident policy must be scoped to condition_a')
  }
  const startedAt = requireUtcSecond(incident?.started_at, 'incident start')
  const completedAt = requireUtcSecond(incident?.completed_at, 'incident completion')
  if (Date.parse(startedAt) >= Date.parse(completedAt)) throw new Error('incident start must precede completion')

  return {
    current_policy: currentPolicy,
    incident: {
      experiment_id: requireString(incident?.experiment_id, 'incident experiment', /^exp\d+$/),
      condition: 'condition_a',
      action_run_id: requireString(incident?.action_run_id, 'action run ID', /^\d+$/),
      approx_minute: approxMinute,
      event: requireString(incident?.event, 'incident event'),
      started_at: startedAt,
      completed_at: completedAt,
      workflow_commit: requireString(incident?.workflow_commit, 'incident workflow commit', /^[0-9a-f]{40}$/),
      policy: {
        scope: 'condition_a',
        step_timeout_minutes: incidentStepMinutes,
        job_timeout_minutes: incidentJobMinutes,
        resume_watchdog_enabled: false,
      },
      source_record_commit: requireString(incident?.source_record_commit, 'incident source record', /^[0-9a-f]{40}$/),
      fix: {
        commit: requireString(incident?.fix?.commit, 'fix commit', /^[0-9a-f]{40}$/),
        applied_at: requireCalendarDate(incident?.fix?.applied_at, 'fix date'),
        step_timeout_before_minutes: fixBeforeMinutes,
        step_timeout_after_minutes: fixAfterMinutes,
        resume_watchdog_enabled: true,
      },
    },
    sources: {
      workflow: '.github/workflows/batch-run.yml',
      incidents: 'data/notes/runtime-incidents.yaml',
    },
  }
}

export async function aggregateRuntimeNote() {
  const [workflowSource, incidentsSource] = await Promise.all([
    readFile(WORKFLOW_PATH, 'utf8'),
    readFile(INCIDENTS_PATH, 'utf8'),
  ])
  const data = {
    ...buildRuntimeNoteData(workflowSource, incidentsSource),
    _generated: new Date().toISOString(),
  }

  await mkdir(dirname(OUTPUT_PATH), { recursive: true })
  await writeFile(OUTPUT_PATH, `${JSON.stringify(data, null, 2)}\n`)
  console.log(`✅ ${OUTPUT_PATH}`)
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  aggregateRuntimeNote().catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
}
