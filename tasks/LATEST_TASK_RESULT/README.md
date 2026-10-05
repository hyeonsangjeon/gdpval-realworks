# Latest task result

## Project5 prospective time-budget comparison registration — 2026-10-05

The separate versioned registration `gpt54_sandboxv2_codex_time_budget_v1` now
compiles offline. It asks which tested GPT-5.4 configuration produces usable,
graded work within the same external generation-time budget. It compares
configuration bundles, not isolated harness effects or equal native compute.
There is no new execution route, preparation or live observation.

Delivery remains **HOLD** for corrected-HEAD review and applicable CI. The five
newly demonstrated CI test-contract failures are repaired in tests only: the
canonical reconstruction accounts for exactly two known inventory additions,
and CURRENT workflow expectations are separate from frozen-fixture expectations.
All five authorized regression nodes passed once at the pinned correction commit.
The registration implementation and original 75-case proof are unchanged. Earlier
local failures, the passing partition continuation and supplied Node CI evidence
remain separate observations; no local Node or HF check was repeated.

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
input hashes and canonical Step0 remain untouched. The earlier CI correction
changed the backend test workflow and its CURRENT test fingerprint, not either
historical execution workflow or a study source binding. The latest repair changes
only tests and completion records; those workflow bytes remain unchanged. This
study has separate IDs and does not retroactively relabel any consumed source or
prepared artifact.

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

### Earlier CI corrections and distinct proof

The leader's six-file [review5410467314][registration-review] covered registration
HEAD `c5217b19f79a44787ae08fafecc28dae3ab145b1`, tree
`7e8e5d0d4cd987c16fe84fba924f3aa2e94cce3f`, and its records-only post-proof
delta. The [immutable correction record][ci-correction-record] retains the
subsequent backend inventory and bounded public-artifact transport repair. That
repair kept sorted exactly-once selection, all workflow security/marker/source-SHA
gates and timeouts, and the six pinned live-artifact hashes and structure checks.
Its pre-edit same-session workflow review missed the imported CURRENT digest;
the private 3126-byte memo has SHA256
`bbdafb85dfc7b9ad84e30445ccdd4133ec10ad6634940c6016ec99f9616c56e3`.

The earlier evidence remains distinct:

- Leader-read backend run `37269485572`, job `111633237507`: **1 failed,
  13464 passed, 64 skipped, 46 deselected in 1663.84s**, at the stale 11-file
  inventory. Validate jobs `111633237134` and `111635977167` in run
  `37269485559`, attempts 1 and 2, failed the pinned HF test at **10060ms** and
  **10064ms**. The owner retry was consumed; no latency cause was established.
- The local combined attempt at `fd910be79992d08e1006622e227e542f8ad0cb78`,
  tree `ef8c4b5d05c3c871f8491b0e62d20f1cb7b2458a`, failed **1 case in 0.24s,
  exit 1**, before partition collection or any Node fake/live request. Commit
  `0821ff8d190a7ca5a1d4cf5a0c4710f8a9111b18`, tree
  `e2c51219d5e027ea6bf2c1911db4874690d08d22`, corrected the CURRENT digest.
  That failed command was not rerun or relabeled as a pass.
- At leader-reviewed `369817bf919eb04632ad0af78160d3a33b5d5692`, tree
  `0bd9f2bbd1c837994d655ad328857082e4988a38`, the separately authorized
  Python partition continuation passed **1 case in 15.32s, exit 0**, including
  its scoped collect-only checks. Only CHANGELOG/LATEST changed from that proof
  to `18cfee10ab3a8de77b06e9d6c6daeca867b9d9c4`. Its full command and scope
  remain in the [immutable continuation record][continuation-record].

| Prior private evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Failed combined command | 1033 | `a1e5a323abeafc9561fd542d50b6e542d7d840d859db0492d65169aa3f45d364` |
| Failed combined log | 1802 | `e8e6488b6a603356644ff1845b210de33c948de47d5ce4e7d21e4f28b27de308` |
| Failed combined receipt | 2393 | `52f82edf52f76cf68a59fa4cad1aab70723ec46197f5b8fb0b1c439f5ef07ee3` |
| One-node continuation command | 992 | `1814661791a888232a78504f1c8e85ee8f169fe94b7fa468da388cca84bf1290` |
| One-node continuation log | 552 | `d9488c9f39a5d63d76a1e27fd74d8dd3b774b084a480fd86a4534c1590aef87f` |
| One-node continuation receipt | 2295 | `3aaef590fc6effaea58b81d7895e2a555b285515b50363cea41c108772971976` |

These command digests identify exact private scripts, not redacted public text.
All earlier command/log/receipt files remain intact.

