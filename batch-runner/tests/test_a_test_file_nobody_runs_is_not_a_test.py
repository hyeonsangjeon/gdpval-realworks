"""A test file that no CI job executes gates nothing, and says nothing.

`scripts/__tests__/` sat outside CI for its whole life. The backend job
changes into `batch-runner` before invoking pytest, and `npm test` picks up
only the `.mjs` files that share that directory, so eight Python files and
ninety-five test functions ran nowhere. Two of them were red on `main` --
`test_sol_max_anchor_selection.py` since #188 (2026-08-21) and
`test_analyze_grade_run.py` since #302 (2026-08-31) -- and nothing reported
it. They were found by hand, days later.

Wiring that directory in fixes the instance. This guards the class: a third
directory of tests can be added just as easily, and it would be just as
silent. So every Python test file in the repository has to live somewhere a
CI job actually runs, and the roots below have to be the ones the workflow
names -- otherwise deleting the step would leave this passing.

This guard deliberately lives under `batch-runner/tests/`, the directory CI
has run since the beginning. In `scripts/__tests__/` it could be switched off
by the very defect it exists to catch.
"""

from __future__ import annotations

import ast
import os
import shlex
import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest
import yaml
from _pytest.mark.expression import Expression

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/backend-tests.yml"

# Every directory a pytest invocation in backend-tests.yml reaches. Adding a
# test directory means adding a step there and a line here, in one commit.
COVERED_ROOTS = (
    "batch-runner/tests",
    "scripts/__tests__",
)


def _test_files() -> list[Path]:
    return sorted(
        path
        for path in REPO_ROOT.rglob("test_*.py")
        if ".git" not in path.parts and "__pycache__" not in path.parts
    )


def _pytest_target_arguments(args: list[str]) -> list[str]:
    """Separate positional targets using only the workflow's option syntax."""
    targets = []
    tokens = iter(args)
    for token in tokens:
        if token == "--":
            targets.extend(tokens)
            break
        if token in {"-k", "-m", "-r", "--tb", "--ignore"}:
            value = next(tokens, None)
            assert value is not None and not value.startswith("-"), "missing pytest option value"
        elif token in {"-q", "-v"}:
            continue
        elif token.startswith(("-k", "-m", "-r", "--tb=", "--ignore=")):
            # Short attached values (-rs/-kexpr) and long --option=value forms.
            continue
        else:
            assert not token.startswith("-"), "unsupported pytest option in workflow"
            targets.append(token)
    return targets


def _pytest_targets() -> set[Path]:
    """The directories the workflow's pytest invocations actually reach.

    Matching the workflow text for a directory name is not enough -- the name
    appears in comments too, and a comment runs nothing. This reads the
    invocations: a `run:` block may `cd` somewhere first, and an invocation
    with no path argument collects everything beneath wherever it is standing.

    Classify options and their values before inspecting the filesystem.
    A keyword/marker expression or another option value is never evidence
    of directory coverage, even when it names an existing directory.
    """
    targets: set[Path] = set()
    base = REPO_ROOT

    for raw in WORKFLOW.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continue
        if line.startswith("- name:"):
            base = REPO_ROOT  # a new step starts back at the repo root
        elif line.startswith("cd "):
            base = REPO_ROOT / line[3:].strip()
        elif "python -m pytest" in line:
            args = shlex.split(line.split("python -m pytest", 1)[1])
            positional = _pytest_target_arguments(args)
            paths = [base / arg for arg in positional if (base / arg).is_dir()]
            targets.update(path.resolve() for path in (paths or [base]))

    return targets


@pytest.fixture
def synthetic_workflow(tmp_path, monkeypatch):
    workflow = tmp_path / "backend-tests.yml"
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "WORKFLOW", workflow)
    return workflow


