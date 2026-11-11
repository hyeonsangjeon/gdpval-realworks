"""Dispatch-only authentication smoke. Never a paid/model admission receipt.

Reuse the original broker, native observer and pre-session policy guards. The
pending patched-host activation is NOT opened here. Runtime work is hosted-only;
tests inject an inert broker boundary and never invoke the vendor host.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import tempfile
import time

import ghcp_ahp_auth_publication as publication
import ghcp_ahp_management as management
import ghcp_ahp_metadata_broker as broker
import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as policy
import ghcp_ahp_wire_capture as wire
import ghcp_ahp_zero_turn as zero
from ghcp_ahp_diagnostics import DiagnosticRedactor
from ghcp_ahp_errors import Refused

BRANCH = "refs/heads/leader/ghcp-patched-runtime-receipt-20261106"
REPOSITORY = "hyeonsangjeon/gdpval-realworks"
WORKFLOW = REPOSITORY + "/.github/workflows/ghcp-ahp-auth-zero-turn-smoke.yml@" + BRANCH
IDENTITY_KEYS = ("github_run_id", "github_run_attempt", "github_sha")
READ_ONLY_NATIVE = frozenset({"initialize", "initialized", "model/list", "config/read", "configRequirements/read",
    "account/read", "account/rateLimits/read", "mcpServerStatus/list", "skills/list", "plugin/list",
    "permissionProfile/list", "thread/list"})
ZERO_TURN_CATALOG_NATIVE = frozenset({"hooks/list"})
REFUSALS = {"auth_smoke_metadata_refused", "auth_smoke_evidence_refused", "auth_smoke_policy_refused",
    "auth_smoke_runtime_refused", "auth_smoke_child_failed", "auth_smoke_process_timeout",
    "auth_publication_secret_detected", "auth_publication_secret_check_failed"}


def require(condition, reason="auth_smoke_evidence_refused"):
    publication.require(condition, reason)


def same(left, right):
    return publication.encoded(left) == publication.encoded(right)


def is_int(value, expected):
    return type(value) is int and value == expected


def context(*, running):
    identity = probe.require_runner()  # Before credential access, process creation or network.
    require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == BRANCH
            and os.environ.get("GITHUB_WORKFLOW_REF") == WORKFLOW
            and os.environ.get("GITHUB_WORKFLOW_SHA") == identity["github_sha"], "auth_smoke_runtime_refused")
    if running:
        zero.require_context()
        require(os.environ.get("GHCP_AUTH_SMOKE_CONFIRM") == "true", "auth_smoke_runtime_refused")
    return {key: identity[key] for key in IDENTITY_KEYS}


def validate_metadata(value):
    require(value.get("schema") == "ghcp-ahp-metadata-http-v1", "auth_smoke_metadata_refused")
    require(value.get("denials") == [] and value.get("response_bodies_persisted") is False
            and value.get("admission_allowed") is False and is_int(value.get("inference_requests"), 0), "auth_smoke_metadata_refused")
    require(same(value.get("limits"), {"external_metadata_gets": 2, "local_requests": 16,
        "inference_requests": 0, "redirects": 0, "retries": 0}), "auth_smoke_metadata_refused")
    require(type(value.get("cache_hits")) is int and value["cache_hits"] >= 0
            and type(value.get("local_requests")) is int and 2 <= value["local_requests"] <= 16
            and value["local_requests"] == 2 + value["cache_hits"], "auth_smoke_metadata_refused")
    url = value.get("bound_models_url")
    require(type(url) is str and url in broker.MODELS_URLS, "auth_smoke_metadata_refused")
    rows = value.get("external_requests")
    require(type(rows) is list and len(rows) == 2, "auth_smoke_metadata_refused")
    expected = [broker.coordinates(broker.USER_URL), broker.coordinates(url)]
    for row, address in zip(rows, expected, strict=True):
        require(type(row) is dict and row.get("method") == "GET" and row.get("host") == address["host"]
                and row.get("path") == address["path"] and is_int(row.get("status"), 200)
                and row.get("delivery") == "response_received" and "error_diagnostic" not in row,
                "auth_smoke_metadata_refused")
        require(type(row.get("response_bytes")) is int and 0 < row["response_bytes"] <= broker.MAX_BODY
                and re.fullmatch(r"[0-9a-f]{64}", row.get("response_sha256", "")), "auth_smoke_metadata_refused")
    return [{key: row[key] for key in ("method", "host", "path", "status")} for row in rows]


def validate_evidence(payloads, identity):
    """Recompute native evidence; do not trust declared zeroes or request echoes."""
    require(publication.CORE_FILES <= set(payloads))
    values = {name: publication.decode(payloads[name]) for name in publication.CORE_FILES}
    require(all(type(value) is dict for value in values.values()))
    p, h, w, t, m = (values[name] for name in ("probe.json", "handshake.json", "wire-capture.json", "thread-policy.json", "metadata-http.json"))
    require(all(not value.get("patched_ghcp") for value in values.values()), "auth_smoke_runtime_refused")
    require(p.get("schema") == "ghcp-ahp-probe-receipt-v1" and h.get("schema") == "ghcp-ahp-authenticated-zero-turn-v1")
    for value in (p, h):
        require(all(value.get("runner", {}).get(key) == item for key, item in identity.items()))
        require(value.get("status") == "probe_completed" and value.get("reason_codes") == [])
        for field, name in (("thread_policy", "thread-policy.json"), ("wire_capture", "wire-capture.json")):
            require(value.get(field, {}).get("path") == name
                    and value[field].get("sha256") == publication.sha(payloads[name]))
    require(p.get("vscode_commit") == wire.PIN and p.get("codex_sdk_version") == "0.163.0")
    require(all(p.get(key) is True for key in ("authentication_supplied", "headless_started", "authenticated_zero_turn", "session_policy_probe", "metadata_reads")))
    require(all(p.get(key) is False for key in ("credential_environment_inherited", "launch_allowed", "gate_ready")))
    require(is_int(p.get("model_calls"), 0) and is_int(p.get("session_create_requests"), 1))
    require(p.get("cleanup") == "owned_process_group_stopped_pid_namespace_exit_cleans_detached_children")
    require(p.get("backend_readiness", {}).get("ready") is True)
    isolation = p.get("isolation", {})
    require(isolation.get("interfaces") == ["lo"] and all(isolation.get(k) is True for k in ("pid_one", "unprivileged", "no_new_privileges")))
    require(re.fullmatch(r"net:\[[0-9]+\]", isolation.get("network_namespace", ""))
            and re.fullmatch(r"net:\[[0-9]+\]", isolation.get("outside_network_namespace", ""))
            and isolation["network_namespace"] != isolation["outside_network_namespace"]
            and re.fullmatch(r"pid:\[[0-9]+\]", isolation.get("pid_namespace", "")))
    require(isolation.get("external_egress") == "kernel_loopback_only"
            and isolation.get("cleanup_boundary") == "all_descendants_die_when_pid_namespace_init_exits")
    require(h.get("admission_allowed") is False and all(h.get(k) is True for k in ("auth_rpc_sent", "auth_rpc_succeeded", "session_created", "metadata_reads")))
    require(same(h.get("requested_policy"), policy.POLICY) and h.get("requested_native_launch_args") == policy.NATIVE_ARGS)
    require(all(is_int(h.get(k), 0) for k in ("model_turn_start_requests", "model_turn_events", "capi_requests")))
    require(same(h.get("limits"), {"turns": 0, "capi_inference_requests": 0, "metadata_gets": 2,
                                  "sessions": 1, "native_threads": 1, "wall_seconds": 120}))
    require(w.get("schema_version") == "ghcp-ahp-wire-capture-v1" and w.get("synthetic") is False
            and w.get("capture_status") == "captured" and w.get("admission_allowed") is False)
    bootstrap = w.get("bootstrap", {})
    require(bootstrap.get("vscode_commit") == wire.PIN and bootstrap.get("sdk_version") == "0.163.0")
    require(all(bootstrap.get(key) is True for key in ("model_free", "session_policy", "authenticated_zero_turn", "metadata_reads")))
    require(not bootstrap.get("patched_runtime_requested"))
    for key, path in (("observer_sha256", wire.PRELOAD), ("metadata_client_sha256", wire.METADATA_CLIENT),
                      ("management_bridge_sha256", wire.MANAGEMENT_BRIDGE)):
        require(bootstrap.get(key) == probe.digest(path))
    records = w.get("records")
    require(type(records) is list and 1 <= len(records) <= 10000)
    sequences, observers = {}, []
    for row in records:
        require(type(row) is dict and row.get("synthetic") is False)
        process = row.get("process", "")
        require(re.fullmatch(r"wire-[1-9][0-9]*\.jsonl", process))
        require(is_int(row.get("sequence"), sequences.get(process, 0) + 1))
        sequences[process] = row["sequence"]
        kind, value = row.get("kind"), row.get("value", {})
        require(type(kind) is str and not kind.startswith("capi_") and kind not in {"blocked", "wire_parse_error"})
        if kind == "observer_installed" and row.get("entrypoint") == "vs/platform/agentHost/node/agentHostMain":
            require(row.get("model_free") is True and row.get("session_only") is True
                    and row.get("observer_sha256") == bootstrap["observer_sha256"])
            observers.append(row)
        if kind in {"ipc_request", "ipc_response"}:
            require(type(value) is dict)
            method = value.get("method", "")
            require(type(method) is str and not method.startswith(("turn/", "item/")))
            if kind == "ipc_request":
                if method in ZERO_TURN_CATALOG_NATIVE:
                    # The verified observer checked the exact owned path before
                    # redaction. Receipt consumers require its narrow projection,
                    # not a broader arbitrary-cwd/list-method allowance.
                    require(set(value) <= {"id", "method", "params", "jsonrpc"}
                            and ("jsonrpc" not in value or value["jsonrpc"] == "2.0"))
                    request_id = value.get("id")
                    require(type(request_id) is int and 0 <= request_id <= 9007199254740991 or
                            type(request_id) is str and 0 < len(request_id) <= 256)
                    require(same(value.get("params"), {"cwds": ["[REDACTED]"]}))
                    require(same(row.get("params_summary"), {"fields": ["cwds"], "cwd_count": 1,
                                                          "cwd_scope": "owned_probe_workspace"}))
                    require(all(type(row.get(key)) is int and row[key] > 0 for key in ("rpc_sequence", "write_sequence")))
                    require(row.get("trigger") in {"stdin.write", "stdin.end"} and row.get("delivery") == "attempted")
                else:
                    require(method in READ_ONLY_NATIVE | {"thread/start", "thread/unsubscribe", "thread/archive"})
    require(len(observers) == 1 and len(sequences) <= 16)
    recalculated = wire.analyze(records, synthetic=False)
    for key, value in recalculated.items():
        require(same(w.get(key), value))
    require(not recalculated["capture_errors"] and not recalculated["capi_requests"] and not recalculated["capi_response_reports"])
    require(len(recalculated["native_requests"]) == 1 and recalculated["native_requests"][0]["request"].get("method") == "thread/start")
    native = recalculated["native_requests"][0]["request"].get("params", {})
    require(native.get("model") == "gpt-5.6-sol" and native.get("modelProvider") == "vscode-proxy"
            and native.get("approvalPolicy") == "untrusted" and native.get("permissions") == "vscode-workspace-read-only",
            "auth_smoke_policy_refused")
    config = native.get("config", {})
    require(config.get("web_search") == "disabled" and config.get("mcp_servers", {}) == {}, "auth_smoke_policy_refused")
    for key, expected in (("model_context_window", 1000000), ("model_reasoning_effort", "max")):
        require(key not in config or same(config[key], expected), "auth_smoke_policy_refused")
    require("allowProviderModelFallback" not in native or native["allowProviderModelFallback"] is False, "auth_smoke_policy_refused")
    results = h.get("rpc_results")
    require(type(results) is dict and same(results, p.get("rpc_results")))
    require(all(type(results.get(k)) is dict and "result" in results[k] and "error" not in results[k]
                for k in ("authenticate", "createSession", "subscribe", "disposeSession")))
    require(results["createSession"].get("transport") == "vscode-child-ipc")
    readback = results.get("management_initialize", {})
    require(readback.get("evidence") == management.EVIDENCE and readback.get("admission_allowed") is False
            and readback.get("derived_permissions") == "vscode-workspace-read-only"
            and same(readback.get("resolved_policy"), policy.POLICY)
            and same(readback.get("settings", {}).get("model"), probe.DESIRED_MODEL)
            and same(readback.get("settings", {}).get("config"), policy.POLICY))
    sent = h.get("rpc_sent", [])
    require(same(sent, p.get("rpc_sent")) and [row.get("method") for row in sent]
            == [method for method in policy.AUTH_METHODS if method != "createSession"])
    require(sent[1].get("params") == {"channel": probe.ROOT_CHANNEL, "resource": policy.AUTH_RESOURCE, "token": "[REDACTED]"})
    assessment = probe.redact(policy.assess(w, results))
    require(same(t, assessment))
    require(t.get("session_created") is True and is_int(t.get("native_thread_responses"), 1)
            and t.get("safety_violation") is False and t.get("admission_allowed") is False)
    require(same(h.get("observed"), t["observed"]) and same(h.get("verdicts"), t["verdicts"]))
    for key in ("model", "model_provider", "reasoning_effort", "approval", "sandbox", "network"):
        require(same(t["observed"].get(key), policy.EXPECTED[key]), "auth_smoke_policy_refused")
    metadata = validate_metadata(m)
    responses = [row for row in recalculated["metadata_http"] if row["kind"] == "metadata_response"]
    require(2 <= len(responses) <= 16 and all(is_int(row.get("status"), 200) and type(row.get("external_request")) is bool for row in responses), "auth_smoke_metadata_refused")
    external = [{key: row.get(key) for key in ("method", "host", "path", "status")} for row in responses if row["external_request"]]
    require(same(external, metadata), "auth_smoke_metadata_refused")
    return {"authentication_transport_verified": True, "metadata_requests": metadata,
        "sessions_created": 1, "native_threads_created": 1, "turns_sent": 0, "capi_inference_requests": 0,
        "observed": t["observed"], "verdicts": t["verdicts"], "capi_count_scope": "inference_only_metadata_gets_separate"}


def run_broker(prepared, evidence, credential):
    context(running=True)
    environment = {name: os.environ[name] for name in ("GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
        "GITHUB_SHA", "RUNNER_ENVIRONMENT", "RUNNER_NAME", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion",
        "GHCP_AUTHENTICATED_ZERO_TURN", "GHCP_PAID_EXECUTION", "GHCP_CONNECTION_ONLY") if name in os.environ}
    environment.update(PATH="/usr/bin:/bin", LANG="C.UTF-8", COPILOT_GITHUB_TOKEN=credential)
    command = [sys.executable, "-B", str(Path(broker.__file__).resolve()), "--prepared", str(prepared), "--evidence", str(evidence)]
    process = probe.CapturedProcess(command, environment)
    try:
        deadline = time.monotonic() + 165
        while process.process.poll() is None:
            process.check()
            require(time.monotonic() < deadline, "auth_smoke_process_timeout")
            time.sleep(0.02)
        process.check()
    finally:
        process.stop()
    return process.record()


def receipt(identity, status, reason, details=None):
    return {"schema": "ghcp-auth-zero-turn-smoke-v1", "runner": identity, "status": status, "reason_code": reason,
        "synthetic": False, "runtime_variant": "original_pinned_host", "vscode_commit": wire.PIN,
        "patched_ghcp": False, "execution_allowed": False, "admission_allowed": False, "launch_allowed": False,
        "authentication_transport_verified": False, "sessions_created": "not_reported", "native_threads_created": "not_reported",
        "turns_sent": "not_reported", "capi_inference_requests": "not_reported", **(details or {})}


def markdown(report):
    return ("# Authentication-only zero-turn smoke\n\n"
            f"Status: {report['status']}\n\nReason: {report['reason_code']}\n\n"
            "Diagnostic only; not served-model proof or paid admission.\n\n"
            f"Sessions: {report['sessions_created']}; native threads: {report['native_threads_created']}; "
            f"turns: {report['turns_sent']}; CAPI inference: {report['capi_inference_requests']}.\n\n"
            "execution_allowed=false; admission_allowed=false; patched_ghcp=false.\n").encode()


def execute(prepared, preparation, output, credential, identity, *, runner=run_broker):
    """Inject only the broker boundary in unit tests; production has no fake mode."""
    zero.validate_credential(credential)
    prepared, preparation, output = map(publication.safe_path, (prepared, preparation, output))
    require(prepared.is_dir() and preparation.is_dir() and not output.exists())
    scanner = publication.LeakScanner(credential)
    payloads, logs = {}, {"exit_code": None, "stdout": "", "stderr": ""}
    report = receipt(identity, "refused", "auth_smoke_evidence_refused")
    with tempfile.TemporaryDirectory(prefix="ghcp-auth-private-") as temporary:
        evidence = Path(temporary)
        try:
            for name in ("prepared.json", "source-evidence.json"):
                raw = publication.read(preparation / name)
                with (evidence / name).open("xb") as stream:
                    stream.write(raw)  # Public pin metadata only; never a token file.
            logs = runner(prepared, evidence, credential)
            require(type(logs) is dict)
            logs = {key: logs.get(key) for key in ("exit_code", "stdout", "stderr")}
            logs = DiagnosticRedactor(credential).clean(logs)
            require(is_int(logs.get("exit_code"), 0), "auth_smoke_child_failed")
            payloads = {name: publication.read(evidence / name) for name in publication.CORE_FILES}
            for name, raw in payloads.items():
                scanner.check(name, raw)  # Existing exporters must already have masked them.
            details = validate_evidence(payloads, identity)
            report = receipt(identity, "success", "metadata_and_native_thread_verified", details)
        except Exception as error:
            code = str(error) if isinstance(error, Refused) and str(error) in REFUSALS else "auth_smoke_evidence_refused"
            report = receipt(identity, "refused", code)
            # Never publish unvalidated original artifacts on a failure.
            payloads = {}
    logs = DiagnosticRedactor(credential).clean(logs)
    payloads.update({"auth-smoke.json": publication.encoded(report), "auth-smoke.md": markdown(report),
                     "process-log.json": publication.encoded(logs)})
    try:
        scan_sha = publication.publish(output, payloads, credential, identity)
    except Refused:
        # A redactor fault cannot turn a leak into success; discard all logs/evidence.
        require(not output.exists())
        report = receipt(identity, "refused", "auth_publication_secret_check_failed")
        scan_sha = publication.publish(output, {"auth-smoke.json": publication.encoded(report), "auth-smoke.md": markdown(report),
            "process-log.json": publication.encoded({"status": "withheld_after_independent_scan_failure"})}, credential, identity)
    return (0 if report["status"] == "success" else 2), scan_sha


def verify_publication(directory, expected_sha, identity):
    payloads = publication.verify(directory, expected_sha, identity)
    report = publication.decode(payloads["auth-smoke.json"])
    require(report.get("schema") == "ghcp-auth-zero-turn-smoke-v1" and report.get("runner") == identity)
    require(all(report.get(key) is False for key in ("synthetic", "patched_ghcp", "execution_allowed", "admission_allowed", "launch_allowed")))
    require(payloads["auth-smoke.md"] == markdown(report))
    if report.get("status") == "success":
        require(same(report, receipt(identity, "success", "metadata_and_native_thread_verified", validate_evidence(payloads, identity))))
    else:
        require(report.get("status") == "refused" and report.get("reason_code") in REFUSALS
                and same(report, receipt(identity, "refused", report["reason_code"])) and not set(payloads) & publication.CORE_FILES)
    return report


def output_digest(scan_sha):
    # Only a public digest, never any secret, is handed to the secret-free step.
    require(re.fullmatch(r"[0-9a-f]{64}", scan_sha))
    path = publication.safe_path(os.environ["GITHUB_OUTPUT"])
    root = publication.safe_path(os.environ["RUNNER_TEMP"])
    require(path.is_relative_to(root) and path.is_file())
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW), "w") as stream:
        stream.write("scan_sha256=" + scan_sha + "\n")


def main(argv=None):
    parser = probe.SafeArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "verify"))
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--published", type=Path, required=True)
    parser.add_argument("--scan-sha256")
    try:
        args = parser.parse_args(argv)
        identity = context(running=args.mode == "run")
        if args.mode == "verify":
            verify_publication(args.published, args.scan_sha256, identity)
            return 0
        require(args.prepared is not None and args.preparation is not None and args.scan_sha256 is None)
        credential = os.environ.pop("COPILOT_GITHUB_TOKEN", "")
        code, scan_sha = execute(args.prepared, args.preparation, args.published, credential, identity)
        output_digest(scan_sha)
        return code
    except Exception:
        # No argparse text, exception, partial child log or environment can escape.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
