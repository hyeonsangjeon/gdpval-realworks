import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
import { parse } from 'yaml'

const readSource = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

async function importTypeScriptModule(path) {
  const source = await readSource(path)
  const result = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 },
    reportDiagnostics: true,
  })
  assert.equal(result.diagnostics?.length ?? 0, 0)
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

test('published build provenance links an exact validated commit', async () => {
  const { resolveBuildProvenance } = await importTypeScriptModule('src/lib/buildProvenance.ts')
  const sha = '0123456789abcdef0123456789abcdef01234567'

  assert.deepEqual(resolveBuildProvenance({
    version: '0.2.0',
    sha,
    repository: 'hyeonsangjeon/gdpval-realworks',
  }), {
    kind: 'published',
    version: '0.2.0',
    shortSha: '0123456',
    fullSha: sha,
    repository: 'hyeonsangjeon/gdpval-realworks',
    commitUrl: `https://github.com/hyeonsangjeon/gdpval-realworks/commit/${sha}`,
    displayLabel: 'Dashboard build v0.2.0 · 0123456',
    accessibleLabel: `Dashboard build version 0.2.0, source commit ${sha}`,
  })
})

test('local build provenance fails closed for malformed public values', async () => {
  const { resolveBuildProvenance } = await importTypeScriptModule('src/lib/buildProvenance.ts')
  const sha = '0123456789abcdef0123456789abcdef01234567'
  const cases = [
    { name: 'missing values', input: { version: '0.2.0' } },
    { name: 'uppercase SHA', input: { version: '0.2.0', sha: sha.toUpperCase(), repository: 'owner/repo' } },
    { name: 'short SHA', input: { version: '0.2.0', sha: sha.slice(0, -1), repository: 'owner/repo' } },
    { name: 'missing repository name', input: { version: '0.2.0', sha, repository: 'owner' } },
    { name: 'extra path segment', input: { version: '0.2.0', sha, repository: 'owner/repo/commit' } },
    { name: 'URL injection', input: { version: '0.2.0', sha, repository: 'owner/repo?tab=readme' } },
    { name: 'invalid owner', input: { version: '0.2.0', sha, repository: '-owner/repo' } },
    { name: 'relative repository', input: { version: '0.2.0', sha, repository: 'owner/..' } },
    { name: 'invalid version', input: { version: 'release/latest', sha, repository: 'owner/repo' } },
  ]

  for (const { name, input } of cases) {
    const provenance = resolveBuildProvenance(input)
    assert.equal(provenance.kind, 'local', name)
    assert.equal(provenance.commitUrl, null, name)
    assert.match(provenance.displayLabel, /local build$/, name)
  }
})

test('build wiring exposes only exact public GitHub identity', async () => {
  const [workflowText, viteSource, dashboardSource, declarations, packageMetadata] = await Promise.all([
    readSource('.github/workflows/deploy.yml'),
    readSource('vite.config.ts'),
    readSource('src/pages/Dashboard.tsx'),
    readSource('src/vite-env.d.ts'),
    readSource('package.json').then(JSON.parse),
  ])
  const workflow = parse(workflowText)
  const buildStep = workflow.jobs.validate.steps.find((step) => step.name === 'Build')
  const browserStep = workflow.jobs.validate.steps.find(
    (step) => step.name === 'Verify dashboard build provenance in browser',
  )

  assert.deepEqual(buildStep.env, {
    NODE_ENV: 'production',
    VITE_BUILD_SHA: '${{ github.sha }}',
    VITE_BUILD_REPOSITORY: '${{ github.repository }}',
  })
  assert.deepEqual(browserStep.env, {
    EXPECTED_BUILD_SHA: '${{ github.sha }}',
    EXPECTED_BUILD_REPOSITORY: '${{ github.repository }}',
  })
  assert.match(viteSource, /readFileSync\(new URL\('\.\/package\.json', import\.meta\.url\)/)
  assert.match(viteSource, /__APP_VERSION__: JSON\.stringify\(packageMetadata\.version\)/)
  assert.match(declarations, /declare const __APP_VERSION__: string/)
  assert.match(declarations, /readonly VITE_BUILD_SHA\?: string/)
  assert.match(declarations, /readonly VITE_BUILD_REPOSITORY\?: string/)
  assert.match(dashboardSource, /resolveBuildProvenance\(\{/)
  assert.doesNotMatch(dashboardSource, /v0\.2\.0/)
  assert.equal(packageMetadata.scripts['pretest:aggregate'], 'npm run aggregate')
  assert.equal(packageMetadata.scripts['test:aggregate'], 'npm run test:aggregate:prepared')
  assert.match(packageMetadata.scripts['test:aggregate:prepared'], /build-provenance\.test\.mjs/)
  assert.equal(browserStep.run, 'npm run test:build-provenance-browser:dist')
})