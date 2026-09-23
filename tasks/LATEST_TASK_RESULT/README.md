# Latest task result

## PROJECT5-RETAINED-CELL-EXECUTION-0051 / TERMINAL-ADMISSION-POLICY-0122

### Current scope

Wire the existing single-cell CI execution to private CAS admission, same-runner
output publication and terminal confirmation, starting from exact main
`053e2e33c22775e23e3c13a13773090613fc200b`. This task is code/offline only.
No real HF credential, request, claim, publication, setup replay, original payload
transfer, workflow dispatch, Azure, model or grader operation occurred. No CI
state was queried or awaited. The new head needs leader review and final checks;
the design decision and earlier approvals do not approve this implementation head.

The mandatory extreme-reasoner decision preceded workflow/HF-write-path edits:
**APPROVE-WITH-CONDITIONS**. The same reviewer closed the pending terminal-response
condition after the leader's `PROJECT5-TERMINAL-ADMISSION-POLICY-0122` decision.
There was no new audit loop or additional owner-budget approval requirement.
Experiment-design guidance kept the inputs, controls, order and denominator fixed;
English reporting/copyediting preserved the distinctions below.

### Admission, retention and confirmation

`codex_budget_pilot_retention.py` defaults to local plan/validation without token
lookup or network. Its internal `--admit` and `--retain` entry points reuse the
real compiler, existing CI bindings, private file helpers, publisher and completion
projection. They add no dispatch inputs, scheduler, service, arbitrary target or
grading entry. The fixed target is derived from the fingerprint-matched tracked
namespace and must have name SHA256
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`.

1. Before inference, admission requires the exact private target, verified local
   inputs and pristine local cell state. At the same immutable parent, both the
   selected claim and output prefixes must be absent. The first canonical cell
   requires bootstrap `bfc7ae01ed14490817ceb7cb406adcb9bb95f557`. Later cells require
   a verified terminal record for the immediately preceding compiler-ordered cell.
   A tiny host-generated claim binds campaign/cell/order, source/config/input
   identities, actual CI run/job/attempt, workflow, host instance and expected parent.
   One add-only server-parent/CAS commit is verified before a private acknowledged
   admission receipt is written. The token-free CI `--execute` gate checks that
   receipt itself; a workflow condition alone is insufficient.
2. After the existing dispatcher finishes and owned cleanup is confirmed, the
   publisher uses the actual admission commit as its exact parent. It preserves
   the validated result, deliverables and valid ledger bytes. Failed/stopped cells
   without a result may retain only an explicit failure manifest, with missing
   result/ledger/usage still missing and `grade_ready=false`. The standalone
   publisher still refuses missing results by default. A narrow dispatcher fix
   binds an already written valid result on timeout without changing its stopped
   status, original deadline, bytes or accounting.
3. Only acknowledged publication with a durably saved private receipt and verified
   immutable output objects may produce a terminal confirmation. That confirmation
   is one CAS commit against the actual output revision. It binds the claim,
   existing output manifest, completion/status/cleanup and byte identities; it
   does not name its own future commit. No Git SHA or input revision is used as
   an HF publication revision.

The server terminal state, not delivery of its response, is authoritative for
**only the immediate successor**. A bounded fresh read checks the terminal,
claim and output manifest at their immutable commits, plus provider Git/LFS object
metadata for the already verified output bytes. It does not redownload generated
payloads. Per-run instance hashes may differ; each writer's own plan/run binding
and the common host policy must validate. Unknown tips, partial markers, foreign
identities, changed bytes and unverified hashes refuse.

A lost terminal response remains unresolved in the original local receipt. The
next runner writes a separate verified-server-state observation without claiming
that the prior writer received an acknowledgment. There is no acknowledgment-of-
acknowledgment chain. Ambiguous **output publication**, absent/invalid confirmation,
unconfirmed cleanup or a failed reconciliation read remains blocked. The successor
must still win its own absent-prefix/CAS claim. The same claimed cell cannot be
re-admitted on a new runner, skipped, replayed or given a new clock. Failed/stopped
rows are not changed to success. Missing/partial accounting is not changed to
complete accounting or zero cost. A local reservation remains distinct from the
durable remote claim.

Admission and retention have separate HF-token steps and short online scopes,
using the existing 30-second request and 120-second operation bounds, a 130-second
process limit plus five-second kill grace, and three-minute steps. SDK retries and
debug output remain suppressed. Execution refuses input/output tokens, and the
child launcher strips them. Ordinary plan, input-check, historical inspection and
setup retain their existing modes. No setup or old public dataset is touched.
Private receipts/locators/payloads do not enter the public artifact; only the
unchanged allowlisted completion envelope is uploaded. Safe retention CLI output
contains closed metadata, not raw errors, paths, URLs, credentials or native state.
Observed privacy and CAS do not atomically lock repository visibility.

The global concurrency guard, reviewed-main/attempt-one/source gates,
`contents:read`, 240-minute job ceiling, 180-minute cumulative/30-minute attempt
limits, A's four fresh attempts, B/C same-live-host continuation and C-only feedback
are unchanged. The canonical order remains A1/B1/C1/C2/B2/A2 for each of five tasks;
the denominator remains 30, including failed/stopped/missing outcomes. No automatic
30-run launcher or grading is added. Dependency/runtime/model/grader settings and
the active grading source pin are unchanged.

### Focused offline validation

The only selected family was
`batch-runner/tests/test_codex_budget_pilot_retention.py` (66 new cases, not the
earlier publisher family). The command used the existing Python 3.10.12,
pytest 9.1.1 and huggingface_hub 1.23.0; no dependency install/resolution ran.

```bash
timeout --signal=TERM --kill-after=5s 480s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_retention.py
```

At `a0c39e042b93ac2938c6f18d97693d2b0cc5091a`, the invocation ended with
**`66 errors in 4.03s`**, exit 1: the imported fixture required an absent
`openai_codex` package, so no test body ran. A test-only correction blocks the
repository's native/model/auth constructors without requiring that package and
supplies explicitly synthetic pinned-version metadata. Production pins and
execution checks were not relaxed; no native installation was established.

Corrected tested SHA: **`498c99d09f573707c2f9a9abd6afe8ac7b99e370`**.
The same selector emitted **48 passing case reports**, then reached its
480-second process limit, exit **124**, without a full pytest summary. It is not
a successful full-family command. Only the 18 unfinished cases were then selected
at that same SHA, with the same offline environment/options and a 300-second limit:
**`18 passed in 208.63s (0:03:28)`**, exit 0. The completed cases were not repeated.
This is split evidence, not an invented single `66 passed` invocation. The
process/test times are not model latency or changes to any CI/model budget.

The remaining-only selector used these explicit nodes in the same file:

```text
test_retention_invalid_predecessor_or_same_cell_never_advances[source]
test_retention_invalid_predecessor_or_same_cell_never_advances[manifest_hash]
test_retention_invalid_predecessor_or_same_cell_never_advances[output_bytes]
test_retention_invalid_predecessor_or_same_cell_never_advances[claim_bytes]
test_retention_invalid_predecessor_or_same_cell_never_advances[acknowledged]
test_retention_invalid_predecessor_or_same_cell_never_advances[unknown_tip]
test_retention_invalid_predecessor_or_same_cell_never_advances[read_failed]
test_retention_invalid_predecessor_or_same_cell_never_advances[same_cell]
test_retention_unconfirmed_cleanup_and_changed_output_refuse_before_network
test_retention_output_rechecks_private_identity_and_exact_admission_parent
test_retention_raw_errors_are_redacted_and_no_response_status_is_not_guessed
test_retention_target_fingerprint_refuses_before_credential_or_network
test_retention_current_byte_mismatch_refuses_before_publication
test_retention_conflicting_modes_refuse_before_token
test_retention_workflow_token_scopes_and_existing_controls
```

The real compiler, dispatcher/deadline, publisher, file/hash/no-clobber/CAS and
completion logic ran behind fake HF/child boundaries and synthetic input provenance,
CI/source capability and SDK-version metadata. Cases cover claim-before-child,
token isolation, strict canonical order/private/parent/duplicate refusals,
unchanged bytes, failed/stopped/partial/missing accounting, actual fake-returned
commit binding, cleanup/publication failure, and lost terminal response with valid
server proof admitting only the successor. Socket/process/auth/grader and real
HF boundaries were blocked. No original inputs or native SDK were exercised.

The source, workflow and test bytes in the documentation head match the corrected
tested SHA. Diff/identity checks also confirm unchanged dependency, backend-CI,
fixed-grader/shared-materializer and profile-control files. Five older test files
received coupled fixture or workflow-guard/token-scope updates; those families and
the prior 78/66/46/71/31/19 families were not rerun. No full suite, live check,
additional audit or CI wait ran.

### Separate observations and review scopes

The leader supplied actual setup success from run `35881609256`, job
`107251200144`, on exact source `053e2e33c22775e23e3c13a13773090613fc200b`:
at `2026-09-23T15:29:34.308692Z`, `outcome=created`, `private=true`, HTTP 200,
`stage=created_metadata`, `reason=null`, actual HF HEAD
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557`, and candidate name SHA256
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`.
The source gate bound the authenticated user/namespace, repository-level 404,
one private create and post-create metadata. Input/OIDC/Execute were skipped;
publication/model/grading were false and write/prefix readiness was not established.
The leader's durable setup reservation is CREATED/CONSUMED and must not be replayed.
The leader selected only that repository as the output destination. This is not
authorization for live writes/inference in this task or proof that retention ran.

Review `5293033879` applies to #666 at
`a45e5bb66c350ee2de432f0e9488d39ec3cabf34`. Its setup-family result remains
`78 passed in 58.90s` at `46d3bd32c3317e0e0cc41b4741c7087dd3584e42`, not live
setup evidence and not this implementation's validation or approval.

The leader supplied completed metadata run `35870090309`, job `107211610516`,
at 13:54:56 UTC on 2026-09-23. The historical target matched name SHA256
`88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf`:
`exact_identity_match=true`, HTTP 200, `private=false`, HEAD
`6c7e07ee7365f145dfcf898263365b5c8c97b224`, `eligible_private_target=false`,
reason `private_output_target_required`, exit 2. Write access was not established;
publication was not authorized and no model was requested. Input transfer,
OIDC and model steps were skipped. This was a successful privacy observation
and intentional refusal, not invalid credentials or failure to fetch. It says
nothing about the new destination by itself; its later setup is a separate
observation above. The old public repository remains untouched.

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
the new retention code or this head.

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
[source record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/053e2e33c22775e23e3c13a13773090613fc200b/tasks/LATEST_TASK_RESULT/README.md)
and changelog, not relabeled as new validation.

### Remaining work

New-head leader review/final checks; separately authorized, checked live admission,
write/prefix and output-publication observations; the first paid cell; canonical
grading-adapter workflow wiring using an actual output revision and Ubuntu 22.04
atomic grading-input installation; all 30 ordered cell outcomes and fixed grading.
The code now supplies serial next-cell admission and private retention, but no
live claim, retained pilot output, executed pilot cell or grade was observed here.
There is no automatic campaign launch, model retry, setup replay or new target.
