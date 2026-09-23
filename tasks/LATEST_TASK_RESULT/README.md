# Latest task result

## CI output-target inspection: exact-main integration

`PROJECT5-TARGET-CHECK-INTEGRATION-2146` brings the reviewed #665 inspection
unit onto exact main `7f089ee005c00f2a37c5f578c295555bd8a51cbb` with one
ordinary non-squash merge. The first parent is
`79c43ca20bac525d7ff77cc3e7a042ec81bdc2a3`; the second parent is that exact
main. Their merge base is `7c3238f18f1e32d76c8f326b29bf674f8364d4a0`.
Only `CHANGELOG.md` and this completion record conflicted. No implementation
conflict occurred, and no inspection, publisher, grader or workflow behavior
changed.

### Exact identities and review boundaries

Direct index-to-parent comparisons preserve all seven #665 blobs from
`79c43ca20bac525d7ff77cc3e7a042ec81bdc2a3`:

| File | Git blob |
| --- | --- |
| `.github/workflows/codex-budget-pilot-ci-cell.yml` | `e8b9e9b01767c0d899ecc4112100e4ec22d54e6e` |
| `batch-runner/codex_budget_pilot_ci.py` | `b07f3ce3ce2fa7ee1c0a8de5b618f6d3e0a693e6` |
| `batch-runner/codex_budget_pilot_output.py` | `c74703dc0fd60c225e2b54058610e9ac769fd51b` |
| `batch-runner/tests/test_codex_budget_pilot_output_target.py` | `cead9516d4444911e6760bf9031122bc762d371a` |
| `batch-runner/tests/test_codex_budget_pilot_ci.py` | `fc52ec0591935e54eb8647d40e2816c04a35b7cb` |
| `batch-runner/tests/test_codex_ci_hf_originals.py` | `8997ea44be4530ca5a8ccd82e3000e4d2a334f13` |
| `batch-runner/tests/test_codex_ci_input_intake.py` | `10a1f8fa7096f5bf04aa4277338b28d905ba5c50` |

With those seven files and the two completion records excluded, every tracked
file matches incoming main. Its four adapter-related blobs are:

| File | Git blob |
| --- | --- |
| `batch-runner/codex_budget_pilot_grading_input.py` | `caf58212bbac277c57dc574ba8365819be35c83c` |
| `batch-runner/gpt54_codex_grading_input.py` | `663717a3bf17633cd09a551bb5cda33cb328f4ab` |
| `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml` | `948f3b591fdab246d11bc0a675a9aa1ac5b330f3` |
| `batch-runner/tests/test_codex_budget_pilot_grading_input.py` | `fa171f881342a4f572456b7e7fde09afd5f616e1` |

The legitimate incoming `gpt54_codex_grading_input.py` source pin remains
`9a24f053afde1bf4b039135fdc633d49b32553f5b02a50c596f210dc7e46d1b7`.
Parent/blob comparisons and diff checks are the only integration validation.
No tests, counters, dependency validation, previous audits or live operations
were repeated. These checks establish byte preservation, not target privacy,
write access, publication or grade readiness.

Leader FINAL-APPROVE `5290860576` applies to #665 at
`79c43ca20bac525d7ff77cc3e7a042ec81bdc2a3`. At the leader's read, eight
checks had passed and native-host-contracts was still running. Leader
FINAL-APPROVE `5290860366` and all ten applicable passing checks with deploy
skipped apply to #664 at `054761aaa6e1ddae295840a1cf30ede36aa96f81`, now
included in supplied main. No CI state was queried or awaited here. Neither
review approves this new integration head; it needs its own leader review and
ordinary final-head checks.

### Preserved inspection unit

The original `PROJECT5-CI-OUTPUT-TARGET-CHECK-2044` unit started independently
at `7c3238f18f1e32d76c8f326b29bf674f8364d4a0`. Its implementation and first
focused test invocation are at `faa64ef15fce0e101c3911a092a312563fff2486`.
Only a test fixture changed at `668cdbed6574d0b0b458d87cda9e3ad87a1cbfed`;
production bytes are identical between those commits. The
[reviewed inspection record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/79c43ca20bac525d7ff77cc3e7a042ec81bdc2a3/tasks/LATEST_TASK_RESULT/README.md)
retains the complete interface, request restrictions and pre-edit
extreme-reasoner **APPROVE-WITH-CONDITIONS** decision for code/offline work.

