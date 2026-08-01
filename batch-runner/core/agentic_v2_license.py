"""Deterministic Phase 1C package-license evidence and decision contracts."""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import os
import stat
import sys
import types
import packaging
import packaging.licenses as packaging_licenses
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import quote

from packaging.licenses import InvalidLicenseExpression
from packaging.licenses import (
    canonicalize_license_expression as _packaging_canonicalize_license_expression,
)
from packaging.licenses import _spdx

from core.agentic_v2_substrate import canonical_sha256


_INTERPRETER_FROZENSET_TYPE = (
    lambda value: value in {"a", "b"}
).__code__.co_consts[1].__class__


CLASSIFICATIONS = _INTERPRETER_FROZENSET_TYPE({
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
    "825f97f04b9b94c048326625a7e56b6a0960b196964dabcf4ba7ad3e8e9b3056"
)
UNRESOLVED_CLASSIFICATIONS = _INTERPRETER_FROZENSET_TYPE({
    "missing_metadata", "ambiguous", "unverifiable",
})
_PYTHON_PURELIB_PATH = PurePosixPath("/usr/local/lib/python3.11/site-packages")
_MAX_LICENSE_EXPRESSION_LENGTH = 4096
_MAX_LICENSE_EXPRESSION_DEPTH = 64
_MAX_LICENSE_EXPRESSION_TOKENS = 512
_DEP5_FORMAT_URI = (
    "https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
)
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

_EXACT_ALIASES = types.MappingProxyType(dict(_EXACT_ALIASES))
_DEBIAN_EXACT_ALIASES = types.MappingProxyType(dict(_DEBIAN_EXACT_ALIASES))
_PYTHON_CLASSIFIERS = types.MappingProxyType(dict(_PYTHON_CLASSIFIERS))
_PYTHON_EXACT_ALIASES = types.MappingProxyType(dict(_PYTHON_EXACT_ALIASES))

@dataclass(frozen=True)
class _Outcome:
    expression: str | None
    issue: str | None
    reason: str
    identifiers: frozenset[str]


_FROZEN_OUTCOME_TYPE = _Outcome
_FROZEN_OUTCOME_INIT = _Outcome.__init__
_FROZEN_OUTCOME_INIT_CODE = _Outcome.__init__.__code__
_FROZEN_OUTCOME_INIT_DEFAULTS = _Outcome.__init__.__defaults__
_FROZEN_DATE_TYPE = date
_FROZEN_CANONICAL_SHA256 = canonical_sha256
_FROZEN_CANONICAL_SHA256_CODE = canonical_sha256.__code__
_FROZEN_CANONICAL_SHA256_DEFAULTS = canonical_sha256.__defaults__
_FROZEN_ALIAS_BINDINGS = (
    ("debian", _DEBIAN_EXACT_ALIASES),
    ("exact", _EXACT_ALIASES),
    ("python-classifiers", _PYTHON_CLASSIFIERS),
    ("python-exact", _PYTHON_EXACT_ALIASES),
)


def _callable_constant_identity(value):
    if value is None:
        return {"type": "none"}
    if value is Ellipsis:
        return {"type": "ellipsis"}
    if type(value) is bool:
        return {"type": "bool", "value": value}
    if type(value) is int:
        return {"type": "int", "value": str(value)}
    if type(value) is float:
        return {"type": "float", "value": value.hex()}
    if type(value) is complex:
        return {
            "type": "complex",
            "real": value.real.hex(),
            "imag": value.imag.hex(),
        }
    if type(value) is str:
        return {"type": "str", "value": value}
    if type(value) is bytes:
        return {"type": "bytes", "value": value.hex()}
    if type(value) is tuple:
        return {
            "type": "tuple",
            "items": [_callable_constant_identity(item) for item in value],
        }
    if type(value) is frozenset:
        items = [_callable_constant_identity(item) for item in value]
        return {
            "type": "frozenset",
            "items": sorted(
                items,
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                ),
            ),
        }
    if type(value) is _FROZEN_CODE_TYPE:
        return {"type": "code", "value": _callable_code_identity(value)}
    raise RuntimeError("agentic v2 license evaluator code constant is invalid")


def _callable_code_identity(code: types.CodeType) -> dict[str, Any]:
    return {
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "code": code.co_code.hex(),
        "constants": [
            _callable_constant_identity(value) for value in code.co_consts
        ],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
        "filename": "packaging/licenses/__init__.py",
        "name": code.co_name,
        "qualname": getattr(code, "co_qualname", code.co_name),
        "firstlineno": code.co_firstlineno,
        "line_table": getattr(code, "co_linetable", code.co_lnotab).hex(),
        "exception_table": getattr(code, "co_exceptiontable", b"").hex(),
    }


_FROZEN_FUNCTION_TYPE = (lambda: None).__class__
_FROZEN_CODE_TYPE = (lambda: None).__code__.__class__
_FROZEN_MAPPING_PROXY_TYPE = _FROZEN_FUNCTION_TYPE.__dict__.__class__
_FROZEN_BUILTIN_FUNCTION_TYPE = {}.get.__class__
_FROZEN_STR_TYPE = "".__class__
_FROZEN_BOOL_TYPE = (1 == 1).__class__
_FROZEN_DICT_TYPE = {}.__class__
_FROZEN_FLOAT_TYPE = (0.0).__class__
_FROZEN_INT_TYPE = (0).__class__
_FROZEN_LIST_TYPE = [].__class__
_FROZEN_SET_TYPE = {None}.__class__
_FROZEN_TUPLE_TYPE = ().__class__
_FROZEN_TYPE_TYPE = _FROZEN_STR_TYPE.__class__
_FROZEN_FROZENSET_TYPE = _INTERPRETER_FROZENSET_TYPE


def _capture_value_error_type():
    try:
        "".index("missing")
    except:  # noqa: E722
        return sys.exc_info()[0]
    raise RuntimeError("agentic v2 ValueError identity is unavailable")


_FROZEN_VALUE_ERROR = _capture_value_error_type()
_FROZEN_EXCEPTION = _FROZEN_VALUE_ERROR.__base__
_FROZEN_BASE_EXCEPTION = _FROZEN_EXCEPTION.__base__


def _capture_recursion_error_type():
    def recurse():
        return recurse()

    try:
        recurse()
    except _FROZEN_BASE_EXCEPTION:
        value = sys.exc_info()[0]
        if value.__module__ == "builtins" and value.__qualname__ == "RecursionError":
            return value
    raise RuntimeError("agentic v2 RecursionError identity is unavailable")


_FROZEN_RECURSION_ERROR = _capture_recursion_error_type()
_FROZEN_RUNTIME_ERROR = _FROZEN_RECURSION_ERROR.__base__


