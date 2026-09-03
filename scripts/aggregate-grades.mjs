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

// The thresholds the grading backend actually counts `openai_compat`'s
// `perfect_count` and `zero_count` at. They are NOT 100 and 0. A task that
// scored 99.77% is inside `perfect_count`; one that scored 0.9% is inside
// `zero_count`. `step8_grade.py` has published them this way since the field
// existed, and PR #371 fixed the backend's wording to match rather than moving
// the boundary, because the counts are already published. Exported so the
// labels that describe these counts, and the tests over them, read the
// boundary instead of restating it from memory.
export const NEAR_PERFECT_MIN_PCT = 99;
export const NEAR_ZERO_MAX_PCT = 1;

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
// times that. The four real disagreements under `data/grades` run from 0.23 to
// 1.26 points, so the narrowest of them is twenty-three times the rounding
// bound and four times this tolerance, and no plausible widening of the
// tolerance admits the rounding and the defect together.
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

// ── The denominator a judge_error takes with it ───────────────────────────
//
// An item the judge could not read leaves the numerator and the denominator
// together, so the task is scored out of less than its rubric is worth and
// the percentage rises. The widest case on the dashboard today is task
// f1be6436 of the sol regrade: 24 points earned, 45 points of rubric read,
// and 29 further points across 17 items the judge never reached. It arrives
// here as `pct: 54.22` and the screen prints 54%. Those same 24 points out of
// the whole 74-point rubric are 32.97%. Nothing said so.
//
// (The gold-ceiling corpora hold worse ones still, but those files are
// `grading_diagnostic` and `isPublishableGrade` keeps them off the board, so
// they are not what a reader is being misled by.)
//
// Neither number is wrong. `pct` divides by what was read, which assumes an
// unread item would have scored like the read ones. The full denominator
// divides by the whole rubric, which assumes an unread item would have scored
// nothing. The task's true percentage lies between them, and the two are one
// number only when nothing was excluded.
//
// So both travel, and `avg_score` is left exactly as it was. Changing the
// published figure here would silently restate every score already on the
// board, which is a decision about the benchmark rather than one for a reader
// to make on the way to the screen.

/**
 * What a task's excluded items did to its denominator, or null if nothing did.
 *
 * Absent stays absent: a task that lost nothing gains no key, so the dashboard
 * can tell "the denominator held" from "nobody looked".
 *
 * Two sources, in order. A payload written since the producer learned to
 * report this carries `pct_full_denominator` itself and is believed. Older
 * payloads are recomputed from their items, which is why the already-published
 * runs surface at all -- every 1.3/1.4 file on the board predates that writer,
 * and `validateScoreExcludedGrade` has already enforced there that an excluded
 * item and a judge_error are the same thing. Below 1.3 the flag may be absent,
 * so the verdict stands in for it.
 */
function scoreExclusionForTask(task) {
  const items = Array.isArray(task?.items) ? task.items : [];
  const excluded = items.filter((item) => (
    item?.score_excluded === true || item?.verdict === 'judge_error'
  ));
  if (excluded.length === 0) return null;

  const excludedMax = excluded.reduce((total, item) => (
    total + Math.max(0, Number.isFinite(item?.max_score) ? item.max_score : 0)
  ), 0);
  // Items can carry a non-positive max_score (penalty criteria), and losing
  // one of those moves no denominator. Reporting it would put a badge on a
  // task whose score did not shift by so much as a rounding step.
  if (excludedMax <= 0) return null;

  const awarded = Number.isFinite(task?.total_awarded) ? task.total_awarded : null;
  const readMax = Number.isFinite(task?.total_max) ? task.total_max : null;
  // No published percentage, nothing to qualify. This is the whole-task
  // failure case: when every item was excluded the producer leaves the task
  // unscored, the dashboard already prints a dash, and there is no inflated
  // number here for a second one to stand beside.
  if (!Number.isFinite(task?.pct)) return null;
  const published = task.pct;

  let full = Number.isFinite(task?.pct_full_denominator)
    ? task.pct_full_denominator
    : null;
  if (full === null) {
    if (awarded === null || readMax === null) return null;
    const fullMax = readMax + excludedMax;
    // A rubric can carry penalty criteria heavy enough to drive the whole
    // denominator to zero or below. Task c94452e4 on the board today is one:
    // a -60 item leaves it with `total_max: -10`, and dividing its 34.72
    // points by that would put "-868%" on screen beside a published 0%. There
    // is no honest second number to compute here, so none is offered.
    if (fullMax <= 0) return null;
    full = Math.max(0, Math.min(100, (awarded / fullMax) * 100));
  }

  // The denominator moved and the score did not. A task that earned nothing
  // is 0% out of what was read and 0% out of the whole rubric, so its
  // published figure was never inflated and there is no range to show; 66 of
  // the 303 affected rows on the board are exactly this, and one more is a
  // task already clamped to 100%. Reporting them would print "somewhere
  // between 0% and 0%" beside a zero. That the items went missing is still on
  // the record, in `summary.wow.judge_error_rate`, which is where a reader
  // asks how much of the rubric was read rather than what the reading was
  // worth.
  const rounded = Math.round(full * 100) / 100;
  if (rounded === published) return null;

  return {
    items: excluded.length,
    excluded_max: Math.round(excludedMax * 100) / 100,
    read_max: readMax,
    pct_published: published,
    pct_full_denominator: rounded,
  };
}

