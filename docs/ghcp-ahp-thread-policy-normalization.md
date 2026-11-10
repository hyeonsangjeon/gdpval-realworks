# Pinned GHCP Codex thread-policy normalization

Source audit and offline fixtures, 2026-11-10 UTC / 2026-11-11 KST.
No policy change, runtime activation, dispatch, authentication or model call is
authorized by this document. `execution_allowed=false` and all existing guards
remain unchanged.

## What actually refused run 42862054915

The observer rejected an **outgoing** native `thread/start` before forwarding it;
this was not a Codex SDK/server response that changed requested settings.
`ghcp_ahp_wire_preload.cjs:220-247` enforces the request contract. The two rejected
attempts forwarded zero native requests and produced zero native thread replies.
The run's AHP authentication succeeded; its two metadata GETs were HTTP 200.

| Field | Requested | Rejected outgoing request | Native applied observation |
| --- | --- | --- | --- |
| approvalPolicy | untrusted | on-request | not_reported |
| permissions | vscode-workspace-read-only | vscode-workspace | not_reported |
| legacy sandbox | omitted with a named profile | omitted | not_reported |

Omitting `sandbox` is normal when `permissions` names a profile. The pinned
[`ThreadStartParams.ts:38`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadStartParams.ts#L38)
declares the two fields mutually exclusive. Adding both is not a fix.

The Actions failed-step log exposes exit 2, not the policy values. The detailed
evidence is in `ghcp-ahp-zero-turn-42862054915-1`: `handshake.json`,
`wire-capture.json`, `thread-policy.json` and `management-init.json`. The management
readback retained the five exact requested keys with no permissions preset, and
explicitly labels itself staged/resolver evidence, not thread-applied evidence.

## Exact runtime identity and source path

- Actual Agent Host: VS Code **1.144.0**, commit
  `2c33b50b16c472efe58357d1d2a8a5414bc23fbf`; source archive SHA256
  `cb7fb5b3b219585a63ec8e3dbc66bab135d2fe900b0541e73862da5302c24206`.
- Actual native Codex package **0.163.0-linux-x64**, package layout version
  **0.163.0**, selected `vendor/x86_64-unknown-linux-musl/bin/codex`; measured
  binary SHA256 `399ff69c431c066e40de318fba45c2b07f45a76b19939d247ee4828fc70c4215`.
- Copilot CLI **1.0.103** was version-checked in the separate offline CI job. It
  is not the producer of these Codex thread parameters. Chat **0.72.0** is the
  pinned source's `extensions/copilot/package.json` version, not evidence that a
  Chat extension process normalized this headless request.
- The source package declares Copilot SDK `1.0.27-unstable.40031404408.gba6c003`;
  do not conflate that dependency, the standalone Copilot CLI, and Codex 0.163.0.

All source references below use that exact VS Code commit:

1. [`codexAgent.ts:9254`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L9254),
   `resolveChatConfig`: removes the three permission keys and reapplies
   `migrateCodexPermissionValues(params.config, defaults)` at 9273-9279. A default
   preset materialized by generic schema validation is deliberately not copied
   over a legacy read-only config.
2. [`codexAgent.ts:2002`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L2002),
   `_resolveSessionPermissions`: reads raw stored config, migrates it, then calls
   `resolveCodexPermissions`. Defaults at 556-557 are on-request/workspace-write.
3. [`codexSessionConfigKeys.ts:132`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexSessionConfigKeys.ts#L132),
   `migrateCodexPermissionValues`: explicit preset wins; read-only raw axes are
   preserved at 148-152; other nonmatching axes snap to the sandbox's preset.
   `resolveCodexPermissionsPreset` is at 29 and `resolveCodexPermissions` at 85.
4. [`codexLaunchConfig.ts:56`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexLaunchConfig.ts#L56),
   `codexPermissionProfile`: sandbox/network axes become an exact native profile
   name. `_permissionProfile` in `codexAgent.ts:2011` supplies the network flag.
5. [`codexAgent.ts:6085`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L6085),
   `_materialize`: reads settings at 6108/6113, builds the profile at 6115, and
   sends `approvalPolicy`, `permissions` and `approvalsReviewer` at 6162-6175.

The causal ordering is still the known prewarm-before-published-state path:
`AgentService._createSession` resolves into a local variable at 5940, awaits
provider creation at 5949, then publishes `state.config` at 6055. Provider chat
creation schedules prewarm at `codexAgent.ts:5227`; `_schedulePrewarm:6274` calls
materialization at 6294. `AgentConfigurationService.getChatConfigValues:470-474`
returns undefined while that session state/config is absent. Undefined values
normalize to the exact on-request/vscode-workspace pair observed in this run.
The run does not capture an instantaneous raw config-store snapshot; source order
and the offline reproduction must not be presented as a native settings reply.

## Closed value sets and exact Linux mapping

Host approval axes: `never`, `on-request`, `untrusted` (narrower at 53, schema
`codexAgent.ts:419`). Sandbox axes: `read-only`, `workspace-write`,
`danger-full-access` (narrower at 64, schema `codexAgent.ts:438`). Public presets:
`default`, `auto-review`, `full-access` (common `codexSessionConfigKeys.ts:34-37`).
Unsupported strings are not aliases: the host falls back to defaults; our gate
continues to reject the resulting mismatch.

| Raw/preset input | Normalized approval / sandbox | Native permissions | Reviewer |
| --- | --- | --- | --- |
| No preset; any allowed approval + read-only | same approval / read-only | vscode-workspace-read-only | user |
| No preset; any allowed approval + workspace-write | on-request / workspace-write | vscode-workspace; network=true selects vscode-workspace-network | user |
| No preset; any allowed approval + danger-full-access | never / danger-full-access | :danger-full-access | user |
| Explicit default or auto-review, even with conflicting raw read-only axes | on-request / workspace-write | same workspace profiles as above | user / auto_review |
| Explicit full-access | never / danger-full-access | :danger-full-access | user |

Read-only ignores a true network flag when choosing the profile: its profile
inherits network=false. Full access ignores a false flag by selecting the
unrestricted built-in profile. The migration returns only permission keys; real
callers preserve unrelated network/web-search/model fields separately.

The pinned generated SDK `AskForApproval.ts:9` also permits a granular object;
the GHCP string-axis narrowing/schema does **not** offer it. This is not a usable
alias or a new approved gate input. SDK response acceptance is unmeasured here.
The current [official approval documentation](https://developers.openai.com/codex/agent-approvals-security)
describes newer handling/retirement of explicit `untrusted`; that latest guidance
does not establish the behavior of this fixed 0.163.0 package or explain a
request stopped before reaching it.

## Recommended combination and isolation limits

Keep the original closest supported combination, **without any preset**:
`codex.approvalPolicy=untrusted`, `codex.sandboxMode=read-only`,
`codex.networkAccessEnabled=false`, `codex.webSearchMode=disabled`,
`codex.modelReasoningEffort=max`; explicit Sol/Max/1M model settings unchanged.
Once the session config is visible, the pure host resolver preserves this pair
and produces `permissions=vscode-workspace-read-only`, with no legacy `sandbox`
field. This establishes host normalization support, not native live acceptance.

No different input combination can fix the publication-order race while keeping
the present exact request/readback/native guards. Accepting on-request/workspace
defaults would change the experiment's approval/write condition. OS isolation
cannot make those strings equal to untrusted/read-only or prove SDK application.
Do not silently substitute a preset, never, on-request, or a permission alias.

Even the intended Linux profile is **not globally read-only**:
`codexPermissionProfileOverrides:39-52` inherits `vscode-runtime` (network=false)
through `vscode-workspace`, then changes workspace roots from write to read.
`codexWorkspaceFileSystemPermissions:25-32` still grants `:tmpdir=write`, minimal
reads, and protects `.git/.agents/.codex` as read-only. This is useful bounded
filesystem policy, not proof that every host tool is covered by it.

This inheritance conclusion is also supported by the matching Codex release
source, tag `rust-v0.163.0`, commit `83086188ae0614bd882818ff1aa23f3194962012`:
[`permissions_toml.rs:158`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/config/src/permissions_toml.rs#L158)
`merge_permission_profiles` merges parent then child, and
[`merge.rs:139`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/config/src/merge.rs#L139)
recurses only into keys present in the child. The child workspace override does
not remove the parent's tmpdir or network entries. This is source-level behavior,
not an observed filesystem write or a native thread readback in the failed run.

The zero-turn observer/kernel namespace already prevents tools, inference and
external host egress except the two metadata GETs. For a future tool-enabled gate,
retain a separate tool/turn budget and approval boundary, read-only input/sealed
mounts, task-owned limited scratch/output mounts, isolated/quota-bound temp space,
no host credential mounts, and tool/host network namespaces. Any future model
transport allowance must be separate from tool egress, not general internet.
Host-owned dynamic tools can execute in-process (`codexAgent._handleDynamicToolCallRpc:3031`,
`host.executeTool:3088`), so the Codex child profile alone is not a whole-VM proof.
No isolation implementation or filesystem/network canary was run on NAS here.

## Offline verification and scope

`tests/fixtures/ghcp_ahp_permission_sources.json` contains exact pure-function
excerpts, extracted after matching the source archive, full source-file hashes
and excerpt hashes. The fixture evaluates only those functions in a VM without
process/require/fetch, using built-in TypeScript syntax stripping; this is not a
VS Code build, full module typecheck or vendor host execution.

`test_ghcp_ahp_permission_normalization.py` covers 90 input rows, migration
idempotence, preset precedence, malformed values, missing-versus-published config,
Linux profile inheritance, and unchanged native guard refusals. Fake stdio
responses are explicitly synthetic and the existing analyzer still refuses live
admission, even when their reported settings match. Source/quote mutation is
refused before evaluation. No model, network authentication or automatic reviewer
is involved. Initial targeted result: **201 passed / 0 failed / 0 skipped**.
The existing 17-file offline contract/guard/authentication suite plus the new
file also passed: **2,108 passed / 0 failed / 0 skipped**, 106.54 seconds. Existing
workflow selections and historical expected hashes were not edited.

## Next single dispatch proposal — not executed

There is **no policy or patched-runtime selector input** on the current workflow.
Repeating these inputs at the unchanged runtime is expected to hit the same
prewarm refusal; do not spend a diagnostic attempt on an unchanged condition.
First obtain the outstanding owner decision and review/publish a runtime that
guarantees config publication before prewarm with the same strict guards (the
pending patched-host route is not activated by this audit). Confirm the PAT is
still valid; it may expire around **2026-11-11 16:50Z**. The owner alone can renew
`ghcp-sol-gate/COPILOT_GITHUB_TOKEN`; no value or expiry was inspected here.

### 2026-11-11 addendum: authorized zero-turn order verification only

The subsequent leader instruction authorizes fixing the order, publishing the
branch, and making one zero-turn dispatch after green CI. This is **not** an
owner selection of patched GHCP for the five-task/paid experiment. The public
`require_activation()` remains unconditionally locked; `execution_allowed=false`
and all native-request, readback, admission, turn and inference guards remain.

The narrow preparation route reuses the already tested two-patch bundle. It
does not edit either patch, the pin, permission normalization, SDK or sealed
inputs. Its internal ready hook is after `state.config` publication, not a
timer, alias, request rewrite, new preset or retry. Offline tests evaluate the
exact patch's pure ready hook with inert first/second sessions: no prewarm before
publication, one per session after publication, and no restart for duplicate,
disposed or already-materialized sessions. These tests are synthetic, not a
native application report.

The registered gate's `ahp-zero-turn` job now fetches **the unique successful
push run at its exact HEAD**, never branch-latest, failed, rerun or old-SHA
artifacts. Read-only Actions access is confined to that fetch step; the Copilot
credential remains in only the original authentication step. Producer identity,
two-patch manifest (`6d869d65…`), fixed bundle (`5006baa5…`, 5,193,139 bytes), build
receipt, staging copies and the current dispatch identity must all agree. The
same-process Node loader must then measure that bundle before authentication
or session creation. Missing or altered evidence refuses; staged policy is
explicitly `not_reported` as an applied value. Native readback remains the only
candidate evidence for actual thread policy; a catalog or config echo cannot
establish served Sol/Max/1M.

Only the existing two metadata GETs may leave the broker. The host still runs
unprivileged in the loopback-only network/PID namespace, and its session-only
observer refuses turns, tools and inference before forwarding. No authentic
runtime is executed on NAS. The old workflow SHA is tested after an exact,
single-match inverse of this separately tested overlay; its expected value and
the other historical workflow hashes are unchanged. Any dispatch failure,
including 401/403 or native policy mismatch, ends this one-attempt verification.

After those prerequisites, the one-run input proposal is:

```bash
gh workflow run agentic-v2-ghcp-sol-gate.yml \
  --repo hyeonsangjeon/gdpval-realworks \
  --ref leader/ghcp-patched-runtime-receipt-20261106 \
  -f dry_run=true -f execute_paid=false -f execution_adapter=ahp-draft \
  -f connection_only=false -f capability_only=false \
  -f authenticated_zero_turn=true
```

Require exactly one native thread response with `approvalPolicy`, legacy
`sandbox` and `activePermissionProfile.id` recorded independently of request and
resolver echoes. Preserve zero turns/inference and admission=false for missing
served-model/effort/context proof. Stop once on auth, policy, boundary or capture
failure; no retry or promotion to the one-turn/five-task gate.

## License for the copied VS Code function excerpts

The source fixture retains Microsoft's notices. Its excerpts are covered by the
following upstream license from the same pinned source archive:

```text
MIT License

Copyright (c) 2015 - present Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
