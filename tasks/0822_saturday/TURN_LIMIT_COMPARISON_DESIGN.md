# Does 8 tool calls hold the model back? — a design, not yet a run

`tool_calls_per_attempt: 8` is a pinned condition of stage one. It gives an
attempt nine model calls: eight tool turns and one commit. Nobody chose eight
for a measured reason, and eleven of trial_30's twenty-one failed attempts
ended with the harness saying, verbatim, *"the model has been asked 9 times,
which is all the 9 this run was allowed"*.

So the question is fair. This file works it through before any setting is
changed, and reaches a verdict that is not "run it".

**trial_30 is not modified by anything here.** Neither is its sealed
preregistration. Any comparison gets a new config file and a new run id.

---

## 1. What decision turns on the answer

Whether full_220 runs at 8 or at something larger. That is a real fork with a
real price: the stage ceiling scales close to linearly with the limit, so the
decision is also a budget decision. If the answer is "8 is fine", the cheapest
setting is also the right one and that is worth knowing.

## 2. What would show the hypothesis is wrong

Hypothesis: *tasks fail at this limit because they run out of turns, not
because the model cannot do them.*

It is wrong if, at a higher limit, the tasks that previously ran out still
fail — they simply fail later, having spent more. That outcome is publishable
and settles the limit for full_220 at 8.

It is also wrong, in a more interesting way, if the higher limit makes things
*worse*. See §4: more turns means more opportunities to call a tool that ends
the task.

## 3. How many axes move

This is where the design bites.

**The backend must not move.** A comparison run against a real Firecracker
backend, against a trial_30 run against the fixture backend, changes the limit
and the execution capability together and can say nothing about the limit
alone. The comparison therefore runs on the **fixture backend**, the same one
trial_30 used, whatever the state of the host permissions
(`HOST_PERMISSIONS.md`) at the time.

**The refusal behaviour must not move either.** `agentic_v2_runner.py:772`
ends a task on its first tool result that is not `ok: true`. Changing that is
not a setting — it reaches the trace schema (see §4) — but if it is ever
changed it must not be changed in the same run as the limit.

Everything else is held at trial_30's values: same 30 tasks, same model, same
`max_output_tokens_per_turn: 8192`, same `retry_max_attempts`, same
`max_result_bytes`, same instructions.

## 4. What the limit can actually reach

The cohort does not divide the way the disposition labels suggest. Read from
`run_record.json` — from each attempt's `budget_after` and the `tool_name` on
each turn, not from the labels:

| | tasks | what happened |
|---|---|---|
| ended on `browser_run` | **12** | one call, reaching the network — 8 a `search`, 4 an `open_url`. Refused, task over. 2–5 of the 9 calls allowed. None retried |
| ended on `workspace_apply` | **2** | same terminal refusal, different tool. One was rescued by a retry, one also hit the ceiling and failed |
| ran out of calls, desk never broke | **9** | 5 rescued by a retry, 4 failed |
| gave up early, without committing | **2** | stopped well short of the limit |
| finished inside the limit | **5** | never came near the ceiling |

That is 30 tasks, 11 successes and 19 errors, which is trial_30's headline.

Two things follow.

**The limit can only act on 18 of the 30 tasks.** The twelve that ended on
`browser_run` were ended before the ceiling was anywhere near. Of the eighteen
that remain, ten touched the ceiling in some attempt and five of those already
reach success through a retry — so the visible effect is bounded at roughly
five tasks out of thirty before any noise is considered.

**The 18 is not a stable denominator.** A model given more turns has more
chances to reach `browser_run` and be terminated, so tasks can move *into* the
terminated group as the limit rises. A naive success-rate comparison would
confound "more turns helped" with "more turns found the trapdoor". Any result
must be reported on the fixed set of 18 task ids from trial_30, with movement
in and out of the terminated group reported separately.

### The thing worth fixing first

Across all 30 tasks the cohort made **zero** calls to `exec_run`,
`environment_resolve` and `environment_activate` — the three tools the
instructions say refuse. The model obeyed the instruction exactly. What ended
40% of the cohort was `browser_run`, which the instructions present as
available and which the fixture backend half-opens: a local `path` read
succeeds, a `search` or `open_url` is refused
(`agentic_v2_fixture_backend.py:272`).

The instructions also tell the model that calling a refusing tool again "will
not change the answer, and the calls are counted against you" — wording that
describes a loop where a refusal is survivable. In this build it is not.

