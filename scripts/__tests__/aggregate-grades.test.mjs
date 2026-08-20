// Unit tests for scripts/aggregate-grades.mjs
//
// Covers the dashboard_cleanup contract:
//   - `inference_model` never silently falls back to `judge.model`
//   - `grade_status` is set on every emitted result
//   - `experiment_id` is a 1st-class field (no startsWith brittleness)
//
// Run:
//   node --test scripts/__tests__/aggregate-grades.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { isPublishableGrade, processGradesFile } from '../aggregate-grades.mjs';
import { gradeIdentityFromRaw } from '../grade-identity.mjs';

test('gradeIdentityFromRaw supports top-level, legacy meta, filename fallback, source pointer, and dummy', () => {
  assert.deepEqual(gradeIdentityFromRaw('ignored.json', {
    experiment_id: 'exp-top',
    source_inference_experiment_id: 'exp-source',
  }), {
    is_dummy: false,
    experiment_id: 'exp-top',
    source_inference_experiment_id: 'exp-source',
  });
  assert.deepEqual(gradeIdentityFromRaw('ignored.json', {
    _meta: { experiment_id: 'exp-legacy', source_inference_experiment_id: 'exp-legacy-source' },
  }), {
    is_dummy: false,
    experiment_id: 'exp-legacy',
    source_inference_experiment_id: 'exp-legacy-source',
  });
  assert.deepEqual(gradeIdentityFromRaw('exp-file__judge__rubric__v1.json', {}), {
    is_dummy: false,
    experiment_id: 'exp-file',
    source_inference_experiment_id: null,
  });
  assert.deepEqual(gradeIdentityFromRaw('exp-dummy.json', { _meta: { is_dummy: true, experiment_id: 'exp-dummy' } }), {
    is_dummy: true,
    experiment_id: 'exp-dummy',
    source_inference_experiment_id: null,
  });
  assert.deepEqual(gradeIdentityFromRaw('v1.json', { schema_version: '1.0', experiment_id: 'exp-v1', _meta: { is_dummy: true } }), {
    is_dummy: false,
    experiment_id: 'exp-v1',
    source_inference_experiment_id: null,
  });
});

test('processGradesFile treats v1 as real even when contradictory legacy dummy metadata is present', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp-v1-real',
    _meta: { is_dummy: true },
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4' },
    summary: { total_tasks: 0, graded_tasks: 0, error_tasks: 0, openai_compat: {}, wow: {} },
    tasks: [],
  };
  const out = processGradesFile('exp-v1-real__judge__rubric__v1.json', raw);
  assert.equal(out.is_dummy, false);
  assert.equal(out.grade_status, 'graded_v1');
  assert.equal(out.experiment_id, 'exp-v1-real');
});

test('processGradesFile routes current schema 1.2 through item-level grading', () => {
  const raw = {
    schema_version: '1.2',
    experiment_id: 'exp-current',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.6-sol' },
    summary: {
      total_tasks: 0,
      graded_tasks: 0,
      error_tasks: 0,
      openai_compat: {},
      wow: {},
    },
    tasks: [],
  };

  const out = processGradesFile('current.json', raw);

  assert.equal(out.grade_status, 'graded_v1');
  assert.equal(out.schema_version, '1.2');
  assert.equal(out.judge_model, 'gpt-5.6-sol');
});

test('processGradesFile preserves visible zero judge-error rate for schema 1.3', () => {
  const raw = {
    schema_version: '1.3',
    experiment_id: 'exp-score-excluded',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-mini' },
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 100,
        ci_pct: 0,
        perfect_count: 1,
        partial_count: 0,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 0 },
    },
    tasks: [{ task_id: 'task-1', pct: 100, error: null, items: [] }],
  };

  const out = processGradesFile('score-excluded.json', raw);

  assert.equal(out.grade_status, 'graded_v1');
  assert.equal(out.schema_version, '1.3');
  assert.equal(out.summary_v1.wow.judge_error_rate, 0);
});

