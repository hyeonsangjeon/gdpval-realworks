"""A refused Code Interpreter call now says what refused it.

The Azure code interpreter is one of the three run places the execution
envelope comparison measures. Its five-task advance check failed on all five
tasks, and every task recorded the same thing::

    task_execution_error:PermissionDeniedError

That is the OpenAI SDK's class for HTTP 403. It says the call was refused. It
does not say *what* refused it, and the two facts that would say — the status
and the provider's own error code — were thrown away before anything could
record them.

They were thrown away on purpose. ``core/code_interpreter.py`` wraps the
client in ``_CodeInterpreterProviderCallProxy`` whenever the run is on a typed
Azure route, and the proxy replaces every provider exception with a
``RuntimeError`` carrying the class name and nothing else, chained
``from None``. That redaction exists because the raw exception's text carries
the endpoint, the account, the project and the deployment, and this repository
publishes its run records. Keeping the redaction is not negotiable.

But redaction and diagnosis are not actually opposed here. An HTTP status is a
number. A provider error code is an identifier — ``PermissionDenied``,
``AuthorizationFailed``, ``DeploymentNotFound``, ``insufficient_quota``. An
endpoint, an account name or a sentence of prose cannot be spelled without a
dot, a dash, a slash, a colon or a space. So the two useful facts are
admitted by *shape*, and everything else stays out because it cannot take that
shape — not because somebody listed it.

These tests hold both halves at once: that the refusal now names itself, and
that nothing else came with it.

Nothing here calls a model, signs in to a cloud account, or spends anything.
The one realistic refusal is built locally out of ``httpx`` objects.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import PermissionDeniedError

from core.code_interpreter import (
    CodeInterpreterRunner,
    _CodeInterpreterProviderCallProxy,
    _provider_error_classification,
    _redacted_provider_error_message,
)
from core.public_error import public_task_error_text

# What a real refusal from this project's Foundry endpoint would carry along
# with it. Every one of these must be absent from anything the run records.
PRIVATE_URL = "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/api/projects/gdpval-realworks/openai/v1/responses"
PRIVATE_PROSE = (
    "Principal 00000000-0000-0000-0000-000000000000 does not have "
    "authorization to perform action 'Microsoft.CognitiveServices/"
    "accounts/OpenAI/responses/action' over scope "
    "/subscriptions/.../hjeon-fdpo-foundry-eus2/projects/gdpval-realworks"
)


def _refusal(body: object, *, status: int = 403) -> PermissionDeniedError:
    """A 403 shaped the way the SDK shapes one, built without a network."""
    request = httpx.Request("POST", PRIVATE_URL)
    if isinstance(body, (dict, list)):
        response = httpx.Response(status, request=request, json=body)
    else:
        response = httpx.Response(status, request=request, text=str(body))
    return PermissionDeniedError(
        f"Error code: {status} - {PRIVATE_PROSE}",
        response=response,
        body=body,
    )


def _injected_client(response=None):
    """The same stand-in client the neighbouring tests inject."""
    if response is None:
        response = SimpleNamespace(output=[], output_text="injected result")
    return SimpleNamespace(
        responses=SimpleNamespace(create=Mock(return_value=response)),
        files=SimpleNamespace(create=Mock(), delete=Mock(), content=Mock()),
        containers=SimpleNamespace(
            create=Mock(),
            files=SimpleNamespace(
                list=Mock(),
                content=SimpleNamespace(retrieve=Mock()),
            ),
        ),
        close=Mock(),
    )


# ── the contract that was already there ───────────────────────────────────


def test_a_refusal_with_nothing_to_classify_reads_exactly_as_it_did() -> None:
    """The frozen sentence stays frozen when there is nothing to add.

    ``tests/test_code_interpreter.py`` asserts this string by equality in five
    places. A classification that appended itself unconditionally — an empty
    bracket, a ``None``, an ``unknown`` — would break all five. Absent means
    absent.
    """
    assert (
        _redacted_provider_error_message(OSError(PRIVATE_PROSE))
        == "Code Interpreter provider error (OSError)"
    )
    assert _provider_error_classification(OSError(PRIVATE_PROSE)) == ""


def test_the_chain_is_still_dropped_when_the_proxy_raises() -> None:
    """Redaction is worth nothing if the original hangs off the new one.

    ``raise ... from None`` clears ``__cause__`` but leaves ``__context__``
    set whenever the raise happens inside the ``except`` block. The proxy
    therefore builds the message inside the block and raises outside it. This
    holds that arrangement, because it is invisible in the reading and the
    whole redaction leaks through ``__context__`` if it is undone.
    """
    client = _injected_client()
    client.responses.create.side_effect = _refusal(
        {"error": {"code": "PermissionDenied", "message": PRIVATE_PROSE}}
    )
    proxy = _CodeInterpreterProviderCallProxy(client)

    with pytest.raises(RuntimeError) as caught:
        proxy.responses.create(model="deployment")

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


# ── what the refusal may now say ──────────────────────────────────────────


def test_an_azure_refusal_carries_its_status_and_its_own_code() -> None:
    """The case this was written for, in the shape Azure sends it."""
    message = _redacted_provider_error_message(
        _refusal({"error": {"code": "PermissionDenied", "message": PRIVATE_PROSE}})
    )

    assert message == (
        "Code Interpreter provider error "
        "(PermissionDeniedError, http 403, code PermissionDenied)"
    )


def test_the_sdk_cannot_see_a_nested_code_so_the_body_is_read_as_well() -> None:
    """Why reading the body is load-bearing rather than belt-and-braces.

    The OpenAI SDK lifts ``code`` and ``type`` off the *top* of the JSON body.
    Azure nests both one level down under ``error``, so on a real Azure
    refusal ``exc.code`` is ``None`` and reading the attribute alone would
    have produced the status and nothing else — which is most of the way to
    learning nothing. This asserts the SDK's blindness directly, so that a
    later simplification down to ``exc.code`` fails here with the reason.
    """
    refusal = _refusal(
        {"error": {"code": "AuthorizationFailed", "message": PRIVATE_PROSE}}
    )

    assert refusal.code is None, "the SDK started reading nested codes"
    assert "code AuthorizationFailed" in _redacted_provider_error_message(refusal)


def test_an_openai_shaped_refusal_is_read_off_the_exception() -> None:
    """The flat shape, which the SDK does lift onto the exception."""
    refusal = _refusal(
        {"code": "insufficient_quota", "type": "insufficient_quota",
         "message": PRIVATE_PROSE}
    )

    assert refusal.code == "insufficient_quota"
    assert "code insufficient_quota" in _redacted_provider_error_message(refusal)


def test_a_refusal_with_no_readable_body_still_names_its_status() -> None:
    """Azure answers some refusals with HTML or an empty body.

    Half an answer is still an answer: knowing it was a 403 rather than a 429
    or a 404 decides where to look next.
    """
    message = _redacted_provider_error_message(_refusal("<html>Forbidden</html>"))

    assert message == (
        "Code Interpreter provider error (PermissionDeniedError, http 403)"
    )


# ── what it may not say ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code, why",
    [
        (PRIVATE_URL, "is the endpoint"),
        ("hjeon-fdpo-foundry-eus2", "is the account, and has dashes"),
        ("gdpval-realworks", "is the project"),
        ("gpt-5.4", "is the deployment"),
        ("services.ai.azure.com", "is a host"),
        (PRIVATE_PROSE, "is the whole prose message"),
        ("Permission Denied", "has a space"),
        ("Microsoft.CognitiveServices/accounts", "is a path"),
        ("code:403", "has a colon"),
        ("Denied\nby policy", "has a newline"),
        ("A" * 65, "is longer than a code"),
        ("", "is empty"),
    ],
)
def test_a_code_that_is_not_code_shaped_is_dropped(code: str, why: str) -> None:
    """Everything worth hiding needs a character the shape does not admit."""
    message = _redacted_provider_error_message(
        _refusal({"error": {"code": code, "message": PRIVATE_PROSE}})
    )

    assert message == (
        "Code Interpreter provider error (PermissionDeniedError, http 403)"
    ), f"a code that {why} was admitted"
    assert code not in message or code == ""


@pytest.mark.parametrize(
    "code", [403, None, True, {"code": "PermissionDenied"}, ["PermissionDenied"]]
)
def test_a_code_that_is_not_text_is_dropped(code: object) -> None:
    """A body is somebody else's JSON; its fields need not be strings."""
    message = _redacted_provider_error_message(
        _refusal({"error": {"code": code, "message": PRIVATE_PROSE}})
    )

    assert message == (
        "Code Interpreter provider error (PermissionDeniedError, http 403)"
    )


