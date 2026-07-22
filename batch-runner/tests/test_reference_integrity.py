from pathlib import Path

import pytest

from core import reference_integrity as integrity


def test_staged_reference_isolated_from_source_mutation(tmp_path):
    source = tmp_path / "source" / "input.xlsx"
    source.parent.mkdir()
    source.write_bytes(b"approved")
    verified = integrity.verify_reference_path(source)

    with integrity.stage_verified_references([verified]) as staged:
        assert Path(staged[0]).stat().st_mode & 0o777 == 0o400
        source.write_bytes(b"mutated")
        source.write_bytes(b"approved")
        assert Path(staged[0]).read_bytes() == b"approved"


def test_duplicate_reference_basename_rejected_before_staging(tmp_path):
    first = tmp_path / "first" / "input.xlsx"
    second = tmp_path / "second" / "input.xlsx"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    with pytest.raises(integrity.ReferenceIntegrityError, match="basenames collide"):
        with integrity.stage_verified_references([first, second]):
            pytest.fail("duplicate basenames must not yield staged paths")


def test_partial_staging_failure_removes_private_directory(tmp_path, monkeypatch):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    original_copy = integrity.shutil.copyfileobj
    calls = 0

    def fail_second_copy(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("copy failed")
        return original_copy(*args, **kwargs)

    monkeypatch.setattr(integrity.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(integrity.shutil, "copyfileobj", fail_second_copy)

    with pytest.raises(integrity.ReferenceIntegrityError, match="copy failed"):
        with integrity.stage_verified_references([first, second]):
            pytest.fail("partial staging must not yield")

    assert not list(tmp_path.glob("gdpval-reference-*"))