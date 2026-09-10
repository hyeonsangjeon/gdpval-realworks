"""The bisect that became possible once a request was actually served.

Run ``34442249527`` sent this route a request it could serve and got
``200 completed`` with model text back, on the host fingerprint that answered
the Codex runtime ``401`` and with the token that runtime's own auth command
minted. So the resource, the identity, the deployment name and the route are
all fine, and the refusal is something the runtime does.

That also retires the earlier transmission sweep's null result, and this file
exists because of the difference. Every arm there carried a body naming no
model and every arm came back ``400 Missed model deployment`` -- a request that
dies in the deployment router never reaches whatever refuses the runtime, so
"no property closed the gate" there was the instrument failing to see, not a
measurement that no property does.

This sweep is that experiment with a baseline that works. What is asserted here
is the instrument: that the baseline arm is byte-for-byte the request that was
served, that each arm varies exactly one thing, that a run whose baseline stops
being served stops rather than spending on arms it cannot interpret, and that
finding nothing is reported as finding nothing. Every arm costs money on the
real host; every host in this file is a socket on this machine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from diagnose_codex_foundry_connection import (  # noqa: E402
    CLOSING_SWEEP_SCHEMA,
    CODEX_ACCEPT,
    CODEX_ORIGINATOR,
    CODEX_RUNTIME_HEADERS,
    CODEX_USER_AGENT,
    NOT_ESTABLISHED_BY_THE_CLOSING_SWEEP,
    TOOL_DEFINITIONS_THE_RUNTIME_ALWAYS_SENDS,
    VALID_REQUEST_MAX_OUTPUT_TOKENS,
    VERDICT_A_PROPERTY_CLOSES_A_SERVED_REQUEST,
    VERDICT_CLOSING_SWEEP_INCONCLUSIVE,
    VERDICT_NO_PROPERTY_CLOSES_A_SERVED_REQUEST,
    classify_closing_sweep,
    closing_sweep_arms,
    closing_sweep_probe,
    main,
    servable_body,
)

# The loopback host, the completing and refusing rules, the redirected
# settings and the auth-command printer all belong to the valid request's
# tests. A second copy here would be a second thing to keep true.
from tests.test_codex_auth_discriminator import (  # noqa: E402
    _printer,
    _settings,
    _with_auth_command,
)
from tests.test_codex_valid_request import (  # noqa: E402
    _Host,
    _answers,
    _no_redaction,
    _refuses,
)

ARM_COUNT = len(closing_sweep_arms(_settings(1)))


def _probe(host: _Host, tmp_path: Path) -> dict:
    settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
    return closing_sweep_probe(settings, redact=_no_redaction)


def _by_arm(record: dict) -> dict[str, dict]:
    return {arm["arm"]: arm for arm in record["arms"]}


def _sent(host: _Host) -> dict[str, dict]:
    """The requests that arrived, keyed by arm, in the order they were sent."""
    names = [name for name, _h, _b, _w in closing_sweep_arms(_settings(1))]
    return dict(zip(names, host.calls))


# ── The baseline is the request that was served ─────────────────────────────


def test_the_baseline_arm_is_the_valid_requests_body_unchanged(tmp_path: Path):
    """The comparison is worthless if the baseline is a different request.

    Every arm's meaning is "the served request, plus this". If the baseline
    drifted from what ``--valid-request`` sends, a flip would be attributable
    to the drift and nobody would know.
    """
    with _Host(_answers()) as host:
        _probe(host, tmp_path)

    settings = _settings(host.port)
    assert _sent(host)["baseline"]["body"] == servable_body(settings)


def test_the_baseline_arm_adds_no_header_of_its_own(tmp_path: Path):
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    headers = _sent(host)["baseline"]["headers"]
    assert _by_arm(record)["baseline"]["added_headers"] == []
    for name in {"originator", *CODEX_RUNTIME_HEADERS}:
        assert name not in headers, f"the baseline sent {name}"
    assert headers["accept"] == "application/json"


# ── One property per arm ────────────────────────────────────────────────────


def test_every_arm_varies_exactly_one_thing_against_the_baseline(tmp_path: Path):
    """Isolated, not cumulative.

    A cumulative sweep's first flip is attributable only to "this arm or an
    earlier one". The extra requests buy the difference between "this property
    is sufficient" and "something before it was", which is the only reading
    worth having.
    """
    settings = _settings(1)
    base = servable_body(settings)
    combination = "everything"

    for name, extra_headers, body, _why in closing_sweep_arms(settings):
        if name in ("baseline", combination):
            continue
        changed_body = set() if body is None else {
            key for key in set(body) | set(base) if body.get(key) != base.get(key)
        }
        # Headers or body, and within the body a single key. `stream_true` is
        # the one arm allowed both, and the reason is in its own `why`: a
        # streaming body with a JSON Accept is not a request anyone sends, so
        # the pair travels together and the header-only arm above it is what
        # separates them.
        if name == "stream_true":
            assert changed_body == {"stream"}, (name, changed_body)
            assert set(extra_headers) == {"Accept"}, (name, extra_headers)
            continue
        if extra_headers:
            assert not changed_body, f"{name} varies a header and a body field"
        else:
            assert len(changed_body) == 1, (name, changed_body)


def test_the_combination_arm_carries_every_property_the_others_do(tmp_path: Path):
    """Otherwise a property that only closes the gate in company is missed."""
    settings = _settings(1)
    arms = {name: (h, b) for name, h, b, _w in closing_sweep_arms(settings)}
    combined_headers, combined_body = arms["everything"]

    for name, (headers, body) in arms.items():
        if name in ("baseline", "everything"):
            continue
        for key, value in headers.items():
            assert combined_headers.get(key) == value, f"{name}: {key} is missing"
        if body is None:
            continue
        base = servable_body(settings)
        for key, value in body.items():
            if base.get(key) != value:
                assert combined_body is not None
                assert combined_body.get(key) == value, f"{name}: {key} is missing"


def test_the_arms_reproduce_the_runtimes_headers_and_not_a_guess(tmp_path: Path):
    """These names came off the wire in test_what_one_codex_turn_actually_sends.

    Read from the same constants the earlier sweep used, so a runtime version
    bump that changes them changes both sweeps at once.
    """
    settings = _settings(1)
    arms = {name: h for name, h, _b, _w in closing_sweep_arms(settings)}

    assert arms["accept_event_stream"] == {"Accept": CODEX_ACCEPT}
    assert arms["originator_and_user_agent"] == {
        "originator": CODEX_ORIGINATOR,
        "User-Agent": CODEX_USER_AGENT,
    }
    assert arms["codex_runtime_headers"] == dict(CODEX_RUNTIME_HEADERS)


def test_the_body_arms_reach_the_size_and_count_that_were_measured(tmp_path: Path):
    """Size and count, which is what these arms claim to vary -- not wording.

    The runtime's instructions and tools were measured at over 10 KB each. An
    arm that sent a one-line `instructions` would be testing the presence of a
    field nobody suspects rather than the payload nobody has tried.
    """
    settings = _settings(1)
    arms = {name: b for name, _h, b, _w in closing_sweep_arms(settings)}

    instructions = arms["large_instructions"]["instructions"]
    assert len(instructions.encode("utf-8")) > 10_000, len(instructions)

    tools = arms["ten_tool_definitions"]["tools"]
    assert len(tools) == TOOL_DEFINITIONS_THE_RUNTIME_ALWAYS_SENDS
    assert len(json.dumps(tools).encode("utf-8")) > 10_000


def test_no_arm_carries_benchmark_content_or_a_task(tmp_path: Path):
    """A connectivity check. The filler is this repository's own sentences."""
    settings = _settings(1)
    for name, _headers, body, _why in closing_sweep_arms(settings):
        payload = json.dumps(body or servable_body(settings))
        assert "gdpval" not in payload.lower(), name
        assert body is None or body["input"] == servable_body(settings)["input"]


