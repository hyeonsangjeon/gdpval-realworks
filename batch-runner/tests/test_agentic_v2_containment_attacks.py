"""Judging the seven attacks, and the one way of judging them that would be a lie.

The attacks themselves need a machine. The judging does not, and it is where the
mistake would be: a verdict function that reads a missing observation as "nothing
went wrong" turns a guest that never booted into a clean sweep. Most of this file
is that one property, applied to each attack in turn, because it has to hold for
all seven and not merely for the ones easiest to write.

The second thing held here is that two attacks cannot be answered from inside the
guest. ``user`` and ``credentials`` are facts about the host-side Firecracker
process; inside the machine PID 1 is root and is supposed to be. A judge that
accepted the guest's own uid would pass on a launcher that never dropped
privilege at all, which is the failure the rule exists to prevent.

Nothing here boots anything. This box runs kernel 3.10 and cannot.
"""

from __future__ import annotations

import pytest

from core.agentic_v2_containment_attacks import (
    ATTACKS,
    BOOT_MEMORY,
    BOOT_PROBES,
    BOOT_WALL_CLOCK,
    BOOT_WORKDIR,
    guest_commands,
    judge_all,
)
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY


def _probe_output(**overrides: str) -> str:
    lines = {
        "interfaces": "lo",
        "connect": "connect_probe=refused:OSError",
        "mounts": "/dev/vda / ext4 ro,relatime 0 0",
        "write": "rootfs_write=refused",
        "memory": "MemTotal:        4014520 kB",
        "env": "guest_env=clean",
    }
    lines.update(overrides)
    return "\n".join(
        [
            "== network ==",
            lines["interfaces"],
            lines["connect"],
            "== rootfs ==",
            lines["mounts"],
            lines["write"],
            "== memory bound ==",
            lines["memory"],
            "== credentials ==",
            "env_count=0",
            lines["env"],
            "",
        ]
    )


def _watched(**overrides):
    seen = {
        "pid": 4242,
        "real_uid": 999,
        "expected_uid": 999,
        "supplementary_groups": [],
        "environment_seen": 3,
        "canaries_in_environment": [],
        "descriptors": {"0": "/dev/null", "1": "/dev/null", "2": "/dev/null"},
        "descriptors_reaching_the_orchestrator": [],
        "standard_descriptors": {
            "0": "/dev/null",
            "1": "/dev/null",
            "2": "/dev/null",
        },
    }
    seen.update(overrides)
    return seen


def _clean_sweep(**overrides):
    """Evidence in which all seven rules held, before any override breaks one."""
    evidence = {
        "boots": {
            BOOT_PROBES: {
                "outcome": "booted",
                "results": {"/out/stdout": _probe_output()},
                "watched": _watched(),
            },
            BOOT_WORKDIR: {
                "outcome": "booted",
                "results": {
                    "/out/stdout": (
                        "quota_mib_configured=256\n"
                        "dd: error writing '/work/gdpval-filler': No space left "
                        "on device\nrc=1\n"
                    )
                },
            },
            BOOT_MEMORY: {
                "outcome": "booted",
                "results": {
                    "/out/stdout": (
                        "MemTotal:        4036852 kB\n"
                        "allocated_mib=64\n"
                        "allocated_mib=3840\n"
                        "rc=137\n"
                    ),
                    "/out/stderr": "Killed\n",
                },
            },
            BOOT_WALL_CLOCK: {
                "outcome": "stopped_by_the_deadline",
                "stopped_by_the_deadline": True,
                "ran_for_seconds": 45.04,
                "deadline_seconds": 45,
                "teardown": {"all_gone": True},
            },
        }
    }
    for boot, patch in overrides.items():
        evidence["boots"][boot] = patch
    return evidence


def _verdict(judgement, attack_id):
    return next(v for v in judgement["verdicts"] if v["id"] == attack_id)


# --------------------------------------------------------------------------
# the property the whole file exists for
# --------------------------------------------------------------------------


def test_nothing_at_all_stops_nothing_at_all():
    """A run that produced no evidence is seven failures, not seven passes.

    This is the shape of the mistake worth guarding: a guest that panicked on
    boot leaves the same silence as a guest that was contained, and the only
    thing separating them is which way the judge resolves an absence.
    """
    judgement = judge_all({})

    assert judgement["stopped"] == 0
    assert judgement["all_seven_stopped"] is False
    assert len(judgement["escapes"]) == 7
    for verdict in judgement["verdicts"]:
        assert verdict["stopped"] is False
        assert verdict["evidence"], "a verdict with no sentence behind it"


