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
import { statSync } from 'fs';
import { join, extname, basename } from 'path';
import { gradeIdentityFromRaw } from './grade-identity.mjs';
import { classifyTaskOutcome, summarizeOutcomes } from './selection-outcome.mjs';
import {
  projectCostLedgerReference,
  projectCostReceipt,
  summarizeCostReceipts,
} from './cost-receipt.mjs';

// Item-level payloads that go through the rich grade projection. Later minor
// versions add provenance contracts without changing the dashboard score
// shape, so they join this list rather than forking the reader.
const ITEM_LEVEL_VERSIONS = ['1.0', '1.1', '1.2', '1.3', '1.4'];

// Versions whose invariants the aggregator enforces itself. 1.0-1.2 predate
// the score_excluded contract and are checked more loosely below.
const ITEM_LEVEL_STRICT_VERSIONS = ['1.3', '1.4'];

// Versions that carry per-task grading cost receipts. Gated rather than
// sniffed: an older grade file must read exactly as it read before this
// feature existed, cost keys or not.
const COST_RECEIPT_VERSIONS = ['1.4'];

// Every version the rich projection accepts has to be claimed by one of the
// two validators below, and the assertion runs at import rather than in a
// test so it cannot be skipped. 1.3 and 1.4 each joined ITEM_LEVEL_VERSIONS
// in their own change; a third one added the same way but left out of both
// lists would be read with no headline check at all, and the missing value
// would arrive at the projection as `undefined` — the one shape the historical
// check below was written without.
const HISTORICAL_HEADLINE_VERSIONS = ['1.0', '1.1', '1.2'];
{
  const claimed = new Set([
    ...ITEM_LEVEL_STRICT_VERSIONS,
    ...HISTORICAL_HEADLINE_VERSIONS,
  ]);
  const unclaimed = ITEM_LEVEL_VERSIONS.filter((v) => !claimed.has(v));
  if (unclaimed.length > 0) {
    throw new Error(
      `grade schema version(s) ${unclaimed.join(', ')} are read by the item-level `
        + 'projection but validated by neither validateScoreExcludedGrade nor '
        + 'validateHistoricalHeadline. Add each one to a validator list before '
        + 'adding it to ITEM_LEVEL_VERSIONS.',
    );
  }
}

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

// ── corpus coverage ───────────────────────────────────────────────────────
// How much of an inference run a grading run actually covered.
//
// A grade over 3 of an experiment's 220 tasks is a preflight, not a result.
// Put on the same axis as a full run it reads as a comparison, and the numbers
// cannot support one. The denominator is the inference run's own published
// total from reports-index.json, so this never guesses: an experiment with no
// report yields corpus_tasks: null and is left alone.
function buildCoverage(experimentId, gradeTasks, corpusByExperiment) {
  const corpus = corpusByExperiment.get(experimentId);
  const corpus_tasks = Number.isInteger(corpus) && corpus > 0 ? corpus : null;
  return {
    grade_tasks: gradeTasks,
    corpus_tasks,
    is_partial_corpus: corpus_tasks !== null && gradeTasks < corpus_tasks,
  };
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
function processLegacyGradesFile(
  filePath,
  raw,
  taskQaByExperiment = new Map(),
  corpusByExperiment = new Map(),
) {
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
    coverage: buildCoverage(experiment_id, tasks.length, corpusByExperiment),
    tasks,
  };
}

