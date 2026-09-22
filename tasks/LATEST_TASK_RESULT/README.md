# Latest substantive task result

## PROJECT5-PR647-CANONICAL-HANDOFF-1148

The one authorized Step 0 candidate was a safely readable single-link regular
file, but its bytes were not canonical. The unchanged validator refused it at
the full-byte digest check, exit 2. No preparation or execution was attempted.
This update changes only the two completion records. Production, tests,
configuration and workflows remain frozen at the reviewed HEAD.

### Single-candidate result

Exactly one named candidate for `workspace/step0_needs_files_manifest.json`
was checked from source `0913891fcbcfe2119c2899535a5e2b017cd99eee`. The check
held directory descriptors, opened each path component without following
links, required a single-link regular file and checked that its identity and
metadata stayed stable across one byte read. The active policy and canonical
digest map were the unchanged `deliverable_only` contract.

| Observation | Result |
|---|---|
| Bytes read | `56057` |
| Observed SHA256 | `16778d3ae830232e1c59070ad9254b926045e3bff3f67a3d6186b3c593c8a0e7` |
| Required canonical SHA256 | `463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512` |
| Verdict / phase / static refusal code | `named_candidate_refused` / `canonical_digest` / `canonical_validation_refused` |
| Exit status | `2` |

`require_canonical_manifest_bytes()` rejected the full bytes. The check stopped
before JSON/schema validation, so it does not claim schema 4 acceptance. There
was no second read, alternate locator, directory search, copy, repair or
accepted-source handoff. The source file was read only. This result applies
only to the named candidate; it does not establish that no valid canonical
source exists elsewhere. No private path or source content is published here.

### Source integration and supplied hosted failure

During the preceding correction, one `git fetch --no-tags origin main`
returned 0 and exact main
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

### Preserved parent correction and seven-case validation

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
Subsequent completion-record commits are outside that tested commit. That
earlier correction used exactly one focused invocation:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[codex_r1]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[codex_r2]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[relocated_codex]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[v2_r1]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[v2_r2]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[relocated_v2]' 'batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution[existing_data_parent]'
```

Result: `7 passed in 7.30s`, exit 0. No additional changed row, failed local
attempt or targeted rerun occurred. `git diff --check` passed. This is focused
synthetic validation, not a passing verdict for the full comparison job.

### Preserved implementation evidence

The Step 0 fix requires an explicit local canonical manifest for Codex input
preparation, installs its full bytes at the consumer's workspace role, binds
size/SHA256 and verifies current bytes before reporting ready. The materializer,
checkout/API/CLI, verifier, workflow helper, source pins, fixtures and
documentation cover that role. V2 semantics, fixed five-task order, comparison
controls and the canonical validator remain unchanged. The parent correction
changes only the test expectation for the intended directory mutation.

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

The leader reviewed the complete Step 0 implementation, narrow parent-snapshot
correction and records at `0913891fcbcfe2119c2899535a5e2b017cd99eee` and posted
`FINAL-APPROVE` review `5273753355`, with no high-confidence correctness findings.
That immutable review does not assert final-HEAD CI passed, prove a real
canonical source exists, establish real Step 1 success or authorize model/paid
execution. This later candidate check and records update are outside its
boundary. Earlier review `5273344624`, `FINAL-APPROVE` at
`259f50567e95c07b720ac51a3f020453fad449bf`, covers operational records only.

Fresh carrying-HEAD automatic CI remains unobserved. No CI query, fetch,
integration, new review job or waiting occurred for this handoff. Only bounded
record-to-observation, editorial and whitespace checks were performed; no
tests or earlier runtime validations were rerun. After publication, the branch
remains frozen for final carrying-HEAD checks and the leader's disposition.

All six preflight blockers and false launch flags are unchanged. Any separately
authorized real preparation still needs an explicit local source of the
existing canonical Step 0 manifest bytes; the named candidate does not satisfy
that requirement. No real prepared checkout, old partial, original parquet or
reference source, cache, prior handoff or GHCP bundle was opened, repaired or
retried. No preparer, Step 1, Step 2, model, provider, VM, grading, Azure/HF,
credential or paid operation ran. No blocker or launch flag was cleared, and
no runtime result or Project-card completion is claimed.

The full skill catalog was inspected once. `experiment-report-en` keeps the
single-candidate refusal, immutable review, hosted failure and two historical
synthetic selections separate; `im-not-ai-en` preserves their literals and
qualifications. The condition audit was performed locally because no new
review job was authorized. `experiment-design` does not apply because no
experiment/control changed. No implementation or workflow change requires
backend architecture or `extreme-reasoner` guidance. UI/animation,
repo-readiness and new tooling are outside this records/input-handoff task.
