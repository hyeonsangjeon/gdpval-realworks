from __future__ import annotations

from copy import deepcopy
import json

import pytest

from sandbox.v2.measure_hosted_containment import (
    build_hosted_result,
    render_markdown,
    validate_hosted_result,
)
from core.agentic_v2_supply_chain import canonical_sha256


def _parent_lock():
    return {
        "schema_version": "1.0",
        "reference": "ghcr.io/hyeonsangjeon/gdpval-sandbox@sha256:" + "b" * 64,
        "manifest_digest": "sha256:" + "b" * 64,
        "observed_local_image_id": "sha256:" + "a" * 64,
        "platform": "linux/amd64",
    }


def _containment(failed: str | None = None):
    names = {
        "cap_drop_all", "cpu_quota", "memory_limit", "network_none",
        "no_new_privileges", "non_root_uid", "pids_limit", "read_only_rootfs",
    }
    checks = {name: name != failed for name in names}
    collection_names = {
        "cap_drop_all", "memory_limit", "network_none",
        "no_new_privileges", "non_root_uid", "read_only_rootfs",
    }
    collection = {name: checks[name] for name in collection_names}
    report = {
        "schema_version": "1.1",
        "status": "verified" if all(checks.values()) else "failed",
        "checks": checks,
        "required": sorted(checks),
        "collection_status": "verified" if all(collection.values()) else "failed",
        "collection_checks": collection,
        "host_scope": "exact-docker-daemon",
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def _runner():
    return {
        "environment": "github-hosted",
        "os": "Linux",
        "architecture": "X64",
        "kernel_release": "6.11.0-test",
        "cgroup": "v2",
        "github_run_id": "123",
        "github_run_attempt": "1",
    }


def _measurement(failed: str | None = None):
    lock = _parent_lock()
    return {
        "image_id": lock["observed_local_image_id"],
        "platform": lock["platform"],
        "repo_digests": [lock["reference"]],
        "containment": _containment(failed),
    }


def test_hosted_result_records_all_verified_checks_but_keeps_gate_blocked():
    result = build_hosted_result(
        source_revision="c" * 40,
        parent_lock=_parent_lock(),
        measurement=_measurement(),
        runner=_runner(),
    )

    assert result["containment"]["status"] == "verified"
    assert {
        item["status"] for item in result["containment"]["checks"].values()
    } == {"verified"}
    assert result["aggregate_gate"]["status"] == "blocked"
    assert result["aggregate_gate"]["can_leave_blocked"] is False
    assert result["aggregate_gate"]["containment_is_blocking"] is False
    assert len(result["aggregate_gate"]["unmeasured_required_evidence"]) == 8
    assert validate_hosted_result(result) == result


def test_hosted_result_surfaces_failed_containment_check():
    result = build_hosted_result(
        source_revision="c" * 40,
        parent_lock=_parent_lock(),
        measurement=_measurement("cpu_quota"),
        runner=_runner(),
    )

    assert result["containment"]["status"] == "failed"
    assert result["containment"]["checks"]["cpu_quota"]["status"] == "failed"
    assert result["aggregate_gate"]["containment_is_blocking"] is True


def test_hosted_result_rejects_image_outside_parent_lock():
    measurement = _measurement()
    measurement["image_id"] = "sha256:" + "d" * 64

    with pytest.raises(ValueError, match="differs from parent lock"):
        build_hosted_result(
            source_revision="c" * 40,
            parent_lock=_parent_lock(),
            measurement=measurement,
            runner=_runner(),
        )


def test_hosted_result_hash_and_markdown_are_bound():
    result = build_hosted_result(
        source_revision="c" * 40,
        parent_lock=_parent_lock(),
        measurement=_measurement(),
        runner=_runner(),
    )
    markdown = render_markdown(result)
    round_tripped = json.loads(json.dumps(result, sort_keys=True))

    assert markdown.count("| `verified` |") == 8
    assert "- Status: `blocked`" in markdown
    assert "- Can leave blocked: `false`" in markdown
    assert render_markdown(round_tripped) == markdown

    forged = deepcopy(result)
    forged["runner"]["kernel_release"] = "changed"
    with pytest.raises(ValueError, match="identity"):
        validate_hosted_result(forged)

    forged = deepcopy(result)
    forged["parent_image"]["platform"] = "linux/arm64"
    forged_without_hash = dict(forged)
    forged_without_hash.pop("result_sha256")
    forged["result_sha256"] = canonical_sha256(forged_without_hash)
    with pytest.raises(ValueError, match="identity"):
        validate_hosted_result(forged)