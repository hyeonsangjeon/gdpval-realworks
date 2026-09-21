# Latest substantive task result

## PROJECT5-GHCP56-REAL-LOCAL-INPUT-STAGING

Published and verified one real local input bundle for the registered GHCP
Codex GPT-5.6 Sol five-task condition. The existing CLI accepted the original
pinned bytes. Explicit bundle consumption satisfied only
`original_task_input_materialization_unverified`; fourteen requirements remain.
This proves local input materialization, not VM or model consumption, grading
accuracy or paid readiness.

The operation used unchanged code at
`c1c4e7a50af80a719bacae0054337a4306c5c051` in a new clean worktree.
Only `CHANGELOG.md` and this record are changed. No production module, schema,
GHCP/Foundry plan, source pin, workflow, test or evidence policy was changed.
Completed branches, earlier worktrees and the preserved checkout remain intact.

### Source and input identities

The unmodified no-bundle preflight ran once and returned 2 with a valid
configuration, fifteen blockers, nine null observations and six false flags.
Its canonical plan digest and emitted task/reference identities were used
directly. No task selection or pin list was redefined.

| Identity | Observed value |
| --- | --- |
| Condition | `gpt56_sol_ghcp_codex_vm_pilot5_v1` |
| Dataset | `openai/gdpval` |
| Dataset revision | `11e7900cdcac61bc4daf59e65feb238acda98fbf` |
| Canonical reviewed plan SHA256 | `6cc207ee574e6b062cecfab8dd6035a0ab67cd0f2cba24516b2fdc149babd5dc` |
| Input CLI source SHA256 | `f6b57eacdcb93715bb286dc7bc979599d5c5a14a948f5b14a1c8561631780d39` |
| GHCP preflight source SHA256 | `20bf6f374c576c96fd9fdc222a767bdcac62bd253d23de39bfaefc95cde796b2` |
| Ordered five-task source projection SHA256 | `1635898065af9948c5e611ff0bb44d23620f20ad11fa69c9f1202de931dbb090` |

The authorized snapshot already contained the complete pinned input set.
Discovery stopped there; no broader filesystem search was needed. Each exact
snapshot role was a symlink to a regular, single-link blob inside that same
dataset cache. The operation checked confinement and the pinned digest, then
copied the bytes into fresh private single-link regular source files with the
existing relative layout. This was local cache normalization, not a download.
The cache was not changed and the materializer's no-symlink rule was preserved.

| Published relative role | Bytes | SHA256 |
| --- | ---: | --- |
| `data/train-00000-of-00001.parquet` | 1913489 | `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` |
| `reference_files/bb09ca2a9999b404d7fced9202b42949/Work Time Study - Source.xlsx` | 329418 | `bb09ca2a9999b404d7fced9202b42949cd9f142f39554e254bac77b3686dae9e` |
| `reference_files/901e943a97328a661f9e704ae43eeea1/Acquisition Criteria (2).pdf` | 47850 | `901e943a97328a661f9e704ae43eeea167e7805385a99322f1c24f8e159125c4` |
| `developer-instructions.txt` | 178 | `f8300fb85d3bd1231d9dd548817a941aa938fb42d6c8c7a1cd8dea7abece97a4` |
| `ghcp-vm-input-manifest.json` | 11132 | `960be2a26ccd97da5f3c7530deca3c66dd77f3f3fe6124811309cda54435da18` |
| `ghcp-vm-input-bundle-ready.json` | 1519 | `bdab5831512ab01bd68e292cf8f9558583abc1dcd46d405911076f24aeccc33d` |

The sibling reservation contains 349 bytes with SHA256
`88e67f6c5f20e7d21c7a40cc988149a5217dba584d3ad3134eb00911abd2bfa9`.
The whole parquet was copied without filtering or re-encoding. Only the two
reference roles in the exact five-task closure were staged. The verifier
checked the ordered task IDs, prompt hashes, reference hashes, developer
instructions, deliverable/grading metadata and all nineteen source pins.
These pins establish source consistency, not grader accuracy or a full-220
execution identity.

### Executed operations