@pytest.mark.parametrize("attack", ATTACKS, ids=lambda a: a["id"])
def test_each_attack_fails_when_its_own_boot_produced_nothing(attack):
    """Dropping one boot must fail that boot's attacks and no others.

    Checked per attack rather than in aggregate, because a judge that reads the
    wrong boot's output would still show seven verdicts and would still fail
    when everything is missing — it would only be wrong in the case that matters.
    """
    evidence = _clean_sweep()
    del evidence["boots"][attack["boot"]]

    judgement = judge_all(evidence)
    assert _verdict(judgement, attack["id"])["stopped"] is False


def test_a_probe_that_did_not_report_is_not_a_probe_that_passed():
    """An empty stdout from a machine that booted is still no observation.

    The distinction matters because ``outcome: booted`` looks like success and
    the attacks are judged on what came back, not on whether the machine ran.
    """
    judgement = judge_all(
        _clean_sweep(
            **{BOOT_PROBES: {"outcome": "booted", "results": {"/out/stdout": ""}}}
        )
    )

    assert _verdict(judgement, "network")["stopped"] is False
    assert _verdict(judgement, "read-only-root")["stopped"] is False


def test_the_evidence_that_holds_says_all_seven_stopped():
    judgement = judge_all(_clean_sweep())

    assert judgement["all_seven_stopped"] is True
    assert judgement["stopped"] == 7
    assert judgement["escapes"] == []


# --------------------------------------------------------------------------
# each rule, broken one at a time
# --------------------------------------------------------------------------


def test_a_connection_that_opened_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {
                        "/out/stdout": _probe_output(connect="connect_probe=CONNECTED")
                    },
                    "watched": _watched(),
                }
            }
        )
    )
    assert _verdict(judgement, "network")["stopped"] is False


def test_an_interface_beyond_loopback_is_an_escape_even_with_no_connection():
    """``network: none`` is about the device, not about whether it was used.

    A guest handed a tap device that happened to reach nothing today is one
    routing change away from reaching everything, and the rule says the device
    is not there.
    """
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": _probe_output(interfaces="lo\neth0")},
                    "watched": _watched(),
                }
            }
        )
    )
    assert _verdict(judgement, "network")["stopped"] is False


def test_a_root_that_refused_a_write_but_is_mounted_read_write_is_an_escape():
    """The refusal alone is a permission bit, and a permission bit is not the rule.

    A root the kernel mounted read-write is one ``mount -o remount,rw`` from
    being writable, and the guest is root inside its own machine.
    """
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {
                        "/out/stdout": _probe_output(
                            mounts="/dev/vda / ext4 rw,relatime 0 0"
                        )
                    },
                    "watched": _watched(),
                }
            }
        )
    )
    assert _verdict(judgement, "read-only-root")["stopped"] is False


def test_a_write_that_succeeded_on_the_root_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {
                        "/out/stdout": _probe_output(write="rootfs_write=SUCCEEDED")
                    },
                    "watched": _watched(),
                }
            }
        )
    )
    assert _verdict(judgement, "read-only-root")["stopped"] is False


def test_a_fill_past_the_quota_that_succeeded_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_WORKDIR: {
                    "results": {"/out/stdout": "quota_mib_configured=256\nrc=0\n"}
                }
            }
        )
    )
    assert _verdict(judgement, "workdir-quota")["stopped"] is False


def test_a_guest_that_sees_more_memory_than_the_rule_allows_is_an_escape():
    """Read before the allocation, because the allocation can fail for other reasons.

    A ``dd`` that failed on a machine which can see 32 GiB says nothing about
    ``memory_mib``; what says something is the total the guest was given.
    """
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_MEMORY: {
                    "results": {
                        "/out/stdout": "MemTotal:       32000000 kB\nrc=1\n"
                    }
                }
            }
        )
    )
    assert _verdict(judgement, "memory")["stopped"] is False


def test_an_allocation_past_the_bound_that_succeeded_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_MEMORY: {
                    "results": {"/out/stdout": "MemTotal: 4014520 kB\nrc=0\n"}
                }
            }
        )
    )
    assert _verdict(judgement, "memory")["stopped"] is False


def test_an_allocator_that_reported_holding_it_all_is_an_escape():
    """``rc`` comes from the shell, and the shell is not what did the allocating.

    A machine that let the guest hold every requested byte and then returned a
    non-zero status — a tidy-up that failed, a signal on the way out — would pass
    on the exit status alone, while the bound it was meant to enforce did not
    hold.
    """
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_MEMORY: {
                    "results": {
                        "/out/stdout": (
                            "MemTotal: 4014520 kB\nallocated_mib=6144\n"
                            "ALLOCATED_ALL\nrc=1\n"
                        )
                    }
                }
            }
        )
    )
    assert _verdict(judgement, "memory")["stopped"] is False


