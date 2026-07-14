# Latest Task Result

- Updated: 2026-07-15
- Status: Merged; runtime canary pending

## Task

Use the exp026/exp027 paired evidence to harden generated-code execution before
changing Skills selection: reject invalid Python before its body runs, route
runtime failures to category-specific repair strategies, and preserve bounded
provenance across local and Docker backends.

## Result

- Actions run
  [#93](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29324114951)
  completed successfully in 2h47m54s without a relay. Steps 1-7, exact 50-row
  validation, report generation, and Hugging Face upload all passed.
- exp027 produced 23 successes, 14 QA failures, and 13 errors across the
  outcome-selected diagnostic set. Average Self-QA was 5.08 and average task
  latency was 76.78s. Result PR
  [#66](https://github.com/hyeonsangjeon/gdpval-realworks/pull/66) was merged.
- On identical task IDs, exp026 changed from 30/14/6 success/QA-failed/error to
  exp027's 23/14/13. Paired Self-QA was effectively unchanged. This
  directionally supports the complete sandbox/skills/repair bundle for
  execution reliability, but does not isolate any individual component.
- Added a standard-library reproducibility script with immutable HF revisions,
  content hashes, deterministic bootstrap settings, and checked-in paired
  analysis. Outcome-based selection is explicitly treated as diagnostic rather
  than population-level or confirmatory inference.
- Added a dashboard scope guard: exp027 is hidden from the default cross-run
  views and error narratives but restored by `?debug=1`; direct detail access is
  preserved. Existing valid subsets such as exp012 remain visible, and global
  benchmark copy remains fixed at 220 tasks.
- Dashboard guard PR
  [#67](https://github.com/hyeonsangjeon/gdpval-realworks/pull/67) was
  squash-merged as `92efc10518e0cbcd23adcf54b68e8c7355228645`; Pages run
  [29342635220](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29342635220)
  succeeded.
- Result PR [#66](https://github.com/hyeonsangjeon/gdpval-realworks/pull/66)
  was then squash-merged as `2a33c99813bec08b598e5dd272916207c18594da`;
  Pages run
  [29342879619](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29342879619)
  succeeded and published exp027.
- Added a trusted launcher shared by local and Docker execution. It compiles the
  untouched `solution.py` with the actual target interpreter, emits a bounded
  schema-validated preflight record over stderr before untrusted code starts,
  and executes with `runpy` so `_AVAILABLE_FILES` remains available without
  breaking `from __future__` imports.
- Invalid Python consumes the existing bounded repair attempt but never reaches
  its body. Prompt-spec guidance now differs for syntax, input schema, API
  compatibility, binary decode, and memory failures.
- Added stable execution categories shared by local and Docker paths, including
  chained-exception handling, real OOM variants, binary output, timeout,
  backend-unavailable, and stderr-empty nonzero exits.
- Removed the writable preflight sidecar design. The trusted protocol accepts
  only the first 1,024-byte record, validates every field type, ignores later
  spoof records, and survives `chdir`, `os._exit`, SIGKILL, and non-UTF-8 output.
- Best-attempt selection now distinguishes compile-only failures from body
  execution so a repaired runtime failure cannot be hidden behind an earlier
  syntax failure. Manifests use `not_executed` unless compile success proves the
  selected backend reached the generated body.
- Sandbox preflight PR
  [#71](https://github.com/hyeonsangjeon/gdpval-realworks/pull/71) was
  squash-merged to `main` as
  `aa6c35c985c3bdb11cf98f4e0c4a4747968d9f8c`. No workflow was automatically
  dispatched by this backend-only merge.

## Verification

- Actions #93 concluded with `success`; HF self-report and parquet both contain
  exactly 50 tasks and matching metrics.
- Dashboard/aggregate Node tests: 19 passed.
- Paired-analysis Python tests: 6 passed; pinned live calculation reproduced
  all checked metrics and source hashes.
- TypeScript `--noEmit`: passed.
- Production Vite build: passed.
- Python compile and `git diff --check`: passed.
- Validation-generated `public/generated`, `dist`, and cache directories were
  removed from the worktree.
- Deployed `reports-index.json` contains 23 raw experiments, including exp027 at
  23/50, 46.0%, and Self-QA 5.08; exp026 remains 200/220, 90.9%, and 6.24.
- Browser default view shows 22 experiments, excludes exp027 from leaderboard
  and Execution Errors, and keeps both KPI/copy values at 220 tasks.
- Browser `?debug=1` view restores 23 experiments and exp027's 23/50 metrics
  while retaining the 220-task global KPI.
- Clicking exp027 and directly opening `/experiments/exp027` both render the
  detail page with the expected metrics. GitHub Pages serves the direct SPA
  deep link through its 404 fallback, so the initial HTTP response remains 404
  even though the application recovers and renders correctly.
- Four changed Python modules compile successfully.
- Focused sandbox/local execution regression suite: 195 passed, 0 failed, 0
  skipped, including the actual `gdpval-sandbox:latest` Python 3.11 boundary.
- `git diff --check` passed; executable sidecar references are absent; editor
  diagnostics and independent final review reported no findings.

## Remaining Work

- Add a normalized workbook/document schema manifest before generation and
  repair, then harden ffmpeg/video execution with bounded output and explicit
  container cleanup.
- Skills and perception changes still require separate controlled ablations;
  the paired run did not justify changing the selector yet.
- Run rubric-based LLM-judge grading separately if exp027 needs quality
  comparison beyond Self-QA.
- Run an owner-approved bounded sandbox canary before treating the repair
  strategy as production-validated; no paid model or batch run was dispatched
  by PR #71.
