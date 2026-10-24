# Latest task result

## Native provider observation, local implementation only (2026-10-24)

Implemented an attempt-owned loopback observer for the existing five-task
Foundry GPT-5.6 Sol pilot. It records native HTTP forward attempts and the
provider response body's allowlisted `model`, separately from logical SDK
turns. The initial offline selection passed **81 tests**. An additional socket
closure regression then exposed one failure; after a narrow correction, only
that node ran again and passed. These are separate source-bound results below,
not a pooled suite or live pilot. No launch approval is granted.

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`.
Base HEAD `f54b0ebcc1c2065d6a4cda30055878e6209793e6`, tree
`cfae8372dd1fc1eb8aaf9908493ad58b9ddb0546`.
Initial clean tested HEAD `ae4b37da23518a7b0d9b0af567a43c81806e75f3`, tree
`e89dc33b38fb6e8eb74d9c96af16845148a0191a`.
Corrected code/test HEAD `f017607fb1ae0dbd334c9a2b6ae4ffaa847b45a3`, tree
`04e6e9f8ab27af6cee5ab27f0097738072d682d4`; only this record and CHANGELOG were
pending during its one-node proof. The final local child commits those two
records only; its full identity is returned in the handoff. No independent
review or CI covers this change.

### Why this observation point

The installed `openai-codex` and CLI distributions are both `0.147.0`, under
`/ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/lib/python3.10/site-packages/`.
No software was installed and no external documentation was fetched.

- `openai_codex/client.py:241-267` passes configuration to a subprocess running
  `codex app-server --listen stdio://`. A Python HTTP hook would not observe
  the Rust process's provider traffic. The new SDK fixture checks those actual
  argument-building lines while trapping process creation.
- `openai_codex/_run.py:22-34,69-100` exposes items, status and usage, not the
  provider response envelope or headers. Thread/rollout model settings are
  not served identity; the synthetic rollout and quoted-output cases refuse.
- The bundled binary contains `SSE event:`, `codex.api_request`,
  `codex.sse_event` and `codex-api/src/sse/responses.rs` markers. These establish
  trace facilities, not a verified lossless response-model/count contract.
  Raw SSE logging can also contain private output. No old sessions or logs
  were read to infer either measurement.
- `core/codex_runtime_config.py:1066-1086` already supplies the provider URL,
  auth command and zero retry settings through CLI overrides. The observer
  changes only the URL in this process's copy, after the existing account and
  task binding checks. Original provider settings and the auth command remain
  unchanged. It forwards only the two fixed Responses/compaction POST routes
  to that same HTTPS account, without redirects, retries or credential lookup.

The receipt implementation is `batch-runner/gpt56_pilot_wire_receipt.py:97,173,476`.
`core/codex_runner.py:1077,1600,1969` installs/closes it and returns its closed
summary; `step2_run_inference.py:1339` preserves that allowlisted summary in
persisted task observability. The existing non-pilot path remains unchanged.

### What the values mean

`native_request_count` counts forward attempts, including transport failures
and remote compaction, within one owned attempt. It is not a count of confirmed
provider arrivals, successful responses, billable calls or logical turns.
Existing cost-ledger `model_calls` and unavailable native-count fields are not
relabelled. A synthetic 33-request case verifies counting without treating the
draft 32 as an enforced limit.

`served_model` comes only from an actual response JSON/SSE envelope and a closed
Sol-name syntax, never from requested deployment, rollout text or usage. An
absent, unsafe, malformed, incomplete, oversized or conflicting observation
retains `null` with a closed reason. Version remains `null`; no version is
inferred from a model suffix. Neither field attests the deployment or a bill.
Bodies and headers pass in memory; the report contains neither. Observation
buffers are limited to 256 KiB plus a 64 KiB read chunk; this is not an output
quota. The observer shares one deadline across requests, closes with the CLI,
and does not add a retry or a native-call enforcement claim.

### Exact offline evidence

Evidence directory: `/ai-work/copilot/_tmp/p5-native-provider-observer.LJj1da/`.
`invocation.txt` and `close-invocations.txt` contain the exact commands and
selectors. Python **3.10.12**;
`TERM120s/KILL5s`, empty task-local HOME, `env -i`, offline Hub/dataset flags,
disabled plugin autoload, bytecode and pytest cache. Tests use fake provider
bodies and actual loopback HTTP forwarding; all non-loopback socket connections
are trapped. The upstream TLS connection is replaced by local HTTP, and SDK
process creation is trapped. No Azure, model, credential or grading call ran.

The first collection wrapper exited **127** because `/usr/bin/time` is absent;
no pytest body started. Bash's existing timer then collected **81 tests in
2.02s**, outer **2.409s**, exit **0**. That body invocation covers the new
observer plus directly related wire/guard/legacy/Step 2/cap contracts, not an
old full suite or a model outcome.

