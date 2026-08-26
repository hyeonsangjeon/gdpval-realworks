# Agentic Sandbox V2: a safe path to running commands and letting the model decide

- Written: 2026-08-25
- Updated: 2026-08-26 — step one of section 8 is done. The cost of a stage-one
  run has been worked out and is in section 7a. Nothing was spent doing it and
  nothing was switched on.
- Status: **specification only. Nothing here is built, and nothing in it may be
  built without a separate, explicit approval to open command execution.**
- Related GitHub Project: hyeonsangjeon/projects/5 — card
  "같은 GPT 모델의 실행 환경별 성능 비교"

## 1. The problem a person actually hits

The comparison of run places has five columns. The fourth is Agentic Sandbox V2,
where the model would repeatedly pick a tool, read what came back, and choose
the next action. Today that column is empty and cannot be filled, because two
things are missing and a third is deliberately shut.

This matters beyond one empty column. The other run places all work the same
way: the model writes a block of Python once, somebody runs it, and the result
is whatever that one block produced. If a library is missing or a file is not
shaped the way the model assumed, the task simply fails. A model that can look
at the failure and try something else is doing a different and more realistic
kind of work, and nobody can currently measure how much that is worth.

## 2. What exists today, read from the code

**The tool surface is fully specified.** `core/agentic_v2_tools.py` defines
eleven operations a backend must provide, including `exec_run` for running a
command, `environment_resolve` and `environment_activate` for packages,
`browser_run`, `verify_public`, and `finalize`. The dispatcher around them
already enforces a ceiling on the number of calls, a ceiling on the size of each
result, and a deadline.

**There is a large amount of supporting machinery.** Alongside the tools sit
modules for the contract, provenance, supply chain, licence evaluation, the
image format, and the substrate. The substrate manifest requires a small
isolated virtual machine and refuses to validate without that policy.

**Three things stand between this and a real run:**

1. **Running commands is switched off.** In
   `core/agentic_v2_fixture_backend.py`, `exec_run` answers
   `capability_unavailable` for every command except one deliberately trivial
   test case that copies a file and converts it to capital letters. Nothing real
   can be run.

2. **No real model can be asked anything.** The loop now exists:
   `core/agentic_v2_conversation.py` asks a model, runs the tool it asked for,
   shows it the result, and asks again, under five ceilings checked before each
   call. It is proven against stand-in models that spend nothing. What it
   cannot do is reach a real model: `real_model_voice()` refuses, and the loop
   refuses any model that declares itself paid before asking it anything.
   `core/agentic_v2_runner.py` is untouched and still replays a list of calls
   written down in advance, with no model client at all — the loop was added
   beside it rather than inside it, so nothing that runs today changed.

3. **Two separate guards refuse the mode outright.**
   `step2_run_inference._require_runnable_execution_mode` rejects it, and
   `core/executor.py` refuses to build a runner unless the caller states that
   the run makes no paid model calls.

The third item is a safety decision, not an oversight, and this document does
not propose removing it.

## 3. Goals

1. Describe a route from "replays a script" to "the model chooses", in stages,
   where each stage is separately reviewable and separately approvable.
2. Make the dangerous stage — actually running commands the model chose — the
   last one, behind its own approval, with the containment written down first.
3. Give the comparison a fourth column that is honestly comparable to the other
   three, or an honest statement of why it cannot be.

## 4. What must not happen

- **The three guards must not be bypassed, weakened, or worked around** as a
  side effect of any stage below. The existing free check runs all three and
  reports if any has opened; that check must keep passing until the guard is
  removed deliberately, in its own reviewed change, with its replacement
  containment already in place.
- **Command execution must not be opened before containment is proven.** Letting
  a model choose commands that then run is a different risk from running a block
  of Python a person can read first.
- **No stage may quietly fall back to a weaker containment.** This is the same
  rule the Docker run place already follows: if the intended isolation is not
  available, the task fails and says so, rather than running somewhere else.

## 5. The design, in plain terms

Four stages, in order. Each is useful on its own, and each can be stopped at.

**Stage one — let the model choose, but only among safe tools.**
Replace the list of pre-written calls with a real conversation with the model,
while leaving `exec_run` shut. The model can look at the workspace, resolve
packages, and finish, but it cannot run a command. This proves the loop works —
the model reads a result and picks a next action — without the risky capability.
It is enough to answer "does asking the model repeatedly help at all?"
*The loop is built (`core/agentic_v2_conversation.py`) and proven against
stand-ins. Asking a real model needs an approved amount and the removal of a
deliberate refusal; neither has happened.*

**Stage two — write down the containment, and prove it separately.**
Before any command runs, state what the command may touch: which directory,
whether the network is reachable, how much memory and time, which user it runs
as, and what happens when it exceeds any of those. Prove each one with a test
that tries to exceed it and requires the attempt to fail. This is a test-only
stage; nothing is switched on.

