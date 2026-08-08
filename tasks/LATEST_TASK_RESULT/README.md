# Latest Task Result

- Updated: 2026-08-08
- Status: Completion records retain verified task evidence without forcing
  documentation-only PRs that restate their carrying PR's merge status

## Current Task: Non-Recursive Completion Records

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
