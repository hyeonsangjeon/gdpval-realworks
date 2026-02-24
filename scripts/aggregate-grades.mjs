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

const ROOT = new URL('..', import.meta.url).pathname;
const GRADES_DIR = join(ROOT, 'data', 'grades');
const OUTPUT_DIR = join(ROOT, 'public', 'generated');

async function dirExists(path) {
  try { await access(path); return true; } catch { return false; }
}

function processGradesFile(filePath, raw) {
  const filename = basename(filePath, '.json');
  const meta = raw._meta || {};
  const tasks = raw.tasks || raw; // support both { _meta, tasks } and bare array

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

  return {
    id: filename,
    is_dummy: !!meta.is_dummy,
    label: meta.label || filename,
    model: meta.model || 'Unknown',
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
    },
    tasks,
  };
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

  const results = [];
  for (const file of jsonFiles) {
    const content = await readFile(join(GRADES_DIR, file), 'utf-8');
    try {
      const data = JSON.parse(content);
      results.push(processGradesFile(file, data));
    } catch (err) {
      console.error(`⚠️  ${file} 파싱 실패:`, err.message);
    }
  }

  await mkdir(OUTPUT_DIR, { recursive: true });
  await writeFile(
    join(OUTPUT_DIR, 'grades-index.json'),
    JSON.stringify(results, null, 2),
  );

  console.log(`✅ Aggregated ${results.length} grade file(s) → grades-index.json`);
  for (const r of results) {
    const dummy = r.is_dummy ? ' [DUMMY]' : '';
    console.log(`   ${r.id}: ${r.summary.avg_score_pct}% avg (${r.summary.graded_tasks}/${r.summary.total_tasks} tasks)${dummy}`);
  }
}

main().catch(err => { console.error(err); process.exit(1); });
