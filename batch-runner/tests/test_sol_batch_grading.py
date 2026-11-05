"""Combined solve+grade USD admission for the Sol batch's grade; all model-free.

No socket opens. The published dataset is tmp files handed in through the
fetch seam, the judge is a fake client behind core's real CostRecorder, and
every journal, ledger and grade file is written under tmp_path.
"""

from __future__ import annotations

import ast
import copy
import errno
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import core.cost_metering as cost_metering
import gpt54_v2_grading_input
import gpt56_pilot_usd_budget as usd
import sol_batch_controls as controls
import sol_batch_grading as grading
import step8_grade as step8
from core import runner_environment
from core.cost_metering import CostRecorder
from core.cost_receipts import STAGE_GRADING, CostReceiptLedger
from core.task_checkpoint import checkpoint_path
from . import test_step8_grade as step8_fixture
from .test_step8_grade import _typed_azure_ai_route  # noqa: F401 - autouse route env for step 8

BATCH_RUNNER = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER.parent
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"
EXP036 = "exp036_sol_fixed5"
EXP036_CONFIG = "grading_configs/exp036_v2_sol_max.yaml"
EXP035 = "exp035_codex_foundry_full220"
EXP035_CONFIG = "grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml"
EXP035_REVISION = "dc36d6837a8f0899f8bfa4d32aae9a9f6805f3b0"
INFERENCE_SHA = "b" * 40
PROOF_STEP = "Prove the paid grading runner admission (model-free)"
DRY_CHECK_STEP = "Check combined solve+grade USD admission (model-free)"
PAID_CHECK_STEP = "Resolve combined solve+grade USD admission"
JOURNAL_STEP = "Commit combined solve+grade USD journal"
NEW_INPUT_PATHS = (
    "batch-runner/gpt54_v2_grading_input.py",
    "batch-runner/gpt56_pilot_usd_budget.py",
    "batch-runner/sol_batch_controls.py",
    "batch-runner/sol_batch_grading.py",
)
#: A grading request of the shape core.grader sends: visible text and an
#: output limit, so the reservation is the exact text bound.
KWARGS = {"model": "gpt-5.6-sol", "input": "Grade this rubric item.", "max_output_tokens": 2400}
MILLION = Decimal(1_000_000)
PLACES = Decimal("0.00000001")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network forbidden in combined USD tests")

    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)


@pytest.fixture
def in_batch_runner(monkeypatch):
    # preflight reads experiments/ and grading_configs/ relative to cwd, as
    # step 8 does and as grade-run.yml runs it after `cd batch-runner`.
    monkeypatch.chdir(BATCH_RUNNER)


@pytest.fixture
def restore_step8_binding(monkeypatch):
    # install_admission rebinds this module global; monkeypatch puts the real
    # one back after the test whatever the test did to it.
    monkeypatch.setattr(step8, "open_cost_recorder", step8.open_cost_recorder)


# -- helpers ------------------------------------------------------------------


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps(job: str) -> list[dict]:
    return _workflow()["jobs"][job]["steps"]


def _names(job: str) -> list[str | None]:
    return [step.get("name") for step in _steps(job)]


def _step(job: str, name: str) -> dict:
    return next(step for step in _steps(job) if step.get("name") == name)


def _input_paths(job: str, step_name: str) -> list[str]:
    lines = _step(job, step_name)["run"].splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "GRADING_INPUT_PATHS=(")
    paths: list[str] = []
    for line in lines[start + 1:]:
        if line.strip() == ")":
            return paths
        paths.append(line.strip())
    raise AssertionError("GRADING_INPUT_PATHS is not closed")


def _proof_source() -> str:
    lines = _step("grade-dry-run", PROOF_STEP)["run"].splitlines()
    start = lines.index("python - <<'PY'") + 1
    return "\n".join(lines[start:lines.index("PY", start)]) + "\n"


def _reserve_for(kwargs: dict) -> Decimal:
    """The reservation computed here, independently of the admission."""
    inputs = len(json.dumps(kwargs, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    outputs = kwargs["max_output_tokens"]
    # Sol list meter: (input 10.00 + cache write 12.50) per input, 45.00 per output.
    amount = (Decimal(inputs) * Decimal("22.50") + Decimal(outputs) * Decimal("45.00")) / MILLION
    return amount.quantize(PLACES, rounding=ROUND_CEILING)


def _seed(**overrides) -> grading.Seed:
    values = dict(
        experiment_id=grading.GRADED_EXPERIMENT_ID,
        config_name=grading.GRADING_CONFIG_NAME,
        inference_revision=INFERENCE_SHA,
        solve_usd=Decimal("40"),
        published_ledger_floor_usd=Decimal("0"),
        published_ledger_status="absent",
        narrative_allowance_usd=controls.NARRATIVE_ALLOWANCE_USD,
        prior_grading_usd=Decimal("0"),
        prior_journals=(),
        ceiling_usd=controls.CEILING_USD,
    )
    values.update(overrides)
    return grading.Seed(**values)


def _usage(input_tokens=1000, cached=0, output_tokens=200, reasoning=50):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached),
        output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
    )


class FakeResponses:
    """A Responses client that never leaves the process."""

    def __init__(self, *, usage=True, error: BaseException | None = None, tokens: dict | None = None):
        self.responses = self
        self.calls: list[dict] = []
        self._usage = usage
        self._error = error
        self._tokens = tokens or {}

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(
            model=kwargs.get("model"),
            status="completed",
            output=[],
            output_text="{}",
            usage=_usage(**self._tokens) if self._usage else None,
        )


def _records(journal: Path) -> list[dict]:
    return [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]


def _events(journal: Path) -> list[str]:
    return [record["event"] for record in _records(journal)]