@pytest.mark.parametrize("option", ["-k", "-m"])
@pytest.mark.parametrize("attached", [False, True])
def test_pytest_targets_long_quoted_option_values_are_not_paths(
    synthetic_workflow, tmp_path, option, attached,
):
    target = tmp_path / "tests"
    target.mkdir()
    expression = "condition_" * 40 + " or another_condition"
    assert len(expression.encode()) > 255
    options = [option + expression] if attached else [option, expression]
    synthetic_workflow.write_text(
        "run: python -m pytest -q --tb=short -rs "
        + shlex.join([*options, "tests"]) + "\n",
        encoding="utf-8",
    )
    assert _pytest_targets() == {target}


@pytest.mark.parametrize("option,value", [
    ("-k", "other_tests"), ("-m", "other_tests"), ("-r", "s"),
    ("--tb", "short"), ("--ignore", "other_tests"),
])
@pytest.mark.parametrize("attached", [False, True])
def test_pytest_targets_only_positionals_reach_filesystem_inspection(
    synthetic_workflow, tmp_path, monkeypatch, option, value, attached,
):
    target = tmp_path / "selected_tests"
    target.mkdir()
    (tmp_path / value).mkdir()
    if attached:
        options = [option + ("=" if option.startswith("--") else "") + value]
    else:
        options = [option, value]
    synthetic_workflow.write_text(
        "run: python -m pytest " + shlex.join([*options, "-q", "selected_tests"]) + "\n",
        encoding="utf-8",
    )
    inspected, original = [], Path.is_dir

    def tracked(path):
        inspected.append(path)
        return original(path)

    monkeypatch.setattr(Path, "is_dir", tracked)
    assert _pytest_targets() == {target}
    assert inspected == [target]


@pytest.mark.parametrize("directory,args,expected", [
    (".", [], ["."]),
    ("batch-runner", [], ["batch-runner"]),
    ("batch-runner", ["-m", "not integration", "--tb=short", "-q", "-rs", "--ignore=excluded"],
     ["batch-runner"]),
    ("batch-runner", ["tests", "-m", "not integration", "-q"], ["batch-runner/tests"]),
    ("batch-runner", ["-q", "tests", "other tests"], ["batch-runner/tests", "batch-runner/other tests"]),
    ("batch-runner", ["-q", "--", "-k"], ["batch-runner/-k"]),
])
def test_pytest_targets_preserve_positional_directories_and_default_cwd(
    synthetic_workflow, tmp_path, directory, args, expected,
):
    for name in ("tests", "other tests", "excluded", "-k"):
        (tmp_path / "batch-runner" / name).mkdir(parents=True)
    synthetic_workflow.write_text(
        "- name: tests\n  run: |\n    cd " + directory
        + "\n    python -m pytest " + shlex.join(args) + "\n",
        encoding="utf-8",
    )
    assert _pytest_targets() == {(tmp_path / name).resolve() for name in expected}


def test_pytest_targets_next_step_resets_to_repo_root(synthetic_workflow, tmp_path):
    runner = tmp_path / "batch-runner"
    scripts = tmp_path / "scripts" / "__tests__"
    runner.mkdir()
    scripts.mkdir(parents=True)
    synthetic_workflow.write_text(
        "- name: core\n  run: |\n    cd batch-runner\n    python -m pytest -q\n"
        "- name: scripts\n  run: python -m pytest scripts/__tests__ -m 'not integration' -q\n",
        encoding="utf-8",
    )
    assert _pytest_targets() == {runner, scripts}


@pytest.mark.parametrize("args,refusal", [
    (["-k"], "missing pytest option value"),
    (["--ignore"], "missing pytest option value"),
    (["-k", "-q", "tests"], "missing pytest option value"),
    (["--ignore", "--future-option", "tests"], "missing pytest option value"),
    (["-m", "--", "tests"], "missing pytest option value"),
    (["--future-option", "tests"], "unsupported pytest option in workflow"),
])
def test_pytest_targets_unknown_or_incomplete_options_refuse_before_paths(
    synthetic_workflow, monkeypatch, args, refusal,
):
    synthetic_workflow.write_text(
        "run: python -m pytest " + shlex.join(args) + "\n", encoding="utf-8",
    )

    def forbidden(_):
        pytest.fail("option parsing must finish before filesystem inspection")

    with monkeypatch.context() as patches:
        patches.setattr(Path, "is_dir", forbidden)
        with pytest.raises(AssertionError, match=refusal):
            _pytest_targets()


