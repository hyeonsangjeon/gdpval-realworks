"""The stage-1 gold-ceiling contract.

Grading the benchmark's own expert answers answers one question: how high can
this grader score at all? Every model score already published is read against
that ceiling, so the measurement is only worth anything if the thing measured
cannot drift. These tests pin the parts that would drift silently -- which 30
tasks, which settings, which dataset commit -- and the parts that would let a
ceiling be mistaken for a competitor's result.

Spec: tasks/rebuilding_grading_task/300-gold-ceiling.md
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap

import pytest
import yaml

import step8_grade as s8
from core.inference_manifest import GOLD_PROVENANCE_STATUS
from scripts import preflight_grading_renderer as preflight


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = REPO_ROOT / "batch-runner"
GOLD_CONFIG_PATH = BATCH_RUNNER / "grading_configs/gold_ceiling_30_v2_sol_max.yaml"
PRODUCTION_CONFIG_PATH = BATCH_RUNNER / "grading_configs/default_v2_sol_max.yaml"
GOLD_EXPERIMENT_PATH = BATCH_RUNNER / "experiments/exp_gold_baseline.yaml"
GRADE_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grade-run.yml"
SPEC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/300-gold-ceiling.md"

#: The dataset commit everything in stage 1 is frozen to. Written out rather
#: than read from the config, so a test that checks the config against this
#: constant is checking something.
PINNED_DATASET_SHA = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
SAMPLE_SIZE = 30


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _manifest_module():
    """Import the manifest builder by path.

    It lives under scripts/ with no package, and it is the only place that
    knows how a task's row maps to its gold files -- re-deriving that rule here
    would be re-deriving the thing under test.
    """
    spec = importlib.util.spec_from_file_location(
        "_gold_manifest_builder",
        BATCH_RUNNER / "scripts/build_gold_deliverable_manifest.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Which 30, and are they still the same 30
# --------------------------------------------------------------------------


def test_pinned_sample_is_the_manifest_prefix_not_a_typed_list():
    """The config's 30 IDs must be re-derivable from the committed manifest.

    A hand-kept list drifts the moment anyone edits one character, and a
    one-character drift would be a different sample scored against the same
    threshold. Deriving the list here means a drift is a red test rather than a
    quietly different measurement.
    """
    module = _manifest_module()
    derived = module.gold_bearing_task_ids(module.load_manifest())[:SAMPLE_SIZE]
    pinned = _load_yaml(GOLD_CONFIG_PATH)["rerun_identity"]["task_ids"]

    assert pinned == derived
    assert len(pinned) == SAMPLE_SIZE
    assert len(set(pinned)) == SAMPLE_SIZE


def test_pinned_sample_is_ordered_the_way_the_grader_demands():
    """`filter_tasks_for_config` refuses a pin that is not in source order.

    That refusal is the safety net; this is the tripwire in front of it. The
    manifest records each task's row position, so the pinned list is in source
    order exactly when those positions ascend.
    """
    module = _manifest_module()
    positions = {
        task["task_id"]: task["position"]
        for task in module.load_manifest()["tasks"]
    }
    pinned = _load_yaml(GOLD_CONFIG_PATH)["rerun_identity"]["task_ids"]

    pinned_positions = [positions[task_id] for task_id in pinned]
    assert pinned_positions == sorted(pinned_positions)


def test_every_pinned_task_actually_has_an_expert_answer():
    """A task with no gold file would score zero and drag the ceiling down.

    That would read as a grader defect when it is really an empty input, so the
    sample skips the 35 tasks the dataset ships without an answer. Checking it
    here means the skip stays deliberate.
    """
    module = _manifest_module()
    by_task = {task["task_id"]: task for task in module.load_manifest()["tasks"]}
    pinned = _load_yaml(GOLD_CONFIG_PATH)["rerun_identity"]["task_ids"]

    for task_id in pinned:
        assert by_task[task_id]["files"], f"{task_id} has no gold deliverable"


# --------------------------------------------------------------------------
# The frozen contract: settings, rubric commit, corpus size
# --------------------------------------------------------------------------


def test_gold_config_grades_with_production_settings_unchanged():
    """A ceiling measured under different settings is not their ceiling.

    Every runtime block has to be what the graded runs used, byte for byte:
    same judge and reasoning effort, same tool ops and caps, same perception
    models, same prompts, same rate-limit guard. Only identity may differ.
    """
    gold = _load_yaml(GOLD_CONFIG_PATH)
    production = _load_yaml(PRODUCTION_CONFIG_PATH)

    for block in ("judge", "grader", "tpm_guard", "prompt", "output"):
        assert gold[block] == production[block], f"{block} diverged"

    # The rubric block may differ in exactly one field: the revision, pinned to
    # a commit here where production follows `main`. Following a branch is what
    # stage 2's three repeats cannot tolerate.
    assert {k: v for k, v in gold["rubric"].items() if k != "revision"} == {
        k: v for k, v in production["rubric"].items() if k != "revision"
    }
    assert production["rubric"]["revision"] == "main"
    assert gold["rubric"]["revision"] == PINNED_DATASET_SHA


def test_gold_config_pins_one_commit_for_both_rubric_and_corpus():
    """For a gold corpus the dataset IS the inference.

    No model ran, so the revision that supplied the answers has to be the
    revision that supplied the rubric being scored against them. Two different
    commits here would score one release's answers with another's rubric.
    """
    identity = _load_yaml(GOLD_CONFIG_PATH)["rerun_identity"]

    assert identity["rubric_commit_sha"] == PINNED_DATASET_SHA
    assert identity["inference_revision"] == PINNED_DATASET_SHA
    assert identity["experiment_id"] == "exp_gold_baseline"
    assert identity["expected_task_count"] == SAMPLE_SIZE


def test_gold_config_does_not_forgive_missing_provenance():
    """`allow_legacy_missing_provenance` must stay absent.

    It forgives a submission whose Azure routes were never recorded. Here no
    inference ran, so there is no route that could be missing -- setting it
    would be claiming to excuse a gap this corpus cannot have, and would put a
    real forgiveness switch on a config nobody would think to check.
    """
    identity = _load_yaml(GOLD_CONFIG_PATH)["rerun_identity"]

    assert "allow_legacy_missing_provenance" not in identity


def test_gold_config_passes_the_grader_validator():
    s8.validate_grading_config(_load_yaml(GOLD_CONFIG_PATH))


def test_gold_experiment_yaml_declares_the_dataset_not_a_submission():
    """The downloader must be told to build from gold, fail-closed.

    Absent, `inference_source` means `submission`, and the run would go looking
    for output that was never produced. The declaration is also what keeps this
    file from ever being mistaken for an experiment.
    """
    experiment = _load_yaml(GOLD_EXPERIMENT_PATH)

    assert experiment["data"]["source"] == "openai/gdpval"
    assert experiment["data"]["inference_source"] == "gold_deliverables"
    # No default may speak for a run that had no model. `ExperimentConfig`
    # fills an absent deployment with "gpt-4", which would put a model that
    # never ran on the record.
    assert experiment["condition_a"]["model"]["deployment"] == "gold-deliverable"


def test_gold_experiment_yaml_loads_through_both_readers():
    """Two independent loaders read this file, and both run before any spend.

    A file that parses by eye but not by `ExperimentConfig` would fail at
    dispatch; one the downloader cannot resolve would fail after checkout. Both
    are cheap to catch here and expensive to catch there.
    """
    from core.experiment_config import ExperimentConfig

    config = ExperimentConfig.from_yaml(str(GOLD_EXPERIMENT_PATH))
    assert config.condition_a.model.deployment == "gold-deliverable"

    spec = importlib.util.spec_from_file_location(
        "_gold_downloader",
        BATCH_RUNNER / "scripts/download_inference_from_hf.py",
    )
    downloader = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(downloader)

    cwd = Path.cwd()
    os.chdir(BATCH_RUNNER)
    try:
        assert downloader.resolve_repo_id("exp_gold_baseline") == "openai/gdpval"
        assert (
            downloader.resolve_inference_source("exp_gold_baseline")
            == downloader.GOLD_INFERENCE_SOURCE
        )
    finally:
        os.chdir(cwd)


# --------------------------------------------------------------------------
# A ceiling must never be publishable as a competitor's result
# --------------------------------------------------------------------------


def test_gold_provenance_status_is_a_value_the_schema_accepts():
    """The written grade is validated against the schema before it lands.

    A status the schema does not list would fail after the run has already been
    paid for, which is the most expensive possible place to find a typo.
    """
    schema = json.loads(
        (BATCH_RUNNER / "schemas/grade.schema.json").read_text(encoding="utf-8")
    )
    enum = schema["properties"]["source_azure_ai_provenance_status"]["enum"]

    assert GOLD_PROVENANCE_STATUS in enum
    # Distinct from every status a real submission can carry: those describe
    # how much is known about a model's route, and this one says no model ran.
    assert GOLD_PROVENANCE_STATUS not in {
        "runtime-verified",
        "verified-sidecar",
        "legacy-missing",
        "local-runtime",
    }


@pytest.fixture
def _typed_azure_ai_route(monkeypatch):
    """The one route step8 will accept, with every ambient credential cleared.

    A run that picked up a stray key from the developer's shell would prove
    nothing about the route the grading job actually takes, and step8 refuses
    to start without an explicit profile -- so the refusal has to be satisfied
    deliberately here rather than by whatever happens to be exported.
    """
    for name in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_API_KEY",
        "AZURE_OPENAI_AD_TOKEN",
        "AZURE_CLIENT_SECRET",
        "OPENAI_API_KEY",
        "FOUNDRY_PROJECT_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "direct-v1")
    monkeypatch.setenv(
        "AZURE_OPENAI_V1_ENDPOINT",
        "https://test-account.services.ai.azure.com/openai/v1/",
    )


def test_gold_run_stays_diagnostic_even_when_the_whole_corpus_is_pinned(
    monkeypatch, tmp_path, _typed_azure_ai_route
):
    """Pinning everything lifts the scope rule. It must not lift this one.

    A complete pin proves nothing was dropped, which is why it publishes a
    `legacy-missing` submission. It cannot make a ceiling publishable:
    `scripts/aggregate-grades.mjs` reads the canonical path and has no way to
    say "this is the ceiling, not a competitor", so a gold run landing there
    would appear on the dashboard as a rival to the models it exists to
    calibrate. What makes it unpublishable is what it is, not how much of it
    was graded.
    """
    from tests.test_step8_grade import (
        INFERENCE_SHA,
        _FakeGrader,
        _FakeLoader,
        _setup_workspace,
    )

    _setup_workspace(tmp_path)
    inference_path = tmp_path / "workspace/step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["azure_ai_provenance_status"] = GOLD_PROVENANCE_STATUS
    inference_path.write_text(json.dumps(inference), encoding="utf-8")

    task_ids = ["task-001", "task-002", "task-003"]
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["schema_version"] = "2.0"
    config["rubric"]["revision"] = _FakeLoader().rubric_sha
    config["rerun_identity"] = {
        "experiment_id": "exp998_smoke_baseline_sample",
        "expected_task_count": len(task_ids),
        "rubric_commit_sha": _FakeLoader().rubric_sha,
        "inference_revision": INFERENCE_SHA,
        "task_ids": task_ids,
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr(
        "sys.argv",
        [
            "step8_grade.py",
            "exp998_smoke_baseline_sample",
            "--config",
            "grading_configs/default.yaml",
            "--force",
        ],
    )

    assert s8.main() == 0

    # Nothing on the canonical path -- that is the path the dashboard reads.
    assert not sorted((tmp_path / "data/grades").glob("*.json"))
    written = sorted((tmp_path / "data/grades/_diagnostic").rglob("*.json"))
    assert len(written) == 1
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["run_status"] == "diagnostic"
    assert payload["source_azure_ai_provenance_status"] == GOLD_PROVENANCE_STATUS


def test_a_thirty_task_pin_of_the_full_corpus_is_a_subset():
    """The gold payload carries all 220 rows; the sample pins 30 of them.

    So the scope is `subset` and the output forks into `_diagnostic/` on that
    ground too. Worth stating, because it is why stage 1 needs no special case
    -- and why the rule above is about stage 3, where the pin gets wider.
    """
    inference = {
        "results": [{"task_id": f"task-{index:03d}"} for index in range(220)]
    }
    config = {
        "rerun_identity": {
            "task_ids": [f"task-{index:03d}" for index in range(SAMPLE_SIZE)]
        }
    }

    tasks, scope = s8.filter_tasks_for_config(
        inference, config, tasks_csv=None, limit=0
    )

    assert len(tasks) == SAMPLE_SIZE
    assert scope == "subset"


# --------------------------------------------------------------------------
# The written record has to match what was actually frozen
# --------------------------------------------------------------------------


def _pinned_gold_files() -> list[dict]:
    """Every gold file behind the pinned sample, in task order then file order."""
    module = _manifest_module()
    by_task = {task["task_id"]: task for task in module.load_manifest()["tasks"]}
    pinned = _load_yaml(GOLD_CONFIG_PATH)["rerun_identity"]["task_ids"]
    return [file for task_id in pinned for file in by_task[task_id]["files"]]


def test_spec_records_the_input_fingerprints_that_re_derive():
    """The spec quotes two hashes. They have to be the real ones.

    A fingerprint nobody can recompute is a decoration -- it looks like proof
    and settles nothing. Both of these come from the manifest and the config
    alone, so the 623 MB of gold files are not needed to check the claim, and
    a sample that shifted by one task changes both.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")
    pinned = _load_yaml(GOLD_CONFIG_PATH)["rerun_identity"]["task_ids"]

    ordered_ids = hashlib.sha256("\n".join(pinned).encode("utf-8")).hexdigest()
    file_set = hashlib.sha256(
        "\n".join(
            f"{file['graded_path']}\t{file['sha256']}\t{file['size']}"
            for file in _pinned_gold_files()
        ).encode("utf-8")
    ).hexdigest()

    assert f"`{ordered_ids}`" in spec
    assert f"`{file_set}`" in spec
    # Distinct inputs, so a copy-paste of one into the other is caught.
    assert ordered_ids != file_set


