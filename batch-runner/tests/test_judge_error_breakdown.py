"""Tests for the judge-error breakdown tool.

Two things here are worth more than the rest.

The first is ``test_the_tool_reproduces_the_published_run_exactly``. The whole
value of the tool is that its split adds up: 243 + 74 + 12 + 4 = 333, the
number the sol-220 run already published, with nothing left over. A split that
loses or invents an error is worse than no split, because it would be read as
evidence about which fixes worked. The corpus is checked in, so this is a real
regression test rather than a mock.

The second is ``test_the_borrowed_rate_still_matches_grade_payload``. The
script copies ``canonical_rate`` instead of importing it, to stay free of the
grading stack, and a copy can drift. It is held to the original over a grid
that includes exact ties -- and a companion test proves the grid actually has
teeth by showing a ``round()``-based rate disagrees on some of them.

The rest are constructed cases, one per branch of ``classify_error``, plus the
properties that make the output trustworthy: an unrecognised failure shape is
reported rather than absorbed, precheck items stay out of the denominator, and
a paired comparison says so when the two sides are not the same items.
"""

import ast
import json
from pathlib import Path

import pytest

from scripts import judge_error_breakdown as jeb


REPO_ROOT = Path(__file__).resolve().parents[2]

# The sol-220 run that is badged OFFICIAL on the dashboard. Matched by its
# source-hash segment rather than the full stem, which also carries the config,
# rubric and inference hashes and is 200 characters long.
PUBLISHED_SRC = "src_1c967673eb8081a6"

# What that run's 333 judge errors are, once split by cause. Transcribed on
# purpose: unlike the rate, there is no published field to check the split
# against, so these numbers are the record of what the corpus contained when
# the classifier was written.
PUBLISHED_TOTALS = {
    "tasks": 220,
    "judge_items": 10453,
    "errors": 333,
    "selector_ambiguous": 243,
    "render_target_missing": 68,
    "wrong_format": 12,
    "nothing_submitted": 6,
    "judge_no_verdict": 4,
    "unclassified": 0,
}


def _published_corpus():
    """Return the published shard directory, or ``None`` if it is not here."""
    root = REPO_ROOT / "data" / "grades" / "_shards"
    if not root.is_dir():
        return None
    matches = [p for p in root.iterdir() if p.is_dir() and PUBLISHED_SRC in p.name]
    return matches[0] if len(matches) == 1 else None


def _item(verdict="judge_error", decided_by="judge", **fields):
    item = {"decided_by": decided_by, "verdict": verdict}
    item.update(fields)
    return item


def _payload(items, *, published_rate=None, task_count=1, task_prefix="t"):
    """One grade payload holding ``items``, spread over ``task_count`` tasks."""
    tasks = [
        {"task_id": f"{task_prefix}-{index}", "items": []}
        for index in range(task_count)
    ]
    for offset, item in enumerate(items):
        tasks[offset % task_count]["items"].append(item)
    payload = {"tasks": tasks}
    if published_rate is not None:
        payload["summary"] = {"wow": {"judge_error_rate": published_rate}}
    return payload


def _write(directory: Path, name: str, payload) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# the borrowed arithmetic
# --------------------------------------------------------------------------


RATE_GRID = [
    (num, den)
    for den in (1, 3, 6, 7, 16, 1081, 10453, 20000, 40000)
    for num in range(0, min(den, 60) + 1)
]


def test_the_borrowed_rate_still_matches_grade_payload():
    """The copy must agree with the function the grader publishes with.

    Checked against the real implementation rather than a table of expected
    values, so that a change to how the grader rounds fails here instead of
    letting this tool quietly report a rate nobody else would get.
    """
    from core.grade_payload import canonical_rate as original

    mismatches = [
        (num, den, jeb.canonical_rate(num, den), original(num, den))
        for num, den in RATE_GRID
        if jeb.canonical_rate(num, den) != original(num, den)
    ]
    assert mismatches == []

    # Degenerate denominators are defined, not crashes: a shard with no
    # judge-decided items has a rate of zero, not a ZeroDivisionError.
    for den in (0, -1):
        assert jeb.canonical_rate(5, den) == original(5, den) == 0.0


