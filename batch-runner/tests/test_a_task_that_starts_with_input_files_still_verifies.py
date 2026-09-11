"""A task whose workspace is not empty at the start must survive verification.

Staging reference files into the workspace broke every task that used it, and
it broke them in the worst available way: after the work was done. The model
read its inputs, wrote its deliverable and committed an answer, and then
:func:`verify_agentic_v2_result` threw the whole thing away with ``agentic v2
initial fixture state mismatch``. The record called it ``runner_internal_error``
and kept no files. A paid run would have been charged for every one of those
tasks and scored as though the model had produced nothing.

Two separate causes, and both are guarded here.

*The replay modelled every workspace as starting empty.* There was no way to say
otherwise, so the startup digest could never agree with a backend that had files
in it. The fix is a declaration in the ``started`` event, and the tests below
pin what it may contain -- digests and sizes, never bytes, because the inputs run
to hundreds of megabytes and a trace is not a file store.

*The modes disagreed.* The replay models every directory as 0o700 and every
file as 0o600; ``Path.mkdir(mode=..., parents=True)`` applies its mode to the
last component only, and ``mkdir(exist_ok=True)`` ignores it entirely for a
directory somebody else already made. A tree that is 0o755 halfway down is a
different digest and the same rejection, reached by a route that looks nothing
like a permissions problem. There is a test per route because each was found
separately and each can come back separately.

A third thing is checked and is not a bug: a task that names no files must still
get the guide. The model's standing instructions send it to ``inputs/INPUTS.md``
first, and one failed tool call ends a task outright, so skipping the guide for
those tasks killed 95 of the 220 on turn one -- as a model failure, in the
record. The guide is unconditional now and this file holds it that way. How many
tasks that is is counted from the catalogue in
``tests/test_agentic_v2_reference_staging.py``, because the figure was written
down by hand first and was wrong by fifty.

Nothing here calls a model or spends anything.
"""

from __future__ import annotations

import hashlib
import stat
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core import agentic_v2_provenance as provenance  # noqa: E402
from core.agentic_v2_contract import AgenticV2Profile  # noqa: E402
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend  # noqa: E402
from core.agentic_v2_reference_staging import (  # noqa: E402
    MODEL_INPUT_PREFIX,
    stage_task_reference_files,
)

TEXT = b"a readable input file\n"
BINARY = b"\x89PNG\r\n\x1a\n\xff\xfe\x00not text"
CAPS = {"tool_calls": 32, "wall_seconds": 1200}


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    folder = root / "reference_files" / "abc123"
    folder.mkdir(parents=True)
    (folder / "notes.txt").write_bytes(TEXT)
    (folder / "logo.png").write_bytes(BINARY)
    return root


def _stage(snapshot: Path, work: Path, *names: str) -> None:
    stage_task_reference_files(
        task_id="t",
        reference_files=list(names),
        snapshot_root=snapshot,
        into=work / MODEL_INPUT_PREFIX,
        render_text=True,
    )


def _backend(root: Path) -> AgenticV2FixtureBackend:
    return AgenticV2FixtureBackend(
        root=root,
        profile=AgenticV2Profile(
            policy_profile_id="offline-full-v1",
            tool_contract_version="2.0",
            foundation_only=True,
        ),
        budget_caps=CAPS,
    )


def _started_payload(declaration) -> dict:
    payload = {
        "run_id": "r",
        "condition": "c",
        "task_id": "t",
        "backend_identity": {
            "backend_id": "x",
            "foundation_only": True,
            "implementation_sha256": "0" * 64,
        },
        "capabilities": {},
        "policy_profile_id": "offline-full-v1",
        "runtime": {
            "substrate_manifest_sha256": "0" * 64,
            "package_snapshot_sha256": "0" * 64,
            "browser_build_sha256": "0" * 64,
            "budget_caps": CAPS,
        },
    }
    if declaration:
        payload["initial_workspace"] = declaration
    return payload


def _real_started_payload(backend, declaration) -> dict:
    """The payload the runner would build, taken from the backend's own startup.

    Hand-writing one is fine for the ledger, which only reads a few fields, and
    no good for :func:`_valid_started_payload`, which re-derives the identity
    and would reject a stand-in for reasons that have nothing to do with what
    is being tested here.
    """
    startup = backend.start(30.0)
    data = startup["data"]
    payload = {
        "run_id": "r",
        "condition": "c",
        "task_id": "t",
        "backend_identity": dict(data["backend_identity"]),
        "capabilities": dict(data["capabilities"]),
        "policy_profile_id": backend.profile.policy_profile_id,
        "runtime": {
            "substrate_manifest_sha256": data["substrate_manifest"]["sha256"],
            "package_snapshot_sha256": data["package_snapshot_sha256"],
            "browser_build_sha256": data["browser_build_sha256"],
            "budget_caps": dict(backend.budget_caps),
        },
    }
    if declaration:
        payload["initial_workspace"] = declaration
    return payload


