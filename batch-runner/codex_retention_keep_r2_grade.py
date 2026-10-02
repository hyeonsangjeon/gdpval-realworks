"""Fixed evidence adapter for one keep/r2 grade; no lifecycle or live CLI."""

from pathlib import Path

import codex_budget_pilot as pilot
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained

SELECTOR = "retention/keep-r2"
CELL = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2"
ORDINAL, REPETITION = 3, 2
PREFIX = "retention-cell-grades/retention_bundle_diagnostic_20260929/" + CELL
CLAIM_PATH, TERMINAL_PATH = PREFIX + "/claim.json", PREFIX + "/terminal.json"
CLAIM_FORMAT = "retention-task4-keep-r2-grade-claim-v1"
TERMINAL_FORMAT = "retention-task4-keep-r2-grade-terminal-v1"
PREPARATION_FORMAT = "retention-task4-keep-r2-grade-preparation-v1"
GRADER_PATH = "batch-runner/workspace/retention-ci-task4-keep-r2/grader-config.json"
INFERENCE_CONFIG_PATH = "batch-runner/workspace/retention-ci-task4-keep-r2/inference-config.json"
GRADER_SHA256 = "997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1"
MARKER = "retention-keep-r2-result-intake.json"
READER = {
    "module_sha256": "5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583",
    "intake_sha256": "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196",
    "ci_sha256": "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c",
    "producer_facade_sha256": "a0710039c33c17af85f226269ceeaccdb1c17bbc7238a46a15614226afed26e3",
    "controller_sha256": "957934b869ed5071923add7e9554aa68de941c9488f3e6d650557d27f6179601",
    "producer_r2_sha256": "8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f",
    "producer_keep_r2_sha256": "12106b5423e25ffefa1b04023e2e98742861762762966a04bf17fe3da1851450",
}
READER_FILES = {
    "module_sha256": "codex_retention_fresh_r1_result_intake.py",
    "intake_sha256": "codex_retention_result_intake.py",
    "ci_sha256": "codex_retention_ci.py",
    "producer_facade_sha256": "codex_retention_task4_fresh_r1.py",
    "controller_sha256": "codex_retention_first_cell.py",
    "producer_r2_sha256": "codex_retention_task4_fresh_r2.py",
    "producer_keep_r2_sha256": "codex_retention_task4_keep_r2.py",
}

# Independent leader-read full-marker/payload pins, never a safe-receipt reconstruction.
RESULT = {
    "producer_source_sha": "b8351e561acb9675a4993419e819c12787b5b305",
    "request_sha256": "8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1",
    "cell_id": CELL, "ordinal": 3,
    "recorded_provider_run_id": "36947454688", "recorded_provider_job_id": 110660390316,
    "expected_execution_job_id": 110660390316,
    "terminal_commit": "e55fac5d60191167dd66688510ec0fef472e594d",
    "terminal_identity": {"sha256": "70fb8778ae15e369ef1ac4d03dbe4fa6f5d9852966b250fa812695d6bd77bf91", "size": 5885},
    "claim_commit": "f29f8d4a19710aa0e832dba720ff7d32701c309c",
    "claim_identity": {"sha256": "4af63e82ddcaf2b795595081c59d29369e2bf2a4bb2c37f81eb7f5409cd6b363", "size": 1888},
    "output_commit": "54a4362ce3554b7c71b5ada00802efc9521038e6",
    "output_manifest_identity": {"sha256": "93e1dada24779909cfc593dff7507b7f9c6452c6f36c12b2c5e86305e35d9a8c", "size": 2679},
    "output_objects_sha256": "4bda1c0d48a5dd980bd683a6f8316b3d52808e95dca68099b86ad4de2d3e03b2",
    "intake_sha256": "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4",
    "retained_authority_sha256": "7427be5a3d3f5692ca9d92920161c7ddf4491faf39f36f9ee9cee062f45f5705",
    "result": {
        "sha256": "8d90bb52bc87f5989baba1eea59de205155523492e9b679087eac5c12b7e539e", "size": 10238,
        "result_fingerprint": "909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a",
        "recorded_prepared_fingerprint": "fb6e4301ec91245601e80fc6f181076513dd71bd358bb0fbc856b5080e8108e8",
        "registered_config_sha256": "307dc07923d377faa7d7c6bd6c4934de2fa5f99e9007dd0d723f3c3337e6d010",
    },
}
PARENT = {
    "branch": "pilot-grades-20260925-04",
    "cell_id": "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1",
    "revision": "40712e0980cc05c31688fdbb98c693774fb90c0d",
    "terminal_identity": {"sha256": "11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234", "size": 3119},
    "claim_revision": "dec305d669e3ca2e53c7f7b9ebfbe7974d661350",
    "claim_identity": {"sha256": "8e1e0a51b462a442e9024c2bd5140d3898b61424ce3f44d4adff9fa346cce53d", "size": 2384},
    "writer_source_sha": "29e0353f1539265b1741e71be894fedf9be32a8b",
    "writer_run": {"id": "36776393736", "job": "pilot-live", "attempt": 1},
    "observer_source_sha": "f30c9efa392bc14cba790fb5d1dedf12071a5677", "observer_run_id": "36820845596",
    "fixed_evidence_sha256": "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d",
    "inference_terminal": "de50ff0aa6037c0ef6e3b713da519359abd1d08d",
    "result_fingerprint": "3441f200e6e4c53faf1b36f216283c80eee68e5d3e7d827587ba6c3135c7d200",
}


