# Latest task result

## Project5 independent comparison runtime launch refusal — 2026-10-05

Both direct comparison capture entrypoints now refuse independently of valid
local source/input evidence. The shared, argument-free
`require_comparison_runtime_launch()` raises
`comparison_runtime_launch_refused`; no caller, environment, manifest or marker
can enable it. Invalid evidence may still refuse earlier. V2 refuses before
capture publication/probes, and both paths remain blocked before provider/auth/
model-child setup. Absent/non-comparison behavior and model-free bundle
verification/materialization APIs remain unchanged. Profile recognition is
still deferred; this is not launch authorization.

### Source and historical boundaries

The fresh source worktree began at accepted main
`c6fbf893595336e0a89ceb122ac5859991487144`, tree
`c04f7331bec0bfa794f5eb16c691d4675cca6442`, obtained by an ordinary origin fetch
of that exact missing commit. Its production code was unchanged from reviewed
source `14d7579c2578cb2a09397b5d42f41e7b5daaf2d7`. Existing worktrees and inputs
were preserved.

The leader supplied prior PR745 evidence: reviewed HEAD
`78620a6b35e6ad4747f36feb41553fe9bff48fdc`, owner
[review5408853800][prior-review] and all 9 applicable checks passed. This is
accepted prior evidence, not review or CI for the new implementation. The
same-session pre-edit source/grade-provenance review identified the independent
runtime refusal as the prerequisite; no separate reviewer invocation was made.

Production changes are limited to `gpt54_codex_input_capture.py` and
`gpt54_v2_input_capture.py`. Only their two source bindings change in the
separately named prospective profile; its new raw-file SHA256 is
`6c93ab4664e69bb00e444779110a5158f8024e45188964c8b18db8ed0a0f0b54`.
Directly coupled tests retain genuine frozen-source refusal inventories in
manifest order and now expect intentional runtime refusal rather than capture
success. No CURRENT observer registry repin was required or made.

The historical comparison manifest remains byte-for-byte at SHA256
`3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1`.
The actual whole grader TEMPLATE closure remains
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`, not a
materialized-grader identity. Historical compiler/core/Step2/grader/workflow
files, closed registrations, paid `RESULT/PARENT/READER`, fixed-evidence digests,
baseline pin-set, original input identities and canonical Step0 are unchanged.
Model, effort, task order, ABBA20, limits, run IDs, schema and false-launch fields
are unchanged. The separate 30-cell pilot and 8-cell retention study stay closed.

### Original pinned offline proof

Implementation HEAD `e2f04171f5812dd1f2044f6b807c62267efb3b64`, tree
`edb7d235274b8cec61e0197c7a1fff513cd45e01`, was clean before and after the
single authorized invocation. From `batch-runner/`, the exact command was:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 timeout --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -ra -x --tb=short --color=no -p no:cacheprovider -m "not integration" tests/test_gpt54_codex_input_capture.py tests/test_gpt54_disposable_checkout.py -k comparison_runtime_launch_boundary
```

Result: **57 passed, 185 deselected in 52.69s; exit 0.** Recorded process times
were 2026-10-05T00:38:33Z–2026-10-05T00:39:26Z. The 300-second bound plus
5-second termination grace applies to this software-regression invocation,
not a CI timeout or experiment budget. No retry or wider suite ran.

| Private evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| Exact command, including final newline | 543 | `5a4be8ee555f2bf29188e51a9e0ab030f91499c1e2e57c4db6480e5141f91d4b` |
| Combined pytest stdout/stderr | 7758 | `5e9cf35d75a264aed14a0bf3211cbd4ee778ca6331af70e82390634a784be328` |
| Process status | 74 | `bfe80cd7135bad3985c656e47a9663ee69d244f1b2534c9c9885a2c5b8c27f57` |
| Receipt | 1921 | `e9869b38bde30081f86325a82d3758f2a0d1048c16879c1e65850c0fcd11e1f4` |

The selector covers caller/environment no-enablement, genuine compilation of
the tracked prospective manifest and the real whole-template closure, and
frozen comparison/pilot source refusals. It exercises both actual capture
entrypoints with synthetic source/input evidence and forbidden-effect sentinels,
including source/marker tampering and no capture publication. Capture-unit
fixtures isolate Git lineage; separate model-free temporary-Git cases retain
real source/marker/HEAD binding, no-clobber, reservation and partial-failure
checks. No test patches the new launch guard to pass. Non-comparison cases
reach their existing synthetic sentinel boundary, not real provider/auth calls.

These are regression fixtures, not observations of private originals or proof
that runtime profile selection works. No archive, original, prepared artifact,
marker or earlier private receipt was reopened; no import or preparation ran.
No real Step1/Step2/Step8, model, grading, HF/Azure call or workflow dispatch ran.
Evidence remains private; only safe identities and this non-input command are
published.

