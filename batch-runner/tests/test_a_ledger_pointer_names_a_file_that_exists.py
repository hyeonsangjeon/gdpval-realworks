"""The address on a grade's audit trail has to be an address.

``cost_ledger.path`` is where a published grade says its per-call bill lives.
Three places define it as a *relative repository path* — the grade schema,
``core.cost_projection.project_cost_ledger_reference``, and its JavaScript
mirror in ``scripts/cost-receipt.mjs`` — and for the field's whole life both
grading writers put ``Path.name`` in it: a bare filename.

That is not a shorter way of saying the same thing. Of the thirty-eight grade
files on disk carrying the field, **none** resolved from the repository root.
Twenty-nine resolved as a sibling of their own grade file — which only helps a
reader who already knows where the grade file is, and the dashboard record
built from the payload drops exactly that. Nine resolved from nowhere at all.
So the field read as an audit trail that exists while pointing at nothing, and
the one reader that could have reconstructed the location is the one reader
that cannot.

Nothing here calls a model or a network. Two things are measured against the
real corpus rather than a fixture, because a bound guessed from taste is how
the previous cap came to exclude seven real filenames.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.cost_projection import (
    _MAX_LEDGER_NAME,
    _MAX_LEDGER_PATH_LENGTH,
    project_cost_ledger_reference,
    repo_relative_ledger_path,
)
from step9_merge_shards import _resolve_shard_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]
GRADES_DIR = REPO_ROOT / "data" / "grades"

_DIGEST = "0" * 64


# ── what the writers may publish ─────────────────────────────────────────


def test_a_ledger_in_the_repository_is_named_from_the_root(tmp_path):
    """The whole fix in one line: the directories survive.

    ``data/grades/_shards/<stem>/`` is where a shard's export actually sits.
    A reader given only ``shard-004-of-011.cost_ledger.jsonl`` has no way back
    to it.
    """
    export = tmp_path / "data" / "grades" / "_shards" / "stem" / "s.cost_ledger.jsonl"
    export.parent.mkdir(parents=True)
    export.write_text("", encoding="utf-8")

    assert repo_relative_ledger_path(export, tmp_path) == (
        "data/grades/_shards/stem/s.cost_ledger.jsonl"
    )


def test_a_ledger_outside_the_repository_is_no_path_at_all(tmp_path):
    """``None``, not a filename, because a filename is what was wrong.

    A local run exporting somewhere outside the checkout has no repository
    path to give. Answering with the basename is how the field spent its whole
    life pointing at nothing; answering with nothing at least says so.
    """
    outside = tmp_path / "elsewhere" / "ledger.cost_ledger.jsonl"
    outside.parent.mkdir(parents=True)
    outside.write_text("", encoding="utf-8")
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    assert repo_relative_ledger_path(outside, checkout) is None


def test_the_underscore_directories_the_real_paths_run_through_are_allowed(tmp_path):
    """The segment rule had to be widened before any of this could ship.

    Every published ledger path passes through ``_shards``, ``_repeats`` or
    ``_diagnostic``. The original pattern required each segment to begin with
    ``[A-Za-z0-9]``, which never mattered while the field held a bare filename
    and rejects essentially every real path now that it does not.
    """
    for directory in ("_shards", "_repeats", "_diagnostic"):
        export = tmp_path / "data" / "grades" / directory / "l.cost_ledger.jsonl"
        export.parent.mkdir(parents=True)
        export.write_text("", encoding="utf-8")
        relative = repo_relative_ledger_path(export, tmp_path)
        assert relative == f"data/grades/{directory}/l.cost_ledger.jsonl"
        # And the validator has to agree, or the writer emits what the reader
        # refuses — which is the same defect with the halves swapped.
        project_cost_ledger_reference(
            {"path": relative, "sha256": _DIGEST}, field="cost_ledger"
        )


@pytest.mark.parametrize("segment", ["..", ".hidden", "-oh"])
def test_a_segment_that_is_not_a_plain_name_is_refused(segment):
    """``_`` was let in; ``.`` and ``-`` were deliberately kept out.

    ``..`` climbs out of the repository, a leading ``.`` names a file nothing
    here publishes, and a leading ``-`` is a segment a shell reads as an
    option. None of them appears in the corpus, so admitting them buys nothing
    and costs a class of surprise.
    """
    with pytest.raises(Exception) as raised:
        project_cost_ledger_reference(
            {"path": f"data/grades/{segment}/l.jsonl", "sha256": _DIGEST},
            field="cost_ledger",
        )
    assert "relative repository path" in str(raised.value)


def test_the_bounds_are_the_filesystems_and_not_a_preference(tmp_path):
    """255 is ``NAME_MAX``. It is not a number anyone chose.

    A component longer than this cannot name a file that exists, and a bound
    below it rejects names that do -- the 128 this used to be excluded seven
    real run-identity filenames from validation. The whole-path bound is
    separate because nesting, not naming, is what grows it.
    """
    assert _MAX_LEDGER_NAME == 255
    assert _MAX_LEDGER_PATH_LENGTH == 512

    long_name = "a" * _MAX_LEDGER_NAME + ".jsonl"
    with pytest.raises(Exception) as raised:
        project_cost_ledger_reference(
            {"path": f"data/grades/{long_name}", "sha256": _DIGEST},
            field="cost_ledger",
        )
    assert "relative repository path" in str(raised.value)

    deep = "/".join(["dir"] * 200) + "/l.jsonl"
    assert len(deep) > _MAX_LEDGER_PATH_LENGTH
    with pytest.raises(Exception) as over_long:
        project_cost_ledger_reference(
            {"path": deep, "sha256": _DIGEST}, field="cost_ledger"
        )
    assert "relative repository path" in str(over_long.value)


# ── measured against the corpus, not chosen ──────────────────────────────


@pytest.mark.skipif(not GRADES_DIR.is_dir(), reason="no grades corpus in this checkout")
def test_every_ledger_path_on_disk_fits_inside_the_bounds():
    """The bounds are only right if the real corpus clears them.

    Twenty-nine exports, the longest path 348 bytes and the longest single
    component 239. Both bounds sit above what exists with room to spare, and
    neither was picked before the corpus was counted.
    """
    exports = sorted(GRADES_DIR.rglob("*.cost_ledger.jsonl"))
    assert exports, "the corpus lost its exports; the bounds below are unmeasured"

    for export in exports:
        relative = repo_relative_ledger_path(export, REPO_ROOT)
        assert relative is not None, f"{export} does not project to a repository path"
        project_cost_ledger_reference(
            {"path": relative, "sha256": _DIGEST}, field="cost_ledger"
        )


@pytest.mark.skipif(not GRADES_DIR.is_dir(), reason="no grades corpus in this checkout")
def test_a_published_pointer_is_a_path_that_resolves():
    """The check the dashboard aggregator now enforces, stated here too.

    ``scripts/aggregate-grades.mjs`` refuses to publish a grade whose pointer
    names no file in this repository. It is free today because none of the
    nineteen top-level grade files carries the field at all -- which is worth
    knowing, because it means the guard was installed before it had anything
    to catch rather than after an incident.
    """
    for grade in sorted(GRADES_DIR.glob("*.json")):
        pointer = json.loads(grade.read_text(encoding="utf-8")).get("cost_ledger")
        if not pointer:
            continue
        claimed = pointer.get("path")
        assert (REPO_ROOT / claimed).is_file(), (
            f"{grade.name} publishes cost_ledger.path={claimed!r}, which is not "
            "a file here; see scripts/aggregate-grades.mjs"
        )


@pytest.mark.skipif(not GRADES_DIR.is_dir(), reason="no grades corpus in this checkout")
def test_the_sidecar_naming_scheme_is_past_NAME_MAX_for_five_grades():
    """A separate defect, pinned rather than fixed, so it cannot grow quietly.

    step8 derives its ledger from the grade file: ``out_path.stem`` plus
    ``.cost_ledger.sqlite3``, twenty characters. ``NAME_MAX`` is 255, so any
    grade filename over 240 bytes has a sidecar that cannot be created --
    ``ENAMETOOLONG``, verified on this filesystem, not assumed. Five files on
    disk are already past it, the longest needing 269, and all five carry no
    ledger pointer.

    Whether the missing pointer is *caused* by the cliff is not established
    here and is not claimed. Fixing it means changing how these files are
    named, which is a change with its own blast radius. What this test buys is
    that the count is a number somebody chose to accept rather than one nobody
    ever looked at.
    """
    suffix = ".cost_ledger.sqlite3"
    over = [
        grade
        for grade in GRADES_DIR.rglob("*.json")
        if len((grade.stem + suffix).encode()) > _MAX_LEDGER_NAME
    ]

    assert len(over) == 5, (
        f"{len(over)} grade files now have un-creatable ledger sidecars, not 5; "
        "the naming scheme moved, or a new run landed past NAME_MAX"
    )
    for grade in over:
        payload = json.loads(grade.read_text(encoding="utf-8"))
        assert payload.get("cost_ledger") is None, (
            f"{grade.name} claims a ledger, but its sqlite3 sibling would need "
            f"{len((grade.stem + suffix).encode())} bytes and NAME_MAX is "
            f"{_MAX_LEDGER_NAME}"
        )


# ── what the merge will still accept ─────────────────────────────────────


def test_a_shard_that_never_left_its_own_runner_still_resolves(tmp_path):
    """Shards do not share a root, so one root cannot find them all.

    Each shard is graded on a runner of its own and only meets the others once
    the merging job has downloaded them. Trying the merge's root and then each
    directory above the shard file, nearest first, is what covers both -- and
    the same walk resolves the bare filenames written before this field was a
    path, because a shard's own directory is the first ancestor tried.
    """
    shard = tmp_path / "downloaded" / "shard0" / "batch-runner" / "grade.json"
    shard.parent.mkdir(parents=True)
    shard.write_text("{}", encoding="utf-8")
    export = shard.with_name("grade.cost_ledger.jsonl")
    export.write_text("", encoding="utf-8")

    # Named from a root it was never under: found anyway, by walking up.
    found = _resolve_shard_ledger(shard, "grade.cost_ledger.jsonl", tmp_path / "root")
    assert found == export


def test_the_merge_root_is_tried_before_the_walk(tmp_path):
    """Ambiguity resolved toward the contract, not toward the legacy.

    When a name exists both at the root and beside the shard, the root wins:
    that is what the field means now. The two are the same file in every real
    arrangement; making the order explicit means a future reader does not have
    to work out which one a merge actually read.
    """
    root = tmp_path / "root"
    shard = tmp_path / "shard" / "grade.json"
    for path in (root / "l.jsonl", shard):
        path.parent.mkdir(parents=True, exist_ok=True)
    shard.write_text("{}", encoding="utf-8")
    (root / "l.jsonl").write_text("from the root", encoding="utf-8")
    (shard.with_name("l.jsonl")).write_text("from beside the shard", encoding="utf-8")

    found = _resolve_shard_ledger(shard, "l.jsonl", root)
    assert found is not None
    assert found.read_text(encoding="utf-8") == "from the root"


def test_a_pointer_that_climbs_out_of_the_repository_resolves_to_nothing(tmp_path):
    """The walk tries many roots, so ``..`` would eventually find something.

    Refused before the search starts rather than filtered after it, because a
    pointer containing ``..`` is not a repository path under any root and the
    validator would not have emitted one.
    """
    shard = tmp_path / "a" / "b" / "grade.json"
    shard.parent.mkdir(parents=True)
    shard.write_text("{}", encoding="utf-8")
    (tmp_path / "a" / "secret.jsonl").write_text("", encoding="utf-8")

    assert _resolve_shard_ledger(shard, "../secret.jsonl", tmp_path) is None
    assert _resolve_shard_ledger(shard, "", tmp_path) is None
