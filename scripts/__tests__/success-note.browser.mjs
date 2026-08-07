import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { preview } from 'vite'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const successPath = new URL('../../public/generated/success-note.json', import.meta.url)
const reportsPath = new URL('../../public/generated/reports-index.json', import.meta.url)
const chapterTitles = [
  '90.9%를 보고 일이 끝났다고 생각했다',
  '220개 대신 두 태스크로 범위를 줄였다',
  '파일을 열고 꼭 필요한 분석부터 셌다',
  '파일은 열렸지만 확인 가능한 범위가 달랐다',
  '세 가지 발견이 처음의 가설을 바꿨다',
  '문제는 네 질문을 한 줄에 넣은 데 있었다',
]

const clone = (value) => structuredClone(value)

async function assertSuccessHidden(page) {
  for (const title of chapterTitles) {
    assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 0)
  }
  assert.equal(await page.locator('.grid.grid-cols-3.border-y').count(), 0)
  assert.equal(await page.getByRole('heading', { name: '같은 직군, 서로 다른 내부 진단' }).count(), 0)
  assert.equal(await page.getByRole('complementary', { name: 'Success evidence source' }).count(), 0)
  assert.equal(await page.getByText('FOUR LAYERS · TWO TASKS', { exact: true }).count(), 0)
  assert.equal(await page.locator('figure').first().locator('svg:visible').count(), 0)
  assert.equal(await page.locator('[data-citation-id]').count(), 0)
  assert.equal(await page.locator('[data-evidence-id]').count(), 0)
}

