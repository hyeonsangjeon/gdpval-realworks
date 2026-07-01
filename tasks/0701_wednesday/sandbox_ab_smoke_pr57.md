# Sandbox A/B Smoke — PR #57 (skills-only vs hybrid perception)

Branch: `hyeonsangjeon-sandbox-skills-multimodal-eval` · Scope: bounded smoke, **not** a full run · Date: 2025-07-01

## Core question

Can the sandbox harness solve representative GDPVal tasks with **only the main solving
model + local open-source skills** (condition **A**, audio/video GPT preprocessors
disabled), and how does that compare to the **current exp026 hybrid** (condition **B**,
skills + GPT audio/video preprocessors)? This informs whether the harness is viable for
future non-GPT providers (Grok/Llama) that lack GPT perception models.

## TL;DR verdict

- **Skills-only (A) is viable.** 6/6 representative tasks produced valid, verified
  deliverables using only the main model + local skills. This is the provider-agnostic
  signal the owner asked for: no GPT-specific perception was required for the harness to
  produce openable, contract-valid outputs across document, spreadsheet, deck, audio, and
  video modalities.
- **Hybrid (B) did not categorically beat skills-only on pass/fail** in this smoke (5/6),
  but the **audio preprocessor measurably enriched audio-task outputs** (more complete
  deliverable sets, higher contract confidence). The single B failure was the hardest task
  (657 MB 4K video) and is attributable to **resource limits + LLM code-gen variance**, not
  to skills-vs-hybrid, because the **video preprocessor could not run in this environment**.
- **PR #57 is safe to merge from a smoke perspective.** No harness bug was found. All
  manifests are clean (relative paths, no secret/PII leakage). The findings below are
  configuration/environment notes, not code defects. Two are worth folding into exp026
  defaults before a large run (reasoning budget, video container memory/timeout).

## Setup

| Item | Value |
|---|---|
| Backend | **docker** (`gdpval-sandbox:latest`) for every non-failed task in both A and B |
| Tasks | 6 pinned (`tasks/0701_wednesday/smoke_task_ids.txt`) |
| Solving runs | 12 (6 × A, 6 × B) |
| Repair | `max_attempts=1`, `resume_max_rounds=1` |
| Output control loop | contract + verifier + manifest + render QA — **enabled** |
| `output_qa.vision.enabled` | **false** in both (deterministic render/openability/blank-page QA only) |
| Vision/LLM judge cost | none (disabled as required) |

### Commands (per variant)

```bash
# from batch-runner/, venv = session testenv, PYTHONPATH=.
# A: skills_only strips preprocessors; B: hybrid keeps them
python tasks/0701_wednesday/run_ab_smoke.py \
    --yaml tasks/0701_wednesday/exp_smoke_sandbox_ab.yaml \
    --variant {skills_only|hybrid} \
    --task-ids-file tasks/0701_wednesday/smoke_task_ids.txt

# then, with Azure AAD token auth forced (see auth note):
python step2_run_inference.py --condition condition_a
```

Config overrides live in `tasks/0701_wednesday/exp_smoke_sandbox_ab.yaml` (a copy of
exp026 with two smoke deviations, documented inline and below). The driver
`run_ab_smoke.py` pins the 6-task subset, strips `preprocessors:` for `skills_only`,
keeps them for `hybrid`, forces `mode: sandbox`, `use_docker: auto`, and disables the
legacy per-condition QA so only the new output control loop runs.

### Task subset (representative modalities)

| Task | Occupation | Modality / deliverable | Reference files |
|---|---|---|---|
| `7d7fc9a7` | Accountant | XLSX workbook | + `.pdf` ref |
| `e6429658` | Nurse Practitioner | DOCX/PDF report | + `.png` ref |
| `5a2d70da` | Mechanical Engineer | PPTX / multi-file | multi-ref |
| `ff85ee58` | Sound Engineer | Audio (`.mp3`+`.wav`) | audio refs |
| `38889c3b` | Music Producer | Audio (`.wav`) | audio ref |
| `a941b6d8` | Film/Video Editor | Video (`.mp4`, 657 MB 4K) | video ref |

