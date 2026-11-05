# Sol five-task paid launch: route A, WIP

**Not merge-ready or runnable as a paid workflow.** The one-task Step 2
component now consumes verified inputs and a restored wallet, but the workflow
does not yet connect five owned Step 2 outcomes to the Step 8 consumers.
Even `execute_paid: true` stops with `sol_pilot_execution_bridge_incomplete`
before authentication, model-client creation or a new monetary reservation.
Do not remove that stop just to make a workflow green.

The owner has already approved the five-task Foundry/Codex pilot and combined
USD 200 cap. The remaining checklist is implementation, not another spending
approval request. No dispatch, model or grading call was made for this change.

## Chosen shortest route

Use **A: existing Step 2 / native Codex / Step 8**. That path already contains
the provider observer, held 1M catalog, host guard, public-list-price money
admission and actual grader. Route B's `_fake_transport` takes a literal test
amount; replacing it would also require rebuilding task execution, result
capture, response verification and grading integration. It is not a Foundry
transport abstraction.

The frozen `batch-run.yml`, `core/`, `step2_run_inference.py`, `step8_grade.py`,
price/limit records, all source profiles and the original model-free handoff
remain unchanged. The new caller verifies the existing full source profile
and #794 grader seal, rather than refreshing hashes. The original plan-only
reader remains an inspector; its always-false launch flag is not toggled.

New workflow/caller bytes are tied to the independently supplied exact main
commit and the actual workflow/checkout SHA, not silently added to an old
registration. Any later change to a registered consumer needs its proper
successor registration. Any change to the #794 grader closure must be reviewed
as a separate seal change, not hidden by this caller.

## Implemented

- A manual-only Actions workflow, `gpt56-sol-paid-pilot.yml`, with explicit
  boolean `execute_paid` (default false), exact reviewed main/workflow SHA,
  first-run-attempt-only admission and a single non-cancelling concurrency key.
- Hosted **ubuntu-24.04** validation in both workflow and Python. The current
  workflow has read-only permissions, no secret reference and no authentication
  step. NAS can run unit tests but cannot pass production host admission.
- A deterministic order: five solve stages in the registered task order,
  followed by five grading stages in the same order. All ten jobs are serial;
  these are **five tasks, one solve and one grade pass each**, not ten tasks.
  Grading follows all solve outcomes so the five-task denominator is retained.
- Exact source-profile and grader-seal validation, fixed Sol/Max/1M requests,
  prompt v2.2, rubric revision, 1,800-second attempt and one logical turn.
- A **single real `PilotUsdLedger`** checkpoint writer/reader, not the three
  synthetic wallets in #793. It carries both origins, outstanding unknown
  consumption, wallet ID, capture, source/run lineage and history. It does not
  issue requests, insert invented charges, settle estimated observations or
  create a replacement wallet on restore.
- Independent predecessor SHA256 and exact file-set checks, no links or
  overwrites, ready-last publication, original database/identity/price/cap
  checks on reopening, monotonic spend and stage order. Missing/changed state,
  pending reservations, a failed/stopped predecessor and exhausted money stop
  before the next worker workspace is created (database-semantic corruption is
  detected on reopening and the refused files remain for diagnosis).
- Unknown usage keeps the whole reservation booked and an existing request ID
  cannot be reserved twice. This preserves #795 rather than restoring the
  superseded unknown-usage or unverified-tariff refusal.

The original provider observer remains unchanged: a mismatched served model
stops; context `not_reported` is recorded and accepted under #796, while a
different reported context stops. The single-task worker now connects this
observer, the held 1M catalog and the real shared ledger to the pinned SDK.
Loopback tests prove the adapter wiring, not a live Foundry observation.

The stage's 180-minute workflow ceiling is infrastructure headroom within the
six-hour Actions limit, not a changed inference attempt budget. It still needs
an end-to-end timing check with the completed bridge and grading preparation.

## Single-task component (checklist 1 and 2)

