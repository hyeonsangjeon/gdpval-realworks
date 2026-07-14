# GDPVal Sandbox Image

Skill-aware, multimodal **container sandbox** for the `execution.mode: sandbox`
solving path. It is the container evolution of `subprocess` mode.

## What it provides

- **Isolation** — generated `solution.py` runs in a throwaway container with
  `--network none`, a memory cap (`--memory`), `--pids-limit`, and
  `--security-opt no-new-privileges`.
- **Batteries included** — bakes in `batch-runner/requirements.txt` plus the
  system libraries those packages need (ffmpeg, poppler, tesseract, libreoffice,
  graphviz, GDAL/GEOS, the weasyprint stack, espeak-ng, CJK fonts, …) so audio,
  video, document, image, geo, and ML tasks all run.
- **Skills** — the `skills/` package is baked into `/opt/gdpval` (and also
  bind-mounted into the work dir), giving generated code *vision* (video
  frame-by-frame, image OCR) and *hearing* (audio FFT / sampling / loudness).

## Build

From the `batch-runner/` directory (build context must be `batch-runner/`):

```bash
bash sandbox/build.sh
# or a custom tag:
SANDBOX_IMAGE=myrepo/gdpval-sandbox:1.0 bash sandbox/build.sh
```

This produces `gdpval-sandbox:latest` (override with `SANDBOX_IMAGE`).

> ⚠️ The image is large (LibreOffice, GDAL, full scientific stack). The first
> build takes a while; subsequent builds reuse cached layers.

### Rebuild & arm64 recovery

If Docker Desktop is reset (or the image is pruned), `gdpval-sandbox:latest`
must be rebuilt before any Docker-backed run — `use_docker: auto` will otherwise
fall back to the local subprocess sandbox. Rebuild with `bash sandbox/build.sh`
from `batch-runner/`.

**Known arm64 (Apple Silicon) blocker:** `requirements.txt` pins
`aspose-words>=25.0.0`, which ships **no arm64 wheel**, so a native `arm64`
build fails at that layer. Options for local verification on Apple Silicon:

- Build for amd64 under emulation: `docker build --platform linux/amd64 …`
  (slower, but matches CI), **or**
- Build a temporary **trimmed** image with `aspose-words` removed from a scratch
  copy of `requirements.txt` (only `.docx` via `aspose-words` is affected;
  `python-docx`/LibreOffice paths still work). Do **not** commit the trimmed
  requirements.
- After a local `buildx` build, if `docker image inspect gdpval-sandbox:latest`
  can't see the image (classic-store registration quirk), re-register it with
  `docker tag <image-id> gdpval-sandbox:latest`.

CI runners (`ubuntu-latest`, amd64) build the full image without this blocker.

## Host-side perception dependencies (video preprocessing)

The audio/video **preprocessors** run on the **host/orchestrator**, not inside
the sandbox. Audio analysis only base64-encodes the file, but **video** frame
sampling needs a frame backend — `opencv-python` (`cv2`) or `av` (PyAV), both
pinned in `batch-runner/requirements.txt`. If neither is importable on the host,
`video_analyzer` silently no-ops and no frames are ever sent to the model.

`step2_run_inference.py` prints a one-time **preflight warning** at startup when
a `video_analyzer` preprocessor is configured but no host frame backend is
found, so a hybrid run never silently skips video perception. Install the host
perception deps (`pip install -r requirements.txt`) to enable it.

## How the runner uses it

`core/sandbox_runner.py` decides at runtime via `execution.sandbox.use_docker`:

| `use_docker` | Behavior |
|---|---|
| `auto` (default) | Use Docker **if** the daemon is up and the image exists; otherwise fall back to the hardened in-process subprocess sandbox (with a warning). |
| `never` | Always use the local subprocess fallback (handy for laptops/CI without Docker). |
| `always` | Require Docker + image; error if either is missing. |

For each task the runner:

1. Selects relevant **skills** and resolves the **pip dependencies** the task
   needs (from reference-file extensions, task keywords, and the generated
   code's imports), and probes which are importable in the environment.
2. Infers a deterministic **deliverable contract** (expected file types/count)
   and injects it into the codegen prompt so the model knows what to produce.
3. Writes generated code unchanged to `solution.py`. A trusted launcher compiles
  it with the actual target interpreter before running it: Python 3.11 in the
  Docker image, or the current host Python for local fallback. Invalid code
  never reaches its body and consumes the existing bounded repair attempt with
  syntax-specific guidance. The launcher sends bounded compile provenance to
  the parent over stderr before untrusted code starts.
4. Copies reference files and the `skills/` package into a temp dir.
5. Runs the trusted `.gdpval_runner.py` as
  `docker run --rm --network none … gdpval-sandbox:latest python -u .gdpval_runner.py`;
  the launcher compiles and executes the untouched `solution.py` via `runpy`.
6. Selects the **generated artifacts** (copied input names, `solution.py`, the
  trusted runner, directories, and bytecode are excluded), then **verifies** them (non-empty,
   openable, correct type) and runs **render QA** (PDF/Office rasterized to PNG
   with blank-page detection; optional LLM vision QA behind config).
7. If a blocking failure is found and repair is enabled, classifies syntax,
  schema, API compatibility, binary decode, and memory failures, then builds a
  focused **repair prompt** with the matching strategy (bounded; default 1).
8. Writes a `manifest.json` (contract, dependency probe, per-attempt status,
   verification/render reports, and `final_status`) alongside the deliverables.

Skills give the sandbox eyes/ears on the **inputs**; the contract + verifier +
render QA + repair loop verify and fix the **outputs**.

The codegen prompt itself — persona, rules, the order of the injected context
blocks, the self-repair wording, and where perception is placed — is authored in a
single spec file, `prompts/sandbox_occupation_codegen.yaml`. See
[`prompts/sandbox_prompt_authoring.md`](../prompts/sandbox_prompt_authoring.md)
for how to edit it (and how to A/B an alternate spec via `prompt_name` without
touching Python).

## Configure in an experiment YAML

```yaml
execution:
  mode: sandbox
  sandbox:
    image: gdpval-sandbox:latest   # or your custom tag
    use_docker: auto               # auto | never | always
    memory_gb: 5
    cpus: 2.0                       # optional CPU cap
    max_skills: 5                  # skill manuals injected into the prompt
    repair:                        # bounded output repair loop
      enabled: true
      max_attempts: 1              # repair retries after attempt 0
    output_qa:                     # verify + render generated deliverables
      enabled: true
      render: true                 # rasterize PDF/Office to PNG for QA
      max_pages_per_artifact: 3
      blank_page_threshold: 0.999  # per-page near-white warning ratio
      vision:                      # optional LLM vision QA (off by default)
        enabled: false
        provider: azure
        deployment: gpt-5.4
        max_images: 6
    manifest:                      # per-run manifest.json
      enabled: true
      filename: manifest.json
    cache:                         # cache rendered PNGs / perception by sha256
      enabled: true
```

The same `SANDBOX_IMAGE` env var read by `build.sh` is also the default image
the runner looks for, so they stay in sync.

## Security posture

The threat model is *untrusted, LLM-generated code*. Isolation comes from the
container namespaces, no network, and the resource caps above. On POSIX hosts,
the runner passes the host numeric UID/GID with `--user`; otherwise the image
default user is used. The disposable container is removed (`--rm`) after each
task. When Docker is unavailable the local fallback still applies the existing
subprocess hardening (isolated temp dir, restricted execution).
