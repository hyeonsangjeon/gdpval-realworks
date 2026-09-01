#!/usr/bin/env node

// aggregate-reports.mjs
// Load all batch-runner/results/*/report/report_data.json files
// and generate public/generated/reports-index.json

import { readdir, readFile, writeFile, mkdir } from 'fs/promises';
import { join, resolve } from 'path';
import { fileURLToPath } from 'url';

const ROOT = new URL('..', import.meta.url).pathname;
const RESULTS_DIR = join(ROOT, 'batch-runner', 'results');
const OUTPUT_DIR = join(ROOT, 'public', 'generated');
const HF_USER = 'HyeonSang';

// A local report that is present but unreadable is a defect, not an absence.
// Only ENOENT means "this experiment publishes from HuggingFace"; a truncated
// file or a permission error used to fall through to the network too, where a
// remote copy silently stood in for the broken local one — while the log said
// `local: not found` about a file that was sitting right there.
async function readLocalReport(reportPath) {
  let content;
  try {
    content = await readFile(reportPath, 'utf-8');
  } catch (err) {
    if (err?.code === 'ENOENT') return null;
    throw new Error(`local report_data.json could not be read: ${err.message}`);
  }
  try {
    return JSON.parse(content);
  } catch (err) {
    throw new Error(`local report_data.json is present but is not valid JSON: ${err.message}`);
  }
}

// Every one of these fetches is unauthenticated — there is no HuggingFace token
// anywhere in the Pages build — which is the tier with the tightest rate limits,
// and a 429 from the hub is a documented recurring flake on this repository.
//
// A hole in the index and a hiccup on the wire both used to end the same way: the
// report was dropped and the build went green. They are not the same failure, so
// the hiccup is retried here before it is allowed to become one, and only a
// report that is still unreachable afterwards stops the build.
export const TRANSIENT_HTTP_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
const HF_ATTEMPTS = 3;
const HF_BACKOFF_MS = 1000;
const HF_BACKOFF_CAP_MS = 20000;

// Honour Retry-After when the hub sends one, but never wait longer than the cap:
// an unbounded header would hang the deploy instead of failing it.
function backoffMs(res, attempt) {
  const advised = Number(res?.headers?.get?.('retry-after'));
  const fromHeader = Number.isFinite(advised) && advised > 0 ? advised * 1000 : 0;
  return Math.min(
    Math.max(fromHeader, HF_BACKOFF_MS * 2 ** (attempt - 1)),
    HF_BACKOFF_CAP_MS,
  );
}

const sleepMs = (ms) => new Promise((done) => setTimeout(done, ms));

// `deps` exists so the retry rule can be tested without a network or a real
// wait. Production passes nothing and takes the real fetch and the real clock.
export async function fetchHuggingFaceReport(dirName, deps = {}) {
  const doFetch = deps.fetch ?? globalThis.fetch;
  const sleep = deps.sleep ?? sleepMs;
  const attempts = deps.attempts ?? HF_ATTEMPTS;
  const url = `https://huggingface.co/datasets/${HF_USER}/${dirName}/resolve/main/self_report.json`;

  let lastFailure = 'no attempt was made';
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    let res;
    try {
      res = await doFetch(url);
    } catch (err) {
      lastFailure = `network error: ${err.message}`;
      if (attempt === attempts) break;
      await sleep(backoffMs(null, attempt));
      continue;
    }

    if (res.ok) {
      try {
        return await res.json();
      } catch (err) {
        throw new Error(`HuggingFace body is not valid JSON: ${err.message}`);
      }
    }

    lastFailure = `HTTP ${res.status}`;
    if (!TRANSIENT_HTTP_STATUS.has(res.status)) break;
    if (attempt === attempts) break;
    await sleep(backoffMs(res, attempt));
  }

  throw new Error(`no local report_data.json, and HuggingFace answered ${lastFailure}`);
}

/**
 * Load a single report: local report_data.json first, then HF self_report.json.
 */
