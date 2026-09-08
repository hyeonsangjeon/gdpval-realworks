#!/usr/bin/env python3
"""Hold the development host's definition to the contract the card wrote.

The Xenology card fixes a handful of things about the machine it allows: which
region, which image, which size, that the only way in is an SSH key from a named
address, that no long-lived Azure key is stored on it, and that it shuts itself
down. `infra/dev-host/main.bicep` is where those are written as a definition
rather than as a memory of some portal clicks. This reads that definition back
and says whether each promise is still in it.

It is an offline reader. It signs in to nothing, deploys nothing, and needs
neither an Azure subscription nor the Bicep CLI to run, so it can hold the file
in a pull request rather than only after somebody has spent money.

What it is *not*: this cannot tell you what is deployed. A template that says
`disablePasswordAuthentication: true` and a machine that has password
authentication turned off are two different facts, and only the first is
readable from here. The second needs `deploy.sh status` against a real
subscription. Every check below is phrased as a statement about the definition
for that reason.

Why a reader and not a search for strings
-----------------------------------------

Grepping for `disablePasswordAuthentication: true` passes on a file where that
line sits inside a comment, inside a different resource, or inside a branch that
never runs. So this parses: it finds parameters with their defaults, finds
resources with balanced bodies, and looks properties up by path inside the
resource they belong to. The parser understands the subset of Bicep this one
template uses and refuses loudly on anything it does not recognise, which is the
honest failure -- better than a reader that silently sees nothing and reports
that nothing is wrong.

Usage:

    python scripts/check_dev_host_definition.py
    python scripts/check_dev_host_definition.py --json
    python scripts/check_dev_host_definition.py --out report.json
    python scripts/check_dev_host_definition.py --root /path/to/repo

Exit status:

    0   every check passed
    1   at least one check failed -- the definition no longer matches the card
    2   the reader could not run at all (a file is missing or unparseable)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

SCHEMA = "gdpval_dev_host_definition/1"

# The card: "시작 크기: 8 vCPU / 32 GiB 계열. 측정 후에만 확대한다."
#
# A size name is not self-describing -- Standard_D8as_v5 and Standard_D8s_v5 are
# both 8/32 while Standard_D8ads_v5 is too, and Standard_E8as_v5 is 8/64. So the
# sizes this template is allowed to name are listed with what they actually are,
# and an unlisted size fails rather than being assumed to fit. Growing the
# machine is allowed by the card *after measuring*; it is not allowed by
# accident, and adding a row here is the deliberate act that permits it.
KNOWN_VM_SIZES: Mapping[str, tuple[int, int]] = {
    "Standard_D8as_v5": (8, 32),
    "Standard_D8ads_v5": (8, 32),
    "Standard_D8s_v5": (8, 32),
    "Standard_D8ds_v5": (8, 32),
    "Standard_D8as_v6": (8, 32),
    "Standard_D8ds_v6": (8, 32),
}
REQUIRED_VCPUS = 8
REQUIRED_MEMORY_GIB = 32

REQUIRED_REGION = "koreacentral"
REQUIRED_IMAGE_PUBLISHER = "Canonical"
REQUIRED_IMAGE_OFFER = "ubuntu-24_04-lts"

# Values that would open port 22 to everybody. Azure accepts all four spellings
# and they mean the same thing, which is why a check for the literal '*' alone
# is not a check.
WILDCARD_SOURCES = frozenset({"*", "0.0.0.0/0", "::/0", "internet", "any"})

# Words that make a parameter name credential-shaped. A parameter may still be
# called one of these -- adminPublicKey is -- but it may not carry a default,
# because a default is a value committed to the repository.
#
# Matched against the *words* of the name rather than against the name itself.
# A regex like r"\bkey\b" looks right and matches nothing in `storageAccountKey`,
# because there is no word boundary between `t` and `K`; the check would then be
# one that cannot fail, which is worse than not having it. Names are split on
# camelCase humps, underscores and dashes first.
CREDENTIAL_WORDS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "key",
        "keys",
        "token",
        "credential",
        "credentials",
        "sas",
        "pat",
        "cert",
        "certificate",
        "pfx",
        "signature",
    }
)
CREDENTIAL_PHRASES = ("connectionstring", "sharedaccess", "accesskey", "apikey")

_WORD_SPLIT = re.compile(r"[_\-\s]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def name_words(name: str) -> tuple[str, ...]:
    """The words of an identifier, camelCase humps included."""
    return tuple(part.lower() for part in _WORD_SPLIT.split(name) if part)


def is_credential_shaped(name: str) -> bool:
    flat = name.replace("_", "").replace("-", "").lower()
    if any(phrase in flat for phrase in CREDENTIAL_PHRASES):
        return True
    return bool(CREDENTIAL_WORDS & set(name_words(name)))

# The one sysctl the bootstrap must not write. Setting it to 0 removes
# unprivileged user namespace restriction from *every* process on the machine,
# which is the refused shortcut in TASK_NATIVE_CODEX_RUN_PATH.md §3b, not a fix.
APPARMOR_SYSCTL = "apparmor_restrict_unprivileged_userns"


# ---------------------------------------------------------------------------
# A reader for the subset of Bicep this template uses
# ---------------------------------------------------------------------------


class BicepParseError(ValueError):
    """The reader met something it does not understand, and says so."""


def strip_comments(text: str) -> str:
    """Remove // and /* */ comments without touching string literals.

    A naive `text.split('//')` eats the inside of any string containing a URL,
    and a naive regex eats `'https://example'`. This walks the file once and
    knows when it is inside a single-quoted string, which is the only string
    form Bicep has.

    Comment bytes are replaced by spaces rather than deleted so that every
    offset in the result still points at the same character in the original --
    error messages stay truthful about where they are.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                out.append(ch)
                out.append(text[i + 1])
                i += 2
                continue
            out.append(ch)
            if ch == "'":
                in_string = False
            elif ch == "\n":
                # An unterminated string cannot span a line in Bicep; treating
                # it as terminated here keeps one typo from swallowing the rest
                # of the file and reporting a clean bill of health.
                in_string = False
            i += 1
            continue
        if ch == "'":
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