def test_holding_more_than_the_bound_is_an_escape_however_the_guest_ended():
    """The high-water mark is the rule; the exit status is only how it ended.

    Every page counted there was written to, and a guest with no swap cannot give
    touched anonymous memory back — so a number past the bound is memory the
    machine actually handed over.
    """
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_MEMORY: {
                    "results": {
                        "/out/stdout": (
                            "MemTotal: 4014520 kB\nallocated_mib=5120\nrc=137\n"
                        )
                    }
                }
            }
        )
    )
    verdict = _verdict(judgement, "memory")
    assert verdict["stopped"] is False
    assert "5120" in verdict["evidence"]


def test_the_verdict_says_how_far_the_allocation_got():
    """"Something stopped it" and "it stopped 102 MiB short" are different findings."""
    judgement = judge_all(_clean_sweep())
    assert "3840 MiB" in _verdict(judgement, "memory")["evidence"]


def test_a_hanging_guest_that_finished_on_its_own_did_not_test_the_deadline():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_WALL_CLOCK: {
                    "outcome": "booted",
                    "stopped_by_the_deadline": False,
                    "teardown": {"all_gone": True},
                }
            }
        )
    )
    assert _verdict(judgement, "wall-clock")["stopped"] is False


def test_a_deadline_that_fired_and_left_the_chroot_behind_is_not_a_stop():
    """The work disk lives in that chroot, and it holds whatever the guest wrote."""
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_WALL_CLOCK: {
                    "outcome": "stopped_by_the_deadline",
                    "stopped_by_the_deadline": True,
                    "ran_for_seconds": 45.0,
                    "teardown": {"all_gone": False},
                }
            }
        )
    )
    assert _verdict(judgement, "wall-clock")["stopped"] is False


# --------------------------------------------------------------------------
# the two that the guest cannot answer
# --------------------------------------------------------------------------


def test_a_firecracker_process_still_running_as_root_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": _probe_output()},
                    "watched": _watched(real_uid=0),
                }
            }
        )
    )
    verdict = _verdict(judgement, "privileged-user")
    assert verdict["stopped"] is False
    assert "root" in verdict["evidence"]


def test_a_guest_running_as_root_inside_its_own_machine_is_not_the_rule():
    """PID 1 is uid 0 in every one of these guests, including the ones that pass.

    If the judge looked at the guest's uid this would fail, and the rule would
    be untestable — which is the point of reading it from the host instead.
    """
    guest_says_root = _probe_output()
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": guest_says_root},
                    "watched": _watched(real_uid=999),
                }
            }
        )
    )
    assert _verdict(judgement, "privileged-user")["stopped"] is True


def test_supplementary_groups_on_the_jailed_process_are_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": _probe_output()},
                    "watched": _watched(supplementary_groups=[27]),
                }
            }
        )
    )
    assert _verdict(judgement, "privileged-user")["stopped"] is False


def test_a_canary_in_the_processs_environment_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": _probe_output()},
                    "watched": _watched(
                        canaries_in_environment=["GDPVAL_C3_CANARY_TOKEN"]
                    ),
                }
            }
        )
    )
    assert _verdict(judgement, "inherited-credentials")["stopped"] is False


def test_a_clean_environment_with_the_console_still_attached_is_an_escape():
    """The half that a dropped ``--daemonize`` would silently reopen.

    The jailer wipes the environment whatever else is passed to it, so an
    attack that checked only the environment would pass on a launcher that had
    lost the flag — and with the flag gone the guest's console is whatever the
    orchestrator was writing to.
    """
    attached = {"0": "/dev/null", "1": "/var/log/orchestrator.log", "2": "/dev/null"}
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": _probe_output()},
                    "watched": _watched(
                        standard_descriptors=attached, descriptors=attached
                    ),
                }
            }
        )
    )
    verdict = _verdict(judgement, "inherited-credentials")
    assert verdict["stopped"] is False
    assert "daemonize" in verdict["evidence"]


def test_a_descriptor_reaching_the_orchestrator_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": _probe_output()},
                    "watched": _watched(
                        descriptors_reaching_the_orchestrator=[
                            "9 -> /var/tmp/gdpval-c3/c3-canary-token.txt"
                        ]
                    ),
                }
            }
        )
    )
    assert _verdict(judgement, "inherited-credentials")["stopped"] is False


def test_the_environment_alone_is_not_enough_to_pass_the_credential_rule():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {"/out/stdout": _probe_output()},
                    "watched": _watched(descriptors=None, standard_descriptors=None),
                }
            }
        )
    )
    verdict = _verdict(judgement, "inherited-credentials")
    assert verdict["stopped"] is False
    assert "environment alone is not the rule" in verdict["evidence"]


