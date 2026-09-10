"""Stage D's paid probe, run end to end without paying for it and without a boot.

Stage A's probe could be proved free because the only real thing under it was a
backend that writes bytes. Stage D has a second real thing under it — a machine
— and this box cannot start one. So the boot is injected, exactly as it is in
:mod:`tests.test_agentic_v2_stage_d_session`, and *everything else runs*: the
real dispatcher, the real microVM backend, the real work disk built with
``mke2fs``, the real carriage, read back with ``debugfs``.

That leaves one test in this file doing something no other test in the tree
does, and it is the one the whole stage is for:

    a model asks to run a command → a work disk is built from the session's
    workspace → the injected guest writes a file onto it → the disk comes back →
    the carriage installs it → and the *next* model turn reads that file through
    ``workspace_apply`` and gets its contents.

Five modules and a filesystem, in one sequence, with only the network and the
hypervisor standing in. If that passes, what a paid run adds is the model's own
judgement and a real kernel — not any of the wiring.

The tool list is checked here too, for stage A's reason and one more: this probe
offers a tool that *boots*, so a list that has drifted does not merely waste a
turn, it spends a machine.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_microvm_backend import GuestImage  # noqa: E402
from core.agentic_v2_one_call_machine import OneCallMachine  # noqa: E402
from core.agentic_v2_stage_a_probe import (  # noqa: E402
    PROBE_TOOLS as STAGE_A_TOOLS,
)
from core.agentic_v2_stage_d_probe import (  # noqa: E402
    PROBE_INSTRUCTIONS,
    PROBE_TOOLS,
    TOOLS_THIS_BACKEND_REFUSES,
    TURNS_STAGE_D_NEEDS,
    ProbeCannotDescribeItself,
    ProbeToolsAreWrong,
    StageDProbeOutcome,
    check_probe_tools,
    run_stage_d_probe,
)
from core.agentic_v2_stage_one_budget import StageOneBudget  # noqa: E402
from core.agentic_v2_substrate import AgenticV2SubstrateManifest  # noqa: E402
from core.agentic_v2_work_disk import (  # noqa: E402
    SCRATCH_ON_DISK,
    WORKSPACE_ON_DISK,
    workspace_out_of_work_disk,
)
from core.execution_envelope_cost import ModelPrice  # noqa: E402


needs_ext4_tools = pytest.mark.skipif(
    shutil.which("mke2fs") is None or shutil.which("debugfs") is None,
    reason="e2fsprogs is what builds and reads the work disk",
)

MODEL = "gpt-5.4"

AN_IMAGE = GuestImage(
    reference="ghcr.io/hyeonsangjeon/gdpval-sandbox",
    digest="sha256:ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5bd24edb",
    kernel_sha256="a" * 64,
    rootfs_sha256="b" * 64,
)


# ── stand-ins: one for the network, one for the hypervisor ────────────────


class FakeResponses:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[dict] = []

    def create(self, **payload):
        self.calls.append(payload)
        if not self.answers:
            raise AssertionError("the probe asked more times than it was told to")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeClient:
    def __init__(self, answers):
        self.responses = FakeResponses(answers)


class AGuestThatReallyWritesADisk:
    """The injected boot: reads the staged disk, changes it, leaves a new one.

    The same stand-in the joint session tests use, for the same reason — it is
    the only thing here that is not the production object, and it does exactly
    what a booted machine does to the work disk and nothing else.
    """

    def __init__(self, *, writes=None, status=0, outcome="booted", returns_a_disk=True):
        self.writes = dict(writes or {})
        self.status = status
        self.outcome = outcome
        self.returns_a_disk = returns_a_disk
        self.commands: list[str] = []

    def __call__(self, plan, *, jailer_binary, kernel, rootfs, work_disk, uid, gid):
        staged = Path(work_disk)
        self.commands.append(
            subprocess.run(
                ["debugfs", "-R", f"cat {SCRATCH_ON_DISK}/command.sh", staged.as_posix()],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
        )
        if self.returns_a_disk:
            self._rebuild(staged, Path(str(staged) + ".returned"))
        return {
            "outcome": self.outcome,
            "command_exit_status": self.status,
            "results": {"/out/stdout": "", "/out/stderr": ""},
            "teardown": {"all_gone": True},
        }

    def _rebuild(self, staged: Path, rebuilt: Path) -> None:
        scratch = staged.parent / "guest"
        if scratch.exists():
            shutil.rmtree(scratch)
        read = workspace_out_of_work_disk(image=staged, into=scratch)
        assert read["read_back"], read["said"]

        tree = staged.parent / "guest-tree"
        if tree.exists():
            shutil.rmtree(tree)
        (tree / SCRATCH_ON_DISK).mkdir(parents=True)
        shutil.move(read["root"], str(tree / WORKSPACE_ON_DISK))
        for relative, content in self.writes.items():
            target = tree / WORKSPACE_ON_DISK / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        subprocess.run(
            [
                "mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096",
                "-d", tree.as_posix(), rebuilt.as_posix(), "8192",
            ],
            check=True,
            capture_output=True,
        )


def _machine(tmp_path, guest) -> OneCallMachine:
    images = tmp_path / "images"
    images.mkdir(exist_ok=True)
    (images / "vmlinux").write_bytes(b"stands in for a kernel\n")
    (images / "rootfs.ext4").write_bytes(b"stands in for a rootfs\n")
    return OneCallMachine(
        kernel=images / "vmlinux",
        rootfs=images / "rootfs.ext4",
        firecracker_binary=images / "firecracker",
        uid=1200,
        gid=1200,
        vcpu_count=2,
        cgroup_version=2,
        scratch=tmp_path / "scratch",
        session="gdpval-stage-d",
        boot=guest,
    )


def _manifest() -> AgenticV2SubstrateManifest:
    return AgenticV2SubstrateManifest.load(Path("sandbox/agentic_v2_capabilities.json"))


def asks_for(name: str, arguments: dict, *, call_id: str = "call-1") -> dict:
    return {
        "model": MODEL,
        "usage": {"input_tokens": 120, "output_tokens": 30},
        "output_text": "",
        "output": [
            {
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": json.dumps(arguments),
            }
        ],
    }


def says_nothing_useful(text: str = "I have finished thinking") -> dict:
    return {
        "model": MODEL,
        "usage": {"input_tokens": 140, "output_tokens": 12},
        "output_text": text,
        "output": [],
    }


def runs(argv, *, cwd=".", timeout_seconds=60, call_id="call-1") -> dict:
    return asks_for(
        "exec_run",
        {"argv": list(argv), "cwd": cwd, "timeout_seconds": timeout_seconds},
        call_id=call_id,
    )


def a_budget(**changes) -> StageOneBudget:
    settings = {
        "max_model_calls": 12,
        "max_input_tokens": 300_000,
        "max_output_tokens": 16_384,
    }
    settings.update(changes)
    return StageOneBudget(**settings)


def prices_for(model: str = MODEL) -> dict[str, ModelPrice]:
    return {
        model: ModelPrice(
            model=model,
            input_usd_per_million=Decimal("1.25"),
            output_usd_per_million=Decimal("10"),
        )
    }


def run_probe(answers, tmp_path, *, guest=None, **changes):
    guest = guest if guest is not None else AGuestThatReallyWritesADisk()
    settings = {
        "client": FakeClient(answers),
        "deployment": "gpt-5.4",
        "resource": "a-foundry-resource",
        "budget": a_budget(),
        "task_prompt": "count the rows in the attached sheet and write the total",
        "workspace_root": tmp_path / "probe",
        "image": AN_IMAGE,
        "boot_one_command": _machine(tmp_path, guest),
        "substrate_manifest": _manifest(),
        "max_output_tokens_per_turn": 2_048,
        "max_seconds": 120.0,
        "prices": prices_for(),
    }
    settings.update(changes)
    return run_stage_d_probe(**settings)


# ── the tool list, which here guards machines and not only turns ──────────


def test_the_offered_tools_are_the_three_a_command_run_needs():
    """Written down so widening the list is a change somebody has to make."""
    assert PROBE_TOOLS == ("capabilities_query", "workspace_apply", "exec_run")


def test_the_shipped_list_is_acceptable_to_the_check_that_guards_it():
    assert check_probe_tools() == []


def test_stage_d_is_stage_a_plus_the_one_tool_it_exists_to_test():
    """The difference between the two stages is one tool, and it is exec_run."""
    assert set(PROBE_TOOLS) - set(STAGE_A_TOOLS) == {"exec_run"}


def test_a_list_without_exec_run_is_refused_because_that_is_the_question():
    problems = check_probe_tools(("capabilities_query", "workspace_apply"))

    assert len(problems) == 1
    assert "exec_run" in problems[0]
    assert "stage A again" in problems[0]


def test_offering_finalize_is_refused_because_it_reaches_the_grader():
    problems = check_probe_tools((*PROBE_TOOLS, "finalize"))

    assert len(problems) == 1
    assert "finalize" in problems[0]
    assert "marking" in problems[0]


@pytest.mark.parametrize("shut", TOOLS_THIS_BACKEND_REFUSES)
def test_offering_a_tool_this_backend_always_refuses_is_refused(shut):
    """A tool that can only answer no spends a paid turn to say so."""
    problems = check_probe_tools((*PROBE_TOOLS, shut))

    assert len(problems) == 1
    assert shut in problems[0]


def test_a_tool_the_contract_does_not_define_is_refused():
    problems = check_probe_tools((*PROBE_TOOLS, "make_it_work"))

    assert len(problems) == 1
    assert "make_it_work" in problems[0]


def test_a_wrong_list_stops_the_probe_before_it_spends_or_boots(tmp_path):
    client = FakeClient([runs(["true"])])
    guest = AGuestThatReallyWritesADisk()

    with pytest.raises(ProbeToolsAreWrong, match="finalize"):
        run_probe(
            [], tmp_path, client=client, guest=guest, tools=(*PROBE_TOOLS, "finalize")
        )

    assert client.responses.calls == []
    assert guest.commands == []


def test_a_backend_that_cannot_say_what_it_is_stops_before_spending(tmp_path):
    """A paid record naming an unverified image is worse than no record.

    The numbers would be real and would refer to nothing anyone can check
    afterwards, which is exactly the shape of evidence this whole stage exists
    to avoid producing.
    """
    client = FakeClient([runs(["true"])])

    with pytest.raises(ProbeCannotDescribeItself, match="substrate_manifest_missing"):
        run_probe([], tmp_path, client=client, substrate_manifest=None)

    assert client.responses.calls == []


def test_the_turn_budget_is_sized_off_what_stage_a_measured(tmp_path):
    """Stage A spent three of four turns asking what it was allowed to do.

    A stage D run has more to do than that and the same habit to pay for, so a
    four-turn limit would stop it mid-sequence — having spent the money and
    answered nothing.
    """
    assert TURNS_STAGE_D_NEEDS > 4


# ── the whole loop, with only the network and the hypervisor standing in ──


@needs_ext4_tools
def test_a_command_runs_and_the_next_turn_reads_the_file_it_wrote(tmp_path):
    """The one sequence stage D exists to establish, start to finish.

    Model asks to run a command; a disk is built from the workspace; the guest
    writes onto it; the disk comes back; the carriage installs it; the turn
    after that reads the file through a different tool; and the bytes reach the
    model. Nothing here is mocked except the socket and the hypervisor.

    The last leg is checked against what was *sent to the model*, not against
    the turn record — the record keeps hashes and no bodies, which is the
    property that makes these runs safe to store, and it means the record
    cannot show that the contents arrived. The request can.
    """
    guest = AGuestThatReallyWritesADisk(writes={"total.txt": "1462 rows\n"})
    client = FakeClient(
        [
            runs(["python3", "count.py"]),
            asks_for(
                "workspace_apply",
                {"operation": "read", "path": "total.txt"},
                call_id="call-2",
            ),
            says_nothing_useful(),
        ]
    )
    outcome = run_probe([], tmp_path, client=client, guest=guest)

    assert outcome.tools_asked_for == ("exec_run", "workspace_apply")
    assert outcome.asked_to_run_something is True
    assert outcome.a_command_really_ran is True
    assert outcome.worked_on_after_running_something is True
    assert outcome.carriage_failures == 0

    # It came off the disk and onto the host, and was collected before the
    # ephemeral workspace was purged -- which is the only reason it still
    # exists to be read here.
    assert outcome.collected["kept"] is True
    kept = Path(outcome.collected["root"]) / "total.txt"
    assert kept.read_text(encoding="utf-8") == "1462 rows\n"
    # And out of the host into the model's own next request, which is the leg
    # that makes this a loop rather than two things that both worked.
    assert "1462 rows" in json.dumps(client.responses.calls[2]["input"])


@needs_ext4_tools
def test_the_files_survive_the_teardown_that_the_policy_requires(tmp_path):
    """Both rules hold at once, and the order is what makes that possible.

    ``workdir: ephemeral-quota`` means the next task must not inherit these
    files, so the workspace is purged. The files are also the entire product of
    the run. A probe that closed without collecting would leave a boot record
    describing deliverables that no longer exist — which reads exactly like a
    model that produced nothing.
    """
    outcome = run_probe(
        [runs(["true"]), says_nothing_useful()],
        tmp_path,
        guest=AGuestThatReallyWritesADisk(writes={"report.md": "# done\n"}),
    )

    assert not (tmp_path / "probe" / "work").exists()
    assert (Path(outcome.collected["root"]) / "report.md").read_text() == "# done\n"
    assert outcome.collected["files"] >= 1


@needs_ext4_tools
def test_the_collection_can_be_sent_somewhere_the_caller_chose(tmp_path):
    outcome = run_probe(
        [runs(["true"]), says_nothing_useful()],
        tmp_path,
        guest=AGuestThatReallyWritesADisk(writes={"report.md": "# done\n"}),
        collect_outputs_into=tmp_path / "deliverables",
    )

    assert outcome.collected["root"] == (tmp_path / "deliverables").as_posix()
    assert (tmp_path / "deliverables" / "report.md").is_file()


@needs_ext4_tools
def test_the_command_the_model_asked_for_is_the_one_on_the_disk(tmp_path):
    """A boot that ran something else would still look like a success."""
    guest = AGuestThatReallyWritesADisk()
    run_probe([runs(["echo", "hello"]), says_nothing_useful()], tmp_path, guest=guest)

    assert "echo" in guest.commands[0]
    assert "/work/ws" in guest.commands[0]


@needs_ext4_tools
def test_one_tool_call_is_one_machine(tmp_path):
    machine = _machine(tmp_path, AGuestThatReallyWritesADisk())
    outcome = run_probe(
        [
            runs(["true"], call_id="c1"),
            runs(["true"], cwd=".", timeout_seconds=61, call_id="c2"),
            says_nothing_useful(),
        ],
        tmp_path,
        boot_one_command=machine,
    )

    assert [row["vm_id"] for row in outcome.machines] == [
        "gdpval-stage-d-0000",
        "gdpval-stage-d-0001",
    ]
    assert len(outcome.boots) == 2


@needs_ext4_tools
def test_a_carriage_that_broke_is_counted_and_not_read_as_an_empty_command(tmp_path):
    """The failure mode that would otherwise read as a model producing nothing."""
    guest = AGuestThatReallyWritesADisk(returns_a_disk=False)
    outcome = run_probe(
        [runs(["true"]), says_nothing_useful()], tmp_path, guest=guest
    )

    assert outcome.carriage_failures == 1
    assert outcome.a_command_really_ran is False
    assert outcome.boots[0]["result"]["error_type"] == "compute_backend_error"


@needs_ext4_tools
def test_a_run_that_booted_on_its_last_turn_has_not_closed_the_loop(tmp_path):
    """Proving the machine is not the same as proving the model can build on it.

    Reported as a finding rather than a failure: the command really ran, and
    what is missing is the turn afterwards.
    """
    outcome = run_probe(
        [runs(["true"]), says_nothing_useful()],
        tmp_path,
        guest=AGuestThatReallyWritesADisk(writes={"made.txt": "x\n"}),
    )

    assert outcome.a_command_really_ran is True
    assert outcome.worked_on_after_running_something is False


def test_a_model_that_never_reached_for_the_machine_is_a_finding_not_an_error(
    tmp_path,
):
    """Stage D records what happened. "It did not use it" is an answer."""
    guest = AGuestThatReallyWritesADisk()
    outcome = run_probe(
        [asks_for("capabilities_query", {"kind": "commands"}), says_nothing_useful()],
        tmp_path,
        guest=guest,
    )

    assert outcome.reached_a_model is True
    assert outcome.asked_to_run_something is False
    assert outcome.a_command_really_ran is False
    assert outcome.worked_on_after_running_something is False
    assert guest.commands == []


def test_a_service_that_never_answered_is_not_reported_as_reached(tmp_path):
    outcome = run_probe([RuntimeError("the route was refused")], tmp_path)

    assert outcome.reached_a_model is False
    assert outcome.resolved_model is None
    assert outcome.turns_taken == 0
    assert outcome.boots == ()


# ── what is written down, and what is deliberately not ────────────────────


def test_the_model_is_not_told_which_tool_to_call(tmp_path):
    """Otherwise the probe proves models follow instructions, not that they choose."""
    for name in PROBE_TOOLS:
        assert name not in PROBE_INSTRUCTIONS

    client = FakeClient([says_nothing_useful()])
    run_probe([], tmp_path, client=client)

    sent = client.responses.calls[0]
    assert {tool["name"] for tool in sent["tools"]} == set(PROBE_TOOLS)


@needs_ext4_tools
def test_nothing_the_model_said_is_kept(tmp_path):
    outcome = run_probe(
        [
            runs(["python3", "-c", "print('my private working out')"]),
            says_nothing_useful("my private working out"),
        ],
        tmp_path,
    )

    written = json.dumps(outcome.as_dict()["model_calls"])
    assert "private working out" not in written
    for row in outcome.ledger:
        assert set(row) == {
            "turn",
            "requested_deployment",
            "resolved_model",
            "input_tokens",
            "output_tokens",
            "history_entries_sent",
            "price_usd",
            "price_missing",
        }


@needs_ext4_tools
def test_the_record_names_the_image_the_commands_actually_ran_in(tmp_path):
    """A boot record with no image behind it cannot be checked afterwards."""
    written = run_probe(
        [runs(["true"]), says_nothing_useful()], tmp_path
    ).as_dict()

    assert written["guest_image"]["digest"] == AN_IMAGE.digest
    assert len(written["substrate_manifest_sha256"]) == 64
    assert json.loads(json.dumps(written))["a_command_really_ran"] is True


def test_an_unpriced_call_makes_the_total_missing_rather_than_zero(tmp_path):
    """Zero would make an unsettled bill look settled."""
    outcome = run_probe([says_nothing_useful()], tmp_path, prices={})

    assert outcome.spent_usd is None
    assert outcome.price_missing is True
    assert outcome.as_dict()["spent_usd"] is None


def test_running_something_is_read_from_the_boots_not_from_the_tool_calls():
    """A model that asked and was refused before launch has run nothing.

    Kept apart on purpose: ``asked_to_run_something`` is about the model and
    ``a_command_really_ran`` is about the machine, and a probe that conflated
    them would report a refused argument list as a successful boot.
    """
    asked_but_refused = StageDProbeOutcome(
        reached_a_model=True,
        resolved_model=MODEL,
        requested_deployment="gpt-5.4",
        resource="a-foundry-resource",
        tools_offered=PROBE_TOOLS,
        tools_asked_for=("exec_run",),
        turns_taken=1,
        stop_reason="turn_limit_reached",
        detail="",
        guest_image=AN_IMAGE.as_record(),
        boots=({"call": 0, "booted": False, "refused_before_launch": "bad argv"},),
    )

    assert asked_but_refused.asked_to_run_something is True
    assert asked_but_refused.a_command_really_ran is False