@pytest.mark.parametrize(
    "status, why",
    [
        (True, "is a bool, which Python counts as an int"),
        ("403", "is text"),
        (999, "is not a status"),
        (99, "is not a status"),
        (403.0, "is a float"),
        (None, "is absent"),
    ],
)
def test_a_status_that_is_not_a_status_is_dropped(status, why: str) -> None:
    """A status is admitted by being a whole number in the range of one.

    ``isinstance(True, int)`` is ``True`` in Python, so a bool would slip past
    a type check alone. It does not need a check of its own here: ``True`` is
    ``1`` and ``False`` is ``0``, and the range refuses both. Writing a
    separate ``isinstance(status, bool)`` guard would look careful and do
    nothing, so the range is the only thing standing there — and the mutation
    that widens it is what proves the range is load-bearing.
    """

    class _Refused(Exception):
        pass

    exc = _Refused()
    exc.status_code = status

    assert _provider_error_classification(exc) == "", f"a status that {why}"


def test_nothing_but_the_status_and_the_code_reaches_the_redacted_text() -> None:
    """The sweep: build a refusal carrying every private thing at once."""
    refusal = _refusal(
        {
            "error": {
                "code": "PermissionDenied",
                "message": PRIVATE_PROSE,
                "target": PRIVATE_URL,
                "innererror": {"account": "hjeon-fdpo-foundry-eus2"},
            }
        }
    )
    message = _redacted_provider_error_message(refusal)

    for secret in (
        PRIVATE_URL,
        PRIVATE_PROSE,
        "hjeon-fdpo-foundry-eus2",
        "gdpval-realworks",
        "azure.com",
        "subscriptions",
    ):
        assert secret not in message


