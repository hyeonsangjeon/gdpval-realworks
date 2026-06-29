"""Tiny file-hash cache for expensive sandbox-derived data.

Render PNGs, perception/OCR summaries, and optional vision-QA verdicts are
expensive to recompute. This is a *minimal* content-addressed cache — not a
service — keyed by ``sha256(input bytes) + operation + config fingerprint``.

Design goals:
* **Disabled-safe** — when ``enabled`` is False every method is a cheap no-op, so
  callers never branch on cache availability.
* **Never committed** — the default cache directory lives outside the repo
  (``$SANDBOX_CACHE_DIR`` or a per-user temp dir), and callers may point it at the
  run's output directory. Nothing is written under the source tree.
* **Best-effort** — any I/O error degrades to a miss; the cache never raises.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Optional


def _fingerprint(config: Optional[dict]) -> str:
    if not config:
        return "default"
    try:
        blob = json.dumps(config, sort_keys=True, default=str)
    except Exception:
        blob = str(config)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


class FileCache:
    """Content-addressed blob cache. All operations are best-effort."""

    def __init__(self, enabled: bool = False, cache_dir=None, namespace: str = "sandbox"):
        self.enabled = bool(enabled)
        self.namespace = namespace
        self._dir: Optional[Path] = None
        if self.enabled:
            base = (
                cache_dir
                or os.getenv("SANDBOX_CACHE_DIR")
                or os.path.join(tempfile.gettempdir(), "gdpval_sandbox_cache")
            )
            try:
                self._dir = Path(base) / namespace
                self._dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                self.enabled = False
                self._dir = None

    # ── key construction ─────────────────────────────────────────────────
    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def hash_file(path) -> str:
        h = hashlib.sha256()
        with Path(path).open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def key(self, content_hash: str, operation: str, config: Optional[dict] = None) -> str:
        return f"{operation}-{content_hash[:32]}-{_fingerprint(config)}"

    def _path(self, key: str, suffix: str) -> Optional[Path]:
        if not self.enabled or self._dir is None:
            return None
        safe = "".join(c for c in key if c.isalnum() or c in "-_.")
        return self._dir / f"{safe}{suffix}"

    # ── blob get/put ─────────────────────────────────────────────────────
    def get_bytes(self, key: str, suffix: str = ".bin") -> Optional[bytes]:
        p = self._path(key, suffix)
        if p is None or not p.exists():
            return None
        try:
            return p.read_bytes()
        except Exception:
            return None

    def put_bytes(self, key: str, data: bytes, suffix: str = ".bin") -> Optional[Path]:
        p = self._path(key, suffix)
        if p is None:
            return None
        try:
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(p)
            return p
        except Exception:
            return None

    # ── json get/put ─────────────────────────────────────────────────────
    def get_json(self, key: str):
        raw = self.get_bytes(key, suffix=".json")
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def put_json(self, key: str, obj) -> Optional[Path]:
        try:
            data = json.dumps(obj, default=str).encode("utf-8")
        except Exception:
            return None
        return self.put_bytes(key, data, suffix=".json")


def build_cache(config: Optional[dict], output_dir=None) -> FileCache:
    """Construct a :class:`FileCache` from an ``execution.sandbox.cache`` block."""
    config = config or {}
    enabled = bool(config.get("enabled", False))
    cache_dir = config.get("dir")
    if cache_dir is None and output_dir is not None and enabled:
        cache_dir = os.path.join(str(output_dir), ".sandbox_cache")
    return FileCache(enabled=enabled, cache_dir=cache_dir)
