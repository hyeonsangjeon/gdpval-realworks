<p align="center">
  <img src="https://img.shields.io/badge/GDPVal-Real%20Work%20Benchmark-blueviolet?style=for-the-badge" alt="GDPVal RealWorks" />
</p>

<h1 align="center">GDPVal RealWorks</h1>

<p align="center">
  <strong>Benchmark LLMs on real expert work — not academic toy problems.</strong><br/>
  <em>A YAML-driven experiment pipeline + live dashboard for the <a href="https://arxiv.org/abs/2510.04374">GDPVal</a> Gold Subset (220 tasks).</em>
</p>

<p align="center">
  <a href="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/deploy.yml">
    <img src="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/deploy.yml/badge.svg" alt="Deploy" />
  </a>
  <a href="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/batch-run.yml">
    <img src="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/batch-run.yml/badge.svg" alt="Batch Run" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License" />
  </a>
</p>

<p align="center">
  <a href="https://hyeonsangjeon.github.io/gdpval-realworks/">🌐 Live Dashboard</a> · 
  <a href="README_KR.md">🇰🇷 한국어</a> · 
  <a href="batch-runner/README.md">📖 Batch Runner Docs</a> · 
  <a href="https://arxiv.org/abs/2510.04374">📄 Paper</a>
</p>

---

