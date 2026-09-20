# Latest substantive task result

## PROJECT5-GPT56-FOUNDRY-DEPLOYMENT-BINDING FULL-9CDA8A92

The Foundry GPT-5.6 Sol pilot can now bind private local resource-ID bytes to
complete evidence and publish a separate runtime candidate. The compiler uses
the real evidence, identity, config and input bundle verifiers. Explicit
preflight consumption clears only `actual_pilot_deployment_not_prepared`.

The sole selector reported `162 passed in 156.65s (0:02:36)`, exit 0. No selector
was rerun. Both `launch_allowed` and `full_220_allowed` remain false, as do the
active contract's `launch_enabled` and `full_220_enabled`.

### Scope and concrete outcome

`batch-runner/gpt56_pilot_deployment_binding.py` adds a small offline CLI and
`compile_pilot_deployment_binding`, `materialize_pilot_deployment_binding` and
`verify_pilot_deployment_binding`. All require complete evidence, identity,
config and input bundles, a caller-reviewed full source SHA, explicit UTC
evaluation time and separate account/project/deployment resource-ID files.

The compiler calls all four real upstream verifiers, checks their exact shared
evidence/plan/run linkage and binds each private file's original bytes to the
corresponding evidence subject's `resource_id_sha256`. It rechecks the upstream
chain and resource files after candidate derivation. Verification recomputes
the expected canonical bytes; matching forged output hashes cannot replace the
trusted derivation. The active registration pins 46 sources, up from 43. Bundles
tied to the earlier active-plan digest are stale and must not be reused.

Resource files must be distinct, regular single-link UTF-8 files. The supported
closed ARM path shape is an account with its project and deployment children.
Project-scoped deployment layouts are not inferred. A single terminal slash is
allowed and remains part of the exact byte digest. The compiler derives only
the deployment's last nonempty path segment, without case folding, trimming or
URL decoding. URI forms, query/fragment text, whitespace/control characters,
credential-like content, traversal, unsafe links and mismatched roles or parent
accounts fail closed. Errors and CLI reports never echo private paths or IDs.

The separate candidate uses the existing `codex_foundry` route and real
`ExperimentConfig.from_dict` and `validate` methods. Its deployment name comes
from the hash-bound resource ID, not the requested `gpt-5.6-sol` model label.
The verified dispatch and prepared-task manifests preserve the exact five task
IDs/order/input hashes, Sol-not-Fast, Max, 1M request, one attempt/repeat, fresh
sessions, no relay/resume/escalation, unchanged retry/timeout/native-cap
declarations and record-only receipt contract. No credential, token, endpoint,
launch command, inference result or grade is generated.

The original config bundle's closed inert template remains `deployment: null`,
`execution: null` and `runnable: false`. The separate candidate is intentionally
parser-compatible. Its outer false flags are not runtime enforcement, and Step 2
does not automatically consume this binding. A passing parser establishes
configuration compatibility, not permission to execute it.

After validating inputs and checking for destination overlap, publication writes
a sibling reservation ending in `.pilot-deployment-binding-reservation.json`, creates the
exclusive destination and publishes:

- `pilot-runtime-candidate.json` with only the derived deployment leaf.
- `pilot-deployment-binding.json` with source file roles/sizes/SHA256 values,
  exact task/dispatch identities, upstream links and remaining work.
- `pilot-deployment-binding-ready.json` last, after rechecking source and
  installed bytes, exact membership, held parents and the reservation.

The existing held-parent and atomic no-clobber primitives reject collisions,
partial reuse, path escape, symlinks, hardlinks and drift. Interrupted files and
reservations remain for manual disposition. Nothing is overwritten, adopted on
retry or automatically deleted. Full resource IDs and host paths are not copied
into the bundle. Source files, upstream bundles and historical records are not
modified.

### Closed preflight transition

Absent/null deployment options delegate to the existing preflight path. Its ten
default blockers are unchanged; the registered source count and active-plan
digest change with this implementation. Explicit consumption requires all four
upstream bundles and the three private resource files, and calls the real
deployment verifier. The closed `DEPLOYMENT_BINDING_BLOCKERS` mapping contains
only `actual_pilot_deployment_not_prepared`.

After the existing evidence, identity and prepared-input gates and this new gate
succeed, the named launch blockers are
`live_inference_identity_and_wire_unverified` and
`native_sandbox_and_result_bundle_host_unverified`.
`actual_pilot_execution_and_runtime_receipts_unverified` remains in the explicit
remaining-work lists of both the binding and report; it is not silently added to
or removed from the default blocker mapping. Missing links, invalid evidence and
late reporting errors retain the deployment blocker. CLI refusals are static.

