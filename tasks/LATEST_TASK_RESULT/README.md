# Latest task result

## Native pilot SDK startup deadline and combined offline proof (2026-10-25 KST)

The synchronous SDK initializer now shares the observer's existing
**1,800-second** deadline on a supported main-thread host. Offline fixtures
verified interruption, socket closure, SDK-child termination and a failed
receipt with unknown thread, turn and token usage. This is not a live pilot
result or a hard provider-token ceiling.

The unchanged starting source reported **126 passed, 1 failed, 0 skipped** in
one combined invocation. After the startup change and a directly coupled
socket-fixture correction, the combined bundle reported
**143 passed, 0 failed, 0 skipped**. These are separate invocations; the first
failure remains evidence. No paid call, push, dispatch or grading occurred.

### Source and implementation

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`. The supplied nested path was
absent. This existing registered path matched the requested branch and starting
HEAD and was clean; no worktree or branch was created or moved.

| Source role | Full HEAD | Tree |
| --- | --- | --- |
| Clean baseline and first combined test | `eb6bc6818249e3c7e12356df11e686218327c37d` | `2c60e96f13b9b5f130bcfc13011c86affcb96e2c` |
| Startup implementation and new-node collection | `e485dcdf889c961e8c520f121359342af6c01675` | `8afee76ba727ad4507457a27764a8655b131eddb` |
| Clean final code/tests and second combined test | `ab72943aaa33e97620d33b36a7ac33f4c5c454a0` | `f4f54873df89beaa476d4a9b5ef53531f96a1e7f` |

The final local child changes only this record and CHANGELOG. Its full HEAD/tree
and record hashes are returned in the handoff; executable bytes remain those
of the final tested code above. No independent review or CI covers this source.

The installed SDK **0.147.0**, `openai_codex/api.py:82`, starts its client and
waits for initialize metadata in the constructor. `client.py:337` waits on a
response queue without a timeout. Its constructor catches `Exception` and
closes the client; `client.py:274` waits **2 seconds** after TERM, then KILLs
without a final wait. The implementation uses this actual initializer, not a
copy of the SDK or a timed-out background constructor.

At `batch-runner/core/codex_runner.py:1098`, the caller holds the SDK instance
before invoking its initializer. `gpt56_pilot_wire_receipt.py:772` installs a
temporary `SIGALRM` for the same remaining monotonic deadline. Expiry keeps the
existing `native_attempt_deadline_exceeded` reason, closes the listener, and
raises `TimeoutError` through SDK cleanup. The partial constructor's actual
process is held before the SDK clears its reference, then killed if still live
and reaped with a **1-second cleanup-only wait** at line 811. The attempt
deadline is never renewed. A constructor returning at the deadline is refused.

An unsupported/non-main-thread caller or an active `ITIMER_REAL` is refused
before auth at `gpt56_pilot_wire_receipt.py:763`. The previous handler is
restored; another timer is not borrowed or cancelled. Existing auth/preparation
stages were not moved into this clock. Kernel-level uninterruptible startup and
detached-grandchild cleanup were not exercised, so this is not a universal
process-containment guarantee.

Only a closed, locally witnessed startup timeout with no native forward or
thread/turn traffic can produce the new
`codex_app_server_startup_deadline_before_thread` receipt scope. Correlation and
settings remain null, requests and usage snapshots remain empty, and usage is
`not_available`. `gpt56_pilot_wire_receipt.py:989` and
`gpt56_pilot_runtime_caps_usage.py:144` keep the ordinary post-initialize
correlation checks. No missing thread identifier is invented or entered into
the used-thread set. The Step 2 projection still excludes raw prompts, bodies,
headers, endpoints, private paths and exceptions. No retry reason was added.

### Two combined invocations, not pooled evidence

Evidence directory: `/ai-work/copilot/_tmp/p5-native-startup-deadline.ENTKcQ/`.
`invocation.txt` and `invocation-after.txt` hold the complete selectors and
commands. CWD was the worktree's `batch-runner/`; Python was
`/ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python`, **3.10.12**.
Both used `timeout --signal=TERM --kill-after=5s 120s`, `env -i`, offline
Hub/dataset flags, disabled plugin autoload/bytecode/pytest cache, and bounded
existing local-Git fixtures. No HOME or CODEX_HOME override was declared.

| Invocation | Result | Pytest elapsed | Wrapper wall | Exit |
| --- | --- | ---: | ---: | ---: |
| Baseline collection at `eb6bc6818` | 127 collected | 2.24s | 2.644s | 0 |
| Step 1, one combined body invocation | 126 passed, 1 failed, 0 skipped | 15.26s | 15.808s | 1 |
| Expanded collection at `e485dcdf8` | 143 collected | 2.20s | 2.599s | 0 |
| Step 4, one combined body invocation at `ab72943aa` | 143 passed, 0 failed, 0 skipped | 20.13s | 20.674s | 0 |

Both body invocations produced JUnit, with zero collection errors or warnings.
The only baseline failure was
`test_gpt56_pilot_provider_observation.py::test_one_cumulative_deadline_no_retry_or_turn_count_substitution`:
the watchdog closed the second request's socket before its error response,
raising `RemoteDisconnected`. The fixture now accepts that specific disconnect
while preserving exact timeouts **[60, 25]**, **2** forwards, null served model
and `deadline_exceeded`. No production transport assertion or deadline was
relaxed to repair the test.

The expanded bundle adds **16 cases**: eight startup paths and eight refusal
checks for incomplete/contradictory startup receipts. Real runner, receipt,
usage projection and installed SDK initialization/cleanup run against harmless
local Python children. The cases include successful initialize, no initialize
response, a child ignoring TERM, deadline-raced return, already-expired budget,
ordinary initializer failure, occupied alarm, non-main caller, canary exclusion
and traps on thread/turn creation, call reservation and provider transmission.
Real expiry fixtures use **0.5 seconds**; deterministic clock cases retain the
**1,800-second** boundary. No private input, auth, Rust CLI or live provider was
exercised. Host/source admission is synthetic in the process fixtures.

After collection, a source check added explicit partial-process ownership and
reaping, and changed the late-return fixture to wrap the real initializer.
No node, parameter set or fixture dependency changed, and no new import was
added. No test body
ran at the intermediate collection commit, and no passing body was replayed
beyond the two requested combined invocations.

| Evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| `invocation.txt` | 4089 | `921888469fa9d49e6d435f524d76de6ad092917e07ff1742bda0cb56bdd81a43` |
| `invocation-after.txt` | 4433 | `df74cd734cc6d164062994ecdd6f593e2adc0c128d0e5bb4cf8432cc710a6900` |
| `collection-before.log` | 15345 | `bfafde0f0284e13c02f4734a70618657757d13b6b29e546ec2f0f7c7a0baa84a` |
| `collection-after.log` | 17192 | `056d686a40406d6df35a44d3bc8a55c136d62687c7e11ae19b88be3ccba51a10` |
| `test-before.log` | 1185 | `81db7fac87f6527f48520414cce6520443f7b050a3e1dd9ed9032ee7e74d69f0` |
| `junit-before.xml` | 21396 | `5be99dd80c1980c6b1b4160eabe98b5b6aec1e0580079040727f78f0897b5351` |
| `timing-before.txt` | 20 | `0eaf9df851803e301ae083f77569031927a459c77a331781e389d8a993329692` |
| `test-after.log` | 181 | `5ddd87ca82dbb89067f8d82c57c387e747e65de5aa097d7bee49f6ddae419f84` |
| `junit-after.xml` | 23137 | `4fad34f92f4a12c40609243de6d7fb2f70e70fbaa606aa50979e1948e37cdb0b` |
| `timing-after.txt` | 20 | `a0e1b094f748c7122d0b6b23cdae1b2def2f321a04755389b32a96a0dddbd371` |
| `tested-code.patch` | 25904 | `2afb2c62ad70d22bb18cf3b97a8b3de906d9c050368fad32ab90c8bb531ec778` |

Final tested source hashes, unchanged by the record-only child:

| File under `batch-runner/` | SHA256 |
| --- | --- |
| `core/codex_runner.py` | `aadc19edd6691de97345fafb1ff941e262b67fe6b2a118e22c44c92ba731b509` |
| `gpt56_pilot_wire_receipt.py` | `9bf7c94aacec0663d718e7462e138423b36e4b2d48471cd65801eda976f12007` |
| `gpt56_pilot_runtime_caps_usage.py` | `80b75cb847295c27eabc139c3b1172177b9c1ebff74f6bb208ef3d782e5db44f` |
| `tests/test_gpt56_pilot_provider_observation.py` | `b5cc7951c5122993780f3abbddb932a3ea8a134ca980059f8d620593704961a5` |
| `tests/test_gpt56_pilot_remaining_caps.py` | `bde0589e9348e010e9123c9175a62e4e189782fa990a7645f04836b1108d9c5f` |

The prior **114 passed / 11 failed**, unresolved-only **11 passed**, and separate
late-usage **2 passed** remain separate historical proofs in the
[immutable preceding record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/eb6bc6818249e3c7e12356df11e686218327c37d/tasks/LATEST_TASK_RESULT/README.md).
That record links the earlier 97-case and 81-case/socket proofs. None is pooled
with the two new invocations, and no old evidence file was overwritten.

### Input-token precheck: investigation only

Package metadata/spec lookup in the existing Python environment found no
installed `tiktoken`, `tokenizers` or `transformers`. No tokenizer, vocabulary
or model file was installed, downloaded or initialized. The SDK's
`generated/v2_all.py:8579` exposes reported cumulative/last token usage;
`TurnStartParams` at line 8638 has no input/output token reservation field.
The existing observer can stop after an overrun, not undo it.

| Candidate method | Availability and work required | Error/limit |
| --- | --- | --- |
| A model-matched local tokenizer, such as an approved `tiktoken` encoding | Not installed here. It would require verified Sol model/encoding and vocabulary bindings, plus counting every native request's actual inputs and framing. Moderate-to-high integration work. | Exact only for text under the same tokenizer; provider framing, hidden context and non-text inputs remain unverified. No numerical error bound was established for Sol. |
| Character or UTF-8-byte count divided by a heuristic ratio | Available with the standard library; a small estimator would be easy to write. Not implemented. | No finite error bound for this workload was established. Language, code, tool output and repeated context can invalidate the ratio. It cannot justify a hard 300,000-token ceiling. |

A prompt-only estimate also misses later agent/tool context and input repeated
across native requests. A future pre-request guard would need a validated
model-specific accounting contract at the actual payload boundary, including
the attempt's cumulative total. No estimator or token guard was added here.

### Preserved limits and remaining gates

The **7343-byte** caps draft remains SHA256
`7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6`, and the source
plan remains SHA256 `506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482`.
Historical draft-status text and null registration limits were not rewritten.
This task did not edit the shared Git helper, plans, registrations, workflow,
dependencies, grader or other worktrees. Existing Git identity was retained,
and no attribution trailers were added.

Native forward caps remain **32 per attempt / 128 per task / 640 per pilot**,
with no refunds or adoption. **300,000 input / 10,000 output tokens** remain
reported-overrun stops, not hard pre-request or provider-output ceilings;
`token_hard_limit_enforced=false`. Missing usage stays unknown, cached/reasoning
subcounts are not added twice, and usage does not establish provider billing.
The fixed account, no-redirect transport, zero retries and all source/identity
checks remain. This change does not measure headroom under the 32-request cap.

Real CLI/provider behavior, served deployment/version, applied Max/Long settings,
hard token/spend limits, tariff/billing evidence, frozen-source/judge admission
and final-source review/CI remain open. This source is not declared launchable.
Task3 run `37756891578` remains uncertain, spent and nonretryable. No finite right
was consumed, restored or retried by this offline task.

`experiment-report-en` kept the two test populations, timings and synthetic/live
limits separate; `im-not-ai-en` was used for technical English. `openai-docs`
used installed SDK source as the offline fallback. No study redesign or UI
skill applied.
