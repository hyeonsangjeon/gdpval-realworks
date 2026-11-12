"""Pinned pure policy functions + fake native stdio. No vendor runtime on NAS."""

import copy
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import subprocess

import pytest

import ghcp_ahp_thread_policy as policy
import ghcp_ahp_wire_capture as wire

FIXTURES = Path(__file__).with_name("fixtures")
DRIVER = FIXTURES / "ghcp_ahp_permission_normalization_fixture.cjs"
SOURCE = FIXTURES / "ghcp_ahp_permission_sources.json"
SOURCE_SHA256 = "82f174deb64825fb97c9a5ef04b4e81bad1e7d0b991ff3dc8435e70f4061dd51"
PIN = "2c33b50b16c472efe58357d1d2a8a5414bc23fbf"
APPROVALS = ("never", "on-request", "untrusted")
SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
PRESETS = ("default", "auto-review", "full-access")
AXES = list(itertools.product(APPROVALS, SANDBOXES, (False, True)))
PRESET_AXES = list(itertools.product(PRESETS, APPROVALS, SANDBOXES, (False, True)))
BAD_APPROVALS = ("on-failure", "UNTRUSTED", True, 7)
BAD_SANDBOXES = ("read_only", "readonly", None, True)
BAD_PRESETS = ("read-only", "unknown", True, 1)


def config(approval="untrusted", sandbox="read-only", network=False):
    return {"codex.approvalPolicy": approval, "codex.sandboxMode": sandbox,
            "codex.networkAccessEnabled": network, "codex.webSearchMode": "disabled",
            "codex.modelReasoningEffort": "max"}


def cases():
    result = []
    for approval, sandbox, network in AXES:
        result.append({"id": f"raw-{approval}-{sandbox}-{network}", "config": config(approval, sandbox, network), "guard": True})
    for preset, approval, sandbox, network in PRESET_AXES:
        result.append({"id": f"preset-{preset}-{approval}-{sandbox}-{network}",
                       "config": {**config(approval, sandbox, network), "codex.permissionsPreset": preset}})
    for index, value in enumerate((None, {}, {"unrelated": True})):
        result.append({"id": f"empty-{index}", "config": value, "guard": True})
    for index, value in enumerate(BAD_APPROVALS):
        result.append({"id": f"bad-approval-{index}", "config": config(approval=value)})
    for index, value in enumerate(BAD_SANDBOXES):
        result.append({"id": f"bad-sandbox-{index}", "config": config(sandbox=value)})
    for index, value in enumerate(BAD_PRESETS):
        result.append({"id": f"bad-preset-{index}", "config": {**config(), "codex.permissionsPreset": value}})
    for reply in (None, "matching", "changed"):
        result.append({"id": f"reply-{reply}", "config": config(), "guard": True, "reply": reply})
    return result


CASES = cases()


def run_fixture(rows, source=SOURCE):
    node = shutil.which("node")
    assert node, "Node with built-in TypeScript stripping is required; never skip"
    return subprocess.run([node, str(DRIVER), str(source)], input=json.dumps(rows), text=True,
                          env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                          capture_output=True, timeout=15)


@pytest.fixture(scope="module")
def result():
    completed = run_fixture(CASES)
    assert completed.returncode == 0, completed.stderr
    value = json.loads(completed.stdout)
    assert value["synthetic"] is True and value["execution_allowed"] is False
    assert value["sdk_or_host_executed"] is False
    assert value["source_sha256"] == SOURCE_SHA256 and value["source_commit"] == PIN
    assert len(value["rows"]) == len(CASES) == 90
    return {row["id"]: row for row in value["rows"]}


def test_excerpts_have_exact_pinned_source_and_quote_provenance():
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256
    value = json.loads(raw)
    assert value["vscode_commit"] == PIN and value["codex_sdk_version"] == "0.163.0"
    assert value["source_archive_sha256"] == "cb7fb5b3b219585a63ec8e3dbc66bab135d2fe900b0541e73862da5302c24206"
    expected = {"common": "d70a1746711f32fa6090bf5165c6928ae16d9340cd9c02ee04134d15fb582e67",
                "resolution": "774874473761ec258abd38ea2eaeafe457457eaaf93af344c004d874d0c6092d",
                "profiles": "94be5055cc9a02764be49abae6129d05b9f83384a9834be913d72278582f2b62"}
    assert {item["name"]: item["sha256"] for item in value["files"]} == expected
    for item in value["files"]:
        for fragment in item["fragments"]:
            assert hashlib.sha256(fragment["text"].encode()).hexdigest() == fragment["sha256"]
            assert len(fragment["text"].splitlines()) == fragment["last_line"] - fragment["first_line"] + 1


