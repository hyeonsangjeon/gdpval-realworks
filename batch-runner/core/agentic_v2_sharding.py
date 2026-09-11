"""Splitting one stage across several runs, without losing what the stage was.

A stage is a fixed cohort: five tasks, thirty, or two hundred and twenty. The
cohort is sealed before the run, and the seal is what lets a result be quoted as
*this* experiment rather than some tasks that happened to be handy. Nothing here
touches that. What it does is let the cohort be *run* in pieces, because one
piece is all that fits in the place the paid run has to happen.

**Why pieces are necessary.** The plan fixes ``per_task_timeout_seconds: 1200``,
so a task may take twenty minutes. A GitHub Actions job is killed at six hours.
That is eighteen tasks in the very worst case, and the worst case is the only one
a limit may be designed against — thirty tasks is already ten hours and the full
two hundred and twenty is over seventy-three. So the choice is not between one
job and several; it is between several jobs and a stage that cannot be run at
all beyond the first five.

**Why the split is by stride and not by block.** ``task_ids[i::n]`` deals the
cohort out like cards. A block split — first eleven, next eleven — would hand one
shard a run of neighbouring tasks, and the cohort is ordered by a selection rule
that groups related work together. If a block shard is lost, what is missing from
the partial result is *all of one kind of work*; if a stride shard is lost, what
is missing is a thin slice of every kind. Both lose the same number of tasks. Only
one of them lets the remainder still be described.

**What a shard is not.** It is not a smaller stage. A run of one shard has not run
the stage, and :meth:`Shard.as_dict` says so in the record rather than leaving the
reader to work it out from a count. :func:`coverage_problems` is how a set of
finished shards earns the sentence "the stage ran" — by showing that every task
was covered exactly once, not by adding up how many each shard reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence


class ShardRefused(ValueError):
    """Raised for a split that would not mean what it says."""


@dataclass(frozen=True)
class Shard:
    """One piece of a cohort, and the whole it is a piece of.

    Carries ``cohort_size`` rather than only its own tasks, because a record
    holding twelve task ids and no denominator is indistinguishable from a
    twelve-task experiment.
    """

    index: int
    """Which piece, counted from one.

    From one rather than from zero because this number is written by a person
    into a workflow input and read by a person out of a run record, and "shard 0
    of 20" is read as *none of them* about as often as it is read correctly.
    """

    of: int
    task_ids: tuple[str, ...]
    cohort_size: int

    @property
    def covers_whole_stage(self) -> bool:
        return self.of == 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "of": self.of,
            "task_count": len(self.task_ids),
            "cohort_size": self.cohort_size,
            "task_ids": list(self.task_ids),
            "covers_whole_stage": self.covers_whole_stage,
            "what_this_run_is": (
                "the whole stage, in one run"
                if self.covers_whole_stage
                else (
                    f"{len(self.task_ids)} of the {self.cohort_size} tasks in "
                    f"this stage. The stage has not run until all {self.of} "
                    "shards have, and their coverage has been checked"
                )
            ),
        }


def split(task_ids: Sequence[str], of: int) -> tuple[tuple[str, ...], ...]:
    """Deal the cohort into ``of`` piles, one card at a time.

    Every task lands in exactly one pile and the order inside a pile follows the
    cohort's own order, so a shard is reproducible from the cohort and its two
    numbers alone — nothing about the split is stored anywhere or has to be.
    """
    if of < 1:
        raise ShardRefused("a cohort cannot be split into fewer than one piece")
    if of > len(task_ids):
        raise ShardRefused(
            f"{len(task_ids)} tasks cannot be split into {of} pieces without "
            "leaving some piece empty, and an empty run that reports success "
            "is worse than one that refuses to start"
        )
    return tuple(tuple(task_ids[start::of]) for start in range(of))


def shard_of(task_ids: Sequence[str], index: int, of: int) -> Shard:
    """The one piece this run is responsible for."""
    if index < 1 or index > of:
        raise ShardRefused(
            f"shard {index} of {of} does not exist; shards are numbered 1 to {of}"
        )
    return Shard(
        index=index,
        of=of,
        task_ids=split(task_ids, of)[index - 1],
        cohort_size=len(task_ids),
    )


def parse(text: str | None, task_ids: Sequence[str]) -> Shard | None:
    """``"3/20"`` as a shard of this cohort, or ``None`` for the whole of it.

    ``None`` rather than a one-of-one shard for the unsharded case, so a caller
    that forgot to handle sharding at all behaves exactly as it did before this
    module existed instead of picking up a new code path by default.
    """
    if text is None or text.strip() in {"", "all", "1/1"}:
        return None
    try:
        left, right = text.split("/", 1)
        index, of = int(left.strip()), int(right.strip())
    except ValueError as error:
        raise ShardRefused(
            f"{text!r} is not a shard. Write it as index/total, like 3/20"
        ) from error
    if of == 1:
        return None
    return shard_of(task_ids, index, of)


def how_many_shards_fit(
    *,
    cohort_size: int,
    per_task_timeout_seconds: float,
    job_limit_seconds: float,
    margin: float = 0.75,
) -> int:
    """The fewest pieces that fit the worst case inside the job limit.

    ``margin`` is not timidity. A job spends time before the first task —
    checkout, a Python install, the dataset download — and a run that is killed
    at the limit loses the task it was in the middle of, which is the one thing a
    resume cannot recover cheaply. Three quarters leaves room for both.

    Worst case throughout: every task is assumed to run to its timeout. Most will
    not, and sizing against what most tasks do is how a run gets killed at hour
    six with nothing collected.
    """
    if cohort_size < 1:
        raise ShardRefused("a cohort with no tasks needs no shards")
    usable = job_limit_seconds * margin
    if usable < per_task_timeout_seconds:
        raise ShardRefused(
            f"one task may take {per_task_timeout_seconds:.0f}s and a job has "
            f"{usable:.0f}s of usable time, so no split makes this fit"
        )
    per_shard = int(usable // per_task_timeout_seconds)
    return -(-cohort_size // per_shard)


def coverage_problems(
    shards: Iterable[Shard], *, task_ids: Sequence[str]
) -> list[str]:
    """Every reason a set of finished shards is not the whole stage.

    The question this answers is the one that decides whether the results may be
    described as the stage's results. Counting is not enough: twenty shards that
    each ran twelve tasks could still have run one task twice and missed another,
    and the total would look right.
    """
    shards = list(shards)
    problems: list[str] = []
    if not shards:
        return ["no shard ran, so the stage did not run"]

    totals = {shard.of for shard in shards}
    if len(totals) > 1:
        problems.append(
            f"the shards disagree about how many there are ({sorted(totals)}), "
            "so they are pieces of different splits and cannot be added up"
        )
        return problems

    of = totals.pop()
    missing_indices = sorted(set(range(1, of + 1)) - {shard.index for shard in shards})
    if missing_indices:
        problems.append(
            f"{len(missing_indices)} of {of} shards did not run: "
            + ", ".join(str(index) for index in missing_indices)
        )

    seen: dict[str, int] = {}
    for shard in shards:
        for task_id in shard.task_ids:
            seen[task_id] = seen.get(task_id, 0) + 1

    twice = sorted(task_id for task_id, count in seen.items() if count > 1)
    if twice:
        problems.append(
            f"{len(twice)} tasks were covered by more than one shard, so they "
            f"were paid for twice: {', '.join(twice[:3])}"
            + (" and others" if len(twice) > 3 else "")
        )

    never = sorted(set(task_ids) - set(seen))
    if never:
        problems.append(
            f"{len(never)} of the {len(task_ids)} tasks in this stage were "
            f"covered by no shard: {', '.join(never[:3])}"
            + (" and others" if len(never) > 3 else "")
        )

    stranger = sorted(set(seen) - set(task_ids))
    if stranger:
        problems.append(
            f"{len(stranger)} tasks were run that are not in this stage: "
            + ", ".join(stranger[:3])
        )
    return problems
