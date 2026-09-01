"""``--experiment`` says which file to open. The file says which experiment it is.

Those are two facts, and until now they looked like one. Every experiment
config sat directly in ``experiments/`` and was named after the id it
declared, so the path used to open a config and the identity recorded inside
it were the same string, and code could use either one interchangeably without
anyone noticing which it had picked.

Putting a config in a directory separates them for the first time.
``execution_envelope/exp030_envelope_host_python_process`` opens a file whose
declared id is ``exp030_envelope_host_python_process`` — no folder. Step 3
writes that declared id into ``inference_provenance.json`` and uploads it
beside the results, so a downloader comparing the *path* against that sidecar
refuses the experiment its own inference. Dry run 33482175890 stopped there:

    ValueError: inference provenance experiment identity mismatch

The fix is a rule rather than a normalisation, and this file is where the rule
is written down: the path selects the file, the file states the identity, and
every comparison against something a run recorded uses the second.

``exp002_single_baseline.yaml`` is why the obvious shortcut is wrong. It
declares ``exp002``, so "take the last path component" is not a restatement of
the existing convention — it is a change that would misidentify a config that
has been on main since the beginning.

Nothing here calls a model or the network. The end-to-end tests build the
sidecar with the same function step 3 builds it with, so they prove a
round trip rather than a hand-written approximation of one.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from core.inference_manifest import build_inference_provenance

BATCH_RUNNER = Path(__file__).resolve().parents[1]
EXPERIMENTS = BATCH_RUNNER / "experiments"

FULL_SHA = "a" * 40

# The dispatch that hit the wall, and the identity the file it opens declares.
DIRECTORY_CONFIG = "execution_envelope/exp030_envelope_host_python_process"
DECLARED_ID = "exp030_envelope_host_python_process"

# The config that makes "declared id == filename" a coincidence rather than a
# rule, and so decides the shape of the fix.
DIVERGENT_CONFIG = "exp002_single_baseline"
DIVERGENT_ID = "exp002"


def _module():
    path = BATCH_RUNNER / "scripts/download_inference_from_hf.py"
    spec = importlib.util.spec_from_file_location(
        "download_inference_from_hf", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _declared_id(config_path: Path) -> str | None:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    block = (data or {}).get("experiment")
    return block.get("id") if isinstance(block, dict) else None


def _dispatchable_configs() -> list[str]:
    """Every config a grade run can be pointed at, as ``--experiment`` spells it.

    Naming a repository is what makes a file dispatchable; the plan documents
    beside the execution-envelope configs do not, and are not grading inputs.
    """
    found = []
    for path in sorted(EXPERIMENTS.rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        block = data.get("data") if isinstance(data, dict) else None
        source = block.get("source") if isinstance(block, dict) else None
        if isinstance(source, str) and source.strip():
            found.append(
                path.relative_to(EXPERIMENTS).with_suffix("").as_posix()
            )
    return found


# ── the rule, read off the configs that are really on disk ───────────────


def test_a_config_in_a_directory_is_the_experiment_it_declares(monkeypatch):
    """The regression, stated on the real file rather than a fixture."""
    monkeypatch.chdir(BATCH_RUNNER)
    module = _module()
    assert module.resolve_experiment_id(DIRECTORY_CONFIG) == DECLARED_ID
    assert "/" not in module.resolve_experiment_id(DIRECTORY_CONFIG), (
        "the identity uploaded beside the results has no folder in it; a "
        "resolver that returns one can never match the sidecar"
    )


def test_the_identity_is_not_the_last_component_of_the_path(monkeypatch):
    """Why the shortest-looking fix is the wrong one.

    Normalising the dispatched value to its basename would satisfy the five
    execution-envelope configs and quietly misidentify this one, which has been
    on main since long before any of them.
    """
    monkeypatch.chdir(BATCH_RUNNER)
    module = _module()
    assert module.resolve_experiment_id(DIVERGENT_CONFIG) == DIVERGENT_ID
    assert DIVERGENT_ID != DIVERGENT_CONFIG.rsplit("/", 1)[-1]


def test_every_config_that_can_be_dispatched_states_an_identity(monkeypatch):
    """A config the resolver cannot read is a run that fails after downloading.

    The refusal is deliberate rather than a fall back to the path, so a config
    added without an id has to be caught here, at no cost, instead of at the
    grading step of a dispatch someone is waiting on.

    "Dispatchable" means it names a repository to grade. ``experiments/`` also
    holds two plan documents that name neither, and those already stop one line
    earlier on ``data.source is missing`` — this fix did not change what
    happens to them.
    """
    monkeypatch.chdir(BATCH_RUNNER)
    module = _module()

    dispatchable = _dispatchable_configs()
    assert len(dispatchable) > 30, "the survey found almost nothing to check"

    for name in dispatchable:
        assert module.resolve_experiment_id(name) == _declared_id(
            EXPERIMENTS / f"{name}.yaml"
        ), name


def test_a_config_that_states_no_identity_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    module = _module()
    path = Path("experiments/nameless.yaml")
    path.parent.mkdir(parents=True)
    path.write_text('experiment:\n  name: "no id here"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="experiment.id is missing"):
        module.resolve_experiment_id("nameless")


@pytest.mark.parametrize("declared", ['""', "[]", "{}"])
def test_an_empty_or_mistyped_identity_is_refused(
    declared, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    module = _module()
    path = Path("experiments/blank.yaml")
    path.parent.mkdir(parents=True)
    path.write_text(f"experiment:\n  id: {declared}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="experiment.id is missing"):
        module.resolve_experiment_id("blank")


def test_the_declared_identity_is_compared_exactly_as_written(
    tmp_path, monkeypatch
):
    """Trimming here would invent a disagreement instead of preventing one.

    Step 3 records whatever the config declares — ``ExperimentConfig`` reads
    ``experiment.id`` and does not trim it either. Tidying one side of a
    comparison and not the other is how the two sides stop matching.
    """
    monkeypatch.chdir(tmp_path)
    module = _module()
    path = Path("experiments/padded.yaml")
    path.parent.mkdir(parents=True)
    path.write_text('experiment:\n  id: "  spaced  "\n', encoding="utf-8")

    assert module.resolve_experiment_id("padded") == "  spaced  "


# ── the download, end to end, against a sidecar step 3 really wrote ──────


def _payload(experiment_id: str) -> dict:
    """A step 2 result set shaped the way step 3 hands it to the sidecar."""
    return {
        "experiment_id": experiment_id,
        "source_repo_id": "owner/repo",
        "prepared_fingerprint": hashlib.sha256(b"prepared").hexdigest(),
        "execution_mode": "subprocess",
        "azure_ai_routes": [],
        "results": [
            {
                "task_id": "task-1",
                "deliverable_text": "hello",
                "deliverable_files": [],
                "status": "success",
            }
        ],
    }


def _run_main(module, monkeypatch, tmp_path, *, dispatched, sidecar_id):
    """Run ``main()`` against a Hub that answers with one experiment's upload."""
    monkeypatch.chdir(tmp_path)

    config = Path("experiments") / f"{dispatched}.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'experiment:\n  id: "{DECLARED_ID}"\ndata:\n  source: "owner/repo"\n',
        encoding="utf-8",
    )

    results = tmp_path / "step2_inference_results.json"
    results.write_text(
        json.dumps(_payload(DECLARED_ID)), encoding="utf-8"
    )
    # Built by the writer, not by hand: whatever step 3 puts in this file is
    # what the downloader has to accept.
    sidecar = tmp_path / "inference_provenance.json"
    sidecar.write_text(
        json.dumps(build_inference_provenance(_payload(sidecar_id))),
        encoding="utf-8",
    )

    class FakeApi:
        def __init__(self, token=None):
            self.token = token

        def dataset_info(self, repo_id, revision):
            return SimpleNamespace(sha=FULL_SHA)

    def fake_hf_hub_download(**kwargs):
        return str(
            {
                "step2_inference_results.json": results,
                "inference_provenance.json": sidecar,
            }[kwargs["filename"]]
        )

    monkeypatch.setattr(module, "HfApi", FakeApi)
    monkeypatch.setattr(module, "hf_hub_download", fake_hf_hub_download)
    monkeypatch.setattr(
        module,
        "snapshot_download",
        lambda **kwargs: str(kwargs["local_dir"]),
    )
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: SimpleNamespace(
            experiment=dispatched,
            output="workspace/inference.json",
            revision="",
            expected_leading_task_id=[],
            grading_config=None,
            allow_legacy_missing_provenance=False,
        ),
    )
    return module.main()