/**
 * Map<task_id, exclusion> for every task in an item-level grade file whose
 * denominator actually moved. Tasks that lost nothing are simply absent.
 *
 * Gated on the version list rather than sniffed for `items`, so a payload
 * shape the projection has never validated cannot quietly acquire a second
 * headline number on the strength of a key that happens to be spelled the
 * same.
 */
function scoreExclusionsByTask(raw) {
  const exclusions = new Map();
  if (!ITEM_LEVEL_VERSIONS.includes(raw?.schema_version)) return exclusions;
  for (const task of Array.isArray(raw.tasks) ? raw.tasks : []) {
    const exclusion = scoreExclusionForTask(task);
    if (exclusion !== null) exclusions.set(task.task_id, exclusion);
  }
  return exclusions;
}

/**
 * How much the run's own average is lifted by the items its judge could not
 * read, or null if nothing was excluded.
 *
 * The per-task pair above is on the board already, but only inside the task
 * table, and only one row at a time. Nothing said what the *headline* — the
 * one number an experiment is remembered by — owed to the same effect. Twelve
 * of the nineteen grade files under `data/grades` have a headline that moved
 * this way, and a reader comparing two experiments had no way to see it.
 *
 * Measured against `avg_score_pct_from_rows` rather than against the published
 * headline, and that is the whole care of this function. Two different defects
 * move these runs' averages in opposite directions: an item the judge could
 * not read leaves the denominator and lifts the score, while a task it could
 * not grade stays in the denominator as a zero and lowers it. Four published
 * 1.0 files carry the second, by 0.23 to 1.26 points. Subtracting a
 * full-denominator row mean from a published headline would report the two
 * added together as though both were this one, and on the worst of those four
 * it flips the sign: 54.10 published against 55.36 from the rows and 54.82 out
 * of the whole rubrics is a lift of +0.53, which the naive subtraction reports
 * as −0.72. Both figures here are means over one row set, so their difference
 * isolates exactly the excluded items — and `headline_support`, computed over
 * the same rows, carries the other.
 *
 * Every value averaged is the same value the task table shows for that row, so
 * the headline figure and the rows underneath it cannot tell different
 * stories. That also means the three cases `scoreExclusionForTask` declines to
 * report — a non-positive full denominator, a rubric of penalties only, a
 * second number that rounds onto the first — fall back to the published `pct`
 * here too. They understate the lift rather than overstate it.
 */
