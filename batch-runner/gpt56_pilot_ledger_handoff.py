"""Model-free, linear Actions handoff of the existing USD-200 SQLite ledger.

No provider, grader, credentials, real task inputs or live launch authority.
The three wallets below are independent synthetic scenarios, not three budgets
for the real pilot. Historical registrations and the money implementation are
read unchanged. An external predecessor digest is mandatory after shard zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import gpt56_pilot_usd_budget as usd
from core import runner_environment as host

BATCH = Path(__file__).resolve().parent
SCHEMA = "pilot-ledger-handoff-model-free-v1"
MANIFEST = "handoff.json"
SCENARIOS = ("continuity", "ceiling", "interruption")
TASKS = (
    "02aa1805-c658-4069-8a6a-02dec146063a",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
)
MAX_JSON = 131072
MAX_DB = 4 * 1024 * 1024
EXPECTED_INTERRUPT_EXIT = 75
FILE_NAMES = frozenset(
    f"{scenario}-{role}" for scenario in SCENARIOS
    for role in (usd.IDENTITY, usd.DATABASE)
)
SOURCE_PATHS = (
    "gpt56_pilot_ledger_handoff.py", "gpt56_pilot_usd_budget.py",
    "core/runner_environment.py",
)


class HandoffRefused(ValueError):
    def __init__(self, code="pilot_ledger_handoff_refused"):
        self.code = code
        super().__init__(code)


def _require(condition, code="pilot_ledger_handoff_refused"):
    if not condition:
        raise HandoffRefused(code)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _same(actual, expected):
    _require(_json(actual) == _json(expected))


def _unique(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value)
        value[key] = item
    return value


def _parents(path):
    _require(path.is_absolute())
    for parent in path.parents:
        _require(stat.S_ISDIR(parent.lstat().st_mode))


def _read(path, maximum):
    path = Path(path)
    _parents(path)
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= maximum)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        _require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino))
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    fields = lambda value: (value.st_dev, value.st_ino, value.st_size,
                            value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)
    _require(fields(before) == fields(after) == fields(path.lstat())
             and len(data) == before.st_size)
    return data


def _new_directory(path):
    path = Path(path)
    _parents(path)
    _require(not os.path.lexists(path), "handoff_destination_not_fresh")
    os.mkdir(path, 0o700)


def _write(path, data):
    _parents(Path(path))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def implementation_hashes():
    usd.price_document()  # The existing cap and price-file guards still run.
    return {path: _sha(_read(BATCH / path, MAX_DB)) for path in SOURCE_PATHS}


def checked_lineage(value):
    _require(type(value) is dict and set(value) == {
        "repository", "run_id", "run_attempt", "source_sha"})
    _require(value["repository"] == "hyeonsangjeon/gdpval-realworks"
             and type(value["run_id"]) is str
             and re.fullmatch(r"[1-9][0-9]{0,19}", value["run_id"]) is not None
             and value["run_attempt"] == "1"
             and type(value["source_sha"]) is str
             and re.fullmatch(r"[0-9a-f]{40}", value["source_sha"]) is not None,
             "handoff_lineage_refused")
    return dict(value)


def _capture(lineage, scenario):
    return _sha(_json({"schema": SCHEMA, "lineage": lineage, "scenario": scenario,
                       "implementation": implementation_hashes(), "task_ids": list(TASKS)}))


def _ledger(workspace, lineage, scenario, *, create=False):
    return usd.PilotUsdLedger(workspace, capture_sha256=_capture(lineage, scenario),
                              task_ids=list(TASKS), create=create)


def _checked_runner(receipt, lineage):
    host.validate_receipt(receipt)
    _same(receipt["stage"], "diagnostic")
    observation = receipt["observation"]
    for key, expected in {"github_actions": "true", "github_hosted": True,
                          "eligible_for_execution": True, "runner_environment": "github-hosted",
                          "os_id": "ubuntu", "os_version_id": "24.04", "image_os": "ubuntu24",
                          "run_id": lineage["run_id"], "run_attempt": lineage["run_attempt"]}.items():
        _same(observation[key], expected)


def _checked_history(value, lineage, next_shard):
    history = value["history"]
    _require(type(history) is list and len(history) == next_shard)
    previous = {}
    for index, row in enumerate(history):
        _require(type(row) is dict and set(row) == {"shard_index", "scenarios", "runner"})
        _same(row["shard_index"], index)
        _checked_runner(row["runner"], lineage)
        _same(sorted(row["scenarios"]), sorted(SCENARIOS))
        for scenario in SCENARIOS:
            record = row["scenarios"][scenario]
            _require(type(record) is dict and set(record) == {
                "synthetic_requests", "replayed_settlements", "interruption_injected",
                "worker_started", "snapshot", "next_worker_allowed"})
            for name in ("synthetic_requests", "replayed_settlements"):
                _require(type(record[name]) is int and 0 <= record[name] <= 10)
            for name in ("interruption_injected", "worker_started", "next_worker_allowed"):
                _require(type(record[name]) is bool)
            snapshot = record["snapshot"]
            _require(usd.checked_snapshot(snapshot) and snapshot["pending_requests"] == 0)
            _same(snapshot["ledger_id"], value["scenarios"][scenario]["binding"]["ledger_id"])
            _same(record["next_worker_allowed"], snapshot["stop_reason"] is None and index < 4)
            earlier = previous.get(scenario)
            if earlier is not None:
                _require(Decimal(snapshot["combined_modeled_usd"]) >= Decimal(earlier["combined_modeled_usd"]))
                if earlier["stop_reason"] is not None:
                    _same(snapshot, earlier)
                    _same([record["worker_started"], record["synthetic_requests"], record["replayed_settlements"]],
                          [False, 0, 0])
            previous[scenario] = snapshot
    _same(history[-1]["runner"], value["producer_runner"])


def read_handoff(directory, expected_sha256, lineage, next_shard):
    """The expected digest comes from needs.<previous>.outputs, not this file."""
    directory = Path(directory)
    checked_lineage(lineage)
    _require(type(next_shard) is int and 1 <= next_shard <= 5)
    _require(type(expected_sha256) is str
             and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
             "handoff_predecessor_required")
    _parents(directory)
    _require(stat.S_ISDIR(directory.lstat().st_mode))
    _same(sorted(path.name for path in directory.iterdir()), sorted({MANIFEST, *FILE_NAMES}))
    raw = _read(directory / MANIFEST, MAX_JSON)
    _require(_sha(raw) == expected_sha256, "handoff_digest_mismatch")
    value = json.loads(raw, object_pairs_hook=_unique)
    _same(raw.decode("ascii"), _json(value).decode("ascii"))
    _require(type(value) is dict and set(value) == {
        "schema", "mode", "lineage", "implementation", "shard_index", "previous_sha256",
        "task_ids", "scenarios", "history", "model_calls", "judge_calls",
        "paid_execution_allowed", "evidence_boundary", "producer_runner"})
    for key, expected in {
        "schema": SCHEMA, "mode": "model-free", "lineage": lineage,
        "implementation": implementation_hashes(), "shard_index": next_shard - 1,
        "task_ids": list(TASKS), "model_calls": 0, "judge_calls": 0,
        "paid_execution_allowed": False,
        "evidence_boundary": "synthetic_ledger_transfer_not_live_pilot_or_billing",
    }.items():
        _same(value[key], expected)
    _checked_runner(value["producer_runner"], lineage)
    previous = value["previous_sha256"]
    _require(previous is None if next_shard == 1 else
             type(previous) is str and re.fullmatch(r"[0-9a-f]{64}", previous) is not None)
    _same(sorted(value["scenarios"]), sorted(SCENARIOS))
    _checked_history(value, lineage, next_shard)
    files = {}
    for scenario in SCENARIOS:
        record = value["scenarios"][scenario]
        _require(type(record) is dict and set(record) == {"binding", "snapshot", "files"})
        _require(usd.checked_snapshot(record["snapshot"]))
        _require(record["snapshot"]["pending_requests"] == 0)
        _same(record["binding"]["capture_sha256"], _capture(lineage, scenario))
        _same(record["binding"]["task_ids"], list(TASKS))
        _same(record["binding"]["ledger_id"], record["snapshot"]["ledger_id"])
        _same(sorted(record["files"]), sorted((usd.DATABASE, usd.IDENTITY)))
        for role, description in record["files"].items():
            name = f"{scenario}-{role}"
            _same(sorted(description), ["sha256", "size"])
            data = _read(directory / name, MAX_DB if role == usd.DATABASE else MAX_JSON)
            _same(description, {"sha256": _sha(data), "size": len(data)})
            files[name] = data
        _same(json.loads(files[f"{scenario}-{usd.IDENTITY}"], object_pairs_hook=_unique),
              record["binding"])
        _same(value["history"][-1]["scenarios"][scenario]["snapshot"], record["snapshot"])
    return value, files


def _restore(workspace, lineage, predecessor, expected_sha256, shard_index):
    _require(predecessor is not None, "handoff_predecessor_required")
    value, files = read_handoff(predecessor, expected_sha256, lineage, shard_index)
    _new_directory(workspace)
    for scenario in SCENARIOS:
        root = workspace / scenario
        _new_directory(root)
        _new_directory(root / usd.DIRECTORY)
        for role in (usd.IDENTITY, usd.DATABASE):
            _write(root / usd.DIRECTORY / role, files[f"{scenario}-{role}"])
        ledger = _ledger(root, lineage, scenario)
        try:
            _same(ledger.binding(), value["scenarios"][scenario]["binding"])
            _same(ledger.snapshot(), value["scenarios"][scenario]["snapshot"])
        finally:
            ledger.close()
    return value


def _cost(scenario, index, origin):
    if scenario == "ceiling":
        return Decimal(("35" if origin == "inference" else "14") if index < 4 else "5")
    return Decimal("1" if origin == "inference" else "4")


def _fake_transport(scenario, task_id, origin, amount):
    """Literal synthetic settlement, NOT a price or a provider response."""
    return amount, Decimal(0)


def _request(ledger, lineage, scenario, index, origin, counters):
    task = TASKS[index]
    amount = _cost(scenario, index, origin)
    request_id = _sha(_json([ledger.identity["capture_sha256"], task, origin]))[:32]
    with ledger._transaction():
        row = ledger.connection.execute(
            "SELECT r.*,a.origin,a.task FROM reservations r JOIN accounts a ON a.id=r.account WHERE r.id=?",
            (request_id,),
        ).fetchone()
    if row is not None:
        _require(row["origin"] == origin and row["task"] == task)
        if row["state"] == "unknown":
            # Owner decision 2026-10-30: the whole reservation stays booked and
            # the wallet continues, but the same request is never sent again.
            return
        _require(row["state"] == "settled")
        _same([str(Decimal(row["settled_io"])), row["settled_cache"]], [str(amount), "0"])
        _require(ledger.settle(request_id, amount, Decimal(0)) is None)
        counters["replayed_settlements"] += 1
        return
    account = ledger.begin(origin, task)
    # This is the original admission method, not a copied/relaxed USD guard.
    ticket = ledger.reserve(account, amount, request_id=request_id)
    try:
        counters["synthetic_requests"] += 1
        io, cache = _fake_transport(scenario, task, origin, amount)
        reason = ledger.settle(ticket, io, cache)
    except Exception:
        # Unknown usage keeps its reservation as consumed spend; not a stop.
        ledger.abandon(account)
        return
    if reason is not None:
        raise usd.PilotUsdRefused(reason, origin)


def _preview_next(ledger, scenario, shard_index):
    """Refuse the next shard in the predecessor, before its worker can start."""
    snapshot = ledger.snapshot()
    if snapshot["stop_reason"] is not None or shard_index == 4:
        return
    reserve = _cost(scenario, shard_index + 1, "inference")
    if Decimal(snapshot["combined_modeled_usd"]) + reserve > usd.APPROVED_MAXIMUM_USD:
        account = ledger.begin("inference", TASKS[shard_index + 1])
        try:
            ledger.reserve(account, reserve)
        except usd.PilotUsdRefused as refused:
            _require(refused.code == usd.CEILING)
        else:
            raise HandoffRefused("handoff_ceiling_guard_missing")


def _run_scenario(ledger, lineage, scenario, shard_index):
    counters = {"synthetic_requests": 0, "replayed_settlements": 0,
                "interruption_injected": False, "worker_started": False}
    if ledger.snapshot()["stop_reason"] is not None:
        return counters
    counters["worker_started"] = True
    try:
        # Revisit earlier tasks using stable request IDs. Settled calls are
        # idempotent; an unknown reservation stays booked and is never re-sent.
        for index in range(shard_index + 1):
            _request(ledger, lineage, scenario, index, "inference", counters)
            if scenario == "interruption" and shard_index == index == 1:
                counters["interruption_injected"] = True
                return counters  # Persisted inference, no grading reply yet.
            _request(ledger, lineage, scenario, index, "grading", counters)
        _preview_next(ledger, scenario, shard_index)
    except usd.PilotUsdRefused:
        _require(ledger.snapshot()["stop_reason"] is not None)
    return counters


def run_shard(workspace, output, *, lineage, shard_index, predecessor=None, expected_sha256=None):
    """Only fake work; live callers have no entry point in this module."""
    workspace, output = Path(workspace), Path(output)
    checked_lineage(lineage)
    _require(type(shard_index) is int and 0 <= shard_index < 5)
    _require(not workspace.is_relative_to(output) and not output.is_relative_to(workspace))
    _require(not os.path.lexists(output), "handoff_destination_not_fresh")
    if shard_index == 0:
        _require(predecessor is None and expected_sha256 is None, "handoff_first_shard_refused")
        _new_directory(workspace)
        for scenario in SCENARIOS:
            _new_directory(workspace / scenario)
        history = []
    else:
        previous = _restore(workspace, lineage, predecessor, expected_sha256, shard_index)
        history = previous["history"]
    scenarios, current = {}, {}
    for scenario in SCENARIOS:
        ledger = _ledger(workspace / scenario, lineage, scenario, create=shard_index == 0)
        try:
            counters = _run_scenario(ledger, lineage, scenario, shard_index)
            snapshot, binding = ledger.snapshot(), ledger.binding()
            _require(snapshot["pending_requests"] == 0, "handoff_pending_reservation")
            current[scenario] = {**counters, "snapshot": snapshot,
                                 "next_worker_allowed": snapshot["stop_reason"] is None and shard_index < 4}
            scenarios[scenario] = {"binding": binding, "snapshot": snapshot, "files": {}}
        finally:
            ledger.close()
    _new_directory(output)
    for scenario in SCENARIOS:
        for role in (usd.IDENTITY, usd.DATABASE):
            data = _read(workspace / scenario / usd.DIRECTORY / role,
                         MAX_DB if role == usd.DATABASE else MAX_JSON)
            scenarios[scenario]["files"][role] = {"sha256": _sha(data), "size": len(data)}
            _write(output / f"{scenario}-{role}", data)
    producer_runner = host.receipt("diagnostic")
    result = {"schema": SCHEMA, "mode": "model-free", "lineage": lineage,
              "implementation": implementation_hashes(), "shard_index": shard_index,
              "previous_sha256": expected_sha256, "task_ids": list(TASKS),
              "scenarios": scenarios,
              "history": [*history, {"shard_index": shard_index, "scenarios": current, "runner": producer_runner}],
              "producer_runner": producer_runner,
              "model_calls": 0, "judge_calls": 0, "paid_execution_allowed": False,
              "evidence_boundary": "synthetic_ledger_transfer_not_live_pilot_or_billing"}
    raw = _json(result)
    _require(len(raw) <= MAX_JSON)
    _write(output / MANIFEST, raw)  # Ready-last; a partial export cannot resume.
    directory_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return result, _sha(raw)


def verify_completed_handoff(directory, expected_sha256, *, lineage, workspace):
    value = _restore(Path(workspace), lineage, directory, expected_sha256, 5)
    expected_amounts = {"continuity": "25", "ceiling": "196", "interruption": "25"}
    for scenario in SCENARIOS:
        rows = [item["scenarios"][scenario] for item in value["history"]]
        amounts = [Decimal(row["snapshot"]["combined_modeled_usd"]) for row in rows]
        _require(amounts == sorted(amounts))
        _require(len({row["snapshot"]["ledger_id"] for row in rows}) == 1)
        snapshot = value["scenarios"][scenario]["snapshot"]
        _same(snapshot["combined_modeled_usd"], expected_amounts[scenario])
        ledger = _ledger(Path(workspace) / scenario, lineage, scenario)
        try:
            count = ledger.connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            _same(count, 8 if scenario == "ceiling" else 10)
        finally:
            ledger.close()
    ceiling = value["history"]
    _same(ceiling[3]["scenarios"]["ceiling"]["snapshot"]["stop_reason"], usd.CEILING)
    _same(ceiling[3]["scenarios"]["ceiling"]["next_worker_allowed"], False)
    _same(ceiling[4]["scenarios"]["ceiling"]["worker_started"], False)
    _same(ceiling[4]["scenarios"]["ceiling"]["synthetic_requests"], 0)
    _same(value["history"][1]["scenarios"]["interruption"]["interruption_injected"], True)
    _require(value["history"][2]["scenarios"]["interruption"]["replayed_settlements"] >= 3)
    return {"schema": "pilot-ledger-handoff-proof-v1", "lineage": lineage,
            "continuity_passed": True, "next_shard_ceiling_refusal_passed": True,
            "interrupted_settlement_no_double_charge_passed": True,
            "synthetic_combined_usd": expected_amounts, "task_count": 5,
            "model_calls": 0, "judge_calls": 0, "paid_execution_allowed": False,
            "actual_billing_hard_limit_verified": False}


@contextmanager
def no_external_effects():
    def refused(*args, **kwargs):
        raise HandoffRefused("model_free_external_effect_refused")
    slots = ((socket.socket, "connect"), (socket, "create_connection"), (subprocess, "Popen"))
    originals = [(owner, name, getattr(owner, name)) for owner, name in slots]
    try:
        for owner, name, _ in originals:
            setattr(owner, name, refused)
        yield
    finally:
        for owner, name, original in originals:
            setattr(owner, name, original)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "pilot_ledger_handoff_configuration_refused\n")


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("action", choices=("run-shard", "verify"))
    parser.add_argument("--mode", choices=("model-free",), required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, choices=range(5))
    parser.add_argument("--predecessor", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    try:
        with no_external_effects():
            observed = host.require_execution()
            _require(observed["github_hosted"] and observed["os_version_id"] == "24.04",
                     "handoff_runner_refused")
            lineage = checked_lineage({key: os.environ.get(env) for key, env in (
                ("repository", "GITHUB_REPOSITORY"), ("run_id", "GITHUB_RUN_ID"),
                ("run_attempt", "GITHUB_RUN_ATTEMPT"), ("source_sha", "GITHUB_SHA"))})
            if args.action == "verify":
                _require(args.shard_index is None)
                proof = verify_completed_handoff(args.predecessor, args.expected_sha256,
                                                  lineage=lineage, workspace=args.workspace)
                _write(args.output, _json(proof))
                print(json.dumps(proof, sort_keys=True))
                return 0
            result, digest = run_shard(args.workspace, args.output, lineage=lineage,
                shard_index=args.shard_index, predecessor=args.predecessor,
                expected_sha256=args.expected_sha256)
            # Only a nonsecret hash crosses the job-output boundary.
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                    stream.write(f"manifest_sha256={digest}\n")
            print(json.dumps({"manifest_sha256": digest, "shard_index": args.shard_index,
                              "model_calls": 0, "judge_calls": 0,
                              "scenarios": result["history"][-1]["scenarios"]}, sort_keys=True))
            # Exercise an actual worker exit after a durable partial settlement.
            # The workflow requires exactly this exit, then uploads its artifact.
            return EXPECTED_INTERRUPT_EXIT if args.shard_index == 1 else 0
    except Exception as error:
        reason = error.code if isinstance(error, (HandoffRefused, usd.PilotUsdRefused,
                                                   host.ExecutionEnvironmentRefused)) else "pilot_ledger_handoff_refused"
        print(json.dumps({"status": "refused", "reason": reason,
                          "model_calls": 0, "judge_calls": 0, "paid_execution_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