@pytest.mark.parametrize("approval,sandbox,network", AXES)
def test_raw_read_only_axes_survive_but_other_sandboxes_snap_to_presets(result, approval, sandbox, network):
    row = result[f"raw-{approval}-{sandbox}-{network}"]
    expected_approval = approval if sandbox == "read-only" else "never" if sandbox == "danger-full-access" else "on-request"
    assert row["resolved"] == {"approvalPolicy": expected_approval, "sandboxMode": sandbox, "approvalsReviewer": "user"}
    if sandbox == "read-only":
        assert row["migrated"] == {"codex.approvalPolicy": approval, "codex.sandboxMode": "read-only"}
        assert row["permissions"] == "vscode-workspace-read-only"  # Network flag cannot open this profile.
    else:
        assert row["migrated"] == {"codex.permissionsPreset": "full-access" if sandbox == "danger-full-access" else "default"}
        assert row["permissions"] == (":danger-full-access" if sandbox == "danger-full-access" else
                                       "vscode-workspace-network" if network else "vscode-workspace")


@pytest.mark.parametrize("preset,approval,sandbox,network", PRESET_AXES)
def test_explicit_presets_take_precedence_even_over_conflicting_read_only_axes(result, preset, approval, sandbox, network):
    row = result[f"preset-{preset}-{approval}-{sandbox}-{network}"]
    assert row["migrated"] == {"codex.permissionsPreset": preset}
    assert row["resolved"] == {"approvalPolicy": "never" if preset == "full-access" else "on-request",
        "sandboxMode": "danger-full-access" if preset == "full-access" else "workspace-write",
        "approvalsReviewer": "auto_review" if preset == "auto-review" else "user"}
    assert row["permissions"] == (":danger-full-access" if preset == "full-access" else
                                   "vscode-workspace-network" if network else "vscode-workspace")


@pytest.mark.parametrize("case_id", [row["id"] for row in CASES])
def test_permission_migration_is_idempotent_and_never_claims_native_acceptance(result, case_id):
    row = result[case_id]
    assert row["migratedAgain"] == row["migrated"]
    assert row["synthetic"] is True and row["execution_allowed"] is False
    assert row["native_acceptance_observed"] is False


@pytest.mark.parametrize("index", range(len(BAD_APPROVALS)))
def test_unsupported_approval_values_are_not_new_aliases(result, index):
    assert result[f"bad-approval-{index}"]["resolved"] == {
        "approvalPolicy": "on-request", "sandboxMode": "read-only", "approvalsReviewer": "user"}


@pytest.mark.parametrize("index", range(len(BAD_SANDBOXES)))
def test_unsupported_sandbox_values_resolve_to_the_host_default_not_read_only(result, index):
    assert result[f"bad-sandbox-{index}"]["resolved"] == {
        "approvalPolicy": "on-request", "sandboxMode": "workspace-write", "approvalsReviewer": "user"}


@pytest.mark.parametrize("index", range(len(BAD_PRESETS)))
def test_unknown_presets_do_not_become_a_read_only_preset(result, index):
    assert result[f"bad-preset-{index}"]["migrated"] == {
        "codex.approvalPolicy": "untrusted", "codex.sandboxMode": "read-only"}


def test_missing_state_reproduces_the_run_rejection_but_published_raw_policy_does_not(result):
    # This models config visibility, not scheduling or a native SDK response.
    before = result["empty-0"]
    after = result["raw-untrusted-read-only-False"]
    assert before["resolved"] == {"approvalPolicy": "on-request", "sandboxMode": "workspace-write", "approvalsReviewer": "user"}
    assert before["permissions"] == "vscode-workspace"
    assert before["guard"]["writes"] == []
    blocked = [row for row in before["guard"]["records"] if row["kind"] == "blocked"]
    assert len(blocked) == 1
    assert blocked[0]["rejected_fields"] == ["params.approvalPolicy", "params.sandbox/permissions"]
    assert after["resolved"]["approvalPolicy"] == "untrusted"
    assert after["permissions"] == "vscode-workspace-read-only"
    assert after["guard"]["refusal"] is None and len(after["guard"]["writes"]) == 1


