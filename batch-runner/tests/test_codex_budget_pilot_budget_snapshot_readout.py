"""Selected-only budget observations over genuine offline writer histories.

The ordinary/NG writers are reused once; only isolated copies are mutated.
These snapshots, revisions and accounting fixtures are not live measurements.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_budget_pilot_ungraded as ungraded
import step8_grade as step8
from core.result_fingerprint import inference_result_fingerprint
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task3_a1_readout as controls
from . import test_codex_budget_pilot_task4_a1_ungraded_readout as ng
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — forbid live execution
from .test_codex_budget_pilot_task3_grading_chain import _Capture

FIELDS = ("total_seconds", "started_unix", "expires_unix", "remaining_seconds",
          "wait_seconds", "attempts_admitted", "native_resumes")
SNAPSHOT = dict(zip(FIELDS, (10800, 1000.25, 11800.25, 9170.5, 17.75, 3, 2)))
PRIVATE = "PRIVATE https://private.invalid/checkpoint?thread=PRIVATE"
ADVANCED = "f8" * 20
VALID = ("recorded", "zero", "partial", "empty", "absent", "unstarted", "extra")
INVALID = ("bool_seconds", "string_seconds", "negative_seconds", "zero_total", "null_wait",
           "float_admissions", "bool_resumes", "negative_count", "snapshot_list", "snapshot_null",
           "observation_list", "nan", "infinity", "task_identity", "fingerprint", "hash", "size",
           "lost_response", "claim", "parent", "source", "no_observability")


@pytest.fixture(scope="module")
def historical_budget_source(approved_pilot_source):
    """Compile and copy the retained writer's real frozen source, not this runtime."""
    import gpt54_comparison_preflight as comparison

    with pytest.MonkeyPatch.context() as source:
        source.setattr(comparison, "ROOT", approved_pilot_source)
        source.setattr(pilot, "ROOT", approved_pilot_source)
        yield


@pytest.fixture(scope="module")
def history(tmp_path_factory, historical_budget_source):
    # Build the legacy fixed-revision case before entering the inherited
    # history's constructor guards. No old test function is executed.
    capture = _Capture()
    local = tmp_path_factory.mktemp("budget-legacy-writer")
    with pytest.MonkeyPatch.context() as patch:
        base.boundaries.__wrapped__(patch)
        current = writer.case.__wrapped__(local, patch, writer.compilations.__wrapped__(),
                                          writer.compiled_cells.__wrapped__())
        with redirect_stdout(capture.out), redirect_stderr(capture.err):
            revision, path, terminal = writer._writer(current, capture, local, patch, "graded")
        legacy = SimpleNamespace(api=copy.deepcopy(current.api), context=copy.deepcopy(current.context),
                                 revision=revision, path=path, terminal=terminal)
    # This fixture constructs its genuine failure before installing constructor
    # guards, then retains the actual ordinary predecessor and native NG record.
    source = ng.history.__wrapped__(tmp_path_factory, _variants=("partial_cost",))
    shared = next(source)
    try:
        record = shared.rows["partial_cost"]
        ordinary = SimpleNamespace(api=record.api, context=shared.previous_context,
            revision=shared.previous_revision, path=shared.previous_path,
            terminal=pilot._json_object(record.api.trees[shared.previous_revision][shared.previous_path]))
        yield {"ordinary": ordinary, "ng": record, "legacy": legacy}
    finally:
        source.close()


