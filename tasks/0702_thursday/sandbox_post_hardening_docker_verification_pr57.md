# Post-Hardening Docker Verification — PR #57 (sandbox + skills + multimodal)

**Branch:** `hyeonsangjeon-sandbox-skills-multimodal-eval`
**Pre-verification HEAD:** `203790c` (pre-220 hardening pass)
**Scope:** Prove the cleaned/reset Docker environment can rebuild
`gdpval-sandbox:latest` and run the sandbox path end-to-end after the hardening,
and classify any failure as **harness** vs **model-quality**. This is a
verification pass; the one code change below is a narrow, evidence-backed fix for
a real empty-output config bug surfaced during the run.

**Result:** ✅ Docker path fully verified (rebuild + tool smoke + synthetic
harness run + real GDPVal task end-to-end). One real bug found and fixed:
`exp026` sandbox `reasoning_effort` was **marginal at `medium`** (intermittent
empty output) → changed to **`low`**. PR #57 remains **OPEN / MERGEABLE**.

---

## 1. Environment state before touching anything

| Check | Value |
|---|---|
| git identity | `Hyeonsangjeon` (owner identity configured in the worktree) |
| branch / HEAD | `hyeonsangjeon-sandbox-skills-multimodal-eval` @ `203790c` (local == remote) |
| dirty tracked files | none (only untracked `data/gdpval-local` symlink — not staged) |
| Docker daemon | up, Docker `29.1.3` |
| local images | **0** — `gdpval-sandbox:latest` absent (expected post-reset) |
| Data volume free | **27 GiB** (86% used) before build |

---

## 2. Image rebuild (arm64 / aspose-words recovery)

`requirements.txt` pins `aspose-words>=25.0.0`, which has **no arm64 (Apple
Silicon) wheel**. Recovery followed the documented branch recipe: build from a
**temporary context** with that one line trimmed — **no tracked file was
modified**.

```bash
# temp context assembled under a session scratch dir (NOT the repo):
#   Dockerfile, .dockerignore, skills/, requirements.txt (aspose-words commented)
docker build -t gdpval-sandbox:latest <temp_context>
```

- Build time ≈ 8 min on this machine. apt LibreOffice layer ≈ 113 s; full pip
  scientific stack (pandas, scipy, scikit-image, opencv, av, PyMuPDF, openpyxl,
  python-docx/pptx, pdfplumber, …) succeeded. All 7 stages `DONE`.
- Image: `gdpval-sandbox:latest`, `arch=arm64`, ≈ **2.21 GB** manifest.
- Disk after build: **12–13 GiB** free (build cost ≈ 14 GiB).

> Note: `aspose-words` is only needed for a niche doc-conversion path; the baked
> LibreOffice + PyMuPDF + python-docx/pptx cover the sandbox deliverable
> pipeline. The trim is arm64-local only; CI (`ubuntu-latest`, x86_64) builds the
> unmodified `requirements.txt`.

---

## 3. `docker run` tool smoke (baked toolchain)

```bash
docker run --rm --network none gdpval-sandbox:latest \
  python -c "import openpyxl, fitz, cv2, av, docx, pptx, pandas; print('ok')"
```

- Python **3.11.15** (`aarch64`); all key modules import OK.
- CLI tools present: **LibreOffice 7.4.7.2**, **ffmpeg**, **tesseract**.

---

## 4. Synthetic harness Docker-path smoke (no model)

`SandboxRunner(use_docker="always")` with `complete` patched to emit a small
openpyxl program (writes `quarterly_revenue.xlsx`); render QA + repair off.

| Check | Result |
|---|---|
| `sandbox_backend` | **docker** (container stdout marker present) |
| artifact generated → selected primary | `quarterly_revenue.xlsx` |
| verifier openability | openable, kind=spreadsheet, suffix `.xlsx` |
| deliverable contract | inferred `.xlsx` |
| manifest | written, `schema_version=1.0` |
| path leaks (absolute paths, temp dirs, email) | **none** (relative paths only) |
| `final_status` | **ok** |

→ **Mount / execute / collect / select / verify / manifest all pass under
Docker, independent of any model call.**

---

## 5. Host video preflight warning (Finding 3 regression check)

The host test environment has **no `cv2`/`av`** → `video_analyzer.frame_backend_available()`
returns `None` (a genuine "backend absent" host). Replaying the committed step2
preflight block against the **real** `exp026` `condition_a` (which configures a
`video_analyzer` preprocessor) fires the one-time warning branch as designed.
→ **Preflight warning path verified.**

---

## 6. Real single-task capstone + the empty-output finding

One real GDPVal task run through **step2** with the hardened `exp026` settings
(Docker `auto`, timeout 1200, memory 8 GB, `code_generation` 32768). Task:
accountant `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` (spreadsheet+report, 6 reference
files, no audio/video). Auth: `DefaultAzureCredential` (Entra ID / owner `az`
login). Preprocessors disabled for this task subset.

### 6.1 What happened

The **first real run at `reasoning_effort: medium` failed** with
`✗ No Python code found in LLM response` — empty visible content, the exact
symptom the hardening targeted. An instrumented probe (recording `finish_reason`
+ token usage on the **real runner prompt**) explained why:

