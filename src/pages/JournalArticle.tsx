import { useEffect } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Clock3,
  ExternalLink,
  FlaskConical,
  Moon,
  Sun,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTheme } from '../contexts/ThemeContext'
import NoteComparisonChart from '../components/notes/NoteComparisonChart'
import NoteHeroVisual from '../components/notes/NoteHeroVisual'
import { useReports } from '../hooks/useReports'
import { useRuntimeNote } from '../hooks/useRuntimeNote'
import { useIntegrityNote } from '../hooks/useIntegrityNote'
import { usePerceptionNote } from '../hooks/usePerceptionNote'
import { useSuccessNote } from '../hooks/useSuccessNote'
import {
  selectPromptComplexityBenchmark,
  type PromptComplexityBenchmarkRow,
  type PromptComplexityBenchmarkSelection,
} from '../lib/promptComplexityBenchmark'
import {
  selectRuntimeNoteBenchmark,
  type RuntimeNoteBenchmarkSelection,
} from '../lib/runtimeNoteBenchmark'
import {
  selectIntegrityNoteBenchmark,
  type IntegrityNoteSelection,
} from '../lib/integrityNoteBenchmark'
import {
  selectPerceptionBenchmark,
  type PerceptionSelection,
} from '../lib/perceptionNoteBenchmark'
import {
  selectSuccessNoteBenchmark,
  type SuccessBenchmarkSelection,
} from '../lib/successNoteBenchmark'
import {
  getJournalArticle,
  journalArticles,
  lensLabels,
  type JournalArticle as JournalArticleData,
  type JournalEvidence,
  type JournalLens,
} from '../data/journal'
import { getExperimentHref, isExternalExperimentHref } from '../data/journalLinks'
import { validateJournalCitations } from '../lib/journalCitations'

const lensStyles: Record<JournalLens, string> = {
  experiment: 'text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
  engineering: 'text-blue-700 dark:text-blue-300 bg-blue-500/10 border-blue-500/20',
  task: 'text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-500/20',
  domain: 'text-rose-700 dark:text-rose-300 bg-rose-500/10 border-rose-500/20',
}

type ReadyPromptBenchmark = Extract<PromptComplexityBenchmarkSelection, { status: 'ready' }>
type ReadyRuntimeBenchmark = Extract<RuntimeNoteBenchmarkSelection, { status: 'ready' }>
type ReadyIntegrityBenchmark = Extract<IntegrityNoteSelection, { status: 'ready' }>
type ReadyPerceptionBenchmark = Extract<PerceptionSelection, { status: 'ready' }>
type ReadySuccessBenchmark = Extract<SuccessBenchmarkSelection, { status: 'ready' }>

const formatSigned = (value: number, suffix: string) => `${value > 0 ? '+' : ''}${value.toFixed(1)}${suffix}`
const citationAnchorId = (prefix: string, evidenceId: string) => `citation-${prefix}-${evidenceId}`
const evidenceAnchorId = (evidenceId: string) => `evidence-${evidenceId}`

function InlineCitations({
  evidenceIds,
  prefix,
  evidenceLookup,
}: {
  evidenceIds?: string[]
  prefix: string
  evidenceLookup: Map<string, { source: JournalEvidence; index: number }>
}) {
  if (!evidenceIds?.length) return null
  return (
    <sup className="ml-1 inline-flex gap-0.5 align-super font-mono text-[9px] leading-none">
      {evidenceIds.map((evidenceId) => {
        const evidence = evidenceLookup.get(evidenceId)
        if (!evidence) return null
        return (
          <span
            key={evidenceId}
            id={citationAnchorId(prefix, evidenceId)}
            className="inline-block scroll-mt-24"
          >
            <a
              href={`#${evidenceAnchorId(evidenceId)}`}
              data-citation-id={evidenceId}
              aria-label={`근거 ${evidence.index + 1}: ${evidence.source.label}`}
              title={evidence.source.label}
              className="text-emerald-700 dark:text-emerald-400 underline decoration-emerald-500/40 underline-offset-2 hover:text-emerald-600 dark:hover:text-emerald-300"
            >
              [{evidence.index + 1}]
            </a>
          </span>
        )
      })}
    </sup>
  )
}

function resolvePromptComplexityArticle(article: JournalArticleData, benchmark: ReadyPromptBenchmark) {
  const baseline = benchmark.rows[0]
  const headless = benchmark.rows[benchmark.rows.length - 1]
  const completedDifference = baseline.successCount - headless.successCount
  const qaDifference = Math.abs(baseline.avgQaScore - headless.avgQaScore)

  return {
    metrics: [
      { value: `${baseline.successRatePct.toFixed(1)}%`, label: `${baseline.condition} 완료율` },
      { value: formatSigned(benchmark.completionDeltaPctPoints, '%p'), label: `${baseline.shortId} 대비 ${headless.shortId}`, note: 'success_count / total_tasks 기준' },
      { value: `${baseline.avgQaScore.toFixed(2)} ≈ ${headless.avgQaScore.toFixed(2)}`, label: `${baseline.shortId} ↔ ${headless.shortId} Self-QA` },
    ],
    hero: article.hero ? {
      ...article.hero,
      caption: `report summary 기준 완료 작업은 ${benchmark.rows.map((row) => `${row.shortId} ${row.successCount}/${row.totalTasks}`).join(', ')}였다. Self-QA는 ${benchmark.rows.map((row) => row.avgQaScore.toFixed(2)).join(' → ')}로 움직였다.`,
    } : undefined,
    chart: article.comparisonChart ? {
      ...article.comparisonChart,
      data: benchmark.rows.map((row) => ({
        label: `${row.shortId} ${row.condition}`,
        primary: row.successRatePct,
        secondary: row.avgQaScore,
      })),
    } : undefined,
    sections: article.sections.map((section) => section.benchmarkNarrative === 'prompt-complexity-results' ? {
      ...section,
      paragraphs: [
        `완료율은 ${benchmark.rows.map((row) => `${row.condition} ${row.shortId} ${row.successCount}/${row.totalTasks}, ${row.successRatePct.toFixed(1)}%`).join(' · ')}였다. 관찰된 완료 수는 순서대로 ${benchmark.rows.map((row) => `${row.successCount}개`).join(', ')}였다.`,
        `Self-QA는 ${benchmark.rows.map((row) => row.avgQaScore.toFixed(2)).join(' → ')}로 움직였다. ${headless.shortId}는 ${baseline.shortId}보다 ${completedDifference}개를 덜 완료했지만, 점수가 남은 결과의 평균 자기평가는 ${qaDifference.toFixed(2)}점 차이였다. 완료율만 보면 악화였고 Self-QA만 보면 거의 회복이었다.`,
      ],
    } : section),
  }
}

