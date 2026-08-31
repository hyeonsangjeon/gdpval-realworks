"""Spec-driven assembly of the sandbox codegen prompt (sandbox-only).

P2 of the prompt-consolidation refactor. Historically ``SandboxRunner._augment_prompt``
hardcoded both the *order* of the prompt sections and their separators. This module
turns that structure into data: each section is produced by a thin **provider**
(a pure ``SectionContext -> str | None`` function that adapts an existing fragment
module), and the *order* is owned by the prompt spec (``sections:`` in
``prompts/sandbox_occupation_codegen.yaml``), falling back to :data:`DEFAULT_SECTIONS`.

No fragment logic lives here — providers only call the already-tested builders
(``build_file_structure_info``, ``SkillsRegistry.render_manual``,
``DependencyManifest.to_prompt_hint``, ``DeliverableContract.to_prompt_section``,
``generate_all_previews``). A provider returning ``None``/"" means *omit this
section*, preserving today's per-block emptiness rules. Unknown section ids raise
loudly so a typo in the spec never silently drops a section.

Privacy: providers surface only basenames/sanitized text (``available_files`` uses
``os.path.basename``; previews render filename + structure, not host roots). The
context carries host paths only to feed the fragment builders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Union

from core.file_preview import build_file_structure_info, generate_all_previews


@dataclass(frozen=True)
class SectionContext:
    """Everything a section provider may read. Sandbox-only; never mutated."""

    task_prompt: str
    ref_files: List[str]
    skills: object
    manifest: object            # DependencyManifest (avoid import cycle in typing)
    contract: object            # DeliverableContract | None
    reflection: Optional[str]
    registry: object            # SkillsRegistry
    perception_text: Optional[str] = None   # P3; None in P0-P2
    host_reference_access: bool = True


def _available_files_line(ref_files: List[str]) -> str:
    names = [os.path.basename(f) for f in ref_files]
    return (
        f"📁 Files available in the sandbox working directory "
        f"(use them directly): {names}"
    )


# id -> provider. Each provider returns the section text, or None to omit it.
# Keep these thin: adapt an existing module, do not add fragment logic here.
SECTION_PROVIDERS: Dict[str, Callable[[SectionContext], Optional[str]]] = {
    "reflection": lambda c: c.reflection or None,
    "file_structure": lambda c: (
        build_file_structure_info(c.ref_files or []) or None
        if c.host_reference_access
        else None
    ),
    "skills_manual": lambda c: c.registry.render_manual(c.skills) or None,
    "deps_hint": lambda c: c.manifest.to_prompt_hint() or None,
    "contract": lambda c: (c.contract.to_prompt_section() if c.contract is not None else None),
    "perception_analysis": lambda c: c.perception_text or None,   # P3
    "task": lambda c: c.task_prompt or None,
    "previews": lambda c: (
        (generate_all_previews(c.ref_files) or None)
        if c.ref_files and c.host_reference_access
        else None
    ),
    "available_files": lambda c: _available_files_line(c.ref_files) if c.ref_files else None,
}


# Fallback order, byte-identical to the pre-refactor hardcoded assembly. The
# canonical order lives in the spec's ``sections:`` list; this reproduces it when
# a spec omits the key. ``perception_analysis`` is intentionally absent here
# (enabled via the spec in P3) so default output is unchanged.
DEFAULT_SECTIONS: List[str] = [
    "reflection",
    "file_structure",
    "skills_manual",
    "deps_hint",
    "contract",
    "task",
    "previews",
    "available_files",
]


SectionEntry = Union[str, dict]


def _parse_entry(entry: SectionEntry):
    """A spec ``sections:`` entry is either a bare id string or ``{id, enabled?}``."""
    if isinstance(entry, str):
        return entry, True
    if isinstance(entry, dict):
        if "id" not in entry:
            raise ValueError(f"prompt section entry missing 'id': {entry!r}")
        return entry["id"], bool(entry.get("enabled", True))
    raise ValueError(f"invalid prompt section entry (want str or mapping): {entry!r}")


def enabled_section_ids(section_order: List[SectionEntry]) -> List[str]:
    """The ids :func:`assemble_sections` will ask a provider for, in order.

    Entries with ``enabled: false`` are left out, because a spec that switches a
    section off is a spec whose requests do not carry it. A malformed entry
    raises here for the same reason it raises there.

    Read by ``core/first_request_sections.py``: what a run place puts in its
    first request past the rendered prompt depends on which of these the spec
    leaves on, and reading the spec is the only way to know. Unknown ids are
    *not* rejected here — that is :func:`assemble_sections`'s refusal to make,
    against the provider table, and making it twice would put two answers in
    the repository for one question.
    """
    ids: List[str] = []
    for entry in section_order:
        sid, enabled = _parse_entry(entry)
        if enabled:
            ids.append(sid)
    return ids


def assemble_sections(section_order: List[SectionEntry], ctx: SectionContext) -> str:
    """Render ``section_order`` against ``ctx`` and join non-empty blocks with blank lines.

    Entries with ``enabled: false`` are skipped; providers returning ``None``/""
    are omitted; an unknown id raises ``ValueError`` (fail-fast, never silent).
    """
    parts: List[str] = []
    for entry in section_order:
        sid, enabled = _parse_entry(entry)
        if not enabled:
            continue
        provider = SECTION_PROVIDERS.get(sid)
        if provider is None:
            raise ValueError(
                f"unknown prompt section id: {sid!r}; known ids: {sorted(SECTION_PROVIDERS)}"
            )
        block = provider(ctx)
        if block:
            parts.append(block)
    return "\n\n".join(parts)
