"""Model-free scripted runner for the Agentic Sandbox V2 foundation."""

from __future__ import annotations

from copy import deepcopy
import multiprocessing
import os
import signal
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from core.agentic_v2_contract import (
    ERROR_TYPES,
    FOUNDATION_BACKEND_ID,
    TOOL_CONTRACT_VERSION,
    AgenticV2Lifecycle,
    AgenticV2Profile,
    LifecycleState,
    is_sha256,
)
from core.agentic_v2_provenance import (
    AgenticV2EventChain,
    canonical_sha256,
    foundation_implementation_fingerprint,
    runtime_fingerprint,
    trace_pair_fingerprint,
    validate_failure_stage,
    verify_agentic_v2_failure_result,
    verify_agentic_v2_result,
)
from core.agentic_v2_tools import AgenticV2Backend, AgenticV2ToolDispatcher


class AgenticV2IsolatedFixtureRunner:
    """Run the model-free fixture in a killable task-local worker process."""

    def __init__(
        self,
        *,
        fixture_root: str | Path,
        scripted_calls: Iterable[Mapping[str, Any]],
        profile: Mapping[str, Any],
        budget_caps: Optional[Mapping[str, Any]] = None,
        cancel_requested: Optional[Callable[[], bool]] = None,
    ):
        root = Path(fixture_root)
        if root.is_symlink():
            raise ValueError("agentic v2 fixture root symlink is forbidden")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.fixture_root = root.resolve()
        self.scripted_calls = tuple(deepcopy(dict(call)) for call in scripted_calls)
        self.profile = AgenticV2Profile.from_mapping(profile)
        self.budget_caps = _validate_budget_caps(budget_caps)
        self.cancel_requested = cancel_requested or (lambda: False)
        self._context = multiprocessing.get_context("fork")
        self._active_process = None
        self._active_process_group = None
        self._last_process = None
        self._closed = False

    def close(self) -> None:
        self._closed = True
        if self._active_process is not None:
            _stop_process(
                self._active_process,
                self._active_process_group,
            )
            self._active_process = None
            self._active_process_group = None

    def run(
        self,
        task_prompt: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        perception_text: Optional[str] = None,
        *,
        run_id: str = "local-nonpaid",
        condition_name: str = "condition_a",
        task_id: str = "unknown-task",
    ) -> dict:
        if self._closed:
            raise RuntimeError("agentic v2 runner is closed")
        run_root = Path(tempfile.mkdtemp(
            prefix=".agentic-v2-run-", dir=self.fixture_root
        ))
        receiver, sender = self._context.Pipe(duplex=False)
        request = {
            "task_prompt": task_prompt,
            "reference_files": list(reference_files or []),
            "occupation": occupation,
            "experiment_prompt": experiment_prompt,
            "perception_text": perception_text,
            "run_id": run_id,
            "condition_name": condition_name,
            "task_id": task_id,
        }
        process = self._context.Process(
            target=_run_fixture_worker,
            args=(
                sender,
                str(run_root),
                self.scripted_calls,
                {
                    "tool_contract_version": self.profile.tool_contract_version,
                    "policy_profile_id": self.profile.policy_profile_id,
                    "foundation_only": True,
                },
                self.budget_caps,
                request,
            ),
            name="agentic-v2-fixture",
            daemon=True,
        )
        self._last_process = process
        result = None
        error = None
        started = False
        process_group = None
        deadline = time.monotonic() + self.budget_caps["wall_seconds"]
        try:
            process.start()
            started = True
            self._active_process = process
            sender.close()
            while process_group is None and error is None:
                if self.cancel_requested():
                    error = "cancelled"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = "task_wall_time_exhausted"
                    break
                if receiver.poll(min(remaining, 0.05)):
                    try:
                        message = receiver.recv()
                    except (EOFError, OSError):
                        error = "compute_backend_error"
                    else:
                        if (
                            isinstance(message, dict)
                            and message.get("kind") == "ready"
                            and message.get("process_group") == process.pid
                        ):
                            process_group = process.pid
                            self._active_process_group = process_group
                        else:
                            error = "compute_backend_error"
                    continue
                if not process.is_alive():
                    error = "compute_backend_error"
                    break
            while result is None and error is None:
                if self.cancel_requested():
                    error = "cancelled"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = "task_wall_time_exhausted"
                    break
                if receiver.poll(min(remaining, 0.05)):
                    try:
                        message = receiver.recv()
                    except (EOFError, OSError):
                        error = "compute_backend_error"
                    else:
                        if (
                            isinstance(message, dict)
                            and message.get("kind") == "result"
                            and isinstance(message.get("result"), dict)
                        ):
                            candidate = message["result"]
                            try:
                                _verify_worker_result(candidate)
                            except Exception:
                                error = "compute_backend_error"
                            else:
                                result = candidate
                        else:
                            error = "compute_backend_error"
                    break
                if not process.is_alive():
                    process.join()
                    if receiver.poll():
                        try:
                            message = receiver.recv()
                        except (EOFError, OSError):
                            error = "compute_backend_error"
                        else:
                            candidate = (
                                message.get("result")
                                if isinstance(message, dict)
                                and message.get("kind") == "result"
                                and isinstance(message.get("result"), dict)
                                else None
                            )
                            if candidate is None:
                                error = "compute_backend_error"
                            else:
                                try:
                                    _verify_worker_result(candidate)
                                except Exception:
                                    error = "compute_backend_error"
                                else:
                                    result = candidate
                    else:
                        error = "compute_backend_error"
                    break
        except Exception:
            result = None
            error = "compute_backend_error"
        finally:
            if started:
                _stop_process(process, process_group)
            self._active_process = None
            self._active_process_group = None
            receiver.close()
            try:
                sender.close()
            except OSError:
                pass
        cleanup_failed = False
        try:
            shutil.rmtree(run_root)
        except OSError:
            cleanup_failed = True
        if result is None:
            state = (
                LifecycleState.CANCELLED
                if error == "cancelled"
                else LifecycleState.FAILED
            )
            result = _failure(
                error or "compute_backend_error",
                AgenticV2Lifecycle(state),
                AgenticV2EventChain(),
                AgenticV2EventChain(),
                stage=(
                    "control"
                    if error in {"cancelled", "task_wall_time_exhausted"}
                    else "backend"
                ),
            )
        if cleanup_failed and result.get("success") is True:
            result = _failure(
                "compute_cleanup_failed",
                AgenticV2Lifecycle(LifecycleState.FAILED),
                AgenticV2EventChain(),
                AgenticV2EventChain(),
                stage="cleanup",
            )
        return result