// ── Is the headline an average of the rows underneath it? ─────────────────
//
// `summary.openai_compat.avg_score_pct` is the number the dashboard shows as
// an experiment's score, and it is the one figure on this record that is
// copied out of the payload rather than derived here. The validators below
// check every count around it — total/graded/error, perfect/zero/partial,
// judge_error_rate — and never checked the average itself, so a headline the
// task rows do not add up to rendered with nothing to mark it.
//
// Four of the nineteen grade files this aggregator reads are exactly that.
// All four are schema 1.0 `exp003` runs whose average was taken over all 220
// tasks instead of the 215 or 219 that were graded, counting every ungraded
// task as a zero: one of them publishes 54.10 where its own rows mean 55.36.
// It is the mirror image of the excluded-item defect — an item the grader
// could not read leaves the denominator and the score goes UP; a task it
// could not grade stays in the denominator as a zero and the score goes DOWN
// — and neither was visible from the published summary.
//
// The treatment splits the way this file already splits versions:
//
//   * 1.3 and 1.4, the versions today's writer produces, are checked and
//     rejected. Across all seventy-five 1.3/1.4 grade files under data/grades
//     — the two this aggregator reads plus the diagnostic, shard and
//     validation files a publish is copied from — the largest disagreement is
//     0.005 points, which is two-decimal rounding and nothing else. The check
//     costs the corpus nothing today and refuses the defect the moment a
//     writer reintroduces it.
//   * 1.0-1.2 cannot be rejected. Four real published experiments would take
//     the dashboard build down with them, which is the same reasoning that
//     keeps the historical count checks loose a few dozen lines below. They
//     are measured instead, and the measurement travels on the record.
//
// Either way the published `avg_score_pct` is passed through untouched.
// Which number is the experiment's score is a decision about the benchmark,
// not one for a reader to make silently on the way to the screen.

// The headline and every task `pct` are each published rounded to two
// decimals, so a mean over correctly-computed rows can sit 0.005 from the
// rows' rounding plus 0.005 from the headline's — 0.01 at worst. This is five
// times that, and twenty-five times below the 1.24-point disagreement of the
// smallest of the four real ones, so no plausible widening of the tolerance
// admits the rounding and the defect together.
const HEADLINE_ROW_TOLERANCE_PCT = 0.05;

/**
 * Compare the published headline against the mean of the rows it summarises.
 *
 * `supported` is deliberately three-valued. `null` means the comparison could
 * not be made — no scored rows, or no numeric headline — and is not the same
 * claim as `true`. A boolean default here would report "the rows agree" for a
 * file whose rows said nothing at all, which is the failure this whole block
 * exists to stop.
 */
function headlineSupport(raw) {
  const published = raw?.summary?.openai_compat?.avg_score_pct;
  const pcts = [];
  for (const task of Array.isArray(raw?.tasks) ? raw.tasks : []) {
    // A falsy `error` is what every other reader in this file counts as
    // graded — the `graded_tasks` check above, the task projection below — so
    // the row set measured here cannot drift from the one being summarised.
    if (!task || typeof task !== 'object' || Array.isArray(task) || task.error) continue;
    if (Number.isFinite(task.pct)) pcts.push(task.pct);
  }
  if (pcts.length === 0 || !Number.isFinite(published)) {
    return {
      avg_score_pct_from_rows: null,
      delta_pct: null,
      rows_counted: pcts.length,
      supported: null,
    };
  }
  const fromRows = pcts.reduce((sum, pct) => sum + pct, 0) / pcts.length;
  const delta = published - fromRows;
  return {
    avg_score_pct_from_rows: Number(fromRows.toFixed(2)),
    delta_pct: Number(delta.toFixed(2)),
    rows_counted: pcts.length,
    supported: Math.abs(delta) <= HEADLINE_ROW_TOLERANCE_PCT,
  };
}