_OPENERS = {"{": "}", "[": "]", "(": ")"}
_CLOSERS = {"}": "{", "]": "[", ")": "("}


def balanced_span(text: str, start: int) -> tuple[int, int]:
    """The span of the bracketed group beginning at ``start``, inclusive/exclusive.

    Quotes are respected, so a `'}'` inside a description does not close a
    resource body.
    """
    if start >= len(text) or text[start] not in _OPENERS:
        raise BicepParseError(f"expected a bracket at offset {start}")
    stack = [text[start]]
    i = start + 1
    in_string = False
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                in_string = False
            i += 1
            continue
        if ch == "'":
            in_string = True
        elif ch in _OPENERS:
            stack.append(ch)
        elif ch in _CLOSERS:
            if not stack or stack[-1] != _CLOSERS[ch]:
                raise BicepParseError(f"mismatched '{ch}' at offset {i}")
            stack.pop()
            if not stack:
                return start, i + 1
        i += 1
    raise BicepParseError(f"unclosed '{text[start]}' opened at offset {start}")


@dataclass(frozen=True)
class Parameter:
    name: str
    type_name: str
    default: str | None
    decorators: tuple[str, ...]

    @property
    def has_default(self) -> bool:
        return self.default is not None

    @property
    def is_secure(self) -> bool:
        return any(d.startswith("@secure") for d in self.decorators)

    def default_as_value(self) -> Any:
        return literal(self.default) if self.default is not None else None


@dataclass(frozen=True)
class Resource:
    symbol: str
    type_name: str
    api_version: str
    condition: str | None
    body: str


@dataclass(frozen=True)
class Template:
    path: Path
    source: str
    parameters: Mapping[str, Parameter]
    resources: tuple[Resource, ...]

    def parameter(self, name: str) -> Parameter:
        try:
            return self.parameters[name]
        except KeyError:
            raise BicepParseError(f"no parameter named {name!r}") from None

    def by_type(self, type_name: str) -> tuple[Resource, ...]:
        wanted = type_name.lower()
        return tuple(r for r in self.resources if r.type_name.lower() == wanted)

    def one(self, type_name: str) -> Resource:
        found = self.by_type(type_name)
        if len(found) != 1:
            raise BicepParseError(
                f"expected exactly one {type_name}, found {len(found)}"
            )
        return found[0]


