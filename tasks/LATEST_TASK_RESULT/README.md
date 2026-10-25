# Latest task result

## Native pilot hard token cap contract investigation

The offline investigation found **no sufficient evidence to implement a
server-enforced token cap** on the fixed Codex SDK/CLI **0.147.0** to Foundry
GPT-5.6 Sol path. Both existing attempt limits remain client checks of reported
usage. This task changes documentation only; it does not weaken or bypass a
gate, change the plan, or declare the pilot launchable.

| Existing attempt limit | Verdict | Decisive boundary |
| --- | --- | --- |
| 300,000 input tokens | **Client post-check only** | Context-window and compaction config/readback fields do not establish a server input reservation or a sum across native requests. |
| 10,000 output tokens | **Client post-check only** | Generic OpenAI `max_output_tokens` semantics cover one response's visible output and reasoning tokens. Neither this Codex sender's mapping nor the Foundry Sol-specific server contract was established. |

The [contract investigation](../../batch-runner/docs/gpt56_native_hard_token_contract.md)
records the exact package/schema/runtime locations, field-by-field findings,
evidence hashes and aggregate-budget implications. The inspected wheels do not
include the Rust provider serializer source or full `ConfigToml` schema.
App-server `Config` permits extra properties, so a missing declared field does
not prove that every spelling is rejected. A generic SDK request field, binary
string or configured model label is not a verified provider contract.

### Source and preserved boundaries

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`.
Branch: `codex/gpt56-native-pilot-caps-20261024`. All commits remain local.

| Role | Identity |
| --- | --- |
| Clean inspected starting HEAD | `af685f5c4a436a7f476a41c5cf4f44a702c0a67d` |
| Inspected tree | `96ca35aa8f8da94a5d6bf8c9ea5f33a3bb93494f` |
| Runtime/source-registration changes | None; no successor registration was needed |
| New runtime-tested or independently approved HEAD | None |

The final documentation commit's full HEAD/tree and three file hashes are
retained in the evidence directory's `final-source.txt` and returned in the
handoff. That commit is not relabeled as a tested or approved runtime revision.

Native request limits **32 per attempt / 128 per task / 640 per pilot**, the
**1,800-second** deadline, all token values and the null monetary cap remain
unchanged. Existing `native_input_token_cap_exceeded` and
`native_output_token_cap_exceeded` stops still follow reported usage;
`token_hard_limit_enforced=false` remains required. Missing usage is unknown,
not zero. The earlier decision not to use an unverified Sol tokenizer estimate
was preserved. No model, host, judge, QA, dependency or workflow changed.

The unchanged sealed files retain these SHA256 identities:

| Record | SHA256 |
| --- | --- |
| 7343-byte caps draft | `7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6` |
| 10-23 source registration | `506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482` |
| 10-25 source registration | `f88c850558674a4c3a89ae0840f23dc27402aefafe56f7323ba3d3b8ad33a3b2` |
| Active 10-25 bindings successor | `740ec085c047ad359b4c5e56a8bf5867ebc2cb6c229d479262d6815fbe8154cf` |

### New offline evidence, not a test replay

Evidence directory: `/ai-work/copilot/_tmp/p5-native-hard-token-contract.aOpcll/`.
The installed binary returned `codex-cli 0.147.0`. Its package metadata,
binary, SDK client and generated Python protocol matched their local wheel
`RECORD` size/digest entries. That check exited **0** and establishes local
distribution consistency, not remote attestation or provider behavior.

`invocation.txt` retains the exact schema command with
`env -i / TERM60s / KILL5s`. The existing binary's
`app-server generate-json-schema --experimental --out` exited **0**, Bash wall
**0.041 seconds**, with a **0-byte** output log. No app-server session or
model request was started. `schema-observations.json` records its extensible
config and absent declared turn token-cap fields, SHA256
`668e3bddf8dde7244601ef9bf0a17764415808d228be46f21d13deb312e36bca`.
The report lists the three generated JSON files' exact sizes and hashes.

No pytest body, collection or plan-only preflight ran for this documentation-only
outcome. **0 tests were executed; pass/fail/skip counts are not applicable**, and
there is no new JUnit. Validation was limited to the installed evidence/schema,
documentation scope/whitespace and unchanged sealed-file hashes. No old passing
suite was replayed. The optional `strings` lookup was unavailable; its help
wrapper's exit **1** is recorded separately, not called a test failure or pass.

The [immutable preceding record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/af685f5c4a436a7f476a41c5cf4f44a702c0a67d/tasks/LATEST_TASK_RESULT/README.md)
preserves **34 passed, 0 failed, 0 errors, 0 skipped** at
`bbc12b69414ef90580711f1d40f42eb17778f479`, pytest **124.63s**, wrapper
**125.042s**, exit **0**. Its separate plan-only preflight reached
`source_verified` and `inspect_plan`, exit **2** in **1.644s**, with
`launch_allowed=false`. These are prior results, not fresh measurements at this
documentation commit. The separate **6002-pass** proof at `e0fa32ef3`, earlier
registration failure/correction, and older caps proofs remain linked there and
are not pooled with this investigation.

### Remaining conditions

The unchanged launch ledger is **0 cleared / 11 retained / 0 new**. This is not
a fresh preflight verdict; `native_call_and_token_limits_unresolved` remains.

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

Further implementation needs an approved evidence package binding the fixed
Codex request serializer and exact Foundry Sol API/version to hard-limit
semantics. Any per-response field would also need an evidence-backed remaining
allowance across the attempt. Deployment TPM/quota controls remain
**owner/external** matters, not a substitute for an attempt budget. Missing
local evidence does not establish missing account/model access. `direct-v1`
does not require a child-project ID.

Final-source owner review, CI, environment approval and separately authorized
live evidence remain open. The frozen-grader source refusal is unchanged, not
a new twelfth blocker. Task3 run `37756891578` stays uncertain, spent and
nonretryable. No finite right was consumed, restored or retried. No installation,
download, credential/token read or issuance, network/model call, Azure
management, dispatch, grading, push or PR operation occurred.

`openai-docs` used installed first-party package/schema evidence under the
offline restriction; no official online retrieval was performed.
`experiment-report-en` kept schema, runtime and server claims separate;
`im-not-ai-en` preserved the technical wording and evidence limits. The brief,
checkpoints and reconciliation are retained with the evidence. No experiment
redesign or UI/animation skill applies. Existing Git identity is unchanged;
no attribution trailer or external approval is added.
