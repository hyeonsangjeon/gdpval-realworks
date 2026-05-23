import { CheckCircle, Clock, Sparkles, BookOpen } from 'lucide-react'
import InfoTooltip from './common/InfoTooltip'
import { tooltipTexts } from '../data/tooltipTexts'

interface ScopeBadgeProps {
  scope: 'self_assessed_pre_grading' | 'graded' | 'graded_v1' | 'legacy_demo'
}

export default function ScopeBadge({ scope }: ScopeBadgeProps) {
  if (scope === 'graded_v1') {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gradient-to-r from-fuchsia-500/10 to-violet-500/10 border border-fuchsia-400/30">
        <Sparkles className="w-3.5 h-3.5 text-fuchsia-400" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-fuchsia-300">
          ✨ LLM-Judge Graded (v1.0)
        </span>
      </div>
    )
  }

  if (scope === 'legacy_demo') {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-500/10 border border-zinc-500/30">
        <BookOpen className="w-3.5 h-3.5 text-zinc-400" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
          📚 Legacy Demo
        </span>
      </div>
    )
  }

  if (scope === 'graded') {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30">
        <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
          ✓ LLM-Judge Graded
        </span>
      </div>
    )
  }

  // self_assessed_pre_grading — amber retained per spec 002 D4 (true warning class)
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30">
      <Clock className="w-3.5 h-3.5 text-amber-500" />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">
        ⏰ Awaiting LLM-Judge Grade
      </span>
      <InfoTooltip content={tooltipTexts.badge.selfAssessed} position="bottom" />
    </div>
  )
}