def _write_journal(path: Path, records: list[dict], *, experiment_id: str = grading.GRADED_EXPERIMENT_ID) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"event": "open", "schema": grading.JOURNAL_SCHEMA, "experiment_id": experiment_id}, *records]
    path.write_text(
        "".join(json.dumps({**record, "seq": index}, sort_keys=True) + "\n" for index, record in enumerate(lines)),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def admitted(tmp_path):
    """Build a real admission behind core's CostRecorder; both closed afterwards."""
    opened: list[tuple[grading.CombinedGradingAdmission, CostReceiptLedger]] = []

    def build(seed: grading.Seed, name: str = "run-7-1.combined_usd.jsonl"):
        admission = grading.CombinedGradingAdmission(seed, tmp_path / name)
        ledger = CostReceiptLedger(tmp_path / f"{name}.audit.sqlite3", run_id="g")
        opened.append((admission, ledger))
        return admission, CostRecorder(ledger, usd_admission=admission)

    yield build
    for admission, ledger in opened:
        admission.close(None)
        ledger.close()


# -- (1)-(4) workflow wiring --------------------------------------------------


def test_all_three_grading_containers_hand_the_runners_image_version_through():
    workflow = _workflow()
    containers = {name: workflow["jobs"][name]["container"] for name in ("grade-dry-run", "grade", "pilot-live")}
    for name, container in containers.items():
        assert container["options"] == "--env ImageVersion", name
    # Four existing tests pin pilot-live.container == grade.container.
    assert containers["grade-dry-run"] == containers["grade"] == containers["pilot-live"]
    text = WORKFLOW.read_text(encoding="utf-8")
    assert len(set(re.findall(r"gdpval-grading@sha256:[0-9a-f]{64}", text))) == 1
    # Copied from the runner, never typed: no job or step states a value.
    for job in workflow["jobs"].values():
        assert "ImageVersion" not in (job.get("env") or {})
        for step in job.get("steps", []):
            assert "ImageVersion" not in (step.get("env") or {})


def test_the_free_dry_run_proves_admission_and_the_usd_check_before_its_download():
    names = _names("grade-dry-run")
    install = names.index("Install dependencies")
    assert names[install + 1:install + 3] == [PROOF_STEP, DRY_CHECK_STEP]
    assert names.index(DRY_CHECK_STEP) < names.index("Download inference results anonymously")
    for name in (PROOF_STEP, DRY_CHECK_STEP):
        step = _step("grade-dry-run", name)
        # No if, no timeout-minutes, no shell, no env, so nothing secret.
        assert set(step) == {"name", "run"}, name
        assert "secrets." not in yaml.safe_dump(step)
    check = _step("grade-dry-run", DRY_CHECK_STEP)["run"]
    assert "python sol_batch_grading.py preflight" in check
    assert '--config "grading_configs/$GRADE_CONFIG"' in check
    first = re.search(r"^\s*timeout-minutes:\s*(\S+)", WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE)
    assert first is not None and first.group(1) == "359"


def test_the_admission_proof_prints_the_receipt_step8_would_record(native_hosted_runner, monkeypatch, capsys):
    source = compile(_proof_source(), f"{WORKFLOW.name}:{PROOF_STEP}", "exec")
    exec(source, {"__name__": "__main__"})
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["schema_version"] == "native-runner-evidence-v1"
    assert receipt["stage"] == "grading"
    assert receipt["observation"]["image_version"] == "20261026.354.1"
    assert receipt["observation"]["eligible_for_execution"] is True
    assert receipt == runner_environment.receipt("grading")

    monkeypatch.delenv("ImageVersion")
    with pytest.raises(SystemExit) as refused:
        exec(source, {"__name__": "__main__"})
    message = str(refused.value)
    assert "execution_environment_refused" in message
    assert "image_version" in message.partition("unset: ")[2].split(", ")


def test_the_paid_job_checks_before_oidc_and_records_its_journal_before_the_grade():
    names = _names("grade")
    check = names.index(PAID_CHECK_STEP)
    assert names[check - 1] == "Determine renderer requirement"
    assert names[check + 1] == "Validate Azure OIDC identity before remote access"
    for index, step in enumerate(_steps("grade")):
        if "secrets." in yaml.safe_dump(step):
            assert index > check, step.get("name")
    paid_check = _step("grade", PAID_CHECK_STEP)
    assert paid_check["id"] == "sol_usd"
    assert set(paid_check) == {"name", "id", "run"}
    assert "python sol_batch_grading.py preflight" in paid_check["run"]

    grade = _step("grade", "Run grading")
    assert grade["env"]["SOL_COMBINED_USD"] == "${{ steps.sol_usd.outputs.enabled }}"
    script = grade["run"]
    wrapper = 'python sol_batch_grading.py run --inference-revision "$GRADE_INFERENCE_REVISION" -- "${ARGS[@]}"'
    plain = 'python step8_grade.py "${ARGS[@]}"'
    switch = 'if [[ "$SOL_COMBINED_USD" == "true" ]]; then'
    assert script.count(plain) == 1 and script.count(wrapper) == 1
    # Inside the existing rc capture, which stays as it was.
    assert (script.index("set +e") < script.index(switch) < script.index(wrapper)
            < script.index(plain) < script.index("RC=$?"))
    assert 'if [[ "$RC" != "0" && "$RC" != "7" ]]; then' in script

    journal = _step("grade", JOURNAL_STEP)
    for clause in ("always()", "inputs.dry_run == false", "steps.sol_usd.outputs.enabled == 'true'"):
        assert clause in journal["if"]
    assert names.index(JOURNAL_STEP) == names.index("Run grading") + 1
    assert names.index(JOURNAL_STEP) < names.index("Commit grade result")
    assert journal["env"] == {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "rebase.autoStash",
        "GIT_CONFIG_VALUE_0": "true",
    }
    run = journal["run"]
    path = 'data/grades/_combined_usd/${GRADE_EXPERIMENT_SLUG}/run-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}.combined_usd.jsonl'
    assert f'JOURNAL="{path}"' in run
    assert path.startswith(grading.JOURNAL_DIR.as_posix() + "/")
    assert grading.JOURNAL_NAME.fullmatch("run-123456789-1.combined_usd.jsonl")
    # Only the journal is staged and committed, after it parses.
    assert run.count("git add") == 1 and 'git add -- "$JOURNAL"' in run
    commit = [line.strip() for line in run.splitlines() if "git commit" in line]
    assert len(commit) == 1
    assert commit[0].startswith("git commit --only ") and commit[0].endswith('-- "$JOURNAL"')
    assert run.index("check-journal") < run.index("git add")
    # A journal that does not parse is still committed, so the next preflight
    # refuses rather than never seeing that spend; the step still goes red.
    assert 'if ! python batch-runner/sol_batch_grading.py check-journal --journal "$JOURNAL"; then' in run
    assert run.count("check-journal") == 1
    assert 'git rev-parse HEAD >> "$PUBLISHED_COMMITS_FILE"' in run
    assert run.index('if [[ "$JOURNAL_PUSHED" != "true" ]]') < run.index("git rev-parse HEAD >>")
    assert run.index("git rev-parse HEAD >>") < run.index('if [[ "$JOURNAL_READABLE" != "true" ]]')

    # A journal that cannot be pushed survives in the always() cost-ledger upload.
    upload = _step("grade", "Upload cost ledger")
    assert "always()" in upload["if"] and "steps." not in upload["if"]
    glob = "data/grades/_combined_usd/**/*.combined_usd.jsonl"
    assert glob in upload["with"]["path"].splitlines()
    assert glob.startswith(grading.JOURNAL_DIR.as_posix() + "/**/")


def test_both_grading_input_pins_cover_the_admission_and_what_it_imports():
    dry_run = _input_paths("grade-dry-run", "Verify read-only checkout and input files")
    paid = _input_paths("grade", "Verify checked out main and input files")
    assert dry_run == paid == sorted(paid)
    for path in NEW_INPUT_PATHS:
        assert path in paid
        assert (REPO_ROOT / path).is_file(), path
    for module in (grading, controls, usd, gpt54_v2_grading_input):
        relative = Path(module.__file__).resolve().relative_to(REPO_ROOT).as_posix()
        assert any(relative == entry or relative.startswith(entry + "/") for entry in paid), relative

    # Everything a paid grade imports, not only its first level: a fresh
    # interpreter, so modules other tests loaded cannot hide or add anything.
    probe = (
        "import json, sys\n"
        "for name in ('step8_grade', 'sol_batch_grading', 'sol_batch_controls',\n"
        "             'gpt56_pilot_usd_budget', 'step9_merge_shards'):\n"
        "    __import__(name)\n"
        "print(json.dumps(sorted({getattr(m, '__file__', None) or '' for m in list(sys.modules.values())})))\n"
    )
    loaded = json.loads(subprocess.run(
        [sys.executable, "-c", probe], cwd=BATCH_RUNNER, env=dict(os.environ),
        capture_output=True, text=True, check=True, timeout=300,
    ).stdout)
    imported = set()
    for name in loaded:
        if not name:
            continue
        path = Path(name).resolve()
        if REPO_ROOT not in path.parents or "site-packages" in path.parts:
            continue
        imported.add(path.relative_to(REPO_ROOT).as_posix())
    assert "batch-runner/gpt54_comparison_preflight.py" in imported
    uncovered = sorted(relative for relative in imported
                       if not any(relative == entry or relative.startswith(entry + "/") for entry in paid))
    assert uncovered == []


# -- (5) applicability --------------------------------------------------------


def test_only_the_sol_batch_with_its_own_config_turns_the_admission_on(in_batch_runner):
    assert grading.applies(EXP035, EXP035_CONFIG) is False
    assert grading.applies(EXP036, EXP036_CONFIG) is True
    # Not applicable means no check at all, whatever the other arguments say.
    assert grading.preflight(EXP035, EXP035_CONFIG, "", 4) is None
    for experiment, config in ((EXP036, EXP035_CONFIG), (EXP035, EXP036_CONFIG)):
        with pytest.raises(grading.CombinedUsdRefused) as refused:
            grading.applies(experiment, config)
        assert refused.value.code == grading.UNVERIFIED
        assert "only grade each other" in refused.value.detail


def test_the_preflight_command_is_inert_for_every_other_grade(in_batch_runner, tmp_path, monkeypatch, capsys):
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    argv = ["preflight", "--experiment", EXP035, "--config", EXP035_CONFIG,
            "--inference-revision", EXP035_REVISION, "--shard-count", "1"]
    assert grading.main(argv) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"enabled": False}
    assert captured.err == ""
    assert output.read_text(encoding="utf-8") == "enabled=false\n"

    mismatched = ["preflight", "--experiment", EXP036, "--config", EXP035_CONFIG,
                  "--inference-revision", EXP035_REVISION, "--shard-count", "1"]
    assert grading.main(mismatched) == grading.REFUSED_EXIT
    captured = capsys.readouterr()
    assert captured.out == ""
    refusal = json.loads(captured.err)
    assert refusal["status"] == "refused" and refusal["reason"] == grading.UNVERIFIED
    assert refusal["actual_billing_hard_limit_verified"] is False
    # Nothing appended: a refused check names no output.
    assert output.read_text(encoding="utf-8") == "enabled=false\n"

    with pytest.raises(SystemExit) as usage:
        grading.main(["run", "--inference-revision", INFERENCE_SHA])
    assert usage.value.code == 2