async function main() {
  const [successNote, reportsIndex] = await Promise.all([
    readFile(successPath, 'utf8').then(JSON.parse),
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
    let releaseSuccess
    let markIntercepted
    const intercepted = new Promise((resolve) => { markIntercepted = resolve })
    const released = new Promise((resolve) => { releaseSuccess = resolve })
    await page.route('**/generated/success-note.json*', async (route) => {
      markIntercepted()
      await released
      await route.fulfill({ json: successNote })
    })
    await page.goto(`${base}/journal/what-does-success-mean?source=legacy`)
    await intercepted
    await page.waitForURL('**/notes/what-does-success-mean?source=legacy')
    await page.getByRole('status').waitFor()
    await assertSuccessHidden(page)
    releaseSuccess()
    const source = page.getByRole('complementary', { name: 'Success evidence source' })
    await source.waitFor()
    await page.unroute('**/generated/success-note.json*')

    assert.equal(await source.locator('a').count(), 7)
    const exp026Detail = source.getByRole('link', { name: 'exp026 상세', exact: true })
    assert.equal(
      await exp026Detail.getAttribute('href'),
      'https://hyeonsangjeon.github.io/gdpval-realworks/experiments/exp026',
    )
    assert.equal(await exp026Detail.getAttribute('target'), '_blank')
    assert.equal(await exp026Detail.getAttribute('rel'), 'noopener noreferrer')
    for (const title of chapterTitles) {
      assert.equal(await page.getByRole('heading', { name: title, exact: true }).count(), 1)
    }
    const taskSection = page.getByRole('heading', { name: chapterTitles[1], exact: true }).locator('xpath=ancestor::section')
    assert.match(await taskSection.innerText(), /확인할 질문도 세 가지로 줄였다[\s\S]*실행이 끝났는가[\s\S]*파일이 실제로 열리는가[\s\S]*요청한 핵심 분석이 들어 있는가/)
    const hypothesisSection = page.getByRole('heading', { name: chapterTitles[4], exact: true }).locator('xpath=ancestor::section')
    const hypothesisText = await hypothesisSection.innerText()
    assert.match(hypothesisText, /발견은 세 가지였다[\s\S]*success 규칙을 통과했다는 상태[\s\S]*둘째[\s\S]*셋째[\s\S]*처음의 가설은 지지되지 않았다/)
    assert.doesNotMatch(hypothesisText, /프로세스가 끝났다는 신호|실행이 끝났음을 보여줬다|실행 완료율|실행 경로를 완료/)
    assert.equal(await hypothesisSection.locator('li').count(), 3)
    const rootSection = page.getByRole('heading', { name: chapterTitles[5], exact: true }).locator('xpath=ancestor::section')
    const rootText = await rootSection.innerText()
    assert.match(rootText, /근본 원인은 모델 하나가 아니었다[\s\S]*네 질문을 success 한 줄에 넣어 기록한 방식[\s\S]*report의 success 상태 비율/)
    assert.doesNotMatch(rootText, /실행 완료율|실행 경로를 완료/)
    const resultSection = page.getByRole('heading', { name: chapterTitles[3], exact: true }).locator('xpath=ancestor::section')
    assert.match(await resultSection.innerText(), /기본 형식과 길이는 확인됐다[\s\S]*요구 충실도 전체는 미확인/)
    const mobileHero = page.getByRole('img', { name: /workbook은 qa_failed/ })
    assert.match(await mobileHero.innerText(), /qa_failed[\s\S]*35\/500 companies[\s\S]*Self-QA 2\/10[\s\S]*success[\s\S]*PPTX 32 · PDF 32[\s\S]*Self-QA 9\/10[\s\S]*external quality · unknown/)
    const metrics = page.locator('.grid.grid-cols-3.border-y')
    const metricsText = await metrics.innerText()
    assert.match(metricsText, /200\/220[\s\S]*report success 상태[\s\S]*90\.9% · success 규칙 통과율[\s\S]*35\/500[\s\S]*7\.0%[\s\S]*미확인/)
    assert.doesNotMatch(metricsText, /실행 완료율|실행 경로를 완료/)
    const chart = page.getByRole('heading', { name: '같은 직군, 서로 다른 내부 진단' }).locator('xpath=ancestor::figure')
    assert.deepEqual(await chart.locator('.recharts-xAxis .recharts-cartesian-axis-tick-value').allTextContents(), ['S&P 500 workbook', 'LatAm briefing'])
    assert.equal(await page.locator('[data-citation-id]').count(), 30)
    assert.equal(await page.locator('[data-evidence-id]').count(), 10)

    const artifactCitation = page.locator('[data-citation-id="workbook-artifact"]').first()
    await artifactCitation.click()
    assert.match(page.url(), /#evidence-workbook-artifact$/)
    const artifactEvidence = page.locator('[data-evidence-id="workbook-artifact"]')
    assert.match(await artifactEvidence.innerText(), /sp500_pe_deep_dive\.xlsx@47aed3c · sha256 fb26bf7b…/)
    assert.equal(
      await artifactEvidence.locator('a').first().getAttribute('href'),
      'https://huggingface.co/datasets/HyeonSang/exp026_sandbox_skills_multimodal/blob/47aed3c0b13eaa90eb02803bec9d5c75e559f416/deliverable_files/8079e27d-b6f3-4f75-a9b5-db27903c798d/sp500_pe_deep_dive.xlsx',
    )
    const backref = artifactEvidence.getByRole('link', { name: /본문 1로 돌아가기/ })
    assert.equal(await backref.getAttribute('href'), '#citation-section-3-paragraph-1-workbook-artifact')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)

    await page.evaluate(() => {
      globalThis.__successChartMutations = 0
      new MutationObserver((records) => {
        for (const record of records) {
          if (record.target instanceof SVGElement && record.target.closest('.recharts-wrapper')) globalThis.__successChartMutations += 1
        }
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ['d', 'width', 'height', 'transform'] })
    })
    await page.waitForTimeout(600)
    assert.equal(await page.evaluate(() => globalThis.__successChartMutations), 0)

    await page.setViewportSize({ width: 1280, height: 900 })
    await page.reload()
    await source.waitFor()
    const desktopHero = page.locator('figure').first().locator('svg:visible')
    for (const text of ['qa_failed', 'success', '5 sheets · open', '35 / 500 companies', '32 slides · 32 pages', 'EXTERNAL QUALITY · UNKNOWN']) {
      assert.equal(await desktopHero.getByText(text, { exact: true }).count(), 1)
    }
    const heroBox = await desktopHero.boundingBox()
    assert.ok(heroBox && heroBox.width > 900 && heroBox.height > 300)
    const firstSection = page.getByRole('heading', { name: chapterTitles[0], exact: true }).locator('xpath=ancestor::section')
    assert.equal(await firstSection.locator('h2').evaluate((node) => getComputedStyle(node).fontSize), '34px')
    assert.equal(await firstSection.locator('p').first().evaluate((node) => getComputedStyle(node).lineHeight), '34.85px')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false)

    const invalidSource = clone(successNote)
    invalidSource.interpretation.external_grade_available = true
    await page.route('**/generated/success-note.json*', (route) => route.fulfill({ json: invalidSource }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /success-note\.json/)
    await assertSuccessHidden(page)
    await page.unroute('**/generated/success-note.json*')

    const gradeDrift = clone(successNote)
    gradeDrift.grade_inventory.external_grade_matches = 1
    await page.route('**/generated/success-note.json*', (route) => route.fulfill({ json: gradeDrift }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /success-note\.json/)
    await assertSuccessHidden(page)
    await page.unroute('**/generated/success-note.json*')

    await page.route('**/generated/success-note.json*', (route) => route.fulfill({ body: 'null', contentType: 'application/json' }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /success-note\.json/)
    await assertSuccessHidden(page)
    await page.unroute('**/generated/success-note.json*')

    await page.route('**/generated/success-note.json*', (route) => route.fulfill({ status: 404, body: 'missing' }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /Failed to fetch success note: 404/)
    await assertSuccessHidden(page)
    await page.unroute('**/generated/success-note.json*')

    const missingReport = clone(reportsIndex)
    missingReport.reports = missingReport.reports.filter((report) => report.short_id !== 'exp026')
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: missingReport }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp026/)
    await assertSuccessHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    const duplicateReport = clone(reportsIndex)
    duplicateReport.reports.push(clone(duplicateReport.reports.find((report) => report.short_id === 'exp026')))
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: duplicateReport }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp026/)
    await assertSuccessHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    const malformedReport = clone(reportsIndex)
    malformedReport.reports.find((report) => report.short_id === 'exp026').task_qa['8079e27d-b6f3-4f75-a9b5-db27903c798d'] = 3
    await page.route('**/generated/reports-index.json*', (route) => route.fulfill({ json: malformedReport }))
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /exp026/)
    await assertSuccessHidden(page)
    await page.unroute('**/generated/reports-index.json*')

    await page.route('**/generated/success-note.json*', (route) => route.abort())
    await page.reload()
    assert.match(await page.getByRole('alert').innerText(), /Failed to fetch/)
    await assertSuccessHidden(page)
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
