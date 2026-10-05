# Latest task result

## Single-observation handoff consumer — 2026-10-05

`gpt54_time_budget_comparison.consume_observation_handoff` now validates one
prepared observation and binds its verified arguments and the same
`TimeBudgetObservation` to the existing V2 or Codex factory. The sole offline
selector reported **53 passed, 226 deselected in 76.10s**, exit 0. All selected
nodes completed; none failed, timed out or skipped. No test was rerun.

The API defaults to refusal without an independent execution-direction checker.
No production checker, workflow/CLI entrypoint or live direction is installed.
Preparation remains evidence, not launch authority. Final-HEAD owner review and
applicable CI acceptance remain pending.

### Scope, effects and output

The caller supplies the compiled time-budget plan, one `run_id`/`task_id`, a
preparation directory and its independent expected `sha256`/`size`, explicit
runtime R and frozen F roots/full-commit anchors, and an explicit
input-registration path/root/full-commit anchor. Existing local parquet and
reference bytes are reverified. Codex also requires canonical Step0; V2 refuses
it without reading it. There is no HEAD, marker or environment fallback for
review authority.

The shared `_observation_handoff_data` helper reconstructs the preparer's exact
configuration, model-safe task and selected reference bytes through the existing
source/input validators. The consumer checks the reservation-to-marker binding,
exact member/hash/size set, condition/template/task/reference bindings and the
running process's core bytes against R. Coherent replacement, aliases, extra or
missing members, changed sources/inputs, and reused/partial state refuse before
provider, admission or output effects. Held-directory/member/source/input
identities are reread after direction checking and before effects.

`require_execution_direction(ObservationExecutionBinding)` is a trusted caller
dependency, not a marker-selected function. Its immutable binding contains the
preparation digest/size, canonical observation identity, F commit/tree/template
identity and canonical preparation/admission paths. The checker must validate
these against a separate reviewed source-bound execution direction and either
return `None` or raise. Boolean approval values are refused. Checked preparation
and execution permission remain distinct.

After validation, direction checking and final rereads:

1. A permanent no-clobber sibling
   `<preparation_directory>.time-budget-consumed.json` binds the preparation
   identity and observation, with state
   `consumed_not_completion_or_launch_authority`. It is never removed, adopted,
   repaired or retried, including after partial or unsupported startup.
2. One real `TimeBudgetObservation` reserves admission before factories. V2's
   existing `build_runner_factory` receives that same control through
   `observation_for`, along with its configuration, `TaskToRun` and verified
   references. `CodexAgentRunner` receives it through `observation_control`,
   along with the prepared native arguments and a provider whose declared
   model/provider/effort/context/retry fields must match the configuration.
3. The existing runner owns claim, first generation start and cleanup. Startup
   failure uses that control's existing bounded cleanup. No outer retry/resume
   or parallel observation is added.

The return value is the existing runner result dictionary plus
`handoff_preparation_identity` and `time_budget_observation`. The preparer's
configuration/task/reference/marker output shape is unchanged. Factories are
statically selected; untrusted marker text cannot name an import. No provider,
backend or execution direction is selected by default.

### Source identities and pre-edit review

- Accepted main: `a5a04701fed3067b56bd80af424824c447f3075e`, tree
  `d36a356b0950bd44b0b789dfebf725035601d259`.
- Delivered PR752 basis supplied by the leader: reviewed
  `bba2c6dc3a026ec744f12089ab6f037cfe15ee5e`, owner review `5418852580`, all
  11 applicable checks passed and PR-only deploy skipped.
- Tested implementation: `b9daec496548293d7e0f316fd6d18f0c16b6ae2e`, tree
  `e5a68af749c699ed5b5d6971cc0bd491dc73b3e8`.
- Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
  `45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with genuine TEMPLATE
  `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
  No materialized-grader identity or execution is claimed.

Before edits, the primary worker applied the same-session architecture,
source-provenance and grading charters and read the consolidated grading
specification. The recorded decision was APPROVE-WITH-CONDITIONS: independently
anchored source/input/preparation identities, strict validation before effects,
an external trusted direction dependency, static factory selection, the same
control, unchanged legacy gates and synthetic offline proof. This was not
independent owner approval. The pre-edit review's exact identity is below.

The directly coupled CURRENT consumers were audited once. Only the two existing
prospective helper digest fields advance: `source_basis.registration_compiler`
and the helper's `source_pins` entry. The new helper SHA256 is
`d0f13ac8d3e847510ca535eff6ab50dea71ef3c23d33d6249eb19016887208ca`;
the prospective inventory remains 42. Historical manifests and the 37-source
profile, frozen F, core/runtime/ownership/finalization, workflows, grader
algorithm and paid evidence are unchanged.

