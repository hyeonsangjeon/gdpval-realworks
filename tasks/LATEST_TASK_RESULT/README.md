# Latest task result

## PROJECT5-RETENTION-GRADE-LEDGER-BINDING

The fixed retention bridge and its focused ledger-contract check passed in one
offline invocation: **2 collected, 2 passed in 14.58s, exit 0**. Tested HEAD is
`117d0ded256fde2794b4be02bbb0cef78c38c6dd`, tree
`b4a418f2441e607e36b88c7b1269a1444379a0d3`. Publication validation, simulated
lost-acknowledgement reconciliation, duplicate-publication refusal and final
no-effect/private-namespace assertions were reached. This is offline integration
evidence, not a paid grade, provider authentication or an invoice.

### Responsible layer and exact correction

The compiler and synthetic judge already agreed. The real Step8 constructor
derives `retention/first-cell|<config_hash>|<grader_source_hash>` at run ordinal 1.
The config hash is the first 16 lowercase hexadecimal characters of SHA256 over
the actual materialized config bytes; the grader-source hash has 64 lowercase
hexadecimal characters. The fixture uses that prepared entry without rewriting
its ledger. The production publication validator previously accepted only
`pilot/cell-{index:02d}|<16 lowercase hex>|<64 lowercase hex>` for grading.

After the bounded pre-edit auth/storage `APPROVE-WITH-CONDITIONS` decision,
`codex_budget_pilot_output.RetentionFirstCellLedgerBinding` carries only the
config and grader-source hashes. It is frozen, requires its canonical type and
grants no grading or publication authority. The optional binding defaults to
None in `_ledger` and `_grade_files`. The nondefault path requires the literal
Task4 keep-r1 cell/task, integer cell index 0, exact adapted inference run ID,
exact keep/r1 control, hash widths/case and equality to the derived retention
run ID. Alternate families, repeat suffixes, wrong task/run/hash and lookalikes
refuse, including with an empty ledger.

`bridge.publish` constructs the binding from the rederived prepared entry only
after unchanged `_ready`, `_admission` and owned-cleanup checks. The shared
row-validator body, default inference/pilot predicate, pointer/hash linkage,
record schema, unique IDs, row/file/aggregate bounds and safe amount/text checks
are unchanged. No ledger is rewritten, priced, aggregated or reconstructed.
The production delta is limited to that type and the three-function handoff;
the focused test is the fourth code file changed in this correction.

The reviewed `root/original-upload` deliverables-only handoff and
`grade.RESULT_FORMAT` fixture correction remain. Static comparison preserved
all 103 existing assertion/refusal nodes and added 22 focused nodes. These are
static counts, not separate runtime passes. A read-only conformance check found
no unmet review condition; it is not immutable-head approval or live authority.
Workflows, reader/verifier, runtime, grader/config/rubric, registrations, source
pins, budgets, original routes/claims and grade namespaces were not changed by
this correction.

### Single validation and evidence limits

From `batch-runner`, the one invocation selected only:

```text
python3 -B -m pytest -q -p no:cacheprovider --tb=short -x tests/test_codex_retention_fixed_grade.py::test_retention_grade_ledger_binding_is_exact_and_legacy_defaults_stay_closed tests/test_codex_retention_fixed_grade.py::test_first_retention_fixed_grade_is_bound_one_use_and_private
```

Python 3.10.12 / pytest 9.1.1 ran with `env -i`, disabled plugin autoload,
bytecode/cache, offline HF/datasets/transformers flags, single-thread limits and
the unchanged shared process/network/credential/model guards. The 180-second
outer limit did not fire. No second test invocation or post-test code edit
occurred. Log SHA256 is
`1813545d68730574aaa5f58e4175cf768a2f9ad0b2441aae9202eca8fb908adb`.

The focused contract check exercised real Step8 derivation and ledger validation:
exact retention acceptance, wrong binding/run/hash/task and arbitrary-family
refusals, noncanonical binding and missing grading-run refusal, row corruption,
duplicate/row-limit refusals, and unchanged positive/negative inference/pilot
defaults. The bridge selector completed its workflow/legacy-request and inert
CLI checks, real registration/config validation, synthetic intake/readback,
deliverables-only materialization and grader/readiness validation, authority and
source negatives, fixed-parent verification/drift/corruption cases, simulated
one-use claim/judge and duplicate refusals, cleanup/grade/pointer negatives,
publication, lost-acknowledgement reconciliation and final no-effect checks.
It also verified that published synthetic ledger bytes were unchanged.

No assertion phase in either selected test remained unreached. Validators were
real; original inputs, Git metadata, HF, renderer/native-rename and owned-judge
transport boundaries were synthetic or simulated. No validation verdict was
replaced with success. No live HF/OIDC/Azure/model/grade call, workflow dispatch,
permission change, inference replay, Project edit or merge occurred.

### Earlier failures remain separate

The prior full handoffs and both previously uncommitted records were preserved
unchanged in the tested commit before this validation. Their
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

Only completion records changed after the pass. Author and committer remain
`hyeonsangjeon <wingnut0310@gmail.com>`, with no attribution trailers. The
authorized publication is one ordinary push and one new draft PR, not a live
grade. Prior worktrees/branches, `wip/local-main-preserved-20260719`, uncommitted
NAS refusal records and `/ai-work/copilot/retention-intake-private-20260930-2239`
remain unchanged. The leader's unavailable M4 files were not updated.
