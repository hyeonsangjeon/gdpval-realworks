# Latest Task Result

- Updated: 2026-08-12
- Status: the four-task Sol Max anchor completed, but the 220-task run is
  blocked by audio routing and the 44-hour envelope

## Current Task: First Sol Max Four-Task Anchor

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

---

## Preserved Prior Result: Non-Recursive Completion Records (2026-08-08)

- Status: Completion records retain verified task evidence without forcing
  documentation-only PRs that restate their carrying PR's merge status

### Task

- Clarify the repository completion requirements so the latest-task result and
  changelog remain complete without describing the carrying PR's own merge.
- Preserve task scope, concrete outcome, verification evidence, reviewed head
  SHA, remaining work, bounded history, `[Unreleased]`, and unrelated entries.
- Preserve every existing historical merge record and require genuine earlier
  corrections to ride with the next substantive work PR.

### Result

- Both completion records now stop at pre-merge facts and exclude their
  carrying PR's own merge SHA, merge time, and `OPEN` / `MERGED` state.
- The policy states the reason directly: Git history already holds those facts,
  while a record describing its own merge cannot be written before that merge
  and therefore forces an unnecessary follow-up PR.
- Earlier status corrections remain supported, but they must be folded into the
  next substantive work PR instead of opening a documentation-only PR solely
  for merge status.
- Existing rigor is unchanged: scope, outcome, verification, reviewed head,
  remaining work, bounded history, changelog category, unrelated-entry
  preservation, and post-validation/pre-response timing all remain required.
- The previous README containment, Hosted Tier 1, and Field Notes records are
  preserved below, and no historical merge metadata was rewritten.

### Verification

- Exact-phrase completion-policy contract: passed.
- Scope and preservation contract: exactly three changed files, all six prior
  changelog merge markers unchanged, all three prior latest-task records
  preserved, and no carrying-PR identity in the new completion entries.
- VS Code diagnostics and `git diff --check`: passed.
- No application model/API call, credential, workflow dispatch, or paid
  operation ran; shipment is limited to authenticated Git and GitHub branch/PR
  writes.

### Review Evidence

- Reviewed substantive head:
  `e800734576dbcc314e5646af80281114672e05dc`.
- Independent `first-reviewer` verdict: `APPROVE`, with no blocking findings.

### Remaining Work

- The owner decides whether and when to merge the reviewed change. Do not create
  a later documentation-only PR to record the carrying PR's merge metadata.

---

## Preserved Prior Result: Root README Containment Evidence (2026-08-08)

- Status: Root English/Korean containment documentation now separates the
  unexecuted self-hosted preflight from verified hosted Docker controls;
  merged through PR #165 while `exec_run` and the aggregate gate remain blocked

### Task

- Correct the stale implication that no containment result exists after PR
  #163, without claiming that the self-hosted preflight itself ran.
- Keep English and Korean root README descriptions structurally parallel.
- Preserve the evidence ladder and the blocked boundaries for arbitrary
  execution and the aggregate gate.

### Result

- Split the operational-control entry into two distinct facts:
  - the `[self-hosted, linux, x64, agentic-sandbox]` preflight remains
    unexecuted and `not_run` because no matching runner exists;
  - the separate GitHub-hosted Docker-control measurement is `verified` for all
    eight checks through run `31193818481`, PR #163 / merge `4b1bff35`, and
    containment-report SHA-256
    `f0c4ec3cdff7d714d0db8aca58b1f5669c3958c6b6203be00095b8acb827e50e`.
- Both READMEs state that the hosted result measures Docker control
  effectiveness, not arbitrary execution isolation. `exec_run` remains
  blocked.
- Both READMEs retain aggregate gate `blocked` because capability, CVE, license,
  microVM, OCI, provenance, SBOM, and signature evidence remains unmeasured.
- Removed the now-false English statement that no containment result is
  established and its Korean equivalent, while preserving the accurate
  `not_run` status of the self-hosted workflow.

### Verification

- Bilingual onboarding contracts: 12 passed.
- Self-preparing aggregate suite: 98 passed, 1 expected Ruby skip.
- `npm run build`: passed with 2,783 transformed modules.
- VS Code diagnostics and `git diff --check`: passed.
- No model, grading, cloud credential, workflow dispatch, Hugging Face write,
  or paid operation ran. Aggregation made unauthenticated read-only public
  report requests only.

