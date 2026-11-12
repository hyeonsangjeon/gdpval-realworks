"""Independent, fail-closed publication checks. Never starts a process or network.

This module deliberately does not import the diagnostic redactor: a redactor
regression must not disable the last check before bytes reach disk/stdout/Actions.
Only fixed artifact names are accepted; the scan digest is handed to the next
step through GITHUB_OUTPUT, not trusted from a rehashed artifact itself.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import quote, quote_plus, unquote

from ghcp_ahp_errors import Refused

MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
CORE_FILES = frozenset({"probe.json", "handshake.json", "thread-policy.json", "wire-capture.json", "metadata-http.json"})
FILES = CORE_FILES | {"auth-smoke.json", "auth-smoke.md", "process-log.json"}
SCAN = "leak-scan.json"
PRIVATE = {"token", "accesstoken", "refreshtoken", "idtoken", "authorization", "apikey", "password",
           "secret", "credential", "credentials", "connectiontoken", "clientsecret", "cookie", "setcookie",
           "account", "accounts", "accountid", "userid", "username", "login", "email", "tenantid", "identity"}
TOKEN = re.compile(r"\b(?:github_pat_|gh[opusr]_|sk-)[A-Za-z0-9_-]{8,}|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
ASSIGNMENT = re.compile(r"(?i)\b(?:authorization|[a-z_]*token|[a-z_]*api_key|[a-z_]*password|client_secret)\s*[:=]\s*[\"']?([^\s\"'&,<>]+)")
BEARER = re.compile(r"(?i)\bBearer\s+([^\s\"'<>]+)")


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, reason="auth_publication_refused"):
    if not condition:
        raise Refused(reason)


def safe_path(value):
    path = Path(value).absolute()
    require(".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)), "auth_publication_path_refused")
    return path


def read(path):
    path = safe_path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= MAX_FILE)
        raw = stream.read(MAX_FILE + 1)
    require(len(raw) <= MAX_FILE)
    return raw


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "auth_publication_json_refused")
            value[key] = item
        return value

    def invalid(_value):
        raise Refused("auth_publication_json_refused")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError):
        raise Refused("auth_publication_json_refused") from None


class LeakScanner:
    """Use independent matching, including decoded JSON and encoded credentials."""

    def __init__(self, credential=""):
        self.forms = set()
        if credential:
            self.forms.update({credential, quote(credential, safe=""), quote_plus(credential), credential.encode().hex(),
                json.dumps(credential, ensure_ascii=True)[1:-1], json.dumps(credential, ensure_ascii=False)[1:-1]})
            for encode in (base64.b64encode, base64.urlsafe_b64encode):
                text = encode(credential.encode()).decode()
                self.forms.update({text, text.rstrip("=")})

    def _text(self, value):
        # Inspect URL-encoded echoes too; never include a match or path in errors.
        for text in (value, unquote(value)):
            require(not any(form in text for form in self.forms), "auth_publication_secret_detected")
            require(TOKEN.search(text) is None, "auth_publication_secret_detected")
            for pattern in (ASSIGNMENT, BEARER):
                require(all(match.group(1).rstrip(";,") == "[REDACTED]" for match in pattern.finditer(text)),
                        "auth_publication_secret_detected")

    def _value(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                self._text(key)
                normalized = re.sub(r"[^a-z]", "", key.lower())
                if normalized in PRIVATE or normalized.endswith(("token", "apikey", "password", "secret")):
                    require(item is None or item == "[REDACTED]", "auth_publication_secret_detected")
                self._value(item)
        elif isinstance(value, list):
            for item in value:
                self._value(item)
        elif isinstance(value, str):
            self._text(value)

    def check(self, name, raw):
        require(name in FILES | {SCAN} and type(raw) is bytes and len(raw) <= MAX_FILE)
        try:
            self._text(raw.decode("utf-8"))
            if name.endswith(".json"):
                self._value(decode(raw))
        except (UnicodeError, RecursionError):
            raise Refused("auth_publication_secret_check_failed") from None


def publish(directory, payloads, credential, identity):
    """Check every byte before creating a fresh publication directory."""
    require(set(payloads) <= FILES and {"auth-smoke.json", "auth-smoke.md", "process-log.json"} <= set(payloads))
    require(sum(len(raw) for raw in payloads.values()) <= MAX_TOTAL)
    scanner = LeakScanner(credential)
    for name, raw in payloads.items():
        scanner.check(name, raw)
    scan = encoded({"schema": "ghcp-auth-zero-turn-publication-v1", "runner": identity,
        "checked_before_write": True, "secret_matches": 0, "execution_allowed": False,
        "files": {name: {"sha256": sha(raw), "bytes": len(raw)} for name, raw in sorted(payloads.items())}})
    scanner.check(SCAN, scan)
    directory = safe_path(directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, raw in {**payloads, SCAN: scan}.items():
        with os.fdopen(os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
            stream.write(raw)
    return sha(scan)


def verify(directory, expected_sha, identity):
    """No credential is needed in the upload step; bind to the prior step digest."""
    require(type(expected_sha) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha))
    directory = safe_path(directory)
    raw = read(directory / SCAN)
    require(sha(raw) == expected_sha, "auth_publication_digest_mismatch")
    scanner = LeakScanner()
    scanner.check(SCAN, raw)
    scan = decode(raw)
    require(scan.get("schema") == "ghcp-auth-zero-turn-publication-v1" and scan.get("runner") == identity)
    require(scan.get("checked_before_write") is True and type(scan.get("secret_matches")) is int
            and scan["secret_matches"] == 0 and scan.get("execution_allowed") is False)
    files = scan.get("files")
    require(type(files) is dict and set(files) <= FILES
            and {"auth-smoke.json", "auth-smoke.md", "process-log.json"} <= set(files))
    require({p.name for p in directory.iterdir()} == set(files) | {SCAN}, "auth_publication_members_refused")
    payloads = {name: read(directory / name) for name in files}
    require(sum(len(data) for data in payloads.values()) <= MAX_TOTAL)
    for name, data in payloads.items():
        require(files[name] == {"sha256": sha(data), "bytes": len(data)}, "auth_publication_digest_mismatch")
        scanner.check(name, data)
    return payloads
