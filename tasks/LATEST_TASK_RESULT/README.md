# Latest task result

## Project5 prospective time-budget comparison registration — 2026-10-05

The separate versioned registration `gpt54_sandboxv2_codex_time_budget_v1` now
compiles offline. It asks which tested GPT-5.4 configuration produces usable,
graded work within the same external generation-time budget. It compares
configuration bundles, not isolated harness effects or equal native compute.
There is no new execution route, preparation or live observation.

Delivery remains **HOLD** for remaining CI and final-record acceptance. The
registration implementation and its original 75-case proof are unchanged. After
the CURRENT workflow-digest correction, the unfinished Python partition node
passed once at the leader-reviewed correction HEAD. Separately, the leader
supplied successful CI evidence for the transport fakes and live artifact check.
The first failed local combined attempt remains a failure; no local Node or HF
check was repeated.

The existing historical comparison and local-source profile keep their intent,
controls, run IDs and launch refusals. The closed 30-cell external-budget pilot
and 8-cell retention diagnostic are neither reopened nor pooled with this study.

### Registered scope and evidence boundary

The same five approved tasks and GPT-5.4/direct-v1/xhigh deployment binding are
fixed. Inference concurrency is 1, with at most 20 generation observations:

| Order | Run ID | Condition | Repeat | Tasks |
| --- | --- | --- | ---: | ---: |
| 1 | `gpt54_time_budget_v1_v2_r1` | SandboxV2 | 1 | 5 |
| 2 | `gpt54_time_budget_v1_codex_r1` | native Codex | 1 | 5 |
| 3 | `gpt54_time_budget_v1_codex_r2` | native Codex | 2 | 5 |
| 4 | `gpt54_time_budget_v1_v2_r2` | SandboxV2 | 2 | 5 |

Each observation has one external attempt. Failed observations are not externally
replayed, resumed or retried. The registered generation deadline is 1200 elapsed
seconds from first generation start, including all waits and native internal
recovery. At that deadline, request interruption and allow at most 20 seconds of
local cleanup, recorded separately. The 1220-second maximum planned host lifecycle
does not bound remote billing or guarantee server-side cancellation.

Native model-attempt and repeated-request counts, input/output/written tokens
and native retries are observation-only when actually available. Missing counters
remain explicitly unavailable, not zero or estimated. Cumulative usage snapshots
are differenced; cached-input and reasoning breakdowns are not counted again.
Incomplete usage retains nulls and partial reasons. No numeric shared native
request/token hard caps or money hard cap are registered. V2's 9-turn/8192-output
settings remain named V2-specific settings; a Codex native turn is not an equivalent
count. Existing per-harness template bytes and provider retry settings are sealed,
without claiming that retry settings bound every native recovery path or that
client requests establish backend enforcement.

Grading remains one attempt per resulting observation with the same source-bound
frozen judge. Failed/missing outcomes are retained and never regraded because of
score. The decision rule is descriptive paired outcome/grade differences and
within-condition spread over the fixed observations, with no early selection or
score-dependent repeats. Two repeats do not establish precise uncertainty or
isolated causality.

`gpt54_time_budget_comparison.py` implements only a strict registration compiler.
It rejects unknown fields, contradictory hard-cap claims, changed controls,
source drift, duplicate YAML keys and aliases. The unchanged comparison compiler
validates all 37 source pins, the real score-free task selection, input identities
and whole grader TEMPLATE closure. Only validated model, dataset, judge, result,
cost and named per-harness facts are reused. No fake dispatch/grading plan or
unchecked compiler path is introduced.

The compiled result separates registered intent, implementation status and launch
authority. Deadline/cleanup integration is not implemented for this study, and
measurement availability remains unverified. All launch/execution flags remain false.
There are no commands, runtime configs or preparation recipes. The offline CLI
returns status 2 even for a valid registration. Existing launch guards are
unchanged, including `comparison_runtime_launch_refused`.

### Reviewed basis and immutable source boundaries

The fresh clean worktree started at accepted main
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, after an ordinary origin fetch
of that exact missing object. The leader supplied prior source-reviewed PR748
HEAD `b1a8e9ed6296ff346580b110b4ddad9172af9b25`, owner
[review5410023630][prior-review], all 11 applicable checks successful and PR-only
deploy skipped. These are prior-source facts, not approval or CI for this change.

The same-session source-provenance charter review selected a separate parser path
because the historical parser requires shared numeric native caps. Its conditions
were strict finite scope, no executable recipes, genuine source/judge validation,
no historical edits and false launch authority. No separately spawned reviewer,
model override or renewed budget-approval request was used. The accepted SDK
0.147.0 capability memo was not repeated.

