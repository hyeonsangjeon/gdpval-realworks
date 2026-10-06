# Latest task result

## PR757: missing-usage failed-result retention proof

The corrected missing-usage test completed its full failed-result retention
path. The one invocation reported **1 passed in 15.88s**, exit 0. The only
software change is the test's two status expectations and assertions for the
exact missing-usage outcome. Production, workflow, response fixture, serializer
and validator bytes are unchanged. This is one synthetic proof, not a live
observation or publication.

### Scope and reviewed source

Work started from clean leader-read
`561219c661e8a5f05cd20c1637aac792d782a887`, tree
`42ab0ceae2b32f858618a0c7f9c99251ffde854a`, on
`b/codex-time-budget-first-v2-actions-20261006`. The leader confirmed the
existing missing-usage contract and directed this narrow test correction and
one-node proof. The established cause was not investigated again: unchanged
`AzureFoundryVoice` returns `GaveUp` when usage is absent, before interpreting
the offered tool. Its existing entrypoint test expects error/failed/no
deliverables and unavailable usage. Neither runtime policy nor the synthetic
response was changed to make the CI test pass.

The pinned correction is `d82fbd9b47b3af97d56510ee98db5370830d30fb`, tree
`c1da94784a28100f0ce10ff9607d6271e99b52c9`. Its entire delta is one test file,
17 insertions and two deletions. Both returned-status and envelope-status
expectations now classify `missing_usage` as `error` alongside `failed`;
`success` and `not_started`/`uncertain` remain distinct. Additional assertions
check canonical result semantics, exact retention identity and consumed
reservations. All existing admission/direction/claim/CAS/readback, credential
isolation and duplicate-refusal assertions remain in place.

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
workflow/controller before selecting only the missing-usage node. It used tiny
synthetic inputs, genuine temporary source identities and the existing
ordinary transport seams, not a real provider or storage service. The complete
retained `command.sh` is:

```bash
#!/usr/bin/env bash
set -uo pipefail
cd /ai-work/copilot/worktrees/codex-time-budget-first-v2-actions-20261006/batch-runner || exit 2
[[ "$(git rev-parse HEAD)" == d82fbd9b47b3af97d56510ee98db5370830d30fb ]] || exit 2
[[ "$(git rev-parse 'HEAD^{tree}')" == c1da94784a28100f0ce10ff9607d6271e99b52c9 ]] || exit 2
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
  --basetemp=/tmp/pr757-missing-usage-retention-proof.nGPcoc/pytest-tmp \
  --junitxml=/tmp/pr757-missing-usage-retention-proof.nGPcoc/junit.xml \
  'tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_roundtrip[missing_usage]' \
  2>&1 | tee /tmp/pr757-missing-usage-retention-proof.nGPcoc/pytest.log
proof_exit=${PIPESTATUS[0]}
printf 'PROOF_EXIT=%s\n' "$proof_exit"
exit "$proof_exit"
```

Pytest reported **1 passed in 15.88s**, exit 0. JUnit records one case, zero
failures, zero errors and zero skips. There was one invocation, bounded by
300 seconds plus 5 seconds termination grace without
`-x`. The only completed node was
`tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_roundtrip[missing_usage]`.
Neither the 10 nor the 14 previously passing nodes were repeated. The full
11/25-node selectors, prior platform/study selectors and broad suites were not
run, and there was no rerun after this result.

### Verified failed-result retention

The case reached all previously unreached private-retention assertions.
The canonical row retains status `error`, terminal reason `failed`, null
usage and `usage_availability.usage_complete: false`; its deliverable records
and file lists are empty, and no deliverable file is present. The unchanged
envelope has status `error`, terminal reason `failed`, `usage: null` and
`retention: acknowledged`. It has no new `usage_complete` field.

The real retention validators and existing synthetic storage transport
confirmed the private object bytes and immutable readback. The returned,
canonical and envelope result fingerprints match the recomputed fingerprint;
result byte identities also match. Claim and execution reservations remain
present. Existing duplicate execution and duplicate retention assertions
refuse another attempt, and the transport records only the claim and output
commits. Storage credentials remain absent during inference, original inputs
remain outside the public envelope, and V2 still has no Codex Step0 input.
The socket sentinel remained intact with no external connection. None of
this is evidence of a real host, model call or HF publication.

