"""Grader-side read-only tools exposed to the v2 tool-calling judge.

Currently exports the single multi-op ``read_deliverable`` entrypoint.
Anything added here MUST stay read-only — never mutate the deliverable
or any file under the trusted base directory.
"""

from .read_deliverable import (
    get_renderer_fingerprint,
    read_deliverable,
    ReadDeliverableError,
    RendererDependencyError,
    MODEL_READ_DELIVERABLE_OPS,
    MODEL_READ_DELIVERABLE_TOOL_SCHEMA,
    READ_DELIVERABLE_OPS,
    READ_DELIVERABLE_TOOL_SCHEMA,
)

__all__ = [
    "get_renderer_fingerprint",
    "read_deliverable",
    "ReadDeliverableError",
    "RendererDependencyError",
    "MODEL_READ_DELIVERABLE_OPS",
    "MODEL_READ_DELIVERABLE_TOOL_SCHEMA",
    "READ_DELIVERABLE_OPS",
    "READ_DELIVERABLE_TOOL_SCHEMA",
]
