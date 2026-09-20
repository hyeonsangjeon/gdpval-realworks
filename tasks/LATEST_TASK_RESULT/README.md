# Latest substantive task result

## PROJECT5-GPT56-NATIVE-RESULT-HOST

Implemented a session-owned native workspace and accepted-result receipt for
the registered Foundry GPT-5.6 Sol five-task pilot. The current pilot still has
no live host evidence. Both `native_sandbox_and_result_bundle_host_unverified`
and `live_inference_identity_and_wire_unverified` remain unresolved, and all
launch/full-220 flags remain false.

The sole local selector reported `1 failed, 70 passed, 84 deselected in
2790.26s (0:46:30)`, exit 1. The test-only API error was corrected without a
rerun. A fixture-cache correction was also made after the run; its speedup is
unmeasured. Fresh automatic CI is required for the corrected implementation
and its runtime budget.

### Scope and evidence boundary

The new helper attaches to the exact live pre-execution capture/wire-receipt
session. The runner requires that owner before runtime/auth, holds the actual
local workspace directory identities, and rechecks collected bytes and the
runner handoff before cleanup. It records the sandbox/approval policy observed
in the app-server request. It does not infer remote or kernel isolation.

Step 2 verifies the runner handoff before accepting or saving deliverables.
The host binds task order and attempt indices, wire-receipt linkage, relative
deliverable paths/sizes/SHA256 values, saved-file records, accepted task rows,
and error/no-output state. Final publication binds a non-circular fingerprint
of the payload before host linkage. It rereads the actual saved result files
and publishes the host ready marker last.

Unsafe paths, links, special files, hidden/runtime files, duplicate or colliding
names, stale links, altered handoffs, changed output bytes, partial publication
and witness/session reuse fail closed. No-clobber writes retain failed partials
for quarantine; another session cannot adopt them. Public host receipts contain
no prompt/output text, private host paths, resource IDs, credentials or exception
strings. The existing Step 2 result retains its ordinary content; the receipt
contains only its digest and the allowed identities.

There is no saved-JSON adoption API, new CLI, offline preflight consumption
option or runnable launch command. A future runtime-owned verified host bundle
may satisfy only the native-host blocker. It cannot satisfy live wire/served
identity, native-cap enforcement, usage/tariff/billing or launch requirements.
Synthetic fixtures establish verifier behavior only.

Legacy absent/null paths keep their collector, saver and output shapes. The
active source closure grows from 52 to 55 files, adding the host helper and two
existing fingerprint/public-error helpers. Only directly affected source pins,
grader source-closure hashes and count expectations were refreshed. The grader
implementation, five-task scope, model, Max effort, 1M request and experiment
settings are unchanged. The three-way Backend partition is unchanged.

### Exact validation and post-run corrections

Exactly one pytest command ran, from the new worktree root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_pilot_wire_receipt.py -k native_result_host
```

Pytest collected 155 cases, selected 71 and deselected 84. The selected set has
66 new native-host cases and five adapted existing runner/Step 2 boundary cases.
The result was `1 failed, 70 passed, 84 deselected in 2790.26s (0:46:30)`, exit 1.
The failing node was
`test_native_result_host_five_task_real_verifiers_ready_last_and_private_result_digest`.
It reached its preflight assertion after the receipt checks, then raised
`AttributeError` because the test called nonexistent `pilot.inspect`.
The call now uses the existing `pilot.inspect_plan` API.

Static cost inspection found that `ExperimentConfig.from_yaml()` passes an open
text stream to `yaml.safe_load`, bypassing the existing string/bytes parse cache.
The shared fixture now reads the current `io.TextIOBase` contents into the same
content-keyed cache and returns a fresh `deepcopy`. Changed contents change the
key. Real validators, source hashes, path/link checks, current-byte checks and
session/witness checks still run; no validator verdict or mutable tree is shared.

Neither post-run correction was rerun locally. The 46:30 measurement belongs to
the pre-cache run, not the corrected HEAD. No passing selector, speedup or hosted
CI headroom is claimed. `git diff --check` and `git diff --cached --check` passed.
No full wire selector, prior pilot selector, core suite, contract job, broad
suite or manual workflow ran locally.

### Immutable review boundary

The new clean worktree and branch
`b/gpt56-native-result-host-20260921` start at requested main
`f6d76e2084bcda75de5dad15b98503f598734bc0`.
The implementation review HEAD is
`d2850e6dd4d12ab5180bdaaeef17c840a2a90fa3`.
The initial implementation commit was
`c2fbd6f3696058403b571b35b767a318423ad253`; its only follow-up change corrects a
source-count comment from 52 to 55. Both `llm-systems-engineer` and
`first-reviewer` returned APPROVE on the final implementation HEAD, with no
remaining findings. Their reviews were read-only and ran no tests, imports,
runtime, network calls or CI queries. They checked the 55 source pins and the
actual caller/handoff/result boundary. These are static review verdicts, not
passing test, live-runtime or CI-readiness evidence. This record and the
changelog are a subsequent records-only commit, outside that boundary.

### Historical PR #638 evidence, not validation of this code

The original wire-receipt selector ran from `batch-runner`:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q tests/test_gpt56_pilot_wire_receipt.py --tb=short
```