def _run_fixture_worker(
    connection,
    run_root: str,
    scripted_calls: Iterable[Mapping[str, Any]],
    profile: Mapping[str, Any],
    budget_caps: Mapping[str, Any],
    request: Mapping[str, Any],
) -> None:
    sent_result = False
    try:
        os.setsid()
        os.environ.clear()
        connection.send({
            "kind": "ready",
            "process_group": os.getpgrp(),
        })
        from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend

        runner = AgenticV2ScriptedRunner(
            backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
                root=run_root, **kwargs
            ),
            scripted_calls=scripted_calls,
            profile=profile,
            budget_caps=budget_caps,
            required_backend_type=AgenticV2FixtureBackend,
        )
        connection.send({
            "kind": "result",
            "result": runner.run(**dict(request)),
        })
        sent_result = True
    except Exception:
        try:
            connection.send({
                "kind": "result",
                "result": _failure(
                    "compute_backend_error",
                    AgenticV2Lifecycle(LifecycleState.FAILED),
                    AgenticV2EventChain(),
                    AgenticV2EventChain(),
                    stage="backend",
                ),
            })
            sent_result = True
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        if sent_result:
            threading.Event().wait()
        connection.close()


def _verify_worker_result(value: Mapping[str, Any]) -> None:
    if value.get("success") is True:
        verify_agentic_v2_result(value)
    elif value.get("success") is False:
        verify_agentic_v2_failure_result(value)
    else:
        raise ValueError("agentic v2 worker result status is invalid")


def _stop_process(process, process_group: int | None) -> None:
    if process_group is None:
        try:
            candidate = os.getpgid(process.pid)
        except (ProcessLookupError, OSError):
            candidate = None
        if candidate == process.pid:
            process_group = candidate
    if process_group is not None and (
        process_group != process.pid or process_group == os.getpgrp()
    ):
        process_group = None
    if process_group is None:
        if process.is_alive():
            process.terminate()
    else:
        try:
            os.killpg(process_group, signal.SIGTERM)
        except ProcessLookupError:
            pass
    process.join(timeout=0.5)
    if process_group is not None:
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.is_alive():
        process.kill()
    process.join()


