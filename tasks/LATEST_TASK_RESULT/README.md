# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Codex Grading-Input Materializer

### Scope and Outcome

`materialize_codex_grading_input` validates existing Codex step2 results and
deliverables, then installs an isolated canonical step8 input bundle. It
reuses the dispatch/grading compilers and #620's validation, byte snapshots,
descriptor-anchored staging, and native no-clobber rename. It does not execute
inference or grading, materialize a checkout, or authorize a launch.

Work started from immutable main
`f85da3f87550abc335c9365e9bca22372747f1e4` in branch
`b/gpt54-codex-grading-input-materializer-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-codex-grading-input-materializer-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly eleven files differ from that base:

- `batch-runner/gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Binding and Compatibility

The caller supplies an exact Codex `ComparisonGradingRunSpec`, manifest,
actual step2 JSON and upload root, separate inference identity document,
externally approved document SHA256, and absent destination. The function
recompiles the plan and checks the run, condition, repeat, ordered five-task
scope, producer path/pointer, manifest and combined-plan fingerprints, config
and source pins, original JSON digest, result fingerprint, runtime/prepared
identities, and task-owned deliverable paths, sizes, and hashes. The document
must name a canonical inference repo and immutable revision. Dataset or Git
provenance cannot substitute for that identity. The external issuer must
verify publication and prepared-input provenance; this function checks only
the approved offline binding.

The real producer's `experiment_id` matches the deterministic comparison run
ID. Its opaque `run_id` and `publication_generation` are validated and bound
separately, without inventing a prefix requirement. The producer condition,
model, execution mode, terminal cardinality/status, and task order must match.
Missing, duplicate, extra, reordered, nonterminal, resumed, retried, or
contradictory rows are refused before staging. Terminal errors remain errors.
Unsafe paths, symlinks, hardlinks, empty/missing/extra/cross-task files, changed
bytes, and destination collisions are refused.

Raw Codex rows are validated through existing helpers, including
`project_result_row`, but are not replaced with report projections. Absent
and present-null receipts remain distinct. Partial reasons and original
receipt fields survive unchanged. In the reserved-call fixture,
`estimated_cost_usd` remains null; the existing `known_cost_usd: 0.0` is a
confirmed floor, not a zero-cost total. No pricing or arithmetic is changed.

The output adds the approved `source_repo_id`, `source_revision`, and
`source_identity_document_sha256`, then recomputes its result fingerprint
with the existing helper. Conflicting pre-existing identity fields are
refused. Every other source field retains its JSON semantics. The original
digest and fingerprint remain bound in the approved document. When the
producer references `cost_ledger_condition_a.jsonl`, its separately bound
sibling bytes are copied unchanged beside the output JSON. Absent/null
references remain absent/null and produce no sidecar.

All input bytes are read and validated before private sibling staging. The
bundle contains the existing `batch-runner/workspace/step2_inference_results.json`
and `batch-runner/workspace/upload/deliverable_files/<task_id>` paths, plus the
optional bound producer ledger. Native `renameat2(RENAME_NOREPLACE)` is required;
there is no unsafe fallback. The real step8 local loader, source identity
resolver, ordered task filter, result fingerprint validator, and deliverable
validators read the fixture output.

The shared installer's optional ledger argument defaults to `None`. That
default preserves V2 serialization, tree contents, descriptor anchoring,
cleanup, and atomic-install behavior. Thirteen existing V2 cases are reused
without weakening their assertions. The only edit to the V2 test updates the
source-pin count from 23 to 24. The Sol YAML only refreshes its existing shared
parser digest; its contract and launch gates are unchanged. The existing
grader source-closure digest remains
`c10ea303f212bab87ea6303cb41ee51e21430e6bc35df7a69b9a63d265f3a241`.
Production runtime/grader defaults, schemas, and historical ledgers/evidence
are unchanged.

### Exact Verification Evidence

