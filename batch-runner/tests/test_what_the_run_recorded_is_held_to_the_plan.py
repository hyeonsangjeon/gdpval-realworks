"""What the run recorded, held to the plan and to the other run places.

``core/execution_environment_readiness.py`` reads the plan and checks it agrees
with itself. These tests cover the other half — ``core.execution_envelope_observed``
— which reads what a finished attempt recorded and holds *that* against the
plan's claims.

The failure this guards against is the quiet one. A run place can be pinned to a
model in the plan, pass every readiness check, and be served by something else;
a run place can load a different prompt file and still produce a plausible
answer. Neither shows up in a plan that only reads itself. Both show up in the
provider's echoed-back model name and the digest of the text that really left
the process, which is what these checks compare.

Every test below is arithmetic over recorded values — no API, no network.
"""

from __future__ import annotations

import pytest

from core.execution_envelope_observed import (
    API_FAMILY_CHAT_COMPLETIONS,
    API_FAMILY_RESPONSES,
    DECLARED_ABSENT_BY_RUN_PLACE,
    MAY_DIFFER_AND_IS_DECLARED,
    MUST_AGREE_ACROSS_RUN_PLACES,
    ObservedRunPlace,
    check_observations_agree,
    check_observations_match_the_plan,
    describe_observations,
    observed_from_record,
)
from core.shared_first_request import (
    UNCONTROLLED_DIFFERENCES,
    residual_differences_for,
)


def _record(**overrides):
    """A complete run record, with only what a test cares about changed."""
    record = {
        "provider": "azure",
        "deployment": "gpt-5-2-chat",
        "requested_model": "gpt-5.2-chat",
        "answering_model": "gpt-5.2-chat-2026-04-01",
        "api_family": API_FAMILY_CHAT_COMPLETIONS,
        "api_version": "2025-03-01-preview",
        "prompt_name": "execution_envelope_shared",
        "first_request_fingerprint": "0f1e2d3c4b5a6978",
        "max_completion_tokens": 16000,
        "per_task_timeout_seconds": 900,
        "max_attempts": 3,
        "task_ids": ["t1", "t2", "t3", "t4", "t5"],
        "input_file_versions": {"budget.xlsx": "sha256:aaaa", "brief.pdf": "sha256:bbbb"},
    }
    record.update(overrides)
    return record


def _three_agreeing():
    return [
        observed_from_record("host_python_process", _record()),
        observed_from_record("docker_container", _record()),
        observed_from_record(
            "azure_code_interpreter",
            _record(api_family=API_FAMILY_RESPONSES, api_version="2025-04-01-preview"),
        ),
    ]


# ─── reading a record ────────────────────────────────────────────────────────


def test_a_complete_record_reads_with_nothing_unreadable():
    place = observed_from_record("host_python_process", _record())
    assert place.unreadable == {}
    assert place.answering_model == "gpt-5.2-chat-2026-04-01"
    assert place.max_completion_tokens == 16000
    assert place.task_ids == ("t1", "t2", "t3", "t4", "t5")


@pytest.mark.parametrize(
    "missing",
    sorted(
        {
            "provider",
            "deployment",
            "answering_model",
            "prompt_name",
            "first_request_fingerprint",
            "max_completion_tokens",
            "per_task_timeout_seconds",
            "max_attempts",
        }
    ),
)
def test_a_field_that_is_absent_becomes_a_reason_not_a_none(missing):
    """An absent field must say so, because ``None`` reads as agreement.

    The comparison loop skips ``None`` — otherwise a run place that recorded
    nothing would be counted as matching every other place. That skip is only
    safe because the same field is already a problem for being unreadable, and
    this is the test that keeps the two in step.
    """
    record = _record()
    del record[missing]
    place = observed_from_record("host_python_process", record)

    assert missing in place.unreadable
    assert getattr(place, missing) is None

    problems = check_observations_agree([place, observed_from_record("docker_container", _record())])
    assert any(missing in problem for problem in problems), problems


@pytest.mark.parametrize("empty", ["", "   "])
def test_a_blank_string_is_not_a_value(empty):
    place = observed_from_record("host_python_process", _record(answering_model=empty))
    assert place.answering_model is None
    assert "answering_model" in place.unreadable


@pytest.mark.parametrize("not_a_number", [None, "16000", 16000.0, True, [16000]])
def test_a_token_cap_that_is_not_a_whole_number_is_unreadable(not_a_number):
    """``True`` is in this list on purpose: ``isinstance(True, int)`` is true.

    A recorder that wrote a flag where a cap belongs would otherwise compare as
    ``1`` and match another place that also wrote a flag.
    """
    place = observed_from_record(
        "host_python_process", _record(max_completion_tokens=not_a_number)
    )
    assert place.max_completion_tokens is None
    assert "max_completion_tokens" in place.unreadable


