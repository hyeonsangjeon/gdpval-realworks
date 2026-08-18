#!/usr/bin/env node

/**
 * aggregate-grades.mjs
 *
 * data/grades/*.json 파일들을 집계하여 대시보드용 JSON을 생성:
 *   public/generated/grades-index.json
 *
 * 사용법:
 *   node scripts/aggregate-grades.mjs
 */

import { readdir, readFile, writeFile, mkdir, access } from 'fs/promises';
import { join, extname, basename } from 'path';
import { gradeIdentityFromRaw } from './grade-identity.mjs';

const ROOT = new URL('..', import.meta.url).pathname;
const GRADES_DIR = join(ROOT, 'data', 'grades');
const OUTPUT_DIR = join(ROOT, 'public', 'generated');
const PER_GRADE_DIR = join(OUTPUT_DIR, 'grades');

async function dirExists(path) {
  try { await access(path); return true; } catch { return false; }
}

/**
 * inconsistent_grades: count of tasks where multiple judges produced
 * different scores. Always 0 for single-judge runs (Phase A). Populated
 * by Phase B multi-judge aggregator.
 */

// ── Calibration helpers ────────────────────────────────────────────────────
// Build summary-level calibration stats from a list of legacy-shaped task rows
// already decorated with `qa_score` (0-10) and `avg_score` (0-1).
// Convention: delta = (avg_score * 100) - (qa_score * 10). Positive Δ ⇒ rubric
// > self (model underconfident); negative Δ ⇒ rubric < self (overconfident).
function buildCalibration(tasks) {
  const samples = [];
  let unmatched = 0;
  for (const t of tasks) {
    if (t.error) continue;
    if (t.qa_score == null) { unmatched++; continue; }
    if (t.avg_score == null) continue;
    const delta = (t.avg_score * 100) - (t.qa_score * 10);
    samples.push(delta);
  }
  const calibration_mae = samples.length > 0
    ? Number((samples.reduce((s, d) => s + Math.abs(d), 0) / samples.length).toFixed(2))
    : null;
  const calibration_counts = {
    calibrated: samples.filter(d => Math.abs(d) <= 10).length,
    overconfident: samples.filter(d => d < -10).length,
    underconfident: samples.filter(d => d > 10).length,
    unmatched,
  };
  return { calibration_mae, calibration_counts };
}

// ── qa_score resolution (strict per-experiment) ───────────────────────────
// Returns a function (taskId) → qa_score|null for a given grade.
// Strict rules:
//   - Dummy grades have no real inference run → always null (caller must not
//     accidentally pick up unrelated qa values from a same-task-id report).
//   - Otherwise, prefer Phase 2's explicit `source_inference_experiment_id`
//     pointer when present; fall back to `experiment_id` (Phase 1 default).
//     This lets renamed/relabeled experiments carry an explicit source link
//     while legacy grades (no Phase 2 field) keep working unchanged.
//   - Missing experiment or missing task → null. Never falls back to a
//     global / cross-experiment map.
function makeQaResolver(experiment_id, is_dummy, taskQaByExperiment, source_experiment_id = null) {
  if (is_dummy) return () => null;
  // Phase 2: source pointer wins when explicitly set & non-empty.
  const lookupKey = (typeof source_experiment_id === 'string' && source_experiment_id.trim())
    ? source_experiment_id
    : experiment_id;
  const qaMap = taskQaByExperiment?.get(lookupKey) ?? null;
  if (!qaMap) return () => null;
  return (taskId) => {
    if (!taskId) return null;
    const v = qaMap[taskId];
    return typeof v === 'number' ? v : null;
  };
}

