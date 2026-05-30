"""Grader-side read-only tools exposed to the v2 tool-calling judge.

Currently exports the single multi-op ``read_deliverable`` entrypoint.
Anything added here MUST stay read-only — never mutate the deliverable
or any file under the trusted base directory.
"""

from .read_deliverable import (
    read_deliverable,
    ReadDeliverableError,
    READ_DELIVERABLE_OPS,
    READ_DELIVERABLE_TOOL_SCHEMA,
)

__all__ = [
    "read_deliverable",
    "ReadDeliverableError",
    "READ_DELIVERABLE_OPS",
    "READ_DELIVERABLE_TOOL_SCHEMA",
]
