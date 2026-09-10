# Codex's own agent: what is officially supported, and what is still unknown

- Written: 2026-08-25
- Updated: 2026-08-26 — the documentation was searched again and half of the
  open question is now answered. See section 3a.
- Updated: 2026-09-08 — the documentation now covers the Azure provider, and the
  run place was built against the pinned runtime and checked without a paid
  deployment. Running it on a host that can sandbox then found a defect in the
  run place itself. See section 3b. The instrument that will ask the deployment
  is built and has not been fired; see section 3c.
- Updated: 2026-09-09 — the instrument was repaired and fired. A free read, a
  free role inventory and the one authorised paid turn have closed four of the
  five candidate causes of the 401 and left the refusal itself unexplained. See
  section 3c.
- Updated: 2026-09-10 — the sweep was fired and found nothing: all nine paid
  arms served. The refusal was then located, and it was ours — the auth command
  could not produce a token where Codex runs it, for three separate reasons.
  Fixed and tested locally; no turn has yet been sent through the fixed path.
  See the last three bullets of section 12.
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

## 3c. The other leg: a way to ask the deployment, and to hear which "no"

Section 7's question is answered by a request. Sending one and reading
"the turn failed" would have answered almost nothing, so before sending anything
the failure had to be made legible.

`core/execution_environment_readiness.py` names three separate unmeasured
things, and they are fixed in three different places:

  a. the token `core/codex_azure_token.py` mints has only ever been *minted*,
     never *accepted* by anything;
  b. which API contract this deployment serves Codex on is unmeasured;
  c. whether the pinned Codex build's request shape survives this resource's
     model version and content filters is a third question again.

A single `RuntimeError` distinguishes none of them — and that is not incidental,
it is the SDK's own doing. `openai_codex/_run.py::_raise_for_failed_turn` raises
`RuntimeError(turn.error.message)` and drops `turn.error.codex_error_info`,
which is where the error's name lives and, for four of its variants, an
`http_status_code`. `scripts/diagnose_codex_foundry_connection.py` consumes
`TurnHandle.stream()` itself rather than calling `run()`, so it recovers both
**from the first request**: a refused sign-in (401/403), a rejected payload
(400/422), an absent deployment (404) and a content filter each come back under
their own name, with no second paid call to tell them apart.

Seventeen verdicts, a closed vocabulary, and no guessing from message text. The
status code beats the error name where both exist, and an error variant this
pin has never seen reports **its own name** rather than being folded into
`other` — a future SDK adding a case must not silently become "something went
wrong".

Four things it deliberately does not do, each of which would have been easier:

* **It does not clear a blocker.** It records evidence and a person decides. A
  diagnostic that flipped the readiness gate would be a manual override wearing
  a diagnostic's name, which is the thing §9 exists to prevent.
* **It does not establish the run place.** The prompt forbids commands, files
  and tools on purpose, and `tool_execution_observed` is `false` in every record
  it can produce, `connected` ones included. The record carries four sentences
  saying which legs a text turn leaves standing — the tool leg, the deliverable
  leg, the batch leg and the cost leg — rather than leaving that to be inferred
  by whoever reads a green verdict. §3b's exec leg and this one are different
  questions and the artifact says so in its own words.
* **It does not fall back.** No second model, no second provider, no dated
  legacy route. A run that cannot reach the deployment it was asked about
  reports that, rather than reporting a different deployment's health — §6's
  second and fourth prohibitions, enforced instead of promised.
* **It does not name the resource.** This one needed a different mechanism than
  the obvious one. The account and project names live in repository
  *variables*, and a variable is reprinted verbatim in a step's `env` header —
  so pinning identity the ordinary way, with
  `AZURE_AI_REQUIRE_EXPECTED_IDENTITIES` and `AZURE_AI_EXPECTED_DIRECT_ACCOUNT`,
  would publish the name of the resource in the log of the job built not to name
  it. The pin is a **sha256 of the endpoint host** instead: printable, still
  sensitive to the endpoint secret being repointed, and worth nothing to anyone
  who reads it. The names that must be blanked out of runtime messages are mined
  from the endpoint secret itself with `classify_endpoint`, the way
  `scripts/azure_rbac_diagnostic.py` already does, and the workflow re-greps its
  own artifact afterwards rather than trusting the redactor to have worked.

`send_request` defaults to `false`, and with it nothing is sent: the job prints
the plan — deployment, route profile, host fingerprint, prompt hash, call count,
retry count — and stops. Plan and result share one schema, so what was fixed
beforehand and what happened can be compared field by field afterwards. Every
exit writes its record, including the one where nothing could be configured,
because an empty artifact and a run that never happened used to look identical.

`core/codex_runner.py` grew `open_runtime()` and `start_thread()` out of its
private `_build_codex` so that the diagnostic and a real task construct the
runtime through **one** path — a diagnostic that describes a configuration no
run uses is worse than none. The sandbox preset and approval mode are read off
the runner rather than taken as arguments, so nothing can ask this path for
weaker isolation.

