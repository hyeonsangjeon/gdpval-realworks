# Latest task result

## PR757: linked Actions runtime repair; focused proof failed

The source-layout repair is implemented. Its one new offline selector reported
**6 passed, 1 failed in 58.33s**, exit 1. The failed `[linked]` case stopped at
the test's exact-argv assertion before `ci.main`: `shlex.split` retained Bash
continuation newlines as arguments. No source/test/workflow change or test
rerun followed. The positive workflow CLI path remains unproved.

### Scope and reviewed basis

Work started in a fresh worktree from exact reviewed
`1a1e9f9199497ccb804f1d00ece46515f75544ff`, tree
`0392fc326b3293ffbf30e75e25570b0912c2da15`, review `5425363467`.
The leader supplied the confirmed defect and the actual pre-edit CI/source
charter approval for this bounded repair and one synthetic proof. This was
a leader-executed review, not a successful spawned-model review. The unavailable
reviewer harness was not retried. The leader also reported 10 prior CI checks
passing; those checks did not exercise this Actions layout and do not validate
the correction or authorize execution.

The established cause was the ordinary `actions/checkout` directory at
`GITHUB_WORKSPACE` being passed as runtime R. The existing
`registration._reviewed_source` path requires a genuinely registered detached
linked worktree through `_runtime_revision` and `_registered_gitdir`; the
ordinary `.git` directory could not satisfy that contract. The validators
were not changed or weakened.

The workflow now verifies the bootstrap's reviewed commit/tree, refuses
existing runtime or frozen destinations, and creates detached linked R at
`$RUNNER_TEMP/time-budget-v2-runtime` and distinct linked F at
`$RUNNER_TEMP/time-budget-v2-frozen`. State remains at
`$RUNNER_TEMP/time-budget-first-v2`. Actual `GITHUB_WORKSPACE` stays the ordinary
bootstrap. Controller calls, dependency installation and the existing identity
preflight use linked R. The independently digest-bound request must name the
new R path. The controller checks canonical paths, shared common Git identity,
bootstrap commit/tree and held directories before credentialed work and on
final reread. Existing R/F blob, input, direction, CAS, host and no-retry checks
remain in place.

Only the workflow, controller and directly coupled test module changed before
the proof. The old fixtures now construct the same ordinary-bootstrap/linked-R/F
layout with real temporary Git objects and explicit synthetic input declarations.
Their older test cases were not rerun; their coverage remains pending CI.
No core, ownership, manifest, source pin, frozen F, permission or study policy
was changed. The first registered V2 cell, 20-observation study, GPT-5.4/direct-v1/xhigh,
concurrency 1, one attempt, 1200-second generation, shared 20-second cleanup and
45-minute job ceiling remain fixed. The ceiling is not a money cap.

### Pinned implementation and one proof

- Tested HEAD: `14fe35b08018af3c92e02bfc474b5aef6777c724`.
- Tested tree: `27c5c4f7f275a9cb5a06633ebb5298733f3e7ae9`.
- Implementation delta: three files, 192 insertions and 27 deletions.
- Selector: `tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_source_layout`.
- Python 3.10.12, one offline invocation, 300 seconds plus 5 seconds termination
  grace, no `-x`. JUnit records seven cases, one failure, zero errors and zero
  skips. No previous PR757, PR758, study, platform or full-suite selector ran.

All seven completed parameter outcomes are retained:

| Parameter | Result |
| --- | --- |
| `linked` | Failed at line 326, before the CLI call |
| `ordinary_runtime` | Passed |
| `bootstrap_commit` | Passed |
| `bootstrap_tree` | Passed |
| `bootstrap_common` | Passed |
| `final_bootstrap_commit` | Passed |
| `final_bootstrap_common` | Passed |

