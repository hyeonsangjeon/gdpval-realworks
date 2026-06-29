"""Image skill toolkit — metadata / OCR / colours / QR-barcode / transforms.

Heavy libraries (PIL, cv2, pytesseract, pyzbar) are imported lazily so importing
this module never fails.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

from skills import _require

__all__ = [
    "image_info",
    "ocr_text",
    "dominant_colors",
    "read_codes",
    "to_grayscale",
    "resize",
    "thumbnail",
]


def image_info(path: str) -> dict:
    Image = _require("PIL.Image", "Pillow")
    with Image.open(str(path)) as im:
        return {
            "width": im.width,
            "height": im.height,
            "mode": im.mode,
            "format": im.format,
            "size_kb": round(os.path.getsize(path) / 1024, 1),
        }


def ocr_text(path: str, lang: str = "eng") -> str:
    pytesseract = _require("pytesseract", "pytesseract")
    Image = _require("PIL.Image", "Pillow")
    with Image.open(str(path)) as im:
        return pytesseract.image_to_string(im, lang=lang)


def dominant_colors(path: str, k: int = 5) -> List[Tuple[int, int, int]]:
    cv2 = _require("cv2", "opencv-python")
    np = _require("numpy", "numpy")
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"could not read image: {path}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    small = cv2.resize(img, (100, 100), interpolation=cv2.INTER_AREA)
    pixels = small.reshape(-1, 3).astype("float32")
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    k = max(1, min(k, len(pixels)))
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3,
                                    cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(counts)[::-1]
    return [tuple(int(v) for v in centers[i]) for i in order]


def read_codes(path: str) -> List[dict]:
    """Decode QR codes / barcodes via pyzbar."""
    pyzbar = _require("pyzbar.pyzbar", "pyzbar")
    Image = _require("PIL.Image", "Pillow")
    with Image.open(str(path)) as im:
        results = pyzbar.decode(im)
    return [
        {
            "type": r.type,
            "data": r.data.decode("utf-8", errors="replace"),
            "rect": tuple(r.rect),
        }
        for r in results
    ]


def to_grayscale(path: str, out: str) -> str:
    Image = _require("PIL.Image", "Pillow")
    with Image.open(str(path)) as im:
        im.convert("L").save(out)
    return out


def resize(path: str, width: int, out: str) -> str:
    Image = _require("PIL.Image", "Pillow")
    with Image.open(str(path)) as im:
        ratio = width / im.width
        im.resize((width, max(1, int(im.height * ratio)))).save(out)
    return out


def thumbnail(path: str, max_px: int = 256, out: Optional[str] = None) -> str:
    Image = _require("PIL.Image", "Pillow")
    out = out or f"thumb_{Path(path).stem}.png"
    with Image.open(str(path)) as im:
        im.thumbnail((max_px, max_px))
        im.save(out)
    return out
