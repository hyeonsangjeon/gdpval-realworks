"""Local archive boundary with synthetic provenance, real byte/publish guards.

Only the registered provenance supplier/transport is synthetic. The CLI,
canonical Step0 reader, reference-tree/current-byte checks, USTAR encoding,
external digest, member checks and no-clobber publication stay real.
"""

from __future__ import annotations

import copy
import gzip
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_ci_input_bundle as bundle
from core import repo_bootstrapper
from gpt54_prepared_input_attestation import _reference_snapshot
from gpt54_run_input_bundle import _step0_bytes
from .test_codex_budget_pilot import offline  # noqa: F401


@pytest.fixture
def originals(tmp_path, monkeypatch):
    root = tmp_path / "synthetic-originals"
    root.mkdir()
    references = root / "references"
    names = ("reference_files/first/one.txt", "reference_files/second/two.txt")
    records = {}
    for index, name in enumerate(names):
        path = references / name
        path.parent.mkdir(parents=True)
        path.write_bytes(f"synthetic reference {index}\r\n".encode())
        records[name] = bundle._identity(path.read_bytes())
    parquet = root / "original.parquet"
    # This is deliberately not an original dataset or a fabricated real pin.
    # Its provenance is accepted only by the explicit synthetic transport.
    parquet.write_bytes(b"PAR1 synthetic provenance boundary\x00\xffPAR1")
    source_digest = "a" * 64
    manifest = {
        "_schema_version": 4, "_summary": {"active_policy": "deliverable_only"},
        "_total_tasks": 1,
        "tasks": {"synthetic-task": {"needs_files": True, "source_projection_sha256": source_digest}},
        "reference_files": records,
        "_source_path": "/synthetic/private/original.parquet",
    }
    step0 = root / "canonical-step0.json"
    step0.write_bytes(bundle._canonical_json(manifest).encode())
    monkeypatch.setattr(repo_bootstrapper, "NEEDS_FILES_POLICY", "deliverable_only")
    monkeypatch.setattr(repo_bootstrapper, "CANONICAL_MANIFEST_SHA256_BY_POLICY", {
        **repo_bootstrapper.CANONICAL_MANIFEST_SHA256_BY_POLICY,
        "deliverable_only": bundle._identity(step0.read_bytes())["sha256"],
    })
    monkeypatch.setenv("NEEDS_FILES_POLICY", "deliverable_only")
    files = {bundle.PARQUET: parquet.read_bytes(), **{
        bundle.REFERENCES + "/" + name: (references / name).read_bytes() for name in names
    }, bundle.STEP0: step0.read_bytes()}
    specs = {name: {"role": "normalized_original_parquet" if name == bundle.PARQUET else
                   "canonical_schema4_deliverable_only_step0" if name == bundle.STEP0 else "declared_reference",
                   **bundle._identity(data)} for name, data in files.items()}
    plan = object()
    revision = "b" * 40
    monkeypatch.setattr(bundle, "_registered", lambda: (plan, revision, copy.deepcopy(specs)))

    class SyntheticProvenance(pilot.LocalTransport):
        def __init__(self):
            self.calls = []

        def inputs(self, requested_plan, sources):
            assert requested_plan is plan
            self.calls.append(sources)
            data = bundle._read_bytes(sources.parquet, **bundle._identity(files[bundle.PARQUET]))
            refs = _reference_snapshot(sources.references, {name: record["sha256"] for name, record in records.items()})
            snapshot = pilot._SourceSnapshot(
                {"needs_files_policy": "deliverable_only", "synthetic_provenance": True},
                [{"projection": {"task_id": "synthetic-task", "reference_files": list(names)},
                  "source_projection_sha256": source_digest,
                  "reference_file_records": [{"path": name, **refs[name]} for name in names]}],
                [], refs, {"synthetic-task": True}, None,
            )
            canonical = _step0_bytes(sources.manifest, snapshot)
            return pilot.VerifiedInputs(snapshot, {
                bundle.PARQUET_PATH: data, bundle.STEP0_MANIFEST_PATH: canonical,
                **{bundle.DATASET_ROOT + "/" + name: bundle._read_bytes(sources.references / name, **identity)
                   for name, identity in refs.items()},
            })

    return SimpleNamespace(root=root, parent=tmp_path, parquet=parquet, references=references,
                           step0=step0, files=files, specs=specs, revision=revision,
                           transport=SyntheticProvenance())


