"""Serial dispatch/capture state machine with durable, at-most-once intents.

No default gh executor, credentials, private-store reader or judge. CLI commands
are read-only plan/status. An approved launcher must explicitly supply the four
ports; tests supply fake gh, approved synthetic requests, storage and a grader.
An ambiguous dispatch or grading response is NOT permission to repeat it.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

from core.agentic_v2_preregistration import seal
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_schedule as schedule
import gpt54_time_budget_v2_ci as v2
import gpt54_time_budget_codex_ci as codex
from gpt54_time_budget_v2_observation import validate_runner_image
from gpt54_v2_grading_input import _object, _read_bytes
from gpt54_prepared_input_attestation import _identity

FORMAT = "gpt54-time-budget-serial-controller-v1"
REPO = v2.REPOSITORY
ARTIFACTS = {"sandbox_v2": "time-budget-first-v2-completion", "codex": "time-budget-first-codex-completion"}
RUN_FIELDS = "databaseId,number,attempt,event,headSha,headBranch,status,conclusion,workflowName"
DISCOVERY_SECONDS = 120
WAIT_SECONDS = 7200  # Confirmation bound only: never cancels/renews generation.
STATES = {"pending", "dispatch_intent", "observing", "captured", "prepare_intent", "prepared",
          "grade_intent", "complete", "missing"}


class ControllerRefused(ValueError):
    """Fixed reason only, never gh/provider output, auth values or task bodies."""


def require(value, reason):
    if not value:
        raise ControllerRefused(reason)


def same(actual, expected, reason):
    require(registration._canonical_json(actual) == registration._canonical_json(expected), reason)


def document(path, identity=None):
    data = _read_bytes(Path(path), **(identity or {}))
    require(len(data) <= 8 * 1024 * 1024, "document_size_limit")
    return json.loads(data, object_pairs_hook=_object)


def atomic_json(path, value):
    data = (registration._canonical_json(value) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".ledger-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        require(not path.is_symlink(), "ledger_symlink")
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)  # Only this function's new, exact temp file.


class Ledger:
    def __init__(self, directory, header, order):
        self.root, self.header, self.order = Path(directory), header, order
        require(self.root.is_absolute(), "absolute_ledger_required")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.root.lstat()
        require(self.root.resolve() == self.root and stat.S_ISDIR(info.st_mode)
                and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700, "owned_ledger_required")
        self.path = self.root / "ledger.json"

    @contextmanager
    def lock(self):
        fd = os.open(self.root / "controller.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ControllerRefused("controller_already_running") from None
            yield
        finally:
            os.close(fd)

    def read(self):
        if not self.path.exists():
            state = {"header": self.header, "runner_image": None, "stopped": None,
                     "rows": [{"binding": item.binding(self.order), "state": "pending", "issue": None,
                               "score_pct": None} for item in self.order]}
            self.write(state)
        packet = document(self.path)
        same(packet["sha256"], seal(packet["state"]), "ledger_digest_changed")
        state = packet["state"]
        same(state["header"], self.header, "ledger_source_or_contract_changed")
        require(len(state["rows"]) == 20, "ledger_scope_changed")
        active_seen = False
        for item, row in zip(self.order, state["rows"]):
            same(row["binding"], item.binding(self.order), "ledger_schedule_changed")
            require(row["state"] in STATES, "ledger_state_invalid")
            if active_seen:
                require(row["state"] == "pending", "ledger_order_changed")
            active_seen |= row["state"] != "complete"
        ids = [row["run_id"] for row in state["rows"] if "run_id" in row]
        require(len(ids) == len(set(ids)), "run_reused_for_another_observation")
        return state

    def write(self, state):
        atomic_json(self.path, {"state": state, "sha256": seal(state)})


@dataclass(frozen=True)
class ApprovedRequest:
    data: bytes
    sha256: str  # Independent supplied approval, not calculated by dispatch.


class DirectoryRequests:
    """JIT owner-issued NN.json plus independently supplied NN.sha256. No templating."""
    def __init__(self, directory):
        self.directory = Path(directory)

    def __call__(self, item, previous):
        del previous  # An approved new request must already bind its actual parent.
        base = self.directory / f"{item.sequence:02d}"
        return ApprovedRequest(_read_bytes(base.with_suffix(".json")),
                               _read_bytes(base.with_suffix(".sha256")).decode("ascii").strip())


def checked_request(approved, item, source, plan, now, previous):
    require(type(approved) is ApprovedRequest and 0 < len(approved.data) <= v2.MAX_REQUEST_BYTES
            and _identity(approved.data)["sha256"] == approved.sha256, "independent_request_digest_required")
    request = json.loads(approved.data, object_pairs_hook=_object)
    module = v2 if item.condition == "sandbox_v2" else codex
    keys = {"format", "purpose", "source", "frozen_source", "input_registration", "cell", "ci",
            "registration_sha256", "dataset_sha256", "paths", "storage", "not_before_unix", "expires_unix"}
    same(sorted(request), sorted(keys | ({"step0"} if item.condition == "codex" else set())), "request_schema")
    same(request["source"], source, "request_source_mismatch")
    same(request["cell"], item.cell, "request_schedule_mismatch")
    same(request["format"], module.REQUEST_VERSION, "request_format_mismatch")
    same(request["purpose"], (codex.PURPOSE if item.condition == "codex" else
        "execute_and_privately_retain_first_v2_observation"), "request_purpose_mismatch")
    same(request["registration_sha256"], seal(plan), "request_registration_mismatch")
    same(request["dataset_sha256"], seal(plan["shared"]["dataset"]), "request_dataset_mismatch")
    same(request["frozen_source"], {"sha": registration.ACCEPTED_BASE_SHA, "tree": registration.ACCEPTED_BASE_TREE},
         "request_frozen_source_mismatch")
    same(request["input_registration"], {"source_sha": registration.ACCEPTED_BASE_SHA,
         "source_tree": registration.ACCEPTED_BASE_TREE, "path": registration.SOURCE_PROFILE,
         "sha256": registration.SOURCE_PROFILE_SHA256}, "request_input_registration_mismatch")
    ci = request["ci"]
    require(type(ci.get("run_number")) is int and ci["run_number"] > 0, "request_run_number_required")
    same(ci, {"repository": REPO, "workflow": schedule.WORKFLOWS[item.condition], "ref": "refs/heads/main",
        "actor": v2.OWNER, "job": "observation", "attempt": 1, "run_number": ci["run_number"],
        "runner": "ubuntu-24.04", "runner_os": "Linux", "runner_arch": "X64"}, "request_ci_mismatch")
    begin, end = request["not_before_unix"], request["expires_unix"]
    require(type(begin) is int and type(end) is int and begin <= now < end and 0 < end - begin <= 2700,
            "request_window_invalid")
    require(type(request["storage"]) is dict and
            re.fullmatch(r"[0-9a-f]{40}", request["storage"].get("expected_parent", "")), "request_parent_required")
    if previous is not None:
        same(request["storage"]["expected_parent"], previous["output_commit"], "request_parent_chain_mismatch")
    return request  # Workflow still performs the full R/F/input/path/remote-CAS admission.


class GhCommands:
    """Exact gh argv, supplied executor only. It never searches for credentials."""
    def __init__(self, execute, *, synthetic=False):
        self.execute, self.synthetic = execute, synthetic

    def _call(self, argv, *, payload=None, json_result=False):
        completed = self.execute(["gh", *argv, "--repo", REPO], input=payload, timeout=60)
        require(completed.returncode == 0, "gh_command_unconfirmed")
        if not json_result:
            return None
        require(len(completed.stdout) <= 1024 * 1024, "gh_response_size_limit")
        return json.loads(completed.stdout, object_pairs_hook=_object)

    def runs(self, item):
        return self._call(["run", "list", "--workflow", Path(schedule.WORKFLOWS[item.condition]).name,
                          "--event", "workflow_dispatch", "--branch", "main", "--limit", "100",
                          "--json", RUN_FIELDS], json_result=True)

    def dispatch(self, item, approved, source):
        inputs = {"reviewed_source_sha": source["sha"], "reviewed_source_tree": source["tree"],
                  "request_sha256": approved.sha256, "request_json": approved.data.decode("utf-8")}
        self._call(["workflow", "run", Path(schedule.WORKFLOWS[item.condition]).name, "--ref", "main", "--json"],
                   payload=registration._canonical_json(inputs))

    def view(self, run_id):
        return self._call(["run", "view", str(run_id), "--json", RUN_FIELDS + ",jobs"], json_result=True)

    def download(self, item, run_id, destination):
        self._call(["run", "download", str(run_id), "--name", ARTIFACTS[item.condition], "--dir", str(destination)])


def checked_run(value, row, source, workflow_name, *, jobs=False):
    require(type(value.get("databaseId")) is int and value["databaseId"] > 0, "run_id_invalid")
    for key, expected in {"number": row["request"]["run_number"], "attempt": 1, "event": "workflow_dispatch",
                          "headSha": source["sha"], "headBranch": "main", "workflowName": workflow_name}.items():
        same(value.get(key), expected, "run_identity_mismatch")
    if "run_id" in row:
        same(value["databaseId"], row["run_id"], "run_identity_changed")
    require(value.get("status") in {"queued", "in_progress", "waiting", "pending", "requested", "completed"},
            "run_status_invalid")
    if jobs and value["status"] == "completed":
        require(type(value.get("jobs")) is list and len(value["jobs"]) == 1
                and value["jobs"][0]["name"] == "observation"
                and value["jobs"][0]["status"] == "completed", "observation_job_not_completed")


def checked_completion(path, item, row, source):
    envelope = document(path)
    (v2 if item.condition == "sandbox_v2" else codex).validate_envelope(envelope, expected_cell=item.cell)
    require("runner_image" in envelope, "runner_image_required")
    validate_runner_image(envelope["runner_image"])
    same(envelope["source"], source, "completion_source_mismatch")
    same(envelope["request_sha256"], row["request"]["sha256"], "completion_request_mismatch")
    same(envelope["ci"], {"run_id": str(row["run_id"]), "run_number": row["request"]["run_number"],
                          "job": "observation", "attempt": 1}, "completion_run_mismatch")
    require(envelope["retention"] == "acknowledged" and envelope["result_identity"] is not None
            and envelope["cleanup_complete"] is True and envelope["host_reusable"] is True,
            "capture_or_cleanup_unconfirmed")
    return envelope


class SerialController:
    """advance() performs bounded I/O; waiting returns to its caller, no sleeps.

    requests(item, previous_envelope) supplies independent request approval.
    store(item, envelope) hydrates only the pinned output commit and returns a
    CaptureBundle. pipeline validates/prepares/grades/reads out. None has a live
    default. Lost preparation/grade acknowledgements stop, never adopt/retry.
    """
    def __init__(self, *, plan, source, directory, gh, requests, store, pipeline, clock=time.time):
        import yaml
        import gpt54_time_budget_paired_readout as paired
        self.plan, self.source, self.clock = deepcopy(plan), deepcopy(source), clock
        self.order = paired._schedule(plan)
        require(set(source) == {"sha", "tree"} and all(re.fullmatch(r"[0-9a-f]{40}", v) for v in source.values()),
                "reviewed_source_required")
        self.gh, self.requests, self.store, self.pipeline = gh, requests, store, pipeline
        require(gh.synthetic == pipeline.synthetic, "fixture_live_boundary_mismatch")
        self.names = {condition: yaml.safe_load((registration.ROOT / path).read_bytes())["name"]
                      for condition, path in schedule.WORKFLOWS.items()}
        header = {"format": FORMAT, "source": source, "registration_sha256": seal(plan),
                  "schedule_sha256": self.order[0].binding(self.order)["schedule_sha256"],
                  "synthetic": gh.synthetic, "max_observations": 20, "concurrency": 1}
        self.ledger = Ledger(directory, header, self.order)

    def _admit(self):
        if not self.gh.synthetic:
            require(self.pipeline.live_execution_supported, "common_live_grading_admission_not_implemented")
            from core.runner_environment import require_execution
            observed = require_execution()
            require(observed["github_hosted"] and observed["os_version_id"] == "24.04", "hosted_controller_required")
            self.pipeline.admit()

    def _stop(self, state, row, reason):
        row.update(state="missing", issue=reason, score_pct=None)
        state["stopped"] = {"observation_id": row["binding"]["observation_id"], "reason": reason}
        self.ledger.write(state)
        return "stopped"

    def advance(self):
        self._admit()
        with self.ledger.lock():
            state = self.ledger.read()
            if state["stopped"] is not None:
                return "stopped"
            index = next((i for i, row in enumerate(state["rows"]) if row["state"] != "complete"), None)
            # Re-validate completed evidence; a local ledger is not hash authority.
            try:
                if index is None or state["rows"][index]["state"] == "pending":
                    self.pipeline.recheck(self.plan, state["rows"])
            except Exception:
                row = next((r for r in state["rows"] if r["state"] != "complete"), state["rows"][-1])
                return self._stop(state, row, "checkpoint_evidence_changed")
            if index is None:
                return "complete"
            row, item = state["rows"][index], self.order[index]
            try:
                return self._advance(state, row, item, index)
            except ControllerRefused as error:
                return self._stop(state, row, str(error))
            except Exception:
                # Never persist raw transport/provider errors. A potentially
                # sent dispatch retains its intent for discovery, not replay.
                if row["state"] == "dispatch_intent":
                    return "waiting"
                return self._stop(state, row, "external_step_unconfirmed")

    def _advance(self, state, row, item, index):
        now = self.clock()
        if row["state"] == "pending":
            previous = None if index == 0 else state["rows"][index - 1]["completion"]
            approved = self.requests(item, deepcopy(previous))
            request = checked_request(approved, item, self.source, self.plan, now, previous)
            existing = self.gh.runs(item)
            require(type(existing) is list, "run_list_schema")
            require(not any(run["number"] == request["ci"]["run_number"] for run in existing), "run_preexists_dispatch")
            row.update(state="dispatch_intent", request={"sha256": approved.sha256, "size": len(approved.data),
                "run_number": request["ci"]["run_number"]}, discovery_deadline=now + DISCOVERY_SECONDS,
                wait_deadline=now + WAIT_SECONDS)
            self.ledger.write(state)  # Write-ahead before a potentially paid side effect.
            # Request/discovery I/O and intent fsync cannot extend approval.
            require(request["not_before_unix"] <= self.clock() < request["expires_unix"],
                    "request_window_invalid")
            try:
                self.gh.dispatch(item, approved, self.source)
            except Exception:
                return "waiting"  # Lost response cannot authorize another dispatch.
            return "progress"
        if row["state"] == "dispatch_intent":
            runs = self.gh.runs(item)
            require(type(runs) is list, "run_list_schema")
            found = [run for run in runs if run["number"] == row["request"]["run_number"]]
            require(len(found) <= 1, "duplicate_run")
            if not found:
                if now >= row["discovery_deadline"]:
                    return self._stop(state, row, "dispatch_confirmation_unknown")
                return "waiting"
            checked_run(found[0], row, self.source, self.names[item.condition])
            require(found[0]["databaseId"] not in {r.get("run_id") for r in state["rows"]}, "run_reused")
            row.update(state="observing", run_id=found[0]["databaseId"])
            self.ledger.write(state)
            return "progress"
        if row["state"] == "observing":
            run = self.gh.view(row["run_id"])
            checked_run(run, row, self.source, self.names[item.condition], jobs=True)
            if run["status"] != "completed":
                if now >= row["wait_deadline"]:
                    return self._stop(state, row, "run_still_active_at_wait_limit")
                return "waiting"
            if run["conclusion"] != "success" or run["jobs"][0]["conclusion"] != "success":
                return self._stop(state, row, "workflow_failed_or_timed_out")
            # Downloads may be repeated after interruption, into a new owned
            # directory. Dispatch/grading may not. Never overwrite an artifact.
            download = Path(tempfile.mkdtemp(prefix=f"download-{item.sequence:02d}-", dir=self.ledger.root))
            self.gh.download(item, row["run_id"], download)
            require(sorted(path.relative_to(download).as_posix() for path in download.rglob("*") if path.is_file())
                    == ["completion.json"] and not any(p.is_symlink() for p in download.rglob("*")),
                    "completion_artifact_inventory")
            envelope = checked_completion(download / "completion.json", item, row, self.source)
            if state["runner_image"] is not None:
                same(envelope["runner_image"], state["runner_image"], "runner_image_mixed")
            bundle = self.store(item, deepcopy(envelope))
            capture = self.pipeline.validate_capture(self.plan, item, envelope, bundle)
            row.update(state="captured", completion=envelope, capture=capture)
            state["runner_image"] = envelope["runner_image"]
            self.ledger.write(state)
            return "progress"
        if row["state"] in {"prepare_intent", "grade_intent"}:
            return self._stop(state, row, "preparation_or_grade_acknowledgement_unknown")
        if row["state"] == "captured":
            row["state"] = "prepare_intent"
            self.ledger.write(state)
            row["prepared"] = self.pipeline.prepare(self.plan, item, row["capture"])
            row["state"] = "prepared"
            self.ledger.write(state)
            return "progress"
        require(row["state"] == "prepared", "controller_state_invalid")
        row["state"] = "grade_intent"
        self.ledger.write(state)
        row["grade"] = self.pipeline.grade(self.plan, item, row["prepared"])
        if row["grade"].get("continuation_allowed") is False:
            reason = row["grade"].get("stop_reason")
            require(reason in {"grading_cleanup_unconfirmed", "grading_cancelled"}, "grading_stop_reason_invalid")
            return self._stop(state, row, reason)
        row["state"] = "complete"
        self.ledger.write(state)
        return "progress"

    def run(self, *, max_steps=200):
        require(type(max_steps) is int and 0 < max_steps <= 1000, "bounded_controller_steps_required")
        for _ in range(max_steps):
            result = self.advance()
            if result != "progress":
                return result
        return "paused"  # No sleep/background work; a caller schedules the next poll.

    def readout(self):
        with self.ledger.lock():
            state = self.ledger.read()
            value = self.pipeline.readout(self.plan, state["rows"])
            scores = {entry["observation_id"]: entry["score_pct"] for entry in value.get("observations", [])}
            value["controller"] = {"source": self.source, "stopped": state["stopped"],
                "observations": [{"observation_id": r["binding"]["observation_id"], "state": r["state"],
                    "issue": r["issue"], "score_pct": scores.get(r["binding"]["observation_id"])}
                    for r in state["rows"]]}
            return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "status"))
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(registration._canonical_json(schedule.job_descriptors(registration.load_registration())))
    else:
        require(args.ledger is not None, "ledger_required")
        packet = document(args.ledger / "ledger.json")
        same(packet["sha256"], seal(packet["state"]), "ledger_digest_changed")
        print(registration._canonical_json(packet["state"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