test('processGradesFile rejects malformed schema 1.3 required shapes', () => {
  const valid = {
    schema_version: '1.3',
    experiment_id: 'exp-shape',
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 100,
        ci_pct: 0,
        perfect_count: 1,
        partial_count: 0,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 0 },
    },
    tasks: [{ task_id: 'task-1', pct: 100, error: null, items: [] }],
  };

  for (const mutate of [
    (raw) => { delete raw.tasks; },
    (raw) => { delete raw.tasks[0].items; },
    (raw) => { delete raw.summary.openai_compat.ci_pct; },
    (raw) => { delete raw.summary.openai_compat.zero_count; },
  ]) {
    const invalid = structuredClone(valid);
    mutate(invalid);
    assert.throws(
      () => processGradesFile('invalid-shape.json', invalid),
      /schema 1.3 .*missing|schema 1.3 .*invalid/,
    );
  }
});

test('processGradesFile rejects nullable headline before schema 1.3', () => {
  const raw = {
    schema_version: '1.2',
    experiment_id: 'exp-old-null',
    summary: {
      total_tasks: 0,
      graded_tasks: 0,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: null,
        ci_pct: null,
        perfect_count: 0,
        partial_count: 0,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [],
  };

  assert.throws(
    () => processGradesFile('old-null.json', raw),
    /schema 1.0-1.2 headline must remain numeric/,
  );
});

test('processGradesFile rejects hidden or score-included schema 1.3 judge errors', () => {
  const raw = {
    schema_version: '1.3',
    experiment_id: 'exp-invalid-score-policy',
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 0,
        ci_pct: 0,
        perfect_count: 0,
        partial_count: 1,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 1 },
    },
    tasks: [{
      task_id: 'task-1',
      pct: 0,
      error: null,
      items: [{
        verdict: 'judge_error',
        decided_by: 'judge',
        score_excluded: false,
      }],
    }],
  };

  assert.throws(
    () => processGradesFile('invalid.json', raw),
    /judge_error must be score_excluded/,
  );

  raw.tasks[0].items[0].score_excluded = true;
  raw.tasks[0].items.push({
    verdict: 'pass',
    decided_by: 'precheck',
    score_excluded: false,
  });
  delete raw.summary.wow.judge_error_rate;
  assert.throws(
    () => processGradesFile('invalid.json', raw),
    /judge_error_rate is missing or inconsistent/,
  );

  raw.summary.wow.judge_error_rate = 0.99999;
  assert.throws(
    () => processGradesFile('invalid.json', raw),
    /judge_error_rate is missing or inconsistent/,
  );
});

test('processGradesFile renders an all-excluded schema 1.3 run as unscored', () => {
  const raw = {
    schema_version: '1.3',
    experiment_id: 'exp-unscored',
    summary: {
      total_tasks: 1,
      graded_tasks: 0,
      error_tasks: 1,
      openai_compat: {
        avg_score_pct: null,
        ci_pct: null,
        perfect_count: 0,
        partial_count: 0,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 1 },
    },
    tasks: [{
      task_id: 'task-1',
      pct: 0,
      error: 'all_items_score_excluded',
      items: [{
        verdict: 'judge_error',
        decided_by: 'judge',
        score_excluded: true,
      }],
    }],
  };

  const out = processGradesFile('unscored.json', raw);

  assert.equal(out.summary.avg_score_pct, null);
  assert.equal(out.summary.zero_score, 0);
  assert.equal(out.tasks[0].error, true);

  raw.summary.total_tasks = 999;
  assert.throws(
    () => processGradesFile('invalid-count.json', raw),
    /task counts are inconsistent/,
  );
  raw.summary.total_tasks = 1;

  raw.summary.openai_compat.inconsistent_count = 7;
  assert.throws(
    () => processGradesFile('invalid-inconsistent.json', raw),
    /unscored grade must not report headline scores/,
  );
  raw.summary.openai_compat.inconsistent_count = 0;

  raw.tasks[0].error = null;
  raw.summary.openai_compat.avg_score_pct = 0;
  raw.summary.openai_compat.ci_pct = 0;
  raw.summary.openai_compat.zero_count = 1;
  assert.throws(
    () => processGradesFile('invalid-unscored.json', raw),
    /all-excluded task must be unscored/,
  );
});

