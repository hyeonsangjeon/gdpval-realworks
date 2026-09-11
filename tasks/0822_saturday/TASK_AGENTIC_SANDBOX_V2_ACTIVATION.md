# Agentic Sandbox V2: the activation plan, written before anything is run

- Written: 2026-09-10
- Companion to `TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md`, which is the
  specification. This is the operating plan: what gets built, in what order,
  what each stage has to prove before the next one starts, and what happens
  when a stage fails.
- Status: **plan only at the time of writing.** Every stage below records its
  own result underneath it as it happens. A stage with no result recorded has
  not been run.

## 0. Why this document exists separately

The foundation document ends on two decisions it correctly refused to take:
which row of the cost table to run stage one at, and whether to obtain a
machine that can hold the containment. Both have now been taken by the owner,
and the instruction that took them also said the thing this document is for:

> 각 단계의 조건과 실패시 대응을 실행 전에 기록하고 기술 조건을 통과하면
> 비용 재승인 질문 없이 다음 단계로 진행하세요.

Conditions written *after* a stage runs are not conditions, they are
descriptions. So they are written here first, and the results are appended
under them rather than replacing them.

Two things that decision did **not** do, stated here so no later stage can
quietly read it as having done them:

- **It is not a security waiver.** Money being approved does not open a
  boundary. Every guard in the foundation document stays shut until its own
  replacement exists and has been shown to hold.
- **It is not permission to substitute.** A stage that cannot get its
  containment fails and says so. It does not fall back to the V1 Docker
  backend, to a weaker profile, or to the host it happens to be running on.

## 1. What was inherited, read from the code on 2026-09-10

Not from the prose. Each of these was read out of the file named.

| Fact | Where |
|---|---|
| The tool contract and dispatcher are complete: 11 tools, per-call ceilings, a result-size ceiling, a deadline, replay by `call_id`, and a result envelope that is hashed. | `core/agentic_v2_tools.py` |
| The conversation loop exists and is bounded by five ceilings, each of which refuses to start when it is missing rather than defaulting. | `core/agentic_v2_conversation.py:299-349`, `:603-616` |
| Nothing can reach a real model. `real_model_voice()` raises, and the loop refuses any voice whose `makes_paid_calls` is true — defaulting to true when the voice does not say. | `core/agentic_v2_conversation.py:168-183`, `:596-601` |
| `exec_run` answers `capability_unavailable` for every command except a three-argument `fixture-upper` that upper-cases a file. | `core/agentic_v2_fixture_backend.py:197-213` |
| The batch entry point refuses the mode outright. | `step2_run_inference.py:158-163` |
| The runner in use today replays a written-down list of calls and has no model client. | `core/agentic_v2_runner.py:1` |
| The containment rules exist, in one copy, with all six questions answered. Stage C0, later the same day, added a seventh — so this row is what was inherited, not what is there now. | `core/agentic_v2_substrate.py` `REQUIRED_MICROVM_POLICY` |
| **Nothing turns those rules into arguments for starting a machine.** The readiness report says so on every rule, on every machine — "this is the same on every machine, because it is a fact about this repository". | `core/agentic_v2_containment_readiness.py:851`, via `scripts/check_agentic_containment.py`, run 2026-09-10 |
| No machine in play can host the containment: this box is kernel 3.10.102 inside a container with no virtualisation device; GitHub-hosted runners are documented as unsupported for it; the `agentic-sandbox` self-hosted runner does not exist. Stage B, later the same day, brought a machine into play that can — `machine_could_host_it: true` — so this row too is what was inherited rather than where things stand. | same run |

And one fact that is easy to miss and matters more than any of the above:

**A working paid agentic loop already exists in this repository, and it is not
this one.** `agentic_sandbox` (V1) reaches real models, runs commands in
`AgenticDockerBackend` — "uncredentialed persistent Docker compute plane" —
applies a seccomp filter that denies `execve`, `socket`, `mount`, `ptrace` and
twenty-odd more, and can split its compute plane onto another machine over
mutual TLS. It has authorization, a budget ledger and pinned pricing.

That is an asset for the parts that are genuinely shared — pricing, ledgering,
identity — and a trap for the part that is not. **V2's containment is a
Firecracker microVM, not a Docker container.** Pointing V2's `exec_run` at the
V1 backend would make every test pass and would be the substitution the
specification forbids. It is not done here, and stage C's exit condition is
written so that it could not pass if it were.

## 2. What finishing means

Restated from the instruction, as conditions that can be checked:

1. A real Foundry deployment receives a task and chooses its own tools.
2. The commands it chooses **actually run**, in an isolation that has been
   verified rather than declared.
3. Result files are collected from that isolation.
4. Failure, timeout and resume are handled and recorded.
5. Every model call, retry and execution-environment cost is in a per-task
   ledger, and a report is produced from it.
6. The path is exercised at 5 tasks, then 30, then 220.

Two things this explicitly does not mean:

- **Passing the mock tests is not finishing**, and neither is flipping
  `foundation_only` or `production_activation`.
- **A 100% solve rate is not the bar.** Tasks the model fails are ordinary
  recorded outcomes. What must not happen is a task failing *silently*, or a
  run reporting a number it did not measure.

"Environment ready" and "220 actually executed" are reported as two separate
claims and never merged into one.

## 3. Stages

Each stage lists: what it builds, the condition it must meet to be called done,
how that condition is checked, and what happens if it is not met. A stage's
exit condition is a command that returns a verdict, not a paragraph.

### Stage A — reach a real model

**Builds.** A `ModelVoice` implementation that calls the approved Foundry
deployment, plus the seam replacing `real_model_voice`'s unconditional refusal
with a gate on an approved amount being on record. The loop's
`makes_paid_calls` refusal is **not deleted** — it becomes a refusal to run a
paid voice with no approved amount and no ledger attached, which is the
condition it was actually standing in for.

**Model.** Read from `experiments/execution_envelope/agentic_stage_one_plan.yaml`
(`azure_connection`, `model.deployment`), not written into code. The ledger
records `requested_model` and `resolved_model` separately, so a deployment that
answers as something else is visible rather than assumed away. A run whose
resolved model differs from the requested one stops.

**Exit condition.** A single task completes a real conversation of at least two
turns, where turn two demonstrably contains turn one's tool result, and the
ledger holds one row per model call with token counts and either a price or an
explicit `price_missing`.

**Failure response.** If the deployment refuses, or resolves to a different
model, or the ledger comes back short of one row per call: stop, record the run
id and what came back, and do not retry with a different deployment. A model
switch is never automatic — `automatic_model_switch_allowed: false` is already
in the plan file and stays.

**Cost.** Bounded by `StageOneBudget`, which refuses the next call rather than
reporting an overspend afterwards.

The free check was run on 2026-09-10 and priced all 24 candidate rows. Two
things in it decide how stage A is approved:

| | cheapest row (4 calls, 2,048 tokens) |
|---|---|
| running | 40 model calls, **$3.37** |
| marking | 2,937 model calls, **$2,504.67** |
| total the check compares against | **$2,543.04** |

Marking does not move when the settings move; it is most of the bill at every
row. And it is not phantom: `workspace_apply` lets the model write a file and
`finalize` collects it, so **stage one really can produce something gradeable
even with `exec_run` shut**. An earlier reading of this — "nothing can be
produced, so nothing can be graded" — was checked against the tool list and is
wrong.

So stage A is approved as its own small thing rather than by approving the full
five-task run:

- Stage A calls neither `finalize` nor the grader, and the preflight requires
  that by checking the probe's tool list rather than taking its word for it.
  A probe that can reach `finalize` is priced with marking included.
- The amount approved for stage A is the priced running figure for one task at
  the chosen row, not the five-task total and not the marking column.
- The five-task stage-one run stays gated exactly as it is today. Nothing in
  stage A flips `may_start` for it.

This keeps one gate rather than growing a second path around it. No question is
asked before spending inside the approved figure.

### Stage B — a host that can hold the containment

**Builds.** An execution host definition, modelled on `infra/dev-host`, plus a
bootstrap that **measures** what it got rather than asserting it.

The hardware question has a documented answer. Azure's own size documentation
lists `Nested Virtualization: Supported` for the Dasv5 series, which is the
series `infra/dev-host` already uses (`Standard_D8as_v5`, 8 vCPU / 32 GiB), in
a subscription that is already approved and deliberately separate from the one
carrying the Foundry permissions. Ubuntu 24.04's kernel is above the 5.10 floor
Firecracker validates against.

**That is a reason to try, not a result.** "Supported" in a documentation table
and `/dev/kvm` present on a booted machine are two different facts. The
bootstrap reads the second one — the device, the `svm` flag as the guest sees
it, the running kernel, and whether `firecracker` and `jailer` start — and
writes what it read. Nothing downstream reads the documentation table.

**Exit condition.** `scripts/check_agentic_containment.py` gains a recorded
finding for this machine derived from that measurement, and the finding says
the machine *could host* the containment. If the measurement says otherwise,
the finding says otherwise and this stage has failed honestly.

**Failure response.** If `/dev/kvm` is not there, the stage stops and the next
decision is stated with its options priced — a different SKU, a different
region, or a different containment technology, each of which is a change to the
signed policy and therefore its own reviewed change. **It does not become
"run it in Docker instead".**

**Access, lifetime, cleanup.** Inherited from `infra/dev-host` because that
shape has already been reviewed: no inbound SSH rule, no public address,
system-assigned identity with no role, `az vm run-command` as the only way in,
auto-shutdown on a daily ceiling, and a `delete` that requires the resource
group name to be repeated back. Usage is recorded per run; where the price is
unknown it is `null`, never `0`.

### Stage C — apply the rules, then attack them

**Builds.** The launcher that nobody has written: the module that turns
`REQUIRED_MICROVM_POLICY` into arguments for starting a machine. This is the
blocker the readiness report calls "the same on every machine, because it is a
fact about this repository".

**Exit condition.** For each of the seven rules, a test that **starts the
machine, exceeds the rule, and requires the machine to stop it**: writing past
the 256 MiB working-directory quota, allocating past 4,096 MiB, running past
1,200 seconds, opening a network connection, writing to the read-only root,
running as a privileged user, and reading a token, key or environment secret
the orchestrator holds.

The last of those was written here as an eighth test alongside six rules, which
was the wrong shape: no rule said a command may not read the orchestrator's
credentials, so the test would have passed against nothing at all. C0 adds the
rule, and the count becomes seven and seven.

This is the test `tests/test_agentic_v2_containment_rules.py` names in its own
docstring and declines to fake — "that is the test these rules will eventually
need, and it cannot be written yet … a passing test named after a thing that
never happened is how an unenforced rule comes to look enforced". When the
launcher exists the test becomes writable, and that note is corrected by the
test existing, not by editing the note.

**Failure response.** A rule that is not enforced by the launcher is a rule
that does not exist. If any of the seven attacks succeeds, `exec_run` stays
shut and the finding is recorded with the exact escape. **No attack is
downgraded to a warning**, and no rule is relaxed to make its test pass.

**What is not built here.** Nothing that runs as root, nothing that turns off a
host's unprivileged-namespace restriction, no `--privileged`, no capability
added to make a test pass, and no automatic fallback to the existing runner.
Those are the shortcuts the instruction names directly, and they are refused
rather than reasoned around.

### Stage D — open `exec_run`, and produce files

**Entry condition.** Stage C passed in full. Not partially.

**Builds.** A real `AgenticV2Backend` whose `exec_run` runs the model's chosen
command inside the machine stage C proved, and whose `finalize` collects the
files it produced back out, hashed.

**Exit condition.** A task where the model chooses a command, the command
really runs, a file that did not exist before exists afterwards, its hash
matches what `finalize` reported, and the whole exchange is in the event chain.
The two guards in `step2_run_inference.py` and `core/executor.py` are revisited
here, each in its own change, each stating what replaced it.

**Failure response.** If a command cannot be run, the tool answers a refusal
and the model is shown it — that is the loop working, not the stage failing.
The stage fails if a command runs *outside* the containment, if a file is
collected that the containment cannot account for, or if the guards are opened
without their replacement being in place.

### Stage E — the run path around it

**Builds.** Runner, workflow, resume, per-task ledger, report. Resume must come
back to a half-finished task without re-charging the calls already made and
recorded.

**Exit condition.** A deliberately interrupted run resumes and finishes, and
the ledger afterwards holds each call exactly once. Timeout and failure produce
recorded outcomes with named reasons, not absences.

**Failure response.** A resume that double-charges, or that loses a task, stops
the stage. Nothing scales up on a run path that cannot be interrupted safely.

### Stage F — 5, then 30, then 220

**Exit condition per step.** Every task ends in a named outcome; the ledger row
count matches the call count; no task disappears. Solve rate is reported, not
gated.

**Failure response.** A step that ends with unexplained missing tasks is not
followed by the next step. Between steps, what was learned is written down
before more is spent — but no approval is re-sought for cost alone.

## 4. Ownership

B owns V2 core, tools, isolation, image, tests, and the V2 specifications. A
owns the Codex files. `core/executor.py`, shared config, the ledger, shared CI
and `CHANGELOG.md` are touched by both: every such change states its intent in
its pull request, one side merges, and the other rebases onto latest `main`
rather than editing across. Runs in flight are separated by pinned SHA, inputs
and price fingerprint.

## 5. Results

Appended as stages complete. A stage with nothing here has not been run.

### Stage A — half built, 2026-09-10. Not passed.

Reported as two things, because they are two things.

**Built and proven for free.** `core/agentic_v2_model_voice.AzureFoundryVoice`
asks a Foundry deployment through the Responses API. It is exercised by 18
tests against a stand-in client (`tests/test_agentic_v2_model_voice.py`), which
cover the four ways a paid loop goes quiet: spending past a limit, counting a
call it did not make, missing a call it did, and carrying on after the thing
answering changed underneath it. Alongside it, the seam
`real_model_voice()` now returns a voice when it is given a client **and** a
budget, and raises otherwise; and the loop's refusal was narrowed from "any
paid voice" to "a paid voice with no approved amount".

**Not done.** Nothing has asked a real model. The exit condition above — two
real turns, turn two carrying turn one's tool result, one ledger row per call —
has not been met, and the plan file still has no approved amount, so the free
check still exits 1.

**One thing was made stricter rather than looser.** Narrowing the refusal would
have let through a voice that never declared whether it costs anything, because
the old code read a missing declaration as "paid" and the new gate would then
have been satisfied by the budget. That is now its own refusal: an undeclared
voice is refused *even on a budgeted run*. An approved amount is approval to
spend on a known model, not permission to ask an unexamined one. The free check
runs all three refusals rather than reading them.

**What stands between here and the exit condition:** an amount written into
`experiments/execution_envelope/agentic_stage_one_plan.yaml`, a client built
through `core/azure_ai_clients.py`, and a probe that wires the two to the loop
while reaching neither `finalize` nor the grader.

### Stage A — approved and built, 2026-09-10. Still not passed.

Two of the three things above are done. The third is the paid call itself.

**The amount.** `cost.stage_a_probe.approved_maximum_usd` is $1.00, against a
priced ceiling of **$0.59** — $0.47 to run, $0.00 to mark, 8 model calls at
most, at the cheapest candidate row (4 tool calls, 2,048 tokens a turn). The
figure is not copied from anywhere: `stage_a_probe_ceiling()` reuses the same
arithmetic the 24-row table above comes from, with exactly two things changed —
one task instead of five, and `grading_required=False` — so a correction to
stage one's pricing reaches this figure too. Stage one's own
`approved_maximum_usd` is untouched and still `null`.

Four calls is a deliberate floor rather than economising. It is the smallest
setting that leaves a model room to spend a turn orienting and still have a
later turn that must react to an earlier one's answer, which is the entire
question. Paying for longer replies would buy nothing stage A is asking about.

**The probe.** `core/agentic_v2_stage_a_probe.py` offers two tools —
`capabilities_query` and `workspace_apply` — and not the eighth.
`check_probe_tools()` raises `ProbeToolsAreWrong` **before the first call** if
`finalize` or `exec_run` ever appears, so the cheapest moment to catch a probe
that could reach the grader is the one it is caught at. The instructions name
no tool: a probe that tells a model to call `capabilities_query` and then
reports that it called `capabilities_query` has established that models follow
instructions, not that they choose.