None of this has been sent yet. What exists is the instrument; §11's fifth box
stays unticked until a request has actually been answered.

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
reading. The instrument that asks it now exists — §3c — and has not been fired.
Until such a request has succeeded, the run place stays at
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
| `batch-runner/core/codex_runner.py` | Starts the runtime per task, hands over the prompt and reference files, collects deliverables, enforces the time limit, and cleans up. `open_runtime()` and `start_thread()` are the one construction path the diagnostic shares. |
| `batch-runner/scripts/diagnose_codex_foundry_connection.py` | Asks the deployment one question and names which "no" came back, by reading the turn stream the SDK's collector discards (§3c). |
| `.github/workflows/codex-foundry-connection-diagnostic.yml` | Runs it from `main` under the existing OIDC sign-in. `send_request` defaults off; the plan step always runs. |
| `batch-runner/core/codex_azure_token.py` | Prints an Entra token to stdout for `auth.command`. Now runnable by path from any directory, and takes `--azure-config-dir` so it can find a sign-in the isolation has hidden from it. |
| `batch-runner/tests/test_the_auth_command_runs_where_codex_runs_it.py` | Holds the three faults of §12 apart: the working directory, the sign-in, and the silence — plus the assertion that the fix did not buy the connection with isolation. |
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
- `batch-runner/scripts/diagnose_codex_foundry_connection.py` asks the pinned
  deployment one question and classifies the answer into a closed vocabulary of
  seventeen verdicts, so that a refusal names *which* refusal it was.
  `batch-runner/tests/test_codex_foundry_connection_probe.py` holds it to that:
  the status code beats the error name, an unknown future error variant reports
  its own name, nothing is guessed from message text, and the redactor blanks
  the account and project names it derives from the endpoint secret. Half of the
  file holds the workflow instead of the script — `send_request` gated on the
  input, no `AZURE_AI_EXPECTED_*` name anywhere in it, the plan step before the
  send step, pinned action SHAs, and the embedded leak check pulled back out of
  its heredoc and run against five crafted leaks and a clean record, so the
  check that guards the artifact is itself checked.
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
- **Blocked on a live request — but no longer on being able to read its
  answer.** Version, authentication and per-region compatibility against our own
  deployment are separate facts from the documentation, and only a request
  settles them. As of 2026-09-08 the instrument that asks exists (§3c) and
  separates a refused sign-in, a rejected request shape and an absent deployment
  from one another out of a single turn.

  **It has since been fired, and it came back 401.** Run `34319880025`,
  `send_request: true`, `usage: null`. A workflow that concludes `success` is
  reporting that the job ran, not that the provider answered; the record inside
  it says `unauthorized`. The turn cost is unestablished rather than zero —
  there was no usage to price, and an unpriced turn is not a free one.

  The 401 is an authentication result, not an authorization one. The read-only
  RBAC diagnostic (run `34325382584`) shows the CI identity holding
  `Cognitive Services OpenAI User` at the **account** scope, which is the scope
  governing the `/openai/v1/` route Codex posts to. So the missing Foundry
  *project* role assignments belong to a different route and are not the
  demonstrated cause here. What the 401 does *not* establish, and must not be
  written up as if it did: which of deployment name, region, API contract or
  credential is wrong. One status code does not locate the fault.

  Firing it is a `workflow_dispatch` from `main` with `send_request: true`. It
  costs one turn and — since the retry pins landed — **one HTTP request**, or
  two if the answer is another 401. Before the pins, "no retries" was a line in
  the plan dictionary and nothing else: the provider table set neither counter,
  so the runtime used its own defaults and one turn against a 500 sent
  **thirty** requests. Measured, not estimated:
  `batch-runner/tests/test_codex_retry_pins_are_enforced.py` drives the pinned
  binary against a local server that refuses four different ways and counts
  what arrives.

  This paragraph used to add "of roughly 135 characters with no tools", and
  that was wrong in the same way the pre-pin retry claim was wrong — a property
  of the plan asserted about the runtime. One turn puts **about 45.9 KB** on
  the wire: roughly 21 KB of Codex system `instructions`, 18 KB of **ten
  `tools` definitions** with `tool_choice: auto`, and 5 KB of `input`. No
  prompt wording and no key in `core/codex_runtime_config.py` removes the
  tools, so nothing sent through this path can promise that none were offered
  — only that none *ran*, which the record separately shows. Measured in
  `batch-runner/tests/test_what_one_codex_turn_actually_sends.py`, which also
  closes the older harness's blind spot: it recorded `do_POST` only, so any
  other verb would have been answered `501` and left no trace in the count that
  said one request was sent. Checking all seven verbs turns "no hidden
  requests" into a measurement — the answer is two POSTs to `/v1/responses`,
  no GET, nothing else.

  | server answers | counters unset | pinned to 0 |
  | --- | --- | --- |
  | HTTP 500 | 30 requests | 1 request |
  | mid-stream disconnect | 6 requests | 1 request |
  | HTTP 429 | 1 request | 1 request |
  | HTTP 401 | 12 requests | **2 requests** |

  The 401 row is the residue pinning does not remove: the runtime re-runs the
  provider's auth command once after an authentication failure and retries with
  the fresh token, which no documented key switches off. Two requests, two
  tokens minted. It is recorded as a bound rather than rounded down to one.
