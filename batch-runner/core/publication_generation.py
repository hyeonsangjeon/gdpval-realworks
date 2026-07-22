"""Run freshness identity shared by preparation, relay, and publication."""

from __future__ import annotations

import os
import re
import uuid


GENERATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}")


def validate_publication_generation(value: object) -> str:
    if not isinstance(value, str) or GENERATION_RE.fullmatch(value) is None:
        raise ValueError("publication generation is missing or invalid")
    return value


def resolve_publication_generation(experiment_id: str) -> str:
    lineage = os.getenv("GDPVAL_RELAY_LINEAGE_ID", "").strip()
    if lineage:
        return validate_publication_generation(lineage)
    github_run = os.getenv("GITHUB_RUN_ID", "").strip()
    if github_run:
        github_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1").strip()
        return validate_publication_generation(
            f"{experiment_id}:{github_run}:{github_attempt}"
        )
    return validate_publication_generation(
        f"{experiment_id}:local:{uuid.uuid4().hex}"
    )