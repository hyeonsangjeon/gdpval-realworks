"""What the paid smoke actually measured, read back from its own artifact.

Run ``33363059548`` bought two tasks at grader fingerprint ``f9ecc9e2…`` to
find out whether PR #276 repaired the audio path. It half did, and this file
pins both halves against the committed grade file so neither can drift into
folklore:

    the routing fix works        all 21 criteria the inventory recorded as
                                 demoted to TEXT now route AUDIO -- checked
                                 item id by item id, not by counting

    listening still does not     19 of those 21 came back ``judge_error``, so
                                 no audio verdict has ever been observed and
                                 the score movement is not evidence of one

The second is why these tests exist. The smoke's two tasks both scored *higher*
than they did in the 174-task run, and a reader skimming for a number would
conclude the fix landed. It did not: the gain came from text items re-marked by
a changed grader, while the audio items -- the entire point of the exercise --
returned nothing. A test that only compared percentages would have gone green
on a run that proved the opposite of what it looks like it proved.

These assertions are expected to *change* when the audio call is repaired. That
is the intent: the file is a description of a known-broken state, and the next
smoke either updates it or is not finished.

Spec: tasks/rebuilding_grading_task/307-audio-smoke-result.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

BATCH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_ROOT.parent

INVENTORY_PATH = (
    REPO_ROOT / "tasks/rebuilding_grading_task/stage3_partial_inventory.json"
)
SMOKE_DIR = (
    REPO_ROOT
    / "data/grades/_diagnostic"
    / "916c151265850ae5deb8368e8aecfb528309c0f00bb3fe071f40b643e06afa64"
)

#: The fingerprint the smoke was graded at. A literal for the same reason
#: ``PINNED_SOURCE_HASH`` is one: this file describes a measurement that has
#: already happened, and a computed value would silently follow the next fix.
SMOKE_SOURCE_HASH = (
    "f9ecc9e27ceb57b45548bff812b34b564df0ddbe7edbe09d437e8cf406a16f1a"
)


@pytest.fixture(scope="module")
def smoke() -> dict:
    matches = sorted(SMOKE_DIR.glob("*__src_f9ecc9e27ceb57b4__*.json"))
    assert len(matches) == 1, (
        f"expected exactly one smoke grade file in {SMOKE_DIR}, found {matches}"
    )
    return json.loads(matches[0].read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def damaged() -> dict[str, list[str]]:
    document = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    defect = document["known_grading_defects"][
        "audio_criteria_scored_without_listening"
    ]
    return {task["task_id"]: task["rubric_item_ids"] for task in defect["tasks"]}


def _items(smoke: dict, task_id: str) -> dict[str, dict]:
    for task in smoke["tasks"]:
        if task["task_id"] == task_id:
            return {item["rubric_item_id"]: item for item in task["items"]}
    raise AssertionError(f"{task_id} is not in the smoke result")


def test_the_smoke_is_the_run_this_file_describes(smoke, damaged):
    """Guard the fixtures before anything reads meaning into them."""
    assert smoke["grader_source_hash"] == SMOKE_SOURCE_HASH
    assert smoke["run_status"] == "diagnostic", (
        "the smoke graded a subset and must stay classified as diagnostic; a "
        "complete run at this path would be a different artifact"
    )
    assert {task["task_id"] for task in smoke["tasks"]} == set(damaged)


def test_every_demoted_criterion_now_routes_to_audio(smoke, damaged):
    """The half that worked, checked per item rather than per count.

    Counting would pass if seven criteria routed AUDIO and they happened to be
    a different seven. The inventory names exactly which items were demoted, so
    the check is an identity comparison: each id the deaf grader sent to TEXT
    is looked up in the new run and must now say AUDIO.
    """
    for task_id, item_ids in damaged.items():
        items = _items(smoke, task_id)
        wrong = {
            item_id: items[item_id]["routing_modality"]
            for item_id in item_ids
            if items[item_id]["routing_modality"] != "audio"
        }
        assert not wrong, (
            f"{task_id}: criteria the inventory recorded as demoted are still "
            f"not routed to audio: {wrong}"
        )


def test_the_audio_calls_failed_and_no_verdict_was_produced(smoke, damaged):
    """The half that did not, stated so it cannot be quietly assumed fixed.

    Routing a criterion to AUDIO is not hearing it. Nineteen of the twenty-one
    came back ``judge_error``, so the smoke has demonstrated the *route* and
    not the *judgement*. If this test starts failing because more verdicts are
    arriving, the audio call has been repaired and 307 needs rewriting -- which
    is the intended way for it to fail.
    """
    errored, total = 0, 0
    for task_id, item_ids in damaged.items():
        items = _items(smoke, task_id)
        for item_id in item_ids:
            total += 1
            if items[item_id]["verdict"] == "judge_error":
                errored += 1

    assert total == 21
    assert errored == 19, (
        f"{errored} of {total} audio criteria errored; 307 records 19. If this "
        "dropped, the audio call was fixed and the report must be updated "
        "before the full run is dispatched"
    )


def test_a_failed_audio_call_still_burns_the_per_task_cap(smoke, damaged):
    """The design defect the failure exposed, evidenced from the artifact.

    ``AudioPerception`` increments ``_calls_used`` before the request and does
    not give the slot back when the request raises. With ``AUDIO_CALL_CAP = 3``
    that means three provider errors exhaust a task's entire audio budget, and
    every criterion after them is refused without being attempted -- so one
    transient fault costs a task all of its sound marking, not three items of
    it.

    The artifact splits three ways, and the third way is the reason this test
    counts rather than asserts a single number. A handful of the routed
    criteria are answerable from the container probe alone -- "the MP4 contains
    at least one audio stream" is a metadata question, and the demotion bug is
    what used to send it to a judge that could only guess. Those never needed a
    model call and so were never at the cap's mercy.
    """
    for task_id, item_ids in damaged.items():
        items = _items(smoke, task_id)
        attempted, starved, no_call = [], [], []
        for item_id in item_ids:
            evidence = str(items[item_id]["evidence"])
            if "provider_error" in evidence:
                attempted.append(item_id)
            elif "cap_exceeded" in evidence:
                starved.append(item_id)
            else:
                no_call.append(item_id)

        assert len(attempted) <= 3, (
            f"{task_id}: {len(attempted)} calls got through a cap of 3"
        )
        assert starved, (
            f"{task_id}: no criterion was refused for cap_exceeded, so the cap "
            "no longer counts failed calls and this defect is fixed"
        )
        assert len(attempted) + len(starved) + len(no_call) == len(item_ids)
        for item_id in no_call:
            assert items[item_id]["perception_called"] is False, (
                f"{task_id}/{item_id} reports a perception call but carries "
                "neither a provider error nor a cap refusal"
            )


def test_the_container_probe_answers_the_criterion_it_used_to_fail(smoke):
    """One criterion the fix repaired outright, named because 306 named it.

    ``306`` quoted this item as the clearest statement of the defect: the
    criterion "the MP4 contains at least one audio stream" scored zero -- not
    excluded, *failed* -- on evidence that literally read ``"audio_tracks": 1``.
    The judge had the answer in front of it and had been told the file was
    silent.

    It now passes on the same evidence string, and without a model call. That
    is worth pinning separately from the routing count: it is the one place the
    smoke shows the repaired path producing a *correct mark*, rather than only
    a correct route.
    """
    items = _items(smoke, "75401f7c-396d-406d-b08e-938874ad1045")
    matches = [
        item for item in items.values()
        if "contains at least one audio stream" in str(item.get("criterion"))
    ]
    assert len(matches) == 1, "the criterion 306 quoted is no longer in the rubric"
    item = matches[0]

    assert item["routing_modality"] == "audio"
    assert item["verdict"] == "pass"
    assert item["awarded_score"] == item["max_score"]
    assert item["perception_called"] is False, (
        "a metadata question about the container was answered by spending an "
        "audio model call; the probe already holds the answer"
    )
    assert '"audio_tracks": 1' in str(item["evidence"])



def test_the_score_movement_is_not_evidence_the_fix_landed(smoke, damaged):
    """Why 307 refuses to read the percentages as an improvement.

    Both tasks scored higher than the 174-run recorded. Almost none of that
    came from sound: of the points available on audio criteria, the run earned
    two. The gain is text items re-marked by a changed grader, which is
    ordinary variance and says nothing about the audio path.
    """
    earned = available = 0
    for task_id, item_ids in damaged.items():
        items = _items(smoke, task_id)
        for item_id in item_ids:
            earned += items[item_id].get("awarded_score") or 0
            available += items[item_id].get("max_score") or 0

    assert available > 0
    assert earned / available < 0.15, (
        f"audio criteria earned {earned} of {available}; if this rose, the "
        "audio path started working and the report's central claim -- that no "
        "audio verdict has ever been observed -- is stale"
    )
