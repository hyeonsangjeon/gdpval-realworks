# BOLT: Typed Azure AI Runtime Adapters

- Date: 2026-07-23
- Status: `LOCALLY_VERIFIED`
- Base: `origin/main@9943995623e7156f6acdf921e181af4208be6165`
- Execution boundary: model-free, local-only, offline, no credentials

## Objective

Add bounded, explicit runtime adapters over the typed Azure AI endpoint
foundation without changing any active Step 2 or workflow caller. The adapters
make client, lease, factory, runner, and executor ownership deterministic while
preserving legacy client construction and reference-file integrity behavior.

## Hypothesis

The foundation factory already owns route selection, capability validation,
runtime fingerprints, and lease cleanup. A synchronous delegating wrapper plus
an explicit Code Interpreter injection path can expose that contract to runtime
objects without changing legacy `create_client` or `create_provider_client`
behavior and without wiring the adapter into active inference.

## Discriminating Check

Model-free tests must prove owned and shared factory boundaries, exact Code
Interpreter capabilities, environment-free injected construction, provider
input-file cleanup, close idempotency, post-close API exclusion, executor-only
runner delegation, and unchanged legacy provider returns. The focused suite
must also retain the foundation tests and existing reference upload tests.

## Scope

- Add `ManagedAzureAIClient` and `create_typed_azure_client` in
  `batch-runner/core/llm_client.py`.
- Add caller-owned client injection and explicit synchronous lifecycle support
  to `CodeInterpreterRunner`.
- Add Code Interpreter client forwarding and runner lifecycle support to
  `TaskExecutor`.
- Add model-free unit coverage in the three corresponding test modules.
- Keep the foundation wording contract on its immutable BOLT and changelog
  entry rather than pinning the rolling latest-task record to an older task.
- Record local-only evidence in this BOLT, `CHANGELOG.md`, and the rolling
  latest-task result.

## Fixed Lifecycle Contracts

- `ManagedAzureAIClient` uses one private open-state guard for `client`,
  `route`, `runtime_fingerprint`, delegated attributes, and context entry.
  Every guarded access after close raises the same `RuntimeError` before an
  underlying API can be called, while close remains idempotent; the raw
  `_lease` remains private.
- An owned typed-client factory that closes successfully after create failure
  preserves the exact creation exception. If factory close also fails, the
  exact close exception is primary with the creation exception as
  `__cause__`. Shared factories are never adapter-closed.
- Injected Code Interpreter clients remain caller-owned across capability and
  prompt failures. Internally constructed clients and credentials share one
  outer initialization cleanup boundary covering prompt load and token-limit
  assignment; cleanup failure is primary with initialization retained as its
  cause.
- API-key fallback closes and releases a failed OIDC credential before key
  client construction, does not echo the raw OIDC error, and preserves cleanup
  failure chaining without double close.
- Synchronous resource cleanup rejects async close functions while continuing
  to later owners, closes returned coroutines without unawaited warnings,
  retains the first close failure, and deduplicates identical resources.
- `TaskExecutor` adapter behavior remains unchanged.

## Non-Goals

- The adapters are **NOT WIRED** into Step 2 or workflows.
- No active inference, grading, reporting, deployment, or workflow behavior is
  changed.
- No credential or token acquisition, network request, Azure/model API call,
  Hugging Face access, workflow run, or paid action is permitted or performed.
- No foundation route contract, experiment configuration, generated data,
  Step 2 orchestration, or workflow is changed in this slice.

## Evidence

| Check | Result |
|---|---|
| LLM adapter focused pytest | `29 passed, 6 deselected in 0.73s` |
| Code Interpreter focused pytest | `29 passed in 0.92s` |
| Clean-checkout focused pytest | `279 passed, 6 deselected` with pinned local SDK versions |
| Clean-checkout backend non-integration | Zero failures; `2,105-2,108 passed`, `6-9` host-dependent skips, `44` deselected across repeat runs |
| Ruff | Seven changed Python files, `All checks passed!` |
| `py_compile` | Seven changed Python files, no diagnostics |
| Diff and scope | `git diff --check` clean; seven Python changes plus this BOLT and two completion records; no conflict markers or committed secrets |
| Remote or paid execution | None; no token, network, Azure/model API, HF, workflow, or paid action |

## Decision

`LOCALLY_VERIFIED`. The explicit adapters exist only as opt-in construction
and injection surfaces. They are not connected to Step 2 or any workflow, so
there is no active runtime behavior change. The repository ignores `tasks/**`
by default, so this requested BOLT remains an unstaged ignored file for the
orchestrator to include explicitly; no Git staging operation was performed.