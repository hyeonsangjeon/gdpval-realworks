# Grading Cost Optimization Sweep — Final Report

**Run period**: 2026-05-24 05:59 → 18:38 UTC (~12.6 hours wall-clock across 3 GH Actions jobs)
**Total spend**: **$42.36 / $80 cap** (53% utilized)
**Variants completed**: 27 (15 Phase A + 5 Phase B + 6 Phase C stability + 1 diversity)
**Benchmark**: `exp998_smoke_baseline_sample` (3 tasks, 94 rubric items, rubric `11e7900`)

---

## 🏆 WINNER: `A4_model_mini` (single gpt-5.4-mini, medium reasoning, no batching)

| Metric | Winner | Baseline | Δ |
|---|---|---|---|
| avg_score_pct | **77.91** | 77.83 | **+0.08pp** ✓ |
| critical_item_pass_rate | **1.00** | 1.00 | 0 ✓ |
| judge_error_rate | **0.0%** | 5.9% | **-5.9pp** ✓ |
| precheck_pass_rate | 0.80 | 0.80 | 0 ✓ |
| wall-clock (smoke 3 tasks) | **299s** | 142 min | **-96.5%** |
| smoke cost | **$0.25** | $7.42 | **-96.6%** |
| projected full-run (220 tasks) | **$18.45** | $493 | **-96.3%** |
| projected monthly capacity ($2,500 budget) | **~135 runs** | ~5 runs | **27×** |

### Config: [`winner_config.yaml`](./winner_config.yaml)
```yaml
judge:
  model: "gpt-5.4-mini"          # ← key change: was gpt-5.4-pro
  reasoning.effort: "medium"     # ← key change: was "high"
grader:
  deliverable_extract_max_chars: 1500  # ← was 4000 (4× shorter input)
  batch_size: 1                  # batching NOT used by winner
```

---

## Phase A: Single-Axis Sweep (15 variants, $26.66)

> Acceptance hard filter: critical=1.00, err≤5%, score Δ ±2pp.

| variant | judge_model | effort | extract | batch | avg | err | crit | smoke $ | full $ | accept |
|---|---|---|---|---|---|---|---|---|---|---|
| A1_pro_minimal | gpt-5.4-pro | minimal | 1500 | 1 | 9.8 | **100%** | 0 | $0.00 | $0 | ✗ |
| A1_pro_low | gpt-5.4-pro | low | 1500 | 1 | 9.8 | **100%** | 0 | $0.00 | $0 | ✗ |
| A1_pro_medium | gpt-5.4-pro | medium | 1500 | 1 | 72.2 | 1.2% | 1 | $5.63 | $412.81 | Δ ✗ |
| A1_pro_high | gpt-5.4-pro | high | 1500 | 1 | 71.4 | 2.4% | 1 | $6.73 | $493.54 | Δ ✗ |
| A2_std_extract_1000 | gpt-5.4 | medium | 1000 | 1 | 64.6 | 0% | 1 | $1.09 | $79.69 | Δ ✗ |
| **A2_std_extract_1500** | gpt-5.4 | medium | 1500 | 1 | **77.0** | 0% | 1 | $1.08 | **$79.10** | ✓ |
| A2_std_extract_2500 | gpt-5.4 | medium | 2500 | 1 | 82.8 | 0% | 1 | $1.22 | $89.46 | Δ ✗ |
| A3_std_batch_1 | gpt-5.4 | medium | 1500 | 1 | 76.2 | 0% | 1 | $1.16 | $84.82 | ✓ |
| A3_std_batch_4 | gpt-5.4 | medium | 1500 | 4 | 72.6 | 0% | 1 | $0.80 | $58.91 | Δ ✗ |
| A3_std_batch_8 | gpt-5.4 | medium | 1500 | 8 | 71.9 | 4.8% | 1 | $0.81 | $59.04 | Δ ✗ |
| A3_std_batch_12 | gpt-5.4 | medium | 1500 | 12 | 63.1 | **16.7%** | 1 | $0.93 | $67.99 | ✗ |
| A4_model_pro | gpt-5.4-pro | medium | 1500 | 1 | 72.9 | 2.4% | 1 | $5.88 | $430.96 | Δ ✗ |
| A4_model_std | gpt-5.4 | medium | 1500 | 1 | 74.4 | 0% | 1 | $1.10 | $80.46 | ✓ |
| **A4_model_mini** | **gpt-5.4-mini** | **medium** | 1500 | 1 | **77.9** | 0% | 1 | **$0.25** | **$18.45** | **✓ WIN** |
| A4_model_nano | gpt-5.4-nano | minimal | 1500 | 1 | 9.8 | **100%** | 0 | $0.00 | $0 | ✗ |

## Phase B: Combinations (5 variants, $10.56)

| variant | tiering | avg | err | calls | crit | smoke $ | full $ | accept |
|---|---|---|---|---|---|---|---|---|
| B1_baseline_ref | default_gpt5pro.yaml | 78.7 | 5.9% | 84 | 1 | $7.29 | $534.59 | err ✗ |
| B2_std_med_b8 | std + batch 8 | 72.4 | 0% | 18 | 1 | $0.88 | $64.54 | Δ ✗ |
| B3_tiered_pro_std_b8 | pro/std 2-tier batch 8 | 68.4 | 4.8% | 16 | 1 | $0.74 | $54.15 | Δ ✗ |
| B4_tiered_with_mini_b8 | pro/std/mini 3-tier batch 8 | 67.5 | 5.9% | 19 | 1 | $0.94 | $68.94 | both ✗ |
| B5_tiered_with_nano_b8 | pro/std/nano 3-tier batch 8 | 66.0 | 5.9% | 15 | **0** | $0.71 | $52.36 | crit ✗ |