`gpt56_sol_pilot_inputs.prepare_input_bundle` reads the original pinned parquet
and the exact two-reference closure. It verifies the five prompt/projection
identities before writing byte-identical inputs, `sol-pilot-request-capture.json`
and ready-last `sol-pilot-input-ready.json`. The verifier rechecks these bytes,
the independent ready digest, all files/directories and link refusals. No saved
JSON can manufacture an issued `VerifiedInputs` object.

Capture explicitly separates **requested** Sol/Max/1M from **not yet observed**
response fields. It is not an old complete evidence bundle, provider capability
attestation, billing receipt or five-task live witness. The actual request body
is produced by the unchanged renderer/SDK; the receipt binds its complete
rendered message hash. The original renderer's outer whitespace stripping is
unchanged, while source prompt hashes still cover the original raw strings.

`gpt56_sol_pilot_single_task.run_single_task_shard` requires explicit opt-in and
actual clean-source/main/host admission. It restores the predecessor through
`PilotUsdLedger(..., create=False)` and checks the predecessor's identity and
snapshot again in a new formal `SingleTaskWitness`. A fresh USD 200 ledger is
refused even if the task IDs and capture hash match. Request counts are restored
from **all** prior inference reservations, including unknown outcomes.

The witness owns one claim, SDK process, thread, turn and registered task. It
verifies exact Sol/Max/1M and zero retry settings before runtime effects. The
production provider must be the exact existing `CodexProviderSettings`, bound
to the approved account/deployment resource bytes by the unchanged reader.
The test-only provider has no auth command and only a dummy credential; its
outbound forwarding is replaced by a loopback HTTP server in the tests.

The existing parent experiment ID remains
`gpt56_sol_foundry_codex_pilot5_v1`. A derived **fragment execution ID** scopes
the generic core workspace, not another experiment or complete pilot result.
This is a new sibling witness and schema, not a partial/fabricated
`PilotWireReceiptSession`, a forged `PilotCaptureSources`, or a monkeypatch of
the old owner. The old full-five Step 2 and native-result-host guards still
refuse missing sessions and these fragment receipts. Five-fragment admission
to Step 8 is a separate unfinished item; no fragment may be graded as a full
pilot or silently promoted to a successful five-task result.

The pinned native core owns workspace/reference staging, rendering, SDK,
file collection and cleanup. The wrapper calls unchanged
`step2_run_inference._execute_single_task`, then the existing deliverable
hash/public-row projection and real wallet exporter. `strict_inputs=True`
accepts only the privately staged paths from actual reference verification.
It is not used with the legacy whole-five owner.

Outputs are `sol-single-task-claim.json`, `sol-single-task-result.json`, masked
native response artifacts, `sol-single-task-witness.json` and a separate wallet
checkpoint. Requested and observed fields stay separate; `fixture_transport`
and `full_five_task_witness: false` cannot be mistaken for live full-pilot
proof. Failed/mismatched responses retain the claim, result and money, publish
a failed checkpoint and cannot feed another stage. Interrupted or incomplete
publication leaves the workspace/ledger for diagnosis, without automatic retry.

This component handles **solve stages 1–4 with a predecessor**. First-stage
wallet/bootstrap and cross-workflow-run once-only ownership remain checklist 6.
The workflow still invokes neither this component nor authentication: its
source-owned `sol_pilot_execution_bridge_incomplete` refusal is unchanged.

