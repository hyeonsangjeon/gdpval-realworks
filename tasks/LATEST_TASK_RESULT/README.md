# Latest task result

## PROJECT5-PR709-ROUTING-AND-RECONCILIATION

The two scoped PR709 corrections passed one offline invocation:
**2 collected, 2 passed in 1.52s, exit 0**. Tested HEAD is
`120ff70f382d54eef97452099ede06fa6bbb242c`, tree
`f446d162fc0c9d964cba5e932c3381896723848c`. The exact Step8 routing test and all
ten publication-path scenarios completed. This is workflow-routing evidence,
not live publication, a paid grade, provider authentication or an invoice.

### Exact corrections and unchanged boundaries

Seven exact expressions in
`test_grade_workflow_rc7_requires_valid_committed_partial` now match the existing
retention exclusions and fixed routes. Equality checks remain exact. Static
comparison preserved all 138 existing assertions, including approval inheritance,
permissions, source, published-commit and failure checks. This is a static count,
not 138 runtime test passes. No production exclusion was removed.

After the required bounded pre-edit CI/auth `APPROVE-WITH-CONDITIONS` decision,
only the existing publication step's shell body changed in `grade-run.yml`.
It captures the actual publication exit under `bash -e`. Only the exact
`retention/first-cell` selector, a nonzero publication exit and a regular,
non-symlink, current-user-owned `publication-reserved.json` at the fixed private
root permit one call to the existing read-only reconcile phase. Source, selector,
producer, terminal, root and step-scoped HF credential remain identical.

The original `publication-receipt.json` is not rewritten. The step emits the
CLI's separate safe server observation and fixed numeric exit labels, then exits
with the original publication status even if reconciliation succeeds.
`verified_server_state` retains `writer_acknowledgment=not_established`; it is
not a writer acknowledgement. Missing/unsafe reservations do not reconcile;
refused or ambiguous reconciliation remains explicit. There is no second
publication, polling, claim/judge re-entry, new request or raw artifact upload.

Job/step guards, permissions, credential scope and the five-minute step limit
are unchanged. All production Python bytes remain unchanged, including canonical
dispatch, authority, real receipt/terminal validators, typed ledger binding,
`root/original-upload` materialization, prepared-input revalidation, CAS,
deadline, owned cleanup and no-replay gates. The existing
`batch-runner/comparison-grading.json` config path, original pilot routes,
registrations, judge/model/rubric and budgets were not reopened. A read-only
conformance check found no unmet bounded-review conditions; it does not approve
the new immutable head or authorize a live grade.

### Single validation and evidence limits

From `batch-runner`, the one invocation selected only:

```text
python3 -B -m pytest -q -p no:cacheprovider --tb=short -x tests/test_step8_grade.py::test_grade_workflow_rc7_requires_valid_committed_partial tests/test_codex_retention_grade_publication_workflow.py::test_retention_publication_workflow_reconciles_once_without_replay
```

Python 3.10.12 / pytest 9.1.1 ran with `env -i`, disabled plugin autoload,
bytecode/cache, offline HF/datasets/transformers flags and single-thread limits.
The 180-second outer limit did not fire. Log SHA256 is
`91975eb26d5b651a861e4f02cbb8d294cbf94d794fe099e8f4e53df95b0d5adc`.

The new test parses the real YAML and executes its unmodified publication body
with real Bash. Only the external CLI process boundary is simulated, with no
executable available through its isolated PATH and no credential in that test
environment. No production validator is replaced with a successful verdict.
The scenarios cover successful publish/no reconciliation; reserved failure/one
reconciliation; pre-reservation refusal; refused and ambiguous reconciliation;
symlink/directory reservations; legacy success/failure; and a selector lookalike.
Exact arguments and call counts, original exits/receipt bytes, separate safe
observations, private-file preservation and final file inventories were checked.

No selected assertion phase remained unreached. This invocation does not repeat
the full bridge's validator proof. No unchanged ledger/14.58s selector bundle,
private 295.37s integration, full suite or CI workflow was rerun. No live
HF/OIDC/Azure/model/grade call, workflow dispatch, permission change, inference
replay, Project edit or merge occurred.

### Reviewed head and separate previous observations

