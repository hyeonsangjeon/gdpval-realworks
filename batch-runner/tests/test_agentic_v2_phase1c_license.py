from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import py_compile
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

import core.agentic_v2_license as license_module
import core.agentic_v2_substrate as substrate_module
from core.agentic_v2_license import (
    build_license_report,
    validate_license_evidence,
    validate_license_exceptions,
    validate_license_report,
)
from core.agentic_v2_substrate import canonical_sha256
from core.agentic_v2_supply_chain import (
    CandidateSubject,
    SupplyChainPolicy,
    build_evidence_report,
    evidence_item,
)
import sandbox.v2.build_candidate as builder
import sandbox.v2.effective_sbom as sbom_collector
import sandbox.v2.image_probe as image_probe
import sandbox.v2.license_evidence as collector
import sandbox.v2.verify_candidate as verifier


CASES = Path("tests/fixtures/agentic_v2_phase1c_license_cases.json")
SCHEMA = Path("schemas/agentic-v2-license-report.schema.json")


def _subject():
    return {
        "schema_version": "1.0",
        "substrate_id": "professional-work-v1",
        "image_id": "sha256:" + "1" * 64,
        "oci_manifest_digest": "sha256:" + "2" * 64,
        "parent_manifest_digest": "sha256:" + "3" * 64,
        "platform": "linux/amd64",
        "source_revision": "4" * 40,
        "dockerfile_sha256": "5" * 64,
        "manifest_sha256": "6" * 64,
        "probe_sha256": "7" * 64,
        "embedded_source_sha256": "8" * 64,
        "verifier_sha256": "9" * 64,
        "oci_exporter_sha256": "a" * 64,
        "sbom_generator_sha256": "b" * 64,
        "license_collector_sha256": "c" * 64,
        "license_evaluator_sha256": "d" * 64,
        "license_evaluator_packaging_version": "26.2",
        "license_evaluator_parser_sha256": (
            "fc9c745d1883ff9f296a5b169f22eb2ee879f59a4608f20f5cb29d668f4e26f4"
        ),
        "license_evaluator_python_version": "3.10.12",
        "license_evaluator_callable_sha256": (
            "e27e24ff0053d4f68aca4d2ec770d83b8cd8536629c01406c7f5578f6972a78b"
        ),
        "license_evaluator_runtime_graph_sha256": (
            "8fff34b3a069995de020a123594de0254935b12ab154b272057807c8de7be459"
        ),
        "license_evaluator_spdx_version": "3.27.0",
        "license_evaluator_spdx_sha256": (
            "ecc082fdc1fcdcae47b2f56c4ce2cdc2c9d6d54ca555a09814abd78dece7a230"
        ),
        "lock_set_sha256": "e" * 64,
    }


def _policy():
    return {
        "schema_version": "1.0",
        "policy_id": "agentic-v2-phase1c-candidate-v1",
        "foundation_only": True,
        "production_activation": "disabled",
        "required_evidence": [
            "capability_receipt",
            "containment",
            "cve",
            "license",
            "microvm",
            "oci_layout",
            "provenance",
            "sbom",
            "signature",
        ],
        "cve": {
            "policy_id": "agentic-v2-cve-v1",
            "scanner_db_max_age_days": 7,
            "denied_severities": ["CRITICAL", "HIGH"],
            "exceptions_require": [
                "cve", "purl", "reason", "approver", "expires_at",
            ],
        },
        "license": {
            "policy_id": "agentic-v2-license-v2",
            "as_of_date": "2026-07-31",
            "unknown_is_failure": True,
            "unknown_classifications": [
                "ambiguous", "missing_metadata", "unverifiable",
            ],
            "denied_identifiers": ["BUSL-1.1", "Commons-Clause", "SSPL-1.0"],
            "exceptions_require": [
                "ecosystem", "package", "version", "purl",
                "normalized_expression", "evidence_sha256", "reason",
                "approver", "expires_at",
            ],
            "exceptions": [],
        },
        "signature": {
            "profile": "cosign-offline-v1",
            "trusted_key_required": True,
            "bundle_required": True,
        },
        "provenance": {
            "profile": "buildkit-max-v1",
            "required_subjects": [
                "candidate", "parent", "dockerfile", "locks", "manifest",
                "probe", "sbom", "policy",
            ],
        },
        "microvm": {
            "runtime": "firecracker",
            "jailer_required": True,
            "kvm_required": True,
            "network": "none",
            "read_only_rootfs": True,
            "ephemeral_work_disk": True,
        },
    }


def _evidence(source: str, path: str | None, index: int):
    return {
        "source": source,
        "path": path,
        "resolved_path": path,
        "sha256": f"{index + 1:064x}",
        "size": index + 1,
    }


def _case_record(case, index):
    package = case["id"]
    version = "1.0.0"
    ecosystem = case["ecosystem"]
    if ecosystem == "debian":
        purl = f"pkg:deb/debian/{package}@{version}?arch=amd64"
        evidence = [
            _evidence("debian-status", "/var/lib/dpkg/status", 900),
            _evidence(
                "debian-copyright", f"/usr/share/doc/{package}/copyright", index
            ),
        ]
    elif ecosystem == "python":
        purl = f"pkg:pypi/{package}@{version}"
        evidence = [_evidence(
            "python-metadata",
            f"/usr/local/lib/python3.11/site-packages/{package}-{version}.dist-info/METADATA",
            index,
        )]
    elif ecosystem == "r":
        purl = f"pkg:cran/{package}@{version}"
        runtime_bytes = json.dumps(
            {"license": "", "version": "4.2.2"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        evidence = [
            _evidence(
                "r-description", f"/usr/lib/R/library/{package}/DESCRIPTION", index
            ),
            _evidence(
                "r-runtime-description",
                "/usr/lib/R/library/base/DESCRIPTION",
                index + 100,
            ),
            {
                "source": "r-runtime-license",
                "path": None,
                "resolved_path": None,
                "sha256": hashlib.sha256(runtime_bytes).hexdigest(),
                "size": len(runtime_bytes),
            },
            _evidence(
                "r-runtime-copyright",
                "/usr/share/doc/r-base-core/copyright",
                index + 200,
            ),
        ]
    else:
        purl = f"pkg:npm/{package}@{version}"
        evidence = [_evidence(
            "npm-package-json", "/usr/share/nodejs/npm/package.json", index
        )]
    metadata = deepcopy(case["metadata"])
    if ecosystem == "debian":
        metadata["copyright_format"] = collector.DEP5_FORMAT_URI
    if ecosystem in {"python", "r", "npm"}:
        metadata["license_file_tokens"] = []
    if ecosystem == "r":
        metadata["runtime_copyright_format"] = collector.DEP5_FORMAT_URI
    if ecosystem == "python":
        metadata["license_files"] = []
    return {
        "ecosystem": ecosystem,
        "package": package,
        "version": version,
        "purl": purl,
        "raw_values": case["raw_values"],
        "metadata": metadata,
        "evidence": evidence,
    }


def _fixture():
    fixture = json.loads(CASES.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == "1.0"
    records = [
        _case_record(case, index)
        for index, case in enumerate(fixture["cases"])
    ]
    records.sort(key=lambda item: item["purl"])
    evidence = {
        "schema_version": "1.0",
        "collector": "gdpval-agentic-v2-license-evidence-v1",
        "records": records,
        "records_sha256": canonical_sha256(records),
    }
    sbom = {
        "packages": [{
            "name": record["package"],
            "versionInfo": record["version"],
            "externalRefs": [{"referenceLocator": record["purl"]}],
        } for record in records],
    }
    policy = _policy()
    exception_record = next(
        record for record in records if record["package"] == "python-exception"
    )
    policy["license"]["exceptions"] = [{
        "ecosystem": "python",
        "package": exception_record["package"],
        "version": exception_record["version"],
        "purl": exception_record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": canonical_sha256(exception_record["evidence"]),
        "reason": "fixture-review",
        "approver": "fixture-approver",
        "expires_at": "2027-07-31",
    }]
    subject = _subject()
    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    return fixture, subject, sbom, evidence, policy, report


def test_phase1c_fixture_has_exact_classifications_and_expressions():
    fixture, _subject_value, _sbom, _evidence_value, _policy_value, report = _fixture()
    decisions = {item["package"]: item for item in report["decisions"]}

    for case in fixture["cases"]:
        decision = decisions[case["id"]]
        assert decision["classification"] == case["expected_classification"]
        assert decision["normalized_expression"] == case["expected_expression"]
        assert decision["evidence"]
        assert decision["evidence_sha256"] == canonical_sha256(decision["evidence"])

    assert report["counts"] == {
        "ambiguous": 1,
        "denied": 1,
        "exception": 1,
        "missing_metadata": 1,
        "resolved": 4,
        "unverifiable": 1,
    }
    assert report["unresolved_count"] == 3
    assert report["status"] == "failed"


def test_phase1c_report_is_canonical_deterministic_and_schema_valid():
    _fixture_value, subject, sbom, evidence, policy, report = _fixture()
    repeated = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=deepcopy(sbom),
        license_evidence=deepcopy(evidence),
        policy=deepcopy(policy),
        policy_sha256=canonical_sha256(policy),
    )

    assert repeated == report
    assert json.dumps(report, sort_keys=True, separators=(",", ":")) == json.dumps(
        repeated, sort_keys=True, separators=(",", ":")
    )
    unsigned = deepcopy(report)
    claimed = unsigned.pop("report_sha256")
    assert claimed == canonical_sha256(unsigned)
    assert report["decisions_sha256"] == canonical_sha256(report["decisions"])

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    mismatched = deepcopy(report)
    mismatched["decisions"][0]["ecosystem"] = "npm"
    assert list(Draft202012Validator(schema).iter_errors(mismatched))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("foundation_only",), 1),
        (("package_count",), 9.0),
        (("counts", "resolved"), True),
        (("decisions", 0, "evidence", 0, "size"), 1.0),
    ],
)
def test_phase1c_persisted_report_rejects_type_coercion(path, value):
    _fixture_value, subject, sbom, evidence, policy, report = _fixture()
    tampered = deepcopy(report)
    target = tampered
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    unsigned = deepcopy(tampered)
    unsigned.pop("report_sha256")
    tampered["report_sha256"] = canonical_sha256(unsigned)

    with pytest.raises(ValueError, match="license report identity"):
        validate_license_report(
            tampered,
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom=sbom,
            license_evidence=evidence,
            policy=policy,
            policy_sha256=canonical_sha256(policy),
        )


def test_phase1c_empty_inventory_cannot_build_verified_report():
    subject = _subject()
    policy = _policy()
    evidence = {
        "schema_version": "1.0",
        "collector": "gdpval-agentic-v2-license-evidence-v1",
        "records": [],
        "records_sha256": canonical_sha256([]),
    }

    with pytest.raises(ValueError, match="(evidence identity|inventory is empty)"):
        build_license_report(
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom={"packages": []},
            license_evidence=evidence,
            policy=policy,
            policy_sha256=canonical_sha256(policy),
        )


def test_phase1c_evaluator_runtime_drift_is_rejected(monkeypatch):
    monkeypatch.setattr(license_module.packaging, "__version__", "26.3")

    with pytest.raises(RuntimeError, match="runtime identity differs"):
        license_module.license_evaluator_runtime_identity()


def test_phase1c_evaluator_parser_source_drift_is_rejected(tmp_path, monkeypatch):
    tampered = tmp_path / "__init__.py"
    tampered.write_text("def canonicalize_license_expression(value): return 'MIT'\n")
    monkeypatch.setattr(license_module.packaging_licenses, "__file__", str(tampered))

    with pytest.raises(RuntimeError, match="parser identity differs"):
        license_module.license_evaluator_runtime_identity()


def test_phase1c_evaluator_callable_tamper_is_rejected(monkeypatch):
    original = license_module.packaging_licenses.canonicalize_license_expression

    def forged(value):
        return original(value)

    forged.__module__ = "packaging.licenses"
    monkeypatch.setattr(
        license_module.packaging_licenses,
        "canonicalize_license_expression",
        forged,
    )

    with pytest.raises(RuntimeError, match="parser identity differs"):
        license_module.license_evaluator_runtime_identity()


def test_phase1c_staged_evaluator_runtime_is_source_only(tmp_path):
    identity = builder._stage_license_evaluator_runtime(tmp_path)

    assert identity["runtime_graph_sha256"] == (
        "8fff34b3a069995de020a123594de0254935b12ab154b272057807c8de7be459"
    )
    assert sorted(
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file()
    ) == list(builder._LICENSE_RUNTIME_PATHS)
    assert not list(tmp_path.rglob("*.pyc"))
    assert not list(tmp_path.rglob("__pycache__"))


def test_phase1c_verifier_command_uses_isolated_no_site_runtime(tmp_path):
    command = builder._verifier_command(
        runtime_root=tmp_path / "runtime",
        verifier=tmp_path / "verify.py",
        image_id="sha256:" + "a" * 64,
        source_revision="b" * 40,
        oci_layout=tmp_path / "oci",
        output_directory=tmp_path / "evidence",
        session_id="c" * 32,
    )

    assert command[:6] == [
        sys.executable,
        "-I",
        "-S",
        "-B",
        "-c",
        builder._VERIFIER_BOOTSTRAP,
    ]
    assert command[-2:] == ["--session-id", "c" * 32]


