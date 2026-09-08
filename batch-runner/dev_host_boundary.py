"""Refuse to run the benchmark on the machine that exists to develop it.

The Xenology card allows an Azure VM for development and test, and then draws a
line under it:

    이 VM은 개발·테스트 가속용이다. 사전등록된 GDPVal 벤치마크의 Host
    subprocess, Docker, Azure Code Interpreter 등 실행 환경을 이 VM으로 몰래
    대체하지 않는다. 벤치마크를 Azure VM에서 실행하려면 별도 Arm으로 등록하고
    커널, 이미지, VM 크기, 지역, 컨테이너 지문과 task manifest 를 함께
    고정한다.

The card asks for "a test or a documented contract" that this does not happen.
A document is what gets read once; this is the contract as a refusal, so that
the quiet substitution has to be argued with rather than merely not thought
about.

Why it matters, concretely. The benchmark's claim about an execution arm is that
between two runs *only the run place changed*. A development host has a
different kernel, a different image, a different machine size and a different
region from whatever the arm was registered with, and it is also the machine
somebody is actively installing things on. A run started here would produce
numbers that look like the arm's and are not, and nothing downstream would be
able to tell.

The escape is not a flag that means "ignore this". It is the card's own
condition: register the machine as its own arm, with the five things pinned. If
those pins are present in the marker and the kernel still matches the one that
was pinned, this is a registered arm and the run proceeds. If they are partly
present, that is not a registration, and it refuses and names what is missing.

Where this lives, and why not in ``core/``
------------------------------------------

``step8_grade.compute_grader_source_hash`` hashes every ``core/**/*.py``. A
module placed there would move the grader's source fingerprint, which invalidates
the smoke run that a paid grading run is gated on -- for a file that grading
never calls. It sits at the batch-runner root instead, next to
``step2_run_inference.py``, which is the one thing that uses it.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

#: Written by ``infra/dev-host/bootstrap.sh`` in its first section, before
#: anything else is installed. Overridable so the tests can point at a file they
#: made rather than needing a development host to run on.
MARKER_ENV = "GDPVAL_DEV_HOST_MARKER"
DEFAULT_MARKER_PATH = "/etc/gdpval-dev-host"

#: The card's list, as keys. Registering an arm means fixing all five; four out
#: of five is not a registration, and the difference is the whole point.
REQUIRED_ARM_PINS: tuple[str, ...] = (
    "benchmark_arm",
    "benchmark_arm_kernel",
    "benchmark_arm_image",
    "benchmark_arm_vm_size",
    "benchmark_arm_region",
    "benchmark_arm_task_manifest_sha256",
)

ALLOWED = "yes"
REFUSED = "no"
BENCHMARK_KEY = "benchmark_execution_environment"


class DevHostBoundaryError(RuntimeError):
    """A benchmark run was started on a host that is not registered to carry it."""


@dataclass(frozen=True)
class HostMarker:
    """What ``/etc/gdpval-dev-host`` says about the machine reading it."""

    path: Path
    values: Mapping[str, str]

    @property
    def role(self) -> str:
        return self.values.get("role", "unstated")

    @property
    def claims_benchmark_registration(self) -> bool:
        return self.values.get(BENCHMARK_KEY, REFUSED).strip().lower() == ALLOWED

    @property
    def missing_pins(self) -> tuple[str, ...]:
        return tuple(
            key for key in REQUIRED_ARM_PINS if not self.values.get(key, "").strip()
        )


def read_marker(
    marker_path: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> HostMarker | None:
    """The marker file as key/value pairs, or None when there is no marker.

    No marker means an ordinary machine, and this module has nothing to say
    about it. Only a machine that has declared itself a development host is
    subject to the boundary -- the file is the declaration, not an inference
    from what the hardware looks like.

    An unreadable marker is *not* treated as absent. A file that exists and
    cannot be read is a machine whose role is unknown, and the boundary answers
    unknown the same way it answers "development": by refusing.
    """
    values = os.environ if environ is None else environ
    path = Path(marker_path or values.get(MARKER_ENV) or DEFAULT_MARKER_PATH)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DevHostBoundaryError(
            f"{path} exists and could not be read ({exc}). A machine whose role "
            f"cannot be determined is not a machine to start a benchmark run on."
        ) from exc

    parsed: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        parsed[key.strip()] = value.strip()
    return HostMarker(path=path, values=parsed)


def _registration_instructions(marker: HostMarker) -> str:
    lines = [
        "To run the benchmark on an Azure VM the card requires it to be "
        "registered as its own arm, with all of these fixed in "
        f"{marker.path}:",
        "",
    ]
    for key in REQUIRED_ARM_PINS:
        present = marker.values.get(key, "").strip()
        state = f"= {present}" if present else "MISSING"
        lines.append(f"    {key:<40} {state}")
    lines += [
        "",
        f"    {BENCHMARK_KEY:<40} "
        f"= {marker.values.get(BENCHMARK_KEY, REFUSED)}  (must be {ALLOWED!r})",
        "",
        "That registration is a decision with a paper trail, which is what "
        "makes the arm's numbers comparable to the other arms'. Deleting the "
        "marker file is not it.",
    ]
    return "\n".join(lines)


def check_benchmark_allowed(
    *,
    marker_path: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    kernel: str | None = None,
    what: str = "benchmark inference run",
) -> HostMarker | None:
    """Raise unless this machine may carry a benchmark run.

    Returns the marker when the host is a registered arm, so the caller can
    record which arm it ran as; returns None when there is no marker at all,
    which is every machine that never went through the development-host
    bootstrap.
    """
    marker = read_marker(marker_path=marker_path, environ=environ)
    if marker is None:
        return None

    running_kernel = platform.release() if kernel is None else kernel

    if not marker.claims_benchmark_registration:
        raise DevHostBoundaryError(
            f"refusing to start a {what} here.\n\n"
            f"{marker.path} says this machine is a "
            f"{marker.role} host, not a registered benchmark execution "
            f"environment. Its kernel, image, machine size and region are not "
            f"the ones any arm was registered with, so a run started here would "
            f"produce numbers that look like an arm's and are not.\n\n"
            f"{_registration_instructions(marker)}"
        )

    missing = marker.missing_pins
    if missing:
        raise DevHostBoundaryError(
            f"refusing to start a {what} here.\n\n"
            f"{marker.path} claims this machine is a registered benchmark "
            f"execution environment, but the registration is incomplete: "
            f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not "
            f"set. A partial registration is not a registration -- the pins are "
            f"what make one arm's numbers comparable to another's.\n\n"
            f"{_registration_instructions(marker)}"
        )

    pinned_kernel = marker.values["benchmark_arm_kernel"].strip()
    if pinned_kernel != running_kernel:
        raise DevHostBoundaryError(
            f"refusing to start a {what} here.\n\n"
            f"{marker.path} registers arm "
            f"{marker.values['benchmark_arm']!r} on kernel {pinned_kernel!r}, "
            f"and this machine is running {running_kernel!r}. The arm was "
            f"pinned to a kernel; this is a different one. Re-register the arm "
            f"against the kernel it will actually run on, or run it on the "
            f"kernel it was pinned to."
        )
    return marker


def describe(marker: HostMarker | None) -> str:
    """One line for a log, saying which machine a run believes it is on."""
    if marker is None:
        return "host: no development-host marker; not a declared development host"
    if marker.claims_benchmark_registration and not marker.missing_pins:
        return (
            f"host: registered benchmark arm "
            f"{marker.values['benchmark_arm']!r} "
            f"(kernel {marker.values['benchmark_arm_kernel']}, "
            f"{marker.values['benchmark_arm_vm_size']} in "
            f"{marker.values['benchmark_arm_region']})"
        )
    return f"host: {marker.role}; not a registered benchmark execution environment"


def marker_summary(marker: HostMarker | None) -> dict[str, object]:
    """The marker as run-record fields, for the manifest a run writes."""
    if marker is None:
        return {"dev_host_marker": None, "benchmark_arm": None}
    return {
        "dev_host_marker": str(marker.path),
        "dev_host_role": marker.role,
        "benchmark_arm": marker.values.get("benchmark_arm") or None,
        "benchmark_arm_pins": {
            key: marker.values.get(key) or None for key in REQUIRED_ARM_PINS
        },
    }


__all__: Sequence[str] = (
    "ALLOWED",
    "BENCHMARK_KEY",
    "DEFAULT_MARKER_PATH",
    "DevHostBoundaryError",
    "HostMarker",
    "MARKER_ENV",
    "REFUSED",
    "REQUIRED_ARM_PINS",
    "check_benchmark_allowed",
    "describe",
    "marker_summary",
    "read_marker",
)
