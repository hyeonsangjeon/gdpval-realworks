"""Leader-approved zero-turn scope, never permission to run a model turn.

Paths are measured by the live observer, before native TMPDIR cleanup. This
consumer checks the bound measurement; it never resolves paths on the NAS or
substitutes a profile name for a native sandbox report.
"""

from __future__ import annotations

import copy
import json
import posixpath

from ghcp_ahp_errors import Refused

SCOPE = "authenticated_zero_turn_only"
DEFERRED = ("served_model", "context_window", "web_search")
REQUIRED = {"model": "gpt-5.6-sol", "model_provider": "vscode-proxy", "reasoning_effort": "max",
            "approval": "untrusted", "network": False}
FIELDS = ("admission_scope", "admission_allowed", "observed", "verdicts", "sandbox_scope",
          "deferred_fields", "first_turn_required", "settings_verified", "session_created",
          "native_thread_responses", "synthetic", "safety_violation", "auth_rpc_succeeded",
          "model_turn_start_requests", "model_turn_events", "capi_requests")


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def require(value, code):
    if not value:
        raise Refused(code)


def normalized(value):
    require(type(value) is str and value.startswith("/") and not value.startswith("//")
            and ".." not in value.split("/") and "\0" not in value and "[REDACTED]" not in value,
            "sandbox_scope_path_invalid")
    return posixpath.normpath(value)


def identity(value):
    require(type(value) is dict and set(value) == {"path", "realpath", "device", "inode", "uid"},
            "sandbox_scope_identity_missing")
    require(normalized(value["path"]) == value["path"] == value["realpath"]
            and all(type(value[k]) is int and value[k] >= 0 for k in ("device", "inode", "uid"))
            and value["inode"] > 0, "sandbox_scope_identity_invalid")
    return value


def validate_scope(evidence):
    require(type(evidence) is dict, "sandbox_scope_unmeasured")
    row, thread = evidence.get("observer", {}), evidence.get("thread", {})
    require(type(row) is dict and type(thread) is dict, "sandbox_scope_unmeasured")
    require(row.get("schema") == "ghcp-ahp-sandbox-scope-v1" and row.get("status") == "measured",
            "sandbox_scope_unmeasured")
    require(all(key in row and key in thread and same(row[key], thread[key])
                for key in ("process", "stream", "request_id", "thread_id")), "sandbox_scope_thread_binding")
    binding = row.get("binding", {})
    require(type(binding) is dict, "sandbox_scope_job_tmpdir_unmeasured")
    require(binding.get("status") == "measured", "sandbox_scope_job_tmpdir_unmeasured")
    expected = identity(binding.get("job_tmpdir"))
    require(same(identity(row.get("tmpdir_at_reply")), expected), "sandbox_scope_tmpdir_changed")
    state = normalized(evidence.get("state_root"))
    require(state not in {"/", "/tmp", "/home"} and binding.get("state_root") == state
            and posixpath.dirname(expected["path"]) == state + "/tmp", "sandbox_scope_job_tmpdir_binding")
    native = thread.get("sandbox_report", {})
    require(type(native) is dict and "writableRoots" in native, "sandbox_scope_roots_not_reported")
    roots = native["writableRoots"]
    require(type(roots) is list and len(roots) <= 1, "sandbox_scope_root_count")
    require(type(thread.get("permission_profile")) is dict and type(thread.get("values")) is dict,
            "sandbox_scope_report_mismatch")
    require(same(row.get("reported_writable_roots"), roots)
            and row.get("reported_sandbox") == native.get("type")
            and row.get("network") is native.get("networkAccess") is False
            and row.get("approval") == thread.get("values", {}).get("approval") == "untrusted"
            and row.get("permission_profile") == thread.get("permission_profile", {}).get("id")
            == "vscode-workspace-read-only", "sandbox_scope_report_mismatch")
    kind = native.get("type")
    require(kind in {"readOnly", "workspaceWrite"}, "sandbox_scope_kind")
    if kind == "workspaceWrite":
        require(native.get("excludeSlashTmp") is row.get("exclude_slash_tmp") is True
                and type(native.get("excludeTmpdirEnvVar")) is bool
                and same(native["excludeTmpdirEnvVar"], row.get("exclude_tmpdir_env_var"))
                and (roots or native["excludeTmpdirEnvVar"] is True), "sandbox_scope_implicit_write")
    names = [normalized(root) for root in roots]
    require(names == row.get("normalized_writable_roots") and
            (not roots or names == [expected["path"]]), "sandbox_scope_not_exact_job_tmpdir")
    require(same(row.get("root_identities"), [expected] if roots else []), "sandbox_scope_identity_mismatch")
    require(not roots or kind != "readOnly", "sandbox_scope_contradictory_roots")
    verdict = "read_only_except_job_tmpdir" if roots else "readOnly"
    require(row.get("verdict") == verdict, "sandbox_scope_verdict_mismatch")
    return verdict


def sandbox_report(capture, thread):
    rows = [row for row in capture.get("native_sandbox_scopes", []) if all(
        key in thread and same(row.get(key), thread[key]) for key in ("process", "stream", "request_id", "thread_id"))]
    evidence = {"observer": copy.deepcopy(rows[0]) if len(rows) == 1 else {}, "thread": copy.deepcopy(thread),
                "state_root": capture.get("bootstrap", {}).get("agent_host_fork", {}).get("state_root")}
    report = {"evidence": evidence, "allowed": False, "verdict": "refused", "reason_codes": []}
    try:
        require(len(rows) == 1, "sandbox_scope_missing_or_duplicate")
        report["verdict"] = validate_scope(evidence)
        report["allowed"] = True
    except (Refused, KeyError, TypeError, ValueError) as error:
        report["reason_codes"] = [str(error) if isinstance(error, Refused) else "sandbox_scope_invalid"]
    return report


def require_scoped_admission(value):
    """Narrow exception to the patched-loader's no-execution contract.

    A zero-turn receipt may admit ONLY its already finished metadata/session
    inspection. All model/paid/launch permissions remain independently false.
    """
    require(value.get("admission_scope") == SCOPE and value.get("admission_allowed") is True
            and same(value.get("deferred_fields"), list(DEFERRED))
            and value.get("first_turn_required") is True and value.get("settings_verified") is False,
            "zero_turn_scope_contract_refused")
    observed, verdicts = value.get("observed", {}), value.get("verdicts", {})
    require(set(observed) == set(verdicts) == {*REQUIRED, *DEFERRED, "sandbox"}, "zero_turn_scope_fields_refused")
    require(all(same(observed[key], expected) and verdicts[key] == "matches" for key, expected in REQUIRED.items()),
            "zero_turn_required_policy_refused")
    require(all(verdicts[key] == "deferred_to_first_turn" for key in DEFERRED), "zero_turn_deferred_counted_as_pass")
    scope = value.get("sandbox_scope", {})
    verdict = validate_scope(scope.get("evidence"))
    require(scope.get("allowed") is True and scope.get("reason_codes") == [] and scope.get("verdict") == verdict
            and verdicts["sandbox"] == verdict and observed["sandbox"] == scope["evidence"]["observer"]["reported_sandbox"],
            "zero_turn_sandbox_verdict_refused")
    require(value.get("session_created") is True and value.get("auth_rpc_succeeded") is True
            and value.get("synthetic") is False and value.get("safety_violation") is False
            and same(value.get("native_thread_responses"), 1)
            and all(same(value.get(key), 0) for key in ("model_turn_start_requests", "model_turn_events", "capi_requests")),
            "zero_turn_activity_contract_refused")
    return True
