# Latest task result

## Local 30-cell completion reader: current-main integration

The local CLI assembles CI completion envelopes into the registered 30-cell
order. Its one focused offline family reported `31 passed in 36.01s`, exit 0,
at `deefb34ad684a00494ef689db86f4c461dbca004`. These are synthetic-envelope
tests, not pilot execution or grading. That evidence was not rerun or relabeled
for this integration.

One ordinary non-squash merge brings exact main
`84c18b778d2e9aa1def9d5f7912ac9f03edaee11` into the reader branch. Only these
two completion records conflicted. Both substantive changelog histories remain;
the reader remains the latest result. No implementation conflict occurred.
The reader and its test retain Git blobs
`79aaf179eea991a2461e67c7cd7501efb1422731` and
`e8d4478a1e48d6e044eccb3373252bca4fbb0c73`, identical to reviewed
`eca512dec96f2d5143e14ff65c37b454e5bdef79`. A whole-tree diff excluding only
those two additions and the completion records confirms that all other code,
workflows and tests match incoming main. This includes private intake, the
60-minute native-host CI ceiling and the native-only diagnostic/corrected sweep
contract. These are byte-identity checks, not a test run.

Leader FINAL-APPROVE `5287148513` applies to the pre-integration reader HEAD,
not this new merge. The leader reports that #658's reviewed
`7a4711f319f57d56e71678f85f0a110fd78f5546` passed all nine checks before
integration into the incoming main. Review `5286955706` covers that earlier
intake, CI ceiling, integration and staging scope, not a later error-context fix.
No CI query, live operation or repeated document audit was performed here.

### Reader behavior and limits

[The reader](../../batch-runner/codex_budget_pilot_results.py) calls
`codex_budget_pilot.compile_pilot` for the canonical cohort, cell order and
config identities, and `codex_budget_pilot_ci.validate_completion` for the
existing closed envelope contract. It does not materialize a plan, open original
inputs, construct a provider or call the CI execution-context guard.

- The denominator is always five `advance_check_5` tasks x A/B/C x repetitions
  1/2 = 30. Rows follow the compiler's per-task A1/B1/C1/C2/B2/A2 order regardless
  of file order. Each envelope's other-29-unrun declaration is local to that job;
  30 envelopes do not create a denominator of 900.
- Missing envelopes produce `NOT_OBSERVED` rows with null execution, cleanup,
  receipt, usage and artifact observations. An observed `pending` envelope is
  distinct from no envelope. Failed, stopped and unresolved cells remain in the
  denominator; a reported success does not establish cost completeness or quality.
- Before publication, the reader checks the producer's payload checksum and
  matching campaign, caller-supplied reviewed source SHA, canonical config,
  declared inputs, order, registration and common host-policy fingerprints.
  Duplicate cells are rejected even when their records are identical. Foreign cells,
  mismatches, malformed JSON and non-allowlisted fields also refuse.
- Any non-null `verified_inputs_sha256` requires an external
  `--expected-verified-inputs-sha256` expectation matching the existing reader's
  `files_sha256`. This is not the transfer archive's SHA. The first envelope is
  not its own trust anchor; absent input proof remains null rather than being
  filled from the expectation. This unit does not reverify original bytes.
- Different CI jobs may carry different plan hashes. Completion v1 omits the
  plan preimage and runner-instance binding, so their independent verification
  is explicitly unavailable. The receipt preimage is likewise unavailable.
  The source SHA is a caller assertion, not review approval issued by this CLI.
- Only validated execution/cleanup fields, per-cell receipt/usage/cost fields
  and artifact hashes/sizes are projected. No filenames, private host paths,
  native/auth state, guessed prices, HTTP counts or grades are published. No
  token or cost totals are computed: thread-total and most-recent-request views
  are not combined, and reasoning is not added to output again. Missing cost
  stays missing; a genuine recorded zero is not assigned to other cells.

The CLI reads at most 30 explicit local files, each at most 64 KiB, without
following links or accepting a changed file. Its JSON result is bounded to
2 MiB. The existing no-clobber helper writes complete bytes before atomically
linking the absent output file; that single file is the ready publication.
Existing partial or complete destinations are retained and refused, not adopted.
Stdout and the output file contain equivalent JSON. Errors use closed codes
without input filenames or exception bodies.

This is a reader, not a scheduler, remote admission lock or execution receipt
issuer. Rejecting duplicate local envelopes does not deduplicate remote runs.
It does not rank A/B/C, regrade low scores or establish that any pilot cell ran.

Example interface, with explicit placeholders rather than private locators:

```bash
"$PILOT_RESULTS_PYTHON" batch-runner/codex_budget_pilot_results.py \
  --reviewed-source-sha <reviewed-execution-sha> \
  --expected-verified-inputs-sha256 <external-files-sha256> \
  --envelope <local-cell-completion.json> \
  --out <absent-local-result.json>
```

Repeat `--envelope` for additional distinct cells. With no envelopes, omit the
input expectation to report 30 `NOT_OBSERVED` rows; this creates no campaign.

### Exact offline evidence

