# Latest substantive task result

## PROJECT5-PR634-DEPLOYMENT-NAME-SEPARATION

PR #634's runtime artifact now separates the requested model label from the
deployment name. It is a closed template with `deployment: null`,
`execution: null` and `runnable: false`, rejected by the existing runtime parser
and Step 1 entrypoint before provider/auth setup. The correction selector ran
once and reported `129 passed in 23.26s`, exit 0. All original 108 cases remain,
with 21 regressions added.

The original config-bundle scope is unchanged: a verified #633 identity bundle
becomes four exact canonical files and a ready marker, without deploying or
executing the fixed Foundry GPT-5.6 Sol Codex pilot. Grading generation and the
exact ordered five-task scope are unchanged.

Both `launch_allowed` and `full_220_allowed` remain false, as do the manifest's
`launch_enabled` and `full_220_enabled`. Ready means local config consistency,
not launch permission, served capability or actual input consumption.

### Leader BLOCK and correction

The leader blocked PR #634 at
`b872446d6e61cfaa8fa1558ee94ea4a6b4ff67ea`. `_runtime()` put the requested
`identity.model` value `gpt-5.6-sol` into `model.deployment`, although the active
contract's `foundry_identity.deployment` was null. The artifact passed
`ExperimentConfig` validation and could be handed to the runner. Outer false
launch flags did not enforce the claimed inert boundary. The original
`108 passed in 22.34s` result and earlier review did not catch this defect.

The correction removes the executable config shape and runtime-parser acceptance
from the compiler. A small internal validator permits only the exact template
keys and their verified contract/identity-plan values. The model label remains
in the sealed dispatch request; deployment stays null, even with linked evidence.
Explicit null execution prevents the legacy parser from filling absent fields
with runnable defaults. Actual `ExperimentConfig.from_dict`,
`ExperimentConfig.from_yaml` and the Step 1 CLI entrypoint refuse this document
before data loading, provider settings, route resolution, auth or command setup.
The inherited offline guards also prohibit client/model/grader construction.

Only a separate future materialization may bind an externally reviewed deployment
name into an executable runtime config. No model label, placeholder or hash is
accepted as a deployment name. `actual_pilot_deployment_not_prepared` remains
blocked. The materializer source pin was refreshed; the active contract still
pins 38 sources, and bundles with the old canonical plan digest are stale.

### Scope and concrete outcome

`gpt56_pilot_config_bundle.py` exposes `compile_pilot_config_bundle`,
`materialize_pilot_config_bundle` and `verify_pilot_config_bundle`, plus a small
offline CLI. It calls the real `verify_pilot_identity` against the active plan,
identity plan/ready/reservation bytes, current source pins and grader source
closure. An evidence-linked identity also requires the real evidence bundle,
caller-reviewed source SHA and explicit UTC evaluation time for reverification.
Only the sealed evidence digest/SHA/time link is carried forward; raw evidence,
resource identities and credentials are not copied.

The absent destination receives these files:

- `pilot-runtime-config.json`: a closed `foundry-pilot-runtime-template-v1`
  document, not an `ExperimentConfig`. It binds the verified dispatch request
  for Foundry/Codex, Sol-not-Fast, Max and 1M, with exactly five registered tasks
  in order. It preserves developer instructions, timeout/retry/native-cap
  declarations, the endpoint-free route, no self-QA/resume/relay/escalation and
  the record-only receipt contract. Deployment and execution stay null;
  `runnable` stays false. It does not inherit exp035's 220-task scope.
- `pilot-prepared-task-manifest.json`: the registered dataset revision/parquet
  hash, ordered task IDs, prompt hashes, per-task reference hashes and instruction
  digest. This is a future preparation contract, not fabricated Step 1 output.
- `pilot-grading-config.json`: a separate config derived from the verified
  step8 template. Judge, rubric, prompt, grader, TPM and schema blocks are
  unchanged. The pilot name/description and run-local future output directory
  replace the historical metadata; the filename contract is preserved.
