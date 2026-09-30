"""Real immutable-result readers; synthetic retained records/transport, no grade."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path

import pytest

import codex_retention_result_intake as reader
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from core.result_fingerprint import inference_result_fingerprint
from ghcp_vm_input_bundle import GHCPInputBundleRefused
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN, offline  # noqa: F401

ci, retained, output, owned = reader.ci, reader.retained, reader.output, reader.owned
CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD, LATER_HEAD = (char * 40 for char in "abcd")
PRIVATE = b"SYNTHETIC PRIVATE DELIVERABLE; NEVER STDOUT\n"
FILE = "deliverable_files/" + reader.registration.TASK4 + "/report.txt"


class ResultHF(MemoryHF):
    """Only declared immutable reads; any write, sweep or other path fails."""

    def __init__(self, plan, *, receipt=None, with_ledger=False, request_sha256=reader.REQUEST_SHA256):
        super().__init__()
        self.downloads, self.path_reads = [], []
        self.corrupt, self.escape = None, None
        self.files = {FILE: PRIVATE}
        cell = reader.controller._adapted_cell(plan["cells"][0])
        row = {"task_id": cell["task_id"], "status": "success", "model": "gpt-5.4", "usage": None,
               "content": PRIVATE.decode(), "deliverable_files": [FILE],
               "deliverable_file_records": [{"path": FILE, **owned._identity(PRIVATE)}]}
        if receipt is not None:
            row["problem_solving_cost"] = receipt
        self.payload = {
            "run_id": cell["run_id"], "experiment_id": cell["run_id"], "condition_identity": "condition_a",
            "execution_mode": "codex_foundry", "ordered_task_ids": [cell["task_id"]], "model": "gpt-5.4",
            "source": plan["inputs"]["repo_id"], "publication_generation": cell["run_id"],
            "prepared_fingerprint": "e" * 64, "results": [row],
        }
        if with_ledger:
            ledger = {name: None for name in output._CALL_COLUMNS}
            ledger.update(record_type="call", call_id="synthetic-call", run_id=cell["run_id"],
                          task_id=cell["task_id"], stage="generation", retry_kind="none", state="settled",
                          missing_reasons=["synthetic_missing_cost"])
            data = (json.dumps(ledger) + "\n").encode()
            self.files[reader.LEDGER] = data
            self.payload["cost_ledger"] = {"path": reader.LEDGER, "sha256": owned._identity(data)["sha256"]}
        self.bind_payload()
        authority = {"request_sha256": request_sha256, "provider_run_id": reader.RUN_ID,
            "provider_job_id": reader.JOB_ID, "runner_id": 123, "host_instance_sha256": "f" * 64,
            "job_origin": {"issuer": ci.OIDC_ISSUER, "scope_sha256": "1" * 64, "host_instance_sha256": "f" * 64},
            "review_sha256": "2" * 64, "reviewer": ci.OWNER, "environment": ci.ENVIRONMENT}
        self.claim = {"format": ci.CLAIM_FORMAT, "request_sha256": request_sha256, "authority": authority,
            "scope": "existing_inference_branch_one_use_remote_cas", "expected_parent": "3" * 40,
            "predecessor": {"cell_id": ci.historical.FINAL_CELL, "terminal_commit": "3" * 40,
                            "terminal_sha256": "4" * 64, "output_commit": "5" * 40, "manifest_sha256": "6" * 64},
            "model_result": False, "grade": None}
        self.summary = {"format": "retention-first-cell-output-v1", "request_sha256": request_sha256,
            "source_sha": reader.PRODUCER_SOURCE, "cell_id": reader.EXPECTATION.cell_id,
            "status": "succeeded", "exit_code": 0, "cleanup_confirmed": True,
            "accounting": "missing" if receipt is None else receipt["status"], "receipt": receipt,
            "grade": None, "grading_launched": False, "invoice_complete": False,
            "missing": ([] if with_ledger else ["bound_ledger_export"])
                       + ([] if receipt is not None and receipt["usage"] is not None else ["usage"]),
            "files": []}
        self.terminal = {"format": ci.TERMINAL_FORMAT, "request_sha256": request_sha256,
            "authority": deepcopy(authority), "scope": self.claim["scope"], "claim_commit": CLAIM_HEAD,
            "claim_identity": None, "output_commit": OUTPUT_HEAD, "output_objects": None,
            "completion": self.summary, "publication_acknowledged": True}
        self.seed()

    def bind_payload(self):
        self.payload["result_fingerprint"] = inference_result_fingerprint(self.payload)
        self.files[reader.RESULT] = (json.dumps(self.payload, sort_keys=True) + "\n").encode()

    def seed(self):
        # Synthetic server state, not calls to the production remote writer.
        self.summary["files"] = [{"path": name, **owned._identity(data)} for name, data in sorted(self.files.items())]
        claim_bytes = retained._encoded(self.claim)
        self.terminal["claim_identity"] = owned._identity(claim_bytes)
        outputs = {ci.OUTPUT + "/" + name: data for name, data in self.files.items()}
        outputs[ci.OUTPUT + "/" + output.MANIFEST] = retained._encoded(self.summary)
        self.terminal["output_objects"] = [retained._object(name, data) for name, data in sorted(outputs.items())]
        self.trees[CLAIM_HEAD] = {ci.CLAIM: claim_bytes}
        self.trees[OUTPUT_HEAD] = {**self.trees[CLAIM_HEAD], **outputs}
        self.trees[TERMINAL_HEAD] = {**self.trees[OUTPUT_HEAD], ci.TERMINAL: retained._encoded(self.terminal)}
        self.trees[LATER_HEAD] = {**self.trees[TERMINAL_HEAD], "unrelated/never-read": b"NO SWEEP"}
        self.writers[CLAIM_HEAD] = {ci.CLAIM: CLAIM_HEAD}
        self.writers[OUTPUT_HEAD] = {**self.writers[CLAIM_HEAD], **{name: OUTPUT_HEAD for name in outputs}}
        self.writers[TERMINAL_HEAD] = {**self.writers[OUTPUT_HEAD], ci.TERMINAL: TERMINAL_HEAD}
        self.writers[LATER_HEAD] = {**self.writers[TERMINAL_HEAD], "unrelated/never-read": LATER_HEAD}
        self.parents.update({OUTPUT_HEAD: CLAIM_HEAD, TERMINAL_HEAD: OUTPUT_HEAD, LATER_HEAD: TERMINAL_HEAD})
        self.head = LATER_HEAD

    def get_paths_info(self, **kwargs):
        assert set(kwargs["paths"]) <= {ci.CLAIM, ci.TERMINAL, *self.trees[OUTPUT_HEAD]}, "path sweep refused"
        self.path_reads.append((kwargs["revision"], tuple(kwargs["paths"])))
        if kwargs["revision"] == retained.BRANCH:
            assert kwargs["paths"] == [ci.TERMINAL] and kwargs["expand"] is True
            kwargs = {**kwargs, "revision": self.head}
        return super().get_paths_info(**kwargs)

    def repo_info(self, **kwargs):
        pytest.fail("only the fixed terminal path may be discovered")

    def hf_hub_download(self, **kwargs):
        self.record("immutable_read", kwargs)
        revision, name = kwargs["revision"], kwargs["filename"]
        assert revision in {CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD}
        assert name in {ci.CLAIM, ci.TERMINAL, *self.trees[OUTPUT_HEAD]}
        assert kwargs["force_download"] is True and kwargs["local_files_only"] is False
        assert 0 < kwargs["etag_timeout"] <= output.REQUEST_SECONDS
        self.downloads.append((revision, name))
        if self.escape is not None:
            return str(self.escape)
        data = b"ALTERED" if name == self.corrupt else self.trees[revision][name]
        path = Path(kwargs["cache_dir"]) / "downloaded"
        output._write_no_clobber(path, data)
        return str(path)

    def create_commit(self, **kwargs):
        pytest.fail("result reader attempted a remote write")

    def list_repo_tree(self, **kwargs):
        pytest.fail("result reader attempted a repository sweep")


def test_first_retention_result_intake_is_immutable_bound_and_read_only(tmp_path, monkeypatch, capsys):
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("result-intake regression crossed an execution or private-input boundary")

    for owner, name in (
        (ci, "execute"), (ci, "verify_approval"), (ci, "verify_job_origin"),
        (ci._Admission, "__init__"), (ci.LocalTransport, "github_job_token"), (ci.LocalTransport, "authority_opener"),
        (ci.LocalTransport, "github"), (ci.LocalTransport, "azure"), (owned.LocalTransport, "clock"),
        (owned.LocalTransport, "child"), (owned.LocalTransport, "process"),
        (ci.preparation, "prepare_packet"), (ci.preparation, "verify_packet"), (ci.historical, "observe"),
        (ci.controller, "execute_first_cell"), (ci.controller, "stage_runtime"), (ci.controller, "_deadline"),
        (CodexTaskDeadlineStore, "__init__"), (CodexTaskDeadline, "admit_attempt"),
        (reader.retained_reader, "prepare"), (reader.retained_reader, "main"), (output, "_hf_client"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "unchanged"
    sentinel.write_bytes(b"UNCHANGED OUTSIDE OWNED DESTINATIONS")
    plan = reader.registration.compile_plan()  # Real compiler/validators, no originals or grader constructor.
    source = reader.reader_identity()
    api = ResultHF(plan)

    def captured():
        text = capsys.readouterr()
        assert text.err == ""
        for secret in (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), FILE):
            assert secret not in text.out
        return json.loads(text.out)

    with monkeypatch.context() as default:
        default.setattr(retained, "_session", forbidden)
        assert reader.main([], _test_api=api) == 0
        planned = captured()
        assert planned["read_attempted"] is False and planned["mode"] == "plan"
        assert planned["reader"] == source and planned["grade"] is None
        assert reader.main(["--output", str(tmp_path / "not-opted-in")], _test_api=api) == 2
        assert captured()["reason"] == "explicit_retention_result_read_required"
    assert api.calls == [] and not (tmp_path / "not-opted-in").exists() and effects == []
    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Synthetic explicit credential; real session scrubs it for the transport.

    def read(api, name, **changes):
        args = dict(expectation=reader.EXPECTATION, destination=tmp_path / name,
                    expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=api)
        args.update(changes)
        return reader.read_result(**args)

    # Exact legacy document hashing is preserved. No fake prepared request is
    # used for the supplied producer binding; this separate document is synthetic.
    document = {"source": {"head": reader.PRODUCER_SOURCE}, "synthetic": "whole document is hashed"}
    digest = owned._digest(document)
    equivalence = ResultHF(plan, request_sha256=digest)
    expectation = ci.TerminalExpectation(digest, reader.PRODUCER_SOURCE, reader.EXPECTATION.cell_id)

    class ForeignExpectation(ci.TerminalExpectation):
        pass

    with retained._session(equivalence) as (transport, token, deadline):
        results = []
        for name, doc, options in (("document", document, {}), ("expectation", None, {"expectation": expectation})):
            cache = tmp_path / name
            cache.mkdir()
            results.append(ci.verify_terminal(transport, api.repo, TERMINAL_HEAD, doc, cache, token, deadline, **options))
        assert results[0] == results[1]
        assert set(results[0]) == {"request_sha256", "terminal_commit", "completion", "observation_only", "replay_authorized"}
        assert results[0]["observation_only"] is True and results[0]["replay_authorized"] is False
        for wrong_doc, wrong_expected, reason in (
            (document, expectation, "retention_terminal_expectation_conflict"),
            (None, None, "retention_terminal_expectation_required"),
            (None, object(), "retention_terminal_expectation_required"),
            (None, ForeignExpectation(digest, reader.PRODUCER_SOURCE, reader.EXPECTATION.cell_id),
             "retention_terminal_expectation_required"),
            (None, replace(expectation, source_sha="bad"), "retention_terminal_expectation_refused"),
            (None, replace(expectation, request_sha256="bad"), "retention_terminal_expectation_refused"),
            (None, replace(expectation, request_sha256=True), "retention_terminal_expectation_refused"),
            (None, replace(expectation, cell_id="another-cell"), "retention_terminal_expectation_refused"),
        ):
            before = list(equivalence.calls)
            with pytest.raises(ci.RetentionCIRefused) as refused:
                ci.verify_terminal(transport, api.repo, TERMINAL_HEAD, wrong_doc, tmp_path / "unused",
                                   token, deadline, expectation=wrong_expected)
            assert str(refused.value) == reason and equivalence.calls == before
        changed_document = {**document, "synthetic": "changed outside source identity"}
        cache = tmp_path / "changed-document"
        cache.mkdir()
        with pytest.raises(ci.RetentionCIRefused, match="^retention_terminal_contract_mismatch$"):
            ci.verify_terminal(transport, api.repo, TERMINAL_HEAD, changed_document, cache, token, deadline)

    for index, (changes, reason) in enumerate((
        ({"expectation": object()}, "retention_result_expectation_required"),
        ({"expectation": ForeignExpectation(reader.REQUEST_SHA256, reader.PRODUCER_SOURCE, reader.EXPECTATION.cell_id)},
         "retention_result_expectation_required"),
        ({"expectation": replace(reader.EXPECTATION, source_sha="0" * 40)}, "retention_result_expected_producer_mismatch"),
        ({"expectation": replace(reader.EXPECTATION, request_sha256="0" * 64)}, "retention_result_expected_request_mismatch"),
        ({"expectation": replace(reader.EXPECTATION, cell_id="another-cell")}, "retention_result_expected_cell_mismatch"),
        ({"expected_reader_sha256": "0" * 64}, "retention_result_reader_bytes_mismatch"),
        ({"discover_terminal": True}, "one_terminal_revision_or_discovery_required"),
        ({"terminal_revision": None}, "one_terminal_revision_or_discovery_required"),
    )):
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(api, "early-" + str(index), **changes)
        assert str(refused.value) == reason and api.calls == []
        assert not (tmp_path / ("early-" + str(index))).exists()

    argv = ["--read", "--output", str(tmp_path / "valid"), "--expected-producer-source", reader.PRODUCER_SOURCE,
            "--expected-request-sha256", reader.REQUEST_SHA256, "--cell-id", reader.EXPECTATION.cell_id,
            "--expected-reader-sha256", source["module_sha256"], "--discover-terminal"]
    assert reader.main(argv, _test_api=api) == 0
    public = captured()
    marker = tmp_path / "valid" / reader.MARKER
    record = json.loads(marker.read_bytes())
    assert public["intake_verified"] is True and "intake_verified" not in record
    assert record["evidence_only"] is record["consumer_readback_required"] is True
    assert record["reader"] == source and record["producer_source_sha"] == reader.PRODUCER_SOURCE
    assert public["intake_sha256"] == owned._identity(marker.read_bytes())["sha256"]
    assert record["terminal_commit"] == TERMINAL_HEAD != api.head
    assert record["claim_commit"] == CLAIM_HEAD and record["output_commit"] == OUTPUT_HEAD
    assert record["provider_run_id"] == reader.RUN_ID and record["provider_job_id"] == reader.JOB_ID
    assert record["terminal_identity"] == owned._identity(api.trees[TERMINAL_HEAD][ci.TERMINAL])
    assert record["result"]["sha256"] == owned._identity(api.files[reader.RESULT])["sha256"]
    assert record["result"]["result_fingerprint"] == api.payload["result_fingerprint"]
    assert record["receipt"] is None and record["accounting"] == "missing"
    assert record["missing"] == ["bound_ledger_export", "usage"]
    for key in ("launch_authorized", "admission_attempted", "grading_launched", "invoice_complete",
                "replay_authorized", "fresh_origin_authentication", "prepared_input_independently_verified"):
        assert record[key] is False
    assert record["grade"] is None and record["commands"] == []
    assert api.path_reads[0] == (retained.BRANCH, (ci.TERMINAL,))
    assert all(revision != retained.BRANCH for revision, _ in api.path_reads[1:])
    assert all(revision != retained.BRANCH for revision, _ in api.downloads)
    assert all(revision == TERMINAL_HEAD for revision, name in api.downloads if name == ci.OUTPUT + "/" + FILE)
    assert (tmp_path / "valid" / FILE).read_bytes() == PRIVATE
    assert {name for _, name in api.downloads} == {ci.CLAIM, ci.TERMINAL, ci.OUTPUT + "/" + output.MANIFEST,
                                                *(ci.OUTPUT + "/" + name for name in api.files)}
    assert api.commits == [] and effects == []

    partial = CostReceipt(status="partial", known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
                          model_calls=1, usage={"input_tokens": 12, "output_tokens": 3, "reasoning_tokens": 2},
                          missing_reasons=("synthetic_missing_cost",)).as_dict()
    partial = ci.project_cost_receipt(partial)
    partial_api = ResultHF(plan, receipt=partial, with_ledger=True)
    partial_record = read(partial_api, "partial-accounting")
    assert partial_record["accounting"] == "partial" and partial_record["receipt"] == partial
    assert partial_record["invoice_complete"] is False and partial_record["grade"] is None
    assert partial_record["missing"] == [] and partial_record["receipt"]["estimated_cost_usd"] is None
    assert (tmp_path / "partial-accounting" / reader.LEDGER).read_bytes() == partial_api.files[reader.LEDGER]
    empty_ledger = ResultHF(plan, with_ledger=True)
    empty_ledger.files[reader.LEDGER] = b""
    empty_ledger.payload["cost_ledger"]["sha256"] = owned._identity(b"")["sha256"]
    empty_ledger.bind_payload()
    empty_ledger.seed()
    empty_record = read(empty_ledger, "empty-bound-ledger")
    assert empty_record["receipt"] is None and empty_record["accounting"] == "missing"
    assert empty_record["missing"] == ["usage"] and empty_record["invoice_complete"] is False
    assert (tmp_path / "empty-bound-ledger" / reader.LEDGER).read_bytes() == b""
    missing_discovery = ResultHF(plan)
    del missing_discovery.trees[LATER_HEAD][ci.TERMINAL]
    with pytest.raises(output.OutputPublicationRefused, match="^retention_result_terminal_missing$"):
        read(missing_discovery, "missing-discovery", terminal_revision=None, discover_terminal=True)
    assert missing_discovery.downloads == [] and not (tmp_path / "missing-discovery" / reader.MARKER).exists()

    # Every negative traverses the real immutable/control/payload predicates;
    # only the transport's synthetic retained bytes/metadata are varied.
    refusals = {
        "source": (ci.RetentionCIRefused, "retention_completion_mismatch"),
        "request": (ci.RetentionCIRefused, "retention_completion_mismatch"),
        "cell": (ci.RetentionCIRefused, "retention_completion_mismatch"),
        "unacknowledged": (ci.RetentionCIRefused, "retention_terminal_contract_mismatch"),
        "missing": (output.OutputPublicationRefused, "terminal_or_claim_missing"),
        "claim": (ci.RetentionCIRefused, "retention_terminal_claim_mismatch"),
        "history": (output.OutputPublicationRefused, "remote_output_history_mismatch"),
        "authority": (output.OutputPublicationRefused, "retention_result_authority_binding_mismatch"),
        "origin": (output.OutputPublicationRefused, "retention_result_job_origin_mismatch"),
        "hash": (output.OutputPublicationRefused, "retained_file_identity_mismatch"),
        "fingerprint": (ValueError, "inference result fingerprint does not match payload"),
        "private": (output.OutputPublicationRefused, "retention_result_private_state_refused"),
        "traversal": (ValueError, "deliverable path is not canonical for task '" + reader.registration.TASK4 + "'"),
        "cache-escape": (output.OutputPublicationRefused, "retention_control_cache_escape"),
    }
    for index, (mode, (error_type, reason)) in enumerate(refusals.items()):
        bad = ResultHF(plan)
        if mode in {"source", "request", "cell"}:
            key = {"source": "source_sha", "request": "request_sha256", "cell": "cell_id"}[mode]
            bad.summary[key] = "wrong-binding"
        elif mode == "unacknowledged":
            bad.terminal["publication_acknowledged"] = False
        elif mode == "claim":
            bad.claim["request_sha256"] = "0" * 64
        elif mode in {"authority", "origin"}:
            for value in (bad.claim["authority"], bad.terminal["authority"]):
                if mode == "authority":
                    value["provider_job_id"] += 1
                else:
                    value["job_origin"]["host_instance_sha256"] = "0" * 64
        elif mode == "hash":
            bad.corrupt = ci.OUTPUT + "/" + FILE
        elif mode == "fingerprint":
            bad.payload["result_fingerprint"] = "0" * 64
            bad.files[reader.RESULT] = json.dumps(bad.payload).encode()
        elif mode in {"private", "traversal"}:
            bad.files[FILE.rsplit("/", 1)[0] + ("/auth.json" if mode == "private" else "/../outside")] = bad.files.pop(FILE)
        elif mode == "cache-escape":
            bad.escape = sentinel
        bad.seed()
        if mode == "missing":
            del bad.trees[TERMINAL_HEAD][ci.TERMINAL]
        elif mode == "history":
            bad.writers[TERMINAL_HEAD][ci.OUTPUT + "/" + FILE] = TERMINAL_HEAD
        destination = tmp_path / ("negative-" + str(index))
        with pytest.raises(error_type) as refused:
            read(bad, destination.name)
        assert type(refused.value) is error_type and str(refused.value) == reason
        assert not (destination / reader.MARKER).exists()
        assert sentinel.read_bytes() == b"UNCHANGED OUTSIDE OWNED DESTINATIONS" and effects == []
        if mode not in {"hash", "fingerprint"}:
            assert not any(name == ci.OUTPUT + "/" + reader.RESULT for _, name in bad.downloads)

    # Per-role record bounds are stricter than generic object bounds. Roles
    # reserve the marker/cache namespace; no local state can enter as payload.
    for name in (reader.RESULT, reader.LEDGER):
        summary = deepcopy(api.summary)
        summary["files"] = [item for item in summary["files"] if item["path"] != name]
        summary["files"].append({"path": name, "size": output.MAX_RECORD_BYTES + 1, "sha256": "0" * 64})
        with pytest.raises(output.OutputPublicationRefused, match="^retention_result_record_bounds_exceeded$"):
            reader._roles(summary)
    for forbidden_path in (reader.MARKER, reader.CACHE + "/auth.json", "HOME/auth.json", "CODEX_HOME/auth.json"):
        summary = deepcopy(api.summary)
        summary["files"].append({"path": forbidden_path, "size": 1, "sha256": "0" * 64})
        with pytest.raises(ValueError):
            reader._roles(summary)

    before = list(api.calls)
    with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
        read(api, "valid")
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        read(api, "symlink", destination=link / "must-not-exist")
    with pytest.raises(ValueError):
        read(api, "traversal", destination=tmp_path / ".." / "must-not-exist")
    assert api.calls == before and list(outside.iterdir()) == [sentinel]

    real_write = reader._write_no_clobber
    for phase in ("member", "marker", "altered-readback"):
        destination, moved = tmp_path / phase, tmp_path / (phase + "-retained-partial")
        swapped = []

        def interrupted(path, data, *, parent_fd):
            if not swapped and ((phase == "member") or (phase == "marker" and path.name == reader.MARKER)):
                destination.rename(moved)  # Exact test-owned namespaces only.
                destination.mkdir()
                swapped.append(True)
            real_write(path, data, parent_fd=parent_fd)
            if phase == "altered-readback" and path.name == reader.RESULT:
                path.write_bytes(b"TEST-OWNED TAMPER")

        with monkeypatch.context() as writing:
            writing.setattr(reader, "_write_no_clobber", interrupted)
            with pytest.raises((GHCPInputBundleRefused, FileNotFoundError, output.OutputPublicationRefused)):
                read(ResultHF(plan), phase)
        assert not (destination / reader.MARKER).exists()
        if phase != "altered-readback":
            assert swapped == [True] and list(destination.iterdir()) == []
            assert (moved / reader.CACHE).is_dir() and not (moved / reader.MARKER).exists()
            if phase == "marker":
                assert (moved / FILE).read_bytes() == PRIVATE
            with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
                read(api, phase)
    # A post-link failure retains evidence but must not leave a success-shaped
    # marker or emit a successful receipt. This is not safe to adopt or retry.
    real_fsync, real_bytes = reader.os.fsync, output._bytes
    for phase in ("marker-fsync", "marker-readback"):
        destination = tmp_path / phase
        marker = destination / reader.MARKER

        def fail_fsync(descriptor):
            if marker.exists():
                raise OSError("synthetic post-link fsync refusal")
            return real_fsync(descriptor)

        def fail_readback(path, **kwargs):
            if path == marker:
                raise output.OutputPublicationRefused("payload_identity_mismatch")
            return real_bytes(path, **kwargs)

        with monkeypatch.context() as publication:
            if phase == "marker-fsync":
                publication.setattr(reader.os, "fsync", fail_fsync)
            else:
                publication.setattr(output, "_bytes", fail_readback)
            with pytest.raises(output.OutputPublicationRefused) as refused:
                read(ResultHF(plan), phase)
        assert str(refused.value) == "retention_result_completion_acknowledgment_unconfirmed"
        evidence = json.loads(marker.read_bytes())
        assert evidence["evidence_only"] is evidence["consumer_readback_required"] is True
        assert "intake_verified" not in evidence and "intake_sha256" not in evidence
        assert (destination / FILE).read_bytes() == PRIVATE
        with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
            read(api, phase)
    assert sentinel.read_bytes() == b"UNCHANGED OUTSIDE OWNED DESTINATIONS"
    assert list(outside.iterdir()) == [sentinel] and effects == [] and api.commits == []