// ── Legacy (dummy / _meta-based) format ────────────────────────────────────
function processLegacyGradesFile(filePath, raw, taskQaByExperiment = new Map()) {
  const filename = basename(filePath, '.json');
  const meta = raw._meta || {};
  const rawTasks = raw.tasks || raw; // support both { _meta, tasks } and bare array

  const identity = gradeIdentityFromRaw(filePath, raw);
  const is_dummy = identity.is_dummy;
  const experiment_id = identity.experiment_id;
  const qaFor = makeQaResolver(experiment_id, is_dummy, taskQaByExperiment);

  // Decorate each task with qa_score (null when no match) so the GradeDetail
  // table can render Self-QA / Δ Gap / Calibration columns.
  const tasks = rawTasks.map(t => ({
    ...t,
    qa_score: qaFor(t.task_id),
  }));

  const gradedTasks = tasks.filter(t => !t.error && t.avg_score !== null);
  const errorTasks = tasks.filter(t => t.error);

  const scores = gradedTasks.map(t => t.avg_score);
  const avgScore = scores.length > 0
    ? scores.reduce((a, b) => a + b, 0) / scores.length
    : 0;

  // Score buckets
  const perfect = gradedTasks.filter(t => t.avg_score === 1.0).length;
  const partial = gradedTasks.filter(t => t.avg_score > 0 && t.avg_score < 1.0).length;
  const zero = gradedTasks.filter(t => t.avg_score === 0.0).length;

  // Grader disagreement (scores contain different values)
  const inconsistent = gradedTasks.filter(t => {
    const unique = new Set(t.scores);
    return unique.size > 1;
  }).length;

  // dummy_gpt5_baseline.json _meta.model represents the inference model
  // (it's the legacy demo's own "Model:" header). No judge metadata exists
  // for legacy dummies, so judge_model is null. Never fall back to judge.
  const inference_model = meta.model && String(meta.model).trim() ? meta.model : null;
  const judge_model = null;
  const model = inference_model || '';

  const grade_status = is_dummy ? 'legacy_dummy' : 'no_grade';

  // Self-QA vs Rubric calibration stats (null when no tasks have qa_score).
  const { calibration_mae, calibration_counts } = buildCalibration(tasks);

  return {
    id: filename,
    experiment_id,
    grade_status,
    schema_version: null,
    is_dummy,
    label: meta.label || filename,
    model,
    inference_model,
    judge_model,
    dataset_url: meta.dataset_url || null,
    summary: {
      total_tasks: tasks.length,
      graded_tasks: gradedTasks.length,
      error_tasks: errorTasks.length,
      avg_score_pct: Math.round(avgScore * 1000) / 10,
      ci_pct: meta.ci_pct || null,
      perfect_score: perfect,
      partial_score: partial,
      zero_score: zero,
      inconsistent_grades: inconsistent,
      calibration_mae,
      calibration_counts,
    },
    tasks,
  };
}

// ── v1.0 schema (007) ─────────────────────────────────────────────────────
//
// Maps raw item-level grade JSON onto the dashboard's existing legacy shape
// while preserving the full v1 payload in summary_v1 / tasks_v1 so WOW
// components can consume rich item-level data.
function validateScoreExcludedGrade(raw) {
  if (raw?.schema_version !== '1.3') return;

  if (!Array.isArray(raw.tasks)) {
    throw new Error('schema 1.3 tasks are missing or invalid');
  }
  if (!raw.summary || typeof raw.summary !== 'object' || Array.isArray(raw.summary)) {
    throw new Error('schema 1.3 summary is missing or invalid');
  }
  if (
    !raw.summary.openai_compat
    || typeof raw.summary.openai_compat !== 'object'
    || Array.isArray(raw.summary.openai_compat)
  ) {
    throw new Error('schema 1.3 headline summary is missing or invalid');
  }
  if (
    !raw.summary.wow
    || typeof raw.summary.wow !== 'object'
    || Array.isArray(raw.summary.wow)
  ) {
    throw new Error('schema 1.3 health summary is missing or invalid');
  }

  const tasks = raw.tasks;
  let judgeItems = 0;
  let judgeErrors = 0;
  let gradedTasks = 0;
  for (const task of tasks) {
    if (!task || typeof task !== 'object' || Array.isArray(task)) {
      throw new Error('schema 1.3 task is missing or invalid');
    }
    if (!Array.isArray(task.items)) {
      throw new Error('schema 1.3 task items are missing or invalid');
    }
    const items = task.items;
    const allExcluded = items.length > 0
      && items.every((item) => item?.score_excluded === true);
    if (allExcluded && !task?.error) {
      throw new Error('schema 1.3 all-excluded task must be unscored');
    }
    if (!task?.error) gradedTasks += 1;
    for (const item of items) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        throw new Error('schema 1.3 item is missing or invalid');
      }
      if (item?.decided_by === 'judge') {
        judgeItems += 1;
        if (item.verdict === 'judge_error') judgeErrors += 1;
      }
      if (item?.verdict === 'judge_error' && item.score_excluded !== true) {
        throw new Error('schema 1.3 judge_error must be score_excluded');
      }
    }
  }

  const summary = raw?.summary;
  const errorTasks = tasks.length - gradedTasks;
  for (const field of ['total_tasks', 'graded_tasks', 'error_tasks']) {
    if (!Number.isInteger(summary[field]) || summary[field] < 0) {
      throw new Error(`schema 1.3 ${field} is missing or invalid`);
    }
  }
  if (
    summary?.total_tasks !== tasks.length
    || summary?.graded_tasks !== gradedTasks
    || summary?.error_tasks !== errorTasks
  ) {
    throw new Error('schema 1.3 task counts are inconsistent');
  }
  const openaiCompat = summary?.openai_compat;
  for (const field of [
    'perfect_count',
    'zero_count',
    'partial_count',
    'inconsistent_count',
  ]) {
    if (!Number.isInteger(openaiCompat[field]) || openaiCompat[field] < 0) {
      throw new Error(`schema 1.3 ${field} is missing or invalid`);
    }
  }
  if (
    openaiCompat.perfect_count
      + openaiCompat.zero_count
      + openaiCompat.partial_count
    !== gradedTasks
  ) {
    throw new Error('schema 1.3 headline counts are inconsistent');
  }
  if (gradedTasks === 0) {
    if (
      openaiCompat?.avg_score_pct !== null
      || openaiCompat?.ci_pct !== null
      || openaiCompat?.perfect_count !== 0
      || openaiCompat?.zero_count !== 0
      || openaiCompat?.partial_count !== 0
      || openaiCompat?.inconsistent_count !== 0
    ) {
      throw new Error('schema 1.3 unscored grade must not report headline scores');
    }
  } else if (
    !Number.isFinite(openaiCompat?.avg_score_pct)
    || openaiCompat.avg_score_pct < 0
    || openaiCompat.avg_score_pct > 100
    || !Number.isFinite(openaiCompat?.ci_pct)
    || openaiCompat.ci_pct < 0
  ) {
    throw new Error('schema 1.3 scored headline is missing or invalid');
  }

  const rate = raw?.summary?.wow?.judge_error_rate;
  const canonicalRate = judgeItems > 0
    ? Math.floor((2 * judgeErrors * 10_000 + judgeItems) / (2 * judgeItems)) / 10_000
    : 0;
  if (
    !Number.isFinite(rate)
    || rate < 0
    || rate > 1
    || rate !== canonicalRate
  ) {
    throw new Error('schema 1.3 judge_error_rate is missing or inconsistent');
  }
}