**One gate, two verdicts.** `run_stage_one_preflight` collects the safety
findings once and hands the same list to both verdicts. Stage A decides for
itself only what is genuinely its own — one task, no marking, its narrower tool
list, its own amount. Held in place by tests that break a safety block and
require *both* verdicts to turn red, and that give stage one $10,000 while
leaving stage A's amount empty and require stage A to refuse anyway.
`scripts/check_agentic_stage_one_ceiling.py --probe` exits 0; the same command
without the flag still exits 1 and prints stage one's refusal in the same
report.

**A double charge was found and removed.** Both `AzureFoundryVoice.next_turn`
and `run_model_conversation` were calling `budget.record(...)`, so every paid
call was charged twice and an approved run would have stopped at half the calls
it paid for — looking, from the outside, like a model that gave up. The loop is
now the only place that charges, matching what `ScriptedVoice` already did. At
stage A's settings this was not cosmetic: a two-call budget exhausted after one
call, and the second turn is the whole question.

**Each call now records what it carried.** `history_entries_sent` goes onto
every ledger row, so "the second turn saw the first turn's answer" is a fact
about a request that was paid for rather than something inferred afterwards
from its token count. Two turns that each started from nothing read as `[0, 0]`
and fail, which is the failure it exists to catch.

**Proven end to end without paying.** A stand-in client, the real voice, the
real dispatcher, the real fixture backend: the model asks for
`workspace_apply`, a file is really written to disk, and the request after it
goes out carrying that answer — `history_entries_sent` of `[0, 1, 2]`. 19 tests
in `tests/test_agentic_v2_stage_a_probe.py`, none of which reach a network.

**Still not done.** Nothing has asked a real model. What is left is a client
built through `core/azure_ai_clients.AzureAIClientFactory` on the `project-ci`
route profile, and the one paid run.

### Stage A — the asking built, 2026-09-10. The one call still not made.

**It cannot be a command someone runs here, and that is a property of the
code.** `AzureAIClientFactory` calls `_reject_static_azure_credential_env`
before it builds anything and takes its identity from a federated session, so a
client cannot be built at all outside a job holding `id-token: write`. On this
box `AzureAIClientFactory()` raises `AZURE_AI_ROUTE_PROFILE is required` and no
Azure environment is configured. The paid run is therefore a workflow —
`.github/workflows/agentic-v2-stage-a-probe.yml` — and not a local invocation.

**`scripts/run_agentic_stage_a_probe.py`.** Runs the free check first and stops
on its verdict. Reads the task's wording from the pinned dataset at run time and
hashes it against the catalogue, because the catalogue holds a hash and never
the benchmark text — a prompt that changed is a different task, and a different
task is not the one that was priced. Builds the client through the one reviewed
place. Checks the resolved route against all three things the plan fixes — the
account, the project and the route profile — *after* the client exists and
*before* anything is asked, so a misconfigured dispatch costs nothing. Runs in a
fresh empty `mkdtemp` directory.

**`--dry-run` is the whole path minus the network**, and it is free for a reason
rather than by intention: with no Azure environment configured, a client cannot
be built, so a clean exit is a run that never tried. It reports the same figures
the gate published, character for character, read back from the verdict's own
report rather than formatted a second time:

```
  at most        $0.59 ($0.47 running, $0.00 marking) against the $1.00 approved
  deployment     gpt-5.4 at hjeon-fdpo-foundry-eus2
  route          project-ci into project gdpval-realworks
```

**The exit code answers stage A's question, not "did it work".** Zero needs
three things together: a model reached, at least two turns, and a later call
that went out holding an earlier tool's answer. Any one alone is true of a run
that proved nothing — two turns could each have started from an empty history,
and reaching a model is only a connection. A model that was reached and declined
to use a tool exits 1 and is uploaded anyway. That is a finding about the model,
and stage A collects findings; it does not launder them into successes.

**What survives a paid run** is one row per model call — turn, deployment asked
for, model that answered, token counts, `history_entries_sent`, and either a
price or an explicit `price_missing`. Not the benchmark wording, not the model's
words, no credential, and the route only as its endpoint-free fingerprint. Held
by tests rather than by reading.

**The workflow cannot be made to spend by accident.** `workflow_dispatch` only —
no push, pull_request or schedule trigger — the mode defaults to `dry-run`, the
paid job needs both `inputs.mode == 'paid'` and the free job to have passed, and
only the paid job holds `id-token: write`. A run is never cancelled part-way,
because a killed conversation has been charged for turns it would leave no
record of. The deployment is read from the plan at run time rather than restated
in the workflow, so the route that gets validated cannot drift from the model
that gets asked. 33 tests in `tests/test_run_agentic_stage_a_probe.py`, nine of
them on the workflow file itself.

**The 59 cents were checked against the raw data, not against the check that
printed them.** A figure produced by the code that also approves it is one
number wearing two hats. Worked out again by hand from the sources instead:
`1.25`/`5.00` per million from `model_price_table.json`, `3.0` characters a
token and `7307` characters of instruction and the `1.25` multiplier from
`advance_check_plan.yaml`, `1589` characters of task from the catalogue, `65536`
bytes of tool result from the dispatcher's own dataclass, and 4 calls across 2
attempts from the plan. That gives 310,456 tokens sent and 16,384 received, and
`$0.46999` before the multiplier and `$0.5874875` after it — the same figures to
the last digit, and the same token counts the free check prints.

It also caught something. The arithmetic only lands there with `7307`
characters of instruction; at the `5020` the plan's own prose still claimed, it
would be `$0.46`. That sentence had gone stale when the sections nobody had
counted were counted, and it took the cheapest stage-one row with it — `3.37` to
run, where the prose said `3.32`. The figures were never wrong; the sentence
describing where they came from was. It now names the history rather than a
number, because a number copied into prose is a number that goes stale the next
time the measurement moves, which is what happened.

**The route check would have refused the run, and the fault was in the check.**
Found by resolving the route the workflow really configures rather than the one
the tests imagined. Under `project-ci` the selection for inference comes back as
an account-scoped `direct-v1` URL derived from the project endpoint — it carries
the account and a `project` of `None`. Checking the selection's project alone
therefore refused the one configuration the paid job uses, after the Azure
sign-in and before anything was asked. No money, but a dispatch spent reporting
a fault that was in the check.

The project the run is held to is the one the client was built from, so it is
read from those settings when the selected route does not carry it. Not a
fallback that looks away: a wrong project endpoint is still refused, and a
project that *nothing* names is refused too, with a different sentence, because
an unconfirmable project is exactly what a quiet skip would hide. Four more
tests, all three cases exercised against the real resolution and not a stand-in.

**And the job would not have got as far as that check.** Turning
`AZURE_AI_REQUIRE_EXPECTED_IDENTITIES` on makes `AzureAIRouteSettings.from_env`
demand every name its own table lists for the profile, and `project-ci` lists
three. The job passed two. `from_env` therefore raises
`required Azure AI endpoint identities are missing: AZURE_AI_EXPECTED_DIRECT_ACCOUNT`
— after the federated sign-in, before the route check, before the question.
Measured by handing the step's exact environment to `from_env`, not by reading
it: two names in, that error; three names in, a client, `settings.project.project`
of `gdpval-realworks`, and the account-scoped route above.

Every other paid workflow in the repository passes all three. This one is the
only one that did not, which is what a first workflow is for. The fix is one
line in each of two steps, but the test that came with it is not about those
two lines: it reads the required names out of `REQUIRED_IDENTITY_ENV_BY_PROFILE`
and checks every step that switches the demand on can meet it. A profile that
grows a fourth requirement now fails on the day it grows one, rather than on
the day somebody dispatches. Run against the file as it stood, it names both
steps and the missing variable.

**The dispatch was made.** Twice, on 2026-09-10, both of workflow
`agentic-v2-stage-a-probe`.

The dry run, `34449960247`, succeeded, and printed in CI exactly what it had
printed locally, to the character: the same task, the same two tools, the same
`$0.59 ($0.47 running, $0.00 marking)` against the `$1.00` approved, the same
deployment and route. Nothing was asked and nothing was spent.

The paid run, `34450289535`, **failed**, and the workflow reported it honestly.
Every step up to and including `Ask` passed; `Report what happened` re-raised
the probe's own exit code, which is what it is for. The record the probe wrote:

```
"reached_a_model": false,   "model_calls": [],   "turns_taken": 0,
"spent_usd": "0",           "resolved_model": null,
"stop_reason": "model_stopped_without_finishing",
"detail": "the model stopped without committing an answer:
           asking the model failed: BadRequestError"
```

**Nothing was charged.** A `400` is a refusal of the request; the model is not
asked, so there are no tokens to bill. `model_calls` is empty because none was
made, and `spent_usd` is `0` because that is measured from the calls, not
assumed. This is the outcome the stage was built to be able to record.

**What was wrong.** Every tool was offered with `strict: true`. That flag is
not a setting for how carefully arguments are checked — it is a declaration
that the schema fits a narrow subset the service enforces on the model's
behalf, and the service validates the declaration when the request arrives. Of
the two tools stage A offers, `workspace_apply` is a `oneOf` at the root — one
branch per operation, each carrying only its own fields — and `capabilities_query`
has genuinely optional fields. Both are outside the subset. Neither could ever
have been sent.

An overclaim does not degrade to a laxer check. It makes the call impossible,
before inference, which is why no amount of local rehearsal found it: the dry
run does not build a request, and every unit test read the definitions back
rather than asking whether a service would take them.

**Nothing was loosened to fix it.** `strict` is now `false`, and what the desk
will *act* on is unchanged — `validate_tool_arguments` validates against the
same schemas in full, `oneOf`, `pattern`, length bounds and all, and is still
the only thing between a tool call and the workspace. The schemas were
deliberately not narrowed to fit the subset; they are the real contract. What
was dropped is a promise that could not be kept. The cost is a turn
occasionally spent on arguments the model must be told were malformed.

**The second defect was that the failure could not be read.** The probe
recorded `BadRequestError` and no more, so the cause had to be re-derived by
hand from the payload while the service had already answered in the status and
error code it sent back. The note now carries both, through the same reduction
`code_interpreter` already used for provider refusals — status and a
code-shaped code, nothing else read — which is now shared in
`core/provider_refusal.py` rather than existing in two copies. An endpoint, an
account, a project or a deployment cannot pass a code-shaped allow-list, so the
note that says *what* was refused still cannot say *who* refused it.

**The guard.** `test_tool_definitions_can_honour_what_they_claim` reads the
definitions the way the service does and fails any that claims `strict` while
breaking the subset. It covers v1 as well as v2, and it found the same
overclaim in v1's `run_ffmpeg` — which is **not fixed here**. v1's tool JSON is
hashed into `V1_TOOLS_SHA256`, freezing v1 as the baseline v2 is measured
against; changing it is a decision about that baseline and every v1 result
recorded under it, not a side effect of a v2 fix. It is recorded in
`KNOWN_OVERCLAIMS` and asserted to *still* be broken, so the day it is fixed
the test fails and puts the frozen hash in front of whoever fixed it. An
`agentic_sandbox` run that offers `run_ffmpeg` is refused with `400` today.

#### Asked again, and answered — run 34455103245, 2026-09-10

The blast radius of the v1 defect was checked rather than left implied: **no
experiment YAML selects `execution_mode: agentic_sandbox`**, so the mode is
live and reachable from `core/executor.py` but nothing committed dispatches it
today. That is why it can wait for a change that re-cuts `V1_TOOLS_SHA256`
deliberately.

Before re-dispatching, the payload the paid probe would actually send was
captured offline — the real `PROBE_TOOLS` and the real voice driven through
`run_stage_a_probe` with a client that records and stops. Every key is one
`Responses.create` accepts, both tools carried `strict: false`, and neither the
tool definitions nor the input items held a key outside the SDK's own
`FunctionToolParam` and `EasyInputMessageParam`. That ruled out the structural
causes of a `400` that can be ruled out for free. It did not promise success:
a service can refuse for reasons only it knows, and what had changed was that
the record would then say which.

Free dry run on `main` at the merge commit `86152b7`: passed. Then the paid
run, with conditions and per-outcome responses written down first.

**The exit condition is met.**

```
reached_a_model: true            resolved_model: "gpt-5.4"
carried_the_first_result: true   turns_taken: 4
stop_reason: "turn_limit_reached"
spent_usd: "0.00635250"          price_missing: false
```

The four calls, in order, sent `0, 1, 2, 3` history entries and `1026, 1127,
1211, 1306` input tokens. The conversation genuinely accumulated: turn two went
out holding turn one's answer, which is the one thing stage A existed to
establish and the one thing nothing offline could have shown. The deployment
asked for and the model that answered agree, so this is one model's work.

**Cost.** $0.0064 — about six tenths of a cent, against a worked-out ceiling of
$0.59 and an approved maximum of $1.00. Roughly 1% of the ceiling, because the
loop stopped at four turns. Every call priced; `price_missing` false
throughout, so the total is a real total rather than a partial one.

**What it does not say.** The model asked for `capabilities_query` three times
out of four and wrote once. It did not finish the task — it ran out of allowed
turns. Finishing was deliberately not the exit condition, and the run is not
counted as a failure for it. But it is a finding worth carrying into stage D:
under a tight ceiling this model spent most of its turns asking what it could
do rather than doing it, and a stage that offers `exec_run` will have to be
sized with that in mind rather than assuming turns go to work.

**Still not done.** Stage A is done and answered yes. What remains is every
stage that makes the answer useful: a host that can actually contain a command
(B), a launcher that starts one (C), a real backend with `exec_run` open (D),
the runner, resume, ledger and report (E), and 5, then 30, then 220 tasks (F).
Nothing here opened `exec_run`, removed a guard or flipped an activation flag.

### Stage B — the execution host, and what will be measured before anything runs on it

Written before anything is provisioned, because the point of stage B is to find
out whether the containment V2 requires can exist at all, and a plan written
afterwards is a plan fitted to whatever turned up.

**The question.** `core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY` says a
command runs inside a Firecracker microVM with no network, a read-only root
filesystem, an ephemeral working directory capped at 256 MiB, 4096 MiB of
memory, a 1200-second wall clock, an unprivileged jailer user, and
stop-and-report on breach. Nothing in the repository turns that into arguments
for starting a virtual machine, and until stage B there is nowhere it could
start one.

**What is already known, and how.** `scripts/check_agentic_containment.py` was
run on this machine on 2026-09-10. Its answer, unedited:

* the processor reports `svm`, so the hardware can virtualise;
* `/dev/kvm` is not reachable — this is a container and nothing passes it
  through;
* the kernel is 3.10.102, below the 5.10 that Firecracker's own kernel policy
  lists;
* `firecracker` and `jailer` are not on the path.

The kernel alone settles it: this machine is out, and no configuration change
here would put it back in. The two machines that cannot be read from here are
already recorded in `RECORDED_FINDINGS` — GitHub-hosted runners are a *no*
(GitHub documents nested virtualisation as unsupported, and a boundary offered
with no guarantee is not a boundary), and the self-hosted `agentic-sandbox`
label is an *unknown* because no such runner is registered.

So the host has to be the Azure development VM, which is what `infra/dev-host/`
already specifies and what the card already allows.

**What stage B does not do.** It does not design a new host. `infra/dev-host/`
has a template, a deploy script with `plan`/`deploy`/`bootstrap`/`status`/
`deallocate`/`start`/`delete`, a bootstrap that reaches the machine through
`az vm run-command` rather than an open port, 22 offline checks in CI, and a
boundary module that refuses to start a benchmark run on it. None of that is
rewritten. Stage B uses it.

It also does not touch `infra/dev-host/bootstrap.sh`. That file installs and
measures for the Codex sandbox question, which is A's, and the two questions
must not be entangled in one file while both are in flight. Stage B's
measurement goes in its own script under `batch-runner/scripts/`, invoked the
same way.

