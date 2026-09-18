# Latest Task Result

- Updated: 2026-09-18 (UTC)

## Current Task: HF Cost Ledger Source Binding

### Scope and Result

HF publication now binds the optional top-level `cost_ledger` reference to
the canonical inference source. The change starts from immutable main
`776c436278b7d99ccc4364c206f02219603a83e0` on branch
`b/cost-ledger-source-binding-20260918`, in a new worktree at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-cost-ledger-source-binding-20260918`.
The preservation checkout and earlier B worktrees were not changed.

Exactly four files differ from the immutable main base:

- `batch-runner/core/hf_publication.py`
- `batch-runner/tests/test_hf_publication.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

`load_publication_identity` retains the source reference through
`project_cost_ledger_reference` in an appended `PublicationIdentity.cost_ledger`
field with a `None` default. Existing positional arguments and submission
rows are unchanged. The expected reference never comes from `self_report.json`.

`_validate_self_report_payload` checks optional-key presence and exact JSON
before `_validate_cost_ledger` and any HF API call. It projects the source
reference to the fixed publication path `cost_ledger.jsonl`, preserving the
digest, just as Step 6 staging does. The source reference itself is unchanged.
Changed, removed, injected, and null report references are rejected even when
replacement staged bytes match the report's changed digest. Genuine source
absence and null still require an absent report key.

The existing staged-file path and byte/digest validator is unchanged. No
ledger format, pricing, receipt arithmetic, schema, dashboard,
diagnostic-publication policy, or unrelated validation changed.

Existing ledger tests now provide source references in their identity
fixtures. The wrong-path test expects the new, earlier source-mismatch error.
Those selectors were not rerun.

### Verification

The new parametrized `FakeApi` selector ran exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_hf_publication.py::test_publication_binds_optional_cost_ledger_to_source
```

The result was `8 passed in 0.51s`. Accepted cases cover an unchanged source
reference with matching staged bytes, legacy absence, and source null
projecting to absence. Rejected cases cover a changed reference with matching
replacement bytes, removal of both reference and ledger, injection with
matching bytes, replacement with null, and null injection. All five rejected
cases assert `api.calls == []`.

The fixture uses the existing `stage_cost_ledger` helper and checks that staged
bytes match the reported digest, including the replacement and injection
cases. Its source filename differs from the pinned publication filename,
covering the existing rename without losing the source digest binding.

```bash
git diff --check 776c436278b7d99ccc4364c206f02219603a83e0
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
The implementation follows the existing optional-field binding pattern,
source-reference projector, and Step 6 publication-path convention.

`/im-not-ai-en` was used only for English completion records, including the PR
record. Commands, identifiers, results, and evidence limits were checked
manually; no additional verification script ran under the requested check limit.
`experiment-design`, `experiment-report-en`, `experiment-report-ko`, and
repository, UI, and animation skills were not applied to this deterministic
source-identity fix.

## Prior Result: #612 Cost Summary Source Binding

[#612](https://github.com/hyeonsangjeon/gdpval-realworks/pull/612) bound the
optional top-level `cost_summary` to canonical per-task receipts using the
shared cost and successful-deliverable helpers. Its implementation HEAD was
`305fc87855695eba8fc3cd5179f1318d3419e3d0`. The recorded selector
`test_publication_binds_optional_cost_summary_to_source` reported
`8 passed in 0.56s`, with `api.calls == []` in all five rejected cases.
That selector ran once for #612 and was not rerun here. This is historical
evidence, not validation of the current HEAD.