def test_the_inert_answer_imports_nothing_beyond_yaml(tmp_path):
    """Every other paid grade now passes this; it must not depend on step 8 importing."""
    code = (
        "import json, sys\n"
        "import sol_batch_grading as grading\n"
        f"rc = grading.main(['preflight', '--experiment', {EXP035!r}, '--config', {EXP035_CONFIG!r},"
        f" '--inference-revision', {EXP035_REVISION!r}, '--shard-count', '1'])\n"
        "heavy = ('step8_grade', 'sol_batch_controls', 'gpt56_pilot_usd_budget', 'core', 'huggingface_hub')\n"
        "print(json.dumps({'rc': rc, 'loaded': [name for name in heavy if name in sys.modules]}))\n"
    )
    env = {"PATH": os.environ.get("PATH", os.defpath), "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8",
           "HF_HUB_OFFLINE": "1"}
    completed = subprocess.run([sys.executable, "-c", code], cwd=BATCH_RUNNER, env=env,
                               capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.splitlines()[-1]) == {"rc": 0, "loaded": []}


def test_the_module_loads_only_the_standard_library_and_yaml_and_runs_no_process():
    tree = ast.parse(Path(grading.__file__).read_text(encoding="utf-8"))
    top: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            top.add(node.module.split(".")[0])
    assert top - {"__future__", "yaml"} <= set(sys.stdlib_module_names)
    everywhere = {
        alias.name.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    } | {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "subprocess" not in everywhere
    assert "GRADER_" not in Path(grading.__file__).read_text(encoding="utf-8")


# -- (6) the config, the shard count and the revision -------------------------


def _exp036_config() -> dict:
    return yaml.safe_load((BATCH_RUNNER / EXP036_CONFIG).read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, config: dict) -> Path:
    path = tmp_path / "exp036_v2_sol_max.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("block", grading.TEMPLATE_BLOCKS)
def test_a_config_that_drifts_from_the_template_refuses(in_batch_runner, tmp_path, block):
    drifted = _exp036_config()
    if isinstance(drifted[block], dict):
        drifted[block] = {**drifted[block], "drift": 1}
    else:
        drifted[block] = "1.0"
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.preflight(EXP036, _write_config(tmp_path, drifted), INFERENCE_SHA, 1)
    assert refused.value.code == grading.UNVERIFIED
    assert repr(block) in refused.value.detail

    missing = _exp036_config()
    del missing[block]
    with pytest.raises(grading.CombinedUsdRefused, match=re.escape(repr(block))):
        grading.preflight(EXP036, _write_config(tmp_path, missing), INFERENCE_SHA, 1)


def test_a_changed_template_or_a_foreign_rerun_identity_refuses(in_batch_runner, tmp_path, monkeypatch):
    rerun = _exp036_config()
    rerun["rerun_identity"] = {"experiment_id": EXP035, "inference_revision": INFERENCE_SHA}
    with pytest.raises(grading.CombinedUsdRefused, match="rerun_identity"):
        grading.preflight(EXP036, _write_config(tmp_path, rerun), INFERENCE_SHA, 1)
    rerun["rerun_identity"] = {"experiment_id": EXP036, "inference_revision": "c" * 40}
    with pytest.raises(grading.CombinedUsdRefused, match="rerun_identity"):
        grading.preflight(EXP036, _write_config(tmp_path, rerun), INFERENCE_SHA, 1)

    monkeypatch.setattr(grading, "TEMPLATE_SHA256", "0" * 64)
    with pytest.raises(grading.CombinedUsdRefused, match="template config changed"):
        grading.preflight(EXP036, EXP036_CONFIG, INFERENCE_SHA, 1)


@pytest.mark.parametrize("shard_count", [2, 0, True])
def test_more_than_one_process_cannot_share_the_admission(in_batch_runner, shard_count):
    with pytest.raises(grading.CombinedUsdRefused, match="unsharded"):
        grading.preflight(EXP036, EXP036_CONFIG, INFERENCE_SHA, shard_count)


@pytest.mark.parametrize("revision", ["", "main", "B" * 40, "b" * 39, "b" * 41, None])
def test_the_seed_is_bound_to_one_full_inference_commit(in_batch_runner, revision):
    with pytest.raises(grading.CombinedUsdRefused, match="inference revision"):
        grading.preflight(EXP036, EXP036_CONFIG, revision, 1)


# -- (7) the published solve spend --------------------------------------------


def _task_row(task_id: str, booked: object = None, *, reached_runner: bool = True, status: str = "success",
              model_calls: int | None = None) -> dict:
    observability: dict = {}
    if reached_runner:
        observability["runner_evidence"] = {"schema_version": "native-runner-evidence-v1", "stage": "inference"}
    if booked is not None:
        # step2._bounded_budget_metrics publishes the booked USD as a float.
        observability["budget_metrics"] = {"schema_version": "1.0", "conservative_cost_usd": booked,
                                           "usage_complete": True}
    row = {"task_id": task_id, "status": status, "observability": observability}
    if model_calls is None and not reached_runner:
        model_calls = 0
    if model_calls is not None:
        # The problem_solving_cost receipt step 6 copies onto every task row.
        row["problem_solving_cost"] = {"status": "not_run" if model_calls == 0 else "partial",
                                       "model_calls": model_calls}
    return row


def _published(tmp_path: Path, rows: list, ledger_rows: list | None = None, *, experiment_id: str = EXP036,
               ledger_error: BaseException | None = None):
    report = tmp_path / "self_report.json"
    report.write_text(json.dumps({"meta": {"experiment_id": experiment_id}, "task_results": rows}), encoding="utf-8")
    files: dict[str, Path] = {"self_report.json": report}
    if ledger_rows is not None:
        ledger = tmp_path / "cost_ledger.jsonl"
        ledger.write_text("".join(json.dumps(row) + "\n" for row in ledger_rows), encoding="utf-8")
        files["cost_ledger.jsonl"] = ledger
    calls: list[tuple[str, str, str]] = []

    def fetch(repo_id: str, filename: str, revision: str) -> Path | None:
        calls.append((repo_id, filename, revision))
        if filename == "cost_ledger.jsonl" and ledger_error is not None:
            raise ledger_error
        return files.get(filename)

    return fetch, calls


SETTLED_CALL = {"record_type": "call", "state": "settled", "input_tokens": 100_000,
                "cached_input_tokens": 20_000, "output_tokens": 5_000, "reasoning_tokens": 1_000}
# 80,000 uncached x 10.00 + 20,000 cached x 1.00 + 5,000 out x 45.00
# + 80,000 writes x 12.50, per 1M tokens.
SETTLED_CALL_USD = Decimal("2.04500000")


def test_the_seed_is_the_booked_usd_on_the_published_task_rows(tmp_path):
    rows = [
        _task_row(controls.FIXED_TASK_IDS[0], 12.5),
        _task_row(controls.FIXED_TASK_IDS[1], 30.12345678),
        _task_row(controls.FIXED_TASK_IDS[2], status="pending"),
        # Stopped before the runner (e.g. reference_input_integrity_failed).
        _task_row(controls.FIXED_TASK_IDS[3], reached_runner=False),
        _task_row(controls.FIXED_TASK_IDS[4], "0"),
    ]
    ledger = [SETTLED_CALL, {**SETTLED_CALL, "state": "reserved"}, {"record_type": "run", "state": "settled"}]
    fetch, calls = _published(tmp_path, rows, ledger)
    solve, floor, status = grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch)
    assert solve == controls.PRIOR_LINEAGE_SPEND_USD + Decimal("42.62345678")
    assert (floor, status) == (SETTLED_CALL_USD, "present")
    assert calls == [("HyeonSang/exp036_sol_fixed5", "self_report.json", INFERENCE_SHA),
                     ("HyeonSang/exp036_sol_fixed5", "cost_ledger.jsonl", INFERENCE_SHA)]