def test_a_round_based_rate_would_disagree_on_ties():
    """Proof that the grid above is not vacuous.

    ``canonical_rate`` rounds half-*up* with integer arithmetic. The obvious
    reimplementation, ``round(num / den, 4)``, rounds half-to-even, and the
    difference only shows on exact ties. If the grid contained no ties, the
    equivalence test would pass for a wrong copy, so this pins down that it
    does contain them.
    """
    disagreements = [
        (num, den)
        for num, den in RATE_GRID
        if jeb.canonical_rate(num, den) != round(num / den, 4) if den > 0
    ]
    assert disagreements, "the rate grid no longer exercises half-up rounding"


# --------------------------------------------------------------------------
# the published corpus
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    _published_corpus() is None,
    reason=(
        f"the published sol-220 shards (data/grades/_shards/*{PUBLISHED_SRC}*) "
        "are not in this checkout"
    ),
)
def test_the_tool_reproduces_the_published_run_exactly():
    """The split must account for all 333 errors and invent none.

    ``unclassified == 0`` is the assertion that carries the weight. The
    headline rate has been quoted in the roadmap and on the dashboard, and the
    reason to split it was to say which part of it we caused. A split with
    leftovers cannot answer that.
    """
    total = jeb.total_of(jeb.read_breakdowns([_published_corpus()]))

    got = {
        "tasks": total.tasks,
        "judge_items": total.judge_items,
        "errors": total.errors,
        **{name: total.buckets[name] for name in jeb.BUCKETS},
    }
    assert got == PUBLISHED_TOTALS
    assert total.rate == 0.0319
    assert sum(total.buckets.values()) == total.errors
    assert total.harness_errors == 243 + 68
    assert total.judge_side_errors == 4
    assert total.model_errors == 12 + 6
    # 311 of the 333 are ours. The published run's headline 3.19% is very
    # nearly a measure of this harness, not of the model under test.
    assert total.harness_errors + total.judge_side_errors + total.model_errors == 333


@pytest.mark.skipif(
    _published_corpus() is None,
    reason=(
        f"the published sol-220 shards (data/grades/_shards/*{PUBLISHED_SRC}*) "
        "are not in this checkout"
    ),
)
def test_every_published_shard_rate_recomputes():
    """Per shard, this tool's numerator must be the grader's numerator.

    Recomputing each of the nine shards and getting the published number back
    is stronger than checking the totals, which could match by two errors
    cancelling.

    It does *not* check the denominator filter. Every one of the 10453 items
    in this corpus is ``decided_by == "judge"``, so dropping the filter
    entirely would not move a single shard's rate. That branch is only
    exercised by ``test_precheck_items_are_not_in_the_denominator``, and if
    this corpus is ever replaced by one containing precheck decisions, this
    test gets stronger rather than weaker.
    """
    parts = jeb.read_breakdowns([_published_corpus()])
    assert len(parts) == 9

    disagreements = [
        (part.label, part.published_rate, part.rate)
        for part in parts
        if part.published_rate is None or part.published_rate != part.rate
    ]
    assert disagreements == []

    # And the spread is the reason ``--baseline`` exists at all: judging a fix
    # by comparing one shard against the whole-run rate would be meaningless.
    rates = sorted(part.rate for part in parts)
    assert rates[0] < 0.01 < 0.09 < rates[-1]