function scoreExclusionLift(raw) {
  if (!ITEM_LEVEL_VERSIONS.includes(raw?.schema_version)) return null;

  // The row predicate `headlineSupport` uses, for the reason it gives there:
  // measuring a different row set than the one being summarised is how the
  // two numbers drift apart.
  const published = [];
  const full = [];
  let tasksAffected = 0;
  let excludedItems = 0;
  let excludedMax = 0;

  for (const task of Array.isArray(raw.tasks) ? raw.tasks : []) {
    if (!task || typeof task !== 'object' || Array.isArray(task) || task.error) continue;
    if (!Number.isFinite(task.pct)) continue;
    published.push(task.pct);
    const exclusion = scoreExclusionForTask(task);
    if (exclusion === null) {
      full.push(task.pct);
      continue;
    }
    tasksAffected += 1;
    excludedItems += exclusion.items;
    excludedMax += exclusion.excluded_max;
    full.push(exclusion.pct_full_denominator);
  }

  // Null rather than a zeroed object. A `lift_pct: 0` on every run would put
  // the caveat on the board wholesale and invite a reader to compare zeros
  // that mean different things. Both ways of arriving here — the denominator
  // held, or no row was scored at all — leave the dashboard nothing to say
  // about unread rubric, and it says nothing.
  if (tasksAffected === 0 || published.length === 0) return null;

  const mean = (xs) => xs.reduce((sum, x) => sum + x, 0) / xs.length;
  const fromRows = mean(published);
  const fullDenominator = mean(full);

  // The producer learned to write this run-level figure in #362 (77ec989).
  // None of the nineteen files the aggregator reads carries it; one grade file
  // further down `data/grades` already does, so this is a payload that exists
  // rather than one that might. It is recomputed from the same items by the
  // same rule, so the two should agree to rounding. Reported three-valued
  // rather than silently preferring one of them: `null` means the payload made
  // no claim, and is not the same statement as `true`.
  const claimed = raw?.summary?.score_exclusions?.avg_score_pct_full_denominator;
  const payloadAgrees = Number.isFinite(claimed)
    ? Math.abs(claimed - fullDenominator) <= HEADLINE_ROW_TOLERANCE_PCT
    : null;

  return {
    tasks_affected: tasksAffected,
    tasks_counted: published.length,
    excluded_items: excludedItems,
    excluded_max: Math.round(excludedMax * 100) / 100,
    avg_score_pct_from_rows: Number(fromRows.toFixed(2)),
    avg_score_pct_full_denominator: Number(fullDenominator.toFixed(2)),
    lift_pct: Number((fromRows - fullDenominator).toFixed(2)),
    payload_agrees: payloadAgrees,
  };
}

/**
 * The routes `step8_grade._ROUTING_MODALITIES` names, sorted the way the
 * producer sorts them. A route the producer knows about but this run never used
 * is a measured zero and is listed; a route neither side knows about but that
 * appears on an item is added rather than dropped, so a modality introduced
 * upstream shows up here before anything downstream has been taught the word.
 */
const ROUTE_NAMES = ['audio', 'formatting', 'mixed', 'text', 'visual'];

/**
 * Which sub-judge decided how much of this run.
 *
 * The question this answers is not academic. The audio sub-judge was measured
 * against synthetic clips whose answers were known and scored a discrimination
 * of 0.00 — it answered no better than a coin, with higher confidence when it
 * was wrong. "How much of this average rests on that route" is therefore a
 * thing a reader needs before quoting the average, and until now it was
 * obtainable only by downloading the payload and counting items by hand.
 *
 * `step8_grade._routing_stats` computes exactly this, and its docstring
 * promises that a payload published before the field existed "reports the same
 * numbers when it is re-summarised". Not one of the grade files here carries
 * it — it post-dates all of them — so this recomputes it from the same items by
 * the same rule rather than waiting for a re-grade to backfill a disclosure
 * that costs nothing to make now. The scoring predicate is copied deliberately:
 * a task with an `error` is out, an item with `score_excluded` is out, and
 * `scored_max_score` sums positive weight only, all matching
 * `scoreExclusionLift` above. Two summarisers over one payload must not
 * disagree about which items the average is made of.
 *
 * **A route absent from a run that recorded routing is a measured zero. A route
 * absent from a run that recorded none is not.** Of the nineteen files read
 * here, eighteen are item-level and get a composition — seven recorded a route
 * and eleven carry `routing_modality: null` on every item; the nineteenth
 * carries no rubric items at all and gets no composition. Zero-filling those
 * eleven into `audio: 0` would turn "never asked" into "asked and found none" —
 * the one reading this exists to prevent. So `recorded` says which of the two
 * situations a reader is in, and the maps are empty in the second.
 *
 * `unrecorded_failing_items` is here because the missing slice is not a random
 * sample of the run. On the official 220-task grade every one of the 964 items
 * without a route is one the judge failed or errored on, so a share computed
 * over routed items alone is a share of a population that is missing failures.
 * That is stated rather than smoothed over.
 *
 * `audio_in_mixed_items` is the one number the producer does not compute, and
 * it is kept OUTSIDE the route maps rather than folded into `audio` so those
 * maps stay comparable with the producer's. A `mixed` item is counted once,
 * under `mixed`, by both sides — but its `child_grades` can name a route of
 * their own, so an audio child inside a mixed item is audio-decided weight that
 * `audio` does not cover. Across all nineteen files today that count is 0: the
 * 23 mixed items on the board have 72 children between them, every one of them
 * `formatting` or `visual`. It is computed anyway, because a silent 0 that
 * nobody measured and a measured 0 are the distinction this whole field is
 * about, and the day an audio child appears the card should say so rather than
 * quietly under-report.
 */
