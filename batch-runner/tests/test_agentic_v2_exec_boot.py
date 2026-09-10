"""What the exec-run wrapper builds, and how a boot is read back.

Two kinds of check here, and the second is the interesting one.

The first kind is ordinary: given a request, does the builder produce the right
text, and given a boot artefact, does the reader reach the right verdict.

The second kind **runs the script it built**, under a real ``/bin/sh``, with
``/work`` pointed at a temporary directory. That is not a microVM and does not
pretend to be one — the containment is stage C's business and was measured
there. What it proves is the part a microVM would not help with anyway: that the
wrapper is valid shell, that it enters the directory it was asked to, that the
payload arrives byte for byte, and that a command reading standard input gets
what the request said and not something else. Those are exactly the faults that
would otherwise be found once, expensively, on a booted machine.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_exec_boot import (
    CD_FAILED_MARKER,
    DECODE_FAILED_MARKER,
    EXEC_RECORD_DIR,
    GUEST_SETUP_STATUS,
    INTERPRETERS,
    MOST_OUTPUT_BYTES,
    WORKSPACE_IN_GUEST,
    ExecRefused,
    command_script,
    effective_deadline,
    read_the_boot,
)
from core.agentic_v2_microvm import REQUIRED_MICROVM_POLICY


ANY_DEADLINE = {
    "requested_seconds": 60,
    "policy_seconds": 1200,
    "applied_seconds": 60,
    "capped_by_the_policy": False,
}


def _boot(outcome: str, *, status=None, stdout: str = "", stderr: str = "") -> dict:
    return {
        "outcome": outcome,
        "command_exit_status": status,
        "results": {"/out/stdout": stdout, "/out/stderr": stderr},
    }


def _run_the_wrapper(script: str, tmp_path: Path, *, cwd_exists: str | None = "job"):
    """Run a built wrapper under a real shell with /work redirected at tmp_path.

    ``GUEST_INIT`` runs the wrapper as ``sh /work/in/command.sh`` with stdout and
    stderr sent to files on the work disk, so that is how it is run here.
    """
    work = tmp_path / "work"
    (work / "in").mkdir(parents=True)
    (work / "ws").mkdir(parents=True)
    if cwd_exists:
        (work / "ws" / cwd_exists).mkdir(parents=True)
    local = script.replace("/work/", f"{work.as_posix()}/")
    wrapper = work / "in" / "command.sh"
    wrapper.write_text(local, encoding="utf-8")
    out = work / "stdout"
    err = work / "stderr"
    with out.open("wb") as stdout, err.open("wb") as stderr:
        finished = subprocess.run(
            ["/bin/sh", wrapper.as_posix()],
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
    return (
        finished.returncode,
        out.read_text(encoding="utf-8", errors="replace"),
        err.read_text(encoding="utf-8", errors="replace"),
    )


class TestTheDeadlineTheModelGetsIsRecorded:
    def test_a_request_inside_the_policy_is_left_alone(self):
        reading = effective_deadline(300)
        assert reading["applied_seconds"] == 300
        assert reading["capped_by_the_policy"] is False

    def test_a_request_past_the_policy_gets_the_policy_and_says_so(self):
        reading = effective_deadline(2700)
        assert reading["applied_seconds"] == REQUIRED_MICROVM_POLICY[
            "wall_clock_seconds"
        ]
        assert reading["requested_seconds"] == 2700
        assert reading["capped_by_the_policy"] is True

    def test_the_number_asked_for_survives_being_overruled(self):
        # Otherwise a kill at the policy's bound reads, later, as the model's
        # own choice having been honoured.
        assert effective_deadline(2700)["requested_seconds"] == 2700

    @pytest.mark.parametrize("bad", [0, -1, None, True, 12.5, "60"])
    def test_a_bound_that_is_not_a_bound_is_refused(self, bad):
        with pytest.raises(ExecRefused):
            effective_deadline(bad)

    def test_a_policy_with_no_wall_clock_is_refused_rather_than_defaulted(self):
        policy = dict(REQUIRED_MICROVM_POLICY)
        policy.pop("wall_clock_seconds")
        with pytest.raises(ExecRefused):
            effective_deadline(60, policy=policy)


class TestTheWrapperRefusesWhatItCannotWriteFaithfully:
    def test_an_absolute_cwd_is_refused(self):
        with pytest.raises(ExecRefused):
            command_script({"argv": ["true"], "cwd": "/etc", "timeout_seconds": 5})

    def test_a_cwd_climbing_out_of_the_workspace_is_refused(self):
        with pytest.raises(ExecRefused):
            command_script({"argv": ["true"], "cwd": "a/../../b", "timeout_seconds": 5})

    def test_a_request_that_is_both_shapes_is_refused(self):
        with pytest.raises(ExecRefused):
            command_script(
                {
                    "argv": ["true"],
                    "interpreter": "python",
                    "script": "pass",
                    "cwd": "job",
                    "timeout_seconds": 5,
                }
            )

    def test_a_request_that_is_neither_shape_is_refused(self):
        with pytest.raises(ExecRefused):
            command_script({"cwd": "job", "timeout_seconds": 5})

    def test_an_interpreter_nobody_named_is_refused(self):
        with pytest.raises(ExecRefused):
            command_script(
                {
                    "interpreter": "perl",
                    "script": "print 1",
                    "cwd": "job",
                    "timeout_seconds": 5,
                }
            )

    def test_an_interpreter_the_image_may_lack_is_still_built(self):
        # Refusing here would hide a recoverable failure from the model. A
        # missing Rscript should come back as "not found" from inside.
        for name in INTERPRETERS:
            built = command_script(
                {
                    "interpreter": name,
                    "script": "x",
                    "cwd": "job",
                    "timeout_seconds": 5,
                }
            )
            assert INTERPRETERS[name] in built


class TestTheWrapperIsRealShellThatDoesWhatItSays:
    def test_it_runs_the_command_in_the_directory_that_was_asked_for(self, tmp_path):
        script = command_script(
            {"argv": ["pwd"], "cwd": "job", "timeout_seconds": 5}
        )
        code, out, err = _run_the_wrapper(script, tmp_path)
        assert code == 0, err
        assert out.strip().endswith("/work/ws/job")

    def test_a_directory_that_is_not_there_stops_before_the_command_runs(
        self, tmp_path
    ):
        script = command_script(
            {"argv": ["touch", "should-not-exist"], "cwd": "job", "timeout_seconds": 5}
        )
        code, _out, err = _run_the_wrapper(script, tmp_path, cwd_exists=None)
        assert code == GUEST_SETUP_STATUS
        # Exactly the marker, with nothing before it. The reader downstream
        # matches stderr against this string, and a shell that had printed its
        # own "can't cd to ..." first would mean that match never once fired on
        # a real guest -- which is what this assertion originally caught.
        assert err.strip() == CD_FAILED_MARKER
        assert not (tmp_path / "work" / "ws" / "should-not-exist").exists()

    def test_an_argument_with_a_space_and_a_quote_survives_intact(self, tmp_path):
        awkward = "two words and an ' apostrophe"
        script = command_script(
            {"argv": ["printf", "%s", awkward], "cwd": "job", "timeout_seconds": 5}
        )
        code, out, err = _run_the_wrapper(script, tmp_path)
        assert code == 0, err
        assert out == awkward

    def test_a_script_arrives_byte_for_byte_including_no_final_newline(
        self, tmp_path
    ):
        # A heredoc appends a newline the model's bytes may not have had, which
        # is why the payload travels as base64 rather than as itself.
        body = "import sys\nsys.stdout.write('exact')"
        script = command_script(
            {
                "interpreter": "python",
                "script": body,
                "cwd": "job",
                "timeout_seconds": 5,
            }
        )
        _code, out, _err = _run_the_wrapper(script, tmp_path)
        assert out == "exact"
        landed = (tmp_path / "work" / "in" / "script").read_bytes()
        assert landed == body.encode("utf-8")

    def test_a_payload_containing_the_heredoc_delimiter_cannot_end_it_early(
        self, tmp_path
    ):
        # base64's alphabet has no underscore, so the delimiter provably cannot
        # occur in the document. This is the proof rather than the argument.
        hostile = "# GDPVAL_SCRIPT_EOF\nprint('still mine')\n"
        script = command_script(
            {
                "interpreter": "python",
                "script": hostile,
                "cwd": "job",
                "timeout_seconds": 5,
            }
        )
        assert script.count("GDPVAL_SCRIPT_EOF") == 2
        code, out, err = _run_the_wrapper(script, tmp_path)
        assert (tmp_path / "work" / "in" / "script").read_text() == hostile
        assert code == 0, err
        assert out.strip() == "still mine"

    def test_a_delimiter_alone_on_a_line_of_the_payload_is_still_only_data(
        self, tmp_path
    ):
        # The harsher shape: the delimiter with nothing else on its line, which
        # is exactly what would terminate the document if it reached the shell.
        hostile = "x = '''\nGDPVAL_SCRIPT_EOF\n'''\nprint(len(x))\n"
        script = command_script(
            {
                "interpreter": "python",
                "script": hostile,
                "cwd": "job",
                "timeout_seconds": 5,
            }
        )
        code, out, err = _run_the_wrapper(script, tmp_path)
        assert (tmp_path / "work" / "in" / "script").read_text() == hostile
        assert code == 0, err
        assert out.strip() == "19"

    def test_standard_input_is_what_the_request_said(self, tmp_path):
        script = command_script(
            {"argv": ["cat"], "cwd": "job", "stdin": "fed in", "timeout_seconds": 5}
        )
        code, out, err = _run_the_wrapper(script, tmp_path)
        assert code == 0, err
        assert out == "fed in"

    def test_a_request_with_no_stdin_reads_an_empty_stream_not_its_own_script(
        self, tmp_path
    ):
        # Without an explicit redirect the command inherits init's descriptor,
        # and a command that consumed part of its own launcher would be a very
        # hard afternoon.
        script = command_script({"argv": ["cat"], "cwd": "job", "timeout_seconds": 5})
        assert "< /dev/null" in script
        code, out, _err = _run_the_wrapper(script, tmp_path)
        assert code == 0
        assert out == ""

    def test_the_commands_own_returncode_comes_back(self, tmp_path):
        script = command_script(
            {
                "interpreter": "bash",
                "script": "exit 42",
                "cwd": "job",
                "timeout_seconds": 5,
            }
        )
        code, _out, _err = _run_the_wrapper(script, tmp_path)
        assert code == 42


class TestReadingOneBootAsOneResult:
    def test_an_exit_status_is_the_answer_whatever_the_number_is(self):
        read = read_the_boot(_boot("booted", status=3), deadline=ANY_DEADLINE)
        assert read["result"] == {"ok": True, "error_type": None, "data": {"returncode": 3}}

    def test_a_failing_command_is_a_successful_tool_call(self):
        # The model is shown "that did not work" and chooses again. That is the
        # loop working, not the call failing.
        assert read_the_boot(_boot("booted", status=1), deadline=ANY_DEADLINE)[
            "result"
        ]["ok"] is True

    def test_a_machine_that_wrote_nothing_is_never_a_zero(self):
        read = read_the_boot(_boot("booted_but_wrote_nothing"), deadline=ANY_DEADLINE)
        assert read["result"]["ok"] is False
        assert read["result"]["error_type"] == "compute_backend_error"
        assert read["result"]["data"] == {}

    def test_a_machine_that_never_started_says_so_specifically(self):
        read = read_the_boot(_boot("never_started"), deadline=ANY_DEADLINE)
        assert read["result"]["error_type"] == "compute_start_failed"

    def test_the_deadline_firing_is_a_cancellation_not_a_broken_backend(self):
        # The bound doing its job is stage C's third attack succeeding on
        # purpose, and calling it a backend fault would report the containment
        # working as the containment being broken.
        read = read_the_boot(_boot("stopped_by_the_deadline"), deadline=ANY_DEADLINE)
        assert read["result"]["error_type"] == "cancelled"

    def test_a_command_that_finished_keeps_its_answer_when_shutdown_overran(self):
        read = read_the_boot(
            _boot("stopped_by_the_deadline", status=0), deadline=ANY_DEADLINE
        )
        assert read["result"]["ok"] is True
        assert read["result"]["data"] == {"returncode": 0}
        assert "only the shutdown overran" in read["grounds"]

    @pytest.mark.parametrize("bad", [-1, 256, 1000, "0", True, 1.5])
    def test_a_returncode_the_guest_made_up_is_refused(self, bad):
        read = read_the_boot(_boot("booted", status=bad), deadline=ANY_DEADLINE)
        assert read["result"]["error_type"] == "invalid_backend_result"

    def test_the_cd_marker_is_a_path_fault_and_not_the_commands_status(self):
        read = read_the_boot(
            _boot("booted", status=GUEST_SETUP_STATUS, stderr=CD_FAILED_MARKER + "\n"),
            deadline=ANY_DEADLINE,
        )
        assert read["result"]["error_type"] == "path_not_directory"

    def test_a_missing_base64_is_an_image_fault_not_a_path_fault(self):
        read = read_the_boot(
            _boot(
                "booted",
                status=GUEST_SETUP_STATUS,
                stderr=DECODE_FAILED_MARKER + "\n",
            ),
            deadline=ANY_DEADLINE,
        )
        assert read["result"]["error_type"] == "compute_backend_error"

    def test_a_real_command_that_happens_to_exit_125_keeps_its_status(self):
        read = read_the_boot(
            _boot("booted", status=GUEST_SETUP_STATUS, stderr="ordinary trouble"),
            deadline=ANY_DEADLINE,
        )
        assert read["result"]["data"] == {"returncode": GUEST_SETUP_STATUS}

    def test_every_reading_says_on_what_grounds(self):
        for boot in (
            _boot("booted", status=0),
            _boot("booted_but_wrote_nothing"),
            _boot("never_started"),
            _boot("stopped_by_the_deadline"),
        ):
            assert read_the_boot(boot, deadline=ANY_DEADLINE)["grounds"].strip()

    def test_the_deadline_that_was_applied_travels_with_the_reading(self):
        read = read_the_boot(_boot("booted", status=0), deadline=ANY_DEADLINE)
        assert read["deadline"] == ANY_DEADLINE


class TestOutputGoesToTheWorkspaceAndSaysWhenItWasCut:
    def test_output_is_carried_out_separately_from_the_result(self):
        # exec_run's data schema is a returncode and nothing else, with
        # additionalProperties false, so there is nowhere in the result to put
        # output even if one wanted to.
        read = read_the_boot(
            _boot("booted", status=0, stdout="printed", stderr="warned"),
            deadline=ANY_DEADLINE,
        )
        assert read["stdout"] == "printed"
        assert read["stderr"] == "warned"
        assert read["result"]["data"] == {"returncode": 0}

    def test_a_stream_past_the_ceiling_is_cut_and_says_it_was(self):
        read = read_the_boot(
            _boot("booted", status=0, stdout="x" * (MOST_OUTPUT_BYTES + 500)),
            deadline=ANY_DEADLINE,
        )
        assert read["truncated"]["stdout"] is True
        assert "output truncated" in read["stdout"]
        assert str(MOST_OUTPUT_BYTES + 500) in read["stdout"]

    def test_a_stream_inside_the_ceiling_is_untouched(self):
        read = read_the_boot(
            _boot("booted", status=0, stdout="small"), deadline=ANY_DEADLINE
        )
        assert read["stdout"] == "small"
        assert read["truncated"] == {"stdout": False, "stderr": False}

    def test_a_stream_the_guest_did_not_write_reads_as_empty_not_as_none(self):
        read = read_the_boot(_boot("booted", status=0), deadline=ANY_DEADLINE)
        assert read["stdout"] == ""
        assert read["stderr"] == ""

    def test_the_place_output_is_left_is_a_path_the_model_can_ask_for(self):
        # It has to satisfy the contract's path rule or workspace_apply will
        # refuse to read back the thing exec_run just wrote.
        assert not EXEC_RECORD_DIR.startswith("/")
        assert ".." not in EXEC_RECORD_DIR.split("/")
        assert WORKSPACE_IN_GUEST.startswith("/work")
