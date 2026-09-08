# Codex's own agent: what is officially supported, and what is still unknown

- Written: 2026-08-25
- Updated: 2026-08-26 — the documentation was searched again and half of the
  open question is now answered. See section 3a.
- Updated: 2026-09-08 — the documentation now covers the Azure provider, and the
  run place was built against the pinned runtime and checked without a paid
  deployment. Running it on a host that can sandbox then found a defect in the
  run place itself. See section 3b.
- Status: **built, executing on one host, and not connected.** The code exists
  and most of the chain is checked against the real Codex binary. As of
  2026-09-08 the agent has been observed executing a command inside its sandbox
  — once, on GitHub's `ubuntu-22.04` runner, against a scripted provider, and
  only after a defect in this repository's own run place was found and fixed
  (§3b). No request has yet reached the Foundry deployment, so the run place is
  still graded `structure_check_only` and a batch run in this mode is still
  refused.
- Related GitHub Project: hyeonsangjeon/projects/5 — cards
  "같은 GPT 모델의 실행 환경별 성능 비교" and
  "Codex SDK와 Foundry GPT를 연결해 220문제 실험 실행"

## 1. The problem a person actually hits

The comparison of run places has five columns. The fifth is Codex's own built-in
agent: the tool picks its own actions, runs its own commands, reviews its own
work, and retries, without this repository directing any of it.

That column is still empty, but it is no longer empty for want of code. This
document records what was checked, what turned out to be true, what was built,
and the one thing that remains — so that the next person does not repeat the
search, and so that nobody fills the column in on an assumption.

## 2. Why an empty column is the right answer until a request succeeds

The comparison's whole claim is that only the run place changes. One of the
conditions every column must meet is that it uses **the same deployment** as the
others. If Codex's own agent cannot be pointed at the same deployment, then a
Codex column would differ in two ways at once — the run place *and* the model
being served — and any difference in the scores could not be attributed to
either.

So the question is not only "can Codex be automated?" It is "can Codex's own
agent be pointed at this exact deployment?" The second question is the one that
decides whether the column can ever be honest, and it is answered by a request,
not by a build.

## 3. What was checked, and what it says

Sources consulted were the official Codex documentation and the repository
itself.

**Confirmed: Codex can be run without a person answering prompts.**
A non-interactive command mode is documented (`codex exec`), which takes an
instruction and runs to completion. Approval behaviour and sandbox behaviour are
configurable settings.

**Confirmed: Codex supports providers other than its default.**
The configuration format includes entries for defining model providers, and
separately an `openai_base_url` setting which the documentation describes as the
way to "point the built-in OpenAI provider at an LLM proxy, router, or
data-residency enabled project" without defining a new provider.

**Confirmed: provider settings are deliberately restricted.**
Provider, credential, and telemetry settings are ignored when they appear in a
repository-local configuration file and must be set in the user-level
configuration. Codex prints a warning when a repository tries to set them. This
is a security boundary and is relevant: a benchmark harness cannot simply commit
a provider configuration into a repository and have it take effect.

**Not confirmed: pointing Codex's own agent at an Azure AI Foundry deployment
using the sign-in this repository requires.**
The documentation describes changing the base address for the built-in provider.
It does not describe using an Azure AI Foundry deployment with a token obtained
from a directory sign-in, which is the only authentication this repository
permits — it explicitly refuses to run with a fixed interface key, a client
secret, or a stored password. A base-address change alone does not establish
that the token flow this repository mandates is supported.

**Not confirmed: an official route for feeding an outside benchmark's tasks in
and collecting deliverable files out.**
Nothing was found describing this as a supported use.

**Confirmed about this repository: there is no Codex code path.**
The list of run modes in `core/executor.py` has no entry for it, and no module
starts a benchmark task this way. Mentions of Codex in the repository are in
documents people read, not in code that runs.

## 3a. Searched again on 2026-08-26: half the question is now answered

The question in section 7 has two halves, and it turns out they have different
answers. Separating them is the main result of the second search.

