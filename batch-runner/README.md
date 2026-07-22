# GDPVal Batch Runner

A Python pipeline that runs LLM experiments on the [OpenAI GDPVal](https://huggingface.co/datasets/openai/gdpval) Gold Subset (220 tasks) and uploads results to HuggingFace.

## Start here

- **See published evidence:** [open the live dashboard](https://hyeonsangjeon.github.io/gdpval-realworks/).
- **Inspect the smallest real run:** open
  [`exp998_smoke_baseline_sample.yaml`](experiments/exp998_smoke_baseline_sample.yaml).
- **Launch the supported cloud path:** use
  [Run GDPVal Batch Experiment](../../../actions/workflows/batch-run.yml)
  with `experiment_yaml=exp998_smoke_baseline_sample`.
- **Find the outputs:** read
  [Results and artifacts](../docs/first-experiment.md#7-know-what-success-looks-like).

For a first run, follow the [beginner guide](../docs/first-experiment.md). It is
the canonical setup path for Azure OIDC, a disposable Hugging Face target, cost
boundaries, and the three-task smoke test.

## Architecture

<picture>
  <source media="(max-width: 960px)" srcset="../docs/images/readme-system-map-mobile.svg" />
  <img src="../docs/images/readme-system-map.svg" alt="GDPVal RealWorks pipeline from experiment YAML through execution, artifacts, external grading, and dashboard evidence" />
</picture>

## Quick Start

### Recommended: GitHub Actions

1. Fork this repository and edit only `data.source` in the
   [three-task sample config](experiments/exp998_smoke_baseline_sample.yaml) to
   point to a new disposable dataset in your Hugging Face namespace.
2. Configure the five repository secrets listed in the
   [beginner guide](../docs/first-experiment.md#5-add-repository-secrets).
3. Open the
  [Batch workflow](../../../actions/workflows/batch-run.yml) in your fork on
  `main`, enter `exp998_smoke_baseline_sample`, and leave the internal relay
   fields at their defaults.
4. Start with `dry_run: true` only after reading the boundary below.

> `dry_run: true` still performs Step 0, calls the model, runs Self-QA, and may
> write relay checkpoints. It skips Step 5, final Step 7 publication, and the
> result pull request. It is not a free or no-write simulation.

### Local step-by-step debugging

This path requires Python 3.11, Azure CLI login, a real model budget, and a
disposable Hugging Face target already configured in the sample YAML. It still
calls the model and writes to Hugging Face in Step 0.

```bash
cd batch-runner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
az login

export HF_TOKEN="<dedicated-hf-write-token>"
export AZURE_OPENAI_ENDPOINT="<azure-openai-resource-endpoint>"
CONFIG="experiments/exp998_smoke_baseline_sample.yaml"

bash step0_bootstrap.sh "$CONFIG"
bash step1_prepare_tasks.sh "$CONFIG"
bash step2_run_inference.sh condition_a
bash step3_format_results.sh
bash step4_fill_parquet.sh

# The 3-task smoke skips Step 5. Generate a model-free, unpublished report.
bash step6_report.sh --no-narrative --dry-run
```

Do not run Step 7 just to test setup. If you intentionally want to publish the
three-row smoke result, `bash step7_upload_hf.sh --test` deletes remote
`data/**` and `deliverable_files/**` in the configured target before upload.

## Authentication and environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HF_TOKEN` | Cloud publication | Dedicated Hugging Face write token used by bootstrap, relay persistence, and Step 7 |
| `AZURE_OPENAI_ENDPOINT` | Azure | Azure OpenAI resource endpoint for `AzureOpenAI(azure_endpoint=...)`; not a Foundry project URL or `/openai/v1/` base URL |
| `AZURE_CLIENT_ID` | GitHub Actions + Azure | Entra application client ID for OIDC |
| `AZURE_TENANT_ID` | GitHub Actions + Azure | Entra directory tenant ID for OIDC |
| `AZURE_SUBSCRIPTION_ID` | GitHub Actions + Azure | Azure subscription ID for `azure/login` |
| `OPENAI_API_KEY` | OpenAI | Native OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic | Anthropic API key |

The supported GitHub Actions path never injects `AZURE_OPENAI_API_KEY`; it uses
`azure/login` and OIDC. The local example uses `az login` through
`DefaultAzureCredential`. API-key-only direct runner behavior is outside this
first-run contract and is not guaranteed here.

## Pipeline Steps

### Step 0: Bootstrap (`step0_bootstrap.sh`)

- Accepts an experiment YAML path and reads the target from `data.source`:
  `bash step0_bootstrap.sh experiments/exp998_smoke_baseline_sample.yaml`
- Duplicates `openai/gdpval` to the configured public HF dataset if it does not exist
- Downloads local snapshot to `data/gdpval-local/`
- Pins one full `openai/gdpval` revision and downloads only its base data plus
  parquet-declared references into fresh staging. Before upload it verifies the
  exact source columns, ordered task prompt/taxonomy/rubric/reference assignment
  projection, complete physical reference tree, and every reference SHA-256/size.
- Persists the source-derived schema-v4 `step0_needs_files_manifest.json` before
  stripping deliverables, then validates its exact task IDs, active policy,
  signal fields, summary, source projection, and ordered reference records.
- Validates: 220 rows, rubric columns present, and exact regular reference files.
  Step 2 and each upload/copy boundary recheck those bytes before any model or
  generated-code execution
- Reuses an existing target only when it already contains a `data/` path;
  otherwise it aborts without automatic deletion. A reused target must also
  contain the canonical manifest; Step 0 never regenerates it from stripped
  data. Every run downloads the target's exact full-SHA HEAD into fresh staging
  and validates the canonical target columns, projection, manifest, reference
  tree, and empty submitter state before replacing the previous local snapshot.
  Use a new disposable target or remove the inspected partial/legacy repository
  explicitly.

### Step 1: Prepare Tasks (`step1_prepare_tasks.py`)

Reads experiment YAML config → loads dataset → applies filters (sector, sample_size) → saves task list + condition configs to `workspace/step1_tasks_prepared.json`.

### Step 2: Run Inference (`step2_run_inference.py`)

Reads prepared tasks → calls the LLM for each task → saves condition-specific
checkpoints such as `workspace/step2_inference_progress_condition_a.json` and
final results such as `workspace/step2_inference_results_condition_a.json`.
Condition A also writes legacy aliases for compatibility. Multi-round resume
re-runs `error`/`qa_failed` tasks automatically.

### Step 3: Format Results (`step3_format_results.py`)

Converts inference output into structured JSON + Markdown report under `results/<exp_id>/`.

### Step 4: Fill Parquet (`step4_fill_parquet.py`)

Merges `deliverable_text` and `deliverable_files` into the base parquet, preserving all original columns (rubric_json, rubric_pretty, etc.).

### Step 5: Validate (`step5_validate.py`)

Pre-upload integrity checks: 220 rows, required columns, deliverable file paths, etc.

### Step 6: Generate Report (`step6_report.py`)

Reads `workspace/result.json`, validates its experiment identity, and writes a
strictly pre-grading report under `results/<experiment_id>/report/`:

- **`report_data.json`** — structured self-report data
- **`report.md`** — human-readable execution summary

For the workspace-owned result, `report_data.json` is also copied to
`workspace/upload/self_report.json` for Step 7. HTML generation is disabled.
External grading remains a separate pipeline.

The default narrative path attempts two `gpt-5.4-pro` calls and then a one-call
experiment-model fallback. The GitHub workflow enforces a model-free
`--no-narrative` fallback and identity check before any publication.

### Step 7: Upload to HuggingFace (`step7_upload_hf.sh`)

Deletes remote `data/**` and `deliverable_files/**`, then uploads only
`README.md`, `data/train-*.parquet`, `deliverable_files/**`, and
`self_report.json`. `reference_files/**` remains from the duplicated base. The
Markdown report is committed through the result pull request, not uploaded as a
report directory to Hugging Face.

## Experiment YAML Configuration

Configs live in `experiments/`. Use the checked-in
[`exp998_smoke_baseline_sample.yaml`](experiments/exp998_smoke_baseline_sample.yaml)
for the first three-task run. Before launching it, change only the owner in
`data.source` and keep the repository name equal to the YAML stem:

```yaml
experiment:
  id: "exp998_smoke_baseline_sample"

data:
  source: "YOUR_HF_USERNAME/exp998_smoke_baseline_sample"
  filter:
    sector: null
    occupation: null
    sample_size: 3

condition_a:
  model:
    provider: "azure"
    deployment: "gpt-5.2-chat"
  qa:
    enabled: true
    max_retries: 3
    min_score: 6

execution:
  mode: "code_interpreter"
  max_retries: 5
  resume_max_rounds: 3
```

The real sample file contains the complete prompt and Self-QA contract.
`condition_b` is optional; omit it for a single-condition run.

## Execution Modes

### `code_interpreter` — Azure OpenAI Responses API (Recommended)

The primary execution mode, powered by the **Azure OpenAI Responses API with built-in Code Interpreter**.

- The model autonomously writes and executes Python code inside a **secure, sandboxed container** managed by Azure OpenAI
- File generation (Excel, PDF, Word, PowerPoint, images) happens in the provider-managed sandbox, reducing host-code execution and local dependency risk; normal cloud, prompt, data, and output-review risks still apply
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
| `azure` / `azure_openai` | `AzureOpenAI` | `AZURE_OPENAI_ENDPOINT` + `DefaultAzureCredential` (`az login` locally, OIDC in CI) |
| `openai` | `OpenAI` | `OPENAI_API_KEY` |
| `anthropic` | `AnthropicClient` wrapper | `ANTHROPIC_API_KEY` |

All providers return a normalized response shape (`response.choices[0].message.content`).

## Project Structure

```text
batch-runner/
├── step0_bootstrap.sh ... step7_upload_hf.sh
├── core/                         # config, clients, executors, validation
├── experiments/                  # versioned YAML experiment configs
├── prompts/                      # prompt templates
├── workspace/                    # checkpoints and upload staging
├── results/<experiment_id>/      # formatted outputs and report/
└── tests/                        # model-free unit and contract tests
```


## Data Flow

Each step reads from `workspace/` (JSON files), not from prior Python objects. Steps are independently restartable.

```text
experiment YAML
  -> workspace/step1_tasks_prepared.json
  -> workspace/step2_inference_{progress,results}_<condition>.json
  -> workspace/result.json + results/<experiment_id>/
  -> workspace/upload/{data,deliverable_files,self_report.json}
  -> result PR (report.md) + Hugging Face allowlist + Actions artifact
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
- **Resume behavior**: Step 2 saves each condition separately and only re-executes `error`/`qa_failed` tasks from that condition's checkpoint.
- **HF upload**: Step 7 deletes remote `data/**` and `deliverable_files/**`, then uploads only the explicit allowlist documented above. `reference_files/**` is preserved.
- **`code_interpreter` mode** is the recommended execution mode, leveraging Azure OpenAI's Responses API with built-in Code Interpreter for secure, sandboxed file generation. Anthropic and other non-OpenAI providers must use `subprocess` or `json_renderer`.
- **Reflection loop**: When Self-QA score is below `min_score`, the retry prompt includes a structured critique (`[REFLECTION]` block) with the previous attempt's summary, itemized issues, and improvement suggestions. This follows the [Reflection agentic pattern](https://www.promptingguide.ai/techniques/reflexion). Each reflection attempt is tracked as `reflection_attempts` in the result object.

## GitHub Actions

The pipeline runs via
[Run GDPVal Batch Experiment](../../../actions/workflows/batch-run.yml)
(`workflow_dispatch`). Launch it from the trusted `main` workflow definition.
The preflight rejects any non-`main` ref or mismatched workflow/event SHA before
checkout and cloud access.

### Workflow Parameters

| Parameter | What it does | Default | When to change |
|-----------|-------------|---------|----------------|
| `experiment_yaml` | Config filename without `.yaml` | *(required)* | Set to a tracked config stem |
| `experiment_name` | Optional display name; empty means read it from YAML | *(empty)* | Usually leave empty |
| `dry_run` | Skip Step 5, final Step 7 publication, and result PR; model/HF setup still run | `false` | Use for the first smoke only after reading the cost/write warning |
| `relay_run` | Internal relay leg counter | `0` | Leave unchanged on a manual run |
| `relay_lineage_id` | Stable identity forwarded across relay legs | *(empty)* | Internal; leave empty on leg 0 |
| `source_sha` | Initial `main` commit required by every relay leg | *(empty)* | Internal; leave empty on leg 0 |
| `wall_timeout` | `condition_a` Step 2 checkpoint watchdog, `0..290` minutes; `0` delegates to `execution.wall_timeout` in YAML and disables only when both are `0` | `290` | Keep the default unless debugging relay behavior |
| `sandbox_image_digest` | Immutable sandbox image forwarded across relay legs | *(empty)* | Internal; the workflow resolves it when needed |

### Three-task smoke input

```
experiment_yaml:       exp998_smoke_baseline_sample
experiment_name:       <empty>
dry_run:               true
relay_run:             0
relay_lineage_id:      <empty>
source_sha:            <empty>
wall_timeout:          290
sandbox_image_digest:  <empty>
```

### How Relay Runs Work

Long experiments can approach the GitHub Actions job limit. Step 2 checks its
watchdog between tasks; when it observes the deadline, it saves a checkpoint
and forwards a stable lineage into the next relay leg:

```
Run 1 (you trigger):
  → Runs tasks → reaches the configured wall timeout
  → Uploads one content-addressed generation to the exact `data.source`
  → Advances `current.json` only after the generation revision and every
    progress/deliverable SHA-256 + size are verified
  → Auto-triggers Run 2 (relay_run=1)

Run 2 (auto-triggered):
  → Restores only the marker's immutable payload revision and exact file set
  → Validates lineage, the complete ordered task set, prepared fingerprint,
    sandbox image digest, and every referenced deliverable before Azure login
  → Continues unfinished tasks → completes
  → Steps 3–7 run normally → PR created
```

This is best-effort rather than reserved handoff time: one long in-flight task
or earlier setup can consume the remaining step/job lifetime.

The experiment config bounds relay attempts. The workflow pins the initial
`main` commit in `source_sha`; a relay fails before checkout if `main` changed.
Missing, malformed, or incomplete checkpoints fail the continuation instead of
silently rerunning every task.

After Step 0, a non-mutating HF authorization check proves that the exact
`data.source` is writable before task preparation, Azure login, or model spend.
Step 0 first authenticates the pinned source projection and complete declared
reference tree, then proves the reusable target's exact HEAD before local
installation. It records every parquet-declared reference as a unique regular,
non-symlink path with SHA-256 and byte size. Step 2 and each executor recheck the
same identity immediately before upload or copy; any missing, changed, or
uncopyable input aborts before a model/container/subprocess starts.
Code Interpreter deletes provider-side input file IDs after each task on a
best-effort basis. A failed deletion may remain subject to the provider's file
retention policy, so the disposable target must not contain sensitive material.

Before Step 7 performs remote cleanup, publication requires exactly the
canonical GDPVal parquet shard, task-owned `deliverable_files/<task_id>/...`
paths, canonical `@main` URLs/URIs, and byte-for-byte equality between every
parquet-declared output and the local upload tree. Failed tasks cannot inherit
submitter text or file metadata from a reused target.

Checkpoint generations live under a source/lineage-scoped `_checkpoint/` path.
Successful cleanup removes that lineage from the dataset's current tree with an
exact-HEAD CAS commit. Failed uploads or cleanup can leave orphan generations,
and path deletion does not erase prior Hugging Face revisions or stored history.
Use only a disposable public target with non-sensitive inputs and outputs; inspect
or delete the dataset explicitly if historical retention is unacceptable.
Do not manually populate `relay_run`, `relay_lineage_id`, `source_sha`, or
`sandbox_image_digest`.

GitHub concurrency is not used as a durable queue. Do not dispatch overlapping
runs that share one `data.source`; checkpoints and destructive publication use
that same Hugging Face target.

## Results and publication

- Step 2 checkpoints and final inference JSON live in `workspace/`.
- Step 3 writes formatted outputs under `results/<experiment_id>/`.
- Step 6 writes `report_data.json` and `report.md` under
  `results/<experiment_id>/report/`, then stages `self_report.json` for HF.
- A non-dry workflow proves a one-file result PR containing `report.md` before
  Step 7 modifies Hugging Face.
- The workflow uploads `batch-runner/workspace/` and `batch-runner/results/` for
  30 days. After download, the archive root exposes `workspace/` and `results/`.

External rubric grading is a separate workflow and is not implied by Self-QA or
the Step 6 pre-grading report.