**The measurement.** `check_agentic_containment.py` run on the VM, its JSON
kept as an artefact. Four readings decide it:

| Reading | Pass |
|---|---|
| processor virtualisation flag | `vmx` or `svm` present |
| `/dev/kvm` | present and openable by the invoking user |
| kernel release | ≥ 5.10 |
| `firecracker` and `jailer` | both on the path after install |

Ubuntu 24.04 ships 6.8, so the kernel is expected to pass and would be a
surprise if it did not. The programs are an install, not a property of the
machine. The reading that actually decides stage B is `/dev/kvm`.

**What happens if `/dev/kvm` is absent.** This is the outcome to plan for, not
the one to hope against. The template's default size is `Standard_D8as_v5`,
which is an AMD-based v5 size, and Azure's nested-virtualisation support is not
uniform across the v5 families. If the device is absent the response is a size
change and a re-measurement, not a policy change:

* `Standard_D8s_v5` is Intel, is the same 8 vCPU / 32 GiB the card fixes, and
  is **already in `KNOWN_VM_SIZES`** in `check_dev_host_definition.py`. Checked
  rather than assumed: a copy of `infra/` with `vmSize` swapped to it was put
  through `check_dev_host_definition.py`, and all 22 checks passed. So the
  change needs no card amendment, no new approval and no edit to the checker,
  and keeps the shape the card fixed.
* If `TrustedLaunch` is what blocks the device rather than the processor family,
  that is a finding to record and to raise, because turning it off is a
  security-posture change to a machine and belongs to a person, not to this
  stage.
* If neither works, stage B ends with a recorded *no* for the Azure host and V2
  stops at stage B. It does not fall back to the V1 Docker runner, and it does
  not proceed with a weaker boundary described as a strong one.

**What is not allowed to happen at any point in stage B.** No `sudo` for the
model. No privileged container. No removal of either of the two guards that
keep V2 out of the paid pipeline. No opening of `exec_run` — that is stage D
and gets its own change. If the containment cannot be demonstrated, the honest
outcome is that commands do not run, and that is a result stage B is allowed to
return.

**Cost.** The VM is charged per hour it is allocated. `deploy.sh` has
`deallocate` and the template has an automatic shutdown at 2100 KST; stage B
deallocates as soon as the measurement artefact is in hand rather than leaving
the machine up between sessions. The figure is recorded in the ledger from the
measured allocated time; the per-hour price is not committed in this repository,
so if it is not available at the time of writing the entry it is `partial`, not
zero.

**Done when.** The readiness JSON from the VM is an artefact of a run, it says
whether the four readings passed, and the answer — yes or no — is written into
`RECORDED_FINDINGS` with the date and how it was established, in the same shape
as the two findings already there. A yes is not the exit condition. A recorded,
sourced answer is.

#### Run, and answered — 2026-09-10

**The answer is yes, and it was measured rather than argued for.**

The host was deployed from `infra/dev-host` with no change to the template:
`gdpval-devhost-vm`, `Standard_D8as_v5`, `koreacentral`, Ubuntu 24.04 image
`24.04.202608270`, `TrustedLaunch`, password authentication disabled, **no
public IP and no inbound allow rule** — the NSG carries only the deny-all rule,
so the machine is reachable solely through the Azure control plane
(`az vm run-command`). That was established before any key material was
generated, and the key that was generated is a dedicated one for this host, not
the box's default identity.

`scripts/check_agentic_containment.py --json` was run on the VM against a clone
of this repository at `86152b7`. The report is 10,560 bytes, sha256
`ee2222285af39a4674ed524865b08397413ab7d758543db20a8caf2477eda070`, verified
against the VM's own computation of that hash after transfer:

| reading | result |
|---|---|
| processor virtualisation flag | `svm` — **met** |
| `/dev/kvm` | present, `crw-rw---- root kvm 10, 232` — **met** |
| kernel release | `6.17.0-1022-azure`, above the 5.10 floor — **met** |
| `firecracker` and `jailer` | v1.13.1, both run — **met** |

`machine_could_host_it: true`.

**The plan's prediction was wrong, and that is the point of having written it
down first.** It expected the AMD default might not expose `/dev/kvm` and
pre-authorised the Intel `Standard_D8s_v5`. The device is there, so no size
change was made and the pre-authorisation went unused. Nested virtualisation
survived `TrustedLaunch` on this size, which does not hold everywhere and is
recorded as a reading rather than carried forward as an assumption.

**One honest caveat.** `firecracker` and `jailer` are not on the image; they
were installed during the measurement from the project's own release. A freshly
deployed host therefore answers *no* on that fourth reading until it is
bootstrapped. The three that no install can supply — processor, device, kernel —
are the ones that make this a property of the machine.

**What did not change.** `required_containment_available` is still `false`, and
the nine policy rules of that commit still read `cannot be established here` —
ten, once C0 added the credential rule later the same day — because no module
turns `REQUIRED_MICROVM_POLICY` into arguments for starting a virtual machine.
That is stage C. So `could_be_hosted_on_any_machine_in_play` flips to `true`,
`available_on_any_machine_in_play` stays `false`, and
`refuse_command_execution` keeps refusing — now naming the second ground rather
than the first. No guard was removed, no activation flag was moved, `exec_run`
stays shut, and nothing fell back to the V1 Docker runner.

**Cost.** Allocated 2026-09-10 08:40:50Z, deallocated by 08:54Z: about 13
minutes of `Standard_D8as_v5`, confirmed `PowerState/deallocated`. The disks are
kept and still charge. The per-hour rate for this size under this subscription
is not established here, so the entry is `partial`, not zero.

**Done when — met.** The readiness JSON is an artefact, the four readings are in
it, and the answer is written into `RECORDED_FINDINGS` as a third finding with
its date and its source, in the same shape as the two already there. The finding
disclaims in its own words the thing a `true` there does not mean.

### Stage C — the launcher, and the attacks that test it

#### The plan, written before any of it is built

Stage C is where the rules stop being written down and start being applied.
Stage B established that a machine *could* host the containment; nothing yet
turns `REQUIRED_MICROVM_POLICY` into arguments for starting one. Until that
module exists, nine of the ten rules read `cannot be established here`, and that
is the honest reading rather than a gap in the report. The tenth is `required:
true`, which is satisfied by the policy saying so — it is the rule that makes the
other nine mandatory, not one of the things a machine has to provide. C0 adds an
eleventh, and it joins the nine rather than the one.

**Stage C is split into four changes, merged in order, because they fail
differently and only the first two can be checked without spending anything.**

##### C0 — the rule that is missing, found before anything was built on top of it

**Builds.** One new entry in `REQUIRED_MICROVM_POLICY`, the same entry in
`sandbox/agentic_v2_capabilities.json`, and its wording in
`_POLICY_SETTING_AS_A_CLAIM`. Three places, established by trying it rather
than by reading — see below.

**Why.** The seven attacks in C3 include reading a token, key or environment
secret the orchestrator holds. Checking the sources rather than assuming: the
words *credential*, *secret* and *token* do not appear in
`core/agentic_v2_substrate.py`, in the signed policy, or in the capabilities
manifest. The six questions the containment answers are where a command may
write, whether it can reach the network, how much memory, how long, who it runs
as, and what happens on breach. **The credential boundary is not among them.**

So attack 7 as first drafted would have tested a boundary no rule states, which
is the same pretend-enforcement this stage exists to end, only pointed the other
way: instead of a rule nothing applies, a test with no rule behind it. The fix is
to write the rule down first.

**Scope, measured rather than guessed — and the guess was short by one.**
The plan first said two files. Adding `credentials: "none-inherited"` to the
policy and the manifest on a scratch copy and running every agentic test found
exactly one failure:
`test_a_machine_with_everything_still_does_not_have_the_containment`. The report
builds one sentence per rule from `_POLICY_SETTING_AS_A_CLAIM`, and a key with
no wording there does not go unnoticed — it produces a line saying the manifest
"has gained a containment setting this report does not know how to describe or
check", which is not the "unenforced rather than met" the test requires. **The
codebase names its own third place**, and reading rather than running would
have missed it.

What did *not* break is as useful. `containment_rules_that_disagree` and the
signed-policy validation both passed untouched, which confirms the rest of the
scope: `_SUPPLY_CHAIN_RULE_NAMES` translates only four of the ten containment
rules into the signed policy's naming, and the other six — including every limit
with a number — live on the containment side alone. A seventh joins them there.
It is deliberately **not** added to the signed policy: that file carries a
signature, and extending it is a separate question from writing the rule down.
The drop test and the manifest-equality test came along on their own, since
`test_a_manifest_that_drops_a_rule_entirely_is_refused` iterates whatever the
policy holds. The weaken test does not — it is parametrised by hand, so C0 adds
its entry there too, a coverage gap rather than a failure and therefore the kind
that stays open unless it is written down.

**Six becomes seven, and prose does not follow a dict on its own.** The last
change of this shape made a docstring false — PR #490 added a finding and left a
test file still asserting the opposite, caught only by grepping the tree
afterwards. The same failure is available here, so the places that say *six* are
listed before the change rather than hunted after it:

| says six | change it |
|---|---|
| `core/agentic_v2_substrate.py:143` — "Six things have to be stated" | yes |
| `core/agentic_v2_substrate.py:222` — "one of the six questions" | yes |
| `tests/test_agentic_v2_containment_rules.py:3` — "Six questions have to be answered" | yes |
| `tests/test_agentic_v2_containment_rules.py:71` — section comment | yes |
| the test named `test_every_one_of_the_six_questions_has_an_answer` | yes, renamed |
| this document, the inherited-state table and stage C's exit condition | yes |
| `CHANGELOG.md` and `TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md` | **no** |

The last row is the one worth stating. Those record what was true on
2026-08-26, when six was the answer. Rewriting them would not fix a stale
sentence, it would falsify a record of when the rule set changed — and the
count moving is exactly the thing a history is for.

**Exit condition.** The new rule is stated, the manifest equals the policy again,
weakening it is refused like the other ten, `containment_rules_that_disagree`
still returns nothing, and nothing in `core/` or `tests/` still says the
containment answers six questions.

**Failure response.** If the boundary cannot be stated as a rule the launcher
could apply, C3's attack 7 is recorded as untestable with the reason, rather than
written as a test that passes because nothing was ever at risk.

**One thing the check turned up that C1 and C3 both need.** The signed
supply-chain policy is not a second copy of the containment. It mirrors four
rules — `runtime`, `network`, `read_only_rootfs`, `ephemeral_work_disk` — and
always has; the other seven, including all three numeric limits, `on_breach`,
`user` and now `credentials`, exist only in `REQUIRED_MICROVM_POLICY` and the
manifest. Nothing is wrong with that, and it is not changed here. It is written
down because the drift check between the two files can only ever guard the four,
so *"the signed policy still validates"* is not the same statement as *"the
containment is intact"*, and a launcher built by reading the signed policy would
enforce well under half of it.

**And a fourth partial copy, found while checking the third.**
`core/agentic_v2_microvm.py` reports `network`, `rootfs_mode` and `workdir` at
the top level of its readiness report, and writes them as the string literals
`"none"`, `"read-only"` and `"ephemeral-quota"`. It imports `canonical_sha256`
from the substrate and nothing else — not `REQUIRED_MICROVM_POLICY` — and
`validate_microvm_readiness_report` checks the report against the same literals
rather than against the rules. So three rules are stated a fourth time, by a
module that would go on stating them if the rules changed underneath it.

This is not currently a hole that hides anything: all three are among the four
the signed policy mirrors, so weakening one is still caught by
`containment_rules_that_disagree` — the stale report would appear beside a
failure rather than instead of one. It is left alone here because C0's scope is
a missing rule and not a drift surface, and because the fix belongs to the
module that will read the policy for real. **C1 imports
`REQUIRED_MICROVM_POLICY` and restates no value of it**, and takes this one with
it rather than adding a fifth.

**Cost.** None.

**Result — done, 2026-09-10.** `credentials: "none-inherited"` is the eleventh
key of `REQUIRED_MICROVM_POLICY` and the eleventh line of the manifest's
`microvm` block. Weakening it to `inherit-environment` or to a bare `"none"` is
refused, deleting it is refused, and the manifest-equals-policy check holds. On
this box the readiness report goes from 14 requirements to 15 and from 12
missing to 13, the new one reading *"the command's access to the tokens, keys
and environment the orchestrator holds is none-inherited — cannot be established
here"*, which is the same honest verdict the other ten get. 1,280 agentic tests
pass, 3 skipped.

**What checking it changed.** The plan said the launcher could lean on the
jailer, which "already clears inherited environment variables and file
descriptors before exec". The jailer documentation for v1.13.1 — the version
stage B found installed — says something narrower: it will *"cleanup all
environment variables received from the parent process"* but *"close all open
file descriptors … **except input, output and error**"*. Those three survive,
and are pointed at `/dev/null` only by the separate step that runs when the
launcher asks to daemonize. So the rule holds by default for the environment and
only conditionally for the descriptors; `--daemonize` moved from something the
launcher might pass to something C1 has to, and C3's attack on this rule checks
the descriptors rather than trusting the sentence. **A rule written down on the
strength of a mechanism that turns out to work differently is the same fault
this stage exists to fix**, arriving one layer down.

The same reading corrected a second thing C1 would have built on: the device
table below said four, and the fourth was `memory-hotplug`, which does not exist
in this Firecracker. No such key in v1.13.1's configuration fixture and no
occurrence of *hotplug* anywhere in its API specification. Balloon is the
runtime-memory mechanism, and the table had it twice under two names. Three
checks in this stage would have held against nothing — attack 7, the jailer's
descriptors, and this — and all three were found by reading the sources the plan
cites rather than the plan.

**What was deliberately not renumbered.** Three records still say six or nine:
`CHANGELOG.md`, `TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md` — which says it in five
places, all of them dated to the day the count was six — and the recorded Azure
finding, which describes a report pinned by its sha256 that did contain nine.
Only the last needed an as-of clause, because it sits in `core/` beside a report
a reader can run today and get ten from; the two dated documents are left
exactly as they are. The count moving is the thing those records exist to show.
The two rows of section 1 that stage B and C0 overtook on the same day say so in
the row rather than being rewritten, for the same reason: a table headed *"read
from the code on 2026-09-10"* cannot silently mean two different states of that
day.

##### C1 — the mapping, as data

**Builds.** `core/agentic_v2_microvm_launch.py`: a pure function from
`REQUIRED_MICROVM_POLICY` to the arguments `jailer` and `firecracker` are
actually given. It returns data and starts nothing, in the same spirit as
`agentic_v2_microvm.py`, which inspects and applies nothing, and
`agentic_v2_containment_readiness.py`, which judges and acts on nothing.

Each of the eleven policy keys maps to something a reader can point at:

| policy key | how it is applied |
|---|---|
| `runtime: firecracker` | the `--exec-file` the jailer launches |
| `network: none` | **no interface configured, and no `--netns`.** Firecracker's own fixtures write this as `"network-interfaces": []`, so the test asserts that no interface is configured rather than that a key is missing — an empty list and an absent key mean the same thing here and a test that only knows one of them is a test that can be walked around |
| `rootfs: read-only` | the root drive's `is_read_only: true` |
| `workdir: ephemeral-quota` + `workdir_quota_mib` | a second drive, a fresh image of exactly that many MiB, writable, destroyed after the run. `--resource-limit fsize=` bounds any single file as well, but the image size is what bounds the total |
| `memory_mib` | `machine-config.mem_size_mib` |
| `wall_clock_seconds` | a host-side deadline, since a guest cannot be trusted to time itself |
| `user: jailer-unprivileged` | `--uid`/`--gid` of a non-root user, and a refusal if either resolves to 0 |
| `credentials: none-inherited` (added in C0) | the jailer does most of it: for v1.13.1 it will "cleanup all environment variables received from the parent process" and "close all open file descriptors … **except input, output and error**". The environment half holds by default; the descriptor half leaves three open, and they are pointed at `/dev/null` only by the separate `--daemonize` step. So the launcher passes `--daemonize`, passes nothing of its own, and the test checks the descriptors rather than trusting the sentence. The two devices that would reopen the path, `mmds-config` and `vsock`, are covered in the table below |
| `on_breach: stop-and-report` | the launcher's error path returns the breached rule by name |
| `required: true` | any rule that cannot be expressed is a refusal to launch, never a silent drop |

