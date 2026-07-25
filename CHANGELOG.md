# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are grouped under dated headings (`## [YYYY-MM-DD]`). The
`## [Unreleased]` block at the top stays empty between releases — new
entries land under a fresh dated heading the day they merge to `main`.

## [Unreleased]

### Added
- **GPT-5.6 Sol Max narrative and grading production policy** - move the
  dashboard narrative analyzer and the default v2 grading profile to
  `gpt-5.6-sol` with `reasoning_effort=max`; use the same identity for the
  main judge, visual perception, and bounded no-tools finalization while
  retaining `gpt-audio-1.5` for audio. Step 6 and Hugging Face publication now
  bind model, effort, runtime fingerprint, and model-backed narrative content;
  explicit all-null identity plus empty narrative remains the only model-free
  fallback. Semantic-invalid final envelopes receive one independent bounded
  retry, and grade schema 1.2 keeps unknown prices fail-closed as explicit
  `null`/incomplete provenance tied to the persisted model set while retaining
  numeric-cost compatibility for prior 1.0/1.1 payloads. The
  grading workflow defaults to a credential-free read-only dry run. Paid runs
  require `paid_approval=true`, a separate protected `grading` Environment
  approval, and then execute Azure OIDC from the environment-free `main`
  branch job so the federated subject remains branch-bound; chunk continuation
  preserves the exact config, inference revision, task limit, and approval
  input while requiring a fresh protected Environment approval for each newly
  dispatched workflow run.
  The remote `grading` Environment has one owner reviewer, administrator bypass
  disabled, and a custom `main`-only deployment policy. Self-review prevention
  remains disabled because no independent collaborator exists. Current manuals
  and specs identify Sol Max as production while preserving historical 5.4
  configs, results, and measurements. Final credential-free validation passes
  **2,358 backend tests** with **6 skipped and 44 deselected**, **94 Node
  contracts**, **9 analysis tests**, both changed workflows under actionlint
  and Ruby Psych, the TypeScript/Vite production build, and all **4 Chromium
  browser suites**. No Azure, model, paid grading, or Hugging Face execution
  occurred.
- **Dashboard source-build provenance** - derive the displayed dashboard
  version from `package.json`, bind Pages builds to the exact checked-out
  GitHub SHA and repository, and link the footer to that full commit only after
  strict public-value validation. Local or malformed builds fail closed to a
  non-link label, while generated-data time remains a separate signal. The
  existing read-only PR validation job now checks published and local browser
  states, exact href and accessible name, keyboard focus, and desktop/mobile
  overflow without adding a workflow or changing Pages permissions. The
  accompanying refined Bolt records why README restructuring, a duplicate fast
  gate, and Action pin churn were deferred. Validation passes **3 focused
  contracts**, **92 aggregate contracts**, the production TypeScript/Vite
  build, the provenance browser matrix, and all four existing Field Notes
  browser suites. Independent code and workflow/security reviews returned
  **APPROVE** after a malformed repository-slug edge case was fixed and covered.
  No batch, grading, Azure, Hugging Face, deployment, or paid action ran during
  local validation. Shipped through PR #142 as
  `a9cc93bb07297332d4f6cfe1a4dea54e07d28fef`; automatic PR validation and the
  post-merge `main` validation/Pages deployment passed. The live dashboard was
  then verified to display `v0.2.0 · a9cc93b`, link to the exact full merge
  commit, expose the full source identity accessibly, and remain overflow-free
  at a 390px viewport.
- **Opt-in typed Azure AI Step 2 wiring** - activate the shipped typed route
  foundation only when `AZURE_AI_ROUTE_PROFILE` is nonempty, while preserving
  the profile-absent legacy constructors, progress shape, result shape, and
  workflow behavior. Step 2 preflights every Azure main, Self-QA, Code
  Interpreter, and recognized audio/video preprocessor workload before
  credential or client construction; binds canonical deployments to exact
  endpoint-free route records; verifies each instantiated client's runtime
  route and fingerprint before use; and includes those records in progress and
  final-result identity. One shared factory, distinct managed clients, and a
  role-aware owner enforce executor-first, reverse-client, factory-last cleanup
  across normal return, exceptions, and `SystemExit`. Typed provider failures,
  cleanup failures, and malformed or duplicate-member QA payloads are reduced
  to class-only diagnostics without erasing native or local runner details.
  Native-only conditions remain entirely legacy even when a profile is
  requested; native main plus Azure preprocessing uses only the typed
  preprocessor path. External typed resume checkpoints, positive wall-timeout
  relay, hardened/agentic typed execution, and workflow activation remain
  deliberately unsupported. Model-free verification passes **216 focused
  tests** and the complete credential-free backend with **2,211 passed, 9
  host-dependent skipped, and 44 integration tests deselected in 134.81
  seconds**. Ruff, `py_compile`, diff checks, and an independent release-gate
  review with **0 mandatory findings** pass. No credential, token, network,
  Azure/model API, grading, Hugging Face, workflow, deployment, or paid action
  occurred. A clean detached checkout of reviewed head
  `6ee41d2a89ff796dc06c238892fe5f78ec1f29a1` passes **216 focused tests in
  2.16 seconds** and the complete backend with **2,214 passed, 6
  host-dependent skipped, and 44 integration tests deselected in 137.30
  seconds**. Shipped through PR #138 as
  `4654b4316ecef30f19da55dd513b35d625f7d30d`. GitHub attached no check run,
  check suite, commit status, or PR check rollup to the reviewed or merge SHA;
  no workflow was manually dispatched to compensate.
- **Typed Azure AI runtime adapters** - add an opt-in managed client wrapper,
  caller-owned Code Interpreter client injection, and deterministic executor
  lifecycle without wiring Step 2 or workflows. Closed adapters reject all
  public client, route, fingerprint, context, and delegated access before an
  API call. Owned factories close after leases, shared factories and injected
  credentials remain caller-owned, and create/cleanup failures preserve the
  foundation exception chain. Code Interpreter keeps same-descriptor reference
  upload and provider-file cleanup while adding one initialization cleanup
  boundary for client, credential, prompt, and token-limit failures. Executors
  close only close-capable runners and never directly close raw LLM clients.
  The foundation documentation contract now binds its immutable BOLT and
  changelog entry without freezing the rolling latest-task record.
  A detached clean checkout passes **279 focused tests with 6 integration cases
  deselected**. Repeated clean-checkout backend runs completed with **zero
  failures**, **2,105-2,108 passed**, **6-9 host-dependent skips**, and **44
  integration tests deselected**. Ruff, `py_compile`, and
  `git diff --check` pass across the seven changed Python files and three
  completion records. These adapters remain `NOT WIRED`, and no credential,
  token, network, Azure/model API, Hugging Face, workflow, or paid action
  occurred. Shipped through PR #136
  (`d8e5796d0f4e4e3b0261fc4419eb5801feb88d07`) from reviewed head
  `9356e02d09b77f4a5cb010849548899b516360ec`. GitHub created no Actions run,
  check suite, or check rollup for either SHA because the ten changed paths do
  not match an active workflow trigger. No workflow was manually dispatched,
  and no credential, token, Azure/model API, Hugging Face, deployment, or paid
  action was used to compensate.
- **Typed Azure AI endpoint foundation** - add exact HTTPS endpoint contracts
  for direct Azure OpenAI v1, Foundry project, and explicitly authorized legacy
  rollback routes. Parsing rejects non-ASCII/control normalization, empty ports,
  malformed percent sequences, host lookalikes, and trailing dots before the
  exact Microsoft suffix/path allowlist. Strict identity is profile-specific,
  including direct verification of `AZURE_AI_EXPECTED_LEGACY_ACCOUNT`. The
  current `CodeInterpreterRunner is Azure-only`; a missing deployment follows
  the runtime's `gpt-4` default, while malformed model objects, explicit null
  deployments, and native-provider Code Interpreter fail. Audio/video
  preprocessors use only the runtime `deployment` field and defaults; other
  types are excluded. `DefaultAzureCredential`-based settings reject known
  static Azure key, token, secret, certificate, username, and password
  variables while allowing `AZURE_FEDERATED_TOKEN_FILE` and native
  `OPENAI_API_KEY`. Owned factory and token-check paths recheck the real process
  environment before constructing a credential even with explicit route
  settings; injected credentials remain caller-managed. Versioned fingerprints
  bind effective token scope and
  transport settings while emitted records remain endpoint-free, redacted
  provenance; the digest is not a confidentiality boundary and not a secret.
  Synchronous non-thread-safe factory/lease ownership and hardened one-write
  `GITHUB_OUTPUT` behavior are covered directly. Exact pins are
  `openai==2.46.0`, `azure-core==1.41.0`, `azure-identity==1.25.3`, and
  `azure-ai-projects==2.3.0`. An offline real-SDK construction smoke verified
  the canonical project OpenAI base URL and the exact capability contract:
  `responses.create`, `files.create`, `files.delete`, fallback `files.content`,
  `containers.create`, `containers.files.list`, and
  `containers.files.content.retrieve`. The current runner uses auto-container
  configuration rather than calling `containers.create` directly; that method
  is retained as a project-client compatibility gate. Credential and HTTP send
  counters remained zero and the credential stayed caller-owned. Raw and
  serialized condition discovery produce the same main, QA, and preprocessor
  workloads. A detached clean checkout passes the focused suite **224/224 in
  20.79 seconds**, the exact real-SDK smoke **1/1 in 1.47 seconds**, and the
  complete credential-free backend non-integration suite with **2,074 passed,
  9 skipped, and 44 integration tests deselected in 126.02 seconds**. Ruff,
  `py_compile`,
  `pip check`, exact-pin, `git diff --check`, conflict-marker, and exact
  eight-path scope checks pass. Runtime and workflow integration is `NOT WIRED`;
  no token, network, Azure/model API, Hugging Face, workflow, or paid action
  occurred. Shipped through PR #134
  (`fb3b7fe02ad54a3b095ffbea532a7b1703ba065b`) from reviewed head
  `127c948a9832d156d17b151ffe9cb6f063818f92`. GitHub created no Actions run,
  check suite, or check rollup for either SHA because the eight changed paths
  do not match an active workflow trigger. No workflow was manually dispatched,
  and no credential, token, Azure/model API, Hugging Face, deployment, or paid
  action was used to compensate.

### Changed
- **Microsoft Foundry workflow activation and OIDC enforcement** — extend the
  shipped typed endpoint foundation, runtime adapters, and Step 2 wiring into
  the active batch, report, publication, and grading paths. Inference,
  narrative, and grading use the Foundry direct
  `/openai/v1/` route; only Code Interpreter may use the project endpoint, and
  dated Azure OpenAI remains an explicitly authorized rollback profile. Batch
  and grading workflows reject static Azure keys, enumerate every configured
  workload before remote writes, compare OIDC client/tenant/subscription
  secrets with independent repository variables, and recheck the active Azure
  account plus `ai.azure.com` token claims after login. Route token preflight
  verifies the selected audience, including Cognitive Services only for the
  explicit legacy rollback. English/Korean onboarding now documents the typed
  routes, expected identities, and local/CI authentication contract.
- **GitHub repository About metadata** — replace the contradictory
  `220 tasks across 11 industries` description with a concise public value
  proposition for the tracked Gold Subset: 220 real professional tasks across
  9 sectors and 44 occupations, reproducible experiments, artifact validation,
  grading, and a live evidence dashboard. Keep the deployed dashboard homepage
  unchanged and reduce 20 mixed vendor/framework topics to 12 high-signal
  discovery topics centered on LLM evaluation, real-world professional tasks,
  artifact validation, benchmark automation, and the operating stack. The
  public GitHub page and repository API show the exact new description,
  homepage, and topic set; the metadata-only update created no commit or
  workflow run.
- **First-run execution contract** — expose fork-safe links to the live
  dashboard, tracked three-task config, Batch workflow, and result/artifact
  guide in both root READMEs. Rebuild the English/Korean Batch Runner quick
  starts around the executable wrappers, five OIDC/HF secrets, Azure OpenAI
  resource-endpoint contract, destructive HF boundaries, all eight workflow
  inputs/defaults, Step 6/7 destinations, and external-grading separation.
  Replace remote onboarding diagrams with repository-owned responsive SVGs and
  add an eight-test contract suite that parses the docs, workflow,
  and owning bootstrap/auth/report/upload code. Shipped through PR #127
  (`30906084dbee384f1c324a8b794cba5aef28170b`): automatic free PR run
  [29889565405](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29889565405)
  passed validation with deployment skipped, and automatic `main` run
  [29889682507](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29889682507)
  passed validation and GitHub Pages deployment. Neither run used manual
  dispatch, grading, Step 8, an Azure/model API, Hugging Face upload, or paid
  execution.

