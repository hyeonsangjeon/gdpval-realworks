"""Offline dispatch/build bindings. No credential, vendor host or network use."""

import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest
import yaml

import ghcp_ahp_load_smoke as load
import ghcp_ahp_metadata_broker as broker
import ghcp_ahp_patched_runtime as runtime
import ghcp_ahp_prewarm_zero_turn as prewarm
import ghcp_ahp_probe as probe
from .test_ghcp_ahp_patched_runtime import build_value
from .test_ghcp_ahp_probe import backend_probe_fixture

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {"github_run_id": "9002", "github_run_attempt": "1", "github_sha": "a" * 40}

# Exact, single-match inverse of this scope's additions. Historical expected
# workflow SHA values are not changed and every original byte is still hashed.
PERMISSIONS = """    permissions:
      contents: read
      actions: read # Exact same-HEAD green push artifact, never a branch-latest build.
"""
PREPARATION_STEPS = '''      - name: Fetch the unique green push build for this exact dispatch SHA
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: hyeonsangjeon/gdpval-realworks
        run: |
          set -euo pipefail
          umask 077
          build_dir="$RUNNER_TEMP/ghcp-zero-turn/build"
          mkdir -p "$build_dir"
          gh api "repos/$GH_REPO/actions/workflows/ghcp-ahp-patched-runtime-tests.yml/runs?event=push&status=success&head_sha=$GITHUB_SHA&per_page=100" > "$build_dir/runs.json"
          build_run="$(python -B batch-runner/ghcp_ahp_prewarm_zero_turn.py select \\
            --runs "$build_dir/runs.json" --output "$build_dir/selected.json")"
          gh run download "$build_run" --repo "$GH_REPO" \\
            --name "ghcp-patched-load-payload-$build_run-1" --dir "$build_dir/transfer"
      - name: Stage the tested config-before-prewarm build for zero-turn only
        run: |
          set -euo pipefail
          umask 077
          python -B batch-runner/ghcp_ahp_prewarm_zero_turn.py prepare \\
            --transfer "$RUNNER_TEMP/ghcp-zero-turn/build/transfer" \\
            --build "$RUNNER_TEMP/ghcp-zero-turn/build/selected.json" \\
            --base "$RUNNER_TEMP/ghcp-zero-turn/prepared" \\
            --output "$RUNNER_TEMP/ghcp-zero-turn/prewarm" \\
            --evidence "$RUNNER_TEMP/ghcp-zero-turn/evidence"
'''
AUTH_OLD = '              --prepared "$RUNNER_TEMP/ghcp-zero-turn/prepared" \\\n'
AUTH_NEW = ('              --prepared "$RUNNER_TEMP/ghcp-zero-turn/prewarm/runtime" \\\n'
            '              --prewarm-zero-turn-preparation "$RUNNER_TEMP/ghcp-zero-turn/prewarm/preparation.json" \\\n')


def restore_workflow(text):
    for current, original in ((PERMISSIONS, ""), (PREPARATION_STEPS, ""), (AUTH_NEW, AUTH_OLD)):
        assert text.count(current) == 1, "prewarm workflow inverse must match exactly once"
        text = text.replace(current, original, 1)
    return text


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline prewarm contract crossed an execution/network boundary")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def build():
    return {"id": 9001, "run_attempt": 1, "head_sha": IDENTITY["github_sha"], "head_branch": prewarm.BRANCH,
            "path": prewarm.BUILD_WORKFLOW, "event": "push", "status": "completed", "conclusion": "success",
            "repository": prewarm.REPOSITORY, "head_repository": prewarm.REPOSITORY}


