"""The counts under a published rate, recovered without re-grading.

``step8_grade`` now emits ``summary.wow.item_counts`` beside the five ``wow``
rates, so a ``0.0`` can be read as "none passed" or "none existed". It emits
them only for runs graded after that change, and nothing re-grades a published
file. On the corpus committed here **not one payload carries them**, and the
distinction is unrecoverable for every run already published -- while twenty
of the thirty-three payloads publish ``precheck_pass_rate: 0.0`` and all
twenty prechecked nothing. Among them is the 185-task gold ceiling: 8,816
judged items, zero prechecked, published as a 0% structural pass rate.

They are recoverable, because the counters are a pure function of the
``tasks`` array already in the file. That is the same basis the four analytic
fields are rebuilt from, so ``backfill_summary_wow.py`` rebuilds these too and
gates them the same way.

What is pinned here is the gate rather than the arithmetic: counts arrive only
where the current summariser still reproduces the file's published rates, a
denominator of zero is written as ``0`` rather than omitted, no published
number moves at any depth, and a file whose bytes another document has
already vouched for is refused outright.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import backfill_summary_wow as backfill  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "backfill_summary_wow.py"
GRADES_ROOT = REPO_ROOT / "data" / "grades"

#: The 185-task gold-ceiling cohort. Named because it is the run this change
#: exists for: the flat ``glob("*.json")`` this walk replaced never reached it.
GOLD_CEILING_COHORT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)


# --------------------------------------------------------------------------
# fixtures: the smallest payloads that exercise each branch
# --------------------------------------------------------------------------


def _item(rid: str, weight: int, awarded: float, verdict: str, decided_by: str):
    return {
        "rubric_item_id": rid,
        "criterion": "c",
        "max_score": weight,
        "awarded_score": awarded,
        "verdict": verdict,
        "decided_by": decided_by,
        "required": None,
        "evidence": "e",
        "model_did_right": verdict == "pass",
    }


def _task(tid: str, items: list[dict], sector: str = "Finance"):
    return {
        "task_id": tid,
        "sector": sector,
        "occupation": "o",
        "items": items,
        "total_awarded": sum(i["awarded_score"] for i in items),
        "total_max": sum(max(i["max_score"], 0) for i in items),
        "pct": 50.0,
        "critical_fail": False,
        "gold_referenced": False,
        "judge_call_count": 1,
        "precheck_count": sum(1 for i in items if i["decided_by"] == "precheck"),
        "judge_total_latency_ms": 1,
        "judge_input_tokens": 1,
        "judge_output_tokens": 1,
        "error": None,
        "graded_at": "2026-05-29T00:00:00Z",
    }


def _payload(tasks: list[dict], **wow_overrides) -> dict:
    """A grade file as published *before* counts existed.

    The five rates are the ones the current summariser computes, so the file
    agrees with itself and the semantics gate opens. ``item_counts`` is absent,
    which is the state every committed payload is in.
    """
    computed = backfill._compute_summary(tasks)["wow"]
    wow = {k: computed[k] for k in backfill.SCALAR_RATES}
    wow.update(
        {
            "by_sector": {},
            "by_rubric_category": {},
            "score_density_histogram": [],
            "rubric_severity_curve": [],
        }
    )
    wow.update(wow_overrides)
    return {
        "schema_version": "1.2",
        "experiment_id": "exp_test",
        "experiment_yaml_name": "exp_test",
        "tasks": tasks,
        "summary": {
            "total_tasks": len(tasks),
            "graded_tasks": len(tasks),
            "error_tasks": 0,
            "openai_compat": {"avg_score_pct": 50.0},
            "wow": wow,
        },
    }


#: Judged and prechecked. Every denominator is non-empty.
MEASURED = [
    _task(
        "t1",
        [
            _item("r1", 10, 10, "pass", "judge"),
            _item("r2", 5, 0, "fail", "judge"),
            _item("r3", 4, 4, "pass", "precheck"),
        ],
    )
]

#: Judged, never prechecked -- the shape twenty committed payloads are in.
#: ``precheck_pass_rate`` comes out ``0.0`` from an empty denominator.
NEVER_PRECHECKED = [
    _task(
        "t1",
        [
            _item("r1", 10, 10, "pass", "judge"),
            _item("r2", 5, 0, "fail", "judge"),
        ],
    )
]


def _write(dirpath: Path, name: str, payload: dict) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / name
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def _run(grades_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(grades_dir), *args],
        capture_output=True,
        text=True,
    )


def _wow(path: Path) -> dict:
    return json.loads(path.read_text())["summary"]["wow"]


# --------------------------------------------------------------------------
# the counts arrive, and an empty denominator is legible as empty
# --------------------------------------------------------------------------


def test_a_published_file_gets_back_the_denominators_it_discarded(tmp_path: Path):
    path = _write(tmp_path, "measured.json", _payload(MEASURED))
    assert "item_counts" not in _wow(path)

    result = _run(tmp_path, "--apply")
    assert result.returncode == 0, result.stderr

    assert _wow(path)["item_counts"] == {
        "rubric_items": 3,
        "critical_items": 3,
        "precheck_items": 1,
        "judge_items": 2,
    }


def test_a_run_that_prechecked_nothing_now_says_nothing_rather_than_zero(
    tmp_path: Path,
):
    """The whole point, on the shape twenty committed payloads are in.

    The rate stays ``0.0`` -- it is published, and moving it is out of bounds.
    What changes is that ``precheck_items: 0`` sits beside it, so the reader
    can tell "no precheck passed" from "no precheck ran". Writing the counts
    but dropping the zero entries would lose exactly the case they exist for.
    """
    path = _write(tmp_path, "unprechecked.json", _payload(NEVER_PRECHECKED))
    before = _wow(path)
    assert before["precheck_pass_rate"] == 0.0

    assert _run(tmp_path, "--apply").returncode == 0

    after = _wow(path)
    assert after["precheck_pass_rate"] == 0.0, "a published rate moved"
    assert after["item_counts"]["precheck_items"] == 0
    assert after["item_counts"]["judge_items"] == 2


def test_the_zero_denominator_is_reported_out_loud(tmp_path: Path):
    """A dry run has to name what was never measured, or nobody looks."""
    _write(tmp_path, "unprechecked.json", _payload(NEVER_PRECHECKED))

    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "nothing measured for ['precheck_items']" in result.stdout


# --------------------------------------------------------------------------
# the semantics gate: counts are a denominator, so they follow the rates
# --------------------------------------------------------------------------


def test_counts_are_withheld_where_the_summariser_no_longer_agrees(
    tmp_path: Path,
):
    """A recomputed denominator under a published numerator is a fiction.

    These are the pre-sign-aware files: no ``model_did_right``, so
    ``critical_item_pass_rate`` recomputes to ``0.0`` against a published
    ``0.5``. The file is written under the old semantics and the summariser
    reads it under the new ones. Attaching this summariser's count to that
    file's rate would state a fraction nobody ever computed -- worse than
    leaving it absent, because absent at least reads as unknown.
    """
    tasks = json.loads(json.dumps(MEASURED))
    for item in tasks[0]["items"]:
        item.pop("model_did_right")
    payload = _payload(tasks, critical_item_pass_rate=0.5)
    path = _write(tmp_path, "presign.json", payload)

    result = _run(tmp_path, "--apply")
    assert result.returncode == 0, result.stderr

    after = _wow(path)
    assert after["critical_item_pass_rate"] == 0.5, "a published rate moved"
    assert "item_counts" not in after, (
        "counts were attached to a file whose rates this summariser cannot "
        "reproduce, so the fraction they complete was never computed by anyone"
    )
    assert after["score_density_histogram"], (
        "the semantics-free field should still have been written"
    )


# --------------------------------------------------------------------------
# no published number moves, at any depth
# --------------------------------------------------------------------------


def test_no_published_rate_is_ever_in_the_writable_set(tmp_path: Path):
    """Guard 2 is a runtime backstop for a property held statically here.

    Nothing the script writes can move a top-level rate, because the five
    rates are in none of the writable tuples -- which is why Guard 2 cannot
    fire today and why asserting on it directly would prove nothing. The
    failure it guards against is a future edit adding a field to one of those
    tuples without noticing it is published. That is what this reads.
    """
    writable = (
        set(backfill.ANALYTIC_FIELDS)
        | set(backfill.COUNT_FIELDS)
        | set(backfill.SEMANTICS_FREE_FIELDS)
    )
    overlap = writable & set(backfill.SCALAR_RATES)

    assert not overlap, (
        f"{sorted(overlap)} is both published and rewritten by this script; "
        "recomputing it would restate a number the corpus already asserts"
    )

    # And the guard that would catch it at runtime is still wired.
    path = _write(tmp_path, "measured.json", _payload(MEASURED))
    assert backfill.backfill_one(path, apply=False)["status"] == "would-write"


def test_a_moved_per_sector_rate_aborts_the_file(tmp_path: Path):
    """Guard 3. ``by_sector`` is rewritten wholesale and each row carries the
    same rates as the block above it, which ``SectorHeatmap.tsx`` renders.
    Guard 2 reads only the top level, so without this the script's stated
    property was being enforced one level shallower than it was written.
    """
    payload = _payload(MEASURED)
    payload["summary"]["wow"]["by_sector"] = {
        "Finance": {
            "task_count": 1,
            "avg_pct": 50.0,
            "critical_item_pass_rate": 0.99,  # published; recomputes to 0.6667
            "precheck_pass_rate": 1.0,
            "judge_pass_rate": 0.5,
        }
    }
    path = _write(tmp_path, "sector.json", payload)
    before = path.read_text()

    report = backfill.backfill_one(path, apply=True)

    assert report["status"] == "ABORTED"
    assert "Finance.critical_item_pass_rate" in report["reason"]
    assert path.read_text() == before, "an aborted file must not be written"


def test_a_sector_row_gaining_only_counts_is_not_treated_as_a_move(
    tmp_path: Path,
):
    """The negative control for the guard above.

    Every published ``by_sector`` row lacks ``item_counts``, and recomputation
    adds one. If Guard 3 counted that as a move it would abort all
    twenty-seven writable files and the guard would look like it was working.
    It does not, because the comparison walks the *published* row: a key the
    file never had is never reached.
    """
    payload = _payload(MEASURED)
    computed = backfill._compute_summary(MEASURED)["wow"]["by_sector"]
    payload["summary"]["wow"]["by_sector"] = {
        sector: {k: v for k, v in row.items() if k != "item_counts"}
        for sector, row in computed.items()
    }
    path = _write(tmp_path, "sector_ok.json", payload)

    report = backfill.backfill_one(path, apply=True)

    assert report["status"] == "written"
    assert _wow(path)["by_sector"]["Finance"]["item_counts"]["precheck_items"] == 1


def test_a_sector_count_that_was_already_published_may_not_change(
    tmp_path: Path,
):
    """A count is a published number too, once a file carries one.

    Rows written by a post-counts grader arrive with ``item_counts`` already
    in them. Nothing in scope today is in that state, which is exactly why it
    needs pinning: the easy way to let a row gain counts is to exempt the key
    from the comparison, and that would also let an existing one be quietly
    restated.
    """
    payload = _payload(MEASURED)
    computed = backfill._compute_summary(MEASURED)["wow"]["by_sector"]
    payload["summary"]["wow"]["by_sector"] = json.loads(json.dumps(computed))
    payload["summary"]["wow"]["by_sector"]["Finance"]["item_counts"][
        "precheck_items"
    ] = 99
    path = _write(tmp_path, "sector_counts.json", payload)
    before = path.read_text()

    report = backfill.backfill_one(path, apply=True)

    assert report["status"] == "ABORTED"
    assert "Finance.item_counts" in report["reason"]
    assert path.read_text() == before


def test_nothing_outside_the_wow_block_is_touched(tmp_path: Path):
    path = _write(tmp_path, "measured.json", _payload(MEASURED))
    before = json.loads(path.read_text())

    assert _run(tmp_path, "--apply").returncode == 0

    after = json.loads(path.read_text())
    before["summary"].pop("wow")
    after["summary"].pop("wow")
    assert before == after


def test_a_dry_run_writes_nothing(tmp_path: Path):
    path = _write(tmp_path, "measured.json", _payload(MEASURED))
    before = path.read_text()

    result = _run(tmp_path)

    assert result.returncode == 0
    assert path.read_text() == before
    assert "dry run" in result.stdout


# --------------------------------------------------------------------------
# scope: which files the walk reaches
# --------------------------------------------------------------------------


def test_the_walk_descends_into_the_cohort_directories(tmp_path: Path):
    """The flat glob this replaced reached eighteen files and none of the
    diagnostic cohorts, so the corpus's clearest instance of the defect was
    also the one instance the tool could not touch."""
    nested = _write(
        tmp_path / "_diagnostic" / "abc123" / "_repeats" / "run-002",
        "grade.json",
        _payload(NEVER_PRECHECKED),
    )

    assert _run(tmp_path, "--apply").returncode == 0

    assert "item_counts" in _wow(nested)


def test_shards_stay_out_of_scope(tmp_path: Path):
    """A shard is an intermediate ``step9`` merges into the payload beside it.
    Rewriting both would restate one run twice."""
    shard = _write(
        tmp_path / "_diagnostic" / "abc123" / "_shards",
        "shard-000-of-011.json",
        _payload(MEASURED),
    )
    merged = _write(tmp_path / "_diagnostic" / "abc123", "grade.json", _payload(MEASURED))

    assert _run(tmp_path, "--apply").returncode == 0

    assert "item_counts" not in _wow(shard)
    assert "item_counts" in _wow(merged)


def test_the_named_exclusion_still_applies(tmp_path: Path):
    excluded = _write(tmp_path, "dummy_gpt5_baseline.json", _payload(MEASURED))
    kept = _write(tmp_path, "real.json", _payload(MEASURED))
    assert backfill.EXCLUDED == {"dummy_gpt5_baseline.json"}

    assert _run(tmp_path, "--apply").returncode == 0

    assert "item_counts" not in _wow(excluded)
    assert "item_counts" in _wow(kept)


# --------------------------------------------------------------------------
# the digest seal: bytes another document has already vouched for
# --------------------------------------------------------------------------


def _tree(root: Path, documents: dict[str, str], track: bool = True) -> Path:
    """A real git repository holding ``documents``, for git to be asked about.

    Real, not a stub. The predecessor of this code kept a hand-written list of
    protected paths and a test asserted its length, so the test agreed with the
    list and neither agreed with the tree -- the first ``--apply`` rewrote two
    sealed files and four unrelated tests were what noticed. A fake ``git grep``
    here would reproduce that exact failure at one remove.
    """
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name, text in documents.items():
        doc = root / name
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(text)
    if track:
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


def test_a_document_that_states_a_files_digest_refuses_the_write(tmp_path: Path):
    """Rewriting the file would not make that document stale. It would make it
    false -- asserting a hash the bytes no longer have."""
    root = tmp_path / "repo"
    payload = _write(root / "data" / "grades", "sealed.json", _payload(MEASURED))
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    _tree(root, {"EVIDENCE.md": f"reproduced at sha256 {digest}\n"})
    before = payload.read_text()

    report = backfill.backfill_one(payload, apply=True, tree=root)

    assert report["status"] == "sealed"
    assert "EVIDENCE.md" in report["reason"], (
        "naming the document is the point -- the next person has to be able to "
        f"read what it claims before moving it; got {report['reason']!r}"
    )
    assert payload.read_text() == before


def test_the_same_file_is_written_when_nothing_vouches_for_it(tmp_path: Path):
    """The negative control. Without it the test above passes just as well
    against a function that refuses everything."""
    root = tmp_path / "repo"
    payload = _write(root / "data" / "grades", "free.json", _payload(MEASURED))
    _tree(root, {"EVIDENCE.md": "no digests here\n"})

    report = backfill.backfill_one(payload, apply=True, tree=root)

    assert report["status"] == "written"
    # MEASURED prechecks exactly one of its three items. The seal is the only
    # thing separating this file from the one above, so the recovered
    # denominator has to actually appear.
    assert _wow(payload)["item_counts"]["precheck_items"] == 1


def test_a_digest_abbreviated_to_sixteen_characters_still_seals(tmp_path: Path):
    """The case that got past the first version and rewrote a sealed file.

    ``PR3_REPEAT_VARIATION.md`` records the runs it compared as ``sha256``
    followed by sixteen characters, the way a person writes a hash they expect
    someone to eyeball. Searching for the full sixty-four found three of the six
    sealed payloads and missed those three entirely.
    """
    root = tmp_path / "repo"
    payload = _write(root / "data" / "grades", "abbrev.json", _payload(MEASURED))
    short = hashlib.sha256(payload.read_bytes()).hexdigest()[:16]
    _tree(root, {"PR3_REPEAT_VARIATION.md": f"run-002  final  sha256 {short}\n"})

    report = backfill.backfill_one(payload, apply=True, tree=root)

    assert report["status"] == "sealed"
    assert "PR3_REPEAT_VARIATION.md" in report["reason"]


def test_sixteen_characters_is_not_reaching_far_enough_to_invent_seals(
    tmp_path: Path,
):
    """Sixty-four bits of prefix, and the reach is checked rather than assumed.

    On the real corpus this flags the same six files that twelve characters
    does, so the extra reach buys no false positives. Here: a digest that shares
    the first eight characters and diverges inside the sixteen is a different
    file and must not seal.
    """
    root = tmp_path / "repo"
    payload = _write(root / "data" / "grades", "near.json", _payload(MEASURED))
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    near_miss = digest[:8] + "".join("f" if c != "f" else "0" for c in digest[8:16])
    assert near_miss != digest[:16]
    _tree(root, {"EVIDENCE.md": f"sha256 {near_miss}\n"})

    assert backfill.documents_asserting(payload, root) == []


def test_an_untracked_note_does_not_seal_anything(tmp_path: Path):
    """An untracked document asserting a digest is somebody's working note, not
    a committed claim. Honouring it would make the refusal depend on what
    happens to be lying around in the directory."""
    root = tmp_path / "repo"
    payload = _write(root / "data" / "grades", "free.json", _payload(MEASURED))
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    _tree(root, {"scratch.md": f"sha256 {digest}\n"}, track=False)

    assert backfill.documents_asserting(payload, root) == []


def test_a_seal_may_live_beside_the_file_it_vouches_for(tmp_path: Path):
    """Not a hypothetical: three of the six real seals are asserted by
    ``data/grades/_validation/PR3_REPEAT_VARIATION.md``, which the walk itself
    steps over. Being inside the walked tree does not make a document less of
    an assertion."""
    root = tmp_path / "repo"
    grades = root / "data" / "grades"
    payload = _write(grades, "run-002.json", _payload(MEASURED))
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()[:16]
    _tree(root, {"data/grades/_validation/REPEATS.md": f"sha256 {digest}\n"})

    assert backfill.documents_asserting(payload, root) == [
        "data/grades/_validation/REPEATS.md"
    ]


def test_a_tree_that_cannot_be_asked_refuses_every_write(tmp_path: Path):
    """Fail closed. A script that cannot find out what is sealed has no
    business concluding that nothing is."""
    not_a_repo = tmp_path / "plain"
    payload = _write(not_a_repo / "data" / "grades", "x.json", _payload(MEASURED))
    before = payload.read_text()

    with pytest.raises(SystemExit) as excinfo:
        backfill.backfill_one(payload, apply=True, tree=not_a_repo)

    assert "Refusing" in str(excinfo.value)
    assert payload.read_text() == before


def test_git_being_absent_refuses_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The other way the question can go unanswered.

    A tree that is not a repository comes back as exit 128, which the check
    above covers. A missing ``git`` binary never reaches an exit code at all --
    it raises ``OSError`` out of ``subprocess.run`` -- and an ``except`` that
    swallowed it would read as "nothing is sealed" on a host where nothing
    could be checked.
    """
    payload = _write(tmp_path, "x.json", _payload(MEASURED))

    def no_git(*args, **kwargs):
        raise OSError(2, "No such file or directory: 'git'")

    monkeypatch.setattr(backfill.subprocess, "run", no_git)

    with pytest.raises(SystemExit) as excinfo:
        backfill.backfill_one(payload, apply=True)

    assert "Refusing" in str(excinfo.value)


