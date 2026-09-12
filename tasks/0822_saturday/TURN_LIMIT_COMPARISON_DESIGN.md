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
`max_result_bytes`, same instructions — **and the same replay format**. That
last one is not a setting and does not appear in any config file, which is
exactly why it is written down here: `_input_for` decides what the model is
shown of its own history, changing it changes the input at every turn, and a
run that moved it alongside the limit could not separate the two. See §4.

## 4. What the limit can actually reach

The cohort does not divide the way the disposition labels suggest. Read from
`run_record.json` — from each attempt's `budget_after` and the `tool_name` on
each turn, not from the labels:

| | tasks | what happened |
|---|---|---|
| ended on `browser_run` | **12** | one call, reaching the network — 8 a `search`, 4 an `open_url`. Refused, task over. 2–5 of the 9 calls allowed. None retried. All 12 failed |
| ended on `workspace_apply` | **2** | same terminal refusal, different tool. One was rescued by a retry, one also hit the ceiling and failed |
| ran out of calls, desk never broke | **7** | `stop_reason: turn_limit_reached`. 3 rescued by a retry, 4 failed |
| stopped without a tool call | **2** | not the model giving up — see below. Both failed |
| finished inside the limit | **7** | all succeeded. Two of them on their ninth and last call |

That is 30 tasks, 11 successes and 19 errors, which is trial_30's headline.

An earlier draft of this table read 9 / 2 / 5 for the last three rows. The 9
came from counting attempts that used every call in their budget, which is not
the same question: two tasks used **9 of 9** and finished normally, calling
`finalize` on the last call they had. Counted by `stop_reason` — the field that
says why the loop stopped — the ceiling group is 7 and the finished group is 7.
The two are in the finished group here, and they are the clearest candidates
for a higher limit helping, which the old split hid.

Two things follow.

**The limit can only act on 18 of the 30 tasks.** The twelve that ended on
`browser_run` were ended before the ceiling was anywhere near. Of the eighteen
that remain, **8 hit the ceiling in some attempt and 3 of those already reach
success through a retry** — so the visible effect is bounded at five tasks out
of thirty before any noise is considered. (Ten of the 18 *used* every call;
the two that finished on the last one are not tasks a higher limit rescues.)

**The 18 is not a stable denominator — but less unstable than it looks.** The
worry is that a model given more turns has more chances to reach `browser_run`
and be terminated, so tasks move *into* the terminated group as the limit
rises, and a naive success-rate comparison confounds "more turns helped" with
"more turns found the trapdoor". That worry is arithmetically sound and the
cohort does not support it. See "Neither trapdoor is a late-conversation
event" below. Either way the reporting rule is the same: results go on the
fixed set of 18 task ids from trial_30, with movement in and out of the
terminated group reported separately from the success count.

And there is a second ending that removes tasks for a reason unrelated to the
limit. Five of the 18 hit the "stopped without a tool call" ending, three of
them in the same task as a ceiling hit, and **none of the five succeeded**.
What that ending is, is set out next.

### The fifth ending, which is the harness finishing its own sentence

`stop_reason: model_stopped_without_finishing` reads as the model walking away,
and the dataclass behind it says so in as many words. Nine attempts across five
tasks ended that way. None of them is a model giving up, and there is no
give-up text to preserve.

Every one of the nine carries a note of the same shape:

```
the model stopped without committing an answer:
I asked for workspace_apply as call call_U8QbjyWEKeR6j4I7sKplBSdK.
```

That sentence is not the model's own phrasing. It is the harness's.
`AzureFoundryVoice._input_for` rebuilds the whole conversation before every
turn — correctly, and the budget is worked out on the assumption that it does —
but what it rebuilds is a paraphrase. Each of the model's earlier turns comes
back as one line of prose in exactly that form, and **the arguments of the call
are dropped**. The tool's answer is replayed in full as JSON; the request that
produced it is not. So a model eight turns in has eight lines telling it that
it asked for `workspace_apply`, and no record of which file it read or wrote.

Shown that format repeatedly, the model eventually produces the next line of it
as text instead of emitting a function call. `next_turn` looks for a
`function_call` item, finds none, and returns `GaveUp` carrying whatever the
model said — which is how the harness's own replay format ended up recorded as
the reason a task stopped.

Four things say this is imitation rather than a model choosing to stop, and all
four are in the record:

- the call ids in those notes are well-formed and **none appears anywhere
  earlier in its own conversation**. They were invented, not repeated
- all nine name `workspace_apply`, which is 254 of the cohort's 296 tool calls
  and so by far the most repeated line in any replayed history
- all nine are 29–32 output tokens: one sentence, not an explanation
- it never happens on the first turn. The earliest is the third. With no
  history there is nothing to imitate

`test_the_model_is_shown_a_paraphrase_of_its_own_turns.py` pins both halves —
the replay format and the no-function-call branch — without calling a model.

This matters for the limit question, though not in the way I first wrote it.
The information loss it comes from does grow with the turn count: the extra
turns a higher limit buys are turns whose history is thinner than the ones
before them. But the failure itself is not a late-conversation event — see
directly below — so "more turns means more of this" is not what the cohort
shows.

It is also a defect rather than a stated condition, which separates it from
everything else in this section. `browser_run` and `exec_run` behave as built
and are described wrongly to the model; this one nobody chose. It is the
strongest candidate for the first fix, and like the instruction text it needs
no access change — but it changes the model's input, so it is an intervention
on a pinned run condition and gets its own config file and run id.

### Neither trapdoor is a late-conversation event

Both of the "more turns means more chances to die" arguments in this file are
mechanically plausible, and neither survives contact with the cohort. Counting
each ending against the conversations that actually reached that turn — the
denominator shrinks as conversations end, which is what makes this a hazard
rate rather than a share of the total:

| turn | conversations reaching it | `browser_run` | | stopped without a tool call | |
|---|---|---|---|---|---|
| 0 | 50 | 0 | — | 0 | — |
| 1 | 50 | 4 | 8.0% | 0 | — |
| 2 | 45 | 6 | 13.3% | 1 | 2.2% |
| 3 | 38 | 1 | 2.6% | 4 | **10.5%** |
| 4 | 32 | 1 | 3.1% | 3 | 9.4% |
| 5 | 26 | 0 | — | 1 | 3.8% |
| 6 | 24 | 0 | — | 0 | — |
| 7 | 21 | 0 | — | 0 | — |
| 8 | 19 | 0 | — | 0 | — |

`browser_run` fires at turns 1–2 and never after turn 4. The paraphrase ending
fires at turns 2–5, needs history to exist at all, and never after turn 5.
**Twenty-four conversations reached turn 6 and none of them died to either
cause.** On this cohort the extra turns a higher limit would add are the turns
where nothing went wrong.

That is a real result and it should not be over-read. Nine and twelve events
are few, and the denominators thin out: zero events in the 24 conversations
that reached turn 6 is consistent with a true hazard of up to about 12%. So
this does not show the hazard *is* zero late on. It shows the cohort gives no
support to a hazard that rises with turn count, which is what the "unstable
denominator" worry needs. The worry stays in the design as something to report
on, and it drops out of the argument for doing the two fixes first — those
stand on removing 17 of 30 tasks for reasons unrelated to the limit, which
does not depend on when the removals happen.

A repeat at the control setting (§10) would sharpen this, because it measures
the same hazards on the same tasks a second time. That is one more thing the
unmeasured repeat spread is currently costing.

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
about that run. It matters here for one reason: it is a third way for a task to
die on a single wrong call, in a cohort where two such ways already removed 14
of 30. Whether extra turns make any of them more likely is a separate question,
and the answer on this cohort is no — see "Neither trapdoor is a
late-conversation event" above.

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

### The instruction list matches neither backend

Put the two side by side and the list the model is given fits neither the
backend it ran against nor the one it is waiting for.

| tool | fixture (`offline-full-v1`) | microVM (the destination) | instructions say |
|---|---|---|---|
| `exec_run` | one command, `fixture-upper` | **works** — boots a machine per call | refuses |
| `browser_run` | 3 local ops served, 2 network refused | **refuses all five** | available |
| `environment_resolve` | refuses | refuses — the guest has only loopback | refuses |
| `environment_activate` | refuses | refuses — nothing to activate | refuses |
| no working call at all | **2 tools** | **3 tools** | 3 tools |

The two the text gets right on both backends are the package pair. `exec_run`
is wrong on both, in opposite directions, and `browser_run` is wrong on both
by omission — partly on the fixture, entirely on the real one.

