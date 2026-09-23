# Latest task result

## Explicit immutable HF originals intake

The existing single-cell intake now accepts an explicit `hf_originals` route.
`github_draft` remains the default; a GitHub refusal never selects HF
automatically. This independent branch starts at exact main
`9cb1c0d84f299f610ec98c90f3bac9ff9cbbdc75`. The implementation and tests were
committed at `fbd038173aa36d67bda8d0aad3f3ecb35aa7c8af` before validation.
Later completion-record edits are not a test run at the final head.

This is byte-preserving input transport, not a new experiment condition,
credential route for models, scheduler or current-access observation. No real
original payload, HF token or data API was used in this task.

### Fixed origins and acceptance boundary

[The intake](../../batch-runner/codex_ci_input_intake.py) obtains the four
allowlisted roles and byte pins from the existing bundle/registered-contract
reader. Repository, revision and member locators are not caller inputs.

| Logical source | Immutable origin | Byte binding |
| --- | --- | --- |
| Normalized original parquet | `openai/gdpval`, revision `11e7900cdcac61bc4daf59e65feb238acda98fbf`, registered parquet member | 1,913,489 bytes; SHA256 `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` |
| Exactly two declared references | The same original dataset/revision; members and digests derived from the genuine registered contract | Each declared SHA256 must match; no extra file is fetched |
| Canonical schema-4 `deliverable_only` Step0 | Only `step0_needs_files_manifest.json` from the existing tracked exp033 submission/result target, revision `6c7e07ee7365f145dfcf898263365b5c8c97b224` | 218,405 bytes; SHA256 `463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512` |

Before implementation, local metadata inspection reconciled the retained
`source_handoff -> step0_upstream_url` with the current tracked parent profile.
The repository-name SHA256 is
`88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf`;
the recorded revision, member, size and digest all matched. Operational
locators remain private. No original bytes were opened or rehashed for that
reconciliation. The submission/result repository supplies only this already
canonical manifest, never its stripped/result parquet. Its current privacy or
access is not inferred from configuration, and no publication policy changes.

After bounded reads, the existing producer's logical manifest and deterministic
USTAR serializer reconstruct the archive. It must match both the four source
identities and the external archive expectation: 2,519,040 bytes, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Only then can the unchanged `codex_ci_input_bundle.import_bundle` publish the
`original.parquet`, `reference-only/...` and `step0-manifest.json` roles under
a new absent private root. Its genuine installed-input reader must pass before
the ready marker is written. The single-cell adapter's existing
`--resume --check-inputs` gate still follows that import.

No-clobber reservations survive failed attempts. Neither partial nor complete
destinations are silently adopted. Missing credentials/files, changed
identities, wrong target/revision redirects, malformed/oversized responses,
digest mismatch and rejected canonical inputs fail closed. HF selection rejects
GitHub release/asset IDs, including in plan mode. No Step0 regeneration,
substitute input or public/private rehosting is implemented.

### Credential, time and publication controls

The mandatory read-only extreme-reasoner decision was
`APPROVE-WITH-CONDITIONS` before any workflow edit. Its fixed-origin,
credential-isolation, bounded-transfer, offline-verification and no-fallback
conditions are implemented. It is a design decision, not final-head approval
or authority to run the workflow.

The declared `huggingface-hub==1.24.0` URL/header/stream helpers are reused.
Fixed HTTPS origins use explicit `HF_TOKEN` headers; the adapter does not ask
for a cached token or populate a Hub cache. Redirects are bounded to three hops
after the fixed source request. Only the same immutable Hub/cache path or
HF-owned CDN hosts are admitted, and a CDN receives no bearer header.
Streaming uses 64-KiB chunks with per-file/aggregate bounds and shared deadline
checks; library retries are disabled. Non-success response bodies are not read.
SDK HTTP/debug logging is suppressed during fetch. CLI failures expose only a
closed logical role and an actually received numeric HTTP status, or null when
no response was received; no exception body, URL, token or private path is logged.

Only the explicitly selected input step receives its existing credential.
`HF_TOKEN` and the GitHub input token are not supplied to native/model steps.
The intake temporarily changes both the environment and SDK-captured HF offline
flag only for the deliberate fetch. Serialization/import/local verification
run offline with input tokens removed from their environment. The workflow
also unsets input tokens before the existing installed-input check. Plan-only
mode does not read a token, fetch inputs or request a model.

GitHub remains `contents:read` with the existing effective OIDC scope. Source,
ref, rerun, cell, connection, host and route gates remain. The workflow retains
TERM at 120 seconds, KILL after 5 seconds and a 3-minute intake/check step
ceiling. Its 240-minute job ceiling is setup/cleanup headroom, not model budget.
Each cell still has 180 cumulative minutes and 30 minutes per attempt, with
A at most four attempts. B/C retain the same continuation/backoff policy;
only C receives host error feedback. GPT-5.4/direct-v1/xhigh, the pinned
Ubuntu/Python/SDK policy, task order, 30-cell denominator and fixed grader are
unchanged. Only the existing validated nonsecret completion envelope can be
uploaded; no source payload, cache or private native state is added to artifacts.

### One focused offline validation