class AgenticV2ScriptedRunner:
    """Exercise the V2 state machine without constructing a model client."""

    def __init__(
        self,
        *,
        backend_factory: Callable[..., AgenticV2Backend],
        scripted_calls: Iterable[Mapping[str, Any]],
        profile: Mapping[str, Any],
        budget_caps: Optional[Mapping[str, Any]] = None,
        cancel_requested: Optional[Callable[[], bool]] = None,
        clock: Callable[[], float] = time.monotonic,
        required_backend_type: type | None = None,
    ):
        if not callable(backend_factory):
            raise ValueError("agentic v2 backend_factory is required")
        self.backend_factory = backend_factory
        self.scripted_calls = tuple(dict(call) for call in scripted_calls)
        self.profile = AgenticV2Profile.from_mapping(profile)
        self.budget_caps = _validate_budget_caps(budget_caps)
        self.cancel_requested = cancel_requested or (lambda: False)
        self.clock = clock
        self.required_backend_type = required_backend_type
        self._closed = False

    def close(self) -> None:
        self._closed = True

    def run(
        self,
        task_prompt: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        perception_text: Optional[str] = None,
        *,
        run_id: str = "local-nonpaid",
        condition_name: str = "condition_a",
        task_id: str = "unknown-task",
    ) -> dict:
        del experiment_prompt, perception_text
        if self._closed:
            raise RuntimeError("agentic v2 runner is closed")
        lifecycle = AgenticV2Lifecycle()
        audit_chain = AgenticV2EventChain()
        public_chain = AgenticV2EventChain()
        started_at = self.clock()
        max_task_seconds = float(self.budget_caps.get("wall_seconds", 1200))
        deadline = started_at + max_task_seconds
        backend: AgenticV2Backend | None = None
        result: dict | None = None

        def finish(value: Mapping[str, Any]) -> dict:
            nonlocal result
            result = dict(value)
            return result

        try:
            try:
                backend = self.backend_factory(
                    task_prompt=task_prompt,
                    reference_files=list(reference_files or []),
                    occupation=occupation,
                    run_id=run_id,
                    condition_name=condition_name,
                    task_id=task_id,
                    profile=self.profile,
                    budget_caps=self.budget_caps,
                )
                if (
                    self.required_backend_type is not None
                    and type(backend) is not self.required_backend_type
                ):
                    raise ValueError("agentic v2 foundation backend type mismatch")
            except Exception:
                lifecycle.transition(LifecycleState.STARTED)
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "compute_backend_error", lifecycle, audit_chain, public_chain,
                    stage="backend",
                ))
            lifecycle.transition(LifecycleState.STARTED)
            startup_started = self.clock()
            if startup_started >= deadline:
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "task_wall_time_exhausted", lifecycle, audit_chain, public_chain,
                    stage="control",
                ))
            try:
                startup = dict(backend.start(deadline - startup_started))
            except Exception:
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "compute_start_failed", lifecycle, audit_chain, public_chain,
                    stage="startup",
                ))
            if self.clock() >= deadline:
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "task_wall_time_exhausted", lifecycle, audit_chain, public_chain,
                    stage="control",
                ))
            if startup.get("ok") is not True:
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "compute_start_failed",
                    lifecycle,
                    audit_chain,
                    public_chain,
                    stage="startup",
                ))
            startup_data = startup.get("data") or {}
            identity = startup_data.get("backend_identity") or {}
            expected_implementation_sha = foundation_implementation_fingerprint()
            if identity != {
                "backend_id": FOUNDATION_BACKEND_ID,
                "foundation_only": True,
                "implementation_sha256": expected_implementation_sha,
            }:
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "compute_start_failed", lifecycle, audit_chain, public_chain,
                    stage="startup",
                ))
            capabilities = startup_data.get("capabilities")
            try:
                expected_capabilities = dict(backend.expected_capabilities())
            except Exception:
                expected_capabilities = None
            if (
                not _valid_capabilities(capabilities)
                or capabilities != expected_capabilities
            ):
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "compute_start_failed", lifecycle, audit_chain, public_chain,
                    stage="startup",
                ))
            substrate = startup_data.get("substrate_manifest") or {}
            substrate_sha = substrate.get("sha256")
            package_snapshot_sha = startup_data.get(
                "package_snapshot_sha256"
            )
            browser_build_sha = startup_data.get(
                "browser_build_sha256"
            )
            if not all(is_sha256(value) for value in (
                substrate_sha, package_snapshot_sha, browser_build_sha
            )):
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "substrate_manifest_missing", lifecycle, audit_chain, public_chain,
                    stage="startup",
                ))
            lifecycle.transition(LifecycleState.ACTIVE)
            try:
                initial_state = backend.state_sha256()
            except Exception:
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "compute_start_failed", lifecycle, audit_chain, public_chain,
                    stage="startup",
                ))
            started_payload = {
                "run_id": run_id,
                "condition": condition_name,
                "task_id": task_id,
                "backend_identity": deepcopy(identity),
                "capabilities": deepcopy(capabilities),
                "policy_profile_id": self.profile.policy_profile_id,
                "runtime": {
                    "substrate_manifest_sha256": substrate_sha,
                    "package_snapshot_sha256": package_snapshot_sha,
                    "browser_build_sha256": browser_build_sha,
                    "budget_caps": deepcopy(self.budget_caps),
                },
            }
            audit_chain.append(
                "started", started_payload, state_sha256=initial_state
            )
            public_chain.append(
                "started", started_payload, state_sha256=initial_state
            )
            dispatcher = AgenticV2ToolDispatcher(
                backend,
                lifecycle,
                max_total_calls=int(self.budget_caps.get("tool_calls", 32)),
                deadline=None,
                clock=self.clock,
                record_wall_time=False,
            )
            current_state = initial_state
            for call in self.scripted_calls:
                if self.cancel_requested():
                    lifecycle.transition(LifecycleState.CANCELLED)
                    return finish(_failure(
                        "cancelled", lifecycle, audit_chain, public_chain,
                        stage="control",
                    ))
                if self.clock() >= deadline:
                    lifecycle.transition(LifecycleState.FAILED)
                    return finish(_failure(
                        "task_wall_time_exhausted",
                        lifecycle,
                        audit_chain,
                        public_chain,
                        stage="control",
                    ))
                dispatch = dispatcher.dispatch(
                    call_id=str(call.get("call_id", "")),
                    name=str(call.get("name", "")),
                    arguments=call.get("arguments"),
                )
                request = {
                    "call_id": str(call.get("call_id", "")),
                    "name": str(call.get("name", "")),
                    "arguments": deepcopy(call.get("arguments")),
                }
                state_commitment = (
                    dispatch.result.get("state_after_sha256")
                    or dispatch.result.get("state_before_sha256")
                    or current_state
                )
                audit_chain.append(
                    "tool_result",
                    {
                        "request": request,
                        "result": deepcopy(dispatch.result),
                        "replayed": dispatch.replayed,
                    },
                    state_sha256=state_commitment,
                )
                current_state = state_commitment
                public_chain.append(
                    "tool_result_public",
                    {
                        "result_commitment": _public_result_commitment(
                            dispatch.result
                        ),
                        "replayed": dispatch.replayed,
                    },
                    state_sha256=state_commitment,
                )
                if dispatch.result.get("ok") is not True:
                    if not lifecycle.terminal:
                        lifecycle.transition(LifecycleState.FAILED)
                    return finish(_failure(
                        str(dispatch.result.get("error_type") or "tool_error"),
                        lifecycle,
                        audit_chain,
                        public_chain,
                        stage="runtime",
                    ))
                if self.clock() >= deadline:
                    failure_lifecycle = lifecycle
                    if not lifecycle.terminal:
                        lifecycle.transition(LifecycleState.FAILED)
                    elif lifecycle.state is not LifecycleState.FAILED:
                        failure_lifecycle = AgenticV2Lifecycle(
                            LifecycleState.FAILED
                        )
                    return finish(_failure(
                        "task_wall_time_exhausted",
                        failure_lifecycle,
                        audit_chain,
                        public_chain,
                        stage="control",
                    ))
                if dispatch.finalized:
                    result = dict(dispatch.terminal_result or {})
                    break
            if result is None:
                if not lifecycle.terminal:
                    lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "finalize_not_called", lifecycle, audit_chain, public_chain,
                    stage="runtime",
                ))
            runtime_sha = runtime_fingerprint(
                policy_profile_id=self.profile.policy_profile_id,
                substrate_manifest_sha256=substrate_sha,
                package_snapshot_sha256=package_snapshot_sha,
                browser_build_sha256=browser_build_sha,
                backend_implementation_sha256=expected_implementation_sha,
                capabilities_sha256=canonical_sha256(capabilities),
                budget_caps=self.budget_caps,
            )
            private_trace = _trace_payload("private", audit_chain)
            public_trace = _trace_payload("public_redacted", public_chain)
            result["agentic_v2"] = {
                "schema_version": "2.0",
                "tool_contract_version": self.profile.tool_contract_version,
                "policy_profile_id": self.profile.policy_profile_id,
                "foundation_only": True,
                "lifecycle_state": lifecycle.state.value,
                "backend_identity": deepcopy(identity),
                "capabilities_sha256": canonical_sha256(capabilities),
                "runtime_fingerprint": runtime_sha,
                "private_audit": private_trace,
                "public_trace": public_trace,
                "trace_pair_sha256": trace_pair_fingerprint(
                    private_trace, public_trace
                ),
            }
            verify_agentic_v2_result(result)
            return finish(result)
        except Exception:
            if not lifecycle.terminal:
                try:
                    lifecycle.transition(LifecycleState.FAILED)
                except ValueError:
                    pass
            return finish(_failure(
                (
                    "runner_internal_error"
                    if audit_chain.events
                    else "compute_start_failed"
                ),
                lifecycle,
                audit_chain,
                public_chain,
                stage="runtime" if audit_chain.events else "startup",
            ))
        finally:
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    if result is None or result.get("success") is True:
                        cleanup_failure = _failure(
                            "compute_cleanup_failed",
                            lifecycle,
                            audit_chain,
                            public_chain,
                            stage="cleanup",
                        )
                        if result is None:
                            result = cleanup_failure
                        else:
                            result.clear()
                            result.update(cleanup_failure)


