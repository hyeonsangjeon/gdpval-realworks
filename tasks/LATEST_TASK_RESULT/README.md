# Latest task result

## Native pilot request cap, local implementation only (2026-10-24)

The attempt-owned loopback recorder now refuses the 33rd native HTTP request
before opening an upstream connection. The authorized offline selection passed
**97 tests, 0 failed**, with no warnings. This verifies local synthetic behavior,
not a live Foundry or five-task pilot result. No push or launch occurred.

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`.
The nested path supplied in the direction did not exist; the existing registered
worktree matched the requested branch and full starting HEAD and was clean.
Base HEAD `b43f7576e75e506f9e35c8c2cbe48a18b383dba1`, tree
`1378c920b973119f3ba1a29947057974a6c1643f`.
Clean tested code/test HEAD `582bc4a4b21b2a5c7882db2be2e478f14b4b438e`, tree
`622a38e5686355b7fbc16ecd83a632438e10cd35`.
The final local child commits only this record and CHANGELOG; its full identity
is returned in the handoff. No independent review or CI covers this new source.

### Enforcement and receipt meaning

- `batch-runner/gpt56_pilot_wire_receipt.py:74` reads the existing 7343-byte caps
  snapshot with exact SHA256
  `7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6`.
  The per-attempt value is **32**. The registered source plan still declares
  its native cap as `null`; the 32 is in the separate caps draft. This leader
  direction authorizes enforcing that unchanged snapshot, not changing either
  plan, approving spend, or claiming measured headroom. The runtime also refuses
  a mismatch with the held reviewed caps evidence when that owner is present.
- The recorder's admission lock reserves each allowed forward before connection
  creation. Requests beyond the limit do not reach upstream, including concurrent
  requests and remote compaction. The listener must install successfully; failure
  cannot restore the direct, uncapped URL. The existing deadline, HTTPS account,
  no-redirect policy, auth command and zero retries are unchanged.
- The denied request closes the recorder's inbound/upstream sockets and invokes
  the owned SDK process's close method. Closure is serialized with runner cleanup.
  `core/codex_runner.py:1884` returns a failure even if the SDK races the stop with
  a completed turn. The existing infrastructure retry allowlist does not include
  `native_request_cap_exceeded`.
- On the tested 33-request boundary, `provider_observation` contains
  `native_request_count=32`, `native_request_count_reason=null`,
  `native_request_limit=32`, `native_request_blocked_count=1`,
  `native_request_cap_reason=native_request_cap_exceeded`,
  `native_request_limit_sha256` equal to the snapshot hash, and
  `native_cap_enforced=true`. The true flag covers this per-attempt forward cap
  only, not tokens, total pilot spend, confirmed provider arrivals or billing.
  Counts still include failed upstream forward attempts, not logical SDK turns;
  the denied request is counted separately and is not a 33rd upstream attempt.
- The strict projection in the recorder and the existing Step 2 insertion at
  `step2_run_inference.py:1339` preserve these closed fields without raw messages.
  A cap stop may retain a missing SDK terminal acknowledgement as
  `transport.correlation.status=null`. The usage owner preserves available
  snapshots or an empty list, with
  `native_request_cap_exceeded_usage_may_be_partial`; it does not invent usage
  or a terminal response. Normal success/usage checks remain unchanged.

### Exact offline proof

Evidence directory: `/ai-work/copilot/_tmp/p5-native-cap-enforcement.pgzqQd/`.
`invocation.txt` contains the full collection and test commands. Python
**3.10.12**, installed SDK **0.147.0**, `TERM120s/KILL5s`, `env -i`, an empty
task-local HOME, offline Hub/dataset flags, and disabled plugin autoload,
bytecode and pytest cache. No install, credential read or network provider call
was needed.

Collection: **97 tests in 2.03s**, outer **2.415s**, exit **0**.
One body invocation at the tested HEAD: **97 passed, 0 failed in 6.44s**,
outer **7.000s**, exit **0**. JUnit records **97 tests, 0 failures, 0 errors,
0 skipped**; its suite duration is **6.408s**, not the wrapper wall time.
There was no failed test invocation or rerun in this task.

The selection reuses the prior 81-node bundle, updates three directly coupled
test functions for enforcement, includes the existing socket-close regression,
and adds 15 cap cases. These cover 1/31/32 allowed requests, refusal at 33,
concurrent admission, missing/drifted caps, invalid public metadata, and four
process/partial-receipt cases. The unchanged socket regression still requires
EOF for incomplete local headers and stable metadata after closure.

Provider bodies and turn results are synthetic; all non-loopback socket
destinations are trapped, and upstream TLS is replaced by local HTTP. The new
cleanup fixture uses the installed SDK's actual close method on a harmless
local Python child, plus the real runner, recorder, usage checks and receipt
projection. It does not start the Rust CLI, authenticate, prepare original
inputs, exercise host admission, or test a live Azure provider. Secret-looking
canaries are excluded from the public receipt/projection and captured output.

| Evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| `invocation.txt` | 3907 | `5ccfbf93f00b6c5ff3513f28ff33bbcd14608668d4bae64c727fbfb6dde0fcd2` |
| `collection.log` | 11536 | `4072d49f16266cb200a1938c898a308b042d097e40205c7a22ceaaf5169ac6e6` |
| `collection-timing.txt` | 19 | `8ae63c826825671bb9cb26eb5ddc00e9618a11c1832b95d568b0b053582bedf1` |
| `test.log` | 179 | `86fedcb3055ab329f068b3b4f6c1dbfb01dca10d946818044f92c2b91d71d35b` |
| `junit.xml` | 15640 | `ac732814b8e0f7f293b631b1f1f7e1e28ae06d038d78e4441d2915435655f6ca` |
| `timing.txt` | 19 | `cc3e53f1fd7319e87423ba2a3fab0b4f8a4f24c0e46202bbdaf4a19327a58404` |
| `tested-code.patch` | 35113 | `d9a61aa2374973b08dbd944eef2d1af022e56d3ca51ac2609ff0c69c91948a09` |

The initial observation proof remains **81 passed in 3.99s**, outer **4.518s**,
at `ae4b37da23518a7b0d9b0af567a43c81806e75f3`. Its later socket regression
first failed (**1 failed, 2.21s**, outer **2.594s**), then passed separately
(**1 passed, 1.93s**, outer **2.306s**) at
`f017607fb1ae0dbd334c9a2b6ae4ffaa847b45a3`. A subsequent one-node recheck at the
current base passed (**1 passed, 1.92s**, outer **2.320s**, exit **0**);
its files remain in `/ai-work/copilot/_tmp/p5-native-provider-close-recheck.r5v2oc/`.
These prior outcomes are not pooled with today's 97-test invocation. Earlier
hashes, failures and observation rationale remain in the
[immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/b43f7576e75e506f9e35c8c2cbe48a18b383dba1/tasks/LATEST_TASK_RESULT/README.md).

### Preserved boundaries and remaining gates

The source plan remains SHA256
`506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482`;
the shared Git helper remains
`77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`.
Plans, cap values, registrations, dependencies, workflow, grader and other
worktrees were not edited. Existing Git author/committer identity was retained
without attribution trailers.

The draft **32 per attempt / 128 per task** still has no measured native-call
headroom evidence. Task/pilot cumulative enforcement, token/spend limits,
served deployment/version, Max/Long application, actual CLI/provider behavior,
tariff/billing evidence, frozen-source/judge admission and fixed-source
review/CI remain separate gates. This local guard does not clear them or make
the current source launchable. No push, dispatch, grading or live experiment
occurred. Task3 run `37756891578` remains uncertain, spent and nonretryable;
no prior right is reset.

Reporting used `experiment-report-en` to keep counts, timings and synthetic/live
limits distinct, followed by `im-not-ai-en` for technical English. `openai-docs`
used local SDK source because the task is local only. No study redesign or UI
skill applied.
