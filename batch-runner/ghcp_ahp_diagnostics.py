"""Redacted AHP advertisements, never served-model or admission evidence.

No environment, credentials store, process, session or network is opened here.
The caller supplies its in-memory credential only for removal before export.
"""

from __future__ import annotations

import base64
import json
import re
from urllib.parse import quote, quote_plus

from ghcp_ahp_probe import DESIRED_MODEL, ROOT_CHANNEL, Refused, redact

NOT_REPORTED = "not_reported"
_PRIVATE_KEYS = frozenset({
    "account", "accounts", "accountid", "accountname", "accountlabel", "accountinfo", "accountdetails",
    "user", "users", "userid", "username", "userlogin", "userinfo", "userprofile", "profile",
    "identity", "identities", "login", "email", "emailaddress", "authentication", "auth",
    "tenant", "tenantid", "organization", "organizationid", "orgid", "principal", "principalid", "subject", "sub", "oid",
    "token", "accesstoken", "refreshtoken", "idtoken", "connectiontoken", "authorization",
    "password", "secret", "apikey", "credential", "credentials", "authsessionid",
    "workingdirectory", "workingdirectories", "cwd", "homedirectory", "homedir", "userdatadir",
})
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _private_key(key):
    normalized = re.sub(r"[^a-z]", "", str(key).lower())
    return normalized in _PRIVATE_KEYS or normalized.endswith((
        "token", "apikey", "password", "secret", "accountid", "userid", "username", "email", "tenantid"))


class DiagnosticRedactor:
    """Remember identifiers in memory so later auth replies also clean earlier echoes."""

    def __init__(self, credential):
        self.identifiers = set()
        self.forms = set()
        if credential:
            self.forms.update((credential, json.dumps(credential, ensure_ascii=True)[1:-1],
                               json.dumps(credential, ensure_ascii=False)[1:-1],
                               quote(credential, safe=""), quote_plus(credential, safe="")))
            for encoded in (base64.b64encode(credential.encode()).decode(),
                            base64.urlsafe_b64encode(credential.encode()).decode()):
                self.forms.update((encoded, encoded.rstrip("=")))

    def _learn(self, value, private=False):
        if isinstance(value, dict):
            for key, item in value.items():
                self._learn(item, private or _private_key(key))
        elif isinstance(value, list):
            for item in value:
                self._learn(item, private)
        elif private and type(value) in (str, int):
            text = str(value)
            if text and text != "[REDACTED]":
                if len(text) > 8192 or len(self.identifiers) >= 512 and text not in self.identifiers:
                    raise Refused("connection_diagnostic_identity_limit")
                self.identifiers.add(text)

    def clean(self, value):
        self._learn(value)
        forms = sorted(self.forms | self.identifiers, key=len, reverse=True)

        def visit(item):
            if isinstance(item, dict):
                return {visit(str(key)): "[REDACTED]" if _private_key(key) else visit(data)
                        for key, data in item.items()}
            if isinstance(item, list):
                return [visit(data) for data in item]
            if isinstance(item, str):
                for form in forms:
                    item = item.replace(form, "[REDACTED]")
                return _EMAIL.sub("[REDACTED]", redact(item))
            return item

        return visit(value)


def policy_rejections(resolved, requested):
    """Explain the same required-key/exact-value gate; missing is not a default."""
    result = resolved if isinstance(resolved, dict) else {}
    schema = result.get("schema")
    properties = schema.get("properties") if isinstance(schema, dict) else None
    properties = properties if isinstance(properties, dict) else {}
    values = result.get("values")
    values = values if isinstance(values, dict) else {}
    rejected = []
    for key, wanted in requested.items():
        reasons = []
        if key not in properties:
            reasons.append("schema_property_not_advertised")
        if key not in values:
            reasons.append("resolved_value_not_reported")
        elif type(values[key]) is not type(wanted) or values[key] != wanted:
            reasons.append("resolved_value_mismatch")
        if reasons:
            rejected.append({"field": key, "requested": wanted,
                "advertised": {"schema_present": key in properties,
                               "schema": properties.get(key, NOT_REPORTED),
                               "resolved_value": values.get(key, NOT_REPORTED)},
                "reasons": reasons})
    return rejected


def advertised_models(frames):
    """Root snapshots and root/agentsChanged are catalogs, NOT response evidence."""
    agents, source = None, NOT_REPORTED
    for frame in frames:
        if frame.get("direction") != "server":
            continue
        message = frame.get("message", {})
        if not isinstance(message, dict):
            continue
        result = message.get("result")
        if isinstance(result, dict):
            snapshots = result.get("snapshots", [])
            for snapshot in snapshots if isinstance(snapshots, list) else []:
                if not isinstance(snapshot, dict) or snapshot.get("resource") != ROOT_CHANNEL:
                    continue
                state = snapshot.get("state", {})
                if isinstance(state, dict) and isinstance(state.get("agents"), list):
                    agents, source = state["agents"], "initialize.snapshots[ahp-root://].state.agents"
        params = message.get("params", {})
        params = params if isinstance(params, dict) else {}
        action = params.get("action", {})
        if (message.get("method") == "action" and params.get("channel") == ROOT_CHANNEL
                and isinstance(action, dict) and action.get("type") == "root/agentsChanged"
                and isinstance(action.get("agents"), list)):
            agents, source = action["agents"], "root/agentsChanged.agents"
    candidates = [agent for agent in agents or [] if isinstance(agent, dict) and agent.get("provider") == "codex"]
    agent = candidates[0] if len(candidates) == 1 else {}
    models = agent.get("models", NOT_REPORTED)
    models = models if isinstance(models, list) else NOT_REPORTED
    matching = [model for model in models if isinstance(model, dict) and model.get("id") == DESIRED_MODEL["id"]] if isinstance(models, list) else []
    selected = matching[0] if len(matching) == 1 else {}
    config = selected.get("configSchema", {})
    properties = config.get("properties", {}) if isinstance(config, dict) else {}
    properties = properties if isinstance(properties, dict) else {}
    status = (NOT_REPORTED if models == NOT_REPORTED else "absent" if not matching
              else "advertised" if len(matching) == 1 else "ambiguous")
    if not matching and isinstance(models, list) and any(
            isinstance(model, dict) and "[REDACTED]" in str(model.get("id", "")) for model in models):
        status = NOT_REPORTED  # Redaction cannot prove that a model is absent.
    return {"evidence_boundary": "advertisement_only_not_served_settings", "source": source,
            "models": models, "agent_capabilities": agent.get("capabilities", NOT_REPORTED),
            "requested_model_id": DESIRED_MODEL["id"], "model_status": status,
            "thinkingLevel": properties.get("thinkingLevel", NOT_REPORTED),
            "contextSize": properties.get("contextSize", NOT_REPORTED),
            "maxContextWindow": selected.get("maxContextWindow", NOT_REPORTED)}