| effort | finish | completion / budget | reasoning tok | visible chars | headroom | latency |
|---|---|---|---|---|---|---|
| `high` | — | exceeded 480 s client timeout | — | (unusable) | — | >480 s |
| `medium` | stop | **31,146 / 32,768 (95%)** | 22,790 | 30,094 | ~1,600 (5%) | 347 s |
| `low` | stop | **10,139 / 32,768 (31%)** | 2,758 | 28,598 | ~22,600 (69%) | 106 s |

gpt-5.4 draws hidden reasoning tokens from the **same** completion budget as the
visible code. At `medium`, reasoning alone reached 22,790 and completion hit 95%
of the 32,768 budget — one slightly larger reasoning draw returns **0 visible
tokens** → "No Python code found" (reproduced live). At `low`, reasoning is
~2,758, leaving ~69% headroom and running **3.3× faster** with comparable code
size.

### 6.2 End-to-end at `low` (Docker)

Re-running the same task at `low` through the real step2 runner succeeded fully:

| Field | Value |
|---|---|
| status | **success** (112 s, 6 files) |
| `sandbox_backend` | **docker** |
| `final_status` | **ok** |
| `execution_mode` | sandbox |
| `selected_skills` | document, data, audio, video |
| primary artifacts | `…Schedule.xlsx`, `…Summary.pdf`, `…Reconciliation_Chart.png` |
| contract exts / conf | `.xlsx/.pdf/.png` / medium |
| verification | `ok=True`, `blocking_errors=[]` |
| `schema_version` | 1.0 |
| manifest path leaks | **none** (relative reference/generated paths) |

### 6.3 Classification — harness vs model-quality

The empty output is a **model-quality / config-tuning** issue (empty visible
content), **not a harness bug**: the runner correctly detected "no code" and
triggered the bounded resume, and the Docker execution path is independently
proven by §4 and by the successful `low` end-to-end run. Root cause = `medium`
reasoning variance intermittently starving the shared completion budget.

---

## 7. Fix applied (narrow, evidence-backed)

The hardening's `medium` default was still a *known* empty-output edge. Changed
`exp026` sandbox codegen only:

- `condition_a.model.reasoning_effort`: **`medium` → `low`** (comment updated with
  the probe table above). `code_generation` stays `32768`.
- Updated the `experiment.name` / `condition_a.name` labels and the control note.
- Updated `batch-runner/README.md` sandbox-safety caution to recommend `low` and
  cite the measured medium-vs-low headroom.

Untouched: the `SandboxRunner` `high`+`<32768` guard (still valid; `medium`
remains a legitimate setting for lighter non-sandbox experiments, so no new
guard noise was added), and `subprocess` / `code_interpreter` / `json_renderer`
behavior.

**Tests:** `test_sandbox_runner.py`, `test_video_analyzer.py`, `test_executor.py`
→ **65 passed**. exp026 YAML re-validated (`reasoning_effort=low`,
`code_generation=32768`). No Python files changed (config + docs only).

---

## 8. Merge-readiness verdict

- **Harness: safe to merge from the smoke perspective.** Cleaned Docker env
  rebuilds the image and runs the full sandbox path (mount → execute → select →
  verify → manifest) end-to-end on a real GDPVal task with `final_status=ok` and
  no path leaks.
- **Config bug fixed:** the last known empty-output edge (`medium`) is removed by
  the `low` default, validated by a real end-to-end Docker run.
- **Residual risk (low):** `low` reasoning trades some deep-reasoning depth for
  reliable visible output; acceptable for the sandbox codegen step, whose job is
  to emit runnable code. Deliverable *quality* is still judged downstream by the
  grader, not by this harness.
- **arm64-only build note:** the `aspose-words` trim is a local Apple-Silicon
  workaround; CI x86_64 builds the unmodified requirements.

**PR #57 remains OPEN, not draft, MERGEABLE.** No full 220 run, no Actions
dispatch, no merge, no PR title/body edits performed.

---

## Appendix — commands (sanitized)

```bash
# state
git fetch --all --prune && git rev-parse --abbrev-ref HEAD && git log --oneline -1
docker version; docker images; df -h /System/Volumes/Data

# rebuild (temporary trimmed context; no tracked files touched)
docker build -t gdpval-sandbox:latest <temp_ctx>
docker run --rm --network none gdpval-sandbox:latest python -c "import openpyxl,fitz,cv2,av,docx,pptx,pandas;print('ok')"
docker run --rm --network none gdpval-sandbox:latest bash -lc "soffice --version; ffmpeg -version|head -1; tesseract --version|head -1"

# synthetic harness Docker-path smoke (no model): SandboxRunner(use_docker="always")

# real single-task capstone (owner Entra ID auth; DefaultAzureCredential)
#   prepared single-task file built from exp026 (execution block preserved)
PYTHONPATH=. python step2_run_inference.py --no-resume --condition condition_a
#   instrumented probe recorded finish_reason + usage at medium and low
```

_Config/docs only. Generated deliverables, Docker artifacts, caches, and local
data are intentionally excluded from the commit._
