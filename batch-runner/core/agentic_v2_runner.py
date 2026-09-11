"""The Agentic Sandbox V2 run place, and the two things that can drive it.

A run here is a backend that is admitted, a dispatcher that enforces the tool
contract, a pair of hash chains that record what happened, and a verifier that
refuses a record which does not add up. None of that depends on *who* chooses
the next tool, and this module now takes that choice as a parameter: a list
written in advance, or a model being asked.

Supplying a model is the caller's job and no caller in this repository does it
yet, because the deployment it would reach is behind a role assignment nobody
here may grant. Nothing in this file opens that, changes ``foundation_only`` or
``production_activation``, or loosens the ``exec_run`` refusal.
"""

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
    result_verification_standard,
    runtime_fingerprint,
    startup_is_admissible,
    trace_pair_fingerprint,
    validate_failure_stage,
    verify_agentic_v2_failure_result,
    verify_agentic_v2_result,
)
from core.agentic_v2_tools import AgenticV2Backend, AgenticV2ToolDispatcher


class _EndTheRun(Exception):
    """The run must stop now, and this is the envelope it stops with.

    Raised only from the per-call bookkeeping, which is shared by every call
    source. Returning from there is not possible and returning a sentinel would
    make every caller responsible for noticing it, so the one ending nobody may
    continue past is the one that cannot be ignored.
    """

    def __init__(self, envelope: dict):
        super().__init__(envelope.get("error", "ended"))
        self.envelope = envelope