Tested SHA: `fbd038173aa36d67bda8d0aad3f3ecb35aa7c8af`.
`HF_ORIGINALS_PYTHON` named the existing isolated Python 3.10.12 environment
from the retained private handoff; no dependency was installed.

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$HF_ORIGINALS_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_ci_hf_originals.py batch-runner/tests/test_codex_budget_pilot_ci.py::test_ci_registered_cell_workflow_invocation_contract
```

Result: `71 passed in 3.68s`, exit 0, from one invocation. These are 70 new
HF-route cases and one directly affected existing workflow contract, not the
historical 71-case native-host family. The 3.68 seconds are pytest wall time,
not transport/model latency.

Synthetic provenance suppliers replace only the original byte pins and source
payloads for tiny fixtures. The CLI, fixed-role derivation, Hub URL/header
helpers, canonical serialization/import, current-byte/reference/Step0 readers,
hash checks and no-clobber behavior remain real. The fetch boundary is fake;
one case also exercises the real Hub stream helper with only its HTTP session
replaced. Network, auth, provider and native boundaries are blocked by the
offline fixture. Controlled workflow bash blocks use fake
commands; YAML/OIDC/publication assertions are static, not an Actions run.

Cases cover four immutable roles and original/submission separation, target
and revision drift, each member's digest, canonical archive binding, missing
credentials/hash, default-plan no fetch, contradictory GitHub IDs, no implicit
fallback, token/log isolation, bounded responses/time/redirects, per-role
401/403/404 and no-response context, retained reservations, canonical-reader
failure, and failed intake never opening the OIDC/native gate. The old
reader31/error19/native71 families and full suites were not rerun.

### Separate observations and prior review scopes

The leader reported completed input-check
[35827845408](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35827845408),
job `107073437115`, on `427a03223fb7c70eb8070fff85fdde8bcfcfac0d`.
At 06:42:45 UTC it refused with `github_draft_or_asset_inaccessible`,
`stage=release_metadata`, `http_status=403`, exit 2. Plan creation passed;
download/import and OIDC/native work were not reached. This is actual failed
access, not evidence of token expiry, asset absence or a need for write
permission. It was not retried here. Current HF access is untested.

Original input-check `35821215749`/job `107053260372`, on
`84c18b778d2e9aa1def9d5f7912ac9f03edaee11`, remains a separate grouped-error
exit-2 observation at 05:11:35 UTC. Its HTTP status/stage are unknown. The
owner-account observation of private draft `394272629`, uploaded asset
`582945947`, 2,519,040 bytes and the matching provider digest remains separate
from both CI refusals. The initial HTTP-400/exit-1 upload with lost stderr is
not assigned a retrospective cause or replacement receipt.

The leader's successful native diagnostic `35817078746`, job `107040793256`,
artifact `10731833980`, on `0f0911b435d7f704db8e2f2131a00ade310d5c1f`
remains historical connectivity evidence for that CI diagnostic. Its matching
plan/result settings fingerprint is
`sha256:af46cb5548b7224a3c0117b37a450fced3765efdc4ed2b6c12994376c9462150`.
It reported `connected`, `provider_answered=true`, successful auth, a completed
native turn and a matching final response, with `tools=false` and
`served_model=null`. Thread-total and most-recent-request views each reported
input 10,982, cached/cache-write input 0, output 29 and reasoning output 22;
the views are not summed and 22 is part of 29. The observed context window was
258,400. SDK/companion 0.147.0 and diagnostic defaults are not pilot xhigh
execution. HTTP count, invoice, recovery, tool/file work and graded quality
remain unestablished. No diagnostic, staging or access observation was repeated.

Prior #659 FINAL-APPROVE `5287940874` at
`3659287caf89c013818d052b54524723e30ac6f3`, with all nine checks reported
passed by the leader, covers only the local completion reader/integration.
Its `31 passed in 36.01s` evidence remains at
`deefb34ad684a00494ef689db86f4c461dbca004`. The
[immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/3659287caf89c013818d052b54524723e30ac6f3/tasks/LATEST_TASK_RESULT/README.md)
preserves its full reader behavior and earlier intake, safe-HTTP-context and
CI-ceiling review/test scopes. None is approval of this new transport head.
New immutable-head review and ordinary automatic checks remain required.

### Remaining live work

After review/final checks, the leader may direct a separate model-free
`input_check` on its reviewed main SHA. Its intended explicit input set is
`input_transport=hf_originals`, `execute=false`, `input_check=true`, canonical
cell `02aa1805-c658-4069-8a6a-02dec146063a_A_r1`, the external bundle SHA above,
and empty GitHub release/asset IDs. Nothing was dispatched here.

Live input acceptance, ordered execution of all 30 cells, cross-run admission
deduplication and fixed grading remain unfinished. The old NAS campaign and
its sealed source/pending cells, the reserved CI campaign identity, original
bytes, deadlines and previous outputs remain untouched. Standing spend
authority is unchanged; this code/offline task neither consumes model
authority nor introduces another budget-approval wait.

`experiment-design` kept inputs and controls fixed. `experiment-report-en`
and `im-not-ai-en` kept synthetic checks, historical observations and unknown
current access separate in these bounded English records.
