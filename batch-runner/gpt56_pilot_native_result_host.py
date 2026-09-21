"""Local native-workspace and accepted-result receipts owned by a wire session.

Only the in-process owner can verify these receipts. Files cannot reconstitute
a witness. Selected sandbox settings are not proof of remote or kernel
isolation, served identity, native caps, billing, or permission to launch.
The existing Step 2 result keeps its normal content; receipts contain only
identities, relative deliverable records and digests, never that content.
"""

from __future__ import annotations

import json
import os
import stat
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import gpt56_pilot_wire_receipt as wire
from core.inference_manifest import bind_deliverable_file_records, canonical_deliverable_path
from core.public_error import public_task_error_text
from core.result_fingerprint import inference_result_fingerprint
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _read_bytes

DIRECTORY = "pilot-native-result-host"
RESERVATION = DIRECTORY + ".reservation.json"
READY_PATH = "pilot-native-result-host-ready.json"
LINK = "pilot_native_result_host"
BLOCKER = "native_sandbox_and_result_bundle_host_unverified"
BOUNDARY = "local_codex_workspace_and_step2_saved_result_not_remote_isolation_or_served_identity"
REFUSAL = "pilot_native_result_host_refused"
_bytes, _digest = wire._bytes, wire._digest


class PilotNativeResultHostRefused(ValueError):
    def __init__(self) -> None:
        super().__init__(REFUSAL)


def _require(value: bool) -> None:
    if not value:
        raise PilotNativeResultHostRefused()


@contextmanager
def _closed():
    try:
        yield
    except Exception:
        raise PilotNativeResultHostRefused() from None


def _identity(path: Path) -> tuple[int, int]:
    metadata = _root(path).stat()
    return metadata.st_dev, metadata.st_ino


def _workspace_bytes(root: Path, relative: Path, identity: tuple[int, int], expected: dict) -> bytes:
    """Read a potentially hostile runtime leaf without following raced links.

    The ordinary bundle reader is used for trusted published bundles. Runtime
    output additionally needs dirfd traversal and a nonblocking leaf open so a
    FIFO swapped in after lstat cannot block collection.
    """
    with _held_parents(root, (relative.as_posix(),)) as check, ExitStack() as stack:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, descriptor)
        metadata = os.fstat(descriptor)
        _require((metadata.st_dev, metadata.st_ino) == identity)
        for component in relative.parts[:-1]:
            descriptor = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            stack.callback(os.close, descriptor)
        leaf = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        stack.callback(os.close, leaf)
        before = os.fstat(leaf)
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1)
        chunks = []
        while chunk := os.read(leaf, 1024 * 1024):
            chunks.append(chunk)
        data = b"".join(chunks)
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        before_identity = tuple(getattr(before, key) for key in fields)
        for after in (os.fstat(leaf), os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)):
            _require(tuple(getattr(after, key) for key in fields) == before_identity)
        _require(len(data) == before.st_size and (not expected or _digest(data) == expected))
        check()
        return data


def _runner_digest(result: dict) -> str:
    """Hash the exact private handoff without ever publishing text or bytes."""
    _require(type(result) is dict and set(result) <= {
        "success", "text", "files", "codex_diagnostics", "error", "error_category", "pilot_wire_receipt",
    } and {"success", "text", "files", "pilot_wire_receipt"} <= set(result))
    _require(type(result["success"]) is bool and type(result["text"]) is str and type(result["files"]) is list)
    files = []
    for item in result["files"]:
        _require(type(item) is dict and set(item) == {"filename", "content"}
                 and type(item["filename"]) is str and type(item["content"]) is bytes)
        files.append({"filename": item["filename"], **_digest(item["content"])})
    return inference_result_fingerprint({**result, "files": files})


