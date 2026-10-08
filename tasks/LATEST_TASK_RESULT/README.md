# Latest task result

## PR777 parent-parity continuation: the single regression passed

Only the newly authorized registration-lifetime regression ran, once:
**1 passed, 1 warning in 1.92s**, exit **0**, wrapper **2.243325s**. It observed
the real synthetic Git refusal and reached every subsequent preservation
check. The earlier four-node invocation remains **1 failed, 3 passed,
1 warning in 28.81s**, exit **1**, wrapper **29.946711s**. Its partition and
two historical readout passes were not repeated, and results are not pooled.
The section below records that earlier turn's stop boundary.

### Test-only parity and the observed result

Starting source was `62d02b71a634986a344131fbc3485700cae0072c`, tree
`2168a7e9962de2be75f22a0240dd6fcd941b590c`. The leader's source comparison
established a setup-parity omission: the actual fixture creates `runner-temp`
before Git registration, while the original generated reuse probe did not.
This finding alone does not explain why Git behaved differently and does not
recover missing historical CI stderr.

Three added lines now create exactly that synthetic parent before the direct
probe, check that it is empty after the expected refusal, and remove only
that newly created empty parent with `Path.rmdir()`. The root stays absent
before the probe and its stale registration remains observable. The existing
exit-128/stderr assertions, subsequent absence assertion, real fixture call
and all later preservation assertions are unchanged. No recursive deletion,
force, Git configuration change, alternative path or pre-existing proof cleanup
was used. The actual source fixture and production code did not change.

Tested HEAD was `5d523d131d97e5255430b15acefb2bf68c7fc407`, tree
`9936c322e3dfc3b2392d032ad77218e6d6a829e5`; regression blob
`a1b34c1ebc5ffc39b5fba96d5d20d7af39d41f70`. The only outer node was
`tests/test_time_budget_readout_worktree_lifetime.py::test_time_budget_readout_worktree_registration_lifetime`.
It ran under Python 3.10.12 / pytest 9.1.1, 300s+5s/no-`-x`, with the unchanged
30-second child and Git bounds and `tmp_path_retention_policy=failed`.
AST checks verified the exact node, outer fixtures and generated child
parameters before launch. The wrapper ran from `2026-10-08T02:18:32.221625Z`
through `2026-10-08T02:18:34.464951Z`. Final JUnit and immediate reports are
retained; the warning is the existing `record_property`/JUnit `xunit2` warning.

The newly constructed child cases reported **1 failed, 2 passed in 1.42s**,
exit **1**. The failure was deliberate and preserved the failed worktree.
With the parent present and the root absent, direct uncorrected Git addition
returned **128**. Its actual stderr includes
`is a missing but already registered worktree`; full stderr and the exact
synthetic path are retained in `registration-receipt.json`. This is newly
observed reproducer stderr, not the unavailable stderr from GitHub CI.

After asserting that the parent was empty and removing it with `rmdir()`,
the unchanged real fixture pruned missing registrations and registered the
same path. Both calls used one unchanged setup deadline. All ten recorded
checks passed: same-path registration, failed-worktree contents and registration,
shared source and sibling contents, repository HEAD/tree/branches, failed
worktree HEAD and new worktree HEAD. After child teardown, the failed directory
still existed and the reused passing directory was absent. Only the new
synthetic pytest lifecycle and its verified empty-parent removal affected data.

### Evidence identities, label correction and gates

Artifacts are in `/tmp/pr777-readout-parent-parity.aJjVl4/`: `command.json`,
`selection.json`, `source.json`, `pytest.log`, `reports.jsonl`, `junit.xml`,
`junit-cases.json`, `cases.json`, `outcome.json`, `registration-receipt.json`,
the bounded wrapper/hook and reporting checks. Log SHA256 is
`9c53b595d8f432fc64aafeee7cd5e9431cd7b57ba3dd026d9e4dfea905e4e842`;
registration-receipt SHA256 is
`dd3b2ce33b51545ea82cb282ca43c5249b8032f441c78a7370cac572cff3658a`.
`handoff.json` records exact final HEAD/tree after the three-record commit,
unchanged tested code, publication outcome and artifact identities;
`SHA256SUMS` binds the retained files. Final Git identity is external to its
own tree to avoid a circular reference.

The readout fixture remains blob `450bbdf768fbb6331047d7bcb91ec5056f9be224`,
the partition test `f4e6cdc5a0cf905765209525fc71619a9c618763`, and the backend
workflow `cd2c6d0f186807a0e879cdd442376f070cf48620`, SHA256
`01fe1494460ae36a6ded2caf3955b27ff9d922374b1ffbe3e91c4077d344d094`.
The approved retention option, 45-minute ceiling, selected workload, all
production/native/grading/source guards, frozen F/scoring, input pins, models,
budgets and twenty-cell study are unchanged. `source.json` records exact
unchanged identities.