The owner's REQUEST-CHANGES
[review 5371296460](https://github.com/hyeonsangjeon/gdpval-realworks/pull/709#pullrequestreview-5371296460)
was at `a8d5c42e69b9b3ecfadb5af1a1dff945e3541e95`. The leader directly read
[CI run 36764747855 / job 110055972491](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36764747855/job/110055972491):
**1 failed, 13298 passed, 64 skipped, 46 deselected in 933.35s**. Its sole failure
was the stale exact route expectation at `test_step8_grade.py:3489`; the later
coupled expressions in that test were not reached. Those reported CI counts
were not polled or rerun, and this local pass is not a new CI result.

The earlier **2 collected, 2 passed in 14.58s, exit 0** at
`117d0ded256fde2794b4be02bbb0cef78c38c6dd` remains a separate observation. Its
[immutable ledger/bridge handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/a8d5c42e69b9b3ecfadb5af1a1dff945e3541e95/tasks/LATEST_TASK_RESULT/README.md#project5-retention-grade-ledger-binding)
preserves the tested tree/log identity, exact non-authorizing ledger binding,
103 preserved plus 22 added static assertion/refusal nodes, and real validators
with synthetic input/transport/child boundaries through publication,
lost-acknowledgement reconciliation and final no-effects. It did not prove the
workflow wiring corrected here. No earlier pass or failure was replayed.

### Earlier failures remain separate

The prior full handoffs and both then-uncommitted records were preserved
unchanged at `117d0ded256fde2794b4be02bbb0cef78c38c6dd`. Their
[immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/117d0ded256fde2794b4be02bbb0cef78c38c6dd/tasks/LATEST_TASK_RESULT/README.md)
retains the exact safe traces and then-current pending work.

| Tested HEAD | Separate result | Reached / not reached at that time |
| --- | --- | --- |
| `ef2708ccf85ffdea04cbaa7e94909cf84a361b94` | 1 collected, 1 failed in 2.96s, exit 1 | Workflow/config/CLI and synthetic intake completed; nonexistent `grade.TERMINAL_FORMAT` stopped predecessor-fixture construction before preparation, predecessor verification, claim, judge or publication. |
| `e1d20767c93bd057504ac5568c5a7e4b2708c1b3` | 1 collected, 1 failed in 7.15s, exit 1 | Fixture construction and approval/source negatives completed; the real materializer refused the complete intake root before prepared/grader, predecessor-verification, claim/judge or publication assertions. |
| `be0761cdeca4d9e15bbd676f1112dd73a23a8c66` | 1 collected, 1 failed in 14.54s, exit 1 | Real materialization/readiness, synthetic predecessor checks, simulated claim/judge and duplicate refusals completed; `fixed_grading_ledger_run_required` stopped before publication reservation/output transport, reconciliation and final assertions. |

The new pass does not retroactively change any of those failures into a pass.
Earlier NAS prerequisite refusal, intake-fixture failures and their later
synthetic passes remain distinct in the
[immutable PR708 evidence](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ece7057a838e6a97d0c7441b2b2617f503a5adc2/tasks/LATEST_TASK_RESULT/README.md).
None was rerun.

### Actual producer/intake evidence and remaining gates

The successful producer remains `e355faf9a6212175a288e8473968915ffb2408d0`,
[run 36696961231 / job 109837605787](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36696961231/job/109837605787).
The leader's actual verified intake remains
[run 36739260150 / job 109969006748](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36739260150/job/109969006748)
at `2026-09-30T15:48:51.8896422Z`, with intake SHA256
`dbdb64c0ea4769c37b1954c972823777dbd90bf6dbde77ddbcef2e169eb4eb32`.
Its original-input stages 6–10 and approval/execution jobs were skipped;
source/hash step 11 and read step 12 succeeded. No inference or grader ran in
that read. Terminal `de50ff0aa6037c0ef6e3b713da519359abd1d08d`, claim
`3fc283087a020caec574e8c9b8e9bc3ca593e88a` and output
`43cbf8e265297813857172ecee51256cc17f2d36` remain fixed. Full object hashes,
request/cell/result fingerprints and the separately verified historical grading
parent remain in the
[preserved identity record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/117d0ded256fde2794b4be02bbb0cef78c38c6dd/tasks/LATEST_TASK_RESULT/README.md#project5-verified-grading-predecessor).
The completed model-free UNGRADED predecessor is neither an unfinished claim
nor a score; its historical observation does not establish today's branch head.

Actual accounting is still partial: 10 recorded model calls, known cost USD
`0.409894`, `runtime_cost_usd=null` and
`missing_reasons=[call_reachability_unknown]`. These are not HTTP request counts,
zero cost or an invoice; top-level `missing=[]` does not make accounting complete.
`grade=null`, `grading_launched=false` and `invoice_complete=false` remain.
Successful inference and retained intake are consumed and were not replayed.

The approved base remains `5b05c4617902491bd180a78365f00df4e5584895`, PR708
reviewed head `ece7057a838e6a97d0c7441b2b2617f503a5adc2`,
[review 5368244291](https://github.com/hyeonsangjeon/gdpval-realworks/pull/708#pullrequestreview-5368244291),
with the leader-reported 10 passing checks. Those checks were not polled or
rerun. New-head immutable review and CI remain pending for this bridge. Later
exact-source/input direction must still bind the pinned terminal/result,
receipt/marker/readback, original Task4 inputs and rubric
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, and the actual materialized grader
`c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320`
before the serial one-use claim or judge. Same-run protected owner approval
remains mandatory. The fixed judge remains `default_v2_sol_max.yaml`,
GPT-5.6 Sol / max, Ubuntu 24.04 / Python 3.11,
with the existing 240-minute ceiling. Producer, reader, historical observer and
grading-source identities stay distinct; parent drift, force/resume/shards,
regrade and ambiguous cleanup still refuse. Budget authority remains delegated.

Only completion records changed after this 1.52s pass. Author and committer remain
`hyeonsangjeon <wingnut0310@gmail.com>`, with no attribution trailers. The
authorized publication is one ordinary push to the existing PR709 branch, not a
new PR or live grade. Prior worktrees/branches, `wip/local-main-preserved-20260719`, uncommitted
NAS refusal records and `/ai-work/copilot/retention-intake-private-20260930-2239`
remain unchanged. The leader's unavailable M4 files were not updated.