def test_the_download_accepts_the_sidecar_its_own_inference_uploaded(
    monkeypatch, tmp_path
):
    """The dry run's failure, reproduced and then passing.

    The dispatch carries a folder; the upload carries the declared id. Before
    the fix these were compared against each other and the run stopped here,
    after the download and before any grading.
    """
    module = _module()
    assert (
        _run_main(
            module,
            monkeypatch,
            tmp_path,
            dispatched=DIRECTORY_CONFIG,
            sidecar_id=DECLARED_ID,
        )
        == 0
    )

    written = json.loads(
        Path("workspace/inference.json").read_text(encoding="utf-8")
    )
    assert written["azure_ai_provenance_status"] == "verified-sidecar"
    assert written["results"][0]["task_id"] == "task-1"


def test_a_sidecar_from_another_experiment_is_still_refused(
    monkeypatch, tmp_path
):
    """The check was taught which value to read, not to stop reading.

    Without this the test above would pass just as happily if the comparison
    had been deleted, and would then be measuring nothing.
    """
    module = _module()
    with pytest.raises(
        ValueError, match="inference provenance experiment identity mismatch"
    ):
        _run_main(
            module,
            monkeypatch,
            tmp_path,
            dispatched=DIRECTORY_CONFIG,
            sidecar_id="exp031_envelope_container_code_interpreter",
        )


