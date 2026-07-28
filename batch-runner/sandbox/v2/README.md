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
4. verifies the disabled entrypoint and exports a host-verified OCI layout;
5. probes effective containment in the trusted exact parent before candidate
  code can run;
6. runs the candidate probe and SBOM only when every network, rootfs, identity,
  capability, privilege, memory, PID, and CPU containment check is enforced;
7. always writes subject, OCI, containment, microVM-readiness, and aggregate
  gate reports; receipt, SBOM, and license files exist only after verified
  containment.

There is no login, push, promotion, `latest` tag, workflow, model client,
experiment, or publication path in this directory.

## Evidence Meanings

| Evidence | Candidate behavior |
|---|---|
| Capability receipt | `not_run` until containment is verified; then bound to one exact local image/config/OCI digest |
| OCI layout | Host-generated and every blob rehashed |
| Effective SBOM | `not_run` until containment is verified; then generated from exact installed Debian, Python, R, and npm records |
| License | `not_run` with no SBOM; otherwise unknown or denied SPDX expressions fail |
| CVE | `not_run` until a pinned scanner and DB snapshot are supplied |
| Signature | `not_run` until an approved offline trust root and bundle exist |
| Provenance | `not_run` until source/locks/build/SBOM policy subjects are attested |
| MicroVM | `not_run` unless Firecracker, jailer, KVM, kernel, and rootfs exist |

## Validated Checkpoint

Commit `5bab79f6bfbb2f3b75f7904035a4b3b5b39314dc` produced one local-only
candidate:

- image ID:
  `sha256:faed2a1b0638d9a34e2144eb5914c78ea2a6c19f198d61aff03a8fb90bb0de78`;
- OCI manifest:
  `sha256:5046051464690f95eb561c60cc424de42ce90a9764bba3a7b2580648749220c9`;
- OCI status: `verified`, 22 layers, `linux/amd64`;
- containment status: `failed` because this host cannot enforce CPU quota or
  PID limits;
- capability, SBOM, and license: `not_run`, with no corresponding files;
- CVE, signature, provenance, and microVM: `not_run`;
- aggregate gate: `blocked`, with production activation still `disabled`.

This result proves fail-closed candidate construction and evidence handling. It
does not prove the professional-work capability matrix for this final image,
because candidate code correctly did not execute on the degraded host.

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