class _WorkspaceWitness:
    """Private, single-use observation; no serializer or disk adoption path."""

    def __init__(self, observer: Any, workspace: Any, task_id: str, attempt: int) -> None:
        self.observer, self.workspace, self.task_id, self.attempt = observer, workspace, task_id, attempt
        self.directories = {name: _identity(getattr(workspace, name))
                            for name in ("root", "workspace", "codex_home", "home")}
        self.collected: list[dict] | None = None
        self.inventory: dict[str, dict] | None = None
        self.result_digest: str | None = None
        self.result_fields: dict | None = None
        self.accepted = False
        self.saved: list[dict] | None = None
        self.row: dict | None = None
        self.linkage: dict | None = None
        self.held = _held_parents(workspace.root, ("workspace/probe", "codex_home/probe", "home/probe"))
        self.check_parents = self.held.__enter__()
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.held.__exit__(None, None, None)


class PilotNativeResultHostSession:
    """One host owner attached to the exact verified capture/wire session.

    Failures poison both owners. Partial files and reservations are retained;
    constructing a new owner cannot adopt them. All public errors are static.
    """

    def __init__(self, wire_session: wire.PilotWireReceiptSession) -> None:
        with _closed():
            _require(type(wire_session) is wire.PilotWireReceiptSession)
            self.wire = wire_session
            self.witnesses: dict[tuple[str, int], _WorkspaceWitness] = {}
            self.files: dict[str, bytes] = {}
            self.ready: bytes | None = None
            self.results: dict[Path, bytes] = {}
            self.output_root: Path | None = None
            self.output_identity: tuple[int, int] | None = None
            self.output_directories: dict[str, tuple[int, int]] = {}
            self.failed = False
            self.workspace = wire_session.workspace
            self.root = self.workspace / DIRECTORY
            self.reserved = self.workspace / RESERVATION
            self.reservation = _bytes({"reservation_version": "pilot-native-result-host-reservation-v1",
                                       "run_id": wire.pilot.RUN_ID, "prepared_capture": wire_session.linkage,
                                       "wire_reservation": _digest(wire_session.reservation),
                                       "launch_allowed": False, "full_220_allowed": False})
            with wire_session._guard():
                _require(getattr(wire_session, "native_host", None) is None and not wire_session.armed
                         and not wire_session.active and not wire_session.files and wire_session.ready is None)
                wire_session._current()
                with _held_parents(self.workspace, (DIRECTORY, RESERVATION)) as check:
                    _require(not os.path.lexists(self.root) and not os.path.lexists(self.reserved))
                    check()
                    _write_no_clobber(self.reserved, self.reservation)
                    check()
                    self._mkdir(self.workspace, DIRECTORY)
                    check()
                self.root_identity = _identity(self.root)
                wire_session.native_host = self

    @staticmethod
    def _mkdir(parent: Path, name: str) -> None:
        with _held_parents(parent, (name,)) as check:
            descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                check()
                os.mkdir(name, mode=0o700, dir_fd=descriptor)
                check()
            finally:
                os.close(descriptor)

    @contextmanager
    def _guard(self):
        with self.wire.lock, _closed():
            try:
                _require(not self.failed and not self.wire.failed and self.wire.native_host is self)
                yield
            except Exception:
                self.failed = self.wire.failed = True
                for witness in self.witnesses.values():
                    witness.close()
                raise PilotNativeResultHostRefused() from None

    def _current(self) -> None:
        self.wire._current()
        _read_bytes(self.reserved, **_digest(self.reservation))
        _require(_identity(self.root) == self.root_identity)
        _require({path.name for path in self.root.iterdir()} ==
                 set(self.files) | ({READY_PATH} if self.ready is not None else set()))
        for name, data in self.files.items():
            _read_bytes(self.root / name, **_digest(data))
        if self.ready is not None:
            _read_bytes(self.root / READY_PATH, **_digest(self.ready))
        if self.output_root is not None:
            _require(_identity(self.output_root) == self.output_identity)
            for role, identity in self.output_directories.items():
                _require(_identity(_path(self.output_root, role)) == identity)
            for witness in self.witnesses.values():
                for record in witness.saved or []:
                    _read_bytes(_path(self.output_root, record["path"]),
                                **{key: record[key] for key in ("size", "sha256")})
        for path, data in self.results.items():
            _read_bytes(path, **_digest(data))

    def begin_task(self, observer: Any, workspace: Any) -> _WorkspaceWitness:
        """Hold the actual four local directory identities before runtime work."""
        from core.codex_runner import CodexWorkspace

        with self._guard():
            _require(self.ready is None and type(workspace) is CodexWorkspace)
            tasks = [task for task, active in self.wire.active.items() if active is observer]
            _require(type(observer) is wire._TransportObservation and len(tasks) == 1 and not observer.sealed)
            task_id = tasks[0]
            attempt = self.wire.armed[task_id]
            key = task_id, attempt
            _require(key not in self.witnesses)
            for name in ("workspace", "codex_home", "home"):
                _require(getattr(workspace, name) == workspace.root / name)
            identities = [_identity(getattr(workspace, name)) for name in ("root", "workspace", "codex_home", "home")]
            absolute_root = _root(workspace.root)
            _require(len(set(identities)) == 4 and not self.workspace.is_relative_to(absolute_root)
                     and not absolute_root.is_relative_to(self.workspace))
            _require(all(absolute_root != Path(os.path.abspath(held.workspace.root)) for held in self.witnesses.values()))
            self._current()
            witness = _WorkspaceWitness(observer, workspace, task_id, attempt)
            self.witnesses[key] = witness
            inventory, files = self._inventory(witness)
            _require(not files and all(row["kind"] == "file" for row in inventory.values()))
            return witness

    def _owned(self, witness: _WorkspaceWitness) -> None:
        _require(type(witness) is _WorkspaceWitness
                 and self.witnesses.get((witness.task_id, witness.attempt)) is witness)

    def _inventory(self, witness: _WorkspaceWitness) -> tuple[dict[str, dict], list[dict]]:
        workspace = witness.workspace
        _require(not witness.closed)
        witness.check_parents()
        root_metadata = workspace.root.stat()
        _require(root_metadata.st_uid == os.getuid() and root_metadata.st_mode & 0o077 == 0)
        _require(all(_identity(getattr(workspace, name)) == identity for name, identity in witness.directories.items()))
        prepared = next(row for row in self.wire.prepared["tasks"] if row["task_id"] == witness.task_id)
        references = {Path(row["path"]).name: {key: row[key] for key in ("size", "sha256")}
                      for row in prepared["reference_file_records"]}
        _require(len(references) == len(prepared["reference_file_records"])
                 and set(workspace.staged_reference_names) == set(references))
        inventory, files, names = {}, [], set()
        # rglob does not follow directory symlinks; lstat precedes every read.
        for path in sorted(workspace.workspace.rglob("*")):
            relative = path.relative_to(workspace.workspace)
            name = relative.as_posix()
            canonical_deliverable_path(witness.task_id, f"deliverable_files/{witness.task_id}/{name}")
            _require(workspace.is_canonical_deliverable_name(relative))
            metadata = path.lstat()
            _require(not stat.S_ISLNK(metadata.st_mode))
            if name not in references:
                _require(workspace.is_deliverable(relative))
            _require(name.casefold() not in names)
            names.add(name.casefold())
            if stat.S_ISDIR(metadata.st_mode):
                _require(name not in references)
                inventory[name] = {"kind": "directory", "identity": list(_identity(path))}
                continue
            _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1)
            data = _workspace_bytes(workspace.workspace, relative, witness.directories["workspace"], references.get(name, {}))
            inventory[name] = {"kind": "file", **_digest(data)}
            if name in references:
                continue
            files.append({"filename": name, "content": data})
        _require(set(references) <= set(inventory))
        witness.check_parents()
        return inventory, files

    def collect_deliverables(self, witness: _WorkspaceWitness, workspace: Any) -> list[dict]:
        """Strict pilot collection; legacy collection retains its own behavior."""
        with self._guard():
            self._owned(witness)
            _require(workspace is witness.workspace and witness.collected is None and not witness.observer.sealed
                     and witness.observer.runtime is not None
                     and witness.observer.runtime["cwd"] == str(workspace.workspace)
                     and "thread/start" in witness.observer.requests)
            inventory, files = self._inventory(witness)
            witness.inventory, witness.collected = inventory, files
            return [dict(row) for row in files]

    def finish_task(self, witness: _WorkspaceWitness, *, result: dict) -> None:
        """Seal the runner's complete handoff while its workspace still exists."""
        from step2_run_inference import _build_execution_observability

        with self._guard():
            self._owned(witness)
            _require(witness.result_digest is None and witness.collected is not None and witness.observer.sealed)
            inventory, files = self._inventory(witness)
            _require(inventory == witness.inventory and result["files"] == files == witness.collected)
            attempt = self.wire.attempts[witness.task_id][witness.attempt]
            _require(result["pilot_wire_receipt"] == attempt["linkage"]
                     and result["success"] is attempt["success"] and not attempt["accepted"])
            witness.result_digest = _runner_digest(result)
            witness.result_fields = {
                "content": _digest(_bytes(result["text"])),
                "deliverable_text": _digest(_bytes(result["text"] if result["success"] else None)),
                "error": _digest(_bytes(result.get("error", "Unknown error"))),
                "observability": _digest(_bytes(_build_execution_observability(result, []))),
            }
            witness.linkage = json.loads(_bytes(attempt["linkage"]))
            self._current()
            _require(self._inventory(witness)[0] == witness.inventory)
            witness.close()  # Handles only. The runner remains the workspace cleanup owner.

    def _attempt(self, task_id: str, attempt_index: int) -> _WorkspaceWitness:
        _require(type(attempt_index) is int)
        witness = self.witnesses[(task_id, attempt_index)]
        _require(witness.closed and witness.result_digest is not None and witness.row is None
                 and attempt_index == len(self.wire.attempts[task_id]) - 1)
        return witness

    def accept_task(self, *, task_id: str, attempt_index: int, result: dict) -> None:
        with self._guard():
            witness = self._attempt(task_id, attempt_index)
            _require(not witness.accepted and _runner_digest(result) == witness.result_digest)
            self._current()
            self.wire.accept_task(task_id=task_id, attempt_index=attempt_index, result=result)
            witness.accepted = True

    def _output(self, upload_root: Path) -> Path:
        _require(upload_root == self.workspace / "upload")
        if not os.path.lexists(upload_root):
            _require(self.output_root is None)
            self._mkdir(self.workspace, "upload")
        root = _root(upload_root)
        if self.output_root is None:
            parent = root / "deliverable_files"
            if os.path.lexists(parent):
                _root(parent)
                _require(not list(parent.iterdir()))
            self.output_root, self.output_identity = root, _identity(root)
        _require(root == self.output_root and _identity(root) == self.output_identity)
        return root

    def require_absent_task_output(self, task_id: str, upload_root: Path) -> None:
        """The pilot never resets, adopts or deletes an earlier task output."""
        with self._guard():
            _require(task_id in self.wire.attempts)
            root = self._output(upload_root)
            _require(not os.path.lexists(_path(root, "deliverable_files/" + task_id)))
            self._current()

    def save_task(self, *, task_id: str, attempt_index: int, result: dict, upload_root: Path) -> list[str]:
        with self._guard():
            witness = self._attempt(task_id, attempt_index)
            _require(witness.accepted and witness.saved is None and result["success"]
                     and _runner_digest(result) == witness.result_digest)
            root = self._output(upload_root)
            self._current()
            records = []
            if result["files"]:
                parent = root / "deliverable_files"
                if "deliverable_files" not in self.output_directories:
                    # An existing empty parent is used by the normal run bootstrap,
                    # but a task directory can never be adopted.
                    if not os.path.lexists(parent):
                        self._mkdir(root, "deliverable_files")
                    self.output_directories["deliverable_files"] = _identity(parent)
                self._mkdir(parent, task_id)
                self.output_directories["deliverable_files/" + task_id] = _identity(parent / task_id)
            for item in result["files"]:
                role = canonical_deliverable_path(task_id, f"deliverable_files/{task_id}/{item['filename']}")
                target = _path(root, role)
                for parent in reversed(target.parent.parents):
                    if parent == root or not parent.is_relative_to(root):
                        continue
                    relative = parent.relative_to(root).as_posix()
                    if relative not in self.output_directories:
                        self._mkdir(parent.parent, parent.name)
                        self.output_directories[relative] = _identity(parent)
                relative = target.parent.relative_to(root).as_posix()
                if relative not in self.output_directories:
                    self._mkdir(target.parent.parent, target.parent.name)
                    self.output_directories[relative] = _identity(target.parent)
                with _held_parents(root, (role,)) as check:
                    self._current()
                    check()
                    _write_no_clobber(target, item["content"])
                    check()
                    _read_bytes(target, **_digest(item["content"]))
                records.append({"path": role, **_digest(item["content"])})
            witness.saved = records
            self._current()
            return [row["path"] for row in records]

    def record_step2_result(self, *, task_id: str, attempt_index: int, row: dict, upload_root: Path) -> dict:
        """Bind what Step 2 accepted, including discarded/error/no-output state."""
        with self._guard():
            witness = self._attempt(task_id, attempt_index)
            _require(witness.accepted and row["task_id"] == task_id and row["status"] in ("success", "error"))
            self._output(upload_root)
            attempt = self.wire.attempts[task_id][attempt_index]
            if not attempt["success"]:
                _require(witness.saved is None and row["status"] == "error")
                witness.saved = []
            _require(witness.saved is not None and row["deliverable_files"] == [r["path"] for r in witness.saved])
            required_files = next(task["needs_files"] for task in self.wire.prepared["tasks"] if task["task_id"] == task_id)
            no_output = attempt["success"] and required_files and not witness.saved
            expected_status = "success" if attempt["success"] and not no_output else "error"
            _require(row["status"] == expected_status and row["model"] == self.wire.document["requested"]["deployment"]
                     and row["usage"] is None and row.get("failure_evidence") is None)
            _require(all(_digest(_bytes(row[key])) == witness.result_fields[key]
                         for key in ("content", "deliverable_text", "observability")))
            if expected_status == "error":
                expected_error = (_digest(_bytes("needs_files=True but no deliverable files produced"))
                                  if no_output else witness.result_fields["error"])
                _require(_digest(_bytes(row["error"])) == expected_error)
            else:
                _require("error" not in row)
            bound = bind_deliverable_file_records([row], self.output_root)[0]
            _require(bound["deliverable_file_records"] == witness.saved)
            self._current()
            data = _bytes({"receipt_version": "pilot-native-result-host-attempt-v1", "evidence_boundary": BOUNDARY,
                           "run_id": wire.pilot.RUN_ID, "condition": "codex_foundry", "task_id": task_id,
                           "task_order": self.wire.document["task_ids"], "attempt_index": attempt_index,
                           "retry_kind": "initial" if attempt_index == 0 else "infrastructure",
                           "prepared_capture": self.wire.linkage, "wire_receipt": witness.linkage,
                           "local_containment_sha256": _digest(_bytes(witness.directories))["sha256"],
                           "workspace_relationship": "distinct_workspace_codex_home_home_under_private_task_root",
                           "selected_policy": {"sandbox": "workspace-write", "approval": "never",
                                               "source": "observed_app_server_thread_start"},
                           "remote_or_kernel_isolation": "not_attested",
                           "collected": [{"path": item["filename"], **_digest(item["content"])}
                                         for item in witness.collected],
                           "saved_deliverables": witness.saved,
                           "runner_result_sha256": witness.result_digest,
                           "step2_status": row["status"],
                           "output_state": ("error" if not attempt["success"] else "saved" if witness.saved
                                            else "text_only" if row["deliverable_text"] else "no_output"),
                           "step2_accepted_row_sha256": inference_result_fingerprint(row),
                           "launch_allowed": False, "full_220_allowed": False})
            name = Path(witness.linkage["path"]).name
            with _held_parents(self.workspace, (RESERVATION, DIRECTORY + "/" + name)) as check:
                check()
                _write_no_clobber(self.root / name, data)
                self.files[name] = data
                self._current()
                check()
            witness.row = json.loads(_bytes(row))
            return row

    def _final_rows(self, payload: dict) -> None:
        ids = self.wire.document["task_ids"]
        prepared = self.wire.prepared
        identity = {key: prepared[key] for key in ("experiment_id", "publication_generation", "experiment_name", "source", "prepared_fingerprint")}
        identity.update(condition=prepared["condition_a"]["name"], model=self.wire.document["requested"]["deployment"])
        _require(all(key in payload and _bytes(payload[key]) == _bytes(value) for key, value in identity.items()))
        required = set(identity) | {"run_id", "ordered_task_ids", "condition_identity", "execution_mode", "pre_execution_input_capture",
                                    "resume_rounds_used", "results", "summary", "pilot_wire_receipts", "started_at", "completed_at"}
        _require(required <= set(payload) <= required | {LINK, "result_fingerprint", "cost_ledger", "azure_ai_routes"})
        _require(payload["run_id"] == wire.pilot.RUN_ID and payload["ordered_task_ids"] == ids
                 and payload["condition_identity"] == "condition_a" and payload["execution_mode"] == "codex_foundry"
                 and payload["pre_execution_input_capture"] == self.wire.linkage
                 and payload["resume_rounds_used"] == 0 and [row["task_id"] for row in payload["results"]] == ids)
        parent = self.output_root / "deliverable_files"
        expected_tasks = {w.task_id for w in self.witnesses.values() if w.saved}
        _require((set(path.name for path in _root(parent).iterdir()) if os.path.lexists(parent) else set()) == expected_tasks)
        bound = bind_deliverable_file_records(payload["results"], self.output_root)
        for row, checked in zip(payload["results"], bound):
            task_id = row["task_id"]
            attempts = self.wire.attempts[task_id]
            _require(bool(attempts))
            for index, attempt in enumerate(attempts):
                held = self.witnesses[(task_id, index)]
                _require(held.row is not None and attempt["accepted"] and held.linkage == attempt["linkage"])
            witness = self.witnesses[(task_id, len(attempts) - 1)]
            _require(set(row) <= set(witness.row) | {"deliverable_file_records", "problem_solving_cost", "reflection_history", "reflection_attempts"})
            _require(_bytes(row.get("reflection_history", [])) == _bytes([])
                     and _bytes(row.get("reflection_attempts", 0)) == _bytes(0))
            _require(row["deliverable_file_records"] == checked["deliverable_file_records"] == witness.saved)
            for key, value in witness.row.items():
                if key == "error" and value:
                    value = public_task_error_text(value)
                if key == "observability":
                    # The ordinary job loop adds measured execution_metrics.
                    _require(type(row[key]) is dict and set(row[key]) <= set(value) | {"execution_metrics"}
                             and all(k in row[key] and _bytes(row[key][k]) == _bytes(v) for k, v in value.items()))
                else:
                    _require(key in row and _bytes(row[key]) == _bytes(value))
        _require(_bytes({key: payload["summary"][key] for key in ("total", "success", "error", "qa_failed")}) ==
                 _bytes({"total": len(ids), "success": sum(row["status"] == "success" for row in bound),
                         "error": sum(row["status"] == "error" for row in bound), "qa_failed": 0}))

    def publish_result(self, payload: dict, *, output_path: Path, legacy_output_path: Path | None,
                       upload_root: Path) -> dict:
        """Save the real Step 2 payload, re-read it, then publish host ready last.

        The ready marker binds the pre-host payload fingerprint. The saved
        result links that marker; neither digest is circular. Private exact
        saved bytes remain owned by this session and are re-read on verification.
        """
        with self._guard():
            _require(self.ready is None and not self.results and LINK not in payload)
            if "result_fingerprint" in payload:
                _require(payload["result_fingerprint"] == inference_result_fingerprint(payload))
                payload = {key: value for key, value in payload.items() if key != "result_fingerprint"}
            self._output(upload_root)
            self._current()
            wire_document = wire.verify_pilot_wire_receipts(self.wire)
            expected_wire = {"path": wire.DIRECTORY + "/" + wire.READY_PATH, **_digest(self.wire.ready),
                             "evidence_boundary": wire.BOUNDARY, "launch_allowed": False, "full_220_allowed": False}
            _require(payload["pilot_wire_receipts"] == expected_wire
                     and wire_document["prepared_capture"] == self.wire.linkage)
            self._final_rows(payload)
            paths = [output_path] + ([legacy_output_path] if legacy_output_path is not None else [])
            _require(paths == [self.workspace / "step2_inference_results_condition_a.json",
                               self.workspace / "step2_inference_results.json"])
            _require(all(not os.path.lexists(path) for path in paths))
            data = _bytes({"bundle_version": "pilot-native-result-host-ready-v1", "evidence_boundary": BOUNDARY,
                           "run_id": wire.pilot.RUN_ID, "task_ids": self.wire.document["task_ids"],
                           "prepared_capture": self.wire.linkage, "wire_ready": expected_wire,
                           "reservation": _digest(self.reservation),
                           "receipts": {name: _digest(value) for name, value in sorted(self.files.items())},
                           "result_payload_before_host_sha256": inference_result_fingerprint(payload),
                           "eligible_blocker": BLOCKER, "live_inference_identity_and_wire_unverified": True,
                           "launch_allowed": False, "full_220_allowed": False})
            linked = {**payload, LINK: {"path": DIRECTORY + "/" + READY_PATH, **_digest(data),
                                       "evidence_boundary": BOUNDARY, "launch_allowed": False, "full_220_allowed": False}}
            linked["result_fingerprint"] = inference_result_fingerprint(linked)
            saved = _bytes(linked)
            roles = tuple(path.name for path in paths) + (RESERVATION, DIRECTORY + "/" + READY_PATH)
            with _held_parents(self.workspace, roles) as check:
                for path in paths:
                    check()
                    self._current()
                    _write_no_clobber(path, saved)
                    self.results[path] = saved
                    self._current()
                    check()
                self._final_rows(json.loads(saved))
                check()
                _write_no_clobber(self.root / READY_PATH, data)
                self.ready = data
                self._current()
                check()
            return linked


def native_result_host_for(session: wire.PilotWireReceiptSession) -> PilotNativeResultHostSession:
    """Require the exact live owner, never a duck-typed or deserialized receipt."""
    with _closed():
        _require(type(session) is wire.PilotWireReceiptSession)
        host = session.native_host
        _require(type(host) is PilotNativeResultHostSession and host.wire is session)
        with host._guard():
            _require(host.ready is None)
            host._current()
            return host


def verify_pilot_native_result_host(session: PilotNativeResultHostSession) -> dict:
    with _closed():
        _require(type(session) is PilotNativeResultHostSession and session.ready is not None)
        with session._guard():
            session._current()
            wire.verify_pilot_wire_receipts(session.wire)
            _require(bool(session.results))
            for data in session.results.values():
                payload = json.loads(data)
                session._final_rows(payload)
                _require(payload[LINK]["sha256"] == _digest(session.ready)["sha256"]
                         and payload["result_fingerprint"] == inference_result_fingerprint(payload))
                unlinked = {key: value for key, value in payload.items() if key not in (LINK, "result_fingerprint")}
                _require(inference_result_fingerprint(unlinked) ==
                         json.loads(session.ready)["result_payload_before_host_sha256"])
            return json.loads(session.ready)