- **Four candidate explanations for the 401 were checked offline and all four
  match a path that demonstrably works — so the fault is not located.** This
  is a negative result and is recorded as one:

  | leg | Codex | grading, which works | verdict |
  | --- | --- | --- | --- |
  | URL | `{account}.services.ai.azure.com/openai/v1/responses` | same host, same `/openai/v1/` route | same |
  | scope | `DIRECT_TOKEN_SCOPE` | `DIRECT_TOKEN_SCOPE` | same |
  | header | `authorization: Bearer …`, measured on a local socket | `Authorization: Bearer` via the openai SDK | same |
  | identity | `secrets.FOUNDRY_PROJECT_ENDPOINT`, same OIDC login, `direct-v1` | identical | same |

  Grading has produced tens of thousands of rows over that path. A comment in
  `core/azure_ai_clients.py` claiming the direct route rewrites the host to
  `openai.azure.com` is wrong for this endpoint shape — the host is unchanged —
  and it is named here because reading it is how one would wrongly conclude the
  URLs differ.

  **What is left unmeasured, and is therefore where to look:** (1) Codex mints
  its token in a **child process** (`auth.command`) while the grading and
  inference paths mint theirs **in process** via `get_bearer_token_provider` —
  two credential chains in the same job can resolve differently; (2) the turn
  carries a 45 KB body, `accept: text/event-stream`, and seven `x-codex-*` /
  `originator` headers the Python paths never send; (3) whether the requested
  deployment name exists on the resource at all is **unverified** — the pinned
  check compares a host fingerprint, not a deployment.

  The 401's own text is a gateway subscription-key message
  (*"invalid subscription key or wrong API endpoint"*), not an AAD audience
  error. That is a hint about which layer refused, and it is not a conclusion.
- **The free half of the question now runs on every dispatch: `--read-only-probe`.**
  It mints the token the child-process way — closing gap (1) above — and issues
  `GET {base_url}/models`. No prompt, no completion. Three outcomes, and each
  one moves the question:

  | it answers | what that settles |
  | --- | --- |
  | `200`, deployment listed | the token is accepted by this resource; the refusal is narrower than the identity |
  | `200`, deployment **not** listed | the name asked for is not on the resource — the cheapest explanation there is |
  | `401` | the refusal reproduces **having spent nothing**, and the question is the token itself |

  What a `200` still does **not** buy is carried inside the record as
  `not_established`, because it is precisely the result that gets over-read: a
  listing is not a completion and a resource may list to an identity it will
  not let infer; `deployment_listed` says a name appears, not that this
  identity may call it; and no inference was requested, so the call is
  **unpriced, which is not the same as proven free**.

  Record schema `codex_foundry_readonly_probe/1`, `inference_requested: false`.
  Model names are counted, never written down. A failing auth command has its
  **stdout withheld** while stderr is quoted, because stdout is where a token
  would be.
- **It was fired, and it measured nothing — the fault was ours.** Run
  `34340775246` (`send_request: false`, no turn sent, job green). The record
  says `token.minted: false`, `listing: null`, and the error is
  `'method' object is not iterable`: `auth_command` is a *method* on
  `CodexProviderSettings` and the probe read it without calling it, so
  `subprocess.run` was handed a bound method. **None of the three outcomes in
  the table above is answered.** The 401 remains unlocated.

  Two things the run *did* settle, because they are read off the record rather
  than off the network:

  * the host it was pointed at is the host that got the 401 —
    `endpoint_host_fingerprint: sha256:69057d59166a82e3`, byte-identical to run
    `34319880025`'s. The probe was aimed correctly;
  * the retry pins are live in the real settings object, not only in tests:
    `retries: {request_max_retries: 0, stream_max_retries: 0}` appears in the
    settings the job actually built.

  The deployment asked for was `gpt-5.4`, the same name run `34319880025` used.

  Three repairs, so the shape of this mistake cannot repeat quietly:

  1. the probe calls `settings.auth_command()` and **checks the argv's shape
     itself**, raising a message that says whose defect it is rather than
     letting the standard library raise one that names neither this file nor
     the attribute;
  2. the test helper that substituted the command was defining it as a
     `@property` — modelling a shape production does not have. Every minting
     test read a value and passed while production got a method. It is a method
     now, and one test uses the **unmodified** settings object with a stub auth
     module so the argv production builds is exercised with nothing overridden.
     Reintroducing the original defect turns 5 of these tests red; before the
     helper was fixed it turned 0 red;
  3. the workflow step now **fails** when the token could not be minted. A
     refusal is a finding and the step keeps going for it; never reaching the
     host is not a finding, and a green step there is exactly how this run
     looked like it had measured something. Failing there also blocks the paid
     turn — a job that cannot mint a token has no business buying one.