The official [app-server protocol](https://developers.openai.com/codex/app-server/)
distinguishes `thread/start` from the generation boundary `turn/start`. Exact
0.147.0 SDK calls/configuration here come from the repository's pinned native
runner, not the current documentation's model examples. No model, effort,
context, prompt or grader contract was migrated.

## Required before removing the WIP stop

- [x] Implement exact fixed-input and pre-send capture materialization, with
  configured route checks separate from first-response evidence. The component
  is tested with public registered bytes; Actions production wiring is still
  blocked by the runtime/publication items below.
- [x] Add a formal opted-in single-task Step 2 owner using the predecessor's
  restored wallet. Preserve the full-five owner's admission instead of
  manufacturing/adopting it. One-task loopback end-to-end regression passes.
- [ ] Assemble the five genuine solve outcomes, per-stage live witness receipts
  and files for Step 8. A missing/error outcome remains missing/error, never a
  synthetic successful row or zero score. Preserve poisoned/failed receipts.
- [ ] Invoke the real local Step 8 shard route using its existing
  `--shard-count 5 --shard-index ...` and `--pilot-usd-workspace`, maintaining
  its full-five source identity, immutable rubric and sealed template. Carry
  the wallet through grading/perception requests and aggregate real partials.
- [ ] Add the standard pinned runtime, sandbox preparation and existing Entra
  authentication steps **after** source/input/host/financial admission. Keep
  request-level stop semantics and retain masked response/usage evidence.
- [ ] Complete the durable once-only pilot claim across workflow runs and
  reconcile prior diagnostic reservation obligations. The current-run chain,
  first-attempt guard and concurrency key do not prevent a later new run from
  requesting the same pilot again; no new USD 200 wallet may erase that debt.
  This also owns stage 0 bootstrap; the new restoring consumer cannot create it.
- [ ] Wire successful worker checkpoints and `manifest_sha256` outputs. The
  current workflow intentionally reaches no fake success/output substitute.
- [ ] Prove the real adapter with fake *provider responses only*, including
  model/context mismatch, deadline, USD stop, runner loss, duplicate/new-run
  refusal and grading failure. Verify unchanged seals and finish required PR CI.

The checkpoint is a trusted linear **current-run financial** artifact chain,
not a distributed spending service or a portable live-session witness. A
privileged workflow author could fork a predecessor; the completed controller
must own the run and stage claim. Arbitrary runner loss must never cause use of
an older checkpoint or an automatic repeat of a request with unknown outcome.

## Local verification

All provider responses and predecessor charges in local tests are synthetic.
The input fixture is the **original public registered parquet and references**,
not generated input or private Task4 results; its provenance/hashes are in
`tests/fixtures/sol_pilot_inputs/README.md`. The single-task regression executes
the real source/input admission, Step 2, core runner, pinned 0.147.0 SDK/CLI,
provider guards, SQLite and checkpoint code. Only provider I/O and hosted OS
labels are fixtures. Its fake model creates a small deliverable directly in the
real workspace; no native sandbox command, benchmark or grading runs on NAS.
The test refuses every non-loopback Python socket and uses no auth command.
This proves wiring and refusal behavior, not live runner/served-model/billing
evidence. The older launch-admission test still denies network and subprocesses.

```sh
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -q -ra -o addopts= -m 'not integration' -p no:cacheprovider \
  tests/test_sol_pilot_launch.py tests/test_sol_pilot_single_task.py \
  tests/test_pilot_shard_ledger_handoff.py \
  tests/test_gpt56_pilot_shared_usd.py tests/test_gpt56_pilot_usd_ceiling.py \
  tests/test_gpt56_pilot_usd200.py tests/test_gpt56_native_response_capture.py \
  tests/test_gpt56_grader_successor_seal.py tests/test_gpt56_runner_environment.py
```

The new tests run in Backend Tests' default **`pytest`** job: their filename is
not in its exclusions or another job's selection. Existing pilot/seal/money
contracts remain in **`pilot-contracts`**, with the preflight/wire/host partitions
unchanged. No workflow hash expectation, guard count, skip or xfail was edited.
Run the real-source regression on a **clean committed candidate**, using a
temporary directory outside the checkout and disabling bytecode/cache output;
the existing clean-source guard is deliberately not mocked. The native test
fixture sets an isolated per-test run root and temporary directory. No live
authentication environment is needed or should be supplied.

## Eventual dispatch draft — NOT executed, currently refuses

Only after the checklist is complete, reviewed, merged and CI passes:

```sh
gh workflow run gpt56-sol-paid-pilot.yml \
  --repo hyeonsangjeon/gdpval-realworks --ref main \
  -f execute_paid=true -f expected_source_sha=<reviewed-merged-main-40-hex-SHA>
```

The exact merged SHA cannot be named before the owner merges. The current WIP
must refuse even with a correct SHA; publication is not evidence of completion.
