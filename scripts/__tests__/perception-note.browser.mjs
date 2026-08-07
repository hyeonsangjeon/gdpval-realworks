import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { preview } from 'vite'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const perceptionPath = new URL('../../public/generated/perception-note.json', import.meta.url)
const reportsPath = new URL('../../public/generated/reports-index.json', import.meta.url)
const chapterTitles = [
  '경로는 감각이 아니다',
  '조건부 hearing',
  'hearing + vision + Skills',
  '25/25 · 24/25 · 23/25가 말하는 것',
  '관측된 runtime과 format 실패',
  '다음 perception contract',
]

const clone = (value) => structuredClone(value)

async function assertPerceptionHidden(page) {
  for (const title of chapterTitles) {
    assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 0)
  }
  assert.equal(await page.locator('.grid.grid-cols-3.border-y').count(), 0)
  assert.equal(await page.getByRole('heading', { name: 'Information 25개 작업의 관측 결과' }).count(), 0)
  assert.equal(await page.getByRole('complementary', { name: 'Perception evidence source' }).count(), 0)
  assert.equal(await page.getByRole('navigation', { name: 'perception 단계별 실험 상세' }).count(), 0)
  assert.equal(await page.locator('figure').first().locator('svg:visible').count(), 0)
  assert.equal(await page.locator('[data-citation-id]').count(), 0)
  assert.equal(await page.locator('[data-evidence-id]').count(), 0)
}

