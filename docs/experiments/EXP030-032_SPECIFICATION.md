# Experiment Specification: Execution Environment (Run Place) Comparison

**Experiment Series**: EXP030–032
**Created**: 2026-08-25 (the three experiment files and the shared plan)
**Status**: Advance check ran 2026-09-01 and did not meet its own success criteria; the third run place produced no result
**Lead**: Hyeonsang Jeon
**Plan of record**: `batch-runner/experiments/execution_envelope/advance_check_plan.yaml`

---

## About this document

This specification is written after the fact: the three experiment files were
written on 2026-08-25 and the five-task advance check ran on 2026-09-01. It
records the design as the repository pins it. Every condition below names the
file that fixes it, and where the repository records no answer this document
says so rather than supplying one.

Nothing here is a result you may cite as a ranking of execution environments.
[What this cannot tell you yet](#what-this-cannot-tell-you-yet) gives the
reasons, and they are structural rather than a matter of collecting more runs.

---

## 🎯 Research Question

> when the same GPT model does the same work, does the place it runs in change
> the result?
>
> — `advance_check_plan.yaml`, opening comment

That question only has an answer if everything except the run place is held
still, which is what the shared plan file exists to write down once for all
three places to read.

The five-task stage now on record is narrower than the question. Its stated
purpose is **to confirm the three places start under identical conditions, not
to compare scores** (`advance_check_plan.yaml`, note above
`comparison: "same_generated_code_rerun"`). The 2026-09-01 numbers are a
readiness check that reported a problem.

---

## 📐 Experiment Design

### The three run places

| ID | Where the model's Python runs | `execution.mode` | Isolation it carries |
|----|-------------------------------|------------------|----------------------|
| **exp030** | A separate Python process on the server's own operating system | `subprocess` | The runner's own timeout and the server's own limits |
| **exp031** | A Docker container built from a fixed image | `sandbox` | No network, `memory_gb: 8`, `cpus: 2.0`, image `gdpval-sandbox:latest`, `use_docker: "always"` |
| **exp032** | Azure AI Foundry runs the Python inside a container the service creates and manages | `code_interpreter` | The service's own; this repository neither sees the container nor controls what is installed in it |

### Control variables

Each of the three files declares the same split:

```yaml
control:
  fixed: [model, tasks, temperature, prompt_strategy]
  changed: [execution_environment]
```

The shared conditions are written once in `advance_check_plan.yaml`, and
`batch-runner/scripts/check_execution_envelope_advance_check.py` compares each
experiment file against the plan character by character. Editing anything the
plan also fixes stops the run instead of quietly changing the comparison. That
check calls no model and costs nothing.

### Fixed conditions

| Condition | Value | Note |
|---|---|---|
| Provider / deployment | `azure` / `gpt-5.4` | All three address one deployment name; the run may not switch it part-way |
| `temperature` | `0.0` | |
| `seed` | `42` | |
| `reasoning_effort` | `null` | Left unset deliberately — setting it in one file and not the others would change how hard the model thinks, which is not what is being measured |
| Self-review (`qa.enabled`) | `false` in all three | The model must not get a second look at its own answer in one place and not another |
| `timeout` | `1200` seconds | exp030 and exp031 only. The host place's built-in default is 570 s, raised here on purpose so the limit is not itself a difference. Azure is given none — see difference 6 |
| `max_retries` | `3` | Attempts after a network failure, a server error, or a timeout. The model's own judgement never causes one, because self-review is off |
| `resume_max_rounds` | `0` | A second round would give one place more attempts than another depending on how its errors fell |
| `tokens.code_generation` | `32768` | `16384` truncated this model's generated code in an earlier run and left an empty answer, which would have read as a failure of the run place rather than of the setting |
| Tasks | 5 fixed ids | See below |
| First request | One shared prompt file | See below |

### Task selection, and the denominator

Five task ids are fixed in the plan and repeated in each experiment file:
`02aa1805`, `0112fc9b`, `2ea2e5b5`, `3baa0009`, `0818571f` (leading segments).

The rule that produced them sorts every benchmark task by task number and fills
five slots in order — spreadsheet, document, presentation, picture, text answer
only — taking the smallest-numbered task not already taken whose job is not
already represented and whose expert answer files belong to that format. It
reads only task numbers, industries, jobs, and expert answer file types, so no
score can move it, and it is re-derived at check time from a catalogue proven
to contain no scores (`batch-runner/core/execution_envelope_tasks.py`;
`advance_check_plan.yaml`, `run_sizes.advance_check.task_selection_method`).

Every count in this document therefore has the same denominator: **5 tasks per
run place, 15 runs in total**.

### One first request for all three

The prompt was not always part of "agree on everything except where the code
runs". Each place loaded the prompt file its own runner class names, and the
three are different files. Measured through the builders a real attempt uses,
the first requests came to 3,533, 3,867 and 7,307 characters for what the
plan called one question.

That is settled: `execution.shared_first_request: true` in all three files puts
every opted-in place on `batch-runner/prompts/execution_envelope_shared.yaml`.
`batch-runner/tests/test_the_three_run_places_really_send_one_request.py` holds
a fake client where the provider client goes and fails if the three texts stop
matching byte for byte. The setting is off everywhere else in the repository, so
every other experiment builds its first request exactly as before.

---

## What the advance check produced

**Observation (2026-09-01).** The three files ran five tasks each.

| Run place | Tasks finished | Denominator | Recorded report under `batch-runner/results/` |
|---|---|---|---|
| exp030 — server process | 3 | 5 | `report/report.md` |
| exp031 — Docker container | 4 | 5 | `report/report.md` |
| exp032 — Azure code interpreter | 0 | 5 | none |

For exp032, every one of the five was refused with http 403 by the project
route. No task reached execution, so the zero is a count of calls that were
turned away, not of work the run place attempted and failed.

**Against the recorded success criteria, this stage did not pass.** The plan
requires that "all five tasks finish in all three run places without an error"
and that the conditions recorded for each place be identical on every point the
plan fixes, adding that "scores are not looked at"
(`run_sizes.advance_check.success_criteria`). Seven of the fifteen runs
finished and the criterion requires all fifteen, so the advance conditions for
moving to the thirty-task stage are not satisfied.

**What this does not establish.** The one-task gap between exp030 and exp031 is
not evidence that a container completes more work than a server process. Neither
place was run twice, so the gap has nothing to be measured against.

---

## What this cannot tell you yet

### 1. Six differences remain after the wording was equalised

Making the three request texts identical did not make the three situations
identical. `batch-runner/core/shared_first_request.py` names what stays
different in `UNCONTROLLED_DIFFERENCES`, and the free check prints all of them
and reports `pure_run_place_effect_is_measurable` as **false** while any remain.
A result from this comparison may therefore not be read as the run place's
effect on its own.

| # | What stays different | Applies to | What it could do to a result |
|---|---|---|---|
| 1 | The API the request is sent on | exp032 | The host process and the container send chat completions; Azure sends the Responses API. The two products may weight a standing instruction differently, so a gap between Azure and the other two is a gap between two products as much as between two run places |
| 2 | A tool declaration only one place sends | exp032 | The Azure call carries `tools=[{'type': 'code_interpreter'}]`, which the provider turns into instructions of its own that are never shown to the caller. Azure's model is told how to run code by text this repository cannot read, so widths reported for Azure are a floor, not a total |
| 3 | How the reference files arrive | exp032 | The other two get files copied onto a working directory; Azure gets them uploaded and referenced by file id. The bytes are checked to be the same, but a task that fails on reading its inputs may be failing on the delivery route rather than on the ability to compute |
| 4 | Isolation and the limits that come with it | exp030, exp031 | A task needing more memory than the container's cap, or a network call, fails in the container and can succeed on the host. That is a real property of the run place and belongs in the result, but it is not the model performing differently |
| 5 | What happens to the answer after the model returns it | exp031 | The container checks its output against a deliverable contract and records the verdict; the other two have no such check. The contract's text is kept out of the shared prompt, so per-task detail is richer for the container without the container having been guided |
| 6 | The per-task time limit | exp032 | The other two are both given 1200 s and it is checked to be the same number. Azure is given none, because the service creates and reclaims the container itself and documents that an idle one goes after about twenty minutes. A timing difference between Azure and the other two is not evidence either way about the run place |

These are not defects awaiting a fix. Entries 4 and 5 are the run places being
themselves: a place stripped of its isolation is not the place the comparison is
about.

### 2. Repeat variability was never measured

A difference smaller than the spread you get from running one condition several
times is not a difference between conditions. The one-task gap between exp030
and exp031 is 1 in 5.

All three experiment files pin `resume_max_rounds: 0` and no repeat count, and
searching the plan of record for repeat, rerun, variability, noise and spread
returns only unrelated matches — a folder-naming note, a credential note, and
the name of the `same_generated_code_rerun` comparison itself. **No repeat of any
single run place under this plan is recorded anywhere this document inspected.**
Until one exists, no ordering of exp030 and exp031 is supportable.

### 3. The third run place was refused before it ran

exp032 cannot start until the Azure connection setting names the project route.
`step2_run_inference._require_code_interpreter_route_profile` refuses the mode
otherwise, which the experiment file records as correct behaviour and explicitly
not to be worked around.

The plan already draws this distinction for an excluded place: leaving one out
of the comparison "records that the place could not run, which is a different
statement from *the place performed badly*". The same reading applies to a place
that ran and was refused at the door.

---

## Run places excluded on purpose

The plan names further candidates and records why each stays out. It adds two
rules: leaving a place out does not make the comparison complete, and none of
the excluded places is replaced by a substitute.

| Candidate | Why it is not in the comparison |
|---|---|
| Agentic Sandbox V2 | Its command-running tool answers that the capability is unavailable and two guards refuse the mode. The loop exists at `core/agentic_v2_conversation.py` and is proven against stand-ins that spend nothing, so only structure checks are possible |
| Codex built-in agent | No code here runs a benchmark task through it, and no official documentation was found for running its agent loop against an outside benchmark or on an Azure AI Foundry deployment |
| Codex native harness on this Foundry deployment | Its configuration reference gives a provider a static API key or a token-printing command; this repository forbids every static Azure credential variable, documents no Entra sign-in for a provider, and has no way to pin an API version — three separate blockers |
| GitHub Copilot CLI on this Foundry deployment | Its own-key path uses a static API key this repository forbids, and its Azure example addresses `/openai/deployments/<name>`, which is none of the three endpoint shapes `core/azure_ai_clients.py` accepts |
| GitHub Copilot CLI on a GitHub-served model | Which model answers is GitHub's decision under automatic model selection, so a result says something about the product rather than about a run place |

**One inconsistency, flagged rather than resolved.** The plan's comment says
"three of the five places named in the written specification are listed. The
other two are left out on purpose", and then lists five excluded candidates, not
two. Either the sentence or the list is stale. This document does not choose
between them; the count needs a reading of the written specification the comment
refers to. `[needs verification]`

---

## Stages, fixed before anything was spent

The plan fixes all three stages "so that a disappointing result cannot lead to
the rules being loosened afterwards", and only the first was asked for.

| Stage | Tasks | Advance condition |
|---|---|---|
| Advance check | 5 | Every point of the success criteria met and every required field of the run record written for all fifteen runs |
| Second stage | 30 | Every run place that can run finishes all thirty tasks and all thirty are recorded |
| Final stage | 220 | Every run place that can run finishes all two hundred and twenty tasks. This is the last stage |

Stop conditions for the advance check are absolute and do not permit switching
to another run place: stop at once if the model or deployment name reported by
the service differs anywhere; if any instruction text, task number, or input
fingerprint differs between places; if a run switches model or deployment on its
own; if the Docker place ends up running on the server's operating system
instead; if any of the three Agentic Sandbox V2 guards shows signs of having
been opened; if a paid call is about to happen without approval on record; or if
any required field of the run record is missing. Cost is recorded and reviewed
after the bounded run rather than stopping the stage, and the estimate comes
from `batch-runner/core/execution_envelope_cost.py` and the price list committed
alongside the plan.

---

## Design questions, and where the repository answers them

| Question | Answered where | Status |
|---|---|---|
| What decision does the result change? | Plan opening; the stage ladder gates paid work at 30 and 220 tasks | Recorded |
| What would show the hypothesis wrong? | `success_criteria` and `stop_conditions` are stated as pass/stop, and scores are excluded at this stage | Recorded for readiness; **not** recorded for the score comparison the series is named for |
| How many axes move at once? | `control.fixed` / `control.changed` declare one, and `UNCONTROLLED_DIFFERENCES` records six that survive it | Recorded, and the honest answer is more than one |
| Was variability measured before the comparison? | — | **Not recorded** |
| Who validates the judge? | Not applicable at this stage: "scores are not looked at" | Out of scope here; needed before the 30-task stage |
| Is a written setting the same as a controlled one? | `seed: 42` and `temperature: 0.0` are pinned, and the free check compares recorded conditions including the model name the service reported back | Recorded as pinned; whether the deployment honours them is **not recorded** |
| What do the measuring tools measure? | Task completion counts; cost from `execution_envelope_cost.py` against a committed price list | Recorded |
| Were the inputs built to favour one side? | The task rule reads only task numbers, industries, jobs and expert answer file types, and is re-derived from a catalogue proven to contain no scores | Recorded |
| When does it stop? | `stop_conditions`, per stage | Recorded |

---

## Source ledger

| File | What it fixes |
|---|---|
| `batch-runner/experiments/execution_envelope/advance_check_plan.yaml` | The question, the shared conditions, task ids and selection rule, stage ladder, success and stop conditions |
| `.../exp030_envelope_host_python_process.yaml` | Run place 1; `subprocess`; timeout raised from 570 to 1200 |
| `.../exp031_envelope_docker_container.yaml` | Run place 2; `sandbox`; `use_docker: "always"`, 8 GB, 2.0 CPU, fixed image |
| `.../exp032_envelope_azure_code_interpreter.yaml` | Run place 3; `code_interpreter`; the project-route precondition |
| `batch-runner/core/shared_first_request.py` | `UNCONTROLLED_DIFFERENCES`, and `pure_run_place_effect_is_measurable` |
| `batch-runner/core/execution_envelope_tasks.py` | The task-selection rule |
| `batch-runner/core/execution_envelope_cost.py` | The cost estimate |
| `batch-runner/scripts/check_execution_envelope_advance_check.py` | The free, model-free comparison of each file against the plan |
| `batch-runner/prompts/execution_envelope_shared.yaml` | The one first-request text |
| `batch-runner/tests/test_the_three_run_places_really_send_one_request.py` | Byte-equality of the three first requests |

One note on provenance that belongs in any reading of these files: the header of
each experiment file claimed no model had been called with it until 2026-09-06,
five days after the calls on 2026-09-01. The files now say so themselves.