### Runtime-checkout contract correction and separate proof

The leader reviewed immutable HEAD `07b83ef8944a1ac35e3721fda82efb81d53718bd`,
tree `133da32505dce5f30db502f4e96692daa87d6636`, and supplied the actual
comparison-contracts CI run37249091204/job111572837265 result: **4 failed,
1060 passed in 1450.43s**. All four failures were the positive r1/r2 cases in
`test_runtime_checkout_lineage_precedes_both_providers`. They still expected
`ProviderBoundary` and a V2 capture after the new launch guard correctly refused.
This is leader-read CI evidence, not a new local discovery or CI query. The
[original proof and initial three-document delta][prior-launch-proof] remain
separate, unchanged evidence; the 57-case selector was not rerun.

Only that test function and its directly coupled assertions changed. Real
temporary-Git lineage and input binding must both succeed before the explicit
launch refusal. Codex must raise the exact `ComparisonRuntimeLaunchRefused`
class with `comparison_runtime_launch_refused`; V2 must return CLI status 1
with that exact output reason. No host/auth/provider/free-safety boundary may
be reached. V2 publishes no capture or new workspace artifact, and Codex's
existing model-free capture bytes remain unchanged. Full-tree equality includes
directories. Read-only Git restrictions, the 37-source inventory, false-launch
assertions and all negative lineage cases are preserved; the negative cases
were not rerun in this four-case invocation. Production, both manifests,
fingerprints, compiler, core, grader, workflows and runtime selection are
unchanged from the leader's source-reviewed HEAD.

The test-only correction was pinned at HEAD
`90b9a50ec46411f8b11ee148be57e0511fd59471`, tree
`513ae06a80b088208230edb23110efd5140c8c17`, with a clean worktree before and
after proof. From `batch-runner/`, exactly these four node IDs ran once:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 timeout --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -ra -x --tb=short --color=no -p no:cacheprovider -m "not integration" 'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r1]' 'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r1]' 'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r2]' 'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r2]'
```

Result: **4 passed in 9.81s; exit 0.** Recorded UTC process times were
2026-10-05T01:28:41Z–2026-10-05T01:28:51Z. The 300-second bound and 5-second
termination grace apply only to this test invocation, not CI or experiment
budgets. The log names each of the four completed cases. No retry, broader suite
or real-input operation ran; synthetic fixtures are not comparison observations.

| Private corrective evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Exact command, including final newline | 851 | `e9aa74c37a831557b437077ef82d6cba88142ab269dd63e7fa033fa3f8243ed5` |
| Combined pytest stdout/stderr | 905 | `678f25b4fea7716030cb15f337543cd2552e11fc015289ccb89695d130b8091e` |
| Receipt | 1971 | `26f136f442d93050671c4518e72cf4070dc29086fecee0ce681b40b19eafdec4` |

### Remaining work and preserved evidence

Only `CHANGELOG.md` and this single current task record change after the
four-case corrective proof; the pinned test bytes remain unchanged. Final
corrected-HEAD review, applicable CI and leader acceptance remain pending.
No carrying-PR future merge state is asserted.

Runtime/workflow profile recognition, native call/token caps, dispatcher and
credentialed-CI input authority remain unresolved. The credentialed workflow
intake proposal remains REJECTED; a local artifact or this guard does not grant
CI-read or launch authority. All separate launch refusals remain in force, and
the registered 20-observation comparison remains unexecuted. This work provides
no evidence of served model identity, wire consumption, inference, a grade,
model success or cost.

The [first local V2 preparation][prior-preparation] remains bound to its reviewed
`14d7579c2578cb2a09397b5d42f41e7b5daaf2d7` source. Its one-operation permission
is consumed; it was not adopted, relabeled or prepared again. Later preparation
requires a newly reviewed source and separate direction. The [immutable prior
profile record][prior-profile] retains the 60-case/2-case/5-case proofs and the
separate incomplete/continuation evidence covering 24 selected cases. None was
rerun. This page replaces stale task status rather than appending full history.

experiment-design kept the existing configuration-bundle scope fixed while the
two prospective bindings changed. im-not-ai-en protected the facts, hashes,
commands, links, uncertainty and refusal conditions in these bounded English
records. No new experiment or configuration axis was added.

[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/745#pullrequestreview-5408853800
[prior-preparation]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c6fbf893595336e0a89ceb122ac5859991487144/tasks/LATEST_TASK_RESULT/README.md
[prior-profile]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fd903b96dc8d4622470b6971fde820334c16396b/tasks/LATEST_TASK_RESULT/README.md
[prior-launch-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/07b83ef8944a1ac35e3721fda82efb81d53718bd/tasks/LATEST_TASK_RESULT/README.md