function routeComposition(raw) {
  if (!ITEM_LEVEL_VERSIONS.includes(raw?.schema_version)) return null;

  const items = {};
  const scoredItems = {};
  const scoredMax = {};
  const taskCounts = {};
  let unrecordedItems = 0;
  let unrecordedFailing = 0;
  let audioInMixed = 0;
  let totalItems = 0;

  for (const task of Array.isArray(raw.tasks) ? raw.tasks : []) {
    if (!task || typeof task !== 'object' || Array.isArray(task)) continue;
    const taskScored = !task.error;
    const seenHere = new Set();
    for (const item of Array.isArray(task.items) ? task.items : []) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
      totalItems += 1;
      const route = item.routing_modality;
      if (typeof route !== 'string' || !route) {
        unrecordedItems += 1;
        if (item.verdict === 'fail' || item.verdict === 'judge_error') {
          unrecordedFailing += 1;
        }
        continue;
      }
      items[route] = (items[route] ?? 0) + 1;
      seenHere.add(route);
      // A parent counted under `mixed` can still have been part-decided by the
      // route in question. Counted separately, never added to `audio`.
      if (route === 'mixed' && Array.isArray(item.child_grades)) {
        const hasAudioChild = item.child_grades.some(
          (child) =>
            child && typeof child === 'object' && child.routing_modality === 'audio',
        );
        if (hasAudioChild) audioInMixed += 1;
      }
      if (taskScored && !item.score_excluded) {
        scoredItems[route] = (scoredItems[route] ?? 0) + 1;
        scoredMax[route] = (scoredMax[route] ?? 0) + Math.max(0, Number(item.max_score) || 0);
      }
    }
    for (const route of seenHere) taskCounts[route] = (taskCounts[route] ?? 0) + 1;
  }

  // Nothing carried a route. Empty maps, not zeroed ones — see above.
  if (Object.keys(items).length === 0) {
    return {
      recorded: false,
      items: {},
      scored_items: {},
      scored_max_score: {},
      tasks: {},
      total_items: totalItems,
      scored_max_score_total: 0,
      unrecorded_items: unrecordedItems,
      unrecorded_failing_items: unrecordedFailing,
      audio_in_mixed_items: audioInMixed,
      payload_agrees: null,
    };
  }

  const names = [...new Set([...ROUTE_NAMES, ...Object.keys(items)])].sort();
  const round4 = (x) => Math.round(x * 10000) / 10000;
  const composition = {
    recorded: true,
    items: Object.fromEntries(names.map((n) => [n, items[n] ?? 0])),
    scored_items: Object.fromEntries(names.map((n) => [n, scoredItems[n] ?? 0])),
    scored_max_score: Object.fromEntries(names.map((n) => [n, round4(scoredMax[n] ?? 0)])),
    tasks: Object.fromEntries(names.map((n) => [n, taskCounts[n] ?? 0])),
    total_items: totalItems,
    scored_max_score_total: round4(
      Object.values(scoredMax).reduce((sum, x) => sum + x, 0),
    ),
    unrecorded_items: unrecordedItems,
    unrecorded_failing_items: unrecordedFailing,
    audio_in_mixed_items: audioInMixed,
    payload_agrees: null,
  };

  // Three-valued against the payload's own claim, for the reason
  // `scoreExclusionLift` gives: `null` means the payload made no claim, and
  // that is not the same statement as `true`. No file read here carries
  // `summary.routing` today; one written after #396 will.
  const claimed = raw?.summary?.routing;
  if (claimed && typeof claimed === 'object' && !Array.isArray(claimed)) {
    composition.payload_agrees =
      claimed.recorded === true &&
      JSON.stringify(claimed.items ?? null) === JSON.stringify(composition.items) &&
      (claimed.unrecorded_items ?? null) === composition.unrecorded_items;
  }
  return composition;
}

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