function resolveRuntimeArticle(article: JournalArticleData, benchmark: ReadyRuntimeBenchmark) {
  const firstRound = benchmark.exp026.recoveryRounds[0]
  const secondRound = benchmark.exp026.recoveryRounds[1]
  const policy = benchmark.currentPolicy
  const incident = benchmark.incident

  return {
    metrics: [
      { value: String(benchmark.exp026.totalTasks), label: '서로 다른 실제 업무', note: undefined },
      { value: `${policy.job_timeout_minutes}분`, label: 'workflow job cap', note: undefined },
      { value: `약 ${incident.approx_minute}분`, label: `${incident.policy.step_timeout_minutes}분 step hard stop`, note: undefined },
    ],
    hero: article.hero ? {
      ...article.hero,
      alt: `사건 당시 ${incident.policy.step_timeout_minutes}분 step hard timeout과 수정 후 ${policy.watchdog_minutes}분 watchdog, ${policy.step_timeout_minutes}분 step ceiling, ${policy.job_timeout_minutes}분 job cap 비교`,
      caption: `사건 당시 ${incident.policy.step_timeout_minutes}분 step hard stop에서 ${incident.event}이 발생했다. 수정 후 condition_a 경로는 ${policy.watchdog_minutes}분 watchdog, ${policy.step_timeout_minutes}분 step ceiling, ${policy.job_timeout_minutes}분 job cap으로 분리됐다.`,
    } : undefined,
    chart: article.comparisonChart ? {
      ...article.comparisonChart,
      description: `첫 round는 ${firstRound.attempted}개 중 ${firstRound.recovered}개를 회복했고, 두 번째 round는 ${secondRound.attempted}개 중 ${secondRound.recovered}개를 회복했다.`,
      data: benchmark.exp026.recoveryRounds.map((round) => ({
        label: `Round ${round.round}`,
        primary: round.recovered,
        secondary: round.stillFailed,
      })),
    } : undefined,
    sections: article.sections.map((section) => {
      if (section.benchmarkNarrative === 'runtime-incident') {
        return {
          ...section,
          paragraphs: [
            `GDPVal의 ${benchmark.exp026.totalTasks}개 작업은 짧은 문서 작성부터 스프레드시트 계산, 프레젠테이션, 코드와 미디어 처리까지 섞여 있다. 한 작업의 평균 시간만 보고 전체 실행 시간을 예상하면 긴 꼬리 작업이 사라진다.`,
            `${incident.experiment_id}의 resume round는 당시 ${incident.policy.step_timeout_minutes}분 step hard timeout에 닿아 약 ${incident.approx_minute}분 지점에서 ${incident.event}로 끝났다. job cap까지 남은 시간이 있었지만, 프로세스가 강제 종료되어 마지막 상태를 다음 실행으로 넘기지 못했다.`,
          ],
          callout: `여기서 ${policy.job_timeout_minutes}분은 GitHub Actions 전체에 보편적으로 적용되는 규칙이라는 뜻이 아니라, 이 기록의 workflow와 runner에서 작동한 job cap을 가리킨다.`,
        }
      }
      if (section.benchmarkNarrative === 'runtime-policy') {
        return {
          ...section,
          paragraphs: [
            `중단 사건 뒤 Resume Round에도 watchdog이 들어갔고 step ceiling은 ${incident.fix.step_timeout_before_minutes}분에서 ${incident.fix.step_timeout_after_minutes}분으로 넓어졌다. 현재 workflow의 condition_a 경로에서 watchdog은 기본 ${policy.watchdog_minutes}분에 checkpoint를 남기고 종료하며, workflow step은 relay handoff를 위한 ${policy.relay_handoff_margin_minutes}분의 여유를 더해 ${policy.step_timeout_minutes}분에 닫힌다. exp008과 exp010은 이 수정 전에 실행됐으므로 현재 정책의 결과로 읽지 않는다.`,
            '이 구조는 작업 실행과 workflow 수명을 분리했다. 한 번의 runner가 전체 실험을 소유하지 않고, 여러 runner가 동일한 실험 상태를 이어받을 수 있게 됐다.',
          ],
        }
      }
      if (section.benchmarkNarrative === 'runtime-results') {
        return {
          ...section,
          paragraphs: [
            `relay는 장시간 실행을 이어갈 수 있게 했지만 모든 실패를 해결하지는 않았다. ${benchmark.exp026.shortId} report에서 첫 resume round는 시도한 ${firstRound.attempted}개 작업 중 ${firstRound.recovered}개를 회복했고 ${firstRound.stillFailed}개를 남겼다. 두 번째 round는 ${secondRound.attempted}개 중 ${secondRound.recovered}개를 회복하고 ${secondRound.stillFailed}개를 남겼다.`,
            `최종 report는 ${benchmark.exp026.totalTasks}개 중 ${benchmark.exp026.successCount}개 success, ${benchmark.exp026.errorCount}개 명시적 실행 오류, ${benchmark.exp026.retriedCount}개 재시도를 기록한다. 복구 가능성은 높아졌지만 반복 시도가 남은 작업을 균일하게 해결하지는 못했다.`,
          ],
        }
      }
      return section
    }),
  }
}

