"""Public-safe opt-in checks, not private integration or input verification."""

import os
import subprocess

import pytest

from . import test_codex_retention_ci as private_integration
from .test_codex_budget_pilot import offline  # noqa: F401; unchanged process/network/SDK guards
from .test_codex_retention_ci import immutable_archives, private_retention_opt_in  # noqa: F401


@pytest.mark.parametrize("supplied", ["absent", "empty", "directory", "missing-file"])
def test_private_retention_opt_in_precedes_archive_setup(supplied, tmp_path, monkeypatch, request):
    variable = "GDPVAL_RETENTION_PREPARED_HANDOFF"
    if supplied == "absent":
        if variable in os.environ:
            monkeypatch.delenv(variable)
        outcome = pytest.skip.Exception
        reason = "explicit retained original-input handoff required; no fetch or synthetic pins"
    else:
        locator = {"empty": "", "directory": str(tmp_path),
                   "missing-file": str(tmp_path / "missing-handoff.json")}[supplied]
        monkeypatch.setenv(variable, locator)
        outcome = AssertionError
        reason = "required explicit private original-input handoff unavailable"
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("private opt-in gate reached archive, subprocess or preparation")

    monkeypatch.setattr(private_integration.historical, "materialize_archive", forbidden)
    monkeypatch.setattr(private_integration.preparation, "_read", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    # Resolve the actual archive fixture and its prerequisite through pytest.
    # No substitute archive or prepared input is supplied, even on absence.
    with pytest.raises(outcome, match="^" + reason + "$"):
        request.getfixturevalue("immutable_archives")
    assert calls == []