The leader clarified that run `37710408405`, time-budget job `113094770711`,
reported **367 passed, 61 setup errors** with a **pytest summary duration of
1513.84s** (display **25m13s**), not a measured full GitHub job duration.
The directly related labels below and in CHANGELOG/direct README are corrected.
The prior immutable task-local receipt's job-duration label is superseded,
not rewritten. CI Git stderr remains unavailable. This single synthetic
success does not establish that all 61 setup errors are fixed or full CI passes.

The failed four-node artifacts in `/tmp/pr777-readout-worktree-lifetime.rvay35/`
remain unchanged, including its original negative result and unreached checks.
The seven-case hosted, quote and earlier lifecycle proofs were not rerun.
Older disk-full and timeout annotations and the **10673136 allocated KiB**
NAS measurement remain separate; this is not a GitHub-runner storage measurement.
The unavailable specialist failed before execution, supplied no review or
endorsement and was not retried. Reporting/English checks preserve these
units and uncertainties. Final fixed-source review, normal synchronization
CI, real host/auth/input checks and exact hosted admission still gate use.
No CI query/retry/dispatch/wait, Project edit, merge, Azure/private fetch,
live claim/model/grade/readout, replay or Task5 occurred. This change grants
no live authority.

## PR777 test continuation: three nodes passed; new regression failed

The single authorized four-node invocation reported **1 failed, 3 passed,
1 warning in 28.81s**, exit **1**, wrapper **29.946711s**. The partition test
and both selected readout tests passed. The new Git registration-lifetime
regression failed because its direct `git worktree add` did not raise the
expected `CalledProcessError`. This is a failed proof, not four passes or
evidence that full CI now passes. No further code change, diagnostic run or
test invocation followed the body failure; only these records were added.

### Two test-only changes and the leader's CI evidence

Starting source was `103667992af71826ddbabf3853ecd406cbefab58`, tree
`6ede045510cb40558fa7b96592a42d218f2c34e6`. The partition test now requires
`["-o", "tmp_path_retention_policy=failed", TIME_BUDGET_GLOB]` in its raw
argument assertion. `_pytest_target_arguments` already accepted `-o` and its
parsed-target assertion had passed; neither the parser nor exact-command or
coverage checks changed.

The readout `source` fixture now runs ordinary
`git worktree prune --expire now` against `source_repository.workspace`
immediately before `worktree add`. Both calls share one existing 30-second
setup deadline and the same bounded Git helper. New test-only ownership
assertions require the workspace to share the pytest temporary parent and
contain an ordinary, non-symlink `.git` directory. Prune concerns missing
worktree registrations in that synthetic repository, not branches or
existing working directories; no real checkout or worktree is targeted.
No force, global cleanup, larger timeout or Git configuration change was added.

The leader read run `37710408405`; no CI endpoint was queried here:

- Pytest job `113094770549`: **1 failed, 13395 passed, 64 skipped, 46 deselected,
  1 warning in 1945.04s**. The exact failure was
  `tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts`,
  line 680. The obsolete second assertion required only the glob despite the
  raw arguments also containing the approved option and value.
- Time-budget job `113094770711`: pytest summary **1513.84s** (display **25m13s**),
  not a measured full job duration; **367 passed,
  61 setup errors**. Reported errors shared the `source` fixture's
  `git worktree add`, exit 128, at `tests/test_time_budget_result_readout.py:90`.
  The examples reused the same function-scoped path against a module-owned
  ordinary bootstrap; uncertainty cases used their separate module bootstrap.
  These are setup errors, not a disk-full or timeout annotation. The CI short
  trace does not include Git stderr, so its exact fatal message is unknown.

The leader's source-derived diagnosis links passed-directory cleanup to stale
worktree registrations retained by the longer-lived module repository. The
new local reproducer did not establish the expected Git refusal. Keep that
negative result separate from the source account and missing CI stderr; no
Git-version or other environmental explanation was investigated or inferred.

### Exact bounded outcomes

Tested HEAD was `98f9471220f22d339b8d42aae642c4437322fc7d`, tree
`64e720462523758eabe4efbcca53bbf839be4fa8`. One invocation ran under Python
3.10.12 / pytest 9.1.1, 300s+5s/no-`-x`, existing Git bounds and
`-o tmp_path_retention_policy=failed`, from `2026-10-08T01:53:04.211328Z` through
`2026-10-08T01:53:34.158040Z`. AST checks verified node/fixture/parameter names
and generated child syntax before launch. The immediate hook retained the
actual failure trace; final JUnit and all four case outcomes are available.
The warning concerns `record_property` with JUnit `xunit2`.

| Selected node | Observed result |
| --- | --- |
| `test_time_budget_readout_worktree_registration_lifetime` | Failed at the child-outcome assertion in the new test, line 138. |
| `test_backend_jobs_partition_the_comparison_contracts` | Passed, including the unchanged parser, command and coverage checks. |
| `test_time_budget_result_readout_historical_registration[wrong_R_tree-historical_runtime]` | Passed with real source/refusal validators and synthetic data. |
| `test_time_budget_result_readout_historical_registration[wrong_registration-historical_runtime]` | Passed with real source/refusal validators and synthetic data. |

