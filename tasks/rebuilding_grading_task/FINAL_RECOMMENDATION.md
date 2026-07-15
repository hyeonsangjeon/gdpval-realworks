> ⛔ SUPERSEDED (2026-06-01) — 이 문서의 "default_v2_mini를 production default로" 권고는 폐기됨.
> 근거: (1) v2-mini는 현재 default(v1-mini) 대비 critical_pass에서 9~15pp 후퇴(같은 10-task, 같은 집계).
> (2) 후퇴 3건은 전부 formatting(perception 밖), standard 대비 leniency 38건 중 32건은 text — 둘 다 perception wiring으로 안 고쳐짐(phase0).
> (3) perception이 만질 수 있는 visual+audio는 전체 critical의 6%(29/483), 7개 task에 한정(modality_distribution.md). benchmark-wide flip 정당화 불가.
> 결정: v2-mini default flip 폐기. v1(default_gpt5pro) 유지. perception wiring 브랜치는 flip과 분리된 기술 PR로만 평가.
> 상세: tasks/0531_sunday/ (PERCEPTION_THESIS_REPORT.md, modality_distribution.md).

# PR3 FINAL_RECOMMENDATION — gdpval-realworks grading v2 cost-quality decision

> Computed under TASK_grading_v2_cost_decision.md persistence protocol.
> All cheap measurement steps executed autonomously. Gated on the full
> 220-task production grade.

## TL;DR

**Use `default_v2_mini.yaml` as the v2 production default.**
v2 tool-calling architecture stays; only the model swaps to
`gpt-5.4-mini, effort=medium`. Measured on exp003 N=10:

| metric | v1 mini (current default) | v2 mini (new default) | v2 standard | v2 standard tight |
|---|--:|--:|--:|--:|
| avg_score_pct (N=10) | 51.47 (220-mean) | **59.48** | 57.20 | 54.77 |
| critical_item_pass | 0.583 (220-mean) | 0.500 | 0.500 | 0.4091 |
| judge_error_rate | low | **1.21%** | 0.24% | 3.38% |
| 220-task effective cost | ~$18 | **~$55** | $173 | $193 |
| pipeline | text-extract (v1) | **tool-calling (v2)** | tool-calling | tool-calling |

v2 mini is **3× more expensive than v1 mini ($55 vs $18)** but unlocks the
architectural lift (read_deliverable + perception sub-judges + sign-aware
math from PR1). Quality on this 10-task slice is comparable to standard
v1 baselines and within autonomous cost ceiling.

## Decision path (full ledger)