def _is_ascii_alphanumeric(value: str) -> bool:
    return (
        "0" <= value <= "9"
        or "A" <= value <= "Z"
        or "a" <= value <= "z"
    )


_FROZEN_ASCII_ALPHANUMERIC = _is_ascii_alphanumeric
_FROZEN_ASCII_ALPHANUMERIC_CODE = _is_ascii_alphanumeric.__code__


def _expression_tokens(
    value: str,
    str_type=_FROZEN_STR_TYPE,
    ascii_alphanumeric=_FROZEN_ASCII_ALPHANUMERIC,
) -> tuple[str, ...]:
    if value.__class__ is not str_type:
        return ()
    tokens = []
    start = None
    index = 0
    for character in value:
        allowed = ascii_alphanumeric(character) or character in ".+-"
        if allowed and start is None:
            start = index
        if not allowed and start is not None:
            candidate = value[start:index]
            start = None
            while candidate and candidate[-1] in ".-":
                candidate = candidate[:-1]
            if candidate and ascii_alphanumeric(candidate[0]):
                tokens.append(candidate)
        index += 1
    if start is not None:
        candidate = value[start:]
        while candidate and candidate[-1] in ".-":
            candidate = candidate[:-1]
        if candidate and ascii_alphanumeric(candidate[0]):
            tokens.append(candidate)
    return (*tokens,)


_FROZEN_EXPRESSION_TOKENS = _expression_tokens
_FROZEN_EXPRESSION_TOKENS_CODE = _expression_tokens.__code__
_FROZEN_EXPRESSION_TOKENS_DEFAULTS = _expression_tokens.__defaults__


def _license_ref_allowed(
    value: str,
    str_type=_FROZEN_STR_TYPE,
    ascii_alphanumeric=_FROZEN_ASCII_ALPHANUMERIC,
) -> bool:
    if value.__class__ is not str_type:
        return False
    for character in value:
        if not ascii_alphanumeric(character) and character not in ".-":
            return False
    return True


_FROZEN_LICENSE_REF_ALLOWED = _license_ref_allowed
_FROZEN_LICENSE_REF_ALLOWED_CODE = _license_ref_allowed.__code__
_FROZEN_LICENSE_REF_ALLOWED_DEFAULTS = _license_ref_allowed.__defaults__


def _clone_json(
    value,
    bool_type=_FROZEN_BOOL_TYPE,
    int_type=_FROZEN_INT_TYPE,
    float_type=_FROZEN_FLOAT_TYPE,
    str_type=_FROZEN_STR_TYPE,
    list_type=_FROZEN_LIST_TYPE,
    dict_type=_FROZEN_DICT_TYPE,
):
    scalar_types = {bool_type, int_type, float_type, str_type}
    def clone(item):
        if item is None or item.__class__ in scalar_types:
            return item
        if item.__class__ is list_type:
            return [clone(child) for child in item]
        if item.__class__ is dict_type:
            return {key: clone(child) for key, child in item.items()}
        raise RuntimeError("agentic v2 license JSON value type is invalid")

    return clone(value)


def _is_lower_hex(
    value,
    length: int,
    str_type=_FROZEN_STR_TYPE,
) -> bool:
    if value.__class__ is not str_type or value.__len__() != length:
        return False
    for character in value:
        if not ("0" <= character <= "9" or "a" <= character <= "f"):
            return False
    return True


def _is_license_file_token(
    value,
    str_type=_FROZEN_STR_TYPE,
    ascii_alphanumeric=_FROZEN_ASCII_ALPHANUMERIC,
) -> bool:
    if (
        value.__class__ is not str_type
        or not value
        or value.__len__() > 128
        or not ascii_alphanumeric(value[0])
    ):
        return False
    if value.__len__() > 1 and not (
        ascii_alphanumeric(value[-1]) or value[-1] == "+"
    ):
        return False
    for character in value:
        if not ascii_alphanumeric(character) and character not in ".+-":
            return False
    return True


def _ascii_words(
    value,
    str_type=_FROZEN_STR_TYPE,
    ascii_alphanumeric=_FROZEN_ASCII_ALPHANUMERIC,
) -> tuple[str, ...]:
    if value.__class__ is not str_type:
        return ()
    words = []
    start = None
    index = 0
    for character in value:
        if ascii_alphanumeric(character):
            if start is None:
                start = index
        elif start is not None:
            words.append(value[start:index].casefold())
            start = None
        index += 1
    if start is not None:
        words.append(value[start:].casefold())
    return (*words,)


def _contains_words(
    value,
    expected: tuple[str, ...],
    word_parser=_ascii_words,
) -> bool:
    words = word_parser(value)
    width = expected.__len__()
    if width == 0 or words.__len__() < width:
        return False
    index = 0
    while index <= words.__len__() - width:
        if words[index:index + width] == expected:
            return True
        index += 1
    return False


def _reference_filename(
    value,
    prefix: str,
    str_type=_FROZEN_STR_TYPE,
    ascii_alphanumeric=_FROZEN_ASCII_ALPHANUMERIC,
) -> str | None:
    if value.__class__ is not str_type or not value.startswith(prefix):
        return None
    filename = value[prefix.__len__():]
    if not filename or not ascii_alphanumeric(filename[0]):
        return None
    for character in filename:
        if not ascii_alphanumeric(character) and character not in "._+-":
            return None
    return filename


def _split_debian_operators(
    value: str,
    str_type=_FROZEN_STR_TYPE,
) -> list[str]:
    if value.__class__ is not str_type:
        return []
    tokens = []
    start = 0
    index = 0
    length = value.__len__()
    while index < length:
        if value[index] in "()":
            if start < index:
                tokens.append(value[start:index])
            tokens.append(value[index])
            index += 1
            start = index
            continue
        candidate_start = index
        if value[index] == ",":
            index += 1
            whitespace_start = index
            while index < length and value[index].isspace():
                index += 1
            if index == whitespace_start:
                index = candidate_start + 1
                continue
        elif value[index].isspace():
            while index < length and value[index].isspace():
                index += 1
        else:
            index += 1
            continue
        for operator in ("and", "or", "with"):
            end = index + operator.__len__()
            if (
                value[index:end].casefold() == operator
                and end < length
                and value[end].isspace()
            ):
                while end < length and value[end].isspace():
                    end += 1
                if start < candidate_start:
                    tokens.append(value[start:candidate_start])
                tokens.append(operator)
                index = end
                start = end
                break
        else:
            index = candidate_start + 1
    if start < length:
        tokens.append(value[start:])
    return tokens


def _freeze_spdx_collection(value, label: str):
    if type(value) is not dict:
        raise RuntimeError(f"agentic v2 {label} SPDX table is invalid")
    frozen = {}
    for key, item in value.items():
        if (
            type(key) is not str
            or type(item) is not dict
            or type(item.get("id")) is not str
            or not item["id"]
        ):
            raise RuntimeError(f"agentic v2 {label} SPDX table is invalid")
        frozen[key] = _FROZEN_MAPPING_PROXY_TYPE({"id": item["id"]})
    return _FROZEN_MAPPING_PROXY_TYPE(frozen)


