#!/usr/bin/env python3
"""Validate DefaultAzureCredential-based Azure AI routes without model calls."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.azure_ai_clients import (  # noqa: E402
    FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
    AzureAIRouteSettings,
    AzureAIWorkload,
    EndpointKind,
    preflight_routes,
    verify_route_tokens,
)


_ROUTE_ENV_NAMES = (
    "AZURE_AI_ROUTE_PROFILE",
    "AZURE_OPENAI_V1_ENDPOINT",
    "FOUNDRY_PROJECT_ENDPOINT",
    "AZURE_OPENAI_LEGACY_ENDPOINT",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_AI_ALLOW_LEGACY_ROLLBACK",
    "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES",
    "AZURE_AI_EXPECTED_DIRECT_ACCOUNT",
    "AZURE_AI_EXPECTED_PROJECT_ACCOUNT",
    "AZURE_AI_EXPECTED_PROJECT_NAME",
    "AZURE_AI_EXPECTED_LEGACY_ACCOUNT",
    *FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
)


def _contains_control(value: str) -> bool:
    return any(
        unicodedata.category(character) == "Cc"
        or character in {"\u2028", "\u2029"}
        for character in value
    )


def _plain_value(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if _contains_control(value):
        raise ValueError(
            f"{label} must not contain newline or control characters"
        )
    return value


def _workload(value: str) -> tuple[AzureAIWorkload, str]:
    try:
        plain = _plain_value(value, "workload")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None
    name, separator, deployment = plain.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("workload must use NAME=DEPLOYMENT")
    try:
        workload = AzureAIWorkload(name.strip())
    except ValueError:
        raise argparse.ArgumentTypeError("unsupported workload name") from None
    if not deployment.strip():
        raise argparse.ArgumentTypeError("deployment must be nonempty")
    return workload, deployment.strip()


def _environment_workloads(
    parser: argparse.ArgumentParser,
    env: Mapping[str, str],
) -> list[tuple[AzureAIWorkload, str]]:
    try:
        encoded = _plain_value(
            env.get("AZURE_AI_WORKLOADS_JSON", ""),
            "AZURE_AI_WORKLOADS_JSON",
        ).strip()
    except ValueError as exc:
        parser.error(str(exc))
    if not encoded:
        return []
    try:
        values = json.loads(encoded)
    except json.JSONDecodeError:
        parser.error("AZURE_AI_WORKLOADS_JSON is invalid JSON")
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        parser.error("AZURE_AI_WORKLOADS_JSON must be a list of strings")

    workloads: list[tuple[AzureAIWorkload, str]] = []
    for value in values:
        try:
            workloads.append(_workload(value))
        except argparse.ArgumentTypeError as exc:
            parser.error(f"AZURE_AI_WORKLOADS_JSON: {exc}")
    return workloads


def _validate_route_environment(env: Mapping[str, str]) -> None:
    for name in _ROUTE_ENV_NAMES:
        if name in env:
            _plain_value(env[name], name)


def _absolute_output_path(raw_path: object) -> Path:
    """Return an absolute output path after lexical injection checks."""
    value = _plain_value(raw_path, "GITHUB_OUTPUT")
    if not value:
        raise ValueError("GITHUB_OUTPUT must be nonempty")
    candidate = Path(value)
    if ".." in candidate.parts:
        raise ValueError("GITHUB_OUTPUT must not traverse parent directories")
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return Path(os.path.abspath(candidate))


def _append_github_output(raw_path: object, encoded: str) -> None:
    """Append one record with one write through non-symlink path components."""
    path = _absolute_output_path(raw_path)
    if len(path.parts) < 2:
        raise ValueError("GITHUB_OUTPUT must identify a file")
    if _contains_control(encoded):
        raise ValueError("routes output must not contain control characters")
    payload = f"routes={encoded}\n".encode("utf-8")

    directory_flags = (
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    directory_fd = os.open("/", directory_flags)
    file_fd: int | None = None
    try:
        for component in path.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd

        target = path.parts[-1]
        try:
            target_stat = os.stat(
                target,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            target_stat = None
        if target_stat is not None and not stat.S_ISREG(target_stat.st_mode):
            raise ValueError("GITHUB_OUTPUT target must be a regular file")

        created = target_stat is None
        file_flags = (
            os.O_WRONLY
            | os.O_APPEND
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
            | os.O_NONBLOCK
        )
        if created:
            file_flags |= os.O_CREAT | os.O_EXCL
        file_fd = os.open(
            target,
            file_flags,
            0o600,
            dir_fd=directory_fd,
        )
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise ValueError("GITHUB_OUTPUT target must be a regular file")
        if created:
            os.fchmod(file_fd, 0o600)
        if os.write(file_fd, payload) != len(payload):
            raise OSError("short write while appending GITHUB_OUTPUT")
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(directory_fd)


def _token_evidence(
    workloads: Sequence[tuple[AzureAIWorkload, str]],
    settings: AzureAIRouteSettings,
) -> list[str]:
    """Say what acquiring a token did and did not establish.

    This is the last gate in ``batch-run.yml`` before Step 2a spends money, so
    a green tick here is read as "the routes will work". It is not that, and
    exp032 is the run that proves the difference: this step passed, and then
    all five of its tasks came back ``PermissionDeniedError (http 403)`` from
    the project-scoped Code Interpreter route.

    Two independent reasons the check could not have seen it. Audiences are
    deduplicated -- ``verify_route_tokens`` collects ``token_scope`` into a
    set, and the project-scoped and account-scoped routes share one audience,
    so several routes collapse into a single ``get_token``. And a token is
    issued by the control plane, which does not consult the data-plane role
    assignment that returns the 403; no endpoint is contacted at all.

    Neither is a defect to repair here. Acquiring an identical token once per
    route would prove nothing the first one did not, and calling the endpoint
    would make a free check a paid one. What was missing is this: the run
    never said which of its routes went unexercised, so nothing warned anyone
    before the money was spent. The detail goes to stderr and the gap itself
    goes out as a ``::warning::`` annotation, which reaches the run summary
    instead of the middle of a step log. Neither goes to stdout, which is the
    records contract that step 2 and step 8 consume unchanged.

    The record count is deduplicated on ``(workload, deployment)``, the same
    identity ``preflight_routes`` deduplicates on, so the number stated here
    is the number of records this run emitted and not a larger one.
    """
    identities = sorted(
        {(workload, deployment.strip()) for workload, deployment in workloads}
    )
    selections = [settings.select(workload) for workload, _ in identities]
    audiences = sorted({selection.token_scope for selection in selections})
    unexercised = sorted(
        {
            f"{selection.workload.value}={selection.endpoint.kind.value}"
            for selection in selections
        }
    )
    detail = (
        f"this token check issued {len(audiences)} token(s), one per distinct "
        f"audience, covering {len(identities)} typed route record(s), and "
        "called no endpoint. It therefore does not establish that these "
        f"routes will answer a call: {', '.join(unexercised)}."
    )
    if any(
        selection.endpoint.kind is EndpointKind.PROJECT
        for selection in selections
    ):
        detail += (
            " A project-scoped route whose identity holds no project-level "
            "role is issued a token by the control plane and then refuses "
            "every call with http 403; exp032 passed this step and lost all "
            "five of its tasks that way."
        )
    return [
        f"token audiences: {', '.join(audiences)}",
        f"token check covered: {', '.join(unexercised)}",
        f"::warning::{detail}",
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workload",
        action="append",
        type=_workload,
        help="Typed workload and deployment as NAME=DEPLOYMENT",
    )
    parser.add_argument(
        "--verify-token",
        action="store_true",
        help=(
            "Also acquire a token per audience from DefaultAzureCredential. "
            "Proves the control plane will issue a token; proves nothing "
            "about whether a route will answer a call"
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    token_verifier: Callable[[], None] | None = None,
) -> list[dict[str, str]]:
    parser = _build_parser()
    args = parser.parse_args(argv)
    values = os.environ if env is None else env

    workloads = list(args.workload or [])
    workloads.extend(_environment_workloads(parser, values))
    if not workloads:
        parser.error("at least one workload is required")

    try:
        _validate_route_environment(values)
        settings = AzureAIRouteSettings.from_env(values)
        records = preflight_routes(workloads, settings=settings)
    except ValueError as exc:
        parser.error(str(exc))
    except Exception:
        parser.error("Azure AI route preflight failed")

    if args.verify_token:
        try:
            if token_verifier is not None:
                token_verifier()
            else:
                verify_route_tokens(workloads, settings=settings)
        except Exception:
            parser.error("Azure AI route token verification failed")
        # Only after it passed. A green token check is the thing that gets
        # over-read, so the scope of what it proved is printed with it.
        for line in _token_evidence(workloads, settings):
            print(line, file=sys.stderr)

    encoded = json.dumps(records, sort_keys=True, separators=(",", ":"))
    output_path = values.get("GITHUB_OUTPUT", "")
    if output_path != "":
        try:
            _append_github_output(output_path, encoded)
        except (OSError, ValueError):
            parser.error(
                "GITHUB_OUTPUT must be a regular non-symlink file with "
                "non-symlink ancestors"
            )
    print(encoded)
    return records


if __name__ == "__main__":
    main()