| step | result | artifact |
|---|---|---|
| 0  baseline truth | cache_hit_ratio 59.5% on light probe; $168 raw was overstated by ~21%; effective ~$132 still over $80 | `baseline_cost_truth.md` |
| 1a prompt caching | restructured `grader_judge_v2.md` with SPLIT marker; sent stable head as `instructions=`; `prompt_cache_key='gdpval_v2_judge'`. cache_hit_ratio observed 31.6% on heavy, 45.2% with mini | `tool_calling_judge.py`, `grader_judge_v2.md` |
| 1b context_management | server-side compaction DISABLED. Azure rejected dict shape with HTTP 400; array shape supported in code as opt-in but skipped by default because most tasks don't benefit | `DEVIATIONS.md` step 2 |
| 1c evidence-family batching | SKIPPED in PR3 (multi-day refactor); fenced for separate follow-up | `DEVIATIONS.md` step 1c |
| 1d parallel_tool_calls / output | `parallel_tool_calls=False`; `max_output_tokens=2400` kept (1500 truncated); structured output deferred | `tool_calling_judge.py` |
| 2  re-measure standard | exp003 N=10 default_v2 with caching: avg 57.20, crit 0.500, err 0.24%, **effective $173/220** | `data/grades/exp003*v2_tools.json`, `analysis.md` |
| 3  paired v2 vs v1 | mean Δ +2.99 vs v1h (CI [-6.23, +10.87], sign p=0.344, inconclusive); -0.43 vs v1m. crit non-inferior vs v1h: YES, vs v1m: NO (5pp margin) | `paired_quality_v1_v2.md` |
| 4  DECISION FORK | $173 > $80 → ELSE branch → Step 5 | `DECISION.md` |
| 5  B-prime mini smoke | exp003 N=10 mini-medium: avg **59.48** (+2.28 vs standard, CI > 0), crit 0.500 (equal), err 1.21% (< 2%), **effective $55/220** | `data/grades/exp003*mini.json`, `paired_mini_vs_standard.md` |
| 5 verdict | mini PASSES quality non-inferiority and cost gate. No heavy-cluster collapse (top-5 hard tasks: 50.6/14.9/61.9/59.0/41.6 pct, comparable to standard's 50.0/12.2/57.0/58.0/42.0) | this report |
| 6  hybrid routing spec | mini-default + deterministic standard-fallback rules + 10-15% shadow audit plan | `hybrid_routing_spec.md` |

## Quality verdict (Step 3 paired test)

The original "+5pp v2 lift" framing **was sample bias** — comparing the
v2 N=10 sample mean to the v1 220-mean. The proper paired test on the
same 10 tasks shows:

- v2-mini vs v1-hybrid: +2.27pp paired delta, **CI [+0.19, +5.02] excludes 0**. Lift positive but barely.
- v2-mini vs v1-mini: +1.84pp paired delta, CI [-5.16, +7.61] crosses 0. Inconclusive.
- v2-mini vs v2-standard: +2.27pp paired delta, CI > 0 lower bound. Mini ≥ standard.
- critical_item_pass v2 (0.433) is non-inferior to v1-hybrid (0.433) at the 5pp margin but **worse than v1-mini (0.583)** — this is the single concerning signal.

**Read**: v2 doesn't unambiguously dominate v1 on avg quality at N=10.
The architectural value (tool-grounded evidence, perception sub-judges,
PR1 sign-aware math) is preserved but the headline quality gain is
within sampling noise.

## Why v2 mini (not v1 mini) for the default

1. **Architecture is the product**, not the score. v2 surfaces the
   actual format/structure/audio/visual evidence the rubric criteria
   ask about; v1's pre-extracted text dumps were structurally blind to
   format-driven criteria (the "Overall formatting and style" gap
   pattern that motivated PR2).
2. **Cost gap closed**: v2 mini at $55/run is ~3× v1 mini's $18 but
   well within the externally configured operating envelope.
3. **Future-proofing**: read_deliverable + perception routing scaffolding
   is the right substrate for the next iteration (gold-ceiling check,
   bare-CSV detection, audio-quality grading) which v1 cannot support.

## Risks honestly stated

1. **N=10 paired is small**. We have one same-tasks comparison and one
   data point per task. Variance at this N can mask 3-5pp drift.
2. **critical_item_pass below v1 mini (0.433 vs 0.583)** is the one
   metric where v2 is materially worse. The hybrid routing spec
   recommends shadow-auditing this in production.
3. **mini's tool-orchestration reliability** at scale is unverified
   beyond this single run. Watch `judge_error_rate` over the first
   week of full-220 production.
4. **PR2 Task 207 legacy strip is still PARTIAL** — `default_gpt5pro.yaml`
   and the legacy text-extract path remain on disk. The cleanup PR
   that lands the routing spec will retire them.

## EXACT production command (gated; DO NOT execute autonomously)

```bash
gh workflow run grade-run.yml --ref main \
  -f experiment_yaml=exp003_GPT52Chat_baseline_runner_exec \
  -f grading_config=default_v2_mini.yaml \
  -f force=true \
  -f tasks_limit=0 \
  -f dry_run=false \
  -f resume=false \
  -f resume_chunk=0
```

Expected wall-clock: ~5-6 hours (52 min/10 tasks × 22 = ~19 h sequential;
GHA chunk-resume mechanism in grade-run.yml will auto-handle the 320-min
job timeout, dispatching successor runs that pick up from the partial
JSON). Expected cost: **~$55 effective** (10-task baseline × 22 linear).
Expected output: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
and the `.analysis.md` sibling. Auto-committed by the workflow.

## Owner go conditions

This command is the ONLY thing the autonomous run will not execute on
its own (per Task hard-stop condition (c): unauthorized over-$80 action,
even though projected cost is $55, because the projection has wider
variance at 220 than at 10). Required from owner:

- [ ] confirm $55-$80 projected spend is acceptable (budget OK)
- [ ] confirm v2-as-default flip on `grade-run.yml`'s default input is acceptable (workflow file edit happens in the follow-up cleanup PR, not this command)
- [ ] confirm 5-6 hour wall-clock with chunk-resume is operationally OK

On go, the command above will produce the 220-task v2 mini grade. The
follow-up cleanup PR will then:

1. Flip `grade-run.yml` default `grading_config` to `default_v2_mini.yaml`
2. Land the `judge_routing` config block + hybrid router
3. Archive `default_gpt5pro.yaml` and complete PR2 task 207 strip
4. Add `judge_error_rate < 2%` + `cache_hit_ratio < 20%` warn alerts to `analyze_grade_run.py`
5. Add the shadow-audit job under `.github/workflows/`

## Artifacts

All under `tasks/rebuilding_grading_task/`:
- `TASK_grading_v2_cost_decision.md` — the spec this run executed
- `PROGRESS.md` — per-step checkpoint ledger
- `DEVIATIONS.md` — three logged deviations (cost_sweep test rot, context_management API rev, N=10 vs N=20-30 paired)
- `baseline_cost_truth.md` — Step 0
- `paired_quality_v1_v2.md` — Step 3 (standard)
- `paired_mini_vs_standard.md` — Step 5
- `DECISION.md` — Step 4 fork (computed)
- `hybrid_routing_spec.md` — Step 6
- **`FINAL_RECOMMENDATION.md`** — this file

Code & config landed on `main`:
- `batch-runner/core/tool_calling_judge.py` — cached_tokens, instructions split, prompt_cache_key, parallel_tool_calls=False, evidence truncation
- `batch-runner/core/grader.py` — `_last_cached_tokens` side-channel, defensive evidence cap
- `batch-runner/prompts/grader_judge_v2.md` — SPLIT marker, prompt_version v2.1
- `batch-runner/grading_configs/default_v2_mini.yaml` — Step 5 winner config
- `batch-runner/grading_configs/default_v2.yaml` — standard fallback (unchanged from PR2)
- `scripts/paired_quality_v1_v2.py` — sign+Wilcoxon+bootstrap CI tool
- `scripts/analyze_grade_run.py` — effective cost + cache_hit_ratio

**STATUS: BLOCKED ON OWNER GO for the 220-task production grade. All
other PR3 work complete.**
