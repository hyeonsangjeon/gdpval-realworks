# Latest task result

## Served identity and archived call-count investigation, local only (2026-10-24)

Scope: inspect Codex SDK/CLI 0.147.0 and existing local evidence for the five
registered tasks; identify a truthful served-model capture seam and measure
available call/turn counts. Worktree:
`/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch `codex/gpt56-native-pilot-caps-20261024`; inspected/tested head
`75d6be526c971ab43332260b8d16d7befbadd2d7`.
This is not an independently reviewed execution head or launch approval.
Only this result record and CHANGELOG change. No sealed plan, cap, runtime,
source pin, workflow, grader or execution right changes.

### A. No served-model identity is exposed by the pinned SDK

Inspected the existing installation at
`/ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/lib/python3.10/site-packages/`.
Both distribution metadata versions are `0.147.0`; nothing was installed.
The following paths are relative to that installation's `openai_codex/`:

| SDK source | Available fact, not a served-model attestation |
| --- | --- |
| `generated/v2_all.py:10241-10272` | `ThreadStartResponse.model` / `model_provider`: app-server thread configuration |
| `generated/v2_all.py:8516-8542` | `ThreadSettings.model` in `thread/settings/updated`: runtime configuration |
| `generated/v2_all.py:2443-2451` | `model/rerouted`: `from_model`, `to_model`, thread/turn IDs and reason, but no provider model version; the pilot already refuses this event |
| `generated/v2_all.py:2454-2464,2493-2499` | Safety-buffering model names and verification flags, not provider response identity |
| `_run.py:22-34,69-100` | `TurnResult` has status/items/text/usage, but no model/version or HTTP headers; collector retains only the last usage notification |
| `generated/v2_all.py:8579-8595,9643-9696,9933-9940` | Usage has total/last token breakdowns and context window; `Turn` and raw response-item notifications do not carry the Responses response envelope's `model` or HTTP headers |

A raw provider Responses envelope's `model` would be a candidate name source,
with separate evidence needed for any version not explicitly returned. That
envelope and provider response headers do not cross this app-server SDK seam.
No existing inspected archive supplies them. Requested deployment, context
window, token counts, safety flags and thread settings must not fill that gap.

Exact repository insertion points, if a separately authenticated provider
response observer becomes available:

- `batch-runner/gpt56_pilot_wire_receipt.py:135-145,175-198` already separates
  `app_server_thread_settings_not_served_identity` from unavailable
  `served_model` / `served_model_version`. The latter is the pilot receipt
  result seam; `response()` currently receives JSON-RPC replies, not Azure
  HTTP envelopes.
- `batch-runner/core/codex_runner.py:678-720,747-765,1569-1573` is the
  observation -> outcome -> returned diagnostics path.
  `batch-runner/step2_run_inference.py:1228-1230,1301-1342` is the bounded
  projection into persisted task observability; adding only a runner field
  would otherwise be dropped.
- The diagnostic already emits nullable `served_model` and an explanation at
  `batch-runner/scripts/diagnose_codex_foundry_connection.py:623-639`;
  its stream consumer at `699-753` sees usage/settings/completion, not the
  provider response.

**No production field-only patch:** it would add another permanently null
copy, not capture served identity. A fixture asserting that a requested model
was served would fabricate evidence. A truthful populated field needs a
lower-level provider response observer and corresponding receipt/source-review
work, beyond a small additive change and the sealed-plan boundary here.

The already-local connection artifact `12257312458`, run `39407062120`, remains
SHA256-verified:
`5d1a2540f0ba1291093b231d0e12e489ca197c32683aee521fb1622893600841`.
Its extracted `codex-foundry-connection.json` has one logical turn, eight
notifications, one usage update, 9,444 input / 5 output tokens and null served
identity. Neither one usage update nor equal total/last tokens measures HTTP
requests. It is a text diagnostic, not any of the five benchmark tasks.

### B. Measured turns are available; native request counts are not

Task order below is exactly the sealed five-task order. Counts include failed
and infrastructure-retry turns. These are ledger logical turns, **not native
model requests** (`core/codex_cost.py:14-36`). A settled row is not necessarily
a completed model response. Missing/unattempted tasks are excluded, not zero.

| Task ID prefix | exp033 | exp034 | exp035 lineage A | exp035 lineage B | Observed max / median | n |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T1 `02aa1805` | 2 | 4 | 4 | 4 | 4 / 4 | 4 |
| T2 `0112fc9b` | 1 | 1 | 1 | 1 | 1 / 1 | 4 |
| T3 `2ea2e5b5` | 1 | absent | 1 | 1 | 1 / 1 | 3 |
| T4 `3baa0009` | 2 | 4 | unattempted | 1 | 4 / 2 | 3 |
| T5 `0818571f` | 3 | 2 | 1 | 1 | 3 / 1.5 | 4 |

Sources, all already tracked locally:

- exp033 run `34528903950`: `batch-runner/tests/fixtures/run_record/step2_inference_results.json`
  and `cost_ledger_condition_a.jsonl` in the same directory. Nine distinct
  settled `call_id`s agree with the five result receipts; every row retains
  `call_reachability_unknown`. Ledger SHA256
  `60f9dd4a5bcf0598e5028c9064c40fae6695d5d728759d0edab0fe7a2b02b970`.
- exp034 run `34540053904`: `batch-runner/tests/fixtures/run_record/exp034_turn_ledger.json`,
  matching only the exact fixed-task IDs and counting distinct `call_id`s.
  SHA256 `7cf55a1b63479c8e215e7aef68529cde2959b5d2f231572d35b6c15994abe8d1`.
- exp035 lineage A: `batch-runner/docs/run_records/exp035_run34571840967_partial/outcomes.json`,
  SHA256 `9813c6bef60526befb3314c1c589de5f938aaf8705664fa628b5b76ddb77874c`.
  Independent restarted lineage B began at `34603033098`; its latest retained
  snapshot is `exp035_run34685779030_partial/outcomes.json` under the same
  run-record directory, SHA256
  `9e98e98d3dbd0a9030c95642388ccb53b210a5e8f4cbc685b13391e67b4a8d6b`.
  `docs/run_records/README.md:50-59` and that last snapshot's `report.md:14-21`
  establish the lineage split and checkpoint inheritance. Intermediate B
  snapshots are not independent samples and are not counted again. The table
  uses the last snapshot as provenance, not a claim that it executed inherited
  rows anew. Different historical protocols are descriptive, not matched repeats.

Separate longer-budget evidence must not be pooled into that historical table:
`tasks/codex_budget_pilot/retention_diagnostic_readout.json`, SHA256
`cda3068a6f46ab8395aac0127e5f2252847e1f6d9af475d3d96068179bd12287`,
records these inference receipt counts, not grader calls:

| Task | Per-cell turns, with producer runs | Max / median |
| --- | --- | ---: |
| T4 | 10 (`36696961231`), 39 (`36845127347`), 39 (`36907894862`), 6 (`36947454688`) | 39 / 24.5 |
| T5 | 18 (`37032230813`), 13 (`37066171719`), 38 (`37081963299`), 1 (`37101934436`) | 38 / 15.5 |

These use 180-minute cumulative cells and different fresh/keep recovery rules;
39/38 are whole-cell logical turns, not requests within one attempt.
The original external-budget pilot additionally records T5 B1 as 33 receipt
calls (`tasks/codex_budget_pilot/REPORT.md:316-325`); that incomplete subset
does not support a five-task pooled median.

Earlier GPT-5.4 comparison observations do not repair the gap:
native T1 run `37574558224` is uncertain with null usage/counters; native T3
run `37631184801` completed with null usage and no established native counters.
These are existing leader-verified records, not newly fetched raw artifacts
(`batch-runner/README.md:1560,2370-2384`;
`gpt54_time_budget_result_readout.py:479-483`).
They are excluded from numeric distributions, not imputed as zero.

**Cap judgement:** no measured native-call maximum or median is available for
any of the five tasks, so headroom under 32 native requests is **unestablished**.
The small historical turn counts cannot prove it; the longer-budget counts
also show why a whole-cell turn count cannot be substituted. The draft actually
says **32 per attempt, 128 per task across four attempts**, not 32 across the
whole task. Those numbers and their provisional heuristic derivation remain
unchanged. Native request measurement and hard enforcement are still required.

### Verification and remaining boundary

At the inspected head above, a completed focused offline invocation reported
**244 passed, 0 failed (15.06s)**. SDK field/metadata and real archived
diagnostic/ledger assertions also passed without constructing a runtime/client.
The pytest selection was:

```text
tests/test_codex_foundry_connection_probe.py
tests/test_codex_cost_adapter.py
tests/test_gpt56_pilot_wire_receipt.py::
  test_actual_flushed_serialization_and_native_absence_are_preserved
  test_changed_request_or_retry_is_refused_at_the_transport_seam
  test_returned_route_drift_and_mismatched_response_fail_closed
  test_closed_native_usage_shape_never_publishes_untyped_fields
  test_incomplete_or_duplicated_observation_never_completes
```

From `batch-runner`, used `env -i`, explicit PATH, credential-empty
session-local HOME outside `/tmp`, the existing dependency directory as
PYTHONPATH, offline Hub/dataset flags, disabled bytecode/plugin autoload,
`-m "not integration" -o addopts= -p no:cacheprovider -p pytest_timeout
--timeout=30 --tb=short -q`. No dependency changes.

An earlier broader invocation was interrupted after stalling in unrelated
result-host tests; it is not a completed suite or a pass count. Its two
observed auth-preflight test failures were reproduced separately (**2 failed,
0.48s**) and traced to the invalid test HOME `/tmp`, which correctly fails
the non-temporary workspace-root guard before auth. Only those two tests were
then rechecked with valid empty HOME: **2 passed, 0.53s**. The final 244-case
selection includes both; these separate runs are not added to its count.
The previously reported 408-test proof is historical and was not rerun here.

Remaining: independently verified served identity/version, provider-native
request measurement/enforcement, cumulative budgets, owner-approved caps,
frozen-grader/live evidence gates and independent final-source review.
No Azure/model call, credential minting, workflow dispatch, grading, push,
merge or execution approval occurred. This commit records pre-merge facts only.
