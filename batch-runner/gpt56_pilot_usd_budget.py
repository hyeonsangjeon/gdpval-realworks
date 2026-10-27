"""One durable *modelled* USD budget for the five-task pilot, not a billing API.

The immutable owner decision is read, never rewritten. SQLite serializes both
origins before egress; a lost reply consumes its reservation and closes further
admission. Reopening money records grants no inference-session or study right.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import threading
import uuid
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

from gpt54_v2_grading_input import _read_bytes

RUN_ID = "gpt56_sol_foundry_codex_pilot5_v1"
DIRECTORY = ".pilot-usd-budget"
DATABASE = "ledger.sqlite3"
IDENTITY = "identity.json"
CAP_SHA256 = "df64cdb0d1e1f242b7500debbca2ca5dac0eab988783e2a03da80c57a940992f"
PRICE_SHA256 = "b01b384c532b1457804e3a77713d2b079b06b363a5ff3b8b939fe65a4cb30b4e"
_ENVELOPE = Path(__file__).resolve().parent / "experiments/execution_envelope"
CAP_PATH = _ENVELOPE / "gpt56_sol_native_usd_cap_20261027.yaml"
PRICE_PATH = _ENVELOPE / "model_price_table.json"
CEILING = "usd_ceiling_exceeded"
UNKNOWN = "usd_usage_unverified"
OVERRUN = "usd_reservation_exceeded"
UNPRICED = "usd_price_contract_unverified"
UNVERIFIED = "usd_ledger_unverified"
STOPS = frozenset({CEILING, UNKNOWN, OVERRUN, UNPRICED, UNVERIFIED})
ORIGINS = frozenset({"inference", "grading"})


class PilotUsdRefused(ValueError):
    def __init__(self, code=UNVERIFIED, source="grading"):
        self.code = code if code in STOPS else UNVERIFIED
        self.source = source if source in ORIGINS else "grading"
        super().__init__(self.code)


def _require(value, code=UNVERIFIED, source="grading"):
    if not value:
        raise PilotUsdRefused(code, source)


def _money(value):
    _require(type(value) in (str, int, Decimal) and not isinstance(value, bool))
    text = str(value)
    _require(len(text) <= 64 and re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", text) is not None)
    try:
        result = Decimal(text)
    except InvalidOperation:
        raise PilotUsdRefused() from None
    _require(result.is_finite() and 0 <= result < Decimal("1e24"))
    return result


def _text(value):
    return format(_money(value), "f")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def price_document():
    _read_bytes(CAP_PATH, sha256=CAP_SHA256)
    raw = _read_bytes(PRICE_PATH, sha256=PRICE_SHA256)
    return json.loads(raw, object_pairs_hook=_unique)


def _process_start(pid):
    """Only process metadata for this ledger's owners; never command/env data."""
    try:
        data = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        fields = data.rsplit(")", 1)[1].split()
        return None if fields[0] in {"Z", "X"} else fields[19]
    except (OSError, ValueError, IndexError):
        return None


def _regular(path):
    metadata = path.lstat()
    _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1)
    return metadata.st_dev, metadata.st_ino


