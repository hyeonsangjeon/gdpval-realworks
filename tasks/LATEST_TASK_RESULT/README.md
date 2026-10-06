# Latest task result

## First directed V2 observation entrypoint

The first-cell callable, direction checker, V2 dependency binding and canonical
result capture are implemented. Delivery remains pending review and CI. The one
local selector reported **32 passed, 1 failed in 81.67s**, exit 1. A subsequent
test-fixture correction was not rerun; this is not a 33-pass result or a live run.

The new worktree/branch is
`b/codex-time-budget-first-v2-entrypoint-20261006`, based on accepted
`c051207c4033c97c4455215b1381aa88d25aef65`, tree
`da2f27bec5785db571ffd8caa20ddf2bd5a12ede`. The leader-supplied reviewed basis is
integrated `2f7a7861a10b75946856c16d7fa5ffbef2b9b050`, review `5421981543`, with
11 applicable checks passed and deploy skipped. That approval does not cover
this new patch. Previous worktrees, the user checkout and historical artifacts
were preserved; the old consumer branch was neither changed nor pushed.

### Implemented scope

`batch-runner/gpt54_time_budget_v2_observation.py` adds
`run_first_v2_observation` and a CLI for exactly
`gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 /
`02aa1805-c658-4069-8a6a-02dec146063a`. All other cells refuse. The separate
20-observation registration, five tasks, ABBA order, two repeats, concurrency 1,
single external attempt, GPT-5.4/direct-v1/xhigh and V2-specific 9-turn/8192-output
settings are unchanged. No replay, resume, outer retry or Codex Step0 read is added.

The concrete `require_execution_direction(ObservationExecutionBinding)` checker
matches a strict direction file against an independent expected digest, exact
observation/preparation/R/F/host identities and canonical paths. Its finite
window authorizes admission, not a renewed generation clock. A direction file
cannot provide its own trusted digest. Missing, stale, malformed, mismatched,
extra-field and consumed state refuses before provider/admission effects.
The existing permanent handoff consumption claim makes that exact direction
nonrenewable; changing the result destination does not grant another attempt.

The adapter uses the real `build_runner_factory`, the registered same-host
`AgenticV2FixtureBackend`, `AzureFoundryVoice` and typed Azure inference client.
The backend's limited tools are not a microVM. Client creation/authentication
waits run inside supervised generation, and client closure uses the existing
cleanup callbacks. The same `TimeBudgetObservation` reaches `observation_for`;
its 1200-second generation and shared 20-second cleanup semantics are unchanged.
No credential/resource/model/region/quota change, provider stub, arbitrary import,
environment bypass, new service or workflow entrypoint is introduced.

One necessary input seam opts prospective validation into synchronous parquet
reads. The legacy omitted/default reader and selected-row validation remain
intact. Only the reader and compiler's three prospective digest entries advance.
Directly coupled CURRENT refusal inventories now name the changed reader;
historical profiles/positive source roots, workflow bytes, core, grader algorithm,
frozen F and launch flags remain unchanged. F is still
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, TEMPLATE
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.

### Output and callable boundary

The independently named new destination receives:

```text
<destination>.time-budget-result-reserved.json
<destination>.time-budget-v2-work/          # backend-owned work, never adopted
<destination>/upload/deliverable_files/<task-id>/<verified-relative-file>
<destination>/step2_inference_results.json  # final canonical publication
```

The canonical result fingerprint covers one actual returned terminal outcome,
its control/admission/cleanup state, preparation/R/F/input/config identities and
usage availability. Cached/reasoning tokens remain subsets. Missing counters,
native model attempts, repeated requests and written tokens are unavailable,
not manufactured counts or shared hard caps. No money or remote billing bound
is claimed. Errors and missing outputs remain terminal error rows; refusal
before admission cannot fabricate a study row. Interrupted publication retains
the consumed claim and any partial/reservation state, without a success marker.

The [usage section](../../batch-runner/README.md) gives the complete command and
strict direction schema. In short, call
`python batch-runner/gpt54_time_budget_v2_observation.py` with the fixed run/task
and these independently supplied values: R root/commit/tree; F root/commit;
input-registration root/commit/path; registration and input-binding SHA256;
preparation directory/digest/size; original parquet and reference-root locators;
private observation-state directory; new destination; direction file plus its
independent SHA256; and the intended host digest. The host metadata API exposes
a boot/namespace/user/CI-instance digest, not an ownership verdict. The approved
OIDC connection must already match the registered account/project/direct route.

No checker or factory stub remains in this callable. Before the first real
observation it still needs delivered/reviewed source and an independently issued
direction with genuine verified input/preparation and actual host values. Host
kernel admission remains mandatory. A library leaving native threads active
still causes refusal; synchronous parser reads do not establish host support.
The command does not grade or upload. Its result can feed the accepted F-derived
grading-preparation API, with separate independent result/input identities and
separate live grading authority.

### One bounded local proof

Tested implementation: `a1380d827814699265e1406cc8e84b0f6187b87a`, tree
`28cd1c7dfb471848dd4ce7b91eed8894da4b7e17`. The command file first checked that
exact HEAD/tree and a clean worktree, then ran this invocation from `batch-runner`:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -o addopts= -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --basetemp=/tmp/time-budget-first-v2-proof.rMkHxH/pytest-tmp \
  --junitxml=/tmp/time-budget-first-v2-proof.rMkHxH/junit.xml \
  tests/test_time_budget_first_v2_observation.py -k time_budget_first_v2_entrypoint
```

