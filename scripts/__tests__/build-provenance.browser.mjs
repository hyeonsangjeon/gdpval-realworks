import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { build, preview } from 'vite'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const packageMetadata = JSON.parse(await readFile(new URL('../../package.json', import.meta.url), 'utf8'))
const expectedSha = process.env.EXPECTED_BUILD_SHA
const expectedRepository = process.env.EXPECTED_BUILD_REPOSITORY

if (Boolean(expectedSha) !== Boolean(expectedRepository)) {
  throw new Error('EXPECTED_BUILD_SHA and EXPECTED_BUILD_REPOSITORY must be set together')
}

async function startPreview(outDir = 'dist') {
  const server = await preview({
    root: ROOT,
    build: { outDir },
    preview: { host: '127.0.0.1', port: 0 },
    logLevel: 'silent',
  })
  const address = server.httpServer.address()
  if (!address || typeof address === 'string') throw new Error('Vite preview did not expose a TCP port')
  return {
    server,
    base: `http://127.0.0.1:${address.port}/gdpval-realworks/`,
  }
}

async function openDashboard(browser, base, viewport) {
  const context = await browser.newContext({ viewport, colorScheme: 'dark', reducedMotion: 'reduce' })
  await context.addInitScript(() => localStorage.setItem('gdpval-about-seen', 'true'))
  const page = await context.newPage()
  const runtimeErrors = []
  page.on('pageerror', (error) => runtimeErrors.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(`console: ${message.text()}`)
  })
  const response = await page.goto(base)
  try {
    await page.getByRole('heading', { name: 'GDPVal RealWorks', exact: true }).waitFor()
  } catch (error) {
    const body = (await page.locator('body').innerText()).slice(0, 1_000)
    throw new Error([
      `Dashboard did not render at ${page.url()} (HTTP ${response?.status() ?? 'unknown'}).`,
      ...runtimeErrors,
      `Body: ${body || '<empty>'}`,
    ].join('\n'), { cause: error })
  }
  return { context, page }
}

async function assertNoOverflow(page) {
  assert.equal(
    await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth),
    false,
  )
}

async function assertPublishedBuild(browser, base, sha, repository) {
  assert.match(sha, /^[0-9a-f]{40}$/)
  assert.match(repository, /^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/)
  const accessibleLabel = `Dashboard build version ${packageMetadata.version}, source commit ${sha}`
  const displayLabel = `Dashboard build v${packageMetadata.version} · ${sha.slice(0, 7)}`
  const commitUrl = `https://github.com/${repository}/commit/${sha}`
  const { context, page } = await openDashboard(browser, base, { width: 390, height: 844 })

  try {
    const link = page.getByRole('link', { name: accessibleLabel, exact: true })
    await link.scrollIntoViewIfNeeded()
    assert.equal(await link.innerText(), displayLabel)
    assert.equal(await link.getAttribute('href'), commitUrl)
    assert.equal(await link.getAttribute('data-build-provenance'), 'published')

    for (let index = 0; index < 250 && !await link.evaluate((node) => node === document.activeElement); index += 1) {
      await page.keyboard.press('Tab')
    }
    assert.equal(await link.evaluate((node) => node === document.activeElement), true)
    assert.equal(await link.evaluate((node) => node.matches(':focus-visible')), true)
    assert.notEqual(await link.evaluate((node) => getComputedStyle(node).outlineStyle), 'none')
    await assertNoOverflow(page)

    await page.setViewportSize({ width: 1280, height: 900 })
    await page.reload()
    await page.getByRole('link', { name: accessibleLabel, exact: true }).waitFor()
    await assertNoOverflow(page)
  } finally {
    await context.close()
  }
}

async function assertLocalBuild(browser, base) {
  const accessibleLabel = `Dashboard build v${packageMetadata.version}, local build without a source commit link`
  const displayLabel = `Dashboard build v${packageMetadata.version} · local build`
  const { context, page } = await openDashboard(browser, base, { width: 390, height: 844 })

  try {
    const fallback = page.locator('[data-build-provenance="local"]')
    await fallback.scrollIntoViewIfNeeded()
    assert.equal(await fallback.innerText(), displayLabel)
    assert.equal(await fallback.getAttribute('aria-label'), accessibleLabel)
    assert.equal(await page.getByRole('link', { name: /Dashboard build/ }).count(), 0)
    await assertNoOverflow(page)
  } finally {
    await context.close()
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  let localBuildRoot

  try {
    const publishedPreview = await startPreview()
    try {
      if (expectedSha && expectedRepository) {
        await assertPublishedBuild(browser, publishedPreview.base, expectedSha, expectedRepository)
      } else {
        await assertLocalBuild(browser, publishedPreview.base)
        return
      }
    } finally {
      await publishedPreview.server.close()
    }

    localBuildRoot = await mkdtemp(join(tmpdir(), 'gdpval-build-provenance-'))
    const localOutDir = join(localBuildRoot, 'dist')
    const previousSha = process.env.VITE_BUILD_SHA
    const previousRepository = process.env.VITE_BUILD_REPOSITORY
    process.env.VITE_BUILD_SHA = ''
    process.env.VITE_BUILD_REPOSITORY = ''
    try {
      await build({ root: ROOT, build: { outDir: localOutDir, emptyOutDir: true }, logLevel: 'silent' })
    } finally {
      if (previousSha === undefined) delete process.env.VITE_BUILD_SHA
      else process.env.VITE_BUILD_SHA = previousSha
      if (previousRepository === undefined) delete process.env.VITE_BUILD_REPOSITORY
      else process.env.VITE_BUILD_REPOSITORY = previousRepository
    }

    const localPreview = await startPreview(localOutDir)
    try {
      await assertLocalBuild(browser, localPreview.base)
    } finally {
      await localPreview.server.close()
    }
  } finally {
    await browser.close()
    if (localBuildRoot) await rm(localBuildRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})