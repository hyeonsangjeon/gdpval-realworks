"""The grader's identity has to cover every file pip reads, not just the first.

``grader_source_hash`` is the value two shards must agree on before their
partial grades may be merged, and the value a published grade cites to say
which grader produced it. It hashed ``batch-runner/requirements.txt`` and
stopped there. That file's fourth line is ``-r requirements-renderer.txt``, and
the included file is where ``PyMuPDF``, ``openpyxl``, ``python-pptx``,
``python-docx`` and ``Pillow`` are declared -- every one a capability the
judge's ``read_deliverable`` tools use to see a deliverable at all.

Measured before the fix, at ``af0f001``: deleting ``PyMuPDF>=1.21.0`` from the
included file left the fingerprint at ``06a1b80c...``, unmoved. A grader that
could no longer open a PDF was still claiming, byte for byte, to be the grader
that could.

This is the same mistake probe 8 made and follow-up 9 named -- reading a graph
as a single file -- sitting inside the identity rather than inside a test. The
suite below pins the fix from four sides: the closure walker, the digest it
feeds, the three hand-kept mirrors that decide when a merge is frozen, and the
failure modes an include can have.

Model-free. Nothing here calls a network.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Callable

import pytest
import yaml

import step8_grade

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_ROOT = REPO_ROOT / "batch-runner"
ENTRY = BATCH_ROOT / "requirements.txt"
INCLUDED = BATCH_ROOT / "requirements-renderer.txt"

#: Declared in the included file, used by ``read_deliverable``. Named here so a
#: capability quietly moving out of the install graph fails as a capability
#: rather than as an arithmetic surprise about file counts.
RENDERER_PACKAGES = ("PyMuPDF", "openpyxl", "python-pptx", "python-docx", "Pillow")

#: Of those, the ones the entry file does *not* also name. These are what make
#: the difference between following ``-r`` and not following it observable at
#: all. ``python-docx`` is excluded because ``requirements.txt`` declares it
#: twice on its own -- at ``>=1.0.0`` and again at ``>=0.8.11``, which is a
#: separate untidiness and not this change's to fix.
INCLUDE_ONLY_PACKAGES = ("PyMuPDF", "openpyxl", "python-pptx", "Pillow")

CONFIG = BATCH_ROOT / "grading_configs" / "gold_ceiling_185_v2_sol_max.yaml"


# ── a batch-runner made of nothing, so mutations stay off the real tree ──


def _fake_batch_runner(tmp_path: Path) -> tuple[Path, Path]:
    """The smallest tree ``compute_grader_source_hash`` will accept.

    The real function is driven throughout this file -- a reimplementation
    would agree with itself while the shipped one drifted. But it hashes files
    in place, so the mutation tests need a tree they are allowed to edit.

    ``tmp_path`` is resolved first: the hash function rejects any path that
    traverses a symlink, and a ``/tmp`` that is one would fail every test here
    for a reason that has nothing to do with requirements files.
    """
    root = tmp_path.resolve()
    batch = root / "batch-runner"
    (batch / "core").mkdir(parents=True)
    (batch / "schemas").mkdir()
    (batch / "scripts").mkdir()
    (batch / "prompts").mkdir()
    (batch / "grading_configs").mkdir()

    (batch / "step8_grade.py").write_text("# stand-in\n", encoding="utf-8")
    (batch / "core" / "grader.py").write_text("# stand-in\n", encoding="utf-8")
    (batch / "schemas" / "grade.schema.json").write_text("{}\n", encoding="utf-8")
    (batch / "scripts" / "download_inference_from_hf.py").write_text(
        "# stand-in\n", encoding="utf-8"
    )
    (batch / "prompts" / "judge.md").write_text("judge\n", encoding="utf-8")
    (batch / "requirements.txt").write_text(
        "pyyaml>=6.0\n-r requirements-renderer.txt\n", encoding="utf-8"
    )
    (batch / "requirements-renderer.txt").write_text(
        "PyMuPDF>=1.21.0\nopenpyxl>=3.1.0\n", encoding="utf-8"
    )

    config = batch / "grading_configs" / "c.yaml"
    config.write_text("prompt:\n  template: prompts/judge.md\n", encoding="utf-8")
    return batch, config


def _hash_fake(monkeypatch, batch: Path, config: Path) -> str:
    """Run the shipped hash function against the fake tree."""
    # _batch_runner_root() resolves against the working directory, not against
    # its own __file__, so the caller has to stand where step8 runs.
    monkeypatch.chdir(batch)
    loaded = yaml.safe_load(config.read_text(encoding="utf-8"))
    return step8_grade.compute_grader_source_hash(str(config), loaded)


def _mutating(monkeypatch, tmp_path: Path, edit: Callable[[Path], None]) -> tuple[str, str]:
    """(before, after) fingerprints across one edit to the fake tree."""
    batch, config = _fake_batch_runner(tmp_path)
    before = _hash_fake(monkeypatch, batch, config)
    edit(batch)
    return before, _hash_fake(monkeypatch, batch, config)


def _paths_read_by_the_hash(monkeypatch) -> list[str]:
    """What the real function reads for the real config, observed not restated."""
    seen: list[Path] = []
    real_read_bytes = Path.read_bytes

    def spy(self: Path) -> bytes:
        seen.append(self)
        return real_read_bytes(self)

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    monkeypatch.chdir(BATCH_ROOT)
    monkeypatch.setattr(Path, "read_bytes", spy)
    step8_grade.compute_grader_source_hash(str(CONFIG), config)
    monkeypatch.undo()
    return sorted({p.resolve().relative_to(REPO_ROOT).as_posix() for p in seen})


# ── the defect itself ────────────────────────────────────────────────────


def test_the_repository_still_reaches_its_renderer_deps_through_an_include():
    """The premise. If the include is ever inlined, this file is measuring air."""
    flat = ENTRY.read_text(encoding="utf-8")
    assert re.search(r"^\s*-r\s+requirements-renderer\.txt\s*$", flat, re.M), (
        "requirements.txt no longer includes requirements-renderer.txt; if the "
        "include was inlined, check what else it carried before deleting this"
    )
    included = INCLUDED.read_text(encoding="utf-8")
    for package in RENDERER_PACKAGES:
        assert re.search(rf"^{re.escape(package)}\b", included, re.M | re.I), (
            f"{package} left requirements-renderer.txt; the judge reads "
            f"deliverables with it, so find out where it went"
        )
    for package in INCLUDE_ONLY_PACKAGES:
        assert not re.search(rf"^{re.escape(package)}\b", flat, re.M | re.I), (
            f"{package} is now named directly in requirements.txt, so this "
            f"suite no longer distinguishes following -r from not following it"
        )


def test_the_fingerprint_reads_the_included_file(monkeypatch):
    """The fix, stated as the thing that was false before it."""
    hashed = _paths_read_by_the_hash(monkeypatch)
    assert "batch-runner/requirements.txt" in hashed
    assert "batch-runner/requirements-renderer.txt" in hashed, (
        "the grader's identity is blind to the half of its install graph that "
        "declares how it reads deliverables"
    )


def test_deleting_a_renderer_package_moves_the_fingerprint(monkeypatch, tmp_path):
    """The measured regression: this returned 'unmoved' at af0f001.

    A grader that has lost PyMuPDF cannot open a PDF. If its fingerprint does
    not move, a merge will join its partials to those of a grader that could,
    and the published grade will cite one identity for both.
    """
    def drop_pymupdf(batch: Path) -> None:
        target = batch / "requirements-renderer.txt"
        kept = [
            line
            for line in target.read_text(encoding="utf-8").splitlines()
            if not line.startswith("PyMuPDF")
        ]
        target.write_text("\n".join(kept) + "\n", encoding="utf-8")

    before, after = _mutating(monkeypatch, tmp_path, drop_pymupdf)
    assert before != after, (
        "PyMuPDF left the install graph and the grader still claims to be the "
        "same grader"
    )


def test_a_comment_in_the_included_file_moves_the_fingerprint(monkeypatch, tmp_path):
    """Any byte, not just a package line. The unit of identity is the file."""
    before, after = _mutating(
        monkeypatch,
        tmp_path,
        lambda batch: (batch / "requirements-renderer.txt").write_text(
            (batch / "requirements-renderer.txt").read_text(encoding="utf-8")
            + "# probe\n",
            encoding="utf-8",
        ),
    )
    assert before != after


def test_the_entry_file_still_moves_it(monkeypatch, tmp_path):
    """The behaviour that already worked must survive the fix."""
    before, after = _mutating(
        monkeypatch,
        tmp_path,
        lambda batch: (batch / "requirements.txt").write_text(
            (batch / "requirements.txt").read_text(encoding="utf-8") + "# probe\n",
            encoding="utf-8",
        ),
    )
    assert before != after


def test_a_requirements_file_outside_the_graph_does_not_move_it(monkeypatch, tmp_path):
    """Negative control: the walker follows the graph, it does not glob a name.

    Globbing ``requirements*.txt`` would pass every test above while freezing
    merges on files pip never opens -- a guard nobody can afford to trust is a
    guard people route around.
    """
    before, after = _mutating(
        monkeypatch,
        tmp_path,
        lambda batch: (batch / "requirements-dev.txt").write_text(
            "pytest>=8.0\n", encoding="utf-8"
        ),
    )
    assert before == after, (
        "a requirements file nothing includes changed the grader's identity"
    )


# ── how the walker behaves on graphs that are not a straight line ────────


def test_a_diamond_include_is_hashed_once(monkeypatch, tmp_path):
    """Two files including a third is pip-legal and must not be a duplicate.

    ``compute_grader_source_hash`` raises on a repeated path, so a walker that
    forgot to de-duplicate would take the whole grading run down rather than
    return a wrong answer -- loud, but still broken.
    """
    batch, config = _fake_batch_runner(tmp_path)
    (batch / "shared.txt").write_text("packaging>=24.0\n", encoding="utf-8")
    (batch / "requirements-renderer.txt").write_text(
        "PyMuPDF>=1.21.0\n-r shared.txt\n", encoding="utf-8"
    )
    (batch / "requirements.txt").write_text(
        "pyyaml>=6.0\n-r requirements-renderer.txt\n-r shared.txt\n", encoding="utf-8"
    )

    digest = _hash_fake(monkeypatch, batch, config)
    assert len(digest) == 64

    closure = step8_grade._requirements_closure(batch, batch / "requirements.txt")
    assert len(closure) == len(set(closure)) == 3


def test_an_include_cycle_terminates(monkeypatch, tmp_path):
    """pip rejects a cycle; this must refuse to hang before pip gets the chance."""
    batch, config = _fake_batch_runner(tmp_path)
    (batch / "requirements-renderer.txt").write_text(
        "PyMuPDF>=1.21.0\n-r requirements.txt\n", encoding="utf-8"
    )
    assert len(_hash_fake(monkeypatch, batch, config)) == 64


def test_the_closure_is_order_independent(monkeypatch, tmp_path):
    """Reordering includes must not change the identity; reordering bytes must.

    The digest sorts by path before hashing, so this is a property of the
    function and not of the order the walker happens to return.
    """
    batch, config = _fake_batch_runner(tmp_path)
    (batch / "extra.txt").write_text("packaging>=24.0\n", encoding="utf-8")

    (batch / "requirements.txt").write_text(
        "-r requirements-renderer.txt\n-r extra.txt\npyyaml>=6.0\n", encoding="utf-8"
    )
    first = _hash_fake(monkeypatch, batch, config)
    (batch / "requirements.txt").write_text(
        "-r requirements-renderer.txt\n-r extra.txt\npyyaml>=6.0\n", encoding="utf-8"
    )
    assert _hash_fake(monkeypatch, batch, config) == first, "not deterministic"

    (batch / "requirements.txt").write_text(
        "-r extra.txt\n-r requirements-renderer.txt\npyyaml>=6.0\n", encoding="utf-8"
    )
    assert _hash_fake(monkeypatch, batch, config) != first, (
        "the entry file's own bytes changed, so the fingerprint must move even "
        "though the set of files reached did not"
    )


@pytest.mark.parametrize(
    "line",
    [
        "-r renderer.txt",
        "-r=renderer.txt",
        "-rrenderer.txt",
        "--requirement renderer.txt",
        "--requirement=renderer.txt",
        "-c renderer.txt",
        "--constraint renderer.txt",
    ],
)
def test_every_spelling_pip_accepts_is_followed(tmp_path, line):
    """Including ``-c``: a constraints file decides which *version* installs.

    A pin moving ``PyMuPDF>=1.21.0`` to 1.21.0 exactly changes what the grader
    can do just as surely as deleting the line, so it belongs to the identity.
    """
    batch, _ = _fake_batch_runner(tmp_path)
    (batch / "renderer.txt").write_text("PyMuPDF>=1.21.0\n", encoding="utf-8")
    (batch / "requirements.txt").write_text(f"pyyaml>=6.0\n{line}\n", encoding="utf-8")

    closure = step8_grade._requirements_closure(batch, batch / "requirements.txt")
    assert (batch / "renderer.txt").resolve() in closure, f"{line!r} was not followed"


@pytest.mark.parametrize(
    "line",
    [
        "requests>=2.0",  # a package, not a directive
        "# -r renderer.txt",  # commented out at line start
        "pyyaml>=6.0  # -r renderer.txt",  # commented out after whitespace
        "-e .",
        "--index-url https://example.invalid/simple",
        "--requirements renderer.txt",  # not a pip option
    ],
)
def test_lines_that_are_not_includes_are_not_followed(tmp_path, line):
    """The other direction: a phantom include freezes merges on nothing."""
    batch, _ = _fake_batch_runner(tmp_path)
    (batch / "renderer.txt").write_text("PyMuPDF>=1.21.0\n", encoding="utf-8")
    (batch / "requirements.txt").write_text(f"{line}\n", encoding="utf-8")

    closure = step8_grade._requirements_closure(batch, batch / "requirements.txt")
    assert closure == [(batch / "requirements.txt").resolve()], (
        f"{line!r} was read as an include"
    )


# ── where the comment rule actually bites ────────────────────────────────
#
# Neither commented-out case above can tell whether comments are stripped at
# all: the pattern is anchored at the start of the line, so ``# -r x`` and
# ``pyyaml  # -r x`` are refused by the anchor whether or not the ``#`` was
# removed first. A mutation that deleted the stripping entirely passed both.
# The rule is only observable on a line that *is* an include, in the two
# directions below.


def test_a_trailing_comment_does_not_hide_the_include(tmp_path):
    """``-r renderer.txt  # renderer deps`` is still an include.

    Without the strip the path would run to end-of-line, the pattern would
    fail to match, and the included file would drop out of the identity in
    silence -- the exact defect this file exists to keep closed, reintroduced
    by the day someone annotates the include.
    """
    batch, _ = _fake_batch_runner(tmp_path)
    (batch / "renderer.txt").write_text("PyMuPDF>=1.21.0\n", encoding="utf-8")
    (batch / "requirements.txt").write_text(
        "-r renderer.txt  # renderer deps, shared with the CI preflight\n",
        encoding="utf-8",
    )

    closure = step8_grade._requirements_closure(batch, batch / "requirements.txt")
    assert (batch / "renderer.txt").resolve() in closure, (
        "an annotated include was not followed"
    )


def test_a_hash_with_no_space_before_it_is_part_of_the_filename(tmp_path):
    """pip's rule, not ``split('#')``.

    A ``#`` only opens a comment at the start of a line or after whitespace.
    That is what leaves ``...git#egg=name`` fragments intact, and it means a
    file whose name contains a ``#`` is reached normally. Splitting on the
    first ``#`` instead would silently hash a different file -- or none.
    """
    batch, _ = _fake_batch_runner(tmp_path)
    odd = batch / "renderer#1.txt"
    odd.write_text("PyMuPDF>=1.21.0\n", encoding="utf-8")
    (batch / "requirements.txt").write_text("-r renderer#1.txt\n", encoding="utf-8")

    closure = step8_grade._requirements_closure(batch, batch / "requirements.txt")
    assert odd.resolve() in closure, "the '#' was treated as a comment marker"


# ── failure modes: every one of them fails closed ────────────────────────


def test_an_include_that_is_not_on_disk_raises_and_names_the_includer(
    monkeypatch, tmp_path
):
    """A broken graph is a different finding from a package being absent.

    Silently skipping would put the fingerprint back where it started, and the
    operator would be told nothing at all.
    """
    batch, config = _fake_batch_runner(tmp_path)
    (batch / "requirements.txt").write_text("-r gone.txt\n", encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        _hash_fake(monkeypatch, batch, config)
    message = str(caught.value)
    assert "gone.txt" in message
    assert "requirements.txt" in message, (
        "the error must say which file asked for the missing one, or it sends "
        "the reader to the wrong place"
    )


def test_an_include_outside_batch_runner_is_refused(monkeypatch, tmp_path):
    """The containment rule every other hashed path already obeys."""
    batch, config = _fake_batch_runner(tmp_path)
    (batch.parent / "outside.txt").write_text("evil>=1.0\n", encoding="utf-8")
    (batch / "requirements.txt").write_text("-r ../outside.txt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside batch-runner"):
        _hash_fake(monkeypatch, batch, config)


def test_an_include_pointing_at_a_symlink_is_refused(monkeypatch, tmp_path):
    """A symlink is how a hashed path stops describing the bytes that ran."""
    batch, config = _fake_batch_runner(tmp_path)
    (batch / "real.txt").write_text("PyMuPDF>=1.21.0\n", encoding="utf-8")
    try:
        (batch / "linked.txt").symlink_to(batch / "real.txt")
    except (OSError, NotImplementedError):  # pragma: no cover - platform guard
        pytest.skip("this filesystem cannot create symlinks")
    (batch / "requirements.txt").write_text("-r linked.txt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="symlink"):
        _hash_fake(monkeypatch, batch, config)


def test_the_entry_file_missing_still_raises_without_an_includer(monkeypatch, tmp_path):
    """The ``includer is None`` branch: no provenance to add, so add none."""
    batch, config = _fake_batch_runner(tmp_path)
    (batch / "requirements.txt").unlink()

    with pytest.raises(ValueError) as caught:
        _hash_fake(monkeypatch, batch, config)
    assert "pulled in by" not in str(caught.value)


# ── the three mirrors that decide when a merge is frozen ─────────────────


def test_the_freeze_predicate_knows_the_included_file():
    """Otherwise a pull request dropping PyMuPDF merges into a live run."""
    import scripts.check_grader_hash_freeze as freeze

    assert freeze.is_grader_source_path("batch-runner/requirements-renderer.txt")
    assert freeze.is_grader_source_path("batch-runner/requirements.txt")
    # Negative control: the predicate is not simply saying yes to everything
    # with 'requirements' in it.
    assert not freeze.is_grader_source_path("batch-runner/tests/test_grader.py")


def test_the_freeze_workflow_starts_for_the_included_file():
    """A guard that never runs on the change it guards against is decoration."""
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/grader-hash-freeze.yml").read_text(
            encoding="utf-8"
        )
    )
    # PyYAML reads a bare `on:` key as the boolean True.
    triggers = workflow.get("on") or workflow[True]
    assert "batch-runner/requirements-renderer.txt" in triggers["pull_request"]["paths"]


def test_the_paid_run_pin_covers_the_included_file():
    """Editing it mid-run changes the grader, so it must stop the chunk."""
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/grade-run.yml").read_text(encoding="utf-8")
    )
    steps = [s for job in workflow["jobs"].values() for s in job.get("steps", [])]
    found = 0
    for step in steps:
        run = step.get("run") or ""
        if "GRADING_INPUT_PATHS=(" not in run:
            continue
        found += 1
        block = run.split("GRADING_INPUT_PATHS=(", 1)[1].split(")", 1)[0]
        paths = [line.strip() for line in block.splitlines() if line.strip()]
        assert "batch-runner/requirements-renderer.txt" in paths, (
            f"{step.get('name')!r} does not pin the -r include"
        )
        assert paths == sorted(paths), f"{step.get('name')!r} pin is out of order"
    assert found == 2, f"expected the paid and dry-run pins, found {found}"


# ── the framing, so a future change to it is a decision ──────────────────


def test_the_digest_still_frames_each_file_with_its_length_and_path(
    monkeypatch, tmp_path
):
    """Reproduce the digest by hand for the fake tree.

    Adding files to a hash is only safe while the framing is unambiguous: with
    lengths and paths written in, no rename or content shuffle can produce a
    second tree with the same digest. Growing the file set without checking
    that would be trading one silent collision for another.
    """
    batch, config = _fake_batch_runner(tmp_path)
    produced = _hash_fake(monkeypatch, batch, config)

    names = [
        "batch-runner/core/grader.py",
        "batch-runner/requirements-renderer.txt",
        "batch-runner/requirements.txt",
        "batch-runner/schemas/grade.schema.json",
        "batch-runner/scripts/download_inference_from_hf.py",
        "batch-runner/step8_grade.py",
        "batch-runner/prompts/judge.md",
    ]
    on_disk = {name: batch.parent / name for name in names}
    on_disk["batch-runner/grading_configs/c.yaml"] = config

    expected = hashlib.sha256()
    expected.update(b"gdpval-grader-source-v1\x00")
    for name, path in sorted(on_disk.items()):
        label = name.encode("utf-8")
        content = path.read_bytes()
        expected.update(len(label).to_bytes(8, "big"))
        expected.update(label)
        expected.update(len(content).to_bytes(8, "big"))
        expected.update(content)
    assert produced == expected.hexdigest()
