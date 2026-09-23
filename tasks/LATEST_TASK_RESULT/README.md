# Latest task result

## Private single-cell output publisher: exact-main integration

`PROJECT5-OUTPUT-MAIN-INTEGRATION-1913` integrates exact main
`b0abe87275e3aa4d403732a6a8de8dacfe591c7e` into reviewed publisher head
`0ff95ba41ce7ce961ee333bbcac9f8e3db539697` with one ordinary non-squash
merge. Only overlaps in `CHANGELOG.md` and this record were resolved. There
was no implementation conflict. No publisher behavior, upload policy, target
choice, active source pin, fixed grader setting or experiment control changed.
No target was selected and no publication, model call or grading occurred.

### Parent and file-identity evidence

The merge preserves the publisher head as its first parent and exact main
as its second parent; their merge base is
`9cb1c0d84f299f610ec98c90f3bac9ff9cbbdc75`. Direct index-to-parent comparisons
confirmed both publisher files match the reviewed publisher parent. With
those two additions and the two completion records excluded, every tracked
file matches exact incoming main. The compared Git blob identities are:

| Preserved file | Git blob |
| --- | --- |
| `batch-runner/codex_budget_pilot_output.py` | `7c741978a54e76e65ab60ead5f277e1e6499bbdd` |
| `batch-runner/tests/test_codex_budget_pilot_output.py` | `a4d94851bece2a07dc837e6211be165ea12e01e9` |
| `.github/workflows/codex-budget-pilot-ci-cell.yml` | `ea80ca0e49967a4e57c3369a05f2178d73c17177` |
| `batch-runner/codex_ci_input_intake.py` | `cb3b7eaec0c60ebcdf233ee94bd5ee7ec4169431` |
| `batch-runner/tests/test_codex_budget_pilot_ci.py` | `f51aaf9bbe27e3f15dbc7011341adc7f1b2b32f0` |
| `batch-runner/tests/test_codex_ci_hf_originals.py` | `568d31993828cd0bd0990464f4d5b0a6117b69a7` |
| `batch-runner/tests/test_codex_ci_input_bundle.py` | `5e41f81021816ce8331c4a428a551097bfa835b0` |

These comparisons preserve HF-originals intake, the equivalent-path fix and
all other incoming implementation/workflow/test bytes. Parent/blob comparisons
and diff checks are the only integration validation. No test family, static
counter, earlier audit or additional semantic-audit agent was run or awaited.

### Review boundaries and current leader observation

The leader supplied FINAL-APPROVE `5289350726` for publisher head
`0ff95ba41ce7ce961ee333bbcac9f8e3db539697` and reported all nine checks
passed at the initial read. The publisher's historical 66-case result below
remains at `731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`. Redirect review
`5289350480` and all nine exact-head checks apply to
`038f0fa911ec7971e69c03528385019de8c29b5f`, now incorporated through the
supplied main. Its 28-pass result remains at
`44e276163e8a241a0a146304c14c64d7437e6914`. Neither approval nor test result
is relabeled as approval or a test run for this new integration head; its
leader review and automatic final-head checks remain outstanding.

Separately, #664 stays frozen at
`e3653758bff6dde3fadd6e72ff0af5b595566af7`, reviewed in `5289680397`.
Its `46 passed in 52.36s` remains at
`bc088ed8473dae362a76fd866763027f90d2a884`: copy cases use the existing
test-only rename double, while native atomic installation on NAS refused
with `EINVAL` (errno 22); production has no fallback. This is not live
installation or grade-readiness evidence. Its code is not part of this merge,
and neither its branch nor tests were changed or rerun.

The leader dispatched changed-source, model-free HF input-check
[35847871634](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35847871634)
on exact main `b0abe87275e3aa4d403732a6a8de8dacfe591c7e` at
10:16:49 UTC on 2026-09-23. It was **IN_PROGRESS AT LEADER OBSERVATION**
at 10:18:55 UTC, with plan/intake still pending. The supplied inputs were
`input_transport=hf_originals`, canonical cell
`02aa1805-c658-4069-8a6a-02dec146063a_A_r1`, `execute=false`,
`input_check=true`, empty GitHub release/asset IDs, and external bundle SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
This observation is neither success nor failure, accepted inputs nor a pilot
cell result. The run was not queried, awaited, cancelled, rerun or redispatched.
The earlier 307 refusal and separate metadata-only HEAD below remain distinct;
the original CI Location is still unknown. Current input acceptance remains
unestablished by the supplied evidence.