async function main() {
  const [perceptionNote, reportsIndex] = await Promise.all([
    readFile(perceptionPath, 'utf8').then(JSON.parse),
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
    let releasePerception
    await page.route('**/generated/perception-note.json*', async (route) => {
      await new Promise((resolve) => { releasePerception = resolve })
      await route.fulfill({ json: perceptionNote })
    })
    await page.goto(`${base}/notes/from-audio-to-multimodal-sandbox`)
    await page.getByRole('status').waitFor()
    await assertPerceptionHidden(page)
    releasePerception()
    const source = page.getByRole('complementary', { name: 'Perception evidence source' })
    await source.waitFor()
    await page.unroute('**/generated/perception-note.json*')

    assert.equal(await source.locator('a').count(), 9)
    assert.deepEqual(
      await page.getByRole('navigation', { name: 'perception 단계별 실험 상세' }).getByRole('link').allTextContents(),
      ['exp011packages25/25QA 5.80 · 0 path', 'exp012audio*24/25QA 5.79 · 1 path', 'exp026audio+video23/25QA 6.00 · 2 path'],
    )
    const exp026Links = page.locator('a[href="https://hyeonsangjeon.github.io/gdpval-realworks/experiments/exp026"]')
    assert.ok(await exp026Links.count() >= 3)
    for (const link of await exp026Links.all()) {
      assert.equal(await link.getAttribute('target'), '_blank')
      assert.equal(await link.getAttribute('rel'), 'noopener noreferrer')
    }
    for (const title of chapterTitles) {
      assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 1)
    }
    const chart = page.getByRole('heading', { name: 'Information 25개 작업의 관측 결과' }).locator('xpath=ancestor::figure')
    assert.deepEqual(
      await chart.locator('.recharts-xAxis .recharts-cartesian-axis-tick-value').allTextContents(),
      ['exp011 · packages', 'exp012 · audio', 'exp026 · audio+video'],
    )
    assert.match(await page.locator('.grid.grid-cols-3.border-y').innerText(), /25 → 24 → 23 \/ 25[\s\S]*0 → 1 → 2[\s\S]*144\.1초/)
    assert.equal(await page.locator('[data-citation-id]').count(), 34)
    const failureSection = page.getByRole('heading', { name: '관측된 runtime과 format 실패', exact: true }).locator('xpath=ancestor::section')
    assert.deepEqual(
      await failureSection.locator('p').first().locator('[data-citation-id]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-citation-id'))),
      ['exp026-report', 'exp026-failure'],
    )
    assert.equal(await page.locator('[data-evidence-id]').count(), 12)
    const reportCitation = page.locator('[data-citation-id="exp012-report"]').first()
    await reportCitation.click()
    assert.match(page.url(), /#evidence-exp012-report$/)
    const reportEvidence = page.locator('[data-evidence-id="exp012-report"]')
    assert.match(await reportEvidence.innerText(), /report\.md@11f042e · L1-L72/)
    const reportBackref = reportEvidence.getByRole('link', { name: /본문 1로 돌아가기/ })
    assert.equal(await reportBackref.getAttribute('href'), '#citation-section-2-paragraph-2-exp012-report')
    assert.equal(
      await page.locator('[data-evidence-id="exp012-config"] a').first().getAttribute('href'),
      'https://github.com/hyeonsangjeon/gdpval-realworks/blob/11f042e51c2bf517aeffd9c49deb08b2cf9477cc/batch-runner/experiments/exp012_GPT52Chat_audio_multiagent.yaml#L1-L165',
    )
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)
    await page.evaluate(() => {
      globalThis.__perceptionChartMutations = 0
      new MutationObserver((records) => {
        for (const record of records) {
          if (record.target instanceof SVGElement && record.target.closest('.recharts-wrapper')) globalThis.__perceptionChartMutations += 1
        }
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ['d', 'width', 'height', 'transform'] })
    })
    await page.waitForTimeout(600)
    assert.equal(await page.evaluate(() => globalThis.__perceptionChartMutations), 0)

    await page.setViewportSize({ width: 1280, height: 900 })
    await page.reload()
    await source.waitFor()
    const desktopHero = page.locator('figure').first().locator('svg:visible')
    for (const text of ['PACKAGES', 'CONDITIONAL AUDIO', 'AUDIO + VIDEO', '25 / 25', '24 / 25', '23 / 25']) {
      assert.equal(await desktopHero.getByText(text, { exact: true }).count(), 1)
    }
    const heroBox = await desktopHero.boundingBox()
    assert.ok(heroBox && heroBox.width > 900 && heroBox.height > 300)
    const firstSection = page.getByRole('heading', { name: chapterTitles[0], exact: true }).locator('xpath=ancestor::section')
    assert.equal(await firstSection.locator('h2').evaluate((node) => getComputedStyle(node).fontSize), '34px')
    assert.equal(await firstSection.locator('p').first().evaluate((node) => getComputedStyle(node).lineHeight), '34.85px')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)

    const invalidSource = clone(perceptionNote)
    invalidSource.interpretation.causal_attribution = true
    await page.route('**/generated/perception-note.json*', (route) => route.fulfill({ json: invalidSource }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /perception-note\.json/)
    await assertPerceptionHidden(page)
    await page.unroute('**/generated/perception-note.json*')

    await page.route('**/generated/perception-note.json*', (route) => route.fulfill({ body: 'null', contentType: 'application/json' }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /perception-note\.json/)
    await assertPerceptionHidden(page)
    await page.unroute('**/generated/perception-note.json*')

    await page.route('**/generated/perception-note.json*', (route) => route.fulfill({ status: 404, body: 'missing' }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /Failed to fetch perception note: 404/)
    await assertPerceptionHidden(page)
    await page.unroute('**/generated/perception-note.json*')

    const missingReport = clone(reportsIndex)
    missingReport.reports = missingReport.reports.filter((report) => report.short_id !== 'exp012')
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: missingReport }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp012/)
    await assertPerceptionHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    const duplicateReport = clone(reportsIndex)
    duplicateReport.reports.push(clone(duplicateReport.reports.find((report) => report.short_id === 'exp026')))
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: duplicateReport }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp026/)
    await assertPerceptionHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    const malformedReport = clone(reportsIndex)
    malformedReport.reports.find((report) => report.short_id === 'exp012').sector_breakdown[0].total = 17
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: malformedReport }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp012/)
    await assertPerceptionHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    const duplicateSector = clone(reportsIndex)
    const exp012Report = duplicateSector.reports.find((report) => report.short_id === 'exp012')
    exp012Report.sector_breakdown.push({ ...clone(exp012Report.sector_breakdown[0]), success: 23, success_rate_pct: 92 })
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: duplicateSector }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp012/)
    await assertPerceptionHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    await page.route('**/generated/perception-note.json*', (route) => route.abort())
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /Failed to fetch/)
    await assertPerceptionHidden(page)
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
