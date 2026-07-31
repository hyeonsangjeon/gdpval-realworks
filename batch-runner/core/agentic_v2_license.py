"""Deterministic Phase 1C package-license evidence and decision contracts."""

from __future__ import annotations

import hashlib
import json
import marshal
import os
import re
import stat
import sys
import types
import packaging
import packaging.licenses as packaging_licenses
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import quote

from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression
from packaging.licenses import _spdx

from core.agentic_v2_substrate import canonical_sha256


CLASSIFICATIONS = frozenset({
    "resolved",
    "missing_metadata",
    "ambiguous",
    "unverifiable",
    "denied",
    "exception",
})
DENIED_LICENSE_IDENTIFIERS = (
    "BUSL-1.1",
    "Commons-Clause",
    "SSPL-1.0",
)
LICENSE_EVALUATOR_PACKAGING_VERSION = "26.2"
LICENSE_EVALUATOR_SPDX_VERSION = "3.27.0"
LICENSE_EVALUATOR_SPDX_SHA256 = (
    "ecc082fdc1fcdcae47b2f56c4ce2cdc2c9d6d54ca555a09814abd78dece7a230"
)
LICENSE_EVALUATOR_PARSER_SHA256 = (
    "fc9c745d1883ff9f296a5b169f22eb2ee879f59a4608f20f5cb29d668f4e26f4"
)
LICENSE_EVALUATOR_RUNTIME_GRAPH_SHA256 = (
    "8fff34b3a069995de020a123594de0254935b12ab154b272057807c8de7be459"
)
LICENSE_EVALUATOR_PYTHON_VERSION = "3.10.12"
LICENSE_EVALUATOR_CALLABLE_SHA256 = (
    "e27e24ff0053d4f68aca4d2ec770d83b8cd8536629c01406c7f5578f6972a78b"
)
UNRESOLVED_CLASSIFICATIONS = frozenset({
    "missing_metadata", "ambiguous", "unverifiable",
})
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")
_EXPRESSION_TOKEN = re.compile(
    r"(?<![A-Za-z0-9.+-])"
    r"([A-Za-z0-9](?:[A-Za-z0-9.+-]{0,126}[A-Za-z0-9+])?)"
    r"(?![A-Za-z0-9+-])",
    re.ASCII,
)
_PYTHON_PURELIB_PATH = PurePosixPath("/usr/local/lib/python3.11/site-packages")
_MAX_LICENSE_EXPRESSION_LENGTH = 4096
_MAX_LICENSE_EXPRESSION_DEPTH = 64
_MAX_LICENSE_EXPRESSION_TOKENS = 512
_R_LICENSE_REFERENCE = re.compile(
    r"file ([A-Za-z0-9][A-Za-z0-9._+-]*)\Z", re.ASCII
)
_NPM_LICENSE_REFERENCE = re.compile(
    r"SEE LICENSE IN ([A-Za-z0-9][A-Za-z0-9._+-]*)\Z", re.ASCII
)
_R_REFERENCE_LIKE = re.compile(r"\bfile\b", re.IGNORECASE | re.ASCII)
_NPM_REFERENCE_LIKE = re.compile(
    r"\bSEE\s+LICENSE\s+IN\b", re.IGNORECASE | re.ASCII
)
_LICENSE_FILE_TOKEN_TEXT = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9.+-]{0,126}[A-Za-z0-9+])?\Z",
    re.ASCII,
)
_DEP5_FORMAT_URI = (
    "https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
)
_REGISTERED_SPDX_IDENTIFIERS = frozenset(
    value["id"]
    for collection in (_spdx.LICENSES, _spdx.EXCEPTIONS)
    for value in collection.values()
)


def _matches(pattern: re.Pattern, value: Any) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


_EXACT_ALIASES = {
    "2-clause BSD": "BSD-2-Clause",
    "Apache 2.0": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache License, Version 2.0": "Apache-2.0",
    "BSD 2-Clause": "BSD-2-Clause",
    "BSD 2-Clause License": "BSD-2-Clause",
    "BSD 3-Clause": "BSD-3-Clause",
    "BSD 3-Clause License": "BSD-3-Clause",
    "MIT License": "MIT",
    "New BSD": "BSD-3-Clause",
    "PSFL": "PSF-2.0",
    "The MIT License (MIT)": "MIT",
    "new BSD License": "BSD-3-Clause",
}

_DEBIAN_EXACT_ALIASES = {
    "Apache-2": "Apache-2.0",
    "Artistic-2": "Artistic-2.0",
    "BOOST-1.0": "BSL-1.0",
    "BSL-1": "BSL-1.0",
    "Expat": "MIT",
    "GPL-1": "GPL-1.0-only",
    "GPL-1+": "GPL-1.0-or-later",
    "GPL-2": "GPL-2.0-only",
    "GPL-2+": "GPL-2.0-or-later",
    "GPL-3": "GPL-3.0-only",
    "GPL-3+": "GPL-3.0-or-later",
    "LGPL-2": "LGPL-2.0-only",
    "LGPL-2+": "LGPL-2.0-or-later",
    "LGPL-2.1": "LGPL-2.1-only",
    "LGPL-2.1+": "LGPL-2.1-or-later",
    "LGPL-3": "LGPL-3.0-only",
    "LGPL-3+": "LGPL-3.0-or-later",
    "MPL2.0": "MPL-2.0",
    "SIL-1.1": "OFL-1.1",
    "expat": "MIT",
}

_PYTHON_CLASSIFIERS = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: GNU Affero General Public License v3": "AGPL-3.0-only",
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)": "GPL-2.0-only",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
    "License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)": "LGPL-2.0-only",
    "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.0-or-later",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: The Unlicense (Unlicense)": "Unlicense",
}

_PYTHON_EXACT_ALIASES = {
    **_EXACT_ALIASES,
    "GPLv2": "GPL-2.0-only",
    "LGPLv3+": "LGPL-3.0-or-later",
}