// ── v1.0 schema (007) ─────────────────────────────────────────────────────
//
// Maps raw item-level grade JSON onto the dashboard's existing legacy shape
// while preserving the full v1 payload in summary_v1 / tasks_v1 so WOW
// components can consume rich item-level data.
function validateScoreExcludedGrade(raw) {
  const version = raw?.schema_version;
  if (!ITEM_LEVEL_STRICT_VERSIONS.includes(version)) return;

  if (!Array.isArray(raw.tasks)) {
    throw new Error(`schema ${version} tasks are missing or invalid`);
  }
  if (!raw.summary || typeof raw.summary !== 'object' || Array.isArray(raw.summary)) {
    throw new Error(`schema ${version} summary is missing or invalid`);
  }
  if (
    !raw.summary.openai_compat
    || typeof raw.summary.openai_compat !== 'object'
    || Array.isArray(raw.summary.openai_compat)
  ) {
    throw new Error(`schema ${version} headline summary is missing or invalid`);
  }
  if (
    !raw.summary.wow
    || typeof raw.summary.wow !== 'object'
    || Array.isArray(raw.summary.wow)
  ) {
    throw new Error(`schema ${version} health summary is missing or invalid`);
  }

  const tasks = raw.tasks;
  let judgeItems = 0;
  let judgeErrors = 0;
  let gradedTasks = 0;
  for (const task of tasks) {
    if (!task || typeof task !== 'object' || Array.isArray(task)) {
      throw new Error(`schema ${version} task is missing or invalid`);
    }
    if (!Array.isArray(task.items)) {
      throw new Error(`schema ${version} task items are missing or invalid`);
    }
    const items = task.items;
    const allExcluded = items.length > 0
      && items.every((item) => item?.score_excluded === true);
    if (allExcluded && !task?.error) {
      throw new Error(`schema ${version} all-excluded task must be unscored`);
    }
    if (!task?.error) gradedTasks += 1;
    for (const item of items) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        throw new Error(`schema ${version} item is missing or invalid`);
      }
      if (item?.decided_by === 'judge') {
        judgeItems += 1;
        if (item.verdict === 'judge_error') judgeErrors += 1;
      }
      if (item?.verdict === 'judge_error' && item.score_excluded !== true) {
        throw new Error(`schema ${version} judge_error must be score_excluded`);
      }
    }
  }

  const summary = raw?.summary;
  const errorTasks = tasks.length - gradedTasks;
  for (const field of ['total_tasks', 'graded_tasks', 'error_tasks']) {
    if (!Number.isInteger(summary[field]) || summary[field] < 0) {
      throw new Error(`schema ${version} ${field} is missing or invalid`);
    }
  }
  if (
    summary?.total_tasks !== tasks.length
    || summary?.graded_tasks !== gradedTasks
    || summary?.error_tasks !== errorTasks
  ) {
    throw new Error(`schema ${version} task counts are inconsistent`);
  }
  const openaiCompat = summary?.openai_compat;
  for (const field of [
    'perfect_count',
    'zero_count',
    'partial_count',
    'inconsistent_count',
  ]) {
    if (!Number.isInteger(openaiCompat[field]) || openaiCompat[field] < 0) {
      throw new Error(`schema ${version} ${field} is missing or invalid`);
    }
  }
  if (
    openaiCompat.perfect_count
      + openaiCompat.zero_count
      + openaiCompat.partial_count
    !== gradedTasks
  ) {
    throw new Error(`schema ${version} headline counts are inconsistent`);
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
      throw new Error(`schema ${version} unscored grade must not report headline scores`);
    }
  } else if (
    !Number.isFinite(openaiCompat?.avg_score_pct)
    || openaiCompat.avg_score_pct < 0
    || openaiCompat.avg_score_pct > 100
    || !Number.isFinite(openaiCompat?.ci_pct)
    || openaiCompat.ci_pct < 0
  ) {
    throw new Error(`schema ${version} scored headline is missing or invalid`);
  }

  // An average has to be the average of something. Every scored task must
  // carry the `pct` the headline is a mean over — otherwise the mean below is
  // taken across a subset and would disagree with a headline that was right —
  // and the headline must be that mean.
  if (gradedTasks > 0) {
    for (const task of tasks) {
      if (task.error) continue;
      if (!Number.isFinite(task.pct) || task.pct < 0 || task.pct > 100) {
        throw new Error(
          `schema ${version} scored task pct is missing or invalid`,
        );
      }
    }
    const support = headlineSupport(raw);
    // `!== true` rather than `=== false`: with a finite headline and a
    // finite pct on every one of the `gradedTasks > 0` rows the null is
    // unreachable, and if that ever stops being true it should stop the
    // build rather than pass as agreement.
    if (support.supported !== true) {
      throw new Error(
        `schema ${version} headline ${openaiCompat.avg_score_pct} is not the average of `
          + `its ${support.rows_counted} scored task rows `
          + `(${support.avg_score_pct_from_rows}, off by ${support.delta_pct})`,
      );
    }
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
    throw new Error(`schema ${version} judge_error_rate is missing or inconsistent`);
  }
}