The tiny child pytest reported **2 failed, 1 passed in 1.42s**, exit **1**.
The first failure was the deliberate failed-worktree retention case. The
unexpected failure was at generated `test_registration_lifetime.py:58`:
`with pytest.raises(subprocess.CalledProcessError)` ended with
`DID NOT RAISE CalledProcessError` after direct `git worktree add`. The expected
exit-128 refusal and its stderr were not observed; no fatal message is supplied
as a substitute. The outer test correctly rejected the extra failed child.

The child receipt confirms that pytest removed the first passed directory and
allocated the same path again. Its deliberately failed worktree still existed
after child exit. The unexpected reuse failure also retained its path. The
new regression did **not** reach the later corrected-fixture reuse, shared/
sibling-content, final commit/branch-identity or failed-registration checks.
Initial identities in its receipt are not post-prune preservation evidence.

Separately, the two existing readout cases used exactly the same root
`/tmp/pr777-readout-worktree-lifetime.rvay35/pytest-tmp/test_time_budget_result_readou0/runner-temp/time-budget-readout-source`
and module repository
`/tmp/pr777-readout-worktree-lifetime.rvay35/pytest-tmp/readout-ordinary-bootstrap0`.
The hook observed each root present after setup and absent, with its per-case
parent, after passing teardown; the shared repository remained. This checks
the corrected fixture on those two cases, not every one of the 61 CI errors.

### Identities, preserved evidence and remaining gates

Changed test blobs are partition `f4e6cdc5a0cf905765209525fc71619a9c618763`,
readout fixture `450bbdf768fbb6331047d7bcb91ec5056f9be224` and new regression
`04ac0c53f8c370172b78cc5c204117de45c18b41`. The backend workflow remains blob
`cd2c6d0f186807a0e879cdd442376f070cf48620`, SHA256
`01fe1494460ae36a6ded2caf3955b27ff9d922374b1ffbe3e91c4077d344d094`.
Its retention option, 45-minute ceiling, markers, glob and permissions are
unchanged. All production/native/readout/grading/source guards, F/scoring,
registration, cohort/model/budgets, `pytest.ini` and dependencies are unchanged;
`source.json` records their exact identities.

Artifacts are in `/tmp/pr777-readout-worktree-lifetime.rvay35/`: the wrapper
and hook, `command.json`, `selection.json`, `source.json`, `pytest.log`,
`reports.jsonl`, `junit.xml`, `junit-cases.json`, `cases.json`, `outcome.json`,
`registration-receipt.json` and `readout-fixture-lifecycle.json`. The receipts
preserve exact paths, child stdout/stderr, initial identities and reached versus
unreached checks. Log SHA256 is
`ed53a7d6e8e74fdc21da8c0a78e611295aec69b95e6f46a6d5d9b7aac00a31fe`;
registration-receipt SHA256 is
`653d02bbd28939dab0635d72c6a8f4456808faf380d9e6938f462b0684fa73a7`.
After this three-record commit, `handoff.json` records exact final HEAD/tree,
unchanged tested code and the failed invocation. `SHA256SUMS` binds the
artifacts; final Git identity is external to its own tree to avoid circularity.

The original seven-case hosted proof, quote proof and previous lifecycle
proof remain unchanged and were not rerun or pooled. Earlier GitHub disk-full
and timeout annotations remain separate from this CI setup failure. The NAS
measurement remains **10673136 allocated KiB** for its original owned proof
basetemp, not a GitHub-runner measurement or causal explanation. Prior records
and proof directories are preserved verbatim; only the new synthetic pytest
lifecycle removes its passed temporary directories.

The unavailable Claude Opus 4.7 preview specialist invocation failed before
execution, produced no review or endorsement and was not retried. The failed
new regression remains unresolved. Further test changes need a new bounded
direction; final fixed-source review and fresh normal CI remain required.
No full-CI success, hosted readiness or grading authority is claimed. Exact
hosted admission and real host/auth/input gates remain. No CI query/retry/
dispatch/wait, Project edit, merge, Azure/private fetch, live claim/model/grade/
readout, replay or Task5 occurred.

## PR777 continuation: scoped temporary retention; new lifecycle proof passed

The `time-budget-contracts` command in `.github/workflows/backend-tests.yml`
now includes pytest's built-in `-o tmp_path_retention_policy=failed`. This is
the only workflow change. Passed per-case `tmp_path` data becomes eligible
for pytest's standard teardown cleanup; failed cases and factory-scoped
shared data are retained. Cleanup is best effort, not a guarantee after
interruption or an assertion that the CI resource incidents are solved.

The 45-minute job ceiling, selected files/markers, permissions, dispatch
checks and other jobs are unchanged. So are `pytest.ini`, dependencies,
the native hosted route, production code, frozen F, scoring, inputs, source
bindings, model, budgets and the twenty-cell study. The two existing test
expectations for the literal command and current workflow checksum changed
mechanically; historical/frozen pins did not. Those older tests were not run.
No shard, extra cleanup script, retry or automatic performance change was added.

