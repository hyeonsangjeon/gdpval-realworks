# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-22
- Status: Shipped via PR #127

## Task

- Put direct dashboard, sample config, Batch workflow, and result/artifact paths
  in the English and Korean root README start sections.
- Align both Batch Runner references and beginner guides with the executable
  OIDC, bootstrap, dry-run, report, publication, artifact, and relay contracts.
- Fail closed before Azure/model spend when dispatch identity, relay source,
  checkpoint identity, write authorization, or referenced deliverables cannot
  be proven.
- Bind Step 0 and relay state to immutable source/input identities so reused
  Hugging Face targets cannot silently change paid model inputs.

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
  `current.json` advances only after downloading and verifying the exact remote
  tree and every SHA-256/size record. Restore and cleanup require the expected
  source SHA, lineage, and complete ordered task set. Cleanup confirms success
  within the same invocation when the CAS commit response is lost.
- Added a non-mutating HF write-access preflight after Step 0 and before task
  preparation, Azure login, or model spend. Read-only sources such as the
  official public dataset fail before paid execution.
- Step 0 authenticates before `create_repo(exist_ok=False)`, treats only HTTP
  409 as an existing target, propagates auth/rate/server/network failures, and
  never auto-deletes partial or legacy targets. The public source is pinned to
  one full revision. New targets persist a schema-3 manifest; reused targets are
  staged at an exact HEAD and accepted only when the canonical model-input
  projection, ordered task identity, policy signals, physical reference tree,
  and every declared reference SHA-256/size match the pinned contract.
- Added model-free checkpoint identity validation after Step 1 and before Azure
  login/model-client construction. Missing progress, lineage/fingerprint drift,
  or incomplete deliverables abort the continuation instead of rerunning tasks.
- Renamed runtime evidence to `step_timeout_headroom_minutes`; the UI/docs state
  that the nominal 60-minute difference is best-effort, not reserved handoff
  time. Operators must not overlap runs sharing one HF target.

## Verification

- Base identity: `origin/main@77d76bc8fd7567ef140bd113c252fcf02e0aae68`.
- Focused Step 0 provenance/safety plus relay transport/identity suites:
  **83 passed**. Coverage includes create-once/409 behavior, no deletion,
  canonical source projection mutation, selective pinned-source download,
  exact target HEAD refresh, prior-local preservation, schema/reference drift,
  symlinks, immutable remote byte verification, complete task sets, cleanup CAS
  races, response-loss recovery, and pre-model-client rejection.
- Full backend non-integration suite: **1,638 passed, 6 skipped, 44 deselected**
  from 1,686 collected tests; no failures.
- Complete frontend aggregate contracts: **84 passed**, including **7/7**
  onboarding contracts. Production aggregate and TypeScript/Vite build passed;
  runtime, integrity, perception, and success browser suites all passed.
- Documentation structure: six documents, **157 links**, **100 local
  file/anchor targets**, **12 fork-relative Actions routes**, and four system-map
  SVGs validated with no broken target, unbalanced fence, or `mermaid.ink` use.
- `actionlint` 1.7.12 reported no diagnostics for `batch-run.yml`. Ruff,
  `py_compile`, YAML parsing, independent high-risk review, and
  `git diff --check` passed. The reviewer verdict was **APPROVE** with no
  blocker, major, or minor findings on the authoritative shell-disk files.
- Read-only public Hugging Face checks confirmed the pinned source revision,
  220-row projection digest, 261 unique declared references, and policy-specific
  schema-3 manifest digests. Only metadata and 5.72 MB of non-LFS public
  reference bytes were read; no repository write occurred.
- No workflow dispatch, Azure login, model/API call, batch/grading run, Hugging
  Face write, checkpoint mutation, deployment, publication, or paid execution
  occurred.

## Shipment

- PR #127 merged as
  `30906084dbee384f1c324a8b794cba5aef28170b` on 2026-07-22.
- Automatic pull-request run
  [29889565405](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29889565405)
  completed in 1 minute 43 seconds with `validate` successful and `deploy`
  skipped.
- Automatic `main` push run
  [29889682507](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29889682507)
  completed in 2 minutes 19 seconds with both `validate` and the GitHub Pages
  `deploy` job successful.
- These were automatic free repository checks. No `workflow_dispatch`, grading,
  Step 8, Azure/model API, Hugging Face upload, or paid execution ran for either
  run.

## Remaining Work

- No repository implementation work remains for this task.
- Repository branch protection remains a separate administrative control; the
  exact-main preflight does not replace a protected `main` ruleset.
- Path cleanup removes only the current Hugging Face tree. Prior revisions may
  retain history, and overlapping runs must not share one target.
