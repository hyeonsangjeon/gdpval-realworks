# Latest task result

## Private-intake integration and one standard-client upload

The ordinary merge preserved the reviewed intake and diagnostic code. One
separately authorized `gh release upload` invocation then succeeded: selected
asset `582945947` is `uploaded` under release `394272629`, observed with
`draft=true`. Its 2,519,040-byte size and provider digest match the independently
verified private archive. This establishes staging, not CI read-token access,
current native connectivity or pilot execution.

### Integration and unchanged source identities

Merge commit `8806971ca06516e02cba12f090e4bf0bed3d47ae` combines the reviewed #658 source
`082a7dab19f3e5e80b94b32f55ad25f8493b63a9` with exact main
`0f0911b435d7f704db8e2f2131a00ade310d5c1f`. Only this completion record and
`CHANGELOG.md` conflicted. Both substantive changelog histories are retained;
no implementation conflict or workflow-behavior edit occurred. Both parents
remain in history; no rebase, squash or copied upstream commit was used.

Git blob comparisons verified all seven protected #658 intake/workflow/test
files against its reviewed source, and all four incoming #657 diagnostic
workflow/test files against exact main:

| Preserved source | Verified files |
| --- | --- |
| #658, seven identical blobs | Backend and single-cell workflows; `codex_ci_input_intake.py`; the partition, single-cell, intake and VM-gate contract tests |
| Incoming #657, four identical blobs | Connection-diagnostic workflow; auth-discriminator, connection-probe and transmission-sweep tests |

The corrected transmission-sweep contract is included unchanged. The backend
workflow retains raw SHA256
`08291d29670966d52a88ec216b71e68811a05bd599c13df040460a72204849ac`,
including the 60-minute native-host ceiling and its coupled assertion.
These are file-identity checks, not new test results. No test selection was
rerun; no active grader-source/template identity or 37/58 source-set guard
changed.

#658 FINAL-APPROVE review `5286767574` applies to
`082a7dab19f3e5e80b94b32f55ad25f8493b63a9`; the static result remains
`1 passed in 6.76s` at `572326c4933cd26870ffe1cfa500979ce8a0f89b`.
#657 review `5286611655` applies to
`ae4c73b834337001102a0a7fc0e78a3d608a7044`; its correction result remains
`1 passed in 0.25s` at `e6445a0544e0e6c0bb3d5ef6bee4a232be96ccff`.
The leader reports all nine exact-head checks passed before #657 entered the
incoming main. Neither review is approval of this integration head.

The earlier #658 intake approval `5286466150` at
`e5d5fcb647129e86d9faf742fc19df1e1e800c15` still covers only its source and
offline evidence. Its `67 passed, 18 deselected in 4.66s` result remains at
`f4a984d8bed0f6845e405c5b6d9f82b3b96757e0`. The original #657 result remains
`42 passed, 155 deselected in 4.92s` at
`f09ffb62b717f9818dedd4e59a9a45c483ca4f42`. The cancelled 45-minute job,
its passing pytest output and the ceiling correction retain their separate
scopes in the historical record below; cancellation is not CI success.

### Independent standard-client staging observation

On 2026-09-23, the named private handoff supplied the existing regular,
single-link archive. A current byte check verified 2,519,040 bytes and SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
One private byte-for-byte copy gave the standard client the required filename;
the copy's size and SHA256 matched independently. No hardlink, repackaging,
original-input preparation or campaign materialization was performed.

A separate exclusive one-use reservation linked this attempt to release
`394272629`, preserving the first reservation and receipt. The existing
GitHub account matched `hyeonsangjeon`. Immediately before upload, the exact
selected-release read verified `draft=true`, label
`project5-ci-inputs-20260923-01`, original target
`266ef7a05335d900304214da0c0d680331fb346c` and `assets=[]`. No release was
created or retargeted. The standard command was:

```bash
gh release upload project5-ci-inputs-20260923-01 "$PRIVATE_NAMED_ARCHIVE" --repo github.com/hyeonsangjeon/gdpval-realworks
```

`PRIVATE_NAMED_ARCHIVE` denotes the private regular file named
`budget-pilot-originals-20260923-01.tar`; it is not a public locator. The
observer invoked this command once without `--clobber`, the previous stdin
API wrapper, debug/header logging or a retry loop. The upload had a 60-second
ceiling including cleanup, within a 240-second total bound. It exited 0 in
1.733163 seconds; the full observer exited 0 after 3.365667 seconds. No timeout
or interruption occurred, and the owned `gh` child was reaped. The private
receipt retains bounded stdout/stderr and outcome; this successful command
produced zero stdout bytes and zero stderr bytes, with no truncation.

