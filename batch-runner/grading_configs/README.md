# Grading configs

## Active configs (top level)

| file | path | grader path | when to use |
|---|---|---|---|
| `default_v2.yaml` | tool-calling judge | v2 (`ToolCallingJudge` via `judge.tools.read_deliverable`) | Explicit opt-in for new tool-calling runs. Single-tier gpt-5.4 medium, read_deliverable tool surface, vision/audio perception. |
| `default_gpt5pro.yaml` | text-extract judge | v1 (`Judge` / `BatchJudge`) | Current workflow default while the v2 cost/capacity envelope remains a separate operator decision. |

`grade-run.yml`'s `grading_config` input default is **currently still
`default_gpt5pro.yaml`**. v2 is opt-in by passing
`default_v2.yaml` to the workflow input. There is no automatic hybrid follow-up
or config flip in the active workflow.

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

|  | v1 (`default_gpt5pro.yaml`) | v2 (`default_v2.yaml`) |
|---|---|---|
| schema_version | `1.0` | `2.0` |
| judge tier | mini / standard / pro routing | single (gpt-5.4) |
| reasoning_effort | medium / high / mini-low (per tier) | medium |
| deliverable input | pre-extracted text, 1500 char cap | live file via `read_deliverable` tool |
| `deliverable_extract_max_chars` | present | **removed** |
| tools | none | `read_deliverable` + opt. `vision_judge` + opt. `audio_judge` |
| perception | none | gpt-5.4 vision / gpt-audio-1.5 (modality-routed) |
| critical rule | `weight >= 4` | `\|max_score\| >= 4` (sign-aware, includes 94 penalty items) |
| score math | clamp-hidden negatives | sign-aware, explicit non-positive total_max handling |
| rubric execution | one final verdict per rubric item | one final verdict per rubric item (plus bounded tool/finalization calls) |

## How to add a new config

1. Copy `default_v2.yaml` to `<your_name>.yaml` and edit only the
   fields you mean to change. `schema_version` must stay `2.0`.
2. `python step8_grade.py <exp_id> --config grading_configs/<your_name>.yaml --dry-run`
   to validate.
3. Run on the smoke experiment (`exp998_smoke_baseline_sample`,
   `--limit 3`) before triggering the full 220 to bound cost.
