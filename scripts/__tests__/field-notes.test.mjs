import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const readSource = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

test('prompt-complexity note keeps its experiment and navigation contracts', async () => {
  const [journal, catalog] = await Promise.all([
    readSource('src/data/journal.ts'),
    readSource('src/data/journalLinks.ts'),
  ])

  assert.match(catalog, /'when-more-prompt-is-less':[\s\S]*relatedExperiments: \['exp003', 'exp004', 'exp005'\]/)
  assert.match(journal, /articleSlug: 'when-more-prompt-is-less'/)
  assert.match(journal, /articleSlugs: \['when-more-prompt-is-less', 'why-build-a-sandbox'\]/)
  assert.match(journal, /\{ label: 'exp003 Baseline', primary: 95\.9, secondary: 6\.18 \}/)
  assert.match(journal, /\{ label: 'exp004 Elicit', primary: 90\.9, secondary: 5\.87 \}/)
  assert.match(journal, /\{ label: 'exp005 Headless', primary: 90\.5, secondary: 6\.16 \}/)
  assert.match(journal, /Elicit은 별도 모델이나 서비스가 아니라[\s\S]*GDPVal 연구의 프롬프트 전략이다/)
  assert.match(journal, /https:\/\/arxiv\.org\/pdf\/2510\.04374#page=37/)
})

test('prompt-complexity hero reflects the source five-step design', async () => {
  const hero = await readSource('src/components/notes/NoteHeroVisual.tsx')

  assert.match(hero, /mode: 'FIVE MANDATORY STEPS'/)
  assert.match(hero, /'2 · DISPLAY PNG'/)
  assert.match(hero, /mode: 'SAME FIVE STEPS · NEW STEP 2'/)
  assert.match(hero, /'2 · PILLOW CHECK'/)
  assert.doesNotMatch(hero, /checks: [367]/)
  assert.doesNotMatch(hero, /MORE CHECKS · FEWER FINISHES/)
})

test('comparison chart preserves mobile labels and reduced-motion behavior', async () => {
  const chart = await readSource('src/components/notes/NoteComparisonChart.tsx')

  assert.match(chart, /interval=\{chart\.kind === 'dual' \? 0 : undefined\}/)
  assert.match(chart, /const reduceMotion = useReducedMotion\(\)/)
  assert.equal(chart.match(/isAnimationActive=\{!reduceMotion\}/g)?.length, 4)
})