### Fixed
- **Foundry provenance, publication, and grading finality** — bind prepared,
  result, ordered-task, deployment-route, and runtime identities through Step 2
  checkpoints/final output, inference provenance sidecars, HF CAS publication,
  grading cache/resume, and every partial/diagnostic save. Impossible
  profile/endpoint/workload combinations fail closed; grading downloads require
  the sidecar unless an explicit non-publishable legacy-analysis override is
  used. Provider errors are projected to stable endpoint-free public values
  before relay or final-result fingerprinting. Subset and legacy grades use
  full ordered-task-hash diagnostic paths and cannot collide with root final
  grades; nested analysis artifacts follow the exact emitted path. Cost sweeps
  translate archived endpoint fields to the typed contract, hash
  repository-contained generated configs, and consume only Step 8's exact
  `GITHUB_OUTPUT` path. Sidecar bytes participate in the core publication plan,
  receipt, and finality checks while stale full Step 2 JSON is removed from the
  public managed tree. Step 6 removes its unused experiment-model fallback:
  after up to two primary `gpt-5.4-pro` calls, any setup, call, parse, or route
  failure emits a model-free report and prevents the second call after an
  invalid, partial, empty, or whitespace-only first response. Typed relay
  restore recomputes the endpoint-free route plan before accepting a checkpoint.
  A shared versioned per-status validator
  rejects malformed success/error/QA/pending rows on local save/restore and
  relay status/upload, while Code Interpreter is rejected outside the
  project-only profile at runtime mode, route selection, and restored-route
  boundaries before client construction. Inference provenance schema v2 binds
  execution mode and rejects route-less/non-project Code Interpreter sidecars
  across formatting, download, bootstrap, and HF publication. Azure
  hardened execution constructs its typed client only after the signed
  authorization and budget reservation; profile-absent runs fail before
  executor creation, and capability-rejected deferred candidates close before
  ownership transfer. The common hardened baseline closes each deferred client
  at task finalization and any residual client at idempotent runner shutdown;
  cleanup failures expose only `provider_cleanup_failed:<Type>`. Main, vision,
  audio, v1 single/batch grader, local
  audio-preparation/tool-dispatch, initialization, and cleanup exceptions use
  class-only public identities; owned clients are released even when close
  fails, without retaining the raw cause or context. Grading cache/resume and
  all output states require the exact non-null primary grader fingerprint, not
  any tier/perception route match, while cleanup failures preserve durable exit
  codes 0, 6, and 7. One shared schema/cross-field validator protects Step 8 and
  both workflow commit gates before and after rebase. OIDC session checks bind
  token `aud`, `nbf`, and `exp` in addition to tenant and client claims.
  Relay cleanup finality revalidates the exact child against the full
  publication plan, including optional README bytes. Frontend skill discovery
  ignores generated cache directories. Model-free route planning no longer
  imports Azure/OpenAI SDKs until credential or client construction, so the
  Node-only aggregate gate runs without paid-runtime dependencies.
  Credential-free validation passes 2,328
  backend tests with 6 skips and 44 integration
  deselections, 89 frontend data contracts, nine onboarding contracts, the
  production build, four browser suites, Ruff, Python compilation, actionlint,
  shell syntax, and diff checks. No workflow dispatch, Azure/model call,
  grading run, Hugging Face write, or paid execution was used for this
  validation. Shipped through PR #140 as
  `f730068a64b2ebe04c42eb68cea696fd69e1e978`; updated PR run
  [30146185099](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/30146185099)
  passed validation with deployment skipped, and automatic `main` run
  [30146254229](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/30146254229)
  passed validation and GitHub Pages deployment. The first PR run
  [30145929181](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/30145929181)
  found the eager SDK import and was superseded by the validated lazy-import
  fix. None of these automatic runs performed Azure/model calls, grading, or
  Hugging Face writes.
- **Batch relay provenance and recovery integrity** — require exact `main` and
  equal workflow/event SHAs before checkout, bound canonical timeout/relay
  inputs, pin every continuation to the initial `source_sha`, and keep relay
  dispatch on `main`. Checkpoints now restore, upload, and clean up against the
  validated full `data.source` rather than a reconstructed YAML-stem repo.
  Continuations fail before Azure login/model construction when progress,
  lineage, prepared fingerprint, or referenced deliverables are missing or
  invalid. The 290-to-350 gap is now reported as nominal step-timeout headroom,
  not guaranteed relay handoff time; overlapping runs sharing one HF target are
  explicitly unsupported because GitHub concurrency is not a durable queue.
  Checkpoint payloads live under content-addressed generations; `current.json`
  advances only after one immutable HF revision has the exact file tree and
  matching SHA-256/size manifest. Restore and cleanup require the same source
  SHA and lineage; cleanup deletes the whole current-tree lineage in one
  exact-HEAD CAS commit. Step 0 propagates lookup/auth/network errors, never
  auto-deletes an existing partial repo, and validates every parquet-declared
  reference as a unique regular non-symlink file. A non-mutating write-access
  preflight rejects read-only targets before task preparation, Azure login, or
  model spend. Path cleanup does not erase prior HF revisions and failed
  operations may leave forensic orphan generations. The required SDK is pinned
  to the verified `1.24.0` contract. Step 0 authenticates first and creates
  targets with `exist_ok=False`, treating only HTTP 409 as reuse and never
  deleting partial or legacy targets. New targets derive from the pinned public
  source revision; reused targets are downloaded at an exact HEAD into fresh
  staging and accepted only when the schema-v4 manifest, canonical target
  columns and source projection, ordered task identity, complete physical
  reference tree, and every declared reference SHA-256/size match. Relay
  uploads download and verify the immutable payload revision before advancing
  `current.json`, require a complete ordered result set, and confirm successful
  cleanup in the same invocation when the CAS response is lost. Relay progress
  now accepts only canonical task IDs and known terminal/pending statuses, and
  every declared deliverable path must remain under its owning task directory.
- **Canonical batch input and publication integrity** — upgrade the source
  manifest to schema v4, binding all 220 ordered task IDs to prompt, taxonomy,
  rubric, ordered reference path/URL/URI semantics plus 261 declared reference
  SHA-256/size records from pinned `openai/gdpval@11e7900...`. Step 1 requires
  and rechecks that projection before writing prepared tasks; Step 2 rechecks
  prepared identity before provider-client construction. References move into
  read-only private per-task staging before preview, preprocessing, codegen, or
  execution, with same-file-descriptor hashing/copying, basename-collision and
  partial-copy rejection, and fatal provider upload/local/Docker copy errors.
  Code Interpreter input IDs are deleted best-effort after normal or failed
  tasks, and provider uploads preserve each verified reference basename. The
  common sandbox keeps private local staging while the hardened remote backend
  preserves opaque reference IDs instead of treating them as host paths. Each
  task output tree is removed with symlink-aware semantics before the first run
  and every QA retry so resumed execution cannot inherit stale deliverables.
  Condition A retains the publication/relay upload root while condition B uses
  an isolated tree, preventing a second condition from deleting or replacing
  the bytes selected for publication. Step 2 binds each declared deliverable to
  same-descriptor SHA-256/size records and a canonical result fingerprint.
  Step 0 creates and clears every submitter column, rejects stale scalar,
  list, URL/URI, and physical deliverable state on reused targets, and never
  auto-deletes partial repositories. Step 4 rebuilds production selected rows
  from current results only and revalidates the full source projection and
  reference bytes after model execution. Step 7 rechecks each published source
  row, the one canonical parquet shard, row-to-task deliverable paths, canonical
  URLs/URIs, exact local file tree and bytes, and a required non-dry
  `self_report.json`. A run-specific publication generation is created by Step
  1, preserved across relay legs, and checked before provider construction;
  Step 3 and publication share one production-shaped projection of prepared
  metadata and raw Step 2 QA/results. Parquet submitter fields and self-report
  task status, QA/error projection, summary, content, and files must exactly
  match that result. Every selected reference byte is rechecked before provider
  construction. Publication holds verified source bytes in private anonymous
  streams so the SDK cannot reopen changed local paths. Step 5 records
  file-required failures without creating dummy files or mutating the parquet.
  Relay marker writes reconcile ambiguous responses without retry; restore
  records the exact generation and cleanup refuses a newer generation. Relay
  dispatch requires both process exit code 42 and pending tasks. Step 0 records
  the validated target HEAD; one `create_commit` requires that HEAD as
  `parent_commit`, then verifies direct ancestry, plan marker, complete remote
  tree/hash, self-report identity, and final HEAD. A private receipt binds that
  plan, and post-cleanup finality accepts only the exact cleanup child with an
  unchanged managed tree. Non-relay finality reuses the already verified
  publication revision instead of downloading managed files twice. Core paths
  shipped through PR #129
  (`2d4026056b6e27f5111a94d1089573f6b4938a58`): automatic pull-request run
  [29919172383](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29919172383)
  passed validation with deployment skipped, and automatic `main` run
  [29919336511](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29919336511)
  passed validation and GitHub Pages deployment. Relay cleanup commits now
  store the short generation label in the Hub commit title and the full
  64-character generation marker in its description; response-loss
  reconciliation and publication finality verify both SDK fields and the direct
  parent before accepting cleanup. Final credential-free evidence is **1,853
  passed, 6 skipped, and 44 integration tests deselected** across the backend;
  the relay checkpoint matrix passes **83/83**, HF publication/finality passes
  **86/86**, and their combined focused matrix passes **169/169**. The cleanup
  identity follow-up shipped through PR #131
  (`576e6f4f4a72998f0311d74006373bcea40a3cf6`). Its code and test paths are
  outside the Pages workflow's pull-request and push filters, so GitHub created
  no automatic run for the PR head or merge SHA. No manual workflow dispatch,
  Hugging Face write, Azure/model call, grading run, or paid execution was used
  to compensate for the path-filtered check.
- **Hermetic deliverable-selector contract tests** — replace import-time pandas
  and ignored local-parquet loading with a checked-in 28-task synthetic signal
  corpus. The 6,889-byte canonical fixture is self-hashed and binds exact public
  `openai/gdpval@11e7900...` task identities to the source parquet SHA-256,
  220-row count, and per-task prompt/ordered-rubric hashes without storing full
  prompts, rubrics, references, deliverables, grades, or model output. A
  stdlib-only verifier validates the fixture offline; optional delayed pandas
  verification checks the known local public snapshot. Clean checkouts now
  collect all selector tests without pandas, PyArrow, parquet, or network. The
  selector/verifier suite passes 15/15, root scripts pass 44/44, and adjacent
  grading tests pass 90 with 2 environment skips. Production selector and
  grader code are unchanged; no grading, Step 8, model/API, HF upload, manual
  workflow, network fetch, or paid execution occurred. Shipped through PR #124
  (`a82776113d617b3fa4bd12c480f36b51cd7b16a3`); automatic free
  `Aggregate Tests & Deploy` run
  [29862415519](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29862415519)
  completed validation and Pages deployment successfully.

### Changed
- **Execution-first repository onboarding and publish gates** — reorganize both
  root READMEs around live evidence, a credential-free local preview, and an
  honest three-task cloud path. English/Korean beginner guides now explain
  OpenID Connect, disposable public Hugging Face targets, destructive bootstrap
  and upload boundaries, Self-QA vs external grading, report fallback cost,
  artifacts, troubleshooting, and cleanup. Pages automation separates a
  read-only PR validation job from main-only deployment; automated result
  PRs are proven before HF upload, rechecked after upload, and dispatched for
  exact-head-SHA validation without Pages/OIDC privileges. Shipped through PR
  #120 (`9892a4c7566a0c5ba24f876459d5932ee7284357`).
- **Success Field Note retrospective voice** — revise
  `what-does-success-mean` without changing its evidence contract, metrics,
  source links, or fail-closed behavior. The six chapters now follow a
  plain-language 상황→태스크→액션→결과→가설 검증→근본 원인 sequence: reduce
  220 outcomes to two comparable tasks, reduce validation to three answerable
  questions, name the workbook's required analysis, summarize three discoveries,
  test the original handoff-ready hypothesis, and trace the root cause to four
  questions compressed into one status. The copy distinguishes the `200/220`
  report success-rule pass rate from process completion, leaves briefing
  fidelity and external quality unverified, and retains all 30 citations and ten
  evidence targets. All 77 aggregate contracts, the production build, and the
  runtime, integrity, perception, and success browser suites pass; the four
  browser suites complete in 48.201 seconds with no mobile overflow. Shipped
  through PR #118 (`f3648f72`) and successful Pages run
  [29757449226](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29757449226);
  public mobile and desktop checks verified all six revised chapters, the three
  validation questions and discoveries, the rejected hypothesis, report-success
  semantics, unverified briefing fidelity, 30 citations, ten evidence targets,
  and zero overflow or SVG label overlap.

