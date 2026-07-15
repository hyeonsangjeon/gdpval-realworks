# Latest Task Result

- Updated: 2026-07-15
- Status: Vision canary stopped before model call; downloader fix verified

## Task

- Start the separately approved, limited Azure Vision canary after the
  GitHub-hosted LibreOffice preflight passed.
- Restrict the run to one existing XLSX task, one planned vision call, and an
  expected total cost below USD 1.
- Stop before model execution if source, renderer, authentication, or task-plan
  gates do not match the approved scope.

## Result

- The original exp998 candidate was rejected before dispatch because its pinned
  first task is DOCX and would produce zero vision calls. The canary was moved
  to exp003 task `83d10b06-26d1-4636-a32c-23f92c57f30b`, whose selected
  `Sample.xlsx` has exactly one planned Overall Style vision call.
- Approved grade run
  [29423860683](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29423860683)
  started on `main` commit `3258b5c3` with pinned inference revision
  `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`, `default_v2_mini.yaml`, and
  `tasks_limit=1`.
- Workflow input validation, dependency installation, LibreOffice renderer
  preflight, and Azure OIDC all passed. Renderer evidence matched the approved
  run: LibreOffice 24.2.7.2, PyMuPDF 1.28.0, XLSX 17,358 bytes, and PPTX 18,637
  bytes.
- The run failed at the HF downloader entrypoint with
  `ModuleNotFoundError: core`. Grading was skipped, no child/relay run appeared,
  no grade artifact or commit was produced, and Azure/model cost was USD 0.
- The downloader now bootstraps only the required
  `core.inference_manifest` namespace when run as a script. The workflow commit
  step additionally checks `steps.grade.conclusion == 'success'`, preventing a
  secondary missing-grade failure after an upstream stop.

## Verification

- Downloader direct-entry, downloader behavior, and step8 workflow tests:
  **112 passed**.
- Track 2 and shared grader regression suite: **449 passed** with one existing
  PyPDF2 deprecation warning.
- Direct `python scripts/download_inference_from_hf.py --help` succeeds and
  exposes `--revision` without a `core` import error.
- `git diff --check` passed.

## Remaining Work

- Merge the downloader fix PR and rerun the exact same canary scope once from
  the then-current `main`, retaining the pinned exp003 inference revision.
- Accept only one task, one render call, one perception call,
  `usage_complete=true`, valid visual provenance, and total cost below USD 1.
- Do not expand to a full grading run from this canary.
