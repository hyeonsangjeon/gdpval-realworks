import {
  journalCatalog,
  lensLabels,
  type JournalLens,
} from './journalLinks'

export { lensLabels }
export type { JournalLens }

export interface JournalMetric {
  value: string
  label: string
  note?: string
}

export interface JournalSection {
  label?: string
  heading: string
  paragraphs: string[]
  paragraphCitations?: string[][]
  points?: string[]
  callout?: string
  calloutCitations?: string[]
  benchmarkNarrative?: 'prompt-complexity-results' | 'runtime-incident' | 'runtime-policy' | 'runtime-results' | 'integrity-observation' | 'integrity-available-files' | 'integrity-qa-failed' | 'integrity-comparison' | 'integrity-decision' | 'perception-baseline' | 'perception-audio' | 'perception-sandbox' | 'perception-results' | 'perception-failure' | 'perception-decision' | 'success-expectation' | 'success-status' | 'success-workbook' | 'success-briefing' | 'success-interpretation' | 'success-decision'
}

export interface JournalEvidence {
  id?: string
  label: string
  detail: string
  source?: string
  href: string
}

export type JournalHero =
  | {
      kind: 'visual'
  variant: 'prompt-complexity' | 'runtime' | 'integrity' | 'perception' | 'task-contrast' | 'sandbox'
      alt: string
      caption: string
    }
  | {
      kind: 'video'
      src: string
      poster?: string
      captionsSrc?: string
      alt: string
      caption: string
    }

export interface JournalChartSeries {
  label: string
  unit: string
  color: string
  domain?: [number, number]
}

export interface JournalChartDatum {
  label: string
  primary: number
  secondary?: number
}

export interface JournalComparisonChart {
  kind: 'bar' | 'stacked' | 'dual'
  title: string
  description: string
  primary: JournalChartSeries
  secondary?: JournalChartSeries
  data: JournalChartDatum[]
  caveat?: string
}

export interface JournalArticle {
  slug: string
  title: string
  dek: string
  thesis: string
  thesisCitations?: string[]
  lens: JournalLens
  publishedAt: string
  period: string
  readingMinutes: number
  relatedExperiments: string[]
  metrics: JournalMetric[]
  hero?: JournalHero
  comparisonChart?: JournalComparisonChart
  sections: JournalSection[]
  evidence: JournalEvidence[]
  benchmark?: { kind: 'prompt-complexity' | 'runtime' | 'integrity' | 'perception' | 'success' }
  readingStyle?: 'reflective'
  featured?: boolean
}

export interface ExperimentGroup {
  id: string
  question: string
  experiments: string[]
  finding: string
  caveat: string
  articleSlug?: string
  state: 'finding' | 'open' | 'caution'
}

export interface TimelineEvent {
  date: string
  title: string
  description: string
  experiments: string[]
  articleSlugs: string[]
  kind: 'experiment' | 'incident' | 'decision'
}

const REPO = 'https://github.com/hyeonsangjeon/gdpval-realworks/blob/main'
const HF_EXP026 = 'https://huggingface.co/datasets/HyeonSang/exp026_sandbox_skills_multimodal'
const INTEGRITY_SOURCE_SHA = '4371ed67b1ae4bfff5392f0d29fab7a52e1effd0'
const INTEGRITY_SOURCE = `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${INTEGRITY_SOURCE_SHA}`
const INTEGRITY_PARENT = '2b41c06fd0647c900520009f30cb26d3a5bd772e'
const INTEGRITY_FIX = '4e0e43d23fe2d829ec8e7469e1fc0ffd9aab75ff'
const INTEGRITY_FOLLOWUP = '645758e0ebfdf5985748f31756de45f1b619ee1d'
const INTEGRITY_MERGE = '4ba399f9f9528ab355b2c8fc6d703aa14b310414'
const PERCEPTION_SOURCE_SHA = '11f042e51c2bf517aeffd9c49deb08b2cf9477cc'
const PERCEPTION_SOURCE = `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${PERCEPTION_SOURCE_SHA}`
const AUDIO_PREPROCESSOR_COMMIT = 'dfc29e43598a3feda54ae5127912b7b0ec3299bd'
const SANDBOX_MULTIMODAL_COMMIT = 'eaa2789081ba7b81901ba977006f9bfd6534a0c1'
const DOCKER_ALWAYS_COMMIT = '6ac8a830a325eb95aec5fb89f38a5e9312ea1b2a'
const SUCCESS_SOURCE_SHA = '865b3e43093ddcb6942f628eb81544e5de16e15c'
const SUCCESS_SOURCE = `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${SUCCESS_SOURCE_SHA}`
const SUCCESS_CONTRACT_SHA = '99601b80b293364de29ce1d437712e6d648ac648'
const SUCCESS_CONTRACT_SOURCE = `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${SUCCESS_CONTRACT_SHA}`
const SUCCESS_HF_REVISION = '47aed3c0b13eaa90eb02803bec9d5c75e559f416'
const SUCCESS_HF = `https://huggingface.co/datasets/HyeonSang/exp026_sandbox_skills_multimodal`

