# Latest task result

## Bounded CI output-target inspection; separate grading-adapter integration

`PROJECT5-CI-OUTPUT-TARGET-CHECK-2044` adds one explicitly selected read-only
mode to the existing single-cell path. This independent branch starts at exact
main `7c3238f18f1e32d76c8f326b29bf674f8364d4a0`; it does not stack on the
grading adapter. Implementation and the first focused test invocation are at
`faa64ef15fce0e101c3911a092a312563fff2486`. A single test-fixture correction
and failed-case-only validation are at
`668cdbed6574d0b0b458d87cda9e3ad87a1cbfed`. Production bytes are identical
between those commits. Subsequent record edits are not another test run or
final-head approval.

### Inspection contract

The existing [single-cell CLI](../../batch-runner/codex_budget_pilot_ci.py)
accepts `--output-target-check`; the
[workflow](../../.github/workflows/codex-budget-pilot-ci-cell.yml) exposes
default-false `output_target_check` in both entry points. It is exclusive with
execute/input-check. The CLI also refuses resume, input paths, output paths and
envelope verification in this mode rather than silently using them. Parser
errors are closed codes, never echoed private arguments.

The genuine canonical-cell compiler, reviewed-source check, main/workflow/host
binding and first-attempt gate still run. The inspection command then returns
before private-state creation, dispatch, `InputSources`, input admission or
completion publication. The preceding workflow plan step retains its ordinary
pending, no-execution completion. The completion schema and its one existing
artifact remain unchanged; inspection evidence is safe CLI JSON in the log,
not a new publication format or artifact.

The metadata helper derives only `CODEX_TEMPLATE.data.source` from the tracked
`batch-runner/experiments/exp033_codex_foundry_fixed5.yaml`. Before token lookup,
it requires the exact name fingerprint:

`88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf`.

Its logical role is `exp033_submission_result`. The operational locator is not
printed, accepted as an argument or discovered through listing. Derivation
does not approve that repository for outputs or establish its current privacy.

The existing CI `HF_TOKEN` is supplied only to the selected metadata step,
apart from its already-reviewed, separately gated input-step use. The helper
captures that explicit token, reuses the existing reversible HF environment
scope, removes ambient input tokens during the request and restores offline
environment/constants/logging afterward. No cached credential, new secret,
identity or permission is used. Model/native steps receive neither input token.

The landed publisher's scoped HTTP client now has an optional exact
metadata-only restriction. It permits at most one attempted HTTPS GET to the
derived dataset's `main` metadata path; its counter spans client recreation.
Only one `HfApi.repo_info(repo_type="dataset", revision="main", token=...)`
call is made. Redirects, alternate paths/hosts/queries/methods, second requests
and every non-200 response refuse. Terminal transport errors prevent SDK
backoff. The response retains the existing bounded streaming-byte limit and
never enters logs as a body, URL, header or arbitrary exception string.

Bounds are separate from model execution: 20 seconds for the internal metadata
timer and each remaining request timeout, 30 seconds for the subprocess plus
five seconds of kill grace, and one minute for its workflow step. Existing
dependency/setup time still applies. The publisher's default 30-second HTTP
phase and 120-second publication bounds are unchanged. So are the existing
120-second/three-minute input envelope, 240-minute job ceiling, and 180-minute
cell/30-minute attempt limits.

Only fixed keys are projected: logical role/name fingerprint, exact returned
identity match, observed boolean privacy or null, actual lowercase 40-hex HEAD
or null, actual received HTTP status or null, observation time, a closed refusal
reason, and `eligible_private_target`. `exact_identity_match=false` includes
unavailable metadata; it is not a guessed identity mismatch. A foreign returned
identity is refused before its privacy/HEAD can be attributed to this target.
Public, missing, inaccessible or malformed metadata exits 2 with the observed
safe boundary retained. No-response failures keep HTTP status null.

Every outcome retains:

- `write_access="not_established"`
- `publication_authorized=false`
- `model_requested=false`