test('schema 1.3 judge-error rate uses the backend half-up tie rule', () => {
  const items = Array.from({ length: 32 }, (_, index) => ({
    verdict: index === 0 ? 'judge_error' : 'pass',
    decided_by: 'judge',
    score_excluded: index === 0,
  }));
  const raw = {
    schema_version: '1.3',
    experiment_id: 'exp-rate-tie',
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 100,
        ci_pct: 0,
        perfect_count: 1,
        partial_count: 0,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 0.0313 },
    },
    tasks: [{ task_id: 'task-1', pct: 100, error: null, items }],
  };

  assert.equal(
    processGradesFile('rate-tie.json', raw).summary_v1.wow.judge_error_rate,
    0.0313,
  );
  raw.summary.wow.judge_error_rate = 0.0312;
  assert.throws(
    () => processGradesFile('rate-tie-invalid.json', raw),
    /judge_error_rate is missing or inconsistent/,
  );
});

test('dashboard always renders judge-error rate and discloses score exclusion', async () => {
  const healthStrip = await readFile(
    new URL('../../src/components/wow/HealthStrip.tsx', import.meta.url),
    'utf8',
  );
  const tooltips = await readFile(
    new URL('../../src/data/tooltipTexts.ts', import.meta.url),
    'utf8',
  );

  assert.match(healthStrip, /label="err"[\s\S]*value=\{fmtPct\(errRate\)\}/);
  assert.doesNotMatch(healthStrip, /errRate\s*&&\s*<Pill/);
  assert.match(tooltips, /excluded from score denominators but remain visible here/);
});

// ── Fixture A — minimal v1 grade with empty `inference_model` ───────────────
test('processGradesFile: v1 with empty inference_model does not fall back to judge.model', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp998_smoke_baseline_sample',
    inference_model: '',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 50.0,
        ci_pct: 0,
        perfect_count: 0,
        partial_count: 1,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 't1', pct: 50, error: null },
    ],
  };

  const out = processGradesFile('exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json', raw);

  assert.equal(out.inference_model, null, 'inference_model must be null when raw value is empty string');
  assert.equal(out.judge_model, 'gpt-5.4-pro', 'judge_model must be the raw judge.model');
  assert.equal(out.model, '', 'legacy `model` falls back to empty string when no inference model — never to judge');
  assert.equal(out.grade_status, 'graded_v1');
  assert.equal(out.experiment_id, 'exp998_smoke_baseline_sample');
});

// ── Fixture B — full v1 grade with schema_version 1.0 ───────────────────────
test('processGradesFile: v1 grade sets grade_status=graded_v1 and lifts raw.experiment_id', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp025_real_run',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 3,
      graded_tasks: 3,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 80.5,
        ci_pct: 5.1,
        perfect_count: 1,
        partial_count: 2,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: {
        judge_error_rate: 0.01,
      },
    },
    tasks: [
      { task_id: 't1', pct: 100, error: null },
      { task_id: 't2', pct: 75,  error: null },
      { task_id: 't3', pct: 67,  error: null },
    ],
  };

  const out = processGradesFile('exp025_real_run__gpt-5_4-pro__abc1234__v1.json', raw);

  assert.equal(out.grade_status, 'graded_v1');
  assert.equal(out.experiment_id, 'exp025_real_run');
  assert.equal(out.inference_model, 'gpt-5.2-chat');
  assert.equal(out.judge_model, 'gpt-5.4-pro');
  assert.equal(out.schema_version, '1.0');
});

