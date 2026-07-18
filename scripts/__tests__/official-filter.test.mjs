import assert from 'node:assert/strict'
import test from 'node:test'

import {
  filterDashboardExperiments,
  filterDashboardReports,
  getDashboardDisplayData,
  HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS,
  isHiddenDiagnosticExperimentId,
  isHiddenOfficialExperiment,
  OFFICIAL_TASK_COUNT,
} from '../../src/lib/officialExperimentScope.js'

test('official 220-task experiments remain visible', () => {
  assert.equal(OFFICIAL_TASK_COUNT, 220)
  assert.equal(isHiddenOfficialExperiment({
    short_id: 'exp026',
    experiment_name: 'Official 220',
    total_tasks: 220,
  }), false)
})

test('registered diagnostic experiments are hidden from the default view', () => {
  assert.equal(HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS.has('exp027'), true)
  assert.equal(isHiddenOfficialExperiment({
    short_id: 'exp027',
    experiment_name: 'Subprocess Bridge 50',
    total_tasks: 50,
  }), true)
  assert.equal(
    isHiddenDiagnosticExperimentId('exp027_GPT54_default_subprocess_bridge50'),
    true,
  )
  assert.equal(
    isHiddenDiagnosticExperimentId('exp027_GPT54_default_subprocess_bridge50__judge_v2'),
    true,
  )
})

test('existing non-diagnostic subsets remain visible', () => {
  assert.equal(isHiddenOfficialExperiment({
    short_id: 'exp012',
    experiment_name: 'Audio Multi-Agent Information Sector',
    total_tasks: 17,
  }), false)
})

test('all preregistered agentic experiment IDs are hidden by default', () => {
  for (const id of ['exp028', 'exp029', 'exp030']) {
    assert.equal(HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS.has(id), true)
    assert.equal(isHiddenDiagnosticExperimentId(id), true)
    assert.equal(isHiddenOfficialExperiment({
      short_id: id,
      experiment_name: id,
      total_tasks: id === 'exp028' ? 5 : 20,
    }), true)
  }
})

test('debug mode restores subsets and smoke reports', () => {
  const experiments = [
    { short_id: 'exp026', experiment_name: 'Official', total_tasks: 220, report_scope: 'self_assessed_pre_grading' },
    { short_id: 'exp027', experiment_name: 'Bridge 50', total_tasks: 50, report_scope: 'self_assessed_pre_grading' },
    { short_id: 'exp999', experiment_name: 'Smoke', total_tasks: 3, report_scope: 'self_assessed_pre_grading' },
    { short_id: 'exp028', experiment_name: 'Agentic canary', total_tasks: 5, report_scope: 'self_assessed_pre_grading' },
  ]

  assert.deepEqual(
    filterDashboardExperiments(experiments).map((experiment) => experiment.short_id),
    ['exp026'],
  )
  assert.deepEqual(
    filterDashboardExperiments(experiments, { debug: true }).map((experiment) => experiment.short_id),
    ['exp026', 'exp027', 'exp999', 'exp028'],
  )
})

test('reports use the exact visible experiment ID set', () => {
  const reports = [
    { short_id: 'exp026', narrative: 'official' },
    { short_id: 'exp027', narrative: 'diagnostic' },
  ]

  assert.deepEqual(filterDashboardReports(reports, ['exp026']), [reports[0]])
  assert.deepEqual(filterDashboardReports(reports, ['exp026', 'exp027']), reports)
})

test('Dashboard display data keeps default and debug reports aligned', () => {
  const experiments = [
    { short_id: 'exp026', experiment_name: 'Official', total_tasks: 220, report_scope: 'self_assessed_pre_grading' },
    { short_id: 'exp027', experiment_name: 'Bridge 50', total_tasks: 50, report_scope: 'self_assessed_pre_grading' },
  ]
  const reports = [
    { short_id: 'exp026', narrative: 'official errors' },
    { short_id: 'exp027', narrative: 'diagnostic errors' },
  ]

  assert.deepEqual(getDashboardDisplayData(experiments, reports), {
    experiments: [experiments[0]],
    reports: [reports[0]],
  })
  assert.deepEqual(getDashboardDisplayData(experiments, reports, { debug: true }), {
    experiments,
    reports,
  })
})