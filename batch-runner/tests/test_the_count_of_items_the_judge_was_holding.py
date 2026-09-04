"""The video undercount, counted a second time and pinned to the payload.

``322`` closed with a rule for the next person: count what the judge was
holding, not what the grader labelled. It then broke its own rule. Its headline
figure -- the criteria on the two gold ``.mp4`` tasks that reached a judge with
no picture -- was assembled as ``fail 38 + pass 9 = 47``, an enumeration of two
verdict buckets. The set has a third. One item came back ``partial`` and fell
out of a total that was never counted, only added up.

The dropped item is:

    75401f7c  "Overall formatting and style of the deliverable"  max 5, awarded 3.0

It is the only item in the set that came back *partly* right. Forty-six of the
other forty-seven are a flat ``pass`` or ``fail``, which is precisely why an
enumeration of those two buckets lost it and why nothing in the arithmetic
looked wrong afterwards. It is also the second-heaviest positive item in the
set -- only a 15-point item outweighs it, and the other forty-four are worth
1 or 2 points each.

It went missing behind a sentence, not a slip. ``322`` §4 said that item "is
still classified visual today, so it is not among the 47" -- wrong twice. It is
recorded ``text`` in the payload, and today's ``resolve_runtime_routing`` sends
it to VISUAL, so it is not merely in the set, it is in the set for exactly the
reason the document was about. The sentence came from reading
``000-OVERVIEW.md`` §"render target missing", which correctly excludes
*"Overall formatting and style"* items pointed at ``data_flow.txt`` and
``MIG_Welding_Catch_Up_Summary.txt``. Those are plain-text files with no shape
to look at, on different tasks. Identical criterion text, different task,
opposite correct answer -- and the exclusion was carried across the gap.

So the count is pinned here instead of asserted in prose. ``322`` stated 47 in
ten places and no test read any of them; that is why a wrong number survived a
merge, a CI run and a review. This reads the committed payload and recomputes,
so the next person to touch these figures has to move a test, not a paragraph.

Nothing here calls a model or a network. It reads one committed file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The 185-task gold-ceiling grade, graded 2026-08-31 at ``src_79c2f503``.
#: The run ``322`` measured. Committed, so this test needs no network and no
#: deliverable files -- the routing decision it checks is recorded per item.
GOLD_185 = (
    REPO_ROOT
    / "data/grades/_diagnostic"
    / "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
    / (
        "exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_185_v2_sol_max"
        "__cfg_f9c5f7bab9bd1530"
        "__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf"
        "__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf"
        "__src_79c2f5035c4aa826__v2.2.json"
    )
)

#: The only two tasks in the 185 that ship an ``.mp4``.
AD_SPOT = "e222075d-5d62-4757-ae3c-e34b0846583b"
CG_REEL = "75401f7c-396d-406d-b08e-938874ad1045"

#: Recorded modality split per task, at the fingerprint that produced the file.
#: ``322`` §4 published ``text 22 / visual 4`` for the reel. The payload says
#: 23 and 3. The stray ``visual 4`` is ``318``'s count of tagged items, which
#: is a repo-wide figure over both tasks -- it is 1 here and 3 there -- and it
#: was written into the per-task row of the other one.
EXPECTED_MODALITY = {
    AD_SPOT: {"text": 25, "audio": 7, "visual": 1},
    CG_REEL: {"text": 23, "audio": 14, "visual": 3},
}

#: Every verdict in the reader-routed set, not the two that were added up.
EXPECTED_VERDICTS = {"fail": 38, "pass": 9, "partial": 1}

#: 48, and it has to be derived from the line above rather than written twice.
EXPECTED_TOTAL = sum(EXPECTED_VERDICTS.values())


@pytest.fixture(scope="module")
def gold_185() -> dict:
    if not GOLD_185.exists():  # pragma: no cover - a committed file
        pytest.fail(f"the payload 322 measured is missing: {GOLD_185}")
    return json.loads(GOLD_185.read_text())


def _task(payload: dict, task_id: str) -> dict:
    for task in payload["tasks"]:
        if task["task_id"] == task_id:
            return task
    raise AssertionError(f"{task_id} is not in {GOLD_185.name}")


def _reader_routed(payload: dict) -> list[dict]:
    """Items on the two video tasks that reached a judge on the text path."""
    return [
        item
        for task_id in (AD_SPOT, CG_REEL)
        for item in _task(payload, task_id)["items"]
        if (item.get("routing_modality") or "").lower() == "text"
    ]


def test_the_two_video_tasks_split_the_way_the_payload_says(gold_185):
    """Per-task modality, because the published per-task row was wrong."""
    for task_id, expected in EXPECTED_MODALITY.items():
        task = _task(gold_185, task_id)
        counted: dict[str, int] = {}
        for item in task["items"]:
            modality = (item.get("routing_modality") or "").lower()
            counted[modality] = counted.get(modality, 0) + 1
        assert counted == expected, (
            f"{task_id[:8]} routed {counted}, not {expected}. If this run was "
            f"regraded the figures in 322 §4 are stale with it."
        )


def test_every_verdict_in_the_set_is_counted_not_two_of_them(gold_185):
    """The regression itself: a bucket left out of a hand-added total."""
    counted: dict[str, int] = {}
    for item in _reader_routed(gold_185):
        counted[item["verdict"]] = counted.get(item["verdict"], 0) + 1
    assert counted == EXPECTED_VERDICTS, (
        f"reader-routed verdicts are {counted}, not {EXPECTED_VERDICTS}. A "
        f"bucket appearing here that 322 does not name is the same mistake "
        f"322 made -- add it to the document, not just to this dict."
    )


def test_the_total_is_forty_eight(gold_185):
    assert len(_reader_routed(gold_185)) == EXPECTED_TOTAL == 48


def test_the_dropped_item_is_in_the_set_and_is_the_only_partial(gold_185):
    """The specific item ``322`` excluded, and why the exclusion was invisible.

    Not just "48 items exist". The item that went missing is the *only* one in
    the set with a partial verdict, so a total assembled from ``fail`` and
    ``pass`` came out internally consistent and wrong. Pinning its identity
    means a future selection change that legitimately moves it has to say so
    here rather than silently restoring the old number.
    """
    routed = _reader_routed(gold_185)
    partials = [item for item in routed if item["verdict"] == "partial"]
    assert len(partials) == 1
    dropped = partials[0]
    assert dropped["criterion"] == "Overall formatting and style of the deliverable"
    assert dropped["max_score"] == 5
    assert dropped["awarded_score"] == 3.0

    weights = sorted(
        (item["max_score"] for item in routed if (item.get("max_score") or 0) > 0),
        reverse=True,
    )
    assert weights[:2] == [15, 5], (
        f"the dropped item was the second-heaviest positive item in the set; "
        f"the top weights are now {weights[:3]}, so 322's framing needs a look"
    )
    assert set(weights[2:]) == {1, 2}, (
        f"the rest of the set was worth 1 or 2 points each; it is now "
        f"{sorted(set(weights[2:]))}"
    )


def test_the_points_at_stake_survive_the_recount(gold_185):
    """61 / -90 / 18 were right in 322 and must not move with the total.

    The recount adds an item; it must not quietly restate the money. These
    three figures are quoted on the Project board and in two other documents,
    so a change here is a change there.
    """
    routed = _reader_routed(gold_185)
    failed_points = sum(
        item["max_score"]
        for item in routed
        if item["verdict"] == "fail" and (item.get("max_score") or 0) > 0
    )
    penalty_weight = sum(
        item["max_score"] for item in routed if (item.get("max_score") or 0) < 0
    )
    passed_points = sum(
        item["max_score"] for item in routed if item["verdict"] == "pass"
    )
    assert failed_points == 61
    assert penalty_weight == -90
    assert passed_points == 18

    heaviest = max(routed, key=lambda item: item["max_score"])
    assert heaviest["max_score"] == 15
    assert heaviest["verdict"] == "fail"
    assert heaviest["awarded_score"] == 0.0
    assert heaviest["criterion"].startswith("All footage is from royalty-free")


def test_the_four_tagged_items_are_a_different_set_entirely(gold_185):
    """``318``'s 4 and ``322``'s 48 must not overlap by even one item.

    The whole argument is that a tagged item and a silently-misrouted one are
    different populations -- one excluded from scoring, one scored. If they
    ever intersect, the documents' 4-versus-48 framing collapses.
    """
    tagged = [
        item
        for task_id in (AD_SPOT, CG_REEL)
        for item in _task(gold_185, task_id)["items"]
        if item.get("evidence") == "required_visual_render_target_unavailable"
    ]
    assert len(tagged) == 4
    assert all(item["score_excluded"] for item in tagged)
    assert all(item["verdict"] == "judge_error" for item in tagged)

    tagged_ids = {item["rubric_item_id"] for item in tagged}
    routed_ids = {item["rubric_item_id"] for item in _reader_routed(gold_185)}
    assert not (tagged_ids & routed_ids)