**Three devices that are not in the policy and can each defeat a rule that is.**
Read off Firecracker's own configuration fixtures rather than assumed, and named
here because a launcher that sets every key in the table above and leaves these
at a default would enforce less than it appears to:

| device | which rule it defeats | required |
|---|---|---|
| `mmds-config` | `network: none`, by a route that is not a NIC — MMDS is a metadata service the *guest* reads over HTTP, and it is the standard way host-side data is handed to a guest | `null` |
| `vsock` | `network: none` — a host↔guest socket is a channel whether or not it is a NIC | `null` |
| `balloon` | `memory_mib` — a balloon device reshapes guest memory at runtime, and it is the only mechanism in this Firecracker that does | `null` |

**This table said four until C0 checked it, and the fourth was not real.** It
listed `memory-hotplug`, on the reasoning that memory added after boot is memory
the bound never saw. The reasoning is sound and the device is not: v1.13.1's
configuration fixture has no such key, and its API specification — 43 KB, every
route — contains no occurrence of *hotplug* at all. The routes are `/balloon`,
`/boot-source`, `/cpu-config`, `/drives`, `/entropy`, `/logger`,
`/machine-config`, `/metrics`, `/mmds`, `/mmds/config`, `/network-interfaces`,
`/snapshot/create`, `/snapshot/load`, `/vsock`, `/vm`, `/vm/config`, `/actions`
and `/version`. Balloon **is** the runtime-memory mechanism here; the table had
it twice under two names. A test pinning `memory-hotplug: null` would have
asserted something about a key Firecracker never emits and passed for that
reason — the third time in this stage that a check would have held against
nothing.

**And one route that is not a device.** `/snapshot/load` restores a machine
whose configuration was decided elsewhere: a snapshot can carry a NIC, a vsock
or a different memory size, none of which the launcher's own arguments would
show. It is not in the table because it is not a setting to pin at `null` — it
is a way in that bypasses the table entirely, so C1's builder emits no snapshot
route and C3 treats loading one as an escape rather than a configuration.

These get tests of their own in C1, on the same footing as the policy keys. The
policy is not amended to add them: they are not rules about what the containment
allows, they are devices that must be absent for the rules it already has to
mean what they say. If that reasoning is wrong, the fix is to add them to
`REQUIRED_MICROVM_POLICY` in a change of their own, not to quietly rely on a
default.

Three further flags are passed because leaving them off would weaken the
boundary the policy describes even though no key names them: `--new-pid-ns`, so
the guest process is not in the host's PID namespace, `--cgroup` for the
host-side memory bound that sits underneath the guest-visible one, and
`--daemonize`, which is what closes the three descriptors the jailer's own
cleanup step leaves open — see the credential row above.

`--daemonize` has a consequence worth stating before it is discovered as a bug:
it points Firecracker's standard output at `/dev/null`, so console output is
gone unless the launcher asks for a log path. That is acceptable here only
because it is not where results come from — deliverables are collected off the
ephemeral work disk, which the `workdir` rule already governs.

> **Correction, made while building C1.** This paragraph used to go on to say
> that `--daemonize` "pairs with `--new-pid-ns`, which is what writes the child's
> PID to a file". That is wrong, and it is the kind of wrong that would have been
> found by a launcher that omitted `--new-pid-ns` and then could not understand
> why the PID file was there anyway. `src/jailer/src/env.rs:735-740` in v1.13.1
> writes the PID file in **both** branches; `save_exec_file_pid` runs after
> `chroot()`, so the file lands inside the jail, which is `<chroot_dir>` seen
> from the host. What `--new-pid-ns` buys is the namespace and nothing else.
> Both flags are still passed, for the two separate reasons above; only the
> explanation was wrong.
>
> **And the correction found a bug in C1's own code**, which is why it is worth
> writing down rather than just fixing. The file is named after the **exec
> file**, not after the word: `save_exec_file_pid` appends `.pid` to
> `chroot_exec_file`, which is `/` joined to the binary's own name. The jailer
> requires that name to *contain* `firecracker`, not to be it — so
> `/opt/firecracker-v1.13.1` writes `/firecracker-v1.13.1.pid`. C1 had the path
> hard-coded as `/firecracker.pid`, and on any host where the binary carries a
> version suffix the plan would have named a file that never appears. Nothing
> would have failed: the deadline would have been recorded, the plan would have
> hashed, and `wall_clock_seconds` would have had nothing to act on at the
> moment it was needed. It is derived from the binary now, and the test asserts
> it against a versioned name rather than against the constant.
>
> Which PID is in the file is worth knowing too, before somebody removes a flag.
> With `--new-pid-ns` the jailer clones and records the **child's** PID, which is
> Firecracker. Without it, and with `--daemonize`, it records the daemonised
> grandchild's. Both are the right process to signal, by different routes.

**A fourth flag, and it is stronger than this plan first had it.** The section
below says C1's builder "emits no snapshot route". That is true and it is not
enough. Pinning a device in a configuration file is a statement about start-up;
with the API socket live it says nothing about the rest of the run. In v1.13.1
(`src/firecracker/src/main.rs:198-205`) `--no-api` takes no value and requires
`--config-file`, and `api_enabled` is simply its absence. Without it, every
device pinned out above — `balloon`, `vsock`, `mmds-config` — can be added back
after boot over the socket, and `/snapshot/load` can bring in a machine whose
configuration was decided somewhere else entirely. `--no-api` is what makes the
configuration file the whole of what the machine will ever be, so it is passed
and asserted alongside the three above.

**And a third, which is a default that would quietly be wrong here.**
`--cgroup-version` defaults to `1` in the jailer's own documentation, while
Ubuntu has defaulted to the cgroup **v2** unified hierarchy since 21.10 and the
host stage B measured runs 24.04. A launcher that passes `--cgroup` and leaves
the version at its default would be writing to a hierarchy that is not the one
in use — a memory bound that does not apply, on a host where nothing would
announce that it had not. So the version is passed explicitly and asserted,
rather than inherited. This is the failure mode the whole stage is about,
arriving through a default instead of through a deletion: **a rule that reads as
enforced and is not.**

The v2 part is a fact about the distribution, not a reading taken from that
machine — stage B measured the processor, `/dev/kvm`, the kernel and the two
programs, and not this. C2 reads it off the host as its first action, before
anything is launched, and the plan says so here rather than letting a reasonable
inference be mistaken later for a measurement.

Every flag named above was checked against the jailer documentation for
**v1.13.1**, which is the version stage B found installed — not against the
current development branch, where a flag can exist that the deployed binary does
not have. `--cgroup-version` is in v1.13.1 and defaults to `1` there.

**Where the kernel and rootfs come from is already decided, and C1 does not get
to decide it again.** `inspect_microvm_readiness` takes `asset_paths` for
`kernel` and `rootfs`, hashes both, and only reports `ready_for_boot_test` when
they and the three host checks are all present. The launcher takes its images
from the same paths and reuses those hashes rather than computing its own, so
there is one answer to "which kernel booted" instead of two that can disagree.
Nothing in this seam touches `foundation_only` or `production_activation`: both
are pinned inside the readiness report's own validation, which is where they
should stay.

**One thing to state plainly rather than discover halfway through.** Firecracker's
jailer runs as root — its own documentation says so — because building the jail
requires `mknod`, `pivot_root` and cgroup writes. It drops to `--uid`/`--gid`
immediately before exec'ing Firecracker. So `user: jailer-unprivileged` is a
statement about the process that runs the model's command, which is unprivileged,
and not about the jailer that built the jail around it. That is the documented
design of the mechanism, not a shortcut taken to make something pass, and it is
written here so that nobody reads the root in `ps` later as a rule quietly
dropped. What stays forbidden is unchanged: no root for the model's command, no
`--privileged`, no capability added to make a test pass.

**Exit condition.** Every key above has a test that reads the built arguments
and fails if the rule is missing, plus one test that removes a key from a copy
of the policy and requires the builder to refuse rather than emit arguments
without it. **A rule the builder cannot express must fail loudly**; a builder
that quietly emits every rule but one is exactly the "written down but
unenforced" state stage C exists to end.

**Failure response.** If a rule turns out not to be expressible in Firecracker's
configuration, it is recorded as such and raised — not dropped, not softened to
a comment, and not moved to a later stage to be forgotten in.

**Cost.** None. This runs on any machine, including this one.

**Done.** `core/agentic_v2_microvm_launch.py` and its 83 tests. The exit
condition is met in both directions: every rule has a test that reads the built
arguments, every rule has a case that deletes it from a copy of the policy and
requires a refusal naming it, and a weakened value is refused rather than
adapted to. The guards were checked by mutation rather than by their passing —
fifteen deliberate breakages of the builder (the flag dropped, the host memory
bound lowered to the guest's, the v1 cgroup file name used under v2, the root
drive made writable, the in-jail config path turned into a host path) and each
one had to fail a test before the work was called done. Three of the fifteen
initially did not, and all three were holes in the tests rather than in the
builder: `fsize=` was asserted as a string anywhere in the argument list, so
deleting the `--resource-limit` that carries it changed nothing; the in-jail
paths were asserted against their own constants, so moving a constant to a host
path took the test with it; and the PID file was asserted against the constant
that turned out to be wrong, so it agreed with the bug instead of catching it.
All three now assert the requirement instead of the spelling. The last surviving
mutation was the builder's own backstop — the check that every accepted rule
reached `rules_applied` — which no healthy build exercises; it now has a test
that stages the drop.

Four things the building of it settled, recorded here because they are not
visible in the diff:

- **The vCPU gap is real and is left open on purpose.** Firecracker requires
  `vcpu_count` and the policy has no rule about processor share, so the builder
  takes the number from its caller and says so rather than inventing a bound.
  Closing it means adding a rule to `REQUIRED_MICROVM_POLICY` in a change of its
  own, the way the credential rule was added — not a default picked in a
  launcher.
- **`/dev/net/tun` is inside the jail whatever the policy says.** The jailer
  `mknod`s it unconditionally, along with `/dev/kvm` and `/dev/urandom`. So
  `network: none` rests on no interface being configured and on `--netns` being
  absent, not on the device being unavailable. Stage C3 attacks that, and should
  not be surprised to find the node there.
- **The host-side memory bound is deliberately larger than the guest's.**
  `HOST_SIDE_MEMORY_OVERHEAD_MIB = 256`, picked rather than derived and named as
  picked. A host bound equal to the guest bound would kill the monitor rather
  than the command that went over, which is a containment that stops the wrong
  process and reports the wrong thing.
- **The readiness report gained a fourth field, and it is not an input to the
  third.** `every_rule_has_an_argument_that_would_apply_it` is derived from the
  builder against the policy. `anything_applies_the_containment_rules` stays
  `False`, because a rule is applied by starting a machine with it and this
  builder starts nothing. Wiring the new field into
  `available_on_any_machine_in_play` would have made the report announce the
  containment as in place on the strength of code that has never booted
  anything — the exact failure the readiness module exists to prevent, arriving
  through good news instead of through a deletion.

  Reading the generated report afterwards caught the same fault in the other
  direction. The recorded azure finding ended by saying
  no code turns the policy into launch arguments — true when it was measured,
  false the moment this module merged — so the printed report asserted both
  halves of a contradiction three lines apart, and **nothing failed**, because a
  finding is a frozen string and no test compared it against the live answer. A
  finding may no longer name `REQUIRED_MICROVM_POLICY` or the launch module at
  all: whether anything applies the rules is a property of this repository, it
  changes without any machine changing, and there is already a section that
  answers it live. Enforced for every finding rather than for the one that went
  stale.

##### C2 — the first boot, on the machine stage B measured

**Builds.** The thin spawn that C1 deliberately left out, and one command run
inside the guest whose output comes back.

**Why it is separate.** This box runs kernel 3.10 and cannot boot a Firecracker
machine at all. Claiming otherwise is the specific dishonesty the instruction
names. So C1's mapping is tested here and C2's boot is tested only on the Azure
host, and the two are not allowed to be confused for one another.

**Exit condition.** A guest boots under `jailer`, a command runs inside it, its
output and exit status come back, and the machine is gone afterwards with its
workdir image destroyed. The artefact records the kernel and rootfs images used
and their hashes.

**Where the guest's contents come from, which is an open question and not a
detail.** `security/agentic-v2-supply-chain-policy.json` governs what may run
inside V2: `cosign-offline-v1` signatures with a trusted key and a bundle
required, `buildkit-max-v1` provenance, CVE scanning against a database no more
than seven days old, and unknown licences treated as failures. Every one of
those is written for an **OCI image**. Its `required_evidence` list names
`oci_layout`, and its provenance subjects include `dockerfile`. A Firecracker
guest needs a `vmlinux` and an ext4 root filesystem, and neither is an OCI image,
so none of those rules reaches them as written — not because the policy is weak
but because it is about a different kind of artefact. A guest built beside the
image could not produce the evidence the policy asks for even if someone wanted
it to.

The answer that keeps the chain intact is to build the rootfs *from* the image
the policy already governs, so what boots is what was signed, scanned and
attested, rather than a second filesystem assembled beside it. That path exists
rather than being hoped for: `core/agentic_v2_oci.py` already verifies a local
OCI layout blob by blob, and its layers are
`application/vnd.oci.image.layer.v1.tar`, so a rootfs is verified layers
unpacked in order into a filesystem image. The kernel has no such parent: a
`vmlinux` has to come from somewhere, and the practical source is Firecracker's
own published kernels, pinned by hash.

So C2 records the kernel as an input whose provenance is **weaker than the OCI
chain's**, and says so in those words rather than listing a hash and letting the
reader assume it was signed. If that is not acceptable, the response is to build
the kernel too and record how — not to proceed and leave the gap unnamed. Either
way `foundation_only` and `production_activation: disabled` are untouched here.

**Failure response.** If it will not boot, stage C stops at C2 with a recorded
reason. `exec_run` stays shut. There is no fallback to the V1 Docker runner and
no describing a weaker boundary as this one.

**Cost.** The dev host, allocated for the length of the test and deallocated
immediately after, on the same terms as stage B: measured minutes, price
`partial` if the rate is not established.

###### C2's inputs, measured and decided before any of it was written

The plan above leaves four things open. Each is settled here, with the reading
it was settled from, so that none of them arrives as an implicit choice inside
the code.

**The host, re-read rather than remembered.** Allocated 2026-09-10T19:33Z and
measured through `az vm run-command` — no inbound port, no session, the same
control-plane path stage B used. `cgroup2fs`, `cgroup.controllers` present:
the hierarchy is **v2**, so the memory bound is `memory.max` and
`--cgroup-version 2` is passed explicitly. That is the exact failure
:data:`CGROUP_MEMORY_FILE_BY_VERSION` was written against, and it is now a
reading rather than an assumption. `/dev/kvm` is present, the processor reports
`svm`, there are 8 processors and 122 GiB free, and `firecracker` and `jailer`
are both v1.13.1 at `/usr/local/bin` — they survived the deallocation because
stage B installed them onto the disk, which is kept.

Two readings contradict what was expected. **Docker is not installed**, so the
rootfs cannot be produced by a daemon pulling an image; the registry is spoken
to directly instead, which is a better fit for a chain that is about digests.
And **uid 1000 (`gdpval`) is in the `sudo` group**, so it is not the
unprivileged account rule `user` asks for. C2 creates a dedicated account with
no password, no login shell and no group beyond its own, and jails to that.
Reusing an account that can become root would leave the host-side process one
`sudo` away from the thing the rule exists to prevent, and the rule would still
have read as met.

