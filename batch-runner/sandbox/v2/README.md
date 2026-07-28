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
2. verifies the exact local parent;
3. creates only a local Docker tag;
4. verifies the disabled entrypoint;
5. exports a local Docker archive into a host-verified OCI layout;
6. runs the candidate with no network, read-only root, fixed non-root identity,
   dropped capabilities, resource caps, and ephemeral tmpfs workspaces;
7. writes a candidate receipt, OCI report, SPDX SBOM, license report, microVM
   readiness report, and aggregate gate report.

There is no login, push, promotion, `latest` tag, workflow, model client,
experiment, or publication path in this directory.

## Evidence Meanings

| Evidence | Candidate behavior |
|---|---|
| Capability receipt | Verified against one exact local image/config/OCI digest |
| OCI layout | Host-generated and every blob rehashed |
| Effective SBOM | Generated from installed Debian, Python, R, and npm metadata |
| License | Conservative; unknown or denied licenses fail |
| CVE | `not_run` until a pinned scanner and DB snapshot are supplied |
| Signature | `not_run` until an approved offline trust root and bundle exist |
| Provenance | `not_run` until source/locks/build/SBOM policy subjects are attested |
| MicroVM | `not_run` unless Firecracker, jailer, KVM, kernel, and rootfs exist |

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