def test_phase1c_verifier_command_executes_source_only_runtime(tmp_path):
    runtime_root = tmp_path / "runtime"
    builder._stage_license_evaluator_runtime(runtime_root)
    verifier_path = tmp_path / "verify.py"
    verifier_path.write_text(
        "import sys\n"
        "from packaging.licenses import canonicalize_license_expression\n"
        "assert sys.flags.isolated == 1\n"
        "assert sys.flags.no_site == 1\n"
        "assert sys.dont_write_bytecode\n"
        "assert canonicalize_license_expression('mit') == 'MIT'\n"
        "print('isolated-evaluator-ok')\n",
        encoding="utf-8",
    )
    marker = tmp_path / "startup-ran"
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    (hostile / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(hostile)
    command = builder._verifier_command(
        runtime_root=runtime_root,
        verifier=verifier_path,
        image_id="sha256:" + "a" * 64,
        source_revision="b" * 40,
        oci_layout=tmp_path / "oci",
        output_directory=tmp_path / "evidence",
        session_id="c" * 32,
    )

    completed = subprocess.run(
        command,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert completed.stdout == b"isolated-evaluator-ok\n"
    assert not marker.exists()
    assert not list(runtime_root.rglob("*.pyc"))


def test_phase1c_verifier_timeout_budget_exceeds_internal_probe_budget():
    expected_overhead = (
        substrate_module.AGENTIC_V2_SHORT_DOCKER_COMMAND_LIMIT
        * substrate_module.AGENTIC_V2_SHORT_DOCKER_TIMEOUT_SECONDS
        + substrate_module.AGENTIC_V2_GIT_COMMAND_LIMIT
        * substrate_module.AGENTIC_V2_GIT_TIMEOUT_SECONDS
        + substrate_module.AGENTIC_V2_EVIDENCE_ROOT_COPY_LIMIT
        * substrate_module.AGENTIC_V2_EVIDENCE_ROOT_COPY_TIMEOUT_SECONDS
        + (
            substrate_module.AGENTIC_V2_VERIFICATION_SESSION_SWEEP_LIMIT + 1
        )
        * substrate_module.AGENTIC_V2_VERIFICATION_SESSION_INVENTORY_TIMEOUT_SECONDS
        + substrate_module.AGENTIC_V2_VERIFICATION_SESSION_MAX_CONTAINERS
        * substrate_module.AGENTIC_V2_VERIFICATION_SESSION_SWEEP_LIMIT
        * substrate_module.AGENTIC_V2_VERIFICATION_SESSION_REMOVE_TIMEOUT_SECONDS
        + substrate_module.AGENTIC_V2_HOST_VALIDATION_BUDGET_SECONDS
    )
    assert substrate_module.AGENTIC_V2_VERIFIER_OVERHEAD_SECONDS == expected_overhead
    assert builder.AGENTIC_V2_VERIFIER_TIMEOUT_SECONDS >= (
        builder.AGENTIC_V2_IMAGE_PROBE_COUNT
        * builder.AGENTIC_V2_IMAGE_PROBE_TIMEOUT_SECONDS
        + builder.AGENTIC_V2_VERIFIER_OVERHEAD_SECONDS
    )


def test_phase1c_verifier_timeout_always_cleans_session(monkeypatch, tmp_path):
    session_id = "c" * 32
    cleaned = []

    class TimedOutProcess:
        pid = 12345

        def communicate(self, *, timeout):
            raise subprocess.TimeoutExpired(["verifier"], timeout)

    def popen(command, **kwargs):
        assert kwargs["start_new_session"] is True
        return TimedOutProcess()

    monkeypatch.setattr(
        builder.subprocess,
        "Popen",
        popen,
    )
    monkeypatch.setattr(
        builder,
        "_terminate_verifier_process_group",
        lambda process: cleaned.append(("terminated", process.pid)),
    )
    monkeypatch.setattr(
        builder,
        "_cleanup_verification_session",
        lambda value: cleaned.append(("cleaned", value)),
    )

    with pytest.raises(subprocess.TimeoutExpired):
        builder._run_verifier(
            [sys.executable, "-c", "pass"],
            cwd=tmp_path,
            environment={},
            session_id=session_id,
        )

    assert cleaned == [
        ("terminated", 12345),
        ("cleaned", session_id),
    ]


def test_phase1c_session_cleanup_removes_all_and_confirms_absence(monkeypatch):
    session_id = "d" * 32
    first = ["a" * 64, "b" * 64]
    inventories = iter([first, [], [], []])
    removed = []
    monkeypatch.setattr(
        builder,
        "_verification_session_containers",
        lambda value: next(inventories),
    )
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        lambda command, **kwargs: (
            removed.append(command[-1])
            or SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        ),
    )

    builder._cleanup_verification_session(session_id)

    assert removed == first


def test_phase1c_session_cleanup_continues_after_removal_failure(monkeypatch):
    session_id = "e" * 32
    first = ["a" * 64, "b" * 64]
    inventories = iter([first, [], [], []])
    removed = []
    monkeypatch.setattr(
        builder,
        "_verification_session_containers",
        lambda value: next(inventories),
    )

    def run(command, **kwargs):
        removed.append(command[-1])
        return SimpleNamespace(
            returncode=1 if command[-1] == first[0] else 0,
            stdout=b"",
            stderr=b"failed" if command[-1] == first[0] else b"",
        )

    monkeypatch.setattr(builder.subprocess, "run", run)

    with pytest.raises(RuntimeError, match="cleanup is incomplete"):
        builder._cleanup_verification_session(session_id)

    assert removed == first


def test_phase1c_session_cleanup_retries_after_initial_inventory_failure(
    monkeypatch,
):
    session_id = "f" * 32
    identifier = "a" * 64
    inventories = iter([
        RuntimeError("initial inventory failed"),
        [identifier],
        [],
        [],
    ])
    removed = []

    def inventory(_value):
        result = next(inventories)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(builder, "_verification_session_containers", inventory)
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        lambda command, **kwargs: (
            removed.append(command[-1])
            or SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        ),
    )

    with pytest.raises(builder.VerificationLifecycleError) as error:
        builder._cleanup_verification_session(session_id)

    assert removed == [identifier]
    assert any("initial inventory failed" in str(item) for item in error.value.failures)


def test_phase1c_lifecycle_preserves_timeout_termination_and_cleanup_failures(
    monkeypatch,
    tmp_path,
):
    session_id = "1" * 32

    class TimedOutProcess:
        pid = 12345

        def communicate(self, *, timeout):
            raise subprocess.TimeoutExpired(["verifier"], timeout)

    monkeypatch.setattr(
        builder.subprocess,
        "Popen",
        lambda command, **kwargs: TimedOutProcess(),
    )
    monkeypatch.setattr(
        builder,
        "_terminate_verifier_process_group",
        lambda process: (_ for _ in ()).throw(RuntimeError("termination failed")),
    )
    monkeypatch.setattr(
        builder,
        "_cleanup_verification_session",
        lambda value: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
    )

    with pytest.raises(builder.VerificationLifecycleError) as error:
        builder._run_verifier(
            [sys.executable, "-c", "pass"],
            cwd=tmp_path,
            environment={},
            session_id=session_id,
        )

    assert [type(item) for item in error.value.failures] == [
        subprocess.TimeoutExpired,
        RuntimeError,
        RuntimeError,
    ]


def test_phase1c_popen_failure_still_cleans_session(monkeypatch, tmp_path):
    session_id = "2" * 32
    cleaned = []
    monkeypatch.setattr(
        builder.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("spawn failed")),
    )
    monkeypatch.setattr(
        builder,
        "_cleanup_verification_session",
        lambda value: cleaned.append(value),
    )

    with pytest.raises(OSError, match="spawn failed"):
        builder._run_verifier(
            [sys.executable, "-c", "pass"],
            cwd=tmp_path,
            environment={},
            session_id=session_id,
        )

    assert cleaned == [session_id]


def test_phase1c_process_group_attempts_kill_after_term_failure(monkeypatch):
    signals = []
    waits = []

    class Process:
        pid = 12345

        def poll(self):
            return None

        def wait(self, *, timeout):
            waits.append(timeout)
            if len(waits) == 1:
                raise subprocess.TimeoutExpired(["verifier"], timeout)
            return -9

    def killpg(_pid, signal_value):
        signals.append(signal_value)
        if signal_value == signal.SIGTERM:
            raise PermissionError("term failed")

    monkeypatch.setattr(builder.os, "killpg", killpg)

    with pytest.raises(builder.VerificationLifecycleError) as error:
        builder._terminate_verifier_process_group(Process())

    assert signals == [signal.SIGTERM, signal.SIGKILL]
    assert waits == [10, 10]
    assert isinstance(error.value.failures[0], PermissionError)


def test_phase1c_all_verifier_containers_are_session_labeled():
    for function in (
        verifier._run_image_json,
        verifier._docker_base_isolation_probe,
        verifier._docker_resource_limit_probe,
        verifier._verify_disabled_entrypoint,
        verifier._verify_embedded_files,
        verifier._verify_license_evidence_files,
    ):
        assert "session.label_arguments()" in inspect.getsource(function)


def test_phase1c_builder_entrypoint_ignores_hostile_startup_before_clean_guard(
    tmp_path,
):
    marker = tmp_path / "builder-startup-ran"
    hostile = tmp_path / "hostile-builder"
    hostile.mkdir()
    (hostile / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(hostile)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    git_marker = tmp_path / "fake-git-ran"
    docker_marker = tmp_path / "fake-docker-ran"
    for name, tool_marker in (("git", git_marker), ("docker", docker_marker)):
        path = fake_bin / name
        path.write_text(
            f"#!/bin/sh\ntouch {str(tool_marker)!r}\nexit 99\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
    environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(Path(builder.__file__)),
            "--help",
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )

    expected_help = (
        b"usage: build_candidate.py [-h] --output-root OUTPUT_ROOT\n\n"
        b"options:\n"
        b"  -h, --help            show this help message and exit\n"
        b"  --output-root OUTPUT_ROOT\n"
    )
    if completed.returncode == 0:
        assert completed.stdout == expected_help
        assert completed.stderr == b""
    else:
        assert completed.stdout == b""
        assert completed.stderr.endswith(
            b"RuntimeError: candidate builder requires a clean source tree\n"
        )
    assert not marker.exists()
    assert not git_marker.exists()
    assert not docker_marker.exists()


def test_phase1c_builder_launches_only_git_staged_sources(
    tmp_path, monkeypatch
):
    fake_repository = tmp_path / "repository"
    fake_batch_root = fake_repository / "batch-runner"
    (fake_batch_root / "packaging").mkdir(parents=True)
    (fake_batch_root / "packaging" / "__init__.py").write_text(
        "raise RuntimeError('shadow packaging executed')\n",
        encoding="utf-8",
    )
    (fake_batch_root / "core").mkdir()
    (fake_batch_root / "core" / "agentic_v2_license.py").write_text(
        "raise RuntimeError('dirty core executed')\n",
        encoding="utf-8",
    )
    pycache = fake_batch_root / "core" / "__pycache__"
    pycache.mkdir()
    (pycache / "agentic_v2_license.cpython-310.pyc").write_bytes(b"unchecked")
    runtime_source = tmp_path / "runtime-source"
    builder._stage_license_evaluator_runtime(runtime_source)
    source_revision = "a" * 40
    blobs = {
        path: f"exact:{path}\n".encode("ascii")
        for path in builder._BUILDER_SOURCE_PATHS
    }
    commands = []

    def bootstrap_git(_root, *arguments):
        if arguments == ("rev-parse", "HEAD"):
            return (source_revision + "\n").encode("ascii")
        if arguments[:2] == ("status", "--porcelain"):
            return b""
        raise AssertionError(arguments)

    def run(command, **kwargs):
        commands.append((command, kwargs))
        staged_root = Path(kwargs["env"][builder._STAGED_ROOT_ENV])
        staged_runtime = Path(kwargs["env"][builder._RUNTIME_ROOT_ENV])
        assert command[:4] == [sys.executable, "-I", "-S", "-B"]
        assert Path(command[4]) == (
            staged_root / "sandbox" / "v2" / "build_candidate.py"
        )
        for path, expected in blobs.items():
            assert (
                staged_root / path.removeprefix("batch-runner/")
            ).read_bytes() == expected
        assert not (staged_root / "packaging").exists()
        assert not list(staged_root.rglob("*.pyc"))
        assert builder._bootstrap_runtime_matches(staged_runtime)
        assert "PYTHONPATH" not in kwargs["env"]
        assert kwargs["env"]["PATH"] == builder._TRUSTED_PATH
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(builder, "BATCH_ROOT", fake_batch_root)
    monkeypatch.setattr(builder, "_bootstrap_git", bootstrap_git)
    monkeypatch.setattr(
        builder,
        "_bootstrap_git_blob",
        lambda _root, _revision, path: blobs[path],
    )
    monkeypatch.setattr(builder, "_bootstrap_runtime_root", lambda: runtime_source)
    monkeypatch.setattr(builder.subprocess, "run", run)
    monkeypatch.setattr(
        builder.sys,
        "argv",
        ["build_candidate.py", "--output-root", str(tmp_path / "output")],
    )
    for name in builder._BOOTSTRAP_FORBIDDEN_ENV:
        monkeypatch.delenv(name, raising=False)

    assert builder._launch_staged_builder() == 0
    assert len(commands) == 1


def test_phase1c_builder_rejects_head_move_after_staging(
    tmp_path, monkeypatch
):
    staged_revision = "a" * 40
    monkeypatch.setattr(builder, "_require_no_credentials", lambda: None)
    monkeypatch.setattr(builder, "license_evaluator_runtime_identity", lambda: {})
    monkeypatch.setattr(
        builder,
        "_require_tools",
        lambda: pytest.fail("Docker preflight ran after staged HEAD moved"),
    )
    monkeypatch.setattr(builder, "_open_build_lock", lambda _path: open(
        tmp_path / "lock", "a+", encoding="utf-8"
    ))
    monkeypatch.setattr(builder.fcntl, "flock", lambda *args: None)
    monkeypatch.setattr(
        builder,
        "_git",
        lambda *args: "b" * 40 if args == ("rev-parse", "HEAD") else "",
    )
    monkeypatch.setattr(
        builder,
        "_load_parent_lock_from_git",
        lambda _revision: pytest.fail("parent lock read after HEAD moved"),
    )

    with pytest.raises(RuntimeError, match="HEAD moved after source staging"):
        builder.build_candidate(
            tmp_path / "output",
            source_revision=staged_revision,
        )


def test_phase1c_builder_uses_only_bootstrap_pinned_revision(
    tmp_path, monkeypatch
):
    staged_revision = "a" * 40
    parent_lock = {
        "v1_dockerfile_sha256": "c" * 64,
        "reference": "fixture",
        "observed_local_image_id": "sha256:" + "d" * 64,
    }
    captured = []
    monkeypatch.setattr(builder, "_require_no_credentials", lambda: None)
    monkeypatch.setattr(builder, "license_evaluator_runtime_identity", lambda: {})
    monkeypatch.setattr(builder, "_require_tools", lambda: None)
    monkeypatch.setattr(builder, "_open_build_lock", lambda _path: open(
        tmp_path / "lock", "a+", encoding="utf-8"
    ))
    monkeypatch.setattr(builder.fcntl, "flock", lambda *args: None)
    monkeypatch.setattr(
        builder,
        "_git",
        lambda *args: staged_revision if args == ("rev-parse", "HEAD") else "",
    )
    monkeypatch.setattr(
        builder,
        "_load_parent_lock_from_git",
        lambda revision: (captured.append(("parent", revision)) or parent_lock),
    )
    monkeypatch.setattr(
        builder,
        "_git_blob_sha256",
        lambda revision, path: (
            captured.append((path, revision))
            or parent_lock["v1_dockerfile_sha256"]
        ),
    )
    monkeypatch.setattr(
        builder,
        "_git_blob",
        lambda revision, path: (
            captured.append((path, revision))
            or json.dumps(
                json.loads(
                    Path("sandbox/agentic_v2_capabilities.json").read_text()
                )
            ).encode()
        ),
    )
    monkeypatch.setattr(
        builder,
        "_docker_json",
        lambda _command: [{
            "Id": parent_lock["observed_local_image_id"],
            "Architecture": "amd64",
            "Os": "linux",
            "RepoDigests": [parent_lock["reference"]],
        }],
    )
    monkeypatch.setattr(
        builder,
        "_build_locked",
        lambda output_root, **kwargs: (
            captured.append(("build", kwargs["source_revision"])) or {"ok": True}
        ),
    )

    assert builder.build_candidate(
        tmp_path / "output",
        source_revision=staged_revision,
    ) == {"ok": True}
    assert captured == [
        ("parent", staged_revision),
        ("batch-runner/sandbox/Dockerfile", staged_revision),
        (
            "batch-runner/sandbox/agentic_v2_capabilities.json",
            staged_revision,
        ),
        ("build", staged_revision),
    ]


def test_phase1c_build_locked_propagates_pinned_revision_end_to_end(
    tmp_path, monkeypatch
):
    staged_revision = "a" * 40
    image_id = "sha256:" + "b" * 64
    manifest_digest = "sha256:" + "c" * 64
    parent_lock = {
        "reference": "parent@sha256:" + "d" * 64,
        "manifest_digest": "sha256:" + "d" * 64,
    }
    manifest = SimpleNamespace(sha256="e" * 64)
    captured = []

    def stage_context(revision, root):
        captured.append(("context", revision))

    def stage_files(revision, root, paths):
        captured.append(("verifier-files", revision))

    def run(command, **kwargs):
        captured.append(("command", command))
        if command[:3] == [builder._TRUSTED_DOCKER, "image", "save"]:
            output = Path(command[command.index("--output") + 1])
            output.write_bytes(b"archive")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    def export(archive, output):
        captured.append(("export", archive.read_bytes()))
        output.mkdir()
        return {"manifest_digest": manifest_digest}

    def run_verifier(command, *, cwd, environment, session_id):
        captured.append(("verifier-command", command))
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({
                "gate_status": "blocked",
                "blocking_evidence": ["cve"],
            }).encode(),
            b"",
        )

    monkeypatch.setattr(builder, "_stage_git_context", stage_context)
    monkeypatch.setattr(builder, "_stage_git_files", stage_files)
    monkeypatch.setattr(builder.subprocess, "run", run)
    monkeypatch.setattr(builder, "_docker_json", lambda command: [{"Id": image_id}])
    monkeypatch.setattr(builder, "export_docker_archive_to_oci", export)
    monkeypatch.setattr(
        builder,
        "_stage_license_evaluator_runtime",
        lambda root: root.mkdir(parents=True),
    )
    monkeypatch.setattr(builder, "_run_verifier", run_verifier)

    output_root = tmp_path / "candidate"
    report = builder._build_locked(
        output_root,
        source_revision=staged_revision,
        parent_lock=parent_lock,
        manifest=manifest,
    )

    build_command = next(
        command
        for name, command in captured
        if name == "command" and command[1] == "build"
    )
    verifier_command = next(
        command for name, command in captured if name == "verifier-command"
    )
    assert ("context", staged_revision) in captured
    assert ("verifier-files", staged_revision) in captured
    assert f"SOURCE_REVISION={staged_revision}" in build_command
    assert verifier_command[
        verifier_command.index("--source-revision") + 1
    ] == staged_revision
    assert report["source_revision"] == staged_revision
    saved_report = json.loads(
        (output_root / "build-report.json").read_text(encoding="utf-8")
    )
    assert saved_report["source_revision"] == staged_revision


