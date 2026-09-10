"""The containment rules, as the arguments that would apply them.

Stage C0 finished with eleven rules written down and nothing turning any of them
into an argument. This file is the check on the half of that gap
core/agentic_v2_microvm_launch.py closes: every rule has to appear in the built
arguments, and a rule that cannot be expressed has to stop the build rather than
be quietly left out.

**What these tests can and cannot establish.** They read a document. They can
show that ``memory_mib`` reached ``mem_size_mib``, that no network interface is
configured, that the three devices which would defeat a rule are absent, and
that weakening any rule is refused — all without hardware, which is why they can
run here at all. They cannot show that any of those arguments has the effect its
name suggests. A machine has to be started for that, and stage C2 starts one on
the host stage B measured; stage C3 attacks it. Neither is pretended here.

The distinction matters because the failure this stage exists to catch is a rule
that reads as enforced and is not, and a test file that blurred the line between
"the argument is present" and "the boundary holds" would be an instance of it.

Nothing here calls a model, runs a command, starts a machine, or spends money.
"""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from core.agentic_v2_microvm_launch import (
    CGROUP_MEMORY_FILE_BY_VERSION,
    DEVICES_THAT_MUST_BE_ABSENT,
    FLAGS_THAT_WOULD_WEAKEN_THE_JAIL,
    HOST_SIDE_MEMORY_OVERHEAD_MIB,
    IN_JAIL_CONFIG,
    IN_JAIL_KERNEL,
    IN_JAIL_ROOTFS,
    IN_JAIL_WORK_DISK,
    LaunchRefused,
    build_launch_plan,
    devices_that_would_reopen_a_closed_rule,
    flags_that_would_weaken_the_jail,
    rules_this_builder_accounts_for,
)
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY

A_MEBIBYTE = 1024 * 1024


@pytest.fixture
def images(tmp_path):
    """A kernel and a root filesystem, as files. Neither is bootable.

    The builder hashes whatever it is given and puts the digest in the plan, so
    the bytes only have to exist and be distinguishable. A test that needed a
    real kernel image would be a test that could not run here, and the thing it
    would establish — that the machine boots — is C2's, not this file's.
    """
    kernel = tmp_path / "vmlinux"
    kernel.write_bytes(b"not a kernel")
    rootfs = tmp_path / "rootfs.ext4"
    rootfs.write_bytes(b"not a root filesystem")
    return {"kernel_path": kernel, "rootfs_path": rootfs}


@pytest.fixture
def plan(images, tmp_path):
    return build_launch_plan(
        vm_id="stage-c1",
        firecracker_binary="/usr/bin/firecracker",
        work_disk_path=tmp_path / "work.ext4",
        uid=1000,
        gid=1000,
        vcpu_count=2,
        cgroup_version=2,
        **images,
    )


def _build(images, tmp_path, **overrides):
    arguments = {
        "vm_id": "stage-c1",
        "firecracker_binary": "/usr/bin/firecracker",
        "work_disk_path": tmp_path / "work.ext4",
        "uid": 1000,
        "gid": 1000,
        "vcpu_count": 2,
        "cgroup_version": 2,
        **images,
    }
    arguments.update(overrides)
    return build_launch_plan(**arguments)


def _argument_after(argv, flag):
    """The value the jailer would read for a flag, or None if it is not there."""
    for index, item in enumerate(argv[:-1]):
        if item == flag:
            return argv[index + 1]
    return None


# ── Every rule reaches an argument ────────────────────────────────────────


def test_every_rule_in_the_policy_is_accounted_for():
    """The check that makes a dropped rule loud instead of invisible.

    Named against the policy rather than against a count, so that a rule added
    to core.agentic_v2_substrate and not to the builder fails here with the
    rule's own name rather than with a number that moved.
    """
    unaccounted = sorted(set(REQUIRED_MICROVM_POLICY) - rules_this_builder_accounts_for())

    assert unaccounted == [], (
        f"the policy has {unaccounted} and the builder turns none of them into "
        "an argument, so a report asking whether the translation is complete "
        "would be answered yes on an incomplete translation"
    )


