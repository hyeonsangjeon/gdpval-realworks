# Latest task result

## GHCP Sol gate: model evidence and authentication audit

Scope: the leader's **2026-10-24 18:45** documentation-only order on
`leader/ghcp-sol-gate-actions-20261024`, in
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`.
The starting worktree was clean at audited HEAD
`f205207bb73f123ed7ff858e0feefd35d23e53ab`, tree
`942355a97c7c61fbe65aec6f0c5b070e0aeebb90`.
Only `docs/ghcp-sol-actions-gate.md`, this record and `CHANGELOG.md` changed.

### Current result

**Do not proceed to paid execution.** Actual response model, Max effort and
1M context are all **settings only** in the current GHCP + Codex route.
The [audit memo](../../docs/ghcp-sol-actions-gate.md#evidence-and-authentication-audit-2026-10-24)
records source locations, the evidence candidates and their limits:

- Copilot SDK documents per-call `assistant.usage.model` and optional
  `reasoningEffort`, but no pinned adapter binds those signals to this gate's
  Codex harness. Copilot CLI custom-agent selection is not proof of that harness.
- Runtime context-window metadata and OpenAI's advertised **1,050,000**-token
  Sol window do not establish this GHCP request's nominal **1,000,000**-token
  allowance. Missing evidence remains unknown; this is not model-unavailability
  evidence. A Python enum accepting `max` is not an applied-Max receipt.
- Exact model selection, no Auto/BYOK/account fallback, per-call comparisons
  and reroute detection are prospective checks. No inspected contract proves
  universal server-side fallback prevention; detection cannot undo spend.
- Three authentication drafts cover scope, lifetime, disposal and exposure:
  conditionally recommended job-scoped `GITHUB_TOKEN`; owner fine-grained PAT;
  or an existing approved App's **one-hour** installation token. The first
  requires organization/policy/billing and selected-runtime eligibility that
  were not queried. None changes permissions or grants launch authority.

The local Copilot wrapper was inspected as source only: it can invoke
`gh auth token` and choose another binary. It was not executed. No credentials,
credential stores, actual session logs or private transcripts were read.

### Verification and retained evidence

This step uses public-document/source inspection and documentation-only
diff, hash and editorial checks. **No pytest, collection or old proof replay**
was performed. Public documentation was fetched without account access;
examples were not executed. The installed Codex SDK/CLI pair remains **0.147.0**.
Installed Copilot package metadata says **1.0.98**, not a tested runtime binding.

The documentation scope/whitespace checks passed, as did the memo and LATEST
literal checks. The full CHANGELOG literal scan returned exit **3** at the
verifier's safe complexity limit; its log is preserved. Checking only the
changed CHANGELOG passage then passed with exit **0**, without changing the
verifier or replaying the completed checks. These are editorial checks and
same-session source review, not independent review or runtime tests.

Evidence directory: `/ai-work/copilot/_tmp/ghcp-sol-evidence-audit.Rqg0rU/`.
It retains public documentation snapshots, their byte counts/SHA-256 values,
original/structured record checkpoints and the documentation check report.
The prior result's unchanged copy is `latest.before.md`, SHA-256
`ac1da4f1ad43988f428da0f6a407a12cdbe9a73ae8f0d5e0ca1d9f9f4627e9ad`.
The same detailed record remains in local Git at
`f205207bb73f123ed7ff858e0feefd35d23e53ab:tasks/LATEST_TASK_RESULT/README.md`;
no hosted availability is asserted for this unpushed commit.

Historical tests remain separate, not new audit results: at tested source
`4e61a4bb20de67995d0684e051f1d3416eacea69`, the partition check reported
**1 passed in 22.43s**, core **3 failed, 13,373 passed, 57 skipped,
46 deselected, 1 warning in 3250.97s**, and script tests **186 passed in 46.50s**.
The same three failures reproduced at branch point
`6efe99cbd40bb839037e7a20711a734e0a4ce002` (**3 failed in 5.95s**): inherited
`GH_TOKEN` presence and two missing-PyAV audio failures. These are pytest
durations, not hosted-job timing; core elapsed exceeded the hosted 45-minute
ceiling. Baseline failures/skips were not fixed or enabled. The earlier
**313 targeted checks** and **5/5 capture-shell rehearsals** also remain
separate; none establishes hosted/paid behavior or a fully green CI gate.

### Remaining gates

The supported GHCP-to-Codex runtime and applied model/Max/1M evidence,
enforced timeout/tool/turn limits, credential isolation and revocation,
private input/capture policy, usage accounting, grader validation and final
fixed-source review remain unresolved. The earlier direct review of
`f27cde892e144a242260e47a1c2b2e22e07abcf8` plus its correction is not approval
of this documentation commit or of a paid route. Push/Draft PR and authentication
decisions remain with the owner; no publication or launch is claimed.

OpenAI Docs guided official source checks. `experiment-report-en` preserved
settings-versus-observations and separate historical test results;
`im-not-ai-en` guided the English evidence wording. No study/configuration
change or UI work applies. No production, helper, plan, cap, workflow, pin,
dependency or permission changed. No Azure/model/GHCP use, authentication,
workflow dispatch, grading, push or Project change was performed.
