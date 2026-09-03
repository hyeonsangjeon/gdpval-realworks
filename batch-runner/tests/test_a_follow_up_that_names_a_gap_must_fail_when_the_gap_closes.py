"""A follow-up that names a gap must go red when the gap closes.

PR3's follow-up list carried three items — Word/PDF page geometry, listening
inside an archive, and the empty-read disclaimer — that were already delivered
by #260 (``df473c0``) on 2026-08-29. They kept reading as open for five days,
with point estimates attached, because #260's closeout moved two Project cards
and never touched the report. Items 4 and 7 were struck when they closed; 1, 2
and 3 were not. Nothing noticed, because nothing tied the sentence to the code.

Correcting the sentences alone would leave that exact hole open for the next
item. So each numbered follow-up is registered here against a *probe*: a
model-free call that runs the capability the item asks for and answers whether
it exists right now.

    probe() is True   ->  the item must be struck through
    probe() is False  ->  the item must not be struck through

Both directions fail. Closing a capability without closing its item is the bug
this file was written for; striking an item whose capability was reverted is the
same bug pointed the other way, and would be worse — the list would then claim a
gap was handled when it is open again.

Items 5 and 6 ask the owner to *choose* something, not for code to exist, so
they have no probe. That exemption is pinned to exactly ``{5, 6}``: a new item
cannot quietly join it, and every number present in the document must appear in
one of the two registries, so adding an item 8 turns this suite red until it is
classified.

Item 8 is the first entry written under that rule, and it is a cautionary one.
It was added while writing probe 1, describing ``inspect_formatting``'s PDF
branch as unreachable in production -- and that was wrong. The probe behind it
grepped ``requirements.txt`` for ``PyMuPDF`` without following the ``-r`` include
on its fourth line, so it answered ``False`` for a capability the shipped
environment has had since 2026-07-15 and that the stage-3 paid run demonstrably
used. Both the item and the probe are corrected here; what the episode shows is
that a probe is only as honest as the question it asks, so the reader it uses now
walks the same include chain pip does.

Item 9 came out of verifying that correction. ``compute_grader_source_hash``
makes the same one-file-for-a-graph move: it hashes ``requirements.txt`` and not
the file that ``requirements.txt`` includes, so the identity two paid runs are
pinned to does not cover the declaration of PyMuPDF, openpyxl, python-pptx,
python-docx or Pillow. Measured, not read off the source -- deleting PyMuPDF
from the included file leaves the fingerprint byte-identical while appending one
comment to the entry file changes it. It answers ``False`` today, so the
``False`` direction of the contract is exercised by a live item as well as by
the negative control over the comparison itself.

Measured evidence for the three closures — the paid runs on either side of #260,
compared item by item — is in ``tasks/rebuilding_grading_task/320-three-gaps-that-closed.md``.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import wave
import zipfile
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS = REPO_ROOT / "tasks/rebuilding_grading_task"
REPORT = TASKS / "PR3_REPORT.md"
AGGREGATE_GRADES = REPO_ROOT / "scripts/aggregate-grades.mjs"

#: Numbered list entries under ``## 후속 항목``. ``~~`` before the bold lead-in
#: is the marker this repository uses for a closed item, so it is captured
#: rather than skipped -- reading the list without it is how the sibling test
#: went blind to closures until #412.
_ENTRY = re.compile(r"^(\d+)\.\s+(~~)?\*\*", re.M)


def _follow_ups() -> dict[int, bool]:
    """Map each numbered follow-up to whether it is struck through."""
    text = REPORT.read_text(encoding="utf-8")
    heading = re.search(r"^## 후속 항목\s*$", text, re.M)
    if heading is None:
        # Prefix-matching the heading would let ``## 후속 항목들`` keep this
        # suite green while pointing it at a section nobody maintains.
        raise AssertionError(f"{REPORT.name} has no '## 후속 항목' section heading")
    body = text[heading.start() :]
    entries: dict[int, bool] = {}
    for number, struck in _ENTRY.findall(body):
        # Two entries sharing a number is not a typo to shrug at: the second
        # would silently overwrite the first here, so one of the two claims
        # would be checked against nothing at all.
        assert int(number) not in entries, (
            f"follow-up {number} is listed twice in {REPORT.name}; one of the "
            f"two would be dropped before anything checked it"
        )
        entries[int(number)] = bool(struck)
    return entries


def _rd() -> Any:
    """The module, not the function of the same name exported beside it."""
    return importlib.import_module("core.tools.read_deliverable")


def _requirements_closure(entry: Path) -> tuple[list[Path], list[str]]:
    """The files ``pip install -r entry`` reads, and every line in them.

    ``requirements.txt`` is not a flat list. Its fourth line is
    ``-r requirements-renderer.txt``, so a package can be installed by every
    workflow in this repository without ever being named in the file those
    workflows pass to pip. Reading the entry file alone is exactly how probe 8
    was first written, and it reported a capability as missing that production
    has had since ``fa8bf4f`` (2026-07-15). pip follows the include; a probe
    that does not is answering a different question from the one that ships.

    The file list is returned beside the lines because the same include is a
    hole in the grader fingerprint (probe 9), and both questions need the same
    walk.
    """
    seen: set[Path] = set()
    files: list[Path] = []
    lines: list[str] = []
    stack = [entry]
    while stack:
        current = stack.pop().resolve()
        if current in seen:  # an include cycle is pip's problem, not a hang here
            continue
        seen.add(current)
        assert current.exists(), (
            f"{current.name} is pulled in with -r but is not on disk. The "
            f"install graph this reader walks is broken, which is a different "
            f"finding from a package being absent from it."
        )
        files.append(current)
        for raw in current.read_text(encoding="utf-8").splitlines():
            # pip treats '#' as a comment at line start or after whitespace,
            # which leaves '#egg=' fragments in URLs alone.
            line = re.sub(r"(^|\s)#.*$", "", raw).strip()
            if not line:
                continue
            include = re.match(r"(?:-r|--requirement)[=\s]+(\S+)", line)
            if include:
                stack.append(current.parent / include.group(1))
            else:
                lines.append(line)
    return files, lines


def _declared_in_requirements(package: str, entry: Path) -> bool:
    """Is ``package`` installed by ``pip install -r entry``, include chain and all?"""
    pattern = re.compile(rf"^{re.escape(package)}\b", re.I)
    return any(pattern.match(line) for line in _requirements_closure(entry)[1])


def _scope_descriptions() -> list[str]:
    """Every ``scope`` description across the tool schemas, by shape not name."""
    rd = _rd()
    out: list[str] = []
    for module in (rd, importlib.import_module("core.tools")):
        for attr in dir(module):
            schema = getattr(module, attr)
            if not isinstance(schema, dict) or schema.get("type") != "function":
                continue
            props = (
                schema.get("function", schema).get("parameters", {}).get("properties", {})
            )
            scope = props.get("scope")
            if isinstance(scope, dict) and isinstance(scope.get("description"), str):
                out.append(scope["description"])
    return out


# --------------------------------------------------------------------------
# probes -- each runs the capability, none calls a model
# --------------------------------------------------------------------------


def _probe_page_geometry(tmp_path: Path) -> bool:
    """1. Is page geometry reported where the judge actually asked for it?

    Two halves. A ``.docx`` must carry ``converted_page_count``, and when that
    is ``None`` it must say why instead of leaving ``paragraph_count`` to be
    misread as a page count. A ``.pdf`` must report the page's actual size --
    the whole of follow-up 1, since ``f9a1c16c``'s landscape item was failed on
    a correct answer when ``page_count: 1`` was the only geometry visible.

    The PDF half asks ``inspect_structure``, not ``inspect_formatting``,
    because that is the op the paid runs used: the stage-1 evidence the judge
    cited, ``"kind": "pdf", "page_count": 1``, is ``_inspect_pdf``'s shape.
    ``_inspect_pdf`` prefers PyMuPDF and falls back to ``pdfplumber``, and both
    branches build the same block, so this answers the same under either.
    ``inspect_formatting``'s PDF branch has no such fallback and is followed by
    :func:`_probe_formatting_pdf_geometry_in_the_shipped_environment`.
    """
    # Only the two writers are guarded. The reader is deliberately not:
    # skipping on an import would make this probe inert exactly where the
    # drift it watches for would land.
    pytest.importorskip("docx")
    pytest.importorskip("reportlab")
    from docx import Document
    from reportlab.pdfgen import canvas

    Document().save(tmp_path / "a.docx")
    # 432x288pt: the landscape page from _pdf_geometry's docstring.
    pdf = canvas.Canvas(str(tmp_path / "land.pdf"), pagesize=(432, 288))
    pdf.drawString(20, 20, "x")
    pdf.save()

    rd = _rd()
    docx = rd.read_deliverable(op="inspect_formatting", path="a.docx", base_dir=str(tmp_path))
    body = docx.get("data") or {}
    if "converted_page_count" not in body:
        return False
    if body["converted_page_count"] is None and not (
        body.get("page_count_error") and body.get("page_count_note")
    ):
        return False

    pdf_body = (
        rd.read_deliverable(op="inspect_structure", path="land.pdf", base_dir=str(tmp_path)).get("data")
        or {}
    )
    return pdf_body.get("orientation") == "landscape" and bool(pdf_body.get("page_sizes"))


def _probe_archive_audio(tmp_path: Path) -> bool:
    """2. Can a listening model be assigned to a member of an archive?

    Assignment needs both halves: routing has to know an archive holds audio,
    and the judge's audio tool has to be able to open the member it picks.
    ``False`` for a text-only archive matters as much as ``True`` for an audio
    one -- a probe that always said yes would promote every zip to listening.
    """
    stem = tmp_path / "Synths.wav"
    with wave.open(str(stem), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        handle.writeframes(b"\x00\x00" * 4800)
    with zipfile.ZipFile(tmp_path / "stems.zip", "w") as archive:
        archive.write(stem, "Synths.wav")
    with zipfile.ZipFile(tmp_path / "docs.zip", "w") as archive:
        archive.writestr("a.txt", "hi")

    rd = _rd()
    if rd.has_audio_content(tmp_path / "stems.zip") is not True:
        return False
    if rd.has_audio_content(tmp_path / "docs.zip") is not False:
        return False
    if not hasattr(rd, "open_archive_member"):
        return False
    with rd.open_archive_member(tmp_path / "stems.zip", "Synths.wav") as opened:
        return Path(opened).exists()


def _probe_empty_read_disclaimer(tmp_path: Path) -> bool:
    """3. Does an empty read refuse to stand in as evidence of absence?"""
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")
    body = (
        _rd().read_deliverable(op="read_content", path="empty.txt", base_dir=str(tmp_path)).get("data")
        or {}
    )
    return "NOT that the content is absent" in (body.get("note") or "")


def _probe_scope_member_documented(tmp_path: Path) -> bool:
    """4. Does every schema that takes a ``scope`` say how to open a member?

    Found by shape, so a third schema added later is held to the same contract
    instead of becoming the next place it is missing.
    """
    rd = _rd()
    contract = getattr(rd, "_SCOPE_MEMBER_CONTRACT", None)
    descriptions = _scope_descriptions()
    if not contract or not descriptions:
        return False
    return all(contract in text for text in descriptions)


def _probe_published_index_cost(tmp_path: Path) -> bool:
    """7. Does the published index stop asserting a cost it never measured?"""
    if not AGGREGATE_GRADES.exists():
        return False
    source = AGGREGATE_GRADES.read_text(encoding="utf-8")
    # Word-bounded: a substring test would keep passing against a renamed
    # ``projectLegacySummaryX``, which is exactly how a probe goes blind.
    return bool(re.search(r"\bprojectLegacySummary\b", source))


def _probe_formatting_pdf_geometry_in_the_shipped_environment(tmp_path: Path) -> bool:
    """8. Can ``inspect_formatting`` report PDF geometry in the shipped env?

    ``_op_inspect_formatting``'s PDF branch is PyMuPDF-only: on ``ImportError``
    it returns ``{"kind": "pdf", "note": "PyMuPDF not available"}``, with no
    geometry and no fonts. The question is whether that branch is the one this
    repository actually runs.

    It is not, and the first version of this probe got that wrong. PyMuPDF is
    declared in ``requirements-renderer.txt``, which ``requirements.txt`` pulls
    in with ``-r`` on its fourth line -- both since ``fa8bf4f`` (2026-07-15).
    ``backend-tests.yml``, ``grade-run.yml``, ``batch-run.yml`` and
    ``audio-accuracy-probe.yml`` all install ``requirements.txt``, so all four
    install PyMuPDF, and the stage-3 paid run confirms it from the other end:
    three items quote a PDF font list, and ``ae0c1093``'s evidence reads
    ``"page_size_uniform": true, "orientation": "portrait", "fonts": [...]`` --
    the fitz branch's exact output shape, which ``_inspect_pdf`` never emits.

    Deliberately static rather than an ``import fitz`` attempt. A developer box
    that happens to have PyMuPDF would otherwise answer ``True`` here while an
    environment without it answered ``False``, and a probe whose verdict depends
    on who is running it cannot hold a document to anything. The question is not
    "can *this* machine do it" but "is it reachable in the environment we ship" --
    so the read has to walk the same include chain pip does.
    """
    source_path = REPO_ROOT / "batch-runner/core/tools/read_deliverable.py"
    requirements = REPO_ROOT / "batch-runner/requirements.txt"
    for path in (source_path, requirements):
        # Raise rather than return False. A missing anchor is not evidence that
        # the capability is absent, and returning False for it would let the
        # probe go blind while the suite stayed green.
        assert path.exists(), f"probe 8 cannot find {path.relative_to(REPO_ROOT)}"

    if _declared_in_requirements("PyMuPDF", requirements):
        return True

    source = source_path.read_text(encoding="utf-8")
    branch = re.search(
        r"def _op_inspect_formatting.*?(?=\n(?:def |# ──))", source, re.S
    )
    assert branch is not None, (
        "probe 8 could not find _op_inspect_formatting; it was renamed or "
        "restructured, and the probe is now reading nothing"
    )
    return "PyMuPDF not available" not in branch.group(0)


#: The grading config probe 9 fingerprints. Any real one would do -- this is
#: the one the 185-task paid run used, so the measurement is taken against the
#: identity that is actually pinned in published grades.
_FINGERPRINT_CONFIG = "batch-runner/grading_configs/gold_ceiling_185_v2_sol_max.yaml"


def _fingerprint_inputs() -> set[Path]:
    """Every file the grader identity hashes, observed rather than parsed.

    ``compute_grader_source_hash`` builds its input list from a literal, an
    ``rglob`` over ``core/`` and a couple of config lookups, so reading the
    source for a filename would answer a slightly different question from the
    one that ships -- the mistake probe 8 made. Recording what the function
    actually reads answers it exactly, and keeps working if the list is later
    built some other way.
    """
    import step8_grade  # local: heavy, and only probe 9 needs it
    import yaml

    config_path = REPO_ROOT / _FINGERPRINT_CONFIG
    assert config_path.is_file(), f"probe 9 cannot find {_FINGERPRINT_CONFIG}"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    read: list[Path] = []
    original = Path.read_bytes

    def recording(self: Path) -> bytes:
        read.append(Path(self).resolve())
        return original(self)

    cwd = Path.cwd()
    Path.read_bytes = recording  # type: ignore[method-assign]
    try:
        # _batch_runner_root() resolves against the working directory, not
        # against its own __file__, so the probe has to stand where step8 runs.
        os.chdir(REPO_ROOT / "batch-runner")
        step8_grade.compute_grader_source_hash(str(config_path), config)
    finally:
        Path.read_bytes = original  # type: ignore[method-assign]
        os.chdir(cwd)
    return set(read)


def _probe_identity_covers_the_install_graph(tmp_path: Path) -> bool:
    """9. Does the grader fingerprint cover every file pip reads?

    ``grader_source_hash`` is what two shards must agree on before their
    partials can be merged, and what a published grade cites to say which
    grader produced it. It hashes ``batch-runner/requirements.txt`` — but not
    ``requirements-renderer.txt``, which that file includes with ``-r`` and
    which is where ``PyMuPDF``, ``openpyxl``, ``python-pptx``, ``python-docx``
    and ``Pillow`` are declared. Every one of those is a capability the judge's
    ``read_deliverable`` tools use, so the identity can stay byte-identical
    while what the grader can see changes.

    Measured offline before this item was opened, at ``94ea015``: deleting
    ``PyMuPDF>=1.21.0`` from the included file left the fingerprint at
    ``7b2bd7d9...``, and appending a single comment line to the entry file moved
    it to ``0247c9e0...``. This is the same one-file-for-a-graph mistake probe 8
    made, sitting inside the identity rather than inside a test.

    Fixing it means editing ``step8_grade.py``, which moves the fingerprint for
    every future run -- a real cost, and the owner's call. The item stays open
    and this probe stays ``False`` until then.
    """
    entry = REPO_ROOT / "batch-runner/requirements.txt"
    assert entry.is_file(), "probe 9 cannot find batch-runner/requirements.txt"
    files, _ = _requirements_closure(entry)
    hashed = _fingerprint_inputs()
    # If the entry file itself stopped being hashed, the comparison below would
    # still say False, but for a completely different reason. Say so instead.
    assert entry.resolve() in hashed, (
        "the grader fingerprint no longer reads requirements.txt at all; probe 9 "
        "is measuring something other than what it was written for"
    )
    return all(path in hashed for path in files)


#: Follow-up number -> the capability it asked for.
PROBES: dict[int, Callable[[Path], bool]] = {
    1: _probe_page_geometry,
    2: _probe_archive_audio,
    3: _probe_empty_read_disclaimer,
    4: _probe_scope_member_documented,
    7: _probe_published_index_cost,
    8: _probe_formatting_pdf_geometry_in_the_shipped_environment,
    9: _probe_identity_covers_the_install_graph,
}

#: Follow-ups that ask the owner to decide, not for code to exist. Pinned, so a
#: new item cannot be dropped in here to escape having a probe written for it.
OWNER_DECISIONS = {5, 6}


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------


def test_the_follow_up_list_is_actually_being_read():
    """Guard the parse itself: a regex that matches nothing passes everything."""
    entries = _follow_ups()
    assert len(entries) >= 7, f"parsed only {len(entries)} follow-ups: {sorted(entries)}"
    assert set(entries) == set(range(1, len(entries) + 1)), f"gaps in {sorted(entries)}"


def test_every_numbered_follow_up_is_classified():
    """An item 8 added later must be classified before this suite goes green."""
    entries = set(_follow_ups())
    classified = set(PROBES) | OWNER_DECISIONS
    assert entries - classified == set(), (
        f"follow-ups with neither a probe nor an owner-decision entry: "
        f"{sorted(entries - classified)}"
    )
    assert classified - entries == set(), (
        f"registered here but absent from the report: {sorted(classified - entries)}"
    )


def test_the_owner_decision_exemption_is_exactly_five_and_six():
    assert OWNER_DECISIONS == {5, 6}
    assert not (OWNER_DECISIONS & set(PROBES)), "an item cannot be both"


def _mismatch(number: int, exists: bool, struck: bool) -> str | None:
    """The contract itself, in one place so it can be negative-controlled.

    Returns the complaint, or ``None`` when the document and the capability
    agree. Kept separate from the test below so the rule can be fed all four
    combinations directly. Item 9 is open, so ``struck and not exists`` is
    reachable today by striking it -- but that is a fact about the current
    contents of the report, not about the rule, and it stops being true the day
    item 9 closes. Between item 8 closing and item 9 opening it was not true at
    all, and nothing said so.
    """
    if exists and not struck:
        return (
            f"follow-up {number} still reads as open, but the capability it asks "
            f"for runs today. Strike it through and record what the change "
            f"actually measured -- see 320-three-gaps-that-closed.md."
        )
    if struck and not exists:
        return (
            f"follow-up {number} is struck through as closed, but its capability "
            f"no longer runs. The list is claiming a gap is handled while it is "
            f"open again."
        )
    return None


@pytest.mark.parametrize("number", sorted(PROBES))
def test_a_follow_up_is_struck_exactly_when_its_capability_exists(number, tmp_path):
    entries = _follow_ups()
    assert number in entries, f"follow-up {number} is missing from {REPORT.name}"

    complaint = _mismatch(number, PROBES[number](tmp_path), entries[number])
    if complaint:
        pytest.fail(complaint)


def test_both_directions_of_the_contract_actually_fail():
    """Negative control over the comparison itself.

    Item 9 exercises the ``False`` direction with a live case today, but that
    is a temporary state -- it holds only until someone decides the fingerprint
    is worth moving. This test does not depend on any item being open: it feeds
    the rule all four combinations directly, so the direction stays pinned on
    the day the last open item closes rather than going quietly dead.

    The second direction is the one worth pinning hardest: a capability that was
    reverted while its item stayed struck would leave the list claiming a gap
    is handled when it is open again, which is worse than the drift this file
    was written for.
    """
    assert _mismatch(8, exists=True, struck=True) is None
    assert _mismatch(8, exists=False, struck=False) is None
    assert "still reads as open" in (_mismatch(8, exists=True, struck=False) or "")
    assert "open again" in (_mismatch(8, exists=False, struck=True) or "")


def test_the_requirements_reader_follows_includes():
    """The bug behind item 8's first version, pinned as its own regression.

    ``requirements.txt`` names neither PyMuPDF nor openpyxl; it reaches both
    through ``-r requirements-renderer.txt``. A reader that stops at the entry
    file reports a shipped dependency as absent, which is how a capability the
    stage-3 paid run used came to be written up as an open gap.
    """
    entry = REPO_ROOT / "batch-runner/requirements.txt"
    flat = entry.read_text(encoding="utf-8")
    assert re.search(r"^\s*-r\s+\S+", flat, re.M), (
        "requirements.txt no longer includes another file; if the include was "
        "inlined this test is obsolete, but check what else it carried first"
    )
    for package in ("PyMuPDF", "openpyxl"):
        assert not re.search(rf"^{package}\b", flat, re.M | re.I), (
            f"{package} is now named directly in requirements.txt, so this test "
            f"no longer distinguishes a reader that follows -r from one that does not"
        )
        assert _declared_in_requirements(package, entry), (
            f"{package} is installed by 'pip install -r requirements.txt' but the "
            f"reader cannot see it -- the include chain is not being walked"
        )


def test_the_three_closed_by_260_are_closed_here_too():
    """The specific drift this file was written for, named rather than implied."""
    entries = _follow_ups()
    still_open = [n for n in (1, 2, 3) if not entries.get(n)]
    assert not still_open, (
        f"follow-ups {still_open} were delivered by #260 (df473c0) and measured "
        f"in the paid runs on either side of it; they must not read as open"
    )


def test_the_measured_note_is_reachable_from_the_report():
    """The estimates were replaced by measurements; the reader must find them."""
    note = TASKS / "320-three-gaps-that-closed.md"
    assert note.exists(), "the note carrying the measurement is missing"
    body = REPORT.read_text(encoding="utf-8")
    section = body[body.index("## 후속 항목") :]
    # Each entry closed by #260 must hand the reader the measurement, because
    # what it replaced was a point estimate. A strike-through on its own would
    # leave "약 20점" as the last number anyone read about that item.
    entries = re.split(r"^(?=\d+\.\s)", section, flags=re.M)
    for number in (1, 2, 3):
        entry = next((e for e in entries if e.startswith(f"{number}.")), "")
        assert entry, f"follow-up {number} not found in {REPORT.name}"
        assert note.name in entry or "320" in entry, (
            f"follow-up {number} is closed but does not point at {note.name}, "
            f"so the estimate it carried has no measured replacement in reach"
        )


def test_the_pre_run_table_is_left_alone():
    """304's known-limits table was written before the paid run and stays put.

    It now contains a row that is false. Correcting it would rewrite a record of
    what was known beforehand, which is the opposite of the fix in this change:
    the successor document carries the correction, and 304 says so itself.
    """
    pre_run = TASKS / "304-full-gold-corpus.md"
    if not pre_run.exists():
        pytest.skip("304-full-gold-corpus.md is not present")
    text = pre_run.read_text(encoding="utf-8")
    assert "유료 실행" in text and "전에" in text, (
        "304 no longer states that its table predates the paid run; without that "
        "sentence the stale row reads as a current claim"
    )


def test_every_sibling_link_points_at_a_file_everyone_has():
    """A note added here is ignored by default; the link would 404 on main.

    ``.gitignore`` closes ``tasks/rebuilding_grading_task/*`` and re-opens each
    file by name, and says so in a comment. Forgetting the negation leaves the
    document correct in the worktree that wrote it and broken for every other
    checkout -- including CI, where the assertion above would then fail for a
    reason that has nothing to do with follow-ups. Checking existence on disk
    cannot see this; only tracking can.
    """
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        pytest.skip("not a git checkout")
    tracked = set(result.stdout.split())

    broken: list[str] = []
    for doc in sorted((TASKS).glob("*.md")):
        if str(doc.relative_to(REPO_ROOT)) not in tracked:
            continue
        for target in re.findall(r"\]\(\./([^)#]+)\)", doc.read_text(encoding="utf-8")):
            relative = f"tasks/rebuilding_grading_task/{target}"
            if relative in tracked:
                continue
            if not (REPO_ROOT / relative).exists():
                broken.append(f"{doc.name} -> {target} (missing)")
                continue
            # On disk but not in the index. Two different causes with two
            # different fixes, and saying the wrong one sends the reader to a
            # .gitignore line that is already correct.
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", relative], cwd=REPO_ROOT
            )
            broken.append(
                f"{doc.name} -> {target} "
                + (
                    "(present but ignored -- add a !negation to .gitignore)"
                    if ignored.returncode == 0
                    else "(present and un-ignored, but never added -- git add it)"
                )
            )
    assert not broken, "links that resolve for nobody else:\n  " + "\n  ".join(broken)


def test_probes_are_model_free():
    """No probe may reach a network client -- this suite runs on every commit."""
    source = Path(__file__).read_text(encoding="utf-8")
    start = source.index("# probes -- each runs")
    end = source.index("#: Follow-up number")
    body = source[start:end]
    for forbidden in ("AzureOpenAI", "OpenAI(", "anthropic", "requests.", "httpx"):
        assert forbidden not in body, f"a probe reaches {forbidden}"


def test_the_registry_covers_what_the_document_numbers(tmp_path):
    """Every probe must return a real bool, not something truthy by accident."""
    for number, probe in sorted(PROBES.items()):
        target = tmp_path / f"p{number}"
        target.mkdir()
        result = probe(target)
        assert isinstance(result, bool), (
            f"probe {number} returned {type(result).__name__}; a non-bool makes "
            f"the strike assertion meaningless"
        )
        assert json.dumps(result) in ("true", "false")
