"""Pure report assertions; no producer, reader, transport or grading invocation."""

from copy import deepcopy
import hashlib
import json


# PR736's code-only document snapshot. These raw hashes are historical evidence,
# not requirements that a later, explicitly authorized report keep the old bytes.
PRIOR_CODE_ONLY_ARTIFACTS = {
    "tasks/codex_budget_pilot/retention_diagnostic_readout.json": "31f7d2b58d044a5548cb9998362b8b6ebaf2d428b4d679b4a42f4191d666814e",
    "tasks/codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md": "12ad05a9483461161e431a8fef834c90cf62832a0177e8a514cb32b3ce32b699",
    "tasks/codex_budget_pilot/REPORT.md": "88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e",
}
PRIOR_CANONICAL_SHA256 = "67b45c772853b8479065247a049fe73f6876dc6b2e9b1e4d6f8cc1839a810625"
PROJECTOR_SHA256 = "96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815"

# Independently authored from the eight leader receipts, in registered order.
# Remaining is zero-clamped, wait is backoff, and the counts are native units.
BUDGET_POINTS = (
    ("Task4 keep/r1", 1790763001.2195864, 1790773801.2195864, 7912.227738618851, 1860.7502946853638, 10, 9),
    ("Task4 fresh/r1", 1790850168.3271084, 1790860968.3271084, 0.0, 8983.719460487366, 39, 0),
    ("Task4 fresh/r2", 1790881801.5121758, 1790892601.5121758, 0.0, 8985.385900974274, 39, 0),
    ("Task4 keep/r2", 1790903881.1127117, 1790914681.1127117, 9564.73209309578, 900.3846650123596, 6, 5),
    ("Task5 fresh/r1", 1790959571.661407, 1790970371.661407, 4909.906562328339, 3781.06050658226, 18, 0),
    ("Task5 keep/r1", 1790976592.4457858, 1790987392.4457858, 7373.157982349396, 2580.858815908432, 13, 12),
    ("Task5 keep/r2", 1790987596.6290615, 1790998396.6290615, 0.0, 8742.75936126709, 38, 37),
    ("Task5 fresh/r2", 1791009579.9246106, 1791020379.9246106, 10724.012340545654, 0.0, 1, 0),
)
MEASUREMENT_LIMITS = [
    "remaining_seconds_is_zero_clamped_not_uncapped_elapsed_or_failure_cause",
    "wait_seconds_is_retry_backoff_only",
    "admissions_and_confirmed_native_resumes_are_not_model_or_HTTP_calls",
    "snapshot_does_not_establish_absence_of_provider_errors_or_unrecorded_recovery",
]

SUCCESS_RECEIPTS = {
    0: {
        "source_addendum": "Project5 leader order 2026-10-04 05:59 KST; actual RESULT-only receipt supplied by the leader, not a worker live read",
        "source_sha": "8494f7c9602c90a9cc354db8b683e9ab01b14426",
        "run_id": "37151823235", "job_id": 111287106594, "receipt_utc": "2026-10-03T20:33:49.6433784Z",
        "marker_sha256": "50403a8d9e7b4324e969df5adc5b7e62a37fcf7a9e87b3f882ed1c32da2a9123",
        "historical_reader_sha256": "043100017cb1db06f74b562b5feca1a6de8e3eed99ff153645e9a33b3481d975",
        "terminal_commit": "de50ff0aa6037c0ef6e3b713da519359abd1d08d",
        "output_commit": "43cbf8e265297813857172ecee51256cc17f2d36",
        "claim_commit": "3fc283087a020caec574e8c9b8e9bc3ca593e88a",
        "claim_identity": {"sha256": "2934d7cc0607be4cd96b5a9f57a7726530cef72548acf81388577dcbbc9addb0", "size": 1287},
        "output_objects_sha256": "ec8c97776d5e1d426f4c506cc571721a1a89d330c25f171612699c7a05813b76",
        "retained_authority_sha256": "110fbd2bbced7528236fda846bf930198006d6867a100cf690b03b7a1d55777c",
        "result": {
            "sha256": "07f335a07ffc8d921a0cfa0c7ab6bbc3728d704adc7c31f7ac1d3594728e3f67", "size": 10972,
            "result_fingerprint": "3441f200e6e4c53faf1b36f216283c80eee68e5d3e7d827587ba6c3135c7d200",
            "recorded_prepared_fingerprint": "e9ffd87a8da6f06e26449b7f8d68468e674ea241e787a84568dace72774a2247",
            "registered_config_sha256": "08b29f44cb57312fd5757a3192c1a64855922bcd3d48d8e02fed96c4160683cb",
        },
        "declared_payload_roles": {"inference_result": 1, "ledger": 1, "deliverables": 4},
        "declared_output_object_count": 7,
    },
    3: {
        "source_addendum": "Project5 leader order 2026-10-04 05:28 KST; actual RESULT-only receipt supplied by the leader, not a worker live read",
        "source_sha": "5acffea43bc621daf1ae7fba014aa47a559e6ca1",
        "run_id": "37146242626", "job_id": 111270679161, "receipt_utc": "2026-10-03T19:01:45.8846626Z",
        "marker_sha256": "42ed9d57052c6c062e1686f469b0c9d38d92d58d6bfcdefb2a79905f958c9355",
        "historical_reader_sha256": "631dd2a76faecd28ae65bdbe69d755f598aa4b025cfc66a8280872c2f3a2bc96",
        "terminal_commit": "e55fac5d60191167dd66688510ec0fef472e594d",
        "output_commit": "54a4362ce3554b7c71b5ada00802efc9521038e6",
        "retained_authority_sha256": "7427be5a3d3f5692ca9d92920161c7ddf4491faf39f36f9ee9cee062f45f5705",
        "result": {
            "sha256": "8d90bb52bc87f5989baba1eea59de205155523492e9b679087eac5c12b7e539e", "size": 10238,
            "result_fingerprint": "909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a",
            "recorded_prepared_fingerprint": "fb6e4301ec91245601e80fc6f181076513dd71bd358bb0fbc856b5080e8108e8",
            "registered_config_sha256": "307dc07923d377faa7d7c6bd6c4934de2fa5f99e9007dd0d723f3c3337e6d010",
        },
        "declared_payload_roles": {"inference_result": 1, "ledger": 1, "deliverables": 3},
    },
}


