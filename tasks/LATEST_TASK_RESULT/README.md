# Latest substantive task result

## PROJECT5-GHCP56-LOCAL-INPUT-BUNDLE

Implemented local staging and verification for the registered GHCP Codex
GPT-5.6 Sol five-task inputs. The new library and CLI copy the whole pinned
parquet unchanged and only the selected tasks' reference files. They preserve
the original developer instructions and deliverable/grading metadata without
creating a runtime or inheriting a full-220 run identity.

The new worktree starts at `788828790798c4dbcaff1c75aeb178d789573e03`.
Implementation changes are limited to `batch-runner/ghcp_vm_input_bundle.py`,
the optional input-bundle path in `batch-runner/ghcp_vm_gate_preflight.py`,
the GHCP plan's directly consumed source pins, and
`batch-runner/tests/test_ghcp_vm_input_bundle.py`. The plan now binds nineteen
source files. Shared helpers, the superseded Copilot record, all Foundry and
GPT-5.4 code/contracts, workflows and the GHCP workflow-digest constant are
unchanged. The new lightweight test file stays in core pytest.

### Local publication and evidence boundary

The caller supplies a local parquet file, a root containing the existing
`reference_files/` layout, an absent destination with an existing parent, and
the reviewed canonical GHCP plan SHA256. No input discovery or download is
provided. Before publication, the module checks the entire parquet hash, exact
five-task order and prompt hashes, selected reference closure and hashes, and
current source pins. Only the selected references are read; unrelated source
members are not scanned or copied.

The publisher creates a sibling reservation, exclusive directories and files,
then `ghcp-vm-input-bundle-ready.json` last. The manifest binds the GHCP
condition, reviewed plan/source identity, ordered tasks and file sizes/digests.
Verification reconstructs it from published bytes and current pins rather than
trusting saved claims. Held parents, single-link regular-file reads and repeated
byte checks refuse traversal, overlap, links, collisions, drift and partial
adoption. Failed partials and reservations remain for quarantine; the caller's
content is never overwritten or silently repaired. CLI refusals contain the
static `ghcp_input_bundle_refused` code, not paths, prompts or exception text.

With no bundle, preflight retains its fifteen blockers, null observations and
six false execution flags. Explicit verification may satisfy only
`original_task_input_materialization_unverified`, with the boundary
`local_input_materialization_not_vm_or_model_consumption`. Every other blocker
and null observation remains. Preflight still exits 2, and all launch, paid and
full-220 flags remain false. Malformed, stale, foreign or partial bundles grant
no readiness.

No real pinned inputs were supplied or sought. Tests staged synthetic fixture
bytes only. Their success is not actual dataset staging, VM reset/capture,
served-model identity, model consumption, grading accuracy or paid readiness.
The real GHCP preregistration therefore still has all fifteen blockers.

### Local CLI

These are offline file operations, not launch commands. Supply the existing
reviewed preflight report's canonical `plan_sha256` and explicit local inputs
through the variables below; no auth values or endpoints are accepted.

```bash
/usr/bin/python3 batch-runner/ghcp_vm_input_bundle.py \
  --reviewed-plan-sha256 "$GHCP_REVIEWED_PLAN_SHA256" \
  --dataset-parquet "$GHCP_LOCAL_PARQUET" \
  --reference-root "$GHCP_LOCAL_REFERENCE_ROOT" \
  --destination "$GHCP_INPUT_DESTINATION"

/usr/bin/python3 batch-runner/ghcp_vm_input_bundle.py \
  --reviewed-plan-sha256 "$GHCP_REVIEWED_PLAN_SHA256" \
  --verify-bundle "$GHCP_INPUT_DESTINATION"

/usr/bin/python3 batch-runner/ghcp_vm_gate_preflight.py \
  --local-input-bundle "$GHCP_INPUT_DESTINATION" \
  --reviewed-plan-sha256 "$GHCP_REVIEWED_PLAN_SHA256"
```

The bundle CLI returns 0 only after local publication or verification succeeds;
refusal returns 2. The preflight command always returns 2. These commands were
not run against real inputs in this task.

