# Latest task result

## First fixed V2 observation: Actions route and private retention

The workflow and controller are implemented. The end-to-end offline proof
is incomplete. The one authorized invocation reported **14 passed, 11 failed
and 11 teardown errors in 16.57s**, exit 1. A five-line fixture correction is
committed but has not been rerun. This is a draft implementation handoff, not
live authority or a claim of a usable execution host.

### Scope and review provenance

Work resumed in `b/codex-time-budget-first-v2-actions-20261006` from accepted
`e2b8c5e15296eefbb2c1ee21d6b8ba3725d75506`, tree
`820bc59533a7fd6ba65e237501e6b3ce2c759ced`. Previous worktrees, PR756 and all
historical inputs/results remain untouched. There was no merge or rebase.

Before workflow edits, the leader performed the actual read-only decision
review against the repository extreme-reasoner charter and this accepted
source. The decision was APPROVE-WITH-CONDITIONS for implementation and one
synthetic proof only. The supervisor retains
`project5-first-v2-workflow-review-1440.md`; the operative conditions are in
the task instruction. This was a leader-executed charter review, not a
successful spawned-agent review. The separate local invocation failed before
execution because its resolved model,
`Claude Opus 4.7 (1M context) (strategy mode) (Preview) (copilot)`, was
unavailable. The repository agent definition has no model field; the causes
of the two earlier HTTP 400 failures remain unproven. No reviewer retry,
global preference, agent definition, billing provider or account change was
made after the leader's direction.

The new `.github/workflows/gpt54-time-budget-first-v2.yml` has one
`workflow_dispatch` job on Ubuntu 22.04/Python 3.10.12. It accepts only
`gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 /
`02aa1805-c658-4069-8a6a-02dec146063a`. The controller is
`batch-runner/gpt54_time_budget_v2_ci.py`; its focused tests are
`batch-runner/tests/test_time_budget_first_v2_ci.py`. These three new files
are the implementation delta. No existing production, core, workflow,
manifest, source pin, frozen F or grading byte changed.

The route checks repository/main/owner/workflow SHA, checkout commit/tree,
attempt 1, exact run number/cell, canonical paths and the independent request
digest before credentials. It validates genuine R/F and input-registration
sources, acquires only the registered V2 parquet/reference inputs and prepares
the real handoff. It does not use the local-only importer as credentialed
authority or read Codex Step0. A permanent observation-keyed private CAS claim
binds the actual source/input/preparation/host/run/job/attempt/paths before the
existing approved login and real first-V2 callable. Existing claims, parent
races, lost acknowledgements and partial state do not authorize another try.
The controller constructs the finite-window direction and passes its digest
independently. Host metadata does not bypass kernel ownership admission.

Permissions remain `contents: read` and `id-token: write`. HF credentials are
step-scoped; storage tokens are removed before inference. The 45-minute job
ceiling includes setup and retention. The registered GPT-5.4/direct-v1/xhigh,
20-observation design, concurrency 1, one external attempt and 1200/20-second
policy remain unchanged. No money cap or backend-cancellation guarantee is
claimed. The closed 30/8 studies and all existing launch guards stay closed.

### One bounded offline proof

The clean pinned implementation was `8be989167037f91b98866a2fdb8bc887b11a4c54`,
tree `b93f57343935fd1a52b1f882e16662503904287c`. The proof used Python 3.10.12,
tiny declared synthetic inputs, genuine temporary Git/source identities and
ordinary transport seams. No successful source/input/direction validator was
substituted. The complete retained `command.sh` is:

```bash
#!/usr/bin/env bash
set -uo pipefail
cd /ai-work/copilot/worktrees/codex-time-budget-first-v2-actions-20261006/batch-runner
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -o addopts= -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --junitxml=/tmp/time-budget-first-v2-actions-proof.aB4lci/junit.xml \
  tests/test_time_budget_first_v2_ci.py \
  2>&1 | tee /tmp/time-budget-first-v2-actions-proof.aB4lci/pytest.log
