# Bolt: README Evidence Audit and Dashboard Build Provenance

- Date: 2026-07-25
- Base: `f849856c6a91c357becc74ae93b60a5c9289917f`
- Status: build-provenance slice implemented and locally validated
- External reference: `open-webui/open-webui@ecd48e2f718220a6400ecf49eafd4867a38feb10`
- External license signal: `NOASSERTION`; no external code or copy is reused

## Decision

The supplied improvement brief was re-audited against current `main` after the
Foundry migration. Only dashboard build provenance remains non-duplicative.
README conversion, a new fast PR workflow, and Action pin changes are deferred.
This Bolt does not modify batch, grading, publication, or Foundry semantics.

The traffic snapshot supplied with the brief informed prioritization but is not
committed here: repository task records are public and traffic analytics are not
an implementation acceptance source.

## Evidence Reviewed

- Complete `README.md`, including first-screen evidence, local preview,
  three-task cloud run, result inspection, and trust-boundary sections.
- Complete `.github/workflows/deploy.yml`, including path filters,
  concurrency, exact checkout, PR validation, browser checks, permissions, and
  main-only Pages deployment.
- `package.json`, `package-lock.json`, `vite.config.ts`, and `src/vite-env.d.ts`.
- Actual application shell and display surfaces under `src/`, including the
  dashboard footer and About modal.
- Existing browser-test harness under `scripts/__tests__`.
- Current workflow list and Action references.
- External comparison commit and license metadata only.

## Defer Report

### README evidence conversion: deferred as duplicate

Current README first screen already exposes live evidence, a credential-free
local preview, a three-task cloud path, result/artifact inspection, and explicit
cost/write boundaries. Existing onboarding contracts enforce those links and
semantics. No screenshot is added because it would duplicate current evidence
paths and introduce an unowned freshness obligation.

### Fast PR gate: deferred as duplicate

`deploy.yml` already provides a read-only PR job with exact checkout, `npm ci`,
aggregation, production build, aggregate contracts, Chromium installation, and
browser verification. Pages permissions and deployment remain main-only. A
second workflow would duplicate cost and feedback without adding a failure
boundary.

### Action pin changes: deferred

The active deploy/preflight Actions are already pinned to 40-character SHAs.
The brief's `validate-hybrid-and-decide.yml` target no longer exists. No
reviewed replacement pin set is available, so no supply-chain churn is made.

## Implementation Contract

### Public inputs

Expose only:

- package version from `package.json`;
- exact build SHA from `VITE_BUILD_SHA`;
- repository slug from `VITE_BUILD_REPOSITORY`.

Never expose the environment object, token, endpoint, workflow payload, actor,
ref, or credential. Repository and SHA values are validated before producing a
GitHub link.

### Build behavior

- `vite.config.ts` injects the package version as a compile-time constant.
- The deploy Build step passes exact `${{ github.sha }}` and
  `${{ github.repository }}` through the two public Vite variables.
- The existing exact-checkout guard remains the source-to-artifact boundary.
- Local builds or malformed public values display a non-link `local build`
  state rather than constructing an untrusted URL.

### UI behavior

- Replace the hardcoded dashboard footer version with one compact provenance
  label.
- A valid build links to the exact GitHub commit using the full SHA while the
  visible label uses the seven-character SHA.
- The link has an explicit accessible name, visible keyboard focus, sufficient
  contrast, and must not cause mobile overflow.
- The build label is distinct from the generated-data timestamp and does not
  imply experiment, model, or Foundry provenance.

## File-Level Work Order

- [x] `vite.config.ts`: inject the package version from parsed `package.json`.
- [x] `.github/workflows/deploy.yml`: pass exact public SHA/repository values to
      the Build step only.
- [x] `src/vite-env.d.ts`: declare the compile-time version constant.
- [x] `src/lib/buildProvenance.ts`: validate and project public build identity.
- [x] `src/pages/Dashboard.tsx`: render the accessible footer provenance.
- [x] `package.json`: wire focused unit and dist browser tests.
- [x] `scripts/__tests__/build-provenance.test.mjs`: validate source/config/UI
      contracts and invalid-value fallback.
- [x] `scripts/__tests__/build-provenance.browser.mjs`: validate rendered text,
      full-SHA link, keyboard focus, and mobile overflow.
- [x] `CHANGELOG.md` and `tasks/LATEST_TASK_RESULT/README.md`: record the final
      result after validation.

## Validation Result

- Focused build-provenance contracts: **3 passed, 0 failed**.
- Frontend/data aggregate contracts: **92 passed, 0 failed**.
- Production TypeScript and Vite build passed with an explicit 40-character
  SHA and repository slug.
- Published and local browser states passed exact-link, accessible-name,
  keyboard-focus, and desktop/mobile overflow checks.
- Runtime, integrity, perception, and success browser suites all passed.
- Editor diagnostics and `git diff --check` passed.
- Independent code and workflow/security re-reviews returned **APPROVE** after
  a slashless repository-slug edge case was reproduced, repaired, and covered.
- `actionlint` was unavailable locally; the changed workflow parsed with the
  installed YAML parser and is covered by the aggregate wiring contract.
- No batch, grading, Azure, Hugging Face, deployment, or paid action ran during
  local validation.

## Acceptance Criteria

- `npm ci`, `npm run test:aggregate`, and `npm run build` pass.
- Focused provenance unit and browser tests pass.
- A build with a valid 40-character SHA displays package version plus short SHA
  and links to the exact full commit.
- A local or malformed build displays `local build` without a commit link.
- The production Pages workflow injects the exact checked-out GitHub SHA.
- Pull requests receive no Pages/OIDC write privileges.
- The footer is keyboard accessible and has no horizontal overflow at desktop
  and mobile viewports.
- Existing Field Notes browser suites remain green.
- No batch, grading, Azure, Hugging Face, or paid execution is performed.

## Rollback

Revert this provenance PR only. The fallback is the existing repository link in
the dashboard footer; benchmark results, datasets, workflows outside
`deploy.yml`, and remote project state are outside rollback scope.