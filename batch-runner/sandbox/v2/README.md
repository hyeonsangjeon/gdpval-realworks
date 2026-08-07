# Agentic Sandbox V2 Phase 1B/1C/1D-A Candidates

This directory defines a **model-free, local-only professional-work substrate
candidate**. It does not activate `agentic_sandbox_v2`, publish an image, or
authorize production execution.

## Capability Direction

The candidate reaches the baseline expected from general agent benchmarks:

- Bash and core Unix tools;
- Python, Node/npm, R, C, C++, Fortran, Make, and CMake;
- local Chromium;
- LibreOffice, Pandoc, Poppler, Tesseract, and fonts;
- ffmpeg/ffprobe;
- scientific Python, machine learning, GIS, and DXF.

GDPVal adds an artifact-first smoke matrix that generic terminal benchmarks do
not normally require:

1. Office to PDF to extracted text;
2. spreadsheet formula round-trip;
3. local browser screenshot;
4. C/C++/Fortran/CMake compile and execution;
5. deterministic ML fit;
6. GeoPackage round-trip;
7. DXF geometry round-trip;
8. audio/video generation and probe;
9. local OCR.

The distinguishing feature is an **evidence ladder**. One candidate digest is
bound to command binary hashes, Python distribution file-set hashes, font file
hashes, package-inventory digests, smoke artifacts, an OCI manifest, an
effective SPDX document, policy status, and microVM readiness. Missing evidence
stays visible as `not_run`; failed policy stays `failed`; the aggregate gate
stays `blocked`.

## Exact Inputs

- `parent.lock.json` fixes the existing broad GDPVal parent by GHCR manifest
  digest and observed local config digest.
- `debian-extra.lock` fixes the seven top-level Debian additions. The full
  transitive installed inventory is observed in the candidate receipt. A
  retained Debian snapshot and full transitive source lock remain release
  blockers.
- `python-extra.lock` fixes the CPython 3.11 amd64 `ezdxf` wheel by SHA-256.
- `professional-work.Dockerfile` has no default parent and no registry output.
- `disabled_entrypoint.py` exits 78 for every default invocation.

## Phase 1D-A Offline Python Wheel Broker

Phase 1D-A adds a separate **model-free, local-only package activation
candidate**. It is not imported by `TaskExecutor`, Step 2, the Agentic V2
runner, an experiment, a workflow, grading, upload, or publication code. Its
dispatcher candidate exposes package resolve and activation while returning
`capability_unavailable` for workspace mutation, command execution, browser,
verification, and finalization.

The implementation remains under `sandbox/v2/`, outside the existing agentic
image's `COPY core` input and core-tree identity. The tracked
`batch-runner/.dockerignore` also excludes the implementation, this README,
the snapshot schema, broker policy, and tests from existing Docker publication
contexts. Phase 1B/1C explicit build allowlists and embedded-image manifests do
not include the broker.

The checked-in snapshot contract accepts at most eight canonical exact Python
coordinates for the current Linux amd64 Python major/minor. Each artifact must
be a dependency-free `py3-none-any` wheel without a build tag. Admission
reopens exact local bytes, verifies size and SHA-256, validates every bounded
ZIP path and RECORD member, matches METADATA name/version and
`Requires-Python`, rejects `Requires-Dist`, file/directory collisions,
executable-mode entries, `.data`, `.pth`, `.egg-link`, `.pyc`, and all
`sitecustomize`/`usercustomize` forms, and requires one strict WHEEL identity.
The snapshot and runtime policy are both identity-bound.

`environment_resolve` is stateless: it returns the existing V2 lock shape and
does not change backend state. Activation reconstructs an approved lock from
the snapshot, then uses a deterministic stdlib wheel extractor. It does not
invoke pip, a package index, a package installer subprocess, or network code.
Content is staged beneath the already-open private environment-root descriptor,
verified against an independently derived expected inventory, mode-sealed,
and atomically renamed. Canonical receipt bytes bind the exact lock, snapshot,
policy, installer implementation, Python version, file modes, sizes, and
hashes.

