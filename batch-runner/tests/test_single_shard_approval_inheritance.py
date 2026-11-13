"""Offline committed evidence and the actual workflow body, with a fake gh."""

import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest
import yaml

from core.runner_environment import receipt
import grade_single_shard_inheritance as inherit


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/grade-run.yml"
HELPER = ROOT / "batch-runner/grade_single_shard_inheritance.py"
BOT = "41898282+github-actions[bot]@users.noreply.github.com"
CONFIG = b"config_name: exp037_v2_sol_max\n"


def encoded(value):
    return json.dumps(value).encode()


class Evidence:
    def __init__(self):
        self.bodies, self.directories, self.authors = {}, {}, {}

    def raw(self, path):
        if path not in self.bodies:
            raise FileNotFoundError(path)
        return self.bodies[path]

    def entries(self, path):
        return self.directories[path]

    def author(self, path, expected):
        inherit.require(self.authors.get(path) == expected, "committed author mismatch")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("inheritance unit test attempted a network connection")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture
def evidence():
    env = {
        "GITHUB_REPOSITORY": "fixture/repository", "GITHUB_SHA": "a" * 40,
        "GITHUB_ACTOR": "github-actions[bot]", "GITHUB_TRIGGERING_ACTOR": "github-actions[bot]",
        "GRADE_EXPERIMENT_YAML": "exp037_sol_first25", "GRADE_EXPERIMENT_SLUG": "exp037_sol_first25",
        "GRADE_CONFIG": "exp037_v2_sol_max.yaml", "GRADE_INFERENCE_REVISION": "b" * 40,
        "GRADE_BOT_EMAIL": BOT, "GRADE_SHARD_COUNT": "1", "GRADE_SHARD_INDEX": "0",
        "GRADE_RUN_ORDINAL": "1", "GRADE_TASKS_LIMIT": "0", "GRADE_TASKS": "", "GRADE_FORCE": "false",
        "GRADE_DRY_RUN": "false", "GRADE_PAID_APPROVAL": "true", "GRADE_RESUME": "true",
        "GRADE_RESUME_CHUNK": "1",
    }
    config_hash = hashlib.sha256(CONFIG).hexdigest()[:16]
    stem = (f"exp037_sol_first25__judge_sol__exp037_v2_sol_max__cfg_{config_hash}"
            f"__rubric_{'d' * 40}__inference_{'b' * 40}__src_{'c' * 16}__v2.2")
    partial_path = f"data/grades/{stem}.json"
    progress_path = f"data/grades/_progress/{stem}__task-b.json"
    journal_path = "data/grades/_combined_usd/exp037_sol_first25/run-123-1.combined_usd.jsonl"
    partial = {
        "experiment_id": env["GRADE_EXPERIMENT_YAML"], "experiment_yaml_name": env["GRADE_EXPERIMENT_YAML"],
        "source_inference_revision": "b" * 40, "grader_source_hash": "c" * 64,
        "run_status": "partial", "tasks": [{"task_id": "task-a"}],
        "judge": {"config_name": "exp037_v2_sol_max", "config_hash": config_hash},
        "runner_evidence": receipt("grading", {
            "run_id": "123", "run_attempt": "1", "github_actions": "true",
            "runner_environment": "github-hosted", "os_id": "ubuntu", "os_version_id": "24.04",
            "image_os": "ubuntu24", "platform_system": "Linux", "github_hosted": True,
            "eligible_for_execution": True,
        }),
    }
    progress = {"format": "task-progress-v1", "task_id": "task-b", "grader_source_hash": "c" * 64,
                "completed_items": [{"rubric_item_id": "item-a"}]}
    journal = [
        {"event": "open", "seq": 0, "schema": "sol-batch-grading-journal-v1",
         "experiment_id": env["GRADE_EXPERIMENT_YAML"], "config_name": "exp037_v2_sol_max",
         "inference_revision": "b" * 40, "github_run_id": "123", "github_run_attempt": "1",
         "ceiling_usd": "700", "committed_floor_usd": "424.55", "solve_usd": "422.55",
         "narrative_allowance_usd": "2", "prior_grading_usd": "0", "prior_journals": []},
        {"event": "reserve", "seq": 1, "ticket": "g1", "reserve_usd": "1"},
        {"event": "settle", "seq": 2, "ticket": "g1", "spent_usd": "0.5"},
        {"event": "close", "seq": 3, "step8_exit": 7, "spent_usd": "0.5", "pending_usd": "0",
         "committed_usd": "425.05"},
    ]
    files = Evidence()
    files.directories = {
        "data/grades": [{"type": "file", "name": f"{stem}.json"}, {"type": "dir", "name": "_progress"}],
        "data/grades/_progress": [{"type": "file", "name": f"{stem}__task-b.json"}],
        "data/grades/_combined_usd/exp037_sol_first25": [{"type": "file", "name": Path(journal_path).name}],
    }
    files.bodies = {partial_path: encoded(partial), progress_path: encoded(progress),
                    journal_path: b"".join(encoded(row) + b"\n" for row in journal)}
    files.authors = dict.fromkeys(files.bodies, BOT)
    return files, env, partial_path, progress_path, journal_path


