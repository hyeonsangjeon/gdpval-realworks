# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are grouped under dated headings (`## [YYYY-MM-DD]`). The
`## [Unreleased]` block at the top stays empty between releases — new
entries land under a fresh dated heading the day they merge to `main`.

## [Unreleased]

### Fixed
- **Four of the six things a containment has to say were never written down,
  and the two that were had three copies that nothing compared.** A set of
  settings is a containment only if it answers where a command may write,
  whether it can reach the network, how much memory it gets, how long it may
  run, who it runs as, and what happens when it exceeds any of those. Two were
  answered. The working directory said `ephemeral-quota` — "there is a quota" —
  and **never said what the quota was**, which is a rule nobody could apply even
  if something were applying rules.

  All six now have a number or a word, and every number that could be derived
  from something already in the repository was derived rather than picked: the
  work disk is **256 mebibytes**, twice what the tool layer already accepts, so
  the tools can never accept a write the disk cannot hold; the clock is
  **1,200 seconds**, the same per-task timeout the other three run places are
  held to, so this column cannot lose a task to a stricter deadline than its
  neighbours; the user is **`jailer-unprivileged`**, so "not root" is
  checkable; a breach is **`stop-and-report`**, because a rule that has been
  exceeded is a containment that is not holding. A test refuses any rule whose
  name ends in a unit but whose value is not a positive whole number — the
  exact shape the working directory had.

  **Memory is the one number with nothing behind it, and it says so.** 4,096
  mebibytes was picked. None of the three run places in the comparison caps
  memory at all, so a cap here makes this column stricter on an axis the
  comparison does not otherwise control. That is written into the rule's own
  documentation, and a test fails if the admission is ever removed.

  **Three copies became one.** The rules were stated in
  `REQUIRED_MICROVM_POLICY`, in the signed supply-chain policy on disk, and in a
  hand-written dictionary inside the supply-chain validator — with different
  names in each (`read_only_rootfs: true` in one, `rootfs: "read-only"` in
  another), which is what made a disagreement hard to see by eye. Nothing
  compared any two of them, so a rule could be weakened in one place and left
  standing in the others with every file still validating. The validator's copy
  is now derived from the first, and a signed policy that disagrees is refused
  with a message naming the rule and both places it is written down.

  **Every rule is now refused when weakened** — 33 tests covering the network
  opened to an allowlist or the host, a writable root filesystem, a persistent
  working directory, any limit quadrupled, the user set to root, a breach rule
  that carries on, the runtime changed to Docker, the containment marked
  optional, and any rule deleted outright.

  **What no test does is start a machine, exceed a limit and watch it stop.**
  That test needs a machine that can host the containment — none of the three in
  play can — and code that turns these rules into arguments for starting one,
  which nobody has written. `tests/test_agentic_v2_containment_rules.py` says so
  in its own opening lines rather than quietly omitting it, because a passing
  test named after a thing that never happened is how an unenforced rule comes
  to look enforced.

- **A rule nothing applies was being reported as met.** The readiness report had
  one field for "the containment is available", and it was answering two
  different questions at once: *could this machine host the containment*, and
  *is the containment actually in place*. Every policy rule now answers "cannot
  be established here" instead of "met", and says which of the two reasons
  applies.

  They are two fields now because they are fixed by two different things. One
  is fixed by finding or building a machine, and is read off the machine. The
  other is fixed by writing the code that applies the rules — a fact about this
  repository, so the answer is the same on every machine, and a better machine
  does not change it. A reader of the refusal can now tell whether to go and
  find a machine or go and write code.

  This makes the report **strictly more cautious than before**: the refusal now
  stands even on a machine meeting every hardware requirement. No refusal was
  removed, nothing was switched on, and the three safety blocks are exactly as
  shut as they were — `exec_run` still answers `capability_unavailable`, and
  both guards still reject the mode.

- **The cost arithmetic had no way to express a perception call, so marking's
  two extra models could not be counted even once they were named.** The
  previous change proved the gap existed: `grading_configs/default_v2.yaml`
  lets marking call `gpt-5.4` to **read a picture up to 72 times per task** and
  `gpt-audio-1.5` to **listen to sound up to 3 times per task**, and the sum
  mentioned neither. Naming them in the check was as far as that change could
  go — `CostAssumptions` had nowhere to put them, so no plan could close the
  gap by raising a number. This builds the arithmetic.

  A plan may now carry `grading_perception`, naming per kind of perception
  which model is called, how many times per task, and how much one call sends
  and writes back. Call counts are checked against the marking settings and
  refused when they sit below them. **Perception is counted per task, not per
  scoring line**, because that is how the settings cap it and because one
  picture can answer several scoring lines at once.

  **Two different refusals, kept apart, because they are fixed differently.**
  A model with no published price cannot be priced at all. A model whose price
  is known but whose call size nobody has measured cannot be priced either —
  but for a reason a measurement would settle. Both refuse; neither is
  silently a zero. `check_cost_ceiling` gained the second refusal and the
  printed line names what is missing from the amount rather than presenting a
  partial figure as a whole one.

  **The picture numbers come from measurement, and from the largest one.**
  Across every marking run committed to this repository, 817 scoring lines
  really called the picture model. The largest single call sent **23,139
  tokens** and wrote back **3,202**; the plan records 24,000 and 4,000. The
  means were 2,123 and 349, so this repository's usual "measured mean, doubled"
  convention would have produced **4,246 — below a call that has already
  happened.** That is exactly the class of error the previous change fixed, so
  the convention is deliberately not followed here. Nothing in the repository
  caps a perception reply at all: `core/perception/vision.py` and
  `core/perception/audio.py` both call the Responses API without
  `max_output_tokens`, so even the measured maximum is a floor rather than a
  lid, and the plan says so.

  **The sound numbers are left blank on purpose.** 116 scoring lines were
  routed to sound across every committed run and the sound model was called
  **zero** times — the text judge decided all of them. There is no measurement
  to draw on, so writing a number would invent evidence and writing 0 would
  claim the calls are free. A blank refuses.

  **A refusal written years ago fired for the first time.** Because the sum now
  hands `gpt-audio-1.5` to the price table, `check_cost_ceiling`'s existing
  "an unpriced model would otherwise be counted as free" refusal finally
  reaches it.

  The plan's own marking numbers were raised to the limits the settings allow
  while the arithmetic was being fixed, since leaving them low would have kept
  the check reporting a wrong number instead of a real one: 1 marking call per
  scoring line → **11**, and 1,000 tokens of reply → **2,400**. Five reported
  problems are down to two, and both are the same unused model.

  **The total rose from 43.77 to 363.59 United States dollars and nothing got
  more expensive.** The same calls were always allowed; the old figure counted
  marking at a ninth of its limit and pictures not at all. **No approved amount
  was changed or added**: 32.23 stands exactly as the owner set it, 363.59 is a
  computed figure and not an approval, and the gap between them is the owner's
  decision to make.

- **The half of the cost ceiling that prices marking was never a ceiling, and
  it hid two whole models.** `core/execution_envelope_cost.py` opens by saying
  every number in it is a ceiling and not a forecast. The half that prices
  running the tasks keeps that promise — it reads how far the settings let a
  request go and charges it. The half that prices marking rested on three
  numbers an operator typed into the plan by hand, and this repository's own
  marking settings already state limits that two of them can be checked
  against. Both were under. The plan allowed **1 marking call per scoring
  line** where `grading_configs/default_v2.yaml` lets the model be asked **11**
  times about one line, and **1,000 tokens of reply** where one reply may run to
  **2,400**.

  The worse half is what the sum never mentioned at all. The same settings let
  marking call `gpt-5.4` to **read pictures up to 72 times per task** and
  `gpt-audio-1.5` to **listen to sound up to 3 times per task**, and neither
  model appeared anywhere in the cost sum. `check_cost_ceiling` has always
  refused a run whose model has no published price, on its own stated grounds
  that "an unpriced model would otherwise be counted as free" — and
  `gpt-audio-1.5` is not in the price table. Because marking never named it,
  **that refusal never had the chance to fire.** An unpriced model was reachable
  from an approved run and counted as costing nothing.

  `batch-runner/core/execution_envelope_grading_cost.py` now opens the marking
  settings the plan will really be marked with, reads the limits out of it, and
  reports every place the written sum sits below one. The plan names that file
  in a new `grading_config` key; **a plan that marks answers and names no
  settings file is refused rather than passed**, because nothing having looked
  is not the same as the numbers being high enough.

  **One number is not pinned this way and is not pretended to be.** How long a
  marking call's input runs follows the answer being marked and nothing in the
  settings caps it, so `grading_input_tokens_per_call` stays an observation
  drawn from runs that really happened, and `describe_grading_caps` says so in
  the output rather than letting a reader assume the whole sum became a ceiling.

  The limits are read from code, not from documentation. A test builds the real
  judge through `core/grader.py` from each of the **nine** committed marking
  settings files and fails if any limit it reads differs from the one that judge
  would really apply, so this cannot drift into quoting numbers marking no
  longer uses.

  The printed report changed too. The totals sit under a heading calling them
  the largest possible bill, so once the marking half is known to be short, a
  warning now prints **beside the number** instead of only in the problem list
  further down — the difference between a reader quoting a ceiling and quoting a
  guess. The free check exits 1 as before, now with five more reasons.
  **No approved amount was changed**: 32.23 United States dollars stands exactly
  as the owner set it, and raising numbers to meet the limits would raise the
  total again, so it is left for the owner to decide alongside the amount.

- **The cost ceiling charged a looping request as though it never grew, and the
  approved amount was worked out with that mistake in it.** The shared
  arithmetic multiplied one turn's input by the number of model calls. That is
  right when each attempt is a fresh request, and wrong for any request where
  the model is asked again after each tool result: every later turn re-reads the
  whole conversation before it, so what was written on turn one is charged again
  on turns two, three and onwards. Counting a conversation as it grows raises
  the Azure code interpreter column from 4.83 to 14.06 United States dollars and
  the whole five-task, three-place run from 32.23 to 43.77 — **above the 32.23
  approved for it on 2026-08-25**. So the run could have been allowed to start
  and then billed more than was approved, with every check reporting it as
  within budget. Nothing was spent under the wrong figure, because the Azure run
  place has never been reachable from the machine it was attempted from. The
  free check now refuses, which is the safety mechanism working; the plan file
  records the three ways out and leaves the choice to the owner. The two
  single-turn run places are unchanged to the token, and a test holds that in
  place. `max_tool_result_tokens_per_turn` is now a required assumption per run
  place: leaving it out stops the count rather than quietly standing in a zero.

### Added
- **The containment question that blocked Agentic Sandbox V2 stage three is
  answered, and the answer is no machine.** The specification said whether the
  small isolated virtual machine it requires "is available on the machines this
  would run on has not been established". It is now established by reading
  machines rather than by asserting prose, and it cost nothing: no model was
  called, no command was run, no account was signed in to, nothing was
  installed. `batch-runner/core/agentic_v2_containment_readiness.py` reports,
  per requirement, whether a machine meets it and **why** in a full sentence.
  Three machines are in play and each is a different kind of no. This box has a
  processor that could do it, but sits inside a container with no virtualisation
  device passed through, runs kernel 3.10.102 against the 5.10 that is the
  oldest Firecracker validates, and has neither `firecracker` nor `jailer`
  installed. GitHub-hosted runners are a documented no: GitHub says running a
  virtual machine inside one is "technically possible" but "not officially
  supported", with no guarantee of stability, performance or compatibility —
  **a containment boundary offered with no guarantee is not a containment
  boundary.** The self-hosted `agentic-sandbox` runner is not a no at all: no
  such machine is registered, so the question has no subject, and that is the
  only one of the three a decision could change.

  Four things it deliberately does. It reads the five required settings from
  `core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY` instead of restating them,
  so the check and the rule it enforces cannot drift apart. It **never runs a
  command** to find any of this out — a test reads its own source and fails if
  it ever gains a way to start a process, because a containment check that
  starts processes to decide whether starting processes is safe has the problem
  backwards. It counts "cannot be established" against availability rather than
  for it, so an unanswered question can never be mistaken for a cleared one. And
  it reads `runs-on:` out of every workflow file and fails if a machine is being
  asked for that has no recorded finding, so adding a runner without answering
  the containment question for it is caught by a test rather than by somebody
  remembering. It also distinguishes "not validated" from "forbidden": Firecracker
  does not ban older kernels, it declines to test them, and the report says so.

  Nothing is switched on and no refusal is removed. `exec_run` still answers
  `capability_unavailable`, both guards still reject the mode, and
  `refuse_command_execution` returns a refusal that would clear only once the
  containment genuinely exists somewhere. `scripts/check_agentic_containment.py`
  prints the whole report for free and exits 1. 61 new tests, one of which pins
  a trap this change fell into: a line added above `canonical_sha256` in
  `core/agentic_v2_substrate.py` silently breaks 91 licence tests, because that
  function's starting line is part of a frozen identity, and the error names the
  licence evaluator and never mentions the file that moved.
- **What Agentic Sandbox V2 stage one would cost, worked out for free.** Step
  one of `tasks/0822_saturday/TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md`. A loop's
  bill does not rise in step with the number of turns — it rises roughly with
  the square of it, because the earlier turns are re-read by every later one.
  `batch-runner/core/agentic_v2_stage_one_budget.py` prices the candidate
  settings over the same five tasks, taking the tool-call ceiling and the
  tool-result size from the dispatcher's own code rather than from numbers
  copied into a document. The finding that motivates the table: **the
  dispatcher's own defaults are the most expensive setting available**, at most
  492.67 dollars to run five tasks, against 3.24 for the cheapest setting that
  could still answer the question — over fifty times, from two settings a
  reasonable person would have left alone. `StageOneBudget` then holds a run to
  the figure, refusing the next call at each ceiling and raising rather than
  reporting quietly if one is passed, so the worked-out amount is a limit and
  not a hope. Nothing is approved, nothing is switched on, and all three safety
  blocks stay shut: `scripts/check_agentic_stage_one_ceiling.py` prints the
  table and refuses, reporting first that nothing here can reach a real model —
  established by running the refusing seam and the loop's own refusal, so the
  answer changes by itself when that stops being true. 52 new tests.

### Added
- **The repeated conversation Agentic Sandbox V2 stage one is about now
  exists.** Step two of
  `tasks/0822_saturday/TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md`. Until now the
  runner replayed a list of tool calls written down in advance; a run therefore
  proved that the tools worked, not that a model could choose them.
  `batch-runner/core/agentic_v2_conversation.py` adds the loop itself: ask,
  run the tool it asked for, show it what came back, ask again — with every
  state and every way of stopping named rather than implied. It reaches no real
  model and cannot be made to: `real_model_voice` refuses, and the loop refuses
  any model that says it would be charged for **before** asking it anything, so
  an unapproved paid run cannot start by accident. A test reads the module's
  own imports and fails if it ever gains a route to a paid client or to another
  way of running a task.

  Three things it holds to, each fixed by tests. **A loop with no limit is not
  a loop, it is a leak** — five ceilings (turns, tokens written in one turn,
  wall-clock seconds, cost, and how often one request may be repeated) are
  checked *before* the next call, and a run whose limits are not all set is
  refused rather than run unlimited. **A failure the model is shown is not a
  failure of the loop** — a refused tool call, including one for a capability
  that is not available, goes back to the model to react to; only a limit
  reached, a cancellation, or a broken tool desk ends the run. **What the model
  reasons is not kept** — the model is shown real tool results, but what is
  stored per turn is fingerprints, sizes, token counts and a short stated
  reason, never the reasoning itself.

  Nothing is switched on. All three safety blocks stay shut, and the free check
  now reports the smaller remaining blocker — no way to reach a real model —
  instead of the loop being missing. 97 new tests, covering normal completion,
  every ceiling, cancellation before and mid-turn, timeout, repeated requests,
  corrupted replies, broken desks, unsupported capabilities, and six runs
  against the real dispatcher.

### Changed
- **The Codex question is now half answered, and narrower.**
  `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md` asked whether Codex's own
  agent could be pointed at an Azure AI Foundry deployment using a directory
  sign-in. The authentication half turns out to be documented in general: a
  `model_providers.<id>.auth` table runs a command that prints a token to
  standard output and refreshes it, which is the shape a directory sign-in
  needs. The Azure half is still unconfirmed, and the evidence now leans
  against: `wire_api` documents `responses` as its only supported value with no
  statement that Azure's Responses API accepts that format, Azure appears
  nowhere in the configuration reference, and Amazon Bedrock — which does have a
  built-in provider, its own settings, its own page, and a statement of format
  compatibility — shows that the documentation covers a competing cloud in depth
  when it means to. The column stays empty and is not filled with Azure's own
  agent service, which is a different product. The remaining unknown is written
  down as one checkable question, with the configuration it would use, marked
  clearly as untested.

### Fixed
- **A deployment name does not identify a deployment, and the run-place
  comparison was relying on one.** The plan pinned `deployment: gpt-5.4` and
  said nothing about which Azure AI Foundry account held it; the free check's
  only Azure input was a single word naming the route. Listing the tenant while
  preparing the five-task advance check turned up **two separate accounts each
  exposing a deployment named exactly `gpt-5.4`**, plus a third exposing the
  same model under a different name. The comparison could therefore have run one
  column against one account's `gpt-5.4` and another column against a different
  account's — different region, possibly different model version, possibly
  different content filters — while every check reported that all three used the
  same deployment, and nobody reading the table could have told. The plan now
  pins the account and project, and `batch-runner/core/execution_envelope_azure.py`
  classifies the endpoint settings the run itself would use, with this
  repository's own endpoint rules rather than text matching, and refuses any
  other account or project. Those names are settings the repository already
  records for its own runs, not secrets.
- **The Azure check gave the same answer to three different problems.** "Not
  configured", "configured but pointing elsewhere", and "configured but
  unreachable" all produced "the Azure route profile was not measured" — three
  different fixes behind one unhelpful sentence, and working out which applied
  took a manual investigation. The check now names the specific setting that is
  wrong and prints the exact address that should have been supplied. It also
  reports forbidden fixed credentials and the deprecated combined endpoint
  setting during the free check, instead of letting a run be scheduled and fail
  later on the same point. Everything still reads settings only: nothing signs
  in, contacts Azure, or spends anything. Twelve new tests, including one where
  the settings are well formed, the route is right, the deployment name is
  unchanged, and **only the account differs** — the case that used to pass.

### Added
- **The approved spending ceiling for the five-task advance check is recorded**
  as $32.23 in
  `batch-runner/experiments/execution_envelope/advance_check_plan.yaml`, equal
  to the worked-out ceiling to the cent so that any change making the run more
  expensive pushes it over the line and stops rather than quietly spending more.
  **The check itself did not run and nothing was spent**: the Azure account it
  is pinned to sits in a different Azure tenant from the one signed in, a
  Conditional Access policy refuses the token, and only an interactive browser
  sign-in remains. Two of the three run places were ready; they were **not** run
  on their own, because dropping a blocked run place and proceeding would answer
  a different question from the approved one.
- **Three standalone specifications** under `tasks/0822_saturday/`: pinning the
  Azure resource; a four-stage route for Agentic Sandbox V2 from replaying a
  written script to the model choosing its own next action, with running
  commands deliberately last and behind its own approval and **none of the three
  existing safety guards bypassed or weakened**; and what official documentation
  does and does not say about Codex's own agent. For Codex, a non-interactive
  mode and custom providers are confirmed, but **pointing its own agent at an
  Azure AI Foundry deployment using a directory sign-in is not confirmed** — and
  since every column must share one deployment, that single fact decides whether
  the column can ever be honest, so it stays empty and marked unconfirmed rather
  than filled with Azure's own agent service driving a similarly named model.