def test_spec_records_the_sample_size_in_bytes_and_files():
    """The corpus is 40 files and 184 MB. Both are stated; both are derived.

    File count and byte total are what a reader uses to sanity-check the run
    time and the bill, so a stale number here is a stale expectation there.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")
    files = _pinned_gold_files()

    assert f"파일 {len(files)}개" in spec
    assert f"{sum(file['size'] for file in files):,} 바이트" in spec


def test_spec_pins_the_same_dataset_commit_as_the_config():
    """One commit, quoted in three places, checked in one.

    The spec's table, the rubric revision and the inference revision all have
    to name the same dataset -- otherwise the answers being graded and the
    rubric grading them come from different releases.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")
    manifest = _manifest_module().load_manifest()

    assert f"`{PINNED_DATASET_SHA}`" in spec
    assert manifest["dataset_revision"] == PINNED_DATASET_SHA
    assert f"`{manifest['dataset_file_sha256']}`" in spec


def test_spec_names_the_container_and_renderer_the_run_will_use():
    """A ceiling rendered by a different LibreOffice is a different ceiling.

    Both are pinned in code; the spec restates them for a reader, so the
    restatement is checked against the pins rather than trusted.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")
    workflow = GRADE_WORKFLOW_PATH.read_text(encoding="utf-8")

    digests = set(re.findall(r"gdpval-grading@sha256:([0-9a-f]{64})", workflow))
    assert len(digests) == 1, "grading jobs must all run the same image"
    assert digests.pop()[:8] in spec

    assert preflight.EXPECTED_LIBREOFFICE_VERSION in spec


def test_spec_discloses_the_unreadable_deliverable_before_the_run():
    """One pinned task's only answer is a zip the read tool cannot open.

    Predicting a weak score is evidence; explaining one afterwards is not. The
    task stays in the sample -- dropping it would flatter the ceiling -- so the
    limitation is written down in advance, and this keeps the disclosure honest
    by checking the tool really does refuse the format.
    """
    from core.tools import read_deliverable

    spec = SPEC_PATH.read_text(encoding="utf-8")
    zipped = [
        file for file in _pinned_gold_files()
        if file["graded_path"].lower().endswith(".zip")
    ]

    assert len(zipped) == 1
    assert "38889c3b-e3d4-49c8-816a-3cc8e5313aba" in spec
    assert ".zip" in spec

    with tempfile.TemporaryDirectory() as workdir:
        name = Path(zipped[0]["graded_path"]).name
        (Path(workdir) / name).write_bytes(b"PK\x03\x04not really a zip")
        envelope = read_deliverable("read_content", name, base_dir=workdir)

    # Not an error -- that is the point. The judge is handed an empty reading
    # with a note, so the shortfall looks like a weak answer rather than a
    # tool that failed, which is exactly why it has to be disclosed up front.
    assert envelope["ok"] is True
    assert envelope["data"]["kind"] == "unknown"
    assert envelope["data"]["text"] == ""
    assert envelope["data"]["note"] == "binary or unsupported for text read"


# --------------------------------------------------------------------------
# Repeating an identical run without erasing the run it repeats
# --------------------------------------------------------------------------


def _output_identity(**overrides) -> dict:
    identity = dict(
        experiment_id="exp_gold_baseline",
        judge_slug="gpt-5_6-sol",
        config_hash="c" * 64,
        rubric_sha=PINNED_DATASET_SHA,
        rubric_short_sha=PINNED_DATASET_SHA[:7],
        prompt_version="v2.2",
        inference_sha=PINNED_DATASET_SHA,
        grader_source_hash="3" * 64,
    )
    identity.update(overrides)
    return identity


_OUTPUT_CONFIG = {
    "config_name": "gold_ceiling_30_v2_sol_max",
    "output": {
        "directory": "data/grades",
        "filename_template": "{exp_id}__{config_name}__{prompt_v}.json",
    },
}


def test_repeats_of_one_run_resolve_to_distinct_paths():
    """Measuring drift needs the same run graded more than once.

    Nothing that identifies the run may change, so every repeat formats the
    same filename -- and step8 refuses to write over an existing grade, while
    `--force` would erase the run being compared against. The ordinal forks the
    directory instead, touching no identity input.
    """
    paths = [
        s8.resolve_grade_output_path(
            _OUTPUT_CONFIG, **_output_identity(), run_ordinal=ordinal
        )
        for ordinal in range(1, 4)
    ]

    assert len(set(paths)) == 3
    # Run 1 keeps the canonical path: the original of a repeat set is an
    # ordinary run and its dispatch needs no flag.
    assert paths[0] == s8.resolve_grade_output_path(
        _OUTPUT_CONFIG, **_output_identity()
    )
    assert paths[1].parent.name == "run-002"
    assert paths[1].parent.parent.name == "_repeats"
    # Same filename throughout: the identity is unchanged, which is the point.
    assert len({path.name for path in paths}) == 1


def test_a_repeat_can_still_be_sharded():
    """Load-bearing. A 30-task grade runs far past the four-hour chunk budget,
    so every stage-1 and stage-2 run has to shard -- which means a repeat has
    to shard too. The ordinal therefore forks the directory ABOVE the shard
    fork, so each repeat gets its own complete set of shards instead of two
    sets landing in one directory with nothing to tell them apart.
    """
    first = [
        s8.resolve_grade_output_path(
            _OUTPUT_CONFIG,
            **_output_identity(),
            shard_index=index,
            shard_count=3,
            run_ordinal=1,
        )
        for index in range(3)
    ]
    second = [
        s8.resolve_grade_output_path(
            _OUTPUT_CONFIG,
            **_output_identity(),
            shard_index=index,
            shard_count=3,
            run_ordinal=2,
        )
        for index in range(3)
    ]

    assert len(set(first) | set(second)) == 6
    assert len({path.parent for path in first}) == 1
    assert len({path.parent for path in second}) == 1
    assert first[0].parent != second[0].parent
    assert [path.name for path in first] == [path.name for path in second]
    # step9 reassembles by stripping `/_shards/*` and re-attaching the stem, so
    # each repeat's shards merge back into that repeat's own final file.
    assert second[0].parent.parent.parent.name == "run-002"


def test_repeat_and_diagnostic_forks_compose():
    """A gold run is always diagnostic, so a gold repeat is always both."""
    path = s8.resolve_grade_output_path(
        _OUTPUT_CONFIG,
        **_output_identity(),
        diagnostic_task_scope_sha="b" * 64,
        shard_index=1,
        shard_count=3,
        run_ordinal=2,
    )

    assert path.parts[:3] == ("data", "grades", "_diagnostic")
    assert path.parts[3] == "b" * 64
    assert path.parts[4:6] == ("_repeats", "run-002")
    assert path.parts[6] == "_shards"
    assert path.name == "shard-001-of-003.json"


def _workflow_merge_final_file(shard_grade_file, cwd):
    """Run the workflow's own final-file derivation on one shard path.

    Lifted out of `.github/workflows/grade-run.yml` rather than restated, so a
    guard that stops accepting a repeat's path fails here instead of after
    every shard has been graded and paid for.
    """
    raw = GRADE_WORKFLOW_PATH.read_text(encoding="utf-8")
    marker = 'SHARD_DIR="$(dirname -- "$SHARD_GRADE_FILE")"'
    start = raw.rindex("\n", 0, raw.index(marker)) + 1
    tail = 'FINAL_FILE="${SHARD_DIR%/_shards/*}/${STEM}.json"'
    end = raw.index(tail, start) + len(tail)
    block = textwrap.dedent(raw[start:end])

    return subprocess.run(
        ["bash", "-c", f'set -euo pipefail\n{block}\nprintf "%s" "$FINAL_FILE"'],
        cwd=cwd,
        env={"SHARD_GRADE_FILE": shard_grade_file, "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_repeats_shards_merge_into_that_repeats_own_final_file():
    """The workflow derives the merged file by stripping `/_shards/*` off the
    shard's own directory and re-attaching the stem, rather than rebuilding the
    path from the config. That is what carries the repeat fork through the
    merge -- and a guard here that refused the deeper path would fail only
    after all three shards had been graded.
    """
    shard = s8.resolve_grade_output_path(
        _OUTPUT_CONFIG,
        **_output_identity(),
        diagnostic_task_scope_sha="b" * 64,
        shard_index=1,
        shard_count=3,
        run_ordinal=2,
    )

    with tempfile.TemporaryDirectory() as workdir:
        (Path(workdir) / shard.parent).mkdir(parents=True)
        result = _workflow_merge_final_file(str(shard), cwd=workdir)

    assert result.returncode == 0, result.stdout + result.stderr
    # Beside the repeat's shards, inside the repeat's own root -- not in run
    # 1's directory, and not in the shared diagnostic root.
    assert Path(result.stdout) == shard.parent.parent.parent / (
        shard.parent.name + ".json"
    )


@pytest.mark.parametrize("ordinal", [0, -1, 11, 100])
def test_impossible_run_ordinals_are_refused(ordinal):
    """Defence in depth: parse_args rejects these too, but the helper is public
    and an out-of-range ordinal would put a paid run somewhere nobody looks."""
    with pytest.raises(ValueError, match="run_ordinal must satisfy"):
        s8.resolve_grade_output_path(
            _OUTPUT_CONFIG, **_output_identity(), run_ordinal=ordinal
        )


def test_run_ordinal_cap_is_the_same_number_in_the_workflow():
    """Two enforcement points, one number. The workflow rejects a bad ordinal
    before the job starts; step8 rejects it after. If they disagreed, the gap
    between them would be a dispatch that validates and then dies mid-run.
    """
    workflow = GRADE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert s8.MAX_RUN_ORDINAL == 10
    assert "^([1-9]|10)$" in workflow
    assert "run_ordinal must be an integer between 1 and 10" in workflow


def test_workflow_carries_the_ordinal_through_to_the_grader():
    """The flag has to survive four hops: input, env, argument, self-retrigger.

    Dropping it at the last hop is the dangerous one -- a repeat that runs out
    of its four hours would resume into run 1's path and overwrite the run it
    exists to be compared against.
    """
    raw = GRADE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert re.search(r"^      run_ordinal:$", raw, re.MULTILINE)
    assert raw.count("GRADE_RUN_ORDINAL: ${{ inputs.run_ordinal }}") == 4
    assert raw.count("ARGS+=(--run-ordinal") == 2
    assert '"run_ordinal": os.environ["GRADE_RUN_ORDINAL"]' in raw


def test_dispatching_a_repeat_needs_no_flag():
    """Run 1 must be the default at every layer.

    An ordinary grade is run 1 and nobody should have to say so; more to the
    point, a default of anything else would silently divert the next real
    campaign into `_repeats/`, where the dashboard never looks.
    """
    raw = GRADE_WORKFLOW_PATH.read_text(encoding="utf-8")
    ordinal_input = raw.split("      run_ordinal:", 1)[1].split("\n\n", 1)[0]

    assert "default: 1" in ordinal_input
    assert "required: false" in ordinal_input

    import inspect

    signature = inspect.signature(s8.resolve_grade_output_path)
    assert signature.parameters["run_ordinal"].default == 1


def test_repeats_are_not_visible_to_the_dashboard_aggregator():
    """`_repeats/` only works because the aggregator does not descend.

    It lists `data/grades/` one level deep and keeps the `.json` entries -- the
    same guarantee `_shards/` already relies on. A subdirectory has no `.json`
    extension, so it drops out. If that listing ever became a recursive walk,
    three repeats of one measurement would appear as three competing results.
    """
    aggregator = (REPO_ROOT / "scripts/aggregate-grades.mjs").read_text(
        encoding="utf-8"
    )

    # The one enumeration of the grades directory, with no options argument:
    # `readdir(dir, {recursive: true})` is what would break the guarantee.
    listings = re.findall(r"readdir\((.*?)\)", aggregator)
    assert listings == ["GRADES_DIR"]
    assert "extname(f) === '.json'" in aggregator
