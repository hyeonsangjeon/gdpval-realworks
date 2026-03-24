# Experiment Specification: GPT-5.4-Pro Reasoning Effort Ablation Study

**Experiment Series**: EXP017–020  
**Created**: 2026-03-24  
**Status**: Planning  
**Lead**: hyeonsangjeon  
**Base**: exp012 (multi-agent audio), expanded to full 220-task benchmark

---

## 🎯 Research Question

**How does `reasoning_effort` impact GPT-5.4-Pro performance across the full GDPVal benchmark?**

This ablation study isolates the effect of OpenAI's `reasoning_effort` parameter on professional task completion quality, keeping all other variables constant. Comparison within series (exp017-020) and cross-model with exp013-016 (gpt-5.4) and exp021-024 (gpt-5.4-mini).

---

## 📐 Experiment Design

### Experiments

| ID | Model | Reasoning Effort | Expected Cost | Duration (est.) |
|----|-------|-----------------|---------------|-----------------|
| **exp017** | gpt-5.4-pro | `high` | ~$180 | ~8 hours |
| **exp018** | gpt-5.4-pro | `medium` | ~$110 | ~5 hours |
| **exp019** | gpt-5.4-pro | `low` | ~$70 | ~4 hours |
| **exp020** | gpt-5.4-pro | `null` (omitted) | ~$45 | ~3 hours |

**Total**: 880 task runs, ~$405, ~20 hours wall-clock  
**TPM**: 100K (gpt-5.4-pro)

### Control Variables (identical across all 4 within exp017-020)

- **Tasks**: All 220 (11 sectors, 55 occupations)
- **Model**: gpt-5.4-pro (Azure deployment)
- **Architecture**: Multi-agent (gpt-audio-1.5 preprocessor + GPT-5.4-Pro generation)
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

### H3: Cost-Efficiency Sweet Spot
**Prediction**: `medium` offers best ROI (accuracy per token)  
**Measurement**: `(success_rate / total_tokens) × 1000`

### H4: First-Shot Accuracy
**Prediction**: `high` reduces QA retry attempts  
**Measurement**: Average `reflection_attempts` per task

### H5: Sector Sensitivity
**Prediction**: Complex sectors (Finance, Healthcare, Information) benefit more from reasoning  
**Measurement**: Success rate delta by sector (11-way comparison)

### H6: Cross-Model Comparison
**Prediction**: GPT-5.4-Pro outperforms GPT-5.4 at all reasoning levels  
**Measurement**: Success rate and QA score delta vs exp013-016

---

## 💰 Budget & Timeline

### Cost Breakdown
- **Baseline (exp020)**: 220 tasks × ~20k tokens = 4.4M tokens ≈ $45
- **High (exp017)**: 220 tasks × ~80k tokens = 17.6M tokens ≈ $180
- **Total series**: ~40M tokens ≈ **$405**

### Schedule
- Run exp020 first (cheapest, validates pipeline)
- Run exp019, exp018, exp017 in ascending cost order
- Can run in parallel with exp021-024 (different model, separate TPM quota)

---

## 📈 Success Metrics

### Primary
1. **ΔSuccess Rate**: (exp017 - exp020) > 10% → reasoning beneficial
2. **Optimal Level**: Which effort level maximizes `accuracy/cost`?

### Secondary
- Token efficiency per successful task
- QA retry reduction (fewer reflection loops)
- Latency impact (median task duration)
- Cross-model comparison vs exp013-016 (gpt-5.4)

### Qualitative
- Manual review: Does reasoning improve output quality observably?
- Error analysis: Which task types benefit most?

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

### Sector-Level Heatmap
11 sectors × 4 reasoning levels → 44 cells showing:
- Success rate delta vs baseline (exp020)
- Average QA score
- Cost per successful task

---

## 🔧 Implementation Notes

**Pipeline Prerequisite**: `reasoning_effort` passthrough already implemented (exp013-016 work).

**YAML Files**: Based on exp013 template with `deployment: "gpt-5.4-pro"`.

**Concurrency**: Can run simultaneously with exp021-024 (gpt-5.4-mini, separate 250K TPM quota).

---

## 📋 YAML Configuration Template

Each experiment inherits from exp012 (multi-agent) with these changes:

```yaml
experiment:
  id: "exp017_GPT54Pro_reasoning_high"  # or 018/019/020

data:
  source: "HyeonSang/exp017_GPT54Pro_reasoning_high"
  filter:
    sector: null      # All 11 sectors
    occupation: null  # All 55 occupations
    sample_size: null # All 220 tasks

condition_a:
  model:
    provider: "azure"
    deployment: "gpt-5.4-pro"
    temperature: 0.0
    seed: null
    reasoning_effort: "high"  # ⭐ {high, medium, low, null}
```

---

## 🎓 Expected Learning Outcomes

1. **Is GPT-5.4-Pro worth the premium?** (vs gpt-5.4 at same reasoning level)
2. **Optimal level for Pro model** (Does Pro need less reasoning to achieve same quality?)
3. **Cost-quality frontier** (Where does Pro sit on the Pareto curve?)
4. **Sector-specific routing** (Which sectors justify Pro pricing?)
5. **Reasoning amplification** (Does Pro benefit more from reasoning than base model?)