def test_a_caller_supplied_reason_survives_reading():
    """A run place that knows why a field is missing keeps its own wording."""
    record = _record()
    del record["answering_model"]
    record["unreadable"] = {
        "answering_model": "this API returns no model name in its response body"
    }
    place = observed_from_record("azure_code_interpreter", record)
    assert place.unreadable["answering_model"].startswith("this API returns no model")


def test_a_record_cannot_both_have_a_value_and_say_it_is_unreadable():
    with pytest.raises(ValueError, match="one of the two is wrong|One of the two is wrong"):
        ObservedRunPlace(
            run_place="host_python_process",
            answering_model="gpt-5.2-chat",
            unreadable={"answering_model": "could not be read"},
        )


def test_an_api_family_this_repository_does_not_know_is_refused():
    with pytest.raises(ValueError, match="not one of"):
        ObservedRunPlace(run_place="host_python_process", api_family="assistants_v1")


# ─── holding the run places to each other ────────────────────────────────────


def test_three_agreeing_run_places_raise_nothing():
    assert check_observations_agree(_three_agreeing()) == []


def test_one_run_place_on_its_own_is_not_a_passed_comparison():
    """A single record must not read as "they all agree"."""
    problems = check_observations_agree([observed_from_record("host_python_process", _record())])
    assert problems
    assert "at least two" in problems[0]


def test_no_run_places_at_all_is_not_a_passed_comparison():
    assert check_observations_agree([]) != []


def test_a_model_the_provider_swapped_is_caught():
    """The one substitution a plan cannot catch by reading itself."""
    observed = _three_agreeing()
    swapped = observed_from_record(
        "docker_container", _record(answering_model="gpt-5.2-chat-2026-01-15")
    )
    problems = check_observations_agree([observed[0], swapped, observed[2]])
    assert any("answering_model" in problem for problem in problems), problems
    assert any("2026-01-15" in problem for problem in problems), problems


def test_a_different_first_request_is_caught_even_when_everything_else_matches():
    """The fingerprint is the field nothing else stands in for.

    Same provider, same deployment, same answering model, same prompt file
    name — and a different question asked. Only the digest of the text that
    left the process shows it.
    """
    observed = _three_agreeing()
    reworded = observed_from_record(
        "docker_container", _record(first_request_fingerprint="ffffffffffffffff")
    )
    problems = check_observations_agree([observed[0], reworded, observed[2]])
    assert len(problems) == 1, problems
    assert "first_request_fingerprint" in problems[0]


def test_a_different_prompt_file_is_caught():
    observed = _three_agreeing()
    other_file = observed_from_record("docker_container", _record(prompt_name="sandbox_default"))
    problems = check_observations_agree([observed[0], other_file, observed[2]])
    assert any("prompt_name" in problem for problem in problems), problems


@pytest.mark.parametrize(
    "field_name,changed",
    [
        ("max_completion_tokens", 8000),
        ("per_task_timeout_seconds", 300),
        ("max_attempts", 1),
    ],
)
def test_unequal_token_time_and_retry_settings_are_caught(field_name, changed):
    """A place that was cut off, timed out or given fewer tries did not do worse."""
    observed = _three_agreeing()
    tightened = observed_from_record("docker_container", _record(**{field_name: changed}))
    problems = check_observations_agree([observed[0], tightened, observed[2]])
    assert any(field_name in problem for problem in problems), problems


def test_the_api_family_and_version_are_allowed_to_differ():
    """Azure's Responses API is a declared uncontrolled difference, not a fault.

    The three-place set built above already differs on both fields. If either
    were held to, the agreeing case above could not be empty — so this test
    states the exemption rather than leaving it as an accident of the data.
    """
    for field_name in MAY_DIFFER_AND_IS_DECLARED:
        assert field_name not in MUST_AGREE_ACROSS_RUN_PLACES


def test_every_allowed_difference_is_one_the_shared_module_already_declared():
    """Nothing is exempt here that is not named in the uncontrolled list.

    Two modules with two separate ideas of what may differ is how a difference
    ends up excused in one place and unmentioned in the other.
    """
    declared = {difference.what for difference in UNCONTROLLED_DIFFERENCES}
    for field_name, points_at in MAY_DIFFER_AND_IS_DECLARED.items():
        assert points_at in declared, (field_name, points_at, sorted(declared))


