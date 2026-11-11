"""Two bounded metadata GETs outside an otherwise zero-egress Agent Host.

No inference URL, token mint, proxy, redirect, retry, arbitrary host or body is
supported. Full response bodies and credentials stay in memory. The audit keeps
only selected, redacted error fields and the presence of diagnostic headers.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

from ghcp_ahp_errors import Refused
from ghcp_ahp_probe import require_runner, save_json, strict_json
from ghcp_ahp_zero_turn import require_context, validate_credential

USER_URL = "https://api.github.com/copilot_internal/user"
# Literal names only. Only the ONE origin returned by authenticated discovery
# can become active; this set is not a wildcard or a fallback host search.
CAPI_ORIGINS = frozenset({"https://api.githubcopilot.com", "https://api.individual.githubcopilot.com",
                          "https://api.business.githubcopilot.com", "https://api.enterprise.githubcopilot.com"})
MODELS_URLS = frozenset(origin + "/models" for origin in CAPI_ORIGINS)
MAX_BODY = 2 * 1024 * 1024
USER_AGENT = "gdpval-ghcp-ahp-metadata/1.0"
DIAGNOSTIC_HEADERS = ("x-accepted-github-permissions", "x-github-sso", "x-oauth-scopes", "x-accepted-oauth-scopes")
HEADERS = frozenset({"authorization", "accept", "content-type", "user-agent", "x-github-api-version", "editor-version",
    "editor-plugin-version", "copilot-integration-id", "openai-intent", "x-request-id", "vscode-sessionid",
    "vscode-machineid", "x-vscode-user-agent", "x-interaction-id", "x-initiator", "editor-device-id", "request-hmac"})


def coordinates(url):
    """For audit only; query, userinfo, fragment and header values never logged."""
    try:
        value = urlsplit(url)
        return {"host": value.hostname, "path": value.path}
    except (TypeError, ValueError):
        return {"host": "not_reported", "path": "not_reported"}


def validate_request(message):
    if not isinstance(message, dict) or set(message) != {"method", "url", "headers"}:
        raise Refused("metadata_shape_refused")
    if message["method"] != "GET" or type(message["url"]) is not str:
        raise Refused("metadata_method_refused")
    if message["url"] not in {USER_URL, *MODELS_URLS}:
        raise Refused("metadata_url_refused")
    headers = message["headers"]
    if (type(headers) is not dict or not set(headers) <= HEADERS or "authorization" not in headers
            or any(type(v) is not str or len(v) > 16384 or any(ord(c) < 32 or ord(c) > 126 for c in v)
                   for v in headers.values())):
        raise Refused("metadata_headers_refused")


def https_get(url, headers):
    # http.client does not follow redirects, consult proxy variables, use netrc,
    # retry, or load a cookie jar. Certificate/hostname checks remain enabled.
    address = urlsplit(url)
    connection = http.client.HTTPSConnection(address.hostname, 443, timeout=10, context=ssl.create_default_context())
    try:
        # Native fetch supplies a default UA; http.client does not. GitHub
        # requires one. Preserve all explicit client headers, including UA.
        connection.request("GET", address.path, headers={"user-agent": USER_AGENT, **headers})
        response = connection.getresponse()
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise Refused("metadata_response_limit")
        return response.status, {"content-type": response.getheader("content-type", "application/json"),
            "diagnostic_header_presence": {name: response.getheader(name) is not None for name in DIAGNOSTIC_HEADERS}}, body
    finally:
        connection.close()


def error_diagnostic(headers, body, credential):
    """No full body, SSO URL, scopes, account identifier or credential export."""
    from ghcp_ahp_diagnostics import DiagnosticRedactor
    payload = {}
    try:
        value = strict_json(body.decode("utf-8"))
        if isinstance(value, dict):
            # Learn private identifiers from the whole envelope before selecting
            # fields, and redact BEFORE truncation so no partial token escapes.
            payload = DiagnosticRedactor(credential).clean(value)
    except (ValueError, UnicodeError, RecursionError, Refused):
        pass  # An unreadable diagnostic must not replace the original HTTP status.
    message = payload.get("message")
    documentation = payload.get("documentation_url")
    try:
        url = urlsplit(documentation) if type(documentation) is str else None
        if (url is None or url.scheme != "https" or url.netloc != "docs.github.com" or url.query
                or len(documentation) > 2048 or "[REDACTED]" in documentation
                or any(ord(char) < 33 or ord(char) > 126 for char in documentation)):
            documentation = "not_reported"
    except ValueError:
        documentation = "not_reported"
    presence = headers.get("diagnostic_header_presence", {})
    presence = presence if isinstance(presence, dict) else {}
    return {"message": message[:1024] if type(message) is str else "not_reported",
            "documentation_url": documentation,
            "header_presence": {name: presence[name] if type(presence.get(name)) is bool else "not_reported"
                                for name in DIAGNOSTIC_HEADERS}}


class Broker:
    def __init__(self, credential, fetch=https_get, *, clock=time.monotonic):
        validate_credential(credential)
        self.credential, self.fetch, self.clock = credential, fetch, clock
        self.deadline = clock() + 120
        self.lock = threading.Lock()
        self.cache, self.models_url = {}, None
        self.requests, self.denials = [], []
        self.failed = False
        self.cache_hits = 0
        self.local_requests = 0

    def request(self, message):
        with self.lock:
            try:
                self.local_requests += 1
                if self.local_requests > 16:
                    raise Refused("metadata_local_request_limit")
                validate_request(message)
                if self.failed or self.clock() >= self.deadline:
                    raise Refused("metadata_closed")
                if not hmac.compare_digest(message["headers"]["authorization"], "Bearer " + self.credential):
                    raise Refused("metadata_credential_mismatch")
                url = message["url"]
                if url != USER_URL and url != self.models_url:
                    raise Refused("metadata_catalog_not_bound_to_discovery")
                # Cache only byte-identical transport semantics (request IDs are
                # tracing only). No second network request, including failures.
                semantic = {k: v for k, v in message["headers"].items() if k not in {"x-request-id", "x-interaction-id"}}
                if url in self.cache:
                    cached_headers, result = self.cache[url]
                    if semantic != cached_headers:
                        raise Refused("metadata_cached_headers_changed")
                    self.cache_hits += 1
                    return {**result, "external_request": False}
                if len(self.requests) >= 2:
                    raise Refused("metadata_request_limit")
                row = {"method": "GET", **coordinates(url), "status": None, "delivery": "attempted"}
                self.requests.append(row)  # Reserve before DNS/TLS/HTTP I/O.
                status, headers, body = self.fetch(url, message["headers"])
                if type(status) is not int or not 100 <= status <= 599 or type(body) is not bytes or len(body) > MAX_BODY:
                    raise Refused("metadata_response_invalid")
                row.update(status=status, delivery="response_received", response_bytes=len(body), response_sha256=hashlib.sha256(body).hexdigest())
                if status != 200:
                    self.failed = True
                    row["error_diagnostic"] = error_diagnostic(headers, body, self.credential)
                if url == USER_URL and status == 200:
                    payload = strict_json(body.decode("utf-8"))
                    origin = payload.get("endpoints", {}).get("api")
                    if origin not in CAPI_ORIGINS:
                        raise Refused("metadata_discovered_origin_refused")
                    self.models_url = origin + "/models"
                result = {"status": status, "headers": {"content-type": headers.get("content-type", "application/json")},
                          "body_base64": base64.b64encode(body).decode(), "external_request": True}
                self.cache[url] = semantic, result
                return result
            except Exception as error:
                self.failed = True
                reason = str(error) if isinstance(error, Refused) else "metadata_transport_failed"
                denied_headers = sorted(set(message.get("headers", {})) - HEADERS) if isinstance(message, dict) and isinstance(message.get("headers"), dict) else []
                self.denials.append({"reason": reason, "refused_header_names": denied_headers,
                                     "method": "GET" if isinstance(message, dict) and message.get("method") == "GET" else "refused",
                                     **(coordinates(message.get("url")) if isinstance(message, dict) else {"host": "not_reported", "path": "not_reported"})})
                return {"error": reason}

    def receipt(self):
        from ghcp_ahp_diagnostics import DiagnosticRedactor
        return DiagnosticRedactor(self.credential).clean({"schema": "ghcp-ahp-metadata-http-v1",
            "external_requests": self.requests, "denials": self.denials, "cache_hits": self.cache_hits, "local_requests": self.local_requests,
            "bound_models_url": self.models_url, "inference_requests": 0, "admission_allowed": False,
            "limits": {"external_metadata_gets": 2, "local_requests": 16, "inference_requests": 0, "redirects": 0, "retries": 0},
            "response_bodies_persisted": False})


class Handler(socketserver.StreamRequestHandler):
    def refuse_local(self, reason):
        with self.server.broker.lock:
            self.server.broker.failed = True
            self.server.broker.denials.append({"reason": reason})

    def handle(self):
        self.connection.settimeout(15)
        peer = struct.unpack("3i", self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if peer[1] != os.getuid():
            return
        try:
            raw = self.rfile.readline(65537)
            if not raw:
                self.refuse_local("metadata_local_disconnected")
                return  # Cancellation/EOF is not a malformed request to reply to.
            if len(raw) > 65536 or not raw.endswith(b"\n"):
                raise Refused("metadata_local_frame_refused")
            result = self.server.broker.request(strict_json(raw.decode()))
        except (BrokenPipeError, ConnectionResetError):
            self.refuse_local("metadata_local_disconnected")
            return
        except Exception:
            self.refuse_local("metadata_local_frame_refused")
            result = {"error": "metadata_local_frame_refused"}
        try:
            self.wfile.write(json.dumps(result, separators=(",", ":")).encode() + b"\n")
        except (BrokenPipeError, ConnectionResetError):
            # Preserve the original HTTP receipt; never retry the write or fetch.
            self.refuse_local("metadata_local_disconnected")


class Server(socketserver.UnixStreamServer):
    request_queue_size = 8


def isolation_prefix(preserved=()):
    """The identical kernel/privilege boundary for preparation and the host."""
    return ["sudo", *(["--preserve-env=" + ",".join(preserved)] if preserved else []),
        "unshare", "--mount", "--net", "--pid", "--fork", "--mount-proc", "--kill-child=KILL",
        "/bin/bash", "-c", 'set -euo pipefail; ip link set lo up; exec "$@"', "metadata-isolation",
        "/usr/bin/setpriv", "--reuid=" + str(os.getuid()), "--regid=" + str(os.getgid()), "--init-groups",
        "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs"]


def isolated_command(prepared, evidence, socket_path, *, prewarm_preparation=None, admission_profile=None):
    if admission_profile is not None and (admission_profile != "default_policy_unpatched" or prewarm_preparation is not None):
        raise Refused("default_policy_mode_refused")
    preserved = ["COPILOT_GITHUB_TOKEN", "GHCP_AUTHENTICATED_ZERO_TURN", "GHCP_PAID_EXECUTION", "GHCP_CONNECTION_ONLY",
        "GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "RUNNER_ENVIRONMENT",
        "RUNNER_NAME", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion"]
    if prewarm_preparation is not None or admission_profile is not None:
        preserved.extend(["GITHUB_REF", "GITHUB_REPOSITORY", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA"])
    environment = {key: os.environ[key] for key in preserved if key in os.environ}
    environment.update(PATH="/usr/bin:/bin", LANG="C.UTF-8")
    command = [*isolation_prefix(preserved),
        sys.executable, "-B", str(Path(__file__).with_name("ghcp_ahp_probe.py")), "probe",
        "--prepared", str(prepared), "--evidence", str(evidence),
        "--outside-netns", os.readlink("/proc/self/ns/net"), "--outside-pidns", os.readlink("/proc/self/ns/pid"),
        "--authenticated-zero-turn", "--metadata-socket", str(socket_path)]
    if prewarm_preparation is not None:
        command.extend(["--prewarm-zero-turn-preparation", str(prewarm_preparation)])
    if admission_profile is not None:
        command.extend(["--admission-profile", admission_profile])
    return command, environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--prewarm-zero-turn-preparation", type=Path)
    parser.add_argument("--runner-userns-receipt", type=Path)
    parser.add_argument("--admission-profile", choices=("default_policy_unpatched",))
    args = parser.parse_args(argv)
    broker = child = None
    handlers = {}
    try:
        require_runner()  # Before credential/file/process/network access; NAS refused.
        require_context()
        if args.admission_profile is not None:
            if args.prewarm_zero_turn_preparation is not None:
                raise Refused("default_policy_mode_refused")
            import ghcp_ahp_default_policy as default
            identity = default.require_context(args.evidence)
            import ghcp_ahp_runner_userns as userns
            userns.verify_for_auth(args.runner_userns_receipt, args.prepared, args.evidence, identity)
        elif args.prewarm_zero_turn_preparation is not None:
            import ghcp_ahp_prewarm_zero_turn as prewarm
            identity = prewarm.context(running=True)
            prewarm.verify_preparation(args.prewarm_zero_turn_preparation, args.prepared, args.evidence, identity)
            import ghcp_ahp_runner_userns as userns
            userns.verify_for_auth(args.runner_userns_receipt, args.prepared, args.evidence, identity)
        elif args.runner_userns_receipt is not None:
            raise Refused("runner_userns_requires_prewarm_zero_turn")
        credential = os.environ.get("COPILOT_GITHUB_TOKEN", "")
        validate_credential(credential)
        def cancel(signum, frame):
            raise Refused("metadata_execution_cancelled")
        for signum in (signal.SIGTERM, signal.SIGINT):
            handlers[signum] = signal.signal(signum, cancel)
        broker = Broker(credential)
        with tempfile.TemporaryDirectory(prefix="ahp-metadata-") as temporary:
            socket_path = Path(temporary) / "broker.sock"
            with Server(str(socket_path), Handler) as server:
                os.chmod(socket_path, 0o600)
                server.broker = broker
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    options = ({"prewarm_preparation": args.prewarm_zero_turn_preparation}
                               if args.prewarm_zero_turn_preparation is not None else {})
                    if args.admission_profile is not None:
                        options["admission_profile"] = args.admission_profile
                    command, environment = isolated_command(args.prepared, args.evidence, socket_path, **options)
                    child = subprocess.Popen(command, env=environment, start_new_session=True)
                    code = child.wait(timeout=135)
                finally:
                    if child is not None and child.poll() is None:
                        os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait(timeout=3)
                    server.shutdown()
                    worker.join(timeout=5)
        return code if code else 2 if broker.failed else 0
    except Exception as error:
        print(json.dumps({"status": "metadata_refused", "reason": str(error) if isinstance(error, Refused) else type(error).__name__, "inference_requests": 0}))
        return 2
    finally:
        if broker is not None:
            receipt = broker.receipt()
            if args.admission_profile is not None:
                receipt.update(admission_profile=args.admission_profile, execution_allowed=False, patched_ghcp=False)
            save_json(args.evidence / "metadata-http.json", receipt)
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
