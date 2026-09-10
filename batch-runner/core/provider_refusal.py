"""What a provider refusal is allowed to say about itself.

A call to a hosted model can be refused for many reasons, and the reason is
the one thing an operator needs in order to act. The exception carrying it is
also the single richest source of things that must never be written down: the
endpoint, the account, the deployment, the request and response headers, and
whatever prose the service chose to echo back out of the body.

So a refusal is reduced to two facts before it is recorded anywhere — the HTTP
status, and the provider's own error code — and everything else is dropped
without being read. ``PermissionDenied``, ``DeploymentNotFound`` and
``insufficient_quota`` all survive that reduction; a URL, an account name and a
sentence of English all do not, because none of them can be spelled without a
character the allow-list refuses.

This module holds the reduction so that every caller shares one copy of it.
Redaction that exists twice is redaction that will eventually differ in one
place, and the place it differs is the place something leaks.
"""

from __future__ import annotations

import re
from typing import Optional

#: What a provider's own error code may be made of before it is allowed
#: into a redacted message: letters, digits and underscore, nothing else.
#: Real codes look like ``PermissionDenied``, ``AuthorizationFailed``,
#: ``DeploymentNotFound`` or ``insufficient_quota``. An endpoint, an account
#: name, a deployment name, a file path or a sentence of prose all need a
#: dot, a dash, a slash, a colon or a space, so none of them can get through
#: this. That is the whole reason the allow-list is a shape and not a
#: blocklist of things to strip out.
PROVIDER_CODE_SHAPE = re.compile(r"\A[A-Za-z0-9_]{1,64}\Z")

#: Where a refusal's own code is looked for, in the order it is preferred.
#: The first pair is what the OpenAI SDK lifts out of a JSON body onto the
#: exception itself. The second pair is read back out of the body, because
#: Azure nests its code one level down under ``error`` and the SDK leaves the
#: attributes ``None`` in that case. Looking in the body as well is what makes
#: this useful against a real Azure refusal rather than only a synthetic one.
PROVIDER_CODE_ATTRIBUTES = ("code", "type")
PROVIDER_CODE_BODY_KEYS = ("code", "type")


def provider_code_of(value: object) -> Optional[str]:
    """Return ``value`` when it is code-shaped, and otherwise nothing."""
    if isinstance(value, str) and PROVIDER_CODE_SHAPE.match(value):
        return value
    return None


def classify_provider_refusal(exc: BaseException) -> str:
    """Say what a provider refusal was, without saying who refused it.

    Exactly two things are ever taken from the exception:

    * the HTTP status, and only when it is a whole number a status can be;
    * the provider's own error code, and only when it is code-shaped by
      ``PROVIDER_CODE_SHAPE``.

    The message, the request, the response headers and the body itself are
    never carried into the result. So a redacted message gains the one thing
    an operator needs to act — *what* was refused — and still cannot name an
    endpoint, an account, a project or a deployment.

    Every read is guarded, because these are attributes on somebody else's
    exception and a property is free to raise. A classification that cannot
    be worked out is simply absent; it never replaces the class name.
    """
    parts: list[str] = []

    try:
        status = getattr(exc, "status_code", None)
    except Exception:
        status = None
    if isinstance(status, int) and 100 <= status <= 599:
        parts.append(f"http {status}")

    code = None
    for attribute in PROVIDER_CODE_ATTRIBUTES:
        try:
            code = provider_code_of(getattr(exc, attribute, None))
        except Exception:
            code = None
        if code is not None:
            break
    if code is None:
        try:
            body = getattr(exc, "body", None)
        except Exception:
            body = None
        nested = body.get("error") if isinstance(body, dict) else None
        for holder in (body, nested):
            if not isinstance(holder, dict):
                continue
            for key in PROVIDER_CODE_BODY_KEYS:
                code = provider_code_of(holder.get(key))
                if code is not None:
                    break
            if code is not None:
                break
    if code is not None:
        parts.append(f"code {code}")

    return ", ".join(parts)
