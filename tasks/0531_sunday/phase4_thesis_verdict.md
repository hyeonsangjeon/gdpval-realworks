# PHASE 4 — Thesis verdict (gold-based)

## Verdict: **BLOCKED — owner-go required**

The rev2 spec is explicit:

> 성공 = Phase 4의 thesis 판정을 *gold 기준*으로 내리는 것. "wiring 돼서
> 돌아감" 또는 "avg_pct 올라감"으로 끝내면 실패.

and on Phase 1:

> reference label이 없으면 여기서 owner-go 필요 — owner가 hand-grade를
> 완료해 gold를 줄 때까지 Phase 4 판정 불가.

Both preconditions for a Phase 4 verdict are currently unmet:

1. **No gold.** GDPVal has no per-rubric-item expected verdict; the 19
   gold candidates in `tasks/0531_sunday/gold_candidates.md` are
   awaiting owner hand-grading. Until `gold_verdicts.json` exists, the
   first-order metrics the spec demands — critical false-pass rate,
   gold agreement, evidence validity — are uncomputable.
2. **No live perception-on grades.** Phase 3's acceptance gate could
   not be tested live because of an Azure auth blocker (see
   [phase3_smoke.md](phase3_smoke.md)). Even with gold, there is no
   perception-on grade JSON to *compare against* the existing
   perception-off v2-mini and v1-mini grades.

## What would unblock Phase 4

(In order; (a) and (b) can run in parallel.)

- **(a, owner)** Hand-grade the 19 candidates → `gold_verdicts.json`.
- **(b, owner)** Refresh OIDC service-principal secret in
  `batch-runner/.env` (or re-enable resource key auth temporarily).
- **(c, agent)** Re-run perception-on grading on the same 10 shared
  exp003 tasks (`config: default_v2_mini.yaml` with the wired
  perception block) — small, ~10 tasks, well within the sanctioned
  N≤30 budget.
- **(d, agent)** Compute on the gold set, modality-restricted:
  - **critical false-pass rate** = `count(gold=fail ∧ judge=pass) / count(gold=fail)`
  - **gold agreement** = `count(judge == gold) / count(gold ≠ unsure)`
  - **evidence validity** spot-check on the 12 visual + 1 audio items
- **(e, agent)** Compare across three judges on the same items:
  - v1-mini (text-extract, perception-impossible)
  - v2-mini perception-OFF (existing `__rubric_v2_tools_mini.json`)
  - v2-mini perception-ON (new run from step c)
- **(f, agent)** Render the gold-based verdict per rev2 spec:
  SUPPORTED / INCONCLUSIVE / REJECTED — based on whether perception-ON
  reduces critical false-pass and raises gold agreement on
  visual/audio criteria.

## Strong negative signal already observable (without gold)

This is **not** a Phase 4 verdict. It is a Phase-0 finding that
*constrains expectations* for whichever Phase 4 result eventually
lands.

- Phase 0(a): all 3 critical-tier regressions (v2-mini < v1-mini on
  |max|≥4) classify as **formatting**. Formatting routes to the
  `inspect_formatting` tool, **not** to a perception sub-judge.
  Wiring perception will not mechanically touch these regressions.
- Phase 0(b): of the 38 leniency flips (mini > standard verdict),
  **32/38 are TEXT** modality (1 visual, 2 visual+1 from "flip\_nontext"
  bucket; the rest formatting/text). Pure text leniency cannot be
  addressed by visual/audio perception either.

So the largest two known v2-mini quality problems — critical regression
vs v1 and leniency vs v2-standard — are **predominantly outside the
modality surface perception wiring can affect**. The honest prior for
Phase 4 is therefore: **modest at best**. Perception may still improve
the 12 visual + 1 audio items specifically (which is what gold should
measure), but it is unlikely to repair the headline v2-mini numbers.

The rev2 spec is clear that an honest REJECTED is an acceptable
outcome. This finding raises the prior for REJECTED on the v2 *flip*
decision, even before gold lands.
