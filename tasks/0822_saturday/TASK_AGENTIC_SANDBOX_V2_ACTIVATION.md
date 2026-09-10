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
| The containment rules exist, in one copy, with all six questions answered. | `core/agentic_v2_substrate.py` `REQUIRED_MICROVM_POLICY` |
| **Nothing turns those rules into arguments for starting a machine.** The readiness report says so on every rule, on every machine — "this is the same on every machine, because it is a fact about this repository". | `core/agentic_v2_containment_readiness.py:851`, via `scripts/check_agentic_containment.py`, run 2026-09-10 |
| No machine in play can host the containment: this box is kernel 3.10.102 inside a container with no virtualisation device; GitHub-hosted runners are documented as unsupported for it; the `agentic-sandbox` self-hosted runner does not exist. | same run |

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

**Exit condition.** For each of the six rules, a test that **starts the
machine, exceeds the rule, and requires the machine to stop it**: writing past
the 256 MiB working-directory quota, allocating past 4,096 MiB, running past
1,200 seconds, opening a network connection, writing to the read-only root, and
running as a privileged user. Plus a credential test: the process must not be
able to read any token, key or environment secret the orchestrator holds.

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

**Still not done.** The dispatch has not been made and no model has been asked.
Everything that decides whether it may be is now built, tested and refusable.

### Stage B — not yet run
### Stage C — not yet run
### Stage D — not yet run
### Stage E — not yet run
### Stage F — not yet run