def _modelled_digest(payload) -> str:
    return provenance._fixture_state_sha256(
        provenance._new_fixture_semantic_ledger(payload)
    )


# --------------------------------------------------------------------------
# The digest the replay computes has to be the digest the backend reports.
# --------------------------------------------------------------------------


def test_a_staged_workspace_verifies_against_the_state_the_backend_reports(
    snapshot, tmp_path
):
    """The whole point. Everything else in this file is a way this can fail."""
    root = tmp_path / "task"
    _stage(snapshot, root / "work", "reference_files/abc123/notes.txt")
    backend = _backend(root)
    try:
        payload = _started_payload(backend.initial_workspace_declaration())
        assert backend.state_sha256() == _modelled_digest(payload)
    finally:
        backend.close()


def test_an_empty_workspace_declares_nothing_and_still_verifies(tmp_path):
    """Every record written before the declaration existed must still verify.

    The declaration is emitted only when the workspace has something in it, so
    a run from before this change is not a run with a missing field.
    """
    backend = _backend(tmp_path / "task")
    try:
        assert backend.initial_workspace_declaration() == []
        assert backend.state_sha256() == _modelled_digest(_started_payload([]))
    finally:
        backend.close()


def test_a_work_root_someone_else_created_is_taken_back_to_0700(tmp_path):
    """Staging makes ``work/`` before the backend is built.

    ``mkdir(mode=0o700, exist_ok=True)`` does nothing to a directory that is
    already there, so the umask's 0o755 survived into the state digest and
    disagreed with the replay, which models this root as 0o700.
    """
    root = tmp_path / "task"
    (root / "work").mkdir(parents=True)
    (root / "work").chmod(0o755)

    backend = _backend(root)
    try:
        mode, _, _ = backend._workspace_snapshot()
        assert stat.S_IMODE(mode) == 0o700
    finally:
        backend.close()


def test_every_directory_staging_creates_is_0700_and_every_file_0600(
    snapshot, tmp_path
):
    """Including the ones ``parents=True`` creates on the way down.

    ``inputs/reference_files/`` and ``inputs/extracted/`` are intermediate
    components, so they took the umask while their leaves took the mode. The
    leaves are the ones anybody looks at.
    """
    work = tmp_path / "task" / "work"
    _stage(
        snapshot,
        work,
        "reference_files/abc123/notes.txt",
        "reference_files/abc123/logo.png",
    )

    wrong = {
        str(path.relative_to(work)): oct(stat.S_IMODE(path.lstat().st_mode))
        for path in work.rglob("*")
        if stat.S_IMODE(path.lstat().st_mode)
        != (0o700 if path.is_dir() else 0o600)
    }

    assert wrong == {}
    assert (work / MODEL_INPUT_PREFIX / "reference_files").is_dir()


# --------------------------------------------------------------------------
# What the declaration is allowed to say.
# --------------------------------------------------------------------------


def test_the_declaration_carries_digests_and_never_bytes(snapshot, tmp_path):
    root = tmp_path / "task"
    _stage(snapshot, root / "work", "reference_files/abc123/notes.txt")
    backend = _backend(root)
    try:
        declaration = backend.initial_workspace_declaration()
    finally:
        backend.close()

    files = [one for one in declaration if one["kind"] == "file"]
    directories = [one for one in declaration if one["kind"] == "directory"]

    assert directories and files
    assert all(set(one) == {"path", "kind"} for one in directories)
    assert all(
        set(one) == {"path", "kind", "sha256", "size", "decodes_as_utf8"}
        for one in files
    )
    staged = next(one for one in files if one["path"].endswith("notes.txt"))
    assert staged["sha256"] == hashlib.sha256(TEXT).hexdigest()
    assert staged["size"] == len(TEXT)


def test_the_declaration_says_which_files_a_read_could_open(snapshot, tmp_path):
    """A digest cannot tell the replay whether a read should have worked.

    Without this field a backend that reported every input as unreadable would
    be believed, and "the model was given nothing it could open" would verify
    exactly as cleanly as the truth.
    """
    root = tmp_path / "task"
    _stage(
        snapshot,
        root / "work",
        "reference_files/abc123/notes.txt",
        "reference_files/abc123/logo.png",
    )
    backend = _backend(root)
    try:
        declaration = backend.initial_workspace_declaration()
    finally:
        backend.close()

    readable = {
        one["path"]: one["decodes_as_utf8"]
        for one in declaration
        if one["kind"] == "file"
    }
    assert readable["inputs/reference_files/abc123/notes.txt"] is True
    assert readable["inputs/reference_files/abc123/logo.png"] is False


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param("inputs", id="not a list"),
        pytest.param([{"path": "a", "kind": "socket"}], id="unknown kind"),
        pytest.param(
            [{"path": "a", "kind": "directory", "mode": 448}],
            id="directory with an extra key",
        ),
        pytest.param(
            [{"path": "a", "kind": "file", "sha256": "0" * 64, "size": 1}],
            id="file missing whether it decodes",
        ),
        pytest.param(
            [
                {
                    "path": "a",
                    "kind": "file",
                    "sha256": "nope",
                    "size": 1,
                    "decodes_as_utf8": True,
                }
            ],
            id="digest is not a digest",
        ),
        pytest.param(
            [
                {
                    "path": "a",
                    "kind": "file",
                    "sha256": "0" * 64,
                    "size": -1,
                    "decodes_as_utf8": True,
                }
            ],
            id="negative size",
        ),
        pytest.param(
            [{"path": "../escape", "kind": "directory"}], id="climbs out"
        ),
        pytest.param([{"path": ".", "kind": "directory"}], id="the root itself"),
        pytest.param(
            [
                {"path": "a", "kind": "directory"},
                {"path": "a", "kind": "directory"},
            ],
            id="same path twice",
        ),
    ],
)
def test_a_declaration_that_is_not_the_agreed_shape_is_refused(declaration):
    assert provenance._valid_initial_workspace(declaration) is False