_PARAM = re.compile(
    r"^[ \t]*param[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]+(?P<type>[A-Za-z]+)"
    r"(?P<rest>[ \t]*=?)",
    re.MULTILINE,
)
_RESOURCE = re.compile(
    r"^[ \t]*resource[ \t]+(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)[ \t]+"
    r"'(?P<type>[^'@]+)@(?P<api>[^']+)'[ \t]*=[ \t]*",
    re.MULTILINE,
)
_DECORATOR = re.compile(r"^[ \t]*(@[A-Za-z]+)", re.MULTILINE)


def _decorators_above(text: str, start: int) -> tuple[str, ...]:
    """The @decorators attached to the declaration beginning at ``start``.

    Read upward until a line that is neither blank nor a decorator. A decorator
    can carry a bracketed argument spanning lines -- @description('...') does --
    so a line ending inside brackets is skipped over.
    """
    found: list[str] = []
    line_start = text.rfind("\n", 0, start) + 1
    while line_start > 0:
        prev_end = line_start - 1
        prev_start = text.rfind("\n", 0, prev_end) + 1
        line = text[prev_start:prev_end]
        stripped = line.strip()
        if not stripped:
            line_start = prev_start
            continue
        match = _DECORATOR.match(line)
        if not match:
            # Might be the tail of a multi-line decorator argument; walk up
            # until a line that starts with @ or clearly is not one.
            if stripped.endswith(")") or stripped.endswith("'"):
                line_start = prev_start
                continue
            break
        found.append(match.group(1))
        line_start = prev_start
    return tuple(reversed(found))


def parse(path: Path) -> Template:
    raw = path.read_text(encoding="utf-8")
    text = strip_comments(raw)

    parameters: dict[str, Parameter] = {}
    for match in _PARAM.finditer(text):
        name = match.group("name")
        end = match.end()
        rest = text[end:]
        default: str | None = None
        if match.group("rest").strip().endswith("="):
            value_start = end + (len(rest) - len(rest.lstrip()))
            if value_start < len(text) and text[value_start] in _OPENERS:
                a, b = balanced_span(text, value_start)
                default = text[a:b].strip()
            else:
                newline = text.find("\n", value_start)
                default = text[value_start : newline if newline != -1 else len(text)].strip()
        parameters[name] = Parameter(
            name=name,
            type_name=match.group("type"),
            default=default,
            decorators=_decorators_above(text, match.start()),
        )

    resources: list[Resource] = []
    for match in _RESOURCE.finditer(text):
        cursor = match.end()
        condition: str | None = None
        if text.startswith("if", cursor):
            paren = text.find("(", cursor)
            a, b = balanced_span(text, paren)
            condition = text[a + 1 : b - 1].strip()
            cursor = b
        brace = text.find("{", cursor)
        if brace == -1:
            raise BicepParseError(f"resource {match.group('symbol')} has no body")
        a, b = balanced_span(text, brace)
        resources.append(
            Resource(
                symbol=match.group("symbol"),
                type_name=match.group("type"),
                api_version=match.group("api"),
                condition=condition,
                body=text[a:b],
            )
        )

    if not parameters and not resources:
        raise BicepParseError(f"{path} produced no parameters and no resources")
    return Template(path=path, source=raw, parameters=parameters, resources=tuple(resources))


def fields(block: str) -> Iterator[tuple[str, str]]:
    """Top-level ``key: value`` pairs of one ``{...}`` block, values raw."""
    if not block.startswith("{"):
        raise BicepParseError("fields() wants a { } block")
    i, end = 1, len(block) - 1
    while i < end:
        ch = block[i]
        if ch in " \t\r\n,":
            i += 1
            continue
        if ch == "'":
            _, close = balanced_string(block, i)
            i = close
            continue
        key_match = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)[ \t]*:").match(block, i)
        if not key_match:
            i += 1
            continue
        value_start = key_match.end()
        while value_start < end and block[value_start] in " \t":
            value_start += 1
        if value_start < end and block[value_start] in _OPENERS:
            a, b = balanced_span(block, value_start)
            value = block[a:b]
            i = b
        else:
            stop = _end_of_unbracketed_value(block, value_start, end)
            value = block[value_start:stop].strip().rstrip(",")
            i = stop
        yield key_match.group(1), value.strip()


