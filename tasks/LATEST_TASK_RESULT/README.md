# Latest substantive task result

## PROJECT5-GPT56-PILOT-INPUT-BUNDLE FULL-845D7218

The Foundry GPT-5.6 Sol pilot can now publish and verify an offline input bundle
from its sealed identity/config bundles and caller-supplied local bytes. The
bundle preserves the original pinned parquet and accepts only the reference
files required by the registered five-task cohort. Explicit preflight consumption
clears only the prepared-input requirement, not live inference identity or wire
consumption.

The sole selector reported `1 failed, 134 passed in 71.41s`, exit 1. Its one
incorrect drift test was corrected after the run and has not been rerun. Static
immutable review found no blocking defect, but a green execution result for the
correction still requires automatic CI. No local green result is claimed.

Both `launch_allowed` and `full_220_allowed` remain false, as do the active
contract's `launch_enabled` and `full_220_enabled`. The existing runtime template
remains `deployment: null`, `execution: null` and `runnable: false`.

### Scope and concrete outcome

`batch-runner/gpt56_pilot_input_bundle.py` exposes
`compile_pilot_input_bundle`, `materialize_pilot_input_bundle` and
`verify_pilot_input_bundle`, plus a small offline CLI. Each uses the real
`verify_pilot_config_bundle` to recheck #634 config/ready/reservation bytes,
the prepared-task manifest, #633 identity linkage, active contract and current
source pins. Optional evidence remains subject to the existing verifier; only
its sealed digest, reviewed source SHA and evaluation time are carried forward.
No raw external claims are copied.

The compiler reuses the existing dataset task selector, source projection and
reference-integrity helpers. It binds the dataset revision, original parquet
size/SHA256, exact five task IDs and order, prompt/rubric/projection hashes,
per-task reference roles/sizes/SHA256, run/condition/repeat and upstream bundle
identities. The active registration now pins 43 sources, up from 38. Its canonical
plan digest changes, so bundles tied to the previous plan are stale.

The absent run-local destination receives:

- `data/train-00000-of-00001.parquet`, copied byte-for-byte. It is not filtered
  or re-encoded into a different parquet artifact.
- The exact registered `reference_files/` closure. The current five-task cohort
  requires two files. Unselected references, extra files and extra directories
  are rejected; the shared full reference tree is not copied.
- `pilot-input-bundle-ready.json`, a canonical document binding those bytes to
  the verified config, prepared manifest, identity plan and source pins. It
  contains run-relative roles and digests, not host paths, raw prompts, resource
  identities or launch permission.

Publication uses the existing held-parent and atomic no-clobber primitives.
It first validates every input and destination relationship, then writes a
sibling reservation ending in `.pilot-input-bundle-reservation.json`, exclusive
directories and complete files. Before publishing the ready marker, it rechecks source
bytes, upstream bundles, installed bytes, exact membership and the reservation.
The verifier independently derives the expected bundle from current installed
bytes and rechecks the upstream and local files after derivation.

Source/destination overlap, traversal, duplicate or cross-task reference roles,
symlinks, hardlinks, missing/extra members, stale identities, byte drift and
existing targets fail closed. Interrupted files and reservations remain for
manual disposition. They are not deleted, overwritten or adopted on retry.
This unit creates no execution checkout, executable config, request, provider
client, inference result or grade, and it does not modify the source inputs.

### Closed preflight transition

The combined `live_identity_and_input_bytes_unverified` requirement is split
into `prepared_input_bytes_unverified` and
`live_inference_identity_and_wire_unverified`. Both remain in the no-bundle path;
the ten default blockers preserve the prior combined blocking meaning. Existing
plan-only report structure and serialization remain apart from this required
split and the changed active-plan digest.

Explicit input consumption requires the config and identity bundles and calls
the real input verifier. The closed `INPUT_BUNDLE_BLOCKERS` mapping clears only
`prepared_input_bytes_unverified`. Existing evidence and identity gates retain
their separate transitions. Live inference identity/wire, native host and actual
deployment blockers remain. The report records only the compact verified link
and `local_prepared_input_consistency_not_model_consumption` boundary. The full
success report is built before blocker mutation, so a late reporting error also
retains the prepared-input blocker. CLI errors use static, non-echoing refusals.

### Exact validation evidence