/** The three counters the legacy block uses to record contacting a provider. */
const LEGACY_CONTACT_COUNTERS = [
  'total_judge_calls',
  'total_input_tokens',
  'total_output_tokens',
];

/**
 * The legacy `summary.cost` block, with a placeholder zero read back as absence.
 *
 * Sixteen of the nineteen published grades carry `estimated_cost_usd: 0.0`
 * here, and every one of them carries real tokens beside it — the largest sits
 * next to 130,092,056 input and 5,523,697 output tokens. That zero is not what
 * the run cost. It is what "nobody could price this" looked like before
 * receipts existed, written by a summariser that filled the field on every
 * path including the ones that had nothing to put in it.
 *
 * The rule it breaks is this repository's oldest one about money
 * (`batch-runner/core/cost_receipts.py`): a missing usage block does not mean a
 * call was free, it means nobody can say what it cost, and the only real $0 is
 * a path that never contacted a provider at all. `measuredAmount` in
 * `scripts/cost-receipt.mjs` already holds the receipt path to exactly this;
 * the spread this feeds was the last place a payload could walk a zero past it.
 *
 * So the test is the contract's own, asked of the block itself: did this run
 * record contacting anyone? Calls and tokens are that record, and all three
 * must be present and zero for the zero to stand. A counter that is merely
 * missing is not a counter that read nothing — the same reasoning one level up,
 * applied to the evidence for the exemption rather than to the amount.
 *
 * Normalised to `null`, not dropped. Absent is the more tempting shape and it
 * is the one this repository has already been bitten by: `undefined !== null`
 * is true, so a reader guarding on `!== null` reaches `.toFixed` on `undefined`
 * and takes the page down (`scripts/cost-receipt.mjs:711-716`). `null` is also
 * what the current writer puts there for a run it could not price
 * (`core/cost_projection.py:810`), so both eras say absence the same way.
 */
function projectLegacyCost(cost) {
  if (!cost || typeof cost !== 'object' || Array.isArray(cost)) return cost;
  if (cost.estimated_cost_usd !== 0) return cost;
  if (LEGACY_CONTACT_COUNTERS.every((field) => cost[field] === 0)) return cost;
  return { ...cost, estimated_cost_usd: null };
}

/**
 * `raw.summary`, as it is allowed to reach the published record.
 *
 * Spreading the payload's summary is how `summary_v1` keeps every field the
 * WOW components read, and it is also how two money shapes get past the
 * projections that exist for them. Both are handled here rather than at the
 * spread, so there is one place that says which of a payload's own numbers
 * this build is willing to republish.
 *
 * `grading_cost` is dropped outright. The rule for it is written at the top of
 * the cost-receipt section: the run summary is derived here from the per-task
 * receipts, never copied out of the payload, because a headline the rows do
 * not add up to is worse than no headline. When this build derives one it is
 * put back below; when it cannot — `summarizeCostReceipts` returns null the
 * moment no task carries a receipt — there is nothing underneath the payload's
 * own figure at all, which is exactly when republishing it is least defensible.
 *
 * Key order is preserved so a regenerated index differs from its predecessor
 * only where a value does.
 */
