from __future__ import annotations

import hashlib

from tests import test_agentic_v2_microvm_backend as microvm_fixtures


def test_overwritten_transcript_bytes_are_excluded_but_clean_records_survive(
    tmp_path, monkeypatch
):
    backend = microvm_fixtures._backend(
        tmp_path,
        launcher=microvm_fixtures.Launcher(
            stdout="original stdout\n", stderr="original stderr\n"
        ),
    )
    assert backend.start(60.0)["ok"] is True
    originals = {}
    hashes_at_creation = []
    for call_number in range(2):
        assert backend.exec_run(microvm_fixtures._ok())["ok"] is True
        output_files = backend.boots[call_number]["output_files"]
        assert set(output_files["kept"]) == {"stdout", "stderr", "meta.json"}
        hashes_at_creation.append(dict(output_files.get("sha256") or {}))
        for leaf in output_files["kept"]:
            relative = f"{output_files['directory']}/{leaf}"
            originals[relative] = (backend.work / relative).read_bytes()

    overwritten = f"{backend.boots[0]['output_files']['directory']}/stdout"
    source = backend.work / overwritten
    source.write_bytes(originals[overwritten].swapcase())
    read_bytes = backend._read_bytes

    def read_then_restore(relative):
        content = read_bytes(relative)
        if relative == overwritten:
            source.write_bytes(originals[relative])
        return content

    monkeypatch.setattr(backend, "_read_bytes", read_then_restore)
    backend.close()

    assert backend.closed is True
    assert not backend.work.exists()
    assert not (backend.root / overwritten).exists()
    expected_files = {
        relative: content
        for relative, content in originals.items()
        if relative != overwritten
    }
    assert set(backend.exec_records_carried) == set(expected_files)
    assert {
        relative: (backend.root / relative).read_bytes()
        for relative in expected_files
    } == expected_files
    expected_reason = f"{overwritten}: transcript_sha256_mismatch"
    assert backend.exec_records_not_carried == expected_reason
    for call_number, record in enumerate(backend.boots):
        output_files = record["output_files"]
        assert hashes_at_creation[call_number] == {
            leaf: hashlib.sha256(
                originals[f"{output_files['directory']}/{leaf}"]
            ).hexdigest()
            for leaf in output_files["kept"]
        }

    carried_before_repeat = list(backend.exec_records_carried)
    backend.close()
    assert backend.exec_records_carried == carried_before_repeat
    assert backend.exec_records_not_carried == expected_reason
    assert not backend.work.exists()
