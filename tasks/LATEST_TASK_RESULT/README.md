# Latest task result

## PROJECT5-TASK5-KEEP-R2-READER-20261003-0922

Implemented the fixed model-free `TASK5_KEEP_R2` reader and its existing
`read_result` / `observe_terminal` routes. The single authorized offline
selector passed at `2f58256bc6aabc345f46c37e8418b1f5f7a188d6`: 1 collected /
1 passed in 17.12s, exit 0, no timeout. It verified synthetic successful payload
intake, failed/stopped three-control-only observation, identity/history and
source refusals, marker readback/no-clobber, old defaults and 288 closed mode
cases with zero forbidden effects or synthetic commits. This is reader proof,
not a Task5 inference result, grade or live-read authorization.

The Project5 leader/AI systems architect supplied a direct
`APPROVE-WITH-CONDITIONS` pre-edit decision on 2026-10-03 at 10:24 KST against
base `bdb7c21111a4c86136b6158f4969a39a9950acb3`. The leader, separate from the
NAS implementation worker, applied the extreme-reasoner checklist and
substituted that decision for unavailable memo transport for this scope only.
No subagent returned approval: all three failed memo requests remain recorded
below. The one-line obsolete `model:` deletion in
`.github/agents/extreme-reasoner.md` is preserved; all other agent instructions
and standing review gates remain intact. Final independent reader-source review,
same-HEAD CI, source delivery and outcome-matched live-read authorization remain
pending.

