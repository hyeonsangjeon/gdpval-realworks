# PR3 Step 6 — Hybrid Routing Spec (deterministic, rule-based)

> Required only if Step 5 PASS. Defines the rule-based router that
> sends each task to `gpt-5.4-mini` (cheap default) or `gpt-5.4` standard
> (expensive fallback). NOT LLM-routed — deterministic and inspectable.

## When to use this

Step 5 measured mini-medium on exp003 N=10 with the same caching
infrastructure as standard. Result: cost dropped 68%, avg quality
went UP +2.27pp (CI lower bound > 0), critical_pass identical, no
heavy-cluster collapse. Mini is the new default judge for v2. The
hybrid fallback exists for safety against pathological tasks where
mini's lower tool-orchestration reliability might collapse.

## Router input → decision

```
ROUTE(task) -> "standard" | "mini"

ROUTE = "standard"  IF ANY of:
  - rubric_items_count > 60                # extreme rubric size
  - any criterion contains audio/video keyword (modality routing)
  - any criterion routes to VISUAL with vision_perception enabled
                                           # subsume vision/audio
                                           # in the safer tier
  - task_id ∈ KNOWN_HARD_TASKS_SET         # operator escape hatch

ROUTE = "mini"  otherwise.
```

The set `KNOWN_HARD_TASKS_SET` is initially empty. Operators add
task_ids that experienced ≥3 retries or `judge_error` in shadow audit.

## Shadow-audit plan (mandatory for first 4 weeks of mini default)

Every grade-run.yml invocation runs an additional **10–15% stratified
shadow** on `gpt-5.4` standard for the SAME tasks the router sent to
mini. Drift monitoring focuses on **`critical_item_pass`**, not avg_pct
(the latter has ±5pp noise at N=10; the former is closer to the actual
"deliverable acceptable?" question).

Drift alarm thresholds:
- mean `critical_item_pass` (mini) <  mean `critical_item_pass` (standard) − 5pp on the shadow set → ALERT
- `judge_error_rate` (mini) > 2% on shadow → ALERT
- per-task standard > mini by ≥ 15pp on `critical_item_pass` for ≥3 tasks in 1 week → ALERT

On any alert, the operator decides:
1. add the offending task_ids to `KNOWN_HARD_TASKS_SET`
2. or escalate the threshold (rubric_items_count down from 60 → 40)
3. or roll the default back to standard

## Implementation notes (not implemented in PR3; for follow-up cleanup PR)

- Add `judge_routing` block to `default_v2.yaml` with `default_tier` +
  `standard_tier_when` rules; reuse the legacy tier-routing scaffold
  in `core/grader.py` (which the PR2 207 cleanup PR is going to delete
  — instead, repurpose it). Decision: defer to the cleanup PR so PR3
  doesn't touch grader execution semantics.
- Shadow-audit runner: small Python script that picks a stratified
  10-15% sample after each main grade-run and dispatches a parallel
  standard run on `data/grades/_shadow/`. Compare via existing
  `scripts/compare_grades.py`. Out of PR3 scope.
- `KNOWN_HARD_TASKS_SET`: surfaced as a YAML list under
  `judge.routing.force_standard_task_ids: []`. Operator edit.

## Rationale: why not "always mini"

Empirically mini matched or beat standard on this 10-task slice. The
hybrid spec is a **safety net** against the unknown: GDPVal has 220
tasks across 9 sectors / 44 occupations; the 10 we measured are
deterministic but not stratified by modality. If full 220 production
surfaces a cluster (e.g. audio-heavy or 100-item rubrics) where mini
collapses, the deterministic router routes those to standard at the
known acceptable cost, while keeping the 220-run total close to mini's
$55 baseline. Worst-case (everything routes to standard) cost is $173,
which Step 4 already characterized.

## Step 6 acceptance

This spec is the artifact. No code shipped in PR3 — implementation
deferred to a follow-up PR alongside the legacy-strip cleanup.