def test_a_credential_shaped_name_inside_the_guest_is_an_escape():
    judgement = judge_all(
        _clean_sweep(
            **{
                BOOT_PROBES: {
                    "results": {
                        "/out/stdout": _probe_output(
                            env="AZURE_OPENAI_API_KEY=sk-x\nguest_env=CARRIES SOMETHING"
                        )
                    },
                    "watched": _watched(),
                }
            }
        )
    )
    assert _verdict(judgement, "inherited-credentials")["stopped"] is False


# --------------------------------------------------------------------------
# the attacks themselves, and what they are sized against
# --------------------------------------------------------------------------


def test_every_verdict_names_the_rule_it_enforced_and_that_rules_value():
    """"Stopped" without a rule beside it is an assertion rather than a finding."""
    judgement = judge_all(_clean_sweep())

    for verdict in judgement["verdicts"]:
        assert verdict["rule_it_enforced"] in REQUIRED_MICROVM_POLICY
        assert verdict["rule_value"] == REQUIRED_MICROVM_POLICY[verdict["rule_it_enforced"]]


def test_the_seven_attacks_cover_seven_different_rules():
    rules = [attack["rule"] for attack in ATTACKS]
    assert len(ATTACKS) == 7
    assert len(set(rules)) == 7


def test_the_overshoot_is_taken_from_the_rule_and_not_written_as_a_number():
    """A raised bound must not leave an attack probing below it.

    An attack that stops short of the limit passes without the limit ever being
    reached, and it passes more comfortably the more the bound is raised.
    """
    raised = dict(REQUIRED_MICROVM_POLICY) | {
        "workdir_quota_mib": 1024,
        "memory_mib": 8192,
    }
    commands = guest_commands(raised)

    assert "count=2048" in commands[BOOT_WORKDIR]
    assert "12288 * 1024 * 1024" in commands[BOOT_MEMORY]
    assert "quota_mib_configured=1024" in commands[BOOT_WORKDIR]


def test_the_memory_attack_reports_from_a_shell_that_allocates_nothing():
    """The regression from the first C3 run, where the reporter was the casualty.

    ``rc=$?`` inside a command substitution runs in a fork. When the machine
    filled, that fork was what the kernel took, so the attack came back with no
    exit status at all — judged, correctly, as an attack that never ran, while
    the bound had in fact held. The report has to be made by a process that is
    never a candidate.
    """
    allocate = guest_commands()[BOOT_MEMORY]

    assert "$(dd" not in allocate, "the reporter is inside a fork again"
    assert "wait \"$allocator\"" in allocate
    assert allocate.index('wait "$allocator"') < allocate.index('echo "rc=$?"')


def test_the_memory_attack_allocates_memory_that_is_charged_to_it():
    """tmpfs is shmem, and shmem belongs to no process the OOM killer can weigh.

    The first run filled a tmpfs, the kernel found nothing large to pick, and it
    picked a bystander. Anonymous memory that has been written to is charged to
    the allocator, which is the only way this attack points the kernel at itself.
    """
    allocate = guest_commands()[BOOT_MEMORY]
    runs = "\n".join(
        line for line in allocate.splitlines() if not line.lstrip().startswith("#")
    )

    assert "tmpfs" not in runs
    assert "/dev/shm" not in runs
    assert "block[offset] = 1" in runs, "untouched pages are address space"


def test_the_memory_attack_reports_as_it_goes_and_not_only_at_the_end():
    """A process the kernel kills does not reach its last line."""
    assert "allocated_mib=" in guest_commands()[BOOT_MEMORY]


def test_the_quota_attack_removes_its_filler_before_the_guest_ends():
    """The work disk is the only channel, and this attack's job is to fill it.

    A guest that finishes with the disk full cannot write the answer, and the
    absent answer would be judged a failure — which would be right, and would
    also be the attack destroying its own evidence rather than the rule holding.
    """
    fill = guest_commands()[BOOT_WORKDIR]
    assert "rm -f /work/gdpval-filler" in fill
    assert fill.index("rm -f /work/gdpval-filler") < fill.rindex("echo")


def test_the_probe_boot_holds_itself_open_long_enough_to_be_watched():
    """C2's guest was gone in 1.269 seconds. Two of the attacks need it alive."""
    probes = guest_commands()[BOOT_PROBES]
    assert "sleep 8" in probes


def test_the_probe_boot_does_not_reach_for_anything_the_policy_closed():
    probes = guest_commands()[BOOT_PROBES]
    for word in ("vsock", "curl", "wget", "ssh", "nc "):
        assert word not in probes