def test_a_task_that_reached_the_runner_without_a_booking_refuses(tmp_path):
    fetch, _ = _published(tmp_path, [_task_row(controls.FIXED_TASK_IDS[0], 1.0),
                                     _task_row(controls.FIXED_TASK_IDS[1])], [])
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch)
    assert refused.value.code == grading.UNVERIFIED
    assert refused.value.detail == "sol_batch_prior_spend_unaccounted"


def test_a_task_that_reached_codex_and_lost_its_booking_refuses(tmp_path):
    # Step 2 rebuilt the row after the runner returned, so runner_evidence and
    # budget_metrics are gone; the solving receipt still counts the call.
    fetch, _ = _published(tmp_path, [_task_row(controls.FIXED_TASK_IDS[0], 1.0),
                                     _task_row(controls.FIXED_TASK_IDS[1], reached_runner=False, model_calls=1)], [])
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch)
    assert refused.value.detail == "sol_batch_prior_spend_unaccounted"


@pytest.mark.parametrize("prior", [None, Decimal("40"), Decimal("146")])
def test_a_published_ledger_above_the_seed_refuses(tmp_path, monkeypatch, prior):
    # The floor is compared with this lineage's own bookings, so a raised
    # PRIOR_LINEAGE_SPEND_USD cannot hide a booking lost from this result.
    if prior is not None:
        monkeypatch.setattr(controls, "PRIOR_LINEAGE_SPEND_USD", prior)
    fetch, _ = _published(tmp_path, [_task_row(controls.FIXED_TASK_IDS[0], 2.0)], [SETTLED_CALL])
    with pytest.raises(grading.CombinedUsdRefused, match="below the published ledger"):
        grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch)


def test_an_unpublished_ledger_is_a_zero_floor_and_said_so(tmp_path):
    fetch, _ = _published(tmp_path, [_task_row(controls.FIXED_TASK_IDS[0], 3.5)])
    assert grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch) == (
        controls.PRIOR_LINEAGE_SPEND_USD + Decimal("3.5"), Decimal(0), "absent")


def test_a_raised_prior_lineage_spend_adds_to_the_seed_once(tmp_path, monkeypatch):
    monkeypatch.setattr(controls, "PRIOR_LINEAGE_SPEND_USD", Decimal("40"))
    fetch, _ = _published(tmp_path, [_task_row(controls.FIXED_TASK_IDS[0], 2.5)], [SETTLED_CALL])
    assert grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch) == (
        Decimal("42.5"), SETTLED_CALL_USD, "present")


def test_a_lost_booking_recorded_for_this_revision_lets_the_grade_seed(tmp_path, monkeypatch):
    # The recovery PR for test_a_task_that_reached_codex_and_lost_its_booking_refuses:
    # the job log's booking for that task, keyed by the revision being graded.
    lost_task = controls.FIXED_TASK_IDS[1]
    rows = [_task_row(controls.FIXED_TASK_IDS[0], 1.0),
            _task_row(lost_task, reached_runner=False, model_calls=1)]
    monkeypatch.setattr(controls, "LOST_BOOKING_USD", {(INFERENCE_SHA, lost_task): Decimal("38.25")})
    fetch, _ = _published(tmp_path, rows, [SETTLED_CALL])
    assert grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch) == (
        controls.PRIOR_LINEAGE_SPEND_USD + Decimal("39.25"), SETTLED_CALL_USD, "present")
    # Raising PRIOR_LINEAGE_SPEND_USD instead never clears the refusal.
    monkeypatch.setattr(controls, "LOST_BOOKING_USD", {})
    monkeypatch.setattr(controls, "PRIOR_LINEAGE_SPEND_USD", Decimal("146"))
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch)
    assert refused.value.detail == "sol_batch_prior_spend_unaccounted"
    # An entry for another published revision does not apply to this one.
    monkeypatch.setattr(controls, "LOST_BOOKING_USD", {("c" * 40, lost_task): Decimal("38.25")})
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch)
    assert refused.value.detail == "sol_batch_prior_spend_unaccounted"


def test_a_lost_booking_entry_below_the_ledger_floor_refuses(tmp_path, monkeypatch):
    lost_task = controls.FIXED_TASK_IDS[0]
    monkeypatch.setattr(controls, "LOST_BOOKING_USD", {(INFERENCE_SHA, lost_task): Decimal("1")})
    fetch, _ = _published(tmp_path, [_task_row(lost_task, reached_runner=False, model_calls=1)],
                          [SETTLED_CALL])
    with pytest.raises(grading.CombinedUsdRefused, match="below the published ledger"):
        grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, fetch=fetch)


