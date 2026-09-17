# Latest Task Result

- Updated: 2026-09-17 (UTC)

## Current Task: HF Grading Cost Source Binding

### Scope and Result

The change starts from immutable main
`c36c722350f5cdfd629b4c82b17a856b537700f4` on branch
`b/grading-cost-source-binding-20260918`, in a new worktree at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-grading-cost-source-binding-20260918`.
The preservation checkout and the earlier B worktree were not changed.

Exactly five files change:

- `batch-runner/core/result_projection.py`
- `batch-runner/core/hf_publication.py`
- `batch-runner/tests/test_hf_publication.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

At the pinned base, `project_result_row` also drops the source's optional
`grading_cost`. It now retains that receipt through the existing
`project_cost_receipt` normalizer. `load_publication_identity` carries the
canonical value into an appended `PublicationTaskResult.grading_cost` field
with a `None` default. Existing positional arguments and the submission
format returned by `as_dict` remain unchanged.

`_task_report_projection` includes the receipt only when it is non-null.
`_validate_self_report_payload` checks optional-key presence and the exact
JSON value before any HF API call. Changed, removed, injected, and null
report receipts are rejected. Genuine legacy absence and source null still
project to an absent report key. Unrelated report metadata remains allowed.
The receipt comes from the source result, never from `self_report.json`.

No pricing, aggregation, receipt arithmetic, schema, diagnostic-publication
policy, or unrelated validation code changed.

### Verification

The single targeted regression ran once from the new worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_hf_publication.py::test_publication_binds_optional_grading_cost_to_source
```

The result was `10 passed in 0.51s`. The accepted cases cover an unchanged
receipt, legacy absence, and source null projecting to absence. The rejected
cases cover a changed receipt, removal, injection into an absent source,
replacement with null, null injection into an absent source, receipt injection
into a null source, and null injection into a null source. All seven rejected
cases assert `api.calls == []` using the existing `FakeApi` fixture.

```bash
git diff --check c36c722350f5cdfd629b4c82b17a856b537700f4
```

The diff check passed. The source and test files were not changed after the
targeted run. Only the completion records were written afterward. No full
suite, real HF upload, paid model call, Azure operation, or workflow dispatch
was run. These results do not establish full-suite or real-HF behavior.

### Reviewed-Head Status and Remaining Work

No head for this change has received an independent immutable-HEAD review.
That review and the required CI evidence remain pending. No approval is
claimed, and no CI run was requested or polled during this task.

### Skills

The complete available skill catalog was inspected before repository work.
Neither `python-fact-grounded-coding` nor another matching Python/code skill
was available in this session, so no Python/code skill invocation is claimed.
The implementation follows the existing #610 pattern.

`/im-not-ai-en` applies only to the English completion and PR records. Its
fidelity gate checks editorial literals, not runtime behavior.
`experiment-design`, `experiment-report-en`, `experiment-report-ko`, and
repository, UI, and animation skills were not applied to this deterministic
source-identity fix.

## Prior Result: #610 Problem-Solving Cost Source Binding

The preceding change retained canonical `problem_solving_cost` in the HF
publication identity and bound report receipts to source presence and value.
Its implementation head was `541c4ea843a1615eb8395860c80c6276ac27652f`.
The recorded selector
`test_publication_binds_optional_problem_solving_cost_to_source` reported
`8 passed in 2.53s`, with `api.calls == []` in every rejected case. This is
historical evidence from the prior completion record; that selector was not
rerun here.