#: How a conversation that never committed an answer is reported.
#:
#: Keyed by :class:`core.agentic_v2_conversation.StopReason` values, by string
#: rather than by import, so this module stays independent of the loop that
#: produces them — a run can be driven by anything that ends with a named
#: reason.
#:
#: The mapping is coarser than the reasons are, because
#: :data:`core.agentic_v2_contract.ERROR_TYPES` has no member for "ran out of
#: money" or "the model said something unusable". Both of those are true
#: instances of *the model never handed in an answer*, which is what
#: ``finalize_not_called`` says and what the default below gives them. The
#: distinction is not lost: the caller supplying the conversation holds its
#: record, which names the reason exactly.
#:
#: ``paid_call_refused`` is the one worth reading twice. It is the gate that is
#: still shut, and mapping it to ``capability_unavailable`` puts it in the
#: ``terminal_capability_absent`` disposition — recorded as a result, attempted
#: once, and not retried. A run against a model nobody may call yet should
#: produce 220 honest refusals quickly, not 660 attempts.
ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED: dict[str, str] = {
    "cancelled": "cancelled",
    "paid_call_refused": "capability_unavailable",
    "time_limit_reached": "task_wall_time_exhausted",
    "tool_call_limit_reached": "tool_budget_exhausted",
    "tool_desk_broke": "runner_internal_error",
    "limit_missing": "runner_internal_error",
}


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
    """Exercise the V2 state machine without constructing a model client.

    Two things can decide which tool is called next. ``scripted_calls`` is a
    list written in advance, which is how every test and every probe in this
    repository drives a run today. ``conversation`` is a model choosing, and it
    is the seam the 220-task run needs: a callable handed the task prompt and
    this run's own dispatch function, returning something that reports how it
    ended and, if it ended by committing, the finalize result.

    Everything either one passes through is the same — the same backend
    admission, the same identity check, the same chain appends, the same
    verification. That is the reason the seam is a parameter here rather than a
    second runner elsewhere: a run place whose containment is decided in two
    files has no containment anybody can read.

    The class keeps its name. ``scripted`` is now the narrower of its two
    modes, but renaming a class this heavily tested would be churn dressed as
    tidiness.
    """

    def __init__(
        self,
        *,
        backend_factory: Callable[..., AgenticV2Backend],
        scripted_calls: Iterable[Mapping[str, Any]] = (),
        conversation: Optional[Callable[[str, Callable[..., Any]], Any]] = None,
        profile: Mapping[str, Any],
        budget_caps: Optional[Mapping[str, Any]] = None,
        cancel_requested: Optional[Callable[[], bool]] = None,
        clock: Callable[[], float] = time.monotonic,
        required_backend_type: type | None = None,
        admitted_identity: Optional[Mapping[str, Any]] = None,
    ):
        if not callable(backend_factory):
            raise ValueError("agentic v2 backend_factory is required")
        if conversation is not None and not callable(conversation):
            raise ValueError("agentic v2 conversation must be callable")
        self.backend_factory = backend_factory
        self.scripted_calls = tuple(dict(call) for call in scripted_calls)
        self.conversation = conversation
        if self.conversation is not None and self.scripted_calls:
            raise ValueError(
                "a run is driven by a script or by a model, not both; two call "
                "sources means no reading of the record says which chose"
            )
        self.profile = AgenticV2Profile.from_mapping(profile)
        self.budget_caps = _validate_budget_caps(budget_caps)
        self.cancel_requested = cancel_requested or (lambda: False)
        self.clock = clock
        self.required_backend_type = required_backend_type
        self.admitted_identity = _validate_admitted_identity(admitted_identity)
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
            # The one identity this run will admit.
            #
            # There are two backends in this repository: the fixture, and
            # core/agentic_v2_microvm_backend.py, which boots a real guest and
            # reports an identity derived from the image rather than from its
            # own source text. Which one a run admits is now a value the caller
            # supplies, not a comparison written into this file, and the
            # default is the fixture -- so nothing changes for any caller that
            # does not say otherwise, and no caller in this repository says
            # otherwise today.
            #
            # Two things are checked elsewhere rather than here, and both are
            # load-bearing. `_validate_admitted_identity` refuses a backend
            # that has no declared result-verification standard, so admission
            # cannot outrun the verifier. And the verifier's fixture branch
            # still re-simulates every executed call against known fixture
            # behaviour; a guest's results are verified under the weaker,
            # separately named `attested-execution-v1` instead, which is what
            # makes admitting a second identity honest rather than a quiet
            # widening of the word "verified".
            admitted = self.admitted_identity or {
                "backend_id": FOUNDATION_BACKEND_ID,
                "foundation_only": True,
                "implementation_sha256": foundation_implementation_fingerprint(),
            }
            if identity != admitted:
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
            # Only when the backend offers one, and only when it is not empty.
            # A task that starts with nothing in its workspace produces the
            # record it produced before this existed, which is what keeps every
            # run made until now verifiable against the same code.
            declare = getattr(backend, "initial_workspace_declaration", None)
            if callable(declare):
                try:
                    starting_entries = declare()
                except Exception:
                    lifecycle.transition(LifecycleState.FAILED)
                    return finish(_failure(
                        "compute_start_failed", lifecycle, audit_chain,
                        public_chain, stage="startup",
                    ))
                if starting_entries:
                    started_payload["initial_workspace"] = starting_entries
            # Ask now whether a record built on this would verify later. The
            # checks above cover what the runner can compare things to; this
            # covers what the backend's own declared standard requires of it,
            # and asking after the event is appended is too late -- the failure
            # envelope would carry the bad event and be unverifiable itself.
            if not startup_is_admissible(started_payload):
                lifecycle.transition(LifecycleState.FAILED)
                return finish(_failure(
                    "compute_start_failed", lifecycle, audit_chain, public_chain,
                    stage="startup",
                ))
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
            #: Set by the bookkeeping when it ends a run, and read afterwards.
            #:
            #: Raising is enough for a scripted run, whose loop is right here.
            #: It is not enough for a conversation: the loop in
            #: :mod:`core.agentic_v2_conversation` catches anything a tool desk
            #: throws and reports ``tool_desk_broke``, which is correct when the
            #: desk really broke and wrong when the desk deliberately ended the
            #: run. So the ending is written down before it is thrown, and the
            #: written ending wins -- the reason a model's bad arguments are
            #: reported as bad arguments rather than as this harness failing.
            pending_ending: Optional[dict] = None

            def dispatch_one(*, call_id: str, name: str, arguments: Any):
                """One tool call, with the bookkeeping every call source owes.

                The cancel check, the deadline, the state commitment and the two
                chain appends happen here rather than once per caller, because a
                caller that skipped one of them would produce a record that
                looks like the others and is not.

                Whether a *failed* tool ends the run is not a policy choice made
                here -- it is what the trace schema already requires.
                :func:`core.agentic_v2_provenance.verify_agentic_v2_result`
                refuses any trace in which a tool event follows a tool result
                with ``ok`` false, so a run that continued past a failure could
                not produce a verifiable record of itself. Ending inside the
                shared bookkeeping makes that structurally impossible rather
                than merely unlikely.

                It matters that the ending carries the *tool's* error. A run
                that kept going and then failed verification would be caught by
                the broad handler at the end of :meth:`run` and reported as
                ``runner_internal_error``, which the ledger buckets as a runner
                defect -- so a model that passed bad arguments would be recorded
                as this harness being broken. The cost of the rule is real and
                belongs where a reader will meet it: under this schema a model
                gets one tool mistake per task, and the conversation loop's
                ability to show it an error and let it choose again cannot
                actually be used. Changing that means changing the trace
                schema, which is a separate and reviewable thing to do.
                """
                nonlocal current_state, pending_ending
                if self.cancel_requested():
                    lifecycle.transition(LifecycleState.CANCELLED)
                    pending_ending = _failure(
                        "cancelled", lifecycle, audit_chain, public_chain,
                        stage="control",
                    )
                    raise _EndTheRun(pending_ending)
                if self.clock() >= deadline:
                    lifecycle.transition(LifecycleState.FAILED)
                    pending_ending = _failure(
                        "task_wall_time_exhausted",
                        lifecycle,
                        audit_chain,
                        public_chain,
                        stage="control",
                    )
                    raise _EndTheRun(pending_ending)
                dispatch = dispatcher.dispatch(
                    call_id=call_id, name=name, arguments=arguments
                )
                request = {
                    "call_id": call_id,
                    "name": name,
                    "arguments": deepcopy(arguments),
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
                    pending_ending = _failure(
                        str(dispatch.result.get("error_type") or "tool_error"),
                        lifecycle,
                        audit_chain,
                        public_chain,
                        stage="runtime",
                    )
                    raise _EndTheRun(pending_ending)
                return dispatch

            def deadline_after_call() -> None:
                """The task's own wall clock, checked once a call has landed.

                Separate from the check inside ``dispatch_one`` because it runs
                at a different moment: after the call's result has been judged,
                and before a ``finalize`` is honoured. A task whose answer
                arrives past its deadline did not finish in time.
                """
                if self.clock() < deadline:
                    return
                failure_lifecycle = lifecycle
                if not lifecycle.terminal:
                    lifecycle.transition(LifecycleState.FAILED)
                elif lifecycle.state is not LifecycleState.FAILED:
                    failure_lifecycle = AgenticV2Lifecycle(
                        LifecycleState.FAILED
                    )
                raise _EndTheRun(_failure(
                    "task_wall_time_exhausted",
                    failure_lifecycle,
                    audit_chain,
                    public_chain,
                    stage="control",
                ))

            try:
                if self.conversation is not None:
                    conversation = self.conversation(task_prompt, dispatch_one)
                    # The bookkeeping's own ending outranks the loop's verdict.
                    # The loop saw an exception come out of the desk and called
                    # it a broken desk; this is the desk, and it knows why it
                    # stopped.
                    if pending_ending is not None:
                        return finish(pending_ending)
                    stop_reason = str(
                        getattr(
                            getattr(conversation, "stop_reason", ""), "value", ""
                        )
                    )
                    if getattr(conversation, "produced_an_answer", False):
                        deadline_after_call()
                        result = dict(conversation.final_result or {})
                    else:
                        if not lifecycle.terminal:
                            lifecycle.transition(LifecycleState.FAILED)
                        return finish(_failure(
                            ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED.get(
                                stop_reason, "finalize_not_called"
                            ),
                            lifecycle,
                            audit_chain,
                            public_chain,
                            stage="runtime",
                        ))
                else:
                    for call in self.scripted_calls:
                        dispatch = dispatch_one(
                            call_id=str(call.get("call_id", "")),
                            name=str(call.get("name", "")),
                            arguments=call.get("arguments"),
                        )
                        deadline_after_call()
                        if dispatch.finalized:
                            result = dict(dispatch.terminal_result or {})
                            break
            except _EndTheRun as ending:
                return finish(ending.envelope)
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
                # The identity's own digest, not the one it was checked
                # against. The guard above has already established they are
                # equal, so this changes nothing today -- which is the point of
                # doing it now rather than later. A run record should describe
                # the backend that ran, and reading the expected value here is
                # only incidentally right: it is right because a second backend
                # cannot get this far, not because the field means "expected".
                backend_implementation_sha256=identity["implementation_sha256"],
                capabilities_sha256=canonical_sha256(capabilities),
                budget_caps=self.budget_caps,
            )
            private_trace = _trace_payload("private", audit_chain)
            public_trace = _trace_payload("public_redacted", public_chain)
            result["agentic_v2"] = {
                "schema_version": "2.0",
                "tool_contract_version": self.profile.tool_contract_version,
                "policy_profile_id": self.profile.policy_profile_id,
                # Reported by the backend, not asserted by this line. The same
                # reasoning, and here it mattered more: the literal that stood
                # here sat two lines above a real backend_identity carrying its
                # own foundation_only, read from a substrate manifest. Nothing
                # made the two agree. Today the guard does, so the value is
                # unchanged; the difference is that a disagreement would now be
                # impossible rather than silent.
                "foundation_only": identity["foundation_only"],
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
            # Constant, and now for a stated reason rather than by inheritance
            # from a time when there was only one backend. Every identity a run
            # can admit must declare `foundation_only: True` -- see
            # `_validate_admitted_identity` -- so no run that reaches this
            # function was anything else. If that condition is ever relaxed,
            # this literal is one of the places that has to move with it, and a
            # test pins the pair together so the move cannot be forgotten.
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


def _validate_admitted_identity(
    value: Optional[Mapping[str, Any]],
) -> Optional[dict[str, Any]]:
    """Check a caller's declaration of which backend a run may admit.

    ``None`` means the foundation fixture, resolved at run time because its
    implementation hash is a hash of files on disk. Anything else has to be a
    complete identity, and has to clear three conditions that are each there
    for a different reason:

    * **a declared verification standard.** ``result_verification_standard``
      raises for a backend nobody has mapped, so a run can never admit a
      backend whose results the verifier would not know how to judge. This is
      the reason admission lives here rather than in the caller.
    * **foundation only.** Admitting a second backend is a change of *which*
      substrate may run; it is not permission to leave the foundation. The
      substrate manifests carry their own ``production_activation`` brake and
      this does not touch it.
    * **a real implementation hash.** An identity with a placeholder in it
      would put a fingerprint into the run record that corresponds to nothing.

    Raising here rather than failing the run is deliberate: a malformed
    declaration is a mistake in configuration, and a configuration mistake that
    surfaces as ``compute_start_failed`` on every task looks like an
    infrastructure fault and would be counted as one.
    """
    if value is None:
        return None
    identity = dict(value)
    if set(identity) != {
        "backend_id", "foundation_only", "implementation_sha256"
    }:
        raise ValueError("agentic v2 admitted identity is malformed")
    result_verification_standard(identity["backend_id"])
    if identity["foundation_only"] is not True:
        raise ValueError(
            "agentic v2 admitted identity must still be foundation only"
        )
    if not is_sha256(identity["implementation_sha256"]):
        raise ValueError(
            "agentic v2 admitted identity needs an implementation hash"
        )
    return identity


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