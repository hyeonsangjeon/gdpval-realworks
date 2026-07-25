# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-25
- Status: Foundry route migration implementation and approval are pushed in
  PR #140. Its first free `validate` run exposed an eager Azure SDK import in
  the Node-only aggregate job; the lazy-import fix is locally validated, while
  fix push, CI rerun, merge, and separately approved remote paid/write
  validation remain pending

## Task

- Complete the Microsoft Foundry migration on top of the already shipped typed
  endpoint foundation, runtime adapters, and Step 2 wiring from PRs #134-#139.
- Use direct `/openai/v1/` routes for inference, narrative, and grading; reserve
  the project endpoint for Code Interpreter; keep dated Azure OpenAI as an
  explicit rollback-only profile.
- Enforce OIDC/`DefaultAzureCredential`, independent expected Azure identities,
  route-specific token audiences, endpoint-free provenance, and deterministic
  client ownership across workflows and consumers.
- Bind the exact prepared, result, task, route, and runtime identity through
  relay checkpoints, reports, HF publication, grading cache/resume, and
  diagnostic outputs.

## Result

- Rebased onto `origin/main@bfa2bb70a063ba621f95929c69b7218e4dce9563`
  and preserved the shipped BOLT documents plus the 2,567-line Step 2 wiring
  regression layer unchanged except for intentional final-contract assertions.
- Batch and grading workflows now preflight every config-derived Azure workload
  before remote writes. Direct/project routes acquire
  `https://ai.azure.com/.default`; only an explicitly authorized legacy route
  acquires the Cognitive Services audience.
- Added independent expected client, tenant, and subscription variables.
  Configured secrets are checked before login; the active subscription/tenant
  and Azure AI JWT `tid`, `azp`/`appid`, exact `aud`, `nbf`, and `exp` claims
  are checked after login without printing IDs or tokens.
- Strict endpoint identity is profile-specific, including
  `AZURE_AI_EXPECTED_LEGACY_ACCOUNT` for rollback-only dated endpoints.
- Code Interpreter is Azure project-route and injected-client only. Untyped
  endpoint overrides, static API keys, and internal credential/client fallback
  paths are removed; the Step 2 runtime owner closes the executor, provider
  clients, managed clients, project owners, and shared factory exactly once.
  Runtime mode selection, route selection, and restored-route validation reject
  missing, direct, and legacy Code Interpreter profiles before any client is
  constructed.
- Step 2 verifies every managed main, Self-QA, Code Interpreter, and Azure
  audio/video preprocessor client against the exact planned workload,
  deployment, profile, endpoint kind, and runtime fingerprint before use.
- Typed relay/wall-timeout checkpoints recompute and bind exact route records.
  One shared versioned per-status result validator rejects unknown statuses,
  missing terminal fields, output-free successes, and noncanonical deliverable
  paths at local save, local restore, relay status, and relay upload boundaries.
- Reserved Azure hardened/agentic runs require a typed route profile. Their
  route plan is computed model-free, while credential and managed-client
  construction remain deferred until after signed authorization and budget
  reservation. The runner owns and closes the deferred client, including a
  factory candidate that fails capability validation with `Exception` or
  `SystemExit` before ownership transfer.
- The common hardened baseline closes its deferred provider client after every
  task and any residual client during idempotent runner shutdown. Normal,
  failed, consecutive, and cleanup-failure paths close exactly once; cleanup
  failures retain only `provider_cleanup_failed:<Type>`.
- Provider failures are projected to stable endpoint- and message-free public
  identities before checkpoint and final-result fingerprinting. Raw provider
  URLs do not enter relay checkpoints, public self-reports, final Step 2
  artifacts, v1 grade diagnostics, audio preparation/dispatch errors, or
  agentic cleanup errors.
- Step 6 makes only its primary `gpt-5.4-pro` narrative calls; any setup, call,
  parse, or route-validation failure immediately emits a model-free report.
  The unused experiment-model fallback path and its misleading cost contract
  were removed. Invalid, partial, empty, or whitespace-only first-call fields
  stop the second paid call.
- Main, audio, and vision provider failures plus local tool exceptions are
  projected to class-only stable identities before logs or grade diagnostics.
  Deferred agentic-client cleanup clears the owned reference in `finally` and
  exposes no raw exception cause or context if provider close fails.
