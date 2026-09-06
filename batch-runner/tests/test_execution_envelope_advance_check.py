"""The free checks that stand between the run-place comparison and a bill.

Every test here is about one of two things: that the five tasks were settled by
a rule rather than by taste, and that the check refuses to let anything start
while a condition is missing, inconsistent, or unaffordable.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_cost import (  # noqa: E402
    CostAssumptions,
    ModelPrice,
    REFERENCE_FILE_CHARACTER_CAP,
    check_cost_ceiling,
    describe_cost_ceiling,
    estimate_cost_ceiling,
    load_price_table,
    max_attempt_counts,
    max_input_tokens_per_call,
)
from core.execution_envelope_preflight import (  # noqa: E402
    COMPARABLE_ENVIRONMENTS,
    COST_POLICY_BLOCK,
    COST_POLICY_RECORD_ONLY,
    PLAN_VERSION,
    conditions_from_plan,
    describe_uncontrolled_differences,
    load_plan,
    run_envelope_preflight,
)
from core.shared_first_request import residual_differences_for  # noqa: E402
from core.execution_envelope_tasks import (  # noqa: E402
    ADVANCE_CHECK_FORMAT_ORDER,
    ADVANCE_CHECK_TASK_COUNT,
    CATALOG_PATH,
    DATASET_REVISION,
    FORMAT_TEXT_ONLY,
    FULL_RUN_TASK_COUNT,
    INPUT_FILE_READ,
    TRIAL_RUN_TASK_COUNT,
    catalog_sha256,
    check_catalog_carries_no_scores,
    check_input_file_versions,
    full_run_tasks,
    load_task_catalog,
    reference_files_for,
    select_advance_check_tasks,
    select_trial_run_tasks,
    selection_matches,
    verify_input_file_versions,
)
from core.execution_environment_readiness import (  # noqa: E402
    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    ModelRunConditions,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)

# The five tasks the fixed rule produces. Written out here as a separate copy
# so that changing the rule, or changing the plan, is not enough on its own to
# change which tasks run: this line has to be changed too, deliberately, in a
# reviewed change.
EXPECTED_ADVANCE_CHECK_TASKS = (
    "02aa1805-c658-4069-8a6a-02dec146063a",  # spreadsheet
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",  # document
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",  # presentation
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",  # picture
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",  # text answer only
)

# The model marking would call to listen to sound. It has no published price
# and has never been called, so several tests below have to name it. Written
# once here rather than typed into each of them.
UNPRICED_SOUND_MODEL = "gpt-audio-1.5"

# The finding raised when a ``same_generated_code_rerun`` plan's run places do
# not send the same first request. It was true of this plan until 2026-09-06,
# when the three were put on one prompt file. Several tests below name the
# phrase to assert it is *absent*, so it is written once here rather than typed
# into each of them. See ``_apart_from_the_sound_model_and_absent_inputs``.
THE_THREE_ARE_NOT_ASKED_THE_SAME_THING = "these places are not asked the same thing"

# How many renders marking may spend on one task, read from the settings that
# decide it rather than restated. The plan's picture line is a ceiling only if
# it is the ceiling marking is actually configured to allow, and while both
# copies were typed out by hand the plan could keep an old number and go on
# calling itself a ceiling. That is what happened when the cap moved from 72 to
# 112: nothing held the two together, so nothing said so.
CONFIGURED_VISUAL_CALL_CAP = yaml.safe_load(
    (BATCH_RUNNER_ROOT / "grading_configs" / "default_v2.yaml").read_text(
        encoding="utf-8"
    )
)["judge"]["perception"]["visual"]["call_cap_per_task"]

# A number large enough to sit above the worked-out ceiling, so that tests
# about something else are not blocked by the amount. It is written into a copy
# of the plan held in memory and never into the plan on disk. **It approves
# nothing.** The only approved amount is the one in the committed plan, and
# test_the_committed_plan_records_the_approved_amount checks it separately.
#
# It has to be raised whenever the arithmetic learns to count something it was
# missing before, which is the opposite of a warning sign: the total rising
# means a real cost stopped being invisible. It was 500 until the marking sum
# stopped stating 10,000 tokens of input a call and started stating the 536,191
# the marking settings permit, which took the worked-out total past 7,600.
APPROVED_ENOUGH = 10_000

# The Azure resource this comparison is pinned to, matching the plan. Used to
# build a settings environment in which the Azure run place is correctly
# configured, so tests can tell "everything is in order" apart from "one thing
# was changed on purpose".
PINNED_AZURE_ACCOUNT = "hjeon-fdpo-foundry-eus2"
PINNED_AZURE_PROJECT = "gdpval-realworks"
PINNED_PROJECT_ENDPOINT = (
    f"https://{PINNED_AZURE_ACCOUNT}.services.ai.azure.com"
    f"/api/projects/{PINNED_AZURE_PROJECT}"
)

# A settings environment in which nothing is left to fix. The three expected-
# identity names below are here because the Azure run place refuses to start
# without them, and every automated run place in this repository that can spend
# money turns that requirement on. They were absent from this dictionary while
# the free check did not look at them, which made "fully ready" describe a
# setup the paid run would have stopped.
FULLY_READY_ENVIRON = {
    "EXECUTION_COMPARISON_PAID_RUN_APPROVED": "yes",
    "AZURE_AI_ROUTE_PROFILE": "project-ci",
    "FOUNDRY_PROJECT_ENDPOINT": PINNED_PROJECT_ENDPOINT,
    "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": PINNED_AZURE_ACCOUNT,
    "AZURE_AI_EXPECTED_PROJECT_ACCOUNT": PINNED_AZURE_ACCOUNT,
    "AZURE_AI_EXPECTED_PROJECT_NAME": PINNED_AZURE_PROJECT,
}


@pytest.fixture(scope="module")
def catalog():
    return load_task_catalog()


@pytest.fixture
def plan():
    return load_plan(PLAN_PATH)


def _ready_preflight(plan, **overrides):
    """Run the check with every outside condition satisfied."""
    settings = {
        "root": BATCH_RUNNER_ROOT,
        "docker_daemon_available": True,
        "docker_image_available": True,
        "azure_route_profile": "project-ci",
        "azure_route_served": True,
        "environ": FULLY_READY_ENVIRON,
    }
    settings.update(overrides)
    return run_envelope_preflight(plan, **settings)


def _approved(plan, amount=APPROVED_ENOUGH):
    plan = copy.deepcopy(plan)
    plan["cost"]["policy"] = COST_POLICY_BLOCK
    plan["cost"]["approved_maximum_usd"] = amount
    return plan


def _apart_from_the_sound_model_and_absent_inputs(result):
    """Every problem except the ones about the sound model nobody has used.

    Several tests below use "no problems at all" to mean "the thing I am
    testing is right, and nothing else is wrong either". That reading stopped
    being available when the marking check began reporting a gap between what
    the plan counts and what the marking settings allow.

    Two things are left in it, and they are left for the same reason: no
    measurement exists anywhere in this repository that would settle either.

    Both are about one model: ``gpt-audio-1.5``, which marking may call to
    listen to sound. It has never been called once, so how much it would send
    and write back has never been measured, and it has no published price, so
    even a measurement would not produce an amount. Neither fact can be fixed
    by writing a number into the plan — a number nobody measured is not
    evidence, and a zero would say the calls are free.

    Both checks report that one, from opposite ends: the marking check compares
    the plan against the marking settings, and the cost check refuses to price a
    model it has no price for. So the notes appear in two lists, and setting
    aside only ``grading_ceiling_problems`` would leave half of them behind.

    A third used to be set aside here and no longer is.
    ``grading_input_tokens_per_call`` was written at 10,000 while the marking
    settings permitted 536,191, and the plan kept the low number deliberately so
    the check had something to report. The plan now states the measured figure,
    the check is silent about it, and tests/test_the_marking_call_ceiling_is_
    reached.py holds it there. Nothing was weakened to achieve that: the note
    stopped appearing because the thing it reported stopped being true.

    Leaving the gap in would make these tests fail for a reason none of them is
    about. Weakening either check to make them pass would be far worse — every
    note in it is reporting something true. So the gap is set aside by name,
    asserted on separately just below, and held in place by
    tests/test_execution_envelope_grading_cost.py and
    tests/test_envelope_preflight_prices_the_marking_tool_results.py.

    The second thing set aside arrived with the input-file check and is set
    aside for a different reason: it depends on the machine. That check reads
    the real benchmark files and compares all 64 characters of each written
    fingerprint against them. On a machine that has already downloaded the
    pinned revision, every file is read and there is nothing to report. On one
    that has not — a fresh continuous-integration runner, for instance — there
    is nothing to read, and the check says so rather than passing the files. So
    these tests would pass on a developer's machine and fail on a build server,
    for a reason none of them is about, and none of that is the plan's fault.

    Only ``missing_input_file_problems`` is set aside, never
    ``InputFileVerification.problems``. A written fingerprint that disagrees
    with the file it names is a fault in the plan, says the same thing on every
    machine, and must fail these tests wherever they run.

    **A third thing was set aside between 2026-09-06 and 2026-09-06, and it is
    not set aside any more, because it was fixed rather than filtered.** The
    plan declares ``same_generated_code_rerun``, and the only check of that
    claim used to compare ``model_run_conditions.shared``'s two wording blocks —
    one value each, written once, inherited by all three places, so three copies
    of one string were held against each other and could not disagree. The plan
    says in its own words that the first of them is never sent. Measuring
    instead of reading showed the three places sending three differently named
    prompt files of three different widths.

    The fix was the first of the two the finding left open: the three now send
    one first request, from ``prompts/execution_envelope_shared.yaml``, because
    each of their settings files sets ``execution.shared_first_request: true``.
    So the finding is gone from a ready plan's output, and the filter that used
    to name it is gone from this helper — a filter for a finding that no longer
    occurs is a place a returning one could hide. The test below asserts its
    absence instead, and
    tests/test_the_three_run_places_really_send_one_request.py holds the three
    requests equal at the wire.
    """
    return [
        note
        for note in result.all_problems
        if note not in result.grading_ceiling_problems
        and note not in result.missing_input_file_problems
        and UNPRICED_SOUND_MODEL not in note
    ]


def test_a_ready_plan_reports_the_marking_gap_and_nothing_of_its_own(plan):
    """What ``_apart_from_the_sound_model_and_absent_inputs`` sets aside.

    If a new problem ever appears in a fully ready plan, it must not be able to
    hide behind that helper. This names exactly what is being set aside, in a
    way that reads the same on a machine holding the benchmark files and on one
    that has never downloaded them.
    """
    result = _ready_preflight(_approved(plan))

    assert _apart_from_the_sound_model_and_absent_inputs(result) == []
    assert len(result.grading_ceiling_problems) == 2
    assert result.may_start is False

    set_aside = [
        note
        for note in result.all_problems
        if note not in result.missing_input_file_problems
    ]
    assert len(set_aside) == 4

    about_the_sound_model = [
        note
        for note in set_aside
        if UNPRICED_SOUND_MODEL in note or "sound" in note
    ]
    about_the_input_figure = [
        note for note in set_aside if "input per marking call" in note
    ]
    assert len(about_the_sound_model) == 4
    # The plan now states what one marking call can carry, so nothing is set
    # aside on that account any more.
    assert about_the_input_figure == []
    # Nothing else. Every set-aside note is about the sound model.
    assert len(about_the_sound_model) == len(set_aside)

    # And the finding this used to carry is absent rather than filtered: the
    # three run places really are asked the same thing now.
    assert not any(
        THE_THREE_ARE_NOT_ASKED_THE_SAME_THING in note
        for note in result.all_problems
    ), result.all_problems


def test_only_files_that_are_absent_are_ever_set_aside(plan):
    """The set-aside list may hold "not here", never "does not match".

    This is the load-bearing half of the helper above. If a disagreement could
    reach ``missing_input_file_problems`` it would be filtered out of six other
    tests, and a plan pinning the wrong file would sail through all of them.
    """
    result = _ready_preflight(_approved(plan))

    for note in result.missing_input_file_problems:
        assert "is on this machine" in note, note
        assert "describes some other file" not in note, note
        assert "different revision" not in note, note

    for verification in result.input_files.values():
        assert set(verification.problems) & set(verification.missing_copies) == set()


def test_what_is_left_of_the_marking_gap_is_named_item_by_item(plan):
    """The gap used to cover five things. Four of them were the arithmetic.

    Marking may ask the model eleven times about one scoring line, let each
    reply run to 2,400 tokens, look at a picture up to seventy-two times per
    task, and listen to sound up to three times. The cost sum counted one call,
    a thousand tokens, and neither kind of perception at all. Those four are
    closed and must stay closed.

    A fifth is closed now too: the sum stated 10,000 tokens of input a call
    where the marking settings permit 536,191. It was left open on purpose while
    nothing in the plan could reach the figure, and it is shut by the plan
    stating the figure rather than by the check being quietened — so this test
    now insists it is gone, and that the number it used to show is gone with it.

    One remains, and it is not the same kind of thing. The sound model is the
    one no measurement exists for, so nothing that can be written in this
    repository would settle it.
    """
    result = _ready_preflight(_approved(plan))
    left = " | ".join(result.grading_ceiling_problems)

    assert UNPRICED_SOUND_MODEL in left
    for closed in (
        "marking calls per scoring line",
        "reading pictures",
        "tokens of reply",
        "input per marking call",
        "533334",
    ):
        assert closed not in left


def test_looking_at_pictures_is_now_part_of_the_worked_out_amount(plan):
    """The picture model is priced, so its calls turn into an amount.

    Before this existed the sum was silent about them, which read as free.
    """
    result = _ready_preflight(_approved(plan))

    assert result.cost.perception_model_calls > 0
    assert result.cost.perception_usd > 0
    # Sound stays out of the amount on purpose, and says so rather than
    # disappearing into it.
    assert result.cost.perception_of_unknown_size == [
        f"audio ({UNPRICED_SOUND_MODEL})"
    ]


def test_the_sound_model_reaches_the_refusal_that_was_written_for_it(plan):
    """An unpriced model has always been a refusal. It never saw this one.

    ``check_cost_ceiling`` refuses a run whose models have no published price,
    on the stated grounds that an unpriced model would otherwise be counted as
    free. The marking half never named the sound model, so the refusal had no
    chance to fire for it. Counting perception calls is what finally hands the
    name over.
    """
    result = _ready_preflight(_approved(plan))

    assert UNPRICED_SOUND_MODEL in result.cost.unpriced_models
    assert any(
        "no published price" in note and UNPRICED_SOUND_MODEL in note
        for note in result.all_problems
    )


def test_a_plan_that_marks_and_names_no_marking_settings_is_refused(plan):
    """Nothing having looked is not the same as the numbers being high enough."""
    plan = _approved(plan)
    plan.pop("grading_config")

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "names no marking settings file" in note
        for note in result.grading_ceiling_problems
    )


# ── The task catalogue holds nothing that could follow a score ────────────


def test_the_catalogue_holds_no_score(catalog):
    assert check_catalog_carries_no_scores() == []


def test_the_catalogue_describes_the_pinned_dataset(catalog):
    assert catalog.dataset_revision == DATASET_REVISION
    assert len(catalog.tasks) == FULL_RUN_TASK_COUNT


def test_the_catalogue_has_no_word_that_looks_like_a_result():
    """A blunt second look for anything result-shaped anywhere in the file."""
    text = CATALOG_PATH.read_text(encoding="utf-8").lower()
    for word in ("awarded", "verdict", "passed", "pct", "judge"):
        assert not re.search(rf'"[^"]*{word}[^"]*"\s*:', text), (
            f"the catalogue holds a field containing {word!r}"
        )


# ── The five tasks come from the rule, not from taste ─────────────────────


def test_the_rule_picks_the_five_tasks_written_down(catalog):
    selection = select_advance_check_tasks(catalog)
    assert selection.task_ids == EXPECTED_ADVANCE_CHECK_TASKS


def test_the_rule_gives_the_same_answer_every_time(catalog):
    first = select_advance_check_tasks(catalog)
    second = select_advance_check_tasks(catalog)
    assert first.task_ids == second.task_ids


def test_the_five_cover_five_different_deliverable_formats(catalog):
    selection = select_advance_check_tasks(catalog)
    formats = [entry[0] for entry in selection.reasons]
    assert formats == list(ADVANCE_CHECK_FORMAT_ORDER)
    assert len(set(formats)) == ADVANCE_CHECK_TASK_COUNT


def test_the_five_cover_five_different_jobs(catalog):
    selection = select_advance_check_tasks(catalog)
    by_id = catalog.by_task_id()
    jobs = [by_id[task_id].occupation for task_id in selection.task_ids]
    assert len(set(jobs)) == ADVANCE_CHECK_TASK_COUNT


def test_each_chosen_task_really_hands_in_the_format_it_was_chosen_for(catalog):
    by_id = catalog.by_task_id()
    selection = select_advance_check_tasks(catalog)
    for deliverable_format, task_id, _ in selection.reasons:
        task = by_id[task_id]
        if deliverable_format == FORMAT_TEXT_ONLY:
            assert task.deliverable_file_extensions == ()
        else:
            assert task.any_format_is(deliverable_format)


def test_the_selection_records_fingerprints_that_match_the_files(catalog):
    selection = select_advance_check_tasks(catalog)
    assert selection.catalog_sha256 == catalog_sha256()
    assert selection.dataset_file_sha256 == catalog.dataset_file_sha256
    assert len(selection.catalog_sha256) == 64


def test_a_changed_task_list_is_reported(catalog):
    selection = select_advance_check_tasks(catalog)
    swapped = list(selection.task_ids)
    swapped[0], swapped[1] = swapped[1], swapped[0]

    problems = selection_matches(swapped, selection)

    assert problems
    assert "does not match" in problems[0]


def test_the_plan_writes_down_exactly_what_the_rule_produced(plan, catalog):
    written = plan["model_run_conditions"]["shared"]["task_ids"]
    assert tuple(written) == select_advance_check_tasks(catalog).task_ids


def test_the_three_stages_hold_five_thirty_and_all_tasks(plan, catalog):
    sizes = plan["run_sizes"]
    assert len(sizes["advance_check"]["task_ids"]) == ADVANCE_CHECK_TASK_COUNT
    assert len(sizes["trial_run"]["task_ids"]) == TRIAL_RUN_TASK_COUNT
    assert len(sizes["full_run"]["task_ids"]) == FULL_RUN_TASK_COUNT
    assert sizes["trial_run"]["task_ids"] == list(select_trial_run_tasks(catalog))
    assert sizes["full_run"]["task_ids"] == list(full_run_tasks(catalog))


def test_the_thirty_keep_the_industry_mix(catalog):
    chosen = select_trial_run_tasks(catalog)
    by_id = catalog.by_task_id()
    industries = {by_id[task_id].sector for task_id in chosen}
    every_industry = {task.sector for task in catalog.tasks}
    assert industries == every_industry


# ── The input fingerprints describe the real inputs ───────────────────────


def test_the_plan_pins_every_reference_file_the_five_tasks_use(plan, catalog):
    conditions = conditions_from_plan(plan)
    for environment, entry in conditions.items():
        verification = verify_input_file_versions(
            entry.input_file_versions, entry.task_ids, catalog
        )
        # Whether the files themselves are on the machine running this test is
        # not the plan's fault, and the check keeps that answer in its own list.
        # What is left is what the plan got wrong, which must be nothing.
        assert verification.problems == (), environment


def test_a_reference_file_left_unpinned_is_reported(plan, catalog):
    conditions = conditions_from_plan(plan)
    entry = conditions["host_python_process"]
    trimmed = dict(entry.input_file_versions)
    dropped = sorted(reference_files_for(entry.task_ids, catalog))[0]
    trimmed.pop(dropped)

    problems = check_input_file_versions(trimmed, entry.task_ids, catalog)

    assert any("no written fingerprint" in note for note in problems)


def test_a_fingerprint_that_belongs_to_another_file_is_reported(plan, catalog):
    """A tampered fingerprint is always reported, in the wording it can support.

    How strongly the report is allowed to put it depends on what this machine
    can see. Where a copy of the file is present its digest settles the matter,
    and the note says the written value describes some other file. Where no copy
    is present, all that is visible is that the folder name and the written value
    disagree — and in this dataset most folders are not named after their file's
    contents, so that disagreement cannot say which of the two is at fault.

    This used to assert the strong wording unconditionally, and passed on a
    machine with nothing downloaded only because the check made that claim from
    the shape of the path. Tampering with the fingerprint destroys the very
    evidence that this folder is one of the content-derived ones, so a machine
    without the bytes genuinely cannot tell the tampering from a correct value
    under an opaque folder. What holds everywhere is that it is reported, that
    the run stops, and that the file is never recorded as one that was read and
    agreed.
    """
    conditions = conditions_from_plan(plan)
    entry = conditions["host_python_process"]
    tampered = dict(entry.input_file_versions)
    target = sorted(reference_files_for(entry.task_ids, catalog))[0]
    tampered[target] = "0" * 64

    verification = verify_input_file_versions(tampered, entry.task_ids, catalog)
    notes = [note for note in verification.all_notes if target in note]

    assert notes, f"{target} was tampered with and the report said nothing"
    assert any(
        "describes some other file" in note or "does not repeat the first" in note
        for note in notes
    ), notes
    check = next(one for one in verification.checks if one.path == target)
    assert check.state != INPUT_FILE_READ, "a tampered value was recorded as read"


def test_a_dataset_fingerprint_that_does_not_match_is_reported(plan, catalog):
    conditions = conditions_from_plan(plan)
    entry = conditions["host_python_process"]
    tampered = dict(entry.input_file_versions)
    key = f"{catalog.dataset_repo_id}@{catalog.dataset_revision}"
    tampered[key] = "1" * 64

    problems = check_input_file_versions(tampered, entry.task_ids, catalog)

    assert any("but the catalogue was built from" in note for note in problems)


# ── The price list stays in step with the rest of the repository ──────────


def test_the_price_list_matches_the_one_already_used_for_grading():
    """One price list, not two that quietly drift apart."""
    source = (REPOSITORY_ROOT / "scripts" / "analyze_grade_run.py").read_text(
        encoding="utf-8"
    )
    block = re.search(
        r"PRICING_USD_PER_M_TOKENS\s*=\s*\{(.*?)\}", source, re.S
    )
    assert block, "the grading price list could not be found"
    existing = {
        name: (Decimal(first), Decimal(second))
        for name, first, second in re.findall(
            r'"([^"]+)":\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', block.group(1)
        )
    }
    assert existing

    committed = load_price_table()
    for model, (input_price, output_price) in existing.items():
        assert model in committed, f"{model} is missing from the committed list"
        assert committed[model].input_usd_per_million == input_price
        assert committed[model].output_usd_per_million == output_price


def test_the_model_the_plan_uses_has_a_published_price(plan):
    conditions = conditions_from_plan(plan)
    prices = load_price_table()
    for entry in conditions.values():
        assert entry.resolved_model in prices


# ── The worst case is counted, and counted conservatively ─────────────────


def _conditions(**overrides):
    base = {
        "provider": "azure",
        "resource": "hjeon-fdpo-foundry-eus2",
        "deployment": "gpt-5.4",
        "resolved_model": "gpt-5.4",
        "api_version": "2025-04-01-preview",
        "model_serving_path": SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
        "system_instruction": "a",
        "task_instruction": "b",
        "task_ids": ["02aa1805-c658-4069-8a6a-02dec146063a"],
        "input_file_versions": {},
        "max_output_tokens": 1000,
        "per_task_timeout_seconds": 60,
        "self_review_enabled": False,
        "self_review_max_attempts": 0,
        "retry_reasons_allowed": ["infrastructure_error"],
        "retry_max_attempts": 0,
        "automatic_model_switch_allowed": False,
        "automatic_fallback_allowed": False,
        "unsupported_runner_substitution_allowed": False,
    }
    base.update(overrides)
    return ModelRunConditions.from_mapping(base)


def test_one_attempt_with_no_retries_is_one_call():
    counts = max_attempt_counts(
        _conditions(),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    assert counts.model_calls == 1
    assert counts.answer_lengths == 1


def test_every_allowed_retry_is_counted():
    counts = max_attempt_counts(
        _conditions(retry_max_attempts=3),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    assert counts.model_calls == 4


def test_a_tool_loop_multiplies_the_calls_but_not_a_capped_answer():
    looping = max_attempt_counts(
        _conditions(retry_max_attempts=3),
        tool_loop_max_model_turns=8,
        output_tokens_capped_per_attempt=True,
    )
    assert looping.model_calls == 32
    assert looping.answer_lengths == 4


def test_self_review_adds_a_look_and_a_replacement():
    counts = max_attempt_counts(
        _conditions(self_review_enabled=True, self_review_max_attempts=2),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    # One attempt, plus for each review: one look and one replacement.
    assert counts.model_calls == 1 + 2 * 2


def test_self_review_that_is_switched_off_costs_nothing():
    counts = max_attempt_counts(
        _conditions(self_review_enabled=False, self_review_max_attempts=0),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    assert counts.model_calls == 1


def test_a_reference_file_is_counted_at_the_cap_the_reader_applies(catalog):
    assumptions = CostAssumptions.from_mapping(
        {
            "characters_per_token": 3,
            "instruction_character_count": 0,
            "tool_loop_max_model_turns": {"host_python_process": 1},
            "output_tokens_capped_per_attempt": {"host_python_process": False},
            "max_tool_result_tokens_per_turn": {"host_python_process": 0},
            "safety_multiplier": 1,
            "grading_required": False,
            "grading_model": "gpt-5.4",
            "grading_calls_per_rubric_item": 1,
            "grading_input_tokens_per_call": 1,
            "grading_output_tokens_per_call": 1,
        }
    )
    by_id = catalog.by_task_id()
    with_reference = by_id["2ea2e5b5-257f-42e6-a7dc-93763f28b19d"]
    assert with_reference.reference_file_count == 1

    tokens = max_input_tokens_per_call(with_reference, assumptions)

    expected = (with_reference.prompt_character_count + REFERENCE_FILE_CHARACTER_CAP) / 3
    assert tokens == pytest.approx(expected, abs=1)


def test_a_model_with_no_published_price_is_not_treated_as_free(catalog):
    assumptions = CostAssumptions.from_mapping(
        {
            "characters_per_token": 3,
            "instruction_character_count": 0,
            "tool_loop_max_model_turns": {"host_python_process": 1},
            "output_tokens_capped_per_attempt": {"host_python_process": False},
            "max_tool_result_tokens_per_turn": {"host_python_process": 0},
            "safety_multiplier": 1,
            "grading_required": False,
            "grading_model": "gpt-5.4",
            "grading_calls_per_rubric_item": 1,
            "grading_input_tokens_per_call": 1,
            "grading_output_tokens_per_call": 1,
        }
    )
    ceiling = estimate_cost_ceiling(
        conditions_by_environment={
            "host_python_process": _conditions(resolved_model="a-model-nobody-priced")
        },
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )

    assert ceiling.unpriced_models == ["a-model-nobody-priced"]
    problems = check_cost_ceiling(ceiling, approved_maximum_usd=1000)
    assert any("no published price" in note for note in problems)


# ── Marking that looks and listens is counted too ─────────────────────────
#
# Marking can send a picture of the answer to one model and a sound clip to
# another. Both are billed separately from the model that reads the words, and
# until this section existed the sum did not count a single one of those calls.


def _marking_assumptions(perception=None, **overrides):
    """The smallest set of assumptions that marks something.

    ``grading_perception`` is passed through untouched, including when it is
    left out entirely, so that the tests below can show what each shape does.
    """
    mapping = {
        "characters_per_token": 3,
        "instruction_character_count": 0,
        "tool_loop_max_model_turns": {"host_python_process": 1},
        "output_tokens_capped_per_attempt": {"host_python_process": False},
        "max_tool_result_tokens_per_turn": {"host_python_process": 0},
        "safety_multiplier": 1,
        "grading_required": True,
        "grading_model": "gpt-5.4",
        "grading_calls_per_rubric_item": 1,
        "grading_input_tokens_per_call": 1,
        "grading_output_tokens_per_call": 1,
    }
    if perception is not None:
        mapping["grading_perception"] = perception
    mapping.update(overrides)
    return CostAssumptions.from_mapping(mapping)


def _marking_ceiling(catalog, perception=None, **overrides):
    """A ceiling over all five tasks, so "per task" can actually be seen.

    One task would not tell a per-task count apart from a per-run one.
    """
    return estimate_cost_ceiling(
        conditions_by_environment={
            "host_python_process": _conditions(
                task_ids=list(EXPECTED_ADVANCE_CHECK_TASKS)
            )
        },
        tasks_by_id=catalog.by_task_id(),
        assumptions=_marking_assumptions(perception, **overrides),
    )


def test_a_plan_that_says_nothing_about_perception_still_works(catalog):
    """Leaving the block out is allowed, because not every plan marks anything.

    It costs nothing here and claims nothing. What stops that from becoming a
    quiet way to hide the calls is a separate check, which compares the plan
    against the marking settings and reports a block that should be there and
    is not.
    """
    ceiling = _marking_ceiling(catalog)

    assert ceiling.perception_model_calls == 0
    assert ceiling.perception_usd == 0
    assert ceiling.perception_of_unknown_size == []


def test_perception_is_counted_once_per_task_rather_than_per_scoring_line(
    catalog,
):
    """One picture can answer several scoring lines, and the cap is per task.

    The marking settings limit how many times a task may be looked at, not how
    many times each line may be. Counting per line would multiply the figure by
    however many lines a task happens to have, which is not what would be
    billed.
    """
    ceiling = _marking_ceiling(
        catalog,
        {
            "vision": {
                "model": "gpt-5.4",
                "calls_per_task": 4,
                "input_tokens_per_call": 1000,
                "output_tokens_per_call": 100,
            }
        },
    )

    assert ceiling.perception_model_calls == 4 * len(EXPECTED_ADVANCE_CHECK_TASKS)
    assert ceiling.perception_usd > 0


def test_a_kind_of_perception_nobody_measured_is_named_rather_than_priced(
    catalog,
):
    """A size nobody established is a refusal, not a zero.

    The calls are still counted, because they will still happen. What cannot be
    done is turn them into an amount, and saying so is the whole point: an
    amount that silently leaves them out reads as an amount that includes them.
    """
    ceiling = _marking_ceiling(
        catalog,
        {
            "audio": {
                "model": "gpt-5.4",
                "calls_per_task": 3,
                "input_tokens_per_call": None,
                "output_tokens_per_call": None,
            }
        },
    )

    assert ceiling.perception_model_calls == 3 * len(EXPECTED_ADVANCE_CHECK_TASKS)
    assert ceiling.perception_usd == 0
    assert ceiling.perception_of_unknown_size == ["audio (gpt-5.4)"]
    assert any(
        "unknown rather than nothing" in note
        for note in check_cost_ceiling(ceiling, approved_maximum_usd=10_000)
    )


def test_half_a_measurement_is_no_measurement(catalog):
    """Knowing what a call sends is not knowing what it writes back.

    Nothing in this repository limits how long a perception reply may run, so a
    known input size and an unknown output size still leaves the amount
    unknown.
    """
    ceiling = _marking_ceiling(
        catalog,
        {
            "vision": {
                "model": "gpt-5.4",
                "calls_per_task": 2,
                "input_tokens_per_call": 5000,
                "output_tokens_per_call": None,
            }
        },
    )

    assert ceiling.perception_usd == 0
    assert ceiling.perception_of_unknown_size == ["vision (gpt-5.4)"]


def test_a_perception_model_with_no_published_price_is_refused(catalog):
    """The refusal that was already written for unpriced models reaches these.

    It could not before. The marking half never named the picture-reading or
    sound-listening models, so a model with no price simply never arrived at
    the check that would have stopped it.
    """
    ceiling = _marking_ceiling(
        catalog,
        {
            "audio": {
                "model": "a-listening-model-nobody-priced",
                "calls_per_task": 1,
                "input_tokens_per_call": 100,
                "output_tokens_per_call": 100,
            }
        },
    )

    assert ceiling.unpriced_models == ["a-listening-model-nobody-priced"]
    assert ceiling.perception_usd == 0
    assert any(
        "no published price" in note
        for note in check_cost_ceiling(ceiling, approved_maximum_usd=10_000)
    )


def test_a_kind_of_perception_that_is_switched_off_costs_nothing(catalog):
    ceiling = _marking_ceiling(
        catalog,
        {
            "vision": {
                "model": "gpt-5.4",
                "calls_per_task": 0,
                "input_tokens_per_call": None,
                "output_tokens_per_call": None,
            }
        },
    )

    assert ceiling.perception_model_calls == 0
    assert ceiling.perception_of_unknown_size == []
    assert ceiling.unpriced_models == []


def test_perception_is_left_out_when_nothing_is_being_marked(catalog):
    ceiling = _marking_ceiling(
        catalog,
        {
            "vision": {
                "model": "gpt-5.4",
                "calls_per_task": 9,
                "input_tokens_per_call": 1000,
                "output_tokens_per_call": 100,
            }
        },
        grading_required=False,
    )

    assert ceiling.perception_model_calls == 0
    assert ceiling.perception_usd == 0


def test_perception_is_part_of_the_total_and_of_the_call_count(catalog):
    """It has to reach the figures a reader actually looks at.

    Counting the calls into a field nothing adds up would be no better than not
    counting them.
    """
    without = _marking_ceiling(catalog)
    with_pictures = _marking_ceiling(
        catalog,
        {
            "vision": {
                "model": "gpt-5.4",
                "calls_per_task": 6,
                "input_tokens_per_call": 20_000,
                "output_tokens_per_call": 3000,
            }
        },
    )

    assert with_pictures.total_before_safety_usd > without.total_before_safety_usd
    assert with_pictures.total_model_calls == without.total_model_calls + 6 * len(
        EXPECTED_ADVANCE_CHECK_TASKS
    )


def test_the_written_out_sum_and_the_readable_lines_both_show_perception(
    catalog,
):
    """A reader must be able to see the calls and see what is missing from them.

    Two of the three kinds here are priced, one is not, and the printed line
    has to say which is which rather than presenting one amount as if it
    covered everything.
    """
    ceiling = _marking_ceiling(
        catalog,
        {
            "vision": {
                "model": "gpt-5.4",
                "calls_per_task": 2,
                "input_tokens_per_call": 1000,
                "output_tokens_per_call": 100,
            },
            "audio": {
                "model": "gpt-5.4",
                "calls_per_task": 1,
                "input_tokens_per_call": None,
                "output_tokens_per_call": None,
            },
        },
    )

    written = ceiling.as_dict()["grading_perception"]
    assert written["most_model_calls"] == 3 * len(EXPECTED_ADVANCE_CHECK_TASKS)
    assert Decimal(written["most_it_could_cost_usd"]) > 0
    assert written["kinds_whose_size_is_unknown"] == ["audio (gpt-5.4)"]

    printed = " | ".join(describe_cost_ceiling(ceiling))
    assert "looking and listening" in printed
    assert "audio (gpt-5.4)" in printed
    assert "never measured" in printed


# ── A missing price must not make the totals look smaller in silence ───────
#
# Three separate things can put calls into the count and no money against
# them: a run place whose model has no published price, a marking model with
# no published price, and a perception kind that is either unmeasured or
# unpriced. All three come out as the same zero, and a zero drags both totals
# *down*. Until this section existed the report named only the unmeasured one,
# and even that only inside the perception line — never beside the totals a
# reader actually quotes.


PRICED = "priced-model"
UNPRICED = "no-price-model"

#: Two prices, so a test can say which model is missing rather than emptying
#: the whole table. Emptying it proves only that nothing is priced, which is
#: not the state this defect lives in.
ONE_PRICED_MODEL = {
    PRICED: ModelPrice(
        model=PRICED,
        input_usd_per_million=Decimal("1.25"),
        output_usd_per_million=Decimal("5.00"),
    )
}


def _ceiling_with_one_thing_unpriced(
    catalog,
    *,
    run_place_model=PRICED,
    grading_model=PRICED,
    perception=None,
):
    """A whole ceiling where exactly the named part has no published price.

    Built through ``estimate_cost_ceiling`` rather than by constructing a
    ``CostCeiling`` by hand, because a hand-built one would let these tests
    agree with a producer that had stopped filling the fields in.
    """
    mapping = {
        "characters_per_token": 3,
        "instruction_character_count": 0,
        "tool_loop_max_model_turns": {"host_python_process": 1},
        "output_tokens_capped_per_attempt": {"host_python_process": False},
        "max_tool_result_tokens_per_turn": {"host_python_process": 0},
        "safety_multiplier": 1,
        "grading_required": True,
        "grading_model": grading_model,
        "grading_calls_per_rubric_item": 1,
        "grading_input_tokens_per_call": 1000,
        "grading_output_tokens_per_call": 100,
    }
    if perception is not None:
        mapping["grading_perception"] = perception
    return estimate_cost_ceiling(
        conditions_by_environment={
            "host_python_process": _conditions(
                resolved_model=run_place_model, deployment=run_place_model
            )
        },
        tasks_by_id=catalog.by_task_id(),
        assumptions=CostAssumptions.from_mapping(mapping),
        prices=ONE_PRICED_MODEL,
    )


def _priced_vision(model=PRICED):
    return {
        "vision": {
            "model": model,
            "calls_per_task": 2,
            "input_tokens_per_call": 1000,
            "output_tokens_per_call": 100,
        }
    }


def _warnings(ceiling):
    return [
        line
        for line in describe_cost_ceiling(ceiling)
        if line.startswith("WARNING")
    ]


def test_a_fully_priced_ceiling_says_nothing_is_missing_from_its_totals(catalog):
    """The quiet case, so the loud cases mean something.

    A warning that is always printed is not a warning. This pins the state in
    which the totals really are the most this could cost, and shows the report
    stays silent about it.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog, perception=_priced_vision()
    )

    assert ceiling.unpriced_models == []
    assert ceiling.perception_of_unknown_price == []
    assert ceiling.perception_of_unknown_size == []
    assert ceiling.grading_model_with_no_price is None
    assert ceiling.what_the_totals_leave_out() == []
    assert _warnings(ceiling) == []
    assert ceiling.total_usd > 0
    assert ceiling.as_dict()["what_the_totals_leave_out"] == []