Only this selector was run, once initially and once after the immutable
review confirmed two blocking test defects:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_codex_grading_input.py::test_codex_grading_input_preserves_source_and_v2_boundary
```

- Initial implementation, preserved at
  `0299a60c7971a513144ae761ca9c2f5eda3226e5`: `8 failed, 106 passed in 68.56s`.
  Six positive cases incorrectly expected a null known-cost floor. Two error
  fixtures eagerly indexed an empty deliverable-record list before reaching
  the materializer.
- Corrected implementation, committed at
  `373a39fd23b9adc6dc6b30db9ca03675565916b6`: `114 passed in 72.92s`.
  This was the single permitted corrective rerun. Only those two test defects
  changed; production implementation bytes and source pins did not change.

The selector covers both Codex repeats, preserved terminal/all-error rows,
opaque runtime lineage, identity/pin/plan/result drift, receipt preservation,
ledger binding, unsafe file trees, collisions, and cleanup. It also calls 13
existing V2 regression cases within this same selector, including parent
replacement, write/rename failure, and native capability checks. The old V2
selector was not run separately.

Successful deterministic installs use an explicit test-only primitive double.
The separate native cases reported:

```text
Codex native RENAME_NOREPLACE unavailable (errno 22); refused without residue.
Native RENAME_NOREPLACE unavailable (errno 22); refused with no destination or staging residue.
```

This NAS demonstrated safe refusal, not native installation success. A host
with working native no-clobber support is still required. Subprocess, network,
provider authentication, route preflight, grader/rubric-loader construction,
typed Azure client creation, and cost-recorder construction are forbidden by
the fixtures. No broad suite, standalone preflight, build, live call, actual
experiment, credential lookup, workflow dispatch, or Project edit ran.

`git diff --check` passed. Scope inspection against the immutable base found
no production runtime/grader, schema, workflow, historical result, or ledger
changes. The preservation checkout remained clean at
`ab6a001912898250a6c33d6ed7555cc50ba04c95`.

### Immutable Review Boundary

The read-only `first-reviewer` audit of
`0299a60c7971a513144ae761ca9c2f5eda3226e5` returned `REQUEST-CHANGES` for the two
test defects described above. It found no additional high-confidence
implementation defect and requested no escalation. Both corrections are in
the new commit `373a39fd23b9adc6dc6b30db9ca03675565916b6`; no commit was amended.
The read-only corrective review of that exact HEAD returned `APPROVE`, with
no remaining BLOCK, MAJOR, or MINOR findings and no escalation requested.
The reviewer did not rerun tests or execute production, network, or auth paths.

Only this record and `CHANGELOG.md` differ from that corrected implementation
HEAD. Approval covers that implementation only. Leader review and automatic
CI evidence remain pending. No approval of these later records or the live
gates, carrying-PR merge result, or future merge SHA/time is claimed.

### Remaining Work

This unit closes only Codex grading-input/deliverable validation and isolated
placement. The four-run ABBA matrix, five-task cohort, Foundry GPT-5.4 identity,
common `xhigh` request, limits, grader, and result/receipt contracts remain
fixed. Both `launch_allowed` and `full_220_allowed` remain false.

- External inference identity issuance, approval, and prepared-input
  provenance verification.
- Native no-clobber support on the materialization host.
- Actual checkout/config materialization and workflow gates.
- Served V2/Codex capability, native call/token caps, and live model/input bytes.
- Usage/tariff evidence under the existing record-only null/partial policy.
- The separate Sol pilot's Copilot provider/auth route, blocked because no
  official runtime-to-Codex handoff contract has been established.

The generic `comparison_materialization_and_workflow_gates_not_wired` blocker
remains. This unit adds no launch command, guessed authentication bridge, or
guard for every paid entrypoint.

### Skills and Roles

The full available skill and repository-agent catalogs were inspected once
before editing. `experiment-design` was applied before code or plan changes
to preserve task/input pins, repeats, units, comparison scope, and stop gates.
The consolidated grading specification and stable `tasks/grading_task`
baseline were read first. The required `grading-engineer` role audited the
producer, projection, identity, and local step8 boundaries. Its working-code
audit caught the unsupported runtime-ID prefix assumption, which was removed
before the initial selector. `first-reviewer` reviewed immutable implementation
HEADs. These roles used the available engine, not an external paid model call.

`im-not-ai-en` was applied to the English changelog, completion record, and PR
wording. Commands, SHAs, counts, results, and limitations were checked manually;
the owner's restricted validation scope takes precedence over an additional
fidelity-script run. Experiment-report skills do not apply because this task
reports no measured experimental outcomes. Repository-readiness, UI, and
animation skills do not apply to this existing offline input boundary.
Workflows, `core/qa.py`, and HF upload scripts are unchanged, so no
extreme-reasoner scope was created.

## Prior Result: #620 V2 Grading-Input Materializer

[#620](https://github.com/hyeonsangjeon/gdpval-realworks/pull/620) added the V2
materializer reused here. Its reviewed implementation was
`4a656026c81453a4b6f9a86bbe27db23deaf373b`, and its final branch HEAD was
`5a550bb736648b8b085251298a262dccd58dbfd5`. Its historical selector reported
`79 passed in 48.22s` after review corrections; first-reviewer returned
`APPROVE`. Native installation on this NAS was refused with errno 22 without
residue. That historical result is not a new test run.
