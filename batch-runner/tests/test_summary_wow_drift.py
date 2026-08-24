"""Tests for the ``summary.wow`` drift diagnosis.

The finding these pin down is narrow and worth stating plainly: two grade files
published in 2026-06 no longer recompute, and the whole difference is one
counting rule. ``#69`` taught the summariser to skip items the judge never
managed to score. Both files were graded before that, so their stored rates
count 255 judge errors as though the model had failed them.

``test_deleting_the_gate_reproduces_both_published_files`` is the load-bearing
one. It does not merely observe a difference; it reconstructs the pre-``#69``
loop and shows it lands on all five published rates exactly, which is what
turns "these numbers disagree" into "these numbers were produced by a rule we
can name". A companion test proves that reconstruction is not vacuous by
showing it disagrees with the current summariser on the same input.

``test_the_official_sol_220_run_still_reproduces`` is the one that decides
whether any of this matters to a reader of the dashboard. It does not: the
badged run was graded after the change and recomputes to the digit.

The corpus-wide guard is ``test_no_published_payload_has_unexplained_drift``.
Two known causes, four payloads under the second, nothing left over. If a
future summariser change lands without a note, that test is where it surfaces.
"""

import copy
import json
from pathlib import Path

import pytest

from scripts import summary_wow_drift as swd


REPO_ROOT = Path(__file__).resolve().parents[2]
GRADES = REPO_ROOT / "data" / "grades"

# Graded 2026-06-10 and 2026-06-04 respectively, both before `6ad789a` (#69).
TOOLS = (
    "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json"
)
MINI = (
    "exp003_GPT52Chat_baseline_runner_exec"
    "__judge_gpt-5_4-mini__rubric_v2_tools_mini.json"
)

# The sol-220 run badged OFFICIAL, matched by its source-hash segment because
# the full stem also carries config, rubric and inference hashes.
OFFICIAL_SRC = "src_1c967673eb8081a6"

# Left column is what the file says; right column is what today's summariser
# makes of the same items. Transcribed, not computed, so that a change to
# either side has to be argued for rather than absorbed.
DRIFT = {
    TOOLS: {
        "rubric_item_coverage_avg": (0.4232, 0.4338),
        "critical_item_pass_rate": (0.501, 0.485),
    },
    MINI: {
        "rubric_item_coverage_avg": (0.4533, 0.4646),
        "critical_item_pass_rate": (0.528, 0.5128),
    },
}

# Both files were graded against the same rubric by two different judges, so
# the items the gate removes are identical in each: 255 judge errors, of which
# 15 are critical. None of the 255 is a `pass`, which is why the coverage
# numerator does not move and only its denominator does.
EXCLUDED_ITEMS = 255
EXCLUDED_CRITICAL = 15