## Preserved publisher unit and offline evidence

`PROJECT5-PRIVATE-CELL-OUTPUT-1740` originally added a plan-first local CLI and
an explicit private HF publication path on a clean branch from exact main
`9cb1c0d84f299f610ec98c90f3bac9ff9cbbdc75`. It does not wire a workflow,
select or approve an output target, change the public completion schema, or
change the grader. No live publication or pilot execution occurred.

### Capability and evidence limits

[The publisher](../../batch-runner/codex_budget_pilot_output.py) accepts one
canonical cell plus the caller's expected campaign, reviewed execution-source
SHA and config SHA256. It uses `codex_budget_pilot.compile_pilot`, the retained
plan/ready/state/config/input bindings, dispatcher lock and owned-cleanup check.
Only a finalized cell with confirmed cleanup is eligible. Existing current-byte
result and deliverable helpers remain the authority: `_finish()` runs on a copy
and its evidence is compared with the retained record. Its status updates are
not applied to the cell. No original input is reopened or rematerialized.

The payload consists only of unchanged bytes under these logical roles:

- The bound condition result, named `step2_inference_results.json` remotely.
- Validated generated files under `deliverable_files/<task-id>/...`.
- The available bound `cost_ledger_condition_a.jsonl` export, with existing
  column/vocabulary, type, run/task, uniqueness and finite-amount validation.
- `output-manifest.json`, containing cell/source/config/input/order/policy
  bindings, observed status/accounting, explicit gaps and logical file hashes
  and sizes. It contains neither a future commit ID nor the output target.

Original parquet/reference trees, native/auth state, transcripts, raw logs,
SQLite and the whole workspace are not publication sources. Unsupported result
fields refuse rather than being silently stripped. Deliverables are treated as
generated content, not scanned or rewritten. Files are bounded to 128 generated
deliverables, 64 MiB each and 128 MiB total; result/ledger records are bounded to
8 MiB, ledger exports to 10,000 rows and the manifest to 128 KiB.

Missing bound results are not replaced with late files found on disk. A plan
reports `can_publish=false` in that case, and explicit publication refuses.
Missing ledger/usage remain explicit; an empty usage object is not evidence
of zero consumption. Failed/stopped status, null exit codes, timeout and partial
accounting stay recorded as such. No cost or token totals, HTTP counts, prices
or grades are inferred. Reasoning is not added to output tokens again.
`grade_ready=false` and `workflow_wired=false` remain unconditional.

Default local validation, with placeholders rather than private locators:

```bash
"$PILOT_OUTPUT_PYTHON" batch-runner/codex_budget_pilot_output.py \
  --campaign-root '<retained-private-campaign-root>' \
  --campaign-id budget_pilot_ci_20260923_01 \
  --cell '<one-canonical-cell>' \
  --reviewed-source-sha '<reviewed-execution-sha>' \
  --expected-config-sha256 '<expected-cell-config-sha256>'
```

This default does not read an HF credential, construct an HF client or transfer
files. Publication additionally requires `--publish`, `--output-repo` and
`--expected-parent`, with an explicit process-local `HF_TOKEN`. Approval is
external caller authority; these arguments are not an approval certificate.
No output repository is supplied or approved by this task.

### Private publication contract

Before its first HF request, publication flushes a private no-clobber one-use
reservation in the selected cell's private directory. Any existing reservation
or receipt, including malformed, partial or unresolved state, refuses replay.
The client checks the exact named dataset repository's actual `private=true`
metadata and expected main-branch commit, then checks the absent
`cell-outputs/<campaign>/<cell>` prefix and its ancestors at that commit.
It never creates a repository, changes privacy, deletes or overwrites files,
chooses an alternate target, merges dataset rows or falls back to public storage.

Existing HF commit-operation helpers build one add-only payload-plus-manifest
commit with `parent_commit` CAS protection. A private completion receipt records
the actual returned immutable commit and metadata read at that commit. A failed
post-check retains a known returned commit but stays unresolved; an ambiguous
commit response is never reconciled by adopting a later HEAD. No result's
`source_revision` is filled from a Git SHA, input revision or guess.

