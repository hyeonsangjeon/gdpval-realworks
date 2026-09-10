"""Check one exact image against what the substrate manifest declares.

``sandbox/agentic_v2_capabilities.json`` is a **declaration**. It lists twenty
commands as ``{"name": "Rscript", "capability": "data-science", "probe":
["Rscript", "--version"]}`` — an argv to run, with no version and no hash — and
thirteen Python modules by name alone. It says what an image ought to hold and
how to find out. It is not the finding out.

This script does the finding out, for one image, on one host, and writes down
which host. That last part is not bookkeeping: a probe result belongs to the
place it was taken, and a sweep run on a 3.10 kernel and a sweep run on the
Azure host are two different measurements even when the image is the same
bytes.

**Why this exists separately from** :mod:`sandbox.v2.image_probe`. That module
produces a *capability receipt* — the artifact
:func:`core.agentic_v2_substrate.validate_capability_receipt` accepts — and it
runs from inside the image, reading ``/opt/gdpval/v2/capabilities.json``, which
only the built candidate carries. The candidate that receipt was measured on
(``sandbox/v2/README.md``: image ID ``sha256:e47537b8…``) was never pushed
anywhere. The image this repository can actually fetch is the one
``parent.lock.json`` pins, and that is the *parent* the candidate is built from.
So the receipt exists and does not describe the reachable image, and the
reachable image has never been swept at all.

This produces the narrower thing that is honestly available: a per-command
answer about a reachable image. It is deliberately **not** a capability receipt,
and it does not validate as one. Naming it one would be the same overclaim in a
new place.

**What a result here is not.** Not a signature check, not a provenance
attestation, not a vulnerability scan, and not an isolation measurement. The
digest is the registry's content address for the bytes fetched — an identity for
what was pulled, not a supplier's assertion about what is in it. Signature and
provenance remain ``not_run``.

A command that is absent is recorded as absent. Nothing is skipped, because a
skipped probe and a failed probe read the same in a summary and mean opposite
things.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


BATCH_ROOT = Path(__file__).resolve().parents[2]
if str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))

DEFAULT_MANIFEST = BATCH_ROOT / "sandbox" / "agentic_v2_capabilities.json"
DEFAULT_LOCK = BATCH_ROOT / "sandbox" / "v2" / "parent.lock.json"

#: Marks the driver's records apart from whatever a probe prints.
#:
#: Long and unlikely rather than short and tidy: one of the things being probed
#: is a shell, and a delimiter a probe could plausibly emit would let its own
#: output be read as the driver's framing.
MARK = "###gdpval-probe-8f2a###"

#: Bytes kept from each stream. A probe that prints a manual is still a probe
#: that answered, and the answer is in the first line.
KEEP_BYTES = 2000

PROBE_TIMEOUT_SECONDS = 120

#: Asked of every image regardless of the manifest.
#:
#: ``python`` versus ``python3`` is the specific unknown: the manifest declares
#: ``platform.python == "3.11"`` and never says which name reaches it, and a
#: command built around the wrong one fails in a way that reads as the model
#: writing a broken command. Both are asked, always, and both answers are kept.
ALWAYS_ASKED: tuple[dict[str, Any], ...] = (
    {"name": "python", "capability": "runtime", "probe": ["python", "--version"]},
    {"name": "python3", "capability": "runtime", "probe": ["python3", "--version"]},
    {"name": "sh", "capability": "runtime", "probe": ["sh", "-c", "echo ok"]},
    {"name": "uname", "capability": "runtime", "probe": ["uname", "-srm"]},
)


class SweepRefused(RuntimeError):
    """The sweep cannot be run as asked, so no image was started."""


_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)


def _is_pinned(image: str) -> bool:
    """Whether this reference names one exact set of bytes.

    Two forms count. ``repo@sha256:…`` is a registry content address, which is
    what a pushed image is pinned by. A bare ``sha256:…`` is a local image ID,
    which is what an image that was *built* and never pushed has instead — and
    that is the case that matters here, because the candidate carrying the
    professional-work layer was never pushed anywhere. ``sandbox/v2/README.md``
    identifies it the same way.

    A tag is not pinning. It names whatever is behind it at the moment of the
    run, which makes a result that cannot be checked afterwards.
    """
    return "@sha256:" in image or bool(_IMAGE_ID.fullmatch(image.strip()))


def _shell_driver(probes: Sequence[Mapping[str, Any]]) -> str:
    """One shell script that runs every probe and frames each answer.

    One container rather than one per probe, because twenty container starts
    measure the daemon more than the image. Each probe still gets its own
    ``execve``, its own exit status and its own two streams — the saving is in
    the starts, not in the isolation between answers.

    ``shlex.quote`` on every argument: these come from a file in this repository
    rather than from anywhere untrusted, which is a reason to expect them to be
    ordinary, not a reason to concatenate them unquoted.
    """
    lines = ["exec 2>/dev/null"]
    for probe in probes:
        argv = " ".join(shlex.quote(str(part)) for part in probe["probe"])
        name = probe["name"]
        lines.extend(
            [
                f"printf '%s\\n' {shlex.quote(MARK + 'BEGIN ' + name)}",
                f"{argv} >/tmp/probe.out 2>/tmp/probe.err",
                "status=$?",
                f"printf '%s%s\\n' {shlex.quote(MARK + 'RC ')} \"$status\"",
                f"printf '%s\\n' {shlex.quote(MARK + 'OUT')}",
                f"head -c {KEEP_BYTES} /tmp/probe.out 2>/dev/null || true",
                f"printf '\\n%s\\n' {shlex.quote(MARK + 'ERR')}",
                f"head -c {KEEP_BYTES} /tmp/probe.err 2>/dev/null || true",
                f"printf '\\n%s\\n' {shlex.quote(MARK + 'END')}",
            ]
        )
    return "\n".join(lines) + "\n"


def _module_probes(modules: Iterable[Mapping[str, Any]], interpreter: str) -> list[dict]:
    """Import each declared module and print whatever version it admits to.

    The import is the answer; the version is a courtesy. A module that imports
    and has no ``__version__`` is present, and recording it as unknown-version
    is right where recording it as absent would be wrong.
    """
    built = []
    for module in modules:
        name = str(module["name"])
        built.append(
            {
                "name": f"{interpreter}:{name}",
                "capability": module.get("capability", ""),
                "kind": "python_module",
                "module": name,
                "interpreter": interpreter,
                "probe": [
                    interpreter,
                    "-c",
                    f"import {name} as m; "
                    "print(getattr(m, '__version__', 'no __version__'))",
                ],
            }
        )
    return built


def _font_probes(families: Iterable[str]) -> list[dict]:
    """Ask ``fc-match`` what it would actually use for each declared family.

    ``fc-list | grep`` answers whether a name appears. ``fc-match`` answers what
    a document would be rendered with, and fontconfig substitutes silently — a
    missing ``Noto Sans CJK KR`` resolves to something else and exits 0. So the
    family it names back is kept, and comparing it to what was asked for is left
    to whoever reads the artifact.
    """
    return [
        {
            "name": f"font:{family}",
            "capability": "fonts",
            "kind": "font_family",
            "asked_for": family,
            "probe": ["fc-match", "-f", "%{family}|%{file}", family],
        }
        for family in families
    ]


def _parse(transcript: str, probes: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Read the driver's framed output back into one record per probe.

    A probe with no record in the transcript is reported as having produced no
    answer rather than dropped. That case means the driver died partway — the
    container was killed, the shell was not there — and it is a fact about the
    sweep, not about the command.
    """
    found: dict[str, dict[str, Any]] = {}
    blocks = transcript.split(MARK + "BEGIN ")
    for block in blocks[1:]:
        name, _, body = block.partition("\n")
        name = name.strip()
        record: dict[str, Any] = {"returncode": None, "stdout": "", "stderr": ""}
        if f"{MARK}RC " in body:
            after = body.split(f"{MARK}RC ", 1)[1]
            digits, _, body = after.partition("\n")
            try:
                record["returncode"] = int(digits.strip())
            except ValueError:
                record["returncode"] = None
        if f"{MARK}OUT" in body:
            out, _, rest = body.split(f"{MARK}OUT", 1)[1].partition(f"{MARK}ERR")
            record["stdout"] = out.strip()
            record["stderr"] = rest.split(f"{MARK}END")[0].strip()
        found[name] = record

    records = []
    for probe in probes:
        name = str(probe["name"])
        answer = found.get(name)
        row = {
            "name": name,
            "capability": probe.get("capability", ""),
            "kind": probe.get("kind", "command"),
            "argv": list(probe["probe"]),
        }
        if answer is None:
            row.update(
                {
                    "answered": False,
                    "present": False,
                    "returncode": None,
                    "first_line": "",
                    "stderr": "",
                    "grounds": (
                        "the driver produced no record for this probe, so the "
                        "sweep did not finish — this is not a statement about "
                        "the command"
                    ),
                }
            )
        else:
            status = answer["returncode"]
            first = (answer["stdout"] or answer["stderr"]).splitlines()
            row.update(
                {
                    "answered": True,
                    "present": status == 0,
                    "returncode": status,
                    "first_line": first[0].strip() if first else "",
                    "stderr": answer["stderr"][:400],
                    "grounds": (
                        "the probe exited 0"
                        if status == 0
                        else f"the probe exited {status}"
                    ),
                }
            )
        records.append(row)
    return records


