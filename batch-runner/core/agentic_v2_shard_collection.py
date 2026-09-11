"""Whether a set of finished shards may be called the stage, and what a halt meant.

Three things were true of the sharded path and none of them was visible from
inside a shard.

**`coverage_problems` had no caller.** The workflow comment says the sentence
"the stage ran" is earned "once every shard has reported and ``coverage_problems``
has been shown nothing was run twice and nothing was missed". The function
exists, is tested, and was invoked by nothing that runs. A check named in a
comment and wired to nothing is the same defect as a stop rule written into a
plan and implemented nowhere, and it fails the same way: silently, in the
direction that flatters the run.

**Nothing outside the driver read ``stopped_early``.** A shard that halted wrote
the rule into its record and exited non-zero, and then no step anywhere opened
that record. A stage with one halted shard and sixteen green ones could be
collected and read as a stage that finished.

**A halt was treated as one shard's business whichever rule it was.** The
matrix sets ``fail-fast: false`` on a good argument -- a shard that failed was
already charged for the turns it made, and cancelling its siblings throws away
paid-for work. That argument holds for a runner defect and does not hold for a
reply that named the wrong model, because the deployment is the same one every
other shard is about to ask. ``RULES_ABOUT_THE_WHOLE_RUN`` is where that split
is written down and argued; this module is what reads it.

**What this deliberately does not do.** It does not stop a shard that is already
running. Nothing here can: the jobs are concurrent and a job cannot cancel a
sibling. What :func:`siblings_that_stopped_the_run` offers is narrower and worth
stating as narrow -- a shard *about to start* can decline to, so a halt in one
wave stops the waves after it. At ``max-parallel: 4`` that bounds a rule-0 halt
in the two hundred and twenty to about four shards' spend instead of seventeen.
It is not zero and must not be described as zero.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.agentic_v2_preregistration import (
    RULES_ABOUT_THE_WHOLE_RUN,
    RULES_THAT_ARE_ONE_SHARDS_OWN,
    STOP_RULES,
)
from core.agentic_v2_sharding import Shard, coverage_problems

#: The file each shard leaves behind, inside its own artifact directory.
RUN_RECORD_NAME = "run_record.json"


class ShardRecordUnreadable(ValueError):
    """Raised for a record that cannot be made to mean anything.

    Deliberately not a return value. Every other disagreement in this module is
    reported as a problem string so that all of them can be shown at once, but a
    record that will not parse is not a finding about the run -- it is this code
    being unable to look. Telling the two apart matters, because "the stage is
    fine" and "the stage could not be checked" are read very differently and a
    list of strings makes them look the same.
    """


def read_shard_records(directory: Path) -> list[tuple[str, dict[str, Any]]]:
    """Every shard record under ``directory``, with the folder it came from.

    The artifacts download one folder per shard, named for the shard, and the
    folder name is kept because it is the only thing a person can use to find
    the job again. The record's own ``shard.index`` is what the checks use;
    where the two disagree that is itself worth seeing, so neither is discarded
    in favour of the other.
    """
    found: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(directory.rglob(RUN_RECORD_NAME)):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as problem:
            raise ShardRecordUnreadable(
                f"{path} could not be read as a run record: {problem}"
            ) from problem
        if not isinstance(body, Mapping):
            raise ShardRecordUnreadable(
                f"{path} parsed to {type(body).__name__} and not an object"
            )
        found.append((path.parent.name, dict(body)))
    return found


def _shard_of(record: Mapping[str, Any]) -> Shard:
    piece = record.get("shard")
    if not isinstance(piece, Mapping):
        raise ShardRecordUnreadable(
            "a run record has no `shard` object, so there is no way to say "
            "which piece of the cohort it covered"
        )
    try:
        return Shard(
            index=int(piece["index"]),
            of=int(piece["of"]),
            task_ids=tuple(str(task_id) for task_id in piece["task_ids"]),
            cohort_size=int(piece["cohort_size"]),
        )
    except (KeyError, TypeError, ValueError) as problem:
        raise ShardRecordUnreadable(
            f"a run record's `shard` object is not usable: {problem}"
        ) from problem


def _halt_in(record: Mapping[str, Any]) -> Mapping[str, Any] | None:
    run = record.get("run")
    if not isinstance(run, Mapping):
        return None
    stopped = run.get("stopped_early")
    return stopped if isinstance(stopped, Mapping) else None


def _rule_index_of(halt: Mapping[str, Any]) -> int | None:
    """Which of the eight, by index, or ``None`` if the record does not say.

    Prefers the recorded index and falls back to matching the rule text, because
    the index is what the classification is keyed on and the text is what
    survives a record being read by something that does not have this code.
    Returns ``None`` rather than guessing when neither is usable: an
    unrecognised halt is handled by the caller as the most serious case, and a
    wrong guess here would quietly make it the least serious one.
    """
    index = halt.get("rule_index")
    if isinstance(index, int) and 0 <= index < len(STOP_RULES):
        return index
    text = str(halt.get("rule") or "").strip()
    for position, rule in enumerate(STOP_RULES):
        if rule == text:
            return position
    return None


def siblings_that_stopped_the_run(
    records: Iterable[tuple[str, Mapping[str, Any]]],
) -> list[str]:
    """Reasons a shard that has not started yet should not start.

    Only the halts that are facts about the whole run. A sibling that hit three
    runner defects, or could not write its ledger, or left a guest dirty, is a
    finding about itself and is no reason to refuse a shard whose tasks,
    runner and guest are all different ones.

    An unrecognised halt counts. A record naming a rule this code cannot place
    is either a rule that was added without this classification being revisited
    or a record this code does not understand, and both are reasons to stop
    rather than to carry on spending.
    """
    reasons: list[str] = []
    for name, record in records:
        halt = _halt_in(record)
        if halt is None:
            continue
        index = _rule_index_of(halt)
        detail = str(halt.get("detail") or "").strip()
        if index is None:
            reasons.append(
                f"shard {name} stopped on a rule this code cannot place "
                f"({halt.get('rule')!r}). An unplaced rule is treated as a "
                f"fact about the whole run, because the alternative is to "
                f"keep spending on the strength of not recognising it"
                + (f": {detail}" if detail else "")
            )
            continue
        if index not in RULES_ABOUT_THE_WHOLE_RUN:
            continue
        reasons.append(
            f"shard {name} stopped on rule {index}, {STOP_RULES[index]}. "
            f"{RULES_ABOUT_THE_WHOLE_RUN[index]}"
            + (f". {detail}" if detail else "")
        )
    return reasons


def stage_problems(
    records: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    task_ids: Sequence[str],
) -> list[str]:
    """Every reason this set of shards is not the stage it was meant to be.

    Coverage and halts together, because they are the same question asked twice.
    Coverage asks whether every task was run once; halts ask whether what ran
    was the run that was registered. A stage needs both, and a check that
    answered only the first would pass a cohort answered throughout by the
    wrong model.
    """
    problems: list[str] = []
    if not records:
        return ["no shard record was found, so nothing here can say what ran"]

    problems.extend(
        coverage_problems(
            [_shard_of(record) for _, record in records], task_ids=task_ids
        )
    )

    for name, record in records:
        halt = _halt_in(record)
        if halt is None:
            continue
        index = _rule_index_of(halt)
        detail = str(halt.get("detail") or "").strip()
        if index is None:
            problems.append(
                f"shard {name} stopped on a rule this code cannot place "
                f"({halt.get('rule')!r})"
                + (f": {detail}" if detail else "")
            )
        elif index in RULES_ABOUT_THE_WHOLE_RUN:
            problems.append(
                f"shard {name} stopped on rule {index}, {STOP_RULES[index]} -- "
                f"which is not one shard's own: "
                f"{RULES_ABOUT_THE_WHOLE_RUN[index]}. The other shards' results "
                f"are in question too"
                + (f". {detail}" if detail else "")
            )
        else:
            problems.append(
                f"shard {name} stopped on rule {index}, {STOP_RULES[index]}. "
                f"This one is the shard's own -- "
                f"{RULES_THAT_ARE_ONE_SHARDS_OWN[index]} -- so the other "
                f"shards' results stand, but this shard's tasks did not all run"
                + (f". {detail}" if detail else "")
            )
    return problems
