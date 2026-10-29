"""Owned, redacted provider response artifacts; never request-setting evidence.

The field paths below are a prospective intake contract, not a claim that
Foundry emits them. Absence stays ``not_reported``. A matching response is not
an attestation of capacity, entitlement, model version, billing or launch rights.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path

from gpt54_codex_input_capture import _write_no_clobber
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _read_bytes

NOT_REPORTED = "not_reported"
SCHEMA = "native-provider-response/v1"
BOUNDARY = "redacted_provider_response_not_capability_or_launch_attestation"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024  # Artifact memory bound, NOT a token quota.
STOPS = frozenset({
    "native_response_artifact_failed", "native_response_capture_incomplete",
    "native_response_capture_limit", "native_response_fields_invalid",
    "served_model_unverified", "served_model_mismatch",
    "reasoning_effort_unverified", "reasoning_effort_mismatch",
    "context_window_unverified", "context_window_mismatch",
    "native_response_fields_inconsistent",
})
CONTEXT_FIELDS = ("context_window", "model_context_window", "context_window_tokens",
                  "tokenLimit", "modelContextWindow")
_SECRET_KEY = re.compile(
    r"(?:authorization|proxy.authorization|(?:x.)?api.key|cookie|set.cookie|"
    r"(?:access[-_]?|refresh[-_]?|id[-_]?)?token|client[-_]?secret|password|secret|credential)", re.I)
_SECRET_HEADER = re.compile(r"authorization|api[-_]?key|token|cookie|secret|credential|password", re.I)
# These response headers describe quotas, not authentication. A numeric zero
# in a token counter must not become a global credential redaction that ruins
# every zero in the response JSON/model identifier. Unknown names or values
# still take the conservative secret path. Known request credentials always
# remain in the redactor, including when echoed in one of these fields.
_RATE_LIMIT_METADATA = frozenset({
    "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens",
    "x-ratelimit-renewalperiod-tokens",
    "x-ratelimit-limit-project-tokens", "x-ratelimit-remaining-project-tokens",
    "x-ratelimit-reset-project-tokens",
})
_RATE_LIMIT_VALUE = re.compile(
    r"(?:[0-9]{1,20}(?:\.[0-9]{1,6})?|(?:[0-9]{1,8}(?:\.[0-9]{1,6})?(?:ms|s|m|h|d)){1,6})\Z")
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"', re.S)
_COLON = re.compile(r"\s*:\s*")
_TOKEN = re.compile(r"\b(?:ey[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}(?:\.[A-Za-z0-9_-]+)?|"
                    r"(?:gh[pousr]_|github_pat_|sk-)[A-Za-z0-9_-]{8,})\b")
_BEARER = re.compile(r"\bBearer\s+[^\s\"'\\,;]+", re.I)
_URL = re.compile(r"https?://[^\s\"'<>\\]+", re.I)
_ATOM = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


def _secret_response_header(name, value):
    if name.lower() in _RATE_LIMIT_METADATA and _RATE_LIMIT_VALUE.fullmatch(value):
        return False
    return bool(_SECRET_HEADER.search(name) or name.lower() == "x-ratelimit-key")


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def empty_fields():
    return {"served_model": NOT_REPORTED, "served_model_version": NOT_REPORTED,
            "reasoning_effort": NOT_REPORTED, "context_tokens": NOT_REPORTED,
            "context_fields": {}}


def response_fields(document):
    """Only a terminal provider response object; never SDK/rollout/request data."""
    result = empty_fields()
    if type(document) is not dict or document.get("object") != "response":
        return result
    for field, raw in (("served_model", document.get("model")),
                       ("served_model_version", document.get("model_version")),
                       ("reasoning_effort", (document.get("reasoning") or {}).get("effort")
                        if type(document.get("reasoning")) is dict else None)):
        if type(raw) is str and _ATOM.fullmatch(raw) and not _TOKEN.search(raw):
            result[field] = raw
    for field in CONTEXT_FIELDS:
        raw = document.get(field)
        if type(raw) is int and 0 < raw < 2 ** 63:
            result["context_fields"][field] = raw
    sizes = set(result["context_fields"].values())
    if len(sizes) == 1:
        result["context_tokens"] = sizes.pop()
    return result


def _redact_text(text, secrets):
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _TOKEN.sub("[REDACTED]", text)
    text = _URL.sub("[REDACTED_URL]", text)
    for secret in secrets:
        text = text.replace(secret, "[REDACTED]")
    return text


def _redact_body(body, secrets):
    """Keep original UTF-8/JSONL formatting outside redactions, including SSE.

    Decode individual JSON string literals as well, so escaped credentials and
    values split across network chunks are not a way around literal masking.
    No unredacted temporary file is ever written.
    """
    text = body.decode("utf-8", "strict")
    spans = []
    covered = -1
    decoder = json.JSONDecoder()
    for match in _STRING.finditer(text):
        if match.start() < covered:
            continue
        value = json.loads(match.group())
        colon = _COLON.match(text, match.end())
        if colon and _SECRET_KEY.fullmatch(value):
            start = colon.end()
            try:
                _, end = decoder.raw_decode(text, start)
            except ValueError:
                # A partially received credential must not be persisted.
                raise ValueError("unsafe_partial_secret") from None
            spans.append((start, end, '"[REDACTED]"'))
            covered = end
            continue
        clean = _redact_text(value, secrets)
        if clean != value:
            spans.append((match.start(), match.end(), json.dumps(clean, ensure_ascii=False)))
    parts, previous = [], 0
    for start, end, clean in spans:
        parts.extend((text[previous:start], clean))
        previous = end
    parts.append(text[previous:])
    return _redact_text("".join(parts), secrets)


def empty_evidence(reason="native_response_capture_incomplete"):
    return {"schema": SCHEMA, "boundary": BOUNDARY, "state": "unverified", "reason": reason,
            **empty_fields(), "responses": [], "launch_allowed": False}


def bounded_evidence(raw):
    """Closed public projection; bodies, headers and private paths stay outside."""
    invalid = empty_evidence("native_response_fields_invalid")
    if type(raw) is not dict or set(raw) != set(invalid):
        return invalid
    if (raw["schema"] != SCHEMA or raw["boundary"] != BOUNDARY or raw["launch_allowed"] is not False
            or raw["state"] not in ("observed", "unverified")
            or not (raw["reason"] is None or type(raw["reason"]) is str)
            or raw["reason"] not in STOPS | {None}
            or (raw["state"] == "observed") != (raw["reason"] is None)):
        return invalid
    def fields_ok(row):
        return (all(type(row.get(key)) is str and _ATOM.fullmatch(row[key])
                    and not _TOKEN.search(row[key]) for key in
                    ("served_model", "served_model_version", "reasoning_effort"))
                and (row.get("context_tokens") == NOT_REPORTED
                     or type(row.get("context_tokens")) is int and 0 < row["context_tokens"] < 2 ** 63)
                and type(row.get("context_fields")) is dict
                and set(row["context_fields"]) <= set(CONTEXT_FIELDS)
                and all(type(value) is int and 0 < value < 2 ** 63
                        for value in row["context_fields"].values()))
    if not fields_ok(raw) or type(raw["responses"]) is not list or len(raw["responses"]) > 32:
        return invalid
    for row in raw["responses"]:
        if (type(row) is not dict or set(row) != {"artifact", "http_status", "complete", "fields"}
                or type(row["http_status"]) is not int or not 100 <= row["http_status"] <= 599
                or type(row["complete"]) is not bool or type(row["fields"]) is not dict
                or set(row["fields"]) != set(empty_fields()) or not fields_ok(row["fields"])):
            return invalid
        artifact = row["artifact"]
        if (type(artifact) is not dict or set(artifact) != {"path", "size", "sha256"}
                or type(artifact["path"]) is not str
                or not re.fullmatch(r"[a-z0-9-]{1,96}/response-[0-9]{4}\.json", artifact["path"])
                or type(artifact["size"]) is not int or not 0 < artifact["size"] <= MAX_RESPONSE_BYTES * 8
                or type(artifact["sha256"]) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"])):
            return invalid
    if raw["state"] == "observed" and (not raw["responses"] or any(not row["complete"] for row in raw["responses"])):
        return invalid
    return json.loads(_bytes(raw))


class ResponseCaptureRefused(ValueError):
    def __init__(self, reason="native_response_artifact_failed"):
        super().__init__(reason)
        self.reason = reason


def verify_artifact_bundle(parent, evidence):
    """Publication check, NOT adoption of a live witness or launch approval."""
    try:
        parent = _root(parent)
        if bounded_evidence(evidence) != evidence:
            raise ValueError("bad_evidence")
        expected = {}
        for row in evidence["responses"]:
            binding = row["artifact"]
            path = _path(parent, binding["path"])
            if path in expected:
                raise ValueError("duplicate_artifact")
            data = _read_bytes(path, size=binding["size"], sha256=binding["sha256"])
            raw = json.loads(data)
            if (set(raw) != {"schema", "http_status", "headers", "body_utf8", "complete", "redaction", "boundary"}
                    or raw["schema"] != SCHEMA or raw["boundary"] != BOUNDARY
                    or raw["complete"] is not row["complete"] or raw["http_status"] != row["http_status"]
                    or type(raw["body_utf8"]) is not str
                    or _redact_body(raw["body_utf8"].encode(), ()) != raw["body_utf8"]):
                raise ValueError("unsafe_artifact")
            for name, value in raw["headers"]:
                if ((_secret_response_header(name, value) and value != "[REDACTED]")
                        or _redact_text(value, ()) != value):
                    raise ValueError("unsafe_header")
            expected[path] = True
        for directory in {path.parent for path in expected}:
            if set(_root(directory).iterdir()) != {path for path in expected if path.parent == directory}:
                raise ValueError("unlisted_artifact")
    except Exception:
        raise ResponseCaptureRefused() from None


class NativeResponseArtifacts:
    """Exclusive attempt-owned files, with no disk-only adoption/replay path."""

    def __init__(self, parent, directory, *, expected_model="gpt-5.6-sol",
                 required_effort="max", required_context=1_000_000):
        if (not re.fullmatch(r"[a-z0-9-]{1,96}", directory)
                or expected_model != "gpt-5.6-sol" or required_effort != "max"
                or type(required_context) is not int or required_context != 1_000_000):
            raise ResponseCaptureRefused("native_response_fields_invalid")
        self.parent = _root(parent)
        self.directory = directory
        self.root = self.parent / directory
        self.expected_model, self.required_effort, self.required_context = expected_model, required_effort, required_context
        self.lock = threading.RLock()
        self.rows, self.files = [], {}
        self.reason = None
        self.sealed = False
        self.unpublished_after_close = threading.Event()
        try:
            with _held_parents(self.parent, (directory,)) as check:
                check()
                os.mkdir(self.root, mode=0o700)
                check()
            stat = self.root.stat()
            self.identity = (stat.st_dev, stat.st_ino)
            self.verify()
        except Exception:
            raise ResponseCaptureRefused() from None

    def refuse(self, reason):
        with self.lock:
            if self.reason is None:
                self.reason = reason if reason in STOPS else "native_response_fields_invalid"
            return self.reason

    def verify(self):
        # A stalled writer must not make admission/final refusal hang either.
        if self.unpublished_after_close.is_set() or not self.lock.acquire(blocking=False):
            raise ResponseCaptureRefused()
        try:
            try:
                root = _root(self.root)
                stat = root.stat()
                if (stat.st_dev, stat.st_ino) != self.identity or {p.name for p in root.iterdir()} != set(self.files):
                    raise ValueError("artifact_directory_changed")
                for name, binding in self.files.items():
                    _read_bytes(_path(root, name), size=binding["size"], sha256=binding["sha256"])
            except Exception:
                self.refuse("native_response_artifact_failed")
                raise ResponseCaptureRefused() from None
        finally:
            self.lock.release()

    def begin(self, status, headers, request_headers, private_values=()):
        with self.lock:
            if self.sealed or self.reason is not None:
                raise ResponseCaptureRefused(self.reason or "native_response_capture_incomplete")
            self.verify()
            secrets = set(value for value in private_values if value)
            for group, is_response in ((request_headers, False), (headers, True)):
                for name, value in group:
                    sensitive = (_secret_response_header(name, value) if is_response
                                 else _SECRET_HEADER.search(name))
                    if sensitive and value:
                        secrets.add(value)
                        if value.lower().startswith("bearer "):
                            secrets.add(value[7:])
            return _ResponseArtifact(self, status, headers, tuple(sorted(secrets, key=len, reverse=True)))

    def record(self, response, fields, *, complete):
        with self.lock:
            if self.sealed:
                return self.refuse("native_response_capture_incomplete")
            try:
                self.verify()
                headers = [[name, "[REDACTED]" if _secret_response_header(name, value)
                            else _redact_text(value, response.secrets)] for name, value in response.headers]
                raw = _redact_body(response.body, response.secrets)
                # Never let an echoed credential become receipt metadata.
                fields = json.loads(_redact_body(_bytes(fields), response.secrets))
                for name in ("served_model", "served_model_version", "reasoning_effort"):
                    if type(fields.get(name)) is not str or not _ATOM.fullmatch(fields[name]):
                        fields[name] = NOT_REPORTED
                data = _bytes({"schema": SCHEMA, "http_status": response.status, "headers": headers,
                               "body_utf8": raw, "complete": complete,
                               "redaction": "secret_headers_json_values_bearers_known_credentials_and_urls",
                               "boundary": BOUNDARY})
                name = f"response-{len(self.rows) + 1:04d}.json"
                binding = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                with _held_parents(self.parent, (self.directory + "/" + name,)) as check:
                    check()
                    _write_no_clobber(self.root / name, data)
                    self.files[name] = binding
                    check()
                    self.verify()
                self.rows.append({"artifact": {"path": self.directory + "/" + name, **binding},
                                  "http_status": response.status, "complete": complete, "fields": fields})
            except Exception:
                return self.refuse("native_response_artifact_failed")
            if not complete or not 200 <= response.status < 300:
                return self.refuse("native_response_capture_incomplete")
            reason = self._field_reason(fields)
            if reason:
                return self.refuse(reason)
            if any(row["fields"] != fields for row in self.rows):
                return self.refuse("native_response_fields_inconsistent")
            return self.reason

    def _field_reason(self, fields):
        for key, expected, missing, mismatch in (
            ("served_model", self.expected_model, "served_model_unverified", "served_model_mismatch"),
            ("reasoning_effort", self.required_effort, "reasoning_effort_unverified", "reasoning_effort_mismatch"),
            ("context_tokens", self.required_context, "context_window_unverified", "context_window_mismatch"),
        ):
            if fields[key] == NOT_REPORTED:
                return missing
            if fields[key] != expected:
                return mismatch
        return None

    def seal(self, requests, finished):
        # Called by the native deadline cleanup. Never wait for redaction/fsync
        # before terminating the SDK. A late writer cannot revive the evidence.
        self.sealed = True
        if not self.lock.acquire(blocking=False):
            self.unpublished_after_close.set()
            return
        try:
            if requests != finished or len(self.rows) != requests or not requests:
                self.refuse("native_response_capture_incomplete")
        finally:
            self.lock.release()

    def report(self):
        if self.unpublished_after_close.is_set() or not self.lock.acquire(blocking=False):
            return empty_evidence()
        try:
            return self._report_locked()
        finally:
            self.lock.release()

    def _report_locked(self):
        with self.lock:
            try:
                self.verify()
            except ResponseCaptureRefused:
                pass
            fields = self.rows[-1]["fields"] if self.rows else empty_fields()
            reason = self.reason or (None if self.sealed and self.rows else "native_response_capture_incomplete")
            return bounded_evidence({**empty_evidence(reason), **fields, "responses": self.rows,
                                     "state": "observed" if reason is None else "unverified"})


class _ResponseArtifact:
    def __init__(self, owner, status, headers, secrets):
        self.owner, self.status, self.headers, self.secrets = owner, status, headers, secrets
        self.body = bytearray()
        self.finished = False

    def feed(self, data):
        if len(self.body) + len(data) > MAX_RESPONSE_BYTES:
            self.owner.refuse("native_response_capture_limit")
            raise ResponseCaptureRefused("native_response_capture_limit")
        self.body.extend(data)

    def finish(self, fields=None, *, complete=False):
        if self.finished:
            return self.owner.reason
        self.finished = True
        try:
            return self.owner.record(self, fields or empty_fields(), complete=complete)
        finally:
            self.secrets = ()
