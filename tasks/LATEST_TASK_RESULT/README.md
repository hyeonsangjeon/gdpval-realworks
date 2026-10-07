# Latest task result

## Explicit native-r1 task selection; targeted proof is blocked

The controller now derives one cell from `request.cell.task_id` and the
accepted compiled registration. It remains restricted to
`gpt54_time_budget_v1_codex_r1` / `codex` / integer repeat 1 and the existing
five tasks. Task2, `0112fc9b-c3b2-4084-8993-5a4abb1f54f1`, is the intended
next task, not another attempt at consumed Task1. This is implementation
only; it supplies no live request or permission to advance ABBA order.

The one new offline selector reported **5 failed, 8 passed in 99.94s**, exit
1. Its wrapper took **100.917453s**. All 13 cases collected. The first
failure was the new test's `configuration["task_ids"]` lookup at
`batch-runner/tests/test_time_budget_first_codex_ci.py:867`, raising
`KeyError: 'task_ids'`. All five failures occurred at that same operation,
after synthetic Task2 input/whole-Step0 preparation and permanent private
CAS claim, before the native callable, capture or retention assertions.

That assertion copied the V2 configuration shape. The unchanged native
producer uses `configuration.data.filter.task_ids` and
`configuration.execution`. This is a test-body error, not a zero-body
collection failure or evidence of a native runtime defect. No correction,
retry or further test invocation followed. The draft remains blocked.

## Source and change boundaries

| Identity | Exact value |
| --- | --- |
| Accepted base, verified by the one origin/main check | `8851fd3cda4aa55becdbface579117f3b16c866f` |
| Accepted tree | `a1fbf675eeebe13777ed2a281502f27d4748b8f7` |
| Tested implementation/test commit | `48bf0873d44b99c7364bbdcce43478826aa3466e` |
| Tested tree | `033eb0c97f11f15cde7a97a1b22f1e28fe8577c9` |
| Unchanged full registration seal | `3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f` |
| Final documentation-bearing HEAD/tree | Recorded after the docs-only commit in `/tmp/native-r1-task-selection-proof.tGICRM/handoff.json` |

The source commit changes only the native controller, its manual workflow's
early task-membership check, and one new parametrized test definition plus
its import. Every existing test/fixture definition is byte-identical. The
native `execute` body and shared safe-event formatter are unchanged. After
the proof, only CHANGELOG, this record and the direct README usage/evidence
section change. Their final commit is not represented as another test run.

The selected cell is carried through original-input and full Step0 checks,
preparation/reconstruction/direction, task-specific private claim and output
paths, canonical task/file/source validation and retention. Both retention
and CLI completion verification pass the independently validated request
cell to the envelope validator; they do not infer it from a received
envelope. This is the implemented source scope, not a claim that every path
completed in this failed proof.

Legacy `CELL`, `PREFIX`, `CLAIM` and `MANIFEST` retain Task1's exact values.
The default native envelope check and unchanged uncertainty reader remain
Task1-only. Namespace paths contain the selected task, not R, so a later
source revision cannot obtain another claim under an occupied Task1 prefix.
In the offline occupied-prefix case, the private-CAS transport made only
metadata/object-existence calls, with no old body read, adoption or new CAS.