**Half one — getting a token from a directory sign-in. Confirmed supported, in
general.** The configuration reference documents a table
`model_providers.<id>.auth`, described as command-backed bearer token
configuration for a custom provider. Its `auth.command` setting runs a command
which "must print the token to stdout", with `auth.args`, `auth.cwd`,
`auth.timeout_ms`, and `auth.refresh_interval_ms` alongside it. It is documented
as mutually exclusive with `env_key`, `experimental_bearer_token`, and
`requires_openai_auth`.

That is exactly the shape a directory sign-in needs: a command runs, it prints a
short-lived token, and the token is refreshed when it expires. The earlier
version of this document said the documentation "does not describe using an
Azure AI Foundry deployment with a token obtained from a directory sign-in".
That was right about Azure and wrong about tokens: a general mechanism for
tokens from a command is documented. This repository's rule is that
authentication comes from a directory sign-in rather than a fixed key, and that
rule could be satisfied by this setting.

**Half two — addressing an Azure AI Foundry deployment. Still not confirmed,
and the evidence now leans against it.** Three things were found:

1. `model_providers.<id>.wire_api` documents `responses` as "the only supported
   value". Azure AI Foundry serves a Responses API of its own, but nothing
   states that the format Codex sends is accepted by it. A shared name is not a
   shared format.
2. Azure OpenAI and Azure AI Foundry do not appear in the configuration
   reference at all. The only Azure entry anywhere in the documentation
   navigation is a workload identity federation page, which is about using an
   Azure identity to authenticate **to OpenAI** — the opposite direction from
   what this run place would need.
3. Amazon Bedrock, by contrast, has a built-in provider selected with
   `model_provider = "amazon-bedrock"`, its own settings
   (`model_providers.amazon-bedrock.aws.profile` and `.aws.region`), its own
   documentation page, and its own authentication path covering federated
   identity. It is documented as providing "an OpenAI-compatible Responses API
   implementation for supported OpenAI models".

Point 3 is what changes the weight of the evidence. Before it, Azure's absence
could be read as documentation simply not covering every case. After it, the
documentation demonstrably does cover a competing cloud in depth, with a
purpose-built provider and a statement of format compatibility. Azure has none
of those. That is not proof of impossibility, but it is no longer neutral, and
it should not be read as "probably fine, nobody wrote it down".

**What this means for the column.** It stays empty. What changes is that the
remaining unknown is now one specific, checkable thing rather than a general
doubt, and it is written in section 7 below.

## 3b. Built on 2026-09-08: the documentation moved, and so did the code

Two things changed since section 3a, and they should not be run together.

**The documentation half is answered.** The configuration reference now carries
an Azure provider example and a `model_providers.<id>.query_params` setting,
which is the documented place for a dated `api-version`. Section 3a's
"Azure does not appear in the configuration reference at all" is out of date and
must not be quoted as a current blocker. Microsoft's own Responses API page
documents the endpoint shape on the other side.

**The deployment half is not answered, and no amount of reading answers it.**
Whether *our* account, in *our* region, accepts what Codex sends, with a
directory sign-in rather than a key, is a fact about a live endpoint. Sections 7
and 12 keep it separate for that reason.

What is new is that the run place is now **built** rather than sketched, and
several of section 7's guesses turned out to be wrong. The corrections, each
read off the pinned code rather than off documentation:

1. **The SDK does not reimplement the agent.** `openai-codex==0.147.0` starts
   the shipped binary — `codex app-server --listen stdio://` — and speaks
   JSON-RPC to it. The distinction section 4 warns about is therefore satisfied
   by construction: this is Codex's own loop, not a re-creation of it. The SDK
   pins `openai-codex-cli-bin==0.147.0` exactly, so the pair is one runtime;
   `batch-runner/requirements.txt` repeats both numbers and
   `core.codex_runtime_config.require_pinned_runtime` checks them at run time.
2. **The provider table goes on the command line, not into a config file.**
   Section 7's block said "in the user-level configuration". That would work but
   is the wrong shape here, because it edits the operator's own machine. Codex
   ignores provider, credential and telemetry settings found in a
   *repository-local* config on purpose, so a table committed here would be
   inert. `core.codex_runtime_config.provider_config_overrides` passes the same
   table as `--config key=value` arguments instead: one run, one provider, and
   nothing left behind on the host.
