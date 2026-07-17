# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-18
- Status: Agentic Sandbox plan approved; implementation pending plan merge

## Task

- Create a dated implementation and experiment plan for a full task-solving
  agentic tool loop in the sandbox.
- Preserve the current sandbox as the paired baseline and keep grading tool
  behavior separate from task-solving behavior.
- Define security, iteration, time, resource, usage, cost, experiment, and
  retrospective gates before writing code or running a model.

## Result

- Added
  `tasks/0717_friday/AGENTIC_SANDBOX_EXPERIMENT_PLAN.md` beside the existing
  Track 2 cohort document without modifying that experiment record.
- Fixed the proposed treatment as a separate `agentic_sandbox` execution mode.
  The MVP supports Azure/OpenAI Responses function calls and preinstalled
  capabilities only; runtime package installation, network, root, arbitrary
  shell, Anthropic support, and capability-image selection are deferred.
- Defined six model-visible tools: workspace inspection, environment inspection,
  Python execution, ffmpeg execution, artifact inspection, and deterministic
  finalization. Plain assistant text cannot complete a task.
- Fixed the persistent workspace design: one disposable container per task,
  `/inputs:ro`, quota-backed `/work` tmpfs, fixed nonzero UID, read-only rootfs,
  dropped capabilities, no network/IPC, syscall-filtered generated Python, and
  host-only source/control state and verified artifact snapshots.
- Preregistered model/tool/finalization/repetition budgets and fail-closed path,
  usage, verification, and security behavior.
- Defined optional agentic observability that excludes raw prompts, code,
  arguments, process output, image payloads, credentials, and absolute paths.
- Defined non-paid scripted and real-image Docker validation, legacy report/UI
  omission checks, broad regression, frontend build, and responsive fixture
  verification. Actual API/model call count must remain zero during
  implementation.
- Fixed an outcome-free, seeded, stratified selector contract that emits
  disjoint five-task canary and twenty-task diagnostic cohorts in one atomic
  pre-outcome step. Exact task IDs and source identities are not yet frozen;
  they must be generated, reviewed, and committed at a separate paid gate with
  projected cost, hard caps, abort procedure, and explicit owner approval.
- Added evidence, cost, and incident ledgers plus the structure for
  `AGENTIC_SANDBOX_RETROSPECTIVE.md` so later experiment notes can distinguish
  preregistered decisions from post-run interpretation.
- Hardened the live boundary around separate credential and compute planes,
  byte-identical baseline/treatment substrates, isolated artifact verification,
  crash-safe shared budgets, signed single-use paid authorization, authenticated
  anti-replay envelopes, and input-byte/provider-classification identities.
- Preserved the concurrent Track 2 state from current `main`: its atomic-save
  fix and model-free preflight passed, while a second paid Stage B attempt still
  requires explicit owner deviation approval and remains out of scope here.

## Concurrent Track 2 Guard

- Rejected paid run `29591036089` has no resumable artifact; its unpersisted
  usage remains conservatively booked at USD 3.81 raw.
- Atomic-save fix PR #99 is merged and model-free preflight `29599249906`
  passed against the corrected grader/output identity.
- A fresh `resume=false` Stage B attempt remains prohibited until the owner
  explicitly approves the deviation and cumulative USD 10 cap. This Agentic
  plan does not grant or inherit that approval.

## Verification

- Plan rebased for merge onto
  `main@71902db3904a358e6f832caf8f39e807047f9bdf`.
- `first-reviewer` and `extreme-reasoner` independently approved the final plan
  with no mandatory blockers; both explicitly denied live model/API approval.
- Focused documentation, security-gate, selection-formula, endpoint, and
  Track 2 preservation checks passed with `git diff --check` clean.
- Existing `tasks/0717_friday/TRACK2_COHORT_EXPANSION_EXPERIMENT.md` is
  preserved.
- No implementation code, workflow, model call, package installation, paid run,
  or remote project mutation was performed while drafting the plan.

## Remaining Work

- Merge the approved docs-only plan.
- Create a fresh implementation branch from the plan merge SHA and implement
  through the non-paid validation gate.
- Stop before live model/API execution until the paid gate receives explicit
  approval.
