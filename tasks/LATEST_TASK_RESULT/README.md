# Latest task result

## Project5 independently anchored prospective-profile verification — 2026-10-05

`verify_runtime_checkout` now accepts `expected_reviewed_source_sha` for an
explicit, read-only metadata-verification mode. The caller supplies that full
lowercase commit SHA independently of the checkout and its markers. The held
ready SHA and detached HEAD must match it; its tree is resolved independently.
The fixed config-ready marker's bound bytes supply `manifest_file.path` only
as a locator, and the selected regular tracked YAML blob must match the exact
expected commit, working bytes, size and digest. Self-consistent mutable
markers do not establish source-review authority.

The same path reaches config/input validation and the canonical checkout
marker. Config-marker and manifest metadata are each limited to 1 MiB. Local
Git retains its 60-second command bound, closed environment and disabled
transport; blob size is checked before its bytes are read. Quarantine,
reservations, held directories and final rereads remain enforced. Verification
writes nothing and returns only the unchanged preparation marker, never
approval, launch permission or dispatch capability.

Omitting the anchor, or passing `None`, keeps the historical manifest path.
No runtime/workflow caller selects the new mode. Both capture modules and the
unconditional `comparison_runtime_launch_refused` guard are byte-for-byte
unchanged. No environment, marker, ref or caller toggle enables launch.

### Reviewed basis and source boundaries

The fresh worktree began at accepted main
`c28847f1b0e3626a088a746558cda82aca67c127`, tree
`7b835f63de87862828337e8ccb5d915d86f9dd22`, after an ordinary origin fetch
of that exact missing object. All previous worktrees and inputs were preserved.
The leader supplied prior PR746 evidence: source-reviewed
`cab0f6e1c49eb41f3ea6ab5021e3333816dc61f1`, owner
[review5409330647][prior-review], all 11 applicable checks passed and PR-only
deploy skipped. That is accepted prior evidence, not review or CI for this
implementation. The pre-edit source/provenance review used the same-session
direct charter-role method, not a separately spawned reviewer.

Production behavior changes only in `gpt54_disposable_checkout.py`. Its one
prospective binding and the explicitly CURRENT observer dependency advance;
the latter also requires its CURRENT test/report fingerprint to advance.
The existing synthetic fixture gains an explicit current-source supplier while
preserving its historical default. Neither source-pin nor grader-closure
validation is replaced.

| Changed source identity | SHA256 |
| --- | --- |
| Checkout helper | `77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62` |
| CURRENT observer facade | `0e2b920875fb5597406e267a8b838e80fcd55d6958ded1e4286516036cb44038` |
| Prospective local-source manifest | `c9bc6bc669005ec4c16cd1a0d98f3ee91443aab2f2b3727c6bc55c1a770836d6` |

The historical comparison manifest remains byte-for-byte at SHA256
`3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1`.
The actual whole grader TEMPLATE closure remains
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`, not a
materialized-grader identity. Compiler/core/Step2/grader/workflow files, paid
`RESULT/PARENT/READER`, frozen registrations, fixed evidence, original input
hashes and canonical Step0 remain unchanged. Model, effort, task order, ABBA20,
limits, run IDs, schema and false-launch fields remain fixed. The separate
30-cell pilot and 8-cell retention study stay closed.

### Pinned offline proof

Implementation HEAD `32f352679be102f193abce3d4710252bdb5f09f2`, tree
`5ea471a9c944d6b3f01dd1ab9d560ccdea220c81`, was clean before and after the
single authorized invocation. From `batch-runner/`, the exact command was:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 timeout --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -ra -x --tb=short --color=no -p no:cacheprovider -m "not integration" tests/test_gpt54_runtime_checkout.py tests/test_codex_retention_observer_source.py -k anchored_prospective_verification
```

Result: **57 passed, 51 deselected in 104.75s; exit 0.** Recorded process times
were 2026-10-05T02:46:56Z–2026-10-05T02:48:41Z. The 300-second limit plus
5-second termination grace applies only to this software-regression invocation,
not a CI timeout or experiment budget. No retry or wider suite ran.

