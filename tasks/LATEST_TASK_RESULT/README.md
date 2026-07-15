# Latest Task Result

- Updated: 2026-07-15
- Status: GitHub-hosted renderer preflight passed

## Task

- Add a model-free GitHub-hosted LibreOffice preflight for the Track 2 grading
  renderer.
- Keep the preflight manual, read-only, secret-free, and isolated from HF,
  Azure, batch inference, and paid model calls.
- Share the renderer Python dependency declaration with the production grading
  environment so both paths exercise the same package constraints.

## Result

- Preflight workflow PR #73 was squash-merged to `main` as `fa8bf4f1` and
  model-free run
  [29392707519](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29392707519)
  was dispatched. LibreOffice/font installation and renderer Python dependency
  installation succeeded; no Azure, HF, batch, or model step existed.
- The first run failed before rendering because direct execution from
  `batch-runner/scripts` could not import `core`. The uploaded failure artifact
  preserved that evidence. The script now inserts its own batch-runner root and
  bootstraps only the lightweight `core.tools` namespace, avoiding unrelated
  dataset/pyarrow imports.
- Import fix PR #74 was squash-merged as `f97cc170`. The model-free rerun
  [29393149367](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29393149367)
  then completed successfully on that exact `main` SHA. Every workflow step,
  including seven-day evidence artifact upload, passed.
- Added `.github/workflows/grading-renderer-preflight.yml`, dispatched manually
  on `main` only with `contents: read`, no environment, no OIDC, and no secret
  references. Checkout, Python setup, and artifact upload actions are pinned to
  full commits.
- The workflow installs LibreOffice Calc/Impress plus the exact font surface,
  runs the existing synthetic XLSX/PPTX renderer probe, requires both process
  success and JSON `ok=true`, and retains the compact evidence JSON for seven
  days even when the probe fails.
- Added `batch-runner/requirements-renderer.txt`; full batch dependencies now
  include this shared file instead of declaring the four renderer packages in
  separate sections.
- Added a static workflow contract test covering trigger, permissions, action
  allowlist, package surface, result handling, and the absence of credential,
  model, grading, and Git-write paths.

## Verification

- Batch-runner non-integration regression coverage: **1,081 passed**, 5
  skipped, and 37 deselected. This combines the broad suite, seven
  data-module suites, and the actual-parquet selector suite without overlap.
- Workflow contract, renderer script, and read-deliverable focused coverage is
  included in that total. After the import fix, its direct run completed with
  **63 passed**.
- Overlay-free direct execution now emits one valid JSON line and reaches the
  expected local `RendererDependencyError` because this SSH host has no
  LibreOffice; it no longer raises `ModuleNotFoundError` for `core` or
  `pyarrow`.
- Shared renderer requirements include and package set were verified, and all
  four declarations parse successfully with the standard requirement parser.
- `git diff --check` passed.
- `extreme-reasoner` approved the no-secret/no-cost workflow design with the
  shared dependency and action-pinning conditions implemented.
- Hosted evidence reported `ok=true`, exact font family `Liberation Sans`,
  LibreOffice `24.2.7.2 420(Build:2)`, and PyMuPDF `1.28.0`. The synthetic XLSX
  first workbook page rendered to a 17,358-byte PNG; PPTX slide 1 rendered to
  an 18,637-byte PNG.
- Run head SHA matched `f97cc170c1d3f79d7cadde24ae14d12682d1eabe`.

## Remaining Work

- This preflight does not approve paid grading. The limited Azure vision canary
  remains a separate owner-approved step after renderer success.
- No HF/Azure request, batch run, or model call has been performed.