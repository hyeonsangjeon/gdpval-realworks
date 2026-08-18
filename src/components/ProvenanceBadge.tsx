import { ShieldAlert } from 'lucide-react'
import {
  hasUnverifiedRouteProvenance,
  UNVERIFIED_PROVENANCE_DESCRIPTION,
  UNVERIFIED_PROVENANCE_LABEL,
} from '../lib/gradeProvenance.js'

interface ProvenanceBadgeProps {
  /** `source_azure_ai_provenance_status` as carried by the grade projection. */
  status: string | null | undefined
  /** `9px` matches the dashboard grade cards; `10px` matches the grades list. */
  size?: 'xs' | 'sm'
}

/**
 * Marks a grade whose source inference run has no verifiable route provenance.
 * Renders nothing for every other status, including the `null` that grades
 * predating the field carry — see `src/lib/gradeProvenance.js`.
 */
export default function ProvenanceBadge({
  status,
  size = 'sm',
}: ProvenanceBadgeProps) {
  if (!hasUnverifiedRouteProvenance(status)) return null

  const text = size === 'xs' ? 'text-[9px]' : 'text-[10px]'
  const icon = size === 'xs' ? 'w-2.5 h-2.5' : 'w-3 h-3'

  return (
    <span
      className={
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-amber-500/10 ' +
        `border border-amber-500/30 ${text} font-bold uppercase tracking-wider ` +
        // amber-700 in light keeps this ≥4.5:1 on the amber-500/10 fill; the
        // 10px bold text is too small to qualify for the large-text exemption.
        'text-amber-700 dark:text-amber-400'
      }
      title={UNVERIFIED_PROVENANCE_DESCRIPTION}
    >
      <ShieldAlert className={icon} />
      {UNVERIFIED_PROVENANCE_LABEL}
    </span>
  )
}