@pytest.mark.parametrize("case", ["ledger_fetch_error", "no_report", "foreign_report", "bad_repo", "bad_ledger_line"])
def test_anything_unreadable_about_the_published_run_refuses(tmp_path, case):
    rows = [_task_row(controls.FIXED_TASK_IDS[0], 1.0)]
    repo_id = "HyeonSang/exp036_sol_fixed5"
    if case == "ledger_fetch_error":
        fetch, _ = _published(tmp_path, rows, ledger_error=RuntimeError("hub unavailable"))
    elif case == "no_report":
        def fetch(repo_id, filename, revision):
            return None
    elif case == "foreign_report":
        fetch, _ = _published(tmp_path, rows, experiment_id=EXP035)
    elif case == "bad_repo":
        fetch, _ = _published(tmp_path, rows)
        repo_id = "not a dataset id"
    else:
        fetch, _ = _published(tmp_path, rows, [])
        (tmp_path / "cost_ledger.jsonl").write_text("{not json\n", encoding="utf-8")
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.published_solve(repo_id, INFERENCE_SHA, fetch=fetch)
    assert refused.value.code == grading.UNVERIFIED


def test_the_hub_read_is_anonymous_and_tells_absence_from_an_outage(tmp_path, monkeypatch):
    import httpx
    import huggingface_hub
    from huggingface_hub.errors import EntryNotFoundError, LocalEntryNotFoundError, RemoteEntryNotFoundError

    monkeypatch.setattr(grading.time, "sleep", lambda seconds: None)
    seen: list[dict] = []

    def download(**kwargs):
        seen.append(kwargs)
        return str(tmp_path / "self_report.json")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    assert grading._fetch("HyeonSang/exp036_sol_fixed5", "self_report.json", INFERENCE_SHA) == tmp_path / "self_report.json"
    assert seen == [{"repo_id": "HyeonSang/exp036_sol_fixed5", "repo_type": "dataset",
                     "filename": "self_report.json", "revision": INFERENCE_SHA, "token": False}]

    def raising(error: BaseException, attempts: list[int]):
        def download(**kwargs):
            attempts.append(1)
            raise error
        return download

    missing = httpx.Response(404, request=httpx.Request("GET", "https://huggingface.co/datasets/x"))
    for absent in (EntryNotFoundError("absent"), RemoteEntryNotFoundError("absent", response=missing)):
        attempts: list[int] = []
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", raising(absent, attempts))
        assert grading._fetch("o/r", "cost_ledger.jsonl", INFERENCE_SHA) is None
        assert len(attempts) == 1

    # LocalEntryNotFoundError subclasses EntryNotFoundError but means the Hub
    # was not reached; it is retried and refused, never read as "absent".
    for outage in (LocalEntryNotFoundError("offline"), RuntimeError("reset")):
        attempts = []
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", raising(outage, attempts))
        with pytest.raises(grading.CombinedUsdRefused) as refused:
            grading._fetch("o/r", "cost_ledger.jsonl", INFERENCE_SHA)
        assert refused.value.code == grading.UNVERIFIED
        assert len(attempts) == 3


# -- (8) journals and the committed floor -------------------------------------


