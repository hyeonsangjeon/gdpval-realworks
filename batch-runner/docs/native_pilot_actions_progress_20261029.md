# Native five-task pilot: publication and Actions execution

## Current integration status

PR #785 merged as `0a15af39b3dddb8275a82be0b609303c4bdc570d`. The publication
candidate now also contains the exact reviewed heads of #786 (`96f7f056d`),
#787 (`62735b89e`) and #788 (`97aba7b2c`), resolving overlapping progress
records by retaining both histories and combining the exact CI inventories.
Those three PRs are not yet merged into main; the integrated tree needs CI.
The GHCP protected environment/token is absent in GitHub metadata (names only
were read), so that paid gate is not dispatched or supplied another credential.

Integration exposed GHCP's current source checks still using the historical
Step8/core pins. A separate source-only GHCP profile binds the three reviewed
grader files and its reader, preserving all policy fields, the original YAML
and every false execution flag. Historical positive tests execute the actual
immutable reader; current-source refusal and successor mutation tests remain.
This restores model-free input/policy checks, not the native grader seal or
an actual grade. The paid Sol diagnostic additionally requires an explicit
reviewed main/workflow SHA before checkout/authentication and permits only the
native-only single-turn mode, so a moving main cannot silently change the run.

Model-free Actions **40924442821** at `62b29f343` passed on hosted Ubuntu
24.04, image **20261026.354.1**: bwrap and the pinned Codex marker both exited
0. The bwrap-only AppArmor profile was added; the system-wide userns restriction
remained enabled and no sysctl was written. Model calls: **0**.

The prospective Sol connectivity request now explicitly sets and fingerprints
Max / 1,000,000 context, as the pilot already requests. Missing controls refuse
before authentication. The existing transport guards still bound the attempt
to input 300,000 / output 10,000 and the configured deadline/request limits.
Before a send, retain a no-clobber **USD 7.20 reference reservation**, including
one cache write per maximum input token, checked against USD 200. This is not
an invoice or verified tariff. Its receipt explicitly blocks pilot progression
until the reservation is reconciled with the five-task shared ledger; it never
pretends this CONNECTED probe is one of the benchmark tasks. The workflow
rechecks the sidecar hash and withholds an unbound/tampered artifact.

The new source-only successor preserves every predecessor and all non-source
pilot settings. The original grader seal and response-evidence refusals remain.
No paid send has occurred at the time of this source change.

## Prior publication record

The owner approved publication/CI on 2026-10-29 and then explicitly requested
paid execution without another paid-approval question. Scope remains Foundry
`gpt-5.6-sol`, Codex SDK/CLI **0.147.0**, the registered five tasks, and the
existing **USD 200 combined inference/grading ceiling**. NAS is development and
offline testing only; execution belongs on GitHub-hosted **ubuntu-24.04**.

The reviewed stack was pushed at `271093150` and published as Draft PR **#789**.
The existing open PRs #785–#788 had successful required checks at inspection.
This document does not claim that any model has run or that old source/grader
seals have been renewed. Original registrations and caps remain unchanged.

## Experiment-design record before any paid request

| Field | Registered boundary |
| --- | --- |
| Purpose | Exercise the bounded five-task native pipeline and collect auditable output/cost evidence; this does not authorize 220 tasks or establish a model ranking. |
| Runtime/condition | Foundry Sol via pinned native Codex, requested Max/1M, prepared hosted Ubuntu 24.04; not an OS-only or reasoning-only causal comparison. |
| Inputs | The existing fixed task IDs and HF `openai/gdpval` revision `11e7900cdcac61bc4daf59e65feb238acda98fbf`; no task substitution or synthetic benchmark input. |
| Judge | Existing Sol/Max grading contract, one pass per task. Synthetic frozen-source parity is not real five-task parity or independent human validation. |
| Repetition | Existing infrastructure retry policy only; no new quality retry or variance estimate. |
| Units | Provider token usage and separately labelled modeled USD; no claim that an estimate is an invoice. |
| Stops | USD 200 combined, 1,800 seconds/attempt, registered request limits, input 300,000/output 10,000, unknown usage/evidence and invalid host remain fail-closed. |
| Unverified | Fresh served model/Max/context evidence, effective Foundry tariff mapping, source/grader admission and final pilot wiring are not supplied by publication approval. |

The experiment-design check keeps settings distinct from observed enforcement.
The owner has now authorized the paid measurement; this is not a reason to
invent absent evidence or change a rejected request into a passing gate.

## Model-free hosted readiness

`gpt56-native-runner-check.yml` runs on the publication branch/PR, with only
`contents: read`, no secret reference and no Azure login or model request.
It installs the registered runtime, runs offline contracts, and executes only
the fixed local sandbox marker through the existing preparer on Actions.
Readiness failure fails the job and retains the bounded runner/probe receipt.
The job does not change the existing paid diagnostic's main-only admission.

The already-reproduced pytest 9.2 worktree-numbering fixture repair from
`97aba7b2c` is included unchanged on this branch. Exact path reuse, cleanup,
identity and failure-retention assertions remain intact.

One related offline invocation for these workflow/host/fixture changes passed
**198 tests, 0 failures/errors/skips**, 24.02 seconds. The earlier 151-case run
is separate, not added to this count. Logs/JUnit are in
`/ai-work/copilot/_tmp/native-pilot-publish-20261029.ZBwoxY/publish-check.*`.
This is not a full PR CI pass; the first CI run also exposed stale legacy
source fixtures and metadata integration cases that remain under repair.

The first PR CI also found the survey's end-to-end proof job still selected
Ubuntu 22.04 and correctly hit `execution_environment_refused`. Move only that
execution proof to prepared 24.04, keeping both unprepared survey legs and all
historical host records unchanged. Mandatory preparation, namespace diagnosis,
the two exact execution assertions and `CODEX_SANDBOX_MUST_RUN=1` remain gates;
no skip or failure is converted to success. Keep the new prepared-host receipt
as a separate artifact, not a replacement for the historical survey.

Hosted run 40919077805 (image `20261026.354.1`) showed the targeted bwrap
profile succeeded: initial namespace exit 1 became 0 without a sysctl write.
The standalone Codex probe nevertheless exited 101. Run 40922263095's bounded
failure facts identified a Rust panic and missing executable, with no model
call. The pinned 0.147.0 parser selects the OS itself and treats `linux` as the
command; its source tests use `codex sandbox -- <command>`. Remove that stray
argument, retain all namespace/exact-marker gates, and rerun the hosted proof.
This syntax correction does not introduce a legacy sandbox fallback.

## Official OpenAI documentation checked

- [CLI Linux sandbox](https://developers.openai.com/codex/cli/reference/): the
  local command uses bubblewrap/seccomp; this is not a model completion.
- [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol): the
  page reports Max support, a 1,050,000 context window and 128,000 maximum
  output tokens. These model-level facts do not prove this Foundry deployment's
  actual settings. The registered request remains **1,000,000**, not 1,050,000.

OpenAI's listed price/long-context/cache-write rules are not substituted for
the required Foundry tariff evidence. Tests and the forthcoming hosted sandbox
receipt are not benchmark scores, served-model proof or billed-usage proof.
