# GDPVal Batch Runner

A Python pipeline that runs LLM experiments on the [OpenAI GDPVal](https://huggingface.co/datasets/openai/gdpval) Gold Subset (220 tasks) and uploads results to HuggingFace.

## Architecture

<table>
<tr>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBBWyJTdGVwIDA6IEJvb3RzdHJhcDxicj5IRiByZXBvICsgc25hcHNob3QiXSAtLT4gQlsiU3RlcCAxOiBQcmVwYXJlPGJyPkZpbHRlciArIGxvYWQgdGFza3MiXQ==" alt="Preparation" width="350" /></td>
<td align="center" style="font-size:2em;">→</td>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBDWyJTdGVwIDI6IEluZmVyZW5jZTxicj5MTE0gKyBTZWxmLVFBIl0gLS0-IERbIlN0ZXAgMzogRm9ybWF0PGJyPkpTT04gKyBNYXJrZG93biJd" alt="Execution" width="350" /></td>
</tr>
<tr>
<td></td>
<td align="center" style="font-size:2em;">↓</td>
<td></td>
</tr>
<tr>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBFWyJTdGVwIDQ6IFBhcnF1ZXQ8YnI-TWVyZ2Ugc3VibWlzc2lvbiJdIC0tPiBGWyJTdGVwIDU6IFZhbGlkYXRlPGJyPkludGVncml0eSBjaGVjayJd" alt="Delivery" width="350" /></td>
<td align="center" style="font-size:2em;">→</td>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBHWyJTdGVwIDY6IFJlcG9ydDxicj5IVE1MICsgSlNPTiJdIC0tPiBIWyJTdGVwIDc6IFVwbG9hZDxicj5IRiArIEF1dG8gUFIiXQ==" alt="Report & Upload" width="350" /></td>
</tr>
</table>


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

<img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IExSCiAgICBzcmNbIm9wZW5haS9nZHB2YWwiXSAtLT58ZHVwbGljYXRlfCBoZlsiU1VCTUlTU0lPTl9SRVBPX0lEIChIRikiXQogICAgaGYgLS0-fHNuYXBzaG90X2Rvd25sb2FkfCBzbmFwWyJkYXRhL2dkcHZhbC1sb2NhbC8iXQogICAgc25hcCAtLT4gcGFycXVldFsiZGF0YS90cmFpbi0qLnBhcnF1ZXQiXQogICAgc25hcCAtLT4gcmVmc1sicmVmZXJlbmNlX2ZpbGVzLyoqIl0KICAgIHNuYXAgLS0-IG91dFsiZGVsaXZlcmFibGVfZmlsZXMvIChlbXB0eSkiXQo=" alt="Diagram" />


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
  mode: "code_interpreter"    # code_interpreter | subprocess | sandbox | json_renderer
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

### `sandbox` — Containerized, Skill-Aware Multimodal Execution

The container evolution of `subprocess`. Adds three capabilities on top of local
code execution (see [`sandbox/README.md`](sandbox/README.md)):

- **Container isolation** — generated `solution.py` runs in a disposable Docker
  container (`--network none`, `--memory`, `--pids-limit`, `no-new-privileges`)
  built from `requirements.txt` + system tools (ffmpeg, poppler, tesseract,
  libreoffice, graphviz, GDAL, …). Falls back to the hardened local subprocess
  when Docker is unavailable (`use_docker: auto`).
- **Per-task dependency discovery** (`core/dependency_resolver.py`) — derives the
  pip packages each task needs from reference-file extensions, task keywords, and
  the generated code's imports, and flags anything missing from the image.
- **Agent Skills** (`skills/` + `core/skills_registry.py`) — famous-library
  toolkits for audio/video/document/image/data are selected per task, documented
  in the prompt, and mounted in the sandbox, giving generated code *vision*
  (video frame-by-frame, image OCR) and *hearing* (audio FFT/sampling/loudness).
- **Output control loop** (`core/deliverable_contract.py`,
  `core/artifact_verifier.py`, `core/output_qa.py`) — skills perceive the
  *inputs*; this layer verifies the *outputs*. Before codegen a deterministic
  **deliverable contract** declares what file(s) the task should produce; after
  execution the generated artifacts are selected (reference files excluded),
  **verified** (non-empty, openable, correct type), and **render-QA'd** (PDF/Office
  rasterized to PNG with blank-page detection; optional LLM vision QA behind
  `output_qa.vision.enabled`). Blocking failures trigger a **bounded repair loop**
  that feeds the concrete failure back to the model (default 1 retry). Every run
  writes a `manifest.json` recording the contract, dependency probe, per-attempt
  status, and `final_status` (`ok` / `repaired_ok` / `failed_*`).
