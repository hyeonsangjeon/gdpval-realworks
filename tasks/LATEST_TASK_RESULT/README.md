# Latest task result

## Plan-first dispatcher for the 30-cell Codex budget pilot

The new local dispatcher compiles and materializes the fixed pilot and wires
serial execution through the existing Step 1 and Step 2 entry points. It
defaults to plan-only. Its focused offline family passed
`25 passed in 286.25s (0:04:46)`, exit 0, at implementation commit
`6967ce8158459fd32506a14c25fa924e5b4747f8`.

Production execution is not ready on this source baseline. The single source
fetch returned main `149d89afd43e54a46b6f172b71c2cf23d0cb7a17`. The branch
starts from that same source baseline; the separate C-feedback implementation
was not copied or stacked. This baseline does not contain the C host-feedback
contract. The plan records
`c_host_feedback_capability_missing`; `--execute` refuses before checkout or
pipeline child operations. It does not silently run C as B. The tests inject
a synthetic capability at a library-only boundary, not a production pin or
CLI waiver. No existing branch or real artifact was modified.

### Registered comparison and controls

`batch-runner/experiments/execution_envelope/codex_external_budget_pilot.yaml`
is a separate preregistration. The existing score-free catalogue and
`advance_check_5` selector supply the same five tasks in their canonical order.
Each task has A1, B1, C1, C2, B2, A2: A/B/C across repetitions 1/2, exactly
30 distinct cells. One child is active at a time on the same declared target.

A uses fresh sessions with four attempts. B continues mechanically on its
retained native thread. C requires the same continuation capability and adds
only the reviewed host-observed error feedback; it does not optimize waiting.
B/C share backoff and the 180-minute cumulative/30-minute attempt policy.
A versus B changes both retention and attempt policy, so that contrast is not
a retention-only effect. B versus C is the feedback intervention. The two
repeats are a finite pilot, not a precision or quality guarantee.

The compiler takes the GPT-5.4 Foundry profile and requested `xhigh` effort
from the existing reviewed profile/compiler, with the same original
task/reference bytes, base instructions, provider, context and tools across
arms. The supervisor model does not select the experiment model. Self-QA and
resume rounds remain disabled; there is no low-score retry. The fixed grader
remains `default_v2_sol_max.yaml`, GPT-5.6-sol/max, prompt v2.2 and one grade
per task, with grading launch left to a separately directed stage. No judge
ran or was calibrated in this unit. There is no automatic monetary cutoff;
missing usage and cost remain missing or partial, not zero.

### Local entry point and durable state

`batch-runner/codex_budget_pilot.py` accepts an explicit run ID, caller-reviewed
source SHA and new private output root. Without `--execute`, it creates only
the plan, per-cell configs and host checkpoints. Compilation is not source
review, launch approval or model consumption.

A later execution also requires explicit original parquet, reference-only
root and canonical Step 0 manifest locators. The existing source snapshot,
no-link, single-regular-file readers and schema-4/deliverable-only manifest contract
verify those bytes. The existing config parser validates every cell. The
reviewed source must be clean and contain the required continuation-v2
feedback contract; the existing pinned SDK/companion, Codex connection,
development-host boundary and registered Foundry route guards remain in force.
No bootstrap, dataset download, workflow, provider fallback or upload is added.

Each cell gets a detached checkout because Step 1/2 resolve workspace paths
relative to source. Config, output, ledger, deadline, native-workspace and
checkpoint roles are isolated. Original inputs are copied without replacement;
Step 1 output must pass the existing exact prepared-input validator before
inference. The dispatcher initializes the existing host deadline once and
starts its clock before the first inference child. Step 2 always receives the
restore path, never a fresh-initialization flag. A restart validates the same
plan, inputs, prepared fingerprint and deadline identity. Downtime consumes
the original expiry; no retry or restart grants a new clock.

The private atomic checkpoints distinguish pending, running, succeeded,
failed and stopped cells. A serial file lock is passed to the child, so a
surviving child retains the lock if its parent dies. Missing or corrupt state,
colliding roles and partial preparation refuse without being overwritten or
silently adopted. A valid result written before dispatcher interruption is
checked and recorded without rerunning that cell; a lost exit code stays
unknown. Finished cells are not dispatched again. An expired running-cell
restore still reaches the existing Step 2 accounting path under the original
deadline, which forbids another native request.

