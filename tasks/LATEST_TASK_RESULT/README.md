# Latest task result

## PROJECT5-PRIVATE-OUTPUT-SETUP-2248

### Current scope

Add a small, plan-first setup mode on exact source
`9366a3bb6bb2ff768b037f56f6b2e268b172d8b8`. This is code/offline work only:
no live account lookup, metadata check, target creation, upload/download,
credential use, workflow dispatch, model or grader call occurred. The new head
needs leader review and ordinary final-head checks; no CI state was queried or
awaited. It does not inherit an earlier approval.

The only candidate uses the namespace from the fingerprint-validated tracked
`CODEX_TEMPLATE.data.source` and the reserved basename
`gdpval-codex-budget-pilot-ci-20260923`. There is no caller-supplied target or
namespace fallback. Neither the historical exp033 repository nor the original
`openai/gdpval` dataset can be mutated by this mode. Operational locators stay
private; public output carries only the candidate name fingerprint and safe
status metadata.

### Setup contract and limits

`codex_budget_pilot_ci.py --output-target-setup` is a local plan after the real
campaign/canonical-cell/reviewed-source/CI gates. It reads no credential, makes
no request and creates no setup files. Creation additionally requires both
`--create-output-target` and `--setup-state <new-absent-private-directory>`.
Setup refuses inspection, input-check, execute, resume, original-input and
ordinary output/completion arguments. It returns before dispatch or input
admission; it cannot invoke native inference, grading or the cell publisher.

The mandatory extreme-reasoner decision preceded workflow/setup-path edits:
**APPROVE-WITH-CONDITIONS** for the reduced no-marker implementation, not a
live-operation authorization. A later explicitly authorized setup permits only
this closed sequence through the existing bounded HF client:

1. One authenticated account request must return the exact namespace with
   type `user`. Organization membership or another identity is not sufficient.
2. One repository-level candidate lookup, without a revision, must return an
   actual 404. Any existing target, including public or headless, refuses.
3. One dataset creation uses the fixed identity, `private=True` and
   `exist_ok=False`. The returned endpoint/type/repository identity must match.
4. One dataset/main lookup must return the exact identity, literal
   `private=true` and an actual lowercase 40-hex HEAD. No Git SHA, input revision
   or planned future commit is substituted.

A repository-level 404 is a prerequisite, not proof against hidden or concurrent
existence. `exist_ok=False` prevents adoption; a conflict is terminal. The HTTP
guard validates the exact method/host/path/auth and create body before transfer,
rejects redirects, and retains its four-attempt counter across SDK client
recreation. It intercepts SDK retry and credential-cache error handling. Existing
bounds remain 30 seconds/request and 120 seconds overall, with a 130-second
process limit plus five-second kill grace and a three-minute selected step.

A private 0700 directory and 0600 single-link, no-clobber/fsynced unresolved
reservation precede requests and mutation. Current reservation bytes are checked
again at the create boundary. A separate no-clobber private receipt retains
actual request stage/status, creation acknowledgment and observed HEAD. Failed
or ambiguous creation, interrupted response, invalid/missing HEAD or receipt
failure cannot become success or trigger replay, deletion or another name.
No marker initialization is implemented: absent initial HEAD remains unresolved,
even if creation was acknowledged. The manifest/reservation never claims its own
future commit. Local files are not a durable cross-run admission ledger and are
not uploaded by the public completion-artifact step.

Workflow input `output_target_setup` defaults false and is mutually exclusive
with historical inspection, input-check and execute before credentials. Selecting
it is the explicit setup request; any later dispatch still requires separate
leader authorization. Only its step receives the already configured `HF_TOKEN`.
The reversible HF-online scope removes ambient credentials, suppresses debug/
retries and restores offline settings. Input transfer, OIDC/native/model,
grading and cell-output publication remain excluded. Historical target inspection
retains its original fixed target and semantics. Ordinary plan/input/execute
behavior, the public completion schema, publisher PRIVATE/expected-parent/
absent-prefix gates, source pins, dependency manifest, permissions, job ceilings
and pilot/model/grader settings, including the 180/30-minute controls, are
unchanged.

Public setup JSON contains a fixed logical role/name hash, observed privacy/HEAD,
actual HTTP status or null, closed stage/reason/outcome and timestamp. It never
contains a raw locator, body, header, token, URL, payload or private path.
`write_access` and `prefix_readiness` remain `not_established`;
`publication_authorized`, `model_requested` and `grading_launched` remain false.
Creating a target would not by itself approve output publication/inference,
establish all write/prefix checks, preserve CI deliverables or make a cell grade-ready.

### Focused offline validation

Tested SHA: `46d3bd32c3317e0e0cc41b4741c7087dd3584e42`.
The implementation and test bytes in the documentation head remain identical to
this tested commit. One family ran once, using the existing Python 3.10.12,
pytest 9.1.1 and huggingface_hub 1.23.0; no dependency install/resolution ran.