// Pre-1.3 payloads are checked for PRESENCE, never for arithmetic. Six of the
// eighteen item-level grade files published today have
// perfect + partial + zero != graded_tasks, which is exactly why 1.0-1.2 are
// read loosely: applying the strict sum here would reject six real experiments.
// "The key has to be there" costs those six nothing — the whole published
// corpus carries all six keys already — and it is the only thing standing
// between an absent headline and the projection's `: 0`.
function validateHistoricalHeadline(raw) {
  const version = raw?.schema_version;
  if (!HISTORICAL_HEADLINE_VERSIONS.includes(version)) return;

  const openaiCompat = raw?.summary?.openai_compat;
  if (
    !openaiCompat
    || typeof openaiCompat !== 'object'
    || Array.isArray(openaiCompat)
  ) {
    throw new Error(`schema ${version} headline summary is missing or invalid`);
  }
  // Null is rejected below with the message this check has always used. Absent
  // is rejected here, because `undefined === null` is false and every
  // downstream reader treats the two the same way except the one that turns
  // absence into a score of zero.
  for (const field of [
    'avg_score_pct',
    'ci_pct',
    'perfect_count',
    'partial_count',
    'zero_count',
    'inconsistent_count',
  ]) {
    if (!(field in openaiCompat)) {
      throw new Error(`schema ${version} headline ${field} is missing`);
    }
  }
  if (openaiCompat?.avg_score_pct === null || openaiCompat?.ci_pct === null) {
    throw new Error('schema 1.0-1.2 headline must remain numeric');
  }
  if (
    !Number.isFinite(openaiCompat.avg_score_pct)
    || !Number.isFinite(openaiCompat.ci_pct)
  ) {
    throw new Error(`schema ${version} headline must remain numeric`);
  }
  for (const field of [
    'perfect_count',
    'partial_count',
    'zero_count',
    'inconsistent_count',
  ]) {
    if (!Number.isInteger(openaiCompat[field]) || openaiCompat[field] < 0) {
      throw new Error(`schema ${version} ${field} is invalid`);
    }
  }
}

// ── Grading cost receipts (schema 1.4) ────────────────────────────────────
//
// The grade JSON is the only place a per-task grading cost is recorded, so
// the aggregator is where it enters the dashboard. Two rules hold the whole
// feature together:
//
//   * Version-gated, never sniffed. A 1.0-1.3 grade file reads exactly as it
//     read before this code existed, so no published experiment changes
//     meaning because a new field arrived.
//   * The run summary is derived here from the per-task receipts rather than
//     copied out of the payload. A headline the rows do not add up to is
//     worse than no headline, and deriving it in one place makes that
//     impossible.

/** Map<task_id, projected receipt> for a cost-carrying grade file. */
function costReceiptsByTask(raw) {
  const receipts = new Map();
  if (!COST_RECEIPT_VERSIONS.includes(raw?.schema_version)) return receipts;
  for (const task of Array.isArray(raw.tasks) ? raw.tasks : []) {
    const receipt = projectCostReceipt(
      task?.grading_cost,
      `schema ${raw.schema_version} grading_cost for ${task?.task_id ?? 'unknown task'}`,
    );
    if (receipt !== null) receipts.set(task.task_id, receipt);
  }
  return receipts;
}

/**
 * Run-level grading cost, or null when nothing was recorded.
 *
 * `cost_per_successful_deliverable_usd` stays null on purpose: a per-unit
 * figure belongs to the run that produced the deliverables, not to the run
 * that graded them.
 */
function gradingCostSummary(rawTasks, receipts) {
  return summarizeCostReceipts(
    rawTasks.map((task) => ({
      receipt: receipts.get(task?.task_id) ?? null,
      succeeded: !(task?.error !== null && task?.error !== undefined && task?.error !== ''),
    })),
  );
}

