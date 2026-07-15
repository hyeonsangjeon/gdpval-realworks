import { motion, useReducedMotion } from 'framer-motion'
import type { JournalHero } from '../../data/journal'

const resolveAsset = (src: string) => (
  src.startsWith('http') ? src : `${import.meta.env.BASE_URL}${src.replace(/^\/+/, '')}`
)

function PromptComplexityVisual({ reduceMotion }: { reduceMotion: boolean | null }) {
  const cards = [
    {
      x: 70,
      title: 'exp003 · BASELINE',
      mode: 'BASIC OUTPUT CONTRACT',
      steps: ['CREATE FILE', 'INSPECT INPUT', 'TEXT SUMMARY'],
      success: '211 / 220',
      qa: 'Self-QA 6.18',
      color: '#2563eb',
    },
    {
      x: 450,
      title: 'exp004 · ELICIT',
      mode: 'FIVE MANDATORY STEPS',
      steps: ['1 · RENDER TO PNG', '2 · DISPLAY PNG', '3 · PROGRAM CHECK', '4 · MATCH REQUEST', '5 · FINAL FILE CHECK'],
      success: '200 / 220',
      qa: 'Self-QA 5.87',
      color: '#b45309',
    },
    {
      x: 830,
      title: 'exp005 · HEADLESS',
      mode: 'SAME FIVE STEPS · NEW STEP 2',
      steps: ['1 · RENDER TO PNG', '2 · PILLOW CHECK', '3 · PROGRAM CHECK', '4 · MATCH REQUEST', '5 · FINAL FILE CHECK'],
      success: '199 / 220',
      qa: 'Self-QA 6.16',
      color: '#be123c',
    },
  ]

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

function RuntimeVisual({ reduceMotion }: { reduceMotion: boolean | null }) {
  const markers = [
    { x: 893, y: 176, value: '290', label: 'watchdog' },
    { x: 1000, y: 326, value: '330', label: 'interrupted' },
    { x: 1053, y: 176, value: '350', label: 'step ceiling' },
    { x: 1080, y: 326, value: '360', label: 'job cap' },
  ]

  return (
    <>
      <g opacity="0.45">
        {[120, 280, 440, 600, 760, 920, 1080].map((x) => (
          <line key={x} x1={x} y1="90" x2={x} y2="390" stroke="hsl(var(--dash-border))" strokeWidth="1" />
        ))}
      </g>
      <text x="120" y="72" fill="hsl(var(--dash-text-secondary))" fontSize="18">RUNNING WINDOW</text>
      <line x1="120" y1="250" x2="1080" y2="250" stroke="hsl(var(--dash-border-active))" strokeWidth="4" />
      <line x1="120" y1="250" x2="893" y2="250" stroke="#10b981" strokeWidth="8" />
      <line x1="893" y1="250" x2="1053" y2="250" stroke="#f59e0b" strokeWidth="8" />
      <line x1="1053" y1="250" x2="1080" y2="250" stroke="#f43f5e" strokeWidth="8" />
      <text x="120" y="286" fill="hsl(var(--dash-text-secondary))" fontSize="16">0 min</text>
      {markers.map((marker) => (
        <g key={marker.value}>
          <line x1={marker.x} y1="224" x2={marker.x} y2="276" stroke="hsl(var(--dash-heading))" strokeWidth="2" />
          <circle cx={marker.x} cy="250" r="9" fill="hsl(var(--dash-page))" stroke="hsl(var(--dash-heading))" strokeWidth="3" />
          <text x={marker.x} y={marker.y} fill="hsl(var(--dash-heading))" fontSize="28" textAnchor="middle" fontWeight="700">{marker.value}</text>
          <text x={marker.x} y={marker.y + 25} fill="hsl(var(--dash-text-secondary))" fontSize="14" textAnchor="middle">{marker.label}</text>
        </g>
      ))}
      {reduceMotion ? (
        <line x1="893" x2="893" y1="112" y2="388" stroke="#2563eb" strokeWidth="3" strokeDasharray="7 7" opacity="0.8" />
      ) : (
        <motion.line
          x1="120"
          x2="120"
          y1="112"
          y2="388"
          stroke="#2563eb"
          strokeWidth="3"
          strokeDasharray="7 7"
          initial={{ x: 0, opacity: 0.25 }}
          animate={{ x: [0, 960], opacity: [0.2, 0.9, 0.2] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
        />
      )}
    </>
  )
}

function IntegrityVisual() {
  return (
    <>
      <text x="120" y="72" fill="hsl(var(--dash-text-secondary))" fontSize="18">THE SAME MODEL, A DIFFERENT MEASUREMENT</text>
      <rect x="180" y="126" width="260" height="238" rx="6" fill="hsl(var(--dash-card))" stroke="hsl(var(--dash-border))" />
      <rect x="760" y="160" width="260" height="204" rx="6" fill="hsl(var(--dash-card))" stroke="hsl(var(--dash-border))" />
      <rect x="180" y="126" width="260" height="238" rx="6" fill="#10b981" opacity="0.18" />
      <rect x="760" y="160" width="260" height="204" rx="6" fill="#f59e0b" opacity="0.18" />
      <text x="310" y="222" fill="hsl(var(--dash-heading))" fontSize="56" textAnchor="middle" fontWeight="700">95.9%</text>
      <text x="310" y="262" fill="hsl(var(--dash-text-secondary))" fontSize="18" textAnchor="middle">exp013 · before</text>
      <text x="890" y="238" fill="hsl(var(--dash-heading))" fontSize="56" textAnchor="middle" fontWeight="700">82.3%</text>
      <text x="890" y="278" fill="hsl(var(--dash-text-secondary))" fontSize="18" textAnchor="middle">exp025 · after</text>
      <path d="M480 242 H700" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <path d="M680 228 L704 242 L680 256" fill="none" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <text x="590" y="210" fill="hsl(var(--dash-heading))" fontSize="18" textAnchor="middle">success changed meaning</text>
      <text x="590" y="304" fontSize="15" textAnchor="middle" className="fill-amber-700 dark:fill-amber-400">lower does not automatically mean worse</text>
    </>
  )
}

function PerceptionVisual({ reduceMotion }: { reduceMotion: boolean | null }) {
  const bars = [34, 62, 88, 48, 106, 72, 42, 92, 58, 80, 38]
  return (
    <>
      <text x="120" y="72" fill="hsl(var(--dash-text-secondary))" fontSize="18">FROM FILE ACCESS TO PERCEPTION</text>
      <text x="185" y="140" fill="hsl(var(--dash-heading))" fontSize="22">HEARING</text>
      {bars.map((height, index) => (
        <motion.rect
          key={index}
          x={110 + index * 23}
          y={250 - height / 2}
          width="10"
          height={height}
          rx="5"
          fill="#3b82f6"
          opacity="0.85"
          animate={reduceMotion ? undefined : { scaleY: [0.5, 1, 0.65] }}
          transition={reduceMotion ? undefined : { duration: 1.4 + index * 0.05, repeat: Infinity, repeatType: 'mirror' }}
          style={{ transformOrigin: `${115 + index * 23}px 250px` }}
        />
      ))}
      <path d="M405 250 H535" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <path d="M515 236 L539 250 L515 264" fill="none" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <g>
        <rect x="560" y="146" width="170" height="104" rx="5" fill="hsl(var(--dash-card))" stroke="#f59e0b" strokeWidth="2" />
        <rect x="585" y="270" width="170" height="104" rx="5" fill="hsl(var(--dash-card))" stroke="#f59e0b" strokeWidth="2" />
        <circle cx="610" cy="178" r="12" fill="#f59e0b" opacity="0.65" />
        <path d="M578 232 L622 190 L658 220 L688 182 L716 232 Z" fill="#f59e0b" opacity="0.24" />
        <circle cx="635" cy="300" r="12" fill="#f59e0b" opacity="0.65" />
        <path d="M603 356 L647 314 L683 344 L713 306 L741 356 Z" fill="#f59e0b" opacity="0.24" />
        <text x="657" y="132" fill="hsl(var(--dash-heading))" fontSize="22" textAnchor="middle">VISION</text>
      </g>
      <path d="M790 250 H892" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <path d="M872 236 L896 250 L872 264" fill="none" stroke="hsl(var(--dash-border-active))" strokeWidth="3" />
      <rect x="920" y="130" width="190" height="244" rx="8" fill="hsl(var(--dash-card))" stroke="#10b981" strokeWidth="3" />
      <text x="1015" y="174" fill="hsl(var(--dash-heading))" fontSize="22" textAnchor="middle">SANDBOX</text>
      {['audio', 'video', 'docs', 'data'].map((label, index) => (
        <g key={label}>
          <rect x={946 + (index % 2) * 82} y={204 + Math.floor(index / 2) * 72} width="64" height="48" rx="4" fill="#10b981" opacity="0.14" />
          <text x={978 + (index % 2) * 82} y={234 + Math.floor(index / 2) * 72} fill="hsl(var(--dash-text))" fontSize="14" textAnchor="middle">{label}</text>
        </g>
      ))}
    </>
  )
}

function TaskContrastVisual() {
  return (
    <>
      <text x="120" y="72" fill="hsl(var(--dash-text-secondary))" fontSize="18">SAME OCCUPATION, DIFFERENT EVIDENCE BURDEN</text>
      <rect x="110" y="116" width="440" height="250" rx="8" fill="hsl(var(--dash-card))" stroke="#f43f5e" strokeWidth="2" />
      <rect x="650" y="116" width="440" height="250" rx="8" fill="hsl(var(--dash-card))" stroke="#10b981" strokeWidth="2" />
      <text x="145" y="158" fill="hsl(var(--dash-text-secondary))" fontSize="16">S&amp;P 500 WORKBOOK</text>
      <text x="685" y="158" fill="hsl(var(--dash-text-secondary))" fontSize="16">LATAM FINTECH BRIEFING</text>
      <text x="145" y="246" fontSize="64" fontWeight="700" className="fill-rose-700 dark:fill-rose-400">2/10</text>
      <text x="685" y="246" fontSize="64" fontWeight="700" className="fill-emerald-700 dark:fill-emerald-400">9/10</text>
      <text x="145" y="292" fill="hsl(var(--dash-heading))" fontSize="24">35 / 500 companies</text>
      <text x="685" y="292" fill="hsl(var(--dash-heading))" fontSize="24">PPTX + PDF delivered</text>
      <text x="145" y="328" fill="hsl(var(--dash-text-secondary))" fontSize="15">placeholder market data</text>
      <text x="685" y="328" fill="hsl(var(--dash-text-secondary))" fontSize="15">external grade still pending</text>
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

function MobileVisualSummary({ variant, alt }: { variant: Extract<JournalHero, { kind: 'visual' }>['variant']; alt: string }) {
  if (variant === 'prompt-complexity') {
    return (
      <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-3 py-6 bg-dash-surface border-y border-dash-border">
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">BASELINE → 5-STEP ELICIT → HEADLESS</div>
        <div className="grid grid-cols-3 gap-2">
          {[
            ['Baseline', '기본 계약', '95.9%', 'QA 6.18', 'border-blue-700/70 bg-blue-500/10'],
            ['Elicit', '5단계 검사', '90.9%', 'QA 5.87', 'border-amber-700/70 bg-amber-500/10'],
            ['Headless', 'STEP 2 교체', '90.5%', 'QA 6.16', 'border-rose-700/70 bg-rose-500/10'],
          ].map(([title, mode, completion, qa, style]) => (
            <div key={title} className={`min-w-0 border px-2 py-4 text-center ${style}`}>
              <div className="text-[11px] font-medium text-dash-text-secondary">{title}</div>
              <div className="mt-1 text-[10px] leading-4 text-dash-text-secondary">{mode}</div>
              <div className="mt-3 font-mono text-xl font-semibold text-dash-heading">{completion}</div>
              <div className="mt-2 text-[11px] text-dash-text-secondary">{qa}</div>
            </div>
          ))}
        </div>
        <p className="mt-5 text-center text-xs/[1.7] text-pretty break-keep text-dash-text-secondary">5단계 도입 뒤 완료율은 낮았고, STEP 2 교체 뒤 Self-QA는 baseline 수준으로 돌아왔다.</p>
      </div>
    )
  }

  if (variant === 'runtime') {
    return (
      <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
        <div className="font-mono text-[11px] text-dash-text-secondary mb-8">RUNNING WINDOW</div>
        <div className="relative">
          <div className="absolute left-3 right-3 top-[25px] h-1 bg-gradient-to-r from-emerald-600 via-amber-600 to-rose-600" />
          <div className="relative grid grid-cols-4 gap-2">
            {[
              ['290', 'watchdog'],
              ['330', '중단'],
              ['350', 'step 종료'],
              ['360', 'job cap'],
            ].map(([value, label], index) => (
              <div key={value} className={`text-center ${index % 2 === 1 ? 'pt-14' : ''}`}>
                <div className="font-mono text-xl font-semibold text-dash-heading">{value}</div>
                <div className="mt-3 mx-auto w-3 h-3 rounded-full bg-dash-page border-2 border-dash-heading" />
                <div className="mt-2 text-[11px] text-dash-text-secondary">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (variant === 'integrity') {
    return (
      <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">SUCCESS CHANGED MEANING</div>
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
          <div className="border border-emerald-700/60 bg-emerald-500/10 p-4 text-center">
            <div className="font-mono text-3xl font-semibold text-dash-heading">95.9%</div>
            <div className="mt-2 text-xs text-dash-text-secondary">exp013 · before</div>
          </div>
          <div className="text-xl text-dash-text-muted" aria-hidden="true">→</div>
          <div className="border border-amber-700/60 bg-amber-500/10 p-4 text-center">
            <div className="font-mono text-3xl font-semibold text-dash-heading">82.3%</div>
            <div className="mt-2 text-xs text-dash-text-secondary">exp025 · after</div>
          </div>
        </div>
        <p className="mt-5 text-center text-xs/[1.7] text-dash-text-secondary">낮아진 숫자가 곧 나빠진 모델을 뜻하지는 않는다.</p>
      </div>
    )
  }

  if (variant === 'perception') {
    return (
      <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">FROM FILE ACCESS TO PERCEPTION</div>
        <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-2">
          {[
            ['HEARING', '오디오'],
            ['VISION', '프레임'],
            ['SANDBOX', 'skills'],
          ].map(([title, detail], index) => (
            <div key={title} className="contents">
              {index > 0 && <span className="text-dash-text-muted" aria-hidden="true">→</span>}
              <div className="min-w-0 border border-dash-border bg-dash-card px-2 py-5 text-center">
                <div className="font-mono text-xs font-semibold text-dash-heading">{title}</div>
                <div className="mt-2 text-[11px] text-dash-text-secondary">{detail}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 flex justify-center gap-2 text-[11px] text-dash-text-secondary">
          <span>audio</span><span>·</span><span>video</span><span>·</span><span>docs</span><span>·</span><span>data</span>
        </div>
      </div>
    )
  }

  if (variant === 'task-contrast') {
    return (
      <div role="img" aria-label={alt} className="md:hidden min-h-[220px] px-4 py-6 bg-dash-surface border-y border-dash-border">
        <div className="font-mono text-[11px] text-dash-text-secondary mb-5">SAME OCCUPATION · DIFFERENT BURDEN</div>
        <div className="grid grid-cols-2 gap-3">
          <div className="border border-rose-700/70 bg-rose-500/10 p-4">
            <div className="text-xs text-dash-text-secondary">S&amp;P 500 workbook</div>
            <div className="mt-3 font-mono text-3xl font-semibold text-rose-600 dark:text-rose-400">2/10</div>
            <div className="mt-2 text-xs text-dash-text-secondary">35 / 500 companies</div>
          </div>
          <div className="border border-emerald-700/70 bg-emerald-500/10 p-4">
            <div className="text-xs text-dash-text-secondary">LatAm briefing</div>
            <div className="mt-3 font-mono text-3xl font-semibold text-emerald-700 dark:text-emerald-400">9/10</div>
            <div className="mt-2 text-xs text-dash-text-secondary">PPTX + PDF</div>
          </div>
        </div>
        <p className="mt-5 text-center text-xs/[1.7] text-dash-text-secondary">외부 등급은 두 작업 모두 아직 대기 중이다.</p>
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

export default function NoteHeroVisual({ hero }: { hero: JournalHero }) {
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
      <MobileVisualSummary variant={hero.variant} alt={hero.alt} />
      <div className="hidden md:block overflow-hidden border-y border-dash-border bg-dash-surface">
        <svg viewBox="0 0 1200 460" role="img" aria-label={hero.alt} className="block w-full aspect-[12/5]">
          {hero.variant === 'prompt-complexity' && <PromptComplexityVisual reduceMotion={reduceMotion} />}
          {hero.variant === 'runtime' && <RuntimeVisual reduceMotion={reduceMotion} />}
          {hero.variant === 'integrity' && <IntegrityVisual />}
          {hero.variant === 'perception' && <PerceptionVisual reduceMotion={reduceMotion} />}
          {hero.variant === 'task-contrast' && <TaskContrastVisual />}
          {hero.variant === 'sandbox' && <SandboxVisual reduceMotion={reduceMotion} />}
        </svg>
      </div>
      <figcaption className="mt-3 text-xs/[1.7] text-dash-text-secondary">{hero.caption}</figcaption>
    </figure>
  )
}