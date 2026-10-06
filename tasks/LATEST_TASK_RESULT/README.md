# Latest task result

## PR757: eleven-node offline continuation

The one authorized continuation reported **10 passed, 1 failed in 68.02s**,
exit 1. All 11 selected nodes completed; none was skipped and no teardown
error occurred. The missing-usage case remains unresolved. No source or test
was changed, and no successful case was repeated after this result.

### Scope and reviewed source

The clean tested and leader-read HEAD was
`0fe559377bbbd20eab790dd7a5c48e4509911c90`, tree
`4bb9ff1cd758b247a7d304f86b3850ccdd34b87f`, on
`b/codex-time-budget-first-v2-actions-20261006`. The leader read the full
workflow/controller/tests and reused source/input/private-CAS primitives,
README and records, finding no additional blocking source defect in that
scope. The task instruction then authorized only the 11 previously failed
nodes. This review did not establish their test result or live authority.

The five-line fixture correction
`1585ef4309f03fc08d0e7c553341d62826b182d0` was already present. It matches the
workflow's cached SDK telemetry-disabled setting. Its earlier unrerun status
is preserved in the [immutable original handoff][original]. The workflow and
controller remain byte-identical to
`8be989167037f91b98866a2fdb8bc887b11a4c54`; the offline socket sentinel and all
real source/input/direction/digest validators are unchanged. No network
connection or successful-validator substitute was allowed.

The existing base `e2b8c5e15296eefbb2c1ee21d6b8ba3725d75506`, tree
`820bc59533a7fd6ba65e237501e6b3ce2c759ced`, is intentional for this proof.
Newer-main integration and record-conflict resolution remain the leader's
work. There was no merge, rebase, reset, stash or change to a prior worktree.
The leader-executed pre-edit charter review and failed reviewer-harness
provenance remain in the original handoff; neither review nor harness was
repeated. The catalog was checked once, retained source/CI guidance applied,
and no new experiment-design review was needed.

### Exact bounded invocation

Python was 3.10.12. The command checked the exact clean HEAD/tree and unchanged
workflow/controller before selecting only the 11 named nodes. It used tiny
synthetic inputs, genuine temporary source identities and the existing
ordinary transport seams, not a real provider or storage service. The complete
retained `command.sh` is:

```bash
#!/usr/bin/env bash
set -uo pipefail
cd /ai-work/copilot/worktrees/codex-time-budget-first-v2-actions-20261006/batch-runner || exit 2
[[ "$(git rev-parse HEAD)" == 0fe559377bbbd20eab790dd7a5c48e4509911c90 ]] || exit 2
[[ "$(git rev-parse 'HEAD^{tree}')" == 4bb9ff1cd758b247a7d304f86b3850ccdd34b87f ]] || exit 2
[[ -z "$(git status --porcelain)" ]] || exit 2
git diff --quiet 8be989167037f91b98866a2fdb8bc887b11a4c54 HEAD -- ../.github/workflows/gpt54-time-budget-first-v2.yml gpt54_time_budget_v2_ci.py || exit 2
[[ "$(/ai-work/venvs/gdpval-realworks-py310/bin/python --version)" == 'Python 3.10.12' ]] || exit 2
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -o addopts= -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --junitxml=/tmp/pr757-first-v2-continuation-proof.cQ5q9i/junit.xml \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_roundtrip[success]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_roundtrip[failed]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_roundtrip[missing_usage]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_roundtrip[not_started]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_genuine_validation_refusals[original_bytes]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_genuine_validation_refusals[direction]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_genuine_validation_refusals[preparation]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_cas_uncertainty_is_permanent[race]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_cas_uncertainty_is_permanent[lost]' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_new_dispatch_cannot_reclaim_observation' \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_retention_lost_response_and_envelope_allowlist' \
  2>&1 | tee /tmp/pr757-first-v2-continuation-proof.cQ5q9i/pytest.log
proof_exit=${PIPESTATUS[0]}
printf 'PROOF_EXIT=%s\n' "$proof_exit"
exit "$proof_exit"
```

Pytest reported **1 failed, 10 passed in 68.02s (0:01:08)**, exit 1. JUnit
records 11 cases, one failure, zero errors and zero skips. There was one
invocation, bounded by 300 seconds plus 5 seconds termination grace without
`-x`. The 14 previously passing nodes, full 25-node module, earlier study or
platform selectors and broad suites were not run.

Every node below belongs to `tests/test_time_budget_first_v2_ci.py`:

| Node | Outcome |
| --- | --- |
| `test_time_budget_first_v2_ci_roundtrip[success]` | Passed |
| `test_time_budget_first_v2_ci_roundtrip[failed]` | Passed |
| `test_time_budget_first_v2_ci_roundtrip[missing_usage]` | Failed |
| `test_time_budget_first_v2_ci_roundtrip[not_started]` | Passed |
| `test_time_budget_first_v2_ci_genuine_validation_refusals[original_bytes]` | Passed |
| `test_time_budget_first_v2_ci_genuine_validation_refusals[direction]` | Passed |
| `test_time_budget_first_v2_ci_genuine_validation_refusals[preparation]` | Passed |
| `test_time_budget_first_v2_ci_cas_uncertainty_is_permanent[race]` | Passed |
| `test_time_budget_first_v2_ci_cas_uncertainty_is_permanent[lost]` | Passed |
| `test_time_budget_first_v2_ci_new_dispatch_cannot_reclaim_observation` | Passed |
| `test_time_budget_first_v2_ci_retention_lost_response_and_envelope_allowlist` | Passed |

