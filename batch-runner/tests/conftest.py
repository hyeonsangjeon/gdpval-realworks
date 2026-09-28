"""Immutable historical source bytes for explicitly requested legacy fixtures."""

import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


@pytest.fixture(scope="module")
def approved_pilot_source(tmp_path_factory):
    """Read immutable local Git data before the function-scoped process guard.

    Only fixture materialization uses Git. Compilation runs with the requesting
    test's existing process, network and credential guards installed.
    """
    approved_sha = "8ac891e3e0e4752fe15a00139a2691ddf9df7dce"
    archived = subprocess.run(
        ["git", "archive", "--format=tar", approved_sha, "batch-runner", ".github/workflows"],
        cwd=Path(__file__).resolve().parents[2], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1"},
    ).stdout
    source = tmp_path_factory.mktemp("native-approved-source")
    with tarfile.open(fileobj=io.BytesIO(archived), mode="r:") as snapshot:
        assert snapshot.pax_headers["comment"] == approved_sha
        assert all(
            not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
            and (member.isdir() or member.isfile()) for member in snapshot.getmembers()
        )
        snapshot.extractall(source)
    return source
