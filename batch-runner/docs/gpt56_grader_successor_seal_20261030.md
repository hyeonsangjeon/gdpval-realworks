# Reviewed successor grader seal — 2026-10-30

Owner option **A**, recorded in the card at **2026-10-30 14:15** and delegated
by the leader at 15:00, authorizes a reviewed successor seal and branch/Draft-PR
publication. It does not change model settings, costs/refusals, or authorize a
model call. The instruction does not specify a timezone for those two times.

### Integration after #795 and #796

Rebased on main `c6fcacaf1e9d52e9dfc94a625ddfa0a694eb45df`. The source chain is
now `capture_counters → list_prices → long_context → grader_seal`. The immediate
predecessor is `gpt56_sol_foundry_codex_pilot_source_20261030_long_context.yaml`,
SHA256 `0d957f81d2c6d82a79fa1db7ff86b21d3a6ec609011787585f93fca8b63f62b1`.
Both preceding transitions keep their exact byte hashes, non-source field
equality checks and changed-file allowlists. The last transition changes only
the preflight reader pin and reviewed grader-template identity.

#795's list-price fallback and unknown-usage booking, #796's held 1M catalog
and `not_reported` context behavior are inherited without reimplementation.
USD 200 and ledger-integrity stops remain. Those implementation files and all
predecessor profiles are checked against the merged main by offline tests.
Neither PR changed any file in the sealed Step8/core closure, so the grader
hash and the original 1a5841ee manifest remain unchanged. The manifest's
`missing_price_or_usage_refusals_unchanged` is a historical statement about
the original ⑦A change at `0140b4c12`, not an instruction to undo owner item 2.
The separately held active financial helpers determine today's policy.

To preserve the published #794 head without a forced update, retain
`d714be0e0208643f757e83619ec975b1bc5cae23` as a parent of a tree-identical
ancestry-connection commit after rebase. Publication is a normal fast-forward
push; no source resolution is delegated to that connection commit. PR merge,
workflow dispatch, model/judge calls and NAS benchmark execution are excluded.

## Identity and unchanged conditions

- Frozen source: `8ac891e3e0e4752fe15a00139a2691ddf9df7dce`;
  grader hash `47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf`.
- Original closure-review main: `0140b4c125093dc04de9ca0814387c140a929a59`;
  successor hash `099755b009e7563e5b3824ac34c1ab2cf5c83b3cdf4aba7886b50e1c28003fd7`.
- New manifest: `experiments/execution_envelope/gpt56_sol_grader_seal_20261030.json`.
  Its SHA256 is `1a5841eed8f7acbdbfdc71d2810b5e6acc5d3b4f87edae8d88cb4bc420150915`.
  It contains both complete filename/SHA256 manifests and the exact **11-file**
  delta (**9 modified, 2 added**). Tests recompute both fingerprints from Git.
- All historical registrations retain their bytes. The new source profile
  `gpt56_sol_foundry_codex_pilot_source_20261030_grader_seal.yaml` changes only
  the preflight reader pin and `dispatch_grading_identity.grader_template_source_hash`.
  The `grading.source_sha` remains the original template's provenance, not a
  claim that today's runtime source equals that historical commit.
- Sol (not Fast), Max, prompt v2.2, rubric revision
  `11e7900cdcac61bc4daf59e65feb238acda98fbf`, ordered five-task selection,
  USD **200** combined inference/grading ceiling stay fixed. The rebase preserves
  the separately approved #795/#796 policies described above.
  The original null cost field is not repurposed: the existing hash-bound
  USD-200 companion record remains the runtime decision.

## File-by-file classification

The classification is conservative: **impact** includes admission/stopping or
input-state changes, not just changes to a score formula. **No score impact**
means no change in this native pilot's score path, not identical behavior in
the separate time-budget study. There are **6 impact / 5 no-score-impact** files.
Line references below are to the reviewed main; this PR does not edit them.

| File | Class | Evidence | Effect |
| --- | --- | --- | --- |
| `step8_grade.py` | Impact | 2528, 3455 | USD/runner refusal stops grading; retain completed tasks, never fabricate an interrupted verdict. |
| `core/cost_metering.py` | Impact | 888, 949 | Reserve before judge dispatch, settle afterward; financial refusal is run control. |
| `core/grader.py` | Impact | 369 | Wrap judge/perception/retry clients with per-request runner admission. |
| `core/runner_environment.py` (new) | Impact | 93, 139 | Unapproved/changed host stops before a request, outside the rubric error path. |
| `core/codex_runner.py` | Impact | 849, 1052, 1556 | Native admission/capture and optional retention can affect inputs; pilot refuses retention/observation co-use. |
| `core/codex_task_deadline.py` | Impact | 96, 601 | Fresh-retention can retire workspaces/outputs in its separate study; legacy A/B/C identity is preserved. |
| `core/grade_payload.py` | No score impact | 27 | Validate additive runner/shard metadata; scoring/denominator formulas unchanged. |
| `core/agentic_v2_conversation.py` | No score impact | 826 | Optional V2 observation supervision, not selected by the native pilot. |
| `core/agentic_v2_conversation_runner.py` | No score impact | 308 | V2 observation/capture cleanup path; no Step8 change. |
| `core/agentic_v2_runner.py` | No score impact | 536 | V2 deadline/cleanup integration, not the native pilot's harness. |
| `core/time_budget_observation_deadline.py` (new) | No score impact | 1, 148 | Opt-in controller for another study; no native-pilot/shared-grader activation. |

