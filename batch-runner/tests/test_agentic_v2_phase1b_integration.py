from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

import pytest

from sandbox.v2.verify_candidate import verify_candidate


@pytest.mark.integration
def test_agentic_v2_phase1b_local_candidate_evidence(tmp_path):
    if os.environ.get("AGENTIC_V2_PHASE1B_PREFLIGHT") != "1":
        pytest.skip("Agentic V2 Phase 1B local preflight not requested")
    image = os.environ["AGENTIC_V2_PHASE1B_IMAGE"]
    source_revision = os.environ["AGENTIC_V2_PHASE1B_SOURCE_REVISION"]
    oci_layout = Path(os.environ["AGENTIC_V2_PHASE1B_OCI_LAYOUT"])

    gate = verify_candidate(
        image=image,
        source_revision=source_revision,
        oci_layout=oci_layout,
        output_directory=tmp_path / "evidence",
        session_id=uuid.uuid4().hex,
    )

    assert gate["gate_status"] == "blocked"
    assert gate["evidence"]["oci_layout"]["status"] == "verified"
    assert gate["evidence"]["cve"]["status"] == "not_run"
    assert gate["evidence"]["microvm"]["status"] == "not_run"
    assert gate["evidence"]["provenance"]["status"] == "not_run"
    assert gate["evidence"]["signature"]["status"] == "not_run"

    containment = json.loads(
        (tmp_path / "evidence" / "containment-report.json").read_text(
            encoding="utf-8"
        )
    )
    if containment["collection_status"] == "verified":
        assert gate["evidence"]["capability_receipt"]["status"] == "verified"
        assert gate["evidence"]["sbom"]["status"] == "verified"
        receipt = json.loads(
            (tmp_path / "evidence" / "candidate-receipt.json").read_text(
                encoding="utf-8"
            )
        )
        assert receipt["foundation_only"] is True
        assert receipt["production_activation"] == "disabled"
        assert receipt["subject"]["source_revision"] == source_revision
    else:
        assert containment["status"] == "failed"
        assert gate["evidence"]["capability_receipt"]["status"] == "not_run"
        assert gate["evidence"]["sbom"]["status"] == "not_run"
        assert not (tmp_path / "evidence" / "candidate-receipt.json").exists()