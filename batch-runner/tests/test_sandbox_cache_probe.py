"""Tests for core/sandbox_cache.py and the dependency import probe (Part F/G)."""

from pathlib import Path

from core.sandbox_cache import FileCache, build_cache
from core.dependency_resolver import ImportProbe, probe_imports


# ── cache ─────────────────────────────────────────────────────────────────

def test_disabled_cache_is_noop():
    c = FileCache(enabled=False)
    k = c.key("abc", "render")
    assert c.get_bytes(k) is None
    assert c.put_bytes(k, b"data") is None
    assert c.get_json(k) is None


def test_enabled_cache_roundtrip_bytes(tmp_path):
    c = FileCache(enabled=True, cache_dir=str(tmp_path))
    k = c.key(c.hash_bytes(b"input"), "render", {"dpi": 120})
    assert c.get_bytes(k) is None
    c.put_bytes(k, b"png-bytes", suffix=".png")
    assert c.get_bytes(k, suffix=".png") == b"png-bytes"


def test_enabled_cache_roundtrip_json(tmp_path):
    c = FileCache(enabled=True, cache_dir=str(tmp_path))
    k = c.key("hash", "vision_qa")
    c.put_json(k, {"visual_ok": True})
    assert c.get_json(k) == {"visual_ok": True}


def test_cache_key_varies_with_config(tmp_path):
    c = FileCache(enabled=True, cache_dir=str(tmp_path))
    k1 = c.key("h", "render", {"dpi": 100})
    k2 = c.key("h", "render", {"dpi": 200})
    assert k1 != k2


def test_build_cache_disabled_default():
    c = build_cache({})
    assert c.enabled is False


def test_build_cache_under_output_dir(tmp_path):
    c = build_cache({"enabled": True}, output_dir=str(tmp_path))
    assert c.enabled is True
    assert str(tmp_path) in str(c._dir)


# ── import probe ────────────────────────────────────────────────────────────

def test_probe_disabled_marks_not_checked():
    p = probe_imports(["numpy", "pandas"], enabled=False)
    assert p.available == [] and p.missing == []
    assert set(p.not_checked) == {"numpy", "pandas"}


def test_probe_detects_available_and_missing():
    def fake_finder(mod):
        return object() if mod in {"numpy", "os"} else None
    p = probe_imports(["numpy", "definitely-not-real-pkg"], finder=fake_finder)
    assert "numpy" in p.available
    assert "definitely-not-real-pkg" in p.missing


def test_probe_maps_pip_to_import_name():
    seen = {}

    def fake_finder(mod):
        seen[mod] = True
        return object()
    probe_imports(["opencv-python", "Pillow", "scikit-learn"], finder=fake_finder)
    # pip names map to import names via the reverse table.
    assert "cv2" in seen
    assert "PIL" in seen
    assert "sklearn" in seen


def test_probe_handles_finder_exception_as_not_checked():
    def boom(mod):
        raise ValueError("weird")
    p = probe_imports(["somepkg"], finder=boom)
    assert p.not_checked == ["somepkg"]


def test_import_probe_to_dict():
    p = ImportProbe(available=["numpy"], missing=["foo"], env="host")
    d = p.to_dict()
    assert d["available"] == ["numpy"]
    assert d["env"] == "host"
