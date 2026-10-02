"""Current observer source checks must not rewrite historical paid evidence."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from . import test_codex_retention_grade_readout as old
from .test_codex_budget_pilot_retention import offline, TOKEN  # noqa: F401

reader, bridge, grade, pilot, output, retained = old.reader, old.bridge, old.grade, old.pilot, old.output, old.retained
FIRST_EVIDENCE = "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
KEEP_EVIDENCE = "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"


def test_current_observer_source_preserves_historical_grade_bindings(tmp_path, monkeypatch, capsys):
    fixed = bridge._fixed("retention/keep-r2")
    historical = deepcopy((bridge.RESULT, bridge.PARENT, bridge.READER, fixed.RESULT, fixed.PARENT, fixed.READER))
    assert bridge.fixed_evidence_sha256() == FIRST_EVIDENCE
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == KEEP_EVIDENCE
    assert fixed.RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    assert reader._fixed().selector == reader.SELECTOR and reader._fixed().grading_selector == bridge.SELECTOR
    assert set(fixed.READER_FILES.values()) <= set(reader.CURRENT_DEPENDENCIES)
    assert reader.CURRENT_DEPENDENCIES["codex_retention_first_cell.py"] == "ae5754bdd294a7560aecbe0d4c819bc6fdd123cf82fc652c6aedee5bae2701f7"
    assert reader.CURRENT_DEPENDENCIES["codex_retention_fresh_r1_result_intake.py"] == "d042c02228f2430d4129ed37b3fb453cf9792bbde269a28bd10c6daf8f00b900"
    assert fixed.READER["controller_sha256"] == "957934b869ed5071923add7e9554aa68de941c9488f3e6d650557d27f6179601"
    assert fixed.READER["module_sha256"] == "5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583"
    for name, expected in reader.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((bridge.ROOT / "batch-runner" / name).read_bytes()).hexdigest() == expected
    effects, git_calls, roots = [], [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        pytest.fail("observer reached a paid/live/input or premature private boundary")

    for owner, names in ((bridge, ("_authority", "prepare", "claim", "judge", "publish", "reconcile", "_derived_inputs")),
                         (grade, ("prepare", "claim", "judge", "publish", "reconcile", "_owned_judge")),
                         (pilot, ("dispatch",)), (old.step8, ("main",)), (bridge.reader, ("read_result",))):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setattr("core.tools.get_renderer_fingerprint", forbidden)
    monkeypatch.setattr(old.RubricLoader, "load", forbidden)
    common = tmp_path / "git-common"
    common.mkdir()
    state = {"head": old.OBSERVER, "diff": b"", "status": b"", "config": b"", "top": bridge.ROOT}

    def git(path, *command, ok=(0,)):
        assert Path(path) == bridge.ROOT
        git_calls.append(command)
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(state["top"]) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (state["head"] + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): state["diff"],
            ("status", "--porcelain", "--untracked-files=normal"): state["status"],
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): state["config"]}
        assert command in answers, "only Git metadata transport is simulated, not source guards"
        return SimpleNamespace(stdout=answers[command], returncode=0)

    monkeypatch.setattr(old.source_checkout, "_git", git)
    monkeypatch.setattr(pilot, "_git", git)
    for selector in (reader.SELECTOR, reader.KEEP_R2_SELECTOR):
        reader._source_current(old.OBSERVER, selector=selector)
    # Paid validation deliberately retains historical dependencies. A consumed
    # keep/r2 grade cannot be replayed by treating current bytes as its old ones.
    bridge._source(bridge.compile_request(old.OBSERVER))
    with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_reader_required$"):
        bridge._source(bridge.compile_request(old.OBSERVER, selector=fixed.SELECTOR))

    def invoke(api=None, *, selector=reader.KEEP_R2_SELECTOR, root=None):
        old._environment(monkeypatch, selector=selector)
        profile = reader._fixed(selector)
        root = root or tmp_path / ("observer-" + str(len(roots)))
        roots.append(root)
        code = grade.main(["--selector", selector, "--phase", "readout", "--reviewed-source-sha", old.OBSERVER,
            "--terminal-revision", profile.terminal, "--producer-source-sha", "", "--root", str(root)], _test_api=api)
        captured = capsys.readouterr()
        result = json.loads(captured.out if code == 0 else captured.err)
        for secret in (TOKEN, old.PRIVATE, str(tmp_path), retained._target()):
            assert secret not in captured.out + captured.err
        return code, result

    # Actual current-byte mismatches, not changes to expected pins/context.
    real_bytes = output._bytes
    for filename in reader.CURRENT_DEPENDENCIES:
        for missing in (False, True):
            with monkeypatch.context() as bad:
                def changed(path, **kwargs):
                    if Path(path).name == filename:
                        if missing:
                            raise FileNotFoundError("synthetic missing dependency")
                        return real_bytes(path, **kwargs) + b"\n"
                    return real_bytes(path, **kwargs)
                bad.setattr(output, "_bytes", changed)
                bad.setattr(grade, "_root", forbidden)
                bad.setattr(retained, "_session", forbidden)
                reason = ("reviewed_retention_grade_adapter_required" if filename == "codex_retention_keep_r2_grade.py"
                          else "reviewed_retention_observer_dependency_required")
                with pytest.raises(FileNotFoundError if missing else output.OutputPublicationRefused,
                                   match="^synthetic missing dependency$" if missing else "^" + reason + "$"):
                    reader._source_current(old.OBSERVER, selector=reader.KEEP_R2_SELECTOR)
                # main reaches _fixed before source_preflight for adapter bytes.
                if filename != "codex_retention_keep_r2_grade.py":
                    code, result = invoke()
                    assert code == 2 and result["stage"] == "source_preflight" and not roots[-1].exists()
    for key, value, reason in (("head", "e" * 40, "retention_grade_source_changed"),
            ("diff", b"tracked.py\n", "retention_grade_source_changed"),
            ("status", b"?? untracked.py\n", "clean_retention_grade_source_required"),
            ("config", b"include.path\n", "checkout filters, includes or partial-clone configuration are unsupported"),
            ("top", tmp_path, "an explicit repository top-level path is required")):
        saved = state[key]
        state[key] = value
        with monkeypatch.context() as denied:
            denied.setattr(grade, "_root", forbidden)
            denied.setattr(retained, "_session", forbidden)
            with pytest.raises(ValueError, match="^" + reason + "$"):
                reader._source_current(old.OBSERVER)
            code, result = invoke()
            assert code == 2 and result["stage"] == "source_preflight" and not roots[-1].exists()
        state[key] = saved
    with monkeypatch.context() as before_import:
        before_import.setattr(bridge, "_fixed", forbidden)
        before_import.setattr(output, "_bytes", lambda path, **kwargs: real_bytes(path, **kwargs) + b"\n")
        with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_grade_adapter_required$"):
            reader._source_current(old.OBSERVER, selector=reader.KEEP_R2_SELECTOR)
    assert effects == []

    # Both numeric readouts use current source checks but canonical historical
    # writer contexts. Keep the omitted parent verifier's default unchanged.
    for selector in (reader.SELECTOR, reader.KEEP_R2_SELECTOR):
        profile = reader._fixed(selector)
        adapter = bridge._fixed(profile.grading_selector)
        context = bridge.compile_request(profile.writer_source, selector=profile.grading_selector)
        template = old._fixture(context, selector=selector)
        with monkeypatch.context() as synthetic:
            api = old._seed(synthetic, *deepcopy(template), selector=selector)
            before = deepcopy((api.trees, api.writers, api.branches))
            code, result = invoke(api, selector=selector)
            assert code == 0 and result["outcome"] == "verified_writer_recorded_grade", result
            assert result["fixed_evidence_sha256"] == (FIRST_EVIDENCE if selector == reader.SELECTOR else KEEP_EVIDENCE)
            assert result["intake_sha256"] == adapter.RESULT["intake_sha256"]
            assert result["original_result_fingerprint"] == adapter.RESULT["result"]["result_fingerprint"]
            assert result["score"]["pct"] == 50 and result["ledger_derived_cost"]["model_calls"] == 1
            assert result["ledger_derived_cost"]["known_cost_usd"] is None
            assert result["materialized_input_fingerprint"]["status"] == "unavailable"
            assert result["invoice_complete"] is False and result["http_request_count"] is None
            assert roots[-1].stat().st_mode & 0o777 == 0o700 and len(api.downloads) == 5
            assert (api.trees, api.writers, api.branches) == before and not api.commits
            calls = list(api.calls)
            assert invoke(api, selector=selector, root=roots[-1])[0] == 2 and api.calls == calls

        for field, value in (("source_sha", "e" * 40), ("github_run", {**profile.writer_run, "id": "1"}),
                ("intake_sha256", "0" * 64), ("fixed_evidence_sha256", "0" * 64), ("cell_id", "unregistered")):
            terminal = deepcopy(template[0])
            terminal["binding"][field] = value
            with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_readout_writer_binding_mismatch$"):
                reader._terminal_contract(context, terminal, selector=selector)
        for fault in ("terminal_revision", "claim_source", "claim_history", "ledger_identity"):
            terminal, claim, payload, ledger = deepcopy(template)
            if fault == "terminal_revision":
                terminal["claim_commit"] = adapter.RESULT["terminal_commit"]
            elif fault == "claim_source":
                claim = deepcopy(claim)
                claim["binding"]["source_sha"] = "e" * 40
                terminal["claim_identity"] = pilot._identity(retained._encoded(claim))
            elif fault == "ledger_identity":
                row = json.loads(ledger)
                row["run_id"] = "foreign|ledger"
                ledger = old.base._json(row)
                payload["cost_ledger"]["sha256"] = hashlib.sha256(ledger).hexdigest()
            with monkeypatch.context() as synthetic:
                api = old._seed(synthetic, terminal, claim, payload, ledger, selector=selector)
                if fault == "claim_history":
                    api.writers[profile.claim][adapter.CLAIM_PATH] = adapter.PARENT["revision"]
                code, result = invoke(api, selector=selector)
                assert code == 2 and result["stage"] == ("grade_payload" if fault == "ledger_identity" else "grade_terminal")
                assert not api.commits
                if fault != "ledger_identity":
                    assert all(name in (adapter.TERMINAL_PATH, adapter.CLAIM_PATH) for _, name in api.downloads)

        if selector == reader.SELECTOR:
            with monkeypatch.context() as synthetic:
                terminal, claim, payload, ledger = deepcopy(template)
                api = old._seed(synthetic, terminal, claim, payload, ledger)
                # Authored synthetic control identities only. Historical source,
                # run, result, evidence and all production dictionaries stay fixed.
                synthetic.setattr(fixed, "PARENT", {**fixed.PARENT,
                    "terminal_identity": pilot._identity(retained._encoded(terminal)),
                    "claim_identity": pilot._identity(retained._encoded(claim))})
                monkeypatch.setenv("HF_TOKEN", TOKEN)
                with retained._session(api) as (server, token, deadline):
                    controls = fixed.parent_controls(server, server.repo, grade._cache(tmp_path, "parent-controls"), token, deadline)
                assert len(controls) == 2 and len(api.downloads) == 3 and not api.commits
                assert {name for _, name in api.downloads} == {bridge.TERMINAL_PATH, bridge.CLAIM_PATH}

    assert effects == [] and historical == (bridge.RESULT, bridge.PARENT, bridge.READER, fixed.RESULT, fixed.PARENT, fixed.READER)
    assert bridge.fixed_evidence_sha256() == FIRST_EVIDENCE
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == KEEP_EVIDENCE
    print("OFFLINE observer: exact CURRENT bytes/source before effects, historical 1ced/25d evidence unchanged, both fixed readouts and omitted parent controls, identity/history/ledger refusals; no live effects")
