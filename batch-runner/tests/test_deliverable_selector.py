"""Unit tests for the standalone deliverable selector.

No Azure calls, grading, rendering, pandas, parquet, or network access. The
checked-in contract fixture contains only synthetic selector signals and exact
public task/source identities; file lists and owner expected targets remain in
this test module.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_deliverable_selector_fixture import (  # noqa: E402
    canonical_json,
    load_and_validate_fixture,
)

from core.deliverable_selector import (  # noqa: E402
    ITEM_TARGET_AUDIT_SCHEMA,
    DeliverableSelection,
    plan_targets_for_criterion,
    select_deliverables,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "deliverable_selector_contract_v1.json"
)


def _path(task: str, name: str) -> str:
    return f"deliverable_files/{task}/{name}"


def _ref_url(name: str) -> str:
    encoded = name.replace(" ", "%20")
    return f"https://huggingface.co/datasets/openai/gdpval/resolve/main/reference_files/hash/{encoded}"


def _load_task_data() -> dict[str, dict[str, Any]]:
    return load_and_validate_fixture(FIXTURE_PATH)["tasks"]


CONTRACT_TASK_DATA = _load_task_data()


def _selected_names(selection: DeliverableSelection) -> set[str]:
    names: set[str] = set()
    for target in selection.primary_targets:
        for path in target.paths:
            names.add(path.rsplit("/", 1)[-1])
    return names


def _actual_criterion(task_id: str, contains: str) -> str:
    for item in CONTRACT_TASK_DATA[task_id]["rubric_items"]:
        criterion = item["criterion"]
        if contains in criterion:
            return criterion
    raise AssertionError(f"criterion containing {contains!r} not found for {task_id}")


def _select(fixture: dict[str, Any]) -> DeliverableSelection:
    task = CONTRACT_TASK_DATA[fixture["task_id"]]
    return select_deliverables(
        task_id=fixture["task_id"],
        deliverable_files=fixture["deliverable_files"],
        reference_file_urls=fixture.get("reference_file_urls", []),
        instruction=task["instruction"],
        rubric_items=task["rubric_items"],
        deliverable_summary=fixture.get("deliverable_summary", ""),
    )


GOLD_FIXTURES = [
    {
        "task_id": "83d10b06",
        "deliverable_files": [
            _path("83d10b06", "Population v2.xlsx"),
            _path("83d10b06", "Sample.xlsx"),
        ],
        "reference_file_urls": [_ref_url("Population v2.xlsx")],
        "expected": {"Sample.xlsx"},
    },
    {
        "task_id": "7b08cd4d",
        "deliverable_files": [
            _path("7b08cd4d", "Fall Music Tour Ref File.xlsx"),
            _path("7b08cd4d", "2024_Fall_Music_Tour_PnL_As_of_2024-12-31.xlsx"),
        ],
        "reference_file_urls": [_ref_url("Fall Music Tour Ref File.xlsx")],
        "expected": {"2024_Fall_Music_Tour_PnL_As_of_2024-12-31.xlsx"},
    },
    {
        "task_id": "7d7fc9a7",
        "deliverable_files": [
            _path("7d7fc9a7", "Aurisic_Prepaid_Insurance.pdf"),
            _path("7d7fc9a7", "COA.xlsx"),
            _path("7d7fc9a7", "Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx"),
        ],
        "reference_file_urls": [
            _ref_url("Aurisic_Prepaid_Insurance.pdf"),
            _ref_url("COA.xlsx"),
        ],
        "expected": {"Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx"},
    },
    {
        "task_id": "43dc9778",
        "deliverable_files": [
            _path("43dc9778", "LISA W2 COMPRESS MIDDLE SCHOOL edit.pdf"),
            _path("43dc9778", "2024 Childcare Statement.pdf"),
            _path("43dc9778", "Smith_2024_Form_1040_Draft.pdf"),
        ],
        "reference_file_urls": [
            _ref_url("LISA W2 COMPRESS MIDDLE SCHOOL edit.pdf"),
            _ref_url("2024 Childcare Statement.pdf"),
        ],
        "expected": {"Smith_2024_Form_1040_Draft.pdf"},
    },
    {
        "task_id": "ee09d943",
        "deliverable_files": [
            _path("ee09d943", "Prof_Fee_Dump-1.xlsx"),
            _path("ee09d943", "AR_Accrual-1.xlsx"),
            _path("ee09d943", "Aurisic_Financials_4-25-1.xlsx"),
        ],
        "reference_file_urls": [
            _ref_url("Prof_Fee_Dump-1.xlsx"),
            _ref_url("AR_Accrual-1.xlsx"),
        ],
        "expected": {"Aurisic_Financials_4-25-1.xlsx"},
    },
    {
        "task_id": "27e8912c",
        "deliverable_files": [
            _path("27e8912c", "Organizational_Ergonomic_Action_Items.docx"),
            _path("27e8912c", "Workstation_Ergonomics_Checklist.pdf"),
            _path("27e8912c", "chair_setup.png"),
        ],
        "expected": {
            "Organizational_Ergonomic_Action_Items.docx",
            "Workstation_Ergonomics_Checklist.pdf",
        },
        "expected_class": "separate_equivalent",
    },
    {
        "task_id": "99ac6944",
        "deliverable_files": [
            _path("99ac6944", "IEM_Budget_Breakdown.png"),
            _path("99ac6944", "IEM_Budget_Breakdown.xlsx"),
            _path("99ac6944", "IEM_Signal_Flow.png"),
            _path("99ac6944", "West_Coast_Tour_IEM_Mobile_Setup.pdf"),
        ],
        "expected": {"West_Coast_Tour_IEM_Mobile_Setup.pdf"},
        "expected_class": "main_plus_support",
    },
    {
        "task_id": "7bbfcfe9",
        "deliverable_files": [_path("7bbfcfe9", "SCRA_Compliance_Test_Questions.xlsx")],
        "expected": {"SCRA_Compliance_Test_Questions.xlsx"},
    },
    {
        "task_id": "f9a1c16c",
        "deliverable_files": [_path("f9a1c16c", "Tour_Stage_Plot.pdf")],
        "expected": {"Tour_Stage_Plot.pdf"},
    },
    {
        "task_id": "bbe0a93b",
        "deliverable_files": [
            _path("bbe0a93b", "Kent_County_Community_Resource_Guide.pdf"),
            _path("bbe0a93b", "Kent_County_Needs_Assessment_English.pdf"),
            _path("bbe0a93b", "Kent_County_Needs_Assessment_Espanol.pdf"),
        ],
        "expected": {
            "Kent_County_Community_Resource_Guide.pdf",
            "Kent_County_Needs_Assessment_English.pdf",
            "Kent_County_Needs_Assessment_Espanol.pdf",
        },
        "expected_class": "separate_equivalent",
    },
    {
        "task_id": "85d95ce5",
        "deliverable_files": [
            _path("85d95ce5", "Notes for Terry Hartsdale.docx"),
            _path("85d95ce5", "J.S..pdf"),
        ],
        "reference_file_urls": [_ref_url("Notes for Terry Hartsdale.docx")],
        "expected": {"J.S..pdf"},
    },
    {
        "task_id": "1b1ade2d",
        "deliverable_files": [_path("1b1ade2d", "Revised_Sourcing_and_Nomination_Workflow_Lamp_Assemblies.docx")],
        "expected": {"Revised_Sourcing_and_Nomination_Workflow_Lamp_Assemblies.docx"},
    },
    {
        "task_id": "93b336f3",
        "deliverable_files": [_path("93b336f3", "EV_Battery_Assembly_Localisation_Partnership_Proposal.docx")],
        "expected": {"EV_Battery_Assembly_Localisation_Partnership_Proposal.docx"},
    },
    {
        "task_id": "575f8679",
        "deliverable_files": [_path("575f8679", "Immigration_and_Family_Stress_Evaluation_Plan.docx")],
        "expected": {"Immigration_and_Family_Stress_Evaluation_Plan.docx"},
    },
    {
        "task_id": "0419f1c3",
        "deliverable_files": [_path("0419f1c3", "Performance Improvement Plan – John Miller (07-13-2025).docx")],
        "expected": {"Performance Improvement Plan – John Miller (07-13-2025).docx"},
    },
    {
        "task_id": "6dcae3f5",
        "deliverable_files": [
            _path("6dcae3f5", "Chief Key Indicator 5-Year.xlsx"),
            _path("6dcae3f5", "Email_to_PD_Key_Indicator_Analysis.docx"),
            _path("6dcae3f5", "Key Indicators.xlsx"),
        ],
        "reference_file_urls": [_ref_url("Key Indicators.xlsx")],
        "expected": {
            "Chief Key Indicator 5-Year.xlsx",
            "Email_to_PD_Key_Indicator_Analysis.docx",
        },
        "expected_class": "separate_equivalent",
    },
    {
        "task_id": "a74ead3b",
        "deliverable_files": [
            _path("a74ead3b", "Session_13_Nurturing_Parenting_Recovery.pptx"),
            _path("a74ead3b", "Session_14_Nurturing_Parenting_Recovery.pptx"),
            _path("a74ead3b", "neutral_background.png"),
        ],
        "expected": {
            "Session_13_Nurturing_Parenting_Recovery.pptx",
            "Session_14_Nurturing_Parenting_Recovery.pptx",
        },
        "expected_class": "separate_equivalent",
    },
    {
        "task_id": "ec591973",
        "deliverable_files": [_path("ec591973", "Differentiated_Distribution_Strategy_Slide.pptx")],
        "expected": {"Differentiated_Distribution_Strategy_Slide.pptx"},
    },
    {
        "task_id": "9a0d8d36",
        "deliverable_files": [_path("9a0d8d36", "ISO_vs_NQSO_Tax_Comparison.pptx")],
        "expected": {"ISO_vs_NQSO_Tax_Comparison.pptx"},
    },
    {
        "task_id": "403b9234",
        "deliverable_files": [_path("403b9234", "Chamber_of_Commerce_Partnership_Proposal.pptx")],
        "expected": {"Chamber_of_Commerce_Partnership_Proposal.pptx"},
    },
]


def test_gold_20_selector_targets_match_owner_targets():
    matches = 0
    for fixture in GOLD_FIXTURES:
        selection = _select(fixture)
        assert selection.selection_status == "ok", fixture["task_id"]
        assert _selected_names(selection) == fixture["expected"], fixture["task_id"]
        if "expected_class" in fixture:
            assert selection.task_class == fixture["expected_class"]
        matches += 1
    assert matches == 20


def test_hermetic_contract_fixture_is_exact_minimal_and_source_bound():
    document = load_and_validate_fixture(FIXTURE_PATH)
    fixture_ids = {
        fixture["task_id"]
        for fixture in [*GOLD_FIXTURES, *WRONG_FORMAT_FIXTURES]
    } | {"a73fbc98"}

    assert set(document["tasks"]) == fixture_ids
    assert len(canonical_json(document)) < 8 * 1024
    assert document["source"] == {
        "repository": "openai/gdpval",
        "revision": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
        "parquet_path": "data/train-00000-of-00001.parquet",
        "parquet_sha256": (
            "f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202"
        ),
        "row_count": 220,
        "projection_policy": "synthetic-minimal-selector-signals-v1",
        "source_content_included": False,
    }


def test_bug2_four_cases_are_corrected_to_generated_primary():
    bug2 = {
        "7d7fc9a7": {"Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx"},
        "43dc9778": {"Smith_2024_Form_1040_Draft.pdf"},
        "ee09d943": {"Aurisic_Financials_4-25-1.xlsx"},
        "99ac6944": {"West_Coast_Tour_IEM_Mobile_Setup.pdf"},
    }
    by_task = {fixture["task_id"]: fixture for fixture in GOLD_FIXTURES}
    for task_id, expected in bug2.items():
        selection = _select(by_task[task_id])
        assert _selected_names(selection) == expected
        assert not expected.intersection(
            {p.rsplit("/", 1)[-1] for p in selection.reference_files_excluded}
        )


WRONG_FORMAT_FIXTURES = [
    {
        "task_id": "ff85ee58",
        "deliverable_files": [
            _path("ff85ee58", "Tavarua_Mix_Reconstruction_Report.docx"),
            _path("ff85ee58", "Tavarua_Sax_Timing_Grid.xlsx"),
        ],
    },
    {
        "task_id": "e222075d",
        "deliverable_files": [
            _path("e222075d", "Graphic_Renewable_Reliable_Green_Energy.png"),
            _path("e222075d", "Support_Green_Energy_30s_Edit_Plan.docx"),
        ],
    },
    {
        "task_id": "c94452e4",
        "deliverable_files": [
            _path("c94452e4", "Care_Not_Cutbacks_Animatic.pptx"),
            _path("c94452e4", "Care_Not_Cutbacks_Timing.xlsx"),
        ],
    },
    {
        "task_id": "75401f7c",
        "deliverable_files": [
            _path("75401f7c", "Goodsin_Studios_Showreel_Edit_Plan_2025.docx"),
            _path("75401f7c", "Goodsin_Studios_Showreel_Timeline.xlsx"),
        ],
    },
    {
        "task_id": "a941b6d8",
        "deliverable_files": [
            _path("a941b6d8", "Teleportation_Compositing_Workflow.pdf"),
            _path("a941b6d8", "Teleportation_Vanish_MockFrame.png"),
        ],
    },
    {
        "task_id": "c7d83f01",
        "deliverable_files": [
            _path("c7d83f01", "convergence_binomial.png"),
            _path("c7d83f01", "pricing_comparison.png"),
        ],
    },
    {
        "task_id": "a95a5829",
        "deliverable_files": [
            _path("a95a5829", "General_Order_Training_Request_Process.docx"),
            _path("a95a5829", "Training_Request_Log.xlsx"),
        ],
    },
]


def test_wrong_format_primary_fires_for_seven_contract_signals():
    for fixture in WRONG_FORMAT_FIXTURES:
        selection = _select(fixture)
        assert selection.selection_status == "wrong_format_primary", fixture["task_id"]
        assert selection.task_class == "ambiguous"
        assert selection.primary_targets == []
        assert selection.selection_error


def test_no_generated_candidate_is_distinct_from_selection_error():
    selection = select_deliverables(
        task_id="only-reference",
        deliverable_files=[_path("only-reference", "Input.xlsx")],
        reference_file_urls=[_ref_url("Input.xlsx")],
        rubric_items=[{"criterion": "Provides an Excel workbook.", "score": 1}],
    )
    assert selection.selection_status == "no_generated_candidate"
    assert selection.selection_error
    assert selection.primary_targets == []


@pytest.mark.parametrize(
    "criterion",
    [
        "Overall Style",
        "Overall formatting and style of the deliverable",
        "The overall presentation and professional polish",
    ],
)
def test_criterion_routing_uses_hybrid_policy_for_overall_style(criterion):
    separate = _select(next(f for f in GOLD_FIXTURES if f["task_id"] == "a74ead3b"))
    plan = plan_targets_for_criterion(separate, criterion)
    assert plan.target_scope == "split_children"
    assert plan.aggregation_rule == "blocking_min_else_mean"
    assert set(plan.target_ids) == {
        "session_13_nurturing_parenting_recovery",
        "session_14_nurturing_parenting_recovery",
    }

    main = _select(next(f for f in GOLD_FIXTURES if f["task_id"] == "99ac6944"))
    main_plan = plan_targets_for_criterion(main, criterion)
    assert main_plan.target_scope == "file_target"
    assert main_plan.selected_paths == [_path("99ac6944", "West_Coast_Tour_IEM_Mobile_Setup.pdf")]


def test_criterion_routing_manifest_file_specific_and_bundle_cases():
    separate = _select(next(f for f in GOLD_FIXTURES if f["task_id"] == "a74ead3b"))
    manifest = plan_targets_for_criterion(
        separate,
        _actual_criterion("a74ead3b", "Provides two distinct .pptx files"),
    )
    assert manifest.target_scope == "manifest"

    session_14 = plan_targets_for_criterion(
        separate,
        _actual_criterion("a74ead3b", "Session 14 deck includes a title slide"),
    )
    assert session_14.target_scope == "file_target"
    assert session_14.target_ids == ["session_14_nurturing_parenting_recovery"]

    bazaar = select_deliverables(
        task_id="a73fbc98",
        deliverable_files=[
            _path("a73fbc98", "Spring_Bazaar_2025_Table_Assignment_Summary.pdf"),
            _path("a73fbc98", "Spring_Bazaar_2025_Vendor_Assignments.xlsx"),
        ],
        instruction=CONTRACT_TASK_DATA["a73fbc98"]["instruction"],
        rubric_items=CONTRACT_TASK_DATA["a73fbc98"]["rubric_items"],
    )
    bundle = plan_targets_for_criterion(
        bazaar,
        _actual_criterion("a73fbc98", "Every assigned table ID in the spreadsheet also appears"),
    )
    assert bundle.target_scope == "primary_bundle"
    assert len(bundle.target_ids) == 2


def test_selection_object_and_audit_schema_are_structured_not_bare_paths():
    selection = _select(next(f for f in GOLD_FIXTURES if f["task_id"] == "99ac6944"))
    payload = selection.to_dict()
    assert payload["selection_status"] == "ok"
    assert isinstance(payload["primary_targets"], list)
    assert payload["primary_targets"][0]["paths"] == [
        _path("99ac6944", "West_Coast_Tour_IEM_Mobile_Setup.pdf")
    ]
    assert set(ITEM_TARGET_AUDIT_SCHEMA["required"]) == {
        "rubric_item_id",
        "target_scope",
        "target_ids",
        "child_grades",
        "aggregation_rule",
        "selected_paths",
        "support_paths_visible",
    }


# The four tests below cover the fall-through that used to return
# "ambiguous_candidates": several same-format outputs and an instruction that
# never says how many files it wants. On the sol-220 run that fall-through was
# 243 of 333 judge errors across 5 tasks, every one of which scored zero with
# the judge never called, on tasks where the model had in fact delivered.
#
# The shapes here are taken from those tasks: a checklist plus a fax cover
# sheet, five parallel school reports, a guide plus its application form.


def _uniform_selection(names: list[str], criteria: list[str], instruction: str = ""):
    return select_deliverables(
        task_id="uniform",
        deliverable_files=[_path("uniform", name) for name in names],
        instruction=instruction,
        rubric_items=[{"criterion": c, "score": 1} for c in criteria],
    )


def test_uniform_same_format_outputs_are_recovered_as_separate_primaries():
    selection = _uniform_selection(
        ["Fax_Cover_Sheet.docx", "Admission_Pre_Screening_Checklist.docx"],
        [
            "Includes a title at the top of the fax cover sheet.",
            "Includes a labeled, writable field for the sender's name.",
            "Lists the required pre-admission documents.",
        ],
    )

    assert selection.selection_status == "ok"
    assert selection.task_class == "separate_equivalent"
    # A distinct rule, not the one explicit language earns. Both reach the same
    # routing, but an audit has to be able to tell which tasks rest on the
    # weaker inference.
    assert selection.selection_rule == "set_diff_then_uniform_primaries"
    assert _selected_names(selection) == {
        "Fax_Cover_Sheet.docx",
        "Admission_Pre_Screening_Checklist.docx",
    }


def test_uniform_recovery_scales_past_two_equivalent_outputs():
    names = [
        "Floral_Park_Bellerose_School_Report.pdf",
        "Garden_City_Park_School_Report.pdf",
        "Hillside_Grade_School_Report.pdf",
        "John_Lewis_Childs_School_Report.pdf",
        "Manor_Oaks_School_Report.pdf",
    ]
    selection = _uniform_selection(
        names,
        [
            "The report includes the overall Niche.com grade for Hillside Grade School.",
            "The report includes the overall Niche.com grade for Manor Oaks School.",
        ],
    )

    assert selection.selection_status == "ok"
    assert selection.selection_rule == "set_diff_then_uniform_primaries"
    assert _selected_names(selection) == set(names)


def test_uniform_recovery_shows_the_judge_every_file_by_default():
    # This is what makes equal primaries safe where choosing one would not be.
    # "fax cover sheet" does not match the filename Fax_Cover_Sheet, so the
    # criterion routes to the bundle rather than to one file -- and that is the
    # common case, not the exception. The judge gets both files plus the
    # criterion text and resolves which one it is about. Nothing is demoted and
    # nothing is hidden, which is exactly what picking a single primary here
    # would have done.
    selection = _uniform_selection(
        ["Fax_Cover_Sheet.docx", "Admission_Pre_Screening_Checklist.docx"],
        ["Limits the fax cover sheet length to one page."],
    )

    plan = plan_targets_for_criterion(
        selection, "Limits the fax cover sheet length to one page."
    )

    assert plan.target_scope == "primary_bundle"
    assert plan.selected_paths == [
        _path("uniform", "Fax_Cover_Sheet.docx"),
        _path("uniform", "Admission_Pre_Screening_Checklist.docx"),
    ]


def test_uniform_recovery_still_narrows_when_a_criterion_names_the_file():
    selection = _uniform_selection(
        ["Fax_Cover_Sheet.docx", "Admission_Pre_Screening_Checklist.docx"],
        ["Limits Fax_Cover_Sheet to one page."],
    )

    plan = plan_targets_for_criterion(selection, "Limits Fax_Cover_Sheet to one page.")

    assert plan.target_scope == "file_target"
    assert plan.selected_paths == [_path("uniform", "Fax_Cover_Sheet.docx")]


def test_explicit_separate_language_keeps_its_own_stronger_rule():
    # The recovery is a fall-through and must stay one: a task whose
    # instruction does say how many files it wants is still classified by that
    # statement, not by counting outputs.
    selection = _uniform_selection(
        ["Session_13.pptx", "Session_14.pptx"],
        ["Provides two separate presentations, one per session."],
    )

    assert selection.selection_status == "ok"
    assert selection.selection_rule == "set_diff_then_separate_primaries"


def test_candidates_with_no_document_still_decline_to_choose():
    # The point of the change is not that the selector now always answers. With
    # nothing document-like to grade there is still no defensible choice, and
    # saying so remains better than inventing one.
    selection = _uniform_selection(
        ["convergence_binomial.png", "pricing_comparison.png"],
        ["The chart is readable."],
    )

    assert selection.selection_status == "selection_error"
    assert selection.task_class == "ambiguous"
    assert selection.selection_rule == "ambiguous_candidates"
    assert selection.primary_targets == []
