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
 * Phase 2 extends this: superseded / partial exp003 cards (old `__<sha>__v*`
 * naming + the 10-task `_tight` subset) are also hidden by default, while the
 * two curated clean-220 runs are pinned OFFICIAL (allowlist) and never hidden.
 */
import type { GradeResult } from '../hooks/useGrades'
import type { ExperimentEntry } from '../types/report'
import {
  isHiddenDiagnosticExperimentId,
  isHiddenOfficialExperiment,
  isSmokeExperimentId,
  OFFICIAL_TASK_COUNT,
} from './officialExperimentScope.js'

export { OFFICIAL_TASK_COUNT }

/**
 * Smoke / test identifier. `exp99x` is the reserved smoke namespace
 * (exp998 grade ids, exp999 report short_id); also catch any id/name that
 * literally contains "smoke". Never matches official ids exp003–exp025.
 */
export function isSmokeId(s: string | null | undefined): boolean {
  return isSmokeExperimentId(s)
}

/** Legacy demonstration grade (e.g. `dummy_gpt5_baseline`) — not a real run. */
export function isDemoGrade(
  g: Pick<GradeResult, 'is_dummy' | 'grade_status'>,
): boolean {
  return g.is_dummy === true || g.grade_status === 'legacy_dummy'
}

/**
 * Curated OFFICIAL grade ids (phase 2). "Official" is a hand-picked status,
 * NOT a pattern — when a new official run is promoted, add its id here.
 * These are pinned visible (badged) and never hidden by any rule.
 */
export const OFFICIAL_GRADE_IDS: ReadonlySet<string> = new Set([
  // clean gpt-5.4 judge, 220 tasks — final baseline
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools',
  // clean gpt-5.4-mini judge, 220 tasks — comparison baseline
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini',
])

/** Curated official baseline (gets the OFFICIAL badge; never hidden). */
export function isOfficialGrade(g: Pick<GradeResult, 'id'>): boolean {
  return OFFICIAL_GRADE_IDS.has(g.id)
}

/**
 * Superseded / partial exp003 grade (phase 2): the old 4-tuple naming
 * `…__<7-hex-sha>__v<n>` (e.g. `__11e7900__v1`, incl. `__v2sm` backfills) or
 * the 10-task `_tight` subset. Verified NOT to match the curated official ids
 * (they use `…__rubric_v2_tools[_mini]` — no sha, not ending in `_tight`);
 * `isHiddenGrade` also guards official explicitly (reverse protection).
 */
export function isLegacyExp003(g: Pick<GradeResult, 'id'>): boolean {
  return /__[0-9a-f]{7}__v\d/i.test(g.id) || g.id.endsWith('_tight')
}

/**
 * True when a grade card should be hidden from the default (non-debug) view:
 * legacy demo, smoke/test run, or a superseded/partial exp003 card.
 * Curated OFFICIAL ids are never hidden (reverse protection).
 */
export function isHiddenGrade(g: GradeResult): boolean {
  if (isOfficialGrade(g)) return false
  return (
    isDemoGrade(g) ||
    isSmokeId(g.experiment_id) ||
    isSmokeId(g.id) ||
    isHiddenDiagnosticExperimentId(g.experiment_id) ||
    isHiddenDiagnosticExperimentId(g.id) ||
    isLegacyExp003(g)
  )
}

/**
 * True when an experiment (inference report) should be hidden from the default
 * view: smoke/test runs and explicitly registered diagnostic reports.
 * `?debug=1` still exposes every underlying report.
 */
export function isHiddenExperiment(
  e: Pick<ExperimentEntry, 'short_id' | 'experiment_name' | 'total_tasks'>,
): boolean {
  return isHiddenOfficialExperiment(e)
}