_DEBIAN_OPERATORS = re.compile(
    r"(\(|\)|,\s+and\s+|,\s+or\s+|\s+and\s+|\s+or\s+|\s+with\s+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Outcome:
    expression: str | None
    issue: str | None
    reason: str
    identifiers: frozenset[str]


def license_evaluator_runtime_identity() -> dict[str, str]:
    packaging_path = Path(str(packaging.__file__))
    package_root = packaging_path.parent
    parser_path = Path(str(packaging_licenses.__file__))
    spdx_path = Path(str(_spdx.__file__))
    expected_paths = {
        "packaging/__init__.py": package_root / "__init__.py",
        "packaging/licenses/__init__.py": package_root / "licenses" / "__init__.py",
        "packaging/licenses/_spdx.py": package_root / "licenses" / "_spdx.py",
    }
    if (
        packaging_path != expected_paths["packaging/__init__.py"]
        or parser_path != expected_paths["packaging/licenses/__init__.py"]
        or spdx_path != expected_paths["packaging/licenses/_spdx.py"]
        or canonicalize_license_expression
        is not packaging_licenses.canonicalize_license_expression
        or canonicalize_license_expression.__module__ != "packaging.licenses"
        or canonicalize_license_expression.__qualname__
        != "canonicalize_license_expression"
        or not hasattr(canonicalize_license_expression, "__code__")
        or Path(canonicalize_license_expression.__code__.co_filename) != parser_path
        or canonicalize_license_expression.__globals__
        is not packaging_licenses.__dict__
        or packaging_licenses.LICENSES is not _spdx.LICENSES
        or packaging_licenses.EXCEPTIONS is not _spdx.EXCEPTIONS
        or InvalidLicenseExpression
        is not packaging_licenses.InvalidLicenseExpression
        or any(not path.is_absolute() for path in expected_paths.values())
        or not all(
            isinstance(getattr(os, name, None), int)
            for name in ("O_NOFOLLOW", "O_CLOEXEC")
        )
    ):
        raise RuntimeError("agentic v2 license evaluator parser identity differs")
    def parser_identity(value):
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
        )

    graph = []
    sources = {}
    for relative_path, path in sorted(expected_paths.items()):
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > 1024 * 1024
            ):
                raise RuntimeError(
                    "agentic v2 license evaluator source file is invalid"
                )
            chunks = []
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        source_bytes = b"".join(chunks)
        if (
            parser_identity(before) != parser_identity(after)
            or len(source_bytes) != before.st_size
        ):
            raise RuntimeError(
                "agentic v2 license evaluator source changed while reading"
            )
        sources[relative_path] = source_bytes
        graph.append({
            "path": relative_path,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "size": len(source_bytes),
        })
    def normalize_code(code):
        constants = tuple(
            normalize_code(value) if isinstance(value, types.CodeType) else value
            for value in code.co_consts
        )
        return code.replace(
            co_consts=constants,
            co_filename="packaging/licenses/__init__.py",
        )

    callable_sha256 = hashlib.sha256(marshal.dumps(normalize_code(
        canonicalize_license_expression.__code__
    ))).hexdigest()
    payload = {
        "packaging_version": packaging.__version__,
        "spdx_version": _spdx.VERSION,
        "licenses": sorted(_spdx.LICENSES.items()),
        "exceptions": sorted(_spdx.EXCEPTIONS.items()),
    }
    identity = {
        "packaging_version": packaging.__version__,
        "spdx_version": _spdx.VERSION,
        "spdx_sha256": canonical_sha256(payload),
        "parser_sha256": hashlib.sha256(
            sources["packaging/licenses/__init__.py"]
        ).hexdigest(),
        "runtime_graph_sha256": canonical_sha256(graph),
        "python_version": ".".join(str(item) for item in sys.version_info[:3]),
        "callable_sha256": callable_sha256,
    }
    if identity != {
        "packaging_version": LICENSE_EVALUATOR_PACKAGING_VERSION,
        "spdx_version": LICENSE_EVALUATOR_SPDX_VERSION,
        "spdx_sha256": LICENSE_EVALUATOR_SPDX_SHA256,
        "parser_sha256": LICENSE_EVALUATOR_PARSER_SHA256,
        "runtime_graph_sha256": LICENSE_EVALUATOR_RUNTIME_GRAPH_SHA256,
        "python_version": LICENSE_EVALUATOR_PYTHON_VERSION,
        "callable_sha256": LICENSE_EVALUATOR_CALLABLE_SHA256,
    }:
        raise RuntimeError("agentic v2 license evaluator runtime identity differs")
    return identity


def _identifiers(expression: str) -> frozenset[str]:
    return frozenset(
        token
        for token in _EXPRESSION_TOKEN.findall(expression)
        if token not in {"AND", "OR", "WITH"}
    )


def _valid_expression_shape(expression: Any) -> bool:
    if not isinstance(expression, str) or len(expression) > _MAX_LICENSE_EXPRESSION_LENGTH:
        return False
    depth = 0
    maximum_depth = 0
    tokens = 0
    in_token = False
    for character in expression:
        if character == "(":
            depth += 1
            maximum_depth = max(maximum_depth, depth)
            tokens += 1
            in_token = False
        elif character == ")":
            depth -= 1
            if depth < 0:
                return None
            tokens += 1
            in_token = False
        elif character == "|":
            tokens += 1
            in_token = False
        elif character.isspace():
            in_token = False
        elif not in_token:
            tokens += 1
            in_token = True
        if (
            maximum_depth > _MAX_LICENSE_EXPRESSION_DEPTH
            or tokens > _MAX_LICENSE_EXPRESSION_TOKENS
        ):
            return False
    return depth == 0


def _canonical(expression: Any) -> str | None:
    if not _valid_expression_shape(expression):
        return None
    try:
        canonical = str(canonicalize_license_expression(expression))
    except (InvalidLicenseExpression, RecursionError):
        return None
    if not _identifiers(canonical).issubset(_REGISTERED_SPDX_IDENTIFIERS):
        return None
    return canonical


def _atom(value: str, aliases: Mapping[str, str]) -> _Outcome:
    stripped = value.strip()
    canonical = _canonical(stripped)
    if canonical is not None:
        return _Outcome(canonical, None, "direct-spdx-expression", _identifiers(canonical))
    mapped = aliases.get(stripped)
    if mapped is not None:
        canonical = _canonical(mapped)
        if canonical is None:
            raise RuntimeError(f"invalid internal SPDX alias: {stripped}")
        return _Outcome(canonical, None, f"exact-alias:{stripped}", _identifiers(canonical))
    ambiguous = (
        stripped in {"Artistic", "BSD", "BSD License", "Dual License", "GPL", "MPL"}
        or "and/or" in stripped.lower()
        or stripped.lower().startswith("dual licens")
    )
    return _Outcome(
        None,
        "ambiguous" if ambiguous else "unverifiable",
        "ambiguous-license-label" if ambiguous else "unmapped-exact-license-label",
        frozenset(),
    )


