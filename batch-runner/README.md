# GDPVal Batch Runner

A Python pipeline that runs LLM experiments on the [OpenAI GDPVal](https://huggingface.co/datasets/openai/gdpval) Gold Subset (220 tasks) and uploads results to HuggingFace.

## Architecture

```
Step 0  Bootstrap       →  Duplicate openai/gdpval to your HF repo + local snapshot
Step 1  Prepare Tasks   →  Load dataset, apply YAML filters, save to workspace/
Step 2  Run Inference   →  Call LLM for each task, save incrementally (resume-safe)
Step 3  Format Results  →  Produce JSON + Markdown report in results/
Step 4  Fill Parquet    →  Merge deliverable_text/files into base parquet
Step 5  Validate        →  Pre-upload checks (220 rows, columns, file paths)
Step 6  Generate Report →  LLM narrative + metrics → report.md / report.html / report_data.json
Step 7  Upload to HF    →  Clean upload with delete_patterns (includes workspace/report/)
```

## Quick Start

```bash
cd batch-runner
pip install -r requirements.txt

# Set environment variables (choose provider)
export HF_TOKEN="hf_xxx"
export AZURE_OPENAI_ENDPOINT="https://xxx.openai.azure.com"
export AZURE_OPENAI_API_KEY="xxx"

# Step 0: Bootstrap (duplicate openai/gdpval + local snapshot)
./step0_bootstrap.sh HyeonSang/my-experiment-repo

# Step 1: Prepare tasks from experiment YAML
./step1_prepare_tasks.sh experiments/exp999_smoke_baseline_sample.yaml

# Step 2: Run inference
./step2_run_inference.sh condition_a

# Step 3: Format results
./step3_format_results.sh

# Step 4: Fill parquet
./step4_fill_parquet.sh results/exp999_smoke_baseline_sample.json HyeonSang/my-experiment-repo

# Step 5: Validate
./step5_validate.sh

# Step 6: Generate experiment report
./step6_report.sh

# Step 7: Upload to HuggingFace
./step7_upload_hf.sh HyeonSang/my-experiment-repo
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HF_TOKEN` | Yes | HuggingFace write token (for Step 0 and Step 6) |
| `AZURE_OPENAI_ENDPOINT` | Azure | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure | Azure OpenAI API key |
| `OPENAI_API_KEY` | OpenAI | Native OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic | Anthropic API key |

## Pipeline Steps

### Step 0: Bootstrap (`step0_bootstrap.sh`)

```
openai/gdpval  ──duplicate──▶  SUBMISSION_REPO_ID (HF)
                                    │
                                    ▼ snapshot_download
                             data/gdpval-local/
                             ├── data/train-*.parquet
                             ├── reference_files/**
                             └── deliverable_files/     (empty)
```

- Duplicates `openai/gdpval` to your HF repo if it doesn't exist
- Downloads local snapshot to `data/gdpval-local/`
- Validates: 220 rows, rubric columns present, reference_files/ exist

### Step 1: Prepare Tasks (`step1_prepare_tasks.py`)

Reads experiment YAML config → loads dataset → applies filters (sector, sample_size) → saves task list + condition configs to `workspace/step1_tasks_prepared.json`.

### Step 2: Run Inference (`step2_run_inference.py`)

Reads prepared tasks → calls LLM for each task → saves results incrementally to `workspace/step2_inference_progress.json`. Supports multi-round resume: re-runs `error`/`qa_failed` tasks automatically.

### Step 3: Format Results (`step3_format_results.py`)

Converts inference output into structured JSON + Markdown report under `results/<exp_id>/`.

### Step 4: Fill Parquet (`step4_fill_parquet.py`)

Merges `deliverable_text` and `deliverable_files` into the base parquet, preserving all original columns (rubric_json, rubric_pretty, etc.).

### Step 5: Validate (`step5_validate.py`)

Pre-upload integrity checks: 220 rows, required columns, deliverable file paths, etc.

### Step 6: Generate Report (`step6_report.py`)

Reads `workspace/result.json` and generates three output files under `workspace/report/`:

- **`report_data.json`** — structured JSON for dashboard rendering (metrics + LLM narrative)
- **`report.md`** — human-readable Markdown report with executive summary, sector breakdown, QA issues, and recommendations
- **`report.html`** — standalone HTML report (no external dependencies) that opens directly in a browser

Narrative sections (overview, quality analysis, failure patterns, recommendations) are
generated via a single LLM call using the same model as the experiment.
Grading scores are not yet available at this stage — the report focuses on task completion,
Self-QA scores, latency patterns, and deliverable quality.

If the LLM call fails, metric sections are still generated; narrative fields are left empty.

### Step 7: Upload to HuggingFace (`step7_upload_hf.sh`)

Uses `delete_patterns` to wipe `data/**` and `deliverable_files/**` on HF before uploading. `reference_files/**` is excluded (keeps duplicated base intact).

## Experiment YAML Configuration

Configs live in `experiments/`. Example:

```yaml
experiment:
  id: "exp999_smoke_baseline_sample"
  name: "Smoke Baseline Run (Sample)"

data:
  source: "HyeonSang/my-experiment-repo"
  filter:
    sector: null          # null = all 220 tasks
    sample_size: 3        # null = all; int = random sample (seed=42)

condition_a:
  name: "Baseline"
  model:
    provider: "azure"         # azure | openai | anthropic
    deployment: "gpt-5.2-chat"
    temperature: 0.0
    seed: 42
  prompt:
    system: "You are a helpful assistant."
    suffix: null
  qa:
    enabled: true
    min_score: 6
    max_retries: 3

execution:
  mode: "code_interpreter"    # code_interpreter | subprocess | json_renderer
  max_retries: 5
  resume_max_rounds: 3
```

`condition_b` is optional — omit for a single-condition run.

## Execution Modes

### `code_interpreter` — Azure OpenAI Responses API (Recommended)

The primary execution mode, powered by the **Azure OpenAI Responses API with built-in Code Interpreter**.

- The model autonomously writes and executes Python code inside a **secure, sandboxed container** managed by Azure OpenAI
- File generation (Excel, PDF, Word, PowerPoint, images) happens entirely within the sandbox — **no local code execution, no dependency management, no security risk**
- The Responses API streams tool calls (`code_interpreter`) in real-time, and generated files are retrieved via the Files API
- Supports iterative code execution: the model can inspect outputs, fix errors, and retry — all within a single API call
- Available on **Azure OpenAI** and **OpenAI** endpoints

> This is the recommended mode for production use with Azure OpenAI, providing the safest and most capable file generation workflow.

### `subprocess` — Local Code Execution

For providers that don't support the Responses API (e.g., Anthropic).

- LLM generates Python code → executed in an **isolated temp directory** with whitelisted environment variables
- Requires local Python packages (openpyxl, reportlab, etc.) to be installed
- Suitable for any model provider

### `json_renderer` — Fair Cross-Model Comparison

Designed for controlled A/B testing across different models.

- LLM outputs a **JSON specification** describing the deliverable structure
- A **fixed Python renderer** (same code for all models) converts the spec into files
- Eliminates code generation skill as a variable — isolates the model's understanding of the task
- Suitable for any model provider

| Mode | Compatible Providers | Security | Best For |
|------|---------------------|----------|----------|
| `code_interpreter` | Azure OpenAI, OpenAI | Sandboxed (cloud) | Production runs, complex file generation |
| `subprocess` | Any | Isolated temp dir | Non-OpenAI models |
| `json_renderer` | Any | No code execution | Fair cross-model comparison |

## Multi-Provider Support

`step2_run_inference.py` reads `condition["model"]["provider"]` to select the client:

| Provider | SDK | Env Variable |
|----------|-----|--------------|
| `azure` / `azure_openai` | `AzureOpenAI` | `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` |
| `openai` | `OpenAI` | `OPENAI_API_KEY` |
| `anthropic` | `AnthropicClient` wrapper | `ANTHROPIC_API_KEY` |

All providers return a normalized response shape (`response.choices[0].message.content`).

## Project Structure

```
batch-runner/
├── step0_bootstrap.sh           # HF repo bootstrap
├── step1_prepare_tasks.py/sh    # YAML → task list
├── step2_run_inference.py/sh    # LLM inference (resume-safe)
├── step3_format_results.py/sh   # JSON + Markdown report
├── step4_fill_parquet.py/sh     # Merge into parquet
├── step5_validate.py/sh         # Pre-upload validation
├── step6_report.py/sh           # Generate experiment report (MD + HTML + JSON)
├── step7_upload_hf.sh           # Upload to HuggingFace
│
├── core/
│   ├── config.py                # Central constants and paths
│   ├── experiment_config.py     # YAML → ExperimentConfig dataclass
│   ├── data_loader.py           # HuggingFace dataset loader
│   ├── domain_filter.py         # Sector/occupation filtering
│   ├── prompt_builder.py        # Prompt presets and builder
│   ├── prompt_loader.py         # YAML prompt template loader
│   ├── llm_client.py            # Provider-agnostic LLM client
│   ├── executor.py              # Mode dispatcher (code_interpreter/subprocess/json_renderer)
│   ├── code_interpreter.py      # Responses API + Code Interpreter runner
│   ├── subprocess_runner.py     # Code gen + safe subprocess runner
│   ├── json_renderer.py         # JSON spec + fixed renderer
│   ├── result_collector.py      # Response collection and validation
│   ├── result_formatter.py      # JSON/Markdown formatting
│   ├── repo_bootstrapper.py     # HF repo duplication
│   ├── hf_uploader.py           # HuggingFace upload logic
│   ├── needs_files.py           # File deliverable detection
│   ├── file_reader.py           # Reference file readers
│   ├── file_preview.py          # File content preview
│   └── evals_submitter.py       # OpenAI Evals submission
│
├── experiments/                 # Experiment YAML configs
│   ├── exp001_GPT52Chat_baseline.yaml
│   ├── exp002_single_baseline.yaml
│   └── exp999_smoke_baseline_sample.yaml
│
├── prompts/                     # YAML prompt templates
│   ├── code_interpreter_occupation_codegen.yaml
│   └── subprocess_occupation_codegen.yaml
│
├── tests/                       # Unit + integration tests
│   ├── test_code_interpreter.py
│   ├── test_data_loader.py
│   ├── test_domain_filter.py
│   ├── test_executor.py
│   ├── test_experiment_config.py
│   ├── test_llm_client.py
│   ├── test_prompt_builder.py
│   ├── test_result_collector.py
│   ├── test_result_formatter.py
│   ├── test_subprocess_runner.py
│   ├── test_json_renderer.py
│   ├── test_hf_uploader.py
│   └── ...
│
├── workspace/                   # Intermediate artifacts (gitignored)
│   ├── step1_tasks_prepared.json
│   ├── step2_inference_progress.json
│   └── step2_inference_results.json
│
└── results/                     # Experiment outputs (JSON + Markdown)
    └── <experiment_id>/
        └── report/              # Generated by Step 6
            ├── report_data.json
            ├── report.md
            └── report.html
```

## Data Flow

Each step reads from `workspace/` (JSON files), not from prior Python objects. Steps are independently restartable.

```
YAML config
    │
    ▼
Step 1 → workspace/step1_tasks_prepared.json
    │
    ▼
Step 2 → workspace/step2_inference_progress.json  (incremental, resume-safe)
       → workspace/step2_inference_results.json   (final)
    │
    ▼
Step 3 → results/<exp_id>/{json, md}
    │
    ▼
Step 4 → workspace/upload/data/train-*.parquet
    │
    ▼
Step 5 → validation (pass/fail)
    │
    ▼
Step 6 → results/<experiment_id>/report/{report_data.json, report.md, report.html}
    │
    ▼
Step 7 → HuggingFace Hub
```

## Testing

```bash
# Mock tests only (default, no API keys needed)
pytest

# Integration tests (requires HF_TOKEN and real data)
pytest -m integration

# All tests
pytest -m ""

# Single file
pytest tests/test_llm_client.py -v

# With coverage
pytest --cov=core --cov-report=html
```

Default: `-m "not integration"` — integration tests are skipped by default.

## Important Notes

- **o-series models** (`gpt-5.x`, `o3`, `o4`) do not support the `temperature` parameter. Passing `temperature=0` causes a 400 error.
- **`needs_files` gate**: Tasks where the rubric expects file deliverables will fail if no files are produced, triggering a retry.
- **Resume behavior**: Step 2 saves progress after each task. Re-running the same condition resumes from `workspace/step2_inference_progress.json`, only re-executing `error`/`qa_failed` tasks.
- **HF upload**: Step 7 uses `delete_patterns` to wipe `data/**` and `deliverable_files/**` before uploading. `reference_files/**` is excluded. `results/<experiment_id>/report/` is included in the upload so the dashboard can read `report_data.json` directly from HuggingFace.
- **`code_interpreter` mode** is the recommended execution mode, leveraging Azure OpenAI's Responses API with built-in Code Interpreter for secure, sandboxed file generation. Anthropic and other non-OpenAI providers must use `subprocess` or `json_renderer`.
- **Reflection loop**: When Self-QA score is below `min_score`, the retry prompt includes a structured critique (`[REFLECTION]` block) with the previous attempt's summary, itemized issues, and improvement suggestions. This follows the [Reflection agentic pattern](https://www.promptingguide.ai/techniques/reflexion). Each reflection attempt is tracked as `reflection_attempts` in the result object.

## GitHub Actions

The pipeline can be automated via GitHub Actions. See `.github/workflows/batch-run.yml` for the `workflow_dispatch` configuration that runs the full Step 0–7 pipeline with manual trigger from the Actions tab.
