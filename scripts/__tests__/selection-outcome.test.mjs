import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SELECTION_OUTCOME,
  classifyTaskOutcome,
  summarizeOutcomes,
  requiredFormats,
  deliverableFiles,
  formatDemandClass,
} from '../selection-outcome.mjs';

// Shapes mirror data/grades/*.json exactly: `selected_deliverables.primary_targets`
// carries `paths` (plural), which is the field an earlier hand-audit of this data
// read as `path` and consequently missed two placeholder tasks on.
const task = (over = {}) => ({
  task_id: 't',
  pct: 50,
  error: null,
  selection_status: 'ok',
  selection_error: null,
  selected_deliverables: {
    selection_status: 'ok',
    primary_targets: [{ target_id: 'a', paths: ['Report.xlsx'], kind: 'xlsx' }],
    support_artifacts: [],
    reference_files_excluded: [],
  },
  ...over,
});

const wrongFormat = (formats, files) => task({
  pct: 0,
  selection_status: 'wrong_format_primary',
  selection_error:
    'generated files exist but none match requested primary formats: ' + formats.join(', '),
  selected_deliverables: {
    selection_status: 'wrong_format_primary',
    primary_targets: [],
    support_artifacts: files,
    reference_files_excluded: [],
  },
});

test('deliverableFiles reads primary_targets.paths as well as support artifacts', () => {
  const files = deliverableFiles(task({
    selected_deliverables: {
      primary_targets: [{ paths: ['A.xlsx', 'B.xlsx'] }],
      support_artifacts: ['C.png'],
    },
  }));
  assert.deepEqual(files, ['A.xlsx', 'B.xlsx', 'C.png']);
});

test('deliverableFiles tolerates a missing or malformed selection block', () => {
  assert.deepEqual(deliverableFiles({}), []);
  assert.deepEqual(deliverableFiles({ selected_deliverables: null }), []);
  assert.deepEqual(deliverableFiles({ selected_deliverables: 'nope' }), []);
  assert.deepEqual(deliverableFiles({ selected_deliverables: { primary_targets: [{}] } }), []);
});

test('requiredFormats parses the selector message and rejects a reworded one', () => {
  assert.deepEqual(
    requiredFormats('generated files exist but none match requested primary formats: .csv, .xlsx'),
    ['.csv', '.xlsx'],
  );
  // A future reword must yield nothing rather than a half-parsed list.
  assert.deepEqual(requiredFormats('could not match the formats .csv, .xlsx'), []);
  assert.deepEqual(requiredFormats(null), []);
  assert.deepEqual(requiredFormats(''), []);
});

test('formatDemandClass separates media a text model cannot render', () => {
  assert.equal(formatDemandClass(['.mp4', '.mov']), 'unproducible_media');
  assert.equal(formatDemandClass(['.mp3']), 'unproducible_media');
  // One producible extension in the set means the model had a way to comply.
  assert.equal(formatDemandClass(['.mp4', '.pdf']), 'producible');
  assert.equal(formatDemandClass(['.xlsx']), 'producible');
  assert.equal(formatDemandClass([]), null);
});

test('a scored task is scored and reached a judge', () => {
  const out = classifyTaskOutcome(task({ pct: 71.2 }));
  assert.equal(out.outcome, SELECTION_OUTCOME.SCORED);
  assert.equal(out.reached_judge, true);
});

test('a judged zero is the only zero that counts as a verdict', () => {
  const out = classifyTaskOutcome(task({ pct: 0 }));
  assert.equal(out.outcome, SELECTION_OUTCOME.CONTENT_ZERO);
  assert.equal(out.reached_judge, true);
});

test('the failed_to_generate placeholder outranks whatever the selector concluded', () => {
  // The selector reports these as a format mismatch, which sends a reader
  // hunting for a grading bug instead of an inference failure.
  const asFormatMiss = wrongFormat(['.xlsx'], ['failed_to_generate.txt']);
  assert.equal(classifyTaskOutcome(asFormatMiss).outcome, SELECTION_OUTCOME.INFERENCE_FAILED);

  // And it is reachable through selection_status 'ok' too: the selector will
  // happily elect the placeholder as the primary deliverable, after which a
  // judge grades a text file that says the generation failed.
  const asOk = task({
    pct: 0,
    selected_deliverables: {
      selection_status: 'ok',
      primary_targets: [{ paths: ['failed_to_generate.txt'] }],
      support_artifacts: [],
    },
  });
  assert.equal(classifyTaskOutcome(asOk).outcome, SELECTION_OUTCOME.INFERENCE_FAILED);
  assert.equal(classifyTaskOutcome(asOk).reached_judge, false);
});

test('a real file alongside the placeholder is not an inference failure', () => {
  const mixed = wrongFormat(['.xlsx'], ['failed_to_generate.txt', 'Notes.docx']);
  assert.equal(classifyTaskOutcome(mixed).outcome, SELECTION_OUTCOME.FORMAT_UNMET);
});

