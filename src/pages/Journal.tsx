import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FlaskConical,
  GitCommitHorizontal,
  Moon,
  Sun,
  Wrench,
} from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTheme } from '../contexts/ThemeContext'
import {
  experimentGroups,
  journalArticles,
  lensLabels,
  timelineEvents,
  type JournalLens,
} from '../data/journal'

const lensStyles: Record<JournalLens, string> = {
  experiment: 'text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
  engineering: 'text-blue-700 dark:text-blue-300 bg-blue-500/10 border-blue-500/20',
  task: 'text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-500/20',
  domain: 'text-rose-700 dark:text-rose-300 bg-rose-500/10 border-rose-500/20',
}

const stateMeta = {
  finding: { label: '관찰됨', icon: CheckCircle2, className: 'text-emerald-600 dark:text-emerald-400' },
  open: { label: '열린 질문', icon: CircleAlert, className: 'text-amber-600 dark:text-amber-400' },
  caution: { label: '비교 주의', icon: CircleAlert, className: 'text-rose-600 dark:text-rose-400' },
}

export default function Journal() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { isDark, toggle: toggleTheme } = useTheme()
  const view = searchParams.get('view') === 'timeline' ? 'timeline' : 'questions'
  const featured = journalArticles.find((article) => article.featured) ?? journalArticles[0]

  const changeView = (next: 'questions' | 'timeline') => {
    setSearchParams(next === 'timeline' ? { view: 'timeline' } : {})
  }

  return (
    <div lang="ko" className="min-h-screen bg-dash-page text-dash-text font-journal-sans">
      <header className="border-b border-dash-border bg-dash-page/90 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-[1200px] mx-auto px-4 md:px-6 py-3 flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-colors"
            title="Back to dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <BookOpen className="w-5 h-5 text-emerald-500" />
          <div>
            <h1 className="text-base font-semibold text-dash-heading">RealWorks Field Notes</h1>
            <p className="text-xs text-dash-text-muted">Independent experiments, decisions, and lessons</p>
          </div>
          <button
            onClick={toggleTheme}
            className="ml-auto inline-flex items-center justify-center w-9 h-9 rounded-lg border border-dash-border bg-dash-card hover:bg-dash-card-hover text-dash-text-secondary hover:text-dash-heading transition-colors"
            title={isDark ? '라이트 모드' : '다크 모드'}
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      <section className="border-b border-dash-border bg-dash-surface">
        <div className="max-w-[1200px] mx-auto px-4 md:px-6 py-12 md:py-20">
          <div className="max-w-4xl">
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-700 dark:text-emerald-400 mb-5">
              <FlaskConical className="w-4 h-4" />
              OpenAI GDPVal을 활용한 독립 프로젝트 기록
            </div>
            <h2 className="font-journal-serif text-[34px] md:text-[52px] leading-[1.15] tracking-normal text-balance break-keep text-dash-heading mb-5">
              숫자 뒤에 남은 질문과 결정을 기록합니다
            </h2>
            <p className="max-w-[700px] text-[15px]/[1.8] md:text-[17px]/[1.8] text-dash-text-secondary">
              어떤 실험을 왜 묶었는지, 실패가 다음 설계를 어떻게 바꿨는지, AI가 실제 전문 업무에서
              어디까지 수행했는지를 근거와 함께 돌아봅니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 mt-8 text-xs text-dash-text-muted">
            <span><strong className="font-mono text-dash-heading">{experimentGroups.length}</strong> question tracks</span>
            <span><strong className="font-mono text-dash-heading">{journalArticles.length}</strong> published notes</span>
            <span><strong className="font-mono text-dash-heading">{timelineEvents.length}</strong> timeline events</span>
          </div>
        </div>
      </section>

      <main className="max-w-[1200px] mx-auto px-4 md:px-6 py-10 md:py-16">
        <div className="inline-flex items-center gap-1 p-1 bg-dash-card border border-dash-border rounded-lg mb-12" aria-label="기록 탐색 방식">
          <button
            onClick={() => changeView('questions')}
            aria-pressed={view === 'questions'}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium transition-colors ${view === 'questions' ? 'bg-dash-card-active text-dash-heading' : 'text-dash-text-muted hover:text-dash-heading'}`}
          >
            <FlaskConical className="w-4 h-4" />
            질문별
          </button>
          <button
            onClick={() => changeView('timeline')}
            aria-pressed={view === 'timeline'}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium transition-colors ${view === 'timeline' ? 'bg-dash-card-active text-dash-heading' : 'text-dash-text-muted hover:text-dash-heading'}`}
          >
            <CalendarDays className="w-4 h-4" />
            타임라인
          </button>
        </div>

        {view === 'questions' ? (
          <div className="space-y-16 md:space-y-20">
            <section>
              <div className="flex items-end justify-between gap-4 mb-6">
                <div>
                  <p className="text-[10px] uppercase text-dash-text-muted mb-2">Featured note</p>
                  <h3 className="font-journal-serif text-xl md:text-2xl text-dash-heading">이번 기록</h3>
                </div>
                <Wrench className="w-5 h-5 text-blue-500" />
              </div>
              <Link
                to={`/notes/${featured.slug}`}
                className="group block border-y border-dash-border py-8 md:py-10 hover:bg-dash-card/40 transition-colors"
              >
                <div className="grid md:grid-cols-[1fr_auto] gap-7 items-end">
                  <div className="max-w-3xl">
                    <span className={`inline-flex border rounded px-2 py-1 text-[10px] font-medium mb-4 ${lensStyles[featured.lens]}`}>
                      {lensLabels[featured.lens]}
                    </span>
                    <h4 className="font-journal-serif text-[28px] md:text-[40px] leading-[1.2] tracking-normal text-balance break-keep text-dash-heading group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors mb-4">
                      {featured.title}
                    </h4>
                    <p className="max-w-[720px] text-[15px]/[1.8] text-dash-text-secondary">{featured.dek}</p>
                  </div>
                  <div className="flex md:flex-col md:items-end gap-3 text-xs text-dash-text-muted">
                    <span className="inline-flex items-center gap-1.5"><Clock3 className="w-3.5 h-3.5" /> {featured.readingMinutes}분</span>
                    <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">읽기 <ArrowRight className="w-3.5 h-3.5" /></span>
                  </div>
                </div>
              </Link>
            </section>

            <section>
              <div className="mb-7">
                <p className="text-[10px] uppercase text-dash-text-muted mb-2">Question tracks</p>
                <h3 className="font-journal-serif text-xl md:text-2xl text-dash-heading">실험을 묶는 질문</h3>
                <p className="text-[13px]/[1.7] text-dash-text-muted mt-3">하나의 설정이 아니라 하나의 의사결정을 기준으로 묶었습니다.</p>
              </div>
              <div className="border-t border-dash-border">
                {experimentGroups.map((group) => {
                  const meta = stateMeta[group.state]
                  const StateIcon = meta.icon
                  const content = (
                    <div className="grid md:grid-cols-[180px_1fr_230px] gap-4 md:gap-7 py-6 md:py-7 border-b border-dash-border group-hover:bg-dash-card/40 transition-colors">
                      <div>
                        <div className={`inline-flex items-center gap-1.5 text-[10px] font-medium mb-2.5 ${meta.className}`}>
                          <StateIcon className="w-3.5 h-3.5" /> {meta.label}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {group.experiments.map((experiment) => (
                            <span key={experiment} className="font-mono text-[10px] text-dash-text-muted">{experiment}</span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-journal-serif text-[18px] md:text-[21px] leading-[1.45] tracking-normal break-keep text-dash-heading mb-3">{group.question}</h4>
                        <p className="text-[13px]/[1.75] text-pretty break-keep text-dash-text-secondary">{group.finding}</p>
                      </div>
                      <p className="text-xs/[1.7] text-pretty break-keep text-dash-text-secondary md:border-l md:border-dash-border md:pl-5">
                        {group.caveat}
                      </p>
                    </div>
                  )
                  return group.articleSlug ? (
                    <Link key={group.id} to={`/notes/${group.articleSlug}`} className="group block">
                      {content}
                    </Link>
                  ) : (
                    <div key={group.id} className="group">{content}</div>
                  )
                })}
              </div>
            </section>

            <section>
              <div className="mb-7">
                <p className="text-[10px] uppercase text-dash-text-muted mb-2">All notes</p>
                <h3 className="font-journal-serif text-xl md:text-2xl text-dash-heading">관점별 기록</h3>
              </div>
              <div className="grid md:grid-cols-2 gap-5">
                {journalArticles.map((article) => (
                  <Link
                    key={article.slug}
                    to={`/notes/${article.slug}`}
                    className="group bg-dash-card border border-dash-border rounded-lg p-6 hover:border-dash-border-active hover:bg-dash-card-hover transition-colors"
                  >
                    <div className="flex items-center justify-between gap-3 mb-4">
                      <span className={`inline-flex border rounded px-2 py-1 text-[10px] font-medium ${lensStyles[article.lens]}`}>
                        {lensLabels[article.lens]}
                      </span>
                      <span className="text-[10px] text-dash-text-faint">{article.period}</span>
                    </div>
                    <h4 className="font-journal-serif text-[21px] md:text-[22px] leading-[1.45] tracking-normal text-pretty break-keep text-dash-heading group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors mb-4">
                      {article.title}
                    </h4>
                    <p className="text-[13px]/[1.75] text-pretty break-keep text-dash-text-secondary mb-6">{article.dek}</p>
                    <div className="flex items-center justify-between text-[10px] text-dash-text-muted">
                      <span>{article.relatedExperiments.join(' · ')}</span>
                      <span className="inline-flex items-center gap-1">{article.readingMinutes}분 <ArrowRight className="w-3 h-3" /></span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          </div>
        ) : (
          <section className="max-w-4xl">
            <div className="mb-10">
              <p className="text-[10px] uppercase text-dash-text-muted mb-2">Chronological record</p>
              <h3 className="font-journal-serif text-[28px] md:text-[32px] leading-[1.35] tracking-normal break-keep text-dash-heading">실패와 결정의 시간순 기록</h3>
              <p className="text-[13px]/[1.75] text-dash-text-secondary mt-3 max-w-2xl">
                최종 결과가 중간 실패를 덮지 않도록, 당시 알았던 사실과 이후의 결론을 분리해 남깁니다.
              </p>
            </div>
            <div className="relative border-l border-dash-border ml-2 md:ml-[132px]">
              {timelineEvents.map((event) => (
                <div key={`${event.date}-${event.title}`} className="relative pl-6 md:pl-8 pb-12 last:pb-0">
                  <div className={`absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full border-2 border-dash-page ${event.kind === 'incident' ? 'bg-rose-500' : event.kind === 'decision' ? 'bg-blue-500' : 'bg-emerald-500'}`} />
                  <time className="block md:absolute md:right-[calc(100%+32px)] md:top-0 md:w-28 md:text-right font-mono text-[11px] text-dash-text-muted mb-2 md:mb-0">
                    {event.date}
                  </time>
                  <div className="flex items-start md:gap-3">
                    <GitCommitHorizontal className="hidden md:block w-4 h-4 text-dash-text-faint mt-0.5 flex-shrink-0" />
                    <div>
                      <h4 className="font-journal-serif text-[17px] md:text-[18px] leading-[1.5] md:leading-[1.45] tracking-normal text-pretty break-keep text-dash-heading mb-3">{event.title}</h4>
                      <p className="text-[13px]/[1.75] text-dash-text-secondary mb-4">{event.description}</p>
                      <div className="flex flex-wrap items-center gap-2">
                        {event.experiments.map((experiment) => (
                          <span key={experiment} className="font-mono text-[10px] text-dash-text-muted bg-dash-card border border-dash-border rounded px-1.5 py-0.5">
                            {experiment}
                          </span>
                        ))}
                        {event.articleSlugs.map((slug) => {
                          const article = journalArticles.find((item) => item.slug === slug)
                          return article ? (
                            <Link
                              key={slug}
                              to={`/notes/${slug}`}
                              className="text-[10px] text-emerald-600 dark:text-emerald-400 hover:underline"
                            >
                              기록: {article.title}
                            </Link>
                          ) : null
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}