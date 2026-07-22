# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-22
- Status: Shipped via PR #129

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
- Code Interpreter uploads retain the verified local basename so provider-side
  file type and extension are explicit. The common sandbox still stages local
  references privately, while the hardened remote backend carries opaque
  reference IDs through to its compute backend without a second host-path copy.
- Step 1 assigns a run-specific publication generation before its prepared
  fingerprint is calculated. Fresh GitHub/local runs receive a new generation,
  relay legs preserve the initial lineage, and Step 2 validates it before
  manifest loading, provider-client construction, or model spend.
- Relay checkpoints canonicalize ordered/result task IDs, reject unknown result
  statuses, and require each deliverable path to be owned by its result task.
  Before the first execution and each QA retry, Step 2 removes the prior task
  output tree with symlink-aware file/directory handling instead of silently
  retaining stale artifacts.
- Condition A keeps the canonical publication/relay upload root while condition
  B writes to an isolated root. Step 2 binds every selected file to its
  same-descriptor SHA-256/size and includes those records in a canonical result
  fingerprint, so later same-path byte drift fails before any HF call.
- Step 0 always creates and clears all submitter columns and rejects stale text,
  scalar/list manifests, URL/URI values, or physical outputs on reused targets.
  Step 4 rebuilds production selected rows from current results. Step 7 requires
  one canonical parquet shard, row-owned deliverable paths, canonical URLs/URIs,
  and exact parquet-to-current-Step-2 text/file/URL/URI/byte equality. Step 3 and
  publication use one shared production-shaped projection of prepared metadata
  plus raw Step 2 nested QA/results. The non-dry self-report must match its run
  generation, prepared/result fingerprints, task order, status, summary, and
  files. Step 5 records missing file-required outputs as failed empty rows and
  never creates dummy files or mutates the parquet after result identity binds.
- Step 0 records the validated target HEAD. Step 7 performs one HF
  `create_commit(parent_commit=...)`, then proves direct ancestry, plan marker,
  exact remote tree/hashes, self-report identity, and final HEAD. Ambiguous
  marker and publication responses are reconciled without retry. Relay cleanup
  requires the exact restored checkpoint generation, and a private local
  receipt binds the publication plan so post-cleanup verification accepts only
  the exact cleanup child with an unchanged managed tree.
- Added model-free checkpoint identity validation after Step 1 and before Azure
  login/model-client construction. Missing progress, lineage/fingerprint drift,
  or incomplete deliverables abort the continuation instead of rerunning tasks.
- Renamed runtime evidence to `step_timeout_headroom_minutes`; the UI/docs state
  that the nominal 60-minute difference is best-effort, not reserved handoff
  time. Operators must not overlap runs sharing one HF target.

## Verification

- Rebased base: `origin/main@723826c9f8a1c3b6c9b10d8d3ad0082d5810e07a`.
- Full backend non-integration suite: **1,851 passed, 6 skipped, 44 deselected,
  0 failed**.
- Focused manifest/reference, relay, publication, output, bootstrap, inference,
  corruption, observability, and agentic trust matrix: **361 passed**.
- Final production-shaped publication/report/subset/relay matrix: **188 passed**;
  condition isolation and byte-finality matrix: **136 passed**; final status,
  no-dummy, and cleanup-generation matrix: **156 passed**. The full suite above
  includes every current version of those tests.
- Focused trust matrices passed for relay generation/marker/CAS, schema v4
  source semantics, private reference staging, provider/local/Docker failures,
  manifest pre-client gates, Step 0 stale-state rejection, Step 4 current-run
  rebuilding, and Step 7 exact publication. The final Step 0 safety matrix is
  **65 passed**, relay checkpoint/status matrix is **82 passed**, and HF
  publication/finality matrix is **85 passed**. These include source-first
  mutation ordering, post-create drift rejection, canonical target columns,
  exact-generation cleanup, realistic HF cache symlinks, and non-relay
  file-verification call bounds.
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
- actionlint 1.7.7 reported no diagnostics for the changed `batch-run.yml`; its
  eight-test executable onboarding contract passed and all six external actions
  remain pinned to 40-character SHAs. All eight active workflows parsed as
  YAML. Ruff and `py_compile` passed for **43 changed Python files**; the
  production TypeScript/Vite build and `git diff --check` also passed.
  `huggingface-hub==1.24.0` pins the verified write-auth, immutable-revision,
  and CAS API surface.
- No workflow dispatch, Azure login, model/API call, batch/grading run, HF write,
  network checkpoint write, or paid execution occurred. Public source bytes
  were downloaded read-only to verify canonical identities.

## Shipment

- PR #129 squash-merged as
  `2d4026056b6e27f5111a94d1089573f6b4938a58` on 2026-07-22.
- Automatic pull-request run
  [29919172383](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29919172383)
  completed with `validate` successful and `deploy` skipped.
- Automatic `main` push run
  [29919336511](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29919336511)
  completed with both `validate` and GitHub Pages `deploy` successful.
- These were free automatic repository checks. No `workflow_dispatch`, grading,
  Step 8, Azure/model API, Hugging Face write, or paid execution ran.

## Remaining Work

- No repository implementation work remains for this task. Repository branch
  protection remains a separate administrative control; the exact-main
  preflight does not replace a protected `main` ruleset.