def produce(case, output):
    return bundle.main(["produce", "--dataset-parquet", str(case.parquet), "--reference-root", str(case.references),
                        "--step0-manifest", str(case.step0), "--out", str(output)], _test_transport=case.transport)


def import_local(case, archive, output, digest=None):
    return bundle.main(["import", "--bundle", str(archive), "--expected-sha256",
                        digest or bundle._identity(archive.read_bytes())["sha256"], "--out", str(output)],
                       _test_transport=case.transport)


def reservation(path):
    return path.with_name(path.name + ".input-bundle-reserved.json")


def archive_bytes(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT, encoding="utf-8") as output:
        for name, data in entries:
            output.addfile(bundle._header(name, len(data)), io.BytesIO(data))
    return stream.getvalue()


def change_header(data, index, **changes):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:", encoding="utf-8") as archive:
        member = archive.getmembers()[index]
    for key, value in changes.items():
        setattr(member, key, value)
    header = member.tobuf(format=tarfile.USTAR_FORMAT, encoding="utf-8", errors="strict")
    return data[:member.offset] + header + data[member.offset + tarfile.BLOCKSIZE:]


def test_ci_input_bundle_real_registration_matches_approved_pins():
    _, revision, specs = bundle._registered()
    assert revision == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    assert len(specs) == 4
    assert specs[bundle.PARQUET] == {"role": "normalized_original_parquet", **bundle.PARQUET_PIN}
    assert specs[bundle.STEP0] == {"role": "canonical_schema4_deliverable_only_step0", **bundle.STEP0_PIN}
    assert len([name for name in specs if name.startswith("reference-only/reference_files/")]) == 2


def test_ci_input_bundle_deterministic_roundtrip_real_cli_and_verifier(originals, capsys):
    case = originals
    first, second = case.parent / "first.tar", case.parent / "second.tar"
    assert produce(case, first) == 0
    report = json.loads(capsys.readouterr().out)
    replacement = case.parent / "other-source-location"
    shutil.copytree(case.root, replacement)
    case.parquet, case.references, case.step0 = replacement / "original.parquet", replacement / "references", replacement / "canonical-step0.json"
    os.utime(case.parquet, (1, 1))
    assert produce(case, second) == 0
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(capsys.readouterr().out) == report
    installed = case.parent / "ci-inputs"
    assert import_local(case, first, installed) == 0
    assert json.loads(capsys.readouterr().out) == report
    assert case.transport.calls[-1] == pilot.InputSources(installed / bundle.PARQUET, installed / bundle.REFERENCES, installed / bundle.STEP0)
    assert len(case.transport.calls) == 3  # Two producers, one installed verifier.
    for name, expected in case.files.items():
        assert (installed / name).read_bytes() == expected
        assert stat.S_IMODE((installed / name).stat().st_mode) == 0o600
    assert stat.S_IMODE(installed.stat().st_mode) == 0o700
    assert json.loads((installed / bundle.READY).read_bytes())["bundle"] == report["bundle"]
    assert reservation(first).is_file() and reservation(installed).is_file()
    assert report["canonical_step0_publication_sensitive_fields_found"] is True
    manifest = (installed / bundle.MANIFEST).read_text()
    assert "/synthetic/private" not in manifest and str(case.parent) not in manifest
    assert set(json.loads(manifest)) == {"dataset_revision", "files"}
    assert set(path.relative_to(installed).as_posix() for path in installed.rglob("*") if path.is_file()) == {
        *case.files, bundle.MANIFEST, bundle.READY,
    }
    assert "/synthetic/private" not in json.dumps(report) and str(case.parent) not in json.dumps(report)


