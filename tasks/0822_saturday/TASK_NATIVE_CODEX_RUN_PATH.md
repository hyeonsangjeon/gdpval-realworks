# Codex's own agent: what is officially supported, and what is still unknown

- Written: 2026-08-25
- Status: **investigation recorded. The run place stays blocked, and one part of
  it stays explicitly unconfirmed.** No code was written, because writing code
  for a path that may not be able to meet the comparison's conditions would be
  premature.
- Related GitHub Project: hyeonsangjeon/projects/5 — card
  "같은 GPT 모델의 실행 환경별 성능 비교"

## 1. The problem a person actually hits

The comparison of run places has five columns. The fifth is Codex's own built-in
agent: the tool picks its own actions, runs its own commands, reviews its own
work, and retries, without this repository directing any of it.

That column is empty. This document records what was checked, what turned out to
be true, and what remains genuinely unknown — so that the next person does not
repeat the search, and so that nobody fills the column in on an assumption.

## 2. Why an empty column is the right answer for now

The comparison's whole claim is that only the run place changes. One of the
conditions every column must meet is that it uses **the same deployment** as the
others. If Codex's own agent cannot be pointed at the same deployment, then a
Codex column would differ in two ways at once — the run place *and* the model
being served — and any difference in the scores could not be attributed to
either.

So the question is not only "can Codex be automated?" It is "can Codex's own
agent be pointed at this exact deployment?" The second question is the one that
decides whether the column can ever be honest.

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

## 7. The one fact that would unblock this

> Can Codex's own agent loop be pointed at a named Azure AI Foundry deployment,
> authenticating with a token from a directory sign-in rather than a fixed key?

If **yes**, and it can be shown in official documentation, then a run place
becomes worth designing: a mode that hands one task to `codex exec`, lets it
work, and collects the files it produced.

If **no**, the honest outcome is that this column can never satisfy the
comparison's conditions, and the comparison is a four-column comparison. That is
a perfectly good result, and much better than a fifth column that silently
measures something else.

## 8. Files that would change, if it were unblocked

| File | Role |
|---|---|
| `batch-runner/core/executor.py` | Would gain a run mode and a dispatch entry. |
| `batch-runner/core/` (new module) | Would hand a task to the tool and collect deliverable files. |
| `batch-runner/core/execution_environment_readiness.py` | The run place would move from "not implemented here" to a real grade. |
| `batch-runner/experiments/execution_envelope/advance_check_plan.yaml` | Would gain a fifth column. |

None of these should be touched before the question in section 7 is answered.

## 9. Safety, cost, and no-silent-substitution conditions

- Codex's own agent decides how many model calls to make, so the cost of a run
  is not predictable from the task. Any ceiling must be based on a hard limit on
  calls, not an expectation.
- Codex runs commands as part of its normal operation. The containment for that
  would need to be stated before any benchmark task is handed to it, in the same
  way the Agentic Sandbox V2 work requires.
- The free check must keep reporting this run place as not implemented here
  until a real path exists. It must never be reported as available on the
  strength of a plan.

## 10. How this would be checked

- A test that the run place is reported as not implemented for as long as no
  code path exists.
- A test that the comparison refuses a plan naming this run place, which already
  exists and passes.
- If it is ever built: a test that the deployment it addresses is the same one
  the other columns address, which is the condition that motivated this whole
  document.

## 11. Done when

- [ ] The question in section 7 is answered from official documentation, either
      way.
- [ ] If yes: a run place exists, and a test proves it uses the same deployment.
- [ ] If no: the comparison is documented as having four columns, with this
      document as the reason.

## 12. Known blockers and the next decision

- **Blocked on an external fact**, not on effort in this repository. No amount of
  work here establishes whether the connection is supported.
- The next decision belongs to whoever can confirm it: either a documented
  statement that Codex's own agent can use an Azure AI Foundry deployment with a
  directory sign-in, or acceptance that the comparison has four columns.

Until then the column stays empty and is reported as unconfirmed. It is not
filled with a substitute.
