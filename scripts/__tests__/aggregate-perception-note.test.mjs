import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { readFile, readdir } from 'node:fs/promises'
import { promisify } from 'node:util'
import test from 'node:test'

import { buildPerceptionNoteData } from '../aggregate-perception-note.mjs'

const execFileAsync = promisify(execFile)
const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')
const cwd = new URL('../..', import.meta.url)

async function loadSources() {
  const [source, exp011, exp012, exp026, skillEntries] = await Promise.all([
    readRepoFile('data/notes/perception-pipeline.yaml'),
    readRepoFile('batch-runner/experiments/exp011_GPT52Chat_domain_packages.yaml'),
    readRepoFile('batch-runner/experiments/exp012_GPT52Chat_audio_multiagent.yaml'),
    readRepoFile('batch-runner/experiments/exp026_sandbox_skills_multimodal.yaml'),
    readdir(new URL('../../batch-runner/skills/', import.meta.url), { withFileTypes: true }),
  ])
  const skills = skillEntries.filter((entry) => entry.isDirectory()).map((entry) => entry.name)
  return { source, configs: { exp011, exp012, exp026 }, skills }
}

test('perception note projects checked-in packages, preprocessors, sandbox, and non-causal limits', async () => {
  const { source, configs, skills } = await loadSources()
  const data = buildPerceptionNoteData(source, configs, skills)
  assert.deepEqual(data.comparison.exp012.perception_paths, ['audio'])
  assert.deepEqual(data.comparison.exp026.perception_paths, ['audio', 'video'])
  assert.deepEqual(data.architecture.exp026.skill_catalog, ['audio', 'video', 'document', 'image', 'data'])
  assert.equal(data.architecture.exp026.use_docker, 'always')
  assert.equal(data.architecture.exp026.max_skills, 5)
  assert.equal(data.interpretation.causal_attribution, false)
  assert.equal(data.interpretation.invocation_count_known, false)
  assert.equal(data.interpretation.external_quality_known, false)
})

test('perception note rejects trigger, frame, runner, registry, and interpretation drift', async () => {
  const { source, configs, skills } = await loadSources()
  assert.throws(() => buildPerceptionNoteData(source, { ...configs, exp012: configs.exp012.replace('trigger: "has_audio_files"', 'trigger: "always"') }, skills), /audio trigger contract changed/)
  assert.throws(() => buildPerceptionNoteData(source, { ...configs, exp026: configs.exp026.replace('max_total_frames: 24', 'max_total_frames: 25') }, skills), /video frame contract changed/)
  assert.throws(() => buildPerceptionNoteData(source, { ...configs, exp026: configs.exp026.replace('use_docker: "always"', 'use_docker: "auto"') }, skills), /must require Docker/)
  assert.throws(() => buildPerceptionNoteData(source, { ...configs, exp012: configs.exp012.replace('Information sector only (17 audio-heavy tasks)', 'Information sector only') }, skills), /header task claim changed/)
  assert.throws(() => buildPerceptionNoteData(source, configs, skills.filter((skill) => skill !== 'audio')), /skill registry changed/)
  assert.throws(() => buildPerceptionNoteData(source.replace('causal_attribution: false', 'causal_attribution: true'), configs, skills), /non-causal and pre-grading/)
  assert.throws(() => buildPerceptionNoteData(source.replace('exp012_yaml_created_at_differs_from_report_date', 'causal_effect_known'), configs, skills), /caveats changed/)
})

test('pinned perception history exists in chronological ancestry', async () => {
  const { source, configs, skills } = await loadSources()
  const history = buildPerceptionNoteData(source, configs, skills).history
  const commits = [history.audio_preprocessor_commit, history.sandbox_multimodal_commit, history.docker_always_commit]
  const dates = await Promise.all(commits.map((commit) => execFileAsync('git', ['show', '-s', '--format=%cs', commit], { cwd }).then((result) => result.stdout.trim())))
  assert.deepEqual(dates, ['2026-03-09', '2026-07-07', '2026-07-09'])
  await execFileAsync('git', ['merge-base', '--is-ancestor', history.audio_preprocessor_commit, history.sandbox_multimodal_commit], { cwd })
  await execFileAsync('git', ['merge-base', '--is-ancestor', history.sandbox_multimodal_commit, history.docker_always_commit], { cwd })
  const audioFiles = await execFileAsync('git', ['show', '--format=', '--name-only', history.audio_preprocessor_commit], { cwd }).then((result) => result.stdout)
  const sandboxFiles = await execFileAsync('git', ['show', '--format=', '--name-only', history.sandbox_multimodal_commit], { cwd }).then((result) => result.stdout)
  const dockerConfig = await execFileAsync('git', ['show', `${history.docker_always_commit}:batch-runner/experiments/exp026_sandbox_skills_multimodal.yaml`], { cwd }).then((result) => result.stdout)
  assert.match(audioFiles, /batch-runner\/core\/audio_analyzer\.py/)
  assert.match(sandboxFiles, /batch-runner\/core\/sandbox_runner\.py/)
  assert.match(dockerConfig, /use_docker: "always"/)
})
