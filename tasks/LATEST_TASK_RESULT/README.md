# Latest task result

## Native pilot deployment and capture linkage checks

The **2026-10-25 22:10 KST order** added two local preflight checks. A deployment
must refer to the same evidence, identity, configuration and input digests as
the preceding gates. A capture must also refer to that deployment digest and
the supplied source SHA. Missing, malformed or conflicting linkage keeps the
existing stage refusal and does not clear its blocker.

The targeted invocation reported **34 passed, 0 failed, 0 errors, 0 skipped**
in **124.63 seconds**; the Bash wrapper took **125.042 seconds**, exit **0**.
The new source profile passed source verification and reached `inspect_plan`.
Plan-only preflight exited **2** in **1.644 seconds**, with **0 launch blockers
cleared / 11 retained / 0 new**. Two local integrity gaps are covered; no real
deployment, input or capture evidence was supplied or fabricated.

### Source and implementation

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`.
Branch: `codex/gpt56-native-pilot-caps-20261024`. All commits are local.

| Role | Identity |
| --- | --- |
| Starting HEAD | `ba377b936e6ecf2841caee9eb039ee71ce7a8ec3` |
| Starting tree | `ca6f06b8302c030232b8c3aac48307535d3c1528` |
| Tested and self-reviewed source HEAD | `bbc12b69414ef90580711f1d40f42eb17778f479` |
| Tested source tree | `a50869a6105782fa871b004f9f0ce883ef7e9587` |
| Before and after test/preflight body commands | Clean; same source HEAD/tree |

The final local child changes only this record and CHANGELOG. Its exact
HEAD/tree and record hashes are retained in the evidence directory's
`final-source.txt`; it is not relabeled as a tested or independently approved
revision. The `--reviewed-source-sha` argument binds local bytes during this
proof; it does not confer leader approval.

Only `gpt56_sol_codex_pilot_preflight.py` changes production behavior.
`_same_reported_upstreams` at line **812** compares the preceding gates' digests
and source linkage. The deployment gate at line **870** and capture gate at
line **933** run these comparisons before clearing a blocker. They retain
`pilot_deployment_binding_gate_refused` and
`pilot_pre_execution_capture_gate_refused`; no new waiver or launch path exists.
Underlying verifiers, their byte/freshness checks and runtime call sites are
unchanged. This bounded self-review found additive checks, not weakened guards.

The successor
[`gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml`](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml)
has **58 matching source hashes**. Only the preflight hash differs from the
sealed 10-25 profile; all non-source fields are identical. The selector holds
and rereads both predecessor files, enforces this exact one-file delta and
retains the older refresh-set, archive, imported-file and final source checks.

| Record | SHA256 |
| --- | --- |
| New profile bytes | `740ec085c047ad359b4c5e56a8bf5867ebc2cb6c229d479262d6815fbe8154cf` |
| New canonical plan seal | `8a50ed179fe6572179c7de0b27fd15777343e2e64bdb8ba12ffe459d99da7fcf` |
| Unchanged 10-25 profile | `f88c850558674a4c3a89ae0840f23dc27402aefafe56f7323ba3d3b8ad33a3b2` |
| Unchanged 10-23 profile | `506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482` |
| Unchanged 7343-byte caps draft | `7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6` |

### Binding breakdown

These statuses distinguish implemented checks from the evidence needed to
satisfy them. A missing receipt is not evidence that the account or model is
unavailable. The earlier **0.5–1 day** estimate is not a new delivery promise.

| Sub-binding | What the code/plan already binds | What remains and who can close it |
| --- | --- | --- |
| Source registration | [Preflight:271](../../batch-runner/gpt56_sol_codex_pilot_preflight.py#L271): exact source/profile bytes, held paths and current commit. | **Locally closed** for this successor. Final published HEAD review, CI and environment approval remain **after merge/review** gates, not automatic consequences of merge. |
| Deployment to earlier receipts | [Preflight:812](../../batch-runner/gpt56_sol_codex_pilot_preflight.py#L812): same evidence, identity, config and input hashes, including their source linkage. | **Locally closed this turn** at the report boundary. This supplies no deployment evidence. |
| Account/deployment and requested model | [Deployment:178](../../batch-runner/gpt56_pilot_deployment_binding.py#L178), [deployment:203](../../batch-runner/gpt56_pilot_deployment_binding.py#L203): exact resource bytes, account hierarchy and evidence hashes; [deployment:165](../../batch-runner/gpt56_pilot_deployment_binding.py#L165): the same deployment in both candidate request fields. | **Owner-reviewed evidence** is required. [Plan:150](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml#L150) keeps identity fields null. `direct-v1` does not require a child-project ID. Actual served identity/version and Max/1M support need **live/external evidence**. |
| Five-task input bytes | [Plan:174](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml#L174) pins dataset/revision, parquet, prompts and references; [input:105](../../batch-runner/gpt56_pilot_input_bundle.py#L105) verifies their projections and config/identity links. | The local verifier exists. Real prepared bytes and their accepted receipt remain absent from this task; **owner-authorized preparation** is a separate prerequisite. No private input was prepared or downloaded here. |
| Capture to accepted deployment | [Capture:175](../../batch-runner/gpt56_pilot_input_capture.py#L175) binds prepared bytes, request intent and upstream receipts; [preflight:933](../../batch-runner/gpt56_sol_codex_pilot_preflight.py#L933) now matches the preceding deployment and source. | The cross-gate check is **locally closed this turn**. An actual Step 1 capture still requires **authorized preparation**; capture intent is not model consumption or live wire evidence. |
| Dispatch and frozen grading scope | [Identity:213](../../batch-runner/gpt56_pilot_identity_plan.py#L213) binds the same ordered five tasks, condition, repeat, prompts and judge/rubric recipe. [Identity:113](../../batch-runner/gpt56_pilot_identity_plan.py#L113) retains the exact frozen-grader source check. | The current closure still refuses with `grader_template_source_drift`. **Owner review/direction** is needed for a separate frozen-grader source binding; merge alone cannot clear it and no judge hash was repinned. |
| Actual inference to grading | [Identity:145](../../batch-runner/gpt56_pilot_identity_plan.py#L145) and [config:138](../../batch-runner/gpt56_pilot_config_bundle.py#L138) leave inference repository/revision unset; [plan:226](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml#L226) keeps the revision null. | A future **live result/retention identity** and separately authorized grading are required. Synthetic output is not a substitute. |
| Host, usage, tariff and money | [Preflight:174](../../batch-runner/gpt56_sol_codex_pilot_preflight.py#L174) retains live-owner receipt boundaries; [plan:238](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml#L238) keeps the tariff hash and monetary maximum null. | Host/wire/usage and tariff application need **live evidence**; the monetary cap needs an **owner decision**. These are outside this local implementation. |

The source-registration test still observes current grader closure
`0b5a59714e10b5193c88c32e934719741c8c17d4a433e565db38c21462802106`
against frozen expected closure
`47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf`.
Its required refusal passes. This is an existing subcondition of
`pilot_dispatch_and_grading_identity_not_wired`, not a twelfth launch blocker.

### Targeted evidence

Evidence directory: `/ai-work/copilot/_tmp/p5-native-binding.EVhVA2/`.
`invocation.txt` records the exact selectors, commands, environment and exits.
The existing Python **3.10.12** environment was reused with `env -i`, HF offline
flags, disabled pytest plugin autoload/cache/bytecode and local-only Git reads.
Test bodies used **TERM600s/KILL5s**; collection and preflight used
**TERM120s/KILL5s**. No HOME/CODEX_HOME override or installation was used.

The **34-case** body invocation contains **24 new synthetic cases** and **10
directly related cases**, including the updated source-registration node.
Both new successful paths use the real bundle/capture verifiers. Negative
cases inject inter-gate metadata drift, missing/null/malformed linkage and
source/deployment conflicts after real verification. These fixtures do not
demonstrate a historical or live race. Their synthetic preparation uses no
private inputs; provider, auth, executor and grading effects remain trapped.

The first collection launcher exited **127** because `/usr/bin/time` was
absent; pytest did not start, and no timing/JUnit was produced. Its **60-byte**
`collection.log` is retained. Bash's built-in timing then collected **34 nodes**
in **6.75 seconds**, outer **7.844 seconds**, exit **0**. Collection is separate
from passing tests. The body ran once; no test or assertion needed correction.
JUnit records **34 unique cases**, no failures/errors/skips, and **124.551
seconds**, distinct from pytest and wrapper duration. No warnings were reported.

The plan-only command, from `batch-runner/`, was:

```bash
timeout --signal=TERM --kill-after=5s 120s env -i \
  PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python \
  gpt56_sol_codex_pilot_preflight.py \
  --plan experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml \
  --reviewed-source-sha bbc12b69414ef90580711f1d40f42eb17778f479
