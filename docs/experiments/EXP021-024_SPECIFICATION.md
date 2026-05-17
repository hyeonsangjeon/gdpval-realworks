# Experiment Specification: GPT-5.4-Mini Reasoning Effort Ablation Study

**Experiment Series**: EXP021–024  
**Created**: 2026-03-24  
**Status**: Planning  
**Lead**: hyeonsangjeon  
**Base**: exp012 (multi-agent audio), expanded to full 220-task benchmark

---

## 🎯 Research Question

**How does `reasoning_effort` impact GPT-5.4-Mini performance across the full GDPVal benchmark?**

This ablation study isolates the effect of OpenAI's `reasoning_effort` parameter on professional task completion quality, keeping all other variables constant. Comparison within series (exp021-024) and cross-model with exp013-016 (gpt-5.4) and exp017-020 (gpt-5.4-pro).

---

## 📐 Experiment Design

### Experiments

| ID | Model | Reasoning Effort | Expected Cost | Duration (est.) |
|----|-------|-----------------|---------------|-----------------|
| **exp021** | gpt-5.4-mini | `high` | ~$35 | ~2 hours |
| **exp022** | gpt-5.4-mini | `medium` | ~$22 | ~1.5 hours |
| **exp023** | gpt-5.4-mini | `low` | ~$14 | ~1 hour |
| **exp024** | gpt-5.4-mini | `null` (omitted) | ~$9 | ~45 min |

**Total**: 880 task runs, ~$80, ~5 hours wall-clock  
**TPM**: 250K (gpt-5.4-mini)

### Control Variables (identical across all 4 within exp021-024)

- **Tasks**: All 220 (9 sectors, 44 occupations)
- **Model**: gpt-5.4-mini (Azure deployment)
- **Architecture**: Multi-agent (gpt-audio-1.5 preprocessor + GPT-5.4-Mini generation)
- **Execution**: subprocess mode + domain packages (exp011 environment)
- **Prompt**: Elicit v2 + audio suffix (from exp012)
- **Self-QA**: enabled, min_score=5, max_retries=1
- **Temperature**: 0.0
- **Seed**: null (reasoning models may not be deterministic)
- **Resume**: 2 rounds max

### Changed Variable

**`reasoning_effort`**: {`"high"`, `"medium"`, `"low"`, `null`}

When `null`, the parameter is **not sent** to OpenAI — this matches legacy behavior (exp001-012) and provides a clean baseline.

---

## 📊 Hypotheses

### H1: Success Rate Ordering
**Prediction**: `high` > `medium` > `low` > `null`  
**Measurement**: % tasks with `status="success"` and `qa_score ≥ 5`

### H2: Quality Improvement
**Prediction**: `high` produces highest average Self-QA scores  
**Measurement**: Mean QA score across 220 tasks

### H3: Cost-Efficiency Champion
**Prediction**: Mini with `medium` reasoning may offer best cost-per-success across all 12 experiments  
**Measurement**: `(success_rate / total_tokens) × 1000`

### H4: First-Shot Accuracy
**Prediction**: `high` reduces QA retry attempts  
**Measurement**: Average `reflection_attempts` per task

### H5: Sector Sensitivity
**Prediction**: Complex sectors (Finance, Healthcare, Information) benefit more from reasoning  
**Measurement**: Success rate delta by sector (9-way comparison)

### H6: Mini Ceiling Effect
**Prediction**: Mini model may plateau at `medium` — `high` reasoning may not help due to model capacity  
**Measurement**: Success rate delta between `high` and `medium` (expected smaller than for Pro)

---

## 💰 Budget & Timeline

### Cost Breakdown
- **Baseline (exp024)**: 220 tasks × ~4k tokens = 0.9M tokens ≈ $9
- **High (exp021)**: 220 tasks × ~16k tokens = 3.5M tokens ≈ $35
- **Total series**: ~8M tokens ≈ **$80**

### Schedule
- Run exp024 first (cheapest, validates pipeline)
- Run exp023, exp022, exp021 in ascending cost order
- Can run in parallel with exp017-020 (different model, separate TPM quota)
- Higher TPM (250K) means faster per-task throughput than Pro (100K)

---

## 📈 Success Metrics

### Primary
1. **ΔSuccess Rate**: (exp021 - exp024) > 10% → reasoning beneficial for Mini
2. **Optimal Level**: Which effort level maximizes `accuracy/cost`?
3. **Cross-model value**: Does Mini+high beat base model+null?

### Secondary
- Token efficiency per successful task
- QA retry reduction (fewer reflection loops)
- Latency impact (median task duration)
- Cross-model comparison vs exp013-016 (gpt-5.4) and exp017-020 (gpt-5.4-pro)

### Qualitative
- Manual review: Does reasoning compensate for smaller model size?
- Error analysis: Which task types are beyond Mini's capacity regardless of reasoning?

---

## 🧪 Analysis Plan

### Cross-Experiment Comparison
Generate 4-way comparison table:
- Success rate, QA mean, total cost, median latency
- Statistical significance testing (χ² for success rate)

### Cross-Model Analysis (3-way)
Compare exp013-016 (gpt-5.4) vs exp017-020 (gpt-5.4-pro) vs exp021-024 (gpt-5.4-mini):
- Same reasoning_effort level across models
- Cost-quality Pareto frontier
- Can Mini+high match base+null? (quality-budget tradeoff)

### Sector-Level Heatmap
9 sectors × 4 reasoning levels → 36 cells showing:
- Success rate delta vs baseline (exp024)
- Average QA score
- Cost per successful task

### Capacity Ceiling Analysis
Identify tasks where Mini fails regardless of reasoning level:
- These represent model capacity limits, not reasoning limits
- Compare ceiling across 3 model sizes

---

## 🔧 Implementation Notes

**Pipeline Prerequisite**: `reasoning_effort` passthrough already implemented (exp013-016 work).

**YAML Files**: Based on exp013 template with `deployment: "gpt-5.4-mini"`.

**Concurrency**: Can run simultaneously with exp017-020 (gpt-5.4-pro, separate 100K TPM quota). Mini has higher TPM (250K) so individual tasks complete faster.

---

## 📋 YAML Configuration Template

Each experiment inherits from exp012 (multi-agent) with these changes:

```yaml
experiment:
  id: "exp021_GPT54Mini_reasoning_high"  # or 022/023/024

data:
  source: "HyeonSang/exp021_GPT54Mini_reasoning_high"
  filter:
    sector: null      # All 9 sectors
    occupation: null  # All 44 occupations
    sample_size: null # All 220 tasks

condition_a:
  model:
    provider: "azure"
    deployment: "gpt-5.4-mini"
    temperature: 0.0
    seed: null
    reasoning_effort: "high"  # ⭐ {high, medium, low, null}
```

---

## 🎓 Expected Learning Outcomes

1. **Is reasoning worth it for Mini?** (Can reasoning compensate for smaller model?)
2. **Cost-quality champion** (Mini+medium may be best bang-for-buck across all 12 experiments)
3. **Capacity ceiling** (Where does Mini fail regardless of reasoning?)
4. **Production routing** (Simple tasks → Mini+low, Complex → Pro+high?)
5. **Sector-specific model selection** (Which sectors can use Mini safely?)
6. **12-experiment Pareto frontier** (Optimal model+reasoning combination per budget level)
