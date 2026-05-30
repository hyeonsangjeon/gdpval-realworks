# PR3 Tight Smoke Findings — caps tightening BACKFIRED

> Round 3 of PR3 task 302. Round 2 measured $168/run with default_v2;
> tightened caps for round 3 expecting $80-99/run. Reality: $193/run
> with judge_error_rate doubled past the SPEC §7.4 ceiling.

## Result table

| metric | round 2 (`default_v2`) | round 3 (`default_v2_tight`) | Δ | gate |
|---|--:|--:|--:|---|
| cost (10 tasks) | $7.66 | **$8.79** | **+14.7%** | — |
| 220-task extrap | $168 | **$193** | +$25 | **❌ > $80** |
| avg_score_pct | 56.66 | 54.77 | -1.89 | ✓ ≥ 51 |
| critical_pass | 0.4091 | 0.4091 | 0 | = |
| **judge_error_rate** | 0.72% | **3.38%** | **+2.66pp** | **❌ > 2%** |
| judge_calls | 414 | 414 | 0 | — |
| input tokens | 4,955,382 | **5,867,216** | **+18%** | — |
| output tokens | 293,268 | 291,827 | -0.5% | — |
| wall-clock | 63.9 min | 63.9 min | 0 | — |

Run: [`26680191340`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/26680191340).

## Diagnosis — why caps backfired

The mental model going in was: tighter `per_item_call_cap` + smaller
`max_iterations` → fewer tool round-trips → less echoed
`function_call`/`function_call_output` history → fewer input tokens.

What actually happened:

1. **`max_output_tokens` 2400 → 1500** truncated the judge's final JSON
   envelope mid-stream. That triggered `_safe_parse_judge_json` failure
   → `judge_error_rate` exploded from 0.72% to 3.38%.
2. **`per_item_call_cap` 8 → 4** caused the model to receive
   `cap_exceeded` envelopes on its 5th-8th attempted call. Rather than
   finalize on what it already had, the harness's "tell the model so
   it can finalize" message itself joined the input batch — and the
   model often re-tried with slightly different args. Net input tokens
   went **up**, not down.
3. **`max_iterations` 10 → 6** had marginal effect — most tasks already
   finalized in ≤6 iterations.

**Generalization**: in this v2 architecture, input-token cost scales
with `(rubric_items_per_task) × (avg_tokens_per_call)`, NOT with
`(iterations) × (tools_per_iteration)`. Tighter per-item caps don't
reduce the dominant factor; they just push the model into
inefficient retry loops.

The top-cost task (`83d10b06`, 49 rubric items) used **2.49M input
tokens** in tight mode vs 2.12M in default — 17% **more**, not less.

## Autonomous gate evaluation

| gate | required | observed | pass? |
|---|---|---|---|
| 220-task extrap | ≤ $80 | $193 | ❌ |
| avg_pct | ≥ 51 | 54.77 | ✓ |
| judge_error | < 2% | 3.38% | ❌ |

**Two of three gates failed.** Autonomous PROCEED to full exp003
(task 301) is NOT authorized. The autonomous tighten-then-retry
branch has run out of useful moves: the lever wasn't where the
model was.

## STOP+ALERT — user decision required

| option | action | est. full cost | quality posture | recommendation |
|---|---|--:|---|---|
| **A** | Revert to `default_v2` and accept the full run | $168 | best (avg 56.66) | OK if budget tolerable |
| **B** | Switch model to `gpt-5.4-mini` (effort=low), keep tool-calling | $25-40 (est.) | likely -3-5pp avg; tool-use reliability TBD | best cost/quality trade if mini's tool-use proves adequate |
| **C** | Mild tighten: `per_item_call_cap`=6, restore `max_output_tokens`=2400 | $120-150 (est.) | ≈ default_v2 quality | half-measure; unclear it saves enough |
| **D** | Accept $168, run full once for the head-to-head signal alone | $168 | best | one-shot purchase of PR3 evidence |
| **E** | Abort PR3 v2-as-default plan; keep v1 in `grade-run.yml` | $0 | v1 baseline | safest exit |

## Suggested next step (recommendation, not autonomous)

**Option B** preserves the v2 tool-calling architecture (which
demonstrably outperforms v1 by +5pp) while attacking the actual cost
center (model price per token). Mini is ~10× cheaper per token than
standard 5.4. The risk is SPEC §4.1's "mini may not orchestrate tools
reliably" concern — but our round-2 measurement showed standard's
judge_error was only 0.72%, so even if mini doubles that, it's still
under the 2% ceiling. Empirically testable in one more N=10 smoke
(~$3, ~60 min).

Awaiting user pick: **A / B / C / D / E** (or your own).