def canonical_digest(value):
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def expected_snapshot(index):
    _, started, expires, remaining, wait, admissions, resumes = BUDGET_POINTS[index]
    return {"total_seconds": 10800, "started_unix": started, "expires_unix": expires,
            "remaining_seconds": remaining, "wait_seconds": wait,
            "attempts_admitted": admissions, "native_resumes": resumes, "missing": {}}


def assert_success_budget_observations(readout):
    """The new receipts are partial RESULT observations, not new successful intakes."""
    for index, supplied in SUCCESS_RECEIPTS.items():
        row = readout["cells"][index]
        actual = row["current_budget_observation"]
        expected = {
            **supplied,
            "historical_scope": "original_full_intake_grade_and_missing_fields_preserved_not_reestablished_by_budget_observation",
            "mode": "observe_budget", "outcome": "budget_observation_verified", "approval_execution_skipped": True,
            "budget_projector_sha256": PROJECTOR_SHA256,
            "supplied_request_binding": {
                "original_input_bundle_sha256": "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3",
                "materialized_grader_source_sha256": row["supplied_materialized_grader_source_sha256"],
            },
            "inference_budget_snapshot": expected_snapshot(index),
            "status": "succeeded", "exit_code": 0, "cleanup_confirmed": True, "grade": None,
            "result_body_verified": True, "payload_verification_scope": "inference_result_only",
            "payload_bodies_verified": False, "ledger_body_verified": False, "deliverable_bodies_verified": False,
            "grading_input_ready": False, "full_intake_established_by_this_observation": False,
            "delivery_established_by_this_observation": False, "grade_established_by_this_observation": False,
            "writer_acknowledgment": "not_established", "recorded_publication_acknowledged": True,
            "fresh_origin_authentication": False, "prepared_input_independently_verified": False,
            "git_parent_cas_independently_verified": False,
            "unavailable": {key: {"status": "unavailable", "value": None, "reason": "not_recorded_in_terminal_controls"}
                            for key in ("detailed_failure", "recovery_exposure")},
            "measurement_limits": MEASUREMENT_LIMITS, "live_read_repeated_here": False, "replay_authorized": False,
        }
        assert actual == expected, f"supplied successful-cell observation differs at ordinal {index}"
        assert type(actual["exit_code"]) is int and type(actual["result"]["size"]) is int
        assert actual["terminal_commit"] == row["terminal"]["revision"]
        assert actual["output_commit"] == row["output_manifest"]["revision"]
        assert actual["result"]["result_fingerprint"] == row["grade"]["inference_result_fingerprint"]
        assert row["read"]["successful_intake_established"] is True
        assert row["realized_budget_and_recovery"] is None
        assert row["realized_details_missing_reason"] == "not_established_by_retained_report_evidence"
    first = readout["cells"][0]
    assert "exit_code" not in first  # The legacy row had no numeric field at all.
    assert first["claim"]["sha256"] is first["claim"]["bytes"] is first["output_objects_sha256"] is None
    assert first["claim"]["missing_reason"] == "identity_not_in_retained_summary_or_fixed_binding"
    assert first["current_budget_observation"]["claim_commit"] == first["claim"]["revision"]
    assert readout["cells"][3]["current_budget_observation"]["retained_authority_sha256"] == (
        readout["cells"][3]["read"]["retained_authority_sha256"])


