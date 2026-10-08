"""One small real-pytest lifetime check; no observation or grader fixtures."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from textwrap import dedent
import xml.etree.ElementTree as ET

import yaml


def test_time_budget_failed_tmp_path_retention(tmp_path, record_property):
    root = Path(__file__).resolve().parents[2]
    workflow_bytes = (root / ".github/workflows/backend-tests.yml").read_bytes()
    option = b" -o tmp_path_retention_policy=failed"
    assert workflow_bytes.count(option) == 1
    # Undo only this option: all other jobs, guards and ceilings stay byte-identical.
    assert hashlib.sha256(workflow_bytes.replace(option, b"", 1)).hexdigest() == (
        "ff89fe6ffc6bfda1ed151fd8b4d6a49aeada28fd97b7a7271be45b9e943785f4"
    )
    job = yaml.safe_load(workflow_bytes)["jobs"]["time-budget-contracts"]
    assert job["timeout-minutes"] == 45
    run = next(step["run"] for step in job["steps"] if step["name"] == "Run time-budget contracts")
    assert run.splitlines()[0] == "cd batch-runner" and len(run.splitlines()) == 2
    argv = shlex.split(run.splitlines()[1])
    assert argv == ["python", "-m", "pytest", "-m", "not integration", "--tb=short", "-q", "-rs",
                    "-o", "tmp_path_retention_policy=failed", "tests/test_time_budget_*.py"]

    owned = tmp_path / "lifecycle"
    owned.mkdir(mode=0o700)
    suite, basetemp, sibling = owned / "suite", owned / "child-basetemp", owned / "sibling-source"
    suite.mkdir(mode=0o700)
    sibling.mkdir(mode=0o700)
    (sibling / "sentinel").write_bytes(b"untouched sibling source")
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    child = suite / "test_synthetic_lifetime.py"
    child.write_text(dedent('''\
        import json
        from pathlib import Path
        import pytest

        RECEIPT = Path(__file__).resolve().parent.parent / "case-paths.json"

        def record(name, value):
            data = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
            data[name] = value
            RECEIPT.write_text(json.dumps(data, sort_keys=True))

        @pytest.fixture(scope="session")
        def shared_source(tmp_path_factory):
            path = tmp_path_factory.mktemp("shared-source")
            (path / "sentinel").write_bytes(b"untouched factory source")
            record("factory_source", str(path))
            return path

        def test_passed(tmp_path, shared_source):
            record("passed", str(tmp_path))
            (tmp_path / "payload").write_bytes(b"passed synthetic payload")
            assert shared_source.is_dir()

        def test_failed(tmp_path, shared_source):
            passed = Path(json.loads(RECEIPT.read_text())["passed"])
            record("passed_removed_before_next_case", not passed.exists())
            record("failed", str(tmp_path))
            (tmp_path / "payload").write_bytes(b"failed synthetic payload")
            assert False, "intentional retention probe"
        '''), encoding="utf-8")
    junit = owned / "child-junit.xml"
    command = [sys.executable, "-m", "pytest", *argv[3:-1],
               "-c", str(suite / "pytest.ini"), "--rootdir", str(suite), "--confcutdir", str(suite),
               "--basetemp", str(basetemp), "-p", "no:cacheprovider", "--junitxml", str(junit),
               str(child) + "::test_passed", str(child) + "::test_failed"]
    result = subprocess.run(command, cwd=suite, check=False, capture_output=True, text=True, timeout=30,
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
             "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"})
    paths = json.loads((owned / "case-paths.json").read_text(encoding="utf-8"))
    for name in ("passed", "failed", "factory_source"):
        assert Path(paths[name]).parent == basetemp
    passed, failed, shared = (Path(paths[name]) for name in ("passed", "failed", "factory_source"))
    outcomes = {
        "passed_removed": not passed.exists(),
        "passed_removed_before_next_case": paths["passed_removed_before_next_case"],
        "failed_retained": failed.is_dir() and (failed / "payload").read_bytes() == b"failed synthetic payload",
        "factory_source_unchanged": shared.is_dir() and (shared / "sentinel").read_bytes() == b"untouched factory source",
        "sibling_source_unchanged": (sibling / "sentinel").read_bytes() == b"untouched sibling source",
    }
    child_cases = [{"name": case.attrib["name"],
                    "status": next((status for tag, status in
                                    (("error", "error"), ("failure", "failed"), ("skipped", "skipped"))
                                    if case.find(tag) is not None), "passed")}
                   for case in ET.parse(junit).getroot().iter("testcase")]
    receipt = {"owned_root": str(owned), "child_basetemp": str(basetemp), "case_paths": paths,
               "sibling_source": str(sibling), "workflow_command": argv, "child_command": command,
               "child_exit_code": result.returncode, "child_cases": child_cases, "outcomes": outcomes,
               "child_stdout": result.stdout, "child_stderr": result.stderr,
               "cleanup": "ordinary pytest tmp_path teardown only; no manual deletion"}
    receipt_path = owned / "lifecycle-receipt.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    record_property("lifecycle_receipt_path", str(receipt_path))
    record_property("lifecycle_receipt", json.dumps(receipt, sort_keys=True))
    assert result.returncode == 1, result.stdout + result.stderr
    assert child_cases == [{"name": "test_passed", "status": "passed"}, {"name": "test_failed", "status": "failed"}]
    assert "intentional retention probe" in result.stdout
    assert all(outcomes.values()), outcomes