# ── both halves of one run have to pin the same spelling ────────────────


def _pinned_identity_argument() -> str:
    """What ``step8_grade.py`` hands its own ``rerun_identity`` check."""
    tree = ast.parse(
        (BATCH_RUNNER / "step8_grade.py").read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_validate_pinned_rerun_identity"
        ):
            for keyword in node.keywords:
                if keyword.arg == "experiment_id":
                    return ast.unparse(keyword.value)
    raise AssertionError(
        "step8_grade.py no longer calls _validate_pinned_rerun_identity"
    )


def test_the_two_pinned_identity_checks_read_the_same_field():
    """One value in a grading config, checked twice, in two different steps.

    ``rerun_identity.experiment_id`` is compared by the downloader against what
    the inference run recorded, and again by step 8 before grading starts. If
    one of them read the dispatched path instead, a grading config for a
    directory config would need two different spellings of the same field to
    get through a single run — which it cannot have.
    """
    assert _pinned_identity_argument() == "exp_config.experiment_id"


def test_the_grading_config_side_reads_the_declared_identity_too(monkeypatch):
    """The same fact, reached by step 8's loader instead of the downloader's.

    Checked on the two configs that can disagree with their own path — the one
    in a directory and the one whose id is not its filename — so this fails if
    either side is ever taught to prefer the name it was given.
    """
    monkeypatch.chdir(BATCH_RUNNER)
    module = _module()

    import step8_grade

    for name in (DIRECTORY_CONFIG, DIVERGENT_CONFIG):
        loaded = step8_grade.load_experiment_yaml(name)
        assert loaded.experiment_id == module.resolve_experiment_id(name), name
