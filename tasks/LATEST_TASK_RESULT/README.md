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

### Remaining gates and record boundary

The post-proof delta is limited to this completion entry, CHANGELOG and directly
related README usage text; implementation, test and prospective-manifest bytes
are unchanged. Final-HEAD owner review, applicable CI and leader acceptance
remain outstanding. Real local preparation requires the leader's subsequent
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

[local-profile-manifest]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/ad584b2d07143e27ea9af6e8c54abf6e6754a70f/batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison_local_source.yaml
[local-profile-prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/743#pullrequestreview-5407286936
[local-profile-prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/5fcf254f4146734493e7390b110ad56189c836ae/tasks/LATEST_TASK_RESULT/README.md

## Project5 local original-input registration correction — 2026-10-04

The corrected local importer materialized the four registered originals once,
with exit0 and installed-input readback. This is local input verification, not
comparison preparation, CI-read authority or launch authorization.

Only `codex_ci_input_bundle.py` changes production behavior. Its local CLI
checks the catalog/envelope input pins, derives the score-free cohort and
validates the registered dataset, task order and prompt/reference identities.
It reuses the existing parquet, cohort-binding, reference and canonical Step0
readers without constructing a comparison dispatch/grading plan. The private
data contract carries no dispatch commands or comparison provenance.
Credentialed intake retains `_registered()` and the public `import_bundle()`
full-source gate. Existing attestation/LocalTransport and lower-level readers,
core/runtime, workflows, graders, registration and source pins are unchanged;
no prospective helper-pin update is needed.

### Distinct evidence

- The accepted owner-mediated transfer remains the source of the archive;
  this task made no download. The initial import exited2 with
  `original_or_archive_verification_failed`. Its unchanged receipt SHA256 is
  `9f212ee1b087e668b71ebfa0bad46712d48384f8ac93586885d26353fdd8d826`;
  stderr SHA256 is
  `f1be4ec7f2c014bee8e3a9c0263fe836716b4be98ca7f6788b9ab223736e5dd4`.
- The accepted read-only diagnosis exited2 with `DispatchPlanRefused` in
  `_registered()`, before `_unpack` or publication. Receipt SHA256 is
  `bd01e99de1440a5c8506f6c36633a277616558e08943a6a34cc0fb41c8dcbb7a`.
  The full compiler rejected the runtime pins for `core/codex_runner.py`,
  `step2_run_inference.py` and `core/codex_task_deadline.py`. That refusal
  remains intact; it was not evidence of corrupt archive bytes or a missing parent.
- One new bounded bundle selector passed: **73 passed, 1 warning in 7.60s**,
  exit0. The warning belongs to the deliberately mismatched Step0-policy
  fixture. Log SHA256 is
  `fad1209a6015f64375bf7f799ee59be1fcf6ac6e2b503ae0d74a6651f67e4b0e`.
  Tests cover real current registration, genuine readers with explicitly
  synthetic input pins, malformed definitions/rows/Step0/archives,
  credentialed-gate separation, path safety and retained reservations.
- After that proof, one corrected real local import exited0 with empty
  stderr. Safe stdout SHA256 is
  `b785be846a68f38a0fefa7e7e97f877ddd3298dcaaa4960fc335a4edac1029d1`;
  stderr SHA256 is
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
  Archive/member checks, canonical Step0 and installed-input readback passed
  before the new ready marker. The old failed destination was not reused.

The real archive is2519040 bytes, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
These identities come from the real import, not its synthetic tests:

| Original role | Bytes | SHA256 |
|---|---:|---|
| Original parquet | 1913489 | `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` |
| Declared reference 1 | 47850 | `901e943a97328a661f9e704ae43eeea167e7805385a99322f1c24f8e159125c4` |
| Declared reference 2 | 329418 | `bb09ca2a9999b404d7fced9202b42949cd9f142f39554e254bac77b3686dae9e` |
| Full canonical schema4 Step0 | 218405 | `463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512` |

The separate logical role manifest is844 bytes, SHA256
`d5e77412993344e6a8510113d9969cb72157643e9cde63e27e51107b624fb0df`;
it is not a fifth original. Raw inputs, archive bytes, exact private paths and
the metadata-only handoff remain outside Git. The handoff SHA256 is
`b5b3b95b7da05f7a0af868196ef8bc7df5cdd40c03c6a5c83971eb088589a965`.
The import's sensitive-field screen returned false; that is not publication
clearance. No raw original or private locator is published by these records.

### Tested source and commands

Base main: `a7e20de5dc798f7cd77b2b0808d4d1b4902d12d0`.
Both proof and real import used clean implementation HEAD
`6d3805f507d291f094df2beecf3b5a378c4313ec`, tree
`a4312618812545c2f1dd31817ee2e66a707c58fc`. Subsequent edits are records/usage
documentation only. No passed selector or earlier runtime proof was repeated.

Both commands used `env -i`, `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`,
`HF_HUB_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`,
`HF_HUB_DISABLE_IMPLICIT_TOKEN=1`, `DO_NOT_TRACK=1`,
`PYTHONDONTWRITEBYTECODE=1` and `PYTHONNOUSERSITE=1`.
The selector additionally used `PYTHONPATH=.` and
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` from `batch-runner/`; import used
`PYTHONPATH=batch-runner` from the source root. The argument views below redact
private path values; the environment is listed above. Exact shell lines and
output redirections are retained privately, with command SHA256 identities below.

```bash
timeout --kill-after=5s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q -ra -x --tb=short -p no:cacheprovider --basetemp="$PRIVATE_EVIDENCE/pytest" tests/test_codex_ci_input_bundle.py
timeout --kill-after=5s 180s /ai-work/venvs/gdpval-realworks-py310/bin/python batch-runner/codex_ci_input_bundle.py import --bundle "$PRIVATE_ARCHIVE" --expected-sha256 757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3 --out "$NEW_PRIVATE_OUTPUT"
```

Selector command SHA256:
`52a5d353ed963eb78e15fe49904663f35616c11efa598d5f5ae2b75b353710ea`.
Import command SHA256:
`56db91202bfc5510992d6714f89d7772ae68bf1957c2ea1e896a78408bc452f0`.
The180-second bound and5-second kill grace apply to these local operations,
not to comparison/model execution limits.

### Remaining gates and record boundary

Credentialed comparison-workflow intake remains **REJECTED**; no HF-token
binding, new privilege or Actions draft-asset access is established. The
comparison still needs approved input-read authority and preparation wiring,
a command dispatcher, implemented native call/token caps and resolution of
its existing full-source/launch refusals. No served identity or input wire
consumption was observed. Four ABBA runs of five tasks =20 observations remain
unexecuted and launch-blocked. The separate30-cell pilot and8-cell retention
study remain finished and consumed. No model, grading, replay or new experiment
ran; no workflow, permission, Project or historical-data mutation occurred.

The full skill catalog was inspected once. experiment-report-en followed by protected
im-not-ai-en applies only to these new passages. Literal/condition reconciliation
uses source, structural and candidate checkpoints plus a change ledger;
reverse-condition review is same-session, not independent approval. No matching
backend/data-integrity skill is supplied; experiment-design and UI skills are
not applicable. No failed editorial transport or full-changelog scan was retried.

The [earlier card-control record][prior-record] preserves its separate failed
review routes and leader-verified repair. Prior PR741 reviewed
`5a69d46e3dcf44d6a833a3381e02f3f2440a65ea`/[review5404449148][prior-review]
remains accepted history, not review of this implementation. Final-HEAD owner
review, applicable CI and leader acceptance remain outstanding.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a7e20de5dc798f7cd77b2b0808d4d1b4902d12d0/tasks/LATEST_TASK_RESULT/README.md
[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/741#pullrequestreview-5404449148
