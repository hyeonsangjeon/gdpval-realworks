#!/usr/bin/env node

import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import YAML from 'yaml'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SOURCE_PATH = join(ROOT, 'data', 'notes', 'perception-pipeline.yaml')
const CONFIG_PATHS = {
  exp011: join(ROOT, 'batch-runner', 'experiments', 'exp011_GPT52Chat_domain_packages.yaml'),
  exp012: join(ROOT, 'batch-runner', 'experiments', 'exp012_GPT52Chat_audio_multiagent.yaml'),
  exp026: join(ROOT, 'batch-runner', 'experiments', 'exp026_sandbox_skills_multimodal.yaml'),
}
const OUTPUT_PATH = join(ROOT, 'public', 'generated', 'perception-note.json')
const SKILLS_PATH = join(ROOT, 'batch-runner', 'skills')
const EXPECTED_MISSING_IDENTITIES = [
  'execution_git_sha',
  'input_dataset_revision',
  'azure_model_revision',
  'runner_environment_identity',
]
const EXPECTED_CAVEATS = [
  'exp011_is_full_benchmark_while_exp012_is_information_only',
  'exp012_audio_analyzer_is_triggered_only_for_tasks_with_audio_files',
  'exp012_yaml_comment_says_17_audio_heavy_tasks_but_report_has_25_information_tasks',
  'exp012_yaml_created_at_differs_from_report_date',
  'exp026_changes_model_reasoning_runner_skills_audio_and_video_together',
  'report_snapshot_is_resolved_at_deployment_not_execution',
]

