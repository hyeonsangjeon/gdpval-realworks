# Latest Task Result

- Updated: 2026-07-14
- Status: Completed and deployed

## Task

Complete the bounded exp027 subprocess diagnostic, compare it with exp026 on
the exact pinned 50-task set, and prevent the diagnostic subset from changing
the default 220-task dashboard scope before its result report is merged.

## Result

- Actions run
  [#93](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29324114951)
  completed successfully in 2h47m54s without a relay. Steps 1-7, exact 50-row
  validation, report generation, and Hugging Face upload all passed.
- exp027 produced 23 successes, 14 QA failures, and 13 errors across the
  outcome-selected diagnostic set. Average Self-QA was 5.08 and average task
  latency was 76.78s. Result PR
  [#66](https://github.com/hyeonsangjeon/gdpval-realworks/pull/66) is open.
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

## Remaining Work

- Prioritize syntax preflight, schema introspection, exception-specific repair,
  binary-safe ffmpeg handling, and bounded video memory before any Skills
  selector change. Skills and perception changes still require separate
  controlled ablations.
- Run rubric-based LLM-judge grading separately if exp027 needs quality
  comparison beyond Self-QA.