### Fixed
- **Grading workflow trust-boundary hardening** — archive the completed May 24
  cost sweep outside `.github/workflows` so it cannot be dispatched again,
  while preserving its exact workflow source beside the historical results and
  marking the former live status/trigger guide as archived.
  The active grade workflow remains one job with its existing three pushes,
  chunk-resume contract, and two follow-up dispatch paths, but now accepts only
  an exact `main` workflow/event SHA, verifies the checked-out branch, upstream,
  remote SHA, publication credential, experiment, and grading config before
  Azure/HF access, and passes all eight dispatch inputs to shell through
  validated environment variables. External actions are pinned to reviewed
  40-character commits and the unused `pull-requests: write` permission is
  removed. This is a fail-closed operational guard, not a protected privilege
  boundary; repository rulesets and a protected grading environment remain a
  separate follow-up. No workflow, model/API call, grading run, HF write, or
  paid execution was dispatched by this change.
- **Pages main deployment gate** — remove the invalid assumption that the
  repository's unprotected `main` branch reports `github.ref_protected=true`.
  Push/manual deployment remains restricted to `refs/heads/main`, while
  validation-only result-PR dispatches still require their exact branch,
  `github.sha`, `github.workflow_sha`, and expected SHA. This repairs failed
  post-merge run `29836869345` without granting Pages/OIDC permissions to PR
  validation jobs. Shipped through PR #121
  (`138e89a8e3a56e86a836656e2572669786cbc0cf`); PR validation run
  [29843523709](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29843523709)
  passed without deployment, and automatic main run
  [29843751719](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29843751719)
  completed validation, artifact upload, and Pages deployment successfully.
- **Inference/report identity and fallback integrity** — hash the complete
  canonical Step 1 prepared payload, persist that fingerprint through relay
  checkpoints and final inference, and reject stale or mixed Step 1/2 inputs in
  Step 3. Experiment IDs and HF targets are path/branch-safe before Step 0.
  Step 6 is now strictly pre-grading, derives HF links from the run's source,
  isolates explicit external result files from current workspace manifests and
  recovery stats, distinguishes dry-run publication, and falls back to a
  model-free report when narrative generation fails. Result PR output and its
  one-file contract are mandatory before destructive HF publication, preventing
  silent no-PR success or stale `self_report.json` upload.
  Relay legs now carry a stable lineage ID across GitHub run IDs, while
  condition A/B use isolated progress and result files. Canonical HF repository
  validation rejects unsupported length and punctuation before credentialed
  bootstrap.
- **Archived v1 cost-sweep template resolution** — point the historical
  `grading_cost_sweep.py` renderer at the tracked
  `grading_configs/_archive_v1/_sweep_template.yaml` after task 207 moved the
  v1 reproduction assets out of the active config directory. A regression test
  freezes the archive path, schema v1 identity, and absence of a duplicate
  top-level template. The two known root-test failures are resolved: the full
  cost-sweep module passes 13/13 and `scripts/__tests__` passes 39/39. Active v2
  grading, workflows, models, prices, and budgets are unchanged; no sweep,
  Step 8, model/API call, grading run, HF upload, manual workflow, or paid
  execution occurred. Shipped through PR #114
  (`16305fd7c0661fdcb07bd298bfd4a9ccf4ffb381`); only the automatic free
  `Aggregate Tests & Deploy` run `29731574595` executed, and it succeeded.

### Added
- **Localized responsive README diagrams** — add twelve repository-owned SVGs:
  English and Korean desktop/mobile versions of the first-run decision, system
  map, and operational controls. Static SVG replaces remote Mermaid rendering;
  each asset has intrinsic dimensions, accessible title/description, at least
  6.04:1 primary text contrast, and a 960px responsive breakpoint. Browser
  geometry checks cover nearest-card spacing and overflow across mobile,
  tablet, and desktop widths.
- **Evidence-backed success Field Note** — rebuild
  `what-does-success-mean` as a retrospective that separates the team's initial
  handoff-ready expectation from exp026's observed execution, artifact integrity,
  requirement fidelity, and still-unknown external quality. A generated
  `success-note.json` contract joins the exact exp026 report summary and task QA
  map to a pinned Hugging Face revision, byte hashes, two task instructions,
  manifests, and directly inspected XLSX/PPTX/PDF structure. The article now
  derives its metrics, four-layer responsive SVG, Self-QA chart, six reflective
  chapters, and 30 inline citations from strict evidence; missing, duplicate,
  malformed, newly graded, or drifted data hides the complete evidence-bearing
  article behind an alert. Workbook coverage is measured at 35/500 while the
  selected file still opens; the briefing's PPTX/PDF parity is measured at
  32/32, but citation depth, financial accuracy, and external quality remain
  explicitly unverified. A shared schema-aware grade identity helper prevents
  dummy, legacy, filename, or source-pointer grades from being misattributed.
  CI streams six pinned HF files through timeout and byte caps before SHA-256
  validation and runs all four Field Note browser suites before Pages upload.
  All 77 aggregate contracts, production build, and four browser suites pass in
  47.996 seconds; no model, grading, batch, HF write, manual workflow, or paid
  execution was dispatched. Shipped through PR #116 (`85e21b30`) and successful
  Pages run
  [29746868595](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29746868595);
  public checks verified the generated 200/220 execution snapshot, 35/500
  workbook coverage, 32/32 briefing parity, external-quality `unknown`, the
  four-layer responsive hero, 30 inline citations, ten pinned evidence targets,
  contract/artifact back-references, reflective typography, and zero horizontal
  overflow on mobile and desktop.
- **Evidence-backed perception Field Note** — rebuild
  `from-audio-to-multimodal-sandbox` around exact exp011/exp012/exp026 report
  snapshots, checked-in package/audio/video/sandbox configuration, and three
  pinned architecture commits. A generated `perception-note.json` contract and
  strict selector now derive the article metrics, three-stage SVG, dual-axis
  chart, six reflective chapters, and inline citations from validated evidence;
  missing, duplicate, malformed, or drifted report/source data hides the full
  numeric article behind an alert. The note preserves the exp012 17-task/YAML-
  date/report-date metadata conflict, treats configured paths separately from
  unknown analyzer invocation counts, and refuses causal attribution because
  scope, model, reasoning, runner, Skills, and execution identities differ.
  Twelve detailed evidence entries link report rows, immutable config/code line
  ranges, and pinned history. Pages now regenerates on every direct source,
  package, workflow, or Skills-registry change and runs runtime, integrity, and
  perception Chromium suites before upload. All 65 aggregate contracts, the
  production build, and all three browser suites pass; the browser gate takes
  41.71 seconds locally and dispatches no model, grading, batch, HF upload, or
  paid workflow. Shipped through PR #112 (`0f9761d7`) and successful Pages run
  [29678863958](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29678863958);
  public checks verified the generated non-causal contract, report-derived
  `25/25 → 24/25 → 23/25` Information sequence, responsive SVG/chart, 34 inline
  citations, 12 detailed evidence targets, pinned source ranges, back-reference
  navigation, reflective typography, and zero horizontal overflow on mobile and
  desktop.
- **Inline citations for the integrity Field Note** — connect the thesis and
  each evidence-bearing paragraph in `honest-pipeline-lower-score` to ten
  numbered source notes. Citations jump to detailed report, config, pinned
  pre/post-fix code, PR #38, and causal-boundary entries; every evidence entry
  shows its immutable commit and line range where available, and links back to
  each citing paragraph. A shared validator rejects duplicate, unknown, unused,
  malformed, or misaligned citation/evidence contracts before rendering. The
  citation trail remains inside the existing 2.05 reading rhythm, uses 9px
  superscripts and 24px return targets on mobile, and introduces no horizontal
  overflow. Existing Field Notes remain compatible and continue to show numbered
  evidence rows, with each row title acting as its explicit source link. All 56
  aggregate contracts, production build, and runtime/integrity Chromium suites
  pass; no model, batch, grading, upload, or paid workflow was dispatched.
  Shipped through PR #109 (`4647a6ce`) and successful Pages run
  [29673420824](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29673420824);
  public mobile and desktop checks verified all forward citations, detailed
  pinned sources, back-references, sticky-header offsets, and overflow bounds.
- **Evidence-backed integrity Field Note** — rebuild
  `honest-pipeline-lower-score` from exact exp013/exp025 report snapshots,
  checked-in experiment config projections, and pinned PR #38 code history.
  Metrics, SVG, chart, and numeric prose now derive from validated sources;
  malformed, duplicated, stale, or contract-drifted evidence hides the entire
  article sequence behind an alert. The note presents the observed `-13.6%p`
  completion gap separately from the proven `_AVAILABLE_FILES` persistence and
  `qa_failed` classification changes, explicitly refusing causal attribution
  because execution Git, input revision, Azure model revision, and runner
  identity are missing. Five reflective chapters use shorter headings, wider
  spacing, 2.05 leading, and quieter callouts to create a deliberate
  관측→불변식→판정→비교→결정 rhythm. The serialized Pages job now regenerates on
  integrity-source changes and runs both runtime and integrity Chromium suites
  before deploy. No model, batch, grading, HF upload, or paid workflow is
  dispatched. Shipped through PR #105 (`8a64f1bf`) and successful Pages run
  [29649567174](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29649567174);
  the deployed JSON, non-causal hero, report-derived chart, pinned source links,
  and reflective typography were verified on desktop and mobile.

### Changed
- **Local merged-branch consolidation** — a post-merge local audit removed
  eight pre-existing linked worktree paths and 23 pre-existing sandbox,
  agentic, prompt, and note branch refs backed by merged PRs. The dirty
  `hyeonsangjeon-sandbox-preflight-final-status`, closed-unmerged
  `docs/prompt-note-deploy-result`, and no-PR
  `hyeonsangjeon-agentic-job-metrics-run-correction` refs were preserved. No
  remote ref, stash, or primary-worktree file was removed; the attempted local
  `main` ff-only update stopped without changing files when concurrent local
  work appeared.
- **Evidence-backed runtime Field Note** — rebuild the `360-minute-experiment`
  note around three explicit sources: exp008/010/025/026 report snapshots, the
  current condition-a workflow policy, and a pinned exp025 incident record.
  The note now separates the incident-time 330-minute hard stop from the
  post-fix 290-minute watchdog, 350-minute step ceiling, and 360-minute job
  ceiling; derives metrics, timeline SVG, resume chart, and numeric prose from
  validated data; and fails closed on missing, malformed, stale, or mismatched
  evidence. Five shorter chapter headings, chapter labels, wider section
  spacing, 2.05 body leading, and quieter serif callouts give the retrospective
  a deliberate 사건→편향→대응→결과→결정 reading rhythm on desktop and mobile.
  The Pages workflow now regenerates this evidence when either runtime source
  changes and gates deployment on all aggregate contracts plus pinned-history
  and Chromium desktop/mobile checks. No model, batch, grading, HF upload, or
  paid workflow is dispatched by this change. Shipped through PR #102
  (`fe222493`) and successful Pages run
  [29628757147](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29628757147);
  the deployed JSON, two-lane timeline, report-derived chart, source links, and
  reflective typography were verified on desktop and mobile.
- **Bounded Agentic Sandbox runtime and preregistered experiment** — implement
  separate `agentic_sandbox` and common hardened-baseline paths with ordered
  Responses tools, deterministic finalization, exact task/request/input and
  selection identities, crash-safe SQLite budgets, Ed25519 single-use live
  approval, fixed-denominator comparison endpoints, optional dashboard fields,
  and legacy omission. Split credential and compute planes use mTLS plus
  deadline-bound HMAC envelopes, bounded streaming JSON, exact sequence retry,
  no-network/non-root Docker, quota-backed work volumes, an in-process generated-
  code seccomp launcher, isolated rendering/verifier containers, component/SBOM
  identity, and auditable terminal cleanup. Manual image and dedicated-runner
  workflows require a protected exact `main` SHA; unfinished agentic publication
  remains opt-in and fails closed until immutable dependency locks exist. Local
  model-free validation passed 1,485 Python tests, 54 Node aggregate tests,
  TypeScript/Vite build, two Chromium suites, image audit/SBOM equality, and WAV,
  XLSX, DOCX, and PPTX Docker E2E. No model/API call, task selection, workflow
  dispatch, image publication, HF upload, grading, or paid run occurred. Exact
  5/20 cohorts, production locks/image identities, dedicated-host preflight, and
  signed owner approval remain required at the paid gate; package installation,
  model-visible shell, and Anthropic support remain deferred.
- **Model-free Track 2 preflight workflow** — add a main-only, read-only manual
  workflow for private pinned cohorts. It validates compact JSON identities
  before checkout, checks out the exact event SHA with credentials disabled,
  pins Action commits and Python 3.11.9, installs a 27-package binary-only
  SHA-256 lock, verifies source/planner/config/grader identities before exposing
  `HF_TOKEN`, and uploads the exact plan plus environment. No Azure login,
  model client, Step 8 grading, repository write, or child dispatch is present.
- **Task-scoped inference download** — allow the HF downloader to require an
  exact ordered source prefix and fetch only those task directories. This keeps
  Stage B preflight limited to the pinned first ten tasks instead of downloading
  the full private deliverable tree.
- **Exact model-free Track 2 cohort planner** — add a direct-entry CLI that
  executes the production selector, routing, and shared visual-preflight
  validator before counting judge-bound routes and render-perception calls. It
  requires a clean checkout and exact expected planner, repository, inference,
  config, grader, rubric, and ordered-task identities, and emits item-level
  plans without creating an Azure client or making model calls.
