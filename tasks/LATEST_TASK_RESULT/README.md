# Latest Task Result

- Updated: 2026-08-05
- Status: Completed 220-task mini regrade history restored on `main` through
  PR #158

## Task

- Recover the useful completed-run content from the preserved dirty checkout
  without merging its stale code, UI regressions, generated artifacts, or
  unrelated local work.
- Replace the checked-in `BLOCKED` pre-run note with a reproducible historical
  record of the completed `default_v2_mini.yaml` 220-task grading relay.
- Correct stale provenance and incorporate later experiments that resolved the
  original future-work hypotheses.

## Result

- Replaced the pre-run note with the four successful GitHub Actions runs,
  workflow input heads, preserved output commits, and cumulative task counts.
- Corrected the chunk-2 output identity to
  `110f3bf604f62029fe12e5737b777687439e4b15`.
- Recomputed from the checked-in final grade JSON:
  - selection status: 194 ok, 20 wrong-format primary, 1 no generated
    candidate, and 5 selection errors;
  - 113 tasks with excluded reference files and no reference fallback;
  - 8,904 judge calls, 130,092,056 input tokens, and 5,523,697 output tokens;
  - 10,453 item audit coverage with no missing required audit fields;
  - 355 judge errors, including 100 score-included zeros across 53 tasks with
    max-score weight 164.
- Rejoined owner gold 20 by exact task and criterion. Overall Style bias is
  -0.1625/5 and MAE is 1.2125/5.
- Clarified that the baseline is selector-clean, not error-free, and that
  `perception_called=false` does not imply the judge had no tool observation.
- Replaced obsolete future work with the checked-in follow-up findings:
  broad rendering was effectively null at equal model, the GPT-5.4 full run was
  completed, and production grading now defaults to GPT-5.6 Sol Max.
- No source code, grading output, grade score, workflow, model configuration,
  current production policy, or published artifact was changed.

## Verification

- Recomputed selector, reference, token, judge-error, audit, population score,
  and gold metrics directly from the final 220-task mini grade JSON.
- Verified all four GitHub Actions runs are complete and successful.
- Reopened each preserved output commit and verified the cumulative progression:
  46 -> 112 -> 162 -> 220 tasks.
- Verified final grade and auto-analysis commits and all linked evidence paths.
- Verified the follow-up GPT-5.4 JSON reproduces the same selector distribution
  and the checked-in vision report records the null broad-render result.
- Executable historical-report contract and `git diff --check` passed.
- Independent grading review returned `APPROVE` with no findings.
- No model call, grading run, workflow dispatch, cloud credential, publication,
  or paid API call was used for this documentation recovery.

## Shipment

- Reviewed branch head:
  `3a303590ca08484e3bd9c83303500d44d0a9b31e`.
- PR [#158](https://github.com/hyeonsangjeon/gdpval-realworks/pull/158)
  reached `MERGED` at `2026-08-05T09:35:56Z` as commit
  `d610c717696b4e6589cf28fb8a122c7b3b9aa2d8`.
- The changed documentation paths are outside the active automatic workflow
  filters, so GitHub created no PR or post-merge workflow run. The executable
  evidence contract and two independent reviews supplied acceptance evidence.

## Remaining Work

- The historical mini headline includes score-included judge errors and must not
  be cited as an error-free judge-quality estimate.
- Historical grade artifacts are preserved as recorded; this task does not
  rewrite their scores or remove old error evidence.
- Reproduction requires explicitly selecting the historical
  `default_v2_mini.yaml` identity because it is no longer the production default.