And the model could not have found out for itself. `capabilities_query` is the
tool for asking what the environment has, and the five things it answers about
are commands, runtimes, packages, formats and budgets — none of them is
*tools*. The backend knows the answer, records it as `fixture-local-only-v1`,
and hashes that string into `browser_build_sha256` where nothing can read it.
So the instruction text is the only account of which tools refuse, which makes
the omission load-bearing rather than untidy.

And the omission is not the only place the text and the room disagree.
`exec_run` is half open too, in the opposite direction: the instructions say
all three named tools refuse "every time" and that "no commands run here", and
one command does. `exec_run` with `argv: ["fixture-upper", source,
destination]` returns `returncode: 0` and really uppercases the file. Every
other argv — including `fixture-upper` with the wrong number of arguments —
answers `capability_unavailable` and ends the task.

Swept across the whole contract, giving each of the eight tools the best call
it allows, the count comes out at **two**: only `environment_resolve` and
`environment_activate` have no working call under `offline-full-v1`. The
instructions name three. The third is `exec_run`, and it works.

The model could have found that one out. `capabilities_query(kind:
"commands")` returns `["fixture-upper"]`, and `kind: "budgets"` states the
turn limit outright. So of the three things worth knowing about this room, two
are answerable from inside it and one is not, and the one that is not is the
one that ended twelve tasks. Where the environment does answer, it contradicts
the instruction text.

**None of this touched trial_30.** All thirty obeyed the instruction and never
called `exec_run`, so the `fixture-upper` trapdoor is exposure, not a finding
about that run. It matters here for one reason: it is a second way for a task
to die that more turns gives it more chances to reach, which is the same
argument §4 makes about `browser_run` and the reason the 18 is not a stable
denominator.

### Which layer is actually out of step

It is tempting to call this a harness bug, and it is not. Both code layers
document their own behaviour accurately, and they document opposite things.

`agentic_v2_conversation.py:504-511` keeps a table of the tool failures that
end a run, and says that everything absent from it — `capability_unavailable`
included — is handed back to the model, because "reading a refusal and choosing
something else is the one behaviour stage one exists to measure, so a loop that
gave up at the first refusal would measure nothing". That is the loop the
instructions describe.

`agentic_v2_runner.py:772` never lets that table be consulted. Any dispatch
whose result is not `ok: true` raises out of the tool desk. The runner's own
docstring gives the reason, and the reason is not a preference:
`verify_agentic_v2_result` raises *"agentic v2 tool event follows terminal
result"* for any tool event recorded after an `ok: false` one
(`agentic_v2_provenance.py:423`). A run that continued past a refusal could
not produce a verifiable record of itself. The docstring then names the cost in
so many words — "a model gets one tool mistake per task, and the conversation
loop's ability to show it an error and let it choose again cannot actually be
used" — and names the change that would lift it: the trace schema.

The plumbing between the two is deliberate too. The runner writes its ending
down before it throws, so the conversation's `except Exception` labelling it
`tool_desk_broke` does not become the task's verdict. Checked in the record:
all fourteen desk breaks carry `detail: "running the tool failed: _EndTheRun"`
at conversation level, while the twelve `browser_run` tasks carry
`terminal_error_category: "capability_unavailable"` at task level. The tool's
own error survives, which is the behaviour the comment claims.

So the only text that is out of step with the build is the one the model reads.
That narrows the fixes and separates them by an order of magnitude:

| | what changes | size |
|---|---|---|
| describe the two half-open tools accurately — `browser_run` refuses the network, `exec_run` serves one command | one pinned string | small, and settles the 12 |
| make `capability_unavailable` survivable | the trace schema, its verifier, and the conversation table | large, and explicitly flagged in-code as separate and reviewable |

The second is not the cheap one-line change an earlier draft of this file
implied by listing it beside the first. Either is its own intervention with its
own run id; only the first is worth doing before the limit question.

### It gets worse on the backend this is all waiting for

`AgenticV2MicroVMBackend.browser_run` refuses **every** operation, including
`open_local`, and says why: the guest has chromium and the file is on the work
disk, but nothing starts it, collects what it rendered, or bounds how long it
runs, so a hash of a file the model already has "would look like a browser
having run".

That is the right call and it widens the trap. On the fixture backend a local
`path` read succeeds; on the real one it does not. This cohort happens not to
notice — all twelve went straight to the network and never made a local read —
so the measured effect on these thirty tasks is the same twelve either way.
The exposure is not the same. Whatever fraction of the 220 would have used
`browser_run` to open a local file is failing silently today only because
these thirty did not try.

