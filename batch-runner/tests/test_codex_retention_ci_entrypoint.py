"""Real script dispatch plus isolated identity predicates, never authorization."""

import ast
import json
from pathlib import Path
import runpy
import sys
from types import ModuleType

import pytest

import codex_retention_ci as adapter
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from .test_codex_budget_pilot import offline  # noqa: F401; unchanged live-boundary guards


def test_retention_script_entrypoint_uses_canonical_authority_types(monkeypatch, capsys, tmp_path):
    script = Path(adapter.__file__).resolve()
    source = script.read_text()
    canonical_footer = (
        'if __name__ == "__main__":\n'
        '    from codex_retention_ci import main as canonical_main\n\n'
        '    raise SystemExit(canonical_main())\n'
    )
    legacy_footer = 'if __name__ == "__main__":\n    raise SystemExit(main())\n'
    assert source.endswith(canonical_footer) and source.count(canonical_footer) == 1
    legacy_source = source[:-len(canonical_footer)] + legacy_footer
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("entrypoint regression crossed a live or private-input boundary")

    for owner, name in (
            (adapter.owned.LocalTransport, "__init__"), (adapter.owned.LocalTransport, "clock"),
            (adapter.LocalTransport, "github_job_token"), (adapter.LocalTransport, "authority_opener"),
            (adapter.LocalTransport, "github"), (adapter.LocalTransport, "azure"),
            (adapter.LocalTransport, "process"), (adapter.LocalTransport, "child"),
            (adapter.intake, "_response"), (adapter.retained, "_session"), (adapter.retained, "_lock"),
            (adapter._Admission, "admit"), (adapter._Admission, "finish"),
            (adapter, "verify_approval"), (adapter, "verify_job_origin"), (adapter, "_cli_request"),
            (adapter.registration, "compile_plan"), (adapter.preparation, "prepare_packet"),
            (adapter.preparation, "verify_packet"), (adapter.controller, "stage_runtime"),
            (adapter.controller, "verify_staged_runtime"), (adapter.controller, "_deadline"),
            (CodexTaskDeadlineStore, "__init__"), (CodexTaskDeadline, "admit_attempt")):
        monkeypatch.setattr(owner, name, forbidden)

    real_main = adapter.main
    entered = []

    def main_spy(argv=None):
        entered.append(real_main.__globals__)
        return real_main(argv)

    monkeypatch.setattr(adapter, "main", main_spy)
    invalid_source = ["--reviewed-source-sha", "not-a-source-sha"]
    false_flags = {"launch_authorized": False, "grading_launched": False}
    source_refusal = {"reason": "exact_reviewed_source_required", **false_flags}
    original_dunder_main = sys.modules["__main__"]

    # Undo only the footer in memory; execute the actual old __main__ definitions.
    legacy = ModuleType("__main__")
    legacy.__file__ = str(script)
    with monkeypatch.context() as old_script:
        old_script.setitem(sys.modules, "__main__", legacy)
        old_script.setattr(sys, "argv", [str(script), *invalid_source])
        with pytest.raises(SystemExit) as stopped:
            exec(compile(legacy_source, str(script), "exec"), legacy.__dict__)
    assert stopped.value.code == 2 and entered == []
    captured = capsys.readouterr()
    assert json.loads(captured.out) == source_refusal and captured.err == ""
    assert sys.modules["__main__"] is original_dunder_main
    for name in ("ExecutionGrantRequest", "RetentionCIRefused", "_Admission"):
        assert getattr(legacy, name) is not getattr(adapter, name)
        assert getattr(legacy, name).__module__ == "__main__"
        assert getattr(adapter, name).__module__ == "codex_retention_ci"

    # Isolate the exact production statement, not _context or an authorization verdict.
    execute = next(node for node in ast.parse(source).body
                   if isinstance(node, ast.FunctionDef) and node.name == "execute")
    reason = "retention_execution_grant_required"
    guards = [node for node in execute.body if isinstance(node, ast.Expr)
              and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
              and node.value.func.id == "require" and len(node.value.args) == 2
              and isinstance(node.value.args[1], ast.Constant) and node.value.args[1].value == reason]
    expected = ast.parse('require(type(grant) is ExecutionGrantRequest, "retention_execution_grant_required")').body[0]
    assert len(guards) == 1 and ast.dump(guards[0]) == ast.dump(expected)
    grant_guard = compile(ast.Module(body=guards, type_ignores=[]), str(script), "exec")
    fields = ("not-reviewed", "0" * 64, tmp_path / "unread-historical-root")
    canonical_grant = adapter.ExecutionGrantRequest(*fields)
    legacy_grant = legacy.ExecutionGrantRequest(*fields)
    exec(grant_guard, {**adapter.execute.__globals__, "grant": canonical_grant})
    with pytest.raises(adapter.RetentionCIRefused) as split_identity:
        exec(grant_guard, {**adapter.execute.__globals__, "grant": legacy_grant})
    assert type(split_identity.value) is adapter.RetentionCIRefused
    assert str(split_identity.value) == reason
    generic = {"reason": "retention_ci_verification_refused:RetentionCIRefused", **false_flags}
    assert legacy._refusal_payload(split_identity.value) == generic
    assert adapter._refusal_payload(split_identity.value) == {"reason": reason, **false_flags}

    class GrantSubclass(adapter.ExecutionGrantRequest):
        pass

    for invalid in (GrantSubclass(*fields), None, True, {"approved": True}, object()):
        with pytest.raises(adapter.RetentionCIRefused) as refused:
            exec(grant_guard, {**adapter.execute.__globals__, "grant": invalid})
        assert type(refused.value) is adapter.RetentionCIRefused and str(refused.value) == reason
        assert adapter._refusal_payload(refused.value) == {"reason": reason, **false_flags}
    private = "PRIVATE_ENTRYPOINT_SENTINEL"
    assert adapter._refusal_payload(legacy.RetentionCIRefused(private)) == generic

    # This real controller check precedes _context; neither case reaches admission.
    host = tmp_path / "never-admitted"
    legacy_admission = legacy._Admission(None, None, None, None, None, None)
    canonical_admission = adapter._Admission(None, None, None, None, None, None)
    with pytest.raises(adapter.controller.RetentionControllerRefused) as refused:
        adapter.controller._run_post_authority_cell(None, host_state=host, _admission=legacy_admission)
    assert str(refused.value) == adapter.controller.LIVE_GATE
    with pytest.raises(adapter.controller.RetentionControllerRefused) as refused:
        adapter.controller._run_post_authority_cell(None, host_state=host, _admission=canonical_admission)
    assert str(refused.value) == "explicit_retention_request_required"
    with pytest.raises(adapter.controller.RetentionControllerRefused) as refused:
        adapter.controller.execute_first_cell(None, host_state=host, grant=canonical_grant)
    assert str(refused.value) == "explicit_retention_request_required"

    # Actual runpy script entry calls through to the real canonical main, not a verdict stub.
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", private)
    for argv, expected_code in (
            (invalid_source, 2),
            (["--observe-locator", "--reviewed-source-sha", "a" * 40], 0)):
        assert real_main(argv) == expected_code
        imported_output = capsys.readouterr()
        with monkeypatch.context() as script_run:
            script_run.setattr(sys, "argv", [str(script), *argv])
            with pytest.raises(SystemExit) as stopped:
                runpy.run_path(str(script), run_name="__main__")
        assert stopped.value.code == expected_code
        script_output = capsys.readouterr()
        assert script_output == imported_output and script_output.err == ""
        payload = json.loads(script_output.out)
        assert payload["launch_authorized"] is False and payload["grading_launched"] is False
        if expected_code == 2:
            assert payload == source_refusal
        else:
            assert payload["reason"] == "github_job_issuance_locator_observation_only"
            assert payload["issuance_locator"]["checks"]["registered_route"] is False
        assert private not in script_output.out
        assert sys.modules["__main__"] is original_dunder_main
    assert len(entered) == 2 and all(namespace is adapter.__dict__ for namespace in entered)
    assert real_main.__globals__ is adapter.execute.__globals__
    for namespace in entered:
        for name in ("ExecutionGrantRequest", "RetentionCIRefused", "_Admission"):
            assert namespace[name] is getattr(adapter, name)
    assert effects == [] and not host.exists() and list(tmp_path.iterdir()) == []