Even `eligible_private_target=true` establishes only observed exact identity,
privacy and HEAD. There is no prefix listing, marker write, `create_commit`,
repository/branch creation, privacy change, payload transfer, input fallback,
publication approval, model execution or grading. The publisher's actual
PRIVATE/parent/CAS/prefix gates are not weakened or invoked by inspection.

The mandatory pre-edit extreme-reasoner decision was
**APPROVE-WITH-CONDITIONS**. It required the early CLI return, explicit workflow
exclusions, exact one-GET guard, response-status capture, bounded/restored HF
scope and unchanged publisher defaults. It authorized implementation/offline
validation only, not a live request or deployment gate.

### Focused offline evidence

The one new family uses the real compiler, CLI, CI gate logic, installed HF SDK,
scoped HTTP transport guard and safe projection with synthetic CI/source
capability and fake HTTP metadata. Pinned-runtime version metadata is supplied
by the fixture; no native SDK/companion installation or execution is established.
Validation reused Python 3.10.12, pytest 9.1.1 and huggingface_hub 1.23.0 in an
environment-cleared process. No dependency installation/resolution was repeated.

At tested SHA `faa64ef15fce0e101c3911a092a312563fff2486`:

```bash
timeout --signal=TERM --kill-after=5s 300s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_output_target.py
```

Result: **`1 failed, 58 passed in 31.61s`**, exit 1. The size-limit fixture
provided an already-buffered response; it refused through JSON parsing with
`output_target_check_failed`, rather than exercising the expected streaming
`hf_response_bytes_exceeded` boundary. This remains a failed test invocation.
Only that synthetic response changed to an unread stream, matching the real
transport boundary. No production/workflow byte changed.

Only the failed case was rerun at tested SHA
`668cdbed6574d0b0b458d87cda9e3ad87a1cbfed`:

```bash
timeout --signal=TERM --kill-after=5s 60s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short 'batch-runner/tests/test_codex_budget_pilot_output_target.py::test_output_target_no_response_and_parse_failure_never_invent_status[size-200-hf_response_bytes_exceeded]'
```

Result: **`1 passed in 1.80s`**, exit 0. The other 58 passing cases were not
repeated. These two observations are not a full 59-case run at the later SHA;
all durations are pytest wall time, not live HF or model latency.

Coverage includes plan-no-token/network, incompatible/unknown modes, canonical
source/cell/host gates, fixed target/main identity, private/public/unavailable
metadata, real numeric 401/403/404 and other statuses, null status without a
response, redirects, malformed metadata, streaming size/time limits, redaction,
environment restoration, client recreation and SDK backoff refusal. The optional
guard also leaves the default publisher's fake-HTTP multi-request/redirect and
timer behavior intact. Excluded-operation guards record any attempted socket,
credential-cache access, input fetch, execution child or publication even if
an exception is caught. Workflow routing assertions are **static YAML contract
checks**, not Actions execution or actual OIDC evidence. Three existing test
files had only the coupled exclusions/token-scope assertions updated; their
old families were not rerun. No 66/46/71 or full suite, live check or prior audit ran.

### Separate #664 normal integration

Before this independent implementation, the owned grading-adapter branch was
merged once and pushed at `054761aaa6e1ddae295840a1cf30ede36aa96f81`, then
frozen. Its two parents are reviewed adapter head
`e3653758bff6dde3fadd6e72ff0af5b595566af7` and exact supplied main
`7c3238f18f1e32d76c8f326b29bf674f8364d4a0`. Only the two completion-record
overlaps were resolved. Direct parent/blob comparisons preserved all four
adapter/shared-materializer/source-pin/test blobs; every other implementation,
workflow and test byte matches incoming main. There was no implementation
conflict, test rerun, audit, regrading or CI query.

Review `5289680397` and the leader's ten applicable passing checks/deploy skip
belong to `e3653758bff6dde3fadd6e72ff0af5b595566af7`, before the base moved.
Its `46 passed in 52.36s` remains at
`bc088ed8473dae362a76fd866763027f90d2a884`. Successful-copy cases use the
existing test-only rename double; the real native `RENAME_NOREPLACE` case
observed errno 22 (`EINVAL`) and fail-closed cleanup. Production has no fallback;
this is not live installation or grade-readiness evidence. The
[immutable integration record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/054761aaa6e1ddae295840a1cf30ede36aa96f81/tasks/LATEST_TASK_RESULT/README.md)
retains exact blobs, commands, earlier failures and incoming histories. That
integration head still requires its own leader review and automatic checks.