def test_phase1c_staged_builder_rejects_shadow_source_and_bytecode(
    tmp_path, monkeypatch
):
    staged_root = tmp_path / "batch-runner"
    source_revision = "a" * 40
    blobs = {
        path: f"exact:{path}\n".encode("ascii")
        for path in builder._BUILDER_SOURCE_PATHS
    }
    monkeypatch.setattr(
        builder,
        "_bootstrap_git_blob",
        lambda _root, _revision, path: blobs[path],
    )
    builder._bootstrap_stage_sources(tmp_path, source_revision, staged_root)
    monkeypatch.setattr(
        builder,
        "__file__",
        str(staged_root / "sandbox" / "v2" / "build_candidate.py"),
    )
    pycache = staged_root / "core" / "__pycache__"
    pycache.mkdir()
    (pycache / "agentic_v2_license.cpython-310.pyc").write_bytes(b"unchecked")

    with pytest.raises(RuntimeError, match="source inventory differs"):
        builder._bootstrap_validate_staged_sources(
            staged_root,
            tmp_path,
            source_revision,
        )


def test_phase1c_staged_runtime_rejects_extra_module_and_bytecode(tmp_path):
    builder._stage_license_evaluator_runtime(tmp_path)
    assert builder._bootstrap_staged_runtime_matches(tmp_path)
    (tmp_path / "packaging" / "shadow.py").write_text(
        "raise RuntimeError('shadow')\n", encoding="utf-8"
    )
    assert not builder._bootstrap_staged_runtime_matches(tmp_path)
    (tmp_path / "packaging" / "shadow.py").unlink()
    pycache = tmp_path / "packaging" / "__pycache__"
    pycache.mkdir()
    (pycache / "__init__.cpython-310.pyc").write_bytes(b"unchecked")
    assert not builder._bootstrap_staged_runtime_matches(tmp_path)


def test_phase1c_isolated_evaluator_runtime_ignores_system_sitecustomize(
    tmp_path,
):
    runtime_root = tmp_path / "runtime"
    builder._stage_license_evaluator_runtime(runtime_root)
    marker = tmp_path / "startup-ran"
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    (hostile / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(hostile)
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            (
                "import sys;sys.path.insert(0,sys.argv[1]);"
                "from packaging.licenses import canonicalize_license_expression;"
                "assert canonicalize_license_expression('mit') == 'MIT';"
                "assert sys.flags.isolated == 1 and sys.flags.no_site == 1;"
                "assert sys.dont_write_bytecode"
            ),
            str(runtime_root),
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert not marker.exists()
    assert not list(runtime_root.rglob("*.pyc"))


def test_phase1c_report_binds_candidate_oci_sbom_evidence_tools_and_policy():
    _fixture_value, subject, sbom, evidence, policy, report = _fixture()
    binding = report["binding"]

    assert binding == {
        "subject_sha256": canonical_sha256(subject),
        "image_id": subject["image_id"],
        "config_digest": subject["image_id"],
        "oci_manifest_digest": subject["oci_manifest_digest"],
        "source_revision": subject["source_revision"],
        "effective_sbom_sha256": canonical_sha256(sbom),
        "license_evidence_sha256": canonical_sha256(evidence),
        "license_collector_sha256": subject["license_collector_sha256"],
        "license_evaluator_sha256": subject["license_evaluator_sha256"],
        "license_evaluator_packaging_version": "26.2",
        "license_evaluator_parser_sha256": (
            "fc9c745d1883ff9f296a5b169f22eb2ee879f59a4608f20f5cb29d668f4e26f4"
        ),
        "license_evaluator_python_version": "3.10.12",
        "license_evaluator_callable_sha256": (
            "e27e24ff0053d4f68aca4d2ec770d83b8cd8536629c01406c7f5578f6972a78b"
        ),
        "license_evaluator_runtime_graph_sha256": (
            "8fff34b3a069995de020a123594de0254935b12ab154b272057807c8de7be459"
        ),
        "license_evaluator_spdx_version": "3.27.0",
        "license_evaluator_spdx_sha256": (
            "ecc082fdc1fcdcae47b2f56c4ce2cdc2c9d6d54ca555a09814abd78dece7a230"
        ),
        "policy_sha256": canonical_sha256(policy),
    }

    for key in binding:
        tampered = deepcopy(report)
        tampered["binding"][key] = "0" * 64
        with pytest.raises(ValueError, match="license report identity"):
            validate_license_report(
                tampered,
                subject=subject,
                subject_sha256=canonical_sha256(subject),
                sbom=sbom,
                license_evidence=evidence,
                policy=policy,
                policy_sha256=canonical_sha256(policy),
            )


def test_phase1c_direct_report_api_rejects_incorrect_input_hashes():
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    arguments = {
        "subject": subject,
        "subject_sha256": canonical_sha256(subject),
        "sbom": sbom,
        "license_evidence": evidence,
        "policy": policy,
        "policy_sha256": canonical_sha256(policy),
    }
    wrong_subject = dict(arguments)
    wrong_subject["subject_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="subject hash differs"):
        build_license_report(**wrong_subject)

    wrong_policy = dict(arguments)
    wrong_policy["policy_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="policy hash differs"):
        build_license_report(**wrong_policy)


def test_phase1c_license_evidence_rejects_inventory_and_source_tampering():
    _fixture_value, _subject_value, sbom, evidence, _policy_value, _report = _fixture()

    assert validate_license_evidence(evidence, sbom) == evidence

    missing = deepcopy(evidence)
    missing["records"].pop()
    missing["records_sha256"] = canonical_sha256(missing["records"])
    with pytest.raises(ValueError, match="package inventory mismatch"):
        validate_license_evidence(missing, sbom)

    wrong_source = deepcopy(evidence)
    wrong_source["records"][0]["evidence"][0]["source"] = "forged"
    wrong_source["records_sha256"] = canonical_sha256(wrong_source["records"])
    with pytest.raises(ValueError, match="license"):
        validate_license_evidence(wrong_source, sbom)

    escaped = deepcopy(evidence)
    escaped["records"][0]["evidence"][0]["path"] = "/tmp/../secret"
    escaped["records"][0]["evidence"][0]["resolved_path"] = "/tmp/../secret"
    escaped["records_sha256"] = canonical_sha256(escaped["records"])
    with pytest.raises(ValueError, match="path"):
        validate_license_evidence(escaped, sbom)

    followed = deepcopy(evidence)
    followed["records"][0]["evidence"][0]["resolved_path"] = (
        "/usr/share/doc/another-package/copyright"
    )
    followed["records_sha256"] = canonical_sha256(followed["records"])
    with pytest.raises(ValueError, match="remain lexical"):
        validate_license_evidence(followed, sbom)

    unresolved_file = deepcopy(evidence)
    python_record = next(
        item for item in unresolved_file["records"]
        if item["ecosystem"] == "python"
    )
    python_record["evidence"][0]["resolved_path"] = None
    unresolved_file["records_sha256"] = canonical_sha256(
        unresolved_file["records"]
    )
    with pytest.raises(ValueError, match="unresolved license evidence source"):
        validate_license_evidence(unresolved_file, sbom)
    with pytest.raises(ValueError, match="unresolved license evidence source"):
        verifier._verify_license_evidence_files(
            "fixture-image",
            unresolved_file,
            session=verifier.VerificationSession("a" * 32),
        )

    shadow = deepcopy(evidence)
    python_record = next(
        item for item in shadow["records"] if item["ecosystem"] == "python"
    )
    metadata_item = python_record["evidence"][0]
    shadow_path = metadata_item["path"].replace(
        "/python3.11/", "/python-shadow/"
    )
    metadata_item["path"] = shadow_path
    metadata_item["resolved_path"] = shadow_path
    shadow["records_sha256"] = canonical_sha256(shadow["records"])
    with pytest.raises(ValueError, match="Python METADATA path is invalid"):
        validate_license_evidence(shadow, sbom)


@pytest.mark.parametrize(
    ("ecosystem", "wrong_ecosystem"),
    [
        ("debian", "python"),
        ("python", "r"),
        ("r", "npm"),
        ("npm", "debian"),
    ],
)
def test_phase1c_evidence_ecosystem_must_match_purl_prefix(
    ecosystem, wrong_ecosystem
):
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(
        item for item in evidence["records"] if item["ecosystem"] == ecosystem
    )
    record["ecosystem"] = wrong_ecosystem
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="record identity"):
        validate_license_evidence(evidence, sbom)


@pytest.mark.parametrize(
    "mutation",
    ["nonempty-runtime-license", "runtime-digest", "runtime-size"],
)
def test_phase1c_host_rejects_impossible_r_runtime_evidence(mutation):
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "r")
    runtime = next(
        item for item in record["evidence"]
        if item["source"] == "r-runtime-license"
    )
    if mutation == "nonempty-runtime-license":
        record["metadata"]["runtime_license"] = "MIT"
        record["raw_values"].insert(1, "MIT")
    elif mutation == "runtime-digest":
        runtime["sha256"] = "f" * 64
    else:
        runtime["size"] += 1
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="R (license metadata|runtime evidence)"):
        validate_license_evidence(evidence, sbom)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("declared_license", " MIT "),
        ("runtime_version", " 4.2.2 "),
        ("priority", " base "),
        ("runtime_license_fields", [" GPL-2"]),
    ],
)
def test_phase1c_host_rejects_padded_r_metadata(field, value):
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "r")
    record["metadata"][field] = value
    if field == "declared_license":
        record["raw_values"][0] = value
    elif field == "runtime_license_fields":
        record["raw_values"][-1] = value[0]
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="R license metadata"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_host_rejects_inconsistent_r_runtime_across_records():
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    source = next(item for item in evidence["records"] if item["ecosystem"] == "r")
    duplicate = deepcopy(source)
    duplicate["package"] = "r-second"
    duplicate["version"] = "2.0.0"
    duplicate["purl"] = "pkg:cran/r-second@2.0.0"
    description = next(
        item for item in duplicate["evidence"] if item["source"] == "r-description"
    )
    description["path"] = "/usr/lib/R/library/r-second/DESCRIPTION"
    description["resolved_path"] = description["path"]
    copyright_item = next(
        item for item in duplicate["evidence"]
        if item["source"] == "r-runtime-copyright"
    )
    copyright_item["sha256"] = "f" * 64
    evidence["records"].append(duplicate)
    evidence["records"].sort(key=lambda item: item["purl"])
    evidence["records_sha256"] = canonical_sha256(evidence["records"])
    sbom["packages"].append({
        "name": "r-second",
        "versionInfo": "2.0.0",
        "externalRefs": [{"referenceLocator": duplicate["purl"]}],
    })

    with pytest.raises(ValueError, match="runtime evidence identity is inconsistent"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_host_rejects_empty_npm_license():
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "npm")
    record["metadata"]["license"] = ""
    record["raw_values"] = [""]
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="npm license metadata"):
        validate_license_evidence(evidence, sbom)