function validateHistoricalHeadline(raw) {
  if (!['1.0', '1.1', '1.2'].includes(raw?.schema_version)) return;
  const openaiCompat = raw?.summary?.openai_compat;
  if (openaiCompat?.avg_score_pct === null || openaiCompat?.ci_pct === null) {
    throw new Error('schema 1.0-1.2 headline must remain numeric');
  }
}

function processV1GradesFile(filePath, raw, taskQaByExperiment = new Map()) {
  validateScoreExcludedGrade(raw);
  validateHistoricalHeadline(raw);
  const filename = basename(filePath, '.json');
  const rawTasks = Array.isArray(raw.tasks) ? raw.tasks : [];
  const summary = raw.summary || {};
  const openaiCompat = summary.openai_compat || {};
  const wow = summary.wow || {};

  // v1 path: prefer human-readable label/title from raw, fall back through
  // experiment_id, finally filename. Aggregator caller may add a `label`
  // field to grade JSON in future spec versions; this is forward-compatible.
  const identity = gradeIdentityFromRaw(filePath, raw);
  const label = raw.label || raw.title || identity.experiment_id || filename;
  const experiment_id = identity.experiment_id;
  // Phase 2: explicit pointer to the inference run that produced these
  // deliverables. Null/empty ⇒ fall back to experiment_id (Phase 1 behavior).
  const source_experiment_id = identity.source_inference_experiment_id;

  // Strict per-experiment Self-QA resolver. v1 grades are never dummies.
  const qaFor = makeQaResolver(experiment_id, false, taskQaByExperiment, source_experiment_id);

  // Convert v1 tasks → legacy-compatible task rows. Snap pct to exact 0/1
  // when it crosses the openai_compat thresholds (pct >= 99 → perfect,
  // pct <= 1 → zero) so legacy Status badges agree with summary counts.
  const tasks = rawTasks.map((t) => {
    const qa_score = qaFor(t.task_id);
    const hasError = t.error !== null && t.error !== undefined && t.error !== '';
    if (hasError) {
      return {
        task_id: t.task_id,
        num_grades: 0,
        scores: [],
        avg_score: null,
        error: true,
        error_messages: [String(t.error)],
        qa_score,
      };
    }
    const pct = typeof t.pct === 'number' ? t.pct : 0;
    let avgScore;
    if (pct >= 99) avgScore = 1.0;
    else if (pct <= 1) avgScore = 0.0;
    else avgScore = pct / 100;
    return {
      task_id: t.task_id,
      num_grades: 1,
      scores: [avgScore],
      avg_score: avgScore,
      error: false,
      error_messages: [],
      qa_score,
    };
  });

  // Decorate raw v1 tasks too — GradeDetail page reads from tasks_v1 directly.
  const tasks_v1 = rawTasks.map((t) => ({ ...t, qa_score: qaFor(t.task_id) }));

  const totalTasks = typeof summary.total_tasks === 'number'
    ? summary.total_tasks
    : rawTasks.length;
  const errorTasks = typeof summary.error_tasks === 'number'
    ? summary.error_tasks
    : tasks.filter((t) => t.error).length;
  const gradedTasks = typeof summary.graded_tasks === 'number'
    ? summary.graded_tasks
    : totalTasks - errorTasks;

  // Explicit fields with no silent fallback. Empty / missing inference_model
  // surfaces as null in the dashboard so the UI can render "unknown" instead
  // of inheriting the judge model name (the bug fixed in this PR).
  const inference_model = typeof raw.inference_model === 'string' && raw.inference_model.trim()
    ? raw.inference_model
    : null;
  const judge_model = raw.judge && raw.judge.model ? raw.judge.model : null;
  // Legacy `model` field: inference only. Never falls back to judge.
  const model = inference_model || '';

  // Self-QA vs Rubric calibration stats — computed from legacy-shaped `tasks`
  // (which carry the snapped avg_score) so MAE aligns with rendered scores.
  const { calibration_mae, calibration_counts } = buildCalibration(tasks);

  return {
    id: filename,
    experiment_id,
    source_inference_experiment_id: source_experiment_id,
    grade_status: raw.run_status === 'partial'
      ? 'grading_partial'
      : raw.run_status === 'diagnostic'
        ? 'grading_diagnostic'
        : 'graded_v1',
    run_status: raw.run_status || 'legacy_final',
    // A pre-sidecar inference can still publish a final grade when its config
    // pins the complete corpus, so the gap has to travel with the grade: the
    // graded tasks are fully accounted for, the Azure AI routes behind them are
    // not. Surfacing it here is what keeps that trade-off visible on the
    // dashboard instead of buried in the payload.
    source_azure_ai_provenance_status:
      raw.source_azure_ai_provenance_status || null,
    schema_version: raw.schema_version || '1.0',
    is_dummy: false,
    label,
    model,
    inference_model,
    judge_model,
    dataset_url: raw.dataset_url || null,
    summary: {
      total_tasks: totalTasks,
      graded_tasks: gradedTasks,
      error_tasks: errorTasks,
      avg_score_pct: openaiCompat.avg_score_pct === null
        ? null
        : typeof openaiCompat.avg_score_pct === 'number'
          ? openaiCompat.avg_score_pct
          : 0,
      ci_pct: typeof openaiCompat.ci_pct === 'number' ? openaiCompat.ci_pct : null,
      perfect_score: openaiCompat.perfect_count ?? 0,
      partial_score: openaiCompat.partial_count ?? 0,
      zero_score: openaiCompat.zero_count ?? 0,
      inconsistent_grades: openaiCompat.inconsistent_count ?? 0,
      calibration_mae,
      calibration_counts,
    },
    tasks,
    // v1.0 provenance + full payload (for WOW dashboard components)
    judge: raw.judge,
    rubric: raw.rubric,
    prompt: raw.prompt,
    graded_at: raw.graded_at,
    summary_v1: { ...summary, wow, openai_compat: openaiCompat, calibration_mae, calibration_counts },
    tasks_v1,
  };
}