The implementation and [test family](../../batch-runner/tests/test_codex_budget_pilot_results.py)
were committed at `deefb34ad684a00494ef689db86f4c461dbca004` before this single
invocation from the source root. `PILOT_RESULTS_PYTHON` names the existing
isolated interpreter from the private handoff, the prior Python 3.10.12 and
SDK/companion 0.147.0 environment. No package was installed or runtime guard
retested.

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_RESULTS_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_results.py
```

Historical result: `31 passed in 36.01s`, exit 0. Every case exercises the real
CLI; the compiler, completion projection/validator, checksum and atomic
publication helper remain real. Host-instance and input fingerprints, statuses,
receipts and artifacts are explicitly synthetic. Dispatch, original-input
readers, child-process, network and sleep boundaries are blocked by the fixture.

The family covers empty, sparse and full 30-cell inputs; canonical order with
distinct CI instances; duplicate/foreign/mismatched refusal; failed, partial,
null and recorded-zero accounting; no token double-counting; malformed/private
fields; bounded local reads; and existing-output and final-link collision
refusal. The 36.01 seconds are pytest wall time, not native latency or model
consumption. Only the two new reader/test files changed before that validation;
later record edits and this integration do not turn it into a later-HEAD run.

### Separate observations supplied by the leader

The leader read completed [diagnostic run 35817078746](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35817078746),
job `107040793256`, artifact `10731833980` (`codex-foundry-connection`), on exact
main `0f0911b435d7f704db8e2f2131a00ade310d5c1f`. The plan and result both have
settings fingerprint
`sha256:af46cb5548b7224a3c0117b37a450fced3765efdc4ed2b6c12994376c9462150`.

The supplied result is `connected`, `provider_answered=true`. Auth-command
`ran`, `ok` and `produced_a_token` are true, with exit 0; `thread_started` and
`turn_sent` are true, `turn_status=completed`, and `final_response_present` and
`matched_instruction` are true. `error=null`, `tools=false`, `served_model=null`.
Five legacy probes were skipped.

| Runtime-reported view | Input tokens | Cached input | Cache-write input | Output tokens | Reasoning output |
| --- | ---: | ---: | ---: | ---: | ---: |
| `thread_total` | 10,982 | 0 | 0 | 29 | 22 |
| `most_recent_request` | 10,982 | 0 | 0 | 29 | 22 |

These are two views of the observation, not additive charges. Reasoning output
22 is part of output 29, not 29 + 22. The observed `model_context_window` is
258,400. Requested deployment/route were `gpt-5.4`/`direct-v1`, with pinned
SDK/companion 0.147.0. These were diagnostic defaults, not pilot `xhigh` or the
supervisor's Astra 1M. This establishes connectivity for that CI diagnostic,
not NAS authentication, benchmark recovery, tool/file execution or graded
quality. HTTP count, price and invoice remain unestablished; token refresh may
involve more than one HTTP request. No pilot envelope was ingested from it.

The leader also supplied an independent owner-account metadata observation:
release `394272629` remained `draft=true`; asset `582945947` was `uploaded`,
2,519,040 bytes, with provider digest
`sha256:757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
That matches the external bundle pin, which remains the trust anchor for later
intake. This task did not retrieve, upload, import or repackage the payload.
Owner-account metadata is not evidence of CI token access. The original HTTP
400/exit-1 upload and lost error explanation remain historical, not repaired or
replaced by the later successful upload/metadata observation.

The leader subsequently reported [intake run 35821215749](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35821215749),
job `107053260372`, on `84c18b778d2e9aa1def9d5f7912ac9f03edaee11`.
Plan creation passed; at 05:11:35 UTC intake printed
`Private input intake refused: github_draft_or_asset_inaccessible` and exited 2.
Azure login, OIDC identity verification and execution were skipped. That grouped
reason does not reveal the actual HTTP status or whether release metadata,
asset download or the CDN hop failed. It does not establish expired credentials,
a missing asset or a need for write permission. CI input acceptance remains
unproven; the intake, diagnostic and asset were not queried or retried here.

### Source, review boundaries and remaining work

The reader originally branched from exact main
`0f0911b435d7f704db8e2f2131a00ade310d5c1f`. This integration preserves that
history and the incoming #658 history through a normal merge of exact
`84c18b778d2e9aa1def9d5f7912ac9f03edaee11`. One source fetch was needed.
The [immutable prior reader record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/eca512dec96f2d5143e14ff65c37b454e5bdef79/tasks/LATEST_TASK_RESULT/README.md)
retains the original implementation/test scope. The [incoming #658 record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/7a4711f319f57d56e71678f85f0a110fd78f5546/tasks/LATEST_TASK_RESULT/README.md)
retains its original tested/reviewed SHAs, cancelled 45-minute CI envelope,
60-minute correction and distinct staging attempts. The unchanged changelog
entries preserve the earlier dispatcher, auth-reporting, one-cell, bundle and
native-only scopes. No historical pass is claimed as an integration-head pass.

Both campaign identities, the sealed NAS source and all 30 NAS pending cells
remain untouched. The CI campaign was not materialized or run by this task.
Original inputs, per-task order, GPT-5.4/direct-v1/xhigh,
model/provider/effort/context/tools, fixed grader and common CI host policy are
unchanged. A retains at most four fresh attempts; B/C share retained continuation
and backoff, with only C receiving host error feedback. The 180-minute cumulative
and 30-minute attempt limits and 240-minute cell-job setup/cleanup ceiling remain
unchanged. No efficacy or causal improvement is inferred from a reader test or
the separate connectivity diagnostic.

Remaining work: review and final checks for this integration; safe intake error
context and a separately directed follow-up for CI input acceptance; ordered
30-cell execution and cross-run admission/deduplication; fixed grading after
execution. Standing spend authority is unchanged. No workflow dispatch, auth,
model, grader, cloud API, payload transfer or CI query was performed here.

The original experiment-design review preserved the 30-cell denominator and
control boundaries. Reporting and English copyediting keep the historical
synthetic tests, supplied live observations and remaining unknowns separate.
