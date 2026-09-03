"""Tests for pricing the required-item definition.

What is being priced and why it needs a test at all: GDPVal rubrics never say
which items are required -- ``required`` is null on all 10,453 of them -- so the
repository decided that weight stands in for necessity, at
``abs(max_score) >= 4``. Two published numbers rest on that choice and the
comment above it has always said 4 was a heuristic. The card that asks for a
real definition lists three options, and the only thing missing before anyone
can choose between them is what each one would do to the runs already
published.

The load-bearing tests here are the ones that stop this measuring the wrong
thing:

* ``test_the_sweep_reprices_through_the_production_summariser`` proves the
  threshold really is being changed underneath ``step8_grade._compute_summary``
  rather than inside a private copy of the rate. If that stopped being true
  every number this script prints would be about a function nobody publishes.
* ``test_the_recount_reproduces_the_published_critical_fail_booleans`` checks
  the same thing for the other published consequence, against two real runs.
  At the shipped threshold the recount has to land on the flags the grader
  itself wrote -- 13 of 30 and 99 of 185 -- or the sweep's other rows are
  measuring some rule of this file's own.
* ``test_raising_the_threshold_to_five_moves_the_gold_rate_away_from_the_gate``
  is the finding. The card's first option is priced against the very run whose
  figure the card quotes, and it moves that figure in the wrong direction.

The refusals are tested as carefully as the measurements, because a priced
option is only worth as much as the payload it was priced against, and two of
the published payloads cannot support one.
"""

import json
import subprocess
from pathlib import Path

import pytest

import core.grader as grader_module
from scripts import analyze_required_item_definition as arid
from scripts.analyze_gold_ceiling import CRITICAL_ITEM_PASS_FLOOR


REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTIC = REPO_ROOT / "data" / "grades" / "_diagnostic"
TOOL_PATH = Path("batch-runner/scripts/analyze_required_item_definition.py")
REPORT_PATH = REPO_ROOT / "data" / "grades" / "_validation" / "REQUIRED_ITEM_DEFINITION.md"

#: The two gold-ceiling corpora, keyed by the ordered-id digest that names
#: their directory. Stage 1 is the run the card quotes 0.5714 from.
GOLD_30 = "82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b"
GOLD_185 = "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"


def _load_gold(digest: str) -> tuple[Path, dict]:
    directory = DIAGNOSTIC / digest
    if not directory.is_dir():
        pytest.skip(f"gold corpus {digest[:8]} not present")
    candidates = sorted(directory.glob("exp_gold_baseline__*.json"))
    if not candidates:
        pytest.skip(f"gold corpus {digest[:8]} has no payload")
    path = candidates[0]
    return path, json.loads(path.read_text(encoding="utf-8"))


# ── synthetic payloads ───────────────────────────────────────────────


def _item(
    criterion: str,
    max_score: float,
    *,
    did_right: bool = True,
    excluded: bool = False,
) -> dict:
    return {
        "id": criterion[:8],
        "criterion": criterion,
        "max_score": max_score,
        "verdict": "pass" if did_right else "fail",
        "decided_by": "judge",
        "model_did_right": did_right,
        "score_excluded": excluded,
    }


def _task(task_id: str, items: list[dict], *, sector: str = "test") -> dict:
    scored = [i for i in items if not i["score_excluded"]]
    awarded = sum(i["max_score"] for i in scored if i["model_did_right"])
    total = sum(max(0.0, i["max_score"]) for i in scored)
    return {
        "task_id": task_id,
        "sector": sector,
        "occupation": "test",
        "items": items,
        "total_awarded": awarded,
        "total_max": total,
        "pct": round((awarded / total * 100.0) if total else 0.0, 2),
        "critical_fail": any(
            abs(i["max_score"]) >= grader_module.MAGNITUDE_THRESHOLD
            and not i["model_did_right"]
            for i in scored
        ),
        "usage_complete": True,
    }