@pytest.mark.skipif(
    _published_corpus() is None,
    reason=(
        f"the published sol-220 shards (data/grades/_shards/*{PUBLISHED_SRC}*) "
        "are not in this checkout"
    ),
)
def test_the_judge_bucket_holds_only_judge_side_failures():
    """Cross-check the structural rule against the prose it refuses to read.

    ``classify_error`` decides from structured fields on purpose, so nothing
    rebuckets when a message is reworded. The cost of that is no feedback if
    the rule is aimed at the wrong thing -- which it was: this bucket was
    called ``empty_output`` and filed under the model under test, and the
    rerun showed ``final_json_parse_failed`` in it. That string comes from
    ``core.tool_calling_judge._finalization_retry_reason``, and it describes
    the *judge's* answer failing to parse, not a submission.

    So read the evidence here and nowhere else, as an assertion rather than as
    a classifier: everything the structural rule puts in this bucket must be
    one of the reasons that function emits. A new shape appearing here means
    the rule is catching something it was not aimed at, and the bucket name is
    lying about the cause.
    """
    judge_side = ("empty_final_text", "final_json_parse_failed", "invalid_final_envelope")
    found = set()
    for part_path in sorted(_published_corpus().glob("shard-*.json")):
        payload = json.loads(part_path.read_text(encoding="utf-8"))
        for task in payload["tasks"]:
            for item in task.get("items") or []:
                if item.get("decided_by") != "judge":
                    continue
                if item.get("verdict") != "judge_error":
                    continue
                if jeb.classify_error(item) != "judge_no_verdict":
                    continue
                evidence = str(item.get("evidence") or "")
                # ``empty_final_text`` carries a ``:finish_reason`` suffix.
                assert evidence.startswith(judge_side), evidence
                found.add(evidence.split(":")[0])

    # If the corpus ever stops containing any, this test would pass vacuously.
    assert found == {"empty_final_text"}


@pytest.mark.skipif(
    _published_corpus() is None,
    reason=(
        f"the published sol-220 shards (data/grades/_shards/*{PUBLISHED_SRC}*) "
        "are not in this checkout"
    ),
)
def test_the_placeholder_bucket_is_drawn_from_the_render_failures():
    """Show that this bucket took its members from the harness, not the judge.

    Asserting that these items carry the placeholder would be circular -- that
    is the rule. What is worth asserting is where they came from, so read the
    evidence prose here, as an assertion and not as a classifier: every one of
    them reports a missing render target. That is what makes the split a
    correction rather than a new category. Before this, all six counted as
    ``render_target_missing`` and were reported as our defect, which put the
    remaining harness residue at seven when it is one.

    The task-level check is the other half: a placeholder means inference
    produced no file, so the task cannot have scored. If one of these ever sits
    on a task that scored, the rule is catching something other than a blank.
    """
    tasks_seen = {}
    evidence_shapes = set()
    for part_path in sorted(_published_corpus().glob("shard-*.json")):
        payload = json.loads(part_path.read_text(encoding="utf-8"))
        for task in payload["tasks"]:
            for item in task.get("items") or []:
                if item.get("decided_by") != "judge":
                    continue
                if item.get("verdict") != "judge_error":
                    continue
                if jeb.classify_error(item) != "nothing_submitted":
                    continue
                evidence = str(item.get("evidence") or "")
                assert "render_target_unavailable" in evidence, evidence
                evidence_shapes.add(evidence)
                tasks_seen[task["task_id"]] = task

    # Non-vacuous, and the whole bucket is one blank submission.
    assert len(tasks_seen) == 1
    assert evidence_shapes == {"required_visual_render_target_unavailable"}
    task = next(iter(tasks_seen.values()))
    assert task["total_awarded"] == 0.0
    assert task["total_max"] > 0

    # And the counts move as a correction: what left the harness is exactly
    # what arrived at the model.
    total = jeb.total_of(jeb.read_breakdowns([_published_corpus()]))
    assert total.buckets["nothing_submitted"] == 6
    assert total.buckets["render_target_missing"] == 74 - 6


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "item, expected",
    [
        # The selector declined to choose between same-format candidates.
        ({"selection_status": "selection_error"}, "selector_ambiguous"),
        # It chose, but nothing it could choose was in a requested format.
        ({"selection_status": "wrong_format_primary"}, "wrong_format"),
        # Selection was fine; the judge was routed to look at something and
        # there was nothing rendered to look at.
        (
            {
                "selection_status": "ok",
                "routing_modality": "visual",
                "visual_provenance": [],
            },
            "render_target_missing",
        ),
        (
            {
                "selection_status": "ok",
                "routing_modality": "mixed",
                "visual_provenance": None,
            },
            "render_target_missing",
        ),
        (
            {"selection_status": "ok", "routing_modality": "mixed"},
            "render_target_missing",
        ),
        # Selection was fine and the route was text, so the work reached the
        # judge and the judge is what failed -- empty final text, unparseable
        # output, or an envelope that would not validate.
        ({"selection_status": "ok", "routing_modality": "text"}, "judge_no_verdict"),
        # Nothing was submitted. Named by target, by path, and by both --
        # whichever the grader wrote, the answer is the same. Each of these
        # would otherwise have been read as a render-target miss, blaming the
        # renderer for a file that was never produced.
        (
            {
                "selection_status": "ok",
                "routing_modality": "visual",
                "visual_provenance": [],
                "target_ids": ["failed_to_generate"],
            },
            "nothing_submitted",
        ),
        (
            {
                "selection_status": "ok",
                "routing_modality": "visual",
                "visual_provenance": [],
                "selected_paths": ["failed_to_generate.txt"],
            },
            "nothing_submitted",
        ),
        (
            {
                "selection_status": "ok",
                "routing_modality": "visual",
                "visual_provenance": [],
                "target_ids": ["failed_to_generate"],
                "selected_paths": ["failed_to_generate.txt"],
            },
            "nothing_submitted",
        ),
        # And it outranks the text route too: a placeholder graded as text is
        # still nothing submitted, not the judge declining to answer.
        (
            {
                "selection_status": "ok",
                "routing_modality": "text",
                "target_ids": ["failed_to_generate"],
            },
            "nothing_submitted",
        ),
    ],
)
def test_each_failure_shape_lands_in_its_own_bucket(item, expected):
    assert jeb.classify_error(item) == expected