def test_every_committed_journal_counts_once_with_what_it_could_not_conclude(tmp_path, admitted):
    reserve = _reserve_for(KWARGS)
    first, recorder = admitted(_seed(), "run-1-1.combined_usd.jsonl")
    with recorder.attributed(task_id="t1", stage=STAGE_GRADING):
        recorder.meter(FakeResponses(), provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
        with pytest.raises(RuntimeError):
            recorder.meter(FakeResponses(error=RuntimeError("provider down")), provider="azure",
                           model="gpt-5.6-sol").responses.create(**KWARGS)
    first.close(0)
    # 1,000 in x 22.50 + 200 out x 45.00 per 1M; the failed request keeps its reservation.
    assert grading.journal_spend(first.journal_path) == Decimal("0.0315") + reserve

    second, recorder = admitted(_seed(), "run-2-1.combined_usd.jsonl")
    second.reserve(task_id="t2", provider="azure", kwargs=KWARGS)
    second.close(None)
    assert grading.journal_spend(second.journal_path) == reserve

    # A process killed mid-request leaves a reservation and no close line.
    crashed = _write_journal(tmp_path / "run-3-2.combined_usd.jsonl", [
        {"event": "reserve", "ticket": "g1", "reserve_usd": "1.25000000"},
        {"event": "settle", "ticket": "g1", "spent_usd": "0.50000000"},
        {"event": "reserve", "ticket": "g2", "reserve_usd": "2.00000000"},
    ])
    assert grading.journal_spend(crashed) == Decimal("2.5")

    root = tmp_path / "repo"
    directory = root / grading.JOURNAL_DIR / EXP036
    directory.mkdir(parents=True)
    for journal in (first.journal_path, second.journal_path, crashed):
        (directory / journal.name).write_bytes(journal.read_bytes())
    total, journals = grading.prior_grading(root, EXP036)
    assert total == Decimal("0.0315") + reserve + reserve + Decimal("2.5")
    assert [entry["path"] for entry in journals] == [
        f"data/grades/_combined_usd/{EXP036}/run-1-1.combined_usd.jsonl",
        f"data/grades/_combined_usd/{EXP036}/run-2-1.combined_usd.jsonl",
        f"data/grades/_combined_usd/{EXP036}/run-3-2.combined_usd.jsonl",
    ]
    for entry in journals:
        assert entry["sha256"] == hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest()
    assert grading.prior_grading(root, "another_experiment") == (Decimal(0), [])


def _good_lines() -> list[dict]:
    return [{"event": "reserve", "ticket": "g1", "reserve_usd": "1.00000000"},
            {"event": "settle", "ticket": "g1", "spent_usd": "0.50000000"}]


@pytest.mark.parametrize("damage", [
    "not_json", "out_of_sequence", "foreign_experiment", "torn_last_line", "unknown_ticket",
    "reused_ticket", "after_close", "duplicate_key", "not_an_amount", "unknown_event", "second_open",
])
def test_a_malformed_journal_refuses(tmp_path, damage):
    path = tmp_path / "run-4-1.combined_usd.jsonl"
    if damage == "foreign_experiment":
        _write_journal(path, _good_lines(), experiment_id=EXP035)
    elif damage == "unknown_ticket":
        _write_journal(path, [{"event": "settle", "ticket": "g9", "spent_usd": "0.10000000"}])
    elif damage == "reused_ticket":
        _write_journal(path, [*_good_lines(), {"event": "reserve", "ticket": "g1", "reserve_usd": "1.00000000"}])
    elif damage == "after_close":
        _write_journal(path, [{"event": "close", "spent_usd": "0.00000000"}, *_good_lines()])
    elif damage == "not_an_amount":
        _write_journal(path, [{"event": "reserve", "ticket": "g1", "reserve_usd": 1.0}])
    elif damage == "unknown_event":
        _write_journal(path, [{"event": "refund", "ticket": "g1"}])
    elif damage == "second_open":
        _write_journal(path, [{"event": "open", "schema": grading.JOURNAL_SCHEMA, "experiment_id": EXP036}])
    else:
        _write_journal(path, _good_lines())
        text = path.read_text(encoding="utf-8")
        if damage == "not_json":
            text += "{\n"
        elif damage == "out_of_sequence":
            text = text.replace('"seq": 2', '"seq": 7')
        elif damage == "torn_last_line":
            text = text[:-5]
        elif damage == "duplicate_key":
            text = text.replace('"event": "settle",', '"event": "settle", "event": "settle",')
        path.write_text(text, encoding="utf-8")
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.journal_spend(path)
    assert refused.value.code == grading.UNVERIFIED

    # One bad journal in the directory refuses the whole committed floor.
    root = tmp_path / "repo"
    directory = root / grading.JOURNAL_DIR / EXP036
    directory.mkdir(parents=True)
    (directory / path.name).write_bytes(path.read_bytes())
    with pytest.raises(grading.CombinedUsdRefused):
        grading.prior_grading(root, EXP036)


@pytest.mark.parametrize("name", [
    "run-0-1.combined_usd.jsonl", "run-1-0.combined_usd.jsonl", "run-1-1.combined_usd.json",
    "run-1-1.combined_usd.jsonl.tmp", "run-x-1.combined_usd.jsonl",
])
def test_a_misnamed_journal_refuses(tmp_path, name):
    path = _write_journal(tmp_path / name, _good_lines())
    with pytest.raises(grading.CombinedUsdRefused, match="journal name"):
        grading.journal_spend(path)
    with pytest.raises(grading.CombinedUsdRefused, match="journal name"):
        grading.CombinedGradingAdmission(_seed(), tmp_path / "fresh" / name)


def test_a_symlinked_journal_or_journal_directory_refuses(tmp_path):
    real = _write_journal(tmp_path / "elsewhere" / "run-5-1.combined_usd.jsonl", _good_lines())
    root = tmp_path / "repo"
    directory = root / grading.JOURNAL_DIR / EXP036
    directory.mkdir(parents=True)
    (directory / real.name).symlink_to(real)
    with pytest.raises(grading.CombinedUsdRefused, match="regular file"):
        grading.journal_spend(directory / real.name)
    with pytest.raises(grading.CombinedUsdRefused):
        grading.prior_grading(root, EXP036)

    linked_root = tmp_path / "linked"
    (linked_root / grading.JOURNAL_DIR).mkdir(parents=True)
    (linked_root / grading.JOURNAL_DIR / EXP036).symlink_to(real.parent, target_is_directory=True)
    with pytest.raises(grading.CombinedUsdRefused, match="plain directory"):
        grading.prior_grading(linked_root, EXP036)


def _preflight_with(monkeypatch, tmp_path, solve: Decimal, journals: dict[str, str] | None = None):
    monkeypatch.setattr(grading, "published_solve",
                        lambda repo_id, revision: (solve, Decimal(0), "absent"))
    monkeypatch.setattr(step8, "_repo_root", lambda: tmp_path)
    for name, spent in (journals or {}).items():
        _write_journal(tmp_path / grading.JOURNAL_DIR / EXP036 / name, [
            {"event": "reserve", "ticket": "g1", "reserve_usd": spent},
            {"event": "settle", "ticket": "g1", "spent_usd": spent},
        ])
    return grading.preflight(EXP036, EXP036_CONFIG, INFERENCE_SHA, 1)


def test_the_committed_floor_is_solve_plus_narrative_plus_earlier_grading(in_batch_runner, tmp_path, monkeypatch):
    seed = _preflight_with(monkeypatch, tmp_path, Decimal("150"), {"run-11-1.combined_usd.jsonl": "10.00000000"})
    assert seed.committed_floor() == Decimal("150") + controls.NARRATIVE_ALLOWANCE_USD + Decimal("10")
    record = seed.as_record()
    assert record["solve_usd"] == "150.00000000"
    assert record["narrative_allowance_usd"] == "2.00000000"
    assert record["prior_grading_usd"] == "10.00000000"
    assert record["committed_floor_usd"] == "162.00000000"
    assert record["ceiling_usd"] == "200.00000000"
    assert record["inference_revision"] == INFERENCE_SHA
    assert [journal["path"] for journal in record["prior_journals"]] == [
        f"data/grades/_combined_usd/{EXP036}/run-11-1.combined_usd.jsonl"]


@pytest.mark.parametrize("solve,journals", [
    (Decimal("198"), None),
    (Decimal("150"), {"run-12-1.combined_usd.jsonl": "30.00000000", "run-13-1.combined_usd.jsonl": "18.00000000"}),
    (Decimal("199.5"), None),
])
def test_a_committed_floor_at_the_ceiling_refuses_before_any_login(in_batch_runner, tmp_path, monkeypatch, solve, journals):
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        _preflight_with(monkeypatch, tmp_path, solve, journals)
    assert refused.value.code == grading.CEILING == usd.CEILING


# -- (9) the file-name budget -------------------------------------------------


def test_the_sol_pair_leaves_room_for_every_file_step8_creates(in_batch_runner, tmp_path):
    out = grading.check_name_budget(step8, _exp036_config(), EXP036_CONFIG, EXP036, INFERENCE_SHA)
    stem = len(out.stem.encode("utf-8"))
    assert stem == 206
    assert stem + grading.CHECKPOINT_TMP_EXTRA == 253 <= grading.NAME_MAX
    # The names themselves, created: the ledger (with SQLite's -journal) and
    # the longest one, a task's progress file while it is written.
    recorder, note = cost_metering.open_cost_recorder(
        tmp_path / (out.stem + ".cost_ledger.sqlite3"), run_id="name-budget")
    assert recorder is not None, note
    recorder.ledger.close()
    progress = checkpoint_path(tmp_path / out.name, controls.FIXED_TASK_IDS[0]).with_suffix(".json.tmp")
    assert len(progress.name.encode("utf-8")) == 253
    progress.parent.mkdir()
    progress.write_text("{}", encoding="utf-8")


def test_an_exp035_length_pair_is_refused_before_approval(in_batch_runner):
    config = yaml.safe_load((BATCH_RUNNER / EXP035_CONFIG).read_text(encoding="utf-8"))
    with pytest.raises(grading.CombinedUsdRefused, match="file name limit") as refused:
        grading.check_name_budget(step8, config, EXP035_CONFIG, EXP035, INFERENCE_SHA)
    assert refused.value.code == grading.UNVERIFIED


# -- (10) per-request admission through core's CostRecorder -------------------


def test_a_request_under_the_ceiling_is_sent_and_settled(admitted):
    admission, recorder = admitted(_seed())
    client = FakeResponses()
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(client, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
    assert len(client.calls) == 1
    records = _records(admission.journal_path)
    assert [record["event"] for record in records] == ["open", "reserve", "settle"]
    assert [record["seq"] for record in records] == [0, 1, 2]
    assert records[1]["reserve_usd"] == format(_reserve_for(KWARGS), "f")
    assert records[2]["spent_usd"] == "0.03150000"
    assert (records[2]["input_tokens"], records[2]["output_tokens"], records[2]["reasoning_tokens"]) == (1000, 200, 50)
    assert admission.pending == {} and admission.spent == Decimal("0.0315")
    assert records[0]["schema"] == grading.JOURNAL_SCHEMA
    assert records[0]["experiment_id"] == grading.GRADED_EXPERIMENT_ID


def test_a_request_that_would_pass_the_ceiling_is_never_sent(admitted):
    floor = controls.CEILING_USD - Decimal("0.01")
    admission, recorder = admitted(_seed(solve_usd=floor - controls.NARRATIVE_ALLOWANCE_USD))
    client = FakeResponses()
    metered = recorder.meter(client, provider="azure", model="gpt-5.6-sol")
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        with pytest.raises(usd.GradingUsdStopped) as stopped:
            metered.responses.create(**KWARGS)
        # Sticky: the next request stops too, without another reservation.
        with pytest.raises(usd.GradingUsdStopped):
            metered.responses.create(**KWARGS)
    assert stopped.value.code == grading.CEILING
    assert not isinstance(stopped.value, Exception)
    assert client.calls == []
    stop = _records(admission.journal_path)[-1]
    assert stop["event"] == "stop" and stop["reason"] == grading.CEILING
    assert stop["requested_reserve_usd"] == format(_reserve_for(KWARGS), "f")
    assert stop["committed_usd"] == "199.99000000"
    assert _events(admission.journal_path).count("reserve") == 0


def test_a_settlement_above_its_reservation_is_booked_as_observed(admitted):
    admission, recorder = admitted(_seed(solve_usd=Decimal("193")))
    heavy = FakeResponses(tokens={"input_tokens": 100_000, "cached": 0, "output_tokens": 50_000, "reasoning": 0})
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(heavy, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
        # 100,000 x 22.50 + 50,000 x 45.00 per 1M = 4.50, far above the reservation.
        assert admission.spent == Decimal("4.5")
        light = FakeResponses()
        with pytest.raises(usd.GradingUsdStopped):
            recorder.meter(light, provider="azure", model="gpt-5.6-sol").responses.create(
                **{**KWARGS, "max_output_tokens": 32_000})
    assert light.calls == []
    assert _events(admission.journal_path) == ["open", "reserve", "settle", "stop"]


def test_unknown_usage_and_a_failed_request_keep_their_whole_reservation(admitted):
    admission, recorder = admitted(_seed())
    reserve = _reserve_for(KWARGS)
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(FakeResponses(usage=False), provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
        with pytest.raises(RuntimeError, match="provider down"):
            recorder.meter(FakeResponses(error=RuntimeError("provider down")), provider="azure",
                           model="gpt-5.6-sol").responses.create(**KWARGS)
    records = _records(admission.journal_path)
    assert [(r["event"], r.get("reason")) for r in records[1:]] == [
        ("reserve", None), ("abandon", "usage_unreported"), ("reserve", None), ("abandon", "request_failed")]
    assert records[2]["spent_usd"] == records[4]["spent_usd"] == format(reserve, "f")
    assert admission.spent == reserve * 2 and admission.pending == {}
    assert grading.journal_spend(admission.journal_path) == reserve * 2


def test_a_failed_fsync_spends_its_seq_and_the_journal_still_reads(admitted, monkeypatch):
    admission, recorder = admitted(_seed())
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(FakeResponses(), provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
    real_fsync = os.fsync
    failed: list[int] = []

    def fsync_fails_once(descriptor):
        if not failed:
            failed.append(descriptor)
            raise OSError(errno.EIO, "fsync failed")
        return real_fsync(descriptor)

    monkeypatch.setattr(grading.os, "fsync", fsync_fails_once)
    client = FakeResponses()
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        with pytest.raises(usd.GradingUsdStopped) as stopped:
            recorder.meter(client, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
    admission.close(grading.REFUSED_EXIT)

    assert stopped.value.code == grading.UNVERIFIED and client.calls == [] and failed
    records = _records(admission.journal_path)
    assert [record["event"] for record in records] == ["open", "reserve", "settle", "reserve", "stop", "close"]
    assert [record["seq"] for record in records] == list(range(6))
    # The line whose fsync failed is on disk without a conclusion, so the next
    # preflight counts its reservation as spent.
    assert grading.journal_spend(admission.journal_path) == Decimal("0.0315") + _reserve_for(KWARGS)
    assert grading.main(["check-journal", "--journal", str(admission.journal_path)]) == 0


def test_a_request_outside_any_task_stops(admitted):
    admission, recorder = admitted(_seed())
    client = FakeResponses()
    with pytest.raises(usd.GradingUsdStopped) as stopped:
        recorder.meter(client, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
    assert stopped.value.code == grading.UNKNOWN == usd.UNKNOWN
    assert client.calls == []
    stop = _records(admission.journal_path)[-1]
    assert (stop["event"], stop["reason"]) == ("stop", grading.UNKNOWN)


def test_the_audio_perception_model_is_reserved_and_settled_at_its_stand_in_rate(admitted):
    admission, recorder = admitted(_seed())
    kwargs = {"model": "gpt-audio-1.5", "input": "Listen to this clip.", "max_output_tokens": 100}
    inputs = len(json.dumps(kwargs, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(FakeResponses(tokens={"input_tokens": 10, "output_tokens": 5, "cached": 0, "reasoning": 0}),
                       provider="azure", model="gpt-audio-1.5").responses.create(**kwargs)
    records = _records(admission.journal_path)
    # 40 per input and 80 per output token, per 1M (gpt56_pilot_usd_budget's stand-in).
    expected = ((Decimal(inputs) * 40 + Decimal(100) * 80) / MILLION).quantize(PLACES, rounding=ROUND_CEILING)
    assert records[1]["reserve_usd"] == format(expected, "f")
    assert records[2]["spent_usd"] == "0.00080000"


# -- (11) the one rebinding ----------------------------------------------------


def test_the_rebinding_hands_core_this_admission(tmp_path, restore_step8_binding):
    admission = grading.CombinedGradingAdmission(_seed(), tmp_path / "run-8-1.combined_usd.jsonl")
    original = grading.install_admission(step8, admission)
    assert original is cost_metering.open_cost_recorder
    assert step8.open_cost_recorder is not original
    recorder, _note = step8.open_cost_recorder(tmp_path / "grade.cost_ledger.sqlite3", run_id="r",
                                               continue_rounds=True)
    try:
        assert isinstance(recorder, CostRecorder)
        assert recorder.usd_admission is admission
    finally:
        recorder.ledger.close()
        admission.close(0)


def test_a_ledger_that_will_not_open_stops_step8_before_any_judge(tmp_path, capsys, restore_step8_binding):
    admission = grading.CombinedGradingAdmission(_seed(), tmp_path / "run-9-1.combined_usd.jsonl")
    grading.install_admission(step8, admission)
    blocker = tmp_path / "a-file-not-a-directory"
    blocker.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit) as exited:
        step8.open_cost_recorder(blocker / "grade.cost_ledger.sqlite3", run_id="r", continue_rounds=True)
    assert exited.value.code == grading.REFUSED_EXIT
    refusal = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert refusal["reason"] == grading.UNVERIFIED
    assert refusal["detail"].startswith("cost ledger could not be opened")
    assert refusal["actual_billing_hard_limit_verified"] is False
    assert refusal["runner_evidence"] == runner_environment.receipt("grading")
    admission.close(4)
    assert _events(admission.journal_path) == ["open", "stop", "close"]


def test_a_pilot_admission_already_chosen_is_refused(tmp_path, capsys, restore_step8_binding):
    admission = grading.CombinedGradingAdmission(_seed(), tmp_path / "run-10-1.combined_usd.jsonl")
    grading.install_admission(step8, admission)
    ledger_path = tmp_path / "pilot.cost_ledger.sqlite3"
    with pytest.raises(SystemExit) as exited:
        step8.open_cost_recorder(ledger_path, run_id="r", usd_admission=object())
    assert exited.value.code == grading.REFUSED_EXIT
    assert not ledger_path.exists()
    assert json.loads(capsys.readouterr().err.splitlines()[-1])["detail"] == "a pilot admission was already chosen"
    admission.close(4)


def test_a_moved_binding_is_refused_rather_than_patched(tmp_path, monkeypatch):
    admission = grading.CombinedGradingAdmission(_seed(), tmp_path / "run-11-1.combined_usd.jsonl")
    try:
        monkeypatch.setattr(step8, "open_cost_recorder", lambda *args, **kwargs: (None, None))
        with pytest.raises(grading.CombinedUsdRefused, match="binding drifted") as refused:
            grading.install_admission(step8, admission)
        assert refused.value.code == grading.UNVERIFIED
    finally:
        admission.close(None)


# -- (12) end to end through step 8 -------------------------------------------


STEP8_ARGV = ["exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--source", "local", "--force"]


def _step8_workspace(tmp_path: Path, monkeypatch) -> list[FakeResponses]:
    step8_fixture._setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(step8, "RubricLoader", step8_fixture._FakeLoader)
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    clients: list[FakeResponses] = []

    class MeteredGrader(step8_fixture._FakeGrader):
        """One metered judge call per task, through the recorder step 8 opened."""

        def grade_task(self, task, deliverable_dir, *, resume_from=None):
            client = FakeResponses()
            clients.append(client)
            with self.cost_recorder.attributed(task_id=task.task_id, stage=STAGE_GRADING):
                self.cost_recorder.meter(client, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
            return super().grade_task(task, deliverable_dir, resume_from=resume_from)

    monkeypatch.setattr(step8, "Grader", MeteredGrader)
    return clients


def test_step8_stops_at_the_combined_ceiling_and_keeps_what_it_finished(
        native_hosted_runner, tmp_path, monkeypatch, capsys, restore_step8_binding):
    clients = _step8_workspace(tmp_path, monkeypatch)
    # Room for exactly one reservation: the second request would pass 200.
    seed = _seed(solve_usd=controls.CEILING_USD - controls.NARRATIVE_ALLOWANCE_USD - _reserve_for(KWARGS))
    asked: list[tuple] = []
    monkeypatch.setattr(grading, "preflight", lambda *args: asked.append(args) or seed)

    assert grading.run(STEP8_ARGV, step8_fixture.INFERENCE_SHA) == grading.REFUSED_EXIT

    assert asked == [("exp998_smoke_baseline_sample", "grading_configs/default.yaml", step8_fixture.INFERENCE_SHA, 1)]
    captured = capsys.readouterr()
    report = [json.loads(line) for line in captured.err.splitlines()
              if line.startswith('{"actual_billing_hard_limit_verified"')][-1]
    assert report == {"status": "refused", "source": "grading", "reason": grading.CEILING,
                      "actual_billing_hard_limit_verified": False,
                      "runner_evidence": runner_environment.receipt("grading")}
    assert "::error::combined solve+grade USD ceiling reached" in captured.out
    grades = list((tmp_path / "data/grades").glob("*.json"))
    assert len(grades) == 1
    payload = json.loads(grades[0].read_text(encoding="utf-8"))
    assert payload["run_status"] == "partial"
    assert [row["task_id"] for row in payload["tasks"]] == ["task-001"]
    assert [len(client.calls) for client in clients] == [1, 0]

    journal = (tmp_path / grading.JOURNAL_DIR / "exp998_smoke_baseline_sample"
               / "run-123456789-1.combined_usd.jsonl")
    records = _records(journal)
    assert [record["event"] for record in records] == ["open", "reserve", "settle", "stop", "close"]
    assert records[0]["github_run_id"] == "123456789" and records[0]["github_run_attempt"] == "1"
    assert records[3]["reason"] == grading.CEILING
    assert records[4]["step8_exit"] == grading.REFUSED_EXIT
    assert grading.journal_spend(journal) == Decimal("0.0315")
    # run() puts step 8's binding back once step 8 has returned.
    assert step8.open_cost_recorder is cost_metering.open_cost_recorder


@pytest.mark.parametrize("extra,detail", [
    (["--dry-run"], "dry run"),
    (["--shard-count", "2", "--shard-index", "1"], "unsharded"),
    (["--pilot-usd-workspace", "somewhere"], "pilot"),
])
def test_run_refuses_what_one_admission_cannot_hold(native_hosted_runner, tmp_path, monkeypatch, capsys, extra, detail):
    _step8_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(grading, "preflight", lambda *args: _seed())
    assert grading.run([*STEP8_ARGV, *extra], step8_fixture.INFERENCE_SHA) == grading.REFUSED_EXIT
    refusal = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert refusal["reason"] == grading.UNVERIFIED and detail in refusal["detail"]
    assert not (tmp_path / grading.JOURNAL_DIR).exists()


@pytest.mark.parametrize("case", ["other_revision", "no_run_id", "not_the_sol_batch", "rerun"])
def test_run_refuses_before_step8_when_the_run_cannot_be_bound(native_hosted_runner, tmp_path, monkeypatch, capsys, case):
    _step8_workspace(tmp_path, monkeypatch)
    revision = step8_fixture.INFERENCE_SHA
    monkeypatch.setattr(grading, "preflight", lambda *args: None if case == "not_the_sol_batch" else _seed())
    if case == "other_revision":
        revision = "c" * 40
    elif case == "no_run_id":
        monkeypatch.delenv("GITHUB_RUN_ID")
    elif case == "rerun":
        # "Re-run failed jobs" after an attempt whose journal never reached main.
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    entered: list[bool] = []
    monkeypatch.setattr(step8, "main", lambda: entered.append(True) or 0)
    assert grading.run(STEP8_ARGV, revision) == grading.REFUSED_EXIT
    assert entered == []
    refusal = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert refusal["status"] == "refused"
    if case == "rerun":
        assert "re-run" in refusal["detail"]
    assert not (tmp_path / grading.JOURNAL_DIR).exists()


def test_check_journal_prints_what_a_journal_spent(tmp_path, capsys):
    journal = _write_journal(tmp_path / "run-14-1.combined_usd.jsonl", _good_lines())
    assert grading.main(["check-journal", "--journal", str(journal)]) == 0
    assert json.loads(capsys.readouterr().out) == {"spent_usd": "0.50000000"}
    journal.write_text(journal.read_text(encoding="utf-8")[:-3], encoding="utf-8")
    assert grading.main(["check-journal", "--journal", str(journal)]) == grading.REFUSED_EXIT
    assert json.loads(capsys.readouterr().err)["reason"] == grading.UNVERIFIED


# -- (13) one experiment, one ceiling, on both sides --------------------------


def test_the_grade_side_and_the_solve_side_name_one_experiment_and_one_ceiling():
    assert grading.GRADED_EXPERIMENT_ID == controls.EXPERIMENT_ID
    assert (grading.CEILING, grading.UNVERIFIED, grading.UNKNOWN) == (usd.CEILING, usd.UNVERIFIED, usd.UNKNOWN)
    experiment = yaml.safe_load((BATCH_RUNNER / "experiments" / f"{EXP036}.yaml").read_text(encoding="utf-8"))
    assert experiment["experiment"]["id"] == grading.GRADED_EXPERIMENT_ID
    assert _exp036_config()["config_name"] == grading.GRADING_CONFIG_NAME
    template = (BATCH_RUNNER / grading.TEMPLATE).read_bytes()
    assert hashlib.sha256(template).hexdigest() == grading.TEMPLATE_SHA256
    # Two dashes, a 36-character task id and ".json.tmp" (core/task_checkpoint.py).
    assert grading.CHECKPOINT_TMP_EXTRA == 47
    assert all(len(task_id) == 36 for task_id in controls.FIXED_TASK_IDS)