def test_a_started_payload_carrying_a_bad_declaration_is_refused(
    snapshot, tmp_path
):
    """And a good one is admitted, against the real payload the runner builds.

    The key-set gate is the only thing standing between the declaration and the
    event schema, which types ``payload`` as nothing more specific than an
    object.
    """
    root = tmp_path / "task"
    _stage(snapshot, root / "work", "reference_files/abc123/notes.txt")
    backend = _backend(root)
    try:
        declaration = backend.initial_workspace_declaration()
        good = _real_started_payload(backend, declaration)
        bad = _real_started_payload(backend, [{"path": "..", "kind": "directory"}])
        junk = _real_started_payload(backend, declaration)
        junk["something_else"] = 1
    finally:
        backend.close()

    assert provenance._valid_started_payload(good) is True
    assert provenance._valid_started_payload(bad) is False
    assert provenance._valid_started_payload(junk) is False


def test_a_started_payload_without_the_field_is_still_valid(tmp_path):
    """An empty workspace declares nothing, and that is not a missing field."""
    backend = _backend(tmp_path / "task")
    try:
        payload = _real_started_payload(backend, [])
    finally:
        backend.close()

    assert "initial_workspace" not in payload
    assert provenance._valid_started_payload(payload) is True


# --------------------------------------------------------------------------
# Reading a staged file during the replay.
# --------------------------------------------------------------------------


def _staged(content: bytes = TEXT, *, decodes: bool = True):
    return provenance._StagedFile(
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
        decodes_as_utf8=decodes,
    )


def _read_result(text: str) -> dict:
    return {"ok": True, "data": {"content": text}}


def test_a_whole_read_teaches_the_replay_the_bytes_it_does_not_hold():
    staged = _staged()

    learned = provenance._learn_staged_bytes(
        staged, {}, _read_result(TEXT.decode("utf-8"))
    )

    assert learned == TEXT
    assert staged.content == TEXT


def test_bytes_that_are_not_what_was_staged_are_refused():
    """A backend that quietly rewrote a file fails here rather than verifying.

    The digest was declared before the call, so this is a check and not the
    replay agreeing with itself.
    """
    with pytest.raises(ValueError, match="does not match what was staged"):
        provenance._learn_staged_bytes(
            _staged(), {}, _read_result("something else entirely")
        )


def test_a_read_from_an_offset_refuses_rather_than_guessing():
    with pytest.raises(ValueError, match="read from an offset"):
        provenance._learn_staged_bytes(
            _staged(), {"offset": 4}, _read_result(TEXT.decode("utf-8")[4:])
        )


def test_a_read_cut_short_by_a_limit_refuses_rather_than_guessing():
    """A slice hashes to nothing the declaration knows.

    Accepting it would turn the check into a formality, which is worse than
    not having it, because the record would still say the trace verified.
    """
    with pytest.raises(ValueError, match="limit shorter than the file"):
        provenance._learn_staged_bytes(
            _staged(), {"limit": 4}, _read_result(TEXT.decode("utf-8")[:4])
        )


def test_a_read_with_no_result_to_check_against_refuses():
    with pytest.raises(ValueError, match="no result to take its bytes from"):
        provenance._learn_staged_bytes(_staged(), {}, {"ok": False})


def test_a_file_that_does_not_decode_replays_as_the_error_it_really_was():
    """Not as a read that worked, and not as a crash.

    ``logo.png`` is a real input of a real task. The backend refuses to return
    it as text, and the replay has to reach the same answer from the
    declaration alone.
    """
    ledger = provenance._new_fixture_semantic_ledger(
        _started_payload(
            [
                {"path": "inputs", "kind": "directory"},
                {
                    "path": "inputs/logo.png",
                    "kind": "file",
                    "sha256": hashlib.sha256(BINARY).hexdigest(),
                    "size": len(BINARY),
                    "decodes_as_utf8": False,
                },
            ]
        )
    )

    replayed = provenance._replay_workspace_apply(
        {"operation": "read", "path": "inputs/logo.png"},
        ledger,
        recorded=None,
    )

    assert replayed == {"ok": False, "error_type": "fixture_backend_error"}
