# Patched GHCP runtime evidence: implemented, activation still locked

This is the owner's option (1) preparation only. A successful build is not permission to authenticate, start a session, send a turn, or run the five-question gate. The original source/archive/SDK pins and experiment seals remain unchanged. No release or runtime hash is silently replaced with a measured value.

The immutable base is VS Code `2c33b50b16c472efe58357d1d2a8a5414bc23fbf` plus the original manifest. The overlay is exactly the three-file patch with SHA256 `a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb`. The candidate workflow has no automatic or dispatch trigger; it is a reusable build-only draft that refuses an absent owner decision. It does not import any secrets or the protected environment. Existing vendor pins, sealed grading values, historical workflow hashes and policy/turn/inference refusal predicates are unchanged.

## Why rebuilding is required

The vendor server archive executes `out/vs/platform/agentHost/node/agentHostMain.js`, not the source files in the probe's quotation archive. Applying the patch to quoted source alone cannot fix runtime behavior and must never produce an "applied" receipt. The pinned source's `build/next/index.ts:140` includes this entry in the server build; :457 bundles from TypeScript. The exact Node development version is 24.22.1 from `.nvmrc`.

The draft builds a separate candidate and calls `ghcp_ahp_patched_runtime.py build-receipt`. The v2 build receipt checks the actual three patched source files and bundle and records `patched_ghcp=true`, `evidence_kind=source-build-no-execution`, `load_evidence_sha256=null`, `admission_allowed=false`, `execution_allowed=false`. A build receipt is deliberately invalid as runtime-load evidence. Its lockfile installs suppress dependency lifecycle scripts; missing generated types or build tools must fail. Needed dependency preparation, packaged-product compatibility, module/assets loading and license/distribution review are open items, not reasons to remove checks.

## Implemented loading boundary

1. `stage-runtime` verifies the original manifest, server archive, Node, bootstrap, server parent and original bundle. It clones the base into a **new non-overlapping directory**, replaces only `out/vs/platform/agentHost/node/agentHostMain.js`, and verifies that the base stayed unchanged. Existing targets, symlinks, special files, archive drift and an unchanged vendor bundle are refused. Its receipt says `staged_not_loaded`; it never opens admission.
2. `wire_capture.install(..., patched_request=...)` requires session-only/model-free mode, verifies the external build-receipt SHA and actual candidate bytes, and binds an immutable per-run contract to the existing fork contract. Its fresh challenge, Node/hash, bundle/hash and observer hash are not inferred from requested policy values.
3. The original exact fork path/argv/parent/socket checks run first. The observer then passes only the validated patched contract to that child and records the real child PID. Conflicting inherited patched metadata is refused; no arbitrary exec argument or fork is added.
4. `ghcp_ahp_patched_runtime.cjs` installs a synchronous Node `registerHooks` load hook **only in the exact Agent Host child**. It hashes the bytes returned by `nextLoad`, verifies the exact module URL and disk bytes before/after loading, and returns the original loader result unchanged. Unsupported hooks, unavailable source, rewritten source, aliases or mismatches throw before the unverified module can be returned. The evidence says `node_load_hook_before_evaluation`, not that initialization or policy application succeeded.
5. Before any authentication/session RPC, `verify_live_ready` requires exactly one load event, the matching guarded fork/observer PID chain and challenge, and matching build/contract/bundle/Node hashes. After process shutdown, collection checks the bytes again and exports the raw build receipt, contract and load evidence with their SHA256 values. Upstream source quotations are explicitly labeled base-only.

These are local integrity checks bound to a reviewed build receipt, not remote attestation against a compromised runner. A staged file hash is insufficient; an actual Node loader event is mandatory. A successful load event is still not served-model or native-policy proof.

## Result, receipt and summary contracts

| Artifact | Role |
|---|---|
| `wire-capture.json` | Result, including the guarded fork and observer records |
| `probe.json` | Enclosing probe receipt |
| `summary.json`, stdout and `summary.md` | Structured and human summaries read back from the validated persisted chain |
| `handshake.json`, `thread-policy.json` | Authenticated/session diagnostics with the same provenance |
| `management-init.json` | Staged management diagnostics, labeled but never native-policy proof |
| `patched-build-receipt.json`, `patched-runtime-contract.json`, `patched-load-evidence.json` | Raw hash-linked evidence, not source echoes |

Measured patched artifacts require `patched_ghcp`, `patch_sha256`, `build_receipt_sha256`, `loaded_bundle_sha256`, `load_evidence_sha256`, `runtime_contract_sha256`, `runtime_load_status`, `runtime_evidence_synthetic` and `execution_allowed`. Missing fields, type substitutions, inconsistent hashes or any execution/admission opt-in are rejected. The consumer does not restore a dropped field from another artifact. Even changing the same hash in every result cannot repair a mismatched raw evidence file.

Failure before measurement carries the patch identity, `runtime_load_status=unmeasured_refused`, null load evidence and `execution_allowed=false`; it is not a valid measured receipt. Fixture evidence retains `runtime_evidence_synthetic=true` and cannot become live evidence by editing a result's synthetic flag. The unpatched path keeps its existing schemas and behavior; a request for patched provenance never falls back to it.

## Public activation remains closed

`ghcp_ahp_probe.py` accepts the paired `--patched-build-receipt` and `--patched-build-receipt-sha256` inputs, but both its public and internal entry call `require_activation`, which **unconditionally refuses pending the owner decision**. No environment variable or receipt can open it. This happens before credential reading, socket/session work or process startup. All new build, staging, measurement and report schemas keep `execution_allowed=false`; no paid or five-question path is introduced.

After option (1), the remaining Actions work is a complete reviewed build/inventory, candidate staging using that exact build receipt, an explicit reviewed activation change for zero-turn only, then a separately authorized single zero-turn run on ubuntu-24.04. That run must show the expected compiled bundle hash in the loader event and an intact artifact chain before its native policy observations can be evaluated. No such run has been made by this change. A different emitted dependency/asset requires inventory review, not a wildcard copy or replacement of the vendor pins.

The experiment-design boundary is explicit: the new condition is **Patched GHCP**, not unmodified GHCP. Local fixture loads measure Node byte consumption and contract propagation, not benchmark quality, serving identity, Max/context enforcement or billing. Existing metadata allowlists, management readback, single-use claim, policy predicates, zero-turn and inference blocks remain in force.