def test_the_runtime_rule_names_the_binary_the_jailer_execs(plan):
    exec_file = _argument_after(plan["jailer"]["argv"], "--exec-file")

    assert exec_file == "/usr/bin/firecracker"
    assert REQUIRED_MICROVM_POLICY["runtime"] in Path(exec_file).name


def test_a_binary_the_jailer_would_reject_is_refused_here_first(images, tmp_path):
    """The jailer requires 'firecracker' in the name of its --exec-file.

    Refused here rather than left to the jailer, because a refusal at build time
    names the rule and a refusal at launch time names a path.
    """
    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, firecracker_binary="/usr/bin/qemu-system-x86_64")

    assert refusal.value.rule == "runtime"


def test_the_network_rule_configures_no_interface_and_joins_no_namespace(plan):
    """Both halves, because either one alone would leave a way in.

    An empty interface list and an absent key mean the same thing to
    Firecracker, so the assertion is that nothing is configured rather than that
    a particular spelling is present.
    """
    assert plan["firecracker"]["config"].get("network-interfaces", []) == []
    assert "--netns" not in plan["jailer"]["argv"]


def test_the_rootfs_rule_is_said_to_firecracker_and_to_the_kernel(plan):
    """One of the two is Firecracker's and the other is the guest's.

    A drive marked read-only that the guest is not told to mount read-only
    fails at boot in a way that reads as a broken image rather than as a rule
    doing its job.
    """
    config = plan["firecracker"]["config"]
    root = [item for item in config["drives"] if item["is_root_device"]]

    assert len(root) == 1
    assert root[0]["is_read_only"] is True
    assert root[0]["path_on_host"] == IN_JAIL_ROOTFS
    assert " ro" in config["boot-source"]["boot_args"]


def test_the_workdir_rule_is_a_second_drive_that_is_writable(plan):
    config = plan["firecracker"]["config"]
    work = [
        item
        for item in config["drives"]
        if item["path_on_host"] == IN_JAIL_WORK_DISK
    ]

    assert len(work) == 1
    assert work[0]["is_root_device"] is False
    assert work[0]["is_read_only"] is False


def test_the_quota_bounds_the_image_and_any_single_file_in_it(plan):
    """Two bounds because they bound different things.

    The image size is what bounds the total. ``fsize`` is what stops one file
    being the whole of it, and the jailer documents that value in bytes.

    Asserted as the value *after* ``--resource-limit`` rather than as a string
    somewhere in the argument list. ``fsize=...`` is its own list element, so a
    check that only looked for it would go on passing with the flag that carries
    it deleted — a bound that reads as applied and is a loose word on a command
    line.
    """
    quota = REQUIRED_MICROVM_POLICY["workdir_quota_mib"]
    work = [
        item for item in plan["place_in_jail"] if item["in_jail"] == IN_JAIL_WORK_DISK
    ]

    assert work[0]["size_mib"] == quota
    assert work[0]["how"] == "create-empty"
    assert _argument_after(plan["jailer"]["argv"], "--resource-limit") == (
        f"fsize={quota * A_MEBIBYTE}"
    )


def test_the_memory_rule_is_applied_inside_the_guest_and_outside_it(plan):
    """The guest-visible bound, and the host-side one underneath it.

    The host bound has to be the larger of the two: it covers the guest's memory
    plus the monitor's own, and a host bound equal to the guest bound would stop
    the monitor rather than the command that went over.
    """
    memory = REQUIRED_MICROVM_POLICY["memory_mib"]
    argv = plan["jailer"]["argv"]

    assert plan["firecracker"]["config"]["machine-config"]["mem_size_mib"] == memory

    written = _argument_after(argv, "--cgroup")
    name, _, value = written.partition("=")

    assert name == CGROUP_MEMORY_FILE_BY_VERSION[2]
    assert int(value) == (memory + HOST_SIDE_MEMORY_OVERHEAD_MIB) * A_MEBIBYTE
    assert int(value) > memory * A_MEBIBYTE


