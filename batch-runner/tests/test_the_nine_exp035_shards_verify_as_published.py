"""The nine exp035 shards, checked against the verifier that rejected them.

Nine grading shards were paid for, graded, and published. Every ``grade`` job
succeeded and every ``verify-published`` job failed, so the evidence sat on
``origin/main`` carrying a red verdict it did not earn. These tests pin what
that evidence actually says, so a later change to the verifier cannot quietly
re-condemn it -- or quietly excuse a shard that really is broken.

Two failures were real and are kept failing here on purpose. Shards 2 and 8
sent audio the ``cost-receipt-v1`` usage block has no field for, and that gap
is a true finding: the receipts understate their own incompleteness, and this
suite records that rather than papering over it.

The shards are 37 MB of JSON, so they load once per module and every test
skips when the checkout does not carry them.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts.verify_cost_ledger import verify  # noqa: E402

STEM = (
    "exp035_codex_foundry_full220__judge_gpt-5_6-sol__"
    "exp035_codex_foundry_full220_v2_sol_max__cfg_89820de9d9c4e2e3__"
    "rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__"
    "inference_dc36d6837a8f0899f8bfa4d32aae9a9f6805f3b0__src_fd0db9d9d78d6d54__v2.2"
)
SHARDS = BATCH_RUNNER_ROOT.parent / "data/grades/_shards" / STEM

#: What each shard's ledger settled. Written out rather than summed in the test
#: because a total hides a shard that lost rows to one that gained them.
SETTLED_ROWS = [2260, 2567, 2219, 1875, 2718, 1972, 1908, 1304, 1722]

#: The shards whose usage the receipt schema cannot express. Not a tolerance --
#: these two must keep failing until the schema carries an audio field.
AUDIO_SHARDS = {2, 8}

pytestmark = pytest.mark.skipif(
    not SHARDS.is_dir(), reason="exp035 shard evidence not in this checkout"
)


def _shard(index: int) -> Path:
    return SHARDS / f"shard-{index:03d}-of-009.json"


@pytest.fixture(scope="module")
def payloads() -> list[dict]:
    return [json.loads(_shard(i).read_text(encoding="utf-8")) for i in range(9)]


@pytest.fixture(scope="module")
def verdicts() -> list[tuple[list, dict]]:
    return [verify(_shard(i)) for i in range(9)]


# 조각이 실제로 하나의 분할인가 -- 겹치지도 빠지지도 않아야 한다.

def test_the_nine_shards_are_one_partition_of_the_fixed_220(payloads):
    """220 is the denominator for the whole experiment, not a per-shard target.

    A stride split can silently drop or double a task if the stride and the
    count disagree, and nothing downstream would notice: every shard would
    still verify, and the merged payload would still look whole.
    """
    ids = [t["task_id"] for p in payloads for t in p["tasks"]]
    assert len(ids) == 220
    assert len(set(ids)) == 220, "a task appears in two shards, so it was graded twice"


def test_every_shard_settled_the_rows_it_was_published_with(verdicts):
    """The accounting, pinned apart from the verdict.

    The repair changed what the verifier concludes. It must not have changed
    what the ledger contains -- if these move, the evidence moved.
    """
    assert [c["settled_rows"] for _, c in verdicts] == SETTLED_ROWS
    assert sum(SETTLED_ROWS) == 18545


# 남은 실패는 두 개뿐이고, 그 둘은 진짜다.

@pytest.mark.parametrize("index", range(9))
def test_the_only_remaining_failure_is_the_audio_usage_gap(index, verdicts):
    """Every shard failed ``task_coverage`` in CI. None of them should.

    ``usage_containment`` is the opposite case: the two shards that sent audio
    really do have usage the receipt cannot account for, and this asserts they
    are still rejected for it.
    """
    findings, _ = verdicts[index]
    failed = sorted(f.check for f in findings if not f.ok)
    expected = ["usage_containment"] if index in AUDIO_SHARDS else []
    assert failed == expected


def test_no_task_is_reported_as_having_been_graded_for_free(verdicts):
    """The false positive that failed all nine runs.

    78 tasks never reached the judge. They are named in the payload, so the
    older rule read them as graded-but-unbilled; they made no call, so zero
    dollars is the correct bill.

    The check has to say so out loud. Passing silently would be the same
    verdict a check that stopped looking would return, so the tasks it decided
    cost nothing are named in the finding and counted here.
    """
    free = []
    for index, (findings, _) in enumerate(verdicts):
        coverage = next(f for f in findings if f.check == "task_coverage")
        assert coverage.ok, f"shard {index}: {coverage.detail}"
        free.extend(coverage.data["tasks_never_graded"])
    assert len(free) == len(set(free)) == 78


def test_what_every_task_declares_is_what_the_ledger_holds(payloads):
    """The identity the repaired check rests on, recomputed independently.

    Recomputed from the files rather than read out of the finding, so this
    fails if the check and the evidence ever drift apart -- including if the
    check starts agreeing with itself for the wrong reason.
    """
    mismatched = []
    for index, payload in enumerate(payloads):
        ledger = SHARDS / f"shard-{index:03d}-of-009.cost_ledger.jsonl"
        billed = Counter(
            str(row.get("task_id"))
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for row in [json.loads(line)]
            if row.get("state") == "settled"
        )
        for task in payload["tasks"]:
            declared = (task.get("judge_call_count") or 0) + (
                task.get("perception_call_count") or 0
            )
            if declared != billed.get(task["task_id"], 0):
                mismatched.append((index, task["task_id"], declared))
    assert mismatched == []


# 0호출 78개가 무엇이었는지 -- 채점기가 멈춘 자리 두 곳.

def test_the_seventy_eight_zero_call_tasks_all_stopped_before_the_judge(payloads):
    """Zero calls is only free if the task genuinely never reached the judge.

    Each of the 78 says so three ways: an error, a selection status that names
    where it stopped, and no counters. A task that stopped for some other
    reason would be a different finding and must not land in this set.
    """
    zero_call = [
        task
        for payload in payloads
        for task in payload["tasks"]
        if not (task.get("judge_call_count") or 0)
        and not (task.get("perception_call_count") or 0)
    ]
    assert len(zero_call) == 78
    assert all(task.get("error") for task in zero_call)
    assert Counter(t.get("selection_status") for t in zero_call) == {
        "no_generated_candidate": 70,
        "selection_error": 8,
    }


def test_the_audio_usage_that_cannot_be_priced_is_stated_not_dropped(verdicts):
    """Costs that are missing are reported as missing.

    The tokens are known and the price is not. Recording the count is what
    keeps this an acknowledged gap instead of an implied zero.
    """
    audio = sum(
        next(f for f in verdicts[i][0] if f.check == "usage_containment")
        .data["totals"]["audio_input_tokens"]
        for i in AUDIO_SHARDS
    )
    assert audio == 11399