const deepEqual = (left, right) => JSON.stringify(left) === JSON.stringify(right)
const requireString = (value, label, pattern) => {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} must be a non-empty string`)
  if (pattern && !pattern.test(value)) throw new Error(`${label} has an invalid format`)
  return value
}
const requireSha = (value, label) => requireString(value, label, /^[0-9a-f]{40}$/)
const requireDate = (value, label) => {
  const date = requireString(value, label, /^\d{4}-\d{2}-\d{2}$/)
  const timestamp = `${date}T00:00:00.000Z`
  if (!Number.isFinite(Date.parse(timestamp)) || new Date(timestamp).toISOString() !== timestamp) {
    throw new Error(`${label} must be a valid date`)
  }
  return date
}

const preprocessorProjection = (config) => (config?.condition_a?.preprocessors ?? []).map((preprocessor) => ({
  type: preprocessor.type,
  deployment: preprocessor.model?.deployment,
  trigger: preprocessor.trigger,
  inject_as: preprocessor.inject_as,
  include_task_instruction: preprocessor.include_task_instruction,
  frames_per_video: preprocessor.frames_per_video ?? null,
  max_total_frames: preprocessor.max_total_frames ?? null,
}))

export function buildPerceptionNoteData(sourceText, configTexts, skillNames) {
  const source = YAML.parse(sourceText)
  const configs = Object.fromEntries(Object.entries(configTexts).map(([id, text]) => [id, YAML.parse(text)]))
  if (!source?.comparison || !source?.history || !source?.interpretation) throw new Error('perception source is incomplete')

  const expectedIds = {
    exp011: 'exp011_GPT52Chat_domain_packages',
    exp012: 'exp012_GPT52Chat_audio_multiagent',
    exp026: 'exp026_sandbox_skills_multimodal',
  }
  const expectedFilters = {
    exp011: { sector: null, occupation: null, sample_size: null },
    exp012: { sector: 'Information', occupation: null, sample_size: null },
    exp026: { sector: null, occupation: null, sample_size: null },
  }
  const expectedModels = { exp011: 'gpt-5.2-chat', exp012: 'gpt-5.2-chat', exp026: 'gpt-5.4' }
  for (const shortId of Object.keys(expectedIds)) {
    const contract = source.comparison[shortId]
    const config = configs[shortId]
    if (contract?.experiment_id !== expectedIds[shortId] || config?.experiment?.id !== expectedIds[shortId]) {
      throw new Error(`${shortId} experiment identity changed`)
    }
    if (config?.condition_a?.name !== ({
      exp011: 'Elicit v2 16k + domain packages',
      exp012: 'Multi-Agent: task-aware audio analysis + code',
      exp026: 'GPT-5.4 low + sandbox + skills + audio/video perception',
    })[shortId]) throw new Error(`${shortId} condition changed`)
    if (config?.execution?.mode !== contract.expected_mode) throw new Error(`${shortId} execution mode changed`)
    if (!deepEqual(config?.data?.filter, expectedFilters[shortId])) throw new Error(`${shortId} data filter changed`)
    if (config?.condition_a?.model?.deployment !== expectedModels[shortId]) throw new Error(`${shortId} model changed`)
  }
  if (configs.exp011?.experiment?.created_at !== '2026-03-05') throw new Error('exp011 config date changed')
  if (configs.exp012?.experiment?.created_at !== '2026-03-09') throw new Error('exp012 config date changed')
  if (!configTexts.exp012.includes('Information sector only (17 audio-heavy tasks)')) throw new Error('exp012 header task claim changed')
  if (configs.exp026?.experiment?.created_at !== '2026-05-18') throw new Error('exp026 config date changed')
  if (!configs.exp011?.condition_a?.prompt?.suffix?.includes('Available packages')) throw new Error('exp011 package notice changed')
  if (configs.exp026?.condition_a?.model?.reasoning_effort !== 'low') throw new Error('exp026 reasoning effort changed')

  const exp011Preprocessors = preprocessorProjection(configs.exp011)
  const exp012Preprocessors = preprocessorProjection(configs.exp012)
  const exp026Preprocessors = preprocessorProjection(configs.exp026)
  if (exp011Preprocessors.length !== 0) throw new Error('exp011 must not configure a perception preprocessor')
  if (!deepEqual(exp012Preprocessors.map((item) => item.type), ['audio_analyzer'])) throw new Error('exp012 audio preprocessor changed')
  if (!deepEqual(exp026Preprocessors.map((item) => item.type), ['audio_analyzer', 'video_analyzer'])) throw new Error('exp026 perception preprocessors changed')
  const exp012Audio = exp012Preprocessors[0]
  if (exp012Audio.deployment !== 'gpt-audio-1.5' || exp012Audio.trigger !== 'has_audio_files' || exp012Audio.inject_as !== 'prompt_prefix' || exp012Audio.include_task_instruction !== true) {
    throw new Error('exp012 audio trigger contract changed')
  }
  const exp026Video = exp026Preprocessors[1]
  if (exp026Video.deployment !== 'gpt-5.4' || exp026Video.trigger !== 'has_video_files' || exp026Video.include_task_instruction !== true || exp026Video.frames_per_video !== 8 || exp026Video.max_total_frames !== 24) {
    throw new Error('exp026 video frame contract changed')
  }
  if (configs.exp026?.execution?.sandbox?.use_docker !== 'always') throw new Error('exp026 must require Docker')
  if (configs.exp026?.execution?.sandbox?.max_skills !== 5) throw new Error('exp026 skill selection limit changed')
  if (!deepEqual([...skillNames].sort(), ['audio', 'data', 'document', 'image', 'video'])) throw new Error('sandbox skill registry changed')

  const interpretation = source.interpretation
  if (interpretation.causal_attribution !== false || interpretation.invocation_count_known !== false || interpretation.external_quality_known !== false) {
    throw new Error('perception interpretation must remain non-causal and pre-grading')
  }
  if (!deepEqual(interpretation.missing_execution_identities, EXPECTED_MISSING_IDENTITIES)) throw new Error('missing execution identities changed')
  if (!deepEqual(interpretation.caveats, EXPECTED_CAVEATS)) throw new Error('perception caveats changed')

  return {
    comparison: Object.fromEntries(Object.keys(expectedIds).map((shortId) => [shortId, {
      short_id: shortId,
      experiment_id: expectedIds[shortId],
      report_date: requireDate(source.comparison[shortId].report_date, `${shortId} report date`),
      expected_mode: source.comparison[shortId].expected_mode,
      expected_scope: source.comparison[shortId].expected_scope,
      perception_paths: source.comparison[shortId].perception_paths,
    }])),
    architecture: {
      exp011: { preprocessors: exp011Preprocessors, package_notice: true },
      exp012: {
        preprocessors: exp012Preprocessors,
        config_created_at: '2026-03-09',
        header_declared_audio_heavy_tasks: 17,
      },
      exp026: {
        preprocessors: exp026Preprocessors,
        use_docker: 'always',
        max_skills: 5,
        skill_catalog: ['audio', 'video', 'document', 'image', 'data'],
      },
    },
    history: {
      audio_preprocessor_commit: requireSha(source.history.audio_preprocessor_commit, 'audio preprocessor commit'),
      sandbox_multimodal_commit: requireSha(source.history.sandbox_multimodal_commit, 'sandbox multimodal commit'),
      docker_always_commit: requireSha(source.history.docker_always_commit, 'Docker-always commit'),
      audio_applied_at: requireDate(source.history.audio_applied_at, 'audio date'),
      sandbox_applied_at: requireDate(source.history.sandbox_applied_at, 'sandbox date'),
      docker_always_applied_at: requireDate(source.history.docker_always_applied_at, 'Docker-always date'),
    },
    interpretation: {
      causal_attribution: false,
      observed_claim: requireString(interpretation.observed_claim, 'observed claim'),
      architecture_claim: requireString(interpretation.architecture_claim, 'architecture claim'),
      invocation_count_known: false,
      external_quality_known: false,
      missing_execution_identities: EXPECTED_MISSING_IDENTITIES,
      caveats: EXPECTED_CAVEATS,
    },
    sources: {
      perception: 'data/notes/perception-pipeline.yaml',
      exp011_config: 'batch-runner/experiments/exp011_GPT52Chat_domain_packages.yaml',
      exp012_config: 'batch-runner/experiments/exp012_GPT52Chat_audio_multiagent.yaml',
      exp026_config: 'batch-runner/experiments/exp026_sandbox_skills_multimodal.yaml',
    },
  }
}

export async function aggregatePerceptionNote() {
  const [sourceText, skillEntries, ...configValues] = await Promise.all([
    readFile(SOURCE_PATH, 'utf8'),
    readdir(SKILLS_PATH, { withFileTypes: true }),
    ...Object.values(CONFIG_PATHS).map((path) => readFile(path, 'utf8')),
  ])
  const configTexts = Object.fromEntries(Object.keys(CONFIG_PATHS).map((id, index) => [id, configValues[index]]))
  const skillNames = skillEntries.filter((entry) => entry.isDirectory()).map((entry) => entry.name)
  const data = { ...buildPerceptionNoteData(sourceText, configTexts, skillNames), _generated: new Date().toISOString() }
  await mkdir(dirname(OUTPUT_PATH), { recursive: true })
  await writeFile(OUTPUT_PATH, `${JSON.stringify(data, null, 2)}\n`)
  console.log(`✅ ${OUTPUT_PATH}`)
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  aggregatePerceptionNote().catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
}
