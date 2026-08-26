"""The containment rules: that they are complete, numbered, and hard to weaken.

Six questions have to be answered before a set of settings is a containment
rather than a gesture — where a command may write, whether it can reach the
network, how much memory it gets, how long it may run, who it runs as, and what
happens when it exceeds any of them. Until 2026-08-26 only the first two were
written down, and the working directory said "there is a quota" without ever
saying what the quota was.

These tests do three things and no more. They check that all six are answered;
they check that the numbers which are derived from something else still agree
with what they were derived from; and they check that weakening any one of them
is refused rather than accepted.

What they deliberately do not do is start a virtual machine, run a command,
exceed a limit and watch it stop. That is the test these rules will eventually
need, and it cannot be written yet: no machine in play can host the containment,
and no code turns these rules into arguments for starting one. Writing a
pretend version of it would be worse than leaving it out, because a passing test
named after a thing that never happened is how an unenforced rule comes to look
enforced. core/agentic_v2_containment_readiness.py reports the gap instead.

Nothing here calls a model, runs a command, or spends money.
"""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest

from core.agentic_v2_fixture_backend import (
    _MAX_FINAL_BYTES,
    _MAX_WORKSPACE_BYTES,
)
from core.agentic_v2_substrate import (
    MICROVM_MEMORY_MIB,
    MICROVM_WALL_CLOCK_SECONDS,
    MICROVM_WORKDIR_QUOTA_MIB,
    REQUIRED_MICROVM_POLICY,
    SUPPLY_CHAIN_HOST_FACTS,
    AgenticV2SubstrateManifest,
    _SUPPLY_CHAIN_RULE_NAMES,
    containment_rules_that_disagree,
    supply_chain_microvm_block,
)
from core.agentic_v2_supply_chain import SupplyChainPolicy

MANIFEST_PATH = Path("sandbox/agentic_v2_capabilities.json")
SIGNED_POLICY_PATH = Path("security/agentic-v2-supply-chain-policy.json")
STAGE_ONE_PLAN_PATH = Path(
    "experiments/execution_envelope/agentic_stage_one_plan.yaml"
)

A_MEBIBYTE = 1024 * 1024


def _manifest_document() -> dict:
    return deepcopy(AgenticV2SubstrateManifest.load(MANIFEST_PATH).document)


def _signed_policy() -> dict:
    return json.loads(SIGNED_POLICY_PATH.read_text(encoding="utf-8"))


# ── All six questions are answered ────────────────────────────────────────


def test_every_one_of_the_six_questions_has_an_answer():
    """A containment that leaves one of these open is not a containment.

    Named individually rather than counted, so that a failure says which
    question stopped being answered instead of saying that a number changed.
    """
    assert REQUIRED_MICROVM_POLICY["workdir"] == "ephemeral-quota"
    assert REQUIRED_MICROVM_POLICY["workdir_quota_mib"] == MICROVM_WORKDIR_QUOTA_MIB
    assert REQUIRED_MICROVM_POLICY["network"] == "none"
    assert REQUIRED_MICROVM_POLICY["memory_mib"] == MICROVM_MEMORY_MIB
    assert REQUIRED_MICROVM_POLICY["wall_clock_seconds"] == MICROVM_WALL_CLOCK_SECONDS
    assert REQUIRED_MICROVM_POLICY["user"] == "jailer-unprivileged"
    assert REQUIRED_MICROVM_POLICY["on_breach"] == "stop-and-report"


def test_no_limit_is_written_without_a_number():
    """"There is a quota" is not a quota, and this is what caught that.

    Every rule whose name ends in a unit has to carry a positive number. A rule
    that names a unit and then holds a word is a rule nobody can apply.
    """
    for name, value in REQUIRED_MICROVM_POLICY.items():
        if name.endswith(("_mib", "_seconds")):
            assert isinstance(value, int) and not isinstance(value, bool), (
                f"containment rule {name!r} names a unit but holds {value!r}"
            )
            assert value > 0, f"containment rule {name!r} is not a limit at {value!r}"


def test_the_breach_rule_neither_carries_on_nor_goes_quiet():
    """The two ways a limit fails to be one.

    Section 7 of the specification asks stage three to fail loudly when its
    containment is unavailable. A rule that has been exceeded is a containment
    that is not holding, so the same answer applies: stop, and say so.
    """
    assert REQUIRED_MICROVM_POLICY["on_breach"] == "stop-and-report"
    assert "stop" in REQUIRED_MICROVM_POLICY["on_breach"]
    assert "report" in REQUIRED_MICROVM_POLICY["on_breach"]


