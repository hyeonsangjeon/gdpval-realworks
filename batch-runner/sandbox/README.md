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
   code's imports).
2. Copies reference files and the `skills/` package into a temp dir.
3. Writes `solution.py` and runs it as
   `docker run --rm --network none … gdpval-sandbox:latest python -u solution.py`.
4. Collects newly created files (excluding inputs, the script, and `skills/`) as
   deliverables.

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
```

The same `SANDBOX_IMAGE` env var read by `build.sh` is also the default image
the runner looks for, so they stay in sync.

## Security posture

The threat model is *untrusted, LLM-generated code*. Isolation comes from the
container namespaces, no network, and the resource caps above. Code runs as the
image's default user inside a disposable container that is removed (`--rm`) after
each task. When Docker is unavailable the local fallback still applies the
existing subprocess hardening (isolated temp dir, restricted execution).
