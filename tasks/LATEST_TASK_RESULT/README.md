# Latest Task Result

- Updated: 2026-08-07
- Status: Field Notes rescue reconciled against current `main`; README facts and
  public experiment links corrected and validated; `first-reviewer` approved;
  single PR #162 open

## Task

- Back up the only three-week primary worktree copy before any Git mutation.
- Surgically rescue seven requested Field Notes assets onto
  `origin/main@a6593c2` without importing the primary worktree's other changes.
- Correct English and Korean root README claims about the unexecuted agentic
  preflight, model roles, Start here cost boundaries, and Field Notes status.

## Result

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

## Verification

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

## Shipment

- Working branch: `feat/field-notes-readme-facts`.
- Base: `origin/main@a6593c2f0b9888a49a90fb96210b0d61b48f6332`.
- PR [#162](https://github.com/hyeonsangjeon/gdpval-realworks/pull/162) is open
  with the Field Notes link correction, bilingual README update, regression
  contracts, changelog, and this completion record in one review unit.

## Remaining Work

- PR #162 awaits the owner's merge decision. Do not merge it or create a second
  completion PR unless the owner explicitly requests it.