def test_every_field_held_to_has_a_reason_a_reader_can_check():
    for field_name, why in MUST_AGREE_ACROSS_RUN_PLACES.items():
        assert hasattr(ObservedRunPlace(run_place="x"), field_name), field_name
        assert len(why) > 30, (field_name, why)


# ─── a field one run place has no setting for ────────────────────────────────


def test_azure_recording_no_time_limit_is_not_counted_as_a_reading_failure():
    """Nothing in this repository sets a per-task limit on the code interpreter.

    ``CodeInterpreterRunner`` takes no timeout and ``TaskExecutor`` passes it
    none; the service runs its own container on its own clock. So the record
    holds no number, and that is the truth rather than a gap — filling it with
    the experiment file's 1200 would put the plan in an observation's place.
    """
    observed = [
        observed_from_record("host_python_process", _record()),
        observed_from_record("docker_container", _record()),
        observed_from_record(
            "azure_code_interpreter",
            _record(
                api_family=API_FAMILY_RESPONSES,
                api_version="2025-04-01-preview",
                per_task_timeout_seconds=None,
            ),
        ),
    ]
    assert check_observations_agree(observed) == []


def test_the_exemption_excuses_silence_and_not_a_different_number():
    """Azure recording a limit of its own is still held against the other two.

    Otherwise the exemption would be a hole rather than a declaration: a run
    place could send any timeout it liked and be excused for it.
    """
    observed = [
        observed_from_record("host_python_process", _record()),
        observed_from_record("docker_container", _record()),
        observed_from_record(
            "azure_code_interpreter",
            _record(
                api_family=API_FAMILY_RESPONSES,
                api_version="2025-04-01-preview",
                per_task_timeout_seconds=120,
            ),
        ),
    ]
    problems = check_observations_agree(observed)
    assert any("per_task_timeout_seconds" in problem for problem in problems), problems


def test_the_exemption_is_only_for_the_run_place_it_names():
    """The host and the container are both given the timeout, so both must show it."""
    observed = [
        observed_from_record(
            "host_python_process", _record(per_task_timeout_seconds=None)
        ),
        observed_from_record("docker_container", _record()),
    ]
    problems = check_observations_agree(observed)
    assert any(
        "host_python_process could not record per_task_timeout_seconds" in problem
        for problem in problems
    ), problems


def test_every_declared_absence_points_at_a_written_down_difference():
    """A field excused here has to be a difference the report already states.

    An exemption that only this module knows about is a difference nobody
    reading the result would ever meet.
    """
    declared = {difference.what for difference in UNCONTROLLED_DIFFERENCES}
    for run_place, fields in DECLARED_ABSENT_BY_RUN_PLACE.items():
        for field_name, points_at in fields.items():
            assert field_name in MUST_AGREE_ACROSS_RUN_PLACES, (run_place, field_name)
            assert points_at in declared, (run_place, field_name, sorted(declared))
            applies_to = {
                place
                for difference in UNCONTROLLED_DIFFERENCES
                if difference.what == points_at
                for place in difference.run_places
            }
            assert run_place in applies_to, (run_place, points_at, sorted(applies_to))


def test_the_declared_absence_reaches_a_report_of_that_run_place():
    """``residual_differences_for`` is what a report reads; it has to carry it."""
    for run_place, fields in DECLARED_ABSENT_BY_RUN_PLACE.items():
        stated = {
            difference.what for difference in residual_differences_for([run_place])
        }
        for points_at in fields.values():
            assert points_at in stated, (run_place, points_at, sorted(stated))


# ─── the same work, in the same places ───────────────────────────────────────


def test_a_run_place_that_ran_a_different_task_is_caught_by_name():
    observed = _three_agreeing()
    other_tasks = observed_from_record(
        "docker_container", _record(task_ids=["t1", "t2", "t3", "t4", "t9"])
    )
    problems = check_observations_agree([observed[0], other_tasks, observed[2]])
    joined = " ".join(problems)
    assert "t5" in joined and "t9" in joined, problems


def test_the_same_tasks_in_a_different_order_are_reported_as_that():
    observed = _three_agreeing()
    shuffled = observed_from_record(
        "docker_container", _record(task_ids=["t5", "t4", "t3", "t2", "t1"])
    )
    problems = check_observations_agree([observed[0], shuffled, observed[2]])
    assert any("different order" in problem for problem in problems), problems


def test_an_empty_task_list_is_not_a_match():
    """Two places that both recorded nothing must not read as having agreed."""
    problems = check_observations_agree(
        [
            observed_from_record("host_python_process", _record(task_ids=[])),
            observed_from_record("docker_container", _record(task_ids=[])),
        ]
    )
    assert any("empty list is not a match" in problem for problem in problems), problems


