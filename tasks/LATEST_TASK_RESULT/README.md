# Latest task result

## Positive owned-host CI evidence — 2026-10-05

The one authorized offline invocation reported **46 passed in 15.76s**, exit 0,
at `b091071f19ca24f973101af67ed5b25e3ac500f2`, tree
`6a416fda9cf47b521951bcb9eeee7ecb665c399b`. It covered 43 synthetic
extractor/receipt/wiring cases and three existing workflow contracts. No target
failed, errored, skipped or remained incomplete. There was no retry.

This is software evidence only. The real platform probe was not run locally,
and no new positive CI receipt has been observed. Host support, CI acceptance
and live authorization are not established by this result.

### Scope and behavior

The existing
`test_time_budget_observation_deadline_process_ownership_platform_contract`
still runs once in the existing comparison-contracts Linux job's ordinary
selection. Its isolated-process 10-second timeout, 2-second termination wait and
5-second orphan failsafe are unchanged. Local development may still report
`admission_refused`; that outcome is not positive CI admission evidence.

The case now records `time_budget_owned_host_platform` as a JSON-valued JUnit
property. The same comparison invocation writes a temporary xunit1 report with
captured logging disabled and refuses a pre-existing report path. One new
metadata-only step requires the comparison invocation to have succeeded, then
requires exactly one completed, non-skipped/non-error platform case with
`platform_result=real_reparenting_confirmed` and `host_reusable=true`. Missing,
duplicate, malformed, refused, skipped, failed or errored evidence fails closed.
This step does not rerun the probe.

`batch-runner/scripts/verify_time_budget_owned_host_ci.py` bounds its XML input
to 8 MiB, the outcome to 1024 bytes and the JSON receipt to 4096 bytes. It rejects
nonregular/symlink reports, XML declarations for entities, duplicate JSON keys,
unknown outcome fields and incorrect case identity. Four bounded read-only Git
commands validate the full CI-supplied SHA, its tree and tracked cleanliness;
the verifier repeats that source check before publishing an outcome. Each Git
command has a 5-second limit. The new metadata step has a 1-minute limit; all
existing job timeouts remain unchanged.

The retained receipt binds the actual checked-out commit/tree, run ID, job key,
attempt and allowlisted runner metadata. The runner name is represented only by
its SHA256. The job summary receives the small JSON receipt, not the temporary
JUnit report, captured log bodies, original inputs, credentials, environment
dumps or signed URLs. The receipt explicitly marks synthetic/model-free platform
evidence, `study_observation=false` and `live_authorization=false`. It is not
approval for a different host, source, observation or execution path.

### Pre-edit review and source roles

Before editing the workflow, the same-session read-only role followed
`.github/agents/extreme-reasoner.md` and returned APPROVE-WITH-CONDITIONS at the
accepted source. The [existing probe][accepted-probe] accepted either refusal or
positive reparenting, while the [comparison job][accepted-job] had no structured
outcome requirement. The role review required strict positive evidence without
another probe, expanded permissions or a runtime change. It is not independent
owner review of this implementation.

The review covered false-green and source-substitution risk, partial/duplicate
evidence, secret exposure, cost, concurrency and reversibility. Conditions were
to bind the checked-out source to the independent CI SHA, retain only safe
metadata, reject stale report paths and unsuccessful invocations, and leave all
checkout/marker/integration/timeout guards intact. Added work is XML/local-Git
metadata processing and synthetic tests, not another kernel lifecycle or any
paid operation. A normal follow-up revert can remove this gate without changing
runtime behavior or historical evidence.

The [current/frozen binding split][binding-roles] was audited before edits.
`CURRENT_WORKFLOW_SHA256` alone advances. The historical reconstruction checks
every added step field, command option, step ID and no-clobber guard exactly
before removing only those additions. The existing PR749 inventory normalization
remains explicit. Historical canonical and frozen-fixture hashes are unchanged.

| Identity | Value |
| --- | --- |
| Accepted source basis | `b057f176f1cbddb77091546d3d7a3e22985a35f6` |
| Basis tree | `249e1ab2fba761cf3f49f460ef71ef246a1ba6e8` |
| Leader-reviewed predecessor | `50d7c11a027396d838a838ce2168f266774df61a`; review `5415947589` |
| Tested implementation | `b091071f19ca24f973101af67ed5b25e3ac500f2` |
| Tested tree | `6a416fda9cf47b521951bcb9eeee7ecb665c399b` |
| CURRENT workflow SHA256 | `b428849ab15f2fe28cef62b89e1bb8fa644eea09043a1cbfbbd8e4adde256111` |
| Unchanged historical canonical SHA256 | `fd2871a0ec60895d50fd16650a0ddfe47b71634a53fe0164b2fb765ea3319c47` |
| Unchanged frozen pilot workflow SHA256 | `b617f79a09427f9b877e9fef214bdf2fe96ba817fc8debf5369b4f172640f9da` |

