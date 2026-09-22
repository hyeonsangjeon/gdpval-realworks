# Latest substantive task result

## PROJECT5-GPT54-STEP0-MANIFEST-FIX-1016

GPT-5.4 Codex preparation now requires an explicit local canonical Step 0
manifest before it can report ready. The input bundle copies its full bytes
to `batch-runner/workspace/step0_needs_files_manifest.json`, records its size
and SHA256, and verifies the installed bytes with the unchanged canonical
validator. The accepted prior real Step 1 exit 1 was not reproduced or retried.

The feature starts from `778a627bbb5404f33e5e62019382fa107aa47840`.
Tested implementation commit: `8728c350266578c299dd64b974f9368288de09d7`.
This later records update is outside the tested implementation commit.

### Implementation and preserved boundaries

The input materializer, disposable-checkout API/CLI and workflow helper accept
the explicit `step0_manifest` / `--step0-manifest` source. Codex refuses missing,
unsafe or incompatible sources before reservation/readiness. V2 still requires
no Step 0 input. Publication retains no-clobber, no-links, held-parent,
reservation/partial retention and ready-last protections. Verification rereads
the installed file and does not trust a marker's digest alone.

The unchanged `deliverable_only` policy requires schema 4 and canonical SHA256
`463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512`.
The selected source projections, reference records and deliverables must agree.
The full canonical manifest is retained; a generated five-task substitute is
not accepted. The fixed task order, controls, repeats and limits are unchanged.
No bootstrap/download orchestration or ambient-workspace discovery is used.

The GPT-5.4 source closure now has 36 pins, including the two existing canonical
reader modules. Directly coupled Foundry shared-source digests and the GHCP
test's Foundry digest were refreshed without changing their behavior or
assertions. Documentation and related fixture callers were updated. Step 1,
the canonical consumer/validator, QA, HF upload code and workflow YAML are
unchanged. Existing hosted workflow lanes do not supply this new source and
remain fail-closed; hosted preparation is not established by this fix.

### Focused evidence

One invocation on the tested implementation commit, exit 0:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt54_run_input_bundle.py batch-runner/tests/test_gpt54_disposable_checkout.py batch-runner/tests/test_gpt54_workflow_gate.py batch-runner/tests/test_gpt54_comparison_preflight.py -k step0_manifest
```

Result: `45 passed, 319 deselected in 18.36s`. No targeted failure or rerun
occurred. `git diff --check` passed for the implementation.

The integration case uses synthetic parquet, references and a canonical-manifest
fixture with explicit test-only pins. It exercises the actual materializer,
local pyarrow loader, `NeedsFilesManifest.load()`, schema/digest/source checks
and Step 1 serializer/capture, emitting the five ordered tasks and matching
prepared fingerprint and capture. The full supplied manifest includes an
unselected fixture entry, so the test also checks that publication does not
reduce it to the selected cohort. Consumer checks were not stubbed away.

Other selected cases cover V2 without a manifest, API/CLI forwarding, missing,
tampered, linked, collided and partial inputs, unsupported schema/policy,
projection/reference/deliverable drift, held-parent swaps, ready-last
publication, current-byte verification, forged-marker refusal, source pins
and unchanged blockers/flags. Workflow helper tests use synthetic request
metadata only; no workflow was dispatched.

This is synthetic integration evidence, not a new real-data preparation or
real Step 1 success. Original sources, real prepared checkouts, readiness
markers, private handoffs, failed outputs, caches and the GHCP bundle were
left untouched. No model/provider, Step 2, VM, grader, paid, Azure/HF or
credential operation ran. No full suite, manual workflow or real-data retry ran.

### Review boundary and remaining work

The leader's `FINAL-APPROVE` review `5273344624` at
`259f50567e95c07b720ac51a3f020453fad449bf` covers only the preceding operational
records. It does not review this implementation or authorize execution.
PR #646 and its branch remain frozen. This fix still needs implementation
review and fresh final-HEAD automatic checks; no new implementation approval
is claimed.

The single authorized `git fetch --no-tags origin main` returned 0 and found
main still at `778a627bbb5404f33e5e62019382fa107aa47840`. No integration merge
was needed. This fix is published separately after the preceding frozen
records PR; the leader controls review and merge ordering. The fetch was
GitHub source traffic, not a provider experiment.

A future separately authorized real preparation needs an explicit local source
containing the existing policy's canonical manifest bytes. No such source was
sought or acquired here. No old partial is repaired or adopted. The six
preflight blockers remain:

```text
v2_reasoning_effort_capability_unverified
codex_reasoning_effort_capability_unverified
codex_native_model_call_and_token_limits_unenforced
live_deployment_identity_and_input_bytes_not_verified
comparison_materialization_and_workflow_gates_not_wired
comparison_usage_and_tariff_evidence_unverified
```

All launch flags remain false. There is no provider, grading, cost, capability
or comparison-performance evidence and no Project-card completion claim.

### Skills

The full catalog was inspected once. `experiment-design` preserved the
registered controls and the local input/consumer acceptance boundary.
`llm-systems-engineer` repository guidance informed the backend change;
it was not a separate immutable review. `experiment-report-en` and
`im-not-ai-en` preserved the evidence and review limits in these records.
No workflow edit required `extreme-reasoner`. UI/animation, repo-readiness,
grading and new-framework work do not apply to this correction.
