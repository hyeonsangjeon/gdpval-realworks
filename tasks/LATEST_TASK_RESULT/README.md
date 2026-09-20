# Latest substantive task result

## PROJECT5-GPT56-PILOT-CONFIG-BUNDLE

The fixed Foundry GPT-5.6 Sol Codex pilot now has an offline config-bundle
compiler, materializer and verifier. They turn a verified #633 identity bundle
into four exact canonical files and a ready marker, without deploying or
executing the pilot. The sole targeted selector reported
`108 passed in 22.34s`, exit 0.

Both `launch_allowed` and `full_220_allowed` remain false, as do the manifest's
`launch_enabled` and `full_220_enabled`. Ready means local config consistency,
not launch permission, served capability or actual input consumption.

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

- `pilot-runtime-config.json`: a single-condition `ExperimentConfig` for
  Foundry/Codex, Sol-not-Fast, Max and the 1M context request, with exactly the
  five registered task IDs in order. It preserves the developer instructions,
  timeout and retry declarations, uses the existing deferred route without an
  endpoint, disables self-QA/resume/relay, and does not inherit exp035's 220-task
  scope. Its raw mapping retains the workflow-owned zero relay setting that
  the existing parser's serializer would omit.
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

The actual runtime parser and step8 validator inspect the generated configs.
The grading validator receives the emitted config parsed through YAML, with
prompt paths resolved only in an in-memory validation copy. No host absolute
path enters a generated identity.

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

Reviewed implementation HEAD:
`4adbdf859cee549fb3f4245f85fa96b051db833c`.
`first-reviewer` returned APPROVE with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. It confirmed that the compiler/preflight Git-object
hashes match the YAML pins. Its boundary is the eight-file implementation/config/
test/spec diff, not a live run or future CI result. This completion record and
`CHANGELOG.md` follow validation and sit outside that implementation boundary.
No code or test changed after the passing selector.

The repository's existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without changing Git
configuration. No attribution trailer, hook bypass, history rewrite, force push
or forbidden Git cleanup was used.

### Exact validation evidence

Exactly one targeted pytest invocation ran:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt56_pilot_config_bundle.py
```

It collected 108 cases and reported `108 passed in 22.34s`, exit 0, under Python
`3.10.12` and pytest `9.1.1`. Nothing was removed, skipped or marked xfail. The
#631–#633 selectors were not rerun. No broad/full suite or manual workflow ran.

Coverage includes complete no-evidence and evidence-linked bundles; real runtime
and step8 validation; exact five-task/order/hash parity; unchanged grader blocks;
null inference identity; stable later-time evidence linkage; deterministic CLI
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

### Changed files

- `batch-runner/gpt56_pilot_config_bundle.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The three older test files only update the exact source count from 37 to 38.
Their selectors were not run.

### Skills and roles

The full supplied/filesystem skill catalog and repository agent catalog were
inspected once. `experiment-design` was applied before planning or config edits.
It kept the intervention limited to file materialization and separated declared
scope from consumed inputs, enforced runtime scope and served capabilities.

`llm-systems-engineer` audited the runtime/config and publication boundaries.
`grading-engineer` checked the existing step8 contract after the consolidated
grading specification and stable baseline were read. Both roles worked read-only.
They confirmed that null future inference identity belongs in the sealed bundle,
not an invalid or ignored step8 field. Static inspection also caught a test that
treated a YAML comment as canonical contract drift; it was corrected to mutate
the registered run ID before the sole selector. `first-reviewer` provided the
separate immutable review boundary above.

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

Remaining work includes live inference identity and actual input/wire binding;
execution-time grading scope and generated-config source identity; native
sandbox/result-bundle hosting; actual source/input deployment and pilot execution;
runtime enforcement of native caps; and usage/tariff receipt integration. Real
Foundry evidence acquisition and independent review remain external obligations.
The nine default blockers remain unless existing explicit evidence/identity
gates are supplied, and both launch flags always remain false.

No Azure/API/CLI, credential/OIDC, provider/model/client, inference, grading,
download, workflow dispatch or paid execution occurred. Production runtime/grader
defaults, exp035 configs, workflows, `core/qa.py`, HF upload and historical
ledger/evidence bytes are unchanged. Project updates and merge decisions remain
with the leader. This record contains pre-merge facts only, with no carrying-PR
merge SHA, time or state.