def test_every_arm_keeps_the_output_ceiling(tmp_path: Path):
    """Nine arms at an unbounded ceiling is a different experiment's budget."""
    settings = _settings(1)
    for name, _headers, body, _why in closing_sweep_arms(settings):
        effective = body if body is not None else servable_body(settings)
        assert effective["max_output_tokens"] == VALID_REQUEST_MAX_OUTPUT_TOKENS, name


def test_an_arms_overrides_do_not_leak_into_the_next_arm(tmp_path: Path):
    """`servable_body` is built per call for this reason.

    A shared dict would make `everything` the accumulated state of whatever ran
    before it, and the arm order would silently become part of the result.
    """
    with _Host(_answers()) as host:
        _probe(host, tmp_path)

    sent = _sent(host)
    assert "instructions" not in sent["ten_tool_definitions"]["body"]
    assert "tools" not in sent["large_instructions"]["body"]
    assert sent["store_true"]["body"]["stream"] is False
    assert sent["stream_true"]["body"]["store"] is False


# ── How many requests, and when it stops ────────────────────────────────────


def test_one_request_per_arm_and_no_more(tmp_path: Path):
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert len(host.calls) == ARM_COUNT
    assert record["requests_sent"] == ARM_COUNT
    assert record["requests_planned"] == ARM_COUNT