### First failing operation and retained outcome

The failing assertion is line 272 of the CI test: returned status was `error`,
not the expected `success`. The ordinary synthetic transport deliberately
returns `usage=None`. In unchanged
`core/agentic_v2_model_voice.py:510-517`, `_usage_from(response)` returns `None`
and `AzureFoundryVoice.next_turn` returns `GaveUp` before interpreting the
offered tool. This is an existing missing-usage refusal, not the earlier
telemetry failure. The existing entrypoint test at
`tests/test_time_budget_first_v2_observation.py:258,268-269` already expects
error and unavailable usage for this response. That test was read, not rerun;
neither expectation nor production was changed in this continuation.

The retained synthetic Step2 row has status `error`, terminal reason `failed`,
`usage: null`, `usage_complete: false`, one returned response and no
deliverables. Claim and execution reservation files remain present. The
missing-usage case stopped before its private-retention assertions, so that
path has no completed retention proof. Other cases passed their synthetic
success/failure/uncertainty retention, token-stripping, real-validator and
CAS/refusal assertions. None proves a real host, inference or publication.

The missing-usage result remains at
`/tmp/pytest-of-dev/pytest-225/test_time_budget_first_v2_ci_r2/time-budget-first-v2/result/step2_inference_results.json`:
6219 bytes, SHA256
`c199172d80580f3250a20e07fbf9ba91087871e94eb6e11dddd8be1cd84fa349`,
canonical result fingerprint
`87a03067ee350fec9cc55880c8ebc8aa7bfad7c790a96bad126ee7bfbbc7fc0d`.
The adjacent synthetic `execution-receipt.json` is 925 bytes, SHA256
`95eec6f3f093411366a4583a2f8e5d88ab9b35ff52000bb80064153fcb664767`.
Byte-identical copies are retained in the proof directory as
`missing-usage-step2.json` and `missing-usage-execution-receipt.json`.
These are explicitly synthetic diagnostics, not private live receipts.

Proof artifacts remain at `/tmp/pr757-first-v2-continuation-proof.cQ5q9i/`:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `73b276aa59d92f163de38945450875a973616be2f69d589497e4acbd07065467` |
| `pytest.log` | `fc917233f3da5eaf972efe02bd28f95a04afeb0f69bac669278a0716bbad36ef` |
| `junit.xml` | `93986783e4e610279d4e3b1b8c57520361fa30dba45b0e185b86f702cb95ddc0` |
| `receipt.json` | `d9324e07b53ed2cf6ca0b9d46a15f3379de5c832134e6d692a7d80f9416bb9df` |

The command digest identifies the complete retained file shown above,
including its source guards, not a shortened or redacted command.

### Separate prior evidence, post-proof delta and remaining gates

The [original invocation][original] remains **14 passed, 11 failed and
11 teardown errors in 16.57s**, exit 1, at
`8be989167037f91b98866a2fdb8bc887b11a4c54`, tree
`b93f57343935fd1a52b1f882e16662503904287c`. Its exact command, log, JUnit and
receipt at `/tmp/time-budget-first-v2-actions-proof.aB4lci/` were preserved
and their recorded SHA256 identities rechecked. The correction's unrerun
status at the prior handoff remains historical fact. This continuation is a
separate failed invocation, not an aggregate 25-pass result. Immutable links
in the original record preserve all earlier study, software, NAS-refusal,
CI-host and grading proofs separately.

The exact repository delta after this proof is `CHANGELOG.md`, this LATEST
record and only the directly affected evidence paragraph in
`batch-runner/README.md`. No source, test, workflow, configuration, source pin,
permission, claim, direction, limit or launch flag changed. The fixed study,
first cell, 1200/20-second policy and 45-minute job ceiling remain unchanged.
`im-not-ai-en` is limited to the changed English records and usage passage,
preserving counts, identities, failure semantics, links and pending gates.
One bounded changed-passage fidelity check passed without warnings; it was
an editorial check, not another software invocation.

Remaining work is the unresolved missing-usage test expectation and its
retention proof, leader-owned newer-main integration, integrated-HEAD review
and CI acceptance, and genuine source/input/host/private-parent values with
a separate leader-issued execution direction. The unchanged
[usage section](../../batch-runner/README.md#first-v2-observation-on-github-actions)
specifies the future command and required identities. Actual-host kernel
admission and provider identity checks remain mandatory; model-free test
results grant no live permission, backend-cancellation guarantee or money
cap. No CI query/dispatch/retry/poll, model/grader/HF/Azure operation, real
private-input or receipt access, Project edit or merge occurred.

[original]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/0fe559377bbbd20eab790dd7a5c48e4509911c90/tasks/LATEST_TASK_RESULT/README.md
