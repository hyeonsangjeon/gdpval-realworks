# Time-budget observation admission on Ubuntu 24.04

Local-only work on `leader/time-budget-2404-guard-20261030`, based on main
`0140b4c125093dc04de9ca0814387c140a929a59`. The owner selected GitHub-hosted
Ubuntu 24.04 for benchmark execution on 2026-10-29. This change does not
authorize dispatch or publication, read private Task4 results, or call a model.

## Review of the four registration mismatches

All four registered SHA256 values exactly match the file bytes at
`e3ad928bf02b99e080a6a5924a4ebda75b156adf` (2026-10-07). The review compares
that commit with the base main above. Classification below concerns the
**dedicated time-budget path**, not whether these changes affect other studies.
All four still block the source-registration checks; that common admission
effect is not waived by a “no direct behavior change” finding.

| File | Direct time-budget behavior | Basis at base main |
| --- | --- | --- |
| `.github/workflows/batch-run.yml` | No | Its lines 316 and 750–778 migrate the generic Codex batch and add sandbox preparation. The time-budget workflows call their own controllers, not this workflow. Its registered byte hash is nevertheless checked. |
| `batch-runner/step8_grade.py` | No, for the frozen F execution | New admission/receipt logic is in runtime `main()` (2491 onward). Time-budget materialization copies and executes F, not this changed entrypoint (`gpt54_time_budget_grading_preparation.py:337`, `gpt54_time_budget_grading_execution.py:562`). The hash-helper addition at 260 applies only to the separately named GPT-5.6 pilot, not this study. No score-parity claim is made. |
| `batch-runner/core/codex_runner.py` | **Yes** | `run():1414` and `open_runtime():1053` require the actual approved host before model effects; the old 22.04 observer no longer passes. The result also acquires `runner_evidence`. Sol-only observer branches are not selected by this GPT-5.4 path. |
| `batch-runner/step2_run_inference.py` | No | Lines 1210 and 1345 add runner/provider evidence to the generic Step2 projection. The time-budget consumer invokes the runner directly (`gpt54_time_budget_comparison.py:1374`) and its dedicated capture builds its own result (`gpt54_time_budget_codex_observation.py:148`), without these Step2 helpers. |

Expected → base-main actual SHA256:

```text
batch-run.yml
47f006f69bc079c50e3fba5ec5a7afcee769478e9857dead9c2e0eee22d90c26
06519bc2abb0f69fe688cd864dadb536e907a433e2726c5bf60c1115c5c220bb
step8_grade.py
ec23fc941aa0edb54e2858750cc1df5a6a6954a1732cd3f3197d9f9b4b3c18f4
0911eaff30b3c4cfbd6f3dfa0ced2b11319062a154a610dd5d9ddaf79215bf1c
core/codex_runner.py
b6765bef5c013b964e6133b6d915ab337e087b8130bc443938c4abb23cf8265c
b5f29c5aef7fc594ed3f042085a078e9e13c3f3754f5840c1df19bae75235c34
step2_run_inference.py
9ae6e0c809be498fd96c25ad16b83302c567fe95bdd7dc587451c4029b8c24bc
fd84734568d1eec7198fc59717bfbb877c75fbf01760cdd48b17316fddc20d40
```

None of those four files or the registration is modified in this change.

## Admission and image evidence

Both observation jobs and their independent request descriptors now require
`ubuntu-24.04` / `ImageOS=ubuntu24`. The shared live-host observation additionally
uses the existing real-OS admission. A self-hosted label, actual Ubuntu 22.04,
missing/malformed image version, or non-X64 host cannot pass. The separate
Azure-VM exception is not accepted by these Actions controllers.

The observed runner environment, OS, architecture, ImageOS, ImageVersion and
actual OS release form a closed `runner_image` record. It is included in the
host identity hash, the permanent observation claim, the captured result's
`observation_execution.host`, and the new v2 completion envelope. The existing
direction and final live-host rechecks therefore detect image changes too.
Host metadata is still **not** kernel process-ownership or cryptographic
host-attestation evidence; `ownership_confirmed` stays false here.

Old v1 envelopes remain readable under their original exact allowlist, without
inventing an image. A v1 envelope cannot carry the v2 image fields, and a v2
envelope cannot omit them. The result reader checks that the result's host
policy and image match the completion envelope. A historical readout is not
new execution authority and is not silently relabelled as a 24.04 observation.

## Codex sandbox preparation

After credential-free source validation, the Codex observation job installs
system bubblewrap if absent and runs the existing, source-held
`scripts/prepare_codex_sandbox_host.py`. Both steps precede the first input
credential, permanent observation claim, Azure login, and model operation.
The preparation step has ordinary fail-closed workflow sequencing, no
`continue-on-error`, and preserves its report even when the probe fails.

