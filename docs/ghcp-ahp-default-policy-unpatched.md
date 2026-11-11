# Unpatched default-policy zero-turn observation (choice 3)

This separate profile, `default_policy_unpatched`, does not replace choice 1,
claim read-only operation, select an owner option, or authorize a first turn.
`execution_allowed=false` remains unconditional.

The leader authorized one green-push-gated authenticated zero-turn dispatch,
not inference, paid tasks or grading. The question is whether the original
pinned product creates a native thread under its default permission policy.
Missing/contradictory evidence, network=true, sandbox-off, broad writable roots,
any turn/tool event or inference HTTP request refuses. The single dispatch
stops on its first failure; 401/403 is not retried.

## Separate contracts, not a relaxed read-only predicate

| Profile | Product | Permission configuration supplied | Observation verdict |
| --- | --- | --- | --- |
| Existing choice 1 | Original plus the unchanged two-patch set | Existing five `codex.` keys, untrusted/read-only | Existing `authenticated_zero_turn_only` and `read_only_except_job_tmpdir` logic unchanged |
| `default_policy_unpatched` | Original pinned vendor release, no overlay | Empty config `{}`; no preset or raw permission axes supplied | `default_policy_unpatched_zero_turn_only` / `default_workspace_policy_observed`; never a read-only verdict |

These are product/permission-profile conditions, not an isolated performance
intervention. No quality, speed, cost or causal comparison is made. Fixtures
test the contract before the single real metadata/session observation; they do
not substitute for native applied-value evidence.

Source defaults are in pinned VS Code
`2c33b50b16c472efe58357d1d2a8a5414bc23fbf`:

- `codexAgent.ts:554-565`: approval on-request, sandbox workspace-write,
  network false, web disabled, permission preset default; default effort medium.
- `codexAgent.ts:9254-9279` and `codexSessionConfigKeys.ts:132-165`: the empty
  config resolves to the actual default preset. Resolver values are retained as
  staged/config observations; absent fields remain `not_reported`.
- `codexLaunchConfig.ts:25-64`: `vscode-workspace` inherits the restricted runtime
  profile, with workspace/TMPDIR writes and network disabled; read-only and
  network-enabled profile names are distinct and rejected by this profile.
- `codexAgent.ts:6108-6175`: the host produces native approval/permission params.
  We do not rewrite them. Explicit Sol/Max/1M model initialization and native
  launch args remain separate from permission config. Initial native effort
  must actually report max; medium is not silently accepted as Max or used to
  fill a missing result.

Prewarm ordering need not be changed for an empty policy config: this experiment
observes the defaults. Original sources, both patches, SDK/CLI/VS Code pins and
historical workflow hashes remain unchanged.

## Original-byte and process binding

The server release archive remains SHA256
`65a713d95bb598310ad86db4daea28f9c3f9687b59ee9e57b3e7060a810bf916`.
Its original `out/vs/platform/agentHost/node/agentHostMain.js` gives SHA256
`bf1c335134a145a8c2af6e00975c3320ef1ad21f542f6c07fdf1361e3cf94780`.
This is not the patched bundle `5006baa5…`.

Preparation compares the installed entry to that original archive member/hash.
The existing fork guard still verifies the original Node, bootstrap, parent
bundles and argv. In the exact Agent Host child, a Node loader hook measures
bytes returned by the real loader, plus disk-before/after hashes, and returns
the bytes untouched. Contract/challenge, observer code hash, parent/child PID
and native thread's observer process must agree. Missing/mismatched/synthetic
or patched load evidence refuses before authentication. The inert loader unit
fixture's `synthetic=true` cannot pass the live verifier.

Native `thread/start` gets a separate exact predicate only for the validated new
profile: Sol / vscode-proxy / on-request / vscode-workspace / user reviewer,
no legacy sandbox argument, web disabled, unchanged model/MCP restrictions.
The original read-only predicate remains the default. Unknown profiles,
inherited selector variables, mixed patched/default contracts and read-only
parameters in this profile refuse. RPC/HTTP allowlists are unchanged.

## Applied policy and privacy

Receipts retain the native sandbox object, approval, active permission profile,
network flag and raw writable-root list, subject to the existing redactor.
Admission requires `workspaceWrite`, `on-request`, `vscode-workspace`,
network=false, no implicit broad `/tmp` writes, and explicitly reported roots
restricted to the owned job workspace/TMPDIR. Symlinks, TMPDIR replacement, duplicate
or unbounded roots and missing roots refuse. An empty explicit list is not
interpreted as read-only: the default profile still has workspace semantics.
No sandbox or network enforcement is turned off.

The existing redactor hides cwd anywhere it appears, including writable roots.
It is not weakened. Before redaction, the live observer compares real path
components and directory identity; path hashes and device/inode/owner bind the
masked workspace root. Receipt display keeps `[REDACTED]`, never a fabricated
replacement path. TMPDIR retains its owned-directory binding. Served model,
context and web remain deferred, never counted as passes; later paid work still
requires actual first-turn evidence.

## Routing and files

The registered `agentic-v2-ghcp-sol-gate.yml` on the existing branch accepts:

```text
dry_run=true
execute_paid=false
execution_adapter=ahp-draft
connection_only=false
capability_only=false
authenticated_zero_turn=true
default_policy_unpatched=true
```

The separate `ahp-default-policy-zero-turn` job uses Ubuntu 24.04, environment
`ghcp-sol-gate`, contents/actions read only, timeout 10 minutes. It verifies the
unique same-HEAD green push, downloads only pinned original public bytes, uses
the unchanged exact-bwrap AppArmor-first preparation/cleanup, then exposes
`COPILOT_GITHUB_TOKEN` solely in the auth step's environment. No patched build
artifact is downloaded, no credential is put in argv or files, and no retry is
added. Invalid mixed inputs fail before runtime/auth; all choice-1, first-turn,
paid, fixed-five and grader jobs explicitly exclude the new selector.

Evidence is rooted in a directory named `default_policy_unpatched` and uploaded
as `ghcp-ahp-default-policy-unpatched-<run>-<attempt>`. Separate policy, handshake,
JSON summary and Markdown names cannot overwrite choice-1 files. The chain
re-derives assessment from wire/RPC evidence and checks profile labels, false
execution flags, hashes and the exact Markdown projection.

## Choice-1 remaining checks — investigation only, no implementation

1. AHP control-plane connection/auth/session/native-thread/subscribe/dispose can
   be checked zero-turn; run 42964958467 already did so. Current probe WebSocket
   and exchange are at `ghcp_ahp_probe.py:705,734`.
2. The real task controller's turn/stream/capture end-to-end path is not proved
   by that handshake. `ghcp_ahp_connection.py:167` sends the first turn and `:276`
   requires its response evidence. This path remains unexecuted and locked.
3. Job TMPDIR path, owner, canonical identity and reported writable scope can
   be checked zero-turn (`ghcp_ahp_wire_preload.cjs:242,260`); the pinned host
   creates/exports it at `codexAgent.ts:2687-2690`. Choice-1 evidence has this.
4. An actual native tool's write and collected deliverable are different proof:
   unchanged zero-turn guards reject work at preload `:375,414`. This path needs
   an authorized first/tool turn; a separately approved model-free sandbox
   canary could test filesystem access, not model generation.
5. Neither control-plane nor path-only evidence opens paid AHP activation,
   proves server-internal caps, or supplies served Sol/Max/1M/web response fields.

Official protocol reference, not a replacement for the pinned schema:
https://developers.openai.com/codex/app-server/ distinguishes thread creation
from turn execution and usage events. No newer example model/policy substitutes
for the exact pins above.
