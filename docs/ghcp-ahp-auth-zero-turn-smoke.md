# GHCP authentication-only zero-turn smoke

This is diagnostic authentication plumbing, not permission to run the five-task
gate. No paid/model execution, first-turn probe, or owner-policy change is enabled.
The pending patched-host activation remains refused; `execution_allowed`,
`admission_allowed`, and `launch_allowed` remain false even on smoke success.

## Runtime and publication boundary

`.github/workflows/ghcp-ahp-auth-zero-turn-smoke.yml` is **workflow_dispatch only**,
with a false-by-default `confirm_zero_turn_only` input, `ghcp-sol-gate` environment,
`ubuntu-24.04`, `contents: read`, and a 10-minute job bound. The runtime validates
the repository, branch, workflow ref/SHA and existing hosted-runner identity.
There is no push, PR, schedule or workflow_call trigger.

Public pins and offline dependencies are prepared without credentials. Only the
authentication step receives `COPILOT_GITHUB_TOKEN`; the value never appears in
argv or a credential file. The parent consumes the environment entry and invokes
the existing `ghcp_ahp_metadata_broker.py` with captured, bounded stdout/stderr.
The original broker/probe/native process, policy readback, HTTP and zero-turn
guards are unchanged. No interactive login, credential-cache or `gh auth token`
fallback is used, and no secret is supplied to the later publication step.

Successful evidence must agree across the original probe, AHP handshake, native
wire capture, recomputed thread-policy report and metadata broker receipt:

- Exactly one `GET https://api.github.com/copilot_internal/user` and one `/models`
  GET on the **single allowlisted origin advertised by the first response**,
  both 200. No redirects, retries, extra endpoints or token exchange. Wire-side
  metadata status/addresses must match the broker receipt. Cached local reads
  do not become repeated external requests.
- Successful AHP authenticate and one session creation through the existing
  management/readback bridge; exactly one correlated native `thread/start`
  result. Initial SDK model/effort/approval/sandbox/network must match Sol, max,
  untrusted, readOnly and false. Requests still require the fixed web-search,
  model/provider and context contract; no aliases or fallback are added.
- No prompt, turn/item request or event, CAPI inference traffic, observer refusal,
  synthetic observation, unmeasured observer, missing cleanup, or unexplained
  count/hash/run-identity difference. Declared zeroes alone are not sufficient.
- Metadata HTTP GETs are counted separately from **CAPI inference requests**.
  The former are two on success; the latter and model turns must be zero.
- A successful authentication smoke is **not** a successful live-model gate.
  Missing served-model/context/web-search proof remains `not_reported` and does
  not change the existing policy/admission verdict.

This first version uses the **original pinned host**, not the patched build. It
does not circumvent the known unpatched prewarm policy mismatch. Authentication
can therefore be accepted while strict session/thread creation is still refused.
Do not present a local fixture pass as proof that the real authenticated smoke
will pass. The owner policy decision and the corresponding reviewed runtime
connection are still required to resolve that known blocker.

## Independent leakage checks

`ghcp_ahp_auth_publication.py` does not import the diagnostic redactor. It checks
actual credential bytes, JSON-decoded echoes, URL/base64/base64url/hex forms,
unmasked sensitive fields and credential syntax. Existing exporters must already
have masked source JSON; residual secrets cause a hard refusal, not a successful
repair of the evidence. Captured process output is redacted before its independent
scan. A fault in the redactor cannot disable the independent checker.

All bytes are checked **before** publication writes. Symlinks, hardlinks, oversized
files, duplicate JSON keys, unknown file names and directory reuse are refused.
Only fixed, explicitly listed JSON/Markdown artifacts can be uploaded. Original
private staging is temporary; a failure publishes no unvalidated core artifacts
and reports unmeasured counts as `not_reported`, not fabricated zeroes.

The authentication step hands the SHA256 of `leak-scan.json` to the next step via
`GITHUB_OUTPUT`. Only that public digest crosses the boundary. The secret-free
step verifies the digest, all artifact hashes, identity and the diagnostic verdict
again before enabling upload. Rehashing a changed artifact/manifest does not
replace the prior step's trusted digest. Failure logs remain captured; arbitrary
exception or argparse text is never printed. No credential fingerprint is stored.

Artifacts: `auth-smoke.json`, `auth-smoke.md`, `process-log.json`, `leak-scan.json`,
and, only after successful validation, `probe.json`, `handshake.json`,
`thread-policy.json`, `wire-capture.json`, `metadata-http.json`.

## First-turn metadata investigation — 2026-11-10, static only

Pin: VS Code 1.144.0 commit
`2c33b50b16c472efe58357d1d2a8a5414bc23fbf`, Chat 0.72.0, generated Codex SDK
0.163.0 protocol. No first turn or authenticated request was performed.

