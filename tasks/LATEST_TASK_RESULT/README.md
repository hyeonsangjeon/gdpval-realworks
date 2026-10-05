# Latest task result

## PR750 legacy/default and frozen-fixture compatibility — 2026-10-05

The single authorized offline invocation reported **23 passed in 136.55s**,
exit 0, at `00997e75f6c72e3bfa0541be1bb1c6e47867c401`, tree
`a3d4e355260c87ed7555d9db2cde1420955596ff`. It covered the nine named failures,
six runtime-checkout cases, seven workflow-gate cases and one accepted historical
pilot predecessor. No target failed, errored, skipped or remained uncompleted.
Delivery remains **HOLD** for whole corrected-HEAD review and applicable CI.
This is targeted software evidence, not CI acceptance or a live-run result.

### Role classification and correction

Before editing, the same-session source/architecture and grading charter review
classified CURRENT runtime R, anchored frozen source F, and template versus
materialized grader identities. The relevant consolidated grading specification
requires the entire core closure and actual config path/bytes to remain in the
fingerprint. The decision was APPROVE-WITH-CONDITIONS: restore legacy sampling,
correct fixture sources rather than old hashes, retain real validators and
source-before-credential ordering, and leave ownership/finalization and launch
gates unchanged. This check is not independent whole-PR approval.

The bounded correction changes twelve files before proof:

- `AgenticV2ScriptedRunner.run` again uses `startup_started >= deadline` when
  observation control is omitted. It does not take the extra startup sample.
  The observation-control branch still calls its existing deadline check. The
  three original timing/error-stage assertions passed without being relaxed.
  Only this runner's pin advances in the prospective time-budget manifest.
- The two comparison seeds now use the existing frozen local-source fixture.
  They first assert the real CURRENT refusal for the changed conversation and
  Codex runners. The shared supplier binds `ROOT`, `PLAN` and its default loader
  path to the selected source. Real compilation, temporary Git lineage,
  manifest/blob/input checks, no-clobber behavior and false-launch assertions
  remain active. Selected workflow negatives assert their exact refusal stage.
- The fixed-grade fixture binds the imported pilot source root and real loader's
  default path to F. It proves that CURRENT core is not the old template, then
  uses F's actual closure in the existing fake child checkout. Reader/controller
  checks remain separate. The real entry validator retains the first-cell
  materialized hash `c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320`
  and KEEP/r2 hash `997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1`,
  both distinct from TEMPLATE. Positive, stale-source, private-boundary and
  one-use assertions remain intact. No hasher or validator verdict is replaced.
- The pilot history passes the real frozen session fixture to its manual
  `offline.__wrapped__` call. The directly related manual consumers were audited
  once; the other direct `offline` call uses the unchanged one-argument pilot
  guard. No silent current-root default or fabricated fixture was added.
- The model-free retention reader test uses the historical registration fixture
  before checking its unchanged explicit-token refusal. The CURRENT input-only
  test names the additional conversation-source refusal. The observer test uses
  the existing `CURRENT_SOURCE` facade expectation, not the frozen-source table.
  The ceiling contract checks `_run_model_conversation`, the real loop called by
  the public wrapper, while retaining both original ceiling assertions.

### Source identities

