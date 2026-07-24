# BOLT: Typed Azure AI Step 2 Wiring

- Date: 2026-07-23
- Status: `SHIPPED`
- Base: `origin/main@41f47b1934baaaa7ad0fabb26041ea695b90f104`
- Execution boundary: model-free, local-only, offline, no credentials

## Objective

Wire the existing typed Azure AI foundation into Step 2 behind the nonempty
`AZURE_AI_ROUTE_PROFILE` opt-in while preserving the profile-absent legacy
runtime and output shape.

## Hypothesis

A preflight-before-factory boundary, one explicit runtime resource owner, and
an exception-redacting proxy around the verified typed MAIN client can keep
provider failures endpoint/deployment-free without erasing ordinary local
runner diagnostics or changing existing workflows.

## Check

Run the bounded Step 2 wiring tests together with the existing relay,
corruption, preprocessor, agentic, client, executor, and reference-integrity
regressions. Then run Ruff, `py_compile`, the BOLT assertions, and
`git diff --check` with credential environment variables removed.

## Scope

- Opt-in typed Step 2 preflight and client construction.
- Exact canonical deployment binding for typed main, Self-QA, Code
  Interpreter, and recognized Azure audio/video preprocessor calls.
- Typed MAIN provider exception redaction at nested SDK attribute/call
  boundaries, with unchanged native and local failure detail.
- Role-aware typed runtime cleanup redaction with unchanged executor exception
  identity and cleanup ordering.
- Code Interpreter provider-call proxying with precise preservation of local
  prompt, file-structure, and verified-reference errors.
- Direct-object typed Self-QA parsing and exact result structure validation,
  with legacy repair and loose parsing unchanged.
- Exact executor, managed-client, and shared-factory cleanup ownership.
- Typed Azure audio/video preprocessor leases and route observations.
- Strict route records in incremental progress and final result identity.
- Model-free local regression coverage.

## Review Disposition

Eight valid follow-up findings were repaired locally:

1. Step 2 owns and verifies the raw typed MAIN `ManagedAzureAIClient`, then
   passes a non-owning nested callable proxy to `TaskExecutor` and legacy direct
   completion. Attribute and call failures become a new class-only safe error
   with no retained provider exception, cause, or message; successful calls
   return the raw SDK response. Self-QA retains its distinct verified raw
   wrapper for the private temperature-compatibility check. Code Interpreter
   and preprocessors retain their verified raw wrappers and local opt-in
   provider catches.
2. Step 2 no longer replaces an entire typed failure result, and
   `TaskExecutor.execute` always retains `Executor error (<mode>): <detail>` for
   unrelated local exceptions. Normal result error, content, deliverable, and
   observability fields survive for typed MAIN and native MAIN plus Azure PP.
    Executor-constructor redaction now uses `typed_azure_main`, meaning typed
    routing is active and MAIN is Azure/Azure OpenAI. Native MAIN plus Azure PP
    therefore retains the existing full local constructor detail while the
    shared factory still closes; typed Azure MAIN, including Code Interpreter,
    remains class-only.
3. After JSON extraction, typed Self-QA accepts only a dict with the exact
  `passed`, `score`, `issues`, and `suggestion` keys and exact bounded field
  types. Structural rejection uses the same generic class-qualified parse
  result, with no raw response, output, or parse detail in stdout. The legacy
  loose structure/default behavior remains unchanged.
4. `_Step2RuntimeResources.close` associates each resource with its executor,
  managed-client, or factory role while retaining executor-first, reverse
  managed-client, then factory order; identity deduplication; idempotency; all
  close attempts; and first-failure precedence. Executor cleanup failures
  remain the exact original local exception. Managed-client and factory
  `BaseException` failures are replaced after the catch context by new stable
  errors such as `typed Azure AI managed client cleanup failed (OSError)` and
  `typed Azure AI factory cleanup failed (LookupError)`, without the original
  message, cause, context, or traceback. A sanitized first cleanup failure
  remains primary and retains an active body exception only as its explicit
  cause.
