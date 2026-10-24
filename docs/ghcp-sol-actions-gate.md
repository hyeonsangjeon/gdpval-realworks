# GHCP Sol fixed-five Actions gate (local draft)

Owner decision 2026-10-24 00:01: use one GitHub Actions standard
`ubuntu-24.04` runner job per task. No nested VM or `/dev/kvm` prerequisite.
This draft does not grant push, dispatch, paid inference or grading approval.

## Evidence and authentication audit, 2026-10-24

**Paid execution remains blocked.** At inspected source
`f205207bb73f123ed7ff858e0feefd35d23e53ab` (tree
`942355a97c7c61fbe65aec6f0c5b070e0aeebb90`), the gate has no GHCP/Codex
inference adapter. All three requested properties are **settings only** in
this route, not observations that they took effect. This is a documentation
audit, not evidence that Sol is unavailable or that no supported route exists.
No CLI/session, authentication, model request or test was run for this audit.

### What can be established

The verdicts below apply to this exact GHCP + Codex gate. A documented signal
in another harness does not establish that the gate can collect it.

| Property | Current verdict | Source and remaining evidence boundary |
| --- | --- | --- |
| Actual response model | Settings only (`설정 표시만`) | `batch-runner/ghcp_sol_actions_gate.py:25-31,56-75` copies requested Sol and sets every served value to `not available`. Copilot SDK documents per-call `assistant.usage.model` [G1, G2], a useful observation candidate. A pinned GHCP-to-Codex adapter and evidence that its value comes from the responding service, not the requested model, are still missing. |
| Reasoning Max | Settings only (`설정 표시만`) | `gpt56_sol_ghcp_codex_vm_gate.yaml:16-31` labels `max` as a request. Copilot SDK documents optional per-call `assistant.usage.reasoningEffort` [G1]. Missing effort must remain unknown; reasoning-token counts do not prove a tier. The CLI reference accepts an effort flag but describes `max` in an Anthropic context [G3]; this is not a provider-specific guarantee for GHCP Sol. Do not silently map `xhigh` to Max. |
| Context 1M | Settings only (`설정 표시만`) | The same plan declares a nominal `1000000`, not a verified server allowance. Copilot `session.usage_info.tokenLimit` and Codex `modelContextWindow` expose runtime context-window metadata [G1, G2, L1]. That metadata alone does not prove the GHCP service accepted the requested window or that this workload exercised it. OpenAI's Sol page advertises **1,050,000** context tokens [O1], which is neither the plan's nominal **1,000,000** nor a GHCP entitlement receipt. |

OpenAI documents Sol support for `reasoning.effort=max` [O1], and Codex
documents `model_reasoning_effort`, `model_context_window` and the separate
auto-compaction threshold [O2]. These establish configuration/capability
semantics, not this account's effective GHCP settings. Changing the window
or inspecting token usage would not establish that all history was retained
without compaction.

The installed, repository-pinned `openai-codex` / `openai-codex-cli-bin`
**0.147.0** pair is a different surface from Copilot SDK:

- `openai_codex/client.py:238-272` starts a Codex app-server subprocess and
  exchanges JSON-RPC; it is not a Python HTTP model client.
- `openai_codex/generated/v2_all.py:10241-10271` returns thread configuration
  including `model`, `modelProvider` and `reasoningEffort`. A thread-start
  response is not a provider completion. Its `Turn`/`TurnStartResponse`
  schema at `9643-9695` does not supply the provider response body's model.
- The same file at `3204-3219` names efforts through `xhigh` but accepts
  unknown nonempty enum strings. Parsing `max` therefore does not prove CLI
  or provider support. At `5294-5303` and `8579-8594`, token counts and optional
  `modelContextWindow` remain distinct from an applied-Max/1M receipt.

These installed-file references are **L1**, not executed runtime evidence.
The inspected venv has no `github-copilot-sdk` package. Locally installed
`@github/copilot/package.json:4` reports **1.0.98**, but its `README.md:5`
identifies the Copilot coding-agent harness. `--agent` selects a custom agent
in the current CLI reference [G3]; naming it `codex` would not prove use of
OpenAI's Codex harness. Current web documentation is not a version guarantee
for that installed binary. The separate Foundry native observer is not a
GHCP adapter and is not imported or credited as this gate's proof.

