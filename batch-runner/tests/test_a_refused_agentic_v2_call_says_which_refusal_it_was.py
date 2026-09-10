"""A refused call has to say which refusal it was.

The first paid stage A dispatch recorded ``asking the model failed:
BadRequestError`` and stopped. That is true and nearly useless: it says the
service would not take the request and nothing at all about which part of it
was wrong. Working that out meant re-deriving the payload by hand, while the
service had already answered the question in the status and the error code it
sent back.

So the note carries those two facts now, and still carries nothing else. The
message, the body, the request and the response headers are not read, because
the same exception that names *what* was refused is the richest available
source of *who* refused it — the endpoint, the account, the project, the
deployment — and none of that may be written down.
"""

from __future__ import annotations

import httpx
import pytest
from openai import BadRequestError

from core.agentic_v2_model_voice import _why_the_call_failed


def _refusal(body: dict) -> BadRequestError:
    """A ``400`` shaped the way Azure really shapes one."""
    request = httpx.Request("POST", "https://example.invalid/openai/v1/responses")
    response = httpx.Response(400, request=request, json=body)
    return BadRequestError("ignored", response=response, body=body.get("error"))


def test_the_note_names_the_status_and_the_code():
    error = _refusal(
        {
            "error": {
                "code": "invalid_function_parameters",
                "message": "Invalid schema for function 'workspace_apply'.",
                "type": "invalid_request_error",
            }
        }
    )

    note = _why_the_call_failed(error)

    assert "asking the model failed: BadRequestError" in note
    assert "http 400" in note
    assert "invalid_function_parameters" in note


def test_the_message_and_the_endpoint_never_reach_the_note():
    """What the service says in prose is exactly what may not be recorded."""
    error = _refusal(
        {
            "error": {
                "code": "DeploymentNotFound",
                "message": (
                    "The API deployment for this resource does not exist at "
                    "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/"
                ),
                "type": "invalid_request_error",
            }
        }
    )

    note = _why_the_call_failed(error)

    assert "DeploymentNotFound" in note
    for forbidden in ("hjeon", "azure.com", "https", "does not exist", "deployment for"):
        assert forbidden not in note


def test_a_failure_with_nothing_to_classify_still_says_what_it_was():
    """No status and no code is not a reason to say less than before."""
    note = _why_the_call_failed(TimeoutError("connect timed out after 600s"))

    assert note == "asking the model failed: TimeoutError"
    assert "600" not in note


def test_the_note_stays_within_what_the_loop_keeps():
    """The loop trims long notes; this one must never need trimming."""
    from core.agentic_v2_model_voice import _SHORTEST_USEFUL_NOTE

    error = _refusal(
        {"error": {"code": "c" * 200, "message": "m" * 5000, "type": "t" * 200}}
    )

    assert len(_why_the_call_failed(error)) <= _SHORTEST_USEFUL_NOTE


@pytest.mark.parametrize(
    "code,why",
    [
        ("has a space", "prose is not a code"),
        ("https://example.invalid/x", "a URL is not a code"),
        ("account-name.eastus2", "a hostname is not a code"),
    ],
)
def test_something_that_is_not_code_shaped_is_dropped(code, why):
    """The allow-list is a shape, so anything that could name a host fails it."""
    note = _why_the_call_failed(_refusal({"error": {"code": code}}))

    assert "http 400" in note, why
    assert code not in note, why