def test_an_unpriced_run_place_model_is_named_beside_its_own_zero(catalog):
    """The run-place line prints a call count and a nothing. Say why.

    Reading "at most 1 model calls, at most 0.00 United States dollars" as a
    fact about a real run place is exactly the mistake available here, and
    nothing on that line used to stop it.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog, run_place_model=UNPRICED, perception=_priced_vision()
    )

    (entry,) = ceiling.environments
    assert entry.model_calls > 0
    assert entry.usd == 0
    assert ceiling.unpriced_models == [UNPRICED]

    (line,) = [
        line
        for line in describe_cost_ceiling(ceiling)
        if line.startswith("host_python_process")
    ]
    assert "no published price was found for " + UNPRICED in line
    assert "in the count and in no figure" in line


def test_an_unpriced_marking_model_is_named_beside_its_own_zero(catalog):
    """The same for marking, which is the largest figure on the page.

    The marking half is thousands of calls on the committed plan. Losing it to
    a missing price is the single biggest way these totals can fall, and the
    old report showed the fall with no explanation anywhere.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog, grading_model=UNPRICED, perception=_priced_vision()
    )

    assert ceiling.grading_model_calls > 0
    assert ceiling.grading_usd == 0
    assert ceiling.grading_model_with_no_price == UNPRICED

    (line,) = [
        line
        for line in describe_cost_ceiling(ceiling)
        if line.startswith("grading: ")
    ]
    assert "no published price was found for " + UNPRICED in line
    assert "in the count and in no figure" in line
    assert ceiling.as_dict()["grading"]["model_with_no_published_price"] == UNPRICED