| Quantity | Field/path found | What it establishes |
| --- | --- | --- |
| Upstream reported model | Responses SSE `response.created/completed/...` → `response.model`, or HTTP JSON `model` | Response-side candidate, if CAPI returns it. The pinned client does not guarantee its presence or independently attest the backend model. |
| Server-applied reasoning effort | No dedicated authoritative applied-effort field found. Candidate: response `reasoning.effort` | Returned reasoning configuration, if present; not proof of actual compute/depth or a documented final server-policy value. `reasoningOutputTokens` is a count, not the effort setting. |
| Context window | `thread/tokenUsage/updated.params.tokenUsage.modelContextWindow`; associated `threadId` and `turnId` | Native SDK-reported window, nullable. Not the provider's independently measured context capacity. No required CAPI response context-window field found. |
| AHP usage model | `ChatUsage.usage.model` | The selected `modelId` is copied into usage; not a served-model observation. |
| Response headers | Upstream fetch `Response.headers` is available | No specific guaranteed model/effort/context header contract found. Collect only redacted allowlisted fields; do not infer missing values from request IDs. |
| `/models` catalog | Model ID, reasoning-effort options and context limits | Advertised eligibility/capability. Cross-check only; never fill missing per-response evidence with catalog/request values. |

Pinned source evidence:

- [copilotApiService.ts:511](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/shared/copilotApiService.ts#L511)
  defines `responses(): Promise<Response>` as a pass-through without deserializing
  the body; `:666-711` forwards the POST and returns the raw response. Its logged
  `requestModel` is parsed from the **request** and is not served-model evidence.
- [codexProxyService.ts:351](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexProxyService.ts#L351)
  reads upstream headers; `:355` forwards only content-type in the response
  headers, and `:364-402` reads/passes the response stream. Capture metadata at
  the upstream fetch boundary, not just at the native loopback response.
- [ThreadTokenUsage.ts:11](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadTokenUsage.ts#L11)
  defines `modelContextWindow: number | null`;
  [ThreadTokenUsageUpdatedNotification.ts:11](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadTokenUsageUpdatedNotification.ts#L11)
  supplies thread/turn correlation. `TokenUsageBreakdown.ts:9` has token counts,
  not served model or applied effort.
- [codexMapAppServerEvents.ts:523](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexMapAppServerEvents.ts#L523)
  copies the selected model ID and at `:527` forwards SDK `modelContextWindow`.
  `protocol/generated/v2/Turn.ts:14-49` has status/items/timestamps, no definitive
  served-model/applied-effort fields.
- Existing `batch-runner/ghcp_ahp_wire_capture.py:487-519` recognizes response
  `model` and `reasoning.effort`, but deliberately labels them response-reported
  **candidates**, with `independent_attestation=false` and
  `proven_for_live_gate=false`. This implementation does not change those verdicts.
- [OpenAI Responses reference](https://developers.openai.com/api/reference/resources/responses/)
  was consulted to distinguish response metadata from request/configuration and
  usage. Its general API schema is not a guarantee of GHCP CAPI behavior.

### Can the gate stop the task if first-turn evidence is absent?

**Yes, as a fail-closed state machine; not as proof that the fields will exist.**
Keep the first response's HTTP status/request-stream/response-ID correlation and
the SDK thread/turn identity. Require exact Sol/Max/integer 1,000,000 values only
from an explicitly approved evidence source. A mismatch can stop immediately;
absence is determined by the first response terminal event plus the existing
bounded metadata deadline, not by accepting request echoes or waiting forever.

Hold all tool execution, the next turn and grading until this check succeeds.
Missing/conflicting/malformed/unmatched metadata, a truncated stream or a deadline
must cancel the owned task and record the refusal without retry, model fallback
or a second paid attempt. If required metadata depends on tool progress, stop
rather than allowing tools through an unverified state.

This rule could stop **every** task on the current service: no authoritative
server-applied effort/context contract has been found, and even response.model
availability is unmeasured. Accepting response-reported candidates or SDK context
as sufficient experiment evidence would require a separate owner decision, not
an engineering relaxation. No first-turn/paid gate rule is implemented by this
authentication-only change, and no one-turn run is authorized or executed here.

## Before any future dispatch

1. Separate authorization to publish this local commit and register the new
   workflow on the default branch is needed. This change does not push, open a
   PR, merge or dispatch.
2. The owner must resolve patched GHCP versus default policy. The corresponding
   runtime/contract must be connected and reviewed without weakening current
   readback/native/admission guards. This smoke does not activate the patch.
3. Use the existing environment secret. Only the owner may inspect/replace it if
   entitlement, permission, expiry or organization/SSO policy requires action.
4. A separately authorized hosted zero-turn dispatch must validate the real
   runtime and publication path. Local fake-server tests are not that validation.