- Pairs with the `video_analyzer` (vision) and `audio_analyzer` (hearing)
  preprocessors. See `experiments/exp026_sandbox_skills_multimodal.yaml`.

Build the image once, then select the mode:

```bash
bash sandbox/build.sh           # builds gdpval-sandbox:latest
```

```yaml
execution:
  mode: sandbox
  timeout: 1200                  # exec ceiling; 4K/video renders need >720s
  sandbox:
    image: gdpval-sandbox:latest
    use_docker: auto             # auto | never | always
    memory_gb: 8                 # video-heavy (4K) tasks; 5 GB OOM-killed a 657 MB clip
    cpus: 2.0
    max_skills: 5
    repair:                      # bounded output repair loop
      enabled: true
      max_attempts: 1
    output_qa:                   # verify + render the generated deliverables
      enabled: true
      render: true
      max_pages_per_artifact: 3
      blank_page_threshold: 0.999
      vision:                    # optional LLM vision QA (off by default)
        enabled: false
    manifest:                    # per-run manifest.json
      enabled: true
    cache:                       # cache rendered PNGs / perception by sha256
      enabled: true
```

> **Sandbox codegen safety:** keep `condition.model.reasoning_effort` at
> `low` for `sandbox` mode. gpt-5.4 draws hidden reasoning tokens from the *same*
> completion budget as the visible code, so `high` — and even `medium` on
> reference-heavy tasks — can consume nearly the whole budget on reasoning,
> emptying the visible output ("No Python code found") and exceeding the 480s
> LLM-client timeout. A post-hardening probe on a representative task measured
> `medium` at 31,146/32,768 completion tokens (95%, intermittently empty) vs
> `low` at 10,139/32,768 (31%, stable, finish=stop). `SandboxRunner` still warns
> at construction if `high` is paired with a `code_generation` budget below
> 32768. See
> `tasks/0702_thursday/sandbox_post_hardening_docker_verification_pr57.md`.

| Mode | Compatible Providers | Security | Best For |
|------|---------------------|----------|----------|
| `code_interpreter` | Azure OpenAI, OpenAI | Sandboxed (cloud) | Production runs, complex file generation |
| `subprocess` | Any | Isolated temp dir | Non-OpenAI models |
| `sandbox` | Any | Container (`--network none`) + local fallback | Multimodal/skill-aware, reproducible execution |
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

<img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRCCiAgICByb290WyJiYXRjaC1ydW5uZXIvIl0KICAgIHN0ZXBzWyJzdGVwMC1zdGVwNyBzY3JpcHRzIl0KICAgIGNvcmVbImNvcmUvPGJyLz5jb25maWcsIGxsbV9jbGllbnQsIGV4ZWN1dG9yLCBmb3JtYXR0ZXJzLCB1cGxvYWRlcnMiXQogICAgZXhwZXJpbWVudHNbImV4cGVyaW1lbnRzLzxici8-WUFNTCBleHBlcmltZW50IGNvbmZpZ3MiXQogICAgcHJvbXB0c1sicHJvbXB0cy88YnIvPnByb21wdCB0ZW1wbGF0ZXMiXQogICAgdGVzdHNbInRlc3RzLzxici8-dW5pdCArIGludGVncmF0aW9uIHRlc3RzIl0KICAgIHdvcmtzcGFjZVsid29ya3NwYWNlLzxici8-c3RlcDEvc3RlcDIgaW50ZXJtZWRpYXRlIEpTT04gYXJ0aWZhY3RzIl0KICAgIHJlc3VsdHNbInJlc3VsdHMve2V4cGVyaW1lbnRfaWR9L3JlcG9ydC88YnIvPnJlcG9ydF9kYXRhLmpzb24sIHJlcG9ydC5tZCwgcmVwb3J0Lmh0bWwiXQoKICAgIHJvb3QgLS0-IHN0ZXBzCiAgICByb290IC0tPiBjb3JlCiAgICByb290IC0tPiBleHBlcmltZW50cwogICAgcm9vdCAtLT4gcHJvbXB0cwogICAgcm9vdCAtLT4gdGVzdHMKICAgIHJvb3QgLS0-IHdvcmtzcGFjZQogICAgcm9vdCAtLT4gcmVzdWx0cwo=" alt="Pipeline Flow" />


