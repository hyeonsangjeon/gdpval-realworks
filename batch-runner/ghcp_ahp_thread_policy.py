"""One exact Codex session request, zero turns/provider HTTP, observer-only assessment.

This is not the paid connection gate. Resolver echoes, requested model settings
and process-wide config/read results never count as thread-applied evidence.
"""

from __future__ import annotations

import copy
import json
import time
import uuid

from ghcp_ahp_probe import DESIRED_MODEL, ROOT_CHANNEL, Refused, digest, save_json, strict_json, validate_request

POLICY = {"codex.approvalPolicy": "untrusted", "codex.sandboxMode": "read-only",
          "codex.networkAccessEnabled": False, "codex.webSearchMode": "disabled",
          "codex.modelReasoningEffort": "max"}
# Supported native launch configuration, not aliases for AHP session keys.
# Pinned Config.ts:28,33 and codexAgent.ts:2682 -> buildCodexLaunchConfig.
NATIVE_ARGS = ["-c", 'model="gpt-5.6-sol"', "-c", 'model_provider="vscode-proxy"',
               "-c", 'model_reasoning_effort="max"', "-c", "model_context_window=1000000"]
EXPECTED = {"model": "gpt-5.6-sol", "model_provider": "vscode-proxy", "reasoning_effort": "max", "context_window": 1_000_000,
            "approval": "untrusted", "sandbox": "readOnly", "network": False,
            "web_search": "disabled", "served_model": "gpt-5.6-sol"}
NOT_REPORTED = "not_reported"
WAIT_SECONDS = 10
METHODS = ("initialize", "resolveSessionConfig", "createSession", "subscribe", "disposeSession")
AUTH_METHODS = ("initialize", "authenticate", *METHODS[1:])
AUTH_RESOURCE = "https://api.github.com"


def same(left, right):
    # JSON's distinct bool/int/string encodings prevent false == 0 acceptance.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def validate(method, params, rpc):
    credential = getattr(rpc, "credential", "")
    methods = AUTH_METHODS if credential else METHODS
    managed = getattr(rpc, "management", None) is not None
    if managed:
        methods = tuple(item for item in methods if item != "createSession")
    if len(rpc.sent) >= len(methods) or method != methods[len(rpc.sent)]:
        raise Refused("session_policy_rpc_order_refused")
    if type(params) is not dict:
        raise Refused("session_policy_rpc_shape_refused")
    base = dict(params)
    if method == "authenticate":
        if not same(params, {"channel": ROOT_CHANNEL, "resource": AUTH_RESOURCE, "token": credential}):
            raise Refused("zero_turn_auth_rpc_refused")
        return
    if method in {"resolveSessionConfig", "createSession"}:
        if not same(base.pop("config", None), POLICY):
            raise Refused("session_policy_config_refused")
    # CreateSessionParams has no model field. Never send an ignored/guessed
    # AHP key; hosted probes use explicit local management plus native launch config.
    validate_request(method, base, rpc.session, rpc.workspace)
    if method in {"subscribe", "disposeSession"}:
        creation = ([getattr(rpc, "policy_results", {}).get("createSession", {})] if managed else
                    [row for row in rpc.received if row.get("id") == methods.index("createSession") + 1])
        if len(creation) != 1 or "result" not in creation[0]:
            raise Refused("session_policy_creation_not_confirmed")
    if credential and method not in {"initialize", "authenticate"}:
        authenticated = [row for row in rpc.received if row.get("id") == 2]
        if len(authenticated) != 1 or "result" not in authenticated[0]:
            raise Refused("zero_turn_auth_not_confirmed")


