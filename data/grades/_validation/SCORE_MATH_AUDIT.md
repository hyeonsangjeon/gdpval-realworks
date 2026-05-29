# Score Math Audit — Negative-Penalty Sign Handling

Discovered during Opus's probe-Y₁ follow-up. Filed alongside the v2
stratification report. **Fix is out of scope for this commit** — this is a
findings note for a follow-up PR that touches `core/grader.py`.

## TL;DR

1. The 397→483 critical-pair difference between v1 and v2 stratifiers is
   not noise — it's 94 negative-magnitude items (`max_score < 0`,
   ranging from −85 to −1) that v1 silently excluded. Several of these
   are the largest single-item stakes in the entire rubric.

2. `verdict == 'pass'` has **opposite semantics depending on item sign**:
   - positive items: `pass` = deliverable satisfied the criterion (good)
   - negative items: `pass` = the bad thing happened (penalty applied, bad)

   Any code that filters or aggregates with `verdict == 'pass'` across both
   signs without normalization is broken. (`compare_grades.py` v1,
   `stratify_critical_gap.py` v1, and possibly `summary.wow.critical_item_pass_rate`
   in core/grader.py are all affected.)

3. `TaskRubric.max_score = sum(it.score for it in self.rubric_items)`
   sums positive and negative scores arithmetically. Four exp003 tasks end
   up with **`total_max <= 0`**, producing meaningless `pct` values:

   | task_id | total_max | total_awarded | reported pct | reality |
   |---|--:|--:|--:|---|
   | `6074bba3-7e3` | −330 | −217.0 | 65.76% | undefined (negative/negative) |
   | `e222075d-5d6` |  −29 |  −60.1 | 100.00% | undefined (clamped from 207%) |
   | `c94452e4-39c` |  −10 |  +34.7 |   0.00% | undefined (clamped from −347%) |
   | `ff85ee58-bc9` |  −57 |   −9.7 | 17.02% | undefined |

   18 of 220 tasks have meaningful negative contribution
   (`abs(neg_sum) / pos_sum > 0`); median ratio 15.4%, max 7.6× (one task
   where penalty potential is **7.6× larger** than the positive max).

4. The `pct = max(0.0, min(100.0, pct))` clamp in `core/grader.py:911`
   was added recently to satisfy `grade.schema.json`'s `{minimum:0,
   maximum:100}` — it correctly prevents schema violations but it
   **silently hides the math defect** for these four tasks. The schema
   passes; the underlying number is nonsense.

## Why this matters for the hybrid-vs-mini decision

Both hybrid and mini grade JSONs are computed with the same broken math,
so their **head-to-head pct comparison is internally consistent** (same
bug, same direction). The headline `−10pp critical_pass` finding survives.

But the absolute numbers — including the `0.7` PROCEED threshold in
`compare_grades.py` — sit on shaky ground. Specifically:
- `summary.wow.critical_item_pass_rate` is computed without sign
  normalization (verified by inspection of core/grader.py paths), which
  means the headline 0.421 and 0.518 numbers conflate "model satisfied
  the criterion" with "model committed a violation."
- For the 4 negative-only-total-max tasks, all per-task `pct`s and any
  rank-based downstream metric (top-k worst tasks, sector heatmap) are
  garbage.

## Recommended fix (separate PR)

Three options, in order of severity:

**Option 1 (minimal — preserve scoring semantics):** change
`TaskRubric.max_score` to `sum(max(0, it.score) for it in items)` so the
denominator is the maximum *positive* score achievable. Penalty items
still subtract from `total_awarded`, but cannot make `total_max`
negative. `pct` then sits in `[−penalty_ceiling, 100]` and the clamp
correctly floors at 0 for catastrophic violations.

**Option 2 (cleaner — separate critical-fail track):** keep
`total_max = sum(positive scores)`, but additionally emit
`summary.critical_violations` as a list of negative-item failures with
their penalty values. UI can show "X critical violations" badge alongside
the pct. This is closer to how a rubric author would describe scoring
("you get up to 100 points, minus penalties").

**Option 3 (most work — sign-aware everything):** add `_model_did_right`
to `core.grader.ItemGrade` as a derived field, recompute
`critical_item_pass_rate` using it, and re-grade or back-fill all
existing grade JSONs. This is the only option that fully fixes the
headline numbers reported to the public dashboard.

## Recommended action right now (no code change)

- Quote v2 sign-aware stratification (`STRATIFY_v2_exp003_critical_gap.md`)
  as the authoritative read of the hybrid-vs-mini gap, not v1.
- Treat the four negative-total_max tasks as unscoreable for this
  decision; exclude from any rank-based analysis.
- File this audit as a known issue in CHANGELOG so the next operator
  doesn't rediscover it.

Probe Y₂ (Opus's spec) is **still the right next step** to disambiguate
whether the hybrid-stricter formatting gap is artifact (Scenario B) or
real catches (Scenario A), independent of the math defect above.
