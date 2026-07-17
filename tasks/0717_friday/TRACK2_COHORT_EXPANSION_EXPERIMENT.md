# Track 2 Cohort Expansion Experiment

- Date: 2026-07-17
- Status: `PREFLIGHT_BLOCKED`
- Owner: repository operator
- Experiment family: rubric grading / harness-owned perception
- Prior accepted run: GitHub Actions `29435264166`

## Why This Experiment Exists

The one-task exp003 canary proved that the current grader can render an XLSX,
call visual perception once, recover one empty final response without exposing
tools, preserve complete usage accounting, and persist a valid grade. It did
not prove that the same behavior holds across more rubric items, larger support
bundles, PDF primaries, DOCX formatting paths, or mixed deliverables.

This experiment expands scope in two gated cohorts. It is not a model-quality
claim and it is not a full 220-task benchmark run. The primary outcome is
runtime reliability under a broader, immutable workload.

## Research Questions

1. Does finalization recovery keep `judge_error_rate == 0` beyond the single
   canary task?
2. Does task-level usage remain complete when tool loops, rendering, and
   perception occur across a larger cohort?
3. Do selected deliverables and visual provenance remain confined to the
   pinned task manifests with no image payload or absolute path persisted?
4. Does wall-clock and effective cost scale closely enough to justify a later
   220-task run?
5. Which file classes or rubric shapes first trigger fail-closed behavior?

## Fixed Identity

| Field | Fixed value |
|---|---|
| Experiment | `exp003_GPT52Chat_baseline_runner_exec` |
| Inference repository revision | `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f` |
| Rubric revision | `11e7900cdcac61bc4daf59e65feb238acda98fbf` |
| Judge | `gpt-5.4-mini` |
| Reasoning effort | `medium` |
| Prompt | `v2.2` |
| Source branch | `main` |
| Authentication | Azure OIDC only |
| Resume | only workflow-managed durable resume for the same identity |

The dispatch must record the exact `main` SHA and grader source hash before any
paid call. A source, rubric, inference, renderer, task-order, or config identity
mismatch is a pre-call stop.

## Baseline

Accepted canary `29435264166` graded task
`83d10b06-26d1-4636-a32c-23f92c57f30b`:

| Metric | Observed |
|---|---:|
| Rubric items | 38 |
| Main calls | 127 |
| Perception calls | 1 |
| Render calls | 1 |
| Input tokens | 2,834,829 |
| Output tokens | 43,822 |
| Cached tokens | 913,152 |
| Raw / effective estimate | USD 0.75 / USD 0.64 |
| Judge errors | 0 |
| Usage complete | true |
| Finalization recovery | 1 empty response recovered |

The score (`50.63%`) is descriptive only. This experiment evaluates harness
reliability, not whether that score is substantively correct.

## Immutable Cohorts

The pinned inference ordering is part of the experimental identity. The task
IDs below must match the first rows downloaded from the pinned revision.

### Stage A: Three-Task Expansion

1. `83d10b06-26d1-4636-a32c-23f92c57f30b` - XLSX primary + XLSX reference
2. `7b08cd4d-df60-41ae-9102-8aaa49306ba2` - XLSX primary + XLSX reference
3. `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` - XLSX primary + PDF/XLSX support bundle

Historical rubric surface: 153 items. Stage A is the cheapest check that adds
two unseen tasks and a multi-file support bundle while retaining deterministic
ordering.

### Stage B: Ten-Task Mixed-Format Expansion

Stage B includes Stage A plus:

4. `43dc9778-450b-4b46-b77e-b6d82b202035` - PDF primary + PDF bundle
5. `ee09d943-5a11-430a-b7a2-971b4e9b01b5` - XLSX primary + XLSX/TXT bundle
6. `f84ea6ac-8f9f-428c-b96c-d0884e30f7c7` - DOCX primary
7. `a328feea-47db-4856-b4be-2bdc63dd88fb` - DOCX primary
8. `27e8912c-8bd5-44ba-ad87-64066ea05264` - DOCX/PDF primaries + PNG support
9. `17111c03-aac7-45c2-857d-c06d8223d6ad` - PDF/XLSX primaries
10. `c44e9b62-7cd8-4f72-8ad9-f8fbddb94083` - DOCX/PDF/XLSX primaries

Historical rubric surface: 435 items. Stage B adds PDF rendering, DOCX
formatting, images, multiple primaries, and mixed child routing.

## Artifact Isolation

The accepted one-task canary artifact must not be overwritten. Create two
configs that inherit the behavior of `default_v2_mini.yaml` but use distinct
`config_name` values and therefore distinct output identities:

- `validation_v2_mini_cohort3.yaml`
- `validation_v2_mini_cohort10.yaml`

Only `config_name` and descriptive metadata may differ from the baseline
configuration. A semantic config diff is a stop.

## Model-Free Preflight

Before each dispatch, record:

- exact ordered task IDs from the pinned inference payload;
- selected primary/support paths per task;
- rubric item and deterministic-precheck counts;
- planned text, formatting, mixed, and visual routes;
- expected render and perception calls;
- renderer fingerprint requirement;
- output path and full identity hashes;
- confirmation that no grade workflow is queued or running.

