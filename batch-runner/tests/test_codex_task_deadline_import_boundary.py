"""Cold config validation must not require host publication/backend SDKs."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", [
    "legacy", "legacy_codex", "deadline", "invalid_repetition", "invalid_timeout",
])
def test_deadline_config_without_publication_sdk_cold_process(case):
    # A fresh interpreter prevents the installed backend or another test's
    # imports from masking the lightweight configuration boundary.
    program = r'''
        import os
        import socket
        import subprocess
        import sys
        from pathlib import Path

        sys.dont_write_bytecode = True
        batch = Path(sys.argv[1])
        sys.path.insert(0, str(batch))
        case = sys.argv[2]
        unavailable = ("core.hf_publication", "huggingface_hub")
        attempted = []
        assert not any(name in sys.modules for name in unavailable)

        class UnavailableImports:
            def find_spec(self, fullname, path=None, target=None):
                if any(fullname == name or fullname.startswith(name + ".")
                       for name in unavailable):
                    attempted.append(fullname)
                    raise ModuleNotFoundError("intentionally unavailable: " + fullname,
                                              name=fullname)

        sys.meta_path.insert(0, UnavailableImports())

        def forbidden(*args, **kwargs):
            raise AssertionError("config validation crossed an execution boundary")

        socket.socket.connect = socket.socket.connect_ex = forbidden
        socket.create_connection = socket.getaddrinfo = forbidden
        subprocess.Popen = os.system = forbidden

        from core.experiment_config import ExperimentConfig

        template = ("exp998_smoke_baseline_sample.yaml" if case == "legacy"
                    else "exp035_codex_foundry_full220.yaml")
        config = ExperimentConfig.from_yaml(batch / "experiments" / template)
        if case not in {"legacy", "legacy_codex"}:
            document = config.to_dict()
            document["experiment"]["id"] = "exp_deadline_import_test"
            document["execution"]["codex"]["task_deadline"] = {
                "condition": "B", "repetition": 1,
            }
            if case == "invalid_repetition":
                document["execution"]["codex"]["task_deadline"]["repetition"] = True
            elif case == "invalid_timeout":
                document["execution"]["timeout"] = 1801
            config = ExperimentConfig.from_dict(document)
        errors = config.validate()
        if case == "invalid_repetition":
            assert "task_deadline requires repetition 1 or 2" in errors
        elif case == "invalid_timeout":
            assert any("task_deadline requires its fixed Codex attempt controls" in error
                       for error in errors)
        else:
            assert errors == [], errors
        assert attempted == [], attempted
        assert not any(name in sys.modules for name in unavailable)
        print("cold config boundary: " + case)
    '''
    result = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(program),
         str(Path(__file__).resolve().parents[1]), case],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cold config boundary: " + case