The rubric/prompt/schema/install-graph/download-helper bytes are unchanged.
The new validator adds no file to Step8/core, so the reviewed grader hash does
not change during this PR. It checks new/missing source files, unsafe paths,
the complete current fingerprint and final rereads. The existing registration
guard additionally requires a clean supplied full Git commit, archives every
held source (including the validator/manifest), and rechecks bytes/import origins.
An arbitrary replacement hash, altered prior seal or unreviewed core file refuses.
The existing identity compiler validates the successor grader component; the
old profile still refuses the new grader bytes. Full identity/config/input
publication still requires its independent complete evidence bundle: without
that bundle the compiler now reaches `complete_evidence_arguments_required`,
not `grader_template_source_drift`. This requirement is not waived.

## Offline equivalence and safety checks

`tests/grader_guard_scope_probe.py` runs the same fake client/replies and fixed
deliverable against the actual archived old source and the current source with
the USD guard enabled. Network and subprocess effects are denied inside each
child. Synthetic hosted-runner metadata is explicitly not NAS launch authority.

Three reply cases (pass/fail/partial) compare the complete serialized request,
item verdict, denominator, score, five aggregation rows and summary JSON.
The five rows include constructed penalty and judge-error aggregation examples;
they are not five real GDPVal results. The real nullable tool schema
`scope.type=["object","null"]` is retained. The pure Codex input prompt and six
legacy A/B/C control serializations are also compared without starting Codex.
Separate guard tests keep USD-ceiling stops out of judge_error and
preserve source=grading, exit 4 and previously completed task checkpoints.
Missing usage follows the separately approved full-reservation booking policy.

An independent AST comparison also found identical `_compute_summary` and
`_task_to_dict` (Step8), and `_aggregate` and `_judge` (Grader), at the old and
reviewed sources. This is a code-structure comparison, not a billing claim.

Initial focused invocation: **34 passed / 0 failed / 0 skipped** (22.31s).
The first clean-source proof had one fixture failure: it expected full identity
compilation without the required upper evidence bundle. The corrected assertion
separately checks the valid grader component and that mandatory refusal.
An initial broad invocation used system Python without the pinned Codex SDK;
its missing-package failures were not waived. Final validation uses the existing
isolated pytest 9.2.0 / openai-codex 0.147.0 environment, read-only, with empty
inherited environment and offline Hub settings. No requirements were changed.
The complete selected invocation (both CI pilot-contracts commands, all grader
files, deadline and new seal/source guards) ran **3,683 cases**: **3,670 passed,
13 failed, 0 skipped**, in **5702.66s**. All 13 failures were the existing
scripted selector/tool-dispatch tests lacking synthetic runner metadata, so
the unchanged production guard correctly refused NAS with
`execution_environment_refused`. Add the existing synthetic hosted-runner
fixture and explicit network denial to those **two test files only**; retain
every scoring/selection assertion and the actual admission check.

The entire grader/metering plus USD/runner/seal recheck then passed **869 cases,
0 failures/skips**, in **111.38s**. The separate preflight selection passed
**198 cases**, 0 failures/skips, **143 external-live cases deselected** as in CI,
in **1111.95s**. Across those three XML files, use the **latest result per test
identity**, not a sum of reruns: **3,881 distinct cases passed, 0 failed/skipped**.
The initial 13 failures remain in their original XML/log. The complete run also
passed the clean-commit registration test; final publication requires another
clean-source check, recorded with its final HEAD in the PR/local handoff.
Logs/JUnit: `/ai-work/copilot/_tmp/p5-grader-seal-20261030.dX3prg/`.

## Limits and concurrent work

This is not a replay of actual five-task judge records. It does not establish
equal stochastic solver outputs, scores across arbitrary inputs, actual billed
costs, or Foundry's applied 1M context. Intentional budget/host refusals remain
possible; a stopped run is not a low model score.

Owner decisions 2 (price/unknown-usage policy) and 3 (applied 1M), and PR #793,
are owned by Claude. #795/#796 are now inherited, not rewritten here; #793 is
not modified or merged by this work. If later work changes Step8/core or any
other source in this closure, this successor must refuse until reviewed and
resealed again. Changes to separately held USD/price helpers also require a
new reviewed source registration; merging is not an automatic hash waiver.
No model/judge/paid call, workflow dispatch, secret access or merge was performed.