HTTP phase timeouts are at most 30 seconds inside a 120-second publication envelope.
The scoped supported HF HTTP client hook turns failed HTTP/transport responses
into terminal safe errors before SDK backoff can retry or log them. Buffered
immutable operations use that HTTP/LFS path rather than native Xet transfer.
One commit operation is not a promise of one HTTP request.
The guard blocks forwarding the supplied bearer token to another host. Stdout
contains only bounded logical-role/hash/size/outcome metadata; the target and
returned revision remain in the private receipt. Errors retain safe codes and
an actual HTTP status when available, not raw messages, bodies, URLs or paths.

The required extreme-reasoner decision was **APPROVE-WITH-CONDITIONS** before
implementation. Its conditions shaped the read-only `_finish()` comparison,
closed payload validation, flushed one-use reservation, exact-parent commit,
terminal SDK retry guard and unresolved-response handling. It did not approve
a target or live use. Metadata checks cannot make repository privacy atomic
with the commit: a concurrent administrator change is outside this unit's
guarantee. `privacy_atomic_with_commit=false` and `download_verified=false`
remain explicit; no remote payload re-download is performed.

### One focused offline validation

Implementation/tested SHA: `731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`.
Only the new publisher and [its test family](../../batch-runner/tests/test_codex_budget_pilot_output.py)
were committed before this single invocation. `PILOT_OUTPUT_PYTHON` named the
existing isolated Python 3.10.12 interpreter from the known private handoff;
installed `huggingface_hub` 1.24.0 and pytest 9.1.1 were reused without installs.

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_OUTPUT_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_output.py
```

Observed result: `66 passed in 109.70s (0:01:49)`, exit 0. This is pytest wall
time, not model or live transfer latency. Synthetic finalized cell records and
fake HF metadata/commit/HTTP responses exercise the real CLI, canonical compiler,
result/file validation, hashes, manifest, no-clobber writes and commit operations.
The fixture blocks sockets, subprocesses, dispatch, original-input reads,
execution admission and sleep. The real scoped HF client guard is tested at a
fake HTTP transport boundary, including SDK backoff refusal; no live HF client
request or credential store was used.

Coverage includes default no-network/no-token planning; cell/source/config and
retained-input/cleanup refusal; current-byte/type/link/size checks; closed result
and ledger fields; unchanged allowlisted bytes; private/existing-parent/prefix
gates; actual returned-commit receipt binding; failed/stopped/missing/partial
accounting; HTTP, lost-response, interruption, timeout and receipt-write failures;
and refusal to replay complete or partial reservations. Neither the reader 31,
error-context 19, native-host 71 nor any previous/full family was rerun. The
original post-test edits changed only the two completion records. This merge
adds the reviewed incoming main bytes without rerunning tests; the 66-case
result is not a pass for the integration head. Review scopes are recorded above.

### Accepted lifecycle gap and separate history

The accepted read-only lifecycle trace established that Step2 and `_finish()`
leave generated deliverables, result and ledger bytes on the cell-local runner.
The single-cell workflow uploads only nonsecret completion metadata. Those
hashes do not preserve the bytes after runner teardown. This task did not repeat
that trace. The standalone publisher is not yet invoked there, so it establishes
neither durable CI outputs nor recovery after a lost job.

Same-job grading is also not ready: the existing local schema2 requires an
actual inference HF repository/revision, and the parent grading materializer
does not accept arbitrary pilot cells. This unit supplies a future private
receipt boundary; it neither relaxes that schema nor admits pilot IDs to it.

Prior #661 review `5288470314` applies only to HF-originals intake head
`fcfe5feb7698af78c18d5257807fc0ee0d4351ff`. Its `71 passed in 3.68s` evidence
remains at `fbd038173aa36d67bda8d0aad3f3ecb35aa7c8af`, not a live HF access
observation or this publisher's test result. The reviewed intake and subsequent
redirect fix enter this merge from exact main without modification; no prior
family was rerun. The prior reader review `5287940874` applies to
`3659287caf89c013818d052b54524723e30ac6f3`, not this integration head.

The leader's separate input-check run `35827845408`, job `107073437115`, on
`427a03223fb7c70eb8070fff85fdde8bcfcfac0d` failed at 06:42:45 UTC with
`github_draft_or_asset_inaccessible`, `stage=release_metadata`,
`http_status=403`, exit 2. Plan passed; download/import and OIDC/native work
were not reached. The earlier `35821215749` grouped-error failure, initial
HTTP 400 upload with lost error detail, later private upload of asset
`582945947` to draft `394272629`, and connected native diagnostic
`35817078746` remain distinct observations. None was repeated or queried here.
Owner-account staging does not establish CI token access; the connected
diagnostic is not pilot `xhigh`, file/recovery evidence or a grade. The
[prior immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/9cb1c0d84f299f610ec98c90f3bac9ff9cbbdc75/tasks/LATEST_TASK_RESULT/README.md)
and preserved changelog entries retain their detailed evidence and earlier
tested/reviewed SHAs. No underlying account, credential or permission cause is
inferred from the 403.

### Controls and remaining work

Both campaign identities, sealed NAS source, original inputs and all 30 NAS
pending cells remain untouched. The registered CI cohort/order, common host,
SDK/runtime/settings, GPT-5.4/direct-v1/xhigh, fixed grader and A/B/C retention
and feedback distinctions are unchanged. A still has at most four attempts;
the cumulative 180-minute and per-attempt 30-minute model limits, and the
240-minute CI job ceiling, are unchanged. Publication bounds are separate.

Remaining: new integration-head review and automatic final-head checks; actual
HF input acceptance; approved private output-target readiness and private
workflow wiring before any paid cell; actual output publication; later
integration/use of the separately frozen #664 adapter with an observed output
revision; ordered 30-cell execution and cross-run admission/deduplication; and
fixed grading. The local publication reservation is not a remote inference-
admission lock. No target readiness, live HF access, durable CI output, model
result or graded quality is established here. The leader retains live-run control.

The original unit's design guidance kept transport separate from experiment
controls. This record-only integration uses `experiment-report-en` and
`im-not-ai-en` to keep synthetic tests, accepted source findings, prior reviews
and live-history observations separate without strengthening their claims.
No additional audit agent or CI/review wait was used. Standing budget authority
is unchanged.

## Preserved incoming redirect fix and observations

The intake now accepts the observed equivalent encoding of an immutable Hub
cache member, while retaining the exact repository/revision/member identity.
The independent redirect-fix branch started at
`ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`. Code and tests were committed at
`44e276163e8a241a0a146304c14c64d7437e6914` before the one offline test run.
Subsequent completion-record edits are not another test run or final-head
approval. No workflow, dependency, permission, credential or experiment
control changed in that fix. Then-frozen #662 was not edited or retested there.

### Original failure and separate metadata observation

The leader supplied the failed model-free input-check
[35841798539](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35841798539),
job `107118366778`, on exact source
`ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`. At 09:17:25 UTC on 2026-09-23,
intake reported `hf_original_redirect_refused`, `stage=hf_reference_1`,
`http_status=307`. Plan creation passed; OIDC, identity and model steps were
skipped. This remains a redirect refusal, not evidence of invalid HF
credentials. Its receipt was neither replaced nor rerun.

One separately authorized HEAD used the genuine `_hf_origins` and `hf_hub_url`
to derive exactly that registered reference-1 URL from
`openai/gdpval@11e7900cdcac61bc4daf59e65feb238acda98fbf`. The request began
at 09:25:38.658426 UTC on 2026-09-23 and returned HTTP 307 in 0.25118 seconds,
within its 20-second limit. It was unauthenticated, with no HF token/cache
credential, ambient proxy, redirect following or response-body read. There
was one request, zero followed redirects and zero body bytes read. The
one-use reservation and raw request/Location metadata remain private.

The Location was relative and resolved to the canonical HTTPS HF Hub cache
route. A query was present; no fragment was present. Its namespace, repository
and immutable revision prefix matched literally. The registered member has
three components: the redirect represented their two separators as `%2F`
and left parentheses literal instead of `%28`/`%29`. After exactly one decode,
the complete member bytes and component boundaries matched the expected
cache path, with no residual percent escape, traversal, backslash or control
byte. No input URL, query value, header, payload or private locator is
published here.

The base guard rejected that retained Location because it compared the paths
literally. The equivalent-encoding defect is therefore verified for this HEAD
response, not merely assumed. The original CI Location was not captured, so
these later headers are not assigned retrospectively to its receipt. Neither
this metadata-only observation nor the offline patch validation establishes
current authenticated GET access to all four files or live input acceptance.

### Surgical change and preserved gates

[The redirect guard](../../batch-runner/codex_ci_input_intake.py) keeps the
Hub namespace/repository/revision prefixes literal. Only the exact expected
member is compared after one strict percent decode; case differences in
valid escapes do not change its bytes. Raw paths are also checked so URL
joining cannot hide literal dot segments. Malformed escapes, residual percent
signs/double encoding, traversal, duplicate separators, backslashes and
control bytes refuse with the existing closed reason and logical-role/actual
HTTP-status context. A different host, repository, revision or member is not
an equivalent path.

The existing host allowlist and no-bearer-to-CDN rule remain. So do explicit
transport selection with no fallback, plan-only no fetch, all four original
byte pins, offline local verification, importer/ready-last/no-clobber checks,
request/transfer limits and the external canonical archive binding:
2,519,040 bytes, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
No original payload was opened or rehashed, and neither campaign was changed
or rematerialized. The workflow, main/ref/rerun and OIDC/model gates, public
completion envelope, fixed host/model policy, 30-cell order and 180/30-minute
cell/attempt limits are untouched. No real payload was downloaded; no model,
grader or Azure call, workflow dispatch or CI query was made.

### One focused offline validation

Tested SHA: `44e276163e8a241a0a146304c14c64d7437e6914`.
`HF_REDIRECT_PYTHON` resolved to the existing isolated Python 3.10.12
interpreter from the known private handoff. No dependency was installed.
From the feature worktree, the exact selector invocation was:

```bash
env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$HF_REDIRECT_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_ci_hf_originals.py -k redirect
```

Result: `28 passed, 63 deselected in 2.81s`, exit 0, from one invocation.
The 2.81 seconds are pytest wall time, not live transfer or model latency.
Twenty-one new cases and seven adjacent redirect cases use synthetic
provenance/files and a fake HF transport through the real intake CLI. The
shared synthetic fixture gained only opt-in reference filenames; its default
inputs are unchanged. Role derivation, URL/header helpers, deterministic
archive serialization, importer, genuine installed-input readers, byte/hash
checks and no-clobber behavior remain real.

Accepted cases cover the observed encoded separators/literal parentheses,
lowercase escapes, the existing literal path and a subsequent token-free CDN
hop. Refusals cover foreign repositories/hosts, changed or mutable revisions,
encoded identity prefixes, wrong members, malformed/double encoding,
literal/encoded traversal, dot/empty components, backslashes and controls.
The CLI preserves `hf_reference_1`/307 for refused redirects without reading
their bodies or logging private values. Existing bounded-loop and no-response
status cases also passed. No 71/66/31/19 family, full suite, workflow execution,
live input-check or second metadata request was run.

### Historical redirect-review boundary

The leader reported #661 review `5288470314` at
`fcfe5feb7698af78c18d5257807fc0ee0d4351ff` and all nine exact-head checks
passed. Its `71 passed in 3.68s` remains at
`fbd038173aa36d67bda8d0aad3f3ecb35aa7c8af`, not this patch or live access.
The [immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/fcfe5feb7698af78c18d5257807fc0ee0d4351ff/tasks/LATEST_TASK_RESULT/README.md)
preserves the original intake controls, prior reader review, GitHub metadata
403, private staging successes/failures and separate successful native
diagnostic `35817078746`. Those observations remain distinct and were not
repeated here.

At the original redirect-fix observation, #662 was frozen at
`0ff95ba41ce7ce961ee333bbcac9f8e3db539697` with leader review incomplete.
Its `66 passed in 109.70s` belonged to
`731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`; it was not an approval. That
historical observation is retained in the
[incoming immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/b0abe87275e3aa4d403732a6a8de8dacfe591c7e/tasks/LATEST_TASK_RESULT/README.md).
The subsequent approvals of #662 and #663 are scoped above, not assigned
retrospectively to their earlier observations. Current remaining work is
listed in the publisher section. This integration neither authorizes a retry
nor proves durable output or graded quality.

`experiment-report-en` and `im-not-ai-en` kept the original failure, later
metadata, synthetic validation and unknown live acceptance separate without
strengthening their claims.