def test_the_clock_rule_becomes_a_host_side_deadline_with_a_pid_to_use(plan):
    """A guest cannot be trusted to time itself, so the deadline is outside it.

    The PID file is what a deadline has to act on. The jailer writes it inside
    the jail, which is a path on the host, and a deadline with no process to
    stop would be a limit in name only.
    """
    assert (
        plan["host_side"]["deadline_seconds"]
        == REQUIRED_MICROVM_POLICY["wall_clock_seconds"]
    )
    assert plan["host_side"]["pid_file"] == (
        plan["host_side"]["chroot_dir"] + "/firecracker.pid"
    )


def test_the_user_rule_is_two_flags_and_neither_may_be_root(plan):
    argv = plan["jailer"]["argv"]

    assert _argument_after(argv, "--uid") == "1000"
    assert _argument_after(argv, "--gid") == "1000"


@pytest.mark.parametrize("account", ["uid", "gid"])
def test_root_for_the_command_is_refused_by_name(account, images, tmp_path):
    """Not a warning, not a fallback. 0 is root and the rule says otherwise."""
    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, **{account: 0})

    assert refusal.value.rule == "user"
    assert account in str(refusal.value)


def test_the_credential_rule_rests_on_a_flag_and_the_flag_is_passed(plan):
    """The half of this rule that does not hold by itself.

    The jailer clears the environment on its own and closes every open
    descriptor except the three standard ones. Those three are pointed at
    /dev/null only by ``--daemonize``, so leaving that flag off would satisfy
    the rule's wording and defeat half of it.
    """
    assert "--daemonize" in plan["jailer"]["argv"]
    assert "--metadata" not in plan["jailer"]["argv"]


def test_the_breach_rule_names_the_rule_rather_than_the_symptom(images, tmp_path):
    """stop-and-report, one step earlier than a breach.

    A refusal that said "invalid configuration" would leave whoever reads it to
    work out which of eleven rules could not be applied.
    """
    weakened = deepcopy(dict(REQUIRED_MICROVM_POLICY))
    weakened["network"] = "allowlist"

    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, policy=weakened)

    assert refusal.value.rule == "network"
    assert "allowlist" in str(refusal.value)
    assert (
        plan_on_breach := REQUIRED_MICROVM_POLICY["on_breach"]
    ) and plan_on_breach == "stop-and-report"


def test_the_deadline_carries_the_breach_rule_with_it(plan):
    assert plan["host_side"]["on_deadline"] == REQUIRED_MICROVM_POLICY["on_breach"]


# ── A rule that cannot be expressed stops the build ───────────────────────


@pytest.mark.parametrize("rule", sorted(REQUIRED_MICROVM_POLICY))
def test_a_policy_missing_any_rule_is_refused_by_that_rule_name(
    rule, images, tmp_path
):
    """One case per rule, because one rule is what goes missing at a time.

    This is the check the stage's exit condition names: a builder that quietly
    emitted every rule but one would produce exactly the state stage C exists to
    end, and it would produce it silently.
    """
    short = deepcopy(dict(REQUIRED_MICROVM_POLICY))
    del short[rule]

    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, policy=short)

    assert refusal.value.rule == rule


@pytest.mark.parametrize(
    ("rule", "weakened_to"),
    [
        ("required", False),
        ("runtime", "docker"),
        ("network", "allowlist"),
        ("network", "host"),
        ("rootfs", "writable"),
        ("workdir", "persistent"),
        ("workdir_quota_mib", 0),
        ("workdir_quota_mib", "unbounded"),
        ("memory_mib", -1),
        ("memory_mib", None),
        ("wall_clock_seconds", 0),
        ("wall_clock_seconds", True),
        ("user", "root"),
        ("credentials", "inherit-environment"),
        ("credentials", "none"),
        ("on_breach", "continue"),
        ("on_breach", "log-and-continue"),
    ],
)
def test_a_rule_weakened_in_the_policy_is_refused_rather_than_applied(
    rule, weakened_to, images, tmp_path
):
    """The builder stops; it does not adapt.

    This is the difference between a reach and a copy. A copy of the policy
    would be updated to match a weakened rule and go on emitting arguments. A
    statement of what the builder can express turns the same weakening into a
    refusal that names the rule.
    """
    weakened = deepcopy(dict(REQUIRED_MICROVM_POLICY))
    weakened[rule] = weakened_to

    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, policy=weakened)

    assert refusal.value.rule == rule


