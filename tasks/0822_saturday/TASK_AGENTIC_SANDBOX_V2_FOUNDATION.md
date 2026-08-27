# Agentic Sandbox V2: a safe path to running commands and letting the model decide

- Written: 2026-08-25
- Updated: 2026-08-26 — step one of section 8 is done. The cost of a stage-one
  run has been worked out and is in section 7a. The containment question that
  blocked stage three has been answered, and the answer is in section 7b: the
  containment is available on no machine currently in play. Nothing was spent
  finding either out and nothing was switched on.
- Updated: 2026-08-26, later the same day — the containment rules themselves are
  now complete and stated once. Four of the six things a containment has to say
  were never written down, and the two that were had three copies that nothing
  compared. Section 7c. Writing down what a containment *would* be is not the
  same as having one: the rules still apply to nothing, and this made the report
  refuse in one more case rather than one fewer.
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
isolated virtual machine and refuses to validate without that policy. Whether
any machine can actually provide that virtual machine is now answered rather
than assumed — `core/agentic_v2_containment_readiness.py` reads the machine it
is on and reports which parts of the policy it can meet. Section 7b has the
answer: none of the machines in play can meet it.

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
*Where the containment could run is established — section 7b, and the answer is
nowhere in play. The rules themselves are now written down in full: on
2026-08-26 all six questions above got an answer, where before only two had one
and the working directory said "there is a quota" without ever saying what the
quota was. They are decided in one place, `REQUIRED_MICROVM_POLICY`; the signed
policy on disk still carries its own copy because a signed artefact has to, but
nothing hand-writes a third one any more and a disagreement between the two is
refused by name. Every rule has a test that attempting to weaken it is refused.*

*What is still missing from this stage, and cannot be supplied yet, is the other
half of "prove it": a test that starts a machine, exceeds a limit and watches the
limit stop it. That needs both a machine that can host the containment and code
that turns these rules into arguments for starting one. Neither exists. A test
written today could only assert that a value is written down, so
`tests/test_agentic_v2_containment_rules.py` says in its own opening lines that
this is what it does and does not do — because a passing test named after a thing
that never happened is how an unenforced rule comes to look enforced.*

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
| `batch-runner/core/agentic_v2_substrate.py` | Stage two, **built**: the containment rules are stated and checked here. `REQUIRED_MICROVM_POLICY` is the one written-down copy of them, and the numbers in it carry documentation saying what each was derived from. `supply_chain_microvm_block()` and `containment_rules_that_disagree()` exist so the signed policy can be derived from it and compared against it rather than restating it. |
| `batch-runner/core/agentic_v2_supply_chain.py` | Stage two: held a hand-written second copy of the containment rules until 2026-08-26. Now derives the block it requires from the file above, and refuses a signed policy whose rules have drifted from it, naming both places in the message. |
| `batch-runner/security/agentic-v2-supply-chain-policy.json` | The signed statement of the same rules, under different names — it says `read_only_rootfs: true` where the substrate says `rootfs: "read-only"`. The mismatch in names is why the two copies could drift unnoticed; the comparison above translates between them. |
| `batch-runner/core/agentic_v2_containment_readiness.py` | Stage two, **built**: reads a machine and reports which of those rules it can actually meet, and why. Reads the policy above rather than restating it. Reports "could this machine host the containment" and "does anything apply the rules" as two separate answers; see section 7b. |
| `batch-runner/core/agentic_v2_microvm.py` | Unchanged. Reports whether a boot test could be attempted; does not judge the host kernel or the processor, which is why the module above exists. |
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

A later correction to the same file raised that ceiling again, to 363.59, by
counting marking at what its settings permit rather than at what past runs
happened to average, and by counting the two extra models marking uses to read
pictures and listen to sound. Neither correction made anything more expensive.
Read the plan file rather than the figure quoted above if you need the current
one; 43.77 is left here because it is what this particular fix produced.

### The numbers

Worked out by `batch-runner/core/agentic_v2_stage_one_budget.py` over the same
five tasks the three-place comparison uses. Print the table with:

```
cd batch-runner
python scripts/check_agentic_stage_one_ceiling.py
```

Two settings decide almost the whole *running* column, which turns out to be the
smaller part of the bill. Every figure below is a column the check itself
prints, in United States dollars:

| tool calls per attempt | most a turn may write | to run | to mark | total |
|---|---|---|---|---|
| 4 | 2,048 | 3.32 | 89.95 | 115.77 |
| 4 | 32,768 | 13.88 | 89.95 | 126.33 |
| 8 | 2,048 | 12.61 | 89.95 | 125.06 |
| 8 | 32,768 | 41.41 | 89.95 | 153.86 |
| 16 | 2,048 | 49.12 | 89.95 | 161.56 |
| 32 | 2,048 | 193.81 | 89.95 | 306.25 |
| 32 | 32,768 | 493.33 | 89.95 | 605.77 |

Marking costs the same whatever the settings are, because the settings do not
change how the answers are marked. The total column is **not** the first two
added up, because a third cost is missing from the table: looking at the
answers — opening the spreadsheets, slides and images a task produced so the
marker can see them — adds 22.50 on every row. The ceiling counts it separately
from marking because it is a different set of calls. So each total is running
plus 89.95 plus 22.50, to within a cent: every column is rounded up on its own,
while the total is worked out from the unrounded parts, so on three of the rows
adding the printed figures overshoots the printed total by 0.01.

An earlier version of this section said marking adds 5.85 and stopped there.
That was wrong twice over, in the direction that costs money: it predated the
correction that made marking a real ceiling rather than a sample, and it left
out looking at the answers entirely. On the cheapest row it understated the bill
by about 106 dollars. The figures above are quoted from the check's own output
rather than carried over, so a future correction moves them here as well.

### What the table says

**The dispatcher's own defaults are the most expensive row on it.** The
dispatcher allows 32 tool calls, and the three-place comparison lets an answer
run to 32,768 tokens. Someone starting from both defaults, reasonably assuming
they were sensible starting points, would be committing to at most 493.33
dollars of running for five tasks — nearly a hundred and fifty times the
cheapest row that could still answer the question. On totals the gap is much
smaller, about five times, because marking and looking at the answers are the
same on every row. Both comparisons are worth having: the first says what the
settings are worth choosing carefully, the second says what the bill will
actually look like.

**The answer-length cap is the cheaper of the two levers, and costs nothing to
turn down.** In the three-place comparison a generous cap is nearly free,
because one answer is written per task; the note there records that lowering it
truncated the model's code. Here it is multiplied by the number of turns, and a
turn that only picks a tool needs very little room. It is not a compromise to
lower it; it matches what a turn actually does.

**Marking dominates, and not only at the small end.** At four tool calls,
marking is 89.95 against 3.32 for running, and looking at the answers adds
another 22.50. Running does not overtake the other two until sixteen tool calls
with a generous cap. Anyone trying to make stage one cheaper by shortening the
loop is working on the smaller half of the bill: at eight tool calls or fewer
the running column never passes 41.41, against 112.45 of marking and looking
that does not move whatever is chosen.

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

## 7b. Where the containment could actually run, established on 2026-08-26

Section 11 used to say the containment question "has not been established". It
has now. Like section 7a, this cost nothing: no model was called, no command was
run, no account was signed in to, and nothing was installed. It reads machines
and published policies.

### What was actually required, and where that is written

The substrate manifest will not validate unless it promises a small isolated
virtual machine, run by Firecracker, with no network, a read-only root
filesystem, and a working directory that is wiped and size-limited. Those
settings now have exactly one written-down copy,
`core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY`, which the manifest check
enforces and the readiness report reads. Two copies could disagree with each
other about what is required; one cannot.

*Updated 2026-08-26, later the same day: there were, in fact, three copies. The
signed supply-chain policy stated the same rules under different names, and
`core/agentic_v2_supply_chain.py` held a third copy hand-written into its
validator — so a rule could be weakened in one place and left standing in the
others with every file still validating. The signed policy's block is now
derived from the one above, and a disagreement between the two is refused by
name. Section 7c has the detail.*

### The answer, in one line

**The containment is available on no machine currently in play.** Three machines
are in play, and each is a different kind of no.

| machine | can it provide the containment? | how that was established |
|---|---|---|
| the box this repository is worked on from | no | read from the machine itself |
| GitHub-hosted runners | no | GitHub's own published documentation |
| the self-hosted `agentic-sandbox` runner | the question cannot be answered | there is no such machine |