The helper's existing contract is unchanged: require the pinned runtime and
GitHub-hosted actual Ubuntu 24.04; optionally add only the binary-scoped
AppArmor userns profile; change no sysctl or existing profile; require the
bubblewrap probe and the pinned local Codex sandbox marker. Its returned
runner receipt is included in a dedicated nonsecret Actions artifact.

Official OpenAI documentation was read on 2026-10-30:
[CLI reference — Linux sandbox](https://developers.openai.com/codex/cli/reference/#codex-sandbox).
It describes local command execution with bubblewrap and seccomp. It does not
prove a particular binary/image works; the same-job probes remain required.
No CLI, sudo, AppArmor operation or hosted probe is run by these local tests.

The fixed Python 3.10.12 check is also retained. The public
[actions/python-versions manifest](https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json),
read on 2026-10-30, lists `python-3.10.12-linux-24.04-x64.tar.gz` for platform
24.04. This verifies that a matching distribution is listed, not that this
branch's Actions job has installed or exercised it.

## Validation and remaining work

The new fixtures cover strict image admission, actual-OS mismatch, image
mutation during a source-bound request, versioned receipt/result matching,
historical receipt preservation, and sandbox-before-credentials sequencing.
The shell failure test substitutes a shell function for Python; it never runs
the preparation helper or a model. The existing source-bound Git fixtures
commit the exact changed working-source bytes only inside their synthetic R
repositories, so testing before the branch's final commit does not mislabel
those bytes as the older HEAD. Repository registrations are not rewritten.

Offline reports are retained under
`/ai-work/copilot/_tmp/time-budget-2404-guard-20261030.KLyRxL/`.

The first invocation stopped at 80 passes and 5 failures: the newly added
native-controller test omitted `request_json` when calling the validator
directly. That fixture call was corrected. These counts are not added to the
final related-suite invocation.

The next related run reported **267 passed / 1 failed / 0 skipped**, 1079.96s.
The sole failure was the pre-existing **positive real-kernel** owned-startup
probe: this NAS reports `pidfd_open` ENOSYS (38), missing proc children data,
and no admitted generation. Its audit reported zero network attempts. This is
not made into a passing test or weakened into a skip: that positive proof
still belongs on the actual supported Actions host. The final local scope
selects the separate static workflow contract from that file, not its
unsupported-host positive probe.

The final explicit offline selection passed: **267 passed / 0 failed /
0 skipped**, exit **0**, **1085.21 seconds** (18m05s), Python 3.10.12 and
pytest 9.2.0. `final-tests.log` and `final-tests.xml` are the final records,
not a sum of overlapping attempts. The source was unchanged during this run.
The selection was:

```text
tests/test_time_budget_ubuntu24_guard.py
tests/test_time_budget_first_codex_ci.py
tests/test_time_budget_first_v2_ci.py
tests/test_time_budget_result_readout.py
tests/test_time_budget_first_v2_observation.py
tests/test_time_budget_codex_observation.py
tests/test_time_budget_owned_startup.py::test_time_budget_owned_startup_workflow_contract
tests/test_codex_ubuntu24_preflight.py
```

It used `env -i`, offline/telemetry flags, `-m 'not integration'`, no pytest
cache provider, and a dedicated temporary test directory. The real-kernel
positive test is neither counted as passing nor reported as a pytest skip.

The experiment-design check treats OS/image/preparation as a distinct recorded
execution condition. GPT-5.4/xhigh, the five task IDs, two conditions/two
repeats, 20-observation maximum, 1,200s generation plus 20s cleanup, no external
retry/replay/resume, frozen F grading and the original registration bytes stay
unchanged. This is not an observed 22.04/24.04 performance comparison.

Still pending: review/re-register the changed runtime/source roles without
renewing F by accident; then obtain publication/hosted-verification authority.
The real registration continues to reject its four existing mismatches before
credentials. Full ABBA/repeat-2 scheduling, generalized capture/grading/readout
integration, and actual hosted readiness verification are outside this change.

## Changed files

```text
.github/workflows/gpt54-time-budget-first-codex.yml
.github/workflows/gpt54-time-budget-first-v2.yml
batch-runner/gpt54_time_budget_codex_ci.py
batch-runner/gpt54_time_budget_v2_ci.py
batch-runner/gpt54_time_budget_v2_observation.py
batch-runner/gpt54_time_budget_result_readout.py
batch-runner/tests/test_gpt54_time_budget_comparison.py
batch-runner/tests/test_time_budget_first_codex_ci.py
batch-runner/tests/test_time_budget_first_v2_ci.py
batch-runner/tests/test_time_budget_owned_startup.py
batch-runner/tests/test_time_budget_ubuntu24_guard.py
batch-runner/docs/time_budget_ubuntu24_guard_20261030.md
```