| Source identity | SHA256 |
| --- | --- |
| New registration compiler | `58a7b76840a6f8c639c278fa771d2271c3f765946e401f6ea4441f7bff7dab93` |
| New time-budget manifest | `c8f878a9be32a06dc14da5cf9d3b7b77acc841e92db548feee3ebbd49d159ec0` |
| Unchanged historical comparison manifest | `3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1` |
| Unchanged local-source comparison profile | `81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe` |
| Unchanged whole grader TEMPLATE closure | `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce` |

The template closure is not a materialized-grader identity. No old source pin or
CURRENT observer binding changed. Historical compiler/core/Step2/grader/capture
files, paid `RESULT/PARENT/READER`, closed registrations, fixed evidence, original
input hashes and canonical Step0 remain untouched. The CI correction below changes
only the backend test workflow and its CURRENT test fingerprint, not either
historical execution workflow or a study source binding. This study has separate
IDs and does not retroactively relabel any consumed source or prepared artifact.

### Pinned offline proof

Implementation HEAD `10c475a1f50355643a2a9ea937fc235d8ad9b19f`, tree
`af670c70fa90316d486313738dbdd99f9701a852`, was clean before and after the
single `time_budget_registration` invocation. From `batch-runner/`, its command
was the following, with only the private temporary-root locator redacted:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR="$PROJECT5_VALIDATION_ROOT" PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 timeout --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -ra -x --tb=short --color=no -p no:cacheprovider -m "not integration" --basetemp "$PROJECT5_VALIDATION_ROOT/pytest" tests/test_gpt54_time_budget_comparison.py -k time_budget_registration
```

Result: **75 passed in 7.54s; exit 0.** Process timestamps were
2026-10-05T05:42:29Z–2026-10-05T05:42:37Z. The 300-second outer limit and
5-second termination grace bound this software proof only, not an experiment or
CI job. No retry, broader suite, build or prior successful selector ran.

| Private evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Exact command, including final newline | 631 | `37c0ae9db22d135e0b560a3bbcf969349241aea9419c869faf7bcc728992e806` |
| Combined pytest stdout/stderr | 77370 | `221f4966e26ca6aabc17cac8bdcd79ffe688f11813f78269c5025c4606c481cb` |
| Metadata-only receipt | 614 | `042aee2775343f67996853350a55598d5be2c24c699460c78d09dad3b2cd66ab` |

The token-free/offline invocation used umask 077, no-clobber evidence output and
the existing Python 3.10 environment. Tests used public registration/source
metadata and synthetic negative cases, not private originals or model outputs.
Positive compilation used real source pins and the real whole-template helper.
Process/network/auth/provider/model/grader/preparation sentinels stayed untouched.
Tests retained the historical default's exact source refusals and the local-source
profile's unchanged caps and false-launch output. This is software-contract
evidence, not measured deadline enforcement, runtime equivalence, served identity,
wire consumption, model quality, grades or cost.

### CI correction and prior local failure

The leader reviewed all six registration/source/record files at
`c5217b19f79a44787ae08fafecc28dae3ab145b1`, tree
`7e8e5d0d4cd987c16fe84fba924f3aa2e94cce3f`, in
[review5410467314][registration-review]. The original 75-case proof and its
documentation-only post-proof delta were accepted at their software-evidence
scope. That review did not cover the CI correction below. The leader subsequently
reviewed all six correction files at
`369817bf919eb04632ad0af78160d3a33b5d5692`, tree
`0bd9f2bbd1c837994d655ad328857082e4988a38`, and accepted the source correction
with no blocking source finding. Delivery remains subject to the remaining gates.

The leader supplied these failed CI outcomes; no CI logs were fetched or jobs
queried, dispatched or retried for this correction:

- Backend run `37269485572`, job `111633237507`: **1 failed, 13464 passed,
  64 skipped, 46 deselected in 1663.84s**. The only failure was the partition
  node at line 556, where discovery found 12 comparison modules but the guard
  expected 11. The new registration module was absent from both explicit
  workflow command lists.
- Frontend run `37269485559`, validate jobs `111633237134` and `111635977167`,
  attempts 1 and 2: the pinned HF artifact test failed with `TimeoutError` at
  **10060ms** and **10064ms**. The leader's one retry was already consumed.
  These are test-I/O failures, not model errors or a demonstrated latency cause.

Before editing the workflow, the same-session extreme-reasoner charter review
approved moving the existing registration module into the comparison job on
condition that both command lists remain sorted and exactly-once coverage,
marker exclusions, source-SHA checks, permissions, checkout controls, concurrency
and all job timeouts remain intact. It was not an independent review. The private
pre-edit memo is 3126 bytes, SHA256
`bbdafb85dfc7b9ad84e30445ccdd4133ec10ad6634940c6016ec99f9616c56e3`.
The review missed the imported CURRENT whole-workflow digest expectation; the
local failure below exposed that omission.

The correction adds `tests/test_gpt54_time_budget_comparison.py` to the generic
ignore list and comparison job selection, and changes the strict module count
from 11 to 12. No job, marker, workflow timeout, security gate or deployment
workflow is changed. The Node test keeps the same six public URLs at revision
`47aed3c0b13eaa90eb02803bec9d5c75e559f416`, exact lengths/hashes, streaming caps
and all selected manifest/grade/structure assertions. Each request has one
30-second allowance inside a 45-second test bound. Failures report artifact key,
stage, HTTP status when available, elapsed time and a safe error class, without
response bodies, raw causes or signed redirects. Requests and readers are
aborted/released on exit; sibling requests are aborted on rejection. There is no
retry, skip, credential, alternate source, cache fallback or replacement of the
live hash check. The tiny transport-fake cases did not run in the local combined
attempt; their later CI result is recorded below. No dependency was installed;
Node uses the existing owner workspace dependencies through an ignored worktree
link.

The correction was pinned at HEAD `fd910be79992d08e1006622e227e542f8ad0cb78`,
tree `ef8c4b5d05c3c871f8491b0e62d20f1cb7b2458a`, clean before and after the
single combined command. Its result was **1 failed in 0.24s; exit 1**, with
process timestamps 2026-10-05T06:42:49Z–2026-10-05T06:42:50Z. Python 3.10.12
and pytest 9.1.1 stopped at line 391 of
`test_backend_jobs_partition_the_comparison_contracts`: the edited workflow's
SHA256 was `3f7d6bf0112a4d669b4144a60a248d55ecb654d4b883c6e62e7e145d8bdf2f9b`,
but the imported `WORKFLOW_SHA256` still expected
`b617f79a09427f9b877e9fef214bdf2fe96ba817fc8debf5369b4f172640f9da`.
The partition assertions and their nested collect-only checks were not reached.
The shell stopped before Node, so **zero live requests and zero local fake cases
ran**. This is a failed, incomplete validation, not a combined pass or a new
observation about the public artifact service.

The [immutable correction record][ci-correction-record] preserves that attempt's
command display with private locators redacted. The command digest below identifies
the exact private 1033-byte script, including its final newline, not the redacted
display. Its environment was token-free; Python was offline. All original failed
command, log and receipt files remain unchanged.

| CI-correction evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Exact combined command script | 1033 | `a1e5a323abeafc9561fd542d50b6e542d7d840d859db0492d65169aa3f45d364` |
| Combined stdout/stderr | 1802 | `e8e6488b6a603356644ff1845b210de33c948de47d5ce4e7d21e4f28b27de308` |
| Metadata-only receipt | 2393 | `52f82edf52f76cf68a59fa4cad1aab70723ec46197f5b8fb0b1c439f5ef07ee3` |

A separate ordinary correction commit,
`0821ff8d190a7ca5a1d4cf5a0c4710f8a9111b18`, tree
`e2c51219d5e027ea6bf2c1911db4874690d08d22`, updates only the CURRENT
`WORKFLOW_SHA256` in `tests/test_ghcp_vm_gate_contract.py` to those edited workflow
bytes. Its `HISTORICAL_SHA256` and `FOUNDRY_SHA256` and all substantive assertions
remain unchanged. No further local test or remote attempt ran in that correction
turn. Only CHANGELOG and this record changed between that commit and
`369817bf919eb04632ad0af78160d3a33b5d5692`. Relative to the failed
`fd910be79992d08e1006622e227e542f8ad0cb78` proof, the delta includes the test
literal and records; it is not records alone. The separately authorized
continuation below validates the corrected partition without rewriting that
failed attempt.

### One-node Python continuation

The existing worktree was clean at HEAD
`369817bf919eb04632ad0af78160d3a33b5d5692`, tree
`0bd9f2bbd1c837994d655ad328857082e4988a38`, before and after the one-node
continuation. Python 3.10.12 and pytest 9.1.1 reported **1 passed in 15.32s;
exit 0**. Process timestamps were 2026-10-05T07:07:56Z–2026-10-05T07:08:11Z.
The node's own scoped collect-only checks completed as part of that invocation.
No Node command, HF request, registration selector, other suite or build ran.

The token-free/offline command used a 300-second outer bound and 5-second
termination grace. These are software-validation bounds, not a CI timeout or
experiment budget. The following display redacts only the worktree and private
evidence locators; it is not ready to run. The digest identifies the exact private
992-byte script, including its final newline, not this redacted text.

```bash
#!/bin/bash
set -euo pipefail
cd <private-worktree>/batch-runner
test "$(git rev-parse HEAD)" = 369817bf919eb04632ad0af78160d3a33b5d5692
test "$(git rev-parse HEAD^{tree})" = 0bd9f2bbd1c837994d655ad328857082e4988a38
git diff --quiet
git diff --cached --quiet
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR=<private-evidence-root> PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_NO_LAZY_FETCH=1 PYTHONPATH=. HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 timeout --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -ra -x --tb=short --color=no -p no:cacheprovider -m "not integration" --basetemp <private-evidence-root>/pytest tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
```

| Continuation evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Exact private command script | 992 | `1814661791a888232a78504f1c8e85ee8f169fe94b7fa468da388cca84bf1290` |
| Combined pytest stdout/stderr | 552 | `d9488c9f39a5d63d76a1e27fd74d8dd3b774b084a480fd86a4534c1590aef87f` |
| Metadata-only receipt | 2295 | `3aaef590fc6effaea58b81d7895e2a555b285515b50363cea41c108772971976` |

Only CHANGELOG and this current record change after that passing proof. Source,
tests, workflows, manifests and budget/deadline policy remain unchanged.

### Separately supplied successful CI transport evidence

At that same `369817bf919eb04632ad0af78160d3a33b5d5692` HEAD, the leader
read completed [validate run `37274687663`, job `111649027037`][transport-ci],
attempt 1, **SUCCESS**. The retained log is 125654 bytes, SHA256
`dc07a93374aac5c78ad9c9369fb6fd6faee0bac0a2e93dccc1af1cfe3742e13e`.
Its full Node result is **556 passed, 0 failed**. The ten transport-fake cases
passed: retains-exact-bytes; the six failure stages `http_status`,
`content_length`, `response_body`, `stream`, `byte_length` and `sha256`;
request/stream timeout redaction; and parent-abort/no-retry. The live six-artifact
hash/structure test passed in **494.959834ms**.

This is leader-supplied CI evidence, not a locally repeated Node/HF check. No CI
log was fetched or job queried for this continuation. The successful check is
newer live evidence than the two earlier 10-second CI timeouts; it does not
establish why those requests timed out or make the failed local combined command
a pass. The registration proof, failed local attempt, Python continuation and CI
transport result remain separate evidence.

### Remaining work

The leader accepted the source correction at
`369817bf919eb04632ad0af78160d3a33b5d5692`; its Python partition proof is now
complete, and the supplied validate job passed. Remaining CI jobs, the final
records HEAD and delivery still need acceptance. Delivery stays **HOLD**. No
combined local pass or all-checks-success claim is made.

The later execution integration unit remains `time_budget_observation_deadline`.
Its accepted source-analysis memo identifies first generation at V2's first
`voice.next_turn(request)` and Codex's `thread.turn(turn_input)`, one observation
clock across turns/waits/native recovery, and one shared cleanup deadline.
It requires core changes and a prospective whole-grader/source binding; it is
not implemented by changing CI timeouts or refreshing historical pins. That
investigation was not repeated. The owner's design/budget choice remains
delegated, not an open approval question. This registration authorizes no execution.

Dispatch/capture integration and credentialed-CI input authority remain unresolved,
and every launch refusal remains in force. The earlier credentialed workflow
intake proposal remains REJECTED. The old comparison's native-cap requirement is
unchanged; this new study makes no native hard-cap claim. No private original input,
retained input receipt, original archive or consumed prepared artifact was read,
imported, prepared or relabeled.
No model/grader, HF/Azure, CI dispatch/query/retry, Project or merge operation
occurred during this correction or continuation. The original local HF check was
never reached, and no local HF check ran in the continuation.

For the original registration, experiment-design kept the new time-policy
question distinct from historical studies and separated intent from enforcement.
For this continuation, the full skill catalog was inspected once. im-not-ai-en
protected exact scope and refusal conditions while keeping the failed local
attempt, passing continuation and supplied CI evidence distinct. Experiment-design
was not retriggered because no experiment/config policy changed. UI/animation and
experiment-result reporting were not applied; there are no experiment results to
report. The [immutable prior record][prior-record]
retains earlier source/verification evidence. This page replaces stale status
instead of appending prior full task histories.

[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/748#pullrequestreview-5410023630
[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2/tasks/LATEST_TASK_RESULT/README.md#project5-model-free-workflow-profile-handoff--2026-10-05
[registration-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/749#pullrequestreview-5410467314
[ci-correction-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/369817bf919eb04632ad0af78160d3a33b5d5692/tasks/LATEST_TASK_RESULT/README.md#ci-correction-and-incomplete-local-validation
[transport-ci]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37274687663/job/111649027037