# --------------------------------------------------------------------------
# --unseal: the one way past the refusal, and what it owes in return
# --------------------------------------------------------------------------
#
# The refusal above is correct and it is also terminal: five payloads on this
# tree were sealed at digests that predate ``item_counts``, and no amount of
# re-running gets the denominators into them. Something has to be able to say
# "rewrite this one, I will move the digest".
#
# What makes that safe is not the flag being hard to type. It is that the flag
# cannot be aimed at a file the tree does not already vouch for, and that it
# hands back both digests -- the one every document still states and the one
# they have to state instead. An unseal that quietly rewrites a file and says
# nothing has not removed the lie; it has moved it somewhere harder to find.


def _sealed_fixture(tmp_path: Path, name: str = "sealed.json"):
    """A payload, a tracked document stating its digest, and the digest."""
    root = tmp_path / "repo"
    payload = _write(root / "data" / "grades", name, _payload(MEASURED))
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    _tree(root, {"EVIDENCE.md": f"reproduced at sha256 {digest}\n"})
    return root, payload, digest


def _different_payload(dirpath: Path, name: str, unlike: Path) -> Path:
    """A second payload, with the difference from ``unlike`` asserted out loud.

    The first draft of these fixtures reached for
    ``_payload(MEASURED, judge_pass_rate=0.5)`` as "some other payload" -- and
    the computed ``judge_pass_rate`` already *was* 0.5, so the file came out
    byte-identical to the sealed one. It inherited that digest, the document
    vouched for it, and the test asserting a stale path gets refused failed:
    the path was not stale, and the code was right to write it. A fixture whose
    two files are supposed to differ has to say so, or a test can read like a
    bug in the thing it is testing.
    """
    path = _write(dirpath, name, _payload(NEVER_PRECHECKED))
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        != hashlib.sha256(unlike.read_bytes()).hexdigest()
    ), f"degenerate fixture: {name} has the same digest as {unlike.name}"
    return path


