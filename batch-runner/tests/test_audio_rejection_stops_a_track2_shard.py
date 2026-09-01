"""One rejected audio call ended a 17-task shard. This is that chain, offline.

Stage 3 shard 1 of 11 died twice at the same place — run 33239138322 and its
re-run 33241377185, both at task 2 of 17, both with ``rc=6`` and the same
message::

    ERROR: Track 2 grading stopped after runtime failure for
    38889c3b-e3d4-49c8-816a-3cc8e5313aba: usage_incomplete

The task had already been graded (40.9 of 62). What stopped the run was not
the grade but an integrity check, and what tripped that check was three audio
sub-judge calls that the provider refused. The cause was a malformed request,
and the first account of it here was only half right: it named the content
part's key, which had put the payload under ``audio`` where an ``input_audio``
part was required. Correcting the key did not fix anything, because the
endpoint was wrong underneath it. ``ResponseInputContentParam`` is a union of
text, image and file, and has no audio member at all — so a Responses request
carrying audio in *any* spelling is refused with a 400 before a model hears a
second of it. Audio belongs to Chat Completions. Every audio call this
pipeline has ever made was rejected, and there is no successful one in any
committed grade payload.

The suite did not catch it because the audio test asserted the key by hand and
asserted it wrong; and then, once the key was corrected, went on passing while
every call still failed, because it read the shape off a same-named type in
the Responses namespace that is not a member of that endpoint's content union.
The generalised guard is now in
``tests/test_audio_goes_to_the_endpoint_that_accepts_it.py``.

The shape itself is pinned in ``test_perception_audio``. What this module
pins is the *consequence* — the chain that turned one refused call into a
dead shard — because that is the part that made the failure expensive rather
than merely wrong:

    a rejected call reports usage_complete=False
        -> the visual prepass ANDs it into the item
            -> the task ANDs every item
                -> _track2_task_runtime_error returned "usage_incomplete"
                    -> step8_grade returned GRADE_EXIT_RUNTIME_FAILURE

Each hop was a deliberate design decision and none was wrong on its own.
Together they meant an unproven perception path could end a paid run over
fifteen tasks that were never attempted.

The chain is now cut in three places, by three changes that only work as a
set, and this module is where the set is held together — each of the three
has its own tests, but none of them can see what the other two do to the
same failure:

* the request carries ``input_audio`` **and goes to Chat Completions**, which
  is the endpoint that accepts it, so the call is not refused at all;
* an item the listening model never answered is a ``judge_error`` and leaves
  the score, instead of being marked as a fault in the deliverable;
* an unknown token count no longer stops the run, because it says nothing
  about whether the marking was right — only about what it cost.

So the first two hops still hold, deliberately: a call that really does fail
still reports its usage as unknown, and that flag still propagates. What no
longer follows is the shard's death. If someone reconnects those last two
hops, this module says which property they gave back.

Nothing here calls a model. It builds verdicts and task dictionaries in
memory and asks the real functions what they make of them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import step8_grade as s8  # noqa: E402
from core.perception.audio import AudioPerception, AudioVerdict  # noqa: E402
from core.tool_calling_judge import (  # noqa: E402
    ToolCallingJudge,
    VisualPrepassResult,
)


class _RejectingCompletions:
    """A provider that refuses the request, the way a 400 arrives in-process."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        raise BadRequestError("invalid content part")


class BadRequestError(Exception):
    """Stands in for ``openai.BadRequestError``.

    Only the class *name* travels: ``public_provider_error_text`` publishes
    ``provider_error:<TypeName>`` and deliberately drops the message, so the
    grade file records the type and nothing that could carry a prompt or an
    endpoint. Naming the local double the same thing is what makes the
    evidence string below identical to the one in the failed run.
    """


class _Client:
    """Offers Chat Completions only, like the real client the reader uses.

    It carries no ``responses`` attribute on purpose. This double used to
    expose one, which meant the shard-death chain below could be reproduced
    against an endpoint that was itself the bug — the refusal being asserted
    was the one the fix removes, arriving for a reason the test could not
    see. Now the refusal has to be the provider's answer to a well-formed
    request, which is the failure this module is actually about: a call that
    genuinely fails still reports its usage as unknown, and that flag still
    travels, but it no longer kills the shard.
    """

    def __init__(self, completions) -> None:
        from types import SimpleNamespace

        self.chat = SimpleNamespace(completions=completions)


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    import struct
    import wave

    p = tmp_path / "stem.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", (i % 50) * 300)
                               for i in range(8000)))
    return p


def _task(*, items: list[dict], usage_complete: bool, error=None) -> dict:
    return {"task_id": "38889c3b", "error": error, "items": items,
            "usage_complete": usage_complete}