The fixed study remains five tasks, four runs in ABBA order, two repeats,
concurrency 1 and at most 20 observations, with GPT-5.4/direct-v1/xhigh and the
existing 1200/20 policy. There is no external replay/resume/retry, shared native
request/token cap or money-cap claim. Closed studies are not reopened or pooled.
Every existing launch refusal and execution-enable flag remains closed.

### Single offline proof

The clean implementation HEAD above was tested once with Python 3.10.12 and
pytest 9.1.1, token-free/offline, under a 300-second outer bound plus 5-second
termination grace, without `-x`. Result: **53 passed, 226 deselected in 76.10s
(0:01:16)**, exit 0. The log and JUnit preserve every completed node identity.

This is the redacted display of the sole invocation. Only absolute local paths
are redacted. The command digest below identifies the exact private 873-byte
script, including its paths and log capture, not this display.

```bash
#!/bin/bash
set -o pipefail
cd "<worktree>/batch-runner" || exit 90
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH="<py310-bin>:/usr/bin:/bin" \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  "<py310-bin>/python" -m pytest \
  -o addopts= -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --basetemp="<proof>/pytest-tmp" \
  --junitxml="<proof>/junit.xml" \
  tests/test_gpt54_time_budget_comparison.py -k time_budget_handoff_consumer \
  2>&1 | tee "<proof>/pytest.log"
```

| Preserved file | Bytes | SHA256 |
| --- | ---: | --- |
| `command.sh` | 873 | `dde2f2ff46a355edc21836bf74e0b7b550bfd449fa0ba01759c264290d1429f0` |
| `pytest.log` | 7460 | `5ec082f6e8f495258227c47113ca0977481fe782d2f1d502fec7ea74e7bf5be3` |
| `junit.xml` | 8552 | `188b388a775da45263cc1ef6caf3e2062ca62d9fd3b804e64979f6f389df46be` |
| `pre-edit-review.md` | 4580 | `f29a633121d2007f54af11be8ea97c7f18ff6ca72082a0357fc35c989c03c8f2` |

The selector covered 31 validation/tamper/coherent-replacement cases, 6 final
reread races, 8 independent/default-deny direction cases, 4 real-factory
positives (both owners, with and without references), 2 failed-start/reuse
cases and 2 condition-specific dependency refusals. Failed validation produced
no provider, admission or output effects.

Temporary Git/source identities and input declarations were genuine and
explicitly synthetic; no successful source or handoff validator was mocked.
Controlled kernel adapters, fake clocks, a scripted V2 backend/voice and a
Codex fake native transport supplied the effectful seams. The actual V2
factory/runner and Codex constructor/run wrapper received the same real control
and verified arguments. The controlled Codex version hook is not evidence of a
live installed runtime. No real provider/model call or local platform probe
occurred. This is software proof, not live deadline enforcement, remote
cancellation, billing evidence or new host support.

### Prior evidence, post-proof delta and remaining gates

The [immutable PR752 record] retains its failed local 38-pass/9-fail proof,
corrected-HEAD 1410-pass CI result and separate positive model-free host receipt.
The [earlier platform record] retains the prior software proofs and distinct NAS
refusal. Those observations remain separate; none covers this new source/host
or supplies study execution authority. No earlier selector was rerun and no
prior private artifact or receipt was read.

The post-proof repository delta is exactly `CHANGELOG.md` and
`tasks/LATEST_TASK_RESULT/README.md`. The consumer, tests, prospective manifest
and usage README all remain byte-identical to the tested implementation.
Final-HEAD owner review and applicable CI are still required; no CI status was
queried, polled, dispatched or rerun in this task.

The single remaining callable/authority boundary is a trusted installation of
`require_execution_direction(ObservationExecutionBinding)` with the matching
provider/backend dependencies on a separately reviewed source-bound host. It
must bind the exact preparation/observation/R/F identities and canonical
preparation/admission paths to the independent execution direction. This PR
does not install that checker or open a workflow/CLI live path. Exact-source
host support, verified credentialed originals, provider identity, live
capture and eventual F-derived grading remain distinct gates; no spending
approval question is reopened.

The skill catalog was inspected once. `experiment-design` preserved the fixed
controls while checking configuration mapping; it did not reopen study design.
`im-not-ai-en` was used for one bounded changed-passage fidelity check of these
English records; it passed with no failures or warnings. The check preserved
the protected counts, identities, links and refusal language. No unrelated
skill was applied. No broad suite, prior
handoff/platform/ownership selector, Node/HF/build, private original/receipt/
consumed-artifact access, real preparation, provider/model/grader/Azure call,
Project edit or merge occurred.

[immutable PR752 record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/bba2c6dc3a026ec744f12089ab6f037cfe15ee5e/tasks/LATEST_TASK_RESULT/README.md
[earlier platform record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/e0e270b67b3c7f63b8f94f945c4839b778c7572b/tasks/LATEST_TASK_RESULT/README.md