- **Track 2 isolated cohort configs** — add Stage A three-task and Stage B
  ten-task validation configs whose parsed runtime semantics exactly match
  `default_v2_mini`; distinct config names, hashes, grader-source identities,
  and output paths prevent either stage from overwriting the accepted one-task
  canary or each other.
- **Track 2 cohort expansion preregistration** — add a dated, immutable
  two-stage plan for expanding the accepted exp003 one-task canary to three and
  then ten tasks without overwriting the canary artifact. The plan fixes task
  IDs, inference/rubric identity, cost and wall-clock gates, provenance checks,
  stop conditions, and a retrospective log. Preflight found and corrected an
  XLSX `Sound Technician` false audio route, then rejected Stage A attempt 1
  after audit exposed unsafe automatic precheck verdicts. Corrected Stage A run
  `29572067428` then passed all gates from merged `main`: 3/3 tasks, 153
  judge-bound items, zero errors, complete usage, exact 4/4 render-perception,
  confined provenance, USD 1.08 effective cost, and 24.9 artifact minutes.
  Stage B retry `29600523299` later passed all runtime gates: 10/10 tasks,
  435 items, zero errors, complete usage, exact 26/26 render-perception,
  confined provenance, USD 2.15 raw / USD 1.73 effective, and 73.4 artifact
  minutes. Full-220 now requires a separate chunk/resume and audio-aware plan.

### Fixed
- **Shared grading finalization retry budget regression coverage** — add a
  model-free test proving that an empty final response followed by malformed
  JSON consumes the same single bounded retry budget, stops after two API
  calls, preserves accumulated token/cache accounting, and leaves a later
  scripted response unused. A local grading/Track 2 branch audit found no
  missing runtime implementation: prior fixes were already merged or safely
  superseded. The cleanup removed 26 stale local refs and 19 clean worktrees
  while preserving the five-file dirty `fix/grading-final-json-recovery`
  worktree for separate review. No remote branch, model/API call, grading run,
  workflow dispatch, HF upload, or paid execution was changed or triggered.
- **Long grade output atomic persistence** — bound `_save_json` temporary
  basenames with a 16-hex SHA-256 identity instead of copying the full final
  filename. Stage B run `29591036089` completed all ten paid tasks but the
  legacy 242-byte basename plus temp decorations reached 256 bytes and failed
  Linux `NAME_MAX=255` before any JSON, commit, analysis, resume, or artifact.
  The final output name and same-directory atomic replace remain unchanged;
  exact 242-byte round-trip, replace-failure cleanup, Step 8, and broad tests
  pass. Post-fix model-free run `29599249906` reproduced the exact 435-item,
  436-judgment, 26/26 plan with zero errors under the new grader identity. A
  second owner-approved paid attempt persisted successfully. The rejected
  attempt remains conservatively booked at USD 3.81; cumulative raw Stage B
  cost is USD 5.96, below the USD 10 cap.
- **Mixed-format visual bundle preflight** — filter harness rendering to stable
  supported paths while retaining all selected paths for main-judge evidence.
  Stage B preflight run `29583415563` exposed nine organization-chart criteria
  whose DOCX/PDF/XLSX bundle was rejected solely because DOCX is not renderable;
  the corrected boundary renders PDF/XLSX, records the filtered DOCX, and keeps
  unsupported-only visual targets fail closed. Runtime and planner now validate
  split children and item/task caps in the same pre-render order. Corrected
  model-free run `29589077065` passed all first-10 gates with 435 items, 436
  judgments, 26/26 render-perception calls, zero prechecks/audio/errors, and one
  audited filtered DOCX path. The accepted paid artifact matched every planned
  route, selected path, and perception call.
- **Exact planner perception accounting** — bump the planner contract to v2,
  count audio separately from harness-owned visual calls, enforce visual/audio
  task caps, and fail closed whenever an audio route exists because the main
  model chooses whether to invoke the audio tool. Lazy Azure/OpenAI imports and
  lazy `core` package exports let model-free planning run without paid-runtime
  clients or the unrelated dataset stack.
- **One-verdict grading config contract** — remove unused `grades_per_task: 3`
  metadata from active v2 configs and document the implemented behavior: one
  final verdict per rubric item, with bounded tool and finalization calls. This
  changes config identities but does not add repeat grading or paid calls.
- **Fail-safe rubric classification** — disable all automatic natural-language
  prechecks after Stage A attempt 1 exposed seven invalid extension-only
  verdicts and further review found compound, negated, and partial-match risks
  in filename, worksheet, and count rules. Every filename, extension,
  worksheet, file/count, page, and word criterion now reaches the judge, while
  stale precheck IDs cannot score an item. Active configs record
  `precheck_patterns_version: v2` as identity metadata only. The rejected grade
  and analysis were removed before the corrected rerun. The same audit removed
  a false visual route where `chart-of-accounts` was read as a visual chart;
  the checked-in 220-task supported-vision inventory is now 466 calls. The
  corrected Stage A artifact contains zero precheck decisions and zero judge
  errors across all 153 items.
- **File-compatible audio routing** — retain criterion-level audio
  classification for inventory, but downgrade runtime routing to text when the
  selected targets contain no supported audio extension. This prevents an XLSX
  `Sound Technician` cost criterion from suggesting `probe_audio`. Selection,
  routing, and `read_deliverable` now share one WAV/MP3/FLAC/OGG/M4A/AAC set;
  extensionless targets remain conservatively audio while known unsupported
  suffixes downgrade to text. Recomputed cohort plans contain zero false audio
  routes; the final exact Stage A plan after all corrections requires 4 render
  and 4 perception calls.
- **Field Note benchmark data source** — replace duplicated completion and
  Self-QA literals in the prompt-complexity article, SVG hero, metric strip,
  result narrative, and comparison chart with an exact exp003-exp005 selector
  over `generated/reports-index.json`. Experiment detail headers now apply the
  same index `meta` and `summary` snapshot while retaining the lazy-loaded full
  report for task-level evidence. The selector requires one unique row per ID,
  the expected Baseline/Elicit/Elicit v2 conditions, subprocess mode, valid
  finite ranges, and count/rate consistency; missing or invalid data renders an
  explicit alert instead of stale fallback numbers. The article links directly
  to the source JSON and all three experiment detail pages, including
  accessible mobile card navigation. Shipped through PR #90 (`b9e224a`) and
  successful Pages run
  [29475359417](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29475359417);
  the deployed JSON, article, and exp003 detail values were verified to match.
- **Public task-spec privacy cleanup** — remove a provider-account failover
  specification and unreferenced hidden sweep metadata, generalize
  organization-specific monthly budget and capacity statements, and keep
  reproducible per-run cost measurements intact. Personal `tasks/**` files are
  now ignored by default while the canonical latest-task result remains
  tracked. The modified public tree passes Gitleaks v8.30.1 with zero findings
  and contains no matching account relationship, exact monthly operating
  budget, personal email, Azure resource identifier, or local-path patterns.
- **Finalization retry cost guardrails** — normalize configured finalization
  retries to zero or one, so `judge_max_retries` values above one cannot expand
  the paid recovery budget. If a supposedly tool-free finalization response
  unexpectedly requests a function call, reject it without dispatching any
  read or perception tool and return a score-excluded error. Deterministic tests
  now prove two-call latency, TPM-guard, token/cache, and incomplete-usage
  accounting across malformed-final recovery. Shipped through PR #88
  (`2728ef7d`); the merge triggered no workflow or paid run.
- **Tool-calling malformed-final recovery** — extend the bounded
  finalization-only retry from empty output to syntactically unparseable final
  JSON, as observed for two text criteria in canary run 29432455047. The retry
  reuses ordered evidence with no tools, low reasoning, and complete usage
  accounting. Valid JSON objects with invalid semantic envelopes are not
  retried, and retry exhaustion remains fail-closed.
- **Tool-calling empty-final recovery** — when a Responses API tool loop ends
  with an empty final message (observed after five successful reads in canary
  run 29429183215), issue at most one finalization-only retry using the existing
  evidence. The retry removes tools and parallel tool calls, lowers reasoning
  to `low`, preserves ordered response items, and keeps complete call, latency,
  input, output, and cache accounting. Retry exhaustion remains a score-excluded
  `empty_final_text` error and Track 2 still exits fail-closed. Shipped through
  PR #81 (`a68a3efe`).
- **Grading canary runtime fail-closed guards** — revert the invalid grade and
  analysis produced by run 29424766879 after 35 Azure requests rejected a
  106-character `prompt_cache_key` and the single vision response failed its
  semantic envelope. Tool-calling cache identities are now deterministically
  bounded to Azure's 64-character limit, while the vision prompt states the
  exact score/confidence/string contract and logs only safe validation reasons.
  Track 2 persists a schema-valid diagnostic but exits nonzero after an actual
  main/perception/render runtime failure or incomplete usage, excludes error
  tasks from score summaries, and rejects failed cache/resume artifacts before
  grader construction. Call-free selection and missing-deliverable diagnostics
  retain their existing behavior.
- **Grade downloader direct-entry import** — make
  `scripts/download_inference_from_hf.py` bootstrap the batch-runner root and
  lightweight `core.inference_manifest` package when executed as a file.
  Approved canary run 29423860683 passed renderer preflight and Azure OIDC but
  stopped before HF download or any model call because direct execution could
  not resolve `core`; the grade commit step now also requires the grading step
  itself to have completed successfully.
- **GitHub-hosted grading renderer verified** — model-free rerun 29393149367
  passed on `main` commit `f97cc170` after PR #74 fixed the direct script import
  boundary. Evidence recorded `ok=true`, exact Liberation Sans resolution,
  LibreOffice 24.2.7.2, PyMuPDF 1.28.0, and successful XLSX/PPTX PNG renders.
  No HF, Azure, batch, or model call was present in the workflow.
- **Renderer preflight direct-entry import** — make
  `scripts/preflight_grading_renderer.py` add its own batch-runner root and load
  only the lightweight `core.tools` package surface when executed as a file.
  GitHub-hosted run 29392707519 had installed LibreOffice and renderer Python
  dependencies successfully but failed before rendering because direct script
  execution could not resolve `core`; the fix also avoids pulling unrelated
  dataset/pyarrow imports into the four-package renderer environment.
- **Sandbox generated-code preflight and targeted repair** — local and Docker
  backends now execute untouched `solution.py` through a trusted launcher that
  compiles with the actual target Python before `runpy` starts untrusted code.
  A bounded first-record stderr protocol preserves compile provenance through
  `chdir`, `os._exit`, SIGKILL, and binary output without a writable sidecar.
  Invalid syntax never reaches the generated body and consumes the existing
  repair budget with syntax-specific guidance. Shared execution categories
  route schema, API compatibility, binary decode, memory, timeout, and backend
  failures to distinct prompt-authored strategies; chained tracebacks prefer
  the final exception. Best-attempt and manifest backend selection now preserve
  actual execution evidence instead of an earlier compile-only failure. Shipped
  through PR #71 (`aa6c35c9`); the backend-only merge triggered no workflow, so
  an owner-approved bounded runtime canary remains pending.
- **Grading Track 2 merge and deploy** — squash-merged the reviewed hardening through PR #69 (`6ad789a7`) and verified successful `Aggregate Tests & Deploy` run 29357775581. The merge did not dispatch any paid grading, batch, or cost-sweep workflow; live Ubuntu renderer and limited Azure vision canaries remain explicit follow-up gates.
- **Dashboard diagnostic scope consistency** — register exp027 as a diagnostic
  report hidden from every default cross-run surface, including leaderboard,
  trends, error narratives, header scope, and future grade cards. `?debug=1`
  restores the aligned experiment/report set, direct detail URLs remain
  available, existing valid subsets such as exp012 stay visible, and global
  benchmark KPI copy remains fixed at 220 tasks. Shipped through PR #67
  (`92efc105`) and verified on the deployed site: the default leaderboard/error
  views exclude exp027 (22 experiments), while `?debug=1` restores it (23
  experiments) and direct detail navigation remains available.
- **Inference config and subset integrity** — preserve `model.reasoning_effort`
  from experiment YAML through prepared tasks, add validated ordered
  `data.filter.task_ids`, and carry canonical task scope through Steps 4 and 5.
  Explicit subset runs now retain exactly their selected rows (including failed
  tasks), reject duplicate/missing/unexpected result IDs, and cannot create
  placeholders for unselected benchmark tasks. `execution.sandbox` also
  survives config round-trips.
- **Sandbox provenance privacy** — persist only bounded hashes, counts, token
  usage, latency, stable error categories, skill-match evidence, preprocessor
  status, and CI identifiers. Raw model/process/preprocessor text, exception
  messages, generated filenames, arbitrary attempt fields, and heavy QA reports
  are excluded from checkpoints and self-reports.