export const journalArticles: JournalArticle[] = [
  {
    ...journalCatalog['when-more-prompt-is-less'],
    dek: 'baseline 뒤 Elicit은 5단계 검증을 도입했고, headless-Elicit은 그중 화면 검사를 프로그램 검사로 바꿨다. 완료율과 Self-QA가 같은 답을 주는지 exp001–005의 설계와 결과를 분리해 읽었다.',
    thesis: '이 기록에서 두 Elicit 실행은 baseline보다 적은 작업을 완료했지만, 끝까지 살아남은 결과의 자기평가는 서로 다른 방향으로 움직였다.',
    publishedAt: '2026-07-16',
    period: 'exp001 → exp005',
    readingMinutes: 8,
    benchmark: { kind: 'prompt-complexity' },
    metrics: [],
    hero: {
      kind: 'visual',
      variant: 'prompt-complexity',
      alt: 'exp003 baseline의 기본 계약과 exp004·005 Elicit의 5단계 검증 구조, 완료 작업 및 Self-QA를 비교하는 시각화',
      caption: '측정값은 benchmark report에서, 검증 구조는 각 experiment YAML에서 읽는다.',
    },
    comparisonChart: {
      kind: 'dual',
      title: '완료율은 내려갔고 Self-QA는 돌아왔다',
      description: 'subprocess로 실행한 exp003·004·005에서 완료율은 계속 낮아졌지만, Self-QA는 Elicit에서 하락한 뒤 headless-Elicit에서 baseline 수준으로 회복했다.',
      primary: { label: 'Completion', unit: '%', color: '#2563eb', domain: [0, 100] },
      secondary: { label: 'Self-QA', unit: '/10', color: '#059669', domain: [0, 10] },
      data: [],
      caveat: 'Self-QA는 외부 채점이 아니라 점수가 존재하는 결과의 자기평가다. exp004는 LibreOffice 설치 설정, exp005는 resume round도 함께 바뀌어 프롬프트 단독 효과로 읽을 수 없다.',
    },
    sections: [
      {
        heading: '질문: 검증을 더 많이 시키면 더 잘 끝낼까',
        paragraphs: [
          '이 글에서 Elicit은 별도 모델이나 서비스가 아니라, 모델에게 산출물 생성 뒤 5단계 렌더링·점검과 신뢰도 보고를 시키는 GDPVal 연구의 프롬프트 전략이다. headless-Elicit은 그중 화면으로 PNG를 보는 두 번째 단계를 Pillow 검사로 바꾼 버전이다.',
          '첫 baseline은 비교적 짧았다. 실제 파일을 만들고, 참조 파일 구조를 살피고, 결과를 plain-text로 요약하라는 정도였다. Elicit은 여기에 PDF 변환, 폰트와 PNG 확인, 5단계 검사, 마지막 CONFIDENCE 보고를 더했다. headless-Elicit은 나머지 네 단계를 유지하고 이미지 확인 방식만 화면 없는 runner에 맞췄다.',
          '가설은 자연스러웠다. 산출물을 더 꼼꼼히 확인하라고 하면 실행 성공과 결과의 자기평가가 함께 좋아질 것이라고 예상했다. 이 글은 그 두 신호가 실제로 같은 답을 줬는지 묻는다.',
        ],
      },
      {
        heading: '방법: 실행 모드를 섞지 않았다',
        paragraphs: [
          'exp001과 exp002는 code interpreter에서 baseline과 Elicit을 비교하도록 설계됐다. 하지만 현재 저장소와 공개 인덱스에는 이 canonical 두 실행의 report가 없다. 설정 차이는 읽을 수 있어도 성능 차이를 말할 수는 없다.',
          '수치 비교는 같은 GPT-5.2-chat을 subprocess로 실행한 exp003, exp004, exp005로 한정했다. exp003은 baseline, exp004는 Elicit, exp005는 headless-Elicit이다. 다만 완전한 prompt-only A/B는 아니다. exp004에서는 LibreOffice 설치 설정이 함께 바뀌었고, exp005에서는 resume_max_rounds가 2에서 1로 줄었다.',
        ],
        callout: 'exp005 YAML의 생성일은 2026-02-28인데 report date는 2026-02-27이다. 저장소에는 이 불일치의 설명이 없어 날짜 순서를 성능 원인으로 사용하지 않았다.',
      },
      {
        heading: '결과: 두 메트릭이 갈라졌다',
        paragraphs: [],
        benchmarkNarrative: 'prompt-complexity-results',
      },
      {
        heading: '해석: 살아남은 결과의 평균은 전체 커버리지가 아니다',
        paragraphs: [
          'Self-QA 평균은 점수가 존재하는 결과를 중심으로 계산된다. 실행 단계에서 탈락해 산출물을 만들지 못한 작업은 높은 품질로 복구된 것이 아니라 평균 바깥으로 빠질 수 있다. 그래서 Self-QA가 비슷하다는 사실은 같은 수의 업무를 같은 품질로 끝냈다는 뜻이 아니다.',
          'headless-Elicit이 보여준 것은 더 좁은 주장이다. 끝까지 도달한 결과의 자기평가는 baseline 수준으로 돌아왔지만, 전체 작업을 끝까지 통과시키는 능력은 돌아오지 않았다. 품질 게이트와 커버리지를 한 숫자로 합치면 이 차이가 사라진다.',
        ],
      },
      {
        heading: '실패: 검증 절차가 새로운 실패 표면이 됐다',
        paragraphs: [
          'exp004 report에는 `soffice`를 찾지 못한 실패가 반복된다. 더 많은 문서 검사를 요구했지만 runner가 그 도구를 안정적으로 제공하지 못하면 검증 단계 자체가 실행 실패가 된다.',
          'exp005에서는 `CONFIDENCE[...]`가 실행 코드로 새어 들어가 NameError를 만든 사례가 반복된다. 결과를 설명하기 위한 출력 규약이 코드 경계와 섞인 것이다. 길어진 검증 프롬프트에는 모델이 지켜야 할 계약뿐 아니라 잘못 해석할 수 있는 표면도 함께 들어왔다.',
        ],
      },
      {
        heading: '결정: 검증을 버리지 않고 가볍게 만들기',
        paragraphs: [
          '후속 exp006은 검증 자체를 포기하지 않았다. 토큰 여유를 16k로 늘리고, 검사를 lightweight하게 줄였으며, CONFIDENCE를 코드 블록 밖에 두도록 경계를 명시했다. 더 많은 문장을 추가하는 대신 실패하기 쉬운 계약을 짧고 분명하게 다시 배치했다.',
          '따라서 이 실험의 결론은 “짧은 프롬프트가 항상 낫다”가 아니다. 검증 지시는 실행 환경이 실제로 지원하고, 코드와 설명의 경계가 분명하며, 실패 시 무엇을 복구할지 알 수 있을 때만 도움이 된다. 복잡성은 품질을 공짜로 올리는 장식이 아니라 운영 비용을 가진 설계 변수였다.',
        ],
      },
    ],
    evidence: [
      {
        label: 'GDPVal 연구 Appendix A.3',
        detail: 'Elicit Capabilities 프롬프트의 원문과 5단계 검사 설계',
        href: 'https://arxiv.org/pdf/2510.04374#page=37',
      },
      {
        label: 'exp001 baseline 설정',
        detail: 'code interpreter baseline의 파일 생성·참조 검사 suffix',
        href: `${REPO}/batch-runner/experiments/exp001_GPT52Chat_baseline.yaml`,
      },
      {
        label: 'exp002 Elicit 설정',
        detail: '추가된 5단계 검사와 CONFIDENCE 규약',
        href: `${REPO}/batch-runner/experiments/exp002_GPT52Chat_elicit.yaml`,
      },
      {
        label: 'exp003 baseline 리포트',
        detail: 'subprocess baseline의 report와 결과 원문',
        href: `${REPO}/batch-runner/results/exp003_GPT52Chat_baseline_runner_exec/report/report.md`,
      },
      {
        label: 'exp004 Elicit 리포트',
        detail: 'Elicit report와 반복된 soffice 실행 실패 원문',
        href: `${REPO}/batch-runner/results/exp004_GPT52Chat_elicit_runner_exec/report/report.md`,
      },
      {
        label: 'exp005 headless-Elicit 리포트',
        detail: 'headless-Elicit report와 CONFIDENCE NameError 원문',
        href: `${REPO}/batch-runner/results/exp005_GPT52Chat_elicit_v2_runner_exec/report/report.md`,
      },
      {
        label: 'exp006 후속 설정',
        detail: '16k, lightweight checks, 코드 블록 밖 CONFIDENCE로 이어진 결정',
        href: `${REPO}/batch-runner/experiments/exp006_GPT52Chat_token16k_lite_elicit.yaml`,
      },
    ],
  },
  {
    ...journalCatalog['360-minute-experiment'],
    dek: '장시간 CI 제한은 단순한 운영 불편이 아니었다. 어떤 작업이 결과에 남는지를 바꾸는 실험 조건이었다.',
    thesis: '시간 제한을 무시한 벤치마크는 모델뿐 아니라 실행 순서와 복구 전략까지 함께 측정하게 된다.',
    publishedAt: '2026-07-15',
    period: '2026-03 — 2026-07',
    readingMinutes: 8,
    readingStyle: 'reflective',
    featured: true,
    benchmark: { kind: 'runtime' },
    metrics: [],
    hero: {
      kind: 'visual',
      variant: 'runtime',
      alt: 'watchdog, 중단 사건, step ceiling, job cap으로 이어지는 실행 시간 경계',
      caption: '측정값은 workflow 정책, incident 기록, experiment report에서 읽는다.',
    },
    comparisonChart: {
      kind: 'stacked',
      title: 'exp026 resume round별 회복 결과',
      description: '각 resume round의 attempted, recovered, still_failed를 report snapshot에서 비교한다.',
      primary: { label: 'Recovered', unit: ' tasks', color: '#059669' },
      secondary: { label: 'Still failed', unit: ' tasks', color: '#e11d48' },
      data: [],
      caveat: '각 막대의 합은 해당 round에서 다시 시도한 작업 수다. 외부 품질 점수가 아니라 실행 복구 결과다.',
    },
    sections: [
      {
        label: '사건',
        heading: '같은 220개, 서로 다른 시간',
        paragraphs: [],
        benchmarkNarrative: 'runtime-incident',
      },
      {
        label: '편향',
        heading: '빠른 작업만 남는 편향',
        paragraphs: [
          '중간에 종료된 실행을 처음부터 다시 시작하면 비용만 늘어나는 것이 아니다. 매번 앞쪽의 빠른 작업은 반복되고 뒤쪽의 느린 작업은 관측되지 않는다. 실행 순서가 표본 선택기가 되는 셈이다.',
          '필요한 것은 단순 재시도가 아니라, 완료된 작업을 정확히 식별하고 같은 입력으로 이어 실행해도 결과가 중복되거나 덮어써지지 않는 복구 계약이었다.',
        ],
        points: [
          '작업별 상태를 즉시 progress에 기록한다.',
          '다음 job이 읽을 checkpoint를 원격 저장소에 남긴다.',
          '시간이 다 되기 전에 스스로 종료하고 후속 relay를 시작한다.',
          '이미 완료된 작업은 건너뛰되 실패 상태는 정책에 따라 다시 시도한다.',
        ],
      },
      {
        label: '대응',
        heading: 'Checkpoint, watchdog, relay',
        paragraphs: [],
        benchmarkNarrative: 'runtime-policy',
      },
      {
        label: '결과',
        heading: '복구가 만든 새로운 경계',
        paragraphs: [],
        benchmarkNarrative: 'runtime-results',
      },
      {
        label: '결정',
        heading: '시간 제한도 실험 조건이다',
        paragraphs: [
          '가장 큰 교훈은 CI 안정성을 벤치마크 바깥의 문제로 취급할 수 없다는 점이다. 특정 형식이나 도메인의 작업이 더 오래 걸린다면 시간 제한은 해당 도메인을 체계적으로 덜 관측하게 만든다.',
          '그래서 이후 기록에서는 실행 완료, 복구 완료, 파일 생성, Self-QA, 외부 채점을 서로 다른 층으로 분리한다. 하나의 success 비트가 이 모든 의미를 대신하지 않도록 하는 것이 다음 실험의 출발점이 됐다.',
        ],
      },
    ],
    evidence: [
      {
        label: 'Workflow 변경 기록',
        detail: 'exp025 중단 사건과 watchdog, step ceiling, relay 도입 기록',
        href: `${REPO}/CHANGELOG.md`,
      },
      {
        label: 'exp026 공개 self-report',
        detail: '최종 실행 지표와 두 resume round의 attempted/recovered/still_failed 기록',
        href: `${HF_EXP026}/blob/main/self_report.json`,
      },
      {
        label: 'exp025 리포트',
        detail: '중단 사건 전후 실행 결과와 resume round 원문',
        href: `${REPO}/batch-runner/results/exp025_GPT54_high_postfix/report/report.md`,
      },
    ],
  },
  {
    ...journalCatalog['honest-pipeline-lower-score'],
    dek: '같은 checked-in 설정의 두 실행에서 완료율은 달랐고, 그 사이 success를 기록하는 규칙도 바뀌었다. 관측된 차이와 측정 정의의 변화를 인과로 섞지 않고 읽었다.',
    thesis: '두 실행의 완료율 차이는 관측 사실이고, success 규칙의 변화도 코드로 확인된다. 그러나 하나를 다른 하나의 원인으로 배분할 실행 정체성은 남아 있지 않다.',
    thesisCitations: ['exp013-report', 'exp025-report', 'measurement-contract'],
    publishedAt: '2026-07-15',
    period: 'exp013 → exp025',
    readingMinutes: 7,
    readingStyle: 'reflective',
    benchmark: { kind: 'integrity' },
    metrics: [],
    hero: {
      kind: 'visual',
      variant: 'integrity',
      alt: 'exp013과 exp025의 관측 완료율과 success 기록 규칙 변화를 분리해 비교하는 시각화',
      caption: '측정값은 report snapshot에서, 판정 규칙은 pinned git history에서 읽는다.',
    },
    comparisonChart: {
      kind: 'bar',
      title: '무결성 수정 전후의 실행 완료율',
      description: '두 report snapshot의 관측 완료율을 나란히 놓되, 차이를 수정의 효과로 해석하지 않는다.',
      primary: { label: 'Completion', unit: '%', color: '#b45309', domain: [0, 100] },
      data: [],
      caveat: '두 실행은 success 판정과 qa_failed 재시도 의미가 다르다. 순수한 모델 성능 전후 비교가 아니다.',
    },
    sections: [
      {
        label: '관측',
        heading: '먼저, 숫자가 달라졌다',
        paragraphs: [],
        paragraphCitations: [
          ['exp013-report', 'exp025-report'],
          ['pr38-merge', 'measurement-contract'],
        ],
        benchmarkNarrative: 'integrity-observation',
      },
      {
        label: '불변식',
        heading: '실행되지 않은 파일 힌트',
        paragraphs: [],
        paragraphCitations: [
          ['available-files-before'],
          ['available-files-after', 'measurement-contract'],
        ],
        benchmarkNarrative: 'integrity-available-files',
      },
      {
        label: '판정',
        heading: '기록되지 않은 qa_failed',
        paragraphs: [],
        paragraphCitations: [
          ['qa-failed-before'],
          ['qa-failed-after', 'measurement-contract'],
        ],
        benchmarkNarrative: 'integrity-qa-failed',
      },
      {
        label: '비교',
        heading: '같은 자, 다른 규칙',
        paragraphs: [],
        paragraphCitations: [
          ['exp013-config', 'exp025-config'],
          ['measurement-contract'],
        ],
        benchmarkNarrative: 'integrity-comparison',
        callout: '관측된 차이는 사실이다. 그 차이의 원인을 하나의 수정에 배분할 증거는 없다.',
        calloutCitations: ['measurement-contract'],
      },
      {
        label: '결정',
        heading: '지표보다 의미를 버전 관리하기',
        paragraphs: [],
        paragraphCitations: [
          ['pr38-merge', 'measurement-contract'],
          ['measurement-contract'],
        ],
        benchmarkNarrative: 'integrity-decision',
      },
    ],
    evidence: [
      {
        id: 'exp013-report',
        label: 'exp013 report snapshot과 상세',
        detail: 'PR #38 이전 실행의 summary와 task-level 상세. 본문은 배포 시점 reports-index snapshot의 완료율·success·error·Self-QA를 사용한다.',
        source: 'reports-index.json → /experiments/exp013',
        href: 'https://hyeonsangjeon.github.io/gdpval-realworks/experiments/exp013',
      },
      {
        id: 'exp025-report',
        label: 'exp025 report snapshot과 상세',
        detail: 'PR #38 이후 실행의 summary와 task-level 상세. exp013과 같은 checked-in condition이지만 실행 시점 정체성은 완전히 고정되지 않았다.',
        source: 'reports-index.json → /experiments/exp025',
        href: 'https://hyeonsangjeon.github.io/gdpval-realworks/experiments/exp025',
      },
      {
        id: 'available-files-before',
        label: '_AVAILABLE_FILES 수정 전 실행 경로',
        detail: '원본 solution.py를 먼저 기록한 뒤 메모리의 code 문자열에만 파일 힌트를 붙였다. 이후 write가 없어 subprocess가 변경 전 파일을 실행했다.',
        source: 'subprocess_runner.py@2b41c06 · L244-L272',
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${INTEGRITY_PARENT}/batch-runner/core/subprocess_runner.py#L244-L272`,
      },
      {
        id: 'available-files-after',
        label: '_AVAILABLE_FILES 수정 후 실행 경로',
        detail: '헤더를 붙인 code를 subprocess 실행 전에 code_path에 다시 기록해 약속한 실행 환경과 실제 파일을 일치시켰다.',
        source: 'subprocess_runner.py@4e0e43d · L244-L276',
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${INTEGRITY_FIX}/batch-runner/core/subprocess_runner.py#L244-L276`,
      },
      {
        id: 'qa-failed-before',
        label: 'qa_failed 수정 전 판정 경로',
        detail: 'Self-QA 재시도를 소진한 determined failure가 best_result의 status를 바꾸지 않은 채 루프를 빠져나갈 수 있었다.',
        source: 'step2_run_inference.py@2b41c06 · L1146-L1158',
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${INTEGRITY_PARENT}/batch-runner/step2_run_inference.py#L1146-L1158`,
      },
      {
        id: 'qa-failed-after',
        label: 'qa_failed 수정 후 판정 경로',
        detail: 'determined QA failure에 qa_failed status를 기록해 retry·resume·summary 경로가 실제로 작동하도록 했다.',
        source: 'step2_run_inference.py@4e0e43d · L1147-L1166',
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/blob/${INTEGRITY_FIX}/batch-runner/step2_run_inference.py#L1147-L1166`,
      },
      {
        id: 'exp013-config',
        label: 'exp013 checked-in 비교 설정',
        detail: 'Azure GPT-5.4 high, QA 기준, subprocess timeout·token·resume·relay 설정을 검증한 비교 전 실행 설정.',
        source: `exp013_GPT54_reasoning_high.yaml@${INTEGRITY_SOURCE_SHA.slice(0, 7)} · L33-L214`,
        href: `${INTEGRITY_SOURCE}/batch-runner/experiments/exp013_GPT54_reasoning_high.yaml#L33-L214`,
      },
      {
        id: 'exp025-config',
        label: 'exp025 checked-in 비교 설정',
        detail: 'exp013과 data.filter, condition_a, execution projection이 동일한지 generator가 직접 비교하는 수정 후 실행 설정.',
        source: `exp025_GPT54_high_postfix.yaml@${INTEGRITY_SOURCE_SHA.slice(0, 7)} · L36-L217`,
        href: `${INTEGRITY_SOURCE}/batch-runner/experiments/exp025_GPT54_high_postfix.yaml#L36-L217`,
      },
      {
        id: 'pr38-merge',
        label: 'PR #38 변경 묶음과 후속 정리',
        detail: 'core fix, review follow-up, merge 경계를 함께 확인한다. Anthropic content parsing fix는 두 Azure 실행 비교에는 적용되지 않는다.',
        source: `merge ${INTEGRITY_MERGE.slice(0, 7)} · follow-up ${INTEGRITY_FOLLOWUP.slice(0, 7)}`,
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/commit/${INTEGRITY_MERGE}`,
      },
      {
        id: 'measurement-contract',
        label: '측정 해석 계약과 인과 제한',
        detail: '관측 차이와 판정 의미 변화를 함께 기록하되, 누락된 실행 Git·입력 revision·Azure model revision·runner identity 때문에 causal_attribution은 false로 고정한다.',
        source: `integrity-incidents.yaml@${INTEGRITY_SOURCE_SHA.slice(0, 7)} · L1-L46`,
        href: `${INTEGRITY_SOURCE}/data/notes/integrity-incidents.yaml#L1-L46`,
      },
    ],
  },
  {
    ...journalCatalog['from-audio-to-multimodal-sandbox'],
    dek: '파일 경로를 넘기는 일과 내용을 지각하게 만드는 일은 달랐다. packages, 조건부 audio analyzer, audio·video·Skills sandbox로 이어진 세 실행을 그 차이에서 다시 읽는다.',
    thesis: '세 실행에서 확인된 것은 perception 경로의 확장이다. 그것이 결과 품질을 개선했다는 인과 효과는 아직 확인되지 않았다.',
    thesisCitations: ['exp011-config', 'exp012-config', 'exp026-config', 'perception-contract'],
    publishedAt: '2026-07-15',
    period: 'exp011 → exp012 → exp026',
    readingMinutes: 9,
    benchmark: { kind: 'perception' },
    readingStyle: 'reflective',
    metrics: [],
    hero: {
      kind: 'visual',
      variant: 'perception',
      alt: 'exp011 packages, exp012 조건부 audio analyzer, exp026 audio와 video 및 Skills sandbox로 확장된 구성 경로',
      caption: '세 report의 관측값과 checked-in 구성을 함께 보되, 경로의 확장을 품질 개선의 원인으로 읽지는 않는다.',
    },
    comparisonChart: {
      kind: 'dual',
      title: 'Information sector의 관측 결과',
      description: '세 report snapshot의 완료율과 Self-QA를 나란히 놓는다.',
      primary: { label: 'Completion', unit: '%', color: '#2563eb', domain: [0, 100] },
      secondary: { label: 'Self-QA', unit: '/10', color: '#b45309', domain: [0, 10] },
      data: [],
      caveat: '동일 task의 paired causal comparison이 아니다. 세 실행은 범위, 모델, reasoning, runner, Skills와 perception 구성이 함께 다르다.',
    },
    sections: [
      {
        label: '경계',
        heading: '경로는 감각이 아니다',
        benchmarkNarrative: 'perception-baseline',
        paragraphs: [
          'reference file에 접근하고 media package를 설치하는 것은 내용을 들었다는 뜻이 아니다.',
          '첫 실행은 파일을 다룰 환경을 넓혔지만 perception preprocessor는 구성하지 않았다.',
        ],
        paragraphCitations: [['exp011-config'], ['exp011-report', 'perception-contract']],
      },
      {
        label: '청각',
        heading: '조건부 hearing',
        benchmarkNarrative: 'perception-audio',
        paragraphs: [
          '다음 실행은 audio reference가 있는 task에만 별도 analyzer를 호출하고 분석을 prompt 앞에 주입하도록 구성했다.',
          '그러나 구성 주석, YAML 날짜와 report snapshot은 서로 완전히 맞지 않는다.',
        ],
        paragraphCitations: [['exp012-config', 'audio-history'], ['exp012-report', 'exp012-config', 'perception-contract']],
      },
      {
        label: '확장',
        heading: 'hearing + vision + Skills',
        benchmarkNarrative: 'perception-sandbox',
        paragraphs: [
          '세 번째 실행은 조건부 audio와 video analysis, task-aware Skills, sandbox execution을 한 경로에 묶었다.',
          'Docker가 없을 때 local subprocess로 물러서지 않도록 실행 경계도 함께 바뀌었다.',
        ],
        paragraphCitations: [['exp026-config', 'sandbox-history'], ['exp026-runner', 'docker-history']],
      },
      {
        label: '관측',
        heading: '세 report가 말하는 것',
        benchmarkNarrative: 'perception-results',
        paragraphs: [
          '세 report에서 Information sector의 완료 수와 Self-QA는 서로 다른 방향으로 움직였다.',
          '이 차이는 perception의 단독 효과가 아니라 서로 다른 실행 묶음의 관측값이다.',
        ],
        paragraphCitations: [['exp011-report', 'exp012-report', 'exp026-report'], ['exp011-report', 'exp012-report', 'exp026-report', 'perception-contract']],
        callout: '같은 sector row라는 사실만으로 paired experiment가 되지는 않는다. Information-only 실행과 full benchmark의 sector slice는 관측 범위가 다르다.',
        calloutCitations: ['perception-contract'],
      },
      {
        label: '병목',
        heading: '관측된 runtime과 format 실패',
        benchmarkNarrative: 'perception-failure',
        paragraphs: [
          '입력 경로가 넓어진 실행에서도 media runtime은 독립적으로 실패했다.',
          '지각, 실행, 산출물 규격, 외부 품질을 하나의 success로 압축하면 다음 병목을 구분할 수 없다.',
        ],
        paragraphCitations: [['exp026-report', 'exp026-failure'], ['exp026-report', 'exp026-config', 'perception-contract']],
      },
      {
        label: '결정',
        heading: '다음 perception contract',
        benchmarkNarrative: 'perception-decision',
        paragraphs: [
          '다음 실행부터 perception의 구성 여부와 실제 호출·결과를 분리해 기록한다.',
          '외부 품질과 실행 identity가 없는 동안 architecture change와 quality claim 사이의 문장을 멈춘다.',
        ],
        paragraphCitations: [['perception-contract'], ['audio-history', 'sandbox-history', 'docker-history', 'perception-contract']],
      },
    ],
    evidence: [
      {
        id: 'exp011-report',
        label: 'exp011 report · Information 관측값',
        detail: 'full benchmark 실행 summary와 Information sector row. 외부 grading은 대기 상태다.',
        source: `report.md@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L1-L75`,
        href: `${PERCEPTION_SOURCE}/batch-runner/results/exp011_GPT52Chat_domain_packages/report/report.md#L1-L75`,
      },
      {
        id: 'exp012-report',
        label: 'exp012 report · Information-only 관측값',
        detail: 'Information-only summary와 sector row. YAML metadata와 다른 report date를 포함하며 외부 grading은 대기 상태다.',
        source: `report.md@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L1-L72`,
        href: `${PERCEPTION_SOURCE}/batch-runner/results/exp012_GPT52Chat_audio_multiagent/report/report.md#L1-L72`,
      },
      {
        id: 'exp026-report',
        label: 'exp026 report · Information 관측값',
        detail: 'full benchmark sandbox 실행 summary와 Information sector row. 수치는 self-assessed pre-grading snapshot이다.',
        source: `report.md@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L1-L75`,
        href: `${PERCEPTION_SOURCE}/batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md#L1-L75`,
      },
      {
        id: 'exp011-config',
        label: 'exp011 package notice',
        detail: 'subprocess에 domain package 목록과 환경 제약을 알렸지만 perception preprocessor는 구성하지 않은 출발점.',
        source: `exp011_GPT52Chat_domain_packages.yaml@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L1-L180`,
        href: `${PERCEPTION_SOURCE}/batch-runner/experiments/exp011_GPT52Chat_domain_packages.yaml#L1-L180`,
      },
      {
        id: 'exp012-config',
        label: 'exp012 조건부 audio analyzer 설정',
        detail: 'has_audio_files trigger, gpt-audio-1.5, prompt_prefix 주입 설정과 header·created_at metadata를 함께 확인한다.',
        source: `exp012_GPT52Chat_audio_multiagent.yaml@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L1-L18, L147-L165`,
        href: `${PERCEPTION_SOURCE}/batch-runner/experiments/exp012_GPT52Chat_audio_multiagent.yaml#L1-L165`,
      },
      {
        id: 'exp026-config',
        label: 'exp026 perception + Skills 설정',
        detail: 'GPT-5.4 low, 조건부 audio/video analyzer, frame budget, Skills 안내, Docker-required sandbox가 함께 들어간 구성.',
        source: `exp026_sandbox_skills_multimodal.yaml@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L50-L270`,
        href: `${PERCEPTION_SOURCE}/batch-runner/experiments/exp026_sandbox_skills_multimodal.yaml#L50-L270`,
      },
      {
        id: 'exp026-runner',
        label: 'sandbox Docker fail-loud 경계',
        detail: 'use_docker=always에서 image 또는 daemon이 없으면 backend_unavailable로 종료하고 local 실행으로 fallback하지 않는다.',
        source: `sandbox_runner.py@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L1034-L1053`,
        href: `${PERCEPTION_SOURCE}/batch-runner/core/sandbox_runner.py#L1034-L1053`,
      },
      {
        id: 'exp026-failure',
        label: 'exp026 Information media-runtime 실패',
        detail: 'report가 MoviePy type mismatch를 Information sector의 media-runtime fragility 사례로 기록한다.',
        source: `report.md@${PERCEPTION_SOURCE_SHA.slice(0, 7)} · L1548`,
        href: `${PERCEPTION_SOURCE}/batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md#L1548`,
      },
      {
        id: 'audio-history',
        label: 'audio preprocessor framework 도입',
        detail: 'audio analyzer와 preprocessor config·dispatch 경로를 도입한 pinned history.',
        source: `${AUDIO_PREPROCESSOR_COMMIT.slice(0, 7)} · 2026-03-09`,
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/commit/${AUDIO_PREPROCESSOR_COMMIT}`,
      },
      {
        id: 'sandbox-history',
        label: 'multimodal Skills sandbox 도입',
        detail: 'containerized sandbox, task-aware Skills, video perception 경로를 함께 도입한 pinned history.',
        source: `${SANDBOX_MULTIMODAL_COMMIT.slice(0, 7)} · 2026-07-07`,
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/commit/${SANDBOX_MULTIMODAL_COMMIT}`,
      },
      {
        id: 'docker-history',
        label: 'exp026 Docker-required 전환',
        detail: 'exp026 use_docker를 always로 고정해 silent local fallback을 닫은 pinned history.',
        source: `${DOCKER_ALWAYS_COMMIT.slice(0, 7)} · 2026-07-09`,
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/commit/${DOCKER_ALWAYS_COMMIT}`,
      },
      {
        id: 'perception-contract',
        label: 'perception 측정·해석 계약',
        detail: '구성 경로와 report 관측을 분리하고 analyzer 호출 수·외부 품질을 unknown으로, causal_attribution을 false로 고정한다.',
        source: 'data/notes/perception-pipeline.yaml · generated evidence contract',
        href: `${REPO}/data/notes/perception-pipeline.yaml`,
      },
    ],
  },
  {
    ...journalCatalog['what-does-success-mean'],
    dek: '처음에는 success 한 줄이 handoff-ready 업무에 가까울 것이라 기대했다. 같은 금융 분석 직군의 두 산출물을 직접 열어보니 실행, 파일, 요구 충실도, 전문가 품질은 서로 다른 질문이었다.',
    thesis: '높은 완료율이 증명한 것은 실행 경로의 완료다. 실제 업무 성공을 말하려면 열리는 파일, 충족된 요구, 외부 품질을 따로 증명해야 한다.',
    thesisCitations: ['exp026-summary', 'success-contract'],
    publishedAt: '2026-07-15',
    period: 'exp026 task review',
    readingMinutes: 11,
    benchmark: { kind: 'success' },
    readingStyle: 'reflective',
    metrics: [],
    hero: {
      kind: 'visual',
      variant: 'task-contrast',
      alt: '같은 금융 분석 직군의 workbook과 briefing을 execution, integrity, fidelity, external quality 네 층으로 비교',
      caption: '같은 직군과 같은 sandbox에서도 성공의 층은 다르게 갈렸다. Self-QA는 그 차이를 발견하는 신호이지 외부 품질 판정이 아니다.',
    },
    comparisonChart: {
      kind: 'bar',
      title: '같은 직군, 서로 다른 내부 진단',
      description: '두 task의 Self-QA를 비교한다.',
      primary: { label: 'Self-QA', unit: '/10', color: '#b45309', domain: [0, 10] },
      data: [],
      caveat: 'Self-QA는 실행 중 모델이 남긴 내부 진단이다. exp026 외부 grade는 현재 공개·checked-in 근거에 없다.',
    },
    sections: [
      {
        label: '기대',
        heading: 'success를 handoff-ready로 읽었다',
        benchmarkNarrative: 'success-expectation',
        paragraphs: [
          '높은 완료율을 보며 실제 업무 대부분이 끝났다고 기대했다.',
          '하지만 success 한 줄에는 서로 다른 네 질문이 접혀 있었다.',
        ],
        paragraphCitations: [['exp026-summary'], ['success-contract']],
      },
      {
        label: '기록',
        heading: '한 줄 status가 가린 것',
        benchmarkNarrative: 'success-status',
        paragraphs: [
          '두 task는 같은 직군이었지만 최종 상태와 내부 진단이 달랐다.',
          'aggregate의 file-generation 한 줄은 실제 task artifact와도 맞지 않았다.',
        ],
        paragraphCitations: [['workbook-row', 'briefing-row'], ['exp026-summary', 'success-contract']],
      },
      {
        label: '사례 A',
        heading: '열리는 workbook, 비어 있는 범위',
        benchmarkNarrative: 'success-workbook',
        paragraphs: [
          '요청은 특정 시점의 전체 지수와 공개 시장 데이터를 요구했다.',
          'artifact는 열렸지만 요구 범위와 출처 증거는 다른 상태였다.',
        ],
        paragraphCitations: [['workbook-prompt', 'workbook-artifact'], ['workbook-row', 'workbook-qa', 'workbook-artifact', 'success-contract']],
        callout: '파일의 존재와 parser 통과는 integrity의 증거다. 의사결정에 필요한 데이터가 완전하다는 증거는 아니다.',
        calloutCitations: ['workbook-artifact', 'success-contract'],
      },
      {
        label: '사례 B',
        heading: '열리는 briefing, 아직 남은 물음',
        benchmarkNarrative: 'success-briefing',
        paragraphs: [
          '두 형식의 파일은 열렸고 길이도 서로 맞았다.',
          '그러나 높은 Self-QA가 외부 품질과 출처 검증을 대신하지는 않는다.',
        ],
        paragraphCitations: [['briefing-prompt', 'briefing-artifacts'], ['briefing-row', 'briefing-artifacts', 'grade-inventory', 'success-contract']],
      },
      {
        label: '해석',
        heading: '두 Self-QA는 품질 순위가 아니다',
        benchmarkNarrative: 'success-interpretation',
        paragraphs: [
          '같은 직군이라는 라벨도 두 산출물의 증거 부담을 같게 만들지 않았다.',
          'Self-QA는 무엇을 더 볼지 알려줬지만 품질 판결을 끝내지 못했다.',
        ],
        paragraphCitations: [['workbook-qa', 'briefing-row', 'success-contract'], ['grade-inventory', 'success-contract']],
      },
      {
        label: '결정',
        heading: 'success를 네 층으로 공개하기',
        benchmarkNarrative: 'success-decision',
        paragraphs: [
          '이후에는 하나의 success 대신 네 층의 증거를 따로 공개한다.',
          'aggregate 완료율은 실행 지표로 남기고 handoff-ready 비율로 확장하지 않는다.',
        ],
        paragraphCitations: [['success-contract'], ['exp026-summary', 'success-contract']],
        points: [
          'Execution: 프로세스가 끝났는가',
          'Integrity: 요청한 파일이 존재하고 열리는가',
          'Fidelity: 데이터, 범위, 형식 요구를 충족했는가',
          'Quality: 전문가 관점에서 정확하고 유용한가',
        ],
      },
    ],
    evidence: [
      {
        id: 'exp026-summary',
        label: 'exp026 self-assessed 실행 summary',
        detail: 'pre-grading scope, 전체 task, success, retry와 Self-QA 집계. file-generation aggregate의 0/0/0도 같은 범위에 남아 있다.',
        source: `report.md@${SUCCESS_SOURCE_SHA.slice(0, 7)} · L1-L56`,
        href: `${SUCCESS_SOURCE}/batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md#L1-L56`,
      },
      {
        id: 'workbook-row',
        label: 'workbook task report row',
        detail: 'qa_failed, retried 여부, 선택 파일 수, Self-QA와 latency를 기록한 task row.',
        source: `report.md@${SUCCESS_SOURCE_SHA.slice(0, 7)} · L221`,
        href: `${SUCCESS_SOURCE}/batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md#L221`,
      },
      {
        id: 'workbook-qa',
        label: 'workbook Self-QA issues',
        detail: '회사 수, sector 분류와 public web data 문제를 기록한 내부 QA 진단.',
        source: `report.md@${SUCCESS_SOURCE_SHA.slice(0, 7)} · L1073-L1077`,
        href: `${SUCCESS_SOURCE}/batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md#L1073-L1077`,
      },
      {
        id: 'workbook-prompt',
        label: 'workbook 원문 task와 pinned self-report',
        detail: '전체 S&P 500, 기준일, public web data와 sortable workbook 요구를 포함한 task instruction.',
        source: `self_report.json@${SUCCESS_HF_REVISION.slice(0, 7)} · task_results[135] · L5883-L5921 · sha256 ec93ad9a…`,
        href: `${SUCCESS_HF}/blob/${SUCCESS_HF_REVISION}/self_report.json`,
      },
      {
        id: 'workbook-artifact',
        label: '선택된 S&P 500 workbook',
        detail: '직접 parser 검사에 사용한 immutable XLSX. artifact SHA-256과 구조 측정값은 success contract에 고정했다.',
        source: `sp500_pe_deep_dive.xlsx@${SUCCESS_HF_REVISION.slice(0, 7)} · sha256 fb26bf7b…`,
        href: `${SUCCESS_HF}/blob/${SUCCESS_HF_REVISION}/deliverable_files/8079e27d-b6f3-4f75-a9b5-db27903c798d/sp500_pe_deep_dive.xlsx`,
      },
      {
        id: 'briefing-row',
        label: 'briefing task report row',
        detail: 'success, retried 여부, 선택 파일 수, Self-QA와 latency를 기록한 task row.',
        source: `report.md@${SUCCESS_SOURCE_SHA.slice(0, 7)} · L223`,
        href: `${SUCCESS_SOURCE}/batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md#L223`,
      },
      {
        id: 'briefing-prompt',
        label: 'briefing 원문 task와 pinned self-report',
        detail: '약 30장, Latin America macro·technology·venture·fintech 구성과 PPTX/PDF 요구를 포함한 instruction.',
        source: `self_report.json@${SUCCESS_HF_REVISION.slice(0, 7)} · task_results[137] · L5963-L5999 · sha256 ec93ad9a…`,
        href: `${SUCCESS_HF}/blob/${SUCCESS_HF_REVISION}/self_report.json`,
      },
      {
        id: 'briefing-artifacts',
        label: '선택된 LatAm briefing 산출물',
        detail: '직접 구조 검사한 pinned PPTX, PDF와 support manifest. 두 primary artifact의 hash를 contract에 고정했다.',
        source: `deliverable_files/9e8607e7…@${SUCCESS_HF_REVISION.slice(0, 7)}`,
        href: `${SUCCESS_HF}/tree/${SUCCESS_HF_REVISION}/deliverable_files/9e8607e7-a38a-491f-ace1-e5ea7dc477cb`,
      },
      {
        id: 'grade-inventory',
        label: 'checked-in grade identity inventory',
        detail: 'dummy, exp003, exp998 grade를 exp026에 대입하지 않는다. non-dummy exp026 identity가 생기면 generator가 실패한다.',
        source: `data/grades@${SUCCESS_SOURCE_SHA.slice(0, 7)} · exp026 match 0`,
        href: `https://github.com/hyeonsangjeon/gdpval-realworks/tree/${SUCCESS_SOURCE_SHA}/data/grades`,
      },
      {
        id: 'success-contract',
        label: 'success 네 층과 artifact 측정 계약',
        detail: 'pinned revision·hash, 직접 구조 검사, report 관측과 external quality unknown을 분리한 generated evidence source.',
        source: `success-layers.yaml@${SUCCESS_CONTRACT_SHA.slice(0, 7)} · L1-L123`,
        href: `${SUCCESS_CONTRACT_SOURCE}/data/notes/success-layers.yaml#L1-L123`,
      },
    ],
  },
  {
    ...journalCatalog['why-build-a-sandbox'],
    dek: '프롬프트 튜닝으로 시작한 실험이 의존성 탐색, Skills, 멀티모달 perception을 갖춘 컨테이너 실행 환경으로 확장된 과정.',
    thesis: '실제 업무 벤치마크에서 실행 환경은 모델을 담는 그릇이 아니라 모델이 사용할 수 있는 능력의 일부다.',
    publishedAt: '2026-07-15',
    period: 'exp003 → exp026',
    readingMinutes: 8,
    metrics: [
      { value: '3가지', label: 'sandbox 핵심 추가', note: 'deps, skills, perception' },
      { value: '6/6', label: 'exp026 pilot 완료' },
      { value: '200/220', label: '최종 공개 완료' },
    ],
    hero: {
      kind: 'visual',
      variant: 'sandbox',
      alt: '불확실한 subprocess에서 dependency, skills, validation을 갖춘 Docker sandbox로 이동하는 실행 구조',
      caption: '프로세스를 한 번 실행하는 기능에서, 작업별 의존성과 도구·파일 경계를 다시 만들 수 있는 실험 장치로 이동했다.',
    },
    comparisonChart: {
      kind: 'dual',
      title: '같은 조건에서 본 실행 모드의 교환 비용',
      description: 'exp008과 exp010은 같은 모델·프롬프트·QA 조건에서 실행 모드만 달리했다. code interpreter는 더 많이 완료했지만 더 느렸다.',
      primary: { label: 'Completion', unit: '%', color: '#059669', domain: [0, 100] },
      secondary: { label: 'Avg latency', unit: 's', color: '#2563eb', domain: [0, 45] },
      data: [
        { label: 'exp008 · subprocess', primary: 97.7, secondary: 29.4 },
        { label: 'exp010 · code interpreter', primary: 99.5, secondary: 39.1 },
      ],
      caveat: '완료율과 평균 지연시간만 표시한다. 외부 산출물 품질을 뜻하지 않는다.',
    },
    sections: [
      {
        heading: '출발: code interpreter 밖으로 나온 이유',
        paragraphs: [
          '초기 실험은 관리형 code interpreter와 로컬 subprocess를 오갔다. subprocess는 실행 코드와 패키지를 직접 통제하고 실패를 재현하기 쉬웠다. 동시에 그 자유는 dependency, 파일 경로, timeout, 프로세스 cleanup을 모두 runner가 책임져야 한다는 뜻이었다.',
          'exp006부터 exp009까지 토큰, 프롬프트, timeout, resume을 조정하며 완료율을 끌어올렸다. exp008은 97.7%에 도달했지만, 프롬프트만으로 실행 환경의 차이를 없앨 수는 없었다.',
        ],
      },
      {
        heading: '비교: subprocess와 관리형 sandbox',
        paragraphs: [
          'exp008과 exp010은 같은 모델, 프롬프트, QA 조건에서 실행 모드를 비교했다. subprocess는 97.7%, Azure code interpreter는 99.5% 완료율을 기록했다. 후자는 더 안정적이었지만 평균 지연은 29.4초에서 39.1초로 늘었다.',
          '이 비교는 “어느 쪽이 항상 우월한가”보다 무엇을 직접 소유할 것인가를 묻게 했다. 관리형 환경의 안정성과 로컬 환경의 관찰 가능성 사이에서, 필요한 격리를 직접 만드는 방향이 생겼다.',
        ],
      },
      {
        heading: '누적된 요구: 패키지, 감각, 작업 지침',
        paragraphs: [
          'exp011은 도메인 패키지와 모델의 환경 인지를, exp012는 오디오 전처리를 시험했다. exp025의 무결성 수정은 성공 상태를 더 엄격하게 만들었다. 각 실험은 subprocess의 한계를 하나씩 드러냈다.',
          'exp026의 공개 self-report는 실행 모드를 sandbox로 기록한다. 이 실행은 작업별 dependency discovery, 문서·이미지·데이터·오디오·비디오 Agent Skills, 그리고 audio/video perception을 한 경로에 묶었다.',
        ],
      },
      {
        heading: '결과: 격리가 해결한 것과 해결하지 못한 것',
        paragraphs: [
          '6개 pilot은 모두 완료됐고 full run의 공개 결과는 200/220이었다. sandbox는 작업별 환경 격리와 도구 공급을 개선했지만 105개 작업이 재시도를 거쳤다. 실행 오류 6개도 남았다.',
          '실패는 더 구체적으로 보였다. 생성 코드의 syntax error, MoviePy type mismatch, 문서 라이브러리 속성 오류, rigid schema assumption이 각각 분리됐다. 반면 public web data와 최신 정보가 필요한 작업은 sandbox 안의 도구만으로 해결되지 않았다.',
        ],
      },
      {
        heading: '결정: sandbox를 제품이 아니라 실험 장치로 보기',
        paragraphs: [
          'sandbox의 목적은 성공률 한 숫자를 높이는 데 있지 않다. 작업에 제공된 패키지, Skills, 네트워크, perception과 파일 경계를 명시해 같은 조건을 다시 만들 수 있게 하는 데 있다.',
          '다음 단계는 모든 작업에 같은 도구를 더 넣는 것이 아니다. code, media, document, live-data 작업을 사전에 분류하고 각 경로에 맞는 validation contract를 두는 것이다.',
        ],
      },
    ],
    evidence: [
      {
        label: 'exp008 리포트',
        detail: 'subprocess resume2 기준선',
        href: `${REPO}/batch-runner/results/exp008_GPT52Chat_resume2_elicit_v2/report/report.md`,
      },
      {
        label: 'exp010 리포트',
        detail: '동일 조건 code interpreter 비교',
        href: `${REPO}/batch-runner/results/exp010_GPT52Chat_resume2_elicit_v2/report/report.md`,
      },
      {
        label: 'exp026 공개 self-report',
        detail: 'sandbox 실행 모드, Skills·multimodal 조건, full-run 결과',
        href: `${HF_EXP026}/blob/main/self_report.json`,
      },
    ],
  },
]