def resolve(evidence):
    files, env, *_ = evidence
    return inherit.resolve(files, env, "exp037_v2_sol_max", CONFIG)


@pytest.mark.parametrize("finished_task", [True, False])
def test_single_shard_inherits_the_actual_partial_progress_and_usd_layout(evidence, finished_task):
    files, _, partial_path, *_ = evidence
    if not finished_task:
        partial = json.loads(files.bodies[partial_path])
        partial["tasks"] = []
        files.bodies[partial_path] = encoded(partial)
    assert resolve(evidence) == partial_path
    assert "_shards" not in partial_path


@pytest.mark.parametrize("path_index", [2, 3, 4])
def test_a_different_approval_lineage_writer_is_refused(evidence, path_index):
    evidence[0].authors[evidence[path_index]] = "someone-else@example.invalid"
    with pytest.raises(inherit.InheritanceRefused, match="committed author mismatch"):
        resolve(evidence)


@pytest.mark.parametrize("path_index", [2, 3, 4])
def test_a_missing_committed_file_is_refused(evidence, path_index):
    del evidence[0].bodies[evidence[path_index]]
    with pytest.raises(FileNotFoundError):
        resolve(evidence)


def test_progress_or_usd_without_a_partial_never_inherits(evidence):
    evidence[0].directories["data/grades"] = [{"type": "dir", "name": "_progress"}]
    with pytest.raises(inherit.InheritanceRefused, match="missing or ambiguous"):
        resolve(evidence)


@pytest.mark.parametrize("field,value", [
    ("experiment_id", "another-experiment"), ("source_inference_revision", "e" * 40),
    ("run_status", "completed"), ("grader_source_hash", "e" * 64),
])
def test_a_different_partial_identity_cannot_inherit(evidence, field, value):
    files, _, path, *_ = evidence
    partial = json.loads(files.bodies[path])
    partial[field] = value
    files.bodies[path] = encoded(partial)
    with pytest.raises(inherit.InheritanceRefused):
        resolve(evidence)


@pytest.mark.parametrize("field,value", [("runner_environment", "self-hosted"), ("os_version_id", "26.04")])
def test_a_different_recorded_grading_environment_is_refused(evidence, field, value):
    files, _, path, *_ = evidence
    partial = json.loads(files.bodies[path])
    observed = partial["runner_evidence"]["observation"]
    observed[field] = value
    partial["runner_evidence"] = receipt("grading", observed)
    files.bodies[path] = encoded(partial)
    with pytest.raises(inherit.InheritanceRefused, match="grading environment"):
        resolve(evidence)


@pytest.mark.parametrize("ceiling", ["425.05", "425.04", "NaN", "Infinity", "-1"])
def test_a_reached_or_invalid_usd_ceiling_refuses_inheritance(evidence, ceiling):
    files, _, _, _, path = evidence
    rows = [json.loads(row) for row in files.bodies[path].splitlines()]
    rows[0]["ceiling_usd"] = ceiling
    files.bodies[path] = b"".join(encoded(row) + b"\n" for row in rows)
    with pytest.raises(inherit.InheritanceRefused):
        resolve(evidence)


