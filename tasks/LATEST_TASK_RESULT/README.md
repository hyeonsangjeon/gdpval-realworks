# Latest task result

## Native capture now matches time-budget grading preparation

The prospective grader preparer now expects `execution_mode="codex_foundry"`
for condition `codex`, matching the accepted native capture. Its previous
expectation was `codex`. V2's exact `agentic_sandbox_v2` mode is unchanged.
The one new offline selector reported **9 passed in 28.73s**, exit **0**;
wrapper **29.206231s**. This is a compatibility correction, not a scoring
change, live result, host-readiness proof or grading authorization.

Only one production literal and its directly coupled synthetic fixture
literal changed. The native producer, controller, canonical captured metadata,
result fingerprint algorithm, registration, core runners, frozen Step8,
rubrics, scoring and workflows are unchanged. No existing observation is
relabeled or given a new fingerprint.

### Reviewed basis and exact source

The one origin/main fetch/check matched accepted main
`4c5a32f7a0347081867fb95f94fc712bc0032ff6`, tree
`6800b87747919ea571c7908ae2b951d15a30fe20`. A fresh clean branch
`b/codex-time-budget-native-grading-mode-20261007` was created at
`/ai-work/copilot/worktrees/codex-time-budget-native-grading-mode-20261007`.
No branch was merged, rebased or copied from PR764/766.

The leader's source-grounded direction identified
`gpt54_time_budget_grading_preparation.py::_result`, blob
`65ebe789033e1400ad3d5d265de7434529be9117`, whose old mode expectation disagreed
with `gpt54_time_budget_codex_observation.py::_capture`. The actual native
producer emits condition `codex` with mode `codex_foundry`. Its unchanged
source SHA256 is
`fbc056b86b9e91cfc50a42f6181eac20de0af23748907687e058742a1c7d4d52`.
The consolidated [grading specification][spec], its overview, the stable
grading-config contract and the producer/preparer contracts were read before
editing. This does not reopen grader policy or claim a new independent review.

Tested commit `f6967c07888208de8b2ad8cc1c2ea84612acbf29`, tree
`fe47d236845882433dc6cb6309f8b8f0beeff849`, contains exactly:

- The single `codex` to `codex_foundry` expected-value change in the preparer.
- The same one-line change in the existing grading-preparation fixture.
- `tests/test_time_budget_native_grading_mode.py`, the new focused selector.

The wrapper verified both one-line replacements byte-for-byte against the
base, parsed the three Python files and checked the clean source/tree before
running pytest. Corrected preparer SHA256 is
`4067abb781faa7bfb18adab54e641fdbeea85eac8174a4210c047cda703b4ffc`;
new test SHA256 is
`21ccd3cd10cf985ee5e8393573610bbe214f23ae738d625f82a21b865ef79458`.
No runtime/compiler registration pin needed changing: the preparer is checked
against its independently reviewed R blob by the existing helper-source guard.
The full registration seal remains
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`;
historical observations retain their originally bound seals.

### What the single proof exercised

The test reuses the existing synthetic R/F/input/Step0 preparation helpers
and the grading fixture's named local Git and effect-denial seams. Source,
registration, original-input, Step0, canonical schema, digest, fingerprint,
deliverable, F-config and publication validators execute on actual temporary
bytes. No source validator or hasher returns a substituted successful verdict.

For native cases, synthetic runner-return data and non-authoritative direction
metadata feed the unchanged production `_capture` function. Its returned
header and fingerprint are serialized unchanged for positive preparation.
No native SDK transport, direction checker, consumer, admission or kernel body
runs in this selector. The control flags are synthetic capture inputs, not
observed host support. Network, provider, grader and admission attempts remain
explicitly forbidden by the reused offline fixture; its effect list stayed
empty. No observation store or consumed-handoff marker was created.

| Case | Exact outcome |
| --- | --- |
| `native_success` | Passed: actual native capture bytes/fingerprint and deliverables survive F-derived preparation unchanged |
| `native_error` | Passed: canonical error is retained with no deliverables, null usage/native counters and unchanged false cleanup/host flags; no success is fabricated |
| `native_legacy_mode` | Passed: coherently hashed mode `codex` is refused with `result execution_mode mismatch` |
| `native_source` | Passed: coherently hashed wrong dataset source is refused with `result source mismatch` |
| `native_observation` | Passed: coherently hashed wrong runtime SHA in the observation is refused with `result observation mismatch` |
| `native_bytes` | Passed: independently expected digest mismatch is refused at the real byte reader |
| `native_fingerprint` | Passed: coherent outer bytes with the wrong fingerprint are refused by the real fingerprint validator |
| `v2_success` | Passed: unchanged `sandbox_v2` / `agentic_sandbox_v2` result is prepared without relabeling |
| `v2_native_mode` | Passed: coherently hashed V2 row carrying `codex_foundry` is refused with `result execution_mode mismatch` |

Every negative case also reached the public preparation refusal and left its
destination and reservation absent. Positive cases retained exact result and
deliverable bytes, the original condition/status, observation/input bindings,
the F-derived grader source and unchanged judge/prompt/rubric/scoring settings.
Launch and execution flags remained false. Original synthetic input, Step0,
reference, handoff and frozen grader bytes stayed unchanged. The older fixture
tests were updated for the intended producer format but not run locally;
their behavioral CI coverage remains separate and pending.

This confirms the corrected boundary on synthetic inputs. The old mismatch
was established from source, not from an additional pre-correction behavioral
run or a historical native failure. No earlier native, V2, directory or grading
selector was rerun, and no proofs are aggregated.

### Command and artifacts

From `batch-runner`, exactly one invocation ran:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_native_grading_mode.py::test_time_budget_native_capture_grading_preparation \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/time-budget-native-grading-mode-proof.1emXK7PW/pytest-tmp \
  --junitxml=/tmp/time-budget-native-grading-mode-proof.1emXK7PW/junit.xml
```

