# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-22
- Status: Grading workflow trust hardening complete; live canary deferred

## Task

- Disable the obsolete grading cost-sweep workflow without deleting its
  historical source or results.
- Harden the active grading workflow without changing its single-job runtime,
  chunk resume, publication, analysis, or follow-up dispatch behavior.
- Pin external actions, remove unused permissions, validate exact-main
  execution, and prevent workflow-dispatch inputs from being interpolated
  directly into shell scripts.

## Result

- Moved `grade-cost-sweep.yml` unchanged from the active workflow directory to
  its May 24 result archive. The historical workflow blob and documentation
  remain available, but GitHub can no longer dispatch the obsolete USD 80-cap
  sweep. Its former live status and trigger commands are explicitly marked as
  archived historical records.
- Kept `grade-run.yml` as one job with `contents: write`, `id-token: write`, and
  `actions: write`; removed only unused `pull-requests: write`.
- Pinned checkout, setup-python, Azure login, and artifact upload to reviewed
  full commit SHAs. Checkout explicitly creates local `main`, tracks
  `origin/main`, and preserves the credential used by the existing result
  publication steps.
- Added pre-checkout validation for workflow-dispatch identity, exact main ref,
  workflow SHA/event SHA equality, safe experiment/config basenames, lowercase
  inference identity, booleans, task limit, resume chunk, and force/resume
  consistency.
- Added post-checkout validation for HEAD, local branch, upstream, remote main,
  credential configuration, and regular non-symlink experiment/config files
  before dependency installation, Azure login, or HF access.
- Routed all eight dispatch inputs used by shell through validated job
  environment variables. No `run:` block interpolates `${{ inputs.* }}`.
- Preserved the rc=7 partial-save/rebase/hash/schema contract, three `git push`
  sites, two self/follow-up dispatches, analysis generation, and artifact path.
- No workflow dispatch, Azure login, HF access/write, model/API call, grading
  run, or paid execution occurred.

## Verification

- Base identity: exact `origin/main@d3fe7f793e202555f6f4df55922282e217494fc6`;
  active grading and sweep runs were zero before implementation.
- Focused workflow/input/archive matrix: **17 passed**. The Bash preflight was
  executed against valid initial/resume inputs and thirteen invalid context,
  traversal, identity, boolean, range, and resume combinations.
- Full Step 8 suite: **114 passed, 0 failed** in 5.02 seconds.
- Workflow invariants: one job, four 40-character action pins, three pushes,
  two `grade-run.yml` dispatches, no input expression in any shell script, and
  unchanged rc=7/schema/hash guards.
- All active workflow YAML and the archived sweep parse successfully. Official
  actionlint v1.7.7 was downloaded outside the repository, matched its published
  SHA-256 checksum, and reported zero diagnostics for `grade-run.yml`.
- Static diagnostics reported zero errors in the workflow and changed Python
  test. `git diff --check` passed.
- `extreme-reasoner` returned `SAFE_WITH_CONDITIONS`; all in-scope conditions
  were implemented. It explicitly classified this same-job check as an
  operational guard rather than a protected security boundary.

## Remaining Work

- Add a repository ruleset for `main` and a protected grading environment before
  treating exact-main validation as a security boundary.
- Design any future read-only/privileged job split separately. It must transfer
  the grade file, resolved inference revision, rc, hashes, and publication state
  without breaking chunk resume, three pushes, or two follow-up dispatches.
- Use a later operator-approved model-free `dry_run` to verify GitHub-hosted
  checkout/upstream/credential behavior. Do not run a paid grading canary solely
  for this hardening change.