class PilotUsdLedger:
    """Local-file admission; durable unknown consumption, never receipt adoption."""

    def __init__(self, workspace, *, capture_sha256, task_ids, create=False):
        price_document()
        _require(type(capture_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", capture_sha256))
        _require(type(task_ids) is list and len(task_ids) == len(set(task_ids)) == 5
                 and all(type(value) is str and 0 < len(value) <= 128 for value in task_ids))
        self.workspace = Path(os.path.abspath(workspace))
        for parent in (self.workspace, *self.workspace.parents):
            _require(stat.S_ISDIR(parent.lstat().st_mode))
        self.directory = self.workspace / DIRECTORY
        self.path = self.directory / DATABASE
        self.identity_path = self.directory / IDENTITY
        self.lock = threading.RLock()
        self.closed = False
        self.pid, self.process_start = os.getpid(), _process_start(os.getpid())
        self.owner_id = uuid.uuid4().hex
        _require(self.process_start is not None)
        expected = {"version": "pilot-shared-usd-v1", "run_id": RUN_ID,
                    "cap_record_sha256": CAP_SHA256, "price_table_sha256": PRICE_SHA256,
                    "approved_maximum_usd": "1000", "currency": "USD",
                    "capture_sha256": capture_sha256, "task_ids": task_ids}
        fresh = False
        if not os.path.lexists(self.directory):
            _require(create)
            os.mkdir(self.directory, 0o700)
            fresh = True
        directory_stat = self.directory.lstat()
        _require(stat.S_ISDIR(directory_stat.st_mode) and not directory_stat.st_mode & 0o022)
        self.directory_identity = (directory_stat.st_dev, directory_stat.st_ino)
        if fresh:
            self.identity = {**expected, "ledger_id": uuid.uuid4().hex}
            fd = os.open(self.identity_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(_json(self.identity))
                stream.flush()
                os.fsync(stream.fileno())
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        else:
            _regular(self.identity_path)
            self.identity = json.loads(_read_bytes(self.identity_path), object_pairs_hook=_unique)
        _require(type(self.identity) is dict and set(self.identity) == {*expected, "ledger_id"}
                 and all(self.identity[key] == value for key, value in expected.items())
                 and re.fullmatch(r"[0-9a-f]{32}", self.identity["ledger_id"]) is not None)
        self.identity_bytes = _json(self.identity)
        self.file_identity = _regular(self.path)
        self.identity_file_identity = _regular(self.identity_path)
        self._check_files()
        try:
            self.connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                              timeout=5, isolation_level=None, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA journal_mode=DELETE")
            self.connection.execute("PRAGMA synchronous=FULL")
            if fresh:
                self.connection.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), identity BLOB NOT NULL,
                        reason TEXT, origin TEXT, blocked_inference INTEGER NOT NULL DEFAULT 0,
                        blocked_grading INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE accounts (id TEXT PRIMARY KEY, origin TEXT NOT NULL, task TEXT NOT NULL,
                        io TEXT NOT NULL DEFAULT '0', cache TEXT NOT NULL DEFAULT '0');
                    CREATE TABLE reservations (id TEXT PRIMARY KEY, account TEXT NOT NULL,
                        amount TEXT NOT NULL, baseline TEXT NOT NULL, state TEXT NOT NULL,
                        pid INTEGER NOT NULL, process_start TEXT NOT NULL, owner_id TEXT NOT NULL,
                        settled_io TEXT, settled_cache TEXT);
                    COMMIT;
                """)
                self.connection.execute("INSERT INTO meta(id,identity) VALUES(1,?)", (self.identity_bytes,))
                directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            with self._transaction():
                pass
        except Exception:
            if hasattr(self, "connection"):
                self.connection.close()
            raise PilotUsdRefused() from None

    def _check_files(self):
        _require(not self.closed)
        metadata = self.directory.lstat()
        _require(stat.S_ISDIR(metadata.st_mode) and (metadata.st_dev, metadata.st_ino) == self.directory_identity)
        _require(_regular(self.path) == self.file_identity
                 and _regular(self.identity_path) == self.identity_file_identity
                 and _read_bytes(self.identity_path) == self.identity_bytes)
        for suffix in ("-journal", "-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if os.path.lexists(sidecar):
                _require(suffix == "-journal")
                try:
                    _regular(sidecar)
                except FileNotFoundError:
                    pass  # Another committed writer legitimately removed its journal.

    @contextmanager
    def _transaction(self):
        with self.lock:
            try:
                self._check_files()
                self.connection.execute("BEGIN IMMEDIATE")
                row = self.connection.execute("SELECT * FROM meta WHERE id=1").fetchone()
                _require(row is not None and row["identity"] == self.identity_bytes
                         and row["reason"] in STOPS | {None} and row["origin"] in ORIGINS | {None})
                self._recover()
                yield
                self.connection.execute("COMMIT")
                self._check_files()
            except BaseException as error:
                if self.connection.in_transaction:
                    self.connection.execute("ROLLBACK")
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                raise PilotUsdRefused(getattr(error, "code", UNVERIFIED),
                                      getattr(error, "source", "grading")) from None

    def _stop(self, reason, origin):
        _require(reason in STOPS and origin in ORIGINS)
        self.connection.execute("UPDATE meta SET reason=COALESCE(reason,?), origin=COALESCE(origin,?) WHERE id=1",
                                (reason, origin))

    def _recover(self):
        pending = self.connection.execute("SELECT r.*, a.origin FROM reservations r JOIN accounts a ON a.id=r.account WHERE state='reserved'").fetchall()
        alive = {}
        for row in pending:
            owner = row["pid"], row["process_start"]
            if owner not in alive:
                alive[owner] = _process_start(owner[0]) == owner[1]
            if not alive[owner]:
                self.connection.execute("UPDATE reservations SET state='unknown' WHERE id=?", (row["id"],))
                self._stop(UNKNOWN, row["origin"])

    def _account(self, account):
        row = self.connection.execute("SELECT * FROM accounts WHERE id=?", (account,)).fetchone()
        _require(row is not None and row["origin"] in ORIGINS and row["task"] in self.identity["task_ids"])
        _money(row["io"])
        _money(row["cache"])
        return row

    def _totals(self):
        accounts = self.connection.execute("SELECT * FROM accounts").fetchall()
        _require(len(accounts) <= 100000)
        known = {origin: Decimal(0) for origin in ORIGINS}
        values = {}
        for row in accounts:
            _require(row["origin"] in ORIGINS and row["task"] in self.identity["task_ids"])
            amount = _money(row["io"]) + _money(row["cache"])
            known[row["origin"]] += amount
            values[row["id"]] = amount
        pending = unknown = Decimal(0)
        pending_count = unknown_count = 0
        for row in self.connection.execute("SELECT * FROM reservations WHERE state != 'settled'"):
            _require(row["state"] in {"reserved", "unknown"} and row["account"] in values)
            remainder = max(Decimal(0), _money(row["amount"]) - max(Decimal(0), values[row["account"]] - _money(row["baseline"])))
            if row["state"] == "unknown":
                unknown += remainder
                unknown_count += 1
            else:
                pending += remainder
                pending_count += 1
        return known, pending, unknown, pending_count, unknown_count

    def begin(self, origin, task_id):
        _require(origin in ORIGINS and task_id in self.identity["task_ids"])
        account = uuid.uuid4().hex
        with self._transaction():
            self.connection.execute("INSERT INTO accounts(id,origin,task) VALUES(?,?,?)", (account, origin, task_id))
        return account

    def refuse(self, code, origin):
        with self._transaction():
            self._stop(code, origin)

    def reserve(self, account, amount, *, request_id=None):
        amount = _money(amount)
        reservation = request_id if request_id is not None else uuid.uuid4().hex
        _require(type(reservation) is str and re.fullmatch(r"[0-9a-f]{32}", reservation))
        reason = None
        with self._transaction():
            row = self._account(account)
            reason = self.connection.execute("SELECT reason FROM meta WHERE id=1").fetchone()[0]
            if reason is None and (self.connection.execute("SELECT 1 FROM reservations WHERE id=? OR (account=? AND state != 'settled')", (reservation, account)).fetchone()):
                reason = UNVERIFIED
            known, pending, unknown, _, _ = self._totals()
            if reason is None and sum(known.values()) + pending + unknown + amount > Decimal(1000):
                reason = CEILING
            if reason is not None:
                self._stop(reason, row["origin"])
                column = "blocked_" + row["origin"]
                self.connection.execute(f"UPDATE meta SET {column}={column}+1 WHERE id=1")
            else:
                self.connection.execute("INSERT INTO reservations(id,account,amount,baseline,state,pid,process_start,owner_id) VALUES(?,?,?,?,'reserved',?,?,?)",
                                        (reservation, account, _text(amount), _text(_money(row["io"]) + _money(row["cache"])), self.pid, self.process_start, self.owner_id))
        if reason is not None:
            raise PilotUsdRefused(reason, row["origin"])
        return reservation

    def observe(self, account, io, cache):
        io, cache = _money(io), _money(cache)
        with self._transaction():
            row = self._account(account)
            _require(io >= _money(row["io"]) and cache >= _money(row["cache"]))
            self.connection.execute("UPDATE accounts SET io=?,cache=? WHERE id=?", (_text(io), _text(cache), account))
            known, pending, unknown, _, _ = self._totals()
            if sum(known.values()) + pending + unknown > Decimal(1000):
                self._stop(CEILING, row["origin"])
            reason = self.connection.execute("SELECT reason FROM meta WHERE id=1").fetchone()[0]
        return reason

    def settle(self, reservation, io, cache):
        io, cache = _money(io), _money(cache)
        with self._transaction():
            entry = self.connection.execute("SELECT * FROM reservations WHERE id=?", (reservation,)).fetchone()
            _require(entry is not None)
            row = self._account(entry["account"])
            if entry["state"] == "settled":
                if _money(entry["settled_io"]) != io or _money(entry["settled_cache"]) != cache:
                    self._stop(UNKNOWN, row["origin"])
            elif entry["state"] != "reserved" or io < _money(row["io"]) or cache < _money(row["cache"]):
                self.connection.execute("UPDATE reservations SET state='unknown' WHERE id=? AND state='reserved'", (reservation,))
                self._stop(UNKNOWN, row["origin"])
            else:
                self.connection.execute("UPDATE accounts SET io=?,cache=? WHERE id=?", (_text(io), _text(cache), row["id"]))
                self.connection.execute("UPDATE reservations SET state='settled',settled_io=?,settled_cache=? WHERE id=?", (_text(io), _text(cache), reservation))
                if io + cache - _money(entry["baseline"]) > _money(entry["amount"]):
                    self._stop(OVERRUN, row["origin"])
                known, pending, unknown, _, _ = self._totals()
                if sum(known.values()) + pending + unknown > Decimal(1000):
                    self._stop(CEILING, row["origin"])
            reason = self.connection.execute("SELECT reason FROM meta WHERE id=1").fetchone()[0]
        return reason

    def abandon(self, account):
        with self._transaction():
            row = self._account(account)
            changed = self.connection.execute("UPDATE reservations SET state='unknown' WHERE account=? AND state='reserved'", (account,)).rowcount
            if changed:
                self._stop(UNKNOWN, row["origin"])

    def snapshot(self):
        with self._transaction():
            known, pending, unknown, pending_count, unknown_count = self._totals()
            meta = self.connection.execute("SELECT * FROM meta WHERE id=1").fetchone()
            total = sum(known.values()) + pending + unknown
            native = self.connection.execute("SELECT io,cache FROM accounts WHERE origin='inference'").fetchall()
            return {"schema": "pilot-shared-usd-v1", "ledger_id": self.identity["ledger_id"],
                    "run_id": RUN_ID, "cap_record_sha256": CAP_SHA256, "price_table_sha256": PRICE_SHA256,
                    "approved_maximum_usd": "1000", "currency": "USD", "persistent": True,
                    "inference_known_usd": _text(known["inference"]), "grading_known_usd": _text(known["grading"]),
                    "inference_input_output_usd": _text(sum((_money(row["io"]) for row in native), Decimal(0))),
                    "inference_cache_reserve_usd": _text(sum((_money(row["cache"]) for row in native), Decimal(0))),
                    "pending_usd": _text(pending), "unknown_consumed_usd": _text(unknown),
                    "combined_modeled_usd": _text(total), "remaining_modeled_usd": _text(max(Decimal(0), Decimal(1000) - total)),
                    "pending_requests": pending_count, "unknown_requests": unknown_count,
                    "blocked_inference": meta["blocked_inference"], "blocked_grading": meta["blocked_grading"],
                    "stop_reason": meta["reason"], "stop_source": meta["origin"],
                    "grading_admission_connected": True, "actual_billing_hard_limit_verified": False}

    def binding(self):
        with self._transaction():
            return json.loads(self.identity_bytes)

    def close(self):
        with self.lock:
            if not self.closed:
                try:
                    with self._transaction():
                        for row in self.connection.execute("SELECT r.id,a.origin FROM reservations r JOIN accounts a ON a.id=r.account WHERE state='reserved' AND owner_id=?", (self.owner_id,)).fetchall():
                            self.connection.execute("UPDATE reservations SET state='unknown' WHERE id=?", (row["id"],))
                            self._stop(UNKNOWN, row["origin"])
                finally:
                    self.connection.close()
                    self.closed = True


def checked_snapshot(raw):
    fixed = {"schema": "pilot-shared-usd-v1", "run_id": RUN_ID,
             "cap_record_sha256": CAP_SHA256, "price_table_sha256": PRICE_SHA256,
             "approved_maximum_usd": "1000", "currency": "USD", "persistent": True,
             "grading_admission_connected": True, "actual_billing_hard_limit_verified": False}
    amounts = {"inference_known_usd", "grading_known_usd", "inference_input_output_usd",
               "inference_cache_reserve_usd", "pending_usd", "unknown_consumed_usd",
               "combined_modeled_usd", "remaining_modeled_usd"}
    counts = {"pending_requests", "unknown_requests", "blocked_inference", "blocked_grading"}
    if type(raw) is not dict or set(raw) != set(fixed) | amounts | counts | {"ledger_id", "stop_reason", "stop_source"}:
        return False
    if any(type(raw[key]) is not type(value) or raw[key] != value for key, value in fixed.items()):
        return False
    if type(raw["ledger_id"]) is not str or re.fullmatch(r"[0-9a-f]{32}", raw["ledger_id"]) is None:
        return False
    if any(type(raw[key]) is not int or not 0 <= raw[key] < 2 ** 63 for key in counts):
        return False
    if (type(raw["stop_reason"]) not in (str, type(None)) or type(raw["stop_source"]) not in (str, type(None))
            or raw["stop_reason"] not in STOPS | {None} or raw["stop_source"] not in ORIGINS | {None}):
        return False
    if (raw["stop_reason"] is None) != (raw["stop_source"] is None):
        return False
    try:
        if any(type(raw[key]) is not str for key in amounts):
            return False
        values = {key: _money(raw[key]) for key in amounts}
    except PilotUsdRefused:
        return False
    total = sum(values[key] for key in ("inference_known_usd", "grading_known_usd", "pending_usd", "unknown_consumed_usd"))
    return (values["inference_known_usd"] == values["inference_input_output_usd"] + values["inference_cache_reserve_usd"]
            and values["combined_modeled_usd"] == total
            and values["remaining_modeled_usd"] == max(Decimal(0), Decimal(1000) - total)
            and (raw["stop_reason"] is not None or total <= Decimal(1000))
            and (raw["unknown_requests"] == 0 or raw["stop_reason"] is not None)
            and (raw["pending_requests"] != 0 or values["pending_usd"] == 0)
            and (raw["unknown_requests"] != 0 or values["unknown_consumed_usd"] == 0))


def grading_prices(config):
    """An exact, settled pricing contract, never the native reference scenario."""
    document = price_document()
    judge = config.get("judge", {})
    _require(judge.get("provider") == "azure_openai", UNPRICED)
    slots = [judge, *judge.get("perception", {}).values()]
    prices = {}
    for slot in slots:
        _require(type(slot) is dict, UNPRICED)
        model = slot.get("model")
        _require(type(model) is str and model and slot.get("deployment", model) == model, UNPRICED)
        key = "azure:" + model
        _require(key not in document.get("models_deliberately_not_priced", {}), UNPRICED)
        entry = document.get("providers", {}).get(key)
        _require(type(entry) is dict and entry.get("currency") == "USD"
                 and entry.get("unit") == "per 1,000,000 tokens"
                 and entry.get("reasoning_billed_as") == "output"
                 and entry.get("source") and entry.get("last_reviewed")
                 and not entry.get("premises") and not entry.get("assumptions")
                 and not document.get("pricing_axes", {}).get("axes_open"), UNPRICED)
        write_kind = entry.get("cache_write_billed_as")
        _require(write_kind in {"none", "input_tokens"}, UNPRICED)
        try:
            rates = {"input": _money(entry["input_usd_per_million"]),
                     "output": _money(entry["output_usd_per_million"]),
                     "cache_write": _money(entry["cache_write_usd_per_million"])}
            _require((write_kind == "none") == (rates["cache_write"] == 0), UNPRICED)
            _require(_money(entry["cached_input_usd_per_million"]) <= rates["input"], UNPRICED)
        except (KeyError, PilotUsdRefused):
            raise PilotUsdRefused(UNPRICED) from None
        prices[model] = rates
    _require(bool(prices), UNPRICED)
    return prices


def _value(container, name):
    return container.get(name) if isinstance(container, dict) else getattr(container, name, None)


def _count(container, *names):
    values = [_value(container, name) for name in names if _value(container, name) is not None]
    _require(values and all(type(value) is int and 0 <= value < 2 ** 63 for value in values)
             and len(set(values)) == 1, UNKNOWN)
    return values[0]


def _request_allowance(kwargs):
    """Restricted visible-text client bound; not a model/server token theorem."""
    _require(type(kwargs) is dict and not kwargs.get("stream"), UNKNOWN)
    limits = [kwargs[key] for key in ("max_output_tokens", "max_completion_tokens", "max_tokens") if key in kwargs]
    _require(len(limits) == 1 and type(limits[0]) is int and 0 < limits[0] < 2 ** 31, UNKNOWN)
    opaque = {"previous_response_id", "conversation", "image_url", "input_image", "image", "input_audio",
              "audio", "file_id", "file_data", "input_file", "encrypted_content", "service_tier"}

    def visit(value):
        if type(value) is dict:
            _require(not (set(value) & opaque), UNKNOWN)
            if "type" in value:
                _require(value["type"] in {"message", "input_text", "text", "output_text", "function",
                                            "function_call", "function_call_output", "object", "array",
                                            "string", "number", "integer", "boolean", "null"}, UNKNOWN)
            for item in value.values():
                visit(item)
        elif type(value) in (list, tuple):
            for item in value:
                visit(item)
        else:
            _require(type(value) in (str, int, float, bool, type(None)), UNKNOWN)

    visit(kwargs)
    try:
        raw = json.dumps(kwargs, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise PilotUsdRefused(UNKNOWN) from None
    _require(len(raw) <= 1024 * 1024, UNKNOWN)
    return len(raw), limits[0]


class GradingUsdAdmission:
    """Passed into the existing CostRecorder, including perception/retry wrappers."""

    def __init__(self, ledger, config):
        _require(type(ledger) is PilotUsdLedger)
        self.ledger = ledger
        self.config = json.loads(_json(config))
        self.prices = grading_prices(self.config)

    def check_client(self, client):
        # A wrapper around create() cannot settle invisible SDK retries. Do not
        # change the frozen transport policy or pretend one reply covers them.
        if type(getattr(client, "max_retries", None)) is not int or client.max_retries != 0:
            self.ledger.refuse(UNKNOWN, "grading")
            raise PilotUsdRefused(UNKNOWN)

    def reserve(self, *, task_id, provider, kwargs):
        try:
            _require(provider == "azure" and grading_prices(self.config) == self.prices, UNPRICED)
            model = kwargs.get("model")
            _require(model in self.prices, UNPRICED)
            inputs, outputs = _request_allowance(kwargs)
            rates = self.prices[model]
            amount = (Decimal(inputs) * (rates["input"] + rates["cache_write"])
                      + Decimal(outputs) * rates["output"]) / Decimal(1_000_000)
            account = self.ledger.begin("grading", task_id)
            reservation = self.ledger.reserve(account, amount)
            return {"account": account, "reservation": reservation, "model": model, "rates": rates}
        except PilotUsdRefused as error:
            self.ledger.refuse(error.code, "grading")
            raise

    def finish(self, ticket, response):
        try:
            _require(_value(response, "model") == ticket["model"], UNKNOWN)
            status = _value(response, "status")
            if status is None:
                choices = _value(response, "choices")
                _require(type(choices) is list and choices and all(_value(choice, "finish_reason") in {"stop", "tool_calls"} for choice in choices), UNKNOWN)
            else:
                _require(status == "completed", UNKNOWN)
            usage = _value(response, "usage")
            inputs = _count(usage, "input_tokens", "prompt_tokens")
            outputs = _count(usage, "output_tokens", "completion_tokens")
            for name in ("input_tokens_details", "prompt_tokens_details"):
                detail = _value(usage, name)
                if _value(detail, "cached_tokens") is not None:
                    _require(_count(detail, "cached_tokens") <= inputs, UNKNOWN)
                _require(_value(detail, "audio_tokens") in (None, 0), UNKNOWN)
            rates = ticket["rates"]
            writes = _count(usage, "cache_write_input_tokens", "cache_creation_input_tokens") if rates["cache_write"] else 0
            io = (Decimal(inputs) * rates["input"] + Decimal(outputs) * rates["output"]) / Decimal(1_000_000)
            cache = Decimal(writes) * rates["cache_write"] / Decimal(1_000_000)
            reason = self.ledger.settle(ticket["reservation"], io, cache)
        except BaseException:
            self.ledger.abandon(ticket["account"])
            raise PilotUsdRefused(UNKNOWN) from None
        if reason is not None:
            raise PilotUsdRefused(reason)

    def abandon(self, ticket):
        self.ledger.abandon(ticket["account"])

    def unattributed(self):
        self.ledger.refuse(UNKNOWN, "grading")
        raise PilotUsdRefused(UNKNOWN)


def is_pilot_grading(*, experiment_id=None, config=None, inference=None, workspace=None):
    config = config or {}
    inference = inference or {}
    return (experiment_id == RUN_ID or config.get("config_name") == RUN_ID + "_v2_sol_max"
            or inference.get("experiment_id") == RUN_ID or inference.get("run_id") == RUN_ID
            or "pilot_wire_receipts" in inference
            or workspace is not None)


def open_grading_admission(*, workspace, inference, task_ids, config):
    """Reopen the inference-bound financial file, not its live wire witness."""
    grading_prices(config)  # No guess, no client construction, no fresh ledger.
    _require(config.get("config_name") == RUN_ID + "_v2_sol_max"
             and inference.get("experiment_id") == RUN_ID)
    _require(workspace is not None)
    root = Path(os.path.abspath(workspace))
    linkage = inference.get("pilot_wire_receipts")
    _require(type(linkage) is dict and linkage.get("path") == "pilot-wire-receipts/pilot-wire-receipts-ready.json")
    raw = _read_bytes(root / linkage["path"], size=linkage["size"], sha256=linkage["sha256"])
    ready = json.loads(raw, object_pairs_hook=_unique)
    _require(ready.get("run_id") == RUN_ID and ready.get("task_ids") == task_ids)
    binding = ready.get("shared_usd_budget")
    _require(type(binding) is dict and binding.get("task_ids") == task_ids)
    ledger = PilotUsdLedger(root, capture_sha256=binding["capture_sha256"], task_ids=task_ids)
    try:
        _require(ledger.binding() == binding)
        snapshot = ledger.snapshot()
        _require(snapshot["stop_reason"] is None and snapshot["pending_requests"] == 0
                 and snapshot["unknown_requests"] == 0, snapshot["stop_reason"] or UNKNOWN)
        return GradingUsdAdmission(ledger, config)
    except BaseException:
        ledger.close()
        raise