**Which rootfs boots, since no candidate digest exists.** The professional-work
candidate has never been built, so there is no digest for it anywhere in the
repository — C2 does not invent one and does not build one as a side quest.
It boots the **parent**, `ghcr.io/hyeonsangjeon/gdpval-sandbox`, pinned by the
digest `batch-runner/sandbox/v2/parent.lock.json` already records. That lock
pins the multi-architecture *index*; the artefact additionally records the
`linux/amd64` manifest digest that index resolved to, because the index digest
alone does not say which of its children was unpacked. The image is public: an
anonymous pull token fetches the manifest, so no credential is issued and none
is needed. **What boots in C2 is therefore the signed, scanned parent and not
the candidate D will need**, and the artefact says so in those words.

**The kernel, and exactly how its provenance is weaker.** Pinned to the one key
`firecracker-ci/v1.13/x86_64/vmlinux-6.1.141` in bucket `spec.ccfc.min`,
41,865,904 bytes, published 2025-08-12 — one exact key, not the discovery logic
upstream's getting-started uses, which resolves `sort -V | tail -1` against a
listing fetched over plain `http` and would let the guest kernel change
underneath the containment tests without anything saying so. Three disclosures
travel with it, and they are the content of "weaker than the OCI chain's":

1. **Upstream publishes no checksum and no signature for these artifacts.**
   Its documented verification step prints filenames. The bucket's ETag is a
   multipart tag (`…-5`) and is not a content hash of the object. So the hash
   in the artefact is one **we** computed on download and enforce thereafter.
   It proves the file did not change between our download and this boot. It
   does not mean anybody vouched for the file, and the artefact must not be
   read as if a signature had been checked.
2. `docs/kernel-policy.md` at the v1.13.1 tag validates exactly two guest
   kernels, v5.10 and v6.1. **v6.1's minimum end-of-support date is
   2026-09-02, which is eight days before this run.** 6.1.141 is used anyway,
   knowingly, and recorded as lapsed rather than pinned in silence. The
   alternative on that page, v5.10, expired in 2024 and is worse.
3. The rootfs does **not** come from upstream's path. Upstream builds one from
   an Ubuntu squashfs with `sudo mkfs.ext4 -d squashfs-root`; C2 builds it from
   the verified OCI layers instead, which is the whole point of having the
   chain. Only the kernel comes from the bucket.

**How a command gets in and its result gets out — one channel, not two.**
`REQUIRED_MICROVM_POLICY` says `network: none`, and
:data:`DEVICES_THAT_MUST_BE_ABSENT` rules out `vsock` for the same reason — a
host-to-guest socket is a channel whether or not it is an interface. The first
draft of this section named the serial console as a second channel and **that
was wrong**: C1 passes `--daemonize`, which is what points the three standard
descriptors at `/dev/null`, and its own docstring already says so — "that is
acceptable only because it is not where results come from". No `logger` section
is written into the configuration either. So Firecracker's stdout goes nowhere
and there is no console to read.

That leaves exactly one channel, which is the one the policy already names.
The **work disk** carries the command in and the results out: `/in/command.sh`
going in, `/out/stdout`, `/out/stderr` and `/out/exit_status` coming back. It
is read with `debugfs`, which walks the ext4 image directly — nothing is
mounted, no loop device is attached, and no privilege is needed to take a file
out of it. The rootfs is read-only, so the guest is given one added file,
`/gdpval-init`, whose whole text and hash go into the artefact; everything else
is the image's own layers unpacked in order.

**One consequence worth naming: a failure to boot is nearly silent.** With no
console and no network, a guest that panics leaves an empty work disk and
nothing else, which is the same evidence as a guest that booted and wrote
nothing. So C2 also does a **separate, deliberately unjailed** Firecracker run
of the same kernel and rootfs with the console attached, before the jailed one,
and records it as `unjailed_image_check`. It proves the two images boot and
nothing more — it is **not** the contained run, it does not count towards the
exit condition, and it is labelled that way in the artefact so no reader can
mistake the weaker boundary for this one. If it were allowed to substitute for
the jailed run, that would be the exact dishonesty this stage forbids.

**Where root is used, stated plainly so it is not mistaken for an escalation.**
`jailer` must start as root: building the chroot means `mknod` for `/dev/kvm`,
`chown` to the jailed account, `chroot` and then `setuid`. Dropping privilege
is the thing it is *for*, and the run-command channel already arrives as root.
So root starts the jailer and the jailer drops. Nothing else runs as root,
**no `--privileged`, no added capability, no sysctl changed, no host security
setting turned off, no guard removed and `exec_run` untouched** — that list is
stage C's own, and C2 does not spend any of it. In particular
`kernel.apparmor_restrict_unprivileged_userns` reads `1` on this host and stays
`1`; it constrains bubblewrap, which is A's Codex path, and Firecracker does
not depend on it.

**When it stops.** `wall_clock_seconds` has no jailer flag behind it — the
launcher enforces it by watching for the PID file C1 derives from the binary's
own name and killing the process when the deadline passes. C2 exercises that,
because a deadline that has never fired is a deadline nobody has tested.

**What C2 is still not.** Booting a guest and getting one command's output back
is not `exec_run`, not a model call, and not a task. `foundation_only` and
`production_activation: disabled` are untouched, and the answer to
`anything_applies_the_containment_rules` is expected to stay `false` until a
caller actually runs these arguments in the product path, which is stage D.

###### C2 ran, and this is what came back

Two runs on `gdpval-devhost-vm`, both through `az vm run-command invoke` — no
public IP, no inbound rule, no SSH, no new access of any kind. The host is
`6.17.0-1022-azure`, 8 processors, KVM present, **cgroup v2** by the evidence
`/sys/fs/cgroup/cgroup.controllers` exists, running `Firecracker v1.13.1` and
`Jailer v1.13.1` at `/usr/local/bin/`. The jail account is `gdpvaljail`,
uid 999, gid 988, shell `/usr/sbin/nologin`, `groups_beyond_its_own: []`.

**Run 1 refused the real image, and the refusal was the bug.** It stopped at the
first member of the first layer: `layer sha256:68629629… contains '.', which
points outside the filesystem it describes`. The check was written with
`member.name.lstrip("./")`, and `str.lstrip` takes a *set of characters* rather
than a prefix. So `"."` became `""` and was read as an escape, while `"../x"`
became `"x"` and `"/etc/shadow"` became `"etc/shadow"` — the two members the
check existed to stop were the two it let through. Rewritten around
`os.path.normpath`, with a refusal for members written through a symlinked
parent and for hardlinks naming something outside the image, both of which the
first version also missed. Fixing it surfaced a second defect that had nothing
to do with the first: the boot arguments carried no `init=`, so the guest would
have fallen through to `/bin/sh` on a console `--daemonize` had already pointed
at `/dev/null` — a machine that boots, runs nothing, writes nothing, and waits
out the full 1,200 seconds, which is the failure hardest to tell from a broken
image.

**Run 2 booted.** `outcome: booted`, `exit_status: 0`, `ran_for_seconds: 1.269`
against a 1,200 s bound, `jailer` returncode 0 with empty stderr, PID file
present, and `teardown.all_gone: true`. The whole run took 475.6 s wall clock
including both image builds, from `2026-09-10T19:57:42Z` to `20:05:37Z`.

Off the work disk — the only channel, since there is no network, `vsock` is
pinned absent, and the console goes to `/dev/null`:

```
/out/guest_kernel          6.1.141
/out/guest_uid             0
/out/init_reached_the_end  done
/out/exit_status           0
/out/stdout                this ran inside the guest
                           python answered 4
                           0
                           /dev/vda on / type ext4 (ro,relatime)
                           rootfs refused a write, as the rule says it must
```

**What was booted, fixed by hash.** The kernel is
`firecracker-ci/v1.13/x86_64/vmlinux-6.1.141`, 41,865,904 bytes, sha256
`b36a4a1b10f33b9cfdcde3d1a787d9c090556a3edb211cd06d1f3f9a6c7e8724`. That digest
was **computed here on download**. Upstream publishes neither a checksum nor a
signature for it, the bucket listing is plain HTTP, and the S3 ETag is a
multipart tag rather than a content hash — so this figure shows the file did not
change between download and boot, and nothing more. It is not a provider
signature and is not recorded as one. Its minimum end-of-support date is
`2026-09-02`, which has passed; the pin carries `support_window_has_lapsed:
true` rather than being quiet about it.

The rootfs was built from `ghcr.io/hyeonsangjeon/gdpval-sandbox` pinned at index
`sha256:ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5bd24edb`,
which resolved to manifest
`sha256:91b524c7dc8f21d653f829d19a283ea269a36cc85e0569ca38c85bfac92d0fe2` for
`linux/amd64` — the index digest is the reproducible pin, but it cannot say
which child booted, so both are recorded. Ten layers, each checked against its
own digest, applied in order: 119,175 entries written, 78 whiteouts honoured,
12,709 directory modes widened during the unpack and restored afterwards. The
extraction filter was `tar`, which clears setuid, setgid and sticky bits, so the
tree is not byte-for-byte the image's own permissions and the artefact says so.
Result: `rootfs.ext4`, 8,714 MiB, sha256 `489188004ad4eb8a…`; work disk 256 MiB,
sha256 `111ad3b79c44db73…`; guest init at `/gdpval-init`, sha256
`191ccbb58fc6b1ed…`. Both images were built with `mke2fs -d` and read back with
`debugfs` — nothing mounted, no loop device, and the host kernel's ext4 driver
never touched a filesystem the guest had been writing.

**The deadline fired.** A second machine ran a command that never finishes:
`stopped_by_the_deadline: true` at 45.042 s, `chroot_destroyed: true`. It used
45 s rather than 1,200 s, and the artefact carries
`policy_used_is_not_the_required_one: true` next to that number. The bound was
not relaxed to get the result — the same builder was handed a different policy
dictionary, and that builder still refuses a policy with a missing rule, an
unknown rule, or a rule it cannot reach. What this shows is that the launcher's
enforcement path works, on a bound short enough to watch.

**Attack 5 answered early, by accident.** `/dev/vda on / type ext4
(ro,relatime)` and a refused write are the read-only-root rule holding, observed
in the C2 boot before C3 was written. It is recorded here because it happened
here, and C3 will still run it as an attack rather than cite this line — one
observation inside a friendly command is not the same as a probe that was trying.

##### C3 — the seven attacks

**Builds.** `tests/test_agentic_v2_containment_rules.py` gains the test its own
docstring currently declines to fake. Each attack starts a machine, exceeds one
rule, and requires the machine to stop it:

1. write past the 256 MiB workdir quota
2. allocate past 4,096 MiB
3. run past 1,200 seconds
4. open a network connection
5. write to the read-only root
6. run as a privileged user
7. read a token, key or environment secret the orchestrator holds — against the
   rule C0 adds, not against an expectation held only in this list. Tested in
   both halves, because the jailer covers them differently: the environment is
   wiped unconditionally, the three standard descriptors only by `--daemonize`.
   An attack that checks the environment alone would pass on a launcher that had
   dropped that flag

**Exit condition.** All seven are stopped, and each stop names the rule it
enforced. Seven passes is the condition — not six and a note.

**Failure response.** Any attack that succeeds is an escape. It is recorded with
the exact path it took, `exec_run` stays shut, and stage C does not advance.
**No attack is downgraded to a warning and no rule is relaxed to make its test
pass** — a rule the launcher does not enforce is a rule that does not exist.

**What is not built anywhere in stage C.** Nothing that runs as root, no
`--privileged`, no capability added to make a test pass, no host security
setting turned off, no guard removed, and no opening of `exec_run` — that is
stage D and gets its own change. If the containment cannot be demonstrated, the
honest outcome is that commands do not run, and stage C is allowed to return
that.

**Not yet run.**

###### C3 ran, and all seven were stopped

Two runs on `gdpval-devhost-vm`. The second is the record; the first is why the
second exists.

**Run 2 — 2026-09-10T20:36:02Z → 20:40:01Z, 239.2 s, `outcome: all_seven_stopped`.**
Seven of seven, no escapes.

| # | attack | rule | what stopped it |
|---|---|---|---|
| 1 | write 512 MiB into the work disk | `workdir_quota_mib: 256` | the write past the quota failed, `rc=1` |
| 2 | hold 6,144 MiB in a 4,096 MiB machine | `memory_mib: 4096` | guest sees 3,942 MiB; the allocator reached 3,776 MiB and the kernel took it, `rc=137` |
| 3 | never finish | `wall_clock_seconds` | stopped at 45.042 s against a 45 s bound, chroot gone |
| 4 | find an interface and use it | `network: none` | only `lo` in `/proc/net/dev`; `connect_probe=refused:OSError` |
| 5 | write to `/` | `rootfs: read-only` | write refused **and** `/dev/root / ext4 ro,relatime` |
| 6 | keep root on the host | `user: jailer-unprivileged` | the Firecracker process runs as uid 999, no supplementary groups |
| 7 | reach a token the orchestrator holds | `credentials: none-inherited` | 0 environment entries, none of the canaries, 28 descriptors reaching nothing of ours, all three standard ones `/dev/null`, guest environment clean |

The images were checked against C2's record before anything booted:
`matches_the_guest_c2_booted: true`, kernel `b36a4a1b…`, rootfs `489188004ad4eb8a…`.
These are seven verdicts about the machine whose boot C2 recorded, not about a
rebuild that happens to be similar. Host unchanged: Firecracker/Jailer v1.13.1,
`6.17.0-1022-azure`, cgroup v2, KVM present, 8 processors. Jail account
`gdpvaljail` uid 999 gid 988 `/usr/sbin/nologin`, no groups beyond its own.

Four boots, each with its plan and work disk pinned:

| boot | outcome | ran | plan sha256 | policy is the required one |
|---|---|---|---|---|
| `probes` | booted, exit 0 | 9.272 s | `f79f1fe7…` | yes (`wall_clock_seconds: 1200`) |
| `workdir-quota` | booted, exit 0 | 1.518 s | `d9e43128…` | yes |
| `memory` | booted, exit 0 | 4.020 s | `6e342ead…` | yes |
| `wall-clock` | stopped by the deadline | 45.042 s | `d3aef11c…` | **no — 45 s, recorded as such** |

The deadline was tested against a shortened bound so the stop could be watched
inside a run. That was done by handing `build_launch_plan` a different policy
dict — an argument it already takes, and one it still refuses if a rule is
missing, unknown or out of reach — and the artefact carries
`policy_is_the_required_one: false` for that boot alone. Attack 3 demonstrates
that the deadline fires and tears the chroot down. **It does not demonstrate
1,200 seconds**, and nothing here should be read as if it did.

Attacks 6 and 7 were read from `/proc/1979` while the machine was alive, because
neither is visible from inside it: PID 1 in that guest was uid 0, as it is in
every guest here including the ones that pass. The probe boot now holds itself
open for 8 s so the read can land — C2's guest was gone in 1.269 s, which is not
reliably long enough.

Both artefacts are committed unedited beside this document —
`c2_first_boot.json` and `c3_attacks.json`. Everything above is a reading of
them, and a reading nobody can check is worth less than the thing it reads,
particularly once the host it was written on is deallocated.

###### Seven attacks, eleven rules — what the other four are

`REQUIRED_MICROVM_POLICY` has eleven keys and seven of them were attacked. **7/7
is not 11/11**, and the difference is not an oversight to be quietly carried:

| key | why there is no attack |
|---|---|
| `required: true` | a flag saying the policy applies, not a boundary a guest can push on |
| `runtime: firecracker` | demonstrated by the boots themselves — Firecracker v1.13.1 is what ran them, recorded per boot with the plan's sha256 |
| `on_breach: stop-and-report` | this *is* attack 3's outcome: the deadline stopped the machine and the artefact reported it |
| `workdir: ephemeral-quota` | the `quota` half is attack 1. The **`ephemeral` half is not attacked.** |

The last one is the real gap and it is named here rather than folded into the
seven. Every boot ended with `teardown.all_gone: true` and every boot was handed
a freshly built work disk, so nothing observed contradicts it — but that is the
*runner* being careful, not the machine refusing. A guest cannot make its own
disk survive; only the code that hands out disks can fail to replace one.

So it is not a microVM property and does not belong among attacks on microVM
rules. **It becomes stage D's problem the moment one machine per task starts
reusing this machinery**, because the failure it guards against is one task's
data reaching the next, and that failure would be silent. Stage D carries it.