def test_an_unpriced_perception_model_is_named_even_when_its_size_is_known(
    catalog,
):
    """The gap this section was opened by: a measured kind with no price.

    ``perception_of_unknown_size`` is empty here, because the size *was*
    measured. Before this field existed that emptiness silenced the line
    completely — a priced-looking figure of zero with no caveat of any kind.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog, perception=_priced_vision(UNPRICED)
    )

    assert ceiling.perception_model_calls > 0
    assert ceiling.perception_usd == 0
    assert ceiling.perception_of_unknown_size == []
    assert ceiling.perception_of_unknown_price == [f"vision ({UNPRICED})"]

    (line,) = [
        line
        for line in describe_cost_ceiling(ceiling)
        if line.startswith("grading, looking and listening")
    ]
    assert f"no published price was found for vision ({UNPRICED})" in line
    assert "in the count and in no figure" in line
    assert "never measured" not in line

    written = ceiling.as_dict()["grading_perception"]
    assert written["kinds_whose_price_is_unknown"] == [f"vision ({UNPRICED})"]
    assert written["kinds_whose_size_is_unknown"] == []


def test_a_perception_kind_missing_both_is_told_it_is_missing_both(catalog):
    """Being told only about the measurement invites the wrong repair.

    A reader who hears the size was never measured will go and measure it, and
    arrive back at the same zero. The line has to say the price is missing too,
    in so many words.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog,
        perception={
            "vision": {
                "model": UNPRICED,
                "calls_per_task": 1,
                "input_tokens_per_call": None,
                "output_tokens_per_call": None,
            }
        },
    )

    assert ceiling.perception_of_unknown_size == [f"vision ({UNPRICED})"]
    assert ceiling.perception_of_unknown_price == [f"vision ({UNPRICED})"]

    (line,) = [
        line
        for line in describe_cost_ceiling(ceiling)
        if line.startswith("grading, looking and listening")
    ]
    assert "never measured" in line
    assert "no published price was found" in line
    assert "measuring it would not produce a figure either" in line


