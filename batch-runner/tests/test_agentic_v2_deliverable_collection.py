"""Whether the guest's files reach the host whole, or leave nothing behind.

The interesting tests are the ones that break a collection half way through and
then assert on what is on disk afterwards. A collector is easy to write and easy
to get wrong in exactly one way — leaving a directory that looks like a short
answer — so that is what most of this file is about.
"""

from __future__ import annotations

import hashlib

import pytest

from core.agentic_v2_deliverable_collection import (
    DELIVERABLE_ROOT,
    MOST_BYTES_IN_ONE_COLLECTION,
    STAGING_PREFIX,
    CollectionRefused,
    abandoned_collections,
    collect_deliverables,
    discard_previous_collection,
)


TASK = "task-0001"
ATTEMPT = "task-0001-deadbeef-a01"


def _result(*files):
    return {
        "success": True,
        "text": "done",
        "deliverable_text": "done",
        "files": [
            {"filename": name, "content": content} for name, content in files
        ],
    }


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ── the ordinary path ────────────────────────────────────────────────────


def test_files_land_where_the_submission_expects_them(tmp_path):
    collection = collect_deliverables(
        _result(("report.xlsx", b"\x00\xffbytes")),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    assert collection.submission_paths() == [
        f"{DELIVERABLE_ROOT}/{TASK}/report.xlsx"
    ]
    landed = tmp_path / DELIVERABLE_ROOT / TASK / "report.xlsx"
    assert landed.read_bytes() == b"\x00\xffbytes"


def test_binary_content_is_not_mangled(tmp_path):
    payload = bytes(range(256)) * 8
    collect_deliverables(
        _result(("book.xlsx", payload)),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    landed = tmp_path / DELIVERABLE_ROOT / TASK / "book.xlsx"
    assert landed.read_bytes() == payload


def test_the_model_s_directory_structure_survives(tmp_path):
    collection = collect_deliverables(
        _result(
            ("analysis/summary.xlsx", b"one"),
            ("raw/summary.xlsx", b"two"),
        ),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    assert collection.submission_paths() == [
        f"{DELIVERABLE_ROOT}/{TASK}/analysis/summary.xlsx",
        f"{DELIVERABLE_ROOT}/{TASK}/raw/summary.xlsx",
    ]
    root = tmp_path / DELIVERABLE_ROOT / TASK
    assert (root / "analysis" / "summary.xlsx").read_bytes() == b"one"
    assert (root / "raw" / "summary.xlsx").read_bytes() == b"two"


def test_the_journal_entries_carry_verified_digests(tmp_path):
    collection = collect_deliverables(
        _result(("report.xlsx", b"payload")),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    assert collection.journal_entries() == [
        {
            "path": f"{DELIVERABLE_ROOT}/{TASK}/report.xlsx",
            "sha256": _sha(b"payload"),
            "size": len(b"payload"),
        }
    ]
    assert collection.total_bytes() == len(b"payload")


def test_nothing_is_staged_once_a_collection_succeeds(tmp_path):
    collect_deliverables(
        _result(("report.xlsx", b"payload")),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    assert abandoned_collections(tmp_path) == []


# ── all or nothing ───────────────────────────────────────────────────────


def test_a_failure_part_way_through_leaves_no_result_directory(tmp_path, monkeypatch):
    import core.agentic_v2_deliverable_collection as module

    real = module._write_one
    calls = {"n": 0}

    def fail_on_the_second(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(28, "No space left on device")
        return real(**kwargs)

    monkeypatch.setattr(module, "_write_one", fail_on_the_second)

    with pytest.raises(OSError):
        collect_deliverables(
            _result(("a.txt", b"one"), ("b.txt", b"two"), ("c.txt", b"three")),
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )

    assert not (tmp_path / DELIVERABLE_ROOT / TASK).exists()
    assert abandoned_collections(tmp_path) == []


def test_a_keyboard_interrupt_also_leaves_nothing(tmp_path, monkeypatch):
    import core.agentic_v2_deliverable_collection as module

    def interrupt(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "_write_one", interrupt)

    with pytest.raises(KeyboardInterrupt):
        collect_deliverables(
            _result(("a.txt", b"one")),
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )
    assert not (tmp_path / DELIVERABLE_ROOT / TASK).exists()


def test_bytes_that_did_not_survive_the_write_are_refused(tmp_path, monkeypatch):
    import core.agentic_v2_deliverable_collection as module

    real = module._write_one

    def truncating_write(*, staging, relative, content):
        return real(staging=staging, relative=relative, content=content[:-1])

    monkeypatch.setattr(module, "_write_one", truncating_write)

    with pytest.raises(CollectionRefused, match="not on disk as it came out"):
        collect_deliverables(
            _result(("report.xlsx", b"payload")),
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )
    assert not (tmp_path / DELIVERABLE_ROOT / TASK).exists()


# ── refusals ─────────────────────────────────────────────────────────────


def test_a_failed_run_has_nothing_to_collect(tmp_path):
    with pytest.raises(CollectionRefused, match="only a successful run"):
        collect_deliverables(
            {"success": False, "files": [], "error": "compute_start_failed"},
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )


def test_a_success_with_no_files_is_refused(tmp_path):
    with pytest.raises(CollectionRefused, match="did not finalize anything"):
        collect_deliverables(
            {"success": True, "files": []},
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )


def test_text_content_is_refused(tmp_path):
    with pytest.raises(CollectionRefused, match="must be bytes"):
        collect_deliverables(
            {"success": True, "files": [{"filename": "a.txt", "content": "one"}]},
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )


@pytest.mark.parametrize(
    "path",
    ["/etc/passwd", "../escape.txt", "a/../../escape.txt", "a\\b.txt"],
)
def test_a_path_that_leaves_the_task_directory_is_refused(tmp_path, path):
    with pytest.raises(CollectionRefused, match="canonical relative path"):
        collect_deliverables(
            _result((path, b"payload")),
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )
    assert not (tmp_path / DELIVERABLE_ROOT / TASK).exists()


def test_a_task_id_with_a_slash_is_refused(tmp_path):
    with pytest.raises(CollectionRefused, match="not usable as a directory"):
        collect_deliverables(
            _result(("a.txt", b"one")),
            task_id="../elsewhere",
            into=tmp_path,
            attempt_name=ATTEMPT,
        )


def test_two_deliverables_with_one_path_are_refused(tmp_path):
    with pytest.raises(CollectionRefused, match="both want"):
        collect_deliverables(
            _result(("a.txt", b"one"), ("a.txt", b"two")),
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )
    assert not (tmp_path / DELIVERABLE_ROOT / TASK).exists()


def test_too_many_bytes_are_refused(tmp_path):
    big = b"x" * (MOST_BYTES_IN_ONE_COLLECTION // 2 + 1)
    with pytest.raises(CollectionRefused, match="exceed"):
        collect_deliverables(
            _result(("a.bin", big), ("b.bin", big)),
            task_id=TASK,
            into=tmp_path,
            attempt_name=ATTEMPT,
        )
    assert not (tmp_path / DELIVERABLE_ROOT / TASK).exists()


def test_an_existing_collection_is_refused_rather_than_replaced(tmp_path):
    collect_deliverables(
        _result(("report.xlsx", b"first")),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    with pytest.raises(CollectionRefused, match="already holds a collection"):
        collect_deliverables(
            _result(("report.xlsx", b"second")),
            task_id=TASK,
            into=tmp_path,
            attempt_name="task-0001-deadbeef-a02",
        )
    landed = tmp_path / DELIVERABLE_ROOT / TASK / "report.xlsx"
    assert landed.read_bytes() == b"first"


def test_an_unusable_attempt_name_is_refused(tmp_path):
    with pytest.raises(CollectionRefused, match="not usable"):
        collect_deliverables(
            _result(("a.txt", b"one")),
            task_id=TASK,
            into=tmp_path,
            attempt_name="a/b",
        )


# ── replacing on purpose ─────────────────────────────────────────────────


def test_discarding_then_collecting_replaces_the_answer(tmp_path):
    collect_deliverables(
        _result(("report.xlsx", b"first")),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    assert discard_previous_collection(tmp_path, TASK) is True
    collect_deliverables(
        _result(("report.xlsx", b"second")),
        task_id=TASK,
        into=tmp_path,
        attempt_name="task-0001-deadbeef-a02",
    )
    landed = tmp_path / DELIVERABLE_ROOT / TASK / "report.xlsx"
    assert landed.read_bytes() == b"second"


def test_discarding_nothing_says_so(tmp_path):
    assert discard_previous_collection(tmp_path, TASK) is False


# ── what an interruption leaves ──────────────────────────────────────────


def test_a_staging_directory_left_behind_is_reported(tmp_path):
    staging = tmp_path / DELIVERABLE_ROOT / f"{STAGING_PREFIX}{ATTEMPT}"
    staging.mkdir(parents=True)
    (staging / "half.txt").write_bytes(b"partial")
    assert abandoned_collections(tmp_path) == [staging]


def test_no_deliverable_root_means_nothing_abandoned(tmp_path):
    assert abandoned_collections(tmp_path) == []


def test_a_stale_staging_directory_does_not_block_a_retry(tmp_path):
    staging = tmp_path / DELIVERABLE_ROOT / f"{STAGING_PREFIX}{ATTEMPT}"
    staging.mkdir(parents=True)
    (staging / "half.txt").write_bytes(b"partial")

    collection = collect_deliverables(
        _result(("report.xlsx", b"whole")),
        task_id=TASK,
        into=tmp_path,
        attempt_name=ATTEMPT,
    )
    assert not (collection.directory / "half.txt").exists()
    assert (collection.directory / "report.xlsx").read_bytes() == b"whole"
