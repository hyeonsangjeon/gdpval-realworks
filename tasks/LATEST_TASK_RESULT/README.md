# Latest task result

## PROJECT5-READOUT-ENTRY-WORKING-DIRECTORY

Corrected the fixed reader's local config-validation working directory. The one
focused offline invocation passed at tested HEAD
`5dd54709a3cbb1d0c7703503c1315babfcce6451`: 1 collected, 1 passed in 2.82s,
exit 0. It covered repository-root and `batch-runner` callers with real validators
and a synthetic writer terminal. This fixes a demonstrated local integration
defect; it is not a successful live readout or proof that the diagnostic receipt
explicitly identified that defect. Numeric score and grader accounting remain
unread, and the acknowledged grade remains consumed.

Work started from exact main `f2f62d7a01430b986d4d2e1b127695dd69ea39e0`, tree
`e9692bd592e5ad44384d9f574790c8112527c784`, in a new clean worktree. The tree
matches prior diagnostic PR711 HEAD `974e6aa48eb0c97c13bf17612d3e397e9a20ed31`,
[review 5374283415](https://github.com/hyeonsangjeon/gdpval-realworks/pull/711#pullrequestreview-5374283415),
with all 10 checks passing as reported by the leader. Those checks were not
polled or replayed and do not cover this new correction.

### Demonstrated source defect and narrow correction

The existing `pilot-readout` job invokes
`python batch-runner/codex_budget_pilot_grading.py` from repository root.
`codex_retention_grade_readout._entry` previously passed the compiled config
directly to `step8_grade.validate_grading_config`. Its `Path.exists()` checks
resolve `prompt.template` and `prompt.tool_template` against the process cwd.
The fixed config retains `prompts/grader_judge.md` and
`prompts/grader_judge_v2.md`; those files exist under `batch-runner`, not
repository root. The compiler and registration validate temporary absolute-path
copies but preserve the relative paths in emitted, hashed configuration bytes.

The bounded CI/auth/path reviewer approved the change before editing. The only
production change wraps the unchanged validation expression in
`with grade._cwd(pilot.ROOT / "batch-runner"):`. This uses the existing restoring
helper and source-derived anchor, consistent with the writer and recorded
payload projector. Hashing, entry construction and all other operations remain
outside that scope. The helper restores the caller's cwd in `finally`.

No configuration, prompt, source/hash pin, schema or validation predicate was
rewritten. There are no placeholder files, new read roles, permission changes,
fallbacks or retries. Workflow invocation, credential scope, immutable
terminal/claim/file/history checks, closed diagnostics, numeric projection and
writer/admission controls remain unchanged. The test file adds one focused
regression and a standard-library import; existing assertions remain intact.

### One offline invocation

The sole selector was
`batch-runner/tests/test_codex_retention_grade_readout.py::test_retention_grade_entry_restores_cwd_for_fixed_relative_prompts`.
It ran from repository root under CPython 3.10.12 / pytest 9.1.1, with
`GITHUB_ACTIONS=true`, synthetic `pull_request` / `pytest` metadata,
`GITHUB_REF=refs/pull/1/merge` and synthetic
`GITHUB_SHA=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee`. The process envelope was
token-free; the test used only its existing fake credential and synthetic
readout CI envelope. Existing network/process/credential guards stayed enabled.
The 180-second outer timeout did not fire. No second invocation ran.

All focused assertions completed:

- The unchanged, unscoped validator raised the exact missing-template
  `ValueError` from repository root and accepted the same compiled config from
  `batch-runner`. This control was inside the single invocation, not a separate
  reproduction run.
- Corrected `_entry` and real synthetic terminal/claim/history verification
  produced identical derived entry identities from both caller directories.
  Each verification made 1 pinned metadata call, 5 path checks and exactly
  2 terminal downloads plus 1 claim download, with no grade-payload read.
- Missing `template` and `tool_template` negatives each raised the exact real
  validator `ValueError` from both caller contexts. Negative configurations were
  fresh direct `_entry` refusal inputs, not canonical contexts accepted as
  terminal evidence. The original context and emitted JSON remained unchanged.
- A corrupted recorded config hash still raised
  `retention_grade_readout_entry_mismatch`. Cwd restoration was checked after
  every success and refusal. The real errors retained the existing closed
  diagnostic projections; transport snapshots and final no-write/admission/
  judge/model/grader-effect assertions passed.

No successful validation verdict was substituted. The old full-reader, Step8,
diagnostic and integration selectors were not replayed; no rendering, rubric
loading, payload projection or live service call occurred. Test log SHA256 is
`fd54dce861269c7021e1e2fbdeb7ccce52c610003239dccfea1d54f652b3ce89`.

### Actual readout observations, separate from offline proof

The leader directly read diagnostic
[run 36811186015 / attempt 1 / job 110206383067](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36811186015/job/110206383067)
at `f2f62d7a01430b986d4d2e1b127695dd69ea39e0`. Plan step 5 passed; read
step 6 failed. The receipt at `2026-10-01T03:38:32.2423099Z` was
`outcome=refused`, `reason=retention_grade_readout_contract_refused`,
`stage=grade_terminal`, `verification_substage=terminal_binding`,
`verification_reason=unclassified_verification_error`, `http_status=null`.
It narrows the attempted boundary but does not name `ValueError`, establish
successful claim verification or supply a numeric score or usage. The source
defect and offline reproduction are consistent with that receipt, not additional
fields recovered from it or evidence of a corrected live terminal verification.

Earlier [run 36801558936 / job 110176813572](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36801558936/job/110176813572)
at source `52e81f12c969771ae929c2456e06feb27d220f0f` passed plan step 5 and
failed read step 6 at `2026-10-01T01:35:09.8072326Z`. It reported the same
top-level reason at `grade_terminal`, with `http_status=null` and no inner
diagnostic. Writer, paid and generic jobs were skipped. The broader failed
boundary remains separate from the later diagnostic observation; neither
establishes a bad grade, numeric result or successful readout.

### Consumed grade and retained evidence limits

The acknowledged grade remains from writer
`29e0353f1539265b1741e71be894fedf9be32a8b`, run `36776393736`, job `pilot-live`,
attempt 1. Its terminal is `40712e0980cc05c31688fdbb98c693774fb90c0d`, SHA256
`11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234`, size
3119 bytes, with claim `dec305d669e3ca2e53c7f7b9ebfbe7974d661350`.
Protected approval, claim, judge, cleanup and publication succeeded in that
writer run; the safe receipts emitted no numeric score. `invoice_complete=false`
remains. The [immutable prior grade record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/974e6aa48eb0c97c13bf17612d3e397e9a20ed31/tasks/LATEST_TASK_RESULT/README.md#consumed-grade-and-evidence-limit)
preserves the publication time, other false execution/retry fields and full
receipt references. Nothing in this task reruns or rewrites that grade.

The evidence contract remains writer-recorded and publication-derived, not
independent intermediate-input reconstruction or fresh provider authentication.
The materialized-input fingerprint remains `status=unavailable`, `value=null`,
`comparison=null`, reason `materialized_input_fingerprint_not_recorded`.
The original retained result fingerprint, preparation digest and materialized
grading input retain their distinct roles. Numeric score and grader accounting
remain unread.

### History and remaining gates

The [immutable diagnostic record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/974e6aa48eb0c97c13bf17612d3e397e9a20ed31/tasks/LATEST_TASK_RESULT/README.md)
preserves tested `8b60f526d3466993597875162eb987c2b77ab8d3`, 1 passed in
8.85s, exit 0, as diagnostic-only offline evidence. Its
[separate history](https://github.com/hyeonsangjeon/gdpval-realworks/blob/974e6aa48eb0c97c13bf17612d3e397e9a20ed31/tasks/LATEST_TASK_RESULT/README.md#earlier-evidence-remains-separate)
retains the 7.20s, 7.60s and 7.82s synthetic failures, 40.06s and 43.19s passes,
and actual CI run 36793228751 / job 110150692589 with 1 failed, 13300 passed,
64 skipped and 46 deselected in 1487.18s. Their reached/unreached boundaries
are not rewritten by this pass or either live refusal.

The same immutable history preserves successful producer run 36696961231,
verified retained intake run 36739260150, older bridge evidence and the NAS
`explicit_hf_token_required` prerequisite refusal separately. Inference
accounting remains partial: 10 recorded model calls, known cost USD `0.409894`,
runtime cost null and missing `call_reachability_unknown`. It is not an HTTP
request count, grader accounting or an invoice. The original inference
`grade=null` / `grading_launched=false` receipt remains distinct from the later
acknowledged grade.

Only the two completion records changed after the tested commit. Reporting used
`experiment-report-en` followed by protected `im-not-ai-en` to replace current
status while preserving historical detail through immutable links. New-head
immutable owner review and CI remain required, followed by a new explicit
leader source-bound read instruction. No automatic retry of either failed read,
grade/inference replay, live HF/OIDC/Azure/model/grade/readout/dispatch,
permission change, Project edit or merge occurred. Earlier worktrees, records,
`wip/local-main-preserved-20260719` and the private NAS refusal directory were
preserved. The leader's unavailable M4 files were not updated.
