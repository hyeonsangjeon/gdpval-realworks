# Latest Task Result

- Updated: 2026-09-17 (UTC)

## Current Task: HF Grading Cost Source Binding

### Scope and Result

The change starts from immutable main
`c36c722350f5cdfd629b4c82b17a856b537700f4` on branch
`b/grading-cost-source-binding-20260918`, in a new worktree at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-grading-cost-source-binding-20260918`.
The preservation checkout and the earlier B worktree were not changed.

Exactly six files differ from the immutable main base:

- `batch-runner/core/result_projection.py`
- `batch-runner/core/hf_publication.py`
- `batch-runner/tests/test_hf_publication.py`
- `scripts/__tests__/test_a_denominator_thrown_away_is_still_recoverable.py`
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

The HF implementation and its regression are unchanged in the CI follow-up.
No pricing, aggregation, receipt arithmetic, schema, diagnostic-publication
policy, or unrelated runtime validation changed.

### CI Contract Correction

CI run [35258893231](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35258893231)
failed in
`scripts/__tests__/test_a_denominator_thrown_away_is_still_recoverable.py::test_the_six_sealed_files_on_disk_are_still_sealed`.
Its expected voucher set still required `tasks/LATEST_TASK_RESULT/README.md`
after that rolling record stopped asserting the sealed digest. The CI failure
showed only that path missing from the actual document set.

The correction removes only that path from the expected set and revises the
test's docstring and error text. The six sealed payload assertion, the
gold-ceiling guard, and every durable voucher path remain unchanged. The
rolling record stays concise; no obsolete history or sealed digest was
restored. This follow-up edits only the script test and the two completion
records.

### Verification

The original grading-cost selector ran once before implementation commit
`bdfa4e36fc1fe69d30bbc4f727fb5a2f82ccf5cd`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_hf_publication.py::test_publication_binds_optional_grading_cost_to_source
```

The result was `10 passed in 0.51s`. The accepted cases cover an unchanged
receipt, legacy absence, and source null projecting to absence. The rejected
cases cover a changed receipt, removal, injection into an absent source,
replacement with null, null injection into an absent source, receipt injection
into a null source, and null injection into a null source. All seven rejected
cases assert `api.calls == []` using the existing `FakeApi` fixture.

That selector was not rerun for the CI correction. Its source and test files
retain the implementation commit's bytes.

The failing CI selector ran exactly once for this correction:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider scripts/__tests__/test_a_denominator_thrown_away_is_still_recoverable.py::test_the_six_sealed_files_on_disk_are_still_sealed
```

The result was `1 passed in 4.30s`.

```bash
git diff --check c36c722350f5cdfd629b4c82b17a856b537700f4
```

The diff check passed. The corrected script test was not changed after its
targeted run; only the completion and PR records were updated afterward. No
full suite, real HF upload, paid model call, Azure operation, workflow
dispatch, or Project #5 edit was performed locally. The CI failure log was
read once; no fresh CI result is claimed, and no CI polling was performed.
These results do not establish full-suite or real-HF behavior.

### Reviewed-Head Status and Remaining Work

The leader specified the correction against immutable head
`bdfa4e36fc1fe69d30bbc4f727fb5a2f82ccf5cd`. The correction still needs review
at its new immutable HEAD and fresh CI evidence. No reviewed correction HEAD
or approval is claimed.

### Skills

The complete skill catalog inspection from implementation was reused for the
CI correction, not repeated.
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
