# Sandbox Multimodal Capstone — PR #57 (audio + 4K video, real Docker end-to-end)

Branch: `hyeonsangjeon-sandbox-skills-multimodal-eval` · PR #57 (OPEN, unmerged)
Scope: runtime proof only — sandbox mode. `subprocess` / `code_interpreter` /
`json_renderer` untouched. No full 220 run, no Actions dispatch, no merge.

## Goal
Prove the container path works end-to-end on real multimodal reference files:
one **audio** task and one **4K video** task, each running the main solving model
(gpt-5.4, reasoning_effort=low) with local Skills inside Docker plus the
host-side audio/video perception preprocessors. This is the runtime half that was
intentionally deferred after the pre-220 hardening pass.

## Harness bug found + fixed (only code change in this pass)
`core/sandbox_runner.docker_image_exists()` used `docker image inspect <name:tag>`
to decide whether the sandbox image is present. Under Docker Desktop's default
**containerd image store** (`io.containerd.snapshotter.v1`), `docker image inspect
<name:tag>` returns *"No such image"* even when the image is listed by
`docker image ls <name:tag>` and inspectable by ID — most reproducibly right after
a daemon restart. That misdetection silently routed the run to the local fallback,
which then failed on host libs (e.g. `No module named 'soundfile'`).

Fix: when `docker image inspect` reports absent, fall back to
`docker image ls --quiet <image>` (returns the ID or empty). Fast path is
preserved — the `ls` call only runs when `inspect` says "missing". Added 3
regression tests (containerd-store fallback, both-empty → false, fast-path skips
`ls` when inspect succeeds).

- `core/sandbox_runner.py`: +24/-2 (hardened `docker_image_exists`)
- `tests/test_sandbox_runner.py`: +40 (3 tests + fake-run factory)
- 30/30 `test_sandbox_runner.py` pass; `py_compile` clean.

## A — Audio capstone (task 4b894ae3, Information / audio production)
3× 48 kHz stereo stem WAVs (~57 MB each). Deliverable: edited stems + mix + report.

| field | value |
|---|---|
| runner backend | **docker** |
| execution_mode | sandbox |
| preprocessor | `audio_analyzer` (gpt-audio-1.5) ran → **799 chars** injected into prompt |
| selected_skills | audio, document, data, video |
| deliverable_contract | ext `[.docx, .wav]`, confidence **medium** |
| primary artifacts | `…_EDIT_REPORT.docx`, `…_FULL_EDIT_MIX.wav`, `…_STEM_BASS_EDITED.wav` |
| verification | **ok=True**, blocking_errors=[] |
| self-QA | score **7** (≥5), 1 reflect round |
| final_status | **ok** |
| runtime | ~269 s (4.5 min), 4 files, host mem 171 MB |

Note: the host verify env lacks `soundfile`/`ffprobe`, so deep WAV validation logs a
non-blocking "not validated" warning — expected, does not affect final_status.

## B — Video capstone (task a941b6d8, Information / Film & Video Editors)
VFX teleportation shot: composite an actor between two 4K clips and make them
vanish. Refs: `TWT_001_02.mp4` (~224 MB) + `TWT_A001_03.mp4` (~657 MB), both
3840×2160 h264.

| field | value |
|---|---|
| runner backend | **docker** |
| execution_mode | sandbox |
| preprocessor | `video_analyzer` (gpt-5.4 vision) **ran on host** via cv2: 8 frames/clip from both 4K clips → 2 vision calls (27.6 s / 25.0 s) → **8,814 chars** injected |
| selected_skills | video, data, document, image |
| deliverable_contract | ext `[.mp4, .png]`, confidence **medium** |
| primary artifacts | `teleportation_composite.mp4`, `teleportation_composite_raw.mp4`, `teleportation_preview.png`, `teleportation_storyboard.png` |
| in-container work | parsed base (204 f, 8.5 s) + overlay (638 f, 26.6 s) 4K h264, composited, wrote .mp4 + preview/storyboard |
| verification | **ok=True**, blocking_errors=[] |
| self-QA | score **6** (≥5), 1 reflect round |
| final_status | **ok** |
| runtime | ~1211 s (20.2 min), 5 files |

### Resource stability (validates F2 hardening)
Live `docker stats` during 4K compositing peaked at **~3.12 GiB / 7.65 GiB**
(memory_gb=8), CPU ~190–204% (multi-core). Comfortable headroom — no OOM /
exit-137 (the earlier 5 GB config was marginal on this task). Completed well
inside the 1200 s timeout.

## Pass/fail matrix
| task | backend | preproc ran? | perception injected | artifacts | verify | final_status |
|---|---|---|---|---|---|---|
| audio 4b894ae3 | docker | yes (audio) | 799 chars | docx + 2 wav | ok | **ok** |
| video a941b6d8 | docker | yes (video, 4K) | 8,814 chars | mp4 + raw + 2 png | ok | **ok** |

Both are genuine harness successes (backend=docker, contract inferred, perception
engaged, artifacts produced + verified). No harness failures. Deliverable
*artistic* quality is model-dependent and out of scope for this runtime proof.

## Merge-readiness verdict
From the runtime perspective PR #57 is **safe to merge**:
- Reset/clean Docker env rebuilds + runs the sandbox path.
- Real audio and 4K-video tasks complete end-to-end in Docker with perception.
- The one real bug surfaced (containerd image detection) is fixed + regression-tested.
- Manifests are schema_version 1.0, relative-path, leak-clean; verification passes.

## Residual risks / notes
- Host perception deps: audio needs none; video needs host `cv2` (or `av`). If a
  full hybrid run is launched on a host without them, `video_analyzer` no-ops —
  the preflight warning (added earlier) makes this explicit; document/ensure host
  deps before a large hybrid run.
- Deep audio validation needs `soundfile`/`ffprobe` in the *host* verify env;
  absence is a non-blocking warning only.
- Video tasks are heavy (~20 min/task here). A full 220 run mixing 4K video will
  be time-dominated by such tasks; schedule accordingly. Not a correctness risk.

## Constraints honored
No full 220 run · no Actions dispatch · no merge · PR title/body untouched ·
subprocess/code_interpreter/json_renderer unchanged · only report + the
sandbox_runner fix + its tests are committed (no binaries/caches/local data).