def _failure(
    error: str,
    lifecycle: AgenticV2Lifecycle,
    audit_chain: AgenticV2EventChain,
    public_chain: AgenticV2EventChain,
    *,
    stage: str,
) -> dict:
    public_error = error if error in ERROR_TYPES else "runner_internal_error"
    validate_failure_stage(public_error, stage)
    terminal_state = (
        "cancelled"
        if lifecycle.state is LifecycleState.CANCELLED
        else "failed"
    )
    failure_payload = {
        "error_type": public_error,
        "lifecycle_state": terminal_state,
        "stage": stage,
    }
    failure_state = canonical_sha256({
        "schema_version": "2.0",
        **failure_payload,
    })
    audit_chain.append("failure", failure_payload, state_sha256=failure_state)
    public_chain.append("failure", failure_payload, state_sha256=failure_state)
    private_trace = _trace_payload("private", audit_chain)
    public_trace = _trace_payload("public_redacted", public_chain)
    value = {
        "success": False,
        "text": "",
        "deliverable_text": "",
        "files": [],
        "error": public_error,
        "agentic_v2": {
            "schema_version": "2.0",
            "foundation_only": True,
            "lifecycle_state": terminal_state,
            "private_audit": private_trace,
            "public_trace": public_trace,
            "trace_pair_sha256": trace_pair_fingerprint(
                private_trace, public_trace
            ),
        },
    }
    return value


