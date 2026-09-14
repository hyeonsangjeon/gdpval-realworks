# Real isolated V2 — what is connected, what is missing, and what only a host can answer

Written before any code was changed for it, so that the list of gaps is the one
that was found rather than the one that survived the work.

Three words are used strictly below and never interchangeably:

- **code implemented** — the path exists and is exercised by tests.
- **fixture-tested** — the production class ran, with a scripted boot injected.
  This proves the wiring. **It proves nothing about isolation.**
- **real-host-tested** — a guest actually booted. Nothing here is this.

---

## 1. What was executed to establish the gap

Every claim in this section was run, not read.

**(a) The cohort path cannot construct the isolated backend, and the shortfall
is exactly two arguments.**

```
microVM required keyword-only args : ['root', 'profile', 'image', 'boot_one_command']
fixture required keyword-only args : ['root', 'profile']

AgenticV2MicroVMBackend(root=..., **driver_kwargs)
  -> TypeError: missing 3 required keyword-only arguments:
     'profile', 'image', and 'boot_one_command'
```

`AgenticV2ScriptedRunner` already passes `profile` and `budget_caps` into the
factory (`core/agentic_v2_runner.py:544-552`). So of the three, one is already
supplied and **the real shortfall is `image` and `boot_one_command`** — the two
that cannot be produced without a host. Everything else the isolated backend
needs is already flowing: root, profile, budget caps, per-attempt workspace,
staged reference files.

**(b) The refusal that stands in front of it is deliberate, not an oversight.**

`scripts/run_agentic_v2_stage.py:364` pins `BACKEND_IN_USE =
AgenticV2FixtureBackend`, and `environment_note` (`:374`) raises `StageRefused`
for any other class, with the reason written out: the run record's
"what was and was not real" sentences are handwritten per backend, and adapting
them automatically is how a record comes to describe something it was not.
Swapping the constant is explicitly *not* sufficient, by design.

**(c) The availability table already knows both backends.**

| tool | fixture | microVM |
|---|---|---|
| workspace_apply | works | works |
| verify_public | works | works |
| capabilities_query | works | works |
| finalize | works | works |
| **exec_run** | partly | **works** |
| **browser_run** | partly | **refuses** |
| environment_resolve | refuses | refuses |
| environment_activate | refuses | refuses |

Two capabilities move, **in opposite directions**. That is one object's
properties, not two dials, so it cannot be made a single-axis change.

**(d) The backend switch does not recover the dominant failure cause.**

From trial_30's own downloaded artifacts (run `34671538199`, all three shards):

```
all tool calls : workspace_apply 254, verify_public 14, browser_run 12,
                 finalize 11, capabilities_query 5, (no tool named) 9
browser_run    : ('operation','query') not-ok  -> 8
                 ('operation','url')   not-ok  -> 4
                 ('operation','path')          -> 0
distinct tasks calling browser_run                -> 12
exec_run calls in the entire cohort               -> 0
```

All twelve used the two operations that need a network. **Both backends refuse
both.** So the twelve tasks that `browser_run` ended fail identically on the
isolated backend. If the reason for wanting a host were task counts, this is the
measurement that says it would not deliver them.

The converse must be stated just as plainly: `exec_run` was called **zero**
times, and that is *not* evidence that opening it changes nothing. The model was
told `exec_run` was shut and obeyed. This cohort is silent on what the model
does when told it works.

**(e) No real boot is possible on this box.**

`/dev/kvm` absent, no `vmx`/`svm` in `/proc/cpuinfo`, process inside a Docker
cgroup. Nothing here can be made to boot a microVM by any change to this
repository.

**(f) One integration risk checked and cleared.** The isolated backend writes
command streams into `.gdpval/exec/NNNN/` *inside the same workspace* the cohort
harvests. V2 collection takes its file list from the declared result
(`core/agentic_v2_deliverable_collection.py:224`, `_files_from(result)`), not
from a workspace sweep, so exec records and staged `inputs/` cannot leak into
deliverables. No change needed.

---

## 2. The design gate

### What changes depending on the answer

The decision is **whether to ask the owner for the two-role grant**, and the
answer is not "yes if the code works". (d) above splits it:

- if the goal is **isolation integrity** — a guest that actually boots, an
  `exec_run` that actually executes, containment evidence that is the run's own
  rather than inherited from a stage — the grant is the right ask.
- if the goal is **more completed tasks**, the grant targets a cause responsible
  for **0 of the 19** trial_30 failures, and the right next move is the
  browser/turn-limit work instead, which needs no access change at all.

These are different actions, so the question is worth answering.

### What would falsify the claim being made