def _payload(tasks: list[dict], *, published_rate: float | None = None) -> dict:
    """A payload whose stored rate is whatever today's summariser computes.

    Tests that want a payload which does *not* reproduce pass an explicit
    ``published_rate``.
    """
    from step8_grade import _compute_summary

    summary = _compute_summary(tasks)
    if published_rate is not None:
        summary["wow"]["critical_item_pass_rate"] = published_rate
    return {"tasks": tasks, "summary": summary}


def _price(payload: dict, *, floor: float = 0.10) -> arid.Priced:
    priced = arid.price(Path("synthetic.json"), payload, repeat_floor=floor)
    assert priced is not None
    return priced


# ── the mechanism: production code, not a copy of it ─────────────────


def test_the_sweep_reprices_through_the_production_summariser():
    """The whole design rests on this.

    ``step8_grade`` imported ``_is_critical_item`` -- the function -- and that
    function reads ``MAGNITUDE_THRESHOLD`` from ``core.grader`` when it is
    called. So rebinding the module global changes what the real summariser
    counts. If someone later froze the threshold into a default argument or a
    module constant in ``step8_grade``, this test fails and the sweep stops
    being a measurement of the shipped metric.
    """
    from step8_grade import _compute_summary

    tasks = [
        _task("t1", [_item("worth four", 4, did_right=False)]),
        _task("t2", [_item("worth five", 5, did_right=True)]),
    ]

    with arid._threshold(4):
        at_four = _compute_summary(tasks)["wow"]["critical_item_pass_rate"]
    with arid._threshold(5):
        at_five = _compute_summary(tasks)["wow"]["critical_item_pass_rate"]

    assert at_four == 0.5  # both items counted, one right
    assert at_five == 1.0  # the four-point failure drops out


def test_the_threshold_is_put_back_even_when_the_body_raises():
    """A leaked threshold would silently mis-grade everything downstream."""
    original = grader_module.MAGNITUDE_THRESHOLD

    with pytest.raises(RuntimeError):
        with arid._threshold(99):
            assert grader_module.MAGNITUDE_THRESHOLD == 99
            raise RuntimeError("boom")

    assert grader_module.MAGNITUDE_THRESHOLD == original


def test_the_shipped_threshold_is_read_not_restated():
    assert arid.SHIPPED_THRESHOLD == grader_module.MAGNITUDE_THRESHOLD
    assert arid.SHIPPED_THRESHOLD in arid.THRESHOLD_SWEEP


# ── the usable-denominator floor is derived, not chosen ──────────────


def test_the_denominator_floor_comes_from_the_gate_it_serves():
    """20 items, because one miss out of 20 is exactly the gate's margin.

    Below that, a single failure costs more than the whole distance between
    the floor and a clean sweep, so the metric cannot express any value in
    between and a rate read off it is not a measurement of anything.
    """
    assert CRITICAL_ITEM_PASS_FLOOR == 0.95
    assert arid.MIN_USABLE_CRITICAL_ITEMS == 20
    assert 1.0 / arid.MIN_USABLE_CRITICAL_ITEMS <= 1.0 - CRITICAL_ITEM_PASS_FLOOR


def test_a_rate_read_off_one_item_is_refused_as_a_basis():
    """The real shape of the trap, from the stage-1 corpus.

    At threshold 6 stage 1 keeps a single critical item, the model got it
    right, and the metric reads a perfect 1.0000 -- over the 0.95 gate, on a
    denominator of one out of 1,431 scored items.
    """
    tasks = [_task("t1", [_item("the only big one", 6, did_right=True)])]
    priced = _price(_payload(tasks))

    effect = priced.effect_at(6)
    assert effect is not None
    assert effect.critical_items == 1
    assert effect.pass_rate == 1.0
    assert effect.usable is False
    assert "[denominator too thin to use]" in arid.render([priced])


def test_a_denominator_that_can_carry_the_gate_is_not_flagged():
    tasks = [
        _task(
            f"t{n}",
            [_item(f"criterion {n}-{k}", 4, did_right=True) for k in range(5)],
        )
        for n in range(5)
    ]
    priced = _price(_payload(tasks))

    effect = priced.effect_at(4)
    assert effect is not None
    assert effect.critical_items == 25
    assert effect.usable is True