def test_a_rule_the_builder_has_never_heard_of_is_refused_too(images, tmp_path):
    """The other direction, and the more likely one.

    A rule added to the policy by a later change reaches this builder as a key
    it cannot express. Emitting the other eleven and ignoring the twelfth is how
    the credential rule would have been lost had it arrived after this file.
    """
    extended = deepcopy(dict(REQUIRED_MICROVM_POLICY))
    extended["vcpu_count"] = 2

    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, policy=extended)

    assert refusal.value.rule == "vcpu_count"


# ── The devices and flags no rule names ───────────────────────────────────


def test_none_of_the_three_devices_is_configured(plan):
    """Each of them defeats a rule that is in the policy.

    Absent rather than set to null: Firecracker treats a null device and a
    configured one as different things, and a reader treats them as the same.
    The plan records the pinning separately so the intent is written down.
    """
    config = plan["firecracker"]["config"]

    assert devices_that_would_reopen_a_closed_rule(config) == []
    for device in DEVICES_THAT_MUST_BE_ABSENT:
        assert device not in config
    assert plan["devices_pinned"] == {
        name: None for name in sorted(DEVICES_THAT_MUST_BE_ABSENT)
    }


@pytest.mark.parametrize("device", sorted(DEVICES_THAT_MUST_BE_ABSENT))
def test_a_configuration_that_names_one_of_them_is_reported(device, plan):
    """The check runs over any configuration, not only the one built here.

    Written that way so stage C3 can read a configuration back off the host and
    ask the same question of it, instead of trusting that what was built is what
    is running.
    """
    smuggled = deepcopy(plan["firecracker"]["config"])
    smuggled[device] = {}

    named = devices_that_would_reopen_a_closed_rule(smuggled)

    assert len(named) == 1
    assert named[0].startswith(device)


def test_no_snapshot_route_is_emitted_and_the_api_is_off(plan):
    """Pinning a device is a statement about start-up until the API is closed.

    With the API socket live, every device pinned above can be added back for
    the life of the machine and a snapshot can be loaded whose configuration was
    decided somewhere else entirely. ``--no-api`` is what makes the
    configuration file the whole of what the machine will ever be.
    """
    argv = plan["jailer"]["argv"]

    assert "--no-api" in argv
    assert "--config-file" in argv
    assert _argument_after(argv, "--config-file") == IN_JAIL_CONFIG
    assert not any("snapshot" in item for item in argv)
    assert not any("snapshot" in key for key in plan["firecracker"]["config"])


@pytest.mark.parametrize("flag", sorted(FLAGS_THAT_WOULD_WEAKEN_THE_JAIL))
def test_no_weakening_flag_is_passed(flag, plan):
    assert flag not in plan["jailer"]["argv"]
    assert flags_that_would_weaken_the_jail(plan["jailer"]["argv"]) == []


@pytest.mark.parametrize("spelling", ["--no-seccomp", "--netns=/var/run/netns/x"])
def test_a_weakening_flag_is_reported_in_either_spelling(spelling, plan):
    """``--flag value`` and ``--flag=value`` are the same flag.

    A check that knew only one of the two spellings is a check somebody walks
    around without meaning to.
    """
    named = flags_that_would_weaken_the_jail(plan["jailer"]["argv"] + [spelling])

    assert len(named) == 1
    assert named[0].startswith(spelling.split("=")[0])


def test_the_three_flags_no_policy_key_names_are_all_passed(plan):
    """Each closes a gap the policy describes without naming the mechanism."""
    argv = plan["jailer"]["argv"]

    assert "--new-pid-ns" in argv
    assert "--daemonize" in argv
    assert _argument_after(argv, "--cgroup") is not None


# ── The cgroup hierarchy, which is where a default would be wrong ─────────


