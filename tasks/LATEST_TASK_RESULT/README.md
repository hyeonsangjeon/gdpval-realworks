# Latest task result

## Native Task3 grading compatibility draft; bounded proof incomplete

The one new offline selector reached native and legacy V2 positives, but the
invocation did not pass. Its 300-second bound expired with exit **124** after
**299.978913s** of wrapper time. The preserved progress log records **13 passed,
1 failed**, one interrupted node and three nodes not started. These are progress
outcomes, not a completed pytest summary. No test body was rerun; production
and test bytes stayed fixed after the invocation. Implementation acceptance
remains **HOLD**. The hosted workflow/controller is deferred.

### Scope and the corrected constraint

The leader explicitly replaced the earlier executor-unchanged constraint.
The accepted source-only finding identified V2-first task/configuration
bindings, no native Step0 parameter and the frozen grader's inference-origin
gate. Its record remains separate at
`/tmp/native-task3-grading-actions-boundary.vFmDip/boundary.json`, SHA256
`3dc65fa0359d403d79700915c33f3a6c88a94e400e0845a4a0d7482d377366b2`;
it was not a runtime proof and was not repeated here. Original executor blob
`161077fdeb1c8880c159a01c3b28a835a9264fca` had SHA256
`1dd91b268816c700f407eafe2917da433666192f9aef0a5146d4fa7a83efdef5`.

The draft adds `prepare_native_task3_grading_execution` and
`execute_native_task3_grading` in the same executor module. Only
`gpt54_time_budget_v1_codex_r1` / `codex` / repeat 1 /
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d` is eligible. The existing
`execute_first_observation_grading` signature and CLI remain first-V2-only,
including their prohibition on a Step0 argument. Shared logic carries the
selected run/task/condition through configuration, input reconstruction,
command, task fingerprint, rubric, filename, grade/sidecars and rereads.
Native Step0 joins held-parent, path-overlap and exact-byte checks, using the
whole 218405-byte role, not a 65536-byte metadata limit. Admission direction,
local once-only claim, safe child environment and configured
14400-second grading / 14520-second child envelopes remain unchanged.

The accepted intake and preparer are unchanged. The new context manager
calls the real retained intake, then issues an in-memory handle only after
model-free validation. It stages a fresh private grading-only tree without
rewriting the canonical result or accepted preparation. Only the derived
result receives `source_repo_id`, `source_revision` and
`source_identity_document_sha256`, from the actually authenticated fixed
private target, immutable output and intake receipt. It receives its own
fingerprint. The execution binding records original and derived size/hash/
fingerprint identities separately. Saved receipts and caller strings cannot
reconstruct the scoped handle; F's inference-origin gate is not removed.
No new publication ledger, grading direction or claim is created by staging.

### The single synthetic invocation

Selector:
`tests/test_time_budget_native_grading_execution.py::test_native_task3_frozen_grading_compatibility`.
AST checks verified the parameter, all eighteen IDs and imported fixture
dependencies before launch. Python 3.10.12 ran once under 300s+5s/no-`-x`,
with the known named 30-second fixture Git bounds and Python timing.

| Scenarios | Recorded outcome |
| --- | --- |
| `native`, `legacy_v2`, `task`, `r2` | Passed |
| `condition` | Failed; first failed node |
| `step0_missing`, `step0_bytes`, `step0_overlap` | Passed |
| `origin_without_intake`, `origin_revision`, `origin_receipt`, `derived_bytes` | Passed |
| `frozen_source`, `direction` | Passed |
| `partial` | Node started, interrupted by the outer bound; setup/body phase unavailable |
| `timeout`, `grade_task`, `sidecar` | Not started |

The timeout occurred before pytest wrote its final traceback or JUnit XML.
The exact failing operation and per-case timings were not retained and are
not inferred. `cases.json` explicitly reconstructs only the observed verbose
progress, not a missing JUnit report. In particular, this invocation does
not establish the planned partial/timeout or wrong-grade/sidecar assertions.

The passing native case began with real native-capture-shaped canonical bytes
without origin annotations. Real source/input/result/file validators and the
accepted intake authenticated synthetic HTTP metadata, result and two files
in four GETs under the existing cumulative 60-second contract. Real F
preparation used valid synthetic originals, including an actual 218405-byte
Step0 with its own hash. The executor reached a synthetic owned child that
used staged F configuration, source/task/output/schema and serialization
checks. The real executor validated its synthetic grade/sidecar data and
local once-only behavior. No preparer or executor verdict was mocked.
HTTP, namespace/ownership facts and child output were explicit fixtures,
not evidence of real host support, cleanup, a judge decision or quality.
The legacy V2 case exercised the unchanged API/CLI with a synthetic child
and refused a Step0 argument. Earlier 21/18/other selectors were not rerun
or pooled with these outcomes.

### Source and proof artifacts

- Accepted base: `fbe64cc6bb90ad91d0330b0f734be272b984ad9b`, tree
  `785ef4ce91782c49e9eaae460b6dc619aae3fa4d`.
- Clean tested HEAD: `9c51dde2e626faad535b739838d936501ecb9e8e`, tree
  `161e8fc14c963e2c60fd24f04d6fec2dc970a85f`.
- Tested executor blob: `10d8e56c5569cc3dea484e4bb9d875712a0d5b4c`, SHA256
  `b7c6ff1182838a7e6c93b666aebafaea7c6d2caf4efd9d6b0a13cf7b6207a80b`.
- Tested test blob: `19453645671ef83e36f77fe36a03e15004d0d444`, SHA256
  `26e9aa80a964d15ae6fa588ed69ef52fc638bfd13c05961d38c41313aa76de4f`.
- Registration seal remains
  `3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`.
  The executor is bound by C's commit/tree, not a registration source pin;
  no runtime pin or historical registration was rewritten.

Artifacts are under `/tmp/native-task3-grading-compatibility.s2Ef7S/`.
Only CHANGELOG, this record and the direct README change after the proof.
`handoff.json` and the draft PR record the final HEAD/tree without claiming
that documentation-only commit was rerun.

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `e2c809885945f34409c681f5db53831a4a06270c453f840aa348873006b04a66` |
| `command.json` | `5e4d4c758ad917c262942126debd2fd94253ce0a91c044a0de2a32bf6ff27378` |
| `selection.json` | `dc8214e0aa41af23193f9fdddd815dee9889cda6473820c799b2fb4835b393a0` |
| `source.json` | `c6478597a11aa4cff698d8d06623846b58d2f2a819d08d21e5dd5f5b1a71350a` |
| `pytest.log` | `8028943ae71eed4a16a57a15269ab3d604a04f5166a4ac44b47a0072db94280b` |
| `cases.json` | `202cf9fb22d8dd1ce2ec4a058fd47cee4b052b747bc8f284aa989a7e93346ea9` |
| `outcome.json` | `925aaf53e92423202ccc5868ed69ff4bbc8d248fb5ea1b2becf56aa0a845a150` |
| `wrapper-failure.json` | `f183e1d45af9eca1ca979376bacd2010aabf1b35c6d2f6da10ef22c193f8e522` |

### Actual Task3 remains separate and ungraded

The leader verified native Task3 generation `37631184801`, run number 5,
attempt 1, at original R `33e24e9c1402ec0b7c92a71222998d1407646a92`, tree
`6e67da4e12169b41a837d92eaf946db15e71010e`. Its generation claim is
`08e485281f25ea06311305e7a4add721a68ba9ea`, output
`d5aeecec1394fb44d4b1da33b1be38a39acdb89a`, execution request SHA256
`3d2bbe5f55f0f0558f8e38bf53ebaa22f722b60b55b2338df465196b278ffc98`.
Its immutable result is 8518 bytes, SHA256
`4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4`,
fingerprint
`4a62be1df3e21eae52bd7814359887c5f774200948ba67fc15ca62bf2f4b2967`.
Actual readout `37651509527`, artifact `11497400004`, contains 2570 bytes,
SHA256 `4dfc3e896b7f57de1c97e1aca2b37feb10031f6b04aa3afe43d1f63c9e189553`.
It verified canonical success and declared two files totaling 408601 bytes,
but did not fetch their contents. We did not hydrate or grade those actual
files here. `items_seen=56` is not a model/request count. Native usage,
counters, served identity, cost and quality score remain unknown, not zero.
Task4's separate retained canonical error at
`82ed160109e40dcf74029f2be34a973350374fc6` has no inferred inner cause.

F stays `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, template SHA256
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The actual original Step0 pin remains 218405 bytes, SHA256
`463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512`.
Synthetic hashes were not substituted for those original facts.

