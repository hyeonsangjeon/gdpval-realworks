# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-15
- Status: Vision canary acceptance failed; invalid results reverted and fixes verified

## Task

- Merge the downloader direct-entry fix and rerun the separately approved
  Azure Vision canary on exactly one pinned exp003 XLSX task.
- Accept only one render call, one perception call, complete usage accounting,
  relative-path visual provenance, and effective cost below USD 1.
- Revert any committed result that fails those gates and do not dispatch a
  child, relay, or full grading run.

## Result

- PR #78 merged as `1f9a5a42`, and run
  [29424766879](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29424766879)
  used the approved experiment, `default_v2_mini.yaml`, inference revision
  `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`, task
  `83d10b06-26d1-4636-a32c-23f92c57f30b`, and selected `Sample.xlsx`.
- Input validation, renderer installation/preflight, Azure OIDC, pinned HF
  download, one XLSX render, and one vision request ran. No child or relay run
  was dispatched, and no API-key fallback or secret exposure was found.
- Acceptance failed. All 35 main requests returned HTTP 400 because the
  106-character `prompt_cache_key` exceeded Azure's 64-character limit. The
  vision request recorded 1,108 input and 248 output tokens but returned an
  invalid semantic envelope. All 36 judged items were `judge_error`, aggregate
  usage was incomplete, and the score-only summary incorrectly displayed 100%.
- The invalid grade commit `da1d57a8` and analysis commit `a1cc84da` were
  reverted by `8cddfda` and `9508d83`; both generated files are absent from
  the resulting tree.
- Long cache identities now use a deterministic 64-character SHA-256 key. The
  vision prompt states the exact envelope contract, semantic strings are safely
  normalized and bounded, and validation failures log only their reason.
- Track 2 now atomically persists a diagnostic but exits nonzero after a real
  main/perception/render runtime failure or incomplete usage. Error tasks no
  longer inflate score summaries, and cache/resume rejects failed diagnostics
  before constructing a grader. Existing call-free `selection_error` and
  `no_deliverables` diagnostics retain their prior behavior.

## Verification

- Affected wiring, vision, tool-calling, Step 8, cache, resume, and workflow
  suite: **161 passed**.
- Broader non-integration suite excluding the unavailable local GDPVal parquet
  fixture: **1,125 passed, 2 skipped, 37 deselected**. The omitted selector
  module failed collection only because
  `data/gdpval-local/data/train-00000-of-00001.parquet` is not present.
- Static diagnostics found no errors in the seven changed Python files.
- `git diff --check` passed.

## Remaining Work

- Merge the canary hardening and artifact reverts, then rerun the exact same
  one-task canary once from the resulting `main`.
- Require successful main verdicts, exactly one render and perception call,
  complete main/perception usage, valid relative-path provenance, and effective
  cost below USD 1.
- Do not expand to a full grading run from this canary.