def _payload_variant(payload, scenario):
    snapshot = copy.deepcopy(SNAPSHOT)
    if scenario == "zero":
        snapshot.update(started_unix=0, expires_unix=10800, remaining_seconds=0,
                        wait_seconds=0, attempts_admitted=0, native_resumes=0)
    elif scenario == "partial":
        snapshot = {"remaining_seconds": 0, "attempts_admitted": 1}
    elif scenario == "empty":
        snapshot = {}
    elif scenario == "unstarted":
        snapshot.update(started_unix=None, expires_unix=None, remaining_seconds=None,
                        wait_seconds=0, attempts_admitted=0, native_resumes=0)
    elif scenario == "extra":
        snapshot.update(thread_id=PRIVATE, checkpoint_path=PRIVATE, provider_text=PRIVATE,
                        attempt_seconds=1800, retained_attempts=999, resume_rounds_used=999)
    changes = {
        "bool_seconds": ("remaining_seconds", False), "string_seconds": ("wait_seconds", "17.75"),
        "negative_seconds": ("remaining_seconds", -1), "zero_total": ("total_seconds", 0),
        "null_wait": ("wait_seconds", None), "float_admissions": ("attempts_admitted", 3.0),
        "bool_resumes": ("native_resumes", True), "negative_count": ("native_resumes", -1),
        "nan": ("wait_seconds", float("nan")), "infinity": ("started_unix", float("inf")),
    }
    if scenario in changes:
        key, value = changes[scenario]
        snapshot[key] = value
    row = payload["results"][0]
    row.setdefault("observability", {})["task_deadline"] = snapshot
    if scenario == "absent":
        del row["observability"]["task_deadline"]
    elif scenario == "no_observability":
        # Unlike an absent deadline, a missing required native result field is
        # invalid. Keep the unchanged Step2 producer validator authoritative.
        del row["observability"]
    elif scenario in {"snapshot_list", "snapshot_null"}:
        row["observability"]["task_deadline"] = [] if scenario == "snapshot_list" else None
    elif scenario == "observation_list":
        row["observability"] = []
    elif scenario == "task_identity":
        row["task_id"] = "00000000-0000-0000-0000-000000000000"
    return snapshot


def _isolate(record, kind, scenario, patch):
    """Rebind isolated input/control mutations with the native identity helpers."""
    api, context = copy.deepcopy(record.api), copy.deepcopy(record.context)
    revision, path = record.revision, record.path
    terminal = pilot._json_object(api.trees[revision][path])
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][grading._paths(context.cell)[0]])
    observation = terminal["binding"]["retained"]
    input_revision, output_revision = observation["terminal_commit"], observation["output_commit"]
    _, input_path, prefix = retained._paths(context.cell)
    original = pilot._json_object(api.trees[input_revision][input_path])
    manifest_path, member = prefix + "/" + output.MANIFEST, prefix + "/step2_inference_results.json"
    manifest = pilot._json_object(api.trees[output_revision][manifest_path])
    payload = pilot._json_object(api.trees[output_revision][member])
    expected = _payload_variant(payload, scenario)
    if scenario not in {"nan", "infinity"}:
        payload["result_fingerprint"] = inference_result_fingerprint(payload)
    if scenario == "fingerprint":
        payload["result_fingerprint"] = "9" * 64
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    identity = pilot._identity(data)
    if scenario == "size":
        identity["size"] += 1
    next(row for row in manifest["files"] if row["role"] == "inference_result").update(identity)
    manifest_bytes = retained._encoded(manifest)
    original["manifest_identity"] = pilot._identity(manifest_bytes)
    original["completion"]["artifacts"]["result"] = identity
    for item in original["output_objects"]:
        if item["path"] == member:
            item.update(retained._object(member, data), **identity)
        elif item["path"] == manifest_path:
            item.update(retained._object(manifest_path, manifest_bytes))
    for commit in (output_revision, input_revision):
        api.trees[commit][member], api.trees[commit][manifest_path] = data, manifest_bytes
    encoded = retained._encoded(original)
    api.trees[input_revision][input_path] = encoded
    observation.update(terminal_sha256=pilot._identity(encoded)["sha256"],
                       manifest_sha256=original["manifest_identity"]["sha256"])
    request = pilot._digest(original["completion"]) if context.terminal_request is not None else input_revision
    if kind != "legacy":
        registry = grading.TASK4_RETAINED if kind == "ng" else grading.TASK3_SUCCESSORS
        patch.setitem(registry, context.cell["cell_id"], (registry[context.cell["cell_id"]][0], request))
    context = readout._writer_context(request)
    terminal["binding"]["approval_request_sha256"] = grading._context_approval(context, terminal["binding"]["github_run"])
    if kind == "ng":
        terminal["inference_completion"] = copy.deepcopy(original["completion"])
        if scenario not in {"nan", "infinity", "fingerprint"}:
            files = {"step2_inference_results.json": data,
                     Path(pilot.LEDGER).name: api.trees[output_revision][prefix + "/" + Path(pilot.LEDGER).name]}
            native = grading._inference_identity(context, {"terminal": original}, files, api.repo)
            terminal["binding"]["inference_identity_sha256"] = pilot._identity(retained._encoded(native))["sha256"]
        # The native NG binding also includes the completion request. Rebuild
        # it after the isolated input mutation, not just its approval hash.
        terminal["binding"] = ungraded._binding(context, {"observation": observation, "terminal": original},
            terminal["binding"]["inference_identity_sha256"], terminal["binding"]["predecessor_entry"],
            terminal["binding"]["github_run"])
    if scenario == "claim":
        claim["format"] = "PRIVATE"
    elif scenario == "parent":
        claim["predecessor"]["sha256"] = "9" * 64
    elif scenario == "source":
        terminal["binding"]["source_sha"] = "9" * 40
    controls._store_grade(api, revision, path, terminal, claim)
    # A later unrelated ref advance must not change which immutable bytes win.
    advanced = ADVANCED
    assert advanced not in api.trees  # Never alias a historical claim revision.
    api.seed(advanced, revision, {"unrelated/PRIVATE": b"PRIVATE"})
    api.branches[grading.BRANCH] = advanced
    return SimpleNamespace(api=api, context=context, revision=revision, terminal=terminal, request=request,
        output_revision=output_revision, input_revision=input_revision, member=member, expected=expected)


