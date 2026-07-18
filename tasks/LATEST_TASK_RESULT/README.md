# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-18
- Status: Integrity Field Note grounded, restyled, and locally verified

## Task

- Ground `성공으로 기록됐지만 정말 성공이었을까` in exp013/exp025 report
  snapshots, checked-in experiment settings, and pinned PR #38 code history.
- Separate the observed completion gap from changes in success/retry semantics
  and stop before making an unsupported causal claim.
- Refine the note's line spacing, chapter titles, transitions, and callouts so
  readers can follow 관측→불변식→판정→비교→결정 without losing the evidence trail.

## Result

- Added `integrity-incidents.yaml` and a generator that verifies the exact
  exp013/exp025 `data.filter`, `condition_a`, and `execution` projections,
  Azure/model/mode/scope contracts, pinned PR #38 history, exact compared-field
  and missing-identity lists, and a permanently disabled causal-attribution
  flag before emitting `integrity-note.json`.
- Added a strict report selector for exact exp013/exp025 identity, date,
  condition, model, mode, 220-task scope, count/rate consistency, finite QA,
  duplicates, and malformed source data. Missing or invalid evidence hides all
  chapters, metrics, SVG, chart, mobile navigation, and source strip.
- Removed duplicated `95.9/82.3`, success counts, retry count, and chart values
  from the article and hero. The deployed data path now derives an observed
  `-13.6%p` and `-30` success difference from report snapshots while labeling
  both as observations rather than PR #38 effects.
- Pinned history tests prove that `_AVAILABLE_FILES` changed only in memory
  before the fix and was persisted afterward, and that determined QA failure
  began setting `qa_failed`. The article also preserves the undetermined-QA
  exception and notes that the Anthropic parsing fix is irrelevant to two
  Azure runs.
- Added eight direct links to generated evidence, pre-fix runner, core fix,
  follow-up, PR #38 merge, and both experiment details. Report data is labeled
  as a deployment-time snapshot rather than an execution-time revision.
- Restyled only this note with five short chapter headings, semantic labels,
  wider vertical spacing, 2.05 body leading, and quieter serif callouts. Other
  Field Notes retain their existing density.
- Extended Pages freshness to the integrity source and combined the existing
  runtime browser suite with integrity desktop/mobile/null/duplicate/invalid-
  list/stale-route verification before artifact upload. Batch remains manual.

## Verification

- Focused integrity source/selector contracts: **9 passed**; full aggregate
  suite: **51 passed, 0 failed**. Production TypeScript/Vite build and
  `git diff --check` passed.
- Pinned git-history checks verified both core/follow-up ancestry and exact
  before/after code behavior. Exact-list tests reject null, duplicate,
  replacement, and added compared fields or missing identities.
- Checked-in Playwright passed for runtime and integrity notes against the same
  production build. Integrity coverage includes 1280px desktop, 390px
  dark/reduced-motion, source URLs, both experiment links, null/malformed/
  duplicate/invalid-list data, and stale route transitions.
- Browser measurements found 34px/34.85px desktop heading/body rhythm and
  28px/32.8px mobile rhythm, all five chapter labels, two chart ticks, eight
  evidence links, no horizontal overflow, and zero post-settle chart mutation.
- `first-reviewer` approved the final causal boundary, strict parsing,
  typography, and browser coverage. `extreme-reasoner` approved the Pages gate
  after full-suite rerun and confirmed model/API, Azure, HF write, batch,
  grading, and paid-workflow impact is **zero**.

## Remaining Work

- Commit and publish the reviewed branch, then verify the GitHub-hosted combined
  browser gate and public article against the deployed generated evidence.
