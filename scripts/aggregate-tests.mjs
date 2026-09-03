#!/usr/bin/env node

/**
 * aggregate-tests.mjs
 * 
 * data/tests/*.yaml 파일들을 읽어서 두 가지 산출물을 생성:
 * 1. public/generated/experiments-index.json  → Dashboard UI용
 * 2. public/generated/llm-context.md          → LLM 챗 컨텍스트용
 * 
 * 사용법:
 *   node scripts/aggregate-tests.mjs
 * 
 * package.json에 prebuild 스크립트로 등록하면 빌드 전 자동 실행됨:
 *   "prebuild": "node scripts/aggregate-tests.mjs"
 */

import { readdir, readFile, writeFile, mkdir } from 'fs/promises';
import { join, extname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml } from 'yaml';

const ROOT = new URL('..', import.meta.url).pathname;
const TESTS_DIR = join(ROOT, 'data', 'tests');
const OUTPUT_DIR = join(ROOT, 'public', 'generated');

// A file that is present but unusable is not the same thing as one that is not
// there. Reading already worked that way — readFile below is deliberately
// outside any catch, so an unreadable file ends the build. Parsing did not: a
// malformed file was logged to stderr and dropped, and `Found N experiments`
// then printed a number that had silently shrunk beside a checkmark, wrote the
// index, and exited 0. data/tests/ holds one file, so one bad byte published an
// empty experiments-index.json to the dashboard with a green build and a green
// deploy.
//
// aggregate-reports.mjs already draws this line for the same job in the same
// directory: ENOENT returns null, anything else throws "present but is not
// valid JSON". This is that contract, for the first script in the prebuild
// chain.
export async function loadAllTests(testsDir = TESTS_DIR) {
  const files = await readdir(testsDir);
  const yamlFiles = files
    .filter(f => ['.yaml', '.yml'].includes(extname(f)))
    .sort(); // 알파벳 순 정렬로 결정적 출력 보장

  const experiments = [];

  for (const file of yamlFiles) {
    const content = await readFile(join(testsDir, file), 'utf-8');
    let data;
    try {
      data = parseYaml(content);
    } catch (err) {
      throw new Error(`${file} is present but is not valid YAML: ${err.message}`);
    }
    // An empty file parses to null, and `{ ...null }` is `{}` — a row with no
    // id that reaches experiments-index.json before the markdown pass dies on
    // it, so the index is written wrong and the failure names no file.
    if (data === null || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error(
        `${file} is present but does not hold an experiment: parsed as ${
          Array.isArray(data) ? 'a list' : String(data === null ? 'nothing' : typeof data)
        }`
      );
    }
    experiments.push({ ...data, _sourceFile: file });
  }

  return experiments;
}

/**
 * Dashboard UI용 JSON 생성
 * 기존 experiments.json과 동일한 구조 유지
 */
function generateIndexJson(experiments) {
  // _sourceFile 메타데이터 제거
  const clean = experiments.map(({ _sourceFile, ...rest }) => rest);
  return JSON.stringify({ experiments: clean, _generated: new Date().toISOString() }, null, 2);
}

/**
 * LLM Context용 Markdown 생성
 * 모든 실험 데이터를 LLM이 읽기 좋은 단일 문서로 컴파일
 * 
 * 핵심: 이 파일 하나만 LLM system prompt에 넣으면 전체 데이터 파악 가능
 */
