# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are grouped under dated headings (`## [YYYY-MM-DD]`). The
`## [Unreleased]` block at the top stays empty between releases — new
entries land under a fresh dated heading the day they merge to `main`.

## [Unreleased]

### Added
- **An experiment can now ask for the Codex run place.** The runtime, the auth
  command, the per-task workspace, deliverable collection and the cost adapter
  all existed and were exercised; what did not exist was any way for an
  experiment file to reach them. `grep -rln codex_foundry experiments/` was
  empty, and it could not have been otherwise. Five separate things stood in
  the way, each found by trying to build the path rather than by reading it:
  - `ExperimentConfig.validate` checked `execution.mode` against a list typed
    out a second time, without `codex_foundry` — while the `Literal`
    annotation beside it had the mode and a whole validation branch was
    written against it. A file naming the mode collected "execution.mode must
    be one of [...]" next to errors from the branch that knows it exists. The
    check now reads the annotation, so the two cannot disagree again.
  - The endpoint setting took a literal address only, and this deployment's
    address is a secret in a public repository. `execution.codex` now takes
    `endpoint_from_route: true`, which resolves through
    `AzureAIRouteSettings.from_env` — the derivation every other Azure caller
    here uses and the one the answered turn used. Exactly one of that key and
    a literal `endpoint` may be set; neither, or both, is refused rather than
    resolved by precedence. An earlier draft took an `endpoint_env` key naming
    a variable; that was a new variable and a new secret for an address the
    run already knows how to find, and it would have let a file point a run at
    a resource other than the confirmed one.
  - `step1_prepare_tasks.py` did not carry `execution.codex` into the prepared
    file at all. It now carries the settings and never the address: the
    prepared file travels as a run artifact, so `endpoint_from_route` (a
    boolean) survives and a literal `endpoint` is dropped.
  - `step2_run_inference.py` built a provider client for every mode, and
    `core.executor` refuses `codex_foundry` outright if it is handed one. It
    now builds no client for this mode, resolves the provider settings in the
    process rather than from any file, and passes the run's cost ledger
    through to the runner — which was accepted by `TaskExecutor` and never
    passed by anything, so the leg would have recorded no cost at all.
  - Only `prompt.system` reaches the agent, as its developer instructions;
    `CodexAgentRunner.build_task_text` writes the rest. A `prefix`, `body` or
    `suffix` is now refused for this mode instead of silently dropped. exp026
    declared `reasoning_effort: low`, step 1 dropped it, and exp027's header
    exists to correct the record — one such correction is enough.
- **`experiments/exp033_codex_foundry_fixed5.yaml`** — the first experiment
  file in this repository that names `execution.mode: codex_foundry`. Five
  tasks: the same five as exp030/exp031/exp032, chosen by the rule in
  `core/execution_envelope_tasks.py`, so a number from it is readable against
  the 3, 4 and 0 those three run places finished on 2026-09-01. It is *not* a
  fourth column of that comparison and the file says so: that comparison holds
  one first request across its places, this run place is not in the module
  that enforces that, and it builds its own message. Limits are fixed before
  the run — 5 tasks x at most 3 attempts, one turn each, 1800s per turn, one
  task at a time, Self-QA off. Retries are taken at the batch runner's layer
  where they are counted; the Codex-side counters stay at 0, because with the
  runtime's shipped defaults one turn against a server answering HTTP 500
  sends thirty requests and none of them appear as attempts anywhere a reader
  would look.
- **Self-QA is refused for `codex_foundry`** rather than cautioned against.
  The reviewer would be an Azure client built in step 2 — a second sign-in
  beside the one Codex performs through its provider auth command, on a run
  whose premise is that the model reaches the deployment exactly one
  documented way.
- **A batch dispatch can now open the Codex gate.**
  `step2_run_inference._require_runnable_execution_mode` refuses
  `codex_foundry` unless `CODEX_FOUNDRY_CONNECTION_CONFIRMED` is set, and
  `batch-run.yml` had no way to set it, so the mode ran only through its own
  tests. It now takes a `codex_foundry_confirmed` dispatch input that defaults
  to false. The gate itself does not change: what the box says is not that the
  connection works — run `34465567349` settled that — but the separate thing,
  that a person looked at this experiment and decided this batch may spend.
  - The decision is made in `inspect-mode`, the job that holds no credentials
    and whose checkout does not persist any, beside the agentic check and for
    the same reason: it decides whether a credentialed job starts at all.
  - A `codex_foundry` dispatch without the box **fails** rather than skipping,
    in a `reject-unconfirmed-codex` job shaped like `reject-agentic` — no
    checkout, nothing with credentials, `exit 1`. A skipped job reads as
    "nothing to do"; this has to read as "refused". The credentialed job is
    guarded by its own `if` as well, because the two are siblings and a red
    sibling does not stop a job that has already started spending.
  - `CODEX_FOUNDRY_CONNECTION_CONFIRMED` is derived from the box itself and
    never from the block. `codex_blocked` is false in two unrelated
    situations — the box was ticked, and the credential-free parser did not
    read this as a Codex experiment — and only the first means somebody
    decided. A step inside the job covers the second: if `ExperimentConfig`
    sees a `codex_foundry` run that the Ruby missed, it stops there, ahead of
    every credential the job holds.
  - The input is forwarded on every relay leg. A leg is the same run
    continuing, and an input that is not forwarded is a run that spends on leg
    0 and is refused on leg 1. That is now checked for *every* dispatch input
    rather than for this one, because the next input added has the same bug.
  - Anything that is not exactly `true` or `false` aborts. The safe reading of
    a value nobody understands is not "spend".

  The box is inert for every other mode, ticked or not, rather than an error:
  the relay forwards every input on every leg, and a run must not start
  failing halfway through for carrying a flag it never used.

### Changed
- **The Codex readiness record narrows its gate blocker rather than dropping
  it.** It said the gate was closed and `batch-run.yml` did not set it; the
  second half is no longer true. What the reason is actually about — that
  somebody decides this batch may spend — is unchanged, so the blocker stays
  and says what it now is: shut by default, opened at dispatch, failing in a
  job that holds no credentials when it is not. "There is no way to open it"
  is retired in
  `test_the_codex_blockers_are_about_the_task_not_about_the_connection` so it
  cannot come back as a reason after being built. The count stays at two.
- **The Codex readiness record drops the two blockers this change cleared.**
  It listed three; two of them named code — no experiment file could ask for
  the mode, and the configuration could not reach the runner if one did — and
  both now exist and are checked. That list has now been rewritten three times
  for the same reason each time: a reason kept past the point where it was
  true, making a solved problem read as unsolvable. Two remain, and neither is
  about reaching the model or about wiring:
  - the batch gate is closed and only a person may open it.
    `_require_runnable_execution_mode` refuses the mode without
    `CODEX_FOUNDRY_CONNECTION_CONFIRMED`, and `batch-run.yml` does not set it.
    "A request was answered" and "this batch may spend" are different claims.
  - no task has produced a deliverable through this place against the real
    deployment. Tool execution, reference-file staging, deliverable collection
    and the cost receipt are still exercised only against the stand-in
    app-server.

  The count moves from three to two rather than gaining an invented third.
  `test_the_codex_blockers_are_about_the_task_not_about_the_connection` keeps
  both cleared claims in its retired list, so neither can return as a reason
  after being built.
- **The Codex readiness record now says what run `34461522053` actually
  settled, and what it did not.** The three blockers standing against
  `ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY` were all written as things that
  had *not been observed*, with the explicit note that no amount of reading
  would clear any of them — only a request that is answered would. That request
  has now been answered, and it cleared all three at once:

  - the auth command ran **inside Codex's own isolated environment and the
    task's own directory** and produced a token (`auth_command.ok: true`,
    `exit_code: 0`, `azure_config_dir: /home/runner/.azure`);
  - the contract the deployment serves Codex on is no longer a guess —
    `endpoint_kind: direct-v1` on the undated `/openai/v1/` route,
    `wire_api: responses`, no query parameters;
  - the pinned runtime is compatible with this deployment in this region:
    pinned **and** installed `openai-codex 0.147.0`, deployment `gpt-5.4`,
    `turn_status: completed`.

  This is the second time this list has had to be rewritten, and both rewrites
  were the same mistake caught late: a reason kept past the point where it was
  true. The first time it was documentation objections the product had already
  answered; this time it was connection questions a real turn answered. Both
  make a solved problem read as unsolvable, which is the more expensive
  direction to be wrong in — it argues against work that is already done.

  **The status does not move.** It stays `structure_check_only`. What replaces
  the three cleared blockers is what a *task* still needs and does not have,
  and each one names the code that would have to change:

  - **no experiment asks for this place.** No file under
    `batch-runner/experiments` names `execution.mode: codex_foundry`, and none
    can be written as `core.experiment_config` validates it today: that check
    builds `CodexProviderSettings` from a **literal** `execution.codex.endpoint`
    with no environment expansion anywhere in the module, and this deployment's
    address is a secret that cannot be committed to a public repository.
  - **the configuration cannot reach the runner.** `TaskExecutor` takes the
    Codex settings through `codex_options`, and nothing outside `core.executor`
    and `tests/test_codex_runtime_end_to_end.py` ever passes it;
    `step2_run_inference._create_executor_with_client_cleanup` builds every
    executor with `llm_client=client`, which `core.executor` refuses for this
    mode. A batch run would fail at construction rather than reach a turn.
  - **nothing has been produced through it.** The answered turn carried no
    tools and wrote no file (`tool_execution_observed: false`; the prompt
    forbade tools by design), so tool execution, reference-file staging,
    deliverable collection and the cost receipt are still exercised only
    against the stand-in app-server. A model that answers is not an agent that
    works.

  `test_the_codex_blockers_are_about_the_task_not_about_the_connection` pins
  the shape rather than the wording: no blocker may claim the connection is
  unproven, and each must name checkable code. The static-key test stops
  requiring Codex to cite `FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV` — the rule
  still binds it, but for Codex that conflict was *resolved* by
  `core.codex_azure_token` rather than merely stated, and a test that demands a
  settled conflict be listed as an obstacle is a test that keeps the record
  wrong on purpose.
- **`test_the_setting_is_off_unless_an_experiment_writes_it` reads the parsed
  key instead of searching the file's text.** The text search counted prose:
  exp033 explains in a comment why it is *not* part of the run-place
  comparison that uses the shared first request, and was reported as running
  it without saying so. The guarantee is unchanged in both directions — a file
  with the setting on has the key, and a file that writes the key must write
  it `true`.
- **`test_the_silent_ones_are_still_silent` counts nineteen, not eighteen.**
  The number is a census of experiment files whose self-review budget carries
  no comment, pinned so that adding a comment to all of them is a visible
  decision. exp033 is a new file rather than a comment removed from an old
  one — its self-review is off and its budget is zero, so there is nothing for
  a comment to describe — and moving the number in the change that adds the
  file is the decision the pin asks to see.

### Fixed
- **The connection diagnostic asked the turn for a field the turn does not
  have, and reported the answer as missing.** Run `34461522053` connected: the
  stream carried `UserMessageThreadItem`, `ReasoningThreadItem` and
  `AgentMessageThreadItem`, and the provider billed 10,994 input / 28 output
  tokens for it. The record still said `final_response_present: false`, which
  reads as the model having stayed silent.

  It had not. `_final_text` looked for `final_response` and then `output_text`
  **on the `Turn`**. Both names are real, but they belong to `TurnResult`, the
  SDK's own dataclass in `_run.py`. The `Turn` in `generated/v2_all.py` — which
  is what a `TurnCompletedNotification` carries — has neither: it has `items`,
  and the answer is the `text` of an `AgentMessageThreadItem` among them.
  `getattr` on a Pydantic model with no such field returns the default without
  complaint, so the miss was silent and total: **every** completed turn this
  diagnostic ever observed was recorded as answerless.

  `_final_text` now reads the items, using the SDK's own selection rule —
  prefer the message marked `final_answer`, else the last one whose phase the
  provider left unset, and never `commentary`. It consults the turn payload
  first and the stream second, because `Turn.items_view` may say `notLoaded`,
  and an unloaded payload is not a claim that nothing was said;
  `observed.final_response_source` records which one answered.

  The rule is copied from the SDK's private
  `_final_assistant_response_from_items` rather than imported, and
  `test_our_reading_rule_matches_the_pinned_sdks_own` runs the two over the
  same eight item lists so an SDK bump that changes the rule fails a test
  instead of drifting. There was no test over this function at all before, which
  is how the bug survived; there are now eleven, built on real SDK objects,
  because a stand-in carrying a `final_response` attribute is exactly the
  fiction that hid it.

  **The real run path was never affected.** `TurnHandle.run()` is annotated
  `-> TurnResult` (`api.py:757`), so `core/codex_runner.py`'s
  `getattr(result, "final_response", None)` reads a field that exists. Only the
  diagnostic, which drives the stream itself, ever held the wire model.

  The record format is now `codex_foundry_connection/3`. This is a version bump
  rather than an additive change because `final_response_present: false` means
  something different on either side of it — a claim about us before, a claim
  about the model after — and the two must not be compared. The model's text is
  still not published: the record says whether an answer arrived and whether it
  matched, and `observe_stream` deliberately returns the agent messages out of
  band rather than folding them into the summary that lands in the artifact.

- **The Codex `401` was never about the deployment: the auth command could not
  produce a token where Codex runs it.** Three independent faults, each
  sufficient on its own, each producing the same silent symptom.

  Codex authenticates the provider by running a command and reading the token
  from its stdout. It starts that command with the **task's directory** as the
  working directory — `CodexAgentRunner.open_runtime` sets `CodexConfig.cwd` to
  the workspace and the pinned SDK passes it straight to `Popen` — and in the
  **isolated environment**, where `HOME` is rewritten to a throwaway directory.
  From there:

  1. `python -m core.codex_azure_token` cannot import `core`. It failed before
     the module's first line.
  2. `DefaultAzureCredential`'s working leg is the Azure CLI, which reads its
     sign-in from `$HOME/.azure`. With `HOME` rewritten there was none.
  3. On any failure the command prints nothing on stdout — deliberately, so
     Codex cannot mistake an error for a token. Codex therefore sent an **empty
     bearer**, and the gateway answered `401 Access denied due to invalid
     subscription key or wrong API endpoint`.

  That sentence names the endpoint and the key, both of which were correct
  throughout — run `34442249527` had already proved the identity may infer on
  this resource. Runs `34319880025` and `34347516170` are what reading it
  literally cost.

  The first fault alone accounts for those runs, without appealing to anything
  local: `PYTHONPATH` is neither inherited nor neutralised by
  `build_isolated_environment`, and the diagnostic workflow never sets it, so
  `-m core.codex_azure_token` from the task's directory raises
  `No module named 'core'` on any host. Whether the second also bites on a
  runner — where `azure/login` writes the sign-in that the rewritten `HOME`
  then hides — is a prediction, and the new free `auth_command` record is what
  settles it.

  The fixes, in the same order. `CodexProviderSettings.auth_entrypoint()` names
  the module by resolved file path instead of `-m`, and the module puts its own
  package root on `sys.path` when run that way, so it no longer depends on
  where it is started. `discover_azure_cli_config_dir()` reads the sign-in's
  location in the **parent** and `auth_command()` appends it as
  `--azure-config-dir`; the value travels in the command's own argv, so the
  Codex process's environment is unchanged and the model's tools see exactly
  the isolation they saw before — asserted by
  `test_the_isolation_still_hides_the_sign_in_from_codex_itself`. And
  `CodexAgentRunner.require_a_usable_auth_command()` runs the real command in
  the real isolated environment once per runner and refuses to start a runtime
  when no token comes back, raising `CodexAuthCommandFailed` with the
  command's own reason attached.

  Measured locally end to end: the auth command now exits `0` with a token
  **inside** the isolation, started from the task directory. The probe keeps no
  token and no token-derived value — only whether stdout carried one, and why
  not.

- **`diagnose_codex_foundry_connection.py` asks the sign-in before it spends.**
  New verdict `auth_command_produced_no_token`, and an `auth_command` block in
  every record. A sign-in that cannot mint now ends the run before a request
  exists, so this failure costs nothing instead of a paid `401`.

  The **free plan** answers it too. Minting an Entra token is a call to the
  identity platform, not to the deployment: no model runs and nothing is
  billed. So a run without `--send-request` now runs the real auth command in
  the real isolated environment and fills the same `auth_command` block — which
  turns "does the second fault bite on a runner?" from a paid dispatch into a
  free one. It reports rather than gates: a sign-in that cannot mint still
  leaves the plan green and exit `0`, because a red plan reads as "the
  diagnostic broke" and the finding here is the opposite. A host that cannot
  run the preflight at all leaves the field `null` — *not asked*, which is not
  the same as *asked, and no*. `reason` goes through the record's redactor like
  every other runtime message; `azure_config_dir` does not, because which home
  the sign-in was found in is the one thing the record is for.

- **Corrected the first `codex_foundry` readiness blocker.** Its old text said
  no token from the auth command had ever been accepted by a Foundry
  deployment; run `34442249527` had already disproved that. The replacement
  says what is actually unobserved — a turn from inside the isolation, on a
  runner. The gate stays closed; only the reason is now true.

### Added
- **The containment answers a seventh question, and it was found by planning
  the test rather than by reading the rules.** Stage C's attack list has always
  ended with one that is not like the others: the command must not be able to
  read a token, key or environment secret the orchestrator holds. Writing it out
  properly meant asking which rule it enforces — and the answer was none. At
  `0076295`, the commit this was written against, `credential`, `secret` and
  `token` appeared nowhere in `core/agentic_v2_substrate.py`,
  `security/agentic-v2-supply-chain-policy.json` or
  `sandbox/agentic_v2_capabilities.json`: zero matches in all three. The test
  would have passed against nothing at all.

  **A test with no rule behind it is the same fault as a rule with no code
  behind it, seen from the other side**, and this repository has spent a lot of
  effort on the first kind. So `credentials: "none-inherited"` is now the
  eleventh containment rule, in `REQUIRED_MICROVM_POLICY` and in the manifest
  that would travel with a built image, which the tests require to be equal
  rather than merely compatible. It is
  refused if it is weakened to `inherit-environment`, refused if it is softened
  to a bare `"none"`, refused if it is deleted, and the readiness report now
  carries it beside the other ten as *"cannot be established here"* — the same
  verdict, for the same reason, because nothing turns any of these rules into
  arguments for starting a machine yet.

  It does **not** appear in the signed supply-chain policy, and that is not an
  omission: that file mirrors four of the eleven rules — `runtime`, `network`,
  `read_only_rootfs`, `ephemeral_work_disk` — and always has. Seven rules,
  including the three numeric limits and `on_breach`, live in the policy and the
  manifest only. Worth knowing before someone reads the signed policy as the
  full statement of the containment; it is a signed subset of it.

  Every other rule here arrived because something was written down and nothing
  applied it. This one arrived the opposite way: nothing was written down, and a
  test was about to be aimed at it anyway.

- **Checking that rule against the jailer's own documentation moved a flag from
  optional to required.** The plan said the launcher could lean on the jailer,
  which "already clears inherited environment variables and file descriptors
  before exec". Firecracker's jailer documentation for **v1.13.1** — the version
  measured on the Azure host, not the development branch — says something
  narrower: it will *"cleanup all environment variables received from the parent
  process"*, but *"close all open file descriptors … **except input, output and
  error**"*. Those three survive, and get pointed at `/dev/null` only by the
  separate step that runs when the launcher asks to daemonize.

  So the new rule holds by default for the environment and only conditionally
  for the descriptors. `--daemonize` is now something stage C1's launcher has to
  pass rather than something it may, and C3's attack on this rule inspects the
  descriptors instead of trusting the sentence. A rule written down on the
  strength of a mechanism that turns out to work differently is the fault this
  stage exists to fix, one layer further down.

- **The same reading deleted a device from stage C's plan, because it does not
  exist.** The plan named four devices a launcher must pin at `null` or lose a
  rule it appears to enforce: `mmds-config`, `vsock`, `balloon`, and
  `memory-hotplug`. The reasoning behind the fourth is sound — memory added
  after boot is memory the bound never saw — and the device is not. Firecracker
  v1.13.1's own configuration fixture has no such key, and its API
  specification, 43 KB covering every route, contains no occurrence of *hotplug*
  at all. Balloon **is** the runtime-memory mechanism in this Firecracker; the
  table had it twice under two names.

  A test pinning `memory-hotplug: null` would have asserted something about a
  key Firecracker never emits, and passed for that reason. That is the third
  check in this stage that would have held against nothing — the credential
  attack, the jailer's three surviving descriptors, and this — and all three
  were found by reading the sources the plan cites rather than the plan.

  Added in its place, as a route rather than a device: `/snapshot/load` restores
  a machine whose configuration was decided elsewhere, so it can carry a NIC, a
  vsock or a different memory size that the launcher's own arguments would never
  show. It is not a setting to pin; it is a way in that bypasses the table, and
  stage C3 treats loading one as an escape rather than a configuration.

- **Three records still say six, and are left saying it.** `CHANGELOG.md`,
  `TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md` and the recorded Azure finding all
  describe a day on which the count was six, or a hashed report that contained
  nine policy rules. Only the last one gained a clause saying so, because it
  sits in `core/` next to a report a reader can run today and get ten from.
  Rewriting the other two would not fix a stale sentence; it would falsify a
  record of when the rule set changed, which is what those records are for.

- **The identity may infer on this resource — measured, not argued — and the
  question is now which property of a Codex request stops it.** Run
  `34442249527` sent `--valid-request` to the pinned deployment and got `200`,
  `response_status: completed`, model text back, 13 input and 5 output tokens.
  Same host fingerprint that answers the runtime's `401`; token minted by the
  runtime's own `auth_command`; same path, same scope, same deployment name.

  That retires five hypotheses at once — wrong resource, missing inference
  permission, wrong deployment name, bad token minting, wrong route — and it
  retires the case for asking anyone for a role: this identity demonstrably
  may infer here. Whatever refuses Codex is Codex-side. `price_usd` is `null`
  and `pricing` is `partial`, which means unpriced, not free.

- **`--closing-sweep`: the transmission sweep re-run against a baseline that
  works.** Nine servable requests, gated on its own `send_closing_sweep` input
  and the resource fingerprint, in
  `batch-runner/scripts/diagnose_codex_foundry_connection.py`. The first arm is
  the request run `34442249527` proved servable, unchanged; each of the other
  eight is that request plus exactly one thing a Codex turn adds, measured off
  the wire by `test_what_one_codex_turn_actually_sends.py` —
  `Accept: text/event-stream`; `originator` and the runtime `User-Agent`; the
  six session and turn headers; `stream: true`; `store: true`; a 19 KB
  `instructions`; ten tool definitions; and all of it together.

  Isolated rather than cumulative, because a cumulative sweep's first flip is
  attributable only to "this arm or an earlier one". One request per arm, no
  retry, the same 512-token ceiling and 90-second wall clock, concurrency 1,
  ceilings in the script so a dispatch cannot widen them.

  If the baseline is not served on the day, the other eight are not sent: they
  would be measured against nothing and they are not free. That run records
  `closing_sweep_inconclusive` rather than "everything closes the gate". A
  `400` on an arm is not counted as the gate closing — that is the route
  objecting to the request's shape, and reporting it as a permission fact is
  how somebody ends up asking for a role over a malformed field. Finding
  nothing is recorded as finding nothing, which would point at the transport
  or at a body property this sweep does not vary.

  Same limits as every probe here: `urllib` and not the runtime, so a property
  that closes the gate is the next place to look and not a proven cause; no
  tool ran and no file was written, so nothing here is a task solved; usage as
  reported with `price_usd: null` and `pricing: partial` — across nine
  requests, which is emphatically not free. Pinned by 31 tests in
  `batch-runner/tests/test_codex_closing_sweep.py`, every host in them a
  loopback socket on the test machine.

  **Fired, run `34448607605`, verdict `no_property_closes_a_served_request`.**
  The baseline was re-tested that day and served, so the premise held and the
  other eight were bought honestly. All nine arms answered `200`, including
  `everything` — 30,981 bytes, nine added headers, `stream: true`, a 19 KB
  `instructions` and ten tool definitions, materially larger and stranger than
  a Codex turn and served without complaint. `properties_that_closed_the_gate`
  is `[]`, 9 planned and 9 sent. Summed usage 5,942 in / 35 out over the seven
  arms that reported it; the two that set `stream: true` hold the SSE prelude
  rather than a parsed final status and report none. `price_usd: null`,
  `pricing: partial` — unpriced, not free.

  Finding nothing was the finding: it is what pointed away from the request
  body, and the thing this sweep does not vary turned out to be the sign-in.

- **The one request in this diagnostic that the route can actually serve.**
  `--valid-request` in `batch-runner/scripts/diagnose_codex_foundry_connection.py`,
  wired as a step gated on its own `send_valid_request` input *and* the resource
  fingerprint. It is paid, and it is the only probe here that can produce a
  completion.

  Everything before it deliberately sends something unservable — a listing, a
  body with no `model` in it, a bearer that was never valid — which is what
  makes those probes free and is also their ceiling. Run `34437632382` looked
  like it had finished that line of questioning: all six header arms of the
  sweep, up to and including every runtime header at once with `stream: true`,
  came back with the same `400`, and the record's
  `properties_that_closed_the_gate` was empty. That reading was wrong and is
  corrected below — a body naming no model dies in the deployment router, so
  none of those arms ever reached whatever refuses the runtime. What has never
  been sent to this resource, across every probe, is a body it could serve — so
  *may this identity infer here* has never been asked, and no record on disk
  answers it.

  One request. No retry, no fallback, `max_output_tokens: 512`, `stream: false`,
  `store: false`, a 90-second wall clock and a trivial public prompt carrying no
  benchmark content. The ceilings live in the script rather than in the
  workflow, so a dispatch cannot widen them.

  512 rather than the API's minimum of 16, and that difference matters more than
  the cost does. These deployments are reasoning models: they spend output
  tokens on reasoning before emitting any text, so a ceiling of 16 is consumed
  entirely by that and the answer comes back `200 incomplete` with nothing in
  it. This probe correctly refuses to call that a success — which would have
  meant spending the one request that was supposed to settle the question on an
  artefact of its own configuration. If it happens anyway the record now says
  so: the Responses status and `incomplete_details.reason` are written down
  alongside the HTTP status, and the note names the ceiling as the thing to
  change rather than leaving a bare "200 with no text" to read as a failure of
  the route.

  Its three outcomes point at three different repairs. `200` with model text:
  the resource, identity and route are fine, what refuses Codex is Codex-side,
  and a working request now exists to diff the runtime's against. `401`/`403`
  on a servable body: a permission fact, the first evidence here that would
  bear on a role, and unobtainable from any free probe. `400`/`404`: the shape
  or the deployment name, still not permission.

  Read strictly on purpose. A `200` carrying no model text is recorded as
  inconclusive rather than as a success, and the exit code is `0` only for a
  completion — a `401` here would be the most useful result this script has
  ever produced and it still exits `1`. Usage is written down as the response
  reported it with `price_usd: null` and `pricing: partial`: no rate for this
  route is registered in this repository, and `partial` means unpriced, not
  free. The record carries what a completion would still not establish — this
  is `urllib` and not the runtime, no tool ran and no file was written, and the
  220-task column is untouched either way. Pinned by 48 tests in
  `batch-runner/tests/test_codex_valid_request.py`.

### Fixed
- **A null result read as a finding when the instrument could not see.** The
  transmission sweep (run `34437632382`) reported no property closing the gate,
  and this changelog, the job summary and the task doc all took that to mean
  the runtime's headers are not what refuses it. They were reading an empty
  list produced by an experiment that could not have produced a full one: every
  arm's body named no model, so every arm died in the deployment router with
  `400 Missed model deployment` before reaching whatever refuses the runtime.
  Its `properties_that_closed_the_gate: []` means the instrument could not see,
  not that nothing closes the gate. The three places that said otherwise now
  say this instead, and `--closing-sweep` is the same experiment with a
  baseline that clears the gate.

- **The diagnostic could write a record that was neither checked nor kept.**
  The leak check's path list and the artifact's path list are written
  separately in the same workflow, and nothing compared them: a probe whose
  `--out` was added to one and not the other either published a record no
  check had looked at — on a public repository — or spent money and threw the
  evidence away, and the run stayed green either way. Two tests now hold the
  two lists equal to each other and require every `--out` any step writes to
  appear in them.

- **The diagnostic's redaction check no longer routes an unknown record shape
  into another shape's check.** Its branches were three free-record schema
  prefixes with the turn record as the `else`. That failed closed once, for
  real, on the sweep record — by `KeyError`, which is a crash that happens to
  be safe. The valid-request record would have hit the same branch, and there
  the accident is expensive: it is the paid record, so the run that crashes is
  the run that already spent the money, and a failed check skips `Keep the
  record` and destroys the evidence. Every schema is now matched by name, the
  paid record is *required* to admit `inference_requested: true` rather than
  merely permitted to, and an unrecognised schema is refused by name instead of
  being vouched for by a check written for something else.

### Added
- **A free sweep that asks which request property closes a gate the plain
  request already clears — and states, in the record, that clearing a gate is
  not permission to do the work.** `--transmission-sweep` in
  `batch-runner/scripts/diagnose_codex_foundry_connection.py`, wired as an
  ungated step in the connection-diagnostic workflow.

  Run `34361684546` established the check order this reads against: the same
  unservable body got `400 Missed model deployment` with a minted bearer and
  `401 invalid subscription key` with an obviously invalid one. The bearer
  clears the gate under `urllib`. The Codex runtime, sending *the same token*,
  gets the `401` — byte-for-byte the invalid-token text. Four transmission
  hypotheses were closed offline against a fake token and a local mock (header
  present, `Bearer` scheme, value uncorrupted 38→38, no second credential), so
  the difference is somewhere else in what the runtime adds.

  The sweep takes the request already known to clear the gate and adds one
  Codex-specific property per arm — `Accept: text/event-stream`, `originator`
  and user-agent, the six session/turn headers, `stream: true` — plus a
  combination arm, and looks for the `400` flipping to `401`. Arms are
  **isolated, not cumulative**: cumulative makes the first flip attributable
  to nothing narrower than "this group or an earlier one", and the extra
  request buys "this property is sufficient" instead.

  The replayed values are **measured, not guessed**. Extending the turn
  recorder to keep header *values* showed `originator: codex_python_sdk` — not
  the `codex_cli_rs` a guess would have used — and `Accept: text/event-stream`
  rather than `application/json`. A `needs_runtime` test binds both to the
  pinned binary, so a version bump that changed either reddens a test instead
  of quietly sweeping a string nobody sends.

  No arm names a model, and that is enforced with a `ValueError` raised before
  the token is minted rather than left to review. Every run re-tests its own
  premise twice — that the control is still stopped at the gate, and that the
  baseline still clears it — and reports `sweep_inconclusive` rather than
  naming five properties as causes on a host where none is doing anything.

  What the record refuses to claim, in every run: these arms are `urllib` and
  not the runtime, so a property that closes the gate here is **where to look
  next, not the proven cause**; the ~45 KB body is not tested; the transport
  layer is not varied; a named property is **not a reason to request a role**;
  and — the distinction a `400` most invites collapsing — this reads **the
  order the host checks a request in, not what the identity may do.** Clearing
  the gate with an unservable body shows authorization is checked before the
  body is read. It does not show a servable body would be served, because no
  arm here is one. Nothing about this moves 220 tasks to runnable.

  Refusals carry no usage record, so these requests are **unpriced rather than
  proven free**; they are not $0.

### Fixed
- **The redaction check crashed on the record it was meant to protect.** It
  branches on schema prefix, with the two free shapes matched by prefix and the
  paid turn shape as the `else` — deliberately, so that an unregistered record
  fails closed. The sweep record was unregistered, so it took the `else` and
  died on `record["observed"]`, which a free record does not have. In CI that
  fails the check, skips `Keep the record`, and loses the record *after* its
  seven requests are spent. The design worked exactly as its comment promised;
  registering `codex_foundry_transmission_sweep/` is the other half of it.
- **A measurement of what one Codex turn actually puts on the wire, replacing
  two claims that were true of narrower things than they were asserted about.**
  `batch-runner/tests/test_what_one_codex_turn_actually_sends.py` drives the
  pinned `0.147.0` runtime against a loopback server that answers `401` to
  everything — production's own failure — and records all seven HTTP verbs.

  The existing retry-pin harness implements `do_POST` and nothing else, so
  `BaseHTTPRequestHandler` answers any other verb with `501` without ever
  calling the recorder: a `GET` the runtime made would have been refused by the
  instrument and left no trace in the count that said one request was sent.
  "One request" and "one request of the only kind we looked for" are different
  measurements, and only the second had been made. The first now has an answer:
  **two POSTs to `/v1/responses`, no `GET`, no other verb**, and the token
  command runs twice — the re-mint that pinning does not remove.

  The turn body is **about 45.9 KB**, not the 135 characters of the prompt:
  roughly 21 KB of Codex system `instructions`, 18 KB of **ten `tools`
  definitions** sent with `tool_choice: auto`, and 5 KB of `input`. Nothing in
  `core/codex_runtime_config.py` removes them.

  A test that asserts an absence passes just as well by not looking, which is
  the failure being corrected one layer down, so
  `test_the_recorder_actually_sees_every_verb_it_claims_to` sends one request
  of each verb by hand and requires all seven back. Reverting the handler
  installation to POST-only reproduces the original blind spot exactly —
  `('GET', 501)` — with the other five tests still green.

  Also here, needing no runtime and no credential: both the Codex diagnostic
  and the working inference path derive their endpoint from
  `FOUNDRY_PROJECT_ENDPOINT` through `AzureAIRouteSettings.from_env`, and
  running both derivations against a stand-in account name shows they post to
  the same URL at the same token scope. That closes "the address is wrong" as a
  cause of the Codex 401 by measurement rather than by reading the source.

- **The four cheapest explanations for the Codex 401, closed with a fake
  token.** Run `34361684546` established that the minted bearer *clears* this
  host's auth gate (`400 Missed model deployment`) while a plainly invalid
  bearer is stopped at it (`401 Access denied due to invalid subscription
  key…`) — and that second message is byte for byte what the paid turn
  `34347516170` received. The token is therefore acceptable and the runtime is
  answered as though it were not, which puts the difference on the
  transmission side.

  Pushing a **fake** token through the pinned binary into a local mock server —
  no credential, nothing off loopback — shows the credential arrives intact on
  both requests: header present, `Bearer` scheme, value **exactly** what the
  auth command printed, and no second credential header alongside. Malformed
  header, truncated token, missing prefix and a competing `api-key` are all
  ruled out.

  The fault is not found; four places it would have been cheapest to find it
  are. What remains is fixed in a test so the next diagnostic aims at the right
  thing: seven runtime headers the working `openai.OpenAI` client does not
  send, `stream: true`, and a body two orders of magnitude larger. **No role
  grant is indicated by any of this and none is being requested** — the earlier
  `role_missing_and_an_owner_must_grant_it` verdict belongs to the
  project-scoped Code Interpreter arm and does not transfer to this account
  route.