- **Fired again, and this time it measured.** Three runs on 2026-09-09, in this
  order, all from `main` at `cb043af`:

  | run | what it cost | what came back |
  |---|---|---|
  | `34346945494` | nothing — no inference requested | token **minted** by the child-process `auth.command`; `GET /models` → **200**; **428** models listed; `gpt-5.4` **is in the listing** |
  | `34347345143` | nothing — ARM control-plane reads only | the CI identity holds exactly **one** role assignment: `Cognitive Services OpenAI User` (`5e0bd9bd-…`) at **foundry-account** scope. `principal_can_assign_roles: false`. `read_failures: []` |
  | `34347516170` | the one authorised paid turn | **401**, `usage: null`, `verdict: unclassified_failure` |

  With the earlier local measurements, every leg that can be checked without
  the host's cooperation now has a number against it:

  | leg | how it was measured | result |
  |---|---|---|
  | address | `endpoint_host_fingerprint` compared across runs | `sha256:69057d59166a82e3` — byte-identical to the run that first got the 401 |
  | identity | live OIDC → the provider's `auth.command` as a child process | token minted |
  | deployment exists | `GET /models` on that host | present, among 428 |
  | wire format | pinned `0.147.0` binary vs a local mock server, fake token | `authorization: Bearer <token>` on `POST …/responses` — not `api-key`, not absent |
  | retries | same harness, and the settings object of a real job | `0`/`0`, live |

  So the refusal is **not** a wrong host, **not** a missing deployment, **not**
  a token that failed to mint, and **not** a credential put in the wrong header.
  Those four were the open candidates and they are closed.

  **The one new fact is the text of the refusal.** The runtime reported
  `unexpected status 401 Unauthorized: Access denied due to invalid
  subscription key or wrong API endpoint. Make sure to provide a valid key for
  an active subscription and use a correct regional API endpoint for your
  resource.` That is the Cognitive Services *subscription-key* string, returned
  by the same host that had accepted the same identity's bearer token for a
  read minutes earlier in the same job. It is written down here because it is
  what came back, **not** because it proves the resource wants a key: this
  message is emitted by the gateway on more than one kind of refusal, and
  nothing measured here distinguishes them.

  What is still **not** established, and must not be written as though it were:

  * **which action is being refused.** A listing and a completion are different
    data actions. `Cognitive Services OpenAI User` is what permits the 200; it
    is unmeasured whether it reaches `POST /openai/v1/responses`;
  * **that the RBAC verdict explains this.** `azure_rbac_diagnostic` refuses to
    run against anything but a Foundry **project** endpoint, and Codex uses the
    **account** `direct-v1` route. Its verdict —
    `role_missing_and_an_owner_must_grant_it`, wanting `Foundry Agent Consumer`
    (`eed3b665-…`) or `Foundry User` (`53ca6127-…`) — is the answer to the Code
    Interpreter arm's 403, on a different surface. It is quoted below as the
    role inventory it is, not as this 401's cause;
  * **the cost.** `usage: null`, and the record's own note says the turn "may
    still have been billed". Unpriced. **Not zero.**

  One measurable improvement did land on the live host: the same refusal that
  produced **6** error notifications in run `34319880025` produced **1** here,
  with the retry pins in force. The two HTTP requests an authentication failure
  still costs are unchanged and documented — the runtime re-runs the auth
  command once and retries with the fresh token, and no pin binds that. Error
  notifications are not requests and are not counted as such.

- **What an owner would have to change, reported and not applied.** No role was
  granted, no policy relaxed, no credential or VM created. For whoever decides:

  * **target**: the CI service principal (`AZURE_CLIENT_ID`), at the Foundry
    **account** scope that already carries its one assignment;
  * **change**: nothing yet — the account-route refusal has not been shown to
    be a role problem, and granting a role to see if a 401 goes away is a
    guess with a blast radius. The next step that would justify a grant is a
    free one: a deliberately malformed `POST` to the same route with the same
    bearer. **The sentence that stood here was wrong, and the bullet below
    corrects it**: it said a `400` would prove the bearer is accepted. It
    would not, on its own. Neither generates tokens. **It was not run here** —
    the authorisation was for one turn and one turn was used;
  * **risk if a grant is made anyway**: `Foundry User` and `Foundry Agent
    Consumer` are project-scoped roles for a route this run did not use, so
    granting them would widen access without a measurement saying it helps.