| Private evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| Exact command, including final newline | 545 | `5d5dea2b8baa9b911ac0923a555dde1adf02a0f37166d00be89d477bfa6fe522` |
| Combined pytest stdout/stderr | 6490 | `0a91c29f8c204166b552fa4ece6938d95369b4fc843c79ca8217dacb2deba98b` |
| Source metadata | 469 | `496682909618c4134d5c7e6901bf482d3420d5ab3fd33699c7aee2fd237cdfdc` |
| Process status | 197 | `6247583bd7cda0c03576c2c6188685a502ad499141f8e8fe68d6da78094f13a8` |
| Receipt | 2237 | `cf9fbef9163474dbaab66af817133a3cfe47207c5c7b51fbc959b324204debc3` |

The new selector uses real temporary Git, genuine current source pins and the
whole-template closure through the existing byte-state-checked cache. Only
original-data identities and bytes are synthetic. Positive V2/Codex cases use
the real preparer and input verifiers, with no patched anchor/blob checks.
Negatives cover missing, wrong, ref/tag and malformed anchors; a coherent
alternate commit/manifest/marker set; untracked, unsafe, symlink, hardlink,
blob, digest and path substitutions; input/source drift; quarantine and
reservations; and final file/directory/HEAD races. No-write snapshots and
provider/auth/probe/model-child/capture-publication sentinels remain intact.

Separate cases retain genuine historical-default lineage/input binding before
both direct runtime launch refusals, and show that successful prospective API
verification does not select that profile for the V2 caller. CURRENT observer
compatibility still rejects helper tampering; the explicit historical paid-source
negative remains `reviewed_retention_reader_required`. No launch guard is patched.
These are software regressions, not private-original observations, measured
runtime equivalence, served identity, wire consumption, a grade or cost evidence.

### Remaining work and preserved evidence

Only `batch-runner/README.md`, `CHANGELOG.md` and this single current task
record change after proof. Tested production/config/test bytes remain pinned.
Final fixed-HEAD review, applicable CI and leader acceptance remain pending.
Runtime/workflow profile selection, native call/token caps, dispatcher,
credentialed-CI input authority and launch permission remain unresolved.
The credentialed workflow-intake proposal remains REJECTED, and the registered
20-observation comparison remains unexecuted.

No real input, archive, prior private receipt or consumed prepared artifact was
opened, imported, prepared, adopted or relabeled. No real Step1/Step2/Step8,
provider, grading, HF/Azure operation or CI query/dispatch ran. The [first local
V2 artifact][prior-preparation] stays bound to reviewed
`14d7579c2578cb2a09397b5d42f41e7b5daaf2d7`; a changed-source preparation
requires separate fixed-HEAD review and direction. Evidence files remain private;
only safe identities and the non-input command appear here.

The [immutable prior launch-boundary record][prior-launch-proof] retains the
earlier 57-case and separate 4-case proofs. The [prior profile record][prior-profile]
retains its 60/2/5-case and incomplete/continuation evidence for 24 selected
cases. None of those selectors was rerun. This page replaces stale task status
instead of appending full history.

experiment-design kept the registered configuration-bundle scope fixed during
the prospective binding update. im-not-ai-en protected the exact evidence,
links, uncertainty and refusal conditions in these bounded English records.
No new experiment, condition, budget or axis was added.

[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/746#pullrequestreview-5409330647
[prior-launch-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c28847f1b0e3626a088a746558cda82aca67c127/tasks/LATEST_TASK_RESULT/README.md#project5-independent-comparison-runtime-launch-refusal--2026-10-05
[prior-preparation]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c6fbf893595336e0a89ceb122ac5859991487144/tasks/LATEST_TASK_RESULT/README.md
[prior-profile]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fd903b96dc8d4622470b6971fde820334c16396b/tasks/LATEST_TASK_RESULT/README.md
