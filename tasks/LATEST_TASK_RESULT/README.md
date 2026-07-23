# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-23
- Status: Typed Azure AI endpoint foundation shipped via PR #134

## Task

- Harden typed direct v1, Foundry project, and authorized legacy endpoint
  contracts plus the standalone route preflight CLI.
- Align workload discovery, identity, credential, fingerprint, lifecycle,
  output-file, and SDK reproducibility contracts with the current runtime.

## Result

- URL parsing now rejects non-ASCII text, C0/C1 controls, CR/LF/TAB, Unicode
  line separators, explicit empty ports, malformed percent sequences,
  lookalikes, and trailing-dot hosts before applying the exact Microsoft
  suffix/path allowlist.
- Strict identity is profile-specific. Direct/project routes bind the active
  direct account, project also binds project account/name, and legacy binds the
  active legacy endpoint through `AZURE_AI_EXPECTED_LEGACY_ACCOUNT` without
  requiring or trusting a separate direct endpoint.
- The current `CodeInterpreterRunner is Azure-only`. A missing main deployment
  follows the runtime's `gpt-4` default; malformed model objects, explicit null
  deployments, and native-provider Code Interpreter fail clearly. Azure
  `audio_analyzer` and `video_analyzer` preprocessors inherit current runtime
  defaults `gpt-audio-1.5` and `gpt-5.2`; other preprocessor types are not route
  workloads. A `model` alias alone does not override the runtime's audio/video
  `deployment` lookup. Native main models can still discover explicitly Azure
  audio/video preprocessors.
- Authentication is `DefaultAzureCredential`-based. Known static Azure keys,
  tokens, client secrets, certificates, usernames, and passwords are rejected
  without echoing values. `AZURE_FEDERATED_TOKEN_FILE` and native
  `OPENAI_API_KEY` remain allowed. Internally owned factory and token-check paths
  recheck the real process environment before credential construction even with
  explicit route settings; injected credentials remain caller-managed.
- Fingerprints now carry a stable contract version and effective token scope in
  addition to endpoint/deployment identity, SDK versions, timeout, retries,
  workload, profile, and legacy API version. Emitted output is endpoint-free,
  redacted provenance; its digest is not a confidentiality boundary and not a
  secret.
- Factory and lease contracts explicitly document synchronous, managed,
  non-thread-safe lifetimes, shared-factory survival, caller-owned injected
  credentials, and rejection of async close implementations.
- `GITHUB_OUTPUT` preserves existing contents/mode, creates new files at mode
  `0600`, rejects directory/FIFO/socket/symlink/missing-ancestor/parent/control
  paths, and fails on a short single `O_APPEND` write.
- Exact local SDK pins now occur once each: `openai==2.46.0`,
  `azure-core==1.41.0`, `azure-identity==1.25.3`, and
  `azure-ai-projects==2.3.0`.
- An offline real-SDK construction smoke created the project and OpenAI clients,
  verified the canonical base URL plus exact `responses.create`, `files.create`,
  `files.delete`, fallback `files.content`, `containers.create`,
  `containers.files.list`, and `containers.files.content.retrieve`
  capabilities, closed both clients, and proved zero token and HTTP send calls
  while leaving the injected credential caller-owned. The current runner uses
  auto-container configuration rather than calling `containers.create`
  directly; that method remains a project-client compatibility gate.
- Runtime and workflow integration remains `NOT WIRED`.
- Raw and serialized `ExperimentConfig` conditions resolve to the same main,
  QA, and audio/video workload identities.

## Verification

- Base identity:
  `origin/main@b82d9fea95fb97a1fcbcea6cb6979d09b031afeb`.
- Detached clean-checkout focused core and CLI contracts: **224 passed in 20.79
  seconds**.
- Exact clean-checkout real-SDK smoke: **1 passed in 1.47 seconds**, with all
  pinned versions and seven capabilities verified and zero token/network calls.
- Detached clean-checkout credential-free backend non-integration suite:
  **2,074 passed, 9 skipped, and 44 integration tests deselected in 126.02
  seconds**.
- All **20** internally owned credential secret cases and the independent
  raw/serialized workload parity test passed before the full suite.
- Ruff reported `All checks passed!` for the four Python implementation/test
  files; `py_compile` completed with no diagnostics.
- `pip check` reported `No broken requirements found.` The four exact SDK pins
  and their package prefixes each occur once.
- `git diff --check` passed, no conflict markers were found, and status contains
  exactly the eight intended paths, including the ignored CLI and BOLT files.
- No token acquisition, network access, Azure/model API call, grading, Hugging
  Face access/write, workflow execution, or paid operation occurred.

## Shipment

- PR #134 squash-merged as
  `fb3b7fe02ad54a3b095ffbea532a7b1703ba065b` on 2026-07-23 from exact reviewed
  head `127c948a9832d156d17b151ffe9cb6f063818f92`.
- The implementation changed exactly eight paths. GitHub attached no Actions
  run, check suite, or check rollup to either SHA because those paths do not
  match an active workflow trigger.
- No manual workflow dispatch, credential injection, token acquisition,
  Azure/model API call, Hugging Face access/write, deployment, or paid action
  was used to replace the path-filtered checks.

## Remaining Work

- No repository implementation work remains for this foundation slice.
- Wire inference, Code Interpreter, narrative, grading, reporting, and workflow
  callers only in a later bounded change with separate local validation.