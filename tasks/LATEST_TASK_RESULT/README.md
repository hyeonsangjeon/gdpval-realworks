# Latest task result

## Codex diagnostic local-auth failure reporting

The diagnostic now emits its existing `auth_command_produced_no_token`
verdict instead of raising while building the failure record. The focused
offline selection passed at `1dfa5d0879e04c1b32b39d0fb0c5ba5785992e63`:
`13 passed, 116 deselected in 0.34s`, exit 0. This is reporting evidence, not
a successful authentication or connectivity observation.

### Accepted failed observation

Campaign `budget_pilot_20260923_01` used clean source
`0d6ed6d806fc0360434952792d5ab82327290570`. Its one authorized diagnostic
exited 1 after 2.859043 seconds, including confirmed owned cleanup.
Authentication preflight failed before native startup. The existing
`auth_command_produced_no_token` verdict was missing from `VERDICTS`, so
`_record()` raised before stdout/file diagnostic JSON could be emitted.
The underlying auth reason, auth-command exit code and token-production
boolean were not emitted. No model turn was sent; usage, charges and HTTP
counts remain unknown.

The diagnostic authorization is consumed. No authentication or diagnostic
was rerun, credentials were not repaired, and no replacement receipt was
created for that attempt. No diagnostic rerun or replacement receipt is
authorized here. Private evidence and the separate reporting commit
`3fbb1c6cca856b62adc7fe7902f9ebc9f83792a6` remain unchanged.

### Correction and offline evidence

The production change adds the existing verdict to `VERDICTS` while keeping
it out of `VERDICTS_THE_PROVIDER_ANSWERED`, and applies the existing redactor
to `observed.auth_command.reason`, as the plan path already does. The
ran/ok/exit_code/produced_a_token observations, failure exit 1, cleanup,
unknown-verdict rejection and unrun-auth meaning are preserved. Auth paths,
credentials, targets and plan-only defaults are unchanged.

One invocation ran from the repository root with `AUTH_VERDICT_PYTHON`
bound to the existing isolated interpreter prepared with
`openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0`:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$AUTH_VERDICT_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_foundry_connection_probe.py -k 'auth_command_failure_output or vocabulary or provider_spoke or token_shaped or names_are_recovered or what_the_sign_in_said or without_send_request or preflight_that_could_not_run_at_all'
```

The five new cases traverse real `main --send-request --out`, `probe()`,
`_record()` and `_emit()` with synthetic `AuthCommandProbe` observations.
Four failed-auth cases check equivalent parseable stdout/file JSON,
`provider_answered=false`, `thread_started=false`, `turn_sent=false`,
`usage=null`, the original auth fields, redacted token/resource-shaped
reasons, real workspace cleanup and no runtime/thread/network/auth
subprocess calls beyond the auth stub. The unrun-auth case preserves that
meaning and reaches only a synthetic runtime-unavailable boundary, not a
native process. Eight related existing cases check vocabulary, unknown
verdict refusal, redaction and plan semantics. No live authentication,
native app-server, provider or model operation occurred. Both reported
durations are wall times for their respective operations, not task latency.

Only completion records change after the tested SHA; this is not a fresh
test run on the final documentation-bearing commit. The diagnostic script
and its tests are outside the full grader-source closure, so no active hash,
source-count, configuration or historical-result change was needed.

### Review boundary and remaining work

This branch starts from `0d6ed6d806fc0360434952792d5ab82327290570` without a
fetch. Prior #653 review `5283415850` at
`52f67d68f77fbdeaedf345d520713e38f3fc332f` covers the dispatcher, not this
diagnostic fix. Earlier dispatcher and experiment evidence remains under
its original scope in `CHANGELOG.md` and the prior immutable records.
Review of this fix and final carrying-HEAD CI remain outstanding.

The sealed execution source, campaign, original inputs and 30 pending cells
remain untouched; plan/order/config/input identities and clocks are
unchanged. The underlying auth cause and current connectivity remain
unresolved. Pilot execution and grading remain unrun and require separate
leader direction. Standing budget authority is unchanged, with no new
owner-approval wait. No tests beyond the focused selection, dependency
installation, dataset/preparation operation, CI query, Project edit or PR
merge occurred.

Backend/LLM guidance kept the change at the reporting boundary.
Experiment-report-en and im-not-ai-en kept the failed observation, synthetic
tests, missing receipt and prior review within their distinct scopes.
No experiment parameters or UI, workflow, QA or upload code changed.