def test_every_python_test_file_sits_under_a_root_ci_runs():
    files = _test_files()

    # If this is ever near-empty the check below passes for the wrong reason.
    assert len(files) > 100, f"only found {len(files)} test files; rglob broke"

    stranded = [
        str(path.relative_to(REPO_ROOT))
        for path in files
        if not str(path.relative_to(REPO_ROOT)).startswith(COVERED_ROOTS)
    ]
    assert not stranded, (
        "these test files are not under any root backend-tests.yml runs, so "
        "nothing executes them and they can be red indefinitely without a "
        f"single red run: {stranded}"
    )


@pytest.mark.parametrize("root", COVERED_ROOTS)
def test_the_workflow_still_runs_each_root_this_file_vouches_for(root: str):
    """The list above is only true while the workflow still runs each root.

    Without this, removing a pytest step would strand a whole directory again
    and the check above would keep passing -- it would simply be reading a
    list that had quietly stopped describing CI.
    """
    directory = (REPO_ROOT / root).resolve()
    targets = _pytest_targets()

    assert any(
        directory == target or target in directory.parents for target in targets
    ), (
        f"{root} is listed as CI-covered here, but no pytest invocation in "
        f"{WORKFLOW.name} reaches it. Reached instead: "
        f"{sorted(str(t.relative_to(REPO_ROOT)) or '.' for t in targets)}. "
        "Either restore the step or stop claiming the directory is covered."
    )