def _combine(operator: str, outcomes: list[_Outcome], reason: str) -> _Outcome:
    identifiers = frozenset().union(*(item.identifiers for item in outcomes))
    issues = [item.issue for item in outcomes if item.issue]
    if issues:
        issue = "ambiguous" if "ambiguous" in issues else "unverifiable"
        return _Outcome(None, issue, reason, identifiers)
    expressions = sorted({item.expression for item in outcomes if item.expression})
    if not expressions:
        return _Outcome(None, "missing_metadata", reason, identifiers)
    if len(expressions) == 1:
        return _Outcome(expressions[0], None, reason, identifiers)
    candidate = f" {operator} ".join(f"({value})" for value in expressions)
    canonical = _canonical(candidate)
    if canonical is None:
        return _Outcome(None, "unverifiable", reason, identifiers)
    return _Outcome(canonical, None, reason, _identifiers(canonical))


def _debian_expression(raw: str) -> _Outcome:
    if not _valid_expression_shape(raw):
        return _Outcome(
            None,
            "unverifiable",
            "invalid-debian-license-expression-shape",
            frozenset(),
        )
    direct = _atom(raw, {**_EXACT_ALIASES, **_DEBIAN_EXACT_ALIASES})
    if direct.expression is not None:
        return direct
    tokens = [token for token in _DEBIAN_OPERATORS.split(raw) if token and token.strip()]
    if len(tokens) == 1:
        return direct

    def parse_range(start: int, end: int) -> _Outcome:
        def encloses_range() -> bool:
            if end - start < 2 or tokens[start] != "(" or tokens[end - 1] != ")":
                return False
            depth = 0
            for index in range(start, end):
                if tokens[index] == "(":
                    depth += 1
                elif tokens[index] == ")":
                    depth -= 1
                    if depth == 0 and index != end - 1:
                        return False
                    if depth < 0:
                        return False
            return depth == 0

        while encloses_range():
            start += 1
            end -= 1
        depth = 0
        for operator, label in (("or", "OR"), ("and", "AND")):
            parts = []
            last = start
            depth = 0
            for index in range(start, end):
                token = tokens[index].strip().lower().replace(",", "")
                if tokens[index] == "(":
                    depth += 1
                elif tokens[index] == ")":
                    depth -= 1
                elif depth == 0 and token == operator:
                    parts.append(parse_range(last, index))
                    last = index + 1
            if parts:
                parts.append(parse_range(last, end))
                return _combine(label, parts, f"debian-{operator}-expression")
        depth = 0
        for index in range(start, end):
            if tokens[index] == "(":
                depth += 1
            elif tokens[index] == ")":
                depth -= 1
            elif depth == 0 and tokens[index].strip().lower() == "with":
                left = parse_range(start, index)
                exception = " ".join(tokens[index + 1:end]).strip()
                exception_aliases = {
                    "Autoconf exception 3.0": "Autoconf-exception-3.0",
                    "Bison exception": "Bison-exception-2.2",
                    "Classpath exception 2.0": "Classpath-exception-2.0",
                    "Libtool exception": "Libtool-exception",
                }
                mapped = exception_aliases.get(exception, exception)
                if left.expression is None:
                    return left
                candidate = f"{left.expression} WITH {mapped}"
                canonical = _canonical(candidate)
                if canonical is None:
                    return _Outcome(
                        None, "unverifiable", "unmapped-license-exception",
                        left.identifiers,
                    )
                return _Outcome(
                    canonical, None, "debian-with-expression", _identifiers(canonical)
                )
        return _atom(" ".join(tokens[start:end]), {**_EXACT_ALIASES, **_DEBIAN_EXACT_ALIASES})

    return parse_range(0, len(tokens))


def _python_outcome(record: Mapping[str, Any]) -> _Outcome:
    metadata = record["metadata"]
    outcomes = []
    expression_outcome = None
    expression_issue = None
    expression = metadata.get("license_expression")
    if isinstance(expression, str) and expression.strip():
        result = _atom(expression, {})
        if result.expression is None:
            expression_issue = result
        else:
            expression_outcome = result
        outcomes.append(result)

    license_outcome = None
    license_issue = None
    license_value = metadata.get("license")
    if isinstance(license_value, str) and license_value.strip() not in {"UNKNOWN", "NOASSERTION"}:
        license_outcome = _atom(license_value, _PYTHON_EXACT_ALIASES)
        outcomes.append(license_outcome)
        if license_outcome.expression is None:
            license_issue = license_outcome
    classifier_values = []
    ambiguous_classifier = False
    unknown_classifier = False
    for classifier in metadata.get("classifiers", []):
        mapped = _PYTHON_CLASSIFIERS.get(classifier)
        if mapped:
            classifier_values.append(_atom(mapped, {}))
        elif classifier == "License :: OSI Approved :: BSD License":
            ambiguous_classifier = True
        else:
            unknown_classifier = True
    all_identifiers = frozenset().union(*(
        item.identifiers for item in outcomes + classifier_values
    ))
    if unknown_classifier:
        return _Outcome(
            None, "unverifiable", "unmapped-python-license-classifier",
            all_identifiers,
        )
    if expression_issue is not None:
        return _Outcome(
            None,
            expression_issue.issue or "unverifiable",
            "invalid-python-license-expression",
            all_identifiers,
        )
    if license_issue is not None:
        return _Outcome(
            None,
            license_issue.issue or "unverifiable",
            "unresolved-explicit-python-license-field",
            all_identifiers,
        )
    if ambiguous_classifier:
        return _Outcome(
            None, "ambiguous", "generic-bsd-classifier",
            all_identifiers,
        )
    if expression_outcome is not None:
        if (
            license_outcome is not None
            and license_outcome.expression != expression_outcome.expression
        ) or any(
            item.expression is not None
            and not item.identifiers.issubset(expression_outcome.identifiers)
            for item in classifier_values
        ):
            return _Outcome(
                None, "ambiguous", "conflicting-python-license-metadata",
                all_identifiers,
            )
        return _Outcome(
            expression_outcome.expression,
            None,
            "python-license-expression-with-compatible-metadata",
            expression_outcome.identifiers,
        )
    resolved = sorted({item.expression for item in outcomes + classifier_values if item.expression})
    if license_outcome is not None and license_outcome.expression is not None:
        if all(
            item.expression is None
            or item.identifiers.issubset(license_outcome.identifiers)
            for item in classifier_values
        ):
            return _Outcome(
                license_outcome.expression,
                None,
                "python-license-field-with-compatible-classifiers",
                license_outcome.identifiers,
            )
    if len(resolved) > 1:
        return _Outcome(
            None, "ambiguous", "conflicting-python-license-metadata",
            frozenset().union(*(item.identifiers for item in outcomes + classifier_values)),
        )
    if resolved:
        return _Outcome(
            resolved[0], None,
            "python-license-field-or-classifier",
            _identifiers(resolved[0]),
        )
    if not record["raw_values"]:
        return _Outcome(None, "missing_metadata", "python-license-metadata-missing", frozenset())
    return _Outcome(None, "unverifiable", "python-license-metadata-unverifiable", frozenset())