# ── refusals ─────────────────────────────────────────────────────────


def test_a_payload_without_sign_aware_verdicts_is_refused():
    """Pre-#100 payloads published a rate this cannot reconstruct.

    ``model_did_right`` is what the metric counts. Without it every item reads
    as "the model got this wrong", so a sweep over such a payload would price
    the options against a corpus of total failure that never happened.
    """
    tasks = [_task("t1", [_item("big", 5, did_right=True)])]
    for item in tasks[0]["items"]:
        del item["model_did_right"]
    payload = _payload(tasks)

    priced = _price(payload)

    assert priced.priced is False
    assert "model_did_right" in (priced.refusal or "")
    assert "summary_wow_drift" in (priced.refusal or "")
    assert priced.effects == []


def test_a_payload_that_does_not_reproduce_is_refused():
    """A stored rate the current summariser does not land on came from a rule
    that is no longer running, so pricing a change against it would compare two
    definitions while reporting one."""
    tasks = [_task("t1", [_item("big", 5, did_right=True)])]

    priced = _price(_payload(tasks, published_rate=0.1234))

    assert priced.priced is False
    assert "does not reproduce" in (priced.refusal or "")
    assert priced.published_rate == 0.1234
    assert priced.recomputed_rate == 1.0


def test_a_refused_payload_makes_the_run_exit_nonzero(tmp_path, capsys):
    tasks = [_task("t1", [_item("big", 5, did_right=True)])]
    (tmp_path / "bad.json").write_text(
        json.dumps(_payload(tasks, published_rate=0.1234)), encoding="utf-8"
    )

    assert arid.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "1 refused" in out
    assert "Do not read a number for it off another payload's table." in out


def test_a_payload_with_no_such_metric_is_skipped_not_refused(tmp_path, capsys):
    """Not every JSON under data/grades is a graded run."""
    (tmp_path / "other.json").write_text(
        json.dumps({"tasks": [], "summary": {}}), encoding="utf-8"
    )

    assert arid.main([str(tmp_path)]) == 0
    assert "no grade payloads" in capsys.readouterr().out


# ── the census: derived from the corpus, never hardcoded ─────────────


def test_the_census_finds_a_repeated_line_it_was_never_told_about():
    """Nothing in the script knows what the repeated criterion says.

    The real corpus repeats one line about formatting; this invents a
    different one, so a hardcoded string would find nothing here.
    """
    tasks = [
        _task(
            f"t{n}",
            [
                _item("Widget torque is within tolerance", 5, did_right=False),
                _item(f"unique to task {n}", 4, did_right=True),
            ],
        )
        for n in range(10)
    ]
    priced = _price(_payload(tasks))

    assert [r.criterion for r in priced.repeated] == [
        "Widget torque is within tolerance"
    ]
    repeat = priced.repeated[0]
    assert (repeat.items, repeat.tasks, repeat.pass_rate) == (10, 10, 0.0)
    assert repeat.share_of(20) == 0.5


def test_spellings_of_one_line_are_counted_as_one_line():
    """Stage 3 carries the style line 119 times bare and once with a full stop.

    Counting those as two lines would halve the share this measures and hide
    the concentration it exists to find.
    """
    tasks = [
        _task("t1", [_item("Overall formatting and style", 5)]),
        _task("t2", [_item("Overall formatting and style.", 5)]),
        _task("t3", [_item("overall  formatting and STYLE ", 5)]),
    ]
    priced = _price(_payload(tasks))

    assert len(priced.repeated) == 1
    repeat = priced.repeated[0]
    assert repeat.items == 3
    assert repeat.variants == 3
    # The most common spelling is quoted, so the report shows the rubric's
    # words rather than this file's folded key.
    assert repeat.criterion in {
        "Overall formatting and style",
        "Overall formatting and style.",
        "overall  formatting and STYLE",
    }
    assert repeat.criterion != repeat.criterion.lower().rstrip(".")