Separately, at the same `369817bf919eb04632ad0af78160d3a33b5d5692` HEAD,
the leader supplied [validate run `37274687663`, job `111649027037`][transport-ci],
attempt 1: **556 Node cases passed, 0 failed**. The ten transport-fake cases
and live six-artifact hash/structure test passed; the live test took
**494.959834ms**. The 125654-byte CI log has SHA256
`dc07a93374aac5c78ad9c9369fb6fd6faee0bac0a2e93dccc1af1cfe3742e13e`.
The [immutable CI transport record][transport-record] names the fake cases.
This is supplied CI evidence, not a local rerun or an explanation of the earlier
timeouts. It does not turn the failed local combined attempt into a pass.

### Five-failure CI result and pre-edit source-role review

The leader's conditional [review5411311343][conditional-review] covered HEAD
`18cfee10ab3a8de77b06e9d6c6daeca867b9d9c4`, tree
`bcd47929dd12f0be0d9987e7de29001dbe95c470`. It did not waive the subsequent
pytest failure. The leader read [run `37276590021`, job `111654931251`][contract-ci],
attempt 1: **5 failed, 13385 passed, 64 skipped, 46 deselected in 1962.91s**.
The log SHA256 is
`645d67b70bada9c41ad01cc63dbeda48e3d69444220f087fbbc604ecbc69e83e`.
Ten applicable checks passed and deploy skipped at that HEAD; only pytest failed.
No CI query, raw-log retrieval or retry was performed for this repair.

Before editing, the same-session source-provenance charter review classified
the three identities below. This was a read-only role review, not a separately
spawned or independent reviewer. Its decision was APPROVE-WITH-CONDITIONS for a
test-only repair preserving production/workflow/fixture bytes, historical digests
and launch guards.

| Role | Bound source or reconstruction | SHA256 |
| --- | --- | --- |
| CURRENT workflow | Current checkout's unchanged backend workflow | `3f7d6bf0112a4d669b4144a60a248d55ecb654d4b883c6e62e7e145d8bdf2f9b` |
| Frozen pilot fixture workflow | Git blob at `8ac891e3e0e4752fe15a00139a2691ddf9df7dce`, the unchanged `approved_pilot_source` anchor | `b617f79a09427f9b877e9fef214bdf2fe96ba817fc8debf5369b4f172640f9da` |
| Historical pre-readout baseline | Canonical JSON reconstruction, not current workflow bytes | `fd2871a0ec60895d50fd16650a0ddfe47b71634a53fe0164b2fb765ea3319c47` |

The shared-symbol audit found three CURRENT assertions in the existing gate and
partition helpers, and two frozen consumers in native-resume/recovery-feedback
tests. They now use `CURRENT_WORKFLOW_SHA256` and
`FROZEN_PILOT_WORKFLOW_SHA256` respectively. The frozen expectation was confirmed
from its immutable Git blob, never derived from the mutable file under test.
Fixture commits/bytes, positive/stale whole-grader assertions, source inventories,
historical manifests and launch refusals remain unchanged.

The canonical-baseline failure reconstructed
`4f81d97517086195dcf47f92f342ceb93936c8eb4b6bf209d0a7f9f6d82a3acf` because it
retained PR749's two comparison-file-list additions. The corrected test asserts
exactly two filename occurrences and exactly one correctly formed token in each
named command before removing those two literal tokens from a copied workflow.
It then checks the unchanged `fd2871a0…` baseline. It does not strip unrelated
changes, replace the baseline digest or relax current coverage/security checks.

### Five-node corrective proof

The ordinary test-only correction is HEAD
`ca0e72e7d771b4a4851b2c8e15bdbb29c8bc7aed`, tree
`ec441d48e5063a78c14a55ae177c168246c2c67d`. Four test files changed from
the reviewed `18cfee10…` basis; no production, workflow, fixture, manifest, HF-test
or policy bytes changed. The worktree was clean before and after one invocation
of exactly the three failing functions, without `-x`. Python 3.10.12 and pytest
9.1.1 reported **5 passed in 5.72s; exit 0**. Process timestamps were
2026-10-05T08:14:07Z–2026-10-05T08:14:14Z.

All five nodes completed: the budget-readout canonical partition check;
native-resume `[current]` and `[pre_resume]`; and recovery-feedback `[current]`
and `[pre_feedback]`. Verbose output identifies each PASS. Existing process,
network, credential/provider and grader guards remained in place. Only local
source fixtures and synthetic data were used; no private input was read.

The 300-second outer bound and 5-second termination grace apply only to this
software proof. The command below redacts only private worktree/evidence locators
and is not ready to run. Its displayed bytes are not the hashed private script.