So settling `browser_run` is not tidying ahead of the limit question. It is a
precondition for the real backend being usable at all, and it is the one item
on that path that needs no access change.

## 5. What judges the outcome

Nothing model-shaped. `success` means `finalize` was called and its artifacts
opened — mechanical, checkable in the record. **That measures completion, not
quality.** Deliverable quality would need grading, and trial_30's
`grading_approved_maximum_usd` is `null` with a written reason. Any claim from
this comparison is a claim about whether the loop finishes, and must be
labelled as such.

## 6. Declared versus controlled

The limit is genuinely controlled: the harness's own budget records
`model_calls_allowed` and `model_calls_made` per attempt, so the condition can
be verified from the artifact rather than trusted from the config. This is the
one axis in this experiment that does not need a caveat.

## 7. What the instruments measure

Turn usage from `conversations.conversations[*].budget_after`. Cost from the
ledger, one `--ledger` per leg, priced by the shared table — which must not be
edited while any leg is in flight. Completion from `status`. No unit
conversion anywhere, so no conversion to get wrong.

## 8. Whether the input favours the intervention

The 30 tasks were fixed before the limit question was raised, so the cohort was
not chosen to make a higher limit look good. It is not a random sample of the
220 and the comparison inherits whatever selection it carries; that is a
limit on generalising to full_220, not a bias toward the intervention.

## 9. When to stop — and the wall this hits

Priced against the real 30-task cohort through the plan's own guard, not
extrapolated:

| tool calls | model calls | trial_30 ceiling | % of the $200 approval | may start |
|---|---|---|---|---|
| 4 | 5 | $34.77 | 17.4% | yes |
| 6 | 7 | $69.06 | 34.5% | yes |
| **8** | **9** | **$114.60** | **57.3%** | yes — the control; actual spend was $6.13 |
| 12 | 13 | $239.49 | 119.7% | **no** |
| 16 | 17 | $409.43 | 204.7% | **no** |
| 32 | 33 | $1539.78 | 769.9% | **no** |

**Under the approval that exists, only limits at or below the control may
start on 30 tasks.** The interesting direction is the one that is closed. An
upward comparison needs either a smaller paired cohort with its own `stages.`
entry and its own approved amount, or a new approval. Note the gap between
ceiling and reality — trial_30 spent 5.4% of its ceiling — so the ceiling is
what gates the start, not what the run would cost.

Stopping rule: if the effect on the 18 does not exceed the repeat spread, the
limit stays at 8 and the question is closed.

## 10. The gap that makes this not-ready

**The repeat spread has never been measured.** trial_30 ran once. A bounded
effect of about five tasks in thirty is exactly the size that a single repeat
of the same settings could produce on its own. Comparing two single runs would
produce a number that cannot be told apart from noise, and the fact that it
came out of a correctly-configured harness would make it more convincing than
it deserves to be.

---

## Verdict

Not ready to run, and the blocker is not money.

In order:

1. **Settle `browser_run`.** It removes 40% of the cohort for a reason
   unrelated to the limit, and what is wrong is the instruction text rather
   than the harness — the cheapest thing in the area to correct. Own run id,
   own record.
2. **Measure the repeat spread** at the control setting, so a difference has
   something to be compared against.
3. **Then** run the limit comparison, on the fixture backend, on the fixed set
   of task ids from trial_30, reporting movement into and out of the
   terminated group separately from the success count.

If the comparison is wanted before step 2, it can still run — but its output
is a description of two runs, not a measured effect, and it must be written
that way.

## The record this would keep

```
intervention   tool_calls_per_attempt, and nothing else
conditions     control = 8 (trial_30's 30 task ids, fixture backend)
               variant = one value, new config file, new run id
axes           moving: the limit. fixed: backend, refusal behaviour, model,
               max_output_tokens_per_turn, retry policy, max_result_bytes,
               instructions, cohort
adjudication   finalize called and artifacts opened. Completion, not quality.
               No judge, so no judge to validate
input          30 task ids fixed before the question was raised; not a random
               sample of the 220
unit           tasks completed out of the 18 the limit can reach; USD from the
               ledger
stop           effect below the repeat spread → the limit stays at 8
known          the 18 is not stable across conditions; the repeat spread is
confounds      unmeasured; the cohort is not representative of the 220
```
