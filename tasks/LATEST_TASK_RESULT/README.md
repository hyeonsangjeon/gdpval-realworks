# Latest task result

## PROJECT5-CORRECT-TEST-OWNER

The corrected eight-node invocation passed at unchanged fixture HEAD
`3188e27a2eac24fd7ed3f3e074c9a088ad7d79e0`: 8 passed in 139.10s, exit 0.
Only the approval-input selector's owning module changed. The earlier attempt
at the same SHA remains a separate selection failure: 7 collected, 0 executed
in 5.49s, exit 4. It was not a setup error or a runtime assertion failure.

The 49-file test-only correction is committed on
`b/codex-retention-runtime-20260928`. This follow-up changes only these two
completion records; no code or fixture edits were needed. The passing result
permits one ordinary push to existing draft
[PR698](https://github.com/hyeonsangjeon/gdpval-realworks/pull/698), subject to
the frozen-byte comparison below. New-HEAD CI and delta review remain required.

### Fixture scope

The saved 54-module inventory was reused, not downloaded or rediscovered.
The patch addresses all demonstrated legacy-source families at their shared
construction boundaries. The corrected invocation validates the eight selected
representatives, not every case in the 49 changed files or the full CI suite.
Budget module names below omit the `test_codex_budget_pilot_` prefix and `.py`;
all test paths are under `batch-runner/tests/`.

- `conftest.py` now owns the existing explicit, non-autouse
  `historical_budget_source` provider. It uses genuine immutable
  `8ac891e3e0e4752fe15a00139a2691ddf9df7dce` bytes, asserts the exact three
  current-runtime source-pin refusals before rebinding, and keeps `ROOT`,
  `PLAN` and registration paths coherent with byte-identical frozen inputs.
  `grade_readout` and `budget_snapshot_readout` use the shared provider.
- The dispatcher `test_codex_budget_pilot.py::scenario`, `epoch02::compiled`,
  `output::cell`, `output_setup::case`, `output_target::case` and
  `results::records` request the source context explicitly. Synthetic host
  directories keep their original worktree-parent location, independent of
  the archived source tree and without relaxing native path guards.
- Shared compilation/cache boundaries are wired in `grading`,
  `grading_branch_inspect`, `grading_input`, `grading_oidc`, `grading_source`,
  `next_b1`, `b1_grading`, `task2_grade_completion`, `task2_final_readout`,
  `task3_a1` and `task3_a1_grading`, including the genuine temporary-Git source
  fixture and `task3_a1::retained_history`.
- Task3 histories in `task3_a1_readout`, `task3_b1_readout`,
  `task3_c_readout`, `task3_b2_readout`, `task3_a2_readout` and
  `task3_grading_chain` receive the context before their first compiler or
  `_writer_context` call. Their direct `__wrapped__` consumers forward it.
- Task4 histories in `task4_failed_grading`, `ungraded`,
  `task4_successor_grading`, `task4_failed_a2`, `task4_a1_ungraded_readout`,
  `task4_b1_readout`, `task4_ordinary_readout` and
  `task4_a2_ungraded_readout` are wired at construction. Genuine failed rows
  are still produced before inherited constructor guards are installed.
- Task5 histories in `task5_failed_a1`, `task5_failed_b1`, `task5_c1_grading`,
  `task5_failed_c2`, `task5_b2_grading`, `task5_failed_a2`,
  `task5_a1_ungraded_readout`, `task5_b1_ungraded_readout`, `task5_c1_readout`,
  `task5_c2_ungraded_readout` and `task5_final_readout` receive and forward the
  same source context. Existing receipt/native validators and ordering remain.
- `test_codex_ci_hf_originals.py` requests historical source for its real
  registered-origins positive. The grader-binding positives in
  `test_codex_native_resume.py`, `test_codex_recovery_feedback.py` and
  `test_codex_task_deadline.py` compute hashes from the same archive used by
  their comparison/Foundry providers. Current-tree source-pin refusals,
  stale-binding mutations, source-byte mutations and no-launch assertions
  remain explicit; no frozen pin or expected hash was replaced.

Seven inventory modules inherit the repair without direct edits: `ci`,
`epoch03_gate`, `epoch04_gate`, `failed_retention`, `failure_category`,
`retention` and `success_retention`. The other unchanged inventory module is
the frozen `test_grading_image.py`; its passing boundary selector was not rerun.
All production bytes and that guard compare equal to
`de3e0401b9c0ae9d2d142c25e14d1f4dab768383`. No workflow, YAML, registration,
source-pin validator, HF/grader production code, skip marker or timeout changed.

### Exact corrected invocation and prior selection diagnostic

The owning definition and `captured-live-shape` parameter were checked
statically in `test_codex_budget_pilot_approval_inputs.py` before execution.
That module imports the OIDC fixtures; the fixture module does not own the test.
From `batch-runner`, the sole invocation authorized for this correction was:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p no:cacheprovider --tb=short \
  'tests/test_codex_budget_pilot_epoch04_gate.py::test_closed04_plan_preserves_original_order_and_controls' \
  'tests/test_codex_budget_pilot_approval_inputs.py::test_dispatch_inputs_bind_actual_approval_to_connector[captured-live-shape]' \
  'tests/test_codex_budget_pilot_task3_a1_readout.py::test_fixed_task3_a1_grade_readout[graded]' \
  'tests/test_codex_budget_pilot_task5_final_readout.py::test_final_task5_readouts[b2-graded]' \
  'tests/test_codex_ci_hf_originals.py::test_hf_originals_real_registered_origins_keep_submission_parquet_out' \
  'tests/test_codex_native_resume.py::test_native_resume_active_grader_template_source_bindings[current]' \
  'tests/test_codex_recovery_feedback.py::test_recovery_feedback_active_grader_template_source_bindings[current]' \
  'tests/test_codex_task_deadline.py::test_cumulative_task_deadline_active_grader_bindings[current]'
```

```text
collected 8 items
======================== 8 passed in 139.10s (0:02:19) =========================
pytest exit status: 0
```

The log is `/tmp/project5-correct-test-owner.3y4tfK/pytest.log`. No other test
invocation ran for this correction. The prior command differed only in its
second selector, which used
`tests/test_codex_budget_pilot_grading_oidc.py::test_dispatch_inputs_bind_actual_approval_to_connector[captured-live-shape]`.
Its exact selection diagnostic remains:

```text
collected 7 items
============================ no tests ran in 5.49s =============================
ERROR: not found: /ai-work/copilot/worktrees/codex-retention-runtime-20260928/batch-runner/tests/test_codex_budget_pilot_grading_oidc.py::test_dispatch_inputs_bind_actual_approval_to_connector
(no match in any of [<Module test_codex_budget_pilot_grading_oidc.py>])
```

No fixture/runtime result was produced by that first attempt. Its unchanged
command, log and selected IDs remain in `/tmp/project5-resume-legacy.D50Xy2/`.

### Separate local validation observations

These are distinct PR698 invocations, not combined totals or a claim that a
single full selector passed. Earlier stops without an invocation add no result.

| Tested SHA | Actual result | Exit |
| --- | --- | --- |
| `b1854e5b50eda9c25c9db5bc2627acf35022e70d` | 5 failed, 42 passed in 334.92s | 1 |
| `91ffae589b240dd9d31978af0dd2cf19532e96c7` | 5 passed in 24.02s | 0 |
| `6710299c5776c30ccf3927a1f8a54c6ee4ffab09` | 3 passed, 1 setup error in 93.52s | 1 |
| `6665c183c215aa6594622eb9fe92ca55633c7013` | 1 setup error in 8.44s | 1 |
| `7bbe61f7880ce0bdb3a130fbf8f89856cb8efc27` | 3 passed in 49.11s | 0 |
| `88b8a62b4b5f4802f6fc22c25b9348d78a931f65` | 3 passed in 9.04s | 0 |
| `3fdc5a95853619135d4165063392144eb6fea540` | 8 passed in 26.06s | 0 |
| `1fa84f2b2cff4d51a323aabd2051130fd8b119c8` | 3 passed in 61.92s | 0 |
| `3188e27a2eac24fd7ed3f3e074c9a088ad7d79e0` | No tests ran; selector not found; 7 collected; 5.49s | 4 |
| `3188e27a2eac24fd7ed3f3e074c9a088ad7d79e0` | Corrected owner: 8 passed in 139.10s | 0 |

The [complete prior handoffs](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md),
[54-module inventory and prior CI results](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md#project5-final-legacy-fixtures)
and [prior changelog](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/CHANGELOG.md)
remain immutable Git evidence. Session artifacts, including
`/tmp/project5-final-legacy-fixtures.S8DFVq/failed-nodes.tsv`, were preserved.
Historical handoffs are linked here rather than copied into this current record.

### Remaining gates

The eight selected representatives passed locally; no new CI result is claimed.
Leader [review 5343801391](https://github.com/hyeonsangjeon/gdpval-realworks/pull/698#pullrequestreview-5343801391)
covered the delta through `de3e0401b9c0ae9d2d142c25e14d1f4dab768383` and was
conditional on all CI; it is not a waiver, approval of this new fixture delta,
authorization of modified runtime for the old campaign, or launch authority.
New-HEAD delta review and CI remain required. The capability remains
unregistered and live-unverified. No model, live readout, Azure, OIDC, HF
credential or paid operation, new campaign, CI rerun/poll or merge occurred.