def _item(*, usage_complete: bool, verdict: str = "fail") -> dict:
    return {"verdict": verdict, "score_excluded": False,
            "usage_complete": usage_complete, "routing_modality": "audio"}


# ── hop 1: the refused call ──────────────────────────────────────────


def test_a_refused_audio_call_reports_its_usage_as_incomplete(wav_file):
    """The verdict that came back from all three real calls.

    ``usage_complete`` is initialised ``False`` and only becomes ``True``
    once a reply has been read, so a call that raises reports ``False`` — it
    was sent, and this process cannot say what it cost.

    That is the honest reading for a timeout, and this fake is a timeout in
    every respect that matters: it raises an exception carrying no status
    code, so nothing can establish that the provider refused it before
    running the model. A call in that state stays counted against the task's
    cap for the same reason its usage stays incomplete — it may have been
    billed, and the safe direction is to assume it was.

    The 400s the smoke actually hit *do* carry a status, and
    ``test_a_provider_rejection_gives_the_call_slot_back`` covers that side.
    Both branches exist because the difference between them is the difference
    between a call that cost nothing and a call nobody can account for.
    """
    client = _Client(_RejectingCompletions())
    perception = AudioPerception(client=client)
    verdict = perception.judge(
        criterion="the mix is free of clipping", audio_path=str(wav_file)
    )

    assert isinstance(verdict, AudioVerdict)
    assert verdict.verdict == "judge_error"
    assert verdict.judge_error == "provider_error:BadRequestError"
    assert verdict.reasoning.startswith("audio call failed: BadRequestError")
    assert "status=None" in verdict.reasoning, (
        "the failure must say what it knew about the request, so the next "
        "paid smoke does not need a fourth one to tell two causes apart"
    )
    assert verdict.api_call_count == 1
    assert (verdict.input_tokens, verdict.output_tokens) == (0, 0)
    assert verdict.usage_complete is False
    assert perception.calls_used == 1, (
        "an exception with no status may have been billed and must stay "
        "charged; only a provable pre-inference rejection is refunded"
    )


# ── hop 2: the prepass ───────────────────────────────────────────────


def test_the_prepass_takes_the_incomplete_flag_from_any_one_tool_result(
    wav_file,
):
    """One bad perception result is enough; the rest cannot repair it.

    The accumulator ANDs, so ordering does not matter and a later good call
    never restores the flag. This is why the real task reported three audio
    calls with zero tokens against 111 grading calls that all reported usage.
    """
    client = _Client(_RejectingCompletions())
    refused = AudioPerception(client=client).judge(
        criterion="x", audio_path=str(wav_file)
    ).to_dict()
    good = AudioVerdict(verdict="pass", partial_score=1.0, evidence="",
                        confidence=1.0, reasoning="", api_call_count=1,
                        input_tokens=900, output_tokens=40).to_dict()

    prepass = VisualPrepassResult()
    assert prepass.usage_complete is True
    ToolCallingJudge._accumulate_perception_result(prepass, {"data": refused})
    assert prepass.usage_complete is False
    ToolCallingJudge._accumulate_perception_result(prepass, {"data": good})
    assert prepass.usage_complete is False, "a good call must not repair it"

    assert prepass.perception_call_count == 2
    assert prepass.perception_input_tokens == 900


# ── hops 3 and 4: the gate and the exit code ─────────────────────────


def test_an_unknown_token_count_no_longer_stops_the_whole_run():
    """The hop that cost sixteen unattempted tasks, cut.

    The flag still travels — hops 1 and 2 above are unchanged — but the gate
    no longer reads it as a reason to stop. It never described the marking:
    an item whose tokens went uncounted was graded exactly as carefully as
    one whose tokens arrived. What is genuinely unknown is the bill, and that
    is carried by the task's own ``usage_complete`` into ``summary.cost``, so
    the run still refuses to publish a cost it cannot stand behind.

    Both shapes are checked because they can differ: the task-level roll-up
    and any single item's flag were separate reasons to abort, and leaving
    either one connected would leave the shard just as killable.
    """
    assert s8._track2_task_runtime_error(
        _task(items=[_item(usage_complete=True)], usage_complete=True)
    ) is None

    assert s8._track2_task_runtime_error(
        _task(items=[_item(usage_complete=True)], usage_complete=False)
    ) is None

    assert s8._track2_task_runtime_error(
        _task(
            items=[_item(usage_complete=True), _item(usage_complete=False)],
            usage_complete=True,
        )
    ) is None


