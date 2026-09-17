"""The state digest, read after a ``finalize`` rather than before one.

``AgenticV2MicroVMBackend.state_sha256`` rebuilt the parent's dictionary so it
could add the guest image and the boot count to it, and in rebuilding it hashed
``self._result`` directly where the parent hashes ``_result_identity(...)``.
``canonical_sha256`` is ``json.dumps``; ``finalize`` puts the deliverables'
*bytes* into ``_result``. So the microVM's state became unreadable the moment a
model handed in a file, and ``core.agentic_v2_tools`` -- which reads the state
after every call, catches everything, and rewrites the payload when it cannot
get a digest -- turned that into ``ok: False, error_type:
invalid_backend_state``. A successful ``finalize`` was recorded as a runner
defect and its deliverables were dropped.

This is the first defect in Agentic Sandbox V2 that only fires on success. A
task that finished with an empty ``deliverables`` list encoded cleanly and was
recorded as a clean failure; a task that did the work was destroyed. Run
35111267647, the first that ever reached a real guest, lost both of the tasks
that got as far as ``finalize`` this way -- ``0112fc9b`` and ``3baa0009``, the
second of which had already booted two guests, written its file and passed
``verify_public``.

Nothing in the suite caught it because every microVM ``state_sha256`` test read
the digest of a backend that had not finalized, so the divergent line sat behind
``if self._result is not None`` and was never evaluated. The tests here are
therefore written the other way round: finalize first, digest second, and over
every backend rather than the one that was wrong.

Offline. No model call, no network, no guest, no spend.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))
if str(BATCH_RUNNER_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT / "tests"))

from core.agentic_v2_contract import (  # noqa: E402
    TOOL_CONTRACT_VERSION,
    AgenticV2Lifecycle,
    AgenticV2Profile,
    LifecycleState,
)
from core.agentic_v2_fixture_backend import (  # noqa: E402
    AgenticV2FixtureBackend,
    _result_identity,
)
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend  # noqa: E402
from core.agentic_v2_provenance import canonical_sha256  # noqa: E402
from core.agentic_v2_substrate import AgenticV2SubstrateManifest  # noqa: E402
from core.agentic_v2_tools import AgenticV2ToolDispatcher  # noqa: E402

import test_agentic_v2_microvm_backend as microvm_fixtures  # noqa: E402

#: The first bytes of every ``.xlsx``, ``.pptx`` and ``.docx``, followed by a
#: byte that is not valid UTF-8. A deliverable a model actually produces.
A_REAL_SPREADSHEET = b"PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00\x21\x00\xde\xad\xbe\xef"


def _profile() -> AgenticV2Profile:
    return AgenticV2Profile(
        tool_contract_version=TOOL_CONTRACT_VERSION,
        policy_profile_id="offline-full-v1",
        foundation_only=True,
    )


def _fixture_backend(root: Path) -> AgenticV2FixtureBackend:
    return AgenticV2FixtureBackend(root=root, profile=_profile())


def _microvm_backend(root: Path) -> AgenticV2MicroVMBackend:
    return AgenticV2MicroVMBackend(
        root=root,
        profile=_profile(),
        image=microvm_fixtures.AN_IMAGE,
        boot_one_command=microvm_fixtures.Launcher(),
        substrate_manifest=AgenticV2SubstrateManifest.load(
            microvm_fixtures.MANIFEST_PATH
        ),
    )


#: Every backend the runner can be told to admit. Parametrised rather than
#: listed in one test, because the defect was a subclass forgetting something
#: the parent does and a third subclass could forget it again.
BACKENDS = {
    "fixture": _fixture_backend,
    "microvm": _microvm_backend,
}


@pytest.fixture(params=sorted(BACKENDS))
def backend(request, tmp_path):
    made = BACKENDS[request.param](tmp_path / "session")
    try:
        yield made
    finally:
        made.close()


# ---------------------------------------------------------------------------
# The property, on every backend
# ---------------------------------------------------------------------------


def test_the_state_is_still_readable_after_a_binary_deliverable(backend):
    """The reproduction, at the level the defect lived at.

    Before the fix this raised ``TypeError: Object of type bytes is not JSON
    serializable`` on the microVM and passed on the fixture, which is exactly
    the shape that let it through: the backend under test in almost every file
    here is the one that was right.
    """
    (backend.work / "book.xlsx").write_bytes(A_REAL_SPREADSHEET)

    before = backend.state_sha256()
    finalized = backend.finalize(
        {"deliverables": ["book.xlsx"], "summary": "the workbook"}
    )
    assert finalized["ok"] is True

    after = backend.state_sha256()
    assert len(after) == 64
    assert after != before, (
        "finalizing left the state digest unchanged, so a resume could not "
        "tell a finished task from an unfinished one"
    )


def test_a_deliverable_that_is_plain_text_is_no_safer(backend):
    """Not a binary-file problem. ``json.dumps`` refuses ``bytes``, not non-ASCII.

    Worth pinning separately because the run that found this had four binary
    deliverables and one text one, and "it was the spreadsheets" is the wrong
    lesson to take from it -- ``_collect_artifacts`` reads every deliverable as
    bytes whatever is in it.
    """
    (backend.work / "notes.txt").write_text("plain ascii\n", encoding="utf-8")
    assert backend.finalize(
        {"deliverables": ["notes.txt"], "summary": "notes"}
    )["ok"] is True
    assert len(backend.state_sha256()) == 64


def test_handing_in_nothing_was_always_safe(backend):
    """The asymmetry that made the defect invisible in the run record.

    An empty ``files`` list encodes, so a task that finalized with no
    deliverables produced a clean digest and was recorded as an ordinary
    failure. Only the tasks that succeeded were destroyed. Pinned so that a
    reader of run 35111267647 who sees three ordinary failures and two runner
    defects can see why the split fell where it did.
    """
    assert backend.finalize({"deliverables": [], "summary": "nothing"})["ok"] is True
    assert len(backend.state_sha256()) == 64


def test_the_digest_still_depends_on_what_was_delivered(backend, tmp_path):
    """The reduction must not have flattened the value into a constant.

    A fix that returned ``None`` whatever was finalized would pass every test
    above. The digest has to keep telling two finished tasks apart.
    """
    (backend.work / "out.bin").write_bytes(A_REAL_SPREADSHEET)
    backend.finalize({"deliverables": ["out.bin"], "summary": "one"})
    one = backend.state_sha256()

    other = BACKENDS[
        "microvm" if isinstance(backend, AgenticV2MicroVMBackend) else "fixture"
    ](tmp_path / "other")
    try:
        (other.work / "out.bin").write_bytes(A_REAL_SPREADSHEET + b"\x00")
        other.finalize({"deliverables": ["out.bin"], "summary": "one"})
        assert other.state_sha256() != one
    finally:
        other.close()


# ---------------------------------------------------------------------------
# Through the dispatcher, which is what the model actually met
# ---------------------------------------------------------------------------


def test_a_successful_finalize_is_not_rewritten_as_a_runner_defect(backend):
    """The user-visible half, and the reason this mattered.

    ``AgenticV2ToolDispatcher`` reads ``state_sha256`` after every call inside
    a bare ``except Exception``, and on anything that is not a digest it
    discards the backend's payload and substitutes
    ``invalid_backend_state``. So the backend returning ``ok: True`` was never
    enough -- the whole defect happened after ``finalize`` had already
    succeeded, which is why no backend test saw it and why the failure arrived
    labelled as the runner's own.
    """
    (backend.work / "book.xlsx").write_bytes(A_REAL_SPREADSHEET)
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )

    dispatched = dispatcher.dispatch(
        call_id="call_finalize_1",
        name="finalize",
        arguments={"deliverables": ["book.xlsx"], "summary": "the workbook"},
    )

    assert dispatched.result["ok"] is True, (
        f"the dispatcher refused a successful finalize: "
        f"{dispatched.result.get('error_type')}"
    )
    assert dispatched.result.get("error_type") is None
    assert dispatched.finalized is True
    assert dispatched.terminal_result is not None
    delivered = dispatched.terminal_result["files"]
    assert [item["filename"] for item in delivered] == ["book.xlsx"]
    assert delivered[0]["content"] == A_REAL_SPREADSHEET, (
        "the bytes that came back are not the bytes on disk, so the artifact "
        "the grader receives is not the one the model made"
    )


# ---------------------------------------------------------------------------
# The refactor itself
# ---------------------------------------------------------------------------


def test_the_shared_reduction_is_the_expression_it_replaced(backend):
    """The fixture's digest must not have moved.

    The microVM's finalized digest never successfully existed -- it raised --
    so there is nothing recorded to preserve there. The fixture's does exist,
    in every run to date, and a refactor that changed it would invalidate them
    silently. Held against the expression that was inlined, not against a
    literal, so it stays true when the reduction is extended.
    """
    (backend.work / "book.xlsx").write_bytes(A_REAL_SPREADSHEET)
    backend.finalize({"deliverables": ["book.xlsx"], "summary": "the workbook"})

    assert backend._terminal_result_digest() == canonical_sha256(
        _result_identity(backend._result)
    )


def test_no_backend_hashes_the_finalized_result_without_reducing_it():
    """The line that was wrong, held as text, for the next subclass.

    Every other test here goes through behaviour and would catch a repeat. This
    one catches the *shape* -- a new override rebuilding the dictionary and
    reaching for ``self._result`` again -- and says so at the place a reader
    would look, since the behavioural failure reads as a backend problem rather
    than as a forgotten call.
    """
    offenders = []
    for module in sorted((BATCH_RUNNER_ROOT / "core").glob("agentic_v2_*.py")):
        source = module.read_text(encoding="utf-8")
        if "canonical_sha256(self._result)" in source:
            offenders.append(module.name)
    assert not offenders, (
        f"{offenders} hash the finalized result without reducing it first. "
        "canonical_sha256 is json.dumps and a finalized result carries the "
        "deliverables' bytes: call _terminal_result_digest() instead"
    )