_FROZEN_LICENSES = _freeze_spdx_collection(_spdx.LICENSES, "license")
_FROZEN_EXCEPTIONS = _freeze_spdx_collection(_spdx.EXCEPTIONS, "exception")
_REGISTERED_SPDX_IDENTIFIERS = _FROZEN_FROZENSET_TYPE(
    value["id"]
    for collection in (_FROZEN_LICENSES, _FROZEN_EXCEPTIONS)
    for value in collection.values()
)
_TRUSTED_COMPILE = builtins.compile
_TRUSTED_LEN = builtins.len
_TRUSTED_ALL = builtins.all
_TRUSTED_ANY = builtins.any
_TRUSTED_BOOL = builtins.bool
_TRUSTED_DICT = builtins.dict
_TRUSTED_FROZENSET = builtins.frozenset
_TRUSTED_GETATTR = builtins.getattr
_TRUSTED_HASATTR = builtins.hasattr
_TRUSTED_ISINSTANCE = builtins.isinstance
_TRUSTED_LIST = builtins.list
_TRUSTED_MAX = builtins.max
_TRUSTED_MIN = builtins.min
_TRUSTED_NEXT = builtins.next
_TRUSTED_SET = builtins.set
_TRUSTED_SORTED = builtins.sorted
_TRUSTED_STR = builtins.str
_TRUSTED_SUM = builtins.sum
_TRUSTED_TUPLE = builtins.tuple
_TRUSTED_TYPE = builtins.type
_FROZEN_UPSTREAM_PARSER_CODE = (
    _packaging_canonicalize_license_expression.__code__
)


def _capture_syntax_error_type():
    try:
        _TRUSTED_COMPILE("(", "", "eval")
    except _FROZEN_BASE_EXCEPTION:
        return sys.exc_info()[0]
    raise RuntimeError("agentic v2 SyntaxError identity is unavailable")


_TRUSTED_SYNTAX_ERROR = _capture_syntax_error_type()


class _TransformLicenseParser(ast.NodeTransformer):
    def __init__(self) -> None:
        self.cast_replacements = 0
        self.license_ref_replacements = 0

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "cast"
            and len(node.args) == 2
            and not node.keywords
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "NormalizedLicenseExpression"
        ):
            self.cast_replacements += 1
            return ast.copy_location(node.args[1], node)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "match"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "license_ref_allowed"
            and len(node.args) == 1
            and not node.keywords
        ):
            self.license_ref_replacements += 1
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id="_license_ref_allowed", ctx=ast.Load()),
                    args=node.args,
                    keywords=[],
                ),
                node,
            )
        return node


def _read_frozen_parser_source() -> bytes:
    path = Path(str(packaging_licenses.__file__))
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size < 0
            or before.st_size > 1024 * 1024
        ):
            raise RuntimeError("agentic v2 license parser source is invalid")
        chunks = []
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    source = b"".join(chunks)
    def identity(value):
        return (
            value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns,
        )

    if (
        identity(before) != identity(after)
        or len(source) != before.st_size
        or hashlib.sha256(source).hexdigest() != LICENSE_EVALUATOR_PARSER_SHA256
    ):
        raise RuntimeError("agentic v2 license parser source identity differs")
    return source


def _build_frozen_parser_code() -> types.CodeType:
    tree = ast.parse(
        _read_frozen_parser_source(),
        filename="packaging/licenses/__init__.py",
        mode="exec",
    )
    functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "canonicalize_license_expression"
    ]
    if len(functions) != 1 or not isinstance(functions[0], ast.FunctionDef):
        raise RuntimeError("agentic v2 license parser function is invalid")
    function = functions[0]
    function.decorator_list = []
    function.returns = None
    for argument in (
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ):
        argument.annotation = None
    transformer = _TransformLicenseParser()
    function = transformer.visit(function)
    if (
        transformer.cast_replacements != 1
        or transformer.license_ref_replacements != 1
    ):
        raise RuntimeError("agentic v2 license parser transform shape is invalid")
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {"__builtins__": {}}
    exec(
        _TRUSTED_COMPILE(
            module,
            "packaging/licenses/__init__.py",
            "exec",
            dont_inherit=True,
            optimize=2,
        ),
        namespace,
    )
    parser = namespace.get("canonicalize_license_expression")
    if type(parser) is not _FROZEN_FUNCTION_TYPE:
        raise RuntimeError("agentic v2 frozen license parser is invalid")
    return parser.__code__


_FROZEN_PARSER_CODE = _build_frozen_parser_code()