test('format_unmet distinguishes an unrenderable medium from a plain miss', () => {
  const media = classifyTaskOutcome(wrongFormat(['.mp4'], ['Storyboard.pdf']));
  assert.equal(media.outcome, SELECTION_OUTCOME.FORMAT_UNMET);
  assert.equal(media.format_demand, 'unproducible_media');
  assert.match(media.detail, /cannot render/);

  const miss = classifyTaskOutcome(wrongFormat(['.xlsx'], ['Summary.docx']));
  assert.equal(miss.format_demand, 'producible');
  assert.match(miss.detail, /none of the 1 generated file matched/);
});

test('selection_error is reported as not scored, never as a zero', () => {
  const out = classifyTaskOutcome(task({
    pct: 0,
    error: 'selection_error',
    selection_status: 'selection_error',
    selection_error: 'generated candidates exist but selector could not choose deterministically',
    selected_deliverables: {
      selection_status: 'selection_error',
      primary_targets: [],
      support_artifacts: ['A.docx', 'B.docx', 'C.docx'],
    },
  }));
  assert.equal(out.outcome, SELECTION_OUTCOME.NOT_SELECTED);
  assert.equal(out.reached_judge, false);
  assert.match(out.detail, /3 candidate files/);
  assert.match(out.detail, /Excluded from the average/);
});

test('no_generated_candidate is its own finding', () => {
  const out = classifyTaskOutcome(task({
    pct: 0,
    error: 'selection_error',
    selection_status: 'no_generated_candidate',
    selection_error: 'no generated deliverable after reference set-diff',
    selected_deliverables: { selection_status: 'no_generated_candidate', primary_targets: [], support_artifacts: [] },
  }));
  assert.equal(out.outcome, SELECTION_OUTCOME.NO_DELIVERABLE);
});

test('an error with no selector metadata stays a generic grading error', () => {
  const out = classifyTaskOutcome({ task_id: 't', pct: 0, error: 'judge timed out' });
  assert.equal(out.outcome, SELECTION_OUTCOME.GRADING_ERROR);
  assert.equal(out.detail, 'judge timed out');
});

test('a pre-selector grade is left unclassified rather than guessed at', () => {
  const zero = classifyTaskOutcome({ task_id: 't', pct: 0, error: null });
  assert.equal(zero.outcome, SELECTION_OUTCOME.UNCLASSIFIED);
  const scored = classifyTaskOutcome({ task_id: 't', pct: 44, error: null });
  assert.equal(scored.outcome, SELECTION_OUTCOME.SCORED);
});

test('summarizeOutcomes reports covered=false for a pre-selector grade', () => {
  const s = summarizeOutcomes([
    { task_id: 'a', pct: 0, error: null },
    { task_id: 'b', pct: 80, error: null },
  ]);
  // covered=false is the switch the card gates on, so an older experiment
  // renders exactly as it did before this feature existed.
  assert.equal(s.covered, false);
  assert.equal(s.covered_tasks, 0);
});

test('summarizeOutcomes counts every task exactly once', () => {
  const tasks = [
    task({ pct: 90 }),
    task({ pct: 0 }),
    wrongFormat(['.xlsx'], ['Summary.docx']),
    wrongFormat(['.xlsx'], ['failed_to_generate.txt']),
    task({
      pct: 0,
      error: 'selection_error',
      selection_status: 'selection_error',
      selected_deliverables: { primary_targets: [], support_artifacts: ['A.docx', 'B.docx'] },
    }),
  ];
  const s = summarizeOutcomes(tasks);
  assert.equal(s.covered, true);
  assert.equal(Object.values(s.outcomes).reduce((a, b) => a + b, 0), tasks.length);
  assert.equal(s.outcomes.scored, 1);
  assert.equal(s.judged_zero, 1);
  assert.equal(s.unjudged_zero, 2);
  assert.equal(s.outcomes.not_selected, 1);
});

test('zero_reasons omits scored tasks and leads with the judged zero', () => {
  const s = summarizeOutcomes([
    task({ pct: 90 }),
    wrongFormat(['.xlsx'], ['Summary.docx']),
    task({ pct: 0 }),
  ]);
  assert.deepEqual(s.zero_reasons.map((r) => r.outcome), ['content_zero', 'format_unmet']);
  assert.equal(s.zero_reasons[0].reached_judge, true);
  assert.equal(s.zero_reasons[1].reached_judge, false);
  assert.ok(s.zero_reasons.every((r) => r.count > 0));
});

test('summarizeOutcomes survives junk input', () => {
  assert.equal(summarizeOutcomes(null).covered, false);
  assert.equal(summarizeOutcomes([]).total_tasks, 0);
  assert.equal(summarizeOutcomes([]).zero_reasons.length, 0);
});