*And a fourth answer, added 2026-08-26, that no machine can change: even a
machine that could host the containment would be started with none of the rules
applied, because no code in this repository turns them into arguments for
starting a machine. See "Two questions that were one field" below.*

### This box

Its processor can do the job — it reports `svm`, so the hardware itself supports
running a virtual machine. Everything above the hardware fails:

- It cannot reach the hardware. This is running inside a container
  (`/.dockerenv` exists) with no virtualisation device passed through. Running
  inside a container is not disqualifying on its own — Firecracker supports it
  when the device is passed through — but nothing here passes it through.
- Its kernel is 3.10.102. The oldest host kernel Firecracker validates against
  is 5.10. Firecracker does not *forbid* older ones; its kernel policy says
  untabled versions "might work" but are not validated in its test suite. An
  unvalidated containment boundary is not one to rely on, so this is treated as
  not met rather than as forbidden, and the report says which of the two it
  means.
- Neither `firecracker` nor `jailer` is installed.

### GitHub-hosted runners

This is a documented no, not an unknown. GitHub's own documentation says running
a virtual machine inside one of its runners is "technically possible" but "not
officially supported" — experimental, at the user's own risk, with no guarantee
of stability, performance or compatibility. **A containment boundary offered
with no guarantee is not a containment boundary.** The whole point of stage
three's containment is that it holds when a model asks for something unexpected,
and "no guarantee of compatibility" is the opposite of that.

### The self-hosted runner

`.github/workflows/agentic-sandbox-preflight.yml` asks for a machine labelled
`agentic-sandbox`. No self-hosted runner is registered to this repository, and
that workflow has never run. So this is not a no — it is a question with no
subject. A machine that does not exist has no containment either way, and
whether a future one would have it is a decision nobody has taken yet.

This is worth stating separately from the other two, because it is the only one
of the three that a decision could change.

### How to see this for yourself, for free

```
cd batch-runner
python scripts/check_agentic_containment.py
```

It prints every requirement, whether this machine meets it, and *why* in a full
sentence; then the findings recorded about the two machines that cannot be read
from here, each with its source; then the answer. It exits 0 only if the
containment is available somewhere, so it is safe to wire into an automated
check — today it exits 1.

Three properties of that check are worth knowing:

- **It never runs a command to find any of this out.** It reads files and
  inspects the program search path. A test asserts the module's own source
  contains no way of starting a process, because a containment check that
  starts processes to decide whether starting processes is safe has the problem
  backwards.
- **It notices when a new machine appears.** It reads `runs-on:` out of every
  workflow file and fails if any machine is being asked for that has no recorded
  finding. Adding a runner to a workflow without answering the containment
  question for it is caught by a test rather than by a person remembering.
- **It distinguishes "no" from "cannot be answered".** A requirement whose
  answer is unknown counts against availability rather than for it, so an
  unanswered question can never be mistaken for a cleared one.

### What this changes, and what it deliberately does not

It answers the question that blocked stage three from being *designed*. It does
not unblock stage three, and it removes no refusal: `exec_run` still answers
`capability_unavailable`, and the two guards still reject the mode. The
readiness module has its own function for this,
`refuse_command_execution`, which returns a refusal today and would return
nothing only once the containment genuinely exists somewhere.

It also changes what stage three's first step is. It was "write the containment
rules". It is now "obtain a machine that can hold them" — which is a request for
hardware, not a code change, and is the owner's to make.

## 7c. The containment rules themselves, finished on 2026-08-26

Section 7b answered *where* the containment could run. This answers *what* it
is. The two are separate, and the second turned out to be in worse shape than
the first suggested.

### What was actually written down, and what was missing

A set of settings is a containment only if it answers six questions: where a
command may write, whether it can reach the network, how much memory it gets,
how long it may run, who it runs as, and what happens when it exceeds any of
those. Only two were answered. The working directory said `ephemeral-quota` —
"there is a quota" — and never said what the quota was. There was no memory
limit, no time limit, no user, and no answer to what a breach does.

All six are now answered, each with a number or a word rather than a promise:

