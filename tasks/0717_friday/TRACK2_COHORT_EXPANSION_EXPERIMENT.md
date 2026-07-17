# Track 2 Cohort Expansion Experiment

- Date: 2026-07-17
- Status: `STAGE_B_ATOMIC_FIX_PREFLIGHT_PASSED_RERUN_APPROVAL_PENDING`
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
- rubric item and automatic-precheck counts, expected to remain zero;
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
- all six grader-supported audio suffixes remain selectable and probeable;
- extensionless targets remain conservatively audio, while a known unsupported
   suffix downgrades to text;
- route totals become 142 text / 6 formatting / 5 visual for Stage A and
   401 text / 16 formatting / 17 visual / 1 mixed for Stage B;
- planned render/vision calls remain 5 and 27 respectively.

No paid run may be dispatched while this blocker is open.

### Blocker Resolution

Runtime routing now downgrades an audio-keyword decision to text when selected
paths have known suffixes but none is a supported audio type. WAV, MP3, FLAC,
OGG, M4A, and AAC targets remain audio. Selection, routing, and
`read_deliverable` now import one shared extension set. The exact
`Sound Technician` XLSX case, every supported primary format, extensionless
paths, and known unsupported suffixes are covered by deterministic tests.

Post-fix recomputation produced:

| Cohort | Items | Prechecks | Text | Formatting | Visual | Audio | Mixed | Planned render/vision calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stage A (3) | 153 | 9 | 142 | 6 | 5 | 0 | 0 | 5 |
| Stage B (10) | 435 | 21 | 401 | 16 | 17 | 0 | 1 | 27 |

Validation results at that audio-only checkpoint:

- perception-routing unit suite: 33 passed;
- selector, mixed visual-child, visual-inventory, and tool-dispatch suite: 50
   passed before the shared audio-format follow-up;
- safe-precheck, routing, exact-planner, selector, config, Step 8, and
   visual-inventory affected suite: 260 passed;
- broad non-integration suite: 1,189 passed, 2 skipped, 37 deselected;
- cohort config baseline-parity and output-isolation tests: 2 passed.

The blocker is closed. Paid dispatch remains pending until this implementation
is merged and its `main` SHA is written below.

## Stage A Attempt 1 Result

- Run: `29559615083`
- Source `main`: `6b48f3dda87a5e9b752b1eced7bf9fa4f94777f5`
- Workflow conclusion: success in 40m12s
- Grade commit: `baafd26841e9bcb29df3dfcfc978b83ddc9b43ac`
- Analysis commit: `f14af9cbafed3d6f774981f499c42b2ea1b24817`
- Runtime: 3/3 tasks, 0 task errors, 0 judge errors, complete usage
- Calls: 490 main, 4 perception, 4 render
- Tokens: 4,369,788 input, 154,166 output, 1,914,368 cached
- Cost estimate: USD 1.26 raw / USD 1.02 effective
- Wall-clock between task timestamps: 21.4 minutes
- Finalization recovery: seven empty max-output responses recovered
- Persisted payload scan: no image payload, data URL, absolute path, or true
   traversal segment

### Gate Decision

**FAIL. Do not advance to Stage B.** The preregistered 5/5 call gate was itself
wrong: route-only preflight counted a `chart-of-accounts` content criterion as
a visual chart and did not execute deterministic prechecks. Exact planning now
correctly predicts the observed 4/4 calls.

The mismatch exposed a more serious runtime issue. The same COA criterion was
then matched by the broad `file_extension` precheck and passed solely because
the selected output was also XLSX. Six neighboring criteria comparing output
data with PDF source invoices were similarly auto-failed because the selected
output was not PDF. These seven verdicts did not evaluate the requested
content, so the artifact remains rejected even though its runtime counters were
otherwise valid.

The committed Stage A grade and analysis are removed by the safe-precheck fix.
They remain available in Git history and `/tmp` audit evidence, but are not
accepted experiment results.