def test_the_free_text_the_request_and_the_response_are_never_even_read() -> None:
    """Proved by making them explode rather than by reading the result.

    Checking that the prose is absent from the output only shows it was not
    *kept*. This shows it was not *touched*, which is the property that
    survives somebody later adding a formatting step.
    """

    class _RefusalThatExplodesIfItsProseIsRead(Exception):
        status_code = 403
        code = "AuthorizationFailed"

        @property
        def message(self):  # pragma: no cover - the assert is the point
            raise AssertionError("the free-text message was read")

        @property
        def response(self):  # pragma: no cover - the assert is the point
            raise AssertionError("the response was read")

        @property
        def request(self):  # pragma: no cover - the assert is the point
            raise AssertionError("the request was read")

        @property
        def args(self):  # pragma: no cover - the assert is the point
            raise AssertionError("the exception arguments were read")

    message = _redacted_provider_error_message(
        _RefusalThatExplodesIfItsProseIsRead()
    )

    assert message == (
        "Code Interpreter provider error "
        "(_RefusalThatExplodesIfItsProseIsRead, http 403, "
        "code AuthorizationFailed)"
    )


def test_an_attribute_that_raises_does_not_break_the_redaction() -> None:
    """These are attributes on somebody else's object, so they may raise.

    ``getattr(obj, name, default)`` only swallows ``AttributeError``. A
    property raising anything else would escape the redaction entirely and
    surface the raw exception, which is the failure mode redaction exists to
    prevent. So the failure has to be to *less* detail, never to more.
    """

    class _RefusalWhoseAttributesRaise(Exception):
        @property
        def status_code(self):
            raise RuntimeError(PRIVATE_PROSE)

        @property
        def code(self):
            raise RuntimeError(PRIVATE_PROSE)

        @property
        def type(self):
            raise RuntimeError(PRIVATE_PROSE)

        @property
        def body(self):
            raise RuntimeError(PRIVATE_PROSE)

    message = _redacted_provider_error_message(_RefusalWhoseAttributesRaise())

    assert message == (
        "Code Interpreter provider error (_RefusalWhoseAttributesRaise)"
    )
    assert PRIVATE_PROSE not in message


# ── where the new sentence ends up ────────────────────────────────────────


def test_the_runner_returns_the_classified_message(capsys) -> None:
    """``run`` puts it in ``error``, and that is what the run log prints.

    ``step2_run_inference.py`` writes ``result["error"]`` straight into the
    per-task progress line — the exp032 log reads ``✗ Code Interpreter
    provider error (PermissionDeniedError), mem=227MB``. So classifying the
    message here is the whole of what makes the next run's log say why.
    """
    client = _injected_client()
    client.responses.create.side_effect = _refusal(
        {"error": {"code": "PermissionDenied", "message": PRIVATE_PROSE}}
    )
    runner = CodeInterpreterRunner(client=client, redact_provider_errors=True)

    result = runner.run(task_prompt="Create a file", model="deployment")

    assert result["success"] is False
    assert result["error"] == (
        "Code Interpreter provider error "
        "(PermissionDeniedError, http 403, code PermissionDenied)"
    )
    captured = capsys.readouterr()
    assert PRIVATE_PROSE not in captured.out + captured.err + json.dumps(result)
    assert PRIVATE_URL not in captured.out + captured.err + json.dumps(result)


def test_the_published_record_still_names_only_the_exception_class() -> None:
    """The persisted result is unchanged, which is the point.

    ``_public_persisted_results`` projects every error through
    ``public_task_error_text`` before it is written or uploaded, and that
    keeps the class name alone. The classification is for the run log and the
    operator; the published artefact carries exactly what it carried before,
    so nothing downstream of it has to change.
    """
    message = _redacted_provider_error_message(
        _refusal({"error": {"code": "PermissionDenied", "message": PRIVATE_PROSE}})
    )

    assert public_task_error_text(message) == (
        "task_execution_error:PermissionDeniedError"
    )


def test_the_classification_is_absent_when_the_route_is_not_redacted() -> None:
    """Unredacted runs are untouched: they already keep the whole detail.

    ``redact_provider_errors`` is forced on only for typed Azure code
    interpreter runs. Everything else injects its client unwrapped, so the
    proxy — and therefore all of this — never runs at all.
    """
    detail = "legacy Code Interpreter provider detail"
    client = _injected_client()
    client.responses.create.side_effect = RuntimeError(detail)
    runner = CodeInterpreterRunner(client=client)

    assert runner.client is client
    assert runner.run(task_prompt="x", model="deployment")["error"] == detail
