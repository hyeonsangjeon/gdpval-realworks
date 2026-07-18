import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { preview } from 'vite'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const integrityPath = new URL('../../public/generated/integrity-note.json', import.meta.url)
const reportsPath = new URL('../../public/generated/reports-index.json', import.meta.url)
const chapterTitles = [
  '먼저, 숫자가 달라졌다',
  '실행되지 않은 파일 힌트',
  '기록되지 않은 qa_failed',
  '같은 자, 다른 규칙',
  '지표보다 의미를 버전 관리하기',
]

const clone = (value) => structuredClone(value)

async function assertIntegrityHidden(page) {
  for (const title of chapterTitles) {
    assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 0)
  }
  assert.equal(await page.locator('.grid.grid-cols-3.border-y').count(), 0)
  assert.equal(await page.getByRole('heading', { name: '무결성 수정 전후의 실행 완료율' }).count(), 0)
  assert.equal(await page.getByRole('complementary', { name: 'Integrity evidence source' }).count(), 0)
  assert.equal(await page.getByRole('navigation', { name: '무결성 수정 전후 실험 상세' }).count(), 0)
}

async function main() {
  const [integrityNote, reportsIndex] = await Promise.all([
    readFile(integrityPath, 'utf8').then(JSON.parse),
    readFile(reportsPath, 'utf8').then(JSON.parse),
  ])
  const server = await preview({ root: ROOT, preview: { host: '127.0.0.1', port: 0 }, logLevel: 'silent' })
  const address = server.httpServer.address()
  if (!address || typeof address === 'string') throw new Error('Vite preview did not expose a TCP port')
  const base = `http://127.0.0.1:${address.port}/gdpval-realworks`
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'dark', reducedMotion: 'reduce' })
  const page = await context.newPage()

  try {
    await page.goto(`${base}/notes/honest-pipeline-lower-score`)
    const source = page.getByRole('complementary', { name: 'Integrity evidence source' })
    await source.waitFor()
    assert.equal(await source.locator('a').count(), 8)
    assert.deepEqual(
      await page.getByRole('navigation', { name: '무결성 수정 전후 실험 상세' }).getByRole('link').allTextContents(),
      ['95.9%exp013 · 211/220', '82.3%exp025 · 181/220'],
    )
    for (const title of chapterTitles) {
      assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 1)
    }
    const chart = page.getByRole('heading', { name: '무결성 수정 전후의 실행 완료율' }).locator('xpath=ancestor::figure')
    assert.deepEqual(await chart.locator('.recharts-xAxis .recharts-cartesian-axis-tick-value').allTextContents(), ['exp013 · 2026-03-27', 'exp025 · 2026-05-20'])
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)
    await page.evaluate(() => {
      globalThis.__integrityChartMutations = 0
      new MutationObserver((records) => {
        for (const record of records) {
          if (record.target instanceof SVGElement && record.target.closest('.recharts-wrapper')) globalThis.__integrityChartMutations += 1
        }
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ['d', 'width', 'height', 'transform'] })
    })
    await page.waitForTimeout(600)
    assert.equal(await page.evaluate(() => globalThis.__integrityChartMutations), 0)

    await page.setViewportSize({ width: 1280, height: 900 })
    await page.reload()
    await source.waitFor()
    const hero = page.locator('figure').first().locator('svg:visible')
    for (const text of ['95.9%', '82.3%', '-13.6%p', 'not a causal estimate']) {
      assert.equal(await hero.getByText(text, { exact: true }).count(), 1)
    }
    const firstSection = page.getByRole('heading', { name: chapterTitles[0], exact: true }).locator('xpath=ancestor::section')
    assert.equal(await firstSection.locator('h2').evaluate((node) => getComputedStyle(node).fontSize), '34px')
    assert.equal(await firstSection.locator('p').first().evaluate((node) => getComputedStyle(node).lineHeight), '34.85px')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)

    const invalidSource = clone(integrityNote)
    invalidSource.interpretation.causal_attribution = true
    await page.route('**/generated/integrity-note.json*', (route) => route.fulfill({ json: invalidSource }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /integrity-note\.json/)
    await assertIntegrityHidden(page)
    await page.unroute('**/generated/integrity-note.json*')

    const invalidIdentity = clone(integrityNote)
    invalidIdentity.interpretation.missing_execution_identities[1] = 'unrelated_identity'
    await page.route('**/generated/integrity-note.json*', (route) => route.fulfill({ json: invalidIdentity }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /integrity-note\.json/)
    await assertIntegrityHidden(page)
    await page.unroute('**/generated/integrity-note.json*')

    await page.route('**/generated/integrity-note.json*', (route) => route.fulfill({ body: 'null', contentType: 'application/json' }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /integrity-note\.json/)
    await assertIntegrityHidden(page)
    await page.unroute('**/generated/integrity-note.json*')

    const duplicateReports = clone(reportsIndex)
    duplicateReports.reports.push(clone(duplicateReports.reports.find((report) => report.short_id === 'exp013')))
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: duplicateReports }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp013/)
    await assertIntegrityHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    await page.reload()
    await source.waitFor()
    await page.evaluate((url) => {
      history.pushState({}, '', url)
      dispatchEvent(new PopStateEvent('popstate'))
    }, '/gdpval-realworks/notes/from-audio-to-multimodal-sandbox')
    await page.getByRole('heading', { name: 'AI가 오디오 파일을 듣지 못했을 때', exact: true }).waitFor()
    await page.route('**/generated/integrity-note.json*', (route) => route.abort())
    await page.evaluate((url) => {
      history.pushState({}, '', url)
      dispatchEvent(new PopStateEvent('popstate'))
    }, '/gdpval-realworks/notes/honest-pipeline-lower-score')
    assert.match(await page.getByRole('alert').innerText(), /Failed to fetch/)
    await assertIntegrityHidden(page)
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
