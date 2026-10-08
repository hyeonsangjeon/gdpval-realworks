# Latest task result

## Preparation probe: three remaining nodes passed on unchanged code

The existing native Task3 controller/workflow now has a separately selected
model-free `prepare-probe` operation. It reuses originals intake and the real
native context/F preparer, closes the handle, and stops before direction,
claim, local grading once-store, executor, model, retention or private-storage
write. This is an implementation-only draft, not a live probe or grading retry.

The authorized follow-up ran only `derived_drift` and the two previously
unstarted guard nodes: **3 passed, 3 warnings in 53.27 seconds**, exit **0**.
Pytest-process elapsed was **53.700716 seconds**; wrapper elapsed, including
source/collection checks, was **59.201955 seconds**. No production, workflow
or test change was needed. The eight previously completed cases did not run.

The original invocation remains an incomplete **300-second** timeout, exit
**124**, wrapper **301.135259 seconds**, with eight passing setup/body/teardown
reports, only setup completed for `derived_drift`, neither guard started and
no final pytest summary or JUnit. These are separate observations, not a
pooled eleven-node pass or a claim that the original invocation finished.

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

### Remaining-node invocation

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-probe-remaining.z0hJou/run-proof.py
```

The existing task-local wrapper was copied and restricted to exactly these
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
- Follow-up tested HEAD `a9263cfa8d94a9673a898b2ac498fcd2f1d9ef6e`, tree
  `e85f99787605b45ae0eddfc03546f7508898cea7`. Its four implementation/test
  blobs match the original tested HEAD
  `879f2c847b1db63c7780b8eb12da86ee894ff811`, tree
  `ddc122ea7cb2c9149c41df2a2f6bb79c0b8e1037`; only three records had changed.
- New artifacts: `/tmp/native-task3-probe-remaining.z0hJou/`. `source.json`,
  `command.json`, `selection.json`, collection/immediate-report logs,
  `junit-cases.json` and `outcome.json` preserve this three-node invocation.
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
  follow-up proof. `final-source.json` and `handoff.json` in the new artifact
  directory seal the exact final HEAD/tree after records and verify all tested
  code bytes unchanged; the same final identities accompany PR782's body.
  No merge fact or new CI result is claimed. The prior proof directory is untouched.
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

Independent fixed-HEAD review/CI and a separate exact leader
source/run-number/window/hash direction remain required before
any live read-only preparation probe. No private access, dispatch, grading
retry, adoption, replay, Task5, Project edit, merge or next cell occurred or is
authorized. The required preparation-boundary specialist failed before
execution on unavailable configured Opus4.7, provided no endorsement and was
not retried. The complete catalog was consulted once. `experiment-report-en`
preserved units and evidence boundaries; `im-not-ai-en` checked English without
strengthening claims. No study redesign or UI skill applied.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a35b4fe58c555ad7abfce423379e99a761a8f1ef/tasks/LATEST_TASK_RESULT/README.md
[original-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a9263cfa8d94a9673a898b2ac498fcd2f1d9ef6e/tasks/LATEST_TASK_RESULT/README.md