export const experimentGroups: ExperimentGroup[] = [
  {
    id: 'prompt-strategy',
    question: '복잡한 프롬프트는 기본 프롬프트보다 나았나?',
    experiments: ['exp001', 'exp002', 'exp003', 'exp004', 'exp005'],
    finding: 'subprocess 비교에서는 baseline 완료율이 Elicit 계열보다 높았다.',
    caveat: 'code interpreter와 subprocess 결과를 하나의 직접 비교로 섞지 않는다.',
    articleSlug: 'when-more-prompt-is-less',
    state: 'finding',
  },
  {
    id: 'subprocess-reliability',
    question: '토큰, 프롬프트, timeout과 resume으로 subprocess를 안정화할 수 있었나?',
    experiments: ['exp006', 'exp007', 'exp008', 'exp009'],
    finding: '순차 튜닝 중 exp008이 97.7%로 가장 높은 완료율을 기록했다.',
    caveat: '여러 변수가 순차적으로 바뀌어 단일 변수 효과로 해석할 수 없다.',
    state: 'finding',
  },
  {
    id: 'execution-mode',
    question: '같은 조건에서 subprocess와 code interpreter 중 무엇이 안정적이었나?',
    experiments: ['exp008', 'exp010'],
    finding: 'code interpreter는 완료율이 1.8%p 높았고 평균 실행은 약 9.7초 느렸다.',
    caveat: '완료율은 산출물의 외부 품질 점수가 아니다.',
    articleSlug: 'why-build-a-sandbox',
    state: 'finding',
  },
  {
    id: 'domain-perception',
    question: '도메인 패키지와 오디오 전처리는 멀티모달 업무에 도움이 됐나?',
    experiments: ['exp011', 'exp012', 'exp026'],
    finding: '입력 접근성은 개선됐지만 media runtime과 요구 충실도가 다음 병목으로 드러났다.',
    caveat: 'exp012는 subset 실행이라 full benchmark와 직접 비교할 수 없다.',
    articleSlug: 'from-audio-to-multimodal-sandbox',
    state: 'caution',
  },
  {
    id: 'gpt54-reasoning',
    question: 'GPT-5.4 reasoning effort의 품질·비용 최적점은 어디였나?',
    experiments: ['exp013', 'exp014', 'exp015', 'exp016'],
    finding: '현재 checkout에는 high와 medium의 완전한 로컬 리포트만 있어 4-way 결론을 내릴 수 없다.',
    caveat: '외부 채점과 누락 실행이 보완되기 전까지 열린 질문이다.',
    state: 'open',
  },
  {
    id: 'gpt52-reasoning',
    question: 'GPT-5.2 reasoning effort가 높을수록 완료율도 높았나?',
    experiments: ['exp017', 'exp018', 'exp019', 'exp020'],
    finding: 'medium이 97.3%로 가장 높았고 high는 94.5%였다. 단조 관계는 없었다.',
    caveat: '운영 완료율의 순위이며 외부 품질 최적점은 아직 아니다.',
    state: 'finding',
  },
  {
    id: 'mini-reasoning',
    question: 'Mini 모델은 더 높은 reasoning으로 용량 한계를 보완했나?',
    experiments: ['exp021', 'exp022', 'exp023', 'exp024'],
    finding: 'high와 null이 모두 94.1%로, 완료율에서 reasoning의 단조 효과가 없었다.',
    caveat: '비용과 외부 품질을 함께 봐야 최적점을 판단할 수 있다.',
    state: 'open',
  },
  {
    id: 'integrity-boundary',
    question: '성공률 하락은 모델 회귀였나, 더 정직해진 파이프라인이었나?',
    experiments: ['exp013', 'exp025'],
    finding: '두 실행의 관측 완료율과 success를 기록하는 규칙이 함께 달라졌다.',
    caveat: '관측 차이는 사실이지만 수정의 순수 효과로 배분할 실행 정체성은 없다.',
    articleSlug: 'honest-pipeline-lower-score',
    state: 'caution',
  },
  {
    id: 'sandbox-transition',
    question: '왜 subprocess만으로는 부족했고 sandbox가 필요했나?',
    experiments: ['exp025', 'exp026'],
    finding: '격리, dependency discovery, Skills와 perception을 하나의 재현 가능한 실행 경로로 묶었다.',
    caveat: '높은 재시도와 외부 채점 대기는 여전히 남아 있다.',
    articleSlug: 'why-build-a-sandbox',
    state: 'finding',
  },
]