- **The free discriminator, built with two arms because one is unreadable.**
  Written and tested on `diag/does-the-bearer-get-past-the-gate`;
  `--auth-discriminator` in
  `batch-runner/scripts/diagnose_codex_foundry_connection.py`, an ungated step
  in the diagnostic workflow, 27 tests in
  `batch-runner/tests/test_codex_auth_discriminator.py`.

  The bullet above promised a one-armed version and the promise did not
  survive being written down. A `400` from the minted bearer means "it got
  past authorization" **only if this host checks authorization before it
  validates the body**, and nothing measured here has ever established that
  ordering. A host that reads the body first answers `400` to everybody,
  including to a string that is obviously not a token — and that `400` would
  have been read as good news.

  So the same unservable body goes twice: once with the bearer the Codex
  runtime mints, once with a fixed sentence that is plainly not a token. The
  control arm is not credential guessing and cannot become it — the string is
  a constant, never varied, never derived from anything real. Its only job is
  to make the host demonstrate which check it runs first.

  | control arm | minted arm | verdict |
  |---|---|---|
  | `401`/`403` | `400`/`422` | `bearer_clears_the_auth_gate` — the fault is past authorization |
  | `401`/`403` | `401`/`403` | `bearer_refused_at_the_auth_gate` — the fault is the token or this identity's rights on this operation |
  | anything else | anything | `check_order_not_established` — **this host cannot be read this way, and the question stays open** |

  The third row is the reason this is three verdicts and not two, and it is
  what the tests spend the most effort on: reordering the checks so the minted
  arm is read first — the version somebody wanting good news would write —
  turns three tests red, including the end-to-end one that asserts a run which
  could not discriminate does not exit zero. A `200` to a body naming no model
  is also refused a clean verdict, and withdraws the free claim with it: the
  argument that nothing can be generated is that no deployment can be
  selected, and a `200` is the host disagreeing.

  What it still will not settle, in the record itself: this is `urllib` on the
  route, not the Codex runtime (the header name and format are the ones the
  pinned binary was measured sending, and nothing else about the runtime's
  request is reproduced); a clear verdict narrows where to look and **is not a
  reason to grant a role**; and "no usage record came back from a refusal" is
  an argument for the call being free, not a measurement of it.

  **It has now been run, and it answered.** Run `34361684546` on `67ac579d`,
  `send_request: false`, no prompt, no completion. Both arms posted the same
  unservable body — `body_sha256:
  a679e5e9896b95bc386aed1754caeeef68665be5a51aae2327f6062db077d5b6` — to the
  same route, minutes apart:

  | arm | status | message |
  | --- | --- | --- |
  | minted bearer | **`400`** | *Missed model deployment* |
  | control, `this-string-is-not-a-token-and-never-was` | **`401`** | *Access denied due to invalid subscription key or wrong API endpoint…* |

  Verdict `bearer_clears_the_auth_gate`. This host **does** check authorization
  before it validates the body — the control proves the order rather than
  assuming it — and the minted bearer got past that check to the part that
  reads the body. That is why the two-armed design mattered: a lone `400` would
  have been consistent with a host that validates the body first and never
  looked at the credential at all.

  **The part that changes the next step.** The control's `401` text is
  *byte-for-byte* the text the paid turn got back on run `34347516170`:
  *"Access denied due to invalid subscription key or wrong API endpoint. Make
  sure to provide a valid key for an active subscription and use a correct
  regional API endpoint for your resource."* So the Codex runtime is being
  answered the way a **plainly invalid bearer** is answered, while the *same
  minted token* on the *same route* clears the gate when `urllib` sends it.

  What that narrows to: the difference is on the **transmission** side — what
  the runtime puts in the request — not on the identity, the token audience,
  the role, or the address, each of which is separately closed above. It is
  **not** yet narrowed to a specific cause, and specifically it does not
  establish that the header is malformed, that the token is truncated, or that
  a second credential is being preferred. Those are the candidates, not the
  finding.

  What it also does **not** establish, and must not be written up as if it did:
  the turn leg is `urllib` on the same route, not the Codex runtime, so a
  refusal reproduced here and a refusal produced there are alike in text and
  not demonstrated to be alike in cause; and no usage record comes back from a
  refusal, so this call is unpriced rather than proven free.

  **A role grant is not indicated by this evidence and is not being
  requested.** The earlier `role_missing_and_an_owner_must_grant_it` verdict
  belongs to the project-scoped Code Interpreter arm and does not transfer to
  this account route.

  **The transmission side has since been measured, and the cheap explanations
  are gone.** A **fake** token pushed through the pinned binary into a local
  mock server — the owner's standing method, no credential and no network —
  says the credential arrives correctly on both requests: the `authorization`
  header is present, it is a `Bearer`, its value is **exactly** what the auth
  command printed (38 characters in, 38 out, no truncation, no wrapping, no
  trailing newline), and **no second credential header** rides alongside for a
  gateway to prefer and reject. Measured in
  `batch-runner/tests/test_what_one_codex_turn_actually_sends.py`.

  So malformed header, truncated token, missing `Bearer ` prefix and a
  competing `api-key` are all **closed**. That is four of the cheapest
  candidates gone and the fault not found — which is the useful kind of
  negative result, because it fixes what is left.

  What is left, and all of it is a difference from the `openai.OpenAI` client
  that produced 68,610 graded rows against this same resource:

  | difference | sent by Codex | sent by the working path |
  | --- | --- | --- |
  | seven runtime headers — `originator`, `session-id`, `thread-id`, `x-client-request-id`, `x-codex-beta-features`, `x-codex-turn-metadata`, `x-codex-window-id` | yes | no |
  | its own `user-agent` | yes | a different one |
  | `stream: true` | yes | not on the grading path |
  | body size | ~45.9 KB, ten tools | a few hundred bytes |

  **The next diagnostic is free and follows from this table.** The
  discriminator's `urllib` arm is a request already known to clear the gate,
  and its body names no model so nothing can be generated. Adding the Codex
  differences to *that* request one group at a time — headers first, then
  `stream` — and watching for `400` to flip to `401` names the cause without
  buying a completion. If nothing flips it, the difference is the body, and
  that is worth knowing too. Neither outcome requires a role, and no role is
  being requested.
- **That diagnostic is now built, and it changed shape twice while being
  written.** `--transmission-sweep`, an ungated step in the diagnostic
  workflow, 29 tests in
  `batch-runner/tests/test_codex_transmission_sweep.py`.

  **First change: the arms are isolated, not cumulative.** The bullet above
  says "one group at a time", which reads as *accumulating* — headers, then
  headers plus `stream`. Written that way, the first arm that flips is
  attributable to nothing narrower than "this group, or something added before
  it", which is the same un-narrowing that made the one-armed discriminator
  unreadable. Each arm here carries **exactly one** property over the baseline,
  and a sixth arm carries all of them, so a flip means *this property is
  sufficient* rather than *something at or before this point was*. The extra
  requests are refusals and buy that distinction.

  **Second change: the values are measured, not written from the table above.**
  Extending the turn recorder to keep header *values* — it kept only names —
  says the runtime sends `originator: codex_python_sdk`. The plausible guess is
  `codex_cli_rs`, and a sweep built on the guess would have replayed a string
  nobody sends and returned a confident null result. `Accept` is likewise
  `text/event-stream` and not `application/json`. Both are now bound to the
  pinned binary by a `needs_runtime` test, so a version bump that changes
  either reddens a test instead of quietly voiding the sweep.

  Two guarantees are enforced rather than asserted. No arm may name a model:
  a `ValueError` is raised **before the token is minted**, so an arm that
  acquired one could not send anything. And the premise is re-tested every run
  — that the control is still stopped at the gate, and that the baseline still
  clears it — with `sweep_inconclusive` reported if either has moved, rather
  than five properties named as causes on a host where none of them is doing
  anything.

  Building it also found a live defect in the workflow, by failing closed the
  way the workflow's own comment said it would: the redaction check branches on
  schema prefix and the sweep's schema was unregistered, so the record fell to
  the paid-turn branch and crashed on a key free records do not have. In CI
  that fails the check, skips `Keep the record`, and destroys the record
  *after* its seven requests are spent. Registering the schema is the fix; the
  design was right.

  What the sweep will **not** settle, carried in the record on every run: these
  arms are `urllib`, so a property that closes the gate here is a candidate for
  what refuses the runtime and not a demonstration that it does; the ~45 KB
  body and the transport layer are not varied; a named property is somewhere to
  look and **not a reason to request a role**; the calls are unpriced rather
  than proven free. And the one a `400` most invites collapsing: this reads
  **the order in which the host checks a request, not what the identity is
  permitted to do.** Clearing the gate with an unservable body shows
  authorization is checked before the body is read. It does not show that a
  servable body would be served — the only request that could show that is the
  one this diagnostic never sends. Nothing here moves the 220-task column.
