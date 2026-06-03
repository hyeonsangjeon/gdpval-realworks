"""Unit tests for the standalone deliverable selector.

No Azure calls, no grading, no rendering. The task fixtures use the actual
GDPVal ``rubric_json`` rows from the local parquet; only file lists and owner
expected targets are fixture data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.deliverable_selector import (
    ITEM_TARGET_AUDIT_SCHEMA,
    DeliverableSelection,
    plan_targets_for_criterion,
    select_deliverables,
)


def _path(task: str, name: str) -> str:
    return f"deliverable_files/{task}/{name}"


def _ref_url(name: str) -> str:
    encoded = name.replace(" ", "%20")
    return f"https://huggingface.co/datasets/openai/gdpval/resolve/main/reference_files/hash/{encoded}"


def _load_actual_task_data() -> dict[str, dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[2]
    parquet = repo_root / "data/gdpval-local/data/train-00000-of-00001.parquet"
    df = pd.read_parquet(parquet)
    data: dict[str, dict[str, Any]] = {}
    for row in df.to_dict("records"):
        rubric = row["rubric_json"]
        if isinstance(rubric, str):
            rubric = json.loads(rubric)
        data[row["task_id"][:8]] = {
            "prompt": row["prompt"],
            "rubric_items": rubric,
        }
    return data


ACTUAL_TASK_DATA = _load_actual_task_data()


def _selected_names(selection: DeliverableSelection) -> set[str]:
    names: set[str] = set()
    for target in selection.primary_targets:
        for path in target.paths:
            names.add(path.rsplit("/", 1)[-1])
    return names


def _actual_criterion(task_id: str, contains: str) -> str:
    for item in ACTUAL_TASK_DATA[task_id]["rubric_items"]:
        criterion = item["criterion"]
        if contains in criterion:
            return criterion
    raise AssertionError(f"criterion containing {contains!r} not found for {task_id}")


def _select(fixture: dict[str, Any]) -> DeliverableSelection:
    task = ACTUAL_TASK_DATA[fixture["task_id"]]
    return select_deliverables(
        task_id=fixture["task_id"],
        deliverable_files=fixture["deliverable_files"],
        reference_file_urls=fixture.get("reference_file_urls", []),
        instruction=task["prompt"],
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


def test_wrong_format_primary_fires_for_ambiguous_seven_with_actual_rubrics():
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


def test_criterion_routing_uses_hybrid_policy_for_overall_style():
    separate = _select(next(f for f in GOLD_FIXTURES if f["task_id"] == "a74ead3b"))
    plan = plan_targets_for_criterion(
        separate,
        _actual_criterion("a74ead3b", "Overall formatting and style"),
    )
    assert plan.target_scope == "split_children"
    assert plan.aggregation_rule == "blocking_min_else_mean"
    assert set(plan.target_ids) == {
        "session_13_nurturing_parenting_recovery",
        "session_14_nurturing_parenting_recovery",
    }

    main = _select(next(f for f in GOLD_FIXTURES if f["task_id"] == "99ac6944"))
    main_plan = plan_targets_for_criterion(
        main,
        _actual_criterion("99ac6944", "Overall formatting and style"),
    )
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
        instruction=ACTUAL_TASK_DATA["a73fbc98"]["prompt"],
        rubric_items=ACTUAL_TASK_DATA["a73fbc98"]["rubric_items"],
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