export function processGradesFile(filePath, raw, taskQaByExperiment = new Map()) {
  // All item-level 1.x payloads share the rich grade projection. Later minor
  // versions add provenance contracts without changing dashboard score shape.
  if (raw && ['1.0', '1.1', '1.2', '1.3'].includes(raw.schema_version)) {
    return processV1GradesFile(filePath, raw, taskQaByExperiment);
  }
  return processLegacyGradesFile(filePath, raw, taskQaByExperiment);
}

export function isPublishableGrade(result) {
  return !['grading_partial', 'grading_diagnostic'].includes(
    result?.grade_status,
  );
}

// ── taskQaByExperiment lookup ─────────────────────────────────────────────
// Build Map<experiment_id, Record<task_id, qa_score>> from reports-index.json.
// STRICT: reports-index is the only source. No fallback to batch-runner/results/
// — the previous global-task_id map produced incorrect cross-experiment matches
// because GDPVal task_ids are shared across all experiments running the same
// dataset. Missing reports-index ⇒ empty Map ⇒ all qa_score = null.
async function buildTaskQaByExperiment() {
  const map = new Map();
  const indexPath = join(OUTPUT_DIR, 'reports-index.json');
  let raw;
  try {
    raw = JSON.parse(await readFile(indexPath, 'utf-8'));
  } catch (err) {
    // ENOENT = file not yet generated (first build, fresh repo) — silent fallback.
    // Other errors (parse failure, permission, etc.) deserve a warning so they
    // are not silently masked as "no qa_score available".
    if (err && err.code !== 'ENOENT') {
      console.warn(`⚠️  reports-index.json unreadable (${err.message}); all qa_score will be null.`);
    }
    return map;
  }
  for (const report of raw.reports ?? []) {
    const expId = report?.meta?.experiment_id;
    if (expId && report.task_qa && typeof report.task_qa === 'object') {
      map.set(expId, report.task_qa);
    }
  }
  return map;
}

