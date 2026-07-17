# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-17
- Status: Stage A rejected; safe prechecks and exact planner validated

## Task

- Audit Stage A against every preregistered gate before advancing to Stage B.
- Explain the planned 5 versus actual 4 render/perception call mismatch.
- Remove any invalid accepted artifact, fix the root cause, and replace
  route-only estimates with an executable model-free cohort planner.

## Result

- Stage A run `29559615083` completed 3/3 tasks with zero runtime/judge errors,
  complete usage, USD 1.26 raw / USD 1.02 effective cost, and no persisted
  payload/path violations. Seven bounded finalization retries succeeded.
- The run initially appeared to fail the preregistered exact-call gate because
  4 render/perception calls occurred instead of 5. Exact planning showed that
  4 was correct: `chart-of-accounts` is accounting content, not a visual chart.
- Audit found seven silent-corruption decisions in task 3. Six criteria
  comparing output content with PDF source invoices were auto-failed because
  the selected output was not PDF; one COA.xlsx consistency criterion was
  auto-passed because the selected output was XLSX. None evaluated content.
- The generic extension-only classifier is removed. Explicit filename and exact
  worksheet-name requirements remain deterministic, while reference filename
  mentions and substantive comparisons fall through to the judge.
- Added `preflight_track2_cohort.py`, which executes the real selector and
  precheck handlers without an Azure client. Corrected Stage A planning is 153
  items, 7 precheck candidates, 5 resolved, 2 fallbacks, 140 text, 4
  formatting, 4 visual, and exactly 4 render/perception calls.
- Active grading configs now declare `precheck_patterns_version: v2`. Corrected
  Stage A identity is config `0a8e1f421ad46dc2`, grader source
  `dafd2b4ea8f63258b6ae58e4cc259184146705f71d79b095c2e27656eca257a7`.
- The invalid Stage A grade and analysis are removed from the current tree.
  Stage B remains blocked until the corrected Stage A rerun passes.

## Verification

- Grader and exact planner focused tests: **46 passed**.
- Grader, routing, planner, selector, config, Step 8, and visual-inventory
  affected suite: **260 passed**.
- Broad non-integration suite excluding the unavailable local GDPVal parquet
  fixture: **1,189 passed, 2 skipped, 37 deselected**.
- The planner CLI ran end-to-end against the pinned Stage A manifest and exact
  local files, producing the expected 7/5/2 precheck split and 4 visual calls.
- Direct-entry help, Python compile, static diagnostics, and `git diff --check`
  passed. No Stage B or unrelated grade workflow was dispatched.

## Remaining Work

- Merge the safe-precheck correction and artifact removal.
- Rerun Stage A once with the corrected isolated identity and require exact
  5/5 render-perception calls plus all original gates.
- Run the exact planner over the first-10 tree and advance to Stage B only after
  the corrected Stage A passes.
