"""Skills Registry — discover, select, and render Agent Skills for the sandbox.

Parses every ``skills/<name>/SKILL.md`` (YAML front-matter + markdown body),
then selects the skills relevant to a task by matching reference-file extensions
and task-text keywords. Selected skills' manuals are injected into the
code-generation prompt so the model knows the exact callable API, and the
``skills`` package is mounted into the sandbox so generated code can import it.

Usage::

    from core.skills_registry import SkillsRegistry

    reg = SkillsRegistry()                       # auto-discovers batch-runner/skills
    selected = reg.select(reference_files, task_text)
    manual = reg.render_manual(selected)         # -> str for prompt injection
    names = [s.name for s in selected]           # -> ['video', 'audio', ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# Default skills directory: batch-runner/skills
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# Per-extension weight is much higher than per-keyword so that a task whose
# reference files clearly belong to a modality always pulls in that skill.
_EXT_WEIGHT = 10
_KW_WEIGHT = 1


@dataclass
class Skill:
    """One parsed SKILL.md pack."""

    name: str
    title: str
    description: str
    modalities: List[str]
    file_extensions: List[str]
    keywords: List[str]
    requires: List[str]
    version: str
    body: str
    api: str
    path: Path
    # Populated during selection:
    score: int = 0
    matched_extensions: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "modalities": self.modalities,
            "requires": self.requires,
            "score": self.score,
            "matched_extensions": self.matched_extensions,
            "matched_keywords": self.matched_keywords,
        }


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a SKILL.md into (front_matter_dict, body)."""
    if text.lstrip().startswith("---"):
        # Strip a leading BOM/whitespace, then split on the front-matter fences.
        stripped = text.lstrip()
        parts = stripped.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            return meta, parts[2].lstrip("\n")
    return {}, text


def _extract_api_section(body: str) -> str:
    """Return the ``## Toolkit API`` section (heading + content) or ""."""
    match = re.search(
        r"(^##\s+Toolkit API\b.*?)(?=^##\s+|\Z)",
        body,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _norm_ext(ext: str) -> str:
    ext = ext.strip().lower()
    return ext if ext.startswith(".") else f".{ext}"


class SkillsRegistry:
    """Discovers and selects Agent Skills."""

    def __init__(self, skills_dir: Optional[str | Path] = None):
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self._skills: Dict[str, Skill] = {}
        self._load()

    # ── discovery ────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.skills_dir.exists():
            return
        for skill_md in sorted(self.skills_dir.glob("*/SKILL.md")):
            try:
                skill = self._parse_skill(skill_md)
                self._skills[skill.name] = skill
            except Exception as exc:  # pragma: no cover - defensive
                print(f"⚠️  SkillsRegistry: failed to parse {skill_md}: {exc}")

    def _parse_skill(self, skill_md: Path) -> Skill:
        text = skill_md.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(text)
        name = str(meta.get("name") or skill_md.parent.name)
        return Skill(
            name=name,
            title=str(meta.get("title", name)),
            description=str(meta.get("description", "")).strip(),
            modalities=[str(m) for m in (meta.get("modalities") or [])],
            file_extensions=[_norm_ext(e) for e in (meta.get("file_extensions") or [])],
            keywords=[str(k).lower() for k in (meta.get("keywords") or [])],
            requires=[str(r) for r in (meta.get("requires") or [])],
            version=str(meta.get("version", "0.0.0")),
            body=body,
            api=_extract_api_section(body),
            path=skill_md.parent,
        )

    # ── access ───────────────────────────────────────────────────────────
    @property
    def skills(self) -> Dict[str, Skill]:
        return dict(self._skills)

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def all_required_packages(self) -> List[str]:
        """Union of ``requires:`` across every skill (for image provisioning)."""
        seen: List[str] = []
        for skill in self._skills.values():
            for pkg in skill.requires:
                if pkg not in seen:
                    seen.append(pkg)
        return seen

    # ── selection ────────────────────────────────────────────────────────
    def select(
        self,
        reference_files: Optional[List[str]] = None,
        task_text: str = "",
        max_skills: int = 5,
    ) -> List[Skill]:
        """Return skills relevant to a task, highest score first.

        Scoring: each reference file whose extension belongs to a skill adds
        ``_EXT_WEIGHT``; each task keyword found in ``task_text`` adds
        ``_KW_WEIGHT``. Skills with a positive score are returned.
        """
        exts = [Path(f).suffix.lower() for f in (reference_files or [])]
        text = (task_text or "").lower()

        scored: List[Skill] = []
        for skill in self._skills.values():
            matched_ext = [e for e in exts if e in skill.file_extensions]
            matched_kw = [k for k in skill.keywords if k in text]
            score = len(matched_ext) * _EXT_WEIGHT + len(matched_kw) * _KW_WEIGHT
            if score <= 0:
                continue
            # Return a per-selection copy so the registry stays reusable.
            chosen = Skill(**{**skill.__dict__})
            chosen.score = score
            chosen.matched_extensions = sorted(set(matched_ext))
            chosen.matched_keywords = matched_kw
            scored.append(chosen)

        scored.sort(key=lambda s: (-s.score, s.name))
        return scored[:max_skills]

    # ── prompt rendering ─────────────────────────────────────────────────
    def render_manual(self, skills: List[Skill], max_chars: int = 7000) -> str:
        """Render a compact skills manual for prompt injection."""
        if not skills:
            return ""
        lines = [
            "🧰 AVAILABLE SKILLS (pre-installed in the sandbox; import directly):",
            "",
            "Import with: `from skills import "
            + ", ".join(s.name for s in skills)
            + "`",
            "Use these helpers instead of hand-rolling perception/IO. They wrap "
            "famous libraries with safe defaults.",
            "",
        ]
        for skill in skills:
            why = []
            if skill.matched_extensions:
                why.append("files: " + ", ".join(skill.matched_extensions))
            if skill.matched_keywords:
                why.append("keywords: " + ", ".join(skill.matched_keywords[:6]))
            reason = f"  (matched {'; '.join(why)})" if why else ""
            lines.append(f"── Skill `{skill.name}` — {skill.title}{reason}")
            if skill.description:
                lines.append(skill.description)
            if skill.api:
                lines.append(skill.api)
            lines.append("")

        manual = "\n".join(lines).strip()
        if len(manual) > max_chars:
            manual = manual[:max_chars].rstrip() + "\n… (skills manual truncated)"
        return manual