```

It ran alongside the targeted tests while repository source stayed clean.
It reports `source_verified`, `configuration_valid=true`, no configuration
problems and `launch_allowed=false`. With no real evidence bundle supplied,
the evidence gate retains `foundry_evidence_gate_refused` and a null consumed
bundle. Standard error is empty. This intentional exit **2** is not a test
failure or launch approval.

| Evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| `test.log` | 1396 | `886c9b1e19f6a2eda1b8c94da3033ddc298bb8c82d427af82027e26d8daa7f3e` |
| `junit.xml` | 5423 | `8f7244333c5dbc569dffe2019842b09fad6a7f8fcd9d44e19d87300de447d9e6` |
| `timing.txt` | 24 | `1f44283c681781ab3eae1d4fc1230746d0a3ce7c890ae1e980574aa7a14e8844` |
| `preflight.json` | 2456 | `05389a76f58b6bf117e8be5250849c2a47f1f19e5a840527149298dd9e159878` |
| `preflight-timing.txt` | 22 | `0223b91ce2316346bcbd5b379a4e405f1e42da18b5130155842d4209bd39459b` |
| `tested-code.patch` | 42832 | `14d0361906505b217df21e299bcea9fd192584c946229913dbc123dc4cdc6a0f` |

`source-hashes.sha256` contains the five changed code/test/profile hashes and
the unchanged predecessor/caps hashes. `evidence.sha256` covers the commands,
collection failure/success, logs, JUnit, timings, preflight and code patch.

### Remaining gates and prior history

All **11** launch blockers remain, in the same order:

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

The [prior immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ba377b936e6ecf2841caee9eb039ee71ce7a8ec3/tasks/LATEST_TASK_RESULT/README.md)
retains the **67-module, CI-derived related selection** with
**6002 passed, 0 failed/errors/skipped, 3 warnings** at
`e0fa32ef30dea02da3ee918b40ae08e744d67e14`, tree
`b67cd5e4d4b956b07850addbfbd1954330d341a0`: pytest **15178.96s**, wrapper
**15180.42s**, exit **0**. Its earlier **3600.02s / exit 124** watchdog outcome
has no final summary/JUnit and remains separate. The earlier two-file review's
**3 maintained / 4 strengthened / 0 weakened** rows apply only to that source.
The record also links the separate **4-pass/1-fail** registration proof,
its **one-node pass** and older **165-case** caps proof. None was rerun or
pooled with this turn's **34** cases; old review is not approval of this HEAD.

Caps remain **32/attempt, 128/task, 640/pilot**, **1800 seconds**, and
**300000 input / 10000 output tokens**. Reported token-overrun stops do not
establish hard provider token ceilings. The monetary cap remains null.
Non-source plan values, model/host/grader identities, cap values, QA,
dependencies, workflows and finite rights were not changed. Task3 run `37756891578` remains uncertain,
spent and nonretryable. No execution right was consumed, restored or retried.
Final-head owner review, CI, environment approval and separately authorized
live evidence are still required. No model, credential/token, external-network,
Azure management, dispatch, grading, push or PR operation occurred.

`experiment-report-en` separated local integrity, synthetic evidence and live
limits; `im-not-ai-en` preserved protected facts and qualifications. The brief,
checkpoints and reconciliation are retained with the evidence. No experiment
redesign, UI work or specialist endorsement applies. Existing Git identity
was kept without attribution trailers.
