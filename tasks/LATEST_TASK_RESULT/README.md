# Latest task result

## Project5 prospective local-preparation source profile — 2026-10-04

The separately named prospective manifest compiles against the current source,
and the existing local preparer binds an explicit selection to the caller's
exact reviewed commit and tracked manifest bytes. This closes source selection
for local preparation only. No retained private input was reopened, rehashed,
imported or used to prepare a real checkout.

The [prospective manifest][local-profile-manifest] changes only the three reviewed
runtime bindings, the fingerprints of `gpt54_disposable_checkout.py`,
`gpt54_run_config_bundle.py` and `gpt54_run_input_bundle.py`, and the full grader
template closure. The historical `gpt54_sandboxv2_codex_comparison.yaml` remains
at SHA256 `3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1`;
`gpt54_comparison_preflight.py` is unchanged. Schema, model/effort, original input
hashes, full canonical Step0, task order, ABBA20, run IDs, limits, launch flags
and historical source constants are preserved. No core, Step2,
workflow, grader, credential, permission or historical-data file changed.

### Source-review basis and binding

The leader accepted the conditional same-session source-review memo and
independently matched the historical/current source pairs: runner and deadline
at `9b572a39af8ecd48850e427d1bccf8cb65b7c65a`, and Step2 at
`149d89afd43e54a46b6f172b71c2cf23d0cb7a17`, against accepted main
`5fcf254f4146734493e7390b110ad56189c836ae`. This is the basis for prospective
runtime bindings, not new runtime edits or approval of this final HEAD.
Prior PR743 reviewed `eb46b7ba5ef54917d0e9e31dff0d62818589c7e7`, owner
[review5407286936][local-profile-prior-review] and all 10 applicable checks cover
local transport only. Its accepted proof/import and earlier failure provenance
remain in the [immutable prior record][local-profile-prior-record]; none was rerun.

The leader source-reviewed HEAD
`a414499e98fb0dd69d339e8afab933a0add6a64e`, tree
`fcf602d8ee08a14e241895af52a0450c5324431e`, and found no high-confidence
implementation blocker, but kept approval on HOLD for the record correction and
applicable CI. The leader subsequently verified the two-file correction at HEAD
`dcb3fcddf2a68cff478f2ed7d565fcf743ebea69`, tree
`83d57e510a4aa3553eb892606b0c991820b314f6`. This was not final approval.

The existing `--manifest` CLI and optional `manifest_path` API keyword carry
the selected repository-relative YAML through all three helpers. The preparer
checks the exact tracked blob in the caller-supplied full commit, its working
bytes, source pins, detached destination HEAD and existing marker linkage.
Traversal, external/URL paths, symlinks, untracked selections and mismatched
commit/blob/digest evidence are refused. Historical omitted-path calling forms
remain available. Runtime/workflow selection still uses the historical default;
a manifest path is not approval. Reservations, no-clobber writes, quarantine
and partial-failure refusal are unchanged.

### Pinned offline evidence

