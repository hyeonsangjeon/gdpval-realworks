# Zero-turn scope and deferred first-turn proof

Leader engineering decision: 2026-11-11 14:0x KST. This is not owner approval
for a paid run, a one-turn dispatch, a product patch, or changed default policy.
The two frozen patches, bundle, pins and historical workflow hashes are unchanged.
`execution_allowed=false`, the patched-host activation lock, zero-turn RPC and
inference boundaries, and the disabled AHP paid adapter remain in force.

## Decision record before execution

The question is whether one authenticated session/native thread satisfies the
leader's narrowly defined filesystem scope, with zero inference. Passing admits
only that completed inspection. Failure ends the one authorized attempt; neither
result authorizes a model turn. This is a contract check, not a quality/cost or
causal benchmark. No repeated model measurement or variance claim is made.

The changed axis is our admission/measurement contract, not the product's
permission profile. Synthetic fixtures exercise pass and refusal cases before
the single Actions run. They are labeled synthetic and cannot become live proof.
Measurements are response fields, path identities and request counts, never
provider-capacity measurements or a billing receipt. Known limitation: the SDK
returns a compatibility sandbox enum, not its complete internal filesystem graph.

## Filesystem criterion

The observer measures the actual native spawn environment's TMPDIR, TMP and TEMP
and requires their equality. TMPDIR must be a canonical, owned, direct child of
the verified invocation's `state_root/tmp`. At the thread reply it remeasures
the directory's device/inode/owner and every path component. Symlinks, `..`,
replacement, missing measurements, ancestor/descendant roots and workspace roots
refuse. A `workspaceWrite` response must also exclude broad `/tmp` writes;
implicit TMPDIR writes cannot masquerade as an empty read-only root list.

`writableRoots` must be explicitly present. Exactly one root must match the
measured native TMPDIR identity and normalized path. An explicitly empty list
is read-only. Missing roots are **not** turned into an empty list. Network must
be false, approval untrusted, and active profile `vscode-workspace-read-only`.
The original sandbox name and root list remain in the receipt (subject only to
the existing credential/cwd redaction). The verdict is separate:
`read_only_except_job_tmpdir` or `readOnly`.

This changes only authenticated zero-turn assessment. The full-field
`matches_all` predicate remains intact. Unknown receipt schemas, synthetic
evidence and any attempt to set execution/launch/gate/connection permissions
true still refuse. The scoped policy, handshake, JSON summary and Markdown
summary must agree and are reconstructed from the hash-bound wire observations.

## Three deferred fields are not three passed fields

`served_model`, `context_window` and `web_search` retain their actual observation
(normally `not_reported`) with verdict `deferred_to_first_turn`. They are not
counted as matches. `settings_verified=false`, `first_turn_required=true`, and
`admission_scope=authenticated_zero_turn_only` accompany the decision.
Initial native model/effort are still required to be gpt-5.6-sol/max and are
never relabeled as served model or final effort.

## First-turn guard, not exercised by this change

`ghcp_ahp_client.SessionClient._action` checks the shared guard before accepting
its own first `chat/turnComplete`; `ConnectionSession` uses the same hook.
Missing/mismatched evidence stops the client, cancels the
active turn, disposes the session and terminates the owned host; there is no
second prompt or retry. It reads the live, bounded observer files through
`ConnectionPort.first_turn_evidence`, not usage.model or selected config echoes.

The exact required response-side observations are:

| Requirement | Evidence |
| --- | --- |
| Served model gpt-5.6-sol | completed CAPI response `model` |
| Effort max | completed CAPI response `reasoning.effort` |
| Context 1000000 | matching native thread/turn `tokenUsage.modelContextWindow` |
| Web search unused | complete response's explicit `output[*].type` inventory; web_search_call must be absent |

An absent output array is unreported, never zero web use. Unknown output item
kinds refuse; a web_search_call refuses. The response must have completed status,
one correlated native turn and one provider request, with a complete/error-free
capture. These are runtime reports, not independent attestation of model internals.
No guarantee that GHCP supplies all fields is claimed.

The paid AHP job invokes `require_verified_connection` before task inputs or any
task process. It now also requires this first-turn receipt, rechecks its actual
wire capture, and rejects synthetic evidence. The existing unconditional
`connection_served_attestation_unavailable` / `ahp_paid_contract_unverified`
locks remain; **no paid AHP task stream is enabled**. The task client's shared
guard checks each task's own first turn, not the connection observations.
Its subsequent `send_turn` also refuses without verified first-turn evidence.
The legacy Copilot CLI path is
not selected, changed or used for this Codex-harness work.

## Authorized run boundary

After offline tests and all five push jobs are green at the exact new SHA, use
the registered `agentic-v2-ghcp-sol-gate.yml` on this branch with
`dry_run=true`, `execute_paid=false`, `execution_adapter=ahp-draft`,
`connection_only=false`, `capability_only=false`, `authenticated_zero_turn=true`.
Exactly one dispatch; stop on any failure, including 401/403. No secret value is
read locally. No native host, SDK, bwrap, build or benchmark runs on the NAS.
