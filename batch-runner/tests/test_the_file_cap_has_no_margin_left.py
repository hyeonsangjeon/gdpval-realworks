"""The other half of that budget: what one item spends, and how little is left.

``call_cap_per_task`` is 112 because 102 is the largest task demand this
grader produces and ``file_cap_per_item`` is what one further visual item can
add. ``test_the_picture_budget_was_counted.py`` argues the 102 from a graded
run and takes the 10 as given. Nothing argued the 10.

It is the tighter of the two. Read out of every payload this repository has
committed -- the planner's own count where an item was refused, the rendered
count where it was not -- the largest demand a single rubric item has ever
recorded is **10**, against a cap of **10**. The margin is zero.

That the cap has stopped biting is real and is not the same thing. All three
refusals this corpus holds were refused at ``cap=3``, the default before
``3eab549`` (#212), and all three demands -- 10, 5, 5 -- clear 10. A run at
cap 3 marks *every* item that wants more than 3, so those three are a complete
census of the demand above 3 and not a sample of it: there is no fourth item
hiding under a cap that never spoke. The old cap's damage is finished.

What is left is the shape of the number. The demand of 10 comes from one item
whose bundle holds **eleven** renderable files; ten went to vision and the
eleventh, a ``.docx``, was diverted to ``inspect_formatting`` by one rule in
``grader_routing`` -- overall-style wording, all paths ``.doc``/``.docx``.
``FORMATTING`` costs no render, so the arithmetic is right. But the same
submission with a ``.pptx`` in place of that ``.docx``, or with the criterion
worded slightly differently, plans 11 and fails closed. The cap clears the
demand by the width of one routing decision.

The gold corpus is not in that position and can be shown not to be. An item's
visual paths are a subset of its task's deliverable bundle, so the bundle's
renderable count is a ceiling on any single item's demand, and no bundle in
the checked-in 220-task gold manifest reaches 7. The 185-task gold run agrees
from the other side: cap 10 in force, not one refusal, six files the most any
item rendered.

Why this is a test and not a note. A refused item is not scored zero, it is
``score_excluded`` -- out of the numerator *and* the denominator -- so the
failure raises the headline it damages. The three refusals above cost 11
points of rubric and moved the published percentage the wrong way while doing
it. That is the failure mode this file is watching for, and at a margin of
zero it is one unlucky submission away.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

import pytest

from core.grader_routing import Modality, resolve_runtime_routing
from core.tool_calling_judge import (
    ToolCallingJudge,
    _VISUAL_RENDER_SCOPES,
    resolve_visual_file_cap,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = Path(__file__).resolve().parents[1]
GRADES_ROOT = REPO_ROOT / "data/grades"
GOLD_MANIFEST = (
    BATCH_RUNNER / "experiments/gold_corpus/gold_deliverable_manifest.json"
)

#: How the judge spells a refusal. ``planned`` is what the item's own plan
#: came to, so a refused item reports its demand exactly; a graded one has to
#: be read off what it rendered.
FILE_CAP_EVIDENCE = re.compile(
    r"required_visual_file_cap_exceeded:planned=(\d+),cap=(\d+)"
)

#: The cap in force before ``3eab549`` (#212, 2026-08-24). Every refusal in
#: this repository was refused at it. Not read from a config -- no shipped
#: config has ever set ``file_cap_per_item`` -- but from the refusals, which
#: carry the cap that produced them.
CAP_BEFORE_212 = 3

#: The largest per-item demand any committed payload records, and what the cap
#: has to clear. One number, two roles, which is the finding.
LARGEST_ITEM_DEMAND = 10

# ── the three refusals, by the ids that survive a re-index ───────────
# Keyed by rubric_item_id: an item's position in ``items`` moves when a rubric
# is re-ordered and these three are cited by count in the R1 error table.
REFUSED_DEMANDS = {
    # ``6d2c8e55`` -- 11 primaries, one criterion over all of them.
    "9b338cae-0e27-4c4d-8bc5-828acde5b634": 10,
    # ``94925f49`` -- both revived by #190. Before it, this task could not be
    # selected at all and these two were counted as selector errors.
    "61ff805a-98cb-4d48-8fc7-888e8a86cdc6": 5,
    "ff5597f6-0548-4a37-844d-506b7d1cbd27": 5,
}

# ── the two sol-220 runs, by fingerprint ─────────────────────────────
# Named rather than globbed: the filenames carry a grader hash, and the whole
# point of the pair is that the hash moved between them.
PUBLISHED_RUN = "src_1c967673eb8081a6"  # 2026-08-19, pre-#190
RERUN_AFTER_190 = "src_595c7254caf8fbd7"  # 2026-08-23, post-#190, pre-#212
GOLD_185_RUN = "src_79c2f5035c4aa826"  # 2026-08-31, cap 10 in force

#: Refusals per run. The rise is the point: #190 did not create demand, it
#: revived two items that had been failing earlier in the pipeline.
REFUSALS_PUBLISHED = 1
REFUSALS_AFTER_190 = 3

#: What the refusals cost, per merged run: 5 rubric points on the published
#: one, and 5+1+5 once #190 gave the other two items back. None of it scored
#: zero and none of it left in a denominator either.
RUBRIC_POINTS_DROPPED = {PUBLISHED_RUN: 5.0, RERUN_AFTER_190: 11.0}

# ── the gold corpus, measured through the judge's own planner ────────
GOLD_BUNDLE_RENDERABLES = {0: 42, 1: 136, 2: 30, 3: 9, 4: 2, 6: 1}
GOLD_LARGEST_BUNDLE = 6
GOLD_TASKS = 220

#: The most any single item on the 185-task gold run actually rendered.
GOLD_185_LARGEST_ITEM = 6


def _payloads() -> list[tuple[Path, dict]]:
    out = []
    for path in sorted(GRADES_ROOT.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict) and "tasks" in payload:
            out.append((path, payload))
    return out


def _item_demand(item: dict) -> int | None:
    """What this one rubric item asked the renderer for, or None if nothing.

    Two sources because there are two outcomes. A refused item never rendered,
    so its provenance is empty and its demand survives only in the marker. A
    graded item has no marker, so its demand is what it rendered -- a lower
    bound in principle, and a safe one here: an item that wanted more than the
    cap would carry the marker instead.
    """
    match = FILE_CAP_EVIDENCE.search(str(item.get("evidence") or ""))
    if match:
        return int(match.group(1))
    provenance = item.get("visual_provenance") or []
    return len(provenance) or None


@pytest.fixture(scope="module")
def committed_payloads() -> list[tuple[Path, dict]]:
    payloads = _payloads()
    assert payloads, "no committed grade payloads to measure against"
    return payloads


@pytest.fixture(scope="module")
def item_demands(committed_payloads) -> collections.Counter:
    demands: collections.Counter = collections.Counter()
    for _, payload in committed_payloads:
        for task in payload.get("tasks") or []:
            for item in task.get("items") or []:
                demand = _item_demand(item)
                if demand is not None:
                    demands[demand] += 1
    return demands


@pytest.fixture(scope="module")
def refusals(committed_payloads) -> list[tuple[str, str, int, int]]:
    """Every file-cap refusal on record, as (run, rubric_item_id, planned, cap).

    Merged payloads and their shards both hold the same refusal, so this is
    deliberately not deduplicated -- a claim about "every refusal" should have
    to hold for the shard copies too.
    """
    return [
        (path.name, item["rubric_item_id"], int(m.group(1)), int(m.group(2)))
        for path, payload in committed_payloads
        for task in payload.get("tasks") or []
        for item in task.get("items") or []
        if (m := FILE_CAP_EVIDENCE.search(str(item.get("evidence") or "")))
    ]


def _run(committed_payloads, fingerprint: str) -> dict:
    found = [
        payload
        for path, payload in committed_payloads
        if fingerprint in path.name and "_shards" not in path.parts
    ]
    assert len(found) == 1, f"{fingerprint} matched {len(found)} merged payloads"
    return found[0]


# ── the margin ───────────────────────────────────────────────────────

def test_no_committed_payload_wants_more_files_than_the_cap_allows(
    item_demands,
):
    """The invariant. It fails the day the cap starts costing points again.

    Not a restatement of the cap: an over-cap item is refused, and the marker
    it carries reports the demand it was refused at, so a payload landing with
    a demand of 11 shows up here as 11. That payload is one where a rubric
    item was dropped from both halves of a percentage, and the percentage went
    up. This is the cheapest place to notice.
    """
    cap = resolve_visual_file_cap({})
    over = {n: c for n, c in item_demands.items() if n > cap}

    assert not over, (
        f"items are being refused for want of file budget again: {over} "
        f"against a cap of {cap}"
    )


def test_the_cap_sits_exactly_on_the_largest_demand_ever_measured(
    item_demands,
):
    """10 and 10. Whichever of the two moves, this is where it is noticed.

    Lowering the cap is the obvious way to break it and not the likely one.
    The likely one is a corpus that grows into it -- a submission with eleven
    renderable primaries and one overall-style criterion is an ordinary thing
    for a model to produce, and this repository already holds a submission
    with exactly eleven.
    """
    cap = resolve_visual_file_cap({})

    assert max(item_demands) == LARGEST_ITEM_DEMAND
    assert cap == LARGEST_ITEM_DEMAND
    assert cap - max(item_demands) == 0, (
        "the margin between the per-item file cap and the largest demand "
        "this corpus has produced is no longer zero; the docstring of this "
        "file argues from it being zero and needs rewriting, not repinning"
    )


def test_the_margin_rests_on_one_routing_decision(committed_payloads):
    """Eleven renderable files, ten of them visual, and that is the whole gap.

    ``Journal_Club_Review_Email.docx`` is renderable -- ``.docx`` is in the
    render scopes and #189 put it there -- so nothing about the file keeps it
    out of the count. What keeps it out is ``grader_routing`` sending an
    overall-style criterion over ``.doc``/``.docx`` paths to
    ``inspect_formatting``, which costs no render and no vision call.

    So the recorded 10 is correct and is the answer to a slightly different
    question than "how big is this bundle". Rather than read the modalities
    back out of the payload, this re-runs the routing on the recorded criterion
    and paths: pinning the 10 alone would go on passing if that rule were
    narrowed, and the item would start planning 11 and failing closed at a cap
    this file says is sufficient.
    """
    task = next(
        t
        for _, payload in committed_payloads
        for t in payload.get("tasks") or []
        if t["task_id"].startswith("6d2c8e55")
    )
    item = next(
        i
        for i in task["items"]
        if i["rubric_item_id"] == "9b338cae-0e27-4c4d-8bc5-828acde5b634"
    )
    children = item["child_grades"]
    every_path = [p for c in children for p in c["selected_paths"]]

    assert len(children) == 11
    assert len(ToolCallingJudge.planned_supported_visual_names(every_path)) == 11

    # Routed now, on this revision, from the criterion and paths the run
    # recorded -- and it has to still agree with what the run decided.
    routed = {
        path: resolve_runtime_routing(item["criterion"], [path]).modality
        for path in every_path
    }
    assert [
        c["routing_modality"] for c in children
    ] == [routed[p].value for c in children for p in c["selected_paths"]]

    visual_paths = [p for p, m in routed.items() if m is Modality.VISUAL]
    diverted = [p for p, m in routed.items() if m is not Modality.VISUAL]

    assert (
        len(ToolCallingJudge.planned_supported_visual_names(visual_paths))
        == LARGEST_ITEM_DEMAND
    )
    assert diverted == ["Journal_Club_Review_Email.docx"]
    assert routed[diverted[0]] is Modality.FORMATTING
    assert Path(diverted[0]).suffix.lower() in _VISUAL_RENDER_SCOPES
    assert 11 > resolve_visual_file_cap({}), (
        "the eleventh file is the point: were it routed to vision the item "
        "would plan 11 and be refused at the current cap"
    )


# ── the refusals on record, and why they are finished ────────────────

def test_every_refusal_this_corpus_holds_was_refused_at_the_old_cap(refusals):
    """Three at cap 3, none at 10 -- read off the refusals, not off a config.

    Worth separating from the demand measurement because the two failures look
    identical in a summary. "No item is over the cap now" and "the cap that
    refused these was a different cap" are different claims, and only the
    second one retires the R1 error-table row.
    """
    assert refusals, "the evidence this file argues from has gone missing"
    assert {cap for *_, cap in refusals} == {CAP_BEFORE_212}


def test_the_three_refused_items_would_all_be_graded_today(refusals):
    """10, 5, 5 -- and 3 is a census, not a sample.

    A run at cap 3 refuses every item wanting more than 3, so these three are
    the complete set of items in this corpus whose demand exceeded 3. There is
    no fourth demand hiding below a threshold that never fired, which is what
    makes "all of them clear 10" a statement about the corpus rather than
    about three items that happened to be visible.
    """
    cap = resolve_visual_file_cap({})
    by_item = {rid: planned for _, rid, planned, _ in refusals}

    assert by_item == REFUSED_DEMANDS
    assert max(by_item.values()) <= cap
    assert min(by_item.values()) > CAP_BEFORE_212


def test_the_refusals_did_not_lower_a_score_they_left_it_out(
    committed_payloads,
):
    """Rubric points excluded from both halves, verdict ``judge_error``.

    This is the reason a cap failure is worth a test at all. Scored zero, the
    three would have shown up as a fall in the published percentage. Excluded,
    they leave the numerator and the denominator together and the percentage
    goes *up* -- the grading failure improves the number it damages, and
    nothing in a headline distinguishes the two.

    The per-run totals are separated rather than summed because the two runs
    are not two measurements of one loss: 5 is what the published number is
    missing, 11 is what a re-run at the old cap would have been missing.
    """
    caught = 0
    points: collections.Counter = collections.Counter()
    for path, payload in committed_payloads:
        for task in payload.get("tasks") or []:
            for item in task.get("items") or []:
                if not FILE_CAP_EVIDENCE.search(str(item.get("evidence") or "")):
                    continue
                caught += 1
                assert item["verdict"] == "judge_error"
                assert item["score_excluded"] is True
                assert item["awarded_score"] == 0.0
                assert item["perception_called"] is False
                assert list(item.get("visual_provenance") or []) == []
                assert int(item.get("render_call_count") or 0) == 0
                if "_shards" not in path.parts:
                    run = next(r for r in RUBRIC_POINTS_DROPPED if r in path.name)
                    points[run] += float(item["max_score"])

    assert caught
    assert dict(points) == RUBRIC_POINTS_DROPPED


def test_the_second_and_third_refusals_are_items_190_gave_back(
    committed_payloads,
):
    """The R1 table's ``(+#190 이후 N)`` column, measured.

    Both items exist in the earlier run too, failing for an entirely different
    reason: the selector could not choose among same-format candidates, so the
    task never reached a render plan. #190 fixed that and the two items walked
    straight into the file cap. They are not new demand -- they moved between
    buckets, which is why the R1 residual falls rather than holds when both
    fixes are counted.
    """
    published = _run(committed_payloads, PUBLISHED_RUN)
    rerun = _run(committed_payloads, RERUN_AFTER_190)

    def refused(payload: dict) -> set[str]:
        return {
            item["rubric_item_id"]
            for task in payload["tasks"]
            for item in task["items"]
            if FILE_CAP_EVIDENCE.search(str(item.get("evidence") or ""))
        }

    assert len(refused(published)) == REFUSALS_PUBLISHED
    assert len(refused(rerun)) == REFUSALS_AFTER_190
    assert refused(published) < refused(rerun)

    revived = refused(rerun) - refused(published)
    earlier = {
        item["rubric_item_id"]: item
        for task in published["tasks"]
        for item in task["items"]
        if item["rubric_item_id"] in revived
    }
    assert set(earlier) == revived
    for item in earlier.values():
        assert item["selection_status"] == "selection_error"
        assert item["verdict"] == "judge_error"
        assert item["routing_modality"] is None


# ── the corpus that cannot reach the cap, and can be shown not to ────

def test_no_gold_bundle_holds_enough_renderable_files_to_reach_the_cap():
    """A ceiling, not an observation: 6 files is the biggest bundle there is.

    An item's visual paths come out of its task's selected deliverables, so a
    bundle's renderable count bounds every item on that task at once. Counting
    the bundles therefore says something the graded run cannot: not "no item
    hit the cap on the day", but "no item on this corpus can".

    Counted through ``planned_supported_visual_names`` rather than by suffix
    so that the ceiling moves if the render scopes do -- #400 adding five
    video extensions is exactly the kind of change that raises demand without
    touching a cap.
    """
    manifest = json.loads(GOLD_MANIFEST.read_text(encoding="utf-8"))
    counts: collections.Counter = collections.Counter()
    for task in manifest["tasks"]:
        names = [f["graded_path"] for f in task.get("files") or []]
        counts[len(ToolCallingJudge.planned_supported_visual_names(names))] += 1

    assert sum(counts.values()) == GOLD_TASKS
    assert dict(sorted(counts.items())) == GOLD_BUNDLE_RENDERABLES
    assert max(counts) == GOLD_LARGEST_BUNDLE
    assert resolve_visual_file_cap({}) - max(counts) == 4


def test_the_gold_run_agrees_from_the_other_side(committed_payloads):
    """Cap 10 in force, no refusal, and six is the most anything rendered.

    The manifest count and this are independent: one is a plan derived from
    checked-in bytes, the other is what a paid run did. They meet at 6, which
    is the check that the manifest is the corpus that was graded and not a
    stale copy of it.
    """
    gold = _run(committed_payloads, GOLD_185_RUN)
    items = [i for t in gold["tasks"] for i in t["items"]]
    rendered = [len(i.get("visual_provenance") or []) for i in items]

    assert gold["judge"]["visual_file_cap"] == resolve_visual_file_cap({})
    assert not [
        i for i in items if FILE_CAP_EVIDENCE.search(str(i.get("evidence") or ""))
    ]
    assert max(rendered) == GOLD_185_LARGEST_ITEM == GOLD_LARGEST_BUNDLE