Linux `flock` leases serialize processes and preserve shared environments until
the last broker closes. Global state and quota checks validate every live
digest/lease pair, reject unaccounted root entries, and bind all receipt hashes
and payload bytes. Limits include 256 MiB and 4,096 entries per environment,
eight environments and 512 MiB per root, 4,104 cleanup entries, and cleanup
depth 128. Replay uses bounded descriptor-relative traversal and exact-length
reads; FIFO, symlink, hardlink, growth, mode, content, receipt, lease, and root
identity drift fail closed.

This slice does not authorize arbitrary Linux execution. The local Bubblewrap
probe could not create the required user namespace, so `exec_run` remains
`capability_unavailable`. npm, Debian/apt, live indexes, URLs, VCS, sdists,
editable installs, model execution, and production wiring remain disabled.
SBOM, license, CVE, provenance, signature, OS network containment, and crash
durability are explicitly `not_run` or `not_claimed` for package admission.

## Phase 1B/1C Local Candidate Build

From a **clean committed worktree**:

```bash
cd batch-runner
python -I -S -B sandbox/v2/build_candidate.py \
  --output-root /tmp/gdpval-agentic-v2-phase1c-evidence
```

The builder:

1. refuses credential-bearing environments;
2. stages an allowlisted build context and host verifier from exact committed
  Git blobs;
3. verifies the exact local parent and creates only a unique local Docker tag;
4. verifies the disabled entrypoint identity and exports a host-verified OCI
  layout without executing the candidate;
5. verifies six effective collection-isolation checks in the immutable trusted
  parent before fixed candidate evidence probes can run;
6. runs the capability and SBOM probes under network-none, read-only-root,
  non-root, cap-drop, no-new-privileges, memory, timeout, and cleanup controls;
  CPU and PID limits are added when the host supports them;
7. always writes subject, OCI, containment, microVM-readiness, and aggregate
  gate reports; receipt, SBOM, and license files exist only after verified
  collection isolation.

Collection isolation is not production authorization. Production containment
still requires all eight checks, including effective CPU quota and PID limits,
and remains a required blocking evidence item.

There is no login, push, promotion, `latest` tag, workflow, model client,
experiment, or publication path in this directory.

## Evidence Meanings

| Evidence | Candidate behavior |
|---|---|
| Capability receipt | `not_run` until collection isolation is verified; then bound to one exact local image/config/OCI digest |
| OCI layout | Host-generated and every blob rehashed |
| Effective SBOM | `not_run` until collection isolation is verified; then generated from exact installed Debian, Python, R, and npm records |
| License | `not_run` with no SBOM; otherwise exact Debian, Python, R, and npm evidence is classified as resolved, missing, ambiguous, unverifiable, denied, or exact exception; every unresolved class fails |
| CVE | `not_run` until a pinned scanner and DB snapshot are supplied |
| Signature | `not_run` until an approved offline trust root and bundle exist |
| Provenance | `not_run` until source/locks/build/SBOM policy subjects are attested |
| MicroVM | `not_run` unless Firecracker, jailer, KVM, kernel, and rootfs exist |

## Deterministic License Closure

Phase 1C adds a stdlib-only in-image collector and a separately staged host
evaluator. The collector reads exact files from fixed Debian, Python, R, and
npm roots with descriptor-relative no-follow opens. The host validates the
SBOM inventory, reopens 1,720 physical evidence files from the exact image,
normalizes only exact SPDX evidence, and records honest unresolved outcomes.
Package exceptions require exact ecosystem, package, version, purl, evidence
digest, normalized expression, reviewer, reason, and expiry. Denied identifiers
win before exceptions, and unstructured or incomplete referenced evidence is
never exception-eligible.

The evaluator runs under `python -I -S -B` from staged Git and packaging source
bytes. Its callable identity binds the transformed parser, frozen SPDX tables,
normalization/classification/report surface, semantic dependencies, and
import-order-independent runtime behavior. Image-declared volumes and
healthchecks are forbidden; every probe disables healthchecks. R inventory is
shared between the receipt and SPDX generator, including the installed
`translations` package. Symlink-heavy npm and Debian documentation roots are
verified through bounded, non-extracted canonical tar members.