def _license_parser_binding_identity() -> dict[str, Any]:
    if (
        builtins.compile is not _TRUSTED_COMPILE
        or builtins.len is not _TRUSTED_LEN
        or builtins.all is not _TRUSTED_ALL
        or builtins.any is not _TRUSTED_ANY
        or builtins.bool is not _TRUSTED_BOOL
        or builtins.dict is not _TRUSTED_DICT
        or builtins.frozenset is not _TRUSTED_FROZENSET
        or builtins.getattr is not _TRUSTED_GETATTR
        or builtins.hasattr is not _TRUSTED_HASATTR
        or builtins.isinstance is not _TRUSTED_ISINSTANCE
        or builtins.list is not _TRUSTED_LIST
        or builtins.max is not _TRUSTED_MAX
        or builtins.min is not _TRUSTED_MIN
        or builtins.next is not _TRUSTED_NEXT
        or builtins.set is not _TRUSTED_SET
        or builtins.sorted is not _TRUSTED_SORTED
        or builtins.str is not _TRUSTED_STR
        or builtins.sum is not _TRUSTED_SUM
        or builtins.tuple is not _TRUSTED_TUPLE
        or builtins.type is not _TRUSTED_TYPE
        or builtins.SyntaxError is not _TRUSTED_SYNTAX_ERROR
        or _TRUSTED_SYNTAX_ERROR.__module__ != "builtins"
        or _TRUSTED_SYNTAX_ERROR.__qualname__ != "SyntaxError"
        or _TRUSTED_SYNTAX_ERROR.__mro__[1:] != (
            _FROZEN_EXCEPTION,
            _FROZEN_BASE_EXCEPTION,
            object,
        )
        or _FROZEN_VALUE_ERROR.__module__ != "builtins"
        or _FROZEN_VALUE_ERROR.__qualname__ != "ValueError"
        or _FROZEN_VALUE_ERROR.__mro__[1:] != (
            _FROZEN_EXCEPTION,
            _FROZEN_BASE_EXCEPTION,
            object,
        )
        or builtins.RecursionError is not _FROZEN_RECURSION_ERROR
        or _FROZEN_RECURSION_ERROR.__mro__[1:] != (
            _FROZEN_RUNTIME_ERROR,
            _FROZEN_EXCEPTION,
            _FROZEN_BASE_EXCEPTION,
            object,
        )
        or InvalidLicenseExpression is not packaging_licenses.InvalidLicenseExpression
        or InvalidLicenseExpression.__module__ != "packaging.licenses"
        or InvalidLicenseExpression.__qualname__ != "InvalidLicenseExpression"
        or InvalidLicenseExpression.__bases__ != (_FROZEN_VALUE_ERROR,)
        or _packaging_canonicalize_license_expression.__defaults__ is not None
        or _packaging_canonicalize_license_expression.__kwdefaults__ is not None
        or _packaging_canonicalize_license_expression.__closure__ is not None
    ):
        raise RuntimeError("agentic v2 license evaluator binding identity differs")
    try:
        _TRUSTED_COMPILE("(", "", "eval")
    except _FROZEN_BASE_EXCEPTION:
        if sys.exc_info()[0] is not _TRUSTED_SYNTAX_ERROR:
            raise RuntimeError(
                "agentic v2 license evaluator builtin behavior differs"
            )
    else:
        raise RuntimeError("agentic v2 license evaluator builtin behavior differs")
    return {
        "builtins": [
            _trusted_builtin_identity(_TRUSTED_ALL, "all"),
            _trusted_builtin_identity(_TRUSTED_ANY, "any"),
            _trusted_builtin_identity(_TRUSTED_COMPILE, "compile"),
            _trusted_builtin_identity(_TRUSTED_GETATTR, "getattr"),
            _trusted_builtin_identity(_TRUSTED_HASATTR, "hasattr"),
            _trusted_builtin_identity(_TRUSTED_ISINSTANCE, "isinstance"),
            _trusted_builtin_identity(_TRUSTED_LEN, "len"),
            _trusted_builtin_identity(_TRUSTED_MAX, "max"),
            _trusted_builtin_identity(_TRUSTED_MIN, "min"),
            _trusted_builtin_identity(_TRUSTED_NEXT, "next"),
            _trusted_builtin_identity(_TRUSTED_SORTED, "sorted"),
            _trusted_builtin_identity(_TRUSTED_SUM, "sum"),
            _trusted_type_identity(_TRUSTED_BOOL, _FROZEN_BOOL_TYPE, "bool"),
            _trusted_type_identity(_TRUSTED_DICT, _FROZEN_DICT_TYPE, "dict"),
            _trusted_type_identity(
                _TRUSTED_FROZENSET,
                _FROZEN_FROZENSET_TYPE,
                "frozenset",
            ),
            _trusted_type_identity(_TRUSTED_LIST, _FROZEN_LIST_TYPE, "list"),
            _trusted_type_identity(_TRUSTED_SET, _FROZEN_SET_TYPE, "set"),
            _trusted_type_identity(_TRUSTED_STR, _FROZEN_STR_TYPE, "str"),
            _trusted_type_identity(_TRUSTED_TUPLE, _FROZEN_TUPLE_TYPE, "tuple"),
            _trusted_type_identity(_TRUSTED_TYPE, _FROZEN_TYPE_TYPE, "type"),
            {"module": "builtins", "qualname": "SyntaxError"},
            {"module": "builtins", "qualname": "ValueError"},
            {"module": "builtins", "qualname": "RecursionError"},
        ],
        "exceptions": sorted(
            (key, value["id"]) for key, value in _FROZEN_EXCEPTIONS.items()
        ),
        "invalid_expression": {
            "module": "builtins",
            "qualname": "ValueError",
        },
        "licenses": sorted(
            (key, value["id"]) for key, value in _FROZEN_LICENSES.items()
        ),
        "transform": "remove-cast-and-license-ref-regex-v2",
        "function_type": {"module": "builtins", "qualname": "function"},
    }


def _execute_frozen_license_parser(
    value: str,
    _code=_FROZEN_PARSER_CODE,
    _function_type=_FROZEN_FUNCTION_TYPE,
    _compile=_TRUSTED_COMPILE,
    _length=_TRUSTED_LEN,
    _syntax_error=_TRUSTED_SYNTAX_ERROR,
    _licenses=_FROZEN_LICENSES,
    _exceptions=_FROZEN_EXCEPTIONS,
    _license_ref_allowed=_FROZEN_LICENSE_REF_ALLOWED,
    _invalid_expression=_FROZEN_VALUE_ERROR,
):
    parser_globals = {
        "__builtins__": {
            "compile": _compile,
            "len": _length,
            "SyntaxError": _syntax_error,
        },
        "EXCEPTIONS": _exceptions,
        "InvalidLicenseExpression": _invalid_expression,
        "LICENSES": _licenses,
        "_license_ref_allowed": _license_ref_allowed,
    }
    parser = _function_type(
        _code,
        parser_globals,
        "canonicalize_license_expression",
    )
    return parser(value)


_FROZEN_PARSER_EXECUTOR = _execute_frozen_license_parser
_FROZEN_PARSER_EXECUTOR_CODE = _execute_frozen_license_parser.__code__
_FROZEN_PARSER_EXECUTOR_DEFAULTS = _execute_frozen_license_parser.__defaults__


def _trusted_builtin_identity(value, name: str) -> dict[str, str]:
    if (
        value.__class__ is not _FROZEN_BUILTIN_FUNCTION_TYPE
        or value.__module__ != "builtins"
        or value.__name__ != name
        or value.__qualname__ != name
        or value.__self__ is not builtins
    ):
        raise RuntimeError("agentic v2 license evaluator builtin identity differs")
    return {"module": "builtins", "qualname": name}


