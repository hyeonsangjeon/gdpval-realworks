# Five-job pilot ledger handoff: model-free path

This path transfers the existing **USD 200 inference + grading SQLite ledger**
between five GitHub-hosted Ubuntu 24.04 jobs. It proves wallet continuity and
refusal behavior with literal synthetic charges. It does **not** solve or grade
GDPVal tasks, authenticate to a provider, establish Sol pricing or 1M support,
renew a grader seal, or authorize the paid pilot.

The registered five task IDs and the existing `PilotUsdLedger` implementation
are reused. The original source registrations, cap/price records, runtime
limits and `relay_max_runs: 0` are unchanged. The new workflow is separate from
`batch-run.yml`; it does not turn on the generic paid relay.

## Decision and test boundary

The engineering question is whether changing jobs loses or duplicates money
already recorded in the shared ledger. A reset balance, changed wallet ID,
post-ceiling fake request or duplicate settlement is a failed proof. The only
changed axis is the worker/job boundary; request IDs, task order, cap and ledger
implementation stay fixed. No judge or stochastic model is part of the proof.

Three independent **synthetic** wallets cover different failures. Their dollar
amounts are literal test data, not token-price calculations, expected pilot
costs, actual usage, bills or three allowances for the real experiment.

| Scenario | Synthetic charges | Required outcome |
| --- | --- | --- |
| `continuity` | $1 inference + $4 grading per task | Same wallet ID; accumulated $5, $10, $15, $20, $25 across five fresh workspaces. |
| `ceiling` | $35 + $14 for each of the first four tasks | $196 carried forward; the predecessor refuses the next $5 reservation with `usd_ceiling_exceeded`; the next ceiling worker never starts. |
| `interruption` | Same $1 + $4 as continuity | Second worker exits 75 after a durable partial settlement ($6); the next job replays that settlement without another request/debit; final $25 and exactly 10 distinct settled requests. |

Unknown usage is separately tested offline: keep the full reservation consumed,
carry `usd_usage_unverified`, and do not enter another fake transport. The
existing production price admission is not patched or bypassed; synthetic
tests use the ledger directly and cannot make an unpriced real judge admissible.

## Linear Actions path

`.github/workflows/gpt56-pilot-ledger-handoff.yml` runs offline contracts, then
`shard_1` through `shard_5` in a strict `needs` chain, then audits the final
artifact. Each shard calls `gpt56-pilot-ledger-shard.yml` on **ubuntu-24.04**.
Each shard has a 10-minute CI timeout (the contracts job has 15 minutes). These
are model-free test limits, not changes to the pilot's 1,800-second attempt cap.
No job relies on the six-hour limit to interrupt and save a live model request.

The second shard deliberately returns exit 75 **after** it has published a
local ready manifest. Its workflow step permits that exit only; a following
mandatory check rejects every other failure/exit combination before upload.
The Actions job succeeds only after that expected-interruption check. The next
fresh runner receives its durable partial wallet. This is a handled worker
failure, not a claim that arbitrary runner loss can always be recovered.

The workflow can start on a matching pull request, or through
`workflow_dispatch` with the sole accepted mode `model-free`. It has no paid
mode, environment secret, provider SDK, OIDC permission or dispatch step.
Python's network-connect and subprocess entry points are denied during the
model-free worker/audit. Dependencies and Actions artifacts still use ordinary
CI networking outside that worker.

## What crosses a job boundary

Only `handoff.json` and six flat files (database + identity for each synthetic
wallet) are uploaded. The manifest is written last and contains:

- Repository, source SHA, run ID and attempt, plus the fixed five task IDs.
- The predecessor manifest digest, exact shard index and source-file digests.
- Existing wallet IDs, capture bindings, cap/price identities and money snapshots.
- SHA256 and size for every file, refusal status and per-shard synthetic counters.
- Observed runner metadata and explicit `model_calls=0`, `judge_calls=0`,
  `paid_execution_allowed=false`, and non-billing evidence boundaries.

`needs.<previous>.outputs` supplies both the immutable artifact ID and manifest
SHA256. Download by mutable artifact name, omitted predecessor, other run/source,
rerun attempt, out-of-order stage, changed bytes, links, extra members, partial
bundle and invented snapshot are refused. There is no "missing state → fresh
USD 200" fallback. Restored database/identity files are single-link 0600 files
inside a new 0700 directory. The old ledger's identity/schema/price guards run
again before work. Stopped/unknown wallets remain stopped.

Each fake request has a stable ID derived from its capture, task and origin.
The original SQLite reservation/settlement methods perform admission. A settled
ID reuses the recorded settlement and does not call the fake transport again.
No reservation or balance is cleared merely because a job changed.

## Trust and failure limits

This is a trusted **linear current-run artifact chain**, not a distributed
spending service. Hashes detect changed bytes against an independently supplied
predecessor digest; they do not prevent a privileged workflow author from
forking an older wallet. GitHub rerun attempts are deliberately refused. Live
multi-run retries need an approved durable ownership/fencing and reconciliation
contract before this can become a paid execution route.

If a runner dies before its updated wallet is uploaded, the next job must stop;
it must not adopt an earlier wallet and send the request again. An exported
unknown reservation also prevents continuation. No automatic artifact deletion,
budget refill, compensating credit or paid retry is implemented.

The paid pilot still needs the grader-seal A/B/C decision, a supported/proven 1M
route or a conditions decision, verified Foundry grading prices, diagnostic
reservation reconciliation, and its actual input/deployment/request/result
bindings. Passing this model-free workflow clears none of those launch checks.

## Local checks and artifacts

Run only offline tests on NAS, from `batch-runner/`:

```sh
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 \
  python -m pytest -q -m 'not integration' \
  tests/test_pilot_shard_ledger_handoff.py \
  tests/test_gpt56_pilot_shared_usd.py \
  tests/test_gpt56_pilot_usd_ceiling.py tests/test_gpt56_pilot_usd200.py
```

Actual cross-runner proof belongs to the new Actions workflow, not NAS. Its
artifacts are `pilot-ledger-model-free-tests`, five run/attempt/shard-specific
wallet bundles, and `pilot-ledger-model-free-proof`. Retention is seven days.
These are synthetic accounting/runner evidence, not benchmark answers or
grading results. The final proof must pass all three assertions; a green
artifact-upload step alone is insufficient.

The contracts job uses `requirements-pilot-ledger-handoff.txt`, including the
`datasets` import needed by the existing native-money fixtures. This is a
separate pinned dependency closure: `datasets` requires an older compatible
`fsspec` than the GHCP-only file. Neither that existing requirements file nor
the sealed production requirements are changed. Shard workers and the final
audit retain the smaller import-only GHCP dependency closure.
