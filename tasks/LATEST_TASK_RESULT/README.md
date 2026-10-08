# Latest task result

## Preparation-only probe refused after originals; intake boundary isolated

The directed probe run `37818721507`/r4a1, job `113453943352`, completed with
failure. Public source/request checks passed. The model-free step ran
**2026-10-08 17:45:07..17:45:11 UTC**; completion validation/upload succeeded.
Artifact `11568232298` contains a **1486-byte** bound completion, SHA256
`753c468fef11533cd55accb0c089290b4362200e15d501347862d3304e8f35e2`.

The envelope reports `status=refused`: environment and originals completed;
`intake_preparation` started and returned `validation_refused`; context exit
is unknown and verified preparation is null. Source/run/request/R/F/result
bindings match the exact directed probe. Grading authority, handle reuse and
retry are false. This establishes a current intake/preparation refusal, not
which inner predicate failed or the discarded cause of historical run 3.
The preparation helper has identical Git blob
`24a430137fb47bced1e5a450b5b5568d477a5b2e` in original R and deployed C;
that particular source-drift hypothesis was ruled out without private reads.

Next isolate that existing boundary and preserve only closed safe internal
refusal codes. No new mode, workflow, private fetch, grading or replay is
authorized by this record.

### Original submission and accepted source

The leader submitted [run 37818721507][probe-run], workflow `378041151`,
run number **4**, attempt **1**, explicitly selecting `prepare-probe`.
Exact readback at **2026-10-08 17:43:07 UTC** was `queued`, with source
`ff3eecd1de1322898c18ae192021de16a9d06ee0`, tree
`30966a77bba3c4322b2b83faf3c0e93022be69c1`. This is the first directed
model-free preparation probe, not a fourth grading attempt.

The canonical **4194-byte** preparation-only request SHA256 is
`a0f0c5afb84529d00253c0474f2741b2c268b55f417c8b946a34426051e9fbbd`.
Its **2400-second** admission window is `1791481273..1791483673`.
Original R/result/F/input bindings are unchanged. The request has distinct
preparation-only format, purpose and policy, with no grading storage authority.

Authorize only originals acquisition, authenticated retained intake/F
preparation and handle closure under the existing **300s+5s** hosted bound.
No direction, claim, grading once-store, model/judge/executor, retention or
private-storage write is authorized. At that queued readback, readiness/refusal
had not been observed. The terminal refusal above supersedes that
submission-only status. Prior run 3 remains uncertain
and nonretryable; no grade or historical outcome is reclassified.

### Accepted source and validation

The leader accepted HEAD `3738b48bb57e324daf1f4e75ff846d8b1aa59fc0`,
tree `59b20c4444bd8ccb6984d3b93d6f84802d9febfe`, in review `5460622280`.
All **11** applicable checks in CI run `37812242630` succeeded, observed at
**2026-10-08 17:37:09 UTC**. No passing test was repeated by the leader.
This accepts the preparation-only source, not live readiness, a grade,
recovered historical evidence or permission to replay run 3.

Only the stale step-ceiling assertion in
`test_native_task3_grading_git_ownership` changed. Following the existing
hosted guard pattern, it checks grade **269 minutes** and prepare-probe
**19 minutes** separately, excluding the opposite branch. The **270-minute**
job cap, **1-minute** Git step, **30-second** local Git-call bound and every ownership,
source, unrelated-repository and reciprocal-registration assertion remain
unchanged. No production, workflow, permission, pin, schema or deadline changed.

The exact ownership node passed in one fresh invocation: **1 passed, 1 warning
in 2.60 seconds**, exit **0**. Pytest-process elapsed was **3.030908 seconds**;
wrapper elapsed, including source/collection checks, was **6.003377 seconds**.
No additional correction or retry was needed. No earlier passing node ran.

### Reported CI failure, separate from this proof