The new clean worktree started at exact main
`bdb7c21111a4c86136b6158f4969a39a9950acb3`. The one duplicate-PR inspection
returned no open PRs. The leader supplied accepted producer HEAD
`226e9ab34385b2f5aff646f5ac2b809f989aafc1`, PR726 owner review
[5397963786](https://github.com/hyeonsangjeon/gdpval-realworks/pull/726#pullrequestreview-5397963786)
and all 10 checks. That producer gate and its 45.85s proof were not repeated
and do not approve this reader's final source. The leader owns the running
producer; this task did not query, wait for, approve, retry or modify it.

### Implemented fixed reader and supplied pending operation

The source-defined `TASK5_KEEP_R2` profile is limited to
`0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_keep_r2`, ordinal 6,
KEEP, repetition 2. It joins only the existing `read_result` and
`observe_terminal` modes, with a distinct private reader namespace and the
unchanged keep/r2 adapter checked before lazy import. The private namespace is
`retention-task5-keep-r2`, with distinct result-intake and terminal-observation
markers. Only necessary current reader/observer/workflow hashes migrate.
Producer, controller, publication discriminator, historical evidence and all
registered conditions remain unchanged. Ordinal 7 remains unsupported.

| Binding or operational event | Leader-supplied value |
| --- | --- |
| Producer source | `bdb7c21111a4c86136b6158f4969a39a9950acb3` |
| Workflow / run / attempt | `370228282` / `37081963299` / `1` |
| Preparation / approval jobs | `111084233411` / `111084948854`, succeeded |
| Execution job | `111085094584`, in progress at the supplied observation |
| Request SHA256 | `1b042b77fcc80b8c1a1c21fdd73feeefbcb80ce7f505b7c842aba496419386ac` |
| Protected owner approval | `6821020369`, posted and read back once for that exact request |
| Actual preparation materialized-grader-source SHA256 | `81bfae73b21f260ffd4985d701631f53c4ee7cb67e4d1a7ff39a7563598bbc6f` |
| Registered original-input bundle SHA256 | `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`; supplied provenance, not independent input verification |
| New terminal / claim / output identities | Unknown; no actual model entry or task outcome is claimed |

The unchanged producer predecessor is failed keep/r1 INFERENCE terminal
`33278d9c26e8c8e8cfe68649e482e01f684d7705`, with the exact dictionary below.
It is not the new result's identity. The reader permits only the
existing single fixed-path terminal discovery followed by immutable reads.
Successful intake verifies declared result/ledger/deliverable bodies,
fingerprint and no-clobber marker readback. Failed/stopped observation remains
controls/metadata/history-only, without payload verification or grading readiness.
Both `_summary` and `_declared_roles` use the closed canonical Task5 path rule;
Task4 deliverable paths are still refused. Neither mode may invoke a model,
grader, writer, child or dispatch, adopt a partial claim, upgrade a lost writer
acknowledgment or authorize replay.

### Single fixed-reader proof and current executable pins

The ordinary implementation commit is
`2f58256bc6aabc345f46c37e8418b1f5f7a188d6`. It excluded the two preserved
completion-record edits; those records are updated here after validation.
The cheap token-free prerequisite confirmed
`/ai-work/venvs/gdpval-realworks-py310/bin/python`, resolving to
`/usr/bin/python3.10`, CPython 3.10.12 and pytest 9.1.1. No package was installed.
Exactly one invocation ran from this worktree's `batch-runner`:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 CI=true PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -s --tb=short -p no:cacheprovider --basetemp=/tmp/task5-keep-r2-reader-proof-20261003-1024.z5MOYT/pytest tests/test_codex_retention_task5_keep_r2_read.py::test_task5_keep_r2_reader_is_fixed_model_free_and_closed
```

Result: 1 collected / 1 passed in 17.12s, invocation exit 0, log-capture exit 0,
no timeout under the 180-second bound. Log
`/tmp/task5-keep-r2-reader-proof-20261003-1024.z5MOYT/pytest.log`, SHA256
`dd1a659dcab342b28be93a9ca3c6f5cb5c6e798c4dee4f69f5426485602c7bbe`.
The same directory preserves `status.log` and `prerequisite.log`; prerequisite
SHA256 `abc7dfa7d89905377d43da841d96b81934ac07b744cc354fde04202d2b71a942`.

The proof used real validators with authored synthetic immutable controls and
payloads, not live HF or the running producer. It reached one successful
result/ledger/deliverable intake and four failed/stopped declaration/accounting
cases. Each unsuccessful observation downloaded exactly three control bodies;
payload verification and grading readiness stayed false. Wrong source, cell,
run, job, request, predecessor, hash/history, payload, ledger and fingerprint
cases refused. Missing/tampered current dependencies refused before private
effects, and the producer adapter was checked before lazy import. Copied/future
profiles, symlink destinations, existing markers and uncertain marker readback
did not authorize reuse or replay. Null grades, partial accounting, supplied
provenance and publication-derived proof limits remained explicit.

Source-only compatibility checks preserved old/default profiles, keep/r1's
null supplied-grader field, both fixed grade readouts and historical grading
digests. Synthetic Git transport exercised the real current-source preflight
and wrong/dirty/unsafe-checkout refusals. Collection-time helper imports kept
process/network/model guards active. All 288 mode/cell combinations were
checked, including spurious successful/nonempty request outputs that could not
enable approval or execution in either read mode. The same three jobs,
permissions, secret scopes, shared concurrency and no-cancellation setting
remain. There are still seven execution cells, now seven result-reader cells
and six terminal-observation cells. The read step retains token stripping,
private destinations, safe-receipt-only output, its 4-minute step bound and
180-second command within the 20-minute preparation job.

| Current source changed in this reader task | Base `bdb7c211` SHA256 | Tested `2f58256b` SHA256 |
| --- | --- | --- |
| `codex_retention_fresh_r1_result_intake.py`, exact keep/r2 profile and Task5 role branches | `d9c1c6a13203d38086ce76ede383d9c1c6459467649b716843ba3fd1434269b4` | `3cabfed49238d43a4ddf9480558e19fdc1c5e64a29fd0aaa129d964ffef6f558` |
| `codex_retention_grade_readout.py`, only the separate current-reader dependency pin | `fa7d7e9465e1c2f314f0aa17fbd901c7eb19e1bb64468f08c8e58e440b33c514` | `29e896f77d001f116f8e68edbd9162414cb99a5994423de642acd9f3834dcb11` |
| `.github/workflows/codex-retention-first-cell.yml`, read allowlists/cases and current pins | `d42be461977c0ef6ae223a16ce28f3de2cb87d4b8096744b245e14cad1aeb7a0` | `e01e28d5375255bcd2ab489193aaf09c04179dae34309ec55538885d1122356e` |
| `.github/agents/extreme-reasoner.md`, only the obsolete model-line deletion | `ea2431a625df0fbdf8bbec08e8498f1683523b669a916363df4fb2cc3888cff0` | `4bd646d736954f48e3d0998b59133d82c9e1299a33aaf23a007a702b361ca8dd` |

The unchanged keep/r2 producer adapter is pinned at
`7ac1e8d8014e7fff765c65a80774d808a8b34d2cc2d88af8ef9ba8580ad820af`.
All 15 observer-current dependency hashes and 10 checksums in each read
preflight matched actual source bytes; both shared-reader CLI pins use the new
reader hash. Six existing test files received only directly coupled
route/current-pin expectations; their delivered selectors were not rerun.
The new selector reused the existing synthetic fixture without duplicating
exclusively owned source roles. There was no collection probe, old producer or
reader proof replay, private integration, renderer, full suite or second test
invocation. Historical `RESULT`/`PARENT`/`READER`, the producer/controller/shared
publication discriminator, grading routes and dependency manifests are unchanged.

### Accepted historical PR726 producer implementation and proof

PR726 implemented the registered seventh closed producer binding. Its one
authorized offline selector
passed at `4be8ae506e678ee1b2b5300cd9bc4ce5cbf2cc45`: 1 collected / 1 passed
in 45.85s, exit 0, no timeout. It reached packet/staging, exact authority and
predecessor/current-parent CAS, owned KEEP recovery and cumulative-clock checks,
child completion, terminal acknowledgment, reconciliation, lost-ack/no-replay,
timeout/cleanup and directly coupled routing/current-source checks. This is
synthetic lifecycle proof, not a live Task5 keep/r2 result or execution authority.

That producer work began in a new clean worktree from exact main
`eef25d13c2e2c764ac4be4d4681791223a34fcf2`. The leader supplied the accepted PR725
reader HEAD `15f6a7fabf7dd70ad38d147a3ec60dd7c91c05fc`, owner review
[5397406710](https://github.com/hyeonsangjeon/gdpval-realworks/pull/725#pullrequestreview-5397406710)
and all 10 checks. That source gate and the 18.80s reader proof were not repeated.
The leader also supplied the failed keep/r1 inference and successful terminal-only
observation below. No producer, observer, HF outcome or CI run was queried or
replayed in that task. Its then-pending producer gate was subsequently satisfied
by the leader-supplied PR726 review/checks and dispatch above; no reader approval
or live result is implied.

### Accepted seventh-cell producer scope and preserved boundaries

The new adapter binds only
`0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_keep_r2`, ordinal 6,
KEEP, repetition 2. The controller adds its exact request/admission-class pair
and dispatcher entry. Its packet, staging, host and remote admission/output/
terminal namespaces are distinct. The shared publication task discriminator
adds only this Task5 identity; canonical Task4/Task5 deliverable isolation and
unknown/future-binding refusals remain strict. The new CLI delegates old cells;
every older entrypoint refuses the new cell before source or private effects.
Ordinal 7 remains unsupported.

The fixed predecessor is failed Task5 keep/r1 INFERENCE terminal
`33278d9c26e8c8e8cfe68649e482e01f684d7705`, never the earlier fresh/r1 or either
grading terminal. The adapter uses explicit `reader.TASK5_KEEP_R1` terminal-only
verification of controls, claim, manifest and object history, then compares the
full independently supplied identity tuple. Actual inference-branch parent
equality and namespace absence precede the existing one-use CAS claim. No
predecessor result, ledger or deliverable body is downloaded to prove cleanup,
and no predecessor native state is adopted.

After PR726, the protected workflow had seven exact execution cells, six
result-reader cells and five terminal-observation cells. Its locator default,
three jobs, permissions, secret scopes and paid-grading routes stayed unchanged.
PR726 added no keep/r2 result reader because its future producer/run/request/job
identities had not then been supplied. This reader task adds only the seventh
result and sixth terminal read bindings; terminal/claim/output identities
remain unknown.
The accepted keep/r1 reader still uses its own `retention-task5-keep-r1` namespace,
checks current dependencies before lazy imports/private effects, and permits one
fixed-path discovery followed by immutable reads. Successful intake must verify
declared result/ledger/deliverable bodies, fingerprint, no-clobber readback and
marker. Failed/stopped observation remains controls/metadata-only, with
`payload_bodies_verified=false`, `grading_input_ready=false` and no
`intake_verified` claim. Omitted/default first-cell and old fixed profiles remain
closed; unknown or copied reader profiles refuse.

Publication-derived evidence does not independently authenticate the provider,
original inputs or actual parent CAS. A read-only reconciliation cannot upgrade
a lost writer acknowledgment, authorize replay or adopt a partial claim. No new
framework, producer wire schema or experimental axis is added. Existing core-runtime
and recovery semantics are unchanged.
KEEP retains only this new cell's own native thread/workspace/HOME/CODEX_HOME/
output during eligible recovery, never the failed keep/r1 cell's state.
The registered GPT-5.4 / direct-v1 / xhigh, SDK/CLI 0.147.0, mechanical B/no C,
one inference slot and own 10800-second cumulative clock are unchanged. Waits,
recovery and downtime do not reset that clock; 1800 seconds is the native-turn
wait, not an all-in attempt ceiling. No count, money or experimental axis changed.
The eight-cell order remains Task4 keep1, fresh1, fresh2, keep2, followed by
Task5 fresh1, keep1, keep2, fresh2; this implementation does not change that registration.

### Leader-verified failed keep/r1 inference and fixed predecessor

The leader verified PR724 HEAD `d23e0a7df8dca37c3fabc14ae9957b05b3eaea72`, tree
`128c85a9a8d189b56631fb04705e035dedfca078`, owner review
[5396422844](https://github.com/hyeonsangjeon/gdpval-realworks/pull/724#pullrequestreview-5396422844)
and all 10 checks. That completed source gate covers the keep/r1 producer, not
this new keep/r2 implementation. The following supplied facts reconcile the
prior pending delivery/dispatch record in this substantive task. The inaccessible
local-volume backlog was not independently read or assumed to contain more evidence.

| Binding or operational event | Leader-supplied value |
| --- | --- |
| Cell / ordinal / retention / repetition | `0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_keep_r1` / `5` / KEEP / `1` |
| Workflow / run / attempt | `370228282` / `37066171719` / `1` |
| Producer source | `a8353cd41f01f7d94129421512a57a62b9bd6997` |
| Preparation / approval / execution jobs | `111034384244` / `111035594016` / `111036410671` |
| Request SHA256 | `22e0bc6f06e4c9c2ac2d3fa4bfe6a7c567ef24e9111bf319b704409d731997de`, matched the prospective scope |
| Protected owner approval | `6818606633`, posted and read back once for that exact request |
| Dispatch | Ordinal 5 dispatched exactly once |
| Actual terminal receipt | `2026-10-02T22:27:02.3524920Z`: FAILED / exit 1 / cleanup true / remote terminal acknowledged / grade null |
| Authorized terminal-only observer | Run `37074821378`, read job `111062242784`, source `eef25d13c2e2c764ac4be4d4681791223a34fcf2`; successful at `2026-10-02T22:55:34.5919539Z`; approval/execution jobs skipped |
| Terminal revision / SHA256 / bytes | `33278d9c26e8c8e8cfe68649e482e01f684d7705` / `bb9cca2f81ea6bcdf0e9c08da9192e7b012d0834b89ea0f64f33489ef9700809` / `4176` |
| Claim revision / SHA256 / bytes | `93b30ecb08acadcede50f0c4eacab15f35450bb5` / `17ed95b8bd181fa0de7b76642cc2ab67d9ee80db6673f66b1da3c1dedcc40632` / `1888` |
| Output revision / manifest SHA256 / bytes | `5e56a906c4bd7a3510087ffc2efe392637e22be9` / `b9b1a4f89151a742caf5a7b0451102e1e1857d993ec4184e6f64a211d08ce3d7` / `2099` |
| Output object-set SHA256 | `4476d117f6cdc6c381491d622a92a24e99d490282c8c7ec72ecce132b0a8b9d7` |
| Observation SHA256 | `009a9677a5aa7189dd26ac993657e1bc54b532b886a252ffdfdfcad858ada49d` |
| Retained authority SHA256 | `ff1a41b9062bca8d743ad15968aab753d5fad09a08af168e5413902b29410f11` |
| Actual preparation grader-source SHA256 | `75f38c05e5c348e481e54f4c0b2000772c2414d7bae7519b1f2a38d92e1e0dc5`, separately supplied by the leader in this order |
| PR725 reader's supplied grader provenance | Remains null: this value was not supplied to that reader task. It is not backfilled from the later preparation evidence or a fetched body |

The observer's `writer_acknowledgment=not_established` is distinct from the actual
producer acknowledgment above. Controls declare 1 result, 1 ledger and 0
deliverables, with 3 objects including the manifest; their bodies were NOT
verified by this observation. No successful intake or grade exists, and absence
of all partial work is not established. Detailed failure, budget and recovery
exposure remain unavailable / `not_recorded_in_terminal_controls`; neither a
rate-limit/timeout cause nor a retention benefit is inferred.

| Partial recorded keep/r1 inference component | Model calls | Known cost (USD) |
| --- | --- | --- |
| Infrastructure retry | 12 | 0.252019 |
| Generation | 1 | 0.161345 |
| Aggregate known/model | 13 | 0.413364 |

Recorded usage is input 190746, cached input 121216, output 13949 and reasoning
12251. Cached/reasoning counters are subsets, not extra totals. Estimated/runtime
costs and HTTP request count are null; missing reason `call_reachability_unknown`,
invoice false. These partial writer-recorded inference costs are neither an invoice
nor Task4 grading costs, and model calls are not HTTP requests or native admissions.

Six producer outcomes are recorded. Ordinal 6 is now dispatched with outcome
pending at the leader's supplied observation; ordinal 7 remains unexecuted.
The original registered input bundle
remains `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`;
the terminal-only observer did not independently reverify those original inputs.

### Accepted historical seventh-cell producer proof; not repeated

The ordinary implementation commit `4be8ae506e678ee1b2b5300cd9bc4ce5cbf2cc45`
was clean before validation. The cheap token-free prerequisite verified
`/ai-work/venvs/gdpval-realworks-py310/bin/python`, CPython 3.10.12 / pytest 9.1.1,
without installation. The executable resolves to `/usr/bin/python3.10`, SHA256
`7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86`.
Exactly one invocation ran from the producer worktree's `batch-runner`
(`/ai-work/copilot/worktrees/codex-retention-task5-keep-r2-20261003-0749`):

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 CI=true PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -s --tb=short -p no:cacheprovider --basetemp=/tmp/task5-keep-r2-proof-20261003-0749.bEiUnu/pytest tests/test_codex_retention_task5_keep_r2.py::test_task5_keep_r2_is_the_closed_seventh_cell
```

Result: 1 collected / 1 passed in 45.85s; invocation exit 0, log-capture exit 0,
no timeout under the 180-second bound. Log
`/tmp/task5-keep-r2-proof-20261003-0749.bEiUnu/pytest.log`, SHA256
`67b6e8cbdf24b5d9786199fbb9aabad990d07b86b6cfe5acb8ef467c3b8a7667`.
The same directory preserves `status.log` and `prerequisite.log`; prerequisite
SHA256 `673fd11a2f6bbeb72f50f1200f91639128af80f8eaab18f00062feb36c2d0c39`.

The test used real validators, authored synthetic control bytes, synthetic Git/
provider/HF responses and owned synthetic children. All 288 exact mode cases,
15 current observer dependency hashes and 9 checksums in each reader preflight
passed. Existing fixed/default readers accepted current dependencies, while the
historical consumed grading evidence stayed unchanged. The test reached exact
ordinal 6 packet/staging and cross-pair refusals across seven exact admission
classes; older entrypoints and ordinal 7 refused. Predecessor identity/history, namespace,
actual-parent CAS-race, duplicate and uncertain-claim cases refused before a
child or deadline. Predecessor downloads were limited to controls.

The KEEP scenario settled and read back real synthetic receipts, retained only
its own native bundle and output, rejected predecessor state adoption and fresh
reset, and kept its original 10800-second clock. A simulated 30-second wait and
45-second downtime left 10725 seconds; native-turn wait remained 1800 seconds.
Owned completion reached execute-return and acknowledged terminal readback/
history. Reconciliation and lost-ack observation added no child or commit and
did not rewrite the unresolved writer receipt. Later remote no-replay,
cumulative-timeout and cleanup-refusal assertions completed. Canonical Task4/
Task5 path isolation remained strict. Helpers were imported during collection;
exclusive fixture ownership and process/network/model guards stayed active.
No live effects, old delivered selector, collection probe, private integration,
renderer, full suite or second invocation occurred.

### Accepted historical PR725 reader proof; not repeated

The implementation and tests were committed before validation. The cheap
same-environment prerequisite verified the exact executable
`/ai-work/venvs/gdpval-realworks-py310/bin/python`, CPython 3.10.12 and pytest
9.1.1 without installation. One invocation ran from `batch-runner`:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 CI=true PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -s --tb=short -p no:cacheprovider --basetemp=/tmp/task5-keep-r1-reader-proof-20261003-0623.TTPPa4/pytest tests/test_codex_retention_task5_keep_r1_read.py::test_task5_keep_r1_reader_is_fixed_model_free_and_closed
```

Result: 1 passed in 18.80s at `ee24a3a12c2f07d66f9ec89ed84073bbd7879ccb`,
invocation exit 0, log-capture exit 0, no timeout. Real validators consumed
sealed synthetic transport bytes. The proof reached source/cell/job/request/run
and predecessor refusals, successful payload/fingerprint/ledger/readback,
failed/stopped three-controls-only reads, missing terminal and history refusals,
corrupt payload and marker checks, no-clobber replay refusal and unresolved
writer-acknowledgment boundaries. All 15 current observer dependency hashes and
9 checksums in each reader preflight matched; changed/missing current bytes and
dirty/wrong/unsafe checkout cases refused. Historical grading evidence stayed
fixed. The 288 exact mode cases kept approval/execution excluded from both read
modes. Helpers were imported at collection, and process/network/model guards
remained active. No old delivered selector, private integration, renderer,
collection probe or full suite was run.

Log `/tmp/task5-keep-r1-reader-proof-20261003-0623.TTPPa4/pytest.log`, SHA256
`8fd97856dbf973f9897f1573fc46ae4bd5f0fa0cb170916514f9109ab6e431b7`.
The same directory preserves `run-proof.sh`, SHA256
`a9cbbbe8fcc846fa5712133bcf65a902f76af03fb5c30a650277a9d30e45ff1b`,
and `prerequisite.log`, SHA256
`65dddf6de7e6d5f4af8290a68b00a7f20f8133695dd709f853eb9057e7c86eb7`.

### Historical sixth-cell implementation proof and setup failure

The producer implementation started from `eb0f40016aa14cb8b1afa8b3590d6c437e8f97e3`.
The preceding PR723 reader HEAD `40b699e9022c601d4fb72482173354829d7b87e1`, review
[5395210507](https://github.com/hyeonsangjeon/gdpval-realworks/pull/723#pullrequestreview-5395210507)
and all 10 checks had passed its source gate. The following two proofs are
historical evidence accepted for PR724; neither was repeated for this task.

The implementation was committed and clean before the original invocation.
The cheap prerequisite in the same token-free environment reported
`/ai-work/venvs/gdpval-realworks-py310/bin/python`, CPython 3.10.12 / pytest 9.1.1,
without installation. Exactly these two selectors ran once at 703d9bbf from
`batch-runner`:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 CI=true PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -s --tb=short -p no:cacheprovider --basetemp=/tmp/task5-keep-r1-proof-20261003-0413.z8knKw/pytest tests/test_codex_retention_task5_keep_r1.py::test_task5_keep_r1_is_the_closed_sixth_cell tests/test_codex_retention_task5_keep_r1.py::test_task5_keep_r1_routes_and_current_pins_preserve_fixed_readers
```

| Selector at `703d9bbf94f59045c4a04d58bf16ddda82d905a0` | Outcome and boundary |
| --- | --- |
| `test_task5_keep_r1_is_the_closed_sixth_cell` | Failed with `FileExistsError` during the synthetic source-copy setup. Independent production pins, closed Task4/Task5 canonical publication paths and unsupported-binding refusals had passed. The shared synthetic original-input/historical-observer scenario returned. The new cell's packet, staging, request, authority, predecessor/CAS admission, KEEP recovery, child, publication, reconciliation and timeout/cleanup phases were not reached. |
| `test_task5_keep_r1_routes_and_current_pins_preserve_fixed_readers` | Passed exact six-cell execution/five-result/four-terminal allowlists, 288 mode cases, job/permission/secret and current hash contracts, old reader defaults, real current-source preflight, tampered/missing dependencies and dirty/wrong/unsafe-checkout refusals. Historical grading evidence stayed fixed. Helper imports completed during collection and the process/network/model guards remained active. |

The original exception is at
`batch-runner/tests/test_codex_retention_task5_keep_r1.py:265`, which calls
`_write(root / role, (REAL_ROOT / role).read_bytes())` for the adapter's source
closure. The shared scenario already created
`batch-runner/codex_retention_task4_fresh_r2.py`. The no-clobber helper at
`batch-runner/tests/test_codex_retention_task4_fresh_r1.py:57` opens the same file
with `xb` and raises `FileExistsError`. This is a duplicate synthetic source-copy
attempt, not a production verifier failure, model result or HF outage. That task
stopped without a guard change, fixture repair or second invocation. The later
`PROJECT5-TASK5-KEEP-FIXTURE-20261003-0444` order separately authorized only the
fixture correction and one lifecycle-only verification.

Log `/tmp/task5-keep-r1-proof-20261003-0413.z8knKw/pytest.log`, SHA256
`3365b47a58477e67d93537a12776a2c6d32546b28066221881d26348f0c6fbf5`.
Runner `/tmp/task5-keep-r1-proof-20261003-0413.z8knKw/run-proof.sh`, SHA256
`380cd53ddb44780491d74e00f44fefafc0584dd7b3bdef2780d0347edfb16e63`,
pins the exact tested HEAD, clean worktree, two selectors and 180-second bound.
The invocation exited 1, not the timeout code. No older suite, private
integration, renderer, collection probe or full build was run.

The correction at `a8e88e5adaf93303032a4bd636f91d48085abaa6` asserts exact current
bytes for the shared scenario's Task4 fresh/r1 facade, Task4 fresh/r2 facade,
shared result reader and original reader. It creates only the additional Task4
keep/r2, Task5 fresh/r1 and Task5 keep/r1 adapter files through the unchanged
exclusive `xb` writer. The explicit owned/additional lists must cover the exact
adapter source closure. No arbitrary existing file is skipped or overwritten.
All non-test/non-record bytes remain identical to 703d9bbf; both existing record
edits were preserved unchanged during verification.

After the same-environment executable/version/pytest prerequisite passed again,
only the previously failed lifecycle selector ran once from `batch-runner`:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 CI=true PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -s --tb=short -p no:cacheprovider --basetemp=/tmp/task5-keep-fixture-proof-20261003-0444.Vc0jY8/pytest tests/test_codex_retention_task5_keep_r1.py::test_task5_keep_r1_is_the_closed_sixth_cell
```

Result: 1 collected / 1 passed in 41.97s, exit 0, no timeout. The test reached
ordinal 5 packet/staging, exact request/admission pairing and authority checks,
fixed failed-predecessor controls/history, actual current-parent CAS and
duplicate/uncertain-claim refusals. Real receipt and lifecycle APIs verified that
KEEP preserves only this cell's own native bundle and does not reset its
cumulative clock. The synthetic owned child completed; terminal readback and
history checks passed, and publication was acknowledged. Reconciliation, lost
acknowledgment, no replay, timeout and cleanup assertions also completed. Lost-ack observation remained
read-only with `writer_acknowledgment=not_established`; it neither rewrote the
unresolved writer receipt nor added a child or commit. No live effects occurred.

Log `/tmp/task5-keep-fixture-proof-20261003-0444.Vc0jY8/pytest.log`, SHA256
`1e5b17617b877a94b883e27bcd75d6558c89650010d3693a007295dcbbf2efdf`.
Runner `/tmp/task5-keep-fixture-proof-20261003-0444.Vc0jY8/run-proof.sh`, SHA256
`806e84d6bee913c83ff56ab34c47d484b8a4a9a2cbdd3d343b6f17c6f8e75c2b`, pins the
test-only HEAD, unchanged production bytes, preserved records, exact selector
and 180-second bound. Helper imports still precede offline fixture activation;
network/process/model guards remained active. The passed 288-mode routing and
current-source selector remains evidence from 703d9bbf only, not a rerun at the
correction HEAD. No other suite or pytest invocation was run in this corrective phase.

### Verified failed Task5 fresh/r1 predecessor

The following evidence is supplied by the leader, not queried by this task.
Terminal-only observation `37049700859` / attempt 1 / job `110979716273`, at
source `eb0f40016aa14cb8b1afa8b3590d6c437e8f97e3`, reported `terminal_verified`
at `2026-10-02T18:48:52.3056439Z`. The producer outcome is FAILED, exit 1,
cleanup true, with recorded publication acknowledged. It is consumed. No
successful intake or grade exists, and neither producer nor reader was replayed.

| Binding or recorded control | Independent value |
| --- | --- |
| Producer workflow / run / attempt | `370228282` / `37032230813` / `1` |
| Producer source | `e5e338aa22c247133936fa075c2def7bffb95173` |
| Cell / scope | `0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r1`, Task5 ordinal 4, fresh, repetition 1 |
| Preparation / execution jobs | `110921652971`, succeeded / `110933285330`, failed terminal outcome |
| Request SHA256 | `9a53e9c0ae7b50400f2b27d514207e489b237cc5b5195ff8e36fcc4ea920370b` |
| Original registered input bundle SHA256 | `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3` |
| Materialized grader source SHA256 | `a820cd9e3a8e74e684aa65a710e5a7b0649ce0435fe425a070a0eb6d8b30145e` |
| Protected approval | `6812887076`, applied once for the exact request |
| Terminal | `94628d12162da2e00cace216fdda5ce41f57e47f`; SHA256 `5bc2eb37dd4ab83cd7653106166cc18d36c193eec12e2bc99b9bf429be6942cf`; 4188 bytes |
| Claim | `fb39a92ccbaf26f1ab698510cf0914f73b17cb0e`; SHA256 `6e06ae9c9e79201ec7eb28019de56ffa1d63b2cc6c8ab9569a267791733d260e`; 1891 bytes |
| Output / manifest | `70a69c818be5c7d751a0481808dbba86aa983b19`; manifest SHA256 `dff85ecf69ee2c38bbfe40280099d87ecd3989969512307671ac3e8a15e60cf4`; 2107 bytes |
| Object-set SHA256 | `6c7ea668caa8cf39569a1848a025bc534bb406c46b46874ea7fdd584870a24e2` |
| Observation marker SHA256 | `429158a5eca5931e2265faa07ff78616b009f5bf83fc071b4734c1d29d3728ed` |
| Retained-authority SHA256 | `e121ccf6ed4213cbfee29ba5eda4d7e8dd25b37ba372a602661d2aa88b762216` |

These are inference controls. The consumed fresh/r1 adapter's own predecessor
remains Task4 keep/r2 inference terminal `e55fac5d60191167dd66688510ec0fef472e594d`.
Neither grade terminal `76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e` nor grade parent
`40712e0980cc05c31688fdbb98c693774fb90c0d` is an inference parent. The earlier
0138 and 0240 leader snapshots saw runtime installation and then `in_progress`
at the combined grant/claim/owned-cell step; they were not completion evidence.
The later terminal-only observation above supersedes that pending status.

The controls declare 1 result, 1 ledger, 0 deliverables and 3 objects including
the manifest. Payload bodies were not verified. Zero declared deliverables does
not establish absence of all partial work. Detailed failure, budget and recovery
exposure remain unavailable / `not_recorded_in_terminal_controls`; no rate-limit
or timeout cause is inferred. Terminal observation does not return
`grading_input_ready`, verify payload bodies or upgrade lost writer acknowledgment.
Successful intake still requires declared result/ledger/deliverable bodies and
marker readback. Publication-derived evidence is not independent provider,
original-input or CAS authentication, a new writer acknowledgment or replay authority.

### Partial fresh/r1 inference accounting and preserved Task4 scores

| Recorded inference component | Model calls | Known cost (USD) |
| --- | --- | --- |
| Infrastructure retry | 17 | 2.517018 |
| Generation | 1 | 0.059075 |
| Aggregate | 18 | 2.576093 |

Recorded usage is input 1487642, cached input 1080192, output 85828 and reasoning
62263. Cached input and reasoning are subsets, not extra totals. Estimated cost,
runtime cost and HTTP counts are null; the missing reason is
`call_reachability_unknown`, and `invoice_complete=false`. These are partial
writer-recorded inference costs, not an invoice or Task4 grade costs.

Task4 keep/r2 remains 30.35 / 45 = 67.44% included and 54.20% full denominator,
with 9 excluded items / maximum score 11. Its grade ledger records 91 model calls
with `price_missing`, null known/model/estimated/runtime costs and
`invoice_complete=false`. Grade usage remains input 264029, cached input 199080,
output 19748 and reasoning 14411, with subsets counted once. The unrecorded
materialized-input comparison remains unavailable. Keep/r1 remains 68.0%
included / 54.64% full. Task4 fresh/r1 and fresh/r2 remain failed/ungraded,
39 calls each / known USD 0.303358 and USD 0.29944 partial, with unknown detailed
causes. Task4 keep/r2 inference remains 6 calls / known USD 0.22195 partial and
null generation cost; zero generation counters do not prove free work. No
causal retention benefit, independent provider authentication or invoice is claimed.

### Historical producer executable pins before this reader extension

PR726's production changes were limited to the new adapter, exact controller
binding, one shared publication-discriminator entry, the existing workflow's
closed seventh execution route and necessary current executable pins. The
reader's `FROZEN` executable checks and observer `CURRENT_DEPENDENCIES` remain
separate from paid grading's immutable historical `READER`. No historical
producer or receipt is relabeled as current source.

| Historical PR726 executable source | Base `eef25d13` SHA256 | Tested `4be8ae50` SHA256 |
| --- | --- | --- |
| `codex_retention_task5_keep_r2.py`, new ordinal 6 adapter | Not present | `7ac1e8d8014e7fff765c65a80774d808a8b34d2cc2d88af8ef9ba8580ad820af` |
| `codex_retention_first_cell.py`, closed controller/admission binding | `054b5f3c68510594b19f53327b39bf973cb96b242e8ed2d1fc31736e6acf54d8` | `5bbbe1f715169192e7fdb45a5f19fe77d075633825b30ecf5dbb18f7b782576a` |
| `codex_retention_task4_fresh_r1.py`, shared task discriminator only | `047da1ab6083edab9e53120230122a8e41c26ce9853c359533b8b74768b9072a` | `b0c397dd6a6dc0f0650322f05ec68282eee92c3abc4099dd82c4a9480f5b8daa` |
| `codex_retention_fresh_r1_result_intake.py`, current dependency pins only | `d5f6162011028aa06fa4e9cbd58725a34d1f59b5bdfab92fef6eea84ab6d3bcc` | `d9c1c6a13203d38086ce76ede383d9c1c6459467649b716843ba3fd1434269b4` |
| `codex_retention_grade_readout.py`, separate current dependency pins only | `6d8b2190d83b9ce29fccf088ce4b50d72d9526cdd0adc19231cff32f7fdc61d5` | `fa7d7e9465e1c2f314f0aa17fbd901c7eb19e1bb64468f08c8e58e440b33c514` |
| `.github/workflows/codex-retention-first-cell.yml`, seventh execution route/current pins only | `fd5aba011aac3f5415606c680208f0cbfd722c3dd5fb5d863dbb7dce8b1c9f17` | `d42be461977c0ef6ae223a16ce28f3de2cb87d4b8096744b245e14cad1aeb7a0` |

That single producer proof checked all 15 observer dependency hashes and 9 checksums
in each read preflight, including the unchanged keep/r1 adapter before lazy
import. Both shared-reader CLI checksums then bound that producer task's current
bytes. The next table preserves PR725's accepted reader-only migration and
18.80s proof; it is historical, not another code change or test invocation in
this task.

| Historical PR725 executable source | Base `a8353cd4` SHA256 | Tested `ee24a3a1` SHA256 |
| --- | --- | --- |
| `codex_retention_fresh_r1_result_intake.py`, exact keep/r1 profile | `d14673345ed406c1f2054d55ee38209f28aa8862d7bd324d88ceeb36dd649e53` | `d5f6162011028aa06fa4e9cbd58725a34d1f59b5bdfab92fef6eea84ab6d3bcc` |
| `codex_retention_grade_readout.py`, current shared-reader pin only | `1c50c892557df11eda52703ad2c97c0becdc8ddca61601a67d868d5c64361695` | `6d8b2190d83b9ce29fccf088ce4b50d72d9526cdd0adc19231cff32f7fdc61d5` |
| `.github/workflows/codex-retention-first-cell.yml`, read allowlists/cases and current pins only | `96ac7c58f833aa4750da1e57dd6b3f67e633079188628cc2b281aaf403b61161` | `fd5aba011aac3f5415606c680208f0cbfd722c3dd5fb5d863dbb7dce8b1c9f17` |

The consumed keep/r1 producer adapter stays at
`21623a1a5bb661f105b8d9dcdfaaad13634c21cb8f1207189608f602b80b14ee`.
PR725 did not change its controller or shared publication discriminator; PR726
changed those two current roles only as listed above. The next table
preserves the earlier PR724 producer migration, not additional changes here.
At its test-only correction
`a8e88e5adaf93303032a4bd636f91d48085abaa6`, all executable hashes stayed equal
to 703d9bbf; its compatibility selector had checked 15 observer hashes and
8 checksums per read preflight at the original HEAD.

| Executable source | Base `eb0f400` SHA256 | Tested `703d9bbf` SHA256 |
| --- | --- | --- |
| `codex_retention_task5_keep_r1.py` | Not present | `21623a1a5bb661f105b8d9dcdfaaad13634c21cb8f1207189608f602b80b14ee` |
| `codex_retention_first_cell.py` | `ae5754bdd294a7560aecbe0d4c819bc6fdd123cf82fc652c6aedee5bae2701f7` | `054b5f3c68510594b19f53327b39bf973cb96b242e8ed2d1fc31736e6acf54d8` |
| `codex_retention_task4_fresh_r1.py`, shared task discriminator only | `11901d7398066d0ccf2692c3f1b41fe4a066d872efecfa411756d67858f941e1` | `047da1ab6083edab9e53120230122a8e41c26ce9853c359533b8b74768b9072a` |
| `codex_retention_fresh_r1_result_intake.py`, current dependency pins only | `89ba281379783d879e7c6208d29415c4aeea22a0af19569fe6c969c9f48f98c2` | `d14673345ed406c1f2054d55ee38209f28aa8862d7bd324d88ceeb36dd649e53` |
| `codex_retention_grade_readout.py`, current dependency pins only | `431f69bb264493041f7814c804a289fb9a52b70b4308eb886ba4186afda2bb89` | `1c50c892557df11eda52703ad2c97c0becdc8ddca61601a67d868d5c64361695` |
| `.github/workflows/codex-retention-first-cell.yml`, closed sixth route and current reader pins | `6cc111c823100a32d01668a816f1941360ffaf8ac09b7ff1aab8b59d0a843cef` | `96ac7c58f833aa4750da1e57dd6b3f67e633079188628cc2b281aaf403b61161` |

The consumed Task5 fresh/r1 adapter remains byte-identical to both bases, SHA256
`9919fda7728e84d0d707fe6a4b23a8a601c04b1e5241bcc83387b9acd20f0f5a`. The original
intake, CI verifier, Task4 fresh/r2 and keep/r2 adapters, grading adapters,
`grade-run.yml`, core runtime, registration, prompts, rubric/model/configuration
and dependency manifests are unchanged. Current-hash migration does not rewrite
any historical producer, writer, `RESULT`, `PARENT`, `READER`, result or receipt.
Keep/r2 evidence remains
`25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0`, first-cell
evidence `1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d`,
and keep/r2 intake marker
`4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4`.

### Historical reader proof, not this cell's validation

The preceding reader started from `e5e338aa22c247133936fa075c2def7bffb95173` after
the leader accepted PR722 HEAD `59320a3cb15aec72073ae4af466ff0a9201e0bae`, review
[5393747564](https://github.com/hyeonsangjeon/gdpval-realworks/pull/722#pullrequestreview-5393747564),
with all 10 checks passed. It added only the identity-equal `TASK5_FRESH_R1`
result/terminal binding, preserved old defaults and checked the unchanged Task5
adapter before lazy import. Successful intake and failed/stopped control-only
observation retained separate body/marker and no-grading-ready boundaries.
Only one fixed terminal path could be discovered, followed by immutable-revision
checks against independent source/run/attempt/request/job/cell/predecessor pins;
mutable latest, partial-claim adoption and replay remained forbidden.

| Historical tested HEAD | Actual outcome | Reached / unreached boundary and later correction | Log SHA256 |
| --- | --- | --- | --- |
| `f4a2c2fdd87e7b69ee99fec52bc0e33fcb19e2d9` | 3 collected / 2 passed / 1 failed in 17.71s; invocation exit 1, log-capture exit 0, no timeout | The success/terminal reader and current-source/historical-evidence selectors passed with synthetic transport and `live_effects=0`. The routing selector failed on a late helper import before its 224 mode cases, permission/secret/hash and missing-token CLI assertions. It was not a workflow failure. The separate 0240 order corrected import timing only. | `74c75d9273fb30cb54c51f71dc3ec236756797c917e112d01fb9a35c9bc86dcc` |
| `113ad8ad329a08978bc1185ba623f6baed28c065` | 1 collected / 1 passed in 4.13s; invocation exit 0, log-capture exit 0, no timeout | Only the failed routing selector reran. Collection-time module import after `_boolean` preserves the mutual helper dependency; all 224 mode/allowlist/permission/secret/hash and missing-token CLI checks passed under active guards with `live_effects=0`. Production/workflow/dependency/pin bytes were identical to `f4a2c2f`. The two original passing selectors were not rerun. | `1086d024317ad1c5a7fc519762c9f52f326dac0cfcb1a04a6397ed76a61b2dad` |

The original exception was `AttributeError: 'function' object has no attribute '_wait'`:
`test_codex_retention_ci_read_result.py:30` imported the observation helper,
`test_codex_retention_ci_observation.py:13` imported the execution helper, and
`test_codex_retention_ci.py:47` accessed `REAL_POPEN._wait`. The already active
offline fixture had replaced `subprocess.Popen` with its refusal function.
The correction restored no real Popen, added no fake method, swallowed no
exception, changed no guard and ran no private opt-in integration.

The original log and runner remain at `/tmp/project5-task5-reader-proof.nwly6s/pytest.log`
and `/tmp/project5-task5-reader-proof.nwly6s/run.sh`; runner SHA256
`13ec7d12bb96990c10ab2c9be8d899a8f8530c5c5340fcc32bc05fa99eb6f3ea`.
The correction log and runner remain at
`/tmp/project5-task5-reader-import-proof.CG9Exu/pytest.log` and
`/tmp/project5-task5-reader-import-proof.CG9Exu/run.sh`; runner SHA256
`0bb290c0438b2ed584ba2a48e4a5f30728eba42c63f91588f841e1ad9fd52b3a`.
Both used the same absolute CPython 3.10.12 / pytest 9.1.1 environment without
installation, token-free guards and a 180-second bound. Their runner records
preserve the exact commands; the original selectors were
`test_task5_fresh_r1_reads_only_its_fixed_result_or_terminal`,
`test_task5_reader_current_source_keeps_historical_grade_evidence` and
`test_retention_result_read_workflow_is_fixed_and_model_free`; only the last
selector ran in the correction. These remain proofs at two historical HEADs,
not a same-HEAD full-suite claim or validation of the new keep/r1 lifecycle.

That reader's source migration was `d042c02228f2430d4129ed37b3fb453cf9792bbde269a28bd10c6daf8f00b900`
to `89ba281379783d879e7c6208d29415c4aeea22a0af19569fe6c969c9f48f98c2`, observer
`adb13ac96702f0d38c49f2977e36607a4b8357f1ac9779de95aa18d0174f9587` to
`431f69bb264493041f7814c804a289fb9a52b70b4308eb886ba4186afda2bb89`, and workflow
`d2f800c9c512bdea0c81096f9309d6979c820f9eac9284a2344755a3adf059a1` to
`6cc111c823100a32d01668a816f1941360ffaf8ac09b7ff1aab8b59d0a843cef`.
At those reader HEADs all three Task4 facades were unchanged from its base;
that historical statement does not describe the current discriminator edit.

### Historical fifth-cell producer boundary

The delivered fresh/r1 producer implemented only Task5 ordinal 4. Its fixed
control-only predecessor was successful KEEP_R2 inference `e55fac5d60191167dd66688510ec0fef472e594d`,
with the exact identity/history/cleanup and actual-parent CAS checks preserved
below. Fresh recovery discards only a reconciled eligible owned native bundle
after confirmed cleanup; it never adopts prior-cell state or resets the
10800-second cumulative clock. The historical 44.78s synthetic proof reached
fresh reset, receipt settlement, persistent clock and completed outer lifecycle.
Its three earlier failures remain failures below. None was replayed in this
keep/r1 task. The following producer/readout source maps retain their historical
scope; the table above is the current executable mapping.
### Preserved source separation from the producer implementation

Read-only inspection at `07e330fd936860aa592bfc5751736e0e8a9c2ad9` established
that `codex_retention_fixed_grade._source` used historical `fixed.READER`
both for current-byte checking and the consumed grading evidence digest. A
controller/reader migration alone would make keep/r2 observation refuse;
rewriting `READER` would change historical evidence. This was a pre-edit
source-inspection boundary, not a failed runtime or test. The leader's
`PROJECT5-TASK5-SOURCE-SEPARATION-20261002-2130` APPROVE-WITH-CONDITIONS
authorized the narrow split, not final approval of this diff or a live run.

The shared `_source_checkout` retains the existing safe repository, unsafe Git
configuration, exact HEAD and clean-checkout checks. Paid `_source` still
validates the historical reader dictionary. Only the model-free grade observer
uses a closed source-controlled `CURRENT_DEPENDENCIES` set before private-root
creation, credentials, transport or payload access. The unchanged keep/r2 grade
adapter remains hash-checked before lazy import. There is no CLI/environment
dependency map, hash fallback, controller copy or historical-pin rewrite.
The original-input observer remains fixed to
`8ac891e3e0e4752fe15a00139a2691ddf9df7dce`; no historical reader loader was added.

The passing source-separation selector verified current dependency bytes,
both fixed readouts and the omitted-binding keep/r1 parent control verifier.
Tampered/missing dependencies, dirty/wrong checkouts, unsafe Git configuration
and changed historical source/run/claim/terminal/intake/ledger identities refused.
Historical `RESULT`/`PARENT`/`READER`, both grading evidence digests and the
keep/r2 intake marker remain unchanged. The paid keep/r2 reader correctly
refuses these new current bytes against its historical pins. Its old lifecycle
test now asserts that refusal before binding its own explicitly synthetic
fixture bytes; no consumed grading authority was migrated.

### Historical producer proof and preserved failures

The final correction was pinned before validation at
`4a2be68c96ef3f3e0961eb65fe15270a81baac6b`. The verified absolute interpreter
again reported CPython 3.10.12 and pytest 9.1.1 without installation. Exactly
`tests/test_codex_retention_task5_fresh_r1.py::test_task5_fresh_r1_is_the_closed_fifth_cell`
ran once from `batch-runner`, using the single-selector command printed below,
the same token-free offline/process/network guards and the 180-second bound.
Result: 1 collected / 1 passed in 44.78s, exit 0, no timeout; log capture exit 0.
Log `/tmp/project5-task5-publication-binding-proof.uQTl3q/pytest.log`, SHA256
`9213298b7d7376b4ac60c4f794bddd7001fede53943f8ae1628387dddb5590ed`.
Command `/tmp/project5-task5-publication-binding-proof.uQTl3q/command.txt`, SHA256
`29247dde61ddf35befe8f7b013ab1dc47324a283c71cab859a8648c75f5303c4`.

The real shared verifier accepted canonical Task4 paths for each existing
Task4 successor and rejected Task5 paths before transport reads. It accepted
the new Task5 path only through ordinal 4 and rejected Task4 paths there.
Noncanonical binding types, malformed cell IDs and unsupported cells refused
before control reads or cache creation. No caller task-ID override, path-prefix
inference, new schema, permissive hash or canonical-path bypass was added.

The corrected fresh-state sequence described below completed, followed by a
successful synthetic owned child and execute-return with
`remote_terminal=acknowledged`. Terminal/claim/manifest readbacks and object
history checks completed. Read-only reconciliation left the writer receipt
unchanged and still reported `writer_acknowledgment=not_established` and no
replay authority. The lost-terminal-response case likewise remained unresolved
after observation; it did not become a new acknowledgment or another child.
Same-host and remote no-replay refusals, cleanup failure stopping publication,
and later timeout/cleanup/publication assertions all completed. The safe test
observer still delegates unchanged to the real error classifier and is scoped
to the synthetic transport being exercised. No live effect occurred.

Static checks, not reruns of the two earlier passing selectors, verified all
15 current observer dependency files and 16 workflow hash-pin occurrences.
Both fixed grading evidence digests and the intake marker remained exact.
The two directly coupled test expectations changed only their current hash
literals. Static output SHA256:
`0664621b31cbab09df31d4bea6ff73605191bc48aa7da4144b0ca9e3dded3fc8`.
The following attempts remain historical failures, not results relabeled by
this passing invocation.

Original production/workflow/test HEAD:
`2068c92d4841e5f7be7aa9e9fc027c9dcc0205d5`. The token-free prerequisite on
`/ai-work/venvs/gdpval-realworks-py310/bin/python` printed CPython
`3.10.12 (main, Jun 22 2026, 18:55:27) [GCC 11.4.0]` and pytest `9.1.1`,
without installation. The original three-selector invocation ran from `batch-runner`:

```text
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest tests/test_codex_retention_task5_fresh_r1.py::test_task5_fresh_r1_is_the_closed_fifth_cell tests/test_codex_retention_observer_source.py::test_current_observer_source_preserves_historical_grade_bindings tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free -vv -s --tb=short -p no:cacheprovider
```

| Selector | Exact outcome and scope |
| --- | --- |
| `test_task5_fresh_r1_is_the_closed_fifth_cell` | Failed at test lines 87–88. Expected `fresh bundle lacks a reconciled eligible recovery`; received `native thread creation was interrupted before its identifier was bound`. `task.continuation(identity)` refused before `require_fresh_retirement` could run. The wrapper reported `task5_claim_fresh_recovery_child_output_terminal:AssertionError:__exit__`. |
| `test_current_observer_source_preserves_historical_grade_bindings` | Passed real current-source/evidence validators, both synthetic numeric readouts, omitted parent controls, privacy/no-clobber and identity/history/ledger refusals. Historical grading digests remained exact. |
| `test_retention_result_read_workflow_is_fixed_and_model_free` | Passed the directly coupled closed routing, mode exclusion, old defaults and current precredential pin checks. This does not validate Task5 child completion. |

Overall: 3 collected, 1 failed / 2 passed in 51.26s, exit 1, no timeout.
Log `/tmp/project5-task5-fresh-r1-proof.JPIuKw/pytest.log`, SHA256
`15c8dbf5bf0534c2630dc3a9c9a6a7821b1412c5fcced67a83d23a686cb98495`.
The saved command/prerequisite record is
`/tmp/project5-task5-fresh-r1-proof.JPIuKw/command.txt`, SHA256
`284bbd9b38523d46502f4d04f214e7de18b1d3b33e91afc6a7508f6d8bbf3e1f`.

The lifecycle reached old-reader control compatibility, Task5 packet/staging/
request checks, old-entrypoint and exact admission-pair refusals, predecessor/
CAS/uncertain-claim refusal cases, a successful synthetic admission and the
owned-process callback. It stopped at the fixture's ambiguous native-start
check. Completed fresh reset/recovery, successful child completion, output/
terminal publication, reconciliation and the later timeout/cleanup assertions
were not reached. The existing guard was not changed to satisfy the expected
message. That invocation stopped without a repair or rerun; the leader later
authorized only the fixture correction and single follow-up below.

The routing selector's printed `mode_cases=192` and
`scope=synthetic_keep_r2_reader_routes` are inherited summary labels; they were
not corrected after the reached failure and are not a Task5 lifecycle result.
The invocation used synthetic records and offline/process/network guards with
plugin autoload disabled, no `-x`, collection probe, old full suite, renderer,
private integration, model call or live read/write.

Under `PROJECT5-TASK5-FRESH-FIXTURE-20261002-2201`, the ordinary test-only commit
`e29f26b8e3ae91907fb7ba759da0feeee20d7046` changes only
`tests/test_codex_retention_task5_fresh_r1.py`. At that HEAD, production, workflows,
dependency manifests, the current pin map and historical evidence were byte-identical
to `2068c92d4841e5f7be7aa9e9fc027c9dcc0205d5`. The corrected test SHA256 is
`c42e389245c0b8df6a1a6cd2fd2f7d3d52f05121187fc4d76f94739acfb6ebdf`.

The fixture now separates the precise interrupted/unbound-start refusal from
retirement ineligibility after binding a deterministic returned thread ID.
It records a synthetic B-eligible failed turn through the real deadline and
cost-receipt APIs, refuses retirement before usage settlement, and verifies
the settled receipt after reopening the stores. The synthetic `rate_limited`
observation is fixture data, not a cause assigned to any actual failure.
Retirement before owned-workspace cleanup also refuses. Only after eligibility
and cleanup does the fixture retire the old bundle and create a distinct one;
prior-cell state and unrelated output remain intact. Its original 10800-second
clock survives a 30-second wait and 45 seconds of downtime, leaving 10725 seconds,
with two admissions, zero native resumes and one retired bundle. No phase or
checksum was forced, and no production guard was mocked or changed.

The same absolute interpreter again passed the CPython 3.10.12 / pytest 9.1.1
import prerequisite without installation, under the same token-free environment.
Only the failed lifecycle selector ran, once, from `batch-runner`:

```text
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest tests/test_codex_retention_task5_fresh_r1.py::test_task5_fresh_r1_is_the_closed_fifth_cell -vv -s --tb=short -p no:cacheprovider
```

Follow-up result: 1 collected / 1 failed in 26.67s, exit 1, no timeout. Log
`/tmp/project5-task5-fresh-fixture-proof.Eydccz/pytest.log`, SHA256
`51a95d83582a52fb70275391af6c2338c04230b2de1deb226e69f4685f5f6b53`.
The exact command is saved at
`/tmp/project5-task5-fresh-fixture-proof.Eydccz/command.txt`, SHA256
`d2a736a12bbf57bedb31a7eefb83e6bdedcfa9f4c77ded6759594f8cb36b4394`.
The failure is `retention_terminal_unresolved:hf_operation_failed`, wrapped as
`task5_claim_fresh_recovery_child_output_terminal:retention_terminal_unresolved:hf_operation_failed:require`.

All corrected fresh-recovery callback assertions above completed. The outer
lifecycle then reached its first synthetic terminal-publication attempt and
refused before execute returned. Its succeeded/cleanup/ack result assertions,
post-return event/parent/readback assertions, terminal reconciliation and later
lost-ack/no-replay/timeout/cleanup cases were not reached. The underlying
`hf_operation_failed` cause was not investigated during that 2201 corrective
task. It stopped without another repair or invocation, rerun of either passing
selector, push, draft PR or live operation. That result remains an
incomplete lifecycle proof, not an acknowledged terminal or successful cell.

The leader then authorized `PROJECT5-TASK5-PUBLICATION-CAUSE-20261002-2232`.
The saved log contained no original exception, and the test-owned publication
receipts had not survived their `TemporaryDirectory`. A scoped test-only
observer was pinned at `77118007ffe9d676e740e98d36bb8e6847fc3a8d`. It delegates
unchanged to `_error_context`, reporting only exception classes, repository-relative
code locations, fixed operation labels and nonsecret state counts. It neither
prints exception messages/payloads/credentials/private absolute paths nor mocks
success. At that diagnostic HEAD, the fresh-recovery sequence and all production
bytes were unchanged.

After the same CPython 3.10.12 / pytest 9.1.1 import prerequisite, the exact
single-selector command above ran once as a diagnostic, under the same token-free
offline/process/network guards and 180-second bound. Result: 1 collected /
1 failed in 29.18s, exit 1, no timeout. Log
`/tmp/project5-task5-publication-cause-proof.ns2Ql4/pytest.log`, SHA256
`f9a9d047ead8725b9d83b15b687c374725a7ffd4df4fd6e98a51a7734cefb7c2`.
Command record `/tmp/project5-task5-publication-cause-proof.ns2Ql4/command.txt`,
SHA256 `e38b675fc23ffcb15c0187dc0836a13945c40ce1ceb77752b9aa0ffd1c565214`.

The original exception was `ValueError`, with no further explicit cause:

| Operation | Repository-relative source |
| --- | --- |
| `_finish_publication` calls the publication verifier after terminal commit returns | `batch-runner/codex_retention_task4_fresh_r1.py:286` |
| `_verify_publication` passes hardcoded `registration.TASK4` for the Task5 deliverable | `batch-runner/codex_retention_task4_fresh_r1.py:171` |
| `canonical_deliverable_path` rejects the mismatched task UUID | `batch-runner/core/inference_manifest.py:110` |

The unchanged `_error_context` maps that `ValueError` to `hf_operation_failed`.
The synthetic transport recorded 3 commit calls: one admission, one output and
one terminal attempt. Both output and terminal commit IDs returned; one terminal
control was committed, with 4 current output objects and one owned child.
Writer acknowledgment remained 0, with stage `terminal`. These counts describe
only this diagnostic's synthetic state, not a live publication or a reconstruction
of the unsaved 26.67s receipt. No actual deliverable count is inferred.

The returned terminal commit means `_commit` had already completed its own exact
control readback/equality at `batch-runner/codex_budget_pilot_retention.py:433`.
The earlier output-object history check had also completed. The later publication
verifier failed at its role/path check, before its own terminal/claim/manifest
readback and final object-history checks. A committed control is not a successful
writer receipt. Execute-return, full publication acknowledgment, reconciliation
and the later lost-ack/no-replay/timeout/cleanup assertions were unreached in
that diagnostic.

The 2232 diagnostic stopped without a source change or second invocation
because correcting the shared verifier needed separate authority. The leader's
`PROJECT5-TASK5-PUBLICATION-BINDING-20261002-2303` APPROVE-WITH-CONDITIONS
subsequently authorized only the closed task mapping and necessary current-pin
migration. The correction and passing proof above followed that decision.
There was no Task5-to-Task4 path relabeling, copied verifier, weakened predicate
or historical-pin rewrite. Conditional scope authority is not final source
approval or permission to execute a live cell.

### Prior readout behavior and historical proof

The existing fixed model-free `retention/keep-r2-readout` implementation was
tested at `8a0b1c368d1e02bf21453bf75e1399f01d0a771f`: 2 collected / 2 passed in
27.10s, exit 0, without timeout. That real-validator/synthetic-transport proof
was not a live read and was not rerun. It started from
`b99a28a4c0ec0ed961a2a8ddcaa886462beb0691`. Prior grading source PR720 HEAD
`4a5f1852933e4958669b6b41e6aa755aca1db428`, owner review
[5389266031](https://github.com/hyeonsangjeon/gdpval-realworks/pull/720#pullrequestreview-5389266031)
and all 10 checks passed that grading source gate. Neither that historical
review nor the prior proof is final source approval for this Task5 implementation.

The existing retention grade reader now has exactly two closed read bindings.
The public `retention/grade-readout` constants and omitted helper arguments
still select keep/r1, including the unchanged keep/r2 grading adapter's parent
verifier. Only `retention/keep-r2-readout` selects the explicit keep/r2 grading
context, KEEP ordinal 3 / repetition 2, and its independent writer/terminal pins.
The unchanged keep/r2 adapter's exact bytes are checked before lazy import or
credentials. The shared read-only projection accepts the existing exact
`RetentionKeepR2LedgerBinding` only with its matching canonical context; the
first-cell type and old pilot ledger contract remain distinct.

The reader verifies the fixed immutable terminal, canonical claim and object
history, then downloads only declared `grade_result` and optional
`grade_cost_ledger` payloads. It reuses type, identity, role, size, transfer/time,
privacy and private no-clobber checks. Terminal reread and claim verification
precede payload access. There is no mutable-head discovery, inference-body
read, retry fallback, publication, materialization or judge entry.

The numeric projection preserves included-score and full-denominator score,
exclusions, retained-item coverage, recorded costs and separately validated
ledger-derived costs, with nulls and missing reasons intact. It exposes no
rubric text, deliverables, private paths, prompts or raw ledgers. The original
result fingerprint and writer preparation hash do not reconstruct the
materialized-input fingerprint: that comparison remains unavailable because
it was not recorded. Provider job `110766211046` is explicitly supplied, not
independently authenticated by controls that record only logical job `pilot-live`.

The prior addition used only the existing contents-read `pilot-readout` route;
`pilot-plan` excludes its selector. The dispatcher uses exact selection, and
that task updated both directly coupled old workflow expectations. All nine jobs, paid
selector groups, generic-retention exclusions, inputs, permissions, concurrency,
timeouts and step-only HF credential remain. The grader, judge, rubric, model,
inference producers and paid paths are unchanged; no experimental or budget
axis was added.

### Completed Task4 keep/r2 grade and fixed numeric readout

These are leader-read phase receipts, not results of the prior readout's
synthetic proof. Workflow `280490256`, run `36984239149`, attempt 1, job
`110766211046` / `pilot-live` used writer source
`b99a28a4c0ec0ed961a2a8ddcaa886462beb0691` and selector `retention/keep-r2`.
All times below are UTC on 2026-10-02.

| Phase receipt time | Reported evidence |
| --- | --- |
| 08:33:48.7096183Z | `judge_ready`, intake marker `4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4` |
| 08:34:01.0866232Z | Claim acknowledged at `f8d5189a86c297499c77084aeeb697aea15aad00` |
| 08:40:46.4081749Z | Judge `entry_invoked=true`, exit 0, `timed_out=false`, `cleanup_confirmed=true` |
| 08:40:54.0824759Z | Publication acknowledged, `grading_state=graded`, terminal `76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e`, SHA256 `d1f2a48d392044937a904243feb5ab0d320d271f1082806ac2aa9e927cb3c66c`, 3107 bytes |

The fixed grading evidence is
`25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0`.
The input is inference terminal `e55fac5d60191167dd66688510ec0fef472e594d`,
result fingerprint `909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a`,
from producer `b8351e561acb9675a4993419e819c12787b5b305`; the separate grade
parent remains `40712e0980cc05c31688fdbb98c693774fb90c0d`.
Numeric score and grade accounting were absent from those phase receipts.
The leader subsequently read fixed readout `36999576988` / job `110813946845`
at source `07e330fd936860aa592bfc5751736e0e8a9c2ad9`. Its
`2026-10-02T11:32:45.1993344Z` receipt verified 30.35 / 45 = 67.44% included,
54.20% full denominator and 9 excluded items / maximum score 11. The grade terminal
identity above remains unchanged; claim `f8d5189a86c297499c77084aeeb697aea15aad00`
has SHA256 `2bf4fad3a789915e56f8fe6b842821f275e1994e0ca577d64654df773923b23b`,
2512 bytes.

The grade ledger records 91 model calls, missing reason `price_missing`, with
known/model/estimated/runtime costs null and `invoice_complete=false`. Recorded
grade usage is input 264029, cached input 199080, output 19748 and reasoning
14411; cached/reasoning counts are subsets, not extra totals. The readout is
writer-recorded/publication-derived, not independent provider authentication
or an established retention benefit. The unrecorded materialized-input
comparison remains unavailable. No keep/r1 score or inference cost is
substituted. The grade and its input inference are consumed: no redispatch,
regrade, repeat readout, low-score retry or reset occurred or is authorized here.

### Historical targeted readout proof

The prior implementation/workflow/test bytes were pinned at
`8a0b1c368d1e02bf21453bf75e1399f01d0a771f` before validation. The same
token-free prerequisite printed
`sys.executable=/ai-work/venvs/gdpval-realworks-py310/bin/python`,
`sys.version=3.10.12 (main, Jun 22 2026, 18:55:27) [GCC 11.4.0]` and
`pytest.__version__=9.1.1`, exit 0, without installation. Exactly one invocation
ran from `batch-runner` in that prior task, not in the current Task5 task:

```text
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 timeout --signal=TERM --kill-after=10s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest tests/test_codex_retention_keep_r2_grade_readout.py::test_keep_r2_grade_readout_is_fixed_numeric_and_model_free tests/test_codex_retention_keep_r2_grade_readout.py::test_keep_r2_grade_readout_routes_and_historical_default_stay_closed -vv -s --tb=short -p no:cacheprovider
```

Saved log:
`/tmp/project5-keep-r2-grade-readout-20261002-1755.OHqeAP/pytest.log`, SHA256
`915a61788524b9ccfe1f16b79ea64123200b64fd43e4866bfe324e280392e4c7`.
Result: 2 collected, 2 passed in 27.10s, exit 0; the 180-second timeout did not
fire. Offline process/network/model guards remained active, plugin autoload
and implicit HF tokens were disabled, and no real credentials were supplied.
No `-x`, separate collection probe, old suite, private integration, renderer,
full suite or build was used.

The proof reached real source, terminal/claim/history, payload/schema,
typed-ledger and safe numeric/accounting validators. It covered wrong source,
run/logical job/attempt, selector/cell, evidence/intake, parent, hashes, types,
roles, history, bounds, private target, missing controls/ledger and no-clobber
refusals. Wrong adapter/reader bytes refused before credentials or transport.
The successful synthetic read made one fixed metadata query, five bounded
path checks and five body downloads (terminal twice, claim once, two declared
grade roles). No inference body, private input, write or judge path was reached.
Synthetic included/full-denominator scores were 50%/33.33%, with one excluded
item; synthetic accounting was 2 calls / known USD 0.0123 partial. These are
test data, not the observed keep/r2 score or grade accounting.

The coupled selector parsed the current YAML's exact read/plan groups and
paid/secret guards, validated the old typed projection and exercised the
unchanged grading adapter's omitted-binding keep/r1 parent verifier with
synthetic control identities. The small exact pilot-plan expectation was also
updated in `test_step8_grade.py`; its unrelated full test was not replayed.

### Historical grading proof and corrections

The earlier one-use `retention/keep-r2` producer proof at
`7d90f7dcce88537d8fe2fa271c19be68078ca019` remains 2 collected / 2 passed in
36.42s, exit 0, no timeout. Its log is
`/tmp/project5-keep-r2-grade-filename.Y8x8dU/targeted.log`, SHA256
`bef2f512c1d22474d69d564b38e965deda8c454a004e80901622ad45edf54c16`.
Both `test_keep_r2_fixed_grade_is_bound_one_use_and_private` and
`test_keep_r2_fixed_grade_workflow_approval_and_ledger_are_closed` in
`tests/test_codex_retention_keep_r2_grade.py` passed. Real marker/payload
readback, materializer provenance/derived fingerprint, original rubric,
separate grading-parent history/current-parent CAS, one synthetic owned judge,
private publication, lost-ack read-only reconciliation and protected approval
were reached. That earlier synthetic proof was not a live grade or independent
provider/writer acknowledgment, and was not rerun here.

The leader's source-informed 1246 APPROVE-WITH-CONDITIONS decision covered
the grading scope; 1316 authorized only fault-injection setup, and 1418 only
the unpublished selector rename and coupled bindings. These decisions did not
authorize a paid run. Failed reviewer transports were not treated as approvals
or retried. Owner review
[5388701816](https://github.com/hyeonsangjeon/gdpval-realworks/pull/720#pullrequestreview-5388701816)
source-approved `fedf80d4298aeb0e4a4fbc43086ddffc148ad236`; review
[5388860597](https://github.com/hyeonsangjeon/gdpval-realworks/pull/720#pullrequestreview-5388860597)
was conditional on CI. The later `5389266031` source gate is identified above.
Prior reader PR719 HEAD `2f865eb6491e236ebe54027f29c030d75e88cef0`, review
[5387838626](https://github.com/hyeonsangjeon/gdpval-realworks/pull/719#pullrequestreview-5387838626)
and all 10 checks passed its source gate; its 1429-line review and 19.11s
reader proof were not repeated.

| Historical tested HEAD and result | Log SHA256 | Refusal and reached/unreached boundary | Subsequent correction |
| --- | --- | --- | --- |
| `44fa6694f73fad8d6ad202855e5847b6c4212d6d`: 2 collected, 1 failed / 1 passed in 7.32s, exit 1; no timeout | `3070012930c09ed096529c73e50ba0a6ee997f412da28874e8249ed661f5234e` | At test line 195, expected `reviewed_retention_reader_required` but correctly received the earlier `retention_grade_context_changed`. Canonical request compilation, frozen-reader checks, synthetic KEEP_R2 intake and pre-root approval/source refusals were reached. The intended bad-byte predicate, successful preparation/materialization, grade-parent history/CAS, owned judge and publication were not reached. The workflow/approval/ledger selector passed only against the old long selector. | `9a628e52732c162dd0a179ca96579dacc402a4d2` retained the expected-pin context-mutation refusal and added actual-reader-byte corruption with canonical expected pins. Production and workflow bytes did not change in that test-only correction. |
| `9a628e52732c162dd0a179ca96579dacc402a4d2`: lifecycle only, 1 collected / 1 failed in 8.64s, exit 1; no timeout | `99ca382018a16c5b6145db7a200ef1d1ec67cd05a5ad81cc15c1873e44cf4ca1` | Corrected context-mutation and actual-byte refusal checks completed. The first intended successful `bridge.prepare` at test line 234 reached `codex_retention_fixed_grade.py:368`, then `_entry_contract` at `codex_budget_pilot_grading.py:747`, and refused with `grading_filename_capacity_refused`. Successful preparation, derived fingerprint/materialization, grade-parent history/CAS, judge, publication and reconciliation assertions were not reached. | `7d90f7dcce88537d8fe2fa271c19be68078ca019` applied the leader-authorized shorter selector and filename assertions. Its changed routing/authority bytes required the separately authorized two-selector proof above. |

Neither historical failure is relabeled as a passing lifecycle proof. Their
logs remain `/tmp/project5-keep-r2-fixed-grade.gz9e7b/targeted.log` and
`/tmp/project5-keep-r2-grade-test-correction.uEdJ4x/lifecycle.log`. The first
attempt used both named selectors; the second used the lifecycle selector only
with the same runner/offline flags and bound. Its test wrapper delegates to
the real `output._bytes`, corrupts only bytes returned for the exact dependency
path, confirms the targeted read, and requires `reviewed_retention_reader_required`
with no private root, transport call or owned-judge activity. Expected-pin
mutation still requires `retention_grade_context_changed`; no guard was
weakened or reordered.

The historical grading prerequisite printed
`sys.executable=/ai-work/venvs/gdpval-realworks-py310/bin/python`,
`sys.version=3.10.12 (main, Jun 22 2026, 18:55:27) [GCC 11.4.0]` and
`pytest.__version__=9.1.1`, exit 0, without installing packages; its log SHA256
is `5f1ef71b3a20194547eb67a95ef44e8a440bd619cf6be992e3b599c9469f60cb`.
The later prerequisites also passed without installation; both
`/tmp/project5-keep-r2-grade-test-correction.uEdJ4x/prerequisite.log` and
`/tmp/project5-keep-r2-grade-filename.Y8x8dU/prerequisite.log` have SHA256
`5513d294c3594784460699bb31a4f4ba3698c333c8f144c3b8085264a9d98b96`.
The earlier reader's missing-pytest failure and authorized replacement proof
remain separate in the preexisting history below.

### Historical CI workflow-contract correction

The leader read the actual CI log for run `36972501988` / job `110729309892`
at published HEAD `8adeaba71228f3da6e8b484436e148d335339f49`: pytest reported
2 failed, 13312 passed, 64 skipped and 46 deselected in 1048.45s. The failures
were stale expectations for already reviewed workflow bytes, not a failed
keep/r2 lifecycle proof. No CI log was fetched again and no full suite was
replayed for this correction.

Three expected expressions in the existing readout and Step8 tests were
corrected to retain the closed `retention/first-cell` OR `retention/keep-r2`
paid group and exclude keep/r2 from generic planning. Surrounding approval,
permission, RC7, resume, secret, no-OIDC and no-model assertions stayed intact.
At test-only HEAD `cbe0d5d9ad2567bb1a486860de439ce8a9028d34`, exactly
`tests/test_codex_retention_grade_readout.py::test_first_retention_grade_readout_is_immutable_writer_recorded_and_unpaid`
and `tests/test_step8_grade.py::test_grade_workflow_rc7_requires_valid_committed_partial`
ran once: 2 collected / 2 passed in 41.88s, exit 0, no timeout. Log:
`/tmp/project5-pr720-ci-contracts.il0bbJ/targeted.log`, SHA256
`cc227b2dbece1f417f13f0328c71e8369bf1e02b9bb0a395c054969162fe6464`.
Its CPython 3.10.12 / pytest 9.1.1 prerequisite passed without installation;
`/tmp/project5-pr720-ci-contracts.il0bbJ/runner-prerequisite.log` has SHA256
`5f1ef71b3a20194547eb67a95ef44e8a440bd619cf6be992e3b599c9469f60cb`.
The same token-free offline flags and 180-second bound were used, with no
`-x`, skip/xfail, collection probe, renderer, private integration or full build.
Full historical commands remain in the task record at base `b99a28a4c0ec0ed961a2a8ddcaa886462beb0691`.
Production/workflow/dependency/pin bytes in that correction matched `8adeaba71228f3da6e8b484436e148d335339f49`;
only those two tests changed before validation and the two records afterward.
Neither that CI correction nor the 36.42s lifecycle proof was rerun here.

### Preserved filename proof for the consumed grading selector

Before the passing invocation, the real fixed config, Step8 output resolver,
judge slug and checkpoint resolver produced these UTF-8 leaf lengths. Actual
`os.pathconf(..., "PC_NAME_MAX")` was 255 on both the worktree and test-owned
filesystem; the limit was not mocked.

| Derived leaf | Former long selector, bytes | Final `retention/keep-r2`, bytes |
| --- | ---: | ---: |
| Grade JSON | 219 | 213 |
| JSONL cost ledger | 232 | 226 |
| SQLite cost ledger | 234 | 228 |
| SQLite `-wal` | 238 | 232 |
| SQLite `-shm` | 238 | 232 |
| SQLite `-journal` | 242 | 236 |
| Checkpoint | 257 | 251 |
| Atomic checkpoint temporary | 261 | 255 |

The temporary checkpoint fits exactly, with no spare bytes. The test asserted
every required leaf against the actual limit and completed a tiny real
checkpoint write/readback including the 255-byte temporary leaf. It proves the
local boundary, not an unmeasured host's capacity. No UUID/hash truncation,
random path, global Step8/checkpoint naming change or relaxed filesystem check
was used. Generated config hash: `62a6d99d9e74d187`. Full derived names are in
`/tmp/project5-keep-r2-grade-filename.Y8x8dU/filenames.json`, SHA256
`5d5dbf13a662280080b0f04862e81753c4b49482074c00b75af0aac53b1e43eb`.

### Fixed input, marker and grading-parent evidence

These are independent leader-supplied live-evidence pins, not products of the
synthetic proof. Successful intake used workflow `370228282`, run `36959616821`
/ attempt 1 / job `110690181822`, reader source
`f1f274f1b0510a9f4d7e7c969574913442105579` and reader SHA256
`5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583`.
The `2026-10-02T03:21:22.9144192Z` receipt reports `intake_verified=true`,
`status=succeeded`, `cleanup_confirmed=true`,
`recorded_publication_acknowledged=true`, `grade=null`, `grading_launched=false`
and `invoice_complete=false`. Approval/execution jobs were skipped. That read
was not repeated here or during the earlier implementation, records
consolidation and CI-contract correction.

Consumed producer `b8351e561acb9675a4993419e819c12787b5b305` ran as
`36947454688` / attempt 1 / execution job `110660390316`, for cell
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2`.
Request SHA256:
`8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1`.
Original input-bundle SHA256:
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Path-specific materialized grader-source SHA256:
`997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1`.

| Inference object | Immutable revision | SHA256 | Bytes |
| --- | --- | --- | --- |
| Terminal | `e55fac5d60191167dd66688510ec0fef472e594d` | `70fb8778ae15e369ef1ac4d03dbe4fa6f5d9852966b250fa812695d6bd77bf91` | 5885 |
| Claim | `f29f8d4a19710aa0e832dba720ff7d32701c309c` | `4af63e82ddcaf2b795595081c59d29369e2bf2a4bb2c37f81eb7f5409cd6b363` | 1888 |
| Output manifest | `54a4362ce3554b7c71b5ada00802efc9521038e6` | `93e1dada24779909cfc593dff7507b7f9c6452c6f36c12b2c5e86305e35d9a8c` | 2679 |

The output-object-set SHA256 is
`4bda1c0d48a5dd980bd683a6f8316b3d52808e95dca68099b86ad4de2d3e03b2`;
the full intake marker SHA256 is
`4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4`;
retained-authority SHA256 is
`7427be5a3d3f5692ca9d92920161c7ddf4491faf39f36f9ee9cee062f45f5705`.
The 10238-byte result has SHA256
`8d90bb52bc87f5989baba1eea59de205155523492e9b679087eac5c12b7e539e`
and fingerprint `909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a`.
Its recorded prepared fingerprint is
`fb6e4301ec91245601e80fc6f181076513dd71bd358bb0fbc856b5080e8108e8`,
and registered config SHA256 is
`307dc07923d377faa7d7c6bd6c4934de2fa5f99e9007dd0d723f3c3337e6d010`.
The consumed keep/r2 producer's own inference predecessor remains failed fresh/r2 terminal
`1d5133590911f3704fc2a65279d4b64bee77c1d6` through the frozen producer's pins.

The safe intake receipt does not disclose a deliverable count or the full
marker's files/result-generation fields; none is fabricated from that projection.
The reviewed grading preparation requires full marker/payload revalidation
because `consumer_readback_required=true`, deliverables-only `source_upload`
staging, recomputed materializer provenance/fingerprint and exact original
rubric/grader bytes. Its reported `judge_ready` receipt is not independent
reconstruction by this readout. The original result fingerprint is not the
materializer's derived-input fingerprint. Neither intake nor inference is replayed.

The consumed grading path's parent on `pilot-grades-20260925-04` is keep/r1 grade
terminal `40712e0980cc05c31688fdbb98c693774fb90c0d`, not keep/r2 inference
terminal `e55fac5d60191167dd66688510ec0fef472e594d`. Its SHA256 is
`11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234`, 3119 bytes;
claim `dec305d669e3ca2e53c7f7b9ebfbe7974d661350` has SHA256
`8e1e0a51b462a442e9024c2bd5140d3898b61424ce3f44d4adff9fa346cce53d`, 2384 bytes.
Its writer is `29e0353f1539265b1741e71be894fedf9be32a8b`, run `36776393736` /
job `pilot-live` / attempt 1, previously verified by readout `36820845596` at
source `f30c9efa392bc14cba790fb5d1dedf12071a5677`. Its inference terminal
`de50ff0aa6037c0ef6e3b713da519359abd1d08d` and result fingerprint
`3441f200e6e4c53faf1b36f216283c80eee68e5d3e7d827587ba6c3135c7d200` remain
historical. Existing readout predicates verify controls, claim and object
history without payload-body reads. Historical verification is not current
branch-head evidence. The frozen writer requires exact current-parent equality
before one-use CAS; drift or uncertainty must refuse, not adopt or reset. This
readout neither queries that mutable head nor permits another CAS for the
consumed grade.

### Accounting and proof limits

Actual recorded Task4 keep/r2 inference accounting is partial: 6 model calls,
comprising 5 infrastructure-retry calls with known USD 0.22195 and 1 generation
call with `known_cost_usd=null` and recorded zero token counters. Aggregate
known/model cost is USD 0.22195, partial. Recorded usage is input 194536,
cached input 163840, output 6950 and reasoning 4096. Cached/reasoning counters
are subsets, not additional token totals. The generation component's zero
counters and null cost do not establish free work or zero actual usage.
Estimated cost, runtime cost and HTTP request count remain null; missing reasons
are `call_reachability_unknown` and `usage_absent`, with `invoice_complete=false`.
Model calls are not HTTP requests or native admissions/resumes. These are
inference costs only. The separate fixed grade readout reports 91 recorded
model calls and usage as listed above; all its monetary totals remain null
with `price_missing`. Its 67.44% included / 54.20% full-denominator scores and
grade accounting are not inferred from this intake.

This intake is publication-derived evidence, not independent provider,
original-input or CAS authentication; `writer_acknowledgment=not_established`.
At the time of that Task4 intake, four producer outcomes were recorded. The two Task5 r1
failures above bring the recorded count to six. Ordinal 6 is now dispatched
with outcome pending at the supplied observation; ordinal 7 remains unexecuted.
The original 30-cell pilot remains closed. Task4 keep/r1 scores remain 68.0% included /
54.64% full with their exclusions; failed Task4 fresh/r1 remains 39 calls / known
USD 0.303358 partial, and failed Task4 fresh/r2 remains 39 calls / known USD 0.29944
partial. Their null grades and unavailable detailed cause/budget/recovery
evidence remain unchanged. Duration or retry labels do not identify a failure
cause, and these repeats do not establish a retention benefit.

### Frozen grading evidence and historical readout source changes

The reviewed selector-bound evidence SHA256 is
`25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0`.
It replaces only the unpublished long-route digest
`eacfc94a16f6fdee0d3259590d35abd0e9d365733742946b8b139b705d5def07`.
Historical first-cell evidence remains
`1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d`.

| Historical source at tested `7d90f7dcce88537d8fe2fa271c19be68078ca019` and reviewed `fedf80d4298aeb0e4a4fbc43086ddffc148ad236` | SHA256 |
| --- | --- |
| `codex_retention_keep_r2_grade.py` | `bb8d1b3a46824a2597f31fe6567531fc59deabb79af87e85d98fd1a08ae3988e` |
| `codex_retention_fixed_grade.py` | `7790852b04f8496db8b13ac6957badf641175c501f422720a7d14896b340d5ac` |
| `codex_budget_pilot_output.py` | `635966f42c0310c9093d59e8f417259a0625b847c52f73342c07ec6c64fa2fdb` |
| `.github/workflows/grade-run.yml` | `a59762078a6dc81a9867490338873a2f6db2ebb8f456f37759874b40710b6824` |

For the historical long-route attempts, adapter SHA256 was
`5c403632d33cebf4e5cf0fb212c7a8262484a6dfe05be7e1acd67a672e978c91` and shared
fixed-grade controller SHA256 was
`e0b3c878b735e4e2e30b54b528c1887807f02cd326cfc0e32c2bf947106ab44f`.
Those are historical bytes, not current pins. The producer-era Task5 controller
and shared-reader migrations below remain historical; the current reader mapping
is above. At source-reviewed
HEAD `979df01aeeee9a3a0a624e605fa47e887f18b048`, the original intake, CI verifier,
Task4 fresh/r2 and keep/r2 producer facades and keep/r2 grading adapter remain
byte-identical to base. The shared Task4 fresh/r1 facade changed for the approved
closed task discriminator; its exact current hash migration is listed below.
No historical pin or receipt was migrated. Grader configuration, core grader
source modules, rubric, prompt, model and dependency manifests are unchanged.
Current-source approval does not authorize live Task5.

Paid behavior from the six-file one-use grading implementation is unchanged: its
`retention/keep-r2` adapter/context/command, emitted
`batch-runner/experiments/retention/keep-r2.yaml`, typed ledger/run-ID and
same-run approval/plan/protected/live/reconciliation gates are unchanged.
The former unpublished `retention/task4-keep-r2` remains refused, not an alias.
One immutable result permits one judge; an uncertain acknowledgment permits
same-job read-only reconciliation, not another judge/upload or a success-shaped
writer receipt. `default_v2_sol_max.yaml`, original rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, the 240-minute judge,
242-minute owned-child and 300-minute job limits remain unchanged.

Only these four source roles changed in the prior readout implementation from
base `b99a28a4c0ec0ed961a2a8ddcaa886462beb0691` to tested
`8a0b1c368d1e02bf21453bf75e1399f01d0a771f`; historical writer, receipt and
evidence hashes were not rewritten. These prior changes remain separate from
the Task5 current-source changes listed next.

| Prior readout source role | Base SHA256 | Tested SHA256 |
| --- | --- | --- |
| `codex_retention_grade_readout.py`: closed second binding/shared read transport | `ab5d5e09dc243dfce83972eb8c860ab0f9c0b653db2fa966472a5cd24d285860` | `c2fd083fbb4a90115fee1b20c4eed1ab687639d1efa8f80c169cb01f2dc06c9e` |
| `codex_budget_pilot_grade_readout.py`: exact second ledger type in recorded projection | `c8d8c67e6c904adfbd149103291a79185e13f530fcc1db3cda4d04eb6d139eb7` | `96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815` |
| `codex_budget_pilot_grading.py`: exact readout dispatch only | `742ac614034e5f987736ff312178740e7d00d24335db6f5eb78128b16ded3611` | `7ae99e053d11f9a21d6b4db27f390366e70df278a414b0f78db0fe82344bf989` |
| `.github/workflows/grade-run.yml`: read route/plan exclusion only | `a59762078a6dc81a9867490338873a2f6db2ebb8f456f37759874b40710b6824` | `1653a0729542a2977daf384b7f04f2a8748e08104ee12f2759affe4ee8b83a1b` |

At initial implementation HEAD `2068c92d4841e5f7be7aa9e9fc027c9dcc0205d5`, only these
production modules and inference workflow changed from base
`07e330fd936860aa592bfc5751736e0e8a9c2ad9`. Tests change only for the new
ordinal/source separation and their directly coupled current/default contracts.
Formerly unsupported ordinal-4 cases now use still-unimplemented cells;
old schema, hash and no-replay refusals are not weakened. Every production and
pin value in this initial table was unchanged at test-only correction HEAD
`e29f26b8e3ae91907fb7ba759da0feeee20d7046` and diagnostic HEAD
`77118007ffe9d676e740e98d36bb8e6847fc3a8d`.

| Initial Task5 role | Base SHA256 | Initial 2068c92d SHA256 |
| --- | --- | --- |
| `codex_retention_first_cell.py`: fifth closed binding/dispatch/admission pair | `957934b869ed5071923add7e9554aa68de941c9488f3e6d650557d27f6179601` | `ae5754bdd294a7560aecbe0d4c819bc6fdd123cf82fc652c6aedee5bae2701f7` |
| `codex_retention_fresh_r1_result_intake.py`: current controller pin only | `5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583` | `d6ef09d39dd4da91e96dedf861c5a26e29c6eae504d312ab496e3489f01e12cf` |
| `codex_retention_fixed_grade.py`: shared safe-checkout extraction, unchanged paid historical-byte loop | `7790852b04f8496db8b13ac6957badf641175c501f422720a7d14896b340d5ac` | `3d771582eaaf0d4cfab8e8858db1c7e557473459c2dd5769a837f059f516a684` |
| `codex_retention_grade_readout.py`: closed current observer dependency set | `c2fd083fbb4a90115fee1b20c4eed1ab687639d1efa8f80c169cb01f2dc06c9e` | `65e61d7a7fea824b7a92345796c9b142b4d8690affd0482b27ebaf221fb6aa7b` |
| `codex_retention_task5_fresh_r1.py`: exact fifth-cell adapter | New file | `9919fda7728e84d0d707fe6a4b23a8a601c04b1e5241bcc83387b9acd20f0f5a` |
| `.github/workflows/codex-retention-first-cell.yml`: fifth execution route and current reader/controller pins | `d4215b6a364d88d37041d96947ddc76f6df05658fe52be795514a39d6f842828` | `14d576779a85b72acaf7c6e483ae278fe8cd06748ec593dff5d0278018cf2a58` |

The 2303 correction changes only the shared task discriminator, its focused
test and these directly coupled current pins at
`4a2be68c96ef3f3e0961eb65fe15270a81baac6b`. The Task5 adapter, controller,
source-check helper, canonical path validator, paid routes and all other
runtime/config/dependency bytes remain unchanged from the initial implementation.

| Role at the producer's passing HEAD | Before the binding correction | SHA256 at `4a2be68` |
| --- | --- | --- |
| `codex_retention_task4_fresh_r1.py`: closed task discriminator in the shared publication verifier | `a0710039c33c17af85f226269ceeaccdb1c17bbc7238a46a15614226afed26e3` | `11901d7398066d0ccf2692c3f1b41fe4a066d872efecfa411756d67858f941e1` |
| `codex_retention_fresh_r1_result_intake.py`: current shared-helper byte pin | `d6ef09d39dd4da91e96dedf861c5a26e29c6eae504d312ab496e3489f01e12cf` | `d042c02228f2430d4129ed37b3fb453cf9792bbde269a28bd10c6daf8f00b900` |
| `codex_retention_grade_readout.py`: current helper/reader dependencies only | `65e61d7a7fea824b7a92345796c9b142b4d8690affd0482b27ebaf221fb6aa7b` | `adb13ac96702f0d38c49f2977e36607a4b8357f1ac9779de95aa18d0174f9587` |
| `.github/workflows/codex-retention-first-cell.yml`: current reader/helper preflight and CLI pins only | `14d576779a85b72acaf7c6e483ae278fe8cd06748ec593dff5d0278018cf2a58` | `d2f800c9c512bdea0c81096f9309d6979c820f9eac9284a2344755a3adf059a1` |

The consumed grading adapter's historical `READER` still contains the old
`957934b869ed5071923add7e9554aa68de941c9488f3e6d650557d27f6179601` controller
and `5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583` reader,
plus the historical `a0710039c33c17af85f226269ceeaccdb1c17bbc7238a46a15614226afed26e3`
fresh/r1 facade pin. These are not current executable hashes.
Both fixed evidence digests and every historical result/parent/receipt identity
remain unchanged. The source-separation selector passed those exact assertions;
the producer's static digest check confirmed their preservation without adopting current
hashes as historical evidence. `grade-run.yml` remains
`1653a0729542a2977daf384b7f04f2a8748e08104ee12f2759affe4ee8b83a1b`.

### Review provenance and remaining gate

The worktree is
`/ai-work/copilot/worktrees/codex-retention-task5-keep-r2-reader-20261003-0922`,
on branch `codex-retention-task5-keep-r2-reader-20261003-0922`, with implementation
pinned and tested at `2f58256bc6aabc345f46c37e8418b1f5f7a188d6` from base
`bdb7c21111a4c86136b6158f4969a39a9950acb3`. All producer checkouts, earlier
worktrees and `wip/local-main-preserved-20260719` are preserved. Existing identity
`hyeonsangjeon <wingnut0310@gmail.com>` is unchanged. These completion records
accompany the tested reader implementation for publication and final review.
Only these two records changed after validation; executable, workflow, test
and pin bytes remain at the tested HEAD.

The original two stream failures are preserved in
`/tmp/task5-keep-r2-reader-blocker-20261003-0922.iOfBT8/memo-failure-record.txt`,
SHA256 `5f78b7d705e339ed48fa6f643e657e5060e6304a957a5222cd1b3d6321b59456`.
The existing worker and one fresh read-only task both returned no decision.

In the 2026-10-03 09:53 KST continuation, the leader supplied the direct rejection
`Model 'Claude Opus 4.7 (1M context) (strategy mode) (Preview) (copilot)' is not available.`
That establishes the obsolete agent-model override, not the internal cause of
either earlier stream error. Only that `model:` front-matter line was deleted;
name, tools, description, read-only rules, threat-model checklist, conditions
and the mandatory gate are unchanged. No global/user settings, permissions,
provider or account were changed.

The one post-correction `collaboration.spawn_agent` request was
`/root/extreme_reasoner_keep_r2_current_route`, using session defaults without
an explicit model override. It was instructed to use the corrected registered
extreme-reasoner role for only the fixed reader/current-pin/read-mode decision.
It failed with `stream disconnected before completion: response.failed event received`.
No backend model/provider identity, decision memo or source finding returned;
the effective backend route is not independently established. This new stream
failure does not establish a model-unavailability cause. No second corrected-route
invocation was made. At that blocked boundary, only the agent-line deletion and
two records differed from base, documentation/equality checks passed, and no
workflow implementation, test, commit, push or reader PR had occurred. The saved
record is
`/tmp/task5-keep-r2-reader-memo-route-20261003-0953.x7yv4y/memo-route-failure-record.txt`,
SHA256 `5e5e1e2d35dc797b08d6bd2d0445e887d2abfb23205af7cb2065aaf59962f66d`.

The leader's subsequent direct `APPROVE-WITH-CONDITIONS` decision on
2026-10-03 at 10:24 KST supplied the actual pre-edit architecture decision for
this bounded scope. It explicitly substituted the separate leader/AI systems
architect's checklist review against `bdb7c21111a4c86136b6158f4969a39a9950acb3`
for unavailable memo transport. It was not a returned subagent verdict and did
not remove any standing agent instruction or final gate. Its saved provenance
and condition record is
`/tmp/task5-keep-r2-reader-proof-20261003-1024.z5MOYT/direct-memo.txt`, SHA256
`d54dcbc8ece6e91e43e9e8e84e6be5c2bc3f023a55d76445380d20b921001833`.
No additional memo request occurred. The implementation and single 17.12s
offline proof followed that decision, not the three failed streams.

The direct decision is scope approval, not approval of the final reader source.
Independent immutable-reader-HEAD review, all applicable same-HEAD CI, source
delivery and a separate outcome-matched live-read order are still required.
The producer remains leader-owned; its result identities and outcome are
unobserved here. No live HF/Actions/Azure outcome query, producer interference,
experiment model/grade call, dispatch, replay, duplicate approval, budget reset,
Project edit, merge or CI polling occurred.

The full skill catalog was checked once for this continuation. No experiment
design or configuration change is authorized, so `experiment-design` was not
invoked in this reader phase; the accepted registered constraints remain fixed.
No UI/animation skill applies. Relevant backend/grading rules were inspected
without changing their runtime. `experiment-report-en` then protected
`im-not-ai-en` was applied only to these changed records. The memo transport
failures remain distinct from tests and from the leader's pending execution
evidence; historical outcomes, partial costs, missing-price limits and
source-versus-input distinctions remain.

## PROJECT5-KEEP-R2-READER-RUNNER-FIX-20261002-1113

The fixed keep/r2 reader extension passed the leader-authorized replacement
invocation at unchanged implementation HEAD
`bd4452d3fd4b77d9f7c86e0fc709179927eaef3f`: 2 collected, 2 passed in 19.11s,
exit 0, with no outer timeout. The intended existing CPython 3.10.12 runner
passed its interpreter/pytest import prerequisite; no dependency installation
or source, workflow, test, manifest or pin change was needed. The earlier
`No module named pytest` failure remains separately recorded below with its
original log. It was a pre-collection runner failure, not a code verdict.
These records accompany the unchanged implementation for the leader's final
immutable-head diff/proof review and applicable CI. No live reader ran.

This resumes the 1011 task in the same worktree from verified base
`b8351e561acb9675a4993419e819c12787b5b305`. The leader's dated 1042
APPROVE-WITH-CONDITIONS decision authorized the bounded pre-edit scope after
reading the source and decision charter. The prior reviewer calls failed with
HTTP 400, a disconnected stream, then HTTP 400 from a fresh same-session
reviewer. Those failures produced no approval and were not retried; no account
or provider was switched. At that earlier blocker there had been no
implementation or test invocation. The leader's decision resolved that
pre-edit blocker, but does not approve the actual new diff, waive CI or
authorize a live operation.

The implementation adds one identity-equal `KEEP_R2` profile to the existing
shared reader for
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2`, ordinal 3 /
repetition 2, campaign `retention_bundle_diagnostic_20260929`. It binds KEEP,
the independent producer/run/request/job/input/grader identities below, and
the frozen keep/r2 producer's fresh/r2 predecessor. Both success and terminal
modes require the exact integer execution job and project it in their evidence.
Only this profile joins the existing contents-read result/terminal routes.
Default `FRESH_R1`, explicit `FRESH_R2`, both predecessor bindings, the original
keep/r1 route and default preparation/execution routing are preserved in source.
Locator remains keep/r1-only. No job, input, credential, permission, experiment
condition or execution authority was added. The replacement proof below uses
real validators and synthetic records; it does not validate live publications.

Prior PR718 HEAD `305c3539f93854248d41558a98e8d3d8cba8e72e`, owner review
[5387019458](https://github.com/hyeonsangjeon/gdpval-realworks/pull/718#pullrequestreview-5387019458)
and all 10 checks passed the producer source gate. Its
[immutable completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/305c3539f93854248d41558a98e8d3d8cba8e72e/tasks/LATEST_TASK_RESULT/README.md)
preserves the separate 61.31s proof and full implementation scope. Those reviews
and tests were not repeated and do not approve this reader extension.

### Preserved pre-collection runner failure

Pinned implementation/attempted validation HEAD:
`bd4452d3fd4b77d9f7c86e0fc709179927eaef3f`. That attempt used
`/ai-work/copilot/.codex-dependency-install-20260923.JN278b/validation-env/bin/python`;
its `pyvenv.cfg` records Python 3.10.12. The command used `env -i`, offline and
implicit-token-disabled settings, no credential variables, plugin autoload
disabled, `timeout --signal=KILL 180s`, and
`python -m pytest -vv -s --tb=short -p no:cacheprovider` without `-x`.

| Exact selector | Result |
| --- | --- |
| `tests/test_codex_retention_keep_r2_read.py::test_keep_r2_reads_only_its_fixed_result_or_terminal` | Not collected / not executed |
| `tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free` | Not collected / not executed |

Python module lookup failed with `No module named pytest`; runner exit was 1.
The outer timeout did not fire. There is no pytest duration or test result
count. Log SHA256:
`c0e5bafd4836ede09b9b58927734f402e2f170996d60c387df7ecc9519d2735c`.
The saved one-shot runner has SHA256
`a24088e1e954e86ca4d3f48b1b15d07ee63e8553ad1c62a255ca2763cf3d34f4`.
Pytest collection, offline fixture guards, reader binding checks, successful
payload intake, unsuccessful control-only observation, historical compatibility
and routing assertions were all not reached. No private input, network/model,
grade or remote-write operation ran. This is a runner setup failure, not an
observed reader-validator failure or model outcome. No repair or rerun occurred
under that earlier order. The 1113 order subsequently authorized the separate
runner-only replacement below, without changing the pinned implementation.

### Authorized replacement proof at the same implementation HEAD

One prerequisite check used the exact intended executable
`/ai-work/venvs/gdpval-realworks-py310/bin/python` under the same token-free
environment as the replacement test. It printed that `sys.executable`,
`sys.version=3.10.12 (main, Jun 22 2026, 18:55:27) [GCC 11.4.0]` and
`pytest.__version__=9.1.1`, and exited 0. No packages or interpreter were
changed. The prerequisite log has SHA256
`5f1ef71b3a20194547eb67a95ef44e8a440bd619cf6be992e3b599c9469f60cb`.

The single replacement invocation ran from `batch-runner` at tested HEAD
`bd4452d3fd4b77d9f7c86e0fc709179927eaef3f`, using that absolute interpreter,
`env -i`, offline/implicit-token-disabled settings, no credential variables,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `timeout --signal=KILL 180s` and
`-m pytest -vv -s --tb=short -p no:cacheprovider`, without `-x`.
Production/workflow/test bytes matched the pinned HEAD before the call; the
current reader and all six frozen file hashes also matched their exact pins.

| Exact replacement selector | Result |
| --- | --- |
| `tests/test_codex_retention_keep_r2_read.py::test_keep_r2_reads_only_its_fixed_result_or_terminal` | PASS |
| `tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free` | PASS |

Pytest collected 2 cases and reported 2 passed in 19.11s; runner exit was 0.
The 180-second outer timeout did not fire. This is offline test duration/count
evidence, not model usage or an experiment outcome. The saved replacement log
is `/tmp/project5-keep-r2-reader-replacement.rXVNdW/pytest.log`, SHA256
`a3df4696dbaacc611ceb4fdadcff015f868ee392c1a0b67a107a22b5f522dc17`.
The replacement runner script has SHA256
`c637f892ac2d1099feb7ff7ba46ae1ec2428a9498dfef4b36f0a4efba21f51f9`.
The original failure log remains unchanged at its separate path and hash.

The reader selector reached successful declared-payload validation and
failed/stopped control-only observation with real validators and synthetic
transport. Its safe marker confirms `exact_job_both_modes=true`,
`old_bindings_preserved=true` and `private_no_clobber_readback=true`.
Identity/treatment/hash/history/type/role/privacy/bounds, missing-control and
no-clobber refusal assertions completed; terminal mode read no payload bodies.
The coupled selector parsed the current YAML, exercised 192 cell/mode cases
and confirmed `three_jobs=true`, `old_routes_preserved=true`,
`keep_r2_reads_added=true` and `current_pins_before_credentials=true`.
Both markers report `live_effects=0`. Offline process/network guards were
active; no private integration, full suite, delivered suite, live read, remote
write, model or grade ran. This authorized replacement was not followed by
another test invocation. Synthetic success is not live successful-result intake.

### Actual keep/r2 preparation, approval and succeeded receipt

The leader supplied workflow `370228282`, run `36947454688` / attempt 1 at
producer `b8351e561acb9675a4993419e819c12787b5b305`. Preparation job
`110652687444` succeeded; its receipt at `2026-10-02T00:47:12.1461147Z` is
`prepared_not_admitted`, request SHA256
`8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1`.
The path-specific materialized grader is
`997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1`;
four original roles were verified from bundle
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
The receipt reports KEEP/B/no C, 10800 cumulative seconds, 1800 native-turn
wait, one slot, no reset, no fixed admission count and no automatic money cap.
These are prepared settings, not observed model behavior or success.

The leader posted and read back one exact owner approval in `grading`
`18744914306`, deployment `6798561339`; approval job `110653531434`.
The one authorized jobs-metadata projection independently returned
`retention-execute` job `110660390316`, run `36947454688`, attempt 1 and exact
source `b8351e561acb9675a4993419e819c12787b5b305`; the response listed 3 jobs.
That one-time metadata read was not repeated. It did not read logs or the
outcome, and no live reader or status polling occurred in this coding task.

The leader subsequently supplied the final safe CLI receipt from execution
job `110660390316` at `2026-10-02T01:38:40.0275325Z`, with the exact cell and
request above: `status=succeeded`, `cleanup_confirmed=true`,
`remote_terminal=acknowledged`, `grade=null`, `grading_launched=false`,
`invoice_complete=false`. All workflow jobs are green, but the reported task
success comes from this explicit receipt, not job status or approval alone.
The inference is completed and consumed and must not be replayed.

Terminal/claim/output revisions, deliverable contents and counts, usage and
costs have not yet been read. Keep/r2 remains ungraded; none of those unknown
values is borrowed from keep/r1 or either fresh cell. This producer receipt is
not a verified successful-result intake, independent provider authentication,
an invoice or a causal retention result. The replacement's synthetic proof
does not verify this consumed inference's unread payloads or accounting.

### Actual failed fresh/r2 control observation

The leader directly read
[observation run 36936506988 / job 110617920889](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36936506988/job/110617920889)
at historical observer `0f68701d62ae7d86a95ba8fd6b9f1cc65a4cf2d6`. The receipt at
`2026-10-01T22:43:16.1975611Z` is `terminal_verified`, observation SHA256
`50f13364c7a261010f210959d425420509bf879040257daeec9b16fea025e9d3`, with historical
reader SHA256 `5bfba1a2cb4d4f5190b0d146fd7b2b890c72ecf3904974d37babfea9ed8661f0`.
Approval/execution jobs were skipped. No payload bodies were read. This coding
task did not query or repeat the observation.

The consumed fresh/r2 inference is `status=failed`, exit 1,
`cleanup_confirmed=true`, `recorded_publication_acknowledged=true`, `grade=null`,
`grading_launched=false` and `invoice_complete=false`. Its cell is
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r2`, producer
`5a9614ac04464c4e0a5e80297f54c3a5c9443bae`, run `36907894862` / attempt 1 /
execution job `110535767415`, request SHA256
`4798c119ea2d06c7c902ae51638bdba25c5bfaf683a2223d286fd7e652d3b317`.

| Verified control identity | Recorded value |
| --- | --- |
| Terminal | `1d5133590911f3704fc2a65279d4b64bee77c1d6`; SHA256 `c1ab656b3ee0556aa5934dc976dfa6086ac59f4f3e2abf936a600a9fcb7fda2b`; 4200 bytes |
| Claim | `98724c1fc83af2b45f65533648162692ba8d12b0`; SHA256 `d2718f7635870efbb3edefaf7d38ed20691fed40c1c39389b93e53947a6ceeb4`; 1889 bytes |
| Output | `46fff9e31bc844a55ced352926aba49479869624`; manifest SHA256 `f44c09d86d48d59579ff6ae3355633740b5d2888c7b38e33cd6c132bb45cf882`; 2119 bytes |
| Output object set | `output_objects_sha256=029c0b29cd7e3b593fb28ec0dfe4a6c3d6999b8867f980496cde1da335d18c3a` |

Declared roles are inference result 1, ledger 1 and deliverables 0, with 3 total
objects including the manifest. These are control/metadata declarations, not
proof of absent partial work or verified grading input. The proof is
`verified_publication_derived_not_independent_provider_authentication`, not
independent original-input or CAS authentication. Recorded publication
acknowledgment does not establish writer acknowledgment by the observer.
Grade null is not zero, and workflow success is not task success.

R2 records 39 model calls: infrastructure-retry 38 / known USD `0.253777`,
generation 1 / known USD `0.045663`; aggregate known/model USD `0.29944`, partial.
Recorded usage is input 105233, cached input 27648, output 6571 and reasoning
3979. Cached/reasoning values are subsets, not extra totals. Calls are not HTTP
requests or native admissions/resumes; partial known cost is not an invoice.
Estimated/runtime cost and HTTP request count remain null, with missing reasons
`call_reachability_unknown` and `usage_absent`. These are not r1's costs below.
`detailed_failure`, `budget` and `recovery_exposure` remain unavailable/null with
reason `not_recorded_in_terminal_controls`. Duration and retry labels do not
establish timeout or rate-limit causality or justify another read/repeat.

### Historical producer proof, not reader validation

The prior producer task tested `bf0bcfdb9e4364d8d8bd7ec72dac4b481556d8a3`:
2 collected, 2 passed in 61.31s, exit 0; the 180-second timeout did not fire.
Its single invocation used CPython 3.10.12 / pytest 9.1.1, `env -i` with token-free
CI-shaped ambient metadata, existing network/process/credential guards and no
`-x`. Its runner was `python -m pytest -vv -s --tb=short -p no:cacheprovider`,
with plugin autoload disabled and `timeout --signal=KILL 180s`.

| Selector, relative to `batch-runner` | Result |
| --- | --- |
| `tests/test_codex_retention_task4_keep_r2.py::test_task4_keep_r2_advances_failed_fresh_r2_without_cross_cell_state` | PASS |
| `tests/test_codex_retention_ci_observation.py::test_retention_keep_r2_routes_preserve_read_and_authority_boundaries` | PASS |

Both completed in the historical aggregate 61.31s above. Log SHA256:
`6a6f2559224e89acb9cd9e64e6e008aac00ca423362cf75c2c7e71b675d1d628`.
Real validators and synthetic transport/owned child reached packet/staging,
canonical request, approval, failed-predecessor claim, child, output, terminal
and immutable reconciliation. The proof covered 21 predecessor cases, wrong
source/run/request/cell/job/cleanup/history, branch drift, duplicate/no-replay,
guard ordering, cleanup, timeout and ambiguous publication. KEEP recovery
retained this cell's thread/directories/output across synthetic wait and
downtime with the original expiry and no C feedback; cross-cell substitution
refused. Old cell schemas and both reader bindings passed small compatibility
checks with the new current pins. Wrong hashes refused before credentials or
effects; predecessor verification made no payload-body downloads.

The coupled selector evaluated current YAML across 192 cell/mode cases and
checked the shared execution assertions, unchanged read allowlists and exact
precredential hashes. Synthetic fixture identities were derived from authored
bytes, not returned controls or canned validator success. This does not verify
the actual live predecessor or current remote parent. No live execution, model,
remote write or grade occurred. No delivered reader suite, private integration,
full suite or second invocation ran.

For that producer task, the bounded auth/runtime/storage/workflow reviewer
approved the scope and 11-file delta, then closed the review with APPROVE after
reading the proof. This remains a historical producer review. The leader's
1042 decision is the separate current pre-edit authority; independent review
of the actual new diff and the saved replacement proof remains pending.
The current reader's offline pass grants no live-read authority.

### Current reader migration and frozen historical bindings

This implementation changes only the CURRENT shared reader hash, from
`cd88a768e573d57c82d8f14bcb266ae455187933fb8a5b70da0fadafe17bea46` to
`5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583`, in both
read preflights and CLI expectations. The keep/r2 route checks its unchanged
facade and fresh/r2 dependency before lazy import and before the step-scoped
HF credential. The replacement proof exercised exact current-pin refusals
before credentials/effects. Historical producer/observer/reader/receipt
identities remain immutable.

The following migration belongs only to the prior producer task and explains
the current frozen controller and this task's starting reader bytes:

| Current-byte role | Before SHA256 | After SHA256 |
| --- | --- | --- |
| Shared controller | `a7c44ce7224b02f31865620e482d0ff6964f36d2b4c4753658e3ecfc72dcbc58` | `957934b869ed5071923add7e9554aa68de941c9488f3e6d650557d27f6179601` |
| Shared fresh reader | `5bfba1a2cb4d4f5190b0d146fd7b2b890c72ecf3904974d37babfea9ed8661f0` | `cd88a768e573d57c82d8f14bcb266ae455187933fb8a5b70da0fadafe17bea46` |

In that prior task, only the reader's current controller pin changed. This
reader extension does not alter that controller or its exact current pin.
The unchanged keep/r2 facade
has SHA256 `12106b5423e25ffefa1b04023e2e98742861762762966a04bf17fe3da1851450`.
R2 already explicitly refuses keep/r2 before source/private-input reads; its
producer bytes and exact pre-import/credential pin did not need a migration.

| Unchanged current-byte role | SHA256 |
| --- | --- |
| Fresh/r1 facade and shared publication helper | `a0710039c33c17af85f226269ceeaccdb1c17bbc7238a46a15614226afed26e3` |
| Fresh/r2 producer | `8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f` |
| CI verifier | `8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c` |
| Original keep/r1 intake | `df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196` |

Core/runtime/model/input/grader/registration bytes remain unchanged. Historical
observer source 910, reader `bbb46c87ac840317a4f41959d2278677ed29e52e7ae28f49cf47db7a464eaafa`
and observation `36df4b36135d0c45db53a23c4f88fde360695f80bad0437735436516ebb626ea`
remain immutable; current helper checks do not replace old evidence.

Prior PR717 HEAD `60f2a334bd76de197cdac668a635ffe1c2e427af`, owner review
[5384875894](https://github.com/hyeonsangjeon/gdpval-realworks/pull/717#pullrequestreview-5384875894)
and all 10 checks passed their source gate. Its
[immutable completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/60f2a334bd76de197cdac668a635ffe1c2e427af/tasks/LATEST_TASK_RESULT/README.md)
preserves the separate tested `d92cac628490baf40ceb8c0a76e38fb6cfd6e985`
2-pass/14.64s reader proof, r2 preparation/approval and one jobs-metadata binding,
plus the PR716 compatibility decision and 49.90s/2.61s proofs. None was repeated
or relabeled as current reader validation.

### Preserved fresh/r1 terminal-only observation and consumed inference

The leader directly read
[observation run 36884357472 / job 110443771878](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36884357472/job/110443771878)
at source `910cbdbc49da764a76932bab3af4af231a0b6771`. Its receipt at
`2026-10-01T15:29:46.3223244Z` reports `terminal_verified`, observation SHA256
`36df4b36135d0c45db53a23c4f88fde360695f80bad0437735436516ebb626ea`.
Its historical reader SHA256 remains
`bbb46c87ac840317a4f41959d2278677ed29e52e7ae28f49cf47db7a464eaafa`.
Approval/execution jobs were skipped. This coding task did not repeat that read.

Fresh/r1 is consumed with recorded `status=failed`, exit code 1,
`cleanup_confirmed=true`, `recorded_publication_acknowledged=true` and
`grade=null`. The fixed producer is `e39d8d1aadcb816d09588829a5ec4929b33083e6`,
run `36845127347` / attempt 1 / execution job `110323708382`, request SHA256
`5bbb0e4cb5ae9444eac9c804ac3c8d2f6d39acbec63e7f7de78d7f2ee35fcf02`.

| Verified control identity | Recorded value |
| --- | --- |
| Terminal | `45f54eb0a24aee5d40dd41b276ff5df777f06d73`; SHA256 `2fa29205d842956fcbd857e4b1e1878af4551ebddc7573e480d7e17d01b63faa`; 4206 bytes |
| Claim | `4bff20bdae3cddb28519eadec9f032af5b6843d5`; SHA256 `0ed2ab8979fd918218415ee08eee5ad99d9d3a9e08b41695f0b30e2afd0cc1c4`; 1484 bytes |
| Output | `3b27e0a7e9d05c9ecfb400040bd8c025bc7f2484`; manifest SHA256 `f48abaab90af661811b257d709a0934819ef057854976694a543e4ed76cd3380`; 2125 bytes |
| Output object set | `output_objects_sha256=1ac663171c092a21edd0287e2749daab3e216dcbee1efa14b5ea70eab4853c1a` |

Declared payload roles are inference result 1, ledger 1 and deliverables 0;
3 output objects include the manifest. These are verified declarations and
metadata, not payload-body verification or proof that all work/files are absent.
The publication-derived observation is not independent provider authentication,
original-input revalidation or Git-parent/CAS ancestry verification. Recorded
publication acknowledgment does not make the observer the writer;
`writer_acknowledgment=not_established`, `payload_bodies_verified=false` and
`grading_input_ready=false` remain explicit. Grade null is not zero.

The recorded receipt has 39 model calls: an infrastructure-retry component of
38 and a generation component of 1. Known/model cost is USD `0.303358`, partial;
`estimated_cost_usd`, `runtime_cost_usd` and HTTP request count are null, with
missing reasons `call_reachability_unknown` and `usage_absent`, and
`invoice_complete=false`. Recorded usage is input 104289, cached input 22144,
output 6164 and reasoning 3863. Cached input and reasoning are subsets, not
additional token totals. Calls are not HTTP requests or native admission/resume
counts, and partial known cost is not a total or invoice.

`detailed_failure`, `budget` and `recovery_exposure` remain unavailable/null with
reason `not_recorded_in_terminal_controls`. Neither the roughly 180-minute step
nor retry labels establish timeout, rate limiting or another cause. These
unknowns do not justify a repeat, another observer or expanded data access.

The earlier final CLI receipt remains distinct from this later control read.

The leader directly read
[run 36845127347 / attempt 1 / execution job 110323708382](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36845127347/job/110323708382)
at producer `e39d8d1aadcb816d09588829a5ec4929b33083e6`, workflow `370228282`,
`.github/workflows/codex-retention-first-cell.yml`. All workflow jobs completed
successfully. The actual final CLI receipt at `2026-10-01T13:22:50.8088344Z`
reported the exact fresh cell, `status=failed`, `remote_terminal=acknowledged`,
`cleanup_confirmed=true`, `grade=null`, `grading_launched=false` and
`invoice_complete=false`, with request SHA256
`5bbb0e4cb5ae9444eac9c804ac3c8d2f6d39acbec63e7f7de78d7f2ee35fcf02`.
Its green workflow status is not task success. The later observation above
supplies control identities and recorded accounting, not a failure explanation.

Execution-side preparation reproduced that request digest and fresh materialized
grader source `298da1d3a36482cf87e7f896d47c8c6c64bf5e1df91dd244847640d9d00a3689`;
signed approval verification succeeded. This is not the consumed keep/r1 grader
identity `c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320`.
Earlier preparation job `110313331439` reported `prepared_not_admitted` at
`2026-10-01T09:51:41.9510199Z`, verifying four original input roles from bundle
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Exactly one owner approval was confirmed in environment `grading`
`18744914306`, deployment `6781320183`, using
`approve-retention-first-cell sha256:`; approval job `110314366065` was queued
afterward. Those preparation/approval facts remain distinct from the later
failed receipt. This coding task did not follow, poll or read that run.

### Actual verified keep/r1 readout, separate from offline proof

The leader directly read
[run 36820845596 / attempt 1 / pilot-readout job 110235885096](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36820845596/job/110235885096)
at source `f30c9efa392bc14cba790fb5d1dedf12071a5677`. Its receipt at
`2026-10-01T05:43:22.3151574Z` reported `verified_writer_recorded_grade`, stage
`verified`. All paid/writer/generic jobs were skipped. That read did not call a
model or regrade; this coding task did not retrieve raw private grade content.

The consumed grade writer is `29e0353f1539265b1741e71be894fedf9be32a8b`,
run `36776393736` / `pilot-live` / attempt 1. Grade terminal
`40712e0980cc05c31688fdbb98c693774fb90c0d` has SHA256
`11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234`,
3119 bytes, and claim `dec305d669e3ca2e53c7f7b9ebfbe7974d661350`.

For keep/r1 cell
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1`:

| Recorded projection | Value and limit |
| --- | --- |
| Score | 30.6 / included possible 45 = 68.0%; full-denominator percentage 54.64% |
| Exclusions | 9 items, maximum score 11.0; the 13.36 percentage-point difference is a denominator effect, not treatment uplift |
| Task outcome | One scored task, no recorded task error; payload `run_status=diagnostic` |
| Coverage | `judge_items=49`, `rubric_items=40`, `passed_items=25`, `rubric_item_coverage=0.625`; recorded projection, not independent rubric revalidation or a validated quality explanation |
| Grader ledger | Present; 93 recorded model calls, `input_tokens=270190`, `cached_input_tokens=212025`, `output_tokens=16031`, `reasoning_tokens=10481` |
| Grader cost | Partial, `missing_reasons=[price_missing]`; known/model/estimated/runtime USD fields null, HTTP request count null, `invoice_complete=false` |

Cached input and reasoning tokens are subsets, not additions to their parent
token counts. Recorded model calls are not HTTP requests. No price or invoice
was reconstructed. Coverage and excluded items do not independently explain
the quality of this result.

The proof is
`verified_publication_derived_not_independent_provider_authentication`.
`materialized_input_fingerprint` remains `{status: unavailable, value: null,
comparison: null, reason: materialized_input_fingerprint_not_recorded}`.
The original result fingerprint, preparation digest and materialized grading
input remain distinct; this read does not fabricate an intermediate comparison.

### Fixed predecessor, study limits and remaining live gate

Keep/r2 requires the failed fresh/r2 terminal `1d5133590911f3704fc2a65279d4b64bee77c1d6`
and the independently fixed control identities above. The actual shared inference
branch must still equal that terminal before one-use CAS; drift refuses without
adoption or reset. Fresh/r2 retains its historical failed-fresh/r1 predecessor
`45f54eb0a24aee5d40dd41b276ff5df777f06d73`
and its fresh/r1 control identities in the preserved section. A completed failure
with confirmed cleanup can
precede the next predeclared cell; an incomplete or ambiguous claim cannot.
Neither the keep/r1 terminal nor its grade is the fresh/r2 predecessor.

The keep/r1 inference remains fresh/r1's historical predecessor, not its grade:
producer `e355faf9a6212175a288e8473968915ffb2408d0`, run `36696961231`, request
SHA256 `ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68`;
terminal `de50ff0aa6037c0ef6e3b713da519359abd1d08d`, SHA256
`0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8`,
6449 bytes; claim `3fc283087a020caec574e8c9b8e9bc3ca593e88a`; output
`43cbf8e265297813857172ecee51256cc17f2d36`. The delivered fresh/r1 reader checks
this exact recorded reference, never adopts it as the fresh result or replays it.

The registered order remains Task4 keep1/fresh1/fresh2/keep2, then Task5
fresh1/keep1/keep2/fresh2. Four of eight producer outcomes are now reported;
fresh/r1 and fresh/r2 are consumed with verified failed controls and unavailable
detailed causes. Keep/r2 is consumed with a leader-reported succeeded receipt,
but its publications and accounting remain unread and it is ungraded.
Four Task5 cells remain outstanding. The original
30-cell pilot is complete and is not reopened. This eight-cell study is
post-selected and not representative; one score is not evidence of benefit.
Two repetitions, service variation and an uncalibrated judge remain registered
limitations. The keep/fresh comparison changes the native-thread/owned-files
retention bundle under mechanical B, not the model, inputs, rubric, budget
policy or C feedback.
The decision rule still requires keep-only deliverable advantage in both pairs
within a predeclared task with no reverse pair. No recovery opportunity stays
in the denominator and is uninformative about retention.

GPT-5.4 direct-v1/xhigh, SDK/CLI 0.147.0 and original input/rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf` remain fixed. Mechanical B, no C,
the registered KEEP bundle for ordinal 3, temporary carveouts and one concurrent
inference are unchanged. By registration, this distinct cell's 10800-second
cumulative clock starts at its own admission and includes waits, recovery and downtime
without reset; it does not reset either consumed fresh cell's clock. The
1800-second native-turn wait is not an all-in attempt ceiling. There is no fixed
admission count or automatic monetary cutoff.

One task's repeats do not establish retention benefit or explain either fresh
failure. This reader task grants no launch or replay authority. The pre-edit
decision is resolved, and the 1113 runner-only replacement passed at the
unchanged tested HEAD after the preserved pre-collection failure. The actual
new diff and saved proof still need independent final source review and
applicable CI before the leader separately authorizes a successful-result
read bound to the reviewed reader source/hash and exact producer/run/attempt/
request/cell/job above. That later route requires `read_result=true`,
`observe_terminal=false`, `prepare=false`, `execute=false` and
`observe_locator=false`, with the exact keep/r2 cell. Keep/r2's unread terminal
is discovered once, with immutable revisions thereafter.
Missing, ambiguous or corrupt records must refuse without polling, fallback,
replay or budget reset. Terminal-only mode remains explicitly separate and
cannot turn the known succeeded receipt into failed/stopped evidence or a
successful payload intake. No live observer or grade ran.
The leader's local M4 files remain unavailable and were not updated.

### Preserved history and reporting scope

The [immutable prior observer record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ea8e7d36693678cedb54fbe277af5cc874360061/tasks/LATEST_TASK_RESULT/README.md)
retains the separate tested `386390b8db59df92f8b297d21d0b99a712887da9` proof:
2 collected, 2 passed in 14.86s, exit 0, no timeout, with both exact selectors
and all reached boundaries. Log SHA256:
`d9f7c3217cb1f1d843e47f6854e5fd2bd832eb0fd7568b6f5a98b0148318a128`.
Its observation marker, default-success isolation, frozen hashes and review
history remain intact. That synthetic proof is neither the actual later
terminal observation nor fresh/r2 validation.

The [immutable prior reader record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/710860be12f26bcf5b60312974c31aff7499eda4/tasks/LATEST_TASK_RESULT/README.md)
retains the separate `56bb86a7cdca02c7f0f9ef8055d3e44f8df8aaaf` proof:
2 collected, 2 passed in 11.06s, exit 0, no timeout; log SHA256
`eabc583e6f50aa61211cfc28aefc132c0326892b923eedcbe6989bb0f15c037e`.
Its successful-result intake, type-coercion review correction and prior source
review `5377303231` are not current keep/r2 reader validation.

The [immutable prior completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/e39d8d1aadcb816d09588829a5ec4929b33083e6/tasks/LATEST_TASK_RESULT/README.md)
retains the exact reached/unreached boundaries and logs for `c291670`'s 2.68s
source-pin failure, `53e5dc2`'s 5.71s missing-`run_id` fixture failure,
`5b788b7`'s separate 34.90s two-selector pass, PR713 CI run `36834022780` /
job `110276977686` (1 failed, 13303 passed, 64 skipped, 46 deselected in
1301.15s), and `a378df8`'s separate 2.08s entrypoint pass. They were not replayed
or relabeled as current reader proof.

Failed readouts `36801558936` and `36811186015`, earlier offline failures and
passes, successful producer `36696961231`, verified intake `36739260150`, the
consumed grade and the NAS prerequisite refusal remain distinct in that
record and its immutable history links. Original inference accounting remains
partial: 10 recorded model calls, known cost USD `0.409894`, runtime cost null,
missing `call_reachability_unknown`, not grader accounting or an invoice.
Its original `grade=null` / `grading_launched=false` receipt is
not rewritten by the later grade and numeric readout.

The full skill catalog was checked once for this phase. `experiment-design` preserved the
registered constraints without a new treatment, sample, repeat or budget.
`experiment-report-en`, then protected `im-not-ai-en`, applied only to the
bounded runner-failure/replacement-proof and remaining-gate update. Unchanged
score/accounting/limit paragraphs were not re-audited or rewritten. Literal checks and a local
reverse-condition check do not constitute independent review or implementation
validation. UI/animation, new-study and generic-framework skills were not
applicable. Only these completion records change after the tested HEAD; the
reader, workflow, tests and all pins remain identical to the replacement proof.

The old PR713/PR714/PR715/PR716/PR717/PR718 worktrees, other records, `wip/local-main-preserved-20260719` and
private NAS refusal directory remain untouched. The existing Git identity is
`hyeonsangjeon <wingnut0310@gmail.com>`, without attribution/session trailers.
The leader's local M4 checkout is unavailable and was not updated. No workflow
dispatch/polling, live HF/OIDC/Azure/model/grade/readout, inference replay,
permission change, Project edit or merge occurred. These records stop at
pre-merge facts.