### Separate CI and storage observations

The starting source was `2ec4d44b8963dec16195c2b44b42c754c212a7d4`, tree
`418e43a93623fa65c68e52676513c19bab75a7f7`, reviewed in `5449683506`, conditional
on CI. The following CI facts were supplied by the leader, not queried here:

- Run `37701493624` had ten successful checks. Only `time-budget-contracts`
  job `113065745498` was **CANCELLED**. Its actual annotation was
  `The job has exceeded the maximum execution time of 45m0s`. The job started
  `2026-10-07T23:18:20Z`, run-tests started `2026-10-07T23:20:33Z`, and the job
  completed `2026-10-08T00:13:21Z`. Run-tests/post-cleanup conclusions were
  null and the log endpoint returned 404. This is not a test assertion;
  the reached or slow test is not established. No test duration is inferred
  from these timestamps or reconciled into the timeout annotation.
- In the earlier run `37695792367`, time-budget job `113047068253` failed at
  `2026-10-07T22:44:22Z` with `System.IO.IOException: No space left on device`
  in `_diag/Worker_20261007-222248-utc.log`. Its log was unavailable and
  run-tests/post-cleanup conclusions were null. This separate disk-exhaustion
  incident does not identify the consuming files or reached test.
- A completed NAS read-only measurement of the proven owned basetemp
  `/tmp/native-task3-hosted-grade.b5J2SO/pytest-tmp` returned **10673136 allocated
  KiB**, exit 0, elapsed **0.189219s**, under a 20-second bound. Measurement
  ran from `2026-10-08T00:06:10.108505Z` through
  `2026-10-08T00:06:10.297683Z`. Receipt
  `/tmp/pr777-basetemp-size.sW0PcL/receipt.json`, SHA256
  `fba3a352c98e37a689cda139250edaabeff5b6309d312a565e9115b302093a8b`, records
  the exact `du -skP` result. This is retained NAS synthetic-test storage,
  not a GitHub-runner measurement or evidence of either CI failure's cause.
  That measurement was not repeated; all earlier proof directories remain.

### One new bounded lifecycle proof

Only
`tests/test_time_budget_tmp_path_retention.py::test_time_budget_failed_tmp_path_retention`
ran, once, at `9c2a9c3e68c2153a60bef481fb60ce411dbd8e24`, tree
`8fdeda28c08c49d929d3e30841249bbefb44876e`. It reported **1 passed, 1 warning
in 0.37s**, exit 0; wrapper **0.684349s**, from
`2026-10-08T00:51:25.773835Z` through `2026-10-08T00:51:26.458188Z`.
Python 3.10.12, existing pytest 9.1.1, 300s+5s/no-`-x` and 30-second Git bounds
were retained. AST checks verified the fixture arguments, generated child
syntax and exact selection before launch, without a separate collection run.
The one warning is `record_property` with JUnit `xunit2`; immediate reports,
the path receipt and final JUnit were all produced.

The test checks the actual workflow command and verifies that removing only
the new option restores the complete previous workflow hash. It launches
one isolated child pytest with that command's marker/options, only two new
synthetic cases, a fresh explicit basetemp and no repository fixture imports.
The child reports **1 failed, 1 passed in 0.02s**, exit **1**. Its failure at
`assert False, "intentional retention probe"` is deliberate and preserved in
the receipt/JUnit, not hidden as a successful child execution. No intake,
child grader, provider, network or historical test body ran.

All paths below are relative to the exact newly owned root
`/tmp/pr777-tmp-retention.lDChVS/pytest-tmp/test_time_budget_failed_tmp_pa0/lifecycle/`:

| Recorded directory | Directly observed lifecycle outcome |
| --- | --- |
| `child-basetemp/test_passed0` | Removed by standard pytest teardown, already absent before the next child case. |
| `child-basetemp/test_failed0` | Retained after child exit; synthetic payload bytes unchanged. |
| `child-basetemp/shared-source0` | Session/factory-scoped directory retained; sentinel bytes unchanged. |
| `sibling-source` | Outside the child basetemp; directory and sentinel bytes unchanged. |

No manual removal occurred. This small synthetic proof checks directory
lifetime, not peak disk use, full-job runtime or actual runner readiness.
The original hosted-route proof remains **7 passed in 294.01s**, exit 0,
wrapper **298.027932s**, at `86d628b4d227b40787b1b958b54b6acb3a6aac51`, tree
`ded2db9655c5ec581a9b64317ce35957348e1f45`. The quote-only proof remains
**1 passed in 0.19s**, exit 0, wrapper **0.521549s**, at
`980ea0f028a79b1b9ca14308673ec941b9ab5782`, tree
`de000e4ef734be1dd1a51b3e29b6ec880b8bcd6a`. Neither ran again or was pooled
with this result. Their full records, CI quote-failure evidence and synthetic
limits remain below unchanged; equal YAML parses never established disabled
identity enforcement. No actual retained Task3 files were hydrated or graded.

