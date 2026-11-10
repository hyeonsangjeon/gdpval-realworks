"""Pure patched hook, inert sessions and the existing exact patch hashes only."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

import ghcp_ahp_patched_runtime as runtime
import ghcp_ahp_thread_policy as policy

DRIVER = Path(__file__).with_name("fixtures") / "ghcp_ahp_prewarm_order_fixture.cjs"


def run(scenario):
    node = shutil.which("node")
    assert node, "Node is required for the pure ready-hook fixture; never skip"
    return subprocess.run([node, str(DRIVER), str(runtime.PATCH), scenario],
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, capture_output=True, text=True, timeout=15)


def test_config_publication_precedes_exactly_one_prewarm_per_session():
    completed = run("normal")
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["synthetic"] is True and result["execution_allowed"] is result["sdk_or_host_executed"] is False
    assert result["config_before_prewarm"] is True and result["native_requests"] == 0
    assert result["lifecycle_refusals"] == 6
    events = result["events"]
    assert [row["kind"] for row in events] == ["config_published", "prewarm"] * 2
    assert [row["chat"] for row in events] == ["first", "first", "second", "second"]
    assert events[1]["policy"] == events[3]["policy"] == policy.POLICY


@pytest.mark.parametrize("mutation", ["without-config-guard", "without-one-shot"])
def test_fixture_detects_missing_order_or_one_shot_guard(mutation):
    completed = run(mutation)
    assert completed.returncode != 0
    assert "AssertionError" in completed.stderr


def test_order_patch_and_followup_remain_exact_and_move_the_call_not_the_policy():
    value = runtime.verify_patch_set()
    assert value["upstream_commit"] == runtime.PIN
    text = runtime.PATCH.read_text()
    assert text.count('-\t\t\t\t\tthis._schedulePrewarm(session);') == 1
    assert text.count('+\t\t\tsession.prewarmScheduled = true;') == 1
    assert text.count('+\t\t\tthis._schedulePrewarm(session);') == 1
    assert 'if (isIdleProvisional && !isEphemeral && !this._sessionResidency.isBeingDisposed(session))' in text
    for key in ('approvalPolicy', 'sandboxMode', 'networkAccessEnabled', 'webSearchMode', 'modelReasoningEffort'):
        assert key not in text  # The patch orders publication; it never substitutes policy values.