That matters for the order of work. When the real backend arrives, the
instruction text has to change anyway: leaving it as it stands would tell the
model that the one capability the real backend adds — running commands — is
shut, which is the mistake this repository already has a name for. So the
instruction fix is not gate-4 hygiene to be done if there is time. It is on
the critical path to the real backend, and it is the only thing on that path
that can be done today.

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

### These prices are for the broken replay format

Every figure above assumes the replay described in §4: past turns come back as
one short line of prose with the arguments dropped. That is why they are cheap.
Fixing it means re-sending every argument the model ever passed, on every
subsequent turn, and the cost of that is not small.

Measured against trial_30, from the ledger — which agrees exactly with the
conversation records, 1,140,544 input and 218,697 output tokens, `gpt-5.4` at
$2.50 / $15.00 per million:

| | tokens | at the cohort's prices |
|---|---|---|
| input actually billed | 1,140,544 | $2.851 |
| output actually billed | 218,697 | $3.280 |
| **actual total** | | **$6.131815** |
| input a faithful replay would add | **+719,526** | **+$1.799** |
| would-be total | | ~$7.93, **+29%** |

The 719,526 is an estimate with a stated basis, not a measurement: a faithful
replay re-sends every past argument, so its extra input at turn *n* is taken as
the tokens the model emitted on turns 0..*n*−1. That over-counts slightly,
because output tokens include the model's spoken `why` as well as the arguments.
The magnitude is the point, and the magnitude is tens of percent.

Two consequences.

**The surcharge grows faster than the limit does.** It is the sum of a running
total, so it is quadratic in conversation length while the priced ceilings above
are close to linear. Fixing the replay makes the 12-call row further out of
reach than it already is, not equally so.

**The ceilings must be re-derived after the fix, before the fix's run is
scheduled.** They are the `may start` column, so a fix that lands without
re-pricing would let a run start against a ceiling computed for a cheaper
harness. That is the one ordering constraint this fix carries.

One thing this does not change: the ledger's own `model_cost_usd` column is
zero on all of trial_30's rows, so $6.131815 is a figure derived by applying
the shared price table afterwards, not one the run recorded. It reproduces to
six decimal places, and it is derived rather than read.

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
2. **Fix the replay format.** The model is shown a paraphrase of its own
   turns with the arguments stripped, and finishing that paraphrase as text
   ended five more tasks. Unlike everything else here it is a defect rather
   than a condition somebody chose. It is also the one fix with a price: a
   faithful replay costs roughly 29% more on this cohort, quadratically more
   as the limit rises, so **the ceilings in §9 have to be re-derived before
   its run is scheduled** (§9, "These prices are for the broken replay
   format").

   These two can be fixed in the same run, and probably should be: the goal is
   a platform to measure the limit on, not an effect estimate for either fix.
   What that run may not then claim is how much each one contributed. It is a
   new baseline, and it needs saying that way.
3. **Measure the repeat spread** at the control setting, so a difference has
   something to be compared against.
4. **Then** run the limit comparison, on the fixture backend, on the fixed set
   of task ids from trial_30, reporting movement into and out of the
   terminated group separately from the success count.

If the comparison is wanted before step 3, it can still run — but its output
is a description of two runs, not a measured effect, and it must be written
that way.

## The record this would keep

```
intervention   tool_calls_per_attempt, and nothing else
conditions     control = 8 (trial_30's 30 task ids, fixture backend)
               variant = one value, new config file, new run id
axes           moving: the limit. fixed: backend, refusal behaviour, model,
               max_output_tokens_per_turn, retry policy, max_result_bytes,
               instructions, replay format, cohort
adjudication   finalize called and artifacts opened. Completion, not quality.
               No judge, so no judge to validate
input          30 task ids fixed before the question was raised; not a random
               sample of the 220
unit           tasks completed out of the 18 the limit can reach; USD from the
               ledger
stop           effect below the repeat spread → the limit stays at 8
known          two endings remove 17 of 30 tasks for reasons unrelated to the
confounds      limit — browser_run's trapdoor and the paraphrase ending. Both
               fire early (hazard 0 past turn 5 on this cohort, but only 19-24
               conversations reach turns 6-8, so that is weak evidence);
               the repeat spread is unmeasured; the cohort is not
               representative of the 220; the priced ceilings assume the
               current replay format
```
