# Latest task result

## PR760: five-path synthetic continuation

The five requested nodes reported **5 passed in 96.48s**, exit 0, in one
offline invocation. The Task2 case followed the selected input through the real
V2 runner/factory using the ordinary model-free transport, then reached the
canonical result, private-prefix readback and permanent-claim assertions. The direction,
result-task, result-source and request-source cases reached their intended
refusals. No production, workflow, test, assertion or validator was changed.
This result is separate from the earlier failed invocation, not an aggregate
11-pass claim or permission to execute Task2.

### Tested and reviewed basis

The existing worktree was verified clean at leader-reviewed
`70a02619276bc9da072567d5ee0e4060aed6dbbf`, tree
`1d85a59c1baf5660d80a3abd5eedf14053dc54b2`. Those are the exact tested HEAD and
tree. The leader reviewed the workflow/controller/callable, selected-task
bindings, tests and records and found no additional blocking source defect in
that scope; the five paths remained unproved before this invocation. This
source review does not substitute for final CI or source-bound live authority.

The one-line wrapper lookup correction
`9b1d5b7fddf887a4233630452a261ff3bebfe880`, tree
`098626359b138c45fc53029fa55ed8cb7a21fe65`, was preserved exactly. The branch
still derives independently from accepted source
`7f4daa09944f6d9635e9bff3d945c224cfc76392`, tree
`9bc2b0bb655c4cd69fb3b59162776743b5a9278a`. Pending PR759 diagnostics and its
worktree were not copied, stacked, merged or changed.

The earlier pre-edit CI/source decision was performed by the leader, not a
successful spawned-model review. This continuation applied the retained
source/CI guidance without a new architecture/registration design or reviewer
harness retry. No study axis, model, budget, source pin or permission changed.

### One bounded proof and exact artifacts

The invocation began at `2026-10-06T13:31:52Z` with Python 3.10.12, offline and
telemetry disabled, retaining the existing network/write/credential/provider/
grader sentinels. The bound was 300 seconds plus 5 seconds termination grace,
without `-x`; temporary Git setup kept its existing 30-second bound. All five
nodes completed, with zero failures, errors or skips:

```text
tests/test_time_budget_first_v2_ci.py::test_time_budget_v2_registered_task_selection[task2]
tests/test_time_budget_first_v2_ci.py::test_time_budget_v2_registered_task_selection[direction_task]
tests/test_time_budget_first_v2_ci.py::test_time_budget_v2_registered_task_selection[result_task]
tests/test_time_budget_first_v2_ci.py::test_time_budget_v2_registered_task_selection[result_source]
tests/test_time_budget_first_v2_ci.py::test_time_budget_v2_registered_task_selection[source]
```

The positive case used actual temporary Git/worktree source validators and
explicitly synthetic registered parquet/reference bytes. It verified the
selected Task2 prompt/control, canonical row and deliverable byte identities,
result fingerprint, exact Task2 private prefix, immutable commit/control
readback and completion binding. Synthetic old Task1 objects remained unchanged.
Storage credentials were absent during model-free inference, and a subsequent
execute call refused the permanently consumed claim without another request.

The direction case refused the wrong task binding before execution reservation
or admission/provider effects. The two result cases used coherent synthetic
result hashes and reached the real result-task/result-source checks before
private retention effects, without publishing a completion. The source case
completed ordinary-bootstrap/linked-R/F setup and reached its request-source
refusal before credentialed intake or storage effects. Its earlier setup timeout
is not counted as source-refusal evidence.

Artifacts are retained in `/tmp/pr760-five-path-proof.3pIeF1ZC/`. `command.sh`
contains all five full node IDs and exact clean HEAD/tree guards.

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `command.sh` | 1833 | `41de10ed55fd61328df5a1273a6fc242eece3fd8378bbb599e9f0e1123c818e7` |
| `pytest.log` | 1099 | `09e467c892f017ce8304e79c04d593639f32cbbb7a49ac7886529096fa34ce68` |
| `junit.xml` | 1220 | `2865f76b41268322862c09391419414921574a5d76ffba2f1a367ac3549f4144` |
| `exit-status` | 2 | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |

