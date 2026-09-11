"""Why the guest was missing six commands: it was the parent image, not the candidate.

D3 swept forty declared commands inside a booted guest and found thirty-four
present and six absent. Read without this, six absences look like gaps in the
sandbox -- tasks that need R, a browser, a C toolchain, Node or DXF would be
recorded as failing on a deficient environment, and somebody would go and add
packages that are already specified.

They are not gaps in the design. The V2 professional-work candidate is the parent
image plus eight locked packages, and six of those eight provide a command. The
six absent commands are those six, exactly, with nothing left over on either
side. What the sweep measured was the parent.

There is a stronger form of that claim already in the repository, and this script
checks it rather than restating it. `sandbox/v2/declared-command-sweep.json` ran
the same forty probes against *both* images on the same host: the candidate
answered forty of forty, the parent thirty-four of forty, and the six it missed
are the six the guest missed. Two runtimes on two kernels -- docker on 3.10,
Firecracker on 6.1 -- disagreeing about nothing.

That distinction matters for the 220-task run, because the run has to separate a
model failing a task from an environment that could not support it. Here the
layer that supplies the six has been measured to supply them; what is missing is
a reachable copy of the image carrying it.

This script derives the correspondence rather than asserting it, so that editing
a lock file without rebuilding the guest cannot leave the claim quietly stale.
It reads only committed files, contacts nothing, and spends nothing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SANDBOX = REPOSITORY_ROOT / "batch-runner" / "sandbox" / "v2"
ARTEFACTS = REPOSITORY_ROOT / "tasks" / "0822_saturday"

DEBIAN_LOCK = SANDBOX / "debian-extra.lock"
PYTHON_LOCK = SANDBOX / "python-extra.lock"
PARENT_LOCK = SANDBOX / "parent.lock.json"
CONTAINER_SWEEP = SANDBOX / "declared-command-sweep.json"
SANDBOX_README = SANDBOX / "README.md"
SWEEP = ARTEFACTS / "guest_declared_command_sweep.json"
BOOT = ARTEFACTS / "c2_first_boot.json"

# Which command a locked package puts on PATH. Only packages that provide one
# appear here; a package that provides none cannot explain a command's absence
# and must not be quietly counted as if it could.
COMMAND_PROVIDED_BY = {
    "r-base-core": "Rscript",
    "chromium": "chromium",
    "cmake": "cmake",
    "nodejs": "node",
    "npm": "npm",
    "ezdxf": "python3:ezdxf",
}

# Stated rather than derived, because "provides no command" is a fact about the
# package, not about this repository, and leaving it implicit would make the
# arithmetic below look like it had dropped two rows.
PROVIDES_NO_COMMAND = {
    "fonts-noto-color-emoji": "a font, not an executable",
    "fonts-noto-core": "a font, not an executable",
}


def _debian_packages(text: str) -> list[str]:
    names = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line.split("=", 1)[0].strip())
    return names


def _python_packages(text: str) -> list[str]:
    names = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("--hash"):
            continue
        match = re.match(r"([A-Za-z0-9._-]+)", line)
        if match:
            names.append(match.group(1))
    return names


def _absent_command_key(record: dict) -> str:
    """Name an absent probe the way COMMAND_PROVIDED_BY names it."""
    argv = record.get("argv") or []
    if not argv:
        return ""
    if argv[0] == "python3" and len(argv) >= 3:
        match = re.search(r"import\s+([A-Za-z0-9_]+)", argv[2])
        if match:
            return f"python3:{match.group(1)}"
    return str(argv[0])


def _absent_keys(records: list) -> list[str]:
    return sorted(
        _absent_command_key(record)
        for record in records
        if record.get("present") is not True
    )


def _recorded_candidate_digests() -> dict:
    """What this repository does and does not hold for the candidate image.

    Read from the README rather than pasted here, so that a rebuild recorded in
    one place cannot leave a second place asserting the old identity.
    """
    text = SANDBOX_README.read_text(encoding="utf-8")

    def _find(label: str) -> str | None:
        match = re.search(label + r":[\s`]*?(sha256:[0-9a-f]{64})", text)
        return match.group(1) if match else None

    return {"image_id": _find("image ID"), "oci_manifest": _find("OCI manifest")}


def explain() -> dict:
    debian = _debian_packages(DEBIAN_LOCK.read_text(encoding="utf-8"))
    python = _python_packages(PYTHON_LOCK.read_text(encoding="utf-8"))
    added = list(debian) + list(python)

    sweep = json.loads(SWEEP.read_text(encoding="utf-8"))
    boot = json.loads(BOOT.read_text(encoding="utf-8"))
    parent = json.loads(PARENT_LOCK.read_text(encoding="utf-8"))
    container = json.loads(CONTAINER_SWEEP.read_text(encoding="utf-8"))

    absent = _absent_keys(sweep["records"])

    unclassified = [
        name for name in added
        if name not in COMMAND_PROVIDED_BY and name not in PROVIDES_NO_COMMAND
    ]
    expected = sorted(
        COMMAND_PROVIDED_BY[name] for name in added if name in COMMAND_PROVIDED_BY
    )
    explained = sorted(set(absent) & set(expected))
    unexplained = sorted(set(absent) - set(expected))
    # A package that adds a command the sweep found *present* would break the
    # story just as badly as an unexplained absence: it would mean the guest was
    # not purely the parent.
    absent_but_expected_present = sorted(set(expected) - set(absent))

    swept_layers = [layer["digest"] for layer in sweep["image"]["layers"]]
    boot_layers = [layer["digest"] for layer in boot["images"]["image"]["layers"]]

    # The same forty probes were run against both images under docker before any
    # of this booted. That is a measurement of the layer's contribution rather
    # than an inference from the lock files, and it is the stronger evidence.
    container_parent_absent = _absent_keys(container["parent"]["records"])
    container_candidate_absent = _absent_keys(container["candidate"]["records"])
    same_image_as_the_guest = (
        container["parent"]["image"].split("@")[-1]
        == boot["images"]["image"]["pinned_digest"]
    )
    runtimes_agree = container_parent_absent == absent

    accounts_for_every_absence = (
        not unexplained and not unclassified and not absent_but_expected_present
    )

    return {
        "what_this_is": (
            "the reason D3's six absent commands are not a gap in the sandbox. "
            "Derived from the committed lock files, the container A/B sweep and "
            "the two guest artefacts, so that editing a lock without rebuilding "
            "the guest cannot leave this claim stale."
        ),
        "the_image_that_was_measured": {
            "repository": sweep["image"].get("repository")
            or boot["images"]["image"]["repository"],
            "pinned_digest": boot["images"]["image"]["pinned_digest"],
            "is_the_parent": (
                boot["images"]["image"]["pinned_digest"] == parent["manifest_digest"]
            ),
            "is_the_professional_work_candidate": False,
            "the_sweep_and_the_boot_are_the_same_image": swept_layers == boot_layers,
            "how_that_is_known": (
                "the pinned digest equals parent.lock.json's manifest_digest, and "
                "the sweep's layer digests equal the boot's layer by layer"
            ),
        },
        "what_the_candidate_adds_on_top": {
            "packages": sorted(added),
            "provide_a_command": {
                name: COMMAND_PROVIDED_BY[name]
                for name in sorted(added)
                if name in COMMAND_PROVIDED_BY
            },
            "provide_no_command": {
                name: PROVIDES_NO_COMMAND[name]
                for name in sorted(added)
                if name in PROVIDES_NO_COMMAND
            },
            "unclassified": sorted(unclassified),
        },
        "the_layer_was_measured_not_inferred": {
            "source": "batch-runner/sandbox/v2/declared-command-sweep.json",
            "taken_on": container.get("taken_on"),
            "runtime": container["parent"]["host"].get("runtime"),
            "candidate_present": container["candidate"]["present"],
            "candidate_absent": container["candidate"]["absent"],
            "candidate_absent_commands": container_candidate_absent,
            "parent_present": container["parent"]["present"],
            "parent_absent": container["parent"]["absent"],
            "parent_absent_commands": container_parent_absent,
            "the_container_parent_is_the_booted_image": same_image_as_the_guest,
            "two_runtimes_name_the_same_six": runtimes_agree,
            "what_that_settles": (
                "the six are supplied by the professional-work layer, observed "
                "rather than deduced: the candidate answered every probe and the "
                "parent missed exactly these six, under docker on kernel "
                f"{container['parent']['host'].get('kernel')} and again under "
                f"Firecracker on kernel {sweep.get('guest', {}).get('kernel')}"
            ),
        },
        "the_correspondence": {
            "absent_in_the_guest": absent,
            "expected_absent_if_the_guest_is_the_parent": expected,
            "explained_by_the_missing_layer": explained,
            "absent_and_not_explained": unexplained,
            "expected_absent_but_found_present": absent_but_expected_present,
            "accounts_for_every_absence": accounts_for_every_absence,
        },
        "where_the_candidate_actually_is": {
            "recorded_digests": _recorded_candidate_digests(),
            "the_digest_the_container_sweep_ran": container["candidate"]["image"],
            "is_pullable_from_here": False,
            "why_not": (
                "it was built locally and never pushed, so what is recorded is a "
                "local image ID and an OCI manifest digest for bytes that exist "
                "on no registry this repository can reach. An image ID is not a "
                "pullable reference."
            ),
        },
        "therefore": (
            "the six absences are the signature of booting the parent rather "
            "than the candidate, and the layer that supplies them has been "
            "measured to supply them. They are not a limit of the sandbox "
            "design and not a model failure: they are an unpublished image. A "
            "220-task run must not count a task that needed R, a browser, "
            "cmake, Node or ezdxf against the environment's capability on this "
            "evidence -- though on this evidence those tasks will still fail, "
            "for a reason that is recorded and correctable."
        )
        if accounts_for_every_absence
        else (
            "the correspondence is NOT exact, so the parent-instead-of-candidate "
            "explanation does not by itself account for what the sweep found. "
            "See absent_and_not_explained and expected_absent_but_found_present."
        ),
        "what_this_is_not": [
            "not a claim that the candidate is reachable -- it was built locally "
            "and never pushed, and nothing here can fetch it",
            "not a claim that the candidate would boot as a microVM guest, or "
            "that its added packages work under this isolation policy; the A/B "
            "above was taken under docker, and neither has been measured",
            "not a re-run of C2 or D3, and nothing here booted anything",
            "not a statement about the other 34 commands, which were present "
            "in the parent and are not in question",
        ],
    }


def main(argv: list[str]) -> int:
    report = explain()
    if "--json" in argv:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    correspondence = report["the_correspondence"]
    image = report["the_image_that_was_measured"]
    measured = report["the_layer_was_measured_not_inferred"]
    print("Why the guest was missing six commands")
    print("=" * 38)
    print(f"  measured   {image['repository']}")
    print(f"             {image['pinned_digest']}")
    print(f"  which is   {'the parent' if image['is_the_parent'] else 'NOT the parent'}"
          f", not the professional-work candidate")
    print()
    print(f"  absent in the guest   {', '.join(correspondence['absent_in_the_guest'])}")
    print("  the candidate adds    "
          f"{', '.join(report['what_the_candidate_adds_on_top']['provide_a_command'].values())}")
    print()
    print(f"  container A/B         candidate {measured['candidate_present']}/40 present"
          f", parent {measured['parent_present']}/40")
    print(f"  two runtimes agree    {measured['two_runtimes_name_the_same_six']}")
    print()
    ok = (
        correspondence["accounts_for_every_absence"]
        and measured["two_runtimes_name_the_same_six"]
        and measured["the_container_parent_is_the_booted_image"]
    )
    if ok:
        print("  every absence is accounted for, with nothing left over either way")
    else:
        print("  NOT exact:")
        print(f"    unexplained absences   {correspondence['absent_and_not_explained']}")
        print(f"    expected but present   "
              f"{correspondence['expected_absent_but_found_present']}")
        print(f"    runtimes agree         "
              f"{measured['two_runtimes_name_the_same_six']}")
        print(f"    A/B parent is the one booted  "
              f"{measured['the_container_parent_is_the_booted_image']}")
    print()
    print(report["therefore"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
