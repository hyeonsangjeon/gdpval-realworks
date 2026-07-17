# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-17
- Status: Stage A corrected rerun accepted; Stage B preflight pending

## Task

- Run the corrected Stage A cohort once from merged `main`.
- Audit the committed grade and analysis against every preregistered runtime,
  identity, usage, provenance, cost, and wall-clock gate.
- Permit Stage B preflight only if Stage A passes without qualification.

## Result

- Corrected run `29572067428` completed from
  `main@fd6d5267fcc15afc144d8de93dc98b0e8b52ed2f` in 44m12s. Grade and
  analysis commits are `9473d9021fc4583a68a4bc338c8aecf4aa5bffdd` and
  `defe85a6bba87181e77f10c9503105104b12e316`.
- All 153 rubric items reached the judge: 143 text, 6 formatting, and 4 visual,
  with zero automatic prechecks. Verdicts were 43 pass, 99 fail, and 11
  partial; judge errors and score-excluded items were zero.
- Actual render/perception counts were exactly 4/4. Every visual item called
  perception once and persisted one relative, task-confined provenance entry.
- Item, task, and summary usage were complete and internally consistent.
  Totals were 532 main API calls, 4,545,150 input tokens, 177,563 output
  tokens, and 1,955,328 cached tokens.
- Nine empty max-output finals were recovered by the bounded tool-free retry.
  No runtime error, resume, auto-dispatch, API-key fallback, or unrelated grade
  workflow occurred.
- Full schema/identity/path audit found no payload, data URL, absolute path,
  traversal, cross-task path, or secret marker. Artifact wall-clock was 24.9
  minutes; raw/effective estimates were USD 1.32 / USD 1.08.
- Stage A passed every preregistered gate. Independent grading-engineer review
  confirmed the PASS. The `36.14%` score is descriptive, not a quality claim.

## Verification

- Workflow `29572067428`: success, `rc=0`, no resume or child dispatch.
- Grade schema, exact identity/task order, 153 item routes, all instrumentation,
  4/4 visual calls, usage, and generated analysis: **PASS**.
- Persisted provenance and recursive payload/path/secret scan: **PASS** with
  four provenance entries and zero violations.
- Cost/time gates: **PASS** at USD 1.08 effective and 24.9 artifact minutes.
- Independent grading-engineer gate review: **PASS**, Stage B exact model-free
  preflight allowed.

## Remaining Work

- Assemble and validate the exact first-10 pinned deliverable tree.
- Run the model-free Stage B planner on clean current `main` and record exact
  route/render/perception counts and identities.
- Dispatch Stage B once only if preflight returns no errors and no other grade
  workflow is active; then audit every Stage B gate before considering a full
  220-task run.