The failed case had already executed the workflow's worktree-creation shell
with explicit synthetic F anchors and checked no-clobber refusal. Its Python
command parser then produced literal newline arguments where Bash removes
backslash-newline continuations. This test failure is retained, not relabeled
as successful workflow execution. The six refusal cases use genuine source
validators, including final bootstrap commit movement and common-directory
replacement. Their intake, private-store, admission and provider effect checks
remained clear. Socket and external-write sentinels stayed enabled.

Artifacts remain at `/tmp/pr757-source-layout-proof.cp7wxA/`. `command.sh`
contains the complete invocation and clean HEAD/tree guards; its digest is
not the hash of shortened or redacted command text.

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `command.sh` | 1322 | `4c72dc3fa89782c81d41f7dc10218c511c6cd6a3c6b90653025ab0dda3196ef1` |
| `pytest.log` | 7810 | `4ccf56767353578b39abba8c212c1ba0e31bbb021039dbf3602d2d2469891295` |
| `junit.xml` | 7929 | `e7d61f72019639b49a57fa7b911b6a4801b87ec792a0de55e286b17806d5a12a` |
| `exit.txt` | 13 | `b3f1a96987ccc7d792693aedce90d59a97a3a52df9aeba6c89066b61a182b0e0` |

### Separate evidence and remaining gates

The [original invocation][original] remains **14 passed, 11 failed and
11 teardown errors in 16.57s**, exit 1, at
`8be989167037f91b98866a2fdb8bc887b11a4c54`. The telemetry correction
`1585ef4309f03fc08d0e7c553341d62826b182d0` was unrerun at that handoff.
The [11-node continuation][continuation] remains **10 passed, 1 failed in
68.02s**, exit 1, at `0fe559377bbbd20eab790dd7a5c48e4509911c90`.
The [missing-usage retention proof][missing-usage] remains **1 passed in
15.88s**, exit 0, at `d82fbd9b47b3af97d56510ee98db5370830d30fb`; its accepted
correction is `32b5fadcb4346fc576b1e5e631b164c596f68bf4`, review `5425328389`.
These immutable records retain their artifacts and earlier software, grading,
NAS-refusal and real CI host evidence. No aggregate 25-pass result is claimed.

The exact post-proof repository delta is only `CHANGELOG.md`, this LATEST
record and the directly affected evidence/request-path/usage passages in
`batch-runner/README.md`. Production, workflow and test bytes remain identical
to the tested implementation. `im-not-ai-en` is limited to these changed
English passages, preserving failures, counts, paths, identities and gates.
One bounded changed-passage fidelity check passed without warnings; it was an
editorial check, not another software test or evidence of live readiness.

Remaining work includes the failed test's shell-tokenization correction and
positive CLI evidence, final-HEAD source review and ordinary CI, then the
leader's source/integration decision. Accepted main remains
`b4e15f02c1db8674ffeff83f133c710627c696e8`, tree
`5de4c1ce82dcfeddf0178a52c6c3bf0e40bae54f`. This repair does not select an
approved runtime. Genuine input/private-parent/actual-host values, the finite
window and a separately issued digest-bound live request are still required.
Actual kernel ownership admission and provider identity checks remain mandatory.
The [usage section](../../batch-runner/README.md#first-v2-observation-on-github-actions)
shows the future request path contract; it is not permission to dispatch.

The old PR757 worktree and PR758 branch were left untouched. No CI query,
dispatch, retry or poll; private HF/input/receipt access; model/grader/Azure
operation; permission expansion; Project edit or merge occurred. This is
synthetic source-layout evidence, not real input, host, inference or publication
evidence.

[original]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/0fe559377bbbd20eab790dd7a5c48e4509911c90/tasks/LATEST_TASK_RESULT/README.md
[continuation]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/561219c661e8a5f05cd20c1637aac792d782a887/tasks/LATEST_TASK_RESULT/README.md
[missing-usage]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/32b5fadcb4346fc576b1e5e631b164c596f68bf4/tasks/LATEST_TASK_RESULT/README.md
