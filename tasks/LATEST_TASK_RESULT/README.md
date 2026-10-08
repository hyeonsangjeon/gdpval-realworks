# Latest task result

## Retained-payload source accepted for delivery

The leader directly reviewed HEAD
`2d6fc1ce47f35e429040f08ea715c6f263c861d5`, tree
`b6702c679134f90b15a3f58fdacfbccd38522074`. Owner comment review
`5464000494` records no blocking source finding. All **11 checks** for that
exact head succeeded in CI run `37853929691` and advance-check run
`37853929689`. This is direct owner review, not a specialist endorsement.

The accepted scope is deliverable-only bounded payload resolution plus the
one-line fake-clock correction below. The two fixed metadata/result reads,
existing host policy, CDN credential exclusions, **10-request** hydration
ceiling, shared **60-second** deadline and exact size/hash checks remain.
The separate local proof outcomes below are unchanged; no successful test
was rerun by the leader.

These are pre-delivery review and validation facts. The remaining step is one
separately directed model-free preparation probe with its own exact source,
run number, window and request hash. No live readiness, historical LFS cause,
recovered grading result, replay authority or private write follows from this
acceptance. Project completion still requires the actual experiment evidence.

## PR #784 native readout fake-clock correction

Only the `cumulative_bound` scenario in
`tests/test_time_budget_result_readout.py::test_time_budget_native_canonical_readout`
now starts its fake clock at `1000.0`. The exact failed node passed once under
TERM120s/KILL5s. No production, workflow, resolver, shared helper, pin, budget
or other test site changed. The earlier payload proofs remain separate below.

### Established CI failure and prior review

The leader read CI run `37845775719`, time-budget-contracts job `113546154746`,
at HEAD `e11048810176178cacefb2110df590d58f4a5e40`, tree
`2e500a8c4f5267bf7659ade376e4dcffa3ab8c12`. Its pytest summary was **1 failed,
493 passed in 1850.64s**; that duration is not the total GitHub job duration.
The other **10 checks** succeeded at the leader's snapshot. No CI status or
old log was fetched during this correction.

Line 574's exact assertion expected `25`; the observed second request timeout
was `24.999999999999773`. Line 531 seeded `now = [time.monotonic()]` before the
two `+35` advances. That fractional origin made exact subtraction unstable.
This file was unchanged by the earlier payload PR. The one-line correction
uses `now = [1000.0]` and preserves `+35`, exact `== 25`, the **60-second**
cumulative bound, **30-second** per-request checks and refusal outcome. No
tolerance or production clock change was introduced.

The leader found no blocking source defect in the prior ten-file change at
`e11048810176178cacefb2110df590d58f4a5e40`. That review is evidence about that
source, not approval of this new HEAD.

### This targeted validation

The existing isolated branch was clean at the prior HEAD before editing.
The one-line correction was committed normally before testing as
`fad2230aff020303fe609273422edc3dabf7535c`, tree
`66a488608045f01a7f940e337b625e98835c13fd`. Existing Python **3.10.12** and
pytest **9.1.1** were used; no dependency installation or new proof framework.
Exact collection found **1 node**, exit **0**, in **1.38s** pytest elapsed
and **1.785s** command wall time. From `batch-runner`, with the sanitized
offline environment retained in `command.json`, the sole body invocation was:

```bash
timeout --signal=TERM --kill-after=5s 120s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -v --tb=short --capture=tee-sys --basetemp=/tmp/native-task3-pr784-clock.zA3VQy/pytest-tmp --junitxml=/tmp/native-task3-pr784-clock.zA3VQy/junit.xml 'tests/test_time_budget_result_readout.py::test_time_budget_native_canonical_readout[cumulative_bound]'
```

Result: **1 passed in 1.85s**, exit **0**; Bash measured **2.238s** command
wall time, including timeout/Python but excluding separate collection. The
command ran **2026-10-08 22:22:34..22:22:36 UTC**. JUnit records **1 test,
0 failures, 0 errors, 0 skipped**. No other test body or successful earlier
selector ran. Synthetic transport and source fixtures exercised the real
readout refusal/validator; this was not a private read or live execution.

