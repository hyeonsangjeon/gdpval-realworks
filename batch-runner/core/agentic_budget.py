"""Crash-safe request and cost reservations for agentic solver calls."""

from __future__ import annotations

import sqlite3
import fcntl
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True)
class BudgetCaps:
    attempts: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


@dataclass(frozen=True)
class BudgetUsage:
    attempts: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class BudgetExceeded(RuntimeError):
    pass


class AgenticBudgetLedger:
    """SQLite ledger whose reservations survive timeout, crash, and resume."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(f"{self.path}.init.lock", "a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.executescript(
                    """
                CREATE TABLE IF NOT EXISTS budget_usage (
                    scope TEXT PRIMARY KEY,
                    attempts INTEGER NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reservations (
                    scope TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    reserved_input INTEGER NOT NULL,
                    reserved_output INTEGER NOT NULL,
                    reserved_cost TEXT NOT NULL,
                    actual_input INTEGER,
                    actual_output INTEGER,
                    actual_cost TEXT,
                    PRIMARY KEY (scope, request_id)
                );
                    """
                )
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def reserve(
        self,
        *,
        scope: str,
        request_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        caps: BudgetCaps,
    ) -> BudgetUsage:
        return self.reserve_many(
            scopes={scope: caps},
            request_id=request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )[scope]

    def reserve_many(
        self,
        *,
        scopes: Mapping[str, BudgetCaps],
        request_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
    ) -> dict[str, BudgetUsage]:
        """Atomically reserve one request against every supplied scope."""
        _validate_nonnegative(input_tokens, "input_tokens")
        _validate_nonnegative(output_tokens, "output_tokens")
        cost = _decimal(cost_usd)
        if not scopes or not request_id or any(not scope for scope in scopes):
            raise ValueError("scopes and request_id are required")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            proposed_by_scope: dict[str, BudgetUsage] = {}
            for scope, caps in sorted(scopes.items()):
                existing = connection.execute(
                    "SELECT 1 FROM reservations WHERE scope=? AND request_id=?",
                    (scope, request_id),
                ).fetchone()
                if existing:
                    raise ValueError("request_id already reserved")
                current = self._usage_row(connection, scope)
                proposed = BudgetUsage(
                    attempts=current.attempts + 1,
                    input_tokens=current.input_tokens + input_tokens,
                    output_tokens=current.output_tokens + output_tokens,
                    cost_usd=current.cost_usd + cost,
                )
                self._check_caps(proposed, caps)
                proposed_by_scope[scope] = proposed

            for scope, proposed in proposed_by_scope.items():
                connection.execute(
                    """
                    INSERT INTO budget_usage(
                        scope, attempts, input_tokens, output_tokens, cost_usd
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(scope) DO UPDATE SET
                        attempts=excluded.attempts,
                        input_tokens=excluded.input_tokens,
                        output_tokens=excluded.output_tokens,
                        cost_usd=excluded.cost_usd
                    """,
                    (scope, proposed.attempts, proposed.input_tokens,
                     proposed.output_tokens, str(proposed.cost_usd)),
                )
                connection.execute(
                    """
                    INSERT INTO reservations(
                        scope, request_id, reserved_input, reserved_output,
                        reserved_cost
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (scope, request_id, input_tokens, output_tokens, str(cost)),
                )
            connection.commit()
            return proposed_by_scope
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def reconcile(
        self,
        *,
        scope: str,
        request_id: str,
        actual_input_tokens: int,
        actual_output_tokens: int,
        actual_cost_usd: Decimal,
    ) -> BudgetUsage:
        return self.reconcile_many(
            scopes=[scope],
            request_id=request_id,
            actual_input_tokens=actual_input_tokens,
            actual_output_tokens=actual_output_tokens,
            actual_cost_usd=actual_cost_usd,
        )[scope]

    def reconcile_many(
        self,
        *,
        scopes: Iterable[str],
        request_id: str,
        actual_input_tokens: int,
        actual_output_tokens: int,
        actual_cost_usd: Decimal,
    ) -> dict[str, BudgetUsage]:
        """Atomically reconcile one request across all reserved scopes."""
        _validate_nonnegative(actual_input_tokens, "actual_input_tokens")
        _validate_nonnegative(actual_output_tokens, "actual_output_tokens")
        actual_cost = _decimal(actual_cost_usd)
        ordered_scopes = sorted(set(scopes))
        if not ordered_scopes or not request_id:
            raise ValueError("scopes and request_id are required")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = {}
            for scope in ordered_scopes:
                row = connection.execute(
                    """
                    SELECT reserved_input, reserved_output, reserved_cost,
                           actual_input, actual_output, actual_cost
                    FROM reservations WHERE scope=? AND request_id=?
                    """,
                    (scope, request_id),
                ).fetchone()
                if row is None:
                    raise ValueError("unknown reservation")
                if row[3] is not None or row[4] is not None or row[5] is not None:
                    raise ValueError("reservation already reconciled")
                reserved_input, reserved_output = int(row[0]), int(row[1])
                reserved_cost = _decimal(row[2])
                if (
                    actual_input_tokens > reserved_input
                    or actual_output_tokens > reserved_output
                ):
                    raise ValueError("actual token usage exceeds reservation")
                if actual_cost > reserved_cost:
                    raise ValueError("actual cost exceeds reservation")
                rows[scope] = (reserved_input, reserved_output, reserved_cost)

            reconciled_by_scope = {}
            for scope, (reserved_input, reserved_output, reserved_cost) in rows.items():
                current = self._usage_row(connection, scope)
                reconciled = BudgetUsage(
                    attempts=current.attempts,
                    input_tokens=current.input_tokens - reserved_input + actual_input_tokens,
                    output_tokens=current.output_tokens - reserved_output + actual_output_tokens,
                    cost_usd=current.cost_usd - reserved_cost + actual_cost,
                )
                connection.execute(
                    """
                    UPDATE budget_usage
                    SET input_tokens=?, output_tokens=?, cost_usd=?
                    WHERE scope=?
                    """,
                    (reconciled.input_tokens, reconciled.output_tokens,
                     str(reconciled.cost_usd), scope),
                )
                connection.execute(
                    """
                    UPDATE reservations
                    SET actual_input=?, actual_output=?, actual_cost=?
                    WHERE scope=? AND request_id=?
                    """,
                    (actual_input_tokens, actual_output_tokens, str(actual_cost),
                     scope, request_id),
                )
                reconciled_by_scope[scope] = reconciled
            connection.commit()
            return reconciled_by_scope
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def usage(self, scope: str) -> BudgetUsage:
        with self._connect() as connection:
            return self._usage_row(connection, scope)

    def reservation_ids(self, scope: str) -> set[str]:
        if not scope:
            raise ValueError("scope is required")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT request_id FROM reservations WHERE scope=?",
                (scope,),
            ).fetchall()
        return {str(row[0]) for row in rows}

    @staticmethod
    def _usage_row(connection: sqlite3.Connection, scope: str) -> BudgetUsage:
        row = connection.execute(
            "SELECT attempts, input_tokens, output_tokens, cost_usd "
            "FROM budget_usage WHERE scope=?",
            (scope,),
        ).fetchone()
        if row is None:
            return BudgetUsage(0, 0, 0, Decimal("0"))
        return BudgetUsage(int(row[0]), int(row[1]), int(row[2]), _decimal(row[3]))

    @staticmethod
    def _check_caps(usage: BudgetUsage, caps: BudgetCaps) -> None:
        if usage.attempts > caps.attempts:
            raise BudgetExceeded("api_attempt_cap")
        if usage.input_tokens > caps.input_tokens:
            raise BudgetExceeded("input_token_cap")
        if usage.output_tokens > caps.output_tokens:
            raise BudgetExceeded("output_token_cap")
        if usage.cost_usd > _decimal(caps.cost_usd):
            raise BudgetExceeded("cost_cap")


def _validate_nonnegative(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("cost must be a finite non-negative Decimal") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("cost must be a finite non-negative Decimal")
    return result