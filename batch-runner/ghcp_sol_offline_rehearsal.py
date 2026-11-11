"""Fixed-five fixture rehearsal through real client/capture/Step8 validators.

Only in-memory AHP I/O and owned synthetic files. Never launch/authenticate a
host, call a model/grader, download task data, or open the paid execution path.
This separate entry point does not impersonate an eligible Actions runner.
"""

from __future__ import annotations

import argparse
import base64
import copy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import re
from unittest.mock import patch

import yaml

import ghcp_ahp_client as client
import ghcp_ahp_first_turn as first_turn
import ghcp_ahp_offline_fixture as fixture_runtime
import ghcp_sol_actions_gate as gate
import ghcp_sol_grader_contract as bridge

FLAGS = {"synthetic": True, "model_free": True, "execution_allowed": False, "grading_allowed": False}
LIMITS = {"turns": 64, "tool_calls": 32, "seconds": 1200}
CAPTURE_FILES = ("client-capture.json", "transcript.jsonl", "tool-calls.jsonl", "commands.jsonl",
                 "first-turn-wire.jsonl", "input-file-hashes.json", "output-file-hashes.json", "exit-status.json")
MAX_FIXTURE_BYTES = 2 * 1024 * 1024
MAX_STEPS = 1024
Refused = bridge.Refused


def require(value, code):
    if not value:
        raise Refused(code)


def encoded(value):
    return bridge._bytes(value)