function generateLlmContext(experiments) {
  const lines = [];

  lines.push('# GDPVal RealWork — 전체 실험 데이터');
  lines.push('');
  lines.push(`> 자동 생성됨: ${new Date().toISOString()}`);
  lines.push(`> 총 실험 수: ${experiments.length}`);
  lines.push('');

  // ── 요약 테이블 (LLM이 빠르게 전체를 파악할 수 있도록)
  lines.push('## 요약');
  lines.push('');
  lines.push('| ID | 실험명 | 모델 | A (win%) | B (win%) | Δ | 최고 산업 |');
  lines.push('|---|---|---|---|---|---|---|');

  for (const exp of experiments) {
    const bestIndustry = Object.entries(exp.industry_breakdown || {})
      .sort(([, a], [, b]) => b - a)[0];
    lines.push(
      `| ${exp.id} | ${exp.name} | ${exp.model} | ` +
      `${exp.condition_a.name} (${exp.condition_a.win_rate}%) | ` +
      `${exp.condition_b.name} (${exp.condition_b.win_rate}%) | ` +
      `+${exp.delta}%p | ${bestIndustry ? `${bestIndustry[0]} (+${bestIndustry[1]}%p)` : '-'} |`
    );
  }

  lines.push('');

  // ── 상세 섹션 (LLM이 깊이 있는 답변을 할 때 참조)
  lines.push('## 상세 데이터');
  lines.push('');

  for (const exp of experiments) {
    lines.push(`### ${exp.id}: ${exp.name}`);
    lines.push('');
    lines.push(`- **모델**: ${exp.model}`);
    lines.push(`- **태스크 수**: ${exp.tasks}`);
    lines.push(`- **Condition A**: ${exp.condition_a.name} — "${exp.condition_a.prompt}" → win rate ${exp.condition_a.win_rate}%`);
    lines.push(`- **Condition B**: ${exp.condition_b.name} — "${exp.condition_b.prompt}" → win rate ${exp.condition_b.win_rate}%`);
    lines.push(`- **Delta**: +${exp.delta}%p`);
    lines.push(`- **산업별 개선**:`);
    for (const [industry, delta] of Object.entries(exp.industry_breakdown || {})) {
      lines.push(`  - ${industry}: +${delta}%p`);
    }
    lines.push(`- **분석**: ${exp.analysis?.trim()}`);
    lines.push('');
  }

  // ── 통계 (LLM에게 전체적인 인사이트 제공)
  lines.push('## 전체 통계');
  lines.push('');
  const avgDelta = (experiments.reduce((s, e) => s + e.delta, 0) / experiments.length).toFixed(1);
  const models = [...new Set(experiments.map(e => e.model))];
  lines.push(`- 평균 Delta: +${avgDelta}%p`);
  lines.push(`- 사용 모델: ${models.join(', ')}`);
  lines.push(`- 전체 실험 수: ${experiments.length}`);

  // 모델별 평균
  lines.push('');
  lines.push('### 모델별 평균 Delta');
  for (const model of models) {
    const modelExps = experiments.filter(e => e.model === model);
    const avg = (modelExps.reduce((s, e) => s + e.delta, 0) / modelExps.length).toFixed(1);
    lines.push(`- ${model}: +${avg}%p (${modelExps.length}개 실험)`);
  }

  // 산업별 평균
  const industries = {};
  for (const exp of experiments) {
    for (const [ind, delta] of Object.entries(exp.industry_breakdown || {})) {
      if (!industries[ind]) industries[ind] = [];
      industries[ind].push(delta);
    }
  }
  lines.push('');
  lines.push('### 산업별 평균 Delta');
  for (const [ind, deltas] of Object.entries(industries)) {
    const avg = (deltas.reduce((s, d) => s + d, 0) / deltas.length).toFixed(1);
    lines.push(`- ${ind}: +${avg}%p (${deltas.length}개 실험)`);
  }

  return lines.join('\n');
}

// ── Main
async function main() {
  console.log('📦 Aggregating test files...');

  const experiments = await loadAllTests();
  console.log(`   Found ${experiments.length} experiments`);

  await mkdir(OUTPUT_DIR, { recursive: true });

  // 1. JSON for Dashboard
  const jsonPath = join(OUTPUT_DIR, 'experiments-index.json');
  await writeFile(jsonPath, generateIndexJson(experiments));
  console.log(`   ✅ ${jsonPath}`);

  // 2. Markdown for LLM
  const mdPath = join(OUTPUT_DIR, 'llm-context.md');
  await writeFile(mdPath, generateLlmContext(experiments));
  console.log(`   ✅ ${mdPath}`);

  // 사이즈 리포트
  const jsonSize = Buffer.byteLength(generateIndexJson(experiments));
  const mdSize = Buffer.byteLength(generateLlmContext(experiments));
  console.log(`   📊 JSON: ${(jsonSize / 1024).toFixed(1)}KB, MD: ${(mdSize / 1024).toFixed(1)}KB`);
  console.log('   Done!');
}

// Only run the aggregation when invoked directly, so scripts/__tests__/ can
// import loadAllTests above without triggering a full run over data/tests/.
if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().catch(err => {
    console.error('❌ Aggregation failed:', err);
    process.exit(1);
  });
}