export async function fetchReportData(dirName, reportPath, deps = {}) {
  const local = await readLocalReport(reportPath);
  if (local !== null) return { data: local, source: 'local' };
  return { data: await fetchHuggingFaceReport(dirName, deps), source: 'hf' };
}

// Extract short_id from directory name
//   exp003_GPT52Chat_baseline_runner_exec -> exp003
//   exp026c_cost_receipt_smoke            -> exp026c
//
// The trailing [a-z]* is what keeps a variant suffix distinct. Without it every
// exp026* directory collapses onto `exp026`, which is destructive twice over:
// generateCrossExperiment() keys the sector matrix by short_id, so the later
// report silently overwrites the real exp026's cells; and
// src/lib/runtimeNoteBenchmark.ts requires exactly one report per pinned id, so
// the runtime note degrades to `invalid`.
//
// Every directory that exists today is `exp\d+_...`, so [a-z]* matches empty and
// every current short_id is byte-identical to what the narrower pattern produced.
export function extractShortId(dirName) {
  const match = dirName.match(/^(exp\d+[a-z]*)/);
  return match ? match[1] : null;
}

// Group directory names by the short_id they resolve to and return only the
// groups holding more than one directory. Pure and side-effect free so the
// collision rule can be tested without touching the filesystem or the network.
export function findShortIdCollisions(dirNames) {
  const byShortId = new Map();
  for (const dirName of dirNames) {
    const shortId = extractShortId(dirName);
    if (!shortId) continue;
    byShortId.set(shortId, [...(byShortId.get(shortId) ?? []), dirName]);
  }
  return [...byShortId.entries()].filter(([, dirs]) => dirs.length > 1);
}

// Load all reports
async function loadAllReports(deps = {}) {
  const subdirs = await readdir(RESULTS_DIR, { withFileTypes: true });

  const candidates = [];
  for (const subdir of subdirs) {
    if (!subdir.isDirectory()) continue;
    const shortId = extractShortId(subdir.name);
    if (!shortId) continue;
    candidates.push({ dirName: subdir.name, shortId });
  }

  // Two reports sharing a short_id is silently destructive rather than merely
  // redundant: generateCrossExperiment() writes sectorMap[sector][short_id], so
  // whichever report is processed last overwrites the other's sector cells, and
  // the dashboard then renders one experiment's numbers under both names. Fail
  // here rather than emit a quietly wrong index.
  //
  // Checked over every candidate directory, not over the ones that happened to
  // load. This guard used to run on the survivors, so a report that failed to
  // load took one side of its own collision away with it and the check passed.
  // It also runs before the fetch loop now: a rename mistake is answered in
  // milliseconds instead of after twenty-three network round trips.
  const collisions = findShortIdCollisions(candidates.map(({ dirName }) => dirName));
  if (collisions.length > 0) {
    const detail = collisions
      .map(([id, dirs]) => `  ${id} <- ${dirs.join(' , ')}`)
      .join('\n');
    throw new Error(
      `duplicate short_id across batch-runner/results directories:\n${detail}\n` +
        'Rename one of the directories so each report has a distinct short_id.',
    );
  }

  const reports = [];
  const failures = [];

  for (const { dirName, shortId } of candidates) {
    const reportPath = join(RESULTS_DIR, dirName, 'report', 'report_data.json');

    let data;
    let source;
    try {
      ({ data, source } = await fetchReportData(dirName, reportPath, deps));
    } catch (err) {
      failures.push(`  ${dirName}: ${err.message}`);
      continue;
    }

    if (source === 'hf') console.log(`  ↓ ${dirName}: fetched from HuggingFace`);

    // Extract compact qa map (task_id → qa_score) before stripping the heavy task_results array.
    // Used by aggregate-grades.mjs for per-experiment Self-QA ↔ Rubric calibration join.
    const taskQa = {};
    for (const t of (data.task_results ?? [])) {
      if (t.task_id && t.qa_score != null) taskQa[t.task_id] = t.qa_score;
    }

    // Strip task_results — heavy per-task data is lazy-loaded from HuggingFace on the detail page
    const { task_results: _ignored, ...indexEntry } = data;
    indexEntry.task_qa = taskQa;
    indexEntry.short_id = shortId;

    reports.push(indexEntry);
  }

  // These used to be a console.warn and nothing else. The index was written one
  // experiment short, `✓ Found N reports` printed a checkmark beside a number
  // that had quietly shrunk, and the build exited 0. Only seven of the
  // twenty-three short_ids are pinned by a note benchmark, so sixteen of them
  // could disappear from the leaderboard, the trend view and the sector matrix
  // without a single reader being told.
  if (failures.length > 0) {
    throw new Error(
      `${failures.length} of ${candidates.length} report(s) could not be loaded:\n`
        + `${failures.join('\n')}\n`
        + 'Publishing the rest would drop them from the leaderboard, the trend view '
        + 'and the sector matrix without saying so. If HuggingFace rate-limited this '
        + 'build, re-run it; otherwise fix or remove the directory.',
    );
  }

  // Sort by date (newest first)
  reports.sort((a, b) => {
    const dateA = new Date(a.meta.date);
    const dateB = new Date(b.meta.date);
    return dateB - dateA;
  });

  return reports;
}