@pytest.mark.parametrize("kind", ("ordinary", "ng"))
@pytest.mark.parametrize("scenario", (*VALID, *INVALID))
def test_selected_budget_snapshot(history, tmp_path, monkeypatch, capsys, kind, scenario):
    _check(history[kind], kind, scenario, tmp_path, monkeypatch, capsys)


def test_selected_budget_snapshot_legacy_revision(history, tmp_path, monkeypatch, capsys):
    _check(history["legacy"], "legacy", "recorded", tmp_path, monkeypatch, capsys)


def _check(record, kind, scenario, tmp_path, patch, capsys):
    selected = _isolate(record, kind, scenario, patch)
    api, context = selected.api, selected.context
    readers, proved, payloads, downloads, active_grants, errors = [], [], [], [], [], []
    initialize = readout._ReadOnlyGrade.__init__
    selected_result = readout._ReadOnlyGrade.selected_result
    verify, predecessor = readout._verified_grade, readout._verify_predecessor
    ng_verify, project = readout._verified_ungraded, readout._budget_snapshot
    raw_download, fetch = api.hf_hub_download, grading._fetch
    error_context = output._error_context

    def forbidden(*args, **kwargs):
        raise AssertionError("budget readout crossed a writer/model boundary")

    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "_entry_contract", "_ready"):
        patch.setattr(grading, name, forbidden)
    for target, name in ((api, "create_commit"), (api, "create_branch"), (output, "_hf_client"),
                         (ungraded, "record"), (ungraded, "prepare_record"), (step8, "main"),
                         (adapter, "materialize_pilot_grading_input"), (base.Child, "process")):
        patch.setattr(target, name, forbidden)

    def denied(reader, revision, member):
        before = list(api.calls)
        with pytest.raises(ValueError, match="grade_readout_download_refused"):
            reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                revision=revision, filename=member, cache_dir=tmp_path / "denied",
                force_download=True, local_files_only=False, etag_timeout=1)
        assert api.calls == before

    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)
        denied(reader, selected.output_revision, selected.member)
        with pytest.raises(ValueError, match="grade_readout_selected_result_not_verified"):
            selected_result(reader, context, {}, tmp_path / "not-verified", 1)

    def verify_grade(reader, current, *args):
        assert reader._selected_verified is reader._selected_download is None
        result = verify(reader, current, *args)
        assert reader._selected_verified is reader._selected_download is None
        proved.append(("grade", current.cell["cell_id"]))
        if kind != "ng":
            denied(readers[0], selected.output_revision, selected.member)
        return result

    def verify_parent(reader, current, *args):
        assert reader._selected_verified is reader._selected_download is None
        denied(reader, selected.output_revision, selected.member)
        result = predecessor(reader, current, *args)
        proved.append(("parent", current.cell["cell_id"]))
        denied(reader, selected.output_revision, selected.member)
        return result

    def verify_ng(reader, current, *args):
        assert reader._selected_verified is reader._selected_download is None
        result = ng_verify(reader, current, *args)
        proved.append(("ng", current.cell["cell_id"]))
        return result

    def budget(payload):
        assert ("ng" if kind == "ng" else "grade", context.cell["cell_id"]) in proved
        if kind == "ordinary":
            assert ("parent", context.cell["cell_id"]) in proved
        assert all(reader._selected_download is reader._selected_verified is None for reader in readers)
        payloads.append(copy.deepcopy(payload))
        return project(payload)

    def download(**kwargs):
        downloads.append((kwargs["revision"], kwargs["filename"]))
        chosen = (kwargs["revision"], kwargs["filename"]) == (selected.output_revision, selected.member)
        if chosen and kind != "ng":
            assert ("grade", context.cell["cell_id"]) in proved
            assert kind == "legacy" or ("parent", context.cell["cell_id"]) in proved
            # The one-use grant was consumed BEFORE calling the transport.
            for reader in readers:
                denied(reader, selected.output_revision, selected.member)
                denied(reader, ADVANCED, selected.member)
                denied(reader, selected.output_revision, selected.member + ".other")
            assert all(reader._selected_download is None for reader in readers)
        path = Path(raw_download(**kwargs))
        if chosen and scenario == "hash":
            data = path.read_bytes()
            path.write_bytes(b"!" + data[1:])
        if chosen and scenario == "lost_response":
            raise output.OutputPublicationRefused("hf_transport_failed")
        return str(path)

    def bounded_fetch(reader, repo, revision, member, *args):
        if reader._selected_download is not None:
            assert kind != "ng" and reader is readers[0]
            assert (revision, member) == (selected.output_revision, selected.member)
            active_grants.append((revision, member))
            denied(reader, ADVANCED, member)
            denied(reader, selected.input_revision, member)
            denied(reader, revision, member + ".other")
            denied(reader, revision, member.rsplit("/", 1)[0] + "/" + Path(pilot.LEDGER).name)
            for parent in readers[1:]:
                denied(parent, revision, member)
                # Parent result permission cannot be inferred from its metadata.
                for commit, members in parent._metadata_paths.items():
                    for name in members:
                        if name.endswith("/step2_inference_results.json"):
                            denied(reader, commit, name)
            assert reader._selected_download == (revision, member)
        return fetch(reader, repo, revision, member, *args)

    def record_error(error):
        errors.append(str(error))
        return error_context(error)

    patch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    patch.setattr(readout, "_verified_grade", verify_grade)
    patch.setattr(readout, "_verify_predecessor", verify_parent)
    patch.setattr(readout, "_verified_ungraded", verify_ng)
    patch.setattr(readout, "_budget_snapshot", budget)
    patch.setattr(api, "hf_hub_download", download)
    patch.setattr(grading, "_fetch", bounded_fetch)
    patch.setattr(output, "_error_context", record_error)
    if kind == "ng":
        patch.setattr(readout._ReadOnlyGrade, "selected_result", forbidden)

    for key, value in {"GITHUB_SHA": ng.OBSERVER, "PILOT_WORKFLOW_SHA": ng.OBSERVER,
        "GITHUB_JOB": "pilot-readout", "GITHUB_RUN_ID": "900080", "PILOT_GRADE_PAID_APPROVAL": "false",
        "HF_TOKEN": base.TOKEN}.items():
        patch.setenv(key, value)
    for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256"):
        patch.delenv(key, raising=False)
    api.calls.clear()
    if hasattr(api, "reads"):
        api.reads.clear()
    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches, api.events))
    args = ["--selector", readout.SELECTOR, "--reviewed-source-sha", ng.OBSERVER,
            "--terminal-revision", selected.request, "--root", str(tmp_path / "readout"), "--phase", "readout"]
    transport = SimpleNamespace(require_source=lambda plan, parent: None)
    code = grading.main(args, _test_api=api, _test_transport=transport)
    captured = capsys.readouterr()
    text = captured.out + captured.err
    public = json.loads(text)
    assert len(text.splitlines()) == 1
    assert all(private not in text for private in ("PRIVATE", "https://", base.TOKEN, api.repo, str(tmp_path)))
    assert (api.trees, api.writers, api.parents, api.branches, api.events) == frozen
    assert all(reader._selected_verified is reader._selected_download is None for reader in readers)
    for reader in readers:
        if kind != "ng":
            denied(reader, selected.output_revision, selected.member)
        with pytest.raises(ValueError, match="grade_readout_selected_result_not_verified"):
            selected_result(reader, context, {}, tmp_path / "after", 1)
    result_reads = [(revision, member) for revision, member in downloads
                    if member.endswith("/step2_inference_results.json")]
    assert set(result_reads) <= {(selected.output_revision, selected.member)}
    assert len(result_reads) <= (2 if kind == "ng" else 1)
    assert len(active_grants) <= (0 if kind == "ng" else 1)
    if scenario in {"claim", "parent", "source", "size"}:
        assert result_reads == [] and active_grants == []
    if scenario in VALID:
        assert code == 0, (public["stage"], errors)
        # NG already fetches once for native verification and once for its
        # existing projection. Budget access must not add a third fetch.
        assert len(result_reads) == (2 if kind == "ng" else 1)
        assert len(active_grants) == (0 if kind == "ng" else 1)
        assert len(payloads) == 1
        assert payloads[0] == pilot._json_object(api.trees[selected.output_revision][selected.member])
        snapshot = public["inference_budget_snapshot"]
        assert set(snapshot) == {*FIELDS, "missing"}
        expected = {} if scenario in {"absent", "no_observability"} else selected.expected
        assert {key: snapshot[key] for key in FIELDS} == {key: expected.get(key) for key in FIELDS}
        assert snapshot["missing"] == {key: "not_recorded" if key not in expected else "unavailable"
                                       for key in FIELDS if key not in expected or expected[key] is None}
        assert public["inference_output_commit"] == selected.output_revision
        assert public["observed_branch_head"] == ADVANCED
        if kind == "ng":
            assert public["record_kind"] == "model_free_ungraded" and public["score"] is None
            assert public["scored_tasks"] == 0 and public["recorder_accounting"]["known_cost_usd"] is None
            receipt = public["inference_accounting"]["recorded_task_cost"]
            assert receipt["status"] == "partial" and "call_reachability_unknown" in receipt["missing_reasons"]
        else:
            assert public["grade_state"] == "graded" and public["scored_tasks"] == 1
            assert public["recorded_task_cost"]["estimated_cost_usd"] is None
        assert not any(key in text for key in ("checkpoint_path", "thread_id", "provider_text", "retained_attempts"))
    else:
        assert code == 2 and public["outcome"] == "refused", public
        assert public["reason"] == "grade_readout_contract_refused" and "inference_budget_snapshot" not in public
        if scenario not in {"claim", "parent", "source", "size"}:
            assert result_reads, (public["stage"], errors)
        if scenario in {"bool_seconds", "string_seconds", "negative_seconds", "zero_total", "null_wait",
                        "float_admissions", "bool_resumes", "negative_count", "snapshot_list", "snapshot_null"}:
            assert "grade_readout_budget_snapshot_refused" in errors, errors
        elif scenario == "no_observability":
            assert "Step 2 terminal result fields are incomplete" in errors, errors
        elif scenario == "observation_list":
            assert "Step 2 result observability is invalid" in errors, errors
        elif scenario == "lost_response":
            assert "hf_transport_failed" in errors, errors
