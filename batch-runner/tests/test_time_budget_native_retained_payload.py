"""Real SDK/adapter/F verification with synthetic retained HTTP payloads only."""

from contextlib import contextmanager
import gzip
import json
import os
from urllib.parse import quote

import httpx
import pytest

import gpt54_time_budget_grading_execution as execution
import gpt54_time_budget_native_grading_ci as controller
import gpt54_time_budget_native_grading_intake as subject
from gpt54_prepared_input_attestation import _identity
from .test_time_budget_native_grading_intake import (
    NAMES, PRIVATE, TOKEN, case, dual_roots, handoff_source_seed, handoff_sources, offline,
)


@pytest.mark.parametrize("scenario", [
    "plain", "resolved", "bad_hash", "pointer", "unsafe_hop", "hop_cap",
    "encoded", "oversized", "deadline", "credentials", "private_error",
])
def test_native_task3_retained_payload(case, offline, monkeypatch, capsys, record_property, scenario):
    """No successful intake/preparation verdict is mocked; no live IO is allowed."""
    from huggingface_hub import constants, hf_hub_url, utils
    from huggingface_hub.utils import _http

    canary = "hf_SECRET_CANARY_retained_payload_not_a_real_credential"
    forbidden, formatted, receipts = [], [], []

    def deny(*args, **kwargs):
        forbidden.append(True)
        raise AssertionError("retained payload proof crossed its preparation-only boundary")

    for owner, names in (
        (controller, ("_direction", "_claim", "_retain", "_commit", "_session", "preflight_routes")),
        (execution, ("execute_native_task3_grading", "execute_first_observation_grading",
                     "_execute_observation_grading", "_execution_binding", "require_execution_direction")),
        (execution.owned.LocalTransport, ("process",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, deny)
    derived_root = case.paths["destination"].parent / "derived"
    derived_reservation = derived_root.with_name(derived_root.name + execution.NATIVE_INPUT_RESERVATION)
    real_write = execution._durable_write

    def preparation_write(path, *args):
        if path != derived_reservation and not path.is_relative_to(derived_root):
            deny()  # Permit only new local derived-input staging, never an attempt claim.
        return real_write(path, *args)

    monkeypatch.setattr(execution, "_durable_write", preparation_write)
    # The existing offline fixture traps network, HF writes, model constructors,
    # Step8 grading and unowned processes, and observes the actual F preparer.
    assert execution._NATIVE_INTAKES == {}
    assert len(case.seed.step0.read_bytes()) == 218405
    data = subject.reader._bytes(case.payload)
    completion = case.request["completion"]
    completion.update(result_identity=_identity(data), result_fingerprint=case.payload["result_fingerprint"])
    revision, target = completion["output_commit"], subject.reader.metadata.TARGET
    prefix, _, _ = subject.native.shared._namespace(subject.CELL)
    result_path = f"/datasets/{target}/raw/{revision}/{prefix}/result/{subject.native.observation.RESULT}"
    records = case.payload["results"][0]["deliverable_file_records"]
    members = [prefix + "/result/upload/" + record["path"] for record in records]
    originals = [hf_hub_url(target, member, repo_type="dataset", revision=revision) for member in members]
    chains = [[original,
               f"https://huggingface.co/api/resolve-cache/datasets/{target}/{revision}/" + quote(member, safe=""),
               f"https://cdn-lfs.huggingface.co/retained-{index}?signature={canary}",
               f"https://synthetic-retained.hf.co/retained-{index}?signature={canary}"]
              for index, (original, member) in enumerate(zip(originals, members, strict=True))]
    bad_locations = {
        "host": "https://huggingface.co.attacker.invalid/payload",
        "http": "http://cdn-lfs.huggingface.co/payload",
        "userinfo": "https://user@cdn-lfs.huggingface.co/payload",
        "port": "https://cdn-lfs.huggingface.co:444/payload",
        "fragment": originals[0] + "#private",
        "revision": originals[0].replace(revision, "main"),
        "member": originals[0] + ".other",
        "encoded_member": originals[0].replace("/result/upload/", "/result/%252e%252e/"),
    }
    variants = (list(bad_locations) + ["metadata_redirect", "result_redirect"] if scenario == "unsafe_hop" else
                ["first", "second"] if scenario == "hop_cap" else
                ["announced", "stream", "short", "length_mismatch"] if scenario == "oversized" else
                ["after_initial", "second_payload", "redirect_sequence"] if scenario == "deadline" else
                ["cdn_bearer", "cdn_cookie"] if scenario == "credentials" else [scenario])

    for variant in variants:
        calls, streams, sessions, published = [], [], [], {}
        clock = [1000.0]  # Exactly representable synthetic origin; no real wait.
        factory = _http._GLOBAL_CLIENT_FACTORY
        real_stream = utils.http_stream_backoff

        class PrivateTimeout(httpx.ReadTimeout):
            def __str__(self):
                formatted.append(True)
                raise AssertionError("private transport exception was formatted")

        @contextmanager
        def observe_stream(method, url, **options):
            assert method == "GET" and options["follow_redirects"] is False and options["max_retries"] == 0
            assert options["retry_on_exceptions"] == options["retry_on_status_codes"] == ()
            assert options["headers"]["Accept-Encoding"] == "identity" and 0 < options["timeout"] <= 30
            streams.append(url)
            with real_stream(method, url, **options) as response:
                yield response  # Actual SDK backoff/client/stream implementation, not a response stub.

        class Transport(httpx.BaseTransport):
            def __init__(self, **kwargs):
                assert kwargs == {"retries": 0, "trust_env": False}

            def handle_request(self, outgoing):
                session = _http.get_session()
                sessions.append(session)
                calls.append(outgoing)
                number = len(calls)
                assert number <= 10 and outgoing.method == "GET" and not outgoing.content
                assert outgoing.url.scheme == "https" and outgoing.headers["accept-encoding"] == "identity"
                assert "cookie" not in outgoing.headers and "proxy-authorization" not in outgoing.headers
                if outgoing.url.host == "huggingface.co":
                    assert outgoing.headers["authorization"] == "Bearer " + TOKEN
                else:
                    assert "authorization" not in outgoing.headers and TOKEN not in str(outgoing.headers)
                assert "HF_TOKEN" not in os.environ and not session.follow_redirects
                assert all(0 < seconds <= 60 for seconds in outgoing.extensions["timeout"].values())
                if scenario == "deadline":
                    clock[0] += 30 if variant == "after_initial" else 15 if variant == "second_payload" else 10
                headers, status = {}, 200
                if number == 1:
                    assert outgoing.url.path == f"/api/datasets/{target}/revision/{revision}"
                    assert outgoing.url.params.multi_items() == [("expand", "private"), ("expand", "sha")]
                    body = subject.reader._bytes({"id": target, "private": True, "sha": revision})
                    if variant == "metadata_redirect":
                        status, headers = 302, {"location": originals[0]}
                elif number == 2:
                    assert outgoing.url.path == result_path and not outgoing.url.query
                    body = data
                    if variant == "result_redirect":
                        status, headers = 302, {"location": originals[0]}
                else:
                    if scenario == "private_error":
                        raise PrivateTimeout(canary + TOKEN, request=outgoing)
                    resolved = scenario in {"resolved", "hop_cap"} or (scenario == "deadline" and variant == "redirect_sequence")
                    allowed = chains if resolved else [[url] for url in originals]
                    matches = [(index, hop) for index, chain in enumerate(allowed) for hop, entry in enumerate(chain)
                               if outgoing.url == httpx.URL(entry)]
                    if scenario == "credentials" and outgoing.url.host == "cdn-lfs.huggingface.co":
                        assert variant == "cdn_cookie" and number == 4
                        return httpx.Response(302, headers={"location": "https://cdn-lfs.huggingface.co/cookie-next",
                            "set-cookie": "private_session=" + canary + "; Path=/; Secure"},
                            stream=httpx.ByteStream(b""), request=outgoing)
                    assert len(matches) == 1, (number, scenario, variant)
                    index, hop = matches[0]
                    body = case.files[records[index]["path"]]
                    if resolved and hop < 3:
                        status, headers, body = 302, {"location": chains[index][hop + 1]}, b""
                    elif scenario == "hop_cap" and index == (0 if variant == "first" else 1):
                        status, headers, body = 302, {"location": chains[index][3] + "&fifth=forbidden"}, b""
                    elif scenario == "unsafe_hop":
                        status, headers, body = 302, {"location": bad_locations[variant]}, b""
                    elif scenario == "credentials":
                        status, headers, body = 302, {"location": "https://cdn-lfs.huggingface.co/cookie-first"}, b""
                        if variant == "cdn_bearer":
                            # A contaminated SDK default cannot override token=False and leak.
                            session.headers["authorization"] = "Bearer " + TOKEN
                    elif scenario == "bad_hash":
                        body = b"x" + body[1:]
                    elif scenario == "pointer":
                        body = ("version https://git-lfs.github.com/spec/v1\noid sha256:" + records[index]["sha256"]
                                + "\nsize " + str(records[index]["size"]) + "\n").encode()
                    elif scenario == "encoded":
                        body = gzip.compress(body, mtime=0)
                        headers["content-encoding"] = "gzip"
                    elif scenario == "oversized":
                        if variant == "announced":
                            headers["content-length"] = str(records[index]["size"] + 1)
                        elif variant == "stream":
                            body += b"x"
                        elif variant == "short":
                            body = body[:-1]
                        else:
                            headers["content-length"] = str(len(body) - 1)
                if "content-length" not in headers and not (scenario == "oversized" and variant == "stream"):
                    headers["content-length"] = str(len(body))
                return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body), request=outgoing)

        with monkeypatch.context() as patch:
            patch.setattr(httpx, "HTTPTransport", Transport)
            patch.setattr(utils, "http_stream_backoff", observe_stream)
            patch.setenv("HF_TOKEN", TOKEN)
            if scenario == "deadline":
                patch.setattr(subject.storage.time, "monotonic", lambda: clock[0])
            request = subject.reader._bytes(case.request)
            arguments = {"request_json": request.decode(), "expected_request_sha256": _identity(request)["sha256"]}
            summary, point = None, None
            if scenario == "plain":
                summary = subject.prepare_retained_native_task3_grading(**arguments)
            elif scenario == "resolved":
                with execution.prepare_native_task3_grading_execution(**arguments,
                        execution_input_directory=derived_root) as handle:
                    assert handle in execution._NATIVE_INTAKES and "HF_TOKEN" not in os.environ
                    _, summary, derived = execution._native_intake(handle)
                    assert execution._native_arguments(handle)["expected_result_identity"] == _identity(data)
                    assert derived.is_dir() and (derived / subject.preparation.RESULT).is_file()
                with pytest.raises(execution.GradingExecutionRefused, match="^current_authenticated_native_intake_required$"):
                    execution._native_arguments(handle)
            else:
                with pytest.raises(subject.NativeGradingIntakeRefused) as refused:
                    if scenario == "bad_hash":
                        subject.prepare_retained_native_task3_grading(**arguments)
                    else:
                        # Cheap wire faults reuse a genuinely reconstructed marker/plan.
                        # No source/intake/preparation success verdict is substituted.
                        with subject.intake._hf_environment(online=False):
                            subject._hydrate(case.request, case.seed.plan, case.marker, TOKEN,
                                             lambda name, value: published.__setitem__(name, value))
                point = refused.value.refusal_point.value
                expected_point = ("retained_metadata" if variant == "metadata_redirect" else
                    "retained_result_download" if variant in {"result_redirect", "after_initial"} else
                    "retained_deliverable_identity" if scenario in {"bad_hash", "pointer"} or variant == "short" else
                    "retained_deliverable_download")
                assert point == expected_point
                assert TOKEN not in repr(refused.value.args) and canary not in repr(refused.value.args)
                assert offline.prepared == [] and not case.paths["destination"].exists()
                assert not (case.paths["hydration_root"] / subject.READY).exists()
                if scenario == "bad_hash":
                    assert (case.paths["hydration_root"] / subject.native.observation.RESULT).read_bytes() == data
                    assert not (case.paths["hydration_root"] / "upload").exists()
                    assert case.paths["hydration_root"].with_name(
                        case.paths["hydration_root"].name + subject.RESERVATION_SUFFIX).is_file()
                else:
                    assert all(value == (data if name == subject.native.observation.RESULT else
                        case.files[name.removeprefix("upload/")]) for name, value in published.items())
                    assert all("upload/" + record["path"] not in published for record in records[1:])
            assert _http._GLOBAL_CLIENT_FACTORY is factory and _http._GLOBAL_CLIENT is None
            assert sessions and len({id(session) for session in sessions}) == 1 and sessions[0].is_closed
            assert os.environ["HF_TOKEN"] == TOKEN and constants.HF_HUB_OFFLINE
            assert subject.SECONDS == 60

        if summary is not None:
            assert summary["status"] == "prepared" and len(offline.prepared) == 1
            assert summary["result_identity"] == _identity(data)
            assert summary["deliverables"] == {"verified_count": 2, "verified_bytes": 408601,
                "basis": "full_contents_verified_against_authenticated_result"}
            assert all(summary[key] is False for key in ("launch_allowed", "execution_enabled", "grading_performed"))
            assert (case.paths["hydration_root"] / subject.native.observation.RESULT).read_bytes() == data
            assert (case.paths["destination"] / subject.preparation.RESULT).read_bytes() == data
            for name, body in case.files.items():
                assert (case.paths["hydration_root"] / "upload" / name).read_bytes() == body
                assert (case.paths["destination"] / subject.preparation.UPLOAD / name).read_bytes() == body
            public = subject.reader._bytes(summary).decode()
            assert all(secret not in public for secret in (TOKEN, canary, PRIVATE, *NAMES, "https://"))
        expected_calls = (4 if scenario == "plain" else 10 if scenario == "resolved" else
            (6 if variant == "first" else 10) if scenario == "hop_cap" else
            {"after_initial": 2, "second_payload": 4, "redirect_sequence": 6}[variant] if scenario == "deadline" else
            (1 if variant == "metadata_redirect" else 2 if variant == "result_redirect" else 3) if scenario == "unsafe_hop" else
            (3 if variant == "cdn_bearer" else 4) if scenario == "credentials" else 3)
        assert len(calls) == expected_calls
        if scenario == "deadline":
            elapsed_per_call = 30 if variant == "after_initial" else 15 if variant == "second_payload" else 10
            assert [request.extensions["timeout"]["read"] for request in calls] == [
                60 - elapsed_per_call * index for index in range(expected_calls)]
        if scenario == "resolved":
            assert [request.url.host for request in calls[2:]] == [
                "huggingface.co", "huggingface.co", "cdn-lfs.huggingface.co", "synthetic-retained.hf.co"] * 2
            assert len(streams) == 8
        assert forbidden == formatted == offline.denied == [] and execution._NATIVE_INTAKES == {}
        assert capsys.readouterr() == ("", "")
        receipts.append({"scenario": scenario, "variant": variant, "http_GETs": len(calls),
            "resolver_GETs": len(calls) - min(2, len(calls)), "refusal_point": point,
            "real_F_preparations": len(offline.prepared), "all_scoped_sessions_closed": True,
            "forbidden_calls": 0, "bearer_cookie_CDN_transmissions": 0, "private_exception_formats": 0})
    record_property("payload_receipt", json.dumps({"cases": receipts,
        "basis": "synthetic_HTTP_sources_inputs_real_SDK_adapter_integrity_F_not_historical_payload_evidence",
        "maximum_hydration_GETs": 10, "shared_deadline_seconds": subject.SECONDS}, sort_keys=True))