# ── The numbers that are derived still agree with their source ────────────


def test_the_disk_is_not_smaller_than_the_tools_already_allow():
    """The working disk has to hold what the tool layer already accepts.

    core/agentic_v2_fixture_backend.py lets a model hold a workspace and hand
    back a set of finished files, each with its own ceiling. A disk smaller than
    those two together would let the tool layer accept a write the disk cannot
    hold, and the failure would surface as a disk error rather than as the
    ceiling the tool layer meant to apply.

    Raising either backend ceiling past this is what this test catches.
    """
    what_the_tools_allow_mib = (_MAX_WORKSPACE_BYTES + _MAX_FINAL_BYTES) // A_MEBIBYTE

    assert MICROVM_WORKDIR_QUOTA_MIB >= what_the_tools_allow_mib, (
        f"the work disk is {MICROVM_WORKDIR_QUOTA_MIB} MiB but the tool layer "
        f"already accepts {what_the_tools_allow_mib} MiB of writes"
    )


def test_the_clock_matches_the_one_the_other_run_places_are_held_to():
    """A containment that cut a task off early would bias the comparison.

    The three run places are compared against each other. If this one stopped a
    task sooner than the others do, it would look worse for a reason that had
    nothing to do with the model, and the comparison would be measuring the
    containment instead.
    """
    plan = STAGE_ONE_PLAN_PATH.read_text(encoding="utf-8")
    stated = [
        line for line in plan.splitlines() if "per_task_timeout_seconds:" in line
    ]

    assert stated, f"{STAGE_ONE_PLAN_PATH} no longer states a per-task timeout"
    for line in stated:
        seconds = int(line.split(":", 1)[1].strip())
        assert seconds == MICROVM_WALL_CLOCK_SECONDS, (
            f"the containment stops a command after {MICROVM_WALL_CLOCK_SECONDS} "
            f"seconds but the plan gives a task {seconds}"
        )


def test_the_memory_rule_says_it_was_picked_rather_than_derived():
    """The one number with nothing behind it, and it has to admit that.

    Every other limit here points at something it was derived from. This one
    does not, and a reader deciding whether to change it needs to know which
    kind of number they are looking at.
    """
    from core import agentic_v2_substrate

    source = Path(agentic_v2_substrate.__file__).read_text(encoding="utf-8")
    documentation = " ".join(
        source.split("MICROVM_MEMORY_MIB = ")[1].split('"""')[1].split()
    )

    assert "Picked, not derived" in documentation
    assert "None of the three run places in the comparison caps memory" in documentation


# ── Weakening any one rule is refused ─────────────────────────────────────


@pytest.mark.parametrize(
    ("rule", "weakened_to"),
    [
        ("network", "allowlist"),
        ("network", "host"),
        ("rootfs", "writable"),
        ("workdir", "persistent"),
        ("workdir_quota_mib", MICROVM_WORKDIR_QUOTA_MIB * 4),
        ("memory_mib", MICROVM_MEMORY_MIB * 4),
        ("wall_clock_seconds", MICROVM_WALL_CLOCK_SECONDS * 4),
        ("user", "root"),
        ("on_breach", "continue"),
        ("on_breach", "log-and-continue"),
        ("runtime", "docker"),
        ("required", False),
    ],
)
def test_a_manifest_that_weakens_one_rule_is_refused(rule, weakened_to):
    """One test per rule, because one rule is what gets changed at a time.

    A manifest is the file that would travel with a built image, so this is the
    check that catches a rule loosened somewhere between here and the machine
    that runs it.
    """
    document = _manifest_document()
    document["microvm"][rule] = weakened_to

    with pytest.raises(ValueError, match="microvm policy"):
        AgenticV2SubstrateManifest.from_mapping(document)


def test_a_manifest_that_drops_a_rule_entirely_is_refused():
    """Deleting a limit is the quietest way to remove it."""
    for rule in sorted(REQUIRED_MICROVM_POLICY):
        document = _manifest_document()
        del document["microvm"][rule]

        with pytest.raises(ValueError, match="microvm policy"):
            AgenticV2SubstrateManifest.from_mapping(document)


def test_the_manifest_on_disk_states_every_rule_and_states_them_the_same():
    """The file that ships has to say what the code requires, exactly.

    Not "contains" — equals. A manifest holding an extra containment setting
    nobody checks is the drift this whole change is about.
    """
    assert _manifest_document()["microvm"] == REQUIRED_MICROVM_POLICY


