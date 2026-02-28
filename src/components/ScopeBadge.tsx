import { CheckCircle, Clock } from 'lucide-react'

interface ScopeBadgeProps {
  scope: 'self_assessed_pre_grading' | 'graded'
}

export default function ScopeBadge({ scope }: ScopeBadgeProps) {
  if (scope === 'graded') {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30">
        <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
          ✓ Externally Graded
        </span>
      </div>
    )
  }

  // self_assessed_pre_grading
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30">
      <Clock className="w-3.5 h-3.5 text-amber-500" />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">
        ⏰ Self-Assessed · Pre-Grading
      </span>
    </div>
  )
}
