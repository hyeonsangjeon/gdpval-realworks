# `summary.wow` Drift — Two Retired 2026-06 Runs

**Diagnosis only.** No payload was edited, no rate was republished, and no
grading was dispatched. Everything below was derived from files already in the
repository plus `git`.

Subjects:

- `exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json`
  (graded 2026-06-10)
- `exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
  (graded 2026-06-04)

## TL;DR

1. **One cause, not two.** `6ad789a` (#69, 2026-07-15) taught the summariser's
   item loop to skip items carrying `score_excluded`. Both files were graded
   before that commit, so their stored rates count 255 judge errors as though
   the model had failed them. Removing the gate — and changing nothing else —
   reproduces **all five** published rates exactly, in **both** files.

2. **The two rates move in opposite directions for one reason.** The gate
   shrinks both denominators. Coverage keeps its entire numerator, because a
   judge error is never a `pass`, so it rises. The critical numerator loses
   every item its denominator does, and loses proportionally more, so it falls.

3. **No OFFICIAL number is affected.** Both runs were retired as comparators in
   Phase 5 (`scripts/__tests__/official-filter.test.mjs`); the two ids the
   dashboard still treats as official are the sol-220 R1 result and its
   single sol-vs-sol predecessor, and both recompute to the digit.

4. **Nothing is left over.** 37 published payloads carry `summary.wow` rates.
   31 reproduce, 2 are the gate, 4 are the already-known pre-sign-aware
   `__v1.json` files, 0 are unexplained.

## The numbers

`n/d` is the counter pair behind each rate.

| file | rate | published | as `n/d` | recomputed | as `n/d` |
|---|---|--:|---|--:|---|
| tools | `rubric_item_coverage_avg` | 0.4232 | 4424 / 10453 | 0.4338 | 4424 / 10198 |
| tools | `critical_item_pass_rate` | 0.501 | 242 / 483 | 0.485 | 227 / 468 |
| mini | `rubric_item_coverage_avg` | 0.4533 | 4738 / 10453 | 0.4646 | 4738 / 10198 |
| mini | `critical_item_pass_rate` | 0.528 | 255 / 483 | 0.5128 | 240 / 468 |

`precheck_pass_rate` (0.5832), `judge_pass_rate` and `judge_error_rate`
reproduce unchanged in both files. That is **not** evidence that their code
paths were left alone — it is evidence that the gate is a no-op for them on
this corpus. All 255 excluded items are `decided_by: judge`, so none reaches
the precheck counters; none is a `pass`, so none reaches `judge_pass`; and
`judge_items` has never been gated.

## What the gate removes

All 255 are the same shape, in both files, because the two runs share a rubric
and differ only by judge:

| field | value |
|---|---|
| `verdict` | `judge_error` (255/255) |
| `decided_by` | `judge` (255/255) |
| `awarded_score` | `0.0` (255/255) |
| `model_did_right` | `true` (255/255 — see below) |
| `selection_status` | `selection_error` (243), `wrong_format_primary` (12) |
| `max_score` | 1 (149), 2 (86), 5 (15), 3 (5) |
| spread | 17 of 220 tasks |

These are items the judge never managed to score. #69's position — the one the
code still holds — is that charging them to the model measures the harness, not
the model.

The minimal diff, per file:

```
coverage: denominator -255, numerator   -0
critical: denominator  -15, numerator  -15
```

The 15 are exactly the excluded items with `|max_score| >= 4`; all 15 carry
`max_score: 5`, and all 15 carry `model_did_right: true`.

## Change history

| commit | date | PR | effect |
|---|---|---|---|
| `240b860` | 2026-05-29 | — | introduces `model_did_right`; `judge_error` → `False` |
| `2cf4171` | 2026-06-03 | — | introduces `score_excluded`, and tests it **before** the `judge_error` branch, so judge errors get `model_did_right = True` |
| **`6ad789a`** | **2026-07-15** | **#69** | **adds the `score_excluded` gate to `_compute_summary` — this is the drift** |
| `6cdfb98` | 2026-08-10 | #168 | swaps those two branches back, so `judge_error` → `False` again; adds the `invalid_score_exclusion` guard; moves `judge_error_rate` to `canonical_rate` |
| `bc14a91` | 2026-08-21 | #180 | refactors the loop into `_tally_item`; semantics unchanged |
| `0e4a844` | 2026-08-21 | #188 | backfills `by_sector` / histogram / severity into the old files, deliberately **without** republishing the rates |

Both grading commits are descendants of `2cf4171` and ancestors of `6ad789a`,
which is the whole story: the files were written in the window where
`score_excluded` existed on items but the summariser did not read it.

`#188` is not a defect here. Leaving the rates alone is why a number anyone had
already cited did not move underneath them — and why the drift is legible at
all, instead of having been quietly overwritten.

## Two differences that do not show up in this recompute

**`model_did_right` on judge errors.** `2cf4171` ordered the branches so that
`if it.score_excluded` won before `elif it.verdict == "judge_error"`, and
`score_excluded` was already set upstream for judge errors. Every judge error
in these files therefore claims the model did right. #168 restored the intended
order. This does not change the recompute — the recompute reads the stored
flag, and today's gate discards those items anyway — but it does mean the
published `critical_item_pass_rate` of 0.501 credits the model for 15 items the
judge failed to score. Applying both later fixes to these frozen verdicts lands
on 227/468 either way: the flag fix and the gate remove the same 15 items.

**Rounding.** `judge_error_rate` moved from `round()` (half-even) to
`canonical_rate()` (half-up) in #168. Inert on this corpus — it reproduces
everywhere — but it is a third rule change, and it would bite on an exact
`.00005` tie.

## Reproduce

From `batch-runner/`:

```bash
# whole corpus, with the per-counter diff for anything that drifts
python3 scripts/summary_wow_drift.py

# the guard, as CI runs it
python -m pytest tests/test_summary_wow_drift.py
```

The script exits nonzero only when a file's drift matches no summariser rule we
have shipped. It never writes to a payload.

## Options, not taken

Listed for a decision; none of these is done, because each changes a published
number or a schema.

| | option | cost | consequence |
|---|---|---|---|
| A | **Leave both files as published** (recommended) | none | The rates stay comparable with the analysis docs and CHANGELOG entries that already quote them. `summary_wow_drift.py` plus its test keep the divergence named rather than rediscovered. Both runs are retired, so nothing on the dashboard reads them. |
| B | Recompute the two rates in place from the frozen items | no model calls; a script run | Makes the files self-consistent, but silently changes 0.501 and 0.528 — both of which are quoted in the committed `.analysis.md` next to each payload. Those docs would have to move in the same commit, and any external citation would go stale. |
| C | Stamp payloads with the summariser rule that produced them | schema field + migration | Removes the need to bisect next time. Worth doing only if the summariser is expected to keep changing; it does not help the files already written. |

Option A is the recommendation. The published rates are not wrong — they are
what the rule of the day produced over honestly-recorded items, on two runs
that no longer back any live claim. What was missing was a way to tell that
from an actual accounting error, and that is now checked on every CI run.