- **The sweep ran and returned a null, and the null does not mean what this
  document said it meant.** Run `34437632382`, seven requests. Baseline `400`.
  `Accept: text/event-stream` `400`. `originator` + `User-Agent` `400`. All six
  session/turn headers `400`. `stream: true` `400`. **Everything at once** —
  nine headers plus the body flag — `400`, with the same `Missed model
  deployment` text as the baseline and a text different from the control's
  every time. The control was `401`. `properties_that_closed_the_gate: []`.

  This was written up as "no property the runtime adds to its headers is what
  refuses it". That is not what was measured. Every arm's body named no
  `model`, and `Missed model deployment` is the deployment router saying so —
  the request stopped there, at the front, before reaching whatever refuses the
  runtime. Seven arms that all die at the same early point cannot distinguish
  between properties that act later, so an empty list here is **the instrument
  failing to see, not a finding that nothing closes the gate.** The `401`
  control shows the socket was live and the host was answering; it does not
  show the arms travelled far enough to be refused for their own reasons.

  The paragraph that followed it was closer to right for the wrong reason: it
  noted that `model` is the field a per-deployment authorization check would
  key on, and guessed a body without one may never reach that check. That is
  now the measured explanation of this null rather than a remaining suspect.
- **A servable request was sent, and it was served — so the identity may infer
  here.** Run `34442249527`: `--valid-request` to the pinned deployment, `200`,
  `response_status: completed`, model text back, 13 input and 5 output tokens,
  `price_usd: null` / `pricing: partial`, verdict `inference_succeeded`. Same
  host fingerprint that answers the runtime's `401`; token minted by the
  runtime's own `auth_command`; same path, same scope, same deployment name,
  `settings_fingerprint: sha256:af46cb55…`.

  Five hypotheses die here at once: wrong resource, missing inference
  permission, wrong deployment name, bad token minting, wrong route. **This
  also ends the case for asking anyone for a role** — the identity
  demonstrably may infer on this resource, so a role request would be asking
  for something it already has. Whatever refuses Codex is Codex-side.

  What it is still not: `urllib` is not the runtime, no tool ran, no file was
  written, no task was solved, and `partial` means unpriced rather than free.
- **`--closing-sweep`: the header experiment re-run against a baseline that
  works.** Nine servable requests. The first is the request above, unchanged —
  which is the whole point, because an arm only means "the served request plus
  this" if the baseline is that request byte for byte. The other eight are that
  request plus exactly one thing a Codex turn adds, taken from the constants
  `test_what_one_codex_turn_actually_sends.py` measured off the wire:
  `Accept: text/event-stream`; `originator` and the runtime `User-Agent`; the
  six session and turn headers; `stream: true`; `store: true`; a 19 KB
  `instructions`; ten tool definitions; and all of it at once.

  Isolated rather than cumulative. A cumulative sweep's first flip is
  attributable only to "this arm or an earlier one", and the extra requests buy
  the difference between *this property is sufficient* and *something before it
  was*. One request per arm, no retry, the same 512-token ceiling and
  90-second clock, concurrency 1, ceilings in the script rather than the
  workflow.

  The baseline is re-tested every run and a failed premise is not bought: if it
  is not served that day, the other eight are not sent, and the verdict is
  `closing_sweep_inconclusive` rather than "everything closed the gate". A
  `400` on an arm is not counted as the gate closing — that is the route
  objecting to the request's shape, and counting it would send somebody to ask
  for a role over a malformed field. Finding nothing is recorded as finding
  nothing, and points at the transport or at a body property this sweep does
  not vary.

  Same ceiling on what it can conclude as everything else here: a property that
  closes the gate is **the next place to look, not a proven cause of the turn's
  401**; all nine arms are `urllib`; nine paid requests are emphatically not
  free; and nothing here moves the 220-task column. Pinned by 31 tests in
  `batch-runner/tests/test_codex_closing_sweep.py`, every host in them a
  loopback socket.
