# Grading configs

## Active configs (top level)

| file | path | grader path | when to use |
|---|---|---|---|
| `default_v2_sol_max.yaml` | tool-calling judge | v2 (`ToolCallingJudge` via `judge.tools.read_deliverable`) | **Production default.** GPT-5.6 Sol 1M Max for main, visual, and bounded finalization; gpt-audio-1.5 for audio perception. |
| `default_v2.yaml` | tool-calling judge | v2 | Historical gpt-5.4 medium comparison identity. Pass explicitly when reproducing that condition. |
| `regrade_exp003_v2_mini_score_excluded.yaml` | tool-calling judge | v2 | Full-220 exp003 rerun only. Pins score-excluded semantics, the historical mini judge condition, rubric commit, inference revision, and exact task count. |
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
override, not a publishable grading path.

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