def before_success_budget_observations(readout):
    """Strip only this unit's two additions, then check the accepted prior scope."""
    prior = deepcopy(readout)
    for index in (0, 3):
        prior["cells"][index].pop("current_budget_observation")
    assert canonical_digest(prior) == PRIOR_CANONICAL_SHA256
    assert_success_budget_observations(readout)
    return prior


def assert_consolidated_report(report, readout):
    """Current-document conditions replace obsolete code-only document hashes."""
    normalized = " ".join(report.split())
    assert "All eight budget observations are verified and consumed, not eight successful tasks." in normalized
    for index, (label, _, _, remaining, wait, admissions, resumes) in enumerate(BUDGET_POINTS):
        line = f"| {label} | RESULT-only | {remaining} | {wait} | {admissions} | {resumes} |"
        assert report.count(line) == 1, f"budget table mismatch at ordinal {index}"
        observation = readout["cells"][index]["current_budget_observation"]
        assert observation["marker_sha256"] in report and observation["result"]["sha256"] in report
        for field in ("started_unix", "expires_unix"):
            assert str(observation["inference_budget_snapshot"][field]) in report
    for protected in (
        "The denominator is eight cells, not eight successes.",
        "The six failures have null grades, not zero scores.",
        "24 epoch04 outcomes (18 graded and 6 model-free UNGRADED) plus 6 frozen epoch03 Task1 failures.",
        "Its 24 retained epoch04 budget snapshots are observed; they are not 30 budget observations.",
        "A/B changes retry policy and retention together.",
        "They did not establish a C-over-B benefit.",
        "B1/B2 each scored 53.84% on the full denominator, versus C1's 51.88% and C2's 51.70%.",
        "a negative C-versus-B descriptive result in both repetitions, not proof that feedback caused harm.",
        "Each cell has 10800 cumulative seconds from first admission, including waits, recovery and downtime without reset.",
        "The 1800-second native-turn wait is not an all-in attempt ceiling.",
        "There is no fixed admission count or automatic monetary cap.",
        "Neither treatment imports its predecessor's state.",
        "USD 5.206594 across 164 recorded model calls.",
        "Task4 contributes USD 1.234642 / 94 calls and Task5 USD 3.971952 / 70 calls.",
        "30.6/45 = 68.0% included and 54.64% on the full denominator.",
        "30.35/45 = 67.44% included and 54.20% full.",
        "Each excludes 9 items worth a maximum of 11 points from the full maximum of 56.",
        "The keep/r1 grade records 93 model calls; keep/r2 records 91.",
        "There is no global grade average or cost-efficiency ranking.",
        "retry backoff, not all recovery or downtime.",
        "neither is a model or HTTP-call count.",
        "not an estimate of retention benefit.",
        "Detailed eligible recovery opportunities and realized state-retention exposure remain unavailable.",
        "This report did not query either consumed operation.",
        "it is not the full failure taxonomy.",
        "This is not runtime output-limit emission or new recovery eligibility.",
        "SDK 0.147.0 supplies no typed Retry-After/retry guidance in this contract; free-form messages are not instructions.",
        "of 3 diagnoses in220 rows does not diagnose the 30-cell pilot or eight-cell retention study.",
        "Detailed causes and recovery exposure of the six retention failures remain unavailable.",
        "All 30 original pilot outcomes, all eight separate diagnostic outcomes and all eight diagnostic budget reads are finished and consumed, including failures.",
        "An inconclusive result is not an unexecuted cell.",
        "Rewriting records cannot supply those measurements.",
        "The dispositions above remain in force; this mapping establishes no additional undelivered implementation.",
        "external-input blockers for their own work, not missing pilot or retention results.",
        "does not close the whole card or all Project5 work",
        "The leader owns acceptance",
        "no 30/220-task expansion is authorized.",
        "All eight receipts verify only RESULT bodies, not ledger, deliverables or overall payload",
    ):
        assert protected in normalized, f"missing report boundary: {protected}"
    for criterion in (
        "Cumulative external limits without reset", "Authority separation",
        "Error/retry classification and retry hints", "State preservation and no replay", "Offline fault injection",
        "Finite outcomes, deliverables and grades", "Realized budget points",
        "Wait, admission and resume measurements", "Usage and cost", "Retention/feedback tradeoff and attribution",
    ):
        assert f"| {criterion} |" in report
    for obsolete in (
        "Both successful Task4 KEEP budgets remain unobserved",
        "seven known points", "first-cell budget remains unobserved",
    ):
        assert obsolete not in normalized