The planned render/perception count is an acceptance value, not an estimate.
Do not dispatch until it is written into the stage log below.

### Initial Preflight Result

The pinned/local task order and the historical 220-task grade order match for
all first 10 IDs. Current routing code produced:

| Cohort | Items | Prechecks | Text | Formatting | Visual | Audio | Mixed | Planned render/vision calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stage A (3) | 153 | 9 | 141 | 6 | 5 | 1 | 0 | 5 |
| Stage B (10) | 435 | 21 | 400 | 16 | 17 | 1 | 1 | 27 |

Preflight is blocked by Stage A task 2, rubric item 46:

> Band and Crew (Fees & Per Diem) includes Sound Technician: 8,256 USD,
> attributed to the tour manager.

The selected path is an XLSX, but the keyword `sound` routes the item to audio
and suggests `probe_audio`. This is a file-incompatible false positive, not an
audio grading requirement. Before any paid dispatch, runtime routing must
downgrade audio classifications to text when none of the selected paths has a
supported audio extension. The focused regression must prove:

- `Sound Technician` + XLSX routes to text;
- a real audio criterion + WAV/MP3 remains audio;
- mixed child routing preserves real audio children;
- route totals become 142 text / 6 formatting / 5 visual for Stage A and
   401 text / 16 formatting / 17 visual / 1 mixed for Stage B;
- planned render/vision calls remain 5 and 27 respectively.

No paid run may be dispatched while this blocker is open.

## Stage Gates

### Stage A Acceptance

- exact task set and order: 3/3;
- `error_tasks == 0`;
- `judge_error_rate == 0`;
- every task and summary has `usage_complete == true`;
- actual render/perception counts equal preflight counts;
- every visual item has `perception_called == true` and relative-path
  provenance;
- no base64/data URL, absolute path, path traversal, or cross-task path in the
  persisted JSON;
- no API-key fallback, secret output, child workflow, or unrelated dispatch;
- effective cost below USD 3 and total wall-clock below 120 minutes.

### Stage B Acceptance

- Stage A passed without qualification;
- exact task set and order: 10/10;
- `error_tasks == 0`;
- `judge_error_rate == 0`;
- every task and summary has `usage_complete == true`;
- actual render/perception counts equal preflight counts;
- provenance confinement checks pass for every visual parent and child;
- no unexpected resume identity change or output collision;
- effective cost below USD 10 and total wall-clock below 240 minutes.

## Stop Conditions

Stop the current stage and do not advance when any of the following occurs:

- workflow input, source SHA, rubric SHA, task order, config, or output identity
  differs from this plan;
- renderer/OIDC/HF preflight fails;
- Step 8 exits with a runtime failure or incomplete usage;
- any `judge_error` remains after the bounded retry;
- a planned visual route does not call perception exactly once;
- persisted provenance contains payload bytes or a non-relative path;
- the stage exceeds its cost or wall-clock cap;
- an unplanned grade workflow appears.

Fail-closed diagnostic artifacts are evidence. They must be downloaded and
audited, but they must not be committed as accepted grades.

## Execution Sequence

1. Merge this preregistration plan.
2. Generate and validate the two isolated grading configs.
3. Run model-free preflight and fill the Stage A planned values.
4. Dispatch Stage A once from current `main`.
5. Audit the committed grade or fail-closed artifact against every gate.
6. Record Stage A results and decision in this document.
7. If Stage A passes, repeat preflight and dispatch Stage B once.
8. Record Stage B results and the recommendation for or against a full run.
9. Update `CHANGELOG.md` and `tasks/LATEST_TASK_RESULT/README.md` after each
   mergeable result, without publishing provider-account or organization budget
   details.

## Stage A Log

| Field | Planned / observed |
|---|---|
| Main SHA | pending |
| Grader source hash | pending |
| Config hash | pending |
| Output path | pending |
| Ordered task IDs | pending preflight |
| Rubric items / prechecks | 153 / 9 |
| Route counts | blocked: 141 text / 6 formatting / 5 visual / 1 false audio |
| Render / perception calls | 5 / 5 planned |
| Run ID | not dispatched |
| Result | not started |
| Raw / effective cost | not started |
| Decision | `HOLD_ROUTING_FIX_REQUIRED` |

## Stage B Log

| Field | Planned / observed |
|---|---|
| Main SHA | pending |
| Grader source hash | pending |
| Config hash | pending |
| Output path | pending |
| Ordered task IDs | pending preflight |
| Rubric items / prechecks | 435 / 21 |
| Route counts | blocked: 400 text / 16 formatting / 17 visual / 1 false audio / 1 mixed |
| Render / perception calls | 27 / 27 planned |
| Run ID | not dispatched |
| Result | not started |
| Raw / effective cost | not started |
| Decision | `HOLD` |

## Retrospective Notes

After each stage, capture facts before interpretation:

1. What happened, in timestamp order?
2. Which guardrail activated, and was it expected?
3. Which task/file/rubric shape dominated calls, latency, or cost?
4. Did recovery change only reliability, or also the verdict distribution?
5. What evidence supports advancing, narrowing, or stopping?
6. Which observations are benchmark facts, and which remain hypotheses?

Do not rewrite failed attempts out of the record. The sequence of failure,
diagnosis, bounded correction, and rerun is part of the experiment result.