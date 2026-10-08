# Latest task result

## Closed native Task3 grading metadata scope implemented; no private read

The existing storage-metadata route now has one explicit `native_task3_grade`
choice. One bounded offline invocation passed **31 tests in 19.64s**, exit
**0**: **30** new metadata cases and the existing workflow contract node whose
input assertion changed. This is implementation and synthetic proof only.
No workflow was dispatched and no private state was inspected. Fixed-HEAD
review and CI are still required before a separate exact leader direction
can authorize a read-only Actions submission.

The prior diagnostics source was accepted in PR780, owner review
`5456198248`, with all **11** CI checks successful, as reported by the leader.
That acceptance does not cover this new metadata scope. Detailed prior
diagnostics, source, proof and submission evidence remains in the
[immutable accepted record][prior-record].

### Exact read-only boundary

The default `generation_task1` selection keeps the original first-V2 Task1
prefix and v1 envelope unchanged. The new scope permits only these two paths:

```text
time-budget-grading/gpt54_sandboxv2_codex_time_budget_v1/gpt54_time_budget_v1_codex_r1/2ea2e5b5-257f-42e6-a7dc-93763f28b19d/882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2/admission.json
time-budget-grading/gpt54_sandboxv2_codex_time_budget_v1/gpt54_time_budget_v1_codex_r1/2ea2e5b5-257f-42e6-a7dc-93763f28b19d/882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2/output-manifest.json
```

The existing private/head GET returns the inspected parent. One paths-info
POST requests exactly those two objects at that immutable parent. The route
retains its **2-operation / 60-second / 64-KiB-per-response** limits, source
closure, owner/Actions/attempt gates and single credential-bearing step.
There is no third operation, pagination, redirect, retry, content download or
storage write. No repository or path is caller-selectable. The grading
workflow, executor, scoring, registries and historical input/result pins do
not change. The shared Git helper stays exactly SHA256
`77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`.

The new envelope binds source, Actions run, independently selected scope,
fixed target identity, native r1 Task3 cell, frozen F and inspected parent.
Its two object roles report `present`, `absent` or `unknown`, with
`metadata_oid` and `metadata_size_bytes` only where verified from metadata.
`contents_verified=false` and `retry_allowed=false` are mandatory. This is
not validation of admission or output-manifest contents. Exact HTTP 200
empty metadata may establish those two objects absent at that parent, not
an empty grading namespace or historical nonexecution. HTTP 404, malformed,
duplicate, unrelated, oversized, encoded or timed-out responses refuse;
they do not become success-shaped absence. A verified parent may survive a
refused second operation while both object states remain unknown.

### One bounded offline proof

The exact body selectors were:

```text
tests/test_time_budget_storage_metadata.py::test_native_task3_grade_metadata_scope
tests/test_time_budget_storage_metadata.py::test_time_budget_storage_metadata_workflow_contract
```

The task-local wrapper command was:

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-grade-metadata.AQ3jgv/run-proof.py
```

AST/import/fixture checks and exact collection preceded the bodies. Python
**3.10.12**, pytest **9.1.1**, **300s+5s**, no `-x`, fixture Git limits and a
**30-second** task-local Git cap were used. Pytest reported **31 passed in
19.64s**, with no warning summary. The pytest process took **20.036112
seconds**; the wrapper, including source and collection checks, took
**22.192873 seconds**, from **2026-10-08 12:16:17.026621 UTC** through
**12:16:39.219481 UTC**. No older selector or full suite ran again.

The new cases exercised the real CLI, SDK, held source validation, bounded
transport and strict envelope validator. Git source/Actions identities,
private-head and object metadata, credentials and HTTP responses were
synthetic. The proof covered both fixed objects, empty and single-object
responses, legacy/default compatibility, unknown scope, privacy/target/parent
refusals, HTTP/encoding/size/time failures, duplicate keys/paths, unrelated
paths/types, source drift, wrong revision, a blocked third operation,
no-clobber and secret-canary exclusion from public JSON/stdout/stderr.
No private object, model, native intake or grader ran. Successful metadata
validation was not mocked and is not a grade or historical result.

### Source identities and artifacts

- Base: `fc9796f048fded13416bde1804e9046608e49652`, tree
  `76385434d312cd6b01c077acbc4af2344e127216`.
- Tested HEAD: `83ea4a90f14b8cba93c4609a48ea4d332d9e48c0`, tree
  `42d070882d36ee077344fcc2285c41306e6bb0d3`.
- Artifacts: `/tmp/native-task3-grade-metadata.AQ3jgv/`. `command.json`,
  `source.json`, `selection.json`, collection and immediate-report logs,
  `junit-cases.json` and `outcome.json` preserve the exact selection and result.
- `pytest.log`: **3937 bytes**, SHA256
  `8763a3c947fab19026d046bd4d5ce5a399abd72861362b4497132c391bb88602`.
  `junit.xml`: **4466 bytes**, SHA256
  `d525e67f8996ba61ae84b560cd68da227b2849530ae0dfa8338080fefe05b2cb`.
  `outcome.json`: **3945 bytes**, SHA256
  `e558ce34a087f73c2aafef8d05ad067fb43e4c5b3d6e6386c2842689b412ffba`.
- Only CHANGELOG, this current LATEST and the direct README change after
  testing. External `final-source.json` and `handoff.json` seal exact final
  HEAD/tree after the records commit and verify tested-code equality. No
  carrying-PR merge facts or new CI outcome are claimed.

### Historical uncertainty and remaining gates

Run `37756891578`/r3a1 at C `0a2ef287751da62d888839ef3b92c250ecabf5fc`
remains uncertain and nonretryable. Its request SHA256 is
`549195f4e5dbfde9ee71702da247d8a43ad84c862180893e45dc496bf7687349`;
artifact `11541001301` holds the matching **1605-byte** public completion,
SHA256 `c0b100d1b3cfc6cbdb66338b25497e361be4023e3afbe174d28b92c4d1815e0b`.
Null claim/entry/grade fields do not prove absent effects, known non-admission,
a score or zero cost. The lost exception remains unknown. Runs
`37726733625`/r1a1 and `37737075149`/r2a1 remain separate proven bootstrap
failures. All three submissions are spent; no rerun, adoption or reclassification
is authorized. Old logs were not fetched again.

Original R remains `33e24e9c1402ec0b7c92a71222998d1407646a92`, tree
`6e67da4e12169b41a837d92eaf946db15e71010e`; F remains
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`. Generation output remains
`d5aeecec1394fb44d4b1da33b1be38a39acdb89a`, result **8518 bytes**, SHA256
`4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4`.
The **2 files / 408601 bytes** remain declarations, not contents verified here.
Even an authorized later metadata read cannot grant readout eligibility,
claim adoption, grading replay, Task5 or a next cell.

Independent fixed-HEAD review and CI remain required. A future read-only
Actions submission also needs a separate exact leader direction. The new
mandatory metadata-scope review attempt failed before execution on the
unavailable configured Opus4.7 label; it supplied no endorsement and was not
retried. The complete skill catalog was consulted once. `experiment-report-en`
preserved numerical evidence, units and uncertainty; `im-not-ai-en` checked
English without strengthening claims. No new study or UI exercise applied.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fc9796f048fded13416bde1804e9046608e49652/tasks/LATEST_TASK_RESULT/README.md