def test_an_unknown_task_list_does_not_hide_a_known_file_mismatch():
    """The two are separate facts and the weaker one must not silence the other.

    Which tasks were run and which bytes were read are found out different
    ways. A record that could not say the first still says the second, and a
    file mismatch is exactly the finding worth having.
    """
    problems = check_observations_agree(
        [
            observed_from_record("host_python_process", _record(task_ids=[])),
            observed_from_record(
                "docker_container",
                _record(
                    task_ids=[],
                    input_file_versions={
                        "budget.xlsx": "sha256:cccc",
                        "brief.pdf": "sha256:bbbb",
                    },
                ),
            ),
        ]
    )
    assert any("empty list is not a match" in problem for problem in problems), problems
    assert any(
        "budget.xlsx" in problem and "did not read the same" in problem
        for problem in problems
    ), problems


def test_a_reference_file_read_at_a_different_version_is_caught():
    observed = _three_agreeing()
    stale = observed_from_record(
        "docker_container",
        _record(input_file_versions={"budget.xlsx": "sha256:cccc", "brief.pdf": "sha256:bbbb"}),
    )
    problems = check_observations_agree([observed[0], stale, observed[2]])
    assert any("budget.xlsx" in problem for problem in problems), problems


def test_a_reference_file_only_one_run_place_recorded_is_caught():
    observed = _three_agreeing()
    short = observed_from_record(
        "docker_container", _record(input_file_versions={"budget.xlsx": "sha256:aaaa"})
    )
    problems = check_observations_agree([observed[0], short, observed[2]])
    assert any("brief.pdf" in problem for problem in problems), problems


# ─── holding the run to the plan ─────────────────────────────────────────────


PLAN = {
    "provider": "azure",
    "deployment": "gpt-5-2-chat",
    "resolved_model": "gpt-5.2-chat-2026-04-01",
    "api_version": "2025-03-01-preview",
    "max_output_tokens": 16000,
    "per_task_timeout_seconds": 900,
}


def test_a_run_that_did_what_the_plan_said_raises_nothing():
    observed = [observed_from_record("host_python_process", _record())]
    assert check_observations_match_the_plan(observed, PLAN) == []


def test_the_plan_pinning_one_model_and_another_answering_is_caught():
    observed = [
        observed_from_record(
            "host_python_process", _record(answering_model="gpt-5.1-chat-2025-11-02")
        )
    ]
    problems = check_observations_match_the_plan(observed, PLAN)
    assert len(problems) == 1, problems
    assert "resolved_model" in problems[0] and "gpt-5.1-chat" in problems[0]


def test_a_pin_the_run_could_not_check_is_a_problem_not_a_pass():
    """An unrecorded field must not read as having satisfied the pin."""
    record = _record()
    del record["answering_model"]
    problems = check_observations_match_the_plan(
        [observed_from_record("host_python_process", record)], PLAN
    )
    assert any("was not checked against anything" in problem for problem in problems), problems


def test_a_plan_field_with_no_observable_counterpart_is_left_alone():
    """Fields the readiness check already reads are not double-reported here."""
    plan = dict(PLAN)
    plan["automatic_fallback_allowed"] = False
    plan["retry_reasons_allowed"] = ["rate_limit"]
    assert check_observations_match_the_plan(
        [observed_from_record("host_python_process", _record())], plan
    ) == []


def test_a_token_cap_below_the_plan_is_caught():
    observed = [observed_from_record("host_python_process", _record(max_completion_tokens=8000))]
    problems = check_observations_match_the_plan(observed, PLAN)
    assert any("max_output_tokens" in problem for problem in problems), problems


# ─── what a reader is shown ──────────────────────────────────────────────────


def test_the_description_names_what_answered_and_what_was_not_recorded():
    record = _record()
    del record["api_version"]
    lines = describe_observations(
        [observed_from_record("azure_code_interpreter", record)]
    )
    joined = "\n".join(lines)
    assert "gpt-5.2-chat-2026-04-01" in joined
    assert "version unrecorded" in joined
    assert "api_version was not recorded" in joined


def test_the_description_never_prints_a_zero_for_something_unread():
    """A missing cap must read as unknown, not as nothing."""
    record = _record()
    del record["max_completion_tokens"]
    joined = "\n".join(describe_observations([observed_from_record("host_python_process", record)]))
    assert "? token cap" in joined
    assert "0 token cap" not in joined