@pytest.mark.parametrize("defect", [
    "absolute", "traversal", "duplicate", "extra", "symlink", "hardlink", "directory", "device", "pax",
    "owner_metadata", "gzip", "oversized_header", "oversized_bundle", "truncated_member", "truncated_trailer",
    "nonzero_padding", "changed_content", "forged_inner_manifest", "manifest_role", "duplicate_json_key",
])
def test_ci_input_bundle_archive_refusal_before_publication(originals, monkeypatch, capsys, defect):
    case = originals
    archive = case.parent / "source.tar"
    assert produce(case, archive) == 0
    capsys.readouterr()
    data = archive.read_bytes()
    manifest, files = bundle._unpack(data, case.revision, case.specs)
    entries = [(bundle.MANIFEST, bundle._canonical_json(manifest).encode()), *files.items()]
    if defect in {"absolute", "traversal", "duplicate"}:
        data = change_header(data, 1, name={"absolute": "/original.parquet", "traversal": "../original.parquet", "duplicate": bundle.MANIFEST}[defect])
    elif defect == "extra":
        data = archive_bytes([*entries, (".env", b"synthetic-forbidden-extra")])
    elif defect in {"symlink", "hardlink", "directory", "device", "pax"}:
        kind = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE, "directory": tarfile.DIRTYPE,
                "device": tarfile.CHRTYPE, "pax": tarfile.XHDTYPE}[defect]
        data = change_header(data, 1, type=kind, linkname="forbidden" if defect.endswith("link") else "")
    elif defect == "owner_metadata":
        data = change_header(data, 0, uname="private-host-user")
    elif defect == "gzip":
        data = gzip.compress(data, mtime=0)
    elif defect == "oversized_header":
        data = change_header(data, 0, size=bundle.MAX_MANIFEST_BYTES + 1)
    elif defect == "oversized_bundle":
        monkeypatch.setattr(bundle, "MAX_BUNDLE_BYTES", len(data) - 1)
    elif defect == "truncated_member":
        data = data[:tarfile.BLOCKSIZE + 2]
    elif defect == "truncated_trailer":
        data = data[:-1]
    elif defect == "nonzero_padding":
        end = tarfile.BLOCKSIZE + len(entries[0][1])
        data = data[:end] + b"x" + data[end + 1:]
    elif defect in {"changed_content", "forged_inner_manifest"}:
        files[bundle.PARQUET] += b"changed"
        if defect == "forged_inner_manifest":
            manifest["files"][0].update(bundle._identity(files[bundle.PARQUET]))
        data = archive_bytes([(bundle.MANIFEST, bundle._canonical_json(manifest).encode()), *files.items()])
    elif defect == "manifest_role":
        manifest["files"][0]["role"] = "model_result"
        data = archive_bytes([(bundle.MANIFEST, bundle._canonical_json(manifest).encode()), *files.items()])
    elif defect == "duplicate_json_key":
        raw = entries[0][1]
        raw = b'{"dataset_revision":"' + case.revision.encode() + b'",' + raw[1:]
        data = archive_bytes([(bundle.MANIFEST, raw), *files.items()])
    archive.write_bytes(data)
    destination = case.parent / "refused"
    assert import_local(case, archive, destination) == 2  # Real external SHA for the malicious bytes.
    assert not destination.exists() and not reservation(destination).exists()
    assert len(case.transport.calls) == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("defect", ["missing_sha", "wrong_sha", "bundle_link"])
