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

/**
 * Load a single report: try local report_data.json first, then HF self_report.json.
 */
async function fetchReportData(dirName, reportPath) {
  try {
    const content = await readFile(reportPath, 'utf-8');
    return { data: JSON.parse(content), source: 'local' };
  } catch {}

  // Fallback: HuggingFace self_report.json
  const hfUrl = `https://huggingface.co/datasets/${HF_USER}/${dirName}/resolve/main/self_report.json`;
  const res = await fetch(hfUrl);
  if (!res.ok) throw new Error(`local: not found, HF: HTTP ${res.status}`);
  return { data: await res.json(), source: 'hf' };
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
async function loadAllReports() {
  const subdirs = await readdir(RESULTS_DIR, { withFileTypes: true });
  const reports = [];
  const errors = [];
  const loadedDirs = [];

  for (const subdir of subdirs) {
    if (!subdir.isDirectory()) continue;

    const shortId = extractShortId(subdir.name);
    if (!shortId) continue;

    const reportPath = join(RESULTS_DIR, subdir.name, 'report', 'report_data.json');

    try {
      const { data, source } = await fetchReportData(subdir.name, reportPath);
      if (source === 'hf') console.log(`  ↓ ${subdir.name}: fetched from HuggingFace`);

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
      loadedDirs.push(subdir.name);
    } catch (err) {
      errors.push(`${subdir.name}: ${err.message}`);
    }
  }

  if (errors.length > 0) {
    console.warn(`Warning: ${errors.length} reports failed to load:`);
    errors.forEach(e => console.warn(`   ${e}`));
  }

  // Two reports sharing a short_id is silently destructive rather than merely
  // redundant: generateCrossExperiment() writes sectorMap[sector][short_id], so
  // whichever report is processed last overwrites the other's sector cells, and
  // the dashboard then renders one experiment's numbers under both names. Fail
  // here rather than emit a quietly wrong index.
  const collisions = findShortIdCollisions(loadedDirs);
  if (collisions.length > 0) {
    const detail = collisions
      .map(([id, dirs]) => `  ${id} <- ${dirs.join(' , ')}`)
      .join('\n');
    throw new Error(
      `duplicate short_id across batch-runner/results directories:\n${detail}\n` +
        'Rename one of the directories so each report has a distinct short_id.',
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