All 33 nodes completed: **32 passed, 1 failed in 81.67s**, exit 1, no `-x`.
The five synthetic factory → canonical result → genuine F-derived grading
preparation roundtrips passed for success, failed output, missing usage, wrong
served model and timeout. The 24 pre-admission refusal cases, two final-reread /
partial-publication cases and synchronous/default-reader case also passed.
These use real temporary Git/source/input validators, a controlled kernel/clock
and a transport substituted at the normal Azure client seam. No successful
direction/source/input/hasher verdict was mocked. No live provider or grader was called.

The failed node was
`tests/test_time_budget_first_v2_observation.py::test_time_budget_first_v2_entrypoint_defaults_and_source_roles`.
Its full legacy-positive compile used the synthetic input-only profile and
correctly raised `DispatchPlanRefused: comparison refused: shared_controls,
conditions`. Correction `9cf4429c377449e98b2c595703d873622c3390dc`, tree
`db32151d10e0c5d777749b604fbc697aacc1c955`, changes only that fixture selection
to the untouched, independently anchored F root. Production, README and pins
retain the tested bytes. The corrected node was **not rerun locally** and still
needs CI acceptance. Nothing turns the original invocation into a pass.

Artifacts remain at `/tmp/time-budget-first-v2-proof.rMkHxH/`; the log and JUnit
retain all individual node outcomes. SHA256 values:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `3bd8ac05aede7de305beabe9c89d3904447acda1473e0f03b6624cd94a1bea68` |
| `output.log` | `9b5d20547fafc3e1ac57fc985f741402db7b78a8368220bdb0e047aea9b8665c` |
| `junit.xml` | `cd7e4485dae88af368191e4198e76f28ea94c9059752bc01efaf7e71c28a49c7` |
| `receipt.json` | `9967628a0841749b8982d5aab4ad912ea670d85f70b6a9089113fa196e45ba6e` |
| `pre-edit-review.md` | `ac400d50ae6c190cf1af1635b0e870459eeb4258038875daf89e3e320153f7aa` |

The command digest identifies the complete retained file, including its source
guards, not the shorter displayed invocation or any redacted command text.
The post-proof delta is the one test-only correction plus CHANGELOG and LATEST.
No successful subset, prior selector, broad suite, Node/HF check or real platform
probe was repeated. No CI query, retry, dispatch, polling or waiting occurred.

### Reviewed basis, separate evidence and remaining gates

The full skill catalog was inspected once. `experiment-design` applied only to
the fixed configuration mapping; it did not reopen the study or delegated budget.
The grading-engineer, extreme-reasoner/source-provenance and architecture charters
and consolidated grading specification informed the pre-edit same-session memo.
That is the primary worker's charter application, not independent owner approval.
`im-not-ai-en` applies to these changed English passages with source identities,
counts, failures, links and uncertainty protected. No experiment-report,
readiness, UI or animation detour was used.

The [consumer record][consumer] retains its separate 53 passed / 226 deselected /
76.10s proof at `b9daec496548293d7e0f316fd6d18f0c16b6ae2e`. The
[grading record][grading] retains 41 passed / 95.22s at
`3e81b74be73ff1a7a925d7780c9fbd9b896d7d6d` and the separate eight passed / 31.43s
terminal correction at `942fb0680b63ec80b3d5f924609de878ef7751d1`.
[Earlier deadline/ownership evidence][deadline], including the NAS real-kernel
admission refusal, remains separate. The leader-supplied positive model-free CI
host outcomes for [PR751's source/job][host751] (tree `2d967786`) and
[PR752's source/job][host752] (tree `ae71f34e`, source `55ee47386c97058863a5ceefb6c1e358f7f41940`)
are not current-host approval, study observations or live authorization.

Remaining gates: full new-HEAD source/records review, applicable CI including the
unrerun fixture correction, genuine independent input/preparation/source/host
values and a source-bound execution direction. The existing connection and
owned-host checks must pass on that actual host. Live grading stays separate.
No paid observation, private original/result/receipt or consumed-artifact read,
private preparation, model/grader/HF/Azure operation, Project mutation, merge or
policy/launch-flag change occurred in this task. No backend-cancellation or
billing guarantee follows from these software fixtures.

[consumer]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a9dd6d12ee52344d3f0e329d2d355d429a175df8/tasks/LATEST_TASK_RESULT/README.md
[grading]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/896a27fffbba23f2d1a1b75fa9fd61c0d83170ed/tasks/LATEST_TASK_RESULT/README.md
[deadline]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/50d7c11a027396d838a838ce2168f266774df61a/tasks/LATEST_TASK_RESULT/README.md
[host751]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37331226376/job/111834532570
[host752]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37345048041/job/111881404006
