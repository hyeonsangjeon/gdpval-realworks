"""Fixed fresh/r1 result intake with real validators and synthetic server bytes."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path

import pytest

import codex_retention_fresh_r1_result_intake as reader
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN, offline  # noqa: F401
from .test_codex_retention_result_intake import ResultHF, CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD, LATER_HEAD, FILE, PRIVATE

fresh, ci, retained, output, owned = reader.fresh, reader.ci, reader.retained, reader.output, reader.owned
intake = reader.intake


class FreshResultHF(MemoryHF):
    """Reuse the valid synthetic result builder; never change production roots."""

    def __init__(self, plan, *, receipt=None, with_ledger=False, binding=reader.FRESH_R1,
                 terminal_head=TERMINAL_HEAD):
        super().__init__()
        self.producer = producer = reader._producer(binding)
        self.terminal_head = terminal_head
        original = ResultHF(plan, receipt=receipt, with_ledger=with_ledger,
                            request_sha256=binding.expectation.request_sha256)
        self.files, self.payload = deepcopy(original.files), deepcopy(original.payload)
        self.claim, self.summary, self.terminal = (deepcopy(value) for value in
                                                   (original.claim, original.summary, original.terminal))
        cell = intake.controller._adapted_cell(plan["cells"][binding.ordinal])
        for key in ("run_id", "experiment_id", "publication_generation"):
            self.payload[key] = cell["run_id"]
        if with_ledger:
            # Synthetic producer rows get their registered runtime identity
            # before sealing, not a rewrite of retained real accounting.
            row = json.loads(self.files[intake.LEDGER])
            row["run_id"] = cell["run_id"]
            self.files[intake.LEDGER] = (json.dumps(row) + "\n").encode()
            self.payload["cost_ledger"]["sha256"] = owned._identity(self.files[intake.LEDGER])["sha256"]
        self.bind_payload()
        self.claim.update(format=producer.CLAIM_FORMAT, expected_parent=producer.PREDECESSOR["terminal_commit"],
                          predecessor=deepcopy(producer.PREDECESSOR))
        # Preserve the old r1 success fixture's deliberately different positive job.
        self.claim["authority"].update(provider_run_id=binding.run_id,
            provider_job_id=123456 if binding is reader.FRESH_R1 else binding.execution_job_id)
        self.summary.update(format=producer.OUTPUT_FORMAT, source_sha=binding.expectation.source_sha,
                            cell_id=binding.expectation.cell_id)
        self.terminal.update(format=producer.TERMINAL_FORMAT, authority=deepcopy(self.claim["authority"]),
                             completion=self.summary)
        self.downloads, self.path_reads = [], []
        self.corrupt, self.escape, self.read_error = None, None, None
        self.seed()

    bind_payload = ResultHF.bind_payload

    def seed(self):
        producer = self.producer
        self.summary["files"] = [{"path": name, **owned._identity(data)} for name, data in sorted(self.files.items())]
        claim_bytes = retained._encoded(self.claim)
        self.terminal["claim_identity"] = owned._identity(claim_bytes)
        outputs = {producer.OUTPUT + "/" + name: data for name, data in self.files.items()}
        outputs[producer.OUTPUT + "/" + output.MANIFEST] = retained._encoded(self.summary)
        self.terminal["output_objects"] = [retained._object(name, data) for name, data in sorted(outputs.items())]
        self.trees[CLAIM_HEAD] = {producer.CLAIM: claim_bytes}
        self.trees[OUTPUT_HEAD] = {**self.trees[CLAIM_HEAD], **outputs}
        self.trees[self.terminal_head] = {**self.trees[OUTPUT_HEAD], producer.TERMINAL: retained._encoded(self.terminal)}
        self.trees[LATER_HEAD] = {**self.trees[self.terminal_head], "unrelated/never-read": b"NO SWEEP"}
        self.writers[CLAIM_HEAD] = {producer.CLAIM: CLAIM_HEAD}
        self.writers[OUTPUT_HEAD] = {**self.writers[CLAIM_HEAD], **{name: OUTPUT_HEAD for name in outputs}}
        self.writers[self.terminal_head] = {**self.writers[OUTPUT_HEAD], producer.TERMINAL: self.terminal_head}
        self.writers[LATER_HEAD] = {**self.writers[self.terminal_head], "unrelated/never-read": LATER_HEAD}
        self.parents.update({CLAIM_HEAD: producer.PREDECESSOR["terminal_commit"], OUTPUT_HEAD: CLAIM_HEAD,
                             self.terminal_head: OUTPUT_HEAD, LATER_HEAD: self.terminal_head})
        self.head = LATER_HEAD

    def get_paths_info(self, **kwargs):
        assert set(kwargs["paths"]) <= {self.producer.CLAIM, self.producer.TERMINAL, *self.trees[OUTPUT_HEAD]}, "path sweep refused"
        self.path_reads.append((kwargs["revision"], tuple(kwargs["paths"])))
        if self.read_error is not None:
            raise self.read_error
        if kwargs["revision"] == retained.BRANCH:
            assert kwargs["paths"] == [self.producer.TERMINAL] and kwargs["expand"] is True
            kwargs = {**kwargs, "revision": self.head}
        return super().get_paths_info(**kwargs)

    def hf_hub_download(self, **kwargs):
        self.record("immutable_read", kwargs)
        revision, name = kwargs["revision"], kwargs["filename"]
        assert revision in {CLAIM_HEAD, OUTPUT_HEAD, self.terminal_head}
        assert name in {self.producer.CLAIM, self.producer.TERMINAL, *self.trees[OUTPUT_HEAD]}
        assert kwargs["force_download"] is True and kwargs["local_files_only"] is False
        assert 0 < kwargs["etag_timeout"] <= output.REQUEST_SECONDS
        self.downloads.append((revision, name))
        if self.escape is not None:
            return str(self.escape)
        path = Path(kwargs["cache_dir"]) / "downloaded"
        output._write_no_clobber(path, b"ALTERED" if name == self.corrupt else self.trees[revision][name])
        return str(path)

    repo_info = ResultHF.repo_info
    create_commit = ResultHF.create_commit
    list_repo_tree = ResultHF.list_repo_tree


def test_fresh_r1_result_intake_is_fixed_immutable_and_model_free(tmp_path, monkeypatch, capsys):
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("fresh-result regression crossed an execution, authority or private-input boundary")

    for owner, name in (
        (ci, "execute"), (ci, "verify_approval"), (ci, "verify_job_origin"), (ci, "verify_terminal"),
        (fresh, "execute"), (fresh, "_predecessor"), (fresh, "verify_terminal"), (fresh._FreshAdmission, "__init__"),
        (ci._Admission, "__init__"), (ci.LocalTransport, "github_job_token"), (ci.LocalTransport, "authority_opener"),
        (ci.LocalTransport, "github"), (ci.LocalTransport, "azure"), (owned.LocalTransport, "clock"),
        (owned.LocalTransport, "child"), (owned.LocalTransport, "process"),
        (ci.preparation, "prepare_packet"), (ci.preparation, "verify_packet"), (ci.historical, "observe"),
        (ci.controller, "execute_first_cell"), (ci.controller, "stage_runtime"), (ci.controller, "_deadline"),
        (CodexTaskDeadlineStore, "__init__"), (CodexTaskDeadline, "admit_attempt"),
        (intake.retained_reader, "prepare"), (intake.retained_reader, "main"), (output, "_hf_client"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    plan = intake.registration.compile_plan()  # Real pinned registration/config/path checks.
    source = reader.reader_identity()
    assert {name: source[name] for name in reader.FROZEN} == {name: pair[1] for name, pair in reader.FROZEN.items()}
    api = FreshResultHF(plan)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "unchanged"
    sentinel.write_bytes(b"UNCHANGED OUTSIDE OWNED DESTINATIONS")

    def captured():
        text = capsys.readouterr()
        assert text.err == ""
        for secret in (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), FILE, "SECRET-LIKE-ERROR"):
            assert secret not in text.out
        return json.loads(text.out)

    with monkeypatch.context() as inert:
        inert.setattr(retained, "_session", forbidden)
        assert reader.main([], _test_api=api) == 0
        assert captured()["read_attempted"] is False
        assert reader.main(["--output", str(tmp_path / "not-opted-in")], _test_api=api) == 2
        assert captured()["reason"] == "explicit_fresh_result_read_required"
    assert not (tmp_path / "not-opted-in").exists() and api.calls == []
    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Not a credential; real session still scrubs it for synthetic transport.

    def read(transport, name, **changes):
        options = dict(expectation=reader.EXPECTATION, destination=tmp_path / name,
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=transport)
        return reader.read_result(**{**options, **changes})

    class ForeignExpectation(ci.TerminalExpectation):
        pass

    for index, (changes, reason) in enumerate((
        ({"expectation": object()}, "fresh_result_expectation_required"),
        ({"expectation": ForeignExpectation(reader.REQUEST_SHA256, reader.PRODUCER_SOURCE, fresh.CELL_ID)},
         "fresh_result_expectation_required"),
        ({"expectation": replace(reader.EXPECTATION, source_sha="0" * 40)}, "fresh_result_expected_producer_mismatch"),
        ({"expectation": replace(reader.EXPECTATION, request_sha256="0" * 64)}, "fresh_result_expected_request_mismatch"),
        ({"expectation": replace(reader.EXPECTATION, cell_id=ci.controller.FIRST_CELL_ID)}, "fresh_result_expected_cell_mismatch"),
        ({"expected_reader_sha256": "0" * 64}, "fresh_result_reader_bytes_mismatch"),
        ({"discover_terminal": True}, "one_terminal_revision_or_discovery_required"),
        ({"terminal_revision": None}, "one_terminal_revision_or_discovery_required"),
    )):
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(api, "early-" + str(index), **changes)
        assert refused.value.args == (reason,) and api.calls == []
        assert not (tmp_path / ("early-" + str(index))).exists()

    def argv(name):
        return ["--read", "--discover-terminal", "--expected-producer-source", reader.PRODUCER_SOURCE,
            "--expected-request-sha256", reader.REQUEST_SHA256, "--cell-id", fresh.CELL_ID,
            "--expected-reader-sha256", source["module_sha256"], "--output", str(tmp_path / name)]

    code = reader.main(argv("valid"), _test_api=api)
    public = captured()  # Preserve only safe diagnostics before the exit-code assertion.
    assert code == 0, {key: public.get(key) for key in ("reason", "intake_verified")}
    marker = tmp_path / "valid" / reader.MARKER
    record = json.loads(marker.read_bytes())
    assert marker.read_bytes() == retained._encoded(record)
    assert record["format"] == reader.FORMAT and record["ordinal"] == 1 and record["cell_id"] == fresh.CELL_ID
    assert record["campaign"] == intake.registration.CAMPAIGN
    assert record["evidence_only"] is record["consumer_readback_required"] is True
    assert public["intake_verified"] is True and "intake_verified" not in record
    assert public["intake_sha256"] == owned._identity(marker.read_bytes())["sha256"]
    assert record["reader"] == source and record["producer_source_sha"] == reader.PRODUCER_SOURCE
    assert record["request_sha256"] == reader.REQUEST_SHA256
    assert record["terminal_commit"] == TERMINAL_HEAD != api.head
    assert record["terminal_identity"] == owned._identity(api.trees[TERMINAL_HEAD][fresh.TERMINAL])
    assert record["claim_commit"] == CLAIM_HEAD and record["claim_identity"] == owned._identity(api.trees[CLAIM_HEAD][fresh.CLAIM])
    assert record["output_commit"] == OUTPUT_HEAD and record["predecessor"] == fresh.PREDECESSOR
    assert record["expected_provider"] == reader.EXPECTED_PROVIDER
    assert record["recorded_provider_run_id"] == reader.RUN_ID and record["recorded_provider_job_id"] == 123456
    assert record["supplied_request_binding"] == reader.SUPPLIED_REQUEST_BINDING
    assert record["proof"] == "verified_publication_derived_not_independent_provider_authentication"
    assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
    assert record["status"] == "succeeded" and record["cleanup_confirmed"] is True
    assert record["result"]["result_fingerprint"] == api.payload["result_fingerprint"]
    assert record["result"]["registered_config_sha256"] == plan["cells"][1]["config_sha256"]
    assert "files" not in public and "recorded_publication_generation" not in public["result"]
    assert record["receipt"] is None and record["accounting"] == "missing"
    assert record["missing"] == ["bound_ledger_export", "usage"] and record["http_request_count"] is None
    for key in ("launch_authorized", "admission_attempted", "grading_launched", "invoice_complete", "replay_authorized",
                "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified"):
        assert record[key] is False
    assert record["grade"] is None and record["commands"] == []
    assert api.path_reads[0] == (retained.BRANCH, (fresh.TERMINAL,))
    assert all(revision != retained.BRANCH for revision, _ in api.path_reads[1:])
    assert all(revision != retained.BRANCH for revision, _ in api.downloads)
    assert {name for _, name in api.downloads} == {fresh.TERMINAL, fresh.CLAIM, fresh.OUTPUT + "/" + output.MANIFEST,
                                                *(fresh.OUTPUT + "/" + name for name in api.files)}
    assert not any(revision == fresh.PREDECESSOR["terminal_commit"] for revision, _ in api.path_reads)
    assert (tmp_path / "valid" / FILE).read_bytes() == PRIVATE and marker.stat().st_mode & 0o077 == 0

    partial = ci.project_cost_receipt(CostReceipt(status="partial", known_cost_usd=Decimal("0.01"),
        model_cost_usd=Decimal("0.01"), model_calls=1, usage={"input_tokens": 12, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    ledger_api = FreshResultHF(plan, receipt=partial, with_ledger=True)
    ledger_record = read(ledger_api, "partial-accounting")
    assert ledger_record["accounting"] == "partial" and ledger_record["receipt"] == partial
    assert ledger_record["receipt"]["estimated_cost_usd"] is None and ledger_record["missing"] == []
    assert ledger_record["invoice_complete"] is False and ledger_record["http_request_count"] is None
    assert (tmp_path / "partial-accounting" / intake.LEDGER).read_bytes() == ledger_api.files[intake.LEDGER]
    empty = FreshResultHF(plan, with_ledger=True)
    empty.files[intake.LEDGER] = b""
    empty.payload["cost_ledger"]["sha256"] = owned._identity(b"")["sha256"]
    empty.bind_payload()
    empty.seed()
    empty_record = read(empty, "empty-ledger")
    assert empty_record["missing"] == ["usage"] and empty_record["accounting"] == "missing"

    missing = FreshResultHF(plan)
    del missing.trees[LATER_HEAD][fresh.TERMINAL]
    assert reader.main(argv("not-ready"), _test_api=missing) == 2
    assert captured()["reason"] == "fresh_result_terminal_not_ready"
    assert missing.downloads == [] and missing.path_reads == [(retained.BRANCH, (fresh.TERMINAL,))]
    assert not (tmp_path / "not-ready" / reader.MARKER).exists()

    reasons = {
        "source": "fresh_result_completion_mismatch", "cell": "fresh_result_completion_mismatch",
        "request": "fresh_result_terminal_binding_mismatch", "run": "fresh_result_authority_binding_mismatch",
        "job-bool": "fresh_result_authority_binding_mismatch", "origin": "fresh_result_origin_mismatch",
        "claim": "fresh_result_terminal_claim_mismatch", "predecessor": "fresh_result_predecessor_mismatch",
        "parent": "fresh_result_predecessor_mismatch", "cleanup": "fresh_result_completion_mismatch",
        "unfinished": "fresh_result_success_required", "exit-bool": "fresh_result_success_required",
        "unacknowledged": "fresh_result_terminal_binding_mismatch", "claim-hash": "payload_identity_mismatch",
        "terminal-bytes": "retention_control_blob_mismatch", "payload-bytes": "retained_file_identity_mismatch",
        "history": "remote_output_history_mismatch", "claim-history": "retention_control_history_mismatch",
        "terminal-history": "retention_control_history_mismatch", "extra-object": "fresh_result_output_objects_mismatch",
        "private-role": "retention_result_private_state_refused", "sqlite": "retention_result_private_state_refused",
        "ledger-pointer": "retention_result_ledger_binding_mismatch", "ledger-run": "ledger_cell_mismatch",
        "cache-escape": "retention_control_cache_escape", "claim-number-type": "fresh_result_terminal_claim_mismatch",
        "predecessor-number-type": "fresh_result_predecessor_mismatch", "summary-bool-type": "fresh_result_summary_readback_mismatch",
        "receipt-number-type": "fresh_result_accounting_mismatch",
    }
    for mode, reason in reasons.items():
        bad = FreshResultHF(plan, with_ledger=mode.startswith("ledger-"))
        if mode in {"source", "cell"}:
            bad.summary[{"source": "source_sha", "cell": "cell_id"}[mode]] = "wrong-binding"
        elif mode == "request":
            bad.terminal["request_sha256"] = "0" * 64
        elif mode in {"run", "job-bool", "origin"}:
            for authority in (bad.claim["authority"], bad.terminal["authority"]):
                if mode == "run":
                    authority["provider_run_id"] = intake.RUN_ID
                elif mode == "job-bool":
                    authority["provider_job_id"] = True
                else:
                    authority["job_origin"]["host_instance_sha256"] = "0" * 64
        elif mode == "claim":
            bad.claim["request_sha256"] = "0" * 64
        elif mode == "predecessor":
            bad.claim["predecessor"]["terminal_commit"] = "0" * 40
        elif mode == "parent":
            bad.claim["expected_parent"] = "0" * 40
        elif mode == "cleanup":
            bad.summary["cleanup_confirmed"] = False
        elif mode == "unfinished":
            bad.summary["status"] = "failed"
        elif mode == "exit-bool":
            bad.summary["exit_code"] = False
        elif mode == "unacknowledged":
            bad.terminal["publication_acknowledged"] = False
        elif mode == "terminal-bytes":
            bad.corrupt = fresh.TERMINAL
        elif mode == "payload-bytes":
            bad.corrupt = fresh.OUTPUT + "/" + FILE
        elif mode == "private-role":
            bad.files[FILE.rsplit("/", 1)[0] + "/HOME/auth.json"] = PRIVATE
        elif mode == "sqlite":
            bad.files[FILE] = b"SQLite format 3\0NATIVE STATE"
            bad.payload["results"][0]["deliverable_file_records"] = [{"path": FILE, **owned._identity(bad.files[FILE])}]
            bad.bind_payload()
        elif mode == "ledger-pointer":
            bad.payload["cost_ledger"]["sha256"] = "0" * 64
            bad.bind_payload()
        elif mode == "ledger-run":
            row = json.loads(bad.files[intake.LEDGER])
            row["run_id"] = intake.controller._adapted_cell(plan["cells"][0])["run_id"]
            bad.files[intake.LEDGER] = (json.dumps(row) + "\n").encode()
            bad.payload["cost_ledger"]["sha256"] = owned._identity(bad.files[intake.LEDGER])["sha256"]
            bad.bind_payload()
        elif mode == "cache-escape":
            bad.escape = sentinel
        elif mode == "claim-number-type":
            bad.claim["authority"]["provider_job_id"] = float(bad.claim["authority"]["provider_job_id"])
        elif mode == "predecessor-number-type":
            identity = bad.claim["predecessor"]["terminal_identity"]
            identity["size"] = float(identity["size"])
        elif mode == "receipt-number-type":
            receipt = ci.project_cost_receipt(CostReceipt(status="partial", known_cost_usd=Decimal("1"),
                model_cost_usd=Decimal("1"), missing_reasons=("synthetic_missing_cost",)).as_dict())
            bad.summary.update(receipt=receipt, accounting="partial")
            bad.summary["receipt"]["known_cost_usd"] = 1  # Projector normalizes amounts to float; not byte-identical.
        bad.seed()
        if mode == "claim-hash":
            bad.terminal["claim_identity"]["sha256"] = "0" * 64
        elif mode == "extra-object":
            bad.terminal["output_objects"].append(deepcopy(bad.terminal["output_objects"][0]))
        elif mode == "history":
            bad.writers[TERMINAL_HEAD][fresh.OUTPUT + "/" + FILE] = TERMINAL_HEAD
        elif mode == "claim-history":
            bad.writers[CLAIM_HEAD][fresh.CLAIM] = TERMINAL_HEAD
        elif mode == "terminal-history":
            bad.writers[TERMINAL_HEAD][fresh.TERMINAL] = OUTPUT_HEAD
        elif mode == "summary-bool-type":
            # Reseal only the immutable manifest and its object identity. The
            # terminal's validated completion remains true, not the integer 1.
            altered = deepcopy(bad.summary)
            altered["cleanup_confirmed"] = 1
            path, data = fresh.OUTPUT + "/" + output.MANIFEST, retained._encoded(altered)
            for head in (OUTPUT_HEAD, TERMINAL_HEAD):
                bad.trees[head][path] = data
            bad.terminal["output_objects"] = [retained._object(path, data) if item["path"] == path else item
                                              for item in bad.terminal["output_objects"]]
        bad.trees[TERMINAL_HEAD][fresh.TERMINAL] = retained._encoded(bad.terminal)
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(bad, "negative-" + mode)
        assert refused.value.args == (reason,), mode
        assert not (tmp_path / ("negative-" + mode) / reader.MARKER).exists()
        assert bad.commits == [] and effects == []

    # Genuine shape/role/fingerprint predicates, without oversized downloads.
    for mode, reason in (("duplicate", "fresh_result_output_bounds_exceeded"),
                         ("total", "fresh_result_output_bounds_exceeded"),
                         ("size", "fresh_result_output_identity_refused"),
                         ("record", "retention_result_record_bounds_exceeded")):
        summary = deepcopy(api.summary)
        if mode == "duplicate":
            summary["files"].append(deepcopy(summary["files"][0]))
        elif mode == "total":
            summary["files"] = [{"path": f"deliverable_files/{intake.registration.TASK4}/{index}.txt",
                "size": output.MAX_FILE_BYTES, "sha256": "0" * 64} for index in range(3)]
        elif mode == "size":
            summary["files"][0]["size"] = output.MAX_FILE_BYTES + 1
        else:
            next(item for item in summary["files"] if item["path"] == intake.RESULT)["size"] = output.MAX_RECORD_BYTES + 1
        with pytest.raises(output.OutputPublicationRefused) as refused:
            reader._summary(summary)
        assert refused.value.args == (reason,)
    for mode in ("extra-role", "fingerprint"):
        bad = FreshResultHF(plan)
        if mode == "extra-role":
            bad.files["unrelated.json"] = b"{}"
        else:
            bad.payload["result_fingerprint"] = "0" * 64
            bad.files[intake.RESULT] = json.dumps(bad.payload).encode()
        bad.seed()
        with pytest.raises(ValueError) as refused:
            read(bad, mode)
        assert type(refused.value) is ValueError
        assert not (tmp_path / mode / reader.MARKER).exists()

    before = list(api.calls)
    with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
        read(api, "valid")
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        read(api, "symlink", destination=link / "must-not-exist")
    assert api.calls == before
    # Retain the ambiguous marker, but never return successful intake or adopt it.
    real_fsync = reader.os.fsync
    ambiguous_marker = tmp_path / "ambiguous" / reader.MARKER

    def fail_after_marker(descriptor):
        if ambiguous_marker.exists():
            raise OSError("SECRET-LIKE-ERROR")
        return real_fsync(descriptor)

    with monkeypatch.context() as publication:
        publication.setattr(reader.os, "fsync", fail_after_marker)
        assert reader.main(argv("ambiguous"), _test_api=FreshResultHF(plan)) == 2
    assert captured()["reason"] == "fresh_result_completion_acknowledgment_unconfirmed"
    assert "intake_verified" not in json.loads(ambiguous_marker.read_bytes())
    with pytest.raises(output.OutputPublicationRefused, match="^new_result_destination_required$"):
        read(api, "ambiguous")
    for index, error in enumerate((ValueError("SECRET-LIKE-ERROR"), output.OutputPublicationRefused("SECRET-LIKE-ERROR"))):
        bad = FreshResultHF(plan)
        bad.read_error = error
        assert reader.main(argv("redacted-" + str(index)), _test_api=bad) == 2
        assert captured()["reason"] == "fresh_result_intake_refused"
    assert sentinel.read_bytes() == b"UNCHANGED OUTSIDE OWNED DESTINATIONS" and list(outside.iterdir()) == [sentinel]
    assert effects == [] and api.commits == ledger_api.commits == empty.commits == []