The leader read CI run `37804015222`, time-budget-contracts job
`113403603647`: **1 failed, 475 passed in 1718.79 seconds**. That is pytest
elapsed time, not job duration. The other **10 checks** succeeded. At line 34,
`tests/test_time_budget_native_grading_git_ownership.py::test_native_task3_grading_git_ownership`
still summed every workflow step and observed **276 versus 269**. The sum
included **7 preparation-only minutes** from a mutually exclusive branch;
it is not evidence of an increased grading timeout. The log was **122916 bytes /
1147 lines**, SHA256
`a20549e3f2420ea857f789fca25d5be2f9ffd42bf0f7558180fc2fe16d10ed3c`.
These are leader-supplied facts; no CI/log query, refetch, retry or polling
occurred in this task. The new local result does not establish that CI passes.

### One ownership-node invocation

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-probe-ceilings.YCXV7y/run-proof.py
```

The copied task-local wrapper verified the exact test-only byte replacement,
unchanged production/source identities, imports, fixture closure and exact
single-node collection before bodies. It used Python **3.10.12**, pytest
**9.1.1**, TERM**300s**/KILL**5s**, no `-x`, the existing Git bounds and immediate
phase/failure flushing. Wrapper UTC interval:
**2026-10-08 16:41:31.232708** through **16:41:37.236071**. Setup/body/teardown
passed; the JUnit case time is **0.793 seconds**, not the complete pytest or
wrapper duration. The **1 warning** is the retained `record_property`/`xunit2`
warning. The exact sole node is the CI-failed ownership node named above.

This proof used real Git and the actual extracted workflow/controller source
checks. `GIT_TEST_ASSUME_DIFFERENT_OWNER=1` simulated foreign ownership, and
three tiny fixture commits/trees replaced C/R/F anchors only inside the proof.
The original local Git call returned **128** with a dubious-ownership refusal;
exact scoped bootstrap trust then succeeded. Wrong physical path, C HEAD/tree,
R/F trees, occupied destination, unrelated repository and tampered reciprocal
registration were refused. Linked sources remained detached, and config/refs
were unchanged. This is synthetic ownership evidence, not a live UID or
container claim. No intake, F preparation, grader, model or private access ran.

### Scope and authority boundary

The workflow choice defaults to `grade`; the opt-in `prepare-probe` request
has a distinct format, purpose and preparation-only permission, without a
grading `storage` field. Grade and probe operations reject each other's
request. Both retain exact source/caller/Actions/cell/input/path/admission
checks. The probe uses the same authenticated originals and four-GET/60-second
retained intake, real F preparation, derived-input checks and final rereads.
It never constructs an execution direction. A readiness receipt or closed
handle cannot authorize another preparation or grading call.

Public completion fields are restricted to fixed source/request/result and
preparation identities, hashes/sizes, readiness/refusal and closed diagnostic
states/categories. `grading_authority=false`, `handle_reusable=false` and
`retry_allowed=false` are mandatory. No raw error, payload, private prose,
filename, path, URL or token is public. Local private staging and partial
inputs are preserved; there is no private-storage publication.

The hosted preparation command has TERM**300s**/KILL**5s**, with phase deadline
checks and a **6-minute** step. Existing originals/retained-intake transfer
and byte limits are unchanged. Preparation skips renderer/OIDC/login; its
intake step alone receives the existing HF secret after public source/request
checks. Mutually exclusive step ceilings total **19 minutes** for preparation
and **269 minutes** for grading within the unchanged **270-minute** job.
The grade request/schema, one-process context, permanent/local once guards,
retention and F/child **14400/14520-second** limits remain unchanged apart
from the explicit refusal of a probe request at the grading entry.

### Earlier three-node probe proof, not rerun

That separate invocation reported **3 passed, 3 warnings in 53.27 seconds**,
exit **0**, pytest-process **53.700716 seconds**, wrapper **59.201955 seconds**.
It ran only `derived_drift` and the two previously unstarted guard nodes; the
eight previously completed cases did not run.

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-probe-remaining.z0hJou/run-proof.py
```

