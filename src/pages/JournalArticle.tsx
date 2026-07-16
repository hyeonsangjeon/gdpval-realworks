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
import {
  selectPromptComplexityBenchmark,
  type PromptComplexityBenchmarkRow,
  type PromptComplexityBenchmarkSelection,
} from '../lib/promptComplexityBenchmark'
import {
  getJournalArticle,
  journalArticles,
  lensLabels,
  type JournalArticle as JournalArticleData,
  type JournalLens,
} from '../data/journal'
import { getExperimentHref, isExternalExperimentHref } from '../data/journalLinks'

const lensStyles: Record<JournalLens, string> = {
  experiment: 'text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
  engineering: 'text-blue-700 dark:text-blue-300 bg-blue-500/10 border-blue-500/20',
  task: 'text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-500/20',
  domain: 'text-rose-700 dark:text-rose-300 bg-rose-500/10 border-rose-500/20',
}

type ReadyPromptBenchmark = Extract<PromptComplexityBenchmarkSelection, { status: 'ready' }>

const formatSigned = (value: number, suffix: string) => `${value > 0 ? '+' : ''}${value.toFixed(1)}${suffix}`

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
  const { reports, generated, loading: reportsLoading, error: reportsError } = useReports(usesPromptBenchmark)
  const promptBenchmark = usesPromptBenchmark && !reportsLoading && !reportsError
    ? selectPromptComplexityBenchmark(reports)
    : null
  const readyPromptBenchmark = promptBenchmark?.status === 'ready' ? promptBenchmark : null
  const resolved = article && readyPromptBenchmark
    ? resolvePromptComplexityArticle(article, readyPromptBenchmark)
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
  const displayedSections = (resolved?.sections ?? article.sections)
    .filter((section) => !section.benchmarkNarrative || readyPromptBenchmark)

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

        {article.hero && (!usesPromptBenchmark || readyPromptBenchmark) && (
          <NoteHeroVisual
            hero={resolved?.hero ?? article.hero}
            promptBenchmark={readyPromptBenchmark?.rows}
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

        <div className="max-w-[760px] mx-auto px-4 md:px-6 py-12 md:py-16">
          {readyPromptBenchmark && <BenchmarkDataSource rows={readyPromptBenchmark.rows} generated={generated} />}
          <div className="mb-14 md:mb-16">
            <div className="flex items-center gap-3 mb-4" aria-hidden="true">
              <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400">THESIS</span>
              <span className="h-px w-10 bg-emerald-500/40" />
            </div>
            <blockquote className="border-l-2 border-emerald-500 pl-4 md:pl-7 py-1 font-journal-serif text-[19px] md:text-[25px] leading-[1.75] md:leading-[1.65] tracking-normal text-pretty break-keep text-dash-heading">
              {article.thesis}
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

          {displayedChart && (!usesPromptBenchmark || readyPromptBenchmark) && (
            <NoteComparisonChart chart={displayedChart} />
          )}

          <div className="space-y-16 md:space-y-20">
            {displayedSections.map((section, sectionIndex) => (
              <section key={section.heading}>
                <div className="mb-6 md:mb-8">
                  <div className="flex items-center gap-3 mb-3" aria-hidden="true">
                    <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400">
                      {String(sectionIndex + 1).padStart(2, '0')}
                    </span>
                    <span className="h-px w-8 bg-dash-border-active" />
                  </div>
                  <h2 className="font-journal-serif text-[26px] md:text-[30px] leading-[1.35] tracking-normal text-balance break-keep text-dash-heading">
                    {section.heading}
                  </h2>
                </div>
                <div className="space-y-5">
                  {section.paragraphs.map((paragraph) => (
                    <p
                      key={paragraph}
                      className="text-[15px]/[1.9] md:text-[16px]/[1.9] text-pretty break-keep text-dash-text"
                    >
                      {paragraph}
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
                  <div className="mt-8 bg-dash-surface/60 border-y border-dash-border px-5 py-5 text-[13px] md:text-sm text-dash-text leading-7">
                    {section.callout}
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
              {article.evidence.map((source, sourceIndex) => (
                <a
                  key={source.href}
                  href={source.href}
                  target={source.href.startsWith('http') ? '_blank' : undefined}
                  rel={source.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                  className="group grid grid-cols-[28px_1fr_auto] gap-3 md:gap-4 py-5 border-b border-dash-border hover:bg-dash-card/40 transition-colors"
                >
                  <span className="font-mono text-[10px] font-semibold text-dash-text-secondary pt-0.5">{String(sourceIndex + 1).padStart(2, '0')}</span>
                  <div>
                    <div className="text-[13px] font-medium text-dash-heading mb-1.5">{source.label}</div>
                    <div className="text-xs text-dash-text-secondary leading-[1.7]">{source.detail}</div>
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-dash-text-faint group-hover:text-emerald-500 flex-shrink-0 mt-1" />
                </a>
              ))}
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
        </div>
      </article>
    </div>
  )
}