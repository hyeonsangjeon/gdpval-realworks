# Grading configs

## Active configs (top level)

| file | path | grader path | when to use |
|---|---|---|---|
| `default_v2.yaml` | tool-calling judge | v2 (`ToolCallingJudge` via `judge.tools.read_deliverable`) | **default for new grade-run jobs after PR3 validation.** Single-tier gpt-5.4 medium, read_deliverable tool surface, vision/audio perception. |
| `default_gpt5pro.yaml` | text-extract judge | v1 (`Judge` / `BatchJudge`) | legacy default. Kept active until PR3 task 302 confirms v2 cost envelope. After PR3 PASS, `grade-run.yml` default flips and this file moves to `_archive_v1/`. |

`grade-run.yml`'s `grading_config` input default is **currently still
`default_gpt5pro.yaml`**. v2 is opt-in by passing
`default_v2.yaml` to the workflow input. The flip is a PR3 follow-up.

## Archived (no longer recommended)

Under `_archive_v1/`. Kept on disk so historical grade JSON files can
be reproduced and PR2 task 207 backfill scripts have a reference.

| file | why archived |
|---|---|
| `recommended_gpt5_4_mini_2026-05-24.yaml` | cost-sweep winner from 2026-05-24 — v1 mini judge, text-extract path, no tool calling. Replaced by `default_v2.yaml` for normal grading; only used now for legacy reruns. |
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
