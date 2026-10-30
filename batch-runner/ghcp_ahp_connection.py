"""One AHP connectivity turn, never a five-task run or a settings echo proof.

Only the explicit protected dispatch entry below can open a live port. Unit
tests inject a fake port. The pinned AHP mapper does not attest served model or
thinking level: those fields stay not_reported, even if usage.model agrees.
"""

from __future__ import annotations

import copy
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import time

from ghcp_ahp_client import Limits, NOT_REPORTED, SessionClient
from ghcp_ahp_probe import DESIRED_MODEL, Refused, digest, require_runner, save_json, strict_json

LIMITS = Limits(turns=1, tool_calls=0, seconds=120)
PROMPT = "Reply with exactly CONNECTED. Do not use any tools."
TURN = "connection-only"
REQUESTED = {"served_model": "gpt-5.6-sol", "thinking_level": "max", "context_size": 1_000_000,
             "usage": "report_if_available"}
FIELDS = ("served_model", "thinking_level", "context_size", "usage")


def empty_observed():
    return {field: NOT_REPORTED for field in FIELDS}


def settings_verdict(observed):
    """Strict decision function. Synthetic successes are NOT live attestation.

    Caller must supply observations with response-side provenance. The pinned
    AHP reader below deliberately cannot fill the two unsupported fields.
    """
    reasons = []
    for field in FIELDS[:-1]:
        value = observed.get(field, NOT_REPORTED)
        if value is None or value == NOT_REPORTED or value == "":
            reasons.append(f"{field}_not_reported")
        elif type(value) is not type(REQUESTED[field]) or value != REQUESTED[field]:
            reasons.append(f"{field}_mismatch")
    return {"settings_verified": not reasons, "reason_codes": reasons}


