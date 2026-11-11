"""A controller-side SOFT stop, not a GitHub billing or provider hard limit.

No default budget, account access, runtime launch or price discovery. The pinned
Codex mapper reports the last call plus turn-cumulative totals. Repeated totals
are not another call; gaps are not priced at an invented average context tier.
Cache-write counts are optional in AHP: reserve a possible write surcharge on
ALL input tokens when absent, explicitly recording null rather than zero.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import threading

from ghcp_ahp_probe import DESIRED_MODEL, Refused

SCHEMA = "ghcp-ahp-token-ledger-v1"
PRICE_SOURCE = "https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing"
TARIFF = {"date": "2026-11-11", "model": "gpt-5.6-sol", "threshold_input_tokens": 272000,
          "unit": "AI credits per 1000000 tokens", "usd_per_credit": "0.01",
          "default": {"input": 400, "cache_read": 40, "cache_write": 500, "output": 2000},
          "long_context": {"input": 800, "cache_read": 80, "cache_write": 1000, "output": 3000},
          "source": PRICE_SOURCE}
MICRO = 1_000_000
MAX_TOKENS = 2**53 - 1
MAX_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 4096


def require(value, reason):
    if not value:
        raise Refused(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode()


def credits(micro):
    whole, fraction = divmod(micro, MICRO)
    return str(whole) + (("." + f"{fraction:06d}".rstrip("0")) if fraction else "")


def _cap(value):
    require(type(value) in {str, int} and re.fullmatch(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,6})?", str(value)),
            "token_budget_invalid")
    whole, separator, fraction = str(value).partition(".")
    amount = int(whole) * MICRO + (int(fraction.ljust(6, "0")) if separator else 0)
    require(amount > 0, "token_budget_invalid")
    return amount


@dataclass(frozen=True)
class Budget:
    task_microcredits: int
    five_task_microcredits: int
    usage_timeout_seconds: int

    @classmethod
    def parse(cls, value):
        require(value is not None, "token_budget_required")
        require(type(value) is dict and set(value) == {"task_credits", "five_task_credits", "usage_timeout_seconds"},
                "token_budget_invalid")
        timeout = value["usage_timeout_seconds"]
        require(type(timeout) is int and 1 <= timeout <= 1200, "token_budget_invalid")
        return cls(_cap(value["task_credits"]), _cap(value["five_task_credits"]), timeout)

    def record(self):
        return {"task_credits": credits(self.task_microcredits), "five_task_credits": credits(self.five_task_microcredits),
                "usage_timeout_seconds": self.usage_timeout_seconds}


def _tokens(value):
    require(type(value) is int and 0 <= value <= MAX_TOKENS, "token_ledger_invalid_usage")
    return value


def price_usage(usage, previous=None):
    """Return a deduplicated conservative estimate; never infer a missing count."""
    require(type(usage) is dict and usage.get("model") == DESIRED_MODEL["id"], "token_ledger_invalid_usage")
    current = {key: _tokens(usage.get(key)) for key in ("inputTokens", "outputTokens", "cacheReadTokens")}
    require(current["cacheReadTokens"] <= current["inputTokens"], "token_ledger_invalid_usage")
    meta = usage.get("_meta")
    require(type(meta) is dict, "token_ledger_usage_totals_missing")
    totals = meta.get("turnTokenTotals")
    require(type(totals) is list and len(totals) == 1 and type(totals[0]) is dict
            and totals[0].get("model") == DESIRED_MODEL["id"], "token_ledger_usage_totals_missing")
    cumulative = {key: _tokens(totals[0].get(source)) for key, source in
                  (("inputTokens", "inputTokens"), ("outputTokens", "outputTokens"), ("cacheReadTokens", "cachedTokens"))}
    require(cumulative["cacheReadTokens"] <= cumulative["inputTokens"], "token_ledger_invalid_usage")
    if "directTurnTokenTotals" in meta:
        require(meta["directTurnTokenTotals"] == totals, "token_ledger_usage_scope_refused")
    if "reasoningOutputTokens" in meta:
        require(_tokens(meta["reasoningOutputTokens"]) <= current["outputTokens"], "token_ledger_invalid_usage")
    # Do not silently interpret an unknown cache-write field/shape as a zero.
    write = None
    if "cacheWriteTokens" in usage:
        write = _tokens(usage["cacheWriteTokens"])
        require(write <= current["inputTokens"], "token_ledger_invalid_usage")
    last = {**current, "cacheWriteTokens": write}
    baseline = previous["cumulative"] if previous else dict.fromkeys(current, 0)
    delta = {key: cumulative[key] - baseline[key] for key in current}
    require(all(value >= 0 for value in delta.values()), "token_ledger_usage_regressed")
    duplicate = not any(delta.values())
    if duplicate:
        require((previous is not None and previous["last"] == last) or (previous is None and not any(current.values())),
                "token_ledger_ambiguous_usage")
    else:
        require(delta == current, "token_ledger_usage_gap")
    tier = "long_context" if current["inputTokens"] > TARIFF["threshold_input_tokens"] else "default"
    prices = TARIFF[tier]
    reported = ((current["inputTokens"] - current["cacheReadTokens"]) * prices["input"]
                + current["cacheReadTokens"] * prices["cache_read"] + current["outputTokens"] * prices["output"])
    reserve = (current["inputTokens"] if write is None else write) * prices["cache_write"]
    # Integer microcredits: prices are per 1M tokens, so no binary float rounding.
    charge = 0 if duplicate else reported + reserve
    return {"last": last, "cumulative": cumulative, "duplicate": duplicate, "tier": tier,
            "reported_component_microcredits": 0 if duplicate else reported,
            "cache_write_reserve_microcredits": 0 if duplicate else reserve,
            "cache_write_basis": "all_input_possible_write_surcharge" if write is None else "reported_additive_write_reserve",
            "estimated_microcredits": charge, "estimated_credits": credits(charge),
            "token_envelope_exceeded": current["inputTokens"] > 1_000_000 or current["outputTokens"] > 128000}


def verify_task_receipt(value):
    """Reprice persisted rows independently; no trusting a claimed cost total."""
    require(type(value) is dict and value.get("schema") == SCHEMA and value.get("soft_guard") is True
            and value.get("execution_allowed") is False and value.get("tariff") == TARIFF,
            "token_ledger_receipt_refused")
    budget = Budget.parse(value.get("budget"))
    rows = value.get("usage_events")
    require(type(rows) is list and len(rows) <= MAX_EVENTS, "token_ledger_receipt_refused")
    previous, seen_seq, total, seen = {}, set(), 0, False
    for row in rows:
        require(type(row) is dict and type(row.get("server_seq")) is int and row["server_seq"] >= 0
                and row["server_seq"] not in seen_seq and row.get("turn_id") in value.get("admitted_turns", []),
                "token_ledger_receipt_refused")
        seen_seq.add(row["server_seq"])
        priced = price_usage(row["usage"], previous.get(row["turn_id"]))
        require(row["pricing"] == priced, "token_ledger_receipt_refused")
        previous[row["turn_id"]] = priced
        total += priced["estimated_microcredits"]
        seen |= not priced["duplicate"]
    require(value.get("known_estimated_credits") == (credits(total) if seen else None)
            and value.get("known_estimated_microcredits") == (total if seen else None), "token_ledger_receipt_refused")
    if value.get("stopped_reason") == "completed":
        require(seen and total < budget.task_microcredits and not value.get("issues")
                and value.get("closed") is True
                and set(value.get("admitted_turns", [])) == set(value.get("completed_turns", [])),
                "token_ledger_receipt_refused")
    return value


class TokenLedger:
    """One exclusive, no-resume JSON journal shared by the five serial tasks.

    This is not a distributed budget: independent workers/ledgers must not be
    substituted for the one shared controller. A missing/malformed report makes
    the aggregate unknown and blocks subsequent tasks, not just the next turn.
    """

    def __init__(self, path, budget, task_ids, *, profile, synthetic):
        self.budget = Budget.parse(budget)
        require(type(synthetic) is bool and profile in {"choice1_job_tmpdir", "default_policy_unpatched"},
                "token_ledger_binding_refused")
        require(type(task_ids) in {list, tuple} and 1 <= len(task_ids) <= 5 and len(set(task_ids)) == len(task_ids)
                and all(type(task) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,160}", task) for task in task_ids),
                "token_ledger_binding_refused")
        self.path, self.profile, self.synthetic = Path(path), profile, synthetic
        require(self.path.is_absolute() and self.path.name == "token-ledger.json" and self.path.parent.is_dir()
                and not os.path.lexists(self.path), "token_ledger_path_refused")
        self.lock = threading.RLock()
        self.file_identity = self.file_sha = None
        self.parent_identity = self._parents()
        self.active_task, self.global_stop, self.unknown = None, None, False
        self.tasks = {task: {"admitted_turns": [], "completed_turns": [], "usage_events": [], "issues": [],
                             "stopped_reason": None, "closed": False} for task in task_ids}
        self.previous, self.progress = {}, {}
        self._persist()

    def _parents(self):
        require(not any(parent.is_symlink() for parent in (self.path, *self.path.parents)), "token_ledger_path_refused")
        info = self.path.parent.stat()
        return info.st_dev, info.st_ino

    def _check_file(self):
        require(self._parents() == self.parent_identity, "token_ledger_path_changed")
        if self.file_identity is None:
            require(not os.path.lexists(self.path), "token_ledger_path_refused")
            return
        descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                    and info.st_nlink == 1 and info.st_size <= MAX_BYTES
                    and (info.st_dev, info.st_ino) == self.file_identity, "token_ledger_file_changed")
            raw = stream.read(MAX_BYTES + 1)
        require(hashlib.sha256(raw).hexdigest() == self.file_sha, "token_ledger_file_changed")

    def _known(self, task):
        rows = self.tasks[task]["usage_events"]
        return sum(row["pricing"]["estimated_microcredits"] for row in rows) if any(not row["pricing"]["duplicate"] for row in rows) else None

    def _total(self):
        values = [self._known(task) for task in self.tasks]
        return sum(value for value in values if value is not None) if any(value is not None for value in values) else None

    def task_receipt(self, task):
        require(task in self.tasks, "token_ledger_binding_refused")
        known = self._known(task)
        return {"schema": SCHEMA, "task_id": task, "soft_guard": True, "execution_allowed": False,
                "synthetic": self.synthetic, "output_profile": self.profile, "budget": self.budget.record(),
                "tariff": copy.deepcopy(TARIFF), "known_estimated_microcredits": known,
                "known_estimated_credits": credits(known) if known is not None else None,
                "billing_complete": False, "unseen_provider_work_bound": "no_finite_bound_proven",
                **copy.deepcopy(self.tasks[task])}

    def snapshot(self):
        with self.lock:
            total = self._total()
            return {"schema": SCHEMA, "soft_guard": True, "execution_allowed": False, "synthetic": self.synthetic,
                    "budget": self.budget.record(), "output_profile": self.profile, "tariff": copy.deepcopy(TARIFF),
                    "known_estimated_credits": credits(total) if total is not None else None,
                    "unknown_usage": self.unknown, "global_stop_reason": self.global_stop,
                    "tasks": {task: self.task_receipt(task) for task in self.tasks}}

    def _persist(self):
        temporary = None
        try:
            self._check_file()
            raw = encoded(self.snapshot())
            require(len(raw) <= MAX_BYTES, "token_ledger_size_limit")
            if self.file_identity is None:
                descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            else:
                descriptor, temporary = tempfile.mkstemp(prefix=".token-ledger-", suffix=".tmp", dir=self.path.parent)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
                info = os.fstat(stream.fileno())
            if temporary is not None:
                self._check_file()
                os.replace(temporary, self.path)
                temporary = None
            self.file_identity, self.file_sha = (info.st_dev, info.st_ino), hashlib.sha256(raw).hexdigest()
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except Exception:
            self.global_stop, self.unknown = "token_ledger_persistence_refused", True
            raise Refused(self.global_stop) from None
        finally:
            if temporary is not None:
                os.unlink(temporary)  # Only the exclusive temporary file created above.

    def _clock(self, now):
        require(type(now) in {float, int} and math.isfinite(now) and now >= 0, "token_ledger_clock_refused")

    def admit(self, task, turn, now):
        with self.lock:
            self._clock(now)
            require(task in self.tasks and type(turn) is str and re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", turn),
                    "token_ledger_binding_refused")
            require(not self.tasks[task]["closed"] and self.active_task in {None, task}, "token_ledger_concurrent_task_refused")
            reason = self.check(task, now)
            require(reason is None, reason or "token_ledger_refused")
            require(turn not in self.tasks[task]["admitted_turns"], "token_ledger_turn_reuse_refused")
            require(set(self.tasks[task]["admitted_turns"]) == set(self.tasks[task]["completed_turns"]),
                    "token_ledger_prior_turn_incomplete")
            self.active_task = task
            self.tasks[task]["admitted_turns"].append(turn)
            self.progress[(task, turn)] = now
            self._persist()

    def fail(self, task, reason):
        with self.lock:
            if task in self.tasks and reason not in self.tasks[task]["issues"]:
                self.tasks[task]["issues"].append(reason)
            self.global_stop, self.unknown = reason, True
            self._persist()

    def check(self, task, now):
        with self.lock:
            self._clock(now)
            try:
                self._check_file()
            except Exception:
                self.global_stop, self.unknown = "token_ledger_persistence_refused", True
            if self.global_stop:
                return self.global_stop
            total, known = self._total(), self._known(task)
            if total is not None and total >= self.budget.five_task_microcredits:
                self.global_stop = "token_ledger_five_task_limit"
                self._persist()
                return self.global_stop
            if known is not None and known >= self.budget.task_microcredits:
                return "token_ledger_task_limit"
            for turn in self.tasks[task]["admitted_turns"]:
                if now < self.progress[(task, turn)]:
                    self.fail(task, "token_ledger_clock_refused")
                    return self.global_stop
                if turn not in self.tasks[task]["completed_turns"] and now - self.progress[(task, turn)] >= self.budget.usage_timeout_seconds:
                    self.fail(task, "token_ledger_usage_missing")
                    return self.global_stop
            return None

    def wait_seconds(self, task, now):
        with self.lock:
            pending = [self.budget.usage_timeout_seconds - (now - self.progress[(task, turn)])
                       for turn in self.tasks[task]["admitted_turns"] if turn not in self.tasks[task]["completed_turns"]]
            return max(0, min(pending)) if pending else self.budget.usage_timeout_seconds

    def observe(self, task, turn, sequence, usage, now):
        with self.lock:
            try:
                self._clock(now)
                require(turn in self.tasks[task]["admitted_turns"] and type(sequence) is int and sequence >= 0,
                        "token_ledger_foreign_usage")
                rows = self.tasks[task]["usage_events"]
                require(len(rows) < MAX_EVENTS and all(row["server_seq"] < sequence for row in rows),
                        "token_ledger_sequence_refused")
                priced = price_usage(usage, self.previous.get((task, turn)))
                # Retain numerical fields ONLY, not arbitrary metadata or secrets.
                safe = {"model": usage["model"], **{key: usage[key] for key in ("inputTokens", "outputTokens", "cacheReadTokens")},
                        "_meta": {"turnTokenTotals": [{"model": DESIRED_MODEL["id"], "inputTokens": priced["cumulative"]["inputTokens"],
                            "outputTokens": priced["cumulative"]["outputTokens"], "cachedTokens": priced["cumulative"]["cacheReadTokens"]}]}}
                if priced["last"]["cacheWriteTokens"] is not None:
                    safe["cacheWriteTokens"] = priced["last"]["cacheWriteTokens"]
                rows.append({"turn_id": turn, "server_seq": sequence, "usage": safe, "pricing": priced})
                self.previous[(task, turn)] = priced
                if not priced["duplicate"]:
                    self.progress[(task, turn)] = now
                if priced["token_envelope_exceeded"]:
                    self.global_stop = "token_ledger_token_envelope_exceeded"
                self._persist()
                return self.check(task, now)
            except Refused as error:
                self.fail(task, str(error))
                raise
            except (KeyError, TypeError, ValueError):
                self.fail(task, "token_ledger_invalid_usage")
                raise Refused("token_ledger_invalid_usage") from None

    def complete_turn(self, task, turn):
        with self.lock:
            if not any(row["turn_id"] == turn and not row["pricing"]["duplicate"] for row in self.tasks[task]["usage_events"]):
                self.fail(task, "token_ledger_usage_missing")
                raise Refused("token_ledger_usage_missing")
            require(turn in self.tasks[task]["admitted_turns"] and turn not in self.tasks[task]["completed_turns"],
                    "token_ledger_turn_reuse_refused")
            self.tasks[task]["completed_turns"].append(turn)
            self._persist()

    def end_task(self, task, reason):
        with self.lock:
            state = self.tasks[task]
            if state["closed"]:
                if (reason.startswith("token_") or self.global_stop is not None) and state["stopped_reason"] != reason:
                    state["stopped_reason"] = reason
                    self._persist()
                return
            if any(not any(row["turn_id"] == turn and not row["pricing"]["duplicate"] for row in state["usage_events"])
                   for turn in state["admitted_turns"]):
                if "token_ledger_usage_missing" not in state["issues"]:
                    state["issues"].append("token_ledger_usage_missing")
                self.global_stop, self.unknown = self.global_stop or "token_ledger_usage_missing", True
            state["closed"], state["stopped_reason"] = True, reason
            if self.active_task == task:
                self.active_task = None
            self._persist()

    def verify(self):
        with self.lock:
            self._check_file()
            value = self.snapshot()
            require(hashlib.sha256(encoded(value)).hexdigest() == self.file_sha, "token_ledger_unpersisted_state")
            for task in self.tasks:
                verify_task_receipt(self.task_receipt(task))
            return value