def sweep(
    *,
    image: str,
    manifest_path: Path = DEFAULT_MANIFEST,
    runtime: str = "docker",
    timeout_seconds: int = PROBE_TIMEOUT_SECONDS,
    run: Any = None,
) -> dict[str, Any]:
    """Run every declared probe inside one image and say what came back."""
    if not _is_pinned(image):
        raise SweepRefused(
            f"the image reference {image!r} is not pinned. Give a registry "
            "digest (repo@sha256:…) or a local image ID (sha256:…): a sweep of "
            "a moving tag describes whatever happened to be behind it at the "
            "time and cannot be checked later"
        )
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    probes: list[dict[str, Any]] = [dict(p, kind="command") for p in ALWAYS_ASKED]
    probes += [dict(p, kind="command") for p in manifest["commands"]]
    probes += _module_probes(manifest["python_modules"], "python3")
    probes += _font_probes(manifest["font_families"])

    argv = [
        runtime, "run", "--rm",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp",
        "--entrypoint", "/bin/sh",
        image,
        "-c", _shell_driver(probes),
    ]
    runner = run or _run
    started = time.time()
    completed = runner(argv, timeout_seconds)
    took = time.time() - started

    transcript = getattr(completed, "stdout", "") or ""
    records = _parse(transcript, probes)
    answered = [row for row in records if row["answered"]]
    return {
        "artifact": "agentic-v2-declared-command-sweep",
        "artifact_version": "1.0",
        "is_not": [
            "a capability receipt",
            "a signature or provenance verification",
            "a vulnerability scan",
            "an isolation or containment measurement",
        ],
        "image": image,
        "manifest_sha256": _canonical_sha256(manifest),
        "manifest_path": Path(manifest_path).as_posix(),
        "declared": {
            "commands": len(manifest["commands"]),
            "python_modules": len(manifest["python_modules"]),
            "font_families": len(manifest["font_families"]),
            "platform": manifest["platform"],
        },
        "host": _where_this_was_taken(runtime),
        "runtime_argv": argv[:-1] + ["<driver>"],
        "sweep_seconds": round(took, 2),
        "sweep_returncode": getattr(completed, "returncode", None),
        "sweep_stderr": (getattr(completed, "stderr", "") or "").strip()[:2000],
        "probes_declared": len(probes),
        "probes_answered": len(answered),
        "present": sum(1 for row in answered if row["present"]),
        "absent": sum(1 for row in answered if not row["present"]),
        "records": records,
    }