## Safe-Precheck Correction

- Disable automatic natural-language prechecks. Filename, extension, worksheet,
   file/count, page, and word requirements all go to the judge so a partial
   regex match cannot decide a compound or negated criterion.
- Keep the dormant precheck entry point fail-safe: a stale pattern ID returns
   no verdict and therefore cannot score an item.
- Treat `chart-of-accounts` as accounting content, not a visual-chart keyword,
   unless another explicit visual keyword is present.
- Mark active grading configs with `precheck_patterns_version: v2` as an
   identity marker only; the field is not a runtime feature switch.
- Use `scripts/preflight_track2_cohort.py` to run the real selector, routing,
   and shared visual-preflight validator before counting judge-bound routes and
   visual calls.
- Require a clean worktree and exact expected planner, repository, source,
   config, grader, rubric, and ordered-task identities. `GITHUB_SHA`, when set,
   must equal the checked-out `HEAD`.

Exact Stage A planner result after the correction:

| Metric | Planned |
|---|---:|
| Rubric items | 153 |
| Precheck candidates / resolved / fallback | 0 / 0 / 0 |
| Judge-bound routes | 143 text / 6 formatting / 4 visual |
| Planned main judgments | 153 |
| Planned render / perception calls | 4 / 4 |
| Planner errors | 0 |

The machine-readable plan also records planner contract
`track2-selection-ok-v1`, planner source hash
`1a7cca75e685d5c2202f4753ae39255fac196dcd27d5581af80976ae60efb147`, clean
implementation commit `acba15bcc56fdc311a7cecf5c847378f69352ede`, exact
source/rubric/config identities, and task-level plans. The planner must run
again on the merged `main` SHA before dispatch.

Final correction validation:

- no-precheck grader/planner focused suite: 65 passed;
- shared visual-validator/planner parity suite: 19 passed, 37 deselected;
- planner identity suite: 14 passed;
- corrected split-selector regressions: 3 passed;
- broad non-integration suite: 1,204 passed, 2 skipped, 37 deselected;
- independent grading-engineer review found no remaining code correctness
   blocker and independently reproduced the broad result.

## Stage A Attempt 2 Result

- Run: `29572067428`
- Source `main`: `fd6d5267fcc15afc144d8de93dc98b0e8b52ed2f`
- Workflow conclusion: success in 44m12s
- Grade commit: `9473d9021fc4583a68a4bc338c8aecf4aa5bffdd`
- Analysis commit: `defe85a6bba87181e77f10c9503105104b12e316`
- Runtime: 3/3 tasks, 153/153 judge-bound items, 0 task errors, 0 judge
   errors, 0 score-excluded items, and complete item/task/summary usage
- Routes: 143 text, 6 formatting, 4 visual; 0 automatic prechecks
- Calls: 532 main API calls, 4 perception calls, and 4 render calls
- Tokens: 4,545,150 input, 177,563 output, and 1,955,328 cached
- Cost estimate: USD 1.32 raw / USD 1.08 effective
- Artifact wall-clock: 24.9 minutes
- Finalization recovery: nine empty max-output responses recovered with the
   bounded tool-free retry; no retry remained as a judge error
- Persisted artifact: schema valid, exact task order and identities, four
   task-confined relative provenance entries, and no image payload, data URL,
   absolute path, traversal segment, cross-task path, or secret marker

### Acceptance Decision

**PASS. Stage B model-free preflight may proceed.** Actual routes and the 4/4
render-perception counts exactly matched the clean merged-main plan. All Stage
A runtime, usage, provenance, identity, cost, and wall-clock gates passed.
There was no resume, child workflow, unrelated dispatch, or API-key fallback.
Independent grading-engineer review confirmed each gate and found no blocker.