function processV1GradesFile(
  filePath,
  raw,
  taskQaByExperiment = new Map(),
  corpusByExperiment = new Map(),
) {
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

  // Empty for every version below 1.4, which is what keeps already-published
  // grades rendering as "no record" instead of as grading that cost nothing.
  const costReceipts = costReceiptsByTask(raw);

  // Convert v1 tasks → legacy-compatible task rows. Snap pct to exact 0/1
  // when it crosses the openai_compat thresholds (pct >= 99 → perfect,
  // pct <= 1 → zero) so legacy Status badges agree with summary counts.
  const tasks = rawTasks.map((t) => {
    const qa_score = qaFor(t.task_id);
    const hasError = t.error !== null && t.error !== undefined && t.error !== '';
    // Absent stays absent. A task with no receipt gains no key, so the
    // dashboard can tell "not recorded" from "recorded as nothing".
    const cost = costReceipts.has(t.task_id)
      ? { grading_cost: costReceipts.get(t.task_id) }
      : {};
    // Additive: the legacy row keeps every field it had, and gains only the
    // reason it ended where it did. error_messages still carries the raw token
    // so anything already reading it sees no change.
    const { outcome, detail, reached_judge } = classifyTaskOutcome(t);
    if (hasError) {
      return {
        task_id: t.task_id,
        num_grades: 0,
        scores: [],
        avg_score: null,
        error: true,
        error_messages: [String(t.error)],
        outcome,
        outcome_detail: detail,
        reached_judge,
        qa_score,
        ...cost,
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
      outcome,
      outcome_detail: detail,
      reached_judge,
      qa_score,
      ...cost,
    };
  });

  // Decorate raw v1 tasks too — GradeDetail page reads from tasks_v1 directly.
  const tasks_v1 = rawTasks.map((t) => {
    const { outcome, detail, reached_judge, required_formats, format_demand, files } =
      classifyTaskOutcome(t);
    return {
      ...t,
      qa_score: qaFor(t.task_id),
      outcome,
      outcome_detail: detail,
      reached_judge,
      required_formats,
      format_demand,
      candidate_files: files,
      // Overwrites the raw receipt with the projected one, so every consumer
      // reads the same normalised shape the validator vouched for.
      ...(costReceipts.has(t.task_id)
        ? { grading_cost: costReceipts.get(t.task_id) }
        : {}),
    };
  });

  // Why the zeros are zeros. Derived, never authoritative: every count the
  // grade JSON publishes is passed through untouched below, so this block can
  // only add an explanation, never move a number.
  const selection = summarizeOutcomes(rawTasks);

  const costSummary = gradingCostSummary(rawTasks, costReceipts);
  const costLedger = COST_RECEIPT_VERSIONS.includes(raw?.schema_version)
    ? projectCostLedgerReference(raw.cost_ledger)
    : null;

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
      // Both validators above reject a headline this reader cannot trust, so
      // in practice only a real number arrives here. The fall-through is still
      // written as null rather than 0 because it is the last thing between a
      // missing value and the dashboard, and every consumer of this field —
      // GradesSummary, GradingAnalysisView, GradeDetail — already renders null
      // as an em dash. A zero would be indistinguishable from a run that
      // genuinely scored nothing.
      avg_score_pct: typeof openaiCompat.avg_score_pct === 'number'
        ? openaiCompat.avg_score_pct
        : null,
      ci_pct: typeof openaiCompat.ci_pct === 'number' ? openaiCompat.ci_pct : null,
      // What the task rows say the average is, beside what the payload
      // claims. On 1.3/1.4 the validator has already refused any file where
      // these disagree, so it reads as a redundant confirmation; on 1.0-1.2,
      // where four published experiments do disagree, it is the only place
      // the disagreement is written down. Present on every version so a
      // reader never has to know which tier a file came from.
      headline_support: headlineSupport(raw),
      perfect_score: openaiCompat.perfect_count ?? 0,
      partial_score: openaiCompat.partial_count ?? 0,
      zero_score: openaiCompat.zero_count ?? 0,
      inconsistent_grades: openaiCompat.inconsistent_count ?? 0,
      calibration_mae,
      calibration_counts,
    },
    coverage: buildCoverage(experiment_id, totalTasks, corpusByExperiment),
    tasks,
    // v1.0 provenance + full payload (for WOW dashboard components)
    judge: raw.judge,
    rubric: raw.rubric,
    prompt: raw.prompt,
    graded_at: raw.graded_at,
    summary_v1: {
      ...summary,
      wow,
      openai_compat: openaiCompat,
      calibration_mae,
      calibration_counts,
      selection,
      // Only on a run that recorded something. Absent here is what the
      // dashboard reads as "no record" — never as $0.
      ...(costSummary ? { grading_cost: costSummary } : {}),
    },
    tasks_v1,
    ...(costSummary ? { cost_summary: { grading_cost: costSummary } } : {}),
    ...(costLedger ? { cost_ledger: costLedger } : {}),
  };
}