def test_the_memory_bound_uses_the_name_its_own_hierarchy_uses():
    """v1 and v2 call it different things, and the jailer does not translate.

    ``--cgroup <file>=<value>`` writes to the file it is given under the
    hierarchy ``--cgroup-version`` selects. Passing v1's name with
    ``--cgroup-version 2`` asks for a file that does not exist there — a memory
    bound that reads as enforced and is not, arriving through a name rather than
    through a deletion.
    """
    assert CGROUP_MEMORY_FILE_BY_VERSION[1] == "memory.limit_in_bytes"
    assert CGROUP_MEMORY_FILE_BY_VERSION[2] == "memory.max"
    assert CGROUP_MEMORY_FILE_BY_VERSION[1] != CGROUP_MEMORY_FILE_BY_VERSION[2]


@pytest.mark.parametrize("version", [1, 2])
def test_the_version_is_passed_explicitly_with_its_own_file_name(
    version, images, tmp_path
):
    """Never inherited. The jailer's default is 1 and the host runs 2.

    A launcher that passed ``--cgroup`` and left the version alone would write
    to a hierarchy that is not the one in use, on a host where nothing would
    announce that it had not.
    """
    argv = _build(images, tmp_path, cgroup_version=version)["jailer"]["argv"]

    assert _argument_after(argv, "--cgroup-version") == str(version)
    assert _argument_after(argv, "--cgroup").startswith(
        CGROUP_MEMORY_FILE_BY_VERSION[version] + "="
    )


def test_an_unsupported_hierarchy_is_refused_rather_than_guessed(images, tmp_path):
    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, cgroup_version=3)

    assert refusal.value.rule == "memory_mib"


# ── Paths, which are jail-relative or they are wrong ──────────────────────


def test_every_in_jail_path_is_a_name_at_the_root_of_the_jail(plan):
    """The shape of the path, not the spelling of the constant.

    Firecracker is chrooted before it reads any of these, so a host path here
    resolves to nothing or — worse — to something else. Asserting only that the
    configuration matches ``IN_JAIL_CONFIG`` would let the constant be changed
    to a host path and take the test with it, which is a check that agrees with
    whatever it is given. A path in the jail is a single name at the root, so
    that is what is asserted.
    """
    for path in (IN_JAIL_KERNEL, IN_JAIL_ROOTFS, IN_JAIL_WORK_DISK, IN_JAIL_CONFIG):
        assert path.startswith("/"), path
        assert path.count("/") == 1, f"{path} is not at the root of the jail"

    assert _argument_after(plan["jailer"]["argv"], "--config-file").count("/") == 1


def test_the_configuration_names_no_path_from_the_host(plan, tmp_path):
    """Firecracker resolves these paths from inside the jail.

    A host path in the configuration would resolve to something else or to
    nothing once Firecracker has been chrooted, and the plan carries the
    host-side placement separately for exactly that reason.
    """
    config = plan["firecracker"]["config"]

    assert config["boot-source"]["kernel_image_path"] == IN_JAIL_KERNEL
    assert {item["path_on_host"] for item in config["drives"]} == {
        IN_JAIL_ROOTFS,
        IN_JAIL_WORK_DISK,
    }
    assert str(tmp_path) not in str(config)


def test_the_jail_is_where_the_jailer_will_build_it(plan):
    """``<chroot-base>/<exec-file-name>/<id>/root``, its own convention."""
    assert plan["host_side"]["chroot_dir"] == "/srv/jailer/firecracker/stage-c1/root"
    assert plan["host_side"]["destroy_after_the_run"] == [
        plan["host_side"]["chroot_dir"]
    ]


def test_the_images_are_carried_by_the_hash_the_readiness_report_took(
    plan, images
):
    """One answer to "which kernel", not two that can disagree.

    core.agentic_v2_microvm already hashes these files to decide whether a boot
    test could be attempted. The builder reuses that reading rather than taking
    its own, which is why it takes the paths and not the digests.
    """
    by_name = {item["in_jail"]: item for item in plan["place_in_jail"]}

    assert by_name[IN_JAIL_KERNEL]["from_host"] == images["kernel_path"].as_posix()
    assert len(by_name[IN_JAIL_KERNEL]["sha256"]) == 64
    assert by_name[IN_JAIL_ROOTFS]["sha256"] != by_name[IN_JAIL_KERNEL]["sha256"]
    assert by_name[IN_JAIL_ROOTFS]["writable_by_the_jailed_user"] is False
    assert by_name[IN_JAIL_WORK_DISK]["writable_by_the_jailed_user"] is True