The implementation was committed before the sole selector invocation at HEAD
`ad584b2d07143e27ea9af6e8c54abf6e6754a70f`, tree
`631099a87abeddd7547420e8f0d74a0c80288169`. The worktree was clean before and
after validation. From `batch-runner/`, the exact executable command was:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 timeout --kill-after=5s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q -ra -x --tb=short -p no:cacheprovider tests/test_gpt54_disposable_checkout.py -k prospective_source_profile
```

Result: 60 passed, 47 deselected in 40.70s, exit 0. Combined stdout/stderr log
SHA256 is `22bc7eab4d1e11ad8bdeb5e5450a1bb16e8a20fc9e650e815b838f53077e6b0b`.
The command text, including its final newline, has SHA256
`1c066c9091854b619873b78c95ec6a24f05a3737561b4379b56efb2c20486b76`.
Private validation receipt SHA256 is
`f56218b4f5dd1d65977e8985923f3a07afecc014d929c5cf6e50ee03a0f465cc`.
The 180-second test timeout and 5-second kill grace are not comparison limits.

The tracked prospective manifest has SHA256
`51a1788d37b7eba3aa134dccff13fdb27eeb5be1ba9a00896e6f2b97fe6509d5`.
The unchanged `step8_grade.compute_grader_source_hash` recomputed its full
template closure as
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The construction log has SHA256
`e806f4c473d56ce4c7a708c881a90481049a7bb9bad1bc548c8ce9330184ff28`.
The selector also exercises that real helper and the real compiler
against tracked current-source bytes, without substituted production pins.
The whole-core closure scope is unchanged; materialized-grader identity remains
unavailable. No grader or inference command was executed.

The remaining cases exercise preparation with synthetic inputs and the existing
historical source fixture. They cover both preparation paths, CLI/API and
historical-default forms, path/commit/blob/marker binding, canonical Step0,
unchanged source/input bytes, and reservation/quarantine/partial-failure
behavior under local process/network/provider guards. They are not observations
of the private originals. Real input-only registration still succeeds; the
historical full-plan registration still refuses the runtime drifts plus the
three newly changed local-helper pins. Coupled legacy assertions name those
additional refusals without changing any historical expected hash.

### Coupled legacy preflight correction

The leader read failed CI [run37227851802/job111511173523][local-profile-failed-ci]
(`pilot-preflight-contracts`): 2 failed, 196 passed, 143 deselected in 1099.90s.
Both failures were at line 84 of
`test_active_grader_template_source_foundry_preflight`, in its `current` and
`stale_expected_hash` cases. The expected current refusal list omitted
`source_pin:batch-runner/gpt54_run_config_bundle.py` and
`source_pin:batch-runner/gpt54_run_input_bundle.py`. Only those two entries were
added, in that order, between the Step2 and deadline entries. No
disposable-checkout entry was added. `configuration_valid=False`, the real
frozen-source fixture, genuine whole-template helper, stale-hash negative case
and all launch refusals remain unchanged. No production, compiler, manifest,
source pin or historical hash changed for this correction.

The test-only correction was committed before its sole invocation at HEAD
`8f0319cd5e924520dacb339717ceb490ead054ef`, tree
`9643b6ad14d508528d5edf731a7f3257d9efd886`. The worktree was clean before and
after validation. From `batch-runner/`, the exact executable command was:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 timeout --kill-after=5s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q -ra -x --tb=short -p no:cacheprovider tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight
```

Result: 2 passed in 2.08s, exit 0. Combined stdout/stderr log SHA256 is
`09446771488fc7d5fd4c81e3c3dadaefccea5a372aaaaf245d2dfe06aaa74d1c`.
The command text, including its final newline, has SHA256
`8136d9983b18bf04cb0b8068b5eee527ff43ce84b04a53400ed6e053fdebe3ac`.
Private validation receipt SHA256 is
`1f61eba793fcdba813634f4a25bcddba231274220c985d470643bcd2cff4dd1b`.
The 180-second bound and 5-second kill grace apply only to this local test.
This corrective proof is separate from the failed CI and the original
60-case proof above. Neither that selector nor the full CI job was rerun.
No private input or real preparation was used.

### Remaining gates and record boundary

The post-proof delta from the corrective tested HEAD is limited to this
completion entry and CHANGELOG; production, test and manifest bytes are unchanged.
Corrected final-HEAD owner review, applicable CI and leader acceptance remain
outstanding. Real local preparation requires the leader's subsequent
fixed-HEAD review and separate direction. Credentialed comparison-workflow
intake remains REJECTED; no HF-token binding or Actions draft-asset authority
is established. The dispatcher and native call/token caps remain unimplemented,
and every existing launch refusal remains in force. This proof establishes no
served identity, input wire consumption, model outcome, invoice or live readiness.

The registered 20-observation comparison remains unexecuted. The separate
30-cell pilot and 8-cell retention study remain finished and consumed. No
experiment, replay, provider/network input read, Project mutation or permission
change occurred. All retained inputs and prior worktrees remain untouched.

The catalog was inspected once. experiment-design preserved the existing
configuration-bundle scope and stopping boundary; protected im-not-ai-en applies
only to the new English passages. This is a software contract proof, not new
experimental-outcome reporting. No UI/animation skill, editorial-agent retry
or additional model was used. Literal and condition checks preserve the
source/fixture distinction and every unresolved gate.

The editorial fidelity checker exited 3 at its safe Markdown complexity limit
after its excerpt inadvertently included later CHANGELOG sections. It was not
retried. Bounded byte, literal and link comparisons passed separately.

[local-profile-manifest]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/ad584b2d07143e27ea9af6e8c54abf6e6754a70f/batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison_local_source.yaml
[local-profile-prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/743#pullrequestreview-5407286936
[local-profile-prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/5fcf254f4146734493e7390b110ad56189c836ae/tasks/LATEST_TASK_RESULT/README.md
[local-profile-failed-ci]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37227851802/job/111511173523