3. **`/openai/v1/` is not an `api-version`.** It is the undated route, where the
   request's `model` argument names the deployment. A dated `api-version`
   belongs to the legacy route. `CodexProviderSettings` refuses a plan that puts
   one in `query_params` alongside the undated endpoint, because that would
   describe a route we are not using.
4. **Usage arrives per request; Codex reports it summed per thread.** The
   earlier wording here — "two turns of 11 and 40 settle as 51" — was wrong, and
   wrong in a way that matters, because 11 + 40 = 51 and 40 − 11 = 29 are both
   defensible readings of it. The actual shape, read off the SDK and pinned by
   the end-to-end fixture: the upstream server reports **11 tokens for the
   tool-call request and 40 for the final request, both inside one turn**.
   `ThreadTokenUsage.total` is Codex's running sum across the thread, so it
   reads **51**, and that is what the receipt records for the turn.
   `ThreadTokenUsage.last` would read 40 — the final request only — which is
   why the adapter uses `total` and not `last`. There is no reading under which
   the answer is 29.

   The per-request 11 and 40 are visible only because the fixture is the server.
   A real run sees the thread total and nothing else: the SDK exposes no
   per-request breakdown, which is exactly what
   `REASON_CALL_REACHABILITY_UNKNOWN` on every Codex settlement says out loud.

   `turn_usage_delta` subtracts a before-total so that a second turn on the same
   thread cannot re-charge the first. Today that subtraction never changes an
   answer: `codex_runner.py` opens a fresh thread per task and runs one turn in
   it, so `before` is `CodexTokenTotals.zero()` every time. It is guarding a
   future, not doing present work, and the earlier text implying otherwise was
   overstating what runs. `tests/test_codex_cost_adapter.py` pins both the
   arithmetic and the refusals — a cumulative counter that goes backwards is an
   error rather than a clamp, and `cache_write_input_tokens`, which the receipt
   has no field for, produces `usage_partial` rather than a total that looks
   complete.

   The receipt contract is the repository's existing one and no new price table
   was added.

`batch-runner/tests/test_codex_runtime_end_to_end.py` drives the real pinned
binary against a stand-in Responses server on the loopback interface. No paid
deployment takes part, and the agent's own settings are not relaxed for it:
`Sandbox.workspace_write` and `ApprovalMode.deny_all`, with no argument that
turns either off.

It is worth being exact about which links of the chain that actually covers,
because the earlier version of this paragraph claimed all of them and the test
file's own skip records said otherwise.

**Driven on every machine, including this one:** the runtime starts, the
JSON-RPC session opens against the pinned `app-server`, a turn begins, the
request reaches the provider with the settings we chose, the model's tool call
comes back, the turn ends, usage is collected off `ThreadTokenUsage`, the call
is settled into the receipt with its missing-information reasons, and the
process exits without leaking a session.

**Driven, but on exactly one machine:** the sandboxed command executing, the
file it writes appearing on disk, and the tool result carrying that command's
real output back to the model. Those are the two assertions that used to skip
everywhere. They now run on GitHub's `ubuntu-22.04` runner under
`CODEX_SANDBOX_MUST_RUN=1`, where a skip is a failure, and on 2026-09-08 they
passed there for the first time — the whole file reading `17 passed` where every
other host in this project reads `15 passed, 2 skipped`. Nowhere else. On every
other host the two still skip, and that skip is still the correct answer for
those hosts.

That sentence is one commit old, and the commit before it said the opposite, so
it is worth recording why rather than only what. The first run of those
assertions on that machine was **red**, and it was right to be. What it found is
below.

Finding the machine is what `scripts/diagnose_codex_sandbox_host.py` was for.
The rule it replaced — *until one machine reports `ready`, no document here may
call the chain end-to-end verified* — has been met, and met by measurement
rather than by argument. What may be said is still narrower than "verified": the
chain has been driven end to end **once, on one runner image, against a scripted
provider**, and the run place needed a repair to get there. What may not be said
is that it works against a paid deployment, which is §3's other open leg and is
not a sandbox question at all.

**What the red run found, and why it was worth the red.** Both assertions failed
the same way, and not on the sandbox:

    bwrap: execvp codex-linux-sandbox: No such file or directory