def test_an_image_that_is_not_there_is_refused_rather_than_named(images, tmp_path):
    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path, kernel_path=tmp_path / "no-such-kernel")

    assert refusal.value.rule == "runtime"
    assert "kernel" in str(refusal.value)


@pytest.mark.parametrize(
    "bad_id", ["../escape", "a" * 65, "", "has space", "-leading", "ünïcode"]
)
def test_an_id_the_jailer_would_reject_never_reaches_a_path(bad_id, images, tmp_path):
    """The id becomes a directory name under the chroot base.

    An id that escaped it would be choosing where the jail is built, which is
    not a thing the caller gets to choose.
    """
    with pytest.raises(LaunchRefused):
        _build(images, tmp_path, vm_id=bad_id)


# ── What the plan is, and what it is not ──────────────────────────────────


def test_the_backstop_fires_when_a_rule_is_dropped_on_the_way_out(
    monkeypatch, images, tmp_path
):
    """The one guard a healthy build never exercises.

    build_launch_plan checks, as its last act, that every rule it accepted also
    appears in the record of where the rules went. In every passing build that
    check is dead code — which is the position a safety net is normally in right
    up until it is needed and turns out not to work.

    So the failure it exists for is staged: the record is made to come back one
    rule short, exactly as it would after somebody deleted a line while editing
    the arguments. The build has to stop and name the rule. The alternative is a
    plan that looks complete, hashes cleanly, and quietly bounds nothing.
    """
    import core.agentic_v2_microvm_launch as launch

    intact = launch._where_each_rule_went

    def one_rule_short(**keywords):
        went = intact(**keywords)
        del went["memory_mib"]
        return went

    monkeypatch.setattr(launch, "_where_each_rule_went", one_rule_short)

    with pytest.raises(LaunchRefused) as refusal:
        _build(images, tmp_path)

    assert refusal.value.rule == "memory_mib"
    assert "silent drop" in str(refusal.value)


def test_the_plan_says_it_started_nothing(plan):
    assert plan["starts_nothing"] is True
    assert plan["host_could_run_this"] in (True, False)


def test_the_plan_has_an_identity_that_covers_everything_in_it(plan):
    from core.agentic_v2_substrate import canonical_sha256

    without = {k: v for k, v in plan.items() if k != "plan_sha256"}

    assert plan["plan_sha256"] == canonical_sha256(without)
    assert plan["policy_sha256"] == canonical_sha256(dict(REQUIRED_MICROVM_POLICY))


def test_two_builds_of_the_same_thing_are_the_same_document(images, tmp_path):
    assert (
        _build(images, tmp_path)["plan_sha256"]
        == _build(images, tmp_path)["plan_sha256"]
    )


def test_a_different_vcpu_count_is_a_different_document(images, tmp_path):
    """The one number the policy does not bound, so it has to be visible.

    Named here rather than fixed here. A containment that bounds memory by rule
    and leaves processor share to whoever calls it has a gap, and closing it
    means adding a rule in a change of its own — the way the credential rule was
    added — not quietly picking a number in the builder.
    """
    assert (
        _build(images, tmp_path, vcpu_count=2)["plan_sha256"]
        != _build(images, tmp_path, vcpu_count=8)["plan_sha256"]
    )


@pytest.mark.parametrize("bad", [0, -1, "two", 1.5, True])
def test_a_processor_count_that_is_not_one_is_refused(bad, images, tmp_path):
    with pytest.raises(LaunchRefused):
        _build(images, tmp_path, vcpu_count=bad)


def test_no_test_in_this_file_starts_anything():
    """The honesty guard on the file itself.

    Every assertion above reads a document. None of them starts a machine, and
    if one ever does, the name of this file stops describing it. The parser is
    used rather than a text search so this test does not trip over its own list
    of names.
    """
    ways_to_run_something = {"subprocess", "os", "pty", "asyncio", "docker", "shutil"}

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not imported & ways_to_run_something
    assert "cannot show that any of those arguments has the effect" in __doc__