// Generate cross-experiment analysis
function generateCrossExperiment(reports) {
  // Experiment summary for leaderboard
  const experiments = reports.map(r => ({
    short_id: r.short_id,
    experiment_name: r.meta.experiment_name || '',
    model: r.meta.model,
    execution_mode: r.meta.execution_mode || 'unknown',
    condition: r.meta.condition_name,
    success_rate_pct: r.summary.success_rate_pct,
    avg_qa_score: r.summary.avg_qa_score,
    total_tasks: r.summary.total_tasks,
    success_count: r.summary.success_count,
    retried_count: r.summary.retried_count || 0,
    date: r.meta.date,
    duration: r.meta.duration,
    report_scope: r.meta.report_scope,
  }));

  // Generate sector x experiment matrix
  const sectors = new Set();
  const sectorMap = {};

  reports.forEach(report => {
    report.sector_breakdown?.forEach(sector => {
      sectors.add(sector.sector);
      if (!sectorMap[sector.sector]) {
        sectorMap[sector.sector] = {};
      }
      sectorMap[sector.sector][report.short_id] = {
        success_rate_pct: sector.success_rate_pct,
        avg_qa_score: sector.avg_qa_score,
        success: sector.success,
        total: sector.total,
      };
    });
  });

  // Sort results
  const sector_matrix = {};
  Array.from(sectors)
    .sort()
    .forEach(sector => {
      sector_matrix[sector] = sectorMap[sector];
    });

  return { experiments, sector_matrix };
}

// Main function
async function main() {
  try {
    // Create output directory
    await mkdir(OUTPUT_DIR, { recursive: true });

    // Load reports
    const reports = await loadAllReports();
    console.log(`✓ Found ${reports.length} reports`);

    if (reports.length === 0) {
      console.warn('Warning: No reports found. Skipping generation.');
      return;
    }

    // Generate cross-experiment analysis
    const cross_experiment = generateCrossExperiment(reports);

    // Create final index
    const index = {
      reports,
      cross_experiment,
      _generated: new Date().toISOString(),
    };

    // Save file
    const outputPath = join(OUTPUT_DIR, 'reports-index.json');
    await writeFile(outputPath, JSON.stringify(index, null, 2));
    console.log(`✓ Created: ${outputPath}`);
    console.log(`  Experiments: ${cross_experiment.experiments.length}`);
    console.log(`  Sectors: ${Object.keys(cross_experiment.sector_matrix).length}`);
  } catch (err) {
    console.error('Error:', err);
    process.exit(1);
  }
}

// Only run the aggregation when invoked directly, so scripts/__tests__/ can
// import the pure helpers above without triggering a full run (which reads the
// filesystem and falls back to the network).
if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main();
}