| question | the rule | where the number comes from |
|---|---|---|
| where it may write | `workdir: ephemeral-quota`, `workdir_quota_mib: 256` | twice what the tool layer already accepts — `_MAX_WORKSPACE_BYTES` and `_MAX_FINAL_BYTES` are 64 MiB each, so a smaller disk would let the tools accept a write the disk could not hold |
| the network | `network: none` | unchanged; it was one of the two already answered |
| memory | `memory_mib: 4096` | **picked, not derived** — the only number here with nothing behind it |
| time | `wall_clock_seconds: 1200` | the same per-task timeout the other three run places are held to, taken from `agentic_stage_one_plan.yaml` |
| the user | `user: jailer-unprivileged` | Firecracker's jailer drops privileges; naming it makes "not root" checkable |
| a breach | `on_breach: stop-and-report` | section 7 already requires stage three to fail loudly when its containment is unavailable, and a rule that has been exceeded is a containment that is not holding |

A test refuses any rule whose name ends in a unit but whose value is not a
positive whole number, because that is exactly the shape the working directory
had before.

**The memory number is the honest weak spot, and is recorded as one.** None of
the three run places in the comparison caps memory at all. Applying a cap here
makes this column stricter than the others on an axis the comparison does not
otherwise control, so a task that failed here for memory would not have failed
elsewhere for that reason. That is written into the rule's own documentation
rather than left for somebody to notice later.

### Three copies of one rule, and nothing comparing them

The rules were stated in three places: `REQUIRED_MICROVM_POLICY`, the signed
supply-chain policy on disk, and a hand-written dictionary inside the
supply-chain validator. Nothing compared any two of them, and the names differ
between them — one says `read_only_rootfs: true` where another says
`rootfs: "read-only"` — which is what made a disagreement hard to see by eye.
Three copies is three chances to weaken a rule and no chance to notice.

There is now one copy. The validator's dictionary is derived from it by
`supply_chain_microvm_block()`, and a signed policy that disagrees with it is
refused with a message naming the rule and both places it is written down.

### Every rule is refused when weakened, and nothing pretends to be enforced

`tests/test_agentic_v2_containment_rules.py` — 33 tests — takes each rule in
turn, weakens it, and requires the weakened version to be rejected: the network
opened to an allowlist or to the host, the root filesystem made writable, the
working directory made persistent, any limit quadrupled, the user set to root,
the breach rule changed to carry on, the runtime changed to Docker, and the
whole containment marked optional. Deleting a rule outright is refused too,
since that is the quietest way to remove one.

What those tests deliberately do not do is start a machine, run a command,
exceed a limit and watch it stop. That is the test these rules will eventually
need. It cannot be written yet, and the file says so in its own opening lines
rather than quietly omitting it, because a passing test named after a thing that
never happened is how an unenforced rule comes to look enforced.

### Two questions that were one field

Writing the numbers down exposed a reporting fault. The readiness report had one
field for "the containment is available", and it was answering two different
questions at once: *could this machine host the containment*, and *is the
containment actually in place*. Because they were one field, a rule that nothing
applies was being reported as met.

They are now two fields, because they are fixed by two different things:

- **Could a machine host it** is fixed by finding, configuring or buying a
  machine. It is read off the machine.
- **Does anything apply the rules** is fixed by writing code that turns
  `REQUIRED_MICROVM_POLICY` into arguments for starting a machine. Nobody has
  written it. This is a fact about this repository, so the answer is the same on
  every machine, and a better machine does not change it.

Every policy setting in the report now answers "cannot be established here"
rather than "met", and says which of the two reasons applies. The recorded
findings for machines that cannot be read from here were renamed accordingly:
they record whether a machine *could host* the containment, which is the only
part of the question a machine can answer.

This makes the report strictly more cautious than before: the refusal now stands
even on a machine that meets every hardware requirement. The free check's exit
code is 1 for either reason, and its own documentation lists them separately so
that a reader can tell whether to go and find a machine or go and write code.

**No refusal was removed and nothing was switched on.** Writing down what a
containment would be is not the same as having one, and the three guards are
exactly as shut as they were.

## 7d. Two free checks that answered the same question differently, fixed 2026-08-26

### What a reader saw

Both of these are printed to whoever is deciding what to do next, and on
2026-08-26 both were run in the same session:

| Check | What it said about the loop |
|---|---|
| `scripts/check_agentic_stage_one_ceiling.py` | the loop exists at `core.agentic_v2_conversation.run_model_conversation`, is proven against stand-ins that spend nothing, and what is missing is a way to reach a real model |
| `scripts/check_execution_envelope_advance_check.py` | "the model never sees a tool result and never chooses a next action" |

Only one of them had looked. The first settles the question by running the loop
against a stand-in that declares itself paid and requiring the loop to stop
before asking it anything. The second was a sentence in
`core/execution_environment_readiness.py`, written before the loop existed and
correct when it was written. Building the loop (section 5, pull request #228) did
not change it, because a sentence is not checked against anything.

This is the same fault as sections 7b and 7c and as the two pull requests before
them: **a claim written in prose, relied on, and never compared with the code.**
The only new part is that this time the repository was already contradicting
itself out loud and nobody had put the two outputs side by side.

### Why it mattered rather than being untidy

The stale half pointed at work that was already finished. A reader taking the
advance check at its word would have concluded that stage one still needed its
loop written, when what stage one needs is an amount approved and a way to reach
a real model — a different job, for a different person.

### One sentence that was three claims

The blocker read: *the command-running tool exec_run is closed, the model never
sees a tool result and never chooses a next action, and no approval exists to use
this environment in a real experiment.*

Those are three separate blockers with three different ways out — opening the
command tool, reaching a real model, and an approval. Bundled into one sentence,
finishing any one of them changed nothing in the report, which is precisely how
the finished one went on being listed as outstanding.

### What it does now

They are three blockers, and none of them is asserted:

- **The command tool** is called, here, with an ordinary command, and the
  blocker reports what came back. If it ever answers instead of refusing, the
  report says so rather than repeating the reassuring sentence.
- **Reaching a real model** is not decided here at all. The readiness report asks
  `core.agentic_v2_stage_one_budget.check_stage_one_cannot_reach_a_model`, which
  is the one place that establishes it by running the loop, and prints back
  exactly what it returns. Writing a second copy of that reasoning is what caused
  this defect; the fix is to have one copy and one caller.
- **The approval** stays a plain statement, because there is nothing in the code
  to observe: an approval is a decision, not a fact about a module.

The lookup goes through this module's existing by-name import helper, so a module
that has moved is reported as an unanswered question rather than crashing the
whole report — and an unanswered question is reported as *a real model has to be
treated as reachable until somebody checks*, never as silence.

`experiments/execution_envelope/advance_check_plan.yaml` carried the same stale
claim in a comment and was corrected in the same change, with a note saying which
of the two copies is the one checked against the code.

### The test that stops it happening again

Nine tests in `tests/test_free_checks_agree_on_the_loop.py`. The load-bearing one
requires the sentence the readiness report prints about reaching a real model to
be, character for character, the sentence the other check produced. Matching on
substance rather than on the text would let the two drift apart again, which is
the whole failure being fixed. Five of the nine fail against the code as it stood
before this change.

### What was switched on — nothing

The report gained a blocker and lost none. The three guards are as shut as they
were, `check_agentic_sandbox_v2_blocks_are_intact()` still returns no problems,
the environment is still `structure_check_only`, and all three free checks still
exit 1.

## 8. Order the work would be done in

1. ~~Work out and get approval for the cost ceiling of a small stage-one run.~~
   Worked out (section 7a). **Approval still outstanding.**
2. ~~Build the model conversation with `exec_run` still shut.~~ Built:
   `core/agentic_v2_conversation.py`, proven against stand-ins that spend
   nothing. `exec_run` is still shut, and the loop cannot reach a real model.
3. Measure whether choosing tools helps, on the same five tasks. **Needs an
   approved amount and a way to reach a real model.**
4. ~~Write the containment rules and the tests that try to break them.~~
   **Rules written (section 7c):** all six questions answered with numbers, one
   written-down copy, and a test per rule that weakening it is refused.
   **The tests that try to break them are only half written**, and the missing
   half needs two things that do not exist: a machine that can host the
   containment — a request for hardware, not a code change — and code that turns
   the rules into arguments for starting one. Until both exist, the rules are
   written down and applied to nothing.
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
  requiring failure. **Half done, and the half that is missing is named rather
  than skipped.** `tests/test_agentic_v2_containment_rules.py`, 33 tests, takes
  each rule in turn, weakens it, and requires the weakened version to be
  refused — including a rule deleted outright, and a rule weakened in the signed
  policy alone. What no test does is start a machine, exceed a limit and watch
  the limit stop it; that needs a machine that can host the containment and code
  that applies the rules, and neither exists. The file's own opening lines say
  so, and a test in it fails if the file ever gains the ability to run anything.
- Stage two: the numbers that were derived from something else are checked
  against their source, so the source moving is caught: the working disk against
  the tool layer's own write ceilings, and the time limit against the per-task
  timeout the other three run places are held to.
- Stage two: a check that reports, per machine, which containment rules that
  machine can meet and why. **Done:**
  `tests/test_agentic_v2_containment_readiness.py`, 64 tests, including one that
  requires the check itself to be incapable of starting a process, one that
  fails if a workflow starts asking for a machine nobody has answered the
  containment question for, and one that requires no policy rule to be reported
  as met while nothing applies the rules.
- All stages: the existing test that opens all three guards and requires them
  shut must keep passing until the stage that deliberately changes one. **Still
  passing**, and both the loop's and the containment check's own test suites run
  all three blocks as well.

## 10. Done when

- [x] The model chooses its own next action, and a test proves it reacts to a
      failure it was shown. (Against a stand-in model. A real one is still out
      of reach and needs an approved amount.)
- [ ] Every containment rule has a test that tries to exceed it and fails.
      Every rule now exists and has a number (section 7c), and every rule has a
      test that weakening it is refused. Exceeding one and watching it stop
      needs a machine that can host the containment — none of the three in play
      can, see section 7b — and code that applies the rules to that machine,
      which nobody has written.
- [ ] Command execution is opened only after a separate written approval.
- [ ] The free check reports this run place as able to run only when it is.
      (Three of the questions behind that report are now answered from real
      readings rather than assumed: whether a real model can be reached, whether
      any machine could host the containment, and whether anything applies the
      containment rules. All three answers are no.)

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
- **Blocked on there being no machine that can hold the containment.** This was
  previously "blocked on a decision about containment", with the note that
  whether it was available "has not been established". It has now been
  established, by reading machines rather than by asserting it, and the answer
  is in section 7b: **no machine currently in play can provide it.** This box
  cannot reach hardware virtualisation and runs a kernel below the oldest
  Firecracker validates; GitHub-hosted runners offer the capability only as
  unsupported and unguaranteed, which is not a containment boundary; and the
  self-hosted machine one workflow asks for has never been registered, so its
  question has no subject. This blocks stage three only, not stage one. It is
  also the only blocker on this list that code cannot clear: it needs a machine.
- **Blocked on nothing applying the containment rules.** Added 2026-08-26, and
  it is genuinely new rather than a restatement of the one above. The rules are
  now complete and written down once (section 7c), but no code turns them into
  arguments for starting a machine, so a machine that could hold the containment
  would still be started with none of the rules applied. This blocker is the
  same on every machine, because it is a fact about this repository rather than
  about any machine — obtaining hardware does not clear it, and it does not
  clear the hardware blocker either. Both must go before stage three can be
  considered. Unlike the one above, this one *is* clearable by code; it was not
  cleared here on purpose, because writing a launcher builds the risky
  capability before there is anywhere to test it and before anyone has approved
  opening it.

The next decision is now a specific one with a price beside it: **which row of
the table in section 7a is stage one worth running at?** The cheapest row that
could still answer the question is four tool calls with a 2,048-token cap per
turn, at most 3.32 to run, 89.95 to mark and 22.50 to look at the answers, so
115.77 in total. The dispatcher's own defaults are 493.33 to run and 605.77 in
total. Choosing the cheapest row saves 490 dollars of running and changes
nothing else, which is why the choice is worth making rather than defaulting.

Choosing a row does not start anything, and none of the figures above is an
approved amount. Approving one, and removing the refusal that keeps a real model out of
the loop, are two separate steps and both are the owner's to take.

There is now a second decision, for stage three rather than stage one, and it
does not compete with the first: **is a machine that can run a Firecracker
virtual machine worth obtaining?** Section 7b establishes that none exists
today. Stage one does not need one — it never runs a command. Stage three
cannot happen without one. Deciding not to obtain one is a legitimate answer,
and it would mean stage three is closed rather than pending, which is worth
knowing either way.
