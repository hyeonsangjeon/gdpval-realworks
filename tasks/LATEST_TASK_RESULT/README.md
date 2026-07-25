# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-25
- Status: refined Bolt implemented and locally validated; PR shipment pending

## Task

- Re-audit the supplied README/evidence improvement Bolt against current
  `main` after the Foundry migration.
- Save a refined repository task before implementation, defer already-shipped
  or invalid work, and complete the remaining non-duplicative work.
- Preserve batch, grading, publication, Foundry, permission, and paid-execution
  semantics.

## Result

- Saved `tasks/0725_saturday/BOLT_README_EVIDENCE_AND_BUILD_PROVENANCE.md` with
  current-main evidence, defer decisions, implementation boundaries,
  acceptance criteria, and rollback.
- Deferred README restructuring because the first screen already exposes live
  evidence, credential-free local preview, a three-task cloud path, artifact
  inspection, and explicit cost/write boundaries backed by onboarding tests.
- Deferred a new fast PR workflow because `deploy.yml` already runs exact
  checkout, aggregation, production build, aggregate contracts, and Chromium
  checks with read-only PR permissions and main-only Pages deployment.
- Deferred Action pin churn because the named workflow target no longer exists,
  active relevant Actions are SHA-pinned, and no reviewed replacement pin set
  was supplied.
- Replaced the hardcoded footer version with package-derived dashboard build
  provenance. A valid lowercase 40-character SHA and two-segment repository
  slug produce a fixed GitHub full-commit link with a short visible SHA.
- Missing or malformed version, SHA, or repository values fail closed to an
  accessible, non-link local-build label.
- Kept dashboard source-build identity separate from the generated-data
  timestamp and from experiment, model, Foundry, and grading provenance.
- Added exact compile-time declarations and limited the Build-step public inputs
  to `${{ github.sha }}` and `${{ github.repository }}`. No environment object,
  token, endpoint, ref, actor, or workflow payload enters the bundle.
- Extended the existing PR validation job rather than creating another
  workflow. Pages and OIDC write permissions remain isolated to the main-only
  deploy job.
- Added focused contracts and production-browser checks for exact links,
  invalid-input fallback, accessible names, keyboard focus, and desktop/mobile
  overflow.
- External comparison used only commit/license metadata and a general
  provenance pattern. No external code or copy was reused.

## Verification

- Base and current remote main:
  `f849856c6a91c357becc74ae93b60a5c9289917f` with 0 ahead / 0 behind before
  commit.
- Focused build-provenance contracts: **3 passed, 0 failed**.
- Frontend/data aggregate contracts: **92 passed, 0 failed, 0 skipped**.
- Production TypeScript and Vite build passed with explicit exact SHA and
  repository inputs.
- The provenance browser matrix passed both the published exact-commit state
  and a separately generated local-build fallback. It verified full-SHA href,
  short-SHA display, accessible name, actual keyboard focus, visible focus
  outline, and no horizontal overflow at mobile and desktop viewports.
- Runtime, integrity, perception, and success browser suites all passed against
  the production dist.
- Editor diagnostics reported no errors in every changed source, test, config,
  and workflow file.
- `git diff --check` passed; no generated or dist artifact is modified or
  untracked.
- `actionlint` was unavailable locally. The changed workflow parsed with the
  installed YAML parser, and the aggregate contract verifies exact Build and
  browser-step wiring.
- First review found one fail-closed defect where a slashless repository slug
  could be accepted through regex coercion. The defect was reproduced, fixed by
  requiring exactly two segments, and covered by a regression case. Subsequent
  code and mandatory workflow/security re-reviews both returned **APPROVE** with
  no remaining finding.
- No workflow dispatch, deployment, credential or token acquisition, Azure or
  model call, grading run, Hugging Face write, network checkpoint write, or paid
  execution occurred during local work.

## Shipment

- Implementation branch: `feat/readme-evidence-paths`.
- Commit, pull request, automatic validation, merge, and post-merge Pages
  deployment are pending.

## Remaining Work

- Commit and push the reviewed tree, open a pull request, wait for the automatic
  read-only validation, and merge only after it passes.
- Record the exact PR, merge SHA, and automatic `main` validation/Pages run in a
  docs-only shipment follow-up.