@pytest.mark.parametrize(
    "mutation",
    [
        "raw-without-format",
        "format-without-copyright",
        "raw-without-copyright",
        "empty-format",
        "architecture-purl-mismatch",
    ],
)
def test_phase1c_host_rejects_impossible_debian_metadata(mutation):
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(
        item for item in evidence["records"] if item["ecosystem"] == "debian"
    )
    copyright_items = [
        item for item in record["evidence"]
        if item["source"] == "debian-copyright"
    ]
    if mutation == "raw-without-format":
        record["metadata"]["copyright_format"] = None
    elif mutation in {"format-without-copyright", "raw-without-copyright"}:
        record["evidence"].remove(copyright_items[0])
        if mutation == "raw-without-copyright":
            record["metadata"]["copyright_format"] = None
    elif mutation == "empty-format":
        record["metadata"]["copyright_format"] = ""
    else:
        record["metadata"]["architecture"] = "arm64"
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="Debian"):
        validate_license_evidence(evidence, sbom)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("architecture", " amd64 "),
        ("copyright_format", " fixture "),
        ("raw_values", [" MIT "]),
    ],
)
def test_phase1c_host_rejects_padded_debian_metadata(field, value):
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(
        item for item in evidence["records"] if item["ecosystem"] == "debian"
    )
    if field == "raw_values":
        record["raw_values"] = value
    else:
        record["metadata"][field] = value
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="Debian license metadata"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_debian_status_identity_cannot_replay_exception():
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    records = [
        item for item in evidence["records"] if item["ecosystem"] == "debian"
    ]
    target = records[0]
    status = next(
        item for item in target["evidence"] if item["source"] == "debian-status"
    )
    status["sha256"] = "f" * 64
    exception = {
        "ecosystem": "debian",
        "package": target["package"],
        "version": target["version"],
        "purl": target["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": canonical_sha256(target["evidence"]),
        "reason": "historical-status",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    }
    policy["license"]["exceptions"] = [exception]
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="status evidence identity is inconsistent"):
        build_license_report(
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom=sbom,
            license_evidence=evidence,
            policy=policy,
            policy_sha256=canonical_sha256(policy),
        )


def test_phase1c_exceptions_are_exact_versioned_reviewable_and_not_stale():
    _fixture_value, subject, sbom, evidence, policy, report = _fixture()
    assert report["counts"]["exception"] == 1
    assert validate_license_exceptions(policy) == policy["license"]["exceptions"]

    wildcard = deepcopy(policy)
    wildcard["license"]["exceptions"][0]["version"] = "*"
    with pytest.raises(ValueError, match="exception identity"):
        validate_license_exceptions(wildcard)

    expired = deepcopy(policy)
    expired["license"]["exceptions"][0]["expires_at"] = "2026-07-30"
    with pytest.raises(ValueError, match="expired"):
        validate_license_exceptions(expired)

    stale = deepcopy(policy)
    stale["license"]["exceptions"][0]["evidence_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="stale or unmatched"):
        build_license_report(
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom=sbom,
            license_evidence=evidence,
            policy=stale,
            policy_sha256=canonical_sha256(stale),
        )

    denied = deepcopy(policy)
    denied["license"]["exceptions"][0]["normalized_expression"] = (
        "MIT OR BUSL-1.1"
    )
    with pytest.raises(ValueError, match="exception identity"):
        validate_license_exceptions(denied)

    blank_reviewer = deepcopy(policy)
    blank_reviewer["license"]["exceptions"][0]["approver"] = "   "
    with pytest.raises(ValueError, match="exception identity"):
        validate_license_exceptions(blank_reviewer)

    numeric_digest = deepcopy(policy)
    numeric_digest["license"]["exceptions"][0]["evidence_sha256"] = int(
        "1" * 64
    )
    with pytest.raises(ValueError, match="exception identity"):
        validate_license_exceptions(numeric_digest)


@pytest.mark.parametrize(
    "denied_identifiers",
    [
        ["BUSL-1.1", "Commons-Clause", "sspl-1.0"],
        ["BUSL-1.1 OR SSPL-1.0", "Commons-Clause"],
        ["BUSL-1.1", "Commons-Clause", "Vendor-Denied"],
        ["BUSL-1.1", "Commons-Clause", "LicenseRef-Proprietary"],
    ],
)
def test_phase1c_denied_policy_identifiers_are_exact_canonical_contract(
    denied_identifiers,
):
    policy = _policy()
    policy["license"]["denied_identifiers"] = denied_identifiers

    with pytest.raises(ValueError, match="denied license identifiers"):
        validate_license_exceptions(policy)
    with pytest.raises(ValueError, match="supply-chain policy"):
        SupplyChainPolicy.from_mapping(policy)


def test_phase1c_canonical_sspl_is_denied_in_full_report():
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "npm")
    record["raw_values"] = ["sspl-1.0"]
    record["metadata"] = {"license": "sspl-1.0", "license_file_tokens": []}
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(item for item in report["decisions"] if item["purl"] == record["purl"])

    assert decision["classification"] == "denied"
    assert decision["denied_identifiers"] == ["SSPL-1.0"]


def test_phase1c_verified_license_does_not_enable_production_gate():
    subject_mapping = _subject()
    subject = CandidateSubject.from_mapping(subject_mapping)
    policy_mapping = _policy()
    policy = SupplyChainPolicy.from_mapping(policy_mapping)
    evidence = {
        name: evidence_item(subject, name=name, status="not_run")
        for name in (
            "capability_receipt", "containment", "cve", "license", "microvm",
            "oci_layout", "provenance", "sbom", "signature",
        )
    }
    evidence["license"] = evidence_item(
        subject,
        name="license",
        status="verified",
        tool_name="gdpval-agentic-v2-license-evaluator",
        tool_version="1.0",
        tool_sha256=subject_mapping["license_evaluator_sha256"],
        report_sha256="f" * 64,
    )

    gate = build_evidence_report(subject, policy, evidence)

    assert gate["gate_status"] == "blocked"
    assert gate["production_activation"] == "disabled"
    assert "containment" in gate["blocking_evidence"]
    assert "cve" in gate["blocking_evidence"]
    assert "microvm" in gate["blocking_evidence"]
    assert "provenance" in gate["blocking_evidence"]
    assert "signature" in gate["blocking_evidence"]


def test_phase1c_collector_hashes_regular_files_and_virtual_evidence(tmp_path):
    path = tmp_path / "LICENSE"
    path.write_bytes(b"license-evidence")

    item = collector._regular_file_evidence("fixture", path)
    virtual = collector._virtual_evidence("fixture-virtual", {"b": 2, "a": 1})

    assert item == {
        "source": "fixture",
        "path": str(path),
        "resolved_path": str(path.resolve()),
        "sha256": hashlib.sha256(b"license-evidence").hexdigest(),
        "size": len(b"license-evidence"),
    }
    assert virtual["source"] == "fixture-virtual"
    assert virtual["path"] is None
    assert virtual["resolved_path"] is None
    assert virtual["sha256"] == hashlib.sha256(b'{"a":1,"b":2}').hexdigest()


def test_phase1c_image_probe_hardens_python_subprocess(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(
        image_probe.subprocess,
        "run",
        lambda command, **kwargs: (
            commands.append(command)
            or SimpleNamespace(returncode=0, stdout=b"Python 3.11\n", stderr=b"")
        ),
    )

    image_probe._run(["python", "--version"], cwd=tmp_path)

    assert commands == [["python", "-I", "-S", "-B", "--version"]]


def test_phase1c_host_rejects_numeric_evidence_digest():
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    evidence["records"][0]["evidence"][0]["sha256"] = int("1" * 64)
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="evidence item identity"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_python_license_files_cannot_escape_dist_info(tmp_path):
    root = tmp_path / "fixture-1.0.dist-info"
    licenses = root / "licenses"
    licenses.mkdir(parents=True)
    (licenses / "LICENSE").write_text("MIT", encoding="utf-8")

    records, tokens, selections = collector._python_license_files(
        root, ["LICENSE"], tmp_path
    )

    assert len(records) == 1
    assert tokens == []
    assert selections == [{
        "declared": "LICENSE",
        "path": str(licenses / "LICENSE"),
    }]
    assert records[0]["resolved_path"] == str((licenses / "LICENSE").resolve())

    outside = tmp_path / "outside"
    outside.write_text("secret", encoding="utf-8")
    (licenses / "LICENSE").unlink()
    (licenses / "LICENSE").symlink_to(outside)
    with pytest.raises(RuntimeError, match="symlink-free"):
        collector._python_license_files(root, ["LICENSE"], tmp_path)


def test_phase1c_python_license_file_denied_token_precedes_exception(
    tmp_path, monkeypatch
):
    site_root = tmp_path / "python3.11" / "site-packages"
    metadata_root = site_root / "fixture-1.0.dist-info"
    licenses = metadata_root / "licenses"
    licenses.mkdir(parents=True)
    (metadata_root / "METADATA").write_text(
        "Name: fixture\nVersion: 1.0\nLicense-File: LICENSE\n\n",
        encoding="utf-8",
    )
    (licenses / "LICENSE").write_text("SSPL-1.0\n", encoding="utf-8")
    monkeypatch.setattr(collector, "PYTHON_PURELIB_PATH", str(site_root))
    monkeypatch.setattr(
        collector.sysconfig, "get_path", lambda name: str(site_root)
    )
    record = collector._python_records()[0]
    evidence_sha256 = canonical_sha256(record["evidence"])
    exception = {
        "ecosystem": "python",
        "package": "fixture",
        "version": "1.0",
        "purl": record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": evidence_sha256,
        "reason": "fixture",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    }

    decision = license_module._decision(
        record,
        {"SSPL-1.0"},
        {(record["purl"], evidence_sha256): exception},
    )

    assert record["metadata"]["license_file_tokens"] == ["SSPL-1.0"]
    assert decision["classification"] == "denied"
    assert decision["exception"] is None


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"SSPL-1.0.\n", ["SSPL-1.0"]),
        (b"BUSL-1.1, Commons-Clause;\n", ["BUSL-1.1", "Commons-Clause"]),
        (b"SSPL-1.0.1\n", ["SSPL-1.0.1"]),
    ],
)
def test_phase1c_license_file_tokens_handle_terminal_punctuation(
    content, expected
):
    assert collector._license_file_tokens(content) == expected


def test_phase1c_terminal_punctuation_denied_token_reaches_full_report(
    tmp_path, monkeypatch
):
    site_root = tmp_path / "python3.11" / "site-packages"
    metadata_root = site_root / "fixture-1.0.dist-info"
    licenses = metadata_root / "licenses"
    licenses.mkdir(parents=True)
    (metadata_root / "METADATA").write_text(
        "Name: fixture\nVersion: 1.0\nLicense-Expression: MIT\n"
        "License-File: LICENSE\n\n",
        encoding="utf-8",
    )
    (licenses / "LICENSE").write_text(
        "Use is governed by SSPL-1.0.\n", encoding="utf-8"
    )
    monkeypatch.setattr(collector, "PYTHON_PURELIB_PATH", str(site_root))
    monkeypatch.setattr(
        collector.sysconfig, "get_path", lambda name: str(site_root)
    )
    collected = collector._python_records()[0]
    assert collected["metadata"]["license_file_tokens"] == ["SSPL-1.0"]

    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    replaced = next(
        item
        for item in evidence["records"]
        if item["ecosystem"] == "python" and item["package"] == "python-denied"
    )
    old_purl = replaced["purl"]
    hosted = deepcopy(collected)
    distribution_root = (
        "/usr/local/lib/python3.11/site-packages/fixture-1.0.dist-info"
    )
    hosted["evidence"][0]["path"] = f"{distribution_root}/METADATA"
    hosted["evidence"][0]["resolved_path"] = f"{distribution_root}/METADATA"
    hosted["evidence"][1]["path"] = f"{distribution_root}/licenses/LICENSE"
    hosted["evidence"][1]["resolved_path"] = (
        f"{distribution_root}/licenses/LICENSE"
    )
    hosted["metadata"]["license_files"][0]["path"] = (
        f"{distribution_root}/licenses/LICENSE"
    )
    replaced.clear()
    replaced.update(hosted)
    evidence["records"].sort(key=lambda item: item["purl"])
    evidence["records_sha256"] = canonical_sha256(evidence["records"])
    package = next(
        item
        for item in sbom["packages"]
        if item["externalRefs"][0]["referenceLocator"] == old_purl
    )
    package["name"] = hosted["package"]
    package["versionInfo"] = hosted["version"]
    package["externalRefs"][0]["referenceLocator"] = hosted["purl"]

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(
        item for item in report["decisions"] if item["purl"] == hosted["purl"]
    )

    assert decision["classification"] == "denied"
    assert decision["denied_identifiers"] == ["SSPL-1.0"]


