# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-18
- Status: Integrity Field Note published and production-verified

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
- Squash-merged the reviewed change through PR #105 as `8a64f1bf`. Automatic
  `Aggregate Tests & Deploy` run
  [29649567174](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29649567174)
  completed build, all 51 aggregate and pinned-history contracts, Chromium
  installation, both Field Note browser suites, artifact upload, and GitHub
  Pages deployment successfully. No other workflow ran for that commit.

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
- On the deployed site, `integrity-note.json` preserved the exact checked-in
  config projection, PR #38 SHAs, disabled causal-attribution flag, and four
  missing execution identities. The public report snapshot matched exp013
  `211/220` (`95.9%`) and exp025 `181/220` (`82.3%`) across metrics, hero, chart,
  and prose while labeling `-13.6%p` as an observed, non-causal gap.
- Public desktop verification found both chart labels, five 34px chapter
  headings, 34.85px body leading, and eight source links. Public 390px
  dark/reduced-motion verification found 28px headings, 32.8px leading, both
  experiment links, all five semantic labels, no horizontal overflow, and zero
  post-settle chart mutations. The exp013 detail route showed the same
  `211/220`, `95.9%`, and `6.07/10` snapshot.

## Remaining Work

- No implementation or deployment work remains for this Integrity Field Note.