@pytest.mark.parametrize(
    "kwargs",
    [
        {"run_place_model": UNPRICED, "perception": _priced_vision()},
        {"grading_model": UNPRICED, "perception": _priced_vision()},
        {"perception": _priced_vision(UNPRICED)},
    ],
    ids=["run place", "marking", "perception"],
)
def test_every_way_to_lose_a_price_warns_beside_the_totals(catalog, kwargs):
    """Whichever part loses its price, the totals must say they are short.

    The parts already say it on their own lines. This is about the last two
    lines on the page, because a total is what gets carried into a message
    asking somebody to approve a bill.
    """
    ceiling = _ceiling_with_one_thing_unpriced(catalog, **kwargs)

    (warning,) = _warnings(ceiling)
    assert "lower than the most this could cost" in warning
    assert "no published price was found for " + UNPRICED in warning
    assert str(ceiling.total_model_calls) in warning
    assert ceiling.what_the_totals_leave_out() == [
        "no published price was found for " + UNPRICED
    ]


def test_the_warning_arrives_after_both_totals_it_is_about(catalog):
    """Order is the whole point: a caveat under a number is read, above it is not."""
    lines = describe_cost_ceiling(
        _ceiling_with_one_thing_unpriced(
            catalog, grading_model=UNPRICED, perception=_priced_vision()
        )
    )

    before = next(
        i for i, line in enumerate(lines) if line.startswith("before the safety")
    )
    after = next(
        i for i, line in enumerate(lines) if line.startswith("after multiplying by")
    )
    warning = next(i for i, line in enumerate(lines) if line.startswith("WARNING"))
    assert before < after < warning