| Source / scope | Actual pytest result | Outer wall / exit |
| --- | --- | --- |
| `ae4b37da23518a7b0d9b0af567a43c81806e75f3`, initial selection | 81 passed, 0 failed, 3.99s | 4.518s / 0 |
| Same production source plus the new hashed close regression | 1 failed, 2.21s | 2.594s / 1 |
| `f017607fb1ae0dbd334c9a2b6ae4ffaa847b45a3`, corrected close node only | 1 passed, 0 failed, 1.93s | 2.306s / 0 |

The added node, `test_close_interrupts_incomplete_local_headers`, collected
successfully before execution. It reproduced an accepted local socket left
open when its HTTP headers were incomplete. The correction tracks inbound
sockets from accept, closes them during shutdown, records failure metadata
before responding, and prevents late workers from upgrading a closed report.
The unchanged 81-node selection was not rerun. No warnings were reported;
the failure log, JUnit and original test hash are retained separately.

| Evidence file | SHA256 |
| --- | --- |
| `invocation.txt` | `b59e74bee183133dfe1735d27fd5430d2fd8623b50b18edd08d5fc27b5da14b1` |
| `test.log` (179 bytes) | `a52f4b35c1efdaf1a74f752372f29978fa6a90aab110bc4b0f1a230e431b4d2c` |
| `junit.xml` (13152 bytes) | `967940dbc6d8024b70ee83980c7ea3243310e7a18807c6bc0ce34a19ae4a3b7b` |
| `timing.txt` | `7c4da02fa373f330f776721bb23b1e2a326ceb30a651efeca2fb76c122b0dbc1` |
| `collection.log` (launcher failure) | `6933a7e0df95783acf93ed90af942334f7d1619d9a6a1f897c79ed256537f3c9` |
| `collection-corrected.log` | `8959a649bb84e194cc747d1e22135a02bf39db50f2869a0507a1800a4c182a4c` |
| `sdk-source-sha256.txt` | `bebd1cfa92d0ac486019d72f3c82f5a3e3caebaa2aef4bfc80091b4af8800f97` |
| `tested-code.patch` (42472 bytes, four code/test files) | `2c8c38274c5927a520e339c8b12cb2be891acd2fdbd9a64b4418d9acd6c34041` |
| `close-failed.log` | `4a115c760ff90276e15a1b2cfd139564dac8c08f5797b68c6d58582c3576ca4e` |
| `close-failed-junit.xml` | `986f98be948ce08646c9916d4f6bc886f318847158f3e4cf2a7f98ac5afae0b8` |
| `close-corrected.log` | `a4f4eee5c3cfd4d66ed0e5640986e5fdcdc04bcae931e493f824f1968c722867` |
| `close-corrected-junit.xml` | `8f4d3547c52a1c094c09a17d94719cc500930da6e5565573dce859c8d238cf78` |
| `close-invocations.txt` | `2938023dbc0ed72de73ea34446c05df43f7ee7452caf45b46dce87f0a7d5eb5e` |
| `close-fix.patch` (5764 bytes) | `63c01d75cdcfa3bc8f9e30c1189a56826355a87179c0c9a2a3d5bd80fda694be` |
| `final-code.patch` (44416 bytes, four code/test files) | `f01ceaec550887cd77e8586e1b42933504e238cf923caf29de2256aca2a953a5` |

### Preserved boundaries and remaining work

Sealed plans, caps, registrations, dependencies, workflow, grader and shared
Git helper were not edited. The helper remains SHA256
`77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`;
the draft cap file remains
`7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6`.
Headroom under **32 per attempt / 128 per task** remains unestablished. The
recorder does not approve those numbers, enforce native caps, change budgets
or reserve any execution right.

Real Rust CLI/provider streaming, Azure TLS, proxy overhead, served deployment
and version, billing, hard native enforcement, frozen-judge/source admission,
final-source review/CI and the existing live gates remain unverified or open.
No push, workflow dispatch, grading or live experiment occurred. Task3 run
`37756891578` remains uncertain, spent and nonretryable; no prior right is reset.
Earlier archive/count findings and separate 244/408-test proofs remain in the
[immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/f54b0ebcc1c2065d6a4cda30055878e6209793e6/tasks/LATEST_TASK_RESULT/README.md),
not pooled with this proof.

Reporting used `experiment-report-en` to preserve units and synthetic/live
limits, then `im-not-ai-en` for concise technical English. `openai-docs` used
local SDK/binary evidence because the owner restricted this task to local
work. No study redesign or UI skill applied.