def test_unseal_writes_the_file_the_seal_was_refusing(tmp_path: Path):
    root, payload, _ = _sealed_fixture(tmp_path)

    report = backfill.backfill_one(
        payload, apply=True, tree=root, unseal=frozenset({payload.resolve()})
    )

    assert report["status"] == "unsealed"
    assert _wow(payload)["item_counts"]["precheck_items"] == 1


def test_unseal_hands_back_both_digests(tmp_path: Path):
    """The before is what the document says today; the after is what it has to
    say now. Getting either wrong makes the operator's next edit wrong."""
    root, payload, digest = _sealed_fixture(tmp_path)

    report = backfill.backfill_one(
        payload, apply=True, tree=root, unseal=frozenset({payload.resolve()})
    )

    assert report["sha_before"] == digest, (
        "the before-digest has to match what EVIDENCE.md actually states, or "
        "the operator searches for a string that is not there"
    )
    assert report["sha_after"] == hashlib.sha256(payload.read_bytes()).hexdigest()
    assert report["sha_after"] != report["sha_before"]
    assert report["vouchers"] == ["EVIDENCE.md"]


def test_a_dry_run_unseal_rehearses_without_writing(tmp_path: Path):
    """Both digests before anything is on disk. Otherwise the only way to find
    out what an unseal would do is to do it."""
    root, payload, digest = _sealed_fixture(tmp_path)
    before = payload.read_text()

    report = backfill.backfill_one(
        payload, apply=False, tree=root, unseal=frozenset({payload.resolve()})
    )

    assert report["status"] == "would-unseal"
    assert payload.read_text() == before
    assert report["sha_before"] == digest
    assert report["sha_after"] != digest
    # and the rehearsed after-digest is the one an --apply actually produces
    backfill.backfill_one(
        payload, apply=True, tree=root, unseal=frozenset({payload.resolve()})
    )
    assert hashlib.sha256(payload.read_bytes()).hexdigest() == report["sha_after"]


