# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-22
- Status: Rebased implementation and local release gates complete; PR/merge pending

## Task

- Put direct dashboard, sample config, Batch workflow, and result/artifact paths
  in the English and Korean root README start sections.
- Align both Batch Runner references and beginner guides with the executable
  OIDC, bootstrap, dry-run, report, publication, artifact, and relay contracts.
- Fail closed before Azure/model spend when dispatch identity, relay source,
  checkpoint/image identity, canonical task/reference semantics, write
  authorization, or publication output identity cannot be proven.

## Result

- Added four fork-safe first-screen routes in both root READMEs and matching
  English/Korean Batch Runner start sections. Local debugging now uses the real
  YAML-driven wrappers and stops before destructive Step 7 publication.
- Corrected OIDC-only workflow guidance, Azure OpenAI resource endpoint scope,
  `dry_run` cost/write behavior, Step 0 fail-closed bootstrap, condition-specific
  checkpoints, Step 6 JSON/Markdown report, Step 7 allowlist, eight dispatch
  inputs/defaults, result PR ordering, and 30-day artifact layout.
- Added exact-main/workflow-SHA preflight, canonical `wall_timeout=0..290` and
  relay bounds, exact checkout checks, initial `source_sha` propagation, and
  `--ref main` continuation dispatch.
- Added fail-closed relay transport using the validated full `data.source`.
  Each payload is a content-addressed generation at one immutable HF revision;
  `current.json` advances only after exact-tree and SHA-256/size verification.
  Marker restore/cleanup also require the expected source SHA, lineage, and
  immutable trusted sandbox image digest. Manual leg 0 cannot inject internal
  relay identity or image inputs.
- Added a non-mutating HF write-access preflight after Step 0 and before task
  preparation, Azure login, or model spend. Read-only sources such as the
  official public dataset fail before paid execution.
- Step 0 now treats only an explicit repository-not-found response as absence,
  propagates 401/403/429/5xx/timeout failures, and refuses automatic deletion of
  existing partial targets. Manifest schema v4 binds all 220 tasks to prompt,
  taxonomy, rubric, ordered reference path/URL/URI semantics and 261 declared
  reference SHA-256/size records from the pinned public source. Step 1 and Step
  2 recheck that identity before prepared output or provider-client creation.
- Every reference is copied to read-only private per-task staging before
  preview, preprocessing, codegen, or execution. Same-file-descriptor hashing,
  fatal provider upload/local/Docker copy errors, basename-collision rejection,
  partial-copy cleanup, and best-effort provider input-file deletion prevent
  missing or changed inputs from silently reaching a model or generated code.
- Step 0 always creates and clears all submitter columns and rejects stale text,
  scalar/list manifests, URL/URI values, or physical outputs on reused targets.
  Step 4 rebuilds production selected rows from current results. Step 7 requires
  one canonical parquet shard, row-owned deliverable paths, canonical URLs/URIs,
  and exact parquet-to-local-file-tree equality before remote cleanup/upload.
- Added model-free checkpoint identity validation after Step 1 and before Azure
  login/model-client construction. Missing progress, lineage/fingerprint drift,
  or incomplete deliverables abort the continuation instead of rerunning tasks.
- Renamed runtime evidence to `step_timeout_headroom_minutes`; the UI/docs state
  that the nominal 60-minute difference is best-effort, not reserved handoff
  time. Operators must not overlap runs sharing one HF target.

## Verification

- Rebased base: `origin/main@30906084dbee384f1c324a8b794cba5aef28170b`.
- Full backend non-integration suite: **1,670 passed, 6 skipped, 44 deselected,
  0 failed**.
- Focused trust matrices passed for relay generation/marker/CAS, schema v4
  source semantics, private reference staging, provider/local/Docker failures,
  manifest pre-client gates, Step 0 stale-state rejection, Step 4 current-run
  rebuilding, and Step 7 exact publication. The merged Step 0 safety matrix is
  **58 passed**, including pinned-source allowlists, exact-HEAD pre-install
  validation, canonical target columns, and previous-snapshot preservation.
- Exact public source verification downloaded **1,670,067,990 bytes** at pinned
  revision `11e7900...`: parquet SHA-256 `f8422fab...`, 220 tasks, 301 physical
  references, 261 declared references, and 220 unique task projections. Four
  policy manifest v4 identities reproduced byte-for-byte three times; default
  manifest SHA-256 is `463fc119...` with 185 needs-files / 35 text-only tasks.
- Onboarding contracts: **8 passed**; complete frontend data contracts:
  **85 passed**.
- Production TypeScript/Vite build and runtime, integrity, perception, and
  success browser suites all passed.
- Documentation structure: **157 links**, **100 file/anchor targets**, **12
  fork-relative Actions routes**, and four system-map SVGs validated with no
  broken target, unbalanced fence, or `mermaid.ink` dependency.
- actionlint reported no diagnostics for `batch-run.yml`; all six external
  actions remain pinned to 40-character SHAs. YAML parse, Ruff, `py_compile`,
  static diagnostics, and `git diff --check` passed across all eight workflows
  and 23 changed Python files. `huggingface-hub==1.24.0` pins the verified
  write-auth, immutable-revision, and CAS API surface.
- No workflow dispatch, Azure login, model/API call, batch/grading run, HF write,
  network checkpoint write, or paid execution occurred. Public source bytes
  were downloaded read-only to verify canonical identities.

## Remaining Work

- Create, review, and merge the pull request, then confirm the free PR validation
  and post-merge Pages run. Do not dispatch a paid batch smoke solely for this
  documentation and fail-closed relay change.
- Repository branch protection remains a separate administrative control; the
  exact-main preflight does not replace a protected `main` ruleset.