@pytest.mark.parametrize("field,value", [("experiment_id", "other"), ("github_run_id", "124")])
def test_another_runs_usd_journal_is_not_evidence(evidence, field, value):
    files, _, _, _, path = evidence
    rows = [json.loads(row) for row in files.bodies[path].splitlines()]
    rows[0][field] = value
    files.bodies[path] = b"".join(encoded(row) + b"\n" for row in rows)
    with pytest.raises(inherit.InheritanceRefused, match="USD journal"):
        resolve(evidence)


def test_a_newer_journal_cannot_hide_behind_an_older_partial(evidence):
    directory = "data/grades/_combined_usd/exp037_sol_first25"
    evidence[0].directories[directory].append({"type": "file", "name": "run-124-1.combined_usd.jsonl"})
    with pytest.raises(inherit.InheritanceRefused, match="committed USD journal set"):
        resolve(evidence)


@pytest.mark.parametrize("mutation", [None, "bytes", "total"])
def test_prior_usd_spend_remains_bound_to_the_committed_journal_set(evidence, mutation):
    files, _, _, _, journal_path = evidence
    previous_path = journal_path.replace("run-123-1", "run-122-1")
    prior_rows = [json.loads(row) for row in files.bodies[journal_path].splitlines()]
    prior_rows[0]["github_run_id"] = "122"
    previous = b"".join(encoded(row) + b"\n" for row in prior_rows)
    rows = [json.loads(row) for row in files.bodies[journal_path].splitlines()]
    rows[0]["prior_journals"] = [{"path": previous_path, "sha256": hashlib.sha256(previous).hexdigest(),
                                 "spent_usd": "0.5"}]
    rows[0]["prior_grading_usd"] = "0.5"
    rows[0]["committed_floor_usd"] = "425.05"
    rows[-1]["committed_usd"] = "425.55"
    if mutation == "total":
        rows[0]["prior_journals"][0]["spent_usd"] = "0.4"
    files.bodies[journal_path] = b"".join(encoded(row) + b"\n" for row in rows)
    files.bodies[previous_path] = previous + (b" " if mutation == "bytes" else b"")
    files.authors[previous_path] = BOT
    files.directories[previous_path.rsplit("/", 1)[0]].append({"type": "file", "name": Path(previous_path).name})
    if mutation is None:
        assert resolve(evidence) == evidence[2]
    else:
        with pytest.raises(inherit.InheritanceRefused, match="USD journal"):
            resolve(evidence)


@pytest.mark.parametrize("key,value", [
    ("GRADE_RUN_ORDINAL", "2"), ("GRADE_TASKS_LIMIT", "1"), ("GRADE_TASKS", "task-a"),
    ("GRADE_FORCE", "true"), ("GITHUB_ACTOR", "human"), ("GRADE_RESUME_CHUNK", "0"),
])
def test_no_scope_widening_or_manual_dispatch_inherits(evidence, key, value):
    evidence[1][key] = value
    with pytest.raises(inherit.InheritanceRefused):
        resolve(evidence)


def run_workflow(tmp_path, evidence, *, shard_count="1", author=BOT, present=True):
    files, original_env, partial_path, *_ = evidence
    env = dict(original_env, GRADE_SHARD_COUNT=shard_count)
    config_route = f"contents/batch-runner/grading_configs/{env['GRADE_CONFIG']}?ref={env['GITHUB_SHA']}"
    routes = {config_route: {"content": base64.b64encode(CONFIG).decode()}}
    for path, body in files.bodies.items():
        routes[f"contents/{path}?ref={env['GITHUB_SHA']}"] = body.decode()
    for path, rows in files.directories.items():
        routes[f"contents/{path}?ref={env['GITHUB_SHA']}"] = rows
    for path, email in files.authors.items():
        routes[f"commits?path={path}&sha={env['GITHUB_SHA']}&per_page=1"] = [{"commit": {"author": {"email": email}}}]
    helper_route = f"contents/batch-runner/grade_single_shard_inheritance.py?ref={env['GITHUB_SHA']}"
    routes[helper_route] = HELPER.read_text()
    stem = Path(partial_path).stem
    shard = f"data/grades/_shards/{stem}/shard-000-of-{int(shard_count):03d}.json"
    routes["contents/data/grades/_shards?ref=main"] = [{"type": "dir", "name": stem}]
    if present:
        routes[f"contents/{shard}?ref=main"] = {"sha": "f" * 40}
    routes[f"commits?path={shard}&sha=main&per_page=1"] = [{"commit": {"author": {"email": author}}}]
    fixture_path = tmp_path / "responses.json"
    fixture_path.write_text(json.dumps(routes))
    bin_path = tmp_path / "bin"
    bin_path.mkdir()
    gh = bin_path / "gh"
    gh.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