@pytest.mark.parametrize(
    "item, expected",
    [
        # The selector's own failures are decided before anything is looked at,
        # so they keep their bucket even when a placeholder is what it landed
        # on. Which of the two is reported matters: `#190` is measured by the
        # selector count, and letting a placeholder silently drain it would
        # make an unfixed selector look fixed.
        (
            {
                "selection_status": "selection_error",
                "target_ids": ["failed_to_generate"],
            },
            "selector_ambiguous",
        ),
        (
            {
                "selection_status": "wrong_format_primary",
                "selected_paths": ["failed_to_generate.txt"],
            },
            "wrong_format",
        ),
    ],
)
def test_a_placeholder_does_not_override_a_selection_failure(item, expected):
    """Ordering is a decision, not an accident, so pin it.

    Neither combination occurs in either run -- every placeholder-carrying
    error in both the published corpus and the rerun is ``(ok, visual)``. That
    is exactly why it is worth a test: nothing in the data would catch it if
    the check moved above the status guards.
    """
    assert jeb.classify_error(item) == expected


@pytest.mark.parametrize(
    "item",
    [
        # A status the grader does not currently emit.
        {"selection_status": "quarantined"},
        # No status at all.
        {},
        # Selection fine, but a routing modality nobody has seen.
        {"selection_status": "ok", "routing_modality": "haptic"},
        # The subtle one: routed to a visual judge, something *was* rendered,
        # and it still failed. That is not a render-target miss, and calling
        # it one would credit `#189` with a fix it did not make.
        {
            "selection_status": "ok",
            "routing_modality": "visual",
            "visual_provenance": [{"page": 1}],
        },
    ],
)
def test_an_unknown_shape_is_reported_not_absorbed(item):
    """Unrecognised failures must surface, not join the nearest bucket.

    Absorbing them is how a regression gets published as an improvement: a new
    harness defect would land in ``model:`` and read as the model getting
    worse while we got better.
    """
    assert jeb.classify_error(item) == "unclassified"


