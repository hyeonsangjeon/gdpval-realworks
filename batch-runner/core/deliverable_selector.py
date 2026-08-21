"""Deterministic deliverable selection helpers.

This module is intentionally standalone. It does not wire into the grader
pipeline yet; it only turns a task's recorded files, references, prompt, rubric,
and optional deliverable summary into an auditable selection object.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote, urlparse

from core.grader_routing import is_overall_style_criterion
from core.media_types import GRADER_AUDIO_EXTENSIONS


DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".xlsm",
    ".ppt",
    ".pptx",
    ".zip",
    *GRADER_AUDIO_EXTENSIONS,
    ".mp4",
    ".mov",
    ".ipynb",
    ".txt",
    ".md",
    ".csv",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".csv"}
WORD_EXTENSIONS = {".doc", ".docx"}
PRESENTATION_EXTENSIONS = {".ppt", ".pptx"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
AUDIO_EXTENSIONS = set(GRADER_AUDIO_EXTENSIONS)


ITEM_TARGET_AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "rubric_item_id",
        "target_scope",
        "target_ids",
        "child_grades",
        "aggregation_rule",
        "selected_paths",
        "support_paths_visible",
    ],
    "properties": {
        "rubric_item_id": {"type": "string"},
        "target_scope": {
            "type": "string",
            "enum": [
                "manifest",
                "file_target",
                "primary_bundle",
                "split_children",
                "selection_error",
            ],
        },
        "target_ids": {"type": "array", "items": {"type": "string"}},
        "child_grades": {"type": "array", "items": {"type": "object"}},
        "aggregation_rule": {
            "type": ["string", "null"],
            "enum": ["blocking_min_else_mean", None],
        },
        "selected_paths": {"type": "array", "items": {"type": "string"}},
        "support_paths_visible": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass(frozen=True)
class SelectionTarget:
    target_id: str
    paths: list[str]
    kind: str
    role: str = "primary"
    evidence_rule: str = "set_diff"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeliverableSelection:
    selection_status: str
    task_id: str
    task_class: str
    primary_targets: list[SelectionTarget] = field(default_factory=list)
    support_artifacts: list[str] = field(default_factory=list)
    reference_files_excluded: list[str] = field(default_factory=list)
    selection_rule: str = ""
    selection_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["primary_targets"] = [t.to_dict() for t in self.primary_targets]
        return data


@dataclass(frozen=True)
class CriterionTargetPlan:
    target_scope: str
    target_ids: list[str]
    selected_paths: list[str]
    support_paths_visible: list[str] = field(default_factory=list)
    aggregation_rule: str | None = None

    def to_audit_dict(self, rubric_item_id: str) -> dict[str, Any]:
        return {
            "rubric_item_id": rubric_item_id,
            "target_scope": self.target_scope,
            "target_ids": list(self.target_ids),
            "child_grades": [],
            "aggregation_rule": self.aggregation_rule,
            "selected_paths": list(self.selected_paths),
            "support_paths_visible": list(self.support_paths_visible),
        }


@dataclass(frozen=True)
class _RubricItemText:
    criterion: str
    score: float = 0.0


def select_deliverables(
    *,
    task_id: str,
    deliverable_files: list[str],
    reference_file_urls: list[str] | None = None,
    reference_files: list[str] | None = None,
    instruction: str = "",
    rubric_items: list[Any] | None = None,
    deliverable_summary: str = "",
) -> DeliverableSelection:
    """Return a deterministic, auditable deliverable selection.

    The function performs no model calls and does not assess quality. The
    deliverable summary is only used as a tie-break when the named file exists
    in the generated-candidate set and matches the expected kind.
    """

    references = _reference_basenames(reference_files or [], reference_file_urls or [])
    reference_echo: list[str] = []
    generated: list[str] = []
    for path in deliverable_files or []:
        if _norm(_basename(path)) in references:
            reference_echo.append(path)
        else:
            generated.append(path)

    if not generated:
        return DeliverableSelection(
            selection_status="no_generated_candidate",
            task_id=task_id,
            task_class="ambiguous",
            reference_files_excluded=reference_echo,
            selection_rule="set_diff_zero_guard",
            selection_error="no generated deliverable after reference set-diff",
        )

    items = _coerce_rubric_items(rubric_items or [])
    all_text = " ".join(
        [instruction or "", deliverable_summary or ""]
        + [item.criterion for item in items]
    )
    required_exts = _required_primary_extensions(all_text)
    matched_required = _filter_by_extensions(generated, required_exts)
    if required_exts and not matched_required:
        return DeliverableSelection(
            selection_status="wrong_format_primary",
            task_id=task_id,
            task_class="ambiguous",
            support_artifacts=list(generated),
            reference_files_excluded=reference_echo,
            selection_rule="set_diff_then_wrong_format_guard",
            selection_error=(
                "generated files exist but none match requested primary formats: "
                + ", ".join(sorted(required_exts))
            ),
        )

    if len(generated) == 1:
        return DeliverableSelection(
            selection_status="ok",
            task_id=task_id,
            task_class="single_primary",
            primary_targets=[
                _target_for_path(generated[0], "set_diff_single", target_id=None)
            ],
            reference_files_excluded=reference_echo,
            selection_rule="set_diff_single",
        )

    task_class = _classify_task(generated, items, instruction, required_exts)
    if task_class == "format_variants":
        primary_paths = _choose_format_variant(generated, required_exts, deliverable_summary)
        if not primary_paths:
            return _selection_error(
                task_id,
                task_class,
                generated,
                reference_echo,
                "no requested format among format variants",
                "format_variant_no_match",
            )
        support = [p for p in generated if p not in primary_paths]
        return DeliverableSelection(
            selection_status="ok",
            task_id=task_id,
            task_class=task_class,
            primary_targets=[
                _target_for_path(primary_paths[0], "format_variant_required_format")
            ],
            support_artifacts=support,
            reference_files_excluded=reference_echo,
            selection_rule="set_diff_then_format_variant",
        )

    if task_class == "main_plus_support":
        primary_paths = _choose_main_primary(generated, required_exts, items, deliverable_summary)
        if not primary_paths:
            return _selection_error(
                task_id,
                task_class,
                generated,
                reference_echo,
                "could not identify primary deliverable among support artifacts",
                "main_plus_support_no_primary",
            )
        support = [p for p in generated if p not in primary_paths]
        return DeliverableSelection(
            selection_status="ok",
            task_id=task_id,
            task_class=task_class,
            primary_targets=[
                _target_for_path(primary_paths[0], "primary_kind_or_summary")
            ],
            support_artifacts=support,
            reference_files_excluded=reference_echo,
            selection_rule="set_diff_then_primary_support_split",
        )

    if task_class in ("separate_equivalent", "uniform_primaries"):
        primary_paths = _choose_separate_primaries(generated, items, required_exts)
        if not primary_paths:
            return _selection_error(
                task_id,
                task_class,
                generated,
                reference_echo,
                "could not identify separate primary deliverables",
                "separate_equivalent_no_primary",
            )
        support = [p for p in generated if p not in primary_paths]
        # The emitted task_class is the same either way, because downstream
        # routing should not care how the classification was reached. The rule
        # is not: "separate_primaries" means the instruction said so, and
        # "uniform_primaries" means it did not and the selector inferred it
        # from several same-format outputs. That is a weaker inference and an
        # audit should be able to see which tasks rest on it.
        rule = (
            "set_diff_then_separate_primaries"
            if task_class == "separate_equivalent"
            else "set_diff_then_uniform_primaries"
        )
        return DeliverableSelection(
            selection_status="ok",
            task_id=task_id,
            task_class="separate_equivalent",
            primary_targets=[
                _target_for_path(path, "separate_primary", target_id=None)
                for path in primary_paths
            ],
            support_artifacts=support,
            reference_files_excluded=reference_echo,
            selection_rule=rule,
        )

    return _selection_error(
        task_id,
        "ambiguous",
        generated,
        reference_echo,
        "generated candidates exist but selector could not choose deterministically",
        "ambiguous_candidates",
    )


def plan_targets_for_criterion(
    selection: DeliverableSelection,
    criterion: str,
) -> CriterionTargetPlan:
    """Return target routing metadata for a rubric criterion.

    This helper does not score anything. It only describes which selected
    target(s) a later grader should inspect and how split children aggregate.
    """

    if selection.selection_status != "ok":
        return CriterionTargetPlan(
            target_scope="selection_error",
            target_ids=[],
            selected_paths=[],
            aggregation_rule=None,
        )

    criterion_norm = _norm(criterion)
    targets = selection.primary_targets
    if _is_manifest_criterion(criterion_norm):
        return CriterionTargetPlan(
            target_scope="manifest",
            target_ids=[t.target_id for t in targets],
            selected_paths=_flatten_paths(targets),
            support_paths_visible=list(selection.support_artifacts),
        )

    if _is_cross_file_criterion(criterion_norm) and len(targets) > 1:
        return CriterionTargetPlan(
            target_scope="primary_bundle",
            target_ids=[t.target_id for t in targets],
            selected_paths=_flatten_paths(targets),
        )

    if is_overall_style_criterion(criterion_norm):
        if selection.task_class == "separate_equivalent" and len(targets) > 1:
            return CriterionTargetPlan(
                target_scope="split_children",
                target_ids=[t.target_id for t in targets],
                selected_paths=_flatten_paths(targets),
                aggregation_rule="blocking_min_else_mean",
            )
        primary = targets[0]
        return CriterionTargetPlan(
            target_scope="file_target",
            target_ids=[primary.target_id],
            selected_paths=list(primary.paths),
        )

    target = _match_file_specific_target(criterion_norm, targets)
    if target is not None:
        return CriterionTargetPlan(
            target_scope="file_target",
            target_ids=[target.target_id],
            selected_paths=list(target.paths),
        )

    if len(targets) > 1:
        return CriterionTargetPlan(
            target_scope="primary_bundle",
            target_ids=[t.target_id for t in targets],
            selected_paths=_flatten_paths(targets),
        )

    return CriterionTargetPlan(
        target_scope="file_target",
        target_ids=[targets[0].target_id],
        selected_paths=list(targets[0].paths),
    )


def _selection_error(
    task_id: str,
    task_class: str,
    generated: list[str],
    reference_echo: list[str],
    message: str,
    rule: str,
) -> DeliverableSelection:
    return DeliverableSelection(
        selection_status="selection_error",
        task_id=task_id,
        task_class=task_class,
        support_artifacts=list(generated),
        reference_files_excluded=reference_echo,
        selection_rule=rule,
        selection_error=message,
    )


def _coerce_rubric_items(items: list[Any]) -> list[_RubricItemText]:
    coerced: list[_RubricItemText] = []
    for item in items:
        if isinstance(item, dict):
            coerced.append(
                _RubricItemText(
                    criterion=str(item.get("criterion") or ""),
                    score=float(item.get("score") or item.get("max_score") or 0),
                )
            )
        else:
            coerced.append(
                _RubricItemText(
                    criterion=str(getattr(item, "criterion", "") or ""),
                    score=float(getattr(item, "score", 0) or 0),
                )
            )
    return coerced


def _reference_basenames(reference_files: list[str], reference_file_urls: list[str]) -> set[str]:
    names: set[str] = set()
    for path in reference_files:
        names.add(_norm(_basename(unquote(str(path)))))
    for url in reference_file_urls:
        parsed = urlparse(str(url))
        names.add(_norm(_basename(unquote(parsed.path))))
    return names


def _required_primary_extensions(text: str) -> set[str]:
    low = _norm(text)
    exts: set[str] = set()
    strong_patterns = [
        (r"(single|exactly one|final|primary|deliverable).*\.pdf|single pdf|exactly one .*pdf", {".pdf"}),
        (r"(single|exactly one|final|primary|deliverable).*\.docx|single microsoft word|single word file", WORD_EXTENSIONS),
        (r"(single|exactly one|final|primary|deliverable).*\.xlsx|single excel workbook|single workbook", SPREADSHEET_EXTENSIONS),
        (r"(single|exactly one|final|primary|deliverable).*\.pptx|single powerpoint|single presentation", PRESENTATION_EXTENSIONS),
        (r"(single|all content|deliverable).*\.zip|single \.zip|single zip", {".zip"}),
        (r"(audio file|wav file|delivered audio|deliverable audio)", AUDIO_EXTENSIONS),
        (r"(final deliverable).*\.mp4|final .*mp4|mp4 video|final composited video|final video", VIDEO_EXTENSIONS),
        (r"python notebook|\.ipynb|notebook file", {".ipynb"}),
    ]
    for pattern, matched in strong_patterns:
        if re.search(pattern, low):
            exts.update(matched)
    return exts


def _classify_task(
    generated: list[str],
    items: list[_RubricItemText],
    instruction: str,
    required_exts: set[str],
) -> str:
    text = _norm(" ".join([instruction] + [item.criterion for item in items]))

    if _looks_like_format_variant(generated):
        return "format_variants"

    non_image_docs = [p for p in generated if _extension(p) not in IMAGE_EXTENSIONS]
    images = [p for p in generated if _extension(p) in IMAGE_EXTENSIONS]

    if _has_single_primary_with_support(generated, text, required_exts):
        return "main_plus_support"

    if _has_separate_deliverable_language(text):
        return "separate_equivalent"

    if (
        len(non_image_docs) >= 2
        and _multiple_file_types_requested(text)
        and not _has_single_primary_language(text)
    ):
        return "separate_equivalent"

    if required_exts and len(_filter_by_extensions(generated, required_exts)) == 1:
        return "main_plus_support"

    if len(non_image_docs) == 1 and images:
        return "main_plus_support"

    doc_ext_groups = {
        _extension(p)
        for p in non_image_docs
        if _extension(p) in DOCUMENT_EXTENSIONS
    }
    if len(non_image_docs) >= 2 and len(doc_ext_groups) >= 1:
        if _multiple_file_types_requested(text) or len(doc_ext_groups) > 1:
            return "separate_equivalent"

    # Everything above needs positive evidence -- "two separate files", two
    # requested formats, a single named primary. What is left is the case with
    # no such evidence: several document-like outputs sharing one format, and
    # an instruction that never says how many files it wants. Five school
    # reports. A plan and a deck. A guide, an application, a template.
    #
    # Declining to choose used to be the answer here, and it is the wrong one,
    # because declining is not neutral: every rubric item on the task becomes a
    # judge error and the task scores zero even though the model delivered. On
    # the sol-220 run that was 243 of 333 judge errors from 5 tasks -- more
    # than every other cause combined.
    #
    # Treating them as equal primaries is safe in a way choosing one is not.
    # No file is demoted, and nothing downstream has to be told which one
    # mattered: a criterion whose text matches a filename routes to that file,
    # and every other criterion routes to the bundle, where the judge sees all
    # of them and resolves "the fax cover sheet ..." from the criterion itself.
    # Most land in the bundle, which is the case this relies on. So the
    # selector no longer has to answer a question it cannot answer -- which of
    # these is THE deliverable -- to let grading proceed.
    if len(_document_like(generated)) >= 2:
        return "uniform_primaries"

    return "ambiguous"


def _document_like(generated: list[str]) -> list[str]:
    return [
        p
        for p in generated
        if _extension(p) in DOCUMENT_EXTENSIONS
        and _extension(p) not in IMAGE_EXTENSIONS
    ]


def _has_single_primary_with_support(
    generated: list[str],
    text: str,
    required_exts: set[str],
) -> bool:
    if not required_exts or not _is_single_extension_family(required_exts):
        return False

    primary_matches = _filter_by_extensions(generated, required_exts)
    if len(primary_matches) != 1:
        return False

    single_primary_signal = (
        _has_single_primary_language(text) or _is_single_extension_family(required_exts)
    )
    if not single_primary_signal:
        return False

    primary = primary_matches[0]
    support = [p for p in generated if p != primary]
    return bool(support)


def _is_single_extension_family(required_exts: set[str]) -> bool:
    families = [
        {".pdf"},
        WORD_EXTENSIONS,
        SPREADSHEET_EXTENSIONS,
        PRESENTATION_EXTENSIONS,
        {".zip"},
        AUDIO_EXTENSIONS,
        VIDEO_EXTENSIONS,
        {".ipynb"},
    ]
    return any(required_exts <= family for family in families)


def _has_separate_deliverable_language(text: str) -> bool:
    # The noun list is intentionally deliverable/file-shaped. Content nouns
    # like mixes, channels, outputs, tracks, tabs, slides, and sections are not
    # multi-deliverable evidence on their own. Keep the numeric phrase in one
    # sentence so "two inputs. The document ..." cannot become two documents.
    noun = (
        r"(?:deliverables?|files?|documents?|pdfs?|\.pdf|docx|\.docx|"
        r"workbooks?|spreadsheets?|decks?|presentations?|pptx|\.pptx|"
        r"forms?|reports?|letters?|emails?|memos?|guides?|checklists?|sheets?)"
    )
    phrase = r"(?:[a-z0-9_/\-]+\s+){0,4}"
    patterns = [
        rf"(?:two|three|exactly two|exactly three)\s+"
        rf"(?:separate\s+|distinct\s+)?{phrase}{noun}\b",
        rf"provides?\s+(?:two|three)\s+"
        rf"(?:separate\s+|distinct\s+)?{phrase}{noun}\b",
        r"both deliverable files",
        rf"one\s+{noun}\b[^.]*\band\s+one\s+{noun}\b",
        r"standalone [^.]{0,80} file",
        r"separate file",
        r"each [^.]{0,80} as a standalone",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _multiple_file_types_requested(text: str) -> bool:
    types = 0
    for pattern in [
        r"\.pdf|pdf file|pdf document",
        r"\.docx|word document|word file",
        r"\.xlsx|excel workbook|spreadsheet",
        r"\.pptx|powerpoint|presentation",
        r"\.zip|zip archive",
    ]:
        if re.search(pattern, text):
            types += 1
    return types >= 2


def _has_single_primary_language(text: str) -> bool:
    return bool(
        re.search(
            r"\b(single|exactly one|one attached file|all content .* single|final deliverable consists of a single)\b",
            text,
        )
    )


def _looks_like_format_variant(paths: list[str]) -> bool:
    if len(paths) < 2:
        return False
    stems: dict[str, set[str]] = {}
    for path in paths:
        ext = _extension(path)
        if ext in IMAGE_EXTENSIONS:
            continue
        stems.setdefault(_stem_key(path), set()).add(ext)
    return any(len(exts) >= 2 for exts in stems.values())


def _choose_format_variant(
    generated: list[str],
    required_exts: set[str],
    deliverable_summary: str,
) -> list[str]:
    candidates = _filter_by_extensions(generated, required_exts)
    if len(candidates) == 1:
        return candidates
    if len(candidates) > 1:
        named = _summary_named_candidates(candidates, deliverable_summary, required_exts)
        if len(named) == 1:
            return named
        pdfs = _filter_by_extensions(candidates, {".pdf"})
        if len(pdfs) == 1:
            return pdfs
    pdfs = _filter_by_extensions(generated, {".pdf"})
    if len(pdfs) == 1:
        return pdfs
    return []


def _choose_main_primary(
    generated: list[str],
    required_exts: set[str],
    items: list[_RubricItemText],
    deliverable_summary: str,
) -> list[str]:
    required = _filter_by_extensions(generated, required_exts)
    if len(required) == 1:
        return required
    if len(required) > 1:
        named = _summary_named_candidates(required, deliverable_summary, required_exts)
        if len(named) == 1:
            return named

    text = _norm(" ".join(item.criterion for item in items))
    for exts in ({".pdf"}, SPREADSHEET_EXTENSIONS, WORD_EXTENSIONS, PRESENTATION_EXTENSIONS, {".zip"}):
        matches = _filter_by_extensions(generated, exts)
        if len(matches) == 1 and _extension_family_name(next(iter(exts))) in text:
            return matches

    non_images = [p for p in generated if _extension(p) not in IMAGE_EXTENSIONS]
    if len(non_images) == 1:
        return non_images
    return []


def _choose_separate_primaries(
    generated: list[str],
    items: list[_RubricItemText],
    required_exts: set[str],
) -> list[str]:
    text = _norm(" ".join(item.criterion for item in items))
    primaries = [
        p
        for p in generated
        if _extension(p) in DOCUMENT_EXTENSIONS
        and not (_extension(p) in IMAGE_EXTENSIONS)
    ]
    if not primaries:
        return []

    # If a criterion explicitly asks for a single primary format plus support,
    # keep the separate path from over-selecting. Otherwise, split all primary
    # document-like outputs and leave images/assets as support.
    if required_exts and _has_single_primary_language(text):
        required = _filter_by_extensions(primaries, required_exts)
        if required:
            return required
    return primaries


def _summary_named_candidates(
    candidates: list[str],
    deliverable_summary: str,
    expected_exts: set[str] | None = None,
) -> list[str]:
    if not deliverable_summary:
        return []
    summary = _norm(deliverable_summary)
    hits: list[str] = []
    for path in candidates:
        if expected_exts and _extension(path) not in expected_exts:
            continue
        basename = _basename(path)
        if _norm(basename) in summary or _norm(Path(basename).stem) in summary:
            hits.append(path)
    return hits


def _target_for_path(path: str, evidence_rule: str, target_id: str | None = None) -> SelectionTarget:
    return SelectionTarget(
        target_id=target_id or _target_id(path),
        paths=[path],
        kind=_kind(path),
        role="primary",
        evidence_rule=evidence_rule,
    )


def _filter_by_extensions(paths: list[str], extensions: set[str]) -> list[str]:
    if not extensions:
        return []
    return [p for p in paths if _extension(p) in extensions]


def _extension_family_name(ext: str) -> str:
    if ext in SPREADSHEET_EXTENSIONS:
        return "excel"
    if ext in WORD_EXTENSIONS:
        return "word"
    if ext in PRESENTATION_EXTENSIONS:
        return "powerpoint"
    return ext.lstrip(".")


def _is_manifest_criterion(criterion: str) -> bool:
    return bool(
        re.search(
            r"\b(exactly|single|separate|submits?|submission|delivers?|provides?|file is|format|extension|opens? without|password-protected)\b",
            criterion,
        )
    )


def _is_cross_file_criterion(criterion: str) -> bool:
    return bool(
        re.search(
            r"\b(both|across|corresponding|also appears|matches?|consistent with|same id|same data|spreadsheet.*layout|workbook.*pdf|pdf.*workbook)\b",
            criterion,
        )
    )


def _match_file_specific_target(
    criterion: str,
    targets: list[SelectionTarget],
) -> SelectionTarget | None:
    if not targets:
        return None
    direct_hits: list[SelectionTarget] = []
    for target in targets:
        haystacks = [target.target_id, _norm(_basename(target.paths[0])), _norm(Path(target.paths[0]).stem)]
        if any(h and h in criterion for h in haystacks):
            direct_hits.append(target)
    if len(direct_hits) == 1:
        return direct_hits[0]

    extension_matches = []
    for target in targets:
        ext = _extension(target.paths[0])
        if ext in SPREADSHEET_EXTENSIONS and re.search(r"\b(workbook|spreadsheet|excel|worksheet|sheet|tab)\b", criterion):
            extension_matches.append(target)
        elif ext in WORD_EXTENSIONS and re.search(r"\b(word|docx|document|email|memo|letter|form|template|sop)\b", criterion):
            extension_matches.append(target)
        elif ext in PRESENTATION_EXTENSIONS and re.search(r"\b(presentation|deck|pptx|slide|powerpoint|session)\b", criterion):
            extension_matches.append(target)
        elif ext == ".pdf" and re.search(r"\b(pdf|report|guide|checklist|map)\b", criterion):
            extension_matches.append(target)
        elif ext == ".zip" and re.search(r"\b(zip|archive)\b", criterion):
            extension_matches.append(target)
    if len(extension_matches) == 1:
        return extension_matches[0]

    # Session-style decks often differ only by a number in the filename.
    number_match = re.search(r"\bsession\s*(\d+)\b", criterion)
    if number_match:
        needle = f"session_{number_match.group(1)}"
        for target in targets:
            if needle in target.target_id:
                return target
    return None


def _flatten_paths(targets: list[SelectionTarget]) -> list[str]:
    out: list[str] = []
    for target in targets:
        out.extend(target.paths)
    return out


def _kind(path: str) -> str:
    return _extension(path).lstrip(".") or "unknown"


def _target_id(path: str) -> str:
    stem = _norm(Path(path).stem)
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return stem or "deliverable"


def _stem_key(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(Path(path).stem))


def _extension(path: str) -> str:
    return Path(path).suffix.lower()


def _basename(path: str) -> str:
    return Path(str(path)).name


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold()