def _reader():
    # Even direct consumer calls verify actual bytes before the lazy import.
    for key, name in READER_FILES.items():
        data = output._bytes(Path(__file__).with_name(name), limit=output.MAX_RECORD_BYTES)
        output._require(pilot._identity(data)["sha256"] == READER[key], "reviewed_retention_reader_required")
    import codex_retention_fresh_r1_result_intake as reader
    return reader


def read_result(destination, *, _test_api=None):
    reader = _reader()
    return reader.read_result(expectation=reader.KEEP_R2.expectation, binding=reader.KEEP_R2,
        destination=destination, expected_reader_sha256=READER["module_sha256"],
        terminal_revision=RESULT["terminal_commit"], discover_terminal=False, _test_api=_test_api)


def intake_boundary():
    reader = _reader()
    return {
        "format": reader.KEEP_R2.result_format, "campaign": reader.intake.registration.CAMPAIGN,
        "expected_provider": {"workflow_id": 370228282, "workflow": reader.ci.WORKFLOW,
                              "run_id": "36947454688", "attempt": 1},
        "supplied_request_binding": {"original_input_bundle_sha256": reader.KEEP_R2.original_input_bundle_sha256,
                                     "materialized_grader_source_sha256": GRADER_SHA256},
        "predecessor": reader._producer(reader.KEEP_R2).PREDECESSOR,
        "recorded_publication_acknowledged": True, "grading_launched": False,
        "proof": "verified_publication_derived_not_independent_provider_authentication",
        "fresh_origin_authentication": False, "prepared_input_independently_verified": False,
        "git_parent_cas_independently_verified": False, "writer_acknowledgment": "not_established",
        "launch_authorized": False, "admission_attempted": False, "replay_authorized": False, "commands": [],
        "http_request_count": None,
    }


def parent_controls(api, repo, cache, token, deadline):
    """Existing canonical grade readout, controls/metadata only; no payload read."""
    import codex_retention_fixed_grade as first
    import codex_retention_grade_readout as readout
    from codex_budget_pilot_grading import _cache

    first._same({"revision": readout.TERMINAL, "terminal_identity": readout.TERMINAL_IDENTITY,
        "claim_revision": readout.CLAIM, "writer_source_sha": readout.WRITER_SOURCE,
        "writer_run": readout.WRITER_RUN, "fixed_evidence_sha256": first.fixed_evidence_sha256(),
        "inference_terminal": first.RESULT["terminal_commit"],
        "result_fingerprint": first.RESULT["result"]["result_fingerprint"]},
        {key: PARENT[key] for key in ("revision", "terminal_identity", "claim_revision", "writer_source_sha",
            "writer_run", "fixed_evidence_sha256", "inference_terminal", "result_fingerprint")},
        "fixed_keep_r1_grading_parent_required")
    context = first.compile_request(PARENT["writer_source_sha"])
    scoped = readout._ReadOnlyGrade(api, repo, token)
    terminal, _, identity = scoped.verify(context, _cache(cache, "keep-r1-controls"), deadline)
    first._same(identity, PARENT["terminal_identity"], "fixed_grading_parent_identity_mismatch")
    first._same(terminal["claim_identity"], PARENT["claim_identity"], "fixed_grading_parent_claim_mismatch")
    _, claim = readout._terminal_contract(context, terminal)
    return [(retained._object(first.TERMINAL_PATH, retained._encoded(terminal)), PARENT["revision"]),
            (retained._object(first.CLAIM_PATH, retained._encoded(claim)), PARENT["claim_revision"])]