### Source identities, artifacts and remaining gates

The backend workflow blob is `cd2c6d0f186807a0e879cdd442376f070cf48620`, SHA256
`01fe1494460ae36a6ded2caf3955b27ff9d922374b1ffbe3e91c4077d344d094`; the new
test blob is `cb4189e2c190e5badb6e41e6df14ab249f670f98`.
The hosted workflow remains `34a4b782232118aced1496dade3a767c43d80a99`,
controller `f12ec5f4a812d53e0105bee1fc01df10d34d3b74`, original seven-case test
`89367c669766f0351f431e5a36c7a3e71e94fea6`, executor
`10d8e56c5569cc3dea484e4bb9d875712a0d5b4c`, intake
`69982bebbe202d516eab101509635e037a7b8efd` and preparer
`24a430137fb47bced1e5a450b5b5568d477a5b2e`. `source.json` also records unchanged
registration/study/core, dependency and pytest-configuration identities.

Artifacts are in `/tmp/pr777-tmp-retention.lDChVS/`: `run-proof.py`,
`pytest-driver.py`, `command.json`, `selection.json`, `source.json`,
`pytest.log`, `reports.jsonl`, `junit.xml`, `junit-cases.json`, `cases.json`,
`outcome.json` and the standalone `lifecycle-receipt.json`. The latter retains
exact directory associations, child command/exit/output and all five direct
lifetime checks. Log SHA256 is
`901e26201865e7d0fc566f101d8013d96d9befdd5fe5f0bafa89888d0a51fdaf`;
receipt SHA256 is
`dca6c9bd9a3525b674351dade916cabd4291deb42cbe1ffe79b8985397cbc817`.
After this three-record commit, `handoff.json` records exact final HEAD/tree
and verifies unchanged tested code; `SHA256SUMS` binds the retained artifacts.
Final identity is recorded there rather than embedded circularly in its own
Git tree. The previous document bytes are retained in `records-original/`.

For this specific CI-resource decision, the leader's new mandatory
extreme-reasoner invocation failed **before execution** because the configured
Claude Opus 4.7 preview label was unavailable. It produced **no review or
endorsement**. No harness retry or model/account change occurred. The leader's
explicit narrow decision authorized this implementation, not runtime use.
Retained design/reporting guidance preserves the twenty-cell study and keeps
CI observations, NAS units and synthetic outcomes distinct.

Final fixed-source review and fresh normal synchronization CI remain required;
no CI query, monitoring, dispatch or retry was performed. The mitigation does
not establish that either earlier incident is fixed or the full job now fits
45 minutes. Exact hosted admission, real host/auth/input checks and a leader's
live request still gate any paid execution. There was no Project edit, merge,
private fetch, live claim/model/grade/readout, replay, Task5 or new cell.

## PR777 continuation: quote contract corrected; one node passed

Only the new hosted workflow's line changed from
`AZURE_AI_REQUIRE_EXPECTED_IDENTITIES: "1"` to
`AZURE_AI_REQUIRE_EXPECTED_IDENTITIES: '1'`. The complete old/new YAML parses
are equal; both values are the string `1`. The failing contract inspects
literal quote spelling. It does not establish that the earlier parsed value
disabled identity enforcement. No controller, test, guard, permission,
identity value, executor, study/source/input pin or budget changed.

The leader accepted source `59fe40cc1a1c693ad013ccb52186c74f093a2def`, tree
`c39120a33366bde6453b35f6564e506ca9a00372`, in review `5449259458`, conditional
on CI. This continuation does not turn source acceptance into merge or grade
authority. The [original seven-case record][pr777-original] is retained below
as historical evidence; only its review status is superseded by this section.

### Known CI evidence, supplied by the leader

Run `37695792367`, pytest job `113047068617`, finished with **1 failed,
13395 passed, 64 skipped, 46 deselected, 1 warning in 1821.67s**. The exact
failed node was
`tests/test_envelope_azure_applies_the_run_rules.py::test_every_run_place_that_can_spend_turns_identity_pinning_on`.
Line 495 asserted `assert "'1'" in value`. The one-line correction conforms to
that unchanged literal contract; it changes no identity value or enforcement
setting. These CI results were not queried or rediscovered in this continuation.

Separately, the same run's `time-budget-contracts` job `113047068253` concluded
failure at `2026-10-07T22:44:22Z`. Its actual check-run annotation reported
`System.IO.IOException: No space left on device` in
`_diag/Worker_20261007-222248-utc.log`. The log endpoint was unavailable to the
leader, and the run-tests/post-cleanup step conclusions were null. This is
evidence of runner disk exhaustion, not a proven test assertion, timeout or
transient GitHub-wide outage. The space-consuming files and reached test are
not established. The quote change does not resolve this separate failure.

