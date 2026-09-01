#!/usr/bin/env python3
"""Report shard relays that stopped without producing a final grade.

``#194`` gave a shard that finds a short union a way to stand down politely:
it exits ``75`` and lets whichever sibling finishes last do the merge. That is
right for the normal case and it removed a large class of false red runs. It
also widened a hole that was already there. If one shard never finishes, every
surviving sibling defers, nobody merges, and no final grade is ever written.

The failure is quiet in a specific way. A shard that *crashes* turns its own
workflow run red, and after ``#194`` red means something really broke, so the
common case reports itself. The case nothing reports is a shard that ends
**green** without finishing -- the auto-resume relay dispatches the next chunk
with ``gh workflow run``, and if that dispatch fails (rate limit, expired
token, a transient API error) the run still ends successfully. The relay is
broken and every signal is green.

It cannot be closed inside the merge step, because shards are independent
``workflow_dispatch`` runs rather than a matrix: no job can ``needs:`` all of
them, so there is nowhere to hang "everyone is done, now merge". This sweep
watches from outside instead. It is read-only -- it never dispatches, never
merges, never writes. It reads what has been committed and says whether anyone
is still making progress.

Liveness comes from git rather than from the workflow API. A working shard
commits its slice at the end of every chunk, so the newest commit touching a
stem directory is a direct record of progress; an idle shard leaves that
timestamp standing still. That is both cheaper and less ambiguous than matching
dispatch inputs against ``Run GDPVal Grade Pipeline``, which is the display
title every shard of every run shares.

Run it from ``batch-runner/``, the way the other scripts here are run::

    python3 scripts/sweep_stalled_shard_relays.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

import yaml


class ShardReadError(ValueError):
    """A shard file cannot be read as a shard."""


def load_shard_file(path: Path) -> tuple[dict, str]:
    """Return ``(payload, sha256_of_file_bytes)`` for one shard file.

    A deliberate copy of ``step9_merge_shards.load_shard_file`` rather than an
    import of it. Importing reaches ``step9_merge_shards`` ->
    ``core.grade_payload`` -> ``jsonschema``, and ``step9_merge_shards`` ->
    ``step8_grade`` -> ``core.azure_ai_clients`` and the rest of the judging
    stack. A watchdog that needs the whole grading dependency set installed
    before it can report anything is a watchdog that stops watching every time
    that set moves -- and this one runs on a schedule where nobody is looking.
    The copy is held to the original by
    ``test_the_borrowed_shard_reader_still_matches_step9``.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShardReadError(f"could not read shard {path}: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ShardReadError(f"could not parse shard {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ShardReadError(f"shard {path} top-level JSON must be an object")
    return payload, hashlib.sha256(raw).hexdigest()


def shard_task_ids(payload: dict, label: str) -> list[str]:
    """Return the task ids a shard payload claims, rejecting a malformed one.

    Copied from ``step9_merge_shards._shard_task_ids`` for the reason above.
    Kept behaviourally identical, error messages included, so a stem the
    merger would refuse reads as ``malformed`` here with the same explanation.
    """
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise ShardReadError(f"{label} has no tasks array")
    if not tasks:
        raise ShardReadError(f"{label} contains zero graded tasks")
    task_ids: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for index, row in enumerate(tasks):
        if not isinstance(row, dict):
            raise ShardReadError(f"{label} task at index {index} is not an object")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ShardReadError(
                f"{label} task at index {index} has no non-empty task_id"
            )
        if task_id in seen:
            duplicates.add(task_id)
        seen.add(task_id)
        task_ids.append(task_id)
    if duplicates:
        raise ShardReadError(
            f"{label} contains duplicate task_ids: {sorted(duplicates)}"
        )
    return task_ids


#: How long a stem may go without a new commit before the relay is called
#: stopped. A healthy chunk is capped by ``GRADER_TIME_BUDGET_SEC=18000`` (5h)
#: in ``grade-run.yml``, after which the shard partial-saves, commits, and
#: re-dispatches itself, so the longest legitimate silence is one chunk plus
#: queueing and dependency install -- about five and a half hours. Eight hours
#: leaves roughly two and a half hours of margin on top of that: late enough
#: never to interrupt a slow-but-working run, early enough that a broken relay
#: is found the same day rather than the next time somebody looks.
STALE_AFTER_HOURS_DEFAULT = 8.0

#: ``grade-run.yml`` writes ``printf 'shard-%03d-of-%03d.json'``.
SHARD_NAME = re.compile(r"^shard-(\d{3})-of-(\d{3})\.json$")

#: States that mean a human has to do something. Everything else is either
#: finished or still moving.
FAILING_STATES = frozenset({"stalled", "unmerged", "malformed"})


@dataclass(frozen=True)
class RelayVerdict:
    """What the sweep concluded about one ``_shards/<stem>/`` directory."""

    stem: str
    state: str
    detail: str
    quiet_for_hours: float | None = None
    #: shard index -> the task ids it still owes, when the canonical order is
    #: known. Empty when it is not; see ``shortfall_by_shard``.
    missing_by_shard: dict[int, list[str]] = field(default_factory=dict)
    #: shard index -> how many tasks it still owes. Always populated for a
    #: failing verdict, because a count can be derived from the stride profile
    #: alone even when the canonical ids cannot be recovered.
    shortfall_by_shard: dict[int, int] = field(default_factory=dict)

    @property
    def failing(self) -> bool:
        return self.state in FAILING_STATES


def ordered_task_ids_sha256(task_ids: Sequence[str]) -> str:
    """Hash an ordered id list the way ``step8_grade`` does.

    Kept byte-identical to ``step8_grade._ordered_task_ids_sha256`` so a
    grading config's pinned list can be checked against the value the shards
    recorded. Duplicated rather than imported because importing ``step8_grade``
    pulls in the whole judging stack for one hash.
    """
    encoded = json.dumps(
        list(task_ids),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stride_owner(position: int, shard_count: int) -> int:
    """Return the shard index that owns canonical ``position``.

    ``step8_grade._shard_slice`` splits by stride (``tasks[i::n]``), so
    ownership is just the position modulo the shard count.
    """
    if shard_count <= 1:
        return 0
    return position % shard_count


def stride_size(shard_index: int, total: int, shard_count: int) -> int:
    """How many tasks shard ``shard_index`` is responsible for."""
    if shard_count <= 1:
        return total
    return len(range(shard_index, total, shard_count))


def parse_commit_stamp(text: str) -> datetime | None:
    """Read the first parseable ``%cI`` timestamp out of ``git log`` output.

    Two renderings have to be accepted. git through ~2.4x writes UTC as
    ``2026-08-20T09:00:00+00:00``; git 2.55 writes the same instant as
    ``2026-08-20T09:00:00Z``. Python 3.10's ``fromisoformat`` accepts only the
    first, so a sweep that parsed naively would read every stem as "cannot
    tell" on a current runner while passing on an older developer box -- silent
    and total, since `unknown` is a quiet state by design.

    Scanning lines rather than taking the whole stream keeps stray output from
    a configured hook or signature check from masking a real answer.
    """
    for line in text.splitlines():
        stamp = line.strip()
        if not stamp:
            continue
        if stamp.endswith(("Z", "z")):
            stamp = f"{stamp[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def last_commit_at(repo_root: Path, path: Path) -> datetime | None:
    """Return the commit time of the newest commit touching ``path``.

    ``None`` when git knows nothing about the path -- an uncommitted or
    shallow-cloned directory. The caller treats that as "cannot tell" and
    stays quiet rather than guessing, because file mtimes after a CI checkout
    are checkout time and would make every stem look brand new.

    The pathspec is made relative to the resolved work tree before it is handed
    to git. That is not tidying: the shipped defaults are ``--repo-root ..`` and
    ``--grades-root ../data/grades``, so passing the stem through unchanged
    hands git a pathspec starting with ``..`` from a cwd inside the repository,
    which it refuses as outside the work tree. Resolving both ends also makes
    the answer independent of which side happens to carry a symlink.
    """
    try:
        root = repo_root.resolve()
        relative = os.path.relpath(path.resolve(), root)
    except OSError:
        return None
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        # Genuinely outside the work tree. Nothing git can say about it.
        return None

    try:
        completed = subprocess.run(
            # `log.showSignature` is a global-config footgun: with it on, every
            # `git log` interleaves verification output, and a monitoring script
            # that parsed the first line would read noise as "cannot tell".
            [
                "git",
                "-c",
                "log.showSignature=false",
                "log",
                "-1",
                "--format=%cI",
                "--",
                Path(relative).as_posix(),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return parse_commit_stamp(completed.stdout)


def canonical_ids_from_configs(
    config_dir: Path, expected_sha256: str
) -> list[str] | None:
    """Find the pinned canonical id list matching ``expected_sha256``.

    Matching by hash rather than by parsing the stem for a config name: the
    stem is a long underscore-joined string whose fields could be re-ordered,
    while the hash is the same value the shards themselves agreed on. A config
    that hashes correctly *is* the right one, so this verifies instead of
    assuming, and simply finds nothing when no config pins that corpus.
    """
    if not expected_sha256 or not config_dir.is_dir():
        return None
    for candidate in sorted(config_dir.glob("*.yaml")):
        try:
            loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(loaded, dict):
            continue
        identity = loaded.get("rerun_identity")
        if not isinstance(identity, dict):
            continue
        task_ids = identity.get("task_ids")
        if not isinstance(task_ids, list) or not task_ids:
            continue
        if not all(isinstance(value, str) for value in task_ids):
            continue
        if ordered_task_ids_sha256(task_ids) == expected_sha256:
            return list(task_ids)
    return None


def _agreed(payloads: Sequence[dict], key: str):
    """Return the value all payloads carry for ``key``, or raise on a split."""
    values = {json.dumps(payload.get(key), sort_keys=True) for payload in payloads}
    if len(values) != 1:
        raise ShardReadError(f"shards disagree on {key}")
    return payloads[0].get(key)


def inspect_stem(
    stem_dir: Path,
    *,
    final_path: Path,
    now: datetime,
    stale_after: timedelta,
    commit_time: Callable[[Path], datetime | None],
    canonical_lookup: Callable[[str], list[str] | None],
) -> RelayVerdict:
    """Classify one ``_shards/<stem>/`` directory."""
    stem = stem_dir.name

    if final_path.exists():
        return RelayVerdict(stem, "merged", "final grade is published")

    shard_files: dict[int, Path] = {}
    declared_counts: set[int] = set()
    for candidate in sorted(stem_dir.iterdir()):
        match = SHARD_NAME.match(candidate.name)
        if match is None:
            continue
        index, count = int(match.group(1)), int(match.group(2))
        declared_counts.add(count)
        if index in shard_files:
            return RelayVerdict(
                stem, "malformed", f"shard index {index} appears more than once"
            )
        shard_files[index] = candidate

    if not shard_files:
        return RelayVerdict(stem, "empty", "no shard files")
    if len(declared_counts) != 1:
        counts = ", ".join(str(value) for value in sorted(declared_counts))
        return RelayVerdict(
            stem, "malformed", f"shard files disagree on the shard count: {counts}"
        )

    shard_count = declared_counts.pop()
    absent = [index for index in range(shard_count) if index not in shard_files]
    if absent:
        # Not a stalled relay. A shard that has published nothing has either not
        # been dispatched yet or is still inside its first chunk, and both are
        # normal -- the canary-first procedure deliberately runs shard 0 alone
        # for hours before the rest go out. Reported, never failed on.
        listed = ", ".join(str(index) for index in absent)
        return RelayVerdict(
            stem,
            "fanning-out",
            f"{len(shard_files)}/{shard_count} shards have published; "
            f"waiting on {listed}",
        )

    payloads: dict[int, dict] = {}
    union: set[str] = set()
    holdings: dict[int, int] = {}
    for index, path in sorted(shard_files.items()):
        try:
            payload, _ = load_shard_file(path)
            ids = shard_task_ids(payload, f"{stem} shard {index}")
        except ShardReadError as exc:
            return RelayVerdict(stem, "malformed", str(exc))
        payloads[index] = payload
        holdings[index] = len(ids)
        union.update(ids)

    ordered = [payloads[index] for index in sorted(payloads)]
    try:
        expected_total = _agreed(ordered, "expected_task_count")
        expected_sha = _agreed(ordered, "expected_ordered_task_ids_sha256")
    except ShardReadError as exc:
        return RelayVerdict(stem, "malformed", str(exc))
    if not isinstance(expected_total, int) or expected_total <= 0:
        return RelayVerdict(
            stem, "malformed", "shards carry no usable expected_task_count"
        )

    newest = commit_time(stem_dir)
    if newest is None:
        return RelayVerdict(
            stem, "unknown", "git has no commit touching this stem; cannot judge liveness"
        )
    quiet = now - newest
    quiet_hours = round(quiet.total_seconds() / 3600.0, 2)

    if quiet < stale_after:
        return RelayVerdict(
            stem,
            "working",
            f"{len(union)}/{expected_total} tasks in, last commit "
            f"{quiet_hours}h ago",
            quiet_for_hours=quiet_hours,
        )

    shortfall = {
        index: stride_size(index, expected_total, shard_count) - holdings[index]
        for index in range(shard_count)
        if stride_size(index, expected_total, shard_count) > holdings[index]
    }

    missing_by_shard: dict[int, list[str]] = {}
    canonical = canonical_lookup(expected_sha) if isinstance(expected_sha, str) else None
    if canonical is not None and len(canonical) == expected_total:
        for position, task_id in enumerate(canonical):
            if task_id in union:
                continue
            missing_by_shard.setdefault(
                stride_owner(position, shard_count), []
            ).append(task_id)

    if len(union) >= expected_total:
        return RelayVerdict(
            stem,
            "unmerged",
            f"all {expected_total} tasks are in and no shard has merged them "
            f"for {quiet_hours}h",
            quiet_for_hours=quiet_hours,
        )

    return RelayVerdict(
        stem,
        "stalled",
        f"{len(union)}/{expected_total} tasks in and nothing has been "
        f"committed for {quiet_hours}h",
        quiet_for_hours=quiet_hours,
        missing_by_shard=missing_by_shard,
        shortfall_by_shard=shortfall,
    )


def sweep(
    grades_root: Path,
    *,
    now: datetime,
    stale_after: timedelta,
    commit_time: Callable[[Path], datetime | None],
    canonical_lookup: Callable[[str], list[str] | None],
) -> list[RelayVerdict]:
    """Classify every stem under ``<grades_root>/_shards/``."""
    shards_root = grades_root / "_shards"
    if not shards_root.is_dir():
        return []
    verdicts: list[RelayVerdict] = []
    for stem_dir in sorted(shards_root.iterdir()):
        if not stem_dir.is_dir():
            continue
        verdicts.append(
            inspect_stem(
                stem_dir,
                final_path=grades_root / f"{stem_dir.name}.json",
                now=now,
                stale_after=stale_after,
                commit_time=commit_time,
                canonical_lookup=canonical_lookup,
            )
        )
    return verdicts


def render(verdicts: Iterable[RelayVerdict], *, annotate: bool) -> list[str]:
    """Return the human-readable report lines."""
    lines: list[str] = []
    for verdict in verdicts:
        lines.append(f"[{verdict.state}] {verdict.stem}")
        lines.append(f"    {verdict.detail}")
        for index in sorted(
            set(verdict.shortfall_by_shard) | set(verdict.missing_by_shard)
        ):
            owed = verdict.shortfall_by_shard.get(index)
            ids = verdict.missing_by_shard.get(index, [])
            suffix = f": {', '.join(ids)}" if ids else ""
            owed_text = "?" if owed is None else str(owed)
            lines.append(f"    shard {index:03d} still owes {owed_text} task(s){suffix}")
        if annotate and verdict.failing:
            lines.append(
                f"::error title=Shard relay {verdict.state}::"
                f"{verdict.stem}: {verdict.detail}"
            )
    return lines


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report shard relays that stopped without writing a final grade. "
            "Read-only: never dispatches, merges, or writes."
        )
    )
    parser.add_argument(
        "--grades-root",
        default="../data/grades",
        help="Directory holding <stem>.json finals and the _shards/ tree",
    )
    parser.add_argument(
        "--config-dir",
        default="grading_configs",
        help="Where to look for a config pinning the canonical task id order",
    )
    parser.add_argument(
        "--repo-root",
        default="..",
        help="Git working tree used to read commit times",
    )
    parser.add_argument(
        "--stale-after-hours",
        type=float,
        default=STALE_AFTER_HOURS_DEFAULT,
        help=(
            "Silence tolerated before a relay is called stopped "
            f"(default {STALE_AFTER_HOURS_DEFAULT})"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.stale_after_hours <= 0:
        print("--stale-after-hours must be positive", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve()
    config_dir = Path(args.config_dir)
    verdicts = sweep(
        Path(args.grades_root),
        now=datetime.now(timezone.utc),
        stale_after=timedelta(hours=args.stale_after_hours),
        commit_time=lambda path: last_commit_at(repo_root, path),
        canonical_lookup=lambda sha: canonical_ids_from_configs(config_dir, sha),
    )

    if not verdicts:
        print("no shard relays to inspect")
        return 0

    annotate = bool(os.environ.get("GITHUB_ACTIONS"))
    for line in render(verdicts, annotate=annotate):
        print(line)

    failing = [verdict for verdict in verdicts if verdict.failing]
    if failing:
        print(f"\n{len(failing)} shard relay(s) need attention", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