> 📊 **[Live Dashboard → https://hyeonsangjeon.github.io/gdpval-realworks/](https://hyeonsangjeon.github.io/gdpval-realworks/)**
>
> Leaderboard · Trends · Execution Errors · Grading Analysis — all in one place.

---

## The Problem

Most LLM benchmarks test **academic reasoning** — math, code puzzles, trivia.  
None of that tells you whether a model can actually **do your job**.

**GDPVal** (GDP-level Validation) is different: **220 real-world expert tasks** across 9 industry sectors and 44 occupations — Excel reports, legal docs, sales decks, the stuff people actually get paid for.

This repo automates the entire loop: **configure → run → collect → visualize** — driven by a single YAML file, executed on GitHub Actions, results on a live dashboard.

> 🎯 One YAML file. One button click. Full experiment lifecycle.

<p align="center">
  <img src="docs/images/dashboard-leaderboard.png" alt="Leaderboard — experiment rankings, KPI cards, sector heatmap" width="720" />
</p>
<p align="center"><em>Live Dashboard — leaderboard, success rates, QA scores across experiments</em></p>

<p align="center">
  <img src="docs/images/dashboard-experiment-tasks.png" alt="Task Detail — real professional task with reference files and deliverables" width="480" />
</p>
<p align="center"><em>Task Detail — real-world task description, reference files, and generated deliverables</em></p>

---

## How It Works

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


---

## ⚡ Quick Start

### 1. Fork & Clone

```bash
git clone https://github.com/hyeonsangjeon/gdpval-realworks.git
cd gdpval-realworks
```

### 2. Configure GitHub Repository Settings

#### 🔑 Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add the secrets you need:

| Secret Name | Value | Required? |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | ✅ If using Azure |
| `AZURE_OPENAI_ENDPOINT` | `https://your-resource.openai.azure.com/` | ✅ If using Azure |
| `OPENAI_API_KEY` | OpenAI API key | If using OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic API key | If using Anthropic |
| `HF_TOKEN` | HuggingFace write token ([get one here](https://huggingface.co/settings/tokens)) | ✅ For upload |

> 💡 You don't need all of them — just the provider you'll actually use.  
> For Azure users: `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` + `HF_TOKEN` is the minimum.

#### 📄 GitHub Pages

**Settings → Pages → Source** → change to **"GitHub Actions"** (not "Deploy from a branch")

#### 🔓 Workflow Permissions

**Settings → Actions → General → Workflow permissions:**

- ✅ Select **"Read and write permissions"**
- ✅ Check **"Allow GitHub Actions to create and approve pull requests"**
- Save

#### 🧹 Auto-cleanup (recommended)

**Settings → General** → ✅ Check **"Automatically delete head branches"**

> This cleans up experiment branches automatically after PR merge.

---

### 3. Run Your First Experiment

1. Go to **Actions** tab → **"Run GDPVal Batch Experiment"**
2. Click **"Run workflow"**
3. Fill in:
   - `experiment_yaml`: `exp998_smoke_baseline_sample` (smoke test, 3 tasks)
   - `dry_run`: ✅ checked (first time — skip upload)
4. Click **Run workflow** 🚀

```
✅ Step 0: Bootstrap        → HF repo ready
✅ Step 1: Prepare tasks    → 3 tasks filtered
✅ Step 2: Run inference    → LLM called for each task
✅ Step 3: Format results   → JSON + Markdown generated
✅ Step 4: Fill parquet     → Submission parquet ready
⏭️ Step 5: Validate        → Skipped (smoke test)
⏭️ Step 6: Upload          → Skipped (dry run)
```

> 🎉 If this passes, uncheck `dry_run` and run a full experiment!

---

## 📝 Write Your Own Experiment

Create a YAML file in `batch-runner/experiments/`:

```yaml
experiment:
  id: "exp001_GPT52Chat_baseline"
  name: "GPT-5.2 Chat Baseline (Full 220 tasks)"
  description: "Full baseline run with code_interpreter and Self-QA."

data:
  source: "HyeonSang/exp001_GPT52Chat_baseline"
  filter:
    sector: null          # null = all sectors
    sample_size: null     # null = all 220 tasks

condition_a:
  name: "Baseline"
  model:
    provider: "azure"
    deployment: "gpt-5.2-chat"
    temperature: 0.0
    seed: 42
  prompt:
    system: "You are a helpful assistant that completes professional tasks."
    suffix: "Generate actual files, not descriptions."
  qa:
    enabled: true
    min_score: 6
    max_retries: 3

# condition_b:            ← Add for A/B comparison (optional)

execution:
  mode: "code_interpreter"
  max_retries: 5
  resume_max_rounds: 3
```

Then trigger it from **Actions → Run workflow** with `experiment_yaml: exp001_GPT52Chat_baseline`.

---

## 🧠 Execution Modes

| Mode | How It Works | Best For |
|---|---|---|
| **`code_interpreter`** | LLM writes + runs code inside Azure/OpenAI's **secure sandbox**. Files generated in the cloud. | ✅ Production — safe, powerful |
| **`subprocess`** | LLM generates code → executed locally in an isolated temp directory. | Non-OpenAI models (Anthropic, etc.) |
| **`json_renderer`** | LLM outputs a JSON spec → a **fixed renderer** creates files. Same renderer for all models. | Fair A/B comparison across models |

> 🐳 `subprocess` mode is planned to evolve into a **container-based** execution mode — if time permits and coffee supply holds.

---

## 🔬 Self-QA: Built-in Quality Reflection Gate

Before acceptance, the same LLM working on the task inspects its own output:
Self-QA scores each output on a 0-10 scale using rubric-based self-evaluation. If the score is below the configured threshold (default: 6), it enters a reflection loop and retries.

<img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IExSCiAgICB0YXNrWyJUYXNrIl0gLS0-IGdlblsiTExNIEdlbmVyYXRlcyBPdXRwdXQiXSAtLT4gcWFbIlNlbGYtUUEgSW5zcGVjdHMiXSAtLT4gZ2F0ZXsiU2NvcmUgPj0gNj8ifQogICAgZ2F0ZSAtLT58WWVzfCBhY2NlcHRbIkFjY2VwdCJdCiAgICBnYXRlIC0tPnxOb3wgcmV0cnlbIlJldHJ5ICh1cCB0byAzeCkiXQo=" alt="Self-QA Flow" />


Self-QA checks: Are all requirements met? Are files actually produced? Is the output professional?

---

## 🏗️ Architecture

<img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRCCiAgICByb290WyJnZHB2YWwtcmVhbHdvcmtzLyJdCgogICAgd2ZbIi5naXRodWIvd29ya2Zsb3dzLzxici8-YmF0Y2gtcnVuLnltbCwgZGVwbG95LnltbCJdCiAgICBiclsiYmF0Y2gtcnVubmVyLzxici8-c3RlcCBzY3JpcHRzLCBjb3JlLCBleHBlcmltZW50cywgcHJvbXB0cywgdGVzdHMiXQogICAgc3JjWyJzcmMvPGJyLz5wYWdlcywgY29tcG9uZW50cyJdCiAgICBkYXRhWyJkYXRhLzxici8-dGVzdHMsIGdyYWRlcyJdCiAgICBzY3JpcHRzWyJzY3JpcHRzLzxici8-YWdncmVnYXRlLXRlc3RzLm1qcywgYWdncmVnYXRlLWdyYWRlcy5tanMiXQoKICAgIHJvb3QgLS0-IHdmCiAgICByb290IC0tPiBicgogICAgcm9vdCAtLT4gc3JjCiAgICByb290IC0tPiBkYXRhCiAgICByb290IC0tPiBzY3JpcHRzCg==" alt="Architecture" />


---

## 🔄 GitHub Actions Workflows

### `batch-run.yml` — Run Experiments

| Feature | Detail |
|---|---|
| **Trigger** | Manual (`workflow_dispatch`) from Actions tab |
| **Input** | Experiment YAML filename + optional dry_run flag |
| **Pipeline** | Step 0 → Step 7 (bootstrap → upload) |
| **Smart skips** | Smoke tests skip validation; dry_run skips upload + PR |
| **Auto PR** | Creates a Pull Request with experiment summary |
| **Artifacts** | Full workspace uploaded for 30 days |
| **Timeout** | 5 hours max |

### `deploy.yml` — Deploy Dashboard

| Feature | Detail |
|---|---|
| **Trigger** | Push to `main` (auto) or manual |
| **Build** | Aggregate test/grade data → React build → GitHub Pages |
| **Scope** | Only runs when `data/`, `src/`, or `scripts/` change |

---

## 🖥️ Dashboard

> **[→ Live Dashboard](https://hyeonsangjeon.github.io/gdpval-realworks/)**

Interactive experiment analytics — leaderboard, sector heatmaps, error analysis, prompt architecture viewer.

| Feature | Description |
|---------|-------------|
| **Leaderboard** | Ranked experiments with strategy, success rate, QA scores |
| **Sector Heatmap** | 9 sectors × N experiments success rate matrix |
| **Trends** | Success rate / QA / latency trend lines across experiments |
| **Execution Errors** | Error distribution, recovery funnel, CONFIDENCE NameError tracking |
| **Prompt Viewer** | See exactly what prompt was sent to the LLM — system, user, QA, config |
| **Grading** | External evaluation scores (OpenAI Evals) |
| **Experiment Detail** | Drill into 220 tasks — filter by sector, status, search |

Built with React 18 + TypeScript + Vite + Tailwind + Recharts + Framer Motion.  
Deployed automatically to GitHub Pages on every push to `main`.

📖 **[Dashboard Documentation →](src/README.md)** · 🇰🇷 **[한국어 →](src/README_KR.md)**

---

## 🧪 Testing

```bash
cd batch-runner
pip install -r requirements.txt

# Unit tests only (no API keys needed)
pytest

# Integration tests (requires real credentials)
pytest -m integration

# With coverage
pytest --cov=core --cov-report=html
```

### 🖥️ Run Locally (step by step)

```bash
cd batch-runner
export HF_TOKEN="hf_xxx"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="xxx"

./step0_bootstrap.sh experiments/exp998_smoke_baseline_sample.yaml
./step1_prepare_tasks.sh experiments/exp998_smoke_baseline_sample.yaml
./step2_run_inference.sh condition_a
./step3_format_results.sh
./step4_fill_parquet.sh
./step5_validate.sh
./step6_report.sh
./step7_upload_hf.sh --test
```

> 💡 Local execution works, but for full 220-task runs we recommend **GitHub Actions**.  
> The batch workflow parallelizes as fast as your TPM (Tokens Per Minute) quota allows — let the cloud do the heavy lifting while you grab a coffee. ☕

---

## 📚 References

- **GDPVal Paper**: [arXiv:2510.04374](https://arxiv.org/abs/2510.04374)
- **GDPVal Dataset**: [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
- **GDPVal Grading**: [evals.openai.com](https://evals.openai.com/)
- **Azure OpenAI Responses API**: [Documentation](https://learn.microsoft.com/azure/ai-services/openai/)

---

## 👤 Author

**Hyeonsang Jeon**  
Sr. Solution Engineer · Global Black Belt — AI Apps | Microsoft Asia, Korea  
[![GitHub](https://img.shields.io/badge/GitHub-hyeonsangjeon-181717?logo=github)](https://github.com/hyeonsangjeon)
[![Dashboard](https://img.shields.io/badge/Live%20Dashboard-GDPVal-blueviolet?logo=react)](https://hyeonsangjeon.github.io/gdpval-realworks/)

---

## 📄 License

MIT — See [LICENSE](LICENSE) for details.
