# Latest task result

## PR756 result-byte reread correction

The confirmed production bytes-serialization bug is corrected. One offline
executor selector reported **2 failed, 29 passed, 49 deselected in 226.13s**,
exit 1. All 31 selected cases completed. The remaining partial-output and
timeout assertions failed; no case was rerun or assertion changed. Delivery
remains HOLD, and no real grade or observation was executed.

### Reviewed basis and exact scope

Work started from clean `8722a9d91c3ef1b7c77a6e6b529052b0ce621cf8`, tree
`e27f9e2d573581feb20f052ac2be8c8034027b3d`, on the existing
`b/codex-time-budget-first-f-grading-executor-20261006` branch. The leader
confirmed this production bug in [review 5423395811][review]. PR755, previous
worktrees and all prior command/log/receipt files remain untouched.

Only `batch-runner/gpt54_time_budget_grading_execution.py` changes before the
proof: three lines replace two in `_checked_preparation`'s `reread`. It now
compares the complete `_result` tuple directly, retaining raw result bytes,
parsed payload, the deliverable-byte dictionary and the fingerprint. A
mismatch raises `GradingExecutionRefused("grading_result_changed")`, following
the preparation helper's existing equality/refusal pattern. `_same` still
performs its original JSON comparisons elsewhere; no `default=str`, omitted
byte field or successful-validator stub was added. Tests are unchanged.

The established grading/source charters preserve the independent controller
C, runtime R and frozen F roles. F remains
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with TEMPLATE
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The actual materialized config/source association and distinct whole-source
fingerprint are unchanged. Independent direction, the nonrenewable claim in
the named local attempt store, every input/result/deliverable check and final
held-directory/source rereads remain mandatory. No frozen profile, manifest,
grader algorithm, core, workflow, study policy or launch gate changed.

### Distinct earlier observations

The [immutable initial record][prior] retains the original local proof at
`362587b029d069f8a27226fbd37e60a6484649b0`, tree
`bc326cbcc6b16ed3b39e5d3596b98ba28904f50a`: **31 failed, 49 deselected in
132.68s**, exit 1. The NAS host lacked `/proc/self/ns/user`; `FileNotFoundError`
with errno 2 stopped shared setup before direction construction or executor
assertions. This was not successful refusal or host-support evidence.

The separate [fixture correction][fixture],
`3642428f88e5d7a6f159be9978e3a6137d7f4bf1`, tree
`58074aae1c1a83c7f00d47ef8b821795dc305c7b`, added 11 lines of explicit synthetic
namespace metadata. It was not rerun locally in that original task. This
continuation retains those fixture bytes and the real source/context/direction
validators. The initial record also links the separate 53/41/8-case proofs and
earlier host evidence; none was repeated or combined into a new pass claim.

At reviewed `8722a9d91c3ef1b7c77a6e6b529052b0ce621cf8`, the leader read completed
[CI run 37405741472, job 112082795143][ci], attempt 1: **31 failed, 13482 passed,
64 skipped, 46 deselected, 1 warning in 1376.58s**. All 31 executor cases failed
at the production bytes-serialization comparison after the namespace fixture
correction. This was separate from the local namespace failure. The supplied
raw-log SHA256 is
`21d3c237d56e8bc4b53afb3cda872b775c6800c1436c43a111bc5662abf690e4`.
No CI query or rerun was made in this task.

### One bounded correction proof

Tested HEAD `b3587f7dc865812e416d6b49b3914d0d3c6ed037`, tree
`dbe3f311d35b20b941b4e61b9306cbe80647d118`, contains only the production
comparison change relative to the reviewed basis. The retained command file
checks that exact clean HEAD/tree and Python 3.10.12, then runs from
`batch-runner`:

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
  --basetemp=/tmp/pr756-result-bytes-reread-proof.eI7i3g/pytest-tmp \
  --junitxml=/tmp/pr756-result-bytes-reread-proof.eI7i3g/junit.xml \
  tests/test_time_budget_grading_preparation.py \
  -k time_budget_first_f_grading_executor
```

Pytest reported **2 failed, 29 passed, 49 deselected in 226.13s**, exit 1.
All 31 selected cases completed before the outer timeout; none was skipped or
left incomplete. The 49 older preparation cases were not run. Genuine
temporary Git/source identities and explicit synthetic namespace/input/result
data were used, with the ordinary model-free process seam and real validators.
This is software evidence, not a real F Step8/provider invocation or platform
probe.

Both failures are in `tests/test_time_budget_grading_preparation.py::`:

- `test_time_budget_first_f_grading_executor_roundtrip[partial-failed]`, line
  600: no `sidecar_files` path contained `/_progress/`, although the assertion
  required one.
- `test_time_budget_first_f_grading_executor_roundtrip[timeout-timeout]`, line
  584: `terminal_reason` was `failed`, not the expected `timeout`.

The completed pass inventory is the other five roundtrip parameters
(`complete-completed`, `error-failed`, `cleanup_lost-cleanup_unconfirmed`,
`missing-missing_grade`, `cancelled-cancelled`), all seven direction-refusal
parameters, all 12 binding-refusal parameters and all five attempt-retention
parameters. The retained output and receipt enumerate all 31 exact node IDs.
No further source/test correction or test invocation follows this result.

Artifacts remain under `/tmp/pr756-result-bytes-reread-proof.eI7i3g/`:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `9c60696e9159437b15d82a0cb4d971d4811bcf8febf535cc8ebd215e61c6a796` |
| `output.log` | `943da6f927051e7e68042d41f72d699d7c003e6e15516bdafa485a2b05022a37` |
| `junit.xml` | `9fb48f402e623dd96941117b517d1d7b9a165930c0671016df3dd505fbc90a40` |
| `receipt.json` | `c2a35e8c42d119c083560eb1c4a913cfca94a91154a614e271141a2d885e6e97` |

The command digest identifies the exact retained file including source guards,
not the shorter displayed invocation or redacted public text. The post-proof
repository delta is `CHANGELOG.md` and this LATEST record only. The total
correction is those two records plus the production tuple comparison.

### Remaining gates

The partial-sidecar and timeout-terminal failures still need resolution, as do
corrected-HEAD source review and applicable CI acceptance. The missing genuine
inference-publication/intake locator is a later integration gate. No
`source_repo_id` or `source_revision` was invented, and no historical result was
changed. Real input/result/deliverable identities, reviewed C/R/F, actual host
context, the approved provider connection and a leader-issued digest-bound
execution direction remain prerequisites. No global once-only, backend
cancellation, billing or live enforcement claim follows from this proof.

The catalog was checked once, and the existing grading/source charters applied
to this narrow correction. `im-not-ai-en` covers only the changed English
records; no new experiment design or unrelated skill was needed. No private
original/result/receipt or consumed preparation was accessed. No real
provider/model/grader/HF/Azure operation, platform probe, CI dispatch/retry/poll,
Project edit, merge or launch enablement occurred.

[review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/756#pullrequestreview-5423395811
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/8722a9d91c3ef1b7c77a6e6b529052b0ce621cf8/tasks/LATEST_TASK_RESULT/README.md
[fixture]: https://github.com/hyeonsangjeon/gdpval-realworks/commit/3642428f88e5d7a6f159be9978e3a6137d7f4bf1
[ci]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37405741472/job/112082795143