| Identity | Value |
| --- | --- |
| Inspected published basis | `513a443f361106300f9be425f8b12c2c48a2540f` |
| Basis tree | `a6021266308b4fb83996e66a05fcb9a38ac1308d` |
| Clean tested correction | `00997e75f6c72e3bfa0541be1bb1c6e47867c401` |
| Tested tree | `a3d4e355260c87ed7555d9db2cde1420955596ff` |
| Changed V2 runner SHA256 | `b573bad6dd5b859106621705c5d9e8adc72efd9e32b4de1165b33b849aeb9ee6` |
| Prospective manifest SHA256 | `11ca9d91f4431005377e2c872e4c35a4c38ef59a4173ec29a4548a2afeff8f42` |
| Unchanged ownership/finalization helper SHA256 | `4ce90fd05e4c8f0c32d3a0267f089bbaf0a279ef704852c994af6debb12a6c26` |
| Accepted main | `f609aff0deefd3c5afd7a6322ba6473c8b3e6c98` |
| Accepted main tree | `3b318f9d70cbf2a080de28ff76fdfd5e278e1264` |

Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with genuine whole TEMPLATE
closure `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The original comparison manifest retains SHA256
`3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1`;
the sealed local-source profile retains
`81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe`.
No historical manifest, F byte, paid RESULT/PARENT/READER, fixed-evidence digest,
grader algorithm, workflow byte or launch guard changed.

### Supplied CI evidence, not new queries

The leader supplied these observations. This task did not query or rerun CI.

| Source / job | Actual result | Interpretation |
| --- | --- | --- |
| `513a443f361106300f9be425f8b12c2c48a2540f`, run `37304369158`, comparison job `111744830880` | 1244 passed, 117 setup errors in 1193.62s | Two shared seeds: 54 runtime-checkout cases and 63 workflow-gate cases |
| Same HEAD/run, pilot job `111744831046` | 1514 passed, 23 setup errors in 1056.86s | One missing argument in the shared historical-predecessor fixture |
| Older `0cee74941b9a093109d7c32a289d563616626e99`, job `111732532758` | 9 failed, 13381 passed, 64 skipped, 46 deselected in 1766.43s | The nine named regressions; not a new-head result |

The comparison log SHA256 is
`e092582349b46b79a99c8b293c11a577c2dfb5461669952a101cc57c7e5b7dfa`;
the pilot log SHA256 is
`24f11bb158310fae07fe1bffb4e3d8033f26e316ddb3cdcb7e5b2184eb55e428`.
A local Git comparison confirmed that the older nine failures' affected runner,
conversation and test paths were unchanged between `0cee7494` and `513a443f`.
That source reconciliation does not turn the older CI observation into a run at
the newer HEAD. The setup errors were shared causes, not separate defect counts.

### One targeted proof

Python 3.10.12 ran the following exact node set once, without `-x`. The outer
300-second bound and 5-second termination grace were test-only. Every listed node
has an explicit PASS in verbose output and the final pytest summary. Source-only
archives, real temporary Git and synthetic input/transport fixtures were used.
No real original input, its receipt or the consumed preparation was accessed.

This public command redacts private executable, worktree and evidence locators.
Its display is not the exact private script identified by the command hash below.
The private script also checks the fixed HEAD/tree and clean worktree before
running. From the worktree's `batch-runner` directory:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR=<private-evidence-directory> \
  PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 \
  timeout --kill-after=5s 300s <existing-py310> -m pytest \
  -vv -rA --tb=short --color=no -p no:cacheprovider -m 'not integration' \
  --basetemp <new-private-directory> \
  tests/test_agentic_v2_foundation.py::test_scripted_runner_honors_wall_time_before_tool_dispatch \
  tests/test_agentic_v2_foundation.py::test_scripted_runner_wall_expires_after_start_before_tool \
  tests/test_agentic_v2_foundation.py::test_scripted_runner_wall_expires_inside_dispatch_boundary \
  tests/test_codex_ci_input_bundle.py::test_ci_input_bundle_current_input_registration_does_not_compile_dispatch \
  tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free \
  tests/test_codex_retention_fixed_grade.py::test_first_retention_fixed_grade_is_bound_one_use_and_private \
  tests/test_codex_retention_keep_r2_grade.py::test_keep_r2_fixed_grade_is_bound_one_use_and_private \
  tests/test_codex_retention_observer_source.py::test_anchored_prospective_verification_current_binding_remains_unpaid \
  tests/test_every_ending_is_named_or_knowingly_unnamed.py::test_the_ceiling_the_map_names_is_not_one_the_loop_can_raise \
  'tests/test_gpt54_runtime_checkout.py::test_anchored_prospective_verification[valid]' \
  'tests/test_gpt54_runtime_checkout.py::test_anchored_prospective_verification[codex_valid]' \
  'tests/test_gpt54_runtime_checkout.py::test_anchored_prospective_verification[wrong_anchor]' \
  'tests/test_gpt54_runtime_checkout.py::test_anchored_prospective_verification[blob_bytes]' \
  'tests/test_gpt54_runtime_checkout.py::test_anchored_prospective_verification[input_bytes]' \
  'tests/test_gpt54_runtime_checkout.py::test_anchored_prospective_verification[pinned_source]' \
  'tests/test_gpt54_workflow_gate.py::test_workflow_profile_anchor_positive[api-prospective-sandbox_v2]' \
  'tests/test_gpt54_workflow_gate.py::test_workflow_profile_anchor_positive[cli-prospective-codex]' \
  'tests/test_gpt54_workflow_gate.py::test_workflow_profile_anchor_positive[api-historical_default-sandbox_v2]' \
  'tests/test_gpt54_workflow_gate.py::test_workflow_profile_anchor_positive[api-historical_default-codex]' \
  'tests/test_gpt54_workflow_gate.py::test_workflow_profile_anchor_preparation_refuses[sandbox_v2-source_head]' \
  'tests/test_gpt54_workflow_gate.py::test_workflow_profile_anchor_verification_refuses[target_altered]' \
  'tests/test_gpt54_workflow_gate.py::test_workflow_profile_anchor_coherent_target_substitution[codex]' \
  'tests/test_codex_budget_pilot_task3_a1.py::test_fixed_task3_a1_historical_predecessor[accepted]'
```