The permitted static inspection found a possible retention boundary:
`batch-runner/tests/test_time_budget_native_grading_ci.py` creates an ordinary
`--shared` bootstrap clone, fetches synthetic R/F objects, adds linked C/R/F
worktrees and keeps per-case state under `tmp_path`. Its `hosted` fixture
returns without fixture-local directory removal. The existing
`time-budget-contracts` job runs
`python -m pytest -m "not integration" --tb=short -q -rs tests/test_time_budget_*.py`
in one process, without a `--basetemp` or temporary-retention override, under
its unchanged 45-minute ceiling. This source-visible boundary could retain
data across cases; it is not a measurement of disk use or attribution of the
runner failure to this fixture. No reproducer, broad disk scan, cleanup,
pytest-policy change, shard or speculative source fix was added.

### One targeted local invocation

At tested HEAD `980ea0f028a79b1b9ca14308673ec941b9ab5782`, tree
`de000e4ef734be1dd1a51b3e29b6ec880b8bcd6a`, only the exact failed full node
above ran once: **1 passed in 0.19s**, exit 0. Python wrapper elapsed time was
**0.521549s**. Python 3.10.12, the existing environment, 300s+5s/no-`-x` and
30-second Git bounds were retained. AST inspection checked the unparametrized
function before launch; the task-local hook confirmed exactly one collected
node and retained setup/call/teardown reports plus final JUnit. No warning or
failure occurred. This proves the static quote contract, not hosted readiness.

The original hosted-route invocation remains **7 passed in 294.01s**, exit 0,
wrapper **298.027932s**, with seven JUnit `record_property`/`xunit2` warnings.
Its tested source remains `86d628b4d227b40787b1b958b54b6acb3a6aac51`, tree
`ded2db9655c5ec581a9b64317ce35957348e1f45`, and its artifacts remain in
`/tmp/native-task3-hosted-grade.b5J2SO/`. None of those cases ran again, and
these results are not pooled. That proof used real accepted validators but
synthetic originals, HTTP/auth/CAS RPC, owned child and kernel facts. It did
not establish actual private hydration, host support, model use or grading.

### Identities and retained artifacts

The tested correction changed only the workflow blob from
`5dd06caef6d89104f5258597eac2bfa81a42bcf7` to
`34a4b782232118aced1496dade3a767c43d80a99`. Controller blob
`f12ec5f4a812d53e0105bee1fc01df10d34d3b74`, hosted test blob
`89367c669766f0351f431e5a36c7a3e71e94fea6`, executor blob
`10d8e56c5569cc3dea484e4bb9d875712a0d5b4c`, intake blob
`69982bebbe202d516eab101509635e037a7b8efd` and preparer blob
`24a430137fb47bced1e5a450b5b5568d477a5b2e` are unchanged. The test containing
the failed CI assertion and the time-budget job configuration are unchanged.

New artifacts are in `/tmp/pr777-quote-contract.859Mwc/`: the retained wrapper
and immediate-report hook, `command.json`, `selection.json`, `source.json`,
`quote-equivalence.json`, `pytest.log`, `reports.jsonl`, `cases.json`,
`junit.xml`, `junit-cases.json` and `outcome.json`.

- Log SHA256: `3b0357352e43af90dfd85efa2b51dfa854d132cccd90ee96c9893d76b054c17b`.
- JUnit SHA256: `0faac14e6126729b9b6c71f211429d5f05388043875f2432f14f85943491586f`.
- Outcome SHA256: `5319a6a4100f923ee8f6b14aca6925f328728804d2503c7b151f42c5f2355798`.
- YAML-equivalence SHA256: `a87aaab1423e4a5658a53648de355f17645ed6bc58b34dc29424f19934110b7c`.

Only CHANGELOG, this record and the direct README evidence changed after the
tested commit. `handoff.json` in the new artifact directory records exact
final HEAD/tree, unchanged tested blobs and artifact identities after that
records commit, avoiding a self-referential identity inside these documents.

### Remaining gates

Final fixed-HEAD review/CI, including new evidence for the separate runner I/O
failure, remains outstanding. Normal PR synchronization may produce new CI
evidence; no manual retry, dispatch, query or monitoring occurred here. Hosted
admission still requires actual host/auth/input checks, a live expected-parent
check and one exact leader request. Source acceptance is not permission to
merge or grade. Actual Task3 remains ungraded; its two declared files/408601
bytes have not been hydrated for grading here. Usage/cost/served identity/
native counters are unknown, and `items_seen=56` is not a model-call count.

The skill catalog was read once. Experiment-design kept the twenty-cell study,
model, pins and budgets fixed; experiment-report-en and im-not-ai-en kept the
three prior evidence groups and this local result separate. Prior unavailable
specialist invocations failed before execution and remain non-endorsements;
none was retried. No Project edit, merge, Azure management, private fetch,
live claim/model/grade/readout, replay, Task5 or next-cell advance occurred.

[pr777-original]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/59fe40cc1a1c693ad013ccb52186c74f093a2def/tasks/LATEST_TASK_RESULT/README.md

## Original hosted-route record (not rerun)

The following is the prior record, preserved without changing its results or
synthetic limits. The continuation above supplies the later review/CI facts.

