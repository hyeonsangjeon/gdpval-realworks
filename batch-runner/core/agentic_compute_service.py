"""Dedicated uncredentialed HTTPS service for one approved agentic task."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import ssl
import tempfile
import time
import math
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from core.agentic_channel import (
    ChannelScope,
    ComputeChannelServer,
    EnvelopeAuthority,
)
from core.agentic_compute import AgenticDockerBackend
from core.agentic_remote_compute import MAX_COMMAND_BYTES, MAX_RESULT_BYTES


class ApprovedDockerBackendFactory:
    """Resolve immutable reference IDs to compute-runner-local approved bytes."""

    def __init__(
        self,
        *,
        input_manifest_path: str | Path,
        dataset_root: str | Path,
        image: str,
        verifier_image: str,
        seccomp_profile: str,
        apparmor_profile: str,
        sbom_sha256: str,
        cpus: float = 2,
        memory_gb: int = 8,
    ):
        raw_dataset_root = Path(dataset_root)
        if raw_dataset_root.is_symlink():
            raise ValueError("compute dataset root must not be a symlink")
        self.dataset_root = raw_dataset_root.resolve()
        if not self.dataset_root.is_dir():
            raise ValueError("compute dataset root is missing")
        document = json.loads(
            Path(input_manifest_path).read_text(encoding="utf-8")
        )
        if not isinstance(document, dict) or set(document) != {
            "schema_version", "provider_classification",
            "selection_recomputation_sha256",
            "staging_filesystem_device", "tasks", "sha256"
        }:
            raise ValueError("input manifest fields are invalid")
        if document["schema_version"] != "agentic-input-manifest-v1":
            raise ValueError("input manifest version is invalid")
        canonical = {
            key: value for key, value in document.items() if key != "sha256"
        }
        actual_hash = hashlib.sha256(
            json.dumps(
                canonical, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        ).hexdigest()
        if document["sha256"] != actual_hash:
            raise ValueError("input manifest hash mismatch")
        selection_hash = document["selection_recomputation_sha256"]
        if (
            not isinstance(selection_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", selection_hash) is None
        ):
            raise ValueError("input manifest selection identity is invalid")
        provider_classification = document["provider_classification"]
        if (
            not isinstance(provider_classification, str)
            or not provider_classification
        ):
            raise ValueError("input manifest provider classification is invalid")
        if document["staging_filesystem_device"] != Path(
            tempfile.gettempdir()
        ).stat().st_dev:
            raise ValueError("input manifest staging filesystem mismatch")
        if not isinstance(document["tasks"], dict):
            raise ValueError("input manifest tasks are invalid")
        self.tasks = document["tasks"]
        self.selection_recomputation_sha256 = selection_hash
        self.provider_classification = provider_classification
        self.image = image
        self.verifier_image = verifier_image
        self.seccomp_profile = seccomp_profile
        self.apparmor_profile = apparmor_profile
        self.sbom_sha256 = sbom_sha256
        self.cpus = cpus
        self.memory_gb = memory_gb

    def __call__(
        self,
        *,
        task_prompt: str,
        reference_ids: list,
        occupation: str,
        task_id: str,
    ) -> AgenticDockerBackend:
        task = self.tasks.get(task_id)
        if not isinstance(task, dict) or set(task) != {
            "reference_ids", "files", "input_merkle_root"
        }:
            raise ValueError("task input manifest is missing or invalid")
        if reference_ids != task["reference_ids"]:
            raise ValueError("task reference IDs differ from approved manifest")
        files = task["files"]
        if not isinstance(files, list):
            raise ValueError("task input files are invalid")
        reference_files = []
        approved = {}
        for item in files:
            required = {
                "reference_id", "source_path", "relative_path", "path", "type",
                "link_count", "size_bytes", "source_allocated_bytes",
                "staged_allocated_bytes", "sha256", "provider_classification",
            }
            if not isinstance(item, Mapping) or set(item) != required:
                raise ValueError("approved input file record is invalid")
            if (
                item["provider_classification"]
                != self.provider_classification
            ):
                raise ValueError(
                    "approved input provider classification differs from manifest"
                )
            if item["reference_id"] not in reference_ids:
                raise ValueError("approved input file has unknown reference ID")
            source_relative = Path(str(item["source_path"]))
            if (
                source_relative.is_absolute()
                or not source_relative.parts
                or ".." in source_relative.parts
                or any(part.startswith(".") for part in source_relative.parts)
            ):
                raise ValueError("approved source path is invalid")
            relative = str(item["relative_path"])
            if item["path"] != relative:
                raise ValueError("approved relative path identity mismatch")
            reference_files.append({
                "source_root": str(self.dataset_root),
                "source_path": source_relative.as_posix(),
                "relative_path": relative,
            })
            approved[relative] = {
                key: item[key]
                for key in (
                    "path", "type", "link_count", "size_bytes",
                    "source_allocated_bytes", "sha256",
                    "provider_classification",
                )
            }
        backend = AgenticDockerBackend(
            task_prompt=task_prompt,
            reference_files=reference_files,
            occupation=occupation,
            approved_input_manifest=approved,
            provider_classification=self.provider_classification,
            expected_input_merkle_root=str(task["input_merkle_root"]),
            selection_recomputation_sha256=(
                self.selection_recomputation_sha256
            ),
            image=self.image,
            verifier_image=self.verifier_image,
            seccomp_profile=self.seccomp_profile,
            apparmor_profile=self.apparmor_profile,
            sbom_sha256=self.sbom_sha256,
            cpus=self.cpus,
            memory_gb=self.memory_gb,
        )
        return backend


class ComputeRequestHandler(BaseHTTPRequestHandler):
    server_version = "GDPValAgenticCompute/1"

    def do_POST(self) -> None:
        self.connection.settimeout(10.0)
        if self.path != "/v1/agentic/compute":
            self.send_error(404)
            return
        if self.connection.getpeercert() is None:
            self.send_error(403)
            return
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "")
        except ValueError:
            self.send_error(411)
            return
        if length <= 0 or length > MAX_COMMAND_BYTES:
            self.send_error(413)
            return
        try:
            envelope = json.loads(self.rfile.read(length))
            deadline_at = _command_deadline(envelope)
            compute_server = getattr(self.server, "compute_server", None)
            if compute_server is None:
                raise RuntimeError("compute server is unavailable")
            result = compute_server.handle(envelope)
            body = _encode_response_before_deadline(result, deadline_at)
        except Exception:
            self.send_error(400)
            return
        if time.time() >= deadline_at:
            self.send_error(408)
            return
        self.connection.settimeout(max(0.001, deadline_at - time.time()))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        view = memoryview(body)
        for offset in range(0, len(view), 64 * 1024):
            remaining = deadline_at - time.time()
            if remaining <= 0:
                self.close_connection = True
                return
            self.connection.settimeout(max(0.001, remaining))
            self.wfile.write(view[offset:offset + 64 * 1024])
        self.wfile.flush()

    def log_message(self, format: str, *args: Any) -> None:
        return


class ComputeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, compute_server):
        super().__init__(address, ComputeRequestHandler)
        self.compute_server = compute_server

    def server_close(self) -> None:
        self.compute_server.close()
        super().server_close()


def _command_deadline(envelope: Any) -> float:
    payload = envelope.get("payload") if isinstance(envelope, Mapping) else None
    value = payload.get("deadline_at") if isinstance(payload, Mapping) else None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= time.time()
        or float(value) > time.time() + 1200
    ):
        raise ValueError("compute command deadline is invalid")
    return float(value)


def _encode_response_before_deadline(
    result: Mapping[str, Any], deadline_at: float
) -> bytes:
    encoder = json.JSONEncoder(
        sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    chunks = []
    total = 0
    for text in encoder.iterencode(dict(result)):
        if time.time() >= deadline_at:
            raise TimeoutError("compute response encoding deadline exhausted")
        chunk = text.encode("utf-8")
        total += len(chunk)
        if total > MAX_RESULT_BYTES:
            raise RuntimeError("compute result exceeds byte cap")
        chunks.append(chunk)
    return b"".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--server-cert", required=True)
    parser.add_argument("--server-key", required=True)
    parser.add_argument("--client-ca", required=True)
    parser.add_argument("--channel-key-file", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--seccomp-profile", required=True)
    parser.add_argument("--apparmor-profile", required=True)
    parser.add_argument("--sbom-sha256", required=True)
    args = parser.parse_args()

    key = base64.b64decode(
        Path(args.channel_key_file).read_text(encoding="ascii").strip(),
        validate=True,
    )
    authority = EnvelopeAuthority(
        key,
        ChannelScope(args.run_id, args.condition, args.task_id),
    )
    backend_factory = ApprovedDockerBackendFactory(
        input_manifest_path=args.input_manifest,
        dataset_root=args.dataset_root,
        image=args.image,
        verifier_image=args.verifier_image,
        seccomp_profile=args.seccomp_profile,
        apparmor_profile=args.apparmor_profile,
        sbom_sha256=args.sbom_sha256,
    )
    compute_server = ComputeChannelServer(authority, backend_factory)
    server = ComputeHTTPServer((args.bind, args.port), compute_server)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.server_cert, args.server_key)
    context.load_verify_locations(args.client_ca)
    context.verify_mode = ssl.CERT_REQUIRED
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()