def test_unseal_reaches_only_the_file_it_names(tmp_path: Path):
    """Naming one sealed file must not open the others.

    Five of the six seals on this tree moved together and the sixth did not.
    A flag that unsealed the whole run would have rewritten a payload whose
    digest is pinned in a test that had no reason to change.
    """
    root = tmp_path / "repo"
    grades = root / "data" / "grades"
    named = _write(grades, "named.json", _payload(MEASURED))
    other = _different_payload(grades, "other.json", unlike=named)
    _tree(root, {
        "EVIDENCE.md": (
            f"named  sha256 {hashlib.sha256(named.read_bytes()).hexdigest()}\n"
            f"other  sha256 {hashlib.sha256(other.read_bytes()).hexdigest()}\n"
        )
    })
    other_before = other.read_text()

    reports = {
        p.name: backfill.backfill_one(
            p, apply=True, tree=root, unseal=frozenset({named.resolve()})
        )
        for p in (named, other)
    }

    assert reports["named.json"]["status"] == "unsealed"
    assert reports["other.json"]["status"] == "sealed"
    assert other.read_text() == other_before


def test_unseal_is_idempotent_once_the_operator_moves_the_digest(tmp_path: Path):
    """The seal comes back. It is a seal at a new digest, not a hole.

    This is the whole shape of the change on the real tree: five payloads
    rewritten, five documents updated, and ``documents_asserting`` finding the
    same files refused on the next run.
    """
    root, payload, digest = _sealed_fixture(tmp_path)
    report = backfill.backfill_one(
        payload, apply=True, tree=root, unseal=frozenset({payload.resolve()})
    )

    doc = root / "EVIDENCE.md"
    doc.write_text(doc.read_text().replace(digest, report["sha_after"]))
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)

    after = payload.read_text()
    again = backfill.backfill_one(payload, apply=True, tree=root)

    assert again["status"] == "sealed"
    assert "EVIDENCE.md" in again["reason"]
    assert payload.read_text() == after