def test_unclassified_items_fail_the_run_and_say_so(tmp_path, capsys):
    payload = _payload([_item(selection_status="quarantined")] * 2)
    path = _write(tmp_path, "grade.json", payload)

    assert jeb.main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "2 item(s) matched no known failure shape" in out
    assert "Do not read the split as complete" in out


# --------------------------------------------------------------------------
# the denominator
# --------------------------------------------------------------------------


def test_precheck_items_are_not_in_the_denominator():
    """Only judge-decided items count, on both sides of the fraction.

    A deterministic precheck can fail an item without a judge ever seeing it.
    Counting those would inflate the denominator and make every fix look
    smaller than it was.
    """
    items = [
        _item(selection_status="selection_error"),
        _item(verdict="pass"),
        _item(verdict="pass"),
        # Precheck-decided, including one that carries the same verdict string.
        _item(decided_by="precheck", selection_status="selection_error"),
        _item(decided_by="precheck", verdict="fail"),
    ]
    result = jeb.breakdown_payload(_payload(items), "L")

    assert (result.judge_items, result.errors) == (3, 1)
    assert result.rate == jeb.canonical_rate(1, 3)
    assert result.buckets["selector_ambiguous"] == 1


def test_a_payload_without_a_tasks_array_is_rejected():
    with pytest.raises(ValueError, match="no tasks array"):
        jeb.breakdown_payload({"summary": {}}, "L")
    with pytest.raises(ValueError, match="task that is not an object"):
        jeb.breakdown_payload({"tasks": ["t-1"]}, "L")


# --------------------------------------------------------------------------
# reading input
# --------------------------------------------------------------------------


def test_a_directory_reads_shards_in_order_then_finals(tmp_path):
    stem = tmp_path / "stem"
    for name in ("shard-002-of-003.json", "shard-000-of-003.json"):
        _write(stem, name, _payload([]))
    _write(stem, "shard-001-of-003.json", _payload([]))
    _write(stem, "final.json", _payload([]))

    assert [p.name for p in jeb.grade_files(stem)] == [
        "shard-000-of-003.json",
        "shard-001-of-003.json",
        "shard-002-of-003.json",
        "final.json",
    ]
    assert jeb.grade_files(stem / "final.json") == [stem / "final.json"]


def test_an_empty_or_missing_directory_is_an_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no grade files"):
        jeb.grade_files(empty)
    with pytest.raises(ValueError, match="not a grade file or directory"):
        jeb.grade_files(tmp_path / "nope")


def test_unreadable_input_exits_two_not_one(tmp_path, capsys):
    """A read failure and a gate failure must not share an exit code.

    Anything wiring this into CI has to be able to tell "the rate is too high"
    from "I could not read the run", because only one of those is a finding.
    """
    (tmp_path / "broken.json").write_text("{[", encoding="utf-8")
    assert jeb.main([str(tmp_path / "broken.json")]) == 2
    assert "error:" in capsys.readouterr().err

    assert jeb.main([str(tmp_path / "absent.json")]) == 2

    good = _write(tmp_path / "ok", "grade.json", _payload([]))
    assert jeb.main([str(good), "--baseline", str(tmp_path / "absent")]) == 2
    assert "error reading baseline:" in capsys.readouterr().err


def test_a_published_rate_that_disagrees_is_flagged(tmp_path, capsys):
    """If the file and the tool count differently, say so rather than pick one."""
    payload = _payload(
        [_item(selection_status="selection_error")] + [_item(verdict="pass")] * 9,
        published_rate=0.5,
    )
    path = _write(tmp_path, "grade.json", payload)

    jeb.main([str(path)])
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "publishes judge_error_rate=0.5 but recomputes to 0.1" in out


# --------------------------------------------------------------------------
# the gate and the pairing
# --------------------------------------------------------------------------


def _hundred_items(errors: int):
    return [_item(selection_status="selection_error")] * errors + [
        _item(verdict="pass")
    ] * (100 - errors)


