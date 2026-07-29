# Agentic Sandbox V2 Phase 1B Candidate

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

## Local Candidate Build

From a **clean committed worktree**:

```bash
cd batch-runner
python sandbox/v2/build_candidate.py \
  --output-root /tmp/gdpval-agentic-v2-phase1b-evidence
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
| License | `not_run` with no SBOM; otherwise unknown or denied SPDX expressions fail |
| CVE | `not_run` until a pinned scanner and DB snapshot are supplied |
| Signature | `not_run` until an approved offline trust root and bundle exist |
| Provenance | `not_run` until source/locks/build/SBOM policy subjects are attested |
| MicroVM | `not_run` unless Firecracker, jailer, KVM, kernel, and rootfs exist |

## Validated Checkpoint

Commit `133df3f0aa5e4361c6c6cb7fd142ef5bdff8c1b5` produced one local-only
candidate:

- image ID:
  `sha256:dea418e4964c2e73bf77496633d0e16e5fc4fb66dddbb743d91d0020b672a77a`;
- OCI manifest:
  `sha256:e55817b206dfc4fed855742b327bf6a7c7bdd3b08bc391c2470f9b16efa7f525`;
- OCI status: `verified`, 22 layers, `linux/amd64`;
- collection isolation: `verified` for network, read-only root, non-root
  identity, dropped capabilities, no-new-privileges, and memory;
- production containment: `failed` only because this host cannot enforce CPU
  quota or PID limits;
- capability receipt: `verified` for 20 commands, 13 Python modules, three font
  families, and all nine artifact smokes;
- effective SPDX SBOM: `verified` for 1,422 packages across Debian, Python, R,
  and npm inventories;
- license: `failed` on 1,255 unknown declarations with zero denied packages;
- CVE, signature, provenance, and microVM: `not_run`;
- aggregate gate: `blocked`, with production activation still `disabled`.

This result proves the exact candidate's observed professional-work capability
matrix and SBOM while keeping production execution fail-closed. It does not
prove a complete dependency lock, license compliance, vulnerability status,
signature, provenance, or microVM isolation.

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
- Phase 1A remains fixture-only. Real package broker, web, model, grading, and
  publication paths remain disabled.