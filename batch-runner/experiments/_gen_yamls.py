#!/usr/bin/env python3
"""Generate exp017-024 YAML files from exp013 template."""
import os

EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(EXPERIMENTS_DIR)

# Read shared body (prompt/preprocessors/qa/execution) from exp013, line 50+
with open("exp013_GPT54_reasoning_high.yaml") as f:
    lines = f.readlines()
shared_body = "".join(lines[49:])  # 0-indexed, so line 50 = index 49

configs = [
    # (exp_id, model_short, deployment, reasoning_effort, ablation_num, series_range)
    # gpt-5.4-pro series
    ("exp017", "GPT54Pro", "gpt-5.4-pro", '"high"', "1/4", "exp017-020"),
    ("exp018", "GPT54Pro", "gpt-5.4-pro", '"medium"', "2/4", "exp017-020"),
    ("exp019", "GPT54Pro", "gpt-5.4-pro", '"low"', "3/4", "exp017-020"),
    ("exp020", "GPT54Pro", "gpt-5.4-pro", None, "4/4", "exp017-020"),
    # gpt-5.4-mini series
    ("exp021", "GPT54Mini", "gpt-5.4-mini", '"high"', "1/4", "exp021-024"),
    ("exp022", "GPT54Mini", "gpt-5.4-mini", '"medium"', "2/4", "exp021-024"),
    ("exp023", "GPT54Mini", "gpt-5.4-mini", '"low"', "3/4", "exp021-024"),
    ("exp024", "GPT54Mini", "gpt-5.4-mini", None, "4/4", "exp021-024"),
]

EFFORT_LABELS = {'"high"': "HIGH", '"medium"': "MEDIUM", '"low"': "LOW", None: "NULL"}
EFFORT_SUFFIXES = {'"high"': "reasoning_high", '"medium"': "reasoning_medium", '"low"': "reasoning_low", None: "reasoning_null"}
MODEL_DISPLAY = {"gpt-5.4-pro": "GPT-5.4-Pro", "gpt-5.4-mini": "GPT-5.4-Mini"}

for exp_id, model_short, deployment, effort, ablation_num, series in configs:
    label = EFFORT_LABELS[effort]
    suffix = EFFORT_SUFFIXES[effort]
    full_id = f"{exp_id}_{model_short}_{suffix}"
    display_model = MODEL_DISPLAY[deployment]
    
    # Header comment
    header = f"""# 🎯 Reasoning Ablation Study ({series})
# Research Question: Impact of reasoning_effort on full GDPVal benchmark
# Control: All settings identical to exp012 except reasoning_effort + model + scope
# Variable: reasoning_effort = {{high, medium, low, null}}
# Base architecture: exp012 multi-agent (gpt-audio-1.5 + main model)
# Scope: All 220 tasks (exp012 was Information sector only)
"""
    
    # Experiment block
    if effort is not None:
        desc_first = f"[ABLATION {ablation_num}] {display_model} with reasoning_effort={effort.strip(chr(34))}."
    else:
        desc_first = f"[ABLATION {ablation_num}] {display_model} with reasoning_effort omitted (null baseline)."
    
    experiment_block = f"""experiment:
  id: "{full_id}"
  name: "{display_model} Reasoning {label} — Full Benchmark (Ablation {ablation_num})"
  description: >
    {desc_first}
    Multi-agent: gpt-audio-1.5 preprocessor + {display_model} code generation.
    Full 220 tasks across 11 sectors, 55 occupations.
    Compare within series: {series} (reasoning_effort only).
    Baseline comparison: exp012 (GPT-5.2, Information sector)."""
    
    if effort is None:
        experiment_block += "\n    No reasoning_effort parameter sent to API — server applies default behavior."
    
    experiment_block += f"""
  author: "Hyeonsang Jeon"
  created_at: "2026-03-24"
"""
    
    # Control block
    if effort is not None:
        changed_comment = "    - reasoning_effort    # ABLATION VARIABLE"
    else:
        changed_comment = "    - reasoning_effort    # ABLATION VARIABLE (null = omitted from API call)"
    
    control_block = f"""# Variable control
control:
  fixed:
    - tasks               # All 220 tasks (11 sectors, 55 occupations)
    - temperature         # 0.0
    - preprocessor        # gpt-audio-1.5
    - execution_mode      # subprocess
    - resume_max_rounds   # 2
    - domain_packages     # full exp011 environment
  changed:
{changed_comment}
"""
    
    # Data block
    data_block = f"""# Data filter — All sectors (full benchmark)
data:
  source: "HyeonSang/{full_id}"
  filter:
    sector: null          # All 11 sectors
    occupation: null      # All 55 occupations
    sample_size: null     # All 220 tasks
"""
    
    # Condition_a block (model section only — prompt comes from shared body)
    if effort is not None:
        condition_comment = f"# Condition A: Elicit v2 + domain packages + audio preprocessor + reasoning_effort={effort.strip(chr(34))}"
        condition_name = f"{display_model} reasoning={effort.strip(chr(34))} + gpt-audio-1.5 preprocessor"
        reasoning_line = f'    reasoning_effort: {effort}  # ⭐ ABLATION VARIABLE'
    else:
        condition_comment = "# Condition A: Elicit v2 + domain packages + audio preprocessor + NO reasoning_effort"
        condition_name = f"{display_model} reasoning=null (omitted) + gpt-audio-1.5 preprocessor"
        reasoning_line = "    # reasoning_effort intentionally omitted — null baseline"
    
    condition_block = f"""{condition_comment}
condition_a:
  name: "{condition_name}"
  model:
    provider: "azure"
    deployment: "{deployment}"
    temperature: 0.0
    seed: null            # Reasoning models may not support determinism
{reasoning_line}
  prompt:
"""
    
    # Combine all
    content = header + "\n" + experiment_block + "\n" + control_block + "\n" + data_block + "\n" + condition_block + shared_body
    
    filename = f"{full_id}.yaml"
    with open(filename, "w") as f:
        f.write(content)
    print(f"Created: {filename}")

print("\nDone! 8 YAML files created.")
