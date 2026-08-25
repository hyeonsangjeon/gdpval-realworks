# Agentic Sandbox V2: a safe path to running commands and letting the model decide

- Written: 2026-08-25
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

2. **The model is never asked anything.** `core/agentic_v2_runner.py` replays a
   list of calls written down in advance. It has a `scripted_calls` input and no
   model client at all. The state machine can be exercised, but no model ever
   sees a result and chooses what to do next, which is the entire point of this
   run place.

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
| `batch-runner/core/agentic_v2_runner.py` | Stage one: gains a real conversation with the model in place of the replayed list. |
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

## 8. Order the work would be done in

1. Work out and get approval for the cost ceiling of a small stage-one run.
2. Build the model conversation with `exec_run` still shut.
3. Measure whether choosing tools helps, on the same five tasks.
4. Write the containment rules and the tests that try to break them.
5. Seek approval for command execution, presenting those test results.
6. Only then, open `exec_run`.
7. Revisit the two guards, each in its own change.
8. Add the fourth column to the comparison plan.

## 9. How this would be checked

- Stage one: a test that gives the model a task whose first attempt must fail,
  and requires that the model be asked again with the failure in front of it.
- Stage one: a test that the run stops at the dispatcher's call ceiling rather
  than continuing indefinitely.
- Stage two: one test per containment rule, each attempting to exceed it and
  requiring failure.
- All stages: the existing test that opens all three guards and requires them
  shut must keep passing until the stage that deliberately changes one.

## 10. Done when

- [ ] The model chooses its own next action, and a test proves it reacts to a
      failure it was shown.
- [ ] Every containment rule has a test that tries to exceed it and fails.
- [ ] Command execution is opened only after a separate written approval.
- [ ] The free check reports this run place as able to run only when it is.

## 11. Known blockers and the next decision

- **Blocked on approval to call a model in a loop.** Stage one costs money and
  its ceiling has not been worked out or approved.
- **Blocked on a decision about containment.** The substrate manifest requires a
  small isolated virtual machine. Whether that is available on the machines this
  would run on has not been established, and stage three cannot be designed
  concretely until it is.

The next decision is whether stage one is worth its cost, which cannot be
answered until that cost is worked out. That is the first piece of work, and it
is free.
