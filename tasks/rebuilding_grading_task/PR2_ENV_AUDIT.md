# PR2 Task 200 — exp011 Env Audit

> Audit-only output for [200-env-audit.md](./200-env-audit.md). De-risks task
> 201 (`read_deliverable` tool) by confirming the libraries that the v2 grader
> can rely on inside the **grading workflow's** runtime.

## Audit scope (authoritative sources, not memory)

| evidence | path | what it tells us |
|---|---|---|
| grader workflow | `.github/workflows/grade-run.yml` | what env the **grader** actually runs in |
| dev/CI requirements | `batch-runner/requirements.txt` | every Python package `pip install -r` will pull |
| exp011 experiment yaml | `batch-runner/experiments/exp011_GPT52Chat_domain_packages.yaml` | the *generator* env we promise parity with |

`grade-run.yml` installs **only** `pip install -r batch-runner/requirements.txt`
on `ubuntu-latest` (Python 3.11). **No `apt-get install` step.** This is the
critical observation: every Python wheel in `requirements.txt` will be
importable, but any package that requires a **system binary** (ffmpeg, libreoffice,
tesseract, poppler, libsndfile…) only works if Ubuntu's base image ships it or
if a follow-up step installs it. Local macOS dev env is not authoritative.

## Library availability matrix (grading workflow env)

Legend: ✅ pip-listed and import-only · ⚠️ pip-listed but requires system binary
not installed by `grade-run.yml` · ❌ missing · 🟦 sufficient for v2 ops

### Tabular / document (structure + formatting)

| modality | tool op (SPEC §4.2) | library | requirements.txt | system dep needed | status |
|---|---|---|---|---|---|
| Excel | `inspect_structure`, `read_content`, `inspect_formatting` | `openpyxl>=3.1.0` | ✅ | none | ✅ 🟦 |
| Word | same | `python-docx>=1.0.0` (listed twice — minor dedupe nit) | ✅ | none | ✅ 🟦 |
| PowerPoint | same | `python-pptx>=0.6.0` | ✅ | none | ✅ 🟦 |
| PDF | `read_content` | `pdfplumber>=0.10.0`, `PyMuPDF>=1.21.0` (fitz) | ✅ | none | ✅ 🟦 |
| PDF render→image | `render_to_image` | `pdf2image>=1.16.0` | ✅ | **poppler-utils** (`pdftoppm`) | ⚠️ |
| Image | `render_to_image`, generic | `Pillow>=10.0.0`, `opencv-python>=4.5.0` | ✅ | none | ✅ 🟦 |
| OCR (optional) | n/a in SPEC | `pytesseract>=0.3.0` | ✅ | **tesseract** binary | ⚠️ (not required by SPEC) |
| Office→PDF (optional) | n/a in SPEC | `aspose-words`, `pypandoc`, `weasyprint` | ✅ | weasyprint needs `libpango/cairo`, pypandoc needs `pandoc` | ⚠️ (not required by SPEC) |

### Audio

| op | library | requirements.txt | system dep | status |
|---|---|---|---|---|
| `probe_audio` (sr/ch/duration/peak) | `pyloudnorm>=0.1.1`, `librosa>=0.10.0`, `pydub>=0.25.1` | ✅ | `librosa`/`pydub` resampling and non-WAV decode → **ffmpeg + libsndfile** | ⚠️ |
| explicit `soundfile` | **NOT explicitly listed** (`librosa` does declare it transitively) | ❌ explicit | libsndfile system pkg | ❌ explicit / ⚠️ system |
| optional processing | `pedalboard>=0.9.0`, `mutagen>=1.47.0` | ✅ | none for pedalboard wheel | ✅ |
| ffmpeg python wrapper | `ffmpeg-python>=0.2.0`, `moviepy>=1.0.3`, `av>=11.0.0` | ✅ | `ffmpeg-python`/`moviepy` need **ffmpeg** binary; `av` (PyAV) bundles its own | ⚠️ wrapper / ✅ PyAV |

### Video