### Accepted observations, not repeated here

The leader reports #662 source-integration head
`fa53c74460aa0c63516eb5d6a34f30f0e12213b9`, review `5289973671`, passed all
nine checks and was incorporated into supplied main. Failed-job-only attempt 2
of `35848830781` and `35848830515` succeeded on that unchanged head. All four
earlier failed jobs had stopped during dependency installation, not tests.
No manifest/pin/code correction was made, and the historical index/cache cause
was not established. Its original `66 passed in 109.70s` remains at
`731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`, with original source review
`5289350726` at `0ff95ba41ce7ce961ee333bbcac9f8e3db539697`. Those reviews
do not approve this new inspection code or prove publication/wiring.

The leader read completed model-free input-check `35847871634`, job
`107138294292`, on exact `b0abe87275e3aa4d403732a6a8de8dacfe591c7e`.
At 10:19:28 UTC on 2026-09-23, `original_inputs_verified=true` with all four
pins and the canonical 2,519,040-byte archive, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Artifact `10744386417` has a checksum-matched completion whose
`verified_inputs_sha256` is
`40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38`.
It records status `pending`, `execution_requested=false`, `child_invocations=0`
and empty receipt/result/deliverables. OIDC, identity and Execute were skipped.
This proves accepted inputs, not a pilot cell, output, durability or grade.

The separate NAS target observation at 11:20:13 UTC matched the tracked name
fingerprint but found no process-local `HF_TOKEN` and no accessible known
handoff. It made **zero HF calls**; privacy, remote HEAD and HTTP status remain
unknown. NAS credential unavailability is not remote refusal. No credential
search or CI-secret transfer followed it. The future selected CI metadata mode
uses the existing CI context, but has not been dispatched or observed here.

The original GitHub release-metadata 403, HF reference-1 redirect 307, separate
equivalent-encoding HEAD observation, initial upload 400/lost stderr, later
private staging success and connected native diagnostic `35817078746` remain
distinct. The original CI Location is still not reconstructed. Detailed
publisher/redirect evidence and review `5289350480` are preserved in the
[incoming main record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/7c3238f18f1e32d76c8f326b29bf674f8364d4a0/tasks/LATEST_TASK_RESULT/README.md)
and changelog; no earlier observation is replaced or relabeled by this task.

### Future invocation and remaining work

For a later leader-directed run on its reviewed main SHA, the intended input
set is `reviewed_source_sha=<reviewed-main-SHA>`, the canonical A1 cell
`02aa1805-c658-4069-8a6a-02dec146063a_A_r1`, `output_target_check=true`,
`execute=false`, `input_check=false`, default `input_transport=github_draft`,
and empty release/asset/bundle-SHA inputs. The input route is unused. This is
an interface description, not a dispatch or authorization to publish.

Remaining: new-head review/final checks; one later CI target observation;
external destination approval and actual private/write/prefix readiness;
private output publication/wiring before paid cells; integration/use of the
grading adapter with actual output provenance; ordered 30-cell admission,
cross-run deduplication and execution; and fixed grading. The accepted lifecycle
gap remains: Step2 leaves bytes on the runner and completion hashes do not
retain them. Inspection does not wire the publisher or solve that gap.

Original bytes, campaign state/order, model/host/fixed-grader settings and budgets
remain unchanged. No real HF metadata, credential, data transfer, OIDC/model or
grader operation, workflow dispatch or CI query ran here. Standing spend
authority is unchanged. `experiment-design` kept this diagnostic separate from
the A/B/C treatments; `experiment-report-en` and `im-not-ai-en` kept failed and
passing test observations, accepted inputs, prior reviews and unknown target
readiness distinct. No additional semantic-audit agent or CI/review wait was used.
