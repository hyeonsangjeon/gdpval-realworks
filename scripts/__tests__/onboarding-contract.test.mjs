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

const pythonHeredocs = (workflow) => {
  const sources = []
  for (const [jobName, job] of Object.entries(workflow.jobs || {})) {
    for (const [stepIndex, step] of (job.steps || []).entries()) {
      const lines = typeof step.run === 'string' ? step.run.split('\n') : []
      for (let index = 0; index < lines.length; index += 1) {
        if (!/^\s*python3?(?:\s+-)?\s+<<'PY'\s*$/.test(lines[index])) continue
        const end = lines.findIndex((line, candidate) => candidate > index && line.trim() === 'PY')
        assert.notEqual(end, -1, `unterminated Python heredoc: ${jobName}/${step.name || stepIndex}`)
        const body = lines.slice(index + 1, end)
        const indents = body.filter((line) => line.trim()).map((line) => line.length - line.trimStart().length)
        const indent = indents.length ? Math.min(...indents) : 0
        sources.push({
          label: `${jobName}/${step.name || stepIndex}`,
          source: body.map((line) => line.slice(indent)).join('\n'),
        })
        index = end
      }
    }
  }
  return sources
}

test('workflow Python heredocs compile before merge', async () => {
  const workflowPaths = [
    '.github/workflows/batch-run.yml',
    '.github/workflows/grade-run.yml',
  ]
  let count = 0
  for (const path of workflowPaths) {
    const workflow = parse(await readRepoFile(path))
    for (const heredoc of pythonHeredocs(workflow)) {
      count += 1
      await execFileAsync(
        'python3',
        ['-c', 'import os; compile(os.environ["WORKFLOW_PYTHON"], os.environ["WORKFLOW_LABEL"], "exec")'],
        {
          env: {
            ...process.env,
            WORKFLOW_LABEL: `${path}:${heredoc.label}`,
            WORKFLOW_PYTHON: heredoc.source,
          },
        },
      )
    }
  }
  assert.ok(count >= 6, `expected at least 6 workflow Python heredocs, got ${count}`)
})

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
  assert.match(rootSections[0], /\$0 · no model calls/)
  assert.match(rootSections[0], /Paid API usage · model calls and remote writes/)
  assert.match(rootSections[1], /\$0 · 모델 호출 없음/)
  assert.match(rootSections[1], /유료 API 사용 · 모델 호출과 원격 쓰기/)

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

test('root docs separate unrun preflight from verified hosted containment', async () => {
  const [rootEnglish, rootKorean, preflightText] = await Promise.all([
    readRepoFile('README.md'),
    readRepoFile('README_KR.md'),
    readRepoFile('.github/workflows/agentic-sandbox-preflight.yml'),
  ])
  const preflight = parse(preflightText)
  assert.deepEqual(
    preflight.jobs['model-free-preflight']['runs-on'],
    ['self-hosted', 'linux', 'x64', 'agentic-sandbox'],
  )

  const operationalSections = [
    extractSection(rootEnglish, '## Operational controls'),
    extractSection(rootKorean, '## 운영 통제'),
  ]
  for (const section of operationalSections) {
    assert.match(section, /not_run/)
    assert.match(section, /self-hosted, linux, x64, agentic-sandbox/)
    assert.match(section, /no matching runner exists|일치하는 러너가 없(?:어|음)/)
    assert.match(section, /not_run[^\n]*failed[^\n]*verified/)
    assert.match(section, /31193818481/)
    assert.match(section, /4b1bff35/)
    assert.match(section, /f0c4ec3cdff7d714d0db8aca58b1f5669c3958c6b6203be00095b8acb827e50e/)
    assert.match(section, /all eight checks|8개 항목 모두/)
    assert.match(section, /exec_run[^\n]*(?:blocked|계속)/)
    assert.match(section, /aggregate\s+gate[\s\S]{0,80}blocked/i)
    for (const evidence of ['capability', 'CVE', 'license', 'microVM', 'OCI', 'provenance', 'SBOM', 'signature']) {
      assert.match(section, new RegExp(evidence, 'i'))
    }
    assert.doesNotMatch(section, /No containment result is established|containment 근거는 `not_run`으로 남아/)
  }

  const cloudSections = [
    extractSection(rootEnglish, '## First cloud experiment'),
    extractSection(rootKorean, '## 첫 클라우드 실험'),
  ]
  assert.match(cloudSections[0], /gpt-5\.2-chat[^\n]*sample configuration value/)
  assert.match(cloudSections[0], /current production report default[^\n]*gpt-5\.6-sol/)
  assert.match(cloudSections[1], /샘플 config 예시값[^\n]*gpt-5\.2-chat/)
  assert.match(cloudSections[1], /현재 프로덕션 report 기본값[^\n]*gpt-5\.6-sol/)
  assert.match(rootEnglish, /\[RealWorks Field Notes\]\(https:\/\/hyeonsangjeon\.github\.io\/gdpval-realworks\/notes\)/)
  assert.match(rootKorean, /\[RealWorks Field Notes\]\(https:\/\/hyeonsangjeon\.github\.io\/gdpval-realworks\/notes\)/)
})

