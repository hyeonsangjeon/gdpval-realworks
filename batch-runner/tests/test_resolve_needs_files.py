"""Tests for core.needs_files.resolve_needs_files.

Truth-table coverage: 4 policies × 4 input combinations = 16 cases,
plus extra coverage for the ``inferred`` confidence class (which exercises
``union`` / ``intersection`` independently of ``explicit_boost``).
"""

import pytest

from core.config import NEEDS_FILES_POLICIES_KNOWN
from core.needs_files import resolve_needs_files
from core.prompt_classifier import PromptClassification


def _make_explicit() -> PromptClassification:
    return PromptClassification(
        requires_file=True,
        explicit_exts=[".docx"],
        inferred_exts=[],
        confidence="explicit",
    )


def _make_inferred() -> PromptClassification:
    return PromptClassification(
        requires_file=True,
        explicit_exts=[],
        inferred_exts=[".docx"],
        confidence="inferred",
    )


def _make_text_only() -> PromptClassification:
    return PromptClassification(
        requires_file=False,
        explicit_exts=[],
        inferred_exts=[],
        confidence="text_only",
    )


# ── Truth table: 4 inputs × 4 policies = 16 cases ─────────────────────────
# Axes: has_deliverable ∈ {T, F}; classification ∈ {explicit, text_only}
# Together these capture the boolean projections of the four resolvers.

_TRUTH_TABLE = [
    # (has_deliverable, classifier_factory, policy, expected)
    # A: deliverable=T, classification=explicit
    (True, _make_explicit, "deliverable_only", True),
    (True, _make_explicit, "explicit_boost", True),
    (True, _make_explicit, "union", True),
    (True, _make_explicit, "intersection", True),
    # B: deliverable=T, classification=text_only
    (True, _make_text_only, "deliverable_only", True),
    (True, _make_text_only, "explicit_boost", True),
    (True, _make_text_only, "union", True),
    (True, _make_text_only, "intersection", False),
    # C: deliverable=F, classification=explicit
    (False, _make_explicit, "deliverable_only", False),
    (False, _make_explicit, "explicit_boost", True),
    (False, _make_explicit, "union", True),
    (False, _make_explicit, "intersection", False),
    # D: deliverable=F, classification=text_only
    (False, _make_text_only, "deliverable_only", False),
    (False, _make_text_only, "explicit_boost", False),
    (False, _make_text_only, "union", False),
    (False, _make_text_only, "intersection", False),
]


@pytest.mark.parametrize(
    "has_deliverable,classifier_factory,policy,expected",
    _TRUTH_TABLE,
)
def test_resolve_needs_files_truth_table(
    has_deliverable, classifier_factory, policy, expected
):
    result = resolve_needs_files(has_deliverable, classifier_factory(), policy)
    assert result is expected, (
        f"resolve_needs_files(has_deliverable={has_deliverable}, "
        f"confidence={classifier_factory().confidence}, policy={policy}) "
        f"-> {result}, expected {expected}"
    )


# ── Inferred-class coverage (explicit_boost must remain False) ────────────


@pytest.mark.parametrize(
    "policy,expected",
    [
        ("deliverable_only", False),
        ("explicit_boost", False),   # no explicit_exts, just inferred
        ("union", True),             # requires_file=True via inferred
        ("intersection", False),     # has_deliverable=False
    ],
)
def test_resolve_inferred_no_deliverable(policy, expected):
    classification = _make_inferred()
    assert (
        resolve_needs_files(False, classification, policy) is expected
    )


@pytest.mark.parametrize(
    "policy,expected",
    [
        ("deliverable_only", True),
        ("explicit_boost", True),
        ("union", True),
        ("intersection", True),
    ],
)
def test_resolve_inferred_with_deliverable(policy, expected):
    classification = _make_inferred()
    assert (
        resolve_needs_files(True, classification, policy) is expected
    )


# ── Policy validation ──────────────────────────────────────────────────────


def test_resolve_unknown_policy_raises():
    with pytest.raises(ValueError):
        resolve_needs_files(True, _make_text_only(), "majority_vote")


def test_known_policies_set_matches_config():
    expected = {"deliverable_only", "explicit_boost", "union", "intersection"}
    assert set(NEEDS_FILES_POLICIES_KNOWN) == expected
