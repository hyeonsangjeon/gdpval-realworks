# Latest task result

## Project5 model-free workflow profile handoff — 2026-10-05

`gpt54_workflow_gate` now carries an explicit manifest selection through local
source validation, preparation and verification. The optional API
`manifest_path` and local CLI `--manifest-path` select a repository-relative
execution_envelope YAML. The existing validators bind its regular tracked blob,
working bytes, size and digest to the request's reviewed commit. There is no
fallback to another path or source. Omission retains the historical path and its
current-source refusal behavior.

Verification forwards the independently validated `request.reviewed_source_sha`
as `expected_reviewed_source_sha`, never a value from the target HEAD or markers.
The selected source blob must match the manifest identity in the config marker
bound by checkout-ready. Source/event/workflow identities, the detached target
HEAD/tree, compiled commands and cwd remain one binding. Final source/marker
rereads, held directories, reservations and quarantine remain enforced.
Verification writes nothing, and its JSON evidence shape is unchanged.

The path is local metadata selection, not a new workflow input or launch control.
`WorkflowRequest` keeps its strict schema. `require_workflow_launch` still
revalidates and refuses the false compiler launch flags; the dispatcher remains
unimplemented. Even after valid model-free preparation, the CLI returns status 2
through that refusal. Both direct `comparison_runtime_launch_refused` guards and
their runtime callers remain byte-for-byte unchanged. No marker, environment
variable or caller toggle enables execution.

### Reviewed basis and source boundaries

The fresh worktree began at accepted main
`3419e7db30784bd89034b95253f9f4698acae6f2`, tree
`ae8b532157850ad6475bf6934b97fc736ca631de`, after an ordinary origin fetch
of that exact missing object. The leader supplied prior PR747 evidence:
source-reviewed `3b8168be6df9ec674c44065a654081597e28c1e2`, owner
[review5409728758][prior-review], all 11 applicable checks successful and PR-only
deploy skipped. This is accepted prior evidence, not review or CI for the new
implementation. The pre-edit source/provenance review used the same-session
direct charter-role method, not a separately spawned reviewer.

Production behavior changes only in `gpt54_workflow_gate.py`. Its one prospective
source binding advances. The workflow helper is not in the CURRENT observer
dependency set, so no observer repin is required. Directly coupled test refusal
inventories add this newly changed helper while preserving the historical hashes
and substantive frozen-plan refusals.

| Changed source identity | SHA256 |
| --- | --- |
| Workflow gate | `714a9e18fe5a3df54f54d472b772bfb958966c807ebe30dab7efc9428a062626` |
| Prospective local-source manifest | `81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe` |

The historical comparison manifest remains byte-for-byte at SHA256
`3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1`.
The actual whole grader TEMPLATE closure remains
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`, not a
materialized-grader identity. The accepted checkout helper, capture modules,
compiler/core/Step2/grader/Actions workflow files, paid `RESULT/PARENT/READER`,
frozen registrations, fixed evidence, original input hashes and canonical Step0
remain unchanged. Model, effort, task order, ABBA20, limits, run IDs, schema and
false-launch fields remain fixed. The separate 30-cell pilot and 8-cell retention
study stay closed.

### Pinned offline proof

Implementation HEAD `5b72b56d3d69c7fcd322da78d12586380f625b21`, tree
`fe1112327564d61f6c9af275f1cb254cdd133667`, was clean before and after the
single authorized invocation. From `batch-runner/`, the exact command was:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR="$PROJECT5_VALIDATION_ROOT" PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 timeout --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -ra -x --tb=short --color=no -p no:cacheprovider -m "not integration" --basetemp "$PROJECT5_VALIDATION_ROOT/pytest" tests/test_gpt54_workflow_gate.py -k workflow_profile_anchor
```

`PROJECT5_VALIDATION_ROOT` named a fresh private temporary directory; its exact
binding is retained in the private source metadata. Restrictive umask 077 and
no-clobber log output were used. Temporary Git repositories and synthetic inputs
stayed inside that new validation root; previous worktrees and inputs were not
touched.

Result: **64 passed, 67 deselected in 102.84s; exit 0.** Recorded process times
were 2026-10-05T04:10:33Z–2026-10-05T04:12:17Z. The 300-second limit plus
5-second termination grace applies only to this software-regression invocation,
not a CI timeout or experiment budget. No retry or wider suite ran.

