# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-17
- Status: Stage A rejected; all-judge correction and exact planner validated

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
- Automatic natural-language prechecks are disabled. Filename, extension,
  worksheet, file/count, page, and word requirements all go to the judge;
  stale precheck IDs cannot emit a verdict.
- Added `preflight_track2_cohort.py`, which executes the real selector,
  routing, and shared visual validator without an Azure client. It rejects a
  dirty tree and mismatched planner/repository/source/config/grader/rubric/task
  identities before planning.
- Clean Stage A planning on implementation commit `acba15bcc56f` is 153 items,
  zero prechecks, 143 text, 6 formatting, 4 visual, 153 main judgments, and
  exactly 4 render/perception calls with no errors.
- Active configs declare `precheck_patterns_version: v2` as an identity marker,
  not a runtime switch. Stage A identity is config `0a8e1f421ad46dc2`, grader
  source `9b8a9ae3288ec3e9c7608ea8af4ced3e77f2e27956da426da5b63d3b0acee01e`,
  and planner source
  `1a7cca75e685d5c2202f4753ae39255fac196dcd27d5581af80976ae60efb147`.
- The invalid Stage A grade and analysis are removed from the current tree.
  Stage B remains blocked until the corrected Stage A rerun passes.

## Verification

- No-precheck grader/planner focused suite: **65 passed**.
- Shared visual-validator/planner parity suite: **19 passed, 37 deselected**.
- Planner identity suite: **14 passed**; corrected split-selector regressions:
  **3 passed**.
- Broad non-integration suite excluding the unavailable local GDPVal parquet
  fixture: **1,204 passed, 2 skipped, 37 deselected**.
- The planner CLI ran end-to-end against the pinned Stage A manifest and exact
  local files from a clean commit, producing zero prechecks, 153 judge-bound
  items, and 4 visual calls with every expected identity matched.
- Independent grading-engineer review found no remaining code correctness
  blocker. Static diagnostics and `git diff --check` passed. No Stage B or
  unrelated grade workflow was dispatched.

## Remaining Work

- Merge the safe-precheck correction and artifact removal.
- Rerun the exact planner on merged `main`, then rerun Stage A once with the
  corrected isolated identity and require exact 4/4 render-perception calls
  plus all original gates.
- Run the exact planner over the first-10 tree and advance to Stage B only after
  the corrected Stage A passes.