## Validated Checkpoint

Commit `1397f92b5257747ca3faf99e00a74269d4b14875` produced one local-only
candidate:

- image ID:
  `sha256:e47537b8f7ac7c595b3a055dea4d16283efaa9c9a67c0f8a3e0fc2d65e834e29`;
- OCI manifest:
  `sha256:0064ce70a26d6df58353a2e305a69d1d03e1db4525eee9870841fe10c6b3d02a`;
- OCI status: `verified`, 23 layers, `linux/amd64`;
- collection isolation: `verified` for network, read-only root, non-root
  identity, dropped capabilities, no-new-privileges, and memory;
- production containment: `failed` only because this host cannot enforce CPU
  quota or PID limits;
- capability receipt: `verified` for 20 commands, 13 Python modules, three font
  families, and all nine artifact smokes;
- effective SPDX SBOM: `verified` for 1,423 packages: Debian 1,152, Python 255,
  R 15, and npm 1;
- license evidence: 1,423 records and 1,720 exact physical files, deterministic
  raw SHA-256
  `bee961e424cdd356eae5db67600829eeeaf28ac423cd14ee04bd702d89980043`;
- license decisions: 186 resolved, 898 ambiguous, 1 missing metadata, 338
  unverifiable, 0 denied, and 0 exceptions; 1,237 unresolved packages keep the
  license evidence status `failed`;
- CVE, signature, provenance, and microVM: `not_run`;
- aggregate gate: `blocked`, with production activation still `disabled`.

This result proves the exact candidate's observed professional-work capability
matrix, SBOM, and deterministic license-evidence classifications while keeping
production execution fail-closed. It deliberately does not claim license
compliance because 1,237 packages remain unresolved. It also does not prove a
complete dependency lock, vulnerability status, signature, provenance, or
microVM isolation.

## GitHub-Hosted Tier 1 Containment Checkpoint

GitHub Actions run
[`31193818481`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/31193818481)
measured the exact public parent image on `ubuntu-latest` from source
`bedcdd8229cc4b96c93f52323dcf2099acc7a0ca`. The runner reported Linux
`6.17.0-1021-azure`, amd64, and cgroup v2. The machine-readable result SHA-256 is
`5caeb42cbe5032169d520e93160a9e19ecbecc0f066faed96979aa44a2103624`;
the underlying containment report SHA-256 is
`f0c4ec3cdff7d714d0db8aca58b1f5669c3958c6b6203be00095b8acb827e50e`.

| Required containment check | Status |
|---|---|
| Network disabled | `verified` |
| Read-only root filesystem | `verified` |
| Non-root UID/GID | `verified` |
| All capabilities dropped | `verified` |
| No new privileges | `verified` |
| Effective memory limit | `verified` |
| Effective CPU quota | `verified` |
| PID limit | `verified` |

The hosted Docker daemon therefore verifies all eight production-containment
controls, and containment is no longer a blocking item for this exact hosted
measurement. The aggregate gate nevertheless remains `blocked` and production
activation remains `disabled`: Tier 1 did not measure the capability receipt,
CVE, license, microVM, OCI layout, provenance, SBOM, or signature evidence for
one complete candidate subject. This result does not authorize `exec_run` or
Phase 1D-B. A second hosted run on the preceding implementation revision
produced the same containment report, providing one repeatability check.

## Anti-Claims

- The capability receipt records observations for one exact candidate. It is
  not a complete package lock, signature, provenance attestation, vulnerability
  scan, or isolation proof.
- No CVE-free, vulnerability-free, license-compliant, signed, trusted,
  reproducible, release-ready, production-grade, or production-ready claim is
  made.
- MicroVM readiness is not a boot/escape/cleanup proof and does not authorize
  task execution.
- No GHCR image is pushed, promoted, signed, or tagged `latest`.
- Phase 1A remains fixture-only. Phase 1D-A proves only exact local wheel
  activation through a disconnected candidate; production package, web,
  command execution, model, grading, and publication paths remain disabled.