The claim the code work asserts is narrow: *given a real `boot_one_command` and
a real `image`, the cohort path runs end to end.* It is falsified if any of
these seams fails with a scripted boot injected into the real backend class:

1. approved isolated backend selection refuses without an approval, and
   constructs with one;
2. `exec_run` → exit status / stdout / stderr / `meta.json` reach the workspace;
3. an absent `/out/exit_status` is reported as an error and **never** as
   `returncode: 0`;
4. staged reference files are present in the workspace the guest is handed;
5. timeout, cancel and cleanup behave, and a purged workspace is collected
   before it is purged;
6. resume skips what the journal says is done;
7. per-task cost attribution survives — reservation and settlement agree.

### Axes

- **moving:** the backend object. Its `exec_run` and `browser_run` verdicts move
  together and in opposite directions (see (c)); this is named, not netted out.
- **fixed:** model, deployment, resource, task set and their hashes, prompt and
  instruction derivation, budget caps, staging rules, workspace file limit.

### Denominator

30 for any trial cohort, enforced by `bind_stage` — a stage whose size differs
is refused as a different experiment, not accepted as a small one.

**The three input-starved tasks stay in the denominator as input limitations.**
`38889c3b` names one file of 33,554,432 bytes against a 1,048,576-byte workspace
limit and received none; `3a4c347c` and `01d7e53e` each lost a multi-megabyte
`.docx`. Those are properties of this environment. Counting them as model
failures — or as successes — would be scoring the environment and calling it the
model. The limit is **not** to be raised to improve the count.

### Units

- model spend: tokens actually reported by the provider, priced from the pinned
  table. Real.
- **boot cost: unknown.** No boot timing or price is recorded anywhere in this
  repository — searched, nothing found. One boot per `exec_run` call is the
  design. Until a boot is measured this stays **partial, never zero**, and no
  total may be presented as complete.

### Repeatability

**Unknown, and not closeable from the request that is actually sent.** The
request carries seven keys — `model`, `instructions`, `input`, `tools`,
`max_output_tokens`, `parallel_tool_calls`, `timeout`. No `temperature`, no
`top_p`, no `seed`. So "same conditions twice" can be asserted of the input and
of nothing else, and no spread measured here separates backend effect from
deployment variability.

### Negative controls

Every acceptance check above ships with a deliberate defect that must make it
fail: a boot record with no exit status that must not become `returncode: 0`; an
approval with a blank approver; an image whose hashes are not hashes; a resume
that is handed a journal for a different run; a settled call whose retry kind
disagrees with its reservation.

### Run list

Finite and, at this stage, **empty of paid runs**. Offline acceptance checks
only. A five-task real compatibility check is on the list but **gated** — it may
not be dispatched until a host exists and admission is opened deliberately.

### Stop rules

- any acceptance check failing stops the work rather than being skipped;
- no brake is loosened to make a check pass — not `production_activation`, not
  the workspace file limit, not the `exec_run` guards, not `environment_note`;
- if a real run is ever approved: stop on the first task whose cost receipt
  cannot be settled, because an unattributable charge is the one failure that
  gets worse by continuing.

---

## 3. What is being built now, and what is deliberately left unwired

**Built (offline, fail-closed):**

- one reviewable place that turns an explicit approval into the isolated
  backend's construction inputs, and refuses to select it without one;
- the handwritten `environment_note` sentences for the isolated backend, which
  `environment_note` currently and correctly refuses to invent;
- a way for the cohort runner to receive `image` and `boot_one_command` — the
  two missing arguments — with the default path unchanged;
- the seven acceptance checks above, against the real backend class.

**Deliberately left unwired:**

- `admitted_identity` is **computed and verified against the backend's own
  identity, and not passed to the runner.**
  `test_nothing_in_this_repository_declares_a_non_default_identity` stays green
  *truthfully*: admission remains possible and nothing does it. Forwarding it
  while no host exists would retire a standing safety claim in exchange for a
  parameter no run can use.
- `production_activation` stays `"disabled"` in every manifest.
- the two guards that keep V2 out of the ordinary pipeline are untouched:
  `step2_run_inference.py:317` refuses the `agentic_sandbox_v2` execution mode
  outright, and `core/executor.py:622` admits only
  `AgenticV2IsolatedFixtureRunner`. Both refuse on the grounds that the
  foundation is **model-free**, which is a narrower claim than the one
  `core/agentic_v2_exec_boot.py`'s docstring makes about them — it calls them
  guards on opening `exec_run`, and neither file mentions `exec_run` at all.
  Checked because the docstring was about to be quoted.

### 3.1 One of those two decisions was reversed during the work (2026-09-14)