| op | library | requirements.txt | system dep | status |
|---|---|---|---|---|
| `probe_video` (codec/fps/res/duration) | `ffmpeg-python`, `moviepy`, `av` | ✅ | needs `ffmpeg`/`ffprobe` for the wrappers; `av` is self-sufficient | ⚠️ + ✅ via PyAV |
| perception | out of scope per SPEC §10 | — | — | n/a |

### Vision perception (model side)

| element | resource | status |
|---|---|---|
| gpt-5.4 vision endpoint | Azure OpenAI Responses API w/ image input | available — same auth as main judge (OIDC) |
| image conversion before send | `Pillow` + `pdf2image` | ✅ / ⚠️ poppler |
| chart re-render | `matplotlib>=3.8.0`, `plotly`, `bokeh`, `seaborn` | ✅ |

### Audio perception (model side)

| element | resource | status |
|---|---|---|
| `gpt-audio-1.5` endpoint | Azure OpenAI (audio input) | **deployment must exist** in the same Azure resource group used by `AZURE_OPENAI_ENDPOINT` (verify via portal before 206). |

## Findings

1. **Pure-Python tools (Excel/Word/PPT/PDF structure + formatting)** are
   guaranteed available in `grade-run.yml`. No new system installs needed.
2. **`pdf2image` requires `poppler-utils` system package** which `grade-run.yml`
   does **not** install. If task 205 (vision) needs to render PDF pages,
   either:
   - prefer `PyMuPDF` (`fitz`) — pure-wheel, already in requirements, renders PDF→image; OR
   - add `sudo apt-get install -y poppler-utils` in `grade-run.yml`.
   → **Recommendation:** use `fitz` for PDF rendering, avoid the system dep.
3. **`ffmpeg`/`ffprobe` binaries are not installed by `grade-run.yml`.** This
   blocks `probe_audio`/`probe_video` if they go through `ffmpeg-python` or
   `moviepy`. Two mitigations:
   - Use `PyAV` (`av`) — wheels bundle their own ffmpeg, no system dep; already in requirements; OR
   - Add `sudo apt-get install -y ffmpeg libsndfile1` step in `grade-run.yml`.
   → **Recommendation:** prefer `PyAV` for probe ops; add the apt step only if PyAV proves insufficient for a specific deliverable codec.
4. **`soundfile` is not explicitly listed** in `requirements.txt`. It is
   pulled transitively by `librosa`/`pedalboard` today, but transitive deps
   are fragile.
   → **Recommendation:** add `soundfile>=0.12.0` explicitly in
   `requirements.txt` during task 201.
5. **`libsndfile` (system)** likewise not installed. `soundfile` wheels on
   `manylinux` bundle libsndfile, so this is **OK on `ubuntu-latest`** — but
   verify by `python -c "import soundfile; soundfile.info(...)"` in 201.
6. **Audio perception model `gpt-audio-1.5`** is the only thing that cannot
   be verified from repo files alone. Verification deferred to task 206 (which
   will deployment-list check before first call).
7. **`python-docx` is listed twice** in `requirements.txt` (line 13 and line
   ~32). Cosmetic dedupe candidate; not blocking.

## Decision rule outcome (per task 200)

- All Python libraries required by SPEC §4.2 ops are present or trivially
  addable (`soundfile` explicit).
- All gaps are **system-binary gaps** with pure-Python fallbacks already
  in `requirements.txt` (`fitz` instead of `pdf2image+poppler`, `PyAV`
  instead of `ffmpeg-python+ffmpeg-binary`).
- Therefore: **proceed with task 201 unchanged** in scope. No user alert.
- Carry these implementation notes into task 201:
  - prefer `fitz` for PDF→image
  - prefer `PyAV` for audio/video probe
  - add `soundfile>=0.12.0` to `requirements.txt`
  - verify `gpt-audio-1.5` deployment as the first thing task 206 does

## Out of audit

- TPM/cost ceilings (covered by task 302).
- gpt-5.4 vision deployment availability (treated as same auth as main judge;
  Azure resource check is operational, not env).
- Container migration to GHCR (SPEC §10, out of scope).