def exercise(rpc, observe=None):
    results = {}
    rpc.policy_results = results
    results["initialize"] = rpc.request("initialize", {"channel": ROOT_CHANNEL,
        "protocolVersions": ["1.1.0", "1.0.0"], "clientId": str(uuid.uuid4()),
        "clientInfo": {"name": "ghcp-ahp-model-free-probe", "version": "1"},
        "initialSubscriptions": [ROOT_CHANNEL], "locale": "en-US"})
    initialized = results["initialize"].get("result")
    if not isinstance(initialized, dict) or initialized.get("protocolVersion") not in {"1.1.0", "1.0.0"}:
        return results
    if getattr(rpc, "require_mcp_disabled", False):
        roots = [s for s in initialized.get("snapshots", []) if s.get("resource") == ROOT_CHANNEL]
        if len(roots) != 1 or roots[0].get("state", {}).get("config", {}).get("values", {}).get("githubMcpServerEnabled") is not False:
            raise Refused("metadata_mcp_disabled_not_reported")
    if getattr(rpc, "credential", ""):
        roots = [s for s in initialized.get("snapshots", []) if s.get("resource") == ROOT_CHANNEL]
        agents = [a for s in roots for a in s.get("state", {}).get("agents", []) if a.get("provider") == "codex"]
        if len(agents) != 1 or AUTH_RESOURCE not in {r.get("resource") for r in agents[0].get("protectedResources", [])}:
            raise Refused("zero_turn_auth_resource_refused")
        results["authenticate"] = rpc.request("authenticate", {"channel": ROOT_CHANNEL,
            "resource": AUTH_RESOURCE, "token": rpc.credential})
        if "error" in results["authenticate"]:
            return results
    results["resolveSessionConfig"] = rpc.request("resolveSessionConfig", {"channel": ROOT_CHANNEL,
        "provider": "codex", "workingDirectory": rpc.workspace, "config": copy.deepcopy(POLICY)})
    resolved_result = results["resolveSessionConfig"].get("result")
    resolved = resolved_result.get("values", {}) if isinstance(resolved_result, dict) else {}
    if not isinstance(resolved, dict) or any(not same(resolved.get(key), value) for key, value in POLICY.items()):
        raise Refused("session_policy_resolver_changed_request")
    # Keep only our five source-defined keys. Do not copy a preset, an unknown
    # key, or a server default back into the creation request.
    management = getattr(rpc, "management", None)
    if management is None:
        # Retained generic AHP-only helper. The hosted session-policy entrypoint
        # ALWAYS supplies its local bridge; bridge failures never fall back here.
        results["createSession"] = rpc.request("createSession", {"channel": rpc.session, "provider": "codex",
            "workingDirectories": [rpc.workspace], "config": copy.deepcopy(POLICY)})
    else:
        results["management_initialize"] = management.prepare(rpc.session, rpc.workspace, POLICY)
        results["createSession"] = management.create()
    if "error" not in results["createSession"]:
        results["subscribe"] = rpc.request("subscribe", {"channel": rpc.session})
        try:
            if observe is not None:
                results["native_wait"] = observe()
        finally:
            results["disposeSession"] = rpc.request("disposeSession", {"channel": rpc.session})
    return results


def await_native_thread(state, deadline):
    """Observe prewarm only. Never send a turn to force materialization."""
    end = min(deadline, time.monotonic() + WAIT_SECONDS)
    while True:
        rows, total = [], 0
        files = sorted((state / "wire").glob("wire-*.jsonl"))
        if len(files) > 16:
            raise Refused("session_policy_observer_file_limit")
        for file in files:
            if file.is_symlink():
                raise Refused("session_policy_observer_path_refused")
            total += file.stat().st_size
            if total > 16 * 1024 * 1024:
                raise Refused("session_policy_observer_size_limit")
            # A writer may have an incomplete final line. Only complete JSONL
            # records are evidence; final export still validates all sequences.
            for line in file.read_text().splitlines(keepends=True):
                if line.endswith("\n"):
                    rows.append({**strict_json(line), "process": file.name})
        if any(row.get("kind") == "blocked" for row in rows):
            raise Refused("session_policy_forbidden_activity")
        starts = {(row.get("process"), row.get("stream"), row.get("value", {}).get("id")) for row in rows
                  if row.get("kind") == "ipc_request" and row.get("value", {}).get("method") == "thread/start"}
        replies = [row for row in rows if row.get("kind") == "ipc_response"
                   and (row.get("process"), row.get("stream"), row.get("value", {}).get("id")) in starts]
        if replies:
            return {"status": "native_thread_reply_observed", "replies": len(replies)}
        if time.monotonic() >= end:
            return {"status": "native_thread_not_reported_before_deadline", "replies": 0}
        time.sleep(0.05)


def matches_all(observed):
    return set(observed) == set(EXPECTED) and all(same(observed[key], value) for key, value in EXPECTED.items())