### Fallback prevention and detection

The unchanged plan's `automatic_fallback_allowed: false` and `fallbacks: []`
are declarations, not implemented provider controls. The current Python
entrypoint still refuses paid mode before capture
(`ghcp_sol_actions_gate.py:133-141`).

For a future reviewed adapter, select the exact registered model, never
`auto`; Auto explicitly routes between models [G3, G8]. Keep the GHCP provider
and authenticated identity fixed. Reject alternate providers/BYOK: GitHub
documents that BYOK variables can route model requests elsewhere despite
GitHub authentication [G4]. Do not accept Fast, another model, or an
unreviewed alias as Sol. These are proposed checks, not new runtime code.

Install metadata capture before execution begins, record each call's
model/effort including sub-agent calls, then compare the full observed sequence
with the registration.
`assistant.usage` is ephemeral: ordinary saved session logs/resume do not
recover it [G1, G2]. No actual session log or private transcript was read here.
Retain only allowlisted metadata with call/source bindings; do not publish
raw events, prompts, headers, tool output or credentials. Missing, conflicting
or unbound metadata must stop acceptance and further requests, not authorize
a retry. Detection after a call cannot undo that call's spend.

Codex 0.147.0 also defines `model/rerouted` metadata with source/target model
and thread/turn IDs (`v2_all.py:2436-2451`). Its documented schema reason is
`highRiskCyberActivity`; it is not a universal report of every possible
provider substitution. No inspected contract establishes a universal
server-side no-fallback switch. A missing reroute event or unchanged requested
model is not proof that silent provider fallback cannot occur.

### Authentication drafts, not authorization

**Conditional recommendation: job-scoped `GITHUB_TOKEN`**, only after the
existing repository's organization eligibility, billing identity, policy and
selected runtime support are explicitly established. None was queried here.
If those conditions do not hold, stop for an owner choice; do not move the
repository, change the billing identity, or automatically select another option.

| Draft | Scope and supply | Lifetime and disposal | Exposure and unresolved condition |
| --- | --- | --- | --- |
| **A. Job `GITHUB_TOKEN` (conditionally recommended)** | GitHub documents organization-owned Actions use with `copilot-requests: write` and the organization Copilot CLI billing policy [G5, G6]. The current workflow has only `contents: read`; no permission is changed here. Supply only to the approved runtime, not to model tools. | GitHub issues a token per job; it expires when the job finishes, subject to the hosted-runner maximum lifetime [G7]. Close runtime/credential channels and discard ephemeral runner state. Job-token expiry is not an execution timeout. | No new long-lived secret, but an exposed token can spend against the organization during its validity. Current organization/policy/billing and pinned-runtime eligibility are unverified. The docs' recommendation to use another workflow framework is not adopted. |
| B. Owner fine-grained PAT in a protected Actions environment | Personal-account-owned token with the **Copilot Requests** account permission; no unrelated repository write permissions. A separate checkout credential stays separate. Use an explicitly selected credential channel, such as runtime-only `COPILOT_GITHUB_TOKEN` [G4]. | Set the shortest owner-approved supported expiration. Remove process exposure at exit; revoke the PAT on GitHub after the approved execution window, including cancellation/failure. Removing an Actions secret or a local file does not revoke a copied PAT. | The permission is account-level, not a five-task or model-specific spending cap. Same-user tools, process environments, diagnostics or artifacts can expose it. Protected-environment approval and credential isolation are required; no PAT was read, created or stored. |
| C. Existing approved GitHub App installation token | Organization **Copilot Requests: Read-only** (`organization_copilot_requests: read`), with organization installation/billing approval [G6]. An approved service would supply only the short-lived token, never its signing key, to the runtime. | Installation tokens expire after **one hour** [G6]; revoke the installation token at the end and discard local exposure. App authorization/signing-key revocation is a separate owner action if compromised. No refresh loop is proposed. | Requires an existing approved App/token supplier and matching billing identity, neither established here. GitHub recommends A for Actions. An App signing key would create a larger persistent secret risk; this audit does not authorize creating a broker or App. |

