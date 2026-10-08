# Latest task result

## PR781 clock tests corrected; production unchanged

Only the readout cumulative-bound test and the new metadata selector's
`cumulative_bound` case now seed their fake clocks with exactly representable
`1000.0` instead of live `time.monotonic()`. Their **+35-second** advances,
**60-second** cumulative bound, **2 calls**, exact second timeout **25**,
refusal and null-summary assertions are unchanged. The older metadata clock
test is untouched. One bounded invocation passed the two authorized nodes:
**2 passed in 2.52s**, exit **0**. No production rounding, deadline, workflow,
helper, schema, source pin or grading code changed.

### Reported CI failure, separate from the local proof

The leader read run `37776879316`, time-budget-contracts job `113309863966`:
**1 failed, 466 passed in 1635.07s**. That is pytest elapsed time, not full job
duration. At readout test line **700**, the exact timeout assertion observed
`24.999999999999773` instead of `25`. The fractional live-clock seed caused
cancellation/representation noise; this is not a demonstrated production
timeout violation. The inspected log was **123102 bytes / 1138 lines**,
SHA256 `3c97713c3aad9465d5cbe72aa87d471cd071b945da6b9f4ae1c8a8633e6ab387`.
These are leader-supplied facts; the log was not fetched again. At that
snapshot, **7** other checks had succeeded and **3** were running. No status
was polled. Metadata source review remains conditional, and the delivery CI
gate is not satisfied by this local correction.

### One two-node offline proof

Only these body selectors ran, together once:

```text
tests/test_time_budget_result_readout.py::test_time_budget_result_readout_cumulative_bound
tests/test_time_budget_storage_metadata.py::test_native_task3_grade_metadata_scope[cumulative_bound]
```

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-metadata-clock.uKhiQL/run-proof.py
```

Exact file-diff, import/fixture and collection checks preceded the bodies.
Python **3.10.12**, pytest **9.1.1**, **300s+5s**, no `-x`, existing fixture
Git bounds and the **30-second** task-local Git cap were retained. Pytest
reported **2 passed in 2.52s**, with no warning summary. The process took
**2.935624 seconds**; the wrapper, including source and collection checks,
took **5.955130 seconds**, from **2026-10-08 13:10:31.439290 UTC** through
**13:10:37.394407 UTC**. Both exact-timeout/refusal paths passed with real
source, CLI and transport validators, synthetic Git/Actions identities and
synthetic HTTP responses. No private read, intake, claim, model or grader
ran. No other test body ran, and the full original 31-case selection was not
rerun.

### Exact sources and retained artifacts

- Starting PR781 HEAD: `2b23b94a1b2637cd12041e7659d0c8ae252d423c`, tree
  `872a42c9210122a48118274f3e864122a31553d9`.
- Main base remains `fc9796f048fded13416bde1804e9046608e49652`, tree
  `76385434d312cd6b01c077acbc4af2344e127216`.
- Tested HEAD: `cda79aa0f355de4975192a48becc06e9dbc555a9`, tree
  `581cfc7486f65af21c65aaba4456daafadc38781`. Its only changes from the
  starting HEAD are the two seed lines; all other test assertions and
  production bytes were checked for equality.
- Artifacts: `/tmp/native-task3-metadata-clock.uKhiQL/`. `command.json`,
  `source.json`, `selection.json`, collection and immediate-report logs,
  `junit-cases.json` and `outcome.json` retain the exact selection and result.
  `pytest.log`: **750 bytes**, SHA256
  `1d558afa9c7b992675856aad4600349dec78da570d115550a4c9c66eb7444576`.
  `junit.xml`: **524 bytes**, SHA256
  `13994e41e396102c629b2337de36086bd6c5731aba21c1c4baa7328fc520331b`.
  `outcome.json`: **669 bytes**, SHA256
  `4f2df675e19e5f7ac8d97d418026a7779274382d97ecf8044575bfd59623f00f`.
- Only CHANGELOG, this current LATEST and the direct README change after
  testing. External `final-source.json` and `handoff.json` seal the exact
  final HEAD/tree after the records commit and verify tested-code equality.
  No carrying-PR merge facts or new CI outcome are claimed.

### Original proof preserved, not rerun

At `83ea4a90f14b8cba93c4609a48ea4d332d9e48c0`, tree
`42d070882d36ee077344fcc2285c41306e6bb0d3`, the original **30** metadata cases
and changed workflow contract passed once: **31 passed in 19.64s**, exit
**0**, process **20.036112s**, wrapper **22.192873s**. That synthetic proof
remains separate from the later CI failure and this two-node correction.
Artifacts remain in `/tmp/native-task3-grade-metadata.AQ3jgv/`; log SHA256
`8763a3c947fab19026d046bd4d5ce5a399abd72861362b4497132c391bb88602`,
JUnit SHA256 `d525e67f8996ba61ae84b560cd68da227b2849530ae0dfa8338080fefe05b2cb`.
The [immutable original record][metadata-record] retains its full scope,
timing and artifact details. The prior accepted diagnostics and submission
evidence remains in the [immutable accepted record][prior-record].

The read-only route still permits only its default Task1 generation scope
or the closed native r1 Task3/F `admission.json` and `output-manifest.json`
metadata scope. Exactly one private/head GET and one immutable-parent
paths-info POST share **2 operations / 60 seconds / 64 KiB per response**.
All source/identity/transport checks remain intact; no third operation,
redirect, retry, body download or storage write is added. OID/size remain
metadata, not validated contents. `contents_verified=false` and
`retry_allowed=false` stay mandatory. The shared Git helper remains SHA256
`77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`.

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
Actions submission also needs a separate exact leader direction. The prior
mandatory metadata-scope review attempt failed before execution on the
unavailable configured Opus4.7 label; it supplied no endorsement and was not
retried. The complete skill catalog was consulted once. `experiment-report-en`
preserved numerical evidence, units and uncertainty; `im-not-ai-en` checked
English without strengthening claims. No new study or UI exercise applied.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fc9796f048fded13416bde1804e9046608e49652/tasks/LATEST_TASK_RESULT/README.md
[metadata-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/2b23b94a1b2637cd12041e7659d0c8ae252d423c/tasks/LATEST_TASK_RESULT/README.md
