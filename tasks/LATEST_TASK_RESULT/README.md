# Latest substantive task result

## PROJECT5-PR647-PARENT-SNAPSHOT-1118

The GPT-5.4 input-bundle test now permits only the intended parent-directory
link-count change when publication creates a child directory. The seven
requested cases passed. This correction changes the existing test and the two
completion records only; production behavior, canonical validation, source
pins, task order, controls and workflow YAML are unchanged.

### Source integration and supplied hosted failure

One `git fetch --no-tags origin main` returned 0 and exact main
`928c3a7e69b28508505479198d329c23c5de8594`. Ordinary merge
`eac39af656861549e572e9b6b8df24d03bd84580` integrated that baseline into this
feature branch. Only the expected latest-result conflict required resolution;
there was no production conflict. The changelog retains the complete earlier
two-preparation/Step 1 operational entry and the Step 0 fix entry. The old
records branch and real artifacts were not touched.

The leader supplied Backend run `35677536185`, `comparison-contracts` job
`106587081789`, completed `2026-09-22T02:14:34Z` at
`928f4576848b73f0f22285747685148d9e52a317`. It reported
`3 failed, 939 passed in 1022.89s (17:02)`. All failures were the
`codex_r1`, `codex_r2` and `relocated_codex` cases of
`test_run_input_bundle_is_exact_atomic_and_gates_execution` in
`batch-runner/tests/test_gpt54_run_input_bundle.py`, at the old line 730.
No hosted logs were queried and the job was not rerun locally.

`_tree_snapshot()` records mode, link count and regular-file bytes or symlink
target. Codex intentionally creates `batch-runner/workspace`, which changes
the existing `batch-runner` directory's link count on the hosted filesystem.
Publication and `_assert_complete()` had succeeded before the stale parent
preservation assertion failed. The old assertion exempted only `data`.

### Narrow correction and validation

The replacement still compares every previously existing row. For `data` when
`data/gdpval-local` is created, and for `batch-runner` when Codex creates
`batch-runner/workspace`, it requires the child to be absent before and a
directory afterward. It preserves the parent's exact mode/type and payload
and permits only an unchanged link count or an increase of 1. This accounts
for filesystem-specific directory metadata; it does not relax single-link
regular-file requirements.

All other rows remain exactly equal, including existing file bytes/link counts
and symlink targets. The exact added-file set, canonical manifest binding,
no-clobber and read-only verification assertions remain intact. V2's
`batch-runner` parent receives no exemption.

Tested correction commit: `0c5074665cd01be89e9d380614903471ab819f0f`.
The later completion-record commit is outside that tested commit. Exactly one
focused invocation ran:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[codex_r1]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[codex_r2]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[relocated_codex]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[v2_r1]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[v2_r2]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[relocated_v2]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[existing_data_parent]'
```

Result: `7 passed in 7.30s`, exit 0. No additional changed row, failed local
attempt or targeted rerun occurred. `git diff --check` passed. This is focused
synthetic validation, not a passing verdict for the full comparison job.

### Preserved implementation evidence

Implementation `8728c350266578c299dd64b974f9368288de09d7`, originally based on
`778a627bbb5404f33e5e62019382fa107aa47840`, reported
`45 passed, 319 deselected in 18.36s`, exit 0, for this earlier command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt54_run_input_bundle.py batch-runner/tests/test_gpt54_disposable_checkout.py batch-runner/tests/test_gpt54_workflow_gate.py batch-runner/tests/test_gpt54_comparison_preflight.py -k step0_manifest
```

Those cases used synthetic parquet/reference/manifest bytes and explicit
test-only pins. They exercised the actual materializer, local loader,
`NeedsFilesManifest` checks and Step 1/capture, including five ordered tasks.
That selection remains valid evidence under its original scope; it was not
rerun and never established a passing full comparison job. Neither result
establishes a new real-data preparation or original-data Step 1 success.

### Review boundary, remaining work and skills

The leader's diagnosis is not a new implementation approval. Earlier review
`5273344624`, `FINAL-APPROVE` at `259f50567e95c07b720ac51a3f020453fad449bf`,
covers operational records only. The current fix/correction still needs implementation review and
fresh final-HEAD automatic CI; neither was polled or awaited for this result.

All six preflight blockers and false launch flags are unchanged. Any separately
authorized real preparation still needs an explicit local source of the
existing canonical Step 0 manifest bytes. No real prepared checkout, partial,
input source, cache, handoff or GHCP bundle was opened, repaired or retried. No model,
provider, Step 2, VM, grading, Azure/HF, credential or paid operation ran.
No full suite, 942-case job, original 45-case selection or manual workflow ran.

The full skill catalog was inspected once. `experiment-report-en` keeps the
hosted failure, focused correction and historical synthetic evidence separate;
`im-not-ai-en` preserves their literals and qualifications. `experiment-design`
does not apply because no experiment/control changed. No production or
workflow change requires backend architecture or `extreme-reasoner` guidance.
UI/animation, repo-readiness and new tooling are outside this correction.
