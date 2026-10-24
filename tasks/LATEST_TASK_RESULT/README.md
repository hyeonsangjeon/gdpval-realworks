# Latest task result

## Native pilot caps self-review and pending-start receipts (2026-10-25 KST)

Self-review found one defect in two early-return paths: a local deadline stop
while awaiting `thread/start` or `turn/start` was returned as a generic start
failure. The wire receipt then required the missing acknowledgement, and the
turn path could abandon its logical-call reservation despite a native forward.
The correction preserves the fixed stop reason, the unknown reservation and a
closed partial receipt. No missing identifier, terminal acknowledgement or
token usage is invented.

The new reproducer reported **0 passed, 2 failed, 0 skipped** against unchanged
runtime code. After correction, one combined invocation reported
**165 passed, 0 failed, 0 skipped**. This is offline fixture evidence, not a live
pilot result or a hard provider-token ceiling. No paid call, push, dispatch or
grading occurred.

### Source and implementation

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`. The supplied nested path was
absent. This existing registered path matched the requested branch and starting
HEAD and was clean. No worktree was created, moved or switched.

| Source role | Full HEAD | Tree |
| --- | --- | --- |
| Branch point and specified PR #785 head | `2bc77ad14cf7205694d11aa5909a9ea67cbb2891` | `753c55c66111dfc763385190766a75e0128dbf7a` |
| Clean fixed head reviewed; runtime used by new reproducer | `59eb1d4e8e561d53b041f12506812a616112c5cc` | `15834afa26c16e3ab88b5fe53d77c3287c5c569f` |
| Clean corrected code and one combined body invocation | `b436ba731ce7b25cf05b87c3776e2b467cb9e51c` | `7c468bb1893ef7592cfbcbce6894e54fa8720b8f` |

The final local child changes only this record and CHANGELOG. Its full HEAD/tree
and record hashes are returned in the handoff; executable bytes remain those
of the final tested code above. No independent review or CI covers this source.

The full caps branch diff, `2bc77ad14..59eb1d4e8`, was self-reviewed. The
following conclusions are bounded static/synthetic findings, not independent
approval or proof that every possible runtime failure has a terminal receipt.

| Review area | Finding and code under `batch-runner/` |
| --- | --- |
| Counter admission and exceptions | `_ProviderHTTPObservation.forward` reserves under locks before constructing the upstream connection. Failed forwards are not refunded; denied and unsupported requests do not create an upstream request. No additional bypass was found. |
| Task/pilot lifetime and retries | `_NativeRequestBudget` is owned by one non-adoptable wire session; Step 2 passes that same session through attempts. `arm_task` keeps the existing four-attempt and acceptance checks. Closed summaries retain a snapshot, not a changing shared total. No unintended reset or sharing was found. |
| Off-by-one | Forward **32/128/640** is eligible; the next reservation is refused. Token overrun uses `>`; deadline expiry uses `<= 0`. These thresholds and their existing fixtures remain unchanged. |
| Early stop and receipts | `core/codex_runner.py:1722` preserves a witnessed stop before a start acknowledgement and closes the observer/runtime before collecting partial files. Its two callers bypass the legacy abandonment path. |
| Partial-record guards | `gpt56_pilot_wire_receipt.py:880` admits only the two actually flushed pending-start shapes after a local stop and returned SDK close. Success, extra/mismatched responses, missing close, usage or fabricated completion are refused. `gpt56_pilot_runtime_caps_usage.py:151` uses the same check. |

The new scope is `codex_app_server_local_stop_before_turn_ack`. A missing
thread or turn ID and terminal status remain null; usage remains
`not_available`. Ordinary wire guards and the separate witnessed startup
timeout scope remain. Pre-admission failures, invalid observations and storage
failures still refuse rather than manufacture a complete receipt. Raw prompts,
bodies, headers, endpoints, private paths and exception text are excluded from
the Step 2 projection. No retry category was added.

The prior SDK **0.147.0** startup guard still uses the same **1,800-second**
deadline, main-thread `SIGALRM`, refusal of an occupied alarm, SDK **2-second**
TERM grace and **1-second cleanup-only** reap. Auth/preparation is not covered
by that observer clock. Kernel-uninterruptible startup and detached-grandchild
cleanup remain unproved; a returned SDK close is not provider-side cleanup
attestation.

### PR #785 relationship

The local branch creation record and merge base both identify `2bc77ad14`.
The temporary branch `review/native-caps-pr785-20261025-0305` pointed to fixed
`59eb1d4e8`. Its ancestor check and three-tree merge confirmed the caps source
is already on the specified PR head, with no conflict files. The temporary
branch was deleted after verification; neither real branch was rebased or
switched. The installed Git lacks `merge-tree --write-tree`; that failed
command form was replaced with its supported three-tree form. This checks
only the specified local PR head, not a future remote head or CI result.

### New reproducer and one combined invocation

Evidence directory: `/ai-work/copilot/_tmp/p5-native-caps-self-review.ghcBdT/`.
`invocation-reproducer.txt` and `invocation-combined.txt` hold the exact
commands, selectors and source identities. CWD was the worktree's
`batch-runner/`; Python was
`/ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python`, **3.10.12**.
Both body commands used `timeout --signal=TERM --kill-after=5s 120s`, `env -i`,
offline Hub/dataset flags, disabled plugin autoload/bytecode/pytest cache,
`-q -ra --tb=short -o addopts= -p no:cacheprovider -m 'not integration'`, and
JUnit. Existing local-Git fixture bounds remain. No HOME or CODEX_HOME override
was declared.

| Invocation | Result | Pytest elapsed | Wrapper wall | Exit |
| --- | --- | ---: | ---: | ---: |
| New pending-start reproducer, runtime at `59eb1d4e8` plus the new test patch | 0 passed, 2 failed, 0 skipped | 3.82s | 4.549s | 1 |
| One combined body invocation at `b436ba731` | 165 passed, 0 failed, 0 skipped | 24.53s | 25.288s | 0 |

Collection first reported **2 nodes in 2.50s**, then **165 nodes in 2.72s**;
both exited **0**. The combined collection preceded the code commit without
any intervening code change. Both body invocations produced JUnit, with no
collection errors or warnings. The first source-hash command used root-relative
paths from `batch-runner/` and exited before collection; corrected source
evidence has the `-actual` suffix. No failed proof was overwritten.

The two original failures retain their tracebacks: `session_start_failed` and
`turn_start_failed` were returned instead of
`native_attempt_deadline_exceeded`. The final bundle is the existing **143**
cases plus **22** new cases: two real pipe/loopback/SDK-close pending-start
fixtures and twenty rejection cases. The positive turn fixture observes one
synthetic forward before a withheld acknowledgement and verifies that no
reservation is abandoned or settlement fabricated. Both positive cases verify
closed sockets/child, null unobserved fields, exact shared counts, receipt and
Step 2 projection, nonretryable classification and canary exclusion. The
negative cases cover missing stop/closure/installation, extra requests,
mismatched responses, usage, fabricated completion/turn IDs and false success.
No real Rust CLI, provider, credentials or private inputs were exercised;
host/source admission remains synthetic in the process fixtures.

| Evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| `reproducer.log` | 1410 | `88594b77cc9d63a45a0c24aaabdf32589d54b1fe7371b284b73f1bcf9a8ac8af` |
| `reproducer-junit.xml` | 1668 | `0b7899cbcea89b7a474830a0f787219686f99c1c4d1f090c88eece2ddc0f20ad` |
| `combined.log` | 261 | `7bba10800937e49274d0412dcd37929e8fce258ac365ad9b4088c58537786e7c` |
| `combined-junit.xml` | 26979 | `d02d76e9aa19bb9ee153fd0f64f0d07aa843aacb94478f721177246f8be8a272` |
| `tested-code.patch` | 17082 | `a6206cca254e89533535b3b7def9149c535b35f5cf836bcfc3540ab797fe8c33` |

The reproducer/combined command SHA256 values are
`cca3571861fcc3cf99b072a3cc79e8c160057eef831c31c69307c1639bec6411` /
`ea6c5d57b578cee29aaa77344b4f262f2d1a40c8e2c5de2ed7cc8e862118307d`;
collection values are
`f9700f789791d4029887aa952a2827441825485debe17844747da0438e980f3a` /
`b7ec2c4dd6f1d38db1e8dd30cb8113f723a6401b9949355c8aaea2853497885f`;
timing values are
`c7313d4d292cac3b11cb8fb4dd6ab5ba3f33963b8aab70f8bf0f9e53641f7856` /
`33ef88ecd14ebf6145147fa9760b35982b0dc4808b11cb2cae08b5bb2b2af50e`.
`branch-relation-final.log` is SHA256
`82a78974fbe0b30735dd9e49fa2154ede849b828a405e6e695a97cb517b68866`.

Final tested source hashes, unchanged by the record-only child:

| File under `batch-runner/` | SHA256 |
| --- | --- |
| `core/codex_runner.py` | `d8de2b16319a433c42935327989210f58673f6f5afc3a2c531f0ac8bceadd80b` |
| `gpt56_pilot_wire_receipt.py` | `3863983ea5d2a29703b0e5d978f61f3556d54685de55905dabc30135d850d306` |
| `gpt56_pilot_runtime_caps_usage.py` | `ca6e40698f51670bf485895f8bc23d728d03a4d834affd3da846cb21bd159fbe` |
| `tests/test_gpt56_pilot_provider_observation.py` | `b5cc7951c5122993780f3abbddb932a3ea8a134ca980059f8d620593704961a5` |
| `tests/test_gpt56_pilot_remaining_caps.py` | `9aaeecf67558e40b426db0fcd35df8576e71a81222b3076f54f583ebe9bc69fc` |

The prior **126 passed / 1 failed** and later **143 passed / 0 failed** remain
separate historical proofs in the
[immutable preceding record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/59eb1d4e8e561d53b041f12506812a616112c5cc/tasks/LATEST_TASK_RESULT/README.md).
That record preserves the socket-disconnect failure and links the earlier
114/11, unresolved-only 11, late-usage 2, 97-case and 81-case/socket proofs.
None is pooled with the new reproducer or combined invocation, and no old
evidence file was overwritten.

### Input-token precheck: investigation only

The preceding package metadata/spec lookup in the existing Python environment
found no installed `tiktoken`, `tokenizers` or `transformers`. No installed
`tiktoken` version or verified Sol-to-encoding binding was available. No
tokenizer, vocabulary or model file was installed, downloaded or initialized. The SDK's
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

`experiment-report-en` kept the failed reproducer, combined proof, historical
populations and synthetic/live limits separate; `im-not-ai-en` was used for
technical English. `openai-docs` used installed SDK source as the offline
fallback. No study redesign or UI skill applied.
