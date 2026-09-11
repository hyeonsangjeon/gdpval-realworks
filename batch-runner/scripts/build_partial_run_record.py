#!/usr/bin/env python3
"""Build the preserved record of a relay leg that did not finish its 220.

A leg of the exp035 relay stops when its watchdog fires, not when the work is
done. What it leaves is a checkpoint, a ledger, and a log -- not a report, and
not anything the dashboard will ever read, because a truncated run is not a
publishable experiment. ``docs/run_records/README.md`` says where such a record
goes and why it is not ``results/``.

The first of these records, for run 34571840967, was assembled by hand. This
script exists so the second one is not, and so the two can be compared: run it
against that leg's artifact and it reproduces the committed file. A record
built twice by two different methods is two records.

Usage
-----

    python scripts/build_partial_run_record.py <artifact-dir> \
        --run-id <id> --output-dir docs/run_records/<name> [--log <job-log>]

``<artifact-dir>`` is the unpacked ``batch-results-<run-id>`` artifact.

What each output is
-------------------
``outcomes.json``  One row per task in the fixed 220, in catalogue order,
                   whether or not the leg reached it. A task the leg never
                   started is recorded as ``never_started`` with no cost and
                   no ``codex_items_seen`` -- not as a zero, which would read
                   as "it ran and produced nothing".

``deliverable_manifest.json``  Name, size and sha256 of every file the leg
                   produced, keyed by task. The files themselves stay in the
                   artifact; several hundred megabytes do not belong in git.

The log and what is lost without it
-----------------------------------
``--log`` is the job log, ANSI already stripped. It is the **only** place the
provider's own sentence survives: the checkpoint stores
``error: "task_execution_error:TaskExecutionError"`` for every failure alike,
which names the exception class and not the cause. Without the log the record
still builds, and every row that would have carried a message instead carries
``message_source: "not_available"``. That is a gap in the record, stated as
one. It is never filled with a guess.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from derive_run_cost import derive, uncalled_row  # noqa: E402

#: Failure categories the pipeline records, split by whose result they are.
#: `benchmark_failure` means the model was asked a real question and what it
#: produced was refused -- that is the benchmark working. Everything else here
#: is the run place, and must not be counted against the model.
FAILURE_CLASSES = {
    "content_filtered": "benchmark_failure",
    "rate_limited": "execution_environment",
    "transport_error": "execution_environment",
    "turn_failed": "execution_environment",
}

#: What each category means, in the words the record will be read in.
#:
#: The `rate_limited` note is deliberate about mechanism. An earlier version of
#: this record said the request "did not reach the deployment", which the same
#: rows refute: they carry settled calls, output tokens and stream items. See
#: `tests/test_a_run_record_note_may_not_deny_its_own_row.py`.
FAILURE_NOTES = {
    "content_filtered": (
        "모델이 응답을 거부했습니다. 이 벤치마크가 재려는 것의 일부이므로 우회하지 "
        "않고 그대로 둡니다."
    ),
    "rate_limited": (
        "배포가 요금 한도로 턴을 거절해 과제가 끝났습니다. 거절이 오기 전까지 모델은 "
        "이미 답을 만들고 있었고(같은 줄의 calls_settled·output_tokens·"
        "codex_items_seen이 그 증거입니다) 그 작업은 버려졌습니다. 모델의 오답이 "
        "아니며 성공률 계산에 실패로 넣으면 안 됩니다."
    ),
    "transport_error": (
        "응답을 받는 도중 연결이 끊겼습니다. 모델의 오답이 아니라 실행 환경 문제이며 "
        "성공률 계산에 실패로 넣으면 안 됩니다."
    ),
    "turn_failed": (
        "요청을 보내는 단계에서 턴이 끝났습니다. 모델의 오답이 아니라 실행 환경 "
        "문제이며 성공률 계산에 실패로 넣으면 안 됩니다."
    ),
}

#: Short reason words, kept stable across records so they can be counted.
REASONS = {
    "content_filtered": "content_filter",
    "rate_limited": "rate_limit",
    "transport_error": "transport_error",
    "turn_failed": "turn_failed",
}

COST_NOTE = (
    "영수증의 model_cost_usd 0.0은 status=partial 이고 missing_reasons 가 있으므로 "
    '"확정된 하한"이지 총액이 아닙니다. 실제 금액은 미확정이며 0이 아닙니다.'
)

TASK_HEADER = re.compile(r"\[(\d+)/(\d+)\]\s+([0-9a-f-]{36})\b")
TASK_FAILED = re.compile(r"✗\s+(.*?)\s*$")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _ledger_by_task(ledger: Path) -> dict[str, dict]:
    """Per-task call counts and token totals, straight from the ledger.

    ``resolved_model`` is taken from **settled** calls only. A reservation that
    was never concluded has no model on it, and letting one of those decide the
    task's value prints "unknown" over a task whose settled call names
    `gpt-5.4` and carries six figures of tokens. Which model answered and how
    many calls went unmeasured are separate questions, and the second already
    has its own fields.
    """
    conn = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "calls_settled": 0,
            "calls_reserved": 0,
            "retries_infrastructure": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "deployment": None,
            "resolved_model": None,
            "price_table_sha256": None,
        }
    )
    for row in conn.execute("SELECT * FROM cost_calls"):
        agg = out[row["task_id"]]
        agg["calls"] += 1
        settled = row["state"] == "settled"
        if settled:
            agg["calls_settled"] += 1
        else:
            agg["calls_reserved"] += 1
        if row["retry_kind"] and row["retry_kind"] != "none":
            agg["retries_infrastructure"] += 1
        for field in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_tokens",
        ):
            agg[field] += row[field] or 0
        if agg["deployment"] is None and row["deployment"]:
            agg["deployment"] = row["deployment"]
        if settled:
            for field in ("resolved_model", "price_table_sha256"):
                if agg[field] is None and row[field]:
                    agg[field] = row[field]
    conn.close()
    return dict(out)


def _messages_from_log(log: Path | None) -> dict[str, str]:
    """Each task's failure sentence, as the provider worded it.

    A task's outcome can land either on its own ``[n/220]`` header line or on a
    later retry-progress line, so the most recent header is carried forward.
    Only the last ✗ for a task is kept: the earlier ones are retries of it.
    """
    if log is None:
        return {}
    messages: dict[str, str] = {}
    current: str | None = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        header = TASK_HEADER.search(line)
        if header:
            current = header.group(3)
        if current is None:
            continue
        failed = TASK_FAILED.search(line)
        if failed:
            messages[current] = failed.group(1)
    return messages


def _deliverables(artifact: Path) -> dict[str, list[dict]]:
    """Every produced file, hashed, keyed by the task that produced it.

    Walked top-down -- a directory's own files, then its subdirectories, each
    sorted -- because that is the order the first of these records was written
    in and reordering 128 entries would bury a real change in a cosmetic diff.
    """

    def walk(directory: Path) -> list[Path]:
        entries = sorted(directory.iterdir())
        files = [p for p in entries if p.is_file()]
        for sub in (p for p in entries if p.is_dir()):
            files.extend(walk(sub))
        return files

    root = artifact / "workspace" / "upload" / "deliverable_files"
    if not root.is_dir():
        return {}
    out: dict[str, list[dict]] = {}
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        files = []
        for path in walk(task_dir):
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
            files.append(
                {
                    "name": str(path.relative_to(task_dir)),
                    "bytes": path.stat().st_size,
                    "sha256": digest.hexdigest(),
                }
            )
        if files:
            out[task_dir.name] = files
    return out


def build(
    artifact: Path, log: Path | None
) -> tuple[list[dict], dict[str, list[dict]], dict]:
    workspace = artifact / "workspace"
    prepared = _read_json(workspace / "step1_tasks_prepared.json")
    progress = _read_json(workspace / "step2_inference_progress_condition_a.json")
    ledger_path = workspace / "cost_ledger_condition_a.sqlite3"

    derived = derive([ledger_path])
    per_task = derived["per_task"]
    method = derived["method"]
    ledger = _ledger_by_task(ledger_path)
    messages = _messages_from_log(log)
    files = _deliverables(artifact)

    catalogue = {t["task_id"]: t for t in prepared["tasks"]}
    results = {r["task_id"]: r for r in progress["results"]}
    reached = sum(
        1 for r in progress["results"] if r.get("status") in ("success", "error")
    )

    rows = []
    for n, task_id in enumerate(progress["ordered_task_ids"], start=1):
        task = catalogue[task_id]
        result = results.get(task_id, {})
        status = result.get("status", "pending")
        attempted = status in ("success", "error")

        row = {
            "n": n,
            "task_id": task_id,
            "sector": task["sector"],
            "occupation": task["occupation"],
            "status": status,
        }

        if not attempted:
            row.update(
                {
                    "attempted": False,
                    "outcome": "never_started",
                    "reason": "run_ended_before_this_task",
                    "note": (
                        f"실행이 {reached}번째 문제에서 끝나 이 문제는 시도되지 "
                        "않았습니다. 아래 checkpoint_error_field는 체크포인트가 "
                        "미시도 항목에도 채워 넣는 기본값이며 실제 실패가 아닙니다."
                    ),
                    "checkpoint_error_field": result.get("error"),
                    "checkpoint_error_field_is_placeholder": True,
                    "calls": 0,
                    "cost_state": "not_incurred",
                    "model_cost_usd": 0.0,
                }
            )
            row.update(uncalled_row(method))
            rows.append(row)
            continue

        category = (result.get("observability") or {}).get("error_category")
        receipt = result.get("problem_solving_cost") or {}
        agg = ledger.get(task_id, {})
        produced = files.get(task_id, [])

        row.update(
            {
                "attempted": True,
                "outcome": "ok" if status == "success" else "failed",
                # `category` is absent when a task failed without the pipeline
                # recording a kind. Guarding on it keeps `reason` null there --
                # the same value `REASONS.get(None)` would give -- rather than
                # letting an unknown failure borrow a named one.
                "reason": REASONS.get(category) if status == "error" and category else None,
                "message": messages.get(task_id, "") if status == "error" else "",
                # First try plus each infrastructure retry. The ledger writes one
                # row per turn attempt, so `calls` agrees -- but the two are
                # different questions and only this one is "how many tries".
                "attempts": 1 + agg.get("retries_infrastructure", 0),
                "calls": agg.get("calls", 0),
                "calls_settled": agg.get("calls_settled", 0),
                "calls_reserved": agg.get("calls_reserved", 0),
                "retries_infrastructure": agg.get("retries_infrastructure", 0),
                "input_tokens": agg.get("input_tokens", 0),
                "cached_input_tokens": agg.get("cached_input_tokens", 0),
                "output_tokens": agg.get("output_tokens", 0),
                "reasoning_tokens": agg.get("reasoning_tokens", 0),
                "deployment": agg.get("deployment"),
                "resolved_model": agg.get("resolved_model"),
                "cost_state": "undetermined",
                "model_cost_usd": receipt.get("estimated_cost_usd"),
                "cost_receipt_status": receipt.get("status"),
                "cost_receipt_model_cost_usd_floor": receipt.get("model_cost_usd"),
                "cost_receipt_estimated_cost_usd": receipt.get("estimated_cost_usd"),
                "cost_missing_reason": (receipt.get("missing_reasons") or [None])[0],
                "cost_note": COST_NOTE,
                "price_table_sha256": receipt.get("price_table_sha256"),
                "latency_ms": result.get("latency_ms"),
                "deliverable_file_count": len(produced),
                "deliverable_bytes": sum(f["bytes"] for f in produced),
            }
        )
        if status == "error" and category:
            row["failure_class"] = FAILURE_CLASSES.get(category, "unclassified")
            row["failure_class_note"] = FAILURE_NOTES.get(
                category, "이 실행은 이 실패를 분류할 근거를 남기지 않았습니다."
            )
        if log is None and status == "error":
            row["message_source"] = "not_available"

        row.update(per_task.get(task_id, uncalled_row(method)))
        row["codex_items_seen"] = (
            (result.get("observability") or {}).get("codex") or {}
        ).get("items_seen")
        rows.append(row)

    return rows, files, derived


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="job log with ANSI stripped; without it no failure message is recorded",
    )
    args = parser.parse_args()

    rows, files, derived = build(args.artifact, args.log)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    (args.output_dir / "outcomes.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (args.output_dir / "deliverable_manifest.json").write_text(
        # indent=2 and no trailing newline: the first record's format, kept so a
        # rebuild of it diffs clean and any difference that shows up is real.
        json.dumps(files, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    attempted = [r for r in rows if r["attempted"]]
    ok = [r for r in attempted if r["outcome"] == "ok"]
    unpriced = [
        r["n"] for r in attempted if r["derived_cost_usd_from_measured_tokens"] is None
    ]
    print(f"run {args.run_id}: {len(rows)} tasks in the fixed set")
    print(f"  attempted     {len(attempted)}")
    print(f"  succeeded     {len(ok)}")
    print(f"  failed        {len(attempted) - len(ok)}")
    print(f"  never started {len(rows) - len(attempted)}")
    print(f"  files         {sum(len(v) for v in files.values())}")
    # The ledger-wide figure, not a sum of the per-task ones: those are rounded
    # to six places each, so adding them back up drifts by ~1e-5. Report the
    # total that was computed once over every call.
    print(f"  derived floor ${derived['derived_total_usd']:.6f}  (a floor, never a bill)")
    print(
        f"  calls         {derived['calls_total']} "
        f"= {derived['calls_measured']} measured + "
        f"{derived['calls_unmeasured']} unmeasured"
    )
    if unpriced:
        print(f"  unpriced rows {unpriced} -- attempted, no amount derivable")
    if args.log is None:
        print("  no --log: no failure message recorded for any failed task")


if __name__ == "__main__":
    main()