The report carries only the consumed bundle/candidate digests, compact evidence
link, evaluation time, cleared/remaining blockers and evidence boundary. It does
not expose the deployment leaf, raw resource IDs, evidence claims or private
file paths. Both launch flags remain false and no launch command is produced.

### Exact validation evidence

Exactly one pytest invocation was run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_pilot_deployment_binding.py
```

Result: `162 passed in 156.65s (0:02:36)`, exit 0.

The selector covers valid raw-ID variants; real verifier/parser participation;
exact five-task parity; unchanged inert templates; exact byte hashing; malformed
or secret-like content; stale plans, SHA/time and source pins; missing, altered
or linked upstream markers; forged output hashes; unsafe source/destination
paths; collisions; every publication write failure; retained partial state;
mid-derivation and publication drift; held-parent replacement; source
immutability; fresh-case isolation; no-binding compatibility; the exact
one-blocker transition; false launch flags; and non-echoing CLI errors.

Module-scoped lazy seeds prepare the real upstream bundles once per synthetic
resource-byte variant. Each case receives fresh single-link copies. The inherited
byte-keyed YAML parse cache does not cache validator verdicts. Tiny synthetic
parquet/reference fixtures avoid scanning the live 220-task snapshot. Offline
guards prohibit subprocess, network, credential/auth lookup, endpoint resolution,
provider/model/client/grader construction and execution. The real static runtime
parser and validator remain active. The #631-#635 selectors and broad/full suites
were not rerun. No manual workflow ran.

`git diff --check` and `git diff --cached --check` passed before the implementation
commit. These are local fixture results, not evidence of a successful workflow,
live model consumption, served capability or paid execution.

### Immutable base and review boundary

The clean development worktree started from main
`9cda8a92040d6679cbfe7f83bca73b0fe657484f` on
`b/gpt56-foundry-deployment-binding-20260920`. The preserved checkout
`wip/local-main-preserved-20260719` was not used or edited.

Implementation review HEAD: `31813e353d3e98bd666c16102d95bfc3f876be41`.
The nine implementation/config/test files below form that immutable boundary.
`first-reviewer` returned APPROVE with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. `llm-systems-engineer` approved the same fixed HEAD
without blocking or high-confidence findings. Both reviews were read-only,
without tests, production imports, runtime/network calls or file changes. This
completion record and `CHANGELOG.md` are subsequent documentation changes outside
the implementation review boundary.

The repository's existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without changing Git
configuration. No attribution trailer, hook bypass, history rewrite, force push
or forbidden Git cleanup was used.

### Changed files

- `batch-runner/gpt56_pilot_deployment_binding.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/tests/test_gpt56_pilot_deployment_binding.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_pilot_input_bundle.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The older test-file changes update only the exact source count from 43 to 46.
Their selectors were not run.

### Skills, evidence boundary and remaining work

The full skill catalog was checked once, and `experiment-design` was applied
before planning or code. Its contract-versus-observation distinction kept this
unit limited to local byte binding. `llm-systems-engineer` provided contract and
fixture assistance plus immutable review; `first-reviewer` reviewed the fixed
implementation HEAD. `im-not-ai-en` was applied to the English changelog,
completion record and PR wording without changing numbers, hashes, commands or
evidence limits. No experimental axis or grading contract changed.

`extreme-reasoner` does not apply because workflows, `core/qa.py` and HF upload
are unchanged. No grading-role task was needed, since grading production code
is unchanged. UI/animation skills are unrelated to this backend contract and
were not used.

`offline_deployment_resource_binding_not_launch_or_execution` is the evidence
boundary. The bundle binds local files to externally supplied evidence; it does
not authenticate Azure facts, attest live input consumption, issue inference
identity or authorize launch. Only synthetic evidence and IDs were used here.

Remaining work includes real external evidence acquisition and independent
review; live inference identity, input consumption and wire binding; native
sandbox/result-bundle hosting; actual candidate deployment and pilot execution;
execution-time gating and native-cap enforcement; grading run/source identity;
and runtime usage/tariff receipt integration. Both launch flags remain false.

No Azure API/CLI or HF calls, credential/OIDC lookup, provider/model/client
execution, inference, grading, download, workflow dispatch or paid execution
occurred. Production runtime/grader defaults, exp035 configs, workflows,
`core/qa.py`, HF upload and historical ledger/evidence bytes are unchanged.
Project updates and merge decisions remain with the leader. This record contains
pre-merge facts only, with no carrying-PR merge SHA, time or state.