def _end_of_unbracketed_value(block: str, start: int, end: int) -> int:
    """Where a value that does not begin with a bracket stops.

    Usually the end of the line. But Bicep lets a value be a call that opens a
    bracket later and spans several lines -- `securityRules: concat(` is exactly
    that -- and stopping at the first newline would leave the reader scanning
    the *inside* of the call as if those were more fields of the enclosing
    object. That is not a cosmetic error: it lifts a nested `access: 'Allow'`
    up to the top level, where a security check would then find a rule that is
    not there. So the scan tracks bracket depth and only a newline at depth zero
    ends the value.
    """
    depth = 0
    i = start
    while i < end:
        ch = block[i]
        if ch == "'":
            _, i = balanced_string(block, i)
            continue
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            if depth == 0:
                return i
            depth -= 1
        elif ch == "\n" and depth == 0:
            return i
        i += 1
    return end


def balanced_string(text: str, start: int) -> tuple[int, int]:
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "'":
            return start, i + 1
        i += 1
    raise BicepParseError(f"unterminated string at offset {start}")


def field_at(block: str, path: str) -> str | None:
    """The raw value at a dotted path inside a block, or None if absent."""
    current = block
    for part in path.split("."):
        found = None
        for key, value in fields(current):
            if key == part:
                found = value
                break
        if found is None:
            return None
        current = found
    return current


def literal(raw: str | None) -> Any:
    """A Bicep literal as a Python value; the raw text when it is an expression.

    Only what this template actually uses: quoted strings, true/false, null,
    integers, flat arrays of literals, and flat objects. Anything else comes
    back as its own text, which the caller can then refuse rather than
    misread as a value.
    """
    if raw is None:
        return None
    text = raw.strip().rstrip(",").strip()
    if not text:
        return None
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        return text[1:-1]
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        items: list[Any] = []
        i = 0
        while i < len(inner):
            ch = inner[i]
            if ch in " \t\r\n,":
                i += 1
                continue
            if ch == "'":
                a, b = balanced_string(inner, i)
                items.append(inner[a + 1 : b - 1])
                i = b
                continue
            if ch in _OPENERS:
                a, b = balanced_span(inner, i)
                items.append(literal(inner[a:b]))
                i = b
                continue
            stop = i
            while stop < len(inner) and inner[stop] not in ",\n":
                stop += 1
            items.append(literal(inner[i:stop]))
            i = stop
        return items
    if text.startswith("{") and text.endswith("}"):
        return {key: literal(value) for key, value in fields(text)}
    return text


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