export const timelineEvents: TimelineEvent[] = [
  {
    date: '2026-02-25',
    title: '관리형 실행에서 subprocess 실험으로 이동',
    description: 'baseline과 Elicit 전략을 직접 실행 가능한 runner에서 다시 비교하기 시작했다.',
    experiments: ['exp003', 'exp004'],
    articleSlugs: ['when-more-prompt-is-less', 'why-build-a-sandbox'],
    kind: 'decision',
  },
  {
    date: '2026-03-05',
    title: '동일 조건에서 실행 모드를 분리 비교',
    description: 'exp008과 exp010으로 subprocess의 속도와 code interpreter의 완료 안정성을 비교했다.',
    experiments: ['exp008', 'exp010'],
    articleSlugs: ['why-build-a-sandbox', '360-minute-experiment'],
    kind: 'experiment',
  },
  {
    date: '2026-03-24',
    title: '세 모델 계열의 reasoning ablation 설계',
    description: 'GPT-5.4, GPT-5.2, GPT-5.4-mini에서 high부터 null까지 reasoning effort를 비교했다.',
    experiments: ['exp013—exp024'],
    articleSlugs: [],
    kind: 'experiment',
  },
  {
    date: '2026-05-17',
    title: 'silent corruption 세 건을 확인',
    description: '실행 파일 힌트와 qa_failed 상태 등 로그 없이 결과 의미를 바꾸던 불변식 오류를 발견했다.',
    experiments: ['exp013', 'exp025'],
    articleSlugs: ['honest-pipeline-lower-score'],
    kind: 'incident',
  },
  {
    date: '2026-05-18',
    title: '장시간 resume가 약 330분에 종료',
    description: '강제 종료 전에 checkpoint를 넘기기 위해 watchdog, step ceiling과 relay 구조를 도입했다.',
    experiments: ['exp025'],
    articleSlugs: ['360-minute-experiment'],
    kind: 'incident',
  },
  {
    date: '2026-05-20',
    title: '수정 후 GPT-5.4 high 기준선 실행',
    description: 'PR #38 이후의 상태 판정 세대에서 exp025 report snapshot을 남겼다.',
    experiments: ['exp025'],
    articleSlugs: ['honest-pipeline-lower-score'],
    kind: 'experiment',
  },
  {
    date: '2026-07-10',
    title: 'sandbox, Skills, multimodal full run 시작',
    description: 'dependency discovery와 audio/video perception을 묶은 exp026의 220개 작업 실행을 시작했다.',
    experiments: ['exp026'],
    articleSlugs: ['why-build-a-sandbox', 'from-audio-to-multimodal-sandbox'],
    kind: 'experiment',
  },
  {
    date: '2026-07-13',
    title: '두 번째 resume round의 회복 한계를 기록',
    description: '첫 round는 78개를 모두 회복했지만, 두 번째 round는 27개 중 7개를 회복하고 20개를 남겼다.',
    experiments: ['exp026'],
    articleSlugs: ['360-minute-experiment'],
    kind: 'incident',
  },
  {
    date: '2026-07-13 18:03 UTC',
    title: 'exp026 최종 self-report 생성',
    description: '복구를 이어간 결과 200/220 success, 6개 명시적 실행 오류, 평균 Self-QA 6.24를 기록했다.',
    experiments: ['exp026'],
    articleSlugs: ['what-does-success-mean', 'why-build-a-sandbox'],
    kind: 'experiment',
  },
]

export function getJournalArticle(slug: string | undefined) {
  return journalArticles.find((article) => article.slug === slug)
}

export function getJournalArticlesForExperiment(experimentId: string | undefined) {
  if (!experimentId) return []
  return journalArticles.filter((article) => article.relatedExperiments.includes(experimentId))
}