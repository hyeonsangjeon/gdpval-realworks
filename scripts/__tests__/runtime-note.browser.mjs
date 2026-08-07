import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { preview } from 'vite'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const runtimePath = new URL('../../public/generated/runtime-note.json', import.meta.url)
const reportsPath = new URL('../../public/generated/reports-index.json', import.meta.url)
const chapterTitles = [
  '같은 220개, 서로 다른 시간',
  '빠른 작업만 남는 편향',
  'Checkpoint, watchdog, relay',
  '복구가 만든 새로운 경계',
  '시간 제한도 실험 조건이다',
]

const clone = (value) => structuredClone(value)

async function assertBenchmarkHidden(page) {
  for (const title of chapterTitles) {
    assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 0)
  }
  assert.equal(await page.locator('.grid.grid-cols-3.border-y').count(), 0)
  assert.equal(await page.getByRole('heading', { name: 'exp026 resume round별 회복 결과' }).count(), 0)
  assert.equal(await page.getByRole('complementary', { name: 'Runtime evidence source' }).count(), 0)
}

async function main() {
  const [runtimeNote, reportsIndex] = await Promise.all([
    readFile(runtimePath, 'utf8').then(JSON.parse),
    readFile(reportsPath, 'utf8').then(JSON.parse),
  ])
  const server = await preview({
    root: ROOT,
    preview: { host: '127.0.0.1', port: 0 },
    logLevel: 'silent',
  })
  const address = server.httpServer.address()
  if (!address || typeof address === 'string') throw new Error('Vite preview did not expose a TCP port')
  const base = `http://127.0.0.1:${address.port}/gdpval-realworks`
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  })
  const page = await context.newPage()

  try {
    await page.goto(`${base}/notes/360-minute-experiment`)
    const source = page.getByRole('complementary', { name: 'Runtime evidence source' })
    await source.waitFor()
    assert.equal(await source.locator('a').count(), 11)
    const exp026Links = page.locator('a[href="https://hyeonsangjeon.github.io/gdpval-realworks/experiments/exp026"]')
    assert.ok(await exp026Links.count() >= 2)
    for (const link of await exp026Links.all()) {
      assert.equal(await link.getAttribute('target'), '_blank')
      assert.equal(await link.getAttribute('rel'), 'noopener noreferrer')
    }
    assert.equal(await page.getByRole('heading', { name: '같은 220개, 서로 다른 시간', exact: true }).count(), 1)
    assert.equal(await page.getByRole('img', { name: /330분 step hard timeout/ }).count(), 1)
    assert.deepEqual(
      await page.getByRole('heading', { name: 'exp026 resume round별 회복 결과' })
        .locator('xpath=ancestor::figure')
        .locator('.recharts-xAxis .recharts-cartesian-axis-tick-value')
        .allTextContents(),
      ['Round 1', 'Round 2'],
    )
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)

    await page.evaluate(() => {
      globalThis.__runtimeChartMutations = 0
      new MutationObserver((records) => {
        for (const record of records) {
          if (record.target instanceof SVGElement && record.target.closest('.recharts-wrapper')) {
            globalThis.__runtimeChartMutations += 1
          }
        }
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ['d', 'width', 'height', 'transform'] })
    })
    await page.waitForTimeout(600)
    assert.equal(await page.evaluate(() => globalThis.__runtimeChartMutations), 0)

    await page.setViewportSize({ width: 1280, height: 900 })
    await page.reload()
    await source.waitFor()
    const desktopHero = page.locator('figure').first().locator('svg:visible')
    assert.equal(await desktopHero.getByText('MAY 18 · INCIDENT', { exact: true }).count(), 1)
    assert.equal(await desktopHero.getByText('AFTER MAY 20 FIX · CONDITION A', { exact: true }).count(), 1)
    const labelBoxes = await desktopHero.locator('text').evaluateAll((nodes) => nodes
      .filter((node) => ['350', '360', 'step ceiling', 'job cap', 'SIGKILL · 330 step hard stop'].includes(node.textContent ?? ''))
      .map((node) => {
        const box = node.getBoundingClientRect()
        return { text: node.textContent, left: box.left, right: box.right, top: box.top }
      }))
    const overlaps = labelBoxes.some((box, index) => labelBoxes.some((other, otherIndex) => (
      index < otherIndex
      && Math.abs(box.top - other.top) < 4
      && box.left < other.right
      && other.left < box.right
    )))
    assert.equal(overlaps, false)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)

    const invalidPolicy = clone(runtimeNote)
    invalidPolicy.current_policy.step_timeout_minutes = 280
    await page.route('**/generated/runtime-note.json*', (route) => route.fulfill({ json: invalidPolicy }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /runtime-note\.json/)
    await assertBenchmarkHidden(page)
    await page.unroute('**/generated/runtime-note.json*')

    await page.route('**/generated/runtime-note.json*', (route) => route.fulfill({ body: 'null', contentType: 'application/json' }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /runtime-note\.json/)
    await assertBenchmarkHidden(page)
    await page.unroute('**/generated/runtime-note.json*')

    const invalidReports = clone(reportsIndex)
    invalidReports.reports.find((report) => report.short_id === 'exp026')
      .recovery_stats.resume_rounds.per_round['1'] = null
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: invalidReports }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp026/)
    await assertBenchmarkHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    await page.reload()
    await source.waitFor()
    await page.evaluate((url) => {
      history.pushState({}, '', url)
      dispatchEvent(new PopStateEvent('popstate'))
    }, '/gdpval-realworks/notes/honest-pipeline-lower-score')
    await page.getByRole('heading', { name: '성공으로 기록됐지만 정말 성공이었을까', exact: true }).waitFor()
    await page.route('**/generated/runtime-note.json*', (route) => route.abort())
    await page.evaluate((url) => {
      history.pushState({}, '', url)
      dispatchEvent(new PopStateEvent('popstate'))
    }, '/gdpval-realworks/notes/360-minute-experiment')
    assert.match(await page.getByRole('alert').innerText(), /Failed to fetch/)
    await assertBenchmarkHidden(page)
  } finally {
    await context.close()
    await browser.close()
    await server.close()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