def test_marks_nobody_can_read_still_stop_the_run():
    """What the gate is still for, so that cutting one hop did not cut them all.

    A number no reader can interpret is worse than no number, so a task the
    grader gave up on, items that are not a list, and a judge error left
    inside the score it should have been excluded from all still end the
    shard. Naming them here keeps the previous test honest: it asserts a
    specific hop was removed, not that the gate was emptied.
    """
    assert s8._track2_task_runtime_error(
        _task(items=[_item(usage_complete=True)], usage_complete=True,
              error="judge_transport_failure")
    ) == "judge_transport_failure"

    assert s8._track2_task_runtime_error(
        {"task_id": "t", "error": None, "items": "not-a-list"}
    ) is not None

    assert s8._track2_task_runtime_error(
        _task(items=[{"verdict": "judge_error", "score_excluded": False,
                      "usage_complete": True}], usage_complete=True)
    ) == "invalid_score_exclusion"


def test_the_repaired_chain_end_to_end_on_the_item_that_killed_shard_one():
    """The join the three changes only satisfy together.

    Each change is tested where it lives, but none of those tests can see the
    other two: the listening fix does not know what the gate does with its
    verdict, and the gate does not know how the verdict was reached. This is
    the handover — the exact item dictionary the judge now emits for a call
    that was never answered, handed to the exact gate that decides whether
    the shard lives.

    ``verdict="judge_error"`` with ``score_excluded=True`` is what the item
    became; ``usage_complete=False`` is what the failed call still costs the
    run. A gate that objected to either field would put the shard's death
    back, one change short of the set.
    """
    item_the_judge_now_emits = {
        "verdict": "judge_error",
        "judge_error": "audio_perception_failed:provider_error:BadRequestError",
        "score_excluded": True,
        "usage_complete": False,
        "routing_modality": "audio",
    }

    assert s8._track2_task_runtime_error(
        _task(items=[item_the_judge_now_emits, _item(usage_complete=True,
                                                     verdict="pass")],
              usage_complete=False)
    ) is None


def test_the_three_tolerated_errors_stay_tolerated():
    """Selection outcomes are findings about the deliverable, not faults.

    A task with nothing to mark is a result the corpus is allowed to contain.
    Were these to start aborting the run, a gold corpus with one empty
    submission could never be graded at all.
    """
    for tolerated in ("all_items_score_excluded", "no_deliverables",
                      "selection_error"):
        assert s8._track2_task_runtime_error(
            _task(items=[_item(usage_complete=True)], usage_complete=True,
                  error=tolerated)
        ) is None

    assert s8._track2_task_runtime_error(
        _task(items=[_item(usage_complete=True)], usage_complete=True,
              error="usage_incomplete")
    ) == "usage_incomplete"


def test_a_judge_error_item_must_be_excluded_from_the_score():
    """The other half of the same gate, and the reason the ceiling held.

    An item the judge could not decide has no score, so counting it as zero
    would depress a ceiling measurement for an infrastructure reason. The gate
    refuses a run where one is scored anyway.

    Worth reading beside the real failure: the three refused audio items came
    back ``fail``, not ``judge_error``, because the main judge was told its
    tool had failed and then decided for itself. So this check passed and the
    usage check is what caught them — but their zeros were counted, which is
    why 65.97% for that task is not a ceiling and must not be read as one.
    """
    assert s8._track2_task_runtime_error(
        _task(items=[{"verdict": "judge_error", "score_excluded": True,
                      "usage_complete": True}], usage_complete=True)
    ) is None

    assert s8._track2_task_runtime_error(
        _task(items=[{"verdict": "judge_error", "score_excluded": False,
                      "usage_complete": True}], usage_complete=True)
    ) == "invalid_score_exclusion"


def test_a_runtime_failure_leaves_its_partial_result_uncommitted():
    """Why this failure cost two runs and left nothing behind in git.

    ``step8_grade`` does write a diagnostic partial before returning — the
    grade for the task that failed, and for the one before it, was computed
    and saved. But the workflow commits a grade file only when the step exits
    0 or 7, and a runtime failure exits 6, so that partial survived only as a
    30-day artifact. Nothing in the repository records that the work happened.

    The exit-code constants are local to ``main``, so the contract is
    read from the workflow instead: this asserts which return codes reach the
    commit, which is the half that decides whether paid work is preserved.
    """
    workflow = (Path(__file__).resolve().parents[2]
                / ".github/workflows/grade-run.yml").read_text(encoding="utf-8")
    step = workflow.index("- name: Commit grade result")
    condition = workflow[step:workflow.index("\n        env:", step)]

    accepted = set(re.findall(r"steps\.grade\.outputs\.rc == '(\d+)'",
                              condition))
    assert accepted == {"0", "7"}, (
        "the commit gate changed; a run that now reaches it, or no longer "
        "does, changes whether paid grades survive as commits"
    )
    assert "6" not in accepted