###### Run 1 came back six of seven, and the seventh was the attack, not the rule

**2026-09-10T20:0x, `outcome: escaped`, `escapes: ['memory']`.** The verdict was
*"the allocation probe did not report, so it did not run"* — correct on the
evidence, and the wrong conclusion about the machine. `/out/stderr` held
`Killed`; `/out/stdout` stopped after `MemTotal`. The bound had held. The attack
destroyed the evidence proving it.

Two causes, both in the attack:

- **The allocation went into a tmpfs.** Those pages are shmem and are charged to
  no process's RSS, so when the machine filled, `oom_badness` had nothing large
  to weigh and the kernel took a bystander.
- **The reporter was that bystander.** `rc=$?` inside a command substitution runs
  in a fork; the fork died holding the exit status.

It is now anonymous memory, written to a page at a time — `bytearray(n)` is
`calloc`, and `calloc` over a fresh mapping is a promise of zeroes rather than
pages, so untouched it would have taken address space and never reached the
bound. The report is made by the top-level shell, which allocates nothing and is
never a candidate. The allocator prints its high-water mark as it goes, because a
process the kernel kills does not reach its last line.

That mark is now the primary check: **holding more than `memory_mib` is an escape
whatever the exit status says**, since a guest with no swap cannot give back
anonymous memory it has touched. A machine that handed over every requested byte
and then failed on the way out would have passed on the exit status alone.

**The judge was not loosened to reach seven.** `Killed` in `/out/stderr` is real
evidence the bound held, and it is still not accepted, because it does not say
*which* process was killed — and accepting it would be reading a bystander's
death as containment. The first run's six-of-seven stands in the record as a
failed run.

###### The host is stopped, and this is what it ran for

C2 and C3 were the only work scheduled on `gdpval-devhost-vm`, and both are done,
so it is deallocated. Idleness was checked before stopping it rather than
assumed: nobody logged in, no `firecracker` or `jailer` process, nothing outside
kernel threads.

| | |
|---|---|
| Started | `2026-09-10T19:33:33.115Z` requested, `19:34:03.528Z` succeeded |
| Deallocated | `2026-09-10T20:52:57.917Z` requested, `20:53:10.886Z` succeeded |
| Outer window | **4,777.8 s — 79.63 min — 1.3272 h** |
| Size / region | `Standard_D8as_v5`, `koreacentral` |
| Published Linux rate | 0.424 USD/h pay-as-you-go, from the public retail price API |
| Rate × window | 0.5627 USD |
| Price status | **`partial`** |

The two timestamps come from the subscription's own activity log, so the
**duration is measured, not estimated**. The dollar figure is not. 0.424 USD/h is
the *published list rate* for this size in this region; what the subscription is
actually billed depends on agreement terms this session cannot read. So the
arithmetic is recorded as arithmetic and the price stays `partial`.

**`partial` is not zero.** Something was spent for 79.63 minutes of an 8-vCPU
machine, and the number simply is not verifiable from here.

Two smaller things worth keeping:

- **`az monitor activity-log` does not run on this box** — the installed CLI
  raises `TypeError: ord() expected string of length 1, but int found` out of a
  bundled antlr4 that disagrees with its own generated lexer. That is a local
  packaging fault, not an access one; the same query answers through
  `az rest` against `Microsoft.Insights/eventtypes/management/values`.
- **The artefacts survive the deallocation.** They are on `/var/tmp`, which on
  this VM is the OS disk, and both are committed to the repository anyway.

### Stage D — not yet run

#### The plan, written before any of it is built

Stage C proved a machine that boots with the rules applied and stops seven ways
of getting out of them. What it did **not** build is the thing on the other side
of the tool contract. The gap is worth naming precisely, because it is not
"wire two finished pieces together".

**C boots a machine to run one command and then destroys it.** The tool
contract's `exec_run` is a call made repeatedly inside a session that holds
state: the model writes a file with `workspace_apply`, runs something with
`exec_run`, reads what came out, and runs something else. Between those calls
the workspace has to still be there. A one-shot boot has nowhere to keep it.

##### One machine per call, not one machine per session

Two ways to close that gap, and the choice matters enough to write down.

**A long-lived machine per task.** Boot once when the session starts, keep it
running, send each `exec_run` to an agent inside it over vsock, tear it down at
`finalize`. Fewer boots, so less latency per call. It needs a guest agent, a
channel protocol, and a way to bound a call without killing the machine — none
of which stage C looked at, so none of which has evidence behind it.

**A fresh machine per call, with the work disk carried across.** The workspace
lives on the host between calls. Each `exec_run` builds a work disk out of it,
boots, runs, and the machine is destroyed; the results and the changed workspace
are read back out of the disk image afterwards. **This is exactly the sequence
stage C measured** — `build_launch_plan`, boot, collect, teardown with
`all_gone: true` — repeated.

**Taking the second.** The cost is real: C2's guest ran for 1.269 s but the
orchestration around it is seconds, and 220 tasks at ten calls each is thousands
of boots. That is hours, and it is affordable. What is bought for it is that
every `exec_run` inherits stage C's evidence instead of needing its own, and
that nothing whatever survives a call except a disk image the host controls —
so a call that gets compromised has no resident machine to stay in.

This does not weaken `workdir: ephemeral`. Carrying the disk between calls
*within* one task is the workspace working; what `ephemeral` forbids is carrying
it between tasks. That is a runner property, and stage E is where it is kept.

##### What gets built, and in what order

**D1 — the pure part, testable on a box that cannot boot.** A module that turns
a validated `exec_run` request into the guest command, and turns what a boot
returned into the tool contract's result. No subprocess, no Firecracker, no
network. Same shape as C3: pure data and pure judging, with the boot injected.

**D2 — the backend.** A real `AgenticV2Backend` whose `workspace_apply` reads
and writes a host-side session directory, whose `exec_run` calls D1 and boots,
and whose `finalize` collects the produced files with their hashes. Guards
untouched.

**D3 — the model's voice.** `real_model_voice` currently refuses, and its stated
reason — *"reaching one costs money that has not been approved"* — **is now out
of date**, because the calls have been approved. It will keep refusing, on the
reason that is still true, and the docstring gets corrected rather than quietly
left saying something false.

**D4 — the guards, each in its own change.** Only after D1–D3 exist, run, and
have artefacts. Nothing is flipped before then.

##### The one judging rule that decides whether any of this is honest

A guest that panicked on boot and a guest whose command returned 0 leave
**different** evidence, and the difference is the whole thing:

- `/out/exit_status` **present** — the command ran and this is its returncode,
  whatever the number is. A non-zero returncode is a *successful tool call*
  reporting a failed command, and the model is shown it.
- `/out/exit_status` **absent** — the command did not run to completion, and
  there is no returncode to report. This is `compute_backend_error`. It is
  **never** `returncode: 0`, and never a made-up non-zero either.

Getting this backwards is how a run of 220 tasks reports a wall of clean
failures that were really a broken launcher. Stage C's first run was this exact
mistake in the other direction, and the discipline is the same: **absent
evidence is not a result.**

##### The bound a model asks for, and the bound it gets

`exec_run`'s schema allows `timeout_seconds` up to 2700. The containment policy
allows 1200. A model asking for more than the policy permits is not an error and
is not a refusal — it gets the policy's bound, and **the result says which
number was actually applied**, so nobody later reads a 1200 s kill as the model's
own 2700 s choice having been honoured.

##### D1 — the pure part, built and green

`core/agentic_v2_exec_boot.py` and `tests/test_agentic_v2_exec_boot.py`.
**47 tests, 0.26 s, nothing booted.**

The technique that made it worth doing first: the tests **run the wrapper they
built**, under a real `/bin/sh`, with `/work` pointed at a temporary directory —
the same way `GUEST_INIT` runs it, output redirected to files. That is not a
microVM and does not pretend to be one; the containment is stage C's business
and was measured there. What it proves is the part a microVM would not have
helped with: that the wrapper is valid shell, that it enters the directory it
was asked to, that the payload arrives byte for byte, and that a command reading
standard input gets what the request said.

It found a real bug on the first run, which is the entire argument for the
technique. The reader downstream matches stderr **exactly** against a marker, and
a shell that cannot enter a directory prints its own sentence first — worded
differently in dash, ash and bash. The match would have fired on no real guest
at all, and the fault would have surfaced once, expensively, on a booted machine.
The fix is `2>/dev/null` on the `cd`, and the same treatment on `base64 -d`.

Two decisions worth keeping written down:

**The payload travels as base64, and that is not decoration.** It closes three
things at once. The heredoc delimiter is `GDPVAL_SCRIPT_EOF`, containing `_`,
which base64's alphabet — `A-Z a-z 0-9 + / =` — provably never emits, so a
payload cannot end its own document early. A heredoc appends a newline the
model's bytes may not have had. And a 256 KiB script as one `printf` argument
would be past `MAX_ARG_STRLEN` and simply fail to execute.

**A setup failure and a command's own status are told apart by a marker, not by
a number.** The wrapper exits 125 when its own setup failed, but 125 is a number
a real command can return, so it counts as a setup failure only alongside the
matching marker on stderr — and there are two markers, not one. A path it could
not enter is something the model can fix by asking for another; a guest with no
working `base64` is a fault in the image, and telling the model to correct its
path would send it chasing something it cannot reach.

##### D2 — the backend, built and green

`core/agentic_v2_microvm_backend.py` and `tests/test_agentic_v2_microvm_backend.py`.
**36 tests.** Wider selection re-run afterwards: **1,971 passed, 3 skipped** —
no fingerprint regression from adding a `core/` module.

It subclasses `AgenticV2FixtureBackend`, and the reason is specific. Most of that
class is not a stub: it is roughly four hundred lines of workspace path safety —
a directory descriptor pinned by device and inode, every open relative to it with
`O_NOFOLLOW`, every resulting descriptor checked back against the root before a
byte moves, and quotas on entries, file size and total size. That is the code
that stops a model writing through a symlink into the host, and it is identical
whether the command afterwards runs in a fixture or in a machine. Two copies of
it would mean two versions of the part that must never drift.

What makes the fixture a fixture is overridden away: its identity, its
`fixture-upper` command, its demonstration package catalogue. **A test pins the
exact set of inherited public methods**, so a convenience added to the fixture
years from now cannot become a production capability while nothing fails.

###### The guard I did not touch, and where it is

`core/agentic_v2_runner.py:466` compares the startup identity against the
foundation fixture's and fails **anything else** with `compute_start_failed`.
This backend does not satisfy that check, and this change does not alter it.
That is not an oversight — it is the guard that has to be opened as its own
reviewable change, once the pieces under it have evidence, and opening it quietly
from inside the backend would make every other honest thing in the file
worthless. So the backend is proven directly by its tests, and **the runner still
refuses it.** There is now a line number for D4 to argue about.

###### Two capability gaps, named as gaps

`environment_resolve` and `environment_activate` refuse. Resolving a requirement
needs an index and the machine has no route to one — that is stage C's fourth
attack, the containment working, and the refusal is its consequence rather than
a missing feature.

`browser_run` refuses **including `open_local`**, and the two reasons differ.
`search` and `open_url` need a network. `open_local` needs none — the image has
chromium and the file is on the work disk — but nothing here starts it, collects
what it rendered, or bounds how long it runs. Returning a hash of the file the
model already handed over would read as a browser having run, which is worse than
an error. **Both gaps will change the outcome of some tasks, and a task that
failed for want of a browser has to read as that and not as a model that could
not do the work.**

###### Identity is the image, because the image is the behaviour

The fixture hashes its own source, which is right for something whose behaviour
is entirely its own code. Here the code decides very little: the same wrapper in
a different guest is a different machine with different programs in it. So the
implementation hash covers the image reference and digest, the kernel and root
filesystem hashes, the manifest, the pinned interpreter binaries and the policy.
`state_sha256` carries it too — an identical workspace under a different guest is
not the same state, and a resume that treated it as one would carry a run across
a change it should have noticed.

Two digests the runner insists on are derived rather than invented, and both are
described for what they are. `package_snapshot_sha256` is the hash of an **empty**
inventory — a real digest of a real state, since nothing can be installed.
`browser_build_sha256` identifies the browser *in this image*, from the image
digest and the manifest's own record of the command. **It is not a build
attestation from whoever built chromium**, and calling it one would be a claim
nobody here can support.

With no manifest, `start` returns `substrate_manifest_missing` rather than
describing itself. The tempting alternative is a placeholder digest, which would
put a hash into the run record that no file on disk corresponds to.

###### One thing found that has to be settled by probing, not by reasoning

The substrate manifest requires a command named **`python`**. D1 invokes
**`python3`**. On a Debian image both normally exist — but *normally* is not
evidence, and a guest with only one of them would fail every Python call with
"not found" while the manifest went on reporting the capability as present.

So the interpreter binaries are an **argument** to the backend rather than a
constant, defaulting to D1's mapping. The capability probe runs both and records
the answer, and the answer gets pinned here without editing D1 on the strength of
what is usually true.

##### D3 — what is actually in the guest, measured in the guest

`sandbox/v2/sweep_in_guest.py`, `tests/test_sweep_in_guest.py` (**23 tests**),
artefact `tasks/0822_saturday/guest_declared_command_sweep.json`.

The container sweep committed earlier says so itself, in its own `host_caveat`:
it was taken with docker, on a cgroup v1 host running a 3.10 kernel, and asks to
be re-taken where tasks will run before its numbers are treated as stage D's.
This is that re-take. Same probes, same framing, same reader — the only thing
that changed is the machine, and the machine was the entire question.

**What ran.** One Firecracker guest on `gdpval-devhost-vm`, the rootfs C2
booted, under `REQUIRED_MICROVM_POLICY`, `policy_sha256`
`6a5e665d3253c80302f001e8fd624b77838c38f92add1af63024277c5215888e`. Outcome
`booted`, command exit status 0, **11.775 s of a 1200 s deadline**, teardown
`all_gone: true`. Kernel and rootfs were re-hashed against C2's record before
the boot — `b36a4a1b…` and `489188…`, both matching — so this is a measurement
of the same bytes C2 booted and not of a directory that happens to share their
paths.

**40 of 40 probes answered. 34 present, 6 absent.** The absent are `Rscript`,
`chromium`, `cmake`, `node`, `npm` and `python3:ezdxf` — the same six the
container sweep found in the parent image. That agreement is worth stating
plainly: the container numbers were not wrong about *the image*, they were
unable to say anything about *the machine*, and now something can.

**Two changes to the driver, both in the artefact rather than left to be
noticed.** The container sweep gives each probe `/tmp` to write to; in the guest
the rootfs is read-only by policy and `/work` is the only writable mount, so the
redirections move there and `HOME` and `TMPDIR` follow. The second is not
tidiness. A probe that fails because it had nowhere to write exits non-zero
exactly like a probe whose command is absent, and without it the artefact would
have recorded the wrong reason for an unknown number of the forty. The
substitution is checked at runtime and the check has its own test: if the shared
driver ever stops writing to `/tmp/probe.`, this module refuses instead of
silently reporting an image with nothing in it.

**`guest_uid` is 0, and that is not a containment failure.** Root inside the
guest is the ordinary arrangement for a microVM — the boundary is the machine,
not a uid — and the host-side process runs as the unprivileged jail account,
uid 999. Both numbers are in the artefact side by side so no reader has to take
that on trust. C3 measured the boundary itself, separately, by attacking it.

**It is still not a capability receipt**, and a test asserts
`validate_capability_receipt` rejects it. No SBOM, no licence classification, no
package inventory. Signature and provenance remain `not_run`.

###### The `python` versus `python3` question, settled

D2 recorded that the substrate manifest requires a command named `python`, that
D1 invokes `python3`, that both normally exist on a Debian image — and that
*normally* is not evidence, so it had to be settled by probing rather than by
reasoning. It is settled: **both are present and both are Python 3.11.15**, in
this guest, on this host. `ALWAYS_ASKED` asks for both on every sweep precisely
so this stays answered rather than assumed after any image change.

