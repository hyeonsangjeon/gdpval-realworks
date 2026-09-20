# Latest substantive task result

## PROJECT5-GPT56-PRE-EXECUTION-CAPTURE FULL-140CBF4E

The registered Foundry GPT-5.6 Sol pilot now binds the real Step 1 prepared
five-task rows to its runtime candidate and five verified upstream bundles.
Step 2 checks that capture before host, route, auth or client setup. Explicit
preflight consumption clears only `prepared_request_capture_unverified`.
`live_inference_identity_and_wire_unverified` remains blocked. Both
`launch_allowed` and `full_220_allowed` remain false, as do the active contract's
`launch_enabled` and `full_220_enabled`.

The sole selector reported `2 failed, 122 passed in 284.01s (0:04:44)`, exit 1.
Both failures were in the fixture's successful Step 2 and legacy paths: the
unchanged Codex connection-confirmation gate stopped them before the expected
host/auth test boundary. The fixture now supplies the same test-only confirmation
stand-in as the GPT-5.4 capture selector. It was not rerun. This record does not
claim a green local selector; automatic `comparison-contracts` validation is
still needed for the corrected fixture.

### Scope and concrete outcome

`PilotInputCapture` is a strict optional control for
`gpt56_sol_foundry_codex_pilot5_v1` only. The deployment candidate carries it;
registered runs cannot select a legacy bypass by removing it. Invalid control
keys, a different run, another execution mode, a second condition or simultaneous
GPT-5.4 and GPT-5.6 controls fail closed. Legacy absent/null controls add no
serialized field or pilot file reads.

The new `gpt56_pilot_input_capture.py` exposes small library functions for
preparation, publication and verification. `PilotCaptureSources` carries private
bundle/resource paths, the caller-reviewed source SHA and external evaluation
time as runtime-only arguments. No execution command or launch CLI was added.
The existing Step 1 and Step 2 CLIs cannot run the registered pilot without that
explicit library context.

Step 1 calls the real deployment binding verifier, which in turn calls the
evidence, identity, config and input bundle verifiers. It reads the actual
candidate and input-bundle roles, uses the existing source projection and
reference snapshot helpers, and preserves the real Step 1 serializer and
prepared fingerprint. The writer exclusively publishes
`step1_tasks_prepared.json`, revalidates the upstream chain, then atomically
publishes `pilot-pre-execution-input.json` last. The held-parent and no-clobber
writer primitives are reused. Existing or partial pairs are never overwritten,
adopted or automatically deleted.

The canonical capture contains the ordered task IDs, raw and canonical prepared
JSON digests, each prepared row's canonical digest, prompt/reference/parquet
identities, dataset revision, requested Foundry/Sol/deployment/Max/1M settings,
candidate and active-plan digests, upstream ready/reservation digests and reviewed
source SHA. It contains no raw prompts, evidence claims, resource IDs, host paths,
endpoint, credentials, auth headers or free-form responses. The deployment leaf
still comes from the separately verified resource binding, not the model label.

Step 2 verifies the current prepared file, byte-equal and digest-equal capture,
candidate and all upstream bundles before its existing host and provider setup.
It rechecks upstreams after building the consumer projection, including changes
during that work. Raw retry/resume/mode/condition/relay overrides are checked
before coercion. Restored checkpoints cannot enter the fresh pilot path. The
existing final-output linkage slot can carry the verified capture digest and
upstream linkage without changing legacy result bytes.

Preflight accepts an explicit `--capture-workspace` alongside the existing
private bundle inputs. Without it, the new prepared-request and existing live
wire blockers both remain. Successful explicit verification removes only the
prepared-request blocker through a closed mapping. Reports expose safe digests,
reviewed source SHA, evaluation time and the evidence boundary, not private
inputs. A capture does not authorize launch or establish actual consumption.

The active Foundry contract now pins 51 sources, up from 46. The GPT-5.4 active
contract retains 34 sources and refreshes only its three shared runtime pins
and grader-template closure digest. Changing `core/experiment_config.py` changes
the existing all-core grader source closure, so both active template digests
were refreshed without changing grader code, configuration, prompts or behavior.
Historical registrations and ledger/evidence bytes are unchanged. Bundles sealed
against the earlier active-plan digest are stale and must not be reused.

### Validation evidence and limits