The sandbox started. It then could not find the helper it was told to exec.
There is no `codex-linux-sandbox` file anywhere in the wheel: at start-up Codex
creates `$CODEX_HOME/tmp/arg0/codex-arg0XXXXXX/` and fills it with symlinks back
to the single `codex` binary, named `codex-linux-sandbox`,
`codex-execve-wrapper`, `apply_patch` and `applypatch`, then puts that directory
on its children's `PATH`. The binary dispatches on `argv[0]`. And it refuses to
build those symlinks when `CODEX_HOME` is inside the temporary directory — which
it says on stderr, and then carries on regardless:

    WARNING: proceeding, even though we could not create PATH aliases:
    Refusing to create helper binaries under temporary dir "/tmp"

Every task directory in this repository was made with `tempfile.mkdtemp()`, so
`CODEX_HOME` was always under `/tmp`, so the helper was never built, on any
host. The execution leg could not have worked anywhere — including in the paid
runs section 12 pins, where it would have failed at the agent's first command,
after the money was spent.

Two repairs, both in this branch:

* `core.codex_runtime_config.resolve_run_root_base` picks a run root outside the
  temporary directory — `$GDPVAL_CODEX_RUN_ROOT` used verbatim, else
  `$XDG_CACHE_HOME/gdpval-codex-runs`, else `~/.cache/gdpval-codex-runs` — and
  raises rather than falling back when all three are missing or land inside the
  temporary directory, the explicit override included. `CodexWorkspace.create`
  builds the task directory there instead. `tests/test_codex_run_root.py` pins
  the rule, and needs neither a sandbox nor the binary to do it.
* The end-to-end file no longer reads that message as "this machine has no
  sandbox". It had been caught by the `^bwrap: ` prefix that means exactly
  that — which is why a defect present on every host produced a green skip on
  every host, and why turning skips into failures on one host was worth doing.
  A missing helper now fails, naming the helper, before the prefix is consulted.

The shortcut was refused, and the refusal is written into the code: pointing the
*child's* `TMPDIR` at the task directory would satisfy Codex's check without
moving anything, and would also move the sandbox's writable carve-out — Codex's
permission model names `tmpdir` and `slash_tmp` separately — in a way nothing
here has measured.

What may be said today is that the defect is understood, fixed, and the fix
watched: with the task directory moved, `prove-execution` is green — the two
assertions that need a command to execute pass, and the whole end-to-end file
reads `17 passed` on that host. What still may not be said is that the chain
runs against a paid deployment, which is §3's other open leg and is not a
sandbox question at all.

The host survey is worth writing down in full, because the first attempt to
write it down got it wrong twice. All of it is in
`batch-runner/docs/codex_sandbox_hosts.json`, measured by the diagnostic and
re-measured by `.github/workflows/codex-sandbox-host-survey.yml`:

| host | kernel | `apparmor_restrict_unprivileged_userns` | verdict |
|---|---|---|---|
| Xenology NAS (the dev box) | 3.10.102 | absent — no `/proc/sys/user` at all | `kernel_lacks_user_namespaces` |
| GitHub `ubuntu-24.04` = `ubuntu-latest` | 6.17.0-1022-azure | `1` | `user_namespaces_restricted_by_security_policy` |
| plain `ubuntu:24.04` container on that runner | 6.17.0-1022-azure | `1` | `user_namespaces_restricted_by_security_policy` |
| GitHub `ubuntu-22.04` | 6.8.0-1064-azure | `0` | **`ready`** |