### Exact validation and review boundary

The initial focused invocation and one necessary correction rerun used this
same selection:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short \
  batch-runner/tests/test_ghcp_vm_input_bundle.py \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_valid_fixed_five_is_still_blocked \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_request_is_not_an_observation \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_original_input_deliverable_and_grader_pins \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_cli_is_canonical_read_only_and_nonzero \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_source_pin_set_is_closed \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_bad_source_bytes_refused \
  batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_unknowns_cannot_be_self_asserted
```

The initial result was `83 passed in 31.47s`, exit 0, on the bytes committed as
`bb87f9a618001f9b6cc84e5c1f2c248f7cf2e55d`. Its immutable `first-reviewer`
verdict was REQUEST-CHANGES. The writer reopened its parent path after the
caller's checks, allowing a replaced destination to receive ready alone and
return success. That is a publication defect, despite the passing initial
selector.

The correction binds every write to the caller-held parent descriptor and
checks directory identity through publication and before successful return.
Six new cases replace actual directories at reservation, parquet, reference,
manifest and ready boundaries, including replacement just after the ready
writer returns. Replacement destinations receive no ready, publication refuses,
and quarantined bytes remain without adoption. The authorized targeted rerun
reported `89 passed in 33.08s`, exit 0, covering 81 input-bundle cases and eight
directly affected fast GHCP contract cases.

Each mutation case uses fresh local files and fixture-local pins. The real
parquet parser, publication path, plan checker and byte verifier run under
process/network/provider/grader guards; those behaviors are not replaced with
mocks or cached verdicts. `git diff --check` and the staged whitespace check
passed after the correction. No heavy selector, contract job, full suite,
build, benchmark task, grader or manual workflow ran.

The corrected tested bytes are committed as
`d92e72b2fc76510929b961c8103a8d2d6ed4e02c`. Read-only `first-reviewer`
review returned APPROVE with no findings on that immutable implementation HEAD,
confirming the earlier publication BLOCK is resolved. Review used Git objects
without test reruns or network access. The following records-only commit is
outside the four-file implementation-review boundary.
Fresh final-HEAD automatic checks remain required and will be read once after
the normal push, without waiting or polling.

### Skills and remaining work

The complete skill catalog was inspected once. `experiment-design` fixed the
question to exact local input identity: missing or drifted bytes falsify the
claim. The same five tasks, original prompts and GHCP Sol/Codex/Max/1M request
remain; Foundry is a separate condition, and no performance comparison is made.
Repeats, variance, auth, runtime limits and costs stay unresolved. Grader pins
establish source consistency, not judge accuracy. The stopping point is before
network/model spending.

`llm-systems-engineer` implemented the new local input module;
`first-reviewer` owns the immutable review. `im-not-ai-en` was applied to the
English records while preserving commands, results, SHAs and evidence limits.
Neutral integrity/source/hash helpers are reused. Importing the existing
GPT-5.4 snapshot and publication helpers would pull in Step 1 and HF dependencies,
so the new module uses the established held-parent/no-clobber pattern locally
without a shared-helper refactor or a fabricated Foundry chain. UI/animation,
grading, repo-readiness and extreme-reasoner do not apply: no interface, grading
behavior, repository-publication audit or workflow boundary changed.

Real local staging remains unperformed. Even after it succeeds, fourteen
requirements remain: served identity, Max/1M capability, CLI/harness versions,
auth supply/disposal, VM image/OS/package policy, fresh reset, network/permission
policy, enforced execution limits, repeats/variance, five-task time/cost caps,
GHCP-native usage/missing-usage policy, transcript/tool/command/file/exit capture,
grading result wiring and grader validation. No decision is invented for these
requirements, and no launch permission is granted.

The existing author/committer identity
`hyeonsangjeon <wingnut0310@gmail.com>` is preserved without attribution
trailers. No Azure/Foundry, provider/model/client, personal account, GHCP login,
VM, HF, credential, grader or paid execution occurred. No Project edit or merge
action occurred. This record stops at pre-merge facts.