def test_phase1c_host_rejects_undeclared_python_license_file():
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "python")
    distribution_root = Path(record["evidence"][0]["path"]).parent
    record["evidence"].append(
        _evidence(
            "python-license-file",
            str(distribution_root / "licenses" / "LICENSE"),
            810,
        )
    )
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    with pytest.raises(ValueError, match="license file evidence"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_host_rejects_python_license_selection_and_token_forgery():
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "python")
    distribution_root = Path(record["evidence"][0]["path"]).parent
    selected_path = str(distribution_root / "licenses" / "LICENSE")
    record["evidence"].append(
        _evidence("python-license-file", selected_path, 811)
    )
    record["metadata"]["license_files"] = [{
        "declared": "LICENSE",
        "path": str(distribution_root / "undeclared" / "LICENSE"),
    }]
    evidence["records_sha256"] = canonical_sha256(evidence["records"])
    with pytest.raises(ValueError, match="license file path"):
        validate_license_evidence(evidence, sbom)

    record["metadata"]["license_files"][0]["path"] = selected_path
    record["metadata"]["license_file_tokens"] = ["SSPL-1.0é"]
    record["raw_values"].append("SSPL-1.0é")
    evidence["records_sha256"] = canonical_sha256(evidence["records"])
    with pytest.raises(ValueError, match="Python license metadata"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_regular_file_reader_rejects_intermediate_symlink(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "LICENSE").write_text("MIT", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink-free"):
        collector._regular_file_evidence(
            "fixture", linked / "LICENSE", allowed_roots=(tmp_path,)
        )


def test_phase1c_npm_and_r_duplicate_fields_are_rejected(monkeypatch):
    monkeypatch.setattr(
        collector,
        "_read_regular_file",
        lambda *args, **kwargs: (
            {"source": "fixture"},
            b'{"name":"npm","version":"1","license":"BUSL-1.1",'
            b'"license":"MIT"}',
        ),
    )
    with pytest.raises(RuntimeError, match="npm package metadata field is duplicated"):
        collector._npm_records()

    with pytest.raises(RuntimeError, match="R DESCRIPTION field is duplicated"):
        collector._parse_r_dcf(
            b"Package: fixture\nVersion: 1\nLicense: BUSL-1.1\nLicense: MIT\n"
        )


@pytest.mark.parametrize(
    "package_bytes",
    [
        '{"name":"npm","version":"1","license":"MIT"}'.encode("utf-16"),
        '{"name":"npm","version":"1","license":"MIT"}'.encode("utf-32"),
        b'{"name":"npm","version":"1","license":"MIT","x":"\xff"}',
    ],
)
def test_phase1c_npm_metadata_requires_strict_utf8(monkeypatch, package_bytes):
    monkeypatch.setattr(
        collector,
        "_read_regular_file",
        lambda *args, **kwargs: ({"source": "fixture"}, package_bytes),
    )

    with pytest.raises(UnicodeDecodeError):
        collector._npm_records()


def test_phase1c_debian_duplicate_status_fields_are_rejected(monkeypatch):
    monkeypatch.setattr(
        collector,
        "_read_regular_file",
        lambda *args, **kwargs: (
            {"source": "fixture"},
            b"Package: fixture\npackage: hidden\nStatus: install ok installed\n"
            b"Version: 1\nArchitecture: amd64\n",
        ),
    )

    with pytest.raises(RuntimeError, match="Debian status field is duplicated"):
        collector._debian_records()


def test_phase1c_debian_dep5_fields_are_case_insensitive_and_stanza_scoped():
    first = collector._debian_fields(
        "Format: fixture\nLicense: MIT\n", "copyright"
    )
    second = collector._debian_fields("license: SSPL-1.0\n", "copyright")
    continued = collector._debian_fields(
        "License:\n MIT\n SSPL-1.0\n", "copyright"
    )

    assert first == {"format": "fixture", "license": "MIT"}
    assert second == {"license": "SSPL-1.0"}
    assert continued == {"license": "MIT\nSSPL-1.0"}
    with pytest.raises(RuntimeError, match="Debian copyright field is duplicated"):
        collector._debian_fields(
            "License: MIT\nlicense: SSPL-1.0\n", "copyright"
        )
    with pytest.raises(RuntimeError, match="Debian copyright field is duplicated"):
        collector._debian_fields("Format: one\nformat: two\n", "copyright")
    merged = collector._debian_fields(
        "# separator\nComment: one\ncomment: two\nLicense: MIT\n",
        "copyright",
        allow_noncritical_duplicates=True,
    )
    assert merged == {"comment": "one\ntwo", "license": "MIT"}
    with pytest.raises(RuntimeError, match="Debian copyright field is duplicated"):
        collector._debian_fields(
            "License: MIT\nlicense: SSPL-1.0\n",
            "copyright",
            allow_noncritical_duplicates=True,
        )


def test_phase1c_debian_license_continuation_is_preserved_and_denied(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_text(
        f"Format: {collector.DEP5_FORMAT_URI}\n\n"
        "Files: *\nLicense: MIT\n SSPL-1.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, {"SSPL-1.0"}, {})

    assert record["raw_values"] == ["MIT\nSSPL-1.0"]
    assert decision["classification"] == "denied"
    assert decision["denied_identifiers"] == ["SSPL-1.0"]


def test_phase1c_debian_continuation_denial_reaches_full_report():
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(
        item for item in evidence["records"] if item["ecosystem"] == "debian"
    )
    record["raw_values"] = ["MIT\nSSPL-1.0"]
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(
        item for item in report["decisions"] if item["purl"] == record["purl"]
    )

    assert decision["classification"] == "denied"
    assert decision["denied_identifiers"] == ["SSPL-1.0"]


def test_phase1c_debian_copyright_symlink_is_unverifiable(tmp_path, monkeypatch):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    (copyright_path.parent / "copyright.real").write_text(
        "Format: fixture\nLicense: MIT\n",
        encoding="utf-8",
    )
    copyright_path.symlink_to("copyright.real")
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})
    blocked = record["evidence"][1]

    assert blocked["source"] == "debian-copyright-path-unverifiable"
    assert blocked["path"] == str(copyright_path)
    assert blocked["resolved_path"] is None
    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == (
        "debian-copyright-path-unverifiable"
    )


def test_phase1c_debian_copyright_enotdir_is_unverifiable(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "not-a-directory"
    documentation_root.write_text("blocked", encoding="utf-8")
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})

    assert record["evidence"][1]["source"] == (
        "debian-copyright-path-unverifiable"
    )
    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == (
        "debian-copyright-path-unverifiable"
    )


@pytest.mark.parametrize(
    "identity_lines",
    ["Version: 1\n", "Architecture: amd64\n"],
)
def test_phase1c_debian_identity_requires_version_and_architecture(
    tmp_path, monkeypatch, identity_lines
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n" + identity_lines,
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(sbom_collector, "DEBIAN_STATUS_PATH", status)

    with pytest.raises(RuntimeError, match="identity is incomplete"):
        collector._debian_records()
    with pytest.raises(RuntimeError, match="identity is incomplete"):
        sbom_collector._debian_packages()


def test_phase1c_debian_invalid_utf8_fails_collector(tmp_path, monkeypatch):
    status = tmp_path / "status"
    status.write_bytes(
        b"Package: fixture\nStatus: install ok installed\n"
        b"Version: 1\nArchitecture: amd64\n\xff"
    )
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)

    with pytest.raises(UnicodeDecodeError):
        collector._debian_records()


def test_phase1c_debian_missing_copyright_is_missing_metadata(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    documentation_root.mkdir()
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})

    assert decision["classification"] == "missing_metadata"
    assert decision["normalization_reason"] == "debian-copyright-metadata-missing"