class ConnectionSession(SessionClient):
    def __init__(self, transport, session, chat, *, authenticated, clock=time.monotonic, credential=None):
        super().__init__(transport, session, chat, authenticated=authenticated, limits=LIMITS,
                         clock=clock, credential=credential, finish_admitted_turn=True)
        self.observed = empty_observed()
        self.provenance = {field: NOT_REPORTED for field in FIELDS}
        self.usage_reports = []
        self.markdown_parts = []
        self.violations = []

    def _stop(self, reason, *, completed=False):
        # Late malformed/error frames cannot turn an already-completed capture
        # into success. Keep these sticky even after admission has closed.
        if not completed and self.status != "open":
            self.violations.append(reason)
        super()._stop(reason, completed=completed)

    def _violation(self, code):
        self.violations.append(code)
        raise Refused(code)

    def _snapshot(self, snapshot):
        state = snapshot.get("state", {})
        # Fresh connection only, never restore/resume/import earlier evidence.
        if snapshot.get("resource") == self.chat and (state.get("turns") or state.get("activeTurn")):
            self._violation("connection_history_refused")
        super()._snapshot(snapshot)

    def _action(self, channel, action):
        kind = action.get("type", "")
        if kind.startswith("chat/") and "turnId" in action:
            if action["turnId"] != TURN or TURN not in self.turns:
                self._violation("connection_foreign_turn")
        if kind.startswith("chat/toolCall") or kind.startswith("terminal/"):
            # Zero approvals/executions by this client. Already-running server
            # tools cannot be undone; preserve the observed violation and stop.
            if "toolCallId" in action:
                self._tool(TURN, action["toolCallId"])
                self.tool_events.append(copy.deepcopy(action))
            self._violation("connection_tool_forbidden")
        if kind == "chat/responsePart":
            part = action["part"]
            if part.get("kind") == "toolCall":
                self._tool(TURN, part["toolCall"]["toolCallId"])
                self.tool_events.append(copy.deepcopy(action))
                self._violation("connection_tool_forbidden")
            if part.get("kind") == "markdown":
                self.markdown_parts.append(part["id"])
        if kind == "chat/usage":
            usage = action.get("usage")
            if not isinstance(usage, dict):
                self._violation("connection_usage_invalid")
            token_fields = ("inputTokens", "outputTokens", "cacheReadTokens")
            if any(key in usage and (type(usage[key]) is not int or usage[key] < 0) for key in token_fields):
                self._violation("connection_usage_invalid")
            self.usage_reports.append(copy.deepcopy(usage))
            counted = [row for row in self.usage_reports if any(key in row for key in token_fields)]
            if counted:
                self.observed["usage"] = copy.deepcopy(counted)
                self.provenance["usage"] = "server chat/usage; SDK token counts, not billing"
            context = (usage.get("_meta") or {}).get("modelContextWindow")
            if context is not None:
                if type(context) is not int or context <= 0:
                    self._violation("connection_context_invalid")
                previous = self.observed["context_size"]
                if previous != NOT_REPORTED and previous != context:
                    self._violation("connection_context_changed")
                self.observed["context_size"] = context
                self.provenance["context_size"] = "chat/usage.usage._meta.modelContextWindow (SDK-reported)"
                if context != REQUESTED["context_size"]:
                    self._violation("context_size_mismatch")
            # codexAgent.ts:3929 supplies session.model?.id to the mapper;
            # codexMapAppServerEvents.ts:514 copies it into usage.model.
            # Neither this nor historical message.model proves served_model.
            # reasoningOutputTokens is a COUNT, never an effort-level proof.
        super()._action(channel, action)

    def result(self, capture):
        verdict = settings_verdict(self.observed)
        reasons = list(dict.fromkeys(self.violations + verdict["reason_codes"]))
        reply = "".join(self.text.get((TURN, part), "") for part in self.markdown_parts)
        if self.status != "completed" or self.completed != {TURN}:
            reasons.append(self.reason or "connection_incomplete")
        if self.turns != {TURN} or self.tools:
            reasons.append("connection_count_refused")
        if reply.strip() != "CONNECTED":
            reasons.append("connection_reply_mismatch")
        if self.clock() - self.started >= LIMITS.seconds:
            reasons.append("time_limit_reached")
        if capture.get("cleanup", {}).get("host_terminated") is not True:
            reasons.append("connection_cleanup_unverified")
        return {"schema_version": "ghcp-ahp-connection-v1", "requested": copy.deepcopy(REQUESTED),
                "observed": copy.deepcopy(self.observed), "observation_sources": copy.deepcopy(self.provenance),
                "requested_model_selection": copy.deepcopy(DESIRED_MODEL), "limits": asdict(LIMITS),
                "counts": capture["counts"], "overshoot_boundary": capture["overshoot_boundary"],
                "status": "connected" if not reasons else "refused", "connection_verified": not reasons,
                "reason_codes": list(dict.fromkeys(reasons)), "gate_ready": False, "five_task_allowed": False,
                "remaining_gate": "ahp_paid_contract_unverified", "reply_exact": reply.strip() == "CONNECTED",
                "capture_boundary": "one_client_turn_not_one_provider_request; no native zero-tool guarantee"}


def run_connection(transport, session, chat, output, *, credential, authenticated, clock=time.monotonic):
    """Injectable session path; no retry, no second prompt, no task loader."""
    client = ConnectionSession(transport, session, chat, authenticated=authenticated,
                               credential=credential, clock=clock)
    if client.send_turn(TURN, PROMPT):
        client.run()
    capture = client.capture(output / "capture.json")
    result = client.result(capture)
    result["capture_sha256"] = digest(output / "capture.json")
    return client._safe(result)


