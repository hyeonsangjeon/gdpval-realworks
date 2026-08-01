# Latest Task Result
This is the canonical rolling record of the most recently completed repository task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-31
- Status: Agentic Sandbox V2 Phase 1C deterministic license evidence
  implemented and validated on one exact local candidate; production remains
  disabled and blocked

## Task

- Close the Phase 1B inventory's 1,255 unknown license declarations with
  deterministic, model-free Debian, Python, R, and npm evidence.
- Normalize only exact evidence, preserve honest unresolved outcomes, and make
  package exceptions exact, reviewable, stale-proof, denied-proof, and
  fail-closed.
- Bind the result to exact Git, image, OCI, SBOM, collector, evaluator runtime,
  policy, containment, and aggregate-gate identities without activating any
  model, workflow, grading, publication, registry, or production path.

## Result

- Added a stdlib-only in-image collector using fixed roots and
  descriptor-relative no-follow opens. Parsed metadata and SHA-256 identities
  derive from the same file descriptor bytes.
- Added host-owned SPDX normalization for exact identifiers, aliases,
  `AND`/`OR`/`WITH`, Debian expressions, Python metadata/classifiers/files, R
  DESCRIPTION/runtime evidence, and npm metadata/files.
- Every package records ecosystem, name, version, purl, raw values, evidence
  source/path/digest/size, classification, normalized expression, and reason.
- Outcomes are `resolved`, `missing_metadata`, `ambiguous`, `unverifiable`,
  `denied`, or exact `exception`; unresolved values never become fabricated
  certainty. Denied identifiers are checked before exceptions.
- Exceptions require exact ecosystem, package, version, purl, evidence digest,
  normalized expression, reason, approver, and expiry. Missing, unstructured,
  malformed, stale, mismatched, reference-incomplete, denied, custom SPDX, and
  Unicode-obfuscated reference cases fail closed.
- Hybrid/noncanonical Debian copyright files remain present-unstructured;
  canonical DEP-5 claims stay strict. Symlink/ENOTDIR copyright paths become
  deterministic unverifiable observations without following links.
- Python multiline Header values become deterministic strings while exact
  METADATA remains evidence. R receipt/SBOM inventory is static and includes
  `translations`; prose runtime copyright keeps all 15 R packages unresolved.
- The staged evaluator runs under `python -I -S -B` from exact Git and
  packaging source. Its identity binds the transformed parser, exact SPDX
  snapshots, normalization/classification/report code, semantic dependencies,
  aliases, exceptions, and import-order-independent behavior.
- Candidate volumes and healthchecks are forbidden; every probe disables
  healthchecks. Probe-loaded SBOM source is Git-digest-bound. Exact evidence
  bytes are rehashed from safe root copies or bounded, canonical, non-extracted
  Docker archives.
- Production activation remains `disabled`. Collection isolation passes all
  six required checks, but production containment still fails on unavailable
  CPU and PID controllers. CVE, signature, provenance, and real microVM boot
  remain `not_run`.

## Exact Candidate Evidence

- Source checkpoint: `1397f92b5257747ca3faf99e00a74269d4b14875`.
- Local image ID/config digest:
  `sha256:e47537b8f7ac7c595b3a055dea4d16283efaa9c9a67c0f8a3e0fc2d65e834e29`.
- OCI manifest:
  `sha256:0064ce70a26d6df58353a2e305a69d1d03e1db4525eee9870841fe10c6b3d02a`;
  23 `linux/amd64` layers.
- Subject SHA-256:
  `1973c18983231fc04bae2cae3c6ea83ac4aef3073fdd723f8361069c66e77bd5`.
- Package inventory: Debian 1,152, Python 255, R 15, npm 1; total 1,423.
- Effective SBOM canonical SHA-256:
  `d255981ec7a5f31091a8d83c8e8c0e099ce312f95da052c01bc361c29551547b`.
- License evidence: 1,423 records, 1,720 physical files, canonical SHA-256
  `53bd61004c298ddddad065730e408228f1a795d3cb06b2b804abb70d4c1f2297`,
  raw file SHA-256
  `bee961e424cdd356eae5db67600829eeeaf28ac423cd14ee04bd702d89980043`.
- Evaluator callable identity:
  `825f97f04b9b94c048326625a7e56b6a0960b196964dabcf4ba7ad3e8e9b3056`.
- Decisions SHA-256:
  `cbf6946482114ec8e9948e845653ec525dcbdccedd585623a320d7c9fc8f7eff`.
- Overall classifications: 186 resolved, 898 ambiguous, 1 missing metadata,
  338 unverifiable, 0 denied, and 0 exceptions; unresolved total 1,237.
- Debian: 842 ambiguous, 310 unverifiable. Python: 185 resolved, 56
  ambiguous, 13 unverifiable, 1 missing. R: 15 unverifiable. npm: 1 resolved.
- License status: `failed`; aggregate gate: `blocked`. Blocking evidence:
  containment, CVE, license, microVM, provenance, and signature.

## Verification

- Phase 1B/1C focused contracts: **372 passed**, 1 integration marker
  deselected.
- Exact local Docker/OCI integration: **1 passed** in 161.30 seconds.
- Agentic, sandbox, hardened-sandbox, and executor regression: **923 passed**,
  1 host-dependent skipped, and 8 integration tests deselected.
- Complete credential-free backend: **2,927 passed**, 6 host-dependent skipped,
  and 45 integration tests deselected in 112.70 seconds.
- Persisted evidence directory semantic reopening passed, including OCI blob
  verification, receipt/SBOM reconciliation, evaluator recomputation, report
  binding, and unsupported-evidence absence.
- The final collector output matched the persisted evidence and a second cold
  run byte-for-byte; all three raw SHA-256 values were `bee961e424cd...`.
- Draft 2020-12 schema validation, Ruff, `py_compile`, `pip check`, static
  diagnostics, and `git diff --check` passed.
- Independent adversarial review iterated through metadata parsing, evidence
  paths, denied/exception precedence, lifecycle cleanup, revision and source
  binding, archive handling, import-order identity, parser globals, builtin and
  regex poisoning, and complete classification dependencies to final
  **APPROVE** with zero mandatory or optional findings.
- No model, Azure, grading, Hugging Face write/upload, registry login/push,
  publication, workflow dispatch, deployment, or paid operation ran.

## Shipment

- Implementation branch: `feat/agentic-v2-phase1c-license-evidence`.
- Current reviewed checkpoint: `1397f92b5257747ca3faf99e00a74269d4b14875`.
- Push, pull request, remote checks, squash merge, and completion-only record PR
  remain pending at this checkpoint.

## Remaining Work

- Ship the reviewed branch through a pull request and record its squash-merge
  identity; update this rolling record in a completion-only PR if needed.
- Production remains blocked on enforceable CPU/PID containment, complete
  retained/transitive package artifacts, a pinned CVE scanner and database,
  approved signature trust root, provenance attestation, and a real
  Firecracker/jailer/KVM boot and cleanup proof.
- Resolve or explicitly review the 1,237 unresolved package licenses before any
  compliance claim. This task makes no license-compliant, vulnerability-free,
  signed, reproducible, release-ready, or production-ready claim.
- Package broker, web egress, model loop, grading, publication, and production
  authorization remain later-phase work.
