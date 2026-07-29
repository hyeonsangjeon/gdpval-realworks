# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-29
- Status: Agentic Sandbox V2 evidence collection decoupled from CPU/PID
  production limits; local implementation and exact validation complete,
  remote shipment pending

## Task

- Remove the overly strict rule that prevented capability, SBOM, and license
  evidence whenever the host lacked CPU quota or PID controllers.
- Preserve effective isolation for fixed CI evidence probes and keep all
  production execution, model, Step 2, workflow, grading, publication, and
  registry paths disabled.
- Prove the change on one exact candidate, complete adversarial review and full
  regression validation, update documentation, and ship through a reviewed PR.

## Result

- Added containment report schema 1.1 with separate `collection_checks` and
  production `checks`. Collection requires effective network-none, read-only
  root, UID/GID 65532, zero capabilities, no-new-privileges, and memory limit;
  production still requires those six plus CPU quota and PID limit.
- Runtime collection proof now checks capability sets, `prctl` NNP state,
  IPv4/IPv6 routes, memory cgroups, identity, and rootfs flags. Docker inspect
  independently binds HostConfig, the `none` network attachment, addresses and
  gateways, security options, user, memory, and read-only root.
- CPU and PID are probed independently, so an unsupported resource controller
  cannot prevent the six isolation checks or fixed evidence collection.
- Every parent and candidate operation uses a previously inspected immutable
  local image ID and `--pull=never`. The verifier never reinterprets a mutable
  tag or pulls during evidence collection.
- Candidate execution occurs only after collection isolation passes. Default
  entrypoint behavior requires exact exit code 78, empty stdout, and the exact
  canonical stderr line. Capability and SBOM scripts are committed, Git-bound
  inputs and run with no network, no host mounts, read-only root, non-root
  identity, dropped capabilities, NNP, memory, tmpfs, timeout, UUID name, and
  verified cleanup.
- Container cleanup survives remove errors and confirms exact-name absence;
  ambiguous daemon errors, wrong names, malformed output, unknown warnings, and
  partial isolation all fail closed.
- Production containment remains `failed` when CPU/PID controls are unavailable,
  remains required by policy, and cannot make the aggregate candidate complete.
- V1, Phase 1A, workflows, executor, Step 2, models, grading, publication, and
  registry behavior are unchanged.

## Exact Candidate Evidence

- Source checkpoint: `133df3f0aa5e4361c6c6cb7fd142ef5bdff8c1b5`.
- Local image ID:
  `sha256:dea418e4964c2e73bf77496633d0e16e5fc4fb66dddbb743d91d0020b672a77a`.
- OCI manifest:
  `sha256:e55817b206dfc4fed855742b327bf6a7c7bdd3b08bc391c2470f9b16efa7f525`.
- OCI layout: `verified`, 22 `linux/amd64` layers.
- Collection isolation: all six checks `true`; status `verified`.
- Production containment: common six checks `true`, CPU quota and PID limit
  `false`; status `failed`.
- Capability receipt: `verified` with 20 commands, 13 Python modules, three font
  families, and all nine artifact smokes passing.
- Package inventories: Debian 1,152, Python 255, R 14, npm 1.
- Effective SPDX SBOM: `verified`, 1,422 packages.
- License policy: `failed`, 1,255 unknown declarations and zero denied packages.
- CVE, signature, provenance, and real microVM boot: `not_run`.
- Aggregate gate: `blocked`; production activation remains `disabled`.
- Every evidence file is a single-link regular file; no evidence symlink or
  candidate container remains.

## Verification

- Focused evidence, containment, cleanup, and supply-chain suite: **64 passed**.
- Phase 1B static contracts: **93 passed**.
- Exact local Docker integration: **1 passed** in 49.26 seconds.
- Combined V1, Phase 1A, Phase 1B, sandbox, and executor suite: **640 passed, 1
  skipped, and 8 integration tests deselected** in 47.01 seconds.
- Complete credential-free backend: **2,644 passed, 6 host-dependent skipped,
  and 45 integration tests deselected** in 103.38 seconds.
- `py_compile`, static diagnostics, exact evidence reopening, V1 image identity,
  and `git diff --check` pass.
- Independent adversarial review progressed through containment, image identity,
  Docker warning, lifecycle cleanup, route/NNP, schema, entrypoint, and test
  findings to final **APPROVE** with no code merge blocker.
- No model, Azure, grading, Hugging Face write/upload, registry login/push,
  workflow dispatch, publication, or paid operation ran. Docker used only the
  local Unix daemon and public package downloads needed for the exact image.

## Shipment

- Branch: `fix/agentic-v2-evidence-containment-decoupling`.
- Reviewed code checkpoint:
  `133df3f0aa5e4361c6c6cb7fd142ef5bdff8c1b5`.
- Push, pull request, checks, merge, and final shipment recording are pending.

## Remaining Work

- Complete remote review, merge, and final shipment recording.
- Production activation remains blocked on CPU and PID containment, complete
  retained/transitive package artifacts, a pinned CVE scanner and database,
  approved signature trust root, provenance attestation, and a real
  Firecracker/jailer/KVM boot and cleanup proof.
- Package broker, web egress, model loop, grading, publication, and production
  authorization remain later-phase work. This change approves none of them.