def test_a_refused_arm_is_not_retried(tmp_path: Path):
    """The failing path is where a retry loop would be silent and expensive."""
    seen: list[int] = []

    def rule(_headers, body):
        seen.append(1)
        if body.get("store"):
            return 401, {"error": {"message": "Access denied"}}
        return 200, {"id": "r", "model": body.get("model"), "output_text": "ok"}

    with _Host(rule) as host:
        record = _probe(host, tmp_path)

    assert len(seen) == ARM_COUNT
    assert record["requests_sent"] == ARM_COUNT


def test_a_baseline_that_is_not_served_stops_before_the_paid_arms(tmp_path: Path):
    """The premise is re-tested every run, and a failed premise is not bought.

    If the baseline is refused, every later arm is measured against nothing.
    They are not free, so they are not sent.
    """
    with _Host(_refuses(500, "the route is having a bad day")) as host:
        record = _probe(host, tmp_path)

    assert len(host.calls) == 1, "arms were sent after the premise failed"
    assert record["requests_sent"] == 1
    assert record["verdict"] == VERDICT_CLOSING_SWEEP_INCONCLUSIVE
    assert "not served" in record["verdict_note"]


def test_a_mint_failure_sends_nothing_at_all(tmp_path: Path):
    settings = _settings(9)  # a port nothing is listening on
    settings = _with_auth_command(settings, ["/nonexistent/auth/command"])
    record = closing_sweep_probe(settings, redact=_no_redaction)

    assert record["token"]["minted"] is False
    assert record["requests_sent"] == 0
    assert record["arms"] == []
    assert record["verdict"] == VERDICT_CLOSING_SWEEP_INCONCLUSIVE


# ── Reading the result ──────────────────────────────────────────────────────


def _arm(name: str, status: int | None, error: str | None = None) -> dict:
    return {"arm": name, "status": status, "error": error}


def test_an_arm_refused_at_the_gate_is_named():
    verdict, note, closed = classify_closing_sweep(
        [_arm("baseline", 200), _arm("store_true", 401)]
    )
    assert verdict == VERDICT_A_PROPERTY_CLOSES_A_SERVED_REQUEST
    assert closed == ["store_true"]
    assert "store_true" in note


def test_a_403_counts_as_the_gate_closing():
    """Forbidden and unauthorized are both the gate; only one was ever seen."""
    _verdict, _note, closed = classify_closing_sweep(
        [_arm("baseline", 200), _arm("codex_runtime_headers", 403)]
    )
    assert closed == ["codex_runtime_headers"]


def test_several_arms_closing_are_all_named():
    _verdict, _note, closed = classify_closing_sweep(
        [
            _arm("baseline", 200),
            _arm("accept_event_stream", 401),
            _arm("store_true", 200),
            _arm("everything", 401),
        ]
    )
    assert closed == ["accept_event_stream", "everything"]


def test_an_arm_rejected_for_its_shape_is_not_a_gate_closing():
    """A 400 is the route complaining about the request, not about permission.

    Reporting one as a closed gate would send somebody to ask for a role over
    a malformed field.
    """
    verdict, _note, closed = classify_closing_sweep(
        [_arm("baseline", 200), _arm("ten_tool_definitions", 400)]
    )
    assert verdict == VERDICT_NO_PROPERTY_CLOSES_A_SERVED_REQUEST
    assert closed == []


def test_finding_nothing_is_reported_as_finding_nothing():
    verdict, note, closed = classify_closing_sweep(
        [_arm("baseline", 200), _arm("store_true", 200), _arm("everything", 200)]
    )
    assert verdict == VERDICT_NO_PROPERTY_CLOSES_A_SERVED_REQUEST
    assert closed == []
    assert "transport" in note


def test_a_baseline_that_did_not_reach_the_host_is_inconclusive():
    verdict, _note, closed = classify_closing_sweep(
        [_arm("baseline", None, error="URLError: unreachable"), _arm("x", 401)]
    )
    assert verdict == VERDICT_CLOSING_SWEEP_INCONCLUSIVE
    assert closed == []


def test_a_refused_baseline_makes_every_arm_uninterpretable():
    """Not "everything closes the gate" -- nothing was open to close."""
    verdict, _note, closed = classify_closing_sweep(
        [_arm("baseline", 401), _arm("store_true", 401)]
    )
    assert verdict == VERDICT_CLOSING_SWEEP_INCONCLUSIVE
    assert closed == []


def test_a_missing_baseline_is_inconclusive():
    verdict, _note, _closed = classify_closing_sweep([_arm("store_true", 401)])
    assert verdict == VERDICT_CLOSING_SWEEP_INCONCLUSIVE


