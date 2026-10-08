"""Tiny real Git/pytest lifecycle proof; no captured bundle or live readout."""

import json
import os
from pathlib import Path
import subprocess
import sys
from textwrap import dedent
import xml.etree.ElementTree as ET


def test_time_budget_readout_worktree_registration_lifetime(tmp_path_factory, record_property):
    root = Path(__file__).resolve().parents[1]
    owned = tmp_path_factory.mktemp("readout-registration-lifetime")
    suite = owned / "suite"
    suite.mkdir()
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    child = suite / "test_registration_lifetime.py"
    child.write_text(
        f"import sys\nsys.path[:0] = {[str(root), str(root / 'tests')]!r}\n" + dedent('''\
        import json
        from pathlib import Path
        import subprocess
        import time
        from types import SimpleNamespace
        import pytest
        import test_time_budget_result_readout as readout

        RECEIPT = Path(__file__).resolve().parent.parent / "registration-receipt.json"

        def record(**values):
            data = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
            data.update(values)
            RECEIPT.write_text(json.dumps(data, sort_keys=True, indent=2) + "\\n")

        @pytest.fixture(scope="module")
        def source_repository(tmp_path_factory):
            workspace = tmp_path_factory.mktemp("readout-ordinary-bootstrap")
            sibling = tmp_path_factory.mktemp("sibling-source")
            (workspace / "sentinel").write_bytes(b"shared source unchanged")
            (sibling / "sentinel").write_bytes(b"sibling unchanged")
            deadline = time.monotonic() + 30
            readout._git(workspace, "init", "--quiet", "-b", "fixture-main", deadline=deadline)
            readout._git(workspace, "add", "sentinel", deadline=deadline)
            readout._git(workspace, "commit", "--quiet", "-m", "Synthetic source", deadline=deadline)
            sha = readout._git(workspace, "rev-parse", "HEAD", deadline=deadline)
            tree = readout._git(workspace, "rev-parse", "HEAD^{tree}", deadline=deadline)
            readout._git(workspace, "branch", "fixture-kept", sha, deadline=deadline)
            refs = readout._git(workspace, "show-ref", "--heads", deadline=deadline)
            record(workspace=str(workspace), sibling=str(sibling), head=sha, tree=tree, branches=refs)
            return SimpleNamespace(workspace=workspace, sha=sha, tree=tree, sibling=sibling, refs=refs)

        def test_failed_worktree_is_retained(source_repository, tmp_path, monkeypatch):
            source = readout.source.__wrapped__(source_repository, tmp_path, monkeypatch)
            (source.root / "failed-payload").write_bytes(b"failed worktree unchanged")
            record(failed_tmp_path=str(tmp_path), failed_root=str(source.root))
            assert False, "intentional failed-worktree retention probe"

        @pytest.mark.parametrize("phase", ["passed", "reuse"])
        def test_time_budget_worktree_registration_reuse(source_repository, tmp_path, monkeypatch, phase):
            repository = source_repository
            root = tmp_path / "runner-temp" / readout.subject.SOURCE_BASENAME
            if phase == "passed":
                source = readout.source.__wrapped__(repository, tmp_path, monkeypatch)
                record(passed_tmp_path=str(tmp_path), passed_root=str(source.root))
                assert (source.root / "sentinel").read_bytes() == b"shared source unchanged"
                return

            data = json.loads(RECEIPT.read_text())
            assert str(tmp_path) == data["passed_tmp_path"] and str(root) == data["passed_root"]
            assert not root.exists()
            record(same_path_reused=True, passed_directory_removed=True)
            deadline = time.monotonic() + 30
            before = readout._git(repository.workspace, "worktree", "list", "--porcelain", deadline=deadline)
            assert "worktree " + str(root) + "\\n" in before
            root.parent.mkdir()
            with pytest.raises(subprocess.CalledProcessError) as failure:
                readout._git(repository.workspace, "worktree", "add", "--quiet", "--detach",
                             str(root), repository.sha, deadline=deadline)
            record(stale_registration={"exit_code": failure.value.returncode, "stderr": failure.value.stderr,
                                       "stdout": failure.value.output, "registrations_before": before})
            assert failure.value.returncode == 128
            assert "already registered worktree" in failure.value.stderr
            assert not root.exists() and not list(root.parent.iterdir())
            root.parent.rmdir()
            assert not root.exists() and not root.parent.exists()

            calls, original_git = [], readout._git
            def observed_git(workspace, *arguments, deadline):
                assert workspace == repository.workspace and workspace.parent == tmp_path.parent
                calls.append({"arguments": list(arguments), "deadline": deadline})
                return original_git(workspace, *arguments, deadline=deadline)
            with monkeypatch.context() as observe:
                observe.setattr(readout, "_git", observed_git)
                source = readout.source.__wrapped__(repository, tmp_path, observe)
            assert [call["arguments"] for call in calls] == [
                ["worktree", "prune", "--expire", "now"],
                ["worktree", "add", "--quiet", "--detach", str(root), repository.sha]]
            assert calls[0]["deadline"] == calls[1]["deadline"]
            failed_root = Path(data["failed_root"])
            after = readout._git(repository.workspace, "worktree", "list", "--porcelain", deadline=deadline)
            checks = {
                "re_registered_same_path": source.root == root and root.is_dir(),
                "failed_worktree_preserved": (failed_root / "failed-payload").read_bytes() == b"failed worktree unchanged",
                "failed_registration_preserved": "worktree " + str(failed_root) + "\\n" in after,
                "shared_source_preserved": (repository.workspace / "sentinel").read_bytes() == b"shared source unchanged",
                "sibling_preserved": (repository.sibling / "sentinel").read_bytes() == b"sibling unchanged",
                "head_preserved": readout._git(repository.workspace, "rev-parse", "HEAD", deadline=deadline) == repository.sha,
                "tree_preserved": readout._git(repository.workspace, "rev-parse", "HEAD^{tree}", deadline=deadline) == repository.tree,
                "branches_preserved": readout._git(repository.workspace, "show-ref", "--heads", deadline=deadline) == repository.refs,
                "failed_head_preserved": readout._git(failed_root, "rev-parse", "HEAD", deadline=deadline) == repository.sha,
                "new_head_matches": readout._git(root, "rev-parse", "HEAD", deadline=deadline) == repository.sha,
            }
            record(corrected_fixture_calls=calls, registrations_after=after, checks=checks)
            assert all(checks.values()), checks
        '''), encoding="utf-8")
    junit = owned / "child-junit.xml"
    command = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-o", "tmp_path_retention_policy=failed",
               "-c", str(suite / "pytest.ini"), "--rootdir", str(suite), "--confcutdir", str(suite),
               "--basetemp", str(owned / "child-basetemp"), "-p", "no:cacheprovider", "--junitxml", str(junit),
               str(child) + "::test_failed_worktree_is_retained",
               str(child) + "::test_time_budget_worktree_registration_reuse[passed]",
               str(child) + "::test_time_budget_worktree_registration_reuse[reuse]"]
    result = subprocess.run(command, cwd=suite, check=False, capture_output=True, text=True, timeout=30,
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
             "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "HF_HUB_OFFLINE": "1",
             "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"})
    receipt_path = owned / "registration-receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    receipt.update(child_command=command, child_exit_code=result.returncode,
                   child_stdout=result.stdout, child_stderr=result.stderr)
    receipt["child_cases"] = [{"name": case.attrib["name"], "status": next(
        (status for tag, status in (("error", "error"), ("failure", "failed"), ("skipped", "skipped"))
         if case.find(tag) is not None), "passed")} for case in ET.parse(junit).getroot().iter("testcase")] if junit.exists() else []
    receipt["failed_directory_exists_after_child"] = bool(receipt.get("failed_root")) and Path(receipt["failed_root"]).is_dir()
    receipt["reused_passed_directory_removed_after_child"] = bool(receipt.get("passed_root")) and not Path(receipt["passed_root"]).exists()
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    record_property("registration_receipt_path", str(receipt_path))
    record_property("registration_receipt", json.dumps(receipt, sort_keys=True))
    assert result.returncode == 1, result.stdout + result.stderr
    assert receipt["child_cases"] == [
        {"name": "test_failed_worktree_is_retained", "status": "failed"},
        {"name": "test_time_budget_worktree_registration_reuse[passed]", "status": "passed"},
        {"name": "test_time_budget_worktree_registration_reuse[reuse]", "status": "passed"}]
    assert "intentional failed-worktree retention probe" in result.stdout
    assert receipt["stale_registration"]["exit_code"] == 128
    assert all(receipt["checks"].values())
    assert receipt["failed_directory_exists_after_child"]
    assert receipt["reused_passed_directory_removed_after_child"]