The one post-upload read of the selected release supplied these facts:

| Field | Observed value |
| --- | --- |
| Release ID and draft status | `394272629`, `draft=true` |
| Asset ID and state | `582945947`, `uploaded` |
| Asset name | `budget-pilot-originals-20260923-01.tar` |
| Size | 2,519,040 bytes |
| Provider digest | `sha256:757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3` |

The label and original target still matched. The external SHA expectation
remains the trust anchor; matching provider metadata does not replace the
local byte check. No payload was downloaded, no importer or CI input-check
ran, and no release publication, tag/ref mutation, overwrite or deletion was
performed. Draft status is observed at those reads, not a permanent privacy
guarantee. Owner-account staging does not establish that the CI
`contents:read` token can access the draft asset. No public fallback or
permission change is implied. Private locators, raw responses and payloads
remain outside the repository records.

The initial HTTP 400/`gh` exit 1 remains a separate failed observation. Its
observer exited 2 after 2.506628 seconds and did not persist the captured
stdout/stderr; the underlying cause remains unrecoverable. The prior
conditional correction did not run. This independently authorized successful
upload neither diagnoses that failure nor recreates or replaces its receipt.

### Leader-dispatched diagnostic: queued at observation only

The leader reported one native-only diagnostic dispatch, run `35817078746`,
on exact main `0f0911b435d7f704db8e2f2131a00ade310d5c1f`, confirmed
**QUEUED AT OBSERVATION**. The reported inputs were:

```yaml
deployment: gpt-5.4
native_only: true
send_request: true
send_valid_request: false
send_closing_sweep: false
```

Its existing 20-minute job ceiling, default 120-second script argument,
native runtime defaults and OIDC/resource/retry/redaction guards remain in
scope. This task did not query, dispatch, rerun, cancel or wait for that run.
No result, connectivity verdict, usage or charge was observed here. One
native turn is not an exactly-one-HTTP claim. The diagnostic is separate from
the 30-cell pilot, its `xhigh` control and graded quality.

### Controls and remaining boundaries

Both campaign identities are unchanged. The sealed NAS source and all 30
pending cells remain untouched; the CI campaign remains reserved, not
materialized. The registered five-task, A1/B1/C1/C2/B2/A2 order, common CI
host/model/runtime policy, original bytes, tools/context and fixed grader
remain unchanged. A keeps at most four fresh attempts. B/C retain the same
continuation/backoff, with only C receiving host error feedback. The
180-minute cumulative cell deadline, 30-minute attempt bound and 240-minute
cell-job ceiling are unchanged; the 60-minute offline CI envelope and the
diagnostic limits are separate.

The new immutable HEAD still needs leader review and ordinary final-head
checks. CI read-token draft access and a separately directed reviewed-main
`input_check`, current native connectivity, ordered 30-cell scheduling,
deduplication/aggregation, execution and fixed grading remain unfinished.
Release `394272629` and asset `582945947` are now observed input-check
identifiers, not authority to dispatch that workflow or use a feature HEAD
as reviewed main. No OIDC, NAS Azure auth retry, native/model, grader or
campaign operation followed the upload. Standing spend authority is
unchanged; there is no new owner-approval wait.

Experiment-design kept the pilot controls, private staging and diagnostic
evidence separate. Experiment-report-en and im-not-ai-en preserved the
original tests/reviews, the lost-error boundary and the distinction between
uploaded bytes, CI-token access and model or grading evidence.

The [incoming native-only correction and staging record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ae4c73b834337001102a0a7fc0e78a3d608a7044/tasks/LATEST_TASK_RESULT/README.md)
and unchanged changelog entries preserve #657's complete evidence. The prior
#658 record below is retained under its original observation scope; its
then-current main, frozen-branch statements and unattempted conditional upload
are historical, not claims about this integration or the new standard-client
upload. Its later input-check command remains an unrun example, not a launch
instruction for this task.

## Prior #658 result: CI envelope correction and staging reconciliation

Only the `native-host-contracts` job ceiling changes from 45 to 60 minutes.
The test selection, guards and pilot budgets are unchanged. The sole local
static selector reported `1 passed in 6.76s`, exit 0, at
`572326c4933cd26870ffe1cfa500979ce8a0f89b`.

Private staging remains incomplete. The leader's selected-release observation
found no assets. Local inspection established that the original upload
observer did not preserve the failed `gh` stdout/stderr, so the evidence
does not identify a concrete request-format correction. No corrected upload
was attempted, and no replacement receipt was created.

### Cancelled CI job and bounded correction

