# GDPVal Sandbox Skills

Famous-library **Agent Skills** that give the sandbox *vision* and *hearing* so
LLM-generated `solution.py` can perceive multimodal reference files and build
deliverables instead of coding blind.

| Skill | Modality | Famous libraries | What it does |
|-------|----------|------------------|--------------|
| [`audio`](audio/SKILL.md) | 🔊 hearing | librosa, soundfile, scipy, pyloudnorm | FFT / spectral peaks, spectrogram, sampling, loudness (LUFS), tempo, synthesis |
| [`video`](video/SKILL.md) | 👁 vision | opencv-python, PyAV, moviepy, Pillow | frame-by-frame sampling, keyframes, scene-change detection, metadata, audio track extraction, contact-sheet montage |
| [`document`](document/SKILL.md) | 📄 docs | pdfplumber, PyMuPDF, python-docx, python-pptx, openpyxl | read/extract + render PDF/DOCX/PPTX/XLSX, tables, page→image |
| [`image`](image/SKILL.md) | 🖼 vision | Pillow, opencv-python, pytesseract, pyzbar | metadata, OCR, dominant colours, QR/barcode, resize/grayscale |
| [`data`](data/SKILL.md) | 📊 analysis | pandas, numpy, matplotlib, scikit-learn | load tables, describe, charts, correlation, linear regression |

## How the sandbox uses them

1. `core/skills_registry.py` parses every `SKILL.md`, then **selects** the skills
   relevant to a task by matching reference-file extensions and task keywords.
2. The selected skills' manuals are injected into the code-generation prompt, so
   the model knows the exact callable API.
3. The whole `skills/` package is copied into the sandbox working directory and
   added to `PYTHONPATH`, so generated code can `from skills import audio, video`.

## Skill format (Agent Skills)

Each `SKILL.md` starts with YAML front-matter:

```yaml
---
name: audio
title: Audio Perception & Synthesis
description: >-
  One-paragraph "what + when to use" used for skill selection.
modalities: [audio]
file_extensions: [".wav", ".mp3", ...]
keywords: [spectrogram, fft, loudness, ...]
requires: [librosa, soundfile, numpy, scipy]
version: 1.0.0
---
```

The body documents the toolkit. The `## Toolkit API` section is extracted
verbatim and injected into the prompt.

> All heavy imports are lazy. Importing `skills` never fails; calling a helper
> whose library is missing raises `SkillDependencyError` naming the pip package.