def test_the_gate_passes_and_fails_on_the_threshold(tmp_path, capsys):
    path = _write(tmp_path, "grade.json", _payload(_hundred_items(3)))

    assert jeb.main([str(path), "--max-rate", "0.02"]) == 1
    assert "gate: 3.00% vs 2.00% -> OVER" in capsys.readouterr().out

    assert jeb.main([str(path), "--max-rate", "0.05"]) == 0
    assert "gate: 3.00% vs 5.00% -> OK" in capsys.readouterr().out

    # Exactly on the threshold passes; the gate is documented as "above this".
    assert jeb.main([str(path), "--max-rate", "0.03"]) == 0

    # And with no gate asked for, a high rate is reported, not enforced.
    assert jeb.main([str(path)]) == 0


def test_a_paired_comparison_keeps_the_three_causes_apart(tmp_path, capsys):
    """A fix should be read off the harness line, not the headline rate.

    The other two lines are what makes that reading safe. Here the harness
    errors go away while a judge flake and a model failure stay exactly where
    they were, so the rate move is attributable to the fix and to nothing
    else. Collapsing judge-side into the model line -- which this tool did
    until the rerun showed ``final_json_parse_failed`` sitting in it -- would
    report grading flakiness as a finding about the submissions.
    """
    old = _write(
        tmp_path / "old",
        "grade.json",
        _payload(
            [_item(selection_status="selection_error")] * 6
            + [_item(selection_status="wrong_format_primary")] * 2
            + [_item(selection_status="ok", routing_modality="text")] * 1
            + [_item(verdict="pass")] * 91
        ),
    )
    # Same denominator, harness errors fixed, the other two untouched.
    new = _write(
        tmp_path / "new",
        "grade.json",
        _payload(
            [_item(selection_status="wrong_format_primary")] * 2
            + [_item(selection_status="ok", routing_modality="text")] * 1
            + [_item(verdict="pass")] * 97
        ),
    )

    assert jeb.main([str(new), "--baseline", str(old)]) == 0
    out = capsys.readouterr().out
    assert "harness-caused          6 ->       0" in out
    assert "judge-side              1 ->       1" in out
    assert "model-caused            2 ->       2" in out
    assert "rate                9.00% ->   3.00%" in out
    assert "NOTE" not in out


def test_a_denominator_change_is_called_out_in_the_pairing(tmp_path, capsys):
    """Same tasks, different item counts, means the rubric moved.

    Pairing on task id removes the "different tasks" explanation for a
    denominator gap, so what is left is a real one: the rubric under which
    those tasks were judged is not the same. A rate change then is not only
    about judge errors, and the reader has to be told.
    """
    old = _write(tmp_path / "old", "grade.json", _payload(_hundred_items(3)))
    new = _write(
        tmp_path / "new",
        "grade.json",
        _payload([_item(selection_status="selection_error")] + [_item(verdict="pass")] * 9),
    )

    jeb.main([str(new), "--baseline", str(old)])
    out = capsys.readouterr().out
    assert "NOTE: the denominators differ (100 vs 10)" in out
    assert "the rubric itself moved" in out


def test_a_partial_run_is_paired_only_on_what_it_has_published(tmp_path, capsys):
    """The case this exists for: reading a shard while the run is in flight.

    The baseline holds every task; the new run has finished two of them.
    Comparing the totals would measure how far along it is, not whether it is
    better. Both sides are cut to the tasks they share before anything is
    counted.
    """
    baseline = _write(
        tmp_path / "old",
        "grade.json",
        _payload(
            # 10 items per task; the two shared tasks carry one harness error
            # each, the three the new run has not reached carry three more.
            [_item(selection_status="selection_error")] * 5
            + [_item(verdict="pass")] * 45,
            task_count=5,
        ),
    )
    # Same two tasks, now clean.
    new = _write(
        tmp_path / "new", "grade.json", _payload([_item(verdict="pass")] * 20, task_count=2)
    )

    assert jeb.main([str(new), "--baseline", str(baseline)]) == 0
    out = capsys.readouterr().out
    assert "paired on the 2 task(s) both runs have published" in out
    assert "Set aside: 0 here, 3 in the baseline" in out
    assert "will not match either run's own published totals" in out
    # 2 of the 5 tasks, so 20 of the 50 items -- not the baseline's own 50.
    assert "tasks in both           2" in out
    assert "judged items           20 ->      20" in out
    assert "judge errors            2 ->       0" in out