## Fixed native Task3 hosted grading draft: seven offline cases passed

One new selector passed all seven cases in **294.01s**, exit 0; its Python
wrapper elapsed **298.027932s** within the unchanged 300s+5s bound. This proves
the tested synthetic route, not a credentialed Actions run, actual hydration,
kernel support or a grade. No earlier selector ran again. The draft still
needs independent fixed-HEAD review/CI and one exact leader request before use.

The change adds one manual workflow, one controller/CLI and one focused test.
It reuses the accepted native context and executor without modifying them.
The [accepted compatibility record][prior] preserves PR776 source
`c8ee6ae03d7238c98f9e01f40733f94c1b717f54`, review `5448348919` and its eleven
successful CI checks. Its earlier incomplete proof and five-node continuation
remain separate from this new proof; their results are not pooled.

### Route and authority boundary

`gpt54-time-budget-native-task3-grade.yml` runs one controller process.
`prepare_native_task3_grading_execution` stays open from authenticated intake
through F preparation and grading-only staging, concrete direction validation,
private claim acknowledgement, `execute_native_task3_grading` and retention.
The live handle is never serialized, reloaded or reconstructed with a second
intake. The old V2-only API/CLI and its Step0 prohibition remain unchanged.

Public gates bind owner/repository/main/workflow, controller C commit/tree,
actual all-event run number, attempt 1 and the independent request digest
before credential-bearing steps. The ordinary Actions bootstrap stays distinct
from linked C/original R/F and private originals, hydration, preparation,
derived-input, attempt-store and grade paths. The request also binds the fixed
cell/result/output, original input facts, paths, finite admission window,
grading permission/budget and independently expected private parent.

Full original parquet/reference/218405-byte Step0 validation, the accepted
four-GET/60-second retained intake, genuine F preparation and model-free
direction checks precede the remote claim. The new grading-only private CAS
namespace keys the original observation and fixed F, not C/job/run number.
It neither reads/adopts an occupied claim nor overwrites generation state.
Wrong parent, occupied prefix or lost response/readback stops without retry.
Only an acknowledged claim permits the accepted executor's direction recheck,
local once-claim and single child. The local store is additional protection,
not distributed admission by itself.

OIDC login uses the existing connection after public gates and before opening
the context. HF credentials are confined to bounded intake/storage calls;
the F child receives neither HF nor GitHub tokens. Original generation/result
bytes, fingerprint and preparation remain immutable. Only the accepted,
separate grading input carries the authenticated publication origin and its
distinct identity/fingerprint. No caller-only origin or inference ledger is
introduced.

The F envelope remains 14400 seconds and the child envelope 14520 seconds.
The workflow has a 270-minute job cap, a 252-minute controller step, bounded
setup steps, a 300-second preclaim ceiling and existing 120-second private
storage sessions. The step leaves 180 seconds after the configured preclaim,
child and retention allowances for final checks/publication. These are
configured time bounds, not a measured host-readiness or monetary ceiling.
Concurrency is one; permissions remain contents-read/id-token-write. The
existing digest-pinned grading image and renderer are reused.

Available executor, grade, ledger, checkpoint and partial files are retained
privately. Child stdout/stderr are discarded by the accepted executor and are
explicitly unavailable, not claimed retained. Lost retention remains uncertain
and nonrenewable. A public completion contains only allowlisted binding,
status, count and hash fields; success needs a validated F grade and confirmed
retention. Public usage/cost/quality stay null, and raw errors/private prose,
filenames, paths, headers and credentials are not projected.

### One bounded proof

The sole invocation selected
`tests/test_time_budget_native_grading_ci.py::test_native_task3_hosted_grading_route`.
Parametrization, imported fixture symbols, syntax and workflow layout were
checked before launch. Python 3.10.12, 300s+5s/no-`-x`, named 30-second local
Git/Bash allowances and Python timing were used. A task-local hook flushed
node/phase reports and would flush an actual failure traceback immediately.
All seven cases finished and final JUnit was produced; no failure occurred.
Seven warnings concern `record_property` with JUnit `xunit2`.

| Case | Actual offline outcome |
| --- | --- |
| `guards` | Passed actual bootstrap Bash/CLI layout and wrong owner/source/attempt/run number/digest/cell/permission/credential refusals before intake or claims. |
| `original` | Passed altered original Step0 byte refusal before retained hydration, remote/local claim or child. |
| `file` | Passed retained-file digest refusal before preparation, remote/local claim or child. |
| `preparation` | Passed the real preparer's result-byte refusal before remote/local claim or child. |
| `success` | Passed native context, derived origin, permanent CAS/readback before local claim/child, real F validation and private retention. Independent synthetic stores also exercised occupied/wrong-parent/lost-response refusals; no claim was adopted. |
| `partial` | Passed synthetic failed-child grade/ledger/checkpoint retention with public partial status. |
| `timeout` | Passed synthetic child-timeout grade/ledger/checkpoint retention with public timeout status. |