The observed score (`36.14%`; 43 pass / 99 fail / 11 partial) is descriptive
only and is not part of this runtime-reliability acceptance decision. Stage B
paid dispatch remains prohibited until its first-10 exact preflight fixes the
new merged `main` identity and returns no errors.

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
| Main SHA | `fd6d5267fcc15afc144d8de93dc98b0e8b52ed2f` |
| Grader source hash | `9b8a9ae3288ec3e9c7608ea8af4ced3e77f2e27956da426da5b63d3b0acee01e` |
| Config hash | `0a8e1f421ad46dc2` |
| Output path | `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__validation_v2_mini_cohort3__cfg_0a8e1f421ad46dc2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_9b8a9ae3288ec3e9__v2.2.json` |
| Ordered task IDs | verified first 3 pinned IDs |
| Rubric items / prechecks | 153 / 0 candidates / 0 resolved / 0 fallback |
| Route counts | 143 text / 6 formatting / 4 visual |
| Render / perception calls | 4 / 4 planned and observed |
| Run ID | attempt 1 `29559615083` rejected; attempt 2 `29572067428` accepted |
| Result | 3/3 tasks, 0 errors, complete usage, exact provenance gates |
| Raw / effective cost | USD 1.32 / USD 1.08 |
| Decision | `PASS_STAGE_B_PREFLIGHT_ALLOWED` |

## Stage B Log

| Field | Planned / observed |
|---|---|
| Main SHA | paid attempt 1 `6bdcfcf9dd4d5feb8890e13d9f69baefc4162b38`; corrected preflight `3af01d423518d3a344b45cf1cb1a40bcba499d14` |
| Grader source hash | paid attempt 1 `ab8704b10f2e39a26bbb443b49c8c4e1a2697a6a31c74258d4af8ebc3ba8b551`; corrected `011ef05cf7f7a951b9bc2322888605549ee4fa9486c775f4154b89c83526d270` |
| Config hash | `b11acba425087d85` |
| Output path | corrected `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__validation_v2_mini_cohort10__cfg_b11acba425087d85__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_011ef05cf7f7a951__v2.2.json` |
| Ordered task IDs | verified first 10 pinned IDs |
| Rubric items / prechecks | 435 / 0 |
| Route counts | 402 text / 16 formatting / 16 visual / 1 mixed; 0 audio |
| Render / perception calls | 26 / 26 planned; 0 audio |
| Run ID | paid attempt 1 `29591036089` rejected; post-fix preflight `29599249906` passed |
| Result | 10/10 graded; atomic temp filename overflow before JSON persistence |
| Raw / effective cost | no usage artifact; attempt 1 booked at conservative raw estimate USD 3.81 |
| Decision | `OWNER_DEVIATION_APPROVAL_REQUIRED_FOR_PAID_ATTEMPT_2` |

The local shell has no private dataset token, so a selective pinned download
failed closed with HTTP 401 before any model/Azure call and left no partial
tree. Stage B preflight will use the repository `HF_TOKEN` only inside the
main-only model-free workflow. That workflow downloads the exact first-ten
source prefix, has no Azure or Step 8 path, and records a hash-locked environment
and plan artifact. Any precheck, audio route, planner error, identity mismatch,
or active grade workflow remains a paid-dispatch stop.

### Stage B Preflight Attempt 1

Run `29583415563` completed the main-only input, checkout, hash-lock, identity,
and exact first-ten private download gates without Azure or model calls. The
planner emitted a 435-item plan with zero prechecks/audio and failed on nine
task-10 organization-chart criteria. All nine selected the same DOCX/PDF/XLSX
primary bundle; rejecting the supported PDF/XLSX because DOCX was also present
was a renderer-boundary bug, not a cohort identity error.

The correction filters harness visual prepass paths to supported formats while
keeping DOCX visible to the main judge. Unsupported-only visual children still
fail before any sibling render, task budget, or main call. Runtime and planner
share this ordering. Artifact re-evaluation predicts 436 main judgments and
26/26 render-perception calls with one filtered DOCX path and no errors. These
remain planned values until a clean merged-main preflight rerun confirms them.

