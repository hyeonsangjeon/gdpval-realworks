#!/usr/bin/env python3
"""Answer the questions exp034 registered before it was allowed to spend.

Why this exists
---------------
``experiments/exp034_codex_foundry_trial30.yaml`` writes three claims into its
header *before* the run, so that they can be wrong:

1. **A prediction about where failure lands.** In exp033 the two tasks that
   succeeded carried the two longest task statements. Across the thirty,
   eleven of thirty statements are shorter than 2,000 characters, so under the
   null -- failure having nothing to do with statement length -- any given
   failure lands short 36.7% of the time. Pile-up means the association is
   real; proportional scatter means the five points were noise.

2. **A question the run can answer alone.** exp034 raises ``max_retries`` from
   2 to 3, so a task may now reach a fourth attempt, and the fourth is the
   first to wait 240 s. *Did a fourth attempt ever convert a task that three
   attempts had not?* If nothing in thirty converts, the extra budget bought
   nothing and the next stage drops it.

3. **A measurement never yet taken.** ``items_seen`` has a producer as of
   ``core/codex_runner.py`` but no run has ever carried it: exp033's artifact
   contains the string zero times. The first run dispatched after that lands
   is the first real reading.

Answering these by hand against a downloaded artifact means writing the same
queries again under time pressure, when the temptation to round in a
convenient direction is highest. They are written here instead, and were
tested against exp033's real artifact -- a run whose answers are already
known -- before exp034 produced any data.

What this does
--------------
Given an unpacked run artifact, it reports per task the status, the error
category recorded by ``classify_execution_error``, the number of settled
ledger rows (which is the attempt count), and the cost state. Then it answers
the three registered questions directly, and prints the contingency table the
first one turns on.

What it will not do
-------------------
* **It does not score.** Success here means the pipeline produced a
  deliverable, not that the deliverable is any good. Grading is a separate
  run with a separate cost, and the two are never added together.
* **It does not convert a null cost into a zero.** A ledger row whose USD is
  unknown is reported as unknown with its stated reason. ``partial`` is a
  state this prints, not a state it repairs.
* **It does not decide whether an association is a defect.** A shorter task
  statement is a vaguer task, and a model given a vaguer task wandering into
  content a filter stops is a benchmark result. This file reports where
  failures land; what that means is not its call.
* **It does not divide by a zero denominator.** No tasks in a bucket prints as
  "no tasks", never as 0%.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

#: The header's boundary, restated so the comparison is reproducible.
SHORT_STATEMENT_CHARS = 2000

#: The null exp034's header registered before the run: eleven of its thirty
#: statements fall under the boundary, so a failure indifferent to statement
#: length lands short this often. Recomputed from the artifact below and
#: compared against this, because a disagreement means the artifact is not the
#: run the prediction was registered for -- which is worth saying out loud
#: rather than quietly scoring a different population.
REGISTERED_SHORT_SHARE_PCT = 36.7

#: Outcomes where the turn never started, so ``items_seen`` was never set and
#: the zero in the record is the dataclass default standing in for a value
#: nobody took. ``core/codex_runner.py`` returns these four without passing
#: ``items_seen`` at all -- ``runtime_unavailable``, ``runtime_start_failed``,
#: ``session_start_failed``, ``turn_start_failed`` -- while the timeout, turn
#: failure, and success paths all pass ``observed.items_seen``.
#:
#: The distinction is the whole point of the field. A refusal after forty
#: items and a refusal after two are different claims about which limit was
#: reached; a refusal before the stream opened is not a claim about item
#: count at all, and averaging its zero in would drag the measurement toward
#: "the turn spends nothing" for reasons that have nothing to do with
#: spending.
#:
#: Only these four are listed because only these four are enumerable. What a
#: started turn reports comes from ``classify_execution_error``, whose
#: vocabulary is open, so an allow-list of post-stream categories cannot be
#: written down. A category outside every set below is flagged rather than
#: assumed into either one.
PRE_STREAM_FAILURE_CATEGORIES = frozenset(
    {
        "runtime_unavailable",
        "runtime_start_failed",
        "session_start_failed",
        "turn_start_failed",
    }
)


def _items_seen_is_measured(task: dict) -> bool:
    """Whether this task's ``items_seen`` is a count or an unset default."""
    if not isinstance(task.get("items_seen"), int):
        return False
    if task.get("status") == "success":
        return True
    return str(task.get("error_category")) not in PRE_STREAM_FAILURE_CATEGORIES


