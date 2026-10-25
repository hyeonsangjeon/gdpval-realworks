# Latest task result

## GHCP Sol gate: disabled process-adapter skeleton

Scope: the leader's **2026-10-25 10:35 KST** order, local implementation and
synthetic verification only. The existing branch is
`leader/ghcp-sol-gate-actions-20261024`, in
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`.
It was clean at HEAD `a40eb9f1e8781d92bb5c016c38da6b453e34d54e`, tree
`c5f723c198a78eede9654c20f05ba19a7c6fcb33`. The nested path in the order was
absent; this registered worktree matched its branch and HEAD. No worktree was
created, and the root checkout and other branches were not changed.

### Result and boundaries

Added `batch-runner/ghcp_sol_execution_adapter.py::run_task` and its synthetic
test module. The adapter accepts an explicit argv, not an inferred GHCP
command. `execution_enabled=False` is the default and refuses before process
creation. A missing/null `execution_config["tool_calls_per_task"]` refuses
with `tool_call_cap_missing`; non-positive or non-integer values refuse with
`tool_call_cap_invalid`. No default or paid tool-call value was selected.

| Per-task bound | Before | New adapter |
| --- | --- | --- |
| 1200 seconds | Offline collection only | Monotonic deadline started before launch and checked during reads/EOF; `task_timeout_exceeded`. |
| 64 turns | Offline collection only | Agent-scoped start events counted while the child runs; stop when 65 is observed with `turn_cap_exceeded`. |
| Tool calls | Undefined | Explicit positive value required; stop at the first observed excess with `tool_call_cap_exceeded`. No value was added to a plan. |

The child has its own POSIX process group. TERM is followed by KILL, with a
one-second grace and four-second final wait. The leader remains unreaped until
group signalling to avoid PID reuse during descendant cleanup. The receipt
records signals, leader reaping and stdout closure; private partial files
remain untouched and are not uploaded. Group signals are not containment of
processes that escape the group, nor proof that every orphan was reaped.
The fake-process tests check that their known child/grandchild PIDs no longer
run, treating zombies as exited rather than falsely calling them reaped.

The existing collector is reused for bounded, allowlisted per-call metadata.
The outer receipt describes adapter counts and cleanup; its nested collector
receipt retains collection-only labels. No raw conversation, event identity,
command, path, stderr, header or credential appears in the receipt. Usage and
cost remain null with `not available`, grade remains null, and metadata is
**settings only**, not applied-Max/1M or served-model proof. Paid authority,
retry authority, live-source and stream-completeness verification remain false.
Auto/BYOK checks, old collector behavior, workflow, plans, cap values, pins,
QA, dependencies, scores and consumed rights are unchanged.

### Verification

The existing Python **3.10.12** environment collected **295 nodes in 0.80s**,
wrapper wall time **1.79s**, exit **0**. One combined invocation then passed
**295 tests, 0 failed, 0 skipped in 15.79s**, wrapper wall time **15.96s**,
exit **0**. JUnit confirms **138 existing Actions checks + 93 existing VM
checks + 64 new adapter checks**. Auto/BYOK tests are included. There was no
failed invocation or test retry, and no full-repository suite was run.
Both collection and bodies used **120s TERM + 5s KILL**.

The new cases launch only a generated Python fake executable under a minimal
environment. They cover 63/64/65 turns; configured tool caps with below/exact/
above counts; 1199/1200/1201 seconds on a fixed-origin fixture clock; blocked,
partial-line and closed stdout; absent/invalid caps and disabled flags;
duplicate/malformed identities and streams; private-canary exclusion; partial
files; and group cleanup with children/grandchildren, ignored TERM and an early
leader exit. Deadline fixtures accelerate the clock, not the declared cap.
Network/provider imports and network calls are trapped in the tests. Only the
fake program can be launched by the new module's fixtures.

The prior **231 passed in 11.36s**, wrapper **11.575s**, remains a separate
proof of the earlier unchanged collector. Its record is retained at
`a40eb9f1e8781d92bb5c016c38da6b453e34d54e:tasks/LATEST_TASK_RESULT/README.md`.
It is not added to the new 295-test result.

The tested worktree contained base HEAD `a40eb9f1e8781d92bb5c016c38da6b453e34d54e`
plus the two new source/test files below. It was not a clean tested commit.
Documentation was updated after validation. The final local commit's source
identity and clean status are in the evidence directory's `final-source.txt`;
the final source/test hashes must equal these tested identities.

| File | Tested SHA-256 |
| --- | --- |
| `batch-runner/ghcp_sol_execution_adapter.py` | `e9b399dd5e222d5f3c6587f59937a608ea433db1d0bdfa5b1f52753f6a8436fb` |
| `batch-runner/tests/test_ghcp_sol_execution_adapter.py` | `796f34e7855da6b5d3b6c8f4ef15772905ed3752868e7049c9e75d549c24d29c` |
| Unchanged `batch-runner/ghcp_sol_actions_gate.py` | `d757aafd7c18c32f6682b79ebd4f51bc901d58f2fa97c8c50030e1b4762ed698` |
| Unchanged workflow `agentic-v2-ghcp-sol-gate.yml` | `455a7bca26dd866ac0f897ea4d2dc607250bf05514e285156ec09a89431ddd31` |
| Unchanged VM gate plan | `121ae4dd3cfa901c5dd590d81e66318034efef7d0ecafc966b9db4f4d8740b5c` |

Evidence directory: `/ai-work/copilot/_tmp/ghcp-sol-process-adapter.D6V4IC/`.
From the worktree's `batch-runner` directory, the combined command was:

```bash
timeout --signal=TERM --kill-after=5s 120s env -i PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python -m pytest -q -ra --tb=short -o addopts= -p no:cacheprovider --junitxml=/ai-work/copilot/_tmp/ghcp-sol-process-adapter.D6V4IC/junit.xml tests/test_ghcp_sol_actions_gate.py tests/test_ghcp_vm_gate_contract.py tests/test_ghcp_sol_execution_adapter.py
```

| Artifact | SHA-256 |
| --- | --- |
| `invocation.txt` | `7add8114d522879437bfe9d7f86b646e3c9a7a80ae6c47ad45d1b8f8a3d35600` |
| `collection.log` | `c18ed8c91742fa65e60185fb80dd46dbb5248f9d3c8f24ee61fae75808b9be7c` |
| `collection-timing.txt` | `216b5343d18a1a92dc4df036ac872fd4058d00fd39d87802254e7a60de74a1f2` |
| `test.log` | `d19b451309c8c4a777686d61879b9a0cb6afe97920abb381b05fdbabbb3d30f0` |
| `junit.xml` | `bcb3a912a1b11e549626df7a73570a0fdf94069dbd90a6cb0b3f26dec9dd07ec` |
| `timing.txt` | `bbc6a29d5e4f60ff87a9ac716b9d2129b0d3a0aaa8f7cbfa7723ec832a5f770f` |
| `tested-files.sha256` | `7de328b2132031509bedc8432f190a011a3951339bfa63edc064f6fbdaf511f4` |

### Remaining live gates

**No actual GHCP CLI command or output was validated.** The command/version
that binds GHCP to the Codex harness is still unknown; substituting a Copilot
custom-agent flag is not that binding. Fixtures use the previously documented
`assistant.turn_start`, `tool.execution_start`, `assistant.usage` and
`session.usage_info` envelope. Whether the eventual CLI emits those fields
completely and promptly, including sub-agents, remains unverified.
Start notifications can arrive after effects begin; this cancellation guard
does not prove pre-effect exclusion of an excess turn/tool action.

The workflow remains dry-run only. A reviewed command/event adapter binding,
an approved tool-call cap, authentication supply/disposal and isolation,
verified original inputs, applied-settings and grader evidence, and fixed-source
review/CI still precede any separate leader execution decision. No new launch,
retry, performance, cost, score, publication or study-completion claim is made.
The [direct memo](../../docs/ghcp-sol-actions-gate.md#disabled-process-adapter-2026-10-25-1035-kst)
keeps the implementation and historical audit boundaries separate.

`experiment-report-en` separates observed fake-process behavior from live
GHCP hypotheses and keeps test populations distinct. `im-not-ai-en` preserves
those qualifications in the English records. No experiment redesign or UI
skill applies; no new model documentation lookup was needed. No network,
GHCP/model call, authentication or secret read, private input, paid execution,
workflow dispatch, grading, push, PR or Project edit occurred.