for (const [runStatus, gradeStatus] of [
  ['partial', 'grading_partial'],
  ['diagnostic', 'grading_diagnostic'],
]) {
  test(`processGradesFile marks ${runStatus} grades non-publishable`, () => {
    const raw = {
      schema_version: '1.0',
      run_status: runStatus,
      experiment_id: 'exp-partial',
      inference_model: 'gpt-5.2-chat',
      judge: { model: 'gpt-5.4-pro' },
      summary: {
        total_tasks: 3,
        graded_tasks: 1,
        error_tasks: 0,
        openai_compat: {},
        wow: {},
      },
      tasks: [{ task_id: 't1', pct: 50, error: null }],
    };

    const output = processGradesFile('partial.json', raw);

    assert.equal(output.grade_status, gradeStatus);
    assert.equal(output.run_status, runStatus);
    assert.equal(isPublishableGrade(output), false);
  });
}

test('processGradesFile carries the source provenance gap onto a publishable grade', () => {
  // A grade from a pre-sidecar inference publishes when its config pinned the
  // complete corpus, so the dashboard is the only place left that can show the
  // Azure AI routes were never verified. Absent the field, it stays null rather
  // than being invented as "verified".
  const base = {
    schema_version: '1.0',
    run_status: 'final',
    experiment_id: 'exp-legacy',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.6-sol' },
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: {},
      wow: {},
    },
    tasks: [{ task_id: 't1', pct: 50, error: null }],
  };

  const legacy = processGradesFile('legacy.json', {
    ...base,
    source_azure_ai_provenance_status: 'legacy-missing',
  });

  assert.equal(legacy.source_azure_ai_provenance_status, 'legacy-missing');
  assert.equal(isPublishableGrade(legacy), true);

  assert.equal(
    processGradesFile('sidecar.json', base).source_azure_ai_provenance_status,
    null,
  );
});

// ── Fixture C — legacy dummy with _meta.is_dummy ────────────────────────────
test('processGradesFile: legacy dummy sets grade_status=legacy_dummy and judge_model=null', () => {
  const raw = {
    _meta: {
      is_dummy: true,
      label: 'GPT-5 Baseline (Sample)',
      model: 'GPT-5 (Baseline)',
      dataset_url: 'https://hf.co/datasets/example',
      avg_score_pct: 47.3,
      ci_pct: 6.2,
    },
    tasks: [
      { task_id: 't1', num_grades: 3, scores: [1, 1, 1], avg_score: 1.0, error: false, error_messages: [] },
      { task_id: 't2', num_grades: 3, scores: [0, 0, 0], avg_score: 0.0, error: false, error_messages: [] },
    ],
  };

  const out = processGradesFile('dummy_gpt5_baseline.json', raw);

  assert.equal(out.grade_status, 'legacy_dummy');
  assert.equal(out.judge_model, null, 'legacy dummies have no judge metadata');
  assert.equal(out.inference_model, 'GPT-5 (Baseline)', 'legacy meta.model represents the inference model');
  assert.equal(out.is_dummy, true);
  assert.equal(out.schema_version, null);
  assert.equal(out.experiment_id, 'dummy_gpt5_baseline');
});