def test_ci_input_bundle_external_anchor_and_regular_file_required(originals, capsys, defect):
    case = originals
    archive, destination = case.parent / "source.tar", case.parent / "refused"
    assert produce(case, archive) == 0
    capsys.readouterr()
    if defect == "missing_sha":
        with pytest.raises(SystemExit) as error:
            bundle.main(["import", "--bundle", str(archive), "--out", str(destination)])
        assert error.value.code == 2
    elif defect == "wrong_sha":
        assert import_local(case, archive, destination, "0" * 64) == 2
    else:
        os.link(archive, case.parent / "other-link.tar")
        assert import_local(case, archive, destination) == 2
    assert not destination.exists() and not reservation(destination).exists()
    assert len(case.transport.calls) == 1


@pytest.mark.parametrize("defect", ["parquet", "step0", "missing_reference", "linked_reference", "extra_reference"])
def test_ci_input_bundle_current_source_refusal(originals, defect):
    case = originals
    reference = next(case.references.rglob("*.txt"))
    if defect == "parquet":
        case.parquet.write_bytes(case.parquet.read_bytes() + b"drift")
    elif defect == "step0":
        case.step0.write_bytes(case.step0.read_bytes() + b" ")
    elif defect == "missing_reference":
        reference.unlink()
    elif defect == "linked_reference":
        real = case.parent / "linked-reference-original"
        reference.rename(real)
        reference.symlink_to(real)
    else:
        (case.references / ".env").write_bytes(b"synthetic-forbidden-file")
    output = case.parent / "refused.tar"
    assert produce(case, output) == 2
    assert len(case.transport.calls) == 1
    assert not output.exists() and not reservation(output).exists()


@pytest.mark.parametrize("operation", ["produce", "import"])
@pytest.mark.parametrize("existing", ["target", "reservation", "link"])
def test_ci_input_bundle_no_clobber_or_partial_adoption(originals, capsys, operation, existing):
    case = originals
    source = case.parent / "source.tar"
    assert produce(case, source) == 0
    capsys.readouterr()
    output = case.parent / "reserved-target"
    target = reservation(output) if existing == "reservation" else output
    if existing == "link":
        target.symlink_to(source)
    else:
        target.write_bytes(b"preserve existing bytes")
    before = source.read_bytes()
    assert (produce(case, output) if operation == "produce" else import_local(case, source, output)) == 2
    assert source.read_bytes() == before
    if existing != "link":
        assert target.read_bytes() == b"preserve existing bytes"
    assert len(case.transport.calls) == 1


@pytest.mark.parametrize("operation", ["produce", "import"])
def test_ci_input_bundle_first_write_failure_keeps_reservation(originals, monkeypatch, operation):
    case = originals
    source = case.parent / "source.tar"
    assert produce(case, source) == 0
    output = case.parent / "interrupted"
    writer = bundle._write_no_clobber

    def interrupted(path, data):
        writer(path, data)
        if path == reservation(output):
            raise OSError("synthetic interruption after reservation")

    monkeypatch.setattr(bundle, "_write_no_clobber", interrupted)
    invoke = lambda: produce(case, output) if operation == "produce" else import_local(case, source, output)
    assert invoke() == 2
    assert reservation(output).is_file() and not output.exists()
    calls = len(case.transport.calls)
    assert invoke() == 2
    assert len(case.transport.calls) == calls


def test_ci_input_bundle_installed_verifier_refuses_corrupt_partial(originals, monkeypatch):
    case = originals
    source, output = case.parent / "source.tar", case.parent / "partial"
    assert produce(case, source) == 0
    writer = bundle._write_no_clobber

    def corrupt(path, data):
        writer(path, data + b"drift" if path == output / bundle.STEP0 else data)

    monkeypatch.setattr(bundle, "_write_no_clobber", corrupt)
    assert import_local(case, source, output) == 2
    assert len(case.transport.calls) == 2 and case.transport.calls[-1].parquet == output / bundle.PARQUET
    assert (output / bundle.PARQUET).read_bytes() == case.files[bundle.PARQUET]
    assert reservation(output).exists() and not (output / bundle.READY).exists()
    assert import_local(case, source, output) == 2
    assert len(case.transport.calls) == 2