# ── The record ──────────────────────────────────────────────────────────────


def test_the_record_admits_it_is_paid(tmp_path: Path):
    """The field the redaction check reads to pick its rules.

    Writing `false` here would hide a paid record in the branch written for
    free ones, which is the thing that check exists to catch.
    """
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert record["schema"] == CLOSING_SWEEP_SCHEMA
    assert record["inference_requested"] is True


def test_the_record_declares_its_ceilings_before_the_run(tmp_path: Path):
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    limits = record["limits"]
    assert limits["arms"] == ARM_COUNT
    assert limits["attempts_per_arm"] == 1
    assert limits["concurrency"] == 1
    assert limits["max_output_tokens"] == VALID_REQUEST_MAX_OUTPUT_TOKENS
    assert "no retry" in limits["abort_on"]


def test_every_arm_records_why_it_was_sent(tmp_path: Path):
    """A record of nine statuses nobody can read is not a record."""
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    for arm in record["arms"]:
        assert arm["why"], arm["arm"]
        assert arm["body_sha256"]
        assert arm["body_bytes"] > 0


def test_usage_is_kept_per_arm_and_no_price_is_invented(tmp_path: Path):
    with _Host(
        _answers(usage={"input_tokens": 13, "output_tokens": 5, "total_tokens": 18})
    ) as host:
        record = _probe(host, tmp_path)

    for arm in record["arms"]:
        usage = arm["usage"]
        assert usage["reported"] is True
        assert usage["input_tokens"] == 13
        assert usage["price_usd"] is None
        assert usage["pricing"] == "partial"


def test_the_record_names_what_it_still_does_not_establish(tmp_path: Path):
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert record["not_established"] == list(NOT_ESTABLISHED_BY_THE_CLOSING_SWEEP)
    joined = " ".join(record["not_established"]).lower()
    assert "urllib" in joined, "a urllib result must not read as a runtime result"
    assert "transport" in joined
    assert "free" in joined


def test_the_record_names_no_resource_and_carries_no_token(tmp_path: Path):
    """Redaction, on the record that is uploaded."""
    with _Host(_refuses(401, "Access denied for account contoso-foundry")) as host:
        settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
        record = closing_sweep_probe(
            settings, redact=lambda value: None if value is None else "<redacted>"
        )

    text = json.dumps(record)
    assert "contoso-foundry" not in text
    assert "Bearer" not in text


# ── The command line ────────────────────────────────────────────────────────


def _run_main(host: _Host, tmp_path: Path, monkeypatch) -> tuple[int, dict]:
    settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
    monkeypatch.setattr(
        "diagnose_codex_foundry_connection.settings_from_environment",
        lambda _deployment: settings,
    )
    out = tmp_path / "record.json"
    code = main(["--deployment", "a-deployment", "--closing-sweep", "--out", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_a_conclusive_run_exits_zero_even_when_nothing_closed_the_gate(
    tmp_path: Path, monkeypatch
):
    """The exit code answers "did the instrument measure", not "was it news"."""
    with _Host(_answers()) as host:
        code, record = _run_main(host, tmp_path, monkeypatch)

    assert code == 0
    assert record["verdict"] == VERDICT_NO_PROPERTY_CLOSES_A_SERVED_REQUEST


def test_a_run_that_could_not_measure_exits_non_zero(tmp_path: Path, monkeypatch):
    with _Host(_refuses(500, "bad day")) as host:
        code, record = _run_main(host, tmp_path, monkeypatch)

    assert code == 1
    assert record["verdict"] == VERDICT_CLOSING_SWEEP_INCONCLUSIVE


def test_the_sweep_cannot_be_asked_for_alongside_another_probe(tmp_path: Path):
    """Different questions, different records, one file to write them to."""
    with pytest.raises(SystemExit):
        main(["--deployment", "a", "--closing-sweep", "--valid-request"])
    with pytest.raises(SystemExit):
        main(["--deployment", "a", "--closing-sweep", "--send-request"])


def test_the_sweep_is_off_unless_it_is_asked_for(tmp_path: Path, monkeypatch):
    """The default path writes a plan and buys nothing."""
    monkeypatch.setattr(
        "diagnose_codex_foundry_connection.settings_from_environment",
        lambda _deployment: _settings(1),
    )
    out = tmp_path / "record.json"
    code = main(["--deployment", "a-deployment", "--out", str(out)])
    record = json.loads(out.read_text(encoding="utf-8"))

    assert code == 0
    assert record["schema"] != CLOSING_SWEEP_SCHEMA