def response():
    row = build()
    for key in ("repository", "head_repository"):
        row[key] = {"full_name": row[key]}
    return {"total_count": 1, "workflow_runs": [row]}


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setattr(probe, "require_runner", lambda: dict(IDENTITY))
    values = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": prewarm.REPOSITORY,
              "GITHUB_REF": "refs/heads/" + prewarm.BRANCH,
              "GITHUB_WORKFLOW_REF": prewarm.REPOSITORY + "/" + prewarm.WORKFLOW + "@refs/heads/" + prewarm.BRANCH,
              "GITHUB_WORKFLOW_SHA": IDENTITY["github_sha"], "GHCP_AUTHENTICATED_ZERO_TURN": "true",
              "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def test_scope_is_exact_and_generic_activation_stays_locked(context):
    assert prewarm.context() == prewarm.context(running=True) == IDENTITY
    assert prewarm.select_build(response(), IDENTITY) == build()
    with pytest.raises(probe.Refused, match="patched_runtime_activation_pending_owner"):
        runtime.require_activation()


@pytest.mark.parametrize("key", ["GITHUB_EVENT_NAME", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_WORKFLOW_REF",
                               "GITHUB_WORKFLOW_SHA", "GHCP_AUTHENTICATED_ZERO_TURN", "GHCP_PAID_EXECUTION", "GHCP_CONNECTION_ONLY"])
def test_changed_or_absent_dispatch_scope_is_refused(context, monkeypatch, key):
    monkeypatch.setenv(key, "different")
    with pytest.raises(probe.Refused):
        prewarm.context(running=True)
    monkeypatch.delenv(key)
    with pytest.raises(probe.Refused):
        prewarm.context(running=True)


@pytest.mark.parametrize("key,value", [("id", True), ("id", 0), ("id", 9002), ("run_attempt", True), ("run_attempt", 2),
    ("head_sha", "b" * 40), ("head_branch", "main"), ("path", "wrong.yml"), ("event", "workflow_dispatch"),
    ("status", "in_progress"), ("conclusion", "failure"), ("repository", "other/repo"), ("head_repository", "fork/repo")])
def test_build_origin_status_attempt_and_same_sha_are_not_optional(key, value):
    row = build()
    row[key] = value
    with pytest.raises(probe.Refused):
        prewarm.validate_build(row, IDENTITY)


@pytest.mark.parametrize("value", [{}, None, [], {"total_count": 0, "workflow_runs": []},
    {"total_count": True, "workflow_runs": [response()["workflow_runs"][0]]},
    {"total_count": 2, "workflow_runs": [response()["workflow_runs"][0]] * 2},
    {"total_count": 1, "workflow_runs": []}])
def test_build_selection_has_no_latest_or_ambiguous_fallback(value):
    with pytest.raises(probe.Refused):
        prewarm.select_build(value, IDENTITY)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(runtime._encoded(value) + b"\n")


@pytest.fixture
def staged(tmp_path, monkeypatch):
    # Inert bytes only, with the fixture baseline explicitly injected. All
    # validation, hashes, patch-set checks and negative mutations are real.
    data = b"inert fixture: no host or SDK"
    sha = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(load, "BASELINE_SHA256", sha)
    monkeypatch.setattr(load, "BASELINE_BYTES", len(data))
    output, evidence = tmp_path / "prewarm", tmp_path / "evidence"
    root = output / "runtime"
    bundle = root / "cli-data/servers" / ("Stable-" + runtime.PIN) / "server" / runtime.RUNTIME_RELATIVE
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(data)
    receipt = output / "payload/build-receipt.json"
    write(receipt, build_value(sha))
    receipt_sha = probe.digest(receipt)
    manifest_path = output / "payload/inputs/server-bundle-manifest.json"
    manifest = {"build_receipt": build_value(sha), "build_receipt_sha256": receipt_sha}
    write(manifest_path, manifest)
    # Manifest validation itself has a separate exhaustive suite. Here the real
    # on-disk equality/digest/receipt validation boundary is under test.
    monkeypatch.setattr(load, "checked_manifest", lambda path: runtime._json(runtime._read(path)))
    transfer = {"schema": "ghcp-load-smoke-transfer-v1", "identity": prewarm.validate_build(build(), IDENTITY),
        "upstream_commit": runtime.PIN, "patch_sha256": runtime.PATCH_SHA256,
        "bundle_sha256": sha, "bundle_bytes": len(data), "bundle_manifest_sha256": probe.digest(manifest_path),
        "build_receipt_sha256": receipt_sha, "payload_sha256": "d" * 64, "payload_bytes": 100,
        "server_archive_sha256": load.bundle.base_manifest()["artifacts"]["server"]["sha256"],
        "synthetic": True, "model_free": True, "execution_allowed": False}
    write(output / "payload/prepared.json", {"transfer": transfer})
    record = prewarm.preparation_record(IDENTITY, build(), transfer)
    path = output / "preparation.json"
    write(path, record)
    write(evidence / "prewarm-zero-turn-preparation.json", record)
    return {"path": path, "root": root, "evidence": evidence, "record": record, "bundle": bundle,
            "receipt": receipt, "manifest": manifest_path, "request": {"path": receipt, "sha256": receipt_sha}}


