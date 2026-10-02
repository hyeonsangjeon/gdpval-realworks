"""Synthetic immutable keep/r2 readout proof, never a live score or invoice.

Only transport/Git metadata and fixture publication identities are simulated.
Canonical contexts, payload/schema/ledger validators and private file reads are
real. The existing offline fixture forbids processes, network and credentials.
"""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest
import yaml

from core.cost_receipts import build_receipt
from core.rubric_loader import RubricLoader
from . import test_codex_retention_grade_readout as old
from .test_codex_budget_pilot_retention import offline, TOKEN  # noqa: F401

reader, bridge, grade, pilot, output, retained = old.reader, old.bridge, old.grade, old.pilot, old.output, old.retained
SELECTOR = "retention/keep-r2-readout"


def test_keep_r2_grade_readout_is_fixed_numeric_and_model_free(tmp_path, monkeypatch, capsys):
    assert reader.KEEP_R2_SELECTOR == SELECTOR
    assert reader.KEEP_R2_WRITER_SOURCE == "b99a28a4c0ec0ed961a2a8ddcaa886462beb0691"
    assert reader.KEEP_R2_WRITER_RUN == {"id": "36984239149", "job": "pilot-live", "attempt": 1}
    assert reader.KEEP_R2_WRITER_JOB_ID == 110766211046
    assert reader.KEEP_R2_TERMINAL == "76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e"
    assert reader.KEEP_R2_TERMINAL_IDENTITY == {
        "sha256": "d1f2a48d392044937a904243feb5ab0d320d271f1082806ac2aa9e927cb3c66c", "size": 3107}
    assert reader.KEEP_R2_CLAIM == "f8d5189a86c297499c77084aeeb697aea15aad00"
    profile = reader._fixed(SELECTOR)
    fixed = bridge._fixed(profile.grading_selector)
    assert hashlib.sha256(Path(fixed.__file__).read_bytes()).hexdigest() == reader.KEEP_R2_ADAPTER_SHA256
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert fixed.CELL == "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2"
    assert fixed.RESULT["terminal_commit"] == "e55fac5d60191167dd66688510ec0fef472e594d"
    assert fixed.RESULT["result"]["result_fingerprint"] == "909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a"
    assert fixed.PARENT["revision"] == "40712e0980cc05c31688fdbb98c693774fb90c0d"
    context = bridge.compile_request(profile.writer_source, selector=fixed.SELECTOR)
    assert context.cell["index"] == 3 and context.cell["control"] == {
        "condition": "retention_bundle_v1", "retention_bundle": "keep", "repetition": 2}

    t, c, p, unknown = old._fixture(context, selector=SELECTOR)
    # Synthetic accounting: one known call plus an unresolved reservation.
    # These amounts/usage are unrelated to either real keep grade or inference.
    known = {**json.loads(unknown), "call_id": "synthetic-known", "state": "settled",
        "input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 10, "reasoning_tokens": 4,
        "model_cost_usd": "0.0123", "missing_reasons": []}
    ledger = old.base._json(known) + unknown
    cost = build_receipt([known, json.loads(unknown)], []).as_dict()
    p["tasks"][0]["grading_cost"] = deepcopy(cost)
    p["summary"]["grading_cost"] = deepcopy(cost)
    p["cost_ledger"]["sha256"] = hashlib.sha256(ledger).hexdigest()
    template = t, c, p, ledger
    api = old._seed(monkeypatch, *deepcopy(template), selector=SELECTOR)
    effects, roots, git_calls = [], [], []

    def forbidden(*args, **kwargs):
        effects.append("forbidden_effect")
        pytest.fail("readout reached a paid, input, renderer or mutation boundary")

    for target, names in (
        (bridge, ("_authority", "prepare", "claim", "judge", "publish", "reconcile", "_ready", "_derived_inputs")),
        (grade, ("_ci_authority", "prepare", "claim", "judge", "publish", "reconcile", "_owned_judge", "setup")),
        (pilot, ("dispatch",)), (old.step8, ("main",)), (bridge.reader, ("read_result",)),
        (fixed, ("read_result", "parent_controls")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    monkeypatch.setattr("core.tools.get_renderer_fingerprint", forbidden)
    monkeypatch.setattr(RubricLoader, "load", forbidden)
    common = tmp_path / "synthetic-git-metadata"
    common.mkdir()
    git_state = {"head": old.OBSERVER, "dirty": b""}

    def git(path, *command, ok=(0,)):
        assert Path(path) == bridge.ROOT
        git_calls.append(command)
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(path) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (git_state["head"] + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): git_state["dirty"],
            ("status", "--porcelain", "--untracked-files=normal"): git_state["dirty"],
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): b""}
        assert command in answers
        return SimpleNamespace(stdout=answers[command], returncode=0)

    monkeypatch.setattr(old.source_checkout, "_git", git)
    monkeypatch.setattr(pilot, "_git", git)

    def invoke(transport=api, *, phase="readout", selector=SELECTOR, source=old.OBSERVER,
               revision=profile.terminal, producer="", root=None, script=False):
        root = root or tmp_path / f"readout-{len(roots)}"
        roots.append(root)
        args = ["--selector", selector, "--reviewed-source-sha", source, "--terminal-revision", revision,
                "--producer-source-sha", producer, "--root", str(root)]
        if phase is not None:
            args += ["--phase", phase]
        if script:
            with monkeypatch.context() as scoped:
                scoped.setattr(sys, "argv", [str(bridge.ROOT / "batch-runner/codex_budget_pilot_grading.py"), *args])
                with pytest.raises(SystemExit) as exit_info:
                    runpy.run_path(sys.argv[0], run_name="__main__")
                status = exit_info.value.code
        else:
            status = grade.main(args, _test_api=transport)
        captured = capsys.readouterr()
        text = captured.out if status == 0 else captured.err
        assert not (captured.err if status == 0 else captured.out)
        for private in (old.PRIVATE, TOKEN, str(tmp_path), retained._target(), '"criterion":',
                        '"evidence":', '"judge_raw_response":', '"grade_path":', '"call_id":'):
            assert private not in text
        result = json.loads(text)
        assert result["remote_mutation_possible"] is False and result["judge_entry_requested"] is False
        assert result["invoice_complete"] is False and result["http_request_count"] is None
        assert result["automatic_retry"] is False and result["inference_requested"] is False
        assert result["materialized_input_fingerprint"] == {
            "status": "unavailable", "value": None, "comparison": None,
            "reason": "materialized_input_fingerprint_not_recorded"}
        assert effects == []
        return status, result

    with monkeypatch.context() as local:
        local.delenv("GITHUB_ACTIONS", raising=False)
        assert invoke(phase=None, script=True)[0] == 0  # Real dispatcher, inert default phase.
        assert not api.calls and not git_calls and not roots[-1].exists()
        assert invoke()[0] == 2 and not api.calls and not roots[-1].exists()
    old._environment(monkeypatch, selector=SELECTOR)
    for changes in ({"source": profile.writer_source}, {"source": fixed.RESULT["producer_source_sha"]},
                    {"source": "invalid"}, {"revision": "main"}, {"revision": reader.TERMINAL},
                    {"revision": fixed.RESULT["terminal_commit"]}, {"producer": profile.writer_source}):
        assert invoke(**changes)[0] == 2 and not roots[-1].exists() and not api.calls
    for phase in ("inspect", "setup", "prepare", "claim", "judge", "publish", "reconcile", "record-ungraded"):
        assert invoke(phase=phase)[0] == 2 and not roots[-1].exists() and not api.calls
    for key, value in (("PILOT_GRADE_PAID_APPROVAL", "true"), ("PILOT_GRADE_DRY_RUN", "true"),
            ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_JOB", "pilot-live"), ("GRADE_SELECTOR", reader.SELECTOR),
            ("GRADE_TERMINAL", reader.TERMINAL), ("GRADE_RESUME", "true"), ("GRADE_FORCE", "true"),
            ("GRADE_SHARD_COUNT", "2"), ("GRADE_TASKS_LIMIT", "1"), ("GRADE_CONFIG", "other.yaml")):
        with monkeypatch.context() as scoped:
            scoped.setenv(key, value)
            assert invoke()[0] == 2 and not roots[-1].exists() and not api.calls
    for head, dirty in (("e" * 40, b""), (old.OBSERVER, b"synthetic-dirty\n")):
        git_state.update(head=head, dirty=dirty)
        status, result = invoke()
        assert status == 2 and result["stage"] == "source_preflight" and not api.calls
    git_state.update(head=old.OBSERVER, dirty=b"")
    real_bytes = output._bytes
    for filename, reason in (("codex_retention_keep_r2_grade.py", "reviewed_retention_grade_adapter_required"),
                             ("codex_retention_fresh_r1_result_intake.py", "reviewed_retention_observer_dependency_required")):
        with monkeypatch.context() as scoped:
            def corrupt(path, **kwargs):
                data = real_bytes(path, **kwargs)
                return data + b"\n" if Path(path).name == filename else data
            scoped.setattr(output, "_bytes", corrupt)
            scoped.setattr(retained, "_session", forbidden)
            if filename == "codex_retention_keep_r2_grade.py":
                scoped.setattr(bridge, "_fixed", forbidden)  # No lazy adapter import before its hash.
                with pytest.raises(output.OutputPublicationRefused, match=f"^{reason}$"):
                    reader._fixed(SELECTOR)
            else:
                with pytest.raises(output.OutputPublicationRefused, match=f"^{reason}$"):
                    reader._source_current(old.OBSERVER, selector=SELECTOR)
            assert invoke()[0] == 2 and not roots[-1].exists() and not api.calls

    before = deepcopy((api.trees, api.writers, api.branches))
    reached = set()

    def witness(label, real):
        def call(*args, **kwargs):
            result = real(*args, **kwargs)
            reached.add(label)
            return result
        return call

    with monkeypatch.context() as proof:
        for target, name in ((reader, "_source_current"), (bridge, "_terminal"), (reader, "_terminal_contract"),
                             (grade, "_validate_grade_identity"), (output, "_ledger"),
                             (reader.readout, "_recorded_projection"), (reader.readout, "_receipt")):
            proof.setattr(target, name, witness(name, getattr(target, name)))
        status, result = invoke()
    assert status == 0 and result["outcome"] == "verified_writer_recorded_grade", result
    assert reached == {"_source_current", "_terminal", "_terminal_contract", "_validate_grade_identity", "_ledger",
                       "_recorded_projection", "_receipt"}
    assert result["grade_state"] == "graded" and result["record_kind"] == "writer_recorded_grade"
    assert result["score"] == {"earned": 2, "possible": 4, "pct": 50,
        "tasks_with_excluded_items": 1, "excluded_items": 1, "excluded_max_score": 2.0,
        "avg_score_pct_full_denominator": 33.33, "avg_score_pct_lift": 16.67}
    assert result["coverage"]["passed_items"] == 1 and result["coverage"]["rubric_item_coverage"] == 0.5
    for field in ("recorded_task_cost", "recorded_summary_cost", "ledger_derived_cost"):
        observed = result[field]
        assert observed["status"] == "partial" and observed["model_calls"] == 2
        assert observed["known_cost_usd"] == observed["model_cost_usd"] == 0.0123
        assert observed["estimated_cost_usd"] is None and observed["runtime_cost_usd"] is None
        assert observed["usage"]["input_tokens"] == 100 and observed["usage"]["cached_input_tokens"] == 40
        assert observed["usage"]["output_tokens"] == 10 and observed["usage"]["reasoning_tokens"] == 4
        assert "call_reachability_unknown" in observed["missing_reasons"]
        assert observed["invoice_complete"] is False and observed["http_request_count"] is None
    assert result["selector"] == SELECTOR and result["cell_id"] == fixed.CELL
    assert result["grade_writer_source_sha"] == profile.writer_source and result["grade_writer_run"] == profile.writer_run
    assert result["supplied_grade_writer_job_id"] == 110766211046
    assert result["provider_job_identity_independently_verified"] is False
    assert result["grade_revision"] == profile.terminal and result["claim_revision"] == profile.claim
    assert result["intake_sha256"] == fixed.RESULT["intake_sha256"]
    assert result["original_result_fingerprint"] == fixed.RESULT["result"]["result_fingerprint"]
    assert result["writer_preparation_sha256"] == "a" * 64
    assert result["proof_boundary"] == grade.PROOF and result["mutable_branch_head_observed"] is False
    assert (api.trees, api.writers, api.branches) == before and not api.commits
    terminal = pilot._json_object(api.trees[profile.terminal][fixed.TERMINAL_PATH])
    allowed = {(profile.terminal, fixed.TERMINAL_PATH), (profile.claim, fixed.CLAIM_PATH),
               *((profile.terminal, row["path"]) for row in terminal["files"])}
    assert len(api.downloads) == 5 and set(api.downloads) == allowed
    assert len(api.paths) == 5 and sum(name == "metadata" for name, _ in api.calls) == 1
    assert roots[-1].stat().st_mode & 0o777 == 0o700
    count = len(api.calls)
    assert invoke(root=roots[-1])[0] == 2 and len(api.calls) == count  # No-clobber, no automatic second read.

    # Canonical expected writer identity is independent of the fetched body.
    for field, value in (("source_sha", "e" * 40), ("selector", bridge.SELECTOR), ("cell_id", bridge.CELL),
            ("github_run", {**profile.writer_run, "id": "1"}),
            ("github_run", {**profile.writer_run, "job": "110766211046"}),
            ("github_run", {**profile.writer_run, "attempt": True}),
            ("approval_sha256", "e" * 64), ("fixed_evidence_sha256", "e" * 64),
            ("intake_sha256", "e" * 64), ("grading_plan_sha256", "e" * 64)):
        bad = deepcopy(terminal)
        bad["binding"][field] = value
        with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_readout_writer_binding_mismatch$"):
            reader._terminal_contract(context, bad, selector=SELECTOR)
    with pytest.raises(output.OutputPublicationRefused, match="^canonical_retention_grade_context_required$"):
        reader._terminal_contract(SimpleNamespace(**context.__dict__), terminal, selector=SELECTOR)
    with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_context_changed$"):
        reader._terminal_contract(replace(context, cell={**context.cell, "index": True}), terminal, selector=SELECTOR)

    for case in ("missing_terminal", "terminal_hash", "terminal_history", "claim_missing", "claim_revision", "claim_hash", "claim_parent",
                 "claim_history", "inherited_claim_history", "file_history", "download_hash", "duplicate",
                 "missing_result", "private_role", "bound", "bool_size", "cleanup", "not_graded", "private_target", "transport_failure"):
        t, c, p, ledger = deepcopy(template)
        bad = old._seed(monkeypatch, t, c, p, ledger, selector=SELECTOR)
        if case == "missing_terminal":
            del bad.trees[profile.terminal][fixed.TERMINAL_PATH]
        elif case == "terminal_hash":
            monkeypatch.setattr(reader, "KEEP_R2_TERMINAL_IDENTITY", {"sha256": "0" * 64, "size": 1})
        elif case == "terminal_history":
            bad.writers[profile.terminal][fixed.TERMINAL_PATH] = profile.claim
        elif case == "claim_missing":
            del bad.trees[profile.claim][fixed.CLAIM_PATH]
        elif case == "claim_revision":
            t["claim_commit"] = reader.CLAIM
        elif case == "claim_hash":
            t["claim_identity"]["sha256"] = "0" * 64
        elif case == "claim_parent":
            c = deepcopy(c)
            c["expected_parent"] = fixed.RESULT["terminal_commit"]  # Inference is not the grading parent.
            raw = retained._encoded(c)
            for revision in (profile.claim, profile.terminal):
                bad.trees[revision][fixed.CLAIM_PATH] = raw
            t["claim_identity"] = pilot._identity(raw)
        elif case in {"claim_history", "inherited_claim_history"}:
            revision = profile.claim if case == "claim_history" else profile.terminal
            bad.writers[revision][fixed.CLAIM_PATH] = fixed.PARENT["revision"]
        elif case == "file_history":
            bad.writers[profile.terminal][t["files"][0]["path"]] = profile.claim
        elif case == "download_hash":
            bad.corrupt_download = t["files"][0]["path"]
        elif case == "duplicate":
            t["files"] = [t["files"][0], t["files"][0]]
        elif case == "missing_result":
            t["files"] = [row for row in t["files"] if row["role"] != "grade_result"]
        elif case == "private_role":
            t["files"][0]["role"] = "native_sqlite"
        elif case in {"bound", "bool_size"}:
            t["files"][0]["size"] = output.MAX_RECORD_BYTES + 1 if case == "bound" else True
        elif case == "cleanup":
            t["child"]["cleanup_confirmed"] = False
        elif case == "not_graded":
            t["outcome"] = "ungraded"
        elif case == "private_target":
            bad.private = False
        elif case == "transport_failure":
            bad.read_fail = True
        if case not in {"missing_terminal", "terminal_hash"}:
            raw = retained._encoded(t)
            bad.trees[profile.terminal][fixed.TERMINAL_PATH] = raw
            monkeypatch.setattr(reader, "KEEP_R2_TERMINAL_IDENTITY", pilot._identity(raw))
        status, refusal = invoke(bad)
        assert status == 2 and refusal["stage"] == ("grade_payload" if case == "download_hash" else "grade_terminal"), case
        if case != "download_hash":
            assert all(name in {fixed.TERMINAL_PATH, fixed.CLAIM_PATH} for _, name in bad.downloads), case
        assert not bad.commits and sum(name == "metadata" for name, _ in bad.calls) == 1

    # Reuse the real payload/schema/ledger projection for a small identity matrix.
    entry = template[0]["binding"]["entry"]
    ledger_binding = output.RetentionKeepR2LedgerBinding(entry["config_hash"], entry["grader_source_hash"])
    payload_refusals = {
        "source": (ValueError, "^Grade resume identity mismatch for source_inference_revision:"),
        "selector": (output.OutputPublicationRefused, "^grade_scope_identity_mismatch$"),
        "task": (output.OutputPublicationRefused, "^grade_task_set_mismatch$"),
        "rubric": (ValueError, "^Grade resume identity mismatch for rubric[.]commit_sha:"),
        "raw_judge": (output.OutputPublicationRefused, "^raw_judge_response_refused$"),
        "ledger_run": (output.OutputPublicationRefused, "^ledger_cell_mismatch$"),
        "ledger_usage": (output.OutputPublicationRefused, "^ledger_usage_refused$"),
        "ledger_note": (output.OutputPublicationRefused, "^unsafe_ledger_note$"),
        "ledger_duplicate": (output.OutputPublicationRefused, "^ledger_duplicate_or_missing_identity$"),
        "ledger_hash": (output.OutputPublicationRefused, "^grade_ledger_pointer_mismatch$"),
    }
    for case, (error_type, reason) in payload_refusals.items():
        t, c, p, ledger = deepcopy(template)
        if case == "source":
            p["source_inference_revision"] = bridge.RESULT["output_commit"]
        elif case == "selector":
            p["experiment_yaml_name"] = bridge.SELECTOR
        elif case == "task":
            p["tasks"][0]["task_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        elif case == "rubric":
            p["rubric"]["commit_sha"] = "e" * 40
        elif case == "raw_judge":
            p["tasks"][0]["items"][0]["judge_raw_response"] = old.PRIVATE
        elif case in {"ledger_run", "ledger_usage", "ledger_note", "ledger_duplicate"}:
            rows = [json.loads(line) for line in ledger.splitlines()]
            if case == "ledger_run":
                rows[0]["run_id"] = entry["cost_run_id"].replace("retention/keep-r2", "retention/first-cell")
            elif case == "ledger_usage":
                rows[0]["input_tokens"] = True
            elif case == "ledger_note":
                rows[0]["note"] = old.PRIVATE
            else:
                rows.append(deepcopy(rows[0]))
            ledger = b"".join(old.base._json(row) for row in rows)
        else:
            p["cost_ledger"]["sha256"] = "e" * 64
        with pytest.raises(error_type, match=reason):
            reader.readout._recorded_projection(context, terminal,
                {"grade_result": old.base._json(p), "grade_cost_ledger": ledger}, entry,
                inference_revision=fixed.RESULT["output_commit"], retention_first_cell_binding=ledger_binding)
    for binding in (output.RetentionFirstCellLedgerBinding(entry["config_hash"], entry["grader_source_hash"]),
                    replace(ledger_binding, config_hash="e" * 16), SimpleNamespace(**ledger_binding.__dict__)):
        with pytest.raises(output.OutputPublicationRefused, match="^fixed_retention_grade_projection_binding_required$"):
            reader.readout._recorded_projection(context, terminal, {}, entry,
                inference_revision=fixed.RESULT["output_commit"], retention_first_cell_binding=binding)
    with pytest.raises(output.OutputPublicationRefused, match="^bound_grade_ledger_missing$"):
        reader.readout._recorded_projection(context, terminal, {"grade_result": old.base._json(template[2])}, entry,
            inference_revision=fixed.RESULT["output_commit"], retention_first_cell_binding=ledger_binding)

    t, c, p, _ = deepcopy(template)
    p["cost_ledger"] = None
    missing = old._seed(monkeypatch, t, c, p, None, selector=SELECTOR)
    status, result = invoke(missing)
    assert status == 0 and result["missing"] == ["grade_cost_ledger"]
    assert result["ledger_state"] == "missing" and result["ledger_derived_cost"] is None
    assert result["recorded_task_cost"]["known_cost_usd"] == 0.0123  # Recorded cost is not ledger verification.
    assert effects == [] and git_calls


def test_keep_r2_grade_readout_routes_and_historical_default_stay_closed(tmp_path, monkeypatch):
    old._workflow()  # Current YAML: exact closed read/plan groups and all paid/secret guards.
    jobs = yaml.safe_load((bridge.ROOT / grade.WORKFLOW).read_bytes())["jobs"]
    assert list(jobs) == ["validate-request", "approve-paid", "grade-dry-run", "grade", "pilot-plan",
                          "pilot-approve-paid", "pilot-live", "pilot-readout", "verify-published"]
    assert jobs["pilot-readout"]["timeout-minutes"] == 25
    for name in ("pilot-approve-paid", "pilot-live"):
        assert SELECTOR not in jobs[name]["if"]
    profile = reader._fixed()
    assert profile.selector == reader.SELECTOR == "retention/grade-readout"
    assert profile.grading_selector == "retention/first-cell"
    assert profile.writer_source == "29e0353f1539265b1741e71be894fedf9be32a8b"
    assert profile.writer_run == {"id": "36776393736", "job": "pilot-live", "attempt": 1}
    assert profile.terminal == "40712e0980cc05c31688fdbb98c693774fb90c0d"
    assert profile.terminal_identity == {
        "sha256": "11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234", "size": 3119}
    assert profile.claim == "dec305d669e3ca2e53c7f7b9ebfbe7974d661350"
    assert bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    for selector in (True, 1, {}, profile, "retention/fresh-r2-readout", "retention/keep-r2", "retention/grade-readout/other"):
        with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_readout_route_refused$"):
            reader._fixed(selector)
    context = bridge.compile_request(reader.WRITER_SOURCE)
    template = old._fixture(context)
    api = old._seed(monkeypatch, *deepcopy(template))
    terminal = pilot._json_object(api.trees[reader.TERMINAL][bridge.TERMINAL_PATH])
    entry, claim = reader._terminal_contract(context, terminal)  # Omitted binding stays first-cell.
    assert claim == template[1] and context.cell["index"] == 0
    first_binding = output.RetentionFirstCellLedgerBinding(entry["config_hash"], entry["grader_source_hash"])
    result = reader.readout._recorded_projection(context, terminal,
        {"grade_result": old.base._json(template[2]), "grade_cost_ledger": template[3]}, entry,
        inference_revision=bridge.RESULT["output_commit"], retention_first_cell_binding=first_binding)
    assert result["score"]["pct"] == 50  # Synthetic old fixture, not the historical 68% score.
    with pytest.raises(output.OutputPublicationRefused, match="^fixed_retention_grade_projection_binding_required$"):
        reader.readout._recorded_projection(context, terminal, {}, entry,
            inference_revision=bridge.RESULT["output_commit"],
            retention_first_cell_binding=output.RetentionKeepR2LedgerBinding(entry["config_hash"], entry["grader_source_hash"]))
    new_context = bridge.compile_request(reader.KEEP_R2_WRITER_SOURCE, selector="retention/keep-r2")
    with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_readout_writer_refused$"):
        reader._terminal_contract(new_context, terminal)
    with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_readout_writer_refused$"):
        reader._terminal_contract(context, terminal, selector=SELECTOR)

    # The unchanged keep/r2 grading adapter uses this omitted historical reader
    # for its parent controls. Substitute only explicit synthetic identities.
    fixed = bridge._fixed("retention/keep-r2")
    monkeypatch.setattr(fixed, "PARENT", {**fixed.PARENT, "terminal_identity": reader.TERMINAL_IDENTITY,
        "claim_identity": terminal["claim_identity"]})
    before = deepcopy((api.trees, api.writers, api.branches))
    old._environment(monkeypatch)
    root = grade._root(tmp_path / "historical-parent-controls", new=True)
    with retained._session(api, response_bytes_limit=output.MAX_RECORD_BYTES) as (transport, token, deadline):
        records = fixed.parent_controls(transport, retained._target(), root, token, deadline)
    assert [revision for _, revision in records] == [reader.TERMINAL, reader.CLAIM]
    assert api.downloads == [(reader.TERMINAL, bridge.TERMINAL_PATH), (reader.TERMINAL, bridge.TERMINAL_PATH),
                             (reader.CLAIM, bridge.CLAIM_PATH)]
    assert (api.trees, api.writers, api.branches) == before and not api.commits
    facade = reader._ReadOnlyGrade(api, api.repo, TOKEN)
    for absent in ("create_commit", "create_branch", "create_repo", "list_repo_tree", "upload_file", "delete_file"):
        assert not hasattr(facade, absent)
    count = len(api.calls)
    for revision in (reader.KEEP_R2_TERMINAL, grade.BRANCH, "main"):
        with pytest.raises(output.OutputPublicationRefused, match="^grade_readout_metadata_refused$"):
            facade.repo_info(repo_id=api.repo, repo_type="dataset", revision=revision, token=TOKEN, timeout=1)
    with pytest.raises(output.OutputPublicationRefused, match="^grade_readout_paths_refused$"):
        facade.get_paths_info(repo_id=api.repo, repo_type="dataset", revision=reader.CLAIM,
            paths=[bridge.CLAIM_PATH], expand=True, token=TOKEN)
    assert len(api.calls) == count
