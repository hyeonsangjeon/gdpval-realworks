# Latest Task Result

- Updated: 2026-08-06
- Status: Phase 1D-A offline Python wheel broker candidate implemented,
  validated, and still disconnected from production

## Task

- Continue Agentic Sandbox V2 toward installable external packages and Linux
  execution without weakening containment, reproducibility, or fail-closed
  behavior.
- Deliver the smallest model-free package slice that can be proved on this
  host, while deferring command execution that lacks enforceable isolation.
- Preserve the intentional dirty primary checkout byte-for-byte by working from
  clean `origin/main@fa76d24973e6` in a separate worktree.

## Result

- Added a foundation-only snapshot schema and runtime policy for at most eight
  exact, canonical, dependency-free `py3-none-any` wheels on Linux amd64 and the
  active Python major/minor.
- Added strict artifact admission for size/hash, archive paths and controls,
  RECORD inventory and hashes, METADATA identity and `Requires-Python`, exact
  WHEEL headers, aggregate limits, collisions, links, executable-mode entries,
  `.data`, `.pth`, `.egg-link`, `.pyc`, and startup hooks.
- Added stateless lock resolution. A returned digest can be activated after a
  broker restart without hidden resolver state.
- Added deterministic stdlib wheel extraction with no pip, installer
  subprocess, package index, or network path. Activation uses private
  descriptor-anchored staging, independent expected inventory, canonical
  receipt bytes, mode sealing, and atomic rename.
- Added process-shared nonblocking leases, shared-root global state and quota
  validation, canonical receipt baselines, bounded descriptor replay and
  cleanup, orphan recovery, last-lease cleanup, and fail-closed root/lease/
  content/mode/size drift handling.
- Added a dispatcher candidate that permits only capabilities query, package
  resolve, and package activation. Command execution, workspace mutation,
  browser, public verification, and finalization return
  `capability_unavailable`.
- Confirmed the candidate is not wired into executor, Step 2, the Agentic V2
  runner, experiments, workflows, grading, upload, or publication.
- Kept the implementation under `sandbox/v2/`, outside the existing
  `COPY core` image input, core-tree identity, Phase 1B/1C build allowlist, and
  embedded-image manifest. Tracked Dockerignore rules also exclude every
  Phase 1D-A artifact from existing publication build contexts.

## Verification

- Focused Phase 1D-A adversarial suite: 75 passed.
- Agentic V2 contract, foundation, compatibility, candidate verifier, Phase 1B
  static/contract/OCI/supply-chain, and Phase 1C license regressions: 644
  passed.
- Ruff, `py_compile`, VS Code diagnostics, and `git diff --check`: passed.
- Credential-free backend: 3,001 passed, 6 skipped, and 45 integration tests
  deselected. Three unrelated environment failures remain: installed
  `openai==2.45.0`, `azure-core==1.39.0`, and `azure-ai-projects==1.0.0` do not
  match repository pins 2.46.0/1.41.0/2.3.0, and `pdfplumber` is absent. The
  failing tests and requirements are unchanged from `origin/main`.
- Independent security and code reviews returned `APPROVE` with no blocking
  findings for this foundation-only candidate.
- No model call, package index, external network, credential, workflow,
  grading, upload, publication, or paid operation was used.

## Shipment

- Working branch: `feat/agentic-v2-package-broker`.
- Base: `origin/main@fa76d24973e660f4e93b26fe7ef7d87dc5ba3223`.
- This record describes the reviewed local candidate before remote shipment.

## Remaining Work

- Production activation remains disabled. The candidate is not connected to a
  model loop, experiment, workflow, grader, uploader, or public artifact path.
- `exec_run` remains blocked. The local Bubblewrap probe cannot create the
  required user namespace, so arbitrary Linux execution has no enforceable
  containment proof on this host.
- npm, Debian/apt, live indexes, URL/VCS requirements, sdists, and editable
  installs remain unsupported.
- Package admission SBOM, license, CVE, provenance, signature, OS-level network
  containment, and crash durability remain `not_run` or `not_claimed`.
- A later production phase must add approved supply-chain evidence and a proven
  containment substrate before connecting package environments to execution.