The first row was known. The second is what was *assumed* without checking:
`ubuntu-latest` does install the pinned runtime and does start the sandbox, and
then bwrap dies anyway with
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` — the namespace
is granted and the capability inside it is not, so the network Codex unshares
cannot be brought up. That assumption cost a red CI run, which is how it was
found. The third row shares the second's cause and not its symptom: inside the
container the namespace creation is refused outright rather than stripped
afterwards, because the container's own seccomp profile stops it first.

The fourth row is the one that matters, and the reason it is evidence rather
than luck is that rows two and four are the same hosted-runner infrastructure
with the same LSM stack, differing in one sysctl — so the failure is
attributable to the policy and to very little else.

Two things about that row have to be said plainly rather than celebrated.
`ubuntu-22.04` is not better configured; it is *older*, and its default posture
simply predates `kernel.apparmor_restrict_unprivileged_userns`. And GitHub is
retiring the 22.04 image, so this result has an expiry date. The execution-host
card is therefore **deferred by this finding, not closed by it**.

Four ways to make the test green were available and all four were refused:
turning the sandbox off; granting the sandboxed command network access so
nothing has to be unshared; running the probe in a privileged container; and
clearing the sysctl on the 24.04 runner. The first two produce a passing test
about a configuration no run would use. The third measures a container nobody
would deploy. The fourth removes the restriction from every process on the
machine, which is not a fix but the absence of one. A fifth was considered and
also refused: Codex's `use_legacy_landlock` backend, which both 24.04 and 22.04
could probably run — it is the *legacy* sandbox, so a green test there would be
measuring a run place no real run configures. It is recorded in the
diagnostic's output as an observation and never as readiness.

## 4. A distinction that is easy to get wrong

Azure offers models whose names contain "codex", and Azure's own agent service
can use them. That is **Azure's agent feature driving that model**. It is not
Codex's own agent, which is a different piece of software with its own loop, its
own tool choices, and its own retry behaviour.

Measuring Azure's agent and calling it Codex would be measuring the wrong thing.
The comparison's fifth column is about Codex's own loop, so the substitution
would quietly answer a different question. This is the same class of error as
letting a container fall back to the host: the label stays the same and the
thing measured changes.

## 5. Goals

1. Record the search so it is not repeated.
2. State precisely which single fact would unblock the column.
3. Keep the column empty and marked unconfirmed until that fact is established.

## 6. What must not happen

- **Do not fill the column with Azure's agent service** using a model whose name
  contains "codex". That is a different product.
- **Do not fill the column by pointing Codex at a different model** than the
  other columns use. The comparison would no longer be about run places.
- **Do not write a fixed interface key into a configuration file** to make a
  connection work. This repository refuses those credentials on purpose, and the
  free check now reports them during the pre-run check.
- **Do not describe the column as "supported" on the strength of the
  base-address setting alone.** That setting changes an address; it does not
  establish that the required sign-in works.

## 7. What is left, now that the settings are code

The original question was:

> Can Codex's own agent loop be pointed at a named Azure AI Foundry deployment,
> authenticating with a token from a directory sign-in rather than a fixed key?

Both halves of it are now answered in documentation, and the settings are no
longer a sketch in this file — they are `core/codex_runtime_config.py`, checked
by tests. What is left is the one thing a document cannot settle:

> Does *this* account's `/openai/v1/` endpoint, in *this* region, accept what
> the pinned Codex build sends, with an Entra token from a directory sign-in?

That is answered by one request against the real deployment, not by more
reading. Until such a request has succeeded, the run place stays at
`structure_check_only`: the code exists, the mock chain passes, and
`step2_run_inference` still refuses to start a batch in this mode.

The settings the run uses, for a reader who wants them in one place. This is
what `provider_config_overrides()` builds, shown as the TOML it parses to:

```toml
# Passed as `--config key=value` arguments, not written to a file. A
# repository-local config is ignored by Codex for provider and credential
# settings, and the operator's own config is not ours to edit.
[model_providers.gdpval-foundry]
name = "gdpval-foundry"
base_url = "https://<account>.openai.azure.com/openai/v1"
wire_api = "responses"

# A directory sign-in, which is the only kind of credential this repository
# permits. The command prints an Entra token to stdout; no token passes
# through the batch runner's own process.
[model_providers.gdpval-foundry.auth]
command = "<python>"
args = ["-m", "core.codex_azure_token", "--scope", "<scope>"]
timeout_ms = <...>
refresh_interval_ms = <shorter than the token's lifetime>

