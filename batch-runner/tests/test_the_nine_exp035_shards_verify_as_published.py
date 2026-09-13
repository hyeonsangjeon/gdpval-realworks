"""The nine exp035 shards, checked against the verifier that rejected them.

Nine grading shards were paid for, graded, and published. Every ``grade`` job
succeeded and every ``verify-published`` job failed, so the evidence sat on
``origin/main`` carrying a red verdict it did not earn. These tests pin what
that evidence actually says, so a later change to the verifier cannot quietly
re-condemn it -- or quietly excuse a shard that really is broken.

Two failures were real and are kept failing here on purpose. Shards 2 and 8
sent audio that the receipts they were published with do not account for, and
that gap is a true finding: the receipts understate their own incompleteness,
and this suite records that rather than papering over it.

What changed is the name of the finding, not the gap. ``cost-receipt-v1``'s
usage block now declares ``audio_input_tokens`` and ``audio_output_tokens``, so
a receipt built today carries them -- but these two were built before it did,
and widening a schema does not reach back into a document written under the old
one. The rejection therefore moved from ``usage_containment`` ("the receipt has
nowhere to put this") to ``usage_reconciles`` and ``components_reconcile`` ("the
receipt has somewhere and it is empty"), which say the same thing about the same
11,399 tokens more exactly. Both spellings are asserted below so that a future
change cannot turn either into a pass by moving the gap somewhere unwatched.

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

#: The shards whose published receipts omit audio the ledger measured. Not a
#: tolerance -- these two must keep failing until a derived repair supersedes
#: the receipts, and the originals are never edited to make them pass.
AUDIO_SHARDS = {2, 8}

#: What each of those two ledgers actually measured, keyed by shard. Written
#: out per shard for the same reason as SETTLED_ROWS: a total would hide one
#: shard losing tokens to the other.
AUDIO_INPUT_TOKENS = {2: 8999, 8: 2400}

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

    The audio gap is the opposite case: the two shards that sent audio really
    do have usage their receipts do not account for, and this asserts they are
    still rejected for it -- twice, once for the receipt total and once for the
    ``perception`` line beneath it. Both are listed rather than summarised,
    because a repair that silenced one and left the other would otherwise read
    here as progress.
    """
    findings, _ = verdicts[index]
    failed = sorted(f.check for f in findings if not f.ok)
    expected = (
        ["components_reconcile", "usage_reconciles"] if index in AUDIO_SHARDS else []
    )
    assert failed == expected


@pytest.mark.parametrize("index", range(9))
def test_no_shard_carries_a_token_kind_the_receipt_cannot_express(index, verdicts):
    """The check the audio gap used to fail still runs, and now passes.

    ``usage_containment`` reads the token kinds off the ledger rows instead of
    a list kept in the verifier, so it did not retire when audio was declared.
    It passes here because every ``*_tokens`` column these ledgers carry is now
    inside the receipt's usage block -- and it would fail again, on the run it
    appeared, for anything metered next.

    Asserted separately from the failure list above so that deleting the check
    outright cannot be mistaken for fixing it.
    """
    findings, _ = verdicts[index]
    containment = next(f for f in findings if f.check == "usage_containment")
    assert containment.ok, containment.detail
    assert containment.data["receipt_keys"] == [
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "audio_input_tokens",
        "audio_output_tokens",
    ]


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

    The finding now names both sides of the disagreement -- what the receipt
    says and what the ledger measured -- so the number a reader takes away is
    the ledger's, and the receipt's silence is visible beside it rather than
    standing in for it.
    """
    per_shard = {}
    for index in sorted(AUDIO_SHARDS):
        reconciles = next(
            f for f in verdicts[index][0] if f.check == "usage_reconciles"
        )
        disagreement = reconciles.data["audio_input_tokens"]
        assert disagreement["receipt"] is None, (
            "the published receipt states an audio count; it was written "
            "before the field existed and must stay silent in the original"
        )
        per_shard[index] = disagreement["ledger"]

    assert per_shard == AUDIO_INPUT_TOKENS
    assert sum(per_shard.values()) == 11399


def test_the_audio_output_the_ledger_measured_as_zero_is_not_read_as_silence(
    verdicts,
):
    """A measured zero is a measurement, and its absence is still a gap.

    Both shards' speech calls report ``audio_output_tokens`` of zero: the
    provider was asked and answered none. The published receipts say nothing
    at all, which is a different statement, and the verifier is required to
    tell the two apart -- otherwise a serializer that silently dropped a whole
    token kind would pass whenever that kind happened to total zero.
    """
    for index in sorted(AUDIO_SHARDS):
        reconciles = next(
            f for f in verdicts[index][0] if f.check == "usage_reconciles"
        )
        assert reconciles.data["audio_output_tokens"] == {
            "receipt": None,
            "ledger": 0,
        }