def test_a_second_unseal_changes_nothing(tmp_path: Path):
    """Running it twice without moving the digest is not a second rewrite.

    The counts are a pure function of the task rows, so the second pass has
    nothing to add. If this ever produced a third digest, every document
    updated from the first run would be wrong again.
    """
    root, payload, _ = _sealed_fixture(tmp_path)
    unseal = frozenset({payload.resolve()})
    first = backfill.backfill_one(payload, apply=True, tree=root, unseal=unseal)
    settled = payload.read_bytes()

    second = backfill.backfill_one(payload, apply=True, tree=root, unseal=unseal)

    assert payload.read_bytes() == settled
    assert second["status"] in ("unchanged", "unsealed")
    if second["status"] == "unsealed":
        assert second["sha_after"] == first["sha_after"]


def test_unseal_refuses_a_path_nothing_vouches_for(tmp_path: Path):
    """A stale operator model is a hard stop, not a no-op.

    Naming a file no document asserts means the path is a typo, or the seal
    already moved, or somebody else updated the document first. Each makes the
    rest of the invocation untrustworthy, and this is the one flag a person
    reaches for while holding a list of digests to paste.
    """
    root = tmp_path / "repo"
    payload = _write(root / "data" / "grades", "free.json", _payload(MEASURED))
    _tree(root, {"EVIDENCE.md": "no digests here\n"})
    before = payload.read_text()

    with pytest.raises(SystemExit) as excinfo:
        backfill._resolve_unseal([payload], root)

    assert "nothing here to unseal" in str(excinfo.value)
    assert payload.read_text() == before