The following are the actual invocation shapes with private path arguments
represented by variables. Each operation ran once, without retries. The plan
variable held the canonical digest above; no raw input or host path is included
in this record.

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

| Operation | Exit | Observed verdict |
| --- | ---: | --- |
| Materialize | 0 | `input_bundle_complete=true`; ready published last |
| Verify bundle | 0 | `input_bundle_complete=true`; published bytes and current pins rechecked |
| Preflight with verified bundle | 2 | `configuration_valid=true`; launch remains blocked |

All three results identify the same ready/bundle SHA256 shown above.
`cleared_blockers` is exactly
`["original_task_input_materialization_unverified"]`. The evidence boundary is
`local_input_materialization_not_vm_or_model_consumption`.
All nine runtime observations, including `verified_task_inputs`, remain null.
`launch_enabled`, `launch_allowed`, `paid_execution_enabled`,
`paid_execution_allowed`, `full_220_enabled` and `full_220_allowed` are false.

The fresh persistent destination is private and outside the checkout and
cache. The real bundle, reservation and normalized sources are retained for
the next stage. A private handoff records the destination and the plan, code
and bundle identities. No raw parquet, references, prompts, host paths, credentials
or endpoints are included in Git or public records.

### Remaining requirements and evidence limits

The consuming preflight returned these fourteen blockers, in order:

```text
ghcp_route_served_identity_unverified
max_long_1m_capability_unverified
ghcp_codex_versions_unresolved
authentication_supply_disposal_unresolved
vm_image_os_packages_version_policy_unresolved
fresh_task_vm_reset_unverified
network_permission_policy_unresolved
native_execution_limits_unresolved
repeat_and_variance_plan_unresolved
five_task_time_cost_caps_unresolved
native_ghcp_usage_and_missing_usage_policy_unresolved
transcript_tool_command_file_exit_capture_unverified
grading_result_runtime_unwired
grader_validation_unverified
```

The same original five tasks and GHCP Sol/Codex/Max/1M request remain fixed.
GHCP and Foundry stay separate; no performance comparison is made. Auth, VM
reset/capture, versions, limits, repeats/variance, time/cost caps and usage
decisions are unchanged. No served identity, capability, usage or grader
validation was observed. This operation grants no execution permission.

The earlier synthetic result, `89 passed in 33.08s` on implementation
`d92e72b2fc76510929b961c8103a8d2d6ed4e02c`, is separate historical test evidence.
It did not stage these real inputs and is not the evidence for this operation.
No pytest, new fixture, build, benchmark, manual workflow, Azure/Foundry call,
HF download/upload, login/token access, provider/model/client, VM, grader or
paid execution occurred here.

### Records review and skills

The complete skill catalog was inspected once. `experiment-design` retained
the existing exact-byte acceptance boundary: missing/drifted bytes or uncertain
provenance would stop the operation. No settings were invented.
`experiment-report-en` separates the real local observation from unobserved
runtime claims; `im-not-ai-en` preserves the exact values and limits while
copyediting the English records. `first-reviewer` reviewed the immutable
records-only commit. No implementation work required `llm-systems-engineer`.
UI/animation, grading, repo-readiness and extreme-reasoner do not apply because
no interface, grading behavior, publication-readiness audit or workflow changed.

Read-only `first-reviewer` returned APPROVE with no findings on records HEAD
`8ea66191829148c3f84bc8564c00951f15ea225e` against base
`c1c4e7a50af80a719bacae0054337a4306c5c051`. The reviewer compared immutable Git
records with the saved sanitized evidence. The review did not independently
rehash raw inputs or repeat the operation; execution counts and cache handling
were reviewed from the supplied operational handoff. No tests, imports,
application CLI, network/CI queries or edits were performed by the reviewer.
This later acknowledgment is outside that initial review boundary.

`git diff --check` passed. Fresh final-HEAD automatic checks remain required
and will be read once after the normal push without waiting or polling.
The existing author/committer identity is
`hyeonsangjeon <wingnut0310@gmail.com>`; no attribution trailers are added.
No Project card edit or merge action was performed. This record stops at
pre-merge facts.
