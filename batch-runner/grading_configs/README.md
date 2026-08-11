# Grading configs

## Active configs (top level)

| file | path | grader path | when to use |
|---|---|---|---|
| `default_v2_sol_max.yaml` | tool-calling judge | v2 (`ToolCallingJudge` via `judge.tools.read_deliverable`) | **Production default.** GPT-5.6 Sol 1M Max for main, visual, and bounded finalization; gpt-audio-1.5 for audio perception. |
| `default_v2.yaml` | tool-calling judge | v2 | Historical gpt-5.4 medium comparison identity. Pass explicitly when reproducing that condition. |
| `regrade_exp003_v2_mini_score_excluded.yaml` | tool-calling judge | v2 | Full-220 exp003 rerun only. Pins score-excluded semantics, the historical mini judge condition, rubric commit, inference revision, and exact task count. |
| `regrade_exp003_v2_sol_max_score_excluded.yaml` | tool-calling judge | v2 | Planned full-220 exp003 Sol Max rerun. Pins score-excluded semantics, production judge/perception settings, rubric commit, inference revision, and exact task count. |
| `validation_exp003_v2_sol_max_anchor4.yaml` | tool-calling judge | v2 | Paid four-task Sol Max anchor with pinned diagnostic-error and visual/audio coverage, plus the same runtime semantics and source identities as the planned full rerun. |
| `default_gpt5pro.yaml` | text-extract judge | v1 (`Judge` / `BatchJudge`) | Historical mini/text-extract comparison identity. Pass explicitly only for provenance-compatible analysis. |

`grade-run.yml` defaults to `default_v2_sol_max.yaml`. The 1.05M context window
belongs to the deployment and is not represented by a synthetic request field.
There is no automatic hybrid follow-up in the active workflow.

The workflow itself defaults to `dry_run: true`. Any non-dry invocation must
set `paid_approval: true` and pass the protected `grading` GitHub Environment.
If a time-bounded run needs another chunk, the exact config, inference revision,
task limit, and paid-approval input are inherited by the continuation. Each new
chunk is a separate workflow run and requires a fresh protected Environment
approval. Model prices are not guessed: grade payloads and analyses remain
explicitly `unpriced` until verified FDPO rates are configured.

## Provenance and diagnostic scopes

The grading downloader requires `inference_provenance.json` by default and
binds it to the embedded prepared fingerprint, ordered tasks, and Azure AI
routes. `--allow-legacy-missing-provenance` is an explicit local-analysis
override, not a publishable grading path. The four-task Sol Max anchor is the
only active config that declares `rerun_identity.allow_legacy_missing_provenance`.
Its source predates the sidecar requirement, so the downloader permits a
confirmed remote sidecar 404 only when the workflow experiment and both the
requested and resolved revisions exactly match its pinned lowercase SHA. Any
embedded routes, sidecar validation error, auth/network/local-file error, or
other config remains fail-closed. The resulting grade stays diagnostic and
persists `source_azure_ai_provenance_status: legacy-missing`; the full-220 Sol
Max config has no allowance.

Runs selected with `--tasks` or `--limit`, plus the legacy override above, are
saved with `run_status: diagnostic` under
`data/grades/_diagnostic/<ordered-task-sha256>/`. The full task hash prevents a
subset from sharing a cache/resume path with a complete run, and the dashboard
aggregator only discovers root-level grade JSON. A verified complete run keeps
the root output path and `run_status: final`.

## Judge-error score boundary

New grade payloads use output schema `1.3`: every `judge_error` item is excluded
from task score numerators and denominators, while `summary.wow.judge_error_rate`
remains required and visible in the dashboard. If every item in a task is
excluded, the task is unscored rather than silently contributing a zero.

Headline scores from schema `1.3` are not directly comparable with schemas
`1.0`-`1.2`, where some judge failures could contribute score-included zeros.
Historical payloads remain readable and unchanged; do not backfill or combine
partial results across this boundary. Compare conditions only after a complete
rerun under one grader source and one schema identity.