// ── Fixture D — v1 grade joined with taskQaByExperiment map ────────────────
// Two tasks both matched: qa=8/10 + rubric=85% → delta=+5 (calibrated);
//                          qa=9/10 + rubric=60% → delta=−30 (overconfident).
// Expected MAE = (|+5| + |−30|) / 2 = 17.50.
test('processGradesFile: v1 with per-experiment qa map decorates tasks and computes MAE/counts', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp998_smoke_baseline_sample',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 2,
      graded_tasks: 2,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 72.5, ci_pct: 0,
        perfect_count: 0, partial_count: 2, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 't_aligned', pct: 85, error: null },
      { task_id: 't_over',    pct: 60, error: null },
    ],
  };
  const taskQaByExperiment = new Map([
    ['exp998_smoke_baseline_sample', { t_aligned: 8, t_over: 9 }],
  ]);

  const out = processGradesFile('exp998_smoke__judge__sha__v1.json', raw, taskQaByExperiment);

  // qa_score is preserved on both legacy-shaped tasks and raw v1 tasks
  assert.equal(out.tasks[0].qa_score, 8);
  assert.equal(out.tasks[1].qa_score, 9);
  assert.equal(out.tasks_v1[0].qa_score, 8);
  assert.equal(out.tasks_v1[1].qa_score, 9);

  // MAE = (5 + 30) / 2 = 17.50 (rounded to 2 decimals)
  assert.equal(out.summary.calibration_mae, 17.5);
  assert.equal(out.summary_v1.calibration_mae, 17.5);

  // Δ +5 → calibrated; Δ −30 → overconfident; none underconfident; 0 unmatched
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 1, overconfident: 1, underconfident: 0, unmatched: 0,
  });
});

// ── Fixture E — v1 grade with no qa_score map (fresh repo) ──────────────────
// All tasks get qa_score=null and land in `unmatched`; MAE must be null.
test('processGradesFile: v1 with empty qa_score map yields null qa_score and null MAE', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp998_smoke_baseline_sample',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 2,
      graded_tasks: 2,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 75, ci_pct: 0,
        perfect_count: 0, partial_count: 2, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 't_a', pct: 80, error: null },
      { task_id: 't_b', pct: 70, error: null },
    ],
  };

  // No second arg → default empty Map ⇒ all tasks unmatched
  const out = processGradesFile('exp998__judge__sha__v1.json', raw);

  assert.equal(out.tasks[0].qa_score, null);
  assert.equal(out.tasks[1].qa_score, null);
  assert.equal(out.summary.calibration_mae, null);
  assert.equal(out.summary_v1.calibration_mae, null);
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 0, overconfident: 0, underconfident: 0, unmatched: 2,
  });
});

// ── Fixture F — partial match (one task in map, one not) ────────────────────
// Verifies unmatched counter and that MAE is computed only over matched samples.
test('processGradesFile: v1 with partial qa_score match — only matched task contributes to MAE', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp_partial',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 2,
      graded_tasks: 2,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 60, ci_pct: 0,
        perfect_count: 0, partial_count: 2, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 't_matched',   pct: 50, error: null },
      { task_id: 't_unmatched', pct: 70, error: null },
    ],
  };
  // Only one task in the experiment's map; pct=50 ⇒ rubric=50%, qa=2 ⇒ self=20%, Δ=+30
  const taskQaByExperiment = new Map([
    ['exp_partial', { t_matched: 2 }],
  ]);

  const out = processGradesFile('exp_partial__judge__sha__v1.json', raw, taskQaByExperiment);

  assert.equal(out.tasks[0].qa_score, 2);
  assert.equal(out.tasks[1].qa_score, null);
  assert.equal(out.summary.calibration_mae, 30, 'MAE = |+30| / 1 = 30');
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 0, overconfident: 0, underconfident: 1, unmatched: 1,
  });
});