- **What had never been sent to this resource was a request it could serve.**
  Not once, across a listing, four transmission hypotheses, an auth
  discriminator and a seven-arm sweep. So the question *may this identity infer
  here* was still open and no record on disk narrowed it, until the run above.
  `--valid-request` sends one servable Responses request through plain
  `urllib`: the deployment named, a trivial public prompt,
  `max_output_tokens: 512`, `stream: false`, `store: false`, one attempt, no
  retry, no fallback, 90-second wall clock. Gated on its own
  `send_valid_request` input *and* the resource fingerprint, so it cannot be
  reached by a forgotten flag. Pinned by
  `batch-runner/tests/test_codex_valid_request.py`.

  It is worth its cost because its three outcomes point at three different
  repairs. `200` **with model text** means the resource, the identity and the
  route are all fine and what refuses Codex is Codex-side — and a working
  request now exists to diff the runtime's against. `401`/`403` on a *servable*
  body is a permission fact, the first evidence in this whole diagnostic that
  would bear on a role, and unavailable from any free probe. `400`/`404` names
  the shape or the deployment and is still not about permission.

  Read strictly. A `200` carrying no text is recorded as inconclusive, not as a
  success, and the exit code is `0` only for a completion. Token counts are
  written down as the response reported them with `price_usd: null` and
  `pricing: partial`, because no rate for this route is registered here —
  `partial` means unpriced, not free. And a completion still says nothing about
  the Codex path (`urllib` is not the runtime), about the harness (no tool ran,
  no file was written), or about the 220-task column.

  The ceiling is 512 output tokens rather than the API's minimum of 16, and that
  is not a cost decision. These deployments reason before they emit text, so at
  16 the ceiling is spent entirely on reasoning and the answer is `200
  incomplete` with nothing in it — refused as a success, correctly, and
  therefore the decisive request wasted on an artefact of this probe's own
  configuration. If it happens anyway the record says which: the Responses
  status and `incomplete_details.reason` sit beside the HTTP status, and the
  note names the ceiling instead of leaving a bare "200 with no text" to be read
  as a failure of the route.

  The leak check needed rebuilding for it. Its branches were three free-record
  prefixes with the turn record as the `else`; this record is the first *paid*
  one and has no `observed`, so it would have crashed in the same place the
  sweep did — except after the money was spent, and the crash skips `Keep the
  record`. Every schema is now matched by name, the paid one is required to
  admit `inference_requested: true` rather than merely permitted to, and an
  unrecognised schema is refused instead of falling into somebody else's check.
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
- **The sweep was fired and it found nothing — which was the answer.** Run
  `34448607605`, verdict `no_property_closes_a_served_request`. The baseline was
  re-tested that day and served (`200`, `completed`, `gpt-5.4`, 13 in / 5 out),
  so the premise held and the other eight were bought honestly. **All nine arms
  returned `200`**, including `everything`: 30,981 bytes, nine added headers,
  `stream: true`, a 19 KB `instructions` and ten tool definitions — a request
  materially larger and stranger than a Codex turn, served without complaint.
  `properties_that_closed_the_gate: []`. Summed usage 5,942 in / 35 out,
  `price_usd: null`, `pricing: partial`; nine paid requests, unpriced, not free.
  Two arms (`stream_true`, `everything`) set `stream: true`, so their records
  hold the SSE prelude instead of a parsed final status and report no usage;
  the sum is over the seven that did, and the gate question is answered at the
  HTTP level for all nine.

  So the refusal is not in what Codex puts in the request. That is a real
  elimination and it cost nine requests, and the sweep's own record said what
  was left: the transport, or something the sweep does not vary. It was the
  second, and it was not in the request at all.