def _r_outcome(record: Mapping[str, Any]) -> _Outcome:
    metadata = record["metadata"]
    declared = metadata.get("declared_license")
    runtime = metadata.get("runtime_license")
    runtime_version = metadata.get("runtime_version")
    if isinstance(declared, str) and not _valid_expression_shape(declared):
        return _Outcome(
            None,
            "unverifiable",
            "invalid-r-license-expression-shape",
            frozenset(),
        )
    if (
        isinstance(declared, str)
        and declared == f"Part of R {runtime_version}"
        and metadata.get("priority") == "base"
    ):
        runtime_fields = metadata.get("runtime_license_fields")
        if isinstance(runtime_fields, list) and runtime_fields:
            outcomes = [_debian_expression(value) for value in runtime_fields]
            return _combine("AND", outcomes, "r-runtime-copyright-license")
        if not isinstance(runtime, str) or not runtime:
            return _Outcome(None, "missing_metadata", "r-runtime-license-missing", frozenset())
        if not _valid_expression_shape(runtime):
            return _Outcome(
                None,
                "unverifiable",
                "invalid-r-license-expression-shape",
                frozenset(),
            )
        parts = [part.strip() for part in runtime.split("|")]
        if not parts or any(not part for part in parts):
            return _Outcome(
                None, "unverifiable", "invalid-r-license-alternatives",
                frozenset(),
            )
        outcomes = [_atom(part, _DEBIAN_EXACT_ALIASES) for part in parts]
        return _combine("OR", outcomes, "r-base-runtime-license")
    if isinstance(declared, str) and declared.startswith("Part of R"):
        return _Outcome(
            None,
            "unverifiable",
            "invalid-r-runtime-license-reference",
            frozenset(),
        )
    if isinstance(declared, str) and declared:
        parts = [part.strip() for part in declared.split("|")]
        if not parts or any(not part for part in parts):
            return _Outcome(
                None, "unverifiable", "invalid-r-license-alternatives",
                frozenset(),
            )
        outcomes = [_atom(part, _DEBIAN_EXACT_ALIASES) for part in parts]
        return _combine("OR", outcomes, "r-description-license")
    return _Outcome(None, "missing_metadata", "r-license-metadata-missing", frozenset())


def _normalize(record: Mapping[str, Any]) -> _Outcome:
    ecosystem = record["ecosystem"]
    if ecosystem == "debian":
        raw_values = record["raw_values"]
        if not raw_values:
            if not any(
                item["source"] == "debian-copyright"
                for item in record["evidence"]
            ):
                return _Outcome(
                    None,
                    "missing_metadata",
                    "debian-copyright-metadata-missing",
                    frozenset(),
                )
            return _Outcome(
                None, "unverifiable", "debian-copyright-has-no-dep5-license-fields",
                frozenset(),
            )
        outcomes = [_debian_expression(value) for value in raw_values]
        return _combine("AND", outcomes, "debian-file-stanza-license-conjunction")
    if ecosystem == "python":
        return _python_outcome(record)
    if ecosystem == "r":
        return _r_outcome(record)
    if ecosystem == "npm":
        if not record["raw_values"]:
            return _Outcome(None, "missing_metadata", "npm-license-missing", frozenset())
        return _atom(record["raw_values"][0], _EXACT_ALIASES)
    raise ValueError("unsupported license evidence ecosystem")


def _validate_evidence_item(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "source", "path", "resolved_path", "sha256", "size",
    }:
        raise ValueError("agentic v2 license evidence item fields are invalid")
    item = dict(value)
    if (
        not isinstance(item["source"], str)
        or not item["source"]
        or not _matches(_HEX_DIGEST, item["sha256"])
        or type(item["size"]) is not int
        or item["size"] < 0
    ):
        raise ValueError("agentic v2 license evidence item identity is invalid")
    for key in ("path", "resolved_path"):
        path = item[key]
        if path is not None and (
            not isinstance(path, str)
            or not path.startswith("/")
            or ".." in PurePosixPath(path).parts
        ):
            raise ValueError("agentic v2 license evidence path is invalid")
    if (item["path"] is None) != (item["resolved_path"] is None):
        raise ValueError("agentic v2 virtual license evidence paths are invalid")
    if item["path"] is not None and item["path"] != item["resolved_path"]:
        raise ValueError("agentic v2 license evidence path did not remain lexical")
    return item


def _require_exact_path(item: Mapping[str, Any], path: str) -> None:
    if item["path"] != path:
        raise ValueError("agentic v2 license evidence source path is invalid")


def _require_resolved_under(item: Mapping[str, Any], root: str) -> None:
    resolved = item["resolved_path"]
    if resolved is None:
        raise ValueError("agentic v2 license evidence resolved path is missing")
    resolved_path = PurePosixPath(resolved)
    root_path = PurePosixPath(root)
    if root_path not in (resolved_path, *resolved_path.parents):
        raise ValueError("agentic v2 license evidence resolved path is invalid")