// ── Fixture G — legacy dummy is ALWAYS unmatched regardless of qa map ──────
// Per spec section 1b: dummy grades come from synthetic scores, NOT a real
// inference run. They must never inherit qa_score from an unrelated report
// even if a global / same-named map happens to contain matching task_ids.
test('processGradesFile: legacy dummy ignores qa map and yields all-null qa_score', () => {
  const raw = {
    _meta: { is_dummy: true, model: 'GPT-5 (Baseline)' },
    tasks: [
      { task_id: 't1', num_grades: 1, scores: [1.0], avg_score: 1.0, error: false, error_messages: [] },
      { task_id: 't2', num_grades: 1, scores: [0.0], avg_score: 0.0, error: false, error_messages: [] },
    ],
  };
  // Even though this map names the dummy's experiment_id with valid scores,
  // the resolver MUST return null for every task because is_dummy=true.
  const taskQaByExperiment = new Map([
    ['dummy_gpt5_baseline', { t1: 10, t2: 8 }],
  ]);

  const out = processGradesFile('dummy_gpt5_baseline.json', raw, taskQaByExperiment);

  assert.equal(out.tasks[0].qa_score, null, 'dummy task 1 must be null');
  assert.equal(out.tasks[1].qa_score, null, 'dummy task 2 must be null');
  assert.equal(out.summary.calibration_mae, null);
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 0, overconfident: 0, underconfident: 0, unmatched: 2,
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Strict per-experiment matching tests (T1-T5)
// ═══════════════════════════════════════════════════════════════════════════

// ── T1 — Real grade with matching report (mixed matched/unmatched) ────────
test('T1: real grade matches reports-index by experiment_id (matched + unmatched)', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'expA',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 3,
      graded_tasks: 3,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 65, ci_pct: 0,
        perfect_count: 0, partial_count: 3, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 'uuid-1', pct: 85, error: null },  // qa=8 → Δ = 85-80 = +5  (calibrated)
      { task_id: 'uuid-2', pct: 60, error: null },  // qa=5 → Δ = 60-50 = +10 (calibrated, boundary)
      { task_id: 'uuid-3', pct: 50, error: null },  // no qa → unmatched
    ],
  };
  const taskQaByExperiment = new Map([
    ['expA', { 'uuid-1': 8, 'uuid-2': 5 }],
  ]);

  const out = processGradesFile('expA__judge__sha__v1.json', raw, taskQaByExperiment);

  assert.equal(out.tasks[0].qa_score, 8);
  assert.equal(out.tasks[1].qa_score, 5);
  assert.equal(out.tasks[2].qa_score, null);
  // MAE over the 2 matched samples = (|+5| + |+10|) / 2 = 7.5
  assert.equal(out.summary.calibration_mae, 7.5);
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 2, overconfident: 0, underconfident: 0, unmatched: 1,
  });
});

// ── T2 — Dummy grade: all qa_score null regardless of reports content ─────
test('T2: dummy grade yields all-null qa_score and MAE=null regardless of map content', () => {
  const raw = {
    _meta: { is_dummy: true, model: 'Dummy Model' },
    tasks: Array.from({ length: 4 }, (_, i) => ({
      task_id: `uuid-${i}`,
      num_grades: 1,
      scores: [0.5],
      avg_score: 0.5,
      error: false,
      error_messages: [],
    })),
  };
  // Map populated with the dummy's id and valid scores → MUST be ignored.
  const taskQaByExperiment = new Map([
    ['dummy_grade', { 'uuid-0': 1, 'uuid-1': 5, 'uuid-2': 9, 'uuid-3': 10 }],
  ]);

  const out = processGradesFile('dummy_grade.json', raw, taskQaByExperiment);

  assert.equal(out.is_dummy, true);
  for (const t of out.tasks) assert.equal(t.qa_score, null);
  assert.equal(out.summary.calibration_mae, null);
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 0, overconfident: 0, underconfident: 0, unmatched: 4,
  });
});

// ── T3 — Non-dummy grade with no matching report entry ────────────────────
test('T3: real grade with no matching report → all qa_score null, MAE=null, all unmatched', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp_no_report',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 2,
      graded_tasks: 2,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 75, ci_pct: 0,
        perfect_count: 0, partial_count: 2, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 'uuid-a', pct: 80, error: null },
      { task_id: 'uuid-b', pct: 70, error: null },
    ],
  };
  // Map contains a DIFFERENT experiment → strict matching must not leak.
  const taskQaByExperiment = new Map([
    ['some_other_exp', { 'uuid-a': 9, 'uuid-b': 7 }],
  ]);

  const out = processGradesFile('exp_no_report__j__s__v1.json', raw, taskQaByExperiment);

  assert.equal(out.tasks[0].qa_score, null);
  assert.equal(out.tasks[1].qa_score, null);
  assert.equal(out.summary.calibration_mae, null);
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 0, overconfident: 0, underconfident: 0, unmatched: 2,
  });
});