@pytest.mark.parametrize("approval,sandbox,network", AXES)
def test_unchanged_native_wire_guard_rejects_all_weaker_normalized_requests(result, approval, sandbox, network):
    row = result[f"raw-{approval}-{sandbox}-{network}"]
    guarded = row["guard"]
    expected = approval == "untrusted" and sandbox == "read-only"
    assert (guarded["refusal"] is None) is expected
    assert len(guarded["writes"]) == int(expected)
    assert guarded["claims"] == int(expected)
    if not expected:
        assert guarded["refusal"] == "session_policy_thread_contract_refused"
    assert "sandbox" not in guarded["request"]["params"]  # Profile and legacy sandbox are exclusive.
    assert guarded["vendor_processes_started"] == guarded["model_requests"] == 0
    assert guarded["execution_allowed"] is False and guarded["synthetic"] is True


def test_linux_read_only_profile_preserves_tmp_write_and_denies_network_by_inheritance(result):
    row = result["raw-untrusted-read-only-False"]
    entries = row["linuxProfileOverrides"]
    assert entries[0] == 'default_permissions="vscode-workspace"'
    assert 'permissions.vscode-runtime={' in entries[1]
    assert '":minimal" = "read"' in entries[1] and '":tmpdir" = "write"' in entries[1]
    assert '":slash_tmp" = "read"' in entries[1] and 'network = { enabled = false }' in entries[1]
    assert entries[2] == 'permissions.vscode-workspace={ extends = "vscode-runtime" }'
    assert entries[3] == 'permissions.vscode-workspace-network={ extends = "vscode-workspace", network = { enabled = true } }'
    assert entries[4] == 'permissions.vscode-workspace-read-only={ extends = "vscode-workspace", filesystem = { ":workspace_roots" = { "." = "read" } } }'
    roots = row["linuxSkillReadOverrides"]["permissions.vscode-workspace.filesystem"]
    assert roots["/fixture/skills"] == "read" and roots[":tmpdir"] == "write"
    assert roots[":workspace_roots"] == {".": "write", ".git": "read", ".agents": "read", ".codex": "read"}


@pytest.mark.parametrize("reply", [None, "matching", "changed"])
def test_synthetic_responses_are_separate_from_requests_and_never_admit_a_live_gate(result, reply):
    row = result[f"reply-{reply}"]
    capture = wire.analyze(row["guard"]["records"], synthetic=True)
    assert capture["synthetic"] is True and capture["admission_allowed"] is False
    assert len(capture["native_requests"]) == 1
    assert len(capture["native_applied_snapshots"]) == (0 if reply is None else 1)
    report = policy.assess(capture, {"createSession": {"result": {"synthetic": True}}})
    assert report["admission_allowed"] is False
    assert report["model_turn_start_requests"] == report["model_turn_events"] == report["capi_requests"] == 0
    assert report["observed"]["approval"] == ("not_reported" if reply is None else "on-request" if reply == "changed" else "untrusted")
    assert report["observed"]["served_model"] == report["observed"]["context_window"] == "not_reported"


@pytest.mark.parametrize("damage", ["byte", "pin", "quote_and_hash"])
def test_changed_source_fixture_is_refused_before_any_source_function_evaluation(tmp_path, damage):
    raw = SOURCE.read_bytes()
    if damage == "byte":
        raw += b" "
    else:
        value = copy.deepcopy(json.loads(raw))
        if damage == "pin":
            value["vscode_commit"] = "0" * 40
        else:
            fragment = value["files"][1]["fragments"][1]
            fragment["text"] = fragment["text"].replace("case 'untrusted':", "case 'unsupported':")
            fragment["sha256"] = hashlib.sha256(fragment["text"].encode()).hexdigest()
        raw = json.dumps(value).encode()
    path = tmp_path / "mutated.json"
    path.write_bytes(raw)
    completed = run_fixture([{"id": "never-evaluated", "config": config()}], path)
    assert completed.returncode == 2 and completed.stdout == ""
    assert completed.stderr == "permission_fixture_refused\n"