5. `CodeInterpreterRunner` validates the raw active client before applying a
  private non-owning nested call proxy when `redact_provider_errors=True`.
  Client attribute and invocation failures become a fresh
  `Code Interpreter provider error (<UnderlyingClass>)` with no retained raw
  exception chain, while successful SDK calls return their raw result.
  Injected clients remain caller-owned; owned close targets the raw client
  exactly once. The outer `run` catch now preserves `str(exc)`, so local
  `build_file_structure_info`, `render_prompt`, and
  `open_verified_reference` details remain exact while response, upload,
  delete, download, and container provider failures remain class-only.
6. Typed Self-QA now parses only one direct JSON object with `json.loads`
   before applying the exact schema checks. Truncation repair, fenced-block
   extraction, and regex fallback remain legacy-only, so malformed text cannot
   be transformed into a trusted typed QA result containing provider details.
7. Typed preflight, factory, main, Self-QA, Code Interpreter, and executor
   initialization handlers retain only the exception class name, leave the
   active exception scope, and only then terminate. The resulting `SystemExit`
   has no implicit raw provider exception context while legacy and native
   initialization diagnostics remain unchanged.
8. Typed Self-QA uses an `object_pairs_hook` that rejects duplicate JSON
   members before exact-schema validation. Conflicting last-wins members can no
   longer change the typed QA gate; legacy JSON repair behavior remains
   unchanged.

The review's normal model/deployment metadata observation is not a defect.
Existing configured model display, final top-level/per-task `model`, and
preprocessor `model` observations remain intentionally visible for schema and
consumer compatibility. They are not route provenance. `azure_ai_routes` is
the route-provenance surface and remains endpoint- and deployment-free.
Provider exception payloads and typed malformed Self-QA payloads omit raw
endpoint/account/deployment text.

Planned routes are endpoint-free capability records, not instantiated clients
or endpoint disclosures. Every instantiated typed client is runtime-verified
against exactly one planned capability record before it is used.

## Non-Goals

- Step 2 workflow wiring or workflow edits.
- External typed resume checkpoints or positive wall-timeout relay runs.
- Hardened or agentic typed execution.
- Foundation, adapter, grading, reporting, or publication changes.
- API, token, network, Azure/model, Hugging Face, workflow, or paid actions.

Typed routing is explicitly opt-in. Existing workflows do not set
`AZURE_AI_ROUTE_PROFILE`, so Step 2 workflow execution remains not wired and
legacy behavior remains active. Internal resume rounds in one process remain
supported; external resume and wall-timeout are intentionally unsupported.

## Evidence

