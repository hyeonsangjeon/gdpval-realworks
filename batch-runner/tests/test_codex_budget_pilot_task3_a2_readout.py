"""Only the fixed A2 readout, over one genuine synthetic C1/C2/B2 prefix.

Synthetic payloads and revisions are not actual private-grade evidence. The
reader must verify A2/B2 and only C2's intrinsic terminal-control backing.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
from types import SimpleNamespace

import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grading
import codex_budget_pilot_retention as retained
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as task2
from . import test_codex_budget_pilot_task3_b2_readout as b2_reader
from . import test_codex_budget_pilot_task3_c_readout as c_reader
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — live boundaries blocked

CELL = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r2"
RECORDED = (17, "36289615941", "36232859421",
            "f4de6c1d36c8f3a2c077be9e4be370545eeb5a11d9513752caa4d40bd08e1bd8", "B_r2")
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{70_000 + offset:040x}" for offset in range(1, 5))


@pytest.fixture(scope="module")
def history(tmp_path_factory, *, _scenarios=c_reader.VARIANTS):
    ordinal, grade_run, inference_run, original_request, prior = RECORDED
    run = {"id": grade_run, "job": "pilot-live", "attempt": 1}
    assert readout.TASK3_A2_CELL == CELL
    assert b2_reader.CELL == c_reader.PREFIX + prior == readout.TASK3_B2_CELL
    assert grading.TASK3_SUCCESSORS[CELL] == (inference_run, original_request)
    assert readout.TASK3_SUCCESSOR_READOUTS[CELL] == (ordinal, readout.TASK3_B2_CELL, run)
    actual = readout._writer_context(original_request)
    actual_parent = readout._writer_context(b2_reader.RECORDED[3])
    assert actual.cell["cell_id"] == CELL and actual.controller_source_sha == c_reader.WRITER
    assert actual.plan["reviewed_source_sha"] == c_reader.PRODUCER
    assert actual.plan["order"][15:18] == [readout.TASK3_C2_CELL, readout.TASK3_B2_CELL, CELL]
    assert actual.plan["order"][12:18] == [grading.TASK3_A1_CELL, *readout.TASK3_SUCCESSOR_READOUTS]
    assert len(actual.plan["order"]) == 30
    assert actual.terminal_revision == "" and actual.terminal_request == original_request
    assert actual.run.grader_config_json == actual_parent.run.grader_config_json
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert readout._writer_run(actual) == run
    assert readout._writer_run(actual_parent) == {"id": "36288201352", "job": "pilot-live", "attempt": 1}

    # Only graded C1/C2/B2 prefix states are constructed; no old test node runs.
    prefix = b2_reader.history.__wrapped__(tmp_path_factory, _scenarios=("graded",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task3-a2-readout-history")
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    capture = _Capture()
    try:
        with pytest.MonkeyPatch.context() as patch:
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                previous = initial.rows["graded"]
                api = copy.deepcopy(previous.api)
                assert not {CLAIM, OUTPUT, TERMINAL, ADVANCED}.intersection(api.trees)
                seed_context = grading.compile_request("pilot/" + CELL, c_reader.PRODUCER, TERMINAL)
                seeded = SimpleNamespace(context=seed_context, api=api)
                with patch.context() as seed:
                    for key, value in {"SOURCE": c_reader.PRODUCER, "CLAIM": CLAIM,
                                       "OUTPUT": OUTPUT, "TERMINAL": TERMINAL}.items():
                        seed.setattr(base, key, value)
                    base._seed_outputs(seeded, directory, extra_deliverable=True)
                claim_path, terminal_path, input_prefix = retained._paths(seed_context.cell)
                input_parent = initial.input_terminal
                prior_bytes = api.trees[input_parent][retained._paths(previous.context.cell)[1]]
                prior_inference = pilot._json_object(prior_bytes)
                seeded.claim["binding"]["github_run"] = {"id": inference_run, "job": "cell", "attempt": 1}
                seeded.claim["expected_parent"] = input_parent
                seeded.claim["predecessor"] = {"cell_id": readout.TASK3_B2_CELL, "terminal_commit": input_parent,
                    "terminal_sha256": pilot._identity(prior_bytes)["sha256"],
                    "output_commit": prior_inference["output_commit"],
                    "manifest_sha256": prior_inference["manifest_identity"]["sha256"]}
                seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
                files = {name: data for name, data in api.trees[OUTPUT].items() if name.startswith(input_prefix + "/")}
                api.seed(CLAIM, input_parent, {claim_path: retained._encoded(seeded.claim)})
                api.seed(OUTPUT, CLAIM, files)
                api.seed(TERMINAL, OUTPUT, {terminal_path: retained._encoded(seeded.terminal)})
                api.branches[retained.BRANCH] = TERMINAL
                api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
                request = pilot._digest(seeded.terminal["completion"])
                patch.setitem(grading.TASK3_SUCCESSORS, CELL, (inference_run, request))
                previous_claim = pilot._json_object(api.trees[previous.terminal["claim_commit"]][
                    grading._paths(previous.context.cell)[0]])
                backing_cell = previous.context.plan["cells"][15]
                assert previous_claim["predecessor"]["cell_id"] == backing_cell["cell_id"] == readout.TASK3_C2_CELL
                shared = SimpleNamespace(rows={}, request=request, cell=CELL, ordinal=ordinal,
                    input_claim=CLAIM, input_output=OUTPUT, input_terminal=TERMINAL, advanced=ADVANCED,
                    previous_context=copy.deepcopy(previous.context), previous_revision=previous.revision,
                    previous_path=previous.path, backing_cell=backing_cell,
                    backing_revision=previous_claim["expected_parent"], backing_path=grading._paths(backing_cell)[1],
                    historical_path=initial.historical_path)
                for scenario in _scenarios:
                    destination = directory / scenario
                    destination.mkdir()
                    current = SimpleNamespace(api=copy.deepcopy(api), workflow=workflow,
                        context=readout._writer_context(request), request=request, root=destination / "grade")
                    current.transport = base.Child(current)
                    current.api.calls.clear()
                    current.api.reads.clear()
                    current.api.events.clear()
                    with patch.context() as selected:
                        selected.setattr(base, "OUTPUT", OUTPUT)
                        selected.setenv("HF_TOKEN", base.TOKEN)
                        task2._authorize(current, destination, selected, grade_run)
                        revision, path, terminal = writer._writer(current, capture, destination, selected, scenario)
                    claim = retained._read(current.root / "claim-receipt.json")["claim"]
                    assert claim["expected_parent"] == previous.revision
                    assert claim["predecessor"] == {"cell_id": readout.TASK3_B2_CELL, "revision": previous.revision,
                                                   **pilot._identity(retained._encoded(previous.terminal))}
                    assert terminal["binding"]["github_run"] == run
                    assert terminal["binding"]["controller_source_sha"] == c_reader.WRITER
                    assert current.transport.calls == 1 and current.api.events == ["grade_claim", "judge", "grade_output"]
                    assert all(current.api.trees[rev] == data for rev, data in api.trees.items())
                    shared.rows[scenario] = SimpleNamespace(api=current.api, context=current.context,
                                                            revision=revision, path=path, terminal=terminal)
            yield shared
    finally:
        prefix.close()


@pytest.mark.parametrize("scenario", c_reader.SCENARIOS)
def test_fixed_task3_a2_grade_readout(history, tmp_path, monkeypatch, capsys, scenario):
    c_reader._check_successor_readout(history, RECORDED, tmp_path, monkeypatch, capsys, scenario)
