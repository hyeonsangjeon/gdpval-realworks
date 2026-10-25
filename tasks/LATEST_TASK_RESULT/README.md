# Latest task result

## GHCP Sol gate: installed CLI help and schema evidence

Scope: the leader's **2026-10-25 12:15 KST** order. This is a local
help/package investigation with synthetic fixture verification, not a GHCP
session, model measurement, launch approval or study completion. Worktree
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`, branch
`leader/ghcp-sol-gate-actions-20261024`, was clean at
`6ceb602bf99e418f932bf7c2fd9d5594b1429e66`, tree
`e4dd1dd7dc1bf12fc4e0811d0c927a77de08db1b`. No other checkout was changed.

### Result

**The exact GHCP -> Codex + Sol + Max + numeric 1M command remains unknown.**
Copilot help confirms noninteractive `-p`, model/effort/context-tier selection
and stdout JSONL; `--agent` means custom agent, not a Codex harness binding.
`long_context` is not proof of numeric or applied 1M. Direct host executable
versions with update/cache selection disabled are **1.0.103** (Desk runtime;
sibling package metadata **1.0.98**) and **1.0.79** (system package).
Codex reports **0.144.5**. None verifies the intended VM versions; the earlier
Copilot **1.0.83** observation was not reproduced. Exact executable paths,
help quotations and file/line references are in the
[direct audit](../../docs/ghcp-sol-actions-gate.md#installed-cli-contract-audit-2026-10-25-1215-kst).

The inspected **1.0.79** package schema supports the existing parser's turn,
tool, usage and context field paths. Runtime parsers were therefore left
unchanged. The schema does not establish **1.0.103 CLI stdout delivery**.
Usage/context/idle events are ephemeral, effort is optional, and neither
EOF nor idle/shutdown proves complete, promptly flushed delivery. A saved
session file alone cannot supply the missing ephemeral metadata. No newer
Codex SDK schema was substituted for the installed 0.144.5 CLI.

Added only a schema-shaped synthetic JSONL fixture and four variants in the
existing adapter test. Eight generated events validate against the packaged
Draft-07 schema, including format checks and internal references only. The
variants cover full settings, missing ephemeral events, absent optional effort,
and absent terminal markers. The latter still carries false completeness and
applied-settings flags. Fixture zero values and timestamps are synthetic, not
usage or performance reports. No tool-cap value, plan, runtime helper, workflow,
dependency, registration, pin, permission, score or consumed right changed.

### Current proof: keep the invocations separate

Evidence directory: `/ai-work/copilot/_tmp/ghcp-sol-cli-contract.9Qj6sx/`.

| Invocation | Result | Timing and exit |
| --- | --- | --- |
| Initial collection launcher | `/usr/bin/time` absent; pytest never started. | Exit **127**, retained `collection.log`. |
| Corrected collection, same three modules | **299 collected** | Pytest **0.39s**; wrapper **0.55s**; exit **0**. |
| Combined gate/VM/adapter bodies | **295 passed, 4 failed, 0 skipped** | Pytest **15.60s**; wrapper **15.77s**; exit **1**. |
| Only four failed new variants, after fixture fix | **4 passed, 0 failed, 0 skipped** | Pytest **0.30s**; wrapper **0.47s**; exit **0**. |

The combined JUnit contains **138 Actions + 93 VM + 64 existing adapter**
passes and **4 new fixture failures**. Auto/BYOK refusals are included in the
passing population. The new fake program read `sys.argv[4]` instead of the
supplied JSON argument at `sys.argv[3]` and exited before emitting events.
Only that index was corrected; no assertion or runtime code was weakened.
The four-case rerun is not a full final 299-test pass. The prior **295 passed
in 15.79s** is a separate historical proof, retained below and at
`6ceb602bf99e418f932bf7c2fd9d5594b1429e66:tasks/LATEST_TASK_RESULT/README.md`.

Commands ran in the worktree's `batch-runner` directory under Python 3.10.12,
**120s TERM + 5s KILL**, with a cleared environment, offline Hub flags,
bytecode/cache/plugin auto-loading disabled, and existing provider/network
traps. The adapter fixtures permit only the generated fake Python executable.
Exact collection/full-test argv is in `invocation.txt`; the only rerun was:

```bash
timeout --signal=TERM --kill-after=5s 120s env -i PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python -m pytest -q -ra --tb=short -o addopts= -p no:cacheprovider --junitxml=/ai-work/copilot/_tmp/ghcp-sol-cli-contract.9Qj6sx/junit-fixed.xml tests/test_ghcp_sol_execution_adapter.py::test_packaged_sdk_shape_is_not_cli_delivery_proof
```

Both body invocations used the starting HEAD plus uncommitted test/fixture
bytes, **not a clean tested commit**. Documentation was updated after proof.
The final local commit/HEAD/tree and clean status are recorded after commit
in `final-source.txt`; its executable/test bytes must match the fixed hashes.

| Source | SHA-256 |
| --- | --- |
| Test before the fake-argument correction | `c31204d5898712aa7decafbfad11ccda513ae3e56e55589402eda5532fb48b61` |
| Final `batch-runner/tests/test_ghcp_sol_execution_adapter.py` | `fd920cc4a51626855b1a35835164c68372b201129d213bf944fb7c03e2a50533` |
| New `batch-runner/tests/fixtures/ghcp_sol_packaged_sdk_events.jsonl` | `352aa198b0bf43c087f7fc64bc6f032e7839738e158c57c0b9e9a81884a8b323` |
| Unchanged `batch-runner/ghcp_sol_execution_adapter.py` | `e9b399dd5e222d5f3c6587f59937a608ea433db1d0bdfa5b1f52753f6a8436fb` |
| Unchanged `batch-runner/ghcp_sol_actions_gate.py` | `d757aafd7c18c32f6682b79ebd4f51bc901d58f2fa97c8c50030e1b4762ed698` |
| Inspected installed Copilot 1.0.79 event schema | `350df35914d4e2fdbadb8932ca66f1e58d759aad79b5be9291857c9052d31301` |

| Artifact in the evidence directory | SHA-256 |
| --- | --- |
| `invocation.txt` | `854c2bbc5a0b090f281070462896a89d26ab97130695738d82df841d6eec67aa` |
| `invocation-fixed.txt` | `0ebe38518bc992c3f107f1c6f7b8c79eccde5b55140c73ad92660b54c710b581` |
| `collection.log` (launcher failure) | `3e737f6a9117cec194b02103b357f8668fae9adb86a8a8cd0bf25efab8948548` |
| `collection-fixed.log` | `f79dd21c0dabd4d6117c196e9c5a212c794294f7f0a587c8b8ccf8a598b02f0f` |
| `collection-fixed-timing.txt` | `3402c7083fa08c10ff5c62156190ee8c2bde40678d2d824f50a46adb29a47a9f` |
| `test.log` (combined failure) | `e6eea5f40d218a8da36e2763640ab307dfb0518e56f3e6891937c866a37e8000` |
| `junit.xml` (combined failure) | `75154c856ee030f2db135bfffcab086bc64cf8459706edb13346b5919b0a3085` |
| `timing.txt` | `cda1c5f91b81049541e0d9a39b8e7355dbab44cf31bcad906088bfdb0d8a5c4e` |
| `test-fixed.log` (four cases only) | `f299cb0ffb4580215f4b9643a2f31cdf09e6c57c46f955b1d1c6a26a088f6fb3` |
| `junit-fixed.xml` (four cases only) | `688c0c5708034504beffefb02e373d8b4f0bd09ea875f65474c0a8f20712203d` |
| `timing-fixed.txt` | `5b4573c4e5671a2aa1054f846e6769754ef1f0736b6ebdeee81eaf79233479f5` |
| `schema-validation.log` | `8a81e78a96f053b1d9c6220ee59ff1d3a2590d1ac3375b758e82de461f753639` |
| `tested-files.sha256` (before fixture fix) | `0e6d63b22eed64be2f18562b908865aacd0af8b4bd082a3f999fdab93395cb19` |
| `tested-files-fixed.sha256` | `35c088c024ef8fefdc86e8d9bfe6e14b31ac45d0e5a036ab482462e2c46f598d` |
| `help-evidence.sha256` (help/version and failed-help hashes) | `dd4a23b4ce01e1eeed63e850559dd0e3b142edc397c9112f0b2acd01b7a82565` |
| `installed-source.sha256` (three binaries, schema and SDK declarations) | `13a1019ee6ba6317634f06bd84262639a3f1305e93041eec2b52194b9ad47e8f` |

### Help-only boundaries and remaining gate

The host `copilot` wrapper was inspected but never invoked because it can
resolve a token. Direct binaries ran only help/version commands under cleared
inherited environments, in the evidence directory, bounded to 20s + 2s.
User namespaces, Landlock and seccomp isolation were unavailable; the first
guarded launcher failed before CLI exec (`copilot-help.stderr`). Initial
direct calls did not disable automatic updates, so **background network
absence was not audited or proved**. Later help calls explicitly disabled
updates and client telemetry. No update/download, login, token, network-fetch,
model/session, schema-generator or server-start command was issued.
Three topic-help calls rejected `--config-dir` (exit 1); their exact errors
remain in `copilot-{logging,config,environment}-help.stderr`. Removing only
that unsupported argument let those help calls exit 0. It did not establish
a config/cache sandbox. No credential value, user cache or raw session was read.

The next free step is one installed-source binding of the intended VM
executable, GHCP-to-Codex bridge and stdout serializer. Complete/prompt event
delivery, applied model/Max/1M, approved tool cap, authentication isolation,
input/grader evidence and fixed-source review/CI still precede any separate
execution decision. The default-disabled adapter and dry-only workflow stay
disabled; no paid call, retry, score, cost, publication or completion authority
is inferred from this work. Local commit only; no push, dispatch or Project edit.

`openai-docs` was applied using installed-source evidence because network
lookup was prohibited. `experiment-report-en` keeps help, schemas, fixtures,
failed diagnostics and measured test populations separate; `im-not-ai-en`
preserves those limits in the English records. No experiment-design, UI or
animation work applies, and no specialist endorsement is claimed.

## Historical: GHCP Sol disabled process-adapter skeleton

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