function resolveIntegrityArticle(article: JournalArticleData, benchmark: ReadyIntegrityBenchmark) {
  const { before, after, observedGapPctPoints, successDifference } = benchmark
  const missingIdentityLabels = benchmark.interpretation.missing_execution_identities.join(', ')

  return {
    metrics: [
      { value: `${before.successRatePct.toFixed(1)}%`, label: `${before.shortId} 관측 완료율`, note: undefined },
      { value: `${after.successRatePct.toFixed(1)}%`, label: `${after.shortId} 관측 완료율`, note: undefined },
      { value: `${observedGapPctPoints.toFixed(1)}%p`, label: '관측 차이', note: '인과 효과 추정치 아님' },
    ],
    hero: article.hero ? {
      ...article.hero,
      alt: `${before.shortId} ${before.successRatePct.toFixed(1)}퍼센트와 ${after.shortId} ${after.successRatePct.toFixed(1)}퍼센트의 관측 차이 및 success 기록 규칙 변화`,
      caption: `${before.shortId}는 ${before.successCount}/${before.totalTasks}, ${after.shortId}는 ${after.successCount}/${after.totalTasks} success를 기록했다. 관측 차이는 ${observedGapPctPoints.toFixed(1)}%p이며 수정의 인과 효과 추정치가 아니다.`,
    } : undefined,
    chart: article.comparisonChart ? {
      ...article.comparisonChart,
      description: `${before.shortId}와 ${after.shortId} report snapshot의 관측 완료율이다. 두 실행 사이에서 success와 retry의 기록 규칙도 바뀌었다.`,
      data: benchmark.rows.map((row) => ({
        label: `${row.shortId} · ${row.date}`,
        primary: row.successRatePct,
      })),
    } : undefined,
    sections: article.sections.map((section) => {
      if (section.benchmarkNarrative === 'integrity-observation') {
        return {
          ...section,
          paragraphs: [
            `${before.shortId} report는 ${before.successCount}/${before.totalTasks}, ${before.successRatePct.toFixed(1)}% 완료율을 기록했다. 같은 checked-in condition과 execution 설정의 ${after.shortId} report는 ${after.successCount}/${after.totalTasks}, ${after.successRatePct.toFixed(1)}%였다. 두 snapshot의 관측 차이는 ${observedGapPctPoints.toFixed(1)}%p, success 수 차이는 ${successDifference}개다.`,
            `함께 달라진 것은 숫자만이 아니다. ${benchmark.history.applied_at}의 PR #38 전후로 _AVAILABLE_FILES가 실제 실행 파일에 반영되는 방식과 determined QA failure가 기록되는 상태가 바뀌었다. 이 글은 관측값과 판정 규칙을 함께 보되, 하나를 다른 하나의 원인으로 단정하지 않는다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'integrity-available-files') {
        return {
          ...section,
          paragraphs: [
            '수정 전 subprocess runner는 reference 파일 목록을 `_AVAILABLE_FILES` 헤더로 조합했지만, 그보다 먼저 원본 `solution.py`를 디스크에 썼다. 메모리의 문자열은 바뀌어도 subprocess가 읽는 파일은 다시 저장되지 않았다.',
            '수정 후에는 헤더가 붙은 코드를 실행 전에 다시 기록했다. 이 fix는 약속한 실행 환경과 실제 실행 파일을 일치시킨다. 다만 그 변화가 각 task의 성공률을 어느 방향으로 얼마나 움직였는지는 paired 결과 없이 배분할 수 없다.',
          ],
        }
      }
      if (section.benchmarkNarrative === 'integrity-qa-failed') {
        return {
          ...section,
          paragraphs: [
            '수정 전에도 `qa_failed`는 재시도 가능한 상태 목록에 있었다. 그러나 Self-QA 점수가 기준 미달인 채 재시도를 소진했을 때 `best_result`의 상태를 바꾸지 않아 determined QA failure가 success로 남을 수 있었다.',
            `수정 후에는 그 경우를 qa_failed로 기록해 resume 대상과 summary에 드러냈다. 단, QA API나 parse가 실패해 판정 자체가 undetermined인 경우는 의도적으로 success에 남는다. report summary만 보면 ${before.shortId}의 success·명시적 error 이외 잔여 상태는 ${before.residualCount}개, ${after.shortId}는 ${after.residualCount}개지만, 이 잔여 수를 모두 qa_failed라고 부르지는 않는다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'integrity-comparison') {
        return {
          ...section,
          paragraphs: [
            `두 experiment YAML의 data filter, condition_a, execution projection은 같다. 모델은 ${before.model}, mode는 ${before.executionMode}, task 수는 ${before.totalTasks}개다. 그래서 두 관측값을 같은 계열의 서로 다른 측정 세대로 놓을 수는 있다.`,
            `그러나 ${missingIdentityLabels}가 report에 남아 있지 않다. 실행 날짜와 환경도 다르고 seed는 고정되지 않았다. 따라서 ${observedGapPctPoints.toFixed(1)}%p를 모델 회귀나 PR #38의 순수 효과라고 부르는 것은 증거 범위를 넘는다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'integrity-decision') {
        return {
          ...section,
          paragraphs: [
            '이후 비교에서는 모델·프롬프트·reasoning뿐 아니라 runner와 상태 판정 세대도 조건으로 기록한다. success의 정의가 바뀐 경계에는 pinned code와 적용일을 함께 남긴다.',
            '과거 결과를 지우지 않는다. 대신 어떤 규칙 아래 생성됐는지를 표시하고, 재현에 필요한 실행 정체성이 없으면 인과 문장을 멈춘다. 낮은 수치를 좋다고 부르는 대신, 무엇을 측정했는지 더 정확히 말하는 쪽을 택한다.',
          ],
        }
      }
      return section
    }),
  }
}

function resolvePerceptionArticle(article: JournalArticleData, benchmark: ReadyPerceptionBenchmark) {
  const { exp011, exp012, exp026, architecture, interpretation } = benchmark
  const exp012Audio = architecture.exp012.preprocessors[0]
  const exp026Video = architecture.exp026.preprocessors[1]
  const formatLatency = (milliseconds: number) => `${(milliseconds / 1000).toFixed(1)}초`
  const pathSequence = benchmark.rows.map((row) => row.perceptionPaths.length).join(' → ')
  const successSequence = benchmark.rows.map((row) => row.information.success).join(' → ')

  return {
    metrics: [
      { value: `${successSequence} / ${exp011.information.total}`, label: 'Information success', note: '세 report sector row' },
      { value: pathSequence, label: 'configured perception paths', note: '호출 횟수 아님' },
      { value: formatLatency(exp026.information.avgLatencyMs), label: `${exp026.shortId} Information 평균 지연`, note: 'report snapshot' },
    ],
    hero: article.hero ? {
      ...article.hero,
      alt: `${exp011.shortId} perception path ${exp011.perceptionPaths.length}개, ${exp012.shortId} ${exp012.perceptionPaths.join(' ')} path, ${exp026.shortId} ${exp026.perceptionPaths.join('와 ')} path 및 sandbox 구성 비교`,
      caption: `구성된 perception path는 ${pathSequence}개로 늘었다. 같은 세 report의 Information success는 ${successSequence}/${exp011.information.total}였으며, 두 흐름 사이의 인과 관계를 뜻하지 않는다.`,
    } : undefined,
    chart: article.comparisonChart ? {
      ...article.comparisonChart,
      title: `Information ${exp011.information.total}개 작업의 관측 결과`,
      description: benchmark.rows.map((row) => `${row.shortId} ${row.information.success}/${row.information.total} · Self-QA ${row.information.avgQaScore.toFixed(2)}`).join(' / '),
      data: benchmark.rows.map((row) => ({
        label: `${row.shortId} · ${row.perceptionPaths.length ? row.perceptionPaths.join('+') : 'packages'}`,
        primary: row.information.successRatePct,
        secondary: row.information.avgQaScore,
      })),
    } : undefined,
    sections: article.sections.map((section) => {
      if (section.benchmarkNarrative === 'perception-baseline') {
        return {
          ...section,
          paragraphs: [
            `${exp011.shortId}은 ${exp011.mode} 환경에 domain package 안내를 더했지만 perception preprocessor는 구성하지 않았다. reference file을 읽을 도구와 그 내용을 별도 모델이 듣거나 보는 경로는 같은 기능이 아니었다.`,
            `그 report의 Information row는 ${exp011.information.success}/${exp011.information.total} success와 Self-QA ${exp011.information.avgQaScore.toFixed(2)}를 기록한다. 이 수치는 실행 결과이지, 개별 media task에서 무엇을 지각했는지를 기록한 측정값은 아니다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'perception-audio') {
        return {
          ...section,
          paragraphs: [
            `${exp012.shortId}는 ${exp012Audio.deployment} audio analyzer를 ${exp012Audio.trigger}일 때 실행하고 task instruction을 함께 넘긴 뒤 결과를 ${exp012Audio.inject_as}로 주입하도록 구성했다. source에는 analyzer의 실제 task별 호출 횟수가 없으므로, 확인할 수 있는 것은 이 조건부 경로의 존재까지다.`,
            `${exp012.date} report는 Information ${exp012.information.success}/${exp012.information.total}, Self-QA ${exp012.information.avgQaScore.toFixed(2)}를 기록한다. 하지만 checked-in YAML header는 ${architecture.exp012.header_declared_audio_heavy_tasks}개 audio-heavy task를 말하고 created_at은 ${architecture.exp012.config_created_at}이다. 어느 쪽을 실행 identity로 보정하지 않고 provenance 충돌로 남긴다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'perception-sandbox') {
        return {
          ...section,
          paragraphs: [
            `${exp026.shortId}는 ${exp026.perceptionPaths.join('와 ')} analyzer를 함께 구성했다. video path는 영상마다 ${exp026Video.frames_per_video}개 frame, 전체 최대 ${exp026Video.max_total_frames}개를 보며, task당 최대 ${architecture.exp026.max_skills}개의 Skills를 고르는 ${exp026.mode} 경로와 결합됐다. perception뿐 아니라 model·reasoning·runner·Skills가 함께 바뀐 하나의 architecture bundle이다.`,
            `이 실행은 use_docker=${architecture.exp026.use_docker}를 요구한다. image나 daemon이 없으면 backend_unavailable로 실패하고 local subprocess로 물러서지 않는다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'perception-results') {
        return {
          ...section,
          heading: `${benchmark.rows.map((row) => `${row.information.success}/${row.information.total}`).join(' · ')}가 말하는 것`,
          paragraphs: [
            `Information ${exp011.information.total}개 row의 success는 ${exp011.shortId} ${exp011.information.success}, ${exp012.shortId} ${exp012.information.success}, ${exp026.shortId} ${exp026.information.success}였다. 완료율은 ${benchmark.rows.map((row) => `${row.information.successRatePct.toFixed(1)}%`).join(' → ')}, Self-QA는 ${benchmark.rows.map((row) => row.information.avgQaScore.toFixed(2)).join(' → ')}였다.`,
            `평균 지연도 ${benchmark.rows.map((row) => `${row.shortId} ${formatLatency(row.information.avgLatencyMs)}`).join(', ')}로 같지 않았다. ${exp012.shortId}는 Information-only 실행이고 나머지는 full benchmark의 sector slice이며 모델과 runner도 달라, 이 순서를 perception의 효과 크기로 해석할 수 없다.`,
          ],
          callout: `같은 ${exp011.information.total}개 sector row라는 사실만으로 paired experiment가 되지는 않는다. ${exp012.shortId}는 Information-only 실행이고 ${exp011.shortId}·${exp026.shortId}은 full benchmark의 sector slice다.`,
        }
      }
      if (section.benchmarkNarrative === 'perception-failure') {
        return {
          ...section,
          paragraphs: [
            `${exp026.shortId}의 Information 평균 지연은 ${formatLatency(exp026.information.avgLatencyMs)}였고 ${exp026.information.success}/${exp026.information.total}개가 success였다. 같은 report는 한 Information task의 MoviePy type mismatch를 media-runtime fragility 사례로 기록한다.`,
            `audio와 video path가 구성됐다는 사실은 media toolchain이나 산출물 format이 검증됐다는 뜻이 아니다. 더구나 report는 self-assessed pre-grading이며 외부 품질은 아직 이 evidence contract의 관측 범위 밖이다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'perception-decision') {
        return {
          ...section,
          paragraphs: [
            `다음 contract는 configured path 수와 실제 invocation을 분리한다. task별 trigger 판정, analyzer 호출·성공·실패, 주입된 artifact와 downstream 사용 여부를 남겨야 ${interpretation.invocation_count_known ? '이미 알려진 호출' : '현재 unknown인 호출'}을 측정값으로 바꿀 수 있다.`,
            `또한 perception, media runtime, deliverable format, external grade를 각각 기록한다. ${interpretation.missing_execution_identities.join(', ')}가 없는 지금은 architecture history를 재현할 수 있어도 관측 차이를 그 변경의 인과 효과로 배분하지 않는다.`,
          ],
        }
      }
      return section
    }),
  }
}

function resolveSuccessArticle(article: JournalArticleData, benchmark: ReadySuccessBenchmark) {
  const { report, workbook, briefing, interpretation } = benchmark
  const workbookCoveragePct = (workbook.inspection.company_rows / workbook.request.expected_company_count) * 100

  return {
    metrics: [
      { value: `${report.successCount}/${report.totalTasks}`, label: 'report success 상태', note: `${report.successRatePct.toFixed(1)}% · success 규칙 통과율` },
      { value: `${workbook.inspection.company_rows}/${workbook.request.expected_company_count}`, label: '워크북에 담긴 회사', note: `${workbookCoveragePct.toFixed(1)}% · 파일 직접 확인` },
      { value: interpretation.external_grade_available ? '있음' : '미확인', label: 'exp026 외부 품질 평가', note: '모델의 자체 점검과 분리' },
    ],
    hero: article.hero ? {
      ...article.hero,
      alt: `같은 금융 분석 직군의 workbook은 ${workbook.observed.status}, Self-QA ${workbook.observed.self_qa_score}, ${workbook.inspection.company_rows}/${workbook.request.expected_company_count} companies이고 briefing은 ${briefing.observed.status}, Self-QA ${briefing.observed.self_qa_score}, PPTX ${briefing.inspection.slide_count}장과 PDF ${briefing.inspection.page_count}쪽이며 외부 quality는 unknown인 비교`,
      caption: `워크북은 열렸지만 ${workbook.inspection.company_rows}/${workbook.request.expected_company_count}개 회사만 담겼다. 브리핑은 ${briefing.inspection.slide_count}장 PPTX와 ${briefing.inspection.page_count}쪽 PDF가 열렸지만, 두 태스크 모두 외부 품질은 아직 확인되지 않았다.`,
    } : undefined,
    chart: article.comparisonChart ? {
      ...article.comparisonChart,
      description: `워크북 ${workbook.observed.self_qa_score}/10, 브리핑 ${briefing.observed.self_qa_score}/10. 두 값은 모델이 실행 중 남긴 자체 점검이며 외부 평가가 아니다.`,
      data: [
        { label: 'S&P 500 workbook', primary: workbook.observed.self_qa_score },
        { label: 'LatAm briefing', primary: briefing.observed.self_qa_score },
      ],
    } : undefined,
    sections: article.sections.map((section) => {
      if (section.benchmarkNarrative === 'success-expectation') {
        return {
          ...section,
          paragraphs: [
            `${report.shortId}에서 ${report.totalTasks}개 태스크 중 ${report.successCount}개, ${report.successRatePct.toFixed(1)}%가 success로 기록됐다. 처음에는 이 숫자를 보고 “대부분의 일이 사람에게 넘길 수 있는 상태까지 갔다”고 생각했다.`,
            `그런데 ${report.retriedCount}개는 적어도 한 번 다시 실행됐고, 모델이 스스로 매긴 평균 점수는 ${report.avgQaScore.toFixed(2)}/10이었다. 완료율은 높았지만 결과에 대한 자신감은 고르지 않았다. 그래서 success가 정확히 무엇을 뜻하는지 다시 확인하기로 했다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'success-status') {
        return {
          ...section,
          paragraphs: [
            `220개를 모두 다시 읽는 대신 조건을 줄였다. 같은 금융·투자 분석가 직군, 같은 실행 환경에서 나온 두 태스크를 골랐다. 워크북 작업은 실행을 마쳤지만 자체 점검을 통과하지 못해 ${workbook.observed.status}로 남았고 점수는 ${workbook.observed.self_qa_score}/10이었다. 브리핑은 ${briefing.observed.status}로 기록됐고 ${briefing.observed.self_qa_score}/10이었다.`,
            `확인할 질문도 세 가지로 줄였다. 실행이 끝났는가, 파일이 실제로 열리는가, 요청한 핵심 분석이 들어 있는가였다. 전문가 품질은 외부 평가가 없었기 때문에 억지로 결론 내리지 않고 미확인으로 남겼다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'success-workbook') {
        return {
          ...section,
          paragraphs: [
            `워크북 태스크에서 꼭 해야 할 분석은 분명했다. ${workbook.request.as_of_date} 기준 S&P 500 전체 ${workbook.request.expected_company_count}개 기업을 공개 데이터로 채우고, 업종 분류와 지표를 비교할 수 있게 만드는 일이었다. 그래서 회사 수, 출처, 파일 사용 가능성만 먼저 보기로 했다.`,
            `선택된 엑셀은 정상적으로 열렸고 ${workbook.inspection.sheet_count}개 시트, 필터와 고정 행도 있었다. 하지만 실제 회사는 ${workbook.inspection.company_rows}개였고 고유 종목도 ${workbook.inspection.unique_tickers}개뿐이었다. 수식은 하나도 없었으며, 자체 점검도 잘못된 업종 분류와 임시 데이터를 지적했다. 파일은 만들어졌지만 핵심 분석은 끝나지 않은 상태였다.`,
          ],
          callout: `중요한 분석은 파일 개수를 세는 일이 아니었다. 요청한 ${workbook.request.expected_company_count}개 기업이 실제로 들어 있는지 확인하는 일이었다.`,
        }
      }
      if (section.benchmarkNarrative === 'success-briefing') {
        return {
          ...section,
          paragraphs: [
            `같은 방법을 브리핑에도 적용했다. 요청은 라틴아메리카의 거시 환경, 기술·벤처 시장, 핀테크 지형을 약 ${briefing.request.approximate_slide_count}장으로 정리하고 PPTX와 PDF를 함께 만드는 것이었다.`,
            `결과물은 PPTX ${briefing.inspection.slide_count}장과 PDF ${briefing.inspection.page_count}쪽으로 열렸고 빈 페이지도 없었다. 기본 형식과 길이는 확인됐다. 다만 출처가 충분한지, 어느 국가를 먼저 볼지에 대한 판단이 타당한지는 이 검사로 확인할 수 없었다. 따라서 브리핑의 요구 충실도 전체는 미확인으로 남겼다. 자체 점검 ${briefing.observed.self_qa_score}/10을 좋은 신호로 볼 수는 있어도 품질 판정으로 쓸 수는 없었다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'success-interpretation') {
        return {
          ...section,
          paragraphs: [
            `발견은 세 가지였다. 첫째, report의 success는 success 규칙을 통과했다는 상태였다. 둘째, 파일이 열린다는 사실은 내용이 완전하다는 뜻이 아니었다. 셋째, 높은 자체 점검 점수도 외부 품질 평가를 대신하지 못했다.`,
            `따라서 “success면 사람에게 바로 넘길 수 있다”는 처음의 가설은 지지되지 않았다. 그렇다고 200개 결과가 모두 나빴다는 뜻도 아니다. 우리가 확인한 것은 ${report.successRatePct.toFixed(1)}%라는 숫자 하나만으로 전달 가능성을 말할 수 없다는 점이었다.`,
          ],
          points: [
            `상태 신호: report의 success는 success 규칙을 통과했음을 보여줬다.`,
            `내용 검증: 열린 워크북에도 ${workbook.request.expected_company_count - workbook.inspection.company_rows}개 회사가 빠져 있었다.`,
            `품질 판단: 자체 점검 ${workbook.observed.self_qa_score}/10과 ${briefing.observed.self_qa_score}/10은 외부 평가가 아니었다.`,
          ],
        }
      }
      if (section.benchmarkNarrative === 'success-decision') {
        return {
          ...section,
          paragraphs: [
            `근본 원인은 모델 하나가 아니었다. 실행 완료, 파일 확인, 요구사항 충족, 전문가 품질이라는 네 질문을 success 한 줄에 넣어 기록한 방식에도 문제가 있었다.`,
            `그래서 이후에는 네 단계를 따로 본다. ${report.successRatePct.toFixed(1)}%는 report의 success 상태 비율로 남기고, 프로세스가 끝났는지, 파일이 열리는지, 핵심 요구가 들어 있는지, 전문가가 믿고 쓸 수 있는지는 각각 별도의 증거로 확인한다.`,
          ],
        }
      }
      return section
    }),
  }
}

function BenchmarkDataSource({ rows, generated }: { rows: PromptComplexityBenchmarkRow[]; generated: string }) {
  return (
    <aside className="mb-10 border-y border-dash-border py-4 text-[11px]/[1.7] text-dash-text-secondary" aria-label="Benchmark data source">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-mono text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">BENCHMARK DATA</span>
        <a
          href={`${import.meta.env.BASE_URL}generated/reports-index.json`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400"
        >
          reports-index.json <ExternalLink className="h-3 w-3" />
        </a>
        {rows.map((row) => (
          <Link
            key={row.shortId}
            to={getExperimentHref(row.shortId)}
            className="inline-flex items-center gap-1 font-mono hover:text-emerald-600 dark:hover:text-emerald-400"
          >
            {row.shortId} 상세 <ArrowRight className="h-3 w-3" />
          </Link>
        ))}
      </div>
      <div className="mt-2 text-dash-text-muted">
        측정값: reports-index.json report summary · 상세 페이지 상단과 동일 snapshot · 프롬프트 구조: experiment YAML{generated ? ` · index generated ${generated}` : ''}
      </div>
    </aside>
  )
}

function RuntimeDataSource({ benchmark }: { benchmark: ReadyRuntimeBenchmark }) {
  const repo = 'https://github.com/hyeonsangjeon/gdpval-realworks'
  return (
    <aside className="mb-12 border-y border-dash-border py-5 text-[11px]/[1.75] text-dash-text-secondary" aria-label="Runtime evidence source">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-mono text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">RUNTIME EVIDENCE</span>
        <a href={`${import.meta.env.BASE_URL}generated/runtime-note.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          runtime-note.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${import.meta.env.BASE_URL}generated/reports-index.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          reports-index.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/blob/main/${benchmark.sources.workflow}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          workflow YAML <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/actions/runs/${benchmark.incident.action_run_id}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          incident run <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/blob/${benchmark.incident.workflow_commit}/${benchmark.sources.workflow}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          incident workflow <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/commit/${benchmark.incident.fix.commit}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          watchdog fix <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/blob/${benchmark.incident.source_record_commit}/CHANGELOG.md`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          incident record <ExternalLink className="h-3 w-3" />
        </a>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-2">
        {benchmark.rows.map((row) => (
          <Link key={row.shortId} to={getExperimentHref(row.shortId)} className="inline-flex items-center gap-1 font-mono hover:text-emerald-600 dark:hover:text-emerald-400">
            {row.shortId} · {row.executionMode} · {row.duration} <ArrowRight className="h-3 w-3" />
          </Link>
        ))}
      </div>
      <div className="mt-3 text-dash-text-muted">
        290분 watchdog은 현재 workflow의 condition_a 경로 기준이다. duration은 실험 전체 경과시간이며, relay가 이어진 exp025·exp026에서는 한 job의 실행 시간과 같지 않다.
      </div>
    </aside>
  )
}

function IntegrityDataSource({ benchmark }: { benchmark: ReadyIntegrityBenchmark }) {
  const repo = 'https://github.com/hyeonsangjeon/gdpval-realworks'
  const history = benchmark.history
  return (
    <aside className="mb-12 border-y border-dash-border py-5 text-[11px]/[1.75] text-dash-text-secondary" aria-label="Integrity evidence source">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-mono text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">INTEGRITY EVIDENCE</span>
        <a href={`${import.meta.env.BASE_URL}generated/integrity-note.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          integrity-note.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${import.meta.env.BASE_URL}generated/reports-index.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          reports-index.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/blob/${history.parent_commit}/batch-runner/core/subprocess_runner.py`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          pre-fix runner <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/commit/${history.core_fix_commit}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          core fix <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/commit/${history.followup_commit}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          follow-up <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/commit/${history.merge_commit}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          PR #38 merge <ExternalLink className="h-3 w-3" />
        </a>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-2">
        {benchmark.rows.map((row) => (
          <Link key={row.shortId} to={getExperimentHref(row.shortId)} className="inline-flex items-center gap-1 font-mono hover:text-emerald-600 dark:hover:text-emerald-400">
            {row.shortId} · {row.successCount}/{row.totalTasks} · {row.successRatePct.toFixed(1)}% <ArrowRight className="h-3 w-3" />
          </Link>
        ))}
      </div>
      <div className="mt-3 text-dash-text-muted">
        report는 배포 시점 snapshot이다. 실행 당시 Git SHA·입력 revision·Azure model revision·runner environment가 없어 관측 차이를 수정의 인과 효과로 배분하지 않는다.
      </div>
    </aside>
  )
}

function PerceptionDataSource({ benchmark }: { benchmark: ReadyPerceptionBenchmark }) {
  const repo = 'https://github.com/hyeonsangjeon/gdpval-realworks'
  return (
    <aside className="mb-12 border-y border-dash-border py-5 text-[11px]/[1.75] text-dash-text-secondary" aria-label="Perception evidence source">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-mono text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">PERCEPTION EVIDENCE</span>
        <a href={`${import.meta.env.BASE_URL}generated/perception-note.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          perception-note.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${import.meta.env.BASE_URL}generated/reports-index.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          reports-index.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/blob/main/${benchmark.sources.perception}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          interpretation contract <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/commit/${benchmark.history.audio_preprocessor_commit}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          audio history <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/commit/${benchmark.history.sandbox_multimodal_commit}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          sandbox history <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/commit/${benchmark.history.docker_always_commit}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          Docker-required history <ExternalLink className="h-3 w-3" />
        </a>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-2">
        {benchmark.rows.map((row) => (
          <Link key={row.shortId} to={getExperimentHref(row.shortId)} className="inline-flex items-center gap-1 font-mono hover:text-emerald-600 dark:hover:text-emerald-400">
            {row.shortId} · {row.information.success}/{row.information.total} · QA {row.information.avgQaScore.toFixed(2)} <ArrowRight className="h-3 w-3" />
          </Link>
        ))}
      </div>
      <div className="mt-3 text-dash-text-muted">
        report는 배포 시점의 self-assessed pre-grading snapshot이다. configured path는 analyzer 호출 횟수가 아니며, 세 실행의 차이는 perception 단독 인과 효과가 아니다.
      </div>
    </aside>
  )
}

function SuccessDataSource({ benchmark }: { benchmark: ReadySuccessBenchmark }) {
  const repo = 'https://github.com/hyeonsangjeon/gdpval-realworks'
  const hf = `https://huggingface.co/datasets/${benchmark.huggingface.repository}`
  return (
    <aside className="mb-12 border-y border-dash-border py-5 text-[11px]/[1.75] text-dash-text-secondary" aria-label="Success evidence source">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-mono text-[10px] font-semibold text-emerald-700 dark:text-emerald-400">SUCCESS EVIDENCE</span>
        <a href={`${import.meta.env.BASE_URL}generated/success-note.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          success-note.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${import.meta.env.BASE_URL}generated/reports-index.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          reports-index.json <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${hf}/blob/${benchmark.huggingface.revision}/self_report.json`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          pinned self-report <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${hf}/tree/${benchmark.huggingface.revision}/deliverable_files/${benchmark.workbook.task_id}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          workbook artifacts <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${hf}/tree/${benchmark.huggingface.revision}/deliverable_files/${benchmark.briefing.task_id}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          briefing artifacts <ExternalLink className="h-3 w-3" />
        </a>
        <a href={`${repo}/tree/main/${benchmark.sources.grades}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:text-emerald-600 dark:hover:text-emerald-400">
          grade inventory <ExternalLink className="h-3 w-3" />
        </a>
        <Link to={getExperimentHref('exp026')} className="inline-flex items-center gap-1 font-mono hover:text-emerald-600 dark:hover:text-emerald-400">
          exp026 상세 <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="mt-3 text-dash-text-muted">
        report는 self-assessed pre-grading이다. artifact는 HF revision {benchmark.huggingface.revision.slice(0, 7)}와 SHA-256으로 고정했으며, 구조 검사는 외부 금융 품질 평가를 대신하지 않는다.
      </div>
    </aside>
  )
}

function BenchmarkDataState({ message, error }: { message: string; error?: boolean }) {
  return (
    <div className="max-w-[1080px] mx-auto px-4 md:px-6 py-8 md:py-10">
      <div className="border-y border-dash-border bg-dash-surface px-5 py-8 text-sm text-dash-text-secondary" role={error ? 'alert' : 'status'}>
        {message}
      </div>
    </div>
  )
}

export default function JournalArticle() {
  const { slug } = useParams()

  return <JournalArticleContent key={slug ?? 'missing'} slug={slug} />
}

function JournalArticleContent({ slug }: { slug: string | undefined }) {
  const navigate = useNavigate()
  const { isDark, toggle: toggleTheme } = useTheme()
  const article = getJournalArticle(slug)
  const usesPromptBenchmark = article?.benchmark?.kind === 'prompt-complexity'
  const isReflective = article?.readingStyle === 'reflective'
  const usesRuntimeBenchmark = article?.benchmark?.kind === 'runtime'
  const usesIntegrityBenchmark = article?.benchmark?.kind === 'integrity'
  const usesPerceptionBenchmark = article?.benchmark?.kind === 'perception'
  const usesSuccessBenchmark = article?.benchmark?.kind === 'success'
  const usesReportBenchmark = usesPromptBenchmark || usesRuntimeBenchmark || usesIntegrityBenchmark || usesPerceptionBenchmark || usesSuccessBenchmark
  const { reports, generated, loading: reportsLoading, error: reportsError } = useReports(usesReportBenchmark)
  const { data: runtimeNote, loading: runtimeLoading, error: runtimeError } = useRuntimeNote(usesRuntimeBenchmark)
  const { data: integrityNote, loading: integrityLoading, error: integrityError } = useIntegrityNote(usesIntegrityBenchmark)
  const { data: perceptionNote, loading: perceptionLoading, error: perceptionError } = usePerceptionNote(usesPerceptionBenchmark)
  const { data: successNote, loading: successLoading, error: successError } = useSuccessNote(usesSuccessBenchmark)
  const promptBenchmark = usesPromptBenchmark && !reportsLoading && !reportsError
    ? selectPromptComplexityBenchmark(reports)
    : null
  const readyPromptBenchmark = promptBenchmark?.status === 'ready' ? promptBenchmark : null
  const runtimeBenchmark = usesRuntimeBenchmark && !reportsLoading && !reportsError && !runtimeLoading && !runtimeError
    ? selectRuntimeNoteBenchmark(reports, runtimeNote)
    : null
  const readyRuntimeBenchmark = runtimeBenchmark?.status === 'ready' ? runtimeBenchmark : null
  const integrityBenchmark = usesIntegrityBenchmark && !reportsLoading && !reportsError && !integrityLoading && !integrityError
    ? selectIntegrityNoteBenchmark(reports, integrityNote)
    : null
  const readyIntegrityBenchmark = integrityBenchmark?.status === 'ready' ? integrityBenchmark : null
  const perceptionBenchmark = usesPerceptionBenchmark && !reportsLoading && !reportsError && !perceptionLoading && !perceptionError
    ? selectPerceptionBenchmark(reports, perceptionNote)
    : null
  const readyPerceptionBenchmark = perceptionBenchmark?.status === 'ready' ? perceptionBenchmark : null
  const successBenchmark = usesSuccessBenchmark && !reportsLoading && !reportsError && !successLoading && !successError
    ? selectSuccessNoteBenchmark(reports, successNote)
    : null
  const readySuccessBenchmark = successBenchmark?.status === 'ready' ? successBenchmark : null
  const resolved = article && readyPromptBenchmark
    ? resolvePromptComplexityArticle(article, readyPromptBenchmark)
    : article && readyRuntimeBenchmark
      ? resolveRuntimeArticle(article, readyRuntimeBenchmark)
      : article && readyIntegrityBenchmark
        ? resolveIntegrityArticle(article, readyIntegrityBenchmark)
        : article && readyPerceptionBenchmark
          ? resolvePerceptionArticle(article, readyPerceptionBenchmark)
          : article && readySuccessBenchmark
            ? resolveSuccessArticle(article, readySuccessBenchmark)
            : null

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [slug])

  if (!article) {
    return (
      <div className="min-h-screen bg-dash-page flex items-center justify-center px-4">
        <div className="text-center">
          <BookOpen className="w-8 h-8 text-dash-text-faint mx-auto mb-4" />
          <h1 className="text-lg font-semibold text-dash-heading mb-2">기록을 찾을 수 없습니다</h1>
          <Link to="/notes" className="text-sm text-emerald-600 dark:text-emerald-400 hover:underline">기록으로 돌아가기</Link>
        </div>
      </div>
    )
  }

  const related = journalArticles
    .filter((item) => item.slug !== article.slug && item.relatedExperiments.some((id) => article.relatedExperiments.includes(id)))
    .slice(0, 2)
  const displayedMetrics = resolved?.metrics ?? article.metrics
  const displayedChart = resolved?.chart ?? article.comparisonChart
  const benchmarkReady = readyPromptBenchmark || readyRuntimeBenchmark || readyIntegrityBenchmark || readyPerceptionBenchmark || readySuccessBenchmark
  const displayedSections = (usesRuntimeBenchmark && !readyRuntimeBenchmark) || (usesIntegrityBenchmark && !readyIntegrityBenchmark) || (usesPerceptionBenchmark && !readyPerceptionBenchmark) || (usesSuccessBenchmark && !readySuccessBenchmark)
    ? []
    : (resolved?.sections ?? article.sections)
      .filter((section) => !section.benchmarkNarrative || benchmarkReady)
  const hasCitationContract = Boolean(
    article.thesisCitations?.length
    || article.evidence.some((source) => source.id)
    || article.sections.some((section) => (
      section.paragraphCitations?.length || section.calloutCitations?.length
    )),
  )
  const citationsReady = !hasCitationContract || !usesReportBenchmark || Boolean(benchmarkReady)
  const citationError = citationsReady
    ? validateJournalCitations(article, displayedSections)
    : null
  if (citationError) {
    return (
      <div lang="ko" className="min-h-screen bg-dash-page text-dash-text font-journal-sans">
        <BenchmarkDataState error message={`본문 인용 계약이 유효하지 않습니다: ${citationError}`} />
      </div>
    )
  }
  const evidenceLookup = citationsReady
    ? new Map(
      article.evidence.flatMap((source, index) => source.id ? [[source.id, { source, index }] as const] : []),
    )
    : new Map<string, { source: JournalEvidence; index: number }>()
  const citationBackrefs = new Map<string, string[]>()
  const registerBackrefs = (evidenceIds: string[] | undefined, prefix: string) => {
    for (const evidenceId of evidenceIds ?? []) {
      if (!evidenceLookup.has(evidenceId)) continue
      const refs = citationBackrefs.get(evidenceId) ?? []
      refs.push(citationAnchorId(prefix, evidenceId))
      citationBackrefs.set(evidenceId, refs)
    }
  }
  if (citationsReady) {
    registerBackrefs(article.thesisCitations, 'thesis')
    displayedSections.forEach((section, sectionIndex) => {
      section.paragraphCitations?.forEach((evidenceIds, paragraphIndex) => {
        registerBackrefs(evidenceIds, `section-${sectionIndex + 1}-paragraph-${paragraphIndex + 1}`)
      })
      registerBackrefs(section.calloutCitations, `section-${sectionIndex + 1}-callout`)
    })
  }

  return (
    <div lang="ko" className="min-h-screen bg-dash-page text-dash-text font-journal-sans">
      <header className="border-b border-dash-border bg-dash-page/90 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-[980px] mx-auto px-4 md:px-6 py-3 flex items-center gap-3">
          <button
            onClick={() => navigate('/notes')}
            className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-colors"
            title="Back to notes"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <Link to="/notes" className="flex items-center gap-2 text-sm font-semibold text-dash-heading">
            <BookOpen className="w-4 h-4 text-emerald-500" />
            RealWorks Field Notes
          </Link>
          <button
            onClick={toggleTheme}
            className="ml-auto inline-flex items-center justify-center w-9 h-9 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-colors"
            title={isDark ? '라이트 모드' : '다크 모드'}
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      <article>
        <header className="border-b border-dash-border bg-dash-surface">
          <div className="max-w-[860px] mx-auto px-4 md:px-6 py-12 md:py-20">
            <div className="flex flex-wrap items-center gap-3 mb-6">
              <span className={`inline-flex border rounded px-2 py-1 text-[10px] font-medium ${lensStyles[article.lens]}`}>
                {lensLabels[article.lens]}
              </span>
              <span className="text-[11px] text-dash-text-muted">{article.period}</span>
            </div>
            <h1 className="font-journal-serif text-[34px] md:text-[52px] leading-[1.13] tracking-normal text-balance break-keep text-dash-heading mb-6">{article.title}</h1>
            <p className="max-w-[720px] text-[15px] md:text-[17px] text-dash-text-secondary leading-[1.8] break-keep mb-7">{article.dek}</p>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 pt-5 border-t border-dash-border text-[11px] text-dash-text-muted">
              <span>{article.publishedAt}</span>
              <span className="inline-flex items-center gap-1.5"><Clock3 className="w-3.5 h-3.5" /> {article.readingMinutes}분</span>
              <span className="inline-flex items-center gap-1.5"><FlaskConical className="w-3.5 h-3.5" /> {article.relatedExperiments.length} experiments</span>
            </div>
          </div>
        </header>

        {article.hero && (!usesReportBenchmark || benchmarkReady) && (
          <NoteHeroVisual
            hero={resolved?.hero ?? article.hero}
            promptBenchmark={readyPromptBenchmark?.rows}
            runtimeBenchmark={readyRuntimeBenchmark ?? undefined}
            integrityBenchmark={readyIntegrityBenchmark ?? undefined}
            perceptionBenchmark={readyPerceptionBenchmark ?? undefined}
            successBenchmark={readySuccessBenchmark ?? undefined}
          />
        )}
        {usesPromptBenchmark && reportsLoading && <BenchmarkDataState message="benchmark report 데이터를 불러오는 중입니다." />}
        {usesPromptBenchmark && reportsError && <BenchmarkDataState error message={`benchmark report를 불러오지 못했습니다: ${reportsError}`} />}
        {usesPromptBenchmark && promptBenchmark?.status === 'missing' && (
          <BenchmarkDataState error message={`benchmark report에서 ${promptBenchmark.missingIds.join(', ')} 행을 찾지 못했습니다.`} />
        )}
        {usesPromptBenchmark && promptBenchmark?.status === 'invalid' && (
          <BenchmarkDataState error message={`benchmark report의 ${promptBenchmark.invalidIds.join(', ')} 행이 유효하지 않습니다.`} />
        )}
        {usesRuntimeBenchmark && (reportsLoading || runtimeLoading) && <BenchmarkDataState message="runtime 근거 데이터를 불러오는 중입니다." />}
        {usesRuntimeBenchmark && reportsError && <BenchmarkDataState error message={`runtime report를 불러오지 못했습니다: ${reportsError}`} />}
        {usesRuntimeBenchmark && runtimeError && <BenchmarkDataState error message={`runtime policy를 불러오지 못했습니다: ${runtimeError}`} />}
        {usesRuntimeBenchmark && runtimeBenchmark?.status === 'missing' && (
          <BenchmarkDataState error message={`runtime report에서 ${runtimeBenchmark.missingIds.join(', ')} 행을 찾지 못했습니다.`} />
        )}
        {usesRuntimeBenchmark && runtimeBenchmark?.status === 'invalid' && (
          <BenchmarkDataState error message={`runtime 근거의 ${runtimeBenchmark.invalidSources.join(', ')} 항목이 유효하지 않습니다.`} />
        )}
        {usesIntegrityBenchmark && (reportsLoading || integrityLoading) && <BenchmarkDataState message="integrity 근거 데이터를 불러오는 중입니다." />}
        {usesIntegrityBenchmark && reportsError && <BenchmarkDataState error message={`integrity report를 불러오지 못했습니다: ${reportsError}`} />}
        {usesIntegrityBenchmark && integrityError && <BenchmarkDataState error message={`integrity history를 불러오지 못했습니다: ${integrityError}`} />}
        {usesIntegrityBenchmark && integrityBenchmark?.status === 'missing' && (
          <BenchmarkDataState error message={`integrity report에서 ${integrityBenchmark.missingIds.join(', ')} 행을 찾지 못했습니다.`} />
        )}
        {usesIntegrityBenchmark && integrityBenchmark?.status === 'invalid' && (
          <BenchmarkDataState error message={`integrity 근거의 ${integrityBenchmark.invalidSources.join(', ')} 항목이 유효하지 않습니다.`} />
        )}
        {usesPerceptionBenchmark && (reportsLoading || perceptionLoading) && <BenchmarkDataState message="perception 근거 데이터를 불러오는 중입니다." />}
        {usesPerceptionBenchmark && reportsError && <BenchmarkDataState error message={`perception report를 불러오지 못했습니다: ${reportsError}`} />}
        {usesPerceptionBenchmark && perceptionError && <BenchmarkDataState error message={`perception history를 불러오지 못했습니다: ${perceptionError}`} />}
        {usesPerceptionBenchmark && perceptionBenchmark?.status === 'missing' && (
          <BenchmarkDataState error message={`perception report에서 ${perceptionBenchmark.missingIds.join(', ')} 행을 찾지 못했습니다.`} />
        )}
        {usesPerceptionBenchmark && perceptionBenchmark?.status === 'invalid' && (
          <BenchmarkDataState error message={`perception 근거의 ${perceptionBenchmark.invalidSources.join(', ')} 항목이 유효하지 않습니다.`} />
        )}
        {usesSuccessBenchmark && (reportsLoading || successLoading) && <BenchmarkDataState message="success 근거 데이터를 불러오는 중입니다." />}
        {usesSuccessBenchmark && reportsError && <BenchmarkDataState error message={`success report를 불러오지 못했습니다: ${reportsError}`} />}
        {usesSuccessBenchmark && successError && <BenchmarkDataState error message={`success artifact contract를 불러오지 못했습니다: ${successError}`} />}
        {usesSuccessBenchmark && successBenchmark?.status === 'missing' && (
          <BenchmarkDataState error message={`success report에서 ${successBenchmark.missingIds.join(', ')} 행을 찾지 못했습니다.`} />
        )}
        {usesSuccessBenchmark && successBenchmark?.status === 'invalid' && (
          <BenchmarkDataState error message={`success 근거의 ${successBenchmark.invalidSources.join(', ')} 항목이 유효하지 않습니다.`} />
        )}

        {citationsReady && <div className="max-w-[760px] mx-auto px-4 md:px-6 py-12 md:py-16">
          {readyPromptBenchmark && <BenchmarkDataSource rows={readyPromptBenchmark.rows} generated={generated} />}
          {readyRuntimeBenchmark && <RuntimeDataSource benchmark={readyRuntimeBenchmark} />}
          {readyIntegrityBenchmark && <IntegrityDataSource benchmark={readyIntegrityBenchmark} />}
          {readyPerceptionBenchmark && <PerceptionDataSource benchmark={readyPerceptionBenchmark} />}
          {readySuccessBenchmark && <SuccessDataSource benchmark={readySuccessBenchmark} />}
          <div className="mb-14 md:mb-16">
            <div className="flex items-center gap-3 mb-4" aria-hidden="true">
              <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400">THESIS</span>
              <span className="h-px w-10 bg-emerald-500/40" />
            </div>
            <blockquote className="border-l-2 border-emerald-500 pl-4 md:pl-7 py-1 font-journal-serif text-[19px] md:text-[25px] leading-[1.75] md:leading-[1.65] tracking-normal text-pretty break-keep text-dash-heading">
              {article.thesis}
              <InlineCitations evidenceIds={article.thesisCitations} prefix="thesis" evidenceLookup={evidenceLookup} />
            </blockquote>
          </div>

          {displayedMetrics.length > 0 && (
            <div className="grid grid-cols-3 border-y border-dash-border mb-16 md:mb-20">
              {displayedMetrics.map((metric) => (
                <div key={metric.label} className="py-6 md:py-7 px-2 md:px-4 text-center border-r border-dash-border last:border-r-0">
                  <div className="font-mono text-xl md:text-[28px] font-semibold text-dash-heading mb-2">{metric.value}</div>
                  <div className="text-[10px] md:text-xs text-dash-text-muted leading-[1.5]">{metric.label}</div>
                  {metric.note && <div className="text-[9px] text-dash-text-faint mt-1.5">{metric.note}</div>}
                </div>
              ))}
            </div>
          )}

          {displayedChart && (!usesReportBenchmark || benchmarkReady) && (
            <NoteComparisonChart chart={displayedChart} />
          )}

          <div className={isReflective ? 'space-y-20 md:space-y-28' : 'space-y-16 md:space-y-20'}>
            {displayedSections.map((section, sectionIndex) => (
              <section key={section.heading} className={isReflective ? 'scroll-mt-24' : undefined}>
                <div className={isReflective ? 'mb-8 md:mb-10' : 'mb-6 md:mb-8'}>
                  <div className={isReflective ? 'flex items-center gap-3 mb-4' : 'flex items-center gap-3 mb-3'} aria-hidden="true">
                    <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400">
                      {String(sectionIndex + 1).padStart(2, '0')}
                    </span>
                    <span className="h-px w-8 bg-dash-border-active" />
                    {section.label && (
                      <span className="font-mono text-[10px] text-dash-text-muted">{section.label}</span>
                    )}
                  </div>
                  <h2 className={isReflective
                    ? 'max-w-[660px] font-journal-serif text-[28px] md:text-[34px] leading-[1.42] tracking-normal text-balance break-keep text-dash-heading'
                    : 'font-journal-serif text-[26px] md:text-[30px] leading-[1.35] tracking-normal text-balance break-keep text-dash-heading'}>
                    {section.heading}
                  </h2>
                </div>
                <div className={isReflective ? 'space-y-7 md:space-y-8' : 'space-y-5'}>
                  {section.paragraphs.map((paragraph, paragraphIndex) => (
                    <p
                      key={paragraph}
                      className={isReflective
                        ? `max-w-[700px] text-[16px]/[2.05] md:text-[17px]/[2.05] text-pretty break-keep ${paragraphIndex === 0 ? 'text-dash-heading' : 'text-dash-text'}`
                        : 'text-[15px]/[1.9] md:text-[16px]/[1.9] text-pretty break-keep text-dash-text'}
                    >
                      {paragraph}
                      <InlineCitations
                        evidenceIds={section.paragraphCitations?.[paragraphIndex]}
                        prefix={`section-${sectionIndex + 1}-paragraph-${paragraphIndex + 1}`}
                        evidenceLookup={evidenceLookup}
                      />
                    </p>
                  ))}
                </div>
                {section.points && (
                  <ul className="mt-7 border-y border-dash-border divide-y divide-dash-border">
                    {section.points.map((point, pointIndex) => (
                      <li key={point} className="flex gap-4 py-4 text-[15px] md:text-base leading-[1.75] text-dash-text-secondary">
                        <span className="font-mono text-[10px] text-emerald-500 pt-1.5">{String(pointIndex + 1).padStart(2, '0')}</span>
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {section.callout && (
                  <div className={isReflective
                    ? 'mt-10 border-y border-dash-border px-1 md:px-6 py-6 font-journal-serif text-[15px]/[1.9] md:text-[16px]/[1.9] text-pretty break-keep text-dash-text-secondary'
                    : 'mt-8 bg-dash-surface/60 border-y border-dash-border px-5 py-5 text-[13px] md:text-sm text-dash-text leading-7'}>
                    {section.callout}
                    <InlineCitations
                      evidenceIds={section.calloutCitations}
                      prefix={`section-${sectionIndex + 1}-callout`}
                      evidenceLookup={evidenceLookup}
                    />
                  </div>
                )}
              </section>
            ))}
          </div>

          <section className="mt-20 md:mt-24 pt-9 border-t border-dash-border">
            <div className="flex items-center gap-4 mb-5">
              <h2 className="font-journal-serif text-xl text-dash-heading">관련 실험</h2>
              <span className="h-px flex-1 bg-dash-border" aria-hidden="true" />
            </div>
            <div className="flex flex-wrap gap-2">
              {article.relatedExperiments.map((experiment) => {
                const href = getExperimentHref(experiment)
                const className = 'inline-flex items-center gap-1.5 font-mono text-[11px] text-dash-text-secondary bg-dash-card border border-dash-border rounded px-2.5 py-1.5 hover:text-emerald-600 dark:hover:text-emerald-400 hover:border-emerald-500/30 transition-colors'
                return isExternalExperimentHref(href) ? (
                  <a key={experiment} href={href} target="_blank" rel="noopener noreferrer" className={className}>
                    {experiment} <ExternalLink className="w-3 h-3" />
                  </a>
                ) : (
                  <Link key={experiment} to={href} className={className}>
                    {experiment} <ArrowRight className="w-3 h-3" />
                  </Link>
                )
              })}
            </div>
          </section>

          <section className="mt-14">
            <div className="flex items-center gap-4 mb-5">
              <h2 className="font-journal-serif text-xl text-dash-heading">근거와 원문</h2>
              <span className="h-px flex-1 bg-dash-border" aria-hidden="true" />
            </div>
            <div className="border-t border-dash-border">
              {article.evidence.map((source, sourceIndex) => {
                const sourceId = source.id ?? `source-${sourceIndex + 1}`
                const backrefs = citationBackrefs.get(sourceId) ?? []
                return (
                <div
                  key={source.id ?? source.href}
                  id={evidenceAnchorId(sourceId)}
                  data-evidence-id={sourceId}
                  className="scroll-mt-24 grid grid-cols-[28px_1fr] gap-3 md:gap-4 py-5 border-b border-dash-border target:bg-emerald-500/5 transition-colors"
                >
                  <span className="font-mono text-[10px] font-semibold text-dash-text-secondary pt-0.5">{String(sourceIndex + 1).padStart(2, '0')}</span>
                  <div>
                    <a
                      href={source.href}
                      target={source.href.startsWith('http') ? '_blank' : undefined}
                      rel={source.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                      className="group/source grid grid-cols-[1fr_auto] gap-3 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors"
                    >
                      <span className="text-[13px] font-medium text-dash-heading group-hover/source:text-emerald-600 dark:group-hover/source:text-emerald-400">{source.label}</span>
                      <ExternalLink className="w-3.5 h-3.5 text-dash-text-faint group-hover/source:text-emerald-500 flex-shrink-0 mt-0.5" />
                    </a>
                    <div className="text-xs text-dash-text-secondary leading-[1.7]">{source.detail}</div>
                    {source.source && <div className="mt-2 font-mono text-[10px]/[1.6] text-dash-text-faint break-all">{source.source}</div>}
                    {backrefs.length > 0 && (
                      <div className="mt-3 flex flex-wrap items-center gap-2" aria-label={`${source.label} 본문 복귀 링크`}>
                        {backrefs.map((backref, backrefIndex) => (
                          <a
                            key={backref}
                            href={`#${backref}`}
                            aria-label={`${source.label}을 인용한 본문 ${backrefIndex + 1}로 돌아가기`}
                            className="inline-flex min-h-6 items-center gap-1 px-1 py-1 font-mono text-[9px] text-dash-text-muted hover:text-emerald-600 dark:hover:text-emerald-400"
                          >
                            <ArrowLeft className="w-2.5 h-2.5" /> 본문 {String(backrefIndex + 1).padStart(2, '0')}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )})}
            </div>
          </section>

          {related.length > 0 && (
            <section className="mt-20 pt-9 border-t border-dash-border">
              <div className="flex items-center gap-4 mb-6">
                <h2 className="font-journal-serif text-xl text-dash-heading">같이 읽을 기록</h2>
                <span className="h-px flex-1 bg-dash-border" aria-hidden="true" />
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                {related.map((item) => (
                  <Link key={item.slug} to={`/notes/${item.slug}`} className="group bg-dash-card border border-dash-border rounded-lg p-5 hover:bg-dash-card-hover transition-colors">
                    <div className="text-[10px] text-dash-text-muted mb-3">{lensLabels[item.lens]}</div>
                    <h3 className="font-journal-serif text-[19px] leading-[1.45] tracking-normal break-keep text-dash-heading group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors mb-4">{item.title}</h3>
                    <span className="inline-flex items-center gap-1 text-[10px] text-dash-text-muted">읽기 <ArrowRight className="w-3 h-3" /></span>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>}
      </article>
    </div>
  )
}