"""One fixed CI cell: private CAS claim, same-host output, terminal confirmation.

No launcher, grading or cross-runner restore. Default is local plan only. The
leader-selected private target is fixed; setup is never called here. A local
one-use reservation is not the remote claim. A lost terminal response stays
unresolved locally; only a separately verified server terminal record can admit
the immediate successor. Ambiguous output publication never qualifies.
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import fcntl
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import sys

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
from core.hf_publication import _PublicationFile, _publication_additions, _remote_download_file
from core.inference_manifest import canonical_deliverable_path

TARGET_SHA256 = ci.STORAGE["repository_name_sha256"]
BOOTSTRAP = ci.STORAGE["bootstrap"]
BRANCH = ci.INFERENCE_BRANCH
CLAIM_FORMAT = "codex-ci-cell-admission-v1"
TERMINAL_FORMAT = "codex-ci-cell-terminal-v1"
ADMISSION_RESERVED = "admission-reserved.json"
ADMISSION_RECEIPT = "admission-receipt.json"
SERVER_OBSERVATION = "predecessor-server-observation.json"
TERMINAL_RESERVED = "terminal-reserved.json"
TERMINAL_RECEIPT = "terminal-receipt.json"
require = output._require


def _encoded(value: dict) -> bytes:
    data = (pilot._canonical_json(value) + "\n").encode()
    require(len(data) <= output.MAX_MANIFEST_BYTES, "retention_record_too_large")
    return data


def _write(path: Path, value: dict) -> None:
    output._write_no_clobber(path, _encoded(value))
    output._fsync_directory(path.parent)


def _read(path: Path) -> dict:
    pilot._regular_private(path)
    return pilot._json_object(output._bytes(path, limit=output.MAX_MANIFEST_BYTES))


def _target() -> str:
    historical = pilot.load_plan(pilot.ROOT / pilot.CODEX_TEMPLATE)["data"]["source"]
    require(type(historical) is str and hashlib.sha256(historical.encode()).hexdigest()
            == output.OUTPUT_TARGET_REPO_SHA256, "registered_output_target_mismatch")
    namespace = output.validate_hf_dataset_repo_id(historical).split("/")[0]
    repo = output.validate_hf_dataset_repo_id(namespace + "/" + output.OUTPUT_SETUP_BASENAME)
    require(hashlib.sha256(repo.encode()).hexdigest() == TARGET_SHA256, "selected_private_target_mismatch")
    return repo


def _paths(cell: dict) -> tuple[str, str, str]:
    require(cell["run_id"] == ci.CAMPAIGN + "__" + cell["cell_id"], "retained_epoch_mismatch")
    prefix = f"cell-claims/{ci.CAMPAIGN}/{cell['cell_id']}"
    return prefix + "/admission.json", prefix + "/terminal.json", f"cell-outputs/{ci.CAMPAIGN}/{cell['cell_id']}"


def _binding(plan: dict, cell: dict, inputs: dict, *, host: dict | None = None,
             run: dict | None = None) -> dict:
    require(plan["run_id"] == ci.CAMPAIGN and cell["run_id"] == ci.CAMPAIGN + "__" + cell["cell_id"],
            "retained_epoch_mismatch")
    ordinal = ci._eligible_ordinal(plan, cell["cell_id"])
    host = plan["ci"]["host"] if host is None else host
    run = {"id": os.environ.get("GITHUB_RUN_ID"), "job": os.environ.get("GITHUB_JOB"),
           "attempt": 1} if run is None else run
    require(type(run) is dict and set(run) == {"id", "job", "attempt"}
            and type(run["id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]) is not None
            and type(run["job"]) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,99}", run["job"]) is not None
            and type(run["attempt"]) is int and run["attempt"] == 1, "ci_run_identity_required")
    require(type(host) is dict and set(host) == {"policy", "instance_sha256", "workflow", "workflow_sha", "run_attempt"}
            and pilot._canonical_json(host["policy"]) == pilot._canonical_json(ci.HOST_POLICY)
            and output._hash(host["instance_sha256"])
            and host["workflow"] == plan["ci"]["host"]["workflow"]
            and host["workflow_sha"] == plan["reviewed_source_sha"]
            and type(host["run_attempt"]) is int and host["run_attempt"] == 1, "claim_host_policy_mismatch")
    # Per-job instance hashes intentionally differ. Reconstruct that writer's
    # own plan binding, never require its raw plan hash to equal the next job's.
    writer_plan = {**plan, "ci": {**plan["ci"], "host": host, "selected_cell_id": cell["cell_id"]}}
    return {"repository_name_sha256": TARGET_SHA256, "campaign_id": ci.CAMPAIGN, "inference_branch": BRANCH,
            "cell_id": cell["cell_id"], "run_id": cell["run_id"], "task_id": cell["task_id"],
            "ordinal": ordinal, "source_sha": plan["reviewed_source_sha"],
            "config_sha256": cell["config_sha256"], "plan_sha256": pilot._digest(writer_plan),
            "order_sha256": pilot._digest(plan["order"]),
            "registration_sha256": plan["ci"]["registration_sha256"],
            "host_policy_sha256": pilot._digest(ci.HOST_POLICY),
            "declared_inputs_sha256": pilot._digest(plan["dataset"]),
            "verified_inputs_sha256": inputs["files_sha256"],
            "source_projection_sha256": inputs["source_projection_sha256"], "host": host, "github_run": run}


def _local(plan: dict, cell: dict, root: Path) -> tuple[dict, Path]:
    require(stat.S_IMODE(root.stat().st_mode) == 0o700, "private_campaign_root_required")
    require(output._checkpoint(root / "plan.json") == plan
            and output._checkpoint(root / "ready.json") == {"plan_sha256": pilot._digest(plan)},
            "retained_plan_mismatch")
    inputs = output._checkpoint(root / "ci-inputs.json")
    require(set(inputs) == {"plan_sha256", "files_sha256", "source_projection_sha256"}
            and inputs["plan_sha256"] == pilot._digest(plan)
            and output._hash(inputs["files_sha256"]) and output._hash(inputs["source_projection_sha256"]),
            "retained_input_binding_mismatch")
    pilot._read_bytes(root / cell["roles"]["config"], sha256=cell["config_sha256"])
    return inputs, root / "cells" / cell["cell_id"]


@contextmanager
def _lock(root: Path):
    pilot._regular_private(root / "lock")
    with os.fdopen(os.open(root / "lock", os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


@contextmanager
def _session(api, *, response_bytes_limit: int | None = None, _branch_setup: dict | None = None):
    token = os.environ.get("HF_TOKEN", "")
    require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
            "explicit_hf_token_required")
    from codex_ci_input_intake import _hf_environment

    with output._time_bound() as deadline, _hf_environment(online=True):
        with (nullcontext(api) if api is not None else output._hf_client(
                token, deadline, response_bytes_limit=response_bytes_limit,
                **({} if _branch_setup is None else _branch_setup))) as client:
            yield client, token, deadline


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _object(path: str, data: bytes) -> dict:
    return {"path": path, **pilot._identity(data), "git_blob_sha1": _git_blob(data)}


def _objects(api, repo: str, revision: str, records: list[dict], token: str, deadline: float,
             *, written_at: str | None = None) -> None:
    """Verify immutable Git/LFS object metadata; never download deliverables."""
    from huggingface_hub import RepoFile

    output._remaining(deadline)
    paths = [record["path"] for record in records]
    require(len(set(paths)) == len(paths) and 0 < len(paths) <= output.MAX_FILES + 3, "output_objects_refused")
    found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=revision, paths=paths,
                               expand=True, token=token)
    require(type(found) is list and len(found) == len(records)
            and {getattr(item, "path", None) for item in found} == set(paths), "remote_output_objects_missing")
    expected = {record["path"]: record for record in records}
    for item in found:
        record = expected[item.path]
        require(isinstance(item, RepoFile) and type(item.size) is int and item.size == record["size"],
                "remote_output_size_mismatch")
        if item.lfs is None:
            require(item.blob_id == record["git_blob_sha1"], "remote_output_blob_mismatch")
        else:
            require(item.lfs.sha256 == record["sha256"] and item.lfs.size == record["size"],
                    "remote_output_lfs_mismatch")
        if written_at is not None:
            require(getattr(item.last_commit, "oid", None) == written_at, "remote_output_history_mismatch")
    output._remaining(deadline)


def _control(api, repo: str, revision: str, path: str, cache: Path, token: str, deadline: float,
             *, expected: dict | None = None, written_at: str | None = None) -> tuple[dict, bytes]:
    """Read only one bounded host-generated JSON at an explicit immutable SHA."""
    from huggingface_hub import RepoFile

    require(output._hash(revision, 40), "immutable_retention_revision_required")
    if expected is not None:
        require(type(expected) is dict and set(expected) == {"sha256", "size"}
                and output._hash(expected["sha256"]) and type(expected["size"]) is int
                and 0 < expected["size"] <= output.MAX_MANIFEST_BYTES, "retention_control_identity_refused")
    output._remaining(deadline)
    found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=revision,
                               paths=[path], expand=True, token=token)
    require(type(found) is list and len(found) == 1 and isinstance(found[0], RepoFile),
            "terminal_or_claim_missing")
    info = found[0]
    require(info.path == path and info.lfs is None and output._hash(info.blob_id, 40)
            and type(info.size) is int and 0 < info.size <= output.MAX_MANIFEST_BYTES,
            "retention_control_file_refused")
    if written_at is not None:
        require(getattr(info.last_commit, "oid", None) == written_at, "retention_control_history_mismatch")
    directory = cache / (revision + "-" + hashlib.sha256(path.encode()).hexdigest())
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    downloaded = api.hf_hub_download(repo_id=repo, repo_type="dataset", revision=revision,
        filename=path, token=token, cache_dir=directory, force_download=True, local_files_only=False,
        etag_timeout=output._remaining(deadline))
    resolved = _remote_download_file(Path(downloaded))
    require(resolved.is_relative_to(directory), "retention_control_cache_escape")
    data = output._bytes(resolved, limit=output.MAX_MANIFEST_BYTES, expected=expected)
    require(len(data) == info.size and _git_blob(data) == info.blob_id, "retention_control_blob_mismatch")
    record = pilot._json_object(data)
    require(data == _encoded(record), "noncanonical_retention_record")
    output._remaining(deadline)
    return record, data


def _absent(api, repo: str, parent: str, cell: dict, token: str, deadline: float) -> None:
    from huggingface_hub import RepoFolder

    claim, _, prefix = _paths(cell)
    prefixes = [claim.rsplit("/", 1)[0], prefix]
    ancestors = {part for name in prefixes for part in (name.split("/")[0], name.rsplit("/", 1)[0])}
    output._remaining(deadline)
    found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=parent,
                               paths=sorted(ancestors) + prefixes, token=token)
    require(type(found) is list and len(found) <= len(ancestors), "cell_already_claimed_or_published")
    seen = set()
    for item in found:
        require(isinstance(item, RepoFolder) and item.path in ancestors and item.path not in seen,
                "cell_already_claimed_or_published")
        seen.add(item.path)


def _claim(value: dict, plan: dict, cell: dict, inputs: dict) -> dict:
    require(type(value) is dict and set(value) == {"format", "binding", "expected_parent", "predecessor", "model_result", "grade"}
            and value["format"] == CLAIM_FORMAT and value["model_result"] is False and value["grade"] is False,
            "claim_contract_mismatch")
    binding = value["binding"]
    require(type(binding) is dict and type(binding["ordinal"]) is int
            and binding == _binding(plan, cell, inputs, host=binding["host"], run=binding["github_run"]),
            "claim_identity_mismatch")
    ordinal = binding["ordinal"]
    predecessor = value["predecessor"]
    if ordinal == ci.FIRST_CELL_ORDINAL:
        require(value["expected_parent"] == BOOTSTRAP and predecessor is None, "first_cell_bootstrap_required")
    else:
        require(type(predecessor) is dict and set(predecessor) == {
            "cell_id", "terminal_commit", "terminal_sha256", "output_commit", "manifest_sha256"}
            and predecessor["cell_id"] == plan["order"][ordinal - 1]
            and all(output._hash(predecessor[key], 40 if key.endswith("commit") else 64)
                    for key in ("terminal_commit", "terminal_sha256", "output_commit", "manifest_sha256"))
            and value["expected_parent"] == predecessor["terminal_commit"], "predecessor_order_binding_required")
    return binding


def _manifest(value: dict, completed: dict, cell: dict) -> None:
    """Check the existing publisher manifest against its validated projection."""
    ci.validate_completion(completed)
    require(completed["execution_requested"] is True and completed["status"] in pilot.TERMINAL
            and completed["cleanup_confirmed"] is True, "confirmed_terminal_cleanup_required")
    fields = ("campaign_id", "cell_id", "source_sha", "config_sha256", "plan_sha256", "order_sha256",
              "verified_inputs_sha256", "host_policy_sha256", "status", "exit_code", "reason", "timeout",
              "cleanup_confirmed", "receipt")
    expected = {key: completed[key] for key in fields}
    expected.update(format=output.FORMAT, grade_ready=False, grading_launched=False,
                    accounting="missing" if completed["receipt"] is None else completed["receipt"]["status"])
    if "inference_branch" in value:
        expected["inference_branch"] = BRANCH
    require(set(value) == set(expected) | {"files", "missing"} | ({"withheld"} if "withheld" in value else set())
            and all(value[key] == item for key, item in expected.items()), "terminal_manifest_binding_mismatch")
    _encoded(value)  # Apply the same bounded control-record serialization.
    files = value["files"]
    require(type(files) is list and len(files) <= output.MAX_FILES + 2, "terminal_manifest_files_refused")
    by_role = {"inference_result": [], "generated_deliverable": [], "cost_ledger_export": []}
    names = []
    for record in files:
        require(type(record) is dict and set(record) == {"role", "path", "size", "sha256"}
                and record["role"] in by_role and type(record["size"]) is int
                and 0 <= record["size"] <= output.MAX_FILE_BYTES and output._hash(record["sha256"]),
                "terminal_manifest_files_refused")
        name = record["path"]
        require(type(name) is str, "terminal_manifest_files_refused")
        if record["role"] == "generated_deliverable":
            require(canonical_deliverable_path(cell["task_id"], name) == name, "terminal_deliverable_path_refused")
        else:
            require(name == ("step2_inference_results.json" if record["role"] == "inference_result"
                             else Path(pilot.LEDGER).name), "terminal_record_role_refused")
        names.append(name)
        by_role[record["role"]].append({key: record[key] for key in ("sha256", "size")})
    require(names == sorted(set(names)) and sum(record["size"] for record in files) <= output.MAX_TOTAL_BYTES,
            "terminal_manifest_files_refused")
    artifacts = completed["artifacts"]
    withheld = "withheld" in value
    if withheld:
        evidence = value["withheld"]
        require(type(evidence) is dict and set(evidence) == {"reason", "artifacts"}
                and evidence["reason"] == "unsafe_result_fields" and evidence["artifacts"] == artifacts
                and artifacts["result"] is not None and completed["status"] in {"failed", "stopped"}
                and files == [], "terminal_withheld_artifacts_mismatch")
        require(len(artifacts["deliverables"]) <= output.MAX_FILES
                and all(item is not None and item["size"] <= output.MAX_FILE_BYTES
                        for item in artifacts["deliverables"])
                and all(item is None or item["size"] <= output.MAX_RECORD_BYTES
                        for item in (artifacts["result"], artifacts["ledger"]))
                and sum(item["size"] for item in (artifacts["result"], artifacts["ledger"], *artifacts["deliverables"])
                        if item is not None) <= output.MAX_TOTAL_BYTES, "terminal_withheld_artifacts_mismatch")
    else:
        require(by_role["inference_result"] == ([] if artifacts["result"] is None else [artifacts["result"]])
                and by_role["cost_ledger_export"] == ([] if artifacts["ledger"] is None else [artifacts["ledger"]])
                and sorted(by_role["generated_deliverable"], key=pilot._canonical_json)
                == sorted(artifacts["deliverables"], key=pilot._canonical_json), "terminal_artifacts_mismatch")
    missing = []
    if artifacts["result"] is None or withheld:
        require(completed["status"] in {"failed", "stopped"} and files == [], "missing_result_not_success")
        missing = ["bound_inference_result", "validated_deliverables", "bound_ledger_export"]
    elif artifacts["ledger"] is None:
        missing.append("bound_ledger_export")
    if completed["receipt"] is None or completed["receipt"]["usage"] is None:
        missing.append("usage")
    require(value["missing"] == missing, "terminal_missing_accounting_mismatch")


def _predecessor(api, repo: str, head: str, plan: dict, selected: dict, inputs: dict,
                 cache: Path, token: str, deadline: float) -> dict | None:
    ordinal = ci._eligible_ordinal(plan, selected["cell_id"])
    if ordinal == ci.FIRST_CELL_ORDINAL:
        require(head == BOOTSTRAP, "first_cell_bootstrap_required")
        return None
    cell = next(row for row in plan["cells"] if row["cell_id"] == plan["order"][ordinal - 1])
    predecessor_plan = plan
    if (plan["run_id"] == "budget_pilot_ci_20260925_04" and BRANCH == "pilot-inference-20260925-04"
            and ordinal == 7 and selected["cell_id"] == "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_B_r1"
            and cell["cell_id"] == "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1"
            and head == "8083504edf4ceb63f3c4929aac57e0f4b6741593"):
        # This one retained A1 is historical evidence, not B1 execution authority.
        # Recompile its producer contract; the immutable claim must still match
        # every original plan/config/input hash and its own validated host.
        predecessor_plan, _, _ = pilot.compile_pilot(ci.CAMPAIGN, "b4c95f8eaee16ae2226f3bf6e0493051fa91d770")
        predecessor_plan["ci"] = {
            "registration_sha256": plan["ci"]["registration_sha256"],
            "selected_cell_id": cell["cell_id"], "host": {"workflow": plan["ci"]["host"]["workflow"]},
        }
        cell = next(row for row in predecessor_plan["cells"] if row["cell_id"] == cell["cell_id"])
    evidence = _terminal(api, repo, head, predecessor_plan, cell, inputs, cache, token, deadline)
    return evidence["observation"]


def _terminal(api, repo: str, head: str, plan: dict, cell: dict, inputs: dict,
              cache: Path, token: str, deadline: float) -> dict:
    """Read one exact immutable terminal, also used by grading-only intake.

    Selection/order and expected identities remain the caller's compiled
    contract. This neither adopts a claim nor reads a moving branch tip.
    """
    claim_path, terminal_path, prefix = _paths(cell)
    terminal, terminal_bytes = _control(api, repo, head, terminal_path, cache, token, deadline, written_at=head)
    require(set(terminal) == {"format", "repository_name_sha256", "inference_branch", "claim_commit", "claim_identity",
        "output_commit", "manifest_identity", "publication_receipt_sha256", "publication_acknowledged",
        "output_objects", "completion"} and terminal["format"] == TERMINAL_FORMAT
        and terminal["repository_name_sha256"] == TARGET_SHA256
        and terminal["inference_branch"] == BRANCH
        and terminal["publication_acknowledged"] is True
        and output._hash(terminal["publication_receipt_sha256"])
        and all(output._hash(terminal[key], 40) for key in ("claim_commit", "output_commit"))
        and len({head, terminal["claim_commit"], terminal["output_commit"]}) == 3,
        "terminal_confirmation_contract_mismatch")
    claim, claim_bytes = _control(api, repo, terminal["claim_commit"], claim_path, cache, token, deadline,
                                  expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
    binding = _claim(claim, plan, cell, inputs)
    completed = ci.validate_completion(terminal["completion"])
    require(all(completed[key] == binding[key] for key in ("campaign_id", "cell_id", "source_sha", *ci.HASH_FIELDS)),
            "terminal_completion_identity_mismatch")
    manifest_path = prefix + "/" + output.MANIFEST
    manifest, manifest_bytes = _control(api, repo, terminal["output_commit"], manifest_path, cache, token, deadline,
        expected=terminal["manifest_identity"], written_at=terminal["output_commit"])
    _manifest(manifest, completed, cell)
    require(manifest.get("inference_branch") == BRANCH, "terminal_inference_branch_mismatch")
    expected = {prefix + "/" + row["path"]: {key: row[key] for key in ("size", "sha256")} for row in manifest["files"]}
    expected[manifest_path] = pilot._identity(manifest_bytes)
    objects = terminal["output_objects"]
    require(type(objects) is list and len(objects) == len(expected), "terminal_output_objects_mismatch")
    for record in objects:
        require(type(record) is dict and set(record) == {"path", "size", "sha256", "git_blob_sha1"}
                and record["path"] in expected and output._hash(record["git_blob_sha1"], 40)
                and {key: record[key] for key in ("size", "sha256")} == expected[record["path"]],
                "terminal_output_objects_mismatch")
    # The Git<->SHA256 mapping was measured from buffered bytes by the prior
    # publisher before terminal commit. Check those immutable provider objects,
    # not merely a marker's presence or mutable latest-HEAD text.
    _objects(api, repo, terminal["output_commit"], objects, token, deadline, written_at=terminal["output_commit"])
    _objects(api, repo, head, objects, token, deadline, written_at=terminal["output_commit"])
    _objects(api, repo, head, [_object(claim_path, claim_bytes)], token, deadline, written_at=terminal["claim_commit"])
    return {"terminal": terminal, "claim": claim, "manifest": manifest,
            "observation": {"cell_id": cell["cell_id"], "terminal_commit": head,
                "terminal_sha256": pilot._identity(terminal_bytes)["sha256"],
                "output_commit": terminal["output_commit"], "manifest_sha256": terminal["manifest_identity"]["sha256"]}}


def _commit(api, repo: str, parent: str, path: str, value: dict, cache: Path, token: str, deadline: float) -> str:
    data = _encoded(value)
    staged = _PublicationFile(path, io.BytesIO(data), len(data), hashlib.sha256(data).hexdigest())
    try:
        output._remaining(deadline)
        operations = _publication_additions((staged,))
        response = api.create_commit(repo_id=repo, repo_type="dataset", revision=BRANCH, token=token,
            parent_commit=parent, operations=operations, commit_message="Record one private pilot cell boundary",
            num_threads=1, run_as_future=False, create_pr=False)
        commit = getattr(response, "oid", None)
        require(output._hash(commit, 40) and commit != parent
                and not any(getattr(item, "_should_ignore", False) for item in operations), "commit_identity_unavailable")
        require(output._metadata(api, repo, commit, token, deadline)["sha"] == commit, "returned_commit_metadata_mismatch")
        observed, _ = _control(api, repo, commit, path, cache, token, deadline,
                               expected=pilot._identity(data), written_at=commit)
        require(observed == value, "committed_control_mismatch")
        return commit
    finally:
        staged.stream.close()


def require_admission(plan: dict, cell: dict, root: Path, inputs: dict) -> dict:
    """Token-free same-live-host gate. A copied claim cannot grant a new clock."""
    _target()
    retained_inputs, cell_root = _local(plan, cell, root)
    require(all(inputs[key] == retained_inputs[key] for key in ("files_sha256", "source_projection_sha256")),
            "admission_input_identity_changed")
    reserved, receipt = _read(cell_root / ADMISSION_RESERVED), _read(cell_root / ADMISSION_RECEIPT)
    require(reserved == {"format": CLAIM_FORMAT, "outcome": "unresolved", "binding": _binding(plan, cell, inputs)},
            "admission_reservation_mismatch")
    require(set(receipt) == {"outcome", "stage", "reason", "http_status", "claim", "claim_identity", "returned_commit"}
            and receipt["outcome"] == "acknowledged" and receipt["stage"] == "claim_verified"
            and receipt["reason"] is None and output._hash(receipt["returned_commit"], 40)
            and receipt["claim_identity"] == pilot._identity(_encoded(receipt["claim"])),
            "acknowledged_admission_required")
    require(_claim(receipt["claim"], plan, cell, inputs) == _binding(plan, cell, inputs), "same_live_host_admission_required")
    require(receipt["returned_commit"] != receipt["claim"]["expected_parent"], "admission_commit_identity_required")
    return receipt


def admit(plan: dict, cell: dict, root: Path, *, _test_api=None) -> dict:
    repo = _target()
    with _lock(root):
        inputs, cell_root = _local(plan, cell, root)
        pilot._require_quiet_owner(root, plan)
        require(all(output._checkpoint(root / row["roles"]["checkpoint"]) == pilot._cell_state(plan, row)
                    for row in plan["cells"]), "admission_requires_unstarted_local_cells")
        require(not os.path.lexists(cell_root / ADMISSION_RECEIPT), "admission_already_reserved")
        _write(cell_root / ADMISSION_RESERVED, {"format": CLAIM_FORMAT, "outcome": "unresolved",
                                               "binding": _binding(plan, cell, inputs)})
        result = {"outcome": "unresolved", "stage": "preflight", "reason": None, "http_status": None,
                  "claim": None, "claim_identity": None, "returned_commit": None}
        try:
            cache = cell_root / "admission-readback"
            cache.mkdir(mode=0o700)
            with _session(_test_api) as (api, token, deadline):
                head = output._metadata(api, repo, BRANCH, token, deadline)["sha"]
                _absent(api, repo, head, cell, token, deadline)
                predecessor = _predecessor(api, repo, head, plan, cell, inputs, cache, token, deadline)
                if predecessor is not None:
                    # Separate observation; never recreate/edit the previous
                    # runner's unresolved/lost-response terminal receipt.
                    _write(cell_root / SERVER_OBSERVATION, {"observation": "verified_server_terminal_state",
                        "predecessor": predecessor, "writer_response_delivery": "not_asserted"})
                claim = {"format": CLAIM_FORMAT, "binding": _binding(plan, cell, inputs),
                         "expected_parent": head, "predecessor": predecessor, "model_result": False, "grade": False}
                _claim(claim, plan, cell, inputs)
                result.update(stage="claim_commit", claim=claim, claim_identity=pilot._identity(_encoded(claim)))
                result["returned_commit"] = _commit(api, repo, head, _paths(cell)[0], claim, cache, token, deadline)
                result.update(outcome="acknowledged", stage="claim_verified")
        except (Exception, KeyboardInterrupt) as error:
            result["reason"], result["http_status"] = output._error_context(error)
            result["outcome"] = "refused" if result["stage"] == "preflight" else "unresolved"
        _write(cell_root / ADMISSION_RECEIPT, result)
        return result


def retain(plan: dict, cell: dict, root: Path, *, _test_api=None) -> dict:
    repo = _target()
    inputs, cell_root = _local(plan, cell, root)
    admission = require_admission(plan, cell, root, inputs)
    snapshot = output.prepare(root=root, campaign=ci.CAMPAIGN, cell_id=cell["cell_id"],
                              source_sha=plan["reviewed_source_sha"], config_sha=cell["config_sha256"],
                              _failure_metadata=True)
    # Add only host storage provenance; the approved payload/withholding
    # validator and all original bytes remain unchanged.
    snapshot.manifest = {**snapshot.manifest, "inference_branch": BRANCH}
    with _lock(root):
        pilot._require_quiet_owner(root, plan)
        state = output._checkpoint(root / cell["roles"]["checkpoint"])
        pilot._validate_state(plan, cell, state)
        completed = ci.completion(plan, cell, execute=True, state=state, inputs=inputs, cleanup=True)
        _manifest(snapshot.manifest, completed, cell)
        require(not os.path.lexists(cell_root / TERMINAL_RECEIPT)
                and not os.path.lexists(cell_root / output.RESERVATION), "retention_already_reserved")
        _write(cell_root / TERMINAL_RESERVED, {"format": TERMINAL_FORMAT, "outcome": "unresolved",
            "claim_commit": admission["returned_commit"], "completion_sha256": pilot._digest(completed)})
        result = {"outcome": "unresolved", "stage": "output_publication", "reason": None, "http_status": None,
                  "output_commit": None, "terminal_commit": None}
        try:
            cache = cell_root / "terminal-readback"
            cache.mkdir(mode=0o700)
            with _session(_test_api) as (api, token, deadline):
                receipt = output.publish(snapshot, repo=repo, expected_parent=admission["returned_commit"],
                    _test_api=api, _deadline=deadline, _token=token, _failure_metadata=True, _retained_ref=True)
                if receipt["outcome"] != "acknowledged":
                    raise output.OutputPublicationRefused("output_publication_not_acknowledged", receipt["http_status"])
                require(_read(cell_root / output.RECEIPT) == receipt, "durable_publication_receipt_required")
                revision = receipt["returned_commit"]
                result.update(stage="output_verification", output_commit=revision)
                claim_path, terminal_path, prefix = _paths(cell)
                manifest_bytes = _encoded(snapshot.manifest)
                objects = [_object(prefix + "/" + name, data) for name, data in sorted({
                    **snapshot.files, output.MANIFEST: manifest_bytes}.items())]
                _objects(api, repo, revision, objects, token, deadline, written_at=revision)
                # Check the retained claim too; publication does not refresh its
                # parent from a mutable HEAD or adopt a different writer's claim.
                _objects(api, repo, revision, [_object(claim_path, _encoded(admission["claim"]))],
                         token, deadline, written_at=admission["returned_commit"])
                manifest, _ = _control(api, repo, revision, prefix + "/" + output.MANIFEST, cache,
                                      token, deadline, expected=receipt["manifest"], written_at=revision)
                require(manifest == snapshot.manifest, "published_manifest_mismatch")
                require(output._metadata(api, repo, BRANCH, token, deadline)["sha"] == revision,
                        "terminal_parent_changed")
                require(api.get_paths_info(repo_id=repo, repo_type="dataset", revision=revision,
                    paths=[terminal_path], token=token) == [], "terminal_already_exists")
                terminal = {"format": TERMINAL_FORMAT, "repository_name_sha256": TARGET_SHA256, "inference_branch": BRANCH,
                    "claim_commit": admission["returned_commit"], "claim_identity": admission["claim_identity"],
                    "output_commit": revision, "manifest_identity": receipt["manifest"],
                    "publication_receipt_sha256": pilot._identity(_encoded(receipt))["sha256"],
                    "publication_acknowledged": True, "output_objects": objects, "completion": completed}
                result["stage"] = "terminal_commit"
                result["terminal_commit"] = _commit(api, repo, revision, terminal_path, terminal, cache, token, deadline)
                result.update(outcome="acknowledged", stage="terminal_verified")
        except (Exception, KeyboardInterrupt) as error:
            result["reason"], result["http_status"] = output._error_context(error)
            # No recovery write or inference retry. Even after this lost response
            # the NEXT job may separately verify a fully committed terminal.
        _write(cell_root / TERMINAL_RECEIPT, result)
        return result


def main(argv: list[str] | None = None, *, _test_api=None, _test_transport=None) -> int:
    parser = output._Parser(description=__doc__)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--admit", action="store_true")
    mode.add_argument("--retain", action="store_true")
    try:
        args = parser.parse_args(argv)
        plan, parent, _, cell = ci.compile_ci_cell(ci.CAMPAIGN, args.cell, args.reviewed_source_sha)
        (_test_transport or pilot.LocalTransport()).require_source(plan, parent)
        _target()
        observed = {"outcome": "plan_only", "stage": "plan", "reason": None, "http_status": None}
        if args.admit or args.retain:
            root = pilot._private_root(args.output)
            observed = (admit if args.admit else retain)(plan, cell, root, _test_api=_test_api)
        # Private receipts/repository/path/file names never enter the public run
        # record. The existing CI completion-envelope schema is unchanged.
        print(pilot._canonical_json({"role": "selected_private_pilot_output", "repository_name_sha256": TARGET_SHA256,
            "campaign_id": ci.CAMPAIGN, "source_sha": plan["reviewed_source_sha"], "inference_branch": BRANCH,
            "cell_id": cell["cell_id"], "ordinal": cell["index"],
            **{key: observed[key] for key in ("outcome", "stage", "reason", "http_status")},
            "model_requested": False, "grading_launched": False, "grade_ready": False}))
        return 0 if observed["outcome"] in {"plan_only", "acknowledged"} else 2
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        reason, _ = output._error_context(error)
        print("Private CI retention refused: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
