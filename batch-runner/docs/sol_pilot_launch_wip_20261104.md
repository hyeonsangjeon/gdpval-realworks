# Sol five-task paid launch: route A, WIP

**Not merge-ready or runnable.** This change prepares the real launch route,
but it does not yet connect the owned Step 2/Step 8 consumers across jobs.
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
different reported context stops. Tests exercise that real field classifier,
but **do not claim the new unfinished worker is connected to it**.

The stage's 180-minute workflow ceiling is infrastructure headroom within the
six-hour Actions limit, not a changed inference attempt budget. It still needs
an end-to-end timing check with the completed bridge and grading preparation.

## Required before removing the WIP stop

- [ ] Materialize the actual fixed parquet/reference/config/capture bundle on
  Actions. Separate pre-send identity/input admission from observed model,
  capability, wire/host and usage evidence as authorized for this pilot. Do not
  fabricate a complete historical evidence bundle or label a fixture live.
- [ ] Add the opted-in Step 2 single-task stage consumer. Currently
  `PilotWireReceiptSession.__init__` creates a fresh ledger and
  `finalize` requires all five tasks in one in-process live owner. The next
  stage must reopen this same wallet without recreating or pretending to adopt
  an old live witness. Do not bypass `PilotCaptureSources` or choose a different
  experiment ID to evade that admission.
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

All local tests use synthetic fixtures and the actual SQLite accounting code.
Network connections and subprocesses are denied in the new test module; the
existing response tests permit only their own local fake provider. This is not
an executed benchmark, a served-model observation or a Foundry invoice.

```sh
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -q -ra -o addopts= -m 'not integration' -p no:cacheprovider \
  tests/test_sol_pilot_launch.py tests/test_pilot_shard_ledger_handoff.py \
  tests/test_gpt56_pilot_shared_usd.py tests/test_gpt56_pilot_usd_ceiling.py \
  tests/test_gpt56_pilot_usd200.py tests/test_gpt56_native_response_capture.py \
  tests/test_gpt56_grader_successor_seal.py tests/test_gpt56_runner_environment.py
```

The new tests run in Backend Tests' default **`pytest`** job: their filename is
not in its exclusions or another job's selection. Existing pilot/seal/money
contracts remain in **`pilot-contracts`**, with the preflight/wire/host partitions
unchanged. No workflow hash expectation, guard count, skip or xfail was edited.

## Eventual dispatch draft — NOT executed, currently refuses

Only after the checklist is complete, reviewed, merged and CI passes:

```sh
gh workflow run gpt56-sol-paid-pilot.yml \
  --repo hyeonsangjeon/gdpval-realworks --ref main \
  -f execute_paid=true -f expected_source_sha=<reviewed-merged-main-40-hex-SHA>
```

The exact merged SHA cannot be named before the owner merges. The current WIP
must refuse even with a correct SHA; publication is not evidence of completion.