test('fresh dashboard verification is self-preparing and credential-free', async () => {
  const [readme, packageMetadata] = await Promise.all([
    readRepoFile('README.md'),
    readRepoFile('package.json').then(JSON.parse),
  ])
  const section = extractSection(readme, '### Verify a fresh checkout')
  const commands = [
    'npm ci',
    'npm run test:aggregate',
    'npm run build',
    'git status --short',
  ]
  for (let index = 0; index < commands.length - 1; index += 1) {
    assert.ok(section.indexOf(commands[index]) < section.indexOf(commands[index + 1]))
  }
  assert.match(section, /unauthenticated, read-only requests/)
  assert.match(section, /does not require cloud credentials, call a model, or write or[\s\S]*upload remote data/)
  assert.match(section, /Ruby is optional locally/)
  assert.equal(packageMetadata.scripts['pretest:aggregate'], 'npm run aggregate')
  assert.equal(packageMetadata.scripts['test:aggregate'], 'npm run test:aggregate:prepared')
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
  assert.match(step2a.run, /WALL_TIMEOUT_INPUT is not a decimal integer/)
  assert.match(step2a.run, /if \[\[ "\$WALL_TIMEOUT" != "0" \]\]/)
  assert.doesNotMatch(step2a.run, /"\$WALL_TIMEOUT" -(?:gt|ge|lt|le)/)
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
      'condition_a:',
      '  name: Baseline',
      '  model:',
      '    provider: azure',
      '    deployment: main-deployment',
      '  qa:',
      '    enabled: true',
      '    model: qa-deployment',
      '  preprocessors:',
      '    - type: audio_analyzer',
      '      model:',
      '        provider: azure',
      '        deployment: audio-deployment',
      '    - type: audio_analyzer',
      '      optional: true',
      '      model:',
      '        provider: openai',
      '        deployment: openai-audio-deployment',
      '    - type: video_analyzer',
      '      optional: true',
      '      model:',
      '        provider: anthropic',
      '        deployment: anthropic-video-deployment',
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
    assert.match(
      await readFile(outputPath, 'utf8'),
      /^azure_ai_workloads_json=\["narrative=gpt-5\.6-sol","inference=main-deployment","inference=qa-deployment","inference=audio-deployment","code-interpreter=main-deployment"\]$/m,
    )
    assert.match(await readFile(outputPath, 'utf8'), /^requires_openai_key=true$/m)
    assert.match(await readFile(outputPath, 'utf8'), /^requires_anthropic_key=true$/m)
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

test('documented authentication uses typed Foundry routes and OIDC-only credentials', async () => {
  const [batchText, gradeText, runnerEnglish, runnerKorean, guideEnglish, guideKorean, codeInterpreter, azureClients] = await Promise.all([
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('.github/workflows/grade-run.yml'),
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
    readRepoFile('docs/first-experiment.md'),
    readRepoFile('docs/first-experiment_KR.md'),
    readRepoFile('batch-runner/core/code_interpreter.py'),
    readRepoFile('batch-runner/core/azure_ai_clients.py'),
  ])
  const workflow = parse(batchText)
  for (const name of ['Step 2a: Run inference (condition_a)']) {
    const env = findStep(workflow, name).env || {}
    assert.equal(Object.hasOwn(env, 'AZURE_OPENAI_API_KEY'), false)
    assert.equal(Object.hasOwn(env, 'AZURE_OPENAI_ENDPOINT'), false)
    assert.equal(Object.hasOwn(env, 'AZURE_AI_ROUTE_PROFILE'), true)
    assert.equal(Object.hasOwn(env, 'AZURE_OPENAI_V1_ENDPOINT'), false)
    assert.equal(Object.hasOwn(env, 'FOUNDRY_PROJECT_ENDPOINT'), true)
  }
  const reportEnv = findStep(workflow, 'Step 6: Generate experiment report').env || {}
  assert.equal(reportEnv.AZURE_AI_ROUTE_PROFILE, 'direct-v1')
  assert.equal(Object.hasOwn(reportEnv, 'FOUNDRY_PROJECT_ENDPOINT'), true)
  assert.equal(Object.hasOwn(reportEnv, 'AZURE_OPENAI_ENDPOINT'), false)

  const steps = workflow.jobs['batch-run'].steps
  assert.equal(
    steps.some((step) => step.name === 'Step 2b: Run inference (condition_b)'),
    false,
  )
  const modeStep = workflow.jobs['inspect-mode'].steps.find(
    (step) => step.name === 'Inspect execution mode without credentials',
  )
  assert.ok(modeStep)
  assert.match(modeStep.run, /condition_b is unsupported in the general batch workflow/)
  const configuredIdentity = findStep(workflow, 'Validate Azure OIDC identity before remote access')
  const routePreflight = findStep(workflow, 'Validate Azure AI routes before remote writes')
  const restore = findStep(workflow, 'Restore checkpoint (relay run)')
  const step0 = findStep(workflow, 'Step 0: Bootstrap submission repo')
  const login = findStep(workflow, 'Azure Login (OIDC)')
  const sessionIdentity = findStep(workflow, 'Verify Azure OIDC session identity')
  const tokenPreflight = findStep(workflow, 'Verify Azure AI token before model calls')
  const step2a = findStep(workflow, 'Step 2a: Run inference (condition_a)')
  assert.ok(steps.indexOf(configuredIdentity) < steps.indexOf(routePreflight))
  assert.ok(steps.indexOf(routePreflight) < steps.indexOf(restore))
  assert.ok(steps.indexOf(routePreflight) < steps.indexOf(step0))
  assert.ok(steps.indexOf(routePreflight) < steps.indexOf(login))
  assert.ok(steps.indexOf(login) < steps.indexOf(sessionIdentity))
  assert.ok(steps.indexOf(sessionIdentity) < steps.indexOf(tokenPreflight))
  assert.ok(steps.indexOf(login) < steps.indexOf(tokenPreflight))
  assert.ok(steps.indexOf(tokenPreflight) < steps.indexOf(step2a))
  assert.match(step2a.env.OPENAI_API_KEY, /requires_openai_key/)
  assert.match(step2a.env.ANTHROPIC_API_KEY, /requires_anthropic_key/)
  assert.doesNotMatch(step2a.env.OPENAI_API_KEY, /condition_a_provider/)
  assert.doesNotMatch(step2a.env.ANTHROPIC_API_KEY, /condition_a_provider/)
  assert.match(routePreflight.env.AZURE_AI_ROUTE_PROFILE, /uses_code_interpreter/)
  assert.equal(routePreflight.env.AZURE_AI_REQUIRE_EXPECTED_IDENTITIES, '1')
  assert.equal(
    routePreflight.env.AZURE_AI_WORKLOADS_JSON,
    '${{ steps.read_config.outputs.azure_ai_workloads_json }}',
  )
  assert.equal(Object.hasOwn(routePreflight.env, 'AZURE_AI_EXPECTED_DIRECT_ACCOUNT'), true)
  assert.equal(Object.hasOwn(routePreflight.env, 'AZURE_AI_EXPECTED_PROJECT_NAME'), true)
  assert.match(routePreflight.run, /azure_ai_route_preflight\.py/)
  assert.match(tokenPreflight.run, /--verify-token/)
  for (const step of [configuredIdentity, sessionIdentity]) {
    for (const suffix of ['CLIENT_ID', 'TENANT_ID', 'SUBSCRIPTION_ID']) {
      assert.equal(Object.hasOwn(step.env, `AZURE_AI_EXPECTED_${suffix}`), true)
    }
    assert.match(step.run, /azure_oidc_identity_preflight\.py/)
  }
  assert.match(sessionIdentity.run, /--verify-session/)
  assert.equal(Object.hasOwn(workflow.on.workflow_dispatch.inputs, 'route_profile'), false)

  const relayIdentity = findStep(workflow, 'Validate restored checkpoint identity')
  assert.equal(relayIdentity.env.AZURE_AI_REQUIRE_EXPECTED_IDENTITIES, '1')
  assert.match(relayIdentity.env.AZURE_AI_ROUTE_PROFILE, /uses_code_interpreter/)
  assert.equal(Object.hasOwn(relayIdentity.env, 'FOUNDRY_PROJECT_ENDPOINT'), true)
  for (const name of [
    'Verify Azure AI token before model calls',
    'Step 2a: Run inference (condition_a)',
    'Step 6: Generate experiment report',
  ]) {
    assert.equal(findStep(workflow, name).env.AZURE_AI_REQUIRE_EXPECTED_IDENTITIES, '1')
  }
  assert.equal(
    tokenPreflight.env.AZURE_AI_WORKLOADS_JSON,
    '${{ steps.read_config.outputs.azure_ai_workloads_json }}',
  )

  const gradeWorkflow = parse(gradeText)
  const gradeSteps = gradeWorkflow.jobs.grade.steps
  const renderer = gradeSteps.find((step) => step.name === 'Determine renderer requirement')
  assert.ok(renderer)
  assert.match(renderer.run, /grader_route_workloads\(config\)/)
  assert.match(renderer.run, /azure_ai_workloads_json=/)
  const gradeStep = gradeSteps.find((step) => step.name === 'Run grading')
  assert.ok(gradeStep)
  assert.match(gradeStep.env.FOUNDRY_PROJECT_ENDPOINT, /!inputs\.dry_run/)
  assert.match(gradeStep.env.AZURE_AI_ROUTE_PROFILE, /!inputs\.dry_run/)
  const gradeConfiguredIdentity = gradeSteps.find(
    (step) => step.name === 'Validate Azure OIDC identity before remote access',
  )
  const gradeLogin = gradeSteps.find((step) => step.name === 'Azure Login (OIDC)')
  const gradeSessionIdentity = gradeSteps.find(
    (step) => step.name === 'Verify Azure OIDC session identity',
  )
  assert.ok(gradeSteps.indexOf(gradeConfiguredIdentity) < gradeSteps.indexOf(gradeLogin))
  assert.ok(gradeSteps.indexOf(gradeLogin) < gradeSteps.indexOf(gradeSessionIdentity))
  for (const step of [gradeConfiguredIdentity, gradeSessionIdentity]) {
    assert.equal(step.if, 'inputs.dry_run != true')
    for (const suffix of ['CLIENT_ID', 'TENANT_ID', 'SUBSCRIPTION_ID']) {
      assert.equal(Object.hasOwn(step.env, `AZURE_AI_EXPECTED_${suffix}`), true)
    }
  }
  assert.match(gradeSessionIdentity.run, /--verify-session/)
  for (const name of [
    'Validate Azure AI route before remote access',
    'Verify Azure AI token before grading',
  ]) {
    const step = gradeSteps.find((candidate) => candidate.name === name)
    assert.ok(step)
    assert.equal(step.env.AZURE_AI_REQUIRE_EXPECTED_IDENTITIES, '1')
    assert.equal(
      step.env.AZURE_AI_WORKLOADS_JSON,
      '${{ steps.renderer.outputs.azure_ai_workloads_json }}',
    )
  }

  const expectedSecrets = [
    'AZURE_CLIENT_ID',
    'AZURE_TENANT_ID',
    'AZURE_SUBSCRIPTION_ID',
    'FOUNDRY_PROJECT_ENDPOINT',
    'HF_TOKEN',
  ]
  const expectedVariables = [
    'AZURE_AI_EXPECTED_CLIENT_ID',
    'AZURE_AI_EXPECTED_TENANT_ID',
    'AZURE_AI_EXPECTED_SUBSCRIPTION_ID',
    'AZURE_AI_EXPECTED_DIRECT_ACCOUNT',
    'AZURE_AI_EXPECTED_PROJECT_ACCOUNT',
    'AZURE_AI_EXPECTED_PROJECT_NAME',
    'AZURE_AI_EXPECTED_LEGACY_ACCOUNT',
  ]
  for (const [guide, heading] of [
    [guideEnglish, '### 5. Add repository secrets'],
    [guideKorean, '### 5. Repository secrets 등록'],
  ]) {
    const table = parseTables(extractSection(guide, heading)).find((candidate) => candidate[0][0] === 'Secret')
    assert.ok(table)
    assert.deepEqual(dataRows(table).map((row) => cleanCode(row[0])), expectedSecrets)
    const variableTable = parseTables(extractSection(guide, heading)).find((candidate) => candidate[0][0] === 'Variable')
    assert.ok(variableTable)
    assert.deepEqual(dataRows(variableTable).map((row) => cleanCode(row[0])), expectedVariables)
    assert.match(guide, /`\/openai\/v1\/`/)
    assert.match(guide, /`\/api\/projects\/<project-name>`/)
    assert.match(guide, /maps the `FOUNDRY_PROJECT_ENDPOINT` secret|secret을 동일한 이름의 typed runtime/)
    assert.match(guide, /`https:\/\/ai\.azure\.com\/\.default`|`ai\.azure\.com` token/)
  }

  assert.doesNotMatch(codeInterpreter, /AZURE_OPENAI_API_KEY|API Key fallback/)
  assert.match(codeInterpreter, /AzureAIWorkload\.CODE_INTERPRETER/)
  assert.match(azureClients, /DIRECT_TOKEN_SCOPE = "https:\/\/ai\.azure\.com\/\.default"/)
  assert.match(azureClients, /url=f"https:\/\/{host}\/openai\/v1\/"/)
  assert.match(azureClients, /static Azure credential environment variables are forbidden/)
  assert.match(runnerEnglish, /only Code Interpreter uses the project route/)
  assert.match(runnerKorean, /Code Interpreter만 project route/)
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
  assert.match(bootstrapText, /return "data" if any\(path\.startswith\("data\/"\) for path in files\) else "partial"/)
  assert.match(bootstrapText, /self\.api\.whoami\(token=self\.token\)/)
  assert.match(bootstrapText, /exist_ok=False/)
  assert.match(bootstrapText, /except HfHubHTTPError as exc:/)
  assert.match(bootstrapText, /getattr\(response, "status_code", None\) != 409/)
  assert.match(bootstrapText, /refusing "\s*"automatic repository deletion/)
  assert.doesNotMatch(bootstrapText, /self\.api\.delete_repo\(/)
  assert.match(bootstrapText, /private=self\.private/)
  assert.match(bootstrapText, /MANIFEST_FILENAME = "step0_needs_files_manifest\.json"/)
  assert.match(bootstrapText, /SOURCE_REVISION = "[0-9a-f]{40}"/)
  assert.match(bootstrapText, /CANONICAL_SOURCE_PROJECTION_SHA256 = \(/)
  assert.match(bootstrapText, /CANONICAL_TARGET_COLUMNS = /)
  assert.match(bootstrapText, /def source_projection_hashes\(/)
  assert.match(bootstrapText, /def validate_needs_files_manifest\(/)
  assert.match(bootstrapText, /"_schema_version": 4/)
  assert.match(bootstrapText, /def build_reference_manifest\(/)
  assert.match(bootstrapText, /Manifest reference_files must exactly match declared paths in order/)
  assert.match(bootstrapText, /def _prepare_pinned_source_snapshot\(/)
  assert.match(bootstrapText, /allow_patterns=declared_reference_paths/)
  assert.match(bootstrapText, /def _snapshot_validation_errors\(/)
  assert.match(bootstrapText, /def _restore_manifest_from_snapshot\(self\)/)
  assert.match(bootstrapText, /no canonical needs-files manifest/)
  assert.doesNotMatch(bootstrapText, /Manifest not found, regenerating from snapshot/)
  const classifyIndex = bootstrapText.indexOf('state = self._classify_target_read_only()')
  const prepareIndex = bootstrapText.indexOf('self._prepare_pinned_source_snapshot(source_root)')
  const createIndex = bootstrapText.indexOf('self.api.create_repo(')
  const uploadIndex = bootstrapText.indexOf('self.api.upload_folder(')
  assert.ok(classifyIndex >= 0)
  assert.ok(classifyIndex < prepareIndex)
  assert.ok(prepareIndex < createIndex)
  assert.ok(createIndex < uploadIndex)
  for (const runner of [runnerEnglish, runnerKorean]) {
    assert.match(runner, /public HF dataset|public HF dataset|public Hugging Face|public\s+HF|public\s+dataset/i)
    assert.match(runner, /aborts without automatic deletion|자동 삭제하지 않고 중단/)
    assert.match(runner, /disposable target|일회성 (?:대상|target)/)
  }
})

test('reference inputs remain content-bound through model execution', async () => {
  const [bootstrapper, needsFiles, step1, step2, integrity, codeInterpreter, subprocessRunner, sandboxRunner] = await Promise.all([
    readRepoFile('batch-runner/core/repo_bootstrapper.py'),
    readRepoFile('batch-runner/core/needs_files.py'),
    readRepoFile('batch-runner/step1_prepare_tasks.py'),
    readRepoFile('batch-runner/step2_run_inference.py'),
    readRepoFile('batch-runner/core/reference_integrity.py'),
    readRepoFile('batch-runner/core/code_interpreter.py'),
    readRepoFile('batch-runner/core/subprocess_runner.py'),
    readRepoFile('batch-runner/core/sandbox_runner.py'),
  ])

  assert.match(bootstrapper, /"_schema_version": 4/)
  assert.match(bootstrapper, /CANONICAL_SOURCE_PROJECTION_SHA256/)
  assert.match(bootstrapper, /"_source_projection_sha256":/)
  assert.match(bootstrapper, /"reference_files": \{\}/)
  assert.match(bootstrapper, /build_reference_manifest\(/)
  assert.match(bootstrapper, /snapshot_root=root/)
  assert.match(needsFiles, /def reference_records\(/)
  assert.match(needsFiles, /def source_projection_sha256\(/)
  assert.match(step1, /"reference_file_records":/)
  assert.match(step1, /source_task_projection_sha256\(/)
  assert.match(step2, /resolve_verified_reference_paths\(/)
  assert.match(step2, /reference_input_integrity_failed/)
  assert.match(integrity, /class VerifiedReferencePath\(str\)/)
  assert.match(integrity, /def open_verified_reference\(/)
  assert.match(integrity, /getattr\(os, "O_NOFOLLOW", 0\)/)
  assert.match(integrity, /shutil\.copyfileobj\(source_stream, destination_stream\)/)
  assert.match(codeInterpreter, /with open_verified_reference\(path\)/)
  assert.match(subprocessRunner, /copy_verified_reference\(src_path, tmpdir\)/)
  assert.match(sandboxRunner, /copy_verified_reference\(src_path, tmpdir\)/)
  assert.doesNotMatch(codeInterpreter, /Upload failed.*continue/)
  assert.doesNotMatch(subprocessRunner, /Failed to copy reference file/)
  assert.doesNotMatch(sandboxRunner, /failed to copy reference file/)
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
  const inference = findStep(workflow, 'Step 2a: Run inference (condition_a)')
  const relayStatus = findStep(workflow, 'Check relay status')
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
  assert.equal(inference['continue-on-error'], true)
  assert.match(inference.run, /echo "exit_code=\$STEP2_EXIT_CODE" >> "\$GITHUB_OUTPUT"/)
  assert.equal(relayStatus.env.STEP2_EXIT_CODE, '${{ steps.step2a.outputs.exit_code }}')
  assert.match(relayStatus.run, /relay_checkpoint\.py status/)
  assert.match(relayStatus.run, /--exit-code "\$STEP2_EXIT_CODE"/)
  assert.match(relayStatus.run, /--github-output "\$GITHUB_OUTPUT"/)
  assert.doesNotMatch(relayStatus.run, /\$PENDING| -(?:gt|ge|lt|le) |python3 -c/)

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
  assert.match(cleanup.run, /--expected-generation "\$EXPECTED_GENERATION"/)
  assert.match(cleanup.run, /--sandbox-image-digest "\$SANDBOX_IMAGE_DIGEST_INPUT"/)
  assert.equal(cleanup.env.EXPECTED_GENERATION, '${{ steps.restore_checkpoint.outputs.generation }}')
  assert.match(cleanup.if, /success\(\)/)
  assert.match(cleanup.if, /inputs\.dry_run != true/)
  assert.match(cleanup.if, /inputs\.relay_run > 0/)
  assert.match(cleanup.if, /steps\.check_relay\.outputs\.needs_relay == 'false'/)
  assert.match(cleanup.if, /steps\.step2a\.outcome == 'success'/)

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
  const [runnerEnglish, runnerKorean, step6Text, narrativeText, step7Text, publicationText, fillText, bootstrapText, batchText] = await Promise.all([
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
    readRepoFile('batch-runner/step6_report.py'),
    readRepoFile('batch-runner/core/narrative_analyzer.py'),
    readRepoFile('batch-runner/step7_upload_hf.sh'),
    readRepoFile('batch-runner/core/hf_publication.py'),
    readRepoFile('batch-runner/fill_parquet.py'),
    readRepoFile('batch-runner/core/repo_bootstrapper.py'),
    readRepoFile('.github/workflows/batch-run.yml'),
  ])
  const workflow = parse(batchText)
  assert.match(step6Text, /_SCRIPT_DIR \/ "results" \/ experiment_id \/ "report"/)
  assert.match(step6Text, /output_dir \/ "report_data\.json"/)
  assert.match(step6Text, /output_dir \/ "report\.md"/)
  assert.match(step6Text, /report\.html generation disabled/)
  assert.match(step6Text, /upload_dir \/ "self_report\.json"/)
  assert.match(step6Text, /"prepared_fingerprint": fingerprint/)
  assert.match(step6Text, /"result_fingerprint": result_fingerprint/)
  assert.match(step6Text, /"publication_generation": publication_generation/)
  assert.match(step6Text, /"ordered_task_ids": list\(ordered_task_ids\)/)
  assert.match(narrativeText, /Call 1: Sector-level analysis/)
  assert.match(narrativeText, /Call 2: Deep analysis/)
  assert.match(narrativeText, /DEFAULT_MODEL = "gpt-5\.6-sol"/)
  assert.match(narrativeText, /DEFAULT_REASONING_EFFORT = "max"/)
  assert.match(step6Text, /"narrative_model": narrative\.get\("model"\)/)
  assert.match(step6Text, /"narrative_reasoning_effort": narrative\.get\("reasoning_effort"\)/)

  const includePatterns = [
    'README.md',
    'cost_ledger.jsonl',
    'data/train-*.parquet',
    'deliverable_files/**',
    'inference_provenance.json',
    'self_report.json',
  ]
  const deletePatterns = [
    'cost_ledger.jsonl',
    'data/**',
    'deliverable_files/**',
    'inference_provenance.json',
    'self_report.json',
    'step2_inference_results.json',
  ]
  assert.deepEqual(
    extractPythonStringList(publicationText, 'INCLUDE_PATTERNS'),
    includePatterns,
  )
  assert.deepEqual(
    extractPythonStringList(publicationText, 'DELETE_PATTERNS'),
    deletePatterns,
  )
  assert.match(fillText, /validate_source_projection_rows\(/)
  assert.match(bootstrapText, /errors\.extend\(validate_source_projection_rows\(df, manifest_path\)\)/)
  assert.match(bootstrapText, /TARGET_HEAD_FILENAME = "step0_target_head\.json"/)
  assert.match(step7Text, /publish_dataset_with_receipt\(/)
  assert.match(step7Text, /clear_publication_receipt\(\)/)
  assert.match(step7Text, /load_publication_identity\(/)
  assert.match(step7Text, /expected_task_ids=list\(identity\.ordered_task_ids\)/)
  assert.match(step7Text, /expected_submitter_rows=identity\.submitter_rows\(\)/)
  assert.doesNotMatch(step7Text, /sum\(len\(pd\.read_parquet/)
  assert.match(publicationText, /client\.create_commit\(/)
  assert.match(publicationText, /parent_commit=expected_head/)
  assert.doesNotMatch(publicationText, /client\.upload_folder\(/)
  assert.match(publicationText, /self_report\.json is required for publication/)
  assert.match(publicationText, /publication_plan.*step7_upload_requested/)
  assert.match(publicationText, /prepared fingerprint mismatch/)
  assert.match(publicationText, /result fingerprint mismatch/)
  assert.match(publicationText, /result task set mismatch/)
  // step7_upload_hf.sh restates both lists and aborts the upload when they
  // differ from the module's. Checking the mirror against the same expectation,
  // rather than against a second copy of it, means a pattern added on one side
  // can no longer pass here and then stop the upload after a paid run.
  assert.deepEqual(extractPythonStringList(step7Text, 'INCLUDE'), includePatterns)
  assert.deepEqual(extractPythonStringList(step7Text, 'DELETE'), deletePatterns)
  assert.match(step7Text, /if INCLUDE_PATTERNS != INCLUDE:/)
  assert.match(step7Text, /if DELETE_PATTERNS != DELETE:/)
  assert.match(publicationText, /validate_inference_provenance\(/)
  assert.match(publicationText, /if _is_managed_publication_path\(path\)/)
  assert.match(publicationText, /"step2_inference_results\.json"/)
  assert.doesNotMatch(step7Text, /CommitOperationDelete/)
  assert.doesNotMatch(
    step7Text,
    /hf_publication\._publication_(?:source_paths|validate_files|deletions|plan_sha256)/,
  )
  assert.doesNotMatch(step7Text, /hf_publication\._is_managed_publication_path/)

  const createPr = findStep(workflow, 'Create Pull Request with results')
  const verifyPr = findStep(workflow, 'Verify result PR outputs and contract')
  const uploadHf = findStep(workflow, 'Step 7: Upload to HuggingFace')
  const cleanup = findStep(workflow, 'Cleanup relay checkpoint')
  const finality = findStep(workflow, 'Verify publication finality')
  const recheckPr = findStep(workflow, 'Recheck result PR head after upload')
  const dispatch = findStep(workflow, 'Dispatch exact result PR validation')
  const step0 = findStep(workflow, 'Step 0: Bootstrap submission repo')
  const step1 = findStep(workflow, 'Step 1: Prepare tasks')
  const steps = workflow.jobs['batch-run'].steps
  assert.equal(createPr.with['add-paths'], 'batch-runner/results/${{ env.EXPERIMENT_ID }}/report/report.md')
  assert.ok(steps.indexOf(createPr) < steps.indexOf(verifyPr))
  assert.ok(steps.indexOf(verifyPr) < steps.indexOf(uploadHf))
  assert.ok(steps.indexOf(uploadHf) < steps.indexOf(cleanup))
  assert.ok(steps.indexOf(cleanup) < steps.indexOf(finality))
  assert.ok(steps.indexOf(finality) < steps.indexOf(recheckPr))
  assert.ok(steps.indexOf(recheckPr) < steps.indexOf(dispatch))
  assert.match(step0.run, /output\.write\(f"target_head=\{head\}\\n"\)/)
  assert.equal(step1.env.GDPVAL_RELAY_LINEAGE_ID, '${{ inputs.relay_lineage_id }}')
  assert.equal(uploadHf.env.EXPECTED_TARGET_HEAD, '${{ steps.step0.outputs.target_head }}')
  assert.equal(finality.env.SOURCE_REPO, '${{ steps.read_config.outputs.source_repo }}')
  assert.equal(
    finality.env.EXPECTED_GENERATION,
    "${{ inputs.relay_run > 0 && steps.restore_checkpoint.outputs.generation || '' }}",
  )
  assert.match(finality.run, /load_publication_identity\(/)
  assert.match(finality.run, /verify_publication_finality\(/)
  assert.doesNotMatch(finality.run, /create_commit|upload_file|upload_folder/)
  for (const step of [finality, recheckPr, dispatch]) {
    assert.match(step.if, /success\(\)/)
    assert.match(step.if, /inputs\.dry_run != true/)
    assert.match(step.if, /steps\.check_relay\.outputs\.needs_relay == 'false'/)
    assert.match(step.if, /steps\.step2a\.outcome == 'success'/)
  }
  const artifact = findStep(workflow, 'Upload artifacts')
  assert.match(artifact.with.path, /batch-runner\/workspace\//)
  assert.match(artifact.with.path, /batch-runner\/results\//)
  assert.equal(artifact.with['retention-days'], 30)

  for (const runner of [runnerEnglish, runnerKorean]) {
    assert.match(runner, /results\/<experiment_id>\/report\//)
    assert.match(runner, /workspace\/upload\/self_report\.json/)
    assert.match(runner, /`inference_provenance\.json`/)
    assert.match(runner, /endpoint-free/)
    assert.match(runner, /endpoint\s+URL/)
    assert.match(runner, /stale remote|원격[\s\S]{0,80}step2_inference_results\.json/)
    assert.doesNotMatch(runner, /workspace\/report\//)
    assert.doesNotMatch(runner, /- \*\*`report\.html`\*\*/)
    assert.doesNotMatch(runner, /results\/<experiment_id>\/report\/[^\n]*HuggingFace/)
    assert.match(runner, /step6_report\.sh --no-narrative/)
  }
})

test('current operator docs bind narrative and grading to Sol 1M Max', async () => {
  const [
    rootEnglish,
    rootKorean,
    runnerEnglish,
    runnerKorean,
    guideEnglish,
    guideKorean,
    gradingReadme,
    gradeWorkflowText,
    productionConfigText,
  ] = await Promise.all([
    readRepoFile('README.md'),
    readRepoFile('README_KR.md'),
    readRepoFile('batch-runner/README.md'),
    readRepoFile('batch-runner/README_KR.md'),
    readRepoFile('docs/first-experiment.md'),
    readRepoFile('docs/first-experiment_KR.md'),
    readRepoFile('batch-runner/grading_configs/README.md'),
    readRepoFile('.github/workflows/grade-run.yml'),
    readRepoFile('batch-runner/grading_configs/default_v2_sol_max.yaml'),
  ])

  for (const document of [
    rootEnglish,
    rootKorean,
    runnerEnglish,
    runnerKorean,
    guideEnglish,
    guideKorean,
  ]) {
    assert.match(document, /gpt-5\.6-sol/)
    assert.match(document, /reasoning=max/)
    assert.doesNotMatch(document, /gpt-5\.4-pro/)
  }

  const gradeWorkflow = parse(gradeWorkflowText)
  assert.equal(
    gradeWorkflow.on.workflow_dispatch.inputs.grading_config.default,
    'default_v2_sol_max.yaml',
  )
  assert.match(gradingReadme, /Production default[\s\S]*GPT-5\.6 Sol 1M Max/)
  assert.match(productionConfigText, /model: "gpt-5\.6-sol"/)
  assert.match(productionConfigText, /effort: "max"/)
  assert.match(productionConfigText, /finalization_reasoning_effort: "max"/)
  assert.match(productionConfigText, /model: "gpt-audio-1\.5"/)
  assert.doesNotMatch(productionConfigText, /^\s*context_window:/m)
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
