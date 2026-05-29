# PR1 — Score-Math Sign-Bug Fix — REPORT

> Closes PR1 of the grading-v2 rebuild. Sequel = PR2 (tool-calling
> grader rewrite, new session). Authoritative SPEC:
> [`SPEC_GRADING_PIPELINE_V2.md`](./SPEC_GRADING_PIPELINE_V2.md).

## Outcome

PR1's goal: make every published headline grading number (`avg_score_pct`,
`critical_item_pass_rate`) trustworthy by fixing three correctness bugs
discovered in the prior hybrid-vs-mini cycle. All five tasks (100-104)
shipped to main with commits below. Full regression: 478 pytest +
29 scripts pytest + node mjs tests green.

## Commits

| commit | task | what changed |
|---|---|---|
| `240b860` | 100 | `ItemGrade.model_did_right` (sign-aware) |
| `ad3b922` | 101 | `MAGNITUDE_THRESHOLD=4`, `_is_critical_item()`, summary critical pass uses `model_did_right` |
| `b9c46e8` | 102 | `TaskRubric.max_score` = positive-only sum; `TaskGrade.pct_raw` diagnostic |
| `933c25e` | 103 | `scripts/backfill_sign_aware.py` + 4 v2sm grade JSONs on main; schema 1.1; aggregator routes v1.0+v1.1 |
| (this)    | 104 | regression sweep + this report + CHANGELOG + OVERVIEW status |

## v1 → v2sm headline diff (exp003, 219 of 220 graded)

| metric | hybrid v1 | hybrid v2sm | mini v1 | mini v2sm |
|---|--:|--:|--:|--:|
| critical_item_pass_rate | 0.421 | **0.466** | 0.518 | **0.596** |
| avg_score_pct           | 49.25 | 48.18 | 51.47 | 50.97 |
| hybrid-vs-mini Δcrit    | −0.097 | **−0.130** | — | — |
| critical_items count    | 397 (positive≥3) | **483** (\|max_score\|≥4) | 397 | 483 |

Reads:

- **The wider Δcrit on v2sm is expected, not a regression.** Adding the
  94 negative-magnitude penalty items into the critical set surfaces a
  signal v1 was silently discarding. STRATIFY_v2's per-bucket
  decomposition (formatting 60.3% / penalty 21.8% / content 17.9% of
  hybrid-stricter pairs) remains the authoritative read; the v2sm
  headline numbers just reflect that aggregation honestly.

- **hybrid v2sm 0.466 vs STRATIFY_v2's reported 0.468** — sub-half-pp
  delta is the difference between counting via `tasks[]` walk (v2sm
  summary) vs counting via `pairs` (STRATIFY_v2 script). Both correct,
  same direction.

- **avg_score_pct nudged slightly down** for both configs because the
  positive-only denominator + `[0,100]` clamp now floors the 4
  previously-degenerate-`total_max≤0` tasks at 0% (where v1 surfaced
  nonsense like 65.76%, 100%, 17.02% from clamping divisions of
  signed numerators by signed denominators).

## Degenerate-task accounting (the 4 SCORE_MATH_AUDIT cases, hybrid run)

| task_id | v1 pct | v1 total_max | v2sm pct | v2sm pct_raw | v2sm total_max |
|---|--:|--:|--:|--:|--:|
| `6074bba3-7e3...` | 65.76 (clamped) | −330 | **0.0** | **−434.00** | 50 |
| `e222075d-5d6...` | 100.00 (clamped from 207%) | −29 | **0.0** | **−98.52** | 61 |
| `c94452e4-39c...` | 0.00 (clamped from −347%) | −10 | **62.0** | 62.00 | 56 |
| `ff85ee58-bc9...` | 17.02 (clamped) | −57 | **0.0** | **−13.29** | 73 |

`pct_raw` on these surfaces the actual penalty load; the clamped `pct`
is now a defensible 0 (or accurate positive in c94452e4's case) instead
of a misleading number anchored to a negative denominator.

## What PR1 did NOT touch (PR2/3 scope)

- `deliverable_extract_max_chars=1500` truncation — root cause of the
  formatting bucket gap is unchanged. PR2 tool-calling rewrite tackles this.
- `core/grader.py`'s legacy `Judge` / `BatchJudge` / tier dispatch code —
  PR2 task 207 removes it.
- Dashboard UI exposure of `pct_raw`, `model_did_right` — both fields land
  on main and the TypeScript types in PR1 task 103, but no UI changes here.
- Variance / bootstrap CI re-runs — PR3 task 303.

## New session handoff for PR2

A new session starting PR2 needs only these files in context:

- `tasks/rebuilding_grading_task/SPEC_GRADING_PIPELINE_V2.md` (whole SPEC)
- `tasks/rebuilding_grading_task/000-OVERVIEW.md` (status board + autonomous decisions)
- `tasks/rebuilding_grading_task/PR1_REPORT.md` (this file)
- `tasks/rebuilding_grading_task/200-*.md` through `208-*.md` (PR2 task specs)
- `data/grades/_validation/SCORE_MATH_AUDIT.md` (background diagnostic)

Suggested first prompt for PR2 session:
> "Start PR2 with task 200 (exp011 env audit). SPEC at
> tasks/rebuilding_grading_task/SPEC_GRADING_PIPELINE_V2.md, status at
> 000-OVERVIEW.md, PR1 result at PR1_REPORT.md. Same autonomous
> contract: each task is its own commit, regress before push, mark
> OVERVIEW status, then proceed."