def _trusted_type_identity(value, expected, name: str) -> dict[str, str]:
    if (
        value is not expected
        or value.__class__ is not _FROZEN_TYPE_TYPE
        or value.__module__ != "builtins"
        or value.__name__ != name
        or value.__qualname__ != name
    ):
        raise RuntimeError("agentic v2 license evaluator type identity differs")
    return {"module": "builtins", "qualname": name}


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
        or _packaging_canonicalize_license_expression
        is not packaging_licenses.canonicalize_license_expression
        or _packaging_canonicalize_license_expression.__module__
        != "packaging.licenses"
        or _packaging_canonicalize_license_expression.__qualname__
        != "canonicalize_license_expression"
        or not hasattr(_packaging_canonicalize_license_expression, "__code__")
        or Path(
            _packaging_canonicalize_license_expression.__code__.co_filename
        ) != parser_path
        or _packaging_canonicalize_license_expression.__code__
        is not _FROZEN_UPSTREAM_PARSER_CODE
        or _packaging_canonicalize_license_expression.__globals__
        is not packaging_licenses.__dict__
        or _execute_frozen_license_parser is not _FROZEN_PARSER_EXECUTOR
        or _execute_frozen_license_parser.__code__
        is not _FROZEN_PARSER_EXECUTOR_CODE
        or _execute_frozen_license_parser.__defaults__
        is not _FROZEN_PARSER_EXECUTOR_DEFAULTS
        or _is_ascii_alphanumeric is not _FROZEN_ASCII_ALPHANUMERIC
        or _is_ascii_alphanumeric.__code__
        is not _FROZEN_ASCII_ALPHANUMERIC_CODE
        or _expression_tokens is not _FROZEN_EXPRESSION_TOKENS
        or _expression_tokens.__code__ is not _FROZEN_EXPRESSION_TOKENS_CODE
        or _expression_tokens.__defaults__
        is not _FROZEN_EXPRESSION_TOKENS_DEFAULTS
        or _license_ref_allowed is not _FROZEN_LICENSE_REF_ALLOWED
        or _license_ref_allowed.__code__ is not _FROZEN_LICENSE_REF_ALLOWED_CODE
        or _license_ref_allowed.__defaults__
        is not _FROZEN_LICENSE_REF_ALLOWED_DEFAULTS
        or _identifiers is not _FROZEN_IDENTIFIERS
        or _identifiers.__code__ is not _FROZEN_IDENTIFIERS_CODE
        or _identifiers.__defaults__ is not _FROZEN_IDENTIFIERS_DEFAULTS
        or _valid_expression_shape is not _FROZEN_VALID_EXPRESSION_SHAPE
        or _valid_expression_shape.__code__
        is not _FROZEN_VALID_EXPRESSION_SHAPE_CODE
        or _valid_expression_shape.__defaults__
        is not _FROZEN_VALID_EXPRESSION_SHAPE_DEFAULTS
        or _canonical is not _FROZEN_CANONICAL
        or _canonical.__code__ is not _FROZEN_CANONICAL_CODE
        or _canonical.__defaults__ is not _FROZEN_CANONICAL_DEFAULTS
        or _classification_surface_identity
        is not _FROZEN_CLASSIFICATION_IDENTITY
        or _classification_surface_identity.__code__
        is not _FROZEN_CLASSIFICATION_IDENTITY_CODE
        or _classification_surface_identity.__defaults__
        is not _FROZEN_CLASSIFICATION_IDENTITY_DEFAULTS
        or _Outcome is not _FROZEN_OUTCOME_TYPE
        or _Outcome.__init__ is not _FROZEN_OUTCOME_INIT
        or _Outcome.__init__.__code__ is not _FROZEN_OUTCOME_INIT_CODE
        or _Outcome.__init__.__defaults__ is not _FROZEN_OUTCOME_INIT_DEFAULTS
        or date is not _FROZEN_DATE_TYPE
        or canonical_sha256 is not _FROZEN_CANONICAL_SHA256
        or canonical_sha256.__code__ is not _FROZEN_CANONICAL_SHA256_CODE
        or canonical_sha256.__defaults__ is not _FROZEN_CANONICAL_SHA256_DEFAULTS
        or types.FunctionType is not _FROZEN_FUNCTION_TYPE
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
    current_licenses = _freeze_spdx_collection(_spdx.LICENSES, "license")
    current_exceptions = _freeze_spdx_collection(_spdx.EXCEPTIONS, "exception")
    if (
        dict(current_licenses) != dict(_FROZEN_LICENSES)
        or dict(current_exceptions) != dict(_FROZEN_EXCEPTIONS)
    ):
        raise RuntimeError("agentic v2 license evaluator SPDX bindings differ")
    alias_globals = {
        "debian": _DEBIAN_EXACT_ALIASES,
        "exact": _EXACT_ALIASES,
        "python-classifiers": _PYTHON_CLASSIFIERS,
        "python-exact": _PYTHON_EXACT_ALIASES,
    }
    for name, mapping in _FROZEN_ALIAS_BINDINGS:
        if (
            alias_globals.get(name) is not mapping
            or mapping.__class__ is not _FROZEN_MAPPING_PROXY_TYPE
            or any(
                key.__class__ is not _FROZEN_STR_TYPE
                or value.__class__ is not _FROZEN_STR_TYPE
                for key, value in mapping.items()
            )
        ):
            raise RuntimeError("agentic v2 license alias bindings differ")
    policy_date = _FROZEN_DATE_TYPE.fromisoformat("2026-07-31")
    later_date = _FROZEN_DATE_TYPE.fromisoformat("2027-07-31")
    if (
        policy_date.__class__ is not _FROZEN_DATE_TYPE
        or policy_date.isoformat() != "2026-07-31"
        or later_date.__class__ is not _FROZEN_DATE_TYPE
        or not policy_date < later_date
        or _FROZEN_DATE_TYPE.__module__ != "datetime"
        or _FROZEN_DATE_TYPE.__qualname__ != "date"
    ):
        raise RuntimeError("agentic v2 license date binding differs")
    if (
        _FROZEN_IDENTIFIERS_DEFAULTS != (
            _FROZEN_EXPRESSION_TOKENS,
            _FROZEN_FROZENSET_TYPE,
        )
        or _FROZEN_EXPRESSION_TOKENS_DEFAULTS != (
            _FROZEN_STR_TYPE,
            _FROZEN_ASCII_ALPHANUMERIC,
        )
        or _FROZEN_LICENSE_REF_ALLOWED_DEFAULTS != (
            _FROZEN_STR_TYPE,
            _FROZEN_ASCII_ALPHANUMERIC,
        )
        or _FROZEN_VALID_EXPRESSION_SHAPE_DEFAULTS != (
            _FROZEN_STR_TYPE,
            _TRUSTED_LEN,
            _MAX_LICENSE_EXPRESSION_LENGTH,
            _MAX_LICENSE_EXPRESSION_DEPTH,
            _MAX_LICENSE_EXPRESSION_TOKENS,
        )
        or _FROZEN_CANONICAL_DEFAULTS != (
            _FROZEN_PARSER_EXECUTOR,
            _FROZEN_VALID_EXPRESSION_SHAPE,
            _FROZEN_IDENTIFIERS,
            _REGISTERED_SPDX_IDENTIFIERS,
            (_FROZEN_VALUE_ERROR, _FROZEN_RECURSION_ERROR),
            _FROZEN_STR_TYPE,
        )
    ):
        raise RuntimeError("agentic v2 canonicalizer bindings differ")
    callable_sha256 = canonical_sha256({
        "aliases": {
            name: sorted(mapping.items())
            for name, mapping in _FROZEN_ALIAS_BINDINGS
        },
        "bindings": _license_parser_binding_identity(),
        "canonical": _callable_code_identity(_FROZEN_CANONICAL_CODE),
        "canonical_sha256": _callable_code_identity(
            _FROZEN_CANONICAL_SHA256_CODE
        ),
        "classification_checker": _callable_code_identity(
            _FROZEN_CLASSIFICATION_IDENTITY_CODE
        ),
        "classification_surface": _classification_surface_identity(),
        "canonical_bindings": {
            "errors": ["builtins.RecursionError", "builtins.ValueError"],
            "expression_tokenizer": "ascii-alnum-dot-plus-hyphen-v1",
            "limits": {
                "depth": _MAX_LICENSE_EXPRESSION_DEPTH,
                "length": _MAX_LICENSE_EXPRESSION_LENGTH,
                "tokens": _MAX_LICENSE_EXPRESSION_TOKENS,
            },
            "registered": sorted(_REGISTERED_SPDX_IDENTIFIERS),
            "return_type": "builtins.str",
        },
        "executor": _callable_code_identity(_FROZEN_PARSER_EXECUTOR_CODE),
        "expression_tokens": _callable_code_identity(
            _FROZEN_EXPRESSION_TOKENS_CODE
        ),
        "identifiers": _callable_code_identity(_FROZEN_IDENTIFIERS_CODE),
        "license_ref_allowed": _callable_code_identity(
            _FROZEN_LICENSE_REF_ALLOWED_CODE
        ),
        "outcome": {
            "init": _callable_code_identity(_FROZEN_OUTCOME_INIT_CODE),
            "module": _FROZEN_OUTCOME_TYPE.__module__,
            "qualname": _FROZEN_OUTCOME_TYPE.__qualname__,
        },
        "parser": _callable_code_identity(_FROZEN_PARSER_CODE),
        "shape": _callable_code_identity(
            _FROZEN_VALID_EXPRESSION_SHAPE_CODE
        ),
        "date": {
            "module": "datetime",
            "qualname": "date",
            "ordering": "2026-07-31<2027-07-31",
        },
    })
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