### Added
- **The run-place comparison can now start on five tasks in three places, and
  every check that costs nothing to make refuses on every path that matters.**
  `batch-runner/experiments/execution_envelope/advance_check_plan.yaml` holds,
  in one place, everything the three run places share: provider, deployment,
  the model the service must report back, request-format version, both
  instruction texts word for word, the task list, a content fingerprint for
  every input, answer-length cap, time limit, self-review setting, allowed
  retry reasons and attempts, and a standing refusal to change model or
  deployment part-way. **The per-place section is empty on purpose** — nothing
  differs except where the code runs. Three settings drafts pair with it:
  `exp030` (a separate Python process on the server), `exp031` (a Docker
  container), and `exp032` (Azure's code interpreter). **The five tasks were
  chosen by a rule, not by taste, and the rule cannot follow the scores**: it
  reads a committed catalogue built from the benchmark dataset at one pinned
  revision holding task numbers, industries, jobs, expert answer file types,
  reference-file paths, and a fingerprint of the task wording — and no score,
  grade, or verdict at all, which a test proves by walking the whole file. The
  rule sorts by task number and fills five slots in a fixed order without
  repeating a job, giving five formats, five jobs, and four industries. **The
  picture slot is recorded honestly**: no task in this benchmark hands in a
  picture on its own, so the rule's fallback took the smaller-numbered of the
  two that hand in one at all, and the plan says so rather than implying
  otherwise. **The Docker place can no longer quietly become the server
  place** — the silent failure that would have put the server's numbers in the
  container column with nothing saying so. `exp031` pins the container setting
  to `always`, and `tests/test_execution_envelope_docker_containment.py` holds
  it from three directions: it calls the real execution path with the Docker
  service missing and with the image missing and fails if the server runner is
  reached even once; it reads the committed settings file; and it weakens the
  setting in both the plan and the settings file and requires the check to
  refuse. A fourth test records that the default really does fall back, so the
  reason the pin exists stays visible. **The largest possible bill is worked
  out rather than guessed**, with every assumption named beside the measurement
  behind it: at most 1,001 model calls and **$32.23** after a 1.25 safety
  multiplier, of which $14.02 is grading. Reference files count at the
  50,000-character cap the file reader applies; characters count at three to
  the token rather than the usual four; Azure's code interpreter gets eight
  model turns per attempt because Microsoft publishes no limit, but its answer
  length counts once per attempt because the Responses API caps a whole reply
  with one number. **A model with no published price is refused, not counted as
  free**, and a test holds the committed price list equal to the one the
  repository already uses for grading. The command-line front end
  `batch-runner/scripts/check_execution_envelope_advance_check.py`
  exits 1 unless every one of these holds: no setting
  missing; every place on the same deployment, model, wording, task list, and
  input fingerprints — checked by opening the three settings files that would
  actually run rather than trusting the plan; the container unable to fall
  back; no automatic model switch; a paid-run approval on record; and an
  approved amount covering the ceiling. **A missing approved amount is a
  refusal, not a pass.** Reviewing and testing this work found three real defects,
  all fixed: the check could refuse **without printing a reason**, because the
  readiness check keeps its own problem list and only the envelope check's was
  shown; a settings file that simply **omitted the answer-length cap** passed,
  though a missing cap falls back to a built-in default that would have given
  one run place half the answer length of the others; and **nothing checked
  settings the plan does not name** — temperature, the repeatability seed, and
  how hard the model is asked to think would each produce a difference that is
  not the run place, so the three settings files must now agree on all three. The moving parts are
  `batch-runner/core/execution_envelope_tasks.py`,
  `batch-runner/core/execution_envelope_cost.py`,
  `batch-runner/core/execution_envelope_preflight.py`, and
  `batch-runner/scripts/build_gdpval_task_catalog.py`, with 75 new tests, and
  CI runs 3,716 tests green. **The Agentic Sandbox V2 guards were exercised,
  not worked around, and the Codex
  column stays empty rather than being filled by another place. No comparison
  ran, no model was called, nothing was graded, and no published result file
  was touched.**
- **Comparing one GPT model across five places a task can be run is now
  specified, and a check answers "may it start?" without spending anything.**
  `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md` fixes the
  conditions that must be identical everywhere — provider, deployment, the
  model that actually answered, request-format version, both instruction texts
  verbatim, the task list, input-file digests, output and time limits, whether
  self-review is allowed and how often, which retry reasons are allowed, and a
  standing refusal to switch model or deployment on its own. It names no GPT
  version, so a later run picks its own model without editing the document.
  **Each of the five places is graded from code that was read, not assumed:** a
  separate Python process on the server runs experiments today (24 configs, 220
  graded tasks); a Docker container can, but only with its container setting
  pinned to `always`, because `SandboxRunner._execute` otherwise runs the code
  on the host with a warning and would silently turn a container result into a
  host result; Azure's code interpreter is implemented and chosen by 5 configs
  but refuses to start without its route setting; **Agentic Sandbox V2 supports
  structure checks only** — its command-running tool `exec_run` answers
  `capability_unavailable`, no loop lets a model read a tool result and pick a
  next action, and both `_require_runnable_execution_mode` and `TaskExecutor`
  refuse the mode; **Codex has no run path here at all**, and official
  documentation describes neither running its agent loop against an outside
  benchmark nor running it on an Azure AI Foundry deployment, so that gap is
  recorded as missing evidence rather than assumed away. A new readiness
  module and its command-line front end re-derive all of this at runtime:
  they read the registered run modes, import each runner class, and **open all
  three Agentic Sandbox V2 doors to confirm they are still shut**. Without a
  paid-run approval every runnable place is downgraded to blocked and told
  which setting would grant it, and an unavailable place is never substituted
  with a working one. Re-running one model's own code in each place and letting
  each tool use everything it ships with get **separate scoreboards that cannot
  be added together**, and retries are counted in three buckets — an
  infrastructure failure, the model reviewing its finished output, and the
  model recovering mid-conversation with its tools — with a single lumped count
  rejected. The 5, 30, and 220 task stages each require eight decisions fixed
  before any spending. `tests/test_execution_environment_readiness.py` adds 123
  tests, including a dispatcher that reproduces the real Agentic Sandbox V2
  branch with only the paid-run block removed — the check must still notice,
  because that branch refuses for seven different reasons and accepting any of
  them would have let the block be deleted silently. **The check reports
  "ready" only when every place being compared can actually start**, so with no
  approval on record it exits non-zero rather than green-lighting a run. The
  four self-review and retry settings must match when the same code is re-run
  and are free to differ when each tool uses its own features, which is what
  the second comparison measures. The moving parts are
  `batch-runner/core/execution_environment_readiness.py` and
  `batch-runner/scripts/check_execution_environment_readiness.py`. **No
  comparison ran, no model was called, nothing was graded, and no published
  result file was touched.**
- **Two retired 2026-06 grade runs no longer recompute, and now we can say
  why.** `judge_gpt-5_4__rubric_v2_tools` publishes
  `rubric_item_coverage_avg` 0.4232 and `critical_item_pass_rate` 0.501 where
  today's summariser makes 0.4338 and 0.485; the `_mini` run drifts the same
  way (0.4533 → 0.4646, 0.528 → 0.5128). **One cause, not two:** `6ad789a`
  (#69) taught `_compute_summary` to skip items carrying `score_excluded`, and
  both files were graded before it. Deleting that gate — changing nothing else
  — reproduces all five published rates exactly in both files. The gate removes
  255 items, every one a `judge_error` the judge never managed to score (243
  `selection_error`, 12 `wrong_format_primary`, spread over 17 of 220 tasks).
  Coverage rises because it keeps its whole numerator — a judge error is never
  a `pass` — while critical falls because all 15 of its excluded items are
  flagged `model_did_right`. The other three rates reproduce unchanged, which
  reflects the gate being a no-op for them on this corpus rather than those
  paths being untouched. **Nothing official moved:** both runs were retired as
  comparators in Phase 5, and the sol-220 R1 result and its comparator
  recompute to the digit. Across all 37 published payloads: 31 reproduce, 2 are
  this gate, 4 are the already-known pre-sign-aware `__v1.json` files, and 0
  are unexplained. `scripts/summary_wow_drift.py` recomputes every payload with
  the production summariser and exits nonzero only for drift that matches no
  rule we have shipped; `tests/test_summary_wow_drift.py` pins the finding, and
  `data/grades/_validation/SUMMARY_WOW_DRIFT.md` records the full history and
  the options. **Diagnosis only — no payload was edited and no rate was
  republished**, so every number already cited stays citable.

### Removed
- **Task 207 — the legacy grader code is gone.** `core/grader_batch.py`
  (508 lines) is deleted, and with it every batch / tier-routing / text-extract
  member of `core.grader.Grader`: `_use_batch`, `_tier_judges`,
  `_build_tier_judges`, `_route_to_tier`, `_resolve_batch_prompt_path`,
  `_grade_task_batched`, `_summarize_deliverables`, `_build_prompt`,
  `_call_judge`, `_safe_parse_judge_json`, `_json_scalar`, and the
  `deliverable_extract_max_chars` knob. `core/grader.py` drops 2045 → 1558
  lines. **The PR2 acceptance grep for 207 (`tier_pro|tier_standard|tier_mini|
  deliverable_extract_max_chars`) now returns no matches in `core/grader.py`
  or in any dispatchable config; it was recorded as PARTIAL and is now
  complete.** Two residual matches are prose — the "REMOVED" comments in
  `default_v2.yaml` that document the change — and one is live code outside
  the grader, discussed below.

  Both preconditions the PR2 note set for this strip hold: `grade-run.yml`
  defaults to `default_v2_sol_max.yaml` (not the v1 config), and the v2 path
  has produced published grades.

  **Grade equivalence, established before removing anything.** Of the ten
  configs then shipping at `grading_configs/*.yaml`, nine already resolved to
  the v2 tool-calling path and **zero** resolved to the batch path — so no
  shipped config could reach `grader_batch.py` at all. The one exception,
  `default_gpt5pro.yaml`, was the only remaining schema-1.0 config and the
  only user of the text-extract path; it moves to `grading_configs/_archive_v1/`
  alongside the tier configs archived in PR2. The archived configs are not
  dispatchable: `grade-run.yml` validates `grading_config` against
  `^[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml$`, which forbids a path separator.
  Existing `data/grades/*.json` are unaffected — they are stored artifacts,
  not recomputed by this change.

  `scripts/grading_cost_sweep.py` follows the config to `_archive_v1/`. It is
  itself a v1-era tool that already rendered `_archive_v1/_sweep_template.yaml`,
  and it is kept for provenance rather than revived.

- **A config that does not opt into the tool-calling judge is now rejected at
  construction.** `Grader.__init__` raises `ValueError` when
  `judge.tools.read_deliverable` is absent, instead of silently taking a
  different grading path. A silent fallback is how two runs end up with
  grades that are not comparable, which is the failure this task exists to
  prevent.

  Deliberately left in place: `core.azure_ai_clients.grader_route_workloads`
  still enumerates `tier_standard` / `tier_pro` / `tier_mini` when building the
  Azure deployment allowlist. That function is the credential boundary, not a
  grader path, and it is called with the same config the `Grader` now rejects,
  so the branch is unreachable rather than permissive. Narrowing an allowlist
  is its own change with its own blast radius; it is not folded into a cleanup
  PR.

### Fixed
- **`grade.error = "no_deliverables"` is set on the v2 path.** It was written
  only in the two legacy paths, so the tool-calling path — the one in
  production — never set it, and a task with nothing to grade was
  indistinguishable from one that genuinely graded to zero. Carried over as
  part of the 207 strip rather than lost with it.


### Added
- **The benchmark has a complete score for the first time: 220 of 220 tasks,
  zero error tasks** (#205). The published OFFICIAL run for
  `exp003_GPT52Chat_baseline_runner_exec` is now **57.3% ±3.75** over the full
  corpus, judged by `gpt-5.6-sol`. Its predecessor scored 57.49% ±3.79 over
  **215** of 220, with 5 tasks the harness could not score at all.

  The two numbers are 0.19pp apart, and that is the point of the release. Five
  more tasks entered the average and the headline barely moved, which is the
  evidence that the work below recovered items the harness had been failing to
  read — it did not loosen what "correct" means. A fix that inflated scores
  would have shown up here as a jump.

  | | previous | now |
  |---|---|---|
  | tasks scored | 215 / 220 | **220 / 220** |
  | error tasks | 5 | **0** |
  | avg score | 57.49% ±3.79 | 57.3% ±3.75 |
  | judge errors (rubric items) | 333 of 10,453 — **3.19%** | 32 of 10,453 — **0.31%** |
  | zero-score tasks | 24 | 25 |

  A judge error is not a low score. It is the harness admitting it could not
  put the deliverable in front of the judge — the item is excluded from the
  score rather than counted as a failure, so a run full of them is not a hard
  run, it is an unmeasured one. Ten times fewer of them is the release.

  Broken down by cause, what moved was the harness and only the harness:

  | cause | who | before | after |
  |---|---|---|---|
  | `selector_ambiguous` | harness | 243 | **0** |
  | `render_target_missing` | harness | 68 | **6** |
  | `render_target_partial` | harness | — | 2 |
  | `judge_no_verdict` | judge | 4 | 6 |
  | `wrong_format` | model | 12 | 12 |
  | `nothing_submitted` | model | 6 | 6 |

  The two model-caused rows are *identical* before and after. That is the
  strongest single check on this release: 311 harness errors became 8, and not
  one of the model's own failures was absorbed along with them.
  (`render_target_partial` reads "—" before because the bucket did not exist
  yet; those two are a sharper reading of what used to be filed as missing.)

- **`batch-runner/scripts/judge_error_breakdown.py` — a structural six-cause
  taxonomy for judge errors** (#199). Sorts every `verdict == "judge_error"`
  item into harness causes (`selector_ambiguous`, `render_target_missing`,
  `render_target_partial`), judge causes (`judge_no_verdict`) and model causes
  (`wrong_format`, `nothing_submitted`), plus `unclassified`. It reads only
  structural fields and never the evidence prose, so its verdict on who is at
  fault does not depend on how a judge happened to phrase itself. This is what
  turned "3.19% of items errored" into a list of specific, separately fixable
  defects — and what makes the remaining 0.31% enumerable rather than
  mysterious: 12 `wrong_format`, 6 `judge_no_verdict`, 6 `nothing_submitted`,
  6 `render_target_missing`, 2 `render_target_partial`.

- **Shard the 220-task grade run across N parallel relays** (#175, #176). A
  full paid grade run is far longer than one GitHub Actions job may live. The
  run is now split into an ordered subsequence per shard, each shard
  auto-resumes in chunks, and `step9_merge_shards.py` recomputes the merged
  summary from the union of item grades rather than averaging shard summaries.
  Guide at `docs/grading-sharding.md` and `docs/grading-sharding_KR.md`.

- **Report shard relays that stop without finishing** (#197, #198). A relay
  that dies quietly used to look identical to one that had not started. The
  sweep now names them, and it runs without importing the grading stack so it
  keeps working when the grading code is the thing that is broken.

### Fixed
- **Render `.docx` deliverables for visual judging** (#189, #195). A Word
  document had no render path, so every visual rubric item pointed at one
  failed closed. LibreOffice conversion plus a pinned rasterizer gives it a
  page 1; the grade schema learned to record `source_kind: "docx"`. This took
  `render_target_missing` from 68 errored items to 6.

- **Grade several same-format outputs instead of declining to choose** (#190).
  The deliverable selector treated "four `.pptx` files" as ambiguous and
  refused to select, which turned a complete submission into an unscorable
  one. It now classifies them as separate equivalent deliverables and grades
  each. This was the largest single fix in the release: `selector_ambiguous`
  went from 243 errored items to zero.

- **Text-judge an overall-style item with nothing renderable** (#206). An
  "Overall formatting and style" criterion whose selected files are all plain
  text classified VISUAL, found no render target, and errored — on work the
  judge could simply have read. It is now demoted to TEXT, gated on the same
  `is_overall_style_criterion` predicate the `.docx → FORMATTING` rule uses,
  so an *explicitly* visual criterion ("document color and page layout") still
  fails closed rather than inventing a verdict it cannot ground. Under
  `split_children` this mattered twice over: one unrenderable child used to
  collapse every sibling with it. Merged after the run above was graded, so it
  is not reflected in its numbers — it accounts for 3 of the 6
  `render_target_missing` items still on it.

- **Name the half-rendered bundle instead of dropping it** (#204). A bundle
  where only some files rendered reported nothing at all; it now records
  `render_target_partial` and which file fell out.

- **Stop filing judge flakiness under the model under test** (#200, #201).
  Judge-error runs are paired on `task_id` rather than on totals, so a run
  that graded a different number of tasks cannot be silently compared
  position-by-position, and a judge that failed to return a verdict is no
  longer counted against the model whose work it was judging.

- **Stop counting a blank submission as a render defect** (#202, #203). A task
  with nothing submitted is a zero, not a harness failure. The placeholder
  rule now requires *every* selected target to be a placeholder before the
  task is treated as a non-submission, matching the dashboard's all-match
  semantics.

- **Let a shard stand down when the corpus is not yet complete** (#194).
  A short union under resume is the normal mid-run state, not an error. The
  merger stopped failing on it.

- **Pin the renderer version the published corpus was graded on** (#193). Two
  runs rendering the same `.docx` through different LibreOffice builds are not
  comparable, and nothing recorded which build produced a given image.

- **Exclude judge errors from scores** (#168). An item the harness could not
  read is now excluded rather than scored zero — the change that makes
  `error_tasks: 0` meaningful instead of cosmetic.

- **Bound `apt` installs so a stalled mirror cannot hang a job** (#183) and
  **run the batch-runner pytest suite on pull requests** (#182, #187). Five
  shards were lost to a mirror stall before the first; two guards were being
  silently skipped before the last.

### Changed
- **Publish legacy-provenance runs that pin the complete corpus** (#177, #178,
  #171). A run whose source inference predates route provenance is publishable
  when it pins all 220 canonical task ids — it is badged on the dashboard
  rather than hidden, because a complete scoring with a known gap in its
  audit trail is more useful than no scoring at all.

- **Hide grading runs that covered part of their corpus** (#185) and **retire
  the spare baselines** (#186, #205). The dashboard shows two runs: the
  OFFICIAL 220-task result and one deliberate A/B comparator. Partial-corpus
  runs no longer sit next to complete ones as if they were the same kind of
  measurement.

- **Explain what the zeros on a grade page are made of** (#184). A zero from a
  blank submission, a zero from failed criteria, and an excluded judge error
  are three different facts and now read as three different facts.

- **Let resume chunks inherit the initial paid approval** (#179). A run
  approved once no longer re-prompts on every chunk boundary.

- **Freeze the grader source inputs while shards are in flight** (#196).
  `grader_source_hash` covers `step8_grade.py`, `core/**.py`,
  `schemas/grade.schema.json`, `requirements.txt` and the prompt templates.
  Merging any of them mid-run moves the shard partial path, so the relay
  cannot find its own previous partial — and the failure only surfaces after
  the spend. The policy and the source set are now written down.

### Added
- **`summary.wow` analytics now carry data** - `src/types/grade.ts` has declared
  `by_sector`, `by_rubric_category`, `score_density_histogram` and
  `rubric_severity_curve` since the WOW dashboard landed, and
  `SectorHeatmap.tsx`, `ScoreDensityHistogram.tsx` and `RubricSeverityCurve.tsx`
  have rendered their empty states ever since, because `_compute_summary` in
  `step8_grade.py` never emitted the four fields. It now emits three of them.
  - `by_sector` reports `task_count`, `avg_pct`, `critical_item_pass_rate`,
    `precheck_pass_rate` and `judge_pass_rate` per sector. The run-wide rates
    and the per-sector rates are folded by one shared `_tally_item`, so a
    sector row cannot drift from the header it sits under. The breakdown is
    scoped to graded tasks, so its `task_count` values sum to `graded_tasks`;
    a task with a blank or absent sector lands in `Unknown` rather than
    vanishing from a total that is expected to add up.
  - `score_density_histogram` emits all ten decile buckets including empty
    ones, so the chart draws a full axis instead of collapsing to whichever
    scores happened to occur. The labels and their order are a contract with
    `bucketFromPct` in `ScoreDensityHistogram.tsx`, which buckets `pct`
    client-side when a grade predates the field; a run that emits it and one
    that does not must land in the same bars. `100.0` closes into the last
    bucket rather than falling off the end.
  - `rubric_severity_curve` groups scored items by rubric weight and counts
    `ItemGrade.model_did_right`, not `verdict == 'pass'`. GDPVal rubrics carry
    negative-weight anti-criteria where a `pass` verdict means the model *did*
    the prohibited thing, and this curve deliberately spans both signs, so a
    raw verdict count would invert exactly the points the chart exists to
    show. Grades written before `core/grader.py` began emitting
    `model_did_right` carry no sign-aware verdict, so the curve is omitted
    entirely for them: every point would read `0.0` and a flat-zero chart
    asserts a total failure that never happened. A single rate can absorb that
    gap; a curve cannot, because its shape is the claim.
  - `by_rubric_category` stays `{}`. The GDPVal rubrics carry no category
    taxonomy — a rubric item has an id, a criterion string and a weight, and
    nothing that groups items into categories — so there is no source for this
    breakdown, and populating it would mean inventing a taxonomy and
    presenting it as measurement. `SectorHeatmap.tsx` already treats it as
    absent and falls back to the per-sector rates above.

  `judge_error_rate` keeps using `canonical_rate`, which
  `grade_payload.py` validates and `step9_merge_shards.py` cross-checks; only
  the new fields use the plain rounding helper. `step9_merge_shards.py`
  recomputes the merged summary rather than combining shard summaries, so a
  sharded 220-task run gains these fields with no merge-side change.

  Verified behavior-identical on the pre-existing fields: `_compute_summary`
  from `origin/main` and from this branch were run over the same 16
  checked-in grade payloads, and every previously-emitted field matched on all
  16. `mypy core/ step8_grade.py --ignore-missing-imports` reports the same
  error set before and after. No grade payload was rewritten and no run was
  dispatched.

  **Operational note:** `step8_grade.py` is inside the
  `compute_grader_source_hash` source set, so merging this changes
  `grader_source_hash` and therefore the shard partial path
  `data/grades/_shards/<stem>/`. A chunk relay that is mid-flight when this
  merges will not find its own previous partial, will fail the
  `approval_inherited` check and fall back to a fresh Environment approval, and
  its shard set will fail the cross-shard `grader_source_hash` invariant at
  `step9_merge_shards.py`. This must merge between runs, not during one — and
  did: the 220-task relay had finished and no grading run was in flight when
  this landed.

- **Zero-reason breakdown on the grade page (`scripts/selection-outcome.mjs`,
  `src/components/ZeroReasonBreakdown.tsx`)** - a zero on this benchmark meant
  two unrelated things and the dashboard painted both the same red. Either a
  judge read the deliverable and awarded nothing, or nothing gradeable ever
  reached a judge and the pipeline recorded the absence as a score. On the
  220-task Sol Max run those are **1** task and **23** tasks respectively, so
  the reading most people take from the headline number was close to backwards.

  The classifier derives the reason from the `selection_status`,
  `selection_error` and `selected_deliverables` fields the grader already
  writes, and splits the outcomes into `content_zero`, `format_unmet`,
  `inference_failed`, `no_deliverable`, `not_selected`, `grading_error` and
  `unclassified`. The grade page gains a card separating zeros that count
  toward the average from tasks excluded from it entirely, and each row in the
  task table now carries a badge naming its reason rather than a generic
  "Zero" or "Error".

  Two things this deliberately does not do. It does not recompute any
  published figure - `avg_score_pct`, `graded_tasks`, `error_tasks`,
  `zero_score`, `perfect_score` and `partial_score` are still passed straight
  through from the grade JSON, verified by diffing every generated file
  against the pre-change aggregator (0 changed values, 28,474 added keys, all
  of them the new fields). And it does not touch `batch-runner/core/`, which
  is inside `grader_source_hash`; changing the selector would invalidate the
  finished run's reproducibility. Grades written before the selector recorded
  its reasoning report `covered: false` and render exactly as they did before,
  so no existing experiment changes.

  One finding worth recording separately: **8** of the 220 tasks produced only
  a `failed_to_generate.txt` placeholder, which is an inference-stage failure
  that had been showing up as a grading outcome. Two of those the selector
  passed through with `selection_status: 'ok'`.

- **Curated the published baseline set down to a result and one comparator
  (`src/lib/officialExperimentScope.js`)** - the 220-task `gpt-5.6-sol` regrade,
  the run this month of work existed to produce, was rendering without the
  OFFICIAL badge beside two older badged runs. A reader scanning the page would
  take the badged, older, lower numbers as the benchmark's answer. It is now
  promoted, and the older runs are cut to a single A/B comparator.

  `gpt-5.4-mini` is the one retired. Against a `gpt-5.6-sol` judge it differs in
  judge size and judge version simultaneously, so a gap measured across it
  cannot be attributed to either; the full-size `gpt-5.4` run is the
  like-for-like comparator and stays. Every other rule in the module decides
  from a measured property, but which finished run represents the benchmark is
  a publication decision, so both lists are hand-written and sit together with
  the reasoning attached.

  Retirement is not the partial-corpus rule and does not imply the numbers are
  wrong - the retired run graded all 220 tasks and its figures stand. It is
  display-only: no grade JSON changes, the card is one `?debug=1` away, and its
  own page still resolves by direct URL. Visible cards go from 3 to 2, both
  badged OFFICIAL.

  `OFFICIAL_GRADE_IDS` moved from `officialFilter.ts` into
  `officialExperimentScope.js` so the curation is covered by the node test
  suite, including a guard that the official and retired sets can never
  overlap.

- **Partial-corpus grading runs hidden from the default dashboard view
  (`scripts/aggregate-grades.mjs`, `src/lib/officialExperimentScope.js`)** - the
  Grading Analysis tab listed six cards for the same experiment, three of which
  were preflights: a 1-task config check, a 3-task cohort trial and a 10-task
  cohort trial. Sitting on the same axis as a finished 220-task run they read as
  comparisons, and the numbers cannot support that - the 3-task trial scored
  36.14% and the 10-task trial 57.74% against 53.30% for a full run, spread that
  is mostly sampling noise. Both aggregate charts, the Score Distribution
  Comparison and the Overall Score Breakdown, were mixing them into the same
  totals.

  The rule is measured rather than name-matched. The aggregator now records a
  `coverage` block per grade - `grade_tasks`, `corpus_tasks`,
  `is_partial_corpus` - where the denominator is the inference run's own
  published `summary.total_tasks` read from `reports-index.json`. A grade that
  covered fewer tasks than the run it graded is a preflight and is hidden.
  This subsumes the hand-written `_tight` pattern from the previous phase,
  which was always an instance of the same rule; the pattern stays as a
  fallback for grades whose experiment has no report.

  Two properties make the failure modes safe. Unknown coverage is never
  partial - an experiment with no report yields `corpus_tasks: null` and the
  grade stays visible, so ignorance leaves an early experiment alone rather
  than silently deleting it. And a small experiment graded end to end (17 of
  17) is complete, so the rule cannot mistake "small" for "unfinished". The
  curated `OFFICIAL_GRADE_IDS` allowlist is still checked first and is never
  hidden by any rule.

  This is a display filter and nothing else. No file under `data/grades/` is
  modified, `coverage` is additive metadata that changes no published figure,
  every grade remains reachable by direct URL, and `?debug=1` restores the full
  list. Visible cards go from 6 to 3, all three full-corpus runs.

- **Backend test workflow (`backend-tests.yml`)** - the batch-runner suite had
  no pull-request gate at all, so a change could land on `main` with a red test
  and nothing would report it. That is exactly how the paid-gate assertion
  stayed broken through a merge. The workflow runs `pytest` on pull requests
  and pushes to `main` that touch `batch-runner/**`.

  Pinned to Python **3.10.12** exactly, not `3.11` like the other workflows
  here. `core/agentic_v2_license.py` pins
  `LICENSE_EVALUATOR_PYTHON_VERSION = "3.10.12"` and compares it against
  `sys.version_info[:3]`; on 3.11 the identity check raises and takes ~93
  supply-chain and license tests with it. The pin is a deliberate
  reproducibility control, so CI matches it rather than relaxing it.

  Checks out with `fetch-depth: 0`, because
  `test_verifier_ignores_hostile_path_for_repository_git` resolves a hardcoded
  commit through `git cat-file` and a shallow clone does not contain it.

  Two real defects surfaced on the workflow's own first runs, which is the gate
  earning its place before anyone had to trust it:

  - **`patched_run_inference` was not hermetic.** It left `GITHUB_RUN_ID` and
    `GITHUB_RUN_ATTEMPT` in the environment, so `_resolve_run_identity()`
    returned `exp_test:<runner id>:1` while the checkpoint the fixture writes
    hardcodes `exp_test:local:1`. Every run inside Actions rejected the
    checkpoint with `progress checkpoint identity mismatch` and exited 1
    instead of `EXIT_CHECKPOINT`. The test could only ever pass off-CI. The
    fixture now clears those variables plus `GDPVAL_RELAY_LINEAGE_ID`, matching
    what `test_relay_duration.py` already does per-test. Confirmed by
    reproducing the failure locally with the variables set, and by mutation.
  - **One security test is deselected in CI, and it is an open question, not a
    nuisance.** `test_generated_python_launcher_denies_exec_and_network`
    asserts both `os.system()` and `socket.socket()` raise `OSError` under the
    launcher's seccomp filter. On the runner only `socket()` does.
    `execve`/`execveat` are still in `DENIED_SYSCALLS` and the filter still
    loads, so the sandbox is not weaker there - what differs is whether glibc's
    `system()` surfaces the blocked exec as a Python `OSError`, which it does
    on the dev box's 3.10 kernel and does not on the runner's. That makes the
    assertion a probe of libc error reporting rather than of the filter. It
    stays deselected until it is rewritten to check exec denial directly; the
    Docker gate remains the enforcing control regardless.

  It holds `contents: read`, references no secrets, and checks out with
  `persist-credentials: false`, so it stays runnable from a fork. Integration
  tests reach paid judge endpoints, and `pytest.ini` deselects them via
  `addopts` - but a pull request can edit `pytest.ini`, so the job asserts the
  marker filter is still there before running, and repeats `-m "not
  integration"` on the command line regardless. Both were mutation-checked
  against a `pytest.ini` with the filter stripped.

  Deliberately not gated: mypy (189 findings on `main`) and ruff (20). Gating
  either today would freeze a pre-existing backlog into permanent red and teach
  everyone to ignore the check.

  Known gap, left alone on purpose: two tests carry `@pytest.mark.timeout(2)`
  but `pytest-timeout` is absent from `requirements.txt`, so pytest warns and
  enforces no timeout. Adding it changes `grader_source_hash` and would break
  the in-flight 220-task relay, so it waits for the shard merge.

### Changed
- **Existing grade payloads backfilled with the `summary.wow` analytics** - the
  entry above taught `_compute_summary` to emit the four analytic fields, but
  only for runs graded after it merged. All 17 real grade payloads already on
  disk still carried `by_sector: {}`, `score_density_histogram: []` and
  `rubric_severity_curve: []`, including the newest sol-220 run, so the sector
  heatmap, the score histogram and the severity curve rendered empty states
  across the whole dashboard. Nothing needed re-grading and nothing was
  dispatched: each field is a pure function of the `tasks` array already in the
  file, and `scripts/backfill_summary_wow.py` recomputes it from that array.

  What the script does *not* do is the reason it exists in this form. Six of the
  seventeen payloads were graded under semantics the current summariser no
  longer reproduces — the four pre-sign-aware `__v1.json` files carry no
  `model_did_right`, so their `critical_item_pass_rate` recomputes to `0.0`
  against a published `0.42`/`0.52`/`1.0`, and the two `rubric_v2_tools` files
  drift by about a point (`0.501 → 0.485`, `0.4232 → 0.4338`). Republishing
  those would let a later grading standard rewrite the record of an earlier
  experiment, which is exactly the thing a benchmark must not do. So the rule is
  per-file rather than global: a payload's semantics-dependent breakdowns
  (`by_sector`, `rubric_severity_curve`) are written only when the current
  summariser reproduces that payload's five published scalar rates exactly, and
  that agreement is the evidence the same code understands the same file. It
  holds for 11 of 17. The remaining 6 get `score_density_histogram` only — a
  bucket count over the per-task `pct` values already published in the file,
  carrying no semantic assumption that a change in grading criteria could move.

  `by_rubric_category` stays `{}` everywhere for the reason given above: there
  is no category taxonomy in a GDPVal rubric to build it from.

  The script is dry-run by default and refuses to write a file if anything
  outside `summary.wow`, or any of the five published rates inside it, would
  change. That guard is not decoration — the first cut of this change lacked the
  inside-`wow` half of it and would have republished four payloads'
  `critical_item_pass_rate` as `0.0`. Verified after applying by re-parsing every
  payload against `git show HEAD:` and confirming that the only values that moved
  anywhere are the three analytic fields, that no `_v2sm_*` key was dropped, and
  that every histogram and sector breakdown sums to that file's own
  `graded_tasks` (the shortfall against `total_tasks` is exactly `error_tasks`,
  which carry no `pct`).
- **One paid approval now carries a whole shard, not one 4h chunk** - a shard of
  the 220-task corpus takes ~6.5h of strictly serial judge calls
  (`tpm_guard.max_concurrent: 1`), but GitHub's hosted runners cap a job at 6h
  and cannot be extended. `step8_grade.py` therefore stops at its 4h internal
  budget, saves a partial, exits 7, and re-dispatches itself for the next chunk.
  Every one of those re-dispatches landed back on the `grading` Environment and
  waited for a human to click approve - so finishing a shard meant somebody
  being awake at the four-hour boundary, and finishing nine shards meant that
  eighteen times. Re-sharding cannot avoid it: `shard_count` is capped at 11,
  which still leaves two chunks per shard.

  `validate-request` now resolves an `approval_inherited` output, and
  `approve-paid` is skipped when it is `true`. This is not a relaxation of the
  spending control. `rerun_identity` pins the corpus (`task_ids` plus
  `expected_task_count`) before chunk 0 runs, so approving chunk 0 already
  bounds the bill for the entire shard; the 4h split is an artifact of the
  runner ceiling, not a second spending decision. Inheritance is granted only
  when *all* of the following hold, and any error or ambiguity falls back to
  requiring the click:
  - the request is paid (`dry_run == false`, `paid_approval == true`) and is a
    resume with `resume_chunk >= 1` - chunk 0 is always the human click;
  - both `actor` and `triggering_actor` are `github-actions[bot]`, which only
    the in-workflow auto-retrigger produces (a person passing `resume=true` by
    hand carries their own login);
  - a partial for this exact shard slot exists on `main` under
    `data/grades/_shards/<stem>/shard-NNN-of-MMM.json`, where the stem encodes
    experiment, config name, config hash, rubric SHA, inference SHA and grader
    source hash - so a path match is a full identity match;
  - that partial's last commit was authored by the grading job's bot identity.

  Minting a bot dispatch or a bot-authored partial requires merging a workflow
  change to `main`, which is already owner-gated, so the bypass cannot be
  reached from a feature branch. `grade` reads
  `needs.validate-request.outputs.approval_inherited` rather than trusting a
  bare `skipped` result, so an `approve-paid` skip from any other cause still
  blocks the paid job, and its `if` now carries `!cancelled()` because a job
  whose `needs` was skipped is otherwise skipped before its condition is even
  evaluated. The inheritance step itself denies rather than throws on any
  unexpected error, so a bug in it can never block chunk 0. Chunk 0 of every
  shard, and every non-resume paid request, is unaffected.
  `docs/first-experiment.md` and `docs/first-experiment_KR.md` no longer state
  that each continuation needs a fresh approval. No workflow was dispatched by
  this change.
- **Legacy provenance: a complete pinned corpus is publishable** - inference
  runs that predate `inference_provenance.json` previously forced every grade
  built from them into `data/grades/_diagnostic/`, which the dashboard
  aggregator does not read. That rule conflated two different gaps. The sidecar
  records the Azure AI routes that produced the *deliverables*; neither
  `core/grader.py` nor `core/tool_calling_judge.py` ever reads those routes, so
  a missing sidecar leaves the audit trail incomplete without leaving the graded
  corpus incomplete. `filter_tasks_for_config` in `step8_grade.py` now returns
  the pinned *scope* (`None`, `"subset"`, or `"complete"`) instead of a boolean,
  and the legacy allowance blocks publication only while that scope is not
  `"complete"`. A config pinning a proper subset — the four-task Sol Max anchor
  — still emits a diagnostic grade; a config pinning every task in canonical
  source order keeps the root path and `run_status: final`.
  `--allow-legacy-missing-provenance` on the downloader pins nothing, so a bare
  CLI override still lands in the diagnostic tree. The grade payload continues
  to persist `source_azure_ai_provenance_status: legacy-missing`, and
  `scripts/aggregate-grades.mjs` now carries that field into the dashboard
  projection so a published legacy grade is labelled rather than silently
  normalized. Both exp003 full-rerun configs gained all 220 task IDs in
  canonical order (ordered SHA-256
  `df1fcd6415c55a17e4f39a254aaf0f0f9f2f55c751189f74d2713a873373aa3c`), changing
  the Sol Max config hash from `14fc577ea39d98c5` to `71c325eee0e48c13` and the
  mini config hash from `55a7dc5cfb8023fe` to `0aebaaa2d0e51d74`. The anchor
  config and its hash `7f3c7c2e542cf580` are unchanged. No grade payload,
  deliverable, or HF file was modified, and no run was dispatched.
- **Conductor orchestrator persona** - rename
  `.github/agents/copilot-instructions.agent.md` to
  `.github/agents/conductor.md`, and the persona itself from
  `ai-strategy-consultant` to `conductor`, normalizing the extension to match
  the other ten agent files. The persona previously forbade all file editing in
  its body while its `tools:` list granted `edit/createFile`, `edit/editFiles`,
  and `edit/rename`; the restriction is now scoped by target instead. It may
  write `tasks/**`, `docs/**`, and `.github/agents/*.md`, and must not write
  `batch-runner/**`, `src/**`, `scripts/**`, `.github/workflows/**`,
  `grading_configs/**`, `schemas/**`, or `data/**`, with `git commit`, `push`,
  PR, and tag remaining owner decisions routed to `git-committer`. Adds an
  Orchestration section covering subagent dispatch — that a subagent inherits
  none of the orchestrator's conversation, that job-specific boundaries belong
  in the call prompt rather than in a worker's reusable persona file, and that
  workers must be given a clean worktree cut from the merged SHA rather than a
  dirty checkout. Adds the missing `model:` key to `grading-engineer`, which had
  none, and repoints `llm-systems-engineer`'s cross-reference at the new persona
  name so no dangling reference remains. Source, workflows, configs, schemas,
  and grade data are unchanged.

### Fixed
- **Sandbox launcher test now probes exec denial rather than libc error
  reporting** - `test_generated_python_launcher_denies_exec_and_network`
  asserted that `os.system('/bin/true')` and `socket.socket()` both raise
  `OSError` under the launcher's seccomp filter. Both `execve` and `fork` sit
  in `DENIED_SYSCALLS`, so `os.system` is blocked either way, but glibc's
  `system()` reports that block through its return value on some libc and
  kernel pairs and as an `OSError` on others: the assertion measured error
  reporting, not the filter. CI deselected the test for exactly that reason,
  and the dev box skips it because its 3.10 kernel predates seccomp TSYNC, so
  the test ran nowhere at all. It now calls `os.execv`, a thin `execve` wrapper
  whose denial surfaces as the filter's own `SCMP_ACT_ERRNO` `EPERM` wherever
  the filter loads, and asserts that errno rather than merely that something
  raised. A successful `execv` replaces the process image and would exit 0 with
  empty output, so the `blocked` marker assertion is what keeps that failure
  visible instead of silent. The `--deselect` argument is gone from
  `.github/workflows/backend-tests.yml`, whose comment no longer describes a
  deselection it does not make.
- **`@pytest.mark.timeout` restored to a working guard** - `pytest-timeout` was
  absent from `batch-runner/requirements.txt` while
  `test_snapshot_manifest_fifo_fails_without_blocking` and
  `test_snapshot_artifact_fifo_fails_without_blocking` both carry
  `@pytest.mark.timeout(2)`. pytest treats an unregistered marker as a no-op
  with a warning, so the two tests that exist to prove `PackageSnapshot.load`
  fails fast on a FIFO rather than blocking forever had no mechanism left to
  detect blocking; a regression that hung the loader would have hung the job to
  its own ceiling instead of failing the test. The dependency is now pinned and
  both tests pass in 0.13s with the marker active.
  approval-inheritance change left `test_grade_workflow_rc7_requires_valid_
  committed_partial` comparing `approve-paid`'s `if:` against the old literal
  `inputs.dry_run == false && inputs.paid_approval == true`, so `main` has been
  red since that merge. Nothing caught it because no workflow runs the
  batch-runner pytest suite on pull requests. The assertions now normalize the
  YAML block scalar through a `_gh_expr` helper and pin both the `approve-paid`
  and `grade` conditions exactly, replacing four substring probes that would
  have passed against a gate weakened to `!= 'failure'` or one that dropped the
  `approval_inherited` conjunct. Verified by mutation: removing the inheritance
  conjunct from the workflow makes the test fail.
- **First Sol Max anchor result and bounded analysis filenames** - run the
  owner-approved four-task anchor once as Actions run `31582293672` from main
  SHA `c9492645496e176c8e6a3510809585f9542a5bf1` with grader source hash
  `b00e83209ab6ca93a147da5bcfd02facce922e381fa01b2f73559b0d14631ab9`.
  Grading, schema validation, the grade commit, and artifact upload succeeded;
  the workflow failed only afterward because appending `.analysis.md` to the
  250-byte JSON basename exceeded Linux `NAME_MAX`. The committed diagnostic
  payload SHA-256 is
  `303a5e763e28bf06339877df62c8e2d0d022bc605aeeb3aee77e63ab411a41fb`.
  Its preregistered result is `full_run_gate.status=blocked` with blockers
  `audio_wiring_not_exercised` and `at_or_above_44h_envelope`, projected
  `71.5934` hours against the 44-hour envelope,
  `diagnostic.targetable_status=improved`, and zero audio calls. The run used
  738 model calls, 3,526,558 input tokens, 322,072 output tokens, and 1,746,790
  cached tokens; usage is complete and pricing remains explicitly unpriced.
  The expected `legacy-missing` source provenance is retained. The analyzer now
  preserves legacy names through 255 UTF-8 bytes and otherwise writes a
  deterministic 83-byte `grade__<sha256>.analysis.md` sibling through a
  no-follow directory-FD transaction with mode preservation and rollback. The
  missing Markdown is generated model-free with SHA-256
  `90252c360f2603ec692d163c02736418c32f8eb9d4ca2779cd64efecf51936ec`.
  Config, schema, grade JSON, gates, and dispatch behavior are unchanged; no
  paid rerun occurred. Validation passes 3,102 backend tests with six skips and
  45 integration deselections, 65 analyzer tests, 161 Step 8 tests, and 105
  aggregate tests with one expected skip; the production build transforms
  2,783 modules. Independent systems, grading, security, and code reviews
  approved substantive head `d3c370ce32bcf2f1fc11fa9306460848c87b9d93`.
  Actual Azure cost is not available from the local Azure identity and is not
  recorded as zero; the owner must query Cost Management in the workflow
  tenant/subscription before using this result as a monetary anchor.

### Changed
- **Foundry endpoint secret rename** - read the Foundry project endpoint from a
  `FOUNDRY_PROJECT_ENDPOINT` repository secret instead of the legacy
  `AZURE_OPENAI_ENDPOINT` name across all ten workflow sites, seven in
  `batch-run.yml` and three in `grade-run.yml`. Every site already assigned the
  value to a runtime variable of the same new name, so the mapping is now
  one-to-one and the surrounding route profile, expected-identity, workload,
  and `dry_run` gating expressions are untouched. `AZURE_OPENAI_ENDPOINT`
  remains a rejected runtime environment variable: the deprecation error and
  check in `core/azure_ai_clients.py`, the forbidden-name list in
  `scripts/azure_ai_route_preflight.py`, the legacy native path in
  `step2_run_inference.py`, and the two contract assertions requiring that name
  to be absent from step environments are all unchanged. Both onboarding guides
  and both Batch Runner references now list the new secret, state that the
  deprecated runtime variable is still never injected, and tell operators of a
  fork created before this rename to add the new secret. The onboarding contract
  test pins the new name in the required-secret list and matches the rewritten
  mapping sentence in the English and Korean guides independently. A missing
  value fails the route preflight before any model call, so the failure mode
  stays fail-closed. This change is deliberately name-only: no Python source,
  grading config, schema, archived config, or historical task record moved.
  Validation passes 12 onboarding contract tests and 733 workflow and Azure
  route Python tests; both workflow files parse as YAML, and
  `secrets.AZURE_OPENAI_ENDPOINT` no longer appears under `.github/workflows`.
  The five root aggregate note suites fail three cases each on unmodified
  `origin/main` and after this change alike, because they need the generated
  `public/generated/reports-index.json`. `actionlint` is unavailable on the
  validation host, so GitHub Actions expression schema remains unverified. No
  workflow dispatch, model call, paid operation, or secret deletion occurred.
- **Sol Max anchor4 and revision-scoped legacy provenance wiring** - keep the
  four source-ordered diagnostic/perception tasks and modality-normalized
  projection while allowing their fixed inference revision to use the parquet
  fallback without an `inference_provenance.json` sidecar. That revision,
  `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`, predates the sidecar requirement.
  The exception is a strict boolean in the anchor config identity and requires
  the exact experiment, requested and resolved lowercase SHA, and pinned task
  subset. It accepts only a confirmed remote sidecar 404; embedded routes,
  local cache misses, file errors, timeouts, HTTP 401/403, and malformed or
  mismatched sidecars remain fail-closed. Both protected workflow download
  paths pass the same config to this Python policy without exposing a global
  workflow switch. Results retain an empty source route list,
  `source_azure_ai_provenance_status: legacy-missing`, and diagnostic status.
  The full-220 Sol Max config has no allowance and remains hash
  `14fc577ea39d98c5`; the anchor config hash is now `7f3c7c2e542cf580`
  and its grader source hash is
  `b00e83209ab6ca93a147da5bcfd02facce922e381fa01b2f73559b0d14631ab9`.
  A model-free download of the pinned HF revision reconstructed all 220 source
  rows and confirmed the exact revision, empty routes, and `legacy-missing`
  status. Validation passes 3,099 backend tests with nine skips and 45
  integration deselections, 56 downloader tests, 74 grading-config tests, 161
  Step 8 tests, and 105 aggregate tests with one expected skip. The production
  build transforms 2,783 modules; `py_compile`, focused Ruff, workflow YAML,
  diagnostics, and diff checks pass. Environment approval, OIDC, resume relay,
  time budget, historical grades, protected comparison configs, and HF data
  are unchanged. No workflow dispatch, model call, or paid operation ran.
  Independent systems, grading, security, and code reviews approved substantive
  head `70de50f829f928f88f3bc6b4f6a71b01a8a820bf`.
- **Judge errors excluded from score denominators** - make `judge_error` a
  visible unscored outcome rather than a model failure. Runtime aggregation now
  overrides stale producer flags, excludes judge failures from task numerators,
  denominators, coverage, and critical metrics, and marks fully excluded tasks
  unscored with null headline score and confidence interval. Track 2 continues
  past complete score-excluded errors while malformed items, incomplete usage,
  and unexcluded errors remain fatal. Output schema `1.3`, its Python validator,
  resume identity, and the dashboard parser enforce the same cross-field
  contract; schemas `1.0`-`1.2` remain readable with numeric historical
  headlines. The dashboard always exposes canonical four-decimal
  `judge_error_rate`, discloses denominator exclusion, rejects malformed 1.3
  payloads, and renders unscored headlines as an em dash. Read-only analysis of
  tracked payload SHA-256
  `b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570`
  found 355 judge errors; 100 score-included zeros affected 53 tasks and split
  into 61 final-JSON parse failures, 31 empty final responses, five rate limits,
  and three content-policy errors. A dedicated future full-run config pins all
  220 tasks, config hash `55a7dc5cfb8023fe`, rubric commit
  `11e7900cdcac61bc4daf59e65feb238acda98fbf`, and inference revision
  `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`; Step 8 checks that identity
  before its route preflight and model construction. Headline scores across the
  schema 1.2/1.3 boundary are explicitly non-comparable without a complete
  rerun under one identity. Validation completed 3,033 backend passes with six
  skips and 45 integration deselections; three host-dependency failures passed
  under exact temporary Python 3.10 dependencies. Aggregate contracts passed
  105 with one expected Ruby skip, the production build transformed 2,783
  modules, and Ruff, `py_compile`, diagnostics, and diff checks passed. No grade
  payload was modified, no partial or paid regrade ran, and no credential or
  workflow dispatch was used. Independent grading and code reviews approved
  substantive head `3c8ab817916129dff7a33291520a1f4f2db7d048` with no
  blocking findings.
- **Non-recursive repository completion records** - clarify that the latest-task
  result and changelog entry stop at facts available before merge: task scope,
  concrete outcome, verification evidence, the reviewed head SHA when a review
  gate applies, and remaining work. Neither record duplicates the carrying PR's
  own merge SHA, merge time, or `OPEN` / `MERGED` state. Git history already
  holds those facts, and a record describing its own merge cannot be written
  before that merge, so requiring it forces an unnecessary follow-up PR. A
  genuine correction to an earlier entry must ride with the next substantive
  work PR instead of creating a documentation-only merge-status PR. Existing
  bounded-history, `[Unreleased]`, unrelated-entry preservation, validation,
  and pre-response update requirements remain mandatory; the existing
  historical merge records below are intentionally unchanged. The exact policy
  contract, exact three-file scope, six-marker historical-preservation check,
  three-record preservation check, diagnostics, and diff checks pass. No
  application model/API call, credential, workflow dispatch, or paid operation
  ran; shipment is limited to authenticated Git and GitHub branch/PR writes.
  Independent `first-reviewer` review approved substantive head
  `e800734576dbcc314e5646af80281114672e05dc` with no blocking findings.
- **Root README containment evidence split** - update the English and Korean
  operational-control tables after PR #163 without conflating two separate
  evidence states. The dedicated
  `[self-hosted, linux, x64, agentic-sandbox]` preflight workflow remains
  unexecuted and `not_run` because no matching runner exists. Separately, the
  GitHub-hosted Docker-control measurement is now identified as `verified` for
  all eight checks, with run `31193818481`, PR #163 merge `4b1bff35`, and the
  exact containment-report SHA-256. Both READMEs retain the
  `not_run` / `failed` / `verified` ladder and explicitly state that this is not
  proof of arbitrary execution isolation: `exec_run` and the aggregate gate
  remain `blocked`, with capability, CVE, license, microVM, OCI, provenance,
  SBOM, and signature evidence still unmeasured. Validation passes all 12
  bilingual onboarding contracts, the self-preparing aggregate suite with 98
  passes and one expected Ruby skip, the production build with 2,783 modules,
  diagnostics, and diff checks. No model, grading, cloud credential, workflow
  dispatch, Hugging Face write, or paid operation ran; aggregation made only
  unauthenticated read-only public report requests. Independent
  `first-reviewer` review returned `APPROVE` with no blocking findings. PR #165
  reached `MERGED` at `2026-08-07T17:04:12Z` from reviewed head
  `c3b2a0b4e814d8bb2c830b01162d627f1277739b` as squash merge
  `2d82691ffb5d1911f19f996be0807d4ca037ae81`. GitHub reported the PR
  `MERGEABLE` and `CLEAN`; automatic PR validation passed with deployment
  skipped. Automatic post-merge main run
  [`31200577265`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/31200577265)
  then passed validation and Pages deployment; no workflow was manually
  dispatched.
- **Field Notes rescue reconciliation and onboarding truth labels** - preserve a
  physical copy of the full three-week primary worktree before Git mutation,
  then reconcile the seven requested Field Notes paths against
  `origin/main@a6593c2`. All seven were already tracked on `main`; five primary
  filesystem blobs were exact July 15-16 historical versions, `Journal.tsx`
  was already identical to `main`, the missing filesystem test had a newer
  committed successor, and the one unique `journal.ts` snapshot would remove
  later evidence-backed articles, citations, and selectors. The rescue
  therefore keeps the evolved canonical files instead of overwriting them with
  stale snapshots. Current Field Notes now route every public exp026 detail
  link through its deployed URL with safe new-tab attributes, including mobile
  perception cards and evidence rows. English and Korean root onboarding mark
  the unavailable self-hosted agentic preflight as `not_run`, distinguish the
  sample `gpt-5.2-chat` value from the current production report default
  `gpt-5.6-sol`, label every Start here path with its cost/model-call boundary,
  and link directly to the deployed `/notes` view. Validation passes 21 focused
  Field Notes/onboarding contracts, the self-preparing aggregate suite with 98
  passes and one expected Ruby skip, the production build, and all four
  containerized Chromium Field Notes suites with zero 390px overflow, runtime
  legacy-route redirection, and exact exp026 `href`/`target`/`rel` checks. No
  model, grading, cloud credential, workflow dispatch, Hugging Face write, or
  paid operation ran; aggregation made only unauthenticated public report
  reads.
  Independent `first-reviewer` review returned `APPROVE` with no blocking
  findings; its only note was a nonblocking future-proofing opportunity for
  experiment IDs that are currently internal-only. PR #162 reached `MERGED` at
  `2026-08-07T15:15:36Z` from reviewed head
  `b5d4c2ec68ff027a3187b183183c8b8d81fbf1fb` as squash merge
  `8216181834b4687fd41e543b77f146918e849a23`.
- **Verified 220-task mini regrade history** - replace the stale pre-run
  `BLOCKED` note with an evidence-reopened record of the completed four-run
  `default_v2_mini.yaml` relay. The report now binds each successful GitHub run
  to its preserved Git output, recomputes selector/reference/audit and owner
  gold metrics from the checked-in 220-task grade JSON, binds chunk 2 to exact
  output `110f3bf604f62029fe12e5737b777687439e4b15`, and discloses all 355
  `judge_error` items including the 100 score-included zeros across 53 tasks.
  It also incorporates the later null
  broad-render result, completed GPT-5.4 comparison, and current GPT-5.6 Sol Max
  production default so resolved experiments are not left as future work. This
  documentation recovery made no model call, grading run, workflow dispatch,
  credential use, publication, or paid API call. PR #158 reached `MERGED` at
  `2026-08-05T09:35:56Z` from reviewed head
  `3a303590ca08484e3bd9c83303500d44d0a9b31e` as commit
  `d610c717696b4e6589cf28fb8a122c7b3b9aa2d8`.

### Fixed
- **Excel formatting color observations** - stop openpyxl's inactive color
  descriptors from leaking validation-error strings into grader evidence.
  XLSX inspection now emits stable RGB, theme, indexed, and auto tokens,
  preserves nonzero theme tint, and excludes the workbook's default font color
  so plain and number-format-only cells are not misclassified as explicitly
  styled. Defensive default-style lookup fails soft across openpyxl layout
  changes. Validation passes 51 available `read_deliverable` contracts and 55
  grader dispatch, perception wiring, and grading configuration contracts; one
  unrelated PDF content test remains unexecuted locally because `pdfplumber` is
  unavailable in the active interpreter. PR #156 reached `MERGED` at
  `2026-08-05T06:31:46Z` from reviewed head
  `89f4e5b23df127795b0682e91bfbd6c23c27bc33` as commit
  `609992ede1346da51aac1a8887dbcaaf736d54a3`. No model, grading run, cloud
  credential, publication, or paid API call was used for this fix.

### Added
- **GitHub-hosted Agentic V2 containment measurement** - add a branch-safe,
  model-free `ubuntu-latest` job that pulls the exact public parent digest with
  an empty Docker config and executes the same validated Docker containment
  path used by the Phase 1B/1C verifier. Run
  [`31193818481`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/31193818481)
  on source `bedcdd8229cc4b96c93f52323dcf2099acc7a0ca` measured Linux
  `6.17.0-1021-azure` with cgroup v2 and verified all eight controls: network
  disabled, read-only root, non-root UID/GID, all capabilities dropped,
  no-new-privileges, memory limit, effective CPU quota, and PID limit. Bound
  JSON/Markdown evidence has result SHA-256
  `5caeb42cbe5032169d520e93160a9e19ecbecc0f066faed96979aa44a2103624`
  and containment-report SHA-256
  `f0c4ec3cdff7d714d0db8aca58b1f5669c3958c6b6203be00095b8acb827e50e`;
  an earlier hosted run produced the same containment report. Containment is
  no longer blocking for this exact hosted measurement, but the aggregate gate
  remains `blocked` because capability, CVE, license, microVM, OCI, provenance,
  SBOM, and signature evidence were `not_run` in Tier 1. Existing protected-main
  image publication stayed skipped; no Azure, OIDC, client secret, model,
  grading, Hugging Face write, registry push, paid infrastructure, or Phase
  1D-B execution path was used. Focused workflow/result/verifier tests pass
  74/74, broad Agentic V2 regressions pass 654/654, and Ruff, `py_compile`,
  diagnostics, and diff checks pass. Independent Azure infrastructure and code
  reviews returned `APPROVE`. PR #163 reached `MERGED` at
  `2026-08-07T16:22:26Z` from reviewed head
  `7e4289e5e9a7707b61caabd61d5102cae2361c61` as squash merge
  `4b1bff35541e953e0e0fc583e4f9c4f832db01d2`. GitHub reported the PR
  `MERGEABLE` and `CLEAN`; the final hosted measurement passed with the existing
  publication job skipped, and the merge commit created no additional workflow
  run.
- **Agentic Sandbox V2 Phase 1D-A offline wheel broker candidate** - add a
  disconnected, model-free local candidate for stateless resolution and atomic
  activation of at most eight exact dependency-free `py3-none-any` wheels from
  one approved Linux/amd64/current-Python snapshot. Admission verifies exact
  artifact bytes, ZIP/RECORD/METADATA/WHEEL identity, compatibility, bounded
  paths and resources, and rejects dependency, startup-hook, executable-mode,
  collision, link, FIFO, and mutable-coordinate surfaces. Activation uses a
  deterministic stdlib extractor rather than pip or a subprocess; canonical
  receipts bind independently derived file inventories to the lock, snapshot,
  policy, implementation, and Python identity. Descriptor-relative staging,
  bounded replay and cleanup, process-shared nonblocking leases, global root
  state, and 8-environment/512 MiB quotas fail closed on drift and preserve
  shared environments until the last lease closes. The implementation is
  outside existing image/core-tree and Phase 1B/1C allowlist inputs, while
  tracked Dockerignore rules exclude all Phase 1D-A artifacts from existing
  publication build contexts. The 75 focused adversarial contracts and 644
  Agentic V2/Phase 1B/1C regressions pass; independent
  security and code reviews returned `APPROVE`. The credential-free backend
  completed 3,001 passes and 6 skips with 45 integration tests deselected, and
  three unchanged environment failures caused by stale local Azure SDK versions
  and missing `pdfplumber`. PR #160 reached `MERGED` at
  `2026-08-06T14:05:35Z` from reviewed head
  `15138d88678dfaf08cb478855c6f395a90e32b51` as squash merge
  `4dbb23c9abc3662db984ca8358887184eac4092f`. GitHub reported the PR
  `MERGEABLE` and `CLEAN`; no automatic workflow run was created for the PR or
  merge commit. Local implementation and executable validation used no package
  index, external network, model, cloud credential, workflow, grading, artifact
  upload/publication, or paid operation. Shipment used authenticated Git and
  GitHub PR operations only. `exec_run`, npm, Debian/apt,
  URLs/VCS/sdists/editables, production wiring, and admission claims for
  SBOM/license/CVE/provenance/signature remain disabled or `not_run`; OS
  containment and crash durability remain unproven.
- **Self-preparing dashboard validation** - make `npm run test:aggregate`
  generate its required dashboard/report fixtures before running while exposing
  a prepared-only entry point for CI reuse; isolate the Ruby-backed workflow
  contract so Ruby-less local environments report one explicit skip while CI
  still requires and exercises Ruby; document the fresh-checkout
  `npm ci -> test -> build -> status` path and its unauthenticated public
  Hugging Face reads; and add a fail-closed tracked/untracked cleanliness gate
  after browser validation and before Pages artifact upload. The existing
  build-before-test CI snapshot, permissions, concurrency, dispatch validation,
  Pages/OIDC scope, deployment conditions, experiment paths, and Vite base are
  unchanged. The local aggregate suite passes 96 contracts with one expected
  Ruby skip, and the production build passes separately. PR #154 reached
  `MERGED` at `2026-08-05T05:01:27Z` from reviewed head
  `69821d3cc289fe6f1e3c7cb3352551fcbe92a9af` as commit
  `49fc90acf8117bb1a6961f04783942c1e7bd8f75`. PR validation run
  `30916398926` and post-merge main run `30976841158` both passed; the latter
  uploaded and deployed the exact Pages artifact. The aggregate validation path
  used no model, cloud credential, Hugging Face write, grading, or paid API call.
- **Agentic Sandbox V2 Phase 1C deterministic license evidence closure** - add
  model-free, exact-image Debian, Python, R, and npm license collection with
  same-descriptor bytes and hashes; host-owned SPDX normalization; honest
  `missing_metadata`, `ambiguous`, and `unverifiable` outcomes; denied-first
  decisions; and package/version/purl/evidence-digest/expression/reviewer-bound
  exceptions. The evaluator is staged from pinned Git and packaging source,
  runs under `python -I -S -B`, and binds its transformed parser, frozen SPDX
  tables, normalization/classification/report surface, semantic dependencies,
  and import-order-independent callable identity. Exact-image integration also
  aligns static R receipt/SBOM inventory, rejects image volumes and
  healthchecks, binds probe-loaded source to Git, treats hybrid and
  noncanonical Debian metadata as unresolved, represents blocked symlink paths
  without following them, and rehashes 1,720 physical evidence files through
  safe host copies or bounded non-extracted archives. Checkpoint
  `1397f92b5257747ca3faf99e00a74269d4b14875` produced image
  `sha256:e47537b8f7ac7c595b3a055dea4d16283efaa9c9a67c0f8a3e0fc2d65e834e29`
  and OCI manifest
  `sha256:0064ce70a26d6df58353a2e305a69d1d03e1db4525eee9870841fe10c6b3d02a`.
  Its 1,423 packages classify as 186 resolved, 898 ambiguous, 1 missing
  metadata, 338 unverifiable, and zero denied/exceptions; all 1,237 unresolved
  packages remain visible, license status stays failed, and production remains
  disabled and blocked on containment, CVE, license, microVM, provenance, and
  signature evidence. Validation passes 372 focused contracts, one exact
  Docker/OCI integration, 923 agentic/sandbox/executor regressions with one
  host-dependent skip, and the complete credential-free backend with 2,927
  passed, 6 skipped, and 45 integration tests deselected. Independent
  adversarial review finished with zero mandatory or optional findings. No
  model, Azure, grading, Hugging Face write, registry push, publication,
  workflow dispatch, or paid operation ran. Shipped through PR #152 from
  reviewed head `23c61bdfc32ce7afb65606acbb8df6a9eb5b95b7` as squash merge
  `2f35fe633bab80d76793de78221c2652bc46fa52`. GitHub reported the PR
  `MERGEABLE` and `CLEAN`; no automatic workflow run was created because the
  changed paths are outside active automatic workflow filters, and no manual
  workflow was dispatched to compensate.
- **Agentic Sandbox V2 Phase 1B professional-work candidate** - add a separate,
  local-only image substrate without activating the Phase 1A executor, Step 2,
  workflows, models, grading, publication, or a registry path. An exact GHCR
  parent digest, seven top-level Debian versions, and one hash-pinned Python
  wheel define a candidate with 20 required commands, 13 Python modules, three
  font families, and nine GDPVal artifact round trips spanning Office/PDF,
  spreadsheets, Chromium, compiled languages, ML, GIS, DXF, media, and OCR.
  The clean-tree builder uses a committed Git-blob allowlist, an empty Docker
  config, one local Unix daemon, a unique local tag, an immutable staged host
  verifier, and an always-disabled default entrypoint. Host-owned bounded OCI
  conversion rejects traversal, duplicate JSON or archive members, symlinks,
  hardlinks, FIFOs, unreferenced blobs, digest/size/config/layer drift, and
  verify-then-reopen races. Capability observations include exact package
  records; deterministic SPDX generation is reconciled bidirectionally by
  package, purl, SPDXID, relationship, namespace, and inventory digest; license
  expressions use the SPDX registry and unknown or denied values fail closed.
  Evidence files are reopened with secure Unix flags and rebound to their
  subject, tool, semantic validator, and aggregate gate. A trusted exact-parent
  probe verifies effective network, rootfs, identity, capability, privilege,
  memory, PID, and CPU controls before any candidate code can run. On the local
  host, unsupported CPU and PID cgroups keep containment failed, leave the
  capability receipt, SBOM, and license evidence absent and `not_run`, verify
  only the OCI layout, and keep the aggregate blocked. The exact checkpoint
  candidate has image ID `sha256:faed2a1b0638d9a34e2144eb5914c78ea2a6c19f198d61aff03a8fb90bb0de78`
  and OCI manifest `sha256:5046051464690f95eb561c60cc424de42ce90a9764bba3a7b2580648749220c9`.
  Validation passes 57 Phase 1B static contracts, the exact degraded-host
  integration, 604 combined Agentic Sandbox compatibility tests, and the full
  credential-free backend with 2,608 passed, 6 host-dependent skipped, and 45
  integration tests deselected. CVE scanning, complete transitive artifact
  locks, signature, provenance, and a real Firecracker boot remain visible
  activation blockers. No login, push, promotion, model, Azure, grading,
  publication, or paid operation ran. Shipped through PR #148 from reviewed
  head `992b4feb6379eff756c9812d3ae5931808c7ea0d` as squash merge
  `6e6a463f087f7d3d229ce4f0c2de19349efbf8c4`. No automatic PR or `main`
  workflow run was created because the changed paths are outside every active
  automatic workflow filter; no manual workflow was dispatched to compensate.
- **Agentic Sandbox V2 model-free foundation** - add an explicitly
  non-production `agentic_sandbox_v2` execution contract with eight versioned
  tools, strict lifecycle and result schemas, three policy profiles, and a
  required `foundation_only=true` marker. The shared executor accepts only the
  built-in scripted fixture in non-paid mode and rejects model, client,
  credential, prompt, provider, custom-backend, publication, grading, and
  preprocessing inputs. Each fixture run uses a task-local process group with
  hard wall-time termination, descendant cleanup, descriptor-relative
  filesystem containment, prospective file/entry/byte caps, immutable package
  locks, exact terminal artifact byte binding, and canonical source/runtime
  identity. Private audit and public-redacted traces independently bind
  requests, results, state continuity, replay history, capability/package
  semantics, failures, and final deliverables. General Batch and Step 2 reject
  configured or overridden V2 mode before credentials or provider construction;
  V1 prompt, tool, limit, checkpoint, result, restore, import, and default-mode
  identities remain frozen. Final model-free validation passes **196 focused
  contracts** and the complete credential-free backend with **2,551 passed, 6
  host-dependent skipped, and 44 integration tests deselected**, with no
  warnings, clean static diagnostics, clean diff checks, and an independent
  security/release **APPROVE** after seven high-stakes review rounds and an
  iterative full-diff review. PyYAML parsing passes;
  actionlint and Ruby are unavailable in the local validation environment. No
  model, Azure, grading, paid operation, or manual workflow dispatch ran. Real
  compute, package broker, web, model-loop, publication, and microVM integration
  remain deferred to later phases. Shipped through PR #146 from reviewed head
  `c969aa8d317f843c0060a64d466852c771f97f19` as squash merge
  `f4c0e9e65f2dc244fb7ffa59d4c1454cd3f0f0c4`. Automatic PR validation passed
  with deploy skipped; post-merge `main` validation and Pages deployment also
  passed. Each automatic validation made 23 unauthenticated public Hugging Face
  report reads with no fallback or failure; neither run used Hugging Face
  credentials, writes, uploads, or publication, nor invoked model, Azure,
  grading, or paid work.
- **GPT-5.6 Sol Max narrative and grading production policy** - move the
  dashboard narrative analyzer and the default v2 grading profile to
  `gpt-5.6-sol` with `reasoning_effort=max`; use the same identity for the
  main judge, visual perception, and bounded no-tools finalization while
  retaining `gpt-audio-1.5` for audio. Step 6 and Hugging Face publication now
  bind model, effort, runtime fingerprint, and model-backed narrative content;
  explicit all-null identity plus empty narrative remains the only model-free
  fallback. Semantic-invalid final envelopes receive one independent bounded
  retry, and grade schema 1.2 keeps unknown prices fail-closed as explicit
  `null`/incomplete provenance tied to the persisted model set while retaining
  numeric-cost compatibility for prior 1.0/1.1 payloads. The
  grading workflow defaults to a credential-free read-only dry run. Paid runs
  require `paid_approval=true`, a separate protected `grading` Environment
  approval, and then execute Azure OIDC from the environment-free `main`
  branch job so the federated subject remains branch-bound; chunk continuation
  preserves the exact config, inference revision, task limit, and approval
  input while requiring a fresh protected Environment approval for each newly
  dispatched workflow run.
  The remote `grading` Environment has one owner reviewer, administrator bypass
  disabled, and a custom `main`-only deployment policy. Self-review prevention
  remains disabled because no independent collaborator exists. Current manuals
  and specs identify Sol Max as production while preserving historical 5.4
  configs, results, and measurements. Final credential-free validation passes
  **2,358 backend tests** with **6 skipped and 44 deselected**, **94 Node
  contracts**, **9 analysis tests**, both changed workflows under actionlint
  and Ruby Psych, the TypeScript/Vite production build, and all **4 Chromium
  browser suites**. No Azure, model, paid grading, or Hugging Face execution
  occurred. Shipped through PR #144 from reviewed head
  `148c1838b185c01e97ccfd5286f08b8403a7c97b` as squash merge
  `bc27f882446a5c2c93ecd97e75b4c7cf8d9576f4`. Automatic PR validation passed;
  the post-merge `main` validation and Pages deployment also passed. Neither
  automatic run dispatched grading, Azure, model, or Hugging Face work.
- **Dashboard source-build provenance** - derive the displayed dashboard
  version from `package.json`, bind Pages builds to the exact checked-out
  GitHub SHA and repository, and link the footer to that full commit only after
  strict public-value validation. Local or malformed builds fail closed to a
  non-link label, while generated-data time remains a separate signal. The
  existing read-only PR validation job now checks published and local browser
  states, exact href and accessible name, keyboard focus, and desktop/mobile
  overflow without adding a workflow or changing Pages permissions. The
  accompanying refined Bolt records why README restructuring, a duplicate fast
  gate, and Action pin churn were deferred. Validation passes **3 focused
  contracts**, **92 aggregate contracts**, the production TypeScript/Vite
  build, the provenance browser matrix, and all four existing Field Notes
  browser suites. Independent code and workflow/security reviews returned
  **APPROVE** after a malformed repository-slug edge case was fixed and covered.
  No batch, grading, Azure, Hugging Face, deployment, or paid action ran during
  local validation. Shipped through PR #142 as
  `a9cc93bb07297332d4f6cfe1a4dea54e07d28fef`; automatic PR validation and the
  post-merge `main` validation/Pages deployment passed. The live dashboard was
  then verified to display `v0.2.0 · a9cc93b`, link to the exact full merge
  commit, expose the full source identity accessibly, and remain overflow-free
  at a 390px viewport.
- **Opt-in typed Azure AI Step 2 wiring** - activate the shipped typed route
  foundation only when `AZURE_AI_ROUTE_PROFILE` is nonempty, while preserving
  the profile-absent legacy constructors, progress shape, result shape, and
  workflow behavior. Step 2 preflights every Azure main, Self-QA, Code
  Interpreter, and recognized audio/video preprocessor workload before
  credential or client construction; binds canonical deployments to exact
  endpoint-free route records; verifies each instantiated client's runtime
  route and fingerprint before use; and includes those records in progress and
  final-result identity. One shared factory, distinct managed clients, and a
  role-aware owner enforce executor-first, reverse-client, factory-last cleanup
  across normal return, exceptions, and `SystemExit`. Typed provider failures,
  cleanup failures, and malformed or duplicate-member QA payloads are reduced
  to class-only diagnostics without erasing native or local runner details.
  Native-only conditions remain entirely legacy even when a profile is
  requested; native main plus Azure preprocessing uses only the typed
  preprocessor path. External typed resume checkpoints, positive wall-timeout
  relay, hardened/agentic typed execution, and workflow activation remain
  deliberately unsupported. Model-free verification passes **216 focused
  tests** and the complete credential-free backend with **2,211 passed, 9
  host-dependent skipped, and 44 integration tests deselected in 134.81
  seconds**. Ruff, `py_compile`, diff checks, and an independent release-gate
  review with **0 mandatory findings** pass. No credential, token, network,
  Azure/model API, grading, Hugging Face, workflow, deployment, or paid action
  occurred. A clean detached checkout of reviewed head
  `6ee41d2a89ff796dc06c238892fe5f78ec1f29a1` passes **216 focused tests in
  2.16 seconds** and the complete backend with **2,214 passed, 6
  host-dependent skipped, and 44 integration tests deselected in 137.30
  seconds**. Shipped through PR #138 as
  `4654b4316ecef30f19da55dd513b35d625f7d30d`. GitHub attached no check run,
  check suite, commit status, or PR check rollup to the reviewed or merge SHA;
  no workflow was manually dispatched to compensate.
- **Typed Azure AI runtime adapters** - add an opt-in managed client wrapper,
  caller-owned Code Interpreter client injection, and deterministic executor
  lifecycle without wiring Step 2 or workflows. Closed adapters reject all
  public client, route, fingerprint, context, and delegated access before an
  API call. Owned factories close after leases, shared factories and injected
  credentials remain caller-owned, and create/cleanup failures preserve the
  foundation exception chain. Code Interpreter keeps same-descriptor reference
  upload and provider-file cleanup while adding one initialization cleanup
  boundary for client, credential, prompt, and token-limit failures. Executors
  close only close-capable runners and never directly close raw LLM clients.
  The foundation documentation contract now binds its immutable BOLT and
  changelog entry without freezing the rolling latest-task record.
  A detached clean checkout passes **279 focused tests with 6 integration cases
  deselected**. Repeated clean-checkout backend runs completed with **zero
  failures**, **2,105-2,108 passed**, **6-9 host-dependent skips**, and **44
  integration tests deselected**. Ruff, `py_compile`, and
  `git diff --check` pass across the seven changed Python files and three
  completion records. These adapters remain `NOT WIRED`, and no credential,
  token, network, Azure/model API, Hugging Face, workflow, or paid action
  occurred. Shipped through PR #136
  (`d8e5796d0f4e4e3b0261fc4419eb5801feb88d07`) from reviewed head
  `9356e02d09b77f4a5cb010849548899b516360ec`. GitHub created no Actions run,
  check suite, or check rollup for either SHA because the ten changed paths do
  not match an active workflow trigger. No workflow was manually dispatched,
  and no credential, token, Azure/model API, Hugging Face, deployment, or paid
  action was used to compensate.
- **Typed Azure AI endpoint foundation** - add exact HTTPS endpoint contracts
  for direct Azure OpenAI v1, Foundry project, and explicitly authorized legacy
  rollback routes. Parsing rejects non-ASCII/control normalization, empty ports,
  malformed percent sequences, host lookalikes, and trailing dots before the
  exact Microsoft suffix/path allowlist. Strict identity is profile-specific,
  including direct verification of `AZURE_AI_EXPECTED_LEGACY_ACCOUNT`. The
  current `CodeInterpreterRunner is Azure-only`; a missing deployment follows
  the runtime's `gpt-4` default, while malformed model objects, explicit null
  deployments, and native-provider Code Interpreter fail. Audio/video
  preprocessors use only the runtime `deployment` field and defaults; other
  types are excluded. `DefaultAzureCredential`-based settings reject known
  static Azure key, token, secret, certificate, username, and password
  variables while allowing `AZURE_FEDERATED_TOKEN_FILE` and native
  `OPENAI_API_KEY`. Owned factory and token-check paths recheck the real process
  environment before constructing a credential even with explicit route
  settings; injected credentials remain caller-managed. Versioned fingerprints
  bind effective token scope and
  transport settings while emitted records remain endpoint-free, redacted
  provenance; the digest is not a confidentiality boundary and not a secret.
  Synchronous non-thread-safe factory/lease ownership and hardened one-write
  `GITHUB_OUTPUT` behavior are covered directly. Exact pins are
  `openai==2.46.0`, `azure-core==1.41.0`, `azure-identity==1.25.3`, and
  `azure-ai-projects==2.3.0`. An offline real-SDK construction smoke verified
  the canonical project OpenAI base URL and the exact capability contract:
  `responses.create`, `files.create`, `files.delete`, fallback `files.content`,
  `containers.create`, `containers.files.list`, and
  `containers.files.content.retrieve`. The current runner uses auto-container
  configuration rather than calling `containers.create` directly; that method
  is retained as a project-client compatibility gate. Credential and HTTP send
  counters remained zero and the credential stayed caller-owned. Raw and
  serialized condition discovery produce the same main, QA, and preprocessor
  workloads. A detached clean checkout passes the focused suite **224/224 in
  20.79 seconds**, the exact real-SDK smoke **1/1 in 1.47 seconds**, and the
  complete credential-free backend non-integration suite with **2,074 passed,
  9 skipped, and 44 integration tests deselected in 126.02 seconds**. Ruff,
  `py_compile`,
  `pip check`, exact-pin, `git diff --check`, conflict-marker, and exact
  eight-path scope checks pass. Runtime and workflow integration is `NOT WIRED`;
  no token, network, Azure/model API, Hugging Face, workflow, or paid action
  occurred. Shipped through PR #134
  (`fb3b7fe02ad54a3b095ffbea532a7b1703ba065b`) from reviewed head
  `127c948a9832d156d17b151ffe9cb6f063818f92`. GitHub created no Actions run,
  check suite, or check rollup for either SHA because the eight changed paths
  do not match an active workflow trigger. No workflow was manually dispatched,
  and no credential, token, Azure/model API, Hugging Face, deployment, or paid
  action was used to compensate.

### Changed
- **Agentic Sandbox V2 evidence and production containment split** - allow the
  fixed, Git-bound capability and SBOM probes to run when six effective
  collection-isolation checks pass, without requiring host CPU quota or PID
  controllers. Collection isolation combines runtime capability, `prctl`,
  route, memory, identity, and read-only-root observations with exact Docker
  HostConfig and network attachment; production containment remains a separate
  eight-check policy and still fails when CPU or PID controls are unavailable.
  Parent and candidate execution use immutable local image IDs with
  `--pull=never`; no candidate code runs before collection isolation passes;
  default-entrypoint behavior requires exact exit/stdout/stderr bytes; and all
  containers use predeclared UUID names with verified cleanup. On exact source
  `133df3f0aa5e4361c6c6cb7fd142ef5bdff8c1b5`, the local candidate image
  `sha256:dea418e4964c2e73bf77496633d0e16e5fc4fb66dddbb743d91d0020b672a77a`
  and OCI manifest
  `sha256:e55817b206dfc4fed855742b327bf6a7c7bdd3b08bc391c2470f9b16efa7f525`
  verify 20 commands, 13 Python modules, three fonts, all nine smokes, and a
  1,422-package SPDX SBOM. License policy remains failed on 1,255 unknown
  declarations with zero denied packages. The aggregate remains blocked by
  containment, license, CVE, microVM, provenance, and signature. Validation
  passes 93 Phase 1B static contracts, one exact Docker integration, 640
  combined Agentic Sandbox compatibility tests, and the complete backend with
  2,644 passed, 6 host-dependent skipped, and 45 integration tests deselected.
  No workflow, model, Azure, grading, registry push, publication, or paid
  operation ran. Shipped through PR #150 from reviewed head
  `870dfa9576e028fdf82dbcfbcd2bc61acc8e3085` as squash merge
  `a4f770627aea772203d54f472f4f9d956b0e3dfd`. No automatic PR or `main`
  workflow run was created because the nine changed paths are outside every
  active automatic workflow filter; no manual workflow was dispatched to
  compensate.
- **Microsoft Foundry workflow activation and OIDC enforcement** — extend the
  shipped typed endpoint foundation, runtime adapters, and Step 2 wiring into
  the active batch, report, publication, and grading paths. Inference,
  narrative, and grading use the Foundry direct
  `/openai/v1/` route; only Code Interpreter may use the project endpoint, and
  dated Azure OpenAI remains an explicitly authorized rollback profile. Batch
  and grading workflows reject static Azure keys, enumerate every configured
  workload before remote writes, compare OIDC client/tenant/subscription
  secrets with independent repository variables, and recheck the active Azure
  account plus `ai.azure.com` token claims after login. Route token preflight
  verifies the selected audience, including Cognitive Services only for the
  explicit legacy rollback. English/Korean onboarding now documents the typed
  routes, expected identities, and local/CI authentication contract.
- **GitHub repository About metadata** — replace the contradictory
  `220 tasks across 11 industries` description with a concise public value
  proposition for the tracked Gold Subset: 220 real professional tasks across
  9 sectors and 44 occupations, reproducible experiments, artifact validation,
  grading, and a live evidence dashboard. Keep the deployed dashboard homepage
  unchanged and reduce 20 mixed vendor/framework topics to 12 high-signal
  discovery topics centered on LLM evaluation, real-world professional tasks,
  artifact validation, benchmark automation, and the operating stack. The
  public GitHub page and repository API show the exact new description,
  homepage, and topic set; the metadata-only update created no commit or
  workflow run.
- **First-run execution contract** — expose fork-safe links to the live
  dashboard, tracked three-task config, Batch workflow, and result/artifact
  guide in both root READMEs. Rebuild the English/Korean Batch Runner quick
  starts around the executable wrappers, five OIDC/HF secrets, Azure OpenAI
  resource-endpoint contract, destructive HF boundaries, all eight workflow
  inputs/defaults, Step 6/7 destinations, and external-grading separation.
  Replace remote onboarding diagrams with repository-owned responsive SVGs and
  add an eight-test contract suite that parses the docs, workflow,
  and owning bootstrap/auth/report/upload code. Shipped through PR #127
  (`30906084dbee384f1c324a8b794cba5aef28170b`): automatic free PR run
  [29889565405](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29889565405)
  passed validation with deployment skipped, and automatic `main` run
  [29889682507](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29889682507)
  passed validation and GitHub Pages deployment. Neither run used manual
  dispatch, grading, Step 8, an Azure/model API, Hugging Face upload, or paid
  execution.

### Fixed
- **Foundry provenance, publication, and grading finality** — bind prepared,
  result, ordered-task, deployment-route, and runtime identities through Step 2
  checkpoints/final output, inference provenance sidecars, HF CAS publication,
  grading cache/resume, and every partial/diagnostic save. Impossible
  profile/endpoint/workload combinations fail closed; grading downloads require
  the sidecar unless an explicit non-publishable legacy-analysis override is
  used. Provider errors are projected to stable endpoint-free public values
  before relay or final-result fingerprinting. Subset and legacy grades use
  full ordered-task-hash diagnostic paths and cannot collide with root final
  grades; nested analysis artifacts follow the exact emitted path. Cost sweeps
  translate archived endpoint fields to the typed contract, hash
  repository-contained generated configs, and consume only Step 8's exact
  `GITHUB_OUTPUT` path. Sidecar bytes participate in the core publication plan,
  receipt, and finality checks while stale full Step 2 JSON is removed from the
  public managed tree. Step 6 removes its unused experiment-model fallback:
  after up to two primary `gpt-5.4-pro` calls, any setup, call, parse, or route
  failure emits a model-free report and prevents the second call after an
  invalid, partial, empty, or whitespace-only first response. Typed relay
  restore recomputes the endpoint-free route plan before accepting a checkpoint.
  A shared versioned per-status validator
  rejects malformed success/error/QA/pending rows on local save/restore and
  relay status/upload, while Code Interpreter is rejected outside the
  project-only profile at runtime mode, route selection, and restored-route
  boundaries before client construction. Inference provenance schema v2 binds
  execution mode and rejects route-less/non-project Code Interpreter sidecars
  across formatting, download, bootstrap, and HF publication. Azure
  hardened execution constructs its typed client only after the signed
  authorization and budget reservation; profile-absent runs fail before
  executor creation, and capability-rejected deferred candidates close before
  ownership transfer. The common hardened baseline closes each deferred client
  at task finalization and any residual client at idempotent runner shutdown;
  cleanup failures expose only `provider_cleanup_failed:<Type>`. Main, vision,
  audio, v1 single/batch grader, local
  audio-preparation/tool-dispatch, initialization, and cleanup exceptions use
  class-only public identities; owned clients are released even when close
  fails, without retaining the raw cause or context. Grading cache/resume and
  all output states require the exact non-null primary grader fingerprint, not
  any tier/perception route match, while cleanup failures preserve durable exit
  codes 0, 6, and 7. One shared schema/cross-field validator protects Step 8 and
  both workflow commit gates before and after rebase. OIDC session checks bind
  token `aud`, `nbf`, and `exp` in addition to tenant and client claims.
  Relay cleanup finality revalidates the exact child against the full
  publication plan, including optional README bytes. Frontend skill discovery
  ignores generated cache directories. Model-free route planning no longer
  imports Azure/OpenAI SDKs until credential or client construction, so the
  Node-only aggregate gate runs without paid-runtime dependencies.
  Credential-free validation passes 2,328
  backend tests with 6 skips and 44 integration
  deselections, 89 frontend data contracts, nine onboarding contracts, the
  production build, four browser suites, Ruff, Python compilation, actionlint,
  shell syntax, and diff checks. No workflow dispatch, Azure/model call,
  grading run, Hugging Face write, or paid execution was used for this
  validation. Shipped through PR #140 as
  `f730068a64b2ebe04c42eb68cea696fd69e1e978`; updated PR run
  [30146185099](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/30146185099)
  passed validation with deployment skipped, and automatic `main` run
  [30146254229](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/30146254229)
  passed validation and GitHub Pages deployment. The first PR run
  [30145929181](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/30145929181)
  found the eager SDK import and was superseded by the validated lazy-import
  fix. None of these automatic runs performed Azure/model calls, grading, or
  Hugging Face writes.
- **Batch relay provenance and recovery integrity** — require exact `main` and
  equal workflow/event SHAs before checkout, bound canonical timeout/relay
  inputs, pin every continuation to the initial `source_sha`, and keep relay
  dispatch on `main`. Checkpoints now restore, upload, and clean up against the
  validated full `data.source` rather than a reconstructed YAML-stem repo.
  Continuations fail before Azure login/model construction when progress,
  lineage, prepared fingerprint, or referenced deliverables are missing or
  invalid. The 290-to-350 gap is now reported as nominal step-timeout headroom,
  not guaranteed relay handoff time; overlapping runs sharing one HF target are
  explicitly unsupported because GitHub concurrency is not a durable queue.
  Checkpoint payloads live under content-addressed generations; `current.json`
  advances only after one immutable HF revision has the exact file tree and
  matching SHA-256/size manifest. Restore and cleanup require the same source
  SHA and lineage; cleanup deletes the whole current-tree lineage in one
  exact-HEAD CAS commit. Step 0 propagates lookup/auth/network errors, never
  auto-deletes an existing partial repo, and validates every parquet-declared
  reference as a unique regular non-symlink file. A non-mutating write-access
  preflight rejects read-only targets before task preparation, Azure login, or
  model spend. Path cleanup does not erase prior HF revisions and failed
  operations may leave forensic orphan generations. The required SDK is pinned
  to the verified `1.24.0` contract. Step 0 authenticates first and creates
  targets with `exist_ok=False`, treating only HTTP 409 as reuse and never
  deleting partial or legacy targets. New targets derive from the pinned public
  source revision; reused targets are downloaded at an exact HEAD into fresh
  staging and accepted only when the schema-v4 manifest, canonical target
  columns and source projection, ordered task identity, complete physical
  reference tree, and every declared reference SHA-256/size match. Relay
  uploads download and verify the immutable payload revision before advancing
  `current.json`, require a complete ordered result set, and confirm successful
  cleanup in the same invocation when the CAS response is lost. Relay progress
  now accepts only canonical task IDs and known terminal/pending statuses, and
  every declared deliverable path must remain under its owning task directory.
- **Canonical batch input and publication integrity** — upgrade the source
  manifest to schema v4, binding all 220 ordered task IDs to prompt, taxonomy,
  rubric, ordered reference path/URL/URI semantics plus 261 declared reference
  SHA-256/size records from pinned `openai/gdpval@11e7900...`. Step 1 requires
  and rechecks that projection before writing prepared tasks; Step 2 rechecks
  prepared identity before provider-client construction. References move into
  read-only private per-task staging before preview, preprocessing, codegen, or
  execution, with same-file-descriptor hashing/copying, basename-collision and
  partial-copy rejection, and fatal provider upload/local/Docker copy errors.
  Code Interpreter input IDs are deleted best-effort after normal or failed
  tasks, and provider uploads preserve each verified reference basename. The
  common sandbox keeps private local staging while the hardened remote backend
  preserves opaque reference IDs instead of treating them as host paths. Each
  task output tree is removed with symlink-aware semantics before the first run
  and every QA retry so resumed execution cannot inherit stale deliverables.
  Condition A retains the publication/relay upload root while condition B uses
  an isolated tree, preventing a second condition from deleting or replacing
  the bytes selected for publication. Step 2 binds each declared deliverable to
  same-descriptor SHA-256/size records and a canonical result fingerprint.
  Step 0 creates and clears every submitter column, rejects stale scalar,
  list, URL/URI, and physical deliverable state on reused targets, and never
  auto-deletes partial repositories. Step 4 rebuilds production selected rows
  from current results only and revalidates the full source projection and
  reference bytes after model execution. Step 7 rechecks each published source
  row, the one canonical parquet shard, row-to-task deliverable paths, canonical
  URLs/URIs, exact local file tree and bytes, and a required non-dry
  `self_report.json`. A run-specific publication generation is created by Step
  1, preserved across relay legs, and checked before provider construction;
  Step 3 and publication share one production-shaped projection of prepared
  metadata and raw Step 2 QA/results. Parquet submitter fields and self-report
  task status, QA/error projection, summary, content, and files must exactly
  match that result. Every selected reference byte is rechecked before provider
  construction. Publication holds verified source bytes in private anonymous
  streams so the SDK cannot reopen changed local paths. Step 5 records
  file-required failures without creating dummy files or mutating the parquet.
  Relay marker writes reconcile ambiguous responses without retry; restore
  records the exact generation and cleanup refuses a newer generation. Relay
  dispatch requires both process exit code 42 and pending tasks. Step 0 records
  the validated target HEAD; one `create_commit` requires that HEAD as
  `parent_commit`, then verifies direct ancestry, plan marker, complete remote
  tree/hash, self-report identity, and final HEAD. A private receipt binds that
  plan, and post-cleanup finality accepts only the exact cleanup child with an
  unchanged managed tree. Non-relay finality reuses the already verified
  publication revision instead of downloading managed files twice. Core paths
  shipped through PR #129
  (`2d4026056b6e27f5111a94d1089573f6b4938a58`): automatic pull-request run
  [29919172383](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29919172383)
  passed validation with deployment skipped, and automatic `main` run
  [29919336511](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29919336511)
  passed validation and GitHub Pages deployment. Relay cleanup commits now
  store the short generation label in the Hub commit title and the full
  64-character generation marker in its description; response-loss
  reconciliation and publication finality verify both SDK fields and the direct
  parent before accepting cleanup. Final credential-free evidence is **1,853
  passed, 6 skipped, and 44 integration tests deselected** across the backend;
  the relay checkpoint matrix passes **83/83**, HF publication/finality passes
  **86/86**, and their combined focused matrix passes **169/169**. The cleanup
  identity follow-up shipped through PR #131
  (`576e6f4f4a72998f0311d74006373bcea40a3cf6`). Its code and test paths are
  outside the Pages workflow's pull-request and push filters, so GitHub created
  no automatic run for the PR head or merge SHA. No manual workflow dispatch,
  Hugging Face write, Azure/model call, grading run, or paid execution was used
  to compensate for the path-filtered check.
- **Hermetic deliverable-selector contract tests** — replace import-time pandas
  and ignored local-parquet loading with a checked-in 28-task synthetic signal
  corpus. The 6,889-byte canonical fixture is self-hashed and binds exact public
  `openai/gdpval@11e7900...` task identities to the source parquet SHA-256,
  220-row count, and per-task prompt/ordered-rubric hashes without storing full
  prompts, rubrics, references, deliverables, grades, or model output. A
  stdlib-only verifier validates the fixture offline; optional delayed pandas
  verification checks the known local public snapshot. Clean checkouts now
  collect all selector tests without pandas, PyArrow, parquet, or network. The
  selector/verifier suite passes 15/15, root scripts pass 44/44, and adjacent
  grading tests pass 90 with 2 environment skips. Production selector and
  grader code are unchanged; no grading, Step 8, model/API, HF upload, manual
  workflow, network fetch, or paid execution occurred. Shipped through PR #124
  (`a82776113d617b3fa4bd12c480f36b51cd7b16a3`); automatic free
  `Aggregate Tests & Deploy` run
  [29862415519](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29862415519)
  completed validation and Pages deployment successfully.

### Changed
- **Execution-first repository onboarding and publish gates** — reorganize both
  root READMEs around live evidence, a credential-free local preview, and an
  honest three-task cloud path. English/Korean beginner guides now explain
  OpenID Connect, disposable public Hugging Face targets, destructive bootstrap
  and upload boundaries, Self-QA vs external grading, report fallback cost,
  artifacts, troubleshooting, and cleanup. Pages automation separates a
  read-only PR validation job from main-only deployment; automated result
  PRs are proven before HF upload, rechecked after upload, and dispatched for
  exact-head-SHA validation without Pages/OIDC privileges. Shipped through PR
  #120 (`9892a4c7566a0c5ba24f876459d5932ee7284357`).
- **Success Field Note retrospective voice** — revise
  `what-does-success-mean` without changing its evidence contract, metrics,
  source links, or fail-closed behavior. The six chapters now follow a
  plain-language 상황→태스크→액션→결과→가설 검증→근본 원인 sequence: reduce
  220 outcomes to two comparable tasks, reduce validation to three answerable
  questions, name the workbook's required analysis, summarize three discoveries,
  test the original handoff-ready hypothesis, and trace the root cause to four
  questions compressed into one status. The copy distinguishes the `200/220`
  report success-rule pass rate from process completion, leaves briefing
  fidelity and external quality unverified, and retains all 30 citations and ten
  evidence targets. All 77 aggregate contracts, the production build, and the
  runtime, integrity, perception, and success browser suites pass; the four
  browser suites complete in 48.201 seconds with no mobile overflow. Shipped
  through PR #118 (`f3648f72`) and successful Pages run
  [29757449226](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29757449226);
  public mobile and desktop checks verified all six revised chapters, the three
  validation questions and discoveries, the rejected hypothesis, report-success
  semantics, unverified briefing fidelity, 30 citations, ten evidence targets,
  and zero overflow or SVG label overlap.

### Fixed
- **Grading workflow trust-boundary hardening** — archive the completed May 24
  cost sweep outside `.github/workflows` so it cannot be dispatched again,
  while preserving its exact workflow source beside the historical results and
  marking the former live status/trigger guide as archived.
  The active grade workflow remains one job with its existing three pushes,
  chunk-resume contract, and two follow-up dispatch paths, but now accepts only
  an exact `main` workflow/event SHA, verifies the checked-out branch, upstream,
  remote SHA, publication credential, experiment, and grading config before
  Azure/HF access, and passes all eight dispatch inputs to shell through
  validated environment variables. External actions are pinned to reviewed
  40-character commits and the unused `pull-requests: write` permission is
  removed. This is a fail-closed operational guard, not a protected privilege
  boundary; repository rulesets and a protected grading environment remain a
  separate follow-up. No workflow, model/API call, grading run, HF write, or
  paid execution was dispatched by this change.
- **Pages main deployment gate** — remove the invalid assumption that the
  repository's unprotected `main` branch reports `github.ref_protected=true`.
  Push/manual deployment remains restricted to `refs/heads/main`, while
  validation-only result-PR dispatches still require their exact branch,
  `github.sha`, `github.workflow_sha`, and expected SHA. This repairs failed
  post-merge run `29836869345` without granting Pages/OIDC permissions to PR
  validation jobs. Shipped through PR #121
  (`138e89a8e3a56e86a836656e2572669786cbc0cf`); PR validation run
  [29843523709](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29843523709)
  passed without deployment, and automatic main run
  [29843751719](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29843751719)
  completed validation, artifact upload, and Pages deployment successfully.
- **Inference/report identity and fallback integrity** — hash the complete
  canonical Step 1 prepared payload, persist that fingerprint through relay
  checkpoints and final inference, and reject stale or mixed Step 1/2 inputs in
  Step 3. Experiment IDs and HF targets are path/branch-safe before Step 0.
  Step 6 is now strictly pre-grading, derives HF links from the run's source,
  isolates explicit external result files from current workspace manifests and
  recovery stats, distinguishes dry-run publication, and falls back to a
  model-free report when narrative generation fails. Result PR output and its
  one-file contract are mandatory before destructive HF publication, preventing
  silent no-PR success or stale `self_report.json` upload.
  Relay legs now carry a stable lineage ID across GitHub run IDs, while
  condition A/B use isolated progress and result files. Canonical HF repository
  validation rejects unsupported length and punctuation before credentialed
  bootstrap.
- **Archived v1 cost-sweep template resolution** — point the historical
  `grading_cost_sweep.py` renderer at the tracked
  `grading_configs/_archive_v1/_sweep_template.yaml` after task 207 moved the
  v1 reproduction assets out of the active config directory. A regression test
  freezes the archive path, schema v1 identity, and absence of a duplicate
  top-level template. The two known root-test failures are resolved: the full
  cost-sweep module passes 13/13 and `scripts/__tests__` passes 39/39. Active v2
  grading, workflows, models, prices, and budgets are unchanged; no sweep,
  Step 8, model/API call, grading run, HF upload, manual workflow, or paid
  execution occurred. Shipped through PR #114
  (`16305fd7c0661fdcb07bd298bfd4a9ccf4ffb381`); only the automatic free
  `Aggregate Tests & Deploy` run `29731574595` executed, and it succeeded.

### Added
- **Localized responsive README diagrams** — add twelve repository-owned SVGs:
  English and Korean desktop/mobile versions of the first-run decision, system
  map, and operational controls. Static SVG replaces remote Mermaid rendering;
  each asset has intrinsic dimensions, accessible title/description, at least
  6.04:1 primary text contrast, and a 960px responsive breakpoint. Browser
  geometry checks cover nearest-card spacing and overflow across mobile,
  tablet, and desktop widths.
- **Evidence-backed success Field Note** — rebuild
  `what-does-success-mean` as a retrospective that separates the team's initial
  handoff-ready expectation from exp026's observed execution, artifact integrity,
  requirement fidelity, and still-unknown external quality. A generated
  `success-note.json` contract joins the exact exp026 report summary and task QA
  map to a pinned Hugging Face revision, byte hashes, two task instructions,
  manifests, and directly inspected XLSX/PPTX/PDF structure. The article now
  derives its metrics, four-layer responsive SVG, Self-QA chart, six reflective
  chapters, and 30 inline citations from strict evidence; missing, duplicate,
  malformed, newly graded, or drifted data hides the complete evidence-bearing
  article behind an alert. Workbook coverage is measured at 35/500 while the
  selected file still opens; the briefing's PPTX/PDF parity is measured at
  32/32, but citation depth, financial accuracy, and external quality remain
  explicitly unverified. A shared schema-aware grade identity helper prevents
  dummy, legacy, filename, or source-pointer grades from being misattributed.
  CI streams six pinned HF files through timeout and byte caps before SHA-256
  validation and runs all four Field Note browser suites before Pages upload.
  All 77 aggregate contracts, production build, and four browser suites pass in
  47.996 seconds; no model, grading, batch, HF write, manual workflow, or paid
  execution was dispatched. Shipped through PR #116 (`85e21b30`) and successful
  Pages run
  [29746868595](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29746868595);
  public checks verified the generated 200/220 execution snapshot, 35/500
  workbook coverage, 32/32 briefing parity, external-quality `unknown`, the
  four-layer responsive hero, 30 inline citations, ten pinned evidence targets,
  contract/artifact back-references, reflective typography, and zero horizontal
  overflow on mobile and desktop.
- **Evidence-backed perception Field Note** — rebuild
  `from-audio-to-multimodal-sandbox` around exact exp011/exp012/exp026 report
  snapshots, checked-in package/audio/video/sandbox configuration, and three
  pinned architecture commits. A generated `perception-note.json` contract and
  strict selector now derive the article metrics, three-stage SVG, dual-axis
  chart, six reflective chapters, and inline citations from validated evidence;
  missing, duplicate, malformed, or drifted report/source data hides the full
  numeric article behind an alert. The note preserves the exp012 17-task/YAML-
  date/report-date metadata conflict, treats configured paths separately from
  unknown analyzer invocation counts, and refuses causal attribution because
  scope, model, reasoning, runner, Skills, and execution identities differ.
  Twelve detailed evidence entries link report rows, immutable config/code line
  ranges, and pinned history. Pages now regenerates on every direct source,
  package, workflow, or Skills-registry change and runs runtime, integrity, and
  perception Chromium suites before upload. All 65 aggregate contracts, the
  production build, and all three browser suites pass; the browser gate takes
  41.71 seconds locally and dispatches no model, grading, batch, HF upload, or
  paid workflow. Shipped through PR #112 (`0f9761d7`) and successful Pages run
  [29678863958](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29678863958);
  public checks verified the generated non-causal contract, report-derived
  `25/25 → 24/25 → 23/25` Information sequence, responsive SVG/chart, 34 inline
  citations, 12 detailed evidence targets, pinned source ranges, back-reference
  navigation, reflective typography, and zero horizontal overflow on mobile and
  desktop.
- **Inline citations for the integrity Field Note** — connect the thesis and
  each evidence-bearing paragraph in `honest-pipeline-lower-score` to ten
  numbered source notes. Citations jump to detailed report, config, pinned
  pre/post-fix code, PR #38, and causal-boundary entries; every evidence entry
  shows its immutable commit and line range where available, and links back to
  each citing paragraph. A shared validator rejects duplicate, unknown, unused,
  malformed, or misaligned citation/evidence contracts before rendering. The
  citation trail remains inside the existing 2.05 reading rhythm, uses 9px
  superscripts and 24px return targets on mobile, and introduces no horizontal
  overflow. Existing Field Notes remain compatible and continue to show numbered
  evidence rows, with each row title acting as its explicit source link. All 56
  aggregate contracts, production build, and runtime/integrity Chromium suites
  pass; no model, batch, grading, upload, or paid workflow was dispatched.
  Shipped through PR #109 (`4647a6ce`) and successful Pages run
  [29673420824](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29673420824);
  public mobile and desktop checks verified all forward citations, detailed
  pinned sources, back-references, sticky-header offsets, and overflow bounds.
- **Evidence-backed integrity Field Note** — rebuild
  `honest-pipeline-lower-score` from exact exp013/exp025 report snapshots,
  checked-in experiment config projections, and pinned PR #38 code history.
  Metrics, SVG, chart, and numeric prose now derive from validated sources;
  malformed, duplicated, stale, or contract-drifted evidence hides the entire
  article sequence behind an alert. The note presents the observed `-13.6%p`
  completion gap separately from the proven `_AVAILABLE_FILES` persistence and
  `qa_failed` classification changes, explicitly refusing causal attribution
  because execution Git, input revision, Azure model revision, and runner
  identity are missing. Five reflective chapters use shorter headings, wider
  spacing, 2.05 leading, and quieter callouts to create a deliberate
  관측→불변식→판정→비교→결정 rhythm. The serialized Pages job now regenerates on
  integrity-source changes and runs both runtime and integrity Chromium suites
  before deploy. No model, batch, grading, HF upload, or paid workflow is
  dispatched. Shipped through PR #105 (`8a64f1bf`) and successful Pages run
  [29649567174](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29649567174);
  the deployed JSON, non-causal hero, report-derived chart, pinned source links,
  and reflective typography were verified on desktop and mobile.

### Changed
- **Local merged-branch consolidation** — a post-merge local audit removed
  eight pre-existing linked worktree paths and 23 pre-existing sandbox,
  agentic, prompt, and note branch refs backed by merged PRs. The dirty
  `hyeonsangjeon-sandbox-preflight-final-status`, closed-unmerged
  `docs/prompt-note-deploy-result`, and no-PR
  `hyeonsangjeon-agentic-job-metrics-run-correction` refs were preserved. No
  remote ref, stash, or primary-worktree file was removed; the attempted local
  `main` ff-only update stopped without changing files when concurrent local
  work appeared.
- **Evidence-backed runtime Field Note** — rebuild the `360-minute-experiment`
  note around three explicit sources: exp008/010/025/026 report snapshots, the
  current condition-a workflow policy, and a pinned exp025 incident record.
  The note now separates the incident-time 330-minute hard stop from the
  post-fix 290-minute watchdog, 350-minute step ceiling, and 360-minute job
  ceiling; derives metrics, timeline SVG, resume chart, and numeric prose from
  validated data; and fails closed on missing, malformed, stale, or mismatched
  evidence. Five shorter chapter headings, chapter labels, wider section
  spacing, 2.05 body leading, and quieter serif callouts give the retrospective
  a deliberate 사건→편향→대응→결과→결정 reading rhythm on desktop and mobile.
  The Pages workflow now regenerates this evidence when either runtime source
  changes and gates deployment on all aggregate contracts plus pinned-history
  and Chromium desktop/mobile checks. No model, batch, grading, HF upload, or
  paid workflow is dispatched by this change. Shipped through PR #102
  (`fe222493`) and successful Pages run
  [29628757147](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29628757147);
  the deployed JSON, two-lane timeline, report-derived chart, source links, and
  reflective typography were verified on desktop and mobile.
- **Bounded Agentic Sandbox runtime and preregistered experiment** — implement
  separate `agentic_sandbox` and common hardened-baseline paths with ordered
  Responses tools, deterministic finalization, exact task/request/input and
  selection identities, crash-safe SQLite budgets, Ed25519 single-use live
  approval, fixed-denominator comparison endpoints, optional dashboard fields,
  and legacy omission. Split credential and compute planes use mTLS plus
  deadline-bound HMAC envelopes, bounded streaming JSON, exact sequence retry,
  no-network/non-root Docker, quota-backed work volumes, an in-process generated-
  code seccomp launcher, isolated rendering/verifier containers, component/SBOM
  identity, and auditable terminal cleanup. Manual image and dedicated-runner
  workflows require a protected exact `main` SHA; unfinished agentic publication
  remains opt-in and fails closed until immutable dependency locks exist. Local
  model-free validation passed 1,485 Python tests, 54 Node aggregate tests,
  TypeScript/Vite build, two Chromium suites, image audit/SBOM equality, and WAV,
  XLSX, DOCX, and PPTX Docker E2E. No model/API call, task selection, workflow
  dispatch, image publication, HF upload, grading, or paid run occurred. Exact
  5/20 cohorts, production locks/image identities, dedicated-host preflight, and
  signed owner approval remain required at the paid gate; package installation,
  model-visible shell, and Anthropic support remain deferred.
- **Model-free Track 2 preflight workflow** — add a main-only, read-only manual
  workflow for private pinned cohorts. It validates compact JSON identities
  before checkout, checks out the exact event SHA with credentials disabled,
  pins Action commits and Python 3.11.9, installs a 27-package binary-only
  SHA-256 lock, verifies source/planner/config/grader identities before exposing
  `HF_TOKEN`, and uploads the exact plan plus environment. No Azure login,
  model client, Step 8 grading, repository write, or child dispatch is present.
- **Task-scoped inference download** — allow the HF downloader to require an
  exact ordered source prefix and fetch only those task directories. This keeps
  Stage B preflight limited to the pinned first ten tasks instead of downloading
  the full private deliverable tree.
- **Exact model-free Track 2 cohort planner** — add a direct-entry CLI that
  executes the production selector, routing, and shared visual-preflight
  validator before counting judge-bound routes and render-perception calls. It
  requires a clean checkout and exact expected planner, repository, inference,
  config, grader, rubric, and ordered-task identities, and emits item-level
  plans without creating an Azure client or making model calls.
- **Track 2 isolated cohort configs** — add Stage A three-task and Stage B
  ten-task validation configs whose parsed runtime semantics exactly match
  `default_v2_mini`; distinct config names, hashes, grader-source identities,
  and output paths prevent either stage from overwriting the accepted one-task
  canary or each other.
- **Track 2 cohort expansion preregistration** — add a dated, immutable
  two-stage plan for expanding the accepted exp003 one-task canary to three and
  then ten tasks without overwriting the canary artifact. The plan fixes task
  IDs, inference/rubric identity, cost and wall-clock gates, provenance checks,
  stop conditions, and a retrospective log. Preflight found and corrected an
  XLSX `Sound Technician` false audio route, then rejected Stage A attempt 1
  after audit exposed unsafe automatic precheck verdicts. Corrected Stage A run
  `29572067428` then passed all gates from merged `main`: 3/3 tasks, 153
  judge-bound items, zero errors, complete usage, exact 4/4 render-perception,
  confined provenance, USD 1.08 effective cost, and 24.9 artifact minutes.
  Stage B retry `29600523299` later passed all runtime gates: 10/10 tasks,
  435 items, zero errors, complete usage, exact 26/26 render-perception,
  confined provenance, USD 2.15 raw / USD 1.73 effective, and 73.4 artifact
  minutes. Full-220 now requires a separate chunk/resume and audio-aware plan.

### Fixed
- **Shared grading finalization retry budget regression coverage** — add a
  model-free test proving that an empty final response followed by malformed
  JSON consumes the same single bounded retry budget, stops after two API
  calls, preserves accumulated token/cache accounting, and leaves a later
  scripted response unused. A local grading/Track 2 branch audit found no
  missing runtime implementation: prior fixes were already merged or safely
  superseded. The cleanup removed 26 stale local refs and 19 clean worktrees
  while preserving the five-file dirty `fix/grading-final-json-recovery`
  worktree for separate review. No remote branch, model/API call, grading run,
  workflow dispatch, HF upload, or paid execution was changed or triggered.
- **Long grade output atomic persistence** — bound `_save_json` temporary
  basenames with a 16-hex SHA-256 identity instead of copying the full final
  filename. Stage B run `29591036089` completed all ten paid tasks but the
  legacy 242-byte basename plus temp decorations reached 256 bytes and failed
  Linux `NAME_MAX=255` before any JSON, commit, analysis, resume, or artifact.
  The final output name and same-directory atomic replace remain unchanged;
  exact 242-byte round-trip, replace-failure cleanup, Step 8, and broad tests
  pass. Post-fix model-free run `29599249906` reproduced the exact 435-item,
  436-judgment, 26/26 plan with zero errors under the new grader identity. A
  second owner-approved paid attempt persisted successfully. The rejected
  attempt remains conservatively booked at USD 3.81; cumulative raw Stage B
  cost is USD 5.96, below the USD 10 cap.
- **Mixed-format visual bundle preflight** — filter harness rendering to stable
  supported paths while retaining all selected paths for main-judge evidence.
  Stage B preflight run `29583415563` exposed nine organization-chart criteria
  whose DOCX/PDF/XLSX bundle was rejected solely because DOCX is not renderable;
  the corrected boundary renders PDF/XLSX, records the filtered DOCX, and keeps
  unsupported-only visual targets fail closed. Runtime and planner now validate
  split children and item/task caps in the same pre-render order. Corrected
  model-free run `29589077065` passed all first-10 gates with 435 items, 436
  judgments, 26/26 render-perception calls, zero prechecks/audio/errors, and one
  audited filtered DOCX path. The accepted paid artifact matched every planned
  route, selected path, and perception call.
- **Exact planner perception accounting** — bump the planner contract to v2,
  count audio separately from harness-owned visual calls, enforce visual/audio
  task caps, and fail closed whenever an audio route exists because the main
  model chooses whether to invoke the audio tool. Lazy Azure/OpenAI imports and
  lazy `core` package exports let model-free planning run without paid-runtime
  clients or the unrelated dataset stack.
- **One-verdict grading config contract** — remove unused `grades_per_task: 3`
  metadata from active v2 configs and document the implemented behavior: one
  final verdict per rubric item, with bounded tool and finalization calls. This
  changes config identities but does not add repeat grading or paid calls.
- **Fail-safe rubric classification** — disable all automatic natural-language
  prechecks after Stage A attempt 1 exposed seven invalid extension-only
  verdicts and further review found compound, negated, and partial-match risks
  in filename, worksheet, and count rules. Every filename, extension,
  worksheet, file/count, page, and word criterion now reaches the judge, while
  stale precheck IDs cannot score an item. Active configs record
  `precheck_patterns_version: v2` as identity metadata only. The rejected grade
  and analysis were removed before the corrected rerun. The same audit removed
  a false visual route where `chart-of-accounts` was read as a visual chart;
  the checked-in 220-task supported-vision inventory is now 466 calls. The
  corrected Stage A artifact contains zero precheck decisions and zero judge
  errors across all 153 items.
- **File-compatible audio routing** — retain criterion-level audio
  classification for inventory, but downgrade runtime routing to text when the
  selected targets contain no supported audio extension. This prevents an XLSX
  `Sound Technician` cost criterion from suggesting `probe_audio`. Selection,
  routing, and `read_deliverable` now share one WAV/MP3/FLAC/OGG/M4A/AAC set;
  extensionless targets remain conservatively audio while known unsupported
  suffixes downgrade to text. Recomputed cohort plans contain zero false audio
  routes; the final exact Stage A plan after all corrections requires 4 render
  and 4 perception calls.
- **Field Note benchmark data source** — replace duplicated completion and
  Self-QA literals in the prompt-complexity article, SVG hero, metric strip,
  result narrative, and comparison chart with an exact exp003-exp005 selector
  over `generated/reports-index.json`. Experiment detail headers now apply the
  same index `meta` and `summary` snapshot while retaining the lazy-loaded full
  report for task-level evidence. The selector requires one unique row per ID,
  the expected Baseline/Elicit/Elicit v2 conditions, subprocess mode, valid
  finite ranges, and count/rate consistency; missing or invalid data renders an
  explicit alert instead of stale fallback numbers. The article links directly
  to the source JSON and all three experiment detail pages, including
  accessible mobile card navigation. Shipped through PR #90 (`b9e224a`) and
  successful Pages run
  [29475359417](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29475359417);
  the deployed JSON, article, and exp003 detail values were verified to match.
- **Public task-spec privacy cleanup** — remove a provider-account failover
  specification and unreferenced hidden sweep metadata, generalize
  organization-specific monthly budget and capacity statements, and keep
  reproducible per-run cost measurements intact. Personal `tasks/**` files are
  now ignored by default while the canonical latest-task result remains
  tracked. The modified public tree passes Gitleaks v8.30.1 with zero findings
  and contains no matching account relationship, exact monthly operating
  budget, personal email, Azure resource identifier, or local-path patterns.
- **Finalization retry cost guardrails** — normalize configured finalization
  retries to zero or one, so `judge_max_retries` values above one cannot expand
  the paid recovery budget. If a supposedly tool-free finalization response
  unexpectedly requests a function call, reject it without dispatching any
  read or perception tool and return a score-excluded error. Deterministic tests
  now prove two-call latency, TPM-guard, token/cache, and incomplete-usage
  accounting across malformed-final recovery. Shipped through PR #88
  (`2728ef7d`); the merge triggered no workflow or paid run.
- **Tool-calling malformed-final recovery** — extend the bounded
  finalization-only retry from empty output to syntactically unparseable final
  JSON, as observed for two text criteria in canary run 29432455047. The retry
  reuses ordered evidence with no tools, low reasoning, and complete usage
  accounting. Valid JSON objects with invalid semantic envelopes are not
  retried, and retry exhaustion remains fail-closed.
- **Tool-calling empty-final recovery** — when a Responses API tool loop ends
  with an empty final message (observed after five successful reads in canary
  run 29429183215), issue at most one finalization-only retry using the existing
  evidence. The retry removes tools and parallel tool calls, lowers reasoning
  to `low`, preserves ordered response items, and keeps complete call, latency,
  input, output, and cache accounting. Retry exhaustion remains a score-excluded
  `empty_final_text` error and Track 2 still exits fail-closed. Shipped through
  PR #81 (`a68a3efe`).
- **Grading canary runtime fail-closed guards** — revert the invalid grade and
  analysis produced by run 29424766879 after 35 Azure requests rejected a
  106-character `prompt_cache_key` and the single vision response failed its
  semantic envelope. Tool-calling cache identities are now deterministically
  bounded to Azure's 64-character limit, while the vision prompt states the
  exact score/confidence/string contract and logs only safe validation reasons.
  Track 2 persists a schema-valid diagnostic but exits nonzero after an actual
  main/perception/render runtime failure or incomplete usage, excludes error
  tasks from score summaries, and rejects failed cache/resume artifacts before
  grader construction. Call-free selection and missing-deliverable diagnostics
  retain their existing behavior.
- **Grade downloader direct-entry import** — make
  `scripts/download_inference_from_hf.py` bootstrap the batch-runner root and
  lightweight `core.inference_manifest` package when executed as a file.
  Approved canary run 29423860683 passed renderer preflight and Azure OIDC but
  stopped before HF download or any model call because direct execution could
  not resolve `core`; the grade commit step now also requires the grading step
  itself to have completed successfully.
- **GitHub-hosted grading renderer verified** — model-free rerun 29393149367
  passed on `main` commit `f97cc170` after PR #74 fixed the direct script import
  boundary. Evidence recorded `ok=true`, exact Liberation Sans resolution,
  LibreOffice 24.2.7.2, PyMuPDF 1.28.0, and successful XLSX/PPTX PNG renders.
  No HF, Azure, batch, or model call was present in the workflow.
- **Renderer preflight direct-entry import** — make
  `scripts/preflight_grading_renderer.py` add its own batch-runner root and load
  only the lightweight `core.tools` package surface when executed as a file.
  GitHub-hosted run 29392707519 had installed LibreOffice and renderer Python
  dependencies successfully but failed before rendering because direct script
  execution could not resolve `core`; the fix also avoids pulling unrelated
  dataset/pyarrow imports into the four-package renderer environment.
- **Sandbox generated-code preflight and targeted repair** — local and Docker
  backends now execute untouched `solution.py` through a trusted launcher that
  compiles with the actual target Python before `runpy` starts untrusted code.
  A bounded first-record stderr protocol preserves compile provenance through
  `chdir`, `os._exit`, SIGKILL, and binary output without a writable sidecar.
  Invalid syntax never reaches the generated body and consumes the existing
  repair budget with syntax-specific guidance. Shared execution categories
  route schema, API compatibility, binary decode, memory, timeout, and backend
  failures to distinct prompt-authored strategies; chained tracebacks prefer
  the final exception. Best-attempt and manifest backend selection now preserve
  actual execution evidence instead of an earlier compile-only failure. Shipped
  through PR #71 (`aa6c35c9`); the backend-only merge triggered no workflow, so
  an owner-approved bounded runtime canary remains pending.
- **Grading Track 2 merge and deploy** — squash-merged the reviewed hardening through PR #69 (`6ad789a7`) and verified successful `Aggregate Tests & Deploy` run 29357775581. The merge did not dispatch any paid grading, batch, or cost-sweep workflow; live Ubuntu renderer and limited Azure vision canaries remain explicit follow-up gates.
- **Dashboard diagnostic scope consistency** — register exp027 as a diagnostic
  report hidden from every default cross-run surface, including leaderboard,
  trends, error narratives, header scope, and future grade cards. `?debug=1`
  restores the aligned experiment/report set, direct detail URLs remain
  available, existing valid subsets such as exp012 stay visible, and global
  benchmark KPI copy remains fixed at 220 tasks. Shipped through PR #67
  (`92efc105`) and verified on the deployed site: the default leaderboard/error
  views exclude exp027 (22 experiments), while `?debug=1` restores it (23
  experiments) and direct detail navigation remains available.
- **Inference config and subset integrity** — preserve `model.reasoning_effort`
  from experiment YAML through prepared tasks, add validated ordered
  `data.filter.task_ids`, and carry canonical task scope through Steps 4 and 5.
  Explicit subset runs now retain exactly their selected rows (including failed
  tasks), reject duplicate/missing/unexpected result IDs, and cannot create
  placeholders for unselected benchmark tasks. `execution.sandbox` also
  survives config round-trips.
- **Sandbox provenance privacy** — persist only bounded hashes, counts, token
  usage, latency, stable error categories, skill-match evidence, preprocessor
  status, and CI identifiers. Raw model/process/preprocessor text, exception
  messages, generated filenames, arbitrary attempt fields, and heavy QA reports
  are excluded from checkpoints and self-reports.
- **Grading Track 2 source and execution hardening** — canonicalize every inference task and deliverable path under the exact `deliverable_files/<task_id>/` tree, require an exact regular-file manifest match, and reject absolute/parent/other-task paths, duplicates, symlinks, and ancestor-symlink escapes before grader construction. Workflow string inputs now enter shell steps only through validated, quoted environment variables; resume chunks are limited to 0–10 and require the pinned inference revision. Main and vision judge envelopes reject missing, nonnumeric, nonfinite, inconsistent, or giant-integer score fields as usage-preserving score-excluded errors. Partial saves are atomic and reloaded/schema-checked; `rc=7` requires new durable progress, an exact staged grade diff, a successful strict rebase with unchanged grade SHA-256, current-schema validation, and a pushed commit before relay. The inference full SHA and full grader source hash remain fixed across chunks, including the actual fallback tool prompt bytes.
- **Grading Track 2 harness-owned render + vision** — route Overall Style and visual criteria through a trusted pre-main-judge render/perception pass for PDF/XLSX/XLSM/PPTX/images, while DOC/DOCX-only Overall Style uses formatting inspection and mixed split targets preserve child routing. The main model cannot request render bytes or invoke vision directly; invalid vision envelopes, renderer errors, unsupported scopes, per-item file caps, and task-wide vision budget failures become score-excluded `judge_error` results before a normal verdict. Strict relative-path/SHA-256 renderer, coverage, and vision provenance is retained for parent and child audit records without base64 or absolute paths. The checked-in 220-task policy inventory requires 466 supported vision calls with a task maximum of 68, under the configured hard cap of 72. Rubrics now resolve to an immutable full Hugging Face commit and load only from a staged, atomically promoted per-SHA parquet snapshot whose manifest verifies repository identity, exact paths, SHA-256 hashes, and sizes. Active v2 outputs include config identity, full rubric SHA, and prompt version; cache hits require a schema-valid exact task set, while resume requires a schema-valid unique subset and matching experiment/rubric/prompt/config/renderer identity. New runs reject duplicate inference IDs and invalid `--tasks` selections before grader construction. The Ubuntu 24.04 grade workflow conditionally installs and preflights LibreOffice/fonts before Azure login, fails if the exact output artifact is missing, and the analyzer prices mixed child perception usage by its actual modality. HF inference inputs now resolve once to an immutable full dataset SHA, stamp canonical repository/revision metadata, and atomically replace revision-local deliverables. Active v2 filenames include the full inference SHA plus a 16-character grader-source route, while payload/cache/resume verify the full SHA-256 over the grading implementation surface. Chunk relays propagate the resolved inference SHA, and grade commits use strict rebase with pre/post grade-blob SHA-256 and current-tree schema validation before retrigger eligibility.
- **`batch-runner/scripts/download_inference_from_hf.py`** — pass `HF_TOKEN` explicitly to `hf_hub_download()` (×2) and `snapshot_download()` via a new `_hf_token()` helper. The grade pipeline's "Download inference results from HF" step injects `HF_TOKEN` env, but `huggingface_hub` auto-pickup did not fire, so requests went out **anonymous** (CI log: `unauthenticated requests to HF Hub`). Under the sequential grade relay this tripped HTTP **429 Too Many Requests** on the inference parquet, breaking a chunk mid-run (e.g. 5.4 220 re-grade chunk-2 resume). Authenticated requests have a much higher rate limit → relay no longer 429s on repeated chunk downloads. No behavior change for single runs.

### Added
- **Prompt-complexity Field Note** — add a sixth Korean RealWorks Field Note
  comparing completion rate and Self-QA across the exp003 baseline, exp004
  Elicit, and exp005 headless-Elicit subprocess runs. The article defines
  Elicit as the GDPVal study's five-step verification prompt rather than a
  separate model or service, and identifies headless-Elicit as the same design
  with STEP 2 changed from display inspection to Pillow checks. It separates
  surviving-result self-assessment from whole-run coverage and avoids treating
  the comparison as a prompt-only A/B because runner settings also changed. A
  dedicated responsive hero and dual Recharts comparison visualize
  95.9/90.9/90.5% completion against 6.18/5.87/6.16 Self-QA, while the
  prompt-strategy question, first timeline event, and exp003-exp005 detail pages
  link to the new note. Shipped through PR #84 (`c9cb607`) and successful Pages
  run
  [29437433192](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29437433192);
  the production route was verified at desktop and mobile sizes, including
  dark mode and reduced motion.
- **RealWorks Field Notes** — add lazy-loaded `/notes` and `/notes/:slug`
  routes with nine question-led experiment groups, a nine-event chronology,
  and five evidence-linked Korean columns spanning CI/runtime constraints,
  silent-corruption measurement changes, multimodal perception, task-level
  output review, and the subprocess-to-sandbox decision. The dashboard and
  experiment detail pages now link into the notes, while articles link back to
  available experiment details and source evidence. Legacy `/journal` links
  redirect to the canonical `/notes` paths. The independent-project label,
  Korean reading fonts, responsive editorial rhythm, accessible evidence
  numbering, and explicit Self-QA boundaries distinguish these notes from the
  official GDPVal paper and pending external grades. Each published note opens
  with a story-specific responsive hero (animated inline SVG on desktop,
  large-label summary on mobile) and an evidence-caveated Recharts comparison.
  The same hero slot supports GitHub Pages static MP4/WebM assets with native
  controls, `muted`/`loop`/`playsInline`, optional captions, BASE_URL-safe paths,
  and reduced-motion-aware autoplay. Shipped on `main` as `8ac9c20` through
  successful Pages run
  [29425800514](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29425800514).
- **Model-free grading renderer preflight** — add a manual, `main`-only Ubuntu
  24.04 workflow with read-only repository permission, commit-pinned actions,
  no credentials or model calls, exact LibreOffice/font checks, strict JSON
  success validation, and seven-day evidence artifacts. A shared
  `requirements-renderer.txt` keeps the dedicated workflow and full grading
  environment on the same openpyxl, python-pptx, Pillow, and PyMuPDF lower
  bounds.
- **Opt-in job performance metrics** — experiments may enable
  `execution.metrics.enabled` to record bounded per-task wall, model, tool,
  verification, dependency, Self-QA, and orchestration times plus execution,
  sandbox, tool-call, Self-QA-call, and resumed job-run counts. Resume rounds
  preserve cumulative task lifetime, while `time_to_valid_artifact_ms` requires
  a saved file and successful sandbox verification. Step 6 adds coverage,
  average/P50/P95 job time, successful/failed averages, time-to-valid-file,
  phase totals, and call totals only when measured data exists. The experiment
  detail page conditionally exposes the aggregate panel, sortable Job Time
  column, and per-task metrics; legacy configs, manifests, result JSON, and UI
  remain unchanged when metrics are omitted. Activation requires the literal
  boolean `true`; unrecognized fields are discarded. Durations and counters
  use finite schema bounds with overflow-safe resume merging and strict JSON
  serialization. Time-to-valid requires both a verified sandbox status and at
  least one non-manifest artifact, so text-only and manifest-only tasks cannot
  inflate the metric. Wall-timeout checkpoints retain pending task objects, and
  relay completion replaces them through the same metric-merging path so prior
  task lifetime is not lost. Step 3 serializes once with `allow_nan=False`
  before opening either result destination, preventing split or non-standard
  JSON output. Giant JSON integers are rejected before float conversion, so
  progress merging and report aggregation cannot fail with numeric overflow.
  Shipped through PR #76 (`3258b5c3`) and verified by successful automatic
  `Aggregate Tests & Deploy` run 29423221608; the merge automatically
  dispatched no paid workflow. A separate owner-dispatched grading run
  29423860683 later failed at HF download before model grading or paid inference.
- **`exp027_GPT54_default_subprocess_bridge50`** — checked-in 50-task,
  9-sector diagnostic subprocess comparator for the historical exp026
  Sandbox/Skills runner bundle. Includes pinned 42 non-success-union tasks, six
  media controls, two general controls, source revisions, selection provenance,
  and analysis guardrails against causal or population-level overclaiming. The
  implementation landed through PR #64 (`4306fa55`). Actions run #93 completed
  without relay in 2h47m54s: 23 success, 14 QA-failed, and 13 error tasks, with
  a 5.08 average Self-QA. HF upload completed; result PR #66 was merged as
  `2a33c998` after the scope guard and Pages deployment `29342879619` published
  the report. The raw generated index contains exp027, while the default UI
  keeps official benchmark scope and KPI copy at 220 tasks.
- **Pinned exp026/exp027 paired analysis** — add a standard-library analyzer,
  immutable HF revisions and content hashes, deterministic 10,000-resample
  bootstrap settings, unit tests, and a checked-in diagnostic report. The same
  50 tasks show exp026 30/14/6 versus exp027 23/14/13
  success/QA-failed/error, while paired Self-QA is effectively unchanged.
  Outcome-selected statistics are explicitly non-confirmatory.
- **Repository completion records** — `.github/copilot-instructions.md` now
  requires every repository-changing task to refresh
  `tasks/LATEST_TASK_RESULT/README.md` and the `[Unreleased]` changelog before
  completion is reported.

### Changed
- **`.github/agents/azure-infra-engineer.md`** — rebuilt for Opus 4.8 Copilot (`model: Claude Opus 4.8 (copilot)`, `tools: vscode, execute, read, edit, search, web, todo`). Reframed from a generic Azure/PowerShell advisor into an **end-to-end coding-agent infra provisioner** covering the full **Microsoft Fabric → networking/identity → Azure AI Foundry** estate as ordered layers (foundation, network/identity, Fabric capacity+OneLake+lakehouse, Foundry hub/project+model deployments+connections, operate/verify). Adds OIDC-only auth rule (no client secrets, mirrors grading pipeline), Bicep-first IaC conventions, runtime-proof verification (declaration ≠ wired), least-privilege RBAC, what-if-before-deploy, cost/destructive ops gated to owner, CHANGELOG discipline, and inter-agent handoffs (deployment-engineer / extreme-reasoner / first-reviewer / git-committer).

### Added (grading-v2 PR3 — perception wiring + instrumentation, 0531)
- **`core/grader.py::_build_tool_judge`** now reads `judge.perception.visual` / `judge.perception.audio` from the config and instantiates `VisionPerception` / `AudioPerception` (sharing the Grader's Azure client), then injects them into `ToolCallingJudge`. Previously these blocks were validated by step8 but never wired, so visual/audio criteria were silently graded by the text judge. `grade_task` now calls `_tool_judge.reset_perception()` at each task boundary so per-task call caps reset.
- **`core.grader.ItemGrade`** gains 3 runtime-instrumentation fields (`routing_modality`, `perception_called`, `tools_used`) that land in `data/grades/*.json` per item — proves at runtime which modality an item routed to and whether a perception sub-judge actually fired. Schema-additive only.
- **`core.tool_calling_judge.ToolCallingResult`** gains `tools_used: list[str]` (ordered dispatched function names) and `perception_called: bool` (any `vision_judge`/`audio_judge` dispatch). Stamped on every return path including `judge_error` / JSON-parse-fail branches.
- **`tests/test_perception_wiring.py`** — 5 tests, all PASS — prove the wiring + instrumentation at runtime (not by config inspection): subjudges instantiated, vision-dispatch flips `perception_called` and adds `vision_judge` to `tools_used`, text item leaves both untouched, and `reset_perception()` propagates.
- **Phase-0/1 analysis tooling** (read-only):
  - `scripts/phase0_critical_modality.py` + `tasks/0531_sunday/phase0_critical_modality.md` — decomposes v2-mini's 3 critical regressions vs v1-mini by modality (all 3 are `formatting`, not perception-addressable).
  - `scripts/phase0b_flip_decomp.py` + `tasks/0531_sunday/phase0b_flip_decomp.md` — decomposes mini-vs-standard leniency flips (38 total: 32 text, 3 visual, 3 formatting). Pure-text leniency dominant → perception cannot recover the headline regression.
  - `scripts/phase1_gold_candidates.py` + `tasks/0531_sunday/gold_candidates.md` — enumerates 19 rubric items (12 visual + 1 audio + 6 formatting) for owner hand-grading; GDPVal carries no per-item expected verdict, so thesis Phase 4 is blocked on owner gold.
  - `scripts/phase2_perception_probe.py` — synthetic-deliverable live firing probe (currently blocked on local Azure auth: SP secret expired + resource key-auth disabled).
- **Reports (`tasks/0531_sunday/`):** `phase1_gold.md`, `phase2_wiring.md`, `phase3_smoke.md`, `phase4_thesis_verdict.md`, `PERCEPTION_THESIS_REPORT.md`. Phase 4 verdict is **BLOCKED** pending owner gold + Azure auth fix; v2 flip justification is on hold.

### Notes
- `feat/wire-perception` branch is local-only. Per constitution rule 13, no push of decision artifacts or default-flips to `main` without owner go.
- Dead config recorded, **not modified**: `grades_per_task: 3` (unwired), `context_management.auto_compact` array-shape (disabled).

### Added (grading-v2 PR2 — tool-calling grader rebuild)
- **`core/tools/read_deliverable.py`** — 6-op read-only file inspection tool (`inspect_structure`, `read_content`, `inspect_formatting`, `render_to_image`, `probe_audio`, `probe_video`). Trusted base-dir path resolution (rejects `..` traversal + absolute escape + symlink-out). Uniform `{ok, data}` / `{ok=False, error, error_type}` envelope. 200k char content cap + 5MB image cap with Pillow downsample. Wheel-only deps: `PyMuPDF` for PDF render, `PyAV` for audio/video probe — keeps `grade-run.yml` apt-get-free. `READ_DELIVERABLE_TOOL_SCHEMA` ready to drop into Responses API `tools=[...]`. Commit `69d2d89`.
- **`prompts/grader_judge_v2.md`** (prompt_version `v2`) — tool-aware judge prompt. Drops the v1 `{{extracted_content_or_summary_truncated_4000}}` inline dump entirely. Mandates evidence be a direct quote from a `read_deliverable` tool response (fabricated quotes → verdict=fail). Inline catalog of all 6 tool ops + routing hint placeholders + `tool_calls_made` in required output schema. `prompts/grader_judge_v1_archive.md` is a verbatim copy of v1 for re-run reproducibility. Commit `419b612`.
- **`core/grader_routing.py`** — pure-function perception-modality classifier. Priority `visual > audio > formatting > text`; whole-word case-insensitive keyword match. `RoutingDecision.to_prompt_hint()` renders the `{{routing_modality}}` / `{{routing_preferred_op}}` placeholders consumed by `grader_judge_v2.md`. Commit `ab161f9`.
- **`core/perception/vision.py` + `core/perception/audio.py`** — vision (gpt-5.4) + audio (gpt-audio-1.5) sub-judges. Injected `client`, per-task caps (5 / 3), graceful `judge_error` on cap_exceeded / bad_image / endpoint_missing / FileNotFoundError / upstream exception. Vision: `(path,page)` image cache, base64 PNG header pre-validation. Audio: 30s head trim via PyAV (re-encodes to WAV in memory), `AZURE_AUDIO_ENDPOINT` env fallback. Commit `163bfdc`.
- **`core/tool_calling_judge.py`** — `ToolCallingJudge` standalone class. Responses API function-calling loop (≤10 iterations, ≤8 tool calls per item, both caps configurable). Dispatches `read_deliverable`, `vision_judge`, `audio_judge` function_calls; echoes both `function_call` and `function_call_output` into the next input batch (Azure Responses contract). Returns `ToolCallingResult` (same shape as legacy `Grader._judge`). Commit `653ef1d`.
- **`core.grader.Grader._tool_judge` dispatch** — `__init__` detects `judge.tools.read_deliverable` presence and instantiates a `ToolCallingJudge` sharing the same Azure client. `_judge` early-delegates when active. Legacy text-extract path is untouched; v1 configs run unchanged. Commit `653ef1d`.
- **`grading_configs/default_v2.yaml`** (schema_version `2.0`) — single-tier gpt-5.4 medium judge + `judge.tools.read_deliverable` (activates the v2 dispatch) + `judge.perception.{visual,audio}` modality models + sign-aware critical rule `|max_score| >= 4` + `grades_per_task: 3`. Commit `f14c22a`.
- **`step8_grade.py::validate_grading_config`** accepts schema_version `1.0` and `2.0`. v2 optional blocks validated: `judge.tools.read_deliverable.ops` is a non-empty subset of the 6 allowed ops; `judge.perception.{visual,audio}` require `model`; `judge.critical.rule` enum-restricted; `prompt.tool_template` must exist when set. Commit `f14c22a`.
- **`grading_configs/_archive_v1/`** — v1 sweep/tier configs (`validation_hybrid.yaml`, `validation_pro_only.yaml`, `tiered_critical_pro_mini.yaml`, `_sweep_template.yaml`, `recommended_gpt5_4_mini_2026-05-24.yaml`) archived for cache-key reproducibility + A/B compare against v2. `grading_configs/README.md` documents active vs archived + v1↔v2 feature matrix. Commit `2aa6688`.

#### Tests (PR2 net delta: +85 tests, 0 failures)
- `tests/test_read_deliverable.py` (25 cases): schema/path-safety/per-op happy + scope filters + truncation + render PNG header + cap + probe_audio round-trip
- `tests/test_grader_judge_v2_prompt.py` (8 cases): version tag, all 6 ops named, no v1 placeholder leak, routing hint placeholders, tool_calls_made schema, v1 archive integrity
- `tests/test_perception_routing.py` (19 cases): 12-criterion matrix + priority test + case-insensitive + word-boundary + `to_prompt_hint()` + `inventory()`
- `tests/test_perception_vision.py` + `tests/test_perception_audio.py` (16 cases): happy / cap / cache / corrupt / upstream exception / endpoint missing / reset
- `tests/test_tool_calling_judge.py` (11 cases): no-tool happy path / one tool round / cap short-circuit / max_iterations break / visual routing advertises vision_judge tool / text routing omits perception / vision dispatch end-to-end / upstream exception / unparseable final text / missing evidence / unknown function
- `tests/test_grader_tool_dispatch.py` (2 cases): v2 config triggers `_tool_judge` and `_judge` delegates / v1 config keeps `_tool_judge` None
- `tests/test_grading_config.py` (+7 cases): v2 schema accepted; default_v2.yaml validates; bad ops list / unknown ops / perception missing model / critical rule enum / tool_template path existence

#### Acceptance status (SPEC §7)
| gate | status |
|---|---|
| 7.1 gold-ceiling, 7.2 formatting gap collapse, 7.4 judge_error<2%, 7.5 grades_per_task×3 + CI | **deferred to PR3** — require live `grade-run.yml` jobs |
| 7.3 xlsx vs bare-CSV distinguishable in evidence | structurally guaranteed by `inspect_formatting`; confirmed in unit tests; cross-experiment proof pending PR3 task 301 |
| 7.6 PR1 sign-aware headline numbers republished | ✅ landed in PR1 (`PR1_REPORT.md`) |

#### What did NOT change in PR2 (deferred)
- `grade-run.yml` default `grading_config` is still `default_gpt5pro.yaml`. Flip to `default_v2.yaml` gated on PR3 task 302 cost-validation; flipping pre-validation risks an accidental $50+ accidental run on next trigger.
- Task 207 acceptance grep (`tier_pro|tier_standard|tier_mini|deliverable_extract_max_chars` → 0 matches) is **PARTIAL**. v1 sweep/tier configs are archived but `core/grader.py` legacy text-extract path, `core/grader_batch.py`, and `default_gpt5pro.yaml` remain on disk because they back the still-default v1 path. Full strip happens in a single cleanup PR after PR3 PASS.

Full PR2 details: [tasks/rebuilding_grading_task/PR2_REPORT.md](tasks/rebuilding_grading_task/PR2_REPORT.md).

### Added (grading-v2 PR1 — score-math sign-bug fix, headline numbers now trustworthy)
- **`ItemGrade.model_did_right`** — sign-aware right-outcome flag computed in `core.grader.Grader._aggregate`. For positive `max_score` items right = `verdict == "pass"`; for negative penalty items right = `verdict != "pass"` (i.e. the bad thing did NOT happen). `judge_error` is conservatively right=False. Resolves the systemic bug where every `verdict == "pass"` filter mixed semantically opposite signals for positive and negative rubric items.
- **`MAGNITUDE_THRESHOLD = 4` + `_is_critical_item()`** in `core/grader.py` and `summary.wow.critical_item_pass_rate` recomputed in `step8_grade._compute_summary` to use sign-aware `model_did_right`. Critical set grows from 397 (legacy `score >= 3` rule, positive only) to 483 items (now correctly including 86 negative-magnitude penalty items the legacy rule discarded). Documents rationale for `required` field being dead (null across all observed GDPVal rubrics).
- **`TaskRubric.max_score` = positive-only sum** + **`TaskGrade.pct_raw`** un-clamped diagnostic field. Fixes 4 exp003 tasks where v1's arithmetic positive+negative sum produced `total_max <= 0`, collapsing pct into mathematically undefined values that the `[0,100]` clamp silently masked (e.g. `6074bba3` v1 reported 65.76% on `total_max=-330`; v2sm reports 0.0% with `pct_raw=-434.00`).
- **`scripts/backfill_sign_aware.py`** + **4 new `*__v2sm.json` files on main** (`data/grades/exp003_*__v2sm.json` × 2, `data/grades/exp998_smoke_*__v2sm.json` × 2). v1 files preserved untouched (back-fill policy (c) from `tasks/rebuilding_grading_task/000-OVERVIEW.md`).
- **`schema_version` enum bumped to `["1.0", "1.1"]`** in `batch-runner/schemas/grade.schema.json`. v1.1 = v1.0 superset (`model_did_right`, `pct_raw` optional). `scripts/aggregate-grades.mjs` routes both versions through `processV1GradesFile`.
- **15 new tests** across `batch-runner/tests/test_grader.py` (sign × verdict normalization, magnitude threshold, sign-aware `critical_fail`, positive-only denominator, `pct_raw` diagnostics) and `scripts/__tests__/test_backfill_sign_aware.py` (6 backfill scenarios). Full regression: **478 batch-runner pytest + 29 scripts pytest + node mjs** all green.

#### Headline diff (exp003 219/220 graded)
| metric | hybrid v1 | hybrid v2sm | mini v1 | mini v2sm |
|---|--:|--:|--:|--:|
| critical_item_pass_rate | 0.421 | 0.466 | 0.518 | 0.596 |
| avg_score_pct | 49.25 | 48.18 | 51.47 | 50.97 |

The wider hybrid-vs-mini critical gap on v2sm (−0.130 vs v1 −0.097) reflects inclusion of 94 previously-excluded negative-magnitude penalty items. STRATIFY_v2 bucket decomposition (formatting 60.3% / penalty 21.8% / content 17.9% of hybrid-stricter pairs) remains the authoritative driver-of-the-gap read. Full PR1 details: [tasks/rebuilding_grading_task/PR1_REPORT.md](tasks/rebuilding_grading_task/PR1_REPORT.md).

PR2 (tool-calling grader rewrite) and PR3 (validation gates) tracked in `tasks/rebuilding_grading_task/` and will land in subsequent sessions.

### Added (autonomous validation + full follow-up chain)
- **`scripts/compare_grades.py`** — pair-wise critical-item comparison over the intersection of `task_id`s between two grade JSONs. Emits markdown report + decision JSON. Autonomous decision rule: `hybrid_critical_pass / mini_critical_pass >= 0.7` → PROCEED, otherwise → ABORT. Used both for fast 12-task C′ pre-validation and for the full 220-task post-run head-to-head.
- **`scripts/analyze_grade_run.py`** — extracts wall-clock, judge latency p50/p95, total tokens, price-table-based cost estimate (`PRICING_USD_PER_M_TOKENS`), top-5 slowest tasks, and optional Δ vs baseline grade. Auto-invoked by `grade-run.yml` on rc=0 chunks; produces `<grade>.analysis.md` alongside the grade JSON.
- **`.github/workflows/validate-hybrid-and-decide.yml`** — single-job C′ validation: grades the same first-N tasks with mini default, runs `compare_grades.py`, commits comparison + decision, and on PROCEED auto-dispatches the hybrid full run. `pair_limit` default 12, `timeout-minutes: 150` (sized for exp003's ~3-4 min/task on mini default).
- **`grade-run.yml` auto follow-up steps (rc=0 only):**
  - hybrid full done → auto-dispatch mini default full run for the same experiment (skipped if mini grade ≥200 tasks already exists)
  - mini default full done + hybrid full present → run `compare_grades.py` over the full 220-task pair, commit `DECISION_FULL.json` + `COMPARE_FULL.md` to `data/grades/_validation/`
- **`scripts/__tests__/` (11 new tests)** — `test_compare_grades.py` (6 tests: PROCEED/ABORT at threshold boundary, task_id intersection, mini critical_pass=0 guard) and `test_analyze_grade_run.py` (5 tests: single vs routing cost mode, wall-clock from `graded_at` span, top5 ordering, markdown sections).

### Added (chunked auto-resume for long grade runs)
- **`step8_grade.py` --resume flag + 4h time guard.** Reads existing partial grade JSON at the templated output path, harvests already-completed `task_id`s, skips them, and continues. Time budget is `GRADER_TIME_BUDGET_SEC` env (default 14400s/4h); when tripped before all tasks are graded, step8 partial-saves and exits 7. Distinct from existing `--force` semantics (mutually exclusive).
- **`grade-run.yml` self-retriggering chunk pattern.** Job `timeout-minutes: 320` (5h20m, safely under GH Actions' 6h hard limit), `permissions.actions: write`, new `resume`/`resume_chunk` inputs. When step8 returns 7, commits the partial then dispatches the next chunk via `gh workflow run` (uses `GITHUB_TOKEN`, no PAT). Safety cap: `resume_chunk > 10` aborts. Enables 220-task hybrid/pro_only runs that exceed the single-job 6h limit.
- **`PYTHONUNBUFFERED=1`** on the grading step so per-task progress streams live in the GH Actions log instead of buffering for minutes.

### Fixed
- **`gpt-5.4-mini` rejects `reasoning_effort='minimal'` (Azure HTTP 400).** Valid values are `none/low/medium/high/xhigh`. `core/grader.py` tier_mini default and `validation_hybrid.yaml` both updated to `'low'`; `_sweep_template.yaml` doc comments updated to document the constraint. Root cause of a 6.6h wasted hybrid run that produced only 20/220 graded tasks before this was found.
- **`pct` clamped to `[0, 100]` in `core/grader.py`** to honor `grade.schema.json` `{minimum: 0, maximum: 100}`. Two exp003 tasks (#44 pct=108.9%, #45 pct=229.3%) were violating the schema, causing partial-save validation to silently fail at task #50. `step8_grade.py` partial-save block now also wrapped in try/except with full traceback so future schema violations surface immediately.
- **`pytest -q` collection unbroken from `batch-runner/`.** Two legacy test files (`test_main.py`, `test_main_hf_integration.py`) imported the removed pre-pipeline monolith `main.py` at module top and crashed collection; wrapped with `pytest.importorskip('main')` so they cleanly skip. `test_data_loader.py::test_load_raises_error_when_no_snapshot_and_no_auto_download` asserted the old `download()` substring in the error message; loosened to accept either `step0_bootstrap.sh` (current) or `download()`. Result: 465 passed / 2 skipped / 0 failed (was 37 deselected + 2 errors).

### Tested (decision: keep single-mini default; reject tiered hypothesis)
- **Tiered grading hypothesis rejected on exp003 head-to-head.** Re-tested the ORIGINAL `TASK_GRADE_COST_OPTIMIZATION.md` proposal (pro for weight≥4 critical items, mini for rest) against the sweep-selected single-mini default on 40 tasks of `exp003_GPT52Chat_baseline_runner_exec`. Tiered LOST on all axes:
  - critical_item_pass_rate: single-mini **0.55** vs tiered **0.43** (tiered worse, opposite of intent)
  - avg_score_pct: 47.26 vs 45.61 (tiered −1.65pp)
  - judge_total_latency: 6,002s vs **14,845s** (tiered 2.5× slower)
  - cost (40 tasks): ~$1.7 vs **~$25** (tiered ~15× more expensive)
  - Hypothesis: gpt-5.4-pro with reasoning_effort=high becomes MORE strict on borderline criteria, depressing critical_pass instead of raising it. Confirms the Sweep Phase A pattern (A1_pro_high < A2_std_extract_1500 by ~5pp).
- `tiered_critical_pro_mini.yaml` remains in `batch-runner/grading_configs/` for future re-experimentation (e.g., weight≥5 critical, or pro at medium effort), but is NOT promoted to default.
- Full analysis: `tasks/0525_monday/COMPARISON_REPORT.md`.

### Known issues
- **`step8_grade.py` exits 1 after task #50** when grading exp003 — discovered during the tiered validation. Both runs (single-mini and tiered) failed at the exact same task #50 / `d025a41c` boundary, no Python traceback, ~2.5h elapsed in mini run / ~4h in tiered. Likely memory accumulation or task #51 entry crash. Cost optimization is unaffected; bug tracked in `tasks/0525_monday/TASK_STEP8_TASK50_FAIL.md`. **Root cause found and fixed above** (pct schema violation + silent partial-save failure).

### Changed
- **`batch-runner/grading_configs/default_gpt5pro.yaml` now uses `gpt-5.4-mini` at medium reasoning effort (was `gpt-5.4-pro` high).** Promoted from `recommended_gpt5_4_mini_2026-05-24.yaml` after Stage 1 validation re-graded `exp998_smoke_baseline_sample` against the prior baseline grade. Validation results (head-to-head, same inference, same rubric, same prompt, same precheck):
  - avg_score_pct: 77.83 → **78.03** (+0.20pp, well within ±2pp acceptance)
  - critical_item_pass_rate: 1.00 → 1.00 (preserved)
  - judge_error_rate: **5.9% → 0.0%**
  - precheck_pass_rate: 0.80 → 0.80 (unchanged)
  - judge_total_latency_sec: 8530 → **265** (32× faster)
  - input/output tokens: −23% / −60%
  - Projected full-run cost (220 tasks, linear extrapolation): **$493 → $18** (−96.3%). Projected fixed-budget efficiency improved by approximately **27×**.
- Filename `default_gpt5pro.yaml` preserved so existing `grade-run.yml` triggers, dashboard aggregators, and downstream tooling continue to work. `config_name` field updated to `default_gpt5pro`.
- Prior config preserved as `batch-runner/grading_configs/recommended_gpt5_4_mini_2026-05-24.yaml` (identical content; kept for documentation / future renames).
- Rollback path: `git revert <this commit>` reverts to the gpt-5.4-pro high default. Recommended config remains available for explicit `--grading_config recommended_gpt5_4_mini_2026-05-24.yaml` invocation.

### Added
- **Grading cost optimization sweep — winner `A4_model_mini` (-96.3% cost).** Autonomous sweep (27 variants across Phase A axis-sweeps / Phase B tier-combinations / Phase C stability + 1 gpt-4o diversity check) selected `gpt-5.4-mini` at medium reasoning effort, no batching, deliverable extract 1500 chars as the new default grading judge. Full-run cost projection drops from $493 (baseline `default_gpt5pro.yaml`) to **$18.45** (-96.3%) at avg_score_pct **+0.08pp**, critical_item_pass_rate **1.00** preserved, judge_error_rate **0.0%** (baseline 5.9%). Smoke wall-clock 299s vs 142min (28× faster), with approximately **27×** better fixed-budget efficiency. Total sweep spend $42.36 / $80 cap across 4 GH Actions runs (12.6 hours wall-clock). Drop-in config: `tasks/0523_saturday/cost_opt_results/2026-05-24-grade-cost-sweep/winner_config.yaml`. Full analysis: `tasks/0523_saturday/cost_opt_results/2026-05-24-grade-cost-sweep/FINAL_REPORT.md`. Key insights: (a) gpt-5.4-pro is unusable below medium reasoning (verdict JSON parse fails 100%); (b) tier combinations consistently underperform single-mini (verdict fragmentation); (c) batching loses 3.6pp score per 3× call reduction; (d) gpt-4o diversity validator unfunctional with Responses-API reasoning shape. Caveats: winner has only 1 measurement (Phase C only stresses Phase B variants), pricing is approximate. Promotion path: manual full-run validation → replace default_gpt5pro.yaml.
- **`.github/workflows/grade-cost-sweep.yml` — autonomous sweep dispatcher CI.** New workflow runs `scripts/grading_cost_sweep.py` end-to-end on GH Actions. `source_ref` input separates OIDC subject (must be a federated ref, typically `main`) from the code branch to checkout (the feat branch with sweep dispatcher). 350-min timeout. Federated OIDC via `azure/login@v2` (no API key, no secret rotation needed). Commits `RESULTS.md` / `progress.json` back to source_ref; uploads grade JSON + run.log artifacts for 30 days. Workflow itself lives on `main`; sweep code lives on the feat branch.
- **`fix(grader)`: API key fallback for sweep environments without working OIDC** (opt-in via `GRADER_ALLOW_API_KEY_FALLBACK=1` env). Production CI keeps OIDC-only behavior by default. Documented in module docstring.
- **`fix(sweep)`: subprocess env injection from `batch-runner/.env`**. step8_grade and core/* read only from `os.environ` and do not call `load_dotenv`; the dispatcher now hydrates the subprocess env so local execution does not silently lose `AZURE_OPENAI_ENDPOINT`.
- **`fix(sweep)`: variant outputs isolated to per-variant `runs/<name>/` dir**. Previously variant configs left `output.directory` at the template default `../data/grades`, causing every variant to overwrite production grade JSONs (caught via `git diff` before any data was lost). `render_temp_config()` now sets `output.directory` to an absolute per-variant path; `run_step8_grade()` uses `shutil.copy2` instead of `shutil.move` so the templated original survives for audit.
- **TASK_GRADE_COST_SWEEP Track 1 — prompt-level batching + tiered judge routing.** New `batch-runner/core/grader_batch.py` (`BatchJudge`) evaluates N rubric items per Azure OpenAI Responses API call with per-item evidence enforcement and one-level `chunk_size // 2` fallback on parse failure. New sibling prompt `batch-runner/prompts/grader_judge_batch.md` (legacy `grader_judge.md` preserved byte-identical). `batch-runner/core/grader.py` accepts two new OPTIONAL config keys: `grader.batch_size` (int, default 1) and `judge_routing` (tier_pro / tier_standard / tier_mini); when either is set, judge items are routed by tier and dispatched in batches, and `judge_call_count` switches from per-item to per-API-call semantics. New reference config `batch-runner/grading_configs/_sweep_template.yaml` shows the v1.0 schema plus the new optional knobs. 14 mocked unit tests (`tests/test_grader_batch.py` + `tests/test_grader_routing.py`).
- **TASK_GRADE_COST_SWEEP Track 2 — autonomous sweep dispatcher.** `scripts/grading_cost_sweep.py` (executable, OIDC-only) drives the cost-optimization sweep end-to-end: loads `tasks/0523_saturday/grading_cost_sweep_plan.yaml` (15 Phase A + 5 Phase B variants + Phase C stability spec + gpt-4o diversity validator), validates each variant against a hard-coded `MODEL_TPM` table at 70% cap, renders per-variant configs on top of `_sweep_template.yaml`, subprocesses `step8_grade.py` per variant, extracts metrics, runs Pareto selection under acceptance hard filter (critical=1.0, err≤5%, score±2pp), and emits `RESULTS.md` + `summary.json` + `winner_config.yaml`. Cost cap $80 enforced; `progress.json` supports `--resume`. 12 mocked tests at `scripts/__tests__/test_grading_cost_sweep.py`. Operator guide at `tasks/0523_saturday/cost_opt_results/README.md`.
- Grade source linkage (Phase 2). `step8_grade.py` now embeds two new fields on every emitted grade JSON: `source_inference_experiment_id` (defaults to `experiment_yaml_name`; overridable via new `--source-experiment-id` CLI flag) and `source_inference_run_dir` (repo-relative path, null when unknown). `scripts/aggregate-grades.mjs` resolver looks up `taskQaByExperiment` by the source pointer first, falling back to `experiment_id` (Phase 1 behavior preserved). Schema `batch-runner/schemas/grade.schema.json` adds both fields as optional/nullable — legacy v1 grades without them still validate. Backfilled `data/grades/exp998_smoke_baseline_sample__*.json` to point at `exp999_smoke_baseline_sample`, restoring 3/3 calibration matching (MAE=10.65, unmatched=0). Spec: `tasks/0523_saturday/TASK_GRADE_SOURCE_LINKAGE_BACKEND.md`.
- `tasks/0523_saturday/TASK_GRADE_COST_OPTIMIZATION.md` — judge 채점 비용/시간 압축 계획 (smoke 142m → 30m, 풀런 ~$540 → ≤$120). reasoning_effort, precheck 확장, item batching, tiered judge routing(mini=extended precheck / standard=gpt-5.5 / pro=critical only), concurrency 상향의 단계별 실행안.
- `tasks/0523_saturday/TASK_GRADE_COST_SWEEP.md` — 자율 dispatch sweep 사양. `scripts/grading_cost_sweep.py`가 16+5+6+1=28개 변종(Phase A 단축/Phase B 조합/Phase C 안정성/diversity)을 Global Standard API + prompt-level batching으로 실행하여 정확도 제약(critical=1.0, err≤5%, score±2pp) 내 Pareto 우승자를 자동 도출하고 `RESULTS.md` + `winner_config.yaml`을 생성. 사용 모델은 endpoint 가용 5.4 family(pro/std/mini/nano) + gpt-4o(diversity only). cost_cap_usd $80 강제.
- Grade detail page: Self-QA vs Rubric calibration view (Phase 1). Three new columns (Self-QA, Δ Gap, Calibration), three new filters (Calibrated/Overconfident/Underconfident), Calibration MAE pill in Health Strip, and footer match-rate note. Build-time join via `aggregate-reports.mjs` enriching reports-index with compact `task_qa` map; `aggregate-grades.mjs` performs strict per-experiment lookup (no global task_id map). Dummy grades and unmatched experiments are explicitly handled. Spec: `tasks/0523_saturday/TASK_GRADE_DETAIL_SELF_QA_CALIBRATION.md`. Follow-up: `TASK_GRADE_SOURCE_LINKAGE_BACKEND.md`.

## [2026-05-23] — Phase A wow follow-up: dashboard cleanup + grading hotfix

### Added

- **Dashboard cleanup spec package + WOW chrome cleanup (PR #1 of
  `tasks/dashboard_cleanup`).** Threaded `inference_model` vs
  `judge_model` as separate fields end-to-end so the GradeDetail header
  no longer misleads users into thinking the judge model solved the
  tasks. Aggregator (`scripts/aggregate-grades.mjs`) gained:
  - `grade_status: 'graded_v1' | 'legacy_dummy' | 'no_grade'` derived
    from `schema_version` / `_meta.is_dummy`.
  - `experiment_id` lifted to a top-level field (no more brittle
    `startsWith` matching across the dashboard).
  - `inference_model` / `judge_model` split — the legacy `model` falsy
    fallback to `judge.model` was removed.
  - Unit tests under `scripts/__tests__/aggregate-grades.test.mjs`
    locking the no-fallback contract + status derivation (3 fixtures).
  Frontend additions: `src/types/grade.ts` (already shipped in PR #46;
  unchanged here), `src/lib/format.ts` (`fmtPct` / `fmtLatency`),
  `src/components/wow/HealthStrip.tsx` (single-Card inline pill strip
  showing `judge_error_rate`, `judge_pass_rate`, `precheck_pass_rate`,
  `total_judge_calls`, `total_judge_latency_sec`; err pill turns red
  + `AlertTriangle` when `judge_error_rate > 5%`). Copy pass 2 across
  `src/data/tooltipTexts.ts` + `src/components/ScopeBadge.tsx`
  separates "self-QA" (model judging itself during inference) from
  "LLM-judge grade" (rubric-based, run via `grade-run.yml`) on every
  surface — KPI tiles, leaderboard tooltips, About modal bullets,
  empty-state CTAs.

- **`tasks/dashboard_cleanup/` 8-file spec package.** README + 000
  overview + 001 (model display) + 002 (banner/status) + 003 (health)
  + 004 (disagreement guard) + 005 (copy pass 2) + 006 (rollout) +
  copy_audit.md. Amended in-place after extreme-reasoner +
  ui-designer deep review (precedence rules, opacity → dashed border,
  amber → zinc, hard-gate aggregator tests, mandatory grep audit).

### Changed

- **`legacy_dummy` cards on the Grading tab now use `border-dashed`
  with a neutral `DEMO` badge** (BookOpen icon, zinc palette) instead
  of `opacity-90` (WCAG AA contrast fix) and instead of the previous
  amber `⏳ Awaiting LLM-Judge Grade` strip (which misleadingly fired
  even when v1.0 grades were present). The `⏳ Awaiting` strip is
  removed from per-card chrome.

- **Grading Analysis tab top banner is now status-aware.** When only
  legacy demo grades exist, the banner uses a neutral zinc tone with
  a `BookOpen` icon and points to `grade-run.yml`. When legacy +
  graded-v1 are mixed, the banner switches to a soft sky tone with an
  `Info` icon clarifying that some experiments still show demo data
  alongside fresh LLM-judge results. Amber is no longer used in this
  surface; it remains reserved for `self_assessed_pre_grading` (a
  true "awaiting" state on the experiment side).

- **`ScopeBadge` union extended.** `'graded_v1'` (fuchsia, Sparkles
  icon — "✨ LLM-Judge Graded (v1.0)") and `'legacy_demo'` (zinc,
  BookOpen — "📚 Legacy Demo") added; pre-existing `'graded'` and
  `'self_assessed_pre_grading'` variants preserved. `ExperimentDetail`
  now derives scope via `resolveScope(meta, grades)`: grade-derived
  status wins when an exact `experiment_id` match exists, otherwise
  meta is used as fallback.

- **`Grader Disagreement` UI is guarded.** Both the cross-experiment
  chart in `GradingAnalysisView` and the per-card `Disagreement`
  StatMini in `GradesSummary` now render only when
  `inconsistent_grades > 0` (i.e., Phase B multi-judge runs). The
  underlying counter logic is retained for Phase B.

- **CHANGELOG entries are now grouped under dated release headings
  (`## [YYYY-MM-DD]`)** instead of a single open-ended `## [Unreleased]`
  block. The previous entries have been bundled into a single
  retroactive `## [2026-05-20]` heading since they were committed in
  PR #41–#46 across May 17–23 with the same broad theme (Phase A core
  + WOW dashboard). New PRs will open a fresh dated heading at the
  top.

### Fixed

- **`step8_grade.py` no longer leaves `inference_model` as the empty
  string.** A new `_resolve_inference_model(inf_results, exp_config)`
  helper resolves with the priority `inf_results['model']` →
  `experiment_yaml.condition_a.model.deployment` → `''`, never falling
  back to `config['judge']['model']`. The dashboard's previous fall-
  through `model = inference_model || judge.model` made the GradeDetail
  page show the judge model (`gpt-5.4-pro`) as if it had solved the
  tasks; the resolver guarantees `inference_model` reflects the actual
  inference deployment. Whitespace inputs are stripped on both sources.
  Three new tests in `tests/test_step8_grade.py` lock the contract,
  including a defensive `inference_model != judge.model` assertion
  independent of the literal judge string. (PR #47)

- **`grader.per_item_max_output_tokens` raised 800 → 1600 in
  `grading_configs/default_gpt5pro.yaml`.** The first smoke run on
  2026-05-21 produced `judge_error_rate = 0.2381` (20 of 84 calls
  failed); root cause hypothesis is that `gpt-5.4-pro` with
  `reasoning_effort=high` consumes most of the output-token budget on
  reasoning tokens, leaving the previous 800 ceiling insufficient to
  emit the verdict JSON. 1600 ≈ 2× safety margin without meaningful
  cost impact at the 220-task scale. (PR #47)

## [2026-05-20] — Phase A grading pipeline + WOW dashboard

### Added

- **Phase A grading infrastructure.** Added rubric-based grading pipeline
  components: `batch-runner/core/rubric_loader.py`,
  `batch-runner/core/grader.py`, `batch-runner/prompts/grader_judge.md`,
  `batch-runner/step8_grade.py`,
  `batch-runner/grading_configs/default_gpt5pro.yaml`,
  `batch-runner/schemas/grade.schema.json`,
  `.github/workflows/grade-run.yml`,
  `batch-runner/scripts/download_inference_from_hf.py`, and
  `.github/agents/grading-engineer.md`. (PR #45)

## [2026-05-20] — Phase A grading pipeline + WOW dashboard

### Added

- **Phase A grading infrastructure.** Added rubric-based grading pipeline
  components: `batch-runner/core/rubric_loader.py`,
  `batch-runner/core/grader.py`, `batch-runner/prompts/grader_judge.md`,
  `batch-runner/step8_grade.py`,
  `batch-runner/grading_configs/default_gpt5pro.yaml`,
  `batch-runner/schemas/grade.schema.json`,
  `.github/workflows/grade-run.yml`,
  `batch-runner/scripts/download_inference_from_hf.py`, and
  `.github/agents/grading-engineer.md`. (PR #45)

- **Phase A wow — narrative + dashboard integration.** Threaded schema
  v1.0 grade JSON into `NarrativeAnalyzer` + `step6_report`
  (`_load_grade_for_experiment`, `_build_grading_guard_clause`,
  `_build_grading_results_section`, N3 disclosure paragraph instruction).
  Added W1–W6 WOW components under `src/components/wow/`
  (RubricCoverageCard, CriticalItemCard, StructureVsReasoning,
  SectorHeatmap, ScoreDensityHistogram, RubricSeverityCurve) backed by
  `src/types/grade.ts` and rendered conditionally via `<WowSection>` in
  `src/pages/GradeDetail.tsx`. (PR #46)

### Removed

- **`core/evals_submitter.py` dead code.** Removed deprecated placeholder
  hosted-grading submitter and its test file
  (`tests/test_evals_submitter.py`) in favor of the new self-grading flow.
  (PR #45)

## [2026-05-17] — Resume Round watchdog + silent corruption fixes

### Fixed

- **step2_run_inference: wall-timeout watchdog now also fires inside Resume
  Rounds (silent relay-bypass fix).** Previously the `wall_deadline` check
  existed only in the Round 0 (initial run) and Relay-run continuation
  loops in `batch-runner/step2_run_inference.py`. When Round 0 completed
  within `wall_timeout`, control fell through to the Resume Round loop
  (around L1370) which had no deadline check. Heavy resume retries
  (Self-QA, audio preprocessor, video composition) then silently exceeded
  the GitHub Actions step hard timeout — on SIGKILL the run could not
  save a checkpoint or mark `pending` tasks, so the workflow saw
  `pending=0, needs_relay=false` and skipped the HF checkpoint upload +
  self-retrigger, forcing a full re-run from scratch
  (observed in run 26018603400 / exp025: Round 0 finished ~250min,
  Resume Round 1 SIGKILLed at ~330min with no relay). The Resume Round
  loop now mirrors the existing watchdog: unfinished retriable tasks are
  marked `pending(error=wall_timeout)`, `_save_progress()` is called, and
  the process exits with `EXIT_CHECKPOINT(42)` so the workflow uploads
  the checkpoint and self-retriggers. Backward compatible — `wall_timeout
  = 0` (no timeout) short-circuits the guard as before.
  (PR #41)

- **batch-run workflow: Step 2a/2b `timeout-minutes` widened 330 → 350.**
  After `wall_timeout` (default 290min) fires, the run still needs time to
  save the progress checkpoint, upload it to HuggingFace, and dispatch
  the relay re-trigger. The previous 330min hard step timeout left only
  ~40min for this handoff, which proved insufficient in practice. The new
  350min ceiling gives a 60min margin while still staying well under the
  6h job-level cap. (PR #41)

- **subprocess_runner: `_AVAILABLE_FILES` hint now actually executed.**
  In `core/subprocess_runner.py::_execute_safely`, the `files_header`
  (`_AVAILABLE_FILES = [...]`) prepended to the generated `code` string was
  never persisted back to the executed script path, so the subprocess ran the
  raw user code without the guarded hint. The header-prepended `code` is now
  written to `code_path` end-to-end. The earlier redundant pre-prepend write
  was removed; the file is written exactly once after the header is applied.

- **llm_client (Anthropic): tolerant content parsing + `finish_reason`
  surfaced.** `core/llm_client.py::AnthropicClient.chat_complete` previously
  assumed `response.content[0].text`, which crashed when the first block was
  a `thinking` or `tool_use` block. The parser now walks all content blocks
  and concatenates only `type == "text"` segments. `response.stop_reason` is
  mapped to an OpenAI-compatible `finish_reason` (`max_tokens` → `length`;
  `end_turn` / `stop_sequence` / `tool_use` passed through) and exposed on
  `_Choice` / `NormalizedResponse`, so the existing
  `finish_reason == "length"` truncation guard in
  `step2_run_inference.py:436` actually fires for Anthropic.

- **step2_run_inference: `qa_failed` is now set on genuine Self-QA
  failures.** Previously, when Self-QA scored `< min_score` and retries were
  exhausted, the best result was returned with `status == "success"`, which
  meant the `RETRIABLE_STATUSES` retry plumbing (resume rounds), the
  `_print_status` `qa_failed` branch, and the summary counters at
  `step2_run_inference.py:1419` / `1448` were all dead code paths.
  `_run_task_with_qa` now sets `best_result["status"] = "qa_failed"` on
  genuine quality failures, re-enabling auto-retry / resume.
  The `undetermined` branch is intentionally left as `success` — it only
  marks QA parse / API failures, not quality failures, and is not a retry
  target.

### Changed

- **`qa_failed` semantics (BREAKING for comparability).** As a consequence
  of the fix above, the dashboard / aggregated metric `qa_failed_count` is
  no longer comparable across the boundary: pre-fix runs report
  `qa_failed_count == 0` (the flag was never set even when QA genuinely
  failed); post-fix runs report the true count. Treat pre/post
  `qa_failed_count` as different metrics.

- **`compact` mode parquet may now contain fewer rows.** When
  `result_collector` is configured in compact mode it filters
  `status == "success"`. Because genuine QA failures now flip to
  `qa_failed`, those rows are excluded from the compact parquet that were
  previously silently retained as `success`. The non-compact / per-task
  JSON output is unaffected and remains the source of truth for QA failure
  counts.

- **`resume_rounds_used` will be non-zero on QA-enabled runs.** The same
  fix re-enables the resume / retry loop for `qa_failed` tasks via
  `RETRIABLE_STATUSES`, so QA-enabled runs that previously reported
  `resume_rounds_used == 0` may now legitimately consume one or more
  resume rounds. Worst-case per-task cost is capped by the existing
  `qa_max_retries` × `resume_rounds` × infra-retry budget.

### Notes

- **Cost guardrail (re-validated post-fix).** Production experiment YAMLs
  (`exp001`–`exp024`) keep worst-case per-task LLM call multiplier at ≤6×
  (infra retries × QA retries × resume rounds, within previous SLOs).
  Smoke YAMLs (`exp997` / `exp998` / `exp999`) sit higher at 12×–16× in the
  worst case, but their `sample_size` of 2–3 tasks bounds total wall-clock
  / spend impact to negligible levels. No YAML changes are required.

