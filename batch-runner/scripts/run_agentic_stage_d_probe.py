#!/usr/bin/env python3
"""Stage D: ask a real deployment one task's worth of questions over a real guest.

Stage A proved a model reached over a route will choose a tool and then work
from what came back. It proved that against a backend that wrote into a host
directory. Stage D asks the same question with the machine underneath it: every
``exec_run`` is one microVM, booted under the jailer, given a work disk, killed,
and read back off that disk.

**This runs on the execution host and nowhere else.** It refuses on any other
machine, and it refuses by reading rather than guessing: it will not start
unless C2 has already booted a guest here and left the artefact saying so. That
is not ceremony. Stage D is the paid stage, and a model call made on a host that
has never booted a guest would be bought and then thrown away when the first
``exec_run`` failed.

    # on the execution host, after run_agentic_c2_first_boot.py has passed
    cd batch-runner
    python scripts/run_agentic_stage_d_probe.py --dry-run
    python scripts/run_agentic_stage_d_probe.py

**What it takes from C2 rather than building again.** The kernel, the rootfs,
the jail account, the firecracker and jailer binaries, and the cgroup version.
All of them come out of C2's artefact, so stage D runs against the images that
were actually booted and recorded, not against a second build that happens to
have been made the same way. If C2's artefact says the boot failed, this refuses
and names that as the reason.

**What it takes from stage A rather than copying.** The free gate and the
wording check are loaded out of ``run_agentic_stage_a_probe.py`` as that
module's own functions. A copy would be a second place for the prompt hash to
drift, and stage A's runner is a path that has already been through a paid run —
moving code out of it to make this one tidier would perturb something proven to
buy something cosmetic.

**What is written down, and what is not.** One row per model call: turn,
deployment asked for, model that answered, tokens, how much earlier conversation
the call carried, and either a price or an explicit ``price_missing``. One row
per boot: outcome, exit status, teardown. Plus what is *known* about the guest
image — which is currently ``not_run``, because the digest this repository can
fetch is the parent the capability receipt was never measured against. Nothing
of what was said, and not the benchmark wording.

**The exit code answers stage D's question.** Zero means a real model was
reached, a command really ran inside a guest, and a later call went out holding
what that command produced. A model that was reached and chose to do nothing is
a finding, and it is reported as one — but it did not answer the question, so it
exits 1. A boot that failed is not laundered into a model result.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_guest_image import sha256_file  # noqa: E402
from core.agentic_v2_microvm_backend import GuestImage  # noqa: E402
from core.agentic_v2_one_call_machine import OneCallMachine  # noqa: E402
from core.agentic_v2_stage_d_probe import (  # noqa: E402
    PROBE_TOOLS,
    TURNS_STAGE_D_NEEDS,
    ProbeCannotDescribeItself,
    ProbeToolsAreWrong,
    capability_evidence_for,
    run_stage_d_probe,
)
from core.agentic_v2_stage_one_budget import STAGE_ONE_PLAN_PATH  # noqa: E402
from core.agentic_v2_substrate import AgenticV2SubstrateManifest  # noqa: E402
from core.execution_envelope_cost import load_price_table  # noqa: E402
from core.execution_envelope_tasks import DATASET_REVISION  # noqa: E402

#: Where C2 leaves the artefact this refuses to run without.
C2_ARTEFACT = Path("/var/tmp/gdpval-c2/c2-first-boot.json")

SUBSTRATE_MANIFEST = BATCH_RUNNER_ROOT / "sandbox" / "agentic_v2_capabilities.json"

STAGE_A_RUNNER = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_stage_a_probe.py"


class StageDRefused(RuntimeError):
    """Every reason stage D must not spend anything, raised before it does."""


def _stage_a_runner() -> Any:
    """Load stage A's runner as a module, for its gate and its wording check.

    By path because ``scripts`` is not a package, which is also how the tests
    already load these runners. The alternative — lifting both functions into
    ``core`` — would edit a file that a completed paid run was made with, and
    the tidiness is not worth the change.
    """
    spec = importlib.util.spec_from_file_location(
        "run_agentic_stage_a_probe", STAGE_A_RUNNER
    )
    if spec is None or spec.loader is None:  # pragma: no cover - a missing file
        raise StageDRefused(f"stage A's runner is not at {STAGE_A_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_what_c2_left(path: Path) -> dict[str, Any]:
    """C2's artefact, and a refusal if it does not describe a booted guest.

    Four separate refusals rather than one, because they call for four different
    things from whoever reads them: run C2, run C2 *here*, fix the host, or look
    at why the boot failed. A single "stage D cannot run" would hide which.
    """
    if not path.is_file():
        raise StageDRefused(
            f"there is no C2 artefact at {path}. Stage D runs on a host that has "
            "already booted a guest, and this host has not been shown to have "
            "done so. Run scripts/run_agentic_c2_first_boot.py first"
        )
    artefact = json.loads(path.read_text(encoding="utf-8"))

    outcome = str(artefact.get("outcome") or "")
    if outcome != "booted":
        raise StageDRefused(
            f"C2's artefact records {outcome!r}, not a boot"
            + (f" — {artefact['reason']}" if artefact.get("reason") else "")
            + ". A model call made now would be paid for and then have nothing "
            "to run its commands on"
        )

    recorded = str((artefact.get("host") or {}).get("kernel_release") or "")
    running = os.uname().release
    if recorded and recorded != running:
        raise StageDRefused(
            f"C2 booted on kernel {recorded} and this host is running {running}, "
            "so the artefact describes a different machine than the one about "
            "to be paid for"
        )

    for binary in ("firecracker", "jailer"):
        where = (artefact.get("host") or {}).get(binary)
        if not where or not Path(str(where)).exists():
            raise StageDRefused(
                f"C2 recorded {binary} at {where!r} and it is not there now"
            )
    return artefact


def the_images_are_still_the_ones_c2_booted(
    artefact: dict[str, Any], *, sha256: Any = None
) -> dict[str, Any]:
    """Re-hash the kernel and rootfs, and refuse if they are not C2's.

    C3 already declines to attack a machine whose boot nobody recorded — it
    stops with ``different_guest`` rather than produce seven verdicts about the
    wrong thing. Stage D has the same reason and one more: it is the stage that
    pays. A model call bought against a rebuilt rootfs is charged in full and
    discarded at the first command.

    The gap this closes is real rather than theoretical. C2 and C3 ran on a host
    that has since been deallocated, and stage D will run after it is started
    again. These files are on ``/var/tmp``, which is the OS disk and survives
    that — which is why this is expected to pass, and expecting a check to pass
    is not a reason to skip it. A reprovisioned disk, a truncated download and a
    rootfs somebody rebuilt between stages all look like a healthy host until
    the first ``exec_run``, and by then the money is gone.

    **The work disk is deliberately not checked**, and its absence here is a
    decision rather than an omission. Stage C's own record hands stage D the
    ``workdir: ephemeral`` obligation it could not attack — a guest cannot make
    its own disk survive, only the code handing out disks can fail to replace
    one. Every call gets a freshly built work disk, so pinning C2's
    ``work.ext4`` would assert exactly the thing that must not be true.

    Costs one read of about 8.7 GiB, which is seconds against a paid run.
    """
    measure = sha256 or sha256_file
    images = artefact["images"]
    checked: dict[str, Any] = {}
    for which in ("kernel", "rootfs"):
        recorded = images[which]
        where = Path(str(recorded["path"]))
        if not where.is_file():
            raise StageDRefused(
                f"C2 booted {which} at {where} and it is not there now. The "
                "host has been reprovisioned or the file was removed; run "
                "scripts/run_agentic_c2_first_boot.py again before paying for "
                "anything on it"
            )
        found = measure(where)
        if found != str(recorded["sha256"]):
            raise StageDRefused(
                f"the {which} at {where} hashes {found}, and C2 booted "
                f"{recorded['sha256']}. These are different bytes, so C2's "
                "record is not evidence about the machine this run would use"
            )
        checked[which] = {"path": where.as_posix(), "sha256": found}
    checked["matches_the_guest_c2_booted"] = True
    checked["work_disk"] = (
        "not checked, deliberately — every call builds its own, which is the "
        "workdir: ephemeral obligation stage C recorded and left to stage D"
    )
    return checked


def the_guest_c2_booted(artefact: dict[str, Any]) -> GuestImage:
    """The image, named by what C2 measured rather than by what was intended.

    The digest is the *manifest* digest C2 pulled — the amd64 child, where the
    pinned reference was an index — because that is the thing whose bytes became
    the rootfs. The kernel and rootfs hashes are C2's own, over the files this
    run is about to boot.

    Naming is not verifying. What is known about this image is a separate
    question with a separate answer, and
    :func:`core.agentic_v2_stage_d_probe.capability_evidence_for` gives it.
    """
    images = artefact["images"]
    pulled = images["image"]
    return GuestImage(
        reference=str(pulled["repository"]),
        digest=str(pulled.get("pinned_digest") or pulled["manifest_digest"]),
        kernel_sha256=str(images["kernel"]["sha256"]),
        rootfs_sha256=str(images["rootfs"]["sha256"]),
    )


def the_machine_c2_proved(
    artefact: dict[str, Any], *, scratch: Path, session: str, vcpu_count: int
) -> OneCallMachine:
    """One microVM per call, on the binaries and the account C2 used."""
    host = artefact["host"]
    account = artefact["jail_account"]
    images = artefact["images"]
    return OneCallMachine(
        kernel=Path(images["kernel"]["path"]),
        rootfs=Path(images["rootfs"]["path"]),
        firecracker_binary=Path(str(host["firecracker"])),
        jailer_binary=str(host["jailer"]),
        uid=int(account["uid"]),
        gid=int(account["gid"]),
        vcpu_count=vcpu_count,
        cgroup_version=int(host["cgroup_version"]),
        scratch=scratch,
        session=session,
    )


def exit_condition_met(outcome) -> bool:
    """Whether the run answered stage D's question.

    Three things, and the middle one is the whole difference from stage A. A
    model can be reached without ever asking for a command; it can ask for one
    that the backend refuses on the host and never boots for; and it can be
    handed a result and stop. Stage D asked whether a real model works over a
    real machine, so: reached, a command really ran in a guest, and the model
    went on afterwards.

    Not "did it do the task well". A model that ran a command, got a useless
    answer and wrote nonsense meets this. That is a finding about the model, and
    stage D exists to collect findings rather than to require successes.
    """
    return (
        bool(outcome.reached_a_model)
        and bool(outcome.a_command_really_ran)
        and bool(outcome.worked_on_after_running_something)
    )


def build_record(
    *, verdict, said, outcome, fingerprint, workspace, artefact, images=None
) -> dict:
    """What is kept about a paid run, assembled in one place a test can check.

    ``image_evidence`` is in here on purpose and is expected to read
    ``not_run``. A record that named an image and stopped would be read as
    though the evidence followed the name.

    ``images_checked`` is the other half of that: the digest says which bytes,
    and this says they were still those bytes when the run started.
    """
    return {
        "stage": "agentic-v2-stage-d",
        "task_id": verdict.task_id,
        "dataset_revision": DATASET_REVISION,
        "prompt_sha256": said["prompt_sha256"],
        "route_fingerprint": fingerprint,
        "workspace": str(workspace),
        "c2_artefact": str(artefact),
        "images_checked": images,
        "approved_maximum_usd": said["approved_maximum_usd"],
        "most_it_could_cost_usd": said["most_it_could_cost_usd"],
        "exit_condition_met": exit_condition_met(outcome),
        "probe": outcome.as_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage D: one paid task over one real guest per call."
    )
    parser.add_argument("--plan", type=Path, default=STAGE_ONE_PLAN_PATH)
    parser.add_argument("--c2-artefact", type=Path, default=C2_ARTEFACT)
    parser.add_argument("--parquet", type=Path, default=None)
    parser.add_argument("--vcpu-count", type=int, default=2)
    parser.add_argument(
        "--max-tool-calls",
        type=int,
        default=TURNS_STAGE_D_NEEDS,
        help="One boot apiece. Every one of them is a microVM and a teardown.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help=(
            "Where the session's work directory and the collected outputs go. A "
            "fresh temporary one is made if this is left out; an existing one is "
            "never emptied."
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Everything except the network and the boots: the gate, C2's "
            "artefact, the host, the wording, the machine. Exits 0 when the "
            "paid run would be allowed to go ahead."
        ),
    )
    args = parser.parse_args(argv)

    stage_a = _stage_a_runner()
    try:
        artefact = read_what_c2_left(args.c2_artefact)
        images_checked = the_images_are_still_the_ones_c2_booted(artefact)
        plan, verdict, catalog = stage_a._verdict(args.plan)
        task = catalog.by_task_id()[verdict.task_id]
        prompt = stage_a.read_task_prompt(
            verdict.task_id,
            parquet=args.parquet or stage_a.PINNED_DATASET_PARQUET,
            expected_sha256=task.prompt_sha256,
        )
    except (StageDRefused, stage_a.ProbeRefused) as refusal:
        print(f"Refused before spending anything.\n\n{refusal}")
        return 1

    image = the_guest_c2_booted(artefact)
    known = capability_evidence_for(image)
    deployment = str((plan.get("model") or {}).get("deployment") or "")
    connection = plan.get("azure_connection") or {}
    resource = str(connection.get("account") or "")
    said = dict(verdict.as_dict())
    said["prompt_sha256"] = task.prompt_sha256

    print("Agentic Sandbox V2, stage D — one paid task over one guest per call")
    print("=" * 74)
    print(f"  task           {verdict.task_id}")
    print(f"  prompt         {len(prompt)} characters, wording checked against")
    print(f"                 the catalogue's hash for revision "
          f"{DATASET_REVISION[:12]}")
    print(f"  tools offered  {', '.join(PROBE_TOOLS)}")
    print(f"  boots at most  {args.max_tool_calls}, one microVM each")
    print(
        f"  at most        ${said['most_it_could_cost_usd']} against the "
        f"${said['approved_maximum_usd']} approved"
    )
    print(f"  deployment     {deployment} at {resource}")
    print(f"  guest image    {image.digest}")
    print(f"  known about it {known['status']} — {known['grounds']}")
    print(
        f"  host           {artefact['host']['kernel_release']}, cgroup v"
        f"{artefact['host']['cgroup_version']}, firecracker "
        f"{artefact['host'].get('firecracker_version')}"
    )
    print(f"  jailed to      {artefact['jail_account']['name']}")
    print(
        f"  images         still the ones C2 booted — kernel "
        f"{images_checked['kernel']['sha256'][:12]}, rootfs "
        f"{images_checked['rootfs']['sha256'][:12]}"
    )
    print()

    if args.dry_run:
        print(
            "Dry run. Nothing was asked, nothing was booted and nothing was "
            "spent. Every condition for the paid run is met."
        )
        return 0

    workspace = (
        args.workspace
        if args.workspace is not None
        else Path(tempfile.mkdtemp(prefix="agentic-v2-stage-d-"))
    )
    scratch = workspace / "machines"
    print(f"  workspace      {workspace}")

    from core.azure_ai_clients import AzureAIRouteSettings, AzureAIWorkload
    from core.llm_client import create_typed_azure_client

    settings = AzureAIRouteSettings.from_env()
    seconds = float(plan["fixed_settings"]["per_task_timeout_seconds"])
    managed = create_typed_azure_client(
        AzureAIWorkload.INFERENCE, deployment, settings=settings, timeout=seconds
    )
    try:
        wrong_route = stage_a.check_route_is_the_one_the_plan_fixed(
            managed.route, connection, settings=settings
        )
        if wrong_route:
            print(
                "Refused after building a client and before asking it "
                "anything.\n\n  - " + "\n  - ".join(wrong_route)
            )
            return 1

        outcome = run_stage_d_probe(
            client=managed.client,
            deployment=deployment,
            resource=resource,
            budget=verdict.budget,
            task_prompt=prompt,
            workspace_root=workspace / "session",
            image=image,
            boot_one_command=the_machine_c2_proved(
                artefact,
                scratch=scratch,
                session=f"stage-d-{verdict.task_id}",
                vcpu_count=args.vcpu_count,
            ),
            substrate_manifest=AgenticV2SubstrateManifest.load(SUBSTRATE_MANIFEST),
            max_output_tokens_per_turn=verdict.max_output_tokens_per_turn,
            max_seconds=seconds,
            max_tool_calls=args.max_tool_calls,
            collect_outputs_into=workspace / "collected",
            prices=load_price_table(),
            tools=PROBE_TOOLS,
        )
        fingerprint = managed.runtime_fingerprint
    except (ProbeToolsAreWrong, ProbeCannotDescribeItself) as refusal:
        print(f"Refused before the first model call.\n\n{refusal}")
        return 1
    finally:
        managed.close()
        shutil.rmtree(scratch, ignore_errors=True)

    record = build_record(
        verdict=verdict,
        said=said,
        outcome=outcome,
        fingerprint=fingerprint,
        workspace=workspace,
        artefact=args.c2_artefact,
        images=images_checked,
    )
    written = json.dumps(record, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(written + "\n", encoding="utf-8")
        print(f"  record         {args.output}")
    print()
    print(written)
    print()

    booted = sum(1 for row in outcome.boots if row.get("boot_outcome") == "booted")
    print(f"  boots          {booted} of {len(outcome.boots)} came back")
    print(f"  carriage       {outcome.carriage_failures} infrastructure failures")
    print(f"  collected      {outcome.collected.get('files', 0)} files")
    if outcome.price_missing:
        # An unpriced call is partial, and writing zero for it would be a
        # smaller number than the truth rather than an unknown one.
        print("  spent          partial — at least one call had no price")
    else:
        print(f"  spent          ${outcome.spent_usd}")
    print()
    print(
        "  image evidence "
        f"{known['status']} — this run booted an image nothing here holds a "
        "capability receipt, a signature or a provenance attestation for"
    )

    if exit_condition_met(outcome):
        print("\nStage D's question is answered: reached, ran, and worked on.")
        return 0
    print(
        f"\nStage D's question is not answered — {outcome.stop_reason}: "
        f"{outcome.detail}. The record above is the finding."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
