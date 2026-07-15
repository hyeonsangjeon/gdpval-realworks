#!/usr/bin/env node

/**
 * aggregate-experiments.mjs
 *
 * batch-runner/experiments/*.yaml + batch-runner/prompts/subprocess_occupation_codegen.yaml
 * → public/generated/prompt-architecture.json
 */

import { readdir, readFile, writeFile, mkdir } from 'fs/promises';
import { join, resolve } from 'path';
import { fileURLToPath } from 'url';
import { parse as parseYaml } from 'yaml';

const ROOT = new URL('..', import.meta.url).pathname;
const EXPERIMENTS_DIR = join(ROOT, 'batch-runner', 'experiments');
const PROMPTS_DIR = join(ROOT, 'batch-runner', 'prompts');
const OUTPUT_DIR = join(ROOT, 'public', 'generated');

export function normalizeExecutionMetrics(value) {
  return value && typeof value === 'object' && value.enabled === true
    ? { enabled: true }
    : null;
}

async function main() {
  console.log('📦 Aggregating experiment prompt architectures...');
  const codegen = parseYaml(await readFile(join(PROMPTS_DIR, 'subprocess_occupation_codegen.yaml'), 'utf-8'));
  const files = (await readdir(EXPERIMENTS_DIR))
    .filter(f => f.startsWith('exp') && f.endsWith('.yaml') && !f.includes('smoke'))
    .sort();

  const experiments = [];
  for (const file of files) {
    const expData = parseYaml(await readFile(join(EXPERIMENTS_DIR, file), 'utf-8'));
    const shortId = file.match(/^(exp\d+)/)?.[1];
    if (!shortId) continue;
    const condition = expData.condition_a || {};
    const prompt = condition.prompt || {};
    const qa = condition.qa || {};
    const execution = expData.execution || {};
    const metrics = normalizeExecutionMetrics(execution.metrics);

    experiments.push({
      exp_id: expData.experiment?.id || file.replace('.yaml', ''),
      short_id: shortId,
      experiment_name: expData.experiment?.name || '',
      description: expData.experiment?.description || '',
      created_at: expData.experiment?.created_at || '',
      prompt_architecture: {
        system: {
          source: 'subprocess_occupation_codegen.yaml',
          content: codegen.system_message || '',
          experiment_system: prompt.system || null,
        },
        user_prompt: {
          prefix: prompt.prefix || null,
          body: prompt.body || null,
          codegen_core: {
            source: 'subprocess_occupation_codegen.yaml',
            content: codegen.user_prompt || '',
          },
          suffix: prompt.suffix
            ? { source: file, content: prompt.suffix }
            : null,
        },
        qa_prompt: qa.enabled
          ? { enabled: true, min_score: qa.min_score || 5, max_retries: qa.max_retries || 1, content: qa.prompt || '' }
          : { enabled: false, content: null },
        execution_config: {
          mode: execution.mode || 'subprocess',
          tokens: execution.tokens || null,
          timeout: execution.timeout || null,
          resume_max_rounds: execution.resume_max_rounds ?? null,
          max_retries: execution.max_retries || 5,
          install_libreoffice: execution.install_libreoffice || false,
          ...(metrics ? { metrics } : {}),
        },
      },
    });
  }

  experiments.sort((a, b) => a.short_id.localeCompare(b.short_id));
  await mkdir(OUTPUT_DIR, { recursive: true });
  const output = { experiments, _generated: new Date().toISOString() };
  const outputPath = join(OUTPUT_DIR, 'prompt-architecture.json');
  await writeFile(outputPath, JSON.stringify(output, null, 2));
  console.log(`   ✅ ${outputPath} (${experiments.length} experiments, ${(Buffer.byteLength(JSON.stringify(output, null, 2)) / 1024).toFixed(1)}KB)`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().catch(err => { console.error('❌ Aggregation failed:', err); process.exit(1); });
}