The first bullet above no longer describes the code. It is left standing
because a preregistration that gets quietly edited to match the outcome is not
a preregistration. What changed, and why:

**`admitted_identity` is now forwarded.** `build_runner_factory` takes it and
hands it to `AgenticV2ScriptedRunner`; the stage script passes whatever
`select_backend` returned, which on every existing path is `None`.

**Why the original reasoning was wrong.** It treated
`test_nothing_in_this_repository_declares_a_non_default_identity` as a safety
property. It was not one. That test read every module's *source text* for the
string `admitted_identity`, so what it actually guaranteed was a spelling — and
the guarantee it bought was that on the day a guest is admitted for real,
someone would have to edit the wiring layer, on a booted host, under time
pressure, with no test able to run. Deferring a change to the moment it is
hardest to review is not caution.

**What replaced it, and why it is not weaker.** The old test forbade the
argument from being mentioned. The new one,
`test_only_one_module_computes_an_identity_and_it_refuses_by_default`, holds
the set of modules allowed to mention it to exactly three, names each one's
role, **and then calls `select_backend()` and asserts the identity it returns
is `None`.** The first half is the same spelling check, narrowed from "nobody"
to a named three; the second half is a behavioural assertion the old test could
not make. The property that matters — *nothing in this repository admits a
non-default identity* — is now checked by running the code rather than by
reading it.

**What did not change.** `select_backend()` with no approval still returns the
fixture with `identity_to_declare=None`, so every existing run is
byte-identical. Producing a non-`None` identity still needs a written approval
naming an approver *and* a stage C2 artefact whose kernel, rootfs, firecracker
and jailer all still verify on the running host — neither of which exists here,
and the second of which cannot be produced without `/dev/kvm`.

**Cost of the reversal: none.** No model call, no boot, no dispatch.

The second bullet was not reversed. `production_activation` is still
`"disabled"` in every manifest, and the two pipeline guards are untouched.

---

## 4. The remaining external block, stated once

From `tasks/0822_saturday/HOST_PERMISSIONS.md`, which is bound to its survey
artifact by `tests/test_the_host_permissions_report_matches_its_survey.py`:

> **Principal** — the app registration behind `secrets.AZURE_CLIENT_ID` /
> `vars.AZURE_AI_EXPECTED_CLIENT_ID`, holding 2 role assignments, both
> **Cognitive Services OpenAI User**, scoped to the Foundry account.
> **Scope** — a resource group the owner creates first.
> **Action** — **Virtual Machine Contributor + Network Contributor**, both at
> that resource-group scope. Nothing at subscription scope, no Owner, no
> `Microsoft.Authorization` write.

Twelve actions were measured, all denied; ten of them block, every one at
resource-group scope. This is reported, not requested and not performed.

---

## 5. Where the seven acceptance checks stand (2026-09-14)

Written after the work. The word in the right-hand column is from the strict
list at the top of this file, and **none of the rows say real-host-tested.**

| # | seam | state |
|---|---|---|
| 1 | approved selection refuses without an approval, constructs with one | code implemented, fixture-tested |
| 2 | `exec_run` → exit / stdout / stderr / `meta.json` reach the workspace | code implemented, fixture-tested |
| 3 | absent `/out/exit_status` is an error, never `returncode: 0` | code implemented, fixture-tested |
| 4 | staged reference files are in the workspace the guest is handed | code implemented, fixture-tested |
| 5 | timeout / cancel / cleanup, and collection before purge | code implemented, fixture-tested |
| 6 | resume skips what the journal says is done | code implemented, fixture-tested |
| 7 | reservation and settlement agree per task | code implemented, fixture-tested |

Rows 1–5 are covered by
`tests/test_the_isolated_backend_is_selected_only_by_an_approved_boot.py`, and
rows 6 and 7 by four further tests in the same file that drive `run_manifest`
with this backend underneath it rather than with a stand-in runner. That
distinction is the whole point of the two rows: the driver's own suite already
checks resume, but a stand-in has no machine, so it cannot say that a skipped
task boots nothing. On the fixture a repeated task is a repeated row; here it
is a second machine for work already paid for.

Seventeen deliberate defects were injected into the production modules one at a
time — twelve into selection and the boot reader, five into the driver and the
journal — and **all seventeen were caught** (`missed: 0` both runs, every file
restored byte-for-byte, baseline green after each restore).

Rows 6 and 7 were untestable before this work because the stage script could
not construct the isolated backend at all. They became testable with row 1.

**What all seven rows share:** a scripted boot stood in for a guest. They say
the wiring holds. They say nothing whatsoever about isolation, and no row here
may be cited as evidence that anything was contained.