```bash
timeout --signal=TERM --kill-after=5s 300s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_output_setup.py
```

Result: **`78 passed in 58.90s`**, exit 0. This is pytest wall time, not HF or
model latency. CI/source capability, pinned-runtime version metadata, account
identity and HTTP responses are synthetic. The real compiler, CLI gates,
installed SDK, bounded request guard and private byte/no-clobber checks are used;
socket, cached-token, input, native-execution and publisher boundaries are blocked.
No grader is invoked.
Static YAML assertions are not Actions execution or live setup evidence.

Coverage includes no-token/no-network plans; incompatible modes; canonical
source/cell gates; fixed namespace and target; organization/foreign/public/
existing refusal; exact private create body; actual HEAD receipts; null status
without a response; malformed/oversized replies; time/interruption and retry
refusal; reservation races/tampering/hardlinks; unchanged receipts/no replay;
safe output and restored environment. Four existing test files received only
coupled workflow exclusion/token-scope expectation updates. Their families and
all earlier 66/46/71/31/19 families were not rerun. No full suite, live check or
additional semantic audit ran.

### Separate observations and review scopes

The leader supplied completed metadata run `35870090309`, job `107211610516`,
at 13:54:56 UTC on 2026-09-23. The historical target matched name SHA256
`88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf`:
`exact_identity_match=true`, HTTP 200, `private=false`, HEAD
`6c7e07ee7365f145dfcf898263365b5c8c97b224`, `eligible_private_target=false`,
reason `private_output_target_required`, exit 2. Write access was not established;
publication was not authorized and no model was requested. Input transfer,
OIDC and model steps were skipped. This was a successful privacy observation
and intentional refusal, not invalid credentials or failure to fetch. It says
nothing about the new candidate's current existence, privacy or HEAD.

The earlier NAS observation at 11:20:13 UTC made zero HF calls because the
process token/known handoff were unavailable. That remains local unavailability,
not remote refusal. No secret search/transfer or repeated observation occurred.

Leader review `5291537877` and nine passing exact-head checks apply to #665 at
`dc4f1bc2dc6ea59e73612ef89452f7de23f5740c`, included in supplied main. Earlier
review `5290860576` applies to `79c43ca20bac525d7ff77cc3e7a042ec81bdc2a3`.
The original inspection evidence remains `1 failed, 58 passed in 31.61s` at
`faa64ef15fce0e101c3911a092a312563fff2486`, then failed-fixture-only
`1 passed in 1.80s` at `668cdbed6574d0b0b458d87cda9e3ad87a1cbfed`; it is not
a new 59-case result. #664 review `5290860366` and ten applicable passes/deploy
skip apply to `054761aaa6e1ddae295840a1cf30ede36aa96f81`. Its
`46 passed in 52.36s` remains at `bc088ed8473dae362a76fd866763027f90d2a884`,
with successful test-double copies separate from native `EINVAL` refusal.
Publisher review `5289973671` applies to `fa53c74460aa0c63516eb5d6a34f30f0e12213b9`;
its `66 passed in 109.70s` remains at `731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`.
Unchanged-head failed-install-only CI recovery did not establish the historical
index/cache cause or justify dependency changes. None of these approvals covers
the new setup code or this head.

Accepted-input run `35847871634`/job `107138294292` on
`b0abe87275e3aa4d403732a6a8de8dacfe591c7e` verified all four pins at
10:19:28 UTC on 2026-09-23 and the canonical 2,519,040-byte archive, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Artifact `10744386417` carries checksum-matched
`verified_inputs_sha256=40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38`,
status `pending`, no execution/child and empty receipt/result/deliverables.
Native-connectivity diagnostic `35817078746` separately connected on
`0f0911b435d7f704db8e2f2131a00ade310d5c1f` with diagnostic defaults, not the
pilot treatment. Neither is a pilot result, durable output or grade.

The earlier GitHub metadata 403, HF redirect 307, separate HEAD observation,
initial upload 400/lost stderr and later private staging success remain distinct;
the original CI Location is still not reconstructed. Full prior commands,
identities and histories remain in the
[source record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/9366a3bb6bb2ff768b037f56f6b2e268b172d8b8/tasks/LATEST_TASK_RESULT/README.md)
and changelog, not relabeled as new validation.

### Remaining work

New-head leader review/final checks; explicit live-setup authorization and actual
account/absence/private-HEAD observations; separate destination approval and
write/prefix readiness; private output-publication and grading-adapter workflow
wiring plus native-host grading-input installation; ordered 30-cell admission/
deduplication/execution; fixed grading. No cell execution or publication is
authorized or automatically triggered by this setup unit.
