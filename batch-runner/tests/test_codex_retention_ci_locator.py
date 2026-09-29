"""Closed locator diagnostics with real predicates and simulated HTTP only."""

from copy import deepcopy
import json
import urllib.parse

import pytest

import codex_retention_ci as adapter
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from .test_codex_budget_pilot import offline  # noqa: F401; unchanged process/network/SDK guards
from .test_codex_ci_input_intake import GitHub, Response


def test_retention_job_issuance_locator_diagnostics_are_closed(monkeypatch, capsys):
    token = "SYNTHETIC_ISSUANCE_CREDENTIAL_NEVER_REAL"
    private = "PRIVATE_LOCATOR_SENTINEL"
    audience = "retention-offline-synthetic-audience"
    reason = "github_job_issuance_locator_refused"
    tenant, plan, job = (f"00000000-0000-4000-8000-00000000000{number}" for number in (1, 2, 3))
    origin = "https://pipelines.actions.githubusercontent.com"
    route = f"/{tenant}/_apis/distributedtask/hubs/build/plans/{plan}/jobs/{job}/idtoken"
    locator = origin + route + "?api-version=2.0"
    base_refusal = {"reason": reason, "launch_authorized": False, "grading_launched": False}
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("locator diagnostic reached preparation, admission or execution")

    for owner, name in ((adapter.preparation, "prepare_packet"), (adapter.controller, "stage_runtime"),
                        (adapter.controller, "execute_first_cell"), (adapter.LocalTransport, "azure"),
                        (adapter.LocalTransport, "process"), (CodexTaskDeadlineStore, "__init__"),
                        (CodexTaskDeadline, "admit_attempt")):
        monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", token)

    # These are the pre-existing synthetic accepted forms, not a recovered live URL.
    for accepted in (locator, locator.replace("api-version", "api%2Dversion")):
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", accepted)
        issued, keys = {"value": "synthetic-not-a-signed-job-token"}, {"keys": []}
        responses = [Response(json.dumps(value).encode(), content_type="application/json")
                     for value in (issued, keys)]
        http = GitHub(responses)
        transport = adapter.LocalTransport()
        monkeypatch.setattr(transport, "authority_opener", lambda: http)
        assert transport.github_job_token(audience) == (issued, keys)
        assert len(http.calls) == 2 and all(response.closed and response.reads for response in responses)
        request, timeout = http.calls[0]
        address = urllib.parse.urlsplit(request.full_url)
        assert address.scheme == "https" and address.netloc == "pipelines.actions.githubusercontent.com"
        assert address.path == route and not address.fragment
        assert urllib.parse.parse_qsl(address.query) == [("api-version", "2.0"), ("audience", audience)]
        assert request.get_header("Authorization") == "Bearer " + token
        assert 0 < timeout <= adapter.intake.REQUEST_TIMEOUT_SECONDS
        assert http.calls[1][0].full_url == adapter.OIDC_JWKS
        assert http.calls[1][0].get_header("Authorization") is None
        assert effects == []

    cases = (
        ("absent", "", "https"),
        ("http", locator.replace("https:", "http:"), "https"),
        ("userinfo", locator.replace("https://", "https://" + private + ":" + private + "@"),
         "hostname_only_authority"),
        ("port", locator.replace(origin, origin + ":443"), "hostname_only_authority"),
        ("foreign-host", "https://" + private + ".example.invalid" + route + "?api-version=2.0",
         "allowed_host_pattern"),
        ("suffix-spoof", locator.replace(origin, origin + ".example.invalid"), "allowed_host_pattern"),
        ("issuer", locator.replace(origin, adapter.OIDC_ISSUER), "not_oidc_issuer"),
        ("fragment", locator + "#" + private, "no_fragment"),
        ("opaque-route", locator.replace(tenant, private), "registered_route"),
        ("numeric-route", locator.replace(tenant, "98765432123456789"), "registered_route"),
        ("empty-segment", locator.replace("/jobs/", "//jobs/"), "registered_route"),
        ("encoded-route", locator.replace(tenant, "%50RIVATE_LOCATOR_SENTINEL"), "registered_route"),
        ("route-word", locator.replace("/distributedtask/", "/" + private + "/"), "registered_route"),
        ("api-version", locator.replace("2.0", private), "known_api_query"),
        ("blank-query-value", locator.replace("2.0", ""), "known_api_query"),
        ("duplicate-query", locator + "&api-version=2.0", "known_api_query"),
        ("supplied-audience", locator + "&audience=" + private, "known_api_query"),
        ("unknown-query", locator + "&" + private + "=" + private, "known_api_query"),
        ("malformed-query", locator + "&" + private, "query_parsed"),
        ("malformed-url", "https://[" + private + "]/" + private, "url_parsed"),
        ("many-segments", origin + "/" + "/".join([private] * 32) + "?api-version=2.0", "registered_route"),
        ("many-query-pairs", locator + "&" + "&".join([private + "=" + private] * 32), "known_api_query"),
        ("oversized", origin + "/" + private * 512 + "?api-version=2.0", "length_within_limit"),
    )
    observed = {}
    for name, refused_locator, failed_check in cases:
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", refused_locator)
        http = GitHub([])
        opener_calls = []

        def opener():
            opener_calls.append(True)
            return http

        transport = adapter.LocalTransport()
        monkeypatch.setattr(transport, "authority_opener", opener)
        with pytest.raises(adapter.RetentionCIRefused) as caught:
            transport.github_job_token(audience)
        assert type(caught.value) is adapter.RetentionCIRefused, name
        assert str(caught.value) == reason, name
        assert caught.value.__suppress_context__ and caught.value.__cause__ is None, name
        assert opener_calls == [] and http.calls == [] and effects == [], name
        payload = adapter._refusal_payload(caught.value)
        assert {key: value for key, value in payload.items() if key != "issuance_locator"} == base_refusal, name
        diagnostic = payload["issuance_locator"]
        assert diagnostic["checks"][failed_check] is False, name
        assert all(type(value) is bool for value in diagnostic["checks"].values()), name
        assert all(type(value) is int and 0 <= value <= 16 for value in diagnostic["counts"].values()), name
        assert len(diagnostic["route_skeleton"]) <= 16, name
        assert set(diagnostic["route_skeleton"]) <= adapter._LOCATOR_ROUTE_TOKENS, name
        public = adapter.owned._canonical_json(payload)
        assert len(public) <= 2048, name
        for secret in (token, private, tenant, plan, job, audience, origin, "98765432123456789",
                       "%50RIVATE_LOCATOR_SENTINEL", "https://", ".example.invalid"):
            assert secret not in public and secret not in str(caught.value), name
        observed[name] = diagnostic

    assert observed["numeric-route"]["route_skeleton"][0] == "{number}"
    assert observed["opaque-route"]["route_skeleton"] == [
        "{opaque}", "_apis", "distributedtask", "hubs", "build", "plans", "{uuid}", "jobs", "{uuid}", "idtoken"]
    assert "{empty}" in observed["empty-segment"]["route_skeleton"]
    assert observed["supplied-audience"]["counts"]["audience_parameters"] == 1
    assert observed["duplicate-query"]["counts"]["api_version_parameters"] == 2
    assert observed["unknown-query"]["counts"]["other_query_parameters"] == 1
    assert observed["malformed-query"]["checks"]["url_parsed"] is True
    assert observed["malformed-url"]["route_skeleton"] == []
    assert observed["many-segments"]["truncated"] and observed["many-segments"]["counts"]["route_segments"] == 16
    assert observed["many-query-pairs"]["truncated"] and observed["many-query-pairs"]["counts"]["query_pairs"] == 16
    assert observed["oversized"]["truncated"] and observed["oversized"]["counts"] == {}
    assert observed["oversized"]["route_skeleton"] == []

    # The CLI serializer cannot publish unrestricted or malformed exception metadata.
    for field, replacement in (
            ("extra", private), ("checks", {private: True}), ("checks", {"https": private}),
            ("counts", {"route_segments": 17}), ("counts", {"route_segments": True}),
            ("counts", {private: 1}), ("route_skeleton", [private]),
            ("route_skeleton", ["{opaque}"] * 17), ("truncated", private)):
        error = adapter.RetentionCIRefused(reason)
        error.issuance_locator = {**deepcopy(observed["opaque-route"]), field: replacement}
        assert adapter._refusal_payload(error) == base_refusal
    assert adapter._refusal_payload(adapter.RetentionCIRefused(reason)) == base_refusal
    unrelated = adapter.RetentionCIRefused("github_job_issuance_credential_required")
    unrelated.issuance_locator = observed["opaque-route"]
    assert adapter._refusal_payload(unrelated) == {**base_refusal, "reason": str(unrelated)}
    assert adapter._refusal_payload(ValueError(private)) == {
        **base_refusal, "reason": "retention_ci_verification_refused:ValueError"}

    # An accepted locator still uses the unchanged origin/status guard and closes without reading.
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", locator)
    response = Response(private.encode(), status=302, content_type="application/json")
    http = GitHub([response])
    transport = adapter.LocalTransport()
    monkeypatch.setattr(transport, "authority_opener", lambda: http)
    with pytest.raises(adapter.RetentionCIRefused) as caught:
        transport.github_job_token(audience)
    assert str(caught.value) == "github_authority_origin_or_status_refused"
    assert response.closed and response.reads == [] and len(http.calls) == 1
    assert adapter._refusal_payload(caught.value) == {**base_refusal, "reason": str(caught.value)}

    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    previous = len(http.calls)
    with pytest.raises(adapter.RetentionCIRefused) as caught:
        transport.github_job_token(audience)
    assert str(caught.value) == "github_job_issuance_credential_required"
    assert len(http.calls) == previous
    assert adapter._refusal_payload(caught.value) == {**base_refusal, "reason": str(caught.value)}
    assert adapter.main(["--reviewed-source-sha", "not-a-source-sha"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {**base_refusal, "reason": "exact_reviewed_source_required"}
    assert captured.err == "" and effects == []
