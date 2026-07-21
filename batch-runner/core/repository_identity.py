"""Validated repository and experiment identifiers used across the pipeline."""

from __future__ import annotations

import re

_EXPERIMENT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
_HF_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def validate_experiment_id(value: object) -> str:
    """Return a Git path/ref-safe experiment identifier."""
    if (
        not isinstance(value, str)
        or not _EXPERIMENT_ID_RE.fullmatch(value)
        or ".." in value
        or value.endswith((".", ".lock"))
    ):
        raise ValueError("experiment.id must be a safe identifier")
    return value


def validate_hf_dataset_repo_id(value: object) -> str:
    """Return a canonical Hugging Face ``owner/repository`` dataset ID."""
    if not isinstance(value, str) or len(value) > 96 or value.count("/") != 1:
        raise ValueError("data.source must be a valid owner/repository ID")
    owner, repo = value.split("/", 1)
    if not owner or not repo:
        raise ValueError("data.source must be a valid owner/repository ID")
    for component in (owner, repo):
        if (
            not _HF_COMPONENT_RE.fullmatch(component)
            or ".." in component
            or "--" in component
            or component.startswith((".", "-"))
            or component.endswith((".", "-"))
        ):
            raise ValueError("data.source must be a valid owner/repository ID")
    if repo.endswith(".git"):
        raise ValueError("data.source must be a valid owner/repository ID")
    return value
