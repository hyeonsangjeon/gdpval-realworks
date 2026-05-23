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
import { processGradesFile } from '../aggregate-grades.mjs';

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