def _load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _find(root: Path, *names: str) -> Path | None:
    """First of ``names`` that exists under ``root``, searched shallowly."""
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    for name in names:
        hits = sorted(root.rglob(name))
        if hits:
            return hits[0]
    return None


def _statement_of(task: dict) -> str:
    """The task text whose length the header's prediction is about.

    ``instruction`` is the key this dataset revision uses, and it is the one
    the registered figures were computed from -- exp033's ``02aa1805`` measures
    1,589 characters here, which is the number written into exp034's header.
    The alternatives are tried after it so that a later revision renaming the
    field degrades to "cannot test" rather than to a silent zero.
    """
    for key in ("instruction", "prompt", "task_statement", "statement"):
        value = task.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def collect(root: Path) -> dict:
    results_path = _find(root, "step2_inference_results.json")
    if results_path is None:
        raise SystemExit(f"no step2_inference_results.json under {root}")
    payload = _load_json(results_path)
    results = payload.get("results", payload if isinstance(payload, list) else [])

    prepared_path = _find(root, "step1_tasks_prepared.json")
    statements: dict[str, str] = {}
    sectors: dict[str, str] = {}
    if prepared_path is not None:
        prepared = _load_json(prepared_path)
        tasks = prepared.get("tasks", prepared if isinstance(prepared, list) else [])
        for task in tasks:
            tid = str(task.get("task_id", ""))
            if tid:
                statements[tid] = _statement_of(task)
                sectors[tid] = str(task.get("sector", ""))

    ledger: list[dict] = []
    for name in ("cost_ledger_condition_a.jsonl", "cost_ledger.jsonl"):
        found = _find(root, name)
        if found is not None:
            ledger = _load_jsonl(found)
            break

    rows_by_task: dict[str, list[dict]] = defaultdict(list)
    for row in ledger:
        rows_by_task[str(row.get("task_id"))].append(row)

    tasks = []
    for result in results:
        tid = str(result.get("task_id", ""))
        observability = result.get("observability") or {}
        # Where the persisted record actually keeps it. `codex_runner` hands
        # the turn's numbers up under `codex_diagnostics`, and
        # `_bounded_codex_diagnostics` re-homes them at
        # `observability.codex` before anything is written to disk -- so the
        # top level never carries them, and a reader that looks there reports
        # "never measured" about the one measurement the run was dispatched
        # to take. The top level is still consulted second, because a reader
        # that breaks on a future move of the field is worse than one that
        # tries both.
        codex = observability.get("codex") or {}
        cost = result.get("problem_solving_cost") or {}
        rows = rows_by_task.get(tid, [])
        tasks.append(
            {
                "task_id": tid,
                "status": result.get("status"),
                "error_category": observability.get("error_category"),
                "attempts": len(rows),
                "settled": sum(1 for r in rows if r.get("state") == "settled"),
                "retry_kinds": Counter(str(r.get("retry_kind")) for r in rows),
                "cost_status": cost.get("status"),
                "known_cost_usd": cost.get("known_cost_usd"),
                "missing_reasons": sorted(
                    {m for r in rows for m in (r.get("missing_reasons") or [])}
                ),
                "items_seen": codex.get("items_seen", result.get("items_seen")),
                # The provider's own answer, kept beside the item count
                # because the two are read together: a 429 after many items
                # and a 429 after two are different claims about which limit
                # was reached.
                "http_status_code": codex.get(
                    "http_status_code", result.get("http_status_code")
                ),
                "latency_ms": result.get("latency_ms"),
                "chars": len(statements.get(tid, "")),
                "sector": sectors.get(tid, ""),
            }
        )
    return {"meta": payload, "tasks": tasks, "ledger": ledger}


def _pct(part: int, whole: int, noun: str = "tasks") -> str:
    """A rate, or the reason there isn't one. Never 0% from an empty bucket.

    ``noun`` names what the denominator counts, so that an empty bucket says
    which bucket was empty. A run with no failures at all must not report
    "no tasks" about a set of tasks that plainly exists.
    """
    if whole == 0:
        return f"no {noun}"
    return f"{part}/{whole} = {part / whole * 100:.1f}%"