// ── T4 — MAE calculation precision (canonical example) ────────────────────
// Two matched tasks:
//   qa=8/10, rubric=85% → Δ = 85 - 80 = +5  (|Δ|=5,  calibrated)
//   qa=9/10, rubric=60% → Δ = 60 - 90 = -30 (|Δ|=30, overconfident)
// Expected MAE = (5 + 30) / 2 = 17.5
test('T4: MAE precision — (5 + 30) / 2 = 17.50; counts = 1 calibrated, 1 overconfident', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'expMAE',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 2,
      graded_tasks: 2,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 72.5, ci_pct: 0,
        perfect_count: 0, partial_count: 2, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 't_aligned', pct: 85, error: null },
      { task_id: 't_over',    pct: 60, error: null },
    ],
  };
  const taskQaByExperiment = new Map([
    ['expMAE', { t_aligned: 8, t_over: 9 }],
  ]);

  const out = processGradesFile('expMAE__j__s__v1.json', raw, taskQaByExperiment);

  assert.equal(out.summary.calibration_mae, 17.5);
  assert.equal(out.summary_v1.calibration_mae, 17.5);
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 1, overconfident: 1, underconfident: 0, unmatched: 0,
  });
});

// ── T5 — Error tasks are excluded from calibration counts entirely ────────
// A task with `error: 'something'` must not appear in samples nor in unmatched.
test('T5: error tasks are excluded from calibration_counts (neither sampled nor unmatched)', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'expErr',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 3,
      graded_tasks: 2,
      error_tasks: 1,
      openai_compat: {
        avg_score_pct: 75, ci_pct: 0,
        perfect_count: 0, partial_count: 2, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 'ok-1',  pct: 80,   error: null },          // qa=7 → Δ = 80-70 = +10 (calibrated)
      { task_id: 'err-1', pct: null, error: 'judge failed' },// error → excluded
      { task_id: 'ok-2',  pct: 70,   error: null },          // no qa → unmatched
    ],
  };
  const taskQaByExperiment = new Map([
    ['expErr', { 'ok-1': 7 }],
  ]);

  const out = processGradesFile('expErr__j__s__v1.json', raw, taskQaByExperiment);

  // Error task must be marked as errored on the legacy-shaped tasks row.
  assert.equal(out.tasks[1].error, true);

  // calibration_counts: ok-1 = calibrated, ok-2 = unmatched, err-1 = excluded.
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 1, overconfident: 0, underconfident: 0, unmatched: 1,
  });
  // MAE over the single matched sample = |+10| / 1 = 10.
  assert.equal(out.summary.calibration_mae, 10);
});