- **A free two-armed probe that separates "the bearer was refused" from "the
  bearer got through and something later refused".**
  `diagnose_codex_foundry_connection.py --auth-discriminator` posts a body the
  Responses route cannot serve — no `model`, no `input` — to the same route the
  turn uses, twice: once with the bearer the Codex runtime mints and once with
  a fixed string that is plainly not a token.

  The second arm is the design, not a nicety. Run `34346945494` got `200` from
  `GET /models` and run `34347516170` got `401` from one turn, same host, same
  bearer, minutes apart, so the question is where in the request the refusal
  happens. A `400` from the minted bearer answers that **only if this host
  checks authorization before it validates the body**, and nothing measured in
  this repository establishes that ordering. A host that reads the body first
  answers `400` to everybody, including to a non-token — and that `400` would
  have been read as good news. The control arm makes the host demonstrate
  which check it runs first; it is a constant, never varied and never derived
  from anything real, so it is not credential guessing and cannot become it.

  Three verdicts, not two: `bearer_clears_the_auth_gate`,
  `bearer_refused_at_the_auth_gate`, and `check_order_not_established` for the
  host that cannot be read this way. Reordering the checks so the minted arm
  is read first — the version that always returns an answer — turns three
  tests red, including the end-to-end one asserting that a run which could not
  discriminate does not exit zero. A `200` to a body naming no model is
  refused a clean verdict too, and withdraws the free claim with it: the
  argument that nothing can be generated is that no deployment can be
  selected, and a `200` is the host disagreeing.

  The record states what it cannot settle: this is `urllib` on the route
  rather than the Codex runtime; a clear verdict narrows where to look and is
  **not a reason to grant a role**; and "no usage came back from a refusal" is
  an argument for the call being free, not a measurement of it. The workflow
  step is ungated and sends no prompt, so it runs on the dry dispatches — the
  ones that are all that is left, since the single authorised turn was used.

  The leak check now branches on schema across both free record shapes rather
  than one, with the turn shape as the `else`, so a future free record added
  without touching that list fails closed instead of skipping. Its path list
  and the artifact upload carry the new record.