Default-false `output_target_check` remains exclusive with execute/input-check.
The real canonical-cell/source/CI gates precede an early return before input,
dispatch or publication. Only the tracked exp033 `CODEX_TEMPLATE.data.source`
candidate is accepted, with name fingerprint
`88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf`.
At most one exact dataset/main metadata GET is allowed, without retries or
redirects, within a 20-second internal timer, 30-second process limit plus
five-second kill grace, and one-minute step ceiling. Existing CI `HF_TOKEN`
scope, restored offline settings, redaction, publisher defaults/PRIVATE/CAS/
prefix gates and the public completion schema remain unchanged.

Safe CLI metadata does not carry a raw locator, credentials or payload. Public,
missing, inaccessible or malformed metadata refuses; a missing response keeps
HTTP status null. Every outcome retains `write_access="not_established"`,
`publication_authorized=false` and `model_requested=false`. Even an eligible
private candidate would establish only observed identity/privacy/HEAD, not
approval or write/prefix readiness. No live target observation has been made.

### Historical focused offline evidence

The original family used the real compiler, CLI, CI gate logic, installed HF SDK,
scoped HTTP transport guard and safe projection with synthetic CI/source
capability and fake HTTP metadata. Pinned-runtime version metadata was supplied
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

### Preserved incoming grading adapter

The incoming adapter selects one real compiler cell and reuses the shared
materializer's result, artifact, ledger, provenance and atomic no-clobber
checks. The parent-comparison entry still refuses pilot IDs. Actual output
repository/revision provenance is required; a caller's declaration/hash is
not independent provider authentication. The private preparation manifest
reports grading `UNRUN`, and no original result, deliverable or ledger is
rewritten. Only the derived result receives the existing provenance augmentation.
There is no source-schema relaxation, publisher wiring or grader invocation.

The older review `5289680397` belongs to
`e3653758bff6dde3fadd6e72ff0af5b595566af7`. Its normal integration at
`054761aaa6e1ddae295840a1cf30ede36aa96f81` has the later review/check scope
recorded above. Historical validation remains at
`bc088ed8473dae362a76fd866763027f90d2a884`:

```bash
env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_GRADING_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_grading_input.py
```

`PILOT_GRADING_PYTHON` named the existing isolated Python 3.10.12 interpreter.
Result: `46 passed in 52.36s`, exit 0. Successful-copy cases use the existing
test-only rename double; the real native `RENAME_NOREPLACE` case observed errno
22 (`EINVAL`) and fail-closed cleanup. All 34 refusal cases assert installation
is not reached. Production has no fallback; successful grading-input
installation on the native execution host and grade readiness remain unproven.

Earlier failures at `f13c2fa156b4a80f43620a2a1b4cf0a25eca241a` remain
`11 failed, 34 passed in 51.51s`, then `11 failed, 34 deselected in 14.42s`
for the 11 blocked cases on tmpfs, both exit 1. The
[incoming immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/7f089ee005c00f2a37c5f578c295555bd8a51cbb/tasks/LATEST_TASK_RESULT/README.md)
retains the full interface, commands and earlier histories. Nothing here is
a new test run, native installation or regrading.

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
cover the publisher source only, not this integration head or proof of
publication/wiring.

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
distinct. That successful diagnostic used exact source
`0f0911b435d7f704db8e2f2131a00ade310d5c1f` and diagnostic defaults, not the
pilot's xhigh treatment, file/recovery behavior or benchmark grading. The
original CI Location is still not reconstructed. Detailed
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

Remaining: new integration-head review/final checks; one checked CI
target-metadata observation; output destination approval and write/prefix
readiness; private workflow wiring before paid cells; grading-input installation
on the native execution host and use of actual output provenance; ordered
30-cell admission, cross-run deduplication and execution; and fixed grading.
The accepted lifecycle gap remains: Step2 leaves bytes on the runner and
completion hashes do not retain them. Inspection does not wire the publisher
or solve that gap.

Original bytes, campaign state/order, model/host/fixed-grader settings, existing
job ceilings and 180-minute cell/30-minute attempt limits remain unchanged.
No tests, real HF metadata, credential lookup/transfer, payload transfer,
OIDC/model or grader operation, workflow dispatch or CI query ran for this
integration. Standing spend authority is unchanged. `experiment-report-en`
and `im-not-ai-en` kept historical tests/reviews, native refusal, accepted inputs
and unknown target readiness distinct. No counter, dependency validation,
additional audit agent or CI/review wait was used.