def verify(tree):
    return prewarm.verify_preparation(tree["path"], tree["root"], tree["evidence"], IDENTITY)


def test_preparation_is_bound_but_is_neither_loaded_nor_applied_evidence(staged):
    assert verify(staged) == staged["request"]
    row = staged["record"]
    assert row["execution_allowed"] is row["admission_allowed"] is False
    assert row["runtime_load_status"] == "staged_not_loaded" and row["applied_policy"] == "not_reported"
    assert "codex.permissionsPreset" not in row["requested_policy"]


@pytest.mark.parametrize("key,value", [("consumer", {**IDENTITY, "github_sha": "b" * 40}), ("execution_allowed", True),
    ("admission_allowed", True), ("scope", "paid"), ("patched_ghcp", False), ("patch_sha256", "b" * 64),
    ("bundle_sha256", "c" * 64), ("bundle_bytes", 1), ("bundle_manifest_sha256", "c" * 64),
    ("build_receipt_sha256", "c" * 64), ("requested_policy", {}), ("requested_model", {}),
    ("requested_native_launch_args", []), ("runtime_load_status", "measured"), ("applied_policy", "matched"),
    ("limits", {"turns": 1}), ("upstream_commit", "b" * 40)])
def test_preparation_omissions_and_forged_claims_refuse_even_if_both_copies_agree(staged, key, value):
    for omit in (False, True):
        changed = copy.deepcopy(staged["record"])
        if omit:
            del changed[key]
        else:
            changed[key] = value
        write(staged["path"], changed)
        write(staged["evidence"] / "prewarm-zero-turn-preparation.json", changed)
        with pytest.raises(probe.Refused):
            verify(staged)


@pytest.mark.parametrize("target", ["bundle", "receipt", "manifest"])
def test_one_byte_changed_build_component_is_refused(staged, target):
    path = staged[target]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(probe.Refused):
        verify(staged)


def test_artifact_copy_and_runtime_root_cannot_be_substituted(staged):
    write(staged["evidence"] / "prewarm-zero-turn-preparation.json", {})
    with pytest.raises(probe.Refused, match="prewarm_preparation_contract_refused"):
        verify(staged)
    with pytest.raises(probe.Refused, match="prewarm_runtime_path_refused"):
        prewarm.verify_preparation(staged["path"], staged["root"] / "other", staged["evidence"], IDENTITY)


@pytest.mark.parametrize("changed", [{"authenticated_zero_turn": False}, {"session_policy": False},
    {"capability_only": True}, {"metadata_socket": None}, {"metadata_socket": Path("relative")},
    {"authenticated_zero_turn": 1}])
def test_preparation_can_only_enter_a_brokered_authenticated_zero_turn(staged, context, changed):
    options = dict(authenticated_zero_turn=True, session_policy=True, capability_only=False,
                   metadata_socket=staged["root"].parent / "broker.sock")
    options.update(changed)
    with pytest.raises(probe.Refused, match="prewarm_requires_brokered_zero_turn"):
        prewarm.require_run(staged["path"], staged["root"], staged["evidence"], **options)


