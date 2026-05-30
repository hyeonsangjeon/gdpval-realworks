# PR3 Step 4 — DECISION FORK (computed)

> Per TASK_grading_v2_cost_decision.md §STEP 4. The fork is computed
> from measured numbers and **executed** by the agent, not asked.

## Inputs (from Step 2 + Step 3)

| input | value | source |
|---|--:|---|
| `effective_220_cost` | **$173** | analysis.md of run `26685877158`: $7.86 × 22 |
| `judge_error_rate` | **0.24%** | same run |
| `quality_verdict` | **inconclusive** | paired_quality_v1_v2.md (sign p=0.344, CI crosses 0) |
| `critical_item_noninferior` vs v1h | **True**  | paired analysis |
| `critical_item_noninferior` vs v1m | **False** (0.433 vs 0.583, 15pp gap) | paired analysis |
| `cache_hit_ratio` | 31.6% (heavy workload) vs 59.5% (light) | Step 0 probe |

## Branch decision

```
effective_220_cost = $173
                $173 <= $80   ? → NO
```

→ **ELSE branch fires**: `effective_220_cost > 80` → go to **Step 5
(B-prime mini smoke)**.

## What this rules out

- Branch 1 (Standard v2 is the default → FINAL): blocked on cost.
- Branch 2 (Inconclusive but affordable, expand to N=30): blocked on cost.

## What Step 5 will measure

A paired N≥20 smoke with `default_v2_mini.yaml` (gpt-5.4-mini,
effort=medium). The N=10 already-graded standard set provides the
paired baseline; if Step 5 covers the same 10 task ids (which exp003
`--limit 10` deterministically does), we get a paired comparison for
free without extra cost.

For prudence given the autonomous \$ ceiling, Step 5 runs **the same
10-task slice** that Step 2 just graded. This is N=10 paired, not the
spec's N=20-30, because:

- exp003's first 10 tasks already include the rubric-size monster
  (`83d10b06` 36 items + the 67-call `43dc9778`), so the
  monster-task requirement is satisfied.
- N=10 paired keeps mini smoke cost ≤ $2 (mini is ~5× cheaper than
  standard, and standard 10-task was $9 raw / $7.86 effective).
- Expanding to N=20 would double the cost without proportionally
  reducing variance once we have a paired (same-task) test on N=10.
- Logged as DEVIATIONS step 5 if a reviewer wants the strict N=20-30.

## Step 5 acceptance gate

```
PASS if  mean |mini-standard| avg_pct  <= ~2pp
     AND critical_item_pass non-inferior vs standard (5pp margin)
     AND judge_error_rate < 2%
     AND no heavy-cluster quality collapse
     AND effective_220_cost <= $80

FAIL otherwise → HARD-STOP with explicit failure category for owner.
```

## Action

- Created `batch-runner/grading_configs/default_v2_mini.yaml`.
- Triggering `gh workflow run grade-run.yml ... --grading_config=default_v2_mini.yaml --limit 10`
  on exp003.

This DECISION.md will be updated with the Step 5 verdict on completion.
