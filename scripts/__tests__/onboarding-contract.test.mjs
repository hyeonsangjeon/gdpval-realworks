import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import test from 'node:test'
import { parse } from 'yaml'

const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')
const execFileAsync = promisify(execFile)
const batchRunnerPath = fileURLToPath(new URL('../../batch-runner', import.meta.url))

const extractSection = (text, heading) => {
  const lines = text.split('\n')
  const start = lines.indexOf(heading)
  assert.notEqual(start, -1, `missing section: ${heading}`)
  const level = heading.match(/^#+/)[0].length
  const body = []
  let fenced = false
  for (const line of lines.slice(start + 1)) {
    if (line.trimStart().startsWith('```')) fenced = !fenced
    if (!fenced && new RegExp(`^#{1,${level}}\\s+`).test(line)) break
    body.push(line)
  }
  return body.join('\n')
}

const extractLinks = (text) => [...text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map((match) => match[1])

const parseTables = (text) => {
  const tables = []
  let rows = []
  for (const line of text.split('\n')) {
    if (/^\|.*\|$/.test(line.trim())) {
      rows.push(line.trim().slice(1, -1).split('|').map((cell) => cell.trim()))
    } else if (rows.length) {
      tables.push(rows)
      rows = []
    }
  }
  if (rows.length) tables.push(rows)
  return tables
}

const dataRows = (table) => table.slice(2)
const cleanCode = (value) => value.replaceAll('`', '')

const extractPythonStringList = (text, name) => {
  const match = new RegExp(`${name} = \\[([\\s\\S]*?)\\n\\]`).exec(text)
  assert.ok(match, `missing Python list: ${name}`)
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1])
}

const findStep = (workflow, name) => {
  const step = workflow.jobs['batch-run'].steps.find((candidate) => candidate.name === name)
  assert.ok(step, `missing workflow step: ${name}`)
  return step
}

const extractHeredoc = (script, marker, terminator) => {
  const lines = script.split('\n')
  const start = lines.findIndex((line) => line.trim() === marker)
  assert.notEqual(start, -1, `missing heredoc marker: ${marker}`)
  const end = lines.findIndex((line, index) => index > start && line.trim() === terminator)
  assert.notEqual(end, -1, `missing heredoc terminator: ${terminator}`)
  const body = lines.slice(start + 1, end)
  const indents = body.filter((line) => line.trim()).map((line) => line.length - line.trimStart().length)
  const indent = indents.length ? Math.min(...indents) : 0
  return body.map((line) => line.slice(indent)).join('\n')
}