def test_a_model_missing_from_two_places_is_named_once_in_the_warning(catalog):
    """The two reasons are separate; the model is not, so it is said once.

    An unpriced perception model lands in ``unpriced_models`` *and* in
    ``perception_of_unknown_price``. Building the warning from both lists
    would print the same model name twice and read like two problems.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog,
        perception={
            "vision": {
                "model": UNPRICED,
                "calls_per_task": 1,
                "input_tokens_per_call": None,
                "output_tokens_per_call": None,
            }
        },
    )

    (warning,) = _warnings(ceiling)
    assert warning.count("no published price was found") == 1
    assert "never measured" in warning
    assert ceiling.what_the_totals_leave_out() == [
        "no published price was found for " + UNPRICED,
        f"how much vision ({UNPRICED}) sends and writes back was never measured",
    ]


def test_the_printed_lines_and_the_written_answer_cannot_disagree(catalog):
    """One derivation, two audiences. A person and a script get the same list."""
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog, grading_model=UNPRICED, perception=_priced_vision()
    )

    reasons = ceiling.what_the_totals_leave_out()
    assert ceiling.as_dict()["what_the_totals_leave_out"] == reasons
    (warning,) = _warnings(ceiling)
    for reason in reasons:
        assert reason in warning


def test_the_totals_really_do_fall_when_a_price_goes_missing(catalog):
    """The defect itself, stated as arithmetic rather than as wording.

    This is why silence was not merely unhelpful. A missing price does not
    leave the figure alone; it makes it *smaller*, so the report was at its
    least alarming exactly when it knew least.
    """
    priced = _ceiling_with_one_thing_unpriced(
        catalog, perception=_priced_vision()
    )
    unpriced = _ceiling_with_one_thing_unpriced(
        catalog, grading_model=UNPRICED, perception=_priced_vision()
    )

    assert unpriced.total_model_calls == priced.total_model_calls
    assert unpriced.total_usd < priced.total_usd
    assert _warnings(priced) == []
    assert len(_warnings(unpriced)) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"run_place_model": UNPRICED, "perception": _priced_vision()},
        {"grading_model": UNPRICED, "perception": _priced_vision()},
        {"perception": _priced_vision(UNPRICED)},
    ],
    ids=["run place", "marking", "perception"],
)
def test_what_stops_a_run_is_unchanged_by_any_of_this(catalog, kwargs):
    """Wording moved; the refusal did not.

    ``check_cost_ceiling`` is not touched by this fix, and it already refused
    every one of these. Pinning that here is what keeps a reporting change from
    turning into a new condition on runs that used to be allowed or refused.
    """
    ceiling = _ceiling_with_one_thing_unpriced(catalog, **kwargs)

    problems = check_cost_ceiling(ceiling, approved_maximum_usd=1000)
    assert [note for note in problems if "no published price" in note]

    allowed = _ceiling_with_one_thing_unpriced(
        catalog, perception=_priced_vision()
    )
    assert not [
        note
        for note in check_cost_ceiling(allowed, approved_maximum_usd=1000)
        if "no published price" in note
    ]


def test_the_old_silence_would_be_caught_if_it_came_back(catalog):
    """A check nobody has seen fail is not different from one that cannot.

    The old behaviour is restored in memory only — the producer is left alone
    and the derivation it feeds is emptied. What comes back is the report as it
    was: a total that fell by more than half, printed with nothing beside it.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog, grading_model=UNPRICED, perception=_priced_vision()
    )
    priced = _ceiling_with_one_thing_unpriced(
        catalog, perception=_priced_vision()
    )
    assert ceiling.total_usd * 2 < priced.total_usd

    with patch.object(
        type(ceiling), "what_the_totals_leave_out", lambda self: []
    ):
        old_lines = describe_cost_ceiling(ceiling)

    assert not [line for line in old_lines if line.startswith("WARNING")]
    # And the money it prints is the same money — which is what made this
    # survivable for so long. Nothing was wrong with the arithmetic; the
    # arithmetic was being asked a question it could not answer, and answered
    # anyway.
    assert [line for line in old_lines if line.startswith("after multiplying by")] == [
        line
        for line in describe_cost_ceiling(ceiling)
        if line.startswith("after multiplying by")
    ]


def test_the_old_silence_on_a_measured_but_unpriced_kind_would_be_caught(catalog):
    """The third cause, the one nothing in this repository used to name.

    An unmeasured kind was already called out on its own line. A *measured* one
    whose model has no price reached the same zero down a path with no wording
    on it at all, and emptying the new list here is precisely that old state.
    """
    ceiling = _ceiling_with_one_thing_unpriced(
        catalog, perception=_priced_vision(UNPRICED)
    )
    old = replace(ceiling, perception_of_unknown_price=[], unpriced_models=[])

    (line,) = [
        line
        for line in describe_cost_ceiling(old)
        if line.startswith("grading, looking and listening")
    ]
    assert "at most 0.00 United States dollars" in line
    assert "no published price" not in line
    assert not [
        line for line in describe_cost_ceiling(old) if line.startswith("WARNING")
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"run_place_model": UNPRICED, "perception": _priced_vision()},
        {"grading_model": UNPRICED, "perception": _priced_vision()},
        {"perception": _priced_vision(UNPRICED)},
    ],
    ids=["run place", "marking", "perception"],
)
def test_the_missing_price_is_never_reported_as_a_price_of_zero(catalog, kwargs):
    """No line may show the zero on its own.

    Whichever part is unpriced, the figure printed for it is 0.00. That string
    appearing without a caveat on the same line is the whole defect, so it is
    asserted directly rather than through any one wording.
    """
    for line in describe_cost_ceiling(_ceiling_with_one_thing_unpriced(catalog, **kwargs)):
        if "at most 0.00 United States dollars" in line:
            assert "no published price was found" in line, line


@pytest.mark.parametrize(
    "broken, expected",
    [
        ({"vision": "sometimes"}, "must be a block of settings"),
        ({"vision": {"model": "gpt-5.4"}}, "is missing"),
        (
            {
                "vision": {
                    "model": "gpt-5.4",
                    "calls_per_task": -1,
                    "input_tokens_per_call": 1,
                    "output_tokens_per_call": 1,
                }
            },
            "fewer than no times",
        ),
        (
            {
                "vision": {
                    "model": "gpt-5.4",
                    "calls_per_task": 1,
                    "input_tokens_per_call": -5,
                    "output_tokens_per_call": 1,
                }
            },
            "less than nothing",
        ),
    ],
)
def test_a_perception_block_that_makes_no_sense_is_refused(broken, expected):
    """Each refusal says what is wrong in words, not by failing later.

    A block missing a setting is the one that matters most: without this, a
    forgotten ``output_tokens_per_call`` would read as a reply of no length.
    """
    with pytest.raises(ValueError, match=expected):
        _marking_assumptions(broken)


def test_perception_settings_that_are_not_a_block_are_refused():
    with pytest.raises(ValueError, match="name each kind of perception"):
        _marking_assumptions("look at everything")


