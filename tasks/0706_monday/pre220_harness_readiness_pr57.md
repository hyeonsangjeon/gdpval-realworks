# Pre-220 Harness Readiness Sweep — PR #57 (sandbox + skills + multimodal)

**Branch:** `hyeonsangjeon-sandbox-skills-multimodal-eval` @ `2507309`
**Date:** 2026-07-06
**Scope:** Before the (owner-gated) full 220-task run, cheaply de-risk the
sandbox harness by exercising its **deterministic surface** on **all 220 GDPVal
tasks** — with **no model call, no Docker, and no Azure auth**. Prior runtime
verification (`tasks/0702_thursday/…`) proved the Docker path end-to-end on 1–2
tasks; this pass proves the *task-independent* harness logic does not choke on
any of the 220 task/reference shapes across all 9 sectors.

**Result:** ✅ **Harness is robust across the full benchmark — 0 exceptions on
220 tasks.** The only real pre-220 gap is **data provisioning**: 6 large
audio/video reference files (3 tasks in the *Information* sector) are missing
from the local snapshot and must be re-fetched before the multimodal path can be
exercised. No code change required. PR #57 remains **OPEN / MERGEABLE**.

---

## 1. What was swept

Per task, the model-free deterministic harness surface used by `SandboxRunner`
before any code generation:

| Step | Function | What it validates |
|---|---|---|
| Reference resolution | `DEFAULT_LOCAL_PATH / ref` + exists (step2 lines 686–700) | local data availability |
| Deliverable contract | `infer_deliverable_contract(prompt, refs, {})` | expected extensions + confidence |
| Skill selection | `SkillsRegistry(None).select(refs, prompt, 5)` | which skills each task activates |
| Dependency resolution | `resolve(refs, prompt, base_packages)` | predicted pip deps vs the sandbox base image |

All pure/deterministic — no LLM, no container, no network, no credentials.
Runtime: a few seconds for all 220 tasks.

---

## 2. Headline results

| Metric | Value |
|---|---|
| Tasks swept | **220** across **9** sectors |
| **Harness exceptions** | **0** ✅ |
| Zero-skill tasks | **0** ✅ (every task activates ≥1 skill) |
| `missing_from_base` packages | **{}** ✅ (image covers every predicted dep) |
| Contract confidence | medium **132**, high **80**, low **8** |
| Reference files | 261 declared → **255 resolved, 6 missing** |
| Modality (declared refs) | audio **4**, video **1**, image **8** |

---

## 3. Finding — harness robustness (GREEN)

Running contract inference, skill selection, and dependency resolution across
**all 220 tasks raised zero exceptions.** The harness handles the full diversity
of prompts and reference-file shapes (0–8 refs per task, mixed extensions,
95 tasks with no declared refs) without crashing. Combined with the 65 passing
unit tests and the Docker end-to-end proof, the harness logic is merge-ready.

## 4. Finding — dependency coverage (GREEN)

Every package predicted by the dependency resolver across all 220 tasks is
already in the sandbox base-package set (`missing_from_base = {}`). This matches
the `docker run` tool smoke (openpyxl, PyMuPDF, opencv, av, python-docx/pptx,
pandas, LibreOffice, ffmpeg, tesseract all present). No per-task pip install is
predicted to be required for the baked image.

## 5. Finding — reference-data gap (ACTION before the multimodal run)

6 of 261 declared reference files do not resolve locally. **All 6 are large
audio/video media in the _Information_ sector** — the media whose whole purpose
is to exercise the "vision for video / hearing for audio" thesis:

| Task | Occupation | Refs resolved | Missing |
|---|---|---|---|
| `4b894ae3` | Audio and Video Technician | 3 / 6 | 3 media files |
| `75401f7c` | Film and Video Editors | 1 / 2 | 1 media file |
| `a941b6d8` | Film and Video Editors | 0 / 2 | 2 `.mp4` (the only video task; 657 MB 4K) |

These files existed during the 0701 A/B smoke (the video task ran under Docker
then) but are absent now — cleaned during the earlier disk-full recovery. They
are **re-fetchable** from HuggingFace via each task's `reference_file_urls`
(`auto_download=False` means they will not be pulled automatically).

- **Not a harness bug.** The harness degrades gracefully (treats missing refs as
  fewer/no files; step2 already prints a per-file "Reference file not found"
  warning). But a full 220 run today would **silently under-exercise the
  audio/video perception path** for these 3 tasks.
- **Pre-220 action:** re-fetch these 6 files before the multimodal run. Disk is
  currently tight (~12 GiB free); the 4K video alone is ~657 MB, so provision
  deliberately. Deferred here because the full run is owner-gated and disk is
  constrained — provisioning now would be premature.

## 6. Finding — 8 low-confidence / empty-extension contracts (BY DESIGN)

8 tasks yield an empty `expected_extensions` with `confidence=low`. All 8 have
prompts that name no file type **and** no reference files to infer one from
(e.g. `36d567ba`, `f3351922`, `74d6e8b0`). This is the contract's intended
behavior — it downgrades rather than guessing a wrong extension that could block
a valid deliverable. For these 8, the deterministic extension guard is
intentionally permissive and the model's own judgment drives the output type.
Documented, not a defect.

---

## 7. Per-sector representative snapshot

| Sector | contract ext | conf | skills |
|---|---|---|---|
| Professional, Scientific & Technical | `.xlsx` | medium | data, document |
| Government | `.docx, .pdf` | medium | document, data, image |
| Information | `.xlsx, .pdf, .png` | high | document, data, image, audio |
| Manufacturing | `.docx, .xlsx` | medium | document, data, audio, video |
| Real Estate & Rental | `.docx` | medium | document, data, video |
| Finance & Insurance | — | low | document |
| Wholesale Trade | `.pptx` | medium | document, audio, video |
| Health Care & Social Assistance | `.xlsx, .docx, .pdf` | high | document, data |
| Retail Trade | `.pptx, .pdf` | high | document |

Skill activation and contract inference behave sensibly per sector.

---

## 8. Residual risks & recommended pre-220 actions

1. **Re-fetch the 6 missing A/V media files** (tasks `4b894ae3`, `75401f7c`,
   `a941b6d8`) before the multimodal run, or accept that those 3 tasks run
   text-only. Highest-value pre-220 action.
2. **Video-task resources** — the single 657 MB / 4K video task remains the
   heaviest; exp026 already raised sandbox memory→8 GB and timeout→1200 s for it
   (0702 hardening). Re-verify once its media is re-provisioned.
3. **8 low-confidence contracts** — expected; no action, but worth watching in
   grading to confirm the model chose a sensible deliverable type unaided.

None of these block merging the harness. They are data-provisioning /
run-configuration items for the eventual full run.

---

## 9. Verdict

- **Harness: ready for the full 220 run** from a logic standpoint — 0 exceptions
  across all 220 tasks, every task activates a skill, and the image covers every
  predicted dependency.
- **One real pre-220 gap:** re-provision 6 missing A/V media files so the
  audio/video perception thesis is actually exercised. Data, not code.
- **No code change made** (the sweep found no harness bug; the empty-extension
  and missing-media findings are by-design and data-provisioning respectively).

**PR #57 remains OPEN, not draft, MERGEABLE.** No full 220 run, no Actions
dispatch, no merge, no PR title/body edits, no local data or binaries committed.

---

## Appendix — command

```bash
# model-free deterministic sweep over all 220 tasks (no LLM / Docker / auth)
PYTHONPATH=. python pre220_readiness_sweep.py   # -> pre220_sweep.json
```

Machine-readable summary: `pre220_harness_readiness_pr57.json` (this directory).
