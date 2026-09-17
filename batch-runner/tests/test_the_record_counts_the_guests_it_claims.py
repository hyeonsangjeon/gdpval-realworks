"""The run record has to count the guests it says booted.

``isolated_environment_note`` used to write ``"The isolation was exercised"``
as a constant. It is the sentence a reader quotes and stops at, and it went
into the record whether or not one machine ever came up.

Every way a cohort finishes with no boot in it left that claim standing. The
live one is not hypothetical: on ``agentic_stage_one_plan.yaml`` the model is
told, every turn, that ``exec_run`` refuses -- so a compliant model never asks
for a guest, and a paid ``same-host`` cohort would have returned five
deliverables, a cost record, and a run record reporting exercised isolation
over a run that never entered a machine. Nothing else written down would have
contradicted it.

These tests hold the record to a census taken off the backends that served the
tasks, and hold four answers apart: it booted N, it asked and none started, it
never asked, nobody counted. The middle two are the ones a single number
collapses, and they are opposite faults with opposite repairs.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_isolated_selection import (  # noqa: E402
    isolated_environment_note,
)

RUNNER_PATH = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py"

PROFILE = {"policy_profile_id": "offline-full-v1"}


def _load_runner():
    """Same loader the sibling suite uses, for the same dataclass reason."""
    spec = importlib.util.spec_from_file_location("run_agentic_v2_stage", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["run_agentic_v2_stage"] = module
    spec.loader.exec_module(module)
    return module


def _census(*, asked: int, booted: int, left_running: int = 0) -> dict[str, int]:
    return {
        "exec_run_calls": asked,
        "guests_that_actually_booted": booted,
        "guests_that_left_a_machine_running": left_running,
    }


class _Backend:
    """Stands in for a backend holding the boot records of one task."""

    def __init__(self, *records) -> None:
        self.boots = list(records)


def _entered(*, leaked: bool = False) -> dict:
    """A call that started a machine, optionally leaving it up."""
    return {"booted": True, "machine": {"host_left_running": leaked}}


def _refused_before_launch() -> dict:
    """A call recorded by the backend that never reached a launcher."""
    return {"booted": False, "refused_before_launch": "perl is not an interpreter"}


class _CannotAnswer:
    """A backend with no ``boots`` at all, which is not a backend with none."""


# ── counting ──────────────────────────────────────────────────────────────


def test_the_census_is_summed_over_every_backend_the_run_built():
    """One backend per task, so a run's total is not readable off any one.

    ``AgenticV2MicroVMBackend`` is rebuilt for every task, so the guests of a
    finished task are reachable through nothing else. A count that read the
    last backend would report the last task's boots as the run's.
    """
    runner = _load_runner()

    counted = runner.boot_census(
        [
            _Backend(_entered(), _entered()),
            _Backend(),
            _Backend(_entered()),
        ]
    )

    assert counted == _census(asked=3, booted=3)


def test_a_call_that_never_reached_a_launcher_is_asked_and_not_booted():
    """The defect this census replaces a single number to fix.

    The backend files a record for every ``exec_run`` call, four of whose paths
    start nothing: a cwd that is not a directory, a host an earlier call left
    occupied, a host a previous task left occupied, and a launcher that came
    apart. ``len(boots)`` counts all of them, so a key named
    ``guests_that_actually_booted`` fed that length overstates by exactly the
    calls that failed -- the same overstatement as the constant, arriving
    through the key written to remove it.
    """
    runner = _load_runner()

    counted = runner.boot_census(
        [_Backend(_refused_before_launch(), _entered(), _refused_before_launch())]
    )

    assert counted["exec_run_calls"] == 3
    assert counted["guests_that_actually_booted"] == 1


def test_asking_and_getting_nothing_is_counted_apart_from_never_asking():
    """Both come back with no guests and they are opposite faults.

    A model that never called ``exec_run`` is an instruction or plan problem. A
    model that called it and got no machine is a launcher problem. If a run
    returns zero guests, which of the two it was is the whole diagnosis.
    """
    runner = _load_runner()

    never_asked = runner.boot_census([_Backend()])
    asked_in_vain = runner.boot_census(
        [_Backend(_refused_before_launch(), _refused_before_launch())]
    )

    assert never_asked["guests_that_actually_booted"] == 0
    assert asked_in_vain["guests_that_actually_booted"] == 0
    assert never_asked["exec_run_calls"] == 0
    assert asked_in_vain["exec_run_calls"] == 2


def test_a_machine_left_running_is_counted():
    """The only line in the record that answers whether the host was clean.

    A command can run perfectly in a guest that then refuses to go, so this is
    counted beside the boot rather than instead of it: the isolation was
    exercised *and* the host was not left clean, and both belong in the record.
    """
    runner = _load_runner()

    counted = runner.boot_census(
        [_Backend(_entered(leaked=True), _entered()), _Backend(_entered(leaked=True))]
    )

    assert counted["guests_that_actually_booted"] == 3
    assert counted["guests_that_left_a_machine_running"] == 2


def test_a_record_with_no_machine_is_not_counted_as_a_leak():
    """Absence of the key is a call that never reached a launcher.

    ``host_left_running`` is asked with ``is True`` rather than by demanding
    ``False``, because the records that start nothing carry no ``machine`` at
    all. Reading that absence as a leak would report one on exactly the calls
    that left nothing behind.
    """
    runner = _load_runner()

    counted = runner.boot_census([_Backend(_refused_before_launch())])

    assert counted["guests_that_left_a_machine_running"] == 0


def test_a_backend_that_cannot_answer_makes_the_whole_census_unknown():
    """Not smaller numbers.

    Skipping the backend that cannot answer returns totals that look like a
    measurement and are short by an unknown amount -- the same class of error as
    the constant this replaces, and quieter. The case it arises in is a third
    backend arriving without ``boots``, where the honest report is that nobody
    counted.
    """
    runner = _load_runner()

    assert runner.boot_census([_Backend(_entered()), _CannotAnswer()]) is None


def test_no_backends_is_none_booted_rather_than_unknown():
    """A run that built no backend ran no command. That is answered."""
    runner = _load_runner()

    assert runner.boot_census([]) == _census(asked=0, booted=0)


# ── what the record then says ─────────────────────────────────────────────


def test_a_run_that_never_asked_does_not_claim_the_isolation_was_exercised():
    """The regression this file exists for."""
    note = isolated_environment_note(PROFILE, census=_census(asked=0, booted=0))

    sentence = note["so_the_honest_sentence_is"]
    assert "was exercised" not in sentence
    assert "mounted and not exercised" in sentence
    assert "it never asked it to" in sentence
    assert "not evidence that the sandbox runs anything" in sentence


def test_a_run_that_asked_and_got_nothing_points_at_the_backend():
    """Same zero guests, different sentence, because it is a different fault.

    Told the model never asked, a reader goes to the plan and the instruction
    paragraph and finds nothing wrong with either. The count of calls is what
    sends them to the launcher instead.
    """
    note = isolated_environment_note(PROFILE, census=_census(asked=4, booted=0))

    sentence = note["so_the_honest_sentence_is"]
    assert "was exercised" not in sentence
    assert "asked the isolation to run something 4 times" in sentence
    assert "look at the backend, not at the plan" in sentence

    never_asked = isolated_environment_note(
        PROFILE, census=_census(asked=0, booted=0)
    )
    assert sentence != never_asked["so_the_honest_sentence_is"]


def test_a_run_with_no_boots_does_not_list_the_guest_among_what_was_real():
    """One sentence corrected and a list left standing is still a false record.

    ``what_was_real`` carried "one microVM per exec_run call" beside the
    claim, so a reader who distrusted the summary and went to the list would
    find the same thing asserted twice.
    """
    for census in (_census(asked=0, booted=0), _census(asked=4, booted=0)):
        note = isolated_environment_note(PROFILE, census=census)

        real = " ".join(note["what_was_real"])
        assert "one microVM per exec_run call" not in real
        assert "stdout and stderr of every command" not in real

    not_real = " ".join(
        isolated_environment_note(PROFILE, census=_census(asked=0, booted=0))[
            "what_was_not_real"
        ]
    )
    assert "no exec_run call asked it to" in not_real

    asked_in_vain = " ".join(
        isolated_environment_note(PROFILE, census=_census(asked=4, booted=0))[
            "what_was_not_real"
        ]
    )
    assert "exec_run was called 4 times and no machine started" in asked_in_vain


def test_an_uncounted_run_is_not_reported_as_an_unexercised_one():
    """``None`` and ``0`` are different failures and need different fixes.

    A run whose boots went uncounted may have exercised the isolation
    perfectly; what is missing is the evidence. Reporting it as zero invents a
    failure as confidently as the old constant invented a success.
    """
    unknown = isolated_environment_note(PROFILE, census=None)
    none_at_all = isolated_environment_note(PROFILE, census=_census(asked=0, booted=0))

    assert unknown["exec_run_calls"] is None
    assert unknown["guests_that_actually_booted"] is None
    assert unknown["guests_that_left_a_machine_running"] is None
    assert "Nothing counted the guests" in unknown["so_the_honest_sentence_is"]
    assert "not answered here" in unknown["so_the_honest_sentence_is"]

    assert unknown["so_the_honest_sentence_is"] != (
        none_at_all["so_the_honest_sentence_is"]
    )
    assert "nothing ran in a guest" not in " ".join(unknown["what_was_not_real"])


def test_an_uncounted_run_is_not_reported_as_an_exercised_one_either():
    """The other half of the same correction, in the two lists this time.

    ``None`` was folded in with the boots everywhere except the headline
    sentence, so a run nobody counted read exactly like a six-of-six one: it
    denied that the isolation was among the things that were not real, and
    listed one microVM per call among the things that were. Both of those are
    assertions, and an uncounted run supports neither.

    So ``None`` is kept off both lists rather than moved from one to the other.
    That is the whole of what is knowable: a reader who quotes any single line
    of this note gets told nobody looked, and nothing tells them which way.
    """
    unknown = isolated_environment_note(PROFILE, census=None)
    booted = isolated_environment_note(PROFILE, census=_census(asked=6, booted=6))

    not_real = " ".join(unknown["what_was_not_real"])
    assert "nothing about the isolation" not in not_real
    assert "nothing counted whether it did" in not_real
    assert not_real != " ".join(booted["what_was_not_real"])

    real = " ".join(unknown["what_was_real"])
    assert "one microVM per exec_run call" not in real
    assert "stdout and stderr of every command" not in real


def test_a_run_that_booted_says_how_many_rather_than_that_it_did():
    """A number can be checked against the ledger and a boolean cannot."""
    note = isolated_environment_note(PROFILE, census=_census(asked=14, booted=12))

    assert note["exec_run_calls"] == 14
    assert note["guests_that_actually_booted"] == 12
    assert "12 of 14 exec_run calls entered a guest" in note["so_the_honest_sentence_is"]
    assert "the isolation was exercised" in note["so_the_honest_sentence_is"]


def test_a_leak_is_reported_beside_the_boots_and_not_instead_of_them():
    """Acceptance observation six, which nothing else in the record answers.

    The isolation being exercised and the host being left dirty are both true
    of the same run when a command succeeds in a guest that then will not stop.
    A record that reported only the first would close out a run that left a
    machine on the host.
    """
    note = isolated_environment_note(
        PROFILE, census=_census(asked=5, booted=5, left_running=2)
    )

    sentence = note["so_the_honest_sentence_is"]
    assert note["guests_that_left_a_machine_running"] == 2
    assert "the isolation was exercised" in sentence
    assert "2 of them left a machine running on the host" in sentence
    assert "does not show teardown working" in sentence


def test_a_clean_run_does_not_mention_a_leak():
    """The clause is evidence, so it appears only when there is some."""
    note = isolated_environment_note(PROFILE, census=_census(asked=5, booted=5))

    assert "left a machine running" not in note["so_the_honest_sentence_is"]


def test_the_cost_of_a_boot_is_still_unknown_on_every_branch():
    """Four sentences now, and the thing nobody measured is true of all of them."""
    censuses = [
        None,
        _census(asked=0, booted=0),
        _census(asked=4, booted=0),
        _census(asked=3, booted=3),
    ]
    for census in censuses:
        note = isolated_environment_note(PROFILE, census=census)
        assert "What it cost to boot is not known" in note["so_the_honest_sentence_is"]


# ── the fixture is not asked ──────────────────────────────────────────────


def test_the_fixture_reports_none_booted_whatever_it_is_handed():
    """It has no launcher, so no census taken over it could be anything else.

    Echoing the caller's argument here would let a wrong one make the fixture
    look like it booted something -- the failure these keys exist to catch,
    arriving through the keys themselves.
    """
    runner = _load_runner()

    note = runner.environment_note(
        PROFILE, census=_census(asked=99, booted=99, left_running=99)
    )

    assert note["guests_that_actually_booted"] == 0
    assert note["guests_that_left_a_machine_running"] == 0
    assert note["exec_run_calls"] is None
    assert note["backend_boots_guests"] is False


def test_the_fixture_does_not_report_zero_calls_over_an_exec_run_it_serves():
    """Zero here is a measurement nobody took, and it routes to the wrong repair.

    The two guest counts above are zero because the fixture has no launcher, so
    the answer is knowable without counting. ``exec_run`` is not like that: the
    fixture serves ``fixture-upper SOURCE DESTINATION``, advertises it in its
    own capabilities, and really writes the file -- a fixture cohort can make
    calls that succeed. Nothing counts them, because ``boot_census`` reads
    ``boots`` and the fixture has none.

    Writing ``0`` there is the constant this whole change deletes, arriving
    through one of its own keys, and it fails in the expensive direction: by
    the diagnosis these tests exist to protect, no calls means the model never
    asked, which sends a reader to the plan and the instruction paragraph over
    a run where it did ask and was served.
    """
    runner = _load_runner()

    note = runner.environment_note(PROFILE)

    assert note["exec_run_calls"] is None


def test_the_fixture_record_does_not_call_an_exec_run_it_serves_a_refusal():
    """``what_was_not_real`` contradicted the verdict two keys above it.

    The record carried ``exec_run: partly`` in ``tool_availability`` and, in
    plain language underneath, that ``exec_run`` "answered
    capability_unavailable to everything". Only one of those can be true, and
    the prose is the half a reader takes at face value -- it is written out in
    full precisely so it can be quoted, while the verdict is one word in a
    list. So the false half is the one that travels.
    """
    runner = _load_runner()

    note = runner.environment_note(PROFILE)

    not_real = " ".join(note["what_was_not_real"])
    assert "capability_unavailable to everything" not in not_real
    assert "fixture-upper" in not_real
    assert "refuses every other argv" in not_real

    served = [
        entry for entry in note["tool_availability"] if entry["tool"] == "exec_run"
    ]
    assert served and served[0]["verdict"] == "partly"


@pytest.mark.parametrize(
    "census",
    [
        None,
        _census(asked=0, booted=0),
        _census(asked=6, booted=0),
        _census(asked=6, booted=6),
        _census(asked=6, booted=6, left_running=1),
    ],
)
def test_both_notes_still_have_the_same_shape(census):
    """A backend switch changes what the record says, never how much it says.

    Parametrised because the isolated note now builds two of its lists from the
    census, and a branch that dropped or added a key would be a shape the
    unparametrised version of this test could not see.
    """
    runner = _load_runner()

    fixture = runner.environment_note(PROFILE)
    isolated = isolated_environment_note(PROFILE, census=census)

    assert set(isolated) == set(fixture)


# ── that the runner really takes the census ───────────────────────────────


def test_the_factory_keeps_every_backend_it_builds():
    """Read from the source, because no microVM boots in this suite.

    A running total incremented at construction cannot work: a backend's boots
    happen after it is handed over, so the only moment a count is right is the
    end.
    """
    source = RUNNER_PATH.read_text("utf-8")

    factory = source.split("def backend_factory(")[1].split("\n        def ")[0]
    assert "backends_built.append(" in factory


def test_the_record_asks_for_the_census_rather_than_stating_one():
    """The literal is what this whole change removes. It must not come back.

    Pinned at the call site as well as in the note, because a caller passing a
    constant would satisfy every test above while restoring exactly the defect:
    a record that says what it was told rather than what happened.
    """
    source = RUNNER_PATH.read_text("utf-8")

    call = source.split('"environment": environment_note(')[1].split("\n        ),")[0]
    assert "census=boot_census(backends_built)" in call


def test_the_backend_records_a_call_it_refused_on_the_path_check():
    """Otherwise a model can ask and leave no trace of having asked.

    A bad ``cwd`` is refused before anything is launched, which is right and
    costs nothing. But a refusal ends the model's attempt, so a task can end
    having called ``exec_run`` once with no record of the call -- and the census
    would then report a model that never asked, sending a reader to the plan
    over a fault in neither the plan nor the model.
    """
    source = (
        BATCH_RUNNER_ROOT / "core" / "agentic_v2_microvm_backend.py"
    ).read_text("utf-8")

    refusal = source.split("error_type\": \"path_not_directory\"")[0].split(
        "def exec_run("
    )[1]
    assert "self.boots.append(" in refusal.split("_open_directory(")[1]


# ── and that it says whether the records survived ─────────────────────────


class _Carried:
    """A backend that has been closed, holding what its ``close()`` lifted out.

    Two attributes rather than one because the backend keeps two: what came out
    and, separately, what stopped coming out. A helper that collapsed them into
    a single list could not express the case these tests exist for -- nothing
    carried, for a reason.
    """

    def __init__(self, *carried: str, failed: str | None = None) -> None:
        self.exec_records_carried = list(carried)
        self.exec_records_not_carried = failed


def test_the_files_are_counted_by_call_as_well_as_by_file():
    """Three files over two calls is two calls, not three.

    A call keeps up to three leaves, so a file count sitting beside
    ``exec_run_calls`` reads as though more happened than did. Both numbers are
    reported because neither answers the other's question.
    """
    runner = _load_runner()

    counted = runner.exec_record_carriage(
        [
            _Carried(".gdpval/exec/0000/stdout", ".gdpval/exec/0000/stderr"),
            _Carried(".gdpval/exec/0001/stdout"),
        ]
    )

    assert counted["files_carried_out"] == 3
    assert counted["calls_with_records"] == 2
    assert counted["not_carried_because"] is None


def test_two_tasks_that_both_ran_one_command_are_two_calls():
    """The directory is numbered within its task, so the task has to be in the key.

    ``_keep_the_output`` builds ``.gdpval/exec/0000`` with no task component and
    there is one backend per task, so counting bare directories makes every
    task's first call the same call. The test above misses it by handing the two
    backends different numbers; this one gives them the same number, which is
    what a cohort actually looks like.

    The number is read beside run-wide ``exec_run_calls``. Undercounting it says
    the transcripts were lost -- the reading this whole function exists to stop
    a reader from making when nothing was lost at all.
    """
    runner = _load_runner()

    counted = runner.exec_record_carriage(
        [
            _Carried(".gdpval/exec/0000/stdout", ".gdpval/exec/0000/stderr"),
            _Carried(".gdpval/exec/0000/stdout", ".gdpval/exec/0000/stderr"),
        ]
    )

    assert counted["files_carried_out"] == 4
    assert counted["calls_with_records"] == 2


def test_a_run_that_lost_its_records_is_not_reported_as_one_that_made_none():
    """The distinction the artifact could not make, and the reason for the key.

    Both of these carried nothing. One ran nothing; the other ran something and
    the copy failed. A reader with only the file count sees one fact, goes
    looking at the plan and the instruction paragraph, and never learns that
    the evidence existed and was dropped on the way out.
    """
    runner = _load_runner()

    ran_nothing = runner.exec_record_carriage([_Carried()])
    lost_it = runner.exec_record_carriage(
        [_Carried(failed=".gdpval/exec/0000/stdout: OSError: [Errno 5] I/O error")]
    )

    assert ran_nothing["files_carried_out"] == lost_it["files_carried_out"] == 0
    assert ran_nothing["not_carried_because"] is None
    assert "OSError" in lost_it["not_carried_because"]
    assert ran_nothing != lost_it


def test_a_backend_that_cannot_answer_makes_the_carriage_unknown():
    """Same rule as the census, and the live case is the fixture backend.

    ``_Backend`` here answers ``boots`` and nothing about exec records, which
    is exactly the fixture's shape: it serves ``exec_run`` and writes no
    transcript. Summing over it and reporting the smaller total would publish a
    zero that means "nobody looked" under a key that reads as "nothing ran".
    """
    runner = _load_runner()

    assert runner.exec_record_carriage([_Backend(_entered())]) is None
    assert (
        runner.exec_record_carriage(
            [_Carried(".gdpval/exec/0000/stdout"), _Backend(_entered())]
        )
        is None
    )


def test_no_backends_is_nothing_carried_rather_than_unknown():
    """A run that built no backend ran no command. That is answered, not unknown."""
    runner = _load_runner()

    assert runner.exec_record_carriage([]) == {
        "files_carried_out": 0,
        "calls_with_records": 0,
        "not_carried_because": None,
    }


def test_the_record_asks_the_backends_what_they_carried():
    """Pinned at the call site, for the reason the census is.

    A constant here would satisfy every test above and restore the defect in a
    new place: a record reporting what it was told rather than what happened.
    """
    source = RUNNER_PATH.read_text("utf-8")

    assert '"exec_records": exec_record_carriage(backends_built),' in source