- **Grading Track 2 source and execution hardening** — canonicalize every inference task and deliverable path under the exact `deliverable_files/<task_id>/` tree, require an exact regular-file manifest match, and reject absolute/parent/other-task paths, duplicates, symlinks, and ancestor-symlink escapes before grader construction. Workflow string inputs now enter shell steps only through validated, quoted environment variables; resume chunks are limited to 0–10 and require the pinned inference revision. Main and vision judge envelopes reject missing, nonnumeric, nonfinite, inconsistent, or giant-integer score fields as usage-preserving score-excluded errors. Partial saves are atomic and reloaded/schema-checked; `rc=7` requires new durable progress, an exact staged grade diff, a successful strict rebase with unchanged grade SHA-256, current-schema validation, and a pushed commit before relay. The inference full SHA and full grader source hash remain fixed across chunks, including the actual fallback tool prompt bytes.
- **Grading Track 2 harness-owned render + vision** — route Overall Style and visual criteria through a trusted pre-main-judge render/perception pass for PDF/XLSX/XLSM/PPTX/images, while DOC/DOCX-only Overall Style uses formatting inspection and mixed split targets preserve child routing. The main model cannot request render bytes or invoke vision directly; invalid vision envelopes, renderer errors, unsupported scopes, per-item file caps, and task-wide vision budget failures become score-excluded `judge_error` results before a normal verdict. Strict relative-path/SHA-256 renderer, coverage, and vision provenance is retained for parent and child audit records without base64 or absolute paths. The checked-in 220-task policy inventory requires 466 supported vision calls with a task maximum of 68, under the configured hard cap of 72. Rubrics now resolve to an immutable full Hugging Face commit and load only from a staged, atomically promoted per-SHA parquet snapshot whose manifest verifies repository identity, exact paths, SHA-256 hashes, and sizes. Active v2 outputs include config identity, full rubric SHA, and prompt version; cache hits require a schema-valid exact task set, while resume requires a schema-valid unique subset and matching experiment/rubric/prompt/config/renderer identity. New runs reject duplicate inference IDs and invalid `--tasks` selections before grader construction. The Ubuntu 24.04 grade workflow conditionally installs and preflights LibreOffice/fonts before Azure login, fails if the exact output artifact is missing, and the analyzer prices mixed child perception usage by its actual modality. HF inference inputs now resolve once to an immutable full dataset SHA, stamp canonical repository/revision metadata, and atomically replace revision-local deliverables. Active v2 filenames include the full inference SHA plus a 16-character grader-source route, while payload/cache/resume verify the full SHA-256 over the grading implementation surface. Chunk relays propagate the resolved inference SHA, and grade commits use strict rebase with pre/post grade-blob SHA-256 and current-tree schema validation before retrigger eligibility.
- **`batch-runner/scripts/download_inference_from_hf.py`** — pass `HF_TOKEN` explicitly to `hf_hub_download()` (×2) and `snapshot_download()` via a new `_hf_token()` helper. The grade pipeline's "Download inference results from HF" step injects `HF_TOKEN` env, but `huggingface_hub` auto-pickup did not fire, so requests went out **anonymous** (CI log: `unauthenticated requests to HF Hub`). Under the sequential grade relay this tripped HTTP **429 Too Many Requests** on the inference parquet, breaking a chunk mid-run (e.g. 5.4 220 re-grade chunk-2 resume). Authenticated requests have a much higher rate limit → relay no longer 429s on repeated chunk downloads. No behavior change for single runs.

### Added
- **Prompt-complexity Field Note** — add a sixth Korean RealWorks Field Note
  comparing completion rate and Self-QA across the exp003 baseline, exp004
  Elicit, and exp005 headless-Elicit subprocess runs. The article defines
  Elicit as the GDPVal study's five-step verification prompt rather than a
  separate model or service, and identifies headless-Elicit as the same design
  with STEP 2 changed from display inspection to Pillow checks. It separates
  surviving-result self-assessment from whole-run coverage and avoids treating
  the comparison as a prompt-only A/B because runner settings also changed. A
  dedicated responsive hero and dual Recharts comparison visualize
  95.9/90.9/90.5% completion against 6.18/5.87/6.16 Self-QA, while the
  prompt-strategy question, first timeline event, and exp003-exp005 detail pages
  link to the new note. Shipped through PR #84 (`c9cb607`) and successful Pages
  run
  [29437433192](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29437433192);
  the production route was verified at desktop and mobile sizes, including
  dark mode and reduced motion.
- **RealWorks Field Notes** — add lazy-loaded `/notes` and `/notes/:slug`
  routes with nine question-led experiment groups, a nine-event chronology,
  and five evidence-linked Korean columns spanning CI/runtime constraints,
  silent-corruption measurement changes, multimodal perception, task-level
  output review, and the subprocess-to-sandbox decision. The dashboard and
  experiment detail pages now link into the notes, while articles link back to
  available experiment details and source evidence. Legacy `/journal` links
  redirect to the canonical `/notes` paths. The independent-project label,
  Korean reading fonts, responsive editorial rhythm, accessible evidence
  numbering, and explicit Self-QA boundaries distinguish these notes from the
  official GDPVal paper and pending external grades. Each published note opens
  with a story-specific responsive hero (animated inline SVG on desktop,
  large-label summary on mobile) and an evidence-caveated Recharts comparison.
  The same hero slot supports GitHub Pages static MP4/WebM assets with native
  controls, `muted`/`loop`/`playsInline`, optional captions, BASE_URL-safe paths,
  and reduced-motion-aware autoplay. Shipped on `main` as `8ac9c20` through
  successful Pages run
  [29425800514](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29425800514).
- **Model-free grading renderer preflight** — add a manual, `main`-only Ubuntu
  24.04 workflow with read-only repository permission, commit-pinned actions,
  no credentials or model calls, exact LibreOffice/font checks, strict JSON
  success validation, and seven-day evidence artifacts. A shared
  `requirements-renderer.txt` keeps the dedicated workflow and full grading
  environment on the same openpyxl, python-pptx, Pillow, and PyMuPDF lower
  bounds.
- **Opt-in job performance metrics** — experiments may enable
  `execution.metrics.enabled` to record bounded per-task wall, model, tool,
  verification, dependency, Self-QA, and orchestration times plus execution,
  sandbox, tool-call, Self-QA-call, and resumed job-run counts. Resume rounds
  preserve cumulative task lifetime, while `time_to_valid_artifact_ms` requires
  a saved file and successful sandbox verification. Step 6 adds coverage,
  average/P50/P95 job time, successful/failed averages, time-to-valid-file,
  phase totals, and call totals only when measured data exists. The experiment
  detail page conditionally exposes the aggregate panel, sortable Job Time
  column, and per-task metrics; legacy configs, manifests, result JSON, and UI
  remain unchanged when metrics are omitted. Activation requires the literal
  boolean `true`; unrecognized fields are discarded. Durations and counters
  use finite schema bounds with overflow-safe resume merging and strict JSON
  serialization. Time-to-valid requires both a verified sandbox status and at
  least one non-manifest artifact, so text-only and manifest-only tasks cannot
  inflate the metric. Wall-timeout checkpoints retain pending task objects, and
  relay completion replaces them through the same metric-merging path so prior
  task lifetime is not lost. Step 3 serializes once with `allow_nan=False`
  before opening either result destination, preventing split or non-standard
  JSON output. Giant JSON integers are rejected before float conversion, so
  progress merging and report aggregation cannot fail with numeric overflow.
  Shipped through PR #76 (`3258b5c3`) and verified by successful automatic
  `Aggregate Tests & Deploy` run 29423221608; the merge automatically
  dispatched no paid workflow. A separate owner-dispatched grading run
  29423860683 later failed at HF download before model grading or paid inference.
- **`exp027_GPT54_default_subprocess_bridge50`** — checked-in 50-task,
  9-sector diagnostic subprocess comparator for the historical exp026
  Sandbox/Skills runner bundle. Includes pinned 42 non-success-union tasks, six
  media controls, two general controls, source revisions, selection provenance,
  and analysis guardrails against causal or population-level overclaiming. The
  implementation landed through PR #64 (`4306fa55`). Actions run #93 completed
  without relay in 2h47m54s: 23 success, 14 QA-failed, and 13 error tasks, with
  a 5.08 average Self-QA. HF upload completed; result PR #66 was merged as
  `2a33c998` after the scope guard and Pages deployment `29342879619` published
  the report. The raw generated index contains exp027, while the default UI
  keeps official benchmark scope and KPI copy at 220 tasks.
- **Pinned exp026/exp027 paired analysis** — add a standard-library analyzer,
  immutable HF revisions and content hashes, deterministic 10,000-resample
  bootstrap settings, unit tests, and a checked-in diagnostic report. The same
  50 tasks show exp026 30/14/6 versus exp027 23/14/13
  success/QA-failed/error, while paired Self-QA is effectively unchanged.
  Outcome-selected statistics are explicitly non-confirmatory.
- **Repository completion records** — `.github/copilot-instructions.md` now
  requires every repository-changing task to refresh
  `tasks/LATEST_TASK_RESULT/README.md` and the `[Unreleased]` changelog before
  completion is reported.

### Changed
- **`.github/agents/azure-infra-engineer.md`** — rebuilt for Opus 4.8 Copilot (`model: Claude Opus 4.8 (copilot)`, `tools: vscode, execute, read, edit, search, web, todo`). Reframed from a generic Azure/PowerShell advisor into an **end-to-end coding-agent infra provisioner** covering the full **Microsoft Fabric → networking/identity → Azure AI Foundry** estate as ordered layers (foundation, network/identity, Fabric capacity+OneLake+lakehouse, Foundry hub/project+model deployments+connections, operate/verify). Adds OIDC-only auth rule (no client secrets, mirrors grading pipeline), Bicep-first IaC conventions, runtime-proof verification (declaration ≠ wired), least-privilege RBAC, what-if-before-deploy, cost/destructive ops gated to owner, CHANGELOG discipline, and inter-agent handoffs (deployment-engineer / extreme-reasoner / first-reviewer / git-committer).