export function processGradesFile(
  filePath,
  raw,
  taskQaByExperiment = new Map(),
  corpusByExperiment = new Map(),
) {
  // All item-level 1.x payloads share the rich grade projection. Later minor
  // versions add provenance contracts without changing dashboard score shape.
  if (raw && ITEM_LEVEL_VERSIONS.includes(raw.schema_version)) {
    return processV1GradesFile(filePath, raw, taskQaByExperiment, corpusByExperiment);
  }
  return processLegacyGradesFile(filePath, raw, taskQaByExperiment, corpusByExperiment);
}

export function isPublishableGrade(result) {
  return !['grading_partial', 'grading_diagnostic'].includes(
    result?.grade_status,
  );
}

// A published `cost_ledger.path` has to name a file this repository actually
// holds. The field is defined as a relative repository path — in the grade
// schema, in `core/cost_projection.py`, and in `projectCostLedgerReference`
// above — and for a long while both grading writers put `Path.name` in it: a
// bare filename. None of the thirty-eight grade files carrying the field
// resolved from the repository root; the sidecars were sitting beside their
// grades several directories down, and the record built here drops the
// directory, so the one reader that could have reconstructed the location is
// the one reader that cannot.
//
// Checked here rather than in `processGradesFile` because this is the layer
// that knows the payload came off this disk. A pointer that resolves nowhere
// is worse than no pointer: it reads as an audit trail that exists.
function ledgerIsOnDisk(relativePath) {
  try {
    return statSync(join(ROOT, relativePath)).isFile();
  } catch {
    return false;
  }
}

// Separates the two reasons a grade file can be absent from the index, because
// only one of them is a decision:
//
//   excluded — the grader itself labelled the run grading_partial or
//              grading_diagnostic. Not for publication, on purpose.
//   failures — the file could not be parsed, or a validator refused it. Nobody
//              decided that. The run is real and its absence is a hole.
//
// Every entry is attempted before the caller is told anything, so one run names
// every broken file rather than stopping at the first. `main` throws when
// `failures` is non-empty; see the comment at the throw site for why silence
// there was worse than a crash.
export function collectGrades(
  entries,
  taskQaByExperiment = new Map(),
  corpusByExperiment = new Map(),
) {
  const results = [];
  const failures = [];
  const excluded = [];
  for (const { file, content } of entries) {
    let processed;
    try {
      processed = processGradesFile(
        file,
        JSON.parse(content),
        taskQaByExperiment,
        corpusByExperiment,
      );
    } catch (err) {
      failures.push({ file, message: err?.message ?? String(err) });
      continue;
    }
    const ledgerPath = processed?.cost_ledger?.path;
    if (ledgerPath && !ledgerIsOnDisk(ledgerPath)) {
      failures.push({
        file,
        message: `cost_ledger points at ${ledgerPath}, which is not a file in `
          + 'this repository; the pointer must be a path from the repository '
          + 'root, not a bare filename',
      });
      continue;
    }
    if (!isPublishableGrade(processed)) {
      excluded.push({ file, status: processed.grade_status });
      continue;
    }
    results.push(processed);
  }
  return { results, failures, excluded };
}

// ── reports-index lookups ─────────────────────────────────────────────────
// Both maps below are derived from the same file. Missing or unreadable ⇒
// empty maps, which degrade to "no qa_score" and "coverage unknown" rather
// than to a guess.
async function readReportsIndex() {
  const indexPath = join(OUTPUT_DIR, 'reports-index.json');
  try {
    return JSON.parse(await readFile(indexPath, 'utf-8'));
  } catch (err) {
    // ENOENT = file not yet generated (first build, fresh repo) — silent fallback.
    // Other errors (parse failure, permission, etc.) deserve a warning so they
    // are not silently masked as "no qa_score available".
    if (err && err.code !== 'ENOENT') {
      console.warn(`⚠️  reports-index.json unreadable (${err.message}); all qa_score will be null.`);
    }
    return null;
  }
}