def test_the_committed_plan_measures_pictures_and_leaves_sound_blank(plan):
    """What the plan claims about perception, in the plan's own words.

    How many renders is the cap marking is configured to allow, and is read
    from those settings rather than restated, because a plan that keeps its own
    copy of a ceiling stops being a ceiling the moment the real one moves. The
    two token figures come from the largest call every marking run this
    repository has committed. The sound numbers are blank because that model
    has never been called, so there is nothing to draw on — and a blank is a
    refusal while a zero would be a claim that the calls are free.
    """
    perception = plan["cost"]["assumptions"]["grading_perception"]

    assert perception["vision"]["model"] == "gpt-5.4"
    assert perception["vision"]["calls_per_task"] == CONFIGURED_VISUAL_CALL_CAP
    assert perception["vision"]["calls_per_task"] == 112
    assert perception["vision"]["input_tokens_per_call"] == 24000
    assert perception["vision"]["output_tokens_per_call"] == 4000

    assert perception["audio"]["model"] == UNPRICED_SOUND_MODEL
    assert perception["audio"]["input_tokens_per_call"] is None
    assert perception["audio"]["output_tokens_per_call"] is None


def test_a_missing_approved_amount_is_a_refusal(plan, catalog):
    """Removing the approved amount must stop the run, whatever else is right.

    The committed plan now records an approved amount, so this clears it on
    purpose rather than relying on it being absent.
    """
    plan = _approved(plan, None)

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "largest amount that may be spent" in note
        for note in result.all_problems
    )


def _no_ceiling_can_be_worked_out(plan):
    """Break the sums the ceiling is built from, leaving the amount readable.

    The point of the tests below is the amount, not the assumptions: this makes
    the ceiling half of the comparison fail so that the amount half is left on
    its own, which is the situation the amount used to go unchecked in.
    """
    plan = copy.deepcopy(plan)
    plan["cost"]["assumptions"] = {"input_tokens_per_task": "not a number"}
    return plan


@pytest.mark.parametrize(
    "amount, expected",
    [
        (None, "no ceiling could be worked out"),
        (-12, "must be greater than zero"),
        ("lots", "is not a number"),
        (float("inf"), "is not a definite amount of money"),
        (float("nan"), "is not a definite amount of money"),
    ],
)
def test_the_amount_is_still_checked_when_no_ceiling_could_be_worked_out(
    plan, amount, expected
):
    """A failure in one half of the sum must not silence the other half.

    The approved amount is normally judged on the way to comparing it against
    the worked-out ceiling. When the ceiling cannot be worked out at all, that
    comparison never happens — and with it went the only check that a policy
    which stops runs on cost has a usable figure to stop at. A plan saying
    "stop on cost" with no amount, a negative one, or one that is not a
    definite amount of money must not reach a run place.
    """
    broken = _no_ceiling_can_be_worked_out(_approved(plan, amount))

    result = _ready_preflight(broken)

    assert result.cost is None, "the ceiling was supposed to fail here"
    assert result.may_start is False
    assert any(expected in note for note in result.all_problems), (
        result.all_problems
    )


@pytest.mark.parametrize("amount", (float("inf"), float("nan")))
def test_an_amount_that_is_not_a_definite_sum_of_money_is_refused(plan, amount):
    """``.inf`` and ``.nan`` are ordinary YAML, so both arrive as real values.

    Neither is an amount anyone approved. An infinite limit permits every bill
    a run could produce, and comparing a not-a-number against zero raises
    instead of answering, which used to end the check with an uncaught error
    rather than a refusal. Both are refused by name.
    """
    result = _ready_preflight(_approved(plan, amount))

    assert result.cost is not None, "the ceiling was supposed to work here"
    assert result.may_start is False
    assert any(
        "is not a definite amount of money" in note
        for note in result.all_problems
    ), result.all_problems


def test_an_unpriced_model_is_still_unpriced_when_the_amount_is_refused(plan):
    """Refusing the amount must not turn a missing price into nothing owed."""
    result = _ready_preflight(_approved(plan, float("inf")))

    assert result.cost is not None
    assert result.cost.unpriced_models, "the sound model has no price"
    assert result.cost.total_usd > 0


def test_the_committed_plan_records_the_owner_decision_without_a_balance(plan):
    """The old per-run dollar refusal is replaced by the owner's decision.

    The decision is the two flags. How much credit the account has left is not
    part of it, is not written here, and no check reads it.
    """
    cost = plan["cost"]
    approval = cost["owner_approval"]

    assert cost["policy"] == COST_POLICY_RECORD_ONLY
    assert cost["approved_maximum_usd"] is None
    assert approval == {
        "approved_on": "2026-08-28",
        "paid_model_calls": True,
        "unpriced_audio_measurement": True,
    }


def test_record_only_cost_findings_do_not_block_the_owner_approved_run(plan):
    environ = dict(FULLY_READY_ENVIRON)
    environ.pop("EXECUTION_COMPARISON_PAID_RUN_APPROVED")
    result = _ready_preflight(plan, environ=environ)

    assert result.cost_policy == COST_POLICY_RECORD_ONLY
    assert result.cost_findings
    assert set(result.cost_findings).isdisjoint(result.all_problems)
    assert result.readiness.paid_model_calls_approved is True
    # Nothing about money is left in ``all_problems`` — that is what this test
    # is about. What is left is the absent input files and nothing else. It said
    # "and the one finding that the three run places are not asked the same
    # thing" until 2026-09-06, when that finding was fixed rather than waved
    # through; a cost policy could never have waved it through either.
    assert all(
        note in result.missing_input_file_problems for note in result.all_problems
    ), result.all_problems


@pytest.mark.parametrize(
    "field",
    ("paid_model_calls", "unpriced_audio_measurement"),
)
def test_record_only_cost_policy_requires_the_exact_owner_approval(plan, field):
    plan = copy.deepcopy(plan)
    plan["cost"]["owner_approval"][field] = False

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(field in note or "audio model" in note for note in result.all_problems)


@pytest.mark.parametrize("credit", (None, 0, -1, "not-a-number", 1234.56))
def test_a_monthly_credit_written_into_the_plan_is_refused(plan, credit):
    """Refused rather than ignored, and refused whatever the value is.

    A positive figure is in the list on purpose, and it is a made-up one. The
    objection is not that the number is wrong, it is that an account's
    remaining balance is account information, this file is published, and
    nothing here reads it. A number left sitting unread would be an invitation
    to keep it up to date, so no real balance is written even in a test.
    """
    plan = copy.deepcopy(plan)
    plan["cost"]["owner_approval"]["available_monthly_credit_usd"] = credit

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "available_monthly_credit_usd" in note and "must not be written" in note
        for note in result.all_problems
    )


def test_record_only_starts_from_two_flags_with_no_amount_and_no_balance(plan):
    """The whole point of the policy: approval is flags, not money.

    Neither an approved per-run amount nor an account balance is written, and
    the cost block contributes nothing to the reasons this plan cannot start.
    """
    plan = copy.deepcopy(plan)

    result = _ready_preflight(plan)

    assert result.cost_policy == COST_POLICY_RECORD_ONLY
    assert plan["cost"]["approved_maximum_usd"] is None
    assert "available_monthly_credit_usd" not in plan["cost"]["owner_approval"]
    assert not any(
        "largest amount that may be spent" in note
        or "available_monthly_credit_usd" in note
        for note in result.all_problems
    ), result.all_problems


def test_record_only_cost_policy_does_not_hide_a_missing_grading_config(plan):
    plan = copy.deepcopy(plan)
    plan.pop("grading_config")

    result = _ready_preflight(plan)

    matching = [
        note for note in result.all_problems if "names no marking settings" in note
    ]
    assert len(matching) == 1
    assert matching[0] not in result.cost_findings


def test_an_unknown_cost_policy_is_refused(plan):
    plan = copy.deepcopy(plan)
    plan["cost"]["policy"] = "ignore_everything"

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any("cost.policy" in note for note in result.all_problems)


def test_an_approved_amount_below_the_ceiling_is_a_refusal(plan):
    result = _ready_preflight(_approved(plan, "0.01"))
    assert result.may_start is False
    assert any("is above the" in note for note in result.all_problems)


def test_an_approved_amount_that_covers_the_ceiling_is_accepted(plan):
    result = _ready_preflight(_approved(plan))
    assert _apart_from_the_sound_model_and_absent_inputs(result) == []
    assert not any("is above the" in note for note in result.all_problems)


def test_the_worked_out_ceiling_is_reported_in_full(plan):
    result = _ready_preflight(_approved(plan))
    assert result.cost is not None
    written = result.cost.as_dict()
    assert {entry["environment"] for entry in written["environments"]} == set(
        COMPARABLE_ENVIRONMENTS
    )
    assert Decimal(written["most_the_whole_thing_could_cost_usd"]) > 0
    assert written["grading"]["most_model_calls"] > 0


def test_grading_is_counted_once_for_every_run_place(plan, catalog):
    """Each run place produces its own answers, so each is marked separately.

    How many marking calls one scoring line costs is read from the plan rather
    than assumed to be one. This test is about the multiplication by run place;
    pinning the other number here would make it fail whenever that number is
    corrected, for a reason it is not about.
    """
    result = _ready_preflight(_approved(plan))
    by_id = catalog.by_task_id()
    scoring_lines = sum(
        by_id[task_id].rubric_item_count for task_id in EXPECTED_ADVANCE_CHECK_TASKS
    )
    calls_per_line = plan["cost"]["assumptions"]["grading_calls_per_rubric_item"]
    assert result.cost is not None
    assert result.cost.grading_model_calls == int(
        Decimal(str(calls_per_line)) * scoring_lines * len(COMPARABLE_ENVIRONMENTS)
    )


def test_marking_a_scoring_line_is_counted_at_the_settings_limit(plan):
    """The plan counts every turn the marking settings allow, not the usual one.

    It used to say one call per scoring line, taken from what three recorded
    runs happened to average. The settings allow ten tool rounds and a final
    answer, so the bill can be eleven times what that assumed.
    """
    assert plan["cost"]["assumptions"]["grading_calls_per_rubric_item"] == 11.0
    assert plan["cost"]["assumptions"]["grading_output_tokens_per_call"] == 2400