### Shipment

- Reviewed branch head:
  `c3b2a0b4e814d8bb2c830b01162d627f1277739b`.
- Independent `first-reviewer` verdict: `APPROVE`, with no blocking finding.
- PR [#165](https://github.com/hyeonsangjeon/gdpval-realworks/pull/165) reached
  `MERGED` at `2026-08-07T17:04:12Z` as squash commit
  `2d82691ffb5d1911f19f996be0807d4ca037ae81`.
- GitHub reported the PR `MERGEABLE` and `CLEAN`; automatic PR validation passed
  with deployment skipped. Automatic post-merge main run
  [`31200577265`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/31200577265)
  passed validation and Pages deployment. No workflow was manually dispatched.

### Remaining Work

- No remaining shipment work is carried by this README correction record.

---

## Preserved Prior Result: Hosted Containment Tier 1 (2026-08-08)

- Status: GitHub-hosted Agentic Sandbox V2 containment verified 8/8; aggregate
  gate remains blocked and production execution remains disabled

### Task

- Measure network isolation, read-only root, non-root execution, capability
  drop, no-new-privileges, memory, effective CPU quota, and PID limit on a
  GitHub-hosted `ubuntu-latest` runner.
- Use the existing validated containment probe and exact public parent image,
  without local-kernel workarounds, model calls, credentials, paid
  infrastructure, or Phase 1D-B execution code.
- Emit `verified` / `failed` / `not_run` evidence and decide whether the
  aggregate gate can leave `blocked`.

### Result

- Run
  [`31193818481`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/31193818481)
  measured source `bedcdd8229cc4b96c93f52323dcf2099acc7a0ca` on GitHub-hosted
  Linux `6.17.0-1021-azure`, amd64, cgroup v2.
- Exact parent manifest:
  `sha256:ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5bd24edb`.
- Result SHA-256:
  `5caeb42cbe5032169d520e93160a9e19ecbecc0f066faed96979aa44a2103624`.
- Containment report SHA-256:
  `f0c4ec3cdff7d714d0db8aca58b1f5669c3958c6b6203be00095b8acb827e50e`.

| Containment check | Status |
|---|---|
| Network disabled | `verified` |
| Read-only root filesystem | `verified` |
| Non-root UID/GID | `verified` |
| All capabilities dropped | `verified` |
| No new privileges | `verified` |
| Effective memory limit | `verified` |
| Effective CPU quota | `verified` |
| PID limit | `verified` |

### Gate Decision

- Production containment is `verified` for the exact hosted Docker measurement;
  it is not a blocker in this result.
- The aggregate gate cannot leave `blocked`. Tier 1 did not measure a complete
  candidate subject's capability receipt, CVE, license, microVM, OCI layout,
  provenance, SBOM, or signature evidence.
- Production activation remains `disabled`, and `exec_run` remains
  `capability_unavailable`. No Phase 1D-B code was written.
- Tier 2 Azure VM provisioning was not requested or performed because Tier 1
  was sufficient to measure all eight Docker controls.

### Verification

- Final hosted workflow completed every setup, exact-image pull, measurement,
  evidence upload, and terminal-cleanup step successfully; the existing image
  publication job was skipped.
- The downloaded JSON passed the checked-in strict validator, and its Markdown
  matched deterministic regeneration byte-for-byte.
- The preceding hosted run produced the same parent identity, containment
  report, eight statuses, and gate decision.
- Focused hosted workflow/result/verifier suite: 74 passed.
- Agentic V2 / Phase 1B / Phase 1C / Phase 1D-A regression suite: 654 passed.
- Ruff, `py_compile`, VS Code diagnostics, and `git diff --check`: passed.
- Independent `azure-infra-engineer` and `first-reviewer` reviews returned
  `APPROVE` with no blocking findings.
- No Azure, OIDC, client secret, model, grading, Hugging Face write, registry
  push, paid infrastructure, or artifact publication outside the 14-day GitHub
  Actions evidence artifact was used.

### Shipment

- Reviewed branch head:
  `7e4289e5e9a7707b61caabd61d5102cae2361c61`.
- PR [#163](https://github.com/hyeonsangjeon/gdpval-realworks/pull/163) reached
  `MERGED` at `2026-08-07T16:22:26Z` as squash commit
  `4b1bff35541e953e0e0fc583e4f9c4f832db01d2`.
- GitHub reported the PR `MERGEABLE` and `CLEAN`. The final hosted measurement
  succeeded with the protected-main publication job skipped; the merge commit
  created no additional workflow run.

### Remaining Work

- A future activation task must bind the hosted containment result to one
  complete candidate subject and verify every remaining required evidence item
  before enabling production execution.

---

## Preserved Prior Result: Field Notes (2026-08-07)

- Status: Field Notes rescue reconciled against current `main`; README facts and
  public experiment links corrected and validated; `first-reviewer` approved;
  merged through PR #162

### Task

- Back up the only three-week primary worktree copy before any Git mutation.
- Surgically rescue seven requested Field Notes assets onto
  `origin/main@a6593c2` without importing the primary worktree's other changes.
- Correct English and Korean root README claims about the unexecuted agentic
  preflight, model roles, Start here cost boundaries, and Field Notes status.

### Result

- Created and checksum-verified an external physical backup outside the
  repository: 16,173 regular files, 27 symlinks, and 521,099,777 bytes. Its Git
  status fingerprint is the pre-task 1,235-line SHA-256
  `8e96ad2cfdaceb05d61c978ad786df13c3647b8ae810771344dd3430314d91ce`.
- Reconciled all seven requested paths and found the supplied absence premise
  was no longer true: every path is tracked on current `main`, with Field Notes
  history from initial commit `8ac9c20` through later evidence-backed fixes.
- Five primary filesystem assets were exact older Git blobs, `Journal.tsx` was
  already identical to `main`, and the missing filesystem test had a newer
  committed successor. The only unique `journal.ts` blob was a stale
  intermediate that would remove the prompt-complexity note and later runtime,
  integrity, perception, and success evidence/citation contracts. No stale blob
  was copied over current `main`.
- The clean branch keeps all seven canonical paths as ordinary tracked files,
  resolving the intended final file set without changing the primary
  index/worktree D/?? state.
- Fixed all public exp026 detail links in Field Notes evidence and mobile cards
  to use
  `https://hyeonsangjeon.github.io/gdpval-realworks/experiments/exp026` with
  `target="_blank" rel="noopener noreferrer"`.
- Corrected both root READMEs:
  - the self-hosted agentic preflight is defined but never run and its
    containment evidence remains `not_run`;
  - `gpt-5.2-chat` is labeled as the sample config value and `gpt-5.6-sol` as
    the current production report default;
  - every Start here route identifies $0/no-model inspection or paid model and
    remote-write behavior;
  - RealWorks Field Notes links to the deployed `/notes` view.
- The primary worktree was not modified by this task. Relative to the physical
  backup, its only new status entry is one user-created private task spec
  supplied during the session.

### Verification

- Focused Field Notes and bilingual onboarding contracts: 21 passed.
- Self-preparing aggregate suite: 98 passed, 1 expected skip because Ruby is
  unavailable locally.
- `npm run build`: passed with 2,783 transformed modules.
- Four Field Notes Chromium suites passed inside the pinned
  `mcr.microsoft.com/playwright:v1.61.1-noble` image. They verify:
  - `/journal/:slug` redirects at runtime to `/notes/:slug` while preserving
    query parameters;
  - all visible exp026 links use the public URL and exact safe new-tab
    attributes;
  - 390px and 1,280px layouts have zero horizontal overflow;
  - reduced-motion charts remain static and evidence failure states fail closed.
- The host Playwright binary itself could not start because `libnspr4.so` is
  absent; the matching container supplied the browser runtime without changing
  the host.
- `git diff --check`: passed.
- Independent `first-reviewer` review: `APPROVE`, with no blocking findings.
- No model, grading, cloud credential, workflow dispatch, Hugging Face write,
  or paid operation ran. Aggregation made unauthenticated read-only requests to
  23 public report datasets.

### Shipment

- Reviewed branch head: `b5d4c2ec68ff027a3187b183183c8b8d81fbf1fb`.
- PR [#162](https://github.com/hyeonsangjeon/gdpval-realworks/pull/162) merged
  at `2026-08-07T15:15:36Z` as squash commit
  `8216181834b4687fd41e543b77f146918e849a23`.

### Remaining Work

- No remaining Field Notes shipment work is carried by this preserved record.
