"""Deliverable contract & selector for the sandbox output control loop.

Skills give the sandbox *eyes/ears/hands* on the **inputs**. This module answers
the complementary question about the **outputs**: *"what file(s) is this task
supposed to PRODUCE, and did the generated code actually produce them?"*

It is deliberately deterministic (no LLM calls) so it can:

1. Infer a :class:`DeliverableContract` from the task text + reference-file list
   *before* code generation, and inject a compact ``DELIVERABLE CONTRACT`` block
   into the codegen prompt so the model knows exactly what to emit.
2. After execution, separate **generated** artifacts from **reference/input**
   files (set-diff + explicit reference exclusion) so a copied input is never
   mistaken for a deliverable.
3. Validate the produced artifacts against the contract and surface blocking
   failures (wrong/missing primary type, no deliverable at all) that the repair
   loop can feed back to the model.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

# Control / bookkeeping files the runner writes into the workdir. They are never
# counted as task deliverables even though they live alongside them.
RESERVED_NAMES: Set[str] = {"solution.py", "manifest.json"}

# Creation verbs that indicate the task expects a tangible file deliverable.
_CREATION_VERBS = (
    "create", "generate", "produce", "build", "make", "write", "draft",
    "prepare", "design", "compose", "develop", "fill", "update", "complete",
    "convert", "export", "save", "assemble", "compile", "format", "plot",
    "chart", "summarize", "summarise", "analyze", "analyse", "calculate",
)

Confidence = str  # "high" | "medium" | "low"


def _has_word(text: str, *words: str) -> bool:
    for w in words:
        if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text):
            return True
    return False


# 1) Explicit extension tokens / unambiguous format words (highest signal).
#    Each entry: ext, HIGH-confidence words (literal type tokens), MEDIUM
#    words (format nouns that might instead refer to an *input* file).
_EXPLICIT_EXTENSION_RULES = [
    (".xlsx", ("xlsx",), ("excel", "workbook", "spreadsheet"), "Excel/spreadsheet requested"),
    (".pptx", ("pptx",), ("powerpoint", "slide deck", "slides", "deck", "presentation"), "PowerPoint/slides requested"),
    (".docx", ("docx",), ("word document", "word doc"), "Word document requested"),
    (".pdf", ("pdf",), (), "PDF requested"),
    (".csv", ("csv",), (), "CSV requested"),
    (".tsv", ("tsv",), (), "TSV requested"),
    (".json", ("json",), (), "JSON requested"),
    (".mp4", ("mp4",), ("video", "animation", "screencast", "montage"), "Video requested"),
    (".mp3", ("mp3",), (), "MP3 audio requested"),
    (".wav", ("wav",), (), "WAV audio requested"),
    (".zip", ("zip",), ("archive", "bundle"), "Archive requested"),
    (".md", ("markdown",), (), "Markdown requested"),
    (".html", ("html",), ("webpage", "web page"), "HTML requested"),
]

# 2) Softer deliverable nouns -> a likely (medium-confidence) type, unless an
#    explicit type already covered it.
_DELIVERABLE_NOUN_RULES = [
    ((".docx",), ("memo", "letter", "report", "write-up", "writeup", "essay",
                  "cover letter", "meeting notes", "minutes", "brief"),
     "Prose deliverable (memo/report/letter)"),
    ((".pdf",), ("flyer", "one-pager", "one pager", "brochure", "poster",
                 "form", "datasheet", "fact sheet", "factsheet", "handout"),
     "Print/layout deliverable"),
    ((".png",), ("logo", "icon", "chart", "graph", "diagram", "screenshot",
                 "infographic", "storyboard", "mockup", "wireframe",
                 "figure", "plot", "image"),
     "Graphic/image deliverable"),
    ((".wav",), ("audio", "podcast", "voiceover", "voice-over", "soundtrack",
                 "song", "music", "jingle", "narration"),
     "Audio deliverable"),
    ((".xlsx",), ("model", "tracker", "budget", "schedule", "roster",
                  "dashboard", "pivot", "ledger"),
     "Tabular deliverable"),
]


def detection_vocabulary() -> List[str]:
    """Every word :func:`_detect_extensions` can match, deduped, order-stable.

    Worked out from the two tables above on every call rather than written out
    again here, so adding a word moves whatever holds a figure against this
    instead of leaving a stale one behind.

    Read by ``core/first_request_sections.py``, which drives
    :func:`infer_deliverable_contract` to the widest contract these tables can
    produce so a cost ceiling can be built on it. A copy kept in that module
    would go stale silently, and the bill would then be understated by whatever
    the copy missed.
    """
    words: List[str] = []
    seen: Set[str] = set()
    for _ext, high_words, med_words, _note in _EXPLICIT_EXTENSION_RULES:
        for word in (*high_words, *med_words):
            if word not in seen:
                seen.add(word)
                words.append(word)
    for _exts, nouns, _note in _DELIVERABLE_NOUN_RULES:
        for word in nouns:
            if word not in seen:
                seen.add(word)
                words.append(word)
    return words


def _detect_extensions(text: str) -> List[Dict]:
    """Return ordered ext detections: list of {ext, confidence, note}."""
    t = text.lower()
    hits: List[Dict] = []
    seen: Set[str] = set()

    def add(ext: str, confidence: Confidence, note: str) -> None:
        if ext in seen:
            return
        seen.add(ext)
        hits.append({"ext": ext, "confidence": confidence, "note": note})

    for ext, high_words, med_words, note in _EXPLICIT_EXTENSION_RULES:
        if _has_word(t, *high_words):
            add(ext, "high", note)
        elif med_words and _has_word(t, *med_words):
            add(ext, "medium", note)

    for exts, words, note in _DELIVERABLE_NOUN_RULES:
        if _has_word(t, *words):
            for ext in exts:
                add(ext, "medium", note)

    # 3) Explicit-override refinements.
    refined: List[Dict] = []
    for h in hits:
        ext = h["ext"]
        # "csv" explicitly trumps a generic spreadsheet guess.
        if ext == ".xlsx" and _has_word(t, "csv") and not _has_word(
            t, "xlsx", "excel", "workbook"
        ):
            continue
        # "pdf" explicitly trumps a generic docx guess.
        if ext == ".docx" and _has_word(t, "pdf") and not _has_word(
            t, "docx", "word document", "word doc"
        ):
            continue
        refined.append(h)
    return refined


@dataclass
class DeliverableContract:
    """What the task is expected to PRODUCE, inferred deterministically."""

    expected_extensions: List[str] = field(default_factory=list)
    min_count: int = 1
    max_count: Optional[int] = None
    required_keywords: List[str] = field(default_factory=list)
    allow_extra_files: bool = True
    requires_deliverable: bool = True
    notes: List[str] = field(default_factory=list)
    confidence: Confidence = "low"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_prompt_section(self) -> str:
        """Compact block injected into the codegen prompt (no ``{`` / ``}``)."""
        lines = ["DELIVERABLE CONTRACT (what the evaluator expects you to PRODUCE):"]
        if self.expected_extensions:
            lines.append(
                "- Expected file type(s): " + ", ".join(self.expected_extensions)
            )
        else:
            lines.append(
                "- Expected file type(s): a standard professional file "
                "(PDF/DOCX/XLSX/PPTX/PNG/CSV as appropriate)"
            )
        lines.append(f"- Minimum deliverable files: {self.min_count}")
        if self.required_keywords:
            lines.append(
                "- Deliverable name should reference: " + ", ".join(self.required_keywords)
            )
        lines.append(f"- Confidence in this contract: {self.confidence}")
        for n in self.notes:
            lines.append(f"- Note: {n}")
        lines.append(
            "Save real, openable file(s) of the expected type(s) to the working "
            "directory. Do NOT count reference/input files as your deliverable, and "
            "do NOT describe the file only in text. If you cannot produce the exact "
            "type, produce the closest standard professional format and say so."
        )
        return "\n".join(lines)


@dataclass
class ContractValidation:
    ok: bool = True
    blocking_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    matched_primary: List[str] = field(default_factory=list)
    generated_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def infer_deliverable_contract(
    task_text: str,
    reference_files: Optional[List[str]] = None,
    config: Optional[dict] = None,
) -> DeliverableContract:
    """Infer the deterministic deliverable contract for a task."""
    config = config or {}
    reference_files = reference_files or []
    text = task_text or ""

    detections = _detect_extensions(text)

    # A literal type token ("csv", "pdf", "xlsx", …) frequently names an *input*
    # file rather than the deliverable. When a high-confidence detection matches a
    # reference file's extension it is ambiguous, so downgrade it to "medium":
    # the type is still expected (and a mismatch still warns), but a valid output
    # of a different type is no longer hard-blocked / sent into a wasted repair.
    ref_exts = {Path(r).suffix.lower() for r in reference_files if Path(r).suffix}
    for d in detections:
        if d["confidence"] == "high" and d["ext"].lower() in ref_exts:
            d["confidence"] = "medium"
            d["note"] = d["note"] + " — also an input file type; confidence reduced"

    expected = [d["ext"] for d in detections]
    notes = [d["note"] for d in detections]

    if detections:
        confidence = "high" if any(d["confidence"] == "high" for d in detections) else "medium"
    else:
        confidence = "low"

    has_creation_verb = _has_word(text.lower(), *_CREATION_VERBS)
    requires_deliverable = bool(expected) or has_creation_verb or bool(reference_files)

    # Config overrides (execution.sandbox.contract.*).
    if "expected_extensions" in config and config["expected_extensions"]:
        expected = [e if e.startswith(".") else f".{e}" for e in config["expected_extensions"]]
        confidence = "high"
        notes.append("Expected type(s) pinned by experiment config")
    if config.get("requires_deliverable") is not None:
        requires_deliverable = bool(config["requires_deliverable"])
    min_count = int(config.get("min_count", 1))
    max_count = config.get("max_count")
    required_keywords = list(config.get("required_keywords", []) or [])
    allow_extra = bool(config.get("allow_extra_files", True))

    # Dedupe while preserving order.
    seen: Set[str] = set()
    expected = [e for e in expected if not (e in seen or seen.add(e))]

    return DeliverableContract(
        expected_extensions=expected,
        min_count=max(min_count, 1) if requires_deliverable else 0,
        max_count=max_count,
        required_keywords=required_keywords,
        allow_extra_files=allow_extra,
        requires_deliverable=requires_deliverable,
        notes=notes,
        confidence=confidence,
    )


def select_generated_artifacts(
    workdir,
    reference_files: Optional[List[str]] = None,
    before_snapshot: Optional[Set[str]] = None,
) -> List[Path]:
    """Return files in ``workdir`` that are generated deliverables.

    Reference/input files (by basename), reserved control files, bytecode, and
    anything present in ``before_snapshot`` (relative paths) are excluded.
    """
    workdir = Path(workdir)
    if not workdir.exists():
        return []
    ref_names = {Path(r).name for r in reference_files or []}
    before = before_snapshot or set()
    out: List[Path] = []
    for p in sorted(workdir.rglob("*")):
        if p.is_dir():
            continue
        if p.suffix == ".pyc" or "__pycache__" in p.parts or "skills" in p.parts:
            continue
        rel = str(p.relative_to(workdir))
        if p.name in ref_names or p.name in RESERVED_NAMES:
            continue
        if rel in before:
            continue
        out.append(p)
    return out


def snapshot_dir(workdir) -> Set[str]:
    """Relative-path snapshot of files currently in ``workdir`` (for set-diff)."""
    workdir = Path(workdir)
    if not workdir.exists():
        return set()
    return {
        str(p.relative_to(workdir))
        for p in workdir.rglob("*")
        if p.is_file()
    }


def validate_contract(
    contract: DeliverableContract,
    artifacts: List[Path],
) -> ContractValidation:
    """Check the produced artifacts against the contract."""
    arts = [Path(a) for a in artifacts]
    nonempty = [a for a in arts if a.exists() and a.stat().st_size > 0]
    blocking: List[str] = []
    warnings: List[str] = []

    if contract.requires_deliverable and len(nonempty) < max(contract.min_count, 1):
        blocking.append(
            f"Expected at least {max(contract.min_count, 1)} non-empty deliverable "
            f"file(s); found {len(nonempty)}."
        )

    matched: List[str] = []
    if contract.expected_extensions:
        want = {e.lower() for e in contract.expected_extensions}
        matched = [a.name for a in arts if a.suffix.lower() in want]
        if not matched and nonempty:
            produced = sorted({a.suffix.lower() or "(none)" for a in arts})
            msg = (
                f"Expected a {'/'.join(contract.expected_extensions)} deliverable "
                f"but produced {produced}."
            )
            (blocking if contract.confidence == "high" else warnings).append(msg)

    if (
        contract.max_count is not None
        and not contract.allow_extra_files
        and len(nonempty) > contract.max_count
    ):
        warnings.append(
            f"Produced {len(nonempty)} files; contract allows at most {contract.max_count}."
        )

    for kw in contract.required_keywords:
        if not any(kw.lower() in a.name.lower() for a in arts):
            warnings.append(f"No deliverable filename references required keyword '{kw}'.")

    return ContractValidation(
        ok=not blocking,
        blocking_errors=blocking,
        warnings=warnings,
        matched_primary=matched,
        generated_count=len(nonempty),
    )