endpoint = next(arg for arg in args if arg.startswith("repos/"))
route = endpoint.split("/", 3)[3]
with open(os.environ["FIXTURE_LOG"], "a") as log:
    log.write(route + "\\n")
responses = json.loads(Path(os.environ["FIXTURE_RESPONSES"]).read_text())
if route not in responses:
    raise SystemExit(1)
value = responses[route]
if "--jq" in args:
    expression = args[args.index("--jq") + 1]
    if expression == '.content // ""': value = value.get("content", "")
    elif expression == '.[] | select(.type == "dir") | .name':
        value = "\\n".join(row["name"] for row in value if row["type"] == "dir")
    elif expression == '.sha': value = value["sha"]
    elif expression == '.[0].commit.author.email // ""': value = value[0]["commit"]["author"]["email"]
    else: raise SystemExit("unexpected fake gh query")
print(value if isinstance(value, str) else json.dumps(value), end="" if isinstance(value, str) else "\\n")
''')
    gh.chmod(0o755)
    # This PATH contains no real gh. Even a malformed fixture cannot reach GitHub.
    env.update(PATH=f"{bin_path}:{Path(sys.executable).parent}:/usr/bin:/bin", LANG="C.UTF-8",
               RUNNER_TEMP=str(tmp_path), GITHUB_OUTPUT=str(tmp_path / "output"),
               FIXTURE_LOG=str(tmp_path / "calls"), FIXTURE_RESPONSES=str(fixture_path),
               PYTHONDONTWRITEBYTECODE="1")
    workflow = yaml.safe_load(WORKFLOW.read_text())
    step = next(step for step in workflow["jobs"]["validate-request"]["steps"] if step.get("id") == "inherit")
    result = subprocess.run(["/bin/bash", "-c", step["run"]], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return (tmp_path / "output").read_text(), (tmp_path / "calls").read_text(), result


def test_workflow_uses_the_single_shard_proof_at_one_immutable_main_sha(tmp_path, evidence):
    output, calls, result = run_workflow(tmp_path, evidence)
    assert output == "approval_inherited=true\n", result.stderr
    assert "_shards" not in calls and "?ref=main" not in calls and "&sha=main" not in calls
    assert "grade_single_shard_inheritance.py?ref=" in calls
    assert evidence[2] in result.stdout


@pytest.mark.parametrize("missing", [False, True])
def test_single_shard_denial_keeps_the_environment_gate(tmp_path, evidence, missing):
    if missing:
        evidence[0].bodies.pop(evidence[4])
    else:
        evidence[0].authors[evidence[2]] = "wrong-author@example.invalid"
    output, _, _ = run_workflow(tmp_path, evidence)
    assert output == "approval_inherited=false\n"


@pytest.mark.parametrize("author,present,expected", [(BOT, True, "true"), ("wrong", True, "false"), (BOT, False, "false")])
def test_multi_shard_path_is_unchanged(tmp_path, evidence, author, present, expected):
    output, calls, _ = run_workflow(tmp_path, evidence, shard_count="2", author=author, present=present)
    assert output == f"approval_inherited={expected}\n"
    assert "shard-000-of-002.json?ref=main" in calls
    assert "grade_single_shard_inheritance.py" not in calls


def test_protected_approval_and_full_usd_preflight_are_not_bypassed():
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    assert jobs["approve-paid"]["environment"] == {"name": "grading"}
    assert "needs.validate-request.outputs.approval_inherited != 'true'" in jobs["approve-paid"]["if"]
    steps = jobs["grade"]["steps"]
    usd = next(index for index, step in enumerate(steps) if step.get("id") == "sol_usd")
    login = next(index for index, step in enumerate(steps) if "azure/login@" in step.get("uses", ""))
    assert usd < login and "python sol_batch_grading.py preflight" in steps[usd]["run"]
    assert "approval_inherited" not in steps[usd].get("if", "")