It reported `88 passed in 642.32s (0:10:42)`, exit 0, at implementation
`59aa7f00de5505e0ed5c1bff8e8ae7757ff9398a`, before the endpoint-account correction.
The corrected implementation
`89e9a33baa3b6c4b3c404f7c2c6f61798003a868` had 89 cases; that full selector was
not rerun locally. The 88-pass result does not validate the account correction
or this native-host implementation.

The subsequent partition history remains distinct:

| HEAD | Backend run / job | Result |
| --- | --- | --- |
| `c88f76f02c43ef9b2672e61d6cdd6d4630235305` | `35514065313` / `106086906143` (`pytest`) | Cancelled at `45:13` / `87%`, with no assertion failure. |
| `8117a667a49133cfd11f3401d17ddfd36d82db55` | `35517208735` / `106095045010` (`pytest`) | Succeeded in about `25:13`. |
| `8117a667a49133cfd11f3401d17ddfd36d82db55` | `35517208735` / `106095045151` (`comparison-contracts`) | Cancelled at about `45:16` / `91%`, with no assertion failure. |

The three-way partition's static selector reported `1 passed in 0.18s` at
reviewed implementation `c6bf7269480bfc804e7f2aaf6427613cdab3fda9`.
The final historical HEAD was
`9e6e42b85e56478f8082cd7bc9ae1fb6feb31812`. A single read of its hosted checks
confirmed all three Backend jobs succeeded in run `35520193108`. They all
started at `2026-09-20T15:38:03Z`:

| Check | Job | Completed UTC | Duration | Result |
| --- | --- | --- | --- | --- |
| `comparison-contracts` | `106102829162` | `2026-09-20T15:55:57Z` | `17:54` | success |
| `pilot-contracts` | `106102829266` | `2026-09-20T15:56:30Z` | `18:27` | success |
| `pytest` | `106102829319` | `2026-09-20T16:03:28Z` | `25:25` | success |

Those hosted results validate the historical HEAD only. They do not establish
success or CI headroom for the new native-host code. No cancelled job was rerun.

### Changed files

- `batch-runner/gpt56_pilot_native_result_host.py`
- `batch-runner/core/codex_runner.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/tests/test_gpt56_pilot_wire_receipt.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_input_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_deployment_binding.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Skills and remaining work

The complete skill catalog was inspected once. `experiment-design` was applied
before planning to keep the change confined to local evidence, with no new
experiment axis or launch authority. `llm-systems-engineer` covered implementation
and review; `first-reviewer` covered the immutable implementation. `im-not-ai-en`
was applied to the English records while preserving commands, hashes, counts,
timings and evidence limits.

UI/animation and repo-readiness do not apply to this backend evidence unit.
Grading behavior is unchanged, so no grading skill or execution is needed.
No workflow, `core/qa.py` or HF upload code changed, so the extreme-reasoner
decision boundary was not triggered.

Fresh automatic checks and duration evidence remain required. Actual Foundry
evidence acquisition/approval, a separately approved pilot deployment and
execution, live input consumption/HTTP wire/served identity, a real runtime-owned
native-host receipt, native-cap enforcement and usage/tariff/billing receipts
remain separate work. `launch_enabled`, `launch_allowed`, `full_220_enabled` and
`full_220_allowed` remain false.

No Azure/HF/OIDC/credential lookup, provider/model/client/grader execution,
inference, grading, download, paid execution or manual workflow dispatch occurred.
The preserved checkout and prior worktrees were not edited. Existing Git identity
`hyeonsangjeon <wingnut0310@gmail.com>` was retained without configuration changes,
attribution trailers, history rewriting, force push or hook bypass. Project and
merge actions were not taken. This record stops at pre-merge facts.
