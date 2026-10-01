# Latest task result

## PROJECT5-PR713-CANONICAL-REQUEST-GUARD-20261001-1741

The admission guard correction passed at tested HEAD
`a378df829166dc9cb5031882723944a5d009238a`: 1 collected, 1 passed in 2.08s,
exit 0. The one guarded, token-free CI-shaped invocation completed the real
canonical-authority entrypoint regression; the 180-second timeout did not fire.
The guard rejects noncanonical, mixed-transport or mismatched admissions with
`retention_execution_grant_required` before accessing `request.cell_id`. It
then requires the exact `Request` type with
`explicit_retention_request_required` and retains the exact two admission/cell
pairs before `_context`, transport access or host effects.

The earlier successor/closed-route pass at
`5b788b79a3385a3588d64fe5a96b58434e05ae1e` remains separate: 2 tests passed
in 34.90s, exit 0. It did not cover this entrypoint regression and was not
rerun. The 2.68s source-pin and 5.71s missing-field failures remain preserved
below. This is an offline guard correction, not a live inference or execution
approval. Only the guard and two directly coupled reason assertions changed;
the remaining successor implementation and fixture corrections are unchanged.

The first keep/r1 numeric result is now available from the leader's successful
read of the existing safe receipt: 30.6 / included possible 45 = 68.0%, with
54.64% on the full denominator. This is one writer-recorded task score, not
evidence of retention benefit. The acknowledged inference and grade remain
consumed; this implementation task launched neither a model nor a readout.

### PR713 CI failure and targeted correction