- `pilot-identity-linkage.json`: exact dispatch/grading recipes, file digests,
  identity plan/ready/reservation linkage, active-contract digest, source pins
  and optional evidence linkage. It preserves one logical attempt/repeat,
  fresh sessions, no escalation, null native caps, record-only cost findings
  and null/partial receipts.

The internal runtime shape check enforces exact contract parity without creating
a runtime configuration. The actual step8 validator still receives the emitted
grading config parsed through YAML, with prompt paths resolved only in an
in-memory validation copy. No host absolute path enters a generated identity.

The grading boundary is explicit. The existing step8 `rerun_identity` requires
a real immutable inference revision. The materializer therefore omits that
historical block rather than inventing a revision or copying its 220-task
identity. Future inference repo/revision remain null in the sealed grading
recipe. No ignored grader task-selection keys are added. The bundle seals the
same five-task scope, order and hashes for dispatch and grading, but the
generated grader config alone does not enforce future execution scope. Real
inference identity, ordered-row binding and the generated config's eventual
runtime source hash remain unresolved; `materialized_grader_source_hash` is null.

Publication uses the existing held-parent and atomic no-clobber primitives:
sibling reservation, four complete files, then `pilot-config-bundle-ready.json`
last. Before ready, the materializer re-verifies the identity, active contract,
source closure and optional evidence, re-derives all files, and checks their
current bytes, exact membership and reservation. Verification independently
recomputes the bundle; forged matching file/marker hashes cannot substitute for
the pinned derivation. Collisions, partial reuse, links, traversal, overlap and
drift fail closed. Reservations and partial files remain for manual disposition.
There is no overwrite, automatic cleanup or reuse path.

The destination is a config-only disposable directory. This unit creates no
Git checkout, copies no source/data/reference tree, emits no execution command,
and produces no prepared rows, inference result or grade. It changes no
preflight blocker transition. The new active registration pins 38 sources;
the resulting plan digest changes, so older identity/evidence bundles are stale.

### Immutable base and review boundary

The clean development worktree started from immutable main
`1c038f8f46df3936228cbeb7bc36a0b8aef61337` on
`b/gpt56-pilot-config-bundle-20260920`. The preserved checkout
`wip/local-main-preserved-20260719` was not used or edited.

The correction uses the same PR worktree and branch, starting from
`b872446d6e61cfaa8fa1558ee94ea4a6b4ff67ea`. No new development or execution
checkout was created. The earlier `first-reviewer` approval at
`4adbdf859cee549fb3f4245f85fa96b051db833c` is historical and was superseded by the
leader BLOCK.

New immutable implementation HEAD:
`c61ede3afaf43a67296262d95a23a7e00ec871aa`.
The correction's four-file module/test/source-pin/spec diff is the review
boundary. Both `llm-systems-engineer` and `first-reviewer` returned APPROVE on
this exact HEAD. The systems review found no blocking or high-confidence
correctness issue. The first review reported no BLOCK, MAJOR or MINOR findings
and no second-review escalation. Both confirmed that null execution stops the
current parser before runtime setup and that the refreshed materializer pin
matches the committed bytes. Reviews were read-only, without tests, production
imports or external calls. This record and `CHANGELOG.md` follow validation and
are outside the implementation review boundary. No code or test changed after
the passing correction selector.

The repository's existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without changing Git
configuration. No attribution trailer, hook bypass, history rewrite, force push
or forbidden Git cleanup was used.

### Exact validation evidence

