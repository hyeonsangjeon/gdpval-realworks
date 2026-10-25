# Latest task result

## GHCP Sol gate: installed harness and stdout contract

Scope: the leader's **2026-10-25 13:50 KST** order, local installed-source
investigation and synthetic verification only. Worktree
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`, branch
`leader/ghcp-sol-gate-actions-20261024`, started clean at
`8eb449d90a43fab68cd553ee73b95907a55a00e3`, tree
`b0efd84089fcea3ef835741ca7dfa31193dc609f`. No other checkout was changed.

### Result

**No Codex harness selector was found in the inspected installed interfaces,
and the auditable 1.0.79 CLI writer omits required per-call metadata.** The
adapter now parses that writer's separate result envelope without treating
it as settings or completion authority. The full gate bundle passes once;
the actual GHCP-to-Codex launch and applied Sol/Max/1M gate remain open.

| Question | Finding and boundary |
| --- | --- |
| Command | **Partial**: noninteractive model/effort/context-tier/JSONL options are confirmed. `--agent` selects a custom agent; no Codex selector is present in the inspected built-in registry/options. The account feature `codex_agent_enabled` is not a launch command. Opaque binary internals and other products are not ruled out. |
| Event schema | **Confirmed for installed 1.0.79 only**: start configuration, turn/call model labels, optional effort and session `tokenLimit` exist. There is no event `modelContextWindow`. None proves applied Max or numeric 1M. |
| Delivery | **Confirmed omissions; completeness unverified**: the JSONL writer filters usage, context, model-change, idle and shutdown events. A newline or final result does not prove prompt/complete delivery. Saved logs cannot restore ephemeral metadata. |
| Version | Prior executable observations were Desk **1.0.103**, system **1.0.79**; Desk metadata says **1.0.98**. The Desk bundle has no standalone schema. Exact cross-version differences remain unverified. Propose **1.0.79 as an offline reference only**; no pin changed. |

No Copilot/Codex executable, including help/version, ran this turn. The
[dated source audit](../../docs/ghcp-sol-actions-gate.md#installed-harness-and-stdout-audit-2026-10-25-1350-kst)
provides installed paths and line references. Key 1.0.79 sources are
`app.js:287` (built-ins), `app.js:5600` (options), `app.js:2744` (stdout filter),
`app.js:2745` (result writer), and `schemas/session-events.schema.json`
(field definitions). The described fallback causes are schema possibilities,
not observed runtime switches.

### Source-supported implementation

Changed `batch-runner/ghcp_sol_execution_adapter.py`, its test module and the
new `tests/fixtures/ghcp_sol_copilot_1079_stdout.jsonl`. The adapter separates
CLI-only results from session events, checks exact top-level keys and matching
observed session ID, and permits only an integer 0/1 exit code. Its safe
`cli_result` records observed/exit-code fields while keeping
`completion_authority=false` and `settings_authority=false`. Raw identities,
timestamps, usage, paths and errors are not projected. Nonzero summaries
refuse with `cli_result_failed`; invalid, duplicate or post-result frames
refuse with `session_event_stream_refused`. A zero result does not release
supervision: EOF/process exit or the unchanged deadline must still occur.

Fourteen new cases cover the filtered stream with/without a result, malformed
or failed summaries, private-canary non-egress and a hanging process after a
zero result. SDK-plus-summary combinations are **synthetic**, not observed CLI
output. Start labels Sol/Max/long_context do not repair the filtered stream's
missing call metadata; it still refuses. Usage/cost remain unavailable.
No command builder, collector, workflow, plan, cap, dependency, registration,
pin, identity, permission, score or consumed right changed.

### One current proof; prior results stay separate

Evidence directory: `/ai-work/copilot/_tmp/ghcp-sol-harness-schema.zoULYD/`.
Tests used clean HEAD `59c23a1446533cc988cf74840cd00eb1a23c3605`, tree
`49033ac832de59987d19d41817f3fc6d6f4567ad`. Documentation was updated afterward;
`final-source.txt` in that directory records the later local HEAD/tree and
clean status. Only documentation may differ from the tested commit.

| Invocation | Outcome | Pytest / wrapper time; exit |
| --- | --- | --- |
| Collection, three gate modules | **313 nodes** | **0.40s / 0.56s; 0** |
| One combined body invocation | **313 passed, 0 failed, 0 skipped** | **16.50s / 16.66s; 0** |

JUnit contains **138 Actions + 93 VM + 82 adapter** cases, including eight
Auto/BYOK-named refusals. No test failure, retry or warning was reported. A
separate static check validates the new fixture's **four session events**
against the exact installed Draft-07 schema with format checking and internal
references only. Its fifth, CLI-only result is outside the session schema.
Synthetic timestamps/zeros and fake-process cleanup are not runtime or cost
measurements, complete delivery proof or general containment guarantees.

The existing Python 3.10.12 environment ran in `batch-runner/`, under
**120s TERM + 5s KILL**, cleared environment/offline flags and existing network/
provider guards. Adapter subprocesses were generated fake executables only.
The exact collection and body commands are in `invocation.txt`; the body was:

```bash
timeout --signal=TERM --kill-after=5s 120s env -i PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python -m pytest -q -ra --tb=short -o addopts= -p no:cacheprovider --junitxml=/ai-work/copilot/_tmp/ghcp-sol-harness-schema.zoULYD/junit.xml tests/test_ghcp_sol_actions_gate.py tests/test_ghcp_vm_gate_contract.py tests/test_ghcp_sol_execution_adapter.py
```

| Tested source | SHA-256 |
| --- | --- |
| `batch-runner/ghcp_sol_execution_adapter.py` | `9a5fb7ee55be3a990d61ec565c56314d235847c8f0c8ef29ec3213255bc01558` |
| `batch-runner/tests/test_ghcp_sol_execution_adapter.py` | `4f4746c015d4f76eba338783abfe26a14793a4f075c28e4104147b7bd1311006` |
| New `ghcp_sol_copilot_1079_stdout.jsonl` | `5d28496a0d825c80f0165b192bcd70641ba9ed415450eba1b786647f88ba0459` |
| Unchanged collector `ghcp_sol_actions_gate.py` | `d757aafd7c18c32f6682b79ebd4f51bc901d58f2fa97c8c50030e1b4762ed698` |
| Inspected installed 1.0.79 event schema | `350df35914d4e2fdbadb8932ca66f1e58d759aad79b5be9291857c9052d31301` |

| Artifact | Bytes, where listed | SHA-256 |
| --- | --- | --- |
| `test.log` | 421 | `d58de7d756370bc651f4acbf51fef6302728efc51c33130bd4c6ef5dfb92ba8b` |
| `junit.xml` | 48745 | `533e6bc12092a2518dc115583b55620f2246b19247ea6bb16353acb610a6a2fa` |
| `tested-code.patch` | 12917 | `3fb98d42c8758e460df9fb93a910929c72772b3e973eea4b20b7b20d213d0f34` |
| `invocation.txt` | — | `d7d9ec7ab6140fcfc50b56a9582e2f04837f56c20a4931907e90a62223fac771` |
| `timing.txt` | — | `59a49055ea0b11ba106be7b2a35d81134b574a9437a5ecd877ff1be452e2511b` |
| `schema-validation.log` | — | `49a4e1e67fe2f5f8fdcdb0d4fd794296ad082bc7483e9715757f4aca2a32b3c4` |
| `proof.sha256` | — | `94d59e69f83bd17963003480ed1e498cc695e75afd4ca1e1bcc8011df2a9882d` |

`proof.sha256` also binds collection/timing, installed-source excerpts,
package manifests and unchanged-scope hashes. The previous **295 passed,
4 failed** and separate **4 passed** proof, original help diagnostics and
unverified background-network behavior remain in the
[immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/8eb449d90a43fab68cd553ee73b95907a55a00e3/tasks/LATEST_TASK_RESULT/README.md)
and its unchanged `/ai-work/copilot/_tmp/ghcp-sol-cli-contract.9Qj6sx/` evidence.
They are not pooled with, or relabeled by, this new 313-test invocation.

### Remaining gates and authority

The adapter remains disabled by default, and the workflow remains dry-only.
The actual VM/harness command binding, an unfiltered complete/prompt event
channel, served/applied model/Max/1M evidence, approved tool-call cap,
authentication isolation/disposal, input/grader bindings and fixed-HEAD
review/CI remain required before a separate execution decision. Event-based
cancellation is not pre-effect admission of turn/tool limits. Paid/retry and
completion authority remain false; no performance, cost or score is inferred.

Only local commits are authorized here. No real CLI, authentication/secret
read, raw session/private input, network/model call, dispatch, grading, push,
PR or Project edit occurred. A nonessential `file` diagnostic was unavailable
(exit 127); bounded `od` inspection identified ELF headers without installing
anything. This was not a failed test or a CLI invocation.

`openai-docs` was applied using installed source only because network lookup
was prohibited. `experiment-report-en` separates source findings, schema
descriptions, synthetic proof and live hypotheses; `im-not-ai-en` preserves
those limits and exact values. The evidence directory's `record-protection.md`
records the protection brief and reconciliation. No experiment-design, UI or
animation work applies; no specialist endorsement is claimed.