Artifacts are retained in `/tmp/native-task3-pr784-clock.zA3VQy/`:

- `pytest.log`: **752 bytes**, SHA256
  `a22867de68ee80adb8c1f548580910139ec96e8dfad0f794d1913b16636c2ffb`.
- `junit.xml`: **394 bytes**, SHA256
  `754354820aa1b43a88ea6fb3bdd36eade651ac78584709aa37733033ea3dc09e`.
- `collection.log`: **540 bytes**, SHA256
  `68e7bd56a9c0b287b18c268a371914c1d8ec4eafc28c775dc51342844d91ce1e`.
- Exact command, source and outcome JSON receipts preserve the independent
  collection/test timings and exit codes. Only CHANGELOG and this LATEST
  change after the tested commit. `final-source.json` in this directory and
  the updated PR body seal final HEAD/tree after that records-only commit.
  No carrying-PR merge SHA, time or state is claimed.

### Unchanged retained-payload implementation

The native intake now resolves only its two retained deliverable payloads
through the existing HF reader. Real SDK/adapter/F checks completed preparation
with synthetic plain and redirected payloads. The first proof had one test
expectation failure; its isolated, test-only correction passed. These are
separate results, not a pooled passing suite or a live recovery claim.

`gpt54_time_budget_native_grading_intake._hydrate` preserves its immutable
private metadata GET and canonical result JSON raw GET, with no redirects.
Only the two authenticated, canonical deliverable paths use `_hf_read` and
`_hf_redirect`. Each permits at most **4 streamed GETs**, including the final
payload response. The hydration cap changes prospectively from **4 to 10 HTTP
requests**: **2 + 4 + 4**, under the same **60-second cumulative deadline** and
existing **30-second per-request cap**. There is no extra HEAD/metadata/batch
operation, retry, pagination, automatic redirect or background download.

The adapter replaces the raw-only event hooks on the same scoped SDK session
before payload reads. Every next URL is validated before transmission against
the unchanged HTTPS Hub/cache/HF-owned-CDN policy. CDN authorization and cookie
headers refuse before transmission. Encoded/oversized bodies, excess hops,
unsafe paths/revisions and expired deadlines still refuse. Full declared
payload SHA256, size and canonical path checks remain mandatory; pointer
identity cannot substitute for payload identity. Partial state is not adopted.

No workflow, CLI mode, shared reader, registry, original source/input/result/F
pin, core/preparer/scoring code or grading budget changed. The execution file
has only a directly coupled comment correction. The shared Git helper remains
SHA256 `77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`.
Grade/probe separation, context closure and no-retry authority remain intact.
Preparation still stops before direction, permanent/private or local grading
claim, executor/model, retention and private-storage writes. F/child/job limits
remain **14400 seconds / 14520 seconds / 270 minutes**.

### Earlier payload proof results (not rerun)

Imports, fixture dependencies and exact collection were checked before each
invocation. Python **3.10.12**, pytest **9.1.1**, huggingface-hub **1.24.0** and
httpx **0.28.1** were already installed. Both earlier invocations used **300s+5s**, no
`-x`, local Git capped at **30 seconds**, immediate phase/failure flushing and
JUnit. Warnings are the existing `record_property`/`xunit2` compatibility warning.