// ── T6 — Phase 2: source_inference_experiment_id wins over experiment_id ──
// A grade carries an explicit source pointer to a *different* experiment id
// than its own. The qa map is keyed by the source id (expB). Resolver MUST
// look up via the source pointer, ignoring the grade's own experiment_id
// (expA). Verifies the priority order documented on `makeQaResolver`.
test('T6: v1 grade with source_inference_experiment_id resolves qa via the source pointer', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'expA',
    source_inference_experiment_id: 'expB',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-pro' },
    summary: {
      total_tasks: 2,
      graded_tasks: 2,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 75, ci_pct: 0,
        perfect_count: 0, partial_count: 2, zero_count: 0, inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [
      { task_id: 'shared-1', pct: 80, error: null },  // expB.qa=7 → Δ=+10 (calibrated boundary)
      { task_id: 'shared-2', pct: 70, error: null },  // expB.qa=6 → Δ=+10 (calibrated boundary)
    ],
  };
  // expA has its OWN map with different scores — these MUST NOT leak in
  // when a source pointer is provided. Strict source-key priority.
  const taskQaByExperiment = new Map([
    ['expA', { 'shared-1': 1, 'shared-2': 1 }],
    ['expB', { 'shared-1': 7, 'shared-2': 6 }],
  ]);

  const out = processGradesFile('expA__judge__sha__v1.json', raw, taskQaByExperiment);

  // qa_score must come from expB's map, not expA's.
  assert.equal(out.tasks[0].qa_score, 7, 'shared-1 qa must come from expB (source)');
  assert.equal(out.tasks[1].qa_score, 6, 'shared-2 qa must come from expB (source)');
  assert.equal(out.tasks_v1[0].qa_score, 7);
  assert.equal(out.tasks_v1[1].qa_score, 6);

  // MAE = (|+10| + |+10|) / 2 = 10
  assert.equal(out.summary.calibration_mae, 10);
  assert.deepEqual(out.summary.calibration_counts, {
    calibrated: 2, overconfident: 0, underconfident: 0, unmatched: 0,
  });

  // Surface the pointer on the aggregated row so the dashboard can render it.
  assert.equal(out.source_inference_experiment_id, 'expB');
  assert.equal(out.experiment_id, 'expA', 'experiment_id field must be preserved unchanged');
});

// ── corpus coverage ───────────────────────────────────────────────────────
// The denominator is the inference run's own published task count, taken from
// reports-index.json. A grade never supplies its own denominator, because a
// preflight that graded 3 tasks would then report 3/3 and look complete.

test('processGradesFile measures coverage against the inference corpus', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp-corpus',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-mini' },
    summary: { total_tasks: 3, graded_tasks: 3, error_tasks: 0, openai_compat: {}, wow: {} },
    tasks: [],
  };
  const corpus = new Map([['exp-corpus', 220]]);

  const out = processGradesFile('preflight.json', raw, new Map(), corpus);

  assert.deepEqual(out.coverage, {
    grade_tasks: 3,
    corpus_tasks: 220,
    is_partial_corpus: true,
  });
  // The published counts are untouched — coverage explains them, never edits.
  assert.equal(out.summary.total_tasks, 3);
  assert.equal(out.summary.graded_tasks, 3);
});

test('processGradesFile marks a full-corpus grade complete', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp-corpus',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.6-sol' },
    summary: { total_tasks: 220, graded_tasks: 215, error_tasks: 5, openai_compat: {}, wow: {} },
    tasks: [],
  };
  const corpus = new Map([['exp-corpus', 220]]);

  const out = processGradesFile('full.json', raw, new Map(), corpus);

  assert.equal(out.coverage.is_partial_corpus, false);
  // 5 tasks the grader could not score are still 5 tasks it was handed. An
  // error is not a coverage gap, so graded_tasks is deliberately not the
  // numerator here — total_tasks is.
  assert.equal(out.coverage.grade_tasks, 220);
});

test('processGradesFile leaves coverage unknown when the experiment has no report', () => {
  const raw = {
    schema_version: '1.0',
    experiment_id: 'exp-unreported',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4' },
    summary: { total_tasks: 10, graded_tasks: 10, error_tasks: 0, openai_compat: {}, wow: {} },
    tasks: [],
  };

  const out = processGradesFile('unreported.json', raw, new Map(), new Map());

  assert.equal(out.coverage.corpus_tasks, null);
  assert.equal(out.coverage.is_partial_corpus, false);
});

test('processGradesFile emits coverage on legacy grades too', () => {
  const out = processGradesFile('dummy_gpt5_baseline.json', {
    _meta: { is_dummy: true, experiment_id: 'dummy_gpt5_baseline' },
    tasks: [
      { task_id: 't1', num_grades: 3, scores: [1, 1, 1], avg_score: 1.0, error: false, error_messages: [] },
    ],
  }, new Map(), new Map([['dummy_gpt5_baseline', 220]]));

  assert.equal(out.coverage.corpus_tasks, 220);
  assert.equal(out.coverage.is_partial_corpus, true);
});