In that earlier proof, the task-local wrapper was restricted to exactly these
nodes. Imports, fixture closure and exact collection passed before bodies
started. Python **3.10.12**, pytest **9.1.1**, no `-x`, the existing Git bounds
and task-local **30-second** Git cap were retained. There was one invocation,
no retry and no timeout increase. Its wrapper ran from
**2026-10-08 15:40:42.298266 UTC** through **15:41:41.500206 UTC**.

| Exact node | Result | JUnit case elapsed |
|---|---|---|
| `tests/test_time_budget_native_preparation_probe.py::test_native_task3_preparation_probe[derived_drift]` | Passed | 36.677s |
| `tests/test_time_budget_native_grading_ci.py::test_native_task3_grading_bootstrap_without_python` | Passed | 0.665s |
| `tests/test_time_budget_native_grading_ci.py::test_native_task3_hosted_grading_route[guards]` | Passed | 10.030s |

All three have passing setup/body/teardown reports and a final JUnit result.
The **3 warnings** report `record_property` incompatibility with the configured
`xunit2` family; they are retained in the log, not hidden or fixed in this task.
JUnit case times are not the full pytest-process or wrapper duration.

The derived-drift case exercised the actual controller CLI, native context
and F preparation. It recorded **4 original GETs**, **4 retained-intake GETs**,
**1 real F preparer call**, a refused result, closed handles and **0 trapped
direction/claim/executor/model/private-write calls**. Its **218405-byte** Step0,
source/Actions identities, HTTP/auth and kernel facts were synthetic. The
existing assertions also retain the no-retention boundary and secret-canary
exclusion. The two guard cases exercised extracted Bash/JSON and actual source
CLI refusals with synthetic identities, including the mutually exclusive
operation and step-ceiling assertions. They did not run setup-python on an
Actions host or establish live-container/private-input readiness.

### Original timeout remains separate