def test_phase1c_unstructured_debian_copyright_is_unverifiable(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_text(
        "This package is distributed under terms described in its sources.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})

    assert [item["source"] for item in record["evidence"]] == [
        "debian-status",
        "debian-copyright",
    ]
    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == (
        "debian-copyright-has-no-dep5-license-fields"
    )


def test_phase1c_noncanonical_debian_format_is_unverifiable(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_text(
        "Format: http://www.debian.org/doc/packaging-manuals/"
        "copyright-format/1.0/\n"
        "# Non-control-file comments remain untrusted.\n"
        "License: MIT\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})

    assert record["metadata"]["copyright_format"] is None
    assert record["raw_values"] == []
    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == (
        "debian-copyright-has-no-dep5-license-fields"
    )


def test_phase1c_orphan_debian_license_prose_is_unverifiable(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_text(
        f"Format: {collector.DEP5_FORMAT_URI}\n\n"
        "Files: *\nLicense: MIT\n\n"
        "    Detached SSPL-1.0 prose must not be ignored.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})

    assert record["metadata"]["copyright_format"] is None
    assert record["raw_values"] == []
    assert decision["classification"] == "unverifiable"
    assert decision["denied_identifiers"] == []


@pytest.mark.parametrize(
    "copyright_state", ["missing", "unstructured", "unverifiable_path"]
)
def test_phase1c_debian_without_dep5_cannot_receive_exception(
    copyright_state,
):
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(
        item for item in evidence["records"] if item["ecosystem"] == "debian"
    )
    copyright_items = [
        item for item in record["evidence"]
        if item["source"] == "debian-copyright"
    ]
    if copyright_state == "missing":
        record["evidence"].remove(copyright_items[0])
    elif copyright_state == "unverifiable_path":
        record["evidence"][record["evidence"].index(copyright_items[0])] = (
            collector._unverifiable_path_evidence(
                "debian-copyright-path-unverifiable",
                Path(f"/usr/share/doc/{record['package']}/copyright"),
            )
        )
    record["raw_values"] = []
    record["metadata"]["copyright_format"] = None
    evidence_sha256 = canonical_sha256(record["evidence"])
    policy["license"]["exceptions"].append({
        "ecosystem": "debian",
        "package": record["package"],
        "version": record["version"],
        "purl": record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": evidence_sha256,
        "reason": "non-dep5-review",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    })
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    decision = license_module._decision(
        record,
        set(policy["license"]["denied_identifiers"]),
        {
            (item["purl"], item["evidence_sha256"]): item
            for item in policy["license"]["exceptions"]
        },
    )
    assert decision["classification"] in {"missing_metadata", "unverifiable"}
    assert decision["exception"] is None
    with pytest.raises(ValueError, match="stale or unmatched"):
        build_license_report(
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom=sbom,
            license_evidence=evidence,
            policy=policy,
            policy_sha256=canonical_sha256(policy),
        )


@pytest.mark.parametrize("tampering", ["digest", "resolved_path"])
def test_phase1c_debian_unverifiable_path_observation_is_exact(tampering):
    _fixture_value, _subject, sbom, evidence, _policy, _report = _fixture()
    record = next(
        item for item in evidence["records"] if item["ecosystem"] == "debian"
    )
    copyright_item = next(
        item for item in record["evidence"]
        if item["source"] == "debian-copyright"
    )
    blocked = collector._unverifiable_path_evidence(
        "debian-copyright-path-unverifiable",
        Path(f"/usr/share/doc/{record['package']}/copyright"),
    )
    record["evidence"][record["evidence"].index(copyright_item)] = blocked
    record["raw_values"] = []
    record["metadata"]["copyright_format"] = None
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    assert validate_license_evidence(evidence, sbom) == evidence

    if tampering == "digest":
        blocked["sha256"] = "0" * 64
    else:
        blocked["resolved_path"] = blocked["path"]
    evidence["records_sha256"] = canonical_sha256(evidence["records"])
    with pytest.raises(ValueError, match="unverifiable path evidence is invalid"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_debian_malformed_denied_field_fails_collector(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_text(
        "Format: fixture\nLicense: MIT\nLicense : SSPL-1.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    with pytest.raises(RuntimeError, match="field name is malformed"):
        collector._debian_records()


@pytest.mark.parametrize(
    ("copyright_text", "newline"),
    [
        ("License: MIT{nl}", "\n"),
        ("License: MIT{nl}{nl}Format: fixture{nl}", "\n"),
        ("License: MIT{nl}{nl}Format: fixture{nl}", "\r\n"),
        ("License: MIT{nl}{nl}Format: fixture{nl}", "\r"),
    ],
)
def test_phase1c_formatless_dep5_like_document_is_unverifiable(
    tmp_path, monkeypatch, copyright_text, newline
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_bytes(copyright_text.format(nl=newline).encode("utf-8"))
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})

    assert record["metadata"]["copyright_format"] is None
    assert record["raw_values"] == []
    assert decision["classification"] == "unverifiable"


def test_phase1c_dep5_requires_nonempty_first_stanza_format(
    tmp_path, monkeypatch
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_text("Format:   \nLicense: MIT\n", encoding="utf-8")
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    with pytest.raises(RuntimeError, match="DEP-5 Format header is invalid"):
        collector._debian_records()


@pytest.mark.parametrize(
    "field_line",
    [
        "Upstream-Name: fixture",
        "Upstream-Contact: maintainer@example.test",
        "Source: https://example.test/source",
        "Disclaimer: generated source",
        "Comment: package notes",
        "Copyright: 2026 Example",
        "Files: *",
        "Files-Excluded: vendor/*",
        "Files-Excluded-component: generated/*",
    ],
)
def test_phase1c_dep5_field_set_without_format_is_unverifiable(
    tmp_path, monkeypatch, field_line
):
    status = tmp_path / "status"
    status.write_text(
        "Package: fixture\nStatus: install ok installed\n"
        "Version: 1\nArchitecture: amd64\n",
        encoding="utf-8",
    )
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_text(field_line + "\n", encoding="utf-8")
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )

    record = collector._debian_records()[0]
    decision = license_module._decision(record, set(), {})

    assert record["metadata"]["copyright_format"] is None
    assert record["raw_values"] == []
    assert decision["classification"] == "unverifiable"


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_phase1c_debian_newlines_are_deterministic_through_full_report(
    tmp_path, monkeypatch, newline
):
    status = tmp_path / "status"
    status.write_bytes((
        "Package: fixture{nl}Status: install ok installed{nl}"
        "Version: 1.0{nl}Architecture: amd64{nl}"
    ).format(nl=newline).encode("utf-8"))
    documentation_root = tmp_path / "doc"
    copyright_path = documentation_root / "fixture" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_bytes((
        "Format: https://www.debian.org/doc/packaging-manuals/"
        "copyright-format/1.0/{nl}{nl}Files: *{nl}License: Expat{nl}"
    ).format(nl=newline).encode("utf-8"))
    monkeypatch.setattr(collector, "DEBIAN_STATUS_PATH", status)
    monkeypatch.setattr(
        collector, "DEBIAN_DOCUMENTATION_ROOT", documentation_root
    )
    monkeypatch.setattr(sbom_collector, "DEBIAN_STATUS_PATH", status)

    record = collector._debian_records()[0]
    sbom_package = sbom_collector._debian_packages()[0]
    record["evidence"][0]["path"] = "/var/lib/dpkg/status"
    record["evidence"][0]["resolved_path"] = "/var/lib/dpkg/status"
    record["evidence"][1]["path"] = "/usr/share/doc/fixture/copyright"
    record["evidence"][1]["resolved_path"] = record["evidence"][1]["path"]
    evidence = {
        "schema_version": "1.0",
        "collector": "gdpval-agentic-v2-license-evidence-v1",
        "records": [record],
        "records_sha256": canonical_sha256([record]),
    }
    sbom = {"packages": [sbom_package]}
    policy = _policy()
    subject = _subject()

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )

    assert record["raw_values"] == ["Expat"]
    assert report["decisions"][0]["classification"] == "resolved"
    assert report["decisions"][0]["normalized_expression"] == "MIT"


def test_phase1c_python_single_use_metadata_duplicates_are_rejected(
    tmp_path,
    monkeypatch,
):
    site_root = tmp_path / "python3.11" / "site-packages"
    metadata_root = site_root / "fixture-1.0.dist-info"
    metadata_root.mkdir(parents=True)
    (metadata_root / "METADATA").write_text(
        "Name: fixture\nVersion: 1.0\nLicense-Expression: MIT\n"
        "License-Expression: BUSL-1.1\n\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "PYTHON_PURELIB_PATH", str(site_root))
    monkeypatch.setattr(
        collector.sysconfig, "get_path", lambda name: str(site_root)
    )

    with pytest.raises(RuntimeError, match="single-use metadata is duplicated"):
        collector._python_records()


def test_phase1c_python_purelib_runtime_drift_is_rejected(monkeypatch):
    monkeypatch.setattr(
        collector.sysconfig,
        "get_path",
        lambda name: "/usr/local/lib/python-shadow/site-packages",
    )

    with pytest.raises(RuntimeError, match="purelib root differs"):
        collector._python_records()


def test_phase1c_python_malformed_denied_header_fails_collector(
    tmp_path, monkeypatch
):
    site_root = tmp_path / "python3.11" / "site-packages"
    metadata_root = site_root / "fixture-1.0.dist-info"
    metadata_root.mkdir(parents=True)
    (metadata_root / "METADATA").write_bytes(
        b"Name: fixture\nVersion: 1.0\nLicense: MIT\n"
        b"License : SSPL-1.0\n\n"
    )
    monkeypatch.setattr(collector, "PYTHON_PURELIB_PATH", str(site_root))
    monkeypatch.setattr(
        collector.sysconfig, "get_path", lambda name: str(site_root)
    )

    with pytest.raises(RuntimeError, match="metadata is malformed"):
        collector._python_records()


def test_phase1c_python_utf8_multiline_license_is_serializable(
    tmp_path, monkeypatch
):
    site_root = tmp_path / "python3.11" / "site-packages"
    metadata_root = site_root / "fixture-1.0.dist-info"
    metadata_root.mkdir(parents=True)
    (metadata_root / "METADATA").write_bytes(
        b"Name: fixture\nVersion: 1.0\nLicense: BSD prose\n"
        b" Copyright Jos\xc3\xa9 Example\n\n"
    )
    monkeypatch.setattr(collector, "PYTHON_PURELIB_PATH", str(site_root))
    monkeypatch.setattr(
        collector.sysconfig, "get_path", lambda name: str(site_root)
    )

    record = collector._python_records()[0]

    assert isinstance(record["metadata"]["license"], str)
    assert "Jos" in record["metadata"]["license"]
    json.dumps(record, sort_keys=True, allow_nan=False)


def test_phase1c_python_invalid_utf8_fails_collector(tmp_path, monkeypatch):
    site_root = tmp_path / "python3.11" / "site-packages"
    metadata_root = site_root / "fixture-1.0.dist-info"
    metadata_root.mkdir(parents=True)
    (metadata_root / "METADATA").write_bytes(
        b"Name: fixture\nVersion: 1.0\nLicense: MIT\n"
        b"X-Denied-Looking: \xffSSPL-1.0\n\n"
    )
    monkeypatch.setattr(collector, "PYTHON_PURELIB_PATH", str(site_root))
    monkeypatch.setattr(
        collector.sysconfig, "get_path", lambda name: str(site_root)
    )

    with pytest.raises(UnicodeDecodeError):
        collector._python_records()


def test_phase1c_python_enumerates_only_direct_purelib_children(
    tmp_path, monkeypatch
):
    site_root = tmp_path / "python3.11" / "site-packages"
    direct = site_root / "direct-1.0.dist-info"
    nested = site_root / "shadow" / "nested-1.0.dist-info"
    direct.mkdir(parents=True)
    nested.mkdir(parents=True)
    (direct / "METADATA").write_text(
        "Name: direct\nVersion: 1.0\nLicense: MIT\n\n", encoding="utf-8"
    )
    (nested / "METADATA").write_text(
        "Name: nested\nVersion: 1.0\nLicense: SSPL-1.0\n\n", encoding="utf-8"
    )
    monkeypatch.setattr(collector, "PYTHON_PURELIB_PATH", str(site_root))
    monkeypatch.setattr(
        collector.sysconfig, "get_path", lambda name: str(site_root)
    )

    records = collector._python_records()

    assert [record["package"] for record in records] == ["direct"]


def test_phase1c_python_metadata_enumeration_does_not_use_glob():
    assert ".glob(" not in inspect.getsource(collector._python_records)


def test_phase1c_atomic_file_read_rejects_identity_change(tmp_path, monkeypatch):
    path = tmp_path / "LICENSE"
    path.write_text("MIT", encoding="utf-8")
    original_fstat = collector.os.fstat
    calls = 0

    def changed_fstat(descriptor):
        nonlocal calls
        value = original_fstat(descriptor)
        calls += 1
        if calls == 2:
            class Changed:
                st_dev = value.st_dev
                st_ino = value.st_ino
                st_mode = value.st_mode
                st_nlink = value.st_nlink
                st_size = value.st_size
                st_mtime_ns = value.st_mtime_ns + 1
            return Changed()
        return value

    monkeypatch.setattr(collector.os, "fstat", changed_fstat)

    with pytest.raises(RuntimeError, match="changed while reading"):
        collector._regular_file_evidence("fixture", path)


def test_phase1c_collector_is_uid_guarded_sorted_and_deterministic(monkeypatch):
    def record(purl):
        return {
            "ecosystem": "npm",
            "package": purl,
            "version": "1",
            "purl": purl,
            "raw_values": ["MIT"],
            "metadata": {"license": "MIT", "license_file_tokens": []},
            "evidence": [{
                "source": "fixture",
                "path": "/fixture",
                "resolved_path": "/fixture",
                "sha256": "a" * 64,
                "size": 1,
            }],
        }

    monkeypatch.setattr(collector.os, "geteuid", lambda: 65532)
    monkeypatch.setattr(collector.os, "getegid", lambda: 65532)
    monkeypatch.setattr(collector, "_debian_records", lambda: [record("pkg:z/z@1")])
    monkeypatch.setattr(collector, "_python_records", lambda: [record("pkg:a/a@1")])
    monkeypatch.setattr(collector, "_r_records", lambda: [])
    monkeypatch.setattr(collector, "_npm_records", lambda: [])

    first = collector.collect()
    second = collector.collect()

    assert first == second
    assert [item["purl"] for item in first["records"]] == ["pkg:a/a@1", "pkg:z/z@1"]
    assert first["records_sha256"] == canonical_sha256(first["records"])

    monkeypatch.setattr(collector.os, "geteuid", lambda: 0)
    with pytest.raises(RuntimeError, match="UID/GID 65532"):
        collector.collect()


def test_phase1c_collector_and_evaluator_are_staged_without_activation():
    dockerfile = Path("sandbox/v2/professional-work.Dockerfile").read_text(
        encoding="utf-8"
    )
    verifier_source = inspect.getsource(verifier.verify_candidate)

    assert "batch-runner/sandbox/v2/license_evidence.py" in builder._BUILD_CONTEXT_PATHS
    assert "batch-runner/core/agentic_v2_license.py" not in builder._BUILD_CONTEXT_PATHS
    assert "batch-runner/core/agentic_v2_license.py" in builder._VERIFIER_PATHS
    assert "COPY sandbox/v2/license_evidence.py /opt/gdpval/v2/license_evidence.py" in dockerfile
    assert (
        'ENTRYPOINT ["python", "-I", "-S", "-B", '
        '"/opt/gdpval/v2/disabled_entrypoint.py"]'
    ) in dockerfile.splitlines()
    assert "evaluate_license_policy(" not in verifier_source
    assert verifier_source.count("_run_image_json(\n            image_id") == 3
    assert verifier_source.count("include_purelib=True") == 2
    assert verifier_source.count("include_purelib=False") == 1

    policy = json.loads(Path("security/agentic-v2-supply-chain-policy.json").read_text())
    assert policy["foundation_only"] is True
    assert policy["production_activation"] == "disabled"
    assert policy["required_evidence"] == sorted(policy["required_evidence"])
    for name in ("containment", "cve", "microvm", "provenance", "signature"):
        assert name in policy["required_evidence"]


def test_phase1c_python_unresolved_metadata_cannot_be_overridden_by_classifier():
    fixture, subject, sbom, evidence, policy, _report = _fixture()
    del fixture
    record = next(item for item in evidence["records"] if item["ecosystem"] == "python")
    record["raw_values"] = [
        "Vendor-Proprietary",
        "License :: OSI Approved :: MIT License",
    ]
    record["metadata"] = {
        "license_expression": None,
        "license": "Vendor-Proprietary",
        "classifiers": ["License :: OSI Approved :: MIT License"],
        "license_file_tokens": [],
        "license_files": [],
    }
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(item for item in report["decisions"] if item["purl"] == record["purl"])
    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == "unresolved-explicit-python-license-field"


def test_phase1c_unknown_python_classifier_blocks_resolution():
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "python")
    record["raw_values"] = [
        "MIT",
        "License :: Other/Proprietary License",
    ]
    record["metadata"] = {
        "license_expression": None,
        "license": "MIT",
        "classifiers": ["License :: Other/Proprietary License"],
        "license_file_tokens": [],
        "license_files": [],
    }
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(item for item in report["decisions"] if item["purl"] == record["purl"])
    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == "unmapped-python-license-classifier"


@pytest.mark.parametrize(
    ("license_value", "classifiers", "classification", "reason"),
    [
        (
            "Vendor-Proprietary",
            [],
            "unverifiable",
            "unresolved-explicit-python-license-field",
        ),
        (
            "Apache-2.0",
            [],
            "ambiguous",
            "conflicting-python-license-metadata",
        ),
        (
            None,
            ["License :: Other/Proprietary License"],
            "unverifiable",
            "unmapped-python-license-classifier",
        ),
    ],
)
def test_phase1c_python_expression_does_not_hide_conflicting_metadata(
    license_value,
    classifiers,
    classification,
    reason,
):
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "python")
    record["raw_values"] = [
        value for value in ["MIT", license_value, *classifiers] if value is not None
    ]
    record["metadata"] = {
        "license_expression": "MIT",
        "license": license_value,
        "classifiers": classifiers,
        "license_file_tokens": [],
        "license_files": [],
    }
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(item for item in report["decisions"] if item["purl"] == record["purl"])
    assert decision["classification"] == classification
    assert decision["normalization_reason"] == reason


def test_phase1c_mixed_case_denied_identifier_cannot_use_exception():
    _fixture_value, _subject, _sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "python")
    record["raw_values"] = ["sspl-1.0", "Reviewed-Custom"]
    record["metadata"] = {
        "license_expression": "sspl-1.0",
        "license": "Reviewed-Custom",
        "classifiers": [],
        "license_file_tokens": [],
        "license_files": [],
    }
    evidence_sha256 = canonical_sha256(record["evidence"])
    exception = {
        **policy["license"]["exceptions"][0],
        "package": record["package"],
        "version": record["version"],
        "purl": record["purl"],
        "evidence_sha256": evidence_sha256,
    }

    decision = license_module._decision(
        record,
        {"BUSL-1.1", "Commons-Clause", "SSPL-1.0"},
        {(record["purl"], evidence_sha256): exception},
    )

    assert decision["classification"] == "denied"
    assert decision["denied_identifiers"] == ["SSPL-1.0"]
    assert decision["exception"] is None


def test_phase1c_bounded_command_rejects_stdout_and_stderr_overflow():
    with pytest.raises(RuntimeError, match="stdout exceeds size limit"):
        verifier._run_bounded_command(
            [sys.executable, "-c", "print('x' * 10000)"],
            timeout=5,
            stdout_limit=100,
            stderr_limit=100,
        )
    with pytest.raises(RuntimeError, match="stderr exceeds size limit"):
        verifier._run_bounded_command(
            [sys.executable, "-c", "import sys;sys.stderr.write('x' * 10000)"],
            timeout=5,
            stdout_limit=100,
            stderr_limit=100,
        )


def test_phase1c_bounded_json_rejects_duplicates_depth_and_huge_integer():
    with pytest.raises(ValueError, match="duplicate keys"):
        verifier._bounded_json_loads(b'{"a":1,"a":2}')
    with pytest.raises(RuntimeError, match="structure exceeds limits"):
        verifier._bounded_json_loads(("[" * 65 + "0" + "]" * 65).encode())
    with pytest.raises(ValueError, match="integer is too large"):
        verifier._bounded_json_loads(b'{"value":' + b"9" * 101 + b'}')
    with pytest.raises(ValueError, match="constant is invalid"):
        verifier._bounded_json_loads(b'{"value":NaN}')
    with pytest.raises(ValueError, match="float is not finite"):
        verifier._bounded_json_loads(b'{"value":1e400}')


def test_phase1c_debian_parenthesized_alternatives_preserve_scope():
    outcome = license_module._debian_expression("(GPL-2+) or (Expat)")
    assert outcome.issue is None
    assert outcome.expression == "(GPL-2.0-or-later) OR (MIT)"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "GPL-2+ or Expat and Apache-2",
            "((Apache-2.0) AND (MIT)) OR (GPL-2.0-or-later)",
        ),
        (
            "(GPL-2+ or Expat) and Apache-2",
            "((GPL-2.0-or-later) OR (MIT)) AND (Apache-2.0)",
        ),
        (
            "GPL-2+ with Bison exception and Expat",
            "(GPL-2.0-or-later WITH Bison-exception-2.2) AND (MIT)",
        ),
        (
            "(GPL-2+ with Bison exception) or (Expat and Apache-2)",
            "((Apache-2.0) AND (MIT)) OR "
            "(GPL-2.0-or-later WITH Bison-exception-2.2)",
        ),
    ],
)
def test_phase1c_debian_nested_operator_precedence(raw, expected):
    outcome = license_module._debian_expression(raw)
    assert outcome.issue is None
    assert outcome.expression == expected


@pytest.mark.parametrize(
    "value",
    [
        "LicenseRef-Proprietary",
        "MIT OR LicenseRef-Proprietary",
        "DocumentRef-vendor:LicenseRef-Proprietary",
    ],
)
def test_phase1c_custom_spdx_references_are_unverifiable(value):
    outcome = license_module._atom(value, {})
    assert outcome.expression is None
    assert outcome.issue == "unverifiable"
    assert license_module._canonical(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "LicenseRef-Proprietary",
        "MIT OR LicenseRef-Proprietary",
        "DocumentRef-vendor:LicenseRef-Proprietary",
    ],
)
def test_phase1c_custom_spdx_references_cannot_be_exceptions(value):
    _fixture_value, _subject, _sbom, _evidence_value, policy, _report = _fixture()
    policy["license"]["exceptions"][0]["normalized_expression"] = value

    with pytest.raises(ValueError, match="exception identity"):
        validate_license_exceptions(policy)


def test_phase1c_host_validates_npm_reference_file_path():
    _fixture_value, _subject, sbom, evidence, _policy_value, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "npm")
    record["raw_values"] = ["SEE LICENSE IN LICENSE"]
    record["metadata"] = {
        "license": "SEE LICENSE IN LICENSE",
        "license_file_tokens": [],
    }
    record["evidence"].append(
        _evidence("npm-license-file", "/usr/share/nodejs/npm/LICENSE", 500)
    )
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    assert validate_license_evidence(evidence, sbom) == evidence
    record["evidence"][-1]["path"] = "/usr/share/nodejs/npm/OTHER"
    record["evidence"][-1]["resolved_path"] = "/usr/share/nodejs/npm/OTHER"
    evidence["records_sha256"] = canonical_sha256(evidence["records"])
    with pytest.raises(ValueError, match="source path"):
        validate_license_evidence(evidence, sbom)