def _validate_record_metadata(record: dict[str, Any]) -> None:
    ecosystem = record["ecosystem"]
    metadata = record["metadata"]
    evidence = record["evidence"]
    raw_values = record["raw_values"]
    def valid_file_tokens(value: Any) -> bool:
        return (
            isinstance(value, list)
            and value == sorted(set(value))
            and len(value) <= 4096
            and all(
                isinstance(item, str)
                and _LICENSE_FILE_TOKEN_TEXT.fullmatch(item) is not None
                and "-" in item
                for item in value
            )
        )

    if ecosystem == "debian":
        status_items = [item for item in evidence if item["source"] == "debian-status"]
        copyright_items = [
            item for item in evidence if item["source"] == "debian-copyright"
        ]
        if (
            set(metadata) != {"architecture", "copyright_format"}
            or not isinstance(metadata["architecture"], str)
            or not metadata["architecture"]
            or metadata["architecture"] != metadata["architecture"].strip()
            or metadata["copyright_format"] is not None
            and not isinstance(metadata["copyright_format"], str)
            or isinstance(metadata["copyright_format"], str)
            and (
                not metadata["copyright_format"]
                or metadata["copyright_format"]
                != metadata["copyright_format"].strip()
            )
            or raw_values != sorted(set(raw_values))
            or any(
                not isinstance(item, str)
                or not item
                or item != item.strip()
                for item in raw_values
            )
            or len(status_items) != 1
            or len(copyright_items) > 1
            or len(status_items) + len(copyright_items) != len(evidence)
            or record["purl"] != (
                f"pkg:deb/debian/{quote(record['package'], safe='')}@"
                f"{quote(record['version'], safe='')}?arch="
                f"{quote(metadata['architecture'], safe='')}"
            )
        ):
            raise ValueError("agentic v2 Debian license metadata is invalid")
        _require_exact_path(status_items[0], "/var/lib/dpkg/status")
        _require_resolved_under(status_items[0], "/var/lib/dpkg")
        if copyright_items:
            _require_exact_path(
                copyright_items[0], f"/usr/share/doc/{record['package']}/copyright"
            )
            _require_resolved_under(copyright_items[0], "/usr/share/doc")
            if metadata["copyright_format"] == "":
                raise ValueError("agentic v2 Debian copyright format is invalid")
            if (
                metadata["copyright_format"] is not None
                and metadata["copyright_format"] != _DEP5_FORMAT_URI
            ):
                raise ValueError("agentic v2 Debian copyright format is invalid")
            if raw_values and metadata["copyright_format"] is None:
                raise ValueError("agentic v2 Debian license fields lack DEP-5 format")
        elif metadata["copyright_format"] is not None or raw_values:
            raise ValueError("agentic v2 Debian license fields lack evidence")
        return
    if ecosystem == "python":
        if (
            set(metadata) != {
                "license_expression", "license", "classifiers",
                "license_file_tokens", "license_files",
            }
            or any(
                metadata[key] is not None and not isinstance(metadata[key], str)
                for key in ("license_expression", "license")
            )
            or not isinstance(metadata["classifiers"], list)
            or metadata["classifiers"] != sorted(set(metadata["classifiers"]))
            or any(not isinstance(item, str) for item in metadata["classifiers"])
            or not valid_file_tokens(metadata["license_file_tokens"])
            or not isinstance(metadata["license_files"], list)
        ):
            raise ValueError("agentic v2 Python license metadata is invalid")
        expected_raw = []
        for key in ("license_expression", "license"):
            value = metadata[key]
            if isinstance(value, str) and value.strip():
                expected_raw.append(value.strip())
        expected_raw.extend(metadata["classifiers"])
        expected_raw.extend(metadata["license_file_tokens"])
        metadata_items = [item for item in evidence if item["source"] == "python-metadata"]
        license_items = [item for item in evidence if item["source"] == "python-license-file"]
        if (
            raw_values != expected_raw
            or len(metadata_items) != 1
            or len(metadata_items) + len(license_items) != len(evidence)
        ):
            raise ValueError("agentic v2 Python license evidence is invalid")
        metadata_path = metadata_items[0]["resolved_path"]
        if metadata_path is None:
            raise ValueError("agentic v2 Python METADATA path is missing")
        metadata_file = PurePosixPath(metadata_path)
        if (
            metadata_file.name not in {"METADATA", "PKG-INFO"}
            or not metadata_file.parent.name.endswith((".dist-info", ".egg-info"))
            or _PYTHON_PURELIB_PATH not in metadata_file.parents
            or metadata_file.parent.parent != _PYTHON_PURELIB_PATH
        ):
            raise ValueError("agentic v2 Python METADATA path is invalid")
        distribution_root = metadata_file.parent
        expected_paths = []
        declared = set()
        for selection in metadata["license_files"]:
            if (
                not isinstance(selection, Mapping)
                or set(selection) != {"declared", "path"}
                or not isinstance(selection["declared"], str)
                or not selection["declared"]
                or PurePosixPath(selection["declared"]).is_absolute()
                or ".." in PurePosixPath(selection["declared"]).parts
                or selection["declared"] in declared
                or not isinstance(selection["path"], str)
            ):
                raise ValueError("agentic v2 Python License-File declaration is invalid")
            declared.add(selection["declared"])
            allowed_paths = {
                str(distribution_root / "licenses" / selection["declared"]),
                str(distribution_root / selection["declared"]),
            }
            if selection["path"] not in allowed_paths:
                raise ValueError("agentic v2 Python license file path is invalid")
            expected_paths.append(selection["path"])
        if (
            metadata["license_files"]
            != sorted(
                metadata["license_files"],
                key=lambda item: (item["declared"], item["path"]),
            )
            or sorted(item["path"] for item in license_items)
            != sorted(expected_paths)
            or len(expected_paths) != len(license_items)
        ):
            raise ValueError("agentic v2 Python license file evidence is invalid")
        return
    if ecosystem == "r":
        if (
            set(metadata) != {
                "declared_license", "priority", "runtime_license",
                "runtime_license_fields", "runtime_copyright_format",
                "runtime_version",
                "license_file_tokens",
            }
            or any(
                not isinstance(metadata[key], str)
                for key in (
                    "declared_license", "runtime_license", "runtime_version",
                )
            )
            or not metadata["declared_license"]
            or not metadata["runtime_version"]
            or metadata["declared_license"]
            != metadata["declared_license"].strip()
            or metadata["runtime_version"] != metadata["runtime_version"].strip()
            or metadata["runtime_license"] != ""
            or metadata["runtime_copyright_format"] != _DEP5_FORMAT_URI
            or metadata["priority"] is not None
            and not isinstance(metadata["priority"], str)
            or isinstance(metadata["priority"], str)
            and (
                not metadata["priority"]
                or metadata["priority"] != metadata["priority"].strip()
            )
            or not isinstance(metadata["runtime_license_fields"], list)
            or metadata["runtime_license_fields"] != sorted(
                set(metadata["runtime_license_fields"])
            )
            or any(
                not isinstance(item, str)
                or not item
                or item != item.strip()
                for item in metadata["runtime_license_fields"]
            )
            or not valid_file_tokens(metadata["license_file_tokens"])
        ):
            raise ValueError("agentic v2 R license metadata is invalid")
        expected_raw = [
            value
            for value in (
                metadata["declared_license"], metadata["runtime_license"],
                *metadata["runtime_license_fields"],
                *metadata["license_file_tokens"],
            )
            if value
        ]
        sources = [item["source"] for item in evidence]
        reference = _R_LICENSE_REFERENCE.fullmatch(metadata["declared_license"])
        reference_items = [item for item in evidence if item["source"] == "r-license-file"]
        if (
            raw_values != expected_raw
            or sources.count("r-description") != 1
            or sources.count("r-runtime-description") != 1
            or sources.count("r-runtime-license") != 1
            or sources.count("r-runtime-copyright") != 1
            or any(
                source not in {
                    "r-description", "r-runtime-description", "r-runtime-license",
                    "r-runtime-copyright", "r-shared-license", "r-license-file",
                }
                for source in sources
            )
            or (reference is None and reference_items)
            or (reference is not None and len(reference_items) != 1)
        ):
            raise ValueError("agentic v2 R license evidence is invalid")
        description = next(item for item in evidence if item["source"] == "r-description")
        _require_exact_path(
            description, f"/usr/lib/R/library/{record['package']}/DESCRIPTION"
        )
        _require_resolved_under(description, "/usr/lib/R/library")
        runtime_description = next(
            item for item in evidence if item["source"] == "r-runtime-description"
        )
        _require_exact_path(
            runtime_description, "/usr/lib/R/library/base/DESCRIPTION"
        )
        _require_resolved_under(runtime_description, "/usr/lib/R/library/base")
        runtime = next(item for item in evidence if item["source"] == "r-runtime-license")
        runtime_value = {
            "version": metadata["runtime_version"],
            "license": "",
        }
        runtime_bytes = json.dumps(
            runtime_value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        if (
            runtime["path"] is not None
            or runtime["resolved_path"] is not None
            or runtime["sha256"] != hashlib.sha256(runtime_bytes).hexdigest()
            or runtime["size"] != len(runtime_bytes)
        ):
            raise ValueError("agentic v2 R runtime evidence is invalid")
        copyright_item = next(
            item for item in evidence if item["source"] == "r-runtime-copyright"
        )
        _require_exact_path(copyright_item, "/usr/share/doc/r-base-core/copyright")
        _require_resolved_under(copyright_item, "/usr/share/doc/r-base-core")
        for item in evidence:
            if item["source"] == "r-shared-license" and not str(item["path"]).startswith(
                "/usr/share/R/share/licenses/"
            ):
                raise ValueError("agentic v2 R shared license path is invalid")
            if item["source"] == "r-shared-license":
                _require_resolved_under(item, "/usr/share/R/share/licenses")
        if reference is not None:
            referenced_path = (
                f"/usr/lib/R/library/{record['package']}/{reference.group(1)}"
            )
            _require_exact_path(reference_items[0], referenced_path)
            _require_resolved_under(
                reference_items[0], f"/usr/lib/R/library/{record['package']}"
            )
        return
    if ecosystem == "npm":
        reference = _NPM_LICENSE_REFERENCE.fullmatch(metadata.get("license", ""))
        package_items = [
            item for item in evidence if item["source"] == "npm-package-json"
        ]
        reference_items = [
            item for item in evidence if item["source"] == "npm-license-file"
        ]
        if (
            set(metadata) != {"license", "license_file_tokens"}
            or not isinstance(metadata["license"], str)
            or not metadata["license"]
            or metadata["license"] != metadata["license"].strip()
            or not valid_file_tokens(metadata["license_file_tokens"])
            or raw_values != [metadata["license"], *metadata["license_file_tokens"]]
            or len(package_items) != 1
            or len(package_items) + len(reference_items) != len(evidence)
            or (reference is None and reference_items)
            or (reference is not None and len(reference_items) != 1)
        ):
            raise ValueError("agentic v2 npm license metadata is invalid")
        _require_exact_path(package_items[0], "/usr/share/nodejs/npm/package.json")
        _require_resolved_under(package_items[0], "/usr/share/nodejs/npm")
        if reference is not None:
            _require_exact_path(
                reference_items[0], f"/usr/share/nodejs/npm/{reference.group(1)}"
            )
            _require_resolved_under(reference_items[0], "/usr/share/nodejs/npm")
        return
    raise ValueError("unsupported license evidence ecosystem")


def validate_license_evidence(
    value: Any,
    sbom: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version", "collector", "records", "records_sha256",
    }:
        raise ValueError("agentic v2 license evidence fields are invalid")
    document = deepcopy(dict(value))
    if (
        document["schema_version"] != "1.0"
        or document["collector"] != "gdpval-agentic-v2-license-evidence-v1"
        or not isinstance(document["records"], list)
        or not document["records"]
        or document["records_sha256"] != canonical_sha256(document["records"])
    ):
        raise ValueError("agentic v2 license evidence identity is invalid")
    if (
        not isinstance(sbom.get("packages"), list)
        or not sbom["packages"]
    ):
        raise ValueError("agentic v2 SBOM package inventory is empty")
    packages = {
        package["externalRefs"][0]["referenceLocator"]: package
        for package in sbom["packages"]
    }
    if len(packages) != len(sbom["packages"]):
        raise ValueError("agentic v2 SBOM purl identity is invalid")
    records = {}
    ecosystem_prefixes = {
        "debian": "pkg:deb/debian/",
        "python": "pkg:pypi/",
        "r": "pkg:cran/",
        "npm": "pkg:npm/",
    }
    for raw_record in document["records"]:
        if not isinstance(raw_record, Mapping) or set(raw_record) != {
            "ecosystem", "package", "version", "purl", "raw_values",
            "metadata", "evidence",
        }:
            raise ValueError("agentic v2 license evidence record fields are invalid")
        record = dict(raw_record)
        if (
            record["ecosystem"] not in {"debian", "python", "r", "npm"}
            or not all(
                isinstance(record[key], str) and record[key]
                for key in ("package", "version", "purl")
            )
            or not record["purl"].startswith(
                ecosystem_prefixes.get(record["ecosystem"], "invalid:")
            )
            or not isinstance(record["raw_values"], list)
            or any(not isinstance(item, str) or len(item) > 1024 * 1024 for item in record["raw_values"])
            or not isinstance(record["metadata"], dict)
            or not isinstance(record["evidence"], list)
            or not record["evidence"]
            or record["purl"] in records
        ):
            raise ValueError("agentic v2 license evidence record identity is invalid")
        package = packages.get(record["purl"])
        if (
            package is None
            or package["name"] != record["package"]
            or package["versionInfo"] != record["version"]
        ):
            raise ValueError("agentic v2 license evidence differs from SBOM")
        record["evidence"] = [_validate_evidence_item(item) for item in record["evidence"]]
        _validate_record_metadata(record)
        records[record["purl"]] = record
    r_runtime_identities = {
        canonical_sha256({
            "runtime_version": record["metadata"]["runtime_version"],
            "runtime_license": record["metadata"]["runtime_license"],
            "runtime_license_fields": record["metadata"]["runtime_license_fields"],
            "runtime_copyright_format": record["metadata"][
                "runtime_copyright_format"
            ],
            "evidence": [
                item
                for item in record["evidence"]
                if item["source"] in {
                    "r-runtime-description",
                    "r-runtime-license",
                    "r-runtime-copyright",
                    "r-shared-license",
                }
            ],
        })
        for record in records.values()
        if record["ecosystem"] == "r"
    }
    if len(r_runtime_identities) > 1:
        raise ValueError("agentic v2 R runtime evidence identity is inconsistent")
    debian_status_identities = {
        canonical_sha256(next(
            item
            for item in record["evidence"]
            if item["source"] == "debian-status"
        ))
        for record in records.values()
        if record["ecosystem"] == "debian"
    }
    if len(debian_status_identities) > 1:
        raise ValueError("agentic v2 Debian status evidence identity is inconsistent")
    if set(records) != set(packages) or document["records"] != sorted(
        document["records"], key=lambda item: item["purl"]
    ):
        raise ValueError("agentic v2 license evidence package inventory mismatch")
    return document


def validate_license_exceptions(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    license_policy = policy.get("license")
    if not isinstance(license_policy, Mapping):
        raise ValueError("agentic v2 license policy is missing")
    as_of_date = license_policy.get("as_of_date")
    exceptions = license_policy.get("exceptions")
    if license_policy.get("denied_identifiers") != list(DENIED_LICENSE_IDENTIFIERS):
        raise ValueError("agentic v2 denied license identifiers are invalid")
    try:
        policy_date = date.fromisoformat(as_of_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("agentic v2 license policy date is invalid") from exc
    if not isinstance(exceptions, list):
        raise ValueError("agentic v2 license exceptions are invalid")
    validated = []
    identities = set()
    expected_fields = {
        "ecosystem", "package", "version", "purl", "normalized_expression",
        "evidence_sha256", "reason", "approver", "expires_at",
    }
    denied_identifiers = set(license_policy.get("denied_identifiers", []))
    for raw in exceptions:
        if not isinstance(raw, Mapping) or set(raw) != expected_fields:
            raise ValueError("agentic v2 license exception fields are invalid")
        item = dict(raw)
        normalized = _canonical(item["normalized_expression"])
        if (
            item["ecosystem"] not in {"debian", "python", "r", "npm"}
            or any(
                not isinstance(item[key], str)
                or not item[key]
                or item[key] != item[key].strip()
                or "*" in item[key]
                for key in (
                    "package", "version", "purl", "normalized_expression",
                    "reason", "approver", "expires_at",
                )
            )
            or not _matches(_HEX_DIGEST, item["evidence_sha256"])
            or normalized != item["normalized_expression"]
            or bool(denied_identifiers.intersection(
                _identifiers(item["normalized_expression"])
            ))
        ):
            raise ValueError("agentic v2 license exception identity is invalid")
        try:
            expires = date.fromisoformat(item["expires_at"])
        except ValueError as exc:
            raise ValueError("agentic v2 license exception expiry is invalid") from exc
        if item["expires_at"] != expires.isoformat():
            raise ValueError("agentic v2 license exception expiry is not canonical")
        if expires < policy_date:
            raise ValueError("agentic v2 license exception is expired")
        identity = (item["purl"], item["evidence_sha256"])
        if identity in identities:
            raise ValueError("agentic v2 license exception is duplicated")
        identities.add(identity)
        validated.append(item)
    return sorted(validated, key=lambda item: (item["purl"], item["evidence_sha256"]))


def _decision(
    record: Mapping[str, Any],
    denied_identifiers: set[str],
    exceptions: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    outcome = _normalize(record)
    evidence = deepcopy(record["evidence"])
    evidence_sha256 = canonical_sha256(evidence)
    policy_by_casefold = {
        identifier.casefold(): identifier for identifier in denied_identifiers
    }
    raw_identifiers = set()
    for raw in record["raw_values"]:
        for token in _EXPRESSION_TOKEN.findall(raw):
            if token.upper() in {"AND", "OR", "WITH"}:
                continue
            spdx = _spdx.LICENSES.get(token.casefold()) or _spdx.EXCEPTIONS.get(
                token.casefold()
            )
            if spdx is not None:
                raw_identifiers.add(spdx["id"])
            elif token.casefold() in policy_by_casefold:
                raw_identifiers.add(policy_by_casefold[token.casefold()])
    denied = sorted(
        denied_identifiers.intersection(outcome.identifiers | frozenset(raw_identifiers))
    )
    if denied:
        classification = "denied"
    elif outcome.expression is not None:
        classification = "resolved"
    else:
        classification = outcome.issue or "unverifiable"
    exception = exceptions.get((record["purl"], evidence_sha256))
    exception_applied = None
    normalized_expression = outcome.expression
    reason = outcome.reason
    reference_evidence_complete = True
    if record["ecosystem"] == "debian":
        reference_evidence_complete = (
            record["metadata"].get("copyright_format") == _DEP5_FORMAT_URI
            and sum(
                item["source"] == "debian-copyright"
                for item in record["evidence"]
            ) == 1
        )
    elif record["ecosystem"] == "r":
        declared = record["metadata"].get("declared_license", "")
        if isinstance(declared, str) and _R_REFERENCE_LIKE.search(declared):
            reference_evidence_complete = (
                _R_LICENSE_REFERENCE.fullmatch(declared) is not None
                and sum(
                    item["source"] == "r-license-file"
                    for item in record["evidence"]
                ) == 1
            )
    elif record["ecosystem"] == "npm":
        declared = record["metadata"].get("license", "")
        if isinstance(declared, str) and _NPM_REFERENCE_LIKE.search(declared):
            reference_evidence_complete = (
                _NPM_LICENSE_REFERENCE.fullmatch(declared) is not None
                and sum(
                    item["source"] == "npm-license-file"
                    for item in record["evidence"]
                ) == 1
            )
    if (
        exception is not None
        and classification in UNRESOLVED_CLASSIFICATIONS
        and reference_evidence_complete
    ):
        if (
            exception["ecosystem"] != record["ecosystem"]
            or exception["package"] != record["package"]
            or exception["version"] != record["version"]
        ):
            raise ValueError("agentic v2 license exception package identity mismatch")
        classification = "exception"
        normalized_expression = exception["normalized_expression"]
        reason = "package-version-specific-policy-exception"
        exception_applied = deepcopy(dict(exception))
    return {
        "ecosystem": record["ecosystem"],
        "package": record["package"],
        "version": record["version"],
        "purl": record["purl"],
        "classification": classification,
        "normalized_expression": normalized_expression,
        "raw_values": deepcopy(record["raw_values"]),
        "normalization_reason": reason,
        "denied_identifiers": denied,
        "evidence": evidence,
        "evidence_sha256": evidence_sha256,
        "exception": exception_applied,
    }


def build_license_report(
    *,
    subject: Mapping[str, Any],
    subject_sha256: str,
    sbom: Mapping[str, Any],
    license_evidence: Mapping[str, Any],
    policy: Mapping[str, Any],
    policy_sha256: str,
) -> dict[str, Any]:
    if subject_sha256 != canonical_sha256(subject):
        raise ValueError("agentic v2 license report subject hash differs")
    if policy_sha256 != canonical_sha256(policy):
        raise ValueError("agentic v2 license report policy hash differs")
    from core.agentic_v2_supply_chain import CandidateSubject, SupplyChainPolicy

    CandidateSubject.from_mapping(subject)
    SupplyChainPolicy.from_mapping(policy)
    runtime_identity = license_evaluator_runtime_identity()
    if any(
        subject.get(subject_key) != runtime_identity[runtime_key]
        for subject_key, runtime_key in (
            ("license_evaluator_packaging_version", "packaging_version"),
            ("license_evaluator_spdx_version", "spdx_version"),
            ("license_evaluator_spdx_sha256", "spdx_sha256"),
            ("license_evaluator_parser_sha256", "parser_sha256"),
            ("license_evaluator_runtime_graph_sha256", "runtime_graph_sha256"),
            ("license_evaluator_python_version", "python_version"),
            ("license_evaluator_callable_sha256", "callable_sha256"),
        )
    ):
        raise ValueError("agentic v2 license evaluator runtime binding differs")
    evidence = validate_license_evidence(license_evidence, sbom)
    exceptions = validate_license_exceptions(policy)
    exception_map = {
        (item["purl"], item["evidence_sha256"]): item
        for item in exceptions
    }
    denied_identifiers = set(policy["license"]["denied_identifiers"])
    records_by_purl = {item["purl"]: item for item in evidence["records"]}
    decisions = [
        _decision(records_by_purl[purl], denied_identifiers, exception_map)
        for purl in sorted(records_by_purl)
    ]
    applied_exceptions = {
        (decision["purl"], decision["evidence_sha256"])
        for decision in decisions
        if decision["exception"] is not None
    }
    if applied_exceptions != set(exception_map):
        raise ValueError("agentic v2 license exception is stale or unmatched")
    counts = {name: 0 for name in sorted(CLASSIFICATIONS)}
    ecosystem_counts = {
        ecosystem: {name: 0 for name in sorted(CLASSIFICATIONS)}
        for ecosystem in ("debian", "python", "r", "npm")
    }
    for decision in decisions:
        counts[decision["classification"]] += 1
        ecosystem_counts[decision["ecosystem"]][decision["classification"]] += 1
    unresolved_count = sum(counts[name] for name in UNRESOLVED_CLASSIFICATIONS)
    status = "failed" if counts["denied"] or unresolved_count else "verified"
    binding = {
        "subject_sha256": subject_sha256,
        "image_id": subject["image_id"],
        "config_digest": subject["image_id"],
        "oci_manifest_digest": subject["oci_manifest_digest"],
        "source_revision": subject["source_revision"],
        "effective_sbom_sha256": canonical_sha256(sbom),
        "license_evidence_sha256": canonical_sha256(evidence),
        "license_collector_sha256": subject["license_collector_sha256"],
        "license_evaluator_sha256": subject["license_evaluator_sha256"],
        "license_evaluator_packaging_version": runtime_identity["packaging_version"],
        "license_evaluator_spdx_version": runtime_identity["spdx_version"],
        "license_evaluator_spdx_sha256": runtime_identity["spdx_sha256"],
        "license_evaluator_parser_sha256": runtime_identity["parser_sha256"],
        "license_evaluator_runtime_graph_sha256": runtime_identity[
            "runtime_graph_sha256"
        ],
        "license_evaluator_python_version": runtime_identity["python_version"],
        "license_evaluator_callable_sha256": runtime_identity["callable_sha256"],
        "policy_sha256": policy_sha256,
    }
    report = {
        "schema_version": "2.0",
        "policy_id": policy["license"]["policy_id"],
        "foundation_only": True,
        "production_activation": "disabled",
        "status": status,
        "binding": binding,
        "package_count": len(decisions),
        "counts": counts,
        "unresolved_count": unresolved_count,
        "ecosystem_counts": ecosystem_counts,
        "exceptions": exceptions,
        "decisions": decisions,
        "decisions_sha256": canonical_sha256(decisions),
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def validate_license_report(
    value: Any,
    *,
    subject: Mapping[str, Any],
    subject_sha256: str,
    sbom: Mapping[str, Any],
    license_evidence: Mapping[str, Any],
    policy: Mapping[str, Any],
    policy_sha256: str,
) -> dict[str, Any]:
    expected = build_license_report(
        subject=subject,
        subject_sha256=subject_sha256,
        sbom=sbom,
        license_evidence=license_evidence,
        policy=policy,
        policy_sha256=policy_sha256,
    )
    if not isinstance(value, Mapping):
        raise ValueError("agentic v2 license report identity is invalid")
    supplied = deepcopy(dict(value))
    claimed = supplied.pop("report_sha256", None)
    if (
        not _matches(_HEX_DIGEST, claimed)
        or claimed != canonical_sha256(supplied)
        or canonical_sha256(value) != canonical_sha256(expected)
    ):
        raise ValueError("agentic v2 license report identity is invalid")
    return deepcopy(expected)