def test_the_cost_sum_uses_the_wording_that_is_actually_sent(plan):
    plan = _approved(plan)
    plan["cost"]["assumptions"]["instruction_character_count"] = 1

    result = _ready_preflight(plan)

    assert any("but " in note and "sends" in note for note in result.all_problems)


# ── The check refuses every way the comparison could go wrong ─────────────


def test_no_approval_on_record_blocks_every_run_place(plan):
    result = _ready_preflight(_approved(plan), environ={})
    assert result.may_start is False
    assert set(result.readiness.blocked_environments) == set(
        COMPARABLE_ENVIRONMENTS
    )


def test_a_run_place_that_uses_a_different_deployment_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["docker_container"] = {
        "deployment": "gpt-5.4-mini"
    }

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any("deployment" in note for note in result.all_problems)


def test_a_run_place_that_uses_a_different_model_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["azure_code_interpreter"] = {
        "resolved_model": "gpt-5.4-mini"
    }

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_run_place_allowed_to_change_model_on_its_own_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["shared"]["automatic_model_switch_allowed"] = True

    result = _ready_preflight(plan)

    assert result.may_start is False
    # The reason has to reach the reader, not only the verdict. This one is
    # found by the readiness check rather than by the envelope check, so it
    # only appears if the two lists are shown together.
    assert any(
        "switching to another" in note for note in result.all_problems
    )


def test_every_refusal_says_why(plan):
    """A refusal with no stated reason is not usable by whoever has to fix it."""
    plan = _approved(plan)
    plan["model_run_conditions"]["shared"]["automatic_model_switch_allowed"] = True

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert result.all_problems
    assert result.as_dict()["problems"] == result.all_problems


def test_a_run_place_with_different_wording_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["host_python_process"] = {
        "system_instruction": "Something else entirely.\n"
    }

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_run_place_with_a_different_task_list_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["docker_container"] = {
        "task_ids": list(EXPECTED_ADVANCE_CHECK_TASKS[:4])
    }

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_switching_self_review_on_for_this_comparison_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["shared"]["self_review_enabled"] = True
    plan["model_run_conditions"]["shared"]["self_review_max_attempts"] = 2

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_run_place_this_repository_cannot_score_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["agentic_sandbox_v2"] = {}

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "cannot run a scored comparison" in note for note in result.problems
    )


def test_a_plan_written_for_another_version_is_refused(plan):
    plan = _approved(plan)
    plan["plan_version"] = "something-else"

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_missing_azure_connection_setting_blocks_that_run_place(plan):
    result = _ready_preflight(_approved(plan), azure_route_profile=None)

    assert result.may_start is False
    assert "azure_code_interpreter" in result.readiness.blocked_environments


def test_a_missing_docker_service_blocks_that_run_place(plan):
    result = _ready_preflight(_approved(plan), docker_daemon_available=False)

    assert result.may_start is False
    assert "docker_container" in result.readiness.blocked_environments


def test_a_missing_container_image_blocks_that_run_place(plan):
    result = _ready_preflight(_approved(plan), docker_image_available=False)

    assert result.may_start is False
    assert "docker_container" in result.readiness.blocked_environments


def test_an_experiment_settings_file_that_drifts_is_refused(plan, tmp_path):
    plan = _approved(plan)
    root = tmp_path / "batch-runner"
    (root / "experiments" / "execution_envelope").mkdir(parents=True)
    for environment, relative in plan["experiment_files"].items():
        settings = yaml.safe_load(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8")
        )
        if environment == "host_python_process":
            settings["condition_a"]["model"]["deployment"] = "gpt-5.4-mini"
        (root / relative).write_text(
            yaml.safe_dump(settings, sort_keys=False), encoding="utf-8"
        )

    result = run_envelope_preflight(
        plan,
        root=root,
        docker_daemon_available=True,
        docker_image_available=True,
        azure_route_profile="project-ci",
        environ=FULLY_READY_ENVIRON,
    )

    assert result.may_start is False
    assert any("gpt-5.4-mini" in note for note in result.all_problems)


def test_a_missing_experiment_settings_file_is_refused(plan, tmp_path):
    plan = _approved(plan)
    root = tmp_path / "batch-runner"
    (root / "experiments" / "execution_envelope").mkdir(parents=True)

    result = run_envelope_preflight(
        plan,
        root=root,
        docker_daemon_available=True,
        docker_image_available=True,
        azure_route_profile="project-ci",
        environ=FULLY_READY_ENVIRON,
    )

    assert result.may_start is False
    assert any("does not exist" in note for note in result.all_problems)


def _preflight_with_edited_settings(plan, tmp_path, environment, edit):
    """Copy the three settings files, change one, and run the check on them."""
    root = tmp_path / "batch-runner"
    (root / "experiments" / "execution_envelope").mkdir(parents=True)
    for name, relative in plan["experiment_files"].items():
        settings = yaml.safe_load(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8")
        )
        if name == environment:
            edit(settings)
        (root / relative).write_text(
            yaml.safe_dump(settings, sort_keys=False), encoding="utf-8"
        )
    return run_envelope_preflight(
        plan,
        root=root,
        docker_daemon_available=True,
        docker_image_available=True,
        azure_route_profile="project-ci",
        environ=FULLY_READY_ENVIRON,
    )


def test_a_settings_file_that_omits_the_answer_length_cap_is_refused(
    plan, tmp_path
):
    """Silence is not agreement: a missing cap falls back to a different one."""

    def drop_the_cap(settings):
        settings["execution"].pop("tokens", None)

    result = _preflight_with_edited_settings(
        _approved(plan), tmp_path, "host_python_process", drop_the_cap
    )

    assert result.may_start is False
    assert any(
        "does not say how much the model may write" in note
        for note in result.all_problems
    )


@pytest.mark.parametrize(
    "setting, value",
    [
        ("reasoning_effort", "high"),
        ("temperature", 0.7),
        ("seed", 99),
    ],
)
def test_run_places_that_disagree_on_an_unfixed_setting_are_refused(
    plan, tmp_path, setting, value
):
    """A setting the plan never mentions still has to be the same everywhere.

    The refusal names the setting by its full key path. A bare name stopped
    being enough once the reviewer's settings were compared too, since both it
    and the model have a ``model`` of their own.
    """

    def change_it(settings):
        settings["condition_a"]["model"][setting] = value

    result = _preflight_with_edited_settings(
        _approved(plan), tmp_path, "docker_container", change_it
    )

    assert result.may_start is False
    assert any(
        f"(condition_a.model.{setting})" in note for note in result.all_problems
    ), result.all_problems


def test_the_three_settings_files_agree_on_the_unfixed_settings(plan):
    """Today they do, and nothing may quietly change that."""

    result = _ready_preflight(_approved(plan))

    assert _apart_from_the_sound_model_and_absent_inputs(result) == []


def test_the_committed_files_agree_with_the_committed_plan(plan):
    """The three settings files and the plan say the same thing today."""
    result = _ready_preflight(_approved(plan))
    assert _apart_from_the_sound_model_and_absent_inputs(result) == []


def test_the_plan_names_the_version_this_check_reads(plan):
    assert plan["plan_version"] == PLAN_VERSION


def test_the_two_comparisons_keep_separate_score_tables(plan):
    boards = plan["scoreboards"]
    assert set(boards) == {"same_generated_code_rerun", "tool_built_in_features"}
    for name, board in boards.items():
        assert board["comparison"] == name


# ── The Agentic Sandbox V2 guards are still shut ──────────────────────────


def test_the_agentic_sandbox_v2_guards_are_not_worked_around(plan):
    """The check exercises all three guards; none may have been opened."""
    result = _ready_preflight(_approved(plan))
    assert _apart_from_the_sound_model_and_absent_inputs(result) == []
    assert result.readiness.status_of("agentic_sandbox_v2") == "structure_check_only"


def test_the_codex_run_place_is_still_reported_as_absent(plan):
    result = _ready_preflight(_approved(plan))
    assert (
        result.readiness.status_of("codex_built_in_agent")
        == "not_implemented_in_this_repository"
    )


def test_neither_absent_run_place_is_quietly_replaced(plan):
    """An empty slot stays empty; it is never filled with a working place."""
    result = _ready_preflight(_approved(plan))
    assert set(result.readiness.compared_environments) == set(
        COMPARABLE_ENVIRONMENTS
    )
    assert "agentic_sandbox_v2" not in result.readiness.compared_environments
    assert "codex_built_in_agent" not in result.readiness.compared_environments


# ── The committed catalogue still describes the pinned dataset ────────────


def test_the_committed_catalogue_is_internally_consistent(catalog):
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert raw["dataset_revision"] == DATASET_REVISION
    assert len(raw["tasks"]) == FULL_RUN_TASK_COUNT
    assert [entry["task_id"] for entry in raw["tasks"]] == sorted(
        entry["task_id"] for entry in raw["tasks"]
    )
    for entry in raw["tasks"]:
        assert len(entry["prompt_sha256"]) == 64
        assert entry["reference_file_count"] == len(entry["reference_file_paths"])


# ── The tool a person actually runs is present and refuses today ──────────


CHECK_SCRIPT = (
    BATCH_RUNNER_ROOT / "scripts" / "check_execution_envelope_advance_check.py"
)
CATALOG_SCRIPT = (
    BATCH_RUNNER_ROOT / "scripts" / "build_gdpval_task_catalog.py"
)


@pytest.mark.parametrize("script", [CHECK_SCRIPT, CATALOG_SCRIPT])
def test_the_scripts_are_in_the_repository(script):
    """A check nobody can run is not a check.

    `batch-runner/scripts/` is ignored by default with a per-file allow list,
    so a new tool there is invisible in a fresh clone unless it is added to
    that list. This fails if that step is ever missed.
    """
    assert script.is_file(), f"{script.name} is missing from a fresh checkout"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(script)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{script.name} exists here but git does not track it. Add it to the "
        "allow list in .gitignore under batch-runner/scripts/."
    )