function projectLegacySummary(summary) {
  const projected = {};
  for (const [key, value] of Object.entries(summary)) {
    if (key === 'grading_cost') continue;
    projected[key] = key === 'cost' ? projectLegacyCost(value) : value;
  }
  return projected;
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

  // Not gated to new payloads: the runs already on the board are exactly the
  // ones whose inflated task scores are visible today, and their items carry
  // enough to recompute the honest denominator.
  const scoreExclusions = scoreExclusionsByTask(raw);

  // Convert v1 tasks → legacy-compatible task rows. Snap pct to exact 0/1
  // when it crosses the openai_compat thresholds (pct >= NEAR_PERFECT_MIN_PCT
  // → perfect, pct <= NEAR_ZERO_MAX_PCT → zero) so legacy Status badges agree
  // with summary counts.
  const tasks = rawTasks.map((t) => {
    const qa_score = qaFor(t.task_id);
    const hasError = t.error !== null && t.error !== undefined && t.error !== '';
    // Absent stays absent. A task with no receipt gains no key, so the
    // dashboard can tell "not recorded" from "recorded as nothing".
    const cost = costReceipts.has(t.task_id)
      ? { grading_cost: costReceipts.get(t.task_id) }
      : {};
    // Same convention, second reason: a task whose denominator held gains no
    // key, so the dashboard shows one number where there is only one.
    const excluded = scoreExclusions.has(t.task_id)
      ? { score_exclusion: scoreExclusions.get(t.task_id) }
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
    // A row with no score is not a row that scored nothing. Reading the
    // absence as 0 would hand the snap below a number the payload never
    // published, and the snap would then mark it unmoved -- so it would arrive
    // at the dashboard as a flat zero with `num_grades: 1`, `scores: [0]` and
    // no `pct_exact` breadcrumb to say the figure was invented. The shape
    // returned here is the `hasError` branch's, minus the claim that an error
    // occurred: no score, no scores array, nothing counted. `score_exclusion`
    // is left off for the same reason it is left off there -- it describes the
    // denominator of a score, and there is no score.
    // Which tier this is for: on 1.3/1.4 a scored task with no finite `pct`
    // already throws in validateScoreExcludedGrade, and that stays the
    // stronger answer -- the file is refused rather than rendered. 1.0-1.2 are
    // checked for the PRESENCE of the headline keys and nothing else, so
    // nothing on that tier looks at a task's own `pct` before this line. The
    // published 1.0-1.2 files all carry one, which is why this has never
    // fired; it is what the aggregator does with the file that does not.
    if (!Number.isFinite(t.pct)) {
      return {
        task_id: t.task_id,
        num_grades: 0,
        scores: [],
        avg_score: null,
        error: false,
        error_messages: [],
        outcome,
        outcome_detail: detail,
        reached_judge,
        qa_score,
        ...cost,
      };
    }
    const pct = t.pct;
    let avgScore;
    // Whether the snap above moved this row, which is not the same question as
    // which branch it took: a task that really did score 100 takes the first
    // branch and is not moved by it.
    let snapped = false;
    if (pct >= NEAR_PERFECT_MIN_PCT) {
      avgScore = 1.0;
      snapped = pct !== 100;
    } else if (pct <= NEAR_ZERO_MAX_PCT) {
      avgScore = 0.0;
      snapped = pct !== 0;
    } else {
      avgScore = pct / 100;
    }
    // Absent stays absent, third use of the convention: the snap buys agreement
    // between badge and count by making the row unable to state its own score,
    // and `avg_score` is now the only number the task table has. Carry the
    // unsnapped figure on exactly the rows the snap moved, so a near miss reads
    // as the 99.8% it was instead of a 100% that never happened. A row the snap
    // left alone gains no key and renders byte-identically to before.
    const exact = snapped ? { pct_exact: pct } : {};
    return {
      task_id: t.task_id,
      num_grades: 1,
      scores: [avgScore],
      avg_score: avgScore,
      ...exact,
      error: false,
      error_messages: [],
      outcome,
      outcome_detail: detail,
      reached_judge,
      qa_score,
      ...cost,
      ...excluded,
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
      // Same projection the legacy row carries, so a consumer that reads
      // tasks_v1 does not have to recompute the denominator itself and reach
      // a slightly different answer.
      ...(scoreExclusions.has(t.task_id)
        ? { score_exclusion: scoreExclusions.get(t.task_id) }
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
      // The same headline read the other way. `headline_support` measures a
      // published average against its rows; this measures those rows against
      // the rubric weight the judge never read. Absent on a run that lost
      // nothing, which is most of the reason it is worth printing when it is
      // present.
      score_exclusion_lift: scoreExclusionLift(raw),
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
      // Every field the WOW components read, minus the two money shapes a
      // payload is not allowed to publish through this spread. See
      // projectLegacySummary.
      ...projectLegacySummary(summary),
      wow,
      openai_compat: openaiCompat,
      calibration_mae,
      calibration_counts,
      selection,
      // Which sub-judge decided how much of this run, recomputed from the
      // items. Always present on an item-level payload, including as
      // `recorded: false` — "this run recorded no route" is the answer to the
      // reader's question, not the absence of one.
      route_composition: routeComposition(raw),
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
