# Native CONNECTED diagnostic: web-search-free request proof

## Observed failure

Actions run [40960964194](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/40960964194)
used main `98e677c2f40699b5c964d6428a05e2da4b2f59be`, Codex SDK/CLI
0.147.0, GitHub-hosted Ubuntu 24.04 image 20261026.354.1. Authentication,
thread creation and turn creation succeeded. The HTTP observer checked one
request, rejected it as `native_token_request_unverified`, and forwarded zero
requests upstream. Usage was null and every served-configuration field was
`not_reported`. Workflow success is not a CONNECTED verdict or a five-task run.
The separate cleanup failure made the top-level verdict `unclassified_failure`.
The $7.20 reference reservation is not a measured charge; reconciliation with
the combined USD 200 pilot ledger is still required before pilot progression.

## Bounded intervention

The default pinned request inventory includes remote `web_search`. The strict
token precheck accepts only locally visible text and function/custom tool
definitions. This is a demonstrated incompatibility, not proof that it was
the only cause of the live refusal: that run did not retain the request body.

[Official Codex configuration](https://developers.openai.com/codex/config-reference/)
documents `web_search = "disabled"` as removing that tool. Codex 0.147.0's
schema includes the same value. The runner now sets it only for the existing
Sol response-observed CONNECTED diagnostic. Conflicting explicit overrides
are refused. Default runtime and five-task pilot configuration are unchanged.
No input/output/request/time/USD ceiling, response-evidence requirement or
server-hard-limit claim changes. The parser still rejects remote tools,
opaque context, missing usage and unsupported output-limit contracts.

## The actual pinned request's second format issue

Hosted model-free runs 40964728825 and 40965182470 rejected before fake
upstream forwarding. The second captured a 48,098-byte request containing a
developer `additional_tools` input followed by text messages; the top-level
tool list was empty. This is observed request structure, not model usage.

Pinned source explains it: [client.rs](https://github.com/openai/codex/blob/rust-v0.147.0/codex-rs/core/src/client.rs#L862)
uses `AdditionalTools` for Responses-lite model metadata, and
[models.rs](https://github.com/openai/codex/blob/rust-v0.147.0/codex-rs/protocol/src/models.rs#L816)
defines type/role/tools plus an optional ID. The
[namespace schema](https://github.com/openai/codex/blob/rust-v0.147.0/codex-rs/tools/src/responses_api.rs#L58)
contains name/description/tools and only function/custom children.

The precheck now recognizes this fully visible local-definition container:
developer role only, no non-null ID or extra fields, and only function/custom
tools (optionally in one exactly shaped namespace). Remote children, nested
namespaces, opaque fields and malformed containers still refuse. The entire
serialized body, including every definition byte, consumes the same input
estimate; no tool definitions or token usage are silently discarded. Fixtures
cover valid raw/namespaced definitions and eleven refusal/over-limit cases.
This is a supported-format correction, not a bypass of the safety conditions
or evidence that Foundry accepts the format.

## Model-free check before another paid attempt

`tests/test_sol_native_loopback.py` requires explicit opt-in and actual hosted
runner admission. The pinned real SDK/CLI uses a fake auth command and a
loopback scripted Responses provider through the production HTTP observer.
Only auth source and the far end of HTTP are replaced; the request precheck,
response capture, deadline, cleanup and native startup run normally. The test
requires one admitted request, Sol/Max request fields, an inserted
`max_output_tokens=10000`, locally inspectable tools/text, a completed scripted
reply and durable synthetic response evidence. Missing settings do not pass.

`gpt56-native-runner-check.yml` runs this after its actual Ubuntu 24.04 sandbox
proof, with an empty inherited environment plus allowlisted runner metadata.
It has no secrets, Azure login or paid input. Its artifact is explicitly
`synthetic_model_free`: it cannot prove provider capability, served settings,
model quality, actual billing or five-task completion. NAS does not run it.

The source-only successor preserves every predecessor file, the frozen grader
seal and all non-source plan fields. GHCP's separate model-free workflow also
fetches full Git history so historical fixture commits are present on dispatch.

## Paid response and the remaining 1M blocker

After the hosted loopback proof passed, PR #791 merged normally as
`f9fc251cb43fd24523111813816cd969509e5f15`. The owner-approved native-only
[run 40967326333](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/40967326333)
forwarded **one real request** and received a complete HTTP 200 response.
The provider body reported `model=gpt-5.6-sol` and `reasoning.effort=max`.
The terminal provider usage accounted by the proxy was **9,468 input tokens
and 5 output tokens**. SDK usage was null because the proxy withheld the
response for `context_window_unverified`; the SDK saw the proxy's 502, not
an upstream 502. The top-level diagnostic verdict was `unclassified_failure`.
Model version and context size were `not_reported`. No five-task run started.

Artifact 12939480285 (`codex-foundry-connection`) holds the masked response:
`codex-foundry-connection-responses/response-0001.json`, SHA256
`ac5a26a68390f92339d47bf94942d0a36f186bbec13306b220f2dd05d0ae19c8`.
The two paid-mode dispatches hold $14.40 of conservative reference reservations
in total, not measured billing. The first dispatch forwarded zero requests.
Neither reservation was silently released or merged into the pilot ledger;
reconciliation remains required under the combined USD 200 owner ceiling.

The hosted real CLI proof separately reported client `model_context_window`
**258,400**, despite requesting 1,000,000. Pinned
[Sol catalog metadata](https://github.com/openai/codex/blob/rust-v0.147.0/codex-rs/models-manager/models.json#L4)
sets both context_window and max_context_window to **272,000**.
[The config override](https://github.com/openai/codex/blob/rust-v0.147.0/codex-rs/models-manager/src/model_info.rs#L26)
clamps the requested window to that catalog maximum. This is a client/catalog
limitation, not evidence of the provider's maximum. Do not invent a larger
catalog limit or describe these observations as a verified 1M benchmark.

**Owner decision 2026-10-30 (benchmark card, item 3).** The pilot now hands
Codex a held catalog, `batch-runner/codex_catalogs/codex-0.147.0-models-gpt56-sol-1m.json`.
It is the bundled `models.json` byte-for-byte except Sol's window fields
(1,050,000, the Long-context maximum, 100% usable), so the requested 1,000,000
reaches the client. The wire observer adds it only above 272,000 and refuses
changed bytes. This is still a client setting: what the provider serves is
observed per response, and the records above stay as they were.

### Capture correction, without another paid retry

The capture redactor treated token rate-limit headers as credentials and
globally replaced numeric zeroes, damaging numeric JSON literals and the
`x-ms-served-model` header. The old artifact and its hash are preserved; its
damaged model version is not reconstructed or asserted as live evidence.
This bug is separate from the missing context field: the in-memory parser
also observed no context size before masking.

Only named, typed quota headers are now recognized as non-secret metadata.
[Public rate-limit documentation](https://developers.openai.com/api/docs/guides/rate-limits)
identifies token quota counters/reset durations; the observed Azure renewal
counter is handled under the same narrow numeric/duration grammar. Unknown
header names/values still redact. Request credentials always enter the secret
set, even when numeric or echoed in a quota field; rate-limit identity keys
also redact. These counters are **not context-window evidence**. Fixtures and
the hosted fake provider exercise zero counters without making another paid
call or weakening any missing-context refusal.

The diagnostic also labels a successful provider reply withheld by its own
missing/mismatched-field guard as `response_evidence_unverified`, even
when the SDK reports the resulting proxy error. It remains a failure, never
`connected`. A separate SDK failure with otherwise valid response evidence is
not reclassified. The hosted loopback proof covers both a complete synthetic
response and a synthetic HTTP 200 response missing context; neither is a
paid rerun or retroactive alteration of the saved live verdict.