def test_the_check_refuses_today_and_says_why():
    """Run the tool exactly as a person would, and require a refusal.

    The ordinary checkout still cannot reach Azure. Cost findings remain
    visible, while the committed owner approval satisfies the paid-run switch
    and keeps those findings out of the refusal.
    """
    finished = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT)],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **{
                key: value
                for key, value in os.environ.items()
                if key
                not in {
                    "AZURE_AI_ROUTE_PROFILE",
                    "FOUNDRY_PROJECT_ENDPOINT",
                    "AZURE_OPENAI_V1_ENDPOINT",
                }
            },
            "EXECUTION_COMPARISON_PAID_RUN_APPROVED": "",
        },
    )

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "no model was called" in finished.stdout
    assert "AZURE_AI_ROUTE_PROFILE is not set" in finished.stdout
    assert "FOUNDRY_PROJECT_ENDPOINT is not set" in finished.stdout
    assert "record findings only" in finished.stdout
    assert "cost findings to measure and review after the run" in finished.stdout
    assert "monthly credit" not in finished.stdout


# ── The Azure run place must reach the deployment that was pinned ─────────
#
# A deployment name does not identify a deployment. The tenant this comparison
# was first attempted from held two Azure AI Foundry accounts that each exposed
# a deployment named exactly "gpt-5.4". Pinning the name alone would let the
# comparison run against a resource nobody intended and report success.


def _environ_with(**overrides):
    settings = dict(FULLY_READY_ENVIRON)
    for key, value in overrides.items():
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = value
    return settings


def test_the_plan_pins_the_azure_account_and_project(plan):
    pinned = plan["azure_connection"]
    assert pinned["account"] == PINNED_AZURE_ACCOUNT
    assert pinned["project"] == PINNED_AZURE_PROJECT
    assert pinned["route_profile"] == "project-ci"


def test_a_correctly_pointed_azure_setup_is_accepted(plan):
    result = _ready_preflight(_approved(plan))

    assert result.azure is not None
    assert result.azure.problems == []
    assert result.azure.observed_account == PINNED_AZURE_ACCOUNT
    assert result.azure.observed_project == PINNED_AZURE_PROJECT
    assert _apart_from_the_sound_model_and_absent_inputs(result) == []
    assert result.readiness.ready is True


def test_the_same_deployment_name_on_another_account_is_refused(plan):
    """The exact hole this block was added to close.

    The settings are well formed, the route is right, and the deployment name
    is unchanged. Only the account differs — which is precisely the case that
    used to pass.
    """
    other = (
        "https://some-other-account.services.ai.azure.com"
        f"/api/projects/{PINNED_AZURE_PROJECT}"
    )
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(FOUNDRY_PROJECT_ENDPOINT=other),
    )

    assert result.may_start is False
    assert any(
        "is not unique across accounts" in note for note in result.all_problems
    )


def test_another_project_on_the_right_account_is_refused(plan):
    other = (
        f"https://{PINNED_AZURE_ACCOUNT}.services.ai.azure.com"
        "/api/projects/some-other-project"
    )
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(FOUNDRY_PROJECT_ENDPOINT=other),
    )

    assert result.may_start is False
    assert any("names the project" in note for note in result.all_problems)


def test_a_missing_project_address_says_what_it_should_look_like(plan):
    result = _ready_preflight(
        _approved(plan), environ=_environ_with(FOUNDRY_PROJECT_ENDPOINT=None)
    )

    assert result.may_start is False
    assert any(
        PINNED_AZURE_ACCOUNT in note and "services.ai.azure.com" in note
        for note in result.all_problems
    )


def test_a_missing_route_profile_is_told_apart_from_a_wrong_one(plan):
    """"Not set" and "set to the wrong thing" need different fixes."""
    missing = _ready_preflight(
        _approved(plan), environ=_environ_with(AZURE_AI_ROUTE_PROFILE=None)
    )
    wrong = _ready_preflight(
        _approved(plan),
        environ=_environ_with(AZURE_AI_ROUTE_PROFILE="direct-v1"),
    )

    assert any("is not set" in note for note in missing.all_problems)
    assert any("'direct-v1'" in note for note in wrong.all_problems)


def test_the_deprecated_endpoint_setting_is_refused(plan):
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(
            AZURE_OPENAI_ENDPOINT="https://something.openai.azure.com/"
        ),
    )

    assert result.may_start is False
    assert any(
        "does not say which kind of endpoint" in note
        for note in result.all_problems
    )


@pytest.mark.parametrize(
    "variable", ["AZURE_OPENAI_API_KEY", "AZURE_CLIENT_SECRET"]
)
def test_a_fixed_credential_is_refused_up_front(plan, variable):
    """Say so during the free check, not after the run has been scheduled."""
    result = _ready_preflight(
        _approved(plan), environ=_environ_with(**{variable: "value-not-read"})
    )

    assert result.may_start is False
    assert any(variable in note for note in result.all_problems)


def test_a_direct_address_on_another_account_is_refused(plan):
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(
            AZURE_OPENAI_V1_ENDPOINT=(
                "https://some-other-account.services.ai.azure.com/openai/v1/"
            )
        ),
    )

    assert result.may_start is False
    assert any(
        "AZURE_OPENAI_V1_ENDPOINT" in note for note in result.all_problems
    )


def test_a_plan_that_forgets_to_pin_the_account_is_refused(plan):
    plan = _approved(plan)
    plan.pop("azure_connection")

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "not unique across accounts" in note for note in result.all_problems
    )


def test_the_azure_check_is_skipped_when_azure_does_not_take_part(plan):
    """A plan without the Azure run place has no Azure resource to get wrong."""
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"].pop("azure_code_interpreter")
    plan["experiment_files"].pop("azure_code_interpreter")
    plan.pop("azure_connection")

    result = _ready_preflight(plan, environ=_environ_with(
        AZURE_AI_ROUTE_PROFILE=None, FOUNDRY_PROJECT_ENDPOINT=None
    ))

    assert result.azure is None
    assert not any("AZURE" in note for note in result.all_problems)


# ── The written specifications must survive a fresh checkout ─────────────
#
# Both `batch-runner/scripts/` and `tasks/0822_saturday/` are ignored by
# default with a per-file allow list. A document added to either without being
# added to that list is invisible to anyone who clones the repository, which
# makes it useless exactly when someone needs it.

SPECIFICATION_FILES = (
    "tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md",
    "tasks/0822_saturday/TASK_PIN_AZURE_RESOURCE_IDENTITY.md",
    "tasks/0822_saturday/TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md",
    "tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md",
)


@pytest.mark.parametrize("relative", SPECIFICATION_FILES)
def test_the_specifications_are_in_the_repository(relative):
    path = REPOSITORY_ROOT / relative
    assert path.is_file(), f"{relative} is missing"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{relative} exists here but git does not track it, so a fresh clone "
        "would not have it. Add it to the allow list in .gitignore."
    )


# ── What the comparison does not control ─────────────────────────────────
#
# Every other check in this file asks whether the comparison may start. These
# ask the different question the result has to answer afterwards: with all of
# them passed, is a difference in the results the run place's? For these three
# places the answer is no, and the check has to say so rather than let a clean
# pass be read as a yes.


def test_a_clean_pass_still_refuses_the_pure_run_place_verdict(plan):
    result = _ready_preflight(_approved(plan))

    assert result.pure_run_place_effect_is_measurable is False, (
        "every setting matching is not the same as only the run place "
        "differing, and the second is the claim a reader takes away"
    )
    assert result.uncontrolled_differences


def test_the_differences_named_are_the_ones_the_run_places_carry(plan):
    """Read from the shared module, not restated here.

    A second list would drift from the first, and the report would state one
    while the runners were built against the other.
    """
    result = _ready_preflight(_approved(plan))
    expected = residual_differences_for(sorted(COMPARABLE_ENVIRONMENTS))

    assert result.uncontrolled_differences == list(expected)
    for entry in result.uncontrolled_differences:
        assert set(entry.run_places) <= set(COMPARABLE_ENVIRONMENTS), entry.what


def test_the_azure_time_limit_is_among_them(plan):
    """The one found by capturing a real request rather than by reading a plan.

    ``CodeInterpreterRunner`` is given no timeout — the service runs its own
    container on its own clock — while the other two are given the experiment
    file's 1200 seconds. The plan files say 1200 three times, so only something
    that reads the sent request finds this.
    """
    result = _ready_preflight(_approved(plan))
    named = {entry.what: entry for entry in result.uncontrolled_differences}

    assert "the per-task time limit" in named, sorted(named)
    assert named["the per-task time limit"].run_places == (
        "azure_code_interpreter",
    )


def test_every_uncontrolled_difference_is_printed_with_its_consequence(plan):
    """A list of headings would let a reader skip what each one could do."""
    result = _ready_preflight(_approved(plan))
    printed = "\n".join(describe_uncontrolled_differences(result))

    assert "may pass and a difference in results still not be" in printed
    for entry in result.uncontrolled_differences:
        assert entry.what in printed
        assert entry.why_it_stays in printed
        assert entry.what_it_could_do_to_a_result in printed


def test_a_comparison_of_two_places_is_not_charged_for_azures_differences(plan):
    """The container and the host share an API family; Azure's entries are not theirs.

    The plan is cut down to two run places rather than the list being filtered
    afterwards, so what is exercised is the path a two-place comparison would
    really take. Whether such a plan passes its other checks is not asked here
    — only which differences it is told it carries.
    """
    two_of_them = copy.deepcopy(_approved(plan))
    by_environment = two_of_them["model_run_conditions"]["by_environment"]
    del by_environment["azure_code_interpreter"]
    assert sorted(by_environment) == ["docker_container", "host_python_process"]

    result = _ready_preflight(two_of_them)

    named = {entry.what for entry in result.uncontrolled_differences}
    assert "the API the request is sent on" not in named, named
    assert "the per-task time limit" not in named, named
    assert result.pure_run_place_effect_is_measurable is False, (
        "the container's isolation and its output check are still uncontrolled"
    )


def test_the_summary_says_so_when_nothing_is_uncontrolled(plan):
    """The honest wording for the other case, so it is not left to a reader.

    Reached by replacing the list rather than by finding two run places that
    really do differ in nothing, because none exist here — which is the point.
    """
    result = replace(_ready_preflight(_approved(plan)), uncontrolled_differences=[])

    assert result.pure_run_place_effect_is_measurable is True
    printed = "\n".join(describe_uncontrolled_differences(result))
    assert "none recorded for these run places" in printed