@dataclass
class Check:
    check_id: str
    promise: str
    ok: bool
    evidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "promise": self.promise,
            "ok": self.ok,
            "evidence": self.evidence,
        }


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def record(self, check_id: str, promise: str, ok: bool, evidence: str) -> None:
        self.checks.append(Check(check_id, promise, bool(ok), evidence))

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "verdict": "ok" if not self.failed else "violations",
            "checked": len(self.checks),
            "failed": len(self.failed),
            "reads_the_definition_not_the_deployment": (
                "Every statement here is about infra/dev-host/. What is actually "
                "running in Azure is a different fact and is not readable from here; "
                "`deploy.sh status` is what reads that."
            ),
            "checks": [c.as_dict() for c in self.checks],
        }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def check_template(template: Template, report: Report) -> None:
    params = template.parameters

    location = params["location"].default_as_value() if "location" in params else None
    report.record(
        "region_default_is_koreacentral",
        "The card fixes koreacentral and allows another region only for SKU or quota, recorded.",
        location == REQUIRED_REGION,
        f"param location default = {location!r}",
    )

    publisher = literal(params["imagePublisher"].default) if "imagePublisher" in params else None
    offer = literal(params["imageOffer"].default) if "imageOffer" in params else None
    image_ok = publisher == REQUIRED_IMAGE_PUBLISHER and offer == REQUIRED_IMAGE_OFFER
    report.record(
        "image_is_ubuntu_24_04_lts",
        "The card fixes Ubuntu 24.04 LTS. This is not a place to substitute an image that sandboxes more easily.",
        image_ok,
        f"publisher={publisher!r} offer={offer!r}",
    )

    size = literal(params["vmSize"].default) if "vmSize" in params else None
    shape = KNOWN_VM_SIZES.get(str(size))
    report.record(
        "size_is_eight_vcpu_thirty_two_gib",
        "The card starts at 8 vCPU / 32 GiB and grows only after measuring.",
        shape == (REQUIRED_VCPUS, REQUIRED_MEMORY_GIB),
        (
            f"vmSize={size!r} is {shape[0]} vCPU / {shape[1]} GiB"
            if shape
            else f"vmSize={size!r} is not in KNOWN_VM_SIZES, so its shape is unknown; "
            f"add it there with what it actually is if it is meant to be allowed"
        ),
    )

    vm = template.one("Microsoft.Compute/virtualMachines")

    disabled = literal(
        field_at(vm.body, "properties.osProfile.linuxConfiguration.disablePasswordAuthentication")
    )
    report.record(
        "password_authentication_is_off",
        "SSH keys only. Not a strong password -- the property is off.",
        disabled is True,
        f"disablePasswordAuthentication = {disabled!r}",
    )

    has_admin_password = field_at(vm.body, "properties.osProfile.adminPassword") is not None
    report.record(
        "no_password_is_carried_at_all",
        "There is no password to leak because there is no password property.",
        not has_admin_password,
        "adminPassword is absent from osProfile"
        if not has_admin_password
        else "osProfile carries an adminPassword",
    )

    key_param = params.get("adminPublicKey")
    key_ok = key_param is not None and key_param.is_secure and not key_param.has_default
    report.record(
        "ssh_key_is_required_and_has_no_default",
        "A deployment with no key fails rather than falling back to something.",
        key_ok,
        (
            f"adminPublicKey secure={key_param.is_secure} default={key_param.default!r}"
            if key_param
            else "no adminPublicKey parameter"
        ),
    )

    sources_param = params.get("sshAllowedSourcePrefixes")
    sources_default = sources_param.default_as_value() if sources_param else None
    report.record(
        "ssh_source_defaults_to_none",
        "Nobody gets port 22 by forgetting a parameter; empty means no inbound rule exists.",
        sources_default == [],
        f"sshAllowedSourcePrefixes default = {sources_default!r}",
    )

    public_ip_default = literal(params["attachPublicIp"].default) if "attachPublicIp" in params else None
    report.record(
        "public_address_is_off_by_default",
        "The card asks for a private connection where possible; run-command needs no address.",
        public_ip_default is False,
        f"attachPublicIp default = {public_ip_default!r}",
    )

    # Every inbound Allow rule in the template, from every NSG, read as data.
    wildcard_allow: list[str] = []
    allow_rules: list[str] = []
    for nsg in template.by_type("Microsoft.Network/networkSecurityGroups"):
        for rule in _iter_security_rules(nsg.body):
            props = field_at(rule, "properties") or "{}"
            access = literal(field_at(props, "access"))
            direction = literal(field_at(props, "direction"))
            if access != "Allow" or direction != "Inbound":
                continue
            name = literal(field_at(rule, "name"))
            allow_rules.append(str(name))
            prefixes = _as_list(literal(field_at(props, "sourceAddressPrefix"))) + _as_list(
                literal(field_at(props, "sourceAddressPrefixes"))
            )
            for prefix in prefixes:
                if isinstance(prefix, str) and prefix.strip().lower() in WILDCARD_SOURCES:
                    wildcard_allow.append(f"{name}: {prefix}")
    report.record(
        "no_inbound_allow_rule_names_a_wildcard_source",
        "Port 22 is opened to named addresses or to nobody. There is no branch that produces the internet.",
        not wildcard_allow,
        f"inbound Allow rules: {allow_rules or 'none'}"
        + (f"; WILDCARD: {wildcard_allow}" if wildcard_allow else ""),
    )

    # The template's own deployment-time refusal. It has to be more than
    # present: an unreferenced Bicep var is never evaluated, so a guard nothing
    # reads is a guard that never fires. It must be read by an output.
    clean = strip_comments(template.source)
    guard = re.search(
        r"var\s+(?P<name>_?\w*[Ss]shSourceGuard)\s*=.*?\bfail\(", clean, re.DOTALL
    )
    guard_name = guard.group("name") if guard else ""
    guard_is_read = bool(guard_name) and bool(
        re.search(rf"output\s+\w+\s+\w+\s*=\s*{re.escape(guard_name)}\b", clean)
    )
    report.record(
        "a_wildcard_is_refused_at_deployment_time_too",
        "The offline reader can be skipped; the template's own assertion cannot. An unread var is never evaluated, so it has to be read.",
        guard_is_read,
        (
            f"var {guard_name} calls fail() and is read by an output"
            if guard_is_read
            else f"guard present={bool(guard_name)}, read by an output={guard_is_read}"
        ),
    )

    identity_type = literal(field_at(vm.body, "identity.type"))
    report.record(
        "identity_is_system_assigned",
        "The card forbids a long-lived Azure key on the machine; an identity is how that is met.",
        identity_type == "SystemAssigned",
        f"identity.type = {identity_type!r}",
    )

    role_assignments = template.by_type("Microsoft.Authorization/roleAssignments")
    report.record(
        "the_identity_is_granted_nothing",
        "An identity with no role can do nothing. Granting one is a permission change that is asked for.",
        not role_assignments,
        f"{len(role_assignments)} roleAssignments resources",
    )

    defaulted_credentials = [
        p.name
        for p in params.values()
        if is_credential_shaped(p.name)
        and p.has_default
        and literal(p.default) not in (None, "", [])
    ]
    credential_shaped = sorted(p.name for p in params.values() if is_credential_shaped(p.name))
    report.record(
        "no_credential_shaped_parameter_carries_a_default",
        "A default for a credential is a value committed to the repository.",
        not defaulted_credentials,
        f"credential-shaped parameters: {credential_shaped or 'none'}; "
        f"with defaults: {defaulted_credentials or 'none'}",
    )

    custom_data = field_at(vm.body, "properties.osProfile.customData")
    report.record(
        "nothing_is_baked_into_the_machine_at_first_boot",
        "customData runs before anyone reviews it and is a place secrets end up. Bootstrap goes through run-command instead.",
        custom_data is None,
        "no customData" if custom_data is None else "osProfile carries customData",
    )

    schedules = template.by_type("Microsoft.DevTestLab/schedules")
    shutdown = [
        s
        for s in schedules
        if literal(field_at(s.body, "properties.taskType")) == "ComputeVmShutdownTask"
        and literal(field_at(s.body, "properties.status")) == "Enabled"
    ]
    report.record(
        "it_shuts_itself_down",
        "The card asks for automatic shutdown. This task deallocates; a guest shutdown would leave it billed.",
        len(shutdown) == 1,
        f"{len(shutdown)} enabled ComputeVmShutdownTask schedules of {len(schedules)} total",
    )

    adopted = re.findall(r"^\s*resource\s+\w+\s+'[^']+'\s+existing\b", strip_comments(template.source), re.MULTILINE)
    report.record(
        "no_existing_resource_is_adopted",
        "The card forbids reusing another project's VM without confirming ownership. This template can only create.",
        not adopted,
        f"{len(adopted)} `existing` resource references",
    )


