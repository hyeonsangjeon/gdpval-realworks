# Experiment Specification: Reasoning Effort Ablation Study

**Experiment Series**: EXP013–016  
**Created**: 2026-03-24  
**Status**: Planning → Implementation → Execution  
**Lead**: hyeonsangjeon  
**Base**: exp012 (multi-agent audio), expanded to full 220-task benchmark

---

## 🎯 Research Question

**How does `reasoning_effort` impact LLM performance across the full GDPVal benchmark?**

This ablation study isolates the effect of OpenAI's `reasoning_effort` parameter on professional task completion quality, keeping all other variables constant.

---

## 📐 Experiment Design

### Experiments

| ID | Model | Reasoning Effort | Expected Cost | Duration (est.) |
|----|-------|-----------------|---------------|-----------------|
| **exp013** | gpt-5.4 | `high` | ~$140 | ~6 hours |
| **exp014** | gpt-5.4 | `medium` | ~$88 | ~4 hours |
| **exp015** | gpt-5.4 | `low` | ~$53 | ~3 hours |
| **exp016** | gpt-5.4 | `null` (omitted) | ~$35 | ~2 hours |

**Total**: 880 task runs, ~$316, ~15 hours wall-clock

### Control Variables (identical across all 4)

- **Tasks**: All 220 (11 sectors, 55 occupations)
- **Model**: gpt-5.4 (Azure deployment, 150 PTU)
- **Architecture**: Multi-agent (gpt-audio-1.5 preprocessor + GPT-5.4 generation)
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

### H6: Audio Synergy
**Prediction**: Reasoning + audio preprocessing compounds improvement for Information sector  
**Measurement**: Information sector QA score vs other sectors

---

## 💰 Budget & Timeline

### Cost Breakdown
- **Baseline (exp016)**: 220 tasks × ~16k tokens = 3.5M tokens ≈ $35
- **High (exp013)**: 220 tasks × ~64k tokens = 14M tokens ≈ $140
- **Total series**: ~31.6M tokens ≈ **$316**

### Schedule
- **Day 1**: Implement pipeline + smoke test
- **Day 2**: Run exp016 (fastest, validates pipeline)
- **Day 3**: Run exp015
- **Day 4**: Run exp014
- **Days 5-6**: Run exp013 (most expensive, run last)
- **Week 2**: Analysis + documentation

---

## 📈 Success Metrics

### Primary
1. **ΔSuccess Rate**: (exp013 - exp016) > 10% → reasoning beneficial
2. **Optimal Level**: Which effort level maximizes `accuracy/cost`?

### Secondary
- Token efficiency per successful task
- QA retry reduction (fewer reflection loops)
- Latency impact (median task duration)

### Qualitative
- Manual review: Does reasoning improve output quality observably?
- Error analysis: Which task types benefit most?

---

## 🧪 Analysis Plan

### Cross-Experiment Comparison
Generate 4-way comparison table:
- Success rate, QA mean, total cost, median latency
- Statistical significance testing (χ² for success rate)

### Sector-Level Heatmap
11 sectors × 4 reasoning levels → 44 cells showing:
- Success rate delta vs baseline (exp016)
- Average QA score
- Cost per successful task

### ROI Optimization
Scatter plot: `success_rate` (y) vs `total_tokens` (x)  
Identify Pareto frontier → recommend optimal `reasoning_effort` per sector

### Audio Synergy Test
Information sector tasks (with gpt-audio-1.5 preprocessing):
- Compare QA score improvement vs other sectors
- Hypothesis: audio analysis + reasoning creates compound lift

---

## 🔧 Implementation Notes

**Pipeline Prerequisite**: `reasoning_effort` parameter passthrough required in 4 files:
1. `llm_client.py`: Add parameter to `complete()`
2. `subprocess_runner.py`: Store and propagate
3. `executor.py`: Pass from config to runner
4. `step2_run_inference.py`: Extract from YAML, pass to executor

**Verification**: Smoke test (sample_size=3) should show `reasoning_tokens` in API response.

**Implementation tracking**: See separate development task document for code-level details.

---

## 📋 YAML Configuration Template

Each experiment inherits from exp012 (multi-agent) with these changes:

```yaml
experiment:
  id: "exp013_GPT54_reasoning_high"  # or 014/015/016
  description: "[ABLATION 1/4] GPT-5.4 reasoning_effort=high, full 220 tasks"

control:
  fixed: [tasks, temperature, preprocessor, execution_mode, ...]
  changed: [reasoning_effort]  # ABLATION VARIABLE

data:
  source: "HyeonSang/exp013_GPT54_reasoning_high"
  filter:
    sector: null      # All 11 sectors
    occupation: null  # All 55 occupations
    sample_size: null # All 220 tasks

condition_a:
  model:
    provider: "azure"
    deployment: "gpt-5.4"
    temperature: 0.0
    seed: null
    reasoning_effort: "high"  # ⭐ {high, medium, low, null}
  
  preprocessors:
    - type: "audio_analyzer"
      model:
        deployment: "gpt-audio-1.5"
      # ... (inherited from exp012)
```

---

## 🎓 Expected Learning Outcomes

After this study, we will know:

1. **Is reasoning worth the cost?** (3-5× token multiplier justified?)
2. **Optimal level per sector** (Finance needs `high`, Retail works with `low`?)
3. **Production strategy** (Should `medium` become new default?)
4. **Complexity correlation** (Do Actuaries benefit more than Data Entry clerks?)
5. **Sector-specific ROI** (Which sectors have highest reasoning payoff?)
6. **Audio synergy confirmation** (Does preprocessing + reasoning compound?)
7. **Routing strategy** (Can we build dynamic reasoning_effort selector?)

---

## 📚 References

- **Base experiments**: exp012 (multi-agent audio), exp011 (domain packages)
- **OpenAI docs**: [Reasoning Models Guide](https://platform.openai.com/docs/guides/reasoning)
- **Azure API version**: `2025-04-01-preview`
- **Dataset**: GDPVal (220 tasks, 11 sectors, 55 occupations)
- **Config**: `batch-runner/core/experiment_config.py::ModelConfig.reasoning_effort`

---

## 📝 Change Log

- **2026-03-24**: Initial specification created
- **[TBD]**: Pipeline implementation completed
- **[TBD]**: Smoke test passed
- **[TBD]**: Full runs executed
- **[TBD]**: Analysis completed, findings documented