## Data Flow

Each step reads from `workspace/` (JSON files), not from prior Python objects. Steps are independently restartable.

<img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRCCiAgICBjZmdbIllBTUwgY29uZmlnIl0gLS0-IHMxWyJTdGVwIDEgLT4gd29ya3NwYWNlL3N0ZXAxX3Rhc2tzX3ByZXBhcmVkLmpzb24iXQogICAgczEgLS0-IHMycFsiU3RlcCAyIHByb2dyZXNzIC0-IHdvcmtzcGFjZS9zdGVwMl9pbmZlcmVuY2VfcHJvZ3Jlc3MuanNvbiJdCiAgICBzMnAgLS0-IHMyZlsiU3RlcCAyIGZpbmFsIC0-IHdvcmtzcGFjZS9zdGVwMl9pbmZlcmVuY2VfcmVzdWx0cy5qc29uIl0KICAgIHMyZiAtLT4gczNbIlN0ZXAgMyAtPiByZXN1bHRzL3tleHBfaWR9L3tqc29uLG1kfSJdCiAgICBzMyAtLT4gczRbIlN0ZXAgNCAtPiB3b3Jrc3BhY2UvdXBsb2FkL2RhdGEvdHJhaW4tKi5wYXJxdWV0Il0KICAgIHM0IC0tPiBzNVsiU3RlcCA1IC0-IHZhbGlkYXRpb24gKHBhc3MvZmFpbCkiXQogICAgczUgLS0-IHM2WyJTdGVwIDYgLT4gcmVzdWx0cy97ZXhwZXJpbWVudF9pZH0vcmVwb3J0LyJdCiAgICBzNiAtLT4gczdbIlN0ZXAgNyAtPiBIdWdnaW5nRmFjZSBIdWIiXQo=" alt="Data Flow" />


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

The pipeline runs via GitHub Actions (`workflow_dispatch`). Go to **Actions → Run GDPVal Batch Experiment → Run workflow**.

### Workflow Parameters

| Parameter | What it does | Default | When to change |
|-----------|-------------|---------|----------------|
| **Experiment YAML filename** | Which experiment to run (without `.yaml`) | *(required)* | Always fill this |
| **Experiment name** | Display name for PR title. Leave empty = auto-extract from YAML | *(empty)* | Usually leave empty |
| **Dry run** | Skip HF upload + PR creation (test mode) | `false` | ✅ Check on first test run |
| **Relay run number** | **🚫 Don't touch.** Internal counter for relay continuation. Auto-incremented by the pipeline. | `0` | **Never** — auto-managed |
| **Wall-clock timeout** | Minutes before Step 2 saves a checkpoint and triggers a relay continuation. `0` = no limit. | `0` | Set to `270` for `code_interpreter` experiments |

### Example: subprocess experiment (exp008)

```
Experiment YAML filename:  exp008_GPT52Chat_resume2_elicit_v2
Dry run:                   ☐
Relay run number:          0   ← don't touch
Wall-clock timeout:        0   ← not needed (finishes in ~3h)
```

### Example: code_interpreter experiment (exp010)

```
Experiment YAML filename:  exp010_GPT52Chat_resume2_elicit_v2
Dry run:                   ☐
Relay run number:          0   ← don't touch
Wall-clock timeout:        270 ← required (4.5h, prevents 6h job timeout)
```

### How Relay Runs Work

`code_interpreter` experiments can take 6+ hours — exceeding the GitHub Actions 6-hour job limit. The relay mechanism handles this automatically:

```
Run 1 (you trigger):
  → Runs tasks 1–150 → hits 4.5h wall timeout
  → Saves checkpoint to HuggingFace
  → Auto-triggers Run 2 (relay_run=1)

Run 2 (auto-triggered):
  → Restores checkpoint from HuggingFace
  → Runs tasks 151–220 → completes
  → Steps 3–7 run normally → PR created
```

- **Max 3 relay runs** (safety limit). If the experiment still isn't done after 3 relays, it stops and requires manual intervention.
- `subprocess` experiments (~3h) don't need relay — leave `wall_timeout=0`.