def identity(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def read(path):
    return bridge._read(path, client.MAX_CAPTURE_BYTES)


def read_json(path):
    return bridge._json(read(path))


def write(path, raw):
    bridge._path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("xb") as stream:
        stream.write(raw)


def write_json(path, value):
    write(path, encoded(value) + b"\n")


def jsonl(rows):
    return b"".join(encoded(row) + b"\n" for row in rows)


def tagged_rows(rows):
    return [{**FLAGS, "value": row} for row in rows]


def relative_name(name):
    require(type(name) is str and re.fullmatch(r"[A-Za-z0-9_./-]{1,256}", name) is not None
            and all(part and not part.startswith(".") for part in name.split("/"))
            and Path(name).name not in {"auth.json", "hosts.yml", "credentials", "token", "stored_tokens"},
            "fixture_path_refused")
    return name


def validate_fixture(value):
    require(type(value) is dict and set(value) == {"schema", "synthetic", "model_free", "execution_allowed", "limits", "tasks"}
            and value["schema"] == "ghcp-fixed-five-offline-fixture-v1"
            and value["synthetic"] is True and value["model_free"] is True and value["execution_allowed"] is False
            and first_turn.same(value["limits"], LIMITS), "fixture_contract_refused")
    require(len(encoded(value)) <= MAX_FIXTURE_BYTES, "fixture_size_refused")
    require(type(value["tasks"]) is list and all(type(task) is dict for task in value["tasks"])
            and [task.get("task_id") for task in value["tasks"]] == list(gate.fixed_task_ids()), "fixture_task_set_refused")
    for task in value["tasks"]:
        require(set(task) == {"task_id", "inputs", "first_turn_records", "steps"}, "fixture_task_contract_refused")
        require(type(task["inputs"]) is dict and bool(task["inputs"]), "fixture_inputs_refused")
        for name, text in task["inputs"].items():
            require(relative_name(name).startswith("reference_files/") and type(text) is str, "fixture_inputs_refused")
        require(type(task["first_turn_records"]) is list and len(task["first_turn_records"]) <= 64
                and all(type(row) is dict and row.get("synthetic") is True for row in task["first_turn_records"]),
                "fixture_native_records_refused")
        require(type(task["steps"]) is list and 0 < len(task["steps"]) <= MAX_STEPS, "fixture_steps_refused")
        for step in task["steps"]:
            require(type(step) is dict, "fixture_step_refused")
            kind = step.get("kind")
            keys = {"begin": {"kind", "turn_id", "text"}, "event": {"kind", "action"},
                    "write": {"kind", "path", "content"}, "advance": {"kind", "seconds"}}
            require(kind in keys and set(step) == keys[kind], "fixture_step_refused")
            if kind == "begin":
                require(type(step["turn_id"]) is str and type(step["text"]) is str, "fixture_step_refused")
            elif kind == "event":
                require(type(step["action"]) is dict and type(step["action"].get("type")) is str, "fixture_step_refused")
            elif kind == "write":
                relative_name(step["path"])
                require(not step["path"].startswith("reference_files/") and type(step["content"]) is str,
                        "fixture_output_refused")
            else:
                require(type(step["seconds"]) in {int, float} and 0 <= step["seconds"] <= 1201,
                        "fixture_clock_refused")
    return value


def _decoded_files(capture):
    require(type(capture.get("generated_files")) is list, "rehearsal_generated_files_missing")
    files = {}
    for item in capture["generated_files"]:
        name = relative_name(item["path"])
        require(name not in files and item["redacted"] is False, "rehearsal_generated_file_refused")
        if item["encoding"] == "utf-8":
            raw = item["content"].encode("utf-8")
        else:
            require(item["encoding"] == "base64", "rehearsal_generated_file_refused")
            raw = base64.b64decode(item["content"], validate=True)
        require(identity(raw) == {"sha256": item["source_sha256"], "size": item["source_bytes"]},
                "rehearsal_generated_file_hash_mismatch")
        files[name] = raw
    return files


def _capture_components(capture, baseline, records, steps_done, steps_total):
    # No .get(..., []) defaults: a missing capture is a failure, not empty output.
    require(type(capture) is dict and {"transcript", "tool_calls", "commands", "generated_files", "cleanup",
            "counts", "limits", "status", "reason_codes", "first_turn_attestation", "workspace_collected"} <= capture.keys(),
            "rehearsal_capture_incomplete")
    transcript = capture["transcript"]
    require(type(transcript) is dict and {"wire", "snapshots", "history", "text"} <= transcript.keys()
            and all(type(transcript[key]) is list for key in ("wire", "snapshots", "history", "text"))
            and bool(transcript["wire"]) and type(capture["tool_calls"]) is list and type(capture["commands"]) is list
            and capture["workspace_collected"] is True and capture["cleanup"]["host_terminated"] is True
            and capture["gate_ready"] is False and capture["status"] in {"completed", "stopped"}
            and bool(capture["reason_codes"]) and first_turn.same(capture["limits"], LIMITS), "rehearsal_capture_incomplete")
    counts = capture["counts"]
    require(type(counts) is dict and set(counts) == {"admitted_or_observed_turns", "observed_turns", "observed_tool_calls",
            "model_requests", "premium_requests"}
            and all(type(counts[key]) is int and 0 <= counts[key] <= bound for key, bound in
                    (("admitted_or_observed_turns", 64), ("observed_turns", 64), ("observed_tool_calls", 32)))
            and counts["model_requests"] == counts["premium_requests"] == "not_reported"
            and first_turn.same(capture["overshoot_boundary"], client.OVERSHOOT), "rehearsal_capture_counts_refused")
    require(first_turn.same(capture["first_turn_attestation"], first_turn.assess(records)),
            "rehearsal_first_turn_evidence_mismatch")
    if capture["status"] == "completed":
        first_turn.require_report(capture["first_turn_attestation"])
        require(capture["reason_codes"] == ["completed"], "rehearsal_exit_status_mismatch")
    require(not any(row["direction"] == "client_work" and row["after_stop"] for row in transcript["wire"]),
            "rehearsal_work_after_stop")
    files = _decoded_files(capture)
    exit_status = {**FLAGS, "status": capture["status"], "exit_status": 0 if capture["status"] == "completed" else 2,
                   "reason_codes": capture["reason_codes"], "cleanup": capture["cleanup"],
                   "fixture_steps_delivered": steps_done, "fixture_steps_total": steps_total,
                   "native_process_started": False}
    return {
        "transcript.jsonl": jsonl(tagged_rows(transcript["wire"])),
        "tool-calls.jsonl": jsonl(tagged_rows(capture["tool_calls"])),
        "commands.jsonl": jsonl(tagged_rows(capture["commands"])),
        "first-turn-wire.jsonl": jsonl(tagged_rows(records)),
        "input-file-hashes.json": encoded({**FLAGS, "files": baseline}) + b"\n",
        "output-file-hashes.json": encoded({**FLAGS, "files": {name: identity(raw) for name, raw in files.items()}}) + b"\n",
        "exit-status.json": encoded(exit_status) + b"\n",
        **{"files/" + name: raw for name, raw in files.items()},
    }


def run_task(root, task):
    # Reuse only the pure staging function, never paid/auth/input-download entry
    # points. The caller's effects guard remains active throughout this import.
    from ghcp_sol_paid_gate import stage_task
    work, captures = root / "workspace", root / "capture"
    work.mkdir(parents=True, mode=0o700)
    captures.mkdir(mode=0o700)
    stage_task(work, {"references": {name: text.encode() for name, text in task["inputs"].items()}})
    baseline = {name: identity(raw) for name, raw in client.workspace_files(work).items()}
    clock, port = fixture_runtime.Clock(), fixture_runtime.Port(task["first_turn_records"])
    session = client.SessionClient(port, "ahp-session:/" + task["task_id"], "ahp-chat:/" + task["task_id"],
        authenticated=True, limits=client.Limits(), clock=clock)
    # authenticated=True is strictly a fixture precondition. No authenticate RPC
    # or credential is sent; all I/O goes to Port.sent in this Python process.
    sequence = steps_done = 0
    for step in task["steps"]:
        if not session.tick():
            break
        steps_done += 1
        if step["kind"] == "begin":
            session.send_turn(step["turn_id"], step["text"])
        elif step["kind"] == "event":
            sequence += 1
            session.accept({"jsonrpc": "2.0", "method": "action", "params": {"channel": session.chat,
                "serverSeq": sequence, "origin": None, "action": copy.deepcopy(step["action"])}})
        elif step["kind"] == "advance":
            clock.value += step["seconds"]
            session.tick()
        else:
            # Fixture materialization only. No shell, tool, SDK or model runs.
            require(bool(session.active), "fixture_write_without_active_turn")
            write(work / step["path"], step["content"].encode())
    session.finish()
    capture = session.capture(captures / "client-capture.json", workspace=work,
                              baseline={name: row["sha256"] for name, row in baseline.items()})
    components = _capture_components(capture, baseline, port.observed_records, steps_done, len(task["steps"]))
    observed_files = client.workspace_files(work)
    require(all(identity(observed_files[name]) == expected for name, expected in baseline.items()),
            "rehearsal_input_changed")
    require(_decoded_files(capture) == {name: raw for name, raw in observed_files.items() if name not in baseline},
            "rehearsal_generated_capture_incomplete")
    for name, raw in components.items():
        write(captures / name, raw)
    manifest = {"client-capture.json": identity(read(captures / "client-capture.json")),
                **{name: identity(raw) for name, raw in components.items()}}
    record = {**FLAGS, "schema": "ghcp-fixed-five-fixture-capture-v1", "task_id": task["task_id"],
              "runtime": "in_memory_fixture_only", "limits": LIMITS, "files": manifest,
              "fixture_steps_delivered": steps_done, "fixture_steps_total": len(task["steps"])}
    write_json(captures / "capture.json", record)
    return validate_capture(root, task["task_id"])


def validate_capture(root, task_id):
    captures = root / "capture"
    record = read_json(captures / "capture.json")
    require(record.get("schema") == "ghcp-fixed-five-fixture-capture-v1" and record.get("task_id") == task_id
            and all(record.get(key) is value for key, value in FLAGS.items())
            and record.get("runtime") == "in_memory_fixture_only" and first_turn.same(record.get("limits"), LIMITS),
            "rehearsal_capture_contract_refused")
    require(type(record.get("files")) is dict and set(CAPTURE_FILES) <= record["files"].keys(),
            "rehearsal_capture_incomplete")
    actual = client.workspace_files(captures)
    require(set(actual) == set(record["files"]) | {"capture.json"}, "rehearsal_capture_inventory_mismatch")
    for name, digest in record["files"].items():
        relative_name(name)
        require(identity(actual[name]) == digest, "rehearsal_capture_hash_mismatch")
    capture = bridge._json(actual["client-capture.json"])
    baseline = bridge._json(actual["input-file-hashes.json"])["files"]
    native = [bridge._json(line) for line in actual["first-turn-wire.jsonl"].splitlines()]
    require(all(all(row.get(key) is value for key, value in FLAGS.items()) for row in native),
            "rehearsal_native_synthetic_marker_missing")
    records = [row["value"] for row in native]
    require(all(row.get("synthetic") is True for row in records), "rehearsal_native_synthetic_marker_missing")
    expected = _capture_components(capture, baseline, records, record["fixture_steps_delivered"], record["fixture_steps_total"])
    require(set(record["files"]) == set(expected) | {"client-capture.json"}
            and all(actual[name] == raw for name, raw in expected.items()), "rehearsal_capture_component_mismatch")
    current = client.workspace_files(root / "workspace")
    generated = _decoded_files(capture)
    require(set(current) == set(baseline) | set(generated)
            and all(identity(current[name]) == info for name, info in baseline.items())
            and all(current[name] == raw for name, raw in generated.items()), "rehearsal_workspace_capture_mismatch")
    return capture


def _check_step8(output, payload):
    """Use unchanged readers, paths, policy and live-refusal checks, not a judge."""
    plan = bridge.contract.load_plan(bridge.contract.ROOT / bridge.contract.SOURCE_PROFILE_PATH)
    require(bridge.contract.inspect_plan(plan)["configuration_valid"] is True, "pinned_grader_contract_refused")
    template = bridge.ROOT / plan["grading"]["template"]
    template_raw = read(template)
    require(identity(template_raw)["sha256"] == plan["source_pins"][plan["grading"]["template"]], "grader_template_drift")
    require(identity(read(bridge.ROOT / "batch-runner/core/inference_manifest.py"))["sha256"] == bridge.INPUT_CONTRACT_SHA256,
            "step8_input_contract_drift")
    import step8_grade as step8
    require(Path(step8.__file__).resolve() == bridge.ROOT / "batch-runner/step8_grade.py", "step8_module_identity_refused")
    config = yaml.safe_load(template_raw)
    with ExitStack() as blocked:
        for owner, name in ((step8.Grader, "__init__"), (step8.RubricLoader, "__init__"),
                            (step8, "main"), (step8, "preflight_routes")):
            blocked.enter_context(patch.object(owner, name, bridge._deny))
        with bridge._cwd(bridge.ROOT / "batch-runner"):
            step8.validate_grading_config(config)
        with bridge._cwd(output):
            loaded = step8.load_local_inference_results()
            require(first_turn.same(loaded, payload), "step8_manifest_roundtrip_mismatch")
            rows = step8.filter_tasks(loaded, None, 0)
            require([row["task_id"] for row in rows] == list(gate.TASK_IDS), "step8_task_set_mismatch")
            require(first_turn.same(step8.validate_local_deliverables(rows, output / "workspace/upload"), rows),
                    "step8_deliverable_tree_mismatch")
            for row in rows:
                require(Path(step8.resolve_deliverable_dir(row)) == output / "workspace/upload/deliverable_files" / row["task_id"],
                        "step8_deliverable_tree_mismatch")
            for check in (
                lambda: step8.resolve_source_inference_identity(loaded, config["schema_version"]),
                lambda: step8._validate_pinned_rerun_identity(config, experiment_id=payload["experiment_id"],
                    task_ids=list(gate.TASK_IDS), rubric_commit_sha=config["rubric"]["revision"], inference_revision=None),
            ):
                try:
                    check()
                except ValueError:
                    pass  # The existing live identity MUST refuse synthetic input.
                else:
                    raise Refused("fixture_must_not_admit_live_grading")
    return {"readers_and_policy_verified": True, "grader_instantiated": False, "rubric_loaded": False,
            "template_sha256": identity(template_raw)["sha256"], "input_contract_sha256": bridge.INPUT_CONTRACT_SHA256,
            "live_refusals_observed": ["source_inference_identity_missing", "full220_rerun_identity_not_reusable"]}


@bridge._no_effects()
def prepare_grader_input(root):
    # Re-read all five captures before publishing any success row. No cached
    # in-memory result can hide a missing/tampered file or failed first turn.
    captures = {task_id: validate_capture(root / "tasks" / task_id, task_id) for task_id in gate.fixed_task_ids()}
    output = root / "grader-input"
    output.mkdir(mode=0o700)
    payload = {**FLAGS, "record_version": "ghcp-step8-fixture-rehearsal-v1", "experiment_id": "ghcp_sol_offline_rehearsal",
               "inference_performed": False, "source_repo_id": None, "source_revision": None, "results": []}
    for task_id, capture in captures.items():
        completed = capture["status"] == "completed"
        folder = output / "workspace/upload/deliverable_files" / task_id
        folder.mkdir(parents=True, mode=0o700)
        files = _decoded_files(capture) if completed else {}
        text = "\n".join(row["text"] for row in capture["transcript"]["text"] if row["part_id"] == "answer") if completed else ""
        require(not completed or bool(text or files), "fixture_deliverable_missing")
        paths = []
        for name, raw in files.items():
            write(folder / name, raw)
            paths.append(f"deliverable_files/{task_id}/{name}")
        payload["results"].append({**FLAGS, "task_id": task_id, "status": "success" if completed else "error",
            "content": text or None, "deliverable_text": text, "deliverable_files": paths, "usage": None,
            "error": None if completed else capture["reason_codes"], "fixture_status": capture["status"],
            "fixture_capture_sha256": identity(read(root / "tasks" / task_id / "capture/capture.json"))["sha256"]})
    write_json(output / bridge.MANIFEST, payload)
    checks = _check_step8(output, payload)
    require(read(output / bridge.MANIFEST) == encoded(payload) + b"\n", "step8_manifest_changed")
    for task_id in captures:
        require(first_turn.same(validate_capture(root / "tasks" / task_id, task_id), captures[task_id]), "rehearsal_capture_changed")
    report = {**FLAGS, "schema": "ghcp-offline-grader-contract-v1", "step8_layout_valid": True, "ready_for_grading": False,
              "gate5_passed": False, "grade": None, "model_calls": 0, "judge_calls": 0,
              "manifest": bridge.MANIFEST, "manifest_identity": identity(read(output / bridge.MANIFEST)), "checks": checks}
    write_json(output / bridge.REPORT, report)
    return report


def run_rehearsal(output, *, fixture=None):
    report = {**FLAGS, "schema": "ghcp-fixed-five-offline-rehearsal-v1", "fixture_pipeline_passed": False,
              "gate5_passed": False, "ready_for_grading": False, "exit_status": 2, "reason_codes": [], "tasks": [],
              "actual_calls": {"authentication": 0, "model_turns": 0, "capi_inference": 0, "external_http": 0, "judge": 0},
              "limits": LIMITS, "cap_scope": "client_admission_in_fixture_not_server_or_billing_limit",
              "overshoot_boundary": dict(client.OVERSHOOT), "grader_contract": None}
    owned = False
    try:
        with bridge._no_effects():
            fixture = validate_fixture(copy.deepcopy(fixture if fixture is not None else fixture_runtime.fixed_five()))
            bridge._path(output)
            require(not output.exists() and not output.is_relative_to(bridge.ROOT) and not bridge.ROOT.is_relative_to(output),
                    "rehearsal_output_reuse_or_checkout_refused")
            output.mkdir(mode=0o700)
            owned = True
            write_json(output / "fixture.json", fixture)
            report["fixture_identity"] = identity(read(output / "fixture.json"))
            capture_failed = False
            for task in fixture["tasks"]:
                result = {**FLAGS, "task_id": task["task_id"], "capture_valid": False}
                try:
                    capture = run_task(output / "tasks" / task["task_id"], task)
                    result.update(capture_valid=True, status=capture["status"], reason_codes=capture["reason_codes"],
                        counts=capture["counts"], first_turn_attestation=capture["first_turn_attestation"],
                        capture=f"tasks/{task['task_id']}/capture/capture.json")
                except (Refused, client.Refused, OSError, ValueError, KeyError, TypeError) as error:
                    capture_failed = True
                    result.update(status="capture_refused", reason_codes=[str(error) if isinstance(error, (Refused, client.Refused))
                                                                         else "rehearsal_capture_refused"])
                report["tasks"].append(result)
            require(not capture_failed, "rehearsal_capture_incomplete")
            report["grader_contract"] = prepare_grader_input(output)
            require(identity(read(output / "fixture.json")) == report["fixture_identity"], "rehearsal_fixture_changed")
            require(all(row["status"] == "completed" for row in report["tasks"]), "rehearsal_task_stopped")
            report.update(fixture_pipeline_passed=True, exit_status=0)
    except (Refused, client.Refused) as error:
        report["reason_codes"] = [str(error)]
    except bridge.EffectsRefused:
        report["reason_codes"] = ["offline_effect_refused"]
    except Exception:
        report["reason_codes"] = ["offline_rehearsal_refused"]
    if owned:
        write_json(output / "rehearsal.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_rehearsal(args.output)
    print(json.dumps({key: result[key] for key in ("synthetic", "execution_allowed", "fixture_pipeline_passed", "exit_status", "reason_codes")}))
    return result["exit_status"]


if __name__ == "__main__":
    raise SystemExit(main())