| Private evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| Exact command, including final newline | 567 | `1ff99750c84a0264523e97e8e7bee718668dcead4835f202d8ffb152ce24e2f1` |
| Combined pytest stdout/stderr | 8071 | `5135bcf0a846c4f6c53d8367e75f2de2bb5bfcaf56a0d3380c684fe96d1895a1` |
| Source metadata | 857 | `9a44dcf9a23fdcafce02f98d05154d834b1d8a709d55f02ae60e5db962d26e4f` |
| Process status | 280 | `1409b08d8c9a1a29d22b992e2ad56192ca2a010cacedf0632d9d5d1faa7c66af` |
| Receipt | 1903 | `09a1c10f72f6eb0f46188a93cf2a589f99cf9d91b6605846eff2df998a78c59b` |

The new selector uses real temporary Git and source validators. The prospective
production manifest compiles with genuine source pins and the real whole-template
closure. Preparation fixtures change only original-data identities and bytes;
they are not observations of the private originals. The existing byte-state-checked
compiler cache preserves the real closure check, and no anchor/blob validator or
launch guard is bypassed.

Positive cases cover both owners through the API and local CLI, with explicit
prospective selection and historical default/explicit selection. Other cases check
independent anchor forwarding, a coherent alternate target commit/marker set,
wrong source/event/workflow SHA, untracked/unsafe/altered manifests, selected-path
substitution, immutable commands/cwd, final source/marker/HEAD/directory races,
reservation/quarantine precedence, no-clobber and retained handoff failure.
No-write snapshots and provider/auth/probe/model-child/command sentinels remain
intact. The mandatory launch refusal is observed after valid model-free evidence.
These are software regressions, not runtime equivalence, wire consumption, served
identity, grades, experiment outcomes or model-cost measurements.

### Remaining work and preserved evidence

Only `batch-runner/README.md`, `CHANGELOG.md` and this single current task record
change after proof. Tested production/config/test bytes remain pinned. Final
fixed-HEAD review, applicable CI and leader acceptance remain pending. Actual
Actions/capture profile selection, native call/token caps, dispatcher,
credentialed-CI input authority and launch authorization remain unresolved.
The credentialed workflow-intake proposal remains REJECTED, and the registered
20-observation comparison remains unexecuted.

No real input, archive, prior private receipt or consumed prepared artifact was
opened, imported, prepared, adopted or relabeled. No real Step1/Step2/Step8,
provider, grading, HF/Azure operation or CI query/dispatch ran. The [first local
V2 artifact][prior-preparation] stays bound to reviewed
`14d7579c2578cb2a09397b5d42f41e7b5daaf2d7`; any changed-source preparation
requires separate fixed-HEAD review and direction. Raw evidence and private paths
stay outside Git; only safe identities and the non-input command appear here.

The [immutable prior anchored-verifier record][prior-anchor] preserves its
57-case proof. The [launch-boundary record][prior-launch] preserves the earlier
57-case and separate 4-case proofs. The [prior profile record][prior-profile]
retains its 60/2/5-case and incomplete/continuation evidence for 24 selected cases.
None was rerun. This page replaces stale task status instead of appending full
history.

experiment-design kept the registered configuration-bundle scope fixed during
the prospective binding update. im-not-ai-en protected exact evidence, links,
uncertainty and refusal conditions in these bounded English records. No new
experiment, condition, budget or axis was added.

[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/747#pullrequestreview-5409728758
[prior-anchor]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/3419e7db30784bd89034b95253f9f4698acae6f2/tasks/LATEST_TASK_RESULT/README.md#project5-independently-anchored-prospective-profile-verification--2026-10-05
[prior-launch]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c28847f1b0e3626a088a746558cda82aca67c127/tasks/LATEST_TASK_RESULT/README.md#project5-independent-comparison-runtime-launch-refusal--2026-10-05
[prior-preparation]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c6fbf893595336e0a89ceb122ac5859991487144/tasks/LATEST_TASK_RESULT/README.md
[prior-profile]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fd903b96dc8d4622470b6971fde820334c16396b/tasks/LATEST_TASK_RESULT/README.md