def _destination(path):
    if (not path.is_absolute() or path.exists() or ".." in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise Refused("connection_destination_refused")
    path.mkdir(mode=0o700, parents=True)


def execute(prepared, evidence, state, output, *, open_port=None):
    """Protected dispatch only. Authentication admission precedes host startup.

    No fixture flag/environment bypass exists. Tests patch the injected port
    in-process. Runner and run-attempt checks also apply to that entry.
    """
    import ghcp_sol_execution_adapter as adapter
    from ghcp_sol_paid_gate import require_dispatch
    record = {"schema_version": "ghcp-ahp-connection-v1", "status": "refused", "connection_verified": False,
              "requested": copy.deepcopy(REQUESTED), "observed": empty_observed(), "limits": asdict(LIMITS),
              "reason_codes": [], "gate_ready": False, "five_task_allowed": False, "client_turns_sent": 0}
    guard = port = None
    owned_output = False
    try:
        require_dispatch()
        if os.environ.get("GHCP_CONNECTION_ONLY") != "true":
            raise Refused("connection_dispatch_required")
        identity = require_runner()
        _destination(output)
        owned_output = True
        record["runner"] = identity
        auth = adapter._selected_auth_environment("COPILOT_GITHUB_TOKEN", state_root=state)
        credential = auth["COPILOT_GITHUB_TOKEN"]
        guard = adapter._CredentialGuard(credential)
        # No discovery, download, process or transport until auth is nonempty.
        if output.is_relative_to(state) or state.is_relative_to(output):
            raise Refused("connection_destination_refused")
        if open_port is None:
            from ghcp_ahp_connection_transport import open_connection_port
            open_port = open_connection_port
        with open_port(prepared, evidence, state, credential) as port:
            record.update(run_connection(port, port.session, port.chat, output,
                                         credential=credential, authenticated=True))
            record["client_turns_sent"] = port.turns_sent
            # Handshake contains only redacted frames, never raw credentials or host logs.
            save_json(output / "handshake.json", port.handshake_capture())
            record["handshake_sha256"] = digest(output / "handshake.json")
        guard.check(json.dumps(record, allow_nan=False).encode())
    except (Refused, adapter._Stop) as error:
        code = error.code if isinstance(error, adapter._Stop) else str(error)
        code = code if re.fullmatch(r"[a-z_]{1,100}", code) else "connection_execution_refused"
        record.update(status="refused", connection_verified=False, reason_codes=[
            code])
    except Exception:
        record.update(status="refused", connection_verified=False, reason_codes=["connection_execution_refused"])
    if port is not None:
        record["client_turns_sent"] = port.turns_sent
    if guard:
        try:
            guard.check(json.dumps(record, allow_nan=False).encode())
        except adapter._Stop:
            record = {"schema_version": "ghcp-ahp-connection-v1", "status": "refused",
                      "requested": copy.deepcopy(REQUESTED), "observed": empty_observed(),
                      "connection_verified": False, "five_task_allowed": False, "gate_ready": False,
                      "reason_codes": ["authentication_secret_exposure_refused"]}
    if owned_output:
        save_json(output / "connection.json", record)
    return record


def require_verified_connection(path):
    """Do not accept a missing, edited, old-run or synthetic connection receipt."""
    if path is None:
        raise Refused("connection_verification_required")
    identity = require_runner()
    if (not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents))
            or not path.is_file() or path.stat().st_size > 1024 * 1024):
        raise Refused("connection_receipt_refused")
    record = strict_json(path.read_text())
    if (record.get("schema_version") != "ghcp-ahp-connection-v1"
            or record.get("connection_verified") is not True or record.get("status") != "connected"
            or record.get("reason_codes") != [] or record.get("requested") != REQUESTED
            or record.get("limits") != asdict(LIMITS) or record.get("reply_exact") is not True
            or record.get("client_turns_sent") != 1 or record.get("runner") != identity
            or not settings_verdict(record.get("observed", {}))["settings_verified"]):
        raise Refused("connection_verification_required")
    for name in ("capture", "handshake"):
        artifact = path.parent / (name + ".json")
        if artifact.is_symlink() or not artifact.is_file() or digest(artifact) != record.get(name + "_sha256"):
            raise Refused("connection_capture_unverified")
    # This pinned mapper cannot attest these two fields. Never admit a hand-
    # edited JSON or a synthetic-success fixture as a live receipt.
    raise Refused("connection_served_attestation_unavailable")


def main(argv=None):
    from ghcp_sol_execution_adapter import _Parser
    parser = _Parser(description=__doc__)
    for name in ("prepared", "evidence", "state", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    result = execute(args.prepared, args.evidence, args.state, args.output)
    print(json.dumps({key: result[key] for key in ("status", "connection_verified", "reason_codes")}))
    return 0 if result["connection_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