def test_a_line_that_appears_once_is_not_repeated_however_small_the_corpus():
    """On a three-task smoke one occurrence is a third of the corpus.

    A share floor on its own would report every criterion in such a run as
    repeated boilerplate, which is the opposite of what this measures.
    """
    tasks = [_task(f"t{n}", [_item(f"unique {n}", 5)]) for n in range(3)]

    assert _price(_payload(tasks), floor=0.10).repeated == []


def test_a_line_below_the_floor_is_not_reported_as_repeated():
    tasks = [_task(f"t{n}", [_item("rare line", 5)]) for n in range(2)]
    tasks += [_task(f"u{n}", [_item(f"unique {n}", 5)]) for n in range(38)]

    assert _price(_payload(tasks), floor=0.10).repeated == []
    assert [r.criterion for r in _price(_payload(tasks), floor=0.05).repeated] == [
        "rare line"
    ]


def test_excluded_items_are_outside_both_the_census_and_the_rates():
    """The published metric is defined over scored items only."""
    tasks = [
        _task(
            "t1",
            [
                _item("counted", 5, did_right=True),
                _item("never scored", 5, did_right=False, excluded=True),
            ],
        )
    ]
    priced = _price(_payload(tasks))

    effect = priced.effect_at(4)
    assert effect is not None
    assert effect.critical_items == 1
    assert effect.pass_rate == 1.0
    assert effect.critical_fail_tasks == 0


# ── the text-rule option ─────────────────────────────────────────────


def test_the_text_rule_option_uses_the_predicate_the_grader_already_ships():
    """Priced against something real rather than a rule invented here.

    ``core.grader_routing.is_overall_style_criterion`` is what the grader uses
    to decide a criterion is asking about deliverable-wide polish rather than
    about the work, and it is already covered by the routing tests.
    """
    tasks = [
        _task(
            "t1",
            [
                _item("Overall formatting and style of the deliverable", 5, did_right=False),
                _item("The totals reconcile to the ledger", 5, did_right=True),
            ],
        )
    ]
    priced = _price(_payload(tasks))

    assert (priced.text_rule_items, priced.text_rule_rate) == (1, 0.0)
    assert (priced.remainder_items, priced.remainder_rate) == (1, 1.0)


def test_two_tasks_carrying_the_same_line_both_stay_in_their_partition():
    """Rubric items are plain dicts and ``in`` compares them by value.

    Splitting the critical set with a membership test dropped every copy of
    every repeated line from the remainder -- which is exactly the set being
    measured. Four items here, two identical pairs, and both partitions must
    keep both of theirs.
    """
    line = "Overall formatting and style of the deliverable"
    other = "The totals reconcile to the ledger"
    tasks = [
        _task("t1", [_item(line, 5, did_right=True), _item(other, 5, did_right=True)]),
        _task("t2", [_item(line, 5, did_right=True), _item(other, 5, did_right=True)]),
    ]
    priced = _price(_payload(tasks))

    assert priced.text_rule_items == 2
    assert priced.remainder_items == 2


# ── against the runs that were actually published ────────────────────


@pytest.mark.parametrize(
    "digest,tasks,rate,stored_fails",
    [(GOLD_30, 30, 0.5714, 13), (GOLD_185, 185, 0.6394, 99)],
)
def test_the_recount_reproduces_the_published_critical_fail_booleans(
    digest, tasks, rate, stored_fails
):
    """Both published consequences, checked against the grader's own output.

    The rate comes back through the production summariser; the booleans are
    recounted here, so this is where that recount is held to the flags
    ``core.grader._aggregate`` actually wrote into the payload.
    """
    path, payload = _load_gold(digest)
    priced = arid.price(path, payload, repeat_floor=0.10)
    assert priced is not None and priced.priced, priced.refusal if priced else None

    assert priced.task_count == tasks
    assert priced.published_rate == priced.recomputed_rate == rate

    stored = sum(1 for task in payload["tasks"] if task.get("critical_fail"))
    assert stored == stored_fails
    shipped = priced.effect_at(arid.SHIPPED_THRESHOLD)
    assert shipped is not None
    assert shipped.critical_fail_tasks == stored