def _identifiers(
    expression: str,
    tokenizer=_FROZEN_EXPRESSION_TOKENS,
    frozen_type=_FROZEN_FROZENSET_TYPE,
) -> frozenset[str]:
    return frozen_type(
        token
        for token in tokenizer(expression)
        if token not in {"AND", "OR", "WITH"}
    )


def _valid_expression_shape(
    expression: Any,
    str_type=_FROZEN_STR_TYPE,
    length=_TRUSTED_LEN,
    max_length=_MAX_LICENSE_EXPRESSION_LENGTH,
    max_depth=_MAX_LICENSE_EXPRESSION_DEPTH,
    max_tokens=_MAX_LICENSE_EXPRESSION_TOKENS,
) -> bool:
    if (
        expression.__class__ is not str_type
        or length(expression) > max_length
    ):
        return False
    depth = 0
    maximum_depth = 0
    tokens = 0
    in_token = False
    for character in expression:
        if character == "(":
            depth += 1
            if depth > maximum_depth:
                maximum_depth = depth
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
            maximum_depth > max_depth
            or tokens > max_tokens
        ):
            return False
    return depth == 0


def _canonical(
    expression: Any,
    parser=_FROZEN_PARSER_EXECUTOR,
    valid_shape=_valid_expression_shape,
    identifiers=_identifiers,
    registered=_REGISTERED_SPDX_IDENTIFIERS,
    errors=(_FROZEN_VALUE_ERROR, _FROZEN_RECURSION_ERROR),
    str_type=_FROZEN_STR_TYPE,
) -> str | None:
    if not valid_shape(expression):
        return None
    try:
        canonical = parser(expression)
    except errors:
        return None
    if canonical.__class__ is not str_type:
        return None
    if not identifiers(canonical).issubset(registered):
        return None
    return canonical


_FROZEN_IDENTIFIERS = _identifiers
_FROZEN_IDENTIFIERS_CODE = _identifiers.__code__
_FROZEN_IDENTIFIERS_DEFAULTS = _identifiers.__defaults__
_FROZEN_VALID_EXPRESSION_SHAPE = _valid_expression_shape
_FROZEN_VALID_EXPRESSION_SHAPE_CODE = _valid_expression_shape.__code__
_FROZEN_VALID_EXPRESSION_SHAPE_DEFAULTS = _valid_expression_shape.__defaults__
_FROZEN_CANONICAL = _canonical
_FROZEN_CANONICAL_CODE = _canonical.__code__
_FROZEN_CANONICAL_DEFAULTS = _canonical.__defaults__


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
        _FROZEN_FROZENSET_TYPE(),
    )