| New private evidence | SHA256 | Bytes |
| --- | --- | --- |
| Exact command | `a480936099b18cc75a2a241bcac5bd66d5babfc7de7063e92f3c972b3e18d7aa` | 3333 |
| Combined stdout/stderr log | `eeebc45da1491ee35e8613fbc41cd0e5b6113e80ed4ee96a92689e2593f5a91c` | 10491 |
| Receipt with all 23 passed node IDs | `aaf6910b2200c97394610a428d5edb981316c60851253172976a73763b375b29` | 3745 |

### Prior proofs remain separate

The [immutable prior record][prior-record] retains command/log/receipt identities,
node inventories and links to earlier detail. All prior local evidence was left
untouched.

| Earlier invocation | Tested HEAD | Actual result |
| --- | --- | --- |
| Original combined selector | `1d5a9c2472e17fde1c0ad2dc1a0f3300772b5c95` | 5 failed, 46 passed, 75 deselected in 8.35s; exit 1 |
| Five-failed-target continuation | `73a86933934ac0a9cc260a963f042414b61bc151` | 5 passed in 7.55s; exit 0 |
| Persistence/finalization selector | `d6bff25dc037c96bccf418a0fe06b00402592bc7` | 21 passed, 126 deselected in 6.51s; exit 0 |
| Process-ownership selector | `c73a71b5307a8d1f3405cf3cc3f55cb3d8d4cb3e` | 30 passed, 147 deselected in 4.91s; exit 0 |

These observations remain separate. There is no aggregate 51-pass or global
all-tests-pass claim. None of those selectors or the full 117/23-case setup-error
families was rerun. Only `CHANGELOG.md` and this single current record follow the
new pinned proof; there is no post-proof source, test or pin change.

### Remaining review, platform and live gates

The prior isolated real-kernel case refused admission with
`time_budget_owned_process_host_required`, caused by `FileNotFoundError`, errno 2.
Standard proc paths are used, but a missing interface is not real orphan-cleanup
success. Supported lifecycle coverage remains controlled-kernel evidence. The
ownership/finalization design was not expanded or re-tested in this task.
SIGALRM does not establish a hard real-time bound on uninterruptible kernel stalls
or a descheduled host, nor prove remote cancellation, ownership or billing.

The fixed prospective 20-observation GPT-5.4/direct-v1/xhigh, five-task ABBA study,
two repeats, concurrency 1, 1200-second generation deadline and shared 20-second
cleanup remainder are unchanged. There is no external replay/resume/retry or
native request/token/money hard-cap claim. The closed 30-cell/8-cell studies,
10800-second store, all prior worktrees and consumed preparation remain untouched.

Whole corrected-HEAD source review, applicable CI and delivery acceptance remain
pending. Dispatcher/capture selection, verified credentialed inputs, supported
host validation, F-derived grading materialization and a separately reviewed
source-bound live direction remain. All launch refusals and execution flags stay
closed. No CI query/poll/dispatch/rerun, Node/HF check, provider/model/grader/HF/Azure
call, Project edit or merge occurred.

The full catalog was inspected once. The source/grading/architecture charters
governed the role separation. `im-not-ai-en` preserved the evidence, numbers and
limits in these English records. Experiment design was not rerun because the
policy is unchanged; no UI/animation or unrelated skill was used.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/513a443f361106300f9be425f8b12c2c48a2540f/tasks/LATEST_TASK_RESULT/README.md
