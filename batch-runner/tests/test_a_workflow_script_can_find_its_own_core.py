"""A script under `scripts/` must be able to import `core` when run AS a script.

Why this exists
---------------
`.github/workflows/batch-run.yml` runs these files the plain way::

    cd batch-runner
    python3 scripts/relay_checkpoint.py verify-write --repo-id "$SOURCE_REPO"

When Python is handed a *file path*, it puts that file's own directory on
`sys.path[0]` -- so `sys.path[0]` becomes `batch-runner/scripts`, and
`batch-runner` itself is nowhere on the path. A bare `from core.x import y`
therefore dies at import time::

    ModuleNotFoundError: No module named 'core'

The unit tests never saw this. pytest's rootdir insertion puts `batch-runner`
on `sys.path`, so `import scripts.relay_checkpoint` resolves happily -- the
module is fine, the *invocation* is not. That gap let the defect reach `main`
and kill a paid batch run (33300827995) four minutes in, after Step 0 had
already duplicated a dataset on the Hub.

So this test does not import anything. It spawns the interpreter exactly the
way the workflow does and reads what comes back.

Deliberately NOT asserted: the exit code. Some of these scripts fail without
their required arguments, and `preflight_grading_renderer.py` exits non-zero
when LibreOffice is absent. Those are honest failures that say what they need.
A missing `core` is a different animal: the script never gets to speak at all.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BATCH_RUNNER_ROOT / "scripts"

# `core` is the only first-party package that lives beside `scripts/` rather
# than inside it, so it is the only one this invocation style can lose.
FIRST_PARTY_ROOT = "core"

REMEDY = (
    "Add the preamble its 12 siblings already carry, above the core imports:\n"
    "    BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]\n"
    "    if str(BATCH_RUNNER_ROOT) not in sys.path:\n"
    "        sys.path.insert(0, str(BATCH_RUNNER_ROOT))\n"
    "and mark the core imports `# noqa: E402`."
)


def _imports_core(path: Path) -> bool:
    """True if `path` has a module-level import of the `core` package.

    Parsed, not grepped: a `core.` inside a docstring, a comment, or a
    function-local import must not drag a file into this test.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not our concern here
        return False
    for node in tree.body:  # module level only
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and (node.module or "").split(".")[0] == FIRST_PARTY_ROOT:
                return True
        elif isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == FIRST_PARTY_ROOT for a in node.names):
                return True
    return False


def _core_importing_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS_DIR.glob("*.py") if _imports_core(p))


def test_the_discovery_actually_found_scripts() -> None:
    """Guard the guard: an empty sweep would make every case below vacuous."""
    found = _core_importing_scripts()
    assert len(found) >= 10, (
        f"expected the scripts/ directory to hold many core-importing scripts, "
        f"found {len(found)}: {[p.name for p in found]}"
    )


@pytest.mark.parametrize(
    "script", _core_importing_scripts(), ids=lambda p: p.name
)
def test_script_can_import_core_when_run_by_path(script: Path, monkeypatch) -> None:
    # PYTHONPATH must be absent, or it silently supplies what the script should
    # be supplying itself -- and the test would pass while the workflow fails.
    # (batch-run.yml sets no PYTHONPATH; that is why the defect was reachable.)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    # Credentials are scrubbed so a script that does real work on --help cannot
    # reach a provider from a unit test.
    for leaked in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "OPENAI_API_KEY",
                   "ANTHROPIC_API_KEY", "AZURE_OPENAI_API_KEY"):
        monkeypatch.delenv(leaked, raising=False)

    proc = subprocess.run(
        [sys.executable, f"scripts/{script.name}", "--help"],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = proc.stdout + proc.stderr

    assert f"No module named '{FIRST_PARTY_ROOT}'" not in output, (
        f"`cd batch-runner && python scripts/{script.name}` cannot import "
        f"`{FIRST_PARTY_ROOT}`.\n\n{REMEDY}\n\n--- what it printed ---\n{output[-2000:]}"
    )