The leader supplied run `35811169415`, job `107022868111`, with the
`native-host-contracts` cancellation annotation that its maximum 45 minutes
was exceeded. Its pytest step printed
`71 passed, 84 deselected in 2562.66s (0:42:42)`. Setup began at
`02:38:39Z`, the test command began at `02:40:54Z`, and tests/cleanup ended
at `03:23:38Z`. The supplied interval totals approximately 44:59, including
2:15 before the test command. Eight other checks passed. Passing selected
assertions did not make this cancelled job successful or clear GATE-BLOCKED
review `5286611715`. No CI query or manual rerun was performed here.

The mandatory pre-edit extreme-reasoner decision approved this change with
conditions. It used the available inherited agent, not the charter's
unavailable named preset. The allowance increases by at most 15 runner-minutes
for this job, not a model-spend allowance or a prediction that CI will pass.
Every other backend job remains at 45 minutes, including the general pytest
job and its existing timeout warning. The exact native command remains:

```bash
python -m pytest -m "not integration" --tb=short -q -rs tests/test_gpt56_pilot_wire_receipt.py -k native_result_host
```

The complementary wire predicate, exactly-once node coverage, action/runtime
pins, permissions, concurrency and dispatch/checkout guards remain intact.
The partition assertion now requires 60 only for `native-host-contracts`
and 45 for every other job. The directly coupled whole-workflow digest
expectation in `test_ghcp_vm_gate_contract.py` was refreshed to
`08291d29670966d52a88ec216b71e68811a05bd599c13df040460a72204849ac`.
Its hash guard and historical/Foundry digests are unchanged. No intake,
native implementation, experiment, dependency or active grader-source/template
identity changed; the 37/58 source-set guards were preserved and not rerun.

### One local static selector

The workflow and its two coupled expectations were committed before the
single invocation at `572326c4933cd26870ffe1cfa500979ce8a0f89b`.
`CI_ENVELOPE_PYTHON` denotes the existing isolated interpreter in the private
handoff, previously recorded as Python 3.10.12 with SDK and companion 0.147.0.
No dependency was installed. From the repository root:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$CI_ENVELOPE_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
```

Result: `1 passed in 6.76s`, exit 0. This is a static YAML/command/partition
contract. Its existing scoped `--collect-only` subprocesses check preflight
node coverage without running fixtures or test bodies. It did not execute
the native-host family, the earlier 67/42-case selections, a full suite or a
workflow. This result is not final-head CI success, live access, native
connectivity, model consumption or graded quality.

### Private staging reconciliation and stopped boundary

The original authorized transaction created draft release `394272629` with
label `project5-ci-inputs-20260923-01`, targeting exact main
`266ef7a05335d900304214da0c0d680331fb346c`. Its single upload of
`budget-pilot-originals-20260923-01.tar` returned HTTP 400 and `gh` exit 1.
No asset ID was captured. The observer exited 2 after 2.506628 seconds and
retained its one-use reservation, release receipt and stopped observation.
The [immutable prior staging record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ae4c73b834337001102a0a7fc0e78a3d608a7044/tasks/LATEST_TASK_RESULT/README.md)
preserves that original unresolved outcome; those private records were not
modified.

The leader subsequently read only that selected release and reported
`draft=true`, the same target/label and `assets=[]`. This resolves asset
absence at that observation, not the HTTP 400 cause or access by the CI
`contents:read` token. This task did not repeat the release read.

The retained observer constructs a `gh api` POST with `Content-Type:
application/x-tar`, `--input -` and the archive bytes on stdin. Its failure
path captures stdout/stderr only in process memory, extracts the HTTP status,
stores that status and exit code, then raises
`github_operation_failed_no_retry`. The persisted observation contains that
generic reason, HTTP 400 and exit 1, but no server message or response body.
The known argv does not establish the wire framing or the underlying server
reason. No client-format, credential or permission diagnosis is supported.

The conditional corrected-upload authorization required an identifiable
request-format defect. That evidence precondition was not met, so no
corrected-attempt reservation or upload was made. No account/release API,
candidate reread/rehash, download, import, public fallback, tag/ref mutation,
clobber, deletion, credential operation or campaign operation followed.
The external expectation remains the previously verified 2,519,040 bytes and
SHA256 `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`;
it was not remeasured here. No remote asset ID, state, size or provider digest
is invented. Private locators, raw responses, signed URLs, tokens and payloads are
not published. No OIDC, native/model or grader boundary was reached.

### Preserved intake evidence and review scopes

Main remains `266ef7a05335d900304214da0c0d680331fb346c`. The reviewed intake
source at `e5d5fcb647129e86d9faf742fc19df1e1e800c15` is unchanged.
FINAL-APPROVE review `5286466150` covers that intake implementation and its
offline evidence only, not this CI-ceiling correction or live draft access.
The original result remains `67 passed, 18 deselected in 4.66s`, exit 0,
at `f4a984d8bed0f6845e405c5b6d9f82b3b96757e0`: 66 synthetic intake cases
and one workflow contract, not 67 pilot cells. Its original command was:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$CI_INTAKE_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_ci_input_intake.py batch-runner/tests/test_codex_budget_pilot_ci.py -k 'ci_input_intake or ci_registered_cell_workflow_invocation_contract'
```