def test_two_runs_with_no_shared_tasks_refuse_to_compare(tmp_path, capsys):
    """An empty intersection is a mistake, not a 0.00% -> 0.00% result."""
    old = _write(
        tmp_path / "old", "grade.json", _payload(_hundred_items(3), task_prefix="old")
    )
    new = _write(
        tmp_path / "new", "grade.json", _payload(_hundred_items(0), task_prefix="new")
    )

    assert jeb.main([str(new), "--baseline", str(old)]) == 2
    err = capsys.readouterr().err
    assert "share no task ids" in err
    assert "same corpus" in err


def test_restricting_drops_the_published_rate():
    """A file's published rate belongs to all of its tasks, not to a subset."""
    payload = _payload(
        [_item(selection_status="selection_error")] + [_item(verdict="pass")] * 9,
        published_rate=0.1,
        task_count=2,
    )
    whole = jeb.breakdown_payload(payload, "L")
    assert whole.published_rate == 0.1

    part = whole.restrict({"t-0"})
    assert part.published_rate is None
    assert part.tasks == 1


def test_a_task_counted_twice_is_refused_not_summed(tmp_path):
    """Reading the shards and their merged final would double every number.

    Shard slices are disjoint by construction, so an id appearing twice means
    either the slicing broke or someone pointed this at a directory holding
    both halves of the same data. Summing them silently would report every
    figure at twice its true value, and the totals would still look plausible.
    """
    with pytest.raises(ValueError, match="more than once"):
        jeb.breakdown_payload(
            {"tasks": [{"task_id": "t-0", "items": []}] * 2}, "L"
        )

    stem = tmp_path / "stem"
    _write(stem, "shard-000-of-001.json", _payload([_item(verdict="pass")]))
    _write(stem, "final.json", _payload([_item(verdict="pass")]))
    with pytest.raises(ValueError, match="repeats 1 task"):
        jeb.total_of(jeb.read_breakdowns([stem]))


def test_a_task_without_an_id_is_read_but_cannot_pair():
    """Legacy files predate ``task_id``; refusing to read them helps nobody."""
    payload = {"tasks": [{"items": [_item(selection_status="selection_error")]}] * 2}
    result = jeb.breakdown_payload(payload, "legacy.json")

    assert (result.tasks, result.errors) == (2, 2)
    assert sorted(result.per_task) == ["legacy.json#0", "legacy.json#1"]
    assert result.restrict({"t-0"}).tasks == 0


# --------------------------------------------------------------------------
# independence from the grading stack
# --------------------------------------------------------------------------


def test_the_tool_imports_without_the_grading_stack():
    """The breakdown must run wherever a grade file can be copied to.

    Same guarantee the relay sweep has, for the same reason: reading how a
    paid run went should not require the stack that ran it -- azure, openai
    and jsonschema, none of which a laptop or a minimal runner will have.

    Parsed rather than prefix-matched, because this module's own docstring
    contains a line beginning "from two unlike places:" and a string check
    would call that an import.
    """
    tree = ast.parse(Path(jeb.__file__).read_text(encoding="utf-8"))

    imported = []
    for node in tree.body:  # module scope only
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    forbidden = ("step8_grade", "step9_merge_shards", "core", "jsonschema")
    offenders = [
        name
        for name in imported
        if name.split(".")[0] in forbidden
    ]
    assert offenders == [], (
        f"the breakdown must not import the grading stack: {offenders}"
    )