**Stage three — open command execution behind its own approval.**
Only after stage two passes. `exec_run` starts running real commands inside the
containment from stage two. This needs an explicit approval of the same kind the
paid-run approval already uses: absent it, the capability stays shut.

**Stage four — join the comparison.**
The run place is added to the plan as a fourth column, under the same fixed
conditions as the other three.

The reason for this order is that stage one delivers the interesting
measurement, and stage three carries nearly all the risk. Doing them in this
order means the risky work is only undertaken if the safe work has already shown
the loop is worth having.

## 6. Files and how information flows

| File | Role |
|---|---|
| `batch-runner/core/agentic_v2_conversation.py` | Stage one, **built**: the loop that asks the model, runs the tool it chose, shows it the result, and asks again. Reaches no real model. |
| `batch-runner/core/agentic_v2_runner.py` | Unchanged. Still replays the written-down list; the loop was added beside it, not inside it. |
| `batch-runner/core/agentic_v2_tools.py` | Unchanged surface; the ceilings it already applies become the loop's limits. |
| `batch-runner/core/agentic_v2_fixture_backend.py` | Stays shut through stages one and two. |
| `batch-runner/core/agentic_v2_substrate.py` | Stage two: the containment rules are stated and checked here. |
| `batch-runner/step2_run_inference.py` | Stage three: the guard is revisited, not before. |
| `batch-runner/core/executor.py` | Stage three: the paid-run refusal is revisited, not before. |

Flow: the task and instructions reach the model; the model asks for a tool; the
dispatcher checks the ceilings and passes it to the backend; the result comes
back to the model; repeat until the model finishes or a ceiling is hit.

## 7. Safety, cost, and no-silent-substitution conditions

- Stage one is the first stage that costs money, because it calls a model in a
  loop. The number of calls per task is bounded by the dispatcher's existing
  ceiling, and a cost ceiling must be worked out and approved before it runs, in
  the same way the five-task advance check was.
- The loop's cost is not predictable from the task alone, because the model
  decides how many turns to take. The ceiling must therefore be based on the
  maximum number of calls, not an expected number.
- Stage three must fail loudly when its containment is unavailable.
- The existing free check must keep reporting this run place as
  "structure checks only" until stage three is genuinely approved and complete.

## 7a. What stage one would cost, worked out on 2026-08-26

This is step one of section 8, done. It cost nothing: no model was called, no
command was run, and no account was signed in to.

### Why a loop is not priced the way a single request is

The three run places already in the comparison ask the model once per task.
Their cost is close to fixed: the task is however long it is, the answer may be
up to the length the settings permit, and that is the bill.

A loop is different in three ways at once, and only the first is obvious.

1. The model is asked once per tool call rather than once per task.
2. Every one of those turns may write a full-length answer, so the writing is
   charged per turn instead of per task.
3. **Every turn re-reads the whole conversation before it.** What the model
   wrote on turn one, and every tool result it was shown, is sent again on turn
   two, and again on turn three, and so on.

The third is the one that catches people out, because it means the bill does not
rise in step with the number of turns. It rises roughly with the square of it.
Doubling how many times the model may be asked roughly quadruples what the
earlier turns cost to re-read.

That property was worth finding for a second reason: the same mistake was
already in the shared arithmetic, where it was undercounting the Azure code
interpreter — which also loops. Correcting it raised the three-place
comparison's ceiling from 32.23 to 43.77 United States dollars, above the amount
that had been approved for it. That is recorded in
`batch-runner/experiments/execution_envelope/advance_check_plan.yaml`.

### The numbers

Worked out by `batch-runner/core/agentic_v2_stage_one_budget.py` over the same
five tasks the three-place comparison uses. Print the table with:

```
cd batch-runner
python scripts/check_agentic_stage_one_ceiling.py
```

Two settings decide almost the whole bill. Running costs, in United States
dollars, at most:

| tool calls per attempt | most a turn may write | most it could cost to run |
|---|---|---|
| 4 | 2,048 | 3.24 |
| 4 | 32,768 | 13.80 |
| 8 | 2,048 | 12.45 |
| 8 | 32,768 | 41.25 |
| 16 | 2,048 | 48.79 |
| 32 | 2,048 | 193.15 |
| 32 | 32,768 | 492.67 |

Marking the answers adds 5.85 whichever row is chosen, so a total is the running
figure plus 5.85.

### What the table says

**The dispatcher's own defaults are the most expensive row on it.** The
dispatcher allows 32 tool calls, and the three-place comparison lets an answer
run to 32,768 tokens. Someone starting from both defaults, reasonably assuming
they were sensible starting points, would be committing to at most 492.67
dollars for five tasks — over fifty times the cheapest row that could still
answer the question.

**The answer-length cap is the cheaper of the two levers, and costs nothing to
turn down.** In the three-place comparison a generous cap is nearly free,
because one answer is written per task; the note there records that lowering it
truncated the model's code. Here it is multiplied by the number of turns, and a
turn that only picks a tool needs very little room. It is not a compromise to
lower it; it matches what a turn actually does.