def test_the_orphaned_directory_that_prompted_this_is_actually_wired():
    """The specific regression, pinned separately from the general rule.

    The rule above is satisfied by any invocation reaching the path, including
    one rooted higher up. This asserts the shape that was missing: a pytest run
    naming the directory, from the repository root.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "python -m pytest scripts/__tests__" in workflow, (
        "the repo-root script tests are unwired again; they resolve fixtures "
        "through parents[2] and must be invoked from the repository root"
    )


def test_backend_jobs_partition_the_comparison_contracts():
    """Eight jobs cover every node once, including wire and preflight splits."""
    text = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    jobs = workflow["jobs"]
    assert set(jobs) == {
        "pytest", "comparison-contracts", "pilot-contracts", "pilot-preflight-contracts",
        "pilot-external-receipt-contracts", "pilot-external-publication-contracts",
        "wire-contracts", "native-host-contracts"
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "backend-tests-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    assert "secrets." not in text
    assert "id-token" not in text
    for name, job in jobs.items():
        # No renamed check, matrix, dependencies, credentials or job-level skip.
        assert set(job) == {"runs-on", "timeout-minutes", "steps"}
        assert job["runs-on"] == "ubuntu-latest"
        assert job["timeout-minutes"] == (60 if name == "native-host-contracts" else 45)

    core = jobs["pytest"]["steps"]
    comparison = jobs["comparison-contracts"]["steps"]
    pilot = jobs["pilot-contracts"]["steps"]
    pilot_preflight = jobs["pilot-preflight-contracts"]["steps"]
    pilot_external = jobs["pilot-external-receipt-contracts"]["steps"]
    pilot_publication = jobs["pilot-external-publication-contracts"]["steps"]
    wire = jobs["wire-contracts"]["steps"]
    native_host = jobs["native-host-contracts"]["steps"]
    setup_names = [
        "Verify dispatch contract",
        "Checkout",
        "Verify exact checkout",
        "Setup Python",
        "Install dependencies",
        "Verify integration tests stay deselected",
    ]
    assert [step["name"] for step in core] == setup_names + [
        "Run tests",
        "Run repo-root script tests",
    ]
    assert [step["name"] for step in comparison] == setup_names + [
        "Run comparison contracts"
    ]
    assert [step["name"] for step in pilot] == setup_names + ["Run pilot contracts"]
    assert [step["name"] for step in pilot_preflight] == setup_names + ["Run pilot preflight contracts"]
    assert [step["name"] for step in pilot_external] == setup_names + ["Run pilot external receipt contracts"]
    assert [step["name"] for step in pilot_publication] == setup_names + ["Run pilot external publication contracts"]
    assert [step["name"] for step in wire] == setup_names + ["Run wire contracts"]
    assert [step["name"] for step in native_host] == setup_names + ["Run native host contracts"]
    assert all(steps[:6] == core[:6] for steps in (
        comparison, pilot, pilot_preflight, pilot_external, pilot_publication,
        wire, native_host,
    ))
    assert core[1] == {
        "name": "Checkout",
        "uses": "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
        "with": {"fetch-depth": 0, "persist-credentials": False},
    }
    assert core[3] == {
        "name": "Setup Python",
        "uses": "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "with": {
            "python-version": "3.10.12",
            "cache": "pip",
            "cache-dependency-path": "batch-runner/requirements.txt",
        },
    }
    assert core[4] == {
        "name": "Install dependencies",
        "run": "cd batch-runner\npip install -r requirements.txt\n",
    }
    for index in (0, 2):
        assert set(core[index]) == {"name", "if", "env", "run"}
        assert core[index]["if"] == "github.event_name == 'workflow_dispatch'"
        assert "set -euo pipefail" in core[index]["run"]
    assert core[0]["env"] == {
        "EXPECTED_SHA": "${{ inputs.expected_sha }}",
        "WORKFLOW_SHA": "${{ github.workflow_sha }}",
    }
    assert core[2]["env"] == {"EXPECTED_SHA": "${{ inputs.expected_sha }}"}
    for assertion in (
        '[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]',
        '[[ "$GITHUB_SHA" == "$EXPECTED_SHA" ]]',
        '[[ "$WORKFLOW_SHA" == "$EXPECTED_SHA" ]]',
    ):
        assert assertion in core[0]["run"]
    assert '[[ "$(git rev-parse HEAD)" == "$EXPECTED_SHA" ]]' in core[2]["run"]
    assert set(core[5]) == {"name", "run"}
    assert 'grep -qE \'^addopts = .*-m "not integration"\' pytest.ini' in core[5]["run"]
    assert "exit 1" in core[5]["run"]
    assert core[-1] == {
        "name": "Run repo-root script tests",
        "run": 'python -m pytest scripts/__tests__ -m "not integration" --tb=short -q -rs',
    }

    argv = []
    for step, command_count in (
        (core[6], 1), (comparison[6], 1), (pilot[6], 1),
        (pilot_preflight[6], 1), (pilot_external[6], 1), (pilot_publication[6], 1),
        (wire[6], 1), (native_host[6], 1)
    ):
        assert set(step) == {"name", "run"}
        lines = step["run"].splitlines()
        assert len(lines) == command_count + 1 and lines[0] == "cd batch-runner"
        argv.extend(shlex.split(line) for line in lines[1:])
    prefix = [
        "python", "-m", "pytest", "-m", "not integration", "--tb=short", "-q", "-rs"
    ]
    assert all(command[:len(prefix)] == prefix for command in argv)
    excluded = [arg.removeprefix("--ignore=") for arg in argv[0][len(prefix):]]
    selected = argv[1][len(prefix):]
    pilot_selected = argv[2][len(prefix):]
    pilot_preflight_selected = argv[3][len(prefix):]
    pilot_external_selected = argv[4][len(prefix):]
    pilot_publication_selected = argv[5][len(prefix):]
    wire_selected = argv[6][len(prefix):]
    native_selected = argv[7][len(prefix):]

    runner = REPO_ROOT / "batch-runner"
    tests = runner / "tests"
    comparison_files = sorted(
        path.relative_to(runner).as_posix()
        for path in tests.glob("test_gpt54_*.py")
    )
    pilot_files = sorted(
        path.relative_to(runner).as_posix()
        for path in tests.glob("test_gpt56_*.py")
    )
    assert len(comparison_files) == 11 and len(pilot_files) == 9
    wire_file = "tests/test_gpt56_pilot_wire_receipt.py"
    pilot_preflight_file = "tests/test_gpt56_sol_codex_pilot_preflight.py"
    publication_functions = (
        "test_external_live_receipt_real_owners_ready_last_and_no_disk_adoption_or_reuse",
        "test_external_live_receipt_mid_publication_drift_and_partials_cannot_be_adopted",
        "test_external_live_receipt_every_real_infrastructure_attempt_is_bound_without_inferred_calls",
    )
    publication_expression = " or ".join(publication_functions)
    keyword = "native_result_host"
    assert wire_file in pilot_files
    assert pilot_preflight_file in pilot_files
    general_pilot_files = [path for path in pilot_files if path not in {wire_file, pilot_preflight_file}]
    assert len(general_pilot_files) == 7
    actual = sorted(comparison_files + pilot_files)
    assert argv[0][len(prefix):] == [f"--ignore={path}" for path in actual]
    assert excluded == actual
    assert selected == comparison_files
    assert pilot_selected == general_pilot_files
    assert pilot_preflight_selected == [pilot_preflight_file, "-k", "not external_live_receipt"]
    assert pilot_external_selected == [
        pilot_preflight_file, "-k", f"external_live_receipt and not ({publication_expression})"
    ]
    assert pilot_publication_selected == [pilot_preflight_file, "-k", publication_expression]
    assert wire_selected == [wire_file, "-k", f"not {keyword}"]
    assert native_selected == [wire_file, "-k", keyword]
    assert len(excluded) == len(set(excluded))
    assert len(selected) == len(set(selected))
    assert len(pilot_selected) == len(set(pilot_selected))
    assert len(pilot_preflight_selected) == len(set(pilot_preflight_selected))

    pilot_sources = {path: (runner / path).read_text(encoding="utf-8") for path in pilot_files}
    assert {path for path, source in pilot_sources.items() if keyword in source.casefold()} == {wire_file}
    # Use pytest's own expression parser, without collecting/importing the
    # shared file. Both possible keyword-match states must select one job,
    # including parametrized nodes whose IDs can affect keyword matching.
    predicates = [Expression.compile(arguments[-1]) for arguments in (wire_selected, native_selected)]
    for matches in (False, True):
        assert sum(predicate.evaluate(lambda name: matches if name == keyword else False)
                   for predicate in predicates) == 1
    wire_nodes = [node.name for node in ast.walk(ast.parse(pilot_sources[wire_file]))
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")]
    assert wire_nodes and len(wire_nodes) == len(set(wire_nodes))
    node_selections = [{node for node in wire_nodes
                        if predicate.evaluate(lambda name: name.casefold() in node.casefold())}
                       for predicate in predicates]
    assert all(node_selections)
    assert not node_selections[0] & node_selections[1]
    assert node_selections[0] | node_selections[1] == set(wire_nodes)

    def collect_preflight_nodes(arguments: list[str]) -> set[str]:
        # Collection runs imports/hooks but not fixtures or test bodies. Keep
        # it scoped to this one file, with the workflow's non-integration filter.
        assert arguments[0] == pilot_preflight_file
        result = subprocess.run(
            [sys.executable, *prefix[1:], "--collect-only", "-p", "no:cacheprovider",
             "-o", "addopts=", "--color=no", *arguments],
            cwd=runner,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_ADDOPTS": ""},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        nodes = [line for line in result.stdout.splitlines()
                 if line.startswith(pilot_preflight_file + "::")]
        assert nodes, result.stdout
        assert len(nodes) == len(set(nodes)), "duplicate collected preflight node IDs"
        return set(nodes)

    # Ask pytest itself about full parameterized node IDs and -k semantics.
    # No AST/regex approximation can establish this three-way partition.
    all_preflight_nodes = collect_preflight_nodes([pilot_preflight_file])
    preflight_node_sets = [collect_preflight_nodes(arguments) for arguments in (
        pilot_preflight_selected, pilot_external_selected, pilot_publication_selected,
    )]
    assert all(preflight_node_sets)
    for index, nodes in enumerate(preflight_node_sets):
        assert all(not nodes & other for other in preflight_node_sets[index + 1:])
    assert set().union(*preflight_node_sets) == all_preflight_nodes
    publication_nodes = {
        node for node in all_preflight_nodes
        if node.split("::")[-1].split("[", 1)[0] in publication_functions
    }
    assert {node.split("::")[-1].split("[", 1)[0] for node in publication_nodes} == set(publication_functions)
    assert preflight_node_sets[2] == publication_nodes

    discovery = ConfigParser()
    discovery.read(runner / "pytest.ini")
    assert discovery["pytest"]["testpaths"] == "tests"
    assert discovery["pytest"]["python_files"] == "test_*.py"
    all_tests = {
        path.relative_to(runner).as_posix() for path in tests.rglob("test_*.py")
    }
    core_tests = all_tests - set(excluded)
    comparison_tests = set(selected)
    pilot_tests = set(pilot_selected)
    pilot_preflight_tests = {pilot_preflight_file}
    shared_wire_tests = {wire_file}
    assert not core_tests & comparison_tests
    assert not core_tests & pilot_tests
    assert not comparison_tests & pilot_tests
    assert not core_tests & pilot_preflight_tests
    assert not comparison_tests & pilot_preflight_tests
    assert not pilot_tests & pilot_preflight_tests
    assert not core_tests & shared_wire_tests
    assert not comparison_tests & shared_wire_tests
    assert not pilot_tests & shared_wire_tests
    assert not pilot_preflight_tests & shared_wire_tests
    # Every other file is selected once without a keyword filter. The shared
    # wire and preflight files have exhaustive/disjoint node splits above.
    assert core_tests | comparison_tests | pilot_tests | pilot_preflight_tests | shared_wire_tests == all_tests


@pytest.mark.parametrize("root", COVERED_ROOTS)
def test_a_change_under_each_covered_root_actually_starts_this_workflow(root: str):
    """A step that exists but never fires is still a step nobody runs.

    Wiring the invocation fixed half of it. The trigger did not follow: the
    path filter listed only `batch-runner/**`, so a pull request touching
    just repo-root `scripts/` started no run, and the step above never
    executed on the change it was added to cover.

    Measured, not inferred -- #392 changed `scripts/grading_cost_sweep.py` and
    added twenty-five tests under `scripts/__tests__/`, and the only workflow
    that ran on it was Aggregate Tests & Deploy. The suite was green and
    nothing had checked it.
    """
    triggers = _trigger_block()

    for event in ("pull_request", "push"):
        patterns = triggers[event]["paths"]
        assert any(_pattern_covers(pattern, root) for pattern in patterns), (
            f"a change under {root}/ starts no {event} run of "
            f"{WORKFLOW.name}, so the pytest step that covers it never "
            f"executes. Filter is: {patterns}"
        )


def _trigger_block() -> dict:
    """The workflow's `on:` mapping.

    Keyed by `True`, not by `"on"` -- PyYAML follows YAML 1.1, where a bare
    `on` is a boolean. Reading `["on"]` here would raise `KeyError` rather
    than check anything, so both spellings are accepted.
    """
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), f"no trigger block in {WORKFLOW.name}"
    return triggers


def _pattern_covers(pattern: str, root: str) -> bool:
    """Whether a workflow path filter would match a file under `root`.

    Only the `dir/**` and exact-path forms this workflow uses are understood;
    anything cleverer should be checked deliberately rather than guessed at.
    """
    if pattern.endswith("/**"):
        return (root + "/").startswith(pattern[:-2])
    return pattern == root