test('first-screen routes stay complete and fork-relative', async () => {
  const [rootEnglish, rootKorean, runnerEnglish, runnerKorean] = await Promise.all([
    readRepoFile('README.md'),
    readRepoFile('README_KR.md'),
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
  ])

  const rootSections = [
    extractSection(rootEnglish, '## Start here'),
    extractSection(rootKorean, '## 여기서 시작하세요'),
  ]
  for (const section of rootSections) {
    const links = extractLinks(section)
    assert.ok(links.includes('https://hyeonsangjeon.github.io/gdpval-realworks/'))
    assert.ok(links.includes('batch-runner/experiments/exp998_smoke_baseline_sample.yaml'))
    assert.ok(links.includes('../../actions/workflows/batch-run.yml'))
    assert.ok(links.some((link) => /docs\/first-experiment(?:_KR)?\.md#7-/.test(link)))
    assert.doesNotMatch(section, /github\.com\/hyeonsangjeon\/gdpval-realworks\/actions/)
  }

  const runnerSections = [
    extractSection(runnerEnglish, '## Start here'),
    extractSection(runnerKorean, '## 여기서 시작하세요'),
  ]
  for (const section of runnerSections) {
    const links = extractLinks(section)
    assert.ok(links.includes('../../../actions/workflows/batch-run.yml'))
    assert.ok(links.includes('experiments/exp998_smoke_baseline_sample.yaml'))
    assert.ok(links.some((link) => /\.\.\/docs\/first-experiment(?:_KR)?\.md#7-/.test(link)))
    assert.doesNotMatch(section, /github\.com\/hyeonsangjeon\/gdpval-realworks\/actions/)
  }

  const rootAction = new URL(
    '../../actions/workflows/batch-run.yml',
    'https://github.com/fork-owner/gdpval-realworks/blob/main/README.md',
  )
  const runnerAction = new URL(
    '../../../actions/workflows/batch-run.yml',
    'https://github.com/fork-owner/gdpval-realworks/blob/main/batch-runner/README.md',
  )
  assert.equal(rootAction.href, 'https://github.com/fork-owner/gdpval-realworks/actions/workflows/batch-run.yml')
  assert.equal(runnerAction.href, rootAction.href)
})

test('workflow input tables mirror defaults and watchdog delegation', async () => {
  const [batchText, rootEnglish, rootKorean, runnerEnglish, runnerKorean, guideEnglish, guideKorean] = await Promise.all([
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('README.md'),
    readRepoFile('README_KR.md'),
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
    readRepoFile('docs/first-experiment.md'),
    readRepoFile('docs/first-experiment_KR.md'),
  ])
  const workflow = parse(batchText)
  const inputs = workflow.on.workflow_dispatch.inputs
  const inputNames = [
    'experiment_yaml',
    'experiment_name',
    'dry_run',
    'relay_run',
    'relay_lineage_id',
    'source_sha',
    'wall_timeout',
    'sandbox_image_digest',
  ]
  assert.deepEqual(Object.keys(inputs), inputNames)
  assert.deepEqual(
    Object.fromEntries(inputNames.slice(2).map((name) => [name, inputs[name].default])),
    {
      dry_run: false,
      relay_run: 0,
      relay_lineage_id: '',
      source_sha: '',
      wall_timeout: 290,
      sandbox_image_digest: '',
    },
  )
  assert.match(inputs.wall_timeout.description, /^condition_a Step 2 watchdog minutes/)
  assert.match(inputs.wall_timeout.description, /0\.\.290/)
  assert.match(inputs.wall_timeout.description, /0=use execution\.wall_timeout from YAML/)
  assert.match(inputs.wall_timeout.description, /disabled only when both are 0/)
  assert.equal(workflow.concurrency, undefined)

  for (const [document, heading] of [
    [rootEnglish, '## First cloud experiment'],
    [rootKorean, '## 첫 클라우드 실험'],
  ]) {
    const table = parseTables(extractSection(document, heading))[0]
    assert.deepEqual(dataRows(table).map((row) => cleanCode(row[0])), inputNames)
  }

  for (const [document, heading] of [
    [runnerEnglish, '### Workflow Parameters'],
    [runnerKorean, '### 워크플로우 파라미터'],
  ]) {
    const table = parseTables(extractSection(document, heading))[0]
    const rows = dataRows(table)
    assert.deepEqual(rows.map((row) => cleanCode(row[0])), inputNames)
    const defaults = Object.fromEntries(rows.map((row) => [cleanCode(row[0]), cleanCode(row[2])]))
    assert.equal(defaults.dry_run, 'false')
    assert.equal(defaults.relay_run, '0')
    assert.equal(defaults.wall_timeout, '290')
    const wallRow = rows.find((row) => cleanCode(row[0]) === 'wall_timeout')
    assert.match(wallRow[1], /execution\.wall_timeout/)
    assert.match(wallRow[1], /both are `0`|둘 다 `0`/)
  }

  const step2a = findStep(workflow, 'Step 2a: Run inference (condition_a)')
  assert.equal(step2a.env.CONFIG_WALL_TIMEOUT, '${{ steps.read_config.outputs.wall_timeout }}')
  assert.match(step2a.run, /WALL_TIMEOUT="\$WALL_TIMEOUT_INPUT"/)
  assert.match(step2a.run, /"\$WALL_TIMEOUT" == "0"[\s\S]*WALL_TIMEOUT="\$CONFIG_WALL_TIMEOUT"/)
  assert.match(step2a.run, /if \[ "\$WALL_TIMEOUT" -gt 0 \]/)
  const dispatchStep = workflow.jobs['inspect-mode'].steps.find(
    (step) => step.name === 'Verify dispatch contract',
  )
  assert.ok(dispatchStep)
  const sha = 'a'.repeat(40)
  const validEnv = {
    ...process.env,
    EVENT_NAME: 'workflow_dispatch',
    EVENT_REF: 'refs/heads/main',
    EVENT_SHA: sha,
    WORKFLOW_SHA: sha,
    WALL_TIMEOUT: '290',
    RELAY_RUN: '0',
    RELAY_LINEAGE_ID: '',
    SOURCE_SHA: '',
    SANDBOX_IMAGE_DIGEST: '',
  }
  await execFileAsync('bash', ['-c', dispatchStep.run], { env: validEnv })
  await execFileAsync('bash', ['-c', dispatchStep.run], {
    env: {
      ...validEnv,
      RELAY_RUN: '1',
      RELAY_LINEAGE_ID: 'experiment:run:attempt',
      SOURCE_SHA: sha,
      SANDBOX_IMAGE_DIGEST: `ghcr.io/hyeonsangjeon/gdpval-sandbox@sha256:${'c'.repeat(64)}`,
    },
  })
  for (const invalid of [
    { EVENT_NAME: 'push' },
    { EVENT_REF: 'refs/heads/feature' },
    { WORKFLOW_SHA: 'b'.repeat(40) },
    { EVENT_SHA: 'a'.repeat(39), WORKFLOW_SHA: 'a'.repeat(39) },
    { WALL_TIMEOUT: '-1' },
    { WALL_TIMEOUT: '291' },
    { WALL_TIMEOUT: '350' },
    { WALL_TIMEOUT: 'text' },
    { WALL_TIMEOUT: '999999999999999999999999999999' },
    { RELAY_RUN: '-1' },
    { RELAY_RUN: '11' },
    { RELAY_RUN: '999999999999999999999999999999' },
    { RELAY_RUN: '1', SOURCE_SHA: 'b'.repeat(40) },
    { RELAY_RUN: '1', SOURCE_SHA: '' },
    { RELAY_RUN: '0', SOURCE_SHA: sha },
    { RELAY_RUN: '0', RELAY_LINEAGE_ID: 'injected-lineage' },
    { RELAY_RUN: '0', SANDBOX_IMAGE_DIGEST: `ghcr.io/hyeonsangjeon/gdpval-sandbox@sha256:${'c'.repeat(64)}` },
    { RELAY_RUN: '1', SOURCE_SHA: sha, RELAY_LINEAGE_ID: '' },
    { RELAY_RUN: '1', SOURCE_SHA: sha, RELAY_LINEAGE_ID: 'lineage', SANDBOX_IMAGE_DIGEST: 'ghcr.io/attacker/image:latest' },
    { RELAY_RUN: '1', SOURCE_SHA: sha, RELAY_LINEAGE_ID: 'lineage', SANDBOX_IMAGE_DIGEST: 'ghcr.io/hyeonsangjeon/gdpval-sandbox:latest' },
  ]) {
    await assert.rejects(
      execFileAsync('bash', ['-c', dispatchStep.run], {
        env: { ...validEnv, ...invalid },
      }),
    )
  }
  const configCheckout = workflow.jobs['inspect-mode'].steps.find(
    (step) => step.name === 'Verify exact config checkout',
  )
  assert.match(configCheckout.run, /"\$\(git rev-parse HEAD\)" == "\$GITHUB_SHA"/)
  const inspectSteps = workflow.jobs['inspect-mode'].steps
  assert.ok(inspectSteps.indexOf(dispatchStep) < inspectSteps.findIndex((step) => step.name === 'Checkout config only'))
  const exactCheckout = findStep(workflow, 'Verify exact checkout')
  assert.match(exactCheckout.run, /"\$\(git rev-parse HEAD\)" == "\$GITHUB_SHA"/)
  const batchSteps = workflow.jobs['batch-run'].steps
  assert.ok(batchSteps.indexOf(exactCheckout) < batchSteps.findIndex((step) => step.name === 'Setup Python'))
  const relayStep = findStep(workflow, 'Retrigger relay run')
  assert.match(relayStep.run, /gh workflow run batch-run\.yml --ref main/)
  assert.match(relayStep.run, /-f source_sha="\$SOURCE_SHA"/)
  assert.match(relayStep.run, /-f experiment_name="\$experiment_name"/)

  const readConfigStep = findStep(workflow, 'Read experiment config flags')
  const readConfigPython = extractHeredoc(readConfigStep.run, "python3 <<'PY'", 'PY')
  const fixtureRoot = await mkdtemp(join(tmpdir(), 'gdpval-onboarding-'))
  try {
    const experimentDir = join(fixtureRoot, 'batch-runner', 'experiments')
    await mkdir(experimentDir, { recursive: true })
    const fixturePath = join(experimentDir, 'fixture.yaml')
    const outputPath = join(fixtureRoot, 'output.txt')
    const config = (wallTimeout) => [
      'data:',
      '  source: openai/gdpval',
      'execution:',
      '  mode: code_interpreter',
      `  wall_timeout: ${wallTimeout}`,
      '',
    ].join('\n')
    await writeFile(fixturePath, config(290), 'utf8')
    await execFileAsync('python3', ['-c', readConfigPython], {
      cwd: fixtureRoot,
      env: {
        ...process.env,
        PYTHONPATH: batchRunnerPath,
        EXPERIMENT_YAML_INPUT: 'fixture',
        GITHUB_OUTPUT: outputPath,
      },
    })
    assert.match(await readFile(outputPath, 'utf8'), /^source_repo=openai\/gdpval$/m)
    await writeFile(fixturePath, config(291), 'utf8')
    await assert.rejects(
      execFileAsync('python3', ['-c', readConfigPython], {
        cwd: fixtureRoot,
        env: {
          ...process.env,
          PYTHONPATH: batchRunnerPath,
          EXPERIMENT_YAML_INPUT: 'fixture',
          GITHUB_OUTPUT: outputPath,
        },
      }),
    )
  } finally {
    await rm(fixtureRoot, { recursive: true, force: true })
  }
  for (const guide of [guideEnglish, guideKorean]) {
    assert.match(guide, /`relay_lineage_id`/)
    assert.match(guide, /`source_sha`/)
    assert.match(guide, /`wall_timeout`[\s\S]{0,80}`290`/)
    assert.match(guide, /not a durable queue|durable\s+queue가 아니므로/)
  }
})

test('documented authentication narrows OIDC and excludes direct fallback from first-run guarantees', async () => {
  const [batchText, runnerEnglish, runnerKorean, guideEnglish, guideKorean, codeInterpreter] = await Promise.all([
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
    readRepoFile('docs/first-experiment.md'),
    readRepoFile('docs/first-experiment_KR.md'),
    readRepoFile('batch-runner/core/code_interpreter.py'),
  ])
  const workflow = parse(batchText)
  for (const name of [
    'Step 2a: Run inference (condition_a)',
    'Step 2b: Run inference (condition_b)',
    'Step 6: Generate experiment report',
  ]) {
    const env = findStep(workflow, name).env || {}
    assert.equal(Object.hasOwn(env, 'AZURE_OPENAI_API_KEY'), false)
    assert.equal(Object.hasOwn(env, 'AZURE_OPENAI_ENDPOINT'), true)
  }

  const expectedSecrets = [
    'AZURE_CLIENT_ID',
    'AZURE_TENANT_ID',
    'AZURE_SUBSCRIPTION_ID',
    'AZURE_OPENAI_ENDPOINT',
    'HF_TOKEN',
  ]
  for (const [guide, heading] of [
    [guideEnglish, '### 5. Add repository secrets'],
    [guideKorean, '### 5. Repository secrets 등록'],
  ]) {
    const table = parseTables(extractSection(guide, heading)).find((candidate) => candidate[0][0] === 'Secret')
    assert.ok(table)
    assert.deepEqual(dataRows(table).map((row) => cleanCode(row[0])), expectedSecrets)
    const endpoint = dataRows(table).find((row) => cleanCode(row[0]) === 'AZURE_OPENAI_ENDPOINT')[1]
    assert.match(endpoint, /AzureOpenAI\(azure_endpoint=\.\.\.\)/)
    assert.match(endpoint, /not a Foundry project URL|Foundry project URL은 아님/)
    assert.match(guide, /not a\s+Foundry project URL|Foundry project URL이나/)
    assert.match(guide, /`\/openai\/v1\/` base URL/)
    assert.doesNotMatch(guide, /compatible Foundry endpoint/)
  }

  assert.match(codeInterpreter, /os\.getenv\("AZURE_OPENAI_API_KEY"\)/)
  assert.match(codeInterpreter, /Priority 2: API Key fallback/)
  assert.match(runnerEnglish, /supported GitHub Actions path never injects `AZURE_OPENAI_API_KEY`/)
  assert.match(runnerEnglish, /API-key-only direct runner behavior is outside this\s+first-run contract and is not guaranteed/)
  assert.match(runnerKorean, /지원되는 GitHub Actions 경로는 `AZURE_OPENAI_API_KEY`를 주입하지 않고/)
  assert.match(runnerKorean, /API-key-only direct runner 동작은 이\s+첫 실행 계약 밖이며 여기서는 보장하지/)
})

test('local quick starts and bootstrap warnings follow their owning code', async () => {
  const [runnerEnglish, runnerKorean, step0Text, bootstrapText] = await Promise.all([
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
    readRepoFile('batch-runner/step0_bootstrap.sh'),
    readRepoFile('batch-runner/core/repo_bootstrapper.py'),
  ])
  const commands = [
    'bash step0_bootstrap.sh "$CONFIG"',
    'bash step1_prepare_tasks.sh "$CONFIG"',
    'bash step2_run_inference.sh condition_a',
    'bash step3_format_results.sh',
    'bash step4_fill_parquet.sh',
    'bash step6_report.sh --no-narrative --dry-run',
  ]
  for (const [document, heading] of [
    [runnerEnglish, '### Local step-by-step debugging'],
    [runnerKorean, '### 로컬 단계별 디버깅'],
  ]) {
    const section = extractSection(document, heading)
    const bashBlock = /```bash\n([\s\S]*?)```/.exec(section)?.[1]
    assert.ok(bashBlock)
    let previous = -1
    for (const command of commands) {
      const index = bashBlock.indexOf(command)
      assert.ok(index > previous, `missing or unordered command: ${command}`)
      previous = index
    }
    assert.doesNotMatch(bashBlock, /step7_upload_hf/)
  }

  assert.match(step0Text, /YAML_CONFIG="\$\{1:\?Usage: \.\/step0_bootstrap\.sh <yaml_config_path>\}"/)
  assert.match(step0Text, /cfg\.get\('data', \{\}\)\.get\('source', ''\)/)
  assert.match(bootstrapText, /private: bool = False/)
  assert.match(bootstrapText, /return any\(f\.startswith\("data\/"\) for f in files\)/)
  assert.match(bootstrapText, /self\.api\.whoami\(token=self\.token\)/)
  assert.match(bootstrapText, /exist_ok=False/)
  assert.match(bootstrapText, /except HfHubHTTPError as exc:/)
  assert.match(bootstrapText, /status_code != 409/)
  assert.match(bootstrapText, /refusing "\s*"automatic repository deletion/)
  assert.doesNotMatch(bootstrapText, /self\.api\.delete_repo\(/)
  assert.match(bootstrapText, /private=self\.private/)
  assert.match(bootstrapText, /MANIFEST_FILENAME = "step0_needs_files_manifest\.json"/)
  assert.match(bootstrapText, /SOURCE_REVISION = "[0-9a-f]{40}"/)
  assert.match(bootstrapText, /CANONICAL_SOURCE_INPUT_SHA256 = \(/)
  assert.match(bootstrapText, /def _source_input_projection_sha256\(/)
  assert.match(bootstrapText, /source input projection differs from pinned source/)
  assert.match(bootstrapText, /def validate_needs_files_manifest\(/)
  assert.match(bootstrapText, /"_schema_version": 3/)
  assert.match(bootstrapText, /def build_reference_manifest\(/)
  assert.match(bootstrapText, /Manifest reference_files must exactly match declared paths in order/)
  assert.match(bootstrapText, /def _prepare_pinned_source_snapshot\(/)
  assert.match(bootstrapText, /allow_patterns=declared_reference_paths/)
  assert.match(bootstrapText, /def _snapshot_validation_errors\(/)
  assert.match(bootstrapText, /def _restore_manifest_from_snapshot\(self\)/)
  assert.match(bootstrapText, /no canonical needs-files manifest/)
  assert.doesNotMatch(bootstrapText, /Manifest not found, regenerating from snapshot/)
  for (const runner of [runnerEnglish, runnerKorean]) {
    assert.match(runner, /public HF dataset|public HF dataset|public Hugging Face|public\s+HF|public\s+dataset/i)
    assert.match(runner, /aborts without automatic deletion|자동 삭제하지 않고 중단/)
    assert.match(runner, /disposable target|일회성 (?:대상|target)/)
  }
})

test('relay transport uses exact data.source and fails before cloud work', async () => {
  const [batchText, relayText, step2Text, exp002Text, requirementsText] = await Promise.all([
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('batch-runner/scripts/relay_checkpoint.py'),
    readRepoFile('batch-runner/step2_run_inference.py'),
    readRepoFile('batch-runner/experiments/exp002_single_baseline.yaml'),
    readRepoFile('batch-runner/requirements.txt'),
  ])
  const workflow = parse(batchText)
  const exp002 = parse(exp002Text)
  assert.equal(exp002.experiment.id, 'exp002')
  assert.equal(exp002.data.source, 'openai/gdpval')

  const steps = workflow.jobs['batch-run'].steps
  const restore = findStep(workflow, 'Restore checkpoint (relay run)')
  const step0 = findStep(workflow, 'Step 0: Bootstrap submission repo')
  const writeAccess = findStep(workflow, 'Verify result dataset write access')
  const step1 = findStep(workflow, 'Step 1: Prepare tasks')
  const identity = findStep(workflow, 'Validate restored checkpoint identity')
  const login = findStep(workflow, 'Azure Login (OIDC)')
  const upload = findStep(workflow, 'Checkpoint: Upload to HuggingFace')
  const cleanup = findStep(workflow, 'Cleanup relay checkpoint')
  assert.ok(steps.indexOf(restore) < steps.indexOf(step0))
  assert.ok(steps.indexOf(restore) < steps.indexOf(login))
  assert.ok(steps.indexOf(step0) < steps.indexOf(writeAccess))
  assert.ok(steps.indexOf(writeAccess) < steps.indexOf(step1))
  assert.ok(steps.indexOf(writeAccess) < steps.indexOf(login))
  assert.equal(writeAccess.env.SOURCE_REPO, '${{ steps.read_config.outputs.source_repo }}')
  assert.match(writeAccess.run, /relay_checkpoint\.py verify-write --repo-id "\$SOURCE_REPO"/)
  assert.ok(steps.indexOf(step1) < steps.indexOf(identity))
  assert.ok(steps.indexOf(identity) < steps.indexOf(login))
  assert.equal(restore['continue-on-error'], undefined)
  assert.equal(identity['continue-on-error'], undefined)
  assert.equal(cleanup['continue-on-error'], undefined)
  assert.match(identity.run, /--validate-checkpoint-only/)

  for (const [step, operation] of [
    [restore, 'restore'],
    [upload, 'upload'],
    [cleanup, 'cleanup'],
  ]) {
    assert.equal(step.env.SOURCE_REPO, '${{ steps.read_config.outputs.source_repo }}')
    assert.match(
      step.run,
      new RegExp(`relay_checkpoint\\.py ${operation}[\\s\\S]*--repo-id "\\$SOURCE_REPO"`),
    )
    assert.doesNotMatch(step.run, /REPO_OWNER|EXPERIMENT_YAML_INPUT/)
  }
  assert.match(restore.run, /--source-sha "\$SOURCE_SHA_INPUT"/)
  assert.match(restore.run, /--lineage-id "\$RELAY_LINEAGE_ID_INPUT"/)
  assert.match(restore.run, /--sandbox-image-digest "\$SANDBOX_IMAGE_DIGEST_INPUT"/)
  assert.match(upload.run, /--source-sha "\$SOURCE_SHA"/)
  assert.match(upload.run, /--sandbox-image-digest "\$SANDBOX_IMAGE_DIGEST"/)
  assert.match(cleanup.run, /--source-sha "\$SOURCE_SHA_INPUT"/)
  assert.match(cleanup.run, /--lineage-id "\$RELAY_LINEAGE_ID_INPUT"/)
  assert.match(cleanup.run, /--sandbox-image-digest "\$SANDBOX_IMAGE_DIGEST_INPUT"/)

  assert.match(relayText, /repo_id = validate_hf_dataset_repo_id\(repo_id\)/)
  assert.match(relayText, /CHECKPOINT_SCHEMA = "relay-checkpoint-v2"/)
  assert.match(relayText, /sandbox_image_digest/)
  assert.match(relayText, /relay checkpoint sandbox image digest mismatch/)
  assert.match(relayText, /REMOTE_LINEAGES = "_checkpoint\/lineages"/)
  assert.match(relayText, /def _marker_path\(source_sha: str, lineage_id: str\)/)
  assert.match(relayText, /def _generation_root\(/)
  assert.match(relayText, /payload_revision/)
  assert.match(relayText, /list_repo_files\(/)
  assert.match(relayText, /auth_check\(/)
  assert.match(relayText, /hf_hub_download\(/)
  assert.match(relayText, /snapshot_download\(/)
  assert.match(relayText, /def _verify_remote_records\(/)
  assert.match(relayText, /def _validate_complete_task_set\(/)
  assert.match(relayText, /result task IDs differ from ordered task set/)
  assert.match(relayText, /_verify_record\(verified_root \/ record\["path"\], record\)/)
  assert.match(relayText, /uploaded generation hash mismatch/)
  assert.match(relayText, /_validate_exact_local_deliverables\(staged_upload, required\)/)
  assert.match(relayText, /except HfHubHTTPError as exc:/)
  assert.match(relayText, /getattr\(response, "status_code", None\) != 404/)
  assert.match(relayText, /revision=head/)
  assert.match(relayText, /marker is missing while lineage files remain/)
  assert.match(relayText, /Relay checkpoint already cleaned/)
  assert.match(relayText, /except Exception:[\s\S]*confirmed_head = _repo_head/)
  assert.match(step2Text, /allow_missing_results=False/)
  assert.doesNotMatch(relayText, /Continuing without checkpoint|except:\s*pass/)
  assert.match(requirementsText, /^huggingface-hub==1\.24\.0$/m)
})

test('report, publication, and artifact destinations follow Step 6 and Step 7', async () => {
  const [runnerEnglish, runnerKorean, step6Text, narrativeText, step7Text, batchText] = await Promise.all([
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
    readRepoFile('batch-runner/step6_report.py'),
    readRepoFile('batch-runner/core/narrative_analyzer.py'),
    readRepoFile('batch-runner/step7_upload_hf.sh'),
    readRepoFile('.github/workflows/batch-run.yml'),
  ])
  const workflow = parse(batchText)
  assert.match(step6Text, /_SCRIPT_DIR \/ "results" \/ experiment_id \/ "report"/)
  assert.match(step6Text, /output_dir \/ "report_data\.json"/)
  assert.match(step6Text, /output_dir \/ "report\.md"/)
  assert.match(step6Text, /report\.html generation disabled/)
  assert.match(step6Text, /upload_dir \/ "self_report\.json"/)
  assert.match(narrativeText, /Call 1: Sector-level analysis/)
  assert.match(narrativeText, /Call 2: Deep analysis/)
  assert.match(narrativeText, /DEFAULT_MODEL = "gpt-5\.4-pro"/)

  assert.deepEqual(
    extractPythonStringList(step7Text, 'INCLUDE'),
    ['README.md', 'data/train-*.parquet', 'deliverable_files/**', 'self_report.json'],
  )
  assert.deepEqual(extractPythonStringList(step7Text, 'DELETE'), ['data/**', 'deliverable_files/**'])

  const createPr = findStep(workflow, 'Create Pull Request with results')
  const verifyPr = findStep(workflow, 'Verify result PR outputs and contract')
  const uploadHf = findStep(workflow, 'Step 7: Upload to HuggingFace')
  const steps = workflow.jobs['batch-run'].steps
  assert.equal(createPr.with['add-paths'], 'batch-runner/results/${{ env.EXPERIMENT_ID }}/report/report.md')
  assert.ok(steps.indexOf(createPr) < steps.indexOf(verifyPr))
  assert.ok(steps.indexOf(verifyPr) < steps.indexOf(uploadHf))
  const artifact = findStep(workflow, 'Upload artifacts')
  assert.match(artifact.with.path, /batch-runner\/workspace\//)
  assert.match(artifact.with.path, /batch-runner\/results\//)
  assert.equal(artifact.with['retention-days'], 30)

  for (const runner of [runnerEnglish, runnerKorean]) {
    assert.match(runner, /results\/<experiment_id>\/report\//)
    assert.match(runner, /workspace\/upload\/self_report\.json/)
    assert.doesNotMatch(runner, /workspace\/report\//)
    assert.doesNotMatch(runner, /- \*\*`report\.html`\*\*/)
    assert.doesNotMatch(runner, /results\/<experiment_id>\/report\/[^\n]*HuggingFace/)
  }
})

test('English and Korean Batch Runner references retain structural parity', async () => {
  const [runnerEnglish, runnerKorean] = await Promise.all([
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
  ])
  const modeNames = (text) => [...text.matchAll(/^### `([^`]+)`/gm)].map((match) => match[1]).sort()
  assert.deepEqual(modeNames(runnerEnglish), ['code_interpreter', 'json_renderer', 'sandbox', 'subprocess'])
  assert.deepEqual(modeNames(runnerKorean), modeNames(runnerEnglish))

  for (const [document, headings] of [
    [runnerEnglish, ['## Project Structure', '## Data Flow']],
    [runnerKorean, ['## 프로젝트 구조', '## 데이터 흐름']],
  ]) {
    for (const heading of headings) {
      const section = extractSection(document, heading)
      assert.match(section, /```text\n[\s\S]+```/)
    }
    assert.doesNotMatch(document, /mermaid\.ink/)
    assert.doesNotMatch(document, /exp999_smoke_baseline_sample/)
    assert.doesNotMatch(document, /no security risk|보안 위험 없음/i)
    assert.doesNotMatch(document, /Runs sharing[^\n]*serialized|같은 `experiment_yaml`[^\n]*직렬화/)
    assert.match(document, /best-effort/)
  }
})