def _combine(operator: str, outcomes: list[_Outcome], reason: str) -> _Outcome:
    identifiers = _FROZEN_FROZENSET_TYPE().union(
        *(item.identifiers for item in outcomes)
    )
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
            _FROZEN_FROZENSET_TYPE(),
        )
    direct = _atom(raw, {**_EXACT_ALIASES, **_DEBIAN_EXACT_ALIASES})
    if direct.expression is not None:
        return direct
    tokens = [
        token for token in _split_debian_operators(raw)
        if token and token.strip()
    ]
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
    all_identifiers = _FROZEN_FROZENSET_TYPE().union(*(
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
            _FROZEN_FROZENSET_TYPE().union(*(
                item.identifiers for item in outcomes + classifier_values
            )),
        )
    if resolved:
        return _Outcome(
            resolved[0], None,
            "python-license-field-or-classifier",
            _identifiers(resolved[0]),
        )
    if not record["raw_values"]:
        return _Outcome(
            None,
            "missing_metadata",
            "python-license-metadata-missing",
            _FROZEN_FROZENSET_TYPE(),
        )
    return _Outcome(
        None,
        "unverifiable",
        "python-license-metadata-unverifiable",
        _FROZEN_FROZENSET_TYPE(),
    )


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
            _FROZEN_FROZENSET_TYPE(),
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
        if metadata.get("runtime_copyright_format") != _DEP5_FORMAT_URI:
            return _Outcome(
                None,
                "unverifiable",
                "r-runtime-copyright-unstructured",
                _FROZEN_FROZENSET_TYPE(),
            )
        if not isinstance(runtime, str) or not runtime:
            return _Outcome(
                None,
                "missing_metadata",
                "r-runtime-license-missing",
                _FROZEN_FROZENSET_TYPE(),
            )
        if not _valid_expression_shape(runtime):
            return _Outcome(
                None,
                "unverifiable",
                "invalid-r-license-expression-shape",
                _FROZEN_FROZENSET_TYPE(),
            )
        parts = [part.strip() for part in runtime.split("|")]
        if not parts or any(not part for part in parts):
            return _Outcome(
                None, "unverifiable", "invalid-r-license-alternatives",
                _FROZEN_FROZENSET_TYPE(),
            )
        outcomes = [_atom(part, _DEBIAN_EXACT_ALIASES) for part in parts]
        return _combine("OR", outcomes, "r-base-runtime-license")
    if isinstance(declared, str) and declared.startswith("Part of R"):
        return _Outcome(
            None,
            "unverifiable",
            "invalid-r-runtime-license-reference",
            _FROZEN_FROZENSET_TYPE(),
        )
    if isinstance(declared, str) and declared:
        parts = [part.strip() for part in declared.split("|")]
        if not parts or any(not part for part in parts):
            return _Outcome(
                None, "unverifiable", "invalid-r-license-alternatives",
                _FROZEN_FROZENSET_TYPE(),
            )
        outcomes = [_atom(part, _DEBIAN_EXACT_ALIASES) for part in parts]
        return _combine("OR", outcomes, "r-description-license")
    return _Outcome(
        None,
        "missing_metadata",
        "r-license-metadata-missing",
        _FROZEN_FROZENSET_TYPE(),
    )


def _normalize(record: Mapping[str, Any]) -> _Outcome:
    ecosystem = record["ecosystem"]
    if ecosystem == "debian":
        raw_values = record["raw_values"]
        if not raw_values:
            if any(
                item["source"] == "debian-copyright-path-unverifiable"
                for item in record["evidence"]
            ):
                return _Outcome(
                    None,
                    "unverifiable",
                    "debian-copyright-path-unverifiable",
                    _FROZEN_FROZENSET_TYPE(),
                )
            if not any(
                item["source"] == "debian-copyright"
                for item in record["evidence"]
            ):
                return _Outcome(
                    None,
                    "missing_metadata",
                    "debian-copyright-metadata-missing",
                    _FROZEN_FROZENSET_TYPE(),
                )
            return _Outcome(
                None, "unverifiable", "debian-copyright-has-no-dep5-license-fields",
                _FROZEN_FROZENSET_TYPE(),
            )
        outcomes = [_debian_expression(value) for value in raw_values]
        return _combine("AND", outcomes, "debian-file-stanza-license-conjunction")
    if ecosystem == "python":
        return _python_outcome(record)
    if ecosystem == "r":
        return _r_outcome(record)
    if ecosystem == "npm":
        if not record["raw_values"]:
            return _Outcome(
                None,
                "missing_metadata",
                "npm-license-missing",
                _FROZEN_FROZENSET_TYPE(),
            )
        return _atom(record["raw_values"][0], _EXACT_ALIASES)
    raise ValueError("unsupported license evidence ecosystem")


def _validate_evidence_item(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or {item for item in value} != {
        "source", "path", "resolved_path", "sha256", "size",
    }:
        raise ValueError("agentic v2 license evidence item fields are invalid")
    item = dict(value)
    if (
        not isinstance(item["source"], str)
        or not item["source"]
        or not _is_lower_hex(item["sha256"], 64)
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
    if item["path"] is None and item["resolved_path"] is not None:
        raise ValueError("agentic v2 virtual license evidence paths are invalid")
    if (
        item["path"] is not None
        and item["resolved_path"] is None
        and item["source"] != "debian-copyright-path-unverifiable"
    ):
        raise ValueError("agentic v2 unresolved license evidence source is invalid")
    if (
        item["resolved_path"] is not None
        and item["path"] != item["resolved_path"]
    ):
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
            and value == sorted({item for item in value})
            and len(value) <= 4096
            and all(
                isinstance(item, str)
                and _is_license_file_token(item)
                and "-" in item
                for item in value
            )
        )

    if ecosystem == "debian":
        status_items = [item for item in evidence if item["source"] == "debian-status"]
        copyright_items = [
            item for item in evidence if item["source"] == "debian-copyright"
        ]
        unverifiable_path_items = [
            item for item in evidence
            if item["source"] == "debian-copyright-path-unverifiable"
        ]
        if (
            {item for item in metadata} != {"architecture", "copyright_format"}
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
            or raw_values != sorted({item for item in raw_values})
            or any(
                not isinstance(item, str)
                or not item
                or item != item.strip()
                for item in raw_values
            )
            or len(status_items) != 1
            or len(copyright_items) > 1
            or len(unverifiable_path_items) > 1
            or copyright_items and unverifiable_path_items
            or len(status_items) + len(copyright_items)
            + len(unverifiable_path_items) != len(evidence)
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
        elif unverifiable_path_items:
            item = unverifiable_path_items[0]
            path = f"/usr/share/doc/{record['package']}/copyright"
            _require_exact_path(item, path)
            observation = json.dumps(
                {"path": path, "reason": "symlink-or-nondirectory"},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
            if (
                item["resolved_path"] is not None
                or item["sha256"] != hashlib.sha256(observation).hexdigest()
                or item["size"] != len(observation)
                or metadata["copyright_format"] is not None
                or raw_values
            ):
                raise ValueError(
                    "agentic v2 Debian unverifiable path evidence is invalid"
                )
        elif metadata["copyright_format"] is not None or raw_values:
            raise ValueError("agentic v2 Debian license fields lack evidence")
        return
    if ecosystem == "python":
        if (
            {item for item in metadata} != {
                "license_expression", "license", "classifiers",
                "license_file_tokens", "license_files",
            }
            or any(
                metadata[key] is not None and not isinstance(metadata[key], str)
                for key in ("license_expression", "license")
            )
            or not isinstance(metadata["classifiers"], list)
            or metadata["classifiers"] != sorted({
                item for item in metadata["classifiers"]
            })
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
        declared = {item for item in ()}
        for selection in metadata["license_files"]:
            if (
                not isinstance(selection, Mapping)
                or {item for item in selection} != {"declared", "path"}
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
            {item for item in metadata} != {
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
            or metadata["runtime_copyright_format"] is not None
            and metadata["runtime_copyright_format"] != _DEP5_FORMAT_URI
            or metadata["priority"] is not None
            and not isinstance(metadata["priority"], str)
            or isinstance(metadata["priority"], str)
            and (
                not metadata["priority"]
                or metadata["priority"] != metadata["priority"].strip()
            )
            or not isinstance(metadata["runtime_license_fields"], list)
            or metadata["runtime_license_fields"] != sorted({
                item for item in metadata["runtime_license_fields"]
            })
            or any(
                not isinstance(item, str)
                or not item
                or item != item.strip()
                for item in metadata["runtime_license_fields"]
            )
            or metadata["runtime_license_fields"]
            and metadata["runtime_copyright_format"] != _DEP5_FORMAT_URI
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
        reference = _reference_filename(metadata["declared_license"], "file ")
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
            f"/usr/lib/R/library/{record['package']}/{reference}"
            )
            _require_exact_path(reference_items[0], referenced_path)
            _require_resolved_under(
                reference_items[0], f"/usr/lib/R/library/{record['package']}"
            )
        return
    if ecosystem == "npm":
        reference = _reference_filename(
            metadata.get("license", ""),
            "SEE LICENSE IN ",
        )
        package_items = [
            item for item in evidence if item["source"] == "npm-package-json"
        ]
        reference_items = [
            item for item in evidence if item["source"] == "npm-license-file"
        ]
        if (
            {item for item in metadata} != {"license", "license_file_tokens"}
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
                reference_items[0], f"/usr/share/nodejs/npm/{reference}"
            )
            _require_resolved_under(reference_items[0], "/usr/share/nodejs/npm")
        return
    raise ValueError("unsupported license evidence ecosystem")


def validate_license_evidence(
    value: Any,
    sbom: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or {item for item in value} != {
        "schema_version", "collector", "records", "records_sha256",
    }:
        raise ValueError("agentic v2 license evidence fields are invalid")
    document = _clone_json({key: item for key, item in value.items()})
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
        if not isinstance(raw_record, Mapping) or {item for item in raw_record} != {
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
    if (
        {item for item in records} != {item for item in packages}
        or document["records"] != sorted(
        document["records"], key=lambda item: item["purl"]
        )
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
    identities = {item for item in ()}
    expected_fields = {
        "ecosystem", "package", "version", "purl", "normalized_expression",
        "evidence_sha256", "reason", "approver", "expires_at",
    }
    denied_identifiers = {
        item for item in license_policy.get("denied_identifiers", [])
    }
    for raw in exceptions:
        if not isinstance(raw, Mapping) or {item for item in raw} != expected_fields:
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
            or not _is_lower_hex(item["evidence_sha256"], 64)
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
    evidence = _clone_json(record["evidence"])
    evidence_sha256 = canonical_sha256(evidence)
    policy_by_casefold = {
        identifier.casefold(): identifier for identifier in denied_identifiers
    }
    raw_identifiers = {item for item in ()}
    for raw in record["raw_values"]:
        for token in _FROZEN_EXPRESSION_TOKENS(raw):
            if token.upper() in {"AND", "OR", "WITH"}:
                continue
            spdx = _FROZEN_LICENSES.get(
                token.casefold()
            ) or _FROZEN_EXCEPTIONS.get(token.casefold())
            if spdx is not None:
                raw_identifiers.add(spdx["id"])
            elif token.casefold() in policy_by_casefold:
                raw_identifiers.add(policy_by_casefold[token.casefold()])
    denied = sorted(
        denied_identifiers.intersection(
            outcome.identifiers | _FROZEN_FROZENSET_TYPE(raw_identifiers)
        )
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
        runtime_version = record["metadata"].get("runtime_version")
        if (
            isinstance(declared, str)
            and _contains_words(declared, ("part", "of", "r"))
        ):
            reference_evidence_complete = (
                declared == f"Part of R {runtime_version}"
                and record["metadata"].get("priority") == "base"
                and record["metadata"].get("runtime_copyright_format")
                == _DEP5_FORMAT_URI
                and sum(
                    item["source"] == "r-runtime-copyright"
                    for item in record["evidence"]
                ) == 1
            )
        elif isinstance(declared, str) and _contains_words(declared, ("file",)):
            reference_evidence_complete = (
            _reference_filename(declared, "file ") is not None
                and sum(
                    item["source"] == "r-license-file"
                    for item in record["evidence"]
                ) == 1
            )
    elif record["ecosystem"] == "npm":
        declared = record["metadata"].get("license", "")
        if (
            isinstance(declared, str)
            and _contains_words(declared, ("see", "license", "in"))
        ):
            reference_evidence_complete = (
                _reference_filename(declared, "SEE LICENSE IN ") is not None
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
        exception_applied = _clone_json({
            key: item for key, item in exception.items()
        })
    return {
        "ecosystem": record["ecosystem"],
        "package": record["package"],
        "version": record["version"],
        "purl": record["purl"],
        "classification": classification,
        "normalized_expression": normalized_expression,
        "raw_values": _clone_json(record["raw_values"]),
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
    denied_identifiers = {
        item for item in policy["license"]["denied_identifiers"]
    }
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
    if applied_exceptions != {item for item in exception_map}:
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


_CLASSIFICATION_SURFACE_NAMES = (
    "_clone_json",
    "_is_lower_hex",
    "_is_license_file_token",
    "_ascii_words",
    "_contains_words",
    "_reference_filename",
    "_split_debian_operators",
    "_identifiers",
    "_valid_expression_shape",
    "_canonical",
    "_atom",
    "_combine",
    "_debian_expression",
    "_python_outcome",
    "_r_outcome",
    "_normalize",
    "_validate_evidence_item",
    "_validate_record_metadata",
    "validate_license_evidence",
    "validate_license_exceptions",
    "_decision",
    "build_license_report",
)
_MODULE_GLOBALS = globals()
_FROZEN_CLASSIFICATION_SURFACE = _FROZEN_MAPPING_PROXY_TYPE({
    name: (
        _MODULE_GLOBALS[name],
        _MODULE_GLOBALS[name].__code__,
        _MODULE_GLOBALS[name].__defaults__,
        _MODULE_GLOBALS[name].__kwdefaults__,
    )
    for name in _CLASSIFICATION_SURFACE_NAMES
})


def _classification_surface_identity(
    _module_globals=_MODULE_GLOBALS,
    _surface=_FROZEN_CLASSIFICATION_SURFACE,
    _names=_CLASSIFICATION_SURFACE_NAMES,
) -> dict[str, Any]:
    identity = {}
    for name in _names:
        expected_function, expected_code, expected_defaults, expected_kwdefaults = (
            _surface[name]
        )
        current = _module_globals.get(name)
        if (
            current is not expected_function
            or current.__code__ is not expected_code
            or current.__defaults__ is not expected_defaults
            or current.__kwdefaults__ is not expected_kwdefaults
        ):
            raise RuntimeError(
                "agentic v2 license classification surface differs"
            )
        identity[name] = _callable_code_identity(expected_code)
    return identity


_FROZEN_CLASSIFICATION_IDENTITY = _classification_surface_identity
_FROZEN_CLASSIFICATION_IDENTITY_CODE = _classification_surface_identity.__code__
_FROZEN_CLASSIFICATION_IDENTITY_DEFAULTS = (
    _classification_surface_identity.__defaults__
)


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
    supplied = _clone_json({key: item for key, item in value.items()})
    claimed = supplied.pop("report_sha256", None)
    if (
        not _is_lower_hex(claimed, 64)
        or claimed != canonical_sha256(supplied)
        or canonical_sha256(value) != canonical_sha256(expected)
    ):
        raise ValueError("agentic v2 license report identity is invalid")
    return _clone_json(expected)