The original invocation reached the **300-second** outer bound, exit **124**,
wrapper **301.135259 seconds**. Eight cases completed setup/body/teardown;
`derived_drift` completed setup only and neither guard started. No final
pytest summary or JUnit was produced. That invocation remains incomplete.

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-preparation-probe.7JqRjH/run-proof.py
```

Source, imports, fixture dependencies and exact collection were checked before
bodies launched. Python **3.10.12**, pytest **9.1.1**, no `-x`, existing fixture
Git bounds and the task-local **30-second** Git cap were used. The wrapper ran
from **2026-10-08 15:02:34.389068 UTC** through **15:07:35.524309 UTC**,
including source/collection checks and termination handling. Final pytest
process elapsed/exit and warning count are unavailable, not zero. The retained
wrapper traceback is `SystemExit: 124`, not a pytest assertion traceback.

| Exact selected function | Recorded case outcomes |
|---|---|
| `tests/test_time_budget_native_preparation_probe.py::test_native_task3_preparation_probe` | `ready`, `original`, `file`, `preparation`, `deadline_originals`, `deadline_preparation`, `context_exit`, `private_error`: setup/body/teardown passed; `derived_drift`: setup passed, remaining phases incomplete |
| `tests/test_time_budget_native_grading_ci.py::test_native_task3_grading_bootstrap_without_python` | Not started; its workflow-operation/budget assertions changed |
| `tests/test_time_budget_native_grading_ci.py::test_native_task3_hosted_grading_route[guards]` | Not started; its two mutually exclusive credentialed-step assertions changed |

The passing readiness case exercised the actual controller CLI, source checks,
authenticated intake, native context, F preparer and original/derived byte
validators. Source/Actions identities, inputs, HTTP/auth and kernel facts were
synthetic. It observed four original GETs and four retained-intake GETs, one
real F preparer call, a closed handle and no trapped direction/claim/executor/
model/retention/private-write calls. The synthetic Step0 had **218405 bytes**
but a synthetic identity. Other completed cases exercised real byte refusals,
injected clock bounds and safe exception handling. Secret canaries were absent
from public JSON/stdout/stderr. The original incomplete case proves no final
derived-drift outcome in that invocation; the new result above is separate.
This is not live host/private-input evidence, a model result or a grade. No
old passing suite or unrelated test body ran. The original
[immutable record][original-proof] remains available.

### Exact sources and retained artifacts

- Base HEAD `a35b4fe58c555ad7abfce423379e99a761a8f1ef`, tree
  `bda73d9de85093ee9a3fca303cf48d336b993931`.
- Correction starts from PR782 HEAD `bc7a8d53ed83f8d52af35dc2f7639ae492fc28bb`,
  tree `c2c928da9535d28f66502d0583fdc781092637b6`.
- Current tested HEAD `a91a36b343481b9fd8af24887d933b4ffecb5472`, tree
  `7ee4102b867caf522f69b736f96eef852d4211b2`. Only the branch-aware ceiling
  assertion changed; all other test bytes and production/workflow/source
  identities match the correction base.
- Current artifacts: `/tmp/native-task3-probe-ceilings.YCXV7y/`. The exact
  command, source, collection, immediate phase reports and outcome are retained.
  `pytest.log`: **1143 bytes**, SHA256
  `3a9caea80dc68f7d410ba2a8c54df8872843c4eee67138451eacd2d451bd29d5`.
  `junit.xml`: **886 bytes**, SHA256
  `c619326a19e8ae5035137a5034ebcf337f7c8bf1c66b18c4f220c0332691f35b`.
  `reports.jsonl`: **1339 bytes**, SHA256
  `d14ff0a308504436a0828d055058b0737e0cd6d63161508d9a928b13e3f77b88`.
  `outcome.json`: **557 bytes**, SHA256
  `610fede891c8a2bc75325be08100e887f6cf1c32d58da472375314110dceab09`.
  The fixture's `pytest-tmp/test_native_task3_grading_git_0/ownership-receipt.json`
  is **54583 bytes**, SHA256
  `8d99d9888e08cd7c681d45b734124e02f2b9a36b93b7f8131bd1cdc30a2d7827`.
- Earlier three-node tested HEAD `a9263cfa8d94a9673a898b2ac498fcd2f1d9ef6e`, tree
  `e85f99787605b45ae0eddfc03546f7508898cea7`. Its four implementation/test
  blobs match the original tested HEAD
  `879f2c847b1db63c7780b8eb12da86ee894ff811`, tree
  `ddc122ea7cb2c9149c41df2a2f6bb79c0b8e1037`; only three records had changed.
- Earlier three-node artifacts: `/tmp/native-task3-probe-remaining.z0hJou/`. `source.json`,
  `command.json`, `selection.json`, collection/immediate-report logs,
  `junit-cases.json` and `outcome.json` preserve that three-node invocation.
  `pytest.log`: **2025 bytes**, SHA256
  `591545ea4b1dbb16470e5e4ca19b3523963df35c34b917c32d3d6b3666189f5a`.
  `junit.xml`: **3844 bytes**, SHA256
  `2a7f74c8ff3e577231c636464f938951df664e089b9c3e2754018bd04847b23a`.
  `reports.jsonl`: **3877 bytes**, SHA256
  `e7b9b11bca9d0ac649b89c73752ed837a2238ee913654ec02ff0362a9548ba1c`.
  `outcome.json`: **788 bytes**, SHA256
  `262f0cfda754d3509469e917341921914acf6a6f24618f2b887289f8acf288f3`.
- Original artifacts: `/tmp/native-task3-preparation-probe.7JqRjH/`. `source.json`,
  `command.json`, `selection.json`, collection/immediate-report logs,
  `wrapper-error.json` and `outcome.json` preserve the exact incomplete run.
  `pytest.log`: **1397 bytes**, SHA256
  `ab442be3cb66da708146a12c3178137125c20e36576d6eebb4f2541d74826354`.
  `reports.jsonl`: **11936 bytes**, SHA256
  `782aa630c64308d78760d354ebcd6630ab8a94a292e3138b595ba46f8708c24c`.
  `outcome.json`: **1766 bytes**, SHA256
  `99a60407c0c22fbca03a6746d7ffac06520be8922212cd9a1538d2e3170f2386`.
  JUnit is absent; it has no byte count or hash. Injected-clock hook timestamps
  are not used as wall-time measurements.
- Only CHANGELOG, this current LATEST and the direct README change after the
  current one-node proof. `final-source.json` and `handoff.json` in the current artifact
  directory seal the exact final HEAD/tree after records and verify all tested
  code bytes unchanged; the same final identities accompany PR782's body.
  No merge fact or new CI result is claimed. Both prior proof directories are
  untouched. The original timeout, earlier three-node result and current
  ownership proof remain separate, without a pooled pass claim. Detailed prior
  results also remain in the [immutable pre-correction record][prior-probe].
- The shared helper remains SHA256
  `77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`.
  Intake, preparer, executor, frozen/core/scoring/registration, metadata route,
  backend workflow, dependencies and study/input/result pins are unchanged.

### Historical evidence remains separate

Metadata workflow `376247700`, run `37789923398`/r2a1, verified absence of
the two fixed Task3/F `admission.json` and `output-manifest.json` objects at
parent `82ed160109e40dcf74029f2be34a973350374fc6` at
**2026-10-08 14:10:27 UTC**. Artifact `11555488682` is **1204 bytes**, SHA256
`3963bab2da01c66512165198bdc5072f944df3d2352bec63bd3a355d51f890c4`.
This is metadata at one parent, not an empty namespace, validated contents,
historical nonexecution, a score, zero cost or replay permission. Logs and
metadata were not fetched again. Detailed accepted metadata/clock proofs and
earlier history remain in the [immutable base record][prior-record].

Grading run `37756891578`/r3a1 at C
`0a2ef287751da62d888839ef3b92c250ecabf5fc` remains uncertain, spent and
nonretryable. Request SHA256
`549195f4e5dbfde9ee71702da247d8a43ad84c862180893e45dc496bf7687349`
and artifact `11541001301` (**1605 bytes**, SHA256
`c0b100d1b3cfc6cbdb66338b25497e361be4023e3afbe174d28b92c4d1815e0b`)
stay bound. Null claim/entry/grade fields do not prove absent effects or known
non-admission. The discarded exception remains unknown; this probe cannot
recover it. Runs `37726733625`/r1a1 and `37737075149`/r2a1 remain separate
proven bootstrap failures. All three grading submissions are spent.

The only cell remains `gpt54_sandboxv2_codex_time_budget_v1` /
`gpt54_time_budget_v1_codex_r1` / codex / repeat 1 /
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d`. Original R remains
`33e24e9c1402ec0b7c92a71222998d1407646a92`, tree
`6e67da4e12169b41a837d92eaf946db15e71010e`; F remains
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`. Output remains
`d5aeecec1394fb44d4b1da33b1be38a39acdb89a`, result **8518 bytes**, SHA256
`4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4`.
The **2 files / 408601 bytes** remain declarations, not genuine contents
fetched or verified by this implementation task. Usage/cost/score remain unknown.

Independent fixed-HEAD review and CI passed before the separate exact
source/run-number/window/hash direction and preparation-only submission above.
That one submission consumes this direction. It does not authorize a grading
retry, adoption, replay, Task5 or next cell.
The required preparation-boundary specialist failed before
execution on unavailable configured Opus4.7, provided no endorsement and was
not retried. The complete catalog was consulted once. `experiment-report-en`
preserved units and evidence boundaries; `im-not-ai-en` checked English without
strengthening claims. No study redesign or UI skill applied.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a35b4fe58c555ad7abfce423379e99a761a8f1ef/tasks/LATEST_TASK_RESULT/README.md
[original-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a9263cfa8d94a9673a898b2ac498fcd2f1d9ef6e/tasks/LATEST_TASK_RESULT/README.md
[prior-probe]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/bc7a8d53ed83f8d52af35dc2f7639ae492fc28bb/tasks/LATEST_TASK_RESULT/README.md
[probe-run]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37818721507
