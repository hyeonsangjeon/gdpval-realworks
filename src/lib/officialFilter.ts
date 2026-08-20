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
 *
 * Phase 3 replaces the name-matching half of that with a measured one: any
 * grade covering fewer tasks than the inference run it graded is a preflight
 * and is hidden. `_tight` was always an instance of this rule written by hand;
 * the pattern stays as a fallback for grades whose experiment has no report.
 *
 * Phase 4 curates what survives. The 220-task `gpt-5.6-sol` regrade is promoted
 * to OFFICIAL as the current result, and the older full-corpus runs are retired
 * down to a single A/B comparator — every rule up to here removes things that
 * are not results, this one decides which results still earn screen space.
 */
import type { GradeResult } from '../hooks/useGrades'
import type { ExperimentEntry } from '../types/report'
import {
  isHiddenDiagnosticExperimentId,
  isHiddenOfficialExperiment,
  isOfficialGradeId,
  isPartialCorpusGrade,
  isSmokeExperimentId,
  isSupersededGradeId,
  OFFICIAL_GRADE_IDS,
  OFFICIAL_TASK_COUNT,
  SUPERSEDED_GRADE_IDS,
} from './officialExperimentScope.js'

export {
  OFFICIAL_GRADE_IDS,
  OFFICIAL_TASK_COUNT,
  SUPERSEDED_GRADE_IDS,
  isPartialCorpusGrade,
}

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
 * Curated OFFICIAL grade ids (phase 2, recurated in phase 4). "Official" is a
 * hand-picked status, NOT a pattern — when a new official run is promoted, add
 * its id to `OFFICIAL_GRADE_IDS` in `officialExperimentScope.js`, where it sits
 * next to the retirement list and is covered by the node test suite.
 * These are pinned visible (badged) and never hidden by any rule.
 */

/** Curated official baseline (gets the OFFICIAL badge; never hidden). */
export function isOfficialGrade(g: Pick<GradeResult, 'id'>): boolean {
  return isOfficialGradeId(g.id)
}

/**
 * A complete run retired in favour of a newer judge (phase 4). Distinct from
 * `isPartialCorpusGrade`: nothing is wrong with these numbers, they are simply
 * no longer the comparison the page is making.
 */
export function isSupersededGrade(g: Pick<GradeResult, 'id'>): boolean {
  return isSupersededGradeId(g.id)
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
 * legacy demo, smoke/test run, a superseded/partial exp003 card, a grading run
 * that covered only part of its inference corpus, or a complete run retired in
 * favour of a newer judge.
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
    isSupersededGrade(g) ||
    isPartialCorpusGrade(g) ||
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