The workflow retains its name, inputs, fixed study/run/condition/repeat,
source/owner/ref/attempt guards, paths, permissions, secret steps, concurrency
group and ceilings. No shared controller, native callable, core, compiler,
registration, frozen F, historical data, model, prompt or provider setting
changes. Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`. The twenty-cell registration,
GPT-5.4/direct-v1/xhigh, null context override, provider request/stream
retries 0, one external attempt, concurrency 1, nonrenewable 1200-second
generation, shared 20-second cleanup and 45-minute job ceiling remain fixed.
None is a money hard cap.

## One bounded offline invocation

The outer command was:

```sh
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-r1-task-selection-proof.tGICRM/run-proof.py
```

From this worktree's `batch-runner` directory it invoked exactly:

```sh
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout tests/test_time_budget_first_codex_ci.py::test_time_budget_native_registered_task_selection -m 'not integration' --tb=short -ra --basetemp=/tmp/native-r1-task-selection-proof.tGICRM/pytest-tmp --junitxml=/tmp/native-r1-task-selection-proof.tGICRM/junit.xml
```

Python was 3.10.12, pytest 9.1.1, pytest-timeout 2.4.0, huggingface-hub
1.24.0 and the pinned native SDK/CLI packages 0.147.0. No package was
installed or upgraded. The wrapper used Python timing, no `-x`, the one
300s+5s ceiling, 30s Git bounds and the existing named fixture Git/Bash/auth
allowances. AST checks verified parameter bindings and unchanged existing
definitions before pytest. The parsed registration seal and exact workflow
delta also passed their static checks. No separate collection/body rerun,
old selector, full suite or real NAS kernel probe ran.

| Cases | Actual outcome and boundary |
| --- | --- |
| `task2`, `direction_task`, `result_task`, `result_source`, `result_file` | Failed at the common test-only configuration lookup. Intended execution/direction/result/retention assertions were not reached. |
| `unregistered_task`, `run`, `condition`, `repeat`, `namespace`, `source` | Passed early workflow/controller refusals. Namespace coverage also refused cross-task control/path writes before transport. |
| `old_task1_claim` | Passed occupied synthetic Task1-prefix refusal with unchanged objects/writers and no old body read, adoption or new CAS. |
| `legacy_task1_readout` | Passed the default Task1 envelope binding and pure synthetic uncertainty-manifest projection. No actual readout or private fetch occurred. |

The fixtures use real source/input/schema/namespace validators and synthetic
HTTP/private-CAS data. Existing synthetic auth/RPC and kernel seams were
available, but the five failing cases stopped before their native
execution. This is not a real Linux ownership, provider, model, cleanup,
grading or hosted-readiness proof. It is not a thirteen-case pass or a
successful Task2 roundtrip.

All proof artifacts are retained in
`/tmp/native-r1-task-selection-proof.tGICRM/`. `first-failure.json` names the
first operation and unreached boundaries. `cases.json` preserves all outcomes;
the log/JUnit files preserve the five identical failures.

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `17d559dc6ab6c00a23f6966b162b35dc1018f7c45fb1457ba907dc3bed6e5362` |
| `command.json` | `ac1033e2667713cfc16acd5eb15539032bca0c59a44243aa0fbce64d1279f4ab` |
| `source.json` | `e44c36f93c6f73c8c84b1e105b05d7d10394a903b46050b1c4c383953f0f93e9` |
| `pytest.log` | `edf75e3af0389b06b67a26c606ec0864b5931327cd2a73b405cfdc729a4038f9` |
| `junit.xml` | `54e22d8f370ad08b3fb333ea25397d03afde25af03742fcfcb450dace28e57c4` |
| `cases.json` | `b8d1707ee18fa214173f2839cdb271722d47d7a5ecb940e5eee14a2759736cd7` |
| `outcome.json` | `cf7e25e53c4401705d4a00547c9c68688d3281d05499a933a56a176d95008ad8` |

## Historical evidence remains separate

Native r1/Task1 remains consumed and uncertain. The leader verified native
run `37574558224`, run number 3, attempt 1, job `112640438630`, at original R
`b0bba8c71369605fd4261c59259e3cc3924de981`. Execute returned 2; retention was
acknowledged. Its immutable claim is
`4ca4fd9c86fe1253059fffc66f6e4397c34c3c4e`, output
`d443e8045f58b6f7b4b35ed7f1888182b62296e0`, request size 2369 bytes / SHA256
`c78a581c482baf495b09efad70899e0067293752f3cc7320f54f2af0079fa062`.
No claim, output or preparation from that observation was accessed or adopted.

Leader-verified readout `37585054563`, run number 4, attempt 1, artifact
`11466485746`, retains exactly `observation_callable` / `validation_refused`
/ `execution_refused_or_uncertain`. It identifies no first historical guard.
The manifest identity, 1096 bytes / SHA256
`458db9999f436360072181f5e1907b15c4c9f2c1ed018829137920fd495ade5e`, is observed,
not independently expected. Model calls, cost and cleanup remain unknown,
not zero. This failed test does not narrow that historical classification.

The earlier [one-case native boundary proof][boundary] remains 1 passed,
1 warning in 21.97s, wrapper 22.641730s, without reproducing a production
defect. The earlier eight-case wiring proof, two-case environment correction
and eleven-case safe-event proof remain separate in the [accepted usage
record][prior-usage]. None was rerun or added to this invocation's eight
passes. The [previous accepted-source record][prior-record] preserves its
review/integration provenance. PR771 at
`b66a2a5f8329a362ccf48ea25469764e8a9325c5` and its worktree are untouched;
its combined CI was not queried. All five V2 r1 cells also remain consumed.

## Review and remaining gates

The leader read the relevant controller/callable/namespace/claim/retention
paths and approved this bounded selection design. The required new workflow
review invocation failed before execution on the unavailable legacy Opus
preference; it was not an endorsement or spawned review and was not retried.
The agent catalog was read once. Experiment-design confirms that this exposes
already registered cells without adding study conditions. Reporting and
English copyediting keep the failed selector, its eight passes and historical
uncertainty separate; no new design or reviewer loop was introduced.

The test's native configuration assertions need a separately authorized
correction before the unreached Task2 path can be proven. Fixed-HEAD source
review, final CI, leader-owned integration, actual host, source, original-input,
whole-Step0 and auth checks, an independently expected private parent and fresh
task-specific CAS, and a separately issued live authorization remain gates.
No actual Task2, readout, provider/model/grader/private-HF operation, replay
or ABBA advance was performed or authorized.

[boundary]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/ab0662ec687369bb41a1d62bd43c6b38a4c4f273/tasks/LATEST_TASK_RESULT/README.md
[prior-usage]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/8851fd3cda4aa55becdbface579117f3b16c866f/batch-runner/README.md#fixed-native-r1task1-observation-on-github-actions
[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/8851fd3cda4aa55becdbface579117f3b16c866f/tasks/LATEST_TASK_RESULT/README.md