# Only for the dated legacy route. On the `/openai/v1/` endpoint above, an
# `api-version` here is refused rather than ignored.
# [model_providers.gdpval-foundry.query_params]
# api-version = "<date>"
```

Section 3a's third possibility is still the trap to watch: the connection could
partly work — answers come back — while some part of the format is quietly
handled differently, producing a column that looks filled in and is not
comparable. The defence against that is not optimism about the first successful
request; it is that the run place is graded on evidence and stays ungraded
until the evidence exists.

## 8. Files that changed

| File | Role |
|---|---|
| `batch-runner/core/codex_runtime_config.py` | Version pins, environment isolation, provider settings, and the loopback stand-in. |
| `batch-runner/core/codex_runner.py` | Starts the runtime per task, hands over the prompt and reference files, collects deliverables, enforces the time limit, and cleans up. |
| `batch-runner/core/codex_azure_token.py` | Prints an Entra token to stdout for `auth.command`. |
| `batch-runner/core/codex_cost.py` | Adapts thread-cumulative usage onto the repository's existing receipt contract. |
| `batch-runner/core/executor.py` | Gained the `codex_foundry` mode and its dispatch entry. |
| `batch-runner/core/experiment_config.py` | Accepts the mode in an experiment file. |
| `batch-runner/step2_run_inference.py` | Refuses to start a batch in this mode until the connection is confirmed. |
| `batch-runner/core/execution_environment_readiness.py` | The run place moved from "not implemented here" to `structure_check_only`, with its blockers and its evidence named. |
| `batch-runner/requirements.txt` | The two exact pins. |
| `batch-runner/tests/test_audio_format_failure_diagnostic.py` | One test gained the "has run" gate its sibling in 333 already had. Not this task's file — see below. |
| `batch-runner/experiments/execution_envelope/advance_check_plan.yaml` | **Unchanged.** A fifth column waits on section 7. |

### 8b. The one file here that belongs to the other task, and why it had to move

`compute_grader_source_hash` hashes **every** `core/**/*.py` by content, plus
`requirements.txt`. So there is no way to add a run place under `core/` — this
one or any other — without moving the grader fingerprint. That is by design and
is not worth working around: putting the Codex modules outside `core/` to dodge
it, or carving them out of the hash, would both weaken a guarantee that exists to
protect paid grading.

Moving it turned one test red:
`tests/test_audio_format_failure_diagnostic.py::test_the_registered_document_is_one_this_diagnostic_will_accept`,
which asserts that the fingerprint pinned in `tasks/rebuilding_grading_task/335-why-the-format-failed.md`
equals the one this checkout computes.

The document is not the problem and was not touched. Its §11 records
`상태: 실행 완료`, run [`34156359141`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/34156359141)
at commit `1e06e452`, and the repository's own rule — written down in
`tests/test_audio_accuracy_probe_knows_its_own_answers.py` — is that *"once it
has run the pin is history and must not be edited, which is what the status line
gates."* 333's equivalent test carries that gate. 335's did not. That omission is
the actual defect, and any change under `core/` on `main` would have exposed it;
this one happened to be first.

So the gate was added, keyed on 335's own §11 wording rather than on the header
— 335 deliberately leaves its header reading "사전등록. 아직 안 샀다" so that
nothing above §11 is edited after the fact. Nothing else in that file changed, no
pinned value was rewritten, and the assertion still runs in full on any checkout
where 335 has not yet been bought.

**Consequence to carry forward, from `scripts/check_grader_hash_freeze.py`:** no
paid grade run was in flight when this landed, so the move is safe — but the next
paid run must be preceded by a fresh smoke at the new fingerprint.

## 9. Safety, cost, and no-silent-substitution conditions

- Codex's own agent decides how many model calls to make, so the cost of a run
  is not predictable from the task. Every call it makes opens a receipt before
  the request leaves and settles it afterwards; a failed or interrupted turn
  leaves its receipt open rather than dropping it, because the request may still
  have been billed.
- Usage the runtime does not report is recorded as missing, not as zero. A turn
  that returns no usage settles with no token counts and a stated reason.
- Codex runs commands as part of its normal operation. The containment is
  `Sandbox.workspace_write` plus `ApprovalMode.deny_all`, set in
  `core/codex_runner.py` with no argument that relaxes either — including for
  the mock check, which skips on a host that cannot sandbox rather than running
  the agent unsandboxed.
- Each task gets its own directory, its own `CODEX_HOME`, and its own `HOME` and
  XDG paths. The operator's Codex sign-in, plugins and history are not
  inherited, and the credential variable names arrive blank rather than absent,
  because the runtime merges its environment over the parent's.
- **No fallback.** If the mode cannot start, the task fails with the reason. It
  is never quietly handed to another runner, which would relabel a different run
  place with this one's name.
- The free check must keep reporting this run place as not runnable until a
  request has actually reached the deployment. Code existing is not the same as
  a connection existing.

## 10. How this is checked

- `batch-runner/tests/test_codex_runtime_end_to_end.py` drives the real pinned
  binary against a stand-in Responses server: the tool round trip, the reference
  file, the deliverable, per-task file isolation, the time limit, a refused
  provider, a closed port, missing usage, a wrong deployment, and the absence of
  a fallback. Mocking the SDK objects would prove none of this, which is why it
  is not done here.
- `batch-runner/tests/test_three_more_run_places.py` pins the grade: the run
  place has code, and having code is still not being able to run.
- `batch-runner/scripts/diagnose_codex_sandbox_host.py` answers, for one
  machine, whether Codex can execute a command there — and when it cannot, which
  of six named walls it hit. Its own tests
  (`batch-runner/tests/test_codex_sandbox_host_diagnosis.py`) hold it to the
  distinctions that matter, chief among them that only a command which actually
  ran counts as `ready`.
- `.github/workflows/codex-sandbox-host-survey.yml` re-measures the hosted
  runners against `batch-runner/docs/codex_sandbox_hosts.json` and fails on any
  disagreement in either direction, so a runner image that quietly gains or
  loses the ability to sandbox shows up as a change rather than as nothing. Its
  `prove-execution` job runs the end-to-end file on `ubuntu-22.04` with
  `CODEX_SANDBOX_MUST_RUN=1`, which is what stops the execution leg from
  reverting to a silent skip on the one host that can exercise it.
- Still to be written, when section 7 is answered: a test that the deployment
  Codex addresses is the same one the other columns address, which is the
  condition that motivated this whole document.

## 11. Done when

- [x] The question in section 7 is answered from official documentation.
- [x] A run place exists, with the settings in code rather than in prose.
- [x] The chain from runtime start to cost collection is checked without a paid
      deployment.
- [x] Codex executes a command inside its sandbox. Observed on 2026-09-08 on
      GitHub's `ubuntu-22.04` runner — the one host measured `ready` — with
      `CODEX_SANDBOX_MUST_RUN=1` turning a skip into a failure, so the whole
      end-to-end file reads `17 passed` there where every other host in this
      project reads `15 passed, 2 skipped`. Getting there needed a fix: running
      on a host that can sandbox is what showed that the run place itself was
      building `CODEX_HOME` somewhere Codex will not create its sandbox helper
      (§3b). Ticked for what it says and no more — one host, one runner image
      that is being retired, and a scripted provider rather than a paid one.
- [ ] One request reaches the real deployment and is accepted.
- [ ] A test proves the deployment it addresses is the same one the other
      columns address.
- [ ] The fixed sequence of 5, then 30, then 220 tasks — not started before the
      line above is ticked.

## 12. Known blockers and the next decision

- **No longer blocked on an external fact.** As of 2026-09-08 the documentation
  covers the Azure provider and `query_params`, and the settings are built. The
  old "no Azure settings / cannot pass an api-version" conclusion is superseded
  and must not be reused as a current blocker.
- **Blocked on a live request.** Version, authentication and per-region
  compatibility against our own deployment are separate facts from the
  documentation, and only a request settles them.
- **The exec leg is closed, on one host, and it took a repair to close it.** The
  host limit was real and was closed by finding a host rather than by removing
  isolation: no sandbox was disabled, no network was opened, no container was
  privileged, and no host's security policy was changed. The first run on that
  host was red, and what it found was ours: `CODEX_HOME` under `/tmp`, so Codex
  never builds `codex-linux-sandbox`, so the agent's first command dies whatever
  the host allows (§3b). With that fixed, `prove-execution` is green — the two
  assertions that need a command to run pass, and so does the whole file. The
  development box (Linux 3.10, no user namespaces) and `ubuntu-latest`
  (namespace granted, capability stripped) still cannot run it and still skip.
  The execution-host card stays open, because one retiring runner image is a
  reprieve rather than an answer.
- The next decision is whoever can run one paid request against the pinned
  deployment. Until it succeeds, the column stays empty and is reported as
  unconfirmed. It is not filled with a substitute.