// Build Map<experiment_id, Record<task_id, qa_score>> from reports-index.json.
// STRICT: reports-index is the only source. No fallback to batch-runner/results/
// — the previous global-task_id map produced incorrect cross-experiment matches
// because GDPVal task_ids are shared across all experiments running the same
// dataset. Missing reports-index ⇒ empty Map ⇒ all qa_score = null.
function buildTaskQaByExperiment(rawIndex) {
  const map = new Map();
  for (const report of rawIndex?.reports ?? []) {
    const expId = report?.meta?.experiment_id;
    if (expId && report.task_qa && typeof report.task_qa === 'object') {
      map.set(expId, report.task_qa);
    }
  }
  return map;
}

// Build Map<experiment_id, corpus size> — the task count the inference run
// itself published. This is the denominator a grade's coverage is measured
// against, so it is read from the report and never inferred from the grade.
function buildCorpusByExperiment(rawIndex) {
  const map = new Map();
  for (const report of rawIndex?.reports ?? []) {
    const expId = report?.meta?.experiment_id;
    const total = report?.summary?.total_tasks;
    if (expId && Number.isInteger(total) && total > 0) {
      map.set(expId, total);
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

  // Build experiment_id → task_qa and experiment_id → corpus size lookups once
  // for all grade files. Strict per-experiment matching; reports-index.json is
  // the sole source.
  const reportsIndex = await readReportsIndex();
  const taskQaByExperiment = buildTaskQaByExperiment(reportsIndex);
  const corpusByExperiment = buildCorpusByExperiment(reportsIndex);
  const totalQaTasks = Array.from(taskQaByExperiment.values())
    .reduce((n, m) => n + Object.keys(m).length, 0);
  console.log(`ℹ️  task_qa lookup built: ${taskQaByExperiment.size} experiment(s), ${totalQaTasks} task(s)`);
  console.log(`ℹ️  corpus lookup built: ${corpusByExperiment.size} experiment(s)`);

  const entries = [];
  for (const file of jsonFiles) {
    entries.push({ file, content: await readFile(join(GRADES_DIR, file), 'utf-8') });
  }
  const { results, failures, excluded } = collectGrades(
    entries,
    taskQaByExperiment,
    corpusByExperiment,
  );
  for (const { file, status } of excluded) {
    console.warn(`⚠️  ${file} is ${status}; excluded from dashboard`);
  }
  if (failures.length > 0) {
    const detail = failures.map(({ file, message }) => `  ${file}: ${message}`).join('\n');
    // This used to be `console.error(...)` inside the loop, so a grade file the
    // validators refused was written to the log and then dropped: the build
    // stayed green and grades-index.json came out one experiment shorter, which
    // is indistinguishable from a corpus that never had that experiment in it.
    // The same instinct is already written down in aggregate-reports.mjs, at
    // the throw for duplicate short_ids -- "fail here rather than emit a quietly
    // wrong index". Throwing reaches main().catch below and exits non-zero, so
    // deploy.yml stops instead of publishing the hole.
    throw new Error(
      `${failures.length} of ${jsonFiles.length} grade file(s) could not be read:\n${detail}\n`
        + 'Fix or remove the file. Publishing the remaining files would hide it.',
    );
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
    // Naming a partial run in the build log is the only place the exclusion is
    // visible to whoever ran the aggregation; the card itself just vanishes.
    const partial = r.coverage?.is_partial_corpus
      ? ` [PARTIAL ${r.coverage.grade_tasks}/${r.coverage.corpus_tasks} corpus]`
      : '';
    const headline = r.summary.avg_score_pct == null
      ? 'unscored'
      : `${r.summary.avg_score_pct}% avg`;
    console.log(`   ${r.id}: ${headline} (${r.summary.graded_tasks}/${r.summary.total_tasks} tasks)${dummy}${v1}${partial}`);
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