###### The first run of this was not reproducible, and that was the point of the second

The sweep was first taken by a one-off script and produced the same 34/6. Its
artefact used different field names from the module written afterwards, which
meant a file committed as *what `sweep_in_guest.py` produces* could not have been
produced by `sweep_in_guest.py`. The test that matters here —
`test_it_was_taken_in_a_guest_and_not_on_the_host`, which compares the guest
kernel `6.1.141` against the host kernel `6.17.0-1022-azure` — only means
anything if the file came out of the code under test. So the host was started
again and the sweep re-taken by the committed module with `--rehash-images`.
Cost: about six minutes of a `Standard_D8as_v5`. That is the correct trade
against a committed artefact that quietly overstates its own provenance.

###### What the six absent commands mean for stage D, stated before it runs

`chromium` is moot: the microVM backend refuses `browser_run` in every form,
including `open_local`, and D2 already recorded that a task failing for want of
a browser must read as that. The other five are real narrowing. A task that
needs R, node, npm, cmake or `ezdxf` will fail in this guest, and **that failure
is an environment defect, not a model failure** — the distinction stage F is
required to keep. The image carrying all forty (`sha256:e47537b8…`) was built
and never pushed, so it is not reachable from here; the reachable parent is what
stage D executes against. This is written down before execution so no post-hoc
reading can convert those failures into a claim about the model.

###### The same six, now checked rather than stated — and C2's open item closed

`scripts/explain_guest_command_absences.py`,
`tests/test_explain_guest_command_absences.py` (**23 tests**), artefact
`tasks/0822_saturday/guest_command_absences_explained.json`.

The paragraph above is right, and it was also the kind of thing that rots. It
names a digest, a count and a cause in prose; add one line to
`debian-extra.lock` and every number in it is wrong while still reading as
confidently as before. So the claim is now derived on every test run from the
files it depends on, and fails when they and it diverge.

**What the derivation finds.** The candidate is the parent plus eight locked
packages — `chromium`, `cmake`, `fonts-noto-color-emoji`, `fonts-noto-core`,
`nodejs`, `npm`, `r-base-core`, and `ezdxf==1.4.3`. Six provide a command; the
two fonts provide none, which is stated in the script rather than derived,
because it is a fact about the packages and leaving it implicit would make the
arithmetic look as though it had dropped two rows. The six commands those
packages provide are `Rscript`, `chromium`, `cmake`, `node`, `npm` and
`python3:ezdxf` — **exactly** the six the guest was missing, with nothing left
over in either direction. The test that matters most is the one nobody would
think to write: a candidate-added command found *present* would falsify the
explanation just as thoroughly as an unexplained absence, because it would mean
the guest was not purely the parent and the tidy correspondence was a
coincidence.

**And it did not need to be inferred at all.** `sandbox/v2/declared-command-sweep.json`
ran the same forty probes against **both** images under docker on 2026-09-10,
before any of this booted: the candidate answered **40 of 40**, the parent **34
of 40**, and the six it missed are the six. Its parent digest is the digest C2
booted. So the six are named identically by two runtimes on two kernels —
docker on 3.10.102 and Firecracker on 6.1.141 — and the layer's contribution is
*measured*, not deduced from a lock file. The lock derivation corroborates that;
it was never the primary evidence, and the record should not have implied
otherwise.

**C2's open item, closed.** The pre-C2 note asked that C2 either build the
candidate or pin the parent and **say which it booted**, and not let it be
implicit. C2 pinned the parent and did not say so. It is said now, and checked:
the boot's `pinned_digest` equals `parent.lock.json`'s `manifest_digest`, and
the D3 sweep's layer digests equal the boot's layer for layer, so the sweep
measured the image C2 booted and not a directory sharing its paths.

**One correction to make in my own record.** The first draft of the script
disclaimed that "no digest for the candidate is recorded anywhere in this
repository." That is false three times over: `sandbox/v2/README.md` records an
image ID `sha256:e47537b8…` *and* an OCI manifest `sha256:0064ce70…`, and the
container sweep ran a third, `sha256:94ea6cb4…` — evidently a different local
build, which the artefact reports side by side without claiming they are the
same bytes. The true statement is narrower and is what the artefact now says:
none of the three can be pulled from here, because an image ID is not a
reference and the manifest was never pushed. The overstatement was caught before
it was committed, by reading the files the claim was about.

**What this does and does not change for stage F.** Not a model failure —
unchanged. Not a limit of the sandbox design either, which is the part the
prose above leaves implicit: the layer has been *observed* to supply all six, so
what stands between the run and those capabilities is an unpublished image
rather than anything about microVMs, the policy or the guest. And — the reading
that would be wrong in the other direction — those tasks will still fail. The
artefact says so in the same sentence as the exoneration, deliberately, so that
"not an environment defect" cannot be read as "so those tasks are fine."

##### The block stage D cannot clear from inside the repository

Stage D needs two things at once, and they live in different Azure tenants.

| | the guest host | the Foundry model |
|---|---|---|
| resource | `gdpval-devhost-vm`, RG `RG-GDPVAL-DEVHOST-KRC`, koreacentral | account `hjeon-fdpo-foundry-eus2`, project `gdpval-realworks`, deployment `gpt-5.4` |
| subscription | `4b7c60a5-b0e5-468e-9a2d-f0dcb2cc60d1` | `d372e9cf-d5f4-497e-b487-1a9973d20df9` |
| tenant | `6d93cc9b-abb8-4dab-9406-892843d0de0b` | `16b3c013-d300-468d-ac64-7eda0820b6d3` |
| what reaches it | `az vm run-command invoke` as the local signed-in admin | the GitHub OIDC application `f5e0ecfa-6d29-46b1-bdff-bb19ed3307ba` |

Established by converging readings rather than by one: `az cognitiveservices
account list` does not return the Foundry account, `az account list` shows one
subscription, Resource Graph returns **0 records** for it, no workflow in the
repository invokes `run-command`, and there are no C2 or C3 workflow runs —
every boot so far was driven from a local shell. The VM's system-assigned
identity `8544cbfc-76cc-4bd2-81e2-8985afc11a9f` holds **zero role assignments**,
and a managed identity cannot hold a role in another tenant regardless.

So the paid leg needs one of: a cross-tenant service-principal grant, or a
booting host inside subscription `d372e9cf…`. **Both are access changes, and
neither is covered by the cost approval**, which is why this is reported rather
than performed — even though the credentials to do the first are on this box.
GitHub-hosted runners remain ruled out for the host role on the grounds already
recorded here: nested virtualisation is documented as unsupported, and a
boundary offered with no guarantee is not a boundary. That finding is not loose
prose — it is `RECORDED_FINDINGS[0]` in
`batch-runner/core/agentic_v2_containment_readiness.py`, dated 2026-08-26 and
carrying the GitHub documentation URL it was established from, and
`_LABELS_COVERED_BY_A_FINDING` maps `ubuntu-latest`, `ubuntu-24.04`,
`ubuntu-22.04` and `ubuntu-20.04` onto it. Re-checked against that record in
this window, and it holds. Worth being explicit about why no measurement
reopens it: the objection is to the *support status*, not to the hardware, so a
job that found `/dev/kvm` present on a runner would have measured something
true and answered a different question. `check_every_machine_has_a_containment_finding`
also means a workflow introducing a *new* runner label reports a gap rather
than silently inheriting this answer.

The cheapest thing that could dissolve this without any grant has not been tried
and costs nothing: a read-only `workflow_dispatch` job that logs in as the OIDC
identity and asks what it can already do in *its own* subscription — `az account
show`, `az vm list`, provider registration, role assignments, `az vm
list-usage`. That is the next free step, and it is free because it asks for
nothing.

###### A matching kernel does not mean the same machine

CI corrected a test in this window, which is the outcome worth having and worth
recording. `test_this_box_is_refused_by_the_real_artefact` branched on
`kernel_release == os.uname().release` and read equality as *this is the
execution host*. GitHub's hosted runners are Azure virtual machines carrying the
same `6.17.0-…-azure` kernel build as the development host, so on a runner the
equality held, the test took the execution-host branch, and the reader refused
for the reason it should have: no `/usr/local/bin/firecracker`. Kernel equality
is necessary and not sufficient; the binaries check is what separates a runner
from the machine C2 booted on. Both gates were already there and both are
load-bearing — only the test's reasoning about them was wrong.

###### Host ledger for this window

Two windows on `gdpval-devhost-vm`, `Standard_D8as_v5`, koreacentral:
23:02→23:20 UTC and 23:23→23:29 UTC on 2026-09-10, about **25 minutes**
combined, both ended by `az vm deallocate` after confirming no logged-in users
and no `firecracker`, `jailer` or sweep processes. List rate 0.424 USD/h puts
the arithmetic near 0.18 USD; the actual charge is **not verifiable from this
box** — the local `az` tenant is not the one that bills these workflows — so the
window is recorded as `partial` and **not** as zero. **Zero model calls were
made in this window; the only spend is the host.**

##### The guard, measured: it is eight places, not one

Earlier notes in this document, and the project card, described the remaining
code gate as one comparison — `core/agentic_v2_runner.py`, the startup check
that a backend's identity is exactly the foundation fixture's. That was
counted, and it is wrong. The foundation identity is pinned in **eight**
places across two modules:

| module | what it pins |
|---|---|
| `agentic_v2_runner.py` ×4 | the worker's profile, the startup guard, and two constants in the success envelope |
| `agentic_v2_provenance.py` ×6 | `foundation_fixture_identity`, and five callers that reconstruct a whole expected startup payload from it |

That is not sprawl to be tidied up. It is the property that no single edit can
turn a fixture run into a claimed real one, and it should stay that way.

**What it means for the shape of the change.** The provenance module does not
merely compare an identity. `foundation_fixture_identity()` *manufactures* the
startup payload a run must match — capabilities `["fixture-upper"]`, runtimes
`["fixture"]`, a fixed package record set, a fixed browser-build digest — and
`_verify_fixture_result_semantics()` goes further and **re-simulates every
executed tool call** against the fixture's known behaviour, comparing the
result envelope and the state digest either side of it.

A command run in a real guest cannot be re-simulated. Its output is not a
function of anything the verifier holds. So admitting a second identity is not
a matter of loosening a comparison: it requires a **second verification
standard** — structure, digests, chain integrity, budget accounting and state
continuity, but not output equality — and that standard has to be recorded in
the run, by name, so a reader can tell which one was applied. Admitting the
identity without that would produce runs this code calls verified while
checking strictly less than the word implies. That is the failure this whole
stage is arranged to avoid, and it is why the gate is still shut.

**What was done now, and why only this.** Two constants in the success
envelope were replaced by the values the backend reported:

- the runtime fingerprint's implementation digest, which read the digest the
  guard compared *against* rather than the one the backend *reported*
- `foundation_only`, which was the literal `True` two lines above a
  `backend_identity` carrying its own `foundation_only`, read from a substrate
  manifest, with nothing making the two agree

Both were right today, by consequence: there is one admitted backend, so the
readings cannot differ. Doing it while they cannot differ is the point — the
moment a second identity is admitted, a constant there would describe the
wrong run, silently, in the field a reader would use to tell the runs apart.

The startup guard's inline dict also became a named tuple of complete
identities, `admitted_identities`, holding exactly one entry. Nothing is
admitted that was not admitted before. What the shape buys is that admitting
something later is an addition to a named list rather than a comparison that
got weaker, so it appears in a diff as what it is. A test asserts the set has
exactly one entry and that it is the foundation's — not that the microVM
backend is excluded *by name*, which would pass while admitting anything else.

**What is still shut, deliberately:** the admitted set has one member, the
second verification standard is not written, and `exec_run` on a real guest
reaches nothing through this path. None of that changed here.

##### And the other half of it is not code

Even with the gate open, there is nowhere to run: the GPT deployment and the
machine that boots a guest are in different subscriptions in different
tenants, and the runner-as-host route is closed on support status rather than
hardware. Whether a host could go in the model's own subscription under
permissions that already exist is a question that can be asked for free and
read-only — `batch-runner/scripts/azure_boot_host_survey.py`, run from its own
workflow, five ARM control-plane reads, creating nothing and requesting
nothing. Its answer decides whether stage D needs an access change at all. If
it does, the exact change gets **named and reported**, not performed.

##### It was asked, and the answer is permissions

Run `34549220652` on `8cce9ab`, 2026-09-11T01:05:16Z, twenty-seven seconds,
`success`. All five reads completed, so this is a block that was **observed**
rather than one inferred from a read that failed — the distinction the survey's
own first test exists to protect. Transcribed to
`tasks/0822_saturday/boot_host_survey.json`, since the job log will age out and
the block will not.

| read | answer |
|---|---|
| session | the expected subscription, `Enabled` |
| provider | `Microsoft.Compute` **registered** |
| existing hosts | **0** |
| quota | `standardDASv5Family`, **100 free vCPUs** of 100, 0 in use |
| permissions | **2 assignments**, and **none** of the three writes permitted |

Verdict `blocked_and_the_change_is_named`.

**Four of the five came back favourable.** It is the right subscription, the
provider is registered, and eastus2 has room for an 8-vCPU host more than ten
times over. Exactly one thing is missing: the run identity holds two role
assignments, and neither grants `Microsoft.Compute/virtualMachines/write`,
`Microsoft.Network/networkInterfaces/write`, or
`Microsoft.Resources/subscriptions/resourceGroups/write`.

That narrowness is the useful part. A quota increase would not help, a region
change would not help, and registering the provider would not help, because
none of those is what is stopping it — and each would have been a plausible
thing to go and ask for. The survey's value was in ruling them out, not in
finding the block.

So the named change is a role assignment on this identity in the model's
subscription, and per the standing instruction that access expansion is
separate from cost approval, it is **named here and left undone**. It is not
requested, and nothing in this repository moves toward it.

Two things it is not. It is not a claim that a host placed here would boot a
guest — that is C2's question, answered on a different machine in a different
subscription, and it would have to be answered again. And it is not a reason to
fall back to Docker, V1 or a host subprocess, which would answer a question
nobody asked.

What it does not block is the code. The second verification standard the
microVM backend needs, and the stage E ledger and retry wiring, need no host and
no access change, so they are where the work continues while this sits with
whoever owns the subscription.

##### The second standard, written: what "verified" means when nothing can be re-simulated

That is where the work went. `core/agentic_v2_provenance.py` now names two
standards instead of assuming one:

| standard | for |
|---|---|
| `fixture-replay-v1` | the foundation fixture, every result of which can be produced again from a known simulation and compared in full |
| `attested-execution-v1` | a backend whose output nothing in this process can predict |

**Naming it is the change; the contents follow from the name.** A run that says
*verified* is making a claim, and the claim is not the same for a fixture as for
a guest. Three parts of a real result cannot be predicted by anything in the
verifying process — the bytes a command actually wrote, the time it actually
took, and the state of a filesystem that is not a dictionary in memory — so
re-simulation there is not expensive, it is undefined. Letting both kinds of run
say the same word would let the weaker claim be read as the stronger one, and
nothing in the record would show which had been made.

`RESULT_STANDARD_COVERAGE` writes out both halves in the record's own words. The
attested standard **checks eight things**: the envelope's shape and its declared
schema version, `request_sha256` recomputed from the committed request,
`result_sha256` recomputed over the envelope's own fields, the result data
against the tool contract's schema, `output_bytes` against the encoded length of
the data reported, the state chain either side of the call, the tool-call budget
counted the same way for every backend, and the 64 KiB result ceiling together
with the error it must produce. It **declines three**: whether the data is what
the command *should* have produced, which no party to this process knows;
`wall_ms` against any particular value, because a real command takes real time;
and the state digest against a re-simulation, because the state is a real
filesystem rather than a ledger in memory. The fixture standard's
`does_not_check` is empty, and that emptiness is a fact about it rather than a
section nobody filled in.

The three declines are the useful half. "Verified" with nothing after it reads
as the strongest thing the word can mean; this standard is genuinely weaker, and
a reader who cannot see *where* it is weaker will assume it is not.