- **The 401 was ours the whole time: the auth command could not produce a token
  where Codex runs it.** Three faults, stacked, each sufficient alone, each
  producing the same silence.

  Codex authenticates by running a command and reading the token off its stdout.
  It runs that command **from the task's directory** — `open_runtime` sets
  `CodexConfig.cwd` to the workspace and the pinned SDK hands it to `Popen` —
  and **inside the isolated environment**, where `HOME` is rewritten so the
  model cannot reach the operator's home. Both are deliberate; both stay. From
  there: `python -m core.codex_azure_token` cannot import `core`, so it died
  before its first line; `DefaultAzureCredential`'s only working leg here is the
  Azure CLI, which reads `$HOME/.azure`, and with `HOME` rewritten there was no
  sign-in to read; and on failure the command prints **nothing** on stdout, by
  design, so that an error can never be mistaken for a token. Codex forwarded an
  empty bearer and the gateway answered `401 Access denied due to invalid
  subscription key or wrong API endpoint` — a sentence naming the endpoint and
  the key, both of which were correct throughout.

  Measured, free, locally, before anything was changed: the same command exits
  `0` with a 2,083-character token in the parent environment and exits `1` with
  an empty stdout under `build_isolated_environment`. A per-credential sweep of
  `DefaultAzureCredential` in the parent showed exactly one leg minting —
  `AzureCliCredential` — and six unavailable, which is why the rewritten `HOME`
  is decisive rather than incidental.

  **The first fix proposed here was wrong and its own test said so.** Pointing
  the credential at the real config directory alone still failed, because this
  development box installs `az` into user site-packages, whose path Python
  derives from `HOME`; under isolation `az` cannot start at all, and that
  masked the sign-in question. Only pointing at the config directory *and*
  neutralising that second, box-local breakage restored minting. A GitHub runner
  installs the CLI system-wide, so the second condition should not apply
  there — should, not does, and the diagnostic now carries the free instrument
  that will say which.

  The repairs are in `core/codex_runtime_config.py`, `core/codex_azure_token.py`
  and `core/codex_runner.py`, and the important property of the second one is
  what it refused to do. The sign-in's location travels in the **auth command's
  own argv** as `--azure-config-dir`. It is not added to the Codex process's
  environment, `HOME` is still rewritten, and `AZURE_CONFIG_DIR` is still absent
  from what the model's tools inherit — the easy fix, and the one a later change
  will be tempted by, is blocked by
  `test_the_isolation_still_hides_the_sign_in_from_codex_itself`. §6's
  prohibition on buying a connection with isolation is enforced here, not
  promised.

  Third, `CodexAgentRunner.require_a_usable_auth_command()` runs the real
  command in the real isolated environment once per runner and refuses to open a
  runtime when nothing comes back, raising `CodexAuthCommandFailed` with the
  command's own reason. The probe reports *that* stdout carried a token and
  never *which*; GUIDs and JWT-shaped strings are redacted out of the reason
  before it is recorded. The connection diagnostic asks first and returns
  `auth_command_produced_no_token` without sending anything, so this whole class
  of failure now costs nothing instead of arriving as a paid `401`.

  Twenty tests in
  `batch-runner/tests/test_the_auth_command_runs_where_codex_runs_it.py` hold
  the three faults apart, including one that runs the real module as a
  subprocess from a directory where `core` is not importable and fails
  *at the argument* rather than at the import. The existing credential test
  could not have caught any of this and is not at fault:
  `test_what_one_codex_turn_actually_sends.py` uses a **stub** token printer
  that needs no sign-in, which is correct for what it measures — that the
  runtime forwards whatever the command printed — and blind to the command
  printing nothing.

  What this is not. No request has been sent through the fixed path, on a runner
  or anywhere else. The local end-to-end check is the auth command minting
  inside a real isolated environment from a real task directory; it is not a
  turn, not a tool, not a deliverable, and not the column. §11's fifth box stays
  unticked.

  **Which of the three bit on the runner, which is where the 401s were
  bought.** The first one, certainly, and by itself it is enough. `PYTHONPATH`
  is neither inherited nor neutralised by `build_isolated_environment`, so it
  reaches the child only if the parent had it — and
  `codex-foundry-connection-diagnostic.yml` never sets it. With the working
  directory the task's and `PYTHONPATH` unset, `-m core.codex_azure_token`
  raises `No module named 'core'` on any host, so run `34319880025`'s empty
  bearer is accounted for without appealing to anything about this development
  box.

  The second is a **prediction and is recorded as one**. The workflow signs in
  with `azure/login`, which writes to `/home/runner/.azure` — the directory the
  rewritten `HOME` hides. `INHERITED_ENV_NAMES` does pass `AZURE_CLIENT_ID`,
  `AZURE_TENANT_ID`, `AZURE_FEDERATED_TOKEN_FILE` and the two
  `ACTIONS_ID_TOKEN_REQUEST_*` names through, so a credential that needs only
  those could still work there; but `azure/login` with OIDC writes no federated
  token file and no client secret, which is what `WorkloadIdentityCredential`
  and `EnvironmentCredential` respectively require. The expectation is
  therefore that the CLI is the working leg on the runner too and that the
  second fault bites there as well. The free `auth_command` record settles it
  either way, and it is not being assumed in advance.

  The third bit everywhere, because it is what turned both of the others into
  a sentence about a subscription key.

- **Both dispatches happened, and both answered.** Plan mode on `main`
  (`34461076798`) wrote `auth_command: {ran: true, exit_code: 0,
  produced_a_token: true, azure_config_dir: "/home/runner/.azure", ok: true}`.
  The sign-in was found where `azure/login` writes it, which is the directory
  the rewritten `HOME` hides — consistent with the prediction above, though not
  a proof of it: the measurement was taken with the fix in place, so it shows
  the fixed path works rather than showing the unfixed one failed. The question
  the prediction existed to settle is settled by the turn instead.

  The turn (`34461522053`) came back `connected`: `turn_status: completed`,
  `UserMessageThreadItem` → `ReasoningThreadItem` → `AgentMessageThreadItem`,
  10 notifications, 10,994 input / 28 output tokens, `model_context_window:
  258400`, `auth_command.ok: true`. Price unread, so the cost is recorded as
  `null` — an unpriced record is not a free one.

  What the turn did **not** establish, from the record's own `not_established`:
  the tool leg (the prompt forbids commands; `tool_execution_observed: false`),
  the deliverable leg (no file was asked for), the batch leg (one turn says
  nothing about 5, 30 or 220), and the cost leg.

- That run also exposed a reporting defect of its own: it reported
  `final_response_present: false` about a turn that had demonstrably produced
  an agent message, because `_final_text` read field names belonging to the
  SDK's `TurnResult` off the wire model `Turn`, which has neither. Fixed by
  reading the turn's items; record format bumped to
  `codex_foundry_connection/3`. The real run path was never affected —
  `TurnHandle.run()` returns a `TurnResult`, which is what
  `core/codex_runner.py` reads.

- The next step is no longer a diagnostic. It is a Codex **experiment**: there
  is still no YAML anywhere that uses `execution.mode: codex_foundry`, and
  `experiment_config.py` requires an `execution.codex` block carrying a literal
  `endpoint` — which cannot be written into a public repository, and for which
  there is no environment expansion. That gap, then the fixed 5, then 30, then
  220. Until a task produces a file, the deliverable column stays empty and is
  reported as unconfirmed. It is not filled with a substitute.