The synthetic result is retained under the proof directory at
`pytest-tmp/test_time_budget_first_v2_ci_r0/time-budget-first-v2/result/step2_inference_results.json`:
6219 bytes, SHA256
`2771a2d014ced95cbf4b2d73118861d5b981b8880a13e40653d4a74ddf3a89ba`,
canonical result fingerprint
`15f34d9da63186f177d7fbbdecdcba04f644539bb3d281076da930dfc5242aff`.
The same synthetic state's `completion.json` has SHA256
`b9e61b087221b5745431245b3e8d36e164283f8ec56bfb14a3286e3f7d43056e`.
These are explicitly synthetic outputs, not private live receipts.

Proof artifacts remain at `/tmp/pr757-missing-usage-retention-proof.nGPcoc/`:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `9d2e903ec1d3229e6d4eb0353f6a6a34d72c23821cb70d8712d1fd605386dbbe` |
| `pytest.log` | `1a9cb27d74be42836805f4c7852da62be47729b730aed55aa58a841f8eb7609d` |
| `junit.xml` | `48d7dfbedd308503b11f7a284c9f07856e1074922fb3d12a100e249bdb0c55dd` |
| `receipt.json` | `17bece34c94fdfaa409922e75dff390a968a0a293a93af38f3da80e1c47f7b31` |

The command digest identifies the complete retained file shown above,
including its source guards, not a shortened or redacted command.

### Separate prior evidence, post-proof delta and remaining gates

The [11-node continuation][continuation] remains **10 passed, 1 failed in
68.02s**, exit 1, at `0fe559377bbbd20eab790dd7a5c48e4509911c90`, tree
`4bb9ff1cd758b247a7d304f86b3850ccdd34b87f`. It stopped the missing-usage case
before private-retention assertions; its exact artifacts remain at
`/tmp/pr757-first-v2-continuation-proof.cQ5q9i/`.

The [original invocation][original] remains **14 passed, 11 failed and
11 teardown errors in 16.57s**, exit 1, at
`8be989167037f91b98866a2fdb8bc887b11a4c54`, tree
`b93f57343935fd1a52b1f882e16662503904287c`. Its exact command, log, JUnit and
receipt at `/tmp/time-budget-first-v2-actions-proof.aB4lci/` were preserved.
Both earlier artifact sets had their recorded SHA256 identities rechecked.
The telemetry correction's unrerun status at the original handoff remains
historical fact. This one-node pass does not turn either failed invocation
into a pass, and no aggregate 25-pass result is claimed. Immutable links
in the original record preserve all earlier study, software, NAS-refusal,
CI-host and grading proofs separately.

The exact repository delta after this proof is `CHANGELOG.md`, this LATEST
record and only the directly affected evidence paragraph in
`batch-runner/README.md`. The total correction also includes the pinned test
change; no further test change follows the proof. Production, workflow,
configuration, source pin, permission, claim, direction, limit and launch-flag
bytes remain unchanged. The fixed study, first cell, 1200/20-second policy
and 45-minute job ceiling remain unchanged.
`im-not-ai-en` is limited to the changed English records and usage passage,
preserving counts, identities, failure semantics, links and pending gates.
One bounded changed-passage fidelity check passed without warnings; it was
an editorial check, not another software invocation.

Remaining work is correction review, leader-owned newer-main integration,
integrated-HEAD review and CI acceptance, and genuine
source/input/host/private-parent values with a separate leader-issued
execution direction. The unchanged
[usage section](../../batch-runner/README.md#first-v2-observation-on-github-actions)
specifies the future command and required identities. Actual-host kernel
admission and provider identity checks remain mandatory; model-free test
results grant no live permission, backend-cancellation guarantee or money
cap. No CI query/dispatch/retry/poll, model/grader/HF/Azure operation, real
private-input or receipt access, Project edit or merge occurred.

[original]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/0fe559377bbbd20eab790dd7a5c48e4509911c90/tasks/LATEST_TASK_RESULT/README.md
[continuation]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/561219c661e8a5f05cd20c1637aac792d782a887/tasks/LATEST_TASK_RESULT/README.md