Three full roundtrips each performed one synthetic child call; no paid child
or judge was run. Each used four synthetic original reads and the accepted
four retained GETs, an actual 218405-byte synthetic Step0 with its computed
hash, real native-capture-shaped bytes initially lacking origin annotations,
and the unchanged intake/preparer/executor/F validators. HTTP/auth/private CAS
RPC and namespace/owned-child facts were synthetic. No successful intake,
preparer or executor verdict was mocked. Local duplicate claims, expired live
handles, public leakage and credential-containing retention were refused.
The synthetic Task3 files were content-verified; this does not verify the
actual retained Task3 files or prove real host cleanup.

### Source and evidence identities

- Accepted base `a24c6dc9e9370362ce2adc886878b547b80cdc4c`, tree
  `3f94b28df6337ccd92f91b605f1c26bcf51f70a3`.
- Tested source `86d628b4d227b40787b1b958b54b6acb3a6aac51`, tree
  `ded2db9655c5ec581a9b64317ce35957348e1f45`.
- New controller blob `f12ec5f4a812d53e0105bee1fc01df10d34d3b74`, workflow
  blob `5dd06caef6d89104f5258597eac2bfa81a42bcf7`, test blob
  `89367c669766f0351f431e5a36c7a3e71e94fea6`.
- Unchanged executor blob `10d8e56c5569cc3dea484e4bb9d875712a0d5b4c`,
  intake blob `69982bebbe202d516eab101509635e037a7b8efd`, preparer blob
  `24a430137fb47bced1e5a450b5b5568d477a5b2e`; Step8/core/scoring and existing
  workflows are unchanged. No registration or historical source pin changed.
- Full registration seal
  `3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`.
- Proof directory `/tmp/native-task3-hosted-grade.b5J2SO/` contains
  `command.json`, `selection.json`, `source.json`, `pytest.log`,
  `reports.jsonl`, `cases.json`, `junit.xml`, `junit-cases.json` and
  `outcome.json`. The task-local reporting/wrapper sources are retained too.
- Log SHA256
  `df7116976e51f3b11690740d5e12efde7c2b5295cd10e8138dd4966c49941f34`;
  JUnit SHA256
  `f875deac34310eb562414071e2566f57e48aff33593896094898a79408775703`;
  outcome SHA256
  `2664034f8b633b98886a864f47290d3c646742ae589d3ce2b54cef1e7ae068cc`.

Only this record, CHANGELOG and direct README evidence change after testing.
`handoff.json` in that proof directory records exact final HEAD/tree, the
unchanged tested code blobs and artifact identities after that docs commit;
the final response and draft PR identify the same source. This avoids a
self-referential commit identity inside its own records.

### Actual Task3 is still ungraded

The fixed cell is `gpt54_sandboxv2_codex_time_budget_v1` /
`gpt54_time_budget_v1_codex_r1` / `codex` / repeat 1 /
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d`. Original R remains
`33e24e9c1402ec0b7c92a71222998d1407646a92`, tree
`6e67da4e12169b41a837d92eaf946db15e71010e`; generation run
`37631184801`, run number 5, attempt 1. The immutable output is
`d5aeecec1394fb44d4b1da33b1be38a39acdb89a`, generation claim
`08e485281f25ea06311305e7a4add721a68ba9ea`. Original result identity is
8518 bytes / SHA256
`4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4`,
fingerprint
`4a62be1df3e21eae52bd7814359887c5f774200948ba67fc15ca62bf2f4b2967`,
generation request SHA256
`3d2bbe5f55f0f0558f8e38bf53ebaa22f722b60b55b2338df465196b278ffc98`.
The leader's actual readout `37651509527` / artifact `11497400004`
independently matched that successful canonical result and declared two
files/408601 bytes. Their contents have not been hydrated or graded here.
Native usage/cost/served identity/counters remain unknown; `items_seen=56`
is not a model/request count. No quality score is established.

Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, template SHA256
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The original 218405-byte Step0 pin remains SHA256
`463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512`.
The fixed twenty-cell cohort, model, budgets, rubrics, filename policy and
scoring are unchanged. Task4's separate canonical error at
`82ed160109e40dcf74029f2be34a973350374fc6` remains unread internally and is
not evidence about Task3. Consumed observations remain nonrenewable.

Prior grading/extreme specialist invocations failed before execution on
unavailable configured model labels. They are not endorsements, and no
harness retry occurred. The leader's bounded implementation decision uses
the corrected native APIs; independent review/CI of this final route is still
required. Catalog/design/reporting guidance kept the study fixed and the
offline result separate from actual execution. English copyediting preserves
these facts and limits.

After review/CI, actual host/auth/input readiness, a live expected-parent
check and one exact leader request must still succeed. Existing finite budget
delegation does not authorize a dispatch from this implementation task. No
CI query/dispatch, live private fetch/claim, Azure/model/grade/readout, replay,
Task5, merge, Project edit or ABBA/next-cell advance occurred.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a24c6dc9e9370362ce2adc886878b547b80cdc4c/tasks/LATEST_TASK_RESULT/README.md