def assess(capture, results):
    observed = dict.fromkeys(EXPECTED, NOT_REPORTED)
    origins = dict.fromkeys(EXPECTED, NOT_REPORTED)
    starts = [row for row in capture.get("native_applied_snapshots", []) if row.get("source") == "native.thread/start.result"]
    reasons = []
    if len(starts) == 1 and isinstance(starts[0].get("thread_id"), str) and starts[0]["thread_id"] not in {"", NOT_REPORTED}:
        thread = starts[0].get("thread_id")
        updates = [row for row in capture.get("native_applied_snapshots", []) if row.get("thread_id") == thread]
        report = updates[-1]
        for key in ("model", "model_provider", "reasoning_effort", "approval", "sandbox", "network"):
            observed[key] = report.get("values", {}).get(key, NOT_REPORTED)
            origins[key] = report.get("source", NOT_REPORTED)
        contexts = [row for row in capture.get("native_context_reports", []) if row.get("thread_id") == thread]
        if contexts:
            observed["context_window"] = contexts[-1].get("context_window", NOT_REPORTED)
            origins["context_window"] = contexts[-1].get("source", NOT_REPORTED)
    else:
        reasons.append("exactly_one_native_thread_response_required")
    # Pinned ThreadStartResponse/ThreadSettings have no applied web-search field.
    # Native model is a configured model, not an upstream served-model report.
    # config/read is process/disk scope and cannot fill either of these gaps.
    reasons.extend("unreported_or_mismatched:" + key for key in EXPECTED if not same(observed[key], EXPECTED[key]))
    native = capture.get("native_requests", [])
    turn_requests = sum(row.get("request", {}).get("method") == "turn/start" for row in native)
    turn_events = sum(str(row.get("value", {}).get("method", "")).startswith("turn/")
                      for row in capture.get("records", []) if row.get("kind") == "ipc_response")
    forbidden = any(row.get("request", {}).get("method") != "thread/start" for row in native)
    safety_violation = bool(forbidden or turn_events or len(native) > 1 or capture.get("capture_errors")
                            or capture.get("capi_requests") or capture.get("capi_response_reports"))
    live = (capture.get("synthetic") is False and capture.get("capture_status") == "captured"
            and capture.get("bootstrap", {}).get("session_policy") is True
            and any(row.get("kind") == "observer_installed" and row.get("model_free") is True
                    and row.get("session_only") is True and row.get("entrypoint") == "vs/platform/agentHost/node/agentHostMain"
                    for row in capture.get("records", [])))
    creation = results.get("createSession", {})
    created = "result" in creation and "error" not in creation
    return {"schema": "ghcp-ahp-thread-policy-v1", "requested_policy": copy.deepcopy(POLICY),
            "requested_model": copy.deepcopy(DESIRED_MODEL), "requested_native_launch_args": list(NATIVE_ARGS),
            "observed": observed, "origins": origins,
            "verdicts": {key: "matches" if same(observed[key], EXPECTED[key]) else
                         "not_reported" if observed[key] == NOT_REPORTED else "mismatch" for key in EXPECTED},
            "session_created": created, "session_error": creation.get("error"),
            "management_initialize": results.get("management_initialize"),
            "creation_transport": creation.get("transport", "ahp-websocket"),
            "native_thread_responses": len(starts), "native_wait": results.get("native_wait"),
            "synthetic": capture.get("synthetic", True), "safety_violation": safety_violation,
            "admission_allowed": created and live and not safety_violation and matches_all(observed),
            "reasons": reasons, "model_turn_start_requests": turn_requests, "model_turn_events": turn_events,
            "capi_requests": len(capture.get("capi_requests", [])),
            "metadata_http": capture.get("metadata_http", []), "capi_count_scope": "inference_only_metadata_gets_separate",
            "evidence_boundary": "requested_vs_native_thread_report_vs_served_model_kept_separate",
            "limits": {"ahp_sessions": 1, "native_threads": 1, "turns": 0, "capi_inference_requests": 0,
                       "metadata_gets": 2 if capture.get("bootstrap", {}).get("metadata_reads") else 0},
            "limitations": ["resolver_echo_is_not_applied", "process_config_is_not_thread_config",
                            "thread_model_is_not_served_model", "initial_effort_is_not_final_turn_effort",
                            "sdk_context_is_not_provider_capacity", "unreported_web_search_refuses_admission"]}


def export(evidence, results):
    capture = strict_json((evidence / "wire-capture.json").read_text())
    report = assess(capture, results)
    provenance = None
    if capture.get("patched_ghcp") is True:
        import ghcp_ahp_patched_runtime as patched
        provenance = patched.validate_provenance(capture)
        report = patched.stamp(report, provenance)
    target = evidence / "thread-policy.json"
    save_json(target, report)
    if "management_initialize" in results:
        management = results["management_initialize"]
        if provenance is not None:
            management = patched.stamp(management, provenance)
        save_json(evidence / "management-init.json", management)
    return {"path": target.name, "sha256": digest(target), "admission_allowed": report["admission_allowed"],
            "session_created": report["session_created"], "native_thread_responses": report["native_thread_responses"],
            "safety_violation": report["safety_violation"]}