def test_unseal_refuses_a_path_that_is_not_there(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "data" / "grades", "real.json", _payload(MEASURED))
    _tree(root, {"EVIDENCE.md": "x\n"})

    with pytest.raises(SystemExit) as excinfo:
        backfill._resolve_unseal([root / "data" / "grades" / "typo.json"], root)

    assert "no such file" in str(excinfo.value)


def test_one_bad_path_stops_the_whole_run(tmp_path: Path):
    """Fail closed across the batch, not per file.

    The real invocation named six paths at once. If a typo in the fourth one
    let the first three through, the run would have written three files and
    printed three digests to paste into documents -- while the operator's
    reason for believing the fourth was sealed had just been shown wrong.
    """
    root, payload, _ = _sealed_fixture(tmp_path)
    before = payload.read_text()

    with pytest.raises(SystemExit):
        backfill._resolve_unseal(
            [payload, root / "data" / "grades" / "typo.json"], root
        )

    assert payload.read_text() == before


def test_without_the_flag_the_same_file_is_still_refused(tmp_path: Path):
    """The negative control. Without it every test above passes against a
    build that stopped sealing anything at all."""
    root, payload, _ = _sealed_fixture(tmp_path)
    before = payload.read_text()

    report = backfill.backfill_one(payload, apply=True, tree=root)

    assert report["status"] == "sealed"
    assert payload.read_text() == before


