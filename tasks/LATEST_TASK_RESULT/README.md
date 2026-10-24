# Latest task result

## GHCP Sol gate: offline per-call capture and refusal

Scope: the leader's **2026-10-24 21:30** order on
`leader/ghcp-sol-gate-actions-20261024`, in
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`.
The starting worktree was clean at HEAD
`31679f60d98f4718e04c7dc173c1c6b84d37640b`, tree
`7fca89ce53d5c7eae446180ddf50b1cd8b1e69d6`.
Only the gate collector, its test module, the direct gate memo and these two
completion records changed. No plan, cap, workflow, pin, dependency, permission
or unrelated worktree changed. Delivery is a local commit only, not publication.

### Current result

The existing dry-run capture path now records each supplied
`assistant.usage` event's allowlisted model and effort, together with the
latest preceding same-agent `session.usage_info.tokenLimit`. Missing fields,
non-Sol models, non-Max effort, a context limit other than **1,000,000**, or
changes between calls produce fixed reasons, a failed receipt and exit **2**.
An explicit empty stream fails; the unchanged no-stream rehearsal remains
`not_collected`. Auto, BYOK and custom or unverified provider/model configuration
refuse before catalogue/event reads or capture writes. Provider environment
values and registry contents are never read; tests use a synthetic home.

**Paid execution remains blocked.** Even consistent metadata remains
**settings only**, not proof of the actual response model, applied Max or a
granted 1M window. Context values are labelled session snapshots, not per-call
attestations; missing sub-agent context is not borrowed from its parent.
This includes a sub-agent origin reported by `initiator` or the deprecated
`parentToolCallId` without `agentId`: its context and identity remain unverified.
`modelContextWindow` stays null because its separate Codex schema has no bound
GHCP event source here. Observed usage-event counts are not native-request
counts or a complete-call receipt. Raw conversation, error, header, ID and
credential values are excluded. Actual served fields remain unavailable;
usage, cost and grade remain null. Paid/retry authority remains false.

The [capture contract](../../docs/ghcp-sol-actions-gate.md#offline-per-call-capture-2026-10-24-2130)
describes the explicit offline JSONL input, safe projection, parser limits and
the remaining live-adapter gap. No GHCP client or paid execution path was added.

### Verification and source identity

With the existing Python **3.10.12** / pytest **9.1.1** environment, initial collection
passed (**204 nodes, 0.26s**). One bounded invocation then reported
**204 passed, 0 failed in 9.89s**; wrapper wall time **10.084s**, exit **0**.
This comprises **111 Actions capture tests** (**67 new**, **44 existing**) and
**93 unchanged VM gate-contract tests**. Synthetic cases cover normal Sol,
mixed/Fast models, missing/malformed fields, context drift and missing
sub-agent context, Auto/BYOK, duplicate/malformed/oversized streams and canary
non-egress, with network/process traps on the new capture tests. Existing
shell-guard tests execute only their local bash guards. No full suite ran.

The initial tests ran on the starting HEAD plus a two-file uncommitted code/test
patch, **not on a clean new HEAD**. That initial code patch is **32651 bytes**,
SHA-256 `a427cab2939b9a416ca18224b1d10c5f5d5ebf76cbcb876193ce9323926cb555`.
It remains unchanged in `tested-code.patch`; its two files are also retained as
`gate.before-subagent.py` and `test.before-subagent.py`.

Source review then found that an explicit sub-agent origin without `agentId`
could select the main-agent context. The narrow correction now refuses that
case. Its separate collection passed (**7 nodes, 0.18s**); the follow-up reports
**7 passed, 0 failed in 0.23s**, wrapper **0.390s**, exit **0**. It includes two
new origin fixtures and five directly coupled context fixtures. The original
204-case bundle was not replayed. This is not a pooled full-suite pass on the
final code. No test assertion failed in either invocation.

The follow-up used the same base plus `final-code.patch`, **33574 bytes**,
SHA-256 `1f749b6e062b3d88500c45c4c9fad0f949f578fa7e3fef3c6ed875806819479c`.
The final executable/test identities, unchanged by the record edits, are:

| File | SHA-256 |
| --- | --- |
| `batch-runner/ghcp_sol_actions_gate.py` | `26a19c3f5be5b03420101bf87c0e7c3d7b916b78671ebf03d7bea043471d964f` |
| `batch-runner/tests/test_ghcp_sol_actions_gate.py` | `98ce9b549a03a82dc9e5baf5c835e103294e58a0416ff40e93ac5f5fa7cedc55` |

From the worktree's `batch-runner` directory, the exact initial test invocation was:

```bash
timeout --signal=TERM --kill-after=5s 120s env -i PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python -m pytest -q -ra --tb=short -o addopts= -p no:cacheprovider --junitxml=/ai-work/copilot/_tmp/ghcp-sol-event-capture.4SVuxo/junit.xml tests/test_ghcp_sol_actions_gate.py tests/test_ghcp_vm_gate_contract.py
```

The follow-up retained the same interpreter, environment, flags and **120s
TERM + 5s KILL** bound. It used `subagent-junit.xml` and only these selectors:

```text
tests/test_ghcp_sol_actions_gate.py::test_subagent_without_agent_id_cannot_borrow_main_context
tests/test_ghcp_sol_actions_gate.py::test_context_is_not_backfilled_or_borrowed
tests/test_ghcp_sol_actions_gate.py::test_session_events_capture_documented_fields_without_promoting_evidence
```

Its complete command is retained in `subagent-invocation.txt`.

Evidence directory: `/ai-work/copilot/_tmp/ghcp-sol-event-capture.4SVuxo/`.

| Artifact | SHA-256 |
| --- | --- |
| `invocation.txt` | `c2766f9ce97a22a7c78c2e899f0840da3f019170864e6275a3b2eedc6b76c048` |
| `collection.log` | `bab634bd27034d75fec3586a5bd4a08ca0654dfefeb235682ef0da584327726d` |
| `test.log` | `65d9a00c00731fb7b27443970e74a1eb7f4bac6719ab8f9820d2059dcdfce079` |
| `junit.xml` | `2deb9b984634ab9789f99b23b7eca02b89c0e046f90c67ad2ca475a4ae76cbe7` |
| `timing.txt` | `a086a46347a4959175b7d707f069b23cc8fc3acdc084f78acff6472ff0c43433` |
| `subagent-invocation.txt` | `6d14466bf047ea6e073ea4d601565bc789d45fb74dfbdf8a290bb28c6ddd9c25` |
| `subagent-collection.log` | `dc63ca45bc13e6620f922935ee5ef5c6a4952bc33c6ad3b55344e5bba1703bdc` |
| `subagent-test.log` | `bf57a87e7fe91a0d8a8815a680d416938ba682dee7e8a176a4973cb35e527edc` |
| `subagent-junit.xml` | `ccaa7fafe577e9678f0ccb9c0b4fdc139cea833dac9658b7d1efcbac95b6f549` |
| `subagent-timing.txt` | `2ff49f7dbed044238d7baa38700b162f009ce5952bde1e6838b32cda6ec7acd2` |

### Field provenance and remaining limits

**Actual GHCP output was not inspected.** Fixtures follow the already cached
official [streaming-event reference](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/streaming-events#assistantusage)
and [usage reference](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing#per-call-token-counts).
The local snapshots are under
`/ai-work/copilot/_tmp/ghcp-sol-evidence-audit.Rqg0rU/`:

- `github-streaming-events.md:376-402,565-573` documents model/optional effort
  and session-level token limits; SHA-256
  `91feefbc0a9a1809aeeb6adfa6ffd4300c9690850ff02a4333f61f53348d208b`.
- `github-usage-and-billing.md:49-61,174-179` documents per-call/sub-agent usage,
  ephemeral delivery and changing context snapshots; SHA-256
  `80256955f997816416fb9e760b84bea704ad905d3bb66e3c2d30f2868000ec7b`.
- `github-cli-reference.md:699,781,886-893` documents Auto, model selection
  and provider-registry/configuration paths; SHA-256
  `52dfb285981b394fc6b7b636ad84403b5cce878a3c34df51d094e2cb4ebe94bc`.

These mutable public documents do not establish the installed runtime's output
or this account's entitlement. The prior audit and authentication drafts remain
in the [memo](../../docs/ghcp-sol-actions-gate.md#evidence-and-authentication-audit-2026-10-24)
and local `31679f60d98f4718e04c7dc173c1c6b84d37640b:tasks/LATEST_TASK_RESULT/README.md`.
Historical **313 targeted checks**, **5/5 capture rehearsals**, full core
**13,373 passed / 3 failed**, and their baseline reproduction remain separate
there; they were not rerun or pooled into this proof. No fully green CI gate
is claimed, and this task does not fix those unrelated baseline failures.

A reviewed GHCP-to-Codex adapter, complete pre-call subscription (including
sub-agents), applied-settings evidence, credential isolation/revocation,
enforced paid timeout/tool/turn limits, private-input policy, usage accounting,
grader validation and final fixed-source review remain unresolved. No universal
server-side fallback prevention is established; detection cannot undo spend.
Prior source review is not approval of this new local commit. Push, hosted
dispatch, paid inference and grading still require the owner's separate gates.

`experiment-report-en` preserves settings-versus-proof and separate test
populations; `im-not-ai-en` guides the English records. OpenAI Docs is applied
with the offline fallback to existing local references; no fresh document
fetch occurred. No study redesign or UI skill applies. No Azure/model/GHCP
call, authentication, credential/private-input read, workflow dispatch,
grading, push or Project change was performed.
