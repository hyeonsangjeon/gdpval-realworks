"""Choice 3: separate, unpatched default-policy ZERO-TURN admission only.

No permission setting is supplied to the host. Native defaults are observed,
not relabeled as read-only. This profile never authorizes a model/paid turn.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import posixpath
import re
import tarfile
import uuid

import ghcp_ahp_thread_policy as original
import ghcp_ahp_zero_turn_admission as read_only
from ghcp_ahp_probe import DESIRED_MODEL, Refused, digest, save_json, strict_json

PROFILE = "default_policy_unpatched"
SCOPE = "default_policy_unpatched_zero_turn_only"
POLICY = {}  # No preset, approval, sandbox, network or web override is sent.
NATIVE_ARGS = original.NATIVE_ARGS
EXPECTED = {"model": "gpt-5.6-sol", "model_provider": "vscode-proxy", "reasoning_effort": "max",
            "approval": "on-request", "sandbox": "workspaceWrite", "network": False,
            "permission_profile": "vscode-workspace"}
RESOLVER_DEFAULTS = {"codex.permissionsPreset": "default", "codex.approvalPolicy": "on-request",
    "codex.sandboxMode": "workspace-write", "codex.networkAccessEnabled": False,
    "codex.webSearchMode": "disabled", "codex.modelReasoningEffort": "medium"}
POLICY_FILE = "default-policy-unpatched.json"
HANDSHAKE_FILE = "default-policy-unpatched-handshake.json"
SUMMARY_FILE = "default-policy-unpatched-summary.json"
SUMMARY_MD = "default-policy-unpatched-summary.md"
LOADER = Path(__file__).with_suffix(".cjs")
RELATIVE = "out/vs/platform/agentHost/node/agentHostMain.js"
ENTRYPOINT = "vs/platform/agentHost/node/agentHostMain"
# Measured from the unchanged, SHA-verified 65a713d9... vendor server archive.
UNPATCHED_BUNDLE_SHA256 = "bf1c335134a145a8c2af6e00975c3320ef1ad21f542f6c07fdf1361e3cf94780"
CONTRACT_KEYS = {"schema", "admission_profile", "vscode_commit", "server_archive_sha256", "node", "entry",
                 "loader_sha256", "state_root", "challenge", "patched_ghcp", "patches_applied", "synthetic", "execution_allowed"}
LABELS = {"admission_profile": PROFILE, "comparison_row": PROFILE, "admission_scope": SCOPE,
          "patched_ghcp": False, "patch_sha256": None, "execution_allowed": False,
          "read_only_requirement": False, "owner_selection": "not_made"}
FIELDS = (*LABELS, "admission_allowed", "observed", "origins", "verdicts", "native_policy_report",
          "sandbox_scope", "unpatched_runtime", "reasons", "session_created", "native_thread_responses",
          "auth_rpc_succeeded", "synthetic", "safety_violation", "model_turn_start_requests", "model_turn_events",
          "capi_requests", "deferred_fields", "settings_verified", "first_turn_required")
same = original.same


def require(value, reason):
    if not value:
        raise Refused(reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require_context(evidence):
    import ghcp_ahp_prewarm_zero_turn as dispatch
    import ghcp_ahp_patched_runtime as files
    identity = dispatch.context(running=True)  # Identity only, never patch activation.
    require(evidence.name == PROFILE and not any(p.is_symlink() for p in (evidence, *evidence.parents)),
            "default_policy_evidence_namespace_refused")
    require(not any((evidence / name).exists() for name in ("handshake.json", "thread-policy.json", "summary.json", "patched-build-receipt.json")),
            "default_policy_mixed_evidence_refused")
    dispatch.validate_build(strict_json(files._read(evidence / "green-ci.json").decode()), identity)
    return identity


def validate_resolved(values):
    require(type(values) is dict and values.get("codex.permissionsPreset") == "default", "management_default_policy_readback_refused")
    projection = {key: values.get(key, original.NOT_REPORTED) for key in RESOLVER_DEFAULTS}
    require(all(actual == original.NOT_REPORTED or same(actual, RESOLVER_DEFAULTS[key]) for key, actual in projection.items()),
            "management_default_policy_readback_refused")
    return projection


def validate(method, params, rpc):
    original.validate(method, params, rpc, policy=POLICY)


def exercise(rpc, observe=None):
    return original.exercise(rpc, observe, policy=POLICY, resolve_check=validate_resolved)


await_native_thread = original.await_native_thread


def binding(prepared, state, manifest, fork_contract):
    """Compare installed entry bytes to the ORIGINAL pinned release archive."""
    archive_path = prepared / "downloads/server.tgz"
    require(digest(archive_path) == manifest["artifacts"]["server"]["sha256"], "default_policy_archive_drift")
    entry = Path(fork_contract["files"]["node"]["path"]).parent / RELATIVE
    require(entry.is_file() and not any(p.is_symlink() for p in (entry, *entry.parents)), "default_policy_entry_path_refused")
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.getmember("vscode-server-linux-x64/" + RELATIVE)
        require(member.isfile() and 0 < member.size <= 64 * 1024 * 1024 and member.size == entry.stat().st_size,
                "default_policy_entry_size_refused")
        with archive.extractfile(member) as source:
            measured = hashlib.sha256()
            for block in iter(lambda: source.read(1024 * 1024), b""):
                measured.update(block)
            expected = measured.hexdigest()
    require(digest(entry) == expected == UNPATCHED_BUNDLE_SHA256, "default_policy_patched_or_changed_bundle_refused")
    return {"schema": "ghcp-default-unpatched-load-contract-v1", "admission_profile": PROFILE,
            "vscode_commit": manifest["vscode_commit"], "server_archive_sha256": manifest["artifacts"]["server"]["sha256"],
            "node": copy.deepcopy(fork_contract["files"]["node"]), "entry": {"path": str(entry), "sha256": expected},
            "loader_sha256": digest(LOADER), "state_root": str(state), "challenge": uuid.uuid4().hex,
            "patched_ghcp": False, "patches_applied": [], "synthetic": False, "execution_allowed": False}


def verify_load(capture):
    from ghcp_ahp_probe import load_manifest
    manifest = load_manifest()
    boot = capture.get("bootstrap", {})
    require(type(boot) is dict, "default_policy_profile_binding_refused")
    contract = boot.get("default_policy_runtime", {})
    require(boot.get("admission_profile") == PROFILE and boot.get("authenticated_zero_turn") is True
            and boot.get("session_policy") is True and boot.get("model_free") is True
            and not boot.get("patched_runtime_requested") and not capture.get("patched_ghcp"), "default_policy_profile_binding_refused")
    require(type(contract) is dict and set(contract) == CONTRACT_KEYS
            and type(contract.get("node")) is dict and set(contract["node"]) == {"path", "sha256"}
            and type(contract.get("entry")) is dict and set(contract["entry"]) == {"path", "sha256"}
            and type(contract.get("challenge")) is str and re.fullmatch(r"[a-f0-9]{32}", contract["challenge"])
            and contract["entry"]["path"] == posixpath.join(posixpath.dirname(read_only.normalized(contract["node"]["path"])), RELATIVE)
            and boot.get("agent_host_fork", {}).get("entrypoint") == ENTRYPOINT,
            "default_policy_unpatched_contract_refused")
    require(contract.get("schema") == "ghcp-default-unpatched-load-contract-v1"
            and contract.get("admission_profile") == PROFILE and contract.get("patched_ghcp") is False
            and contract.get("execution_allowed") is False and contract.get("synthetic") is False
            and same(contract.get("patches_applied"), []) and contract.get("loader_sha256") == digest(LOADER)
            and contract.get("vscode_commit") == manifest["vscode_commit"]
            and contract.get("server_archive_sha256") == manifest["artifacts"]["server"]["sha256"]
            and same(contract.get("node"), boot.get("agent_host_fork", {}).get("files", {}).get("node"))
            and contract.get("state_root") == boot.get("agent_host_fork", {}).get("state_root"), "default_policy_unpatched_contract_refused")
    rows = capture.get("records", [])
    loads = [row for row in rows if row.get("kind") == "default_policy_loaded"]
    forks = [row for row in rows if row.get("kind") == "default_policy_child"]
    require(len(loads) == len(forks) == 1, "default_policy_load_unmeasured_or_duplicate")
    proof, fork = loads[0], forks[0]
    wanted = contract.get("entry", {}).get("sha256")
    require(wanted == UNPATCHED_BUNDLE_SHA256
            and proof.get("schema") == "ghcp-default-unpatched-load-v1" and proof.get("admission_profile") == PROFILE
            and proof.get("patched_ghcp") is False and proof.get("execution_allowed") is False
            and proof.get("synthetic") is False and proof.get("phase") == "node_load_hook_before_evaluation"
            and all(proof.get(key) == wanted for key in ("loaded_source_sha256", "disk_before_sha256", "disk_after_sha256"))
            and proof.get("contract_sha256") == fork.get("contract_sha256") == sha(encoded(contract)), "default_policy_loaded_hash_refused")
    require(type(proof.get("pid")) is int and proof["pid"] > 0 and type(proof.get("ppid")) is int and proof["ppid"] > 0
            and fork.get("child_pid") == proof["pid"] and fork.get("parent_pid") == proof["ppid"]
            and proof.get("process") == f"wire-{proof['pid']}.jsonl" and fork.get("process") == f"wire-{proof['ppid']}.jsonl",
            "default_policy_loaded_pid_refused")
    installed = [row for row in rows if row.get("kind") == "observer_installed" and row.get("process") == proof["process"]]
    require(len(installed) == 1 and installed[0].get("admission_profile") == PROFILE
            and installed[0].get("entrypoint") == ENTRYPOINT and installed[0].get("model_free") is True
            and installed[0].get("session_only") is True and installed[0].get("synthetic") is False,
            "default_policy_observer_binding_refused")
    return {**LABELS, "runtime_load_status": "measured", "loaded_source_sha256": wanted,
            "server_archive_sha256": contract["server_archive_sha256"], "contract_sha256": sha(encoded(contract)),
            "process": proof["process"], "phase": proof["phase"]}


def verify_live_ready(state):
    from ghcp_ahp_first_turn import read_live_records
    return verify_load({"bootstrap": strict_json((state / "wire/bootstrap.json").read_text()), "records": read_live_records(state)})


def _identity_digest(value, expected_path, uid):
    require(type(value) is dict and value.get("path_sha256") == value.get("realpath_sha256") == sha(expected_path.encode())
            and value.get("uid") == uid and all(type(value.get(k)) is int and value[k] >= 0 for k in ("uid", "device", "inode"))
            and value["inode"] > 0, "default_policy_directory_identity_refused")


def validate_scope(capture, thread):
    rows = [row for row in capture.get("records", []) if row.get("kind") == "default_policy_sandbox_scope"
            and all(same(row.get(key), thread.get(key)) for key in ("process", "stream", "request_id", "thread_id"))]
    require(len(rows) == 1, "default_policy_scope_missing_or_duplicate")
    row = rows[0]
    require(row.get("schema") == "ghcp-default-unpatched-sandbox-scope-v1" and row.get("admission_profile") == PROFILE
            and row.get("status") == "measured" and row.get("verdict") == "default_workspace_policy_observed",
            "default_policy_scope_unmeasured")
    report, values = thread.get("sandbox_report", {}), thread.get("values", {})
    roots = report.get("writableRoots")
    require(type(roots) is list and len(roots) <= 2 and same(roots, row.get("reported_writable_roots"))
            and report.get("type") == row.get("reported_sandbox") == "workspaceWrite"
            and report.get("networkAccess") is row.get("network") is False
            and values.get("approval") == row.get("approval") == "on-request"
            and thread.get("permission_profile", {}).get("id") == row.get("permission_profile") == "vscode-workspace"
            and report.get("excludeSlashTmp") is row.get("exclude_slash_tmp") is True
            and type(report.get("excludeTmpdirEnvVar")) is bool
            and same(report["excludeTmpdirEnvVar"], row.get("exclude_tmpdir_env_var")), "default_policy_native_report_refused")
    bind = row.get("binding", {})
    temporary = read_only.identity(bind.get("job_tmpdir"))
    require(bind.get("status") == "measured" and same(read_only.identity(row.get("tmpdir_at_reply")), temporary),
            "default_policy_tmpdir_changed")
    state = read_only.normalized(capture.get("bootstrap", {}).get("agent_host_fork", {}).get("state_root"))
    require(state not in {"/", "/tmp", "/home"} and bind.get("state_root") == state
            and posixpath.dirname(temporary["path"]) == state + "/tmp", "default_policy_job_binding_refused")
    _identity_digest(row.get("workspace_identity"), state + "/workspace", temporary["uid"])
    identities = row.get("root_identities")
    require(type(identities) is list and len(identities) == len(roots), "default_policy_root_inventory_refused")
    seen = set()
    for root, item in zip(roots, identities, strict=True):
        role = item.get("role")
        require(role in {"job_workspace", "job_tmpdir"} and role not in seen, "default_policy_root_outside_job_or_duplicate")
        seen.add(role)
        expected = state + "/workspace" if role == "job_workspace" else temporary["path"]
        _identity_digest(item, expected, temporary["uid"])
        # Existing redaction intentionally hides cwd. Keep its exact masked raw
        # report; source-bound live path identities, not a guessed alias, bind it.
        require(root == "[REDACTED]" and role == "job_workspace" or read_only.normalized(root) == expected,
                "default_policy_root_report_mismatch")
    return copy.deepcopy(row)


def assess(capture, results):
    observed = dict.fromkeys((*EXPECTED, *read_only.DEFERRED, "writable_roots"), original.NOT_REPORTED)
    origins = dict.fromkeys(observed, original.NOT_REPORTED)
    reasons, runtime, scope = [], {}, {}
    starts = [row for row in capture.get("native_applied_snapshots", []) if row.get("source") == "native.thread/start.result"]
    native_report = starts[0] if len(starts) == 1 else {}
    permissions = native_report.get("permission_profile")
    permissions = permissions if type(permissions) is dict else {}
    sandbox = native_report.get("sandbox_report")
    sandbox = sandbox if type(sandbox) is dict else {}
    for key in EXPECTED:
        observed[key] = (permissions.get("id", original.NOT_REPORTED) if key == "permission_profile"
                         else native_report.get("values", {}).get(key, original.NOT_REPORTED))
        if observed[key] != original.NOT_REPORTED:
            origins[key] = "native.thread/start.result"
    observed["writable_roots"] = sandbox.get("writableRoots", original.NOT_REPORTED)
    if observed["writable_roots"] != original.NOT_REPORTED:
        origins["writable_roots"] = "native.thread/start.result.sandbox.writableRoots"
    for check, key in ((lambda: verify_load(capture), "runtime"), (lambda: validate_scope(capture, native_report), "scope")):
        try:
            value = check()
            if key == "runtime": runtime = value
            else: scope = value
        except (Refused, KeyError, TypeError, ValueError, AttributeError) as error:
            reasons.append(str(error) if isinstance(error, Refused) else "default_policy_evidence_invalid")
    reasons.extend("unreported_or_mismatched:" + key for key, expected in EXPECTED.items() if not same(observed[key], expected))
    native = capture.get("native_requests", [])
    turns = sum(row.get("request", {}).get("method") == "turn/start" for row in native)
    events = sum(str(row.get("value", {}).get("method", "")).startswith(("turn/", "item/"))
                 for row in capture.get("records", []) if row.get("kind") == "ipc_response")
    safety = bool(turns or events or capture.get("capture_errors") or capture.get("capi_requests")
                  or capture.get("capi_response_reports") or len(native) > 1
                  or any(row.get("request", {}).get("method") != "thread/start" for row in native))
    created = "result" in results.get("createSession", {}) and "error" not in results["createSession"]
    authenticated = "result" in results.get("authenticate", {}) and "error" not in results["authenticate"]
    if len(starts) != 1 or len(native) != 1 or not created or not authenticated:
        reasons.append("default_policy_exactly_one_authenticated_native_thread_required")
    if capture.get("synthetic") is not False or capture.get("capture_status") != "captured" or safety:
        reasons.append("default_policy_live_zero_turn_boundary_refused")
    if native_report.get("process") != runtime.get("process"):
        reasons.append("default_policy_thread_process_binding_refused")
    from ghcp_ahp_metadata_broker import MODELS_URLS, USER_URL
    responses = [row for row in capture.get("metadata_http", []) if row.get("kind") == "metadata_response"]
    external = [row for row in responses if row.get("external_request") is True]
    urls = {"https://" + row.get("host", "") + row.get("path", "") for row in external}
    if (len(external) != 2 or USER_URL not in urls or len(urls & MODELS_URLS) != 1
            or any(row.get("method") != "GET" or type(row.get("status")) is not int or row["status"] != 200 for row in responses)):
        reasons.append("default_policy_two_successful_metadata_gets_required")
    return {**LABELS, "schema": "ghcp-default-unpatched-assessment-v1", "requested_policy": {},
        "requested_model": copy.deepcopy(DESIRED_MODEL), "requested_native_launch_args": list(NATIVE_ARGS),
        "observed": observed, "origins": origins,
        "verdicts": {**{key: "matches_default_profile" if same(observed[key], expected) else
                        "not_reported" if observed[key] == original.NOT_REPORTED else "mismatch" for key, expected in EXPECTED.items()},
                     **dict.fromkeys(read_only.DEFERRED, "deferred_to_first_turn"),
                     "writable_roots": "default_workspace_policy_observed" if scope else "refused"},
        "native_policy_report": {"sandbox": copy.deepcopy(native_report.get("sandbox_report", {})),
                                 "approval": observed["approval"], "permission_profile": copy.deepcopy(native_report.get("permission_profile", {}))},
        "unpatched_runtime": runtime, "sandbox_scope": scope, "reasons": list(dict.fromkeys(reasons)),
        "session_created": created, "session_error": results.get("createSession", {}).get("error"),
        "auth_rpc_succeeded": authenticated, "native_thread_responses": len(starts),
        "synthetic": capture.get("synthetic", True), "safety_violation": safety,
        "model_turn_start_requests": turns, "model_turn_events": events, "capi_requests": len(capture.get("capi_requests", [])),
        "metadata_http": capture.get("metadata_http", []), "admission_allowed": not reasons,
        "deferred_fields": list(read_only.DEFERRED), "first_turn_required": True, "settings_verified": False,
        "evidence_boundary": "unpatched_default_policy_zero_turn_only_not_read_only_or_paid_admission"}


def export(evidence, results):
    require(evidence.name == PROFILE, "default_policy_evidence_namespace_refused")
    report = assess(strict_json((evidence / "wire-capture.json").read_text()), results)
    save_json(evidence / POLICY_FILE, report)
    if "management_initialize" in results:
        save_json(evidence / "default-policy-management-init.json", {**results["management_initialize"], **LABELS})
    return {"path": POLICY_FILE, "sha256": digest(evidence / POLICY_FILE), "admission_allowed": report["admission_allowed"],
            "session_created": report["session_created"], "native_thread_responses": report["native_thread_responses"],
            "safety_violation": report["safety_violation"], **LABELS}


def markdown(summary):
    text = "# default_policy_unpatched — zero-turn observation only\n\n"
    text += "patched_ghcp=false; execution_allowed=false; read-only requirement excluded; owner selection pending.\n\n"
    text += "| Field | Native reported value | Verdict |\n| --- | --- | --- |\n"
    for key, value in summary["observed"].items():
        text += "| " + key + " | " + json.dumps(value, ensure_ascii=False).replace("|", "\\|") + " | " + summary["verdicts"][key] + " |\n"
    text += "\nAdmission: " + str(summary["admission_allowed"]).lower() + "; reasons: " + json.dumps(summary["reasons"]) + "\n"
    return text


def write_summary(evidence, handshake):
    summary = {"schema": "ghcp-default-unpatched-summary-v1", "status": handshake["status"],
        "reason_codes": handshake["reason_codes"], **{key: handshake[key] for key in FIELDS},
        "model_calls": 0, "first_turn_executed": False,
        "files": {name: digest(evidence / name) for name in ("probe.json", "wire-capture.json", POLICY_FILE, HANDSHAKE_FILE)}}
    save_json(evidence / SUMMARY_FILE, summary)
    with (evidence / SUMMARY_MD).open("x", encoding="utf-8") as target:
        target.write(markdown(summary))
    verify_chain(evidence)


def verify_chain(evidence):
    report = strict_json((evidence / POLICY_FILE).read_text())
    probe = strict_json((evidence / "probe.json").read_text())
    capture = strict_json((evidence / "wire-capture.json").read_text())
    expected = assess(capture, probe.get("rpc_results", {}))
    require(same(report, expected), "default_policy_assessment_chain_refused")
    handshake = strict_json((evidence / HANDSHAKE_FILE).read_text())
    summary = strict_json((evidence / SUMMARY_FILE).read_text())
    require(handshake.get("schema") == "ghcp-default-unpatched-handshake-v1"
            and summary.get("schema") == "ghcp-default-unpatched-summary-v1"
            and all(same(handshake.get(key), expected[key]) and same(summary.get(key), expected[key]) for key in FIELDS),
            "default_policy_profile_chain_refused")
    require(all(summary.get("files", {}).get(name) == digest(evidence / name)
                for name in ("probe.json", "wire-capture.json", POLICY_FILE, HANDSHAKE_FILE)), "default_policy_artifact_hash_refused")
    require((evidence / SUMMARY_MD).read_text() == markdown(summary), "default_policy_markdown_profile_refused")
    return summary