The 3 document/deck tasks have no audio/video references, so A and B are configured
identically for them — they are a control group. The 2 audio tasks and 1 video task are
where A and B differ by design.

## Results matrix

| Task | Modality | A `final_status` | A att | B `final_status` | B att | Backend |
|---|---|---|---|---|---|---|
| `7d7fc9a7` | XLSX | `ok` | 1 | `ok` | 1 | docker |
| `e6429658` | DOCX | `ok` | 1 | `ok` | 1 | docker |
| `5a2d70da` | PPTX/multi | `repaired_ok` | 2 | `ok` | 1 | docker |
| `ff85ee58` | Audio mp3+wav | `ok` | 1 | `ok` | 1 | docker |
| `38889c3b` | Audio wav | `ok` | 1 | `ok` | 1 | docker |
| `a941b6d8` | Video mp4 (657 MB) | `repaired_ok` | 2 | **`failed_execution`** | — | docker |
| **Total** | | **6/6 ok** | | **5/6 ok** | | |

Every completed task: `verify_ok=True`, zero blocking verification errors, zero render-QA
warnings, manifest present with stable `schema_version`, and **no absolute-path / secret /
PII leakage** (manifests use relative paths; stdout/stderr tails sanitized).

## Preprocessor behavior (the A vs B mechanism)

Confirmed from B's step2 log:

```
[music] 🎵 Preprocessor injected 820 chars into prompt      # audio_analyzer / gpt-audio-1.5
[sound] 🎵 Preprocessor injected 2334 chars into prompt     # audio_analyzer / gpt-audio-1.5
[video] ⚠️  Video preprocessor: no frame backend (cv2/av) installed — skipping   (×2)
```

