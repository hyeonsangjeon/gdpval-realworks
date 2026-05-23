#!/usr/bin/env node

// aggregate-reports.mjs
// Load all batch-runner/results/*/report/report_data.json files
// and generate public/generated/reports-index.json

import { readdir, readFile, writeFile, mkdir } from 'fs/promises';
import { join } from 'path';

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
// exp003_GPT52Chat_baseline_runner_exec -> exp003
function extractShortId(dirName) {
  const match = dirName.match(/^(exp\d+)/);
  return match ? match[1] : null;
}

// Load all reports
async function loadAllReports() {
  const subdirs = await readdir(RESULTS_DIR, { withFileTypes: true });
  const reports = [];
  const errors = [];

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
    } catch (err) {
      errors.push(`${subdir.name}: ${err.message}`);
    }
  }

  if (errors.length > 0) {
    console.warn(`Warning: ${errors.length} reports failed to load:`);
    errors.forEach(e => console.warn(`   ${e}`));
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

main();