def test_the_cli_carries_the_flag_through(tmp_path: Path):
    """Everything above calls the function. The operator types the command."""
    root, payload, digest = _sealed_fixture(tmp_path)
    before = payload.read_text()

    result = _run(
        root / "data" / "grades",
        "--tree", str(root),
        "--unseal", str(payload),
    )

    assert result.returncode == 0, result.stderr
    assert "would-unseal" in result.stdout
    assert digest in result.stdout, "the digest to search for has to be printed"
    assert "EVIDENCE.md" in result.stdout
    assert payload.read_text() == before, (
        "a dry run through the CLI still writes nothing"
    )


def test_the_cli_refuses_a_stale_path_before_touching_anything(tmp_path: Path):
    root, payload, _ = _sealed_fixture(tmp_path)
    free = _different_payload(root / "data" / "grades", "free.json", unlike=payload)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    before = payload.read_text()

    result = _run(
        root / "data" / "grades",
        "--apply",
        "--tree", str(root),
        "--unseal", str(free),
    )

    assert result.returncode == 1
    assert "nothing here to unseal" in result.stderr
    assert payload.read_text() == before, (
        "the refusal has to come before the walk, or a bad --unseal still "
        "rewrites every unsealed file in the tree"
    )


def test_the_committed_backfill_added_denominators_and_nothing_else():
    """What actually landed in the diff, read off the committed tree.

    #188 introduced this script and ran it, so the analytic fields it was
    written for are already populated wherever they legitimately can be.
    Re-running it today recovers ``item_counts`` and touches nothing else --
    but "nothing else" is a claim about a diff, and a docstring cannot hold a
    diff honest. This reads every payload and checks that the only ``wow`` key
    it carries beyond what ``_compute_summary`` would refuse is the one this
    change is for.

    The counts moved once, when the five sealed payloads were unsealed and
    backfilled: 22 -> 27 payloads, 62 -> 86 sector rows (21 existing rows
    gained denominators and the anchor payload gained three rows it never
    had), and one fewer empty ``by_sector`` for that same anchor. Every one of
    those deltas is a file this suite can name.
    """
    grades = REPO_ROOT / "data" / "grades"
    carried, sector_rows, empty_analytics = 0, 0, 0
    for path in backfill.collect_grade_files(grades):
        payload = json.loads(path.read_text())
        if not isinstance(payload.get("tasks"), list):
            continue
        wow = (payload.get("summary") or {}).get("wow") or {}
        if "item_counts" in wow:
            carried += 1
            counts = wow["item_counts"]
            assert set(counts) == {
                "rubric_items",
                "critical_items",
                "precheck_items",
                "judge_items",
            }, f"{backfill._display(path)} carries {sorted(counts)}"
            assert counts["judge_items"] >= 0
            # Every sector row must carry its own denominators too.
            # SectorHeatmap.tsx draws a cell per sector off those rates, so a
            # run-level count alone would leave each cell as ambiguous as it
            # was.
            for sector, row in (wow.get("by_sector") or {}).items():
                assert "item_counts" in row, (
                    f"{backfill._display(path)} sector {sector} has rates but "
                    "no denominators"
                )
                sector_rows += 1
        # by_rubric_category is empty everywhere on purpose; the other three
        # are only empty where a guard refused them.
        if backfill._is_empty(wow.get("by_sector")):
            empty_analytics += 1

    assert carried == 27, (
        f"27 payloads should carry recovered denominators; {carried} do"
    )
    assert sector_rows == 86, (
        f"86 sector rows should carry them as well; {sector_rows} do"
    )
    assert empty_analytics == 6, (
        "six payloads have no by_sector and every one is semantics-diverged; "
        f"found {empty_analytics}"
    )


