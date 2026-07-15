export type JournalLens = 'experiment' | 'engineering' | 'task' | 'domain'

export interface JournalLink {
  slug: string
  title: string
  lens: JournalLens
  relatedExperiments: string[]
}

export const lensLabels: Record<JournalLens, string> = {
  experiment: '실험 회고',
  engineering: '엔지니어링 노트',
  task: '작업 해부',
  domain: '도메인 관찰',
}

export const journalCatalog = {
  '360-minute-experiment': {
    slug: '360-minute-experiment',
    title: '220개의 실제 업무를 360분 안에 실행한다는 것',
    lens: 'engineering',
    relatedExperiments: ['exp008', 'exp010', 'exp025', 'exp026'],
  },
  'honest-pipeline-lower-score': {
    slug: 'honest-pipeline-lower-score',
    title: '성공으로 기록됐지만 정말 성공이었을까',
    lens: 'experiment',
    relatedExperiments: ['exp013', 'exp025'],
  },
  'from-audio-to-multimodal-sandbox': {
    slug: 'from-audio-to-multimodal-sandbox',
    title: 'AI가 오디오 파일을 듣지 못했을 때',
    lens: 'domain',
    relatedExperiments: ['exp011', 'exp012', 'exp026'],
  },
  'what-does-success-mean': {
    slug: 'what-does-success-mean',
    title: '성공률 90.9%는 실제 업무 성공을 뜻하는가',
    lens: 'task',
    relatedExperiments: ['exp026'],
  },
  'why-build-a-sandbox': {
    slug: 'why-build-a-sandbox',
    title: 'subprocess만으로는 부족했다: sandbox를 만든 이유',
    lens: 'experiment',
    relatedExperiments: ['exp003', 'exp008', 'exp010', 'exp011', 'exp012', 'exp025', 'exp026'],
  },
} satisfies Record<string, JournalLink>

const journalLinks = Object.values(journalCatalog)

const PUBLIC_EXPERIMENT_URLS: Record<string, string> = {
  exp026: 'https://hyeonsangjeon.github.io/gdpval-realworks/experiments/exp026',
}

export function getExperimentHref(experimentId: string) {
  return PUBLIC_EXPERIMENT_URLS[experimentId] ?? `/experiments/${experimentId}`
}

export function isExternalExperimentHref(href: string) {
  return href.startsWith('http')
}

export function getJournalLinksForExperiment(experimentId: string | undefined) {
  if (!experimentId) return []
  return journalLinks.filter((article) => article.relatedExperiments.includes(experimentId))
}