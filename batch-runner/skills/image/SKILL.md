---
name: image
title: Image Perception
description: >-
  Vision for still images. Use for any task with image reference files
  (.png/.jpg/.jpeg/.webp/.bmp/.tiff/.gif) or that asks to read text from an
  image (OCR), analyze colours, detect QR/barcodes, or transform pictures.
  Provides metadata, OCR, dominant-colour extraction, QR/barcode reading, and
  resize/grayscale/thumbnail helpers.
modalities: [image]
file_extensions: [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"]
keywords:
  [image, picture, photo, png, jpg, jpeg, logo, screenshot, scan, ocr, text in
   image, colour, color, palette, qr, barcode, thumbnail, resize, crop, chart
   image, diagram]
requires: [Pillow, opencv-python, pytesseract, pyzbar, numpy]
version: 1.0.0
---

# Image Skill — read & transform pictures

Use this skill to *see* still images: read embedded text, measure colours,
decode QR/barcodes, and produce transformed image deliverables.

A typical "image problem" workflow:

1. `info = image.image_info(path)` — size, mode, format.
2. `text = image.ocr_text(path)` — pull any text in the picture.
3. `colors = image.dominant_colors(path)` — brand/palette analysis.
4. Transform / annotate and save the deliverable.

## Toolkit API

```python
from skills import image

image.image_info(path) -> dict          # {width, height, mode, format, size_kb}
image.ocr_text(path, lang="eng") -> str # pytesseract OCR
image.dominant_colors(path, k=5) -> list[tuple[int,int,int]]
image.read_codes(path) -> list[dict]    # QR / barcode payloads via pyzbar
image.to_grayscale(path, out) -> str
image.resize(path, width, out) -> str   # keep aspect ratio
image.thumbnail(path, max_px=256, out=None) -> str
```

Notes:
- OCR needs the system `tesseract` binary (present in the sandbox image).
- `dominant_colors` uses k-means over down-sampled pixels (OpenCV).
