"""Tests for the pinned paired diagnostic analysis."""

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "analyze_exp026_exp027.py"
SPEC = importlib.util.spec_from_file_location("analyze_exp026_exp027", MODULE_PATH)
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(analysis)


def _report(statuses, scores, latencies):
    return {
        "task_results": [
            {
                "task_id": task_id,
                "status": status,
                "qa_score": scores[index],
                "latency_ms": latencies[index],
                "retried": index % 2 == 0,
            }
            for index, (task_id, status) in enumerate(statuses.items())
        ]
    }


def test_analyze_builds_transition_matrix_and_paired_metrics():
    selection = {
        "groups": {
            "group_a": ["a", "b"],
            "group_b": ["c"],
            "group_c": [],
        }
    }
    exp026 = _report(
        {"a": "success", "b": "qa_failed", "c": "error"},
        [6, 4, None],
        [100, 200, 300],
    )
    exp027 = _report(
        {"a": "error", "b": "success", "c": "error"},
        [None, 5, None],
        [50, 150, 250],
    )

    result = analysis.analyze(exp026, exp027, selection)

    assert result["status_transition_matrix"]["success"]["error"] == 1
    assert result["status_transition_matrix"]["qa_failed"]["success"] == 1
    assert result["status_transition_matrix"]["error"]["error"] == 1
    assert result["ordered_outcome_change"] == {
        "improved": 1,
        "unchanged": 1,
        "degraded": 1,
    }
    assert result["self_qa"]["both_scores"]["n"] == 1
    assert result["self_qa"]["both_scores"]["mean_delta"] == 1
    assert result["latency_ms"]["all_tasks"]["mean_delta"] == -50


def test_exact_two_sided_binomial_matches_4_vs_11():
    value = analysis._exact_two_sided_binomial(4, 11)
    assert round(value, 6) == 0.118469


def test_pinned_sources_and_bootstrap_constants_are_frozen():
    assert "47aed3c0b13eaa90eb02803bec9d5c75e559f416" in analysis.DEFAULT_EXP026
    assert "830d476f24da9d842882ac69ed785c546b362a91" in analysis.DEFAULT_EXP027
    assert analysis.EXPECTED_EXP026_SHA256 == (
        "ec93ad9ae193734bfc7cb78c1879328ef8a1ff6777af80dcd57b38acc5a0fa3a"
    )
    assert analysis.EXPECTED_EXP027_SHA256 == (
        "783183dbc9d8aae3811b164c40ee8681998c005ebc8b63a8fcd943c829f72a80"
    )
    assert analysis.BOOTSTRAP_SEED == 20260714
    assert analysis.BOOTSTRAP_RESAMPLES == 10_000
    assert analysis.HTTP_TIMEOUT_SECONDS == 30


def test_bootstrap_interval_is_deterministic():
    assert analysis._bootstrap_mean_ci([1.0, 1.0, -1.0, 2.0]) == [-0.5, 1.75]


def test_load_json_rejects_hash_drift(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"ok": true}', encoding="utf-8")

    try:
        analysis._load_json(source, expected_sha256="0" * 64)
    except ValueError as exc:
        assert "SHA-256 mismatch" in str(exc)
    else:
        raise AssertionError("hash drift must fail")


def test_duplicate_selection_ids_fail():
    report = _report({"a": "success"}, [5], [100])
    selection = {"groups": {"group_a": ["a"], "group_b": ["a"], "group_c": []}}

    try:
        analysis.analyze(report, report, selection)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate selected IDs must fail")