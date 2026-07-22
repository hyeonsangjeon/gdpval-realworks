# BOLT: Turn the README into an Execution and Trust Entry Point

- Date: 2026-07-21
- Status: `COMPLETE`
- Base: `origin/main@77d76bc8fd7567ef140bd113c252fcf02e0aae68`
- Execution boundary: documentation, fail-closed runtime controls, and free
  validation; no paid model run or remote dataset write

## Outcome

Rebuild the repository README around the three decisions a new visitor needs to
make: inspect real results, run the project without credentials, and launch a
small experiment with explicit cost and security prerequisites. Replace remote
diagram rendering and visually weak workflow descriptions with repository-owned
SVG assets, then add a pull-request build gate so the trust claims are backed by
an executable check before merge.

The target reader is a graduate student who is comfortable with a terminal but
has not operated GitHub Actions, Azure workload identity, or Hugging Face dataset
uploads before.

## Falsifiable Hypothesis

Visitors stall because the current README places its runnable path below a long
problem statement and screenshots, while its setup copy mixes no-credential
dashboard use with a credentialed, potentially paid benchmark run. Moving a
three-choice `Start here` block above the narrative, separating those two paths,
and pairing them with local diagrams and verifiable workflow guarantees should
make the first useful action discoverable in the first viewport without hiding
cost, identity, or upload requirements.

## Discriminating Check

Render the README at desktop and narrow widths, then verify that all three entry
points are visible before the problem narrative, every local image loads, all
relative links resolve, and the documented no-credential path passes
`npm run aggregate`, `npm run test:aggregate`, and `npm run build`. Validate the
workflow syntax and confirm pull requests run those same checks without reaching
the Pages deployment step.

## Scope

Allowed implementation files:

- `README.md`
- `README_KR.md`
- `docs/first-experiment.md`
- `docs/first-experiment_KR.md`
- `docs/images/readme-system-map.svg`
- `docs/images/readme-system-map-mobile.svg`
- `docs/images/readme-system-map-ko.svg`
- `docs/images/readme-system-map-mobile-ko.svg`
- `docs/images/readme-first-run.svg`
- `docs/images/readme-first-run-mobile.svg`
- `docs/images/readme-first-run-ko.svg`
- `docs/images/readme-first-run-mobile-ko.svg`
- `docs/images/readme-trust-boundaries.svg`
- `docs/images/readme-trust-boundaries-mobile.svg`
- `docs/images/readme-trust-boundaries-ko.svg`
- `docs/images/readme-trust-boundaries-mobile-ko.svg`
- `batch-runner/core/prepared_fingerprint.py`
- `batch-runner/core/needs_files.py`
- `batch-runner/core/reference_integrity.py`
- `batch-runner/core/repo_bootstrapper.py`
- `batch-runner/core/experiment_config.py`
- `batch-runner/scripts/relay_checkpoint.py`
- `batch-runner/requirements.txt`
- `batch-runner/step1_prepare_tasks.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/step3_format_results.py`
- `batch-runner/step6_report.py`
- focused pipeline test modules
- `scripts/__tests__/onboarding-contract.test.mjs`
- `.github/workflows/batch-run.yml`
- `.github/workflows/deploy.yml`
- `scripts/__tests__/aggregate-runtime-note.test.mjs`
- `.gitignore`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`
- this BOLT record

## Content Architecture

1. Keep the project name and one-sentence benchmark definition compact.
2. Add `Start here` immediately below the badges with three routes:
   live evidence, local dashboard, and the first 3-task experiment.
3. Put a copy-paste local dashboard path before the long project rationale.
4. Add a beginner guide that explains accounts, credentials, expected cost,
   fork settings, OIDC, the smoke YAML, workflow inputs, success signals,
   artifacts, common failures, and cleanup.
5. State that Self-QA is an inference-time reflection signal, not independent
   grading or proof of professional quality.
6. Summarize operational guarantees only where the linked code or workflow
   enforces them today.
7. Move implementation detail below the first-run path and reduce repeated copy.

## Visual Direction

- Use six English and six Korean desktop/narrow-screen hand-authored SVGs with a restrained
  ink, teal, amber, coral, and blue palette; no remote Mermaid rendering,
  gradients, or decorative blobs.
- `readme-first-run.svg`: fork-to-smoke-run path with prerequisites and outputs.
- `readme-system-map.svg`: configuration, execution, artifacts, grading, and
  dashboard ownership boundaries.
- `readme-trust-boundaries.svg`: identity, isolation, validation, and deploy
  controls, with claims tied to repository paths.
- Keep text legible when the image is rendered at 680 px and provide meaningful
  README alt text. SVGs must contain titles/descriptions and no external assets.
- Prefer static SVG over GIF: the flows do not require motion, and static assets
  remain searchable, crisp, reduced-motion safe, and inexpensive to load.

## Truth and Safety Rules

- Canonical public scope is `220 tasks / 9 sectors / 44 occupations`.
- Do not describe inference completion or Self-QA as external quality grading.
- Mark the smoke run as a real API run that may incur provider charges.
- Never ask readers to paste secrets into YAML, source files, logs, or shell
  history; GitHub secrets and federated Azure identity are the supported path.
- Describe the agentic image and production preflight as manual, protected-main
  controls. Do not imply they execute for every baseline smoke run.
- Tie supply-chain claims to reviewed dependency locks, digest-pinned images,
  runtime/attached SBOM verification, and the exact workflow that enforces each.
- Do not imply that `dry_run` avoids inference cost; it skips final publication
  and PR creation, not model calls or Hugging Face bootstrap/checkpoint traffic.

## Implementation Steps

1. Write the bilingual beginner guides from the actual smoke config and
   `batch-run.yml` inputs.
2. Create and inspect twelve localized desktop/narrow-screen SVG assets.
3. Recompose both root READMEs around `Start here`, progressive disclosure, and
   evidence-linked operational guarantees.
4. Split dashboard validation from deployment in `deploy.yml`; run aggregate,
   aggregate tests, browser contracts, and production build on relevant pull
  requests, while keeping artifact upload and Pages deployment out of them.
  Because GitHub suppresses downstream PR events created by `GITHUB_TOKEN`,
  dispatch a validation-only run for the exact automated result-PR head SHA.
  5. Fail closed on mixed Step 1/2 inputs with a canonical prepared-payload
    fingerprint, keep Step 6 strictly pre-grading, and require a model-free report
    fallback plus a proven result PR before HF publication.
  6. Run link, SVG/XML, workflow, aggregate-test, build, and responsive rendering
   checks; correct only defects in this task's slice.
  7. Update this decision record and the canonical completion records.

## Non-Goals

- Do not change inference model calls, grading scores, prompts, or dataset contents.
- Do not dispatch Actions, call model/provider APIs, upload to Hugging Face, or
  deploy Pages solely to validate this change. Repository commit, pull request,
  and merge are the delivery path requested for the completed work.
- Do not turn the README into an exhaustive operator manual; detailed setup
  belongs in the linked beginner guide and batch-runner documentation.
- Do not modify or remove unrelated generated and untracked files in the stale
  VS Code checkout; implementation stays on the clean current-main worktree.

## Acceptance Gates

- The first viewport offers dashboard, local preview, and first experiment
  routes before the problem narrative.
- A beginner can distinguish the free local dashboard path from the credentialed
  paid smoke experiment and can identify every required prerequisite.
- All architecture and workflow diagrams used by the README are local SVGs;
  no `mermaid.ink` URL remains in either root README.
- Every operational guarantee links to an enforcing file or workflow that exists.
- Pull requests execute aggregate, aggregate tests, browser contracts, and
  production build; automated result PRs receive the same read-only validation
  through an exact-SHA dispatch. Pages upload/deploy remain main-only.
- Both READMEs have no broken local links or missing images.
- All SVGs are valid XML, have unique IDs, and render nonblank at desktop and
  mobile widths without clipped text.
- `npm run aggregate`, `npm run test:aggregate`, and `npm run build` pass.
- Workflow validation and `git diff --check` pass.
- No paid, remote, destructive, deployment, or publication action occurs.

## Evidence

| Check | Result |
|---|---|
| Baseline README audit | Start path begins after problem copy and screenshots; remote Mermaid images are used |
| Workflow audit | PR build gate absent; sandbox publication and preflight are manual protected-main controls |
| Static document contract | 56 local links pass; 12 SVGs parse with unique accessibility IDs, intrinsic sizes, and no remote image dependency |
| Visual accessibility | Localized mobile source min font 26px; primary text colors at least 6.04:1; nearest-card/canvas overflow checks pass; 960/961px source transition verified |
| Workflow contract | Both YAML files parse; embedded config/report/PR Python compiles from parsed step scripts; 7/7 workflow and 77/77 aggregate contracts pass |
| Dashboard validation | Aggregate passed (1 experiment, 23 reports, 16 grades, 28 prompt architectures); production build passed |
| Browser contracts | Runtime, integrity, perception, and success suites all passed |
| Backend focused tests | 151 passed after relay lineage, A/B checkpoint, and HF ID fixes; Ruff and `py_compile` clean |
| Backend broad tests | 1,529 passed, 6 skipped, 44 integration tests deselected; only the missing local-parquet selector module excluded |
| Responsive README render | 390-960px selects localized mobile SVGs; 961px+ selects desktop SVGs; zero horizontal overflow |

## Execution-Trust Follow-up

The documentation audit exposed runtime contracts that could not truthfully be
documented without implementation changes. The completed follow-up therefore:

- binds every workflow and relay leg to trusted `main`, the initial source SHA,
  the exact configured dataset ID, and a complete ordered checkpoint task set;
- creates Step 0 targets atomically with `whoami` plus
  `create_repo(exist_ok=False)`, treating only HTTP 409 as an existing target
  and never deleting partial or legacy repositories automatically;
- pins the public source revision and validates the target's exact HEAD in fresh
  staging before local installation. A canonical schema-3 manifest binds the
  ordered tasks, policy signals, model-input projection, and every declared
  reference path, SHA-256, and byte size;
- verifies relay payload bytes at their immutable Hugging Face revision before
  advancing the marker, and confirms cleanup success in the same invocation if
  the CAS response is lost; and
- rejects missing, malformed, reordered, or identity-drifted checkpoints before
  Azure login or model-client construction.

Final local evidence on the rebased implementation:

- backend non-integration suite: **1,638 passed, 6 skipped, 44 deselected**;
- focused Step 0 plus relay suite: **83 passed**;
- frontend aggregate contracts: **84 passed**;
- onboarding contracts: **7 passed**;
- production aggregate/build and all four browser note suites passed;
- `actionlint` 1.7.12, Ruff, `py_compile`, and `git diff --check` passed; and
- six onboarding documents resolved **157 links**, **100 local targets**, **12
  fork-relative Actions routes**, and four SVGs with zero errors.

No workflow dispatch, Azure/model call, Hugging Face write, paid batch run,
grading run, deployment, or publication was used as validation.
| Independent review | UI review approved after glyph/card-boundary fixes; backend review findings drove fingerprint, pre-grading, and publication gates, while final backend signoff requests failed at the review service network boundary |

## Decision

`LOCALLY_VERIFIED` — implementation, all free local acceptance checks, and final
independent review pass. No commit, push, workflow dispatch, Pages deployment,
HF write, model call, or paid action occurred. A natural future result PR must
still confirm that the PR-before-HF chain and validation-only dispatch attach
`validate` to the exact head SHA without creating a Pages deployment.