def test_broker_carries_nonsecret_identity_and_keeps_all_kernel_and_zero_turn_guards(staged, context):
    command, environment = broker.isolated_command(staged["root"], staged["evidence"], Path("/tmp/fake.sock"),
        prewarm_preparation=staged["path"])
    assert command[-2:] == ["--prewarm-zero-turn-preparation", str(staged["path"])]
    for name in ("GITHUB_REF", "GITHUB_REPOSITORY", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA"):
        assert environment[name] == context[name]
    assert "GH_TOKEN" not in environment and "GITHUB_TOKEN" not in environment
    for flag in ("--net", "--pid", "--kill-child=KILL", "--no-new-privs", "--bounding-set=-all",
                 "--authenticated-zero-turn", "--metadata-socket"):
        assert flag in command


def test_cli_refuses_wrong_mode_before_credential_or_vendor_access(staged, context, monkeypatch, capsys):
    monkeypatch.setattr(probe, "load_manifest", lambda: pytest.fail("refusal was too late"))
    assert probe.main(["prepare", "--prepared", str(staged["root"]), "--evidence", str(staged["evidence"]),
        "--prewarm-zero-turn-preparation", str(staged["path"])]) == 2
    assert "prewarm_requires_brokered_zero_turn" in capsys.readouterr().out


def test_original_generic_patched_entry_remains_locked_even_with_new_option(staged, context):
    with pytest.raises(probe.Refused, match="patched_runtime_activation_pending_owner"):
        probe.run_probe({}, staged["root"], staged["evidence"], "", "", session_policy=True,
                        patched_request=staged["request"], prewarm_preparation=staged["path"])


def test_missing_live_load_proof_refuses_before_authenticate_or_session(backend_probe_fixture, monkeypatch, tmp_path):
    # Fake host/socket peer only. The new entry never stubs require_activation:
    # its paid/public path stays locked; loaded-byte proof is still mandatory.
    request = {"path": tmp_path / "absent-build.json", "sha256": "a" * 64}
    monkeypatch.setattr(prewarm, "require_run", lambda *args, **kwargs: request)
    monkeypatch.setattr(prewarm.zero, "require_context", lambda: None)
    original = probe.run_probe
    monkeypatch.setattr(probe, "run_probe", lambda *args, **kwargs: original(*args, **kwargs,
        prewarm_preparation=tmp_path / "preparation.json", metadata_socket=tmp_path / "broker.sock"))
    monkeypatch.setattr(runtime, "verify_live_ready", lambda *args: (_ for _ in ()).throw(
        probe.Refused("synthetic_live_load_missing")))
    monkeypatch.setattr(probe, "Rpc", lambda *args, **kwargs: pytest.fail("authentication preceded live load proof"))
    receipt, calls, _ = backend_probe_fixture(authenticated_zero_turn=True)
    assert calls["exit_code"] == 2 and calls["stops"] >= 1
    assert "synthetic_live_load_missing" in receipt["reason_codes"]
    assert receipt["session_create_requests"] == 0 and not receipt.get("rpc_sent")
    assert receipt["execution_allowed"] is False and receipt["runtime_load_status"] != "measured"


def test_bad_preparation_refuses_in_the_broker_before_reading_credentials(staged, context, monkeypatch, capsys):
    write(staged["path"], {})
    monkeypatch.setattr(broker, "require_runner", lambda: dict(IDENTITY))
    monkeypatch.setattr(broker, "validate_credential", lambda *args: pytest.fail("credential read after invalid preparation"))
    assert broker.main(["--prepared", str(staged["root"]), "--evidence", str(staged["evidence"]),
        "--prewarm-zero-turn-preparation", str(staged["path"])]) == 2
    assert "prewarm_build_record_refused" in capsys.readouterr().out


def test_select_cli_emits_only_the_validated_run_id(context, tmp_path, capsys):
    path, selected = tmp_path / "runs.json", tmp_path / "selected.json"
    write(path, response())
    assert prewarm.main(["select", "--runs", str(path), "--output", str(selected)]) == 0
    assert capsys.readouterr().out == "9001\n"
    assert json.loads(selected.read_text()) == build()


def test_local_prepare_cli_refuses_before_reading_artifacts(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(probe, "require_runner", lambda: (_ for _ in ()).throw(probe.Refused("synthetic_not_actions")))
    monkeypatch.setattr(runtime, "_read", lambda *args: pytest.fail("NAS artifact preparation attempted"))
    assert prewarm.main(["select", "--runs", str(tmp_path / "absent"), "--output", str(tmp_path / "never")]) == 2
    assert "synthetic_not_actions" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_prepare_stages_a_distinct_tree_and_keeps_producer_and_consumer_bindings(staged, monkeypatch, tmp_path):
    selected = tmp_path / "selected.json"
    write(selected, build())
    transfer = json.loads((staged["root"].parent / "payload/prepared.json").read_text())["transfer"]
    calls = []
    def payload(directory, output, identity):
        calls.append(("payload", directory, output, identity))
        return {"transfer": transfer}
    monkeypatch.setattr(load, "prepare_payload", payload)
    monkeypatch.setattr(runtime, "stage_runtime", lambda *args: calls.append(("stage", *args)))
    monkeypatch.setattr(prewarm, "verify_preparation", lambda *args: calls.append(("verify", *args)))
    output, evidence, base = tmp_path / "next", tmp_path / "next-evidence", tmp_path / "original"
    evidence.mkdir()
    result = prewarm.prepare(tmp_path / "downloaded", selected, base, output, evidence, IDENTITY)
    assert calls[0] == ("payload", tmp_path / "downloaded", output / "payload", prewarm.validate_build(build(), IDENTITY))
    assert calls[1] == ("stage", base, output / "runtime", output / "payload/inputs/agentHostMain.js",
                       {"path": output / "payload/build-receipt.json", "sha256": transfer["build_receipt_sha256"]})
    assert calls[2] == ("verify", output / "preparation.json", output / "runtime", evidence, IDENTITY)
    assert result["consumer"] == IDENTITY and result["producer"] == build()
    assert result["execution_allowed"] is False and result["applied_policy"] == "not_reported"
    assert (output / "preparation.json").read_bytes() == (evidence / "prewarm-zero-turn-preparation.json").read_bytes()


def test_workflow_build_and_secret_scopes_and_historical_bytes():
    text = (ROOT / prewarm.WORKFLOW).read_text()
    assert hashlib.sha256(restore_workflow(text).encode()).hexdigest() == "bf862ff51934fbff926340b0b52fa30e75ce175357816199d8c3526730d92b1d"
    value = yaml.load(text, Loader=yaml.BaseLoader)
    job = value["jobs"]["ahp-zero-turn"]
    assert job["permissions"] == {"contents": "read", "actions": "read"}
    assert job["runs-on"] == "ubuntu-24.04" and job["environment"] == "ghcp-sol-gate"
    assert job["needs"] == "offline-ci" and int(job["timeout-minutes"]) <= 10
    steps = job["steps"]
    download = next(step for step in steps if step.get("name", "").startswith("Fetch the unique"))
    stage = next(step for step in steps if step.get("name", "").startswith("Stage the tested"))
    auth = next(step for step in steps if step.get("env", {}).get("GHCP_AUTHENTICATED_ZERO_TURN") == "true")
    assert steps.index(download) < steps.index(stage) < steps.index(auth)
    assert download["env"] == {"GH_TOKEN": "${{ github.token }}", "GH_REPO": prewarm.REPOSITORY}
    assert "secrets." not in yaml.dump(download) + yaml.dump(stage)
    assert sum("secrets." in yaml.dump(step) for step in steps) == 1
    assert "--prewarm-zero-turn-preparation" in auth["run"] and "--prepared" in auth["run"]
    assert "ghcp_ahp_metadata_broker.py" in auth["run"] and "$COPILOT_GITHUB_TOKEN" not in auth["run"]
    assert "--patched-build-receipt" not in text


@pytest.mark.parametrize("fragment", [PERMISSIONS, PREPARATION_STEPS, AUTH_NEW])
def test_workflow_inverse_refuses_missing_duplicate_or_changed_overlay(fragment):
    text = (ROOT / prewarm.WORKFLOW).read_text()
    for changed in (text.replace(fragment, "", 1), text + fragment, text.replace(fragment, fragment + "# changed\n", 1).replace(fragment, fragment[:-1], 1)):
        with pytest.raises(AssertionError, match="inverse must match exactly once"):
            restore_workflow(changed)