def test_phase1c_r_runtime_dep5_is_case_insensitive_and_denied_visible():
    fields = collector._debian_license_values(
        b"License: GPL-2\n\nlicense: SSPL-1.0\n",
        "R runtime copyright",
    )

    assert fields == ["GPL-2", "SSPL-1.0"]


def _configure_r_tree(
    tmp_path,
    monkeypatch,
    *,
    declared_license="Part of R 4.2.2",
    priority="base",
    runtime_copyright=(
        b"Format: https://www.debian.org/doc/packaging-manuals/"
        b"copyright-format/1.0/\n\nLicense: GPL-2\n"
    ),
):
    library_root = tmp_path / "R" / "library"
    package_root = library_root / "base"
    package_root.mkdir(parents=True)
    description = (
        f"Package: base\nVersion: 4.2.2\nLicense: {declared_license}\n"
        f"Priority: {priority}\n"
    )
    (package_root / "DESCRIPTION").write_text(description, encoding="utf-8")
    copyright_path = tmp_path / "doc" / "r-base-core" / "copyright"
    copyright_path.parent.mkdir(parents=True)
    copyright_path.write_bytes(runtime_copyright)
    shared_root = tmp_path / "R" / "share" / "licenses"
    shared_root.mkdir(parents=True)
    monkeypatch.setattr(collector, "R_LIBRARY_ROOT", library_root)
    monkeypatch.setattr(collector, "R_RUNTIME_COPYRIGHT_PATH", copyright_path)
    monkeypatch.setattr(collector, "R_SHARED_LICENSE_ROOT", shared_root)
    return package_root


def test_phase1c_r_records_surface_mixed_case_runtime_denied(
    tmp_path, monkeypatch
):
    _configure_r_tree(
        tmp_path,
        monkeypatch,
        runtime_copyright=(
            b"Format: https://www.debian.org/doc/packaging-manuals/"
            b"copyright-format/1.0/\n\nLicense: GPL-2\n\n"
            b"license: SSPL-1.0\n"
        ),
    )

    record = collector._r_records()[0]
    decision = license_module._decision(record, {"SSPL-1.0"}, {})

    assert record["metadata"]["runtime_license_fields"] == ["GPL-2", "SSPL-1.0"]
    assert decision["classification"] == "denied"
    assert decision["denied_identifiers"] == ["SSPL-1.0"]