### Stage B Corrected Preflight Result

Run `29589077065` passed from clean `main` commit
`51839d64ea854a0de1420beb7541b369f55bea6e` in 40 seconds. Its plan artifact
SHA-256 is
`db40b02e08f5c40a62f4b7dd85be12c69732da7b25c8c11f4224485953406b9d`.
All pinned repository/planner/config/grader/inference/rubric identities and the
exact first-ten task order matched. The plan contains 435 items, 436 main
judgments, 402 text / 16 formatting / 16 visual / 1 mixed routes, 26 render and
26 perception calls, zero prechecks, zero audio routes, and zero errors.

The one filtered path is
`Briefing_Note_FTE_Reductions_Administrative_Support_Services.docx`. It remains
selected and visible to the main judge for nine organization-chart criteria;
harness perception uses the sibling PDF organization chart and XLSX FTE report.
All planned paths are relative and task-confined. Recursive artifact audit found
no payload, data URL, absolute path, traversal, cross-task path, or secret
marker. The Python 3.11.9 environment matched all 27 locked packages and did not
contain Azure/OpenAI/datasets/pytest.

Independent grading-engineer review passed every artifact gate. Stage A-based
cost scaling estimates USD 3.77 raw / USD 3.07 effective and 71-83 minutes,
below the Stage B USD 10 / 240-minute caps. These are planning estimates; actual
cost, time, usage, provenance, judge errors, and 26/26 calls must be audited from
the paid Stage B artifact. The result-record merge changes only repository
documentation, so a final model-free run on that new `main` SHA must confirm the
same plan before dispatch. An active grade workflow remains a stop.

### Stage B Paid Attempt 1

Run `29591036089` executed once from `main` commit
`6bdcfcf9dd4d5feb8890e13d9f69baefc4162b38`. All ten task progress lines were
printed over 1h25m58s and seven empty max-output finals recovered with the
bounded tool-free retry. No runtime, task, or judge error appeared before
persistence.

At the task-10 partial-save boundary, `NamedTemporaryFile` failed with
`OSError: [Errno 36] File name too long`. The final filename was 242 bytes and
valid; the legacy hidden prefix plus random component and `.tmp` made the temp
component 256 bytes, one over Linux `NAME_MAX`. Step 8 exited 1. No grade JSON,
analysis, commit, durable resume, child dispatch, or artifact exists, so this
attempt is rejected rather than quality-scored.

The correction hashes the final basename into a bounded temp prefix while
preserving same-directory atomic replace and the public output template. The
actual failed-run usage cannot be recovered. For the Stage B cap, attempt 1 is
conservatively counted at USD 3.81 raw, the higher preflight sensitivity
estimate. A fresh rerun at the same ceiling would produce USD 7.62 cumulative
estimated raw spend, below USD 10. Because the preregistration allowed one paid
dispatch, a second attempt is a deviation and requires explicit owner approval
after merge, clean-main preflight, and active-run checks.

### Atomic-Fix Preflight Confirmation

PR #99 merged the bounded temp-name fix as
`3af01d423518d3a344b45cf1cb1a40bcba499d14`. Model-free run `29599249906`
passed from that clean `main` in 42 seconds with corrected grader source hash
`011ef05cf7f7a951b9bc2322888605549ee4fa9486c775f4154b89c83526d270`.
Plan artifact SHA-256 is
`76f514bff56c2d2b32ac2b21325f7092542d7538b6da39bd1cd038e87a402faa`.
After normalizing repository/grader identity, its entire plan JSON is identical
to the previously accepted first-ten plan: 435 items, 436 main judgments,
402/16/16/1 routes, 26/26 render-perception, one filtered DOCX path, and zero
prechecks/audio/errors. The locked environment is byte-identical. No paid run
was started. Explicit owner approval remains the only dispatch authorization
missing; active workflow state must still be checked immediately before use.

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