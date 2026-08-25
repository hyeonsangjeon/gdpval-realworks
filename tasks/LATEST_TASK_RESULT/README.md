# Latest Task Result

- Updated: 2026-08-25
- Status: the comparison of one GPT model across five places a task can be run
  is now specified, and a check that answers "may it start?" without calling a
  model ships with it; no comparison ran, because paid model calls are
  unapproved and two of the five places cannot run a GDPVal task at all

## Current Task: Execution Environment Comparison Groundwork

### Task

Settle in code and in writing what has to be true before the same GPT model is
compared across five places a GDPVal task can be run, without running the
comparison, calling a paid model, grading anything, signing in to Azure, or
publishing an image.

The five places: a separate Python process on the server's own operating
system; a Docker container; Azure AI Foundry's code interpreter; the
Agentic Sandbox V2 foundation; and Codex's own built-in agent.

### Result

- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md` is the written
  specification. It names no GPT version, so a later run picks its own model
  and the document does not change. The card's in-house shorthand for the
  fixed-model idea is gone; it is written out as "고정 모델 실행 조건" — fifteen
  entries that must match in every place — and carried in code as
  `ModelRunConditions`.
- **Each of the five places is graded from code that was read, not assumed.**
  A separate Python process can run a real experiment today (24 experiment
  configs use it; 220 graded tasks exist). A Docker container can, but only
  when its container setting is `always` — `SandboxRunner._execute` at
  `batch-runner/core/sandbox_runner.py` line 1039 otherwise runs the code on
  the host and prints a warning, which would silently turn the container
  result into a host result. Azure's code interpreter is implemented and
  selected by 5 configs but refuses to start without its route setting.
  Agentic Sandbox V2 supports structure checks only. Codex has no code path
  here at all.
- **The Agentic Sandbox V2 state is recorded as three closed doors, and the
  check opens each one to confirm it is still shut**: the command-running tool
  `exec_run` answers `capability_unavailable` for ordinary commands; there is
  no loop in which a model reads a tool result and picks a next action; and
  both `step2_run_inference._require_runnable_execution_mode` and
  `TaskExecutor` refuse the mode outright. None was bypassed or weakened.
- **Codex is recorded as absent, and the reason it cannot simply be added is
  recorded too.** Official documentation does not describe running Codex's own
  agent loop against an outside benchmark task set, and does not describe
  Codex's agent loop on an Azure AI Foundry deployment. Since the specification
  requires all five places to share one deployment, that gap is written down as
  missing evidence rather than papered over. Azure models whose names contain
  "codex" are Azure's own agent service using that model, which is a different
  thing, and the document says so.
- **The two comparisons cannot share a score.** Re-running one model's already
  written code in each place, and letting each tool use everything it ships
  with, get separate scoreboards; `check_comparisons_are_scored_apart` fails if
  one is missing or mislabelled. Retries are counted in three separate
  buckets — an infrastructure failure, the model reviewing its own finished
  output, and the model recovering mid-conversation with its tools — and a
  single lumped count is rejected.
- `scripts/check_execution_environment_readiness.py` answers "may the
  comparison start?" for free. With no approval present it downgrades every
  runnable place to blocked and names the setting that would grant it; it never
  substitutes a working place for a missing one. The 5, 30, and 220 task stages
  each require eight decisions to be fixed before any spending.

### Review Evidence

An independent review found eight defects in the first version; all were fixed
and each now has a test that fails without the fix. Three mattered:

- **The readiness check said "ready" while every place was blocked.** `ready`
  was `not problems`, so per-place blockers never reached it and the command
  line tool exited 0 with no paid-run approval on record — the exact thing the
  approval exists to prevent. `ready` now requires that every place being
  compared can actually start, and which places those are comes from the plan.
- **One of the three Agentic Sandbox V2 doors was not really being tested.**
  The check accepted any `ValueError` from the dispatcher, but that branch
  raises for seven different reasons; with the paid-run block deleted a
  later missing-argument complaint took its place and the door was reported
  shut. The check now fills in every other argument so the paid-run block is
  the only remaining reason to refuse, and matches on the refusal itself.
- **Five of the fifteen fixed conditions were never compared.** Self-review and
  retry settings were left out, so one place could take nine self-review passes
  and twenty-five retries against another's one and three and still be called
  conforming. Fixing this exposed a real distinction rather than a simple
  oversight: those four settings must match when the same code is re-run, and
  must be free to differ when each tool uses its own features, because that is
  what the second comparison measures. The check now takes the comparison as an
  argument and applies the matching strictness.

Also fixed: a stage plan could not express "no self-review, no retries" because
zero and the empty list were read as missing, and that misreading also skipped
the 5/30/220 count check; the command line tool turned a plan naming no place
at all into "no plan given"; one test assertion sliced a tuple to nothing and
was true for any input; and the specification said 15 configs where 24 use that
mode, and claimed one Codex mention repository-wide where the true statement is
that no *executable* path exists.

### Verification

- New suite `batch-runner/tests/test_execution_environment_readiness.py`:
  123 passed. It runs the three Agentic Sandbox V2 doors for real, and asserts
  the check reports a problem when each is opened — including a dispatcher
  reproducing the real branch with only the paid-run block removed.
- Full backend suite locally: 3,641 passed, 6 skipped, 45 deselected, 3 failed.
- **In CI the same suite is 3,641 passed, 9 skipped, 45 deselected, 0 failed**
  (run 32810669993). The 3 local failures are
  pre-existing and environmental: `pdfplumber` is not installed here (2 tests),
  and one test pins SDK versions older than the locally installed
  `openai 2.45.0` / `azure-ai-projects 1.0.0` / `azure-core 1.39.0`. They were
  confirmed by re-running them with both new files moved out of the tree, where
  they fail identically.
- `mypy` on the new module: clean.
- Every file path, line number, function name, and count cited in the
  specification was checked against the repository by the reviewer; the two
  wrong counts above were the only errors, and both are corrected.
- No model call, no grading, no Azure sign-in, no image publish, no workflow
  dispatch, and no Hugging Face write occurred. Network access was confirmed
  unused by patching `socket.connect`, `socket.create_connection`, and
  `getaddrinfo` to raise and running the whole check.
- Work was done in a throwaway worktree cut from `origin/main` at `47b0fe5`.
  The user's own working folder and its 1,275 pending changes were not touched.

### Shipment

- PR [#224](https://github.com/hyeonsangjeon/gdpval-realworks/pull/224).

### Remaining Work

- The comparison itself has not run and must not until the owner approves paid
  model calls and names the model and deployment.
- Azure's code interpreter needs its route setting supplied.
- The Docker container place needs an experiment config that pins its container
  setting to `always`.
- Agentic Sandbox V2 needs its command-running tool, a real model loop, and an
  explicit approval before it can join.
- Codex needs both a run path here and public evidence that its agent loop can
  use the same Azure deployment. Until then the fifth column stays empty rather
  than being filled by another place.

---

## Preserved Prior Result: Legacy Provenance Complete-Corpus Policy (2026-08-18)

### Task

Remove the provenance rule that made the 220-task exp003 Sol Max regrade
unpublishable, without weakening what that rule was actually protecting.

exp003 ran in 2026-02, before `step3_format_results.py` began emitting
`inference_provenance.json`. Its payloads carry neither `prepared_fingerprint`
nor `azure_ai_routes`, so the sidecar cannot be written after the fact without
inventing both. Under the prior rule any grade built from it was forced to
`run_status: diagnostic` and written under `data/grades/_diagnostic/`, which
`scripts/aggregate-grades.mjs` does not read — so a completed paid 220-task run
would have produced a grade the dashboard never shows.

### Result

- The sidecar is an audit receipt, not a grading input. `core/grader.py` and
  `core/tool_calling_judge.py` never read `azure_ai_routes`; their only
  `*_provenance` field is `visual_provenance`, which is image evidence paths.
  The `routes` validated in `core/grade_payload.py` are the *grader's* own
  routes checked against `azure_ai_runtime_fingerprint`. A missing sidecar
  therefore leaves the audit trail incomplete without leaving the graded corpus
  incomplete.
- `filter_tasks_for_config` in `step8_grade.py` now returns the pinned scope —
  `None` when the config pins nothing, `"subset"` for a proper subset of the
  source corpus, `"complete"` when the pinned list covers all of it — instead of
  a boolean. Equal counts mean equal sets here because canonical order is
  already proven upstream.
- The legacy allowance blocks publication only while that scope is not
  `"complete"`. The four-task anchor pins a subset and stays diagnostic. A
  config pinning every task in canonical source order keeps the root output path
  and `run_status: final`.
- `--allow-legacy-missing-provenance` on `download_inference_from_hf.py` pins
  nothing, so gating on scope rather than on the `legacy-missing` label keeps a
  bare CLI override in the diagnostic tree. That bypass was closed by the same
  condition that opened the intended path.
- The grade payload still persists
  `source_azure_ai_provenance_status: legacy-missing`; no euphemistic status was
  introduced. `scripts/aggregate-grades.mjs` now carries that field into the
  dashboard projection, so a published legacy grade is labelled rather than
  silently normalized.
- Both exp003 full-rerun configs gained all 220 task IDs in canonical source
  order. The mini config had the identical defect and was fixed alongside the
  Sol Max one rather than left as a known-broken path the README advertises.
- No grade payload, deliverable, or HF file was modified. No workflow was
  dispatched.

### Fixed Identities

| Purpose | Config | Config hash | Tasks |
|---|---|---|---:|
| Full rerun (Sol Max) | `regrade_exp003_v2_sol_max_score_excluded.yaml` | `71c325eee0e48c13` | 220 |
| Full rerun (mini) | `regrade_exp003_v2_mini_score_excluded.yaml` | `0aebaaa2d0e51d74` | 220 |
| Paid anchor | `validation_exp003_v2_sol_max_anchor4.yaml` | `7f3c7c2e542cf580` | 4 |

- Sol Max and mini hashes changed from `14fc577ea39d98c5` and
  `55a7dc5cfb8023fe` because each config gained its pinned `task_ids` list. The
  anchor config is untouched.
- Ordered task-ID SHA-256, 220 tasks:
  `df1fcd6415c55a17e4f39a254aaf0f0f9f2f55c751189f74d2713a873373aa3c`.
- Ordered task-ID SHA-256, 4-task anchor:
  `29d5623a5cec85eb38f21fb73a2f3b06c66ed6a5fd6fd95948b979cd70a70bc9`.
- Rubric commit `11e7900cdcac61bc4daf59e65feb238acda98fbf` and inference
  revision `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f` are unchanged.

### Verification

- Both new Python tests were confirmed to fail against an emulated pre-change
  policy and pass after it, so neither is tautological. The JS test was
  confirmed the same way against the aggregator field.
- `test_step8_grade.py` adds `test_legacy_missing_provenance_publishes_when_
  corpus_is_pinned_complete` and `test_sharded_legacy_provenance_run_with_
  complete_pin_stays_publishable`. The second covers the paid production shape
  specifically: missing sidecar, complete pin, and shard slicing at once.
  `test_legacy_missing_provenance_full_run_stays_diagnostic` passes unchanged,
  which is the case that must keep failing closed.
- `scripts/__tests__/aggregate-grades.test.mjs`: 26 passed.
- mypy on `step8_grade.py`: 50 errors before the change and 50 after, none on
  changed lines.

### Review Evidence

- No independent reviewer agent was run. The owner authorized the policy change
  directly after reviewing why the block was a rule rather than a capability
  limit.

### Remaining Work

- The 220-task paid run is still not dispatched and still requires fresh owner
  approval plus the protected `grading` Environment approval per chunk. This
  change removes one blocker; it authorizes nothing.
- The anchor's own gates are untouched and still stand: `audio.call_count` must
  exceed zero, `task_visual_budget_exceeded` must be zero, and the projected
  runtime must clear the 44-hour envelope.
- Credential rotation for the values in the untracked local scratch file remains
  outstanding and owner-only.

---

## Preserved Prior Result: Conductor Orchestrator Persona (2026-08-14)

### Task

- Rename `.github/agents/copilot-instructions.agent.md` to
  `.github/agents/conductor.md`, and rename the persona itself from
  `ai-strategy-consultant` to `conductor`.
- Resolve the persona's internal contradiction: its `tools:` list granted
  `edit/createFile`, `edit/editFiles`, and `edit/rename` while its body forbade
  all file editing.
- Repair every cross-reference the rename would otherwise leave dangling.
- Do not modify the preserved WIP checkout, its stashes, or protected branches,
  and do not carry that checkout's unrelated pending changes into this commit.

### Result

- The persona is now `conductor`: the orchestrating lead that decomposes work,
  writes the governing specs, dispatches worker subagents, and reconciles what
  returns. Decomposition and reconciliation are stated as non-delegable.
- The edit restriction is scoped by **target** rather than by tool. The persona
  may write `tasks/**`, `docs/**`, and `.github/agents/*.md`. It must not write
  `batch-runner/**`, `src/**`, `scripts/**`, `.github/workflows/**`,
  `grading_configs/**`, `schemas/**`, or `data/**`, and `git commit`, `push`,
  PR, and tag remain owner decisions routed to `git-committer`.
- An Orchestration section records three dispatch rules, including that a
  subagent inherits none of the orchestrator's conversation and that
  job-specific boundaries belong in the call prompt rather than in a worker's
  reusable persona file.
- A further dispatch rule requires workers to receive a clean worktree cut from
  the merged SHA and to abort on a non-empty `git status --porcelain`, because a
  harness run against a mixed tree does not measure the merged state and the
  repo-wide instruction files on disk there may be stale.
- `grading-engineer.md` had no `model:` key at all; one is added.
- `llm-systems-engineer.md` line 207 pointed at the old persona name and now
  points at `conductor`.
- The extension is normalized from `.agent.md` to `.md`, matching the other ten
  personas.

### Verification

- Repository-wide search for `ai-strategy-consultant` and
  `copilot-instructions.agent`: zero remaining matches.
- Changed paths are exactly four: the rename pair plus the two edited personas.
- The commit was prepared in a clean worktree cut from `origin/main`
  `f6030e9fb276f7536e913fb0630db0d1818def6a` whose `git status --porcelain` was
  empty at start, so none of the preserved WIP checkout's 211 staged, 59
  unstaged, or 1,013 untracked entries are included.
- The preserved WIP checkout, its three stashes, and
  `hyeonsangjeon-review-handoff-context` are unchanged.
- No model, grading, cloud credential, workflow dispatch, Hugging Face write, or
  paid operation ran.

### Review Evidence

- No independent reviewer agent was run for this change. The owner reviewed the
  complete diff in session before authorizing the commit.

### Remaining Work

- `conductor` and `grading-engineer` now carry
  `Claude Opus 5 (Max reasoning) (copilot)`. No other persona on `main` uses that
  string and it has not been confirmed to resolve at agent invocation —
  appearing in an agent listing proves registration, not invocation. Confirm it
  resolves before relying on either persona. The attested values already on
  `main` are `Claude Opus 4.8 (copilot)` and
  `Claude Opus 4.7 (1M context) (Xhigh reasoning) (Preview) (copilot)`.
- Eight worker personas (`analyzer`, `azure-infra-engineer`, `coder`,
  `extreme-reasoner`, `first-reviewer`, `frontend-developer`, `git-committer`,
  `ui-designer`) carry an uncommitted `model:` change dated 2026-07-17 in the
  preserved WIP checkout that sets a value which fails at invocation. That
  change is deliberately excluded here and remains an owner decision.
- `llm-systems-engineer.md` keeps its existing `model:` value; only its
  cross-reference changed.
- The completion-record mandate lives only in `.github/copilot-instructions.md`,
  which Claude Code does not load, and `CLAUDE.md` does not mention it. Where
  that rule should live is open.
- Do not create a documentation-only PR to record this change's eventual merge
  metadata.

---

## Preserved Prior Result: First Sol Max Four-Task Anchor (2026-08-12)

- Status: the four-task Sol Max anchor completed, but the 220-task run is
  blocked by audio routing and the 44-hour envelope

### Task

- Dispatch exactly one owner-approved paid run of the four pinned anchor tasks
  from exact `main`, through the protected `grading` Environment.
- Read the existing preregistered modality projection and gates without
  changing config, scoring, routing, schema, or acceptance criteria afterward.
- Record exact run, payload, identity, usage, and gate values. Do not run the
  full 220 tasks or manually dispatch a continuation.
- Repair the post-grading analysis filename failure without rerunning models or
  modifying the committed grade JSON.

### Result

- Run `31582293672` executed from
  `c9492645496e176c8e6a3510809585f9542a5bf1` after the exact inputs were printed
  and the protected Environment received its required owner approval.
- `validate-request`, OIDC identity, route/token, renderer, inference download,
  grading, grade schema validation, grade commit, and artifact upload all
  succeeded. No rc=7 relay or additional dispatch occurred.
- The overall run conclusion is `failure` only because Auto-analyze attempted a
  257-byte `.analysis.md` basename after the grade was safely committed. This
  is not a grading or payload failure.
- The grade commit added exactly one diagnostic JSON. The artifact contains the
  same bytes; schema `1.3` and cross-field validation pass, all four tasks and
  all usage planes are complete, and task errors are zero.
- `source_azure_ai_provenance_status` is the expected `legacy-missing`: this
  inference predates sidecars and the exception remains bound to this exact
  revision and four-task config.
- The 13 criteria historically labelled audio were target-aware routed to text
  against a PDF, so `gpt-audio-1.5` was never exercised. This is a routing
  discovery, not a provider deployment failure.
- Auto-analysis now uses a deterministic bounded sibling filename. Writes use a
  no-follow directory FD, UTF-8 byte limits, atomic replacement, mode
  preservation, parent/target race checks, and rollback. The missing Markdown
  was generated from the committed JSON with no model call.

### Fixed Identities

- Run ID: `31582293672`.
- Execution main SHA: `c9492645496e176c8e6a3510809585f9542a5bf1`.
- Grade result commit: `7eb71b52004e611202d396cbaaa636aa317f1000`.
- Config: `validation_exp003_v2_sol_max_anchor4.yaml`, hash
  `7f3c7c2e542cf580`.
- Grader source hash:
  `b00e83209ab6ca93a147da5bcfd02facce922e381fa01b2f73559b0d14631ab9`.
- Payload:
  `exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_6-sol__validation_exp003_v2_sol_max_anchor4__cfg_7f3c7c2e542cf580__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_b00e83209ab6ca93__v2.2.json`.
- Payload SHA-256:
  `303a5e763e28bf06339877df62c8e2d0d022bc605aeeb3aee77e63ab411a41fb`.
- Generated analysis:
  `grade__233124fc9c26e453b906d82429fc0f6387a14c70586639ad428685146e5b4da0.analysis.md`.
- Analysis SHA-256:
  `90252c360f2603ec692d163c02736418c32f8eb9d4ca2779cd64efecf51936ec`.

### Preregistered Decision

- `(a) full_run_gate.status`: `blocked`.
- Blockers: `audio_wiring_not_exercised`,
  `at_or_above_44h_envelope`.
- `(b) projected_220_hours`: `71.5934`; envelope: `44`; status:
  `at_or_above_44h_envelope`.
- Components: main `70.4184h`, visual `1.1750h`, audio `0h`.
- `(c) diagnostic.targetable_status`: `improved`; targetable errors fell from
  22 to one `empty_final_text` (`95.45%` reduction).
- `(d) audio call_count`: `0`; status `failed_no_audio_calls`.
- Anchor integrity: passed. Visual budget errors: `0`. Unknown perception
  calls: `0`. Non-targetable judge errors: none.
- Interpretation: the Sol Max finalization transition has diagnostic support,
  but the full 220-task run remains blocked by unexercised audio routing and
  projected duration. This is not approval to run 220 tasks.

### Token And Runtime Accounting

| Plane | Calls | Input | Output | Cached | Latency |
|---|---:|---:|---:|---:|---:|
| Main | 657 | 3,429,050 | 289,976 | 1,746,790 | 4,568.33923s |
| Perception/visual | 81 | 97,508 | 32,096 | 0 | 539.74591s |
| Perception/audio | 0 | 0 | 0 | 0 | 0s |
| **Total model** | **738** | **3,526,558** | **322,072** | **1,746,790** | **5,108.08514s** |

- Render: 81 calls, 28.12545 seconds.
- Task wall-clock sum: 5,148.95162 seconds; grading step: approximately 5,152
  seconds. Usage is complete.
- Mini calls and latency remain a pre-perception main-judge-only reference, not
  a Sol Max multiplier.
- `estimated_cost_usd=null`, `pricing_complete=false`, with both Sol and audio
  models unpriced. Actual Azure cost is **not confirmed** and is not recorded as
  zero. The local Azure session does not match the workflow tenant/subscription
  and lacks the required Cost Management query command.

### Verification

- Analyzer/path-security tests: 65 passed; Step 8: 161 passed.
- Complete backend: 3,102 passed, 6 skipped, 45 integration tests deselected.
- Self-preparing aggregate suite: 105 passed, 1 expected skip.
- `npm run build`: passed with 2,783 transformed modules.
- `py_compile`, focused Ruff, workflow YAML, VS Code diagnostics, and
  `git diff --check`: passed.
- Grade payload SHA and content are unchanged by the fix; generated Markdown is
  byte-for-byte reproducible and mode `0644`.

### Review Evidence

- Reviewed substantive head:
  `d3c370ce32bcf2f1fc11fa9306460848c87b9d93`.
- Independent `llm-systems-engineer`, `grading-engineer`, `extreme-reasoner`,
  and `first-reviewer` verdicts: `APPROVE`, no blocking findings.

### Remaining Work

- The owner decides whether and when to merge this analysis filename fix and
  generated Markdown. Do not rerun the paid anchor to repair analysis.
- Query Azure Cost Management with the workflow tenant/subscription and attach
  actual run-attributed cost to the operational record before treating this as
  a monetary anchor.
- Investigate why the selected PDF criteria do not exercise audio routing and
  decide how to handle a projected 71.5934-hour serial run. Do not change the
  preregistered gates after observing this result.
- The full-220 config remains provenance-blocked as well as gate-blocked.
- Do not create a documentation-only PR to record this change's eventual merge
  metadata.

---

## Preserved Prior Result: Sol Max Anchor Legacy Provenance Wiring (2026-08-11)

- Status: exact-revision legacy provenance wiring is reviewed and validated;
  no paid grading was dispatched

### Task

- Permit the fixed four-task anchor revision, which predates inference
  provenance sidecars, to use the existing parquet fallback.
- Bind the exception to the anchor config identity and exact inference SHA;
  preserve strict sidecar validation and fail-closed defaults everywhere else.
- Apply one Python-tested policy to both protected workflow download paths
  without changing Environment approval, OIDC, resume, or time-budget gates.
- Do not dispatch paid grading, upload a sidecar, or modify historical grades.

### Result

- Added `rerun_identity.allow_legacy_missing_provenance: true` only to
  `validation_exp003_v2_sol_max_anchor4.yaml`. Step 8 requires a strict boolean
  and pinned task IDs, so the declaration participates in config and grader
  source identity.
- The downloader requires the exact experiment plus requested and resolved
  lowercase inference SHA before honoring the declaration. Blank revisions,
  aliases, uppercase SHA text, identity drift, and unpinned configs are denied.
- Only `RemoteEntryNotFoundError` for the sidecar is accepted. Embedded source
  routes, local cache misses, file errors, timeout, HTTP 401/403, malformed
  JSON, and sidecar identity mismatch still fail.
- Both dry-run validation and paid grading pass the same quoted config path to
  the downloader. No raw legacy override or workflow input was added.
- Step 8 preserves `source_azure_ai_provenance_status: legacy-missing` and
  forces these results into the diagnostic output scope.
- A model-free download of the pinned HF revision reconstructed 220 rows from
  parquet and produced the exact revision, empty source routes, and
  `legacy-missing` status. No deliverables, grade payloads, or HF files changed.

### Fixed Identities

| Purpose | Config hash | Tasks |
|---|---|---:|
| Full rerun | `14fc577ea39d98c5` | 220 |
| Paid anchor | `7f3c7c2e542cf580` | 4 |

- Experiment: `exp003_GPT52Chat_baseline_runner_exec`.
- Rubric commit: `11e7900cdcac61bc4daf59e65feb238acda98fbf`.
- Inference revision: `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`.
- Ordered-task digest:
  `29d5623a5cec85eb38f21fb73a2f3b06c66ed6a5fd6fd95948b979cd70a70bc9`.
- Baseline payload SHA-256:
  `b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570`.
- Anchor grader source hash:
  `b00e83209ab6ca93a147da5bcfd02facce922e381fa01b2f73559b0d14631ab9`.

### Provenance Boundary

- The fixed inference revision has parquet data but no
  `step2_inference_results.json` or `inference_provenance.json`; it was produced
  before sidecars became mandatory.
- The allowance does not synthesize provenance. It records the degradation as
  `legacy-missing`, keeps source routes empty, and preserves diagnostic scope.
- `regrade_exp003_v2_sol_max_score_excluded.yaml` has no declaration. A future
  full-220 run therefore remains blocked on missing sidecar provenance unless
  the owner separately reviews a new identity-bound exception.

### Verification

- Downloader contracts: 56 passed.
- Grading config: 74 passed; Step 8: 161 passed.
- Complete backend: 3,099 passed, 9 skipped, 45 integration tests deselected.
- Self-preparing aggregate suite: 105 passed, 1 expected Ruby skip.
- `npm run build`: passed with 2,783 transformed modules.
- Model-free pinned-revision download: 220 rows, exact SHA, empty routes,
  `legacy-missing` status.
- `py_compile`, focused Ruff, workflow YAML parsing, VS Code diagnostics, and
  `git diff --check`: passed.
- Historical grades, HF data, full/mini configs, Environment approval, OIDC,
  resume, and time-budget behavior are unchanged. No credentialed workflow
  dispatch, model call, or paid operation ran.

### Review Evidence

- Reviewed substantive head:
  `70de50f829f928f88f3bc6b4f6a71b01a8a820bf`.
- Independent `llm-systems-engineer`, `grading-engineer`, `extreme-reasoner`,
  and `first-reviewer` verdicts: `APPROVE`, with no blocking findings.

### Remaining Work

- The owner decides whether and when to merge this protected workflow change.
- After it reaches exact `main`, a separate owner-approved protected dispatch
  may run only the four-task anchor with explicit config and pinned revision.
- The resulting artifact must still pass every preregistered identity, usage,
  diagnostic, audio, visual-budget, attribution, and 44-hour gate.
- This preparation neither dispatches nor authorizes the full 220-task run.
- Do not create a documentation-only PR to record this change's eventual merge
  metadata.

---

## Preserved Prior Result: Judge Error Score Exclusion (2026-08-08)

- Status: `judge_error` is score-excluded at runtime and remains visible in
  schema 1.3 summaries and the dashboard; no paid regrade was run

### Task

- Analyze the 100 known score-included `judge_error` zeros without a model call
  or mutation of the checked-in grade payload.
- Exclude every judge failure from score numerators and denominators at runtime,
  including stale or missing producer flags, while keeping the error rate
  visible.
- Increment the grade output schema, document the comparison boundary, and pin
  the exact identity for a later complete 220-task rerun.
- Do not partially regrade the 53 affected tasks or perform any paid grading in
  this policy task.

### Result

- `Grader._aggregate` now forces every `judge_error` to
  `score_excluded=true`, keeps `model_did_right=false`, and excludes the item
  from score, coverage, and critical metrics.
- A task whose items are all excluded is unscored rather than zero-scored. Its
  headline score and confidence interval are null, all headline counts are
  zero, and dashboard score surfaces render an em dash.
- Complete score-excluded judge errors no longer abort Track 2. Malformed
  items, incomplete usage, and any unexcluded judge error still stop the run.
- Output schema `1.3`, shared Python validation, resume identity, and strict
  dashboard ingestion enforce the same task-count, exclusion, headline, and
  canonical four-decimal error-rate invariants. Historical schemas `1.0`-`1.2`
  remain readable and retain numeric headline requirements.
- `judge_error_rate` remains visible even at zero in run health and analysis
  cards; its tooltip explicitly states that errors are excluded from score
  denominators but not hidden.
- Headline scores from schema `1.3` are not directly comparable with schemas
  `1.0`-`1.2`. Resume rejects the old score semantics rather than mixing them.

### Historical Analysis

- Read-only source:
  `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`.
- Payload SHA-256:
  `b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570`.
- Observed 355 `judge_error` items. Of those, 100 score-included zeros affected
  53 tasks: 61 `final_json_parse_failed`, 31 `empty_final_text`, five
  `RateLimitError`, and three content-policy `BadRequestError` items.
- The other 255 errors were already score-excluded selection failures. The
  source payload was not edited or partially regraded.

### Fixed Rerun Identity

- Config: `regrade_exp003_v2_mini_score_excluded.yaml`.
- Config hash: `55a7dc5cfb8023fe`.
- Rubric commit: `11e7900cdcac61bc4daf59e65feb238acda98fbf`.
- Inference revision: `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`.
- Expected task count: 220. Step 8 rejects experiment, task-count, rubric, or
  inference drift before its Azure route preflight and model construction.

### Verification

- Runtime/schema/config/selector matrix: 382 passed before the final invariant
  fixes; the complete backend suite then passed 3,033 tests with six skips and
  45 integration tests deselected.
- The three unchanged host-environment failures were stale Azure SDK versions
  and missing `pdfplumber`; all three passed under exact temporary Python 3.10
  dependencies.
- Self-preparing aggregate suite: 105 passed, 1 expected Ruby skip.
- `npm run build`: passed with 2,783 transformed modules.
- Ruff, `py_compile`, VS Code diagnostics, and `git diff --check`: passed.
- No grade payload, workflow, or production configuration was rewritten. No
  partial/full grading run, credential use, workflow dispatch, or paid model
  operation occurred.

### Review Evidence

- Reviewed substantive head:
  `3c8ab817916129dff7a33291520a1f4f2db7d048`.
- Independent `grading-engineer` and `first-reviewer` verdicts: `APPROVE`, with
  no blocking findings.

### Remaining Work

- The owner decides whether and when to merge the reviewed change.
- A later paid task may run the complete 220-task pinned config after separate
  approval. Do not merge a 53-task partial rerun, and do not create a
  documentation-only PR to record this change's eventual merge metadata.
