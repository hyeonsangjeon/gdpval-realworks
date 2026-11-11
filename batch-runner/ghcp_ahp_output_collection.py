"""Collect and seal owned task outputs BEFORE disposal can remove native TMPDIR.

No host, network, authentication or model entry point. This does not open the paid
gate. The injected transport must hold writers AND cleanup until sealing ends;
an absent/failed hold refuses. Current live task transport remains unimplemented.
Fixture holds are explicitly synthetic, never native process-freeze evidence.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from ghcp_ahp_client import MAX_CAPTURE_BYTES, MAX_FILE_BYTES, MAX_FILES
from ghcp_ahp_probe import Refused, strict_json

PROFILES = ("choice1_job_tmpdir", "default_policy_unpatched")
COLLECTION_SECONDS = 3.0
MAX_ENTRIES = 4096
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ghcp-output-seal-v1"
EVENTS = ["bound", "writers_and_cleanup_held", "collected", "sealed", "runtime_stopped", "deleted"]


def require(value, code):
    if not value:
        raise Refused(code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink, info.st_mode)


def directory_identity(info):
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), "output_directory_identity_refused")
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode)


@contextmanager
def directory(path):
    """Walk every absolute component by dir_fd; never follow an ancestor link."""
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "output_path_refused")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def parent_fd(root, name):
    require(type(name) is str and name and not name.startswith("/")
            and all(part not in {"", ".", ".."} for part in name.split("/")), "output_relative_path_refused")
    descriptor = os.dup(root)
    try:
        for component in name.split("/")[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor, name.split("/")[-1]
    finally:
        os.close(descriptor)


def identity(path):
    with directory(path) as descriptor:
        return directory_identity(os.fstat(descriptor))


def inventory(path, expected, check=lambda: None):
    """Independent directory inventory, including empty directories and sizes."""
    result, total, files = {}, 0, 0
    with directory(path) as root:
        require(directory_identity(os.fstat(root)) == expected, "output_root_changed")

        def walk(descriptor, prefix="", depth=0):
            nonlocal total, files
            check()
            require(depth <= 64, "output_entry_limit")
            for name in sorted(os.listdir(descriptor)):
                check()
                relative = prefix + name
                require(len(result) < MAX_ENTRIES and len(relative.encode()) <= 4096, "output_entry_limit")
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                require(info.st_dev == expected[0], "output_cross_device_refused")
                if stat.S_ISDIR(info.st_mode):
                    result[relative] = ("directory", file_identity(info))
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                    try:
                        require(file_identity(os.fstat(child)) == file_identity(info), "output_directory_changed")
                        walk(child, relative + "/", depth + 1)
                    finally:
                        os.close(child)
                else:
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "output_special_file_refused")
                    files += 1
                    total += info.st_size
                    require(files <= MAX_FILES and info.st_size <= MAX_FILE_BYTES and total <= MAX_CAPTURE_BYTES,
                            "output_size_limit")
                    result[relative] = ("file", file_identity(info))
            check()

        walk(root)
    require(identity(path) == expected, "output_root_changed")
    return result


def read_snapshot(path, expected, entries, check):
    result = {}
    with directory(path) as root:
        require(directory_identity(os.fstat(root)) == expected, "output_root_changed")
        for name, (kind, before) in sorted(entries.items()):
            if kind != "file":
                continue
            check()
            with parent_fd(root, name) as (parent, leaf):
                descriptor = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                with os.fdopen(descriptor, "rb") as stream:
                    require(file_identity(os.fstat(stream.fileno())) == before, "output_file_changed")
                    raw = bytearray()
                    while block := stream.read(min(1024 * 1024, MAX_FILE_BYTES + 1 - len(raw))):
                        check()
                        raw.extend(block)
                        require(len(raw) <= MAX_FILE_BYTES, "output_size_limit")
                    require(file_identity(os.fstat(stream.fileno())) == before
                            and file_identity(os.stat(leaf, dir_fd=parent, follow_symlinks=False)) == before
                            and len(raw) == before[2], "output_file_changed")
                result[name] = bytes(raw)
    return result


def hashes(files):
    return {name: {"sha256": digest(raw), "bytes": len(raw)} for name, raw in sorted(files.items())}


def exported(files, baseline, sanitize):
    result = []
    for name, raw in sorted(files.items()):
        require(sanitize(name) == name, "output_name_redaction_refused")
        if baseline.get(name) == {"sha256": digest(raw), "bytes": len(raw)}:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            require(sanitize(raw.decode("latin1")) == raw.decode("latin1"), "binary_credential_exposure_refused")
            value, encoding, redacted = base64.b64encode(raw).decode("ascii"), "base64", False
        else:
            value, encoding = sanitize(text), "utf-8"
            redacted = value != text
        result.append({"path": name, "source_sha256": digest(raw), "source_bytes": len(raw),
                       "encoding": encoding, "content": value, "redacted": redacted})
    return result


def read_regular(folder, name, maximum):
    with directory(folder) as parent:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum,
                    "output_seal_file_refused")
            raw = stream.read(maximum + 1)
            require(len(raw) == before.st_size and file_identity(before) == file_identity(os.fstat(stream.fileno()))
                    and file_identity(before) == file_identity(os.stat(name, dir_fd=parent, follow_symlinks=False)),
                    "output_seal_file_changed")
            return raw


def verify_seal(folder, *, profile, binding, seal_sha256, receipt_sha256=None):
    require(profile in PROFILES and type(binding) is str and re.fullmatch(r"[a-f0-9]{64}", binding)
            and type(seal_sha256) is str and re.fullmatch(r"[a-f0-9]{64}", seal_sha256),
            "output_seal_binding_refused")
    seal_raw = read_regular(folder, "output-seal.json", 65536)
    require(digest(seal_raw) == seal_sha256, "output_seal_hash_mismatch")
    seal = strict_json(seal_raw.decode())
    require(type(seal) is dict and set(seal) == {"schema", "profile", "binding", "synthetic", "execution_allowed", "events",
                                                "snapshot", "source_inventory_sha256"}, "output_seal_contract_refused")
    raw = read_regular(folder, "output-snapshot.json", MAX_CAPTURE_BYTES)
    require(seal["schema"] == SCHEMA and seal["profile"] == profile and seal["binding"] == binding and seal["execution_allowed"] is False
            and type(seal["synthetic"]) is bool and seal["events"] == EVENTS[:4]
            and seal["snapshot"] == {"sha256": digest(raw), "bytes": len(raw)}, "output_seal_contract_refused")
    snapshot = strict_json(raw.decode())
    require(type(snapshot) is dict and set(snapshot) == {"schema", "profile", "binding", "synthetic", "execution_allowed",
                                                        "input_files", "source_files", "generated_files"}
            and snapshot["schema"] == "ghcp-output-snapshot-v1" and snapshot["profile"] == profile and snapshot["binding"] == binding
            and snapshot["execution_allowed"] is False and snapshot["synthetic"] is seal["synthetic"]
            and digest(encoded(snapshot["source_files"])) == seal["source_inventory_sha256"], "output_snapshot_refused")
    for field in ("input_files", "source_files"):
        files = snapshot[field]
        require(type(files) is dict and len(files) <= MAX_FILES, "output_snapshot_refused")
        total = 0
        for name, info in files.items():
            require(type(name) is str and name and not name.startswith("/")
                    and all(part not in {"", ".", ".."} for part in name.split("/"))
                    and type(info) is dict and set(info) == {"sha256", "bytes"}
                    and type(info["sha256"]) is str and re.fullmatch(r"[a-f0-9]{64}", info["sha256"])
                    and type(info["bytes"]) is int and 0 <= info["bytes"] <= MAX_FILE_BYTES, "output_snapshot_refused")
            total += info["bytes"]
        require(total <= MAX_CAPTURE_BYTES, "output_size_limit")
    generated = snapshot["generated_files"]
    expected_names = {name for name, info in snapshot["source_files"].items()
                      if profile == PROFILES[0] or snapshot["input_files"].get(name) != info}
    require(type(generated) is list and all(type(row) is dict and set(row) ==
            {"path", "source_sha256", "source_bytes", "encoding", "content", "redacted"}
            and type(row["path"]) is str and type(row["source_bytes"]) is int for row in generated)
            and len(generated) == len(expected_names)
            and {row["path"] for row in generated} == expected_names, "output_partial_collection")
    for row in generated:
        require(snapshot["source_files"][row["path"]] == {"sha256": row["source_sha256"], "bytes": row["source_bytes"]},
                "output_snapshot_refused")
        require(type(row["content"]) is str and type(row["redacted"]) is bool
                and row["encoding"] in {"utf-8", "base64"}, "output_snapshot_refused")
        try:
            decoded = row["content"].encode() if row["encoding"] == "utf-8" else base64.b64decode(row["content"], validate=True)
        except ValueError:
            raise Refused("output_snapshot_refused") from None
        require(not row["redacted"] or row["encoding"] == "utf-8", "output_snapshot_refused")
        if not row["redacted"]:
            require(row["source_sha256"] == digest(decoded) and row["source_bytes"] == len(decoded), "output_snapshot_refused")
    if receipt_sha256 is not None:
        receipt_raw = read_regular(folder, "output-lifecycle.json", 65536)
        require(digest(receipt_raw) == receipt_sha256, "output_receipt_hash_mismatch")
        receipt = strict_json(receipt_raw.decode())
        require(type(receipt) is dict and set(receipt) == {"schema", "profile", "binding", "synthetic", "execution_allowed", "status",
                "reason_codes", "events", "seal_sha256", "host_terminated", "deleted", "hold_scope"}
                and receipt["schema"] == "ghcp-output-lifecycle-v1" and receipt["profile"] == profile and receipt["binding"] == binding
                and receipt["status"] == "complete" and receipt["reason_codes"] == []
                and receipt["execution_allowed"] is False and receipt["synthetic"] is seal["synthetic"]
                and receipt["events"] == EVENTS and receipt["seal_sha256"] == seal_sha256
                and receipt["host_terminated"] is True and receipt["deleted"] == ["job_tmpdir", "workspace"]
                and receipt["hold_scope"] == "transport_report_not_independent_native_freeze_proof",
                "output_receipt_refused")
    return snapshot


class OutputCollection:
    """One owned state, one profile, one immutable seal; never reuse on failure."""

    def __init__(self, state, job_tmpdir, spool, *, profile, synthetic, clock=time.monotonic):
        require(profile in PROFILES and type(synthetic) is bool, "output_profile_refused")
        require(callable(clock) and (synthetic or clock is time.monotonic), "output_clock_refused")
        self.state, self.job_tmpdir, self.spool = map(Path, (state, job_tmpdir, spool))
        self.workspace = self.state / "workspace"
        require(self.state.is_absolute() and self.state not in {Path("/"), Path("/tmp"), Path.home()}
                and not self.state.is_relative_to(ROOT) and not ROOT.is_relative_to(self.state)
                and self.job_tmpdir.parent == self.state / "tmp"
                and re.fullmatch(r"vscode-agent-codex-sandbox-[A-Za-z0-9_-]+", self.job_tmpdir.name)
                and not self.spool.is_relative_to(self.state) and not self.state.is_relative_to(self.spool),
                "output_binding_refused")
        self.profile, self.synthetic, self.clock = profile, synthetic, clock
        self.paths = {"job_tmpdir": self.job_tmpdir, "workspace": self.workspace}
        self.identities = {name: identity(path) for name, path in self.paths.items()}
        self.binding = digest(encoded({"profile": profile, "directories": self.identities, "nonce": uuid.uuid4().hex}))
        require(all(info[3] & 0o077 == 0 for info in self.identities.values()), "output_directory_permissions_refused")
        self.source = "job_tmpdir" if profile == PROFILES[0] else "workspace"
        initial = inventory(self.workspace, self.identities["workspace"])
        inputs = read_snapshot(self.workspace, self.identities["workspace"], initial, lambda: None)
        require(set(inputs) == {name for name, (kind, _) in initial.items() if kind == "file"}
                and initial == inventory(self.workspace, self.identities["workspace"]), "output_partial_collection")
        self.baseline = hashes(inputs)
        require(not inventory(self.job_tmpdir, self.identities["job_tmpdir"]), "output_tmpdir_not_fresh")
        identity(self.spool.parent)
        self.spool.mkdir(mode=0o700)  # Exclusive; never overwrite another receipt.
        self.spool_identity = identity(self.spool)
        self.events, self.error, self.phase = ["bound"], None, "bound"
        self.seal_sha256 = self.receipt_sha256 = None
        self.inventories = None
        self.root_hashes = None

    def refuse(self, error):
        code = "output_required_path_missing" if isinstance(error, FileNotFoundError) else str(error)
        self.error = self.error or (code if re.fullmatch(r"output_[a-z_]+|binary_credential_exposure_refused", code)
                                    else "output_collection_failed")
        self.phase = "refused"

    def _write(self, name, raw):
        require(name in {"output-snapshot.json", "output-seal.json", "output-lifecycle.json"}, "output_seal_file_refused")
        require(identity(self.spool) == self.spool_identity, "output_spool_changed")
        with directory(self.spool) as parent:
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(descriptor, "wb") as stream:
                require(stream.write(raw) == len(raw), "output_partial_write")
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent)
        require(read_regular(self.spool, name, max(len(raw), 1)) == raw, "output_partial_write")

    def collect_and_seal(self, transport, sanitize):
        require(self.phase == "bound", "output_phase_refused")
        deadline = self.clock() + COLLECTION_SECONDS

        def check():
            require(self.clock() < deadline, "output_collection_timeout")

        hold = getattr(transport, "hold_outputs", None)
        require(callable(hold), "output_hold_unavailable")
        expected = {"binding": self.binding, "writers_stopped": True, "cleanup_held": True, "synthetic": self.synthetic}
        returned = hold(binding=self.binding, timeout=1.0)
        require(type(returned) is dict and encoded(returned) == encoded(expected), "output_hold_refused")
        check()
        self.events.append("writers_and_cleanup_held")
        self.inventories = {name: inventory(path, self.identities[name], check) for name, path in self.paths.items()}
        require(sum(info[2] for entries in self.inventories.values() for kind, info in entries.values() if kind == "file")
                <= MAX_CAPTURE_BYTES, "output_size_limit")
        snapshots = {name: read_snapshot(path, self.identities[name], self.inventories[name], check)
                     for name, path in self.paths.items()}
        for name, files in snapshots.items():
            require(set(files) == {key for key, (kind, _) in self.inventories[name].items() if kind == "file"},
                    "output_partial_collection")
        self.root_hashes = {name: hashes(files) for name, files in snapshots.items()}
        data, inputs = snapshots[self.source], snapshots["workspace"]
        input_hashes = hashes(inputs)
        require(all(input_hashes.get(name) == value for name, value in self.baseline.items())
                and (self.source == "workspace" or input_hashes == self.baseline), "output_input_changed")
        for name, path in self.paths.items():
            require(inventory(path, self.identities[name], check) == self.inventories[name], "output_tree_changed")
            # Same-size writes can retain/coarsen timestamps on some filesystems.
            # Re-read bytes, not just stat metadata, before authorizing a seal.
            require(hashes(read_snapshot(path, self.identities[name], self.inventories[name], check))
                    == self.root_hashes[name], "output_tree_changed")
        generated = exported(data, self.baseline if self.source == "workspace" else {}, sanitize)
        snapshot = {"schema": "ghcp-output-snapshot-v1", "profile": self.profile, "binding": self.binding, "synthetic": self.synthetic,
                    "execution_allowed": False, "input_files": self.baseline, "source_files": hashes(data),
                    "generated_files": generated}
        require(sanitize(snapshot) == snapshot, "output_snapshot_redaction_refused")
        raw = encoded(snapshot)
        require(len(raw) <= MAX_CAPTURE_BYTES, "output_size_limit")
        self.events.append("collected")
        self._write("output-snapshot.json", raw)
        seal = {"schema": SCHEMA, "profile": self.profile, "binding": self.binding, "synthetic": self.synthetic, "execution_allowed": False,
                "events": EVENTS[:4], "snapshot": {"sha256": digest(raw), "bytes": len(raw)},
                "source_inventory_sha256": digest(encoded(snapshot["source_files"]))}
        seal_raw = encoded(seal)
        self._write("output-seal.json", seal_raw)
        self.seal_sha256 = digest(seal_raw)
        verify_seal(self.spool, profile=self.profile, binding=self.binding, seal_sha256=self.seal_sha256)
        for name, path in self.paths.items():
            require(inventory(path, self.identities[name], check) == self.inventories[name], "output_tree_changed")
            require(hashes(read_snapshot(path, self.identities[name], self.inventories[name], check))
                    == self.root_hashes[name], "output_tree_changed")
        self.events.append("sealed")
        self.phase = "sealed"

    def _delete(self, name):
        """Delete only the exact, held, inventoried root; never recurse by glob."""
        path, expected = self.paths[name], self.identities[name]
        try:
            path.lstat()
        except FileNotFoundError:
            return  # Native close cleanup AFTER sealing may already have removed it.
        entries = inventory(path, expected)
        require(entries == self.inventories[name], "output_changed_after_seal")
        require(hashes(read_snapshot(path, expected, entries, lambda: None)) == self.root_hashes[name],
                "output_changed_after_seal")
        with directory(path) as root:
            for relative, (kind, info) in sorted(entries.items(), key=lambda row: row[0].count("/"), reverse=True):
                with parent_fd(root, relative) as (parent, leaf):
                    current = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                    if kind == "file":
                        require(file_identity(current) == info, "output_changed_after_seal")
                        os.unlink(leaf, dir_fd=parent)
                    else:
                        require(stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == info[:2],
                                "output_changed_after_seal")
                        os.rmdir(leaf, dir_fd=parent)
            require(not os.listdir(root), "output_changed_after_seal")
        require(identity(path) == expected, "output_root_changed")
        with directory(path.parent) as parent:
            os.rmdir(path.name, dir_fd=parent)

    def after_termination(self, terminated):
        deleted = []
        try:
            require(self.error is None and self.phase == "sealed", "output_not_sealed")
            require(terminated is True, "output_runtime_not_stopped")
            verify_seal(self.spool, profile=self.profile, binding=self.binding, seal_sha256=self.seal_sha256)
            self.events.append("runtime_stopped")
            for name in self.paths:
                self._delete(name)
                require(not os.path.lexists(self.paths[name]), "output_delete_incomplete")
                deleted.append(name)
            self.events.append("deleted")
            self.phase = "complete"
        except Exception as error:
            self.refuse(error)
        receipt = {"schema": "ghcp-output-lifecycle-v1", "profile": self.profile, "binding": self.binding, "synthetic": self.synthetic,
                   "execution_allowed": False, "status": self.phase, "reason_codes": [self.error] if self.error else [],
                   "events": self.events, "seal_sha256": self.seal_sha256, "host_terminated": terminated is True,
                   "deleted": deleted, "hold_scope": "transport_report_not_independent_native_freeze_proof"}
        try:
            raw = encoded(receipt)
            self._write("output-lifecycle.json", raw)
            self.receipt_sha256 = digest(raw)
        except Exception as error:
            self.refuse(error)
        return self.phase == "complete"

    def capture(self):
        require(self.phase == "complete" and not self.error and self.receipt_sha256 is not None, self.error or "output_not_sealed")
        snapshot = verify_seal(self.spool, profile=self.profile, binding=self.binding, seal_sha256=self.seal_sha256,
                               receipt_sha256=self.receipt_sha256)
        return copy.deepcopy(snapshot["generated_files"]), {
            "schema": "ghcp-output-reference-v1", "profile": self.profile, "binding": self.binding, "synthetic": self.synthetic,
            "execution_allowed": False, "seal_sha256": self.seal_sha256,
            "receipt_sha256": self.receipt_sha256, "events": list(self.events), "status": "complete"}