def _iter_security_rules(nsg_body: str) -> Iterator[str]:
    """Every rule object in an NSG body, however the array was assembled.

    The template builds its rule array with concat() over a conditional, so the
    value at properties.securityRules is an expression rather than a literal
    array. Scanning the body for objects that carry a `properties.access` is
    what survives that, and it also catches a rule somebody adds later in a
    shape this reader has not seen.
    """
    for match in re.finditer(r"\{", nsg_body):
        try:
            a, b = balanced_span(nsg_body, match.start())
        except BicepParseError:
            continue
        block = nsg_body[a:b]
        props = field_at(block, "properties")
        if props and field_at(props, "access") is not None:
            yield block


def check_scripts(root: Path, report: Report) -> None:
    deploy = (root / "infra/dev-host/deploy.sh").read_text(encoding="utf-8")
    bootstrap = (root / "infra/dev-host/bootstrap.sh").read_text(encoding="utf-8")

    demands_subscription = "GDPVAL_DEV_HOST_SUBSCRIPTION" in deploy and re.search(
        r"GDPVAL_DEV_HOST_SUBSCRIPTION.*\n(?:.*\n)?.*\bdie\b", deploy
    )
    report.record(
        "deploy_will_not_pick_a_subscription_for_you",
        "The card separates this machine from the internal subscription; 'whichever one az was signed into' is not a way to honour that.",
        bool(demands_subscription),
        "deploy.sh dies when GDPVAL_DEV_HOST_SUBSCRIPTION is unset"
        if demands_subscription
        else "deploy.sh does not require GDPVAL_DEV_HOST_SUBSCRIPTION",
    )

    refuses_foundry = "AZURE_AI_EXPECTED_SUBSCRIPTION_ID" in deploy and "refusing" in deploy
    report.record(
        "deploy_refuses_the_subscription_the_foundry_checks_expect",
        "internal FDPO 구독과 Foundry 권한 작업에는 사용하지 않는다 -- as a refusal, not a warning.",
        refuses_foundry,
        "deploy.sh compares the target against AZURE_AI_EXPECTED_SUBSCRIPTION_ID and refuses"
        if refuses_foundry
        else "deploy.sh has no Foundry-subscription refusal",
    )

    deallocates = re.search(r"az vm deallocate", deploy) is not None
    deletes = re.search(r"az group delete", deploy) is not None
    report.record(
        "teardown_is_a_command_not_a_paragraph",
        "완료 기준 5: the automatic shutdown, deallocate and delete procedures are verified.",
        deallocates and deletes,
        f"deallocate={deallocates} group-delete={deletes}",
    )

    # The bootstrap must never turn the restriction off. Written as: no line
    # that writes to the sysctl, by any of the three ways of writing to it.
    writes_sysctl = [
        line.strip()
        for line in bootstrap.splitlines()
        if APPARMOR_SYSCTL in line
        and (
            re.search(r"sysctl\s+(-w|--write)", line)
            or re.search(r">\s*/proc/sys", line)
            or re.search(r"^\s*kernel\." + APPARMOR_SYSCTL + r"\s*=", line)
            or re.search(r"tee\s+/proc/sys", line)
        )
    ]
    report.record(
        "bootstrap_reads_the_namespace_restriction_and_does_not_clear_it",
        "Setting the sysctl to 0 removes the restriction from every process on the machine. That is the absence of a fix, not a fix.",
        not writes_sysctl,
        "the sysctl is read only" if not writes_sysctl else f"writes: {writes_sysctl}",
    )

    marks_itself = (
        "/etc/gdpval-dev-host" in bootstrap
        and "benchmark_execution_environment=no" in bootstrap
    )
    report.record(
        "bootstrap_marks_the_machine_as_not_a_benchmark_environment",
        "완료 기준 6: the development VM does not implicitly become a benchmark environment.",
        marks_itself,
        "writes /etc/gdpval-dev-host with benchmark_execution_environment=no"
        if marks_itself
        else "no development-host marker is written",
    )

    clones_clean = "git clone" in bootstrap and "rsync" not in bootstrap
    report.record(
        "bootstrap_clones_rather_than_copying_the_users_checkout",
        "구현 방식 4: a clean worktree from origin/main; the existing user checkout is not copied.",
        clones_clean,
        f"git clone present={('git clone' in bootstrap)}; rsync present={('rsync' in bootstrap)}",
    )


