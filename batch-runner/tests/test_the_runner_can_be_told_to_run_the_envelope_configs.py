"""The workflow that runs experiments can be handed the run-place configs.

The run-place comparison keeps its three experiment configs beside the plan
that fixes their conditions::

    batch-runner/experiments/execution_envelope/exp030_envelope_host_python_process.yaml
    batch-runner/experiments/execution_envelope/exp031_envelope_docker_container.yaml
    batch-runner/experiments/execution_envelope/exp032_envelope_azure_code_interpreter.yaml

``advance_check_plan.yaml`` names all three in its ``experiment_files`` block,
two test files assert those paths, and the specification's table writes them.
The one workflow that can run an experiment, ``.github/workflows/batch-run.yml``,
takes the config as ``experiment_yaml`` — an extensionless name it joins onto
``batch-runner/experiments/``. Its check on that name was written before the
directory existed and admitted no separator at all, so every one of the three
stopped on ``invalid experiment YAML name`` before the file was even looked for.

Nothing pointed at it. The free gates read the plan, price the run, compare the
fixed conditions across all three places and report what still blocks the
comparison — and not one of them asks whether the runner can be told the name.
The configs were checked in every way except the way they would be used.

So the check now takes one directory, and these tests hold that. They type
neither the names nor the rule: the names come from the plan and from the files
on disk, and the rule is read back out of the workflow, so a rewrite that
narrows it again fails here rather than at a dispatch.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "batch-run.yml"
EXPERIMENTS_ROOT = BATCH_RUNNER_ROOT / "experiments"
PLAN_PATH = EXPERIMENTS_ROOT / "execution_envelope" / "advance_check_plan.yaml"

# Where the workflow's check on the name starts and stops. Reading between
# these is what keeps this file measuring the real rule instead of a copy of it.
CHECK_OPENS_AT = "valid_name ="
CHECK_CLOSES_AT = "abort('invalid experiment YAML name')"

# The two refusals the workflow spells out beside the pattern. They are asserted
# as written so that dropping one is a failure here and not a discovery later.
GUARDS_WRITTEN_BESIDE_THE_PATTERN = ("include?('..')", "end_with?('.', '.lock')")

# How the workflow turns an accepted name into a file to look for.
PATH_THE_WORKFLOW_BUILDS = "File.join('batch-runner', 'experiments', \"#{name}.yaml\")"

# A config the runner can be given, as against a plan that only describes one.
# The workflow loads the file and reads its settings, so the discriminator is a
# key every runnable config carries and neither plan does.
CONFIG_ROOT_KEY = "experiment"

# Names one directory must not have brought in with it. Taking a separator is
# the whole change, so what a separator must still not buy is the whole risk.
NAMES_IT_MUST_REFUSE = [
    ("../secrets", "climbs out of the experiments directory"),
    ("execution_envelope/../../secrets", "climbs out further along"),
    ("/etc/passwd", "starts at the root of the disk"),
    ("execution_envelope/deeper/exp030", "asks for a second directory"),
    (".hidden", "starts with a dot"),
    ("execution_envelope/.hidden", "starts a part with a dot"),
    ("-rf", "starts with a dash"),
    ("execution_envelope/-rf", "starts a part with a dash"),
    ("execution_envelope\\exp030", "separates with a backslash"),
    ("/exp030", "starts with the separator"),
    ("execution_envelope/", "stops at the separator"),
    ("", "is nothing at all"),
    ("exp030.", "ends with a dot"),
    ("exp030.lock", "ends with .lock"),
    ("exp 030", "has a space in it"),
    ("exp030;rm", "carries a second command"),
    ("exp030%2Fsecrets", "hides the separator"),
]


def _read_the_check_out_of_the_workflow() -> str:
    """The workflow's own words for the rule, from the workflow."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    opens = text.find(CHECK_OPENS_AT)
    assert opens != -1, (
        f"{WORKFLOW_PATH.name} no longer contains {CHECK_OPENS_AT!r}, so this "
        "file cannot tell what it now accepts. Point it at the new check "
        "rather than deleting these tests."
    )
    closes = text.find(CHECK_CLOSES_AT, opens)
    assert closes != -1, (
        f"{WORKFLOW_PATH.name} checks the name but no longer refuses it with "
        f"{CHECK_CLOSES_AT!r}."
    )
    return text[opens:closes]


def _pattern_from(check: str) -> re.Pattern[str]:
    """Ruby's literal, compiled by Python.

    The braces are counted rather than searched for, because the pattern
    contains ``{0,99}`` and the first closing brace is that one's, not the
    literal's. Only the anchors are spelled differently between the two
    languages: Ruby writes the ends of the string ``\\A`` and ``\\z``, Python
    writes ``\\A`` and ``\\Z``. Character classes, counts, groups and the
    optional mark all mean the same thing in both, so nothing else is changed.
    """
    body = None
    opens = check.find("%r{")
    if opens != -1:
        depth = 0
        for index in range(opens + 2, len(check)):
            if check[index] == "{":
                depth += 1
            elif check[index] == "}":
                depth -= 1
                if depth == 0:
                    body = check[opens + 3 : index]
                    break
    else:
        slashed = re.search(r"match\?\(\s*/(?P<body>.+?)(?<!\\)/", check, re.DOTALL)
        if slashed is not None:
            body = slashed.group("body").replace(r"\/", "/")

    assert body, (
        "the check no longer holds a pattern this file can read; it said:\n"
        f"{check}"
    )
    return re.compile(body.replace(r"\z", r"\Z"))


@pytest.fixture(scope="module")
def check() -> str:
    return _read_the_check_out_of_the_workflow()


