# BOLT: Typed Azure AI Endpoint Contracts

- Date: 2026-07-23
- Status: `LOCALLY_VERIFIED`
- Base: `origin/main@b82d9fea95fb97a1fcbcea6cb6979d09b031afeb`
- Execution boundary: model-free, local-only, offline, no credentials

## Objective

Establish a bounded foundation for typed Microsoft Foundry and Azure OpenAI
routes. The foundation validates exact endpoint shapes, discovers every Azure
deployment a condition can call, constructs synchronous clients, and exposes a
standalone preflight without changing active runtime or workflow callers.

## Contract

- URL classification rejects non-ASCII text, C0/C1 controls, CR/LF/TAB,
  Unicode line separators, explicit empty or non-443 ports, malformed percent
  sequences, host lookalikes, and trailing-dot hosts before accepting the exact
  Microsoft suffix/path allowlist.
- Strict identity is profile-specific. Direct and project profiles verify the
  active direct account; project additionally verifies project account/name;
  legacy verifies only the active legacy endpoint through
  `AZURE_AI_EXPECTED_LEGACY_ACCOUNT` and does not require or trust a direct
  endpoint.
- The current `CodeInterpreterRunner is Azure-only`. A missing main deployment
  follows `ExperimentConfig`'s `gpt-4` default; malformed model objects,
  explicit null deployments, and native-provider Code Interpreter fail. Azure
  audio and video preprocessors default to `gpt-audio-1.5` and `gpt-5.2`;
  preprocessor types that do not invoke a model are not route workloads. The
  runtime reads only `deployment` for audio/video, so a `model` alias alone does
  not override those defaults and an explicit null deployment fails.
- Authentication is `DefaultAzureCredential`-based. Known static Azure key,
  token, client-secret, certificate, username, and password environment
  variables fail without value echo. `AZURE_FEDERATED_TOKEN_FILE` and the
  native-provider `OPENAI_API_KEY` remain allowed. Internally owned factory and
  token-verification paths recheck the real process environment before creating
  a credential even when route settings were supplied explicitly; injected
  credentials remain caller-managed.
- The versioned fingerprint binds effective token scope, endpoint/deployment
  identity, SDK versions, timeout, retry setting, workload, profile, and legacy
  API version. Emitted records are endpoint-free, redacted provenance. The
  digest is not a confidentiality boundary and not a secret.
- Factory and lease lifetimes are synchronous, explicit, and not thread-safe.
  Closing or failing a lease does not close the shared factory or an injected
  caller-owned credential; async close implementations fail explicitly.
- `GITHUB_OUTPUT` accepts only a regular non-symlink target beneath regular
  non-symlink ancestors. Existing content and mode are preserved, new files are
  mode `0600`, and one `O_APPEND` write must write the complete record.

## SDK Contract

The locally verified exact set occurs once each in `requirements.txt`:

- `openai==2.46.0`
- `azure-core==1.41.0`
- `azure-identity==1.25.3`
- `azure-ai-projects==2.3.0`

An offline real-SDK construction smoke created `AIProjectClient` with a
canonical project endpoint, called `get_openai_client(timeout=480,
max_retries=0)`, verified the expected `/openai/v1/` base URL and the exact
`responses.create`, `files.create`, `files.delete`, fallback `files.content`,
`containers.create`, `containers.files.list`, and
`containers.files.content.retrieve` capabilities, then closed both SDK clients.
The current runner uses auto-container configuration rather than calling
`containers.create` directly; that method is a project-client compatibility
gate. Instrumented credential and HTTP send paths remained at zero; the injected
credential remained caller-owned.

## Evidence

| Check | Result |
|---|---|
| Clean-checkout focused pytest | `224 passed in 20.79s` |
| Clean-checkout SDK smoke | `1 passed in 1.47s`; exact versions/capabilities, zero token/network |
| Clean-checkout backend non-integration | `2,074 passed, 9 skipped, 44 deselected in 126.02s` |
| Credential and field parity | 20 owned-secret cases plus raw/serialized workload parity passed |
| Ruff | Four Python files, `All checks passed!` |
| `py_compile` | Four Python files, no diagnostics |
| `pip check` | `No broken requirements found.` |
| Exact SDK pins | Each exact pin and package prefix occurs once |
| Diff and scope | `git diff --check` clean; zero conflict markers; exactly eight intended status paths |
| Remote or paid execution | No token, network, Azure/model API, HF, workflow, or paid action |

## Decision

`LOCALLY_VERIFIED`. Runtime and workflow integration remains `NOT WIRED`.
Inference, Code Interpreter, grading, reporting, and workflow callers are
unchanged. No token acquisition, network request, Azure/model API operation,
Hugging Face access, workflow run, or paid action occurred.