The read-only baseline analysis used tracked payload
`data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
(SHA-256
`b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570`).
It contains 355 `judge_error` items. Of those, 100 were score-included zeros
across 53 tasks: 61 `final_json_parse_failed`, 31 `empty_final_text`, five
`RateLimitError`, and three content-policy `BadRequestError` items. The other
255 errors were already score-excluded selection failures. This analysis did
not mutate or partially regrade the payload.

The approved future exp003 full rerun is fixed to:

- config: `regrade_exp003_v2_mini_score_excluded.yaml`
- config hash: `55a7dc5cfb8023fe`
- rubric commit: `11e7900cdcac61bc4daf59e65feb238acda98fbf`
- inference revision: `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`
- expected task count: `220`

Inside Step 8, the config's `rerun_identity` block is checked before its Azure
route preflight and before model-client construction, so a partial task set or
identity drift cannot start model grading. The workflow may authenticate and
perform its own route checks earlier.

The pinned Sol Max identities are:

| purpose | config | config hash | tasks |
|---|---|---|---:|
| full rerun | `regrade_exp003_v2_sol_max_score_excluded.yaml` | `14fc577ea39d98c5` | 220 |
| paid anchor | `validation_exp003_v2_sol_max_anchor4.yaml` | `7f3c7c2e542cf580` | 4 |

Both pin rubric commit `11e7900cdcac61bc4daf59e65feb238acda98fbf`
and inference revision `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`.
Their audio block remains the production `gpt-audio-1.5` configuration with a
three-call task cap and 30-second trim, and their visual task cap remains 72.

The mini reference below is not like-for-like. Its tracked payload uses schema
`1.0`, has no top-level `config_name` or `grader_source_hash`, and all 220 tasks
have `perception_call_count=0`. Although its items are labelled with 337 visual
and 58 audio routing decisions, those criteria predate perception wiring and
were silently handled by the text judge. Therefore its calls and latency are a
main-judge-only historical reference, not a "Sol Max multiplier" and not a
basis for scaling newly active visual or audio work.

### Pinned anchor tasks and selection rules

The paid anchor pins these tasks in canonical inference-source order (the
tracked payload array indices are authoritative):

1. index 10 — `99ac6944-4ec6-4848-959c-a460ac705c6f`
2. index 29 — `4c18ebae-dfaa-4b76-b10c-61fcdf26734c`
3. index 78 — `40a8c4b1-b169-4f92-a38b-7f79685037ec`
4. index 179 — `a73fbc98-90d4-4134-a54f-2b1d0c838791`

The tasks were selected by targetable score-included mini errors, not by score.
The baseline payload is
`data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
(SHA-256
`b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570`).

| task | final JSON parse | empty final text | targetable | visual | audio | main calls | main latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `99ac6944-4ec6-4848-959c-a460ac705c6f` | 2 | 1 | 3 | 10 | 13 | 52 | 679.03787 s |
| `4c18ebae-dfaa-4b76-b10c-61fcdf26734c` | 5 | 1 | 6 | 1 | 0 | 50 | 387.76369 s |
| `40a8c4b1-b169-4f92-a38b-7f79685037ec` | 3 | 5 | 8 | 0 | 0 | 72 | 635.26040 s |
| `a73fbc98-90d4-4134-a54f-2b1d0c838791` | 3 | 2 | 5 | 32 | 0 | 60 | 747.13748 s |
| **Total** | **13** | **9** | **22** | **43** | **13** | **234** | **2,449.19944 s** |

These 22 errors are all `final_json_parse_failed` or `empty_final_text`; none is
wrong-format, rate-limit, content-policy, or selection failure. They cover 22%
of the 100 historical score-included judge errors while adding 43 visual and 13
audio criteria. Every latency value and the
2,449.19944-second total above are derived from raw `judge_total_latency_ms`;
display precision is decimal formatting, not per-task truncation.

When config `rerun_identity.task_ids` is present, Step 8 resolves it through the
existing `filter_tasks` validation path. Canonical source order is authoritative.
CLI `--tasks` is accepted only when it resolves to the same ordered task set;
otherwise the run fails. `--limit` must be either `0` or the pinned count (`4`),
so the protected workflow may continue to pass `tasks_limit=4` without adding a
new workflow input. Any pinned subset is emitted as a diagnostic grade.

### Preregistered anchor decision

The paid result is judged against the same four mini task rows above:

1. **Diagnostic outcome.** Count `final_json_parse_failed` and
   `empty_final_text` by task. Fewer than the mini baseline total of 22 is an
   improvement; zero is elimination. A total of 22 or more is **no improvement**
   and means the model-switch rationale has no diagnostic support. Other judge
   errors make the diagnostic inconclusive and block the full run; they cannot
   be credited as finalization improvement. The
   baseline is the four selected rows in the 220-task payload above, not a
   different cohort payload.
2. **Operational reference.** Report observed main calls and main latency
   against 234 calls and 2,449.19944 seconds. Label those ratios
   **main-judge-only references**, never Sol Max multipliers, because the mini
   baseline had no active perception. Also report main, visual, audio, and
   unknown token/cache/call/latency planes. No USD amount is inferred.
