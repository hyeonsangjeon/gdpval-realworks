"""How much of a published score each sub-judge decided.

Every graded item has carried ``routing_modality`` for as long as routing has
existed, and nothing has ever added it up. The only code that counted routes
was ``scripts/analyze_audio_repeat_variation.py``, pinned to one cohort, so
"how many audio items are in this run" was answerable by downloading an 18 MB
payload and counting by hand -- and only by whoever thought to ask.

That became the wrong place for the number to live the moment a route's
trustworthiness came into question. The audio sub-judge measures at a
discrimination of 0.00 against synthetic clips whose answers are known: it
cannot tell a correct clip from a wrong one. The question that follows is not
about the sub-judge, it is about the run -- *how much of this average rests on
it* -- and a property of the run should be stated by the run.

So ``summary.routing`` reports, per route, the items, the items that actually
counted, the rubric weight those carry, and the tasks touched. Symmetrically,
for all five routes. This file does not assert that audio should be dropped;
that is the owner's call, and a summariser that pre-empted it by publishing
``avg_score_pct_excluding_audio`` would be making the decision rather than
informing it. What is asserted is that the ingredients are correct.

The load-bearing test in here is
:func:`test_a_run_that_recorded_no_routes_reports_none_not_zero`. Twelve
committed payloads predate routing entirely, and every item in them carries
``routing_modality: null``. Zero-filling those into ``audio: 0`` would turn
"never asked" into "asked and found none" -- which is precisely the reading
this field exists to prevent, and it would read as *reassuring*.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from step8_grade import _ROUTING_MODALITIES, _compute_summary, _routing_stats


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = Path(__file__).resolve().parents[1]
GRADES_ROOT = REPO_ROOT / "data/grades"
SCHEMA = BATCH_RUNNER / "schemas/grade.schema.json"

#: The 185-task gold corpus, by the fingerprint its payloads carry rather than
#: by filename -- filenames encode a config hash, and a hash moves.
CORPUS_FINGERPRINT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)

# ── measured on that corpus, pinned ──────────────────────────────────
# These are the numbers the owner's decision about the audio sub-judge is
# being made from. Pinned rather than re-derived, so that a payload which
# stops producing them is a failure here and not a silently different premise
# under a decision that was already taken.
GOLD_TASKS = 185
GOLD_ITEMS = 8816
GOLD_AUDIO_ITEMS = 31
GOLD_AUDIO_TASKS = 3
GOLD_AUDIO_SCORED_WEIGHT = 50.0
GOLD_SCORED_WEIGHT = 14117.0  # every route, so the share below is a share


def _item(modality: object, *, max_score: float = 1.0, excluded: bool = False) -> dict:
    item = {"routing_modality": modality, "max_score": max_score, "score": 0.0}
    if excluded:
        item["score_excluded"] = True
    return item


def _task(*items: dict, error: str | None = None) -> dict:
    # `pct` is what `_compute_summary` averages; `_routing_stats` never reads
    # it, and the tests that go through the summary need a task to be a task.
    task: dict = {"task_id": "t", "pct": 50.0, "items": list(items)}
    if error:
        task["error"] = error
    return task


# ── the population ───────────────────────────────────────────────────


def test_items_counts_every_task_including_the_ones_that_failed() -> None:
    """The corpus figure, not the scored figure.

    "31 of 8,816 items route audio" is a claim about what is in the corpus. A
    task that errored still had its rubric parsed and its items routed, and
    leaving those out would quietly shrink the denominator of a sentence that
    is being read as a statement about the whole run.
    """
    stats = _routing_stats(
        [
            _task(_item("audio"), _item("text")),
            _task(_item("audio"), error="judge exploded"),
        ]
    )

    assert stats["items"]["audio"] == 2
    assert stats["tasks"]["audio"] == 2
    # ...and the errored one is not in what the average was made of.
    assert stats["scored_items"]["audio"] == 1


def test_tasks_counts_tasks_and_not_items() -> None:
    """One item in ten tasks is a different problem from ten in one task.

    The first is a caveat that has to go on the whole corpus; the second is a
    footnote on a single row. A count of items cannot tell them apart.
    """
    spread = _routing_stats([_task(_item("audio")) for _ in range(10)])
    concentrated = _routing_stats([_task(*[_item("audio") for _ in range(10)])])

    assert spread["items"]["audio"] == concentrated["items"]["audio"] == 10
    assert spread["tasks"]["audio"] == 10
    assert concentrated["tasks"]["audio"] == 1


def test_a_task_using_a_route_twice_is_still_one_task() -> None:
    stats = _routing_stats([_task(_item("visual"), _item("visual"), _item("text"))])

    assert stats["items"]["visual"] == 2
    assert stats["tasks"]["visual"] == 1
    assert stats["tasks"]["text"] == 1


# ── what actually moved the number ───────────────────────────────────


def test_scored_items_are_scoped_exactly_like_the_exclusion_summary() -> None:
    """Two summarisers over one payload must agree on what the average is.

    ``score_exclusions`` already answers "which items left the denominator",
    over tasks without an ``error`` and items not ``score_excluded``. If
    ``routing`` scoped its own subset even slightly differently, the two
    fields would disagree about the same run and there would be no way to
    tell from the outside which one to believe.
    """
    tasks = [
        _task(_item("visual"), _item("visual", excluded=True)),
        _task(_item("visual"), error="dropped"),
    ]

    stats = _routing_stats(tasks)
    summary = _compute_summary(tasks)

    assert stats["items"]["visual"] == 3
    assert stats["scored_items"]["visual"] == 1

    # The same three items, partitioned by the neighbouring field: one scored,
    # one excluded, one inside an errored task and so outside both.
    assert summary["score_exclusions"]["excluded_items"] == 1
    assert summary["routing"]["scored_items"]["visual"] == 1


def test_a_penalty_items_negative_weight_is_not_weight() -> None:
    """Same convention as ``excluded_max_score``, and for the same reason.

    ``scored_max_score`` exists to answer "what would leave the denominator if
    this route were dropped". A penalty item carrying ``max_score: -5`` is not
    five points of denominator; summing it raw would understate the route and
    make dropping it look cheaper than it is.
    """
    stats = _routing_stats(
        [_task(_item("audio", max_score=4.0), _item("audio", max_score=-5.0))]
    )

    assert stats["scored_max_score"]["audio"] == 4.0
    assert stats["scored_items"]["audio"] == 2  # counted, just not as weight


def test_weight_ignores_items_that_are_not_in_the_average() -> None:
    stats = _routing_stats(
        [
            _task(_item("audio", max_score=2.0), _item("audio", max_score=8.0, excluded=True)),
            _task(_item("audio", max_score=100.0), error="never graded"),
        ]
    )

    assert stats["items"]["audio"] == 3
    assert stats["scored_max_score"]["audio"] == 2.0


def test_a_missing_or_unreadable_weight_is_zero_and_not_a_crash() -> None:
    """A malformed weight must not take the whole summary down with it.

    This runs at the end of a grading run that has already been paid for.
    """
    stats = _routing_stats(
        [
            _task(
                {"routing_modality": "text", "max_score": None},
                {"routing_modality": "text"},
                {"routing_modality": "text", "max_score": 3},
            )
        ]
    )

    assert stats["scored_items"]["text"] == 3
    assert stats["scored_max_score"]["text"] == 3.0


# ── absence is not zero ──────────────────────────────────────────────


def test_a_run_that_recorded_no_routes_reports_none_not_zero() -> None:
    """The reading this whole object exists to prevent.

    Twelve committed payloads predate routing: every item in them carries
    ``routing_modality: null``. If those reported ``audio: 0`` they would be
    saying "we looked, there is no audio here" about a run that never looked,
    and a reader deciding what to do about the audio sub-judge would take that
    as the good news it is not.
    """
    stats = _routing_stats([_task(_item(None), _item(None)), _task(_item(None))])

    assert stats["recorded"] is False
    assert stats["items"] == {}
    assert stats["scored_items"] == {}
    assert stats["scored_max_score"] == {}
    assert stats["tasks"] == {}
    assert stats["unrecorded_items"] == 3
    assert "audio" not in stats["items"]


def test_a_run_that_did_record_reports_a_measured_zero() -> None:
    """The mirror, and the reason the empty maps above are not just sloppiness.

    Once a run is recording routes, "no audio" is a finding. Every route in
    the schema's enum gets a count, including the four this run did not use,
    because a zero that was measured is worth publishing.
    """
    stats = _routing_stats([_task(_item("text"), _item("text"))])

    assert stats["recorded"] is True
    assert stats["items"]["audio"] == 0
    assert stats["scored_items"]["visual"] == 0
    assert stats["scored_max_score"]["formatting"] == 0.0
    assert stats["tasks"]["mixed"] == 0
    assert stats["unrecorded_items"] == 0
    assert set(stats["items"]) == set(_ROUTING_MODALITIES)


def test_a_partly_instrumented_run_reports_both_halves() -> None:
    """Not hypothetical: two committed 220-task payloads look exactly like this.

    They carry 8,844 routed items and 1,609 unrouted ones. Reporting only the
    routed part would overstate how much of the run the record covers;
    reporting only ``recorded: false`` would throw away a real measurement.
    """
    stats = _routing_stats([_task(_item("audio"), _item(None), _item(""))])

    assert stats["recorded"] is True
    assert stats["items"]["audio"] == 1
    assert stats["unrecorded_items"] == 2


def test_an_empty_run_has_not_measured_anything() -> None:
    assert _routing_stats([])["recorded"] is False
    assert _routing_stats([_task()])["unrecorded_items"] == 0


def test_a_route_that_is_not_a_string_is_unrecorded_not_a_key() -> None:
    """Whatever a malformed payload puts there, it is not a route name."""
    stats = _routing_stats([_task(_item(0), _item(True), _item(["audio"]), _item({}))])

    assert stats["recorded"] is False
    assert stats["unrecorded_items"] == 4


# ── a route nobody downstream knows yet ──────────────────────────────


def test_a_route_outside_the_enum_is_counted_and_not_dropped() -> None:
    """A new sub-judge should be visible here before anything is taught its name.

    Dropping unknown routes would make the first run of a new one report as a
    run with fewer items than it graded, which is the failure mode that hides
    a new route's weight for exactly as long as nobody looks.
    """
    stats = _routing_stats([_task(_item("hologram", max_score=7.0), _item("text"))])

    assert stats["items"]["hologram"] == 1
    assert stats["scored_max_score"]["hologram"] == 7.0
    assert stats["unrecorded_items"] == 0
    # ...and the known routes are still all present beside it.
    assert set(_ROUTING_MODALITIES) <= set(stats["items"])


def test_the_route_names_here_are_the_route_names_in_the_schema() -> None:
    """Drift guard.

    ``_ROUTING_MODALITIES`` exists so that unused routes still get a zero. If
    the schema grows a route and this tuple does not, that route's zero
    silently stops being published -- absence again, wearing a different hat.
    """
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enum = schema["properties"]["tasks"]["items"]["properties"]["items"]["items"][
        "properties"
    ]["routing_modality"]["enum"]

    assert set(_ROUTING_MODALITIES) == {name for name in enum if name is not None}


# ── the merged-shard property ────────────────────────────────────────


def test_two_shards_summarised_together_are_the_sum_of_their_parts() -> None:
    """``step9_merge_shards`` re-summarises merged tasks rather than merging
    summaries, and this is the property that makes that produce the same
    answer a serial run would have. It also means a payload published before
    this field existed reports the same numbers when re-summarised.
    """
    left = [_task(_item("audio", max_score=2.0), _item("text"))]
    right = [_task(_item("audio", max_score=3.0)), _task(_item("visual"))]

    merged = _routing_stats(left + right)
    a, b = _routing_stats(left), _routing_stats(right)

    for route in _ROUTING_MODALITIES:
        assert merged["items"][route] == a["items"][route] + b["items"][route]
        assert merged["tasks"][route] == a["tasks"][route] + b["tasks"][route]
        assert merged["scored_max_score"][route] == pytest.approx(
            a["scored_max_score"][route] + b["scored_max_score"][route]
        )


# ── against the run the decision is about ────────────────────────────


@pytest.fixture(scope="module")
def gold_run() -> dict:
    found = []
    for path in sorted(GRADES_ROOT.rglob("*.json")):
        if "_shards" in path.parts or "_repeats" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("expected_ordered_task_ids_sha256") == CORPUS_FINGERPRINT
            and payload.get("run_status") == "final"
            and len(payload.get("tasks") or []) == GOLD_TASKS
        ):
            found.append(payload)
    if not found:
        pytest.skip("the 185-task gold payload is not in this checkout")
    return found[0]


def test_the_gold_run_reproduces_the_figure_the_decision_cites(gold_run: dict) -> None:
    """"31 of 8,816", from the summariser instead of from a one-off script.

    The number reached the owner through
    ``scripts/analyze_audio_repeat_variation.py``, which is pinned to one
    cohort and answers no question about any other run. Getting the same
    answer out of ``_routing_stats`` is what moves it from a finding somebody
    made once into something every run states about itself.
    """
    stats = _routing_stats(gold_run["tasks"])

    assert sum(stats["items"].values()) == GOLD_ITEMS
    assert stats["items"]["audio"] == GOLD_AUDIO_ITEMS
    assert stats["tasks"]["audio"] == GOLD_AUDIO_TASKS
    assert stats["unrecorded_items"] == 0


def test_the_gold_run_says_what_dropping_audio_would_cost(gold_run: dict) -> None:
    """The number the decision actually needs, which nothing published before.

    Not "are 31 items a lot" -- items are not comparable across rubrics -- but
    what share of the graded weight would leave the denominator. It is 0.35%,
    over three tasks of 185. That is a fact about the size of the problem, and
    it is the owner's to act on; this test only holds it steady.
    """
    stats = _routing_stats(gold_run["tasks"])
    weight = stats["scored_max_score"]

    assert weight["audio"] == pytest.approx(GOLD_AUDIO_SCORED_WEIGHT)
    assert sum(weight.values()) == pytest.approx(GOLD_SCORED_WEIGHT)

    share = weight["audio"] / sum(weight.values()) * 100
    assert share == pytest.approx(0.354, abs=0.005)


def test_the_gold_runs_scored_subset_matches_its_own_exclusion_figures(
    gold_run: dict,
) -> None:
    """On a real payload, not a three-item fixture.

    ``items`` minus ``scored_items``, summed over routes, is exactly the
    excluded items plus everything inside an errored task. If the two
    summarisers ever drift apart, they drift here first.
    """
    stats = _routing_stats(gold_run["tasks"])

    excluded_or_errored = sum(
        1
        for task in gold_run["tasks"]
        for item in task.get("items", [])
        if task.get("error") or item.get("score_excluded")
    )

    assert sum(stats["items"].values()) - sum(stats["scored_items"].values()) == (
        excluded_or_errored
    )


# ── what the run publishes ───────────────────────────────────────────


def test_the_summary_carries_it_beside_the_other_two_compositions() -> None:
    summary = _compute_summary([_task(_item("audio"), _item("text"))])

    assert summary["routing"]["items"]["audio"] == 1
    # Beside the neighbours it is scoped against, not inside `wow` -- those are
    # rates about how the grading went, this is what was graded.
    assert {"routing", "visual_budget", "score_exclusions"} <= set(summary)


def test_a_grade_written_before_this_field_existed_still_validates() -> None:
    """``routing`` is not in ``summary.required``, deliberately.

    Every payload in ``data/grades`` was written without it -- the 185-task
    gold run's summary has seven keys and this is not one of them. Requiring
    it would invalidate the entire published record to add a field to future
    runs, which is not a trade this change is worth.
    """
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    summary_schema = schema["properties"]["summary"]

    assert "routing" in summary_schema["properties"]
    assert "routing" not in summary_schema.get("required", [])
    # The same call the neighbouring optional fields made.
    assert "visual_budget" not in summary_schema.get("required", [])


def test_the_published_shape_is_what_the_schema_describes() -> None:
    jsonschema = pytest.importorskip("jsonschema")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    routing_schema = schema["properties"]["summary"]["properties"]["routing"]

    for stats in (
        _routing_stats([_task(_item("audio", max_score=2.0), _item(None))]),
        _routing_stats([_task(_item(None))]),
        _routing_stats([]),
    ):
        jsonschema.validate(stats, routing_schema)
        assert set(routing_schema["required"]) <= set(stats)