`CI_INTAKE_PYTHON` was the existing isolated Python 3.10.12 interpreter with
`openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0`. That family used
fake GitHub transport and explicitly synthetic provenance/anchor boundaries,
with real CLI/importer/readers and hash/type/no-clobber/refusal checks. It was
not rerun. The [immutable intake completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/e5d5fcb647129e86d9faf742fc19df1e1e800c15/tasks/LATEST_TASK_RESULT/README.md)
retains its complete privacy/transport limits, earlier integration history,
original 19/39-case results and the one-cell/bundle review scopes. Existing
changelog entries are preserved verbatim.

Plan-only still makes no transfer or model request. Intake still requires
explicit source/cell/release/asset/hash identities, an unpublished draft and
the genuine installed-original verifier; failed inputs stop before OIDC or
native admission. Input-check does not request OIDC or invoke native work,
although the existing job-level OIDC permission remains. Only the allowed
completion envelope is publishable. No static permission declaration or
owner-account draft observation proves CI read-token access.

#657 remains frozen at `ae4c73b834337001102a0a7fc0e78a3d608a7044`.
Its FINAL-APPROVE review `5286611655` covers its one-test correction; the
`1 passed in 0.25s` result remains at
`e6445a0544e0e6c0bb3d5ef6bee4a232be96ccff`. The earlier native-only result
remains `42 passed, 155 deselected in 4.92s` at
`f09ffb62b717f9818dedd4e59a9a45c483ca4f42`, under review `5286077604` at
`0f291f4041bb321817ce93e6d8b4bfe0c4f2cfb0`. Neither is a live diagnostic
or approval of this change. No #657 tests, CI query or diagnostic ran here.

### Controls and remaining work

The sealed NAS campaign `budget_pilot_20260923_01`, source
`0d6ed6d806fc0360434952792d5ab82327290570`, original inputs and all 30 pending
cells remain untouched. `budget_pilot_ci_20260923_01` remains reserved, not
materialized or run. The five `advance_check_5` tasks retain per-task
A1/B1/C1/C2/B2/A2 order, GPT-5.4/direct-v1/xhigh, common CI host policy,
context, tools and fixed grader. A keeps at most four fresh attempts; B/C
share retained workspace/native-thread continuation and backoff, with only
C receiving host error feedback. The 180-minute cumulative cell deadline,
30-minute attempt bound and 240-minute execution-job ceiling are unchanged.
The 60-minute offline contract job is a separate CI envelope. Input transport
and native diagnostics remain separate from the A/B/C treatment and quality.

The new immutable HEAD still needs leader review and ordinary final-head
checks. Private staging, the subsequent reviewed-main read-token input-check,
current CI OIDC/native connectivity, ordered 30-cell scheduling/deduplication/
aggregation, paid execution and grading remain unfinished. No workflow was
dispatched. Standing spend authority is unchanged; the present blockers are
technical evidence boundaries, not another owner-budget approval request.

The intended later no-model input-check invocation remains below. It was not
run. The leader must supply a reviewed main SHA, canonical cell and observed
positive release/asset IDs; the absent asset ID cannot be invented, and a
feature HEAD cannot replace the reviewed main identity.

```bash
gh workflow run codex-budget-pilot-ci-cell.yml \
  --repo hyeonsangjeon/gdpval-realworks --ref main \
  -f reviewed_source_sha="$REVIEWED_MAIN_SHA" \
  -f cell_id="$CANONICAL_CELL_ID" \
  -f execute=false -f input_check=true \
  -f input_release_id="$PRIVATE_DRAFT_RELEASE_ID" \
  -f input_asset_id="$PRIVATE_DRAFT_ASSET_ID" \
  -f input_bundle_sha256=757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3
```

Experiment-design kept the existing controls and diagnostic boundary fixed.
The CI/cost decision constrained the job envelope and exact static guards.
Experiment-report-en and im-not-ai-en kept passing assertions separate from
job cancellation, and reconciled asset absence separate from an unknown
upload cause, live access or benchmark evidence.
