# GHCP Sol fixed-five Actions gate (local draft)

Owner decision 2026-10-24 00:01: use one GitHub Actions standard
`ubuntu-24.04` runner job per task. No nested VM or `/dev/kvm` prerequisite.
This draft does not grant push, dispatch, paid inference or grading approval.

## Existing path surveyed

| Workflow | Inputs and task layout | Credentials and retained evidence |
| --- | --- | --- |
| `agentic-v2-stage-run.yml` | `stage`, `mode`, `isolation`, `plan`, `run_id`, `resume_from_github_run`, `comparison_reviewed_source_sha`; free planning, paid shard matrix, collection and comparison admission. Planner packs up to 13 tasks/shard, so advance-check five normally share one shard/job. | HF_TOKEN for pinned input fetch, Azure OIDC client/tenant/subscription IDs and Foundry endpoint; GITHUB_TOKEN for resume downloads, paid job permissions include actions read and OIDC. Uploads the full run directory including hidden exec streams, separate host proofs and cost rollup. **Do not reuse its broad artifact upload for private inputs.** |
| `agentic-v2-stage-a-probe.yml` | `mode=dry-run/paid`; free check then one paid probe task, not the five-task run. | HF_TOKEN, Azure OIDC and Foundry endpoint. Paid artifact is metadata-only model-call record, not prompt/reply/reasoning text. Even its free job fetches the dataset; it is not this card's input-free rehearsal. |
| `gpt54-time-budget-first-v2.yml` | `reviewed_source_sha`, `reviewed_source_tree`, `request_sha256`, `request_json`; one source-bound registered task/job, with no replay. | Validates before credentials; HF private input/claim/retention and Azure OIDC separated by phase. Only validated `completion.json` is uploaded; canonical outputs remain private. This is the stronger privacy pattern reused here. |
| `agentic-sandbox-preflight.yml` | Image/SBOM/AppArmor inputs; self-hosted model-free containment checks. | No model credential permitted. Not the selected standard-runner execution route. |

The surveyed V2 workflows contain no explicit `::add-mask::` step.
GitHub's masking of configured secrets is not a privacy boundary for task
wording, reference contents, tool output or generated deliverables. The new
route supplies no secrets, prints only fixed status, reads only the public
score-free catalogue, and uploads exactly one generated `capture.json` per
task. It never uploads a directory, raw stream or file hashes.

This is an additive sibling in the existing `.github/workflows/agentic-v2-*`
path, reusing its plan-to-matrix structure and pinned checkout/Python/artifact
actions. It does **not** invoke the paid V2 conversation runner, Firecracker
boot action, Azure route, or legacy shard/resume logic; those would inherit
unapproved spending, private capture and obsolete VM requirements.

## Fixed cohort and grading contract

`core/execution_envelope_tasks.py::select_advance_check_tasks` derives the five
ordered IDs from `experiments/execution_envelope/gdpval_task_catalog.json`.
`advance_check_plan.yaml` pins the same order and input versions.
`experiments/execution_envelope/gpt56_sol_ghcp_codex_vm_gate.yaml` binds the
GHCP identity, original-input policy, inherited developer instructions and
grader policy. That older inert VM prerequisite contract remains unchanged;
its VM/reset blockers are not assertions about this new Actions target.

The grader template is
`grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml`: rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, prompt v2.2, Sol/Max judge,
one pass/task, grade schema 1.4. The GHCP gate uses only its policy blocks,
**not** its 220-task rerun identity. Five-task inference identity, original
input verification and grader validation remain unresolved. Nothing is graded.

## Local rehearsal and capture

From `batch-runner`, `python3 ghcp_sol_actions_gate.py --matrix` emits the
five-task matrix. For each returned ID, run:

```bash
python3 ghcp_sol_actions_gate.py --dry-run true --task-id TASK_ID \
  --state-root /absolute/fresh/parent/ghcp-sol-gate
python3 -m pytest -q tests/test_ghcp_sol_actions_gate.py
```

The state-root parent must exist. Each task gets a fresh directory; reuse
refuses. `private/` contains empty transcript/tool-call/command streams, empty
input/output hash arrays, a dry-run exit record and an empty `files/` directory.
These are path placeholders, **not** real input staging or transcript evidence.
Only `capture.json` is artifact-eligible; it contains relative logical paths,
requested settings, actual Python/OS versions and explicit unavailable CLI/
served values. Local execution does not prove the requested hosted image ran.

Proposed paid caps are 1200 seconds/task (the V2 stage cap), 64 model turns/task
(draft choice), zero retries; neither approval nor live enforcement is claimed.
The dry-run workflow enforces 60 seconds/process and five minutes/job with
zero model turns. Unknown usage/cost/grade stay null, never inferred as zero.
`dry_run=false` exits 2 before input reads, capture or client construction.

## Questions blocking paid execution

- How are scoped GHCP/Copilot credentials supplied, kept outside model tools,
  and disposed of on standard Actions runners? Is this unattended use supported?
- Which supported route actually selects the Codex agent harness, pinned CLI/
  SDK versions, Sol model, Max effort and 1M context without fallback? What
  independent served metadata proves each rather than repeating requested values?
- How are original prompts/references verified and staged privately, and raw
  transcript/tool/file captures retained privately without leaking in logs,
  artifacts, action diagnostics, credentials or caches?
- What network/tool permissions, budget/usage policy, paid timeout/turn/tool/
  token caps, cancellation handling and no-retry admission are approved?
- What five-task inference/grader identity, judge validation, repeat/variance
  plan and pass/fail criteria govern the decision? No quality result follows
  from this wiring rehearsal or from these five cases alone.
- Who reviews the exact source and authorizes push, hosted dry-run dispatch,
  and separately paid inference/grading? All remain unapproved on this card.