def report(data: dict) -> None:
    tasks = data["tasks"]
    meta = data["meta"]

    print(f"experiment : {meta.get('experiment_id')}")
    print(f"run_id     : {meta.get('run_id')}")
    print(f"model      : {meta.get('model')}   mode: {meta.get('execution_mode')}")
    print(f"resume     : rounds used = {meta.get('resume_rounds_used')}")
    print()

    print("=== per task ===")
    header = f"{'task':10} {'status':9} {'category':18} {'att':>3} {'chars':>6} {'items':>6} cost"
    print(header)
    print("-" * len(header))
    for t in sorted(tasks, key=lambda x: (x["status"] != "success", x["task_id"])):
        print(
            f"{t['task_id'][:8]:10} {str(t['status']):9} "
            f"{str(t['error_category']):18} {t['attempts']:>3} "
            f"{t['chars']:>6} {str(t['items_seen']):>6} {t['cost_status']}"
        )
    print()

    total = len(tasks)
    ok = [t for t in tasks if t["status"] == "success"]
    bad = [t for t in tasks if t["status"] != "success"]
    print(f"=== outcome ===  success {_pct(len(ok), total)}")
    print("  categories:", dict(Counter(str(t["error_category"]) for t in bad)) or "none")
    print()

    by_sector: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        by_sector[t["sector"] or "(unrecorded)"].append(t)
    if len(by_sector) > 1:
        print("=== by sector ===")
        for sector, group in sorted(by_sector.items()):
            won = sum(1 for t in group if t["status"] == "success")
            print(f"  {sector[:46]:48} {_pct(won, len(group))}")
        print()

    # --- Registered question 1: does failure pile up in short statements? ---
    print("=== 1. where failure lands ===")
    measured = [t for t in tasks if t["chars"] > 0]
    unmeasured = [t for t in tasks if t["chars"] <= 0]
    if not measured:
        print("  task statements were not carried in the artifact -- cannot test.")
    else:
        if unmeasured:
            # Shrinking the denominator without saying so would turn a partly
            # unreadable artifact into a confident-looking rate.
            print(f"  NOT TESTED      : {len(unmeasured)}/{len(tasks)} tasks carried "
                  f"no statement in the artifact and are excluded below "
                  f"({', '.join(t['task_id'][:8] for t in unmeasured)})")
        short = [t for t in measured if t["chars"] < SHORT_STATEMENT_CHARS]
        long_ = [t for t in measured if t["chars"] >= SHORT_STATEMENT_CHARS]
        short_bad = [t for t in short if t["status"] != "success"]
        long_bad = [t for t in long_ if t["status"] != "success"]
        failures = len(short_bad) + len(long_bad)
        base = len(short) / len(measured) * 100
        print(f"  boundary        : {SHORT_STATEMENT_CHARS} chars")
        print(f"  chars min/max   : {min(t['chars'] for t in measured)} "
              f"{max(t['chars'] for t in measured)}   "
              f"median {statistics.median(t['chars'] for t in measured)}")
        print(f"  short tasks     : {len(short)}/{len(measured)} = {base:.1f}%  "
              f"<- the null: this is how often a failure lands short by chance")
        if round(base, 1) != REGISTERED_SHORT_SHARE_PCT:
            print(f"  NOTE            : the registered null was "
                  f"{REGISTERED_SHORT_SHARE_PCT}%, so this artifact is not the "
                  f"population that prediction was written for. The comparison "
                  f"below is against this run's own {base:.1f}%.")
        print(f"  failures short  : {_pct(len(short_bad), failures, 'failures')}")
        print()
        print(f"    {'':12}{'failed':>8}{'ok':>8}")
        print(f"    {'short':12}{len(short_bad):>8}{len(short) - len(short_bad):>8}")
        print(f"    {'long':12}{len(long_bad):>8}{len(long_) - len(long_bad):>8}")
        print()
        print(f"  failure rate short : {_pct(len(short_bad), len(short), 'short tasks')}")
        print(f"  failure rate long  : {_pct(len(long_bad), len(long_), 'long tasks')}")
        print("  (reported, not adjudicated -- a vaguer task failing is a "
              "benchmark result, not automatically a defect)")
    print()

    # --- Registered question 2: did a fourth attempt ever convert? ---
    print("=== 2. did a fourth attempt convert what three did not? ===")
    deep = [t for t in tasks if t["attempts"] >= 4]
    if not deep:
        print("  no task reached a fourth attempt. The raised budget was never "
              "exercised, so this run does not answer the question either way.")
    else:
        converted = [t for t in deep if t["status"] == "success"]
        print(f"  reached 4+ attempts : {len(deep)}")
        for t in deep:
            print(f"    {t['task_id'][:8]}  attempts={t['attempts']}  -> {t['status']}")
        print(f"  converted           : "
              f"{_pct(len(converted), len(deep), 'deep tasks')}")
        if not converted:
            print("  The extra attempt bought nothing here. The next stage may drop it.")
    print()

    # --- Registered question 3: items_seen, first real reading ---
    print("=== 3. items_seen ===")
    seen = [t for t in tasks if _items_seen_is_measured(t)]
    unset = [
        t
        for t in tasks
        if isinstance(t["items_seen"], int) and not _items_seen_is_measured(t)
    ]
    if unset:
        # Reporting these as zeros would answer the registered question with
        # the dataclass default of a field the run never reached.
        print(f"  NOT MEASURED    : {len(unset)}/{len(tasks)} tasks failed before "
              f"the turn started, so their 0 is the field's default, not a count "
              f"({', '.join(sorted(str(t['error_category']) for t in unset))})")
    if not seen:
        print("  absent from every task -- this artifact predates the producer, "
              "or no turn reported one. Not a measurement of zero.")
    else:
        values = [t["items_seen"] for t in seen]
        print(f"  carried on {len(seen)}/{len(tasks)} tasks   "
              f"min {min(values)}  max {max(values)}  median {statistics.median(values)}")

        # The discriminator this field was added for. A 429 is the provider
        # saying no; where in the turn it arrives is the part that says what
        # it was refusing. Refused after many items points at what one turn
        # consumes; refused at zero or near it points at something decided
        # before the turn spent anything -- arrival rate, concurrency, or a
        # reservation that was already full. This prints the two numbers side
        # by side and stops there: which limit it is, is not a thing a table
        # of item counts can settle on its own.
        refused = [t for t in seen if t["http_status_code"] == 429]
        if refused:
            print()
            print(f"  of those, refused with HTTP 429 : {len(refused)}")
            for t in sorted(refused, key=lambda x: x["items_seen"]):
                print(f"    {t['task_id'][:8]}  items_seen={t['items_seen']:<5} "
                      f"attempts={t['attempts']}")
            at_zero = sum(1 for t in refused if t["items_seen"] == 0)
            print(f"    refused before any item : "
                  f"{_pct(at_zero, len(refused), '429 tasks')}")
        else:
            statuses = sorted(
                {str(t["http_status_code"]) for t in seen if t["http_status_code"]}
            )
            print(f"  no task carried HTTP 429 alongside a measured item count"
                  f"{'   (statuses seen: ' + ', '.join(statuses) + ')' if statuses else ''}")
    print()

    # --- Cost: reported, never repaired, never added to grading ---
    print("=== cost (task-solving only; grading is a separate run) ===")
    ledger = data["ledger"]
    states = Counter(str(r.get("state")) for r in ledger)
    print(f"  ledger rows     : {len(ledger)}   states: {dict(states)}")
    print(f"  retry kinds     : {dict(Counter(str(r.get('retry_kind')) for r in ledger))}")
    print(f"  resolved models : {dict(Counter(str(r.get('resolved_model')) for r in ledger))}")
    known = [r.get("model_cost_usd") for r in ledger if isinstance(r.get("model_cost_usd"), (int, float))]
    reasons = Counter(m for r in ledger for m in (r.get("missing_reasons") or []))
    statuses = Counter(str(t["cost_status"]) for t in tasks)
    print(f"  cost status     : {dict(statuses)}")
    if reasons:
        print(f"  USD unknown because: {dict(reasons)}")
        print("  -> the run's dollar cost is UNDETERMINED, which is not zero.")
    elif known:
        print(f"  model cost USD  : {sum(known)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "artifact",
        type=Path,
        help="directory holding an unpacked run artifact (workspace/ and results/)",
    )
    args = parser.parse_args(argv)
    if not args.artifact.is_dir():
        raise SystemExit(f"not a directory: {args.artifact}")
    report(collect(args.artifact))
    return 0


if __name__ == "__main__":
    sys.exit(main())