### Fixed
- **Three cost and capability notes that understated one Codex turn by about
  340×.** The diagnostic's job summary said `tool execution observed: false —
  this prompt forbids tools, by design`; its header comment said the turn costs
  "one prompt of about 135 characters, no tools"; `TASK_NATIVE_CODEX_RUN_PATH.md`
  and a docstring in `test_codex_foundry_connection_probe.py` said the same.

  All four were true of *execution* and of the *plan*, and false of the
  request. The runtime attaches ten tool definitions and `tool_choice: auto` to
  every turn, and no prompt wording or config key removes them, so the billed
  input is dominated by the ~39 KB of `instructions` and `tools` rather than by
  the prompt. This is the same error those notes themselves warn about one
  paragraph earlier — before the retry pins landed, the plan said
  `retries_configured: 0` while the runtime used its own defaults and one turn
  against a 500 sent thirty requests. A property of the plan was again being
  asserted about the runtime.

  Each now separates the two and cites the measurement. The consequence is
  recorded rather than smoothed over: a body-matched A/B between the Codex path
  and the direct Python path is not available, because Codex sends 45.9 KB with
  ten tools whatever the prompt says. A contrast can control for resource,
  deployment, identity, route and token audience — not for body — and must say
  so.

- **The backend gate now starts a run for the tree it asserts about.**
  `backend-tests.yml` filtered on `batch-runner/**`, `scripts/**` and two
  workflow files by name. Resolving every repo-root-relative path literal in
  `batch-runner/tests/` against the tree found five directories that started no
  run at all: `.github/` (30 literals across 25 test files), `data/` (35 across
  26), `tasks/` (36 across 25), `infra/` (6 across 2) and `src/` (1 across 1).

  That is not a theoretical gap. #468 edited a pinned hash under
  `tasks/rebuilding_grading_task/`, started no run of this suite, merged, and
  left `main` red -- the same failure #179 caused and the one this workflow was
  written to prevent. Enumerating single files is what let the gap open twice,
  so the filter is directory globs now: a new assertion about a new workflow or
  a new task document is covered the day it is written.

  `data/**` was checked rather than assumed, since it carries grading results:
  over the last 60 commits on `main` it appears in 3, against 165 for
  `batch-runner/`, and most commits touching it touch `batch-runner/` too and
  already started a run. The bot-authored result PRs cannot start a
  `pull_request` run at all, so this reaches human PRs only -- and tests do
  assert about what is in `data/grades`.

  Two assertions in `test_the_free_check_runs_in_ci.py` were checking literal
  membership in the `paths` list, which scored the *wider* filter as a
  regression while continuing to pass for one that named a single workflow and
  missed twenty-nine other workflow references. They check coverage now,
  through a written-out translation of GitHub's glob rules -- `*` stops at a
  slash and `**` does not, which `fnmatch` gets wrong in the direction that
  restores false confidence. Removing `tasks/**` turns the check red with a
  message naming the file that would go ungated.

  The job timeout goes 30 -> 45 minutes. Run `34341659511` was cancelled by the
  old ceiling at 86% and its re-run of the identical tree passed in 22:10, with
  the twelve runs before it taking 18-22 minutes. A cancelled run is reported
  as a failure, so a ceiling that close to the mean turns runner variance into
  a red gate. This is headroom for that variance, not for a slower suite.

### Added
- **344 cannot be dispatched from a tag, and now says so before spending the
  one authorised dispatch rather than after.** §12 told the run to tag the
  merge commit and dispatch `--ref audio-344-dispatch`. The paid gate
  `approve-paid` deploys to the `grading` environment, whose deployment policy
  lists exactly one allowed ref — the `main` branch (`custom_branch_policies:
  true`, one entry). Every other ref is rejected.

  This is not inference from settings. Run `34038055900` (2026-09-06) already
  tried it on this workflow from tag `speech-diagnostic-run-1` at `5418048`:
  the free `dry-run` job succeeded, `approve-paid` **failed**, `measure` was
  skipped, and the annotation reads `Tag "speech-diagnostic-run-1" is not
  allowed to deploy to grading due to environment protection rules`. Following
  the old §12 would have burned the authorised dispatch on a gate error.

  The environment's allow-list is **not** being widened. Adding the tag there
  changes what the paid gate accepts, which is a protection-surface change to
  report with its exact scope, not to make in passing. The exact action, if
  someone decides to take it: repository settings → Environments → `grading` →
  deployment branch/tag policy → add `audio-344-dispatch` as a **tag**. This
  work proceeds without it.

  What replaces it verifies more, not less. The tag is still cut at the merge
  commit — as an immovable *name* for it, not as a dispatch ref. The dispatch
  goes out on `--ref main` while `main` still points there; GitHub freezes the
  run's `head_sha` at creation; that SHA is read back and compared against the
  tag; and **only if they match is the paid gate approved.** `measure` sits
  behind `approve-paid`, so nothing is spent before that comparison. The old
  order assumed the commit from the ref and checked afterwards; this one reads
  the commit that will actually run and checks before opening the door money
  goes through.

  The pre-registration was amended because the old step **does not execute**,
  not because a result came back — nothing has been measured and nothing has
  been bought.

- **344 ran, and the V3 header lost: `format_lost`, candidate closed.** Run
  `34363078893`, ten calls to `gpt-audio-1.5`, dispatched on `--ref main`
  under the amended §12. Its `head_sha` is `c301771`, byte-identical to the
  tag `audio-344-dispatch` cut at the merge commit, and that comparison was
  made **before** the paid gate was approved — the order the amendment exists
  to enforce. All four pins were re-measured at that SHA with the repository's
  own accessors and match the document: grader `7e745a18…`, price table
  `b01b384c…`, manifest `97755288…`, header `dd0380fa…` at 1,931 chars.

  Six of the seven registered conditions passed. The sixth did not: the
  candidate arm came back readable **3 of 5** against a registered 5/5, while
  the production control arm came back **5/5** — so the control behaved and
  the number is about the candidate. §6 calls a near miss a loss, and 3/5 is
  not a near miss. The candidate is closed: not re-worded, not re-ordered, not
  re-scored at a lower bar, and #338 stays shut.

  What #337 bought ten calls and could not produce, this run produced. The two
  unreadable replies are not the transcribed prose the standing hypothesis
  predicted. They are **refusals claiming the audio never arrived** — "I don't
  have access to the audio you're referring to", "I can't process the audio
  input without first receiving it" — on calls whose own usage records
  `audio_tokens: 30` and `34`, in the same run where the production arm parsed
  the same five clips at 30–34 audio tokens each. `finish_reason: stop`, zero
  braces, zero code fences, parser failing at character 0, `refusal_present:
  false`. §3.4 asked whether "the model is following an instruction to write
  prose" survives a header with no output instruction in it; it does not, and
  the surviving explanation — that the observation header can make the model
  fail to see the attachment — is recorded as a hypothesis and **not bought**.

  The ledger has 10 rows, 10 distinct `call_id`, `retry_kind: none` throughout
  (the SDK-retry-zero setting held), `requested_model` and `resolved_model`
  both `gpt-audio-1.5`, 320 audio input tokens, 4,095 input and 648 output
  text tokens. `model_cost_usd` is `null` on every row with
  `missing_reasons: ["price_missing"]`, so the receipt is `partial` and the
  amount is **null, not `$0`** — `gpt-audio-1.5` is absent from the pinned
  price table, and the token counts are kept so this run can be priced the day
  it is listed.

- **The Codex 401 is now surrounded by measurements, and four of its five
  candidate causes are closed.** Three runs on 2026-09-09 from `main` at
  `cb043af`: the free read-only probe (`34346945494`), the free ARM role
  inventory (`34347345143`), and the one authorised paid turn
  (`34347516170`).

  The free read minted the token **the way Codex mints it** — the provider's
  `auth.command` as a child process — and `GET /models` answered **200** with
  **428** models, `gpt-5.4` among them. The role inventory found the CI
  identity holding exactly one assignment, `Cognitive Services OpenAI User`
  (`5e0bd9bd-…`) at **foundry-account** scope, with
  `principal_can_assign_roles: false` and `read_failures: []`. The paid turn
  then returned **401** with `usage: null`.

  Set beside the wire-format and retry measurements already taken against the
  pinned `0.147.0` binary and a local mock server, that closes the address
  (fingerprint `sha256:69057d59166a82e3`, identical to the first 401), the
  identity (token minted), the deployment (present in the listing) and the
  header (`authorization: Bearer` on `POST …/responses`, not `api-key`).

  The one new fact is the refusal's text: `Access denied due to invalid
  subscription key or wrong API endpoint…`, the Cognitive Services
  subscription-key string, returned by the host that had accepted the same
  identity's bearer for a read minutes earlier in the same job. It is recorded
  because it is what came back — that gateway message covers more than one kind
  of refusal, and nothing measured distinguishes them.

  What is **not** established: which data action is refused (a listing and a
  completion are not the same one); that the RBAC verdict explains this —
  `azure_rbac_diagnostic` runs only against a Foundry **project** endpoint
  while Codex uses the **account** `direct-v1` route, so its
  `role_missing_and_an_owner_must_grant_it` answers the Code Interpreter arm's
  403 on a different surface; and the cost, which is **unpriced and not zero**
  (`usage: null`, and the record's own note says the turn may still have been
  billed).

  No role was granted, no policy relaxed, no credential or VM created. The
  next step that would justify a grant is itself free and was deliberately not
  run here, because the authorisation was for one turn and one turn was used:
  a malformed `POST` to the same route with the same bearer, where a `400`
  moves the fault off authorization and a `401` keeps it there. Neither
  generates tokens.

  One live improvement is measurable: the same refusal that produced **6**
  error notifications in run `34319880025` produced **1** with the retry pins
  in force. The two HTTP requests an authentication failure still costs are
  unchanged and documented. Error notifications are not requests.

- **The connection question now has a free half: the token is minted the way
  Codex mints it, and the host is asked to list its models.**
  `--read-only-probe` runs the provider's `auth.command` **as a child process
  and reads stdout** — which is how the Codex runtime obtains its token, and
  not how the grading and inference paths obtain theirs — then issues
  `GET {base_url}/models`. No prompt, no completion, nothing to generate; it
  runs on every dispatch including the dry ones.

  It exists because run `34319880025`'s 401 survived every offline check made
  against it. The URL (`https://<account>.services.ai.azure.com/openai/v1/`),
  the token scope (`DIRECT_TOKEN_SCOPE`), the header name and format
  (`authorization: Bearer …`, measured on the wire) and the OIDC identity all
  match the direct-v1 path grading uses successfully for tens of thousands of
  rows — so **none of them explains the refusal, and the fault is not
  located.** Where the token comes from was the one difference nobody had
  measured. A `200` says this resource accepts that token and moves the
  question to something narrower than the identity; a `401` reproduces the
  refusal having spent nothing; `deployment_listed: false` would say the name
  asked for is not on the resource at all.

  The record is `codex_foundry_readonly_probe/1` and carries
  `inference_requested: false`. Model names are **counted, never recorded** —
  a deployment list names a resource. The token is never in the record, and a
  failing auth command has its **stdout withheld** while its stderr is quoted,
  because a credential chain can print a token and then exit non-zero on a
  later step.
- **What a green listing still does not buy is written into the record
  itself**, as `not_established`: a listing is not a completion and a resource
  can list to an identity it will not let infer; `deployment_listed` says a
  name appears, not that this identity may call it; and no inference was
  requested, so **the call is unpriced — which is not the same as proven
  free.** Without this, a 200 here is exactly the result that gets quoted as
  "the connection works".

- **The Codex diagnostic's "no retries" is now a setting the runtime reads,
  not a line it wrote about itself — and one turn against a 500 stopped being
  thirty requests.** `request_plan()` reported `retries_configured: 0` while
  the provider table set neither retry key, so the pinned runtime used its own
  documented defaults (`request_max_retries` 4, `stream_max_retries` 5). Both
  are now fields on `CodexProviderSettings`, defaulted to 0, **emitted into
  the provider table**, carried in `describe_provider()`, and included in the
  diagnostic's settings fingerprint — so a verdict measured with retries
  pinned cannot be read as evidence for a run without them. The plan reads its
  numbers off the same settings object the table is built from, and reports
  `null` rather than `0` when no settings could be built, because a run that
  could not be configured did not configure zero retries.
- **Measured against the real binary, not asserted.**
  `tests/test_codex_retry_pins_are_enforced.py` starts the pinned `codex`
  binary against a local server that refuses four different ways and counts
  the requests that arrive. The token is a fixed fake string and only two keys
  of the production provider table are rewritten — `base_url` and
  `auth.args` — which a test asserts, so the `Authorization: Bearer` header
  observed on `POST /v1/responses` is produced by the same `auth.*` block
  production emits.

  | server answers | counters unset | pinned to 0 |
  | --- | --- | --- |
  | HTTP 500 | 30 requests | 1 request |
  | mid-stream disconnect | 6 requests | 1 request |
  | HTTP 429 | 1 request | 1 request |
  | HTTP 401 | 12 requests | **2 requests** |

  The 401 row is recorded as a bound the pins do **not** remove: the runtime
  re-runs the provider's auth command once after an authentication failure and
  retries with the fresh token — two requests, two tokens minted — and no
  documented key switches that off. It is in the record as
  `retries_not_removed_by_pinning` rather than rounded down to one, and the
  test asserts it at exactly 2 so that a runtime which later drops the retry
  turns the claim red instead of leaving it standing.
- **The record format is `codex_foundry_connection/2`.**
  `request.retries_configured` changed from the scalar `0` to the two counters
  actually written into the table, so a `/1` record — including the one from
  run `34319880025` — cannot be misread as saying how many requests its turn
  made. It made an unknown number.
- **The grader source fingerprint moves with this: `ee1ca0b0…` →
  `7e745a18…`.** `core/codex_runtime_config.py` is inside
  `compute_grader_source_hash`'s walk of `core/*.py`, so a one-line change
  there moves it. Both values were measured rather than reported —
  `ee1ca0b0…` re-measured at `3d51e7cc`, where it still matched `342` §2, and
  `7e745a18…` on this branch. Nothing in `337`/`342`/`343` is rewritten: those
  record what was true for runs that are finished. What this does mean is that
  `342` §0's fingerprint rows re-open for **any future paid dispatch**, exactly
  as `343` §5.1 says they do on the next `core/` merge — re-measure before
  buying, do not carry `ee1ca0b0…` forward. No grade run was in flight when
  this merged.
- **`344`'s run will record what came back, not just how many came back.**
  `339` §9 ends "we did not store the body, so we never saw what it wrote",
  and that is why `337` bought ten calls and stopped in the same place `334`
  stopped. `WireClient` now calls `335`'s own `collect_response_facts` on each
  reply and files the result under `response_shape`, so a failed envelope
  leaves a `finish_reason`, a brace count, the character the parser stopped
  at, the contract keys present and a masked 240-character head. **Opt-in per
  kind**, and `speech-format-pilot-v3` is the only kind opted in: `333`,
  `337`, `338` and `342` registered a delivery record of a fixed shape and
  widening theirs now would change what their own documents describe, so
  `response_shapes` is *absent* — not empty — from every other kind's digest.
  Recorded defensively: a collector that raised on the malformed reply it was
  added to describe would take a paid run down and leave nothing behind, so a
  failure to read the shape is written into the record as `shape_error`.
  Internal reasoning is a boolean and nothing else; a test toggles the block
  and asserts `reasoning_present` is the *only* field that moves.
- **`scripts/verify_format_pilot_run.py` — `344` §6's verdict, decided by a
  file written before the run it judges.** Seven conditions over the report
  and its ledger, no model call and no socket: the header and grader pins
  match the pre-registration, ten requests went out with no early stop and no
  retried call, both arms ran the same five claims, the control arm held
  ≥4/5, the candidate held 5/5, and a paid run does not report its cost as
  `0`. A rehearsal cannot return `format_held` and a *broken* rehearsal
  cannot return `rehearsal_ok`, because that word is what `344` §0 ticks a
  precondition on.
- **The checker is made to say no.**
  `tests/test_the_format_check_can_fail.py` starts from `337`'s **real
  committed report**, relabels its pins as V3, and confirms the checker reads
  the 1-of-5 that started all of this as `format_lost` with 0 usable
  verdicts — a fixture written alongside the checker would agree with it by
  construction. Then it breaks a passing run each way §6 names: 4-of-5 (the
  number most likely to be argued into a pass), a collapsed control arm
  (inconclusive, in *both* directions, so a broken control cannot launder a
  perfect candidate), a short run, an early stop, a retried call, a
  substituted header, a moved grader, mismatched claims, a missing ledger,
  and a paid run reporting `$0`.
- **The `344` verdict is now computed where the run happens, on both the free
  job and the paid one.** A checker that lives in the repository and is called
  by nothing is a precondition satisfied on paper, and `344` §0 ticks boxes on
  two checks that only exist in CI. `audio-accuracy-probe.yml` gains a step in
  each job: the rehearsal is read from `audio-accuracy-dry-run.json`, the
  pilot from `audio-accuracy-measured.json`, and each writes a verdict file
  that is uploaded **with the ledger rows it was computed from** — `337`'s
  per-call record lived only in an artifact, the artifact expired, and `340`
  had to be written to say the numbers could no longer be produced.

  Both steps run under `always()` and **carry the checker's exit code**, after
  the summary is written so the reason is on the page when the step is red. A
  rehearsal that came back `inconclusive` — wrong pin, short call count, no
  ledger — under a green tick would clear a paid dispatch using the finding
  that should have stopped it. Four tests break the workflow four ways (the
  rehearsal step pointed at the paid filename, which would skip *silently*;
  a swallowed exit code; the verdict files dropped from the upload; the steps
  made conditional on success) and each goes red.
- **What the checker actually opens, in its own docstring.** It said "the
  report and the ledger export beside it"; it reads the report and the
  pre-registration, and the ledger *reference* comes from inside the report's
  cost block. The difference matters for a tool whose case rests on naming
  exactly what it looks at — and it means a report stays checkable after the
  `.sqlite3` beside it is gone.

- **344's rehearsal ran, and its §0 now carries six ticks instead of none.**
  Run `34351518357` on `6e867a66`, dispatched free: `dry_run: true`,
  `paid_approval: false`, `repeats: 1`, `prompt_arm: production`,
  `corpus: speech-format-pilot-v3`. All three paid jobs report `skipped` —
  `approve-paid` is gated on `dry_run == false && paid_approval == true`, and
  a skipped dependency skips `measure`, so no path to a billed call existed.

  The verdict file is `rehearsal_ok`, and the interesting part is which
  conditions it refuses to answer. Conditions 1–4 and 7 pass: the candidate
  header is `dd0380fa…` in both the report and the pre-registration, the
  grader is `7e745a18…` in both, ten planned requests produced ten calls with
  no retry and no early stop, both arms asked §4's same five criteria in
  §4's order, and the ledger holds ten rows with receipt `partial` and amount
  `null` (`price_missing` — `gpt-audio-1.5` is unpriced, which is not `$0`).
  Conditions 5 and 6 — the two readability gates the whole experiment is
  about — come back **unanswerable**, because a rehearsal's replies are the
  stub's and say nothing about what the deployment does with the candidate
  header. A rehearsal that passed those two would be reading canned text as
  evidence, and would remove the reason to buy anything.

  So this fills §0's fifth and sixth boxes and no others. Three remain, and
  the order is fixed: re-measure §2's four fingerprints **at the dispatch
  SHA**, confirm A is not mid-`core/`-change, then pin that SHA behind an
  immutable tag. Nothing has been bought.

  The rehearsal is also the first look at §9's response-shape record on a
  real artifact, under `wire.response_shapes` in the report. It carries what
  §9 promised and in the shape §9 promised: `finish_reason`, open and close
  brace counts with a balance flag and the offset of the first one, the JSON
  error type with its **character position and characters remaining**, the
  five contract keys as present/missing with their types, character count,
  first and last non-whitespace character, and a masked excerpt (162 chars
  here, under the 240 ceiling). Reasoning is a **boolean** — `reasoning_present`
  — and there is no credential, no request id and no reply body beyond the
  excerpt. This is precisely what 337 spent ten calls without recording, and
  what left 339 unable to say more than "it failed in the same place as 334".

  §0's earlier boxes are attributed to the PRs that actually filled them
  rather than left blank: the header and corpus registration to #468
  (`446acfd`), the response-shape record to #470 (`82db5fc`), the verifier
  and its ten broken-report cases to #470 with the four broken-workflow cases
  to #473 (`ce847ff`). The §0 paragraph on dispatching a paths-filtered
  commit is rewritten twice over: #475 (`0aae1c3`) put `tasks/**` into both
  triggers, so the box-7 re-pin commit now starts a run on its own and that
  paragraph becomes a record of how it used to be. The explicit dispatch
  stays anyway, because §12's concern is holding a run to one commit rather
  than to a branch that moves.

  It also cited the wrong run, in a way worth keeping visible: the dispatch
  meant to give `main`'s merged commit a verdict, `34351414118`, came back
  **cancelled** — `concurrency: backend-tests-${{ github.ref }}` with
  `cancel-in-progress`, and #475's own push run took the group. So the check
  before a paid dispatch is not "a run was started" but **"that run finished
  `success`"**. #475 did not touch the concurrency block, and a cancelled run
  still reads much like a passing one in a run list.

- **344's four fingerprints re-measured at the dispatch SHA, and the eighth
  box closed with what was actually checked.** At `cff4d7c1`: grader
  `7e745a18…`, price table `b01b384c…`, manifest `97755288…`, candidate
  header `dd0380fa…` (1,931 chars). **All four match what §2 already
  carries**, so the table needs no new value — what was missing was the
  measurement, not the numbers.

  It was taken with the repository's own accessors on both sides rather than
  by hashing files by hand: `grader_pin_stated_in` against
  `grader_source_hash()`, `price_table_pin_stated_in` against
  `sha256(PRICE_TABLE_PATH)`, `manifest_pin_stated_in` against the manifest
  bytes, `candidate_pin_stated_in` against
  `sha256(SPEECH_OBSERVATION_HEADER_V3)`. Reading the document with the same
  function the run uses is the point: a hand-rolled comparison would prove
  the two files agree with *my* arithmetic rather than with the code's.

  The commit carrying this cannot move any of the four — it touches this
  document and `CHANGELOG.md`, the grader fingerprint covers neither, and the
  manifest is a file this work never opens. That is stated rather than
  trusted: the measurer re-checks the grader and header pins against the
  document at run time and stops before calling the model if either has
  moved, which is what conditions 1 and 2 of the rehearsal exercised.

  For the `core/`-drift box: **zero open PRs** at that commit, and `main`'s
  last `core/` change is `7a8c94d` (#467) with ten commits landed since that
  touch none of it — #477 included, which is documentation only.

  The ninth box is deliberately left unticked, and §12 now says why. The tag
  goes on the commit that carries this document, so ticking it here would put
  a document claiming a finished step inside the tag that step creates. Its
  evidence is `git`, not markdown: `git rev-parse audio-344-dispatch^{commit}`
  against the dispatched run's `headSha`, both copied into §13. If they
  differ, nothing is bought — and a failed run does not get the tag moved to
  a new commit, which would be §7's forbidden re-dispatch under another name.

### Fixed
- **How `446acfd` came to sit red, since #469 fixed it without the two dates
  that explain it.** `344` §2's grader row carried `ee1ca0b0…` because that is
  what `342` pinned; the entry above moved the fingerprint to `7e745a18…`
  while `344` was being written. Neither PR could have caught it: #467 was
  green before `344`'s test existed and #468 was green before #467 merged
  (08:42 and 09:00 against 08:53). Both were right about the tree they ran on
  and wrong about the tree they made. #469 moved the row; independently
  re-measured here, the **other three** pins — price `b01b384c…`, manifest
  `97755288…`, candidate header `dd0380fa…` — had not moved, so the one line
  that changed is the one `core/` reaches.
- **Correction to the entry above, which said nothing runs the suite on a
  push to `main`.** That is wrong, and the run that disproves it is the one
  the entry is about. `backend-tests.yml` has had `push: branches: [main]` all
  along; commit `446acfd` started run `34332874303` at 09:06 and it finished
  `failure` at 09:28 with `assert 'ee1ca0b0…' == '7e745a18…'` — 1 failed, 9195
  passed. CI named the wrong line, in the right file, within twenty-two
  minutes. Nobody read it.

  Two mechanisms are real, and neither is the one first written down. The
  `push` trigger is **paths-filtered** to `batch-runner/**`, `scripts/**` and
  two named workflow files, so #469 — which edited one `tasks/**` document and
  nothing else — started no run at all: the change that returned `main` to
  green was never itself run on `main`. Green came back at 10:32 on `ce164ad5`,
  a later merge that happened to touch a filtered path. Separately,
  `concurrency: cancel-in-progress` keyed on `github.ref` means consecutive
  merges cancel each other's `main` runs: `7a8c94de` (#467) and `cb043afa`
  (#472) both carry `cancelled`, so two commits sit on `main` with no verdict
  either way — and a cancelled run is not visually distinct from a passing one
  in a branch listing.

  This matters to `344` beyond bookkeeping. §0's last precondition re-pins §2's
  four fingerprints in a `tasks/**` document, which is precisely the change
  shape that starts no run — the pins would land unverified unless something
  else touches a filtered path in the same commit. §0 now carries the remedy:
  `backend-tests.yml` accepts `workflow_dispatch` with a required
  `expected_sha`, so a doc-only commit can be given a real verdict without a
  decorative edit to a filtered path. This entry's own PR had no checks at all
  for exactly the reason it describes, and was dispatched that way.

  **Still not fixed here.** Both mechanisms live in `.github/workflows/`
  trigger blocks, which is A's lane this week; changing them while A's Codex
  work is mid-flight is how the collision above happened in the first place.
  Recorded with the run IDs so the next person owns a measurement rather than
  a hunch.
- **`verify_format_pilot_run.py` is named in `.gitignore`, which is not a
  formality.** `batch-runner/scripts/*` is ignored and files are re-admitted
  one `!` line at a time, so the checker was written, tested green and absent
  from `git status`. `344` §0 ticks a precondition on this file having been
  merged, so an untracked copy would have held that gate open on a file only
  one working tree had. A test now asks git what is tracked rather than
  trusting the allowlist.

### Fixed
- **The read-only probe never reached the host, and reported it as though the
  host had answered.** `auth_command` is a *method* on `CodexProviderSettings`;
  the probe read it without calling it, so `subprocess.run` was handed a bound
  method and `'method' object is not iterable` landed in the record's
  `token.error` field beside the host's answers. Run `34340775246` burned a
  real OIDC login producing that, finished green, and settled none of the three
  outcomes it exists to separate.

  Three repairs, because the calling convention was the least of it:

  - the probe calls `settings.auth_command()` and **checks the argv's shape
    before starting a child process**, raising a message that says this is a
    defect in the probe rather than an answer from the host;
  - the test helper that substituted the command defined it as a `@property`.
    That is not the shape production has, so every minting test read a value
    and passed while production got a method — a helper modelling the wrong
    shape tests the helper. It is a method now, and one test uses the
    **unmodified** settings object against a stub auth module so the argv
    production builds is exercised with nothing overridden. Reintroducing the
    original defect now turns 5 tests red; before the helper was fixed it
    turned 0 red;
  - the workflow step **fails** when the token could not be minted. A refusal
    is a finding and the step keeps going for it; never reaching the host is
    not a finding, and a green step there is how the run looked like it had
    measured something. Failing there also blocks the paid turn, since a job
    that cannot mint a token has no business buying one.

  What the run *did* settle, read off the record rather than the network: the
  probe was aimed at the same host that returned the 401
  (`endpoint_host_fingerprint` byte-identical to run `34319880025`'s), and the
  retry pins are live in the settings object the job actually built
  (`request_max_retries: 0`, `stream_max_retries: 0`) rather than only in
  tests. The 401 itself remains unlocated.
- **The workflow's leak check would have crashed on the record it was being
  asked to check.** It indexed `record["observed"]` unconditionally, which the
  read-only record has no key for, so publishing one would have raised
  `KeyError` inside an `always()` step and failed the job *after* the run
  rather than before it. It now branches on the record's own `schema` and
  enforces `inference_requested is false` on the new shape — deliberately not
  `.get("observed", {})`, which would have been shorter and would have turned
  a renamed field in the connection record into a silent pass.

  The workflow's own script is now executed by
  `tests/test_codex_readonly_token_probe.py` against both record shapes;
  reverting the branch turns three of those tests red with the actual
  `KeyError`. Nothing had run that heredoc before, which is why a one-line
  indexing bug reached a workflow file.
- **`_redaction_check()` was selecting "the first step containing a heredoc"**
  and silently changed subject the moment a second heredoc step was added
  ahead of it — six tests began asserting redaction rules about a step that
  has none. It now selects by step id, and the readonly record's path is
  redirected into the test's own directory like the other two, instead of
  reading whatever a real dispatch left in `/tmp` on the machine.

### Changed
- **`CodexProviderSettings` refuses a retry count that is not a whole
  non-negative number, including `True`.** `bool` is an `int` and
  `_toml_literal` would render it as `true`, which the runtime reports as a
  type error about a config file no operator wrote.

- **A refusal now reaches the audio checker as a refusal, and a paid run whose
  every call was declined is `inconclusive` rather than `rehearsal_ok`.** The
  shared fix `341` proposed landed in the common metering code (not this
  branch's work, and not edited here): a verifiable HTTP refusal settles as
  **`refused` / `call_refused_unpriced`** instead of leaving a standing
  reservation. `340`'s pinned expectation moved with it — `[refused]` is now
  `refused` and `[broke]` (5xx) stays `reserved` / `call_reachability_unknown`
  — and both branches are pinned **by state and by reason**, separately,
  because a test written to accept either would still pass on the day the
  distinction is lost. A refused row is **counted as a call, claims no amount,
  and holds the receipt at `partial`**; routing it to `abandoned` instead
  would drop it out of `model_calls` and close an all-refused run as a
  **complete receipt for `$0`**, which says the run spent nothing rather than
  that its cost is unclaimed.
- **Condition 7 tells a reply apart from a request that never got one.** It
  used to require a settled row for every broken verdict, which on an
  all-refused run produced the sentence *"a reply that could not be parsed was
  still a reply, and it was still billed"* about calls that were never
  answered — a false statement, found by running the integration rather than
  by reading it. It now reads `requests_that_raised` off the wire records and
  asks two things separately: replies must have settled rows, raises must have
  refused-or-reserved ones. **The loose form was rejected on purpose** —
  "settled or refused, either is fine" is one line shorter and passes on the
  day a reply's row goes missing, so a deliberate test deletes a settled row
  and requires condition 7 to fail. A report that does not carry the raised
  count **says it cannot tell them apart** instead of pretending to, and that
  fallback has its own test.
- **`inconclusive` — a fourth verdict, for a paid run that failed nothing and
  answered nothing.** Condition 2 becomes `unanswerable` by two different
  routes now, carried in `unanswerable_because`: `rehearsal`, where there was
  no provider to answer, and `no_model_ran`, where the calls were all refused.
  The second is not a rehearsal — that word belongs to runs that spent
  nothing, and a paid artifact wearing it reads as free — and it is not
  `measured_ok` either, which would claim a measurement nobody made. The exit
  status stays **0**, because what the status answers is *does this cost
  record hold together*; whether the run learned what it wanted is the
  **verdict word**, and callers that need the second must read `verdict`
  rather than the status. `342` §1 and `343` §5.4 now state the two exit-code
  scales side by side: the measurement's `2` means the **accuracy** question
  went unanswered, the checker's `0` means the **cost** question was answered,
  and a run can honestly be both at once.
- **All eight ways a metered audio call can end are walked end to end** in
  `tests/test_every_way_an_audio_call_can_end_is_metered.py` (13 tests), from
  the production adapter through the receipt to all nine checker conditions. A
  verifiable refusal is a counted call with no amount; a request stopped by
  the ceiling leaves **no row and no wire record at all**, because the cap
  raises inside `WireClient` above the metered client, which is what keeps
  condition 1 an equality rather than an inequality; a timeout stays
  `reserved`, since a request that may have been served is not the same as one
  that provably was not; a reply with no usage block settles as `usage_absent`
  because the reply itself is the evidence it was billed; an unpriced model
  reports `null`, never `$0`; an unreadable reply settles carrying its usage;
  re-reading the export reproduces a refusal unchanged; a recorded cost is not
  overwritten by a second, differing settlement; and `refused` is terminal —
  settling or abandoning one raises. One asymmetry is worth knowing before
  reading the rows: a **refusal writes its reason onto the row**, while a
  reserved row's `missing_reasons` is empty and `call_reachability_unknown` is
  **derived by the receipt** from the row still being open, so that ending is
  asserted on the receipt and not on the row.
- **None of this changed what the rehearsal reports, and nothing was bought.**
  The checker still returns **8 passed, 0 failed, 1 unanswerable —
  `rehearsal_ok`** on the offline run; it was not turned into 9/9. The grader
  fingerprint moved with the shared fix, `50f6f8bb…` → `ee1ca0b0…`,
  recomputed here rather than taken on report; the price table did not move
  (`b01b384c…`), which is the point of pinning the two separately. Both were
  then **re-measured on `38038a1`, the merge of this work** — the code a paid
  run would actually execute — and came out unchanged, so `342` §0's two
  fingerprint rows are ticked against a named SHA. They re-open on the next
  merge that touches `core/`, which is why `343` §5.1 is run again
  immediately before any dispatch. The paid run stays unstarted:
  `gpt-audio-1.5` was not called, no ledger row was bought, and `337`'s
  artifacts and pre-registration are untouched.
- **The metering path `340` found missing now runs end to end, with no model
  called and nothing bought.** `measure_audio_grading_accuracy.py` opens the
  production `cost_recorder`, meters the client **inside** `WireClient` rather
  than around it — that client rewrites the request before calling `create`,
  so a meter on the outside would digest a body nobody sent — and runs the
  perception calls inside `attributed(task_id="audio_accuracy_diagnostic",
  stage=STAGE_PERCEPTION)`. The cost block that `340` showed to be four
  constants is now the ledger's own answer: `pricing_complete`,
  `unpriced_models`, `estimated_cost_usd` and the receipt come from a lookup
  against the pinned price table, and **usage-missing and price-missing are
  separate fields** (`missing_reasons.usage` vs `.price`) rather than one
  sentence. **No second ledger was built** — only the public API of
  `core/cost_receipts.py`, which this work reads and does not edit. `337`'s
  artifacts and pre-registration are untouched; no request ID and no ledger
  row was reconstructed for calls made when there was no ledger.
- **`--metering-run` refuses before it spends, and the checker was written
  before the run.** The flag takes `342` as a document and stops with `exit 3`
  on a mismatched diagnostic kind, a claim count other than two, repeats other
  than the registered one, a plan larger than its registered ceiling, and each
  of three independent fingerprints — grader source, price table, speech
  manifest. **The manifest pin is the one that is easy to miss**: a swapped
  corpus passes every clip digest in `load_speech_corpus`, because the file
  making the claim is the file being checked, so consistency only becomes
  identity once the document names the manifest's own digest. Judgement is
  `scripts/verify_audio_metering_run.py`, which reads the report and the
  ledger export and nothing else — no model, no credentials, no network — and
  reports `measured_ok` / `rehearsal_ok` / `inconclusive` / `failed`. A
  rehearsal cannot reach
  `measured_ok`: the stub has no audio tokens, so condition 2 is recorded as
  **`unanswerable`, a third state that is neither pass nor fail**, and the
  verdict stops one short of the paid one.
- **The whole path was rehearsed offline and reached `rehearsal_ok`.** Two
  planned requests produced **two ledger rows, no duplicates**, both under the
  diagnostic's task with the problem-solving bucket left `not_run`;
  `provider: stub` and `resolved_model: stub-not-a-model` on every row;
  `pricing_complete: false`, `missing_reasons.price: ["price_missing"]`,
  `usage_complete: true`, receipt `status: partial`, and
  **`estimated_cost_usd: null` rather than `$0`**. The checker returned
  **8 passed, 0 failed, 1 unanswerable — `rehearsal_ok`, exit 0**. The corpus
  is two synthetic tones the test builds in a temp directory and never
  commits, so no artifact can later be mistaken for `330`'s speech set, and
  `342`'s real document stays pinned to `330`'s manifest. It carries **four
  claims for a two-question run**, because the loader requires every
  `pair_id` to hold exactly one true and one false claim and narrowing does
  not re-run that check. **A rehearsal is not evidence about `gpt-audio-1.5`**
  — it is kept apart at three layers: `record_kind` in the report, the
  provider and model on every row, and a ledger that refuses to accept rows of
  the other kind.
- **Breaking the verdict does not erase the cost, and neither does the
  ceiling.** With every reply broken — one unreadable envelope, one valid JSON
  declining to judge, which take different code paths — the run exits **2, "no
  verdict was reached"**, while both cost rows survive, the receipt closes,
  and the checker still returns `rehearsal_ok`. **The two exit codes hold the
  two questions apart**: `2` from the measurement means *we did not hear*, `0`
  from the checker means *we recorded what we spent*, and neither covers for
  the other. A run stopped by its request ceiling exits 3 and **still exports
  the request that already went out**, because export happens in `finally` —
  exporting only on success would delete the record of exactly the spend
  nobody planned. Sixty-six tests across four files —
  `tests/test_the_metering_run_goes_end_to_end.py` (19),
  `tests/test_the_metering_check_can_fail.py` (20),
  `tests/test_a_broken_audio_reply_still_costs_what_it_cost.py` (14) and
  `tests/test_every_way_an_audio_call_can_end_is_metered.py` (13); the second
  feeds the
  checker wrong task attribution, duplicate rows, an unsettled call, an
  inflated `pricing_complete` and an amount on a row with no rate, and
  requires **the condition that claims to catch each one** to be the one that
  does. `check_grader_hash_freeze.py` reports "PASS: no grader-source file in
  this diff" for every path changed here. **`342` §2's grader and price
  fingerprints remain provisional and must be recomputed at the merged SHA
  before anything is bought; `337`/`338`'s thresholds are unchanged and the
  120-call experiment is not resumed.**
- **`340` — the audio calls `337` bought never reached the ledger, so §11.9's
  "sound metering is unverified" is still true.** The probe that spent those
  ten calls builds `AudioPerception(client=wire, …)` with an unmetered client;
  across all 4,131 lines of `measure_audio_grading_accuracy.py` there is no
  `MeteredClient`, `CostRecorder`, `CostReceiptLedger`, `open_cost_recorder`
  or `price_call`, where the production grader wraps the same client in
  `cost_recorder.meter(…, stage=STAGE_PERCEPTION)`. Its cost block reads like
  a lookup and is not one: `pricing_complete` is `not billable`,
  `unpriced_models` copies the deployment name through,
  `estimated_cost_usd` is the literal `None`, and the note naming the model as
  absent from the price table is a sentence someone wrote rather than a
  finding — all four would have printed identically had `gpt-audio-1.5` been
  priced, and a dry run, which is billable for nothing, prints
  `pricing_complete: true` about the same unpriced model. The values are right
  (`azure:gpt-audio-1.5` is genuinely in `models_deliberately_not_priced` with
  `official_price_exists: false`, re-verified 2026-09-07) and they are
  right by coincidence. So `337`'s artifacts prove the **adapter** leg and
  only that: usage complete on 10/10 calls, 4,095 input and 553 output tokens,
  320 audio tokens, one digest per clip. Ledger rows: zero. Priced calls:
  zero. Receipts: zero.
- **The production metering path is now driven end to end with broken
  replies** — `Grader` → `cost_recorder.meter()` → `AudioPerception` →
  `MeteredClient` → `CostReceiptLedger` → receipt, reading its settings from
  `grading_configs/default_v2.yaml` rather than restating them, with only the
  provider response faked. `tests/test_a_broken_audio_reply_still_costs_what_it_cost.py`
  is 14 tests and covers what the existing suite does not: the paths that
  fail. A reply that is prose rather than JSON and a reply that is valid JSON
  declining to judge both settle with 1000/200/30/10 intact, because `_around`
  settles before anything parses the envelope; a reply with no usage block
  settles as a call with no number and still counts as a call; a failure
  before the wire files no row at all; an unknown call does not erase the
  known money beside it ($0.118 of a three-call task survives one 500); the
  audio share is charged inside the input count ($0.059) and not on top
  ($0.061); a resumed run adds its round to the ledger it reopened; and a
  second settle with different figures raises `LedgerIntegrityError` rather
  than overwriting what was recorded. Perception spend lands in
  `grading_cost` and never in `problem_solving_cost`. **Fourteen green tests
  on the first run are the least trustworthy result available**, so the
  production code was broken eight ways by monkeypatch — settle made a no-op,
  settle moved after the parse, usage-less rows dropped, audio added on top,
  audio priced as prose, one unknown call sinking the task, resume forgetting
  its round, contradictory settles overwriting — and every one is caught by
  the test that claims to guard it. Moving settle after the parse fails only
  the unparseable-prose case and not the declined-verdict one, which is the
  distinction `339` §2 paid to establish.
- **Price-missing and usage-missing are verified separately, and neither ever
  becomes `$0`.** Two different causes share `price_missing` by design — a
  model absent from the table, and a model priced for text while the call
  carried speech — so the second is pinned against a negative control: the
  same table prices a zero-audio call, which is what makes the refusal about
  the speech rather than about the table. Contradictory usage (an audio share
  larger than the total it belongs to, a split that is `None` under audio
  rates) stays `usage_partial` and does not leak into `price_missing`. No rate
  was invented for `gpt-audio-1.5` and none was borrowed from a similar model.
- **`341` — a provider refusal is filed as a call that might have run.** The
  eight statuses `core/perception/audio.py` already knows are unbilled
  (`400`, `401`, `403`, `404`, `413`, `415`, `422`, `429`) reach the ledger as
  nothing at all: `_around` has no `except`, so the reservation stands and the
  receipt reports `call_reachability_unknown` — the specification's「API 도달
  여부 불명확」— about a request that provably reached the API and provably came
  back. **The amount is right and the reason is wrong**; a standing
  reservation is the safe direction, and what a rate-limited run would produce
  is false "might owe money" flags crowding out the real unknowns beside them.
  `abandon` as documented is not the existing answer either — it requires the
  call to have never left. The document carries a test that fails on all eight
  statuses today, a three-file proposed diff, and a measurement of its blast
  radius: applied by monkeypatch the eight pass and the filtered suite gives
  1 failed / 1,666 passed / 4 skipped, the single failure being `340`'s own
  assertion recording today's behaviour while its 500 branch keeps passing.
  Shared metering code is read, quoted and not edited.
- **A pre-registration-ready plan for the smallest real metering run**, kept
  strictly apart from the accuracy work: one task, two criteria, six requests,
  zero transport retries, a ten-minute paid-window ceiling, and no re-dispatch
  if it fails. Its nine pass criteria are all about the ledger and none about
  verdict correctness — a run whose verdicts all break is a *good* test here.
  The clips are `crate` and `shelf` from the committed
  `330-speech-verification-manifest.json`, whose `crate` digest
  `7e59f9a5…` is the one `337` actually put on the wire, so the pin is a value
  that has already survived a real dispatch. Because the model has no rate,
  the ceiling is stated in requests rather than dollars — **no amount ceiling
  was introduced**; the six is a per-diagnostic entry in the existing
  `SPEECH_REQUEST_CAPS`, counted on the wire, and the config's
  `audio_call_cap_per_task` is read as it stands rather than lowered.
  **Nothing was dispatched and no model was called.**
- **`339` — the pilot ran, the candidate missed its bar, and `338` is not
  bought.** Ten paid calls at commit `e7a820e2`, run `34211419777`, ten
  requests counted against a registered ceiling of twelve, each call one
  `create` with no 429/5xx/timeout in the log — the report says "no trace
  suggesting a retry" rather than "no retry", because SDK-internal retries sit
  below that counter. `337` §5 asked for readable JSON on 5/5 candidate calls
  with the production control at 4/5 or better; the control returned **5/5**
  and the candidate returned **1/5**, so the run is valid and what failed is
  the candidate. Four replies were
  `format_error:unparseable_json` and the fifth parsed and declined, which is
  why the report carries two numbers rather than one: 1/5 envelopes is what §5
  judges, 0/5 usable verdicts is what the run learned about verdicts. The
  candidate sentence was delivered — every observation prompt is exactly 898
  characters longer than its production twin against `334`'s 739, and 898 −
  739 is the 159 the sentence adds — and the audio was delivered too: 10/10
  requests carried it, one digest per clip across both arms, no clip's sent
  duration off its pin. The four unreadable replies are 22–29 output tokens
  against the 18–68 (median 32) of `334`'s 51, which places them in the same
  neighbourhood and no further: no response bodies were stored, so the report
  states the length match and declines the mechanism claim `335` paid to
  establish. Content accuracy is recorded and used for nothing, as §6 fixed
  before the run — the control answered `fail` five times for 2/5 with
  `discrimination_j` 0.0, and the pre-registered one-sided exact binomial
  gives p = 0.8125 where the smallest p this size can reach is 0.03125, so no
  result of five calls could have been significant. Cost is
  `estimated_cost_usd: null` with `pricing_complete: false` and
  `unpriced_models: ["gpt-audio-1.5"]`; usage is complete on all ten calls, so
  the figure is unknown rather than zero. **`338` is closed rather than
  re-pinned**: §0's first row stays unticked, its thresholds are unchanged,
  the pilot's ten calls are not pooled into its 120, and a next candidate
  needs a new number. `331`/`334`/`335`/`336`'s published figures are
  untouched, no production prompt or grading configuration was modified, and
  the parser and `response_format` were left exactly as `337` §2 pinned them.
- **The grader fingerprint moved two minutes after the paid job, so the two
  pin assertions now ask the question that outlived the run.** `#455` merged
  at 09:50:53Z and this checkout computes `50f6f8bb…` where the run used
  `6970a67c…`. Neither document is re-pinned. `337`'s assertion now holds its
  §2 value against `pins.grader_source_sha256` in the paid artifact — after a
  run, the useful question is whether the document tells the truth about what
  dispatched, not whether it matches today's checkout. `338`'s branches on its
  status line: while it reads "안 샀다. 그리고 안 산다." the pin is held against
  `337`'s, and re-opening the document restores the freshness demand on its
  own. Dispatch-time enforcement is untouched — `measure_audio_grading_accuracy.py`
  still recomputes the fingerprint and refuses (exit 3) before calling the
  model, and the test covering that refusal is unchanged.
- **`337` and `338` — the two pre-registrations that take `334` §10's fourth
  item, written before anything was bought.** `334` asked whether the
  observation arm changes the judge's verdict and could not answer: the arm
  came back unreadable on 51 of 60 calls, so `p = 0.0654` measured a delivery
  failure. `335` bought the reason — `SPEECH_OBSERVATION_HEADER` opens with an
  imperative ("write down what it actually contains") that names no
  destination, while the response contract in the same prompt says no prose
  before or after the JSON, and the model obeyed the first one. The candidate,
  `SPEECH_OBSERVATION_HEADER_V2`, is that header with one 158-character
  sentence added as the last sentence of its first paragraph, naming
  `reasoning` as where the transcript goes: 1,774 → 1,933 characters (the
  sentence plus the space that joins it), `b9bfaaa2…` → `93239fe7…`, and a
  test deletes the sentence again and reconstructs V1 byte-for-byte. **The parser is not touched and
  `response_format` is not enabled** — the deployment returns `400` for both
  `json_object` and `json_schema` (`335` §11), and the parser type-checks only
  `verdict`, `partial_score` and `confidence`, so a transcript in `reasoning`
  needs no loosening to be accepted. `337` buys ten calls (five claims × one
  repeat × two arms) and passes only at candidate 5/5 with production ≥ 4/5;
  `338` buys the original comparison once, at the 120 calls `333` registered
  and `334` spent, and only if `337` passed. The two are not pooled, neither
  is re-run to move a p-value, and `334`'s published figures are unchanged.
  Zero model calls were made for any of this.
- **A per-kind ceiling on model requests, and a stop that keeps what it
  bought.** `SPEECH_REQUEST_CAPS` gives `337` twelve requests and `338` a
  hundred and twenty-six, against plans of ten and a hundred and twenty. The
  headroom for `338` is deliberately six: enough that a couple of stray
  requests do not lose the run, and far too little for a fourth repeat, which
  would need 160 — the "does not grow past 120" instruction as arithmetic
  rather than as a sentence. A plan larger than its ceiling stops before the
  first call. `RequestCapReached` is a `BaseException` on purpose, because
  `AudioPerception.judge` converts any `Exception` into a `judge_error` and
  continues to the next claim, which would turn a ceiling into a quiet stream
  of failures that each still cost a request; reaching it stops the run at that
  point, writes the partial record with `stopped` set, and exits 3. The
  historical `speech-prompt-ab` kind stays uncapped: an unregistered kind gets
  `None` and the check is skipped, so this adds no ceiling to a run that has
  already happened. **The count is of `chat.completions.create` invocations,
  not of HTTP requests** — `max_retries` is unset all the way down, so the SDK
  default of two applies and up to three HTTP requests can sit under one tick;
  a request that timed out may have been billed without being counted.
- **The probe workflow can dispatch the two new diagnostics, and routes each
  one to its own document.** `corpus` gains `speech-format-pilot` and
  `speech-prompt-ab-v2`, and both the free and the paid job select the
  pre-registration by corpus rather than by a single `if`. This is the one
  place the measurer cannot protect itself: it refuses a document that does not
  name a diagnostic kind, but a file that says `speech-prompt-ab` is a valid
  answer to a dispatch that asked for `337`, so a mis-wired path would have run
  40 calls under a document registering 120 with nothing to notice it. A test
  walks every kind in `SPEECH_TWO_ARM_REGISTRATIONS` through both jobs' argument
  blocks and checks each lands on its own file. The paid gate's approval record
  is corrected in the same place: it now derives the arm count from the list of
  corpora that open a second arm themselves — `prompt_arm` stays `production`
  for all three — and the criteria count per corpus, so `337` is recorded as 5
  criteria and 10 calls rather than the 20 and 40 the old literal would have
  printed, with a `narrowed` line so a five-claim run cannot be mistaken for a
  twenty-claim run that went wrong. Two tests execute that shell rather than
  reading it.
- **A response-rate stop rule, pre-registered before it was pointed at any
  run.** `330`'s `zero_response_after` stops an arm that never answers; it
  cannot reach an arm that answers *sometimes*, which is why `334`'s
  observation arm answered on its fourth call, failed 27 in a row, and still
  bought all 120. The new rule asks a different question, per arm, after every
  call: *if this arm were meeting the rate the design needs, how often would a
  window this thin happen?* It fires at `p ≤ 0.05` after a minimum of ten calls
  in that arm. The rate — 1/3 — is derived from the corpus, not from `334`'s
  failure rate: an exact one-sided binomial cannot clear α = 0.05 on fewer than
  five settled claims (`0.5**5 = 0.03125`), a claim needs two answered repeats
  to be settled, and 20 claims × 3 repeats reaches five settled claims at
  r = 0.3264, rounded up. `required_response_rate` recomputes it from those
  design parameters and a test pins the literal against the recomputation
  rather than against itself. Because it is an evidence gate and not a point
  comparison, at its minimum window of ten it fires only on zero answers —
  exactly where `zero_response_after` already fired — so it buys nothing new
  on its first opportunity and gains reach only as calls accumulate. The
  false-stop rate is measured, not assumed: ~14.6% for an arm sitting exactly
  at the requirement over 60 calls, under 2% at r = 0.5, zero at `334`'s
  production rate. It applies to runs after this commit and changes no
  published figure. `330`'s four registered values are unchanged.
- **A stopped run now records what it left unpaired, and what that forbids.**
  A stop lands between calls and the arms interleave, so the last claim can
  hold one arm and not the other. The run does not buy the partner call to
  tidy the record — that would spend the money the rule just declined — so
  `stopped.left_behind` names the claims instead, and carries the sentence the
  imbalance implies: a stop makes n depend on the data, so the run's
  pre-registered tests are no longer the tests that were registered. Do not
  report a p-value over the pairs that survived, and do not compare a stopped
  arm's accuracy with a complete one's. The workflow summary prints it beside
  the numbers, because the person about to quote a figure is reading that page
  and not the artifact.
- **`336-334-stability-reanalysed.json` — `334`'s stability figures under the
  corrected count, in a new file with its own fingerprint.** `334`'s artifact
  is opened read-only and is byte-identical; its published numbers stand as
  published. The re-analysis records the source digest, both readings side by
  side, and how each was counted. Observation `identical_across_repeats` 13 →
  2 (18 claims moved to "fewer than two answers", not to "differed");
  production 15 → 16. It also records where the new stop rule would have landed
  on `334`'s recorded call log — arm `observation`, call 26 of 120, one answer
  in 13 arm calls, `p = 0.0385`, 94 calls not bought — with the ordering stated
  in the field itself: the threshold was pinned before that replay was run.
  `334` was not re-run and is not being re-run; this is the rule's reach as a
  number rather than as a claim, and it is not a finding about
  `gpt-audio-1.5`. Zero model calls were made for any of the above.
  at all.** The eight-request diagnostic ran at commit `1e06e452` and used
  seven; `335-audio-format-diagnostic.json` holds the result. All three
  reproduce probes failed exactly as `334` recorded, and all three failed the
  same way: zero braces, zero code fences, `json.loads` stopping at character 0
  with `Expecting value` and the whole reply still unconsumed, none of the five
  contract keys present. Every reply that arrived carried `finish_reason:
  stop`, so these three were not truncated — read off the field itself, which
  is what `335` §7 said would have to settle it after `334` §3 inferred it from
  output token counts. No refusals, no reasoning blocks, and the collector
  agreed with core on all five. The two contrast probes returned clean
  five-key JSON from the same code against the same clips minutes apart, so
  the failures are not an artifact of the collector. Counts here describe a
  sample chosen *because* it failed in `334`; they do not estimate a rate.
- **Structured outputs are unavailable on this audio deployment, which
  `334` §10 left open and the documentation did not settle.** Both
  compatibility probes were rejected `400 invalid_request_error` on
  `param: response_format` — `'json_object' ... is not supported with this
  model` and `'json_schema' ... is not supported with this model`. Neither was
  re-sent without the rejected parameter: the rejection is the result, and a
  parameter-free retry reported as "supported" would be a fabrication. The
  reserved eighth request was therefore not spent, since a deterministic 400 is
  an answer rather than a lost response body.
- **A diagnostic that can see what `334` could not: the response bodies.**
  `334` reported that 51 of the observation arm's 60 replies were
  `format_error:unparseable_json` and stopped there, because that run stored no
  response bodies — `core.perception.audio` labels a malformed envelope and
  drops it, so the label was the only surviving fact.
  `scripts/diagnose_audio_format_failure.py` collects the structure instead:
  `finish_reason`, refusal presence, which field the text came from, code fence
  position and language tag, brace balance, where `json.loads` stopped and with
  what error, which of the five contract keys were present and of what type,
  and whether the collector's reading agrees with core's own. Registered by
  `335-why-the-format-failed.md` and run by
  `.github/workflows/audio-format-diagnostic.yml`, which has the same free
  dry-run, the same `grading` environment gate and the same OIDC identity
  preflight as the accuracy probe.
- **It is capped at eight model requests including retries, and the cap is
  enforced before each call rather than counted after.** Seven probes are fixed
  in the document — three reproduce the failure on the observation arm, two
  contrast against the production arm on the same claims, two check whether
  `response_format` is accepted alongside `input_audio` at all — and the eighth
  is reserved for a single transport-level retry. A failed request still counts,
  because a request lost to a timeout may have run. If the failure does not
  reproduce in the fixed sample, the run reports "not reproduced" rather than
  looking further:
  `test_one_judge_call_is_one_request_so_the_plan_length_is_the_call_count`
  asserts the arithmetic against the real `AudioPerception`, so a retry loop
  added to core later breaks the test instead of silently tripling the spend.
- **The sample is fixed, and the artifact says why that limits it.** The three
  claims were selected by a rule written before it was applied — every
  observation-arm claim that failed all three repeats in `334`, then the first
  three by `claim_id` on distinct clips. `test_the_fixed_sample_is_what_the_rule_selects`
  re-derives them from `334-audio-accuracy-measured.json` rather than trusting
  the constant. Because they were chosen for having failed, no count over them
  estimates a rate, and that sentence is stored next to every summary the run
  writes.
- **The collection rules are enforced by tests that need no credentials and
  place no calls.** 68 of them, against fabricated response objects: masking
  runs before truncation (the other order leaves the first 12 characters of a
  60-character key in the file), the 240-character limit cannot be raised from
  the command line, a non-string body is recorded as a type marker rather than
  through `__repr__`, a reasoning block leaves one boolean and nothing else, no
  model text reaches stdout, and a provider error message is masked before it is
  stored. Excerpts are off by default and go only to the committed report, never
  to a CI log.
- **Documentation on `input_audio` + `response_format` is inconclusive, and the
  document says so instead of guessing.** The Azure Foundry chat REST reference
  documents both in the same request schema with no stated interaction;
  OpenAI's audio guide never mentions structured outputs; OpenAI's
  structured-outputs guide never mentions audio. `335` §6 also names the trap:
  the Azure *audio* reference does have a `response_format`, but it is
  `audioResponseFormat` on `/audio/transcriptions`, a different parameter on a
  different endpoint. Two probes settle it by asking. A rejection is the result
  — there is no parameter-free retry path in the module, and
  `test_there_is_no_parameter_free_retry_anywhere_in_the_module` keeps it that
  way, because reporting a retry-without-the-parameter as "supported" would be
  a fabrication.
- Nothing under `core/` changed. Collection happens by wrapping the client core
  is handed, so core's request assembly, prompt and parsing all run unmodified
  and `compute_grader_source_hash` returns the same digest `333` §2 pins —
  verified with the new files present.

- **The pre-registered speech prompt A/B ran once, and the intervention broke
  the response format instead of the verdict.** `333` asked whether the
  grader's own prompt pushes it toward `fail` on speech. The paid run
  ([34117749459](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/34117749459),
  120 calls at `1583caf`) is preserved verbatim as
  `334-audio-accuracy-measured.json` and read in
  `334-the-arm-that-broke-the-format.md`. The design held — clip digests
  reproduced `330`'s manifest exactly, both arms got the same audio bytes and
  the same 1,848 audio tokens, and the prompts differed by exactly 739
  characters on every criterion — but 51 of the observation arm's 60 replies
  came back as `format_error:unparseable_json`, against 0 read failures in the
  control arm. The pre-registered primary test (20 paired criteria, exact
  McNemar) gives **p = 0.0654**, and the report says plainly that this p is
  mostly measuring *an arm that produced no readable verdict*, not two arms
  that judged differently. **The original question is still unanswered**, and
  the run was not repeated to chase a smaller p — `333` §7 forbade that before
  the numbers existed. Cost stays `null`: `gpt-audio-1.5` is not in the price
  table, and unmeasured is not zero.
- The control arm reproduced `331` closely on a moved grader fingerprint
  (0.627 vs 0.610 over the same 59 answered calls, identical audio tokens),
  which is recorded as a replication observation and explicitly *not* as this
  A/B's control — `333` §7 forbids using `331` as a concurrent control, and
  the report labels it a historical reference where it appears.
- `test_the_334_report_quotes_the_run_it_preserved` and
  `test_the_334_report_does_not_overwrite_what_331_bought` tie the report's
  headline figures to the JSON it was written from. Nothing else in the
  repository checked a result document against its own raw file.

### Fixed
- **`339` §11's call-count summary said 8 where its own run record said 7.**
  The line above it reads seven used with one spare unspent, and the artifact
  agrees; the summary is corrected to `7회 (상한 8회, 예비 1회 안 씀)`. The same
  table conflated `337`'s one readable envelope with its zero usable verdicts,
  which the body of `339` had already separated — corrected to name both. Only
  the summary wording changed; every measured figure in `330`–`339` is
  untouched, and the correction cites the originals it was checked against.
- **The record of what `333` and `334` actually varied: the observation arm
  changes the label in front of the criterion as well as the header above it.**
  `apply_arm` writes `Statement:` where production writes `Criterion:`. Both
  labels are ten characters, which is why `334` §1's "정확히 739자만 달랐다"
  could not see it — the difference is in the bytes, not in the count. **The
  code is not changed**: making the arms differ by one thing instead of two
  would mean `338` no longer runs the arm `334` ran, and the comparison would
  stop being a repeat of the registered experiment. It is pinned by a test,
  recorded in `337` §3 and `338` §3 as a limit, and the conclusion sentence has
  to read "관찰 갈래가" and not "머리말이". No published number changes; what
  changes is that the intervention is now described completely.
- **A claim nobody answered was being counted as a claim the repeats agreed
  on — and, in the other direction, one missing repeat beside two matching
  answers was counted as a disagreement.** `summarise` asked whether the three
  verdicts formed a one-element set, with `judge_error` an element like any
  other, so silence was read as evidence in whichever direction it happened to
  fall. `334`'s observation arm published `identical_across_repeats: 13` when
  all thirteen of those claims had never produced a verdict; its production arm
  published `15` when `column_second` (`judge_error`, `fail`, `fail`) had
  answered twice and answered the same way both times. The observation arm went
  13 → 2 without losing eleven claims: the published thirteen and the corrected
  two are disjoint sets. All thirteen left the comparison entirely and none
  became a disagreement, while both survivors are claims the old rule had
  called *not* identical — the key counts different claims now, not fewer of
  the same ones. `stable` is now three-valued — `None` means there was nothing
  to compare, and it is not `False` — and the published block carries
  `claims_with_two_or_more_answers`, `differed_across_repeats`,
  `claims_without_two_answers` and an `identical_share_of_comparable` that is
  `null` rather than `0.0` or `1.0` when no claim was comparable. The same
  omission in `repeat_flip_rate` is fixed the same way: a claim with no
  comparable pair no longer counts toward `claims_that_ever_flipped`, which now
  prints out of the new `claims_compared` rather than out of the corpus — the
  field that let `334`'s observation arm render "0 of 20" off two comparable
  pairs. `330` §4 had already written this rule for the *pair* denominator
  ("안 온 답은 일치도 불일치도 아니다"); this is
  the same sentence where the *claim* denominator was missing it. No key was
  removed and no run was re-executed. `334`'s primary metric is the per-claim
  majority McNemar `p = 0.0654`, which does not read the stability block, so no
  headline figure moves — recorded as `primary_metric_changed: false`.
- **`334` §3 inferred "not truncated" from output token counts, and that
  inference was not supported.** Token count is a proxy; `finish_reason` is the
  only field that settles truncation, and `334`'s run did not store it — so the
  honest reading of that data is "unknown", not "not truncated". The original
  wording is preserved with an explicit correction record beside it, and none of
  `334`'s numbers move: 51/60, 12/20 vs 5/7, p = 0.0654 and the 27-call streak
  all stand. The new diagnostic reads `finish_reason` directly and reports
  `unsettled` when it is absent rather than filling the gap with token lengths;
  `test_truncation_is_read_off_finish_reason_and_never_off_token_counts` uses a
  short reply with `finish_reason="length"` so the token-length argument cannot
  quietly return.
- **`zero_response_after` could not fire in a two-arm run, and that is why
  `334` bought 120 calls while one arm was silent.** The rule counted answered
  calls across the whole run, but a two-arm run interleaves the arms, so the
  healthy arm answering on call 1 made `answered == 0` false for the rest of
  the run — while the observation arm went 27 calls in a row without a
  readable verdict. The second arm was added in #445, so the defect is that
  change's. The rule now counts per arm and names the arm it stopped;
  single-arm runs are unaffected because their one group is the whole call
  list. **This is necessary and not sufficient, and the test suite says so:**
  `334`'s observation arm answered once on its fourth call, so even the
  per-arm rule would not have stopped it.
  `test_the_per_arm_rule_would_still_not_have_stopped_334` pins that limit so
  the fix cannot be read as a guarantee. Catching an arm that answers 15% of
  the time needs a response-rate rule whose threshold is pinned *before* a
  run; choosing one now, with `334`'s numbers in view, would be fitting the
  guard to the result, so it is left to its own pre-registration.
- None of this changes `334`'s numbers. The 120 calls are already bought and
  stored; stop rules affect acquisition only.

- **A second speech diagnostic is pre-registered, and nothing has been bought
  for it.** `331` measured one prompt and so could not separate "it did not
  hear the words" from "the question pushed it toward `fail`". This registers
  the run that separates them — the same ten clips and twenty criteria under
  two headers, 20 × 3 × 2 = 120 calls — as
  `333-speech-prompt-ab-prereg.md`, before any dispatch. `330`, `331` and
  their two raw reports are untouched; this is a new number, a new result ID
  and a new run.
  - **The second arm is opened by the document, not by `--prompt-arm`.**
    `330`'s single-arm rule stays exactly as it was: `--prompt-arm observation`
    or `both` with a speech set still exits 2 at argument-validation time. The
    A/B goes through a separate `--speech-prompt-ab <document>` door that only
    opens when the file itself says `진단 종류 = speech-prompt-ab`, because a
    path on a command line says nothing about what the file agreed to. The
    door reuses `--expect-grader-pin`'s fingerprint comparison rather than
    adding a second one, and a run that names both flags is refused.
  - **Repeats are no longer counted as extra criteria.** `compare_arms` now
    emits a claim-level comparison beside the call-level one, labelled
    `unit: "claim"` and `unit: "call"` so neither can be mistaken for the
    other. The collapse is `majority_verdict` then `classify` — the two steps
    `summarise` already uses, in that order, not a third scoring rule. 20
    criteria × 3 repeats is **20** paired units, not 60; the 60-pair test is
    kept as a secondary because delivery differences surface there first.
    `claims` is a required keyword argument, so the "defaults to the tone
    corpus and silently pairs nothing on a speech run" failure cannot recur.
  - **Every accuracy is printed beside what always answering `fail` scores.**
    With ten true and ten false claims that machine scores 0.50 / 1.00 on
    false / 0.00 on true / J = 0. `constant_fail_baseline` is recomputed from
    the claims actually paired, not typed in, so it cannot drift if the corpus
    balance changes. A criterion whose three repeats disagree is **unsettled,
    not wrong**: out of the accuracy denominator, still in McNemar's
    discordant count, and reported split into "never answered" and "answered
    without a majority" so flip rate cannot hide inside accuracy.
  - **The approval record counts the arms the document opens.** The gate read
    the arm count off `prompt_arm` alone, which would have authorised 60 calls
    for a 120-call dispatch — the `calls = 36` failure this workflow's own
    header describes, on the input that spends. It now resolves the corpus
    first, and a test runs the gate's shell to check both the two-arm and the
    one-arm arithmetic.
  - **The pinned fingerprint is this tree's, and the divergence is written
    down.** `#444` changed `core/cost_metering.py` and `core/cost_receipts.py`;
    `compute_grader_source_hash` hashes every `core/**` module by content, so
    the value moved to `7506ce50…c52b6168` even though the audio grading path
    did not change. `333` names `330`'s old `74e1f478…a558a90` and says which
    commit moved it, and a test holds the document to what this checkout
    computes for as long as it says it has not run. Nothing was loosened to
    make the old value fit; the run-time comparison still stops before the
    first model call.
  - **Structured output is still off.** `response_format` alongside
    `input_audio` remains unverified for this API/model pair, so the A/B
    inherits `331`'s format exactly — changing it here would make the two
    arms' format success rates unattributable.
  - **What has not happened.** No paid call, no dispatch, no allow-list
    change, no edit to the 185-run/31-item results or to any published score.
    `331` is not a control arm for this comparison — the control is the
    `production` arm running inside the same job — and the run is registered
    to happen **once**. Cost is `null`: `gpt-audio-1.5` is still absent from
    the price table.

- **The summary lines that had only ever run against money now run for free.**
  `331` §10 listed six follow-ups; this closes them without buying anything.
  No paid call, no edit to an existing number, and nothing under
  `batch-runner/core/` was touched — so the grader fingerprint
  `74e1f478…a558a90` is unmoved and `330`'s pre-registration still names the
  code `331` actually bought. Recorded as
  `332-the-lines-that-first-ran-against-money.md`.
  - **Four branches of the paid summary page are now executed by tests, not
    grepped.** A rehearsal makes every one of their conditions false — no
    unanswered calls, one arm, no digest conflict — so "only prints when
    something is wrong" meant "first runs after the money is gone". The tests
    pull the python heredoc out of the workflow's own `run:` block and `exec`
    it against a report on disk: the three-way `unanswered_by_kind` split (with
    deliberately unequal 5/9/16 counts, so a swapped label shows up as a
    number), the arrival usage row, the multi-arm note and paired table, and
    the two-digest banner. A grep proves a sentence is in the file, not that
    the branch holding it ever runs.
  - **The paid summary now prints `pins.grader_source_sha256`.** The value was
    already in the report; only the reading of it was missing, so "this is the
    pre-registered grader" was a sentence a reader had to take on trust while
    the model name and call count sat one line above. Printed whole, for
    comparison against the 64-character constant in the pre-registration.
  - **An out-of-vocabulary verdict can no longer be scored.** `classify()`'s
    `fail` arm was a plain `else`, so `true`, `false`, `refuse` and
    `analyze_audio` — the four out-of-vocabulary strings run `34008840627`
    actually produced — became confident `fail` verdicts,
    correct on every false claim. This reuses `core.perception.audio`'s own
    `AUDIO_VERDICT_VOCABULARY` and `_offending_token` rather than adding a
    second rule: core already rejects those replies on the wire, and this is
    the second reader of the same value. Unreachable today for exactly that
    reason, which is why it was silent.
  - **`--prompt-arm observation` with a speech set exits 2, and that is
    documented rather than removed.** The mechanism is `argparse`'s
    `parser.error()`, at argument-validation time — before a client exists and
    before anything is billable. The reason is that `330` pre-registers one
    arm; two questions in one run is what left 328 unable to answer either.
    Verified by running it: `observation` → 2, `both` → 2, `production` → 0.
  - **Structured output stays off and unverified.** `response_format` is still
    not sent; `core/audio_analyzer.py:108` and
    `test_no_structured_output_is_requested_until_it_is_verified` hold that
    decision. Nobody has observed `gpt-audio-1.5` accepting it alongside
    `input_audio`, and sending it to a deployment that rejects it turns every
    audio call into a 400. Turning it on requires either official evidence for
    that API/model pair or a separate minimum compatibility check — not a
    quiet swap of `331`'s comparison inputs, which would make the format
    success rate unattributable.
  - A fixture honesty note: adding the fingerprint line broke five existing
    tests with `KeyError: 'grader_source_sha256'`, because `pinned_identity()`
    does not carry it and `main()` stamps it. Fixed by making the fixtures
    build the shape a real run emits, **not** by adding a `.get()` fallback in
    the workflow — that would let the page render green without saying which
    grader produced the numbers.

- **The pre-registered speech diagnostic ran, and the answer was "not shown".**
  60 paid calls on run `34038371185`, pinned to commit `54180489e` (#439's merge)
  so a moving `main` could not change what the job saw. Results and both raw
  reports are preserved as `331-it-said-no-to-almost-everything.md`,
  `331-audio-accuracy-measured.json` and `-delivery.json`. What the run bought:
  - **The format failure is gone.** 328's tone run lost 43 of 120 answers to
    unparseable JSON and answered 17 more with words outside the verdict
    vocabulary. This run had **0 read failures, 0 provider failures, 0
    out-of-vocabulary answers** and a 98.33% response rate. That matters for
    what the numbers below mean: they measure the judge, not the parser.
  - **The pre-registered primary says nothing was shown.** Exact one-sided
    binomial on one majority verdict per claim: 12 of 20, **p = 0.2517**. The
    secondary within-pair permutation agrees — J = 0.2069, p = 0.125.
  - **61.02% accuracy is not quotable on its own.** The judge answered `fail`
    53 times out of 60. It got 30 of 30 false claims right — which is exactly
    what a machine that never listened produces — and 6 of 29 true claims. A
    constant-`fail` responder scores 10 of 20 on the registered primary; this
    run scored 12. `false_pass` was 0 and `false_fail` was 23, and the wrong
    fails carried mean confidence 0.863, so confidence does not separate them.
  - **2 of 10 pairs were told apart**, both of them confusable-numeral pairs
    (seventeen/seventy, fifteen/fifty). The other eight got `fail` on both
    sides. A third number-bearing pair (nine/four boxes) was *not* told apart,
    so "it heard the numbers" is an over-read of two pairs.
  - **Delivery is evidenced, comprehension is not.** All 60 requests carried
    audio, one digest per clip, `wav`/16 kHz/mono, `response_models` exactly
    `["gpt-audio-1.5"]`, 1,848 audio tokens against the pre-registered band of
    1,687–2,061, and prompt tokens correlated with clip duration at r = 0.849.
    Bytes arriving and being billed is not the model understanding them.
  - **Cost is `null`, not $0.** `gpt-audio-1.5` is absent from the price table,
    so `pricing_complete: false` and `estimated_cost_usd: null` on 60 billable
    calls. 1,848 is a usage count, not an invoice.
  - The one unanswered call was an honest `declined_to_judge`, kept distinct
    from read failures and provider failures by 329's three-way split rather
    than collapsed into "wrong".
  Two other runs are recorded and cost nothing: `34037363820` (rehearsal, no
  paid calls) and `34038055900`, where dispatching from a tag was **refused by
  the `grading` environment's branch policy** and the paid job was skipped. The
  policy was left alone — the tag was not added to the allow-list — and the run
  was re-dispatched from `main` at the verified SHA.

- **`330-speech-diagnostic-prereg.md` now states it was executed.** Only the
  status header changed, and it links to `331`. The body — including sentences
  reading "아직 아무것도 안 샀다" — is left exactly as written before the spend,
  because a pre-registration edited after the fact is not one. The grader source
  fingerprint `74e1f478…a558a90` did not move across #439 or #440, so the
  registered conditions still describe the code that ran and no existing result
  needs segregating.

### Changed
- **A guard that grepped for a line broke while the property it guards stayed
  true.** `test_the_tone_corpus_runs_without_stop_rules` asserted the literal
  `stop_rules=SPEECH_STOP_RULES if speech else None` was present in the
  measurement script; adding the metering branch rewrote that expression and
  failed the test, though the tone corpus still got no stop rules and no
  published number moved. The decision is now `stop_rules_for(metering=,
  speech=)` and the guard **calls** it for all three inputs — and, because a
  correct decision nothing calls is the failure a grep also cannot see, a
  second test runs the tone path through `main` with `run_measurement`
  captured and asserts the argument that arrives is `None`. **`metering` is
  answered before `speech`**, since a metering run is a speech run too and
  `342` §5's ten-minute clock has to beat the twenty-minute one it derives
  from.
- **The paid summary printed both halves of a model-identity check and did
  neither half.** Its header states the model 330 §2 pins; a table row four
  hundred lines down lists what actually answered. Nothing compared the two, so
  a reader was expected to hold both strings in their head. An Azure deployment
  can be repointed at a different model without its name changing, and a run
  answered by a different model is not less accurate — it is a different run
  than the registered one, which no accuracy figure repairs. A foreign name now
  gets a banner above the numbers it disqualifies. The comparison was grounded
  on the real paid run `34008840627`, whose delivery block reads
  `"response_models": ["gpt-audio-1.5"]` — the pin exactly, no version suffix —
  rather than on a guess about what Azure returns, because a check that cries
  wolf on every run is worse than no check. Both wolf-crying directions are
  pinned by the test: a rehearsal answers `stub-not-a-model` by design and stays
  quiet, and a run where *nothing* answered (`[]`) is a measurement that did not
  happen, not an impostor — the same "not measured is not something else" rule
  as the row below it. Mutation-checked three ways, one per direction.

- **The summary put `None` in the cell that decides whether the audio judge can
  hear.** Rendering the paid summary against a run where no call was answered —
  the shape 330 §3's second stop rule exists to produce, and the shape run
  `34008840627` actually had 52 times — printed `**None**` for Youden's J and
  again for the pre-registered binomial p, plus three more rows. `None` is
  Python's repr leaking into a table a person reads, and it landed in the one
  cell where it is dangerous: a discrimination of **0** is this diagnostic's
  headline finding, the thing "판별력 0 → 못 믿음" is about, and a run that
  measured *nothing* was one glance from being recorded as having measured zero.
  The same three-state discipline the delivery line was fixed for, in the row
  that carries the conclusion. All six rows now say `not measured`, including
  the accuracy row that had been saying `n/a` — one table, one vocabulary for
  one condition. Rehearsals answer every call, so none of these rows had ever
  rendered without a real number in them; the test builds a judge that answers
  nothing, executes the workflow's own summary code, and asserts the word `None`
  appears nowhere in the output, then asserts the healthy run still prints
  `1.0`. Mutation-checked four ways, including the one that matters: making the
  helper return `0`.

  Nothing was wrong with the stop-early banner, which is worth recording because
  the check was not free. Its test grepped the workflow text, and a grep cannot
  see a `KeyError`; the branch is skipped on every rehearsal, so its first
  execution would have been a paid run that aborted. Executed against a real
  stopped run it behaves: the rule name, the shortfall and the reason all
  render, above the table they qualify. The regression test now asserts the two
  counts stay distinguishable — `1` bought against `30` planned — because a
  summary that prints the same figure twice says a partial run went to plan.
- **The audio judge accepted answers that were not verdicts, and scored them as
  `fail`.** Replaying the 120 stored responses from run `34008840627` offline —
  no new API call — the observation arm's published "47.1% accuracy over 17
  answers" turns out to have been computed over 17 replies that never contained
  a verdict: 13 said `true`, 2 `false`, and one each `no`, `refuse` and
  `analyze_audio`. Anything that was not `pass` counted against the deliverable,
  so a model answering *correctly* in the wrong vocabulary was scored as having
  said the criterion did not hold. Under the strict contract that arm answered
  **0 of 60** (response rate `0.283` → `0.000`); the production arm goes
  `51` → `50` answered, and the arithmetic closes exactly against the per-arm
  format-failure counts.

  Three things changed. **One contract, shared byte-for-byte**: both A/B arms
  ended with their own hand-written paragraph asking for JSON, which made any
  difference in response rate unattributable to the prompt under test; both now
  append the same `AUDIO_RESPONSE_CONTRACT`. **Strict validation**: an
  out-of-vocabulary string, a missing `verdict`, a non-string `verdict`, and
  unparseable JSON all raise `AudioEnvelopeError` and surface as
  `format_error:<kind>` instead of defaulting to `fail` — including
  `"partial_score": true`, which without an explicit `isinstance(raw, bool)`
  guard would have scored 1.0, since `bool` is an `int` in Python. **Three-way
  separation of non-answers**: `declined_to_judge` (the model said so),
  `read_failure` (the reply broke the contract) and `provider_failure` (the call
  failed) are counted apart and reported beside the accuracy denominator. All
  three stay out of the accuracy denominator — only the diagnosis differs — and
  an unlabelled non-answer falls to `provider_failure`, the reading that claims
  least about the model.

  No verdict is remapped after the fact: the observation arm answered nothing,
  so whether that prompt is better or worse remains **unknown** rather than
  quietly re-scored into a new result. `response_format` stays off until a probe
  confirms `gpt-audio-1.5` accepts it alongside `input_audio`, pinned by
  `test_no_structured_output_is_requested_until_it_is_verified`.

  This moves the grader fingerprint —
  `ed3fcd56…` → `8bb8360a…`. The existing 185-run / 31-item grades are kept as
  they are: not overwritten, not retroactively re-graded, and distinguishable by
  the hash. No grading run was in flight. Full account in
  [`329`](tasks/rebuilding_grading_task/329-the-verdict-that-was-never-a-verdict.md).

- **The grader's fingerprint covered half of its own install graph.**
  `compute_grader_source_hash` hashed `batch-runner/requirements.txt` and stopped
  there. That file's fourth line is `-r requirements-renderer.txt`, and the
  included file is where `PyMuPDF`, `openpyxl`, `python-pptx`, `python-docx` and
  `Pillow` are declared — every one of them a capability the judge's
  `read_deliverable` needs in order to see a deliverable at all. Measured at
  `af0f001` with `gold_ceiling_185_v2_sol_max.yaml`: touching the entry file
  moved the fingerprint, and **deleting `PyMuPDF>=1.21.0` from the included file
  did not**. Two graders that could not read the same PDFs claimed the same
  identity, and a shard merge compares exactly that value before joining
  partials.

  The hash now walks the include graph the way pip does — `-r`, `-c`,
  `--requirement`, `--constraint`, in every spelling pip accepts, with comments
  stripped by pip's rule (a `#` at line start or after whitespace, which leaves
  `#egg=` fragments alone), diamonds hashed once and cycles terminated. It fails
  closed: an include that is missing, symlinked or outside `batch-runner/` raises
  and names the file that asked for it, because a fingerprint that quietly
  skipped a file pip reads would be the same defect wearing an exception handler.
  Files hashed go **108 → 109**, and the fingerprint moves as intended —
  `gold_ceiling_185_v2_sol_max.yaml` `06a1b80c…` → `fbffad9c…`,
  `default_v2_sol_max.yaml` `1a46fc66…` → `85aadf17…`.

  The same file list is mirrored in four places, and **all four read the graph as
  a single file**: the hash itself, the merge-freeze predicate in
  `check_grader_hash_freeze.py`, the `paths:` filter in `grader-hash-freeze.yml`,
  and the input pin in both copies of `grade-run.yml`. The first two were caught
  by existing coupling tests that went red on their own. The fourth was not:
  `test_the_pin_covers_everything_the_source_hash_covers` documented itself as
  "derived from the real hash function, not from a list typed twice" while its
  body was a list typed twice, so a pull request touching only the include could
  have merged into a live grading run. That test now spies on what the function
  actually reads.

  Timing, stated rather than assumed: this was held open as an owner decision on
  the sole ground that fixing it moves the fingerprint. That cost is currently
  zero — #419 moved the fingerprint earlier the same day and no run was
  dispatched at `06a1b80c…`, so deferring would mean paying the same price
  twice. Follow-up 9 in `tasks/rebuilding_grading_task/PR3_REPORT.md` is struck,
  and `321-the-question-the-probe-asked.md` keeps the original deferral text with
  the reversal appended. 32 new contract tests, 16 of 16 planted mutations
  caught, **no model calls and no cost**.
- **Three follow-ups that named a gap kept naming it after the gap closed.**
  PR3's follow-up list carried items 1, 2 and 3 — Word/PDF page geometry,
  listening inside an archive, and the empty-read disclaimer — as open, with
  point estimates of roughly 15, 20 and 13 attached. All three were delivered by
  #260 (`df473c0`) on 2026-08-29. They read as open for five days because that
  PR's closeout moved two Project cards and never touched the report; items 4
  and 7 were struck when they closed, and 1–3 were not, since nothing tied the
  sentence to the code.

  The two paid gold-ceiling runs sit either side of #260 — 30 tasks graded
  2026-08-28, 185 tasks graded 2026-08-31, sharing 30 task ids — so the closures
  are recorded as measurements rather than as a reading of the diff:

  - **Follow-up 1** flips on the same task and the same sentence. `f9a1c16c`'s
    *"PDF page orientation is landscape"* went **fail 0/2 → pass 2/2**, with the
    judge's evidence moving from `"kind": "pdf", "page_count": 1` to
    `"orientation": "landscape"`. The answer was landscape both times; the page
    geometry was simply invisible. No perception call was made in either run.
    The `.docx` half of the item has never been exercised — neither payload
    contains a `.docx` structure inspection at all.
  - **Follow-up 2** delivered the capability and not the estimate. On `38889c3b`
    the items routed to listening went **0 → 10** and listening calls **0 → 6**,
    matching #260's replayed prediction exactly. Those ten items scored
    **8.5 → 9.0 of 18.0**, a gain of **+0.5** against an estimate of ~20.2. The
    task's **+5.97pp** must not be credited here either: of the 28 shared tasks
    whose routing did not change, the mean move was +1.62pp with a standard
    deviation of 1.89pp and a **maximum of +5.83pp**, so the audio task's total
    sits inside the spread of tasks nothing touched. The payload gives the
    reasons — three of the ten were answerable from the WAV header and already
    passed, one routed to audio and never called, and three of the six that did
    listen were judged against 1:22–1:49 criteria from a clip ending at 0:30, a
    separate limit closed afterwards by `f514d05` (#374).
  - **Follow-up 3** reaches the judge: the disclaimer appears in **0** rubric
    items before #260 and **23** after. It cannot be separated into a score.

  So the third of the three paths offered before stage 3 — "fix the remaining
  tool defects first and recover about 46 points" — was in fact taken, and the
  46 points did not arrive: the same 30 tasks moved **82.87% → 83.48%**. The
  estimates are marked in the report as replaced by measurement, and
  `tasks/rebuilding_grading_task/320-three-gaps-that-closed.md` carries the
  item-by-item comparison.

  Fixing the three sentences alone would leave the same hole open for the next
  item, so each numbered follow-up is now registered against a model-free
  **probe** that runs the capability it asks for:
  `probe() is True` requires the item to be struck through, `probe() is False`
  requires that it is not, and both directions fail. Items 5 and 6 ask the owner
  to decide rather than for code to exist and are exempt — an exemption pinned to
  exactly `{5, 6}`, with every number in the document required to appear in one
  of the two registries, so a newly numbered item turns the suite red until it is
  classified. 20 of 20 planted mutations were caught; two of them found real
  weaknesses in the probes themselves (a substring test that still matched a
  renamed symbol, and a heading match that a renamed heading slipped past). A
  further check requires every `./NNN-*.md` link in these documents to resolve to
  a *tracked* file, because `tasks/rebuilding_grading_task/*` is ignored by
  default and a note added without a `!` negation is correct only in the
  worktree that wrote it.

  Writing probe 1 turned up what looked like a second half of the same gap, and
  it was recorded as **follow-up 8, open**: `_op_inspect_formatting`'s PDF branch
  has no fallback, so on `ImportError` it returns
  `{"kind": "pdf", "note": "PyMuPDF not available"}` with no geometry and no
  fonts, and PyMuPDF is declared in `requirements-renderer.txt` rather than in
  `requirements.txt`. **That reading was wrong, and is corrected below.**
  `requirements.txt` pulls the renderer file in with `-r` on its fourth line, so
  every workflow that installs it installs PyMuPDF too. Probe 8 did not follow
  the include, so it reported a shipped capability as an open gap. Both the item
  and the probe are fixed in the same release;
  `tasks/rebuilding_grading_task/321-the-question-the-probe-asked.md` carries the
  evidence.

- **A probe answered its question correctly and still gave the wrong answer.**
  Follow-up 8, opened above, claimed `inspect_formatting`'s PDF branch returned
  `note: "PyMuPDF not available"` in every environment this repository runs,
  including both paid gold-ceiling runs. It does not. `requirements.txt` line 4
  is `-r requirements-renderer.txt`, and that file declares `PyMuPDF>=1.21.0`;
  the include and the declaration arrived together in `fa8bf4f` (2026-07-15),
  six weeks before either paid run. `backend-tests.yml`, `grade-run.yml`,
  `batch-run.yml` and `audio-accuracy-probe.yml` all install `requirements.txt`,
  so all four install PyMuPDF.

  The stage-3 payload confirms it from the other end. Three items cite a PDF font
  list, and `ae0c1093`'s evidence reads
  `"page_size_uniform": true, "orientation": "portrait", "fonts": [...]` — the
  fitz branch's exact return shape, which `_inspect_pdf` never produces because
  it emits `metadata`, not `fonts`. On `788d2bc6` that font list decided a
  verdict (*"No more than two distinct font families are used across the deck"*,
  failed against seven). Stage 1 shows no such evidence not because the
  capability was missing but because none of its 1,433 rubric items asked about a
  font; stage 3 asked in 11 of 8,715.

  What was defective was the question the probe asked — "is this package named in
  this file", where the shipped behaviour depends on "does `pip install -r` end
  up installing it". The requirements reader now walks the `-r` / `--requirement`
  chain the way pip does, breaks include cycles, strips comments by pip's rule,
  and **raises** rather than returning `False` when an included file is missing,
  since a broken install graph is a different finding from an absent package.
  That behaviour is pinned by its own regression: two packages `requirements.txt`
  does not name (`PyMuPDF`, `openpyxl`) must still be visible through the
  include, and the test fails loudly if either is later named directly, because
  it would then no longer distinguish a reader that follows `-r` from one that
  does not.

  Follow-up 8 is struck. The remaining asymmetry between the two `_pdf_geometry`
  call sites is documented and deliberately not changed: the branch does not
  execute in any environment we run, closing it would move the grader
  fingerprint, and the two engines do not agree on fonts (measured on one 2-page
  PDF, page rects match exactly while PyMuPDF reports a declared font pdfplumber
  does not), so a fallback filling the same `fonts` key would make one field name
  mean two things by environment.

- **The grader identity makes the same one-file-for-a-graph move, and is now
  registered as follow-up 9, open.** Found while proving the correction above did
  not move the fingerprint. `compute_grader_source_hash` hashes
  `requirements.txt` and not the `requirements-renderer.txt` that
  `requirements.txt` includes, so the identity both paid runs are pinned to does
  not cover the declaration of `PyMuPDF`, `openpyxl`, `python-pptx`,
  `python-docx` or `Pillow` — every package the judge's `read_deliverable`
  depends on. What the judge can see could change while the identity says
  nothing did, and that identity is what a merged shard set and a published grade
  cite. Measured rather than read off the source, at `94ea015` with
  `gold_ceiling_185_v2_sol_max.yaml`: deleting `PyMuPDF>=1.21.0` from the
  included file leaves the fingerprint byte-identical at `7b2bd7d9…`, while
  appending a single comment line to the entry file moves it to `0247c9e0…`. The
  hash reads 108 files and none of them is an include target. **Not fixed** — the
  fix lives in `step8_grade.py` and would move the fingerprint of every run after
  it, which costs merge freezes and reproducibility, so it is left as an owner
  decision. Probe 9 holds that state by observing which files the hash function
  actually reads rather than grepping the source for a filename, since grepping
  for a filename is precisely what went wrong in follow-up 8. It also restores a
  live `False` case to the contract, which item 8's closure had removed; the
  explicit negative control over the comparison rule stays regardless, because
  item 9 will close one day too. No model calls; grader source untouched.

- **A way into an archive that only one of two schemas mentioned.** PR3 follow-up
  4. A stage-1 gold answer — five WAV stems inside one `.zip` — scored 2 of 62
  because thirty-four rubric items were answered "binary or unsupported" about
  files nothing had opened. The re-run recovered **39.8 points** (→ 41.80/62),
  and PR3 recorded the outcome and the caveat together: the judge found the
  member scope *by itself*, in a `note` returned by `inspect_formatting`, so this
  was booked as a reproducibility item rather than a defect — "it worked, but
  nothing made it work."

  The fix was to say it where the judge is looking, and by then three of the four
  places did: the structure listing, the text read, and
  `MODEL_READ_DELIVERABLE_TOOL_SCHEMA`, the schema the judge is actually handed.
  The fourth did not. `core/tools/read_deliverable.py` describes `scope` twice,
  and the other one — `READ_DELIVERABLE_TOOL_SCHEMA`, exported from `core.tools`,
  which this changelog's own entry for that file offers as "ready to drop into
  Responses API `tools=[...]`" — said nothing about a member. A caller who took
  that at its word got a model that could reach every file in an archive and was
  told about none of them: the 2-of-62 answer, reintroduced one export over.

  Both descriptions are now composed from one `_SCOPE_MEMBER_CONTRACT`. The
  string the judge receives is **byte-identical to before** — verified by
  evaluating the old literals out of `git show` — so the grading prompt does not
  move, and only the six-op export gains text. The comment on `_ZIP_MEMBER_HINT`
  claimed the fact was said "in all three places" including the schema; it was
  said in two, and now says which two.

  Nine tests find the schemas **by shape rather than by name**, so a third one
  added later is held to the same contract instead of quietly becoming the next
  place it is missing; one of them pins the sweep itself against matching
  nothing. Two checks are needed for one claim: the built dict must *contain* the
  constant, and the source must *refer* to it — at runtime a hand-written copy
  and a reference are identical bytes, and the hand-written copy is what drifted.
  13 of 13 planted mutations were caught, including that one. Grader source hash
  moves `fc1fe6a9…` → `726b2c38…` (`default_v2_sol_max.yaml`); no grade run was
  in flight. No model calls, $0.

- **The published grades index carried an amount nobody ever measured.** Sixteen
  of the nineteen rows in `public/generated/grades-index.json` said
  `summary_v1.cost.estimated_cost_usd: 0`, and every one of them said it beside
  real tokens — the largest next to 130,092,056 input and 5,523,697 output
  tokens across 8,904 judge calls. Those runs did not cost nothing; nobody could
  price them, because the judge they used is deliberately absent from this
  repository's price table. `scripts/aggregate-grades.mjs` spread the legacy
  payload's summary into the record unfiltered, two lines above the receipt path
  that already gets this right ("Absent here is what the dashboard reads as 'no
  record' — never as $0").

  The spread now goes through `projectLegacySummary`. No payload is rewritten —
  the sixteen zeros stay on disk exactly where they were written; what changed is
  what the build is willing to republish from them. The exemption is the
  contract's own (`batch-runner/core/cost_receipts.py`: the only real $0 is a
  path that never contacted a provider), asked of the block itself: a zero
  survives only when `total_judge_calls`, `total_input_tokens` and
  `total_output_tokens` are all present and all zero. A *missing* counter is not
  a counter that read nothing, so a block with no counters normalises — fail
  closed on the evidence for the exemption, the same reasoning one level up from
  the amount. Unrecorded becomes `null`, not absent: `undefined !== null` is
  true, so dropping the key sends a reader guarding on null into `.toFixed` on
  `undefined` (`scripts/cost-receipt.mjs:711-716`).

  The same spread also carried a payload's own run-level `summary.grading_cost`,
  which the line below it overrides only when this build derived one — and
  `summarizeCostReceipts` returns null the moment no task carries a receipt. Not
  live on any published file, but it is the other half of the section's own rule
  that a run summary is derived from the rows, never copied. Both are dropped
  there now.

  Measured across the regenerated `public/generated`: 16 field differences, all
  `0 → null`, plus one `_generated` timestamp per other file — 23 in total, with
  no token, call, latency or key-order change anywhere. No index row publishes a
  numeric amount. `scripts/__tests__/a-zero-beside-real-tokens-is-not-a-price.test.mjs`
  (14 tests) pins that on the real corpus and holds the genuine-$0 exemption
  open; 12 of 12 planted defects were caught. Frontend generator and docs only —
  no `core/` change, so no grader fingerprint moved. No model was called.
- **A grading config could ask for tiered judging, be credentialed for it, and
  be graded without it.** Task 207 removed the tiered judge, and an earlier
  entry below recorded a decision to leave
  `core.azure_ai_clients.grader_route_workloads` enumerating `tier_standard` /
  `tier_pro` / `tier_mini` on the grounds that the branch was "unreachable
  rather than permissive" — the `Grader` was said to reject the configs that
  reach it. That reading was wrong. `Grader` rejects a config only for
  *lacking* `judge.tools.read_deliverable`; it never looks at `judge_routing`.
  A config carrying both therefore passed `validate_grading_config`, had its
  two or three tier deployments added to the Azure allowlist `azure/login`
  federates for, and then graded every item on the single main judge. The
  operator reads a tiered config and a green run; the run was not tiered.

  Deleting the enumeration on its own would have kept that config valid and
  merely stopped crediting deployments the run could not use — a narrower
  boundary and a quieter one. So `grader_route_workloads` now *refuses* any
  config carrying a `judge_routing` key, before the provider check so that a
  non-Azure judge cannot carry the block through unremarked, and however empty
  the block is: a key nobody reads is a belief about routing, and the belief is
  the failure. `validate_grading_config` calls this function, so the refusal
  lands at the entry point every run passes through, before spend.

  This clears the last live hit of task 207's acceptance grep in
  `batch-runner/core/`. `tests/test_the_tier_names_are_gone_from_the_grading_core.py`
  re-runs that grep and requires every survivor to be one of the two carve-outs
  PR3 documented — the `_archive_v1/` directory 207's own instruction created,
  and lines that name a removed knob without assigning it — plus a check that
  the archive stays undispatchable and that no shipped config carries a legacy
  key at any depth. Shipped configs and published grades are unaffected: none
  carries `judge_routing`. The grader source hash moves with any `core/` change
  (`default_v2_sol_max.yaml`: `13cf75f8…` → `fc1fe6a9…`), so this merged with no
  grade run in flight. No model was called.
- **"필수 항목 통과율" was never measuring required items, and it decided a
  pass gate anyway.** The rubric's own `required` field is `null` on all 10,453
  items across all 220 tasks, so `core/grader.py` substitutes
  `abs(max_score) >= 4`. That substitute was published as the headline
  "Critical Items (weight ≥ 3)" — a label wrong three ways: nothing marks these
  items required, the threshold is 4 rather than 3, and it reads the score
  magnitude rather than any weight field. Owner decision of 2026-09-03, priced
  first by `scripts/analyze_required_item_definition.py` and recorded in
  `data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`.

  **The threshold does not move and no grade file is rewritten.**
  `MAGNITUDE_THRESHOLD` stays at 4, `core/**`, `step8_grade.py` and
  `schemas/grade.schema.json` are untouched — so no grader fingerprint moved and
  no published run is restated. The JSON keys keep their published names
  (`critical_item_pass_rate`, `critical_fail`, `item_counts.critical_items`),
  because renaming them would break every reader of every payload written so
  far. What changed is the name a human reads, and what the number is allowed
  to decide.

  - `scripts/analyze_gold_ceiling.py` gates on two things now, not three: mean
    score and judge error rate. The rate moves to a `diagnostics` block that
    prints its own denominator and states plainly that it does not decide the
    stage. Exit codes are unchanged on both gold corpora — stage 1 (mean
    82.87%) and stage 3 (mean 79.53%) already failed on mean score, so nothing
    that failed before passes now.
  - The dashboard card is renamed *High-magnitude item pass rate (|max score| ≥
    4)*, moved out of the headline row into a dashed diagnostic card below the
    heatmap, and stripped of its WOW badge. `CriticalItemCard.tsx` →
    `HighMagnitudeItemCard.tsx`; the decision itself lives in the import-free
    `src/components/wow/highMagnitudeReading.ts` so a node test can execute it.
  - The sector heatmap's column header said `Critical ≥3` while the code
    thresholded at 4. It now says `High-mag ≥4`, and any cell whose denominator
    is unrecorded, empty, or under 20 items is greyed out with the reason on
    hover instead of painted red.
  - **An empty denominator reads "not recorded", never `0%`.** Measured on this
    repository's own grades with #393 merged in: **83 published sector rows**
    carry the rate, of which #393 recovered a denominator for 62 — the other 21
    still publish a bare rate with nothing behind it. **4 of the 62 counted no
    high-magnitude item at all**; those printed `0.0%` and painted the heatmap
    bright red for a run that measured nothing, and they now read "not
    recorded". A further 21 counted between 1 and 19, and 37 counted 20 or
    more. 13 sector rows read exactly `0.0`, and recomputing the count straight
    from the item data settles all 13: **4 counted nothing, 9 counted 1–19, and
    none reached 20.**
    The 61 shard payloads, whose rates are published nowhere, say the same at
    scale — 364 rows, 155 zeros, split 41 and 114, none at 20, none carrying a
    denominator. Run level is the same shape: 33 published payloads publish the
    rate and 22 carry `item_counts.critical_items` (1 of them zero, 14 under
    20). The 20-item floor is derived rather than chosen:
    `ceil(1 / (1 − 0.95))`, below which one item moves the rate further than
    the whole distance from the reference to a clean sweep.
  - `scripts/__tests__/high-magnitude-label.test.mjs` pins all of it — the two
    constants against their Python sources, the absence of the heuristic from
    `gates`, the banned labels across every rendered `src/` surface, and the
    five states of `readHighMagnitudeRate`.

  The residual this entry recorded — `core/narrative_analyzer.py` still writing
  "Critical item pass rate" into the report prompt — is closed under **Fixed**.

### Added
- **The accuracy probe can now run the speech fixture, and stops when 330 says
  to stop.** The fixture landed pinned but unrunnable: the measurement script
  only knew the nine synthetic tone clips, so a `corpus: speech` dispatch had
  nowhere to go. It now loads `330-speech-verification-manifest.json`, rebuilds
  the clips from eSpeak NG on the runner, and refuses to measure anything whose
  SHA-256 does not match the committed pin — in both the free and the paid job,
  before either spends. Agreeing with the pin is what makes two directories the
  same audio; travelling together in an artifact is not.

  Two defects surfaced in the wiring, both of which would have produced a
  confident wrong reading. The delivery record built its duration table from the
  *tone* clips whatever corpus ran, so a perfectly healthy speech run would have
  listed every clip under `clips_whose_sent_duration_differs` and reported
  `prompt_token_vs_clip_seconds.n == 0` — the delivery block readers are told to
  check *before* trusting the accuracy would have said the audio never arrived.
  And the record counted the calls that reported audio tokens without ever
  totalling them, which is the number 330's stop rule turns on.

  `audio_tokens_total` is `null` when no call reported the field, not `0`. A
  zero is a claim — *the provider metered no audio* — and it must not be
  indistinguishable from the provider never having said.

  A third instance of the same bug, and the worst of the three: `summarise()`
  built its per-claim table by iterating the *tone* claim list. Speech claim
  ids do not intersect it, so `by_claim` came back empty, `stability.claims`
  read `0`, and `discrimination_j.per_claim_majority` had nothing to compute
  from — while every per-call figure looked healthy. 330 §4 names the majority
  vote as the **primary** analysis, so the number the run exists to produce is
  precisely the one that would have gone missing, after the money was spent.

  And the primary significance test did not exist at all. §4 pre-registers an
  exact binomial on majority verdicts (n = 20, p = 0.5); the report computed
  only a within-pair permutation test, whose floor is 1/1024. Reporting the
  permutation p afterwards as "the pre-registered result" is exactly the
  after-the-fact substitution the document was written to prevent, so both are
  now computed, both are named in §4 before either has a value, and the summary
  labels which is primary and which is secondary. A `partial` majority leaves
  the binomial's denominator rather than being rounded into whichever side is
  convenient, and `n` is printed beside the p so a shrunk denominator is
  visible.

  Two of §4's secondary metrics were promised and not computed. The repeat
  disagreement was to be "comparable with the 19.35%" measured on the graded
  audio cohort, and the dispatch description said so too, but 19.35% is flips
  over *pairs of runs* and the report carried only `identical_across_repeats`,
  whose complement is the share of claims that flipped at all. On three repeats
  a claim that flips once is 33% of the first figure and 100% of the second, so
  the obvious division would have been printed beside 19.35% as a change in
  steadiness that never happened. `repeat_flip_rate` computes the pairwise one
  — 20 claims × 3 pairs = 60 — and both are shown with the claim-level figure
  marked as a different denominator. Pairs where a repeat never answered leave
  the denominator and are counted separately; nothing to compare reports null,
  not 0%, which would claim the repeats agreed. And §4's pair consistency ("둘
  다 `pass`면 안 듣고 찍은 것") had no count: Youden's J summarises it as a
  difference of rates and cannot say *how many* pairs were never separated.
  `pair_consistency` reports pairs told apart, pairs given the same verdict on
  both sides and which verdict that was, and pairs missing a side. Ten pairs of
  `pass` still scores 50% on this balanced corpus, which accuracy alone reads
  as a near miss.

  And the response rate was in the artifact but not in the summary a person
  reads, beside the accuracy §4 says it must never appear without. 328's
  observation arm published 47.1% on 17 answers; the paid table now prints the
  answers the accuracy was computed from and the rate, so that run would have
  rendered as `n/a`, `0`, and `0.00%`. Both are this arm's, like the accuracy —
  the run's call count stays sourced from the cost block, which an existing
  test keeps separate because a `both` run scores one arm and calls two.

  The seventh was that nothing stopped the answer reaching the model. The
  manifest has to carry the sentence eSpeak was given and why each claim
  holds, or the set is not reproducible — so for the whole run the ground
  truth sits one attribute access away from the prompt. A judge handed it
  answers all twenty correctly and the report says the model hears words;
  the run does not fail. The argument list is now pinned instead of the
  prompt text, which §6 keeps unpublished: `judge()` takes `criterion` and
  `audio_path`, and a third keyword fails the test. The corpus was audited
  the same way — no criterion states its own truth value or quotes its
  transcript, and each pair differs by one confusable word on the same clip.

  The eighth and ninth are both the report saying more than the run can
  support. §4 reads "solves the other families but not these three" as *hears
  words, not sentences* — but `binding` and `negation` hold two claims each, so
  they can only score 0, 50 or 100%, and 100% is two coin flips landing heads
  (p = 0.25) printed as a discovery. The family sizes are now written into the
  document beside the accuracies each can produce, taken from the manifest and
  kept honest by a test, and that reading is restricted to `order`, the only
  one of the three with four claims. Then the delivery checks: §2 says to read
  them *before* trusting the accuracy, and the paid summary printed them sixty
  lines below it. §3's fourth stop rule covers audio metered at a real `0`. It
  does not cover a request that carried no audio part at all, and it does not
  cover a clip that is not the pinned length — `WireClient` records both and
  deliberately does not raise, because a diagnostic that dies on the defect it
  exists to find cannot describe it. The result is a complete sixty-call run
  with a headline number and the evidence against it far enough down the page
  to miss, which is 324 exactly. The count of requests that actually carried
  audio now prints in the row above the accuracy, with a banner when either
  check fails saying that whatever the number below describes, it is not this
  model hearing these clips. The detail stays where it was; only the line that
  decides whether to read on moved. A test pins the order.

  The tenth is the summary page saying what the design can do, computed from
  the wrong test. The pre-registration names the binomial primary and the
  within-pair permutation secondary, and their floors are not the same kind of
  number: the permutation's is fixed by the pair count at 1/1024, while the
  binomial's is 1/2^n and *climbs* as hedged majorities leave n. At n = 4 the
  primary's floor is 0.0625, and the page — computing from the permutation —
  announced "thresholds this design can reach: 0.05, 0.01, 0.001" for a run
  where the pre-registered primary could reach none of them. It now quotes both
  floors by name and derives the thresholds from the primary, and prints why n
  shrank beside n, because a bare `n=14` does not distinguish six claims the
  model hedged from six that were never answered. And on a run where nothing
  was answered at all — the outcome §3's second stop rule exists to produce —
  both floors are null, the page printed "the floor is 1/0" and then died
  comparing `None` to 0.05, losing the delivery, cost and family sections with
  it. The one run whose summary has to explain itself had no summary. It now
  says no verdict was usable and carries on. That test executes the workflow's
  own summary code against a real zero-answer report rather than grepping it,
  because a string check cannot see a TypeError.

  The eleventh is the page having the right sentence and printing it in the
  subjunctive. A judge that answers `pass` to every criterion scores 50% on a
  balanced corpus, and 50% reads as a near miss; §4 names that trap by hand,
  because accuracy alone cannot tell a listener from a coin. Under the table
  sat "J = 0 *would* mean the verdict does not depend on the audio" — general
  guidance, easy to skim, and on the one run where it is a description of what
  just happened it still reads as boilerplate. When no pair was told apart the
  summary now says so above the accuracy, beside the arrival banner, with the
  verdict it gave to everything. It stays silent when the pairs were separated:
  a warning that prints on every run is decoration. Verified by rendering the
  paid summary against both shapes offline.

  One label in the pre-registration was corrected in the same pass, before any
  spend: the primary test's row read `n = 20` while the rule two paragraphs
  below it removes hedged majorities from the denominator. It now reads
  `n ≤ 20`. Nothing about the design changed — the exclusion was always there —
  but a table cell saying `n = 20` is how a run with n = 14 gets written up as
  a twenty-item test.

  The twelfth is the grader fingerprint the pre-registration pins. It existed
  in exactly two places, both prose, and nothing recomputed it. That one string
  covers `core/**.py`, `step8_grade.py`, the grade schema, the requirements
  closure and the prompt template, so any of them moving leaves the document
  pinning a grader that no longer exists — while still reading like a pin.
  Recomputing it found that it had already happened: another workstream added
  and edited files under `core/`, nothing to do with this diagnostic and
  correct on its own terms, and the pinned `8bb8360a…` became a grader that is
  not in this repository. Section 2 is re-pinned to `74e1f478…` with the old
  value kept beside it, which is the right move only because nothing has been
  bought yet; after the run that string is the record of what executed, and
  editing a record to track a moved `HEAD` is falsifying it to keep CI green.

  Where the check lives matters as much as the check. An equality asserted in a
  unit test would go red on somebody else's correct `core/` merge — a tripwire
  across a colleague's path, not a safeguard. It is enforced at dispatch
  instead: `--expect-grader-pin` hands the measurer the document, which reads
  section 2's own row, recomputes the fingerprint from this checkout and
  refuses before a single call goes out — the same place and shape as the
  `--expect-manifest` clip check. The free `dry_run` job passes it too, so
  drift surfaces without buying a dispatch to discover it. And the computed
  value is written into the report as `pins.grader_source_sha256`, so what ran
  is recorded by the run rather than by a string somebody typed.

  The thirteenth is the column in section 0 that tells the operator which
  inputs to type. Five rows, three marked "differs from the default" and two
  marked "same" — and the two marked same are the two nobody types, which is
  what the column is for. It was written by hand, so a default moving in the
  workflow does not produce a wrong document so much as a wrong dispatch.
  Neither "same" row spends on its own: `repeats` was already pinned, and a
  `prompt_arm` default of `both` is refused for a speech set before the
  identity resolves. But it stops, and section 0 says the pre-registration is
  those five values and not a sixth combination. The other direction is
  `dry_run`, whose `true` default is what makes a careless dispatch free. The
  column is now derived from the workflow's own defaults and compared row by
  row. Every row was already right; nothing had checked it.

  The fourteenth is the arrival banner itself — the line 330 section 3 calls
  the fix for 324, and the only one in the summary that tells a reader the
  number below is not this model hearing these clips. Its test checked that
  the banner's text sits earlier in the workflow source than the accuracy row:
  an ordering check over a string, true whether or not the condition beneath
  it is. The branch had only ever run on healthy reports, where it prints
  nothing — the wrong way round, because the banner exists for the run where
  `WireClient` recorded missing audio or a clip of the wrong length and
  deliberately did not raise. All three shapes are now rendered and read: no
  audio at all, a clip that is not the pinned length, and a clean run that has
  to stay quiet. Mutation-checked four ways, including `or` → `and`, which
  silences the wrong-length half alone and is the edit a tidy-up makes.

  The fifteenth is one step earlier than the tenth. That one was the summary
  dying on a run where nothing answered; this one is the summary on a run that
  never wrote a report at all. It began `test -f report || exit 0`, so a
  pre-flight refusal left an empty page under a red job, with the reason in an
  annotation. The grader-pin check above adds another way to land there. It
  also matters more than tidiness, because the two ways of getting here differ
  by money: the pre-flight checks all run before the first call and cost
  nothing, while a failure after the calls started bought them and still writes
  no report, since the report is written at the end. An empty page reads like
  the free one. The step now names both and points at the annotation, and the
  test runs the shell rather than reading it — shell that is never executed is
  a suggestion.

  The sixteenth is the fourteenth on the other page. Both delivery conditions
  are bannered above the accuracy in the *paid* summary; the *free* one printed
  the arrival count and the digest list and stopped there, saying nothing about
  a clip that is not its pinned length. The free run is the whole point of
  having a free run — it is what finds, for nothing, what would otherwise be
  found by buying a dispatch. On the run where defect 1 was live, with all ten
  speech clips measured against the tone corpus's durations, that page read
  `60/60 requests carried audio; clips sending more than one digest: []` and
  nothing else. It looked clean; the defect was found by opening the JSON by
  hand. The free page now prints both values and, when either is wrong, says
  not to dispatch the paid run yet — and stays quiet when they are right.
  Mutation-checked three ways: guard never fires, guard always fires, bullet
  drops the field.

  The seventeenth is not wrong yet, which is the only reason it is worth
  writing down. The approval gate has no checkout, so the line it shows a
  reviewer — `corpus = speech (10 clips)`, `criteria = 20`, `calls = 60 in
  total` — is a restatement. That is the line that was once `calls = 36` for a
  run that made sixty, after the tone corpus grew from twelve criteria to
  twenty: the record of what was authorised disagreeing with what was spent.
  It was pinned afterwards, and pinned against `CLAIMS` — the tone corpus,
  which is not the one this dispatch buys. That the speech set also holds
  twenty was a comment. Since the criteria count *is* the call count, and 330
  §5 says twenty claims is few, four more claims would have the gate recording
  sixty calls for a run that makes seventy-two — and the assertion would still
  have passed, because the twenty was typed into the test. Verified by growing
  the manifest by four claims: the tests as they stood went green. Both counts
  now come from the manifest, and the day the corpora diverge the failure says
  to branch the record on `$CORPUS` the way the clip count already is.

  Not a defect — the code was right — but the fourteenth's shape again and
  worth the same paragraph. `--expect-manifest` is what stands between a moved
  eSpeak and a paid dispatch, and only its passing half had ever executed.
  Eight tests cover `compare_to_expected`; none covered the command that turns
  the list it returns into the exit code the paid job's `set -euo pipefail`
  acts on. The one real execution — free CI run `34027400241` — matched, so the
  refusal was skipped there too. It is now driven both ways, with the published
  manifest standing in for the synthesiser that cannot run on this kernel: one
  altered `sent` digest exits 1 and names the clip, while an unaltered rebuild
  still exits 0, because a check that stops every dispatch is a check that gets
  removed. Mutation-checked in both directions — a refusal that returns 0, and
  one that refuses without saying which clip.

  The eighteenth was in the one number that has to be right *before* anything
  is bought. 330 section 2 predicted 937 audio tokens — the corpus length,
  31.235 s, times three repeats — and pre-registered a ±10% band around it as
  the check for whether the sound went out as pinned. But a call carries the
  clip its own criterion is about, and twenty criteria share ten clips, so one
  pass over the corpus sends every clip twice: 187.41 s across the sixty calls,
  1,874 tokens. Exactly double. A run with nothing wrong with it lands 82%
  above the band, and the summary prints *"the billed audio is more than 10%
  away from the pre-registered figure — either different sound was sent or the
  metering changed"* in bold, on the healthy run. That is worse than having no
  band at all: a check that fires every time is the check that would have
  caught a real delivery failure, spent in advance on a false alarm. It is also
  the only pre-dispatch cost estimate for a model with no published price, and
  it understated that by half. Measured rather than reasoned — summing the clip
  duration of all sixty calls in a free rehearsal gives 187.41 s. The report now
  derives the figure from `calls_planned`, so the estimate and the plan cannot
  disagree, and the document's block is *read* by a test instead of restated in
  one. The two tests this replaces asserted the code's formula against itself
  and the document's number against the same formula, so both were green on the
  wrong answer. The block was also not the only copy — the rehearsal table two
  sections up carried 937 as well, which is how a document ends up disagreeing
  with itself about what a run costs, so the test now requires every labelled
  statement of the figure to be the same one.

  Fixing that number exposed the nineteenth: the line that *compares* against it
  had never executed anywhere. All six tests that run this summary feed it a free
  rehearsal report, and no free call reports an audio token count, so
  `delivery.audio_tokens_total` is always `None` and the whole block is skipped —
  the fourteenth's shape a fourth time, except that here the input which does
  exercise it is the paid run itself. The skip was the defect, too. The measurer
  is deliberately three-state: `None` when nothing reported the field, *not* `0`,
  because `0` is a claim about metering. The summary collapsed that back to two
  by printing nothing, so a reader checking whether the ±10% band held saw the
  same blank space whether it held or was never measured. It now says which of
  the three happened, and a test renders all of them — unreported, exact, 9%,
  11%, and metered at zero. Mutation-checked four ways: restoring the silent
  skip, widening the band to 20%, making the banner fire on every run, and
  reporting the unmeasured case as `0`.

  And the number that line compares is not the bill. A judge call can make more
  than one request — a malformed envelope is asked again — and `summarise_wire`
  keeps a `requests` count for exactly that reason. It collapsed the audio token
  figure to the *last* request, which is right for `audio_sha256` and
  `response_model`, since those describe the request that produced the verdict,
  and wrong for a billing quantity: the retry sends the clip again and is
  charged again. Six retries in sixty calls is 10% more audio bought than
  pre-registered — the entire width of the band — reported as `0.0% from
  expected`, because the compared number was structurally incapable of holding
  it. Split in two: `audio_tokens` stays the verdict's own meter reading, and
  `audio_tokens_billed` sums every request the call made, which is what
  `audio_tokens_total` now totals. `requests_total` is recorded beside it and
  the summary names the retries when there are any, so a band that was exceeded
  says why rather than leaving a reader to choose between a retry and a
  delivery fault. Found by reading the collapse, then measured: 54 clean calls
  and 6 retried ones report 1,860 against 2,046 billed. Mutation-checked five
  ways, including the one that started it — the test fixture had never carried
  a `requests` field at all, so `delivery_section` read it as zero and a
  sixty-call run reported twelve requests.

  330 section 3 pre-registered four stop conditions and nothing enforced them.
  They are now `SPEECH_STOP_RULES`, checked after each call, with a test that
  fails if the constants and the document drift apart: 20 minutes wall clock,
  zero usable verdicts in the first 10 calls, 10 provider failures, and audio
  metered at 0. The second would have ended 328's observation arm at ten calls
  instead of sixty. A stopped run keeps everything it bought — including the
  call that tripped the rule — and reports `stopped` beside `calls_planned`, so
  a partial run cannot be read as a completed one. The tone corpus runs unruled:
  its numbers are published and adding conditions now would change the design
  they came out of. 116 tests on the probe, 231 across the audio suite.

- **A speech fixture, because every audio measurement so far has been beeps.**
  The tone corpora answered "does the verdict depend on the audio at all". None
  of the 31 graded audio deliverables is a sine wave, so the question the corpus
  actually turns on — *can it hear words?* — has never been asked.
  `build_speech_verification_set.py` builds ten privacy-free clips and twenty
  claims in ten matched pairs (ten true, ten false, so guessing scores 50%),
  with `order`, `binding` and `negation` families whose true claim shares every
  content word with the clip and differs only in arrangement — unsolvable by a
  bag-of-words transcriber.

  eSpeak NG is pinned by version string read at build time, binary SHA-256
  resolved through symlinks, originating package read from `dpkg-query` rather
  than assumed, full argv, and **two** SHA-256s per clip. Two, because eSpeak NG
  has no sample-rate flag — the rate belongs to the voice data, and `en-us`
  renders at 22050 Hz — while the grading path re-encodes whatever it is handed
  to 16 kHz mono before the model hears it. The file the synthesiser writes is
  therefore never the file that is sent, and one digest could not say which.
  `source` pins what eSpeak wrote and reproduces from eSpeak alone; `sent` pins
  what the judge actually receives and additionally needs the same ffmpeg. A
  `sent` mismatch beside a matching `source` blames the encoder, and the
  comparison says so in those words. The conversion calls the grading path's own
  `_trim_audio_bytes` rather than shelling out to ffmpeg or sox, so no second
  tool joins the set of things that have to be pinned. It is GPL-3.0-or-later
  and **nothing of it is redistributed here** — no source, no binary, no
  dictionary, no generated clip; the clips are CI artifacts and the repository
  holds only digests. The ground truth lives in the manifest and is never sent;
  the judging path sees one `criterion` at a time.

  The set now exists: run
  [`34022771513`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/34022771513)
  built it with eSpeak NG 1.51 (`espeak-ng` 1.51+dfsg-12build1), 31.2350 s of
  delivered audio across ten clips. All twenty digests match their files, and
  **the ten `sent` files re-encode byte-for-byte identically on the dev host** —
  a different machine, same PyAV 17.1.0 / libavcodec 62.28.101 — so the delivered
  digest is a value anyone can check rather than an artifact of one runner. The
  manifest is committed as
  `tasks/rebuilding_grading_task/330-speech-verification-manifest.json` (digests
  and transcripts only, no audio) to give `--expect-manifest` a target. Four
  tests hold it to the corpus it was built from: reword a criterion or flip an
  answer without rebuilding and the committed digests would go on describing a
  set that no longer exists, which is caught on the dev host without a
  synthesiser — verified by doing both.

  Reported as a field rather than a caveat: synthesised speech is harder to
  follow than a human voice, so **a pass confirms the capability and a failure
  cannot refute it**. Built in `speech-verification-set.yml` because the dev
  host's kernel (3.10.102) cannot run espeak-ng; `--describe` reviews the corpus
  anywhere. Nothing in this workflow calls a model or costs anything, and one of
  its own tests caught a defect in the corpus it ships: the `valve_negation`
  false claim was shorter than its true partner, and length alone is a cue you
  can act on without listening. The claim was rewritten rather than the
  threshold lowered.

- **The prompt A/B was bought, and it did not separate the causes — because the
  treatment broke the answer format, not the hearing.** #433's pre-registration
  was executed as written: run
  [34008840627](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/34008840627)
  at `1eccfb7`, 120 paid calls to `gpt-audio-1.5`, 20 criteria × 3 repeats × 2
  prompt arms, interleaved control-then-treatment on each `(criterion, repeat)`.
  The delivery record came back clean on every invariant the prereg said would
  void the run — 120 of 120 calls carried audio, `clips_with_more_than_one_digest`
  empty, `clips_whose_sent_duration_differs` empty, one `wav`/16 kHz/mono format,
  `response_models: ["gpt-audio-1.5"]`, usage complete on all 120 — so the
  experiment is valid and the pre-registered analysis stands as computed:
  production 28/51 correct at a 0.850 response rate against observation 8/17 at
  **0.283**, discordant 21:1, **exact McNemar p = 1.0967 × 10⁻⁵**, which is the
  prereg's fourth row, *the treatment is significantly worse*.

  It is the *why* that removes the result's teeth, and the artifact says it
  plainly. Every one of the treatment's 43 unanswered calls is
  `provider_error:JSONDecodeError` — the model answered, spent output tokens and
  reported usage; the grader's `_parse_json_envelope` could not read the shape.
  The 17 it did parse came back as `true` ×13, `false` ×2, `refuse` and
  `analyze_audio` — **not one `pass`**, and the scorer's rule is
  `said_pass = verdict == "pass"`. That single line is what produced the
  treatment's J of exactly 0.0 and its 0% on true claims. Re-scoring `true`→pass
  and `false`→fail, post-hoc and marked as such, flips the sign: 66.67%
  accuracy, J = 0.2857, and the paired test over the 15 surviving pairs gives
  **p = 1.0**. One scoring rule moves the answer from *p* = 10⁻⁵ to *p* = 1, and
  the distance between them is entirely response format. The honest conclusion
  is the one the document leads with: **prompt versus capability is still not
  separated**, and the A/B has to be re-bought with the verdict vocabulary
  enforced and format failure counted apart from judgement error. The prereg's
  own assumption — "the response envelope is identical in both arms, so format
  will not drive the response rate" — is what failed.

  What the run did buy outright is delivery, now beyond inference. The provider's
  own `audio_tokens` counter came back at **exactly 10.00 tokens per second on
  every clip, zero variance**, including `pure_silence`, whose samples are all
  zero and which was still billed 60 tokens for its 6 seconds. The token/duration
  fit reproduces #429 to four decimals *within each arm* — r = 0.9805, 10.86
  tokens/second, in both — with only the intercept moving (119.6 → 265.6) by the
  146 tokens the longer treatment header costs; pooling the arms drops r to
  0.2492 while leaving the slope untouched, which is why the figure is reported
  per arm and not as a headline. And for the first time the sent digests exist
  beside the file digests, confirming 325's warning that they differ:
  `tone_stops_early` is `faf3dccf…` on disk and `9578b014…` on the wire.

  Two side findings are recorded without being acted on. `presence_false` and
  `timing_true` reached no verdict in any arm or repeat, all six calls each,
  which is why the job exited 2 — the fail-closed guard is correct and is left
  alone, and the paper's denominators are 18 criteria, not 20. And
  `core/perception/audio.py` accepts any string as a verdict
  (`str(payload.get("verdict", "fail"))`) with no vocabulary check, while
  `tool_calling_judge._validated_final_envelope` rejects anything outside
  `{pass, partial, fail}`; the sub-judge is missing the check the main judge has.
  **No production grader file, config or published score was touched**, the 31
  audio-routed items of the 185-task run are untouched, and `gpt-audio-1.5`
  remains absent from the price table, so `pricing_complete` is `false` and
  `estimated_cost_usd` is **`null` — money was spent and the amount is unknown,
  which is not $0**. Both source artifacts ship with the document:
  `328-audio-accuracy-measured.json` (178,100 B,
  `e9d21a1b603a2c6f219d8895f583f26957aa49dc72c1d50fbf9cdeb98da9b92d`) and
  `328-audio-accuracy-measured-delivery.json` (3,315 B,
  `88288b6ecc56f0bfd1c0ea0e657261766e78d50c8abdae9b431f6bc9edd7318e`), and every
  figure above re-derives from them with the snippet in §9. **324's numbers are
  unchanged, all of them.**
- **The audio did arrive, and the probe can now prove it on every run — including
  the free one.** #429 left the 51.85% of the audio judge with three unseparated
  explanations behind it: the bytes never reached the model, the question dragged
  the answer, or the model cannot hear. This change kills the first and builds
  the instrument for the second. `measure_audio_grading_accuracy.py` grew a
  `WireClient` that wraps every provider call and records what the wire actually
  carried — SHA256 of the encoded audio, byte count, format, sample rate,
  channels, declared duration, the model name that came *back*, and the usage
  block — and `--delivery-out` writes that record beside the report on paid runs
  and dry runs alike. **Hashes and counts only: no audio, no prompt text, no
  model reasoning is ever written.**

  The record settles delivery arithmetically. Across the 60 calls of #429 the
  prompt-token count tracks clip duration at **r = 0.9805**, slope **10.86
  tokens per second**, intercept 119.6; by per-clip means **r = 0.9821**, slope
  11.01; and subtracting criterion text length's own share of the tokens (that
  share is itself only r = 0.4249) leaves **r = 0.9678**, slope 9.71 — the
  stricter two-sided partial correlation gives 0.9984, and the document quotes
  the weaker one. `pure_silence` — the file where the judge heard a
  clear human voice — was billed for six seconds of audio tokens. All 60 calls
  report `usage_complete`. **Something the length of each clip was charged for
  on every call, so "the bytes never arrived" is no longer an available
  explanation.** Written up in
  `tasks/rebuilding_grading_task/325-what-the-wire-carried.md`.

  The instrument for the second explanation is a pre-registered, interleaved
  A/B. `--prompt-arm production|observation|both` sends the identical criteria
  and the *identical audio object* under either the grading path's own prompt,
  passed through untouched so the control is structurally the production
  prompt, or a header that asks the model to observe before judging. `both`
  interleaves them criterion by criterion so that anything drifting with time
  hits both arms equally, and the report carries an exact two-sided McNemar over
  the pairs — `null`, never `1.0`, when nothing is discordant — alongside each
  arm's accuracy **over answered calls** and response rate **over all attempts**,
  because the observation arm is allowed to decline and declining is how an arm
  buys accuracy it did not earn. The conditions, the five header changes, the
  detectability floor (fewer than 6 discordant pairs and `p < 0.05` is
  arithmetically impossible) and the four pre-committed readings are frozen
  before the spend in
  `tasks/rebuilding_grading_task/326-prompt-arm-prereg.md`; the same document
  records why the speech half is still blocked — a `wave`-and-`math` corpus has
  no external warrant that its words are intelligible, so an offline formant TTS
  binary would have to be pinned by version and sha256 first. No recorded voice
  and no cloned person, either way.

  `Audio Accuracy Probe` gained a matching `prompt_arm` choice input and uploads
  the delivery record as its own artifact, so a reader who distrusts the
  accuracy can check whether the sound arrived without buying anything. The
  approval record now states the doubled call count that `both` actually buys.
  **That last line is the one this change most needed:** the summaries first
  read `accuracy.overall.calls`, which scores the production arm alone, and a
  120-call run would have announced itself as 60 — the same undercount that once
  put "calls = 36" on a 60-call approval. Both summaries now read
  `cost.model_calls`, and a test asserts it in **both** jobs after a mutation
  survived by hiding in the free one.

  57 new tests: 45 in `test_audio_payload_actually_carries_the_audio.py`, which
  constructs the payload and asserts the audio is in it — a mock provider that
  drops the audio part fails the suite — and 12 more in the probe's own file
  (60 → 72) pinning the workflow's arms, its forwarding of both new flags, and
  the approval record, which is checked by **executing the gate's own bash** and
  reading the numbers it prints. 24/24 and 11/11 planted mutations caught.
  Alongside them, `327-thirty-one-items-that-listened.md` counts the blast
  radius without touching it: of 8,816 items in the 185-task run, **31 went to
  audio**, 25 actually called the audio judge and **6 answered a question about
  sound by reading a `.zip` listing or an `.mp4` filename**; 50 of 13,615 points,
  **zero of them required**; run mean 79.53% moves only to 79.29–79.74% at either
  limit, but inside a single task the span reaches **29.03, 20.00 and 35.72
  points**. **Nothing was deleted, zeroed or overwritten**, and the re-grade
  options are recorded as evidence, not executed.

  Nothing under `core/perception/**`, `core/tool_calling_judge.py` or any
  grading config is touched; all 14 grader fingerprints are unmoved, verified by
  running `compute_grader_source_hash` itself and intersecting the files it
  hashes against this diff's eleven — empty. The 120-call paid run is pre-registered
  and not yet bought; when it is, `gpt-audio-1.5` still has no published price,
  so it will report `pricing_complete: false` and `estimated_cost_usd: null`.
  **That is not `$0`.**

- **The audio judge described a clear human voice, at confidence 0.98, in a file
  where every sample is zero.** The doubled probe corpus was put to
  `gpt-audio-1.5` for the first time — 20 criteria on 9 synthesised clips, 10
  true and 10 false in matched pairs, 3 repeats, **60 calls** — and the result
  is a clean negative. Accuracy **51.85%** on 54 answered calls; discrimination
  (Youden's J) **0.011** per call and **−0.1** by per-claim majority; exhaustive
  within-pair permutation `p = 0.5`, meaning 512 of the 1024 relabellings do as
  well as what was observed. 46 of 54 answered calls said `fail`, and seven of
  ten families land on exactly "six answered, three correct" — the arithmetic of
  answering the same word every time.

  This is the measurement #427 was built to make possible and it cleared its own
  bar: the floor is `1/1024 = 0.00098`, so a judge that was listening could have
  been shown to be listening at `p < 0.001`. It was not. The earlier
  12-criterion run recorded below reached the same conclusion and could be
  answered with "the corpus is beeps"; that answer is now gone, and the
  conclusion is not.

  Three exhibits, quoted verbatim from the report rather than summarised. On
  `pure_silence` the judge reported *"A clear, natural human voice is heard
  speaking throughout the 30s clip"* at 0.98 and, in another repeat, *"30s of
  complete silence"* at 0.98. On a clip holding exactly three beeps, six calls
  returned four different counts — one, three, five, four. And on clicks spaced
  exactly 0.5 s apart, the judge "measured" 0.5 s whenever the criterion
  proposed 120 BPM and 1.0 s whenever the sibling criterion proposed 60 BPM, all
  three repeats, passing both — while the ±1 BPM criteria on the same file
  produced 0.7 s, 0.8 s, "~110 clicks in 30s" and "about 58 BPM", and failed
  every time. **The verdict follows the shape of the question, not the sound.**
  16 of 20 claims got an identical verdict in all three repeats, which is the
  "consistency is not correctness" the 19.35% flip rate could not settle.

  Recorded in
  `tasks/rebuilding_grading_task/324-the-speech-it-heard-in-silence.md` with the
  raw report committed beside it, and `test_324_quotes_the_run_it_measured.py`
  re-derives every percentage, every decimal, both tables, all 60 verdicts and
  each quoted fragment from that JSON — 19 tests, 35 planted mutations caught 35
  times, including a dropped minus sign on the negative J and a `p` restated as
  0.05 three sections from where it was measured. The sweep also earned its
  keep: corrupting the *second* copy of `512 of 1024` survived a containment
  check that only asked whether the document mentioned the number anywhere, so a
  test was added that reads the counter instead and requires every relabelling
  count in the prose to be one the report enumerated. Six calls returned
  `provider_error:JSONDecodeError` and are counted as unanswered rather than
  scored zero. Speech is still not measured and the document says so:
  intelligible speech cannot be synthesised from `wave` and `math`, so this is
  the music half. **Cost: 60 billable calls, amount `미등록` —
  `gpt-audio-1.5` has no published price, so the report emits
  `pricing_complete: false` and `estimated_cost_usd: null`. That is not `$0`.**
  No grade was written, no published number moved, and the grader fingerprint is
  unchanged across all 14 grading configs.
- **How much of a published average was decided by the audio sub-judge is now
  on screen — and for most runs the honest answer is "not recorded".** The
  audio route was measured against synthetic clips whose answers were known and
  came back at 48.6%, with a discrimination of exactly **0.00** by item
  majority, an 83.3% false-negative rate on true claims, higher confidence when
  wrong than when right, and 11 of 12 items answered identically across three
  repeats — so re-running a grade can never surface the error. Nothing on the
  board said how much of any average passed through it.

  `step8_grade._routing_stats` computes exactly this and post-dates every
  published payload, so `scripts/aggregate-grades.mjs` recomputes it from the
  same items by the same rule, which that function's own docstring licenses:
  *"a payload published before this field existed reports the same numbers when
  it is re-summarised."* The predicate is copied deliberately — an errored
  task's items stay in the population but leave the scored counts, a
  `score_excluded` item does the same, a penalty item's negative weight is
  clamped to 0 rather than netted off, an unknown modality is counted under its
  own name rather than dropped, and `tasks` counts a task once however many
  items it routed. `route_composition` lands on `summary_v1`; the new
  `RouteExposureCard` renders it as a dashed diagnostic card with no WOW badge,
  beside the high-magnitude card and for the same reason.

  **Three states, never collapsed into two.** Of the 19 grade files the
  dashboard reads, **18 are item-level and get a composition — 7 recorded a
  route and 11 recorded none at all**; the 19th carries no rubric items and
  gets no composition. Those 11 predate the field and carry
  `routing_modality: null` on every item. Reading
  them as `audio: 0` would turn *never asked* into *asked and found none*, so a
  run that recorded nothing gets **empty maps rather than zero-filled ones**
  and reads `not recorded`, never `0%`. A route missing from a run that *did*
  record is a measured zero and reads `none`. Where the route was used, the
  card prints its share of scored rubric weight: on the two `rubric_v2_tools`
  runs that is **58 items across 22 tasks, 0.64%**; the OFFICIAL sol-220 grade
  carries no audio key at all.

  **The unrouted remainder is stated, and it is not a random sample.** The
  OFFICIAL grade leaves **964 of 10,453 items (9.2%)** without a route, and
  every one of them is an item the judge failed or errored on — 952 `fail`
  plus 12 `judge_error` — so a share taken over the routed rest is a share
  over a population missing its failures. The card says so rather than
  printing the percentage bare.

  **What the counts structurally cannot see is disclosed too.** Both the
  producer and this recomputation count a `mixed` item once, under `mixed`, and
  neither descends into `child_grades` — so an audio child inside a mixed item
  is audio-decided weight the audio row does not cover. Measured across all 19
  files: **23 mixed items, 72 children, zero audio children**, so nothing on
  screen moves today. `audio_in_mixed_items` is computed and reported anyway,
  kept outside the route maps so they stay comparable with the producer's, and
  the headline reads `none directly` rather than `none` the day it fires.

  **This discloses; it does not decide.** No score changes, no grade file is
  rewritten, and nothing under `compute_grader_source_hash` is touched — the
  change is confined to `scripts/aggregate-grades.mjs`, `src/**`,
  `scripts/__tests__/**` and `package.json`, so no grader fingerprint moved and
  no published run is restated. How the audio-graded items should ultimately be
  treated remains an open owner decision, and the card says that on its face.
  The rule lives in the import-free `src/components/wow/routeExposure.ts` so
  `scripts/__tests__/route-exposure.test.mjs` can execute it; that test also
  reads `_ROUTING_MODALITIES` straight out of `step8_grade.py` so the two
  languages cannot drift apart, and asserts the three states on the real
  published grades, not only on fixtures.

- **The number that says whether the model got the important things right is,
  on the gold corpora, mostly one line about formatting.** GDPVal rubrics carry
  a `required` field and it is `null` on all 10,453 items, so the repository
  decided weight stands in for necessity at `abs(max_score) >= 4` and left a
  comment saying 4 was a heuristic to revisit once gold-ceiling validation
  could show whether it mis-classifies. That validation is finished, and
  `batch-runner/scripts/analyze_required_item_definition.py` now prices the
  alternatives against the runs already published, without changing any of
  them.

  `'Overall formatting and style of the deliverable'` is worth exactly 5 and
  appears in 55–65% of tasks. It is **54.3%** of the stage-1 gold critical set
  and **33.8%** of stage-3's, and the expert gold answers pass it at about a
  third the rate of everything else. So raising the threshold to 5 — the first
  option on the board — keeps every copy of it and drops only the genuine
  must-haves worth 4: stage-1 gold moves **0.5714 → 0.5312**, *away* from the
  0.95 gate it has to reach, and stage 3 moves 0.6394 → 0.6325, while the
  220-task model run drifts the other way (0.4903 → 0.4950). Threshold 6 does
  clear the boilerplate and leaves stage 1 with **one** critical item out of
  1,431 scored ones, which then reads a perfect 1.0000. Excluding
  deliverable-wide style lines with the predicate the grader already ships,
  `core.grader_routing.is_overall_style_criterion`, takes gold to 0.7500 and
  0.8128 — still short of 0.95, which is the honest part: what is left is real
  must-haves the reference answers miss.

  The sweep runs through the production summariser rather than a copy of it.
  `step8_grade` imports `_is_critical_item` — the function — and that function
  reads `MAGNITUDE_THRESHOLD` from `core.grader` when it is called, so
  rebinding the module global reprices `summary.wow.critical_item_pass_rate`
  and `tasks[].critical_fail` exactly as a real change would. At the shipped
  threshold the recount lands on the flags the grader itself wrote (13 of 30,
  99 of 185) or the tool says so and stops. It refuses a payload whose stored
  rate the current summariser does not reproduce, deferring to the two causes
  `scripts/summary_wow_drift.py` already named — six of the 94 payloads under
  `data/grades/` — and refuses a rate whose denominator is below
  `ceil(1 / (1 - 0.95)) = 20` items, a floor derived from the gate it serves
  rather than chosen.

  **No definition was changed.** `MAGNITUDE_THRESHOLD` is untouched, nothing
  under `core/` or `step8_grade.py` was edited, and no grader fingerprint
  moved — the tool lives outside `compute_grader_source_hash`'s input set. The
  choice belongs to the owner, because it would change this metric on every run
  already published. Measurements, all four options and their costs:
  `data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`.

- **The grading rebuild (v2) is complete, and the first thing it established is
  that a perfect answer does not score 100.** The rebuild ran in three parts.
  PR1 fixed a sign error in the score arithmetic. PR2 rebuilt the judge around
  tool calls, so a verdict has to be grounded in something the judge actually
  opened rather than in a text extract handed to it up front; the batch judge,
  the tier fan-out and the character-capped extract are gone, and `Grader` now
  refuses to be constructed against a configuration that is not tool-calling.
  PR3 asked whether the result can be trusted, and answered in four parts.

  Grading the benchmark's own reference answers — the thirty-task gold subset,
  the same files a model is asked to match — returns **82.87%**, not the ≥90%
  the specification expected. Classifying that shortfall the way the
  specification requires produced **no grader defects at all**: the lost points
  are a reading tool that still cannot see everything inside a deliverable
  (about 46 points, recoverable) and reference answers that do not literally
  satisfy their own rubric (at least 57 points, not recoverable by any code
  change here). Two reading-tool holes were fixed mid-stage and the run
  repeated, moving 78.24% → 82.87%; fixing the rest raises the ceiling to about
  84–85%. **Published model scores should therefore be read against ~83%, not
  against 100.** Full evidence in
  `tasks/rebuilding_grading_task/PR3_GOLD_CEILING.md`.

  Re-grading exp003's 220 tasks under v2 **inverted** v1's headline diagnosis:
  the formatting gap did not collapse, it widened from −25.5pp to −46.0pp. What
  v1 read as "the hybrid judge over-rejects" was the opposite — the smaller
  judge could not see the deliverable and was lenient about what it could not
  read. Report in `data/grades/_validation/PR3_EXP003_REVALIDATION.md`.

  Repeating that gold grading three times, changing nothing, put the corpus
  mean at **82.87 · 83.07 · 83.25%** — a spread of 0.37pp — and cleared all
  three stability gates the specification set: worst per-task deviation
  **4.02pp** (ceiling 5), judge error rate **0.09%** (ceiling 2), bootstrap 95%
  confidence interval **7.26pp** wide (ceiling 10). The ~83% ceiling is
  therefore a property of the grader, not of one lucky run. Two limits are
  recorded rather than smoothed over. The confidence-interval gate turns out to
  measure how far the thirty tasks sit from each other rather than how far a
  repeat moves — resampling runs alone gives 0.86pp, an order of magnitude
  narrower — so passing it is not evidence of repeat stability. And chasing the
  single worst-moving task found a defect the gold-ceiling stage had observed
  but not explained: an item the judge fails to answer is dropped from the
  denominator as well as the numerator, so **the maximum score itself changes
  between runs** (three of thirty tasks). That task's 7.05pp swing came entirely
  from its maximum moving 22 → 24 — the points awarded were 18.6 both times.
  Whether to keep that rule is an owner decision, logged as a follow-up. Report
  in `tasks/rebuilding_grading_task/PR3_VARIANCE.md`.

  The cost-budget re-estimate (302) was the last item still resting on that
  three-task projection, and it has now been re-answered from measurement.
  Recomputing three real runs from the grade payloads and cost ledgers already
  committed here puts one grading run at **$411.80–$980.84** — **8.2× to 19.6×**
  the `< $50` the gate asks for. The remedy 302 prescribes on failure, tightening
  the vision/audio caps or narrowing the routing, cannot reach that money:
  perception is **1.85%–3.49%** of the bill, and deleting it entirely still
  leaves $404.17. The driver is reasoning at `effort: max` — **82.3%** of
  gold-185's output tokens, **$194.41**, about ten times the entire perception
  spend. The `$52.1` the gate was set from does not reproduce; held to one
  convention the three-task sample understated per-task cost by **2.81×**. Of
  the 21 published per-token meters in this repository exactly one lands under
  $50, two classes below the judge, so satisfying the gate by price means
  grading with a different model rather than tightening a cap. What remains is
  therefore not a cost question but a choice of which grading configuration
  every published score is based on, and that stays with the owner. Report in
  `tasks/rebuilding_grading_task/PR3_COST_BUDGET.md`; no model was called and
  nothing was regraded to produce it.

  The v2 judge code, prompt (`prompts/grader_judge.md` v2.2), configurations
  and grade JSON are all on `main`; the v1 grade files are preserved unmodified
  alongside them.

- **Three more run places, two of which change only the program driving the
  work.** The comparison covered five places, all of which take Python from
  the model and run it somewhere. Products that drive the whole task
  themselves were missing. `core/execution_environment_readiness.py` now
  carries eight: `codex_command_line_tool_foundry` and
  `copilot_command_line_tool_foundry` each do the whole task with their own
  program while asking **the same named deployment in the same Microsoft
  Foundry resource** `azure_code_interpreter` asks, and
  `copilot_command_line_tool_github_served` does the whole task on a model
  GitHub picks. A test reads the first two out of
  `SERVING_PATH_FIXED_BY_ENVIRONMENT` and compares them against the Azure
  place's entry, so "same deployment" is checked rather than asserted in prose.
- **Where a model comes from is now a declared field, because every other
  field can match while the model does not.** `model_serving_path` is required
  on `ModelRunConditions` and takes one of two values —
  `microsoft_foundry_deployment` or `github_served_copilot`. A plan that names
  a third value is refused; a plan that contradicts
  `SERVING_PATH_FIXED_BY_ENVIRONMENT` is refused, so no plan can relabel the
  GitHub-served place as a Foundry one and inherit the fixed conditions it
  cannot honour. `PRODUCT_CHOOSES_THE_MODEL` is **derived from that table
  rather than written out a second time**, and a test asserts the derivation —
  a hand-written second copy that agrees today and diverges later is the shape
  the same-number-in-four-places entry below was opened to close.
- **A third scoreboard, `native_product_bundle`, which may be absent but may
  not be merged.** A product that chooses its own model cannot join a
  comparison that holds the model still, so scoring it beside one would leave
  a better result unattributable between the program and the model.
  `REQUIRED_SCOREBOARDS` therefore holds only the two same-model boards; the
  bundle board is optional because an operator may judge it not worth the
  money. If present it is kept apart: a bundle board labelled as one of the
  other two is refused as "added together by mistake", a same-model board
  listing any `PRODUCT_CHOOSES_THE_MODEL` place is refused, and a bundle
  comparison of fewer than two places is refused as not a comparison. The
  bundle still fixes the instructions, the task list, the input files and the
  budget — only the model route is free — and a plan that lets those drift is
  told the places "are not being asked the same thing for the same money".
- **Two more prohibitions, required separately, because they are three
  different accidents.** Alongside `automatic_model_switch_allowed`,
  `ModelRunConditions` now requires `automatic_fallback_allowed` and
  `unsupported_runner_substitution_allowed`. Switching model changes **what
  answered**; carrying on with a substitute changes **what ran**; substituting
  a runner changes **where it ran**. A plan that says no to one has said
  nothing about the other two, so all three are required fields and silence is
  refused at load time rather than defaulted to permission. `resource` becomes
  required for the same reason — a deployment name alone does not say which
  model would answer — and is **inherited from `azure_connection.account`
  rather than written twice**, with distinct refusals for a plan that pins no
  account and for a place whose model does not come from that resource at all.
- **The documented reasons these three cannot run are checked against the code
  they cite.** All three grade `not_implemented_in_this_repository` from the
  absence of an execution mode and a runner class, not from an opinion.
  `DOCUMENTED_BLOCKERS_BY_ENVIRONMENT` records **three** further reasons for
  the Codex tool, **two** for Copilot's own-key setting and **three** for the
  GitHub-served one, and a test counts them so that clearing one does not read
  as clearing the place. The static-key conflict is checked against
  `core.azure_ai_clients.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV` itself, so a
  later decision to permit one of those names fails the test instead of
  leaving the blocker text quietly wrong. The Azure address GitHub's own-key
  documentation gives —
  `https://<resource>.openai.azure.com/openai/deployments/<deployment>` — is
  **passed to `classify_endpoint` and shown to raise**, alongside an address
  the repository does accept, so the result is a statement about that shape
  rather than about the call.
- **A plan that names a place with no code behind it now stops the run.**
  `build_readiness_report` previously let such a place be dropped and the rest
  proceed, which files a score under the name of a place that never ran. It
  now refuses, and repeats what is missing rather than only saying no.
- **Side effect, intended.** The free check's `environments` list grows from
  five entries to eight, and `not_implemented_in_this_repository` from one to
  four. `ready`, `may_start`, `compared_environments`,
  `blocked_environments`, the eleven problems, and the status of all five
  pre-existing places are **unchanged**; the three new places cost nothing
  because none of them can run.

### Fixed
- **A negative result was written up as a proof, and it was not one.** The #429
  entry above and the document it points at claimed the run had shown the model
  "never listened", that the counter-argument was "gone", and that the ability
  was absent. Nine synthesised clips, 20 criteria, one model and three repeats
  cannot carry that. `p = 0.5` says the observed split is what chance produces;
  it is **not** a demonstration of incapacity, and a null result on one corpus is
  not a null result everywhere. The overclaim survived review because the
  measurement was careful — the conclusion drawn from it was not.

  `324-the-speech-it-heard-in-silence.md` now opens with a retraction naming the
  three sentences that overreached and stating what the run does and does not
  license: on **this** corpus, at **this** size, the verdicts did not track the
  sound, and delivery, prompt and capability were **not** separated. **Every
  figure, table, quotation and the raw JSON are unchanged** — the 19 pinning
  tests that re-derive them from the report still pass, which is the point:
  the numbers were never the problem. The two follow-ups that do the separating
  are #325 (delivery, now settled) and #326 (prompt, pre-registered above).

- **A scope that matched nothing was reported as a file with no text.**
  `read_deliverable` takes a `scope`: `{"sheet": ...}` for a workbook,
  `{"page_start": ...}` for a PDF. Name a sheet the workbook does not have, or
  open a window that begins past the last page, and the selection came back
  empty — and an empty selection was indistinguishable from an empty file. The
  read then carried `_EMPTY_READ_DISCLAIMER`: *"an empty text read means this
  file carries no extractable text."* An absence produced by the **question**
  was handed to the judge as an absence in the **document**.

  The same file already refused this three other ways. `scope={"member": ...}`
  on a non-zip is refused; an out-of-range page or slide is refused by
  `_render_pdf_page`/`_render_pptx_slide` *naming the range that exists*; an
  unknown `scope` key is refused by `_validate_scope_keys`. All three are on
  the render and dispatch paths. Neither `sheet` nor `page_start`/`page_end`
  had it on the read path, so the one shape of the mistake a grading judge is
  most likely to make was the one shape that failed quietly.

  Both now raise `InvalidScope`, which the envelope already surfaces as
  `error_type: "bad_scope"` — the retryable kind, so a caller that guessed a
  sheet name gets a turn to name a real one instead of a dead end. Each refusal
  names what exists: the workbook's sheets, the document's page range, the keys
  the op accepts. `MAX_SHEETS` no longer silently drops a sheet that was asked
  for by name; that cap bounds a whole-workbook read and was never a statement
  about reachability. A file that genuinely holds no text still gets the
  disclaimer, unchanged — three tests hold that line from the other side, on an
  empty `.docx`, a glyph-free PDF and a PNG.

  Measured on the 185-task gold-ceiling payload, model-free: **15 rubric items
  across 9 tasks** were graded `fail` at **0.0 of 29.0** with that sentence as
  their entire evidence. Reading all 10 files they name with `scope={}` returns
  **346 to 200,000 characters** from every one; none is missing from disk. This
  closes the question `320-three-gaps-that-closed.md` recorded as unanswered —
  *"왜 같은 파일이 3단계에서 비어서 돌아왔는지는 이 조사에서 확인하지 않았다"* —
  and both tasks it named as unexplained pass→fail flips, `7d7fc9a7` and
  `dfb4e0cd`, are inside the 15.

  That document publishes 23 where this says 15, and both are right about what
  they counted: the judge did not always quote the note whole, so the whole
  sentence matches 17 items, the tail alone 23, the union 24. Restricted to
  office files every rule gives the same 15 and the same 0.0 of 29.0 — the
  entire spread is nine items on two `.mp4` deliverables, which is a routing
  question and stays open. All three rules are pinned so the figure cannot
  drift with its own definition, and both documents' counts are re-derived from
  the payload rather than restated.

  What this does **not** claim: `judge_raw_response` is null and `tools_used`
  keeps call names without arguments, so the payload preserves *that* the tool
  was called three times, not *what was asked*. The mechanism reproduces
  model-free; per-item attribution does not, and a test asserts the record is
  that thin so no later document can quietly assume otherwise.

  32 tests, 17 mutations planted and 17 caught. No model calls, no regrade,
  $0. **This moves the grader source fingerprint**, since
  `core/tools/read_deliverable.py` is one of its inputs:
  `7b2bd7d97125c38337e77b4aaa3c08891bf2d7b7ac4c773d144a81fbccebed40` →
  `06a1b80c8787b9aeea485dabb89a21344baac4fbbb182c78f5e60ea9fd29cb41`, measured
  by running the hash twice against `gold_ceiling_185_v2_sol_max.yaml` with only
  this file swapped. Already-published grades are unaffected; the next run at
  this fingerprint is not comparable to one before it.
- **The report prompt ordered a paid model to headline the heuristic the owner
  had just retired.** `core/narrative_analyzer.py` was the one surface the
  2026-09-03 ruling had not reached, and it is the surface where a model is
  paid to turn these numbers into prose a person then reads. The string in the
  known-residual note above was the smaller half of it.

  `_build_grading_guard_clause` built its `Highlight:` line — the line that
  decides what the report leads with — as
  `"weakest sector, strongest sector, critical_item_pass_rate"`, unconditionally.
  The very next statement in the same function denominator-guards the precheck
  breakdown, so one rate was protected from its own empty denominator while
  this one was promoted regardless of what was behind it. The rate is out of
  the highlight list now, and the prompt states in its own words that it counts
  items by score magnitude, is **not** a measure of required items, is **not**
  a pass criterion, and must not be called critical, required or mandatory.

  Point 5 of the ruling — show the denominator, and say when it is too small to
  read — had never reached this surface either. `crit=0%` went to the model
  with nothing beside it. `_format_high_magnitude_rate` now renders
  `not measured (0 items)` over an empty denominator, `0% (denominator not
  recorded)` where `item_counts` is absent,
  `0% of 3 -- too few to read (< 20 items)` under the floor, and `33% of 400`
  when there is something to read. The floor is the same `ceil(1 / (1 − 0.95))`
  the dashboard and `scripts/analyze_gold_ceiling.py` each derive; the label is
  built from `core/grader.py`'s `MAGNITUDE_THRESHOLD` so it cannot drift from
  the comparison that decides criticality. The other two rates keep
  `_format_rate`'s behaviour unchanged — the ruling was about this metric, and
  inventing a readability floor for `precheck_pass_rate` and `judge_pass_rate`
  would be a new criterion applied to runs already published.

  Measured on this repository's own grades, with #399 merged: 86 published
  sector rows carry the rate, 16 report exactly `0.0`, and recomputing the count
  settles all 16 — 4 counted nothing, 12 counted 1–19, none reached 20. The 61
  shard payloads, whose rates are published nowhere, say the same at scale: 364
  rows, 155 zeros, split 41 and 114, none at 20. Not one `0.0` on this metric,
  in either population, is a run where twenty or more high-magnitude items were
  scored and failed. All four rendered states are reached by the committed
  corpus, and a census test floors each one so none can become a branch nothing
  exercises:

  | population | not recorded | not measured (0) | too few to read | readable |
  |---|--:|--:|--:|--:|
  | published, run level | 6 | 1 | 15 | 11 |
  | published, per sector | 0 | 4 | 34 | 48 |
  | shard, run level | 61 | 0 | 0 | 0 |
  | shard, per sector | 364 | 0 | 0 | 0 |

  Writing that measurement down found an arithmetic error in the entry above
  and in point 6 of `REQUIRED_ITEM_DEFINITION.md`, both merged by #394: they
  gave 447 sector rows, 168 zeros and 385 missing denominators, split 41/127,
  and called all of it published. That total folded the 364 shard rows in
  alongside the 83 real ones. Shards are intermediate halves of a run and their
  rates are published nowhere, so they are not published rows. The conclusion
  those entries drew is unaffected — no zero on this metric is readable in
  either population — but the counts were wrong, so both are corrected in place
  rather than repeated here, and the new test asserts a floor per population so
  the two cannot be conflated again.

  Then #399 moved the published side again, mid-review, by backfilling
  `item_counts` across the corpus: 83 rows became 86, 13 zeros became 16, the
  1–19 bucket went 9 → 12, and the 21 published sector rows with no denominator
  went to none. Every `>=` floor in the tests stayed green while the sentences
  they guarded went stale, which is the whole reason the census above is
  floored per state as well as per population. The figures here and in
  `REQUIRED_ITEM_DEFINITION.md` are the post-#399 ones; #394's entry above is
  left as written, since it dates itself to "#393 merged in" and was correct on
  that corpus.

  **The grader source fingerprint moves, deliberately.**
  `compute_grader_source_hash` walks every `.py` under `batch-runner/core/` and
  hashes `step8_grade.py` alongside them, so a prompt with nothing to do with
  grading — and even a comment restating a count in the summariser — still
  changes the hash each shard stamps and `step9_merge_shards` compares. That is
  why the one-word edit waited for a pull request of its own.

  Measured rather than asserted, against `main` at `de9b5ef`, and re-measured
  there rather than carried forward. Full 64 characters, because an abbreviated
  hash is not one:

  | grading config | | grader source hash |
  |---|---|---|
  | `regrade_exp003_v2_sol_max_score_excluded` (the OFFICIAL run) | before | `b3634efefd90bec6640c1ef258e459cd93147f7bee67fe52b73e28924c3363d6` |
  | | after | `832900dbdd07363c58bd4e61679f62d12a7349c6a341d1c5a988c078cefb7eca` |
  | `gold_ceiling_185_v2_sol_max` | before | `1312a579d67ec2e8eafd0d5dbce81a890fb3497d1a0f5841188d7310d7ccc215` |
  | | after | `4e65f0c3e6ff223ee08c65b6d5705e4aad5cb0df0dbc5c7e03aef74d95c3f3a5` |
  | `default_v2_mini` | before | `7599593dc16cbbc5829af6ae1fa2a261b3f46edb67cae2138b7d588f50acc8eb` |
  | | after | `82987c3dbd2f28b9f87338298587de016762d02fcb4624ba307a1babb39ab482` |

  Three configs because the hash is per config, so "it moved" is a claim about
  each one and not about the tree.

  Both columns were measured three times over this change's life, and recording
  that is the point: only the last measurement is worth anything. The first pair
  was taken against `main` at `4739321`. The `after` column then moved once, when
  correcting the stale count in `step8_grade.py`'s own `item_counts` comment
  brought that file into the diff. The `before` column then moved too — without
  this branch touching anything — when `de9b5ef` merged the video contact-sheet
  work, which changed `core/media_types.py`, `core/perception/vision.py`,
  `core/tool_calling_judge.py`, files under `core/tools/` and
  `schemas/grade.schema.json`: every one of them an input. The table above is the
  state after merging that base in. A fingerprint recorded when a branch opens is
  a fingerprint of a tree nobody will grade against; this one is measured
  immediately before merging, and re-measured whenever the base moves underneath
  it.

  They are recorded here and **not** pinned in a test. A test that asserted a
  literal hash would fail on the next unrelated edit under `core/` and would
  have to be updated by whoever broke it, which is how a fingerprint check
  becomes a formality. The repository has no such pin today and this change does
  not add one.

  Checked before merging: no literal source hash is pinned anywhere in the
  tests, scripts, workflows or validation docs, and no grade run was in flight.
  Nothing under `data/grades/` is
  rewritten, no rate changes value, and no stored score moves — what changes is
  the text a future report generation is given. The next paid grade run needs a
  fresh smoke at the new fingerprint.
  `batch-runner/tests/test_the_report_prompt_retires_the_required_item_name.py`
  pins the label against `MAGNITUDE_THRESHOLD`, the floor against all three
  copies of the constant, the five rendering states, the highlight line, the
  scope decision, and the corpus claim above.

- **A precheck that never ran was published as "Strong on reasoning, weak on
  structure".** `step8_grade._rate` returns `0.0` when the denominator is
  empty, and `0.0` is also the worst possible score, so the two are the same
  number on the wire — a hazard that function's own docstring states. The
  producer's answer was `_wow_item_counts`, which publishes the denominators
  beside the rates, and its docstring names the reader that had not yet used
  them: *"the dashboard's Structure vs Reasoning card turns the same gap into
  'Strong on reasoning, weak on structure' — a finding about a check that never
  ran, in a paid report and on a public page."* The obligation sits on the
  reading side, and that is where this is fixed.

  **Measured on this repository's own published grades.** 33 published
  run-level payloads carry `precheck_pass_rate` and **20 of them publish
  `0.0`**. 22 record the denominator, and among those, every one of the **15**
  zeros counted **no precheck items at all** — not one is a run where prechecks
  ran and failed. Per sector the shape repeats: 83 rows carry the rate, **56
  publish `0.0`**, 62 record a denominator, and **all 35 recorded zeros counted
  nothing**. Among them is the 185-task gold-ceiling run — 8,816 judged items,
  zero prechecked ones, published as a 0% structural pass rate and captioned as
  a weakness. The 61 shard payloads, whose rates are published nowhere, carry
  364 more sector rows; every one of them is a zero and not one records a
  denominator.

  (This paragraph first gave those counts as 94 run-level payloads, 81 zeros,
  447 sector rows and 420 zeros — the published and shard populations added
  together and all called published. The figures for the denominator itself
  were right, because no shard records one. `tests/test_a_rate_over_nothing_is
  _not_zero.py` had it right all along at 20 and 56; the prose here did not.
  Corrected in place, and the same conflation is corrected in the entry above.

  A second note, added afterwards rather than written over the paragraph: #399
  backfilled `item_counts` across the published corpus and moved every published
  figure above. The finding is unchanged and got stronger — with denominators
  recovered, **all 20** run-level zeros and **all 59** sector zeros counted no
  precheck items, where before only the 15 and 35 with a recorded denominator
  could be checked. The counts now read 33 run-level payloads carrying the rate,
  20 zeros, 27 with a denominator and 6 without; per sector 86 rows, 59 zeros,
  and a denominator on every one. The shard totals — 61 payloads, 364 rows, no
  denominator anywhere — did not move. The paragraph above is left as it was
  measured, because it was right on the corpus it was measured against.)

  **Four states, never collapsed into two.** `src/components/wow/rateReading.ts`
  is import-free so a node test can execute the decision itself. A rate whose
  denominator was recorded and non-zero is `measured` and reads exactly as
  before. A recorded zero denominator is `none-counted`: it prints "not
  recorded", **draws no bar at all** — a bar at zero length is the picture of
  total failure, which is the one thing the run did not measure — and says why.
  A rate with no denominator recorded is `denominator-unknown`: the percentage
  is still shown, greyed, with the gap stated, because 11 of the 33 published
  run-level payloads and 21 of their 83 sector rows predate `item_counts` — as
  do all 61 shard payloads and all 364 of their rows — and #393 recovered it
  for only some. (#399 then recovered the rest of the published side: 6 run-level
  payloads and no sector row are still in this state. The shard rows all are,
  and a merge reads shards, so the state is not dead.) A
  run publishing no rate at all is `absent`. Only `measured` may be set against
  another rate, so *Structure vs Reasoning* now withholds its verdict and names
  the missing half instead of subtracting a zero that stands for nothing.

  Applied uniformly across every surface that reads one of these three rates:
  `StructureVsReasoning`, `HealthStrip`, `SectorHeatmap`, `RubricCoverageCard`
  and the `GradingAnalysisView` mini-pills, where runs are read side by side and
  an invented `0.0%` ranks them. **Scope stated honestly:**
  `precheck_pass_rate` is the live case; `judge_pass_rate` and
  `rubric_item_coverage_avg` have zero zero-denominator instances in anything
  published so far and are fixed as the same code path, not as a live defect.

  **Nothing the producer writes changes.** The rates keep their type, their
  values and their keys — `scripts/grading_cost_sweep.py` compares them against
  thresholds and 33 payloads carry them, so turning them null to fix a caption
  would break more than it repairs. No grade file is rewritten, no score moves,
  and the change is confined to `src/**` plus one new test, so **no grader
  source fingerprint moves**. As Session B's backfill fills `item_counts`, the
  `denominator-unknown` state shrinks into `measured` or `none-counted` on its
  own. `scripts/__tests__/wow-rate-denominator.test.mjs` pins it: the
  producer's four denominator keys against `step8_grade.py`, the four states run
  for real, the comparison withheld unless both sides were measured, the
  measured case unchanged in every band, and a scan proving no `src/` surface
  reads one of these rates without going through `readWowRate`.

- **The dashboard called a band "Perfect (100%)" that a task scoring 99.77%
  is inside, and printed that task's score as "100%".**
  `summary.openai_compat.perfect_count` and `zero_count` are counted by the
  grading backend at `>= 99%` and `<= 1%`. PR #371 corrected the backend's own
  wording to say so — `narrative_analyzer.py` prints `Near-perfect (>= 99%)`,
  `grade.schema.json` warns the number "must not be read as one" — and
  deliberately left the dashboard alone. So the screen went on saying
  `Perfect (100%)`, `Zero (0%)`, `Score = 100% — all rubric criteria were
  fully satisfied` and `scored full marks` over counts that require none of it.

  Two published rows are why this is not a wording quibble. In
  `exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-hybrid`, task
  `476db143` scored **99.77%** and task `0e386e32` scored **0.9%**. The
  aggregator snaps a row's `avg_score` to a flat 1.0/0.0 once it crosses a band
  boundary, so that the per-row Status badge and the summary count cannot
  disagree — which left `476db143` rendering as a `100%` in its own score
  column, under a `Perfect` badge, inside a `Perfect (100%)` total. Every
  figure on that row was a number the task did not have.

  The thresholds do not move and no published count changes, for PR #371's
  reason: the counts are already on the board, and moving a boundary would
  restate every run. What changes is the words, plus one number the row can now
  state for itself. `src/data/scoreBands.ts` is the single place the two
  thresholds and the five labels derived from them are written, and
  `scripts/aggregate-grades.mjs` exports the same two constants;
  `scripts/__tests__/near-perfect-labels.test.mjs` fails if the two files drift,
  if a label spells its threshold out as a literal instead of interpolating it,
  or if any surface under `src/` goes back to naming an exact figure.

  The aggregator now carries `pct_exact` on **exactly** the rows the snap moved
  — measured across every published grade file, that is 2 rows out of 2,020, so
  2,018 render byte-identically to before — and `ScoreCell` prefers it, so
  `476db143` reads `99.8%` and `0e386e32` reads `0.9%`. A task that genuinely
  scored 100 or 0 gains no key and is unchanged. The recount of snapped rows
  still equals `perfect_count` and `zero_count` on both published runs, which is
  the check that the counts did not move.

  `OUTCOME_BADGES` has no `scored` entry, so both rows fell through to the
  `avg_score === 1 / === 0` fallback and were badged from the snapped value;
  those two badges now read `Near-perfect` / `Near-zero`. The `content_zero`
  badge is deliberately left saying `Zero`: `classifyTaskOutcome` branches on
  the raw `pct === 0`, so that one is exact.

  Nothing here is inside `compute_grader_source_hash`, which covers only
  `batch-runner/`, so no grader fingerprint moves and no published grade needs
  regrading.
- **A React component was refused a verdict for want of a picture that does
  not exist.** Task 7de33b48's whole deliverable is one 3.5 KB
  `screen_reader_status_message.zip` — two `.tsx` files, a `.css`, a
  `README.md` and a `package.json`. Five of its rubric items, worth eight of
  its fifty-two points, use the words `render`, `layout` and `visual`, so all
  five were classified visual, found nothing renderable inside an archive, and
  were recorded as `required_visual_render_target_unavailable`. There is no
  picture in that submission to find. The component's appearance is not a
  property of the submission at all — it exists only once something builds and
  runs the code — so the JSX and the CSS are not a substitute for looking at
  the page, they are the only place the answer is written down.

  This is the narrow inverse of the rule it sits beside, which is unchanged:
  "document color and page layout are visually polished" against a `.csv` still
  fails closed, because data has a look a reader sees on opening it and a text
  verdict there would be invented rather than merely absent. So `.csv`, `.txt`,
  `.md` and `.json` are deliberately absent from the new
  `GRADER_SOURCE_CODE_EXTENSIONS`, and an archive of prose and configuration is
  refused on the separate ground that none of it is source.

  `has_only_source_code_content` answers the question the routing rule needs:
  is every selected file program text, with nothing anywhere in it — nor in any
  archive member — that could be turned into a picture. It is tri-state on the
  same discipline as the audio probe. `True` demotes, `False` is a positive
  claim that the file was examined and is not that, and `None` is an admission
  — missing file, unreadable archive, or a member list cut short one entry
  before the screenshot — which changes nothing, because demoting on a guess is
  what the tri-state exists to refuse. A companion `README.md` and
  `package.json` do not spoil the claim, since nothing in them is looked at
  either; one `.png`, one `.csv`, or one extension this module cannot name
  settles the whole archive as `False`.

  The demotion cannot divert an item that renders today. It fires only when no
  selected suffix is in the render set, which is exactly the set that currently
  errors: `.zip` is not renderable, so a zip of screenshots errored before and
  still errors now rather than being answered from source it happens to
  contain. Nor can the unreadable-file escalation undo it — that promotes only
  when every suffix *is* renderable.

  The other four of the nine unjudgeable items are two video reels, and they
  are deliberately left alone. A reel really does have to be watched; sampling
  a frame would turn "could not see it" into a verdict about whichever frame
  was picked. They stay excluded, which is the honest outcome rather than a
  gap.

- **Repeating a grading run gave its calls the names run 1's calls already
  had, and 684 separately billed calls stopped being countable.** Grading a
  corpus twice is how repeat variation gets measured, so a repeat holds
  everything that identifies the run fixed on purpose: same inference, same
  grading config, same grader source. `step8_grade.py` forked the *output path*
  on the repeat number and wrote to `_repeats/run-NNN/`, but the run id the cost
  ledger hangs its call identifiers off was built from those three fixed parts
  alone. Call identifiers are derived from where a call sits in its run and
  never from what it says, so repeat 2's first call on a task was named exactly
  what repeat 1's had been — and `CostReceiptLedger` keys on that identifier and
  updates a row it already holds rather than inserting one.

  Three runs of the audio-repeat corpus are committed. They carry 1,039 rows
  between them under **355** distinct identifiers. All 344 colliding identifiers
  have rows that disagree on request digest or token counts, and no two of the
  ledgers are even the same size, so these are different calls wearing one name
  rather than one call recorded twice. Sort order keeps repeat 2, which leaves
  632 `gpt-5.6-sol` and 52 `gpt-audio-1.5` calls out of every figure counted by
  identifier. The `$549.50`–`$980.84` tier bound is computed from a different
  run's merged ledger and does not move.

  `step8_grade.make_cost_run_id` now suffixes a repeat's run id past run 1, so
  run 1 keeps the identifiers already published beside it and no new collision
  can be minted. The identifiers already on disk cannot be un-minted; the
  price-table entry records how many calls they hide and in which direction, and
  the guard test classifies every duplicated identifier by the paths it appears
  under — merge duplication has to equal the merged ledger exactly, repeat
  collisions have to be pre-fix, and a duplicate belonging to neither fails
  rather than being absorbed into a total.

- **The headline never said what part of it was rubric nobody read.** An item
  the judge fails to read leaves the numerator and the denominator together, so
  the task is scored out of less rubric than it was worth and its percentage
  rises. Both ends of that have been on the board since #362, but only inside
  the task table — one row at a time, fifty rows at most. Nothing told a reader
  what the *run's* average owed to the same effect. Twelve of the nineteen grade
  files under `data/grades` have a headline that moved this way; the widest is
  3.53 points on a three-task smoke, and the 215–220 task runs move 0.14 to
  0.53. `summary.score_exclusion_lift` now carries the run-level measurement and
  the grade detail page prints it, on the runs where it is true and nowhere
  else.

  Both percentages it reports are means over the task rows, and neither is the
  published headline. Two independent defects move these averages in opposite
  directions: unread rubric leaves the denominator and lifts the score, while a
  task the grader could not grade at all stays in the denominator as a zero and
  lowers it. Four published 1.0 files carry the second, by 0.23 to 1.26 points.
  Subtracting a full-denominator row mean from a published headline reports the
  two added together as though both were the first, and on the worst of the four
  it flips the sign: 54.10 published against 55.36 from the rows and 54.82 out
  of the whole rubrics is a lift of **+0.53**, which the naive subtraction
  reports as **−0.72**. The two gaps are therefore reported apart — the existing
  `headline_support` carries the other — and the page says so in words when a
  run's headline disagrees with its own rows. No published number changes; the
  headline is passed through as written and asserted byte-identical.

  This is the reporting half of the follow-up logged above, where an item the
  judge fails to answer changes the maximum score itself between runs. Whether
  to keep that rule remains an owner decision; the dashboard no longer stays
  quiet about its effect while it stands.

  candidates, and they are not.** The stage-3 analysis has no tool-failure
  field, so it offered the `read_deliverable` call census in its place, on the
  plain reading that its zero end is where a verdict was reached without opening
  the deliverable. Measured across the three runs, all 92 zero-call items are
  routed `visual`, all 92 have `perception_called: true`, and all 92 carry a
  non-empty `tools_used` — they rendered the deliverable and looked at the
  rendering, 25 of them more than once, and `read_deliverable` is not the tool
  for that. The direction that settles it: 92 of the 231 visual items never call
  it, and **not one** of the 3,858 text items is in the bucket. A tool failure
  would not sort itself by routing. `observed_vocabulary` now splits the zero
  bucket three ways — rendered and looked, some other tool, reached the file no
  way at all — and only the last is a failure candidate; on these runs it is 0.
  The `tool_failure` label says it was not measured and disclaims the proxy
  reading instead of inviting it.
  `data/grades/_validation/PR3_REPEAT_VARIATION.md` is regenerated (every
  bootstrap figure reproduces unchanged) and its Korean deferral is replaced
  with the answer. No published score moves, and the tool is outside
  `compute_grader_source_hash`, so no grader fingerprint moves either.
- **A guard against mixing two graders was being decided by filesystem
  order.** `test_a_shard_from_a_superseded_grader_cannot_join_this_run` merges
  a current shard with one graded by superseded code and asserts the refusal
  names `grader_source_hash`. It got that older shard from
  `iterdir()`'s first entry — and two superseded passes are committed side by
  side. One differs from the current run only in the grader source; the other
  also carries a different judge config, which `step9` refuses on *first*, so
  the refusal never mentions a grader at all. On identical bytes the test
  passed on one machine and failed on CI. The sibling is now chosen by reading
  the payloads for the difference the test is about — same `judge.config_hash`,
  different `grader_source_hash` — and a new test pins both ends of that
  choice, including that the sibling it rejects really would have swallowed the
  assertion. Restoring the old selection turns both tests red.
- **A task lost 34 of its 63 scoring lines to a picture budget nobody had
  counted.** `judge.perception.visual.call_cap_per_task` was 72 in all thirteen
  grading configurations, and nothing anywhere said where 72 came from. It was
  not idle: on the 185-task gold run, task `a73fbc98` planned 102 renders, was
  refused, and 34 of its rubric items were never attempted — no perception
  call, no tool call, no render against any of them. Its published 76.74% is 33
  points out of the 43 that got graded, from a rubric worth 87. The same cap had
  already cost more than that once: at an earlier grader generation task
  `43dc9778` planned 134, was refused whole, and came back
  `all_items_score_excluded` at 0.0% — a 67-item task leaving a 185-task corpus
  without the corpus looking any smaller.

  The cap is now **112**, and the figure is counted rather than chosen. The two
  refusals differ in the way that settles it. `43dc9778`'s 134 was
  **reducible**, and a code change had already reduced it: `058d4f8` (#303)
  narrowed the no-text-layer escalation so one unreadable file stops sending a
  whole task to pictures, and at the next grader generation that task plans 68,
  renders 68 and scores 92.23% with nothing excluded — at the same cap of 72,
  with nothing about the budget changed. `a73fbc98`'s 102 is **irreducible**:
  every render is wanted by a criterion naming something visual, so
  `_relax_to_fit_visual_budget` returns the strict plan unchanged and the task
  fails closed. That relaxation was live on the run — the payload's
  `grader_source_hash` is the tree of the commit that introduced it, and not one
  of the task's 63 items is marked `visual_budget_downgraded`, which is the
  signature of relaxation having been tried and having freed nothing. So the cap
  has to clear 102, plus one more item's worth of files, which the run records
  as `visual_file_cap` 10.

  It deliberately stays below 134. Not as a live saving — the current grader
  would not spend 134 on that task at any cap — but as a guard on the shape of
  demand that produced it: one unreadable file escalating a whole task is a
  mistake that can be reintroduced, and at a cap of 134 or more the benchmark
  would quietly pay for it instead of refusing and saying so.

  What it costs: one task of 185 starts rendering, adding 102 renders against
  the corpus total of 670. Every other task planned inside 72 to begin with, the
  largest at 68, so 184 of the 185 do exactly what they did before. Those are
  strict plans throughout — `visual_budget_downgraded` is false on all 17,743
  items that carry it across every committed payload, so relaxation has never
  once fired in production.

  Three exp003 configuration hashes are repinned as a consequence, and none of
  the published exp003 figures can move: a raised ceiling can only change a run
  that reached it, and not one of the thirteen committed exp003 payloads holds a
  single budget refusal (`grep -rl task_visual_budget_exceeded data/grades/`).

  Two things that quoted the old cap are corrected with it. The execution
  envelope's cost plan mirrored it at 72, which silently stopped being a ceiling
  the moment the grader allowed 112; its vision line is now 112 and is read from
  the grading configuration rather than typed beside it, so the next cap change
  cannot leave it behind. Unlike the sound line this one carries money, so the
  worked-out perception total rises $54.00 → $84.00 and the safety-multiplied
  grand total $7,608.40 → $7,645.90 — the honest direction, since the old total
  was a ceiling under a cap that no longer applies. Everything that quoted that
  total in prose is requoted with it, including
  `core.execution_envelope_tasks.catalog_number_problems`, whose docstring
  measures what the zeroed-rubric rule saves.
  `test_track2_visual_inventory.py` keeps its projection but no
  longer reads as the basis for the cap; it counts what criteria ask for by
  their wording, cannot see the no-text-layer escalation at all, and projects
  this run's two heaviest renderers — 68 and 59 renders — as 2 apiece. The
  third, at 39, it projects exactly, because that task's renders are asked for
  by criteria naming something visual. Exact where the demand is named, blind
  where it is escalated, and both halves are now pinned in that file rather
  than asserted in a comment.

  The basis lives with the number: `grading_configs/README.md` §"Why the visual
  task cap is 112" states every figure, and
  `tests/test_the_picture_budget_was_counted.py` recomputes all of them from the
  committed run rather than restating them.
- **Thirteen items the judge never answered were all written down as the same
  six words.** When a grading call returns no usable final text, the judge
  already works out *which* kind of nothing it was — the output budget ran out,
  the provider filtered the reply, the response came back with a failed status,
  or nothing explains it — because whether to retry at all depends on that
  answer. The value was used for the retry decision and then dropped, and the
  item was recorded as a bare `empty_final_text`.

  On the 185-task gold run that happened to thirteen items across ten tasks, at
  60–85 seconds of grading each. Afterwards there was no way to separate them
  without paying to grade them again, and they need opposite responses: a
  budget exhaustion is fixed by a larger cap, a content filter is not fixed by
  anything a cap can do, and `unknown` means the provider said nothing at all.
  The distinction was visible the whole time in the retry warning line — the
  shard-4 entry below quotes `empty_final_text:max_output_tokens` from exactly
  that log — but the log is per-run and the record is what the analysis reads.

  The reason is now carried the last few lines to where the item is recorded,
  so an empty verdict reads `empty_final_text:<finish_reason>`. Three things
  are deliberately unchanged. A failure that happened *before* the text was
  read — an upstream error, a tool call during finalization, the iteration cap
  — still wins, because it names a more specific cause than emptiness. The
  reason is overwritten on every attempt rather than remembered from the first,
  so an item whose retry succeeded carries nothing from how it started, and an
  item that failed twice differently is filed under the second failure rather
  than the one a bigger budget already failed to fix. And the item is still
  excluded from the score exactly as before: naming the failure is a separate
  question from deciding what an unanswered item costs, and that one is open on
  its own card.

  The `finish_reason` vocabulary is bounded — a provider `incomplete_details`
  reason, a status, `max_output_tokens`, or `unknown` — so the suffix groups
  rather than fragmenting into one bucket per item. The recorded reason and the
  string that tells the retry to think cheaply are now built from one constant,
  so they cannot drift apart into a silent no-op. Consumers that count
  `baseline_empty_final_text` read a configured integer, not this string, and
  are unaffected. Regression tests in
  `batch-runner/tests/test_an_empty_verdict_says_why_it_was_empty.py`.
- **A task that takes longer than one chunk could never be graded, only paid
  for repeatedly.** `--resume` harvests *completed* `task_id`s from the partial
  on disk, so resume granularity is one whole task. A task abandoned part-way
  leaves nothing behind and the next chunk starts it from zero. That turns the
  chunk budget from a preference into a floor: below it, the task is not slow,
  it is ungradeable, and every attempt spends a chunk's worth of judging to
  learn nothing.

  Gold shard 4 of 11 found the floor. Task `9e39df84` — 57 rubric items of a
  Manufacturing deliverable — ran **4h21m against the 4h budget and completed
  nothing**. Eleven of its grading calls exhausted the config's 2400-token
  per-item output budget without returning parseable final text
  (`empty_final_text:max_output_tokens`), and the retry-without-tools cycles
  that followed account for **4h18m of the 4h21m** — 99% of the chunk's wall
  clock, measured from the run's own log timestamps. It reached 168 model calls
  against the ~146 that the six finished tasks on the same shard predict for 57
  items, so it stopped near the end rather than early. The chunk then exited 5
  rather than 7: a chunk that finished no task declines to request another paid
  resume on identical terms. That refusal is correct and is unchanged here — it
  is the reason the loss was one chunk instead of ten.

  The per-item token cap is not the lever. It lives in the grading config,
  which `compute_grader_source_hash` covers, so moving it would refingerprint
  the grader and orphan the ten shards already graded, committed and paid for.
  `.github/workflows/**` is in neither the `batch-runner` tree nor the config,
  so the wall clock is the only dial that can turn without invalidating a run
  in progress.

  That dial has now moved three times against the same task, which is worth
  recording as a progression rather than as a final number.
  `GRADER_TIME_BUDGET_SEC` went 14400 → **18000** (5h) with `timeout-minutes`
  320 → 350; the task then ran **5h10m and stopped three rubric items short of
  57**, so the budget went to **20160** (336 min) with the timeout at 355. This
  entry takes it to **20280** (338 min) and the timeout to **359**, which is
  where it stops: 338 is the remainder after the platform's non-extendable 360
  gives up one minute of reserve, 6.3 for setup, 12 for the single rubric item
  a chunk can still be inside when the guard fires, and 2 to save and commit.

  The 20160 step had a defect this fixes. Its setup allowance, 4.2 min, came
  from one run — 33286656393, which sits near the fast end. Measured across
  all ten grade jobs the spread is **2.85 to 6.27 min**, and at the worst of
  those the arithmetic closed at 356.3 min against a 355 min timeout: a
  slow-setup chunk could be killed *while saving*. Taking the worst rather
  than a sample is what moves the timeout to 359.

  20700 (345 min) was considered and rejected. It fits the path where the
  guard fires after `9e39df84` finishes, but not the path where it fires
  inside it — there the job reaches 6.3 + 345 + 12 + 2 = **365 min**, past the
  platform kill, and a platform kill does not run the `always()` steps that
  upload the cost ledger. 338 is the last value whose worst case (358.3 min)
  lands inside the timeout on both paths.

  338 has now been measured, and it is not enough. Run `33316285562` graded
  **55 of 57 items in 346.0 min** and the guard stopped it starting item 56 —
  one item further than the two attempts before it, two items short of done,
  rc=5 again. Across four attempts the work does not move but the pace does:
  **5.75, 5.81, 6.29 and 6.44 min an item**, which extend over the whole task
  to full passes of **328, 331, 359 and 367 min**. Against that the platform
  offers at most `360 − 6.3 setup − 2 save = 351.7 min` of grading, whatever
  the budget says. The two oldest paces fit; the two most recent miss by 7 and
  15 min, and no value of `GRADER_TIME_BUDGET_SEC` closes a gap in the runner's
  own lifetime — raising it further only moves where inside the task the money
  is lost.

  So the task is not too big; the pace is not ours to choose. Two of four
  observed draws would have finished, at roughly six hours of paid judging a
  draw. Both halves are asserted, because stating only the first would read as
  "impossible" and only the second as "try again":
  `test_the_platform_cannot_give_this_task_the_time_its_recent_pace_needs` and
  `test_the_two_earliest_paces_would_have_fitted_so_this_is_a_lottery`.

  The cost of stopping is **eleven tasks, not one**. `9e39df84` is 7th of 17 in
  its shard and the shard is graded in pinned order, so every resume meets it
  before the ten after it, which have never been started.
  `test_losing_this_task_strands_the_ten_behind_it` derives that from the
  committed config rather than from a run log.

  Both ways round it are refused, and the refusals are now covered rather than
  assumed: dropping the task shortens the list and trips `task_count`, moving
  it to the end keeps the count and trips `task_ids`
  (`test_the_pinned_list_refuses_both_ways_round_the_stalled_task`). Loosening
  either pin would let a shard grade fifteen of seventeen and still call itself
  complete. The remaining structural fix is a runner without the 360-minute
  kill, which is out of scope here and is recorded, not taken.

  Nine tests carry the reasoning rather than the numbers. Two assert that the
  workflow cannot enter the grader source hash — one structurally, one by
  taking the hash twice with the workflow rewritten in between and restoring it
  in `finally`. One holds the budget from both sides at once: under what a pass
  last cost, so the setting cannot be read as sufficient, and inside the
  window, so a later raise fails here instead of by losing a ledger in
  production. One pins the 2400 cap to the config, so that if it ever moves
  into the workflow the trade-off recorded above is revisited instead of
  silently becoming false.

- **Three ways a judge could be shown a deliverable and still not see what was
  in it.** All three were found by taking the lowest-scoring gold answers in the
  185-task corpus and opening the real files, rather than reasoning about what
  the reading tool ought to do.

  *A file that could not be read hid behind one that could.* The escalation
  added earlier — an item whose files yield no text goes to the path that looks
  at them — asked whether *any* selected file had text. That collapses a bundle
  to a single yes the moment one file yields a character. Task `f9f82549`
  selects a two-page incident flowchart whose pages hold **0 characters**,
  because page one is a single full-page image, alongside a readable memo. The
  bundle answered "yes, there is text here", the item stayed on the reading
  path, and the flowchart was never rendered or looked at. The narrower question
  — "is any one of these files unreadable" — is now asked as well, and either
  one escalating is enough. It shares the same per-file memo, so asking twice
  costs no extra reading, and a file that nothing could answer for still cannot
  escalate on a guess.

  *A read came back looking complete when the values were pictures.* Task
  `94925f49`, the lowest-scoring gold answer in the corpus at **15.85%**, is one
  PDF page holding a school-performance table. Extraction returns 572 characters
  — the title, the column headers and the row labels — and **every grade,
  percentage and ratio the rubric asks about is absent from the entire text
  layer**, living instead in **30 embedded images**. Nothing said so, so the read
  looked complete and the missing values read as absent from the document. A
  non-empty PDF read now reports how many embedded images it did not extract,
  which turns a silent omission into the disclosed gap the judge's existing rule
  about absence already handles. This is disclosure, not extraction: no
  threshold is guessed, and a PDF that really is all text is not accused of
  hiding anything.

  *Tracked changes and reviewer comments were invisible.* Task `5d0feb24`
  (**38.28%**) is marked on edits it carries as Word revision marks. The real
  file holds **48 insertions and 10 deletions**; a content read returns 4,218
  characters with no trace of any of them, so reading could never witness the
  thing being graded. `inspect_formatting` now reports insertion and deletion
  counts, and reviewer comments with the text they are anchored to — capped at
  50 comments and 500 characters each — and the judge's standing instructions
  now say to ask for it on a `.docx`. Without that line the judge would never
  learn the question was available.

- **A PDF table reached the judge as unrelated paragraphs.** A ruled table's row
  now arrives as one line, instead of the label and the value becoming separate
  paragraphs several lines apart. This is general robustness and nothing more.
  It was written believing it was the fix for `94925f49`, and measuring that
  task against the real file **disproved that**: extraction recovers the row
  labels, but the value cells come back empty, because those grades are
  pictures. The disclosure above is what addresses that task; this entry claims
  only what it earns.

- **The marking cost envelope was re-measured rather than left quoting the old
  length.** Telling the judge that `inspect_formatting` can now report Track
  Changes took `prompts/grader_judge_v2.md` from **6,772 to 6,866 characters**,
  and the longer tool description moved the opening every marking call carries
  from **2,825 to 2,857 tokens** and the demanded input per call from **536,159
  to 536,191**. That file is read from disk and sent on every single call, so
  its length is counted into what one call can carry. Five cost tests failed on
  the old numbers and were corrected to the freshly measured ones rather than
  loosened — the guard exists so that nobody can widen what every call carries
  without the recorded ceiling moving with it, and a guard that gets relaxed
  when it fires is not a guard. The tool-results half, 533,334 tokens, did not
  move and was left alone. The figures quoted in the earlier entries in this
  section were correct when they were measured and are superseded by these.

- **A task made entirely of music was graded without anything ever listening to
  it.** Stage-1 task `38889c3b` delivers its whole answer as one 180 MB `.zip`
  of audio stems and is marked on tempo, key, vocals, effects and mix. It
  recorded `perception_call_count: 0` and scored 41.8 of 62. The cause is one
  line of routing: an audio criterion whose files carry no audio is demoted to
  the reading path, and the test for "carries audio" was the file extension.
  `.zip` is not an audio extension, so every listening criterion on that task
  was demoted and answered by reading an archive listing. A container is a fact
  about packaging, not about the medium. New `has_audio_content()` opens the
  archive and looks, and routing now keeps the listening model on a criterion
  whose files really do hold audio. **Measured against that run's own recorded
  routing, across all 1,428 items of the 30-task cohort: exactly 10 items move,
  all of them on this one task, all of them to the listening path** (7 from the
  reading path, 3 from the formatting path). Together they hold 18 points — 9.5
  the task lost and 8.5 it already earned, which the change must not undo.
  About 5.5 of the 9.5 are reachable; the
  rest need more than the first 30 seconds, which `trim_seconds` in the frozen
  grading config fixes, or need signal measurements no listening model performs.
  The probe is used **defensively only** — it can stop a demotion, it can never
  route a criterion on its own — so "the file is named correctly" on a music
  task stays on the reading path instead of spending one of the three listening
  calls a task is allowed.
- **`audio_judge` could only be handed a whole file, so a stem inside an archive
  was unreachable even once routing pointed at it.** The tool now takes an
  optional `member`, extracts that one entry for the duration of the call, and
  cleans it up afterwards; naming an entry that is not there returns the
  archive's real contents so the next call can succeed, which is the same answer
  `read_deliverable` gives for the same mistake.
- **The blast radius is one file.** Across all 248 gold deliverable files the
  new probe answers *yes* exactly once — the stems archive above. Every one of
  the 146 Office deliverables answers *no*, because an `.xlsx` is a zip
  container but not an archive of media, so the defect PR #93 fixed ("Sound
  Technician fees" on a tour budget routing to audio) stays fixed and is now
  pinned end-to-end rather than at the routing call alone. One gold `.zip` will
  not open at all; the probe reports *unknown* rather than *no*, which leaves
  the existing extension rule in charge instead of promoting towards a file
  nothing can extract.
- **The listening model was handed the first 30 seconds of the deliverable and
  then asked about 1:22.** With the routing above fixed, task `38889c3b` grades
  at **45.5 of 62 (73.39%)** with `perception_call_count: 6` and nothing
  excluded — and three of its items are *still* failed for a reason that is not
  a property of the work under test. Each names a region the clip could not
  reach, and one sub-judge wrote the defect out itself: *"The clip only includes
  the first 30s, ending well before 1:49."* It listened, it reported honestly
  what it had been given, and the harness recorded that as a finding about the
  deliverable. **6 points, across the items asking about 1:22–1:49, 1:49–end,
  and the beginning through 1:22.**

  The clip now opens where the criterion is looking. A criterion naming a region
  that begins after the head slice *ends* — and only such a criterion — moves
  the window there, using the tolerance the rubric states rather than one we
  guess (`1:49 (+/- 2 s)` opens at 1:47). Anything anchored at the beginning,
  naming no time, or naming a time already inside the slice is untouched, so
  *"From the beginning ... through 1:22"* keeps the head it needs. **Neither the
  number of calls nor the length of the clip changes** — the same 30 seconds at
  the same encoding, cut at a different offset — so the set of items that can
  move is exactly the set that cannot be answered from the audio sent today,
  and `start_seconds=0` is byte-for-byte the path it has always been.

  The system prompt now names the span it is actually carrying instead of
  claiming "first 30s" of everything, which is the half of the defect that made
  the wrong verdicts look well-grounded. Where a window is wanted and cannot be
  cut, the two reasons are kept apart because they deserve opposite verdicts: a
  deliverable that genuinely ends before the timestamp is a fact about the work
  and is graded as one, while a file this machine could not decode is a fact
  about us, and there the sub-judge is told to return `judge_error` and say what
  went unheard. That line is drawn from the file's own frame timestamps, never
  from silence — a container that reports no times at all cannot be read as a
  short deliverable. Absence of observation is not observation of absence.

  One more link had to hold for any of this to reach a real run. `audio_judge`
  grades whatever criterion string the *main* judge passes it, and nothing
  obliged that string to be the rubric's own words — a summary such as "check
  the bridge thins to synths" carries no time, leaves the window at the head
  and fails the item exactly as before. The tool now asks for the criterion
  verbatim and says which words are load-bearing, and its description no longer
  advertises "the head-30s slice" of the file it is about to be given.
- **An empty read was treated as proof the content was absent.** On stage-1
  task `43dc9778` the judge read a two-page scan that has no text layer,
  `read_content` returned `"text": "", "char_count": 0`, and **ten rubric items
  about that document's contents were failed on that alone — 13 points** — for
  a document that says all ten things, on pages the harness had already
  rendered for the same task's other items. Reads that come back empty now say
  *why* (no text layer, an unsupported kind, a genuinely empty file) and name
  the op that can still answer, and the judge's standing instructions now say
  that "I could not read it" is not "it is not there". A second, narrower net
  routes an item whose files *all* fail to read to the path that looks at them
  instead: only a *measured* "no text" counts, only text and formatting items
  escalate, and every selected file must be renderable, so it can only fire
  where the run currently produces `required_visual_render_target_unavailable`
  anyway. **Measured across all 1,428 items of the 30-task gold cohort, that
  escalation fires on none of them** — the one text-less file in the corpus is
  always selected alongside a readable companion — so on this cohort the repair
  is the honest empty result and the instruction that goes with it, and the
  added vision cost is zero.
- **"Does it fit on one page" was answered from a character count.** A `.docx`
  stores no pagination — the number does not exist until something lays the
  document out — so six stage-1 items asking about length were answered from
  `paragraph_count` or `char_count`, and five were marked down against gold
  answers that were the right length. `inspect_structure` now converts with the
  same LibreOffice the render path uses and reports `converted_page_count`; a
  missing converter costs that one number and nothing else. Separately, a gold
  answer lost an orientation item because the only geometry a judge could see
  was `page_count: 1` — the page was 432×288, landscape, exactly as asked — so
  both PDF ops now report page sizes, orientation and whether the pages are
  uniform.
- **The judge's standing instructions got longer, so the marking cost envelope
  was re-measured instead of left quoting the old length.** Telling the judge
  what an empty read means, and which op can still answer, took the committed
  `prompts/grader_judge_v2.md` from **6,263 to 6,772 characters**. That length
  is not decoration: the file is read from disk and sent on every single
  marking call, so it is counted into what one call can carry. The opening
  every call carries rises from **2,656 to 2,825 tokens** and the demanded
  input per call from **535,990 to 536,159**. Running the free check on this
  branch and on `main` shows those figures are the *only* difference in its 98
  lines of output — the same 14 problems, the same ceiling, the same approved
  maximum, the same non-zero exit. The figures quoted in the earlier entries in
  this section were correct when they were measured and are superseded by
  these. Five cost tests failed on the old number and were corrected to the new
  measurement rather than loosened: a length that has stopped matching the file
  is precisely what those tests exist to catch.
- **Every request was charged 1,068 characters for wording that renders to
  between 3,533 and 5,020, and 345 of the 1,068 were for wording no model ever
  reads.** `instruction_character_count` pays for everything a request carries
  besides the task's own words and its reference files, and it is charged on
  every call every run place makes. The plan reached 1,068 by adding up the two
  wording blocks it keeps in `model_run_conditions`, and both halves of that
  were wrong in the same direction. The `system_instruction` block it counted
  is **never sent** — `core/prompt_loader.py` lets a committed prompt file's own
  `system_message` win whenever it has one, and all three committed files have
  one — while the committed prompt file itself, which is the great majority of
  what is sent, **was not counted at all**. The container's first request comes
  to **5,020 characters**, not 1,068: short by **3,952 on every call**.
- **Measured by rendering the prompt, not by adding up lengths written down a
  second time.** New `fixed_prompt_characters()` renders each run place's
  prompt file through the same `render_prompt()` an attempt is built with, once
  alone and once wrapped in that place's `condition_a.prompt` block, and reports
  what each part added — so the parts come to the length of a real render by
  construction, and a refusal can say what the total is made of. The task's own
  words are the one thing left out, because `max_input_tokens_per_call` already
  charges them per task and counting them here would bill them twice. Editing
  any of that wording moves the demand with it; no test in the new file types
  5,020.
- **The occupation is read from the catalogue, because the prompt writes it in
  up to three times.** New `widest_occupation()` takes the longest name across
  all 220 tasks — a benchmark fact from the pinned dataset column, not a
  setting — so a plan running five tasks is held to the widest name any of them
  could carry. An empty catalogue is **refused** rather than priced with a
  prompt that names nobody.
- **A prompt file named in the settings is priced alongside the runner's own,
  and the longer is charged.** `core/executor.py` follows
  `execution.sandbox.prompt_name` on the sandbox branch and reaches straight
  past it on the subprocess branch, so which of the two a run place takes is
  settled by wiring the check cannot read back. Charging the longer leaves no
  arrangement of settings under which the prompt really sent exceeds the prompt
  priced.
- **Unreadable means refused, not skipped.** A settings file the plan does not
  name, a settings file that is not there, one that holds no mapping, a named
  prompt missing the keys `load_prompt` requires, a run place no runner serves,
  or wording that will not render: each returns a refusal naming the run place
  and what could not be built. Fourteen mutations of the rule — including the
  original defect, restored — were each caught by a test.
- **What is still not priced, named rather than implied.**
  `SandboxRunner._augment_prompt` adds a deliverable contract section, a
  dependency hint and a skills manual the committed settings switch off to the
  container's **first** request. Those sit outside `render_prompt`, so the
  demand made of the container is smaller than the container's real request.
  This rule under-demands there; it never lets a plan claim more than the render
  proved.
- **The ceiling moves from 363.59 to 364.00 United States dollars.** Running the
  tasks rises from 21.00 to 21.33; marking (269.87) and perception are
  unchanged. Nothing has been spent under any of these figures — the plan is
  refused on cost either way, against an approved maximum of 32.23, and this
  correction does not ask for a new approval.
- **Agentic Sandbox V2 stage one moved with it, which is the borrowing working.**
  `experiments/execution_envelope/agentic_stage_one_plan.yaml` reads its
  assumptions out of the comparison's plan rather than keeping a second copy,
  so raising `instruction_character_count` there raised every row of the
  stage-one table here: the cheapest row goes from **3.24 to 3.32** to run and
  the dispatcher's own defaults from **492.67 to 493.33**.
  `tasks/0822_saturday/TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md` is updated to
  match. **None of these is an approved amount**, no row has been chosen, and
  the three refusals that keep a real model out of the stage-one loop are
  untouched.
- **A separate, older understatement in the stage-one specification, found
  while checking the figure above.** That document said "marking the answers
  adds 5.85 whichever row is chosen, so a total is the running figure plus
  5.85". Both halves were wrong in the expensive direction: 5.85 predates the
  correction that made marking a real ceiling, and looking at the answers was
  left out of the total altogether. `scripts/check_agentic_stage_one_ceiling.py`
  prints **89.95** to mark and, on top of it, **22.50** to look, on every row —
  so the cheapest row's real total is **115.77**, not the 9.17 the old sentence
  implied, an understatement of about 106 dollars. No code changed; the
  specification now quotes the check's own columns, including its total column,
  rather than carrying figures over by hand. Nothing has been spent under either
  figure: stage one has no approved amount at all and cannot reach a model.
- **Two tests that pin the ceiling were updated by hand, on purpose.**
  `test_the_ceiling_is_unchanged_because_the_constant_did_not_move` and
  `test_the_committed_plan_draws_no_refusal_from_the_free_check` each assert the
  total outright, so a correction to the cost arithmetic makes them fail until
  somebody looks at the new figure and writes it in. Both now read
  **363.99643750**, and both say in their docstring which correction moved it.
- **The container's repair prompt was priced at three of its eight parts,
  because the other five were called unmeasurable.** When a container run
  fails, `core/sandbox_runner.py` asks the model for the code again and sends
  the failed run's own record along with it.
  `core/execution_envelope_preflight.py` demands the plan pay for what that
  second request carries, and it counted the stdout tail, the stderr tail and
  the failure tail — **2,200 characters, 734 tokens** — on the stated grounds
  that the blocking errors, the warnings, the repair guidance and the fixed
  headings "have no fixed width". Every one of those had a width available in
  this repository: the render trims blocking errors to **12** lines and
  warnings to **6**, the repair guidance is written in a committed
  `prompts/*.yaml`, a deliverable contract section is appended on every repair
  prompt whatever the task, and the opening, instruction, close and headings
  are strings. The real figure is **3,922 characters, 1,308 tokens** — the
  omission understated it by **78%**.
- **Measured by building the prompt, not by adding up widths written down a
  second time.** `widest_repair_prompt_characters()` renders the widest repair
  prompt the committed wording allows through the same new
  `render_reflection()` that a real repair turn renders with, adding one part
  at a time and recording what each part added — so the parts sum to the
  length of a real render by construction, and the refusal can say what the
  total is made of. `SandboxRunner._build_reflection` now delegates to that
  same function (the golden-output test confirms the rendered block is
  byte-identical), the limits are named constants, and the failure line is
  built by one shared `execution_failure_blocking_error()`. Neither `3922`,
  `1308`, `12` nor `6` appears in the rule that spends them: editing a heading
  in `prompts/sandbox_occupation_codegen.yaml`, changing a limit, or adding a
  repair-guidance entry moves the demanded figure on its own.
- **An unreadable prompt is now a refusal rather than a cheaper answer.** The
  measurement raises when `load_prompt` cannot find, parse, or validate the
  prompt the settings name, and the rule turns that into a problem instead of
  falling through it — including when the plan prices the place at nothing, so
  reading the plan's figure first can no longer let an unreadable prompt pass
  in silence. The prompt measured is the one `execution.sandbox.prompt_name`
  names, matching what `core/executor.py` hands the runner; naming a different
  committed prompt changes the answer to 3,056, which a test asserts. With the
  repair loop off, an unnameable prompt produces nothing — the rule stays
  scoped to runs that would really carry it.
- **The exemption list this sweep carried is now empty, and had to be
  earned.** `test_marking_ceiling_has_no_uncapped_part.py` allowed exactly one
  production string to say a bill had no top. `STILL_OPEN_ELSEWHERE` is now
  `()`, paired with a `CLOSED_HERE` entry asserting the excusing sentence is
  really gone from the source rather than merely dropped from the list.
- **The free check's report is unchanged: 11 problems, `may_start` still
  false.** The committed container file has `repair: enabled: false`, so
  nothing was being under-charged today. What this closes is the case where
  someone turns that one line on: at 220 tasks and one repair each, the
  understatement was **574 tokens a turn, about $0.20** with the safety
  multiplier. Small, and saying so is part of the finding — the defect was a
  figure the source could have settled, not a large sum.
- **The marking-cost floor left out what every marking conversation opens
  with, and said so in a sentence that named one of the caps it was
  denying.** `core/execution_envelope_grading_cost.py` demands that a plan
  price at least what one marking call can carry. It counted the
  `read_deliverable` results and stopped, on the stated grounds that the
  opening — "the standing instructions, the scoring line being judged, and the
  first 500 characters of the task" — "is not capped by anything". Two of
  those three are pinned by this repository. The standing instructions are a
  committed file named by `prompt.tool_template`, which `ToolCallingJudge`
  splits in two and sends **both halves of on every single call** (one as
  `instructions=`, one inside the message); it is **6,263 characters** today.
  The task preview is cut to `ToolCallingJudge.task_prompt_truncate`, which is
  **500**, and every one of the 220 committed tasks is longer than that
  (shortest 617 characters), so the cut is always taken in full.
- **The direction of the error is the one that costs money.** Omitting the
  opening made the demanded floor **lower** than the truth, so a plan could
  clear a floor that was too low and be recorded as checked. The floor rises
  from **533,334 to 535,589 tokens** a call — the 2,255 the opening adds. Both
  pieces are read from where the marking run reads them, so a longer
  instruction file raises the demand by itself instead of leaving this module
  quoting a number that has stopped being true. Characters, not bytes: the
  ratio is characters-per-token, and the instruction file holds multi-byte
  characters (6,267 bytes, 6,263 characters).
- **The figure was still described as a floor, on a reason that was wrong.**
  The third piece was said to be uncapped — the scoring line comes from the
  dataset and no *setting* bounds its length — so the refusal and
  `describe_grading_caps` both went on saying that a plan above this number
  might still not be a ceiling. That reason does not hold, and the entry below
  in this same block closes it. Settings that name no instruction file, or name
  one that is not on disk, are now **refused rather than priced at nothing**,
  and the refusal names the settings file so a reader knows which one to open.
- **`grader.task_prompt_truncate_chars` reaches nothing, and now says so.**
  Nine settings files carry the key, every one saying 500, and no module reads
  it: `core/grader.py` builds `ToolCallingJudge` without passing it, so the
  judge applies its own default and the setting has never taken effect. The
  cost check therefore counts the **applied** width, not the written one, and
  reports the setting as ignored when the two disagree — a width an operator
  can edit without effect is how a number stops describing the run it sits
  next to. No new problem fires today, because all nine happen to agree with
  the default.
- **Nothing else moved.** The cost ceiling is unchanged at **363.59 United
  States dollars** (363.58481250 before rounding), the free check reports the
  same 14 problems, blocks the same run places, and still exits non-zero. The
  report differs from the old one in exactly one line, and a test asserts that
  by running the check twice with the new counting patched out — no dependence
  on which machine it runs on.
- **How many perception calls one task gets was written by hand in four
  places, and nothing bound them together.** Marking may call a second model
  to look at a picture and a third to listen to a sound.
  `core/perception/vision.py` defined `VISION_CALL_CAP = 5`;
  `core/perception/audio.py` defined `AUDIO_CALL_CAP = 3` and
  `AUDIO_TRIM_SECONDS = 30`; `core/grader.py` typed `5`, `3` and `30` again as
  its own fallbacks, never once consulting those constants; and
  `core/execution_envelope_grading_cost.py` typed `5` and `3` a third time.
  All four agreed, so nothing was wrong today — but the free check refuses a
  plan that allows fewer perception calls than the settings permit, so
  whenever a settings file leaves `call_cap_per_task` out, its copy **is** the
  figure the refusal is measured against. Raising what the run falls back to
  without raising that copy would have let marking make more calls than the
  ceiling was ever asked to cover: **understating the bill**, the same
  direction as the two defects before it. Every reader now imports the one
  constant.
- **The guard that was cited as covering this could not reach it.** The note
  above the settings paths named
  `test_the_limits_read_match_the_judge_the_grader_really_builds` as the thing
  that stopped these fallbacks going stale. That test builds the real judge
  from the **committed** settings, and all nine name their own caps — so the
  fallback was never reached on either side of the comparison. The guard was
  real; the claim about what it guarded was not. The same comparison now also
  runs against settings that name perception models and no caps at all, which
  is the only shape that reaches a fallback.
- **Both constants called themselves a "Hard per-task ceiling", which they
  never were.** `call_cap_per_task` in the marking settings replaces the
  number, and the grader passed whatever it found there on every construction.
  The notes now say what each one is — the figure used when the settings name
  none — and which key replaces it.
- **Nothing moved today.** The free check's output is **byte-identical** to
  the previous commit's: same exit code, same 14 problems, same ceiling of
  **363.59 United States dollars** (363.58481250 before rounding). Every
  committed settings file names its caps, so no fallback is in use; this
  closes a latent defect rather than correcting a live number. 41 new tests,
  and a mutation sweep breaks the rule 12 ways and is caught 12 times.
- **The free check printed a total it called the largest possible bill and, in
  the same report, called one part of that total uncapped.** The marking
  refusal in `core/execution_envelope_grading_cost.py` ended: "So one call can
  carry 535589 tokens, and that is still a floor: the scoring line being judged
  is not capped by anything." Both sentences cannot be true at once — if a part
  of a sum has no upper bound the sum has no maximum — so the check was either
  quoting a ceiling it did not have or denying one it did. It was the second.
- **The scoring line was never capped by a *setting*, which is not the same as
  being unbounded.** It lives in the `rubric_json` column of the dataset file
  the check already locates and already verifies to all 64 characters of its
  fingerprint, at a revision it also pins, and nothing between that file and
  the judge shortens it. Measured from the pinned parquet: **220 tasks, 10,453
  scoring lines, none blank and none non-text**; the per-task longest runs from
  **94 to 1,203 characters**, the widest being task
  `0353ee0c-18b5-4ad3-88e8-e001d223e1d7`. A fixed, readable number had been
  described as no number at all.
- **The width is now measured where the catalogue is built and demanded where
  the bill is checked.** `scripts/build_gdpval_task_catalog.py` records
  `widest_rubric_criterion_characters` per task, refusing a criterion that is
  missing, not text, or blank rather than writing a zero.
  `CatalogTask` carries it as a **required** field, `catalog_number_problems`
  refuses a zero the same way it refuses a task nobody marks, and
  `widest_scoring_line_characters` takes the maximum across all 220 tasks — not
  across whichever tasks a plan selects, so the demanded figure cannot move
  when the selection moves. The catalogue schema is now
  `gdpval-task-catalog-v2`, so a file written before the width existed is
  refused by name instead of read with a piece missing. The rebuilt catalogue
  reproduces the same `dataset_file_sha256`; `--check` reports a match.
- **A width nobody measured is refused, and so is a width of zero.**
  `GradingCaps.characters_of_widest_scoring_line` defaults to `None`, meaning
  *nobody looked*, and both the opening arithmetic and the plan check raise or
  report rather than leaving the scoring line out of the sum — leaving it out
  does not make it free, it makes the marking total smaller than the bill. Zero
  is refused too: no scoring line in this benchmark is blank, so a zero is a
  reading that failed rather than a line with no wording in it, and accepting
  it would re-open the same defect through the other door.
- **What actually changed in the report: one line.** The opening every marking
  call carries rises from **2,255 to 2,656 tokens** and the demanded input per
  call from **535,589 to 535,990** — the 1,203 characters of the widest scoring
  line at the plan's own 3.0 characters-per-token ratio. The sentence claiming
  the figure was still a floor is gone, and the description now says the
  figure is a ceiling rather than a floor. Everything else is unchanged: the
  same **14 problems**, the same ceiling of **363.59 United States dollars**
  (363.58481250 before rounding), the same approved maximum of **32.23**, the
  same non-zero exit. Verified by running the check on this commit and on its
  parent and diffing the two reports: exactly one line differs.
- **One instance of the same contradiction is still open, and is now named
  rather than left to be found again.** `core/execution_envelope_preflight.py`
  tells a reader that what a container carries into a later turn is charged at
  a figure that "is a floor — the blocking-error lines, the warnings, the
  repair guidance and the contract section have no fixed width at all". That is
  the identical shape in the run half of the check. It is a different
  measurement — those four kinds of line are produced by `core/sandbox_runner.py`
  at run time, not read from a pinned dataset column — so it is recorded as
  open, exempted by name in the sweep, and a test fails if the exemption ever
  stops pointing at something real.
- **254 new tests**, including a 220-way sweep that empties one task's width at
  a time, and a mutation sweep that breaks the fix five ways — dropping the
  scoring line from the sum, letting a zero through the guard, defaulting the
  width to a number, taking the first task instead of the widest, and cutting
  the catalogue off from the marking check — and is caught five times out of
  five.

- **The task catalogue recorded a count of zero for anything it could not
  read, and a zero is priced as work that costs nothing.**
  `scripts/build_gdpval_task_catalog.py` read all four of its measured columns
  as `row.get(name) or <empty>`. A renamed column, a null, or a rubric that
  would not parse therefore became `[]` or `""`, and was written down as a real
  measurement rather than as something nobody could find. The number that
  matters most here is `rubric_item_count`: marking is charged per scoring
  line, so zeroing it across all 220 tasks drops the cost ceiling from
  **363.59 to 93.75 United States dollars** — 269.84 of it gone, about three
  quarters — while every free check still reports a clean, matching catalogue.
- **Nothing caught it, at four separate points.** `TaskCatalog.from_mapping`
  accepts any whole number, so a zero loads. `catalog_score_problems` answers a
  different question (no scores are present) and answers it correctly.
  `test_a_whole_number_is_still_a_perfectly_good_count` explicitly blesses a
  zero. And `--check` rebuilds with the same code, so it reproduces the same
  zeros and reports a match — the docstring now says so, and a test fails if
  that sentence is ever deleted.
- **The builder now refuses rather than substitutes.** It names the columns it
  reads in one place, refuses a dataset that does not hold them (naming what
  the file *does* hold, so a rename is visible rather than guessed at), refuses
  a row holding a null under any of them, and refuses a rubric that will not
  parse or that is not a list of scoring lines. An empty list stays a real
  answer: a task shipping no reference files still builds, because 95 of the
  220 really ship none. The rebuilt script reproduces the committed catalogue
  byte for byte from the pinned dataset revision.
- **`catalog_number_problems` refuses the zeros that cannot be true**, in
  `core/execution_envelope_tasks.py`, and the free advance check now asks it of
  the catalogue in play before the cost ceiling is worked out from those same
  numbers. Three rules, each resting on a measured fact about this benchmark: a
  task nobody marks (real range 14–137 scoring lines, no zeros), a task with no
  wording (617–6,618 characters, no zeros, 220 distinct fingerprints, none the
  empty-string hash), and a count that disagrees with the paths it was written
  from. A count of reference files being zero is refused by nothing. Only the
  direction that makes the work look smaller is refused; a count that is too
  large would merely overstate what a run might cost.
- **The cost sum charged every reference file at 50,000 characters and named,
  as its authority, a cap the pipeline never reaches.** The comment on
  `REFERENCE_FILE_CHARACTER_CAP` in `core/execution_envelope_cost.py` said the
  figure was "the cap `core/file_reader.py` applies when it reads a reference
  file". That module's 50,000-character cut is dead code: `read_all_references`
  is reachable only through `PromptBuilder.build`, and `PromptBuilder` is
  constructed nowhere the pipeline runs — `main.py` does not exist in this
  repository, and the sole construction anywhere is a test patching
  `main.PromptBuilder.from_preset`. No step file mentions it. The reference
  text that really reaches a model comes from `core/file_preview.py`, whose
  caps nothing was holding the constant against.
- **The real caps are an order of magnitude lower, and two things have no cap
  at all.** `core/file_preview.py` cuts each preview at 3,000 characters and
  all previews together at 10,000. Counting the file name that goes into a
  header written *after* the cut, and this file's share of the block wrapper
  that sits outside the running total, the widest a single reference file can
  add through every section any run place fills is **3,814 characters** —
  leaving the constant **46,186** above what it bounds. Over-charging is safe,
  so the constant stayed at 50,000 and is now *required* to stay above. Two
  things genuinely have no ceiling anywhere in this repository: the column
  headers `build_file_structure_info` lists, one line per sheet with no cut,
  and the file names outside the cap. `reference_file_prompt_budget` reports
  those as unbounded rather than inventing a number for them — a figure that
  looks checked is worse than an admission that it is not.
- **Each run place now says which prompt sections it fills from the reference
  files, and the arithmetic is read rather than copied.**
  `SubprocessRunner` and `SandboxRunner` declare all three sections
  (`file_structure`, `previews`, `available_files`); `CodeInterpreterRunner`
  declares only `file_structure`, because the files themselves go up as
  container attachments and arrive as tool results already priced by
  `max_tool_result_tokens_per_turn` and the carried-forward input assumption.
  `core/execution_envelope_preflight.py` asks `core/file_preview.py` what those
  sections cost per file and refuses a plan whose per-file charge has fallen
  below them. Only that direction is refused; a run place whose runner is
  unregistered or declares nothing is refused too, matching the rule already
  applied to exempted settings and to one-cap-per-attempt. The budget is
  computed on every call, not frozen at import, so raising a cap moves it.
- **Today the new rule is silent, and that is now proved rather than asserted.**
  The free check's report is byte-identical with the rule wired in and with it
  patched out, and the ceiling stays at **363.58 United States dollars** — the
  constant did not move, only its justification and the check around it. No
  problem count is asserted, because that number differs between this machine
  and a build server that has neither the container nor the Azure route.
- **Whether one cap on answer length covers a whole attempt was three
  hand-written booleans, and nothing anywhere held them to anything.** It is
  the largest single divisor in the cost sum: `core/execution_envelope_cost.py`
  computes `answers_per_attempt = 1 if output_tokens_capped_per_attempt else
  tool_loop_max_model_turns`, and the input side either charges every earlier
  answer once each (`turns - 1`) or on the growing sum (`turns × (turns − 1) ÷
  2`). Flipping Azure's `true` to `false` moves the ceiling from **363.58** to
  **413.76 United States dollars** — Azure's own line from 14.06 to 54.20, a
  factor of 3.86, and a **50.18-dollar** swing on a comparison approved at
  32.23. The container fails in the direction nobody goes looking for: at the
  two turns task #27 made reachable, a wrong `true` *lowers* the ceiling from
  368.95 to 364.85, so the extra turn reads as free.
- **The answer is readable from the shape of the request, so it is now read.**
  `CodeInterpreterRunner.run` issues exactly one `responses.create` an attempt,
  with the code interpreter attached to that same call and one
  `max_output_tokens` on it; `SandboxRunner.run` repairs with an ordinary
  Python `for` loop that calls `complete` again with the whole
  `max_completion_tokens`; `SubprocessRunner.run` calls it once and runs the
  code itself. Each runner now declares `SENDS_A_FRESH_REQUEST_PER_TURN`, the
  three constants are proved by driving the runners with the model call patched
  out and counting requests, and `core/execution_envelope_preflight.py` refuses
  a plan that claims one cap where the repository itself opens a fresh one each
  turn. Only that direction is refused — claiming a fresh cap where one really
  covers the attempt over-charges, which is safe.
- **A `true` for a run place whose runner says nothing is refused too.**
  Nothing looked is not a pass, matching the rule the settings comparison
  already applies. That covers Codex, which has no runner registered, and the
  Agentic Sandbox V2 fixture runner, which is deliberately left undeclared
  because it makes no model calls and no request shape would be true of it.
- **The plan's four lines of prose are replaced by a comment that separates
  what was checked from what cannot be.** That the Azure request is one call
  carrying one cap is now read from `core/code_interpreter.py`. Whether Azure
  *honours* that cap across the tool turns it takes inside that request is
  Microsoft's behaviour, taken on the documentation's word — the same class of
  fact as `tool_loop_max_model_turns.azure_code_interpreter: 8`, which the plan
  already flagged as unreadable here. If it does not hold, the honest value is
  `false` and the ceiling rises about 50 dollars. The comment now says so.
- **The check is silent on the committed plan, and that is the correct
  result.** Azure is the only `true` and Azure really does ask once, so the free
  check's report is word for word what it would be with this rule switched off
  — which is how the test states it, holding the two runs against each other
  rather than naming a problem count. That count is a property of the machine,
  not of the rule: a build server with no container daemon and no Azure route
  has more to say than a workstation with both. The ceiling, which is not
  machine-dependent, stays **363.58 dollars**. Two tests drive the public entry
  and the whole free check with a wrong `true` in the plan, so deleting the
  wiring fails a test rather than passing quietly.
- **The container's carried-forward input was priced at nothing, on the written
  grounds that "the model is asked once and nothing is carried forward".** That
  is a property of one line in the container's settings file — `repair:
  enabled: false` — not of the run place. `core/sandbox_runner.py` builds its
  repair settings as `{"enabled": True, "max_attempts": 1, **(repair or {})}`,
  so deleting the block turns the loop *on*; and once it is on,
  `_build_reflection` writes the run's own output into the next request: the
  last 800 characters of what the code printed, the last 800 it printed as an
  error, and the 600-character tail of the failure that stopped it. Those three
  widths are now named constants in the runner, and
  `core/execution_envelope_preflight.py` reads them rather than quoting figures
  of its own. It refuses a plan whose `max_tool_result_tokens_per_turn` for the
  container sits below **734 tokens** — 2,200 characters at the plan's ratio —
  whenever the container's own settings would really loop. Today they say the
  loop is off, so the check is silent and the plan's `0` stands; it stops being
  silent the moment that one line changes. Task #27 made the extra turn
  readable but left what the turn *carries* priced at zero, and this closes
  that half.
- **What the `0` was hiding, measured: about two pennies, and rising.** With
  repair switched on at one attempt the ceiling moves from **368.95** to
  **368.97** United States dollars; at two attempts the gap is 0.07, at three
  it is 0.14. Small, and said plainly rather than dressed up — the defect here
  is a sentence that is false in a reachable setting, not a large sum. The
  figure is a floor: the same repair prompt also carries up to twelve
  blocking-error lines, up to six warnings, the repair guidance and the whole
  contract section, none with a stated width. The prior code is deliberately
  left out, though the prompt carries up to 4,000 characters of it, because
  `max_input_tokens_per_attempt` already charges a full `max_output_tokens` for
  every earlier answer.
- **A rule nobody calls refuses nothing.** Deleting the new check from the free
  check's wiring left all 34 of its first tests passing, because every one of
  them called the rule directly. Two more now copy the plan's settings files to
  a temporary directory, switch the container's repair loop on there, and ask
  the free check the way a person would.
- **Marking was priced at 10,000 tokens of input a call. The settings permit
  533,334, and both the plan and the checking module said in writing that no
  settings file could pin the number down.** They can. The judge never sees the
  answer whole: it asks for pieces through `read_deliverable`, that tool ends
  every content read with `text[:MAX_CONTENT_CHARS]` — 200,000 characters — and
  `judge.tools.read_deliverable.per_item_call_cap` says how many results may
  pile up for one scoring line. Eight, in the committed settings.
  `core/tool_calling_judge.py` appends each result whole and every later turn
  sends the conversation again, so one call can be carrying 8 × 200,000
  characters. `core/execution_envelope_grading_cost.py` already read the call
  cap, and already described it as a number where each result "is re-read by
  every later turn" — then charged nothing for it. It now does the
  multiplication, reading the payload cap off the tool module rather than
  typing it again, and refuses a plan that prices less. Measured on the
  committed plan: the ceiling it reports is **363.58 United States dollars**;
  with the number the settings actually permit it is **7,568.42** — a gap of
  **7,204.84 dollars** the plan called impossible to know.
- **The one thing that still cannot be pinned is now said precisely instead of
  broadly.** What the marking conversation *opens* with — the standing
  instructions, the scoring line, the first 500 characters of the task — is
  capped by nothing. So the figure the check demands is a floor on the largest
  a call can be, not the largest itself, and `describe_grading_caps` prints
  both the figure and that caveat. The old wording said the whole number was
  unknowable, which is how a readable limit went unread.
- **The ceiling rounded itself down.** The new arithmetic first used
  `-(-tokens // 1)` to round up, but `Decimal`'s `//` truncates towards zero
  rather than flooring, so it rounded a ceiling **down** — 533,333 where the
  answer is 533,334. It now uses `ROUND_CEILING`, the same as the rest of
  `core/execution_envelope_cost.py`.
- **Two tests were carrying the same wrong claim, and they were the ones
  guarding it.** `tests/test_execution_envelope_advance_check.py` said in a
  docstring that "everything there that a measurement could settle has been
  settled" and named the unpriced sound model as the only survivor, while a
  helper set the whole marking gap aside for six other tests. That was the
  sentence that made a measurable gap look like a settled one. Both now name
  the two remaining items separately — the sound model, which no measurement
  exists for, and the input-per-call figure, which is measured and left low in
  the plan on purpose — and assert that there is nothing else in the set-aside
  list.
- **The cost sum priced the container's attempt at one call to a model. Two
  deleted lines make it two, and the sum would not have moved.** The plan's
  `cost.assumptions.tool_loop_max_model_turns` is written by hand, one number a
  run place. For two of the three it has to be: a separate Python process on
  the server has no loop at all, and what Azure's tool loop does inside itself
  is not readable from here. The container is the third, and its real number is
  sitting in a file in this repository. Nothing was reading it. `repair` asks
  the model for the code again, as often as its budget allows; `output_qa.vision`
  sends rendered pages to a vision model once for every go at the code — and
  `core/sandbox_runner.py` builds its settings as `{"enabled": True, ...}`, so
  deleting the `repair` block turns the loop **on**. Measured on the committed
  plan: delete those two lines and the container's quoted cost stays at
  **20 calls and 3.47 United States dollars, unchanged**. `core/execution_envelope_preflight.py`
  now works the number out of the container's own settings — taking the runner's
  defaults off `SandboxRunner` rather than typing them again — and refuses when
  the plan prices fewer. It refuses only when the plan is *below* the settings,
  so a number that has to be a chosen limit stays one.
- **The staleness was hidden under one comparison and invisible under the
  other.** Under `same_generated_code_rerun` a different rule refused the run
  for its own reasons, so the too-low ceiling never surfaced. Under
  `tool_built_in_features` — a comparison the same plan names, with a scoreboard
  of its own — nothing refused at all. The new rule holds under both, because a
  ceiling is a ceiling either way, and the comparison that leaves each tool its
  own features running is exactly the one where the container's loop is meant to
  be on.
- **A picture check at another model was counted at the run model's price.**
  `output_qa.vision.deployment` names whatever model it likes, and
  `core/output_qa.py` passes the name straight through. Counting that call and
  pricing it at the compared model's rate is still a wrong sum, so it is now
  reported in a sentence of its own — as is a picture check switched on that
  names no model at all, which cannot be priced from the settings at any rate.

- **The gate said "the fingerprints of every input file are checked against the
  dataset". Nothing read a byte of any file.** `check_input_file_versions` in
  `core/execution_envelope_tasks.py` compared the first 32 of each
  fingerprint's 64 characters against the folder name in the file's own path —
  this benchmark keeps a reference file in a folder named after the start of
  its fingerprint — and called that a match. The other 32 characters were
  compared against nothing at all. Running every single-character change, at
  every one of the 64 positions, against all three fingerprints the committed
  plan pins: **210 changes tried, 70 went unnoticed, and now none do.** All 70
  were on the two reference files, 35 each: the 32 positions past the halfway
  mark, plus swapping the whole second half for the tail of the other reference
  file, of the dataset fingerprint, or of an unrelated file. The dataset's own
  fingerprint was already fully compared, against the catalogue. The check now
  finds a copy of each file already on this machine, hashes it, and compares
  all 64 characters. It never downloads: it asks the Hugging Face download
  cache about that one file at that one pinned revision, or reads a folder
  named with the new `--dataset-root` option.
- **A path of a different shape had nothing compared at all, and was reported
  as fine.** The folder rule only ran when the folder name was exactly 32
  characters long. Any other path skipped the comparison and produced no
  complaint, which is the one answer that was certainly wrong. Such a path is
  now reported as unchecked.
- **A fingerprint nobody could compare is no longer silence.** When no copy of
  a file is reachable, the report now says so per file, with how many of the 64
  characters were compared and the free command that fetches the rest. The
  advance check prints the state of every input file whether or not anything is
  wrong, because "read off this machine and matched" and "assumed correct" are
  different answers and the person authorising a bill is entitled to know which
  one they are looking at. This follows the same rule the Docker probe already
  used: not measured is reported as not measured, never as ready.
- Where a copy is found matters to what a disagreement proves. A reference
  file's path repeats the first half of its own fingerprint, so a copy found
  there can only be that file and a mismatch means the written value describes
  some other file. The dataset's own data file carries no such promise, so a
  mismatch against a copy in a folder somebody pointed at is reported as what
  it is — that folder may hold a different revision — rather than as tampering.
- **"Could not check" and "does not match" are now two lists, not one.** They
  answer different questions: a disagreement means the plan pinned the wrong
  file and says the same thing wherever the check runs, while a missing copy
  means only that this machine has not downloaded the benchmark yet. Both still
  stop a run and both are still printed together, but
  `InputFileVerification.missing_copies` and
  `EnvelopePreflight.missing_input_file_problems` name the machine-dependent
  half. Without that name, six tests asserting "and nothing else is wrong"
  passed on a machine holding the dataset and failed on a fresh build runner —
  and the only way to fix them by hand would have been a substring filter that
  could also have swallowed a real disagreement. The filter is now by list
  membership, and a test asserts a disagreement can never reach that list.
- 32 new tests in
  `batch-runner/tests/test_envelope_preflight_reads_the_input_files.py`,
  including the exhaustive sweep above rebuilt against a small benchmark of
  real files, so the 64-position claim is re-proved on every run rather than
  measured once. Two of them run with the download cache emptied, which is the
  state a fresh build runner is in and the one condition the first version of
  this work was never tried under.
- **The check that holds the three run places to identical settings compared 18
  of the 44 settings in their files, and the comment above it said the rest
  "are the ones that are meant to differ between run places".** Nobody had
  measured that sentence. `_check_settings_the_plan_does_not_name` in
  `core/execution_envelope_preflight.py` named four blocks —
  `condition_a.model`, `condition_a.prompt`, `condition_a.qa`, `data.filter` —
  and looked at nothing outside them. Flattening the three experiment files the
  advance-check plan actually names and changing one setting at a time in a
  single run place, **the rule caught 18 of 44 and now catches 26**; at the
  level of the whole check, **25 of 44 and now 30**. Seven of the 26 the rule
  missed were caught anyway by `_compare_one_experiment_file` holding each file
  against the plan — the plan pins the time limit, the retry count, the resume
  count and the code length — so those were covered because somebody wrote them
  into the plan, not because they are in the files. Nineteen were invisible to
  every rule. The question is now asked the other way round: every setting found
  in the files is compared, and `SETTINGS_ALLOWED_TO_DIFFER` holds the whole set
  of exceptions with a stated reason for each, so a setting added later is
  compared without anybody remembering to add it.
- **The container's repair loop calls the model again after the code is written,
  which the strict comparison forbids in as many words, and nothing was looking
  at it.** `same_generated_code_rerun` fixes that the model is called once, to
  write the code, and not again — no self-review, no retry. `condition_a.qa` was
  checked against that; `execution.sandbox.repair` is the second way to reach the
  same thing and was inside the exemption for container-only settings.
  `_check_the_container_calls_no_model_after_the_code_is_made` now refuses it,
  along with `execution.sandbox.output_qa.vision.enabled`, which sends rendered
  pages to a vision model. The rule deliberately does not fire for
  `tool_built_in_features`, whose whole purpose is to leave each tool's own
  features running.
- **Absence is not off.** `core/sandbox_runner.py` builds its settings as
  `{"enabled": True, "max_attempts": 1, **(repair or {})}`, so deleting the
  `repair` block from the container's experiment file turns the repair loop
  **on** — the `enabled: false` written there is load-bearing. The first version
  of the rule above read a missing setting as falsy and reported a run clean at
  the moment it became least safe; it also decided which run places to ask by
  whether their sandbox block had anything in it, which is wrong in exactly the
  same case. Each watched setting now carries the value the runner really
  applies when it is left out, read from the runner's source, and which places
  get asked is decided by `execution.mode`, the setting the runner dispatches on.
- `tests/test_envelope_preflight_compares_every_setting.py` is new — 55 tests.
  The central one is derived rather than typed: it reads the settings out of the
  committed files, changes each in one run place, and requires either a refusal
  or a stated reason, so it grows with the files. Others require every exception
  to give an argument and to match something the files really hold, check the
  absent-means-on default by building a `SandboxRunner` and by calling
  `run_output_qa`, and read the source to fail if the compared set is ever typed
  out again. `WHAT_THE_SETTING_DOES` was duplicated by the same edit, the second
  copy shadowing the eight new descriptions, and held one entry
  (`condition_a.model.max_tokens`) that no settings file uses; both are fixed and
  a test now fails on either.
- **An exemption was granted to a block, and it quietly covered a setting that
  decides what goes into the model's prompt.** `SETTINGS_ALLOWED_TO_DIFFER`
  matches by key-path prefix, so naming `execution.sandbox` — reasonably, since
  a container's image, memory and processor count really are the run place
  being described — excused all ten settings under it. Nine describe the
  container. The tenth, `execution.sandbox.max_skills`, decides how many skill
  documents `core/skills_registry.py` writes into the container's prompt
  **ahead of the task itself**, as a manual of up to 7,000 characters that
  neither of the other two run places is given — while all three experiment
  files declare `control.fixed` to include `prompt_strategy`. The files make
  the promise; the exemption let one of them break it. Changing the committed
  `max_skills: 0` to `3` produced **10 refusals before and 10 after: no
  detection at all**. `_check_the_container_is_told_no_more_than_the_others`
  now refuses it, taking the whole check from **30 of 44 settings to 31**.
- **Absence is not off, again, and here it is worst.** `core/executor.py` reads
  the setting as `opts.get("max_skills", 5)`, `SandboxRunner` defaults the same
  field to 5, and this repository ships exactly five skill documents — so
  deleting the line does not mean "no skills", it hands the container every
  skill there is. The `max_skills: 0` written in the container's file is
  load-bearing in the same way `repair: enabled: false` is, and deleting either
  is now refused by name.
- **Every setting an exemption lets through is now argued for one at a time.**
  A block-level exception is an argument about a block; the settings under it
  are excused by where they sit. `SETTINGS_EACH_EXCEPTION_COVERS` in the tests
  records a reason for each of the 15 settings the five exemptions cover, and
  fails until a newly added one has one — either a reason written there or a
  rule of its own, as `max_skills` now has. Writing the reasons found a second
  thing worth saying out loud rather than assuming: `manifest.enabled` puts a
  `manifest.json` into the delivered file list, so the container ships one file
  the other two do not. It is built after the answer is chosen and cannot reach
  the model, and what it records is the run place — which is the thing being
  varied — so it stays exempt, but now on stated grounds instead of by
  inheritance.
- 14 further tests in
  `tests/test_envelope_preflight_compares_every_setting.py` (69 in all). The
  count in the comments is no longer a number somebody remembered: one test
  changes all 44 settings in one run place, runs the whole check, and fails if
  the total it reaches is not the 31 the comments claim. Another confirms the
  skill manual really is rendered into the prompt ahead of the task, by calling
  the real registry rather than trusting a sentence about it, and another reads
  the default out of `SandboxRunner` rather than restating it.
- **The check that "proves" the task list carries no scores caught 8 of 45 real
  score field names and missed 37.** `check_catalog_carries_no_scores` in
  `core/execution_envelope_tasks.py` backs the only claim that makes the
  three-way run-place comparison meaningful — that the five tasks were chosen
  before anybody saw a result — and the module docstring said no score, grade or
  verdict "is present, and `check_catalog_carries_no_scores` proves it by
  looking". It held fourteen hand-typed field names and reported a leak only
  when one appeared verbatim. Nobody had compared that list against the field
  names this repository's own grading pipeline writes. Harvesting the 45
  result-carrying names out of the 19 committed files in `data/grades/` and
  injecting each into a copy of the catalogue, **8 were caught and 37 were
  reported clean** — `avg_score`, `scores`, `pass_rate`, `avg_pct`,
  `confidence`, `critical_fail`, `graded_by`, `child_grades`, `num_grades` and
  twenty-eight more. The question is now asked the other way round: every field
  name, at any depth, must be one the two dataclasses the loader fills actually
  describe, so a result is refused whatever it is called. All 45 are now caught.
- The same check looked only at names, never values, so a result could take over
  a field that was already allowed. Every number the catalogue's schema holds is
  a count, and every score this repository produces is a fraction or a flag, so
  fractions and true/false values are now refused wherever they appear. What
  this still cannot catch — a score written into the text of a field allowed to
  hold text, an occupation recorded as `"Nurse (0.87)"` — is stated in the
  docstring instead of being covered by a claim to prove the file clean, and a
  test fails if that sentence is removed.
- `scripts/build_gdpval_task_catalog.py` wrote the catalogue without ever asking
  the check. The committed file is clean only because the builder happens to
  construct each field by hand, so the exposure was the next edit that recorded
  one more useful-looking column: it would have been written, committed, and
  found at the advance check, if at all. The builder now runs the same check on
  what it is about to write and refuses to write at all if anything is flagged.
- `tests/test_catalogue_carries_no_scores.py` is new — 21 tests. The central one
  reads the field names out of `data/grades/*.json` rather than retyping them
  and requires every one to be refused; another reads the source of the
  permitted-name helper and fails if a schema field name is ever typed there
  instead of derived. Against the code as it was, the file does not import at
  all: there was no derivation to test.
- **The free Azure check gave a clean bill of health for six settings the paid
  run refuses to start with.** `core/execution_envelope_azure.py` decides
  whether the three-way run-place comparison may spend anything on Azure, and
  its own specification claimed a plan checked there was "checked against
  exactly the rules the real run applies". Nothing measured that. Sweeping
  seventeen Azure settings one at a time and asking both the check and
  `AzureAIRouteSettings.from_env`, **seven disagreed and six of the seven
  disagreed in the direction that costs money.** All six were endpoint-identity
  settings — `AZURE_AI_EXPECTED_DIRECT_ACCOUNT`,
  `AZURE_AI_EXPECTED_PROJECT_ACCOUNT`, `AZURE_AI_EXPECTED_PROJECT_NAME` — which
  the run demands and compares against the endpoint it is about to use, and
  which the check never looked at. Every workflow step in `batch-run.yml` and
  `grade-run.yml` that can spend money hard-sets
  `AZURE_AI_REQUIRE_EXPECTED_IDENTITIES` to `'1'`, so the run always demands
  them, while the check that gates a 363.59 USD ceiling saw none of them. The
  check now reads the run's own identity table and applies it, and compares the
  plan's pinned account and project against those settings — a comparison the
  plan file asserted in a comment and nothing performed. Sixteen of the
  seventeen settings now agree; the seventeenth is refused here on purpose,
  because the comparison is pinned to the `project-ci` profile.
- **Two lists of setting names were typed out a second time inside the Azure
  check.** The ten fixed credentials the repository refuses to run with were
  retyped in `core/execution_envelope_azure.py`, while
  `scripts/azure_ai_route_preflight.py` imported the same list correctly.
  Demonstrated rather than argued: adding an eleventh name to the real list
  left the run refusing to start and the check reporting no problems at all.
  Four endpoint-setting names were retyped beside a comment claiming they were
  "the same names core/azure_ai_clients.py reads" — which nothing could check,
  because that module held them as string literals inside its functions. Those
  names are now module-scope constants there, and the check reads them from
  there. `core/azure_ai_clients.py` behaviour is unchanged; its 323 existing
  tests pass untouched.
- `tests/test_envelope_azure_applies_the_run_rules.py` is new — 41 tests, of
  which **20 fail against the code as it was**. The core of the file is a
  parametrised sweep that sets one Azure setting, asks the free check and the
  paid run separately, and requires the same verdict, so this class of
  disagreement is measured rather than reasoned about. One test opens the
  workflow files and pins the sentence the check's own wording rests on.
  `core/execution_envelope_azure.py` had no test file at all before this.
- The existing `tests/test_execution_envelope_advance_check.py` carried the same
  omission in its own fixture: the environment it called fully ready, and reused
  across six tests, set no expected-identity names, so "nothing left to fix"
  described a setup the paid run would have stopped. Fixed. `batch-runner`'s
  README and `docs/first-experiment.md` had all three names listed correctly the
  whole time — the written instructions were right and the code was wrong.
- **The check that refuses the paid three-way comparison compared two of the
  prompt's four parts — and the two it compared were the wrong two.**
  `check_experiment_files_match_conditions` in
  `core/execution_envelope_preflight.py` is the last gate before the run costs
  anything, and the only thing the comparison claims is that nothing but the run
  place differs. It compared `condition_a.prompt.system` and
  `condition_a.prompt.suffix`. `core/prompt_loader.py` joins `prefix` and `body`
  into the wording the model receives as well, so either of them set on one
  settings file and not the others changed what one run place was asked while
  every free check reported nothing. Meanwhile `system` does not survive at all:
  each run place loads a codegen prompt carrying its own `system_message`, and
  that one wins — so the check was guarding the part that gets dropped and
  ignoring the two that always arrive.

  Found by measurement rather than reading. Each of the 34 settings in the
  committed files was changed in one file at a time and the check asked whether
  it noticed: **16 noticed, 18 not**. Most of the 18 are meant to differ — the
  experiment's own id, the repository its results go to, the label each run place
  is given. The rest were not.

  The cause was a hand-written list of three setting names. Instead of a longer
  list, the check now names the *blocks* whose every key must match
  (`condition_a.model`, `condition_a.prompt`, `condition_a.qa`, `data.filter`)
  and reads the keys to compare out of the settings files, so a setting added
  later is compared without anybody remembering to add it — an invented `top_p`
  on one file is now refused by name. Coverage went from 16 to 23 of 34; the
  remaining 11 are exactly the fields that must be free to differ. The three
  committed files still pass unchanged.

  Two suspicions were checked and dropped rather than carried: `data.filter.sector`
  and `occupation` cannot silently change which tasks run, because
  `step1_prepare_tasks.py` builds its lookup from the already-filtered tasks and
  raises there instead (they are covered anyway, since refusing before a run
  starts beats crashing after it does); and the reviewer settings are safe today
  only because `qa.enabled` is pinned off, which is luck rather than safety.

  20 tests in `tests/test_envelope_preflight_compares_the_whole_prompt.py`,
  **11 of which fail against the old coverage**. They pin the fact underneath the
  fix by calling `render_prompt` — that `prefix` and `body` reach the model and
  that the settings file's `system` does not — so if prompt assembly changes, a
  test fails instead of a sentence going quietly out of date. One existing
  assertion in `tests/test_execution_envelope_advance_check.py` was updated: the
  refusal now names a setting by its full key path
  (`condition_a.model.temperature`), because a bare `temperature` stopped being
  unambiguous once the reviewer's settings were compared too. The refusal itself
  is unchanged — those three settings were refused before and still are. Nothing
  was enabled: no model was called, no command was run, no amount was approved,
  and no block was loosened.

### Fixed
- **Two free checks printed contradicting answers about the same fact, to the
  same reader, in the same session.** `scripts/check_agentic_stage_one_ceiling.py`
  said the model conversation loop exists, is proven against stand-ins that spend
  nothing, and that what is missing is a way to reach a real model.
  `scripts/check_execution_envelope_advance_check.py` said "the model never sees
  a tool result and never chooses a next action". Only one of them had looked:
  the first establishes its answer by running the loop, the second was a sentence
  in `core/execution_environment_readiness.py` written before the loop existed
  and never re-read after it was built. A sentence is not checked against
  anything.

  This was not untidiness. **The stale half pointed at work that was already
  finished**, so a reader taking it at its word would have gone off to write a
  loop that exists, instead of at the two things stage one actually waits on.

  `core/execution_environment_readiness.py` no longer decides this. It asks
  `core.agentic_v2_stage_one_budget.check_stage_one_cannot_reach_a_model`, the
  one place that settles it by running the loop against a stand-in that declares
  itself paid and requiring the loop to stop before asking it anything, and
  prints back exactly what that returns. Two copies of one piece of reasoning is
  what caused the defect, so the fix is one copy and one caller. The lookup uses
  this module's existing by-name import helper, so a module that has moved is
  reported as *a real model has to be treated as reachable until somebody
  checks* — never as silence, which reads as a question that was asked and came
  back clear.

- **One blocker sentence was making three claims with three different ways
  out.** "the command-running tool exec_run is closed, the model never sees a
  tool result and never chooses a next action, and no approval exists to use this
  environment in a real experiment" bundles opening the command tool, reaching a
  real model, and obtaining an approval. While they shared a sentence, finishing
  one of the three changed nothing in the report — which is how the finished one
  went on being listed as outstanding. They are now three blockers. The command
  tool is **called** and the blocker reports what came back, so a tool that
  opened reaches the report instead of the reassuring sentence; the approval
  stays a plain statement, because an approval is a decision, not a fact about a
  module.

- **`experiments/execution_envelope/advance_check_plan.yaml`** carried the same
  stale claim in a comment. Corrected, with a note naming which of the two copies
  is the one checked against the code.

### Added
- `batch-runner/tests/test_free_checks_agree_on_the_loop.py` — nine tests. The
  load-bearing one requires the sentence the readiness report prints about
  reaching a real model to be, character for character, the sentence the other
  check produced; matching on substance instead would let the two drift apart
  again, which is the failure being fixed. Five of the nine fail against the code
  as it stood before this change.

  Nothing was switched on. The report gained a blocker and lost none, the three
  guards are as shut as they were, the environment is still
  `structure_check_only`, and all three free checks still exit 1.

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
  `934b2d6e4f55f8ebf05a46960620ea6672619814c301c091aa9d9c634af4a8f9`
  (was `303a5e763e28bf06339877df62c8e2d0d022bc605aeeb3aee77e63ab411a41fb`
  until the `summary.wow` denominators were backfilled; task rows, verdicts,
  scores, cost and provenance are byte-identical and the generated analysis
  re-derives unchanged).
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