def test_phase1c_effective_sbom_r_inventory_is_static(tmp_path, monkeypatch):
    library_root = tmp_path / "R" / "library"
    for package, license_value in (
        ("base", "Part of R 4.2.2"),
        ("translations", "Part of R 4.2.2"),
    ):
        package_root = library_root / package
        package_root.mkdir(parents=True)
        (package_root / "DESCRIPTION").write_text(
            f"Package: {package}\nVersion: 4.2.2\nLicense: {license_value}\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(sbom_collector, "R_LIBRARY_ROOT", library_root)

    packages = sbom_collector._r_packages()
    monkeypatch.setattr(
        image_probe,
        "_effective_sbom_namespace",
        lambda _expected: {
            "r_inventory_records": sbom_collector.r_inventory_records,
        },
    )

    assert [
        item["externalRefs"][0]["referenceLocator"] for item in packages
    ] == [
        "pkg:cran/base@4.2.2",
        "pkg:cran/translations@4.2.2",
    ]
    assert image_probe._r_inventory_records("a" * 64) == [
        "base=4.2.2",
        "translations=4.2.2",
    ]


def test_phase1c_image_probe_ignores_effective_sbom_shadow_bytecode(
    tmp_path, monkeypatch
):
    probe_path = tmp_path / "image_probe.py"
    probe_path.write_text("", encoding="utf-8")
    source_path = tmp_path / "effective_sbom.py"
    source_path.write_text(
        "def r_inventory_records():\n"
        "    return [{'name': 'bytecode', 'version': '0', 'license': 'MIT'}]\n",
        encoding="utf-8",
    )
    cache_path = (
        tmp_path / "__pycache__"
        / f"effective_sbom.{sys.implementation.cache_tag}.pyc"
    )
    cache_path.parent.mkdir()
    py_compile.compile(
        str(source_path),
        cfile=str(cache_path),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    source_path.write_text(
        "def r_inventory_records():\n"
        "    return [{'name': 'source', 'version': '1', 'license': 'MIT'}]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(image_probe, "__file__", str(probe_path))
    expected_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()

    records = image_probe._effective_sbom_namespace(expected_sha256)[
        "r_inventory_records"
    ]()

    assert records == [{"name": "source", "version": "1", "license": "MIT"}]
    with pytest.raises(RuntimeError, match="digest differs"):
        image_probe._effective_sbom_namespace("0" * 64)


def test_phase1c_image_probe_rejects_symlinked_effective_sbom_source(
    tmp_path, monkeypatch
):
    probe_path = tmp_path / "image_probe.py"
    probe_path.write_text("", encoding="utf-8")
    target = tmp_path / "target.py"
    target.write_text("def r_inventory_records(): return []\n", encoding="utf-8")
    (tmp_path / "effective_sbom.py").symlink_to(target)
    monkeypatch.setattr(image_probe, "__file__", str(probe_path))

    with pytest.raises(OSError):
        image_probe._effective_sbom_namespace("0" * 64)


def test_phase1c_effective_sbom_r_inventory_is_bounded(tmp_path, monkeypatch):
    library_root = tmp_path / "R" / "library"
    package_root = library_root / "base"
    package_root.mkdir(parents=True)
    description_path = package_root / "DESCRIPTION"
    description_path.write_text(
        "Package: base\nVersion: 4.2.2\nLicense: " + "M" * 65 + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sbom_collector, "R_LIBRARY_ROOT", library_root)
    monkeypatch.setattr(sbom_collector, "MAX_R_FIELD_CHARS", 64)

    with pytest.raises(RuntimeError, match="field is too large"):
        sbom_collector._r_packages()

    monkeypatch.setattr(sbom_collector, "MAX_R_FIELD_CHARS", 1024)
    monkeypatch.setattr(
        sbom_collector,
        "MAX_R_DESCRIPTION_BYTES",
        description_path.stat().st_size - 1,
    )
    with pytest.raises(RuntimeError, match="file is too large"):
        sbom_collector._r_packages()


@pytest.mark.parametrize(
    "runtime_copyright",
    [
        b"Runtime prose.\n\nLicense: GPL-2\nPortions License: Artistic\n",
        b"Format: vendor-text-v1\n\nLicense: MIT\n",
    ],
)
def test_phase1c_unstructured_r_runtime_is_unverifiable(
    tmp_path, monkeypatch, runtime_copyright
):
    _configure_r_tree(
        tmp_path,
        monkeypatch,
        runtime_copyright=runtime_copyright,
    )

    record = collector._r_records()[0]
    decision = license_module._decision(record, set(), {})

    assert record["metadata"]["runtime_copyright_format"] is None
    assert record["metadata"]["runtime_license_fields"] == []
    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == (
        "r-runtime-copyright-unstructured"
    )


@pytest.mark.parametrize(
    ("declared_license", "priority"),
    [
        ("Part of R 4.2.2", "base"),
        ("Part of R anything", "optional"),
        ("(Part of R anything)", "optional"),
        ("GPL-2 | Part of R anything", "optional"),
        ("MIT | part-of-r anything", "optional"),
        ("Part\u00a0of\u00a0R anything", "optional"),
        ("MIT | Part\u2011of\u2011R anything", "optional"),
    ],
)
def test_phase1c_unstructured_r_runtime_cannot_receive_exception(
    declared_license,
    priority,
):
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "r")
    record["metadata"]["declared_license"] = declared_license
    record["metadata"]["priority"] = priority
    record["metadata"]["runtime_copyright_format"] = None
    record["metadata"]["runtime_license_fields"] = []
    record["raw_values"] = [record["metadata"]["declared_license"]]
    evidence_sha256 = canonical_sha256(record["evidence"])
    exception = {
        "ecosystem": "r",
        "package": record["package"],
        "version": record["version"],
        "purl": record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": evidence_sha256,
        "reason": "unstructured-runtime-review",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    }
    policy["license"]["exceptions"].append(exception)
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    decision = license_module._decision(
        record,
        set(policy["license"]["denied_identifiers"]),
        {(record["purl"], evidence_sha256): exception},
    )

    assert decision["classification"] == "unverifiable"
    assert decision["exception"] is None
    with pytest.raises(ValueError, match="stale or unmatched"):
        build_license_report(
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom=sbom,
            license_evidence=evidence,
            policy=policy,
            policy_sha256=canonical_sha256(policy),
        )


def test_phase1c_r_runtime_rejects_empty_dep5_format(tmp_path, monkeypatch):
    _configure_r_tree(
        tmp_path,
        monkeypatch,
        runtime_copyright=b"Format: \n\nLicense: MIT\n",
    )

    with pytest.raises(RuntimeError, match="DEP-5 Format header is invalid"):
        collector._r_records()


def test_phase1c_r_part_of_runtime_identity_must_be_exact(tmp_path, monkeypatch):
    _configure_r_tree(
        tmp_path,
        monkeypatch,
        declared_license="Part of R anything",
        priority="optional",
    )

    decision = license_module._decision(collector._r_records()[0], set(), {})

    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == "invalid-r-runtime-license-reference"


def test_phase1c_r_malformed_denied_field_fails_collector(tmp_path, monkeypatch):
    package_root = _configure_r_tree(tmp_path, monkeypatch)
    (package_root / "DESCRIPTION").write_text(
        "Package: base\nVersion: 4.2.2\nLicense: MIT\n"
        "License : SSPL-1.0\nPriority: base\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="field name is malformed"):
        collector._r_records()


@pytest.mark.parametrize(
    "description_bytes",
    [
        b" continuation\nPackage: base\nVersion: 4.2.2\nLicense: MIT\n",
        b"Package: base\nVersion: 4.2.2\nLicense: MIT\n\n continuation\n",
    ],
)
def test_phase1c_r_orphan_continuation_fails_collector(
    tmp_path, monkeypatch, description_bytes
):
    package_root = _configure_r_tree(tmp_path, monkeypatch)
    (package_root / "DESCRIPTION").write_bytes(description_bytes)

    with pytest.raises(RuntimeError, match="DESCRIPTION"):
        collector._r_records()


def test_phase1c_r_invalid_utf8_fails_collector(tmp_path, monkeypatch):
    package_root = _configure_r_tree(tmp_path, monkeypatch)
    (package_root / "DESCRIPTION").write_bytes(
        b"Package: base\nVersion: 4.2.2\nLicense: MIT\n\xff"
    )

    with pytest.raises(UnicodeDecodeError):
        collector._r_records()


def test_phase1c_r_reference_file_is_evidence_bound(tmp_path, monkeypatch):
    package_root = _configure_r_tree(
        tmp_path, monkeypatch, declared_license="file LICENSE"
    )
    license_path = package_root / "LICENSE"
    license_path.write_text("first", encoding="utf-8")
    first = collector._r_records()[0]
    first_item = next(
        item for item in first["evidence"] if item["source"] == "r-license-file"
    )

    license_path.write_text("second", encoding="utf-8")
    second = collector._r_records()[0]
    second_item = next(
        item for item in second["evidence"] if item["source"] == "r-license-file"
    )

    assert first_item["sha256"] != second_item["sha256"]
    license_path.unlink()
    outside = tmp_path / "outside-license"
    outside.write_text("hidden", encoding="utf-8")
    license_path.symlink_to(outside)
    with pytest.raises(RuntimeError, match="symlink-free"):
        collector._r_records()


def test_phase1c_r_license_file_denied_token_precedes_exception(
    tmp_path, monkeypatch
):
    package_root = _configure_r_tree(
        tmp_path, monkeypatch, declared_license="file LICENSE"
    )
    (package_root / "LICENSE").write_text("SSPL-1.0\n", encoding="utf-8")
    record = collector._r_records()[0]
    evidence_sha256 = canonical_sha256(record["evidence"])
    exception = {
        "ecosystem": "r",
        "package": record["package"],
        "version": record["version"],
        "purl": record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": evidence_sha256,
        "reason": "fixture",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    }

    decision = license_module._decision(
        record,
        {"SSPL-1.0"},
        {(record["purl"], evidence_sha256): exception},
    )

    assert record["metadata"]["license_file_tokens"] == ["SSPL-1.0"]
    assert decision["classification"] == "denied"
    assert decision["exception"] is None


def test_phase1c_npm_reference_file_change_invalidates_exception(
    tmp_path, monkeypatch
):
    package_root = tmp_path / "npm"
    package_root.mkdir()
    package_path = package_root / "package.json"
    package_path.write_text(
        '{"name":"npm","version":"1.0.0",'
        '"license":"SEE LICENSE IN LICENSE"}',
        encoding="utf-8",
    )
    license_path = package_root / "LICENSE"
    license_path.write_text("first", encoding="utf-8")
    monkeypatch.setattr(collector, "NPM_PACKAGE_PATH", package_path)
    first = collector._npm_records()[0]
    first_digest = canonical_sha256(first["evidence"])
    exception = {
        "ecosystem": "npm",
        "package": "npm",
        "version": "1.0.0",
        "purl": "pkg:npm/npm@1.0.0",
        "normalized_expression": "MIT",
        "evidence_sha256": first_digest,
        "reason": "reviewed-reference",
        "approver": "fixture-approver",
        "expires_at": "2027-07-31",
    }
    exception_map = {(first["purl"], first_digest): exception}
    assert license_module._decision(
        first, set(), exception_map
    )["classification"] == "exception"

    license_path.write_text("second", encoding="utf-8")
    second = collector._npm_records()[0]
    second_decision = license_module._decision(second, set(), exception_map)
    assert second_decision["classification"] == "unverifiable"
    assert second_decision["exception"] is None

    license_path.unlink()
    outside = tmp_path / "outside-npm-license"
    outside.write_text("hidden", encoding="utf-8")
    license_path.symlink_to(outside)
    with pytest.raises(RuntimeError, match="symlink-free"):
        collector._npm_records()


def test_phase1c_referenced_file_denied_token_precedes_matching_exception(
    tmp_path, monkeypatch
):
    package_root = tmp_path / "npm-denied"
    package_root.mkdir()
    package_path = package_root / "package.json"
    package_path.write_text(
        '{"name":"npm","version":"1.0.0",'
        '"license":"SEE LICENSE IN LICENSE"}',
        encoding="utf-8",
    )
    (package_root / "LICENSE").write_text("SSPL-1.0\n", encoding="utf-8")
    monkeypatch.setattr(collector, "NPM_PACKAGE_PATH", package_path)
    record = collector._npm_records()[0]
    evidence_sha256 = canonical_sha256(record["evidence"])
    exception = {
        "ecosystem": "npm",
        "package": "npm",
        "version": "1.0.0",
        "purl": record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": evidence_sha256,
        "reason": "fixture",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    }

    decision = license_module._decision(
        record,
        {"BUSL-1.1", "Commons-Clause", "SSPL-1.0"},
        {(record["purl"], evidence_sha256): exception},
    )

    assert record["metadata"]["license_file_tokens"] == ["SSPL-1.0"]
    assert record["raw_values"] == ["SEE LICENSE IN LICENSE", "SSPL-1.0"]
    assert decision["classification"] == "denied"
    assert decision["denied_identifiers"] == ["SSPL-1.0"]
    assert decision["exception"] is None

    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    npm_record = next(
        item for item in evidence["records"] if item["ecosystem"] == "npm"
    )
    hosted_record = deepcopy(record)
    for item in hosted_record["evidence"]:
        path = (
            "/usr/share/nodejs/npm/package.json"
            if item["source"] == "npm-package-json"
            else "/usr/share/nodejs/npm/LICENSE"
        )
        item["path"] = path
        item["resolved_path"] = path
    npm_record.update(hosted_record)
    evidence["records"].sort(key=lambda item: item["purl"])
    evidence["records_sha256"] = canonical_sha256(evidence["records"])
    npm_package = next(
        item for item in sbom["packages"]
        if item["externalRefs"][0]["referenceLocator"].startswith("pkg:npm/")
    )
    npm_package["name"] = record["package"]
    npm_package["versionInfo"] = record["version"]
    npm_package["externalRefs"][0]["referenceLocator"] = record["purl"]
    hosted_exception = deepcopy(exception)
    hosted_exception["evidence_sha256"] = canonical_sha256(
        hosted_record["evidence"]
    )
    policy["license"]["exceptions"] = [hosted_exception]
    with pytest.raises(ValueError, match="stale or unmatched"):
        build_license_report(
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom=sbom,
            license_evidence=evidence,
            policy=policy,
            policy_sha256=canonical_sha256(policy),
        )


def test_phase1c_npm_leading_space_reference_cannot_receive_exception(
    tmp_path, monkeypatch
):
    package_root = tmp_path / "npm-leading"
    package_root.mkdir()
    package_path = package_root / "package.json"
    package_path.write_text(
        '{"name":"npm","version":"1.0.0",'
        '"license":" SEE LICENSE IN LICENSE"}',
        encoding="utf-8",
    )
    (package_root / "LICENSE").write_text("not-collected", encoding="utf-8")
    monkeypatch.setattr(collector, "NPM_PACKAGE_PATH", package_path)

    with pytest.raises(RuntimeError, match="npm license metadata is invalid"):
        collector._npm_records()


@pytest.mark.parametrize(
    ("ecosystem", "declared", "metadata"),
    [
        (
            "r",
            "GPL-2 + file\tLICENSE",
            {
                "declared_license": "GPL-2 + file\tLICENSE",
                "priority": None,
                "runtime_license": "",
                "runtime_license_fields": [],
                "runtime_version": "4.2.2",
            },
        ),
        ("npm", "SEE  LICENSE IN LICENSE", {"license": "SEE  LICENSE IN LICENSE"}),
    ],
)
def test_phase1c_noncanonical_reference_cannot_receive_exception(
    ecosystem, declared, metadata
):
    record = {
        "ecosystem": ecosystem,
        "package": "fixture",
        "version": "1",
        "purl": f"pkg:{'cran' if ecosystem == 'r' else 'npm'}/fixture@1",
        "raw_values": [declared],
        "metadata": metadata,
        "evidence": [_evidence("fixture", "/fixture", 700)],
    }
    evidence_sha256 = canonical_sha256(record["evidence"])
    exception = {
        "ecosystem": ecosystem,
        "package": "fixture",
        "version": "1",
        "purl": record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": evidence_sha256,
        "reason": "fixture",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    }

    decision = license_module._decision(
        record,
        set(),
        {(record["purl"], evidence_sha256): exception},
    )

    assert decision["classification"] == "unverifiable"
    assert decision["exception"] is None


@pytest.mark.parametrize(
    "declared",
    [
        "SEE\u00a0LICENSE\u00a0IN LICENSE",
        "SEE\u2011LICENSE\u2011IN LICENSE",
    ],
)
def test_phase1c_unicode_npm_reference_cannot_receive_exception(declared):
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(
        item for item in evidence["records"] if item["ecosystem"] == "npm"
    )
    record["metadata"]["license"] = declared
    record["raw_values"] = [declared]
    evidence_sha256 = canonical_sha256(record["evidence"])
    exception = {
        "ecosystem": "npm",
        "package": record["package"],
        "version": record["version"],
        "purl": record["purl"],
        "normalized_expression": "MIT",
        "evidence_sha256": evidence_sha256,
        "reason": "unicode-reference-review",
        "approver": "reviewer",
        "expires_at": "2027-07-31",
    }
    policy["license"]["exceptions"].append(exception)
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    decision = license_module._decision(
        record,
        set(policy["license"]["denied_identifiers"]),
        {(record["purl"], evidence_sha256): exception},
    )

    assert decision["classification"] == "unverifiable"
    assert decision["exception"] is None
    with pytest.raises(ValueError, match="stale or unmatched"):
        build_license_report(
            subject=subject,
            subject_sha256=canonical_sha256(subject),
            sbom=sbom,
            license_evidence=evidence,
            policy=policy,
            policy_sha256=canonical_sha256(policy),
        )


def test_phase1c_license_expression_size_is_bounded():
    assert license_module._canonical("MIT OR " * 1000 + "MIT") is None


def test_phase1c_license_expression_depth_is_bounded_below_size_limit():
    expression = "(" * 400 + "MIT" + ")" * 400

    assert len(expression) < 4096
    assert license_module._canonical(expression) is None


@pytest.mark.parametrize(
    "expression",
    [
        ")MIT",
        "(MIT",
        "(" * 65 + "MIT" + ")" * 65,
        " ".join("MIT" for _ in range(513)),
    ],
)
def test_phase1c_expression_shape_rejects_before_parser(
    expression,
    monkeypatch,
):
    assert len(expression) < 4096
    monkeypatch.setattr(
        license_module,
        "canonicalize_license_expression",
        lambda _value: pytest.fail("invalid shape reached SPDX parser"),
    )

    assert license_module._canonical(expression) is None


@pytest.mark.parametrize(
    "expression",
    [
        "(" * 65 + "Expat" + ")" * 65,
        " or ".join("MIT" for _ in range(257)),
    ],
)
def test_phase1c_debian_fallback_cannot_bypass_expression_shape(
    expression,
    monkeypatch,
):
    monkeypatch.setattr(
        license_module,
        "_atom",
        lambda *args, **kwargs: pytest.fail("invalid shape reached Debian fallback"),
    )

    outcome = license_module._debian_expression(expression)

    assert outcome.expression is None
    assert outcome.issue == "unverifiable"
    assert outcome.reason == "invalid-debian-license-expression-shape"


def test_phase1c_r_fallback_cannot_bypass_expression_shape():
    declared = "|".join("MIT" for _ in range(513))
    record = {
        "metadata": {
            "declared_license": declared,
            "priority": "optional",
            "runtime_license": "",
            "runtime_version": "4.2.2",
        }
    }

    outcome = license_module._r_outcome(record)

    assert outcome.expression is None
    assert outcome.issue == "unverifiable"
    assert outcome.reason == "invalid-r-license-expression-shape"


def test_phase1c_spdx_parser_recursion_is_normalized(monkeypatch):
    monkeypatch.setattr(
        license_module,
        "canonicalize_license_expression",
        lambda _value: (_ for _ in ()).throw(RecursionError("fixture")),
    )

    assert license_module._canonical("MIT") is None


@pytest.mark.parametrize("declared", ["MIT || Apache-2.0", "| MIT", "MIT |"])
def test_phase1c_empty_r_alternatives_are_unverifiable_in_full_report(declared):
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "r")
    record["raw_values"] = [declared]
    record["metadata"] = {
        "declared_license": declared,
        "priority": "optional",
        "runtime_license": "",
        "runtime_license_fields": [],
        "runtime_copyright_format": collector.DEP5_FORMAT_URI,
        "runtime_version": "4.2.2",
        "license_file_tokens": [],
    }
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(item for item in report["decisions"] if item["purl"] == record["purl"])

    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == "invalid-r-license-alternatives"


def test_phase1c_debian_expression_is_bounded_before_parsing(monkeypatch):
    raw = "(" * 4097 + "MIT" + ")" * 4097
    monkeypatch.setattr(
        license_module,
        "_atom",
        lambda *args, **kwargs: pytest.fail("oversized expression reached parser"),
    )

    outcome = license_module._debian_expression(raw)

    assert outcome.expression is None
    assert outcome.issue == "unverifiable"
    assert outcome.reason == "invalid-debian-license-expression-shape"


def test_phase1c_oversized_debian_expression_is_unverifiable_in_full_report():
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "debian")
    record["raw_values"] = ["(" * 4097 + "MIT" + ")" * 4097]
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(item for item in report["decisions"] if item["purl"] == record["purl"])

    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == "debian-file-stanza-license-conjunction"


def test_phase1c_deep_expression_is_unverifiable_in_full_report():
    _fixture_value, subject, sbom, evidence, policy, _report = _fixture()
    record = next(item for item in evidence["records"] if item["ecosystem"] == "npm")
    expression = "(" * 400 + "MIT" + ")" * 400
    record["raw_values"] = [expression]
    record["metadata"] = {
        "license": expression,
        "license_file_tokens": [],
    }
    evidence["records_sha256"] = canonical_sha256(evidence["records"])

    report = build_license_report(
        subject=subject,
        subject_sha256=canonical_sha256(subject),
        sbom=sbom,
        license_evidence=evidence,
        policy=policy,
        policy_sha256=canonical_sha256(policy),
    )
    decision = next(item for item in report["decisions"] if item["purl"] == record["purl"])

    assert decision["classification"] == "unverifiable"
    assert decision["normalization_reason"] == "unmapped-exact-license-label"