def test_raising_the_threshold_to_five_moves_the_gold_rate_away_from_the_gate():
    """The card's first option, priced against the run the card quotes.

    Stage 1's 0.5714 has to reach 0.95. Raising the boundary to 5 takes it to
    0.5312, because the line that dominates the critical set is worth exactly
    5: a threshold of 5 keeps every one of them and drops the real must-haves
    worth 4. Stage 3 moves the same way, 0.6394 to 0.6325.
    """
    for digest, at_four, at_five in ((GOLD_30, 0.5714, 0.5312), (GOLD_185, 0.6394, 0.6325)):
        path, payload = _load_gold(digest)
        priced = arid.price(path, payload, repeat_floor=0.10)
        assert priced is not None and priced.priced

        four, five = priced.effect_at(4), priced.effect_at(5)
        assert four is not None and five is not None
        assert (four.pass_rate, five.pass_rate) == (at_four, at_five)
        assert five.pass_rate < four.pass_rate < CRITICAL_ITEM_PASS_FLOOR


def test_one_repeated_line_is_most_of_what_the_gold_metric_measures():
    """Why the definition is worth reopening at all.

    A single verbatim rubric line, worth 5 and present in roughly two thirds of
    tasks, is 54.3% of stage 1's critical set and 33.8% of stage 3's, and the
    expert gold answers pass it at about a third the rate of everything else.
    """
    for digest, items, share_tasks, styled_rate, rest_rate in (
        (GOLD_30, 19, 19, 0.4211, 0.7500),
        (GOLD_185, 120, 120, 0.3000, 0.8128),
    ):
        path, payload = _load_gold(digest)
        priced = arid.price(path, payload, repeat_floor=0.10)
        assert priced is not None and priced.priced

        assert priced.text_rule_items == items
        assert priced.text_rule_tasks == share_tasks
        assert priced.text_rule_rate == styled_rate
        assert priced.remainder_rate == rest_rate
        # Even with that line removed the gold answers stay under the gate, so
        # this is a finding about the rubric or the judge, not a way to pass.
        assert rest_rate < CRITICAL_ITEM_PASS_FLOOR


def test_withdrawing_the_metric_is_priced_in_published_numbers():
    """The second option's cost is countable: what would stop being published."""
    path, payload = _load_gold(GOLD_30)
    priced = arid.price(path, payload, repeat_floor=0.10)
    assert priced is not None and priced.priced

    assert priced.sector_rates == len(payload["summary"]["wow"]["by_sector"])
    assert priced.graded_tasks == 30
    assert "1 run rate, 4 sector rate(s) and 30 task boolean(s)" in arid.render(
        [priced]
    )


# ── the report can actually be reproduced from a fresh clone ─────────


def test_the_tool_is_tracked_where_the_report_says_it_is():
    """``batch-runner/scripts/`` is gitignored with per-file exceptions, so a
    tool can work locally and be absent from a fresh clone.

    That matters more here than usual: the report is a set of numbers about
    published grades, and the only thing standing behind them is the command
    that recomputes them. An untracked tool turns "reproducing this" into an
    instruction nobody else can follow.

    Probed without ``--verbose`` on purpose. With it, git reports the last
    matching pattern *including negations* and exits 0 either way, so a
    verbose probe cannot tell "ignored" from "un-ignored by a later rule".
    Without it the exit code is the answer: 1 means no pattern ignores this.
    """
    assert (REPO_ROOT / TOOL_PATH).is_file()

    finished = subprocess.run(
        ["git", "check-ignore", str(TOOL_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.returncode == 1, (
        f"{TOOL_PATH} is ignored, so the command in the report cannot run "
        f"from a fresh clone"
    )


def test_the_report_names_the_tool_it_was_produced_by():
    """A measured claim that does not say what measured it is not checkable."""
    assert REPORT_PATH.is_file()
    text = REPORT_PATH.read_text(encoding="utf-8")

    assert TOOL_PATH.name in text
    assert "MAGNITUDE_THRESHOLD" in text
