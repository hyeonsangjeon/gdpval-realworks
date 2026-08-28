"""A total called the maximum may not contain a part called uncapped.

The advance check prints a heading that calls its total the largest possible
bill, and under that heading it printed this, about the marking half:

    ... So one call can carry 535589 tokens, and that is still a floor: the
    scoring line being judged is not capped by anything.

Both of those cannot be true in the same report. If one part of a sum has no
upper bound then the sum has no maximum either, so either the heading was wrong
or the sentence was. The sentence was.

Every marking call carries the scoring line it is judging. That wording lives in
the ``rubric_json`` column of the dataset file the check already pins to all
sixty-four characters of its fingerprint, at a revision it also pins. Nothing
between the file and the judge shortens it. So the widest scoring line in the
benchmark is a fixed, readable number — 1,203 characters, in task
``0353ee0c-18b5-4ad3-88e8-e001d223e1d7``, across 10,453 scoring lines — and what
it was, all along, was *not capped by a setting*. That is a different thing from
not being bounded, and the report printed the first as though it were the
second.

The width is now measured when the catalogue is built, carried per task, and
demanded by the check. What that module and this one guard are two different
claims:

* :mod:`tests.test_marking_cost_counts_the_conversation_opening` pins the
  arithmetic — that the opening is those three pieces and that dropping any one
  of them lowers the demand.
* This module pins the honesty of the *report*, and pins that the width is a
  measurement rather than a number somebody typed. Those are the two ways this
  defect comes back: the sentence gets re-written, or the number gets copied.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

import dataclasses
import io
import tokenize
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from core.execution_envelope_grading_cost import (
    GradingCaps,
    check_assumptions_cover_the_caps,
    describe_grading_caps,
    read_grading_caps,
)
from core.execution_envelope_cost import CostAssumptions
from core.execution_envelope_preflight import (
    describe_preflight,
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import (
    catalog_number_problems,
    load_task_catalog,
    widest_scoring_line_characters,
)

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
COMMITTED_MARKING_SETTINGS = (
    BATCH_RUNNER_ROOT / "grading_configs" / "default_v2.yaml"
)

#: Wording that says some part of the bill has no top. None of it may appear
#: anywhere in a report whose heading calls its total the largest possible bill.
#: Written as whole phrases rather than single words so that a line saying the
#: figure *is* a ceiling does not trip its own guard.
SAYS_THERE_IS_NO_TOP = (
    "is not capped by anything",
    "not capped by anything",
    "still a floor",
    "is a floor",
    "uncapped",
    "unbounded",
    "no upper bound",
)

#: The production files this defect could hide in. The catalogue JSON is not
#: here on purpose: it is where the measurement is *supposed* to live.
PRODUCTION_SOURCE = (
    sorted((BATCH_RUNNER_ROOT / "core").rglob("*.py"))
    + sorted((BATCH_RUNNER_ROOT / "scripts").glob("*.py"))
)


# ── Helpers ───────────────────────────────────────────────────────────────


def the_catalog():
    """The committed catalogue, read the way the real check reads it."""
    return load_task_catalog()


def caps(**overrides) -> GradingCaps:
    """The committed marking settings, plus the width they cannot hold."""
    base = read_grading_caps(
        COMMITTED_MARKING_SETTINGS,
        widest_scoring_line_characters=widest_scoring_line_characters(
            the_catalog()
        ),
    )
    return replace(base, **overrides)


def assumptions(**overrides) -> CostAssumptions:
    """A cost sum whose marking numbers meet every limit but the one asked."""
    settled = caps()
    stated = {
        "characters_per_token": "3.0",
        "instruction_character_count": 100,
        "tool_loop_max_model_turns": {"host_python_process": 1},
        "output_tokens_capped_per_attempt": {"host_python_process": False},
        "max_tool_result_tokens_per_turn": {"host_python_process": 0},
        "safety_multiplier": "1.25",
        "grading_required": True,
        "grading_model": settled.judge_model,
        "grading_calls_per_rubric_item": settled.judge_calls_per_rubric_item,
        "grading_input_tokens_per_call": (
            settled.input_tokens_one_call_must_cover(Decimal("3.0"))
        ),
        "grading_output_tokens_per_call": settled.output_tokens_per_call,
    }
    stated.update(overrides)
    return CostAssumptions.from_mapping(stated)


def every_line_of_the_report() -> list[str]:
    """The whole advance check, as a person reading it would see it."""
    result = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)
    return (
        list(describe_preflight(result))
        + list(result.cost_findings)
        + list(result.problems)
    )


# ── The report may not contradict its own heading ─────────────────────────


def test_the_report_says_nowhere_that_a_part_of_the_bill_has_no_top():
    """The defect itself, tested where it was actually printed.

    ``describe_grading_caps`` has no production caller, so the sentence a
    person really read was the refusal in the problem list. This runs the whole
    advance check against the committed plan and reads every line of it —
    summary and problems together — because that is the artefact somebody is
    asked to approve a bill against.

    The container half's still-open instance is exempt by the same list the
    source sweep uses. It does not fire on today's committed plan, which is
    exactly why it is exempted by name rather than by luck.
    """
    report = every_line_of_the_report()

    offending = [
        line
        for line in report
        for phrase in SAYS_THERE_IS_NO_TOP
        if phrase in line.lower()
        and not any(wording in line for _, wording in STILL_OPEN_ELSEWHERE)
    ]
    assert offending == [], (
        "a report headed the largest possible bill said one of its parts has "
        f"no top: {offending}"
    )


def test_the_report_still_claims_a_largest_possible_bill():
    """The other half of the contradiction, so it cannot be fixed by retreat.

    Deleting the heading would also make the two sentences agree, and it would
    be the wrong repair: the check exists to produce a ceiling. The claim has
    to survive, with the sentence that denied it gone.
    """
    report = every_line_of_the_report()
    joined = " | ".join(report)

    assert "after multiplying by" in joined
    assert "United States dollars" in joined
    assert any(
        "not a ceiling" in line and "marking figure" in line for line in report
    ), "the report must still say plainly which half is not yet a ceiling"


def test_the_marking_refusal_accounts_for_the_scoring_line_it_carries():
    """The figure demanded includes the width, and says where it came from."""
    widest = widest_scoring_line_characters(the_catalog())
    report = every_line_of_the_report()

    matching = [
        line for line in report if "tokens of input per marking call" in line
    ]
    assert len(matching) == 1
    assert f"{widest} characters of the widest scoring line" in matching[0]
    assert "So one call can carry" in matching[0]


# ── The width is measured, not typed ──────────────────────────────────────


def test_the_measured_width_is_not_typed_into_any_production_file():
    """One source. A second copy is how the last four defects each began.

    Tokenised rather than searched as text, so that prose saying the widest
    line runs to 1,203 characters — which is true, and worth writing down — is
    not mistaken for a constant somebody can edit out of step with the
    dataset.
    """
    widest = widest_scoring_line_characters(the_catalog())
    typed: list[str] = []

    for path in PRODUCTION_SOURCE:
        source = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type != tokenize.NUMBER:
                continue
            try:
                value = int(token.string.replace("_", ""))
            except ValueError:
                continue
            if value == widest:
                typed.append(
                    f"{path.relative_to(BATCH_RUNNER_ROOT)}:{token.start[0]}"
                )

    assert typed == [], (
        f"the widest scoring line ({widest}) is typed into production source "
        f"at {typed}; it must be read from the task catalogue"
    )


def test_lowering_the_widest_task_lowers_what_the_check_demands():
    """Proof the chain is live from the dataset column to the demand.

    A width that was typed once and never read again would keep this figure
    steady while the catalogue moved underneath it, which is precisely the
    failure that under-charges.
    """
    catalog = the_catalog()
    widest = widest_scoring_line_characters(catalog)
    widest_task = max(
        catalog.tasks, key=lambda task: task.widest_rubric_criterion_characters
    )

    shortened = replace(
        catalog,
        tasks=tuple(
            replace(task, widest_rubric_criterion_characters=widest - 300)
            if task.task_id == widest_task.task_id
            else task
            for task in catalog.tasks
        ),
    )

    before = caps().input_tokens_one_call_must_cover(Decimal("3.0"))
    after = caps(
        characters_of_widest_scoring_line=widest_scoring_line_characters(
            shortened
        )
    ).input_tokens_one_call_must_cover(Decimal("3.0"))

    assert widest_scoring_line_characters(shortened) < widest
    assert before > after


def test_the_width_is_taken_across_every_task_and_not_the_first_one():
    """The widest line in the benchmark, not the widest in some sample."""
    catalog = the_catalog()
    widths = [
        task.widest_rubric_criterion_characters for task in catalog.tasks
    ]

    assert len(widths) == 220
    assert min(widths) > 0, "no scoring line in this benchmark is blank"
    assert widest_scoring_line_characters(catalog) == max(widths)
    assert max(widths) > widths[0], (
        "if the widest task happened to be first, this test would pass while "
        "reading only one task; pick a different assertion"
    )


# ── Every task, one at a time: a blank width is refused ────────────────────


@pytest.mark.parametrize("index", range(220))
def test_blanking_any_single_task_width_is_refused(index):
    """The sweep. 220 catalogues, each with exactly one width emptied.

    A rule that only catches a column that arrived empty everywhere would miss
    the row that arrived empty on its own, and one task marked for a fraction
    of what it costs is the same kind of understatement as all of them.
    """
    catalog = the_catalog()
    tasks = list(catalog.tasks)
    blanked = tasks[index]
    tasks[index] = replace(blanked, widest_rubric_criterion_characters=0)

    problems = catalog_number_problems(replace(catalog, tasks=tuple(tasks)))
    matching = [p for p in problems if "longest scoring line" in p]

    assert len(matching) == 1
    assert blanked.task_id in matching[0]
    assert "price that wording at nothing" in matching[0]


def test_the_committed_catalogue_itself_is_refused_by_nothing():
    """The other side of the sweep: no false alarm on the real catalogue."""
    assert [
        problem
        for problem in catalog_number_problems(the_catalog())
        if "longest scoring line" in problem
    ] == []


# ── Fail closed: a width nobody measured is not a small width ─────────────


@pytest.mark.parametrize("not_a_measurement", [None, 0, -1, -1203])
def test_the_opening_cannot_be_worked_out_without_a_real_width(
    not_a_measurement,
):
    """Refuse, rather than quietly leaving the scoring line out of the sum."""
    with pytest.raises(ValueError) as raised:
        caps(
            characters_of_widest_scoring_line=not_a_measurement
        ).input_tokens_the_conversation_opens_with(Decimal("3.0"))

    assert "scoring line" in str(raised.value)


@pytest.mark.parametrize("not_a_measurement", [None, 0, -1, -1203])
def test_the_check_refuses_rather_than_passing_a_plan_it_did_not_check(
    not_a_measurement,
):
    """A plan must not clear this rule because the rule could not run.

    Without the guard the sum would be compared against an opening with a piece
    missing, and a plan sitting just under the real figure would be waved
    through. The refusal has to name what is missing and where it is kept.
    """
    problems = check_assumptions_cover_the_caps(
        assumptions(),
        caps(characters_of_widest_scoring_line=not_a_measurement),
    )
    matching = [p for p in problems if "scoring line" in p]

    assert len(matching) == 1
    assert "task catalogue" in matching[0]
    assert "does not make it free" in matching[0]


@pytest.mark.parametrize("not_a_measurement", [None, 0, -1])
def test_the_description_warns_instead_of_quoting_a_figure_it_cannot_stand_by(
    not_a_measurement,
):
    """What a person reads must not look complete when it is not."""
    lines = describe_grading_caps(
        caps(characters_of_widest_scoring_line=not_a_measurement)
    )
    warnings = [line for line in lines if line.startswith("WARNING:")]

    assert len(warnings) == 1
    assert "scoring line" in warnings[0]
    assert "below what one call carries" in warnings[0]
    assert not any("a ceiling rather than a floor" in line for line in lines)


def test_a_measured_width_turns_the_warning_into_a_ceiling():
    """The same description, once the measurement is there."""
    lines = describe_grading_caps(caps())

    assert [line for line in lines if line.startswith("WARNING:")] == []
    assert any("a ceiling rather than a floor" in line for line in lines)


def test_the_real_check_hands_the_catalogue_down_rather_than_shrugging():
    """The guard above is only worth having if production reaches past it.

    ``_check_grading_assumptions_match_the_settings`` takes the catalogue as an
    optional argument, which is what lets its tests build one. If the real call
    site ever stopped passing it, every one of these refusals would fire on the
    committed plan and the check would report a missing measurement instead of
    the amount — so this pins that it does not.
    """
    report = every_line_of_the_report()

    assert not any(
        "how wide the scoring line being judged can be was never measured"
        in line
        for line in report
    ), "the real check did not reach the catalogue, so the width went down as unmeasured"
    assert any(
        "characters of the widest scoring line" in line for line in report
    )


# ── The measurement is a required field, not a defaulted one ──────────────


def test_the_width_is_the_one_field_that_defaults_to_nobody_looked():
    """``None`` by default, and it means *not measured*, never *nothing*.

    Every other measurement on these caps is read from a settings file that is
    always present. This one is not in any settings file, so a caller that does
    not pass it has not passed nothing — it has not looked. The default has to
    be the value the guards refuse.
    """
    declared = {
        field.name: field for field in dataclasses.fields(GradingCaps)
    }["characters_of_widest_scoring_line"]

    assert declared.default is None
    assert declared.default_factory is dataclasses.MISSING
    assert read_grading_caps(
        COMMITTED_MARKING_SETTINGS
    ).characters_of_widest_scoring_line is None


def test_the_module_no_longer_argues_that_the_part_has_no_top():
    """The paragraph that argued for the contradiction is gone.

    It read as a reason rather than an oversight, which is why it survived
    three passes over this module. What stands in its place quotes the old
    sentence and then says why it was wrong — a quotation being refuted is the
    opposite of the claim, and worth keeping, so this pins the refutation
    rather than banning the words.
    """
    import core.execution_envelope_grading_cost as grading_cost

    text = grading_cost.__doc__ or ""
    assert "The third piece was the contradiction this module printed" in text
    assert "The part was not unbounded." in text
    assert "The third piece really is uncapped" not in text


#: Places this same contradiction is still printed and that are not this task's
#: to close. Empty, and meant to stay that way: an entry here is a promise that
#: someone will come back, and the two tests below make sure it is a promise
#: this repository keeps rather than a line that quietly stops meaning anything.
STILL_OPEN_ELSEWHERE: tuple[tuple[str, str], ...] = ()

#: What used to be exempt, kept so the exemption cannot be emptied by accident.
#:
#: ``core/execution_envelope_preflight.py`` told a reader that the container's
#: carried-forward output was charged at a figure that "is a floor — the
#: blocking-error lines, the warnings, the repair guidance and the contract
#: section have no fixed width at all". That was the identical shape this whole
#: file is about: a total headed the largest possible bill, containing a part
#: described as having no top. It was recorded as still open rather than waved
#: through, because closing it needed the repair prompt measured rather than
#: guessed at.
#:
#: It is closed now. ``core/sandbox_runner.widest_repair_prompt_characters``
#: builds the widest repair prompt its committed wording allows and reports what
#: every part of it came to, so the check quotes a measurement instead of three
#: widths and an apology. The wording below is asserted *absent*, so emptying
#: STILL_OPEN_ELSEWHERE above cannot be mistaken for having done the work.
CLOSED_HERE = (
    (
        "core/execution_envelope_preflight.py",
        "and that is a floor — the blocking-error lines",
    ),
)


def test_every_exemption_still_points_at_something_real():
    """An exemption has to keep pointing at something real.

    An allow-list nobody checks becomes a list of things that were fixed years
    ago, and then the next real instance slips in beside them.
    """
    for relative, wording in STILL_OPEN_ELSEWHERE:
        text = (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8")
        assert text.count(wording) == 1, (
            f"{relative} no longer says {wording!r} exactly once — if it was "
            "fixed, delete it from STILL_OPEN_ELSEWHERE and record it in "
            "CLOSED_HERE"
        )


def test_what_this_sweep_used_to_excuse_is_really_gone():
    """The other half: an emptied allow-list has to have been earned.

    Deleting an entry from STILL_OPEN_ELSEWHERE is a one-line change that makes
    the sweep pass whether or not anything was fixed. So every entry that leaves
    lands in CLOSED_HERE, and this asserts the wording it named is no longer in
    the file at all — which only a real fix achieves.
    """
    for relative, wording in CLOSED_HERE:
        text = (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8")
        assert wording not in text, (
            f"{relative} says {wording!r} again — it is in CLOSED_HERE, so it "
            "was supposed to have been fixed, not moved"
        )
        assert not any(
            entry[1] == wording for entry in STILL_OPEN_ELSEWHERE
        ), f"{wording!r} cannot be both closed and still open"


def test_the_container_half_now_prices_the_whole_repair_prompt():
    """What closing CLOSED_HERE had to mean, checked against the check itself.

    The entry above could be satisfied by deleting the sentence and leaving the
    arithmetic exactly as optimistic as it was. This asserts the arithmetic
    moved: the container rule now reaches the runner's measurement of a whole
    repair prompt, and that measurement covers the four kinds of line the old
    sentence excused itself from counting.
    """
    from core.sandbox_runner import widest_repair_prompt_characters

    parts = widest_repair_prompt_characters()
    named = " ".join(parts).lower()
    for counted in ("blocking-error", "warning", "guidance", "contract"):
        assert counted in named, f"the repair prompt measurement omits {counted}"
    assert sum(parts.values()) > 2200, (
        "the measurement is no larger than the three tail widths the old "
        "sentence counted, so nothing was actually added"
    )


def test_nothing_the_production_code_can_print_says_the_bill_has_no_top():
    """The same sweep as the report test, but over every line that could print.

    The report test above reads one plan's output. This reads every string the
    production code could ever put in front of a reader, whichever plan it is
    given — the marking half has branches this repository's own plan does not
    reach. Docstrings are left out on purpose: prose that quotes the old
    sentence in order to explain why it was wrong is the record of this fix,
    not a repeat of it. A string that is not a docstring is something the code
    can say out loud.

    Nothing is exempt. STILL_OPEN_ELSEWHERE is empty, and the two tests above
    keep it honest: an entry has to name wording that is really there, and an
    entry that leaves has to name wording that is really gone.
    """
    import ast

    saying_no_top: list[str] = []
    for path in PRODUCTION_SOURCE:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prose = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(
                node,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            )
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        # Attribute docstrings — a bare string under a field — are prose too.
        prose |= {
            id(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if not isinstance(node.value, str) or id(node) in prose:
                continue
            for phrase in SAYS_THERE_IS_NO_TOP:
                if phrase not in node.value.lower():
                    continue
                exempt = any(
                    str(path.relative_to(BATCH_RUNNER_ROOT)) == relative
                    and wording in node.value
                    for relative, wording in STILL_OPEN_ELSEWHERE
                )
                if exempt:
                    continue
                saying_no_top.append(
                    f"{path.relative_to(BATCH_RUNNER_ROOT)}"
                    f":{node.lineno}: {phrase}"
                )

    assert saying_no_top == []


# ── The catalogue schema moved, so a stale one cannot be read ─────────────


def test_a_catalogue_written_before_the_width_existed_is_refused(tmp_path):
    """An old file is refused by name rather than read with a piece missing.

    Without the version bump the loader would meet a task with no width, raise
    a key error somewhere unhelpful, or — worse, if anybody had given the field
    a default — read the whole benchmark as having no scoring wording at all.
    """
    import json

    from core.execution_envelope_tasks import CATALOG_SCHEMA_VERSION

    honest = json.loads(
        (
            BATCH_RUNNER_ROOT
            / "experiments"
            / "execution_envelope"
            / "gdpval_task_catalog.json"
        ).read_text(encoding="utf-8")
    )
    assert CATALOG_SCHEMA_VERSION.endswith("v2")

    stale = dict(honest, schema_version="gdpval-task-catalog-v1")
    for task in stale["tasks"]:
        task.pop("widest_rubric_criterion_characters", None)
    written = tmp_path / "stale.json"
    written.write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(ValueError) as raised:
        load_task_catalog(written)

    assert "gdpval-task-catalog-v1" in str(raised.value)
    assert CATALOG_SCHEMA_VERSION in str(raised.value)


def test_the_committed_catalogue_is_the_version_this_code_reads():
    """And the committed one loads, so the bump was applied to both sides."""
    from core.execution_envelope_tasks import CATALOG_SCHEMA_VERSION

    assert the_catalog().schema_version == CATALOG_SCHEMA_VERSION