The leader supplied the predecessor's 15 successful applicable checks and
PR-only deploy skip. Those are prior evidence, not CI results for this change.
Core runtime, ownership/finalization, the grader hash algorithm, both original
profiles, frozen F and study policy are unchanged. No dispatcher/capture path,
execution-enable flag, provider credential or launch refusal changed.

### One offline selector

Python 3.10.12 / pytest 9.1.1 ran the `owned_host_ci_evidence` selector once from
the clean pinned implementation. The environment was token-free, integration
tests were explicitly excluded, and `-x` was not used. The existing partition
contract performed its own scoped collect-only checks; these do not execute the
collected test bodies. The new extractor tests used tiny synthetic JUnit/receipt
files and controlled Git replies, not real source materialization or a real
owned-host lifecycle.

The display below redacts private executable/evidence paths. The preserved
private script also asserts the exact HEAD/tree and a clean worktree. Its digest
does not identify this redacted text.

```bash
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH="<EXISTING_PY310_BIN>:/usr/bin:/bin" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  "<EXISTING_PY310_BIN>/python" -m pytest \
  -o addopts= -p no:cacheprovider -m "not integration" -vv --tb=short --color=no \
  --basetemp="<PRIVATE_PROOF_DIR>/pytest-tmp" \
  tests/test_time_budget_owned_host_ci.py \
  tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_budget_readout_partition_preserves_exact_commands_and_guards \
  tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts \
  tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition
```

| Private proof artifact | SHA256 | Bytes |
| --- | --- | --- |
| Exact command | `4cd8e0c622094d1391cda4d3dfbffd1bba9a5b2cbe5e0c530d2a87e7ddbd25c4` | 1253 |
| Log with all 46 completed node IDs | `a91414004faf1e50c1380b65ab95a8fa8f68ac4839bb0f8726ab97a6c092e0aa` | 5826 |
| Offline software-proof receipt | `424a2dff742e78447629b53aa80d8f26f90521e4fc091c2ec4f88edd2c40e634` | 1901 |

The result was 46 passed in 15.76s, exit 0, within the 300-second bound plus
5-second termination grace. No successful selector was repeated, and no global
all-tests-pass or real-platform success claim follows.

### Remaining evidence and exact post-proof delta

The implementation changes six files: the existing backend workflow, the probe
test, the dedicated metadata verifier and synthetic test file, the workflow
partition contract and its CURRENT digest expectation. After the pinned proof,
only `CHANGELOG.md` and this single current record change. No workflow, helper,
test, source pin or runtime edit follows the proof.

The [immutable prior record][prior-record] and its links preserve the original
46-pass/5-fail invocation, five-target continuation, 21-case finalization,
30-case ownership and 23-case compatibility proofs as separate observations.
The NAS `time_budget_owned_process_host_required` refusal with
`FileNotFoundError`, errno 2 remains a refusal, not real orphan-cleanup success.
None of those proofs or the real platform probe was rerun here.

The next evidence is the ordinary CI job's actual positive receipt at its
validated checked-out commit/tree, followed by leader review and applicable CI
acceptance. No CI query, dispatch, rerun, polling or waiting was performed.
Host support remains unproved until that receipt exists. Dispatcher/capture
selection, credentialed inputs, F-derived grading execution and separately
reviewed source-bound live direction remain distinct, unresolved gates. A
positive synthetic platform receipt will not itself authorize a study run,
prove remote cancellation or establish billing behavior.

The full supplied skill catalog was read once. The source/architecture CI charter
governed the pre-edit decision, and `im-not-ai-en` preserved the English records'
facts and evidence limits. Its bounded evidence-paragraph fidelity check exited
0 with no failures or warnings; this was not another software selector.
No new experiment design or UI/animation skill was
used. No model/grader/HF/Azure operation, original/consumed-artifact access,
source preparation/materialization, infrastructure purchase, Project edit or
merge occurred. Previous worktrees, inputs and evidence remain untouched.

[accepted-probe]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b057f176f1cbddb77091546d3d7a3e22985a35f6/batch-runner/tests/test_gpt54_time_budget_comparison.py#L808
[accepted-job]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b057f176f1cbddb77091546d3d7a3e22985a35f6/.github/workflows/backend-tests.yml#L248
[binding-roles]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b057f176f1cbddb77091546d3d7a3e22985a35f6/batch-runner/tests/test_ghcp_vm_gate_contract.py#L25
[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/50d7c11a027396d838a838ce2168f266774df61a/tasks/LATEST_TASK_RESULT/README.md