The first invocation selected only the **11 new cases** of
`tests/test_time_budget_native_retained_payload.py::test_native_task3_retained_payload`
and the directly changed existing
`tests/test_time_budget_native_intake_refusal_points.py::test_native_task3_intake_refusal_points[raw_lfs_pointer]`.

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-retained-payload.KtsYUj/run-proof.py
```

It reported **1 failed, 11 passed, 12 warnings in 44.47s**, exit **1**.
Pytest-process elapsed was **44.912487s**; wrapper elapsed was **49.386871s**,
from **2026-10-08 21:01:48.057847 UTC** to **21:02:37.444591 UTC**. All setup
and teardown phases passed. The sole body failure was `[deadline]`, line 262:
the actual timeout list was `[30, 30]`, while the new test expected `[60, 30]`.
The existing shared reader already defined `REQUEST_SECONDS = 30`; this was
a test expectation mismatch, not a production timeout violation.

Only that expectation was corrected to `min(30, remaining)` with an explicit
assertion that the existing request cap is 30. Production bytes did not change.
After exact collection, only the unresolved `[deadline]` node ran:

```bash
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-task3-retained-payload-deadline.UXqu06/run-proof.py
```

It reported **1 passed, 1 warning in 5.74s**, exit **0**. Pytest-process elapsed
was **6.168239s**; wrapper elapsed was **9.704131s**, from **2026-10-08
21:03:59.813403 UTC** to **21:04:09.517519 UTC**. Setup/body/teardown passed.
No successful node was rerun; the original failed invocation is unchanged.
These are local pytest/process/wrapper measurements, not GitHub job durations.

### What the synthetic proof established

| Exercised path | Observed retained GETs | Observed outcome |
|---|---:|---|
| Plain payloads | 4 | Actual hydration and one real F preparation completed |
| Hub/cache/CDN payloads | 10 | Four GETs per deliverable, one real F preparation, real native materialization and closed-handle refusal |
| Unsafe redirect variants | 1, 2 or 3 | Metadata/result redirects and unsafe payload hops refused before the next transmission |
| Excess hops on first or second payload | 6 or 10 | A fifth request for that payload was not sent |
| Wrong hash, pointer, encoding or size | 3 | Real download/identity checks refused; no successful F preparation |
| SDK bearer/cookie contamination | 3 or 4 | No bearer/cookie CDN transmission; session closed |
| Corrected cumulative-expiry variants | 2, 4 or 6 | Refused after initial reads, at the second payload or within redirected acquisition |

HTTP/auth, source anchors and input declarations were synthetic, including
the **218405-byte** Step0 and two files totaling **408601 bytes**. Successful
preparation and integrity verdicts were not stubbed. Cheap refusal variants
call the actual hydration adapter with a genuinely reconstructed synthetic
marker; only the two positive cases run full F preparation. The changed
pointer case also runs the real controller/probe validator with **4 separate
synthetic original-input GETs** and **3 retained GETs**. Those original-input
requests are not part of the hydration cap.

Forbidden grading/private-write calls and private exception formatting stayed
at **0** in the completed checks. Canary data stayed out of public JSON/stdout/
stderr. SDK factories/environment were restored, scoped sessions closed and
the issued native handle became unusable. Wrong-hash partial local input was
preserved without a ready record or preparation. This proves synthetic protocol
behavior, not historical LFS use, the bytes returned by a live server or a
successful future hosted probe.

### Earlier payload sources and retained artifacts

- Base HEAD `2d99265ac79001506f7421485fed037bcad09a2a`, tree
  `7971342e0743f570069f31d92241de43e85ac7f0`.
- First tested HEAD `83ae63a52d3d299571df60c3afb1f6474bcac433`, tree
  `1140e4d069487dfe600d67fb1a3d84fe080d9c88`.
- Corrected tested HEAD `c62a7efbcf6922badaa70ae0b38a88041aec3b39`, tree
  `e4e44f211612f59ac74bd16de9da8d5f41548330`. Only the new test's timeout
  expectation differs from the first tested source.
- First-proof directory `/tmp/native-task3-retained-payload.KtsYUj/`:
  `pytest.log` **3970 bytes**, SHA256
  `8480346cf6fc78e3869aa589e170d6ae6a8657a3a73510559aaaf313fb23f1df`;
  `junit.xml` **16501 bytes**, SHA256
  `8df569e7eb71487c4a381b03d8219799bc3584f9e6ad116cee726e333ee145e7`;
  `reports.jsonl` **37173 bytes**, SHA256
  `bbf0ffc7c5e700d75557b0c008f9947ff957879c7beed98e2288929fb42ef2a2`.
- Follow-up directory `/tmp/native-task3-retained-payload-deadline.UXqu06/`:
  `pytest.log` **1095 bytes**, SHA256
  `da40fa580845fe55b7a469b16d063bac59a14eaf56fb7551ce8f350f2c3bdf3d`;
  `junit.xml` **1963 bytes**, SHA256
  `48beb9053dfe68340afb5f43cf1485b3363f4cc431e4bafcb3706e802f65148b`;
  `reports.jsonl` **3823 bytes**, SHA256
  `7eaa06f76844984c18eea9f880ad3e31babad009c191d4b6905d2d5ae38487a4`.
- Both directories retain exact command/selection/source/outcome receipts and
  JUnit case properties. At the original PR publication, only CHANGELOG,
  LATEST and the direct README changed after the corrected payload proof.
  The first directory's `final-source.json` seals that prior final HEAD
  `e11048810176178cacefb2110df590d58f4a5e40`, tree
  `2e500a8c4f5267bf7659ade376e4dcffa3ab8c12`, and its tested-code equality.
  That [immutable publication record][payload-prior] remains separate from
  this clock correction. No carrying-PR merge fact is recorded.

### Historical refusal, fixed bindings and remaining gates

Established [probe 37838315533][probe-run]/r5a1, job `113520972985`, used source
`af31e3fa400e2b0bcd49d4949464c8bba948eb49`, tree
`78551dadcd9592172ec12c414016939d1b9b3034`. Step 16 failed during **2026-10-08
20:20:09..20:20:13 UTC**; source/request checks and completion validation/upload
succeeded. Artifact `11576133610`, **1534 bytes**, SHA256
`7f50e87a95798a2ee0a35aacb0ce37457c6eaf4c27af8b3e5996b860310d1f23`, binds request
`79a7fb62a2ce9de6c2ab3cd1bcb8fc2f9bbb92146130cc52f59f2540308becfe` and exact
C/R/F/result/cell. Environment/originals completed; intake/preparation started
with `validation_refused` at `retained_deliverable_identity`; verified
preparation is null. Grading, reuse and retry authority remain false. The
returned bytes and historical LFS use remain unknown. Historical logs,
artifacts and private bytes were not refetched.

The fixed cell remains `gpt54_sandboxv2_codex_time_budget_v1` /
`gpt54_time_budget_v1_codex_r1` / codex / repeat 1 /
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d`. Original R remains
`33e24e9c1402ec0b7c92a71222998d1407646a92`, tree
`6e67da4e12169b41a837d92eaf946db15e71010e`; F remains
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`. Output remains
`d5aeecec1394fb44d4b1da33b1be38a39acdb89a`; result **8518 bytes**, SHA256
`4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4`.
The **2 files / 408601 bytes** remain declarations, not genuine private contents
verified here. Usage/cost/score remain unknown.

Run **37756891578/r3a1** remains uncertain, spent and nonretryable; null public
claim/entry/grade fields do not establish absent effects or known non-admission.
Runs 1/2 remain separate proven bootstrap failures. All prior submissions stay
spent. Metadata absence remains limited to two fixed objects at parent
`82ed160109e40dcf74029f2be34a973350374fc6` at **2026-10-08 14:10:27 UTC**.
No replay or historical reinterpretation follows from this implementation.

The prior seven-case diagnostics proof, earlier incomplete probe proof and
later targeted results remain separate in the [immutable prior record][prior].
Prior review `5462314957` and its 11 successful checks accepted diagnostic HEAD
`f34d0f4ef841913271cfbba82840827ed71998cc`, not this transport change. The
current source review and CI gate are recorded above. Any later live probe
needs a separate exact leader source/run-number/window/hash direction. The
implementation and clock-correction worker did not query CI, dispatch, access
private/live data, perform Azure management, model/grade, replay, Task5, next
cell, merge or Project edits. The leader independently read the final checks.

The complete catalog was consulted once. `experiment-report-en` preserves
numeric units, provenance and uncertainty; `im-not-ai-en` checks English.
Experiment-design does not apply because no study/configuration is changing;
UI/animation skills do not apply because no interface work is involved. No
unavailable specialist was retried and no endorsement is claimed. The earlier
reporting reviewer failed before execution with HTTP 400 and supplied no review;
it was not retried. Scoped literal checks and a direct condition audit cover
this narrow records update.

[payload-prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/e11048810176178cacefb2110df590d58f4a5e40/tasks/LATEST_TASK_RESULT/README.md
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/2d99265ac79001506f7421485fed037bcad09a2a/tasks/LATEST_TASK_RESULT/README.md
[probe-run]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37838315533
