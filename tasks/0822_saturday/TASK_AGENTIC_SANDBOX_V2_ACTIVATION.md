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
> `chroot()`, so the file lands at the in-jail path `/firecracker.pid`, which is
> `<chroot_dir>/firecracker.pid` seen from the host. What `--new-pid-ns` buys is
> the namespace and nothing else. Both flags are still passed, for the two
> separate reasons above; only the explanation was wrong.

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

**Done.** `core/agentic_v2_microvm_launch.py` and its 81 tests. The exit
condition is met in both directions: every rule has a test that reads the built
arguments, every rule has a case that deletes it from a copy of the policy and
requires a refusal naming it, and a weakened value is refused rather than
adapted to. The guards were checked by mutation rather than by their passing —
fourteen deliberate breakages of the builder (the flag dropped, the host memory
bound lowered to the guest's, the v1 cgroup file name used under v2, the root
drive made writable, the in-jail config path turned into a host path) and each
one had to fail a test before the work was called done. Two of the fourteen
initially did not, and both were holes in the tests rather than in the builder:
`fsize=` was asserted as a string anywhere in the argument list, so deleting the
`--resource-limit` that carries it changed nothing, and the in-jail paths were
asserted against their own constants, so moving a constant to a host path took
the test with it. Both now assert the requirement instead of the spelling. The
last surviving mutation was the builder's own backstop — the check that every
accepted rule reached `rules_applied` — which no healthy build exercises; it now
has a test that stages the drop.

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
### Stage D — not yet run
### Stage E — not yet run
### Stage F — not yet run