The same targeted selector was used for the original implementation and this
correction, once for each task:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt56_pilot_config_bundle.py
```

The original result was `108 passed in 22.34s`, exit 0. The single correction
invocation collected 129 cases and reported `129 passed in 23.26s`, exit 0,
under Python `3.10.12` and pytest `9.1.1`. The existing 108 cases were retained;
their runtime-shape assertions now match the corrected inert contract. The
21 added cases cover real parser/entrypoint refusal with and without evidence,
closed-shape/control drift, guessed deployment values, forged output hashes
and an attempted deployment change in the active contract. Nothing was removed,
skipped or marked xfail. The #631–#633 selectors were not rerun. No broad/full
suite or manual workflow ran.

Coverage includes complete no-evidence and evidence-linked bundles; real runtime
parser refusal and step8 validation; exact five-task/order/hash parity; unchanged
grader blocks; null inference identity; stable later-time evidence linkage; deterministic CLI
and relocation; every file/ready/reservation's bytes and single-link contract;
self-consistent forgeries; stale plan/source/evidence; missing/extra members;
symlink/hardlink/traversal/overlap/collision; all six publication write failures;
partial reuse; mid-publication drift; held-parent replacement; static privacy-safe
refusals and false launch flags. Runtime/evidence preflight blockers are retained.

Module-scoped seeds perform real publication and share only immutable bytes.
Each case receives fresh single-link copies; a regression verifies that mutation
does not reach another case or seed. No validator verdict is cached. The inherited
byte-keyed YAML parse cache makes defensive copies while real validators and
source hashing still consume current files. Fixtures prohibit subprocess,
network, provider auth, model/client/grader construction and grader execution.

`git diff --check` and `git diff --cached --check` passed before the implementation
commit. This is synthetic offline fixture evidence, not evidence of a successful
workflow, served Foundry capability, actual deployment or paid execution.
Automatic CI is a separate delivery check.

### Correction changed files

- `batch-runner/gpt56_pilot_config_bundle.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The PR also retains its original changes to
`batch-runner/gpt56_sol_codex_pilot_preflight.py` and the exact source-count
assertions in `test_gpt56_pilot_identity_plan.py`,
`test_gpt56_sol_codex_pilot_preflight.py` and `test_gpt56_foundry_evidence_intake.py`.
This correction did not change those files or rerun their selectors.

### Skills and roles

The full supplied/filesystem skill catalog and repository agent catalog were
inspected once for the original task. `experiment-design` was reapplied before
the correction. Its distinction between declared settings and established facts
kept the requested model label separate from a deployment name and left the
actual-deployment blocker intact. No experiment variable or paid run was added.

For the original implementation, `llm-systems-engineer` audited the runtime/config
and publication boundaries. `grading-engineer` checked the existing step8
contract after the consolidated grading specification and stable baseline were
read. Both roles worked read-only. They confirmed that null future inference
identity belongs in the sealed bundle,
not an invalid or ignored step8 field. Static inspection also caught a test that
treated a YAML comment as canonical contract drift; it was corrected to mutate
the registered run ID before the original selector. Those checks missed the
deployment assumption later identified by the leader. This correction received
fresh `llm-systems-engineer` and `first-reviewer` approvals at the immutable HEAD
above. The grader implementation is unchanged.

`im-not-ai-en` was applied to the English specification, changelog, completion
record and PR wording, preserving exact hashes, commands, counts and evidence
limits. UI/animation skills are unrelated to this backend file contract and
were not used. `extreme-reasoner` does not apply: no workflow, `core/qa.py` or HF
upload file changed.

### Evidence boundary and remaining work

This unit closes only inert config-bundle materialization and verification.
It does not authenticate external Foundry claims, approve inference identity,
prove served model/capability, or authorize a launch. No real evidence has been
accepted outside synthetic fixtures in this task.

Remaining work includes separate executable-config materialization with an
externally reviewed deployment name; live inference identity and actual
input/wire binding; execution-time grading scope and generated-config source identity; native
sandbox/result-bundle hosting; actual source/input deployment and pilot execution;
runtime enforcement of native caps; and usage/tariff receipt integration. Real
Foundry evidence acquisition and independent review remain external obligations.
The nine default blockers remain unless existing explicit evidence/identity
gates are supplied, and both launch flags always remain false.

No Azure API/CLI or HF calls, credential/OIDC lookup, provider/model/client
execution, inference, grading, download, workflow dispatch or paid execution
occurred. Production runtime/grader defaults, exp035 configs, workflows,
`core/qa.py`, HF upload and historical
ledger/evidence bytes are unchanged. Project updates and merge decisions remain
with the leader. This record contains pre-merge facts only, with no carrying-PR
merge SHA, time or state.