| Check | Result |
|---|---|
| Original earlier requested suite | Its command included nonexistent `tests/test_audio_analyzer.py`; pytest exited `4` during collection with `0 collected`. This was a failure, not a successful suite. |
| Earlier adjusted existing-path suite | The command was adjusted to existing test paths and produced `458 passed, 6 deselected`. This is distinct from the failed original command. |
| Previous provider-boundary focused suite | `188 passed`, zero failures/warnings/deselections in `1.86s`; this was not the original requested suite. |
| Previous provider-boundary focused rerun | `188 passed`, zero failures/warnings/deselections in `1.87s`; this was not the original requested suite. |
| Previous immediate repair suite (exact command and scope) | From `batch-runner`: `env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 /tmp/gdpval-readme-contract-final-venv/bin/python -m pytest -q tests/test_azure_ai_step2_wiring.py tests/test_executor.py tests/test_code_interpreter.py tests/test_preprocessor_observability.py tests/test_silent_corruption_fixes.py`; exit `0`, `203 passed`, zero failures/warnings/deselections in `1.94s`. |
| Previous concrete repair suite (exact requested command and scope) | From `batch-runner`: `env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 /tmp/gdpval-readme-contract-final-venv/bin/python -m pytest -q tests/test_azure_ai_step2_wiring.py tests/test_code_interpreter.py tests/test_executor.py tests/test_preprocessor_observability.py tests/test_silent_corruption_fixes.py`; exit `0`, `214 passed`, zero failures/warnings/deselections in `2.01s`. |
| Previous typed QA regression | From `batch-runner`, the credential-free wiring test filtered with `-k qa`; exit `0`, `20 passed, 71 deselected` in `0.95s`. This includes the legacy regex-fallback bypass reproduction. |
| Previous focused suite | The five-file focused command below exited `0` with `215 passed`, zero failures in `2.03s`. |
| Latest init-context and QA regression | From `batch-runner`, the credential-free wiring test filtered with `-k 'typed_init_errors or invalid_route_configuration or qa'`; exit `0`, `27 passed, 65 deselected` in `0.96s`. This includes raw `SystemExit` context and duplicate-member reproductions. |
| Latest focused suite (exact command and scope) | From `batch-runner`: `env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 /tmp/gdpval-readme-contract-final-venv/bin/python -m pytest -q tests/test_azure_ai_step2_wiring.py tests/test_code_interpreter.py tests/test_executor.py tests/test_preprocessor_observability.py tests/test_silent_corruption_fixes.py`; exit `0`, `216 passed`, zero failures in `2.20s`. |
| Complete credential-free backend | From `batch-runner`, isolated `python -m pytest -q` used the repository's `not integration` marker; exit `0`, `2,211 passed, 9 host-dependent skipped, 44 integration deselected` in `134.81s`. |
| Clean detached focused suite | Exact reviewed commit `6ee41d2a89ff796dc06c238892fe5f78ec1f29a1`; `216 passed` in `2.16s`. |
| Clean detached complete backend | From the detached checkout's `batch-runner` directory, `2,214 passed, 6 host-dependent skipped, 44 integration deselected` in `137.30s`, exit `0`. An earlier repository-root invocation was invalid because relative-path tests require the `batch-runner` working directory; it is excluded from the gate. |
| Independent release-gate review | `MANDATORY_FINDINGS: 0` after all eight follow-up reproductions were fixed and revalidated. |
| Previous Ruff | `step2_run_inference.py` and `tests/test_azure_ai_step2_wiring.py`, `All checks passed!`, exit `0` in `0.0304s` |
| Final Ruff | `step2_run_inference.py`, `core/code_interpreter.py`, `tests/test_azure_ai_step2_wiring.py`, and `tests/test_code_interpreter.py`; `All checks passed!`, exit `0` in `0.01s` |
| Previous `py_compile` | `step2_run_inference.py` and `tests/test_azure_ai_step2_wiring.py`, exit `0`, no diagnostics in `0.1308s` |
| Final `py_compile` | The four final-repair Python files, with bytecode routed outside the worktree; exit `0`, no diagnostics in `0.14s` |
| Latest Ruff | `step2_run_inference.py` and `tests/test_azure_ai_step2_wiring.py`; `All checks passed!`, exit `0` |
| Latest `py_compile` | `step2_run_inference.py` and `tests/test_azure_ai_step2_wiring.py`; exit `0`, no diagnostics |
| VS Code diagnostics | All four final-repair Python files reported `No errors found` |
| Final diff whitespace | Latest tracked `git diff --check` exit `0`; the untracked wiring-test no-index check emitted no whitespace diagnostics and exited `1` only because the file differs from `/dev/null` |
| Latest BOLT assertions | `13/13` date, status, base, disposition, prior-evidence, latest-evidence, and local-only assertions passed |
| Remote or paid execution | None; no API, credential, token, network, Azure/model, Hugging Face, workflow, or paid action |

The previous and latest repair pytest commands used credential and typed
route-profile environment variables removed via `env -i`. The latest command
used the exact requested test path order and covered Step 2 wiring, Code
Interpreter, executor, preprocessor observability, and silent corruption.
Pre-existing typed-wiring changes outside this repair's five-file allowlist
were not edited.

## Shipment

- PR #138 squash-merged as
  `4654b4316ecef30f19da55dd513b35d625f7d30d` on 2026-07-24 from exact reviewed
  head `6ee41d2a89ff796dc06c238892fe5f78ec1f29a1`.
- The implementation changed exactly 11 paths. GitHub attached no check run,
  check suite, commit status, or PR check rollup to the reviewed or merge SHA
  because the paths do not match an active workflow trigger.
- No workflow was manually dispatched to compensate. No credential, token,
  Azure/model API, grading, Hugging Face, deployment, or paid action occurred.

## Decision

`SHIPPED`. Typed Step 2 is available only through the explicit profile opt-in
and is not enabled by an existing workflow. External typed resume checkpoints,
positive wall-timeout relay runs, and hardened/agentic typed modes remain
unsupported. The original command containing a nonexistent audio test path
remains recorded as an exit-4 failure; the valid local and clean detached
backend gates both have zero failures. No remote or paid runtime action was
performed.