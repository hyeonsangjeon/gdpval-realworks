"""Deterministic deliverable selection helpers.

This module is intentionally standalone. It does not wire into the grader
pipeline yet; it only turns a task's recorded files, references, prompt, rubric,
and optional deliverable summary into an auditable selection object.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote, urlparse

from core.grader_routing import Modality, classify_criterion, is_overall_style_criterion
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
    # Source and configuration files. A task that asks for a script, a query,
    # or a specification is answered with one, and the corpus does exactly
    # that: ``.py``, ``.overpassql`` and ``.yaml`` each ship as a gold
    # deliverable on the pinned revision, and each was previously left out of
    # this set, so ``_classify_task`` found fewer than two document-like files
    # and declined the task -- 154 rubric items, 224 points, judged as nothing.
    #
    # This is a named list rather than "anything unrecognised", because
    # ``grader._list_files`` walks the whole deliverable tree with no junk
    # filter: a permissive rule would promote a stray ``.DS_Store``, ``.log``
    # or ``.pyc`` to a primary deliverable on a model run.
    ".py",
    ".overpassql",
    ".yaml",
    # ``.yml`` is not in the corpus as a file, but 2c249e0f's own rubric names
    # it beside .yaml -- "A YAML file with extension .yaml or .yml exists in
    # the deliverable root" -- so the benchmark treats the two as one format.
    ".yml",
    # ``.json`` is already read as text by ``read_deliverable``; its absence
    # here was the same inconsistency ``.ipynb`` had in the other direction.
    ".json",
    # An email saved as a message file. A task that asks for "an email to your
    # manager" is answered with one as readily as with a ``.docx`` memo, and
    # ``read_deliverable`` decodes it into headers, body and attachments. Its
    # absence here refused exp036 task 02aa1805 outright (workbook + .eml).
    # ``.msg`` is left out on purpose: it is an Outlook OLE binary nothing in
    # the grader can read, so it may only ever be a support file.
    ".eml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".csv"}
WORD_EXTENSIONS = {".doc", ".docx"}
PRESENTATION_EXTENSIONS = {".ppt", ".pptx"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
AUDIO_EXTENSIONS = set(GRADER_AUDIO_EXTENSIONS)
# Kept apart from WORD_EXTENSIONS: that set also feeds the requested-format
# patterns and the single-family checks, and an email is neither a requested
# Word file nor a member of the Word family. It only shares the Word files'
# criterion routing ("the email ...", "the memo ...").
EMAIL_EXTENSIONS = {".eml"}
# Evidence rule of an image target added because the rubric scores an image
# file as part of the deliverable (``_with_requested_images``).
REQUESTED_IMAGE_EVIDENCE_RULE = "requested_image_primary"

# Same-content renditions and the fixed order used to set copies aside. Only
# consulted where the format-variant branch would otherwise refuse a task
# (``format_variant_no_match``). Earlier entries win, by an order fixed in
# advance and never a judgement of which copy is better: the formats the
# renderer draws, then the other formats the reader opens, then the legacy
# binaries with neither, then the pages F4 makes companions, then .msg. Every
# extension seen in gold-185, exp003, exp035 and exp036 is listed here or is a
# distinct-file kind (code, archive, data, media) that is never set aside.
RENDITION_ORDER: tuple[str, ...] = (
    ".pdf",
    ".docx",
    ".xlsx",
    ".xlsm",
    ".pptx",
    ".eml",
    ".md",
    ".txt",
    ".csv",
    ".doc",
    ".xls",
    ".ppt",
    ".html",
    ".htm",
    ".msg",
)
_RENDITION_RANK = {ext: rank for rank, ext in enumerate(RENDITION_ORDER)}
# Two renditions are copies of one another only inside one family. PDF has no
# family because it is the print form of every family. A workbook and a memo
# that happen to share a name are two deliverables, not one in two formats.
_RENDITION_FAMILY = {
    ".docx": "prose",
    ".doc": "prose",
    ".eml": "prose",
    ".msg": "prose",
    ".md": "prose",
    ".html": "prose",
    ".htm": "prose",
    ".txt": "prose",
    ".xlsx": "table",
    ".xlsm": "table",
    ".xls": "table",
    ".csv": "table",
    ".pptx": "slides",
    ".ppt": "slides",
}


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

    selection = _select_deliverables(
        task_id=task_id,
        deliverable_files=deliverable_files,
        reference_file_urls=reference_file_urls,
        reference_files=reference_files,
        instruction=instruction,
        rubric_items=rubric_items,
        deliverable_summary=deliverable_summary,
        set_aside_copies=True,
    )
    return _with_requested_images(selection, _coerce_rubric_items(rubric_items or []))


def _select_deliverables(
    *,
    task_id: str,
    deliverable_files: list[str],
    reference_file_urls: list[str] | None,
    reference_files: list[str] | None,
    instruction: str,
    rubric_items: list[Any] | None,
    deliverable_summary: str,
    set_aside_copies: bool,
) -> DeliverableSelection:
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
            refused = _selection_error(
                task_id,
                task_class,
                generated,
                reference_echo,
                "no requested format among format variants",
                "format_variant_no_match",
            )
            copies = _rendition_copies(generated, required_exts) if set_aside_copies else []
            if not copies:
                return refused
            # The refusal above is about copies: one document left in two
            # renditions, and nothing that says which to grade. Setting the
            # lower-ranked copies aside and selecting again over what is left
            # answers that with the fixed RENDITION_ORDER. Whatever is left is
            # judged by the unchanged rules, and if they still cannot choose,
            # the original refusal stands.
            #
            # A rendition the task itself names is tried first: "include a
            # text file called data_flow.txt" keeps the .txt, not its .docx
            # twin. The words come from the task's own prompt and rubric, never
            # from the model's summary. The named copy stands only where the
            # unchanged rules then grade it as a primary; otherwise keeping it
            # would set its twin aside and leave that document with no primary
            # at all, so the fixed order decides as before.
            def without(set_aside: list[str]) -> DeliverableSelection | None:
                reselected = _select_deliverables(
                    task_id=task_id,
                    deliverable_files=[p for p in deliverable_files if p not in set_aside],
                    reference_file_urls=reference_file_urls,
                    reference_files=reference_files,
                    instruction=instruction,
                    rubric_items=rubric_items,
                    deliverable_summary=deliverable_summary,
                    set_aside_copies=False,
                )
                if reselected.selection_status != "ok":
                    return None
                return replace(
                    reselected,
                    support_artifacts=[
                        *reselected.support_artifacts,
                        *(p for p in set_aside if p not in reselected.support_artifacts),
                    ],
                    selection_rule=f"{reselected.selection_rule}+rendition_copies",
                )

            task_text = _norm(
                " ".join([instruction or ""] + [item.criterion for item in items])
            )
            named_copies = _rendition_copies(generated, required_exts, task_text)
            kept_by_name = [p for p in copies if p not in named_copies]
            if kept_by_name:
                named = without(named_copies)
                if named is not None and set(kept_by_name) <= set(
                    _flatten_paths(named.primary_targets)
                ):
                    return named
            fixed = without(copies)
            return fixed if fixed is not None else refused
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

    if task_class == "main_plus_companions":
        # Emitted as main_plus_support so routing treats it exactly like the
        # document-plus-images case; the rule says how it was reached.
        primary_path = _document_like(generated)[0]
        return DeliverableSelection(
            selection_status="ok",
            task_id=task_id,
            task_class="main_plus_support",
            primary_targets=[
                _target_for_path(primary_path, "lone_document_with_companions")
            ],
            support_artifacts=[p for p in generated if p != primary_path],
            reference_files_excluded=reference_echo,
            selection_rule="set_diff_then_companion_support",
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

    # A requested image (``_with_requested_images``) is shown to the manifest
    # criteria above and to the criteria the grader sends to the renderer, not
    # to every criterion. Beside a renderable document it would otherwise be an
    # unreadable sibling, and every text criterion would be sent to render it.
    if classify_criterion(criterion).modality is not Modality.VISUAL:
        documents = [
            t for t in targets if t.evidence_rule != REQUESTED_IMAGE_EVIDENCE_RULE
        ]
        if documents:
            targets = documents

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


# An extension only asks for a format when it is written on its own -- "as a
# single .pdf", "deliver one .xlsx". Written against a name it is naming a file
# instead: "pm duties final.pdf", "territory_fit_report_ref_(3).xlsx". The
# patterns below reach across the whole task with ``.*``, and _norm has already
# folded the prompt and every rubric line into one line, so without this the
# ``.pdf`` of a reference input the task was told to read against satisfies
# ``final.*\.pdf`` from a trigger word several sentences away. Requiring a space
# in front is what separates the two readings. Parenthesized Word tokens are
# handled separately below, within an explicit deliverable-format clause.
_STANDALONE = r"(?<!\S)"
# A Word extension must end the token, not start .docxm or .docx.bak.
# Sentence-ending punctuation is still allowed, including before a quote.
_WORD_TOKEN_END = r"(?![\w/\\-]|\.+[\w/\\-])"


def _required_primary_extensions(text: str) -> set[str]:
    low = _norm(text)
    exts: set[str] = set()
    strong_patterns = [
        (rf"(single|exactly one|final|primary|deliverable).*{_STANDALONE}\.pdf|single pdf|exactly one .*pdf", {".pdf"}),
        (rf"(single|exactly one|final|primary|deliverable).*{_STANDALONE}\.docx{_WORD_TOKEN_END}|single microsoft word|single word file", WORD_EXTENSIONS),
        # Do not let a distant trigger reach into a parenthesized reference
        # mention. Only this local output-format declaration admits (.docx).
        (
            r"\bdeliverable (?:is|must be) "
            r"(?:(?:provided|submitted|delivered) )?(?:(?:as|in) )?"
            r"(?:a )?(?:single )?(?:microsoft )?word "
            rf"\(\.docx\){_WORD_TOKEN_END}",
            WORD_EXTENSIONS,
        ),
        (rf"(single|exactly one|final|primary|deliverable).*{_STANDALONE}\.xlsx|single excel workbook|single workbook", SPREADSHEET_EXTENSIONS),
        (rf"(single|exactly one|final|primary|deliverable).*{_STANDALONE}\.pptx|single powerpoint|single presentation", PRESENTATION_EXTENSIONS),
        (rf"(single|all content|deliverable).*{_STANDALONE}\.zip|single \.zip|single zip", {".zip"}),
        (r"(audio file|wav file|delivered audio|deliverable audio)", AUDIO_EXTENSIONS),
        (rf"(final deliverable).*{_STANDALONE}\.mp4|final .*mp4|mp4 video|final composited video|final video", VIDEO_EXTENSIONS),
        (rf"python notebook|{_STANDALONE}\.ipynb|notebook file", {".ipynb"}),
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

    # One document plus files of kinds the selector does not grade as
    # documents -- a preview .html, a .js or .svg helper, an Outlook .msg --
    # under other names. The document-plus-images case above already settles
    # this shape by keeping the assets as support, and these companions are
    # assets of the same sort. Unless the task names the companion's format,
    # in which case it may be the very thing asked for and the selector still
    # declines rather than guess.
    if _lone_document_with_companions(generated, text):
        return "main_plus_companions"

    return "ambiguous"


def _document_like(generated: list[str]) -> list[str]:
    return [
        p
        for p in generated
        if _extension(p) in DOCUMENT_EXTENSIONS
        and _extension(p) not in IMAGE_EXTENSIONS
    ]


# How a task names a companion's format, where the bare extension is not the
# only spelling in use. Any other extension is looked for as itself.
_COMPANION_FORMAT_WORDS = {
    ".html": r"html?|web ?pages?",
    ".htm": r"html?|web ?pages?",
    ".js": r"js|javascript",
    ".msg": r"msg|outlook",
}


def _lone_document_with_companions(generated: list[str], text: str) -> bool:
    documents = _document_like(generated)
    if len(documents) != 1:
        return False
    document = documents[0]
    companions = [
        p for p in generated
        if p != document and _extension(p) not in IMAGE_EXTENSIONS
    ]
    if not companions:
        return False
    for path in companions:
        ext = _extension(path)
        if not ext or _stem_key(path) == _stem_key(document):
            return False
        words = _COMPANION_FORMAT_WORDS.get(ext, re.escape(ext.lstrip(".")))
        if re.search(rf"(?<![\w-])(?:{words})\b", text):
            return False
    return True


# How a task names a rendition's format. In a group of copies, the one member
# whose format the task names is kept ahead of RENDITION_ORDER: "include a text
# file called data_flow.txt" (2c249e0f) keeps the .txt, not a same-name .docx,
# and "Provide instructions in Markdown format" (854f3814) keeps the .md. The
# office and PDF spellings are listed so that a task naming two formats of one
# group leaves the choice to the fixed order. Several words are also plain
# English ("word", "deck", "MD" for a physician), which is why exactly one
# named member is required and two named members are never a guess.
#
# Formats the grader cannot open are left out on purpose: an Outlook ``.msg``
# (see DOCUMENT_EXTENSIONS) and the legacy binary ``.doc``, ``.xls`` and
# ``.ppt`` have no reader, so naming one is never a reason to keep it. The
# fixed order then decides, and it ranks every rendition the judge can read
# above them except a same-name ``.html``/``.htm`` page: [memo.doc, memo.txt]
# keeps the .txt, but [guide.doc, guide.html] keeps the .doc. A page kept
# beside another document becomes its companion (F4), so ranking the page
# first would leave [guide.doc, guide.html, plan.csv] with no guide at all.
_RENDITION_FORMAT_WORDS = {
    ".pdf": r"pdfs?",
    ".docx": r"docx?|word",
    ".xlsx": r"xls[xm]?|excel|workbooks?|spreadsheets?",
    ".xlsm": r"xls[xm]?|excel|workbooks?|spreadsheets?",
    ".pptx": r"pptx?|powerpoint|slides?|decks?",
    ".eml": r"eml",
    ".md": r"md|markdown",
    ".html": r"html?|web ?pages?",
    ".htm": r"html?|web ?pages?",
    ".txt": r"txt|text files?|plain[- ]text",
    ".csv": r"csvs?",
}


# A format word inside a negation names nothing: "in .xlsx or .xls format (not
# CSV/Google Sheet/PDF and not embedded)" (62f04c2f) asks for the workbook and
# not its PDF, and "do not submit a plain-text file" does not ask for the .txt.
# A negation reaches from "not", "no", "without", ... up to the word and ends at
# a clause break (. ; : ( ) or a comma), so "No more than two pages, in
# Markdown" still names Markdown. Only the 40 characters before the word count.
_NEGATION = re.compile(r"\b(?:not|no|non|without|instead of|rather than)\b[^.;:(),]*$")
_NEGATION_REACH = 40


def _rendition_named(ext: str, task_text: str) -> bool:
    words = _RENDITION_FORMAT_WORDS.get(ext)
    if not words:
        return False
    for match in re.finditer(rf"(?<![\w-])(?:{words})\b", task_text):
        before = task_text[max(0, match.start() - _NEGATION_REACH):match.start()]
        if not _NEGATION.search(before):
            return True
    return False


def _rendition_copies(
    generated: list[str], required_exts: set[str], task_text: str = ""
) -> list[str]:
    """Files that are another rendition of a file that outranks them.

    A copy shares its folder and its name (``_stem_key``) with the file kept,
    is a different RENDITION_ORDER format, and belongs to the same family.
    The file kept is the first by: a format the task requires
    (``required_exts``); then the one member whose format ``task_text`` names
    outside a negation (``_rendition_named``), when exactly one does; then
    RENDITION_ORDER.
    With no text, or none or several members named, the fixed order alone
    decides. Everything else is a distinct file and is never set aside: a file
    in another folder (``frontend/index.html`` beside ``relayer/src/index.ts``),
    source code, archives, data and media, a cross-family pair such as a
    workbook and a memo, and two files of one format.
    """
    groups: dict[tuple[str, str], list[str]] = {}
    for path in generated:
        if _extension(path) not in _RENDITION_RANK:
            continue
        key = (Path(path).parent.as_posix(), _stem_key(path))
        groups.setdefault(key, []).append(path)
    copies: set[str] = set()
    for members in groups.values():
        extensions = [_extension(p) for p in members]
        if len(members) < 2 or len(set(extensions)) != len(extensions):
            continue
        if len({_RENDITION_FAMILY[e] for e in extensions if e in _RENDITION_FAMILY}) > 1:
            continue
        named = [p for p in members if _rendition_named(_extension(p), task_text)]
        preferred = named[0] if len(named) == 1 else None
        keep = min(
            members,
            key=lambda p: (
                _extension(p) not in required_exts,
                p != preferred,
                _RENDITION_RANK[_extension(p)],
            ),
        )
        copies.update(p for p in members if p != keep)
    return [p for p in generated if p in copies]


# A rubric line that scores an image file as part of the deliverable itself:
# "Deliverable includes at least one chart image saved as a JPG (.jpg or
# .jpeg)" (3baa0009), "Deliverable moodboard is in PNG file format."
# (b1a79ce1). Anchored on the deliverable as the subject, so an image to be
# placed inside a document ("The PDF contains ... as a .png image format",
# 99ac6944) or an input named by its file name ("what are these.jpg",
# f2986c1f) does not match. The prompt alone is not enough: where no scored
# line depends on the image, showing it to the judge changes nothing but cost.
_REQUESTED_IMAGE_CRITERION_PATTERN = re.compile(
    r"^(?:the\s+)?(?:deliverable|submission)s?\b[^.]*?\b(?:saved as|in|as)\s+"
    r"(?:an?\s+)?\.?(?P<fmt>jpe?g|png)\b"
)
_IMAGE_FORMAT_EXTENSIONS = {
    "jpg": {".jpg", ".jpeg"},
    "jpeg": {".jpg", ".jpeg"},
    "png": {".png"},
}


def _requested_image_extensions(items: list[_RubricItemText]) -> set[str]:
    found: set[str] = set()
    for item in items:
        match = _REQUESTED_IMAGE_CRITERION_PATTERN.search(_norm(item.criterion))
        if match:
            found.update(_IMAGE_FORMAT_EXTENSIONS[match.group("fmt")])
    return found


def _with_requested_images(
    selection: DeliverableSelection,
    items: list[_RubricItemText],
) -> DeliverableSelection:
    """Grade a requested image file beside the document, never instead of it.

    "Accompany the article with a JPG chart" asks for two files. Images are
    otherwise always support, and support never reaches a render, so every
    criterion about the chart was excluded as having nothing to look at. Only
    images in the requested format are added, only to a selection that already
    has its document, and only after the existing targets. Which criteria get
    to see them is decided in ``plan_targets_for_criterion``.
    """
    if selection.selection_status != "ok" or not selection.primary_targets:
        return selection
    wanted = _requested_image_extensions(items)
    images = [p for p in selection.support_artifacts if _extension(p) in wanted]
    if not images:
        return selection
    taken = {target.target_id for target in selection.primary_targets}
    added: list[SelectionTarget] = []
    for path in images:
        target_id = _target_id(path)
        if target_id in taken:
            target_id = f"{target_id}_{_kind(path)}"
        taken.add(target_id)
        added.append(
            _target_for_path(path, REQUESTED_IMAGE_EVIDENCE_RULE, target_id=target_id)
        )
    return replace(
        selection,
        primary_targets=[*selection.primary_targets, *added],
        support_artifacts=[p for p in selection.support_artifacts if p not in images],
        selection_rule=f"{selection.selection_rule}+requested_image",
    )


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
        elif ext in EMAIL_EXTENSIONS and re.search(r"\b(email|e-mail|memo|letter)\b", criterion):
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