### Prior failed observation remains separate

The [original PR760 record][original] retains **6 passed, 4 failed, 1 setup
error in 215.64s**, exit 1, at `e99fbc774a6fa2e2c02624e8f78bcc40200928cb`, tree
`4b1d7aadd4813be2f746e4ae8d4dfbdfb5c8aa71`. Four cases stopped at the test's
configuration-wrapper lookup; `source` timed out in setup before its assertion.
Correction `9b1d5b7fddf887a4233630452a261ff3bebfe880` was unrerun at that
handoff. The failed observation and its exact artifacts remain unchanged in
`/tmp/pr760-v2-registered-task-proof.XaKNtvU9/`; all four artifact hashes were
rechecked without rerunning tests.

The earlier passing `unregistered_task`, `run`, `condition`, `repeat`, `prefix`
and `old_task1_claim` nodes were not repeated. Neither the full 11-node selector
nor any old PR759, route/layout, platform or whole-suite selector ran. The
separate [PR759 record][diagnostics] retains **5 passed in 95.25s** for private
receipts and **8 passed in 162.87s** for the safe CI event at reviewed source
`7aebe28c402cfb71463231f2fb1a75825a26391f`, tree
`0165ff4f9f7d226a4cac8f34803d6134f53ba693`. Those proofs were not repeated or
used as evidence for this continuation.

### Historical Task1 stays consumed/uncertain

Real run `37456739936` / attempt 1 / job `112246098370` remains one uncertain
planned cell, not a zero score, excluded observation or replay permission.
Its immutable permanent claim is `e53fe8d4c47ef2a05aea8ffcc0fe1745a9b3c288`;
its acknowledged private output is `f602355f945471963a338ccf79783a6f802ac6dd`.
Completion artifact `11409044632` has SHA256
`06eb9a0c78858da29089cbd9d162e690320e45e40e3f8837de5bfaf11ef9e468`; the job log
has SHA256 `3e606025e66106575a472cb20073ec705ff60fd0cd532d972b589faf710f9a83`.
The [prior immutable record][original] preserves its source, request and host
identities and null result/terminal/usage/cleanup/reuse facts. Its first throw,
model-call count and cost remain unrecoverable from those facts and are not
inferred here. No real private claim, input or output was read or changed.

### Post-proof delta and remaining gates

Only `CHANGELOG.md`, this LATEST record and the directly affected evidence
paragraph in `batch-runner/README.md` change after the proof. Production,
workflow, tests, validators, request paths and usage commands remain identical
to the tested/reviewed source. `im-not-ai-en` is limited to changed English
evidence passages; its fidelity check is editorial, not another software proof.

Final records/source review, integration with the accepted diagnostic source
and ordinary final/integrated-HEAD CI remain leader-owned gates. Existing
expectation changes outside these five nodes still need their own CI coverage.
The fixed five-task/20-observation ABBA design, GPT-5.4/direct-v1/xhigh, V2
9-turn/8192-output settings, one external attempt, concurrency 1, 1200-second
generation and shared 20-second cleanup, 45-minute job ceiling and F/judge
policy remain unchanged.

Task2 `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` / `sandbox_v2` / repeat 1 still
requires a later accepted combined runtime source and a new leader-issued
immutable request. Final R/tree, actual next run number, finite admission
window/request digest, genuine input/preparation/host/path identities and a
current independently expected private parent remain live requirements. Actual
selected-prefix CAS, source/provider checks and kernel admission cannot be
waived. Genuine inference-publication/intake and later grading remain separate
binding/authority gates, with no invented source fields.

No live observation, HF/private-input/provider/model/grader/Azure operation,
CI query/dispatch/retry/poll, Project edit, merge or old-worktree change occurred.
The [usage section](../../batch-runner/README.md#one-selected-v2-observation-on-github-actions)
still describes a future command, not execution permission.

[original]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/70a02619276bc9da072567d5ee0e4060aed6dbbf/tasks/LATEST_TASK_RESULT/README.md
[diagnostics]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/7aebe28c402cfb71463231f2fb1a75825a26391f/tasks/LATEST_TASK_RESULT/README.md