Result fingerprints and run/task/prepared identities, deliverable byte records
and any declared ledger sidecar are checked. Records retain result/receipt/
artifact links without publishing task text or private absolute paths.
A zero exit without a result is a failure. Failed, filtered and expired cells
stay in the denominator of 30. Missing receipts stay missing; usage-based
estimates are not invoices. Partial files and interrupted state are retained.
Dispatch success and file availability are not graded task quality.

### Exact focused evidence

`PILOT_PYTHON` denotes the already restored private isolated interpreter with
the pinned `openai-codex==0.147.0` and companion environment; its absolute
locator is omitted. No dependency was installed. From the repository root:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_PYTHON" -m pytest -q -o addopts= batch-runner/tests/test_codex_budget_pilot.py
```

The invocation at `6967ce8158459fd32506a14c25fa924e5b4747f8` returned
`25 passed in 286.25s (0:04:46)`, exit 0. The duration is pytest wall time,
not task latency. The private log is retained. There was no failed invocation
or test retry, and no earlier 45/8/42/43 selection or full suite was rerun.

The family exercises the actual CLI, command construction, config parser,
input-byte/prepared/result validators, serial lock, atomic checkpoints and
deadline store. Fake clocks supply time, including restart downtime. Tiny
synthetic files replace original data; a fake transport supplies source/host
capability and detached-checkout stand-ins and replaces
the subprocess boundary. It emits synthetic Step 1/Step 2 records. This does
not replay real preparation, execute a native app-server or validate a live
deployment. The tests block SDK/client and credential-provider construction,
token acquisition, network calls, subprocesses and sleeps outside that
explicit fake transport.

The cases cover exact 30-cell order, common profile, seriality and isolated
roles; no-clobber and partial-preparation refusals; interruption before and
after a result, plus expiry during downtime; no rerun of finished cells or
fresh clock for a recorded cell; changed/missing original inputs, linked
references and corrupt/cross-cell restore state; C-capability refusal before
children; and failed/filtered/missing-result cells with missing or unavailable
receipts. These are offline dispatch and persistence findings, not live
recovery, model consumption, quality improvement, cost savings or pilot results.

### Source and review boundaries

No shared core, Step 1/Step 2, model template, workflow, grading or source-pin
file changed. The entry point is outside the full grader closure. The existing
comparison compiler still checks its genuine current closure and pins; no
active hash refresh or source-count change was needed. The existing 37/58
source sets and negative guards remain intact. Historical templates, grades,
results, receipts and successful/failed real checkouts are unchanged.

Earlier #651 evidence remains historical and was not rerun:

| Scope | Tested implementation SHA | Original result |
|---|---|---|
| Initial native continuation and related deadline/legacy cases | `db88d5301dd125704f06122645a049d8518de306` | 45 passed in 188.99s |
| Durable content-filter correction and bindings | `ee11f956d53225760b96040c2642e7ef0682b554` | 8 passed in 18.21s |
| Terminal-accounting correction and bindings | `d486dc456e3caf8c2cacc4cfd480a9828796d0e5` | 42 passed in 158.33s |
| Stable-reference correction and related guards/bindings | `76178074c1ad1e7a11f7b7a40d0773c26295ef20` | 43 passed in 165.28s |

Each result had exit 0 under its own selection and source closure. Their full
history, along with #648/#649/#650 history, remains in the changelog. The leader
reports FINAL-APPROVE review `5281735646` for #652 at
`b116563744351ab03769e356eb00fcfa39565da9`. That review covers the preceding
feedback intervention, not this dispatcher. Its branch remains untouched;
no acknowledgment commit or CI query was made.

This dispatcher needs immutable-HEAD implementation review and carrying-HEAD
automatic checks. The C-capable source must be integrated and reviewed with
this entry point before execution can pass its capability guard. Original
local inputs, live runtime readiness, a separately directed pilot launch and
the fixed grading stage remain outstanding. The leader already holds numeric
budget and paid-run authority; this is not a new owner-approval wait. No whole
experiment or Project-card completion is claimed.

The full skill catalog was reviewed once. Experiment-design kept the matrix,
intervention and causal limits explicit; backend/LLM guidance kept the wiring
on existing pipeline and persistence helpers. Experiment-report-en followed
by im-not-ai-en preserved the synthetic evidence, historical scopes and review
limits in these bounded records. UI/animation and SDK API redesign were not
applicable. No Azure/HF/provider/model/VM/grader or paid operation, real-data
retry, Project edit, PR merge, CI polling or review waiting was performed.
