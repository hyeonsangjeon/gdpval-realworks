# Latest task result

## Safe HTTP context for private input refusal

The intake still fails closed with its existing reason codes and exit 2. Its
request errors now reach the real CLI log with a closed transfer stage and the
numeric HTTP status actually received. A failed request with no response reports
`http_status=null`; it does not inherit a successful earlier hop's status.

One focused offline invocation reported `19 passed, 62 deselected in 2.38s`,
exit 0, at `d3a4f3430e7554a93d4a6486cfbf11f64b15ba0e`. No live intake,
authentication, native diagnostic or model operation was performed. This patch
cannot recover the unrecorded status or cause of the earlier failed run.

### Actual failed gate, supplied by the leader

[Run 35821215749](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35821215749),
job `107053260372`, used exact source
`84c18b778d2e9aa1def9d5f7912ac9f03edaee11`. Plan creation passed. At
05:11:35 UTC, intake printed:

```text
Private input intake refused: github_draft_or_asset_inaccessible
```

It exited 2. Azure login, OIDC identity verification and execution were skipped.
The old grouped error does not identify whether release metadata, asset download
or the CDN hop failed, or which HTTP status was received. It does not establish
token expiry, a missing asset, insufficient permissions or a need for write
access. Those fields remain unknown for that observation. No run, draft metadata
or asset was accessed again in this task.

### Narrow implementation boundary

[The intake](../../batch-runner/codex_ci_input_intake.py) adds the context to its
existing exception and logging path, without another request or logging system:

- The stage vocabulary is exactly `release_metadata`, `asset_download` and
  `asset_redirect`. The last value identifies the allowlisted CDN request.
- Received HTTP 401/403/404 still map to
  `github_draft_or_asset_inaccessible`; other disallowed response statuses keep
  `github_response_status_refused`. The reason prefix and failure exit remain
  compatible. Pre-transfer validation outside this request boundary is unchanged.
- A request that raises before a response has null status. A body-read failure
  after receiving HTTP 200 retains 200 while still failing; this is a received
  response code, not proof of completed transfer or accepted inputs.
- Only the fixed stage and numeric status join the existing closed reason.
  Raw bodies, URLs/signed queries, headers, tokens, private credential/host paths
  and arbitrary exception strings are never added to the log. HTTP refusal
  bodies remain unread, and owned response handles close before returning.
- Same-repository ownership, draft/asset checks, target/redirect rules,
  authorization stripping on the CDN hop, external size/SHA authority,
  transfer bounds, no-clobber reservations and genuine importer gates remain.
  Failed reservations are retained, not silently adopted. Default plan-only,
  workflow inputs/permissions, OIDC admission and model limits do not change.

For illustration only, the offline synthetic 403 case emits:

```text
Private input intake refused: github_draft_or_asset_inaccessible (stage=release_metadata, http_status=403)
```

This is not a reconstructed receipt for run `35821215749` or evidence that its
response was 403. There is no fallback, credential repair or permission change.

### One targeted offline invocation

The feature worktree starts independently at exact main
`84c18b778d2e9aa1def9d5f7912ac9f03edaee11`, not from #659. Only the intake
module and [directly affected tests](../../batch-runner/tests/test_codex_ci_input_intake.py)
changed before validation. They were committed at
`d3a4f3430e7554a93d4a6486cfbf11f64b15ba0e` before this single command:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$INTAKE_ERROR_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_ci_input_intake.py -k error_context
```

`INTAKE_ERROR_PYTHON` names the already installed isolated interpreter from the
existing private handoff; no dependency was installed. Result:
`19 passed, 62 deselected in 2.38s`, exit 0. The elapsed value is pytest wall
time, not transport latency or model consumption. Later completion-record edits
do not relabel this as a test at a different SHA.

The selection covers 12 HTTP-error combinations (401/403/404/500 at each of the
three stages), three no-response failures, three interrupted body reads after
HTTP 200 and one closed-vocabulary refusal. The real `main` -> intake -> request
-> error-log path runs against fake GitHub I/O and explicitly synthetic tiny
input fixtures. Tests assert exact safe CLI messages, no retry or extra request,
no raw/private output, closed responses, retained reservations, absent staged or
installed payloads and zero input-verifier calls. These failures precede the
importer. The CDN tests retain
the no-Authorization assertion. The existing offline fixture blocks real network,
child-process and sleep boundaries. No workflow or live input-check ran.

### Preserved integration and review scopes

Before this independent patch, one ordinary non-squash merge brought exact main
`84c18b778d2e9aa1def9d5f7912ac9f03edaee11` into #659 as
`b1b0a74d99060bd7011cc561fcf089f00da3356c`. Only the two completion records
conflicted. The reviewed reader/test blobs remained byte-identical to
`eca512dec96f2d5143e14ff65c37b454e5bdef79`; every other implementation,
workflow and test matched incoming main, including private intake, the
60-minute native-host CI ceiling and native-only diagnostic/corrected sweep
contract. Both changelog histories were preserved and the reader stayed latest
there. That integration was pushed and no longer edited; no test or CI query
accompanied it. Its [immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/b1b0a74d99060bd7011cc561fcf089f00da3356c/tasks/LATEST_TASK_RESULT/README.md)
contains the blob identities and the original reader evidence.

#659 FINAL-APPROVE `5287148513` remains scoped to
`eca512dec96f2d5143e14ff65c37b454e5bdef79`. Its `31 passed in 36.01s` result
remains at `deefb34ad684a00494ef689db86f4c461dbca004`, not the integration
HEAD or this fix. #658 review `5286955706` at
`7a4711f319f57d56e71678f85f0a110fd78f5546` covers the prior intake,
CI-envelope correction, integration and staging scope. The leader reported all
nine checks passed before that source reached the current main. The
[prior #658 record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/7a4711f319f57d56e71678f85f0a110fd78f5546/tasks/LATEST_TASK_RESULT/README.md)
retains the original 67-case evidence, the cancelled 45-minute CI envelope,
the one-case 60-minute-ceiling correction and the distinct staging attempts.
None of these historical tests or reviews approves the new error-context patch
or establishes successful CI input acceptance. No prior family was rerun.

The leader-supplied successful native diagnostic `35817078746` on
`0f0911b435d7f704db8e2f2131a00ade310d5c1f` remains connectivity evidence for
that separate diagnostic, not pilot execution or grading. The independently
observed private draft `394272629` / uploaded asset `582945947`, 2,519,040 bytes
with provider digest
`sha256:757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`,
remains owner-account staging evidence, not proof of CI read-token access. Neither
was queried or repeated. The original HTTP 400 upload and lost error explanation
remain historical; this patch does not replace that receipt either.

### Remaining work

The new patch and #659 integration need their own final-head review/checks.
After review and final CI, the leader will decide a bounded follow-up for CI
input acceptance; none is run here. Ordered 30-cell execution, cross-run
admission/deduplication and fixed grading remain unfinished. The result reader
does not supply those execution guarantees.

Both campaign identities, all prior pending cells, original inputs, source
bindings and sealed state remain untouched. The registered order, A/B/C
controls, common CI host policy, 180-minute cumulative / 30-minute attempt
limits and fixed grader are unchanged. No workflow, auth, cloud, payload
transfer, native/model or grader operation was performed; CI was not queried.
Standing spend authority is unchanged, and no new approval wait is introduced.

Reporting and English copyediting preserve the distinction between the failed
live gate, synthetic error-context tests and unknown cause/status. No experiment
axis or live-readiness claim was added.
