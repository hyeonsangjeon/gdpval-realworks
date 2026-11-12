"""Synthetic credential fixtures only. No credential lookup, host or network."""

import base64
import json
from pathlib import Path
from urllib.parse import quote

import pytest

import ghcp_ahp_auth_publication as pub
from ghcp_ahp_errors import Refused

CANARY = 'SYNTHETIC_AUTH_ONLY_7af2c9_"?+/='
IDENTITY = {"github_run_id": "123", "github_run_attempt": "1", "github_sha": "a" * 40}


def payloads():
    return {"auth-smoke.json": pub.encoded({"status": "fixture", "execution_allowed": False}),
            "auth-smoke.md": b"# Fixture only\n", "process-log.json": pub.encoded({"message": "[REDACTED]"})}


@pytest.mark.parametrize("name", ["auth-smoke.json", "process-log.json", "auth-smoke.md"])
@pytest.mark.parametrize("form", ["plain", "url", "base64", "base64url", "unpadded", "hex", "unicode"])
def test_independent_scanner_rejects_all_credential_forms_without_echoing(name, form):
    text = {"plain": CANARY, "url": quote(CANARY, safe=""), "base64": base64.b64encode(CANARY.encode()).decode(),
            "base64url": base64.urlsafe_b64encode(CANARY.encode()).decode(),
            "unpadded": base64.b64encode(CANARY.encode()).decode().rstrip("="), "hex": CANARY.encode().hex(),
            "unicode": CANARY}[form]
    raw = pub.encoded({"innocent": text}) if name.endswith(".json") else text.encode()
    if form == "unicode" and name.endswith(".json"):
        raw = ('{"innocent":"' + ''.join('\\u%04x' % ord(char) for char in CANARY) + '"}').encode()
    with pytest.raises(Refused, match="^auth_publication_secret_detected$") as error:
        pub.LeakScanner(CANARY).check(name, raw)
    assert CANARY not in str(error.value) and text not in str(error.value)


@pytest.mark.parametrize("value", ["gho_SYNTHETIC_NOT_VALID_123", "github_pat_SYNTHETIC_NOT_VALID_123", "sk-SYNTHETIC_NOT_VALID_123",
    "Bearer UNKNOWN_SYNTHETIC_NONCE", "authorization=UNKNOWN_SYNTHETIC_NONCE", "access_token=UNKNOWN_SYNTHETIC_NONCE"])
def test_scanner_also_refuses_unseeded_secret_syntax(value):
    with pytest.raises(Refused, match="secret_detected"):
        pub.LeakScanner().check("process-log.json", pub.encoded({"message": value}))


@pytest.mark.parametrize("key", ["token", "Authorization", "openai_api_key", "refreshToken", "client-secret",
                                  "cookie", "set-cookie", "accountId", "username", "email"])
def test_unknown_private_fields_must_already_be_masked(key):
    with pytest.raises(Refused, match="secret_detected"):
        pub.LeakScanner().check("auth-smoke.json", pub.encoded({key: "INERT_VALUE"}))
    pub.LeakScanner().check("auth-smoke.json", pub.encoded({key: "[REDACTED]"}))


@pytest.mark.parametrize("raw", [b'\xff', b'{"a":1,"a":2}', b'{"a":NaN}', b'{broken'])
def test_invalid_encoding_or_ambiguous_json_cannot_be_published(raw):
    with pytest.raises(Refused):
        pub.LeakScanner(CANARY).check("auth-smoke.json", raw)


def test_masked_authorization_and_usage_counts_are_not_secrets():
    value = {"authorization": "[REDACTED]", "message": "Bearer [REDACTED]", "inputTokens": 0,
             "model_context_window": 1000000, "execution_allowed": False, "auth_source": "COPILOT_GITHUB_TOKEN"}
    pub.LeakScanner(CANARY).check("auth-smoke.json", pub.encoded(value))


def test_all_bytes_are_checked_before_the_first_publication_write(tmp_path):
    files = payloads()
    files["process-log.json"] = pub.encoded({"late_echo": CANARY})
    with pytest.raises(Refused, match="secret_detected"):
        pub.publish(tmp_path / "public", files, CANARY, IDENTITY)
    assert not (tmp_path / "public").exists()


def test_exact_publication_round_trip_binds_files_and_identity(tmp_path):
    target = tmp_path / "public"
    digest = pub.publish(target, payloads(), CANARY, IDENTITY)
    assert pub.verify(target, digest, IDENTITY) == payloads()
    scan = pub.decode((target / pub.SCAN).read_bytes())
    assert scan["checked_before_write"] is True and scan["secret_matches"] == 0
    assert scan["execution_allowed"] is False and CANARY not in json.dumps(scan)
    with pytest.raises(FileExistsError):
        pub.publish(target, payloads(), CANARY, IDENTITY)


@pytest.mark.parametrize("damage", ["bytes", "missing", "extra", "symlink", "hardlink", "manifest", "rehashed", "identity"])
def test_publication_tampering_is_refused_even_when_local_manifest_is_rehashed(tmp_path, damage):
    target = tmp_path / "public"
    digest = pub.publish(target, payloads(), CANARY, IDENTITY)
    path = target / "auth-smoke.md"
    identity = dict(IDENTITY)
    if damage in {"bytes", "rehashed"}:
        path.write_bytes(b"tampered")
    elif damage == "missing":
        path.unlink()
    elif damage == "extra":
        (target / "not-allowlisted.log").write_text("inert")
    elif damage == "symlink":
        outside = tmp_path / "outside"
        path.rename(outside)
        path.symlink_to(outside)
    elif damage == "hardlink":
        (tmp_path / "hardlink").hardlink_to(path)
    elif damage == "manifest":
        (target / pub.SCAN).write_bytes(b"{}")
    else:
        identity["github_sha"] = "b" * 40
    if damage == "rehashed":
        scan = pub.decode((target / pub.SCAN).read_bytes())
        scan["files"][path.name] = {"bytes": len(path.read_bytes()), "sha256": pub.sha(path.read_bytes())}
        (target / pub.SCAN).write_bytes(pub.encoded(scan))
    with pytest.raises((Refused, FileNotFoundError)):
        pub.verify(target, digest, identity)


def test_symlink_parent_and_oversized_file_are_refused(tmp_path, monkeypatch):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(Refused, match="path_refused"):
        pub.publish(alias / "public", payloads(), CANARY, IDENTITY)
    file = actual / "oversized"
    file.write_bytes(b"12345")
    monkeypatch.setattr(pub, "MAX_FILE", 4)
    with pytest.raises(Refused):
        pub.read(file)


def test_no_shared_redactor_implementation_can_disable_the_scanner():
    source = Path(pub.__file__).read_text()
    assert "import ghcp_ahp_diagnostics" not in source
    assert "from ghcp_ahp_diagnostics" not in source
