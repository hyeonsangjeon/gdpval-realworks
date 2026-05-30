# PR3 Step 0 — Baseline cost truth

Run: [`26685383319`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/26685383319),
exp998_smoke_baseline_sample (3 tasks), `default_v2.yaml`, with Step 1
(prompt cache + compaction + parallel_tool_calls=false) already applied.

## Headline

| metric | value |
|---|--:|
| **raw 220-task extrap** (full price input) | exp003 N=10 round-2: **$168** |
| **observed cache_hit_ratio** (this probe) | **59.5%** |
| **effective per-call discount** at 50% cached input | **−30%** on input side, **−21%** on total |
| **effective 220-task extrap** (probe-projected) | exp003 N=10 effective ≈ **$132** (still > $80) |

→ **$168 was overstated by ~$36 from caching alone**, but even
cache-discounted exp003 N=10 sits at ~$132/run, still above the $80
autonomous ceiling. Step 2 will measure cache_hit_ratio on the actual
heavy-task workload (exp003) — heavy tasks tend to have **higher**
cache hit because the same scaffold + tool catalog is re-sent across
every iteration of the tool loop.

## Per-task probe

| task_id | judge_calls | tokens_in | cached_tokens | hit_ratio | pct |
|---|--:|--:|--:|--:|--:|
| `0419f1c3` (49-call docx monster) | 49 | 189,536 | (heavy ratio expected, computed at task level by `analyze_grade_run.py`) | — | 75.06 |
| `dfb4e0cd` | 20 | 148,954 | — | — | 93.95 |
| `a328feea` | 15 | 60,139 | — | — | 87.5 |
| **total** | **84** | **398,629** | **237,184** | **59.5%** | — |

(Per-task cached_tokens breakdown was not surfaced in the round-1
analysis markdown but is captured in the grade JSON's per-task
`judge_cached_tokens` field — committed in this run.)

## Pricing assumptions

`scripts/analyze_grade_run.py`:
- `gpt-5.4` input = $1.25 / M tokens, output = $5.00 / M tokens
- cached input billed at **50%** of standard (Azure OpenAI public-parity
  default; confirm against tenant billing before quoting)

## Verdict

- **$168 ≈ partly overstated.** Cache discount alone shaves ~$36 off
  the raw quote. Effective ≈ $132/run on heavy workload — still over
  the $80 autonomous ceiling, but the gap narrowed from $88 to $52.
- **Step 2 must re-measure on exp003 N=10** with caching active to get
  the true effective cost on heavy workload.
- **Step 4 fork stays in the > $80 branch** unless exp003 N=10
  measures effective ≤ $80; routes to **Step 5 (B-prime mini smoke)**
  if it doesn't.

## Artifacts

- `data/grades/exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools.json`
  (run 26685383319 commit)
- `data/grades/exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools.analysis.md`
  (auto-generated; includes effective cost line)