# ── The two written-down copies still agree ───────────────────────────────


def test_the_signed_policy_and_the_rules_agree_today():
    assert containment_rules_that_disagree(_signed_policy()["microvm"]) == []


@pytest.mark.parametrize(
    ("their_rule", "weakened_to"),
    [
        ("runtime", "docker"),
        ("network", "allowlist"),
        ("read_only_rootfs", False),
        ("ephemeral_work_disk", False),
    ],
)
def test_a_rule_weakened_in_the_signed_policy_alone_is_caught(their_rule, weakened_to):
    """Two copies of a rule is two chances to weaken it and one to notice.

    Before this check, the signed policy could be loosened while the substrate
    rules stood, and both files went on validating. The names differ between the
    two — one says ``read_only_rootfs: true`` where the other says
    ``rootfs: "read-only"`` — which is what made the drift hard to see by eye.
    """
    policy = _signed_policy()
    policy["microvm"][their_rule] = weakened_to
    drifted = containment_rules_that_disagree(policy["microvm"])

    assert len(drifted) == 1
    assert "disagrees between the two places it is written down" in drifted[0]
    assert repr(weakened_to) in drifted[0]

    with pytest.raises(ValueError, match="containment drift"):
        SupplyChainPolicy.from_mapping(policy)


def test_a_signed_policy_missing_its_containment_block_is_caught():
    assert containment_rules_that_disagree(None) == [
        "the signed policy's containment block is not a set of rules"
    ]


@pytest.mark.parametrize(
    ("our_rule", "weakened_to"),
    [
        ("runtime", "docker"),
        ("network", "allowlist"),
        ("rootfs", "writable"),
        ("workdir", "persistent"),
    ],
)
def test_a_rule_weakened_on_our_side_alone_is_caught_too(
    our_rule, weakened_to, monkeypatch
):
    """The comparison guards both copies, not just the signed one.

    Easy to assume it only watches the file that arrives from outside. It does
    not: weakening the rule here while the signed policy stands is the same
    disagreement seen from the other side, and it is refused the same way.
    """
    monkeypatch.setitem(REQUIRED_MICROVM_POLICY, our_rule, weakened_to)
    drifted = containment_rules_that_disagree(_signed_policy()["microvm"])

    assert len(drifted) == 1
    assert repr(weakened_to) in drifted[0]

    with pytest.raises(ValueError, match="containment drift"):
        SupplyChainPolicy.load(SIGNED_POLICY_PATH)


def test_the_signed_policy_block_is_derived_rather_than_written_out_again():
    """The third copy is gone, and this is what keeps it gone.

    A rule added to the containment rules and not to the translation between the
    two namings would leave the derived block short of it, so the signed policy
    would be accepted without stating the new rule at all.
    """
    derived = supply_chain_microvm_block()

    assert derived == _signed_policy()["microvm"]
    assert set(derived) == set(_SUPPLY_CHAIN_RULE_NAMES) | set(
        SUPPLY_CHAIN_HOST_FACTS
    )
    for their_name, (our_name, _, _) in _SUPPLY_CHAIN_RULE_NAMES.items():
        assert our_name in REQUIRED_MICROVM_POLICY, (
            f"the signed policy's {their_name!r} is translated to {our_name!r}, "
            "which is not one of the containment rules"
        )


def test_the_signed_policy_as_it_stands_still_validates():
    """The change must refuse drift without refusing the file that is correct."""
    assert SupplyChainPolicy.load(SIGNED_POLICY_PATH).document["microvm"] == (
        _signed_policy()["microvm"]
    )


# ── What is not tested here, and why ──────────────────────────────────────


def test_no_test_in_this_file_pretends_a_rule_was_enforced():
    """The honesty guard on the file itself.

    Every rule above is checked by reading a written-down value. None of them is
    checked by exceeding a limit and observing a stop, because nothing here can
    start a machine to exceed it on. A test that ran something would be a test
    that had stopped answering the question in its own name.

    Read with the Python parser rather than by searching the text, so that this
    test does not trip over its own list of the names it is looking for.
    """
    ways_to_run_something = {"subprocess", "os", "pty", "asyncio", "docker"}

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not imported & ways_to_run_something, (
        f"this file now imports {sorted(imported & ways_to_run_something)}, "
        "which is how a test that reads a value turns into one that runs a "
        "command"
    )
    assert "it cannot be written yet" in __doc__
