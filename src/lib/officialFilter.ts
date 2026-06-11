/**
 * officialFilter — dashboard display filter for demo / smoke entries.
 *
 * Phase 1 (conservative cleanup): hide obvious non-experiment cards — the
 * legacy demo (`dummy_gpt5_baseline`) and smoke/test runs (`exp99x` namespace,
 * e.g. `exp998_smoke_baseline_sample` grades and the `exp999` "Smoke Baseline"
 * report) — from the DEFAULT view. `?debug=1` restores them (see Dashboard).
 *
 * This is a DISPLAY filter only: the underlying grade/report JSON is never
 * mutated, so the effect is fully reversible (toggle the query param).
 *
 * exp003 (the real experiment, possibly duplicated across judges) is
 * intentionally NOT matched here — its de-duplication is deferred to phase 2.
 */
import type { GradeResult } from '../hooks/useGrades'
import type { ExperimentEntry } from '../types/report'

/**
 * Smoke / test identifier. `exp99x` is the reserved smoke namespace
 * (exp998 grade ids, exp999 report short_id); also catch any id/name that
 * literally contains "smoke". Never matches official ids exp003–exp025.
 */
export function isSmokeId(s: string | null | undefined): boolean {
  if (!s) return false
  return /(^|[_-])exp99\d/i.test(s) || /smoke/i.test(s)
}

/** Legacy demonstration grade (e.g. `dummy_gpt5_baseline`) — not a real run. */
export function isDemoGrade(
  g: Pick<GradeResult, 'is_dummy' | 'grade_status'>,
): boolean {
  return g.is_dummy === true || g.grade_status === 'legacy_dummy'
}

/**
 * True when a grade card should be hidden from the default (non-debug) view.
 * exp003 grades never match (neither demo nor smoke), so they always show.
 */
export function isHiddenGrade(g: GradeResult): boolean {
  return isDemoGrade(g) || isSmokeId(g.experiment_id) || isSmokeId(g.id)
}

/**
 * True when an experiment (inference report) should be hidden from the default
 * view — currently only smoke/test runs (the `exp999` "Smoke Baseline").
 */
export function isHiddenExperiment(
  e: Pick<ExperimentEntry, 'short_id' | 'experiment_name'>,
): boolean {
  return isSmokeId(e.short_id) || isSmokeId(e.experiment_name)
}