**The standard is chosen by backend id with no default.**
`result_verification_standard()` raises for a backend nobody has mapped rather
than falling through to the looser of the two. A new backend quietly receiving
the weakest available verification is the failure this whole arrangement exists
to prevent, and a `ValueError` at startup is a much better outcome than a run
record that overclaims.

##### D4 — the guest identity becomes admissible, and nothing admits it

With the standard written, the remaining barrier turned out not to be about
results at all. It is at startup. `_valid_started_payload` did not merely check
that a startup event was well formed: it reconstructed the fixture's **entire**
payload — `commands == ["fixture-upper"]`, `runtimes == ["fixture"]`, the fixed
package records, the fixed browser digest — and required equality. A real guest
reports its own capabilities out of its substrate manifest, so its startup could
never have matched, whatever standard its results were later judged under.

**What changed, exactly.** Four things, each smaller than it sounds:

- `MICROVM_BACKEND_ID` moved into `core/agentic_v2_contract.py` beside the
  foundation's, and the backend module re-exports it. Two files spelling the
  same identity is one file spelling it differently later, and the difference
  would surface as a run silently refused at startup rather than as anything a
  reader could name.
- `_RESULT_STANDARD_BY_BACKEND` gained its second entry. That table is what
  makes the guest admissible at all, because admission refuses any backend it
  cannot look up in it.
- `_valid_started_payload` split in three: a backend-agnostic structural chain
  both standards share, then the fixture's exact-equality block **unchanged**,
  then a shape-only check for the attested standard. What the attested branch
  adds beyond shape is one rule — a payload whose commands are exactly
  `["fixture-upper"]` and whose runtimes are exactly `["fixture"]` is refused —
  so a guest identity cannot be worn by the fixture.
- the runner's hard-coded admitted set became `admitted_identity`, a constructor
  argument that defaults to the fixture.

**`foundation_only` was not relaxed, and did not need to be.** The microVM
backend reads that flag from its substrate manifest, and under the manifests in
this repository it reports `True`. So both standards still require it, and this
change is about *which* backend may start, never about how far one may go.
`production_activation: "disabled"` is untouched and stays an independent brake.
The same reading turned `_failure()`'s hard-coded `"foundation_only": True` from
accidentally correct into correct on purpose, and a test now pins the two
together.

**A declaration is refused where it is made, not where it runs.**
`_validate_admitted_identity` raises at construction for an identity that is
malformed, that is not foundation-only, or whose implementation hash is not a
hash. The alternative — failing the run — would surface a configuration mistake
as `compute_start_failed` on every task, which reads as an infrastructure fault
and, by the disposition map below, would be counted as one.

**And it found an ordering fault that predates it.** A startup no standard
accepts used to be caught only at final verification, by which point the failure
envelope being written *contained* the bad started event and could not be
verified either. A run that failed cleanly, for a nameable reason, produced a
record nothing downstream would accept — and the reason was lost.
`startup_is_admissible()` asks the same question before the event is appended,
so the run stops with an ordinary `compute_start_failed` that verifies like any
other failure. Its test asserts the chain contains no `started` event at all.

**What is still shut.** Nothing in this repository declares a non-default
identity, and a test globs `core/*.py` to establish that rather than asserting
it. `production_activation` is `"disabled"`. `exec_run` on a real guest reaches
nothing through the product path, and the two guards in `step2_run_inference.py`
and `core/executor.py` are where they were. What changed is that admitting a
guest is now an argument someone passes — which a diff shows as an addition —
instead of a comparison someone loosens, which a diff shows as the deletion of a
line that used to say the fixture's name.

**Checked.** 264 tests across the foundation, microVM and contract modules;
2,851 passed and 4 skipped across the wider agentic subset. Nine new tests.
`mypy` on the four changed modules reports 29 errors against a 34-error baseline
taken from `origin/main` in a throwaway worktree — five fewer, none introduced.

The evidence that the fixture path is untouched is the *absence* of behavioural
failures. Three tests failed on the first run and all three asserted the old
one-backend world: that the admitted set had exactly one member, that exactly
one backend had a standard, and that the microVM id appeared nowhere in the
runner's source. They were rewritten to assert the new invariants, which are
still narrow. No test was relaxed to pass.

And the attested branch is exercised rather than merely present: the guest
double declares `commands == ["fixture-upper", "python3"]`, which the fixture
branch rejects outright, and its run verifies — so the attested branch is the
one that ran. That is a proof by consequence rather than by mutation, which is
deliberate: rewriting the source in place would have corrupted the suite running
beside it.

### Stage E — not yet run

Before any of it is written, what the repository already has. Two searches this
window each turned up a finished implementation of something that looked like
new work, and both are recorded here so the next reader spends the hour on
stage E rather than on rediscovering them.

**The three-way retry distinction is built.**
`core/execution_environment_readiness.py` defines
`RETRY_INFRASTRUCTURE_ERROR`, `RETRY_MODEL_SELF_REVIEW` and
`RETRY_TOOL_LOOP_INTERNAL_RECOVERY`, maps them onto the ledger's own
`retry_kind` vocabulary through `RETRY_KIND_TO_REASON`, and counts them off
ledger rows in `retry_counts_by_reason`. It also deliberately declines to map
`RETRY_RESUME` onto any of the three — a resumed round re-attempts a task, but
because the previous *process* stopped, and calling that an infrastructure
error would inflate the one count the run is trying to measure. Unmapped kinds
are reported separately under `unmapped_retry_kinds`, present-and-empty rather
than absent, so an empty count is a measurement.

**The per-task cost ledger is built, with the rules stage E was going to
restate.** `core/cost_receipts.py` already holds each task's cost as two
receipts that never add up — `BUCKET_PROBLEM_SOLVING` and `BUCKET_GRADING` —
which is the separation of grading cost this task asks for. It already refuses
to treat a missing usage block as free: `STATUS_PARTIAL` with
`REASON_USAGE_ABSENT`, `known_cost_usd` carrying the confirmed part and
`estimated_cost_usd` left `None`. Its own words are "zero is a measurement, not
a default", and the only real `$0` is a path that never contacted a provider.
It also refuses prefix or nearest-neighbour price matching, and never removes a
call that happened, even when the output it paid for was thrown away.

So stage E's work is **wiring, not invention**: making the V2 runner emit one
ledger row per call in that existing vocabulary, so the existing counting and
the existing two-bucket receipt apply to a V2 run unchanged. A second ledger
would be the wrong shape of effort and would give the run two answers about its
own cost.

**The runner-as-host route is closed, and re-checking it is not free thinking.**
`RECORDED_FINDINGS[0]` in `core/agentic_v2_containment_readiness.py` rules out
GitHub-hosted runners for the guest role, and `_LABELS_COVERED_BY_A_FINDING`
binds all four `ubuntu-*` labels to it. The objection is the documented support
status, not the hardware, so a job that measured `/dev/kvm` on a runner would
answer a true but different question — and presenting that measurement as
reopening the route would be the same overclaim as reading a self-computed
digest as a supplier signature.

#### The cost and blame wiring, built. Nothing has run through it.

`core/agentic_v2_cost_binding.py` is the V2 caller `core/cost_receipts.py` did
not have. It is a separate module on purpose: the ledger is shared with other
work, and binding a backend to it should not mean editing it.

**All 27 error types are mapped onto 8 dispositions, and two of the eight are
neither the model's fault nor the environment's.** Ten are `semantic` — the
model did something the contract refuses — five are `infrastructure`, one is
internal recovery, and four are terminal. The two that matter are the ones an
easier map would not have:

- **`runner_defect`, seven error types.** They can only be produced by this code
  misbehaving. Filing them under infrastructure would inflate the one retry
  count the 220-task run exists to measure, and would make the sandbox look
  unreliable on occasions when it was fine.
- **`ambiguous_not_attributable`, one.** `task_wall_time_exhausted` cannot be
  attributed from the error alone: a model looping and a host crawling produce
  the same symbol. It is recorded as undecidable rather than assigned to
  whichever side is convenient.

The map is total in both directions and the check is at import — a contract
error nobody classified, or a classification invented for an error that does not
exist, stops the build rather than defaulting to somebody's fault.

**The guest's own time is recorded unpriced rather than free.**
`RUNTIME_KIND_MICROVM_GUEST` is not in the price table, so its seconds go into
the ledger with no amount and a `runtime_cost_unpriced` reason, which holds the
task's receipt at `partial`. That is the same rule the host windows above
follow, for the same reason: a bill this repository cannot read must not be
allowed to look like zero.

Built and tested. Nothing has run through it, because nothing has run.

### Stage F — pre-registered on 2026-09-11, not yet run

Stage F asks for the fixed task manifest, the model, prompt, tools, token, time
and retry conditions and the technical stop rules **written down before
anything runs**, then five tasks, then thirty, then two hundred and twenty.

That is now `core/agentic_v2_preregistration.py`, and its committed output is
`tasks/0822_saturday/v2_run_preregistration.json`, sealed at
`fa74921bdfcb9368c4f9140a1f990b6a60d2059963d2abb76e06d6d8eb9115ea`.

It is code and not prose because a document can be edited to agree with a
result, and because writing the promise down turned out to falsify one of the
sentences this task has been using since it was written.

**The escalation is not nested.** "Five, then thirty, then two hundred and
twenty" reads as three circles inside one another. It is not. One of the five —
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d` — is not in the thirty, so only **four**
tasks carry across the first two stages. A sentence of the form "the thirty
confirmed the five" would be false about a fifth of the five.

This is not a defect and nothing needs fixing. `select_advance_check_tasks` and
`select_trial_run_tasks` answer different questions, both predate every run, and
neither can see a score — so the gap cannot be score-chasing in either
direction. What would have been wrong is discovering it in the report, after
the numbers were in and there was a reason to prefer one reading. A's committed
`exp034_codex_foundry_trial30.yaml` names the same absence independently: it
writes its thirty out in full and that identifier is not among them.

**A difference from A's run is not an environment effect.** The instruction is
to state whether the compared items match and, if they differ, not to claim the
difference is the environment. `compare_with_codex_run()` reads A's committed
file field by field rather than restating it, so the comparison tracks A's
configuration instead of a memory of it. Today:

| | B (V2) | A (Codex) | |
|---|---|---|---|
| deployment | `gpt-5.4` | `gpt-5.4` | matches |
| the thirty tasks | derived | written out | matches, same order |
| self-review | off | off | matches |
| resume rounds | 0 | 0 | matches |
| attempts per task | 1 | 4 | **differs, alignable** |
| per-task clock | 1200 s | 1800 s | **differs, alignable** |
| tool surface | eight named tools | the agent's own | **differs, irreducible** |
| standing instructions | describes those tools | describes its own | **differs, irreducible** |

`may_attribute_difference_to_environment()` returns `False`, and will keep
returning `False`. An unread field counts as differing, not as agreeing, so a
missing source file blocks rather than passes.

The useful part is the last column. Two of the four differences are settings
nobody has aligned yet and B can match before the 220. The other two cannot be
removed by anyone: the two run places offer different tools, and an instruction
has to describe the tools the model actually has. `residual_after_alignment()`
therefore names what a maximally-aligned comparison could honestly claim —
a joint effect of the run place **and the tool contract it imposes** — which is
narrower than "the environment did it" and still, in the file's own words, "not
an effect of the isolation alone, and must not be written as one".

**There is no success quota.** The eight stop rules are all about a record that
can no longer be trusted: the deployment not matching the pinned one, a run
switching model on its own, the seal failing, a gate this record calls shut
reporting itself open, a paid call with no recorded budget or spend past the
approved amount, an unwritable ledger, the runner-defect disposition three
tasks running, and a guest that cannot be cleaned between tasks. None mentions
a score. Beside them, `NOT_STOP_RULES` records in writing that a task scoring
zero, a capability absence, the first five not all succeeding, and disagreement
with A's run are **results** — there is no target pass rate anywhere in the
record, and a stage does not have to look good to proceed.

**What the pre-registration is not.** It is not a statement that the
environment is ready — no V2 task has run, and the blocker is still the role
assignment above. It is not an approval to spend; `approved_maximum_usd` is
still `null` and is the owner's to fill in. And it is not a prediction.

Regenerate with `python batch-runner/scripts/write_v2_preregistration.py`;
`--check` reports drift without writing. If the drift test fails, read why
before regenerating: this repository's own inputs moving and A's experiment
file moving produce the same failure but mean different things, and the second
one means someone has to decide whether the runs are still comparable at all.

### Stage E — a run that can be resumed, collected and reported, 2026-09-11.

Three modules, 91 tests, no model call and no Azure spend. They are the parts
of step 4 that were still missing: per-task isolation and resume, file
collection, and the connection to the report. The retry distinction and the
cost ledger binding were already built and are unchanged here.

**V2 had no resume at all.** Not a weak one — none. A grep across the 26 V2
modules finds the word only in docstrings. V1 has one, but it cannot carry V2:
`workspace/step2_inference_progress.json`, written by `step2_run_inference.py`,
appends a result only once a task has *finished*, as `success` or `error`. A
task that started, cost money and was killed half way through leaves no record
in it at all, and so on resume is indistinguishable from a task that never
began.

`core/agentic_v2_task_journal.py` writes **two** records per attempt for that
reason. An `opened` record is fsync'd *before* `open_task` returns, so a torn
`opened` at the end of the file means the process died before any model call —
which is the fact that makes dropping a torn tail safe rather than convenient. A
torn line anywhere *earlier* is `JournalCorrupt` and stops the run. The journal
also owns `attempt_index`, which nothing owned before and which `make_call_id`
already needed: without it a retry's ledger rows collide with the dead
attempt's, and the two attempts' spend becomes one number.

**An abandoned attempt lowers the run's receipt permanently.** Once a task has
an `opened` with no `closed`, `receipt_ceiling()` returns `partial` and keeps
returning it however well the retry goes — `test_a_later_success_does_not_undo_an_abandoned_attempt`
is the test that pins this. The spend that vanished stays vanished. This is the
same rule as everywhere else in the repository: unpriced is `partial`, and it is
not `$0`.

**A half-written deliverable directory is indistinguishable from a short
answer.** That is the failure `core/agentic_v2_deliverable_collection.py`
exists against. Five files, three written, then a full disk, and what is left on
disk looks exactly like a finished task with three deliverables: `fill_parquet`
reads the paths, `step5_validate` checks they exist, and the submission goes out
short with nothing anywhere saying so. So files are written into
`deliverable_files/.collecting-<attempt>/`, every one is read back and
re-hashed, and only then is the directory `os.replace`d into place. Any
exception — including `KeyboardInterrupt` — removes the staging directory.

The bytes are hashed twice on purpose. The guest's digests answer *did the guest
produce this*; re-reading answers *is this what is on the host's disk now*, and
a short write, a silently truncating filesystem and a disk that filled between
two files all produce a file that exists and is wrong.

**The report will show zeros for seven of V2's eight tools, and that is stated
rather than left to be discovered.** `step6_report._compute_agentic_metrics`
buckets tool calls under V1's names — `inspect_workspace`, `run_python` and the
rest. V2's are `exec_run`, `environment_resolve` and the rest. The two
vocabularies share exactly one name, `finalize`, and
`core/agentic_v2_run_report.py` asserts that overlap at import so it cannot
quietly become half-true. A reader who saw one non-zero `finalize` beside five
zeros would reasonably conclude the model used one tool. The counts are
therefore written under V2's own names as well, where they can be found.
Teaching the report V2's vocabulary is a change to a shared file and is not made
from here.

**`conservative_cost_usd` is absent, never zero, when the cost is unknown.** The
report sums that field as a plain float, so a zero would put a wrong number in a
headline; an absent key contributes nothing and claims nothing. It is written
only when the receipt is `complete` *and* the journal says every attempt was
accounted for. `summarise_v2_run` reports `graded: None` with a stated reason
rather than `graded: 0`, because zero graded and grading-not-attempted look
identical as a number and are not the same fact.

**What this does not mean.** No V2 task has run. Nothing here boots a guest,
asks a model, or prices a call — all three modules are handed facts established
elsewhere and arrange them. The blocker is still the single role assignment
named in stage D, which remains reported and not requested.