proof_exit=${PIPESTATUS[0]}
printf 'PROOF_EXIT=%s\n' "$proof_exit"
exit "$proof_exit"
```

Pytest reported **11 failed, 14 passed, 11 errors in 16.57s**, exit 1. There
were 25 unique selected nodes, zero skips and 36 JUnit records: each of the
11 failed nodes also had a teardown error. There was one invocation, bounded
by 300 seconds plus 5 seconds termination grace, without `-x` or a rerun.

The first failure was `prepare_and_claim` → `intake._hf_read` →
`build_hf_headers` → `_http_user_agent` → `detect_agent` → `_fetch_registry` →
the offline `socket.create_connection` sentinel. The SDK attempted its agent
registry lookup before reaching the synthetic original-file HTTP transport.
The sentinel blocked before connection; no external connection completed.
These failures do not prove the intended input/direction/CAS/retention
refusals or positive execution paths.

All nodes below are in `tests/test_time_budget_first_v2_ci.py`.
The 14 completed passes were:

```text
test_time_budget_first_v2_ci_authority_refuses_before_effects[digest]
test_time_budget_first_v2_ci_authority_refuses_before_effects[extra]
test_time_budget_first_v2_ci_authority_refuses_before_effects[source]
test_time_budget_first_v2_ci_authority_refuses_before_effects[tree]
test_time_budget_first_v2_ci_authority_refuses_before_effects[cell]
test_time_budget_first_v2_ci_authority_refuses_before_effects[stale]
test_time_budget_first_v2_ci_authority_refuses_before_effects[rerun]
test_time_budget_first_v2_ci_authority_refuses_before_effects[manual_number]
test_time_budget_first_v2_ci_authority_refuses_before_effects[workflow]
test_time_budget_first_v2_ci_authority_refuses_before_effects[host]
test_time_budget_first_v2_ci_authority_refuses_before_effects[input_anchor]
test_time_budget_first_v2_ci_genuine_validation_refusals[runtime_bytes]
test_time_budget_first_v2_ci_cli_request_validation_is_not_admission
test_time_budget_first_v2_ci_workflow_command_and_guard_contract
```

The 11 failed nodes, each also with a teardown error, were:

```text
test_time_budget_first_v2_ci_roundtrip[success]
test_time_budget_first_v2_ci_roundtrip[failed]
test_time_budget_first_v2_ci_roundtrip[missing_usage]
test_time_budget_first_v2_ci_roundtrip[not_started]
test_time_budget_first_v2_ci_genuine_validation_refusals[original_bytes]
test_time_budget_first_v2_ci_genuine_validation_refusals[direction]
test_time_budget_first_v2_ci_genuine_validation_refusals[preparation]
test_time_budget_first_v2_ci_cas_uncertainty_is_permanent[race]
test_time_budget_first_v2_ci_cas_uncertainty_is_permanent[lost]
test_time_budget_first_v2_ci_new_dispatch_cannot_reclaim_observation
test_time_budget_first_v2_ci_retention_lost_response_and_envelope_allowlist
```

Artifacts remain at `/tmp/time-budget-first-v2-actions-proof.aB4lci/`:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `80929d5afbdabb3f17207b7f976a033756c97a0ce0dd02c40d566bdac9ed50fc` |
| `pytest.log` | `e4509b0533aff0480825ae66c1afa6f752e33fd5e5413920c76cf6e68fb0581d` |
| `junit.xml` | `cc3987bda3241962c7f9c339281029dbab02f437bfb675569f2d8ab7e3df85bf` |
| `receipt.json` | `977ce1cadfea5b337371ac0650acef1b7781768cc4079717146e9d55fa587bd6` |

The command digest identifies the full retained file shown above, not a
redacted command. The original command/log/JUnit bytes are unchanged.

### Unrerun correction and exact post-proof delta

`1585ef4309f03fc08d0e7c553341d62826b182d0`, tree
`6b5443b2d96d2a89a0edd6e5413c752df0e3f83a`, adds five lines to the new test
fixture to set the SDK's cached `HF_HUB_DISABLE_TELEMETRY` constant. This
matches the already telemetry-disabled workflow. The correction is intended
to reach the fixture's transport seam without changing a validator. It has not
been rerun; it is not evidence that the 11 affected paths pass.

The repository delta after the pinned proof is exactly four files: that
five-line test-fixture change, `batch-runner/README.md`, `CHANGELOG.md` and
this LATEST record. The controller and workflow are byte-identical to the
tested implementation. No other source/test/configuration/pin change follows
the proof.

### Future command, output and remaining gates

The [usage section](../../batch-runner/README.md#first-v2-observation-on-github-actions)
contains the exact request schema. The future command shape is:

```bash
gh workflow run gpt54-time-budget-first-v2.yml --ref main \
  -f reviewed_source_sha=R_COMMIT \
  -f reviewed_source_tree=R_TREE \
  -f request_sha256=LEADER_RECORDED_REQUEST_SHA256 \
  -F request_json=@leader-request.json
```

This is documentation, not dispatch authority. After acceptance, the leader
must select the exact main/workflow commit and tree, genuine registration
and dataset identities, frozen/input-registration anchors, next exact run
number, canonical checkout/temp paths, private expected parent and a finite
admission window. The reviewed controller binds actual run/job/attempt/host
and verified input/preparation identities in the durable claim and direction.
No pending PR or old host receipt is an approved runtime or host substitute.

The existing private target receives only the new study/cell prefix:
`time-budget/gpt54_sandboxv2_codex_time_budget_v1/gpt54_time_budget_v1_v2_r1/02aa1805-c658-4069-8a6a-02dec146063a`.
Its objects are `admission.json`, `output-manifest.json`,
`result/step2_inference_results.json` and verified
`result/upload/deliverable_files/<task>/<file>`, with immutable commit and
byte readback. Failed canonical rows are retained; missing return remains
uncertainty, not a fabricated admitted row. Missing usage is unavailable,
not zero. Only schema-allowlisted `completion.json` metadata may be a public
Actions artifact. Original inputs, credentials, raw private receipts and
exceptions are excluded. No inference `source_repo_id` or `source_revision`
is invented, and there is no grading or grading-intake authorization.

The catalog was checked once. `experiment-design` preserved the existing
fixed study without reopening its design. Source/architecture/CI guidance
and the leader's review governed the implementation. `im-not-ai-en` applies
only to changed English passages, protecting failed outcomes, counts,
identities, links and remaining gates. One bounded changed-passage fidelity
check passed without warnings; it was an editorial check, not a software rerun.

Remaining work is evidence for the 11 unproved paths, final-HEAD source review
and ordinary CI acceptance, followed by genuine live values and a separate
leader-issued execution direction. Actual-host kernel admission, original
input validation and provider identity checks still apply to the future run.
The [immutable observation record][prior] preserves earlier 53/41/8-case,
entrypoint/correction, NAS-refusal and CI-host evidence through its links.
The [separate grading record][grading] preserves its distinct proofs and
filename measurements. None is blended with this failed invocation or rerun.
No dispatch, CI query/retry/poll/wait, real private-input access, provider/model/
grader/HF/Azure operation, Project edit or merge occurred in this task.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/39362bb804b1f0823091cb597e1d6ae4db58ec15/tasks/LATEST_TASK_RESULT/README.md
[grading]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/87fec0a0a4cd3b6b585896782a60690cd1cd7ca8/tasks/LATEST_TASK_RESULT/README.md
