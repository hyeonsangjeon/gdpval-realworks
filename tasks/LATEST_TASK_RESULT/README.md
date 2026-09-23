# Latest task result

## Private single-cell output publisher: standalone offline unit

`PROJECT5-PRIVATE-CELL-OUTPUT-1740` adds a plan-first local CLI and an explicit
private HF publication path on a clean branch from exact main
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
error-context 19, native-host 71 nor any previous/full family was rerun. Only
the two completion records changed after this test; no later-HEAD test pass or
review is claimed.

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

Frozen #661 review `5288470314` applies only to HF-originals intake head
`fcfe5feb7698af78c18d5257807fc0ee0d4351ff`. Its `71 passed in 3.68s` evidence
remains at `fbd038173aa36d67bda8d0aad3f3ecb35aa7c8af`, not a live HF access
observation or this publisher's test result. That branch, workflow and tests
were not changed, queried or rerun. The prior reader review `5287940874`
applies to `3659287caf89c013818d052b54524723e30ac6f3`, not this new source.

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

Remaining: this source's leader review and automatic final-head checks; one
separately directed live HF input check; approved output-target readiness before
any paid cell; private workflow wiring; the canonical pilot grading-input adapter
using an observed output revision; ordered 30-cell execution and cross-run
admission/deduplication; and fixed grading. The local publication reservation is
not a remote inference-admission lock. No target readiness, live HF access,
durable CI output, model result or graded quality is established here.

Design guidance kept transport separate from the experiment controls. English
reporting/copyediting kept synthetic tests, accepted source findings, prior
reviews and live-history observations separate. No additional audit agent or
CI/review wait was used. Standing budget authority is unchanged.
