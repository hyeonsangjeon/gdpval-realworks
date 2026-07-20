import { motion, useReducedMotion } from 'framer-motion'
import { Link } from 'react-router-dom'
import type { JournalHero } from '../../data/journal'
import { getExperimentHref } from '../../data/journalLinks'
import type { PromptComplexityBenchmarkRow } from '../../lib/promptComplexityBenchmark'
import type { RuntimeNoteBenchmarkSelection } from '../../lib/runtimeNoteBenchmark'
import type { IntegrityNoteSelection } from '../../lib/integrityNoteBenchmark'
import type { PerceptionSelection } from '../../lib/perceptionNoteBenchmark'
import type { SuccessBenchmarkSelection } from '../../lib/successNoteBenchmark'

const resolveAsset = (src: string) => (
  src.startsWith('http') ? src : `${import.meta.env.BASE_URL}${src.replace(/^\/+/, '')}`
)

function PromptComplexityVisual({
  reduceMotion,
  benchmark,
}: {
  reduceMotion: boolean | null
  benchmark: PromptComplexityBenchmarkRow[]
}) {
  const cards = benchmark.map((row, index) => ({
    ...row,
    x: 70 + index * 380,
    title: `${row.shortId} · ${row.condition.toUpperCase()}`,
    success: `${row.successCount} / ${row.totalTasks}`,
    qa: `Self-QA ${row.avgQaScore.toFixed(2)}`,
  }))

  return (
    <>
      <text x="70" y="62" fill="hsl(var(--dash-text-secondary))" fontSize="18">BASELINE → FIVE-STEP ELICIT → HEADLESS ADAPTATION</text>
      <text x="1130" y="62" fill="hsl(var(--dash-text-secondary))" fontSize="14" textAnchor="end">prompt structure from experiment YAML</text>
      {cards.map((card) => (
        <g key={card.title}>
          <rect x={card.x} y="105" width="300" height="280" rx="8" fill="hsl(var(--dash-card))" stroke={card.color} strokeWidth="2" />
          <text x={card.x + 24} y="145" fill="hsl(var(--dash-heading))" fontSize="18" fontWeight="700">{card.title}</text>
          <text x={card.x + 24} y="174" fill="hsl(var(--dash-text-secondary))" fontSize="12">{card.mode}</text>
          {card.steps.map((step, index) => (
            <g key={step}>
              <rect
                x={card.x + 24}
                y={190 + index * 23}
                width="252"
                height="18"
                rx="3"
                fill={card.color}
                opacity={step.includes('PILLOW') || step.includes('DISPLAY') ? 0.26 : 0.1}
              />
              <text x={card.x + 32} y={203 + index * 23} fill="hsl(var(--dash-heading))" fontSize="11">{step}</text>
            </g>
          ))}
          <text x={card.x + 24} y="330" fill="hsl(var(--dash-heading))" fontSize="28" fontWeight="700">{card.success}</text>
          <text x={card.x + 24} y="360" fill="hsl(var(--dash-text-secondary))" fontSize="16">{card.qa}</text>
        </g>
      ))}
      {reduceMotion ? (
        <line x1="70" x2="1130" y1="260" y2="260" stroke="hsl(var(--dash-heading))" strokeWidth="2" opacity="0.35" />
      ) : (
        <motion.line
          x1="70"
          x2="1130"
          y1="188"
          y2="188"
          stroke="hsl(var(--dash-heading))"
          strokeWidth="2"
          strokeDasharray="8 8"
          initial={{ y: 0, opacity: 0.15 }}
          animate={{ y: [0, 110], opacity: [0.15, 0.55, 0.15] }}
          transition={{ duration: 4.5, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
    </>
  )
}

type ReadyRuntimeBenchmark = Extract<RuntimeNoteBenchmarkSelection, { status: 'ready' }>
type ReadyIntegrityBenchmark = Extract<IntegrityNoteSelection, { status: 'ready' }>
type ReadyPerceptionBenchmark = Extract<PerceptionSelection, { status: 'ready' }>
type ReadySuccessBenchmark = Extract<SuccessBenchmarkSelection, { status: 'ready' }>

function RuntimeVisual({
  reduceMotion,
  benchmark,
}: {
  reduceMotion: boolean | null
  benchmark: ReadyRuntimeBenchmark
}) {
  const { currentPolicy, incident } = benchmark
  const scaleX = (minutes: number) => 210 + (minutes / currentPolicy.job_timeout_minutes) * 870
  const incidentStepX = scaleX(incident.policy.step_timeout_minutes)
  const watchdogX = scaleX(currentPolicy.watchdog_minutes)
  const currentStepX = scaleX(currentPolicy.step_timeout_minutes)
  const jobX = scaleX(currentPolicy.job_timeout_minutes)

  return (
    <>
      <text x="90" y="64" fill="hsl(var(--dash-text-secondary))" fontSize="18">INCIDENT → POLICY CHANGE</text>
      <text x="90" y="142" fill="hsl(var(--dash-heading))" fontSize="16" fontWeight="700">MAY 18 · INCIDENT</text>
      <text x="90" y="166" fill="hsl(var(--dash-text-secondary))" fontSize="13">Resume Round watchdog absent</text>
      <line x1="210" y1="205" x2={jobX} y2="205" stroke="hsl(var(--dash-border-active))" strokeWidth="4" />
      <line x1="210" y1="205" x2={incidentStepX} y2="205" stroke="#e11d48" strokeWidth="8" />
      <line x1={incidentStepX} y1="178" x2={incidentStepX} y2="232" stroke="#e11d48" strokeWidth="3" />
      <circle cx={incidentStepX} cy="205" r="9" fill="hsl(var(--dash-page))" stroke="#e11d48" strokeWidth="3" />
      <text x={incidentStepX} y="154" fill="hsl(var(--dash-heading))" fontSize="27" textAnchor="middle" fontWeight="700">~{incident.approx_minute}</text>
      <text x={incidentStepX - 12} y="258" fill="hsl(var(--dash-text-secondary))" fontSize="14" textAnchor="end">{incident.event} · {incident.policy.step_timeout_minutes} step hard stop</text>
      <text x={jobX + 10} y="258" fill="hsl(var(--dash-text-secondary))" fontSize="13" textAnchor="start">{incident.policy.job_timeout_minutes} job cap</text>

      <text x="90" y="322" fill="hsl(var(--dash-heading))" fontSize="16" fontWeight="700">AFTER MAY 20 FIX · CONDITION A</text>
      <text x="90" y="346" fill="hsl(var(--dash-text-secondary))" fontSize="13">Resume Round watchdog enabled · step widened</text>
      <line x1="210" y1="382" x2={jobX} y2="382" stroke="hsl(var(--dash-border-active))" strokeWidth="4" />
      <line x1="210" y1="382" x2={watchdogX} y2="382" stroke="#10b981" strokeWidth="8" />
      <line x1={watchdogX} y1="382" x2={currentStepX} y2="382" stroke="#f59e0b" strokeWidth="8" />
      <line x1={currentStepX} y1="382" x2={jobX} y2="382" stroke="#e11d48" strokeWidth="8" />
      {[
        { x: watchdogX, textX: watchdogX, value: currentPolicy.watchdog_minutes, label: 'watchdog', anchor: 'middle' as const },
        { x: currentStepX, textX: currentStepX - 10, value: currentPolicy.step_timeout_minutes, label: 'step ceiling', anchor: 'end' as const },
        { x: jobX, textX: jobX + 10, value: currentPolicy.job_timeout_minutes, label: 'job cap', anchor: 'start' as const },
      ].map((marker) => (
        <g key={marker.label}>
          <circle cx={marker.x} cy="382" r="8" fill="hsl(var(--dash-page))" stroke="hsl(var(--dash-heading))" strokeWidth="3" />
          <text x={marker.textX} y="367" fill="hsl(var(--dash-heading))" fontSize="20" textAnchor={marker.anchor} fontWeight="700">{marker.value}</text>
          <text x={marker.textX} y="420" fill="hsl(var(--dash-text-secondary))" fontSize="13" textAnchor={marker.anchor}>{marker.label}</text>
        </g>
      ))}
      {reduceMotion ? (
        <circle cx={watchdogX} cy="382" r="13" fill="none" stroke="#2563eb" strokeWidth="2" opacity="0.7" />
      ) : (
        <motion.circle
          cx="210"
          cy="382"
          r="7"
          stroke="#2563eb"
          fill="#2563eb"
          initial={{ x: 0, opacity: 0.25 }}
          animate={{ x: [0, watchdogX - 210], opacity: [0.2, 0.9, 0.2] }}
          transition={{ duration: 4.5, repeat: Infinity, ease: 'linear' }}
        />
      )}
    </>
  )
}

function IntegrityVisual({ benchmark }: { benchmark: ReadyIntegrityBenchmark }) {
  const { before, after, observedGapPctPoints } = benchmark
  return (
    <>
      <text x="90" y="62" fill="hsl(var(--dash-text-secondary))" fontSize="18">OBSERVED GAP · MEASUREMENT RULE CHANGED</text>
      <rect x="100" y="112" width="330" height="260" rx="8" fill="hsl(var(--dash-card))" stroke="#059669" strokeWidth="2" />
      <text x="126" y="150" fill="hsl(var(--dash-text-secondary))" fontSize="14">{before.shortId} · PRE-FIX SNAPSHOT</text>
      <text x="265" y="230" fill="hsl(var(--dash-heading))" fontSize="58" textAnchor="middle" fontWeight="700">{before.successRatePct.toFixed(1)}%</text>
      <text x="265" y="270" fill="hsl(var(--dash-heading))" fontSize="20" textAnchor="middle">{before.successCount} / {before.totalTasks} success</text>
      <text x="265" y="314" fill="hsl(var(--dash-text-secondary))" fontSize="14" textAnchor="middle">determined QA fail could remain success</text>
      <text x="265" y="340" fill="hsl(var(--dash-text-secondary))" fontSize="13" textAnchor="middle">report date · {before.date}</text>

      <rect x="770" y="112" width="330" height="260" rx="8" fill="hsl(var(--dash-card))" stroke="#b45309" strokeWidth="2" />
      <text x="796" y="150" fill="hsl(var(--dash-text-secondary))" fontSize="14">{after.shortId} · POST-FIX SNAPSHOT</text>
      <text x="935" y="230" fill="hsl(var(--dash-heading))" fontSize="58" textAnchor="middle" fontWeight="700">{after.successRatePct.toFixed(1)}%</text>
      <text x="935" y="270" fill="hsl(var(--dash-heading))" fontSize="20" textAnchor="middle">{after.successCount} / {after.totalTasks} success</text>
      <text x="935" y="314" fill="hsl(var(--dash-text-secondary))" fontSize="14" textAnchor="middle">determined QA fail → qa_failed</text>
      <text x="935" y="340" fill="hsl(var(--dash-text-secondary))" fontSize="13" textAnchor="middle">report date · {after.date}</text>

      <path d="M458 235 H742" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <path d="M722 221 L746 235 L722 249" fill="none" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <text x="600" y="198" fill="hsl(var(--dash-heading))" fontSize="24" textAnchor="middle" fontWeight="700">{observedGapPctPoints.toFixed(1)}%p</text>
      <text x="600" y="274" fill="hsl(var(--dash-text-secondary))" fontSize="15" textAnchor="middle">observed gap</text>
      <text x="600" y="302" fontSize="14" textAnchor="middle" className="fill-amber-700 dark:fill-amber-400">not a causal estimate</text>
    </>
  )
}

function PerceptionVisual({
  reduceMotion,
  benchmark,
}: {
  reduceMotion: boolean | null
  benchmark: ReadyPerceptionBenchmark
}) {
  const stages = [
    { row: benchmark.exp011, x: 55, title: 'PACKAGES', detail: 'package notice · subprocess', color: '#059669' },
    { row: benchmark.exp012, x: 450, title: 'CONDITIONAL AUDIO', detail: benchmark.architecture.exp012.preprocessors[0].trigger, color: '#2563eb' },
    { row: benchmark.exp026, x: 845, title: 'AUDIO + VIDEO', detail: `sandbox · max ${benchmark.architecture.exp026.max_skills} skills`, color: '#b45309' },
  ]
  return (
    <>
      <text x="55" y="58" fill="hsl(var(--dash-text-secondary))" fontSize="18">CONFIGURED PATHS · OBSERVED INFORMATION ROW</text>
      <text x="1145" y="58" fill="hsl(var(--dash-text-secondary))" fontSize="13" textAnchor="end">architecture change ≠ causal effect</text>
      {stages.map((stage) => (
        <g key={stage.row.shortId}>
          <rect x={stage.x} y="100" width="300" height="286" rx="8" fill="hsl(var(--dash-card))" stroke={stage.color} strokeWidth="2" />
          <text x={stage.x + 24} y="140" fill="hsl(var(--dash-text-secondary))" fontSize="14">{stage.row.shortId} · {stage.row.date}</text>
          <text x={stage.x + 24} y="180" fill="hsl(var(--dash-heading))" fontSize="19" fontWeight="700">{stage.title}</text>
          <text x={stage.x + 24} y="208" fill="hsl(var(--dash-text-secondary))" fontSize="13">{stage.detail}</text>
          <text x={stage.x + 24} y="260" fill="hsl(var(--dash-heading))" fontSize="44" fontWeight="700">{stage.row.information.success} / {stage.row.information.total}</text>
          <text x={stage.x + 24} y="292" fill="hsl(var(--dash-text-secondary))" fontSize="14">Information success</text>
          <line x1={stage.x + 24} x2={stage.x + 276} y1="316" y2="316" stroke="hsl(var(--dash-border))" />
          <text x={stage.x + 24} y="348" fill="hsl(var(--dash-heading))" fontSize="17">Self-QA {stage.row.information.avgQaScore.toFixed(2)}</text>
          <text x={stage.x + 276} y="348" fill="hsl(var(--dash-text-secondary))" fontSize="14" textAnchor="end">{stage.row.perceptionPaths.length} path{stage.row.perceptionPaths.length === 1 ? '' : 's'}</text>
        </g>
      ))}
      {[355, 750].map((startX) => (
        <g key={startX}>
          <path d={`M${startX + 12} 242 H${startX + 78}`} stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
          <path d={`M${startX + 60} 230 L${startX + 80} 242 L${startX + 60} 254`} fill="none" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
          {reduceMotion ? (
            <circle cx={startX + 32} cy="242" r="5" fill="#2563eb" />
          ) : (
            <motion.circle
              cx={startX + 18}
              cy="242"
              r="5"
              fill="#2563eb"
              animate={{ x: [0, 42], opacity: [0.25, 1, 0.25] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}
        </g>
      ))}
    </>
  )
}

function TaskContrastVisual({ benchmark }: { benchmark: ReadySuccessBenchmark }) {
  const { workbook, briefing } = benchmark
  const cards = [
    {
      x: 70,
      title: 'S&P 500 WORKBOOK',
      color: '#e11d48',
      rows: [
        ['TASK STATUS', workbook.observed.status],
        ['INTEGRITY', `${workbook.inspection.sheet_count} sheets · open`],
        ['FIDELITY', `${workbook.inspection.company_rows} / ${workbook.request.expected_company_count} companies`],
        ['SELF-QA', `${workbook.observed.self_qa_score} / 10`],
      ],
    },
    {
      x: 660,
      title: 'LATAM FINTECH BRIEFING',
      color: '#059669',
      rows: [
        ['TASK STATUS', briefing.observed.status],
        ['INTEGRITY', `${briefing.inspection.slide_count} slides · ${briefing.inspection.page_count} pages`],
        ['FIDELITY', 'structure observed'],
        ['SELF-QA', `${briefing.observed.self_qa_score} / 10`],
      ],
    },
  ]
  return (
    <>
      <text x="70" y="54" fill="hsl(var(--dash-text-secondary))" fontSize="18">ONE STATUS CANNOT CARRY FOUR QUESTIONS</text>
      <text x="1130" y="54" fill="hsl(var(--dash-text-secondary))" fontSize="13" textAnchor="end">same occupation · different evidence burden</text>
      {cards.map((card) => (
        <g key={card.title}>
          <rect x={card.x} y="86" width="470" height="300" rx="8" fill="hsl(var(--dash-card))" stroke={card.color} strokeWidth="2" />
          <text x={card.x + 24} y="126" fill="hsl(var(--dash-heading))" fontSize="19" fontWeight="700">{card.title}</text>
          {card.rows.map(([label, value], index) => (
            <g key={label}>
              <text x={card.x + 24} y={174 + index * 48} fill="hsl(var(--dash-text-secondary))" fontSize="12">{label}</text>
              <text x={card.x + 174} y={174 + index * 48} fill="hsl(var(--dash-heading))" fontSize={index === 2 ? 18 : 20} fontWeight={index === 3 ? 700 : 500}>{value}</text>
              {index < card.rows.length - 1 && <line x1={card.x + 24} x2={card.x + 446} y1={190 + index * 48} y2={190 + index * 48} stroke="hsl(var(--dash-border))" />}
            </g>
          ))}
        </g>
      ))}
      <rect x="420" y="406" width="360" height="34" rx="4" fill="#b45309" opacity="0.12" />
      <text x="600" y="428" fill="hsl(var(--dash-heading))" fontSize="14" textAnchor="middle">EXTERNAL QUALITY · UNKNOWN</text>
    </>
  )
}

function SandboxVisual({ reduceMotion }: { reduceMotion: boolean | null }) {
  const skills = ['audio', 'video', 'document', 'image', 'data']
  return (
    <>
      <text x="120" y="72" fill="hsl(var(--dash-text-secondary))" fontSize="18">FROM A PROCESS TO A CONTROLLED WORKSPACE</text>
      <rect x="100" y="142" width="310" height="210" rx="6" fill="hsl(var(--dash-card))" stroke="hsl(var(--dash-border-active))" strokeWidth="2" />
      <text x="255" y="188" fill="hsl(var(--dash-heading))" fontSize="26" textAnchor="middle">subprocess</text>
      {['deps?', 'paths?', 'cleanup?'].map((label, index) => (
        <text key={label} x="255" y={236 + index * 38} fontSize="18" textAnchor="middle" className="fill-amber-700 dark:fill-amber-400">{label}</text>
      ))}
      <path d="M450 247 H620" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <path d="M600 233 L624 247 L600 261" fill="none" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      {reduceMotion ? (
        <circle cx="600" cy="247" r="8" fill="#2563eb" />
      ) : (
        <motion.circle
          cx="470"
          cy="247"
          r="8"
          fill="#2563eb"
          animate={{ x: [0, 130], opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
      <rect x="660" y="110" width="440" height="280" rx="10" fill="hsl(var(--dash-card))" stroke="#10b981" strokeWidth="3" />
      <path d="M660 166 H1100" stroke="#10b981" strokeWidth="2" opacity="0.5" />
      <circle cx="690" cy="138" r="7" fill="#f43f5e" />
      <circle cx="716" cy="138" r="7" fill="#f59e0b" />
      <circle cx="742" cy="138" r="7" fill="#10b981" />
      <text x="880" y="145" fill="hsl(var(--dash-heading))" fontSize="22" textAnchor="middle">Docker sandbox</text>
      {skills.map((skill, index) => (
        <g key={skill}>
          <rect x={696 + (index % 3) * 126} y={198 + Math.floor(index / 3) * 76} width="106" height="52" rx="5" fill="#10b981" opacity="0.14" />
          <text x={749 + (index % 3) * 126} y={231 + Math.floor(index / 3) * 76} fill="hsl(var(--dash-text))" fontSize="15" textAnchor="middle">{skill}</text>
        </g>
      ))}
      <rect x="948" y="274" width="106" height="52" rx="5" fill="#3b82f6" opacity="0.14" />
      <text x="1001" y="307" fill="hsl(var(--dash-text))" fontSize="15" textAnchor="middle">validation</text>
    </>
  )
}

function MobileVisualSummary({
  variant,
  alt,
  promptBenchmark,
  runtimeBenchmark,
  integrityBenchmark,
  perceptionBenchmark,
  successBenchmark,
}: {
  variant: Extract<JournalHero, { kind: 'visual' }>['variant']
  alt: string
  promptBenchmark?: PromptComplexityBenchmarkRow[]
  runtimeBenchmark?: ReadyRuntimeBenchmark
  integrityBenchmark?: ReadyIntegrityBenchmark
  perceptionBenchmark?: ReadyPerceptionBenchmark
  successBenchmark?: ReadySuccessBenchmark
}) {
  if (variant === 'prompt-complexity') {
    if (!promptBenchmark) return null
    const styles = [
      'border-blue-700/70 bg-blue-500/10',
      'border-amber-700/70 bg-amber-500/10',
      'border-rose-700/70 bg-rose-500/10',
    ]
    return (
      <div className="md:hidden min-h-[220px] px-3 py-6 bg-dash-surface border-y border-dash-border">
        <span className="sr-only">{alt}</span>
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">BASELINE → 5-STEP ELICIT → HEADLESS</div>
        <nav className="grid grid-cols-3 gap-2" aria-label="프롬프트 전략별 실험 상세">
          {promptBenchmark.map((row, index) => (
            <Link
              key={row.shortId}
              to={getExperimentHref(row.shortId)}
              className={`min-w-0 border px-2 py-4 text-center ${styles[index]}`}
              aria-label={`${row.shortId} ${row.condition} 실험 상세 보기`}
            >
              <div className="text-[11px] font-medium text-dash-text-secondary">{row.condition}</div>
              <div className="mt-1 text-[10px] leading-4 text-dash-text-secondary">{row.mobileMode}</div>
              <div className="mt-3 font-mono text-xl font-semibold text-dash-heading">{row.successRatePct.toFixed(1)}%</div>
              <div className="mt-2 text-[11px] text-dash-text-secondary">QA {row.avgQaScore.toFixed(2)}</div>
            </Link>
          ))}
        </nav>
        <p className="mt-5 text-center text-xs/[1.7] text-pretty break-keep text-dash-text-secondary">5단계 도입 뒤 완료율은 낮았고, STEP 2 교체 뒤 Self-QA는 baseline 수준으로 돌아왔다.</p>
      </div>
    )
  }

  if (variant === 'runtime') {
    if (!runtimeBenchmark) return null
    const { currentPolicy, incident } = runtimeBenchmark
    return (
      <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">INCIDENT → POLICY CHANGE</div>
        <div className="border-l-2 border-rose-600 pl-4 py-2">
          <div className="font-mono text-[10px] text-rose-700 dark:text-rose-400">MAY 18 · INCIDENT</div>
          <div className="mt-2 flex items-baseline gap-2"><span className="font-mono text-2xl font-semibold text-dash-heading">~{incident.approx_minute}</span><span className="text-xs text-dash-text-secondary">{incident.event} · {incident.policy.step_timeout_minutes}분 hard stop</span></div>
          <div className="mt-1 text-[11px] text-dash-text-muted">Resume Round watchdog 없음 · job cap {incident.policy.job_timeout_minutes}분</div>
        </div>
        <div className="mt-5 border-l-2 border-emerald-600 pl-4 py-2">
          <div className="font-mono text-[10px] text-emerald-700 dark:text-emerald-400">AFTER MAY 20 FIX · CONDITION A</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            {[
              [String(currentPolicy.watchdog_minutes), 'watchdog'],
              [String(currentPolicy.step_timeout_minutes), 'step'],
              [String(currentPolicy.job_timeout_minutes), 'job'],
            ].map(([value, label]) => (
              <div key={label}>
                <div className="font-mono text-xl font-semibold text-dash-heading">{value}</div>
                <div className="mt-1 text-[11px] text-dash-text-secondary">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (variant === 'integrity') {
    if (!integrityBenchmark) return null
    const { before, after, observedGapPctPoints } = integrityBenchmark
    return (
      <div className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
        <span className="sr-only">{alt}</span>
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">SUCCESS CHANGED MEANING</div>
        <nav className="grid grid-cols-[1fr_auto_1fr] items-center gap-3" aria-label="무결성 수정 전후 실험 상세">
          <Link to={getExperimentHref(before.shortId)} className="border border-emerald-700/60 bg-emerald-500/10 p-4 text-center" aria-label={`${before.shortId} 실험 상세 보기`}>
            <div className="font-mono text-3xl font-semibold text-dash-heading">{before.successRatePct.toFixed(1)}%</div>
            <div className="mt-2 text-xs text-dash-text-secondary">{before.shortId} · {before.successCount}/{before.totalTasks}</div>
          </Link>
          <div className="text-center" aria-hidden="true">
            <div className="font-mono text-sm font-semibold text-dash-heading">{observedGapPctPoints.toFixed(1)}%p</div>
            <div className="mt-1 text-lg text-dash-text-muted">→</div>
          </div>
          <Link to={getExperimentHref(after.shortId)} className="border border-amber-700/60 bg-amber-500/10 p-4 text-center" aria-label={`${after.shortId} 실험 상세 보기`}>
            <div className="font-mono text-3xl font-semibold text-dash-heading">{after.successRatePct.toFixed(1)}%</div>
            <div className="mt-2 text-xs text-dash-text-secondary">{after.shortId} · {after.successCount}/{after.totalTasks}</div>
          </Link>
        </nav>
        <p className="mt-5 text-center text-xs/[1.7] text-dash-text-secondary">관측 차이이며, 수정의 인과 효과 추정치가 아니다.</p>
      </div>
    )
  }

  if (variant === 'perception') {
    if (!perceptionBenchmark) return null
    const stageLabels = ['packages', 'audio*', 'audio+video']
    return (
      <div className="md:hidden min-h-[220px] px-3 py-6 bg-dash-surface border-y border-dash-border">
        <span className="sr-only">{alt}</span>
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">CONFIGURED PATHS · OBSERVED ROW</div>
        <nav className="grid grid-cols-3 gap-2" aria-label="perception 단계별 실험 상세">
          {perceptionBenchmark.rows.map((row, index) => (
            <Link key={row.shortId} to={getExperimentHref(row.shortId)} className="min-w-0 border border-dash-border bg-dash-card px-2 py-4 text-center" aria-label={`${row.shortId} 실험 상세 보기`}>
              <div className="font-mono text-xs font-semibold text-dash-heading">{row.shortId}</div>
              <div className="mt-1 min-h-8 text-[10px]/4 text-dash-text-secondary break-words">{stageLabels[index]}</div>
              <div className="mt-3 font-mono text-xl font-semibold text-dash-heading">{row.information.success}/{row.information.total}</div>
              <div className="mt-2 text-[10px]/4 text-dash-text-secondary">QA {row.information.avgQaScore.toFixed(2)} · {row.perceptionPaths.length} path</div>
            </Link>
          ))}
        </nav>
        <p className="mt-5 text-center text-xs/[1.7] text-dash-text-secondary">configured path 수와 Information success는 인과 관계가 아니다.</p>
      </div>
    )
  }

  if (variant === 'task-contrast') {
    if (!successBenchmark) return null
    const { workbook, briefing } = successBenchmark
    return (
      <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">FOUR LAYERS · TWO TASKS</div>
        <div className="grid grid-cols-2 gap-3">
          <div className="border border-rose-700/70 bg-rose-500/10 p-4">
            <div className="text-xs text-dash-text-secondary">S&amp;P 500 workbook</div>
            <div className="mt-3 font-mono text-lg font-semibold text-rose-600 dark:text-rose-400">{workbook.observed.status}</div>
            <div className="mt-3 text-[11px]/[1.7] text-dash-text-secondary">open · {workbook.inspection.sheet_count} sheets<br />{workbook.inspection.company_rows}/{workbook.request.expected_company_count} companies<br />Self-QA {workbook.observed.self_qa_score}/10</div>
          </div>
          <div className="border border-emerald-700/70 bg-emerald-500/10 p-4">
            <div className="text-xs text-dash-text-secondary">LatAm briefing</div>
            <div className="mt-3 font-mono text-lg font-semibold text-emerald-700 dark:text-emerald-400">{briefing.observed.status}</div>
            <div className="mt-3 text-[11px]/[1.7] text-dash-text-secondary">PPTX {briefing.inspection.slide_count} · PDF {briefing.inspection.page_count}<br />structure observed<br />Self-QA {briefing.observed.self_qa_score}/10</div>
          </div>
        </div>
        <p className="mt-5 text-center text-xs/[1.7] text-dash-text-secondary">external quality · unknown</p>
      </div>
    )
  }

  return (
    <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
      <div className="font-mono text-[11px] text-dash-text-secondary mb-5">A CONTROLLED WORKSPACE</div>
      <div className="grid grid-cols-[0.8fr_auto_1.2fr] items-center gap-3">
        <div className="border border-dash-border bg-dash-card p-4 text-center">
          <div className="font-mono text-sm font-semibold text-dash-heading">subprocess</div>
          <div className="mt-3 text-[11px]/[1.7] text-amber-700 dark:text-amber-400">deps?<br />paths?<br />cleanup?</div>
        </div>
        <div className="text-xl text-dash-text-muted" aria-hidden="true">→</div>
        <div className="border border-emerald-700/70 bg-emerald-500/10 p-4">
          <div className="font-mono text-sm font-semibold text-dash-heading">Docker sandbox</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-center text-[11px] text-dash-text-secondary">
            {['audio', 'video', 'document', 'data', 'image', 'validation'].map((label) => (
              <span key={label} className="bg-dash-card px-1 py-1.5">{label}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function NoteHeroVisual({
  hero,
  promptBenchmark,
  runtimeBenchmark,
  integrityBenchmark,
  perceptionBenchmark,
  successBenchmark,
}: {
  hero: JournalHero
  promptBenchmark?: PromptComplexityBenchmarkRow[]
  runtimeBenchmark?: ReadyRuntimeBenchmark
  integrityBenchmark?: ReadyIntegrityBenchmark
  perceptionBenchmark?: ReadyPerceptionBenchmark
  successBenchmark?: ReadySuccessBenchmark
}) {
  const reduceMotion = useReducedMotion()

  if (hero.kind === 'video') {
    return (
      <figure className="max-w-[1080px] mx-auto px-4 md:px-6 py-8 md:py-10">
        <video
          className="w-full aspect-video object-cover bg-black border-y border-dash-border"
          src={resolveAsset(hero.src)}
          poster={hero.poster ? resolveAsset(hero.poster) : undefined}
          aria-label={hero.alt}
          autoPlay={!reduceMotion}
          controls
          loop
          muted
          playsInline
          preload="metadata"
        >
          {hero.captionsSrc && <track kind="captions" src={resolveAsset(hero.captionsSrc)} srcLang="ko" label="한국어" />}
        </video>
        <figcaption className="mt-3 text-xs/[1.7] text-dash-text-secondary">{hero.caption}</figcaption>
      </figure>
    )
  }

  return (
    <figure className="max-w-[1080px] mx-auto px-4 md:px-6 py-8 md:py-10">
      <MobileVisualSummary variant={hero.variant} alt={hero.alt} promptBenchmark={promptBenchmark} runtimeBenchmark={runtimeBenchmark} integrityBenchmark={integrityBenchmark} perceptionBenchmark={perceptionBenchmark} successBenchmark={successBenchmark} />
      <div className="hidden md:block overflow-hidden border-y border-dash-border bg-dash-surface">
        <svg viewBox="0 0 1200 460" role="img" aria-label={hero.alt} className="block w-full aspect-[12/5]">
          {hero.variant === 'prompt-complexity' && promptBenchmark && (
            <PromptComplexityVisual reduceMotion={reduceMotion} benchmark={promptBenchmark} />
          )}
          {hero.variant === 'runtime' && runtimeBenchmark && <RuntimeVisual reduceMotion={reduceMotion} benchmark={runtimeBenchmark} />}
          {hero.variant === 'integrity' && integrityBenchmark && <IntegrityVisual benchmark={integrityBenchmark} />}
          {hero.variant === 'perception' && perceptionBenchmark && <PerceptionVisual reduceMotion={reduceMotion} benchmark={perceptionBenchmark} />}
          {hero.variant === 'task-contrast' && successBenchmark && <TaskContrastVisual benchmark={successBenchmark} />}
          {hero.variant === 'sandbox' && <SandboxVisual reduceMotion={reduceMotion} />}
        </svg>
      </div>
      <figcaption className="mt-3 text-xs/[1.7] text-dash-text-secondary">{hero.caption}</figcaption>
    </figure>
  )
}