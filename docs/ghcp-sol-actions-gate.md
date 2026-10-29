# GHCP Copilot CLI agent + GPT-5.6 Sol

## Model-free Step8 input bridge, 2026-10-29

The `grader-contract` job follows all five dry-capture matrix jobs on the same
GitHub-hosted `ubuntu-24.04` workflow run. It downloads only that run's five
`ghcp-sol-dry-capture-*` artifacts and invokes
`batch-runner/ghcp_sol_grader_contract.py` with an empty inherited environment,
offline data settings, allowlisted runner metadata and a 120-second deadline.
It does not invoke the installed Copilot CLI, a judge or `step8_grade.py`'s main
entrypoint. No secret reference or new authentication source is introduced.

The bridge requires exactly the fixed five capture files, with the existing dry
schema, empty/nonprivate contents and eligible runner metadata. Missing, extra,
malformed, linked, changed or non-model-free inputs refuse with exit **2** and
a fixed reason. It writes an explicitly empty
`workspace/step2_inference_results.json` and task directories under
`workspace/upload/deliverable_files/`, then imports the **unchanged Step8**
reader and validators. Checks cover the frozen GHCP grading policy/template,
`validate_grading_config`, `load_local_inference_results`, `filter_tasks`,
`validate_local_deliverables` and `resolve_deliverable_dir`. The Step8 source,
template and input-manifest helper hashes are checked, including after use.
Grader/rubric-loader construction, network, subprocess and provider-SDK effects
are refused during validation; no rubric download or renderer runs.

| Check | Model-free outcome | What it does not prove |
| --- | --- | --- |
| Five captures and Step8 filesystem/manifest layout | `step8_layout_valid=true` | Real answers, deliverable content or rubric bytes |
| Existing pinned policy syntax | `grader_policy_valid=true` | A materialized five-task grading identity |
| Live inference/full-220 identity validation | Expected refusals retained | A dry capture cannot reuse the full-220 rerun identity or invent an inference SHA |

Success is **`model_free_layout_verified`**, not gate stage 5 passing:
`ready_for_grading=false`, `gate5_passed=false`, `paid_execution_allowed=false`.
All five manifest rows remain `pending`; inference identity, grade and usage are
unset, with usage/cost status **`not available`**. The separate live blockers
are real answers/rubric not captured, missing inference identity and the
unmaterialized five-task grading identity. These are not hidden by the layout
job's successful exit. Frozen plans, graders, templates and limits are unchanged.

The job uploads only `grader-contract.json` and the empty manifest, with input
and manifest SHA256s, actual runner metadata, checks and live refusals. It does
not upload a private input, credential, transcript or score. The earlier CI
artifact allowlist below is extended only by these two nonsecret files.

Local fixture validation, one combined invocation: **689 passed, 0 failed,
0 skipped**, **60.29 seconds**, exit **0** (previous 640 plus 39 bridge and 10
new-job guard cases). This is offline synthetic evidence, not a NAS benchmark
execution. Evidence: `/tmp/p5-ghcp-grader-contract.2zzJok/full.log` and
`full.junit.xml`; the source-specific Actions result is collected after the
authorized normal push, not inferred from local tests.