### Added (grading-v2 PR3 — perception wiring + instrumentation, 0531)
- **`core/grader.py::_build_tool_judge`** now reads `judge.perception.visual` / `judge.perception.audio` from the config and instantiates `VisionPerception` / `AudioPerception` (sharing the Grader's Azure client), then injects them into `ToolCallingJudge`. Previously these blocks were validated by step8 but never wired, so visual/audio criteria were silently graded by the text judge. `grade_task` now calls `_tool_judge.reset_perception()` at each task boundary so per-task call caps reset.
- **`core.grader.ItemGrade`** gains 3 runtime-instrumentation fields (`routing_modality`, `perception_called`, `tools_used`) that land in `data/grades/*.json` per item — proves at runtime which modality an item routed to and whether a perception sub-judge actually fired. Schema-additive only.
- **`core.tool_calling_judge.ToolCallingResult`** gains `tools_used: list[str]` (ordered dispatched function names) and `perception_called: bool` (any `vision_judge`/`audio_judge` dispatch). Stamped on every return path including `judge_error` / JSON-parse-fail branches.
- **`tests/test_perception_wiring.py`** — 5 tests, all PASS — prove the wiring + instrumentation at runtime (not by config inspection): subjudges instantiated, vision-dispatch flips `perception_called` and adds `vision_judge` to `tools_used`, text item leaves both untouched, and `reset_perception()` propagates.
- **Phase-0/1 analysis tooling** (read-only):
  - `scripts/phase0_critical_modality.py` + `tasks/0531_sunday/phase0_critical_modality.md` — decomposes v2-mini's 3 critical regressions vs v1-mini by modality (all 3 are `formatting`, not perception-addressable).
  - `scripts/phase0b_flip_decomp.py` + `tasks/0531_sunday/phase0b_flip_decomp.md` — decomposes mini-vs-standard leniency flips (38 total: 32 text, 3 visual, 3 formatting). Pure-text leniency dominant → perception cannot recover the headline regression.
  - `scripts/phase1_gold_candidates.py` + `tasks/0531_sunday/gold_candidates.md` — enumerates 19 rubric items (12 visual + 1 audio + 6 formatting) for owner hand-grading; GDPVal carries no per-item expected verdict, so thesis Phase 4 is blocked on owner gold.
  - `scripts/phase2_perception_probe.py` — synthetic-deliverable live firing probe (currently blocked on local Azure auth: SP secret expired + resource key-auth disabled).
- **Reports (`tasks/0531_sunday/`):** `phase1_gold.md`, `phase2_wiring.md`, `phase3_smoke.md`, `phase4_thesis_verdict.md`, `PERCEPTION_THESIS_REPORT.md`. Phase 4 verdict is **BLOCKED** pending owner gold + Azure auth fix; v2 flip justification is on hold.

### Notes
- `feat/wire-perception` branch is local-only. Per constitution rule 13, no push of decision artifacts or default-flips to `main` without owner go.
- Dead config recorded, **not modified**: `grades_per_task: 3` (unwired), `context_management.auto_compact` array-shape (disabled).

### Added (grading-v2 PR2 — tool-calling grader rebuild)
- **`core/tools/read_deliverable.py`** — 6-op read-only file inspection tool (`inspect_structure`, `read_content`, `inspect_formatting`, `render_to_image`, `probe_audio`, `probe_video`). Trusted base-dir path resolution (rejects `..` traversal + absolute escape + symlink-out). Uniform `{ok, data}` / `{ok=False, error, error_type}` envelope. 200k char content cap + 5MB image cap with Pillow downsample. Wheel-only deps: `PyMuPDF` for PDF render, `PyAV` for audio/video probe — keeps `grade-run.yml` apt-get-free. `READ_DELIVERABLE_TOOL_SCHEMA` ready to drop into Responses API `tools=[...]`. Commit `69d2d89`.
- **`prompts/grader_judge_v2.md`** (prompt_version `v2`) — tool-aware judge prompt. Drops the v1 `{{extracted_content_or_summary_truncated_4000}}` inline dump entirely. Mandates evidence be a direct quote from a `read_deliverable` tool response (fabricated quotes → verdict=fail). Inline catalog of all 6 tool ops + routing hint placeholders + `tool_calls_made` in required output schema. `prompts/grader_judge_v1_archive.md` is a verbatim copy of v1 for re-run reproducibility. Commit `419b612`.
- **`core/grader_routing.py`** — pure-function perception-modality classifier. Priority `visual > audio > formatting > text`; whole-word case-insensitive keyword match. `RoutingDecision.to_prompt_hint()` renders the `{{routing_modality}}` / `{{routing_preferred_op}}` placeholders consumed by `grader_judge_v2.md`. Commit `ab161f9`.
- **`core/perception/vision.py` + `core/perception/audio.py`** — vision (gpt-5.4) + audio (gpt-audio-1.5) sub-judges. Injected `client`, per-task caps (5 / 3), graceful `judge_error` on cap_exceeded / bad_image / endpoint_missing / FileNotFoundError / upstream exception. Vision: `(path,page)` image cache, base64 PNG header pre-validation. Audio: 30s head trim via PyAV (re-encodes to WAV in memory), `AZURE_AUDIO_ENDPOINT` env fallback. Commit `163bfdc`.
- **`core/tool_calling_judge.py`** — `ToolCallingJudge` standalone class. Responses API function-calling loop (≤10 iterations, ≤8 tool calls per item, both caps configurable). Dispatches `read_deliverable`, `vision_judge`, `audio_judge` function_calls; echoes both `function_call` and `function_call_output` into the next input batch (Azure Responses contract). Returns `ToolCallingResult` (same shape as legacy `Grader._judge`). Commit `653ef1d`.
- **`core.grader.Grader._tool_judge` dispatch** — `__init__` detects `judge.tools.read_deliverable` presence and instantiates a `ToolCallingJudge` sharing the same Azure client. `_judge` early-delegates when active. Legacy text-extract path is untouched; v1 configs run unchanged. Commit `653ef1d`.
- **`grading_configs/default_v2.yaml`** (schema_version `2.0`) — single-tier gpt-5.4 medium judge + `judge.tools.read_deliverable` (activates the v2 dispatch) + `judge.perception.{visual,audio}` modality models + sign-aware critical rule `|max_score| >= 4` + `grades_per_task: 3`. Commit `f14c22a`.
- **`step8_grade.py::validate_grading_config`** accepts schema_version `1.0` and `2.0`. v2 optional blocks validated: `judge.tools.read_deliverable.ops` is a non-empty subset of the 6 allowed ops; `judge.perception.{visual,audio}` require `model`; `judge.critical.rule` enum-restricted; `prompt.tool_template` must exist when set. Commit `f14c22a`.
- **`grading_configs/_archive_v1/`** — v1 sweep/tier configs (`validation_hybrid.yaml`, `validation_pro_only.yaml`, `tiered_critical_pro_mini.yaml`, `_sweep_template.yaml`, `recommended_gpt5_4_mini_2026-05-24.yaml`) archived for cache-key reproducibility + A/B compare against v2. `grading_configs/README.md` documents active vs archived + v1↔v2 feature matrix. Commit `2aa6688`.

#### Tests (PR2 net delta: +85 tests, 0 failures)
- `tests/test_read_deliverable.py` (25 cases): schema/path-safety/per-op happy + scope filters + truncation + render PNG header + cap + probe_audio round-trip
- `tests/test_grader_judge_v2_prompt.py` (8 cases): version tag, all 6 ops named, no v1 placeholder leak, routing hint placeholders, tool_calls_made schema, v1 archive integrity
- `tests/test_perception_routing.py` (19 cases): 12-criterion matrix + priority test + case-insensitive + word-boundary + `to_prompt_hint()` + `inventory()`
- `tests/test_perception_vision.py` + `tests/test_perception_audio.py` (16 cases): happy / cap / cache / corrupt / upstream exception / endpoint missing / reset
- `tests/test_tool_calling_judge.py` (11 cases): no-tool happy path / one tool round / cap short-circuit / max_iterations break / visual routing advertises vision_judge tool / text routing omits perception / vision dispatch end-to-end / upstream exception / unparseable final text / missing evidence / unknown function
- `tests/test_grader_tool_dispatch.py` (2 cases): v2 config triggers `_tool_judge` and `_judge` delegates / v1 config keeps `_tool_judge` None
- `tests/test_grading_config.py` (+7 cases): v2 schema accepted; default_v2.yaml validates; bad ops list / unknown ops / perception missing model / critical rule enum / tool_template path existence

#### Acceptance status (SPEC §7)
| gate | status |
|---|---|
| 7.1 gold-ceiling, 7.2 formatting gap collapse, 7.4 judge_error<2%, 7.5 grades_per_task×3 + CI | **deferred to PR3** — require live `grade-run.yml` jobs |
| 7.3 xlsx vs bare-CSV distinguishable in evidence | structurally guaranteed by `inspect_formatting`; confirmed in unit tests; cross-experiment proof pending PR3 task 301 |
| 7.6 PR1 sign-aware headline numbers republished | ✅ landed in PR1 (`PR1_REPORT.md`) |

#### What did NOT change in PR2 (deferred)
- `grade-run.yml` default `grading_config` is still `default_gpt5pro.yaml`. Flip to `default_v2.yaml` gated on PR3 task 302 cost-validation; flipping pre-validation risks an accidental $50+ accidental run on next trigger.
- Task 207 acceptance grep (`tier_pro|tier_standard|tier_mini|deliverable_extract_max_chars` → 0 matches) is **PARTIAL**. v1 sweep/tier configs are archived but `core/grader.py` legacy text-extract path, `core/grader_batch.py`, and `default_gpt5pro.yaml` remain on disk because they back the still-default v1 path. Full strip happens in a single cleanup PR after PR3 PASS.

Full PR2 details: [tasks/rebuilding_grading_task/PR2_REPORT.md](tasks/rebuilding_grading_task/PR2_REPORT.md).

### Added (grading-v2 PR1 — score-math sign-bug fix, headline numbers now trustworthy)
- **`ItemGrade.model_did_right`** — sign-aware right-outcome flag computed in `core.grader.Grader._aggregate`. For positive `max_score` items right = `verdict == "pass"`; for negative penalty items right = `verdict != "pass"` (i.e. the bad thing did NOT happen). `judge_error` is conservatively right=False. Resolves the systemic bug where every `verdict == "pass"` filter mixed semantically opposite signals for positive and negative rubric items.
- **`MAGNITUDE_THRESHOLD = 4` + `_is_critical_item()`** in `core/grader.py` and `summary.wow.critical_item_pass_rate` recomputed in `step8_grade._compute_summary` to use sign-aware `model_did_right`. Critical set grows from 397 (legacy `score >= 3` rule, positive only) to 483 items (now correctly including 86 negative-magnitude penalty items the legacy rule discarded). Documents rationale for `required` field being dead (null across all observed GDPVal rubrics).
- **`TaskRubric.max_score` = positive-only sum** + **`TaskGrade.pct_raw`** un-clamped diagnostic field. Fixes 4 exp003 tasks where v1's arithmetic positive+negative sum produced `total_max <= 0`, collapsing pct into mathematically undefined values that the `[0,100]` clamp silently masked (e.g. `6074bba3` v1 reported 65.76% on `total_max=-330`; v2sm reports 0.0% with `pct_raw=-434.00`).
- **`scripts/backfill_sign_aware.py`** + **4 new `*__v2sm.json` files on main** (`data/grades/exp003_*__v2sm.json` × 2, `data/grades/exp998_smoke_*__v2sm.json` × 2). v1 files preserved untouched (back-fill policy (c) from `tasks/rebuilding_grading_task/000-OVERVIEW.md`).
- **`schema_version` enum bumped to `["1.0", "1.1"]`** in `batch-runner/schemas/grade.schema.json`. v1.1 = v1.0 superset (`model_did_right`, `pct_raw` optional). `scripts/aggregate-grades.mjs` routes both versions through `processV1GradesFile`.
- **15 new tests** across `batch-runner/tests/test_grader.py` (sign × verdict normalization, magnitude threshold, sign-aware `critical_fail`, positive-only denominator, `pct_raw` diagnostics) and `scripts/__tests__/test_backfill_sign_aware.py` (6 backfill scenarios). Full regression: **478 batch-runner pytest + 29 scripts pytest + node mjs** all green.

#### Headline diff (exp003 219/220 graded)
| metric | hybrid v1 | hybrid v2sm | mini v1 | mini v2sm |
|---|--:|--:|--:|--:|
| critical_item_pass_rate | 0.421 | 0.466 | 0.518 | 0.596 |
| avg_score_pct | 49.25 | 48.18 | 51.47 | 50.97 |

The wider hybrid-vs-mini critical gap on v2sm (−0.130 vs v1 −0.097) reflects inclusion of 94 previously-excluded negative-magnitude penalty items. STRATIFY_v2 bucket decomposition (formatting 60.3% / penalty 21.8% / content 17.9% of hybrid-stricter pairs) remains the authoritative driver-of-the-gap read. Full PR1 details: [tasks/rebuilding_grading_task/PR1_REPORT.md](tasks/rebuilding_grading_task/PR1_REPORT.md).

PR2 (tool-calling grader rewrite) and PR3 (validation gates) tracked in `tasks/rebuilding_grading_task/` and will land in subsequent sessions.

### Added (autonomous validation + full follow-up chain)
- **`scripts/compare_grades.py`** — pair-wise critical-item comparison over the intersection of `task_id`s between two grade JSONs. Emits markdown report + decision JSON. Autonomous decision rule: `hybrid_critical_pass / mini_critical_pass >= 0.7` → PROCEED, otherwise → ABORT. Used both for fast 12-task C′ pre-validation and for the full 220-task post-run head-to-head.
- **`scripts/analyze_grade_run.py`** — extracts wall-clock, judge latency p50/p95, total tokens, price-table-based cost estimate (`PRICING_USD_PER_M_TOKENS`), top-5 slowest tasks, and optional Δ vs baseline grade. Auto-invoked by `grade-run.yml` on rc=0 chunks; produces `<grade>.analysis.md` alongside the grade JSON.
- **`.github/workflows/validate-hybrid-and-decide.yml`** — single-job C′ validation: grades the same first-N tasks with mini default, runs `compare_grades.py`, commits comparison + decision, and on PROCEED auto-dispatches the hybrid full run. `pair_limit` default 12, `timeout-minutes: 150` (sized for exp003's ~3-4 min/task on mini default).
- **`grade-run.yml` auto follow-up steps (rc=0 only):**
  - hybrid full done → auto-dispatch mini default full run for the same experiment (skipped if mini grade ≥200 tasks already exists)
  - mini default full done + hybrid full present → run `compare_grades.py` over the full 220-task pair, commit `DECISION_FULL.json` + `COMPARE_FULL.md` to `data/grades/_validation/`
- **`scripts/__tests__/` (11 new tests)** — `test_compare_grades.py` (6 tests: PROCEED/ABORT at threshold boundary, task_id intersection, mini critical_pass=0 guard) and `test_analyze_grade_run.py` (5 tests: single vs routing cost mode, wall-clock from `graded_at` span, top5 ordering, markdown sections).

### Added (chunked auto-resume for long grade runs)
- **`step8_grade.py` --resume flag + 4h time guard.** Reads existing partial grade JSON at the templated output path, harvests already-completed `task_id`s, skips them, and continues. Time budget is `GRADER_TIME_BUDGET_SEC` env (default 14400s/4h); when tripped before all tasks are graded, step8 partial-saves and exits 7. Distinct from existing `--force` semantics (mutually exclusive).
- **`grade-run.yml` self-retriggering chunk pattern.** Job `timeout-minutes: 320` (5h20m, safely under GH Actions' 6h hard limit), `permissions.actions: write`, new `resume`/`resume_chunk` inputs. When step8 returns 7, commits the partial then dispatches the next chunk via `gh workflow run` (uses `GITHUB_TOKEN`, no PAT). Safety cap: `resume_chunk > 10` aborts. Enables 220-task hybrid/pro_only runs that exceed the single-job 6h limit.
- **`PYTHONUNBUFFERED=1`** on the grading step so per-task progress streams live in the GH Actions log instead of buffering for minutes.

### Fixed
- **`gpt-5.4-mini` rejects `reasoning_effort='minimal'` (Azure HTTP 400).** Valid values are `none/low/medium/high/xhigh`. `core/grader.py` tier_mini default and `validation_hybrid.yaml` both updated to `'low'`; `_sweep_template.yaml` doc comments updated to document the constraint. Root cause of a 6.6h wasted hybrid run that produced only 20/220 graded tasks before this was found.
- **`pct` clamped to `[0, 100]` in `core/grader.py`** to honor `grade.schema.json` `{minimum: 0, maximum: 100}`. Two exp003 tasks (#44 pct=108.9%, #45 pct=229.3%) were violating the schema, causing partial-save validation to silently fail at task #50. `step8_grade.py` partial-save block now also wrapped in try/except with full traceback so future schema violations surface immediately.
- **`pytest -q` collection unbroken from `batch-runner/`.** Two legacy test files (`test_main.py`, `test_main_hf_integration.py`) imported the removed pre-pipeline monolith `main.py` at module top and crashed collection; wrapped with `pytest.importorskip('main')` so they cleanly skip. `test_data_loader.py::test_load_raises_error_when_no_snapshot_and_no_auto_download` asserted the old `download()` substring in the error message; loosened to accept either `step0_bootstrap.sh` (current) or `download()`. Result: 465 passed / 2 skipped / 0 failed (was 37 deselected + 2 errors).

### Tested (decision: keep single-mini default; reject tiered hypothesis)
- **Tiered grading hypothesis rejected on exp003 head-to-head.** Re-tested the ORIGINAL `TASK_GRADE_COST_OPTIMIZATION.md` proposal (pro for weight≥4 critical items, mini for rest) against the sweep-selected single-mini default on 40 tasks of `exp003_GPT52Chat_baseline_runner_exec`. Tiered LOST on all axes:
  - critical_item_pass_rate: single-mini **0.55** vs tiered **0.43** (tiered worse, opposite of intent)
  - avg_score_pct: 47.26 vs 45.61 (tiered −1.65pp)
  - judge_total_latency: 6,002s vs **14,845s** (tiered 2.5× slower)
  - cost (40 tasks): ~$1.7 vs **~$25** (tiered ~15× more expensive)
  - Hypothesis: gpt-5.4-pro with reasoning_effort=high becomes MORE strict on borderline criteria, depressing critical_pass instead of raising it. Confirms the Sweep Phase A pattern (A1_pro_high < A2_std_extract_1500 by ~5pp).
- `tiered_critical_pro_mini.yaml` remains in `batch-runner/grading_configs/` for future re-experimentation (e.g., weight≥5 critical, or pro at medium effort), but is NOT promoted to default.
- Full analysis: `tasks/0525_monday/COMPARISON_REPORT.md`.

### Known issues
- **`step8_grade.py` exits 1 after task #50** when grading exp003 — discovered during the tiered validation. Both runs (single-mini and tiered) failed at the exact same task #50 / `d025a41c` boundary, no Python traceback, ~2.5h elapsed in mini run / ~4h in tiered. Likely memory accumulation or task #51 entry crash. Cost optimization is unaffected; bug tracked in `tasks/0525_monday/TASK_STEP8_TASK50_FAIL.md`. **Root cause found and fixed above** (pct schema violation + silent partial-save failure).

### Changed
- **`batch-runner/grading_configs/default_gpt5pro.yaml` now uses `gpt-5.4-mini` at medium reasoning effort (was `gpt-5.4-pro` high).** Promoted from `recommended_gpt5_4_mini_2026-05-24.yaml` after Stage 1 validation re-graded `exp998_smoke_baseline_sample` against the prior baseline grade. Validation results (head-to-head, same inference, same rubric, same prompt, same precheck):
  - avg_score_pct: 77.83 → **78.03** (+0.20pp, well within ±2pp acceptance)
  - critical_item_pass_rate: 1.00 → 1.00 (preserved)
  - judge_error_rate: **5.9% → 0.0%**
  - precheck_pass_rate: 0.80 → 0.80 (unchanged)
  - judge_total_latency_sec: 8530 → **265** (32× faster)
  - input/output tokens: −23% / −60%
  - Projected full-run cost (220 tasks, linear extrapolation): **$493 → $18** (−96.3%). Projected fixed-budget efficiency improved by approximately **27×**.
- Filename `default_gpt5pro.yaml` preserved so existing `grade-run.yml` triggers, dashboard aggregators, and downstream tooling continue to work. `config_name` field updated to `default_gpt5pro`.
- Prior config preserved as `batch-runner/grading_configs/recommended_gpt5_4_mini_2026-05-24.yaml` (identical content; kept for documentation / future renames).
- Rollback path: `git revert <this commit>` reverts to the gpt-5.4-pro high default. Recommended config remains available for explicit `--grading_config recommended_gpt5_4_mini_2026-05-24.yaml` invocation.

### Added
- **Grading cost optimization sweep — winner `A4_model_mini` (-96.3% cost).** Autonomous sweep (27 variants across Phase A axis-sweeps / Phase B tier-combinations / Phase C stability + 1 gpt-4o diversity check) selected `gpt-5.4-mini` at medium reasoning effort, no batching, deliverable extract 1500 chars as the new default grading judge. Full-run cost projection drops from $493 (baseline `default_gpt5pro.yaml`) to **$18.45** (-96.3%) at avg_score_pct **+0.08pp**, critical_item_pass_rate **1.00** preserved, judge_error_rate **0.0%** (baseline 5.9%). Smoke wall-clock 299s vs 142min (28× faster), with approximately **27×** better fixed-budget efficiency. Total sweep spend $42.36 / $80 cap across 4 GH Actions runs (12.6 hours wall-clock). Drop-in config: `tasks/0523_saturday/cost_opt_results/2026-05-24-grade-cost-sweep/winner_config.yaml`. Full analysis: `tasks/0523_saturday/cost_opt_results/2026-05-24-grade-cost-sweep/FINAL_REPORT.md`. Key insights: (a) gpt-5.4-pro is unusable below medium reasoning (verdict JSON parse fails 100%); (b) tier combinations consistently underperform single-mini (verdict fragmentation); (c) batching loses 3.6pp score per 3× call reduction; (d) gpt-4o diversity validator unfunctional with Responses-API reasoning shape. Caveats: winner has only 1 measurement (Phase C only stresses Phase B variants), pricing is approximate. Promotion path: manual full-run validation → replace default_gpt5pro.yaml.
- **`.github/workflows/grade-cost-sweep.yml` — autonomous sweep dispatcher CI.** New workflow runs `scripts/grading_cost_sweep.py` end-to-end on GH Actions. `source_ref` input separates OIDC subject (must be a federated ref, typically `main`) from the code branch to checkout (the feat branch with sweep dispatcher). 350-min timeout. Federated OIDC via `azure/login@v2` (no API key, no secret rotation needed). Commits `RESULTS.md` / `progress.json` back to source_ref; uploads grade JSON + run.log artifacts for 30 days. Workflow itself lives on `main`; sweep code lives on the feat branch.
- **`fix(grader)`: API key fallback for sweep environments without working OIDC** (opt-in via `GRADER_ALLOW_API_KEY_FALLBACK=1` env). Production CI keeps OIDC-only behavior by default. Documented in module docstring.
- **`fix(sweep)`: subprocess env injection from `batch-runner/.env`**. step8_grade and core/* read only from `os.environ` and do not call `load_dotenv`; the dispatcher now hydrates the subprocess env so local execution does not silently lose `AZURE_OPENAI_ENDPOINT`.
- **`fix(sweep)`: variant outputs isolated to per-variant `runs/<name>/` dir**. Previously variant configs left `output.directory` at the template default `../data/grades`, causing every variant to overwrite production grade JSONs (caught via `git diff` before any data was lost). `render_temp_config()` now sets `output.directory` to an absolute per-variant path; `run_step8_grade()` uses `shutil.copy2` instead of `shutil.move` so the templated original survives for audit.
- **TASK_GRADE_COST_SWEEP Track 1 — prompt-level batching + tiered judge routing.** New `batch-runner/core/grader_batch.py` (`BatchJudge`) evaluates N rubric items per Azure OpenAI Responses API call with per-item evidence enforcement and one-level `chunk_size // 2` fallback on parse failure. New sibling prompt `batch-runner/prompts/grader_judge_batch.md` (legacy `grader_judge.md` preserved byte-identical). `batch-runner/core/grader.py` accepts two new OPTIONAL config keys: `grader.batch_size` (int, default 1) and `judge_routing` (tier_pro / tier_standard / tier_mini); when either is set, judge items are routed by tier and dispatched in batches, and `judge_call_count` switches from per-item to per-API-call semantics. New reference config `batch-runner/grading_configs/_sweep_template.yaml` shows the v1.0 schema plus the new optional knobs. 14 mocked unit tests (`tests/test_grader_batch.py` + `tests/test_grader_routing.py`).
- **TASK_GRADE_COST_SWEEP Track 2 — autonomous sweep dispatcher.** `scripts/grading_cost_sweep.py` (executable, OIDC-only) drives the cost-optimization sweep end-to-end: loads `tasks/0523_saturday/grading_cost_sweep_plan.yaml` (15 Phase A + 5 Phase B variants + Phase C stability spec + gpt-4o diversity validator), validates each variant against a hard-coded `MODEL_TPM` table at 70% cap, renders per-variant configs on top of `_sweep_template.yaml`, subprocesses `step8_grade.py` per variant, extracts metrics, runs Pareto selection under acceptance hard filter (critical=1.0, err≤5%, score±2pp), and emits `RESULTS.md` + `summary.json` + `winner_config.yaml`. Cost cap $80 enforced; `progress.json` supports `--resume`. 12 mocked tests at `scripts/__tests__/test_grading_cost_sweep.py`. Operator guide at `tasks/0523_saturday/cost_opt_results/README.md`.
- Grade source linkage (Phase 2). `step8_grade.py` now embeds two new fields on every emitted grade JSON: `source_inference_experiment_id` (defaults to `experiment_yaml_name`; overridable via new `--source-experiment-id` CLI flag) and `source_inference_run_dir` (repo-relative path, null when unknown). `scripts/aggregate-grades.mjs` resolver looks up `taskQaByExperiment` by the source pointer first, falling back to `experiment_id` (Phase 1 behavior preserved). Schema `batch-runner/schemas/grade.schema.json` adds both fields as optional/nullable — legacy v1 grades without them still validate. Backfilled `data/grades/exp998_smoke_baseline_sample__*.json` to point at `exp999_smoke_baseline_sample`, restoring 3/3 calibration matching (MAE=10.65, unmatched=0). Spec: `tasks/0523_saturday/TASK_GRADE_SOURCE_LINKAGE_BACKEND.md`.
- `tasks/0523_saturday/TASK_GRADE_COST_OPTIMIZATION.md` — judge 채점 비용/시간 압축 계획 (smoke 142m → 30m, 풀런 ~$540 → ≤$120). reasoning_effort, precheck 확장, item batching, tiered judge routing(mini=extended precheck / standard=gpt-5.5 / pro=critical only), concurrency 상향의 단계별 실행안.
- `tasks/0523_saturday/TASK_GRADE_COST_SWEEP.md` — 자율 dispatch sweep 사양. `scripts/grading_cost_sweep.py`가 16+5+6+1=28개 변종(Phase A 단축/Phase B 조합/Phase C 안정성/diversity)을 Global Standard API + prompt-level batching으로 실행하여 정확도 제약(critical=1.0, err≤5%, score±2pp) 내 Pareto 우승자를 자동 도출하고 `RESULTS.md` + `winner_config.yaml`을 생성. 사용 모델은 endpoint 가용 5.4 family(pro/std/mini/nano) + gpt-4o(diversity only). cost_cap_usd $80 강제.
- Grade detail page: Self-QA vs Rubric calibration view (Phase 1). Three new columns (Self-QA, Δ Gap, Calibration), three new filters (Calibrated/Overconfident/Underconfident), Calibration MAE pill in Health Strip, and footer match-rate note. Build-time join via `aggregate-reports.mjs` enriching reports-index with compact `task_qa` map; `aggregate-grades.mjs` performs strict per-experiment lookup (no global task_id map). Dummy grades and unmatched experiments are explicitly handled. Spec: `tasks/0523_saturday/TASK_GRADE_DETAIL_SELF_QA_CALIBRATION.md`. Follow-up: `TASK_GRADE_SOURCE_LINKAGE_BACKEND.md`.

## [2026-05-23] — Phase A wow follow-up: dashboard cleanup + grading hotfix

### Added

- **Dashboard cleanup spec package + WOW chrome cleanup (PR #1 of
  `tasks/dashboard_cleanup`).** Threaded `inference_model` vs
  `judge_model` as separate fields end-to-end so the GradeDetail header
  no longer misleads users into thinking the judge model solved the
  tasks. Aggregator (`scripts/aggregate-grades.mjs`) gained:
  - `grade_status: 'graded_v1' | 'legacy_dummy' | 'no_grade'` derived
    from `schema_version` / `_meta.is_dummy`.
  - `experiment_id` lifted to a top-level field (no more brittle
    `startsWith` matching across the dashboard).
  - `inference_model` / `judge_model` split — the legacy `model` falsy
    fallback to `judge.model` was removed.
  - Unit tests under `scripts/__tests__/aggregate-grades.test.mjs`
    locking the no-fallback contract + status derivation (3 fixtures).
  Frontend additions: `src/types/grade.ts` (already shipped in PR #46;
  unchanged here), `src/lib/format.ts` (`fmtPct` / `fmtLatency`),
  `src/components/wow/HealthStrip.tsx` (single-Card inline pill strip
  showing `judge_error_rate`, `judge_pass_rate`, `precheck_pass_rate`,
  `total_judge_calls`, `total_judge_latency_sec`; err pill turns red
  + `AlertTriangle` when `judge_error_rate > 5%`). Copy pass 2 across
  `src/data/tooltipTexts.ts` + `src/components/ScopeBadge.tsx`
  separates "self-QA" (model judging itself during inference) from
  "LLM-judge grade" (rubric-based, run via `grade-run.yml`) on every
  surface — KPI tiles, leaderboard tooltips, About modal bullets,
  empty-state CTAs.

- **`tasks/dashboard_cleanup/` 8-file spec package.** README + 000
  overview + 001 (model display) + 002 (banner/status) + 003 (health)
  + 004 (disagreement guard) + 005 (copy pass 2) + 006 (rollout) +
  copy_audit.md. Amended in-place after extreme-reasoner +
  ui-designer deep review (precedence rules, opacity → dashed border,
  amber → zinc, hard-gate aggregator tests, mandatory grep audit).

### Changed

- **`legacy_dummy` cards on the Grading tab now use `border-dashed`
  with a neutral `DEMO` badge** (BookOpen icon, zinc palette) instead
  of `opacity-90` (WCAG AA contrast fix) and instead of the previous
  amber `⏳ Awaiting LLM-Judge Grade` strip (which misleadingly fired
  even when v1.0 grades were present). The `⏳ Awaiting` strip is
  removed from per-card chrome.

- **Grading Analysis tab top banner is now status-aware.** When only
  legacy demo grades exist, the banner uses a neutral zinc tone with
  a `BookOpen` icon and points to `grade-run.yml`. When legacy +
  graded-v1 are mixed, the banner switches to a soft sky tone with an
  `Info` icon clarifying that some experiments still show demo data
  alongside fresh LLM-judge results. Amber is no longer used in this
  surface; it remains reserved for `self_assessed_pre_grading` (a
  true "awaiting" state on the experiment side).

- **`ScopeBadge` union extended.** `'graded_v1'` (fuchsia, Sparkles
  icon — "✨ LLM-Judge Graded (v1.0)") and `'legacy_demo'` (zinc,
  BookOpen — "📚 Legacy Demo") added; pre-existing `'graded'` and
  `'self_assessed_pre_grading'` variants preserved. `ExperimentDetail`
  now derives scope via `resolveScope(meta, grades)`: grade-derived
  status wins when an exact `experiment_id` match exists, otherwise
  meta is used as fallback.

- **`Grader Disagreement` UI is guarded.** Both the cross-experiment
  chart in `GradingAnalysisView` and the per-card `Disagreement`
  StatMini in `GradesSummary` now render only when
  `inconsistent_grades > 0` (i.e., Phase B multi-judge runs). The
  underlying counter logic is retained for Phase B.

- **CHANGELOG entries are now grouped under dated release headings
  (`## [YYYY-MM-DD]`)** instead of a single open-ended `## [Unreleased]`
  block. The previous entries have been bundled into a single
  retroactive `## [2026-05-20]` heading since they were committed in
  PR #41–#46 across May 17–23 with the same broad theme (Phase A core
  + WOW dashboard). New PRs will open a fresh dated heading at the
  top.

### Fixed

- **`step8_grade.py` no longer leaves `inference_model` as the empty
  string.** A new `_resolve_inference_model(inf_results, exp_config)`
  helper resolves with the priority `inf_results['model']` →
  `experiment_yaml.condition_a.model.deployment` → `''`, never falling
  back to `config['judge']['model']`. The dashboard's previous fall-
  through `model = inference_model || judge.model` made the GradeDetail
  page show the judge model (`gpt-5.4-pro`) as if it had solved the
  tasks; the resolver guarantees `inference_model` reflects the actual
  inference deployment. Whitespace inputs are stripped on both sources.
  Three new tests in `tests/test_step8_grade.py` lock the contract,
  including a defensive `inference_model != judge.model` assertion
  independent of the literal judge string. (PR #47)

- **`grader.per_item_max_output_tokens` raised 800 → 1600 in
  `grading_configs/default_gpt5pro.yaml`.** The first smoke run on
  2026-05-21 produced `judge_error_rate = 0.2381` (20 of 84 calls
  failed); root cause hypothesis is that `gpt-5.4-pro` with
  `reasoning_effort=high` consumes most of the output-token budget on
  reasoning tokens, leaving the previous 800 ceiling insufficient to
  emit the verdict JSON. 1600 ≈ 2× safety margin without meaningful
  cost impact at the 220-task scale. (PR #47)

## [2026-05-20] — Phase A grading pipeline + WOW dashboard

### Added

- **Phase A grading infrastructure.** Added rubric-based grading pipeline
  components: `batch-runner/core/rubric_loader.py`,
  `batch-runner/core/grader.py`, `batch-runner/prompts/grader_judge.md`,
  `batch-runner/step8_grade.py`,
  `batch-runner/grading_configs/default_gpt5pro.yaml`,
  `batch-runner/schemas/grade.schema.json`,
  `.github/workflows/grade-run.yml`,
  `batch-runner/scripts/download_inference_from_hf.py`, and
  `.github/agents/grading-engineer.md`. (PR #45)

## [2026-05-20] — Phase A grading pipeline + WOW dashboard

### Added

- **Phase A grading infrastructure.** Added rubric-based grading pipeline
  components: `batch-runner/core/rubric_loader.py`,
  `batch-runner/core/grader.py`, `batch-runner/prompts/grader_judge.md`,
  `batch-runner/step8_grade.py`,
  `batch-runner/grading_configs/default_gpt5pro.yaml`,
  `batch-runner/schemas/grade.schema.json`,
  `.github/workflows/grade-run.yml`,
  `batch-runner/scripts/download_inference_from_hf.py`, and
  `.github/agents/grading-engineer.md`. (PR #45)

- **Phase A wow — narrative + dashboard integration.** Threaded schema
  v1.0 grade JSON into `NarrativeAnalyzer` + `step6_report`
  (`_load_grade_for_experiment`, `_build_grading_guard_clause`,
  `_build_grading_results_section`, N3 disclosure paragraph instruction).
  Added W1–W6 WOW components under `src/components/wow/`
  (RubricCoverageCard, CriticalItemCard, StructureVsReasoning,
  SectorHeatmap, ScoreDensityHistogram, RubricSeverityCurve) backed by
  `src/types/grade.ts` and rendered conditionally via `<WowSection>` in
  `src/pages/GradeDetail.tsx`. (PR #46)

### Removed

- **`core/evals_submitter.py` dead code.** Removed deprecated placeholder
  hosted-grading submitter and its test file
  (`tests/test_evals_submitter.py`) in favor of the new self-grading flow.
  (PR #45)

## [2026-05-17] — Resume Round watchdog + silent corruption fixes

### Fixed

- **step2_run_inference: wall-timeout watchdog now also fires inside Resume
  Rounds (silent relay-bypass fix).** Previously the `wall_deadline` check
  existed only in the Round 0 (initial run) and Relay-run continuation
  loops in `batch-runner/step2_run_inference.py`. When Round 0 completed
  within `wall_timeout`, control fell through to the Resume Round loop
  (around L1370) which had no deadline check. Heavy resume retries
  (Self-QA, audio preprocessor, video composition) then silently exceeded
  the GitHub Actions step hard timeout — on SIGKILL the run could not
  save a checkpoint or mark `pending` tasks, so the workflow saw
  `pending=0, needs_relay=false` and skipped the HF checkpoint upload +
  self-retrigger, forcing a full re-run from scratch
  (observed in run 26018603400 / exp025: Round 0 finished ~250min,
  Resume Round 1 SIGKILLed at ~330min with no relay). The Resume Round
  loop now mirrors the existing watchdog: unfinished retriable tasks are
  marked `pending(error=wall_timeout)`, `_save_progress()` is called, and
  the process exits with `EXIT_CHECKPOINT(42)` so the workflow uploads
  the checkpoint and self-retriggers. Backward compatible — `wall_timeout
  = 0` (no timeout) short-circuits the guard as before.
  (PR #41)

- **batch-run workflow: Step 2a/2b `timeout-minutes` widened 330 → 350.**
  After `wall_timeout` (default 290min) fires, the run still needs time to
  save the progress checkpoint, upload it to HuggingFace, and dispatch
  the relay re-trigger. The previous 330min hard step timeout left only
  ~40min for this handoff, which proved insufficient in practice. The new
  350min ceiling gives a 60min margin while still staying well under the
  6h job-level cap. (PR #41)

- **subprocess_runner: `_AVAILABLE_FILES` hint now actually executed.**
  In `core/subprocess_runner.py::_execute_safely`, the `files_header`
  (`_AVAILABLE_FILES = [...]`) prepended to the generated `code` string was
  never persisted back to the executed script path, so the subprocess ran the
  raw user code without the guarded hint. The header-prepended `code` is now
  written to `code_path` end-to-end. The earlier redundant pre-prepend write
  was removed; the file is written exactly once after the header is applied.

- **llm_client (Anthropic): tolerant content parsing + `finish_reason`
  surfaced.** `core/llm_client.py::AnthropicClient.chat_complete` previously
  assumed `response.content[0].text`, which crashed when the first block was
  a `thinking` or `tool_use` block. The parser now walks all content blocks
  and concatenates only `type == "text"` segments. `response.stop_reason` is
  mapped to an OpenAI-compatible `finish_reason` (`max_tokens` → `length`;
  `end_turn` / `stop_sequence` / `tool_use` passed through) and exposed on
  `_Choice` / `NormalizedResponse`, so the existing
  `finish_reason == "length"` truncation guard in
  `step2_run_inference.py:436` actually fires for Anthropic.

- **step2_run_inference: `qa_failed` is now set on genuine Self-QA
  failures.** Previously, when Self-QA scored `< min_score` and retries were
  exhausted, the best result was returned with `status == "success"`, which
  meant the `RETRIABLE_STATUSES` retry plumbing (resume rounds), the
  `_print_status` `qa_failed` branch, and the summary counters at
  `step2_run_inference.py:1419` / `1448` were all dead code paths.
  `_run_task_with_qa` now sets `best_result["status"] = "qa_failed"` on
  genuine quality failures, re-enabling auto-retry / resume.
  The `undetermined` branch is intentionally left as `success` — it only
  marks QA parse / API failures, not quality failures, and is not a retry
  target.

### Changed

- **`qa_failed` semantics (BREAKING for comparability).** As a consequence
  of the fix above, the dashboard / aggregated metric `qa_failed_count` is
  no longer comparable across the boundary: pre-fix runs report
  `qa_failed_count == 0` (the flag was never set even when QA genuinely
  failed); post-fix runs report the true count. Treat pre/post
  `qa_failed_count` as different metrics.

- **`compact` mode parquet may now contain fewer rows.** When
  `result_collector` is configured in compact mode it filters
  `status == "success"`. Because genuine QA failures now flip to
  `qa_failed`, those rows are excluded from the compact parquet that were
  previously silently retained as `success`. The non-compact / per-task
  JSON output is unaffected and remains the source of truth for QA failure
  counts.

- **`resume_rounds_used` will be non-zero on QA-enabled runs.** The same
  fix re-enables the resume / retry loop for `qa_failed` tasks via
  `RETRIABLE_STATUSES`, so QA-enabled runs that previously reported
  `resume_rounds_used == 0` may now legitimately consume one or more
  resume rounds. Worst-case per-task cost is capped by the existing
  `qa_max_retries` × `resume_rounds` × infra-retry budget.

### Notes

- **Cost guardrail (re-validated post-fix).** Production experiment YAMLs
  (`exp001`–`exp024`) keep worst-case per-task LLM call multiplier at ≤6×
  (infra retries × QA retries × resume rounds, within previous SLOs).
  Smoke YAMLs (`exp997` / `exp998` / `exp999`) sit higher at 12×–16× in the
  worst case, but their `sample_size` of 2–3 tasks bounds total wall-clock
  / spend impact to negligible levels. No YAML changes are required.

