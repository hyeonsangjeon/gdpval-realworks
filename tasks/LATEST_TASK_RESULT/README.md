# Latest task result

## Native pilot source registration refresh (2026-10-25 13:20 KST order)

The new 2026-10-25 source profile passes `source_plan_snapshot` and reaches
`inspect_plan`: **58 source hashes match, 0 mismatch**, and
`configuration_valid=true`. The bounded plan-only command exits **2**, because
all **11** existing launch blockers remain. This clears only the earlier
`pilot_source_registration_refused`; it does not authorize a pilot, retry or
full-220 run.

The first related test invocation reported **4 passed, 1 failed, 0 skipped**.
After correcting the test's stale observed grader hash, only that failed node
ran again: **1 passed, 0 failed, 0 skipped**. These are separate proofs, not a
new combined five-test pass. No model/network call, authentication, preparation,
dispatch, grading, push or PR occurred.

### Source and scope

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`. It was clean at each tested
commit. Other worktrees were not changed.

| Source role | Full HEAD | Tree |
| --- | --- | --- |
| Starting caps source | `9511b3d70719be2503d779b3fd17dcb07f49e312` | `8ee899bc98550c0aaed033505deeed6fa487ec30` |
| Registration implementation; first five-node invocation | `6fffb66a3bb43197bc5ccd7d5ac53bc9c864c577` | `d7aa3b8dbac9dc152c68f8024c398db3a879f10e` |
| Test-only correction; one-node proof and plan-only command | `58a7f38abcc90dc63f490c444b5f83e7f05be82f` | `34146495094d0a58df72392bcd19ab224282e267` |

The final local child changes only this record and CHANGELOG. Its full identity
and record hashes are in the evidence directory's `final-source.txt`; tested
source/test/profile bytes remain those of `58a7f38ab`. The
`--reviewed-source-sha` argument identifies local source bytes, not independent
approval. Final-source review and CI remain outstanding.

Changed files under `batch-runner/`:

- `experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261025.yaml`:
  source-only successor for the same run, with the predecessor, reason and hash.
- `gpt56_sol_codex_pilot_preflight.py`: select the successor, require exactly
  five changed source roles against the sealed predecessor, and retain its
  bytes in the existing held Git-blob checks and final rereads.
- `gpt56_pilot_wire_receipt.py`: keep the caps draft's exact old registration
  reference through `SOURCE_PROFILE_PREVIOUS`; no cap or guard is relaxed.
- `tests/test_sol_source_registration.py` and
  `tests/test_gpt56_sol_codex_pilot_preflight.py`: cover the successor, exact
  delta, predecessor/stale-pin refusal, preserved caps loading and old-plan
  source refusal.

The five changed pins are the four already-drifted caps files
(`core/codex_runner.py`, `step2_run_inference.py`, `gpt56_pilot_wire_receipt.py`,
`gpt56_pilot_runtime_caps_usage.py`) plus the updated source selector. The
58-role set and every non-source plan field are unchanged. Existing clean
commit/tree, imported-file, held-blob, admission and final-reread checks remain.
An explicit 10-23 request at this changed source still refuses.

| Registration | Bytes | Raw SHA256 | Canonical plan seal |
| --- | ---: | --- | --- |
| Unchanged 10-23 predecessor | 17227 | `506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482` | `d67216b5d74149c8f4516adb54712269aeb6f603fa507986625c344d83d3bde4` |
| New 10-25 successor | 17430 | `f88c850558674a4c3a89ae0840f23dc27402aefafe56f7323ba3d3b8ad33a3b2` | `c501e11418c4cefdbbcec143b9c53c8092b07660779bcf75f99d450a48f49e7b` |

The original active plan remains SHA256
`f51d92c35f388f016488f15d5e96acd1f9de10345fb2379dac7e194eadbbe2fd`.
The **7343-byte** caps draft remains SHA256
`7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6`.
No frozen plan, hash record, grader pin, shared Git helper, workflow, dependency,
model, host or threshold was changed.

### Offline proof

Evidence directory: `/ai-work/copilot/_tmp/p5-native-source-20261025.4Hj6Eu/`.
`invocation.txt`, `invocation-fixed.txt` and `preflight-invocation.txt` retain
the exact commands, source identities and working directories. All body
commands used **TERM120s/KILL5s**, `env -i`, the existing Python 3.10 environment,
offline Hub/dataset flags, disabled bytecode/plugin autoload/pytest cache and
local-only Git settings. No HOME or CODEX_HOME override was declared.

| Invocation | Result | Pytest elapsed | Wrapper wall | Exit |
| --- | --- | ---: | ---: | ---: |
| Five related nodes at `6fffb66a3` | 4 passed, 1 failed, 0 skipped | 5.70s | 6.10s | 1 |
| Only the failed source-registration node at `58a7f38ab` | 1 passed, 0 failed, 0 skipped | 5.29s | 5.64s | 0 |
| New-profile plan-only preflight at `58a7f38ab` | source verified; inspect reached; launch refused | not a test | 1.51s | 2 |

Collection reported **5 nodes in 2.76s**, outer **3.16s**, exit **0**. The first
selection comprised `test_sol_source_registration`, the two current/stale-hash
`test_active_grader_template_source_foundry_preflight` cases, and the two
missing/drifted `test_native_request_cap_refuses_unsealed_caps_before_a_listener`
cases. Only `tests/test_sol_source_registration.py::test_sol_source_registration`
was rerun. Local Git/archive and adapter checks are real; provider, launch,
preparation and external effects are forbidden-call fixtures, not live proof.

The failed node had already passed source registration and correctly refused
identity compilation with `grader_template_source_drift`. Its expected
*observed current* grader closure was stale. The test-only correction changes
`b87877b47aab42d5b32f12222dfa515c8a94a08f316cbbe5e65cb13715c97cf4`
to `0b5a59714e10b5193c88c32e934719741c8c17d4a433e565db38c21462802106`.
The frozen expected closure remains
`47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf`;
the mismatch and required refusal are preserved. No failed artifact was replaced.

| Evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| `test.log` | 895 | `28fdc9c833d7bdaf0b2c0d48c24429586962df9609bf3f57681338e2fea2c019` |
| `junit.xml` | 1775 | `e50e134c6ccedae61941a6cdb7c4d99235421d940b4c8cc3dd1fdd2f3666f4a8` |
| `test-fixed.log` | 98 | `747939a7ad1389d2150871a2e1986fed8e65dacd2c7b220577f2b4c3b0975d28` |
| `junit-fixed.xml` | 360 | `e412507803208b44415b161fddb0a93a39f9279d0e2be63b3fcd2d3649d3d91f` |
| `preflight.json` | 2451 | `2b6a06d4f8730de24a6f59dd26aea14b9837a0ddbe78805cacc3597c1645ee42` |
| `tested-code.patch` at first test HEAD | 31842 | `e672db2e18b8063c413d8c4719527f95967702e04b8d70a01523222789057aa0` |
| `tested-code-fixed.patch` (full-index, starting source to final tested code) | 32854 | `23d8da3687fe77219b97c8b4e8f4e297bf930cfbc4ae72a87e86c06e42c94bce` |

`evidence.sha256` is SHA256
`7b17de963c0fbeedcd7a96344ffa7029461f826679789e4e538ea04e796de813` and includes
commands, collection, separate timing files, both proofs, the empty preflight
stderr and tested-file hashes. `blocker-comparison.json` is SHA256
`aa6cf9ab4653330794dfde04ac025153e70f6c20ef01dee5432a8aabfae7a6c4`.

### Preflight comparison and remaining conditions

The command selected the new `..._source_20261025.yaml` explicitly and passed
`--reviewed-source-sha 58a7f38abcc90dc63f490c444b5f83e7f05be82f`.
`source_registration.status=source_verified`, `configuration_valid=true`,
`launch_allowed=false` and `full_220_allowed=false`. Source launch/retry authority
remain false; the evidence gate has no consumed bundle or reviewed-source
approval and returns `foundry_evidence_gate_refused`.

Against the leader-provided 12:10 baseline, the source-registration refusal is
cleared. Of the separate **11** launch blockers, **0 cleared, 11 retained,
0 new**:

```text
foundry_account_project_deployment_identity_unverified
foundry_served_model_version_unverified
max_and_long_1m_capability_unverified
native_call_and_token_limits_unresolved
prepared_input_bytes_unverified
live_inference_identity_and_wire_unverified
pilot_dispatch_and_grading_identity_not_wired
foundry_usage_and_tariff_mapping_unverified
native_sandbox_and_result_bundle_host_unverified
actual_pilot_deployment_not_prepared
prepared_request_capture_unverified
```

The legacy account/project blocker name does not require a child-project ID
for `direct-v1`. This task supplies no new account/deployment evidence. Caps
remain **32/attempt, 128/task, 640/pilot**, **1,800 seconds**, and **300,000 input /
10,000 output tokens**. The token limits remain reported-overrun stops, not
hard provider ceilings; monetary cap remains null. Source consistency does not
close served-model/version, Max/Long, private-input/capture, sandbox, usage/tariff,
dispatch/grading identity or frozen-grader admission gaps.

The preceding **165-pass** caps proof, failed reproducer, tokenizer investigation
and their separate older proofs remain in the
[immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/9511b3d70719be2503d779b3fd17dcb07f49e312/tasks/LATEST_TASK_RESULT/README.md).
They were not rerun or pooled here. Task3 run `37756891578` remains uncertain,
spent and nonretryable; no finite right was consumed, restored or retried.

`experiment-report-en` kept observations, separate test populations and live
limits distinct; `im-not-ai-en` was applied after the protection brief. Numbers,
source identities, hashes, refusal conditions and uncertainty were reconciled.
No experiment redesign, UI work or specialist endorsement applies. Existing
Git identity was retained, with no attribution trailers; publication and
execution still require separate authority.