### Remaining gates

The [accepted intake record][accepted-intake] still records source
`4b2a4cd7284aa113835ff6fa6f7954a7799e52aa`, tree
`cf2c187d9aa34206edd53f3b6671af53c4bc030a`, review `5446592128` and eleven
CI passes. Its [earlier 21-case proof][intake-proof] remains 21 passed in
40.03s, wrapper 40.587362s, at `8faa9c1c3adf9cc6cc8debd6335a72c6bd7e379f`.
Those are separate completed observations, not evidence that this invocation
passed. The leader's bounded architectural decision approved implementation
only. The specialist grading/workflow review invocations failed before
execution on unavailable configured model labels, including Opus 4.7;
they were not endorsements and were not retried.

The failed/incomplete cases, independent fixed-HEAD review and final CI remain
open. The hosted route and its durable private grade-attempt CAS are deferred;
local once-only protection is not distributed admission. Genuine originals,
credentialed file intake, exact source/direction/permissions and actual runtime
checks remain required before any later grading. The existing owner budget
decision is not the missing gate, but this draft grants no live authority.
The twenty-cell cohort, model, budgets, F, rubrics and scoring are unchanged.
No workflow, HF write, Azure/model/grader call, live claim, readout, CI query,
dispatch/retry, Project change, merge, consumed Task1-4 replay, Task5 or ABBA
advance occurred. The design/reporting skills were used to preserve these
boundaries; this record is not independent source-review evidence.

[accepted-intake]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fbe64cc6bb90ad91d0330b0f734be272b984ad9b/tasks/LATEST_TASK_RESULT/README.md
[intake-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/4b2a4cd7284aa113835ff6fa6f7954a7799e52aa/tasks/LATEST_TASK_RESULT/README.md
