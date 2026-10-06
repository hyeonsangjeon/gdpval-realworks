# Latest task result

## One explicitly selected registered V2 task: failed offline proof

The existing route now carries `request.cell.task_id` through the source-verified
first V2 run. The one new offline selector reported **6 passed, 4 failed,
1 setup error in 215.64s**, exit 1. Its downstream Task2 execution/retention
coverage is incomplete. A one-line test correction was committed afterward
without a rerun; this is not an 11-pass result or live authorization.

### Scope and reviewed basis

The fresh independent branch starts at accepted main
`7f4daa09944f6d9635e9bff3d945c224cfc76392`, tree
`9bc2b0bb655c4cd69fb3b59162776743b5a9278a`. No prior worktree, remote claim or
output was changed. Pending PR759 diagnostics were not copied or stacked here.

The leader separately performed the read-only CI/source pre-edit decision and
approved implementation plus one synthetic proof. Its critical risk is aliasing
a selected task to another task's prefix/claim, especially treating consumed
Task1 as fresh. This is the leader's review, not a successful spawned-model
review; the unavailable reviewer harness was not retried. `experiment-design`
was applied only to preserve the existing registration, not to reopen its axes.

Only `gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 and one of its five
registered tasks can be selected per invocation. The workflow's early guard
checks that fixed cohort; the credential-free full validator independently
compiles reviewed R/F and resolves the task from the run specification. The
next intended task is `0112fc9b-c3b2-4084-8993-5a4abb1f54f1`, not authorized to
execute by this change. The selected task binds input/handoff, observation
control, direction, canonical row/deliverables, private prefix/CAS, retention
and the existing allowlisted completion schema. Historical first-cell names
remain compatible; execution does not switch tasks through mutable globals.

There is no new scheduler, workflow, task input, permission or experiment.
The five-task / 20-planned-observation ABBA design, GPT-5.4/direct-v1/xhigh,
V2 9-turn/8192-output settings, concurrency 1, one external attempt, 1200-second
generation including waits/recovery, shared 20-second cleanup and 45-minute job
ceiling are unchanged. F `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, TEMPLATE
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`, core,
manifest, grader/judge policy and legacy launch guards remain unchanged.

### Exact source and one invocation

- Tested HEAD: `e99fbc774a6fa2e2c02624e8f78bcc40200928cb`.
- Tested tree: `4b1d7aadd4813be2f746e4ae8d4dfbdfb5c8aa71`.
- Selector: `tests/test_time_budget_first_v2_ci.py::test_time_budget_v2_registered_task_selection`.
- Python 3.10.12; offline, telemetry disabled, network/provider/grader/write
  sentinels retained; 300 seconds plus 5 seconds termination grace; no `-x`.
- Started `2026-10-06T13:13:54Z`; 11 selected cases, **6 passed, 4 failed,
  1 setup error in 215.64s**, exit 1. No old selector was run.

The six passing parameters are `unregistered_task`, `run`, `condition`,
`repeat`, `prefix` and `old_task1_claim`. They exercised genuine request/source
validation and rejected invalid task/run/condition/repeat/prefix declarations
before credentialed intake. The old-claim case used explicitly synthetic old
Task1 objects, refused their occupied prefix without reading/adopting bodies or
making a new CAS, preserved their exact bytes, and blocked execution and local
re-preparation. No real private claim or result was read.

The four failed parameters are `task2`, `direction_task`, `result_task` and
`result_source`. Each reached real Task2 input validation, handoff preparation
and an acknowledged synthetic private claim, then stopped at test line 382:
`config["task_ids"]` raised `KeyError`. The genuine `configuration.json` wrapper
holds those fields inside `configuration`; the test omitted that lookup.
None reached its runner, cross-task direction, result-mismatch or retention
assertions. This does not demonstrate a production failure at those boundaries.

The `source` parameter errored before its test body. The existing
`actions_layout` fixture's actual Bash linked-R/F creation command exceeded its
30-second subprocess bound. The source-refusal assertion did not run. The
record establishes a setup timeout; it does not identify the specific Git
operation or a kernel/provider cause. The outer invocation finished within its bound.

Artifacts remain in `/tmp/pr760-v2-registered-task-proof.XaKNtvU9/`; the command
includes exact clean HEAD/tree guards and the full invocation.

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `command.sh` | 1435 | `85ab70d2b73cd6946ed42fa7219b861fc5989e0ebe3560cf02038a4f59856c61` |
| `pytest.log` | 6234 | `b7f83e5303782ec236e6813469ff78e275b73c6bede6b7aad722a1f0ae4cee2c` |
| `junit.xml` | 6129 | `437ab75f9ef5cffb121eda56b9d9b87e05217a188349e4351050ae668ae89217` |
| `exit-status` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |

### Post-proof delta and pending coverage

Test-only correction `9b1d5b7fddf887a4233630452a261ff3bebfe880`, tree
`098626359b138c45fc53029fa55ed8cb7a21fe65`, adds only `["configuration"]` to the
new test's wrapper read. It preserves every assertion and was not rerun.
Production and workflow bytes are identical to the tested source. The remaining
post-proof delta is only `CHANGELOG.md`, this LATEST record and directly related
`batch-runner/README.md` usage/evidence. `im-not-ai-en` checks only these changed
English passages; that editorial check is not software validation.

Existing test expectations now use an unregistered task for the refusal case,
pass the independently expected cell to completion validation, and bind the
ordinary model-free transport to its supplied observation. The old selectors
were not run; their changed expectations still need ordinary CI coverage.
The four unreached downstream paths and the source-setup error remain explicit
verification gaps. No subsequent successful test is implied by the correction.

### Historical Task1 remains permanently consumed/uncertain

The leader-read real [run 37456739936](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37456739936),
attempt 1 / job `112246098370`, used accepted source `7f4daa09944f6d9635e9bff3d945c224cfc76392`.
Request validation, genuine inputs/preparation/permanent claim, login and OIDC
checks succeeded; execution returned exit 2 with a generic uncertainty outcome.
Retention and artifact publication succeeded. This is one uncertain planned
cell, not a zero score, excluded datum or permission to replay it.

- Completion artifact `11409044632`, SHA256
  `06eb9a0c78858da29089cbd9d162e690320e45e40e3f8837de5bfaf11ef9e468`.
- Job-log SHA256 `3e606025e66106575a472cb20073ec705ff60fd0cd532d972b589faf710f9a83`.
- Permanent claim `e53fe8d4c47ef2a05aea8ffcc0fe1745a9b3c288`;
  private output `f602355f945471963a338ccf79783a6f802ac6dd`.
- Request SHA256 `6425b2b65ad94b6d7e1455df2d1717eccae18f937bf632f68222b80bf75f79bf`;
  host SHA256 `a84bfb9c4e87bd9911654714c629c00ca32466c381376b4f3f07416721ef1c87`.

Its result/fingerprint, terminal reason, usage, cleanup completion and host reuse
are null. Historical first throw, model-call count and cost cannot be recovered
from the retained facts and are not inferred here. The old claim/output and
namespace remain untouched.

The reviewed [PR759 diagnostic record][diagnostics] at
`7aebe28c402cfb71463231f2fb1a75825a26391f`, tree
`0165ff4f9f7d226a4cac8f34803d6134f53ba693`, keeps its **5 passed in 95.25s**
private-receipt proof separate from **8 passed in 162.87s** for the safe CI
event. Neither was repeated, imported or used as proof of this selector.
The [prior route and layout record][prior] preserves its earlier 14/11/10/1
outcomes and immutable links without aggregating them into a passing suite.

### Remaining gates

The leader must review this implementation and the unrerun fixture correction,
resolve the failed-path coverage, integrate the accepted diagnostics and run
ordinary final/integrated-HEAD CI. Source review does not authorize execution.
Task2 still requires a new leader-issued immutable request with final R/tree,
actual next workflow run number, finite admission window, exact request digest,
genuine input/registration/preparation identities, canonical paths/host values
and a current independently expected private parent. Actual selected-prefix
CAS, source/provider checks and kernel ownership admission cannot be waived.
The existing metadata route remains Task1-only; its old parent/prefix finding
does not establish Task2's current state. Genuine inference-publication/intake
and any later grade need their own bindings and authority; none is invented.

See the [direct usage](../../batch-runner/README.md#one-selected-v2-observation-on-github-actions).
No live input, HF, provider/model/grader, Azure management, CI query/dispatch/
retry/poll, Project edit, merge or prior-worktree modification occurred.

[diagnostics]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/7aebe28c402cfb71463231f2fb1a75825a26391f/tasks/LATEST_TASK_RESULT/README.md
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/7f4daa09944f6d9635e9bff3d945c224cfc76392/tasks/LATEST_TASK_RESULT/README.md