def _load(name: str) -> dict:
    return json.loads((GRADES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def payloads() -> dict[str, dict]:
    return {name: _load(name) for name in DRIFT}


@pytest.mark.parametrize("name", sorted(DRIFT))
def test_the_two_2026_06_runs_drift_in_exactly_two_rates(payloads, name):
    published = payloads[name]["summary"]["wow"]
    current = swd._compute_summary(payloads[name]["tasks"])["wow"]

    drifting = {
        key: (published[key], current[key])
        for key in swd.WOW_RATES
        if published[key] != current[key]
    }
    assert drifting == DRIFT[name]

    # The other three are untouched, and say so explicitly: a reader should
    # not have to infer which rates are safe to quote from a list of which
    # are not.
    for key in set(swd.WOW_RATES) - set(DRIFT[name]):
        assert published[key] == current[key], key


@pytest.mark.parametrize("name", sorted(DRIFT))
def test_deleting_the_gate_reproduces_both_published_files(payloads, name):
    legacy = swd.pre_69_wow(payloads[name]["tasks"])
    published = payloads[name]["summary"]["wow"]

    assert {key: legacy[key] for key in swd.WOW_RATES} == {
        key: published[key] for key in swd.WOW_RATES
    }


@pytest.mark.parametrize("name", sorted(DRIFT))
def test_the_reconstructed_rule_is_not_the_current_one(payloads, name):
    """Guard against `pre_69_wow` quietly becoming a copy of the summariser.

    If it ever did, the test above would still pass on files that reproduce
    and would stop meaning anything on files that do not.
    """
    legacy = swd.pre_69_wow(payloads[name]["tasks"])
    current = swd._compute_summary(payloads[name]["tasks"])["wow"]

    assert {key for key in swd.WOW_RATES if legacy[key] != current[key]} == set(
        DRIFT[name]
    )


@pytest.mark.parametrize("name", sorted(DRIFT))
def test_the_gate_moves_the_two_rates_in_opposite_directions(payloads, name):
    """Coverage rises, critical falls, and the counters say why.

    Both denominators shrink. Coverage keeps its whole numerator, because a
    judge error is never a `pass`, so the rate goes up. The critical numerator
    loses every item the denominator does -- all 15 excluded critical items
    are flagged `model_did_right` -- so that rate goes down instead.
    """
    published = payloads[name]["summary"]["wow"]
    current = swd._compute_summary(payloads[name]["tasks"])["wow"]

    assert current["rubric_item_coverage_avg"] > published["rubric_item_coverage_avg"]
    assert current["critical_item_pass_rate"] < published["critical_item_pass_rate"]

    excluded = [
        item
        for item in swd.iter_items(payloads[name]["tasks"])
        if item.get("score_excluded")
    ]
    assert len(excluded) == EXCLUDED_ITEMS
    assert {item["verdict"] for item in excluded} == {"judge_error"}
    assert not [item for item in excluded if item["verdict"] == "pass"]

    critical = [
        item for item in excluded if swd._is_critical_item(item.get("max_score"))
    ]
    assert len(critical) == EXCLUDED_CRITICAL
    assert all(item["model_did_right"] for item in critical)


def test_the_official_sol_220_run_still_reproduces():
    matches = [p for p in GRADES.glob(f"*{OFFICIAL_SRC}*.json")]
    assert matches, f"no payload matching {OFFICIAL_SRC}"

    for path in matches:
        payload = json.loads(path.read_text(encoding="utf-8"))
        published = payload["summary"]["wow"]
        current = swd._compute_summary(payload["tasks"])["wow"]
        assert {key: published[key] for key in swd.WOW_RATES} == {
            key: current[key] for key in swd.WOW_RATES
        }, path.name


def test_no_published_payload_has_unexplained_drift():
    findings = [
        swd.classify(path, json.loads(path.read_text(encoding="utf-8")))
        for path in swd.collect([GRADES])
    ]
    findings = [f for f in findings if f is not None]
    assert findings, "no grade payloads found"

    unexplained = [f.path.name for f in findings if not f.explained]
    assert unexplained == []

    by_cause = {}
    for finding in findings:
        by_cause.setdefault(finding.cause, []).append(finding.path.name)
    assert sorted(by_cause[swd.CAUSE_PRE_69]) == sorted(DRIFT)
    # The four pre-sign-aware `__v1.json` files. Counted separately on purpose:
    # their drift has a different cause and must not be added to the gate's.
    assert len(by_cause[swd.CAUSE_PRE_100]) == 4


def test_an_unexplained_drift_is_reported_rather_than_absorbed(payloads, tmp_path):
    payload = copy.deepcopy(payloads[TOOLS])
    payload["summary"]["wow"]["judge_pass_rate"] = 0.1234

    finding = swd.classify(tmp_path / "made_up.json", payload)

    assert finding.cause == swd.CAUSE_UNKNOWN
    assert "judge_pass_rate" in finding.drift


def test_diagnosing_never_edits_the_payload(payloads):
    """The whole exercise is read-only; nothing here may touch a grade file."""
    for name, payload in payloads.items():
        before = json.dumps(payload, sort_keys=True)
        swd.classify(GRADES / name, payload)
        swd.pre_69_wow(payload["tasks"])
        assert json.dumps(payload, sort_keys=True) == before, name