- Step 8 binds cache, resume, every partial/final/diagnostic payload, and the
  constructed grader to the exact non-null primary grader route fingerprint;
  matching a tier or perception route is insufficient. v1 batch errors and
  init/cleanup failures are class-only, owned references clear on close failure,
  and durable exit codes 0, 6, and 7 survive cleanup errors. A shared validator
  enforces schema plus primary-route equality in Step 8 and both workflow
  commit gates before and after rebase.
- Perception-note skill discovery ignores generated hidden and `__pycache__`
  directories, so compile validation cannot perturb frontend aggregation.
- `inference_provenance.json` is mandatory for publishable grading, participates
  in the HF CAS plan/receipt/finality tree, and binds exact prepared fingerprint,
  ordered tasks, execution mode, and Azure routes. Schema v2 rejects route-less
  or non-project Code Interpreter provenance throughout formatting, download,
  bootstrap, and publication. Missing provenance is accepted only through an
  explicit non-publishable legacy-analysis override.
- Relay cleanup finality revalidates the exact cleanup child against the full
  publication plan, including optional README bytes, not only managed data and
  deliverable paths.
- Any explicit `--tasks` or positive `--limit` grading run uses
  `run_status: diagnostic` and a full ordered-task-hash path, even when it
  selects every source task. Nested grade/analysis paths propagate through
  exact workflow outputs, commits, and artifacts.
- Cost sweeps remove archived endpoint fields, validate against the typed
  config, hash repository-contained generated configs with symlink/outside
  guards, and consume only Step 8's exact private `GITHUB_OUTPUT` path.
- English/Korean onboarding documents the strict OIDC identities, direct,
  project, and rollback-only routes, token audiences, provenance, and
  diagnostic grading behavior.

## Verification

- Base: `origin/main@bfa2bb70a063ba621f95929c69b7218e4dce9563`.
- Complete backend non-integration suite: **2,328 passed, 6 skipped,
  44 integration tests deselected, 0 failed**.
- Azure foundation and route-preflight regression: **229 passed, 0 failed**.
- The exact failed CI command, `npm run test:aggregate`, now passes **89/89**;
  a fresh subprocess explicitly blocks both `azure` and `openai` imports while
  model-free route planning succeeds.
- Final hardened lifecycle matrix: **172 passed, 0 failed**.
- Final Code Interpreter, provenance, publication, grading schema, and workflow
  follow-up matrix: **762 passed, 0 failed**; the complete suite above includes
  the same fixes.
- Final publication/narrative matrix: **157 passed, 0 failed**.
- Frontend/data contracts: **89 passed, 0 failed**.
- Root model-free cost-sweep and perception-probe tests: **16 passed**.
- Executable onboarding contract: **9 passed, 0 failed**.
- Production TypeScript/Vite build passed; runtime, integrity, perception, and
  success browser suites all passed against the production build.
- Ruff and `py_compile` passed for all **67 changed Python files**.
- `actionlint` passed separately for `batch-run.yml` and `grade-run.yml`;
  `bash -n` passed for `step7_upload_hf.sh`.
- Mandatory workflow/publication/security review returned **GO**. Subsequent
  exact-tree review found six route, checkpoint, grading identity/redaction,
  agentic acquisition, and record gaps plus one token-claim advisory. Every
  finding was reproduced and repaired; its re-review found two follow-up mode
  and shared-validation gaps, which were also repaired and covered before the
  final full-suite run. A later re-review found full-plan cleanup and empty
  narrative gaps; both were repaired and covered. The final independent
  re-review found one hardened deferred-client lifecycle leak; it was
  reproduced, repaired, and covered before the final full-suite run. Exact
  clean-tree head `c396ab5f5a4b1c9b07fabaac894642a41074c185` received final
  independent **APPROVE** with no remaining blocker, major, or minor finding.
- `git diff --check` passed. The latest-main candidate spans **97 files**.
- No workflow dispatch, credential or token acquisition, Azure/model API call,
  grading run, Hugging Face write, network checkpoint write, deployment, or
  paid execution occurred.

## Remaining Work

- Commit and push the lazy SDK import fix to PR #140, wait for its free
  `validate` check, and merge only if the exact updated head passes.
- Configure the independent OIDC expected-ID variables and expected
  direct/project account/project-name variables in repository settings.
  Configure `AZURE_AI_EXPECTED_LEGACY_ACCOUNT` only for an explicitly approved
  rollback exercise.
- Run a separately approved real Foundry route/token smoke with artifact-level
  acceptance before any paid batch or grading execution. Required deployment
  aliases, expected identities, and complete audio coverage are not currently
  available in one verified Azure account, so no values were guessed.