def check(root: Path) -> Report:
    report = Report()
    template = parse(root / "infra/dev-host/main.bicep")
    check_template(template, report)
    check_scripts(root, report)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def render(report: Report) -> str:
    lines = ["Development host definition -- infra/dev-host/", ""]
    for item in report.checks:
        mark = "ok  " if item.ok else "FAIL"
        lines.append(f"  [{mark}] {item.check_id}")
        lines.append(f"          {item.promise}")
        lines.append(f"          {item.evidence}")
    lines.append("")
    if report.failed:
        lines.append(f"{len(report.failed)} of {len(report.checks)} checks failed.")
    else:
        lines.append(f"All {len(report.checks)} checks passed.")
    lines.append(
        "This reads the definition, not the deployment. What is running in Azure "
        "is a different fact; `deploy.sh status` reads that one."
    )
    return "\n".join(lines)


def default_root() -> Path:
    # scripts/ -> batch-runner/ -> repository root
    return Path(__file__).resolve().parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="repository root")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--out", type=Path, default=None, help="also write the JSON report here")
    args = parser.parse_args(argv)

    root = args.root or default_root()
    try:
        report = check(root)
    except (BicepParseError, OSError) as exc:
        print(f"could not read the definition: {exc}", file=sys.stderr)
        return 2

    payload = report.as_dict()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render(report))
    if args.out:
        args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