- **Audio preprocessor ran in B** for both audio tasks and injected GPT audio analysis
  into the prompt. Effect: on the Sound Engineer task the injected analysis (2334 chars)
  raised the deterministic **contract confidence from `medium`→`high`** and expanded the
  expected set (`.mp3/.wav/.png` → `.json/.mp3/.wav/.pdf/.png`), and B produced a **richer
  deliverable set (7 artifacts vs A's 2)**: mix-report JSON, summary PDF, preview MP3,
  spectrogram + alignment PNGs, plus the 24-bit master WAV. Both A and B verified `ok`, so
  the preprocessor improved **output completeness/quality**, not pass/fail, on this smoke.
- **Video preprocessor was skipped in both rounds of B.** The preprocessor runs on the
  **host/orchestrator** (the step2 process), whose environment lacks the `cv2`/`av` frame
  backend, so `video_analyzer` degraded gracefully to a no-op. Consequently **B's video arm
  was effectively inactive** — for the video task, B ≡ A in perception. This must be kept
  in mind when reading the video result: it is *not* evidence about hybrid video perception.

## Harness failures vs model-quality failures

| Observation | Classification |
|---|---|
| `5a2d70da` A needed 1 repair (`repaired_ok`), B passed first try | Model/code-gen variance (both succeeded) |
| `a941b6d8` B: Round 0 OOM (exit 137, 5 GB container limit) then resume-round runtime crash (exit 1 in generated `composite_final(...)`) | **Harness/resource limit + code-gen variance.** 657 MB 4K video is marginal against the 5 GB memory cap and 720 s timeout. A happened to recover in its resume round; B did not. Not a skills-vs-hybrid signal (video preprocessor was skipped in both). |
| All audio/doc/deck tasks | Clean harness behavior; no harness defects |

No failure in this smoke was caused by a harness/control-loop bug. The contract, verifier,
manifest, render-QA, and repair loop behaved correctly, including on the failed video task
(it was correctly reported as `failed_execution`, not silently passed).

## Key findings (fold into exp026 before a large run)

1. **Reasoning-budget starvation at `reasoning_effort: high`.** gpt-5.4 at `high` on the
   sandbox codegen prompt spends the entire completion budget on hidden reasoning and
   returns **empty visible content** (finish=length) → the runner raises "No Python code
   found". Probes: high/16384→empty, high/32768→empty; medium/32768→20k reasoning + 38k
   chars but ~340 s latency. **Smoke used `reasoning_effort: low` + `code_generation:
   32768`** to guarantee non-empty output under the 480 s client timeout. A/B fairness holds
   because effort is constant across both conditions. **Recommendation:** exp026's
   `reasoning: high` + `code_generation: 16384` will produce empty outputs on complex
   sandbox tasks — raise the token budget and/or lower effort for sandbox mode.
2. **Docker image-store registration.** Docker Desktop's buildx stored the image where
   `docker images` lists it but classic `docker image inspect` (used by the runner's
   `docker_image_exists()`) returned "No such image", forcing local fallback. Fix:
   `docker tag <image_id> gdpval-sandbox:latest` re-registers it in the classic store so the
   runner selects docker. No code change needed; environment/build note.
3. **Video task is resource-marginal.** 657 MB 4K video + 5 GB container cap + 720 s timeout
   is the failure envelope. **Recommendation:** for video-heavy tasks raise
   `execution.sandbox` memory and `execution.timeout`, and/or have the video skill downsample
   before compositing. This is the single most likely large-run flake source.

## Deviations from the smoke spec (all documented, none affect A/B validity)

- `reasoning_effort: low` (spec said "same as exp026 unless local config requires
  otherwise"; empty-output starvation required it). Constant across A and B.
- Video preprocessor did not execute in B (host lacks `cv2`/`av`). Reported, not hidden.
- Docker image built once locally, trimmed to drop `aspose-words` (no arm64 wheel);
  backend choice (docker) is reported per task, not hidden.

## Merge safety (smoke perspective)

**Safe to merge PR #57.** Rationale:

- Output control loop is correct end-to-end: contracts inferred, artifacts selected with
  reference exclusion, verifier + render QA deterministic, repair bounded, manifests clean.
- Existing modes untouched (smoke only exercised `sandbox`).
- No secret/PII/local-path leakage in any manifest or committed artifact.
- The one failure is an expected resource-limit flake on the hardest task, correctly
  surfaced as `failed_execution` — the harness did not mask it.

**Non-blocking pre-large-run recommendations:** (1) fix sandbox reasoning/token budget so
`high` effort cannot yield empty output; (2) raise video-task memory/timeout; (3) document
that GPT audio/video preprocessors require their perception deps (`cv2`/`av`) on the
orchestrator host, else they no-op.

## Residual risks

- **Non-determinism on marginal tasks** (video): a single run can pass or fail; a large run
  needs the memory/timeout bump above to be reliable.
- **Preprocessor host-dependency**: the "hybrid" advantage for video is unverified here
  because the video preprocessor never ran; re-test on a host with `cv2`/`av` to measure it.
- **Contract inference is prompt-sensitive**: injected preprocessor text legitimately raises
  contract confidence/extension coverage (observed on the Sound Engineer task). Good for
  hybrid, but means A and B contracts can differ on audio/video tasks by design.

## Reproducibility notes

- Auth: the SP client-secret in `.env` is invalid and the OpenAI SDK auto-prefers an API
  key over the AAD token; the runner forces `DefaultAzureCredential` (az login token) by
  unsetting `AZURE_CLIENT_*` / `AZURE_*_API_KEY` before step2. Keep `AZURE_OPENAI_ENDPOINT`.
- Generated binary deliverables (video/wav/zip) are intentionally **not committed**; only
  this report, the machine-readable summary, and the smoke config/driver are committed.

PR #57 remains **open and unmerged**.
