# Latest task result

## Native pilot remaining caps: local guards, incomplete hard-limit coverage (2026-10-24)

The pilot now shares native-request counters across attempts and tasks, stops
on reported token overruns with a fixed reason, and closes its listener and
bound SDK process on the attempt deadline. These changes do **not** establish
hard provider-token ceilings or a timeout covering synchronous SDK startup.
No paid experiment, push, workflow dispatch or grading occurred.

The first offline invocation reported **114 passed, 11 failed**. After two
demonstrated corrections, only those **11 failed cases** ran again and passed.
A separate late-usage correction then passed **2 new cases**. These are
separate results, not a full passing suite at the final source.

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`.
The nested path supplied in the direction did not exist; the existing registered
worktree matched the requested branch and full starting HEAD and was clean.
Base HEAD `3dea2d6d2ba9b6bb92596e691e3ad53a78fa82a4`, tree
`0b06bb0e62173c8bc304ee8c53d3787f9e910fab`.
Initial clean tested HEAD `eaeef4861a3d9ebad805c2ba5c8443f02a4324d4`, tree
`5a479cf5765ff1a648fa2523cfb41c4b09aebfed`.
Corrected clean tested HEAD `c3012107e170dd7b0ba076733568078634b810d3`, tree
`8b0e491bfc6c61c4a5130763251610a2e47c1a97`.
Final code/test HEAD `0a53ee81c27ec79bdef72ffbdbd2f9c4e7f51b4c`, tree
`a0e7a6b4cef37fc3a0708199dc726d56bbc51869`. Only these two completion records
were dirty during the last proof; code and tests matched that commit exactly.
The final local child commits only this record and CHANGELOG; its full identity
is returned in the handoff. No independent review or CI covers this new source.

### Audit and implementation

All limits come from the unchanged **7343-byte** caps draft, SHA256
`7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6`, read by
`batch-runner/gpt56_pilot_wire_receipt.py:94`. Its historical draft-status text
and the registration's null native limits are unchanged. This is prospective
local enforcement work, not plan approval, measured headroom or spend authority.

| Draft item | Before this change | Current behavior and source |
| --- | --- | --- |
| 300,000 input tokens per attempt | Reported-threshold check only; generic refusal in `gpt56_pilot_runtime_caps_usage.py:127` at the base | Preserve the over-limit sample and stop the bound SDK; `gpt56_pilot_wire_receipt.py:480`, `gpt56_pilot_runtime_caps_usage.py:135`. Not a hard pre-request token cap. |
| 10,000 output tokens per attempt | Same reported-threshold check | Same controlled stop; cached/reasoning subcounts are not added again. Not a hard provider-output cap. |
| 1,800 seconds per attempt | Existing turn wait and HTTP deadline; no active listener/SDK watchdog during idle intervals | Clamp the observer timeout to the draft, share its remaining deadline with the turn wait, and stop the bound process; `gpt56_pilot_wire_receipt.py:446`, `core/codex_runner.py:2031`. SDK startup remains outside the confirmed cleanup coverage. |
| 128 native requests per task | No explicit shared counter; implied by 32 per attempt and four allowed attempts | Reserve under one run-owned lock before upstream connection, across fresh attempts, including failures; `gpt56_pilot_wire_receipt.py:108`. |
| 640 native requests per pilot | No explicit shared counter; implied by 32 × four attempts × five tasks | The same owner counts all five tasks. It blocks another forward at the ceiling and checks availability before another task is armed; `gpt56_pilot_wire_receipt.py:1089`. |

The existing **32-request** attempt cap, reviewed-evidence/source checks, fixed
HTTPS account, no redirects and zero transport retries remain. The actual
observer must belong to the run's shared budget before auth at
`core/codex_runner.py:1067`. No counter is restored from a receipt or refunded
after a failed connection. The existing no-adoption reservation still applies.

The closed `provider_observation.runtime_caps` projection records the draft
digest, limits, reported input/output tokens, task/pilot forward counts, effective
deadline and stop reason. Unobserved token counts remain null. It explicitly
sets `token_hard_limit_enforced=false`. New fixed reasons are
`native_input_token_cap_exceeded`, `native_output_token_cap_exceeded`,
`native_attempt_deadline_exceeded`, `native_task_request_cap_exceeded`,
`native_pilot_request_cap_exceeded` and `native_token_usage_unverified`.
They are not added to the infrastructure retry allowlist. A stopped attempt
cannot accept a raced SDK success; missing terminal acknowledgement stays null.
No raw response, prompt, header, endpoint or exception enters this projection.

### Exact offline proof

Evidence directory: `/ai-work/copilot/_tmp/p5-native-remaining-caps.rYMfbu/`.
`invocation.txt` and `invocation-late-usage.txt` contain the exact commands. Python
**3.10.12**, installed SDK **0.147.0**, `TERM120s/KILL5s`, `env -i`, an empty
task-local HOME, offline Hub/dataset flags, and disabled plugin autoload,
bytecode and pytest cache. No install, credential read or network provider call
was needed.

| Invocation | Source | Result | Pytest elapsed | Wrapper wall | Exit |
| --- | --- | --- | ---: | ---: | ---: |
| Initial collection | `eaeef4861` code, before its ordinary commit | 125 collected | 2.19s | 2.585s | 0 |
| Existing 97 plus 28 new cases | `eaeef4861a3d9ebad805c2ba5c8443f02a4324d4` | 114 passed, 11 failed | 15.52s | 16.096s | 1 |
| Unresolved collection | `c3012107e170dd7b0ba076733568078634b810d3` | 11 collected | 2.05s | 2.436s | 0 |
| Only the 11 failed cases | `c3012107e170dd7b0ba076733568078634b810d3` | 11 passed, 0 failed | 4.54s | 5.074s | 0 |
| Late-usage collection | `36d36ae6a2290717be7939dc49d2268b956488e0` | 2 collected | 2.05s | 2.440s | 0 |
| Only the new late-usage cases | `0a53ee81c27ec79bdef72ffbdbd2f9c4e7f51b4c` | 2 passed, 0 failed | 2.31s | 2.707s | 0 |

All three body invocations produced JUnit, with no warnings. Ten failures exposed
a missing stdlib `time` import. One exposed watchdog closure replacing the
existing `deadline_exceeded` reason with `response_capture_incomplete`. The
correction added the import and preserved that known deadline provenance;
no assertion or fixture was weakened. The other 114 cases were not replayed.

The final local source check found that a closed capture could ignore a late
over-limit notification. The follow-up restores the prior threshold refusal
under the capture lock, preserves the closed summary, and refuses non-scalar
stop metadata.
Only the two new input/output late-notification cases ran for that delta.
The scalar check/assertion changed after collection, without changing imports,
fixture dependencies or node identities. No earlier passing body ran again.

New fixtures cover token limits minus one/exactly/plus one, actual 128/640
synthetic HTTP forwards across attempts, refusal before the next upstream
connection, concurrent final-slot admission, no refunds after connection
failure, deadline clamping/idle expiry, partial receipts and secret-canary
exclusion. The real runner/usage/receipt code and installed SDK close method
operate on harmless local Python children. Provider bodies, turns, earlier
reservations in the process fixtures and host admission are synthetic. All
non-loopback socket destinations are trapped; upstream TLS is replaced by
local HTTP. No Rust CLI, private input, live auth or provider was exercised.

| Evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| `invocation.txt` | 7010 | `c1358c963937d1e8f2409a00862a14ef623bf8f61480f997dfa40b7306d07ee9` |
| `test-initial.log` | 8243 | `a8aa6d2d38b3dc87a99cf0fb6d06636f08feba0115dfe335b99c031abbe9d147` |
| `junit-initial.xml` | 26424 | `2d8a993114c238cacd014778b1017f901168b550cac4174d90ac8c80dcf4faca` |
| `timing-initial.txt` | 20 | `bfafcae468edd83c5eebc1f37fa6a999ce7141ced485976a14758cd660756c3c` |
| `test-unresolved.log` | 99 | `8aba684c8171815f9d71dbb90169dcf2ca07df9dd12982829c70e8602a57f1b6` |
| `junit-unresolved.xml` | 2241 | `700d2b66bcb509a84093cf73e8655f9946fa6dc437ae6c586c6f7420f48d5ae1` |
| `timing-unresolved.txt` | 19 | `0e3a5f1f23b711e00c5ede525633a88a45f3cea4c74c8fde823d6cb11f0741c8` |
| `tested-initial-code.patch` | 49788 | `1bd1ee416e22d2a155e286bcca1bbaa4cb08db922ec3f93f3a1cb608f13ca9e8` |
| `tested-code.patch` | 50502 | `78ae40c7905745aef60b661a919b9c10d26e117e6707b6530f764876a9e85ec6` |
| `invocation-late-usage.txt` | 2625 | `22c65860f43793c4501c63db9d99efca2d86fe8bbde0b98c7a7987e9ae97fb15` |
| `test-late-usage.log` | 98 | `65f313c081c0ef8ae25769e77cc41a6bb81f8365a1ced50c4c01aa68948c851c` |
| `junit-late-usage.xml` | 563 | `bcfa7d947f7607c6dbe482a510dc3ca1cf40c6d3647297390191ad856f647e28` |
| `timing-late-usage.txt` | 19 | `1c6f8d678fb00a875ae83eea1f2af00b07dd647a2cd01370cc6b785a3c60c4eb` |
| `tested-final-code.patch` | 52028 | `fbc4b99eb1262d894d9511f49356a0843a075947e022f48707f1927346a373e7` |

Final source SHA256 values, unchanged by the final record-only commit:

| File under `batch-runner/` | SHA256 |
| --- | --- |
| `gpt56_pilot_wire_receipt.py` | `06bad62111e9492e5bedf46ad3950193605d3d75f88c907fbad539e740c23741` |
| `gpt56_pilot_runtime_caps_usage.py` | `38b74969671ed2f8ab68313ad82f512e65dfe19c87d2971e6049f67620752f98` |
| `core/codex_runner.py` | `7973fbc93ec6b7ee8e8fd97467c86d2d4694b05c2735eed56011d705e41ea94c` |
| `tests/test_gpt56_pilot_remaining_caps.py` | `e65a597ed8ea35e0bdad84417f31ba9b106db578eb98a0e4141aa158e95ac6f6` |

The earlier **97 passed in 6.44s**, outer **7.000s**, and the separate 81-case
observation/socket-failure/corrected proofs remain in the
[immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/3dea2d6d2ba9b6bb92596e691e3ad53a78fa82a4/tasks/LATEST_TASK_RESULT/README.md).
They are not pooled with these invocations.

### Preserved boundaries and remaining gates

The source plan remains SHA256
`506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482`;
the shared Git helper remains
`77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`.
Plans, cap values, registrations, dependencies, workflow, grader and other
worktrees were not edited. Existing Git author/committer identity was retained
without attribution trailers.

Two limits cannot be called hard provider-token ceilings: input is reported
after processing, and output/reasoning usage is reported after generation.
The installed SDK **0.147.0** supplies cumulative/last notifications
(`openai_codex/generated/v2_all.py:8579`), not a token reservation mechanism.
Its `TurnStartParams` at line 8638 does not provide an input/output token cap.
This change neither estimates tokens from bytes nor adds an unverified request
field. It can stop further work when overage is observed, but cannot retract
that overage or prove its billing boundary. Missing usage stays unknown.

The active clock covers the recorder and already-bound SDK. In
`core/codex_runner.py:1091`, synchronous `Codex(config)` still initializes before
the runtime close callback is attached at `gpt56_pilot_wire_receipt.py:786`.
The installed SDK's `api.py:82` confirms that ordering. A constructor that
never returns is not covered by the proven SDK cleanup path; no full
startup-inclusive 1,800-second guarantee is claimed.

Measured headroom under **32 per attempt / 128 per task**, hard token/spend
limits, startup-inclusive cleanup, served deployment/version, Max/Long
application, live CLI/provider behavior, tariff/billing evidence, frozen-source
and judge admission, and final-source review/CI remain gates. This source is
not declared launchable. Task3 run `37756891578` remains uncertain, spent and
nonretryable; no prior right is reset.

Reporting used `experiment-report-en` to keep counts, timings and synthetic/live
limits distinct, followed by `im-not-ai-en` for technical English. `openai-docs`
used local SDK source because the task is local only. No study redesign or UI
skill applied.