def _trace_payload(classification: str, chain: AgenticV2EventChain) -> dict:
    return {
        "classification": classification,
        "event_chain_head_sha256": chain.head_sha256,
        "events": deepcopy(chain.events),
    }


def _public_result_commitment(result: Mapping[str, Any]) -> dict:
    fields = (
        "call_id",
        "tool_name",
        "request_sha256",
        "result_sha256",
        "ok",
        "error_type",
        "usage_delta",
        "state_before_sha256",
        "state_after_sha256",
    )
    return {field: deepcopy(result.get(field)) for field in fields}


def _validate_budget_caps(value: Optional[Mapping[str, Any]]) -> dict[str, int]:
    raw = dict(value or {"tool_calls": 32, "wall_seconds": 1200})
    allowed = {"tool_calls", "wall_seconds"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown agentic v2 budget cap(s): {sorted(unknown)}")
    result = {}
    for name, maximum in (("tool_calls", 256), ("wall_seconds", 3600)):
        candidate = raw.get(name, 32 if name == "tool_calls" else 1200)
        if isinstance(candidate, bool):
            raise ValueError(f"agentic v2 {name} must be a positive integer")
        try:
            parsed = int(candidate)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"agentic v2 {name} must be a positive integer"
            ) from exc
        if parsed <= 0 or parsed > maximum:
            raise ValueError(f"agentic v2 {name} must be in [1, {maximum}]")
        result[name] = parsed
    return result


def _valid_capabilities(value: Any) -> bool:
    expected = {"commands", "runtimes", "packages", "formats", "budgets"}
    return (
        isinstance(value, dict)
        and set(value) == expected
        and all(
            isinstance(value[name], list)
            and len(value[name]) <= 512
            and all(isinstance(item, str) and len(item) <= 512 for item in value[name])
            for name in expected
        )
    )