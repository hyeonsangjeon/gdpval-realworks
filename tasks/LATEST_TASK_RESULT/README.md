# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-18
- Status: Agentic Sandbox non-paid implementation complete; paid gate blocked

## Task

- Implement the preregistered bounded `agentic_sandbox` solver and common
  hardened baseline without making any live model/API request.
- Close authorization, budget, transport, input identity, container lifecycle,
  artifact verification, fixed-denominator reporting, workflow, and dashboard
  trust boundaries under repeated independent review.
- Rebase onto current `main`, run the complete available model-free validation,
  and leave publication and paid execution fail closed until their separate
  immutable-input and signed-approval gates exist.

## Result

- Added a bounded Responses state machine with strict ordered tools for
  workspace/environment inspection, generated Python, mapped ffmpeg operations,
  artifact inspection, and mandatory deterministic finalization. The paired
  baseline retains one full-regeneration repair on the same hardened substrate.
- Split the credentialed control plane from an uncredentialed Docker compute
  plane. mTLS and canonical HMAC envelopes bind run/condition/task, exact
  sequence, nonce, payload, command, expiry, and one absolute deadline; bounded
  streaming parsing, exact-envelope recovery, and post-decode sequence commits
  fail closed on ambiguity or amplification.
- Added exact outcome-free selection and input-manifest validation, canonical
  source/staged hashes, Merkle roots, provider classifications, task-request
  digests, component/SBOM identities, and a signed approval chain shared by
  treatment and baseline before deferred client construction.
- Added crash-safe task/condition/paired budget reservations, conservative
  unreconciled usage, fixed-denominator completion/quality/time/cost endpoints,
  optional report/UI fields, and strict omission for legacy experiments.
- Hardened Docker lifecycle handling for may-exist containers/volumes, startup
  deadlines, verifier probes, paused snapshots, helper cleanup, selected
  artifact revalidation, candidate preservation, and signed close/finalize
  failures. The image removes package managers, shells, toolchains, download
  clients, privileged bits, and applies the generated-code syscall filter.
- Protected image-build and dedicated-preflight workflows now require the
  protected exact `main` event SHA. Existing base-image publication remains
  available, while agentic publication is separately opt-in and blocked by
  missing immutable Python/Debian locks.
- Rebased the implementation commits `a26cab3` and `d6cebe6` onto
  `main@ff02ef3a`. Repeated `first-reviewer` passes ended with `APPROVE` and zero
  mandatory code/config findings.
- No model/API call, paid workflow, task selection, image push, HF upload,
  grading run, or live experiment was executed.

## Verification

- Authoritative `batch-runner` model-free suite: **1,485 passed, 6 skipped,
  44 deselected**. The focused agentic suite previously passed **228** tests;
  Ruff passed on all 54 branch-changed Python files and mypy reported zero
  issues in 18 agentic source files.
- Node aggregate contracts: **54 passed, 0 failed**. TypeScript and Vite
  production build passed; both runtime and integrity desktop/mobile Chromium
  suites passed against the same built distribution. All nine workflow YAML
  files parsed successfully.
- Rebuilt local image
  `sha256:a6d43c2929b0de1823c393d558bed373c3850ee06a15fd75c24f1fa93a14309b`.
  Its UID:GID 65532 audit passed with 965 SBOM packages; generated and embedded
  SPDX documents matched at SHA-256
  `d7ca2c2f4eab49d3777744a9a5b1beea69523cb7d6cbbe9638034c4fd2743132`.
- Nested-Docker WAV lifecycle and XLSX/DOCX/PPTX render/verify/finalize E2E
  passed **4/4** in 157.50 seconds. No task container or work volume remained.
- The local host lacks seccomp TSYNC and its Docker daemon rejects custom
  seccomp profiles, so generated-code and outer-seccomp integration checks
  skipped explicitly and remained fail closed. The dedicated production-runner
  preflight is still mandatory before any credential can be released.
- Root `scripts/__tests__` produced 36 passes and two pre-existing failures
  because archived v1 `_sweep_template.yaml` is absent; this regression is
  already recorded in `tasks/rebuilding_grading_task/DEVIATIONS.md` and is
  outside the authoritative agentic gate.

## Remaining Work

- Generate and commit the immutable outcome-free 5/20 cohort and exact approval
  scope; add reviewed Python hash locks and the full Debian package lock; pin
  production image/SBOM, price, workflow, official-scope, and owner-key
  identities; then pass the real dedicated-host AppArmor/rootless-or-userns/
  seccomp preflight.
- Create and explicitly sign a fresh single-use paid gate before any five-task
  canary. Canary expansion, paired baseline/treatment, and grading each require
  separate renewed approval. Until then, agentic publication and every live
  model/API phase remain blocked.