def test_the_six_sealed_files_on_disk_are_still_sealed():
    """Against the real repository, not a fixture.

    Every test above builds the tree it queries, so all of them would keep
    passing if the seals in this repository moved or the walk stopped reaching
    them. This is the one that reads what is actually on disk -- including the
    185-task gold ceiling, the corpus's clearest instance of the defect.

    Five of these six were unsealed and backfilled. A seal that moves is still
    a seal: the payload changed, and every document that stated its digest
    states the new one, so the same six files come back refused. What this
    catches is the half-done version. ``documents_asserting`` reports only the
    documents whose digest matches the bytes on disk, so a document left
    behind does not fail loudly -- it silently drops out of this set while
    continuing to assert a hash nothing in the tree has. That is strictly
    worse than never having moved the seal, and it is exactly what happened on
    the first pass here: ``CHANGELOG.md`` vanished from the set below and this
    assertion is the only thing that said so.
    """
    sealed = {
        backfill._display(path): backfill.documents_asserting(path)
        for path in backfill.collect_grade_files(REPO_ROOT / "data" / "grades")
    }
    sealed = {path: docs for path, docs in sealed.items() if docs}

    assert len(sealed) == 6, f"expected six sealed payloads, found {sealed}"
    assert any("79c2f503" in path for path in sealed), (
        "the 185-task gold ceiling must still be refused; it is quoted as a "
        "reproduction receipt in PR3_FULL_GOLD_CORPUS.md"
    )
    assert {doc for docs in sealed.values() for doc in docs} == {
        "CHANGELOG.md",
        "data/grades/_validation/PR3_REPEAT_VARIATION.md",
        "scripts/__tests__/test_analyze_grade_run.py",
        "scripts/__tests__/test_sol_max_anchor_selection.py",
        "tasks/LATEST_TASK_RESULT/README.md",
        "tasks/rebuilding_grading_task/PR3_FULL_GOLD_CORPUS.md",
    }, (
        "a document dropped out of the voucher set. It did not stop asserting "
        "a digest -- it is asserting one no file in this tree has. Find which "
        "payload it names and move that digest too."
    )


# --------------------------------------------------------------------------
# the report has to name the file it is talking about
# --------------------------------------------------------------------------


def test_two_runs_that_differ_only_in_a_directory_print_differently():
    """Truncation was the first attempt and it collided.

    These names end in ``__src_<16hex>__v2.2.json``; a merged payload and its
    ``_repeats/run-002`` re-run are identical for the last seventy characters
    and differ only in a directory the tail never reaches. Six files on disk
    collapse into two ambiguous groups of three that way -- three lines of
    output, three different item counts, no way to tell which was which.
    """
    base = "data/grades/_diagnostic/" + "a" * 64 + "/"
    tail = "exp_gold__cfg_" + "b" * 16 + "__rubric_" + "c" * 40 + "__v2.2.json"

    merged = backfill._short(base + tail)
    repeat = backfill._short(base + "_repeats/run-002/" + tail)

    assert merged != repeat
    assert "run-002" in repeat
    assert len(merged) < len(base + tail), "digests should be abbreviated"
    assert "a" * 64 not in merged


def test_a_path_outside_the_repository_still_names_itself(tmp_path: Path):
    assert backfill._display(tmp_path / "x.json") == "x.json"


# --------------------------------------------------------------------------
# the committed corpus, not a fixture
# --------------------------------------------------------------------------


@pytest.mark.skipif(not GRADES_ROOT.is_dir(), reason="no data/grades checkout")
def test_the_gold_ceiling_run_is_inside_the_walk():
    """The 185-task run is what the recursive walk was widened for."""
    reachable = backfill.collect_grade_files(GRADES_ROOT)

    assert any(
        GOLD_CEILING_COHORT in path.parts for path in reachable
    ), "the gold-ceiling cohort is out of scope again"


@pytest.mark.skipif(not GRADES_ROOT.is_dir(), reason="no data/grades checkout")
def test_every_zero_precheck_rate_on_disk_is_an_absence():
    """Measured, not assumed.

    If a genuine zero existed -- prechecks that ran and all failed -- the
    counts would have to distinguish it from these, and any reading of "0%
    means nothing ran" would be wrong. There is not one in the corpus.
    """
    absences, genuine = 0, []
    for path in backfill.collect_grade_files(GRADES_ROOT):
        document = json.loads(path.read_text())
        wow = (document.get("summary") or {}).get("wow")
        if not isinstance(document.get("tasks"), list) or not isinstance(wow, dict):
            continue
        if wow.get("precheck_pass_rate") != 0.0:
            continue
        counts = backfill._compute_summary(document["tasks"])["wow"]["item_counts"]
        if counts["precheck_items"]:
            genuine.append(backfill._short(backfill._display(path)))
        else:
            absences += 1

    assert not genuine, f"a real 0% precheck rate exists after all: {genuine}"
    assert absences >= 20, (
        f"expected at least the twenty known absences, found {absences}"
    )