@pytest.fixture(scope="module")
def accepts(check: str):
    pattern = _pattern_from(check)
    for guard in GUARDS_WRITTEN_BESIDE_THE_PATTERN:
        assert guard in check, (
            f"the check no longer refuses names with {guard}, so this file "
            "would stop measuring one of the rules it was written for"
        )

    def accepted(name: str) -> bool:
        return bool(
            pattern.match(name)
            and ".." not in name
            and not name.endswith((".", ".lock"))
        )

    return accepted


@pytest.fixture(scope="module")
def plan() -> dict:
    return yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))


def _dispatch_name(path: Path) -> str:
    """The name the workflow would be given for a config on disk."""
    return path.relative_to(EXPERIMENTS_ROOT).with_suffix("").as_posix()


def _runnable_configs() -> list[Path]:
    return sorted(
        path
        for path in EXPERIMENTS_ROOT.rglob("*.yaml")
        if isinstance(
            (loaded := yaml.safe_load(path.read_text(encoding="utf-8"))), dict
        )
        and CONFIG_ROOT_KEY in loaded
    )


def test_the_three_run_places_the_plan_names_can_be_given_to_the_runner(
    plan: dict, accepts
) -> None:
    """The names come from the plan, so the plan is what is being checked."""
    named = plan["experiment_files"]
    assert set(named) == {
        "host_python_process",
        "docker_container",
        "azure_code_interpreter",
    }, named

    refused = {}
    for environment, written in named.items():
        # The plan writes the path from batch-runner; the workflow is given
        # what is left after the directory it joins on and the suffix it adds.
        name = Path(written).relative_to("experiments").with_suffix("").as_posix()
        assert (EXPERIMENTS_ROOT / f"{name}.yaml").is_file(), written
        if not accepts(name):
            refused[environment] = name

    assert refused == {}, (
        "the plan names these run places' configs, and the runner cannot be "
        f"told to run them: {refused}"
    )


def test_every_config_in_the_tree_can_be_given_to_the_runner(accepts) -> None:
    """The guard for the next directory somebody groups configs into.

    Three configs sat unreachable for weeks because nothing compared what is on
    disk against what the workflow will take. This does the comparison, and
    names the files rather than making the next person find them.
    """
    configs = _runnable_configs()
    assert len(configs) > 30, "the sweep found almost nothing; check the filter"

    refused = [
        str(path.relative_to(EXPERIMENTS_ROOT))
        for path in configs
        if not accepts(_dispatch_name(path))
    ]
    assert refused == [], (
        "these experiment configs exist but the runner cannot be told to run "
        f"them: {', '.join(refused)}"
    )


def test_the_workflow_still_looks_for_the_name_under_the_experiments_directory(
    check: str,
) -> None:
    """One directory is safe only because that is all the name is joined onto.

    The pattern bounds how far a name can reach, and this is the other half of
    that: where it reaches from.
    """
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert PATH_THE_WORKFLOW_BUILDS in text


@pytest.mark.parametrize("name, why", NAMES_IT_MUST_REFUSE)
def test_the_names_it_must_go_on_refusing(accepts, name: str, why: str) -> None:
    """Taking one directory took nothing else with it."""
    assert not accepts(name), f"a name that {why} is accepted: {name!r}"


def test_ruby_reaches_the_same_verdicts_as_the_reading_of_it_here(
    check: str, accepts
) -> None:
    """The workflow's rule is Ruby's to apply, so let Ruby apply it.

    Everything else in this file reads that rule through a translation into
    Python, and a translation is a second copy of the thing it describes. Where
    Ruby is to hand — it is on the runners this workflow uses — the same names
    go through the real check and the two answers must match. Without Ruby the
    translation stands on the note in ``_pattern_from`` and this is skipped,
    which is why it is not the only test here.
    """
    ruby = shutil.which("ruby")
    if ruby is None:
        pytest.skip("no ruby on this machine to compare the reading against")

    names = [_dispatch_name(path) for path in _runnable_configs()]
    names += [name for name, _ in NAMES_IT_MUST_REFUSE]

    program = "\n".join(
        [
            "def accepted?(name)",
            "  " + "\n  ".join(line.strip() for line in check.strip().splitlines()),
            "  valid_name",
            "end",
            f"NAMES = {json.dumps(names)}",
            'NAMES.each { |n| puts (accepted?(n) ? "ACCEPT" : "REJECT") + "\\t" + n }',
        ]
    )
    finished = subprocess.run(
        [ruby, "/dev/stdin"],
        input=program,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert finished.returncode == 0, finished.stderr

    answered = finished.stdout.splitlines()
    assert len(answered) == len(names), finished.stdout

    disagreed = {}
    for line in answered:
        verdict, _, name = line.partition("\t")
        if (verdict == "ACCEPT") != accepts(name):
            disagreed[name] = f"ruby says {verdict.lower()}"
    assert disagreed == {}, (
        "this file reads the workflow's rule differently from the language "
        f"that applies it: {disagreed}"
    )


def test_the_branch_the_workflow_pushes_is_still_a_name_git_will_take(
    plan: dict,
) -> None:
    """A separator in the name reaches further than the file it opens.

    The workflow opens a pull request from ``experiment/<name>``. With a
    directory in the name that branch gains a second separator, which git does
    allow — but being allowed is a thing to show rather than assume, since the
    workflow checks the branch it pushed by name afterwards.
    """
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "branch: experiment/${{ inputs.experiment_yaml }}" in text

    for written in plan["experiment_files"].values():
        name = Path(written).relative_to("experiments").with_suffix("").as_posix()
        subprocess.run(
            ["git", "check-ref-format", "--branch", f"experiment/{name}"],
            check=True,
            capture_output=True,
        )