3. **Modality-normalized projection.** Never extrapolate the whole anchor by
   task count alone. Project and sum these components independently:
   - main plane: scale the measured non-perception wall/main component by
     `220 / 4 = 55`;
   - visual: scale measured visual latency by `337 / 43 ≈ 7.837209`;
   - audio: scale measured audio latency by `58 / 13 ≈ 4.461538`.
   Unknown perception makes the projection incomplete. Compare the known
   component total with the 44-hour envelope.
4. **Wiring and cap gates.** `audio.call_count` must be greater than zero;
   otherwise report dead audio wiring and stop before 220. The count of
   `task_visual_budget_exceeded` must be zero; any occurrence means visual work
   was silently excluded at cap 72 and blocks the full run.

   At or above 44 hours, stop before a full run and return to the owner with the
   existing choices: expand the chunk range, reduce the visual cap, or approve
   an explicit split/resume plan. This preparation authorizes none of them.

The analyzer only projects a JSON-Schema-valid `1.3` diagnostic payload whose
current repository config file matches the persisted config name and hash, and
whose judge/perception, rubric, inference, prompt, and four source-ordered task
identities match that preregistered config. Partial/resume payloads, missing,
duplicate, or reordered tasks, incomplete task/item/summary usage, and any
task-level error make the projection incomplete and block owner review.
For an anchor config identity, a missing or `null` `anchor_projection` is also
blocked rather than falling back to task-count extrapolation. Step 8 requires
the persisted projection contract to exactly match the current config before
accepting either a completed cache entry or a partial `--resume` payload.

All diagnostic, operational, modality, audio, visual-budget, and envelope
results must be reported numerically. Improvement alone does not justify the
full run if any wiring, cap, unknown-attribution, or time gate fails.

## Archived (no longer recommended)

Under `_archive_v1/`. These files are provenance references, not runnable inputs
to the current typed-route validator: they retain the historical
`judge.endpoint_env` contract that is now rejected. To reproduce an old run,
use the historical commit/environment or copy the config to a new top-level
file, remove `endpoint_env`, add an explicit matching `deployment`, and record
the migration as a new run identity. Never resume an old partial across that
boundary.

| file | why archived |
|---|---|
| `recommended_gpt5_4_mini_2026-05-24.yaml` | cost-sweep winner from 2026-05-24 — v1 mini judge, text-extract path, no tool calling. Retained for provenance; not directly runnable under the typed endpoint contract. |
| `validation_hybrid.yaml`, `validation_pro_only.yaml` | tier-routing PR2-preceding validation configs. v2 is single-tier; tier configs no longer match the grader path. |
| `tiered_critical_pro_mini.yaml` | tier-routing experiment config. Same reason as above. |
| `_sweep_template.yaml` | cost-sweep parameterization template. Useful only for reproducing the v1 sweep; v2 has a different cost surface and will get its own template if/when needed. |

## v1 vs v2 quick reference

|  | historical v1 (`default_gpt5pro.yaml`) | production v2 (`default_v2_sol_max.yaml`) |
|---|---|---|
| schema_version | `1.0` | `2.0` |
| judge tier | mini / standard / pro routing | single (gpt-5.6-sol) |
| reasoning_effort | medium / high / mini-low (per tier) | max for main, visual, and finalization |
| deliverable input | pre-extracted text, 1500 char cap | live file via `read_deliverable` tool |
| `deliverable_extract_max_chars` | present | **removed** |
| tools | none | `read_deliverable` + opt. `vision_judge` + opt. `audio_judge` |
| perception | none | gpt-5.6-sol max vision / gpt-audio-1.5 (modality-routed) |
| critical rule | `weight >= 4` | `\|max_score\| >= 4` (sign-aware, includes 94 penalty items) |
| score math | clamp-hidden negatives | sign-aware, explicit non-positive total_max handling |
| rubric execution | one final verdict per rubric item | one final verdict per rubric item (plus bounded tool/finalization calls) |

## How to add a new config

1. Copy `default_v2_sol_max.yaml` to `<your_name>.yaml` and edit only the
   fields you mean to change. `schema_version` must stay `2.0`.
2. `python step8_grade.py <exp_id> --config grading_configs/<your_name>.yaml --dry-run`
   to validate.
3. Run the model-free `--dry-run` first. Any paid smoke or full 220 run requires
   separate operator approval and artifact-level acceptance.
