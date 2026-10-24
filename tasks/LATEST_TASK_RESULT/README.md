# Latest task result

## GHCP Sol gate: offline limit guards; live task limits remain open

Scope: the leader's **2026-10-25 00:15 KST** order on
`leader/ghcp-sol-gate-actions-20261024`, in
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`.
The starting worktree was clean at HEAD
`fe863326f996fe8708cd4098b7ec6ad7dd61905b`, tree
`554c58d5645d8eb96f9199ec875b80fb4e3a2434`.
Only the gate collector, its test module, the direct gate memo and these two
completion records changed. No plan, cap value, workflow, pin, dependency,
permission or unrelated worktree changed. Delivery is local only, not publication.

### Current result

The collector now stops offline event consumption at the existing draft's
**1200-second** deadline or its **65th turn-start event**, closes the input
generator and returns a failed receipt with exit **2**. It does not supervise
live GHCP execution. No GHCP-to-Codex adapter, model launcher or child-process
owner exists in this route; those gaps are not closed by an offline fixture.

| Per-task item | Before | After and fixed reason |
| --- | --- | --- |
| Wall-clock timeout | 1200 seconds was recorded only. The workflow already enforced 60 seconds/process plus 5 seconds for forced termination and 5 minutes/job for the dry run. | Local event collection has a cumulative monotonic deadline and an interrupting signal: `task_timeout_exceeded`. Workflow limits are unchanged; live task timeout remains unverified. |
| Tool-call cap | No value in the current Actions draft or inert GHCP VM execution block. | Still null with `value_not_defined`; no cap or tool-limit refusal is invented. |
| Turn cap | 64 turns was recorded only. | Accept at most 64 supplied `assistant.turn_start` events; stop on the 65th with `turn_cap_exceeded`. Live pre-call enforcement remains unverified. |

The new deadline starts at event collection, not at task setup or at a timestamp
inside the supplied file. The outer workflow process limit is shorter and
unchanged. Unsupported timer ownership or a worker-thread caller refuses with
`task_timeout_guard_unavailable`; missing, malformed or duplicate turn identity
refuses with `turn_count_unverified`. The count includes supplied sub-agent
turn starts, not usage events or native requests. Missing turn events cannot
establish zero live turns or stream completeness. Cleanup failure records
`session_event_cleanup_refused`. The receipt labels subprocess cleanup
`not_applicable_no_subprocess_started`; this is not proof of GHCP child cleanup.

Usage and cost were already null rather than zero. They remain null to preserve
nullable values, now with explicit **`not available`** statuses and fixed
not-collected reasons. No cost estimate or tariff is introduced. Grade stays null.
Model/effort/context capture, Auto/BYOK refusal, source/input/grader pins,
parser bounds and no-retry behavior are unchanged. Per-call metadata remains
**settings only**: actual served model, applied Max and granted 1M are unverified.
`paid_execution_allowed`, `retry_allowed` and `live_enforcement_verified` remain
false. No historical result, score, entitlement or consumed cell is changed.

The [limit audit](../../docs/ghcp-sol-actions-gate.md#offline-capture-limits-2026-10-25-0015-kst)
records the scope and the continuing live-adapter gap. No paid path was added.

### Verification and source identity

Implementation commit **`6ab43d4c7198e9e720fabeac5cb0d796b68cc5c7`**, tree
**`7ac1c0ff646ccbf78a8c9389c26425d4da98df4b`**, was clean before collection and
the test invocation. Title: **Bound offline GHCP capture time and turn events**.
The later completion-record commit changes documentation only. Its full HEAD,
tree and clean status are retained in the evidence directory's `final-source.txt`.
No fixed-head review or CI approval is claimed for either new local commit.

Using the existing Python **3.10.12** environment, collection reported **231
nodes in 0.28s**, wrapper **0.459s**, exit **0**. One combined invocation then
reported **231 passed, 0 failed, 0 skipped in 10.66s**; wrapper wall time
**10.841s**, exit **0**. This is **138 Actions capture checks** (25 new plus
113 existing) and **93 unchanged VM gate checks**. No retry or second test
invocation occurred. It is the requested gate bundle, not the full repository
suite, hosted CI or a five-task model experiment.

Synthetic cases check 63/64/65 turn starts, cumulative timeout and EOF, an
accelerated real OS alarm at a blocked read, signal restoration, actual
synthetic-file closure, invalid turn identities, unavailable usage/cost and
canary non-egress. New capture fixtures trap network and runtime-process calls;
the existing workflow tests execute only local bash guards. No real session,
model, child runtime, credentials or private inputs are used.

The **prior** JUnit was read, not rerun, to recover the clipped selection proof:
**Auto 4 passed**, **BYOK 2 passed**, custom-provider argument **2 passed**, and
other-model selection **4 passed**, all with **0 failures**. That is the prior
12-case matrix/capture refusal group. It also passed within this new combined
invocation. The prior **204 passed in 9.89s** and separate **7 passed in 0.23s**
remain source-specific evidence, not additions to 231. Their exact record is
local Git `fe863326f996fe8708cd4098b7ec6ad7dd61905b:tasks/LATEST_TASK_RESULT/README.md`;
the prior JUnit remains `/ai-work/copilot/_tmp/ghcp-sol-event-capture.4SVuxo/junit.xml`,
**31572 bytes**, SHA-256
`2deb9b984634ab9789f99b23b7eca02b89c0e046f90c67ad2ca475a4ae76cbe7`.

The tested two-file code patch is **20641 bytes**, SHA-256
`1d5965a7881f124c966e9cea310b849a66ab31b0bbfd966168e49173541d1b84`.
Executable and test identities, unchanged by the record edits:

| File | SHA-256 |
| --- | --- |
| `batch-runner/ghcp_sol_actions_gate.py` | `d757aafd7c18c32f6682b79ebd4f51bc901d58f2fa97c8c50030e1b4762ed698` |
| `batch-runner/tests/test_ghcp_sol_actions_gate.py` | `dab87ec665f68562fc95d3f9ef32855e9448e52d921f941f544cd500a61f5b57` |
| Unchanged `.github/workflows/agentic-v2-ghcp-sol-gate.yml` | `455a7bca26dd866ac0f897ea4d2dc607250bf05514e285156ec09a89431ddd31` |
| Unchanged `batch-runner/experiments/execution_envelope/gpt56_sol_ghcp_codex_vm_gate.yaml` | `121ae4dd3cfa901c5dd590d81e66318034efef7d0ecafc966b9db4f4d8740b5c` |

From the worktree's `batch-runner` directory, the exact combined command was:

```bash
timeout --signal=TERM --kill-after=5s 120s env -i PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python -m pytest -q -ra --tb=short -o addopts= -p no:cacheprovider --junitxml=/ai-work/copilot/_tmp/ghcp-sol-task-limits.Ir6lIX/junit.xml tests/test_ghcp_sol_actions_gate.py tests/test_ghcp_vm_gate_contract.py
```

Evidence directory: `/ai-work/copilot/_tmp/ghcp-sol-task-limits.Ir6lIX/`.
Both collection and bodies used **120s TERM + 5s KILL**. The exact collection
command is also in `invocation.txt`.

| Artifact | SHA-256 |
| --- | --- |
| `invocation.txt` | `f2b6e029ec414738cded1dabab86aa8d75cd53413f40bea36f18cc35f31d85e3` |
| `collection.log` | `6db5cfa2a3d1a1fb3a227d6813b760d7b1e4f06b7bf35b2372c4bfcc965b3a5e` |
| `collection-timing.txt` | `887285ab48df8bf0b7d1e3433e2add70469ebbe3ebe02e53bf647cc1186e6d21` |
| `test.log` | `5986f1c324c2c7ff14b8927b144636d7b53e6c212f324b224cb8b643cd794db5` |
| `junit.xml` | `c2ba3645d2b65071b497982fa7ec1cbe496cb0483b2e571b6df7972feb7eee66` |
| `timing.txt` | `606acfdbe434622a99c403a603a68b426ec11ea1baa9394b79dc6c4f049f4274` |

### Evidence limits and remaining gates

**No actual GHCP output was inspected.** The turn fixture follows the previously
cached `github-streaming-events.md:297-305` under
`/ai-work/copilot/_tmp/ghcp-sol-evidence-audit.Rqg0rU/`, SHA-256
`91feefbc0a9a1809aeeb6adfa6ffd4300c9690850ff02a4333f61f53348d208b`.
It describes `assistant.turn_start` as a turn-processing event, not a pre-call
permission hook. The existing [field/authentication audit](../../docs/ghcp-sol-actions-gate.md#evidence-and-authentication-audit-2026-10-24)
preserves the other documentary candidates and their limitations.

Paid execution remains blocked on the absent tool-call cap value, approved
limits and usage policy, a reviewed live adapter with pre-effect accounting and
child-process cancellation, applied-settings evidence, authentication isolation
and disposal, original-input verification, grader validation and fixed-source
review/CI. Offline stream interruption cannot undo historical effects or prove
that a live 65th turn was prevented. Prior reviews do not approve the new source.
No publication, hosted validation, performance result or study completion is
claimed. Root and other worktrees remain unchanged.

`experiment-report-en` keeps configuration, offline enforcement and live proof
separate and preserves test populations; `im-not-ai-en` guides the English
records without strengthening claims. No experiment-design or UI skill applies;
no model/provider documentation fetch was needed for this local collector edit.
No Azure/model/GHCP call, authentication, credential/private-input read, workflow
dispatch, grading, push, PR or Project change was performed.