The leader directly read
[CI run 36834022780 / pytest job 110276977686](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36834022780/job/110276977686)
at prior reviewed HEAD `9645764f09ea2b5b3fe069bbaade4f78984a1d7f`:
1 failed, 13303 passed, 64 skipped, 46 deselected in 1301.15s.
[Review 5376693421](https://github.com/hyeonsangjeon/gdpval-realworks/pull/713#pullrequestreview-5376693421)
was conditional on CI. That failed CI is not green, and its counts/duration
are test evidence, not model usage or a waiver of the new-HEAD gates.

The sole failure was the entrypoint test at line 117: the admission/cell tuple
read `None.cell_id` before rejecting the noncanonical `__main__` admission,
raising `AttributeError` instead of `retention_execution_grant_required`.
The correction keeps exact class identity, rejects unknown/mixed/mismatched
admissions first, validates the canonical `Request` before cell access, and
retains both exact class/cell pairs and every later predicate. The two canonical
`None` expectations now use `_context`'s existing
`explicit_retention_request_required` reason. No workflow or pin changed.

The single selector was:

```text
tests/test_codex_retention_ci_entrypoint.py::test_retention_script_entrypoint_uses_canonical_authority_types
```

It ran once from `batch-runner` under CPython 3.10.12 / pytest 9.1.1 with
`-v --tb=short -p no:cacheprovider`, plugin autoload disabled, token-free
`GITHUB_ACTIONS=true` and synthetic `pull_request`/`pytest` metadata, plus the
existing process/network/credential guards. The legacy-`None` LIVE_GATE refusal,
both canonical-`None` reason checks, actual script/class identity checks and
final no-effects/empty-host assertion all completed. No selected assertion
remained unreached. The full suite and the passed successor/route selectors
were not rerun. Log SHA256:
`c022ac9023b062666d61c18fe554df7b1b3f06a31e9b4aca9f5afcc1389cd5f4`.

### Source, review boundary and implementation

GitHub main was checked before selecting exact base
`f30c9efa392bc14cba790fb5d1dedf12071a5677`, tree
`94337abf2b0f7051eb699aa82848673c1637356f`. Work is isolated in
`b/codex-retention-task4-fresh-r1-20261001-1507` at
`/ai-work/copilot/worktrees/codex-retention-task4-fresh-r1-20261001-1507`.
This continuation reused that worktree and branch. The existing author and
committer identity stayed `hyeonsangjeon <wingnut0310@gmail.com>`; this
correction retains that identity without trailers.

The required bounded CI/auth/storage reviewer approved the fixed facade
approach before workflow or authority edits. That implementation decision is
not an immutable owner review or CI pass for the new HEAD. No broad grader,
reader or original-pilot review was reopened.
That authority decision remained applicable to the fixture-only continuations,
which did not reopen source or authority approval.
The required read-only review of the test-only diff at
`5b788b79a3385a3588d64fe5a96b58434e05ae1e` found no blockers. That narrow
check is not immutable owner/source approval or CI evidence.

For the current guard-only correction, the required narrow pre-edit auth/order
review approved the proposal before the production edit. It did not repeat the
full implementation review or grant new authority. Immutable new-HEAD owner
review and CI remain required.

The original pinned successor delta covered seven implementation/workflow/test files:

- The existing controller has two explicit bindings: keep/r1 ordinal 0 and
  fresh/r1 ordinal 1. It selects the registered config/control and local stage
  names and requires exact admission-type/cell pairs before host reservation.
- `codex_retention_task4_fresh_r1.py` adds only the fixed successor. It reuses
  source, same-run owner approval, runtime, owned-child, snapshot and immutable
  publication primitives. Its request binds its own source, selected stage and
  fixed predecessor. It retains unresolved publication receipts separately
  from read-only server observations; observation is not writer acknowledgment.
- The same three workflow jobs retain their permissions, protected environment,
  concurrency, original-input steps, secret scope and false mode defaults.
  Closed plan/prepare/approval/execute routing selects the facade. Fresh
  `read_result` and `observe_locator` are refused before credentials; the existing
  first-result reader and locator commands remain unchanged.
- A new synthetic regression and directly coupled old shape assertions describe
  staging, predecessor/CAS, one owned child, publication, reconciliation and
  no replay. The original invocation stopped before staging, and the next
  stopped before admission. The 34.90s invocation completed both selectors,
  including predecessor/CAS, owned-child, publication and reconciliation checks.

The old CI verifier is byte-identical, SHA256
`8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c`;
the first-result reader remains
`df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196`.
Runtime, input/model/grader pins, registration, fixed grader and readout bytes
were not changed to accommodate the controller or the failed fixture.

### Earlier 2.68s invocation, preserved

Tested HEAD: `c291670272f897fba03dcbceaa3779560076b522`. The two selectors were:

```text
tests/test_codex_retention_task4_fresh_r1.py::test_task4_fresh_r1_has_one_bound_predecessor_and_owned_route
tests/test_codex_retention_ci_observation.py::test_retention_locator_observation_is_closed_and_separate
```

The command ran once from `batch-runner` under CPython 3.10.12 / pytest 9.1.1,
with `-x -q --tb=short`, a token-free CI-shaped ambient envelope
(`GITHUB_ACTIONS=true`, synthetic `pull_request` / `pytest` metadata,
`refs/pull/1/merge` and `eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee`), and the
existing process/network/credential guards. The 180-second outer timeout did
not fire. Result: 2 collected, 1 failed in 2.68s, exit 1; the second selector
was not run because of `-x`.

The exact safe failure was
`synthetic_original_serializer:DispatchPlanRefused:compile_dispatch_plan`.
The underlying real compiler refusal listed:

```text
source_pin:batch-runner/core/codex_runner.py
source_pin:batch-runner/step2_run_inference.py
source_pin:batch-runner/core/codex_task_deadline.py
```

`_originals` reuses the prepared-input regression's `_fixture`, which calls
`compile_grading_plan(manifest)` and then `compile_dispatch_plan`.
`_configuration_problems` compares the original profile's sealed source hashes
with files under the current source root. Those three comparisons failed.
This is a synthetic fixture/source-closure integration failure, not evidence
that the consumed inference or grade is bad. No source pin or validator was
relaxed after the failure.

The real eight-cell registration compilation, frozen CI/reader hash checks and
explicit binding/scope assertions completed. Original Step1 serialization,
synthetic historical transport, fresh packet/stage/readback, approval and
predecessor checks, CAS/child/publication/reconciliation, duplicate/no-replay,
legacy staging and final no-effects assertions were not reached. That invocation
provided no passing successor or workflow-route proof. Log SHA256:
`6e04bd13f5fd6ad02614bd0913817da5ef922c15e6e4db6777d3c3aa83a17cdb`.

### Source-context correction and earlier 5.71s invocation

Tested HEAD: `53e5dc29f87cee0154aeb643c8611f67e751b283`. Only
`tests/test_codex_retention_task4_fresh_r1.py` changed: 30 insertions and
5 deletions. Its explicit `approved_pilot_source` dependency reuses the local
archive of `8ac891e3e0e4752fe15a00139a2691ddf9df7dce`, with the existing 30-second
bound, `GIT_NO_LAZY_FETCH=1` and archive path/type checks before function-scoped
guards. There is no new archive helper or autouse source override.

The fixture asserts the same three current-source refusals above, derives the
archived plan path before changing comparison `ROOT`, and checks exact plan
byte equality. Only comparison `ROOT`/`PLAN` are scoped to that archive around
the real original serializer/compiler. The `finally` block checks restoration
on return or refusal; this invocation exercised a successful return. Those
assertions passed before successor registration and its existing synthetic
runtime-copy setup; the archive never redirected successor, CI,
preparation, registration or owned-dispatcher roots. No source pin or validation
verdict was substituted.

The same two selectors ran once under CPython 3.10.12 / pytest 9.1.1, the
token-free CI-shaped ambient envelope and existing guards. Result: 2 collected,
1 failed in 5.71s, exit 1; the 180-second outer timeout did not fire. `-x` again
prevented the closed-route selector from running.

Real original compilation/Step1 serialization and root restoration, synthetic
source/archive setup, fresh packet/stage/readback, duplicate-stage refusal,
canonical successor request, both inert actual-script paths and the fresh
locator refusal completed. At test line 338, `retained._paths(old_cells[-1])`
received a synthetic historical cell containing `cell_id` and `index`, but no
`run_id`. The real `codex_budget_pilot_retention._paths` accessed `cell["run_id"]`
while evaluating `cell["run_id"] == ci.CAMPAIGN + "__" + cell["cell_id"]` and
raised `KeyError: 'run_id'` at line 74. It did not emit a
`retained_epoch_mismatch` verdict. This is another synthetic fixture boundary,
not evidence of a production successor defect or a bad consumed result.

Approval/admission negatives, immutable predecessor/current-parent CAS,
owned child, publication/reconciliation, duplicate admission/no-replay,
remaining legacy-route and final no-effects assertions were not reached.
Successful fixture setup and staging are not acceptance. The failed test bytes and log
remain intact, SHA256
`4987911414044bcf1ba619a9fe4eda06e52b02286fb0f0c966b31d2bdebfcacb`.
That turn ended without a second repair/run or production edit.

### Historical-record correction and the passing invocation

Tested HEAD: `5b788b79a3385a3588d64fe5a96b58434e05ae1e`. Only the successor
test changed, with 25 insertions and 1 deletion. The final historical row now
has the full `compile_pilot` cell shape: `cell_id`, `run_id`, `task_id`,
`condition`, `repetition`, `index`, `config_sha256` and `roles`. Its run belongs
to `budget_pilot_ci_20260925_04`, with Task5 A/r2 derived from the already
serialized original profile and immutable original template. The real config
validator checks that synthetic config; its canonical digest and historical
role paths belong to that row, not to a retention or grading record. No full
study compilation, production edit, validator bypass or source override was
added. The deliberately inherited historical terminal still refuses replay at
its original history boundary.

The bounded static pass checked the other synthetic constructors against their
immediate consumers. Existing `ResultHF` records and production-owned serializers
continue to supply claim/output/terminal records; deliberately malformed cases
and every original assertion remain intact. The passing invocation again checked
the three current-source refusals, archived/current plan equality and comparison
`ROOT`/`PLAN` restoration before successor setup. Successor and owned-dispatcher
roots were never redirected to the historical archive.

The two selectors listed above ran once from `batch-runner` with `-v --tb=short`,
plugin autoload disabled, no cache provider, the existing process/network/
credential guards and the same token-free CI-shaped ambient envelope. CPython
3.10.12 / pytest 9.1.1 collected 2 tests; both passed in 34.90s, exit 0.
There was no `-x`; the 180-second outer timeout did not fire.

- `test_task4_fresh_r1_has_one_bound_predecessor_and_owned_route`: PASS. It
  completed original serialization/restoration, fresh packet/stage/readback,
  source/cell/approval/run refusals, all 8 predecessor/admission fault cases,
  current-parent CAS, admission/child/output/terminal ordering, duplicate and
  no-replay refusals, immutable reconciliation, lost output/terminal responses,
  unconfirmed cleanup, unchanged ordinal-zero staging and consumed-cell refusal,
  frozen bytes and final no-effects/privacy assertions.
- `test_retention_locator_observation_is_closed_and_separate`: PASS. It completed
  the directly coupled closed workflow/CLI route and non-authorizing locator
  assertions independently of the successor result.

No selected assertion remained unreached. Transport, provider records and the
owned child were synthetic; no live claim, inference, publication, grade or
readout occurred. At that point, the unchanged production delta still needed
immutable owner review and CI. Log SHA256:
`5ad22e5645e824d93ea31791f01ebcc887e376a502bf2e799cf362c249845435`.

### Actual verified keep/r1 readout, separate from offline proof

The leader directly read
[run 36820845596 / attempt 1 / pilot-readout job 110235885096](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36820845596/job/110235885096)
at source `f30c9efa392bc14cba790fb5d1dedf12071a5677`. Its receipt at
`2026-10-01T05:43:22.3151574Z` reported `verified_writer_recorded_grade`, stage
`verified`. All paid/writer/generic jobs were skipped. That read did not call a
model or regrade; this coding task did not retrieve raw private grade content.

The consumed grade writer is `29e0353f1539265b1741e71be894fedf9be32a8b`,
run `36776393736` / `pilot-live` / attempt 1. Grade terminal
`40712e0980cc05c31688fdbb98c693774fb90c0d` has SHA256
`11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234`,
3119 bytes, and claim `dec305d669e3ca2e53c7f7b9ebfbe7974d661350`.

For keep/r1 cell
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1`:

| Recorded projection | Value and limit |
| --- | --- |
| Score | 30.6 / included possible 45 = 68.0%; full-denominator percentage 54.64% |
| Exclusions | 9 items, maximum score 11.0; the 13.36 percentage-point difference is a denominator effect, not treatment uplift |
| Task outcome | One scored task, no recorded task error; payload `run_status=diagnostic` |
| Coverage | `judge_items=49`, `rubric_items=40`, `passed_items=25`, `rubric_item_coverage=0.625`; recorded projection, not independent rubric revalidation or a validated quality explanation |
| Grader ledger | Present; 93 recorded model calls, `input_tokens=270190`, `cached_input_tokens=212025`, `output_tokens=16031`, `reasoning_tokens=10481` |
| Grader cost | Partial, `missing_reasons=[price_missing]`; known/model/estimated/runtime USD fields null, HTTP request count null, `invoice_complete=false` |

Cached input and reasoning tokens are subsets, not additions to their parent
token counts. Recorded model calls are not HTTP requests. No price or invoice
was reconstructed. Coverage and excluded items do not independently explain
the quality of this result.

The proof is
`verified_publication_derived_not_independent_provider_authentication`.
`materialized_input_fingerprint` remains `{status: unavailable, value: null,
comparison: null, reason: materialized_input_fingerprint_not_recorded}`.
The original result fingerprint, preparation digest and materialized grading
input remain distinct; this read does not fabricate an intermediate comparison.

### Fixed inference predecessor and remaining work

The successor cell is only
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r1`.
Its predecessor is the keep/r1 inference, not the grade or historical grading
parent: producer `e355faf9a6212175a288e8473968915ffb2408d0`, run `36696961231`,
request SHA256 `ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68`;
terminal `de50ff0aa6037c0ef6e3b713da519359abd1d08d`, SHA256
`0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8`,
6449 bytes; claim `3fc283087a020caec574e8c9b8e9bc3ca593e88a`; output
`43cbf8e265297813857172ecee51256cc17f2d36`. At live admission the unchanged
immutable predecessor contract must pass, and the actual shared inference
branch must equal that terminal before CAS. Drift or ambiguity refuses; no
claim reset, adoption, grade substitution or replay is allowed.

The registered order remains Task4 keep1/fresh1/fresh2/keep2, then Task5
fresh1/keep1/keep2/fresh2. Seven study cells remain unexecuted. The original
30-cell pilot is complete and is not reopened. This eight-cell study is
post-selected and not representative; one score is not evidence of benefit.
Two repetitions, service variation and an uncalibrated judge remain registered
limitations. The keep/fresh comparison changes the native-thread/owned-files
retention bundle under mechanical B, not the model, inputs, rubric, budget
policy or C feedback.
The decision rule still requires keep-only deliverable advantage in both pairs
within a predeclared task with no reverse pair. No recovery opportunity stays
in the denominator and is uninformative about retention.

GPT-5.4 direct-v1/xhigh, SDK/CLI 0.147.0 and original input/rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf` remain fixed. Mechanical B, no C,
the fresh bundle for ordinal 1, temporary carveouts and one concurrent inference
are unchanged. The 10800-second cumulative clock includes waits, recovery and
downtime without reset; 1800 seconds is the native-turn wait, not an all-in
attempt ceiling. There is no fixed admission count or automatic monetary cutoff.

The original-source and historical-record fixture boundaries are resolved in
the targeted offline proof. No production predicate changed for either fixture
correction. The guard-order correction now has separate targeted proof; the
failed CI above remains a failure. Immutable new-HEAD owner review and CI must precede any live
operation. The leader must then separately bind
the actual approved source/run/input/budget for exactly fresh/r1, with same-run
protected owner approval and reverified predecessor/CAS authority. No other cell
or additional budget decision is requested here.

### Preserved history and reporting scope

The successful read does not erase failed readouts `36801558936` and
`36811186015`. Their receipts, the separate 2.82s cwd proof, 8.85s diagnostic
proof, prior 7.20s/7.60s/7.82s synthetic failures, 40.06s/43.19s passes and CI
failure counts remain in the
[immutable prior completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/f30c9efa392bc14cba790fb5d1dedf12071a5677/tasks/LATEST_TASK_RESULT/README.md)
and its linked history. They do not become passes for this successor.

That history also preserves producer `36696961231`, verified intake
`36739260150`, the acknowledged grade, older bridge failures and the NAS
`explicit_hf_token_required` prerequisite refusal separately. Original inference
accounting stays partial: 10 recorded model calls, known cost USD `0.409894`,
runtime cost null, missing `call_reachability_unknown`, not grader accounting
or an invoice. Its original `grade=null` / `grading_launched=false` receipt is
not rewritten by the later grade and numeric readout.

The full catalog was checked once for this continuation. The prior
`experiment-design` constraints remain fixed; no treatment, budget, source pin,
sample or repeat changed. `experiment-report-en` updated only the bounded
CI-failure/guard-correction evidence, followed by protected
`im-not-ai-en` with denominators, exclusions, provenance, nulls and claims held
fixed. UI/animation, new-study and generic-framework skills were not applicable.

Older worktrees and records, `wip/local-main-preserved-20260719`, and the private
NAS refusal directory remain untouched. The leader's local M4 checkout is
unavailable and was not updated. No workflow dispatch, live HF/OIDC/Azure/model/
grade/readout, inference replay, permission change, Project edit or merge
occurred. These records stop at pre-merge facts.
