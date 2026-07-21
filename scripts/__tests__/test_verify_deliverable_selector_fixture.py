"""Tests for the hermetic deliverable-selector fixture contract."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from scripts import verify_deliverable_selector_fixture as verifier


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "batch-runner"
    / "tests"
    / "fixtures"
    / "deliverable_selector_contract_v1.json"
)


def _document():
    return verifier.load_and_validate_fixture(FIXTURE)


def _reseal(document):
    document["sha256"] = verifier.fixture_sha256(document)
    return document


def test_checked_in_fixture_is_valid_and_minimal():
    document = _document()

    assert document["schema_version"] == verifier.SCHEMA_VERSION
    assert len(document["tasks"]) == 28
    assert len(verifier.canonical_json(document)) < 8 * 1024
    assert document["source"]["source_content_included"] is False


def test_fixture_rejects_hash_and_identity_drift():
    document = _document()
    document["tasks"]["0419f1c3"]["instruction"] = "drift"
    with pytest.raises(verifier.FixtureValidationError, match="hash_mismatch"):
        verifier.validate_fixture(document)

    document = _document()
    document["tasks"]["1b1ade2d"]["task_id"] = document["tasks"][
        "0419f1c3"
    ]["task_id"]
    with pytest.raises(verifier.FixtureValidationError, match="task_identity"):
        verifier.validate_fixture(_reseal(document))


def test_fixture_rejects_source_and_signal_contract_drift():
    document = _document()
    document["source"]["source_content_included"] = True
    with pytest.raises(verifier.FixtureValidationError, match="source_identity"):
        verifier.validate_fixture(_reseal(document))

    document = _document()
    document["tasks"]["0419f1c3"]["instruction"] = "copied source prompt"
    with pytest.raises(verifier.FixtureValidationError, match="instruction_invalid"):
        verifier.validate_fixture(_reseal(document))

    document = _document()
    document["tasks"]["0419f1c3"]["rubric_items"] = [
        {"criterion": "x" * 513, "score": 1}
    ]
    with pytest.raises(verifier.FixtureValidationError, match="rubric_invalid"):
        verifier.validate_fixture(_reseal(document))


def test_selector_test_module_has_no_parquet_stack_dependency():
    selector_test = (
        Path(__file__).resolve().parents[2]
        / "batch-runner"
        / "tests"
        / "test_deliverable_selector.py"
    ).read_text(encoding="utf-8")

    assert "import pandas" not in selector_test
    assert "read_parquet" not in selector_test
    assert "gdpval-local" not in selector_test


def test_optional_source_verification_uses_delayed_reader(monkeypatch, tmp_path):
    document = _document()
    parquet = tmp_path / "source.parquet"
    parquet.write_bytes(b"fixture")
    source_hashes = {
        task["task_id"]: task["source_selector_input_sha256"]
        for task in document["tasks"].values()
    }

    class FakeFrame:
        def __len__(self):
            return 220

        def to_dict(self, orient):
            assert orient == "records"
            return [
                {"task_id": task_id, "prompt": task_id, "rubric_json": []}
                for task_id in source_hashes
            ]

    def read_parquet(path, columns):
        assert Path(path) == parquet
        assert columns == ["task_id", "prompt", "rubric_json"]
        return FakeFrame()

    fake_pandas = SimpleNamespace(read_parquet=read_parquet)
    monkeypatch.setattr(
        verifier,
        "_sha256_file",
        lambda path: document["source"]["parquet_sha256"],
    )
    monkeypatch.setattr(
        verifier,
        "_source_selector_input_sha256",
        lambda prompt, rubric: source_hashes[prompt],
    )
    monkeypatch.setitem(sys.modules, "pandas", fake_pandas)

    verifier.verify_source_snapshot(
        deepcopy(document),
        parquet,
        source_revision=document["source"]["revision"],
    )

    with pytest.raises(verifier.FixtureValidationError, match="revision_mismatch"):
        verifier.verify_source_snapshot(
            deepcopy(document),
            parquet,
            source_revision="0" * 40,
        )

    monkeypatch.setattr(
        verifier,
        "_source_selector_input_sha256",
        lambda prompt, rubric: "0" * 64,
    )
    with pytest.raises(verifier.FixtureValidationError, match="selector_input"):
        verifier.verify_source_snapshot(
            deepcopy(document),
            parquet,
            source_revision=document["source"]["revision"],
        )