```bash
#!/bin/bash
set -euo pipefail
cd <private-worktree>/batch-runner
test "$(git rev-parse HEAD)" = ca0e72e7d771b4a4851b2c8e15bdbb29c8bc7aed
test "$(git rev-parse HEAD^{tree})" = ec441d48e5063a78c14a55ae177c168246c2c67d
test -z "$(git status --porcelain --untracked-files=normal)"
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR=<private-evidence-root> PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_NO_LAZY_FETCH=1 PYTHONPATH=. HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 timeout --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -vv -ra --tb=short --color=no -p no:cacheprovider -m "not integration" --basetemp <private-evidence-root>/pytest tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_budget_readout_partition_preserves_exact_commands_and_guards tests/test_codex_native_resume.py::test_native_resume_active_grader_template_source_bindings tests/test_codex_recovery_feedback.py::test_recovery_feedback_active_grader_template_source_bindings
```

| Corrective evidence | Bytes | SHA256 |
| --- | ---: | --- |
| Exact private command script, including final newline | 1220 | `e0dd4803e00da3556a8a920d03148b3f6de83031fae97f23e694cdf7474086fe` |
| Combined pytest stdout/stderr | 1054 | `3fd03641afe7f3927668f305038e21c3d2bae435f3af33551e64ec22d6549a15` |
| Metadata-only receipt | 2290 | `ff7a57681a1561b96833ba961599703ee40403e5bafcb5934986fce47f89530f` |

Evidence was retained in a fresh private directory; log capture used umask 077
and no-clobber creation. No earlier evidence was overwritten. No prior successful selector,
Node/HF check, broader suite or CI job was repeated. Only CHANGELOG and this
single current task record change after the five-node proof.

### Remaining work

The new test-only correction and records need final fixed-HEAD review and
applicable CI acceptance. Delivery stays **HOLD**. The five-node local pass does
not rewrite the supplied failing CI result or establish all-checks success.

The later execution integration unit remains `time_budget_observation_deadline`.
Its accepted source-analysis memo identifies first generation at V2's first
`voice.next_turn(request)` and Codex's `thread.turn(turn_input)`, one observation
clock across turns/waits/native recovery, and one shared cleanup deadline.
It requires core changes and the accepted two-root source binding in the same
coherent deadline patch: frozen F at `882868cc…`/tree `45d024f1…` retains TEMPLATE
`37e1791d…`, independently of a future reviewed runtime R. Neither that binding
nor deadline integration is implemented here. The prior investigation was not
repeated. The owner's design/budget choice remains delegated, not an open approval
question. This registration authorizes no execution.

Dispatch/capture integration and credentialed-CI input authority remain unresolved,
and every launch refusal remains in force. The earlier credentialed workflow
intake proposal remains REJECTED. The old comparison's native-cap requirement is
unchanged; this new study makes no native hard-cap claim. No private original input,
retained input receipt, original archive or consumed prepared artifact was read,
imported, prepared or relabeled.
No model/grader, HF/Azure, CI dispatch/query/retry, Project or merge operation
occurred during this test-contract repair. The original local HF check was never
reached, and no local HF check ran in either Python-only follow-up.

For the original registration, experiment-design kept the new time-policy
question distinct from historical studies and separated intent from enforcement.
For this repair, the full skill catalog was inspected once. im-not-ai-en
protected exact scope, digests, commands and refusal conditions while keeping the
failed local attempt, passing proofs and supplied CI evidence distinct. Experiment-design
was not retriggered because no experiment/config policy changed. UI/animation and
experiment-result reporting were not applied; there are no experiment results to
report. The [immutable prior record][prior-record]
retains earlier source/verification evidence. This page replaces stale status
instead of appending prior full task histories.

[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/748#pullrequestreview-5410023630
[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2/tasks/LATEST_TASK_RESULT/README.md#project5-model-free-workflow-profile-handoff--2026-10-05
[registration-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/749#pullrequestreview-5410467314
[ci-correction-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/369817bf919eb04632ad0af78160d3a33b5d5692/tasks/LATEST_TASK_RESULT/README.md#ci-correction-and-incomplete-local-validation
[continuation-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/18cfee10ab3a8de77b06e9d6c6daeca867b9d9c4/tasks/LATEST_TASK_RESULT/README.md#one-node-python-continuation
[transport-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/18cfee10ab3a8de77b06e9d6c6daeca867b9d9c4/tasks/LATEST_TASK_RESULT/README.md#separately-supplied-successful-ci-transport-evidence
[transport-ci]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37274687663/job/111649027037
[conditional-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/749#pullrequestreview-5411311343
[contract-ci]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37276590021/job/111654931251
