"""Prepare one local, reviewed detached checkout; never execute or clean it up.

An explicit reviewed commit is a caller assertion, not approval issued by this
tool. Individual files are published without replacement and ready is last.
The reservation survives success or failure; a failed attempt must be disposed
of manually, never adopted by a later invocation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from core.inference_manifest import _assert_no_symlink_ancestors
from gpt54_comparison_preflight import (
    ROOT as TRUSTED_ROOT,
    ComparisonGradingPlan,
    ComparisonRunSpec,
    _canonical_json,
    compile_grading_plan,
)
from gpt54_prepared_input_attestation import _identity, _same, _source_snapshot
from gpt54_run_config_bundle import (
    MANIFEST_PATH,
    READY_PATH as CONFIG_READY_PATH,
    _files,
    _held_parents,
    _path,
    _root,
    _sources,
    materialize_run_config_bundle,
    verify_run_config_bundle,
)
from gpt54_run_input_bundle import (
    DATASET_ROOT,
    READY_PATH as INPUT_READY_PATH,
    RESERVATION_PATH as INPUT_RESERVATION_PATH,
    materialize_run_input_bundle,
    verify_run_input_bundle,
)
from gpt54_v2_grading_input import _read_bytes

READY_PATH = "comparison-checkout-ready.json"


class DisposableCheckoutRefused(ValueError):
    """Preparation refused; any reserved/partial checkout must not be reused."""


def _git(repository: Path, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[bytes]:
    """Use only local Git, with no caller environment, hooks or lazy transport.

    These command-local protections do not change repository configuration or
    disable hooks on the user's normal development commits.
    """
    environment = {
        "PATH": "/usr/bin:/bin", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1",
        "GIT_ALLOW_PROTOCOL": "", "GIT_ATTR_NOSYSTEM": "1",
    }
    command = ["/usr/bin/git", "--no-replace-objects"]
    for setting in (
        "core.hooksPath=/dev/null", "core.fsmonitor=false",
        "core.attributesFile=/dev/null", "core.autocrlf=false", "core.eol=lf",
        "core.sparseCheckout=false", "core.sparseCheckoutCone=false",
        "submodule.recurse=false", "fetch.recurseSubmodules=false",
        "maintenance.auto=false", "gc.auto=0",
    ):
        command.extend(("-c", setting))
    command.extend(("-C", str(repository), *args))
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=environment, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DisposableCheckoutRefused("bounded local Git command failed") from error
    if result.returncode not in ok:
        # Do not echo arbitrary config values, hook output or credential-bearing
        # stderr, even on an unexpected Git failure.
        raise DisposableCheckoutRefused(f"local Git {args[0]} refused ({result.returncode})")
    return result


def _repository(repository: Path) -> tuple[Path, Path]:
    root = _root(repository)
    git_entry = root / ".git"
    _assert_no_symlink_ancestors(git_entry)
    if git_entry.is_file():
        _read_bytes(git_entry)  # linked-worktree gitfiles must also be single-link
    top = _git(root, "rev-parse", "--show-toplevel").stdout.rstrip(b"\n")
    if top != os.fsencode(root):
        raise DisposableCheckoutRefused("an explicit repository top-level path is required")
    common = _root(Path(os.fsdecode(_git(
        root, "rev-parse", "--path-format=absolute", "--git-common-dir",
    ).stdout.rstrip(b"\n"))))
    return root, common


def _safe_checkout_configuration(repository: Path) -> None:
    # Names only: no token, remote URL or credential value is read into Python.
    # Includes, filters and promisor settings can introduce execution/network or
    # change checked-out bytes. Refuse them, rather than guessing a safe bridge.
    result = _git(
        repository, "config", "--name-only", "--get-regexp",
        r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)",
        ok=(0, 1),
    )
    if result.stdout:
        raise DisposableCheckoutRefused("checkout filters, includes or partial-clone configuration are unsupported")


def _common(repository: Path) -> tuple[Path, Path]:
    root, common = _repository(repository)
    _, trusted_common = _repository(TRUSTED_ROOT)
    if common != trusted_common or not os.path.samefile(common, trusted_common):
        raise DisposableCheckoutRefused("repository does not share the compiler's Git common directory")
    _safe_checkout_configuration(root)
    return root, common


def _compiled(
    run: ComparisonRunSpec, manifest: dict[str, Any], combined_plan: dict[str, Any],
) -> tuple[ComparisonGradingPlan, int]:
    if type(run) is not ComparisonRunSpec:
        raise DisposableCheckoutRefused("an exact typed dispatch recipe is required")
    plan = compile_grading_plan(manifest)
    _same("combined dispatch/grading plan", combined_plan, plan.as_dict())
    index = next(index for index, row in enumerate(plan.dispatch.runs) if row.run_id == run.run_id)
    _same("dispatch recipe", run.as_dict(), plan.dispatch.runs[index].as_dict())
    return plan, index


def _reviewed_commit(
    repository: Path, sha: str, manifest: dict[str, Any], plan: ComparisonGradingPlan,
) -> dict[str, Any]:
    if type(sha) is not str or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise DisposableCheckoutRefused("a caller-reviewed full lowercase 40-hex commit SHA is required")
    if sha == plan.dispatch.source_base_sha:
        raise DisposableCheckoutRefused("historical manifest source_base is not the caller-reviewed source SHA")
    if _git(repository, "cat-file", "-t", sha).stdout != b"commit\n":
        raise DisposableCheckoutRefused("reviewed source must name a commit object, not a tag/tree/blob")
    if _git(repository, "rev-parse", "--verify", "--end-of-options", sha).stdout != sha.encode("ascii") + b"\n":
        raise DisposableCheckoutRefused("reviewed commit resolved to a different object")

    reserved = set(_files(plan, plan.dispatch.runs[0].run_id)) | {
        CONFIG_READY_PATH, INPUT_READY_PATH, INPUT_RESERVATION_PATH, READY_PATH, DATASET_ROOT,
    } | {row.experiment_config_path for row in plan.runs}
    # Inspect the whole tree's paths/modes, not the source working tree. A link or
    # submodule outside the pin set must not redirect a subsequent bundle write.
    entries = {}
    for row in _git(repository, "ls-tree", "-rz", "--full-tree", sha).stdout.split(b"\0"):
        if not row:
            continue
        metadata, raw_name = row.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        name = raw_name.decode("utf-8")
        _path(repository, name)
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise DisposableCheckoutRefused("reviewed checkout may contain only regular tracked files")
        if any(name == role or name.startswith(role + "/") or role.startswith(name + "/")
               for role in reserved):
            raise DisposableCheckoutRefused("reviewed commit already contains a generated bundle target")
        entries[name] = oid.decode("ascii")

    def blob(name: str) -> bytes:
        return _git(repository, "cat-file", "blob", entries[name]).stdout

    manifest_data = blob(MANIFEST_PATH)
    _same("reviewed commit manifest", yaml.safe_load(manifest_data), manifest)
    sources = {}
    for name, expected in sorted(manifest["source_pins"].items()):
        identity = _identity(blob(name))
        _same("reviewed source pin", identity["sha256"], expected)
        sources[name] = identity
    return {
        "tree_sha": _git(repository, "rev-parse", sha + "^{tree}").stdout.decode("ascii").strip(),
        "manifest_file": {"path": MANIFEST_PATH, **_identity(manifest_data)},
        "source_files": sources,
    }


def _sidecars(destination: Path) -> tuple[Path, Path]:
    return (
        destination.with_name("." + destination.name + ".comparison-checkout-reserved.json"),
        destination.with_name("." + destination.name + ".comparison-checkout-quarantine.json"),
    )


def _destination(value: Path, *sources: Path) -> Path:
    path = Path(value)
    if ".." in path.parts:
        raise DisposableCheckoutRefused("destination parent traversal is forbidden")
    path = Path(os.path.abspath(path))
    _root(path.parent)
    _assert_no_symlink_ancestors(path)
    for source in sources:
        if path.is_relative_to(source) or source.is_relative_to(path):
            raise DisposableCheckoutRefused("destination overlaps a source or Git common directory")
    return path


def _absent(destination: Path) -> None:
    if any(os.path.lexists(path) for path in (destination, *_sidecars(destination))):
        raise DisposableCheckoutRefused("destination or sidecar exists; completed/partial attempts cannot be reused")


def _checkout_state(
    repository: Path, destination: Path, common: Path, sha: str,
    manifest: dict[str, Any], reviewed: dict[str, Any],
) -> None:
    root, actual_common = _repository(destination)
    if root != destination or actual_common != common or not os.path.samefile(common, actual_common):
        raise DisposableCheckoutRefused("created checkout has a different Git common directory")
    _safe_checkout_configuration(root)
    if _git(root, "rev-parse", "--verify", "HEAD").stdout != sha.encode("ascii") + b"\n":
        raise DisposableCheckoutRefused("checkout HEAD is not the caller-reviewed commit")
    symbolic = _git(root, "symbolic-ref", "--quiet", "HEAD", ok=(0, 1))
    if symbolic.returncode != 1 or symbolic.stdout:
        raise DisposableCheckoutRefused("checkout HEAD must remain detached")
    # Bind both directions of Git's linked-worktree registration. Unlike the
    # newer `worktree list -z`, this also works with the host's Git 2.34.1 and
    # does not require parsing quoted, potentially newline-containing paths.
    gitdir = _root(Path(os.fsdecode(_git(
        root, "rev-parse", "--absolute-git-dir",
    ).stdout.rstrip(b"\n"))))
    if (gitdir.parent != common / "worktrees"
            or _read_bytes(root / ".git") != b"gitdir: " + os.fsencode(gitdir) + b"\n"
            or _read_bytes(gitdir / "gitdir") != os.fsencode(root / ".git") + b"\n"
            or _read_bytes(gitdir / "commondir") != b"../..\n"):
        raise DisposableCheckoutRefused("detached checkout registration mismatch")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=no", "--ignore-submodules=none").stdout:
        raise DisposableCheckoutRefused("checkout tracked tree is dirty")
    _same("checkout pinned source bytes", _sources(root, manifest), {
        name: reviewed[name] for name in ("manifest_file", "source_files")
    })


def _intent(plan: ComparisonGradingPlan, index: int, sha: str) -> dict[str, Any]:
    run = plan.dispatch.runs[index]
    return {
        "reviewed_source_sha": sha,
        "source_base_sha": plan.dispatch.source_base_sha,
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "abba_index": index, "task_ids": list(run.task_ids),
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "combined_plan_sha256": _identity(plan.canonical_bytes())["sha256"],
        "source_pins": json.loads(plan.dispatch.source_pins_json),
    }


def _reservation(plan: ComparisonGradingPlan, index: int, sha: str) -> bytes:
    return _canonical_json({
        "reservation_version": "gpt54-disposable-checkout-reservation-v1",
        "ready_path": READY_PATH, "state": "reserved_not_ready",
        **_intent(plan, index, sha),
    }).encode("utf-8")


def _marker(
    destination: Path, plan: ComparisonGradingPlan, index: int, sha: str,
    reviewed: dict[str, Any],
) -> dict[str, Any]:
    run = plan.dispatch.runs[index]
    config = verify_run_config_bundle(checkout=destination, run_id=run.run_id, condition=run.condition)
    inputs = verify_run_input_bundle(checkout=destination, run_id=run.run_id, condition=run.condition)
    markers = {}
    for name, path, value in (("config", CONFIG_READY_PATH, config), ("input", INPUT_READY_PATH, inputs)):
        expected = _canonical_json(value).encode("utf-8")
        if _read_bytes(destination / path, **_identity(expected)) != expected:
            raise DisposableCheckoutRefused("bundle marker bytes mismatch")
        markers[name] = {"path": path, **_identity(expected)}
    return {
        "checkout_version": "gpt54-disposable-checkout-v1",
        **_intent(plan, index, sha),
        "reviewed_tree_sha": reviewed["tree_sha"],
        "bundles": markers,
        "attestation_linkage": config["attestation_linkage"],
        "evidence_boundary": "local_reviewed_checkout_and_bundles",
    }


def verify_disposable_checkout(
    dispatch_run: ComparisonRunSpec, *, repository: Path, reviewed_source_sha: str,
    destination: Path, manifest: dict[str, Any], combined_plan: dict[str, Any],
) -> dict[str, Any]:
    """Read-only exact marker/bundle/HEAD check; does not grant launch permission."""
    try:
        plan, index = _compiled(dispatch_run, manifest, combined_plan)
        repository, common = _common(repository)
        destination = _destination(destination, repository, _root(TRUSTED_ROOT), common)
        reservation, quarantine = _sidecars(destination)
        if os.path.lexists(quarantine):
            raise DisposableCheckoutRefused("quarantined checkout cannot be used")
        reviewed = _reviewed_commit(repository, reviewed_source_sha, manifest, plan)
        expected_reservation = _reservation(plan, index, reviewed_source_sha)
        _read_bytes(reservation, **_identity(expected_reservation))
        with _held_parents(destination, (READY_PATH,)) as check:
            _checkout_state(repository, destination, common, reviewed_source_sha, manifest, reviewed)
            marker = _marker(destination, plan, index, reviewed_source_sha, reviewed)
            expected = _canonical_json(marker).encode("utf-8")
            if _read_bytes(destination / READY_PATH, **_identity(expected)) != expected:
                raise DisposableCheckoutRefused("checkout-ready marker mismatch")
            _checkout_state(repository, destination, common, reviewed_source_sha, manifest, reviewed)
            if os.path.lexists(quarantine):
                raise DisposableCheckoutRefused("checkout was quarantined during verification")
            check()
            return marker
    except DisposableCheckoutRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, yaml.YAMLError) as error:
        raise DisposableCheckoutRefused("checkout verification refused") from error


def prepare_disposable_checkout(
    dispatch_run: ComparisonRunSpec, *, repository: Path, reviewed_source_sha: str,
    destination: Path, manifest: dict[str, Any], combined_plan: dict[str, Any],
    dataset_parquet: Path, reference_root: Path,
) -> dict[str, Any]:
    """Create one detached checkout and seal its exact config and five-task inputs.

    The caller supplies external source-review provenance. No ref is resolved as
    a substitute for that SHA. Failures after reservation retain all remaining
    paths for manual disposal; there is no retry, cleanup or execution fallback.
    """
    from gpt54_codex_input_capture import _write_no_clobber

    reserved = False
    phase = "validation"
    try:
        manifest = json.loads(_canonical_json(manifest))
        combined_plan = json.loads(_canonical_json(combined_plan))
        plan, index = _compiled(dispatch_run, manifest, combined_plan)
        repository, common = _common(repository)
        parquet = Path(dataset_parquet)
        if ".." in parquet.parts:
            raise DisposableCheckoutRefused("parquet parent traversal is forbidden")
        parquet = Path(os.path.abspath(parquet))
        _assert_no_symlink_ancestors(parquet)
        references = _root(reference_root)
        destination = _destination(destination, repository, _root(TRUSTED_ROOT), common, parquet, references)
        _absent(destination)
        reviewed = _reviewed_commit(repository, reviewed_source_sha, manifest, plan)
        snapshot = _source_snapshot(plan, parquet, references)
        reservation, quarantine = _sidecars(destination)
        intent = _reservation(plan, index, reviewed_source_sha)
        with _held_parents(destination.parent, (destination.name,)) as check_parent:
            _absent(destination)
            check_parent()
            phase = "reservation"
            # Even an interrupted first publication quarantines the attempted
            # path; it must not silently become an apparently fresh retry.
            reserved = True
            _write_no_clobber(reservation, intent)
            check_parent()
            # Git accepts existing empty directories. Only the directory created
            # exclusively by this attempt may be given to it, never a caller's.
            destination.mkdir(mode=0o700)
            with _held_parents(destination, (READY_PATH,)) as check_destination:
                phase = "detached_checkout"
                check_parent()
                _git(repository, "worktree", "add", "--detach", "--", str(destination), reviewed_source_sha)
                check_parent()
                check_destination()
                _checkout_state(repository, destination, common, reviewed_source_sha, manifest, reviewed)
                phase = "config_bundle"
                materialize_run_config_bundle(
                    dispatch_run, plan.runs[index], manifest=manifest,
                    combined_plan=combined_plan, checkout=destination,
                )
                check_parent()
                check_destination()
                phase = "input_bundle"
                materialize_run_input_bundle(
                    dispatch_run, manifest=manifest, combined_plan=combined_plan,
                    checkout=destination, dataset_parquet=parquet, reference_root=references,
                )
                check_parent()
                check_destination()
                phase = "ready_verification"
                _same("source inputs after publication", _source_snapshot(plan, parquet, references).shared_binding,
                      snapshot.shared_binding)
                _checkout_state(repository, destination, common, reviewed_source_sha, manifest, reviewed)
                marker = _marker(destination, plan, index, reviewed_source_sha, reviewed)
                _read_bytes(reservation, **_identity(intent))
                if os.path.lexists(quarantine):
                    raise DisposableCheckoutRefused("checkout has been quarantined")
                check_parent()
                check_destination()
                _write_no_clobber(destination / READY_PATH, _canonical_json(marker).encode("utf-8"))
                # Ready alone is insufficient if this final verification fails:
                # a retained quarantine sidecar always takes precedence.
                result = verify_disposable_checkout(
                    dispatch_run, repository=repository, reviewed_source_sha=reviewed_source_sha,
                    destination=destination, manifest=manifest, combined_plan=combined_plan,
                )
                check_parent()
                check_destination()
                return result
    except Exception as error:
        if reserved:
            quarantine_written = False
            try:
                check_parent()
                _write_no_clobber(quarantine, _canonical_json({
                    "quarantine_version": "gpt54-disposable-checkout-quarantine-v1",
                    "reservation": reservation.name, "ready_path": READY_PATH,
                    "phase": phase, "failure_type": type(error).__name__,
                    "disposition": "manual_disposal_required_no_reuse",
                }).encode("utf-8"))
                quarantine_written = True
            except Exception:
                # A moved parent or failed disk cannot safely be repaired here.
                # The retained reservation is itself a refusal of any new try.
                pass
            raise DisposableCheckoutRefused(
                f"checkout preparation failed at {phase}; do not reuse or overwrite; "
                f"remaining checkout={destination} (exists={os.path.lexists(destination)}); "
                f"reservation={reservation} (exists={os.path.lexists(reservation)}); "
                f"quarantine={quarantine} (written={quarantine_written}, exists={os.path.lexists(quarantine)}); "
                "manual disposal required"
            ) from error
        if isinstance(error, DisposableCheckoutRefused):
            raise
        raise DisposableCheckoutRefused("checkout preparation refused before reservation") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--combined-plan", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dataset-parquet", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = yaml.safe_load(_read_bytes(args.manifest))
        combined = yaml.safe_load(_read_bytes(args.combined_plan))
        plan = compile_grading_plan(manifest)
        run = next(run for run in plan.dispatch.runs if run.run_id == args.run_id)
        result = prepare_disposable_checkout(
            run, repository=args.repository, reviewed_source_sha=args.reviewed_source_sha,
            destination=args.destination, manifest=manifest, combined_plan=combined,
            dataset_parquet=args.dataset_parquet, reference_root=args.reference_root,
        )
    except (OSError, ValueError, TypeError, KeyError, StopIteration, yaml.YAMLError) as error:
        detail = str(error) if isinstance(error, DisposableCheckoutRefused) else "invalid local preparation inputs"
        print(json.dumps({"prepared": False, "error": detail}, ensure_ascii=False))
        return 2
    print(_canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
