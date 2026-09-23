# Latest task result

## Plan-first CI entry for one registered pilot cell

The new CLI selects one canonical cell through the existing compiler and
dispatcher. Its focused offline selection passed at
`cb3e5dd308f769812809249f1c60ed2fdf2ade58`:
`19 passed in 93.52s (0:01:33)`, exit 0. This demonstrates the tested adapter
and workflow contract with synthetic inputs and fake children, not live CI
authentication, model execution, cleanup or graded quality.

### Host decision and implemented boundary

Before any execution, the separate preregistration reserves
`budget_pilot_ci_20260923_01` for the existing repository-OIDC GitHub Actions
path. No real CI campaign has been materialized or run. All A/B/C cells use
the same Ubuntu 22.04, Python 3.10.12 and SDK/companion 0.147.0 policy. NAS
remains the implementation/control host, not the execution identity. The
sealed NAS campaign `budget_pilot_20260923_01`, source
`0d6ed6d806fc0360434952792d5ab82327290570`, its 30 pending cells, original
inputs and plan/order/config/deadline identities remain untouched. Prior
auth and diagnostic authorizations remain consumed; no NAS auth retry ran.

The adapter reuses `compile_pilot()` and `dispatch()` rather than constructing
another matrix. Five `advance_check_5` tasks, A/B/C and repetitions 1/2 still
produce 30 cells in per-task A1/B1/C1/C2/B2/A2 order. Selection happens inside
the real dispatcher admission loop; all 30 retained checkpoints/configs are
validated before the selected child, and the other 29 cells remain unrun.
The original inputs, base prompts, gpt-5.4/direct-v1/xhigh target, context,
tools and fixed grader are unchanged. B/C differ only by C's host error
feedback; A/B changes both retention and attempt policy, so it is not a
retention-only comparison. No effect on quality or efficiency was measured.

Plan-only remains the default. Execution requires an explicit canonical
cell, reviewed source SHA and execute flag, plus the existing input,
C-feedback, runtime, host, connection and route guards. The workflow binds
the source/event/workflow SHA, main ref and same-repository caller before
credentials; OIDC retains `contents: read` and `id-token: write`. Reusable
calls are limited to a same-commit relative workflow from one manual,
single-job caller. Pinned actions and existing repository inputs are reused.
Missing original parquet, reference-only root or canonical Step0 manifest
fails with named roles before OIDC. Their approved transfer is not part of
this slice; no dataset download, substitute fixture or manifest generation
is a production fallback.

Each selected cell stays within one job. The 240-minute job ceiling is
setup/cleanup headroom, not a 240-minute model budget. The existing host clock
still allows 180 cumulative minutes and 30 minutes per attempt; A has at most
four attempts, and B/C retain their common continuation/backoff mechanics.
Same-live-host process restart preserves the original expiry and partials.
Changed runner identity and `GITHUB_RUN_ATTEMPT != 1` refuse. The existing
owned-tree supervisor must confirm cleanup before the cell is released;
unresolved cleanup remains closed. There is no cross-runner native-state
restore or global deduplication of separately created manual workflow runs.

The publication step validates and uploads only a nonsecret completion
envelope: campaign/cell/source/config/input hashes, status, exit/timeout,
observed usage/receipt fields from the existing projection and allowed
artifact hashes/sizes. Missing
values stay null; `invoice_complete=false` and `http_request_count=null`.
No raw auth store, tokens, CODEX_HOME, transcript, private host path or native
state archive is uploaded. Interrupted work remains unresolved rather than
successful. A lost job may also lose the envelope; complete archival or
recovery is not claimed.

### Focused offline evidence

Both invocations used the existing isolated interpreter with
`openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0`, bound to
`CI_CELL_PYTHON`, from this worktree's repository root:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$CI_CELL_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_ci.py -k ci_registered_cell
```

- At `9a9fe8ab47788ac2eb2e101d0b8dd5c5bf6115b9`, collection stopped with
  `ModuleNotFoundError: No module named 'test_codex_budget_pilot'`:
  `1 error in 1.31s`, exit 2. No cases ran. The correction uses the existing
  test package's relative fixture import; no dependency was installed.
- At `cb3e5dd308f769812809249f1c60ed2fdf2ade58`, the same selection reported
  `19 passed in 93.52s (0:01:33)`, exit 0. These are test wall times, not
  model/cell latency. Only the two completion records change after this SHA;
  this is not a new test run on the final documentation-bearing commit.

The tests traverse the real CLI/compiler/dispatcher with tiny synthetic
reference-bearing inputs, fake clocks and fake pipeline children. They
check the full matrix/order, one selected A/B/C cell, all others unrun,
plan-only no-child behavior, identity/input/config drift refusal, same-host
restart without new clocks, automatic rerun refusal, retained partials,
missing receipts and no duplicate receipt on restore. They also check the
existing deadline/lock/owned-tree options and unresolved-cleanup refusal,
strict envelope publication, and the manual/reusable workflow contract.
Process cleanup is instrumented through the existing supervisor boundary;
these tests do not launch or prove cleanup of a new native process tree.
No live auth, native app-server, provider/model, grader, cloud, real dataset
or workflow operation occurred. Previous suites were not rerun.

### Review boundary and remaining work

This clean feature branch starts from
`42c7b8f2f6457463333e386432baceed96182c72`. The required extreme-reasoner
review preceded every workflow edit and approved the bounded decision with
conditions, not runtime or launch readiness. Prior #653 review `5283415850`
at `52f67d68f77fbdeaedf345d520713e38f3fc332f` covers the dispatcher; #654
review `5284861560` at `cd1d3cf6ba168f92b7868495d6e8ff25f731b831` covers
the auth-verdict reporting fix. The leader supplied their integration/check
status; neither review approves this new entry. Prior results remain under
their original scopes below, in `CHANGELOG.md` and immutable Git history.

Full grader source sets remain 37/58. No core, prompt, requirements or other
active source-pin member changed, so no active hash refresh was needed.
Ordered 30-cell scheduling/aggregation, approved original-input transfer,
live OIDC/connection validation, leader-directed execution and fixed grading
remain unfinished. Final implementation review and carrying-HEAD CI are
still required. Owner budget authority is unchanged; this work adds no new
owner-approval wait and authorizes no launch.

Experiment-design kept the host decision separate from the observed-error
intervention and preserved the comparison's limits. Backend/LLM guidance
kept selection, state and cleanup in the existing dispatcher. Reporting and
copyediting guidance kept synthetic evidence, prior reviews and untested
live boundaries distinct.

## Prior diagnostic-reporting record

The following record is preserved from the prior task at its original
source/test/review boundary; its outstanding-review statements describe
that earlier handoff, not this CI entry or the later leader-supplied approval.

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
