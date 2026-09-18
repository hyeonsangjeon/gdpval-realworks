# Latest Task Result

- Updated: 2026-09-17 (UTC)

## Current Task: HF Cost Summary Source Binding

### Scope and Result

HF publication now binds the optional top-level `cost_summary` to canonical
per-task `problem_solving_cost` and `grading_cost` receipts. The change starts
from immutable main `d56e850dc8f8d17e50994fe0bb865426e1db3722` on branch
`b/cost-summary-source-binding-20260918`, in a new worktree at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-cost-summary-source-binding-20260918`.
The preservation checkout and earlier B worktrees were not changed.

Exactly four files differ from the immutable main base:

- `batch-runner/core/hf_publication.py`
- `batch-runner/tests/test_hf_publication.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

`_publication_cost_summaries` reads receipts from `PublicationIdentity`, not
from `self_report.json`. It reuses `build_cost_summaries` and
`successful_deliverable_count`, the same helpers used by `step6_report`.
Successful-deliverable counting uses the full source text and file list,
not the report's 300-character excerpt or the number of success statuses.

`_validate_self_report_payload` requires matching optional-key presence and
exact JSON before any HF API call. Changed, removed, injected, and null
summaries are rejected. A source with no receipts, including null receipts,
still projects to an absent summary. No pricing, aggregation arithmetic,
schema, dashboard, diagnostic-publication policy, or unrelated validation
changed.

The earlier per-task receipt selectors now include Step 6's expected cost
summary in their report fixtures. Their assertions are unchanged, and those
selectors were not rerun.

### Verification

The new parametrized `FakeApi` selector ran exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_hf_publication.py::test_publication_binds_optional_cost_summary_to_source
```

The result was `8 passed in 0.56s`. Accepted cases cover an unchanged summary
with both cost fields, legacy absence, and source null projecting to absence.
Rejected cases cover a changed value, summary removal, summary injection,
replacement with null, and null injection. All five rejected cases assert
`api.calls == []`. The fixture also checks two successful tasks where only
one has a non-blank deliverable, and that task's text begins after the
300-character report excerpt.

```bash
git diff --check d56e850dc8f8d17e50994fe0bb865426e1db3722
```

The diff check passed. The implementation and regression were not changed
after the targeted run. No full suite, real HF upload, paid model call,
Azure operation, workflow dispatch, Project #5 edit, or CI polling was
performed. These results do not establish full-suite or real-HF behavior.

### Reviewed-Head Status and Remaining Work

No reviewed implementation HEAD, approval, merge, or fresh CI result is
claimed. The next gate is review of the new immutable HEAD and the required
CI evidence. No additional implementation is planned in this task.

### Skills

The complete available skill catalog was inspected once for this task.
Neither `python-fact-grounded-coding` nor another matching Python/code skill
was available in this session, so no Python/code skill invocation is claimed.
The implementation follows the existing receipt-binding pattern and shared
Step 6 cost helpers.

`/im-not-ai-en` was used for the English completion and PR records. Commands,
identifiers, results, and evidence limits were checked manually; no additional
verification script ran under the requested check limit.
`experiment-design`, `experiment-report-en`, `experiment-report-ko`, and
repository, UI, and animation skills were not applied to this deterministic
source-identity fix.

## Prior Result: #611 Grading Cost Source Binding

[#611](https://github.com/hyeonsangjeon/gdpval-realworks/pull/611) retained
canonical per-task `grading_cost` through the result projector and HF
publication identity. At implementation HEAD
`bdfa4e36fc1fe69d30bbc4f727fb5a2f82ccf5cd`, the recorded selector
`test_publication_binds_optional_grading_cost_to_source` reported
`10 passed in 0.51s`, with no API calls in every rejected case.

The follow-up at `9556c8d755f987c6791d3fa341ee9b7b4aa557e3` corrected the
durable-voucher contract exposed by CI run `35258893231`. It removed this
rolling record from the expected voucher set while preserving all six sealed
payloads and every durable voucher path. The recorded selector
`scripts/__tests__/test_a_denominator_thrown_away_is_still_recoverable.py::test_the_six_sealed_files_on_disk_are_still_sealed`
reported `1 passed in 4.30s`. These are historical results; neither selector
was rerun for this task.