// ── Main ──
async function main() {
  if (!(await dirExists(GRADES_DIR))) {
    console.log('ℹ️  No data/grades/ directory — skipping grades aggregation.');
    return;
  }

  const files = await readdir(GRADES_DIR);
  const jsonFiles = files.filter(f => extname(f) === '.json').sort();

  if (jsonFiles.length === 0) {
    console.log('ℹ️  No grade files found in data/grades/ — skipping.');
    return;
  }

  // Build experiment_id → task_qa lookup once for all grade files.
  // Strict per-experiment matching; reports-index.json is the sole source.
  const taskQaByExperiment = await buildTaskQaByExperiment();
  const totalQaTasks = Array.from(taskQaByExperiment.values())
    .reduce((n, m) => n + Object.keys(m).length, 0);
  console.log(`ℹ️  task_qa lookup built: ${taskQaByExperiment.size} experiment(s), ${totalQaTasks} task(s)`);

  const results = [];
  for (const file of jsonFiles) {
    const content = await readFile(join(GRADES_DIR, file), 'utf-8');
    try {
      const data = JSON.parse(content);
      const processed = processGradesFile(file, data, taskQaByExperiment);
      if (!isPublishableGrade(processed)) {
        console.warn(`⚠️  ${file} is ${processed.grade_status}; excluded from dashboard`);
        continue;
      }
      results.push(processed);
    } catch (err) {
      console.error(`⚠️  ${file} 파싱 실패:`, err.message);
    }
  }

  await mkdir(OUTPUT_DIR, { recursive: true });
  await mkdir(PER_GRADE_DIR, { recursive: true });
  await writeFile(
    join(OUTPUT_DIR, 'grades-index.json'),
    JSON.stringify(results, null, 2),
  );
  // Per-experiment full payloads (incl. tasks_v1 / summary_v1) — optional
  // companion files for future detail routes; index file remains the contract.
  for (const r of results) {
    await writeFile(
      join(PER_GRADE_DIR, `${r.id}.json`),
      JSON.stringify(r, null, 2),
    );
  }

  console.log(`✅ Aggregated ${results.length} grade file(s) → grades-index.json`);
  for (const r of results) {
    const dummy = r.is_dummy ? ' [DUMMY]' : '';
    const v1 = r.schema_version ? ` [v${r.schema_version}]` : '';
    const headline = r.summary.avg_score_pct == null
      ? 'unscored'
      : `${r.summary.avg_score_pct}% avg`;
    console.log(`   ${r.id}: ${headline} (${r.summary.graded_tasks}/${r.summary.total_tasks} tasks)${dummy}${v1}`);
  }
}

// Only run as a script when invoked directly (`node aggregate-grades.mjs`).
// When imported as a module (e.g. from unit tests) the side-effecting `main`
// is suppressed so test harnesses can call `processGradesFile` cleanly.
const invokedDirectly = (() => {
  try {
    const entry = process.argv[1] ? new URL(`file://${process.argv[1]}`).href : '';
    return entry === import.meta.url;
  } catch {
    return false;
  }
})();

if (invokedDirectly) {
  main().catch(err => { console.error(err); process.exit(1); });
}
