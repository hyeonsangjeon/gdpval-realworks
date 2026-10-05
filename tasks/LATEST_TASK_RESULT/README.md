# Latest task result

## Project5 prospective time-budget comparison registration — 2026-10-05

The separate versioned registration `gpt54_sandboxv2_codex_time_budget_v1` now
compiles offline. It asks which tested GPT-5.4 configuration produces usable,
graded work within the same external generation-time budget. It compares
configuration bundles, not isolated harness effects or equal native compute.
There is no new execution route, preparation or live observation.

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
CURRENT observer binding changed. Historical compiler/core/Step2/grader/workflow/capture
files, paid `RESULT/PARENT/READER`, closed registrations, fixed evidence, original
input hashes and canonical Step0 remain untouched. This study has separate IDs
and does not retroactively relabel any consumed source or prepared artifact.

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

### Remaining work

Only `batch-runner/README.md`, `CHANGELOG.md` and this single current task record
change after the proof. Final fixed-HEAD review, applicable CI and leader
acceptance remain pending. The single next execution integration unit is
`time_budget_observation_deadline`: bind the existing host deadline to these
observation identities, including all waits/native recovery and separately
recorded cleanup. That unit requires subsequent source review and direction;
the owner's design/budget choice is already delegated, not an open approval
question. This registration authorizes no execution.

Dispatch/capture integration and credentialed-CI input authority remain unresolved,
and every launch refusal remains in force. The earlier credentialed workflow
intake proposal remains REJECTED. The old comparison's native-cap requirement is
unchanged; this new study makes no native hard-cap claim. No private original input,
retained input receipt, original archive or consumed prepared artifact was read,
imported, prepared or relabeled.
No model/grader, HF/Azure, CI dispatch/query or Project operation occurred.

experiment-design kept the new time-policy question distinct from historical
studies and separated intent from enforcement. im-not-ai-en protected exact
scope, evidence, uncertainty and refusal conditions in these bounded English
records. UI/animation and experiment-result-reporting skills were not applied;
there are no experiment results to report. The [immutable prior record][prior-record]
retains earlier source/verification evidence. This page replaces stale status
instead of appending prior full task histories.

[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/748#pullrequestreview-5410023630
[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2/tasks/LATEST_TASK_RESULT/README.md#project5-model-free-workflow-profile-handoff--2026-10-05