For SDKs that support it, explicit token injection plus
`useLoggedInUser: false` disables credential discovery [G6]; setting that
flag while relying only on environment-token discovery would be incorrect.
Do not reuse a developer login/cache or allow an automatic account fallback.
The inspected local `/usr/local/bin/copilot:32-42` wrapper invokes
`gh auth token` when token variables are absent and can select another binary;
it was **read as code, never executed**. GitHub also documents keychain and
`gh` fallback, and that `/logout` removes local credentials without revoking
them on GitHub [G4].

All options require a fixed reviewed source, no untrusted/fork code in the
credential step, a boundary that keeps tokens out of the model's tools, and
metadata-only output. Step-local environment variables and log masking alone
do not isolate a token from same-user processes. Cleanup needs an expiry or
owner-controlled revocation backstop; a workflow `always()` step alone cannot
guarantee cleanup after runner loss. No option proves model/effort/context or
enforces timeout/tool/turn limits. Those remain independent stop-before-spend
conditions; authentication is not permission to run this pilot.

### Audit sources

Public documentation was fetched on **2026-10-24**, without account access.
The mutable documentation is evidence of its stated interface, not proof
of this project's entitlement or installed-version behavior. Local source and
documentation hashes are retained with this audit's completion record.

- [O1: OpenAI GPT-5.6 Sol model reference](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
- [O2: Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), the official redirect target of `developers.openai.com/codex/config-reference`.
- [G1: Copilot SDK streaming events](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/streaming-events#assistantusage), including `assistant.usage` and `session.usage_info`.
- [G2: Copilot SDK usage and billing](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing#per-call-token-counts).
- [G3: Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference), model/effort flags and custom-agent selection.
- [G4: Copilot CLI authentication](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli), supported credentials, selection order and revocation distinction.
- [G5: Copilot CLI in Actions with GITHUB_TOKEN](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions).
- [G6: Copilot SDK server-to-server authentication](https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/server-to-server-tokens).
- [G7: GITHUB_TOKEN lifecycle](https://docs.github.com/en/actions/concepts/security/github_token).
- [G8: Copilot auto model selection](https://docs.github.com/en/copilot/concepts/models/auto-model-selection).

## Existing path surveyed

| Workflow | Inputs and task layout | Credentials and retained evidence |
| --- | --- | --- |
| `agentic-v2-stage-run.yml` | `stage`, `mode`, `isolation`, `plan`, `run_id`, `resume_from_github_run`, `comparison_reviewed_source_sha`; free planning, paid shard matrix, collection and comparison admission. Planner packs up to 13 tasks/shard, so advance-check five normally share one shard/job. | HF_TOKEN for pinned input fetch, Azure OIDC client/tenant/subscription IDs and Foundry endpoint; GITHUB_TOKEN for resume downloads, paid job permissions include actions read and OIDC. Uploads the full run directory including hidden exec streams, separate host proofs and cost rollup. **Do not reuse its broad artifact upload for private inputs.** |
| `agentic-v2-stage-a-probe.yml` | `mode=dry-run/paid`; free check then one paid probe task, not the five-task run. | HF_TOKEN, Azure OIDC and Foundry endpoint. Paid artifact is metadata-only model-call record, not prompt/reply/reasoning text. Even its free job fetches the dataset; it is not this card's input-free rehearsal. |
| `gpt54-time-budget-first-v2.yml` | `reviewed_source_sha`, `reviewed_source_tree`, `request_sha256`, `request_json`; one source-bound registered task/job, with no replay. | Validates before credentials; HF private input/claim/retention and Azure OIDC separated by phase. Only validated `completion.json` is uploaded; canonical outputs remain private. This is the stronger privacy pattern reused here. |
| `agentic-sandbox-preflight.yml` | Image/SBOM/AppArmor inputs; self-hosted model-free containment checks. | No model credential permitted. Not the selected standard-runner execution route. |

The surveyed V2 workflows contain no explicit `::add-mask::` step.
GitHub's masking of configured secrets is not a privacy boundary for task
wording, reference contents, tool output or generated deliverables. The new
route supplies no secrets, prints only fixed status, reads only the public
score-free catalogue, and uploads exactly one generated `capture.json` per
task. It never uploads a directory, raw stream or file hashes.

This is an additive sibling in the existing `.github/workflows/agentic-v2-*`
path, reusing its plan-to-matrix structure and pinned checkout/Python/artifact
actions. It does **not** invoke the paid V2 conversation runner, Firecracker
boot action, Azure route, or legacy shard/resume logic; those would inherit
unapproved spending, private capture and obsolete VM requirements.

## Fixed cohort and grading contract

`core/execution_envelope_tasks.py::select_advance_check_tasks` derives the five
ordered IDs from `experiments/execution_envelope/gdpval_task_catalog.json`.
`advance_check_plan.yaml` pins the same order and input versions.
`experiments/execution_envelope/gpt56_sol_ghcp_codex_vm_gate.yaml` binds the
GHCP identity, original-input policy, inherited developer instructions and
grader policy. That older inert VM prerequisite contract remains unchanged;
its VM/reset blockers are not assertions about this new Actions target.

The grader template is
`grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml`: rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, prompt v2.2, Sol/Max judge,
one pass/task, grade schema 1.4. The GHCP gate uses only its policy blocks,
**not** its 220-task rerun identity. Five-task inference identity, original
input verification and grader validation remain unresolved. Nothing is graded.

## Local rehearsal and capture

From `batch-runner`, `python3 ghcp_sol_actions_gate.py --matrix` emits the
five-task matrix. For each returned ID, run:

```bash
python3 ghcp_sol_actions_gate.py --dry-run true --task-id TASK_ID \
  --state-root /absolute/fresh/parent/ghcp-sol-gate
python3 -m pytest -q tests/test_ghcp_sol_actions_gate.py
```

The state-root parent must exist. Each task gets a fresh directory; reuse
refuses. `private/` contains empty transcript/tool-call/command streams, empty
input/output hash arrays, a dry-run exit record and an empty `files/` directory.
These are path placeholders, **not** real input staging or transcript evidence.
Only `capture.json` is artifact-eligible; it contains relative logical paths,
requested settings, actual Python/OS versions and explicit unavailable CLI/
served values. Local execution does not prove the requested hosted image ran.

Proposed paid caps are 1200 seconds/task (the V2 stage cap), 64 model turns/task
(draft choice), zero retries; neither approval nor live enforcement is claimed.
The dry-run workflow enforces 60 seconds/process and five minutes/job with
zero model turns. Unknown usage/cost/grade stay null, never inferred as zero.
Both planner and task jobs independently reject every `dry_run` value except
the exact string `true` before checkout. The Python entrypoint separately
rejects false or malformed values before catalogue reads or capture writes.
Local tests execute both shell guards with true, false, missing/empty,
case-changed, numeric and whitespace-bearing values; they do not dispatch
Actions or prove hosted behavior.

## Questions blocking paid execution

- How are scoped GHCP/Copilot credentials supplied, kept outside model tools,
  and disposed of on standard Actions runners? Is this unattended use supported?
- Which supported route actually selects the Codex agent harness, pinned CLI/
  SDK versions, Sol model, Max effort and 1M context without fallback? What
  independent served metadata proves each rather than repeating requested values?
- How are original prompts/references verified and staged privately, and raw
  transcript/tool/file captures retained privately without leaking in logs,
  artifacts, action diagnostics, credentials or caches?
- What network/tool permissions, budget/usage policy, paid timeout/turn/tool/
  token caps, cancellation handling and no-retry admission are approved?
- What five-task inference/grader identity, judge validation, repeat/variance
  plan and pass/fail criteria govern the decision? No quality result follows
  from this wiring rehearsal or from these five cases alone.
- Who reviews the exact source and authorizes push, hosted dry-run dispatch,
  and separately paid inference/grading? All remain unapproved on this card.