Exactly one pytest invocation was run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_pilot_input_bundle.py
```

It collected 135 cases under Python `3.10.12` and pytest `9.1.1` and reported
`1 failed, 134 passed in 71.41s (0:01:11)`, exit 1.
`test_upstream_current_bytes_are_reverified[source-plan]` appended a YAML newline
and expected contract drift. The active contract uses canonical JSON semantics,
so whitespace did not change its identity and acceptance was correct. The
retained case now changes `pilot.run_id` to `stale-run` and keeps the refusal and
no-write assertions. All 135 cases remain; none was removed, skipped or marked
xfail. No production code changed after the invocation. The test-only correction
is in the reviewed implementation HEAD but has not been executed locally.

The case set covers no-evidence and evidence-linked bundles; exact ordered
five-task projection and original bytes; no-bundle compatibility and the one
prepared-input transition; wrong/stale/missing/extra/tampered data, sources and
markers; forged matching hashes; invalid roles and overlap; links, traversal and
collisions; each publication write failure; partial reuse; mid-publication drift;
held-parent replacement; late report failures; privacy-safe CLI errors; source
immutability, seed isolation and false launch flags.

Fixtures use real config/identity/evidence verifiers and source/reference
validators. Module-scoped lazy seeds share immutable bytes, with fresh
single-link copies for each case and a defensive byte-keyed YAML parse cache.
No validator verdict is mocked or cached. Tiny synthetic parquet/reference data
and committed five-task prompts avoid scanning the live 220-task snapshot.
Offline guards prohibit subprocess, network, provider auth, model/client/grader
construction and grader execution. The #631-#634 selectors and broad/full suites
were not rerun. No manual workflow ran.

`git diff --check` and `git diff --cached --check` passed before the implementation
commit. These are synthetic local fixture and static-review results, not a
successful workflow, model consumption, Foundry capability or paid run.

### Immutable base and review boundary

The clean development worktree started from main
`845d721886e599b06077da8f3524db9cba8520f0` on
`b/gpt56-pilot-input-bundle-20260920`. The preserved checkout
`wip/local-main-preserved-20260719` was not used or edited.

Implementation review HEAD: `9a87cc143fa6b2ca75eba589bcd15c795bdd55d6`.
The nine implementation/config/test files below form the immutable review
boundary. `first-reviewer` returned APPROVE with no BLOCK, MAJOR or MINOR findings
and no second-review escalation. `llm-systems-engineer` found no high-confidence
production blocker at the same HEAD. Both confirmed the canonical-contract test
correction and explicitly withheld any claim of a green selector. Reviews were
read-only, without tests, production imports, external calls or file changes.
This record and `CHANGELOG.md` are subsequent documentation changes outside that
implementation review boundary.

The repository's existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without changing Git
configuration. No attribution trailer, hook bypass, history rewrite, force push
or forbidden Git cleanup was used.

### Changed files

- `batch-runner/gpt56_pilot_input_bundle.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/tests/test_gpt56_pilot_input_bundle.py`
- `batch-runner/tests/test_gpt56_evidence_preflight_gate.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

Changes to the older test files are limited to exact source-count and split-blocker
expectations. Their selectors were not run.

### Skills and roles

The full skill catalog was checked once, and `experiment-design` was used before
planning or code. Its distinction between an input contract and observed model
consumption kept this unit limited to local prepared-input consistency. No model,
effort, task cohort, attempt, grader or experiment axis changed.

`llm-systems-engineer` provided read-only contract/fixture assistance and the
immutable systems review. `first-reviewer` reviewed the implementation HEAD.
Grading implementation is unchanged; no new grading-role task was needed.
`im-not-ai-en` was applied to the English changelog, completion record and PR
wording while preserving the measured failure, unexecuted correction, hashes,
commands and evidence limits. `extreme-reasoner` does not apply because workflows,
`core/qa.py` and HF upload are unchanged. UI/animation skills are unrelated to this
backend byte-bundle contract and were not used.

### Evidence boundary and remaining work

This implementation binds local prepared-input consistency only. It does not
prove that a model consumed these bytes, authenticate external Foundry facts,
issue inference identity, or authorize launch. No real evidence bundle was
accepted outside synthetic fixtures in this task.

Remaining work includes actual external evidence acquisition and independent
review; live inference identity, input consumption and wire binding; separate
executable-config materialization with a reviewed deployment name; execution-time
grading scope and generated-config source identity; native sandbox/result-bundle
hosting; actual deployment and pilot execution; runtime enforcement of native
caps; and usage/tariff receipt integration. Both launch flags remain false.

No Azure API/CLI or HF calls, credential/OIDC lookup, provider/model/client
execution, inference, grading, download, workflow dispatch or paid execution
occurred. Production runtime/grader defaults, exp035 configs, workflows,
`core/qa.py`, HF upload and historical ledger/evidence bytes are unchanged.
Project updates and merge decisions remain with the leader. This record contains
pre-merge facts only, with no carrying-PR merge SHA, time or state.