Authentication recap: the job's automatic installation token is not documented
as a supported Copilot CLI user token. A protected environment can instead hold
a personal fine-grained PAT (**Copilot Requests** permission), OAuth or GitHub
App user-to-server token; classic PAT is unsupported. See the official sources
in [the authentication table](#actions-authentication-variable-name-is-not-token-type).
Recommendation remains a short-lived personal fine-grained PAT, subject to owner
selection; this model-free workflow supplies none of these tokens.

One-line owner-decision draft, **not an approval**:
> 보호 environment에 Copilot Requests 권한·만료가 있는 개인 fine-grained PAT를 공급하고 작업 후 폐기하며, 유료 실행은 별도 승인한다.

## Current host policy and model-free Actions route, 2026-10-29

The owner's **2026-10-29 09:20** host decision supersedes every historical NAS
execution approval below. **NAS/container directories are dry-run and development
only**, not a smoke, model, grading or paid-gate host. The active target is a
**GitHub-hosted `ubuntu-24.04` runner**. The old NAS route is not an approved
fallback. No Azure VM route is enabled by this change.

`ghcp_sol_runner_environment.py` reads only the allowlisted `GITHUB_ACTIONS`,
`RUNNER_ENVIRONMENT`, `RUNNER_NAME`, `RUNNER_OS`, `ImageOS`, `ImageVersion`, and
the actual OS release/platform. Execution requires literal `true`,
`github-hosted`, Linux, `ubuntu24`, Ubuntu `VERSION_ID=24.04`, and valid nonempty
runner/image identifiers. Missing or conflicting evidence refuses with
`execution_environment_refused` before authentication, catalogue/binary reads,
task-directory creation or subprocess launch. All `run_task` modes share the
guard, including the separately bound CONNECTED smoke and fixed-task command
path; there is no CLI bypass flag. A final snapshot mismatch before spawn
refuses with `execution_environment_changed` and retains the refusal receipt.

Both execution and dry-capture receipts contain runner name, OS, image version
and the admission result. These are **locally observed runner metadata, not
cryptographic host attestation or proof that Sol/Max/1M was served**. Unit tests
inject synthetic hosted metadata and still whitelist only fake executables;
their receipts are not observations of a real Actions host. The Actions job
separately retains its actual `runner.json` before running those tests.

### What the workflow can do

The workflow lookup returned HTTP **404** on 2026-10-29. Its exact branch-only
push trigger is `leader/ghcp-sol-gate-actions-20261024`, with gate-code/test/
workflow path filters. It retains the explicit `dry_run=true` dispatch guard;
push is always model-free. No PR trigger or paid mode was added.

The first job requires Ubuntu 24.04, installs pinned test-only dependencies,
downloads **Copilot CLI 1.0.103**, checks archive and executable SHA256, and runs
**only `--version`** in a new HOME with an empty inherited environment and
auto-update/telemetry disabled. The complete offline gate suite runs once under
`env -i`. A separate synthetic-token projection checks supported-source routing
and missing-source refusal with subprocess/network calls disabled; it never
hands the fake value to the installed Copilot executable. Subsequent jobs
exercise the fixed-five empty dry-capture path. No private task inputs, model
requests, login, secret references, token issuance or actual five-task gate is
part of this workflow. Captured usage/cost remain `not available`.

The only retained CI artifacts are actual runner metadata, CLI version output,
JUnit, and each task's nonsecret `capture.json`; no state directory or transcript
is uploaded. CI has `contents: read` only and checkout credentials are not
persisted. The CLI never inherits a job token. Limits remain 1,200 seconds,
64 observed turns and the existing explicitly selected 32-tool smoke cap.

Release source: [v1.0.103](https://github.com/github/copilot-cli/releases/tag/v1.0.103),
public release API checked 2026-10-29. Linux x64 archive SHA256 is
`9aeb4430e9ac9523546db07b227c7aba179a4710a55f9ac29ad143b0f9e1b325`;
the existing executable pin remains
`f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d`.

Design boundary: the intervention is host admission/CI wiring, not a model or
quality comparison. Cohort, requested model/settings and execution limits stay
fixed. The classifier is tested against missing/spoofed labels, OS conflicts,
self-hosted metadata and pre-spawn drift. Inputs/tokens are synthetic. A failed
host, version or offline test blocks subsequent jobs; no model retry is made.
Passing this rehearsal does not establish paid readiness, authentication,
stream completeness or the live setting evidence still required by the gate.

### Actions authentication: variable name is not token type

Public documentation checked **2026-10-29**, without reading any token value or
testing authentication/model endpoints:

| Candidate | Documented contract | Decision for this card |
| --- | --- | --- |
| Automatic job `GITHUB_TOKEN` | An installation access token, scoped to the workflow repository; not a personal fine-grained PAT or user-to-server token | Copilot CLI's supported-token table does not establish support for this type or a Copilot entitlement. **Unverified; do not use for the model gate.** The accepted environment variable name alone is insufficient. |
| Protected environment secret containing a personal fine-grained PAT | Personal-account owner, **Copilot Requests** account permission, finite expiry; explicitly inject as `COPILOT_GITHUB_TOKEN` only after owner selection | Recommended supply option for owner review; **not configured or supplied** here. Revoke the PAT after the approved window and remove the secret; deletion alone is not revocation. |
| Other supported user tokens | OAuth (`gho_`) and GitHub App **user-to-server** (`ghu_`) are also documented; classic PAT (`ghp_`) is not | A fine-grained PAT is **not the only supported token type**. Alternatives still need owner-approved identity, secure supply, lifetime and entitlement; no source was selected or extracted. |

Sources: [Copilot CLI authentication / supported token types](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli#supported-token-types),
[environment-variable authentication](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli#authenticating-with-environment-variables),
[Actions GITHUB_TOKEN contract](https://docs.github.com/en/actions/concepts/security/github_token),
[environment protection](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).
The installation-token versus user-to-server distinction is intentional;
neither the variable name nor a successful GitHub API request proves Copilot
model access. This is a documentation conclusion, not a live authentication test.

Owner decision draft (not an approval):
> 보호 environment에 개인 소유·Copilot Requests 권한·만료일이 있는 fine-grained PAT를 공급하고, 승인된 작업에서만 `COPILOT_GITHUB_TOKEN`으로 주입하는 안을 선택합니다. 작업 뒤 PAT를 폐기하고 secret도 삭제합니다.
> job별 `GITHUB_TOKEN` 경로는 Copilot 지원 근거가 확인될 때까지 보류합니다. 이번 성공은 model-free CI뿐이며 스모크·5문제·유료 실행 승인은 별도로 결정합니다.

The earlier investigations and NAS outcomes below are historical records only.

## Owner-file authentication and entitlement, 2026-10-27

| Existing gh login: general Copilot entitlement | Read-only endpoint | HTTP | Plan |
| --- | --- | ---: | --- |
| **Yes** | `GET https://api.github.com/copilot_internal/user` | **200** | **enterprise** |

This authenticated metadata GET used the existing stored gh login, without
inheriting token environment overrides. Only the verdict, endpoint, HTTP status
and plan were retained; raw response/headers/error output were discarded. The
installed schema describes the general chat entitlement and plan fields
(`schemas/api.schema.json:12550,12554` in the packaged 1.0.79 reference).
No token-export, token-issuance or completion endpoint was called. This confirms
general Copilot entitlement only, not CLI acceptance, a particular model's
availability, applied Sol/Max/1M settings or billing identity. The endpoint is
an internal GitHub entitlement surface, not a promised stable public API.

The adapter now selects all supported authentication sources in one place.
With explicit `--auth-source COPILOT_GITHUB_TOKEN_FILE`, that variable is an
absolute file locator, not a token value. The file must be regular, single-link,
owned by the runner UID, exactly **0600**, nonempty and at most **8192 bytes**.
No symlink ancestor, traversal, source-tree or capture-tree location is accepted.
A bounded descriptor read checks the file/name identity before and after the
read; binary validation is followed by another source check before launch.
One terminal LF/CRLF is accepted; embedded whitespace, NUL and non-ASCII bytes
are refused. Missing or unsafe files fail closed with no process started.

Only the selected value enters the child `COPILOT_GITHUB_TOKEN` environment
and the transient in-memory leak guard. The parent environment is unchanged;
the locator is not forwarded, no credential file is copied, and receipts record
only `auth_source=COPILOT_GITHUB_TOKEN_FILE`, never a path, value or token hash.
Option A can use the same selector as `--auth-source GH_TOKEN` after an approved
external wrapper supplies it. No gh-token extraction, automatic fallback,
refresh loop or saved-login lookup was added to the adapter. Execution still
defaults false, and the five-task route remains disabled.

The existing literal/JSON-escaped leak guard is reused for this file source.
Token echoes in stdout/stderr or the adapter transcript fail closed; a value
in receipt/handoff metadata is replaced with `[redacted]` and the run fails.
This covers adapter-owned sinks, not arbitrary CLI cache/log files, every
possible encoding or same-UID process inspection. The fresh NAS directories
remain **not a VM or security sandbox**. No real PAT was issued, supplied or
read for this change; the file and process tests used synthetic values only.

### If the owner selects B: five steps

1. Create a personal fine-grained PAT with only the account-level **Copilot Requests** permission; do not add repository/workflow scopes.
2. Set the shortest supported expiration covering the separately approved execution window; do not enable automatic renewal.
3. Use a protected input channel to store it outside Git/run captures, e.g. `/run/user/<uid>/ghcp-sol/token`: parent **0700**, file **0600**, owned by the runner UID; never put the value in an argv or log.
4. Set the locator `COPILOT_GITHUB_TOKEN_FILE` and explicitly select `--auth-source COPILOT_GITHUB_TOKEN_FILE`; leave execution disabled until a separately authorized run.
5. On completion, failure or cancellation, revoke the PAT on GitHub, remove the file and clear the locator; deleting a file/secret alone does not revoke a token.

One full offline gate invocation passed **543 unique cases**, **0 failures,
errors or skips**, exit **0**, in **57.18 pytest / 57.463 wall seconds**.
The existing 500 cases and 43 new file-source cases ran together, including
Auto/BYOK refusals, isolation/capture, limits and process cleanup. The first
verbose invocation stopped after 102 passes because pytest's terminal-width
lookup hit an existing names-only environment guard. Disabling progress output
fixed that harness conflict without changing product checks or assertions;
the incomplete run is not pooled into the final result.

Evidence: `/tmp/p5-ghcp-token-file.IUoE0w/`. The owner still has not selected an
authentication source. No installed Copilot CLI, real smoke, model request,
five-task run, dispatch or PR was started. Plans, limits, workflow and finite
rights are unchanged. Earlier dated sections below retain their historical
authentication findings and test results.

## Authentication choices after the masked-prefix check, 2026-10-27

The default, masked output of `gh auth status --active --hostname github.com`
exposed the nonsecret prefix **`gho_`**, identifying the active gh login as
**OAuth**. Exit was **0**; reported scopes were **gist, project, read:org, repo,
workflow**. The parser accepted a prefix only when the remaining displayed
characters were masking asterisks. No `--show-token`, token-export command,
login, direct credential-file read, or credential copy was used; raw status output
was discarded rather than logged. Only the prefix, type and scopes were retained.

The [official Copilot CLI authentication documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli)
lists **OAuth** as a supported token type. It also supports personal fine-grained
PATs with **Copilot Requests**, but not classic PATs. This uses the public page
retained on **2026-10-26**, not a new model or authentication-supply test.
The previous JSON-projected audit did not identify the type; this masked-prefix
check resolves that narrow gap. Copilot entitlement, billing identity and
acceptance by the installed CLI remain **unverified**.

The existing adapter accepts one explicitly selected environment name. It does
not obtain a token from gh, unlock a keychain, copy a config file, or fall back
automatically. Its fresh HOME/config/cache and missing-source refusal remain
unchanged. The previous inventory found all three allowed variables absent;
this follow-up does not supply one or select an authentication option.

| Option | Operator's action, only after owner choice | Adapter's action | Risk | Availability after this check |
| --- | --- | --- | --- | --- |
| Existing gh OAuth through an explicit wrapper | Approve the account/scopes and a reviewed, runtime-only bridge to `GH_TOKEN`; define disposal/revocation | With explicit `--auth-source GH_TOKEN`, forward only that supplied name into the fresh child environment; refuse if absent | Existing repo/workflow scopes are broad; OAuth lifetime and same-user process exposure need review | **Type compatible**; entitlement and approved supply/bridge are still missing. No wrapper was added or run |
| Dedicated short-lived personal fine-grained PAT | Supply a personal-account token with Copilot Requests through a protected channel as `COPILOT_GITHUB_TOKEN`; set expiration and revoke after the approved window | Select only `COPILOT_GITHUB_TOKEN`; retain source name, never its value; keep existing refusal/redaction checks | Bearer-secret exposure and revocation burden; the permission is not a five-task spending cap | **Documented alternative**, not supplied. Recommended for discussion if narrower permissions are preferred |
| Protected Actions environment secret containing an approved supported token | Approve the separate Actions host/workflow/billing route, protected-secret supply and revocation policy | Consume only an explicitly injected allowed environment name in an approved job; no secret retrieval is implemented in the adapter | Persistent secret and job-code exposure; deleting the secret does not revoke the token | **Not ready on the current NAS route**; workflow remains dry-run-only, with no new auth wiring or permissions |

Related offline authentication tests passed **23**, with **0 failed/errors/skipped**
and **38 deselected**, exit **0**, in **1.05 pytest / 1.225 wall seconds**.
The selection was `auth or credential or secret or presence` in
`tests/test_ghcp_sol_copilot_smoke.py`; executable and credential values were
synthetic. The earlier full **500-test** result remains separate, not rerun or
pooled. No runtime/test source, plan, cap or workflow changed.

Evidence: `/tmp/p5-ghcp-auth-kind.2zmgsj/auth-observation.json` and
`auth-tests.*`. No installed Copilot CLI, model call, real smoke, five-task run,
PR, dispatch or merge was performed. Authentication choice remains with the owner.

## Authentication inventory and fixed-five mock preflight, 2026-10-26

**The final offline suite passed 500 tests; no model or installed Copilot CLI
was invoked.** GitHub CLI has an active login, but the isolated adapter still
has no selected authentication source. This audit does not establish Copilot
entitlement, an OAuth token type, or actually applied Sol/Max/1M settings.

### Authentication metadata, without credential contents

| Source | Observed presence and type | Use in a fresh, noninteractive directory | Evidence |
| --- | --- | --- | --- |
| `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN` | All absent from this Desk worker's inherited environment | Supported in that precedence order, but a source must first be explicitly owner-supplied/approved | Retained 1.0.103 `help environment`, `/tmp/p5-ghcp-cli-smoke.0tE4vK/cli-environment.txt:15` |
| Existing `gh` login | Active `hyeonsangjeon` login on github.com, state `success`; token type **unknown** from masked status | A supported OAuth token can be bridged through an allowed variable; the current account's token type and Copilot entitlement remain unverified | `gh` 2.98.0, metadata-filtered `gh auth status`; [authentication documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli) |
| Default Copilot config | `/home/dev/.copilot/config.json` is a regular file; contents and stored-login presence **unknown** | A file's existence is not authentication evidence. This adapter requires an environment source and does not copy stored login into fresh HOME/config/cache | `lstat` only; installed package README:107 and public authentication documentation |
| OS keychain item, service `copilot-cli` | **Unknown**; no available metadata-only query client or session-bus/runtime-dir variable | Do not infer availability or absence; the adapter will not select this source implicitly | Public documentation names Linux libsecret; no item or secret was read |

The `gh` status check returned exit **0** and scopes **gist, project, read:org,
repo, workflow**, with the token source reported as its normal `hosts.yml` file.
Those scopes do not prove Copilot access or distinguish OAuth from a PAT.
The command used `--json hosts` with an allowlist projection, never `--show-token`;
no token command, authentication wrapper, login, store search or file-content
read was performed. Only default-path metadata was checked.

The installed package README at
`/home/dev/.local/share/nas-copilot-desk/copilot-cli/node_modules/@github/copilot/README.md:109-116`
documents a personal fine-grained PAT with **Copilot Requests**. The public
authentication page supports OAuth and that PAT type, rejects classic PATs,
and describes stored-login and lowest-priority `gh` fallback. These are mutable
interface documents, not evidence that the pinned executable accepted a token
here. Its public HTML SHA256 and excerpts are retained in the evidence directory.

### Owner choices; none selected or implemented here

| Option | Benefit and remaining risk | Required owner action |
| --- | --- | --- |
| Explicit bridge from the existing `gh` login | Reuses an existing login; its broad scopes, token type and Copilot entitlement still need review. A fresh HOME alone does not provide this login | Approve the named account and a bounded in-memory bridge to `GH_TOKEN`, plus disposal/revocation policy; no bridge was executed here |
| Short-lived personal fine-grained PAT, **recommended for discussion** | Can limit permissions to Copilot Requests; still a personal-account credential with same-user process exposure and no built-in five-task spending cap | Supply an owner-approved expiring token as `COPILOT_GITHUB_TOKEN` through a protected channel, then revoke it after the approved window; no token was created or retrieved here |
| Protected Actions environment secret | Enables approval-gated CI injection; storing a secret is not execution permission and does not revoke the token when deleted | Approve a separate Actions host/workflow/billing route and expiry/revocation policy. The current workflow remains dry-run-only; no secret, permission or workflow was changed |

### What the free preflight checked

At base `d99081b74`, the generic fake-command adapter omitted HOME. It now
reuses the smoke's existing fresh work/HOME/config/cache/data/state/temp
environment, without inheriting any authentication variable. Only the existing
explicitly selected smoke path can forward an authentication source. This
change does not bind a live five-task command or make a directory a VM/security
sandbox.

The added test uses each of the **five catalog-pinned task IDs** with **nine
synthetic conditions**, for **45 cases**. It stages fake input bytes, runs a
fake executable and events through the actual adapter, captures output/partial
files and receipt bytes, verifies hashes, then removes the controller-owned
temporary directories. Child and grandchild processes are checked as stopped;
the leader is reaped. Only synthetic private captures remain in the test evidence.

| Conditions, each repeated for all five IDs | Expected result |
| --- | --- |
| 63/31 and 64/32 turn/tool starts, simulated 1,199 seconds | Process-only success; paid/settings-proof authority stays false |
| 65 turn starts or 33 tool starts | `turn_cap_exceeded` or `tool_call_cap_exceeded` |
| Simulated elapsed 1,200 or 1,201 seconds | `task_timeout_exceeded` |
| Missing model, reasoningEffort or tokenLimit | `served_model_unverified`, `reasoning_effort_unverified` or `context_limit_unverified` |

The **10 process-only receipts and 35 expected refusal receipts** all matched
their assertions. Usage and cost remain **not available**, not zero. The final
combined invocation passed **500 / 0 failed / 0 errors / 0 skipped**, exit **0**,
in **55.77 pytest / 56.053 wall seconds**. It includes existing Auto/BYOK,
secret-redaction, input-bundle and gate contracts. This is not a live GDPVal
result or proof of actual Sol/Max/1M, complete CLI event delivery, escaped-session
containment, or pre-effect tool admission. The mocked clock is not a 20-minute
live run; the test-only staging/capture controller is not a registered paid pipeline.

The first launcher found no `/usr/bin/time` and did not start pytest. The first
actual suite passed **455** and failed the **45** new fixtures because their
usage event lacked its required ID. Adding that fake ID, without relaxing any
check or assertion, produced the full final pass. Both runs and the launcher
failure are retained separately, not pooled.

Evidence: `/tmp/p5-ghcp-free-preflight.HkdCO8/`, including metadata-only
`auth-inventory.json`, public-source excerpts, `gate-tests*.log`/JUnit/timing,
and 45 `pytest-final/.../capture/<task-id>/free-preflight.json` records.
No model call, new smoke, paid five-task/220-task run, PR, dispatch or merge.

## Authentication-source opt-in follow-up

**No new smoke was started.** In this Desk worker's inherited environment,
`COPILOT_GITHUB_TOKEN`, `GH_TOKEN` and `GITHUB_TOKEN` were all absent. Only name
membership was inspected, not values. The active Desk's stored-login kind
remains **unknown**; no keychain/config contents were read or credentials sought.

The retained 1.0.103 `help environment` names those variables in that precedence
order (with a documented Codespaces exception). The installed executable still
matches SHA256 `f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d`.
A names-only static inspection of `/usr/local/bin/copilot:32-34` identifies a
`gh auth token` to `GH_TOKEN` bridge. That wrapper was not executed, and its
presence does not establish this Desk session's actual authentication source.

The adapter now requires an explicit `--auth-source` from the three-name
allowlist. It passes only the chosen existing variable to the isolated child;
there is no source fallback, store lookup or file copy. Missing selection or an
unavailable source refuses before executable validation, directory creation or
spawn. A receipt records only the chosen name as `auth_source`, never its value.
Work/HOME/config/cache remain fresh, and model, effort, context and caps do not
change. The execution flag still defaults false.

An in-memory guard fails closed if the selected value, including its JSON-escaped
form, appears in stdout/stderr, the receipt or the adapter-owned bounded JSONL
transcript. Split pipe chunks are covered; credential-bearing lines are not
written to that transcript. The guard does not scan arbitrary CLI cache/log
files or attest protection against every possible encoding or process-memory
reader. This directory setup is still not a VM or a security sandbox.

One combined offline invocation passed **455 tests, 0 failed, 0 skipped** in
**50.87 pytest seconds**. The evidence directory is
`/tmp/p5-ghcp-auth-optin.F5QHs2/`. The current observation is a skipped-smoke
record, not another CLI authentication error: exit, model, effort, context and
usage are unknown/null; usage is `not available`. The earlier single prompt
attempt and its receipt below remain unchanged. No five-task run, login, token
issuance, credential-store change, retry, PR, merge or dispatch followed.

## Current NAS smoke decision and result, 2026-10-26

**The single approved CONNECTED smoke reached an authentication failure.**
The installed CLI reported `No authentication information found`, exited **1**,
and the adapter exited **2**. No served-model, reasoning-effort or context event
was observed. All three remain **null / unverified**. The five-task gate did not
start, and the smoke was not retried. This is not a model-quality result or a
finding that authentication is unavailable outside this isolated environment.

The leader explicitly selected **GHCP Copilot CLI agent + GPT-5.6 Sol** and a
NAS isolated directory: **VM 아님, 격리 디렉터리**. It is the default Copilot
CLI agent, not a Codex-agent selector. Prior VM/Actions registrations and the
historical sections below remain unchanged; they are not the current smoke
condition or launch authority. No GDPVal input, grading or 220-task run is used.

| Binding | Current smoke implementation | Evidence boundary |
| --- | --- | --- |
| Installed CLI | Direct executable **1.0.103**, SHA256 `f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d`; drift is refused before spawn. | Direct `--version` and help evidence, not a VM/package-version inference. |
| Command | `-p "Reply with exactly CONNECTED" --model gpt-5.6-sol --reasoning-effort max --context long_context --output-format json --usage-output-file <private-file>`; streaming on. | Requested values are not observed settings. Only this fixed smoke is bound; all five GDPVal IDs refuse on this route. |
| Isolation and authentication | New work directory, HOME, config, cache, data, state and temporary directory. Only already inherited supported CLI auth variables may pass to the child. | No store inspection/copy, login, token issuance or fallback search. Directory isolation is not a security sandbox. |
| Permissions and limits | Execution defaults false. **1,200 seconds / 64 turn starts / 32 tool starts**, TERM/KILL process-group cleanup. The smoke exposes no tools, disables built-in MCP/custom instructions, and denies shell/write tools. | Start notifications support observed-limit cancellation, not native HTTP counts or pre-effect admission. Escaped sessions are outside group cleanup. |
| Receipt | Allowlisted original model/effort/context and numeric consumption fields; missing/mismatched settings fail closed. Context snapshots remain labelled as session metadata. | `verified` would mean observed fields match requests, not provider attestation or an exercised 1M workload. Five-task permission remains false. |

The pre-smoke combined offline invocation passed **432 tests**, with **0 failed /
0 skipped**, in **51.66 pytest seconds**. Only then was the one real CLI prompt
attempted, using that tested code. Its retained usage file contributed only
`totalApiDurationMs=0`; this is a time diagnostic, **not zero token usage or zero
cost**. The original receipt incorrectly labelled that duration-only projection
as available usage. Its bytes remain unchanged. A separate observation record
states **usage: not available**, and a narrow code correction excludes duration
fields from consumption. No real CLI prompt was rerun after that correction.

Final implementation `b2ee44f3b80cc18663b2993b2a95230efb00468f` passed one
combined **433-test** invocation, **0 failed / 0 skipped**, in **49.94 pytest
seconds**. The first 432 and final 433 results are separate invocations, not
865 distinct tests. The [completion record](../tasks/LATEST_TASK_RESULT/README.md)
binds the exact source patches, invocations, JUnit, timing and receipt digests.
Evidence remains at `/tmp/p5-ghcp-cli-smoke.0tE4vK/`; no raw transcript, header,
credential value or private usage file is published. The next prerequisite is
approved authentication usable by the isolated CLI, followed by a new leader
instruction. No retry, five-task execution, PR, merge or dispatch follows here.

## Historical Actions draft and earlier investigations

The remaining sections preserve earlier findings and approval states. Their
no-command-binding and unresolved-scope statements describe their recorded
sources, not the later smoke implementation above.

Owner decision 2026-10-24 00:01: use one GitHub Actions standard
`ubuntu-24.04` runner job per task. No nested VM or `/dev/kvm` prerequisite.
This draft does not grant push, dispatch, paid inference or grading approval.

## Owner execution request and publication boundary, 2026-10-26

The owner subsequently authorized paid experimentation, pipeline work and
ordinary commit/push. **Approval is no longer the missing prerequisite.**
This request does not identify a replacement harness, a tool-call cap, a
currency ceiling or an authentication supply method. No historical right
or consumed attempt is reset.

OpenAI's [GPT-5.6 Sol model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
advertises a **1,050,000-token context window**. The HTTPS read returned 200;
the retained page is 461,900 bytes, SHA256
`7bde0883be9345f5a4ef44ccbb5a1843ddd9f0672d0970ad35ae2ab03151d451`.
This establishes the published model specification, not the context actually
applied by a GHCP session. No model or session was run to obtain this evidence.

| Remaining execution prerequisite | Existing source evidence |
| --- | --- |
| Runnable GHCP-backed Codex command and isolated authentication | `ghcp_sol_execution_adapter.py` explicitly binds neither; the workflow does not call the adapter. `code` and `code-insiders` are not on this host's PATH. This does not establish product absence elsewhere. |
| Complete capture and enforced task limits | The retained adapter proof concerns fake executables. Real event delivery and pre-effect enforcement remain unverified; the existing 1,200-second/64-turn requirements are unchanged. |
| Approved tool-call and monetary limits | The inert GHCP registration still has null `execution.tool_calls_per_task` and `cost.approved_maximum_usd`. No values were invented or borrowed from the separate Foundry condition. |
| Dispatchable pipeline | The existing workflow implements dry capture only. The GitHub workflow metadata lookup returned HTTP 404; no dispatch was attempted, and that response alone does not distinguish a missing record from unavailable access. |

The requested ordinary branch publication can proceed independently; it does
not merge the workflow or turn dry capture into a paid experiment. Replacing
Codex with the Copilot CLI's default harness would change the registered
condition and still needs an explicit scope decision. The previous b/c/d
unknowns therefore remain; they are not a claim that Sol lacks a 1M capability.
Current evidence is retained in `/tmp/p5-ghcp-execution-20261026.GQp0K1/`.

## Product routes and scope decision, 2026-10-25 21:45 KST

**Copilot-backed Codex exists, but no inspected route closes this card's
unattended VM and applied Sol/Max/1M requirements.** GitHub documents a Codex
cloud coding agent and a VS Code Codex integration. VS Code also documents an
experimental Codex Agent Host integration and a standalone host. This is not
an IDE-only product, nor is it the custom-agent selector in Copilot CLI.
Availability in the documentation is not approval or availability for this
account. No account policy, credential or live session was inspected.

The audit starts from clean `b9440698014eae3a941ea31d86f6b6bf5599a595`, tree
`a2285ea2c50ae30e606015fe7b7a93acc8641880`. Evidence consists of installed
help/version output, package files and public official pages fetched on
2026-10-25. It does not include a model response or a VM execution. Code,
workflow, plans, caps, model identities, permissions and finite rights are
unchanged. The new work is documentation only.

### Route decisions

Here **a** means unattended execution inside the owner-selected task VM, not
merely submitting work from that VM to a different service. **b** requires
both selecting and proving applied GPT-5.6 Sol, Max and numeric 1M context.
**c** requires the complete transcript, tool calls and generated files,
including uncommitted files. **d** requires the existing 1,200-second and
64-turn limits during execution. Yes denotes a documented mechanism, not a
live verification; unknown means the inspected sources do not close the
requirement.

| Route | a: unattended task VM | b: Sol/Max/1M selection and proof | c: complete capture | d: timeout and turn enforcement |
| --- | --- | --- | --- | --- |
| GitHub.com Codex coding-agent session, issue assignment or PR mention | **No** for the selected local job: the cloud target uses provider-managed infrastructure. Task submission is a separate operation. | **Unknown**: the fetched supported-model list does not name Sol; no applied Max/1M evidence contract is supplied. | **Unknown**: activity logs and PR changes are documented, not a complete private transcript/tool/file export. | **Unknown**: a UI stop is documented, not a 1,200-second/64-turn controller. |
| Installed `gh agent-task`, 2.98.0 | **No** for local execution; noninteractive remote task submission is documented. This command does not expose a Codex provider selector. | **No** through the inspected create interface: no model, reasoning or context flags. | **Unknown**: `view --log` and selected JSON metadata exist, not a full-fidelity export contract. | **No** through this interface: only create/list/view; killing the local log follower does not establish remote cancellation. |
| Copilot CLI's own harness, installed 1.0.103 / 1.0.79 | **Yes**, conditionally, for its documented `-p` mode with separately approved authentication and permissions; **not** a Codex harness binding. | **Unknown**: model/effort/context options show selection; 1.0.79 stdout omits required per-call metadata. | **Unknown**: JSONL and local edits exist, but omitted ephemeral metadata and unverified delivery prevent a completeness claim. | **Unknown** as a live pair: owned-process timeout is available in the offline adapter; complete/prompt turn delivery and the actual CLI binding remain unverified. |
| VS Code Codex extension or experimental Codex Agent Host | **Unknown**: a standalone host is documented, but an approved cold-start, unattended Copilot-authenticated Codex task command is not established. | **Unknown**: authentication/model selection is documented, not this exact model/settings combination or applied-setting attestation. | **Unknown**: UI sessions and ordered Agent Host state exist, not a verified full raw-capture mapping for this adapter. | **Unknown**: no inspected binding connects Codex host events, owned-process cleanup and the two fixed limits. |

The cloud findings use [GitHub's third-party-agent contract][route-github],
[session management][route-sessions] and [VS Code's cloud/harness
description][route-vscode]. GitHub's [2026-02-04 release][route-release]
confirms the product entry points, not current billing or account entitlement.
The CLI row uses installed `gh agent-task --help`, `create --help`,
`view --help`, and the matching [published create manual][route-gh].
No create, list, view-session, issue-assignment or PR-mention action ran.

### What the interfaces actually establish

- GitHub says its Codex coding agent and VS Code integration use the Codex
  SDK and can use a Copilot subscription. Its fetched cloud list is `Auto`,
  `GPT-5.3-Codex` and `GPT-5.4 nano`, not GPT-5.6 Sol. The same page says the
  extension can have a different model subset. This is a documentation
  finding, not evidence that this account lacks Sol. The extension's
  documented "Sign in with Copilot" route requires Pro+ or Max; the VS Code
  Agent Host page separately describes a Pro+ requirement. Neither was
  tested or enabled here.
- In `gh 2.98.0`, `--custom-agent` selects a repository agent definition, not
  the OpenAI provider. Create exposes base/repo/file/follow/custom-agent
  flags; view exposes logs and session/PR metadata. There is no installed
  Codex/model/effort/context/turn selector or stop subcommand. A different
  API or future CLI may offer more; this audit does not establish that.
- [VS Code's harness guide][route-vscode] names
  `chat.agentHost.codexAgent.enabled` and
  `chat.editor.codex.preferAgentHost`. These are documented settings, not
  changes made here. Enterprise-managed settings can disable the Codex
  harness. The [Agent Host architecture][route-host] documents
  `code agent host`, local or remote execution, and AHP JSON-RPC over
  WebSocket. AHP supplies an initial snapshot and ordered actions, with
  missed actions or a new snapshot on reconnection. A snapshot is not proof
  of a complete historical transcript or provider settings. A host connection
  token is not a Copilot model entitlement. No host, tunnel or token was
  started or created. The Agent Host command is documentation evidence;
  no installed VS Code/Agent Host version or task handshake was verified.
- Both installed Copilot help surfaces call `--agent` a custom-agent
  selector. Their environment help describes model choice and BYOK, not a
  Codex harness selector. `--acp` selects a protocol server; 1.0.103's
  `--host-environment` describes Mission Control hosting. Neither establishes
  Codex selection. BYOK would change the route and remains refused by this
  card. No hidden flag or feature toggle was tried.
- Standalone Codex **0.144.5** documents noninteractive `exec`, `--model`,
  TOML overrides and `--json`. Those options do not establish a GHCP bridge.
  The [OpenAI authentication guide][route-openai-auth] describes its own
  authentication paths; [Codex's GitHub review integration][route-openai-gh]
  describes `@codex review`. Neither is substituted for the Copilot-backed
  coding-agent contract or authorizes a different billing route.

### Installed-version comparison and retained proof

The exact host binary paths are in the [preceding inventory](#installed-cli-contract-audit-2026-10-25-1215-kst).
New direct `--version` checks confirm Desk **1.0.103**, system **1.0.79**,
Codex **0.144.5**, and `/usr/bin/gh` **2.98.0 (2026-08-20)**. These are host
versions, not VM evidence. Direct platform binaries were used, never the
`/usr/local/bin/copilot` authentication wrapper. Help/version commands used
cleared environments and bounded **15s TERM + 3s KILL** wrappers; Copilot
automatic updates were disabled. No prompt, session or login command ran.

| Comparison | 1.0.103 Desk binary | 1.0.79 system binary |
| --- | --- | --- |
| Model/effort/context and JSONL | Options confirmed; not applied-setting evidence. | Options confirmed; not applied-setting evidence. |
| Codex selector | None in inspected help/environment interfaces; embedded internals not exhaustively audited. | None in inspected interfaces/built-ins; `codex_agent_enabled` is an account feature, not a selector. |
| Schema and serializer | Sibling metadata says **1.0.98**; no standalone event schema. Exact schema/stdout equivalence remains **unknown**. | Inspectable event schema and `app.js:2744` writer. Usage/context/model-change/idle/shutdown events are filtered. |
| Additional help evidence | `help limits` describes a **soft** AI-credit cap, not a timeout or turn cap. | `--max-autopilot-continues` counts continuation messages, not all turns. |

A 1.0.79 environment-help invocation rejected `--disable-client-telemetry`;
the corrected help-only command omitted that unsupported flag. This was a
help diagnostic, not a test failure. Cross-version flags must not be assumed
interchangeable. No version pin changed; 1.0.79 remains an inspectable offline
reference, not an approved execution route.

The last combined test result remains **313 passed, 0 failed, 0 skipped**
in **16.50s** pytest / **16.66s** wrapper time, exit **0**, at
`59c23a1446533cc988cf74840cd00eb1a23c3605`. It includes eight Auto/BYOK-named
refusals. **No tests or collection were rerun in this research task.**
The earlier 295-pass/4-fail invocation and separate four-pass correction
remain distinct. The [immutable pre-audit record][route-prior] preserves
commands, JUnit/log hashes, the synthetic-only boundary and prior failures.

### Owner choices, not a scope change

| Option | Benefit | Remaining risk or cost |
| --- | --- | --- |
| **A. Keep GHCP + Codex + Sol/Max/1M; hold execution. Recommended.** | Preserves the registered comparison. The documented Codex Agent Host is a concrete next research target. | Needs a supported unattended task/authentication contract, exact model availability, applied-settings evidence, complete capture and fixed-limit/cleanup mapping on the selected VM. Cloud execution cannot silently replace that host. |
| **B. Propose a separately approved Copilot CLI + Sol comparison.** | Uses documented noninteractive CLI syntax and the existing offline adapter. | Changes the harness/study scope and needs owner-approved registration; does not fix the settings/delivery gaps or approve billing, tool limits or authentication. Existing scores/rights cannot be reused. |
| **C. Stop this gate without a benchmark result.** | Avoids spending under unverified conditions. | Produces no five-task comparison. Record the missing contract, not a failed or absent model. |

Recommend A only as a documentation/contract follow-up. Before implementation,
obtain one version-bound contract for a Copilot-backed Codex Agent Host task
on the selected VM, covering launch, model/settings evidence, events and
cancellation. If that contract cannot satisfy the unchanged requirements,
return the choice to the owner rather than switching to B. No option is an
execution grant. Fixed-HEAD review/CI, the tool-call cap, private input/grader
bindings, authentication isolation/disposal and separate paid approval remain.

[route-github]: https://docs.github.com/en/copilot/concepts/agent-capabilities/about-agents/about-third-party-coding-agents
[route-sessions]: https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/manage-and-track-agents
[route-release]: https://github.blog/changelog/2026-02-04-claude-and-codex-are-now-available-in-public-preview-on-github/
[route-gh]: https://cli.github.com/manual/gh_agent-task_create
[route-vscode]: https://code.visualstudio.com/docs/agents/run/agent-harnesses
[route-host]: https://code.visualstudio.com/docs/agents/concepts/agent-host
[route-openai-auth]: https://learn.chatgpt.com/docs/auth
[route-openai-gh]: https://learn.chatgpt.com/docs/third-party/github
[route-prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b9440698014eae3a941ea31d86f6b6bf5599a595/tasks/LATEST_TASK_RESULT/README.md

## Installed harness and stdout audit, 2026-10-25 13:50 KST

**The inspected installed selectors do not provide a Codex harness command,
and the auditable 1.0.79 JSONL writer omits required settings metadata.** This
is an installed-source finding, not a live session observation. No Copilot or
Codex executable, including help/version commands, ran during this task.
The versions below refer to the preceding audit, not a new VM measurement.

### Command and harness: partial

The preceding noninteractive syntax remains partial: `-p <prompt> --model
gpt-5.6-sol --reasoning-effort max --context long_context --output-format json
--stream on`, with updates and client telemetry disabled. It selects a model,
effort and context tier, not a verified GHCP-to-Codex bridge or applied 1M.
The system platform package is
`/usr/lib/node_modules/@github/copilot/node_modules/@github/copilot-linux-x64`.
Its `app.js:5600` describes `--agent <agent>` as "Specify a custom agent to use".
The built-in registry at `app.js:287` contains `explore`, `task`, `code-review`,
`rubber-duck`, `research`, `rem-agent`, `security-review` and `general-purpose`,
not Codex. The inspected changelog describes Codex models/custom agents, not
a Codex harness selector. Both Copilot package README files describe the
Copilot coding-agent harness at line 5.

`schemas/api.schema.json:12638` and
`copilot-sdk/generated/rpc.d.ts:2594` name optional `codex_agent_enabled` as an
account feature. This is neither an agent definition nor a selection command;
no account query was made. Thus a Codex selector is **absent from the inspected
installed selectable interfaces**. This does not establish absence from an
opaque binary's internals, external plugins or other products.

### Settings fields: schema confirmed, applied settings unverified

The following locations are in the system package's
`schemas/session-events.schema.json`, SHA-256
`350df35914d4e2fdbadb8932ca66f1e58d759aad79b5be9291857c9052d31301`.

| Event field | Schema lines | Meaning and limit |
| --- | --- | --- |
| `session.start.data.selectedModel`, `reasoningEffort`, `contextTier` | 13065–13088 | Optional selected configuration; tier may be null. Not per-call served/applied evidence. |
| `assistant.turn_start.data.model` | 1186–1208 | Optional turn model label, not provider attestation. |
| `assistant.usage.data.model`, `reasoningEffort` | 1338–1543 | Required call model label, optional effort; usage is ephemeral. |
| `session.usage_info.data.tokenLimit` | 15936–16036 | Numeric session snapshot, not call-specific context attestation; ephemeral. |
| `session.model_change.data.newModel`, optional effort/tier/`cause` | 8686–8745 | Can describe a switch, but only if the event is delivered. |

`ContextTier` at line 4897 allows `default` or `long_context`; the schema has
no event field named `modelContextWindow`. Documented model-change causes
include `rate_limit_auto_switch` and `refusal_fallback`; these describe possible
events, not an observed switch. None of these fields proves an applied Max
setting or numeric 1M context, and start/turn labels cannot replace missing
call metadata in the existing fail-closed collector.

### Delivery: confirmed omissions, unverified completeness

The 1.0.79 `app.js:2744` exclusion set `w6r` and writer `ron` filter
`assistant.usage`, `session.usage_info`, `session.model_change`, `session.idle`
and `session.shutdown` from stdout. The JSON-mode listener is attached at
line 2821 and forwards through `ron` at line 2823. This is a concrete delivery
gap, not merely a lack of evidence that all SDK events reach the CLI. Saved
session logs also cannot restore ephemeral usage/context events.

`app.js:2745` defines `ion`, invoked at line 2844, which writes a final
`type: "result"` object with `timestamp`, `sessionId`, `exitCode` (0 or 1) and
aggregate `usage`. It is not a `data`-bearing session event. The writers append
newlines, but that does not establish prompt, complete delivery or a flush
barrier. A zero result, EOF or selected `long_context` is not completion or
settings authority. Aggregate usage is not a per-call model/context record
or a verified charge.

### Version recommendation: offline reference only

Prior direct executable observations were Desk **1.0.103** and system
**1.0.79**. The Desk platform directory
`/home/dev/.local/share/nas-copilot-desk/copilot-cli/node_modules/@github/copilot-linux-x64`
contains `copilot`, `package.json`, `README.md` and `LICENSE.md`; its metadata
says **1.0.98**. It has no standalone schema, built-in registry or changelog,
and the executable is opaque ELF. An exact 1.0.103-versus-1.0.79 schema diff is
therefore **unverified**; no 1.0.79 field is attributed to 1.0.103 stdout.
Propose **1.0.79 as an auditable offline reference only**, because the schema,
options and serializer are inspectable. No version pin changed. Its filtered
JSONL is not a sufficient live settings-evidence channel.

### Source-supported correction and proof

The adapter now separates the CLI result shape from session events. It checks
the exact top-level keys, a bounded timestamp, matching observed session ID,
integer 0/1 exit code and object-shaped usage. It records only a safe
`cli_result` observation/exit code, with `completion_authority=false` and
`settings_authority=false`; raw identities, usage, private paths and errors
are not projected. Nonzero summaries refuse with `cli_result_failed`;
malformed, duplicate or post-result frames use `session_event_stream_refused`.
After a zero result it still supervises until actual EOF/process exit or the
unchanged deadline. No command builder or collector guard was changed.

The new **synthetic** five-line filtered-stdout fixture contains four session
events plus the CLI result. All four session events validate against the
installed Draft-07 schema; the CLI-only result is outside that schema. The
filtered fixture still refuses missing model/effort/context evidence, even
when start configuration says Sol/Max/long_context. Other new tests combine
SDK events and result summaries synthetically, not as observed CLI output;
they check summary refusal, private-canary exclusion and deadline cleanup
after a zero result from a hanging fake process. No raw session was read.

On clean `59c23a1446533cc988cf74840cd00eb1a23c3605`, tree
`49033ac832de59987d19d41817f3fc6d6f4567ad`, one combined gate invocation reports
**313 passed, 0 failed, 0 skipped in 16.50s** (wrapper **16.66s**, exit **0**):
**138 Actions + 93 VM + 82 adapter**, including Auto/BYOK refusal. Fourteen
cases are new. The earlier **295 passed/4 failed** and separate **4 passed**
remain historical, not pooled. Commands use **120s TERM + 5s KILL**, cleared
environment/offline flags and fake executables with existing network guards.
[The immutable result record][route-prior] binds exact commands,
source/artifact hashes and the later documentation-only final HEAD.

The adapter's default-disabled state and dry-only workflow are unchanged. The actual
VM/harness binding, an unfiltered complete/prompt event channel, served/applied
model/Max/1M evidence, approved tool cap, authentication isolation/disposal,
input/grader bindings and fixed-HEAD review/CI remain required before any
separate execution decision. Event-based cancellation is not pre-effect
admission. No launch, retry, cost, score or study-completion claim is made.

## Installed CLI contract audit, 2026-10-25 12:15 KST

**The exact GHCP-to-Codex launch command remains unconfirmed.** Local help
confirms noninteractive and JSONL options, but not that this route applies
Sol, Max and a numeric 1M context together. No authenticated session, prompt,
model call, server startup or live event capture was run. The adapter and
collector are unchanged; only schema-shaped synthetic fixtures were added.

The retained help files below are in
`/ai-work/copilot/_tmp/ghcp-sol-cli-contract.9Qj6sx/`.

| Inspected host executable | Observed version | Boundary |
| --- | --- | --- |
| `/home/dev/.local/share/nas-copilot-desk/copilot-cli/node_modules/@github/copilot-linux-x64/copilot` | `--no-auto-update --version`: **1.0.103** | Sibling `package.json:3` says **1.0.98**. Package metadata is not the executable version. |
| `/usr/lib/node_modules/@github/copilot/node_modules/@github/copilot-linux-x64/copilot` | `--no-auto-update --version`: **1.0.79** | Sibling metadata agrees; this package contains the inspected runtime/SDK schema. An earlier unpinned invocation reported 1.0.103. |
| `/home/dev/.local/bin/codex` -> `/home/dev/.codex/packages/standalone/releases/0.144.5-x86_64-unknown-linux-musl/bin/codex` | **0.144.5** | This is the host executable, not VM version evidence. |

The earlier host observation of Copilot **1.0.83** was not reproduced; none
of these observations establishes the intended VM version. The default
`/usr/local/bin/copilot` wrapper was read, **not executed**: lines 20-29 run
entropy helpers and line 33 can call `gh auth token`. That wrapper is not an
approved authentication or launch binding for this adapter.

### Command syntax: confirmed options, unconfirmed route

`copilot-pinned-help.txt:38-40,53-63,103-107` documents `-p` (noninteractive,
exit on completion), `--model`, `--reasoning-effort max`,
`--context long_context`, `--stream on` and `--output-format json` (JSONL,
one object per line). `copilot-config-help-fixed.txt:148` lists `gpt-5.6-sol`.
The following is **partial syntax only; it was not executed**:

```text
<pinned-copilot> --no-auto-update --disable-client-telemetry -p <prompt> --model gpt-5.6-sol --reasoning-effort max --context long_context --output-format json --stream on
```

`--agent` explicitly selects a **custom agent**, not a verified Codex harness.
`long_context` is an eligible-model tier (`copilot-config-help-fixed.txt:165`),
not a numeric or applied 1M attestation. Sol/Max options are requested settings,
not served evidence. The config help also documents `continueOnAutoMode`
at lines 110-112; this investigation neither enabled it nor changed guards.

Codex `exec --help` confirms noninteractive execution, `--model`, TOML `-c`
and `--json` (stdout JSONL, `codex-exec-help.txt:92-93`). It does not establish
a GHCP authentication bridge or this four-part launch contract. The inspected
0.144.5 release did not supply an event schema among its bundled resources.
Only `app-server --help` and `app-server generate-json-schema --help` ran;
no server or schema generator was started. A newer repository SDK is not
substituted as evidence for this installed CLI.

### Event shape versus delivery

The packaged 1.0.79 runtime schema is
`/usr/lib/node_modules/@github/copilot/node_modules/@github/copilot-linux-x64/schemas/session-events.schema.json`,
SHA-256 `350df35914d4e2fdbadb8932ca66f1e58d759aad79b5be9291857c9052d31301`.
Its SDK and schema describe these fields; they do **not** prove that the
1.0.103 prompt-mode stdout stream emits every such event promptly.

| Field or marker | Installed evidence | What it does not prove |
| --- | --- | --- |
| `assistant.turn_start`, `data.turnId`, optional top-level `agentId` | Schema lines 1186-1260; absent `agentId` denotes the root agent. | Complete turn delivery from the eventual GHCP-to-Codex route. |
| `tool.execution_start`, `data.toolCallId`, `data.toolName` | Lines 15275-15386; IDs support per-agent counting. | Admission before a tool takes effect, or reliable delivery of all starts. |
| `assistant.usage.data.model`, optional `reasoningEffort` | Lines 1340-1543; the event requires `ephemeral: true`. | Applied settings or a complete native-request count. A valid event can omit effort. |
| `session.usage_info.data.tokenLimit` | Lines 15935-16036; also requires `currentTokens`, `messagesLength` and `ephemeral: true`. | A call-specific 1M context attestation. It remains a preceding session snapshot. |
| `session.idle`, `session.shutdown` | Lines 6760-6788 and 12527-12553: idle means no in-flight agents/attached shell commands; shutdown carries termination metrics. | A stdout flush barrier, a complete stream, or proof that all sub-agent events arrived. |

The same package's `copilot-sdk/session.d.ts:131-145` says `sendAndWait`
waits for `session.idle`; its timeout does **not** abort in-flight work.
`copilot-sdk/types.d.ts:1938-1953` describes streaming/sub-agent forwarding.
Neither establishes CLI stdout buffering, flush timing or loss-free delivery.
Ephemeral usage/idle events are not persisted in the session log. Reading a
saved session file alone therefore cannot supply all required evidence.
EOF, idle and shutdown do not upgrade `stream_completeness_verified`.

### Narrow fixture change and separate proofs

The existing parser already uses the documented field paths, so no parser,
helper, workflow, plan, cap, dependency, registration or permission changed.
Added an eight-event **synthetic** JSONL fixture with schema-required envelopes,
linked parent IDs, tool name, context fields and ephemeral markers. All eight
events pass the installed Draft-07 schema with format checking and internal
references only. Four fake-process variants check full metadata, absent
ephemeral events, optional effort missing, and absent terminal markers.
They retain private-canary exclusion, settings-only labels and false authority
and completeness flags. Fixture timestamps/zeros are not runtime measurements.

One combined invocation returned **295 passed, 4 failed, 0 skipped in 15.60s**
(wrapper **15.77s**, exit **1**). The four new cases failed because their fake
program read the JSON argument at index 4 rather than 3. After that one-line
fixture correction, **only those four** were rerun: **4 passed, 0 failed,
0 skipped in 0.30s** (wrapper **0.47s**, exit **0**). Assertions and production
code were unchanged. This is **not** a 299-pass final invocation. The earlier
**295/15.79s** proof below remains historical and separate. Both test commands
used **120s TERM + 5s KILL**; the first collection launcher also failed before
pytest because `/usr/bin/time` was absent. Its log is retained.

Direct help/version calls used a cleared inherited environment and an empty
evidence working directory. After discovering the relevant flags, calls used
`--no-auto-update` and `--disable-client-telemetry`. Initial calls lacked the
update-disable flag; **no audited zero-background-network claim is made**.
Attempted OS isolation was unavailable (user namespaces, Landlock, seccomp);
the guarded help launcher stopped before CLI execution. No OS setting was
changed. Three topic-help calls rejected unsupported `--config-dir`; removing
only that argument allowed help to complete. It was not a config/cache sandbox.
No update, login, token, model, network-fetch or dispatch command was issued.

The next free prerequisite is to identify the intended VM executable and its
exact **GHCP-to-Codex bridge plus stdout serializer contract**, from installed
source/help only. Tool-cap approval, authentication isolation, complete live
delivery and applied-settings proof remain separate gates; no launch or retry
right was granted. [The current record](../tasks/LATEST_TASK_RESULT/README.md)
binds file hashes, commands, failed and passing logs/JUnit, and local source.

## Disabled process adapter, 2026-10-25 10:35 KST

The leader authorized a local process-adapter skeleton after the earlier
execution-path audit. `batch-runner/ghcp_sol_execution_adapter.py::run_task`
now supervises an explicitly supplied argv. `execution_enabled` defaults to
false and rejects before configuration reads, task-state creation or process
launch. The caller must also supply a positive integer in
`execution_config["tool_calls_per_task"]`; missing, null and invalid values
refuse before launch. There is no default tool-call value or selected candidate.
The existing workflow and inert VM plan remain unchanged and cannot invoke it.

| Limit | Previously available | New adapter behavior |
| --- | --- | --- |
| 1200 seconds/task | Supplied-event collection only | Start a monotonic deadline before `Popen`; check after launch, while reading and after EOF. Stop a silent, partial-line or closed-stdout process with `task_timeout_exceeded`. |
| 64 turns/task | Supplied-event collection only | Count agent-scoped `assistant.turn_start`/`turnId` identities. Accept 64; stop when the 65th start is observed with `turn_cap_exceeded`. |
| Tool-call cap | Undefined | Require the caller's value, count `tool.execution_start`/`toolCallId` once per agent, and stop on the first observed count above it with `tool_call_cap_exceeded`. Malformed or repeated start identities refuse. |

The adapter creates one fresh private task directory and owns a new POSIX
process group. Every started-process exit path signals that group with TERM
and then KILL, including when the leader exits first. Cleanup allows one second
for TERM and four seconds for the final wait; `waitid(..., WNOWAIT)` keeps the
leader PID reserved until group signalling finishes. The receipt distinguishes
group signals, leader reaping and stdout closure. It does not claim that escaped
sessions were contained or every orphan was reaped. Partial files stay in
`private/files`; they are neither read into the receipt nor uploaded.

The JSONL reader retains the existing byte, line and event limits and reuses
the existing collector for allowlisted settings metadata. The outer receipt's
`limits` and `cleanup` describe the owned process; the nested collector receipt
keeps its separate collection-only labels. Commands, paths, raw events, stderr,
headers and credentials are not serialized. The child receives a minimal
environment without inherited credential channels, not an approved GHCP
authentication mechanism or proof that a CLI cannot discover a user cache.
Auto/BYOK checks are reused. Missing usage and cost remain null with
`not available`; settings stay settings only, and all paid/retry/live-proof
authority flags remain false.

One combined offline invocation passed **295 tests, 0 failed, 0 skipped in
15.79s**, with **15.96s** wrapper wall time: the unchanged **231** gate tests
and **64** new adapter tests. Only generated Python fake executables ran.
They cover boundaries, accelerated deadlines, malformed streams, private
canaries, refusal before spawn, partial-file retention, and child/grandchild
group termination, including ignored TERM and a leader that exits first.
The earlier 231-test results below remain separate historical proofs.
[The current result](../tasks/LATEST_TASK_RESULT/README.md) records the exact
source additions, invocation and log/JUnit identities.

**The actual GHCP-to-Codex route remains unbound.** No exact command, pinned
CLI version or real output stream was selected or tested. The documented
event envelope is a fixture contract, not proof of complete, prompt delivery
for this route or its sub-agents. Start events report effects already begun;
cancellation cannot prove that an excess turn/tool action never took effect.
An approved command/event binding, tool-call value, authentication isolation,
input and grader checks, applied-settings evidence and fixed-source review/CI
remain required before any separate execution decision. This change does not
enable the workflow, exercise a model, reopen a spent right or change a plan.

## Execution-path audit, 2026-10-25 02:40 KST

This historical audit predates the disabled adapter above.

**There is no GHCP/Codex task launcher in this gate to attach execution
limits to.** The current task therefore produces a source-backed blocker and
tool-cap options, not a new runtime guard. No executable, test, workflow,
plan, cap, dependency or authentication setting changed. The audit used local
source and previously cached public documentation only; no CLI was executed.

| Item | Actual execution path: before and after | What remains possible but unimplemented |
| --- | --- | --- |
| 1200 seconds/task | Not attachable in this branch: the live task launcher is absent. The collector enforces this value only while consuming supplied events. | An owned subprocess could have a deadline started before launch, process-tree termination and a retained partial receipt. There is no approved GHCP-to-Codex command/process owner here to wire or test. |
| 64 turns/task | Not attachable in this branch: there is no live event subscription or pre-turn admission hook. The collector stops at the 65th supplied turn-start event. | A live stream could trigger cancellation, but a start notification does not prove that the 65th turn was prevented before any effect. |
| Tool calls/task | Value still undefined; no tool-call cap is installed. | Counting events is documented; selecting a value and proving pre-effect enforcement remain separate requirements. |

The concrete route is
`.github/workflows/agentic-v2-ghcp-sol-gate.yml:27-35,58-66,74-83` ->
`batch-runner/ghcp_sol_actions_gate.py:485-527` -> `dry_capture:450-480`.
Both jobs refuse paid mode before checkout. The task step launches only the
model-free Python capture under **60 seconds plus 5 seconds for forced
termination**, with a **5-minute job limit**. It does not launch Copilot or
Codex. `collect_session_events:242-379` retains only supplied metadata; its
`subprocess_cleanup` is explicitly `not_applicable_no_subprocess_started`.
The separate inert VM plan still has `launch_enabled: false`, null CLI/SDK
versions and null execution-limit fields. Its validator preserves those facts.

The host's `/usr/local/bin/copilot:32-42` is not used by this workflow. Its
fallback credential resolution and binary selection must not be inherited as
an approved pilot adapter. Read-only package metadata reports **1.0.98** for
the wrapper's default runtime location and **1.0.79** for `/usr/bin/copilot`'s
package. Neither version is bound by the GHCP plan. Copilot's package README
identifies its own coding-agent harness; cached CLI reference [G3], line 658,
says `--agent` selects a custom agent, not the OpenAI Codex harness. Inventing
that binding would change the unresolved execution contract. No such
substitution, new launcher or fake-executable surrogate was added.

### Tool-event evidence and unselected values

The cached official streaming reference [G1], lines 297-305 and 417-428,
documents `assistant.turn_start` with `turnId` and `tool.execution_start`
with `toolCallId`; the latter means a tool **has begun executing**. Count
starts by bound session/agent/tool identity, not completion/progress events
again. The local **1.0.79** `session-events.schema.json:1244,15370` also
declares those event types. This is source/schema evidence, not an observed
session or a guarantee about the **1.0.98** runtime. The cached CLI reference
at line 711 describes JSONL output, but it does not establish that this
gate receives every event, including sub-agents. At line 697,
`--max-autopilot-continues` counts continuation messages, not these turns or
tool calls; it is not a substitute cap.

The separately installed OpenAI Codex SDK **0.147.0** declares `item/started`
and command/MCP/dynamic-tool items in `generated/v2_all.py:9183,9491,8239,4635,4663`.
Those could support a separately bound Codex counter; they are not GHCP
events. This branch's Foundry `batch-runner/core/codex_runner.py:1995-2050` has its own
turn watchdog but no numeric tool-call cap in the inspected runner. Native
HTTP requests, logical turns and tool executions are different units.

| Candidate only | Existing source and rationale | Limitation |
| --- | --- | --- |
| 8 tool calls/task | `batch-runner/core/agentic_sandbox_runner.py:43` and `batch-runner/core/agentic_tools.py:199-233` use an 8-call dispatch ceiling; the latter rejects an oversized batch before dispatch. This supplies a conservative existing reference. | It may stop file-heavy tasks early; no GHCP workload sufficiency was measured. |
| 32 tool calls/task | `batch-runner/core/agentic_v2_tools.py:56,141-145` and `batch-runner/core/agentic_v2_runner.py:753` use a 32-call dispatcher default with refusal before the next dispatch. This permits more tool work than the 8-call reference. | It is another harness's ceiling, not a GHCP entitlement or a measured requirement. It is unrelated to the native pilot's 32 HTTP requests. |

**Neither candidate is selected.** No new cap or reason code is introduced.
Existing `task_timeout_exceeded` and `turn_cap_exceeded` remain offline
collector reasons. Process-tree termination, retained live partial outputs
and fake-executable boundary/child-cleanup fixtures were **not implemented or
validated**, because no matching task execution adapter is present. This is
not a finding that GHCP cannot support a watchdog or emit countable events.
The next prerequisite is an explicitly bound GHCP-to-Codex launch/event
adapter with a process owner; it cannot be replaced by the host wrapper or
the separate Foundry runner without a new execution-contract decision.

On clean source `8d356e1c1dc13ae10193a045334c7e2ab089de35`, one combined
offline invocation reported **231 passed, 0 failed, 0 skipped in 11.36s**;
wrapper **11.575s**, exit **0**. This repeats the requested existing gate
bundle only: **138 Actions checks plus 93 VM checks**, including **4 Auto**
and **2 BYOK** refusals. No new test was added. The older **231/10.66s** proof
below remains separate. Exact source, invocation, log/JUnit hashes and
remaining gates are in the [current result](../tasks/LATEST_TASK_RESULT/README.md).

## Offline capture limits, 2026-10-25 00:15 KST

The collector now stops reading supplied events at the existing Actions draft's
1200-second deadline or its 65th documented `assistant.turn_start` event. This
is **offline collection enforcement, not live GHCP task enforcement**. The route
still has no GHCP-to-Codex adapter, model launcher or owned child process.
`paid_execution_allowed` and `live_enforcement_verified` remain false.

| Item | Before this change | After this change |
| --- | --- | --- |
| Wall-clock time | 1200 seconds/task was recorded only. The workflow already bounded a dry-run process to 60 seconds plus 5 seconds for forced termination, and a job to 5 minutes. | A local monotonic deadline and Linux real-time signal stop event collection with `task_timeout_exceeded`. The shorter workflow bounds are unchanged. No live task timeout is verified. |
| Tool calls | No value in this Actions draft or the inert GHCP VM execution block. | Still undefined: null plus `value_not_defined`. No tool-call cap or `tool_call_cap_exceeded` claim is invented. |
| Turns | 64 turns/task was recorded only. | The collector accepts at most 64 supplied turn-start events, including sub-agents, and stops on the 65th with `turn_cap_exceeded`. This does not prevent a historical turn or prove pre-call enforcement in a live adapter. |

The deadline begins when event collection starts, not when a historical task
started; setup and receipt writing are covered only by the existing workflow
process bound. Event timestamps cannot reset it. A timer interrupts a blocked
local iterator; unsupported platforms, non-main-thread callers or an existing
timer refuse with `task_timeout_guard_unavailable` before reading events.
Missing, malformed or duplicate turn identities refuse with
`turn_count_unverified`. Turn-start counts are not native-request or usage-event
counts, and a supplied stream without turn markers does not prove zero live
turns. No limit or approval is borrowed from the separate Foundry/native pilot.

The collector closes its explicit input generator and restores the signal
handler/timer on exit. Cleanup failure yields `session_event_cleanup_refused`.
The receipt identifies subprocess cleanup as not applicable because this route
starts no subprocess; termination of actual GHCP children remains unimplemented
and unverified. Adding a hypothetical launcher here would not close that gap.

Missing usage and cost keep their nullable numeric fields. New `usage_status`
and `cost_status` fields say `not available`, with fixed not-collected reasons.
No zero, tariff calculation or other estimate is substituted. Grade stays null.
Per-call model/effort/context observations remain settings only.

One combined offline invocation on clean local source
`6ab43d4c7198e9e720fabeac5cb0d796b68cc5c7` reported **231 passed, 0 failed in
10.66s**, wrapper **10.841s**, exit **0**: **25 new** capture-limit checks plus
**206 existing** Actions/VM gate checks. Fixtures test the 64/65-turn boundary,
cumulative deadline and EOF, an accelerated real OS alarm at a blocked read,
file closure, missing usage, unsafe timer ownership and canary non-egress.
No model or child-runtime process was used. Exact sources, commands and proof
hashes are in the [current task result](../tasks/LATEST_TASK_RESULT/README.md).

## Offline per-call capture, 2026-10-24 21:30

The model-free capture path now projects supplied GHCP JSON session events
into `capture.json` under `session_event_receipt`. It records each
`assistant.usage` event's allowlisted `model` and `reasoningEffort`, plus the
latest preceding `session.usage_info.tokenLimit` for the same agent. The
receipt identifies the context event's position and labels the association
`preceding_same_agent_session_snapshot_not_call_attestation`. A main-agent
snapshot cannot fill a sub-agent's missing context; a later snapshot cannot
repair an earlier call. A sub-agent origin without `agentId` also refuses;
the documented `initiator` or legacy `parentToolCallId` cannot implicitly
select the main-agent snapshot. Missing fields, non-Sol models, non-Max effort,
non-1000000 context limits, duplicate usage events and differences between
calls fail the attempt with fixed reasons and exit 2. No value is filled from
the requested settings. Arbitrary non-Sol model strings are suppressed as
null plus `served_model_mismatch`, not copied into the public receipt.

This is a document-based JSON projection tested with synthetic events, **not
an actual GHCP output capture or a GHCP-to-Codex execution adapter**. The
cached official event reference [G1] documents per-call model/optional effort
and session-level `tokenLimit`; [G2] says usage is ephemeral and includes
sub-agent calls. Codex's separate `modelContextWindow` signal [L1 below] has
no established GHCP binding here. Its receipt field remains null with
`not_in_documented_ghcp_event_contract`; the collector does not invent a
GHCP field or combine unbound streams from different harnesses.

Every receipt retains `evidence_level: settings_only`,
`applied_settings_verified: false`, `live_source_verified: false` and
`stream_completeness_verified: false`. Consistent metadata is not proof of
the actual served model, applied Max or a granted 1M window. Supplied usage
event counts are not a native-request counter. The dry-run runner itself
makes zero model/grader calls; usage, cost and grade stay null. Usage and cost
now also carry the explicit availability statuses described above. Paid execution
and retry authority remain false even for `consistent_settings_only`.

The default matrix/capture commands still perform an empty, model-free
rehearsal. For an explicitly supplied **offline synthetic** JSONL stream, add
`--session-events /absolute/synthetic-events.jsonl` to the existing capture
command. The reader does not discover session logs or credentials. It accepts
one regular, non-symlink file bounded to 1 MiB, 64 KiB per line and 4096
events; these are parser limits, not a paid-call allowance. Parse/read failures
retain only a failed metadata receipt. Raw conversations, errors, headers,
event IDs and credentials never enter that receipt or CLI output.

Before catalogue/event reads or capture writes, exact Sol selection is
required. `--model auto`, `--byok` and any `--provider-config` refuse.
Inherited `COPILOT_PROVIDER_*` or `COPILOT_PROVIDERS_CONFIG` names also refuse,
without inspecting their values. Inherited `COPILOT_MODEL` and `COPILOT_HOME`
refuse as unverified rather than being resolved. The default
`.copilot/providers.json` is checked only for existence: even an empty or
symlinked registry refuses, and its contents are never read. Tests substitute
a synthetic home; no real user configuration was examined. These are local
preflight checks, not a universal server-side no-fallback guarantee. A future
reviewed adapter still needs controlled configuration/authentication and a
subscription installed before any call, including sub-agent calls.

The initial fixture cases and existing Actions/VM gate tests report **204
passed, 0 failed in 9.89s** (pytest), **10.084s** wrapper wall time, exit **0**.
Source review then found the missing-agent-ID sub-agent edge above. A separate
follow-up on the corrected source reports **7 passed, 0 failed in 0.23s**,
wrapper **0.390s**, exit **0**: two new origin cases and five directly coupled
context cases. These are separate proofs, not a pooled full-suite pass on the
final source. No full suite or live session was run. The original source,
command and evidence hashes remain in local Git record
`fe863326f996fe8708cd4098b7ec6ad7dd61905b:tasks/LATEST_TASK_RESULT/README.md`;
they are not added to the new 231-case result.

## Evidence and authentication audit, 2026-10-24

This section preserves the earlier **18:45** audit at the source below.
The new offline collector does not close its live-runtime or authentication gaps.

**Paid execution remains blocked.** At inspected source
`f205207bb73f123ed7ff858e0feefd35d23e53ab` (tree
`942355a97c7c61fbe65aec6f0c5b070e0aeebb90`), the gate has no GHCP/Codex
inference adapter. All three requested properties are **settings only** in
this route, not observations that they took effect. This is a documentation
audit, not evidence that Sol is unavailable or that no supported route exists.
No CLI/session, authentication, model request or test was run for this audit.

### What can be established

The verdicts below apply to this exact GHCP + Codex gate. A documented signal
in another harness does not establish that the gate can collect it.

| Property | Current verdict | Source and remaining evidence boundary |
| --- | --- | --- |
| Actual response model | Settings only (`설정 표시만`) | `batch-runner/ghcp_sol_actions_gate.py:25-31,56-75` copies requested Sol and sets every served value to `not available`. Copilot SDK documents per-call `assistant.usage.model` [G1, G2], a useful observation candidate. A pinned GHCP-to-Codex adapter and evidence that its value comes from the responding service, not the requested model, are still missing. |
| Reasoning Max | Settings only (`설정 표시만`) | `gpt56_sol_ghcp_codex_vm_gate.yaml:16-31` labels `max` as a request. Copilot SDK documents optional per-call `assistant.usage.reasoningEffort` [G1]. Missing effort must remain unknown; reasoning-token counts do not prove a tier. The CLI reference accepts an effort flag but describes `max` in an Anthropic context [G3]; this is not a provider-specific guarantee for GHCP Sol. Do not silently map `xhigh` to Max. |
| Context 1M | Settings only (`설정 표시만`) | The same plan declares a nominal `1000000`, not a verified server allowance. Copilot `session.usage_info.tokenLimit` and Codex `modelContextWindow` expose runtime context-window metadata [G1, G2, L1]. That metadata alone does not prove the GHCP service accepted the requested window or that this workload exercised it. OpenAI's Sol page advertises **1,050,000** context tokens [O1], which is neither the plan's nominal **1,000,000** nor a GHCP entitlement receipt. |

OpenAI documents Sol support for `reasoning.effort=max` [O1], and Codex
documents `model_reasoning_effort`, `model_context_window` and the separate
auto-compaction threshold [O2]. These establish configuration/capability
semantics, not this account's effective GHCP settings. Changing the window
or inspecting token usage would not establish that all history was retained
without compaction.

The installed, repository-pinned `openai-codex` / `openai-codex-cli-bin`
**0.147.0** pair is a different surface from Copilot SDK:

- `openai_codex/client.py:238-272` starts a Codex app-server subprocess and
  exchanges JSON-RPC; it is not a Python HTTP model client.
- `openai_codex/generated/v2_all.py:10241-10271` returns thread configuration
  including `model`, `modelProvider` and `reasoningEffort`. A thread-start
  response is not a provider completion. Its `Turn`/`TurnStartResponse`
  schema at `9643-9695` does not supply the provider response body's model.
- The same file at `3204-3219` names efforts through `xhigh` but accepts
  unknown nonempty enum strings. Parsing `max` therefore does not prove CLI
  or provider support. At `5294-5303` and `8579-8594`, token counts and optional
  `modelContextWindow` remain distinct from an applied-Max/1M receipt.

These installed-file references are **L1**, not executed runtime evidence.
The inspected venv has no `github-copilot-sdk` package. Locally installed
`@github/copilot/package.json:4` reports **1.0.98**, but its `README.md:5`
identifies the Copilot coding-agent harness. `--agent` selects a custom agent
in the current CLI reference [G3]; naming it `codex` would not prove use of
OpenAI's Codex harness. Current web documentation is not a version guarantee
for that installed binary. The separate Foundry native observer is not a
GHCP adapter and is not imported or credited as this gate's proof.

### Fallback prevention and detection

The unchanged plan's `automatic_fallback_allowed: false` and `fallbacks: []`
are declarations, not implemented provider controls. The current Python
entrypoint still refuses paid mode before capture
(`ghcp_sol_actions_gate.py:133-141`).

For a future reviewed adapter, select the exact registered model, never
`auto`; Auto explicitly routes between models [G3, G8]. Keep the GHCP provider
and authenticated identity fixed. Reject alternate providers/BYOK: GitHub
documents that BYOK variables can route model requests elsewhere despite
GitHub authentication [G4]. Do not accept Fast, another model, or an
unreviewed alias as Sol. These are proposed checks, not new runtime code.

Install metadata capture before execution begins, record each call's
model/effort including sub-agent calls, then compare the full observed sequence
with the registration.
`assistant.usage` is ephemeral: ordinary saved session logs/resume do not
recover it [G1, G2]. No actual session log or private transcript was read here.
Retain only allowlisted metadata with call/source bindings; do not publish
raw events, prompts, headers, tool output or credentials. Missing, conflicting
or unbound metadata must stop acceptance and further requests, not authorize
a retry. Detection after a call cannot undo that call's spend.

Codex 0.147.0 also defines `model/rerouted` metadata with source/target model
and thread/turn IDs (`v2_all.py:2436-2451`). Its documented schema reason is
`highRiskCyberActivity`; it is not a universal report of every possible
provider substitution. No inspected contract establishes a universal
server-side no-fallback switch. A missing reroute event or unchanged requested
model is not proof that silent provider fallback cannot occur.

### Authentication drafts, not authorization

**Conditional recommendation: job-scoped `GITHUB_TOKEN`**, only after the
existing repository's organization eligibility, billing identity, policy and
selected runtime support are explicitly established. None was queried here.
If those conditions do not hold, stop for an owner choice; do not move the
repository, change the billing identity, or automatically select another option.

| Draft | Scope and supply | Lifetime and disposal | Exposure and unresolved condition |
| --- | --- | --- | --- |
| **A. Job `GITHUB_TOKEN` (conditionally recommended)** | GitHub documents organization-owned Actions use with `copilot-requests: write` and the organization Copilot CLI billing policy [G5, G6]. The current workflow has only `contents: read`; no permission is changed here. Supply only to the approved runtime, not to model tools. | GitHub issues a token per job; it expires when the job finishes, subject to the hosted-runner maximum lifetime [G7]. Close runtime/credential channels and discard ephemeral runner state. Job-token expiry is not an execution timeout. | No new long-lived secret, but an exposed token can spend against the organization during its validity. Current organization/policy/billing and pinned-runtime eligibility are unverified. The docs' recommendation to use another workflow framework is not adopted. |
| B. Owner fine-grained PAT in a protected Actions environment | Personal-account-owned token with the **Copilot Requests** account permission; no unrelated repository write permissions. A separate checkout credential stays separate. Use an explicitly selected credential channel, such as runtime-only `COPILOT_GITHUB_TOKEN` [G4]. | Set the shortest owner-approved supported expiration. Remove process exposure at exit; revoke the PAT on GitHub after the approved execution window, including cancellation/failure. Removing an Actions secret or a local file does not revoke a copied PAT. | The permission is account-level, not a five-task or model-specific spending cap. Same-user tools, process environments, diagnostics or artifacts can expose it. Protected-environment approval and credential isolation are required; no PAT was read, created or stored. |
| C. Existing approved GitHub App installation token | Organization **Copilot Requests: Read-only** (`organization_copilot_requests: read`), with organization installation/billing approval [G6]. An approved service would supply only the short-lived token, never its signing key, to the runtime. | Installation tokens expire after **one hour** [G6]; revoke the installation token at the end and discard local exposure. App authorization/signing-key revocation is a separate owner action if compromised. No refresh loop is proposed. | Requires an existing approved App/token supplier and matching billing identity, neither established here. GitHub recommends A for Actions. An App signing key would create a larger persistent secret risk; this audit does not authorize creating a broker or App. |

For SDKs that support it, explicit token injection plus
`useLoggedInUser: false` disables credential discovery [G6]; setting that
flag while relying only on environment-token discovery would be incorrect.
Do not reuse a developer login/cache or allow an automatic account fallback.
The inspected local `/usr/local/bin/copilot:32-42` wrapper invokes
`gh auth token` when token variables are absent and can select another binary;
it was **read as code, never executed**. GitHub also documents keychain and
`gh` fallback, and that `/logout` removes local credentials without revoking
them on GitHub [G4].

All options require a fixed reviewed source, no untrusted/fork code in the
credential step, a boundary that keeps tokens out of the model's tools, and
metadata-only output. Step-local environment variables and log masking alone
do not isolate a token from same-user processes. Cleanup needs an expiry or
owner-controlled revocation backstop; a workflow `always()` step alone cannot
guarantee cleanup after runner loss. No option proves model/effort/context or
enforces timeout/tool/turn limits. Those remain independent stop-before-spend
conditions; authentication is not permission to run this pilot.

### Audit sources

Public documentation was fetched on **2026-10-24**, without account access.
The mutable documentation is evidence of its stated interface, not proof
of this project's entitlement or installed-version behavior. Local source and
documentation hashes are retained with this audit's completion record.

- [O1: OpenAI GPT-5.6 Sol model reference](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
- [O2: Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), the official redirect target of `developers.openai.com/codex/config-reference`.
- [G1: Copilot SDK streaming events](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/streaming-events#assistantusage), including `assistant.usage` and `session.usage_info`.
- [G2: Copilot SDK usage and billing](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing#per-call-token-counts).
- [G3: Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference), model/effort flags and custom-agent selection.
- [G4: Copilot CLI authentication](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli), supported credentials, selection order and revocation distinction.
- [G5: Copilot CLI in Actions with GITHUB_TOKEN](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions).
- [G6: Copilot SDK server-to-server authentication](https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/server-to-server-tokens).
- [G7: GITHUB_TOKEN lifecycle](https://docs.github.com/en/actions/concepts/security/github_token).
- [G8: Copilot auto model selection](https://docs.github.com/en/copilot/concepts/models/auto-model-selection).

## Existing path surveyed

| Workflow | Inputs and task layout | Credentials and retained evidence |
| --- | --- | --- |
| `agentic-v2-stage-run.yml` | `stage`, `mode`, `isolation`, `plan`, `run_id`, `resume_from_github_run`, `comparison_reviewed_source_sha`; free planning, paid shard matrix, collection and comparison admission. Planner packs up to 13 tasks/shard, so advance-check five normally share one shard/job. | HF_TOKEN for pinned input fetch, Azure OIDC client/tenant/subscription IDs and Foundry endpoint; GITHUB_TOKEN for resume downloads, paid job permissions include actions read and OIDC. Uploads the full run directory including hidden exec streams, separate host proofs and cost rollup. **Do not reuse its broad artifact upload for private inputs.** |
| `agentic-v2-stage-a-probe.yml` | `mode=dry-run/paid`; free check then one paid probe task, not the five-task run. | HF_TOKEN, Azure OIDC and Foundry endpoint. Paid artifact is metadata-only model-call record, not prompt/reply/reasoning text. Even its free job fetches the dataset; it is not this card's input-free rehearsal. |
| `gpt54-time-budget-first-v2.yml` | `reviewed_source_sha`, `reviewed_source_tree`, `request_sha256`, `request_json`; one source-bound registered task/job, with no replay. | Validates before credentials; HF private input/claim/retention and Azure OIDC separated by phase. Only validated `completion.json` is uploaded; canonical outputs remain private. This is the stronger privacy pattern reused here. |
| `agentic-sandbox-preflight.yml` | Image/SBOM/AppArmor inputs; self-hosted model-free containment checks. | No model credential permitted. Not the selected standard-runner execution route. |

The surveyed V2 workflows contain no explicit `::add-mask::` step.
GitHub's masking of configured secrets is not a privacy boundary for task
wording, reference contents, tool output or generated deliverables. The new
route supplies no secrets, prints only fixed status, reads only the public
score-free catalogue, and uploads exactly one generated `capture.json` per
task. It never uploads a directory, raw stream or file hashes.

This is an additive sibling in the existing `.github/workflows/agentic-v2-*`
path, reusing its plan-to-matrix structure and pinned checkout/Python/artifact
actions. It does **not** invoke the paid V2 conversation runner, Firecracker
boot action, Azure route, or legacy shard/resume logic; those would inherit
unapproved spending, private capture and obsolete VM requirements.

## Fixed cohort and grading contract

`core/execution_envelope_tasks.py::select_advance_check_tasks` derives the five
ordered IDs from `experiments/execution_envelope/gdpval_task_catalog.json`.
`advance_check_plan.yaml` pins the same order and input versions.
`experiments/execution_envelope/gpt56_sol_ghcp_codex_vm_gate.yaml` binds the
GHCP identity, original-input policy, inherited developer instructions and
grader policy. That older inert VM prerequisite contract remains unchanged;
its VM/reset blockers are not assertions about this new Actions target.

The grader template is
`grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml`: rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, prompt v2.2, Sol/Max judge,
one pass/task, grade schema 1.4. The GHCP gate uses only its policy blocks,
**not** its 220-task rerun identity. Five-task inference identity, original
input verification and grader validation remain unresolved. Nothing is graded.

## Local rehearsal and capture

From `batch-runner`, `python3 ghcp_sol_actions_gate.py --matrix` emits the
five-task matrix. For each returned ID, run:

```bash
python3 ghcp_sol_actions_gate.py --dry-run true --task-id TASK_ID \
  --state-root /absolute/fresh/parent/ghcp-sol-gate
python3 -m pytest -q tests/test_ghcp_sol_actions_gate.py
```

The state-root parent must exist. Each task gets a fresh directory; reuse
refuses. `private/` contains empty transcript/tool-call/command streams, empty
input/output hash arrays, a dry-run exit record and an empty `files/` directory.
These are path placeholders, **not** real input staging or transcript evidence.
Only `capture.json` is artifact-eligible; it contains relative logical paths,
requested settings, actual Python/OS versions and explicit unavailable CLI/
served values. Local execution does not prove the requested hosted image ran.

Proposed paid caps are 1200 seconds/task (the V2 stage cap), 64 model turns/task
(draft choice), zero retries; neither approval nor live enforcement is claimed.
The offline collector now applies the time/turn values only as described above.
The dry-run workflow enforces 60 seconds/process and five minutes/job with
zero model turns. Unknown usage/cost/grade stay null, never inferred as zero;
usage and cost have explicit `not available` statuses.
Both planner and task jobs independently reject every `dry_run` value except
the exact string `true` before checkout. The Python entrypoint separately
rejects false or malformed values before catalogue reads or capture writes.
Local tests execute both shell guards with true, false, missing/empty,
case-changed, numeric and whitespace-bearing values; they do not dispatch
Actions or prove hosted behavior.

## Questions blocking paid execution

- How are scoped GHCP/Copilot credentials supplied, kept outside model tools,
  and disposed of on standard Actions runners? Is this unattended use supported?
- Which supported route actually selects the Codex agent harness, pinned CLI/
  SDK versions, Sol model, Max effort and 1M context without fallback? What
  independent served metadata proves each rather than repeating requested values?
- How are original prompts/references verified and staged privately, and raw
  transcript/tool/file captures retained privately without leaking in logs,
  artifacts, action diagnostics, credentials or caches?
- What network/tool permissions, budget/usage policy, paid timeout/turn/tool/
  token caps, cancellation handling and no-retry admission are approved?
- What five-task inference/grader identity, judge validation, repeat/variance
  plan and pass/fail criteria govern the decision? No quality result follows
  from this wiring rehearsal or from these five cases alone.
- Who reviews the exact source and authorizes push, hosted dry-run dispatch,
  and separately paid inference/grading? All remain unapproved on this card.

## Default-agent evidence refinement, 2026-10-26

**The full b/c/d requirements remain unknown.** Installed help confirms
selection and file-export mechanisms, including a final usage JSON option and
local OpenTelemetry output. It does not establish applied Sol/Max/numeric 1M,
complete capture under termination, or both fixed execution limits on the real
CLI route. This is a documentation-only follow-up at clean source
`ff8249cd8d94d07349cbc81292365c5e0f782262`, tree
`603a619c5ddf7715346f7dbdd135009f431d4eeb`; no execution approval is added.

### Installed evidence and version boundary

The Desk platform package is
`/home/dev/.local/share/nas-copilot-desk/copilot-cli/node_modules/@github/copilot-linux-x64`.
The system platform package is
`/usr/lib/node_modules/@github/copilot/node_modules/@github/copilot-linux-x64`.
Package-relative source references below refer to the system package unless
explicitly marked Desk. New help files are retained in
`/ai-work/copilot/_tmp/p5-ghcp-cli-contract.7F3vmK/`.

Direct `--no-auto-update --version` output again reports Desk **1.0.103** and
system **1.0.79**. The Desk sibling `package.json:3` reports **1.0.98**;
its `README.md:5-8` says the executable embeds the JavaScript bundle and native
addons. The inspected Desk platform and parent package expose no standalone
event schema or independently versioned 1.0.98 executable. Consequently, the
requested **1.0.103 versus 1.0.98 output-schema comparison could not be
verified**. The 1.0.79 schema/serializer is a separately identified reference,
not evidence that either other version emits identical events. No download,
installation, binary-asset extraction or version-pin change was performed.

Eleven help/version invocations exited **0**, using direct platform binaries,
`env -i`, fresh task-owned `--config-dir` paths, `--no-auto-update`, and
**15s TERM + 3s KILL** bounds. Only Desk received the supported
`--disable-client-telemetry` flag. `help-invocations.md` records the exact
argument/output mapping. No wrapper, prompt, login, session or export was run;
no telemetry/content capture was enabled. These are host help observations,
not tests, VM evidence, account entitlement or provider observations.

### Requirement decisions

| Requirement | Decision | Confirmed mechanism and unresolved condition | Evidence |
| --- | --- | --- | --- |
| b: select and prove Sol, Max and numeric 1M | **Unknown** overall; **yes** for selection syntax | `--model gpt-5.6-sol --reasoning-effort max --context long_context` is documented syntax, not an executed command. A tier label does not attest numeric 1M or applied reasoning. Session state and call-model labels are not independent served-setting proof. | `desk-help.txt:53-59`; `desk-config-help.txt:148,165-167`; `schemas/api.schema.json:12983-13001` |
| c: complete transcript, tool calls and generated files | **Unknown** overall; **yes** for documented file-output options | JSONL, Markdown sharing, final usage JSON and a local telemetry exporter exist. Neither exact 1.0.103 event coverage nor complete delivery/flush on interruption is established. These exports do not establish a byte-complete archive of generated or uncommitted files. | `desk-help.txt:95-110,230-231`; `desk-monitoring-help.txt:33,124-188`; system `app.js:2744-2745` |
| d: enforce 1,200 seconds and 64 turns during execution | **Unknown** as the required pair | No top-level prompt-mode timeout or total-turn cap is documented in the inspected help/config surfaces. The existing disabled adapter has a deadline and observed-start counters; its real CLI binding, stream completeness and pre-effect limits remain unverified. | `desk-help.txt:188-189`; `schemas/api.schema.json:28781-28792`; repository `batch-runner/ghcp_sol_execution_adapter.py:1-5,79-84,88-115,321-335` |

The b syntax uses neither Auto nor BYOK, but the syntax alone is not proof that
fallback never occurs. `desk-config-help.txt:110-112` documents an optional
rate-limit switch to Auto, default false. No actual user's setting was read.
The existing Auto/BYOK refusal and per-call mismatch requirements are unchanged.

### What capture can and cannot supply

| Surface | Source-supported record | Limit |
| --- | --- | --- |
| Session/API state, 1.0.79 | `session.start` exposes optional selected model/effort/tier fields; tier may be null. `CurrentModel` reports selected state, reading effort synchronously after the model lookup resolves. `assistant.usage.data.model` labels the API call and optional `reasoningEffort` describes effort. `session.usage_info.data.tokenLimit` is a numeric context snapshot. | No live value was read. Start/state labels are not provider attestation. Usage/context events are ephemeral, and the JSON stdout writer excludes them and model-change events. |
| Stdout and saved session export | `--output-format json --stream on` documents JSONL. `--share [<path>]` saves Markdown **after completion**; `--log-dir` and `--log-level` configure diagnostic logs. | The 1.0.79 writer excludes usage, context, model changes and workspace-file-change events. Its final `result` carries aggregate usage, not per-call served settings. Disk session logs cannot restore events declared ephemeral. |
| Final usage file, Desk 1.0.103 | `--usage-output-file <file>` promises final usage statistics in JSON. | Help supplies no field-level schema, per-call model/effort/context contract or guarantee of a file after forced termination. This flag was not used and does not prove reconciled charges. |
| Local OpenTelemetry file | `COPILOT_OTEL_FILE_EXPORTER_PATH` is documented to write signals as JSONL. The trace tree includes `chat <model>` and `execute_tool <tool>` spans. | Help does not identify a provider-response model attestation or applied Max/numeric 1M fields. Prompt/response/tool arguments are excluded by default. Opt-in content capture describes them, but requires a separate privacy decision and still does not prove full delivery or generated-file retention. |

The schema locations for the first row are
`schemas/session-events.schema.json:1338-1344,1444-1446,1515-1518,13065-13090,15936-15942`.
The stdout exclusion set and final aggregate result are in `app.js:2744-2745`.
Desk help documents the local telemetry path at
`desk-monitoring-help.txt:20-33`, the span tree at `124-136`, and default/opt-in
content behavior at `171-188`. `help logging` lists diagnostic levels, not a
full transcript or served-model guarantee. No private logs or session files
were inspected, and no exporter was configured or started.

### Limit names that must not be substituted

- `--max-autopilot-continues` counts continuation messages, not every agent
  turn (`desk-help.txt:188-189`; system `app.js:2334,2389,2837`).
- `maxAgentTurns` in `sdk/index.d.ts:451-465` belongs to internal agent
  definitions; `app.js:2338` uses it for the completion reviewer. It is not an
  established top-level `-p` option.
- `COPILOT_TASK_WAIT_TIMEOUT_SECONDS` bounds waiting for pending background
  work, not the whole task (`sdk/index.d.ts:11105-11111`).
- `FactoryRunLimits.timeoutSeconds` covers factory active execution
  (`schemas/api.schema.json:15638-15657`), a different execution interface.
  The ordinary `SessionLimitsConfig` at `28781-28792` only declares
  `maxAiCredits`. Help explicitly calls the credit stop post-call
  (`desk-config-help.txt:177-183`), not a wall-clock or turn limit.
- The existing adapter's owned-process deadline and TERM/KILL cleanup remain
  available as an offline mechanism. Counting `assistant.turn_start` can stop
  after notification; it does not prove the next effect was prevented. The
  adapter itself records these limitations and is not wired into the workflow.

### Evidence retention and unchanged decision

`installed-evidence.sha256` binds both binaries and metadata, the system
serializer, both schemas and SDK declarations; its SHA256 is
`e054e9ab47d84e00a0e365811831592ec4ec7c0d1e72e829263c61512efa01ad`.
`help-evidence.sha256` binds all eleven retained help/version files; its SHA256
is `53af9ce0714318440b964dab18f22f038c9a93875e9c97a1bae221f46d122e62`.
No pytest or collection was rerun; the earlier synthetic results remain
separate. This addition preserves the preceding document and changes no
adapter, workflow, model, cap, permission, authentication or finite right.

**Recommendation A is unchanged:** preserve GHCP + Codex + Sol/Max/1M and
hold execution while obtaining the missing contract. B still requires an
owner-approved harness/scope change; C still stops without a benchmark result.
The new export options do not authorize B or close the paid gate. VS Code
Agent Host was not re-audited in this installed-Copilot follow-up; its prior
a/b/c/d unknown decisions remain, not a new finding of product absence.