The outer command was:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  /ai-work/venvs/gdpval-realworks-py310/bin/python \
  /tmp/time-budget-native-grading-mode-proof.1emXK7PW/run-proof.py
```

Python `perf_counter` measured the wrapper. The existing offline environment,
explicit timeout plugin, no-`-x` setting and 30-second fixture Git setup bounds
were retained, without retries or a new audit trap. Versions were Python
3.10.12, pytest 9.1.1, pytest-timeout 2.4.0, PyArrow 25.0.1, PyYAML 6.0.3,
jsonschema 4.26.0, openai 2.46.0, httpx 0.28.1 and huggingface-hub 1.24.0.

Artifacts are in `/tmp/time-budget-native-grading-mode-proof.1emXK7PW/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `9bd30e928102fec4e807e2efa66f9b31ff297afb8e1994cec50ab13457655919` |
| `command.json` | `89c221285cd9f73e7cc560d8745c31a515acf421c27fdc0f2984b8d7bd709914` |
| `source.json` | `b077530fa17c641e6b691c8b00f5b054b1b652ccf83fece98b91542d8044b77e` |
| `pytest.log` | `8d91527cbe607599669b27047a4990c1c2857a804dc7b9b9c47cb6b30d093b27` |
| `junit.xml` | `3d9d3473aef12f78acb750759f7daebdcb39f8d94ee08f780e74365613dcad6a` |
| `cases.json` | `60432e2dc77af4e7e56a25d03206a98d4ddba2b851135fc2e440a26ac562d4f4` |
| `outcome.json` | `ed329fac99ace3472c04b4c3080cb34cf606d0eaa1e450c347049ebc1176ef56` |

Only CHANGELOG, this record and direct native README usage change after the
proof. Exact final HEAD/tree and unchanged tested code/test hashes are recorded
in that directory's `handoff.json` after the record-only commit.

### Fixed limits and remaining gates

`experiment-design` holds the existing twenty planned cells, five tasks, ABBA
order, GPT-5.4/direct-v1/xhigh, null native context override, zero configured
request/stream retries, concurrency 1, one external attempt, 1200-second
generation, shared 20-second cleanup and 45-minute execution-job ceiling fixed.
V2's nine-turn/8192 settings are unchanged. Frozen F
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, TEMPLATE
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`, the old
37-pin source profile, rubric bindings and scoring are untouched. No hard money
cap, model-call count, grade or price is inferred.

Final source review and ordinary final-HEAD CI remain required, including the
existing tests that use the corrected fixture. Real use still requires
independent intake of the actual retained result bytes/fingerprint and its
observation, R/F/input and Step0 identities. The grader must be materialized
from frozen F, with its actual config/source hash; this proof is not permission
to run it. A later, separately authorized once-only grading direction/admission
must preserve failed outcomes and permanent claims, without regrade or retry.

PR764 and source-accepted PR766 are untouched; their CI was not queried,
dispatched, retried or awaited. The directory regression's separate negative
finding is not repeated here. Task1-Task4 remain consumed, with their prior
uncertainty/error records unchanged. There was no private HF/input/result read,
Azure, model, grader, readout, native execution, Task5 or replay operation.
The [accepted-base record][prior] preserves earlier proof and review scopes.
`experiment-report-en` and `im-not-ai-en` keep this synthetic compatibility
result separate from those historical observations and pending live gates.

[spec]: ../rebuilding_grading_task/SPEC_GRADING_PIPELINE_V2.md
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/4c5a32f7a0347081867fb95f94fc712bc0032ff6/tasks/LATEST_TASK_RESULT/README.md
