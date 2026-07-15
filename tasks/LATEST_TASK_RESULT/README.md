# Latest Task Result

- Updated: 2026-07-15
- Status: Merged and deployed; runtime canary pending

## Task

Add job-performance metrics for the next sandbox experiment while keeping
existing experiment JSON and dashboard behavior unchanged when metrics are not
available.

## Result

- Added explicit opt-in configuration through `execution.metrics.enabled` and
  preserved it through config parsing, Step 1, executor construction, and the
  prompt-architecture index. Only the literal boolean `true` enables metrics;
  omitted, false, malformed, or string values do not emit metric keys, and
  undeclared fields are discarded.
- Sandbox attempts now measure model, tool, verification, and dependency time.
  Step 2 aggregates those measurements across sandbox repair and Self-QA
  regeneration, adds orchestration time, and preserves cumulative task lifetime
  across resume rounds.
- `time_to_valid_artifact_ms` is recorded only after a file is saved and the
  sandbox reports `ok` or `repaired_ok` with at least one verified non-manifest
  artifact. Text-only, manifest-only, and unsuccessful file tasks retain `null`.
- Duration and count fields use finite 30-day/1,000,000 schema bounds, strict
  integer counters, overflow-safe resume merging, and `allow_nan=False` JSON
  serialization so persisted output remains standards-compliant. Giant JSON
  integers are rejected before float conversion instead of raising overflow.
- Wall-timeout checkpoints retain the original pending task object and relay
  completion replaces it through the normal merge path, preserving prior phase
  time, counts, job runs, and time-to-valid offsets without duplicate rows.
- Step 3 strictly serializes the final result once before opening either output
  file; invalid NaN/Infinity values cannot update one result while leaving the
  other stale.
- Step 6 emits an optional aggregate only when measured data exists: coverage,
  average/P50/P95/max job time, successful and failed job averages,
  time-to-valid-file, phase totals, and execution/tool/Self-QA/job-run counts.
- The experiment detail page conditionally renders Job Performance metrics, a
  sortable Job Time column, and per-task timing details. Legacy reports keep the
  existing table, modal, and metric cards without placeholders for new fields.
- Added sandbox documentation for enabling and interpreting the metrics. No
  existing experiment config or result fixture was rewritten, and no paid model,
  batch, grading, or canary run was automatically dispatched by the feature.
- Feature PR [#76](https://github.com/hyeonsangjeon/gdpval-realworks/pull/76)
  was squash-merged to `main` as `3258b5c3265136b06a4661c16a521bd8c4887005`.
  Automatic `Aggregate Tests & Deploy` run
  [29423221608](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29423221608)
  completed successfully and was the only workflow automatically triggered by
  the merge. A separate owner-dispatched grading run
  [29423860683](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29423860683)
  later targeted the same SHA and failed while downloading inference results
  from Hugging Face. `Run grading` and artifact upload were skipped, so it made
  no model/API grading call or paid inference request.

## Verification

- Latest-main integrated real-dependency regression: 200 passed, 1 skipped, 0
  failed under Python 3.11 with installed `pyarrow`, `datasets`,
  `huggingface_hub`, and `psutil`; no global dependency stubs were used. This
  includes the renderer preflight tests added through main commit `129d13f2`.
- Dashboard aggregate tests: 21 passed, 0 failed.
- Focused review-fix tests cover strict opt-in normalization, numeric bounds,
  overflow fallback, manifest-only exclusion, restored QA test collection,
  resume-timeout relay accumulation, and Step 3 strict dual-output writes.
- Python compilation, editor diagnostics, and `git diff --check`: passed.
- TypeScript compilation and production Vite build: passed.
- Browser-verified a metrics-enabled fixture at desktop and 390px mobile widths:
  aggregate panel, Job Time column, sorting surface, and task modal values render.
- Browser-verified a legacy fixture: zero Job Performance panels, zero Job Time
  columns, and the existing Latency column remains visible.
- Existing generated report data remains unchanged unless an experiment opts in.

## Remaining Work

- Enable `execution.metrics.enabled: true` in the next experiment YAML; existing
  experiment definitions intentionally remain unchanged.
- Run an owner-approved bounded canary to validate live timing distributions
  before using them for model or agent comparisons.
- The proposed free-form tool-calling/install loop is a separate execution-mode
  change and still needs an allowlisted package broker, budgets, and an A/B run.