def _run(argv: Sequence[str], timeout_seconds: int) -> Any:
    return subprocess.run(  # noqa: S603
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout_seconds,
    )


def _where_this_was_taken(runtime: str) -> dict[str, Any]:
    """The host, because a probe result belongs to the place it was taken.

    A sweep on this box's 3.10 kernel and a sweep on the Azure host are two
    measurements, and an artifact that did not say which would let one be read
    as the other.
    """
    version = ""
    try:
        version = subprocess.run(  # noqa: S603
            [runtime, "version", "--format", "{{.Server.Version}}"],
            check=False, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        version = ""
    return {
        "kernel": platform.release(),
        "machine": platform.machine(),
        "system": platform.system(),
        "runtime": runtime,
        "runtime_version": version,
        "cgroup_version": _cgroup_version(),
    }


def _cgroup_version() -> int | None:
    """2 when the unified hierarchy is mounted at ``/sys/fs/cgroup``, else 1.

    Read rather than assumed, and ``None`` when neither is legible. The policy
    stage D runs under requires v2, and a host that cannot say is a host that
    has not answered.
    """
    try:
        with open("/proc/mounts", encoding="utf-8") as mounts:
            for line in mounts:
                parts = line.split()
                if len(parts) > 2 and parts[1] == "/sys/fs/cgroup":
                    return 2 if parts[2] == "cgroup2" else 1
    except OSError:
        return None
    return None


def _canonical_sha256(value: Any) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _pinned_parent(lock_path: Path = DEFAULT_LOCK) -> str:
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    return str(lock["reference"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        default=None,
        help="a digest-pinned reference; defaults to what parent.lock.json pins",
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--timeout", type=int, default=PROBE_TIMEOUT_SECONDS)
    parser.add_argument("--out", default="/var/tmp/gdpval-declared-command-sweep.json")
    args = parser.parse_args(argv)

    image = args.image or _pinned_parent()
    try:
        result = sweep(
            image=image,
            manifest_path=Path(args.manifest),
            runtime=args.runtime,
            timeout_seconds=args.timeout,
        )
    except SweepRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"the sweep did not finish within {args.timeout}s", file=sys.stderr)
        return 3

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print(f"image      {result['image']}")
    print(f"host       {result['host']['kernel']} {result['host']['machine']}")
    print(
        f"answered   {result['probes_answered']}/{result['probes_declared']}"
        f"   present {result['present']}   absent {result['absent']}"
    )
    for row in result["records"]:
        mark = "ok " if row["present"] else ("-- " if row["answered"] else "?? ")
        print(f"  {mark}{row['name']:<28} {row['first_line'][:70]}")
    print(f"written    {out.as_posix()}")
    # A sweep that ran is a success even when things are absent. Absence is the
    # answer it was sent to get, and exiting non-zero for it would make a real
    # finding indistinguishable from a broken run.
    return 0 if result["probes_answered"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