Exactly one targeted invocation ran:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_pilot_input_capture.py
```

Result: `2 failed, 122 passed in 284.01s (0:04:44)`, exit 1, 124 cases collected.
The two failing names were
`test_step2_and_final_output_bind_verified_capture_before_provider` and
`test_legacy_absent_null_keep_serializer_bytes_and_runtime_order`.
Their `SystemExit: 1` came from the existing
`_require_runnable_execution_mode` connection-confirmation check. The correction
adds only a test fixture stand-in for `_codex_connection_confirmed`; production
safety gates and real capture/upstream validators are unchanged. The correction
did not change assertions or case count and added no skips or xfails. No selector
was rerun after the correction.

The passing cases exercise real Step 1 publication and all five upstream
verifiers; exact five-task bytes and hashes; no-clobber and retained partials;
capture/prepared/config/source/reference/parquet drift; missing files and unsafe
links; raw overrides; stale evidence; mid-projection changes; privacy-safe
refusals; and explicit one-blocker preflight consumption. The corrected positive
provider-order and complete legacy regression paths still need automatic CI.

Module-scoped lazy seeds prepare real upstream bundles and captures once. Each
case receives fresh single-link copies. The inherited byte-keyed YAML parse
cache does not cache validator verdicts. Tiny synthetic parquet/reference files
avoid scanning the live 220-task snapshot. Guards prohibit subprocess, network,
credential lookup, endpoint resolution and provider/model/client/grader
construction or execution. Host and connection test stand-ins are not deployment
or served-capability evidence.

The #631-#636 selectors and broad/full suites were not rerun. No manual workflow
ran. `git diff --check` and `git diff --cached --check` passed before the
implementation commit. The existing static grader source-hash helper was used
only to derive closure metadata, not to grade anything.

### Immutable base and review boundary

The clean development worktree started from main
`140cbf4eef59a2b3c6ee731ac3dd4c75d9e005d7` on
`b/gpt56-pre-execution-capture-20260920`. The preserved checkout
`wip/local-main-preserved-20260719` was not used or edited.

Implementation review HEAD: `667fb775fdb2df4424ea85152c8a8ef86d5d9314`.
Both `llm-systems-engineer` and `first-reviewer` returned APPROVE with no blocking
findings in read-only reviews against the base above. They reviewed the corrected
fixture stand-in but did not execute it. Their approval covers the static
implementation, not a green selector, served capability, launch or merge.
This completion record and `CHANGELOG.md` are subsequent documentation changes
outside the implementation review boundary.

The repository's existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without changing Git
configuration. No attribution trailer, hook bypass, history rewrite, force push
or forbidden Git cleanup was used.

### Changed files

- `batch-runner/core/experiment_config.py`
- `batch-runner/gpt56_pilot_input_capture.py`
- `batch-runner/gpt56_pilot_deployment_binding.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/step1_prepare_tasks.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/tests/test_gpt56_pilot_input_capture.py`
- `batch-runner/tests/test_gpt56_evidence_preflight_gate.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_input_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_deployment_binding.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

Older selector files only update exact source-count and closed-blocker
expectations. Their selectors were not run.

### Skills, evidence boundary and remaining work

The full skill catalog was checked once. `experiment-design` was applied before
planning or code and kept prepared intent separate from observed model behavior.
`llm-systems-engineer` provided contract assistance and immutable review;
`first-reviewer` reviewed the fixed implementation HEAD. `im-not-ai-en` was
applied to the English changelog, completion record and PR wording while
preserving exact results, commands, hashes and evidence limits.

`extreme-reasoner` does not apply because workflows, `core/qa.py` and HF upload
are unchanged. Grader production is unchanged, so no grading-role task was
needed. UI/animation skills are unrelated to this backend contract and were not
used. No experimental axis, model setting, cohort or grading behavior changed.

`prepared_request_intent_not_wire_or_served_identity` is the evidence boundary.
The capture proves local prepared-input consistency at verification, not actual
wire bytes, live inference identity, served capability or launch permission.
Remaining work includes genuine external evidence acquisition and independent
review; live identity/input consumption/wire binding; native sandbox/result
bundle hosting; actual deployment and pilot execution; execution-time native-cap
enforcement; and actual usage/tariff receipts. Both launch flags remain false.
Automatic CI must also validate the corrected fixture.

No Azure API/CLI or HF calls, credential/OIDC lookup, provider/model/client
execution, inference, grading, download, workflow dispatch or paid execution
occurred. No live execution checkout was prepared. Production legacy defaults,
exp035 configs, workflows, `core/qa.py`, HF upload and historical evidence bytes
are unchanged. Project updates and merge decisions remain with the leader.
This record contains pre-merge facts only, with no carrying-PR merge SHA, time
or state.