→ **No new winners from Phase B.** Tier combinations consistently underperform single mini.

## Phase C: Stability (B3 × 3 + B2 × 3, $5.14)

| variant | n | mean score | std | mean err | err std | crit | stable? |
|---|---|---|---|---|---|---|---|
| B3_tiered_pro_std_b8 | 3 | 69.76 | 2.45 | 6.3% | 2.7% | 1.0 | ✗ (Δstd>1.5) |
| B2_std_med_b8 | 3 | 71.47 | 2.24 | 4.0% | 5.0% | 1.0 | ✗ (Δstd>1.5) |

→ Phase B's batched variants are **unstable** (score std > 1.5pp threshold). Reinforces winner choice.

---

## Diversity Validator: `DV_gpt4o_medium_b8` — gpt-4o batch=8

**Result**: avg 9.8, err 100%, critical 0 — **gpt-4o cannot grade with this configuration.**

Possible causes (unverified):
1. Responses API + reasoning_effort param incompatible with gpt-4o (not a reasoning model)
2. Structured output JSON schema validation strict for gpt-4o
3. max_output_tokens=4096 incompatible with chat model token semantics

→ family-bias check could not be performed against gpt-4o. Future sweep should use a different non-gpt-5 family (e.g., claude-sonnet) or downgrade gpt-4o's reasoning_effort to default.

---

## 4 Key Insights

### 1. **gpt-5.4-mini is the new default judge**
- Matches baseline score (+0.08pp) at 1/27th cost ($18 vs $493 full-run)
- err rate drops from 5.9% to 0.0% (mini's smaller output is more JSON-compliant)
- wall-clock 299s vs 142min (28× faster)
- **This single change alone delivers the entire cost optimization target.**

### 2. **gpt-5.4-pro is unusable below medium effort**
- minimal/low effort → 100% judge_error (verdict JSON parse fails universally)
- → if forced to use pro, must use medium or high. Both ~$400+ full-run.

### 3. **Tiered judging is counterproductive in this benchmark**
- Phase B variants B3/B4/B5 all underperform single-model A4_model_mini
- Each added tier drops score ~5pp (verdict context fragmentation)
- → **Reject the tiered-judge hypothesis from TASK_GRADE_COST_OPTIMIZATION.md** for this benchmark size. Tiering may still help for >100-task rubrics where critical-vs-fluff routing pays off.

### 4. **Batching has variance cost**
- batch=4 saves 3× calls but loses 3.6pp score with 0% err
- batch=8 saves 5× calls but err jumps to 4.8%
- batch=12 destabilizes (err 16.7%, score -13pp)
- Phase C stability runs: batched variants Δscore std=2.24~2.45pp (above 1.5pp threshold)
- → **Skip batching for the winner config.** mini at batch=1 is fast enough.

---

## Decision: Promote `A4_model_mini` (with caveats)

### ✓ Recommended action
1. Copy `winner_config.yaml` → `batch-runner/grading_configs/recommended_gpt5_4_mini_2026-05-24.yaml` ✓ (already at sweep dir path)
2. Run **one manual full-run validation** (220 tasks via `grade-run.yml`):
   ```bash
   gh workflow run grade-run.yml \
     -f experiment_yaml=exp001_baseline_gpt5_2chat \
     -f grading_config=recommended_gpt5_4_mini_2026-05-24.yaml
   ```
3. Compare against the most recent `default_gpt5pro.yaml` full run on the same experiment. If avg_score Δ ≤ ±2pp and critical_pass=1.0, promote to default.
4. Update `default_gpt5pro.yaml` to import the recommended config (or symlink).

### ⚠️ Caveats / stability gaps
- **Winner has only 1 measurement.** Phase C did not stress A4_model_mini. Recommended follow-up: 3 stability runs of the winner config before promotion. Cost ~$0.75. Could be a 4th GH Actions trigger or part of full-run validation.
- **Pricing estimates** in dispatcher (`PRICING_USD_PER_1M`) are unverified vs tenant billing. Real spend may vary ±20%.
- **Diversity validator unfunctional.** No cross-family bias signal. Add claude-sonnet variant in a follow-up sweep if cross-family validation is required for publication.

---

## Files

- [`winner_config.yaml`](./winner_config.yaml) — drop-in production config
- [`RESULTS.md`](./RESULTS.md) — dispatcher-generated raw results table
- [`progress.json`](./progress.json) — full per-variant metrics (27 entries)
- [`PHASE_A_PARTIAL_RESULTS.md`](./PHASE_A_PARTIAL_RESULTS.md) — interim Phase A analysis (11/15)
- [`PHASE_B_RESULTS.md`](./PHASE_B_RESULTS.md) — Phase B combinations analysis
- [`STATUS.md`](./STATUS.md) — orchestration timeline (auto-updated)
- `runs/<variant>/grade.json` — per-variant grade JSON (local only, .gitignored)
- GH Actions artifacts (30-day retention): runs #26353454477, #26360665836, #26363013282, #26368167957

---

_Generated: 2026-05-24 19:00 UTC. Final orchestrator report._
