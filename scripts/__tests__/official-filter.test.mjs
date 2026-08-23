import assert from 'node:assert/strict'
import test from 'node:test'

import {
  filterDashboardExperiments,
  filterDashboardReports,
  getDashboardDisplayData,
  HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS,
  isHiddenDiagnosticExperimentId,
  isHiddenOfficialExperiment,
  isOfficialGradeId,
  isPartialCorpusGrade,
  isSupersededGradeId,
  OFFICIAL_GRADE_IDS,
  OFFICIAL_TASK_COUNT,
  SUPERSEDED_GRADE_IDS,
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
// ── Phase 3: partial-corpus grades ────────────────────────────────────────
// The dashboard used to hide preflight grades by name (`_tight`), which only
// worked for the one that happened to be named that way. Coverage is measured
// instead: a grade over 3 of an experiment's 220 tasks is a preflight whatever
// its config was called.

test('a grade covering part of its corpus is a preflight, not a result', () => {
  assert.equal(isPartialCorpusGrade({
    coverage: { grade_tasks: 3, corpus_tasks: 220, is_partial_corpus: true },
  }), true)
})

test('a grade covering the whole corpus is kept', () => {
  assert.equal(isPartialCorpusGrade({
    coverage: { grade_tasks: 220, corpus_tasks: 220, is_partial_corpus: false },
  }), false)
})

test('a small experiment graded end to end is complete, not partial', () => {
  // 17 of 17 is the entire corpus. Hiding it would confuse "small" with
  // "unfinished" and drop a legitimate result.
  assert.equal(isPartialCorpusGrade({
    coverage: { grade_tasks: 17, corpus_tasks: 17, is_partial_corpus: false },
  }), false)
})

test('unknown coverage is never treated as partial', () => {
  // No report for the source experiment ⇒ no denominator. Staying visible on
  // ignorance is the safer failure: the alternative silently drops real runs.
  assert.equal(isPartialCorpusGrade({
    coverage: { grade_tasks: 220, corpus_tasks: null, is_partial_corpus: false },
  }), false)
  assert.equal(isPartialCorpusGrade({}), false)
  assert.equal(isPartialCorpusGrade({ coverage: null }), false)
  assert.equal(isPartialCorpusGrade(null), false)
  assert.equal(isPartialCorpusGrade(undefined), false)
})

// ── Phase 4/5: curated baselines ────────────────────────────────────────────
// Phase 4 established the shape — one current result plus one A/B comparator.
// Phase 5 recurated which two runs fill those slots after the harness rebuild.

const SOL_220_R1 =
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_6-sol__regrade_exp003_v2_sol_max_score_excluded__cfg_71c325eee0e48c13__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_595c7254caf8fbd7__v2.2'
const SOL_220_LEGACY =
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_6-sol__regrade_exp003_v2_sol_max_score_excluded__cfg_71c325eee0e48c13__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_1c967673eb8081a6__v2.2'
const GPT54_220 = 'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools'
const GPT54_MINI_220 =
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini'

test('the rebuilt-harness sol 220 regrade is the current official result', () => {
  assert.equal(isOfficialGradeId(SOL_220_R1), true)
})

test('exactly one older run is retained as an A/B comparator', () => {
  assert.equal(isOfficialGradeId(SOL_220_LEGACY), true)
  assert.equal(isSupersededGradeId(SOL_220_LEGACY), false)
  // Two official ids total: the current result and its single comparator.
  assert.equal(OFFICIAL_GRADE_IDS.size, 2)
})

test('the retained comparator differs from the result in one variable only', () => {
  // The point of keeping this particular predecessor: same judge, same rubric,
  // same inference corpus, different `grader_source_hash`. If a future
  // recuration picks a comparator that also swaps the judge, the gap stops
  // being attributable to the harness and the pairing silently stops meaning
  // what the dashboard says it means.
  const strip = (id) => id.replace(/__src_[0-9a-f]+__/, '__src__')
  assert.equal(strip(SOL_220_R1), strip(SOL_220_LEGACY))
  assert.notEqual(SOL_220_R1, SOL_220_LEGACY)
})

test('the mini-judge run is retired, not deleted', () => {
  assert.equal(isSupersededGradeId(GPT54_MINI_220), true)
  assert.equal(isOfficialGradeId(GPT54_MINI_220), false)
})

test('the full-size gpt-5.4 run is retired once a same-judge predecessor exists', () => {
  // It held the comparator slot only because nothing closer was available. A
  // sol-vs-sol pair isolates the harness change; sol-vs-5.4 cannot.
  assert.equal(isSupersededGradeId(GPT54_220), true)
  assert.equal(isOfficialGradeId(GPT54_220), false)
})

test('promotion does not disturb the measured hide rules', () => {
  // Both official ids carry the `__src_<hex>__v2.2` suffix, which is close
  // enough to the legacy `__<7hex>__v<n>` shape to be worth pinning: if
  // `isLegacyExp003` ever widened to match them, the official allowlist would
  // be the only thing keeping the current result on screen.
  for (const id of [SOL_220_R1, SOL_220_LEGACY]) {
    assert.equal(/__[0-9a-f]{7}__v\d/i.test(id), false)
    assert.equal(id.endsWith('_tight'), false)
  }
})

test('no id can be both official and superseded', () => {
  // The official guard runs first in isHiddenGrade, so an id in both sets would
  // stay visible while reading as retired — a silent contradiction. Assert the
  // sets are disjoint rather than relying on evaluation order.
  const overlap = [...OFFICIAL_GRADE_IDS].filter((id) => SUPERSEDED_GRADE_IDS.has(id))
  assert.deepEqual(overlap, [])
})

test('curation predicates reject non-string input', () => {
  for (const bad of [null, undefined, 0, {}, []]) {
    assert.equal(isOfficialGradeId(bad), false)
    assert.equal(isSupersededGradeId(bad), false)
  }
})

test('retirement is curated, never inferred from the judge name', () => {
  // A future gpt-5.4 run must not be swept up by a pattern match on the model
  // name; retirement is a hand-written decision about one specific run.
  assert.equal(isSupersededGradeId('exp042_something__judge_gpt-5_4-mini__rubric_v3'), false)
  assert.equal(isSupersededGradeId('exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini'), false)
})