**Marking dominates at the small end.** At four tool calls, marking is 5.85
against 3.24 for running. Anyone trying to make stage one cheaper by shortening
the loop further will find there is little left to save.

### The figure is enforced, not just written down

A worked-out ceiling that nothing enforces is a hope. `StageOneBudget` in the
same module counts what a run has spent and refuses the next call once any of
the three ceilings is reached, and it is built from the same worked-out figure
rather than from a number typed in beside it, so the two cannot drift apart.
Spending past a ceiling raises rather than being reported quietly, because a
loop that has already overspent has lost track of what it is doing.

### What is still missing before stage one could run

The money is now the larger of the two blockers, which is a change from where
this section started.

The loop itself is built. `core/agentic_v2_conversation.py` asks a model, runs
the tool it asked for, shows it what came back, and asks again, with every
ceiling checked before the next call and every way of stopping named. What is
missing is narrower: nothing here can reach a *real* model.
`real_model_voice()` refuses, and the loop refuses any model that declares
itself paid before asking it anything. The free check still reports this first,
before it reports anything about money, and it now establishes it by *running*
both refusals rather than by reading what the runner accepts — so the answer
will change by itself the day somebody wires a real client in.

`core/agentic_v2_runner.py` is unchanged and still replays a written-down list.
That was left alone on purpose: the loop is a separate module, so nothing that
runs today changed behaviour, and the existing runner's tests still hold.

## 8. Order the work would be done in

1. ~~Work out and get approval for the cost ceiling of a small stage-one run.~~
   Worked out (section 7a). **Approval still outstanding.**
2. ~~Build the model conversation with `exec_run` still shut.~~ Built:
   `core/agentic_v2_conversation.py`, proven against stand-ins that spend
   nothing. `exec_run` is still shut, and the loop cannot reach a real model.
3. Measure whether choosing tools helps, on the same five tasks. **Needs an
   approved amount and a way to reach a real model.**
4. Write the containment rules and the tests that try to break them.
5. Seek approval for command execution, presenting those test results.
6. Only then, open `exec_run`.
7. Revisit the two guards, each in its own change.
8. Add the fourth column to the comparison plan.

## 9. How this would be checked

- Stage one: a test that gives the model a task whose first attempt must fail,
  and requires that the model be asked again with the failure in front of it.
  **Done:**
  `tests/test_agentic_v2_conversation.py::test_the_model_is_asked_again_with_the_failure_in_front_of_it`.
- Stage one: a test that the run stops at the dispatcher's call ceiling rather
  than continuing indefinitely. **Done:**
  `tests/test_agentic_v2_conversation.py::test_the_run_stops_at_the_dispatchers_own_call_ceiling`.
- Stage two: one test per containment rule, each attempting to exceed it and
  requiring failure.
- All stages: the existing test that opens all three guards and requires them
  shut must keep passing until the stage that deliberately changes one. **Still
  passing**, and the loop's own test suite runs all three blocks as well.

## 10. Done when

- [x] The model chooses its own next action, and a test proves it reacts to a
      failure it was shown. (Against a stand-in model. A real one is still out
      of reach and needs an approved amount.)
- [ ] Every containment rule has a test that tries to exceed it and fails.
- [ ] Command execution is opened only after a separate written approval.
- [ ] The free check reports this run place as able to run only when it is.

## 11. Known blockers and the next decision

- **Blocked on there being no way to reach a real model.** This is now the
  smaller blocker. The loop exists at
  `core/agentic_v2_conversation.run_model_conversation` and is proven against
  stand-ins that spend nothing, but `real_model_voice` refuses and the loop
  refuses any model that would be charged for. That refusal is deliberate: it
  means a paid run cannot start until somebody removes it in a change a
  reviewer will see, alongside approving the amount.
- **Blocked on approval to call a model in a loop.** This is now the larger
  blocker. The ceiling has been worked out (section 7a) and nothing has been
  approved against it.
  `experiments/execution_envelope/agentic_stage_one_plan.yaml` leaves the amount
  empty on purpose, and the free check refuses while it is empty. The 32.23
  United States dollars approved on 2026-08-25 was for the three-place
  comparison and does not extend here.
- **Blocked on a decision about containment.** The substrate manifest requires a
  small isolated virtual machine. Whether that is available on the machines this
  would run on has not been established, and stage three cannot be designed
  concretely until it is. This blocks stage three only, not stage one.

The next decision is now a specific one with a price beside it: **which row of
the table in section 7a is stage one worth running at?** The cheapest row that
could still answer the question is four tool calls with a 2,048-token cap per
turn, at most 3.24 to run and 5.85 to mark, so 9.09 in total. The dispatcher's
own defaults are 492.67 to run.

Choosing a row does not start anything, and neither figure above is an approved
amount. Approving one, and removing the refusal that keeps a real model out of
the loop, are two separate steps and both are the owner's to take.
